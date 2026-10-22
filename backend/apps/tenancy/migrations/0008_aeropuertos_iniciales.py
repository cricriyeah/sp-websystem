from django.db import migrations

from apps.tenancy.rls import alcance_operador_migracion

# Los aeropuertos de la Baja que se pueden elegir (el dueño confirmó que son estos cuatro; antes eran dos fijos
# en el código). Se dan de alta cubriendo TODAS las sedes que ya existen: en la Baja se llega a cualquiera sin
# importar la distancia. El operador puede quitar la cobertura de una sede en el admin.
INICIALES = (
    ('lap', 'La Paz (LAP)'),
    ('csl', 'Cabo San Lucas (CSL)'),
    ('sjd', 'San José del Cabo (SJD)'),
    ('lto', 'Loreto (LTO)'),
)


def sembrar(apps, schema_editor):
    Aeropuerto = apps.get_model('tenancy', 'Aeropuerto')
    Sede = apps.get_model('tenancy', 'Sede')
    with alcance_operador_migracion(schema_editor.connection):
        sedes = list(Sede.objects.all())
        for codigo, nombre in INICIALES:
            aeropuerto, _ = Aeropuerto.objects.update_or_create(codigo=codigo, defaults={'nombre': nombre})
            aeropuerto.sedes.add(*sedes)


class Migration(migrations.Migration):
    dependencies = [('tenancy', '0007_aeropuerto')]
    # Sin reversa automática: borrar aeropuertos podría descartar la cobertura que el operador ya ajustó.
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]
