"""Pruebas unitarias para la lógica pura de precio de paquetes (Pieza 5)."""

from decimal import Decimal
from django.test import TestCase
from apps.testing import OperadorTestCase

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.payments.pricing import calcular_precio_paquete, precio_paquete
from apps.tenancy.models import Empresa, Sede


class PricingPaquetePureTests(TestCase):
    def test_precio_paquete_sin_ajustes(self):
        self.assertEqual(precio_paquete(Decimal('5000.00'), []), Decimal('5000.00'))
        self.assertEqual(precio_paquete(Decimal('5000.00'), None), Decimal('5000.00'))

    def test_precio_paquete_con_un_ajuste(self):
        resultado = precio_paquete(Decimal('5000.00'), [Decimal('1200.00')])
        self.assertEqual(resultado, Decimal('3800.00'))

    def test_precio_paquete_con_multiples_ajustes(self):
        resultado = precio_paquete(
            Decimal('10000.00'),
            [Decimal('1500.00'), Decimal('2000.00'), Decimal('500.50')]
        )
        self.assertEqual(resultado, Decimal('5999.50'))

    def test_precio_paquete_piso_cero(self):
        resultado = precio_paquete(Decimal('1000.00'), [Decimal('800.00'), Decimal('500.00')])
        self.assertEqual(resultado, Decimal('0.00'))

    def test_precio_paquete_precio_ancla_none(self):
        self.assertIsNone(precio_paquete(None, [Decimal('500.00')]))


class CalcularPrecioPaqueteIntegrationTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Pesca La Paz Test Pricing', slug='pesca-pricing-test'
        )

        self.servicio_pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca-srv', tipo_servicio='pesca',
            precio_base=Decimal('5000.00'), precio_base_usd=Decimal('280.00')
        )
        self.servicio_snack = Servicio.objects.create(
            empresa=self.empresa, nombre='Catering', slug='catering-srv', tipo_servicio='otro',
            precio_base=Decimal('1000.00'), precio_base_usd=Decimal('60.00')
        )
        self.servicio_foto = Servicio.objects.create(
            empresa=self.empresa, nombre='Fotos', slug='fotos-srv', tipo_servicio='otro',
            precio_base=Decimal('800.00'), precio_base_usd=Decimal('50.00')
        )

        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Experiencia VIP',
            slug='experiencia-vip',
            precio_ancla=Decimal('6500.00'),
            precio_ancla_usd=Decimal('380.00'),
        )

        # Servicio pesca: NO removible (núcleo del paquete)
        self.ps_pesca = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_pesca, orden=1, removible=False,
            ajuste_precio=Decimal('0.00'), ajuste_precio_usd=Decimal('0.00')
        )
        # Snack: removible con ajuste
        self.ps_snack = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_snack, orden=2, removible=True,
            ajuste_precio=Decimal('800.00'), ajuste_precio_usd=Decimal('50.00')
        )
        # Fotos: removible con ajuste
        self.ps_foto = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_foto, orden=3, removible=True,
            ajuste_precio=Decimal('600.00'), ajuste_precio_usd=Decimal('35.00')
        )

    def test_calcular_precio_sin_remover_nada(self):
        precio_mxn = calcular_precio_paquete(self.paquete, [], moneda='MXN')
        self.assertEqual(precio_mxn, Decimal('6500.00'))

        precio_usd = calcular_precio_paquete(self.paquete, None, moneda='USD')
        self.assertEqual(precio_usd, Decimal('380.00'))

    def test_calcular_precio_removiendo_un_servicio(self):
        # Remueve solo fotos (-$600 MXN / -$35 USD)
        precio_mxn = calcular_precio_paquete(
            self.paquete, [self.servicio_foto.pk], moneda='MXN'
        )
        self.assertEqual(precio_mxn, Decimal('5900.00'))

        precio_usd = calcular_precio_paquete(
            self.paquete, [self.servicio_foto.pk], moneda='USD'
        )
        self.assertEqual(precio_usd, Decimal('345.00'))

    def test_calcular_precio_removiendo_multiples_servicios(self):
        # Remueve snack y fotos (-$1400 MXN / -$85 USD)
        precio_mxn = calcular_precio_paquete(
            self.paquete, [self.servicio_snack.pk, self.servicio_foto.pk], moneda='MXN'
        )
        self.assertEqual(precio_mxn, Decimal('5100.00'))

        precio_usd = calcular_precio_paquete(
            self.paquete, [self.servicio_snack.pk, self.servicio_foto.pk], moneda='USD'
        )
        self.assertEqual(precio_usd, Decimal('295.00'))

    def test_servicio_no_removible_no_aplica_descuento(self):
        # Intentar remover pesca (removible=False) no descuenta nada
        precio = calcular_precio_paquete(
            self.paquete, [self.servicio_pesca.pk], moneda='MXN'
        )
        self.assertEqual(precio, Decimal('6500.00'))

    def test_paquete_sin_precio_en_moneda_retorna_none(self):
        paquete_solo_mxn = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Solo Pesos',
            slug='solo-pesos',
            precio_ancla=Decimal('4000.00'),
            precio_ancla_usd=None,
        )
        self.assertIsNone(calcular_precio_paquete(paquete_solo_mxn, [], moneda='USD'))
