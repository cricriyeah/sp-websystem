"""Reglas de anticipo de Servicio y Paquete."""
import importlib
import pkgutil
from decimal import Decimal
from types import SimpleNamespace

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.db import connection

from apps.fleet.models import Paquete, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


def _modulo_migracion():
    import apps.fleet.migrations as paquete_migraciones

    nombre = next(
        n for _, n, _ in pkgutil.iter_modules(paquete_migraciones.__path__)
        if n.endswith('_anticipo_explicito')
    )
    return importlib.import_module(f'apps.fleet.migrations.{nombre}')


class AnticipoServicioPaqueteTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Pesca Anticipo', slug='pesca-anticipo')

    def _servicio(self, slug='pesca-a', **extra):
        return Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug=slug, tipo_servicio='pesca',
            precio_base=Decimal('4000.00'), **extra,
        )

    def test_por_defecto_permite_anticipo_del_30(self):
        servicio = self._servicio()
        self.assertTrue(servicio.permite_anticipo)
        self.assertEqual(servicio.porcentaje_anticipo, 30)

    def test_porcentaje_fuera_de_1_a_99_no_es_valido_en_servicio_ni_paquete(self):
        for pct in (0, 100, 150):
            with self.subTest(pct=pct):
                servicio = self._servicio(slug=f's-{pct}', porcentaje_anticipo=pct)
                with self.assertRaises(ValidationError) as ctx:
                    servicio.full_clean()
                self.assertIn('porcentaje_anticipo', ctx.exception.message_dict)
                paquete = Paquete(
                    sede=self.sede, empresa_lider=self.empresa, nombre='P', slug=f'p-{pct}',
                    precio_ancla=Decimal('5000.00'), porcentaje_anticipo=pct,
                )
                with self.assertRaises(ValidationError) as ctx:
                    paquete.full_clean()
                self.assertIn('porcentaje_anticipo', ctx.exception.message_dict)

    def test_migracion_de_datos_marca_permite_segun_el_porcentaje_viejo(self):
        viejo_completo = self._servicio(slug='viejo-100', porcentaje_anticipo=100)
        viejo_anticipo = self._servicio(slug='viejo-30', porcentaje_anticipo=30)
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='P', slug='p-viejo',
            precio_ancla=Decimal('5000.00'), porcentaje_anticipo=100,
        )

        _modulo_migracion().marcar_permite_anticipo(django_apps, SimpleNamespace(connection=connection))

        for fila in (viejo_completo, viejo_anticipo, paquete):
            fila.refresh_from_db()
        self.assertFalse(viejo_completo.permite_anticipo)
        self.assertEqual(viejo_completo.porcentaje_anticipo, 30)
        self.assertTrue(viejo_anticipo.permite_anticipo)
        self.assertEqual(viejo_anticipo.porcentaje_anticipo, 30)
        self.assertFalse(paquete.permite_anticipo)
        self.assertEqual(paquete.porcentaje_anticipo, 30)

class AnticipoDisponibleTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca AD', slug='pesca-ad')
        self.transporte = Empresa.objects.create(sede=self.sede, nombre='Transp AD', slug='transp-ad')
        self.s_pesca = Servicio.objects.create(
            empresa=self.pesca, nombre='Pesca', slug='pesca-ad-s', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.s_transp = Servicio.objects.create(
            empresa=self.transporte, nombre='Traslado', slug='traslado-ad-s', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
        )

    def _paquete(self, slug, servicios, **extra):
        from apps.fleet.models import PaqueteServicio

        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre=slug, slug=slug,
            precio_ancla=Decimal('9000.00'), **extra,
        )
        for orden, servicio in enumerate(servicios, start=1):
            PaqueteServicio.objects.create(paquete=paquete, servicio=servicio, orden=orden)
        return paquete

    def test_servicio_sigue_su_interruptor(self):
        self.assertTrue(self.s_pesca.anticipo_disponible)
        self.s_pesca.permite_anticipo = False
        self.assertFalse(self.s_pesca.anticipo_disponible)

    def test_paquete_de_una_empresa_admite_anticipo_si_lo_permite(self):
        paquete = self._paquete('mono-ad', [self.s_pesca])
        self.assertFalse(paquete.es_cruza_empresa)
        self.assertTrue(paquete.anticipo_disponible)
        paquete.permite_anticipo = False
        self.assertFalse(paquete.anticipo_disponible)

    def test_paquete_de_dos_empresas_nunca_admite_anticipo(self):
        paquete = self._paquete('cruza-ad', [self.s_pesca, self.s_transp], permite_anticipo=True)
        self.assertTrue(paquete.es_cruza_empresa)
        self.assertFalse(paquete.anticipo_disponible)
