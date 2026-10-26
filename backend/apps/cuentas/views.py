"""Las dos pantallas de la recuperacion de contrasena: pedir el codigo y confirmarlo.

Montadas en `config/urls.py` antes de `admin/` con los nombres `admin_password_reset` (que es el que Unfold
busca para pintar «¿Olvidaste tu contraseña?» en el login) y `admin_password_reset_codigo`.

Reglas que no hay que romper:
- Turnstile obligatorio y cerrado en los dos pasos, con accion y hostname verificados.
- La respuesta del paso 1 es la misma para cualquier correo; el motivo real solo va a la bitacora.
- El bloque que toca cuentas va envuelto en `try/except`: sin eso, `ErrorInesperadoAdminMiddleware`
  (rutas `/admin/`) redirige distinto solo cuando la cuenta existe y se vuelve un oraculo de existencia.
  Se registra la clase del error y nada mas (ni mensaje ni traza: podrian llevar el codigo).
"""
import logging

from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponse
from django.http.request import split_domain_port
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.bookings.captcha import verificar_turnstile_obligatorio
from apps.bookings.ip_cliente import ip_del_cliente

from .forms import ConfirmarForm, SolicitarForm
from .servicio import confirmar_codigo, ip_excedida_confirmacion, ip_excedida_solicitud, solicitar_codigo

logger = logging.getLogger(__name__)

ACCION_SOLICITAR = 'recuperar_solicitar'
ACCION_CONFIRMAR = 'recuperar_confirmar'

TEXTO_NEUTRO = 'Si el correo corresponde a una cuenta activa, te enviamos un código de 6 dígitos. Vence en 10 minutos.'
TEXTO_SIN_CAPTCHA = 'No pudimos verificar que eres una persona, inténtalo de nuevo'
TEXTO_CODIGO_MALO = 'El código es incorrecto o ya venció. Si fallaste varias veces, pide uno nuevo'
TEXTO_DEMASIADOS = 'Demasiados intentos desde tu conexión. Espera un rato e inténtalo de nuevo.'
TEXTO_NO_DISPONIBLE = 'Recuperación no disponible, pide a tu jefe que cambie tu contraseña'


def _disponible():
    """Sin Turnstile (las dos llaves) o sin Resend la recuperacion no se ofrece: cierra, no deja pasar."""
    return all((
        settings.TURNSTILE_SITE_KEY, settings.TURNSTILE_SECRET_KEY, settings.RESEND_API_KEY, settings.RESEND_FROM,
    ))


def _pagina(request, plantilla, status=200, **contexto):
    contexto = {
        **admin.site.each_context(request),
        'turnstile_site_key': settings.TURNSTILE_SITE_KEY,
        'login_url': reverse('admin:login'),
        'pedir_url': reverse('admin_password_reset'),
        **contexto,
    }
    return render(request, plantilla, contexto, status=status)


def _hostname(request):
    return split_domain_port(request.get_host())[0]


def _captcha_ok(request, ip, accion):
    token = request.POST.get('cf-turnstile-response', '')
    return verificar_turnstile_obligatorio(token, ip, accion=accion, hostname=_hostname(request))


@require_http_methods(['GET', 'POST'])
@never_cache
@sensitive_post_parameters()
def solicitar(request):
    """Paso 1: pide el correo y, si corresponde a una cuenta recuperable, manda el codigo."""
    if request.user.is_authenticated:
        return redirect('admin:index')
    if not _disponible():
        return _pagina(request, 'cuentas/recuperar_solicitar.html', 503, aviso=TEXTO_NO_DISPONIBLE, titulo='Recuperar contraseña')
    if request.method == 'GET':
        return _pagina(request, 'cuentas/recuperar_solicitar.html', form=SolicitarForm(), titulo='Recuperar contraseña')

    ip = ip_del_cliente(request)
    if ip_excedida_solicitud(ip):
        return _pagina(
            request, 'cuentas/recuperar_solicitar.html', 429, form=SolicitarForm(), error=TEXTO_DEMASIADOS,
            titulo='Recuperar contraseña',
        )
    if not _captcha_ok(request, ip, ACCION_SOLICITAR):
        return _pagina(
            request, 'cuentas/recuperar_solicitar.html', 400, form=SolicitarForm(request.POST), error=TEXTO_SIN_CAPTCHA,
            titulo='Recuperar contraseña',
        )
    form = SolicitarForm(request.POST)
    if not form.is_valid():
        return _pagina(request, 'cuentas/recuperar_solicitar.html', 400, form=form, titulo='Recuperar contraseña')

    try:
        solicitar_codigo(form.cleaned_data['correo'], ip)
    except Exception as exc:  # excepcion deliberada: ver el docstring del modulo (oraculo de existencia)
        logger.error('Fallo inesperado al pedir un codigo de recuperacion (%s)', type(exc).__name__)

    return _pagina(
        request, 'cuentas/recuperar_codigo.html', form=ConfirmarForm(initial={'correo': form.cleaned_data['correo']}),
        aviso=TEXTO_NEUTRO, titulo='Escribe tu código',
    )


@require_http_methods(['GET', 'POST'])
@never_cache
@sensitive_post_parameters()
def confirmar(request):
    """Paso 2: correo, codigo y contrasena nueva en un solo envio."""
    if request.user.is_authenticated:
        return redirect('admin:index')
    if not _disponible():
        return _pagina(request, 'cuentas/recuperar_codigo.html', 503, aviso=TEXTO_NO_DISPONIBLE, titulo='Escribe tu código')
    if request.method == 'GET':
        return _pagina(request, 'cuentas/recuperar_codigo.html', form=ConfirmarForm(), titulo='Escribe tu código')

    ip = ip_del_cliente(request)
    if ip_excedida_confirmacion(ip):
        return _pagina(
            request, 'cuentas/recuperar_codigo.html', 429, form=ConfirmarForm(), error=TEXTO_DEMASIADOS,
            titulo='Escribe tu código',
        )
    if not _captcha_ok(request, ip, ACCION_CONFIRMAR):
        return _pagina(
            request, 'cuentas/recuperar_codigo.html', 400, form=ConfirmarForm(request.POST), error=TEXTO_SIN_CAPTCHA,
            titulo='Escribe tu código',
        )
    form = ConfirmarForm(request.POST)
    if not form.is_valid():
        return _pagina(request, 'cuentas/recuperar_codigo.html', 400, form=form, titulo='Escribe tu código')

    correo = form.cleaned_data['correo']
    try:
        # Sin variable local con el codigo ni la contrasena: Sentry adjunta las locales de un frame que falle.
        resultado = confirmar_codigo(
            correo, form.cleaned_data['codigo'], form.cleaned_data['password1'], ip,
        )
    except Exception as exc:  # excepcion deliberada: ver el docstring del modulo
        logger.error('Fallo inesperado al confirmar un codigo de recuperacion (%s)', type(exc).__name__)
        resultado = None

    if resultado is not None and resultado.exito:
        messages.success(request, 'Tu contraseña cambió. Ya puedes iniciar sesión con la nueva.')
        return redirect('admin:login')
    if resultado is not None and resultado.errores:
        for mensaje in resultado.errores:
            form.add_error('password1', mensaje)
        return _pagina(request, 'cuentas/recuperar_codigo.html', 400, form=form, titulo='Escribe tu código')
    return _pagina(
        request, 'cuentas/recuperar_codigo.html', 400, form=ConfirmarForm(initial={'correo': correo}),
        error=TEXTO_CODIGO_MALO, titulo='Escribe tu código',
    )
