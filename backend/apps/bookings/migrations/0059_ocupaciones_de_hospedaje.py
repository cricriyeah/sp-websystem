from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0058_viajes_transporte_existentes'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='reservaocupacion',
            options={
                'ordering': ['fecha_inicio', 'recurso'],
                'verbose_name': 'ocupación de recurso',
                'verbose_name_plural': 'ocupaciones de hospedaje',
            },
        ),
    ]
