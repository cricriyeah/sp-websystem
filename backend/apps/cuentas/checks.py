"""Avisos de arranque sobre el inicio de sesion del backoffice.

Son `Info`, no `Warning`: `check --deploy --fail-level WARNING` corre en CI sin llaves de Turnstile y no debe fallar.
Se ven en el registro del despliegue (`migrate` corre las verificaciones) para que nadie descubra por accidente que el
login quedo sin captcha.
"""
from django.conf import settings
from django.core import checks


@checks.register()
def login_sin_turnstile(app_configs, **kwargs):
    if settings.DEBUG:
        return []
    if not (settings.TURNSTILE_SECRET_KEY and settings.TURNSTILE_SITE_KEY):
        return [checks.Info(
            'El inicio de sesion del backoffice NO lleva Turnstile: faltan TURNSTILE_SECRET_KEY y/o TURNSTILE_SITE_KEY.',
            hint='Ponlas en Render (grupo pescadeportiva-secrets) y agrega el dominio del backend al widget.',
            id='cuentas.I001',
        )]
    if not settings.LOGIN_TURNSTILE_OBLIGATORIO:
        return [checks.Info(
            'Salida de emergencia activa: LOGIN_TURNSTILE_OBLIGATORIO=0, el login NO exige Turnstile.',
            hint='Vuelve a poner LOGIN_TURNSTILE_OBLIGATORIO=1 en cuanto se arregle lo que la hizo necesaria.',
            id='cuentas.I002',
        )]
    return []
