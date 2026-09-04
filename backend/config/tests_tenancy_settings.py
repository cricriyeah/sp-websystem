from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase


def _item_por_titulo(titulo):
    for grupo in settings.UNFOLD['SIDEBAR']['navigation']:
        for item in grupo['items']:
            if item['title'] == titulo:
                return item
    raise AssertionError(f"No se encontro el item {titulo!r} en UNFOLD['SIDEBAR']")


class TenancyInstalledAppsTests(SimpleTestCase):
    def test_apps_tenancy_antes_de_fleet_y_bookings(self):
        apps = settings.INSTALLED_APPS
        self.assertIn('apps.tenancy', apps)
        self.assertLess(apps.index('apps.tenancy'), apps.index('apps.fleet'))
        self.assertLess(apps.index('apps.tenancy'), apps.index('apps.bookings'))


class EmpresaScopeMiddlewareOrderTests(SimpleTestCase):
    def test_middleware_va_despues_de_auth_y_de_axes(self):
        mw = settings.MIDDLEWARE
        idx_auth = mw.index('django.contrib.auth.middleware.AuthenticationMiddleware')
        idx_axes = mw.index('axes.middleware.AxesMiddleware')
        idx_scope = mw.index('apps.tenancy.middleware.EmpresaScopeMiddleware')
        self.assertGreater(idx_scope, idx_auth)
        self.assertGreater(idx_scope, idx_axes)


class SidebarTenancyTests(SimpleTestCase):
    def test_sede_empresa_membresia_solo_operador_de_plataforma(self):
        for titulo in ('Sedes', 'Empresas', 'Membresias'):
            item = _item_por_titulo(titulo)
            with mock.patch(
                'apps.tenancy.scope.es_operador_plataforma', return_value=True
            ):
                self.assertTrue(item['permission'](mock.Mock()), titulo)
            with mock.patch(
                'apps.tenancy.scope.es_operador_plataforma', return_value=False
            ):
                self.assertFalse(item['permission'](mock.Mock()), titulo)


class FinanzasPermisoTests(SimpleTestCase):
    def test_visible_para_operador_de_plataforma(self):
        item = _item_por_titulo('Finanzas')
        with mock.patch(
            'apps.tenancy.scope.es_operador_plataforma', return_value=True
        ):
            self.assertTrue(item['permission'](mock.Mock()))

    def test_visible_para_jefe_o_vendedora_con_empresa(self):
        item = _item_por_titulo('Finanzas')
        with mock.patch(
            'apps.tenancy.scope.es_operador_plataforma', return_value=False
        ), mock.patch(
            'apps.tenancy.scope.empresa_actual', return_value=mock.Mock()
        ):
            self.assertTrue(item['permission'](mock.Mock()))

    def test_oculto_sin_membresia_ni_operador(self):
        item = _item_por_titulo('Finanzas')
        with mock.patch(
            'apps.tenancy.scope.es_operador_plataforma', return_value=False
        ), mock.patch('apps.tenancy.scope.empresa_actual', return_value=None):
            self.assertFalse(item['permission'](mock.Mock()))
