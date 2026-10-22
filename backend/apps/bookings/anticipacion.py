"""Anticipación mínima para reservar por la web.

Un servicio con hora de salida exige `HORAS_MINIMAS_RESERVA` horas entre el momento de reservar y esa salida, en la
zona horaria de la sede. Lo que no tiene hora (hospedaje, paquetes) se reserva desde mañana, también con el día de la
sede. Solo aplica a la reserva web: las ventas cerradas a mano por la vendedora (WhatsApp, teléfono) no pasan por aquí.
Con 0 horas la regla está apagada (variable de entorno `HORAS_MINIMAS_RESERVA`, igual que `APARTADO_MINUTOS`).
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def anticipacion_insuficiente(sede, fecha, hora, ahora=None):
    """Texto del error si `fecha` (y `hora`, si la hay) quedan a menos de la anticipación mínima; `None` si cumple."""
    horas = getattr(settings, 'HORAS_MINIMAS_RESERVA', 0)
    if horas <= 0 or fecha is None:
        return None
    zona = ZoneInfo(sede.zona_horaria)
    ahora_sede = (ahora or timezone.now()).astimezone(zona)
    if hora is None:
        if fecha <= ahora_sede.date():
            return 'Elige una fecha a partir de mañana.'
        return None
    salida = datetime.combine(fecha, hora, tzinfo=zona)
    if salida < ahora_sede + timedelta(hours=horas):
        return f'Reserva con al menos {horas} horas de anticipación a la hora de salida.'
    return None
