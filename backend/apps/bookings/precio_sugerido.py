"""Modulo para sugerir el precio total al registrar una reserva en el backoffice.

Reutiliza la logica de pricing del checkout web (apps.payments.estrategias_precio,
apps.fleet.tarifa_transporte y Paquete.precio_total_en) sin duplicar reglas de cobro.
"""

from decimal import Decimal
from typing import Any

from apps.bookings.models import Reserva
from apps.fleet.enums import EstrategiaPrecio, TipoServicio, TipoTraslado
from apps.fleet.tarifa_transporte import TarifaTransporteNoConfigurada
from apps.payments.estrategias_precio import (
    DemandaPrecio,
    REGISTRO_ESTRATEGIAS_PRECIO,
    obtener_estrategia_precio,
)
from apps.payments.pricing import CENTAVOS


def sugerir_precio(
    *,
    servicio=None,
    paquete=None,
    numero_personas,
    moneda,
    fecha=None,
    detalle_transporte=None,
) -> Decimal | None:
    """Devuelve Decimal (dos decimales) o None si no hay forma de calcularlo.

    Calcula el precio sugerido con la misma logica del servidor en el checkout web.
    - `servicio` y `paquete` son excluyentes.
    - `moneda` debe ser 'MXN' o 'USD'.
    - `numero_personas` debe ser un entero >= 1.
    - `detalle_transporte` es un dict opcional con datos del traslado.
    - `fecha` es opcional (el pricing actual no depende de fecha, pero se acepta por contrato).
    """
    # 1. Validar exclusion mutua entre servicio y paquete
    if (servicio is None and paquete is None) or (servicio is not None and paquete is not None):
        return None

    # 2. Validar numero de personas (debe ser entero >= 1, excluyendo booleanos)
    if numero_personas is None or isinstance(numero_personas, bool):
        return None
    try:
        personas_int = int(numero_personas)
    except (TypeError, ValueError):
        return None
    if personas_int < 1:
        return None

    # 3. Validar moneda segun valores de Reserva.Moneda
    if not moneda:
        return None
    moneda_str = str(moneda).upper()
    if moneda_str not in (Reserva.Moneda.MXN, Reserva.Moneda.USD):
        return None

    # 4. Obtener tipo de cambio de la sede si el cobro es en USD
    tipo_cambio = None
    if moneda_str == Reserva.Moneda.USD:
        try:
            if servicio is not None:
                empresa = getattr(servicio, 'empresa', None)
                sede = getattr(empresa, 'sede', None) if empresa else None
            else:
                sede = getattr(paquete, 'sede', None)
                if not sede:
                    empresa_lider = getattr(paquete, 'empresa_lider', None)
                    sede = getattr(empresa_lider, 'sede', None) if empresa_lider else None
            tipo_cambio = getattr(sede, 'tipo_cambio_usd', None) if sede else None
        except Exception:
            tipo_cambio = None

        # Sin tipo de cambio positivo, no es posible calcular precios en USD
        if tipo_cambio is None or Decimal(tipo_cambio) <= Decimal('0.0000'):
            return None

    # 5. Caso Paquete
    if paquete is not None:
        try:
            # Paquetes cruza-empresa se tramitan como Orden, no como Reserva
            if getattr(paquete, 'es_cruza_empresa', False):
                return None

            # Un paquete sin precio ancla o con precio <= 0 no tiene tarifa valida
            precio_ancla = getattr(paquete, 'precio_ancla', None)
            if precio_ancla is None or Decimal(precio_ancla) <= Decimal('0.00'):
                return None

            # Reutiliza el calculo de paquete de apps.fleet (que llama a calcular_total)
            total = paquete.precio_total_en(moneda_str, personas_int, tipo_cambio)
            if total is None or Decimal(total) <= Decimal('0.00'):
                return None
            return Decimal(total).quantize(CENTAVOS)
        except Exception:
            return None

    # 6. Caso Servicio
    try:
        es_traslado = (
            getattr(servicio, 'estrategia_precio', None) == EstrategiaPrecio.POR_RUTA
            or getattr(servicio, 'tipo_servicio', None) == TipoServicio.TRANSPORTE
        )

        if es_traslado:
            # Un traslado exige datos de ruta en detalle_transporte para poder cotizar
            if not detalle_transporte:
                return None

            if isinstance(detalle_transporte, dict):
                tipo_traslado = detalle_transporte.get('tipo_traslado')
                zona = detalle_transporte.get('zona') or ''
                p_traslado = detalle_transporte.get('numero_personas')
            else:
                tipo_traslado = getattr(detalle_transporte, 'tipo_traslado', None)
                if hasattr(detalle_transporte, 'zona_efectiva'):
                    zona = detalle_transporte.zona_efectiva()
                else:
                    zona = getattr(detalle_transporte, 'zona', '') or ''
                p_traslado = getattr(detalle_transporte, 'numero_personas', None)

            if not tipo_traslado:
                return None

            # Resolver cantidad de personas para el traslado
            if p_traslado is None:
                personas_traslado = personas_int
            else:
                try:
                    personas_traslado = int(p_traslado)
                except (TypeError, ValueError):
                    return None
                if personas_traslado < 1:
                    return None

            # Normalizar zona segun tipo de traslado: solo redondo_actividad depende de zona
            if tipo_traslado != TipoTraslado.REDONDO_ACTIVIDAD:
                zona = ''
            elif not zona:
                # Redondo actividad exige zona para determinar tarifa
                return None

            empresa = getattr(servicio, 'empresa', None)
            if not empresa:
                return None

            tarifas = list(empresa.tarifas_transporte.filter(activo=True))
            if not tarifas:
                return None

            demanda = DemandaPrecio(
                personas=personas_traslado,
                moneda=moneda_str,
                tipo_traslado=tipo_traslado,
                zona=zona,
                tipo_cambio=tipo_cambio,
            )
            servicio_config = {'tarifas_transporte_activas': tarifas}
            estrategia = obtener_estrategia_precio(EstrategiaPrecio.POR_RUTA)
            precio = estrategia.calcular_base(servicio_config, demanda)
            if precio is None or Decimal(precio) <= Decimal('0.00'):
                return None
            return Decimal(precio).quantize(CENTAVOS)

        # Servicios no traslado: validar que la estrategia este registrada
        estrategia_clave = getattr(servicio, 'estrategia_precio', None)
        if estrategia_clave not in REGISTRO_ESTRATEGIAS_PRECIO:
            return None

        # Servicios sin precio base o bajo demanda sin tarifa
        precio_base = getattr(servicio, 'precio_base', None)
        if precio_base is None or Decimal(precio_base) <= Decimal('0.00'):
            return None

        estrategia = obtener_estrategia_precio(estrategia_clave)
        demanda = DemandaPrecio(
            personas=personas_int,
            moneda=moneda_str,
            tipo_cambio=tipo_cambio,
        )
        precio = estrategia.calcular_base(servicio, demanda)
        if precio is None or Decimal(precio) <= Decimal('0.00'):
            return None
        return Decimal(precio).quantize(CENTAVOS)

    except (ValueError, TarifaTransporteNoConfigurada):
        return None
    except Exception:
        return None
