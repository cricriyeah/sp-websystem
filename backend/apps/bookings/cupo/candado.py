"""Advisory lock de Postgres para concurrencia de cupo (ADR-003)."""

from datetime import date
import zlib

from django.db import connection


def calcular_clave_candado(fecha: date, servicio_id: int | None = None) -> int:
    """Calcula la clave secundaria de 32 bits para el advisory lock.

    Si servicio_id es None, utiliza fecha.toordinal() directamente para
    conservar compatibilidad exacta con la implementación previa de pesca legacy.
    Si servicio_id es un entero, calcula un hash CRC32 acotado con bit 30
    forzado (0x40000000), lo cual garantiza un entero positivo con signo de 32 bits
    que nunca colisiona con un toordinal() realista.
    """
    ordinal = fecha.toordinal()
    if servicio_id is None:
        return ordinal

    cadena = f'{servicio_id}:{ordinal}'
    return (zlib.crc32(cadena.encode('utf-8')) & 0x3FFFFFFF) | 0x40000000


def bloquear_cupo(empresa_id: int, fecha: date, servicio_id: int | None = None) -> None:
    """Serializa la validación y confirmación de cupo en Postgres.

    Utiliza pg_advisory_xact_lock(empresa_id, clave_secundaria), el cual se libera
    automáticamente al terminar la transacción actual. En SQLite (entornos locales)
    es un no-op seguro.
    """
    if connection.vendor != 'postgresql':
        return

    clave_secundaria = calcular_clave_candado(fecha, servicio_id=servicio_id)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [empresa_id, clave_secundaria])


def bloquear_cupo_del_dia(empresa_id: int, fecha: date) -> None:
    """Función de compatibilidad con la firma anterior de apps/bookings/models.py."""
    bloquear_cupo(empresa_id, fecha, servicio_id=None)
