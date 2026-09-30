"""Estado de cara al cliente de una Reserva o una Orden, calculado sin tocar Stripe.

Una sola fuente para lo que el aviso "Continuar reservación" muestra (spec §10.1): nunca se
infiere en el navegador. `situacion_de_orden` recibe el estado por-pago que ya calcula
`GetOrdenView` (que sí consulta Stripe); esta función solo combina lo que ya se leyó."""
from decimal import Decimal

from django.db import models

PENDIENTES_DE_CAPTURA = {'requires_capture'}
EN_PROCESO = {'requires_payment_method', 'requires_confirmation', 'requires_action', 'processing'}
# 'succeeded' cuenta como dinero comprometido igual que 'requires_capture': en ambos
# casos el cliente ya no tiene nada pendiente de pagar en ese componente, solo difiere
# si ya se capturo o sigue retenido. Ver hallazgo #4 del review.
COMPROMETIDO = PENDIENTES_DE_CAPTURA | {'succeeded'}
# Si el void de un PI sigue en uno de estos estados tras cancelar la orden, el
# `payment_intents.cancel` de `revertir_orden` no se confirmo (fallo silencioso
# atrapado como StripeError) y el dinero sigue retenido. Ver hallazgo #2.
AUN_RETENIDO_TRAS_CANCELAR = PENDIENTES_DE_CAPTURA | EN_PROCESO


class Situacion(models.TextChoices):
    SIN_PAGO = 'sin_pago', 'Sin pagar'
    PAGO_EN_PROCESO = 'pago_en_proceso', 'Pago en proceso'
    RETENIDO_PARCIAL = 'retenido_parcial', 'Pago parcial retenido'
    RETENIDO_TOTAL = 'retenido_total', 'Todo retenido'
    CONFIRMANDO_COBRO = 'confirmando_cobro', 'Confirmando el cobro'
    CONFIRMADA = 'confirmada', 'Confirmada'
    CANCELADA_LIBERADA = 'cancelada_liberada', 'Cancelada, sin cobro'
    CANCELADA_DEVOLUCION_SOLICITADA = 'cancelada_devolucion_solicitada', 'Cancelada, devolución solicitada'
    CANCELADA_DEVOLUCION_POR_CONFIRMAR = 'cancelada_devolucion_por_confirmar', 'Cancelada, devolución por confirmar'
    EXPIRADA = 'expirada', 'Expirada'
    NO_EXISTE = 'no_existe', 'No existe'


def _situacion_cancelada(*, pagado_total, reembolsado_total, aun_retenido):
    """Compartida por reserva y orden. `aun_retenido`=True cuando hay evidencia de que
    un void no se confirmo (ver AUN_RETENIDO_TRAS_CANCELAR); nunca se declara
    "liberada" mientras eso sea cierto, y un reembolso parcial nunca cuenta como
    solicitud completa (hallazgo #2 del review)."""
    if aun_retenido:
        return Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR
    if pagado_total > 0:
        if reembolsado_total >= pagado_total:
            return Situacion.CANCELADA_DEVOLUCION_SOLICITADA
        return Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR
    return Situacion.CANCELADA_LIBERADA


def situacion_de_reserva(*, estado, monto_pagado, monto_reembolsado, tiene_intent_activo=False):
    if estado == 'pendiente_pago':
        return Situacion.PAGO_EN_PROCESO if tiene_intent_activo else Situacion.SIN_PAGO
    if estado in ('pagada', 'asignada', 'completada'):
        return Situacion.CONFIRMADA
    if estado == 'cancelada':
        # Motor de una empresa: captura automatica, sin paso de "retenido" y sin
        # endpoint de cancelacion propio en este plan — monto_pagado is None siempre
        # significa que nunca hubo nada que liberar, sin necesitar evidencia de Stripe.
        return _situacion_cancelada(
            pagado_total=monto_pagado or Decimal('0'),
            reembolsado_total=monto_reembolsado or Decimal('0'),
            aun_retenido=False,
        )
    return Situacion.NO_EXISTE


def situacion_de_orden(*, estado_orden, pagos):
    if estado_orden == 'armando':
        return Situacion.SIN_PAGO
    if estado_orden == 'autorizando':
        con_evidencia = [p for p in pagos if p.get('estado_pi')]
        if not con_evidencia:
            return Situacion.PAGO_EN_PROCESO
        comprometidos = sum(1 for p in pagos if p.get('estado_pi') in COMPROMETIDO)
        if comprometidos == 0:
            # `requires_payment_method` en todos = ningun pago se ha intentado (o el ultimo
            # se rechazo y volvio a ese estado): nadie ha pagado ni hay nada procesandose.
            # Solo `processing`/`requires_action`/`requires_confirmation` son "en proceso".
            if all(p.get('estado_pi') == 'requires_payment_method' for p in con_evidencia):
                return Situacion.SIN_PAGO
            return Situacion.PAGO_EN_PROCESO
        if comprometidos < len(pagos):
            return Situacion.RETENIDO_PARCIAL
        return Situacion.CONFIRMANDO_COBRO
    if estado_orden == 'autorizada':
        return Situacion.CONFIRMANDO_COBRO
    if estado_orden == 'capturada':
        return Situacion.CONFIRMADA
    if estado_orden == 'cancelada':
        pagado_total = sum((p.get('monto_pagado') or Decimal('0')) for p in pagos)
        reembolsado_total = sum((p.get('monto_reembolsado') or Decimal('0')) for p in pagos)
        aun_retenido = any(p.get('estado_pi') in AUN_RETENIDO_TRAS_CANCELAR for p in pagos)
        return _situacion_cancelada(
            pagado_total=pagado_total, reembolsado_total=reembolsado_total, aun_retenido=aun_retenido,
        )
    return Situacion.NO_EXISTE


def requiere_atencion(situacion):
    return situacion == Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR
