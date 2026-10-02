from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models
from django.db.models import Max


def migrar_precios(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Paquete = apps.get_model('fleet', 'Paquete')
    PaqueteServicio = apps.get_model('fleet', 'PaqueteServicio')
    with alcance_operador_migracion(schema_editor.connection):
        bases = dict(
            PaqueteServicio.objects.values('paquete_id')
            .annotate(base=Max('personas_incluidas'))
            .values_list('paquete_id', 'base')
        )
        for paquete in Paquete.objects.all().iterator():
            if paquete.precio_por_persona:
                paquete.estrategia_precio = 'por_persona'
                paquete.personas_precio_base = 1
            else:
                paquete.estrategia_precio = 'por_grupo'
                paquete.personas_precio_base = max(1, bases.get(paquete.pk) or 1)
            paquete.precio_persona_extra = Decimal('0')
            paquete.save(update_fields=[
                'estrategia_precio', 'personas_precio_base', 'precio_persona_extra',
            ])


def revertir_precios(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Paquete = apps.get_model('fleet', 'Paquete')
    with alcance_operador_migracion(schema_editor.connection):
        if Paquete.objects.exclude(precio_persona_extra=0).exists():
            raise RuntimeError(
                'No se puede revertir precio_persona_extra: el campo anterior no representa ese cargo.'
            )
        for paquete in Paquete.objects.all().iterator():
            paquete.precio_por_persona = paquete.estrategia_precio == 'por_persona'
            paquete.save(update_fields=['precio_por_persona'])


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0044_quitar_precios_usd'),
    ]

    operations = [
        migrations.AddField(
            model_name='paquete', name='estrategia_precio',
            field=models.CharField(
                max_length=20, default='por_grupo',
                choices=[('por_grupo', 'Por grupo'), ('por_persona', 'Por persona')],
                help_text='Por grupo: precio base más cargo por cada persona adicional. '
                          'Por persona: el precio base se cobra a cada persona.',
            ),
        ),
        migrations.AddField(
            model_name='paquete', name='personas_precio_base',
            field=models.PositiveSmallIntegerField(
                default=1, validators=[MinValueValidator(1)],
                help_text='Personas cubiertas por el precio base del grupo.',
            ),
        ),
        migrations.AddField(
            model_name='paquete', name='precio_persona_extra',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=Decimal('0'),
                validators=[MinValueValidator(Decimal('0'))],
                help_text='Pesos adicionales por cada persona que supere las cubiertas por el precio base.',
            ),
        ),
        migrations.RunPython(migrar_precios, revertir_precios),
    ]
