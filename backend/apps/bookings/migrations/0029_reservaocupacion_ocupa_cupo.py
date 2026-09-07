from django.db import migrations, models

ESTADOS_QUE_OCUPAN_CUPO = ['pagada', 'asignada', 'completada']


def backfill_ocupa_cupo(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    with alcance_operador_migracion(schema_editor.connection):
        ReservaOcupacion = apps.get_model('bookings', 'ReservaOcupacion')
        ReservaOcupacion.objects.exclude(
            reserva__estado__in=ESTADOS_QUE_OCUPAN_CUPO
        ).update(ocupa_cupo=False)
        ReservaOcupacion.objects.filter(
            reserva__estado__in=ESTADOS_QUE_OCUPAN_CUPO
        ).update(ocupa_cupo=True)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0028_reserva_paquete'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservaocupacion',
            name='ocupa_cupo',
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.RunPython(backfill_ocupa_cupo, migrations.RunPython.noop),
    ]
