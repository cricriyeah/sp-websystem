"""Todo el calculo de dinero vive aqui, en un solo lugar.

El frontend nunca manda totales ni cantidades: manda que quiere, y el servidor
arma la cifra a partir de la `Reserva` y del `Servicio`. Ese mismo calculo se
repite al confirmar el pago para verificar que lo que cobro Stripe es lo que se
debia cobrar.

Que se cobra en linea y que no:

- Tour: precio por viaje (la reserva es de la embarcacion completa).
- Personas extra: cargo por cada una arriba de `PERSONAS_INCLUIDAS`.
- Extras del catalogo (brunch, licencia, carnada): precio de `fleet.ServicioPersonalizacion`,
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
# personas no cambia nada; de ahi en adelante se suma `Servicio.precio_persona_extra`
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


def calcular_total(*, estrategia, base, personas, personas_base=1, extra=Decimal('0')):
    """Cálculo único del precio base de algo que se vende por grupo o por persona.

    `por_grupo`: `base` cubre `personas_base`; cada persona de más suma `extra`.
    `por_persona`: `base` es el precio de UNA persona y `personas_base`/`extra` no cuentan.
    `base` y `extra` ya vienen en la moneda del cobro (USD ya convertido, ver `payments.moneda`)."""
    personas = max(1, int(personas))
    if estrategia == 'por_persona':
        total = Decimal(base) * personas
    elif estrategia == 'por_grupo':
        total = Decimal(base) + Decimal(extra) * personas_extra(personas, personas_base)
    else:
        raise ValueError(f'Estrategia de precio no soportada: {estrategia}.')
    return total.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def personas_cobradas(paquete, personas_por_servicio):
    """El grupo cobrado por un paquete es el mayor de sus componentes.

    Recibe el paquete junto con la selección para que reserva y orden compartan
    el mismo contrato; no consulta sus servicios, que pueden estar bajo RLS de
    distintas empresas.
    """
    return max([1, *(int(n) for n in personas_por_servicio.values() if n)])


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
    personas_por_servicio: dict[int, int] | None = None,
    tipo_cambio: Decimal | None = None,
) -> Decimal | None:
    """Precio final de un paquete. None si el paquete no tiene precio en `moneda`.

    Fórmula:
        paquete.precio_total_en(moneda, personas)   # base + extras del grupo, o base × personas
      + Σ  sp.precio_en(moneda) de cada ServicioPersonalizacion (obligatorio o preseleccionado)
           de los servicios componentes, con activo=True
      + Σ  sp.precio_en(moneda) de las ServicioPersonalizacion OPCIONALES que el cliente marcó

    Cada personalización por persona se multiplica por las personas de su servicio.
    Piso 0. Cuantizado a centavos, ROUND_HALF_UP.
    """
    base = paquete.precio_total_en(moneda, personas, tipo_cambio)
    if base is None:
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

    total = base
    vistos = set()
    for ps in paquete.servicios_asociados.filter(servicio__activo=True).select_related('servicio'):
        personas_del_servicio = (personas_por_servicio or {}).get(ps.servicio_id, personas)
        for sp in ps.servicio.servicio_personalizaciones.filter(
            activo=True, personalizacion__activo=True
        ).select_related('personalizacion'):
            if sp.pk in vistos or sp.pk not in extras_map:
                continue
            vistos.add(sp.pk)
            p = sp.personalizacion
            if p.tipo_interaccion != 'check':
                continue
            cargo = cargo_personalizacion(
                sp.precio_en(moneda, tipo_cambio),
                cobrar_por_persona=p.cobrar_por_persona,
                cantidad_editable=p.cantidad_editable,
                personas=personas_del_servicio,
                cantidad=extras_map[sp.pk],
            )
            if cargo is None:
                return None
            total += cargo
    return precio_paquete(total)


def calcular_precio_paquete(paquete, moneda='MXN', tipo_cambio=None):
    """Calcula el precio de un paquete en la moneda pedida.
    Devuelve None si el paquete no tiene precio en esa moneda."""
    return precio_paquete_total(
        paquete,
        personalizaciones_extra=[],
        personas=1,
        moneda=moneda,
        tipo_cambio=tipo_cambio,
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


