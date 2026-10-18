"""`capacidad_maxima` del servicio llega al frontend (tope de personas del checkout)."""

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class CapacidadMaximaAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede Cap', slug='sede-cap')
            self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa Cap', slug='empresa-cap')
            self.con_tope = Servicio.objects.create(
                empresa=self.empresa, nombre='Traslado', slug='traslado-cap', tipo_servicio='transporte',
                precio_base=Decimal('1000.00'), capacidad_maxima=14,
            )
            self.sin_tope = Servicio.objects.create(
                empresa=self.empresa, nombre='Paseo', slug='paseo-cap', tipo_servicio='paseo',
                precio_base=Decimal('500.00'),
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.empresa, nombre='Combo', slug='combo-cap',
                precio_ancla=Decimal('2000.00'), activo=True,
            )
            PaqueteServicio.objects.create(
                paquete=self.paquete, servicio=self.con_tope, orden=1, dia_estancia=1, personas_incluidas=1,
            )
            PaqueteServicio.objects.create(
                paquete=self.paquete, servicio=self.sin_tope, orden=2, dia_estancia=1, personas_incluidas=1,
            )

    def test_el_detalle_del_servicio_trae_su_tope(self):
        datos = self.client.get('/api/empresa-cap/servicios/traslado-cap/').json()
        self.assertEqual(datos['capacidad_maxima'], 14)

    def test_sin_tope_definido_es_null(self):
        datos = self.client.get('/api/empresa-cap/servicios/paseo-cap/').json()
        self.assertIsNone(datos['capacidad_maxima'])

    def test_el_listado_de_servicios_lo_trae(self):
        datos = {s['slug']: s['capacidad_maxima'] for s in self.client.get('/api/empresa-cap/servicios/').json()}
        self.assertEqual(datos, {'traslado-cap': 14, 'paseo-cap': None})

    def test_el_paquete_lo_trae_en_cada_servicio_asociado(self):
        resp = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/{self.paquete.slug}/')
        self.assertEqual(resp.status_code, 200)
        topes = {c['servicio']['slug']: c['servicio']['capacidad_maxima'] for c in resp.json()['servicios_asociados']}
        self.assertEqual(topes, {'traslado-cap': 14, 'paseo-cap': None})
