"""Todo el calculo de dinero vive aqui, en un solo lugar.

El frontend nunca manda totales ni cantidades: manda que quiere, y el servidor
arma la cifra a partir de la `Reserva` y de la `Tarifa`. Ese mismo calculo se
repite al confirmar el pago para verificar que lo que cobro Stripe es lo que se
debia cobrar.

Que se cobra en linea y que no:

- Tour: precio por viaje (la reserva es de la embarcacion completa).
- Personas extra: cargo por cada una arriba de `PERSONAS_INCLUIDAS`.
- Lunch: precio fijo POR PERSONA. El menu es fijo (no se elige guiso), asi que
  basta con saber cuantos van.
- Bebidas y transporte: **no se cobran en linea**. El precio depende del tipo de
  bebida y de la distancia del traslado, cosas que no se saben al reservar. Se
  registran como solicitud y el agente de ventas las cotiza aparte.
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


def cargo_por_lunch(precio_lunch, numero_personas):
    """Los lunches son uno por persona: comen todos los que van a bordo."""
    return Decimal(precio_lunch) * numero_personas


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
