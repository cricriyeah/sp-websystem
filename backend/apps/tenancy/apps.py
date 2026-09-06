from django.apps import AppConfig
from django.core.signals import request_started
from django.db import connection


class TenancyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenancy'
    label = 'tenancy'

    def ready(self):
        # El import corre el @register() de los system checks (rol de BD para RLS).
        from . import checks  # noqa: F401

        def _limpiar_alcance_huerfano(sender, **kwargs):
            # Revision 7 (N7-C): django.test.Client dispara esta señal dentro de
            # una transaccion de test (_pre_setup abre con_empresa) -- sin el
            # guard, borraria la bandera a mitad de esa transaccion y rompería
            # la garantia de no-reentrancia. En produccion, request_started
            # siempre ocurre en autocommit (fuera de cualquier con_empresa), asi
            # que el guard no le quita nada a la red de seguridad real.
            if not connection.in_atomic_block:
                connection.alcance_actual = None

        request_started.connect(
            _limpiar_alcance_huerfano, dispatch_uid='tenancy_limpiar_alcance_huerfano'
        )
