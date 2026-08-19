"""Pruebas de concurrencia del cupo diario (F-19).

Van en un archivo aparte y no en tests.py por dos motivos: necesitan
`TransactionTestCase` (que es mucho mas lento porque trunca las tablas entre
casos en vez de envolver cada uno en una transaccion) y **solo tienen sentido en
Postgres**.

Por que solo en Postgres: sqlite serializa toda escritura con un solo escritor,
asi que la condicion de carrera que se prueba aqui es imposible de reproducir
ahi por construccion. Correr la suite unicamente en sqlite fue exactamente lo
que dejo pasar este bug — el CI ahora corre las dos (ver config/settings/ci.py).

El escenario: dos clientes distintos pagan el ultimo lugar del mismo dia al
mismo tiempo. Sin el lock, las dos transacciones cuentan `cupo - 1` ocupadas,
las dos pasan la validacion y las dos quedan confirmadas — sobreventa, y alguien
llega al muelle a las 6 de la manana sin panga.
"""
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock, skipUnless

from django.db import connection, connections
from django.test import TransactionTestCase

from apps.testing import crear_flota

from .models import CUPO_MAXIMO_DEFAULT, ESTADOS_QUE_OCUPAN_CUPO, Reserva

SOLO_POSTGRES = skipUnless(
    connection.vendor == 'postgresql',
    'La carrera solo existe en Postgres: sqlite serializa toda escritura.',
)


def _datos(**overrides):
    base = {
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
    }
    base.update(overrides)
    return base


def _intent_falso(reserva):
    """PaymentIntent de Stripe con lo minimo que lee aplicar_pago_exitoso."""
    return {
        'id': f'pi_carrera_{reserva.pk}',
        'amount_received': 450000,
        'currency': 'mxn',
        'created': 1786000000,
        'metadata': {'reserva_id': str(reserva.pk)},
    }


@SOLO_POSTGRES
class SobreventaConcurrenteTests(TransactionTestCase):
    """El ultimo lugar del dia solo se puede vender una vez."""

    def setUp(self):
        crear_flota()  # el motor de cupo le pregunta a la flota; sin pangas no cabe nadie
        self.fecha = date.today() + timedelta(days=10)

        # Se llena el dia hasta dejar exactamente un lugar libre.
        for _ in range(CUPO_MAXIMO_DEFAULT - 1):
            reserva = Reserva(**_datos(fecha=self.fecha, estado=Reserva.Estado.PAGADA))
            reserva.full_clean()
            reserva.save()

        # Dos clientes distintos, los dos a punto de pagar ese ultimo lugar.
        # Sin digitos en el nombre: `validar_nombre_persona` los rechaza (ver
        # apps/bookings/validators.py).
        self.pendientes = []
        for nombre in ('Cliente Uno', 'Cliente Dos'):
            reserva = Reserva(**_datos(
                fecha=self.fecha,
                nombre_cliente=nombre,
                precio_total=Decimal('4500.00'),
                forma_pago=Reserva.FormaPago.COMPLETO,
            ))
            reserva.full_clean()
            reserva.save()
            self.pendientes.append(reserva)

    def _pagar_en_paralelo(self):
        """Aplica los dos pagos a la vez, cada uno en su propio hilo y conexion.

        Devuelve la lista de resultados de aplicar_pago_exitoso.
        """
        import threading

        from apps.payments.services import aplicar_pago_exitoso

        resultados = [None, None]
        errores = [None, None]
        # Las dos peticiones deben entrar a la vez o no hay carrera que probar.
        arrancar = threading.Barrier(2)

        def pagar(indice):
            try:
                arrancar.wait(timeout=10)
                resultados[indice] = aplicar_pago_exitoso(_intent_falso(self.pendientes[indice]))
            except Exception as exc:  # noqa: BLE001 — se re-lanza en el hilo principal
                errores[indice] = exc
            finally:
                # Cada hilo abre su propia conexion; sin cerrarla, TransactionTestCase
                # se queda esperando para truncar las tablas al terminar.
                connections.close_all()

        hilos = [threading.Thread(target=pagar, args=(i,)) for i in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=30)

        for e in errores:
            if e is not None:
                raise e
        return resultados

    @mock.patch('apps.payments.services.stripe.Refund.create')
    def test_dos_pagos_simultaneos_no_sobrevenden_el_ultimo_lugar(self, refund):
        self._pagar_en_paralelo()

        pagadas = Reserva.objects.filter(
            fecha=self.fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO
        ).count()

        self.assertEqual(
            pagadas, CUPO_MAXIMO_DEFAULT,
            f'Sobreventa: {pagadas} reservas ocupan cupo y el maximo del dia es '
            f'{CUPO_MAXIMO_DEFAULT}. El lock por fecha no serializo la validacion.',
        )

    @mock.patch('apps.payments.services.stripe.Refund.create')
    def test_al_que_se_quedo_sin_lugar_se_le_devuelve_el_dinero(self, refund):
        """No basta con no sobrevender: el segundo ya pago y hay que reembolsarle
        de inmediato, dejando la reserva cancelada con el motivo real para que la
        vendedora lo vea en su panel."""
        self._pagar_en_paralelo()

        estados = sorted(
            Reserva.objects.filter(pk__in=[r.pk for r in self.pendientes])
            .values_list('estado', flat=True)
        )

        self.assertEqual(estados, sorted([Reserva.Estado.PAGADA, Reserva.Estado.CANCELADA]))
        self.assertEqual(refund.call_count, 1)

        perdedora = Reserva.objects.get(
            pk__in=[r.pk for r in self.pendientes], estado=Reserva.Estado.CANCELADA
        )
        self.assertTrue(perdedora.reembolsada)
        self.assertIn('cupo', perdedora.motivo_cancelacion.lower())


@SOLO_POSTGRES
class LockDelDiaTests(TransactionTestCase):
    """El lock es por fecha, no global: dos dias distintos no deben estorbarse."""

    @mock.patch('apps.payments.services.stripe.Refund.create')
    def test_dias_distintos_no_se_bloquean_entre_si(self, refund):
        import threading

        from apps.payments.services import APLICADO, aplicar_pago_exitoso

        reservas = []
        for i in range(2):
            reserva = Reserva(**_datos(
                fecha=date.today() + timedelta(days=10 + i),
                precio_total=Decimal('4500.00'),
                forma_pago=Reserva.FormaPago.COMPLETO,
            ))
            reserva.full_clean()
            reserva.save()
            reservas.append(reserva)

        resultados = [None, None]
        arrancar = threading.Barrier(2)

        def pagar(indice):
            try:
                arrancar.wait(timeout=10)
                resultados[indice] = aplicar_pago_exitoso(_intent_falso(reservas[indice]))
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=pagar, args=(i,)) for i in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=30)

        self.assertEqual(resultados, [APLICADO, APLICADO])
        self.assertEqual(refund.call_count, 0)
