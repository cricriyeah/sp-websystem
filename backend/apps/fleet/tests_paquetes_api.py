"""Pruebas de endpoints públicos de paquetes (Pieza 5)."""

from decimal import Decimal
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class PaquetesAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        with scope.como_operador_plataforma():
            self._sembrar()

    def _sembrar(self):
        self.sede_lp, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.sede_cabo = Sede.objects.create(nombre='Los Cabos', slug='los-cabos-api-test')

        self.empresa_pesca = Empresa.objects.create(
            sede=self.sede_lp, nombre='Pesca La Paz API', slug='pesca-lp-api'
        )
        self.empresa_hotel = Empresa.objects.create(
            sede=self.sede_lp, nombre='Hotel Malecón API', slug='hotel-lp-api'
        )
        self.empresa_inactiva = Empresa.objects.create(
            sede=self.sede_lp, nombre='Empresa Inactiva', slug='empresa-inactiva', activo=False
        )

        self.servicio_pesca = Servicio.objects.create(
            empresa=self.empresa_pesca,
            nombre='Pesca Deportiva Día Completo',
            slug='pesca-dia-completo',
            tipo_servicio='pesca',
            precio_base=Decimal('5000.00'),
            precio_base_usd=Decimal('290.00'),
        )
        self.servicio_hotel = Servicio.objects.create(
            empresa=self.empresa_pesca,
            nombre='Estadía 2 Noches',
            slug='estadia-2-noches',
            tipo_servicio='hospedaje',
            precio_base=Decimal('3500.00'),
            precio_base_usd=Decimal('200.00'),
        )

        # Paquete activo liderado por pesca
        self.paquete_activo = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Fin de Semana Inolvidable',
            slug='fin-de-semana',
            descripcion='Pesca y hospedaje',
            precio_ancla=Decimal('8000.00'),
            precio_ancla_usd=Decimal('470.00'),
            activo=True,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete_activo,
            servicio=self.servicio_pesca,
            orden=1,
            removible=False,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete_activo,
            servicio=self.servicio_hotel,
            orden=2,
            removible=True,
            ajuste_precio=Decimal('3000.00'),
            ajuste_precio_usd=Decimal('175.00'),
        )

        # Paquete inactivo
        self.paquete_inactivo = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Paquete Inactivo',
            slug='paquete-inactivo',
            precio_ancla=Decimal('6000.00'),
            activo=False,
        )

        # Paquete de empresa inactiva
        self.paquete_empresa_inactiva = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_inactiva,
            nombre='Paquete Pausado',
            slug='paquete-pausado',
            precio_ancla=Decimal('4000.00'),
            activo=True,
        )

    def test_paquetes_por_sede_lista_activos(self):
        url = f'/api/sedes/{self.sede_lp.slug}/paquetes/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertEqual(len(data), 1)
        item = data[0]
        self.assertEqual(item['slug'], 'fin-de-semana')
        self.assertEqual(item['empresa_lider_slug'], 'pesca-lp-api')
        self.assertEqual(float(item['precio_ancla']), 8000.00)
        self.assertEqual(float(item['precio_ancla_usd']), 470.00)

        servicios = item['servicios_asociados']
        self.assertEqual(len(servicios), 2)
        slugs = [s['servicio']['slug'] for s in servicios]
        self.assertIn('pesca-dia-completo', slugs)
        self.assertIn('estadia-2-noches', slugs)
        pesca = next(s for s in servicios if s['servicio']['slug'] == 'pesca-dia-completo')
        self.assertFalse(pesca['removible'])

    def test_paquetes_por_sede_inexistente_404(self):
        resp = self.client.get('/api/sedes/sede-inexistente/paquetes/')
        self.assertEqual(resp.status_code, 404)

    def test_paquetes_por_sede_vacia(self):
        url = f'/api/sedes/{self.sede_cabo.slug}/paquetes/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_paquetes_por_empresa_lista_activos(self):
        url = f'/api/{self.empresa_pesca.slug}/paquetes/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['slug'], 'fin-de-semana')

    def test_paquetes_por_empresa_otra_empresa_vacia(self):
        url = f'/api/{self.empresa_hotel.slug}/paquetes/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_paquetes_por_empresa_inexistente_o_inactiva_404(self):
        resp = self.client.get('/api/empresa-fantasma/paquetes/')
        self.assertEqual(resp.status_code, 404)

        resp_inactiva = self.client.get(f'/api/{self.empresa_inactiva.slug}/paquetes/')
        self.assertEqual(resp_inactiva.status_code, 404)

    def test_sedes_lista_activas(self):
        resp = self.client.get('/api/sedes/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        slugs = [item['slug'] for item in data]
        self.assertIn(self.sede_lp.slug, slugs)
        self.assertIn(self.sede_cabo.slug, slugs)

    def test_servicios_por_sede_lista_activos(self):
        url = f'/api/sedes/{self.sede_lp.slug}/servicios/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        slugs = [s['slug'] for s in data]
        self.assertIn('pesca-dia-completo', slugs)
        self.assertIn('estadia-2-noches', slugs)

    def test_servicios_por_sede_inexistente_404(self):
        resp = self.client.get('/api/sedes/sede-inexistente/servicios/')
        self.assertEqual(resp.status_code, 404)

    def test_paquete_detalle_devuelve_el_paquete_correcto(self):
        url = f'/api/sedes/{self.sede_lp.slug}/paquetes/{self.paquete_activo.slug}/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['slug'], self.paquete_activo.slug)
        self.assertEqual(data['nombre'], self.paquete_activo.nombre)

    def test_paquete_detalle_404_para_slug_inexistente(self):
        url = f'/api/sedes/{self.sede_lp.slug}/paquetes/no-existe/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_paquete_detalle_404_si_sede_inactiva(self):
        sede_inactiva = Sede.objects.create(nombre='Sede Inactiva', slug='sede-inactiva', activo=False)
        url = f'/api/sedes/{sede_inactiva.slug}/paquetes/{self.paquete_activo.slug}/'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
