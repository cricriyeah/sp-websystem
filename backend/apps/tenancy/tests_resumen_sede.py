"""`resumen` de cada sede en /api/sedes/ (Task 9.3, paso 2c): el «desde» y los tipos del catálogo
para las tarjetas del hub, calculados en el backend con la misma regla de redondeo del cobro.

Se lee con `servicios_de_sede`/`paquetes_de_sede`, que abren el alcance de cada empresa: en
Postgres con RLS una consulta directa desde el serializer devolvería `desde: null`.
"""

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fleet.models import Paquete, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class ResumenSedeTests(TestCase):
    def setUp(self):
        cache.clear()
        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede Resumen', slug='sede-resumen', tipo_cambio_usd=Decimal('18.00'))
            self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa Resumen', slug='empresa-resumen')

    def _servicio(self, slug, precio, **extra):
        with scope.como_operador_plataforma():
            return Servicio.objects.create(
                empresa=self.empresa, nombre=extra.pop('nombre', slug), slug=slug,
                tipo_servicio=extra.pop('tipo_servicio', 'paseo'), precio_base=Decimal(precio), pide_hora=False, **extra,
            )

    def _paquete(self, slug, precio, **extra):
        with scope.como_operador_plataforma():
            return Paquete.objects.create(
                sede=self.sede, empresa_lider=self.empresa, nombre=slug, slug=slug, precio_ancla=Decimal(precio), **extra,
            )

    def _resumen(self):
        respuesta = APIClient().get('/api/sedes/')
        self.assertEqual(respuesta.status_code, 200)
        return next(s for s in respuesta.json() if s['slug'] == 'sede-resumen')['resumen']

    def test_sede_sin_precios(self):
        self.assertEqual(self._resumen(), {'desde': None, 'tipos': []})

    def test_minimo_sin_por_ruta_y_usd_hacia_arriba(self):
        self._servicio('traslado', '300.00', tipo_servicio='transporte', estrategia_precio='por_ruta')
        self._servicio('paseo', '1000.00', estrategia_precio='por_grupo')
        self._servicio('pesca', '4000.00', tipo_servicio='pesca', estrategia_precio='por_grupo')
        resumen = self._resumen()
        self.assertEqual(resumen['desde'], {'monto_mxn': '1000.00', 'monto_usd': '56.00', 'base': 'por_grupo', 'tipo': 'servicio'})
        self.assertEqual(resumen['tipos'], ['paseo', 'pesca', 'transporte'])

    def test_el_paquete_cuenta_con_su_precio_ancla(self):
        self._servicio('paseo', '1000.00', estrategia_precio='por_grupo')
        self._paquete('combo', '800.00', estrategia_precio='por_persona')
        resumen = self._resumen()
        self.assertEqual(resumen['desde'], {'monto_mxn': '800.00', 'monto_usd': '45.00', 'base': 'por_persona', 'tipo': 'paquete'})
        self.assertIn('paquete', resumen['tipos'])

    def test_empate_gana_el_servicio(self):
        self._servicio('paseo', '900.00', estrategia_precio='por_grupo')
        self._paquete('combo', '900.00')
        self.assertEqual(self._resumen()['desde']['tipo'], 'servicio')

    def test_catalogo_inactivo_no_cuenta(self):
        self._servicio('paseo', '100.00', activo=False)
        self._paquete('combo', '50.00', activo=False)
        self.assertEqual(self._resumen(), {'desde': None, 'tipos': []})
