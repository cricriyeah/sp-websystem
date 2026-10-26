"""Politica RLS de PostgreSQL para tenancy_notificacion y tenancy_lecturanotificacion.

Copia del patron de bookings/0065_rls_movimientodinero.py: las dos tablas llevan `empresa_id` (la de lecturas esta
denormalizada justo para esto) y cada empresa solo ve lo suyo; el operador de plataforma ve todo. No hay data
migration que cree filas, asi que no hace falta `alcance_operador_migracion`.
"""

from django.db import migrations

TABLAS_CON_EMPRESA_ID = ['tenancy_notificacion', 'tenancy_lecturanotificacion']

SQL_POLITICA = """
ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenancy_alcance ON {tabla}
FOR ALL
USING (
  empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
  OR current_setting('app.operador_plataforma', true) = 'on'
);
"""

SQL_POLITICA_REVERSA = """
DROP POLICY IF EXISTS tenancy_alcance ON {tabla};
ALTER TABLE {tabla} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY;
"""


def aplicar_politicas_notificacion(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_CON_EMPRESA_ID:
            cursor.execute(SQL_POLITICA.format(tabla=tabla))


def revertir_politicas_notificacion(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_CON_EMPRESA_ID:
            cursor.execute(SQL_POLITICA_REVERSA.format(tabla=tabla))


class Migration(migrations.Migration):

    dependencies = [('tenancy', '0010_notificacion')]

    operations = [
        migrations.RunPython(aplicar_politicas_notificacion, revertir_politicas_notificacion),
    ]
