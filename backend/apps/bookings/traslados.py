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
from apps.fleet.calendario_paquete import fecha_de_componente
from apps.fleet.enums import TipoServicio, TipoTraslado

logger = logging.getLogger(__name__)


def _tramos_de_servicio_de_transporte(reserva, detalle):
    """Tramos de una reserva de servicio de transporte, o None si no aplica (no es transporte o
    todavía no tiene `DetalleTransporte`)."""
    if not getattr(reserva, 'servicio_id', None):
        return None
    servicio = getattr(reserva, 'servicio', None)
    if servicio is None or servicio.tipo_servicio != TipoServicio.TRANSPORTE:
        return None

    if detalle is None:
        try:
            detalle = reserva.detalle_transporte
        except (ObjectDoesNotExist, AttributeError):
            return None
    if detalle is None:
        return None

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
    return deseados


def _tramos_de_paquete(reserva):
    """Tramos del traslado que incluye un paquete de una sola empresa, o None si no lleva traslado.

    Es un redondo: la ida el día del traslado (el de llegada, normalmente) y el regreso el día de
    salida del hospedaje; sin hospedaje, los dos caen el mismo día. La hora no se conoce — es la del
    vuelo y el checkout no la pide— así que los dos tramos nacen sin hora y la vendedora la captura
    en «Asignar vehículos», donde salen marcados «Falta la hora de vuelo».
    """
    traslado = (
        reserva.paquete.servicios_asociados.filter(servicio__tipo_servicio=TipoServicio.TRANSPORTE)
        .order_by('orden').first()
    )
    if traslado is None:
        return None
    dia = fecha_de_componente(reserva.fecha_inicio_paquete, traslado.dia_estancia)
    return {
        ViajeTransporte.Sentido.IDA: {'fecha': dia, 'hora': None},
        ViajeTransporte.Sentido.REGRESO: {'fecha': reserva.fecha_salida or dia, 'hora': None},
    }


def sincronizar_viajes(reserva, detalle=None):
    """Crea, actualiza o cancela los viajes de transporte de una reserva.

    Reglas exactas del spec §5:
    - Aplica a una reserva de servicio de transporte (reserva.servicio.tipo_servicio == 'transporte')
      y, desde la auditoria de 2026-10-23, a un paquete de una sola empresa que incluye un servicio
      de transporte (ver `_tramos_de_paquete`: ida y regreso sin hora).
    - Un servicio de transporte requiere detalle_transporte: sin detalle no se generan viajes.
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
    if not reserva:
        return

    # Un paquete de una sola empresa con traslado no tiene DetalleTransporte: sus tramos salen
    # de la definicion del paquete. Cualquier otra reserva necesita ser un servicio de transporte.
    es_paquete = bool(reserva.paquete_id) and not reserva.orden_id and not reserva.servicio_id
    if es_paquete:
        deseados = _tramos_de_paquete(reserva)
        if deseados is None:
            return
    else:
        deseados = _tramos_de_servicio_de_transporte(reserva, detalle)
        if deseados is None:
            return

    ocupa_cupo = reserva.estado in ESTADOS_QUE_OCUPAN_CUPO

    # Si no ocupa cupo (cancelada o pendiente): marca cancelado=True en los existentes,
    # les quita el vehículo (como una panga que suelta una cancelada) y no crea nuevos.
    if not ocupa_cupo:
        ViajeTransporte.objects.filter(reserva=reserva).update(cancelado=True, vehiculo=None)
        return

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
            # Nunca toca la hora ya capturada de un regreso, ni la de un tramo de paquete (la hora
            # del vuelo no la pide el checkout: la captura la vendedora y no sale de la reserva).
            conserva_hora = sentido == ViajeTransporte.Sentido.REGRESO or es_paquete
            if conserva_hora and existente.hora is not None and info['hora'] is None:
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
