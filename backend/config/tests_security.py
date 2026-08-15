"""Pruebas de las defensas de autenticacion del admin.

El admin es la unica puerta de auth del sistema, y detras esta todo: el dinero,
la PII de clientes, la gestion de usuarios. Django no trae bloqueo por fuerza
bruta de fabrica; lo pone django-axes (ver config/settings/base.py, AXES_*).

Este hallazgo salio de un pentest dinamico: 8 intentos fallidos seguidos contra
/admin/login/ devolvian 200 sin bloqueo. Los tests de abajo son la red que
impide que vuelva a quedar abierto.
"""
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    AXES_ENABLED=True,
    AXES_FAILURE_LIMIT=5,
    # En el test el cliente entra por 127.0.0.1; el bloqueo por defecto es por
    # usuario+IP, asi que se mantiene ese criterio.
    AXES_LOCKOUT_PARAMETERS=['username', 'ip_address'],
)
class BloqueoDeFuerzaBrutaTests(TestCase):
    URL = '/admin/login/'
    USUARIO = 'jefa'
    PASSWORD = 'La.Buena.2026!'

    def setUp(self):
        # axes lleva la cuenta tambien en cache; sin limpiarla, un test arrastra
        # los intentos de otro.
        cache.clear()
        User.objects.create_superuser(self.USUARIO, 'jefa@x.com', self.PASSWORD)

    def _intento(self, password):
        return self.client.post(
            self.URL,
            {'username': self.USUARIO, 'password': password},
            follow=False,
        )

    def test_bloquea_tras_cinco_intentos_fallidos(self):
        # Cinco intentos malos: cada uno re-muestra el formulario (no bloquea aun).
        for _ in range(5):
            self._intento('mala')

        # El sexto, aunque traiga la contraseña CORRECTA, ya no debe pasar: la
        # cuenta+IP esta bloqueada. Es el corazon del arreglo — el atacante que ya
        # gasto sus intentos no entra ni acertando.
        respuesta = self._intento(self.PASSWORD)
        self.assertNotIn('_auth_user_id', self.client.session,
                         'Entro pese al bloqueo: axes no freno la fuerza bruta.')

    def test_por_debajo_del_limite_no_bloquea(self):
        # Cuatro fallos y a la quinta la correcta: debe entrar. El bloqueo no
        # puede castigar a quien simplemente se equivoco un par de veces.
        for _ in range(4):
            self._intento('mala')

        self._intento(self.PASSWORD)
        self.assertIn('_auth_user_id', self.client.session,
                      'Bloqueo demasiado agresivo: no dejo entrar bajo el limite.')

    @override_settings(AXES_RESET_ON_SUCCESS=True)
    def test_un_login_exitoso_limpia_el_conteo(self):
        # Tres fallos, luego entra bien: el contador se reinicia, asi que despues
        # vuelve a tener sus cinco intentos y no queda a uno del bloqueo.
        for _ in range(3):
            self._intento('mala')
        self._intento(self.PASSWORD)
        self.client.logout()

        for _ in range(4):
            self._intento('mala')
        self._intento(self.PASSWORD)
        self.assertIn('_auth_user_id', self.client.session,
                      'El login exitoso no reinicio el conteo de fallos.')
