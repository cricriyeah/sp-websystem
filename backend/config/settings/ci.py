"""Settings para correr la suite contra Postgres en CI.

Existe por F-20: los 139 tests siempre habian corrido en sqlite, que es el motor
de desarrollo, nunca contra el de produccion. No es una diferencia cosmetica —
sqlite serializa toda escritura con un solo escritor, asi que **cualquier
condicion de carrera es invisible ahi por construccion**. F-19 (sobreventa de
cupo con dos pagos simultaneos) es exactamente eso: imposible de reproducir en
sqlite, real en Postgres.

Hereda de `local` (misma SECRET_KEY de desarrollo, mismo CORS) y solo cambia la
base. No hereda de `production` a proposito: ahi vive SECURE_SSL_REDIRECT, que
haria que cada peticion de prueba respondiera 301.
"""
import os

from .local import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'pescadeportiva_test'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}
