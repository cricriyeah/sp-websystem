from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase

from .models import Empresa, Sede

actualizar = import_module('apps.tenancy.migrations.0004_la_ventana_puerto_chale').actualizar_sedes


class SedesHubMigrationTests(TestCase):
    def test_rename_preserves_company_and_destination_identity(self):
        sede = Sede.objects.get(slug='la-ventana')
        sede.slug = 'los-cabos'
        sede.nombre = 'Los Cabos'
        sede.save()
        empresa = Empresa.objects.create(sede=sede, nombre='Operador', slug='operador-migracion')
        actualizar(apps, SimpleNamespace(connection=connection))
        sede.refresh_from_db()
        empresa.refresh_from_db()
        self.assertEqual(sede.slug, 'la-ventana')
        self.assertEqual(sede.nombre, 'La Ventana')
        self.assertEqual(empresa.sede_id, sede.pk)

    def test_repeating_does_not_duplicate_destinations(self):
        chale = Sede.objects.get(slug='puerto-chale')
        actualizar(apps, SimpleNamespace(connection=connection))
        actualizar(apps, SimpleNamespace(connection=connection))
        self.assertEqual(Sede.objects.get(slug='puerto-chale').pk, chale.pk)
        self.assertEqual(Sede.objects.filter(slug='la-ventana').count(), 1)

    def test_conflicting_destinations_are_not_silently_merged(self):
        Sede.objects.create(nombre='Los Cabos', slug='los-cabos')
        with self.assertRaises(RuntimeError):
            actualizar(apps, SimpleNamespace(connection=connection))
