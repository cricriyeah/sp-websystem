from django.apps import AppConfig


class BookingsConfig(AppConfig):
    name = 'apps.bookings'
    label = 'bookings'

    def ready(self):
        # Importado por el efecto de registrar la señal del aviso de asignacion.
        from . import signals  # noqa: F401
