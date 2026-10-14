"""Pruebas de las páginas de error (403, 404, 500) y middleware de admin."""

from django.contrib.auth.models import Group, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.tenancy.middleware_errores import ErrorInesperadoAdminMiddleware
from config.errores import error_500


class PaginasDeErrorTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_test',
            password='password123',
            is_staff=True,
        )
        # Sin membresia el middleware de alcance responde 403 en cualquier ruta del
        # admin; el operador de plataforma no necesita una.
        self.operador = User.objects.create_user(
            username='operador_test', password='password123', is_staff=True,
        )
        self.operador.groups.add(Group.objects.get_or_create(name='OperadorPlataforma')[0])

    def test_404_admin_con_usuario_staff(self):
        """GET /admin/ruta-que-no-existe/ con staff -> 404 con 'Volver al panel' y 'Código de referencia'."""
        self.client.force_login(self.operador)
        respuesta = self.client.get('/admin/ruta-que-no-existe/')
        self.assertEqual(respuesta.status_code, 404)
        self.assertContains(respuesta, 'Volver al panel', status_code=404)
        self.assertContains(respuesta, 'Código de referencia', status_code=404)
        self.assertContains(respuesta, 'Esta página no existe', status_code=404)

    def test_404_api_no_contiene_html_del_admin(self):
        """404 bajo /api/inexistente/ -> 404 simple, no extiende el admin ni contiene su HTML."""
        respuesta = self.client.get('/api/inexistente/')
        self.assertEqual(respuesta.status_code, 404)
        self.assertNotContains(respuesta, 'Volver al panel', status_code=404)
        self.assertNotContains(respuesta, 'id="nav-sidebar"', status_code=404)
        self.assertContains(respuesta, 'Código de referencia', status_code=404)

    def test_403_admin_permission_denied(self):
        """Vista que lanza PermissionDenied en /admin/ -> 403 con pagina propia y aviso."""
        self.client.force_login(self.staff_user)
        # El usuario staff sin membresia ni rol de jefe recibe PermissionDenied en finanzas
        respuesta = self.client.get('/admin/finanzas/')
        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, 'No tienes permiso para abrir esta página', status_code=403)
        self.assertContains(respuesta, 'Si crees que deberías tenerlo, avisa a tu jefe o al operador', status_code=403)
        self.assertContains(respuesta, 'Código de referencia', status_code=403)
        self.assertContains(respuesta, 'Volver al panel', status_code=403)

    def test_500_autonoma(self):
        """error_500 responde 500, es autonoma y contiene los textos requeridos."""
        factory = RequestFactory()
        request = factory.get('/admin/')
        with self.assertLogs('apps.errores', level='ERROR') as cm:
            respuesta = error_500(request)
        self.assertEqual(respuesta.status_code, 500)
        contenido = respuesta.content.decode('utf-8')
        self.assertIn('Algo salió mal', contenido)
        self.assertIn('Código de referencia:', contenido)
        self.assertIn('Volver al panel', contenido)
        self.assertNotIn('id="nav-sidebar"', contenido)
        self.assertTrue(any('Error 500' in out for out in cm.output))


class ErrorInesperadoAdminMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ErrorInesperadoAdminMiddleware()
        self.user = User.objects.create_user(
            username='admin_test',
            password='password123',
            is_staff=True,
        )

    def _simular_request(self, path, method='get', referer=None, headers=None):
        if method.lower() == 'post':
            request = self.factory.post(path, **(headers or {}))
        else:
            request = self.factory.get(path, **(headers or {}))

        if referer:
            request.META['HTTP_REFERER'] = referer

        request.user = self.user

        session_middleware = SessionMiddleware(lambda r: None)
        session_middleware.process_request(request)
        request.session.save()

        storage = FallbackStorage(request)
        setattr(request, '_messages', storage)

        return request

    def test_runtime_error_redirects_and_adds_honest_message(self):
        """RuntimeError en /admin/ genera redirect, mensaje honesto con código y sin 'no se guardó'."""
        request = self._simular_request('/admin/bookings/reserva/')
        respuesta = self.middleware.process_exception(request, RuntimeError("Error inesperado de prueba"))
        self.assertIsInstance(respuesta, HttpResponseRedirect)
        self.assertEqual(respuesta.url, reverse('admin:index'))

        mensajes = [m.message for m in getattr(request, '_messages')]
        self.assertEqual(len(mensajes), 1)
        texto = mensajes[0]
        self.assertIn('Algo salió mal (código', texto)
        self.assertIn('Es posible que una parte de la operación sí se haya aplicado', texto)
        self.assertNotIn('no se guardó', texto.lower())

    def test_referer_mismo_host_redirige_a_referer(self):
        """Con HTTP_REFERER del mismo host, redirige a la pantalla anterior."""
        request = self._simular_request(
            '/admin/bookings/reserva/1/change/',
            referer='http://testserver/admin/bookings/reserva/',
        )
        respuesta = self.middleware.process_exception(request, RuntimeError("Fallo inesperado"))
        self.assertIsInstance(respuesta, HttpResponseRedirect)
        self.assertEqual(respuesta.url, 'http://testserver/admin/bookings/reserva/')

    def test_referer_externo_redirige_a_admin_index(self):
        """Con HTTP_REFERER de otro host, redirige a /admin/."""
        request = self._simular_request(
            '/admin/bookings/reserva/1/change/',
            referer='http://externo.com/phishing',
        )
        respuesta = self.middleware.process_exception(request, RuntimeError("Fallo inesperado"))
        self.assertIsInstance(respuesta, HttpResponseRedirect)
        self.assertEqual(respuesta.url, reverse('admin:index'))

    def test_evita_bucle_en_get_con_mismo_path(self):
        """Si en GET el referer es la misma ruta, redirige a /admin/ para no ciclar."""
        request = self._simular_request(
            '/admin/bookings/reserva/1/change/',
            referer='http://testserver/admin/bookings/reserva/1/change/',
        )
        respuesta = self.middleware.process_exception(request, RuntimeError("Fallo inesperado"))
        self.assertIsInstance(respuesta, HttpResponseRedirect)
        self.assertEqual(respuesta.url, reverse('admin:index'))

    def test_excepciones_esperadas_devuelven_none(self):
        """PermissionDenied y Http404 no son interceptadas (devuelven None)."""
        request = self._simular_request('/admin/bookings/reserva/')
        self.assertIsNone(self.middleware.process_exception(request, PermissionDenied()))
        self.assertIsNone(self.middleware.process_exception(request, Http404()))

    def test_ruta_fuera_de_admin_devuelve_none(self):
        """Peticiones fuera de /admin/ no son interceptadas."""
        request = self._simular_request('/api/servicios/')
        self.assertIsNone(self.middleware.process_exception(request, RuntimeError("Fallo API")))

    def test_peticiones_ajax_o_json_devuelven_none(self):
        """Peticiones AJAX o con Accept application/json devuelven None."""
        req_ajax = self._simular_request(
            '/admin/bookings/reserva/',
            headers={'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'},
        )
        self.assertIsNone(self.middleware.process_exception(req_ajax, RuntimeError("Fallo ajax")))

        req_json = self._simular_request(
            '/admin/bookings/reserva/',
            headers={'HTTP_ACCEPT': 'application/json'},
        )
        self.assertIsNone(self.middleware.process_exception(req_json, RuntimeError("Fallo json")))

    def test_assert_logs_apps_errores(self):
        """El middleware registra el error en el logger 'apps.errores'."""
        request = self._simular_request('/admin/bookings/reserva/')
        with self.assertLogs('apps.errores', level='ERROR') as cm:
            self.middleware.process_exception(request, RuntimeError("Excepcion crítica"))
        self.assertTrue(any('Error inesperado en admin' in log for log in cm.output))
