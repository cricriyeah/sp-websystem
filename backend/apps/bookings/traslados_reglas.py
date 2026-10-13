"""Reglas de choque entre viajes y bloqueos de vehiculos.

Este modulo existe para que la logica sea identica en ViajeTransporte.clean()
(que pregunta si hay un bloqueo que toca el viaje) y en VehiculoNoDisponible.clean()
(que pregunta si hay viajes que chocarian con el bloqueo que se quiere registrar).
Lo importamos con importacion diferida dentro de los clean() para evitar circulos.
"""


def bloqueo_toca_viaje(bloqueo_hora_desde, bloqueo_hora_hasta, viaje_hora):
    """True si un bloqueo de horario cubre la hora de un viaje.

    Reglas del spec §4:
    - Sin hora en el viaje: solo chocan los bloqueos de dia completo (sin horas).
    - Con hora en el viaje: chocan los bloqueos de dia completo Y los rangos que
      contengan esa hora.
    - Un viaje sin hora no choca con un bloqueo de rango (el rango no lo toca).

    `bloqueo_hora_desde` y `bloqueo_hora_hasta` son None cuando el bloqueo es de
    dia completo.
    """
    es_bloqueo_completo = bloqueo_hora_desde is None and bloqueo_hora_hasta is None

    if viaje_hora is None:
        # Sin hora en el viaje: solo choca el bloqueo de dia completo.
        return es_bloqueo_completo

    # Con hora en el viaje: choca dia completo o rango que lo contenga.
    if es_bloqueo_completo:
        return True
    # Rango: la hora del viaje debe caer dentro [desde, hasta).
    return bloqueo_hora_desde <= viaje_hora < bloqueo_hora_hasta


def viajes_que_chocan_con_bloqueo(vehiculo_id, fecha, hora_desde, hora_hasta, excluir_cancelados=True):
    """QuerySet de ViajeTransporte que chocarian con un bloqueo en esa fecha/horas.

    Se usa desde VehiculoNoDisponible.clean() para la validacion inversa: rechaza
    el bloqueo si ya hay viajes asignados que lo tocan.

    Parametros:
        vehiculo_id: PK del vehiculo que se quiere bloquear.
        fecha: fecha del bloqueo.
        hora_desde, hora_hasta: rango del bloqueo (None = dia completo).
        excluir_cancelados: si True, ignora viajes cancelados (para la validacion
            inversa; False si queremos incluirlos para otro proposito).
    """
    from apps.bookings.models import ViajeTransporte

    qs = ViajeTransporte.objects.filter(vehiculo_id=vehiculo_id, fecha=fecha)
    if excluir_cancelados:
        qs = qs.filter(cancelado=False)

    es_bloqueo_completo = hora_desde is None and hora_hasta is None

    if es_bloqueo_completo:
        # Dia completo choca con cualquier viaje (con o sin hora) del dia.
        return qs

    # Bloqueo de rango: choca con viajes que tengan hora dentro del rango.
    # Un viaje sin hora NO choca con un bloqueo de rango (spec §4).
    return qs.filter(hora__isnull=False, hora__gte=hora_desde, hora__lt=hora_hasta)


def bloqueo_cubre_viaje(vehiculo_id, fecha, viaje_hora, excluir_bloqueo_pk=None):
    """True si existe algun VehiculoNoDisponible que cubra el viaje.

    Se usa desde ViajeTransporte.clean() para validar que el vehiculo no
    esta bloqueado en esa fecha/hora.

    Parametros:
        vehiculo_id: PK del vehiculo asignado.
        fecha: fecha del viaje.
        viaje_hora: hora del viaje (None = viaje sin hora).
        excluir_bloqueo_pk: PK de un bloqueo a excluir (para edicion).
    """
    from apps.fleet.models import VehiculoNoDisponible

    qs = VehiculoNoDisponible.objects.filter(vehiculo_id=vehiculo_id, fecha=fecha)
    if excluir_bloqueo_pk is not None:
        qs = qs.exclude(pk=excluir_bloqueo_pk)

    for bloqueo in qs:
        if bloqueo_toca_viaje(bloqueo.hora_desde, bloqueo.hora_hasta, viaje_hora):
            return True
    return False
