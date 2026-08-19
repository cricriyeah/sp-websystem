"""Los dias ya vendidos que la flota real no puede operar.

El motor de cupo valida al guardar, asi que una reserva que entro antes de que el
cupo supiera de tamanos de grupo sobrevive intacta. Puede haber un dia con tres
grupos de 4 y solo dos pangas que los lleven: nadie se entera hasta que el tercer
cliente llega al muelle.

Este comando no arregla nada a proposito — a quien se le mueve la fecha lo decide
una persona, no el sistema. Solo ensena los dias que no cierran.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import (
    ESTADOS_QUE_OCUPAN_CUPO,
    Reserva,
    caben,
    cupo_maximo_del_dia,
)
from apps.fleet.models import capacidades_por_fecha

DIAS_POR_DEFECTO = 90


class Command(BaseCommand):
    help = 'Lista los dias ya vendidos que no se pueden operar con la flota real.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=DIAS_POR_DEFECTO,
            help=f'Cuantos dias hacia adelante revisar. Por defecto {DIAS_POR_DEFECTO}.',
        )

    def handle(self, *args, **options):
        desde = timezone.localdate()
        hasta = desde + timedelta(days=options['dias'] - 1)

        grupos_por_fecha = {}
        for fecha, personas in Reserva.objects.filter(
            fecha__range=(desde, hasta), estado__in=ESTADOS_QUE_OCUPAN_CUPO
        ).values_list('fecha', 'numero_personas'):
            grupos_por_fecha.setdefault(fecha, []).append(personas)

        capacidades = capacidades_por_fecha(desde, hasta)

        problemas = 0
        for fecha in sorted(grupos_por_fecha):
            grupos = sorted(grupos_por_fecha[fecha], reverse=True)
            if len(grupos) <= cupo_maximo_del_dia(fecha) and caben(grupos, capacidades[fecha]):
                continue

            problemas += 1
            self.stdout.write(
                f'{fecha}: {len(grupos)} viajes vendidos '
                f'({", ".join(str(g) for g in grupos)} personas) '
                f'y solo {len(capacidades[fecha])} pangas a flote '
                f'({", ".join(str(c) for c in capacidades[fecha])}). No cierra.'
            )

        if problemas:
            self.stdout.write(f'{problemas} dia(s) por resolver a mano.')
