import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('bookings', '0044_rls_orden_sin_current_query'),
        ('fleet', '0030_personalizacion_tipo_interaccion'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ReservaPaquetePersonalizacion',
            new_name='ReservaPersonalizacion',
        ),
        migrations.AlterField(
            model_name='reservapersonalizacion',
            name='reserva',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='personalizaciones_seleccionadas',
                to='bookings.reserva',
            ),
        ),
        migrations.AddField(
            model_name='reservapersonalizacion',
            name='respuesta',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='reservapersonalizacion',
            name='precio_unitario',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AlterModelOptions(
            name='reservapersonalizacion',
            options={
                'verbose_name': 'personalización de reserva',
                'verbose_name_plural': 'personalizaciones de reserva',
            },
        ),
    ]
