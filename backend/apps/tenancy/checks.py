"""System checks de tenancy. Registrados desde apps.py::ready().

`revisar_rol_rls` es la guardia de arranque de ADR-001: si la app se conecta a
Postgres con un rol superusuario o con `BYPASSRLS`, las politicas RLS no
protegen nada y el aislamiento entre Empresas queda solo en el filtro del ORM,
en silencio. En produccion eso frena el deploy; en dev/CI es solo un aviso (ahi
el rol suele ser superusuario a proposito).
"""
from django.conf import settings
from django.core.checks import Error, Tags, Warning, register
from django.db.utils import DatabaseError, OperationalError

from .rls import rol_de_conexion_es_seguro

W001 = 'tenancy.W001'
E001 = 'tenancy.E001'

_HINT = (
    'Crea un rol dedicado sin privilegios para la app '
    '("CREATE ROLE app_pesca LOGIN NOSUPERUSER NOBYPASSRLS ..." + los GRANT '
    'minimos sobre el esquema) y apuntalo en DB_USER. Ver '
    'docs/deploy/RUNBOOK-corte-multi-empresa.md, seccion "Rol de aplicacion".'
)


@register(Tags.database)
def revisar_rol_rls(app_configs, **kwargs):
    try:
        seguro, detalle = rol_de_conexion_es_seguro()
    except (DatabaseError, OperationalError):
        # Corre durante collectstatic/migrate antes de que la base este lista;
        # y en `check --deploy` de CI, que no se conecta a ninguna base.
        return []

    if seguro:
        return []

    mensaje = (
        f'El rol de Postgres de la aplicacion ("{detalle.get("usuario")}") es '
        f'superusuario o tiene BYPASSRLS (rolsuper={detalle.get("rolsuper")}, '
        f'rolbypassrls={detalle.get("rolbypassrls")}): las politicas RLS de '
        f'tenancy NO aislan nada con este rol.'
    )

    # DEBUG=False => produccion (o `check --deploy`): Error, frena el deploy.
    if settings.DEBUG:
        return [Warning(mensaje, hint=_HINT, id=W001)]
    return [Error(mensaje, hint=_HINT, id=E001)]
