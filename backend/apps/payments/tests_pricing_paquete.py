"""Pruebas unitarias para la lógica pura de precio de paquetes (Pieza 5)."""

from decimal import Decimal
from django.test import TestCase
from apps.testing import OperadorTestCase

from apps.fleet.models import Paquete, PaqueteServicio, Personalizacion, Servicio, ServicioPersonalizacion
from apps.payments.pricing import (
    calcular_precio_paquete, personas_cobradas, precio_paquete, precio_paquete_total,
)
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
            precio_base=Decimal('5000.00')
        )
        self.servicio_snack = Servicio.objects.create(
            empresa=self.empresa, nombre='Catering', slug='catering-srv', tipo_servicio='otro',
            precio_base=Decimal('1000.00')
        )

        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Experiencia VIP',
            slug='experiencia-vip',
            precio_ancla=Decimal('6500.00'),
        )

        self.ps_pesca = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_pesca, orden=1,
        )
        self.ps_snack = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.servicio_snack, orden=2,
        )

    def test_por_persona_multiplica_el_ancla_por_las_personas(self):
        Paquete.objects.filter(pk=self.paquete.pk).update(estrategia_precio='por_persona')
        self.paquete.refresh_from_db()
        self.assertEqual(precio_paquete_total(self.paquete, personas=3, moneda='MXN'), Decimal('19500.00'))
        # 6500/18 = 361.11 -> 362 por persona
        self.assertEqual(
            precio_paquete_total(self.paquete, personas=2, moneda='USD', tipo_cambio=Decimal('18')),
            Decimal('724.00'),
        )

    def test_por_grupo_cobra_extra_tras_personas_base_en_mxn_y_usd(self):
        self.paquete.estrategia_precio = 'por_grupo'
        self.paquete.personas_precio_base = 3
        self.paquete.precio_persona_extra = Decimal('500.00')
        self.assertTrue(self.paquete.precio_depende_de_personas)
        self.assertEqual(self.paquete.precio_total_en('MXN', 5), Decimal('7500.00'))
        # 6500/18 -> 362 y 500/18 -> 28; se convierte cada precio antes de sumar.
        self.assertEqual(self.paquete.precio_total_en('USD', 5, Decimal('18')), Decimal('418.00'))

    def test_personas_cobradas_toma_el_mayor_de_los_servicios(self):
        self.assertEqual(
            personas_cobradas(self.paquete, {self.servicio_pesca.pk: 4, self.servicio_snack.pk: 2}),
            4,
        )

    def test_paquete_fijo_ignora_las_personas(self):
        self.assertEqual(precio_paquete_total(self.paquete, personas=4, moneda='MXN'), Decimal('6500.00'))

    def test_calcular_precio_fijo_mxn_y_usd(self):
        precio_mxn = calcular_precio_paquete(self.paquete, moneda='MXN')
        self.assertEqual(precio_mxn, Decimal('6500.00'))

        precio_usd = calcular_precio_paquete(self.paquete, moneda='USD', tipo_cambio=Decimal('18'))
        self.assertEqual(precio_usd, Decimal('362.00'))

    def test_usd_sin_tipo_de_cambio_falla(self):
        with self.assertRaises(ValueError):
            calcular_precio_paquete(self.paquete, moneda='USD')

    def test_recomendada_se_cobra_solo_si_viene_explicita(self):
        p = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Licencia nueva',
            cobrar_por_persona=True, cantidad_editable=True,
        )
        sp = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_pesca,
            personalizacion=p, precio=Decimal('450'), preseleccionado=True,
        )
        ancla = self.paquete.precio_ancla
        self.assertEqual(precio_paquete_total(self.paquete, personalizaciones_extra=[], personas=5), ancla)
        self.assertEqual(
            precio_paquete_total(self.paquete, personalizaciones_extra=[(sp.pk, 2)], personas=5),
            ancla + Decimal('900'),
        )
        self.assertEqual(calcular_precio_paquete(self.paquete), ancla)


class PrecioPaqueteTotalTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Paquetes', slug='empresa-paquetes'
        )

        self.servicio_pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca Fondo', slug='pesca-fondo', tipo_servicio='pesca',
            precio_base=Decimal('5000.00')
        )
        self.servicio_snack = Servicio.objects.create(
            empresa=self.empresa, nombre='Snack Panga', slug='snack-panga', tipo_servicio='otro',
            precio_base=Decimal('1000.00')
        )

        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Pack Pesca y Snack',
            slug='pack-pesca-snack',
            precio_ancla=Decimal('6500.00'),
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
            precio=Decimal('250.00'),
            obligatorio=True, preseleccionado=False, activo=True
        )

        self.pers_carnada = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Carnada Viva Premium', cobrar_por_persona=False
        )
        self.sp_carnada = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_pesca, personalizacion=self.pers_carnada,
            precio=Decimal('300.00'),
            obligatorio=False, preseleccionado=False, activo=True
        )

        # Personalizaciones para snack:
        self.pers_bebidas = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Pack Cervezas', cobrar_por_persona=False
        )
        self.sp_bebidas = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_snack, personalizacion=self.pers_bebidas,
            precio=Decimal('100.00'),
            obligatorio=False, preseleccionado=True, activo=True
        )

        self.pers_album = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Álbum Foto', cobrar_por_persona=True
        )
        self.sp_album = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_snack, personalizacion=self.pers_album,
            precio=Decimal('200.00'),
            obligatorio=False, preseleccionado=False, activo=True
        )

    def test_sin_extras_devuelve_solo_ancla(self):
        # personas=2
        # ancla = 6500 MXN (obligatorias y preseleccionadas NO se auto-incluyen)
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[],
            personas=2,
            moneda='MXN'
        )
        self.assertEqual(total, Decimal('6500.00'))

        # En USD: 6500/18 = 361.11 -> 362
        total_usd = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[],
            personas=2,
            moneda='USD',
            tipo_cambio=Decimal('18'),
        )
        self.assertEqual(total_usd, Decimal('362.00'))

    def test_personalizacion_marcada_suma_su_precio(self):
        # personas=2
        # extras explícitos: carnada (plana $300) y álbum ($200 * 2 personas = $400)
        # ancla: 6500 MXN
        # total esperado: 6500 + 300 + 400 = 7200 MXN
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[
                (self.sp_carnada.pk, 1),
                (self.sp_album.pk, 1),
            ],
            personas=2,
            moneda='MXN'
        )
        self.assertEqual(total, Decimal('7200.00'))

    def test_personalizaciones_preseleccionadas_u_obligatorias_solo_se_cobran_si_vienen_explicitas(self):
        # Si vienen explícitas: licencia ($250 * 2 = $500) y bebidas ($100)
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[
                (self.sp_licencia.pk, 1),
                (self.sp_bebidas.pk, 1),
            ],
            personas=2,
            moneda='MXN'
        )
        self.assertEqual(total, Decimal('7100.00'))

    def test_input_no_check_no_agrega_cargo(self):
        pers_input = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Nota especial',
            tipo_interaccion='input_texto',
        )
        sp_input = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_pesca, personalizacion=pers_input,
            precio=Decimal('100.00'), activo=True,
        )
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[(sp_input.pk, 1)],
            personas=2,
            moneda='MXN',
        )
        self.assertEqual(total, Decimal('6500.00'))

    def test_componente_inactivo_o_personalizacion_inactiva_se_ignora(self):
        self.sp_carnada.activo = False
        self.sp_carnada.save(update_fields=['activo'])
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[(self.sp_carnada.pk, 1)],
            personas=2,
            moneda='MXN',
        )
        self.assertEqual(total, Decimal('6500.00'))

    def test_extras_en_usd_suben_al_dolar_cada_uno(self):
        # carnada 300/18 = 16.67 -> 17; album 200/18 = 11.11 -> 12 por 2 personas = 24
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[(self.sp_carnada.pk, 1), (self.sp_album.pk, 1)],
            personas=2,
            moneda='USD',
            tipo_cambio=Decimal('18'),
        )
        self.assertEqual(total, Decimal('362.00') + Decimal('17.00') + Decimal('24.00'))
