from datetime import date, timedelta
from decimal import Decimal

from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase

from apps.payments.pricing import PERSONAS_INCLUIDAS

from .models import (
    Embarcacion,
    EmbarcacionNoDisponible,
    Tarifa,
    capacidades_disponibles,
    capacidades_por_fecha,
)


class TarifaTests(TestCase):
    def test_es_singleton(self):
        Tarifa.objects.create(precio=Decimal('4500.00'))
        Tarifa.objects.create(precio=Decimal('5000.00'))
        self.assertEqual(Tarifa.objects.count(), 1)
        self.assertEqual(Tarifa.actual().precio, Decimal('5000.00'))

    def test_precio_por_moneda(self):
        tarifa = Tarifa.objects.create(precio=Decimal('4500.00'), precio_usd=Decimal('260.00'))
        self.assertEqual(tarifa.precio_en('MXN'), Decimal('4500.00'))
        self.assertEqual(tarifa.precio_en('USD'), Decimal('260.00'))

    def test_sin_precio_en_dolares_devuelve_none(self):
        tarifa = Tarifa.objects.create(precio=Decimal('4500.00'))
        self.assertIsNone(tarifa.precio_en('USD'))


class TarifaApiTests(TestCase):
    def test_sin_tarifa_responde_503(self):
        self.assertEqual(self.client.get('/api/tarifa/').status_code, 503)

    def test_devuelve_todas_las_cifras_del_checkout(self):
        Tarifa.objects.create(
            precio=Decimal('4500.00'), precio_usd=Decimal('260.00'),
            precio_persona_extra=Decimal('500.00'), precio_lunch=Decimal('300.00'),
        )
        body = self.client.get('/api/tarifa/').json()
        self.assertEqual(body['precio'], '4500.00')
        self.assertEqual(body['precio_usd'], '260.00')
        self.assertEqual(body['precio_persona_extra'], '500.00')
        self.assertEqual(body['precio_lunch'], '300.00')
        self.assertEqual(body['personas_incluidas'], PERSONAS_INCLUIDAS)

    def test_no_publica_precio_de_lo_que_se_cotiza(self):
        # Bebidas y transporte no tienen precio en linea, los cotiza el agente.
        Tarifa.objects.create(precio=Decimal('4500.00'))
        body = self.client.get('/api/tarifa/').json()
        self.assertNotIn('amenidades', body)


class EmbarcacionTests(TestCase):
    def test_nace_activa(self):
        panga = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5
        )
        self.assertTrue(panga.activa)

    def test_la_etiqueta_de_clase_no_carga_la_capacidad(self):
        """La capacidad vive en `capacidad_maxima` y en ningun otro lado.

        La etiqueta decia "Grande (max. 6 personas)" y era falsa: ninguna panga
        lleva mas de 5. Un numero escrito en dos lugares es un numero que puede
        discrepar."""
        for clase in Embarcacion.Clase:
            self.assertNotIn('personas', clase.label)

    def test_str_muestra_la_capacidad(self):
        """El selector de la agenda ensena la capacidad donde se necesita."""
        panga = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5
        )
        self.assertEqual(str(panga), 'Lupita (Grande, max. 5)')


class CapacidadesDisponiblesTests(TestCase):
    def setUp(self):
        self.fecha = date.today() + timedelta(days=10)
        self.chica = Embarcacion.objects.create(
            nombre='Chuy', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3
        )
        self.grande = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5
        )

    def test_devuelve_las_capacidades_de_mayor_a_menor(self):
        self.assertEqual(capacidades_disponibles(self.fecha), [5, 3])

    def test_excluye_las_inactivas(self):
        self.grande.activa = False
        self.grande.save()
        self.assertEqual(capacidades_disponibles(self.fecha), [3])

    def test_excluye_la_marcada_no_disponible_solo_ese_dia(self):
        """Una panga en mantenimiento el jueves vuelve a contar el viernes."""
        EmbarcacionNoDisponible.objects.create(
            fecha=self.fecha, embarcacion=self.grande, motivo='Mantenimiento'
        )
        self.assertEqual(capacidades_disponibles(self.fecha), [3])
        self.assertEqual(capacidades_disponibles(self.fecha + timedelta(days=1)), [5, 3])

    def test_el_rango_no_hace_una_consulta_por_dia(self):
        """El costo no puede crecer con la ventana: de aqui cuelga la busqueda de
        los proximos 90 dias del checkout."""
        with self.assertNumQueries(2):
            capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=89))

    def test_el_rango_trae_una_entrada_por_dia(self):
        rango = capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=2))
        self.assertEqual(len(rango), 3)
        self.assertEqual(rango[self.fecha], [5, 3])


class EmbarcacionNoDisponibleUnicidadTests(TransactionTestCase):
    """Aparte y con TransactionTestCase: un IntegrityError deja inutilizable la
    transaccion que envuelve a un TestCase normal."""

    def test_una_panga_no_se_puede_marcar_dos_veces_el_mismo_dia(self):
        fecha = date.today() + timedelta(days=10)
        grande = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5
        )
        EmbarcacionNoDisponible.objects.create(fecha=fecha, embarcacion=grande)
        with self.assertRaises(IntegrityError):
            EmbarcacionNoDisponible.objects.create(fecha=fecha, embarcacion=grande)
