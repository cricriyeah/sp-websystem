"""
Settings de desarrollo local. sqlite, DEBUG on, sin necesidad de variables de entorno.
"""

from .base import *  # noqa: F401,F403

SECRET_KEY = 'django-insecure-local-dev-only-change-me'

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
