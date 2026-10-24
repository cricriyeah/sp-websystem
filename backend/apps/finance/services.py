"""Los numeros del panel de dinero, todos sacados de `Reserva`.

No hay tabla de movimientos aparte a proposito: cada peso que se mueve ya deja
su rastro en la reserva que lo genero, y duplicarlo en un libro paralelo solo
abre la puerta a que los dos dejen de cuadrar. Aqui solo se agrupa y se suma.

Cuatro movimientos posibles por reserva, cada uno con su monto y su fecha:

| Movimiento         | Monto               | Fecha                 | Lo sella            |
|--------------------|---------------------|-----------------------|---------------------|
| Entrada tarjeta    | `monto_pagado`      | `pagada_en`           | webhook de Stripe   |
| Entrada efectivo   | `monto_efectivo`    | `efectivo_cobrado_en` | la vendedora        |
| Entrada transferencia | `monto_transferencia` | `transferencia_registrada_en` | la vendedora |
| Salida (reembolso) | `monto_reembolsado` | `reembolsada_en`      | webhook de Stripe   |

Reglas que no hay que romper:

- **Cada moneda se lleva por separado.** Los precios USD se calculan con el
  tipo de cambio de la sede; sumar MXN con USD daria una cifra sin significado.
- **Solo cuenta el dinero que se movio.** `Reserva.reembolsada` es la decision de
  devolver; la salida se registra hasta que Stripe confirma que salio.
- **Las devoluciones de transferencias se hacen fuera del sistema.** No se
  descuentan del saldo teorico del banco.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncDate

from apps.bookings.models import Reserva

CERO = Decimal('0.00')

# (atributo del Balance, campo con el monto, campo con la fecha del movimiento).
MOVIMIENTOS = (
    ('tarjeta', 'monto_pagado', 'pagada_en'),
    ('efectivo', 'monto_efectivo', 'efectivo_cobrado_en'),
    ('transferencia', 'monto_transferencia', 'transferencia_registrada_en'),
    ('reembolsos', 'monto_reembolsado', 'reembolsada_en'),
    # Disputa perdida: Stripe se quedo con el dinero. Sale de la cuenta como un reembolso, pero no lo es.
    ('contracargos', 'contracargo_perdido', 'contracargo_perdido_en'),
)


@dataclass
class Balance:
    """Lo que se movio en una moneda durante un periodo."""

    moneda: str
    tarjeta: Decimal = CERO
    efectivo: Decimal = CERO
    transferencia: Decimal = CERO
    reembolsos: Decimal = CERO
    contracargos: Decimal = CERO

    @property
    def entradas(self):
        return self.tarjeta + self.efectivo + self.transferencia

    @property
    def neto(self):
        """Entradas menos salidas: el balance del periodo."""
        return self.entradas - self.reembolsos - self.contracargos

    @property
    def en_cuenta(self):
        """Lo que deberia haber quedado en Stripe.

        Es bruto: Stripe descuenta su comision antes de depositar y el sistema no
        la registra, asi que el deposito real siempre es un poco menor.
        """
        return self.tarjeta - self.reembolsos - self.contracargos

    @property
    def en_efectivo(self):
        """Lo que deberia haber en caja. Los reembolsos no se descuentan aqui:
        se devuelven por Stripe, salen de la cuenta y no de la caja."""
        return self.efectivo

    @property
    def en_banco(self):
        """Transferencias acumuladas; las devoluciones se hacen fuera del sistema."""
        return self.transferencia

    @property
    def hay_movimiento(self):
        return bool(self.tarjeta or self.efectivo or self.transferencia or self.reembolsos or self.contracargos)


@dataclass
class Movimiento:
    """Una fila de detalle de movimiento de dinero por reserva."""

    fecha: datetime
    reserva: Reserva
    concepto: str
    monto: Decimal
    moneda: str

    def __getitem__(self, item):
        return getattr(self, item)

    @property
    def enlace_stripe(self):
        if self.concepto in ('tarjeta', 'reembolsos', 'contracargos'):
            from apps.bookings.admin import enlace_pago_stripe

            return enlace_pago_stripe(self.reserva)
        return None


def _reservas(empresa):
    return Reserva.objects.filter(empresa=empresa) if empresa is not None else Reserva.objects.all()


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


def balances(desde=None, hasta=None, empresa=None):
    """Balance por moneda del periodo. Sin fechas, todo el historico. Sin
    `empresa`, todas las Empresas juntas (uso: operador de plataforma).

    Devuelve solo las monedas que tuvieron movimiento; un negocio que nunca
    cobro en dolares no tiene por que ver una columna de dolares vacia.
    """
    resultado = {}
    for atributo, campo_monto, campo_fecha in MOVIMIENTOS:
        for fila in _sumar(_reservas(empresa), campo_monto, campo_fecha, desde, hasta):
            balance = resultado.setdefault(fila['moneda'], Balance(moneda=fila['moneda']))
            setattr(balance, atributo, fila['total'] or CERO)
    return dict(sorted(resultado.items()))


def balances_por_dia(desde, hasta, empresa=None):
    """Historico: un balance por dia (y por moneda) del rango pedido.

    Los dias sin un solo movimiento no aparecen — en temporada baja la tabla
    seria mayormente ceros.
    """
    resultado = {}
    for atributo, campo_monto, campo_fecha in MOVIMIENTOS:
        filas = _sumar(
            _reservas(empresa), campo_monto, campo_fecha, desde, hasta, agrupar_por_dia=True
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


def resumen(hoy=None, empresa=None):
    """Todo lo que pinta el panel, en una sola llamada."""
    hoy = hoy or date.today()
    inicio_mes = hoy.replace(day=1)
    inicio_anio = hoy.replace(month=1, day=1)

    return {
        'dia': balances(hoy, hoy, empresa=empresa),
        'mes': balances(inicio_mes, hoy, empresa=empresa),
        'anio': balances(inicio_anio, hoy, empresa=empresa),
        # Sin fechas: el acumulado de siempre, que es contra lo que se cuadra la
        # cuenta bancaria y la caja.
        'acumulado': balances(empresa=empresa),
    }


def movimientos(desde=None, hasta=None, concepto='todos', moneda=None, empresa=None):
    """Devuelve las filas del detalle: una fila por (reserva, concepto).

    Orden: más reciente primero.
    """
    if concepto == 'stripe':
        conceptos_pedidos = {'tarjeta', 'reembolsos', 'contracargos'}
    elif concepto in {'tarjeta', 'efectivo', 'transferencia', 'reembolsos', 'contracargos'}:
        conceptos_pedidos = {concepto}
    else:
        conceptos_pedidos = {'tarjeta', 'efectivo', 'transferencia', 'reembolsos', 'contracargos'}

    filas = []
    base_qs = _reservas(empresa).select_related('empresa')
    if moneda:
        base_qs = base_qs.filter(moneda=moneda)

    for atributo, campo_monto, campo_fecha in MOVIMIENTOS:
        if atributo not in conceptos_pedidos:
            continue
        qs = base_qs.filter(**{f'{campo_monto}__isnull': False, f'{campo_fecha}__isnull': False})
        if desde:
            qs = qs.filter(**{f'{campo_fecha}__date__gte': desde})
        if hasta:
            qs = qs.filter(**{f'{campo_fecha}__date__lte': hasta})

        for reserva in qs:
            monto = getattr(reserva, campo_monto)
            if monto is None:
                continue
            filas.append(
                Movimiento(
                    fecha=getattr(reserva, campo_fecha),
                    reserva=reserva,
                    concepto=atributo,
                    monto=abs(Decimal(str(monto))),
                    moneda=reserva.moneda,
                )
            )

    filas.sort(key=lambda m: (m.fecha, m.reserva.pk), reverse=True)
    return filas


def totales_de_movimientos(filas, concepto='todos', moneda=None):
    """Total por moneda de una lista de movimientos (la que devuelve `movimientos`).

    - Cada concepto individual: suma de sus montos.
    - stripe: tarjeta − reembolsos («En la cuenta»).
    - todos: entradas (tarjeta + efectivo + transferencia) − reembolsos (neto).

    Son los mismos totales que `balances()` para los mismos filtros; hay una prueba que lo exige.
    """
    totales = {}
    if moneda:
        totales[moneda] = CERO

    for fila in filas:
        totales.setdefault(fila.moneda, CERO)
        if fila.concepto in ('reembolsos', 'contracargos') and concepto in ('stripe', 'todos'):
            totales[fila.moneda] -= fila.monto
        else:
            totales[fila.moneda] += fila.monto

    return dict(sorted(totales.items()))
