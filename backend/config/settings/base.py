"""
Settings comunes a todos los entornos (local y production heredan de aqui).
"""

import os
from pathlib import Path

from django.urls import reverse_lazy

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
    # Separador de miles en el panel de finanzas (filtro `intcomma`): una cifra
    # de seis digitos sin separar no se lee de un vistazo.
    'django.contrib.humanize',

    'rest_framework',
    'corsheaders',

    'apps.fleet',
    'apps.bookings',
    'apps.payments',
    'apps.notifications',
    'apps.finance',
]

REST_FRAMEWORK = {
    # API publica (web) sin login: la web nunca autentica, solo crea
    # reservas/pagos. El backoffice (admin) sigue protegido por su cuenta.
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    # Sin login no hay nada que frene a alguien que le pegue en bucle a estas
    # rutas: reservas basura que ensucian el panel y PaymentIntents en masa
    # contra la cuenta de Stripe. `ScopedRateThrottle` limita por IP solo las
    # vistas que declaran `throttle_scope` — el webhook de Stripe queda fuera a
    # proposito (ver apps/payments/views.py), sus rafagas de reintentos son
    # legitimas y frenarlas perderia cobros.
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.ScopedRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {
        # Crear/actualizar reserva y crear cobro: el checkout real reenvia unas
        # pocas veces por sesion, 20/min por IP no le estorba a nadie.
        'reservas': os.environ.get('THROTTLE_RESERVAS', '20/min'),
        'pagos': os.environ.get('THROTTLE_PAGOS', '20/min'),
        # Consultas de solo lectura: el calendario del checkout las dispara al
        # cambiar de dia, se toca mas seguido.
        'consulta': os.environ.get('THROTTLE_CONSULTA', '60/min'),
    },
}

# Cuantos proxies de confianza hay delante de la app. Define que posicion de
# `X-Forwarded-For` es creible (ver apps/bookings/serializers.py). 0 = sin proxy,
# se usa la IP de la conexion; production.py lo sube a 1 por el balanceador de
# Render. Nunca poner un numero mayor al de saltos reales: cada salto de mas es
# una posicion que el cliente puede escribir a mano.
TRUSTED_PROXY_COUNT = int(os.environ.get('TRUSTED_PROXY_COUNT', '0'))

# Cuenta estandar (no Stripe Connect), ver docs/contexto-negocio.md.
# Vacias en local hasta pegar llaves de prueba reales en el entorno.
# Version de la API de Stripe, explicita. La libreria ya manda una por su cuenta
# (la que trae `stripe.api_version`, hoy 2026-07-29.dahlia con stripe==15.4.0),
# asi que esto NO cambia el comportamiento actual — lo que cambia es de donde
# sale el numero. Sin fijarlo aqui, la version de la API viaja pegada a la
# version de la libreria: un `pip install -U stripe` la moveria en silencio, sin
# que aparezca en ningun diff que Stripe empezo a contestar con otro formato.
#
# Subirla es una decision aparte de actualizar la libreria: hay que leer el
# changelog de Stripe y probar. Ver docs/vendors/stripe.md.
STRIPE_API_VERSION = os.environ.get('STRIPE_API_VERSION', '2026-07-29.dahlia')

STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Confirmacion automatica al cliente (ver apps/notifications/services.py). Vacias
# en local: sin llaves no se manda nada y el cobro sigue funcionando igual.
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
RESEND_FROM = os.environ.get('RESEND_FROM', '')
# Copia oculta de cada confirmacion a una direccion del negocio. No es un
# respaldo, es un rastro fuera de la base: si algun dia hay que restaurar y se
# pierden las reservas de medio dia, en ese buzon queda a quien hay que hablarle
# para que nadie llegue al muelle sin que lo esperen (ver docs/vendors/supabase.md).
# Va en copia OCULTA a proposito: el cliente no tiene por que ver una direccion
# interna. Varias direcciones separadas por coma. Ojo al configurarla — una
# direccion equivocada aqui manda datos de clientes a un tercero.
RESEND_BCC = [c.strip() for c in os.environ.get('RESEND_BCC', '').split(',') if c.strip()]
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_TEMPLATE = os.environ.get('WHATSAPP_TEMPLATE', 'reserva_confirmada')
WHATSAPP_TEMPLATE_LANG = os.environ.get('WHATSAPP_TEMPLATE_LANG', 'es_MX')

