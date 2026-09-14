"""Todo el calculo de dinero vive aqui, en un solo lugar.

El frontend nunca manda totales ni cantidades: manda que quiere, y el servidor
arma la cifra a partir de la `Reserva` y de la `Tarifa`. Ese mismo calculo se
repite al confirmar el pago para verificar que lo que cobro Stripe es lo que se
debia cobrar.

Que se cobra en linea y que no:

- Tour: precio por viaje (la reserva es de la embarcacion completa).
- Personas extra: cargo por cada una arriba de `PERSONAS_INCLUIDAS`.
- Extras del catalogo (brunch, licencia, carnada): precio de `fleet.ExtrasItem`,
  por persona o plano segun `cobrar_por_persona`. El precio que se congela es
  siempre el vigente del catalogo al momento de pagar, nunca el que trae la
  reserva desde que se armo el checkout (ver `CrearPagoView`).
- Bebidas: **no se cobra en linea**. El precio depende del tipo de bebida, dato
  que no se sabe al reservar. Se registra como solicitud y el agente de ventas
  la cotiza aparte.
- Codigo promocional: descuento porcentual sobre el subtotal de arriba (tour +
  personas + extras), nunca sobre uno inventado por el cliente.
  El checkout solo manda el string del codigo; que exista, siga vigente y
  tenga usos disponibles se valida en `fleet.CodigoPromocional`/
  `apps.bookings.models.codigo_promocional_valido`, no aqui.
"""
from decimal import ROUND_HALF_UP, Decimal

# El precio del tour es por viaje, no por persona. Hasta esta cantidad de
# personas no cambia nada; de ahi en adelante se suma `Tarifa.precio_persona_extra`
# por cada una. El corte es 3 porque es la capacidad de la embarcacion chica:
# pasando de ahi hace falta una grande (ver docs/contexto-negocio.md).
PERSONAS_INCLUIDAS = 3

# 30% de anticipo en linea, 70% en efectivo el dia del viaje
# (ver docs/contexto-negocio.md, seccion Pagos).
ANTICIPO_PORCENTAJE = Decimal('0.30')

CENTAVOS = Decimal('0.01')


def personas_extra(numero_personas, personas_incluidas=PERSONAS_INCLUIDAS):
    """Cuantas personas pasan del cupo incluido en el precio del viaje."""
    return max(0, numero_personas - personas_incluidas)


def cargo_por_personas(precio_persona_extra, numero_personas, personas_incluidas=PERSONAS_INCLUIDAS):
    """Cargo total por las personas adicionales."""
    return Decimal(precio_persona_extra) * personas_extra(numero_personas, personas_incluidas)


def cargo_por_extra(precio, cobrar_por_persona, numero_personas):
    """Cuanto cobra un extra del catalogo (brunch, licencia, carnada) ya
    resuelto en una moneda. `precio` es lo que ya devolvio
    `ExtrasItem.precio_en(moneda)`: esta funcion no sabe que es un ExtrasItem,
    solo suma. None si no hay precio en esa moneda."""
    if precio is None:
        return None
    cantidad = numero_personas if cobrar_por_persona else 1
    return Decimal(precio) * cantidad


def cantidad_efectiva(*, cobrar_por_persona, cantidad_editable, personas, cantidad=1):
    if not cobrar_por_persona:
        return 1
    if not cantidad_editable:
        return personas
    return max(1, min(cantidad, personas))


def cargo_personalizacion(
    precio,
    *,
    cobrar_por_persona,
    cantidad_editable,
    personas,
    cantidad=1,
):
    if precio is None:
        return None
    return Decimal(precio) * cantidad_efectiva(
        cobrar_por_persona=cobrar_por_persona,
        cantidad_editable=cantidad_editable,
        personas=personas,
        cantidad=cantidad,
    )


def cargo_por_descuento(precio_total, porcentaje_descuento):
    """Cuanto se resta del subtotal por un codigo promocional ya validado
    (ver apps/bookings/models.py, codigo_promocional_valido). Redondeado a
    centavos igual que el resto de los cargos."""
    descuento = Decimal(precio_total) * Decimal(porcentaje_descuento) / 100
    return descuento.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def monto_inicial(precio_total, forma_pago, porcentaje=None):
    """Lo que se cobra en linea: el total, o el % si eligio anticipo."""
    if forma_pago == 'anticipo':
        pct = (Decimal(porcentaje) / Decimal('100')) if porcentaje is not None else ANTICIPO_PORCENTAJE
        return (Decimal(precio_total) * pct).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return Decimal(precio_total).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def a_centavos(monto):
    """Stripe cobra en la unidad minima. Se cuantiza antes de convertir para que
    un Decimal con mas de dos decimales no se trunque de forma silenciosa."""
    return int(Decimal(monto).quantize(CENTAVOS, rounding=ROUND_HALF_UP) * 100)


