"""Sincronización de viajes de transporte asignables.

Reglas del spec §5:
- Cada tramo de un traslado se modela como un ViajeTransporte.
- sincronizar_viajes es idempotente: llamarlo varias veces produce el mismo estado.
- Sincroniza viajes deseados según tipo_traslado y estado de cupo de la reserva.
- sincronizar_viajes_seguro envuelve la llamada en su propio savepoint y atrapa Exception,
  garantizando que un efecto secundario no pueda deshacer un cobro ni abortar una transacción.
"""
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO, ViajeTransporte
from apps.fleet.enums import TipoServicio, TipoTraslado

logger = logging.getLogger(__name__)


def sincronizar_viajes(reserva, detalle=None):
    """Crea, actualiza o cancela los viajes de transporte de una reserva.

    Reglas exactas del spec §5:
    - Aplica solo si reserva.servicio_id no es nulo (reserva de paquete sin servicio directo
      no genera viajes) y reserva.servicio.tipo_servicio == 'transporte'.
    - Requiere detalle_transporte: sin detalle no se generan viajes.
    - Idempotente: ejecutarlo repetidamente no duplica viajes.
    - Viajes deseados según tipo_traslado:
      * recepcion_aeropuerto -> ['unico': (fecha=reserva.fecha, hora=reserva.hora)]
      * redondo_actividad -> ['ida': (fecha=reserva.fecha, hora=reserva.hora), 'regreso': (fecha=reserva.fecha, hora=None)]
      * redondo_aeropuerto -> ['ida': (fecha=reserva.fecha, hora=reserva.hora), 'regreso': (fecha=detalle.fecha_regreso, hora=None)]
    - Si la reserva ocupa cupo (pagada, asignada, completada):
      * Crea los que faltan.
      * Actualiza fecha/hora de los existentes.
      * Quita el vehículo de un viaje cuya fecha cambió (la asignación deja de ser válida).
      * Conserva el vehículo si la fecha no cambió (un cambio de hora conserva el vehículo).
      * Borra los viajes cuyo sentido ya no se desea (ej. al cambiar tipo de traslado).
      * Pone cancelado=False.
      * Nunca pisa la hora de un regreso ya capturada por la vendedora.
      * Usa update_or_create por (reserva, sentido) para evitar IntegrityError por carreras con el admin.
    - Si no ocupa cupo (cancelada, pendiente_pago):
      * Marca cancelado=True en los existentes y les quita el vehículo.
      * No crea nuevos viajes.
    """
    if not reserva or not getattr(reserva, 'servicio_id', None):
        return

    servicio = getattr(reserva, 'servicio', None)
    if servicio is None or servicio.tipo_servicio != TipoServicio.TRANSPORTE:
        return

    if detalle is None:
        try:
            detalle = reserva.detalle_transporte
        except ObjectDoesNotExist:
            return
        except AttributeError:
            return

    if detalle is None:
        return

    ocupa_cupo = reserva.estado in ESTADOS_QUE_OCUPAN_CUPO

    # Si no ocupa cupo (cancelada o pendiente): marca cancelado=True en los existentes,
    # les quita el vehículo (como una panga que suelta una cancelada) y no crea nuevos.
    if not ocupa_cupo:
        ViajeTransporte.objects.filter(reserva=reserva).update(cancelado=True, vehiculo=None)
        return

    # Determinar viajes deseados según tipo_traslado
    tipo = detalle.tipo_traslado
    deseados = {}
    if tipo == TipoTraslado.RECEPCION_AEROPUERTO:
        deseados[ViajeTransporte.Sentido.UNICO] = {
            'fecha': reserva.fecha,
            'hora': reserva.hora,
        }
    elif tipo == TipoTraslado.REDONDO_ACTIVIDAD:
        deseados[ViajeTransporte.Sentido.IDA] = {
            'fecha': reserva.fecha,
            'hora': reserva.hora,
        }
        deseados[ViajeTransporte.Sentido.REGRESO] = {
            'fecha': reserva.fecha,
            'hora': None,
        }
    elif tipo == TipoTraslado.REDONDO_AEROPUERTO:
        deseados[ViajeTransporte.Sentido.IDA] = {
            'fecha': reserva.fecha,
            'hora': reserva.hora,
        }
        if detalle.fecha_regreso:
            deseados[ViajeTransporte.Sentido.REGRESO] = {
                'fecha': detalle.fecha_regreso,
                'hora': None,
            }

    # Borrar los que ya no se desean (ej. cambio de redondo a unico)
    ViajeTransporte.objects.filter(reserva=reserva).exclude(sentido__in=deseados.keys()).delete()

    # Actualizar o crear los deseados
    for sentido, info in deseados.items():
        nueva_fecha = info['fecha']
        existente = ViajeTransporte.objects.filter(reserva=reserva, sentido=sentido).first()
        if existente:
            fecha_cambio = (existente.fecha != nueva_fecha)
            # Quita el vehículo de un viaje cuya fecha cambió; cambio de hora lo conserva.
            vehiculo = None if fecha_cambio else existente.vehiculo
            # Nunca toca la hora de un regreso ya capturada.
            if sentido == ViajeTransporte.Sentido.REGRESO and existente.hora is not None:
                hora = existente.hora
            else:
                hora = info['hora']
        else:
            vehiculo = None
            hora = info['hora']

        ViajeTransporte.objects.update_or_create(
            reserva=reserva,
            sentido=sentido,
            defaults={
                'empresa': reserva.empresa,
                'fecha': nueva_fecha,
                'hora': hora,
                'vehiculo': vehiculo,
                'cancelado': False,
            },
        )


def sincronizar_viajes_seguro(reserva, detalle=None):
    """Envoltura segura para sincronizar viajes sin riesgo de abortar la transacción.

    Abre su propio savepoint (transaction.atomic()) y atrapa Exception.
    Es la única excepción permitida a la regla de no usar `except Exception`:
    un efecto secundario en la creación o sincronización de viajes NO puede
    tumbar un cobro ya realizado por Stripe ni abortar la transacción principal.
    Sin savepoint propio, cualquier error dejaría la transacción de PostgreSQL
    en estado abortado.
    """
    try:
        with transaction.atomic():
            sincronizar_viajes(reserva, detalle=detalle)
    except Exception:
        # Excepción intencionalmente atrapada: un efecto secundario no puede deshacer un cobro.
        logger.exception(
            'Fallo al sincronizar viajes de transporte para Reserva #%s. '
            'Los viajes pueden repararse con manage.py sincronizar_viajes_transporte.',
            getattr(reserva, 'pk', None),
        )


def borrar_viajes_reserva(reserva_id):
    """Borra todos los viajes de transporte de una reserva."""
    ViajeTransporte.objects.filter(reserva_id=reserva_id).delete()


def borrar_viajes_reserva_seguro(reserva_id):
    """Envoltura segura para borrar viajes de transporte al eliminar DetalleTransporte."""
    try:
        with transaction.atomic():
            borrar_viajes_reserva(reserva_id)
    except Exception:
        logger.exception(
            'Fallo al borrar viajes de transporte de Reserva #%s tras eliminar DetalleTransporte.',
            reserva_id,
        )
