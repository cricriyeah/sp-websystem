from django.db import migrations

SQL_POLITICA_PAQUETE = """
ALTER TABLE fleet_paquete ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleet_paquete FORCE ROW LEVEL SECURITY;
CREATE POLICY tenancy_alcance ON fleet_paquete
FOR ALL
USING (
  empresa_lider_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
  OR current_setting('app.operador_plataforma', true) = 'on'
);
"""

SQL_POLITICA_PAQUETE_REVERSA = """
DROP POLICY IF EXISTS tenancy_alcance ON fleet_paquete;
ALTER TABLE fleet_paquete NO FORCE ROW LEVEL SECURITY;
ALTER TABLE fleet_paquete DISABLE ROW LEVEL SECURITY;
"""

SQL_POLITICA_PAQUETESERVICIO = """
ALTER TABLE fleet_paqueteservicio ENABLE ROW LEVEL SECURITY;
ALTER TABLE fleet_paqueteservicio FORCE ROW LEVEL SECURITY;
CREATE POLICY tenancy_alcance ON fleet_paqueteservicio
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM fleet_paquete p
    WHERE p.id = fleet_paqueteservicio.paquete_id
      AND (p.empresa_lider_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
           OR current_setting('app.operador_plataforma', true) = 'on')
  )
);
"""

SQL_POLITICA_PAQUETESERVICIO_REVERSA = """
DROP POLICY IF EXISTS tenancy_alcance ON fleet_paqueteservicio;
ALTER TABLE fleet_paqueteservicio NO FORCE ROW LEVEL SECURITY;
ALTER TABLE fleet_paqueteservicio DISABLE ROW LEVEL SECURITY;
"""


def aplicar_politicas_paquetes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_POLITICA_PAQUETE)
        cursor.execute(SQL_POLITICA_PAQUETESERVICIO)


def revertir_politicas_paquetes(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_POLITICA_PAQUETE_REVERSA)
        cursor.execute(SQL_POLITICA_PAQUETESERVICIO_REVERSA)


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0019_paquetes'),
    ]

    operations = [
        migrations.RunPython(aplicar_politicas_paquetes, revertir_politicas_paquetes),
    ]