# Config visual de unfold. El tema (colores, sidebar) se define aqui en codigo,
# no es editable en vivo desde el admin como admin_interface.
UNFOLD = {
    'SITE_TITLE': 'Sal y Sol Sportfishing',
    'SITE_HEADER': 'Sal y Sol Sportfishing',
    'SITE_SYMBOL': 'anchor',
    'SHOW_HISTORY': True,
    'SHOW_VIEW_ON_SITE': False,
    # El menu lateral se arma a mano porque el panel de finanzas no es un modelo
    # y no aparece solo. Cada item se filtra con el permiso del usuario: la
    # vendedora ve la operacion, los jefes ven ademas el dinero. Si se agrega un
    # modelo nuevo hay que darlo de alta aqui — mientras tanto sigue alcanzable
    # desde el menu "todas las aplicaciones" (`show_all_applications`).
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': True,
        'navigation': [
            {
                'title': 'Operacion',
                'items': [
                    {
                        'title': 'Reservas',
                        'icon': 'event',
                        'link': reverse_lazy('admin:bookings_reserva_changelist'),
                        'permission': lambda request: request.user.has_perm('bookings.view_reserva'),
                    },
                    {
                        'title': 'Checkouts abandonados',
                        'icon': 'remove_shopping_cart',
                        'link': reverse_lazy('admin:bookings_checkoutabandonado_changelist'),
                        'permission': lambda request: request.user.has_perm(
                            'bookings.view_checkoutabandonado'
                        ),
                    },
                    {
                        'title': 'Cupo diario',
                        'icon': 'event_busy',
                        'link': reverse_lazy('admin:bookings_cupodiario_changelist'),
                        'permission': lambda request: request.user.has_perm('bookings.view_cupodiario'),
                    },
                ],
            },
            {
                'title': 'Catalogo',
                'separator': True,
                'items': [
                    {
                        'title': 'Embarcaciones',
                        'icon': 'sailing',
                        'link': reverse_lazy('admin:fleet_embarcacion_changelist'),
                        'permission': lambda request: request.user.has_perm('fleet.view_embarcacion'),
                    },
                    {
                        'title': 'Capitanes',
                        'icon': 'badge',
                        'link': reverse_lazy('admin:fleet_capitan_changelist'),
                        'permission': lambda request: request.user.has_perm('fleet.view_capitan'),
                    },
                    {
                        'title': 'Vendedoras',
                        'icon': 'support_agent',
                        'link': reverse_lazy('admin:bookings_vendedora_changelist'),
                        'permission': lambda request: request.user.has_perm('bookings.view_vendedora'),
                    },
                ],
            },
            {
                # Solo jefes. La vendedora no ve este bloque completo, igual que
                # hoy no ve `fleet.Tarifa` (ver docs/contexto-negocio.md, Roles).
                'title': 'Dinero',
                'separator': True,
                'items': [
                    {
                        'title': 'Finanzas',
                        'icon': 'payments',
                        'link': reverse_lazy('finanzas'),
                        'permission': lambda request: request.user.is_superuser,
                    },
                    {
                        'title': 'Tarifa',
                        'icon': 'sell',
                        'link': reverse_lazy('admin:fleet_tarifa_changelist'),
                        'permission': lambda request: request.user.has_perm('fleet.view_tarifa'),
                    },
                ],
            },
            {
                'title': 'Sistema',
                'separator': True,
                'items': [
                    {
                        'title': 'Usuarios',
                        'icon': 'person',
                        'link': reverse_lazy('admin:auth_user_changelist'),
                        'permission': lambda request: request.user.has_perm('auth.view_user'),
                    },
                    {
                        'title': 'Grupos',
                        'icon': 'group',
                        'link': reverse_lazy('admin:auth_group_changelist'),
                        'permission': lambda request: request.user.has_perm('auth.view_group'),
                    },
                ],
            },
        ],
    },
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
    # Sirve los estaticos del admin (y de apps.bookings) en Render, que no tiene
    # un nginx delante. Va justo despues de SecurityMiddleware, como pide su doc.
    'whitenoise.middleware.WhiteNoiseMiddleware',
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

# Destino de `manage.py collectstatic`. Ignorado por git; en Render lo genera el
# build. En local no hace falta correrlo: con DEBUG=True el runserver sirve los
# estaticos directo desde cada app.
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
