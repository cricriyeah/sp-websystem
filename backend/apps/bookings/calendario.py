"""Calendario del backoffice: de reservas a eventos y estancias.

Es el modulo puro de `/admin/calendario/` (la vista esta en `vistas_calendario.py`).
Solo lee: no toca cobro, cupo ni estados, y no hay tabla de calendario — todo sale de
`Reserva` (y de sus tramos y salidas), igual que el panel de finanzas.

Dos formas de ocupar el tiempo:

- **Evento**: algo de un dia, con hora. Un viaje de mar suelto, un tramo de traslado
  o, solo en la vista Dia, cada dia de mar de un paquete.
- **Estancia**: una barra de varios dias. Un hospedaje, o un paquete de una empresa.

Regla que manda: **una reserva, una marca por vista**. Un paquete es SOLO su barra en
Semana y Mes; sus dias de mar no se repiten como eventos sueltos (`dias_de_mar=False`).
En la vista Dia si son renglones propios, que es donde se reparten. El hallazgo cuenta
**reservas**, nunca eventos ni tramos.

Que estados se ven: pagada, asignada y completada; la cancelada solo con el
interruptor; la `pendiente_pago` NUNCA (cada checkout abandonado deja una y
llenarian el calendario — para eso esta "Checkouts abandonados").

"Sin panga" y "atrasada" salen de la misma regla que la Agenda (`sin_lo_que_no_se_reparte`
y el criterio `pagada` + fecha de hoy o pasada); este modulo solo la estrecha:
un hospedaje y un paquete sin nada de mar nunca piden panga.
"""
from dataclasses import dataclass
from datetime import date, time, timedelta

from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.fleet.models import Embarcacion, PaqueteServicio

from .cupo.adaptador import obtener_contexto_rango
from .cupo.nucleo import motivo_sin_lugar
from .models import ESTADOS_QUE_OCUPAN_CUPO, Reserva, ReservaSalida, ViajeTransporte
from .panorama import sin_lo_que_no_se_reparte

SIN_PANGA = 'sin_panga'
ATRASADA = 'atrasada'

# Tipos de evento.
MAR = 'mar'
DIA_DE_MAR = 'dia_de_mar'
TRASLADO = 'traslado'

# Tipos de estancia.
HOSPEDAJE = 'hospedaje'
PAQUETE = 'paquete'

# Ida antes que regreso cuando comparten dia y hora.
_ORDEN_DE_SENTIDO = {'unico': 0, 'ida': 1, 'regreso': 2}


def _pagado(reserva):
    """Lo cobrado por las tres vias (tarjeta, efectivo, transferencia)."""
    return (reserva.monto_pagado or 0) + (reserva.monto_efectivo or 0) + (reserva.monto_transferencia or 0)


@dataclass(frozen=True)
class Pieza:
    """Lo comun de lo que se pinta: la reserva y como se ve."""

    reserva: Reserva
    # Como se pinta: asignada, completada, cancelada, sin_panga o atrasada. Un hospedaje o
    # un paquete pagado sin nada de mar que repartir se pinta como asignado.
    estilo: str
    # SIN_PANGA / ATRASADA / None. Una marca por reserva, igual en todas sus piezas.
    marca: str | None

    @property
    def pagado(self):
        return _pagado(self.reserva)


@dataclass(frozen=True)
class Evento(Pieza):
    """Algo de un dia. `tramo` es el `ViajeTransporte` cuando es un traslado."""

    fecha: date
    hora: time | None
    tipo: str
    tramo: ViajeTransporte | None = None

    @property
    def sentido(self):
        return self.tramo.sentido if self.tramo else ''


@dataclass(frozen=True)
class Estancia(Pieza):
    """Una barra de `inicio` a `fin` (la salida, exclusiva, como `fecha_fin_servicio`)."""

    inicio: date
    fin: date
    tipo: str
    # Solo con hospedaje; un paquete sin hospedaje dura lo que duran sus dias de mar.
    noches: int | None
    dias_de_mar: int

    @property
    def ultimo_dia(self):
        return self.fin - timedelta(days=1)


@dataclass(frozen=True)
class Hallazgo:
    """Reservas del periodo: cuantas hay y cuantas piden algo. Nunca eventos."""

    total: int = 0
    sin_panga: int = 0
    atrasadas: int = 0

    @property
    def todo_asignado(self):
        return self.total > 0 and not (self.sin_panga or self.atrasadas)


@dataclass(frozen=True)
class Calendario:
    desde: date
    hasta: date
    eventos: list
    estancias: list
    hallazgo: Hallazgo


