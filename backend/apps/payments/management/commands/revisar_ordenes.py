"""Inspección de órdenes en estado intermedio o atascadas.

Herramienta de diagnóstico para la vendedora y operadores: lista órdenes en
estado `armando`, `autorizando` o `autorizada` que lleven más de N horas sin
moverse, junto con el estado en Stripe de cada uno de sus PaymentIntents.

Puramente informativo: no modifica ningún registro ni en la BD ni en Stripe.
La resolución automática la realiza `manage.py conciliar_pagos`.
"""
from datetime import timedelta

import stripe
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import Orden
from apps.bookings.orden_lectura import reservas_de_orden
from apps.payments.stripe_client import configurar_stripe
from apps.tenancy import scope
from apps.tenancy.models import Empresa

HORAS_POR_DEFECTO = 2


class Command(BaseCommand):
    help = 'Lista órdenes atascadas o pendientes de autorización para revisión manual.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--horas', type=int, default=HORAS_POR_DEFECTO,
            help=f'Horas de inactividad a partir de las cuales considerar una orden atascada. Por defecto {HORAS_POR_DEFECTO}.',
        )
        parser.add_argument(
            '--dry-run', action='store_true', default=True,
            help='Comportamiento informativo por defecto; no realiza ninguna modificación.',
        )

    def handle(self, *args, **options):
        horas = options['horas']
        limite = timezone.now() - timedelta(hours=horas)

        estados_pendientes = [
            Orden.Estado.ARMANDO,
            Orden.Estado.AUTORIZANDO,
            Orden.Estado.AUTORIZADA,
        ]

        with scope.como_operador_plataforma():
            ordenes = list(
                Orden.objects.filter(
                    estado__in=estados_pendientes,
                    actualizado_en__lte=limite,
                ).order_by('actualizado_en')
            )

        if not ordenes:
            self.stdout.write(self.style.SUCCESS(f'No se encontraron órdenes atascadas (> {horas}h).'))
            return

        self.stdout.write(self.style.WARNING(f'Se encontraron {len(ordenes)} orden(es) atascada(s) (> {horas}h):'))
        self.stdout.write('-' * 70)

        empresas_cache = {}

        for orden in ordenes:
            self.stdout.write(
                f'Orden #{orden.pk} ({orden.estado}) — {orden.nombre_cliente} <{orden.correo_cliente}> '
                f'— Actualizada: {orden.actualizado_en.strftime("%Y-%m-%d %H:%M:%S")}'
            )

            filas = reservas_de_orden(orden.pk)
            for fila in filas:
                emp_id = fila['empresa_id']
                if emp_id not in empresas_cache:
                    with scope.como_operador_plataforma():
                        empresas_cache[emp_id] = Empresa.objects.filter(pk=emp_id).first()
                empresa = empresas_cache[emp_id]

                pi_id = fila.get('stripe_payment_intent_id')
                status_stripe = 'sin_pi'

                if empresa and empresa.stripe_secret_key and pi_id:
                    cli = configurar_stripe(empresa)
                    try:
                        intent = cli.payment_intents.retrieve(pi_id)
                        status_stripe = intent.status
                    except stripe.StripeError as exc:
                        status_stripe = f'error_stripe ({exc})'

                empresa_slug = empresa.slug if empresa else f'empresa_{emp_id}'
                self.stdout.write(
                    f'  - Reserva {fila["reserva_id"]} ({empresa_slug}): '
                    f'estado_bd={fila["estado"]}, PI={pi_id or "ninguno"}, status_stripe={status_stripe}'
                )

            self.stdout.write('-' * 70)

        self.stdout.write(
            self.style.SUCCESS(f'Total: {len(ordenes)} orden(es) atascada(s) reportada(s).')
        )
