from django.db import migrations, models


def copiar_extras(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Extra = apps.get_model('fleet', 'ExtrasItem')
    Pers = apps.get_model('fleet', 'Personalizacion')
    SP = apps.get_model('fleet', 'ServicioPersonalizacion')
    Servicio = apps.get_model('fleet', 'Servicio')
    db = schema_editor.connection.alias
    with alcance_operador_migracion(schema_editor.connection):
        for extra in Extra.objects.using(db).all().iterator():
            servicio = Servicio.objects.using(db).filter(
                empresa_id=extra.empresa_id, slug='pesca-deportiva', tipo_servicio='pesca',
            ).first()
            if servicio is None:
                raise RuntimeError(f'Falta pesca-deportiva en empresa {extra.empresa_id}')
            licencia = extra.tipo == 'licencia'
            campos = dict(
                tipo=extra.tipo, tipo_interaccion='check', opciones_seleccion=[],
                aviso_reforzado=licencia, cobrar_por_persona=extra.cobrar_por_persona,
                cantidad_editable=extra.cantidad_editable, activo=extra.activo,
            )
            p, creada = Pers.objects.using(db).get_or_create(
                empresa_id=extra.empresa_id, nombre=extra.nombre, defaults=campos,
            )
            if not creada and any(getattr(p, k) != v for k, v in campos.items()):
                raise RuntimeError(
                    f'Conflicto de catálogo: empresa {extra.empresa_id}, nombre {extra.nombre}, extra {extra.pk}'
                )
            precio_flags = dict(
                precio=extra.precio, precio_usd=extra.precio_usd, obligatorio=False,
                preseleccionado=licencia or extra.preseleccionado, activo=extra.activo,
            )
            sp, creada_sp = SP.objects.using(db).get_or_create(
                servicio_id=servicio.pk, personalizacion_id=p.pk, defaults=precio_flags,
            )
            if not creada_sp and any(getattr(sp, k) != v for k, v in precio_flags.items()):
                raise RuntimeError(
                    f'Conflicto de precio: empresa {extra.empresa_id}, nombre {extra.nombre}, extra {extra.pk}'
                )


class Migration(migrations.Migration):
    dependencies = [('fleet', '0032_retirar_tarifa')]
    operations = [
        migrations.AlterField('personalizacion', 'nombre', models.CharField(max_length=150)),
        migrations.RunPython(copiar_extras, migrations.RunPython.noop),
    ]