def de_centavos(centavos):
    return (Decimal(centavos) / 100).quantize(CENTAVOS)


def precio_paquete(precio):
    """Calcula el precio final de un paquete a partir de su precio base.
    Garantiza un piso de 0.00."""
    if precio is None:
        return None
    return max(Decimal('0.00'), Decimal(precio)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def precio_paquete_total(
    paquete,
    *,
    personalizaciones_extra: list[tuple[int, int]] | list[int] | dict[int, int] | None = None,
    personas: int = 1,
    moneda: str = 'MXN',
) -> Decimal | None:
    """Precio final de un paquete. None si el paquete no tiene precio en `moneda`.

    Fórmula:
        paquete.precio_en(moneda)                                              # el ancla
      + Σ  sp.precio_en(moneda) de cada ServicioPersonalizacion (obligatorio o preseleccionado)
           de los servicios componentes, con activo=True
      + Σ  sp.precio_en(moneda) de las ServicioPersonalizacion OPCIONALES que el cliente marcó

    Cada personalización que cobrar_por_persona se multiplica por personas.
    Piso 0. Cuantizado a centavos, ROUND_HALF_UP.
    """
    precio_ancla = paquete.precio_en(moneda)
    if precio_ancla is None:
        return None

    extras_map: dict[int, int] = {}
    if personalizaciones_extra:
        if isinstance(personalizaciones_extra, dict):
            extras_map = dict(personalizaciones_extra)
        else:
            for item in personalizaciones_extra:
                if isinstance(item, (tuple, list)):
                    extras_map[item[0]] = item[1]
                else:
                    extras_map[item] = 1

    total = Decimal(precio_ancla)

    for ps in paquete.servicios_asociados.select_related('servicio').all():
        for sp in ps.servicio.servicio_personalizaciones.select_related('personalizacion').all():
            if not sp.activo or not sp.personalizacion.activo:
                continue

            es_incluida = sp.obligatorio or sp.preseleccionado
            es_extra = sp.id in extras_map

            if not es_incluida and not es_extra:
                continue

            sp_precio = sp.precio_en(moneda)
            if sp_precio is None:
                continue

            mult = Decimal(personas) if sp.personalizacion.cobrar_por_persona else Decimal('1')
            cant = Decimal(extras_map[sp.id]) if es_extra else Decimal('1')
            total += Decimal(sp_precio) * mult * cant

    return max(Decimal('0.00'), total).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def calcular_precio_paquete(paquete, moneda='MXN'):
    """Calcula el precio de un paquete en la moneda pedida.
    Devuelve None si el paquete no tiene precio en esa moneda."""
    return precio_paquete_total(
        paquete,
        personalizaciones_extra=[],
        personas=1,
        moneda=moneda,
    )


def monto_por_empresa(*, precio_paquete, componentes, moneda):
    """Reparte el precio fijo del paquete entre las cuentas de cada empresa.
    Regla (decisión del dueño 2026-09-07): cada componente de tipo conocido
    (transporte) va a su tarifa; la empresa líder (pesca) absorbe el residuo.

    `componentes`: lista de dicts
      {'empresa_id': int, 'es_lider': bool, 'monto_fijo': Decimal | None}
    donde `monto_fijo` es el precio de TransporteTarifa ya resuelto para los
    componentes de transporte, y None para el/los que absorben el residuo.
    Devuelve {empresa_id: Decimal}. Lanza ValueError si el residuo es negativo
    o si no hay exactamente un componente con monto_fijo=None (el líder)."""
    fijos = {c['empresa_id']: Decimal(c['monto_fijo']).quantize(CENTAVOS, rounding=ROUND_HALF_UP) for c in componentes if c.get('monto_fijo') is not None}
    lideres = [c for c in componentes if c.get('monto_fijo') is None]
    if len(lideres) != 1:
        raise ValueError('Debe haber exactamente un componente que absorba el residuo (la empresa líder).')
    residuo = Decimal(precio_paquete) - sum(fijos.values(), Decimal('0'))
    if residuo < 0:
        raise ValueError(f'El precio del paquete ({precio_paquete}) es menor que la suma de los montos fijos ({sum(fijos.values())}).')
    reparto = dict(fijos)
    reparto[lideres[0]['empresa_id']] = residuo.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return reparto


