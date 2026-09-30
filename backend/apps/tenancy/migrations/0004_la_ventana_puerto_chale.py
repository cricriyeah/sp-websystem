from django.db import migrations


def actualizar_sedes(apps, schema_editor):
    Sede = apps.get_model('tenancy', 'Sede')
    sedes = Sede.objects.using(schema_editor.connection.alias)
    cabo = sedes.filter(slug='los-cabos').first()
    ventana = sedes.filter(slug='la-ventana').first()
    if cabo and ventana:
        raise RuntimeError('Existen los-cabos y la-ventana; conciliar las sedes antes de migrar.')
    if cabo:
        # Retain the primary key and all company/package/reservation relations.
        sedes.filter(pk=cabo.pk).update(nombre='La Ventana', slug='la-ventana')
    elif not ventana:
        sedes.create(nombre='La Ventana', slug='la-ventana', zona_horaria='America/Mazatlan', activo=True)
    sedes.get_or_create(
        slug='puerto-chale',
        defaults={'nombre': 'Puerto Chale', 'zona_horaria': 'America/Mazatlan', 'activo': True},
    )


class Migration(migrations.Migration):
    dependencies = [('tenancy', '0003_rls')]
    # No automatic reverse: deleting a destination could discard operational data.
    operations = [migrations.RunPython(actualizar_sedes)]
