"""Pruebas unitarias para la lógica pura de precio de paquetes (Pieza 5)."""

from decimal import Decimal
from django.test import TestCase
from apps.testing import OperadorTestCase

from apps.fleet.models import Paquete, PaqueteServicio, Personalizacion, Servicio, ServicioPersonalizacion
from apps.payments.pricing import calcular_precio_paquete, precio_paquete, precio_paquete_total
from apps.tenancy.models import Empresa, Sede


class PricingPaquetePureTests(TestCase):
    def test_precio_paquete_identidad_y_quantize(self):
        self.assertEqual(precio_paquete(Decimal('5000.00')), Decimal('5000.00'))
        self.assertEqual(precio_paquete('5000.5'), Decimal('5000.50'))

    def test_precio_paquete_piso_cero(self):
        self.assertEqual(precio_paquete(Decimal('-10.00')), Decimal('0.00'))

    def test_precio_paquete_none(self):
        self.assertIsNone(precio_paquete(None))

    def test_precio_paquete_firma_un_solo_argumento(self):
        with self.assertRaises(TypeError):
            precio_paquete(Decimal('5000.00'), [Decimal('500.00')])


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

        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Experiencia VIP',
            slug='experiencia-vip',
            precio_ancla=Decimal('6500.00'),
            precio_ancla_usd=Decimal('380.00'),
        )

        self.ps_pesca = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_pesca, orden=1,
        )
        self.ps_snack = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_snack, orden=2,
        )

    def test_calcular_precio_fijo_mxn_y_usd(self):
        precio_mxn = calcular_precio_paquete(self.paquete, moneda='MXN')
        self.assertEqual(precio_mxn, Decimal('6500.00'))

        precio_usd = calcular_precio_paquete(self.paquete, moneda='USD')
        self.assertEqual(precio_usd, Decimal('380.00'))

    def test_paquete_sin_precio_en_moneda_retorna_none(self):
        paquete_solo_mxn = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Solo Pesos',
            slug='solo-pesos',
            precio_ancla=Decimal('4000.00'),
            precio_ancla_usd=None,
        )
        self.assertIsNone(calcular_precio_paquete(paquete_solo_mxn, moneda='USD'))


class PrecioPaqueteTotalTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Paquetes', slug='empresa-paquetes'
        )

        self.servicio_pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca Fondo', slug='pesca-fondo', tipo_servicio='pesca',
            precio_base=Decimal('5000.00'), precio_base_usd=Decimal('280.00')
        )
        self.servicio_snack = Servicio.objects.create(
            empresa=self.empresa, nombre='Snack Panga', slug='snack-panga', tipo_servicio='otro',
            precio_base=Decimal('1000.00'), precio_base_usd=Decimal('60.00')
        )

        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Pack Pesca y Snack',
            slug='pack-pesca-snack',
            precio_ancla=Decimal('6500.00'),
            precio_ancla_usd=Decimal('380.00'),
        )

        self.ps_pesca = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_pesca, orden=1,
        )
        self.ps_snack = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_snack, orden=2,
        )

        # Personalizaciones para pesca:
        self.pers_licencia = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Licencia Pesca', cobrar_por_persona=True
        )
        self.sp_licencia = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_pesca, personalizacion=self.pers_licencia,
            precio=Decimal('250.00'), precio_usd=Decimal('15.00'),
            obligatorio=True, preseleccionado=False, activo=True
        )

        self.pers_carnada = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Carnada Viva Premium', cobrar_por_persona=False
        )
        self.sp_carnada = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_pesca, personalizacion=self.pers_carnada,
            precio=Decimal('300.00'), precio_usd=Decimal('20.00'),
            obligatorio=False, preseleccionado=False, activo=True
        )

        # Personalizaciones para snack:
        self.pers_bebidas = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Pack Cervezas', cobrar_por_persona=False
        )
        self.sp_bebidas = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_snack, personalizacion=self.pers_bebidas,
            precio=Decimal('100.00'), precio_usd=Decimal('5.00'),
            obligatorio=False, preseleccionado=True, activo=True
        )

        self.pers_album = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Álbum Foto', cobrar_por_persona=True
        )
        self.sp_album = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_snack, personalizacion=self.pers_album,
            precio=Decimal('200.00'), precio_usd=Decimal('12.00'),
            obligatorio=False, preseleccionado=False, activo=True
        )

    def test_sin_extras_suma_ancla_mas_obligatorias_y_preseleccionadas(self):
        # personas=2
        # ancla = 6500 MXN
        # obligatoria: licencia $250 * 2 personas = $500
        # preseleccionada: bebidas $100 * 1 = $100
        # total esperado = 6500 + 500 + 100 = 7100 MXN
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[],
            personas=2,
            moneda='MXN'
        )
        self.assertEqual(total, Decimal('7100.00'))

        # En USD: ancla=380, licencia=15*2=30, bebidas=5*1=5 -> 415 USD
        total_usd = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[],
            personas=2,
            moneda='USD'
        )
        self.assertEqual(total_usd, Decimal('415.00'))

    def test_personalizacion_opcional_marcada_suma_su_precio(self):
        # personas=2
        # extras: carnada (plana $300) y álbum ($200 * 2 personas = $400)
        # base: 7100 MXN (ancla + obligatoria + preseleccionada)
        # total esperado: 7100 + 300 + 400 = 7800 MXN
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[
                (self.sp_carnada.pk, 1),
                (self.sp_album.pk, 1),
            ],
            personas=2,
            moneda='MXN'
        )
        self.assertEqual(total, Decimal('7800.00'))

    def test_paquete_sin_precio_ancla_usd_moneda_usd_retorna_none(self):
        paquete_solo_mxn = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Solo Pesos 2',
            slug='solo-pesos-2',
            precio_ancla=Decimal('4000.00'),
            precio_ancla_usd=None,
        )
        self.assertIsNone(precio_paquete_total(paquete_solo_mxn, moneda='USD'))
