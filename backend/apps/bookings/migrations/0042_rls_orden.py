"""Migración RLS de PostgreSQL para bookings_orden (sede-scoped con INSERT público)."""

from django.db import migrations

SQL_POLITICA_ORDEN = """
ALTER TABLE bookings_orden ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings_orden FORCE ROW LEVEL SECURITY;

CREATE POLICY tenancy_alcance ON bookings_orden
FOR ALL
USING (
  current_setting('app.operador_plataforma', true) = 'on'
  OR (
    sede_id = (
      SELECT sede_id FROM tenancy_empresa
      WHERE id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
    )
  )
  OR current_query() ~* '^\\s*INSERT'
)
WITH CHECK (
  current_setting('app.operador_plataforma', true) = 'on'
  OR EXISTS (SELECT 1 FROM tenancy_sede s WHERE s.id = bookings_orden.sede_id)
);
"""

SQL_REVERSA_ORDEN = """
DROP POLICY IF EXISTS tenancy_alcance ON bookings_orden;
ALTER TABLE bookings_orden NO FORCE ROW LEVEL SECURITY;
ALTER TABLE bookings_orden DISABLE ROW LEVEL SECURITY;
"""


def aplicar_politicas(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_POLITICA_ORDEN)


def revertir_politicas(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_REVERSA_ORDEN)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0041_orden'),
        ('tenancy', '0003_rls'),
    ]

    operations = [
        migrations.RunPython(aplicar_politicas, revertir_politicas),
    ]
