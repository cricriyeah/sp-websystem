"""Settings SOLO para sembrar datos de demo en el entorno de QA (Render + Supabase).

Los comandos `seed_local_demo`, `seed_catalogo_real` y `seed_perfiles_demo` se
niegan a correr con DEBUG=False para que nadie los lance contra produccion por
error. En QA, que no tiene clientes ni dinero real, si se quieren correr: este
modulo es produccion con DEBUG encendido, y se usa SOLO para esos comandos:

    DJANGO_SETTINGS_MODULE=config.settings.qa_seed python manage.py seed_local_demo

NUNCA se pone como DJANGO_SETTINGS_MODULE de un servicio: el servicio web y los
cron siguen con `config.settings.production`.
"""

from .production import *  # noqa: F401,F403

DEBUG = True
