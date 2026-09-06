"""Verificacion del rol de conexion de Postgres para RLS.

Las politicas RLS de tenancy (0003_rls y las de piezas 3/4/5) solo protegen si
el rol con el que la app se conecta a Postgres NO es superusuario y NO tiene
BYPASSRLS. Supabase entrega por defecto roles (`postgres`, `service_role`) con
BYPASSRLS; `FORCE ROW LEVEL SECURITY` tampoco protege contra eso. Un deploy con
el rol equivocado deja todo el aislamiento de ADR-001 sin efecto, en silencio.
"""
from contextlib import contextmanager

from django.db import connection


@contextmanager
def alcance_operador_migracion(conn):
    """`SET LOCAL app.operador_plataforma = 'on'` para data migrations que crean
    o modifican filas tenant-scoped via ORM.

    Las politicas RLS usan `WITH CHECK = USING`; sin esto, un `INSERT` desde una
    data migration corriendo con un rol `NOBYPASSRLS` (el correcto para
    produccion, y el de CI) es rechazado con «new row violates row-level
    security policy» porque `app.current_empresa_id` no esta seteado. La bandera
    de operador hace pasar tanto `USING` como `WITH CHECK` para cualquier
    `empresa_id`. `SET LOCAL` se limita a la transaccion de la migracion. No-op
    fuera de Postgres.
    """
    if conn.vendor != 'postgresql':
        yield
        return
    with conn.cursor() as cursor:
        cursor.execute("SET LOCAL app.operador_plataforma = 'on'")
        yield


def rol_de_conexion_es_seguro(conn=None):
    """Devuelve `(seguro: bool, detalle: dict)`.

    En un backend que no sea Postgres devuelve `(True, {...})`: RLS no aplica
    ahi y la app se apoya en el filtro del ORM. En Postgres consulta
    `pg_roles` para el `current_user` y considera seguro solo un rol que no es
    superusuario y no tiene `rolbypassrls`.
    """
    conn = conn or connection
    if conn.vendor != 'postgresql':
        return True, {'vendor': conn.vendor}

    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT current_user, rolsuper, rolbypassrls '
            'FROM pg_roles WHERE rolname = current_user'
        )
        fila = cursor.fetchone()

    if fila is None:
        return False, {'usuario': None, 'motivo': 'rol no encontrado en pg_roles'}

    usuario, rolsuper, rolbypassrls = fila
    seguro = not rolsuper and not rolbypassrls
    return seguro, {
        'usuario': usuario,
        'rolsuper': bool(rolsuper),
        'rolbypassrls': bool(rolbypassrls),
    }
