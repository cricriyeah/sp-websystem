from django.db import migrations


def asignar_empresa(apps, schema_editor):
    Empresa = apps.get_model('tenancy', 'Empresa')
    empresa = Empresa.objects.get(slug='sal-y-sol')

    for nombre_modelo in (
        'Tarifa', 'ExtrasItem', 'TransportePrecio', 'PuntoEncuentro',
        'CodigoPromocional', 'Embarcacion', 'Capitan', 'EmbarcacionNoDisponible',
    ):
        Modelo = apps.get_model('fleet', nombre_modelo)
        Modelo.objects.filter(empresa__isnull=True).update(empresa=empresa)


def revertir(apps, schema_editor):
    for nombre_modelo in (
        'Tarifa', 'ExtrasItem', 'TransportePrecio', 'PuntoEncuentro',
        'CodigoPromocional', 'Embarcacion', 'Capitan', 'EmbarcacionNoDisponible',
    ):
        Modelo = apps.get_model('fleet', nombre_modelo)
        Modelo.objects.update(empresa=None)


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0012_empresa_nullable'),
        ('tenancy', '0002_crear_sede_empresa_la_paz'),
    ]

    operations = [
        migrations.RunPython(asignar_empresa, revertir),
    ]
