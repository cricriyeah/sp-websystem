"""Al repartir panga y capitan, el admin dice que paso con el aviso al cliente.

Antes todo era mudo: un correo que no salia solo quedaba en el log del servidor y nadie se enteraba.
El correo sale al confirmar la transaccion; las pruebas la confirman al instante para que ocurra dentro de la
peticion, como en produccion (alli el guardado de la vista confirma antes de que la vista termine).
"""
from datetime import date, timedelta
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.fleet.models import Capitan, Embarcacion
from apps.notifications import services
from apps.testing import EmpresaTestCase, crear_flota

from .tests_agenda import viaje

ENVIO = 'apps.bookings.signals.enviar_correo_asignacion'
AL_INSTANTE = mock.patch('django.db.transaction.on_commit', side_effect=lambda funcion, *a, **k: funcion())


class MensajesDeAsignacionTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())
        self.reserva = viaje(self.empresa, fecha=date.today() + timedelta(days=1), nombre_cliente='Ana Ruiz')
        self.panga = Embarcacion.objects.filter(empresa=self.empresa, capacidad_maxima__gte=2).first()
        self.capitan = Capitan.objects.create(empresa=self.empresa, nombre='Cap', telefono='+5216121234567')

    def _guardar(self, panga, capitan):
        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(self.reserva.pk),
            'form-0-embarcacion': str(panga.pk) if panga else '',
            'form-0-capitan': str(capitan.pk) if capitan else '',
            '_save': 'Guardar',
        }, follow=True)
        self.reserva.refresh_from_db()
        return [str(m) for m in respuesta.context['messages']]

    def test_dice_que_el_correo_salio(self):
        with AL_INSTANTE, mock.patch(ENVIO, return_value=True):
            self._guardar(self.panga, None)
            mensajes = self._guardar(self.panga, self.capitan)

        self.assertTrue(any('Correo enviado a ana@example.com' in m for m in mensajes), mensajes)

    def test_si_el_correo_falla_dice_por_que_y_que_la_asignacion_si_quedo(self):
        def falla(reserva):
            reserva.motivo_fallo_aviso = 'el proveedor de correo respondio: dominio no verificado'
            return False

        with AL_INSTANTE, mock.patch(ENVIO, side_effect=falla):
            self._guardar(self.panga, None)
            mensajes = self._guardar(self.panga, self.capitan)

        error = [m for m in mensajes if 'No se pudo avisar a Ana Ruiz' in m]
        self.assertEqual(len(error), 1, mensajes)
        self.assertIn('dominio no verificado', error[0])
        self.assertIn('sí quedó guardada', error[0])
        self.assertEqual(self.reserva.capitan_id, self.capitan.pk)
        self.assertIsNone(self.reserva.aviso_asignacion_enviado_en)

    def test_un_error_inesperado_tambien_se_dice(self):
        with AL_INSTANTE, mock.patch(ENVIO, side_effect=RuntimeError('boom')):
            self._guardar(self.panga, None)
            mensajes = self._guardar(self.panga, self.capitan)

        self.assertTrue(any('No se pudo avisar a Ana Ruiz' in m and 'error inesperado' in m for m in mensajes), mensajes)

    def test_con_solo_la_panga_explica_que_falta_el_capitan(self):
        with AL_INSTANTE, mock.patch(ENVIO, return_value=True) as enviar:
            mensajes = self._guardar(self.panga, None)

        enviar.assert_not_called()
        self.assertTrue(any('Panga asignada a Ana Ruiz' in m and 'capitán' in m for m in mensajes), mensajes)
        self.assertFalse(any('Correo enviado' in m for m in mensajes))

    def test_si_ya_se_aviso_un_cambio_avisa_que_el_cliente_no_se_entera(self):
        otro = Capitan.objects.create(empresa=self.empresa, nombre='Otro', telefono='+5216121230000')
        with AL_INSTANTE, mock.patch(ENVIO, return_value=True):
            self._guardar(self.panga, None)
            self._guardar(self.panga, self.capitan)
            mensajes = self._guardar(self.panga, otro)

        self.assertTrue(any('no le llega aviso de cambios' in m for m in mensajes), mensajes)

    def test_no_arrastra_resultados_de_antes_de_esta_peticion(self):
        """Un aviso que salio desde otro lugar (webhook, shell) en el mismo proceso no se cuela en esta pantalla."""
        from apps.bookings import signals

        signals._anotar_resultado(self.reserva, True)
        with AL_INSTANTE, mock.patch(ENVIO, return_value=True):
            mensajes = self._guardar(self.panga, None)

        self.assertFalse(any('Correo enviado' in m for m in mensajes), mensajes)


class MotivoDeFalloDelCorreoTests(EmpresaTestCase):
    @override_settings(RESEND_API_KEY='k', RESEND_FROM='a@b.com')
    def test_una_reserva_sin_correo_no_intenta_mandar_y_dice_por_que(self):
        reserva = viaje(self.empresa, fecha=date.today() + timedelta(days=1), correo_cliente='')
        with mock.patch.object(services.requests, 'post') as post:
            enviado = services.enviar_correo_asignacion(reserva)

        self.assertFalse(enviado)
        post.assert_not_called()
        self.assertIn('no tiene correo', reserva.motivo_fallo_aviso)

    @override_settings(RESEND_API_KEY='', RESEND_FROM='')
    def test_sin_resend_configurado_dice_que_no_esta_configurado(self):
        reserva = viaje(self.empresa, fecha=date.today() + timedelta(days=1))
        self.assertFalse(services.enviar_correo_asignacion(reserva))
        self.assertIn('no esta configurado', reserva.motivo_fallo_aviso)

    @override_settings(RESEND_API_KEY='k', RESEND_FROM='a@b.com')
    def test_si_resend_rechaza_el_motivo_es_su_mensaje(self):
        reserva = viaje(self.empresa, fecha=date.today() + timedelta(days=1))
        reserva.embarcacion = Embarcacion.objects.filter(empresa=self.empresa).first()
        reserva.capitan = Capitan.objects.create(empresa=self.empresa, nombre='Cap', telefono='+5216121234567')
        respuesta = mock.Mock(text='{"message":"The domain is not verified"}')
        respuesta.json.return_value = {'message': 'The domain is not verified'}
        error = services.requests.HTTPError('422', response=respuesta)
        respuesta.raise_for_status.side_effect = error
        with mock.patch.object(services.requests, 'post', return_value=respuesta):
            enviado = services.enviar_correo_asignacion(reserva)

        self.assertFalse(enviado)
        self.assertIn('The domain is not verified', reserva.motivo_fallo_aviso)
