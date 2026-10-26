"""Arreglos de la auditoria de seguridad (CSO-notificaciones-backoffice): H-1, M-1, M-2, B-1, B-2.

H-1: marcar pagada por transferencia un checkout abandonado deja vivo su PaymentIntent; si el cliente lo completa
despues, el webhook lo tomaba por "evento repetido" y no reembolsaba (doble cobro sin rastro).
"""
from decimal import Decimal
from unittest import mock

import stripe
from django.contrib.sessions.models import Session
from django.test import override_settings
from django.urls import reverse

from apps.payments.services import DUPLICADO_REEMBOLSADO, aplicar_pago_exitoso
from apps.tenancy import scope
from apps.tenancy.notificaciones import enlace_seguro
from apps.testing import EmpresaTestCase

from .models import MovimientoDinero, Reserva
from .tests_transferencia import NOTIFICAR, pendiente
from .transferencia import ErrorDeTransferencia, marcar_pagada_por_transferencia

CLIENTE = 'apps.bookings.transferencia.configurar_stripe'


def _cliente_stripe(estado, **extra):
    cliente = mock.Mock()
    cliente.payment_intents.retrieve.return_value = mock.Mock(status=estado, id='pi_abandonado')
    for nombre, valor in extra.items():
        setattr(cliente.payment_intents, nombre, valor)
    return cliente


class CerrarElCobroConTarjetaTests(EmpresaTestCase):
    def setUp(self):
        self.jefe = self.crear_jefe()
        self.empresa.stripe_secret_key = 'sk_test_abc'
        self.empresa.save()
        self.reserva = pendiente(self.empresa, stripe_payment_intent_id='pi_abandonado')

    def _marcar(self):
        with mock.patch(NOTIFICAR, return_value={}), self.captureOnCommitCallbacks(execute=True):
            return marcar_pagada_por_transferencia(self.reserva.pk, '1000', self.jefe)

    def test_un_intent_abierto_se_anula_antes_de_saldar(self):
        cliente = _cliente_stripe('requires_payment_method')
        with mock.patch(CLIENTE, return_value=cliente):
            self._marcar()

        cliente.payment_intents.cancel.assert_called_once_with(
            'pi_abandonado', options={'idempotency_key': f'transferencia-{self.reserva.pk}-cancel'})
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)

    def test_un_intent_ya_cobrado_o_en_curso_se_rechaza_y_no_se_guarda_nada(self):
        for estado in ('succeeded', 'processing', 'requires_capture'):
            with self.subTest(estado=estado):
                cliente = _cliente_stripe(estado)
                with mock.patch(CLIENTE, return_value=cliente), self.assertRaises(ErrorDeTransferencia) as ctx:
                    self._marcar()

                self.assertIn('ya pagó o está pagando con tarjeta', str(ctx.exception))
                cliente.payment_intents.cancel.assert_not_called()
                self.reserva.refresh_from_db()
                self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
                self.assertFalse(MovimientoDinero.objects.filter(reserva=self.reserva).exists())

    def test_si_stripe_falla_no_se_salda(self):
        cliente = _cliente_stripe('requires_action')
        cliente.payment_intents.cancel.side_effect = stripe.APIConnectionError('sin red')
        with mock.patch(CLIENTE, return_value=cliente), self.assertRaises(ErrorDeTransferencia) as ctx:
            self._marcar()

        self.assertIn('No se pudo cerrar el cobro con tarjeta pendiente', str(ctx.exception))
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PENDIENTE_PAGO)

    def test_un_intent_que_ya_no_existe_en_stripe_no_estorba(self):
        cliente = mock.Mock()
        cliente.payment_intents.retrieve.side_effect = stripe.InvalidRequestError(
            'No such payment_intent', 'id', code='resource_missing')
        with mock.patch(CLIENTE, return_value=cliente):
            self._marcar()

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)

    def test_otro_error_de_stripe_si_se_rechaza(self):
        cliente = mock.Mock()
        cliente.payment_intents.retrieve.side_effect = stripe.InvalidRequestError(
            'Invalid API Key', None, code='api_key_invalid')
        with mock.patch(CLIENTE, return_value=cliente), self.assertRaises(ErrorDeTransferencia):
            self._marcar()

    def test_sin_intent_no_se_habla_con_stripe(self):
        reserva = pendiente(self.empresa)  # checkout que nunca llego a crear-pago ya trae precio, pero no intent
        with mock.patch(CLIENTE) as cliente, mock.patch(NOTIFICAR, return_value={}), \
                self.captureOnCommitCallbacks(execute=True):
            marcar_pagada_por_transferencia(reserva.pk, '1000', self.jefe)

        cliente.assert_not_called()


