from django.db import migrations

from apps.tenancy.rls import alcance_operador_migracion

# Los aeropuertos de la Baja: el dueño confirmó que estos cuatro son los únicos que existen (antes eran dos fijos
# en el código). Se dan de alta cubriendo todas las sedes que ya existen, que es lo que el sitio ofrecía hasta
# ahora; el operador ajusta en el admin qué sedes tienen traslado a cada uno.
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
