"""Pruebas unitarias para la lógica pura de precio de paquetes (Pieza 5)."""

from decimal import Decimal
from django.test import TestCase
from apps.testing import OperadorTestCase

from apps.fleet.models import Paquete, PaqueteServicio, Personalizacion, Servicio, ServicioPersonalizacion
from apps.payments.pricing import calcular_precio_paquete, precio_paquete, precio_paquete_total
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
            empresa=self.empresa, nombre='Snacks', slug='snacks', tipo_servicio='otro',
            precio_base=Decimal('1000.00'), precio_base_usd=Decimal('60.00')
        )
        self.servicio_foto = Servicio.objects.create(
            empresa=self.empresa, nombre='Fotografía', slug='fotografia', tipo_servicio='otro',
            precio_base=Decimal('800.00'), precio_base_usd=Decimal('50.00')
        )

        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Completo',
            slug='paquete-completo',
            precio_ancla=Decimal('6500.00'),
            precio_ancla_usd=Decimal('380.00'),
        )

        self.ps_pesca = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_pesca, orden=1, removible=False,
            ajuste_precio=Decimal('0.00'), ajuste_precio_usd=Decimal('0.00')
        )
        self.ps_snack = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_snack, orden=2, removible=True,
            ajuste_precio=Decimal('800.00'), ajuste_precio_usd=Decimal('50.00')
        )
        self.ps_foto = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_foto, orden=3, removible=True,
            ajuste_precio=Decimal('600.00'), ajuste_precio_usd=Decimal('35.00')
        )

        # Personalizaciones de catálogo
        self.p_licencia = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Licencia Pesca', cobrar_por_persona=True
        )
        self.p_bebidas = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Bebidas Bienvenida', cobrar_por_persona=False
        )
        self.p_carnada = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Carnada Premium', cobrar_por_persona=False
        )
        self.p_album = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Álbum Impreso', cobrar_por_persona=True
        )

        # Asociaciones a servicios:
        # 1. Pesca: Licencia (obligatoria, por persona: $250 MXN / $15 USD)
        self.sp_licencia = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_pesca, personalizacion=self.p_licencia,
            precio=Decimal('250.00'), precio_usd=Decimal('15.00'),
            obligatorio=True, preseleccionado=False, activo=True
        )
        # 2. Pesca: Carnada (opcional, plana: $300 MXN / $20 USD)
        self.sp_carnada = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_pesca, personalizacion=self.p_carnada,
            precio=Decimal('300.00'), precio_usd=Decimal('20.00'),
            obligatorio=False, preseleccionado=False, activo=True
        )
        # 3. Snack: Bebidas (preseleccionada, plana: $100 MXN / $5 USD)
        self.sp_bebidas = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_snack, personalizacion=self.p_bebidas,
            precio=Decimal('100.00'), precio_usd=Decimal('5.00'),
            obligatorio=False, preseleccionado=True, activo=True
        )
        # 4. Foto: Álbum (opcional, por persona: $200 MXN / $10 USD)
        self.sp_album = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_foto, personalizacion=self.p_album,
            precio=Decimal('200.00'), precio_usd=Decimal('10.00'),
            obligatorio=False, preseleccionado=False, activo=True
        )

    def test_sin_removidos_ni_extras_suma_ancla_mas_obligatorias_y_preseleccionadas(self):
        # personas=2
        # ancla = 6500 MXN
        # obligatoria: licencia $250 * 2 personas = $500
        # preseleccionada: bebidas $100 * 1 = $100
        # total esperado = 6500 + 500 + 100 = 7100 MXN
        total = precio_paquete_total(
            self.paquete,
            servicios_removidos_ids=set(),
            personalizaciones_extra=[],
            personas=2,
            moneda='MXN'
        )
        self.assertEqual(total, Decimal('7100.00'))

        # En USD: ancla=380, licencia=15*2=30, bebidas=5*1=5 -> 415 USD
        total_usd = precio_paquete_total(
            self.paquete,
            servicios_removidos_ids=set(),
            personalizaciones_extra=[],
            personas=2,
            moneda='USD'
        )
        self.assertEqual(total_usd, Decimal('415.00'))

    def test_un_servicio_removido_resta_ajuste_y_deja_de_contar_sus_personalizaciones(self):
        # Remover servicio_snack (ajuste 800 MXN).
        # snack tiene sp_bebidas ($100 preseleccionada), que ya NO debe sumarse.
        # personas=2: ancla 6500 - 800 (ajuste snack) + 500 (licencia pesca) = 6200 MXN
        total = precio_paquete_total(
            self.paquete,
            servicios_removidos_ids={self.servicio_snack.pk},
            personalizaciones_extra=[],
            personas=2,
            moneda='MXN'
        )
        self.assertEqual(total, Decimal('6200.00'))

    def test_personalizacion_opcional_marcada_suma_su_precio(self):
        # personas=2
        # extras: carnada (plana $300) y álbum ($200 * 2 personas = $400)
        # base: 7100 MXN (ancla + obligatoria + preseleccionada)
        # total esperado: 7100 + 300 + 400 = 7800 MXN
        total = precio_paquete_total(
            self.paquete,
            servicios_removidos_ids=set(),
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

    def test_piso_cero_ajustes_que_superan_el_ancla(self):
        # Paquete con ancla pequeña
        paquete_barato = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Barato',
            slug='barato',
            precio_ancla=Decimal('500.00'),
            precio_ancla_usd=Decimal('30.00'),
        )
        # Servicio con ajuste grande que supera el ancla
        PaqueteServicio.objects.create(
            paquete=paquete_barato, servicio=self.servicio_snack, orden=1, removible=True,
            ajuste_precio=Decimal('800.00'), ajuste_precio_usd=Decimal('50.00')
        )
        total = precio_paquete_total(
            paquete_barato,
            servicios_removidos_ids={self.servicio_snack.pk},
            personalizaciones_extra=[],
            personas=1,
            moneda='MXN'
        )
        self.assertEqual(total, Decimal('0.00'))
