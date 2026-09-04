"""Red de seguridad del webhook de Stripe, una Empresa a la vez.

Lo normal es que el webhook marque la reserva como pagada en segundos. Pero si
una entrega se pierde de forma permanente (el backend estaba caido, el
`webhook_secret` de esa Empresa estaba mal, Stripe se rindio tras sus
reintentos), queda un cliente que pago y no tiene reserva. Nadie se entera
hasta que reclama.

Este comando busca, por cada Empresa con llave de Stripe configurada, reservas
en `pendiente_pago` que ya tengan un PaymentIntent, le pregunta a Stripe como
quedo, y aplica exactamente la misma logica que el webhook (ver
apps/payments/services.py). Itera TODAS las Empresas, activas o no (Revision 4,
N16): una pausada puede tener dinero ya cobrado pendiente de reconciliar.
Pensado para un cron cada hora.
"""
from datetime import timedelta

import stripe
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.payments.services import aplicar_pago_exitoso
from apps.payments.stripe_client import configurar_stripe
from apps.tenancy import scope
from apps.tenancy.models import Empresa

DIAS_POR_DEFECTO = 7


class Command(BaseCommand):
    help = 'Aplica los pagos que Stripe confirmo pero cuyo webhook nunca llego, por Empresa.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=DIAS_POR_DEFECTO,
            help=f'Hasta que antiguedad revisar. Por defecto {DIAS_POR_DEFECTO}.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo dice que haria, sin tocar ni la base ni Stripe.',
        )

    def handle(self, *args, **options):
        desde = timezone.now() - timedelta(days=options['dias'])
        total_revisadas = total_aplicadas = 0

        for empresa in Empresa.objects.all():
            if not empresa.stripe_secret_key:
                self.stdout.write(f'Empresa {empresa.slug}: sin llave de Stripe, se salta.')
                continue

            with scope.con_empresa(empresa):
                revisadas, aplicadas = self._conciliar_empresa(empresa, desde, options)
            total_revisadas += revisadas
            total_aplicadas += aplicadas

        resumen = (
            f'{total_revisadas} reserva(s) revisada(s), '
            f'{total_aplicadas} con pago confirmado en Stripe.'
        )
        self.stdout.write(
            self.style.WARNING(f'[dry-run] {resumen}') if options['dry_run']
            else self.style.SUCCESS(resumen)
        )

    def _conciliar_empresa(self, empresa, desde, options):
        cliente = configurar_stripe(empresa)
        pendientes = Reserva.objects.filter(
            estado=Reserva.Estado.PENDIENTE_PAGO, creado_en__gte=desde, empresa=empresa,
        ).exclude(stripe_payment_intent_id='')

        revisadas = aplicadas = 0
        for reserva in pendientes:
            revisadas += 1
            try:
                intent = cliente.payment_intents.retrieve(reserva.stripe_payment_intent_id)
            except stripe.StripeError as exc:
                self.stderr.write(f'Reserva {reserva.pk}: no se pudo consultar Stripe ({exc}).')
                continue

            if intent.status != 'succeeded':
                continue

            if options['dry_run']:
                self.stdout.write(
                    f'Reserva {reserva.pk}: pago {intent.id} esta succeeded por '
                    f'{intent.amount_received / 100} {intent.currency.upper()} y sigue pendiente.'
                )
                aplicadas += 1
                continue

            resultado = aplicar_pago_exitoso(intent, empresa)
            aplicadas += 1
            self.stdout.write(f'Reserva {reserva.pk}: {resultado}.')

        return revisadas, aplicadas
