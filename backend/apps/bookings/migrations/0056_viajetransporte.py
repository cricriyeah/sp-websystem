"""Agrega ViajeTransporte a la app bookings."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0055_apartado_cupo'),
        ('fleet', '0047_vehiculo_vehiculonodisponible'),
        ('tenancy', '0004_la_ventana_puerto_chale'),
    ]

    operations = [
        migrations.CreateModel(
            name='ViajeTransporte',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sentido', models.CharField(
                    choices=[('unico', 'Unico'), ('ida', 'Ida'), ('regreso', 'Regreso')],
                    max_length=10,
                )),
                ('fecha', models.DateField()),
                ('hora', models.TimeField(
                    blank=True, null=True,
                    help_text='Hora de recogida. Vacia en el regreso hasta que la vendedora la capture.',
                )),
                ('cancelado', models.BooleanField(default=False)),
                ('empresa', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='viajes_transporte',
                    to='tenancy.empresa',
                )),
                ('reserva', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='viajes_transporte',
                    to='bookings.reserva',
                )),
                ('vehiculo', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='viajes',
                    to='fleet.vehiculo',
                )),
            ],
            options={
                'verbose_name': 'viaje de transporte',
                'verbose_name_plural': 'viajes de transporte',
                'ordering': ['fecha', 'hora', 'pk'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('reserva', 'sentido'),
                        name='viajetransporte_unico_por_sentido',
                    ),
                ],
            },
        ),
    ]
