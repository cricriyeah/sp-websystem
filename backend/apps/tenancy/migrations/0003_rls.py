from django.db import migrations

TABLAS_CON_EMPRESA_ID = [
    'fleet_tarifa', 'fleet_extrasitem', 'fleet_transporteprecio',
    'fleet_puntoencuentro', 'fleet_codigopromocional', 'fleet_embarcacion',
    'fleet_capitan', 'fleet_embarcacionnodisponible',
    'bookings_reserva', 'bookings_cupodiario', 'bookings_vendedora',
]

TABLAS_VIA_RESERVA = ['bookings_reservaextra', 'bookings_reservatransporte']

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

SQL_POLITICA_EXISTS_REVERSA = SQL_POLITICA_REVERSA


def aplicar_politicas(apps, schema_editor):
    # RunSQL corre incondicional contra cualquier backend que este migrando --
    # en local/tests (sqlite) este SQL es invalido por completo (sqlite no
    # tiene RLS). RunPython con guard de vendor deja la migracion como no-op
    # fuera de Postgres, sin bloquear `manage.py test`/desarrollo local.
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_CON_EMPRESA_ID:
            cursor.execute(SQL_POLITICA.format(tabla=tabla))
        for tabla in TABLAS_VIA_RESERVA:
            cursor.execute(SQL_POLITICA_EXISTS.format(tabla=tabla))


def revertir_politicas(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_CON_EMPRESA_ID:
            cursor.execute(SQL_POLITICA_REVERSA.format(tabla=tabla))
        for tabla in TABLAS_VIA_RESERVA:
            cursor.execute(SQL_POLITICA_EXISTS_REVERSA.format(tabla=tabla))


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0002_crear_sede_empresa_la_paz'),
        ('fleet', '0015_unicidad_por_empresa'),
        ('bookings', '0024_unicidad_por_empresa'),
    ]

    operations = [
        migrations.RunPython(aplicar_politicas, revertir_politicas),
    ]
