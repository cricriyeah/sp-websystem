from decimal import Decimal

from django.test import TestCase

from apps.payments.pricing import PERSONAS_INCLUIDAS

from .models import Embarcacion, Tarifa


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
