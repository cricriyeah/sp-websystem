# backend/apps/tenancy/tests_scope.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404, HttpResponse
from django.template import engines
from django.template.response import TemplateResponse
from django.test import RequestFactory, TransactionTestCase
from django.urls import path

from . import scope
from .middleware import EmpresaScopeMiddleware
from .models import Empresa, MembresiaEmpresa, Sede

User = get_user_model()


class ScopePrimitivoTests(TransactionTestCase):
    def setUp(self):
        # slug 'sede-test' a proposito: 'la-paz' ya existe committeada por la
        # migracion de datos 0002 y chocaria con IntegrityError (ver reporte T2).
        sede = Sede.objects.create(nombre='La Paz', slug='sede-test')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-b')

    def test_con_empresa_no_falla_con_el_mismo_valor_anidado(self):
        with scope.con_empresa(self.empresa_a):
            with scope.con_empresa(self.empresa_a):
                pass  # no-op idempotente, no debe lanzar

    def test_con_empresa_falla_con_valor_distinto_anidado(self):
        with scope.con_empresa(self.empresa_a):
            with self.assertRaises(RuntimeError):
                with scope.con_empresa(self.empresa_b):
                    pass

    def test_con_empresa_restaura_al_salir(self):
        with scope.con_empresa(self.empresa_a):
            pass
        self.assertIsNone(getattr(connection, 'alcance_actual', None))

    def test_con_empresa_restaura_el_valor_exterior_tras_anidar(self):
        with scope.con_empresa(self.empresa_a):
            with scope.con_empresa(self.empresa_a):
                pass
            self.assertEqual(connection.alcance_actual, ('empresa', self.empresa_a.id))

    def test_resolver_membresia_sin_membresias_lanza_permission_denied(self):
        user = User.objects.create_user(username='huerfano', password='x')
        with self.assertRaises(PermissionDenied):
            scope.resolver_membresia_o_403(user)

    def test_resolver_membresia_con_dos_membresias_lanza_permission_denied(self):
        user = User.objects.create_user(username='dos', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        MembresiaEmpresa.objects.create(user=user, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.JEFE)
        with self.assertRaises(PermissionDenied):
            scope.resolver_membresia_o_403(user)

    def test_resolver_membresia_con_una_membresia_devuelve_con_empresa(self):
        user = User.objects.create_user(username='uno', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        with scope.resolver_membresia_o_403(user):
            self.assertEqual(connection.alcance_actual, ('empresa', self.empresa_a.id))

    def test_resolver_membresia_operador_de_plataforma(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        user = User.objects.create_user(username='operador', password='x')
        user.groups.add(grupo)
        with scope.resolver_membresia_o_403(user):
            self.assertEqual(connection.alcance_actual, ('operador',))

    def test_resolver_empresa_publica_404_si_no_existe(self):
        with self.assertRaises(Http404):
            scope.resolver_empresa_publica('no-existe')

    def test_resolver_empresa_publica_404_si_pausada(self):
        self.empresa_a.activo = False
        self.empresa_a.save()
        with self.assertRaises(Http404):
            scope.resolver_empresa_publica('empresa-a')

    def test_resolver_empresa_de_dinero_ignora_activo(self):
        self.empresa_a.activo = False
        self.empresa_a.save()
        empresa = scope.resolver_empresa_de_dinero('empresa-a')
        self.assertEqual(empresa.pk, self.empresa_a.pk)

    def test_es_operador_plataforma(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        user = User.objects.create_user(username='op', password='x')
        self.assertFalse(scope.es_operador_plataforma(user))
        user.groups.add(grupo)
        self.assertTrue(scope.es_operador_plataforma(user))


def _vista_prueba_alcance(request):
    # Devuelve una TemplateResponse SIN renderizar hasta despues de que la
    # vista retorna -- reproduce exactamente el bug de la Revision 2 (admin
    # renderiza perezoso, process_view ya habia devuelto).
    assert connection.alcance_actual is not None
    return TemplateResponse(request, engines['django'].from_string('{{ x }}'), {'x': 'ok'})


urlpatterns_prueba = [path('probar-alcance/', _vista_prueba_alcance, name='probar_alcance')]


class MiddlewareTests(TransactionTestCase):
    databases = {'default'}

    def setUp(self):
        sede = Sede.objects.create(nombre='La Paz', slug='sede-test')
        self.empresa = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.user = User.objects.create_user(username='jefe', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=self.user, empresa=self.empresa, rol=MembresiaEmpresa.Rol.JEFE)

    def _middleware(self, get_response):
        return EmpresaScopeMiddleware(get_response)

    def test_envuelve_todo_get_response_incluido_render_perezoso(self):
        capturado = {}

        def get_response(request):
            response = _vista_prueba_alcance(request)
            # El render perezoso ocurre DESPUES de que la vista retorna --
            # si el middleware solo envolviera la llamada a la vista
            # (process_view), esto ya estaria fuera del alcance.
            capturado['alcance_al_renderizar'] = connection.alcance_actual
            response.render()
            return response

        request = RequestFactory().get('/admin/bookings/reserva/')
        request.user = self.user
        middleware = self._middleware(get_response)

        import apps.tenancy.middleware as middleware_module
        original_resolve = middleware_module.resolve

        def resolve_admin(path_info):
            class Match:
                kwargs = {}
                view_name = 'admin:bookings_reserva_changelist'
            return Match()

        middleware_module.resolve = resolve_admin
        try:
            middleware(request)
        finally:
            middleware_module.resolve = original_resolve

        self.assertEqual(capturado['alcance_al_renderizar'], ('empresa', self.empresa.id))

    def test_ruta_publica_con_empresa_slug_no_se_envuelve(self):
        def get_response(request):
            self.assertIsNone(getattr(connection, 'alcance_actual', None))
            return HttpResponse('ok')

        request = RequestFactory().get('/api/empresa-a/tarifa/')
        request.user = AnonymousUser()
        middleware = self._middleware(get_response)
        middleware(request)

    def test_usuario_anonimo_no_se_envuelve(self):
        def get_response(request):
            self.assertIsNone(getattr(connection, 'alcance_actual', None))
            return HttpResponse('ok')

        request = RequestFactory().get('/admin/login/')
        request.user = AnonymousUser()
        middleware = self._middleware(get_response)
        middleware(request)

    def test_admin_logout_no_lanza_permission_denied_sin_membresia(self):
        huerfano = User.objects.create_user(username='sin-membresia', password='x', is_staff=True)

        def get_response(request):
            return HttpResponse('ok')

        request = RequestFactory().get('/admin/logout/')
        request.user = huerfano
        middleware = self._middleware(get_response)
        # No debe lanzar PermissionDenied.
        middleware(request)

    def test_una_peticion_que_deja_la_bandera_pegada_no_contamina_la_siguiente(self):
        from django.core.signals import request_started

        def get_response_que_revienta(request):
            raise ValueError('boom')

        middleware = self._middleware(get_response_que_revienta)
        request = RequestFactory().get('/admin/')
        request.user = self.user
        with self.assertRaises(ValueError):
            middleware(request)
        # La bandera puede quedar pegada tras una excepcion fuera de cualquier
        # `with` real de vista -- request_started es la red de seguridad.
        request_started.send(sender=None)
        self.assertIsNone(getattr(connection, 'alcance_actual', None))
