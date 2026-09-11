"""Orquestación de una Orden cruza-empresa: crear N PaymentIntents en modo
manual capture (uno por empresa), capturarlos todos, o revertir todo.
El dinero se calcula en pricing.monto_por_empresa; aquí solo se mueve."""
import logging
import time
from decimal import Decimal
from typing import Any

import stripe
from django.db import connection

from apps.bookings.models import Orden, Reserva
from apps.bookings.orden_lectura import reservas_de_orden
from apps.payments.pricing import a_centavos, de_centavos
from apps.payments.stripe_client import configurar_stripe
from apps.tenancy import scope
from apps.tenancy.models import Empresa

logger = logging.getLogger(__name__)

CAPTURA_REINTENTOS = 3

INTENT_REUTILIZABLE = {'requires_payment_method', 'requires_confirmation', 'requires_action', 'requires_capture'}
INTENTS_PENDIENTES_VOID = {'requires_capture', 'requires_confirmation', 'requires_action', 'requires_payment_method'}


class OrdenCerradaError(Exception):
    """La orden ya está capturada o cancelada; no admite más pagos ni modificaciones."""


def crear_pagos_orden(orden: Orden, reparto: dict[int, Decimal]) -> list[dict[str, Any]]:
    """Idempotente. `reparto` = {empresa_id: Decimal} de pricing.monto_por_empresa.
    Crea (o reutiliza) un PaymentIntent por cada Reserva de la orden, en la
    cuenta Stripe de su empresa, por su monto del reparto, con
    capture_method='manual' y payment_method_types=['card'] (SOLO tarjeta —
    OXXO/SPEI no soportan auth/capture). metadata {orden_id, reserva_id,
    empresa_id}. idempotency_key = f'orden-{orden.id}-{empresa_id}-crear'.
    Devuelve [{empresa_slug, monto, client_secret, publishable_key}].
    Fallo parcial (creó el de la empresa 1, la llamada de la empresa 2
    revienta): deja los creados, propaga el error; un reintento crea los que
    faltan y reutiliza los existentes. 409 si la orden ya está
    capturada/cancelada.
    """
    if orden.estado in (Orden.Estado.CAPTURADA, Orden.Estado.CANCELADA):
        raise OrdenCerradaError(f'La orden #{orden.id} ya está {orden.estado}.')

    filas = reservas_de_orden(orden.id)
    resultado = []

    for fila in filas:
        empresa_id = fila['empresa_id']
        reserva_id = fila['reserva_id']
        monto = reparto.get(empresa_id, Decimal('0.00'))
        centavos = a_centavos(monto)
        moneda = orden.moneda.lower()

        empresa = Empresa.objects.get(pk=empresa_id)
        cliente = configurar_stripe(empresa)

        intent = None
        pi_id = fila.get('stripe_payment_intent_id')

        if pi_id:
            try:
                intent_existente = cliente.payment_intents.retrieve(pi_id)
                if intent_existente.status in INTENT_REUTILIZABLE:
                    if getattr(intent_existente, 'amount', None) == centavos and getattr(intent_existente, 'currency', None) == moneda:
                        intent = intent_existente
                    else:
                        intent = cliente.payment_intents.update(
                            pi_id,
                            {'amount': centavos, 'currency': moneda},
                        )
                else:
                    intent = intent_existente
            except stripe.StripeError:
                intent = None

        if intent is None:
            intent = cliente.payment_intents.create(
                {
                    'amount': centavos,
                    'currency': moneda,
                    'capture_method': 'manual',
                    'payment_method_types': ['card'],
                    'metadata': {
                        'orden_id': str(orden.id),
                        'reserva_id': str(reserva_id),
                        'empresa_id': str(empresa.id),
                    },
                },
                {'idempotency_key': f'orden-{orden.id}-{empresa.id}-crear'},
            )

        with scope.con_empresa(empresa):
            Reserva.objects.filter(pk=reserva_id).update(
                stripe_payment_intent_id=intent.id,
                precio_total=monto,
            )

        resultado.append({
            'empresa_slug': empresa.slug,
            'monto': str(monto),
            'client_secret': intent.client_secret,
            'publishable_key': empresa.stripe_publishable_key,
        })

    return resultado


