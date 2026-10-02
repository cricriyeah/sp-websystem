"""Sincronización de días de mar de reservas de paquetes multidía."""

from apps.fleet.calendario_paquete import fechas_de_componente


def salidas_deseadas(reserva):
    """Pares (servicio, fecha) calculados desde la reserva actual, aún sin guardar."""
    if not reserva.paquete_id or reserva.orden_id:
        return set()
    return {
        (ps.servicio_id, dia)
        for ps in reserva.paquete.servicios_asociados.select_related('servicio')
        if ps.servicio.estrategia_cupo == 'por_recurso_dia' and ps.salidas > 1
        for dia in fechas_de_componente(reserva.fecha_inicio_paquete, ps.dia_estancia, ps.salidas)
    }


def validar_cupo_salidas_bajo_candado(reserva, deseadas):
    """Serializa y revalida todos los días antes de guardar una reserva ocupante."""
    from django.core.exceptions import ValidationError

    from apps.bookings.cupo.candado import bloquear_cupo
    from apps.bookings.models import evaluar_cupo

    for fecha in sorted({fecha for _, fecha in deseadas}):
        bloquear_cupo(reserva.empresa_id, fecha)
    for servicio_id, fecha in sorted(deseadas, key=lambda par: (par[1], par[0])):
        motivo = evaluar_cupo(
            fecha, reserva.personas_de(servicio_id), reserva.empresa,
            excluir_pk=reserva.pk, estrategia_cupo='por_recurso_dia', servicio_id=servicio_id,
        )
        if motivo:
            raise ValidationError({
                'fecha': f'No hay cupo disponible para el {fecha} ({motivo}).',
            })


def sincronizar_salidas(reserva):
    """Mantiene las salidas de una reserva ocupante iguales al calendario del paquete.

    Las filas de reservas canceladas se conservan como registro histórico; el motor
    de cupo las excluye según el estado de la reserva.
    """
    from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO, ReservaSalida

    if (
        not reserva.pk or not reserva.paquete_id or reserva.orden_id
        or reserva.estado not in ESTADOS_QUE_OCUPAN_CUPO
    ):
        return

    deseadas = salidas_deseadas(reserva)
    if not deseadas:
        return
    existentes = {
        (salida.servicio_id, salida.fecha): salida
        for salida in reserva.salidas.all()
    }
    for clave, salida in existentes.items():
        if clave not in deseadas:
            salida.delete()
    for servicio_id, fecha in deseadas - existentes.keys():
        ReservaSalida.objects.create(
            empresa_id=reserva.empresa_id, reserva=reserva, servicio_id=servicio_id, fecha=fecha,
        )
