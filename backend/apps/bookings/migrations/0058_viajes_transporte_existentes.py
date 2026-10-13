"""Migración de datos: crea los viajes de las reservas de transporte existentes que ocupan cupo."""

from django.db import migrations
from apps.tenancy.rls import alcance_operador_migracion


def crear_viajes_existentes(apps, schema_editor):
    Reserva = apps.get_model('bookings', 'Reserva')
    DetalleTransporte = apps.get_model('bookings', 'DetalleTransporte')
    ViajeTransporte = apps.get_model('bookings', 'ViajeTransporte')

    ESTADOS_QUE_OCUPAN_CUPO = ['pagada', 'asignada', 'completada']

    with alcance_operador_migracion(schema_editor.connection):
        # Reservas de transporte que ocupan cupo
        reservas = (
            Reserva.objects.filter(
                estado__in=ESTADOS_QUE_OCUPAN_CUPO,
                servicio__tipo_servicio='transporte',
            )
            .select_related('servicio')
            .order_by('pk')
        )

        for reserva in reservas:
            detalle = DetalleTransporte.objects.filter(reserva_id=reserva.pk).first()

            if not detalle:
                continue

            tipo = detalle.tipo_traslado
            deseados = {}
            if tipo == 'recepcion_aeropuerto':
                deseados['unico'] = {'fecha': reserva.fecha, 'hora': reserva.hora}
            elif tipo == 'redondo_actividad':
                deseados['ida'] = {'fecha': reserva.fecha, 'hora': reserva.hora}
                deseados['regreso'] = {'fecha': reserva.fecha, 'hora': None}
            elif tipo == 'redondo_aeropuerto':
                deseados['ida'] = {'fecha': reserva.fecha, 'hora': reserva.hora}
                if detalle.fecha_regreso:
                    deseados['regreso'] = {'fecha': detalle.fecha_regreso, 'hora': None}

            # Borrar viajes que ya no coincidan con los deseados
            ViajeTransporte.objects.filter(reserva_id=reserva.pk).exclude(sentido__in=deseados.keys()).delete()

            for sentido, info in deseados.items():
                existente = ViajeTransporte.objects.filter(
                    reserva_id=reserva.pk, sentido=sentido
                ).first()
                if existente:
                    fecha_cambio = existente.fecha != info['fecha']
                    vehiculo_id = None if fecha_cambio else existente.vehiculo_id
                    hora = existente.hora if (sentido == 'regreso' and existente.hora is not None) else info['hora']
                else:
                    vehiculo_id = None
                    hora = info['hora']

                ViajeTransporte.objects.update_or_create(
                    reserva_id=reserva.pk,
                    sentido=sentido,
                    defaults={
                        'empresa_id': reserva.empresa_id,
                        'fecha': info['fecha'],
                        'hora': hora,
                        'vehiculo_id': vehiculo_id,
                        'cancelado': False,
                    },
                )


def revertir_viajes_existentes(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0057_rls_viajetransporte'),
    ]

    operations = [
        migrations.RunPython(crear_viajes_existentes, revertir_viajes_existentes),
    ]