def confirmar_captura(orden: Orden) -> None:
    """Lee los N PaymentIntents (por estado_reservas_de_orden → stripe_payment_intent_id).
    Si alguno NO está 'requires_capture' → revertir_orden(orden, 'una autorización
    no se completó'). Si todos → captura los N; si la captura de alguno falla,
    reintenta ESA hasta CAPTURA_REINTENTOS con espera corta; si agota →
    revertir_orden(orden, 'no se pudo capturar <empresa>'). Idempotente a nivel
    operación: un PI ya 'succeeded' se salta (traga PaymentIntentUnexpectedState),
    no se re-captura. NO marca orden.capturada — eso lo hace el webhook al
    recibir cada payment_intent.succeeded.
    """
    filas = reservas_de_orden(orden.id)
    if not filas:
        return

    intents_info = []
    for fila in filas:
        pi_id = fila.get('stripe_payment_intent_id')
        if not pi_id:
            revertir_orden(orden, 'una autorización no se completó')
            return

        empresa = Empresa.objects.get(pk=fila['empresa_id'])
        cliente = configurar_stripe(empresa)
        try:
            intent = cliente.payment_intents.retrieve(pi_id)
        except stripe.StripeError:
            revertir_orden(orden, 'una autorización no se completó')
            return

        if intent.status not in ('requires_capture', 'succeeded'):
            revertir_orden(orden, 'una autorización no se completó')
            return

        intents_info.append((empresa, cliente, intent))

    # All intents are in 'requires_capture' or 'succeeded'
    for empresa, cliente, intent in intents_info:
        if intent.status == 'succeeded':
            continue

        captured = False
        for attempt in range(CAPTURA_REINTENTOS):
            try:
                cliente.payment_intents.capture(intent.id)
                captured = True
                break
            except stripe.StripeError:
                # Si el intent ya pasó a succeeded (por ejemplo por idempotencia o concurrencia)
                try:
                    re_check = cliente.payment_intents.retrieve(intent.id)
                    if re_check.status == 'succeeded':
                        captured = True
                        break
                except stripe.StripeError:
                    pass
                if attempt < CAPTURA_REINTENTOS - 1:
                    time.sleep(0.5)

        if not captured:
            logger.error('No se pudo capturar el pago para la empresa %s en la orden %s', empresa.slug, orden.id)
            revertir_orden(orden, f'no se pudo capturar {empresa.slug}')
            return


def revertir_orden(orden: Orden, motivo: str) -> None:
    """Compensación idempotente. Por cada PaymentIntent de la orden
    (vía estado_reservas_de_orden):
      - 'requires_capture'/'requires_confirmation'/'requires_action'/'requires_payment_method' → cancel (void)
      - 'succeeded' → refund total (idempotency_key = f'orden-{orden.id}-{empresa_id}-refund')
      - 'canceled'/'refunded'/ya reembolsada → nada
    Marca las reservas afectadas (reembolsada / motivo_cancelacion / estado
    cancelada) y orden.transicionar('cancelada'). Segura para reintentos.
    """
    filas = reservas_de_orden(orden.id)

    prev_alcance = getattr(connection, 'alcance_actual', None)
    connection.alcance_actual = None
    try:
        for fila in filas:
            empresa = Empresa.objects.get(pk=fila['empresa_id'])
            cliente = configurar_stripe(empresa)
            pi_id = fila.get('stripe_payment_intent_id')
            reembolsada = False

            if fila.get('monto_reembolsado') and fila['monto_reembolsado'] > 0:
                reembolsada = True
            elif pi_id:
                try:
                    intent = cliente.payment_intents.retrieve(pi_id)
                    if intent.status in INTENTS_PENDIENTES_VOID:
                        cliente.payment_intents.cancel(intent.id)
                    elif intent.status == 'succeeded':
                        cliente.refunds.create(
                            {'payment_intent': intent.id},
                            {'idempotency_key': f'orden-{orden.id}-{empresa.id}-refund'},
                        )
                        reembolsada = True
                    elif intent.status == 'refunded':
                        reembolsada = True
                except stripe.StripeError:
                    logger.exception('Error al revertir PI %s de empresa %s', pi_id, empresa.slug)

            with scope.con_empresa(empresa):
                campos = {
                    'estado': Reserva.Estado.CANCELADA,
                    'motivo_cancelacion': motivo,
                    'reembolsada': reembolsada,
                }
                if reembolsada and not (fila.get('monto_reembolsado') and fila['monto_reembolsado'] > 0):
                    intent_amount = getattr(intent, 'amount', None) if (pi_id and intent) else None
                    monto_intent = de_centavos(intent_amount) if isinstance(intent_amount, int) and not isinstance(intent_amount, bool) else Decimal('0.00')
                    monto = fila.get('monto_pagado') or monto_intent
                    campos['monto_reembolsado'] = monto
                Reserva.objects.filter(pk=fila['reserva_id']).update(**campos)

        with scope.con_empresa(orden.empresa_lider):
            orden.refresh_from_db()
            if orden.estado != Orden.Estado.CANCELADA:
                orden.transicionar(Orden.Estado.CANCELADA)
                orden.save(update_fields=['estado'])
    finally:
        connection.alcance_actual = prev_alcance
        if connection.vendor == 'postgresql' and prev_alcance:
            with connection.cursor() as cursor:
                if prev_alcance[0] == 'empresa':
                    cursor.execute(f'SET LOCAL app.current_empresa_id = {int(prev_alcance[1])}')
                elif prev_alcance[0] == 'operador':
                    cursor.execute("SET LOCAL app.operador_plataforma = 'on'")
