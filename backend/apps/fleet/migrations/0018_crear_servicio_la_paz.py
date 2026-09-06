from decimal import Decimal
from django.db import migrations


def crear_servicio_pesca_la_paz(apps, schema_editor):
    # fleet_servicio / fleet_recurso ya tienen RLS forzada (0017): sin abrir
    # alcance, estos INSERT los rechaza la politica WITH CHECK bajo un rol
    # NOBYPASSRLS. Ver apps.tenancy.rls.alcance_operador_migracion.
    from apps.tenancy.rls import alcance_operador_migracion

    with alcance_operador_migracion(schema_editor.connection):
        _crear_servicio_pesca_la_paz(apps)


def _crear_servicio_pesca_la_paz(apps):
    Empresa = apps.get_model('tenancy', 'Empresa')
    Tarifa = apps.get_model('fleet', 'Tarifa')
    Servicio = apps.get_model('fleet', 'Servicio')
    Recurso = apps.get_model('fleet', 'Recurso')
    Embarcacion = apps.get_model('fleet', 'Embarcacion')

    empresa = Empresa.objects.filter(slug='sal-y-sol').first()
    if not empresa:
        return

    tarifa = Tarifa.objects.filter(empresa=empresa).first()
    precio_base = tarifa.precio if tarifa else Decimal('4500.00')
    precio_base_usd = tarifa.precio_usd if tarifa else Decimal('260.00')
    precio_persona_extra = tarifa.precio_persona_extra if tarifa else Decimal('500.00')
    precio_persona_extra_usd = tarifa.precio_persona_extra_usd if tarifa else Decimal('30.00')

    servicio, _ = Servicio.objects.get_or_create(
        empresa=empresa,
        slug='pesca-deportiva',
        defaults={
            'nombre': 'Pesca Deportiva en La Paz',
            'tipo_servicio': 'pesca',
            'estrategia_cupo': 'por_recurso_dia',
            'estrategia_precio': 'por_grupo',
            'modo_ocupacion': 'exclusivo',
            'precio_base': precio_base,
            'precio_base_usd': precio_base_usd,
            'precio_persona_extra': precio_persona_extra,
            'precio_persona_extra_usd': precio_persona_extra_usd,
            'personas_incluidas': 3,
            'activo': True,
            'descripcion': (
                'Jornada completa de pesca deportiva en La Paz (Baja California Sur). '
                'Panga exclusiva con capitan experto.'
            ),
        }
    )

    for embarcacion in Embarcacion.objects.filter(empresa=empresa):
        recurso, _ = Recurso.objects.get_or_create(
            empresa=empresa,
            nombre=embarcacion.nombre,
            defaults={
                'servicio': servicio,
                'capacidad_maxima': embarcacion.capacidad_maxima,
                'activo': embarcacion.activa,
            }
        )
        if recurso.servicio_id is None:
            recurso.servicio = servicio
            recurso.save(update_fields=['servicio'])


def revertir_servicio_pesca(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    with alcance_operador_migracion(schema_editor.connection):
        _revertir_servicio_pesca(apps)


def _revertir_servicio_pesca(apps):
    Empresa = apps.get_model('tenancy', 'Empresa')
    Servicio = apps.get_model('fleet', 'Servicio')
    Recurso = apps.get_model('fleet', 'Recurso')

    empresa = Empresa.objects.filter(slug='sal-y-sol').first()
    if not empresa:
        return

    servicio = Servicio.objects.filter(empresa=empresa, slug='pesca-deportiva').first()
    if servicio:
        Recurso.objects.filter(servicio=servicio).delete()
        servicio.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0017_rls_catalogo'),
    ]

    operations = [
        migrations.RunPython(crear_servicio_pesca_la_paz, revertir_servicio_pesca),
    ]
