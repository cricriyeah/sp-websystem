from django.db import migrations

TABLAS_CATALOGO_CON_EMPRESA_ID = [
    'fleet_servicio',
    'fleet_recurso',
    'fleet_personalizacion',
]

TABLAS_CATALOGO_VIA_SERVICIO = [
    'fleet_serviciopersonalizacion',
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

SQL_POLITICA_EXISTS = """
ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenancy_alcance ON {tabla}
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM fleet_servicio s
    WHERE s.id = {tabla}.servicio_id
      AND (s.empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
           OR current_setting('app.operador_plataforma', true) = 'on')
  )
);
"""

SQL_POLITICA_EXISTS_REVERSA = SQL_POLITICA_REVERSA


def aplicar_politicas_catalogo(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_CATALOGO_CON_EMPRESA_ID:
            cursor.execute(SQL_POLITICA.format(tabla=tabla))
        for tabla in TABLAS_CATALOGO_VIA_SERVICIO:
            cursor.execute(SQL_POLITICA_EXISTS.format(tabla=tabla))


def revertir_politicas_catalogo(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for tabla in TABLAS_CATALOGO_CON_EMPRESA_ID:
            cursor.execute(SQL_POLITICA_REVERSA.format(tabla=tabla))
        for tabla in TABLAS_CATALOGO_VIA_SERVICIO:
            cursor.execute(SQL_POLITICA_EXISTS_REVERSA.format(tabla=tabla))


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0016_catalogo_capas'),
    ]

    operations = [
        migrations.RunPython(aplicar_politicas_catalogo, revertir_politicas_catalogo),
    ]
