"""Migración RLS de PostgreSQL para bookings_reservaocupacion."""

from django.db import migrations

TABLAS_CON_EMPRESA_ID = [
    'bookings_reservaocupacion',
]

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


def aplicar_politicas_ocupacion(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_CON_EMPRESA_ID:
            cursor.execute(SQL_POLITICA.format(tabla=tabla))


def revertir_politicas_ocupacion(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_CON_EMPRESA_ID:
            cursor.execute(SQL_POLITICA_REVERSA.format(tabla=tabla))


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0026_reserva_ocupacion'),
    ]

    operations = [
        migrations.RunPython(aplicar_politicas_ocupacion, revertir_politicas_ocupacion),
    ]
