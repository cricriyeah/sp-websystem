from django.db import migrations


def aplicar_constraint_exclude(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
        cursor.execute("""
            ALTER TABLE bookings_reservaocupacion ADD CONSTRAINT ocupacion_sin_traslape
              EXCLUDE USING gist (
                recurso_id WITH =,
                daterange(fecha_inicio, fecha_fin, '[)') WITH &&
              ) WHERE (ocupa_cupo);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ocupacion_recurso_rango
              ON bookings_reservaocupacion (recurso_id, fecha_inicio, fecha_fin);
        """)


def revertir_constraint_exclude(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE bookings_reservaocupacion DROP CONSTRAINT IF EXISTS ocupacion_sin_traslape;")
        cursor.execute("DROP INDEX IF EXISTS idx_ocupacion_recurso_rango;")


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0029_reservaocupacion_ocupa_cupo'),
    ]

    operations = [
        migrations.RunPython(aplicar_constraint_exclude, revertir_constraint_exclude),
    ]
