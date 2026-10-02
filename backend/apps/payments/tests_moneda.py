"""Conversion de MXN a USD con el tipo de cambio de la sede (un solo precio en pesos)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from apps.payments.moneda import convertir
from apps.tenancy.models import Sede


class ConvertirTests(SimpleTestCase):
    def test_mxn_no_cambia(self):
        self.assertEqual(convertir(Decimal('4500.00'), 'MXN', Decimal('18')), Decimal('4500.00'))

    def test_moneda_en_minusculas(self):
        self.assertEqual(convertir(Decimal('4500.00'), 'mxn', Decimal('18')), Decimal('4500.00'))

    def test_usd_redondea_hacia_arriba_al_dolar(self):
        self.assertEqual(convertir(Decimal('500.00'), 'USD', Decimal('17')), Decimal('30.00'))  # 29.41

    def test_usd_exacto_no_sube(self):
        self.assertEqual(convertir(Decimal('540.00'), 'USD', Decimal('18')), Decimal('30.00'))

    def test_usd_un_centavo_arriba_sube_un_dolar(self):
        self.assertEqual(convertir(Decimal('540.01'), 'USD', Decimal('18')), Decimal('31.00'))

    def test_usd_cero_es_cero(self):
        self.assertEqual(convertir(Decimal('0.00'), 'USD', Decimal('18')), Decimal('0.00'))

    def test_none_devuelve_none(self):
        self.assertIsNone(convertir(None, 'USD', Decimal('18')))
        self.assertIsNone(convertir(None, 'MXN', None))

    def test_usd_sin_tipo_de_cambio_falla(self):
        with self.assertRaises(ValueError):
            convertir(Decimal('500.00'), 'USD', None)

    def test_tipo_de_cambio_no_positivo_falla(self):
        for malo in (Decimal('0'), Decimal('-1')):
            with self.assertRaises(ValueError):
                convertir(Decimal('500.00'), 'USD', malo)

    def test_mxn_ignora_el_tipo_de_cambio(self):
        self.assertEqual(convertir(Decimal('100.00'), 'MXN', None), Decimal('100.00'))

    def test_moneda_desconocida_falla(self):
        with self.assertRaises(ValueError):
            convertir(Decimal('100.00'), 'EUR', Decimal('18'))


class SedeTipoCambioTests(TestCase):
    def test_default_es_el_demo(self):
        sede = Sede.objects.create(nombre='Prueba cambio', slug='prueba-cambio')
        self.assertEqual(sede.tipo_cambio_usd, Decimal('18.0000'))

    def test_no_acepta_cero_ni_negativo(self):
        for malo in (Decimal('0'), Decimal('-5')):
            sede = Sede(nombre='Mala', slug='mala', tipo_cambio_usd=malo)
            with self.assertRaises(ValidationError) as ctx:
                sede.full_clean()
            self.assertIn('tipo_cambio_usd', ctx.exception.message_dict)
