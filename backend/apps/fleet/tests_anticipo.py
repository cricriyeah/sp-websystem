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
