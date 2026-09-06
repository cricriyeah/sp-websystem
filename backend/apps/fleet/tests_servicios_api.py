"""Pruebas de endpoints públicos de servicios y catálogo (Pieza 3)."""

from decimal import Decimal
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fleet.models import Personalizacion, Servicio, ServicioPersonalizacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class ServiciosAPITests(TestCase):
    def setUp(self):
        # El throttle de DRF cuenta por IP en el cache y no se reinicia entre
        # clases de test (ver apps.testing.ApiTestCase).
        cache.clear()
        self.client = APIClient()
        self.sede = Sede.objects.create(nombre='Sede API', slug='sede-api')
        self.empresa_a = Empresa.objects.create(sede=self.sede, nombre='Empresa A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=self.sede, nombre='Empresa B', slug='empresa-b')

        # Datos sembrados bajo alcance de operador (cross-empresa); las
        # peticiones de abajo van sin alcance y cada vista abre el suyo.
        with scope.como_operador_plataforma():
            self._sembrar()

    def _sembrar(self):
        # Servicio activo en Empresa A
        self.servicio_a = Servicio.objects.create(
            empresa=self.empresa_a,
            nombre='Pesca en La Paz',
            slug='pesca-la-paz',
            tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia',
            estrategia_precio='por_grupo',
            modo_ocupacion='exclusivo',
            precio_base=Decimal('4500.00'),
            precio_base_usd=Decimal('260.00'),
            precio_persona_extra=Decimal('500.00'),
            precio_persona_extra_usd=Decimal('30.00'),
            personas_incluidas=3,
            activo=True,
        )

        # Personalizacion en Empresa A
        self.pers_a = Personalizacion.objects.create(
            empresa=self.empresa_a,
            nombre='Carnada Viva',
            tipo='carnada',
            cobrar_por_persona=False,
            activo=True,
        )
        self.sp_a = ServicioPersonalizacion.objects.create(
            servicio=self.servicio_a,
            personalizacion=self.pers_a,
            precio=Decimal('300.00'),
            precio_usd=Decimal('18.00'),
            obligatorio=False,
            preseleccionado=True,
            activo=True,
        )

        # Servicio inactivo en Empresa A
        self.servicio_inactivo = Servicio.objects.create(
            empresa=self.empresa_a,
            nombre='Tour Inactivo',
            slug='tour-inactivo',
            precio_base=Decimal('1000.00'),
            activo=False,
        )

        # Servicio en Empresa B
        self.servicio_b = Servicio.objects.create(
            empresa=self.empresa_b,
            nombre='Tour Loreto',
            slug='tour-loreto',
            precio_base=Decimal('3500.00'),
            activo=True,
        )

    def test_listar_servicios_empresa_a(self):
        resp = self.client.get('/api/empresa-a/servicios/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['slug'], 'pesca-la-paz')
        self.assertEqual(data[0]['precio_base'], '4500.00')
        self.assertEqual(data[0]['precio_base_usd'], '260.00')

        # Verifica personalizaciones anidadas
        pers = data[0]['personalizaciones']
        self.assertEqual(len(pers), 1)
        self.assertEqual(pers[0]['nombre'], 'Carnada Viva')
        self.assertEqual(pers[0]['precio'], '300.00')
        self.assertTrue(pers[0]['preseleccionado'])

    def test_listar_servicios_aislamiento_entre_empresas(self):
        resp_b = self.client.get('/api/empresa-b/servicios/')
        self.assertEqual(resp_b.status_code, 200)
        data_b = resp_b.json()
        self.assertEqual(len(data_b), 1)
        self.assertEqual(data_b[0]['slug'], 'tour-loreto')

    def test_detalle_servicio_exitoso(self):
        resp = self.client.get('/api/empresa-a/servicios/pesca-la-paz/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['nombre'], 'Pesca en La Paz')
        self.assertEqual(data['personas_incluidas'], 3)
        self.assertEqual(data['estrategia_precio'], 'por_grupo')

    def test_detalle_servicio_inactivo_devuelve_404(self):
        resp = self.client.get('/api/empresa-a/servicios/tour-inactivo/')
        self.assertEqual(resp.status_code, 404)

    def test_detalle_servicio_de_otra_empresa_devuelve_404(self):
        # El servicio existe pero pertenece a empresa-b
        resp = self.client.get('/api/empresa-a/servicios/tour-loreto/')
        self.assertEqual(resp.status_code, 404)

    def test_empresa_inexistente_devuelve_404(self):
        resp = self.client.get('/api/empresa-fantasma/servicios/')
        self.assertEqual(resp.status_code, 404)
