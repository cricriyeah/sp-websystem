"""
Settings de produccion (Render + Supabase Postgres). Todo viene de variables de entorno.
"""

import os

from .base import *  # noqa: F401,F403

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

DEBUG = False

ALLOWED_HOSTS = [h for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if h]

# URL(s) del frontend en Vercel, ver docs/contexto-negocio.md.
CORS_ALLOWED_ORIGINS = [o for o in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if o]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Render termina el TLS en su proxy y nos reenvia la peticion como HTTP plano. Sin
# esto Django no la reconoce como segura, SECURE_SSL_REDIRECT redirige a https, el
# proxy vuelve a reenviar en plano y el sitio entero entra en loop de redirects.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True

# La sonda de salud queda exenta del redirect a https. Si el sondeo interno de
# Render llegara sin `X-Forwarded-Proto`, Django le responderia un 301 y el
# balanceador lo leeria como servicio caido — tumbando un deploy sano por una
# cuestion de protocolo. No expone nada: /healthz no devuelve datos (ver
# config/health.py). El patron va sin barra inicial, que es como Django lo compara.
SECURE_REDIRECT_EXEMPT = [r'^healthz$']
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Un salto: el balanceador de Render. Marca que posicion de `X-Forwarded-For` es
# creible para la constancia del deslinde (ver apps/bookings/serializers.py).
# Subirlo solo si de verdad se mete otro proxy/CDN delante.
TRUSTED_PROXY_COUNT = int(os.environ.get('TRUSTED_PROXY_COUNT', '1'))

# HSTS: le dice al navegador "de aqui en adelante entra solo por https", lo que
# cierra la ventana de downgrade que deja el redirect de arriba en la segunda
# visita. Arranca en 1 hora a proposito — el navegador **recuerda** este valor y
# no hay forma de retirarlo antes de que expire, asi que un año puesto sobre un
# dominio que todavia se esta moviendo puede dejarlo inalcanzable. Subir a
# 31536000 (via env var, sin tocar codigo) despues de un par de dias sirviendo
# https estable. `preload` se queda fuera: entrar a la lista de Chrome es un
# tramite aparte y salir de ella tarda meses.
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# `check --deploy` corre en CI con --fail-level WARNING para que una regresion de
# configuracion no llegue a produccion. W021 (falta SECURE_HSTS_PRELOAD) se
# silencia porque no es un descuido: ver el bloque de HSTS de arriba. Nada mas
# debe entrar a esta lista sin una razon escrita al lado.
SILENCED_SYSTEM_CHECKS = ['security.W021']

# Sin esto los `logger.exception(...)` de apps/payments se los traga el default de
# Django y no llegan al log de Render: un webhook fallando en silencio es
# exactamente el caso que hay que poder ver. Nivel INFO en las apps propias,
# WARNING en el resto para que el ruido de Django no tape lo que importa.
# Alertas de error. Sin `SENTRY_DSN` no se inicializa nada y el backend se
# comporta igual que antes — como Stripe y Resend, la funcion se enciende sola
# cuando su variable existe, y su ausencia no rompe el arranque.
#
# Existe porque hasta ahora un fallo solo dejaba rastro en el log de Render, que
# es un archivo que nadie abre sin motivo. El caso que importa es el webhook de
# Stripe: si empieza a fallar, el dinero entra y las reservas no se marcan
# pagadas — y eso se descubria por reclamo del cliente.
#
# El DSN no es un secreto del mismo tipo que una llave de Stripe: sirve para
# *mandar* errores, no para leerlos. Aun asi va por variable de entorno, por
# consistencia y porque no gana nada estando en el repo.
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')

if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        # Solo errores. El tracing de rendimiento se come la cuota gratuita
        # (5,000 eventos/mes) sin dar nada a cambio a este volumen.
        traces_sample_rate=0,
        # NO mandar cuerpos de peticion ni cookies: por estas rutas viajan
        # telefono, correo y la constancia del deslinde. Un error de pago no debe
        # convertirse en una copia de datos de clientes en un tercero.
        send_default_pii=False,
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
        # Para saber que version fallo. Render lo expone solo.
        release=os.environ.get('RENDER_GIT_COMMIT', ''),
    )

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'consola': {'format': '{levelname} {asctime} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'consola': {'class': 'logging.StreamHandler', 'formatter': 'consola'},
    },
    'root': {'handlers': ['consola'], 'level': 'WARNING'},
    'loggers': {
        'apps': {'handlers': ['consola'], 'level': 'INFO', 'propagate': False},
        'django.request': {'handlers': ['consola'], 'level': 'WARNING', 'propagate': False},
    },
}

# Comprime y le pone hash al nombre de cada estatico para poder cachearlos para
# siempre. Solo aqui: exige haber corrido collectstatic, asi que en local
# rompería el admin. Build de Render: `pip install -r requirements.txt &&
# python manage.py collectstatic --noinput && python manage.py migrate`.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
