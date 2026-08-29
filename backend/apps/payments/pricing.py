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
- Transporte: precio de `fleet.TransportePrecio` por zona, mas recargo desde
  `min_personas_recargo`. Se resuelve por zona (no por distancia real) porque
  eso es lo unico que se sabe al reservar sin depender de geocoding.
- Bebidas: **no se cobra en linea**. El precio depende del tipo de bebida, dato
  que no se sabe al reservar. Se registra como solicitud y el agente de ventas
  la cotiza aparte.
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


def personas_extra(numero_personas):
    """Cuantas personas pasan del cupo incluido en el precio del viaje."""
    return max(0, numero_personas - PERSONAS_INCLUIDAS)


def cargo_por_personas(precio_persona_extra, numero_personas):
    """Cargo total por las personas adicionales."""
    return Decimal(precio_persona_extra) * personas_extra(numero_personas)


def cargo_por_extra(precio, cobrar_por_persona, numero_personas):
    """Cuanto cobra un extra del catalogo (brunch, licencia, carnada) ya
    resuelto en una moneda. `precio` es lo que ya devolvio
    `ExtrasItem.precio_en(moneda)`: esta funcion no sabe que es un ExtrasItem,
    solo suma. None si no hay precio en esa moneda."""
    if precio is None:
        return None
    cantidad = numero_personas if cobrar_por_persona else 1
    return Decimal(precio) * cantidad


def cargo_por_transporte(precio_base, recargo_grupo, min_personas_recargo, numero_personas):
    """precio_base/recargo_grupo ya resueltos en la moneda que toque (ver
    TransportePrecio.precio_en/recargo_en). None si no hay precio base ahi."""
    if precio_base is None:
        return None
    cargo = Decimal(precio_base)
    if numero_personas >= min_personas_recargo:
        cargo += Decimal(recargo_grupo or 0)
    return cargo


def monto_inicial(precio_total, forma_pago):
    """Lo que se cobra en linea: el total, o el 30% si eligio anticipo."""
    if forma_pago == 'anticipo':
        return (precio_total * ANTICIPO_PORCENTAJE).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return Decimal(precio_total).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def a_centavos(monto):
    """Stripe cobra en la unidad minima. Se cuantiza antes de convertir para que
    un Decimal con mas de dos decimales no se trunque de forma silenciosa."""
    return int(Decimal(monto).quantize(CENTAVOS, rounding=ROUND_HALF_UP) * 100)


def de_centavos(centavos):
    return (Decimal(centavos) / 100).quantize(CENTAVOS)
