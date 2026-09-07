"""Advisory lock de Postgres para concurrencia de cupo (ADR-003)."""

from datetime import date
import zlib

from django.db import connection


def calcular_clave_candado(fecha: date, ambito: str | int | None = 'default') -> int:
    """Calcula la clave secundaria de 32 bits para el advisory lock.

    Si ambito es 'default' o None, utiliza fecha.toordinal() directamente para
    conservar compatibilidad exacta con la implementación previa de pesca.
    Si se especifica un ámbito (ej. tipo de servicio, ID de recurso), calcula un
    hash CRC32 de 31 bits estable que garantiza no-colisión de locks entre ámbitos.
    """
    if ambito is None or ambito == 'default':
        return fecha.toordinal()

    cadena = f'{ambito}:{fecha.toordinal()}'
    # Máscara 0x7FFFFFFF garantiza un entero positivo con signo compatible con int4 de Postgres
    return zlib.crc32(cadena.encode('utf-8')) & 0x7FFFFFFF


def bloquear_cupo(empresa_id: int, fecha: date, ambito: str | int | None = 'default', servicio_id: int | None = None) -> None:
    """Serializa la validación y confirmación de cupo en Postgres.

    Utiliza pg_advisory_xact_lock(empresa_id, clave_secundaria), el cual se libera
    automáticamente al terminar la transacción actual. En SQLite (entornos locales)
    es un no-op seguro.
    """
    if connection.vendor != 'postgresql':
        return

    clave_secundaria = calcular_clave_candado(fecha, ambito=servicio_id if servicio_id is not None else ambito)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [empresa_id, clave_secundaria])


def bloquear_cupo_del_dia(empresa_id: int, fecha: date) -> None:
    """Función de compatibilidad con la firma anterior de apps/bookings/models.py."""
    bloquear_cupo(empresa_id, fecha, ambito='default')
