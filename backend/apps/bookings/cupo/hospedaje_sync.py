"""Mantiene las habitaciones de una reserva ya pagada al dia cuando cambian sus fechas o su grupo."""
from django.db import transaction

from . import SinCupoError
from .adaptador import obtener_recursos_con_ocupaciones
from .candado import bloquear_recurso
from .confirmacion import elegir_habitaciones
from .nucleo import recursos_disponibles_en_rango


def hospedajes_de(reserva):
    """(servicio, desde, hasta, personas) por cada hospedaje de la reserva: el servicio suelto
    `por_noche` o el componente de hospedaje del paquete. Mismos rangos que usa
    `reservar_cupo_al_confirmar` al pagar."""
    if reserva.orden_id is not None:
        return []
    if reserva.paquete_id:
        return [
            (ps.servicio, reserva.fecha_inicio_paquete, reserva.fecha_fin_servicio, reserva.personas_de(ps.servicio_id))
            for ps in reserva.paquete.servicios_asociados.select_related('servicio')
            if ps.servicio.estrategia_cupo == 'por_noche'
        ]
    if reserva.servicio_id and reserva.servicio.estrategia_cupo == 'por_noche':
        return [(reserva.servicio, reserva.fecha, reserva.fecha_fin_servicio, reserva.numero_personas)]
    return []


def sincronizar_ocupaciones(reserva):
    """Lleva las `ReservaOcupacion` de la reserva a sus fechas y grupo actuales.

    Antes, cambiar la fecha de un hospedaje ya pagado dejaba la habitacion bloqueada en las fechas
    viejas y las nuevas libres para venderse otra vez. Se conservan las mismas habitaciones si
    siguen libres en el rango nuevo y alcanzan para el grupo (solo se mueven sus fechas); si no, se
    vuelven a elegir con la misma funcion que usa el pago. Sin habitacion para el nuevo rango lanza
    `SinCupoError` y deja las filas como estaban.

    Solo toca lo que ya existe: reservar por primera vez es de `reservar_cupo_al_confirmar`.
    """
    if not reserva.pk:
        return
    for servicio, desde, hasta, personas in hospedajes_de(reserva):
        existentes = list(reserva.ocupaciones.filter(recurso__servicio=servicio, ocupa_cupo=True))
        if not existentes:
            continue
        if all(o.fecha_inicio == desde and o.fecha_fin == hasta for o in existentes):
            capacidad = sum(o.recurso.capacidad_maxima for o in existentes)
            if capacidad >= personas:
                continue

        with transaction.atomic():
            for recurso in servicio.recursos.filter(activo=True).order_by('pk'):
                bloquear_recurso(reserva.empresa_id, recurso.pk)

            libres = dict(recursos_disponibles_en_rango(
                obtener_recursos_con_ocupaciones(
                    desde=desde, hasta=hasta, empresa=reserva.empresa, servicio=servicio,
                    excluir_pk=reserva.pk,
                ),
                desde, hasta,
            ))
            ids = [o.recurso_id for o in existentes]
            if all(i in libres for i in ids) and sum(libres[i] for i in ids) >= personas:
                reserva.ocupaciones.filter(pk__in=[o.pk for o in existentes]).update(
                    fecha_inicio=desde, fecha_fin=hasta,
                )
                continue

            elegidos = elegir_habitaciones(
                servicio=servicio, desde=desde, hasta=hasta, personas=personas,
                empresa=reserva.empresa, excluir_pk=reserva.pk,
            )
            if not elegidos:
                raise SinCupoError('No hay habitación disponible en esas fechas.')
            from apps.bookings.models import ReservaOcupacion

            reserva.ocupaciones.filter(pk__in=[o.pk for o in existentes]).delete()
            for recurso_id in elegidos:
                ReservaOcupacion.objects.create(
                    reserva=reserva, recurso_id=recurso_id, empresa=reserva.empresa,
                    fecha_inicio=desde, fecha_fin=hasta, ocupa_cupo=True,
                )
