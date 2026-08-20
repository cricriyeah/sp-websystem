"""La cuadricula de dias x pangas que va arriba de la agenda.

Responde la pregunta que la tabla no responde. La tabla dice que viajes hay y
quien los lleva; cuando se reparte, lo que uno se pregunta es al reves: **que
panga me queda libre el jueves**. Con la flota fija en diez y una sola salida por
panga al dia, esa respuesta cabe entera en una cuadricula sin scroll.

Es solo lectura a proposito. Repartir se sigue haciendo en la tabla, con sus
selectores y su validacion; esto solo ensena el panorama.

Todo sale en **tres consultas fijas** para la cuadricula completa — reservas del
rango, pangas activas y las marcadas fuera de servicio — sin ninguna por celda.
Con la flota completa y una semana son setenta celdas: una consulta por celda
seria setenta consultas para pintar una tabla.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from apps.fleet.models import Embarcacion, EmbarcacionNoDisponible

from .models import ESTADOS_QUE_OCUPAN_CUPO, Reserva

DIAS_DEL_PANORAMA = 7


@dataclass(frozen=True)
class Celda:
    """Una panga en un dia."""

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

    @property
    def pie(self):
        """`[(ocupadas, a_flote), ...]` por dia, para pintar "3/10" sin que la
        plantilla tenga que cruzar dos listas por indice."""
        return list(zip(self.ocupadas, self.a_flote))


def armar_panorama(desde, dias=DIAS_DEL_PANORAMA):
    """La cuadricula completa a partir de `desde`, en tres consultas."""
    fechas = [desde + timedelta(days=i) for i in range(dias)]
    hasta = fechas[-1]

    # Las grandes arriba: son las escasas, solo dos llevan mas de 3 personas.
    embarcaciones = list(
        Embarcacion.objects.filter(activa=True).order_by('-capacidad_maxima', 'nombre')
    )

    fuera = {(f, e) for f, e in EmbarcacionNoDisponible.objects.filter(
        fecha__range=(desde, hasta)
    ).values_list('fecha', 'embarcacion_id')}

    asignadas = {}
    sin_panga = {fecha: [] for fecha in fechas}
    for reserva in Reserva.objects.filter(
        fecha__range=(desde, hasta), estado__in=ESTADOS_QUE_OCUPAN_CUPO
    ).select_related('embarcacion'):
        if reserva.embarcacion_id:
            asignadas[(reserva.fecha, reserva.embarcacion_id)] = reserva
        else:
            sin_panga[reserva.fecha].append(reserva)

    renglones = [
        Renglon(
            embarcacion=embarcacion,
            celdas=[
                Celda(
                    reserva=asignadas.get((fecha, embarcacion.pk)),
                    disponible=(fecha, embarcacion.pk) not in fuera,
                )
                for fecha in fechas
            ],
        )
        for embarcacion in embarcaciones
    ]

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
    )
