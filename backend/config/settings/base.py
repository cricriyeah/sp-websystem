"""
Settings comunes a todos los entornos (local y production heredan de aqui).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    # unfold debe ir antes que django.contrib.admin (requisito del paquete,
    # sobreescribe sus templates).
    'unfold',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',

    'apps.fleet',
    'apps.bookings',
    'apps.payments',
]

REST_FRAMEWORK = {
    # API publica (web) sin login: la web nunca autentica, solo crea
    # reservas/pagos. El backoffice (admin) sigue protegido por su cuenta.
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
}

# Cuenta estandar (no Stripe Connect), ver docs/contexto-negocio.md.
# Vacias en local hasta pegar llaves de prueba reales en el entorno.
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Config visual de unfold. El tema (colores, sidebar) se define aqui en codigo,
# no es editable en vivo desde el admin como admin_interface.
UNFOLD = {
    'SITE_TITLE': 'Sal y Sol Sportfishing',
    'SITE_HEADER': 'Sal y Sol Sportfishing',
    'SITE_SYMBOL': 'anchor',
    'SHOW_HISTORY': True,
    'SHOW_VIEW_ON_SITE': False,
    'COLORS': {
        'primary': {
            '50': '255 247 237', '100': '255 237 213', '200': '254 215 170',
            '300': '253 186 116', '400': '251 146 60', '500': '234 88 12',
            '600': '194 65 12', '700': '154 52 18', '800': '124 45 18',
            '900': '124 45 18', '950': '67 20 7',
        },
    },
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# El panel operativo lo usan jefes y vendedora en español; el idioma es/en
# de este bloque es solo el de Django admin, no el de la web publica.
LANGUAGE_CODE = 'es-mx'

TIME_ZONE = 'America/Mazatlan'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
