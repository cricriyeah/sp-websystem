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
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Comprime y le pone hash al nombre de cada estatico para poder cachearlos para
# siempre. Solo aqui: exige haber corrido collectstatic, asi que en local
# rompería el admin. Build de Render: `pip install -r requirements.txt &&
# python manage.py collectstatic --noinput && python manage.py migrate`.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
