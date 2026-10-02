"""Lógica de confirmación y asignación de cupo al confirmar el pago de una reserva."""
from apps.fleet.calendario_paquete import fechas_de_componente
from apps.bookings.cupo import SinCupoError
from apps.bookings.cupo.adaptador import obtener_recursos_con_ocupaciones
from apps.bookings.cupo.candado import bloquear_cupo, bloquear_recurso
from apps.bookings.cupo.nucleo import elegir_recursos, habitaciones_necesarias, recursos_disponibles_en_rango
from apps.bookings.models import (
    ReservaOcupacion,
    ReservaPaqueteComponente,
    evaluar_cupo,
)


def _asignar_cupo_hospedaje(reserva, servicio, es_componente=False, *, desde=None, hasta=None, personas=None):
    desde = desde or reserva.fecha
    hasta = hasta or reserva.fecha_fin_servicio
    personas = personas or reserva.numero_personas
    recursos_candidatos = list(servicio.recursos.filter(activo=True))
    if not recursos_candidatos:
        msg = (
            f'No hay habitación disponible para el componente {servicio.nombre}.'
            if es_componente
            else 'No hay habitaciones configuradas para este servicio.'
        )
        raise SinCupoError(msg)

    for recurso in recursos_candidatos:
        bloquear_recurso(reserva.empresa_id, recurso.pk)

    recursos_con_ocupaciones = obtener_recursos_con_ocupaciones(
        desde=desde,
        hasta=hasta,
        empresa=reserva.empresa,
        servicio=servicio,
        excluir_pk=reserva.pk,
    )
    libres = recursos_disponibles_en_rango(recursos_con_ocupaciones, desde, hasta)
    cantidad = habitaciones_necesarias([cap for _, cap in libres], personas)
    elegidos = elegir_recursos(libres, personas=personas, cantidad=cantidad) if cantidad else None
    if not elegidos:
        msg = (
            f'No hay habitación disponible para el componente {servicio.nombre}.'
            if es_componente
            else 'No hay habitación disponible en esas fechas.'
        )
        raise SinCupoError(msg)

    if not reserva.ocupaciones.filter(recurso__servicio=servicio).exists():
        for rec_id in elegidos:
            ReservaOcupacion.objects.create(
                reserva=reserva,
                recurso_id=rec_id,
                empresa=reserva.empresa,
                fecha_inicio=desde,
                fecha_fin=hasta,
                ocupa_cupo=True,
            )


def reservar_cupo_al_confirmar(reserva) -> None:
    """Crea la ocupación de recursos y/o componentes al confirmarse el pago.

    Lanza `SinCupoError` si no hay cupo disponible para algún componente
    o habitación. Todo debe ejecutarse dentro de la transacción del webhook
    o conciliar_pagos.
    """
    # Caso D: esta reserva es un unico componente de una orden cruza-empresa.
    # Cada webhook confirma solo el servicio de su propia empresa.
    if reserva.orden_id is not None:
        servicio = reserva.servicio
        estrategia = servicio.estrategia_cupo

        if estrategia == 'por_recurso_dia':
            bloquear_cupo(reserva.empresa_id, reserva.fecha, servicio_id=servicio.pk)
            motivo = evaluar_cupo(
                reserva.fecha,
                reserva.numero_personas,
                reserva.empresa,
                excluir_pk=reserva.pk,
                estrategia_cupo='por_recurso_dia',
                servicio_id=servicio.pk,
            )
            if motivo:
                raise SinCupoError(f'No hay cupo para {servicio.nombre} ({motivo}).')
        elif estrategia == 'por_noche':
            _asignar_cupo_hospedaje(reserva, servicio, es_componente=True)
        # bajo_demanda (transporte): no reserva inventario.

        ReservaPaqueteComponente.objects.create(
            reserva=reserva,
            servicio=servicio,
            empresa=reserva.empresa,
            estado_cupo=ReservaPaqueteComponente.EstadoCupo.OK,
        )
        return

    # Caso A: servicio hospedaje directo
    if reserva.servicio and reserva.servicio.estrategia_cupo == 'por_noche':
        _asignar_cupo_hospedaje(reserva, reserva.servicio, es_componente=False)
        return

    # Caso B: paquete con componentes
    if reserva.paquete is not None and reserva.orden_id is None:
        componentes = list(reserva.paquete.servicios_asociados.select_related('servicio').order_by('orden'))
        locks = [
            (dia, ps.servicio_id)
            for ps in componentes if ps.servicio.estrategia_cupo == 'por_recurso_dia'
            for dia in (
                fechas_de_componente(reserva.fecha_inicio_paquete, ps.dia_estancia, ps.salidas)
                if ps.salidas > 1 else [reserva.fecha]
            )
        ]
        for dia, servicio_id in sorted(locks):
            bloquear_cupo(reserva.empresa_id, dia, servicio_id=servicio_id)

        for ps in componentes:
            servicio = ps.servicio
            estrategia = servicio.estrategia_cupo

            if estrategia == 'por_recurso_dia':
                personas = reserva.personas_de(servicio.pk)
                fechas = (
                    sorted(fechas_de_componente(reserva.fecha_inicio_paquete, ps.dia_estancia, ps.salidas))
                    if ps.salidas > 1 else [reserva.fecha]
                )
                for dia in fechas:
                    motivo = evaluar_cupo(
                        dia, personas, reserva.empresa, excluir_pk=reserva.pk,
                        estrategia_cupo='por_recurso_dia', servicio_id=servicio.pk,
                    )
                    if motivo:
                        if ps.salidas > 1:
                            raise SinCupoError(
                                f'No hay cupo disponible para el componente {servicio.nombre} el {dia} ({motivo}).'
                            )
                        raise SinCupoError(f'No hay cupo disponible para el componente {servicio.nombre} ({motivo}).')
                ReservaPaqueteComponente.objects.create(
                    reserva=reserva,
                    servicio=servicio,
                    empresa=reserva.empresa,
                    estado_cupo=ReservaPaqueteComponente.EstadoCupo.OK,
                )
            elif estrategia == 'por_noche':
                _asignar_cupo_hospedaje(
                    reserva, servicio, es_componente=True,
                    desde=reserva.fecha_inicio_paquete, hasta=reserva.fecha_fin_servicio,
                    personas=reserva.personas_de(servicio.pk),
                )
                ReservaPaqueteComponente.objects.create(
                    reserva=reserva,
                    servicio=servicio,
                    empresa=reserva.empresa,
                    estado_cupo=ReservaPaqueteComponente.EstadoCupo.OK,
                )
            elif estrategia == 'bajo_demanda':
                ReservaPaqueteComponente.objects.create(
                    reserva=reserva,
                    servicio=servicio,
                    empresa=reserva.empresa,
                    estado_cupo=ReservaPaqueteComponente.EstadoCupo.OK,
                )
        from apps.bookings.cupo.salidas import sincronizar_salidas

        sincronizar_salidas(reserva)
        return

    # Caso C: servicio directo bajo_demanda (incluido transporte), pesca/paseo
    # o legacy: nada nuevo que reservar. Transporte no crea ocupaciones ni componentes.
