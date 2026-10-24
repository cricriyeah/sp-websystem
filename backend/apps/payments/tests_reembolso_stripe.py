"""Reembolsos hechos desde el panel de Stripe (`charge.refunded`).

El caso real que origino estas pruebas (2026-10-23): la duena devolvio desde
Stripe un anticipo del 30%. El formulario de la reserva decia "reembolsada",
pero el estado seguia en "pagada": la reserva seguia ocupando cupo, panga y
capitan, la columna Cobro decia "Debe ... en efectivo" y el correo de
asignacion todavia podia salir.

Regla que se prueba aqui: un reembolso TOTAL deja la reserva igual que
«Cancelar por mal clima» + reembolso; uno PARCIAL solo registra cuanto salio.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO, Reserva, ReservaOcupacion
from apps.bookings.tests import crear_reserva, datos_reserva
from apps.fleet.models import Capitan, Embarcacion, Recurso, Servicio
from apps.payments.situacion import requiere_atencion, situacion_de_reserva
from apps.testing import ApiTestCase

LLAVES = {'STRIPE_SECRET_KEY': 'sk_test_falsa', 'STRIPE_WEBHOOK_SECRET': 'whsec_falsa'}

# Anticipo del 30% sobre un tour de 4,500: Stripe cobro 1,350 y el resto va en efectivo.
COBRADO = 135000


def cargo(devuelto, cobrado=COBRADO, intent='pi_ant', **extra):
    """El `Charge` que viaja dentro de `charge.refunded`. `amount_refunded` es
    ACUMULADO (todo lo devuelto de ese cargo hasta ese evento) y `refunded` solo
    es true cuando ya se devolvio el cargo completo."""
    return {
        'id': 'ch_1', 'payment_intent': intent,
        'amount': cobrado, 'amount_refunded': devuelto,
        'refunded': devuelto >= cobrado, **extra,
    }


@override_settings(**LLAVES)
class ReembolsoDesdeStripeTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_webhook_secret'])
        self.reserva = crear_reserva(
            self.empresa, estado=Reserva.Estado.PAGADA,
            forma_pago=Reserva.FormaPago.ANTICIPO,
            precio_total=Decimal('4500.00'), monto_pagado=Decimal('1350.00'),
            stripe_payment_intent_id='pi_ant', pagada_en=timezone.now(),
        )

    def entregar(self, objeto, evento_id='evt_x'):
        evento = {'id': evento_id, 'type': 'charge.refunded', 'data': {'object': objeto}}
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            return self.client.post(
                reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                '{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='falsa',
            )

    def recargar(self):
        self.reserva.refresh_from_db()
        return self.reserva

    def asignar_panga_y_capitan(self):
        panga = Embarcacion.objects.filter(empresa=self.empresa).first()
        capitan = Capitan.objects.create(
            empresa=self.empresa, nombre='Ramon Geraldo', telefono='+5216129876543')
        Reserva.objects.filter(pk=self.reserva.pk).update(
            embarcacion=panga, capitan=capitan, estado=Reserva.Estado.ASIGNADA)
        return panga, capitan

    # --- reembolso total -------------------------------------------------

    def test_reembolso_total_cancela_la_reserva_como_el_mal_clima(self):
        self.entregar(cargo(COBRADO))

        reserva = self.recargar()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva.reembolsada)
        self.assertEqual(reserva.monto_reembolsado, Decimal('1350.00'))
        self.assertIsNotNone(reserva.reembolsada_en)
        self.assertIsNotNone(reserva.cancelada_en)
        # No la cancelo una persona de este sistema: el motivo explica de donde vino.
        self.assertIsNone(reserva.cancelada_por)
        self.assertIn('Stripe', reserva.motivo_cancelacion)

    def test_reembolso_total_de_una_asignada_tambien_la_cancela(self):
        self.asignar_panga_y_capitan()

        self.entregar(cargo(COBRADO))

        self.assertEqual(self.recargar().estado, Reserva.Estado.CANCELADA)

    def test_reembolso_total_ya_no_cuenta_como_devolucion_pendiente(self):
        self.entregar(cargo(COBRADO))

        reserva = self.recargar()
        self.assertFalse(requiere_atencion(situacion_de_reserva(
            estado=reserva.estado, monto_pagado=reserva.monto_pagado,
            monto_reembolsado=reserva.monto_reembolsado,
        )))

    def test_reembolso_total_suelta_el_cupo(self):
        self.assertIn(self.reserva.estado, ESTADOS_QUE_OCUPAN_CUPO)

        self.entregar(cargo(COBRADO))

        self.assertNotIn(self.recargar().estado, ESTADOS_QUE_OCUPAN_CUPO)

    def test_reembolso_total_libera_la_panga_y_el_capitan_del_dia(self):
        panga, capitan = self.asignar_panga_y_capitan()
        otra = Reserva(**datos_reserva(
            self.empresa, nombre_cliente='Otra clienta', estado=Reserva.Estado.PAGADA,
            embarcacion=panga, capitan=capitan))
        with self.assertRaises(Exception) as bloqueo:
            otra.full_clean()
        self.assertIn('ya tiene un viaje', str(bloqueo.exception))

        self.entregar(cargo(COBRADO))

        otra.full_clean()  # ya no lanza: la panga y el capitan quedaron libres

    def test_reembolso_total_libera_la_habitacion(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Suite', slug='suite-reembolso',
            tipo_servicio='hospedaje', estrategia_cupo='por_noche', precio_base=3000,
        )
        recurso = Recurso.objects.create(
            empresa=self.empresa, servicio=servicio, nombre='Cabana 1', capacidad_maxima=4)
        hoy = timezone.localdate()
        hotel = Reserva.objects.create(
            empresa=self.empresa, servicio=servicio,
            fecha=hoy + timedelta(days=20), fecha_salida=hoy + timedelta(days=23),
            numero_personas=2, nombre_cliente='Hotel Cliente', telefono_cliente='+5216121234567',
            correo_cliente='hotel@example.com', canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True, deslinde_nombre='Hotel Cliente',
            estado=Reserva.Estado.PAGADA, forma_pago=Reserva.FormaPago.COMPLETO,
            precio_total=Decimal('9000.00'), monto_pagado=Decimal('9000.00'),
            stripe_payment_intent_id='pi_hotel',
        )
        ocupacion = ReservaOcupacion.objects.create(
            empresa=self.empresa, reserva=hotel, recurso=recurso,
            fecha_inicio=hotel.fecha, fecha_fin=hotel.fecha_salida,
        )
        self.assertTrue(ocupacion.ocupa_cupo)

        self.entregar(cargo(900000, cobrado=900000, intent='pi_hotel'))

        ocupacion.refresh_from_db()
        self.assertFalse(ocupacion.ocupa_cupo)

    def test_reembolso_total_no_manda_el_correo_de_asignacion(self):
        self.asignar_panga_y_capitan()

        with mock.patch('apps.bookings.signals.enviar_correo_asignacion', return_value=True) as correo:
            with self.captureOnCommitCallbacks(execute=True):
                self.entregar(cargo(COBRADO))

        correo.assert_not_called()

    def test_un_evento_sin_monto_se_toma_como_reembolso_total(self):
        """Forma historica del evento (sin `amount_refunded`): se asume que se
        devolvio todo lo cobrado, como siempre."""
        self.entregar({'id': 'ch_1', 'payment_intent': 'pi_ant'})

        reserva = self.recargar()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertEqual(reserva.monto_reembolsado, Decimal('1350.00'))

    # --- reembolso parcial -------------------------------------------------

    def test_reembolso_parcial_solo_registra_cuanto_salio(self):
        self.entregar(cargo(50000))

        reserva = self.recargar()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertFalse(reserva.reembolsada)
        self.assertEqual(reserva.monto_reembolsado, Decimal('500.00'))
        self.assertIsNotNone(reserva.reembolsada_en)
        self.assertIsNone(reserva.cancelada_en)
        self.assertEqual(reserva.motivo_cancelacion, '')

    def test_reembolso_parcial_conserva_panga_y_capitan(self):
        panga, capitan = self.asignar_panga_y_capitan()

        self.entregar(cargo(50000))

        reserva = self.recargar()
        self.assertEqual(reserva.estado, Reserva.Estado.ASIGNADA)
        self.assertEqual((reserva.embarcacion, reserva.capitan), (panga, capitan))

    def test_dos_parciales_acumulan_sin_sumarse_dos_veces(self):
        """`amount_refunded` ya es acumulado: el segundo evento trae 800, no 300."""
        self.entregar(cargo(50000), evento_id='evt_1')
        self.entregar(cargo(80000), evento_id='evt_2')

        reserva = self.recargar()
        self.assertEqual(reserva.monto_reembolsado, Decimal('800.00'))
        self.assertFalse(reserva.reembolsada)
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)

    def test_cada_reembolso_nuevo_actualiza_la_fecha_de_la_salida(self):
        self.entregar(cargo(50000), evento_id='evt_1')
        primera = self.recargar().reembolsada_en
        # Se manda al pasado en vez de dormir el test hasta que el reloj avance.
        Reserva.objects.filter(pk=self.reserva.pk).update(
            reembolsada_en=primera - timedelta(days=3))
        antes = self.recargar().reembolsada_en

        self.entregar(cargo(80000), evento_id='evt_2')

        self.assertGreater(self.recargar().reembolsada_en, antes + timedelta(days=2))

    def test_parcial_y_luego_total_cancela_y_actualiza_la_fecha(self):
        self.entregar(cargo(50000), evento_id='evt_1')
        Reserva.objects.filter(pk=self.reserva.pk).update(
            reembolsada_en=timezone.now() - timedelta(days=3))
        antes = self.recargar().reembolsada_en

        self.entregar(cargo(COBRADO), evento_id='evt_2')

        reserva = self.recargar()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva.reembolsada)
        self.assertEqual(reserva.monto_reembolsado, Decimal('1350.00'))
        self.assertGreater(reserva.reembolsada_en, antes + timedelta(days=2))

    def test_la_salida_parcial_llega_a_finanzas(self):
        from apps.finance.services import balances

        self.entregar(cargo(50000))

        hoy = timezone.localdate()
        balance = balances(hoy, hoy, empresa=self.empresa)['MXN']
        self.assertEqual(balance.reembolsos, Decimal('500.00'))
        self.assertEqual(balance.en_cuenta, Decimal('1350.00') - Decimal('500.00'))

    # --- repeticiones y desorden -----------------------------------------------

    def test_el_mismo_evento_total_dos_veces_no_hace_nada_la_segunda(self):
        self.entregar(cargo(COBRADO))
        primera = self.recargar()
        estado = (primera.estado, primera.monto_reembolsado, primera.reembolsada_en,
                  primera.cancelada_en, primera.motivo_cancelacion)

        self.entregar(cargo(COBRADO))

        segunda = self.recargar()
        self.assertEqual(estado, (segunda.estado, segunda.monto_reembolsado,
                                  segunda.reembolsada_en, segunda.cancelada_en,
                                  segunda.motivo_cancelacion))

    def test_el_mismo_evento_parcial_dos_veces_no_cambia_la_fecha_ni_el_monto(self):
        self.entregar(cargo(50000))
        primera = self.recargar()

        self.entregar(cargo(50000))

        segunda = self.recargar()
        self.assertEqual(segunda.monto_reembolsado, primera.monto_reembolsado)
        self.assertEqual(segunda.reembolsada_en, primera.reembolsada_en)

    def test_un_parcial_atrasado_no_deshace_el_reembolso_total(self):
        """Stripe no garantiza el orden: el evento del primer reembolso (500) puede
        llegar despues del que ya trae todo el cargo devuelto (1,350)."""
        self.entregar(cargo(COBRADO), evento_id='evt_total')
        total = self.recargar()

        self.entregar(cargo(50000), evento_id='evt_viejo')

        reserva = self.recargar()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva.reembolsada)
        self.assertEqual(reserva.monto_reembolsado, Decimal('1350.00'))
        self.assertEqual(reserva.reembolsada_en, total.reembolsada_en)

    def test_un_parcial_atrasado_no_baja_el_monto_de_otro_parcial_mayor(self):
        self.entregar(cargo(80000), evento_id='evt_2')
        mayor = self.recargar()

        self.entregar(cargo(50000), evento_id='evt_1')

        reserva = self.recargar()
        self.assertEqual(reserva.monto_reembolsado, Decimal('800.00'))
        self.assertEqual(reserva.reembolsada_en, mayor.reembolsada_en)

    # --- reservas que ya venian cancelando o en otro punto del ciclo -------------

    def test_si_ya_estaba_cancelada_por_mal_clima_solo_se_registra_el_dinero(self):
        antes = timezone.now() - timedelta(days=1)
        Reserva.objects.filter(pk=self.reserva.pk).update(
            estado=Reserva.Estado.CANCELADA, motivo_cancelacion='Mal clima',
            cancelada_en=antes, reembolsada=True)

        self.entregar(cargo(COBRADO))

        reserva = self.recargar()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertEqual(reserva.motivo_cancelacion, 'Mal clima')
        self.assertEqual(reserva.cancelada_en, antes)
        self.assertEqual(reserva.monto_reembolsado, Decimal('1350.00'))
        self.assertIsNotNone(reserva.reembolsada_en)

    def test_un_parcial_no_apaga_la_decision_de_reembolsar_ya_tomada(self):
        Reserva.objects.filter(pk=self.reserva.pk).update(
            estado=Reserva.Estado.CANCELADA, motivo_cancelacion='Mal clima', reembolsada=True)

        self.entregar(cargo(50000))

        reserva = self.recargar()
        self.assertTrue(reserva.reembolsada)
        self.assertEqual(reserva.monto_reembolsado, Decimal('500.00'))

    def test_una_completada_reembolsada_por_completo_conserva_su_estado(self):
        """El viaje ya ocurrio: se anota la devolucion, pero no se reescribe la
        historia ni se vuelve a soltar un cupo que ya paso."""
        Reserva.objects.filter(pk=self.reserva.pk).update(estado=Reserva.Estado.COMPLETADA)

        self.entregar(cargo(COBRADO))

        reserva = self.recargar()
        self.assertEqual(reserva.estado, Reserva.Estado.COMPLETADA)
        self.assertTrue(reserva.reembolsada)
        self.assertEqual(reserva.monto_reembolsado, Decimal('1350.00'))

    def test_un_reembolso_que_llega_antes_que_el_pago_no_toca_la_reserva(self):
        """Si `charge.refunded` gana la carrera contra `payment_intent.succeeded`
        la reserva sigue sin pagar: no hay nada que cancelar ni que registrar
        todavia, y marcarla ahora dejaria una salida sin su entrada."""
        Reserva.objects.filter(pk=self.reserva.pk).update(
            estado=Reserva.Estado.PENDIENTE_PAGO, monto_pagado=None, pagada_en=None)

        respuesta = self.entregar(cargo(COBRADO))

        self.assertEqual(respuesta.status_code, 200)
        reserva = self.recargar()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertIsNone(reserva.monto_reembolsado)
        self.assertFalse(reserva.reembolsada)
