"""Saldar en efectivo lo que un cliente debe de su reserva.

Una sola definicion de "se puede saldar" y de "como se salda", para que la
accion de la lista y el boton de la reserva no puedan decidir distinto.
"""
from django.db import transaction
from django.utils import timezone

from .models import Reserva

# Solo una reserva viva (pagada o ya con panga) tiene un saldo que cobrar el dia del
# viaje. Una cancelada o reembolsada ya no se cobra; una pendiente no ha pagado nada.
ESTADOS_LIQUIDABLES = (Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA)


def saldo_liquidable(reserva):
    """Lo que se puede saldar en efectivo ahora, o None si no aplica."""
    if reserva.estado not in ESTADOS_LIQUIDABLES or reserva.reembolsada:
        return None
    saldo = reserva.saldo_pendiente
    if saldo is None or saldo <= 0:
        return None
    return saldo


def liquidar_saldo_en_efectivo(reserva_pk, usuario):
    """Anota como recibido en efectivo el saldo que la reserva debe. Devuelve el
    monto saldado, o None si no habia nada que saldar.

    Vuelve a leer la reserva con la fila bloqueada y calcula el saldo de ESA
    lectura: la pantalla de confirmacion pudo mostrar un saldo que dejo de ser
    cierto (otro clic, otra pestana, una edicion a mano) y sumar de mas es cobrar
    dos veces. Con el bloqueo, dos clics simultaneos se turnan y el segundo ya
    no encuentra saldo.

    El sello de fecha y usuario es el del primer efectivo registrado: corregir o
    completar el monto despues no lo mueve (misma regla que el formulario).
    """
    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().filter(pk=reserva_pk).first()
        if reserva is None:
            return None
        saldo = saldo_liquidable(reserva)
        if saldo is None:
            return None
        reserva.monto_efectivo = (reserva.monto_efectivo or 0) + saldo
        if reserva.efectivo_cobrado_en is None:
            reserva.efectivo_cobrado_en = timezone.now()
            reserva.efectivo_cobrado_por = usuario
        # Solo campos de dinero: no es una edicion de la reserva, asi que no se
        # revalida cupo ni se tocan salidas o viajes.
        reserva.save(update_fields=['monto_efectivo', 'efectivo_cobrado_en', 'efectivo_cobrado_por'])
        return saldo
