"""Módulo de lectura cruza-empresa acotado a una Orden.

Bajo RLS, cada empresa solo ve sus propias reservas. Para coordinar el cobro/captura/cancelación
de una orden multi-empresa, esta función utiliza la función SECURITY DEFINER de Postgres
`estado_reservas_de_orden` (o un fallback en SQLite) para inspeccionar el estado de las
reservas pertenecientes a dicha orden sin romper el aislamiento general.
"""
from typing import Any
from django.db import connection


def reservas_de_orden(orden_id: int) -> list[dict[str, Any]]:
    """Devuelve la lista de reservas asociadas a una orden con sus campos clave.

    En Postgres invoca la función SECURITY DEFINER `estado_reservas_de_orden(int)`.
    En SQLite consulta directamente `Reserva` (ya que SQLite no tiene RLS ni funciones almacenadas).
    """
    if connection.vendor != 'postgresql':
        from apps.bookings.models import Reserva

        return [
            {
                'reserva_id': r.id,
                'empresa_id': r.empresa_id,
                'servicio_id': r.servicio_id,
                'estado': r.estado,
                'monto_pagado': r.monto_pagado,
                'monto_reembolsado': r.monto_reembolsado,
                'stripe_payment_intent_id': r.stripe_payment_intent_id,
                'correo_cliente': r.correo_cliente,
            }
            for r in Reserva.objects.filter(orden_id=orden_id)
        ]

    with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM estado_reservas_de_orden(%s)', [orden_id])
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
