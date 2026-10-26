"""Inicio de sesion del backoffice con Turnstile.

Mismo widget y mismas llaves que la recuperacion de contrasena y el checkout, con su propia `action` (`login`) para
que un token de otro formulario no sirva aqui. Se verifica ANTES de mirar usuario y contrasena: un captcha malo no
cuenta como intento fallido de contrasena (Axes) ni dice si las credenciales eran buenas.

Falla cerrada: con las llaves puestas, sin token valido no se entra. Para no dejar a todo el equipo fuera si
Cloudflare se cae, o si el dominio del backend no esta en el widget, existe la salida de emergencia
`LOGIN_TURNSTILE_OBLIGATORIO=0` (variable de entorno en Render). Sin llaves (local, pruebas) no se exige.

Como un captcha rechazado no cuenta en Axes, tiene su propio tope por IP (`LOGIN_MAX_CAPTCHA_FALLIDOS_IP_HORA`): cada
envio con un token falso es una llamada a Cloudflare que ocupa un proceso de gunicorn (los mismos que atienden la API);
pasado el tope se rechaza sin llamar a nadie. Se cuenta en la base y no en el cache, que en produccion es de archivos y
no es atomico entre los procesos (misma razon que la recuperacion de contrasena).
"""
import logging
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.http.request import split_domain_port
from django.utils import timezone

from apps.bookings.captcha import verificar_turnstile_obligatorio
from apps.bookings.ip_cliente import ip_del_cliente

from .models import EventoRecuperacion

logger = logging.getLogger(__name__)

ACCION_LOGIN = 'login'
# `EventoRecuperacion.tipo` es una cadena libre (sin migracion): los captchas de login rechazados van a la misma
# bitacora, sin codigo ni correo, y los barre el mismo `limpiar_eventos_recuperacion`.
TIPO_CAPTCHA_LOGIN = 'login_captcha'
RESULTADO_RECHAZADO = 'rechazado'

MENSAJE_CAPTCHA = (
    'No pudimos comprobar que eres una persona. Espera a que termine la verificación y vuelve a intentarlo; '
    'si no avanza, recarga la página.'
)
MENSAJE_LIMITE = 'Demasiados intentos desde esta conexión. Espera unos minutos y vuelve a intentarlo.'


def login_exige_turnstile():
    """El captcha se exige solo si las dos llaves estan puestas y la salida de emergencia no esta activa."""
    return bool(
        settings.LOGIN_TURNSTILE_OBLIGATORIO and settings.TURNSTILE_SECRET_KEY and settings.TURNSTILE_SITE_KEY
    )


def _captchas_rechazados_de(ip):
    desde = timezone.now() - timedelta(hours=1)
    return EventoRecuperacion.objects.filter(tipo=TIPO_CAPTCHA_LOGIN, ip=ip, creado_en__gte=desde).count()


def _anotar_rechazo(ip):
    try:
        EventoRecuperacion.objects.create(
            tipo=TIPO_CAPTCHA_LOGIN, resultado=RESULTADO_RECHAZADO, correo_hash='', ip=ip or None)
    except Exception:
        # La bitacora no puede ser la razon por la que nadie entre ni la que tumbe la pantalla de login.
        logger.warning('No se pudo anotar el captcha de login rechazado')


class LoginConTurnstile(AdminAuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        # La plantilla (templates/admin/login.html) lee esto para pintar el widget; vacio = no se pinta.
        self.turnstile_site_key = settings.TURNSTILE_SITE_KEY if login_exige_turnstile() else ''

    def clean(self):
        if login_exige_turnstile():
            self._exigir_captcha()
        return super().clean()

    def _exigir_captcha(self):
        # `request` solo falta en pruebas que arman el formulario a mano: sin peticion no hay IP ni hostname
        # contra los cuales verificar, y se rechaza.
        peticion = self.request
        ip = ip_del_cliente(peticion) if peticion is not None else None
        if ip and _captchas_rechazados_de(ip) >= settings.LOGIN_MAX_CAPTCHA_FALLIDOS_IP_HORA:
            logger.warning('Inicio de sesion rechazado: demasiados captchas fallidos desde una misma IP')
            raise forms.ValidationError(MENSAJE_LIMITE, code='limite')

        token = self.data.get('cf-turnstile-response', '')
        valido = bool(
            peticion is not None
            and verificar_turnstile_obligatorio(
                token, ip, accion=ACCION_LOGIN, hostname=split_domain_port(peticion.get_host())[0],
                timeout=settings.LOGIN_TURNSTILE_TIMEOUT_SEGUNDOS,
            )
        )
        if not valido:
            logger.warning('Inicio de sesion rechazado: el captcha no se pudo verificar')
            _anotar_rechazo(ip)
            raise forms.ValidationError(MENSAJE_CAPTCHA, code='captcha')