@dataclass(frozen=True)
class TiraDia:
    """Los viajes vendidos de un dia sobre lo que el motor de cupo deja salir."""

    fecha: date
    ocupadas: int
    capacidad: int
    # El dia ya no admite otra salida, ni de una persona.
    lleno: bool
    # El negocio cerro el dia (`CupoDiario` en 0).
    cerrado: bool


def _estilo(estado, marca):
    if estado == Reserva.Estado.CANCELADA:
        return 'cancelada'
    if marca:
        return marca
    if estado == Reserva.Estado.COMPLETADA:
        return 'completada'
    return 'asignada'


def _dias_de_mar_de_paquete(reserva):
    """Los dias de mar de un paquete: sus salidas, o su fecha si solo tiene una. Vacio si no hay mar.

    `ReservaSalida` solo existe cuando una actividad se repite (`salidas > 1`); con una
    sola salida el dia es `Reserva.fecha`. Que el paquete tenga mar sale de su catalogo.
    """
    if not any(
        ps.servicio.estrategia_cupo == 'por_recurso_dia' for ps in reserva.paquete.servicios_asociados.all()
    ):
        return []
    return sorted({salida.fecha for salida in reserva.salidas.all()}) or [reserva.fecha]


def _es_paquete(reserva):
    """Paquete de una empresa. Una reserva de orden lleva servicio y se trata por el."""
    return reserva.servicio_id is None and reserva.paquete_id is not None


def _pide_panga(reserva, dias_de_mar):
    """Lo estrecha sobre la Agenda: hospedaje y paquete sin mar no reparten panga."""
    if _es_paquete(reserva):
        return bool(dias_de_mar)
    if reserva.servicio_id is None:
        return True  # pesca anterior a los servicios, ver Reserva.clean()
    return reserva.servicio.estrategia_cupo == 'por_recurso_dia'


def _marca(reserva, dias_de_mar, hoy, a_repartir):
    """SIN_PANGA / ATRASADA / None. Misma regla que `Agenda.aviso`: pagada sin panga y pasada es atrasada."""
    if reserva.estado != Reserva.Estado.PAGADA or reserva.embarcacion_id:
        return None
    if reserva.pk not in a_repartir or not _pide_panga(reserva, dias_de_mar):
        return None
    return ATRASADA if reserva.fecha < hoy else SIN_PANGA


def _reservas_del_periodo(desde, hasta, empresa, canceladas):
    """`(reservas, filtradas)`: las que tocan el periodo y la consulta base, sin joins."""
    estados = list(ESTADOS_QUE_OCUPAN_CUPO)
    if canceladas:
        estados.append(Reserva.Estado.CANCELADA)
    # Un viaje cae en el periodo por su fecha; una estancia por solaparse con el; un paquete
    # sin hospedaje por sus salidas; un traslado por cualquiera de sus tramos (el regreso
    # puede ser de otra semana que la reserva).
    toca_el_periodo = (
        Q(fecha__range=(desde, hasta))
        | Q(fecha_salida__gt=desde) & (
            Q(inicio_paquete__lte=hasta) | Q(inicio_paquete__isnull=True, fecha__lte=hasta)
        )
        | Q(paquete__isnull=False, inicio_paquete__lte=hasta, fecha__gte=desde)
        | Q(pk__in=ReservaSalida.objects.filter(fecha__range=(desde, hasta)).values('reserva_id'))
        | Q(pk__in=ViajeTransporte.objects.filter(fecha__range=(desde, hasta)).values('reserva_id'))
    )
    filtradas = Reserva.objects.filter(toca_el_periodo, estado__in=estados)
    if empresa is not None:
        filtradas = filtradas.filter(empresa=empresa)
    reservas = filtradas.select_related(
        'empresa', 'servicio', 'paquete', 'embarcacion', 'capitan', 'vendedora__usuario',
    ).prefetch_related(
        'salidas',
        Prefetch('viajes_transporte', queryset=ViajeTransporte.objects.select_related('vehiculo')),
        Prefetch('paquete__servicios_asociados', queryset=PaqueteServicio.objects.select_related('servicio')),
    )
    return reservas, filtradas


