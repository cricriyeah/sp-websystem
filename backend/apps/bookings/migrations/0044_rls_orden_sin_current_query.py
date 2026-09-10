"""Migración RLS de PostgreSQL para eliminar el bypass por current_query() en bookings_orden."""

from django.db import migrations

SQL_POLITICA_ORDEN_ESTRICTA = """
DROP POLICY IF EXISTS tenancy_alcance ON bookings_orden;

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
)
WITH CHECK (
  current_setting('app.operador_plataforma', true) = 'on'
  OR EXISTS (SELECT 1 FROM tenancy_sede s WHERE s.id = bookings_orden.sede_id)
);
"""

SQL_POLITICA_ORDEN_REVERSA = """
DROP POLICY IF EXISTS tenancy_alcance ON bookings_orden;

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


def aplicar_politica(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_POLITICA_ORDEN_ESTRICTA)


def revertir_politica(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_POLITICA_ORDEN_REVERSA)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0043_estado_reservas_de_orden'),
    ]

    operations = [
        migrations.RunPython(aplicar_politica, revertir_politica),
    ]
