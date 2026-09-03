"""Borra los checkouts abandonados viejos para que la lista de recuperacion no
crezca sin fin.

Un checkout abandonado es una `Reserva` que se quedo en `pendiente_pago`: el
cliente lleno sus datos y no pago. Pasados unos dias ya no hay nada que
recuperar, y son datos personales que no tiene sentido conservar.

Solo toca `pendiente_pago`: nunca borra una reserva pagada, asignada, completada
ni cancelada. Pensado para correrlo diario desde un cron de Render.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.tenancy import scope
from apps.tenancy.models import Empresa

DIAS_POR_DEFECTO = 30


class Command(BaseCommand):
    help = 'Borra los checkouts abandonados (pendiente_pago) mas viejos que N dias, en todas las Empresas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=DIAS_POR_DEFECTO,
            help=f'Antiguedad minima para borrar. Por defecto {DIAS_POR_DEFECTO}.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo dice cuantos borraria, sin tocar nada.',
        )

    def handle(self, *args, **options):
        dias = options['dias']
        limite = timezone.now() - timedelta(days=dias)

        total = 0
        for empresa in Empresa.objects.filter(activo=True):
            with scope.con_empresa(empresa):
                viejos = Reserva.objects.filter(
                    estado=Reserva.Estado.PENDIENTE_PAGO, creado_en__lt=limite, empresa=empresa,
                )
                total += viejos.count()
                if not options['dry_run']:
                    viejos.delete()

        if options['dry_run']:
            self.stdout.write(f'Se borrarian {total} checkout(s) abandonado(s) de mas de {dias} dias.')
            return

        self.stdout.write(self.style.SUCCESS(
            f'{total} checkout(s) abandonado(s) de mas de {dias} dias borrado(s).'
        ))
