from datetime import time

from django.db import migrations


def ajustar_servicios_existentes(apps, schema_editor):
    # fleet_servicio tiene RLS forzada: sin abrir alcance, el UPDATE no ve filas bajo un rol NOBYPASSRLS.
    from apps.tenancy.rls import alcance_operador_migracion

    with alcance_operador_migracion(schema_editor.connection):
        Servicio = apps.get_model('fleet', 'Servicio')
        # El hospedaje no tiene hora de salida.
        Servicio.objects.filter(tipo_servicio='hospedaje').update(pide_hora=False)
        # Lo que el checkout ofrecía antes de que la ventana fuera un dato del servicio: el transporte de
        # 6:00 a 22:00 cada 30 minutos, y todo lo demás en la ventana de pesca de 5:00 a 7:00. Se conserva
        # como dato propio de cada servicio para que la empresa lo pueda cambiar.
        sin_ventana = Servicio.objects.filter(pide_hora=True, hora_apertura__isnull=True)
        sin_ventana.filter(tipo_servicio='transporte').update(
            hora_apertura=time(6, 0), hora_cierre=time(22, 0), paso_hora_minutos=30,
        )
        sin_ventana.exclude(tipo_servicio='transporte').update(hora_apertura=time(5, 0), hora_cierre=time(7, 0))


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0042_servicio_pide_hora_y_paso'),
    ]

    operations = [
        migrations.RunPython(ajustar_servicios_existentes, migrations.RunPython.noop),
    ]
