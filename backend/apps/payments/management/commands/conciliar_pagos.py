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

from apps.bookings.models import Orden, Reserva
from apps.bookings.orden_lectura import reservas_de_orden
from apps.payments.ordenes import ORDEN_TIMEOUT_AUTORIZACION, revertir_orden
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
        ordenes_a_conciliar = set()

        for empresa in Empresa.objects.all():
            if not empresa.stripe_secret_key:
                self.stdout.write(f'Empresa {empresa.slug}: sin llave de Stripe, se salta.')
                continue

            with scope.con_empresa(empresa):
                revisadas, aplicadas, orden_ids = self._conciliar_empresa(empresa, desde, options)
            total_revisadas += revisadas
            total_aplicadas += aplicadas
            ordenes_a_conciliar.update(orden_ids)

        for orden_id in sorted(ordenes_a_conciliar):
            revisadas, aplicadas = self._conciliar_orden(orden_id, options)
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
        orden_ids = set()

        for reserva in pendientes:
            if reserva.orden_id:
                orden_ids.add(reserva.orden_id)
                continue

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

        return revisadas, aplicadas, orden_ids

    def _conciliar_orden(self, orden_id, options):
        with scope.como_operador_plataforma():
            orden = Orden.objects.filter(pk=orden_id).first()
        if not orden or orden.estado in (Orden.Estado.CAPTURADA, Orden.Estado.CANCELADA):
            return 0, 0

        filas = reservas_de_orden(orden_id)
        if not filas:
            return 0, 0

        revisadas = 0
        aplicadas = 0
        intents_info = []
        empresas_cache = {}
        hay_error_stripe = False

        for fila in filas:
            revisadas += 1
            pi_id = fila.get('stripe_payment_intent_id')
            emp_id = fila['empresa_id']
            if emp_id not in empresas_cache:
                with scope.como_operador_plataforma():
                    empresas_cache[emp_id] = Empresa.objects.filter(pk=emp_id).first()
            emp = empresas_cache[emp_id]

            if not emp or not emp.stripe_secret_key or not pi_id:
                intents_info.append((fila, emp, None))
                continue

            cli = configurar_stripe(emp)
            try:
                intent = cli.payment_intents.retrieve(pi_id)
            except stripe.StripeError as exc:
                self.stderr.write(f'Orden {orden_id} (reserva {fila["reserva_id"]}): no se pudo consultar Stripe ({exc}).')
                hay_error_stripe = True
                intent = None

            intents_info.append((fila, emp, intent))

        if hay_error_stripe:
            return revisadas, 0

        statuses = [item[2].status if item[2] else None for item in intents_info]
        todos_succeeded = len(intents_info) == len(filas) and all(s == 'succeeded' for s in statuses)

        if todos_succeeded:
            for fila, emp, intent in intents_info:
                if fila['estado'] == Reserva.Estado.PENDIENTE_PAGO:
                    if options['dry_run']:
                        monto = getattr(intent, 'amount_received', 0) / 100
                        moneda = getattr(intent, 'currency', 'mxn').upper()
                        self.stdout.write(
                            f'Orden {orden_id} (reserva {fila["reserva_id"]}): pago {intent.id} esta succeeded por '
                            f'{monto} {moneda} y sigue pendiente.'
                        )
                        aplicadas += 1
                    else:
                        with scope.con_empresa(emp):
                            resultado = aplicar_pago_exitoso(intent, emp)
                        aplicadas += 1
                        self.stdout.write(f'Reserva {fila["reserva_id"]} (orden {orden_id}): {resultado}.')
            return revisadas, aplicadas

        timeout_vencido = (timezone.now() - orden.actualizado_en) >= ORDEN_TIMEOUT_AUTORIZACION
        algun_cancelado = any(s == 'canceled' for s in statuses)

        if timeout_vencido or algun_cancelado:
            motivo = 'autorización expirada' if algun_cancelado else 'timeout de autorización'
            if options['dry_run']:
                self.stdout.write(
                    f'Orden {orden_id}: no completada ({motivo}), se revertiría la orden.'
                )
            else:
                revertir_orden(orden, 'timeout de autorización')
                self.stdout.write(
                    f'Orden {orden_id}: revertida por {motivo}.'
                )

        return revisadas, aplicadas

