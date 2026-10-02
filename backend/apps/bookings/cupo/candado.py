"""Advisory lock de Postgres para concurrencia de cupo (ADR-003)."""

from datetime import date
import zlib

from django.db import connection


def calcular_clave_candado(fecha: date, servicio_id: int | None = None) -> int:
    """Una clave por día compartida por todos los servicios de la empresa.

    Se conserva servicio_id en la firma para los llamadores existentes, pero el
    cupo y la flota son comunes a la empresa: no puede haber locks separados.
    """
    return fecha.toordinal()


def bloquear_cupo(empresa_id: int, fecha: date, servicio_id: int | None = None) -> None:
    """Serializa por empresa y fecha la validación de todos sus servicios de mar.

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


def calcular_clave_recurso(recurso_id: int) -> int:
    """Calcula la clave secundaria de 32 bits para el advisory lock de un recurso físico.

    Utiliza el prefijo 'recurso:' con CRC32 acotado con bit 30 forzado (0x40000000),
    garantizando un entero positivo de 32 bits que no colisiona con el path pesca legacy.
    """
    cadena = f'recurso:{recurso_id}'
    return (zlib.crc32(cadena.encode('utf-8')) & 0x3FFFFFFF) | 0x40000000


def bloquear_recurso(empresa_id: int, recurso_id: int) -> None:
    """Serializa la asignación de un recurso físico (hospedaje) en Postgres.

    Utiliza pg_advisory_xact_lock(empresa_id, clave_secundaria), el cual se libera
    automáticamente al terminar la transacción actual. En SQLite es un no-op.
    """
    if connection.vendor != 'postgresql':
        return

    clave_secundaria = calcular_clave_recurso(recurso_id)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [empresa_id, clave_secundaria])

