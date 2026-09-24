"""El catálogo público expone el anticipo efectivo de servicios y paquetes."""
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class CatalogoAnticipoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede CA', slug='sede-ca-test')
            self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca CA', slug='pesca-ca')
            self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp CA', slug='transp-ca')
            s_pesca = Servicio.objects.create(
                empresa=self.pesca, nombre='Pesca', slug='pesca-ca-s', tipo_servicio='pesca',
                precio_base=Decimal('4000.00'), porcentaje_anticipo=40,
            )
            s_transp = Servicio.objects.create(
                empresa=self.transp, nombre='Traslado', slug='traslado-ca-s', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
            )
            mono = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Mono', slug='mono-ca',
                precio_ancla=Decimal('5000.00'), porcentaje_anticipo=50,
            )
            PaqueteServicio.objects.create(paquete=mono, servicio=s_pesca, orden=1)
            cruza = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Cruza', slug='cruza-ca',
                precio_ancla=Decimal('9000.00'), permite_anticipo=True,
            )
            PaqueteServicio.objects.create(paquete=cruza, servicio=s_pesca, orden=1)
            PaqueteServicio.objects.create(paquete=cruza, servicio=s_transp, orden=2)

    def _paquete(self, slug):
        respuesta = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/{slug}/')
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        return respuesta.json()

    def test_paquete_de_una_empresa_expone_su_anticipo(self):
        datos = self._paquete('mono-ca')
        self.assertTrue(datos['permite_anticipo'])
        self.assertEqual(datos['porcentaje_anticipo'], 50)
        self.assertFalse(datos['es_cruza_empresa'])
        self.assertEqual(datos['servicios_asociados'][0]['servicio']['porcentaje_anticipo'], 40)

    def test_paquete_de_dos_empresas_nunca_dice_que_permite_anticipo(self):
        datos = self._paquete('cruza-ca')
        self.assertFalse(datos['permite_anticipo'])
        self.assertTrue(datos['es_cruza_empresa'])


class CatalogoEstanciaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        with scope.como_operador_plataforma():
            sede = Sede.objects.create(nombre='Sede CE', slug='sede-ce-test')
            empresa = Empresa.objects.create(sede=sede, nombre='Empresa CE', slug='empresa-ce')
            pesca = Servicio.objects.create(
                empresa=empresa, nombre='Pesca', slug='pesca-ce', tipo_servicio='pesca',
                precio_base=Decimal('4000.00'),
            )
            hotel = Servicio.objects.create(
                empresa=empresa, nombre='Cabaña', slug='cabana-ce', tipo_servicio='hospedaje',
                estrategia_cupo='por_noche', estrategia_precio='por_noche',
            )
            paquete = Paquete.objects.create(
                sede=sede, empresa_lider=empresa, nombre='Fin de semana', slug='finde-ce',
                precio_ancla=Decimal('9500.00'),
            )
            PaqueteServicio.objects.create(paquete=paquete, servicio=pesca, orden=1, dia_estancia=2, personas_incluidas=3)
            PaqueteServicio.objects.create(paquete=paquete, servicio=hotel, orden=2, noches=2, personas_incluidas=2)
        self.sede = sede

    def test_el_catalogo_trae_estancia_y_personas_por_componente(self):
        datos = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/finde-ce/').json()
        self.assertEqual(datos['noches'], 2)
        por_slug = {c['servicio']['slug']: c for c in datos['servicios_asociados']}
        self.assertEqual(por_slug['pesca-ce']['dia_estancia'], 2)
        self.assertEqual(por_slug['pesca-ce']['personas_incluidas'], 3)
        self.assertIsNone(por_slug['pesca-ce']['noches'])
        self.assertEqual(por_slug['cabana-ce']['noches'], 2)
