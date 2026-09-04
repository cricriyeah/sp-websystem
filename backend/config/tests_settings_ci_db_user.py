import importlib
import os
from unittest import mock

from django.test import SimpleTestCase


class DefaultDbUserYaNoEsPostgresTests(SimpleTestCase):
    """
    `config/settings/ci.py` deja de asumir el superusuario `postgres` como
    default de `DB_USER` — el rol nuevo (`ci_rls`, ver .github/workflows/ci.yml)
    es el que CI usa de verdad. Recarga el módulo con `DB_USER` ausente del
    entorno para leer su valor de default sin depender de qué settings module
    esté activo mientras corre este test.
    """

    def test_default_db_user_es_ci_rls(self):
        entorno_sin_db_user = {k: v for k, v in os.environ.items() if k != 'DB_USER'}
        with mock.patch.dict(os.environ, entorno_sin_db_user, clear=True):
            modulo = importlib.import_module('config.settings.ci')
            importlib.reload(modulo)
            self.assertEqual(modulo.DATABASES['default']['USER'], 'ci_rls')
