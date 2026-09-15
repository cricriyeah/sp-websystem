from datetime import time
from django.db import migrations


def migrar_tarifas(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion
    Tarifa = apps.get_model('fleet', 'Tarifa')
    Servicio = apps.get_model('fleet', 'Servicio')
    Reserva = apps.get_model('bookings', 'Reserva')
    db = schema_editor.connection.alias
    with alcance_operador_migracion(schema_editor.connection):
        for tarifa in Tarifa.objects.using(db).all().iterator():
            valores = dict(
                tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia',
                estrategia_precio='por_grupo',
                modo_ocupacion='exclusivo',
                precio_base=tarifa.precio,
                precio_base_usd=tarifa.precio_usd,
                precio_persona_extra=tarifa.precio_persona_extra,
                precio_persona_extra_usd=tarifa.precio_persona_extra_usd,
                personas_incluidas=3,
                hora_apertura=time(5),
                hora_cierre=time(7),
            )
            existente = Servicio.objects.using(db).filter(
                empresa_id=tarifa.empresa_id, slug='pesca-deportiva'
            ).first()
            if existente and existente.tipo_servicio != 'pesca':
                raise RuntimeError(
                    f'Slug pesca-deportiva ocupado por otro tipo en empresa {tarifa.empresa_id}'
                )
            servicio, creado = Servicio.objects.using(db).get_or_create(
                empresa_id=tarifa.empresa_id,
                slug='pesca-deportiva',
                defaults=dict(nombre='Pesca Deportiva', activo=True, **valores),
            )
            if not creado:
                Servicio.objects.using(db).filter(pk=servicio.pk).update(**valores)
            Reserva.objects.using(db).filter(
                empresa_id=tarifa.empresa_id,
                servicio_id__isnull=True,
                paquete_id__isnull=True,
            ).update(servicio_id=servicio.pk)
        for empresa_id in Reserva.objects.using(db).filter(
            servicio_id__isnull=True, paquete_id__isnull=True
        ).values_list('empresa_id', flat=True).distinct():
            servicio = Servicio.objects.using(db).filter(
                empresa_id=empresa_id, slug='pesca-deportiva', tipo_servicio='pesca'
            ).first()
            if servicio is None:
                raise RuntimeError(f'Falta configurar Servicio de pesca para empresa {empresa_id}')
            Reserva.objects.using(db).filter(
                empresa_id=empresa_id,
                servicio_id__isnull=True,
                paquete_id__isnull=True,
            ).update(servicio_id=servicio.pk)


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0030_personalizacion_tipo_interaccion'),
        ('bookings', '0044_rls_orden_sin_current_query'),
    ]

    operations = [
        migrations.RunPython(migrar_tarifas, migrations.RunPython.noop),
    ]
