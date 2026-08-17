from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = 'apps.payments'
    label = 'payments'

    def ready(self):
        # Registra el check de las llaves de Stripe. El import es el que corre el
        # `@register()`, por eso va aqui y no arriba del archivo.
        from . import checks  # noqa: F401
