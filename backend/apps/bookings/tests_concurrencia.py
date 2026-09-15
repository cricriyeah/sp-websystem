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

`TransactionTestCase` no hereda el `setUp` de `EmpresaTestCase` (pensado para
`TestCase`, transaccional): cada clase crea su propia Sede/Empresa desde cero.
Y el punto entero de este archivo es que cada hilo abre **su propia conexion**,
que el `con_empresa` del hilo principal no cubre -- cada `target` de hilo
resuelve `Empresa` y abre su propio `con_empresa` a partir de un `empresa_id`
capturado ANTES de lanzar el hilo (no el objeto, que quedo resuelto en la
conexion principal).
"""
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock, skipUnless

from django.db import connection, connections
from django.test import TransactionTestCase

from apps.fleet.models import Recurso, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import crear_flota, crear_servicio_pesca

from stripe import StripeClient

from .models import CUPO_MAXIMO_DEFAULT, ESTADOS_QUE_OCUPAN_CUPO, Reserva, ReservaOcupacion

SOLO_POSTGRES = skipUnless(
    connection.vendor == 'postgresql',
    'La carrera solo existe en Postgres: sqlite serializa toda escritura.',
)


def _crear_empresa_de_prueba():
    """`TransactionTestCase` trunca las tablas entre casos -- no hereda el `setUp`
    de `EmpresaTestCase` (pensado para `TestCase`, transaccional). Cada test de este
    archivo crea su propia Sede/Empresa desde cero, igual que hacia antes con la
    flota."""
    sede = Sede.objects.create(
        nombre='Sede concurrencia', slug='sede-concurrencia', zona_horaria='America/Mazatlan')
    return Empresa.objects.create(
        sede=sede, nombre='Empresa concurrencia', slug='empresa-concurrencia', activo=True)


def _datos(empresa, **overrides):
    base = {
        'empresa': empresa,
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
    if 'servicio' not in overrides and 'paquete' not in overrides:
        empresa_real = overrides.get('empresa', empresa)
        base['servicio'] = crear_servicio_pesca(empresa_real)
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
        self.empresa = _crear_empresa_de_prueba()
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)  # el motor de cupo le pregunta a la flota; sin pangas no cabe nadie
            self.fecha = date.today() + timedelta(days=10)

            # Se llena el dia hasta dejar exactamente un lugar libre.
            for _ in range(CUPO_MAXIMO_DEFAULT - 1):
                reserva = Reserva(**_datos(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA))
                reserva.full_clean()
                reserva.save()

            # Dos clientes distintos, los dos a punto de pagar ese ultimo lugar.
            # Sin digitos en el nombre: `validar_nombre_persona` los rechaza (ver
            # apps/bookings/validators.py).
            self.pendientes = []
            for nombre in ('Cliente Uno', 'Cliente Dos'):
                reserva = Reserva(**_datos(
                    self.empresa,
                    fecha=self.fecha,
                    nombre_cliente=nombre,
                    precio_total=Decimal('4500.00'),
                    forma_pago=Reserva.FormaPago.COMPLETO,
                ))
                reserva.full_clean()
                reserva.save()
                self.pendientes.append(reserva)
        # `con_empresa` abre `transaction.atomic()` -- al salir del `with` aqui, en
        # setUp, ese atomic hace COMMIT de verdad (TransactionTestCase no envuelve el
        # test en una transaccion exterior como TestCase si hace) -- las filas quedan
        # committeadas y visibles para las conexiones nuevas que abriran los hilos.
        # Sin este `with` explicito, la carrera seria invisible cross-conexion, justo
        # la visibilidad que TransactionTestCase existe para dar.

    def _pagar_en_paralelo(self):
        """Aplica los dos pagos a la vez, cada uno en su propio hilo y conexion.

        Devuelve la lista de resultados de aplicar_pago_exitoso.
        """
        import threading

        from apps.payments.services import aplicar_pago_exitoso

        empresa_id = self.empresa.pk  # capturado ANTES de lanzar el hilo: el objeto
        # `Empresa` resuelto en la conexion principal no debe cruzar al hilo, cada
        # hilo debe resolver el suyo en su propia conexion (misma regla que un
        # callback on_commit).
        resultados = [None, None]
        errores = [None, None]
        # Las dos peticiones deben entrar a la vez o no hay carrera que probar.
        arrancar = threading.Barrier(2)

        def pagar(indice):
            try:
                arrancar.wait(timeout=10)
                empresa_del_hilo = Empresa.objects.get(pk=empresa_id)
                with scope.con_empresa(empresa_del_hilo):
                    resultados[indice] = aplicar_pago_exitoso(_intent_falso(self.pendientes[indice]), empresa_del_hilo)
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

    @mock.patch.object(StripeClient, 'refunds')
    def test_dos_pagos_simultaneos_no_sobrevenden_el_ultimo_lugar(self, refund):
        self._pagar_en_paralelo()

        with scope.con_empresa(self.empresa):
            pagadas = Reserva.objects.filter(
                fecha=self.fecha, empresa=self.empresa, estado__in=ESTADOS_QUE_OCUPAN_CUPO
            ).count()

        self.assertEqual(
            pagadas, CUPO_MAXIMO_DEFAULT,
            f'Sobreventa: {pagadas} reservas ocupan cupo y el maximo del dia es '
            f'{CUPO_MAXIMO_DEFAULT}. El lock por fecha no serializo la validacion.',
        )

    @mock.patch.object(StripeClient, 'refunds')
    def test_al_que_se_quedo_sin_lugar_se_le_devuelve_el_dinero(self, refund):
        """No basta con no sobrevender: el segundo ya pago y hay que reembolsarle
        de inmediato, dejando la reserva cancelada con el motivo real para que la
        vendedora lo vea en su panel."""
        self._pagar_en_paralelo()

        with scope.con_empresa(self.empresa):
            estados = sorted(
                Reserva.objects.filter(pk__in=[r.pk for r in self.pendientes])
                .values_list('estado', flat=True)
            )

            self.assertEqual(estados, sorted([Reserva.Estado.PAGADA, Reserva.Estado.CANCELADA]))
            self.assertEqual(refund.create.call_count, 1)

            perdedora = Reserva.objects.get(
                pk__in=[r.pk for r in self.pendientes], estado=Reserva.Estado.CANCELADA
            )
            self.assertTrue(perdedora.reembolsada)
            self.assertIn('cupo', perdedora.motivo_cancelacion.lower())


@SOLO_POSTGRES
class LockDelDiaTests(TransactionTestCase):
    """El lock es por fecha, no global: dos dias distintos no deben estorbarse."""

    def setUp(self):
        # Sin flota no cabe nadie y los dos pagos salen con `sin_cupo` antes de
        # llegar al lock, que es lo que esta clase dice probar. `TransactionTestCase`
        # trunca las tablas entre casos, asi que la flota de la otra clase no sirve.
        self.empresa = _crear_empresa_de_prueba()
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)

    @mock.patch.object(StripeClient, 'refunds')
    def test_dias_distintos_no_se_bloquean_entre_si(self, refund):
        import threading

        from apps.payments.services import APLICADO, aplicar_pago_exitoso

        empresa_id = self.empresa.pk
        with scope.con_empresa(self.empresa):
            reservas = []
            for i in range(2):
                reserva = Reserva(**_datos(
                    self.empresa,
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
                empresa_del_hilo = Empresa.objects.get(pk=empresa_id)
                with scope.con_empresa(empresa_del_hilo):
                    resultados[indice] = aplicar_pago_exitoso(_intent_falso(reservas[indice]), empresa_del_hilo)
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=pagar, args=(i,)) for i in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=30)

        self.assertEqual(resultados, [APLICADO, APLICADO])
        self.assertEqual(refund.create.call_count, 0)


@SOLO_POSTGRES
class SobreventaHospedajeConcurrenteTests(TransactionTestCase):
    """Dos clientes intentan pagar la última habitación en paralelo.
    Uno queda PAGADA con ReservaOcupacion, el otro CANCELADA y reembolsado."""

    def setUp(self):
        self.empresa = _crear_empresa_de_prueba()
        with scope.con_empresa(self.empresa):
            self.servicio = Servicio.objects.create(
                empresa=self.empresa,
                nombre='Cabaña frente al mar',
                slug='cabana-mar',
                tipo_servicio='hospedaje',
                estrategia_cupo='por_noche',
                precio_base=Decimal('2000.00'),
                activo=True,
            )
            self.recurso = Recurso.objects.create(
                empresa=self.empresa,
                servicio=self.servicio,
                nombre='Cabaña 1',
                capacidad_maxima=2,
                activo=True,
            )
            self.fecha = date.today() + timedelta(days=10)
            self.fecha_salida = date.today() + timedelta(days=12)

            self.pendientes = []
            for nombre in ('Cliente Hospedaje Uno', 'Cliente Hospedaje Dos'):
                reserva = Reserva(**_datos(
                    self.empresa,
                    servicio=self.servicio,
                    fecha=self.fecha,
                    fecha_salida=self.fecha_salida,
                    numero_personas=2,
                    nombre_cliente=nombre,
                    precio_total=Decimal('4000.00'),
                    forma_pago=Reserva.FormaPago.COMPLETO,
                ))
                reserva.full_clean()
                reserva.save()
                self.pendientes.append(reserva)

    def _pagar_en_paralelo(self):
        import threading
        from apps.payments.services import aplicar_pago_exitoso

        empresa_id = self.empresa.pk
        resultados = [None, None]
        errores = [None, None]
        arrancar = threading.Barrier(2)

        def pagar(indice):
            try:
                arrancar.wait(timeout=10)
                empresa_del_hilo = Empresa.objects.get(pk=empresa_id)
                with scope.con_empresa(empresa_del_hilo):
                    resultados[indice] = aplicar_pago_exitoso(_intent_falso(self.pendientes[indice]), empresa_del_hilo)
            except Exception as exc:  # noqa: BLE001
                errores[indice] = exc
            finally:
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

    @mock.patch.object(StripeClient, 'refunds')
    def test_dos_pagos_simultaneos_no_sobrevenden_habitacion(self, refund):
        self._pagar_en_paralelo()

        with scope.con_empresa(self.empresa):
            estados = sorted(
                Reserva.objects.filter(pk__in=[r.pk for r in self.pendientes])
                .values_list('estado', flat=True)
            )
            self.assertEqual(estados, sorted([Reserva.Estado.PAGADA, Reserva.Estado.CANCELADA]))

            # Exactamente una ocupación creada
            self.assertEqual(
                ReservaOcupacion.objects.filter(reserva__in=self.pendientes, ocupa_cupo=True).count(),
                1,
            )

            # Reembolso llamado 1 sola vez
            self.assertEqual(refund.create.call_count, 1)

            perdedora = Reserva.objects.get(
                pk__in=[r.pk for r in self.pendientes], estado=Reserva.Estado.CANCELADA
            )
            self.assertTrue(perdedora.reembolsada)
            self.assertIn('habitación', perdedora.motivo_cancelacion.lower())