def armar_calendario(desde, hasta, empresa=None, *, canceladas=False, dias_de_mar=False, hoy=None):
    """Eventos, estancias y hallazgo de `desde` a `hasta` (inclusive), de una empresa o de todas.

    `dias_de_mar` solo se pide en la vista Dia: ahi cada dia de mar de un paquete es un
    renglon propio. En Semana y Mes el paquete es solo su barra.

    Cuatro consultas fijas para cualquier numero de reservas (reservas, salidas, tramos y
    componentes de paquete) mas una para saber cuales reparte la Agenda; ninguna por fila.
    """
    hoy = hoy or timezone.localdate()
    reservas, filtradas = _reservas_del_periodo(desde, hasta, empresa, canceladas)
    a_repartir = set(
        sin_lo_que_no_se_reparte(
            filtradas.filter(estado=Reserva.Estado.PAGADA, embarcacion__isnull=True)
        ).values_list('pk', flat=True)
    )

    eventos, estancias = [], []
    presentes = {}  # reserva.pk -> marca, solo las que cuentan para el hallazgo

    def presente(reserva, marca):
        if reserva.estado != Reserva.Estado.CANCELADA:
            presentes[reserva.pk] = marca

    for reserva in reservas:
        dias_mar = _dias_de_mar_de_paquete(reserva) if _es_paquete(reserva) else []
        marca = _marca(reserva, dias_mar, hoy, a_repartir)
        estilo = _estilo(reserva.estado, marca)
        servicio = reserva.servicio

        if _es_paquete(reserva):
            inicio = reserva.fecha_inicio_paquete
            if reserva.fecha_salida:
                fin, noches = reserva.fecha_salida, (reserva.fecha_salida - inicio).days
            else:
                fin, noches = (max(dias_mar) if dias_mar else inicio) + timedelta(days=1), None
            fin = max(fin, inicio + timedelta(days=1))
            if inicio <= hasta and fin > desde:
                estancias.append(Estancia(reserva, estilo, marca, inicio, fin, PAQUETE, noches, len(dias_mar)))
                presente(reserva, marca)
            if dias_de_mar:
                for dia in dias_mar:
                    if desde <= dia <= hasta:
                        eventos.append(Evento(reserva, estilo, marca, dia, reserva.hora, DIA_DE_MAR))
        elif servicio is not None and servicio.tipo_servicio == 'transporte':
            for tramo in reserva.viajes_transporte.all():
                if not desde <= tramo.fecha <= hasta or (tramo.cancelado and not canceladas):
                    continue
                cancelado = tramo.cancelado or reserva.estado == Reserva.Estado.CANCELADA
                eventos.append(Evento(
                    reserva, 'cancelada' if cancelado else estilo, marca, tramo.fecha, tramo.hora, TRASLADO, tramo,
                ))
                if not tramo.cancelado:
                    presente(reserva, marca)
        elif servicio is not None and servicio.estrategia_cupo == 'por_noche':
            inicio, fin = reserva.fecha, reserva.fecha_fin_servicio
            if inicio <= hasta and fin > desde:
                estancias.append(Estancia(reserva, estilo, marca, inicio, fin, HOSPEDAJE, reserva.noches, 0))
                presente(reserva, marca)
        elif desde <= reserva.fecha <= hasta:
            eventos.append(Evento(reserva, estilo, marca, reserva.fecha, reserva.hora, MAR))
            presente(reserva, marca)

    eventos.sort(key=lambda e: (
        e.fecha, e.hora is None, e.hora or time.min, e.reserva.pk, _ORDEN_DE_SENTIDO.get(e.sentido, 0),
    ))
    estancias.sort(key=lambda e: (e.inicio, e.reserva.pk))

    marcas = list(presentes.values())
    hallazgo = Hallazgo(
        total=len(marcas), sin_panga=marcas.count(SIN_PANGA), atrasadas=marcas.count(ATRASADA),
    )
    return Calendario(desde, hasta, eventos, estancias, hallazgo)


def tira_de_pangas(desde, hasta, empresa):
    """`{fecha: TiraDia}` para una empresa, o None si no tiene pangas activas.

    Sale del mismo contexto que `/api/cupo/` y la validacion del cupo
    (`obtener_contexto_rango`) y decide "lleno" con el mismo nucleo puro
    (`motivo_sin_lugar`), no con un calculo aparte: asi la tira no puede decir que
    hay lugar cuando el sistema ya rechaza la venta. La flota del dia ya descuenta las
    pangas fuera de servicio, y la capacidad es lo menor entre esa flota y el tope del
    dia (`CupoDiario`), que son los dos limites independientes del motor.
    """
    if not Embarcacion.objects.filter(empresa=empresa, activa=True).exists():
        return None
    contexto = obtener_contexto_rango(desde, hasta, empresa)
    tira = {}
    for fecha in contexto.fechas:
        grupos = contexto.grupos_por_fecha.get(fecha, [])
        capacidades = contexto.capacidades_por_fecha[fecha]
        tope = contexto.topes_por_fecha[fecha]
        tira[fecha] = TiraDia(
            fecha=fecha,
            ocupadas=len(grupos),
            capacidad=min(tope, len(capacidades)),
            lleno=motivo_sin_lugar(1, grupos, capacidades, tope) is not None,
            cerrado=tope == 0,
        )
    return tira
