"""Tests del system check `revisar_rol_rls` (guardia de arranque de ADR-001)."""
from unittest import mock

from django.db import connection
from django.db.utils import DatabaseError
from django.test import SimpleTestCase, override_settings

from . import checks
from .rls import rol_de_conexion_es_seguro


class RevisarRolRlsTests(SimpleTestCase):
    def _correr(self):
        return checks.revisar_rol_rls(app_configs=None)

    def test_rol_seguro_no_reporta_nada(self):
        with mock.patch.object(
            checks, 'rol_de_conexion_es_seguro', return_value=(True, {'vendor': 'x'})
        ):
            self.assertEqual(self._correr(), [])

    @override_settings(DEBUG=True)
    def test_rol_inseguro_en_dev_es_warning(self):
        detalle = {'usuario': 'postgres', 'rolsuper': True, 'rolbypassrls': True}
        with mock.patch.object(
            checks, 'rol_de_conexion_es_seguro', return_value=(False, detalle)
        ):
            resultado = self._correr()
        self.assertEqual([w.id for w in resultado], [checks.W001])

    @override_settings(DEBUG=False)
    def test_rol_inseguro_en_produccion_es_error(self):
        detalle = {'usuario': 'service_role', 'rolsuper': False, 'rolbypassrls': True}
        with mock.patch.object(
            checks, 'rol_de_conexion_es_seguro', return_value=(False, detalle)
        ):
            resultado = self._correr()
        self.assertEqual([e.id for e in resultado], [checks.E001])

    def test_base_no_disponible_no_revienta_el_check(self):
        with mock.patch.object(
            checks, 'rol_de_conexion_es_seguro', side_effect=DatabaseError('no db')
        ):
            self.assertEqual(self._correr(), [])


class RolDeConexionEsSeguroTests(SimpleTestCase):
    # En Postgres consulta pg_roles; SimpleTestCase bloquea el acceso a la base
    # salvo que se declare aqui. No escribe nada.
    databases = {'default'}

    def test_backend_no_postgres_se_considera_seguro(self):
        seguro, detalle = rol_de_conexion_es_seguro()
        if connection.vendor == 'postgresql':
            # En CI-postgres el rol es ci_rls (NOSUPERUSER NOBYPASSRLS).
            self.assertTrue(seguro, detalle)
            self.assertFalse(detalle['rolsuper'])
            self.assertFalse(detalle['rolbypassrls'])
        else:
            self.assertTrue(seguro)
            self.assertEqual(detalle['vendor'], connection.vendor)
