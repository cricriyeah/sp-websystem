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

from apps.fleet.models import Embarcacion, Paquete, PaqueteServicio, Recurso, Servicio
from apps.bookings.cupo import confirmacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import crear_flota, crear_servicio_pesca

from stripe import StripeClient

from .models import CUPO_MAXIMO_DEFAULT, ESTADOS_QUE_OCUPAN_CUPO, Reserva, ReservaOcupacion, ReservaSalida

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


@SOLO_POSTGRES
class SobreventaSalidasConcurrenteTests(TransactionTestCase):
    """Dos paquetes cruzan días de mar; una sola panga solo admite uno."""

    def setUp(self):
        self.empresa = _crear_empresa_de_prueba()
        with scope.con_empresa(self.empresa):
            Embarcacion.objects.create(
                empresa=self.empresa, nombre='Panga única', clase=Embarcacion.Clase.CHICA,
                capacidad_maxima=2,
            )
            pesca = Servicio.objects.create(
                empresa=self.empresa, nombre='Pesca de cuatro días', slug='pesca-cuatro-dias',
                tipo_servicio='pesca', estrategia_cupo='por_recurso_dia',
                precio_base=Decimal('4500.00'),
            )
            hotel = Servicio.objects.create(
                empresa=self.empresa, nombre='Hotel de la prueba', slug='hotel-concurrencia',
                tipo_servicio='hospedaje', estrategia_cupo='por_noche',
                estrategia_precio='por_noche', precio_base=Decimal('1000.00'),
            )
            # Dos habitaciones evitan que el hospedaje, en lugar de la panga,
            # decida cuál pago se cancela.
            for indice in (1, 2):
                Recurso.objects.create(
                    empresa=self.empresa, servicio=hotel,
                    nombre=f'Habitación {indice}', capacidad_maxima=2,
                )
            paquete = Paquete.objects.create(
                sede=self.empresa.sede, empresa_lider=self.empresa,
                nombre='Mar en cuatro días', slug='mar-concurrente',
                precio_ancla=Decimal('4500.00'),
            )
            PaqueteServicio.objects.create(
                paquete=paquete, servicio=pesca, orden=1, dia_estancia=2,
                salidas=4, personas_incluidas=2,
            )
            PaqueteServicio.objects.create(
                paquete=paquete, servicio=hotel, orden=2, noches=5,
                personas_incluidas=2,
            )
            self.pendientes = []
            self.fechas_de_mar = []
            for indice, nombre in enumerate(('Cliente Mar Uno', 'Cliente Mar Dos')):
                inicio = date.today() + timedelta(days=20 + 2 * indice)
                self.fechas_de_mar.append([inicio + timedelta(days=d) for d in (1, 2, 3, 4)])
                reserva = Reserva(**_datos(
                    self.empresa, paquete=paquete,
                    fecha=inicio + timedelta(days=1), inicio_paquete=inicio,
                    fecha_salida=inicio + timedelta(days=5),
                    nombre_cliente=nombre, precio_total=Decimal('4500.00'),
                    forma_pago=Reserva.FormaPago.COMPLETO,
                ))
                reserva.full_clean()
                reserva.save()
                self.pendientes.append(reserva)

    @mock.patch.object(StripeClient, 'refunds')
    def test_dos_pagos_con_salidas_solapadas_no_sobrevenden_la_panga(self, refund):
        import threading

        from apps.bookings.cupo import salidas
        from apps.payments.services import APLICADO, SIN_CUPO_REEMBOLSADO, aplicar_pago_exitoso

        empresa_id = self.empresa.pk
        arrancar = threading.Barrier(2)
        antes_del_primer_lock = threading.Barrier(2)
        paso_primer_lock = threading.local()
        validar_real = salidas.validar_cupo_salidas_bajo_candado
        resultados = [None, None]
        errores = [None, None]

        def validar_juntos(*args, **kwargs):
            if not getattr(paso_primer_lock, 'listo', False):
                paso_primer_lock.listo = True
                antes_del_primer_lock.wait(timeout=10)
            return validar_real(*args, **kwargs)

        def pagar(indice):
            try:
                arrancar.wait(timeout=10)
                empresa_del_hilo = Empresa.objects.get(pk=empresa_id)
                with scope.con_empresa(empresa_del_hilo):
                    resultados[indice] = aplicar_pago_exitoso(
                        _intent_falso(self.pendientes[indice]), empresa_del_hilo,
                    )
            except Exception as exc:  # noqa: BLE001 — se re-lanza en el hilo principal
                errores[indice] = exc
            finally:
                connections.close_all()

        with mock.patch.object(salidas, 'validar_cupo_salidas_bajo_candado', side_effect=validar_juntos):
            hilos = [threading.Thread(target=pagar, args=(i,)) for i in range(2)]
            for hilo in hilos:
                hilo.start()
            for hilo in hilos:
                hilo.join(timeout=30)

        self.assertFalse(any(hilo.is_alive() for hilo in hilos), 'Un pago quedó bloqueado.')
        for error in errores:
            if error is not None:
                raise error
        self.assertEqual(sorted(resultados), sorted([APLICADO, SIN_CUPO_REEMBOLSADO]))

        with scope.con_empresa(self.empresa):
            estados = list(
                Reserva.objects.filter(pk__in=[r.pk for r in self.pendientes])
                .values_list('estado', flat=True)
            )
            self.assertEqual(sorted(estados), sorted([Reserva.Estado.PAGADA, Reserva.Estado.CANCELADA]))
            ganadora = Reserva.objects.get(
                pk__in=[r.pk for r in self.pendientes], estado=Reserva.Estado.PAGADA,
            )
            perdedora = Reserva.objects.get(
                pk__in=[r.pk for r in self.pendientes], estado=Reserva.Estado.CANCELADA,
            )
            indice_ganador = next(
                i for i, pendiente in enumerate(self.pendientes) if pendiente.pk == ganadora.pk
            )
            self.assertEqual(
                list(ReservaSalida.objects.filter(reserva=ganadora).order_by('fecha')
                     .values_list('fecha', flat=True)),
                self.fechas_de_mar[indice_ganador],
            )
            self.assertFalse(ReservaSalida.objects.filter(reserva=perdedora).exists())
            self.assertTrue(perdedora.reembolsada)
            self.assertIn('cupo', perdedora.motivo_cancelacion.lower())
        self.assertEqual(refund.create.call_count, 1)

    @mock.patch.object(StripeClient, 'refunds')
    def test_paquete_de_un_dia_y_multidia_no_se_interbloquean(self, refund):
        import threading

        from apps.payments.services import APLICADO, SIN_CUPO_REEMBOLSADO, aplicar_pago_exitoso

        with scope.con_empresa(self.empresa):
            multidia = self.pendientes[0].paquete
            pesca = multidia.servicios_asociados.get(servicio__estrategia_cupo='por_recurso_dia').servicio
            hotel = multidia.servicios_asociados.get(servicio__estrategia_cupo='por_noche').servicio
            un_dia = Paquete.objects.create(
                sede=self.empresa.sede, empresa_lider=self.empresa,
                nombre='Hotel primero', slug='hotel-primero', precio_ancla=Decimal('4500.00'),
            )
            PaqueteServicio.objects.create(
                paquete=un_dia, servicio=hotel, orden=1, noches=5, personas_incluidas=2,
            )
            PaqueteServicio.objects.create(
                paquete=un_dia, servicio=pesca, orden=2, dia_estancia=2, personas_incluidas=2,
            )

        for intento in range(5):
            inicio = date.today() + timedelta(days=40 + 7 * intento)
            with scope.con_empresa(self.empresa):
                pendientes = []
                for paquete, nombre in ((un_dia, 'Cliente Un Día'), (multidia, 'Cliente Varios Días')):
                    reserva = Reserva(**_datos(
                        self.empresa, paquete=paquete, fecha=inicio + timedelta(days=1),
                        inicio_paquete=inicio, fecha_salida=inicio + timedelta(days=5),
                        nombre_cliente=nombre, precio_total=Decimal('4500.00'),
                        forma_pago=Reserva.FormaPago.COMPLETO,
                    ))
                    reserva.full_clean()
                    reserva.save()
                    pendientes.append(reserva)

            empezar = threading.Barrier(2)
            primer_lock = threading.Barrier(2)
            visto = threading.local()
            bloquear_real = confirmacion.bloquear_cupo
            resultados = [None, None]
            errores = [None, None]

            def bloquear_juntos(*args, **kwargs):
                if not getattr(visto, 'primero', False):
                    visto.primero = True
                    primer_lock.wait(timeout=10)
                return bloquear_real(*args, **kwargs)

            def pagar(indice):
                try:
                    empezar.wait(timeout=10)
                    empresa = Empresa.objects.get(pk=self.empresa.pk)
                    with scope.con_empresa(empresa):
                        resultados[indice] = aplicar_pago_exitoso(_intent_falso(pendientes[indice]), empresa)
                except Exception as exc:  # noqa: BLE001 — re-lanzar en el hilo principal
                    errores[indice] = exc
                finally:
                    connections.close_all()

            with mock.patch.object(confirmacion, 'bloquear_cupo', side_effect=bloquear_juntos):
                hilos = [threading.Thread(target=pagar, args=(i,)) for i in range(2)]
                for hilo in hilos:
                    hilo.start()
                for hilo in hilos:
                    hilo.join(timeout=30)
            self.assertFalse(any(hilo.is_alive() for hilo in hilos), f'Pago bloqueado en intento {intento + 1}.')
            for error in errores:
                if error is not None:
                    raise error
            self.assertEqual(sorted(resultados), sorted([APLICADO, SIN_CUPO_REEMBOLSADO]))
        self.assertEqual(refund.create.call_count, 5)

    def test_dos_altas_pagadas_del_admin_no_sobrevenden_salidas(self):
        import threading

        from django.core.exceptions import ValidationError

        paquete_id = self.pendientes[0].paquete_id
        inicio = date.today() + timedelta(days=90)
        ambas_validadas = threading.Barrier(2)
        resultados = [None, None]
        errores = [None, None]

        def crear(indice):
            try:
                empresa = Empresa.objects.get(pk=self.empresa.pk)
                with scope.con_empresa(empresa):
                    paquete = Paquete.objects.get(pk=paquete_id)
                    reserva = Reserva(**_datos(
                        empresa, paquete=paquete, fecha=inicio + timedelta(days=1),
                        inicio_paquete=inicio, fecha_salida=inicio + timedelta(days=5),
                        nombre_cliente=('Cliente Alta Uno', 'Cliente Alta Dos')[indice],
                        estado=Reserva.Estado.PAGADA,
                    ))
                    reserva.full_clean()
                    ambas_validadas.wait(timeout=10)
                    try:
                        reserva.save()
                    except ValidationError:
                        resultados[indice] = 'sin_cupo'
                    else:
                        resultados[indice] = 'pagada'
            except Exception as exc:  # noqa: BLE001 — re-lanzar en el hilo principal
                errores[indice] = exc
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=crear, args=(i,)) for i in range(2)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=30)
        self.assertFalse(any(hilo.is_alive() for hilo in hilos), 'Un alta quedó bloqueada.')
        for error in errores:
            if error is not None:
                raise error
        self.assertEqual(sorted(resultados), ['pagada', 'sin_cupo'])
        with scope.con_empresa(self.empresa):
            self.assertEqual(
                ReservaSalida.objects.filter(fecha=inicio + timedelta(days=2)).count(), 1,
            )


