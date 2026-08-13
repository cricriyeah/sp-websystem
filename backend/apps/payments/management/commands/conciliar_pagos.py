"""Red de seguridad del webhook de Stripe.

Lo normal es que el webhook marque la reserva como pagada en segundos. Pero si
una entrega se pierde de forma permanente (el backend estaba caido, el
`STRIPE_WEBHOOK_SECRET` estaba mal, Stripe se rindio tras sus reintentos), queda
un cliente que pago y no tiene reserva. Nadie se entera hasta que reclama.

Este comando busca reservas en `pendiente_pago` que ya tengan un PaymentIntent,
le pregunta a Stripe como quedo, y aplica exactamente la misma logica que el
webhook (ver apps/payments/services.py). Pensado para un cron cada hora.
"""
from datetime import timedelta

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.payments.services import aplicar_pago_exitoso

DIAS_POR_DEFECTO = 7


class Command(BaseCommand):
    help = 'Aplica los pagos que Stripe confirmo pero cuyo webhook nunca llego.'

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
        if not settings.STRIPE_SECRET_KEY:
            self.stderr.write('STRIPE_SECRET_KEY sin configurar, no hay nada que conciliar.')
            return

        stripe.api_key = settings.STRIPE_SECRET_KEY
        desde = timezone.now() - timedelta(days=options['dias'])

        pendientes = Reserva.objects.filter(
            estado=Reserva.Estado.PENDIENTE_PAGO, creado_en__gte=desde
        ).exclude(stripe_payment_intent_id='')

        revisadas = aplicadas = 0
        for reserva in pendientes:
            revisadas += 1
            try:
                intent = stripe.PaymentIntent.retrieve(reserva.stripe_payment_intent_id)
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

            resultado = aplicar_pago_exitoso(intent)
            aplicadas += 1
            self.stdout.write(f'Reserva {reserva.pk}: {resultado}.')

        resumen = f'{revisadas} reserva(s) revisada(s), {aplicadas} con pago confirmado en Stripe.'
        self.stdout.write(
            self.style.WARNING(f'[dry-run] {resumen}') if options['dry_run']
            else self.style.SUCCESS(resumen)
        )
