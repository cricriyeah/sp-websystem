"""Agrega Vehiculo y VehiculoNoDisponible a la app fleet."""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0046_quitar_precio_por_persona'),
        ('tenancy', '0004_la_ventana_puerto_chale'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Vehiculo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('lugares', models.PositiveSmallIntegerField(
                    help_text='Numero de lugares disponibles (minimo 1).',
                    validators=[django.core.validators.MinValueValidator(1)],
                )),
                ('activo', models.BooleanField(
                    default=True,
                    help_text='Desmarcalo para sacar el vehiculo de la flota sin borrarlo. '
                              'Un vehiculo inactivo no se puede asignar a nuevos viajes pero '
                              'conserva el historial.',
                )),
                ('empresa', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='vehiculos',
                    to='tenancy.empresa',
                )),
            ],
            options={
                'verbose_name': 'vehiculo',
                'verbose_name_plural': 'vehiculos',
                'ordering': ['nombre'],
                'constraints': [
                    models.UniqueConstraint(fields=('nombre', 'empresa'), name='vehiculo_nombre_unico_por_empresa'),
                ],
            },
        ),
        migrations.CreateModel(
            name='VehiculoNoDisponible',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('hora_desde', models.TimeField(
                    blank=True, null=True,
                    help_text='Inicio del bloqueo. Vacio = bloqueo de dia completo.',
                )),
                ('hora_hasta', models.TimeField(
                    blank=True, null=True,
                    help_text='Fin del bloqueo. Vacio = bloqueo de dia completo.',
                )),
                ('motivo', models.CharField(blank=True, max_length=200)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('empresa', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='vehiculos_no_disponibles',
                    to='tenancy.empresa',
                )),
                ('registrado_por', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='vehiculos_dados_de_baja',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('vehiculo', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='no_disponibles',
                    to='fleet.vehiculo',
                )),
            ],
            options={
                'verbose_name': 'vehiculo no disponible',
                'verbose_name_plural': 'vehiculos no disponibles',
                'ordering': ['-fecha', 'vehiculo__nombre'],
            },
        ),
    ]
