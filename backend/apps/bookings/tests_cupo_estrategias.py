from datetime import date, time, timedelta
from decimal import Decimal
from unittest import TestCase

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.bookings.cupo import (
    BajoDemanda,
    DemandaCupo,
    ModoOcupacion,
    PorNoche,
    PorRecursoDia,
    ResultadoDisponibilidad,
    obtener_estrategia,
)
from apps.bookings.cupo.nucleo import MOTIVO_LLENO, MOTIVO_SIN_LUGAR, MOTIVO_SIN_PANGA
from apps.bookings.models import Reserva
from apps.fleet.models import Servicio
from apps.testing import EmpresaTestCase, crear_flota


class CupoEstrategiasTests(TestCase):
    """Pruebas de las clases y métodos de EstrategiaCupo y PorRecursoDia."""

    def setUp(self):
        self.estrategia_exclusiva = PorRecursoDia(modo=ModoOcupacion.EXCLUSIVO)
        self.estrategia_compartida = PorRecursoDia(modo=ModoOcupacion.COMPARTIDO)
        self.fecha = date(2026, 9, 15)

    def test_por_recurso_dia_evaluar_exitoso(self):
        demanda = DemandaCupo(fecha=self.fecha, personas=3)
        res = self.estrategia_exclusiva.evaluar(
            demanda=demanda,
            grupos=[4],
            capacidades=[5, 4],
            tope=2,
        )
        self.assertTrue(res.disponible)
        self.assertIsNone(res.motivo)

    def test_por_recurso_dia_evaluar_sin_panga(self):
        demanda = DemandaCupo(fecha=self.fecha, personas=5)
        # Solo queda una de 3 disponible
        res = self.estrategia_exclusiva.evaluar(
            demanda=demanda,
            grupos=[5],
            capacidades=[5, 3],
            tope=2,
        )
        self.assertFalse(res.disponible)
        self.assertEqual(res.motivo, MOTIVO_SIN_PANGA)

    def test_por_recurso_dia_validar_lanza_validation_error(self):
        # Caso lleno
        demanda_lleno = DemandaCupo(fecha=self.fecha, personas=2)
        with self.assertRaises(ValidationError) as ctx:
            self.estrategia_exclusiva.validar(
                demanda=demanda_lleno,
                grupos=[3, 3],
                capacidades=[5, 5],
                tope=2,
            )
        self.assertIn('se alcanzo el maximo de viajes del dia', str(ctx.exception))

        # Caso sin panga
        demanda_sin_panga = DemandaCupo(fecha=self.fecha, personas=5)
        with self.assertRaises(ValidationError) as ctx:
            self.estrategia_exclusiva.validar(
                demanda=demanda_sin_panga,
                grupos=[4],
                capacidades=[5, 3],
                tope=2,
            )
        self.assertIn('No queda panga para un grupo de 5 personas', str(ctx.exception))

    def test_por_recurso_dia_modo_compartido(self):
        demanda = DemandaCupo(fecha=self.fecha, personas=4, modo=ModoOcupacion.COMPARTIDO)
        # Capacidad total de la lancha compartida = 10, ya hay 8 ocupados
        res = self.estrategia_compartida.evaluar(
            demanda=demanda,
            grupos=[4, 4],
            capacidades=[10],
            tope=5,
        )
        self.assertFalse(res.disponible)
        self.assertEqual(res.motivo, MOTIVO_SIN_LUGAR)

        # Validación lanza el error correspondiente
        with self.assertRaises(ValidationError) as ctx:
            self.estrategia_compartida.validar(
                demanda=demanda,
                grupos=[4, 4],
                capacidades=[10],
                tope=5,
            )
        self.assertIn('No hay espacio disponible para 4 personas', str(ctx.exception))

    def test_por_recurso_dia_evaluar_rango(self):
        f1 = date(2026, 9, 20)
        f2 = date(2026, 9, 21)

        grupos = {f1: [], f2: [5, 5]}
        capacidades = {f1: [5, 3], f2: [5, 3]}
        topes = {f1: 2, f2: 2}

        res_rango = self.estrategia_exclusiva.evaluar_rango(
            fechas=[f1, f2],
            grupos_por_fecha=grupos,
            capacidades_por_fecha=capacidades,
            topes_por_fecha=topes,
            personas=3,
        )

        self.assertTrue(res_rango[f1].disponible)
        self.assertFalse(res_rango[f2].disponible)
        self.assertEqual(res_rango[f2].motivo, MOTIVO_LLENO)


class RegistroEstrategiasTests(SimpleTestCase):
    def test_obtener_estrategia(self):
        self.assertIsInstance(obtener_estrategia('por_recurso_dia'), PorRecursoDia)
        self.assertIsInstance(obtener_estrategia('por_noche'), PorNoche)
        self.assertIsInstance(obtener_estrategia('bajo_demanda'), BajoDemanda)

    def test_obtener_estrategia_inexistente_warning(self):
        with self.assertLogs('apps.bookings.cupo.registro', level='WARNING') as cm:
            est = obtener_estrategia('inexistente')
            self.assertIsInstance(est, PorRecursoDia)
        self.assertTrue(any('estrategia_cupo desconocida' in record.message for record in cm.records))


class ReservaCleanEstrategiaCupoTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.servicio_pesca = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Pesca en Panga',
            slug='pesca-en-panga',
            tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia',
            precio_base=Decimal('5000.00'),
        )

    def test_reserva_de_servicio_pesca_valida_cupo(self):
        reserva = Reserva(
            empresa=self.empresa,
            servicio=self.servicio_pesca,
            fecha=date.today() + timedelta(days=10),
            hora=time(7, 0),
            numero_personas=3,
            estado=Reserva.Estado.PAGADA,
            moneda='MXN',
            precio_total=Decimal('5000.00'),
            nombre_cliente='Juan Perez',
            correo_cliente='juan@example.com',
            telefono_cliente='1234567890',
            canal_origen=Reserva.CanalOrigen.WHATSAPP,
        )
        reserva.full_clean()

    def test_reserva_legacy_sin_servicio_sigue_validando(self):
        reserva = Reserva(
            empresa=self.empresa,
            servicio=None,
            fecha=date.today() + timedelta(days=10),
            hora=time(7, 0),
            numero_personas=3,
            estado=Reserva.Estado.PAGADA,
            moneda='MXN',
            precio_total=Decimal('5000.00'),
            nombre_cliente='Juan Perez',
            correo_cliente='juan@example.com',
            telefono_cliente='1234567890',
            canal_origen=Reserva.CanalOrigen.WHATSAPP,
        )
        with self.assertRaisesMessage(ValidationError, 'Selecciona un servicio o paquete'):
            reserva.full_clean()


