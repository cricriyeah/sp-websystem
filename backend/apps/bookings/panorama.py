"""La cuadricula de dias x pangas que va arriba de la agenda.

Responde la pregunta que la tabla no responde. La tabla dice que viajes hay y
quien los lleva; cuando se reparte, lo que uno se pregunta es al reves: **que
panga me queda libre el jueves**. Con la flota fija en diez y una sola salida por
panga al dia, esa respuesta cabe entera en una cuadricula sin scroll.

Es solo lectura a proposito. Repartir se sigue haciendo en la tabla, con sus
selectores y su validacion; esto solo ensena el panorama.

Todo sale en **cuatro consultas fijas** para la cuadricula completa — reservas del
rango, pangas activas, las marcadas fuera de servicio y los viajes atrasados — sin
ninguna por celda. Con la flota completa y una semana son setenta celdas: una
consulta por celda seria setenta consultas para pintar una tabla.

La cuadricula tambien es la superficie donde se asigna: cada celda y cada viaje sin
panga llevan sus datos (`data-*`) para que `panorama.js` deje elegir la panga desde
aqui. Lo que se guarda sigue siendo el selector de la tabla, con su validacion.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db.models import Q

from apps.fleet.models import Embarcacion, EmbarcacionNoDisponible

from .cupo.adaptador import obtener_contexto_rango
from .cupo.apartado import apartado_activo, demanda_apartada_por_rango
from .models import ESTADOS_QUE_OCUPAN_CUPO, Reserva

DIAS_DEL_PANORAMA = 7


def sin_lo_que_no_se_reparte(queryset):
    """Quita lo que la Agenda de pangas NO reparte: servicios bajo demanda y traslados.

    Es el criterio de la tabla de la Agenda y del panorama; si cada uno lo escribiera por su
    lado pasaba lo que pasaba: la cuadricula mostraba reservas que la lista de abajo no tenia.
    Las reservas sin servicio (paquetes) se conservan.
    """
    return queryset.exclude(
        Q(servicio__estrategia_cupo='bajo_demanda') | Q(servicio__tipo_servicio='transporte')
    )


@dataclass(frozen=True)
class Celda:
    """Una panga en un dia."""

    fecha: date
    reserva: object | None
    # False cuando la panga esta marcada fuera de servicio ese dia. Vacio
    # significa disponible, y confundir las dos cosas haria asignarle un viaje a
    # una panga que no sale.
    disponible: bool


@dataclass(frozen=True)
class Renglon:
    embarcacion: object
    celdas: list


@dataclass(frozen=True)
class DiaCupo:
    """Lo que el motor de cupo usa para decidir si todavia se vende ese dia.

    Sale del mismo contexto que `/api/cupo/` y la validacion (`obtener_contexto_rango`),
    no de un calculo aparte: asi esta cifra no puede decir "quedan 3" cuando el sistema
    ya rechaza la venta. El tope es el de `CupoDiario` (o el normal) y los apartados son
    los clientes que estan en el paso de pago ahora mismo.
    """

    fecha: date
    tope: int
    vendidos: int
    apartados: int
    quedan: int

    @property
    def cerrado(self):
        return self.tope == 0


@dataclass(frozen=True)
class Resumen:
    """Lo que falta, contado, para la linea de arriba de la agenda."""

    sin_panga: int
    sin_capitan: int
    atrasados: int

    @property
    def todo_al_dia(self):
        return not (self.sin_panga or self.sin_capitan or self.atrasados)


@dataclass(frozen=True)
class Panorama:
    dias: list
    renglones: list
    # Por dia, los viajes vendidos que todavia no tienen panga. No caben en
    # ningun renglon porque no tienen panga que los ponga ahi: sin esto serian
    # invisibles, que es lo peor que puede hacer un panorama. En la practica este
    # renglon es la lista de trabajo.
    sin_repartir: list
    ocupadas: list
    a_flote: list
    resumen: Resumen
    cupo_dias: list = field(default_factory=list)

    @property
    def encabezados(self):
        """`[(fecha, DiaCupo), ...]` para pintar la cabecera de cada dia."""
        return list(zip(self.dias, self.cupo_dias))

    @property
    def pie(self):
        """`[(ocupadas, a_flote), ...]` por dia, para pintar "3/10" sin que la
        plantilla tenga que cruzar dos listas por indice."""
        return list(zip(self.ocupadas, self.a_flote))


def armar_panorama(desde, empresa, dias=DIAS_DEL_PANORAMA):
    """La cuadricula completa a partir de `desde`, en tres consultas, para una Empresa."""
    fechas = [desde + timedelta(days=i) for i in range(dias)]
    hasta = fechas[-1]

    # Las grandes arriba: son las escasas, solo dos llevan mas de 3 personas.
    embarcaciones = list(
        Embarcacion.objects.filter(activa=True, empresa=empresa).order_by('-capacidad_maxima', 'nombre')
    )

    fuera = {(f, e) for f, e in EmbarcacionNoDisponible.objects.filter(
        fecha__range=(desde, hasta), empresa=empresa,
    ).values_list('fecha', 'embarcacion_id')}

    asignadas = {}
    sin_panga = {fecha: [] for fecha in fechas}
    sin_capitan = 0
    for reserva in sin_lo_que_no_se_reparte(Reserva.objects.filter(
        fecha__range=(desde, hasta), estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa=empresa,
    )).select_related('embarcacion').order_by('hora', 'pk'):
        if reserva.embarcacion_id:
            asignadas[(reserva.fecha, reserva.embarcacion_id)] = reserva
            if reserva.estado == Reserva.Estado.ASIGNADA and not reserva.capitan_id:
                sin_capitan += 1
        else:
            sin_panga[reserva.fecha].append(reserva)

    # Cobrados que ya pasaron y nadie asigno: la agenda los lista y los marca
    # ATRASADO, asi que el resumen tiene que contarlos tambien.
    atrasados = sin_lo_que_no_se_reparte(Reserva.objects.filter(
        fecha__lt=desde, estado=Reserva.Estado.PAGADA, empresa=empresa,
    )).count()

    renglones = [
        Renglon(
            embarcacion=embarcacion,
            celdas=[
                Celda(
                    fecha=fecha,
                    reserva=asignadas.get((fecha, embarcacion.pk)),
                    disponible=(fecha, embarcacion.pk) not in fuera,
                )
                for fecha in fechas
            ],
        )
        for embarcacion in embarcaciones
    ]

    contexto = obtener_contexto_rango(desde, hasta, empresa)
    apartados = demanda_apartada_por_rango(empresa, desde, hasta) if apartado_activo() else {}
    cupo_dias = []
    for fecha in fechas:
        total = len(contexto.grupos_por_fecha.get(fecha, []))  # ya incluye los apartados
        n_apartados = len(apartados.get(fecha, []))
        tope = contexto.topes_por_fecha[fecha]
        cupo_dias.append(DiaCupo(
            fecha=fecha, tope=tope, vendidos=total - n_apartados,
            apartados=n_apartados, quedan=max(0, tope - total),
        ))

    return Panorama(
        dias=fechas,
        renglones=renglones,
        sin_repartir=[sin_panga[fecha] for fecha in fechas],
        ocupadas=[
            sum(1 for e in embarcaciones if (fecha, e.pk) in asignadas) for fecha in fechas
        ],
        a_flote=[
            sum(1 for e in embarcaciones if (fecha, e.pk) not in fuera) for fecha in fechas
        ],
        resumen=Resumen(
            sin_panga=sum(len(dia) for dia in sin_panga.values()),
            sin_capitan=sin_capitan,
            atrasados=atrasados,
        ),
        cupo_dias=cupo_dias,
    )
