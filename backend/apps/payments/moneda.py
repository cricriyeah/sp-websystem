"""Conversion de pesos a dolares con el tipo de cambio de la sede.

El negocio guarda un solo precio, en MXN. El precio en USD se deriva: cada precio
individual (base, extra, tarifa, personalizacion, minimo de promocion) se convierte
hacia arriba al dolar entero. Como lo que se suma despues (totales, reparto entre
empresas) ya esta en dolares enteros, las lineas siempre cuadran con el total.
"""
from decimal import ROUND_CEILING, Decimal

CENTAVOS = Decimal('0.01')


def convertir(monto_mxn, moneda, tipo_cambio):
    """`monto_mxn` en `moneda`. MXN no cambia; USD = ceil(monto / tipo_cambio) en dolares enteros.

    `None` si no hay monto. `tipo_cambio` (pesos por 1 USD) solo se exige para USD."""
    moneda = (moneda or 'MXN').upper()
    if moneda not in ('MXN', 'USD'):
        raise ValueError(f'Moneda no soportada: {moneda}.')
    if monto_mxn is None:
        return None
    monto = Decimal(monto_mxn)
    if moneda == 'MXN':
        return monto
    if tipo_cambio is None or Decimal(tipo_cambio) <= 0:
        raise ValueError('Falta un tipo de cambio mayor que cero para convertir a USD.')
    dolares = (monto / Decimal(tipo_cambio)).to_integral_value(rounding=ROUND_CEILING)
    return dolares.quantize(CENTAVOS)
