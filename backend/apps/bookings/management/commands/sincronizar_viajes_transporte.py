"""Comando para crear o reparar viajes de transporte de reservas que ocupan cupo."""

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist

from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO, Reserva
from apps.bookings.traslados import sincronizar_viajes
from apps.fleet.enums import TipoServicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa


class Command(BaseCommand):
    help = 'Sincroniza los viajes de transporte para las reservas que ocupan cupo, por Empresa.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo dice qué haría, sin modificar la base de datos.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        total_reservas = 0
        total_sincronizadas = 0

        for empresa in Empresa.objects.all():
            with scope.con_empresa(empresa):
                reservas = (
                    Reserva.objects.filter(
                        empresa=empresa,
                        estado__in=ESTADOS_QUE_OCUPAN_CUPO,
                        servicio__tipo_servicio=TipoServicio.TRANSPORTE,
                    )
                    .select_related('servicio')
                    .order_by('pk')
                )
                for reserva in reservas:
                    total_reservas += 1
                    try:
                        detalle = reserva.detalle_transporte
                    except ObjectDoesNotExist:
                        detalle = None

                    if detalle is not None:
                        if not dry_run:
                            sincronizar_viajes(reserva, detalle=detalle)
                        total_sincronizadas += 1

        if dry_run:
            self.stdout.write(
                f'DRY-RUN: se sincronizarian viajes para {total_sincronizadas} de {total_reservas} reserva(s) de transporte.'
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Se sincronizaron viajes para {total_sincronizadas} de {total_reservas} reserva(s) de transporte.'
                )
            )
