"""El aviso de asignacion tambien tiene que salir al repartir desde «Asignar pangas».

Esa pantalla guarda a traves del proxy `Agenda`, y Django manda `post_save` con el proxy como emisor: una senal
conectada solo a `Reserva` no se enteraba (en produccion el cliente no recibio el correo).
"""
from datetime import date, timedelta
from unittest import mock

from django.urls import reverse

from apps.fleet.models import Capitan, Embarcacion
from apps.testing import EmpresaTestCase, crear_flota

from .tests_agenda import viaje

ENVIO = 'apps.bookings.signals.enviar_correo_asignacion'


class AvisoDesdeLaAgendaTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())
        self.reserva = viaje(self.empresa, fecha=date.today() + timedelta(days=1))
        self.panga = Embarcacion.objects.filter(empresa=self.empresa, capacidad_maxima__gte=2).first()
        self.capitan = Capitan.objects.create(empresa=self.empresa, nombre='Cap', telefono='+5216121234567')

    def _guardar(self, panga, capitan):
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(self.url, {
                'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1',
                'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000',
                'form-0-id': str(self.reserva.pk),
                'form-0-embarcacion': str(panga.pk) if panga else '',
                'form-0-capitan': str(capitan.pk) if capitan else '',
                '_save': 'Guardar',
            })
        self.assertEqual(respuesta.status_code, 302)
        self.reserva.refresh_from_db()

    def test_panga_y_luego_capitan_desde_la_agenda_manda_un_solo_correo(self):
        with mock.patch(ENVIO, return_value=True) as enviar:
            self._guardar(self.panga, None)
            enviar.assert_not_called()
            self._guardar(self.panga, self.capitan)
            enviar.assert_called_once()
            self._guardar(self.panga, self.capitan)
            enviar.assert_called_once()

        self.assertIsNotNone(self.reserva.aviso_asignacion_enviado_en)

    def test_solo_la_panga_no_manda_nada(self):
        with mock.patch(ENVIO, return_value=True) as enviar:
            self._guardar(self.panga, None)

        enviar.assert_not_called()
        self.assertIsNone(self.reserva.aviso_asignacion_enviado_en)
