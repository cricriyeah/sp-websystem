"""Los numeros del panel de dinero, todos sacados de `Reserva`.

No hay tabla de movimientos aparte a proposito: cada peso que se mueve ya deja
su rastro en la reserva que lo genero, y duplicarlo en un libro paralelo solo
abre la puerta a que los dos dejen de cuadrar. Aqui solo se agrupa y se suma.

Tres movimientos posibles por reserva, cada uno con su monto y su fecha:

| Movimiento         | Monto               | Fecha                 | Lo sella            |
|--------------------|---------------------|-----------------------|---------------------|
| Entrada tarjeta    | `monto_pagado`      | `pagada_en`           | webhook de Stripe   |
| Entrada efectivo   | `monto_efectivo`    | `efectivo_cobrado_en` | la vendedora        |
| Salida (reembolso) | `monto_reembolsado` | `reembolsada_en`      | webhook de Stripe   |

Dos reglas que no hay que romper:

- **Cada moneda se lleva por separado.** El negocio fija el precio en pesos y en
  dolares a mano, sin tipo de cambio (ver `fleet.Tarifa`), asi que sumar MXN con
  USD daria una cifra que no significa nada.
- **Solo cuenta el dinero que se movio.** `Reserva.reembolsada` es la decision de
  devolver; la salida se registra hasta que Stripe confirma que salio.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncDate

from apps.bookings.models import Reserva

CERO = Decimal('0.00')

# (atributo del Balance, campo con el monto, campo con la fecha del movimiento).
MOVIMIENTOS = (
    ('tarjeta', 'monto_pagado', 'pagada_en'),
    ('efectivo', 'monto_efectivo', 'efectivo_cobrado_en'),
    ('reembolsos', 'monto_reembolsado', 'reembolsada_en'),
)


@dataclass
class Balance:
    """Lo que se movio en una moneda durante un periodo."""

    moneda: str
    tarjeta: Decimal = CERO
    efectivo: Decimal = CERO
    reembolsos: Decimal = CERO

    @property
    def entradas(self):
        return self.tarjeta + self.efectivo

    @property
    def neto(self):
        """Entradas menos salidas: el balance del periodo."""
        return self.entradas - self.reembolsos

    @property
    def en_cuenta(self):
        """Lo que deberia haber entrado a la cuenta bancaria.

        Es bruto: Stripe descuenta su comision antes de depositar y el sistema no
        la registra, asi que el deposito real siempre es un poco menor.
        """
        return self.tarjeta - self.reembolsos

    @property
    def en_efectivo(self):
        """Lo que deberia haber en caja. Los reembolsos no se descuentan aqui:
        se devuelven por Stripe, salen de la cuenta y no de la caja."""
        return self.efectivo

    @property
    def hay_movimiento(self):
        return bool(self.tarjeta or self.efectivo or self.reembolsos)


def _sumar(qs, campo_monto, campo_fecha, desde=None, hasta=None, agrupar_por_dia=False):
    """Suma un movimiento por moneda (y por dia si se pide).

    El filtro va sobre la fecha del movimiento, no sobre la fecha del viaje: un
    viaje de diciembre que se pago hoy es dinero que entro hoy.
    """
    qs = qs.filter(**{f'{campo_monto}__isnull': False, f'{campo_fecha}__isnull': False})
    if desde:
        qs = qs.filter(**{f'{campo_fecha}__date__gte': desde})
    if hasta:
        qs = qs.filter(**{f'{campo_fecha}__date__lte': hasta})

    agrupacion = ['moneda']
    if agrupar_por_dia:
        qs = qs.annotate(dia=TruncDate(campo_fecha))
        agrupacion = ['dia', 'moneda']

    return qs.values(*agrupacion).annotate(total=Sum(campo_monto))


def balances(desde=None, hasta=None):
    """Balance por moneda del periodo. Sin fechas, todo el historico.

    Devuelve solo las monedas que tuvieron movimiento; un negocio que nunca
    cobro en dolares no tiene por que ver una columna de dolares vacia.
    """
    resultado = {}
    for atributo, campo_monto, campo_fecha in MOVIMIENTOS:
        for fila in _sumar(Reserva.objects.all(), campo_monto, campo_fecha, desde, hasta):
            balance = resultado.setdefault(fila['moneda'], Balance(moneda=fila['moneda']))
            setattr(balance, atributo, fila['total'] or CERO)
    return dict(sorted(resultado.items()))


def balances_por_dia(desde, hasta):
    """Historico: un balance por dia (y por moneda) del rango pedido.

    Los dias sin un solo movimiento no aparecen — en temporada baja la tabla
    seria mayormente ceros.
    """
    resultado = {}
    for atributo, campo_monto, campo_fecha in MOVIMIENTOS:
        filas = _sumar(
            Reserva.objects.all(), campo_monto, campo_fecha, desde, hasta, agrupar_por_dia=True
        )
        for fila in filas:
            del_dia = resultado.setdefault(fila['dia'], {})
            balance = del_dia.setdefault(fila['moneda'], Balance(moneda=fila['moneda']))
            setattr(balance, atributo, fila['total'] or CERO)

    # Mas reciente arriba: lo que se revisa a diario es el cierre de ayer, no el
    # del primero del mes.
    return [
        (dia, dict(sorted(por_moneda.items())))
        for dia, por_moneda in sorted(resultado.items(), reverse=True)
    ]


def resumen(hoy=None):
    """Todo lo que pinta el panel, en una sola llamada."""
    hoy = hoy or date.today()
    inicio_mes = hoy.replace(day=1)
    inicio_anio = hoy.replace(month=1, day=1)

    return {
        'dia': balances(hoy, hoy),
        'mes': balances(inicio_mes, hoy),
        'anio': balances(inicio_anio, hoy),
        # Sin fechas: el acumulado de siempre, que es contra lo que se cuadra la
        # cuenta bancaria y la caja.
        'acumulado': balances(),
    }
