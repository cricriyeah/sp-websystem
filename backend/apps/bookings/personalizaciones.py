"""Selección de extras (personalizaciones) de una Reserva: validar y sincronizar.

Compartido por el serializador de reservas y por la creación de órdenes."""
from django.core.exceptions import ValidationError

from apps.bookings.models import ReservaPersonalizacion
from apps.fleet.models import ServicioPersonalizacion


def validar_respuesta(sp, item):
    """Lanza ValidationError si la respuesta del cliente no cabe en la personalización."""
    ReservaPersonalizacion(
        servicio_personalizacion=sp,
        cantidad=item.get('cantidad', 1),
        respuesta=item.get('respuesta', ''),
    ).clean()


def validar_seleccion(servicio, items):
    """Cada extra pertenece a `servicio`, está activo y no se repite; nada obligatorio queda sin responder."""
    disponibles = {
        sp.pk: sp
        for sp in ServicioPersonalizacion.objects.filter(
            servicio=servicio, activo=True, personalizacion__activo=True,
        ).select_related('personalizacion')
    }
    vistos = set()
    for item in items:
        sp = disponibles.get(item.get('id'))
        if sp is None or sp.pk in vistos:
            raise ValidationError({'personalizaciones': 'Selección inválida o repetida.'})
        vistos.add(sp.pk)
        validar_respuesta(sp, item)
    for sp in disponibles.values():
        if sp.personalizacion.tipo_interaccion != 'check' and sp.obligatorio and sp.pk not in vistos:
            raise ValidationError({'personalizaciones': f'Falta responder: {sp.personalizacion.nombre}.'})


def sincronizar(reserva, items):
    """Reescribe la selección completa de la reserva (lista vacía = borra lo que hubiera)."""
    reserva.personalizaciones_seleccionadas.all().delete()
    for item in items:
        respuesta = item.get('respuesta', '')
        sp = ServicioPersonalizacion.objects.select_related('personalizacion').get(pk=item['id'])
        if sp.personalizacion.tipo_interaccion != 'check' and not respuesta.strip():
            continue
        fila = ReservaPersonalizacion(
            reserva=reserva, servicio_personalizacion=sp,
            cantidad=item.get('cantidad', 1), respuesta=respuesta,
        )
        fila.full_clean()
        fila.save()
