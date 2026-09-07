"""Migración RLS de PostgreSQL para ReservaPaqueteServicioRemovido y ReservaPaquetePersonalizacion."""

from django.db import migrations

TABLAS_VIA_RESERVA = [
    'bookings_reservapaqueteservicioremovido',
    'bookings_reservapaquetepersonalizacion',
]

SQL_POLITICA_EXISTS = """
ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenancy_alcance ON {tabla}
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM bookings_reserva r
    WHERE r.id = {tabla}.reserva_id
      AND (r.empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
           OR current_setting('app.operador_plataforma', true) = 'on')
  )
);
"""

SQL_POLITICA_REVERSA = """
DROP POLICY IF EXISTS tenancy_alcance ON {tabla};
ALTER TABLE {tabla} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY;
"""


def aplicar_politicas(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_VIA_RESERVA:
            cursor.execute(SQL_POLITICA_EXISTS.format(tabla=tabla))


def revertir_politicas(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_VIA_RESERVA:
            cursor.execute(SQL_POLITICA_REVERSA.format(tabla=tabla))


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0031_checkout_paquete'),
    ]

    operations = [
        migrations.RunPython(aplicar_politicas, revertir_politicas),
    ]