class CobroPosteriorALaTransferenciaTests(EmpresaTestCase):
    """Defensa en profundidad: si aun asi llega el cobro del intent guardado, es un doble cobro y se devuelve."""

    def test_el_cobro_del_intent_guardado_tras_una_transferencia_se_reembolsa(self):
        jefe = self.crear_jefe()
        reserva = pendiente(self.empresa, stripe_payment_intent_id='pi_abandonado')
        with mock.patch(NOTIFICAR, return_value={}), self.captureOnCommitCallbacks(execute=True):
            marcar_pagada_por_transferencia(reserva.pk, '1000', jefe)

        intent = {'id': 'pi_abandonado', 'amount_received': 100000, 'metadata': {'reserva_id': str(reserva.pk)}}
        with mock.patch('apps.payments.services.reembolsar', return_value=True) as reembolsar, \
                scope.con_empresa(self.empresa):
            resultado = aplicar_pago_exitoso(intent, self.empresa)

        self.assertEqual(resultado, DUPLICADO_REEMBOLSADO)
        reembolsar.assert_called_once()

    def test_un_evento_repetido_de_un_pago_ya_aplicado_sigue_siendo_repetido(self):
        reserva = pendiente(self.empresa, stripe_payment_intent_id='pi_ok')
        Reserva.objects.filter(pk=reserva.pk).update(estado=Reserva.Estado.PAGADA, monto_pagado=Decimal('1000.00'))

        intent = {'id': 'pi_ok', 'amount_received': 100000, 'metadata': {'reserva_id': str(reserva.pk)}}
        with mock.patch('apps.payments.services.reembolsar') as reembolsar, scope.con_empresa(self.empresa):
            resultado = aplicar_pago_exitoso(intent, self.empresa)

        self.assertEqual(resultado, 'ya_aplicado')
        reembolsar.assert_not_called()


class PrecioNuloTests(EmpresaTestCase):
    def test_sin_precio_calculado_no_se_acepta_ningun_monto(self):
        jefe = self.crear_jefe()
        reserva = pendiente(self.empresa, precio_total=None)

        with self.assertRaises(ErrorDeTransferencia) as ctx:
            marcar_pagada_por_transferencia(reserva.pk, '5000000', jefe)

        self.assertIn('todavía no tiene precio', str(ctx.exception))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)


class SondeoNoRenuevaLaSesionTests(EmpresaTestCase):
    """M-2: el sondeo corre solo cada 10 s; no debe contar como actividad."""

    def _vence(self):
        return Session.objects.get(session_key=self.client.session.session_key).expire_date

    @override_settings(SESSION_SAVE_EVERY_REQUEST=True)
    def test_el_sondeo_no_mueve_el_vencimiento_pero_otra_pagina_si(self):
        self.client.force_login(self.crear_jefe())
        antes = self._vence()

        self.client.get(reverse('avisos_reservas_nuevas'))
        self.client.get(reverse('avisos_reservas_nuevas'))
        self.assertEqual(self._vence(), antes)

        self.client.get(reverse('admin:index'))
        self.assertGreater(self._vence(), antes)


class EnlaceSeguroTests(EmpresaTestCase):
    def test_solo_pasan_rutas_propias_limpias(self):
        for bueno in ('/admin/bookings/reserva/5/change/', '/admin/x/?a=1&b=2'):
            with self.subTest(bueno=bueno):
                self.assertEqual(enlace_seguro(bueno), bueno)
        for malo in ('https://evil.com', '//evil.com', 'javascript:alert(1)', '/\\evil.com', '/\t/evil.com',
                     '/\n/evil.com', '/ /evil.com', '/a\x7fb', 'x' * 400, '', None):
            with self.subTest(malo=malo):
                self.assertEqual(enlace_seguro(malo), '')


class SondeoConFechaImposibleTests(EmpresaTestCase):
    def test_una_fecha_con_mes_13_responde_400_y_no_500(self):
        self.client.force_login(self.crear_jefe())

        respuesta = self.client.get(reverse('avisos_reservas_nuevas'), {'desde': '2026-13-45T00:00:00'})

        self.assertEqual(respuesta.status_code, 400)
