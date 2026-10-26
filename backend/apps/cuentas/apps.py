from django.apps import AppConfig


class CuentasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cuentas'
    label = 'cuentas'
    verbose_name = 'Cuentas'

    def ready(self):
        from . import checks  # noqa: F401  (registra las verificaciones de arranque)
