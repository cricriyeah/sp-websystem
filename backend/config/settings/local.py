"""
Settings de desarrollo local. sqlite, DEBUG on. Variables opcionales (Stripe)
se leen de backend/.env si existe.
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

from .base import *  # noqa: F401,F403,E402

SECRET_KEY = 'django-insecure-local-dev-only-change-me'

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Next.js dev server (frontend/), ver frontend/package.json.
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
