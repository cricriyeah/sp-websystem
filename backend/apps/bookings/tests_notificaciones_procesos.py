"""Los procesos del backoffice que dejan constancia en el feed de notificaciones (catalogo del ARCH, seccion 8).

Cada prueba dice que se guarda, con que nivel y a quien se le atribuye. El feed es de apoyo: ninguna de estas
acciones depende de que la notificacion se guarde (ver `tests_notificaciones.py` en tenancy para esa garantia).
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib import admin
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.fleet.models import Capitan, Embarcacion
from apps.payments import services
from apps.payments.services import APLICADO, YA_APLICADO, aplicar_pago_exitoso
from apps.payments.tests_apartado_avisos import crear_reserva_pendiente
from apps.payments.tests_reembolso_stripe import COBRADO, LLAVES, cargo
from apps.tenancy.models import Notificacion
from apps.tenancy.tests_notificaciones import peticion
from apps.testing import ApiTestCase, EmpresaTestCase, crear_flota

from .admin import ReservaAdmin
from .models import Reserva
from .signals import _mandar
from .tests import crear_reserva
from .tests_agenda import viaje
from .tests_transferencia import NOTIFICAR, pendiente
from .transferencia import marcar_pagada_por_transferencia

ENVIO = 'apps.bookings.signals.enviar_correo_asignacion'
AL_INSTANTE = mock.patch('django.db.transaction.on_commit', side_effect=lambda funcion, *a, **k: funcion())


def del_feed(**filtros):
    return list(Notificacion.objects.filter(**filtros).order_by('pk'))


class AsignacionTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.jefe = self.crear_jefe()
        self.reserva = viaje(self.empresa, fecha=date.today() + timedelta(days=3), nombre_cliente='Ana Ruiz')
        self.panga = Embarcacion.objects.filter(empresa=self.empresa, capacidad_maxima__gte=2).first()
        self.capitan = Capitan.objects.create(empresa=self.empresa, nombre='Cap', telefono='+5216121234567')
        Reserva.objects.filter(pk=self.reserva.pk).update(embarcacion=self.panga, capitan=self.capitan)

    def test_si_el_correo_sale_queda_un_exito_con_el_correo_y_el_enlace(self):
        with mock.patch(ENVIO, return_value=True):
            _mandar(self.reserva.pk, self.empresa.pk)

        n, = del_feed(tipo=Notificacion.Tipo.ASIGNACION)
        self.assertEqual(n.nivel, Notificacion.Nivel.EXITO)
        self.assertIn('Panga y capitán asignados', n.texto)
        self.assertNotIn('ana@example.com', n.texto)  # el correo del cliente no se copia al feed por 90 dias
        self.assertIn('Ana Ruiz', n.texto)
        self.assertEqual(n.enlace_url, reverse('admin:bookings_reserva_change', args=[self.reserva.pk]))
        self.assertEqual(n.enlace_texto, 'Ver reserva')

    def test_si_el_correo_falla_queda_un_error_con_el_motivo(self):
        def falla(reserva):
            reserva.motivo_fallo_aviso = 'el proveedor de correo respondio: dominio no verificado'
            return False

        with mock.patch(ENVIO, side_effect=falla):
            _mandar(self.reserva.pk, self.empresa.pk)

        n, = del_feed(tipo=Notificacion.Tipo.ASIGNACION)
        self.assertEqual(n.nivel, Notificacion.Nivel.ERROR)
        self.assertIn('No se pudo enviar el correo de asignación a Ana Ruiz', n.texto)
        self.assertIn('avísale por WhatsApp', n.texto)
        self.assertIn('dominio no verificado', n.motivo)

    def test_un_error_inesperado_tambien_queda_en_el_feed(self):
        with mock.patch(ENVIO, side_effect=RuntimeError('boom')):
            _mandar(self.reserva.pk, self.empresa.pk)

        n, = del_feed(tipo=Notificacion.Tipo.ASIGNACION)
        self.assertEqual(n.nivel, Notificacion.Nivel.ERROR)
        self.assertIn('error inesperado', n.motivo)

    def test_quien_asigno_queda_como_actor_cuando_se_sabe(self):
        with mock.patch(ENVIO, return_value=True):
            _mandar(self.reserva.pk, self.empresa.pk, self.jefe.pk)

        self.assertEqual(del_feed()[0].actor, self.jefe)

    def test_de_punta_a_punta_desde_asignar_pangas_atribuye_la_asignacion_a_quien_guardo(self):
        Reserva.objects.filter(pk=self.reserva.pk).update(embarcacion=None, capitan=None)
        self.client.force_login(self.jefe)
        with AL_INSTANTE, mock.patch(ENVIO, return_value=True):
            self.client.post(reverse('admin:bookings_agenda_changelist'), {
                'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1',
                'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000',
                'form-0-id': str(self.reserva.pk),
                'form-0-embarcacion': str(self.panga.pk), 'form-0-capitan': str(self.capitan.pk),
                '_save': 'Guardar',
            })

        n, = del_feed(tipo=Notificacion.Tipo.ASIGNACION)
        self.assertEqual((n.nivel, n.actor), (Notificacion.Nivel.EXITO, self.jefe))

    def test_con_solo_la_panga_queda_un_aviso_de_que_falta_el_capitan(self):
        Reserva.objects.filter(pk=self.reserva.pk).update(embarcacion=None, capitan=None)
        self.client.force_login(self.jefe)
        self.client.post(reverse('admin:bookings_agenda_changelist'), {
            'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(self.reserva.pk),
            'form-0-embarcacion': str(self.panga.pk), 'form-0-capitan': '',
            '_save': 'Guardar',
        })

        n, = del_feed(tipo=Notificacion.Tipo.ASIGNACION)
        self.assertEqual((n.nivel, n.actor), (Notificacion.Nivel.AVISO, self.jefe))
        self.assertIn('Panga asignada a Ana Ruiz', n.texto)

    def test_cambiar_panga_o_capitan_de_un_viaje_ya_avisado_deja_un_aviso(self):
        otro = Capitan.objects.create(empresa=self.empresa, nombre='Otro', telefono='+5216121230000')
        Reserva.objects.filter(pk=self.reserva.pk).update(aviso_asignacion_enviado_en=timezone.now())
        self.client.force_login(self.jefe)
        self.client.post(reverse('admin:bookings_agenda_changelist'), {
            'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(self.reserva.pk),
            'form-0-embarcacion': str(self.panga.pk), 'form-0-capitan': str(otro.pk),
            '_save': 'Guardar',
        })

        n, = del_feed(tipo=Notificacion.Tipo.ASIGNACION)
        self.assertEqual(n.nivel, Notificacion.Nivel.AVISO)
        self.assertIn('no le llega aviso de cambios', n.texto)


class TransferenciaTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.jefe = self.crear_jefe()
        self.reserva = pendiente(self.empresa, nombre_cliente='Ana Ruiz')

    def _marcar(self, resultado):
        with mock.patch(NOTIFICAR, return_value=resultado), self.captureOnCommitCallbacks(execute=True):
            marcar_pagada_por_transferencia(self.reserva.pk, '1000', self.jefe)

    def test_marcar_pagada_deja_una_reserva_nueva_con_el_monto_y_quien_la_marco(self):
        self._marcar({'email': True})

        n, = del_feed()
        self.assertEqual((n.tipo, n.nivel, n.actor), (Notificacion.Tipo.RESERVA_NUEVA, Notificacion.Nivel.EXITO, self.jefe))
        self.assertIn('Ana Ruiz', n.texto)
        self.assertIn('1000.00 MXN', n.texto)
        self.assertEqual(n.enlace_url, reverse('admin:bookings_reserva_change', args=[self.reserva.pk]))

    def test_si_el_correo_de_confirmacion_no_sale_queda_ademas_un_aviso(self):
        self._marcar({'email': False})

        primera, segunda = del_feed()
        self.assertEqual(primera.tipo, Notificacion.Tipo.RESERVA_NUEVA)
        self.assertEqual((segunda.tipo, segunda.nivel), (Notificacion.Tipo.TRANSFERENCIA, Notificacion.Nivel.AVISO))
        self.assertIn('correo de confirmación', segunda.texto)
        self.assertIn('WhatsApp', segunda.texto)

    def test_la_pantalla_no_afirma_que_el_correo_fallo_si_todavia_no_se_manda(self):
        """El correo sale al confirmar la transaccion de la peticion, DESPUES de que la vista respondio. Decir «no se
        pudo mandar» por no tener el resultado todavia seria una mentira (y quedaria asi en el feed)."""
        self.client.force_login(self.jefe)
        url = reverse('admin:bookings_reserva_pagar_transferencia', args=[self.reserva.pk])

        respuesta = self.client.post(url, {'monto': '1000'}, follow=True)

        mensajes = [str(m) for m in respuesta.context['messages']]
        self.assertTrue(any('pagada por transferencia' in m for m in mensajes), mensajes)
        self.assertFalse(any('No se pudo mandar el correo' in m for m in mensajes), mensajes)

    def test_si_la_reserva_ya_no_esta_esperando_el_pago_queda_como_error(self):
        Reserva.objects.filter(pk=self.reserva.pk).update(estado=Reserva.Estado.PAGADA)
        self.client.force_login(self.jefe)

        self.client.get(reverse('admin:bookings_reserva_pagar_transferencia', args=[self.reserva.pk]))

        n, = del_feed()
        self.assertEqual((n.tipo, n.nivel, n.actor), (Notificacion.Tipo.TRANSFERENCIA, Notificacion.Nivel.ERROR, self.jefe))
        self.assertIn('ya no está esperando el pago', n.texto)


class ReservaNuevaPorTarjetaTests(ApiTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.reserva = crear_reserva_pendiente(self.empresa, nombre_cliente='Ana Ruiz')
        self.intent = {
            'id': 'pi_notif_nueva', 'amount_received': 450000, 'currency': 'mxn',
            'metadata': {'reserva_id': str(self.reserva.pk)},
            'created': int(timezone.now().timestamp()),
        }

    @mock.patch('apps.payments.services.notificar_reserva_pagada')
    def test_el_pago_exitoso_deja_una_reserva_nueva_atribuida_al_sistema(self, _):
        self.assertEqual(aplicar_pago_exitoso(self.intent, self.empresa), APLICADO)

        n, = del_feed()
        self.assertEqual((n.tipo, n.nivel, n.actor), (Notificacion.Tipo.RESERVA_NUEVA, Notificacion.Nivel.EXITO, None))
        self.assertIn('Nueva reserva pagada: Ana Ruiz', n.texto)
        self.assertIn('Pesca Deportiva', n.texto)
        self.assertEqual(n.enlace_url, reverse('admin:bookings_reserva_change', args=[self.reserva.pk]))

    @mock.patch('apps.payments.services.notificar_reserva_pagada')
    def test_stripe_reintentando_el_mismo_evento_no_duplica_la_notificacion(self, _):
        aplicar_pago_exitoso(self.intent, self.empresa)
        self.assertEqual(aplicar_pago_exitoso(self.intent, self.empresa), YA_APLICADO)

        self.assertEqual(len(del_feed()), 1)

    @mock.patch('apps.payments.services.notificar_reserva_pagada')
    def test_si_el_feed_falla_el_cobro_se_aplica_igual(self, _):
        """REQ-8 en el webhook: una notificacion que no se guarda jamas deja a un cliente sin viaje."""
        with mock.patch.object(Notificacion.objects, 'create', side_effect=Exception('feed caido')), \
                self.assertLogs('apps.tenancy.notificaciones', level='ERROR'):
            resultado = aplicar_pago_exitoso(self.intent, self.empresa)

        self.assertEqual(resultado, APLICADO)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)


@override_settings(**LLAVES)
class ReembolsoTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_webhook_secret'])
        self.reserva = crear_reserva(
            self.empresa, estado=Reserva.Estado.PAGADA, nombre_cliente='Ana Ruiz',
            forma_pago=Reserva.FormaPago.ANTICIPO, precio_total=Decimal('4500.00'),
            monto_pagado=Decimal('1350.00'), stripe_payment_intent_id='pi_ant', pagada_en=timezone.now(),
        )

    def entregar(self, objeto, evento_id='evt_notif'):
        evento = {'id': evento_id, 'type': 'charge.refunded', 'data': {'object': objeto}}
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            return self.client.post(
                reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                '{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='falsa',
            )

    def test_un_reembolso_total_deja_un_aviso_y_dice_que_la_reserva_se_cancelo(self):
        self.entregar(cargo(COBRADO))

        n, = del_feed()
        self.assertEqual((n.tipo, n.nivel, n.actor), (Notificacion.Tipo.REEMBOLSO, Notificacion.Nivel.AVISO, None))
        self.assertIn('Reembolso total', n.texto)
        self.assertIn('1350.00 MXN', n.texto)
        self.assertIn('Ana Ruiz', n.texto)
        self.assertIn('cancelada', n.texto)

    def test_un_reembolso_parcial_solo_dice_cuanto_salio(self):
        self.entregar(cargo(50000))

        n, = del_feed()
        self.assertIn('Reembolso parcial', n.texto)
        self.assertIn('500.00 MXN', n.texto)
        self.assertNotIn('cancelada', n.texto)

    def test_el_mismo_evento_repetido_no_duplica_la_notificacion(self):
        self.entregar(cargo(COBRADO), evento_id='evt_1')
        self.entregar(cargo(COBRADO), evento_id='evt_2')

        self.assertEqual(len(del_feed()), 1)

    def test_el_reembolso_que_falla_deja_un_error_con_el_detalle_una_sola_vez(self):
        reserva = self.reserva
        intent = {'amount_received': 135000}
        with mock.patch.object(services, 'notificar_fallo_reembolso'):
            for _ in range(2):
                with self.captureOnCommitCallbacks(execute=True):
                    services._gestionar_fallo_reembolso(reserva, intent, self.empresa, 'Stripe dijo: tarjeta cerrada')

        n, = del_feed()
        self.assertEqual((n.tipo, n.nivel), (Notificacion.Tipo.REEMBOLSO, Notificacion.Nivel.ERROR))
        self.assertIn('Ana Ruiz', n.texto)
        self.assertIn('tarjeta cerrada', n.motivo)


class EfectivoYCancelacionTests(EmpresaTestCase):
    def setUp(self):
        self.jefa = self.crear_jefe()
        self.client.force_login(self.jefa)
        self.lista = reverse('admin:bookings_reserva_changelist')

    def _reserva(self, estado=Reserva.Estado.PAGADA, **campos):
        datos = dict(
            forma_pago=Reserva.FormaPago.ANTICIPO, precio_total=Decimal('4500.00'),
            monto_pagado=Decimal('1350.00'), pagada_en=timezone.now(), nombre_cliente='Ana Ruiz',
        )
        datos.update(campos)
        return crear_reserva(self.empresa, estado=estado, **datos)

    def test_cobrar_el_saldo_en_efectivo_deja_el_monto_y_el_cliente_y_la_pantalla_no_cambia(self):
        reserva = self._reserva()

        respuesta = self.client.post(self.lista, {
            'action': 'registrar_liquidacion_en_efectivo', '_selected_action': [str(reserva.pk)],
            'confirmar_liquidacion': 'si',
        }, follow=True)

        n, = del_feed()
        self.assertEqual((n.tipo, n.nivel, n.actor), (Notificacion.Tipo.COBRO_EFECTIVO, Notificacion.Nivel.EXITO, self.jefa))
        self.assertIn('3150.00 MXN', n.texto)
        self.assertIn('Ana Ruiz', n.texto)
        self.assertContains(respuesta, '1 reserva(s) liquidada(s).')

    def test_si_no_se_cobro_nada_no_queda_notificacion(self):
        cancelada = self._reserva(estado=Reserva.Estado.CANCELADA, monto_reembolsado=Decimal('1350.00'))

        self.client.post(self.lista, {
            'action': 'registrar_liquidacion_en_efectivo', '_selected_action': [str(cancelada.pk)],
            'confirmar_liquidacion': 'si',
        })

        self.assertEqual(del_feed(), [])

    def test_cancelar_por_mal_clima_deja_un_aviso_con_los_clientes_y_la_pantalla_conserva_el_como_seguir(self):
        uno = self._reserva(nombre_cliente='Ana Ruiz')
        dos = self._reserva(nombre_cliente='Beto Soto')

        respuesta = self.client.post(self.lista, {
            'action': 'cancelar_por_mal_clima', '_selected_action': [str(uno.pk), str(dos.pk)],
            'confirmar_cancelacion': 'si',
        }, follow=True)

        n, = del_feed()
        self.assertEqual((n.tipo, n.nivel, n.actor), (Notificacion.Tipo.CANCELACION, Notificacion.Nivel.AVISO, self.jefa))
        self.assertIn('2 reserva(s) cancelada(s) por mal clima', n.texto)
        self.assertIn('Ana Ruiz', n.texto)
        self.assertIn('Beto Soto', n.texto)
        self.assertIn('NO se devolvió', n.texto)
        self.assertContains(respuesta, 'haz el reembolso')

    def test_cancelar_una_sola_enlaza_a_esa_reserva(self):
        uno = self._reserva()

        self.client.post(self.lista, {
            'action': 'cancelar_por_mal_clima', '_selected_action': [str(uno.pk)], 'confirmar_cancelacion': 'si',
        })

        n, = del_feed()
        self.assertEqual(n.enlace_url, reverse('admin:bookings_reserva_change', args=[uno.pk]))


class CambioDeFechaTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.jefe = self.crear_jefe()
        self.admin = ReservaAdmin(Reserva, admin.site)

    def _guardar_con_nueva_fecha(self, reserva, cambiados=('fecha',)):
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.fecha = reserva.fecha + timedelta(days=2)
        form = mock.Mock(changed_data=list(cambiados))
        self.admin.save_model(peticion(self.jefe), reserva, form, change=True)
        return reserva

    def test_cambiar_la_fecha_de_una_reserva_pagada_avisa_que_al_cliente_no_le_llega_nada(self):
        reserva = viaje(self.empresa, estado=Reserva.Estado.PAGADA, nombre_cliente='Ana Ruiz',
                        fecha=date.today() + timedelta(days=10))

        cambiada = self._guardar_con_nueva_fecha(reserva)

        n, = del_feed()
        self.assertEqual((n.tipo, n.nivel, n.actor), (Notificacion.Tipo.CAMBIO_FECHA, Notificacion.Nivel.AVISO, self.jefe))
        self.assertIn('Ana Ruiz', n.texto)
        self.assertIn(cambiada.fecha.strftime('%d/%m/%Y'), n.texto)
        self.assertIn('no le llega aviso', n.texto)

    def test_si_la_fecha_no_cambio_no_queda_nada(self):
        reserva = viaje(self.empresa, estado=Reserva.Estado.PAGADA, fecha=date.today() + timedelta(days=10))

        self._guardar_con_nueva_fecha(reserva, cambiados=('nombre_cliente',))

        self.assertEqual(del_feed(), [])

    def test_una_reserva_que_aun_no_se_paga_no_avisa_porque_el_cliente_no_tiene_nada_agendado(self):
        reserva = viaje(self.empresa, estado=Reserva.Estado.PENDIENTE_PAGO, fecha=date.today() + timedelta(days=10))

        self._guardar_con_nueva_fecha(reserva)

        self.assertEqual(del_feed(), [])