@SOLO_POSTGRES
class SobreventaEntreServiciosConcurrenteTests(TransactionTestCase):
    """Servicios distintos compiten por la misma flota de la empresa."""

    def setUp(self):
        self.empresa = _crear_empresa_de_prueba()
        self.fecha = date.today() + timedelta(days=20)
        with scope.con_empresa(self.empresa):
            Embarcacion.objects.create(
                empresa=self.empresa, nombre='Panga compartida',
                clase=Embarcacion.Clase.CHICA, capacidad_maxima=2,
            )
            servicios = [
                Servicio.objects.create(
                    empresa=self.empresa, nombre=nombre, slug=slug,
                    tipo_servicio=tipo, estrategia_cupo='por_recurso_dia',
                    precio_base=Decimal('4500.00'),
                )
                for nombre, slug, tipo in (
                    ('Pesca', 'pesca-concurrente', 'pesca'),
                    ('Avistamiento', 'avistamiento-concurrente', 'paseo'),
                )
            ]
            self.pendientes = []
            for nombre, servicio in zip(('Cliente Pesca', 'Cliente Avistamiento'), servicios):
                reserva = Reserva(**_datos(
                    self.empresa, servicio=servicio, fecha=self.fecha,
                    nombre_cliente=nombre, precio_total=Decimal('4500.00'),
                    forma_pago=Reserva.FormaPago.COMPLETO,
                ))
                reserva.full_clean()
                reserva.save()
                self.pendientes.append(reserva)

    @mock.patch.object(StripeClient, 'refunds')
    def test_dos_servicios_no_venden_la_misma_panga(self, refund):
        import threading

        from apps.bookings.cupo import confirmacion
        from apps.payments.services import APLICADO, SIN_CUPO_REEMBOLSADO, aplicar_pago_exitoso

        empresa_id = self.empresa.pk
        empezar = threading.Barrier(2)
        ambos_evaluaron = threading.Barrier(2)
        evaluar_real = confirmacion.evaluar_cupo
        resultados = [None, None]
        errores = [None, None]

        def evaluar_juntos(*args, **kwargs):
            resultado = evaluar_real(*args, **kwargs)
            try:
                # Con claves distintas ambos leen cupo libre antes de confirmar.
                # Con una clave compartida, el primero continúa tras el timeout
                # y el segundo encuentra la panga ocupada.
                ambos_evaluaron.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
            return resultado

        def pagar(indice):
            try:
                empezar.wait(timeout=10)
                empresa = Empresa.objects.get(pk=empresa_id)
                with scope.con_empresa(empresa):
                    resultados[indice] = aplicar_pago_exitoso(_intent_falso(self.pendientes[indice]), empresa)
            except Exception as exc:  # noqa: BLE001 — se re-lanza en el hilo principal
                errores[indice] = exc
            finally:
                connections.close_all()

        with mock.patch.object(confirmacion, 'evaluar_cupo', side_effect=evaluar_juntos):
            hilos = [threading.Thread(target=pagar, args=(i,)) for i in range(2)]
            for hilo in hilos:
                hilo.start()
            for hilo in hilos:
                hilo.join(timeout=30)

        self.assertFalse(any(hilo.is_alive() for hilo in hilos), 'Un pago quedó bloqueado.')
        for error in errores:
            if error is not None:
                raise error
        self.assertEqual(sorted(resultados), sorted([APLICADO, SIN_CUPO_REEMBOLSADO]))
        with scope.con_empresa(self.empresa):
            estados = sorted(
                Reserva.objects.filter(pk__in=[r.pk for r in self.pendientes])
                .values_list('estado', flat=True)
            )
        self.assertEqual(estados, sorted([Reserva.Estado.PAGADA, Reserva.Estado.CANCELADA]))
        self.assertEqual(refund.create.call_count, 1)

