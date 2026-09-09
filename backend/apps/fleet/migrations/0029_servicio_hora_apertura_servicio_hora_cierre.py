from datetime import time
from django.db import migrations, models


def set_ventana_pesca(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Servicio = apps.get_model('fleet', 'Servicio')
    with alcance_operador_migracion(schema_editor.connection):
        Servicio.objects.filter(tipo_servicio='pesca').update(
            hora_apertura=time(5, 0),
            hora_cierre=time(7, 0),
        )


def unset_ventana_pesca(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Servicio = apps.get_model('fleet', 'Servicio')
    with alcance_operador_migracion(schema_editor.connection):
        Servicio.objects.filter(tipo_servicio='pesca').update(
            hora_apertura=None,
            hora_cierre=None,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0028_servicio_capacidad_maxima'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicio',
            name='hora_apertura',
            field=models.TimeField(blank=True, help_text='Inicio de la ventana horaria de salida. Vacío = sin restricción.', null=True),
        ),
        migrations.AddField(
            model_name='servicio',
            name='hora_cierre',
            field=models.TimeField(blank=True, help_text='Fin de la ventana horaria de salida. Vacío = sin restricción.', null=True),
        ),
        migrations.RunPython(set_ventana_pesca, unset_ventana_pesca),
    ]

