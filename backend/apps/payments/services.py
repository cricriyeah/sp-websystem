"""Aplicacion de un pago exitoso a su reserva, por Empresa.

Vive aparte de las vistas porque tiene dos entradas: el webhook de Stripe (la
normal) y `manage.py conciliar_pagos` (la red de seguridad, para cuando una
entrega del webhook se pierde). Las dos deben decidir exactamente lo mismo, asi
que la logica no se duplica. `empresa` es obligatorio en toda funcion publica
de aqui: nunca se infiere de metadatos del PaymentIntent, siempre la resuelve
quien llama (el webhook, por el slug de la URL; conciliar_pagos, iterando).
"""
import logging
from datetime import UTC, datetime

import stripe
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.notifications.services import notificar_reserva_pagada
from apps.tenancy import scope
from apps.tenancy.models import Empresa

from .pricing import a_centavos, de_centavos, monto_inicial
from .stripe_client import configurar_stripe

logger = logging.getLogger(__name__)

# Resultados posibles, para que quien llame pueda reportar que paso.
APLICADO = 'aplicado'
YA_APLICADO = 'ya_aplicado'
DUPLICADO_REEMBOLSADO = 'duplicado_reembolsado'
SIN_CUPO_REEMBOLSADO = 'sin_cupo_reembolsado'
CODIGO_INVALIDO_REEMBOLSADO = 'codigo_invalido_reembolsado'
SIN_RESERVA_REEMBOLSADO = 'sin_reserva_reembolsado'
FALLO_REEMBOLSO = 'fallo_reembolso'


def _reserva_id_de(intent):
    """El `metadata` llega como dict cuando viene del webhook y como StripeObject
    cuando viene de `payment_intents.retrieve`, y ese ultimo no tiene `.get`."""
    try:
        return intent['metadata']['reserva_id']
    except (KeyError, TypeError):
        return None


def _momento_del_pago(intent):
    """Cuando cobro Stripe, no cuando nos enteramos.

    Importa para el panel de finanzas: `conciliar_pagos` puede aplicar horas o
    dias despues un pago cuyo webhook se perdio, y ese dinero tiene que caer en
    el dia en que entro o el balance de ese dia nunca cuadra. Si el intent no
    trae `created` (eventos viejos, pruebas), se usa la hora actual.
    """
    try:
        return datetime.fromtimestamp(intent['created'], UTC)
    except (KeyError, TypeError, ValueError, OSError):
        return timezone.now()


@transaction.atomic
def aplicar_pago_exitoso(intent, empresa):
    """Marca la reserva como pagada, o devuelve el dinero si ya no procede.

    `intent` es el PaymentIntent de Stripe (el del evento o el que se recupera
    al conciliar). `empresa` es la Empresa duena del webhook/comando que
    llama — nunca se infiere de metadatos del intent. Devuelve una de las
    constantes de arriba.
    """
    # select_for_update serializa dos entregas simultaneas del mismo evento
    # (Stripe reintenta y puede solapar): sin el, las dos verian la reserva en
    # pendiente_pago y las dos la marcarian pagada. empresa=empresa: sin
    # RLS (sqlite, tests) nada mas aisla el pk de otra Empresa.
    reserva = (
        Reserva.objects.select_for_update()
        .filter(pk=_reserva_id_de(intent), empresa=empresa)
        .first()
    )

    if reserva is None:
        logger.error('Pago %s sin reserva asociada, se reembolsa', intent['id'])
        return (
            SIN_RESERVA_REEMBOLSADO
            if reembolsar(intent, 'pago sin reserva', empresa)
            else FALLO_REEMBOLSO
        )

    if reserva.estado != Reserva.Estado.PENDIENTE_PAGO:
        return _resolver_cobro_repetido(reserva, intent, empresa)

    _verificar_monto(reserva, intent)

    reserva.monto_pagado = de_centavos(intent['amount_received'])
    reserva.pagada_en = _momento_del_pago(intent)
    reserva.stripe_payment_intent_id = intent['id']
    reserva.estado = Reserva.Estado.PAGADA
    try:
        reserva.full_clean()
        reserva.save()
    except DjangoValidationError as exc:
        # `codigo_promocional` es la unica clave que Reserva.clean() usa para
        # este rechazo (ver validar_codigo_promocional_en_pago) — cualquier
        # otra cosa (cupo, deslinde, etc.) cae en el motivo generico de abajo.
        if 'codigo_promocional' in getattr(exc, 'error_dict', {}):
            return _cancelar_codigo_promocional_invalido(reserva, intent, empresa)
        return _cancelar_sin_cupo(reserva, intent, empresa)

    # Revision 4 (N1): SET LOCAL muere al COMMIT — un callback de on_commit
    # corre FUERA del `with scope.con_empresa(...)` que encolo esta
    # transaccion. Bajo RLS eso es cero filas, no un error: el bug mas
    # peligroso porque no truena, solo calla. Se captura el entero (no el
    # objeto Empresa, con FKs perezosos) antes de encolar, y el callback
    # reabre su propio alcance al ejecutarse.
    empresa_id = empresa.pk

    def _notificar():
        with scope.con_empresa(Empresa.objects.get(pk=empresa_id)):
            notificar_reserva_pagada(reserva)

    transaction.on_commit(_notificar)
    return APLICADO


def _resolver_cobro_repetido(reserva, intent, empresa):
    """La reserva ya no esta pendiente. Si es el mismo intent, es Stripe
    reintentando el evento y no hay nada que hacer. Si es OTRO intent, al
    cliente le cobraron dos veces: se devuelve el segundo de inmediato."""
    if reserva.stripe_payment_intent_id == intent['id']:
        logger.info('Evento repetido del pago %s, ya aplicado', intent['id'])
        return YA_APLICADO

    logger.error(
        'Cobro duplicado en la reserva %s: ya pagada con %s y llego %s. Se reembolsa el segundo.',
        reserva.pk, reserva.stripe_payment_intent_id, intent['id'],
    )
    return (
        DUPLICADO_REEMBOLSADO
        if reembolsar(intent, 'cobro duplicado', empresa)
        else FALLO_REEMBOLSO
    )


def _verificar_monto(reserva, intent):
    """Compara lo que cobro Stripe contra lo que este servidor habia calculado.

    No rechaza el pago — el dinero ya entro y rebotarlo dejaria al cliente sin
    viaje y sin dinero hasta el reembolso — pero deja el descuadre en el log y
    visible en el admin (precio_total contra monto_pagado).
    """
    if intent['currency'].upper() != reserva.moneda:
        logger.error(
            'Moneda distinta en la reserva %s: se esperaba %s y llego %s',
            reserva.pk, reserva.moneda, intent['currency'].upper(),
        )
        return

    if reserva.precio_total is None:
        logger.error('Reserva %s sin precio_total al recibir el pago', reserva.pk)
        return

    esperado = a_centavos(monto_inicial(reserva.precio_total, reserva.forma_pago))
    if intent['amount_received'] != esperado:
        logger.error(
            'Descuadre en la reserva %s: se esperaban %s centavos y llegaron %s',
            reserva.pk, esperado, intent['amount_received'],
        )


def _cancelar_sin_cupo(reserva, intent, empresa):
    """El dia se lleno mientras el cliente pagaba. Se devuelve el 100% y la
    reserva queda cancelada con el motivo real, para que la vendedora la vea en
    su panel en vez de que desaparezca como 'pendiente de pago'."""
    if not reembolsar(intent, 'sin cupo', empresa):
        return FALLO_REEMBOLSO

    reserva.estado = Reserva.Estado.CANCELADA
    reserva.motivo_cancelacion = 'Sin cupo disponible al confirmar el pago. Reembolso automatico.'
    reserva.cancelada_en = timezone.now()
    reserva.reembolsada = True
    reserva.monto_reembolsado = de_centavos(intent['amount_received'])
    reserva.reembolsada_en = timezone.now()
    reserva.full_clean()
    reserva.save()
    return SIN_CUPO_REEMBOLSADO


def _cancelar_codigo_promocional_invalido(reserva, intent, empresa):
    """El codigo promocional se agoto, vencio o se desactivo mientras el
    cliente pagaba. Mismo remedio que sin cupo: se devuelve el 100% y la
    reserva queda cancelada con el motivo real, no uno prestado de cupo."""
    if not reembolsar(intent, 'codigo promocional invalido', empresa):
        return FALLO_REEMBOLSO

    reserva.estado = Reserva.Estado.CANCELADA
    reserva.motivo_cancelacion = (
        'El codigo promocional ya no era valido al confirmar el pago '
        '(se agoto, vencio o se desactivo). Reembolso automatico.'
    )
    reserva.cancelada_en = timezone.now()
    reserva.reembolsada = True
    reserva.monto_reembolsado = de_centavos(intent['amount_received'])
    reserva.reembolsada_en = timezone.now()
    reserva.full_clean()
    reserva.save()
    return CODIGO_INVALIDO_REEMBOLSADO


def _reserva_del_cargo(objeto, empresa):
    """La reserva a la que pertenece un Charge o un Dispute, via su
    PaymentIntent, acotada a `empresa` — sin RLS (sqlite, tests) nada mas
    evita que un stripe_payment_intent_id repetido entre Empresas (no deberia
    pasar, pero no hay unicidad que lo garantice) cruce el reembolso/disputa
    a la reserva equivocada."""
    try:
        intent_id = objeto['payment_intent']
    except (KeyError, TypeError):
        return None
    if not intent_id:
        return None
    return (
        Reserva.objects.select_for_update()
        .filter(stripe_payment_intent_id=intent_id, empresa=empresa)
        .first()
    )


@transaction.atomic
def aplicar_reembolso(charge, empresa):
    """Marca la reserva como reembolsada cuando el dinero se devuelve.

    Cubre los reembolsos hechos a mano desde el panel de Stripe: sin esto, los
    jefes devuelven el dinero y la reserva sigue figurando como cobrada.
    """
    reserva = _reserva_del_cargo(charge, empresa)
    if reserva is None:
        logger.warning('Reembolso de %s sin reserva asociada', charge['id'])
        return None

    reserva.reembolsada = True
    reserva.monto_reembolsado = _monto_devuelto(charge, reserva)
    reserva.reembolsada_en = reserva.reembolsada_en or timezone.now()
    reserva.save(update_fields=['reembolsada', 'monto_reembolsado', 'reembolsada_en'])
    logger.info('Reserva %s marcada como reembolsada por el cargo %s', reserva.pk, charge['id'])
    return reserva


def _monto_devuelto(charge, reserva):
    """Lo que Stripe reporta devuelto en ese cargo. `amount_refunded` es
    acumulado (cubre reembolsos parciales); si no viene, se asume que se
    devolvio todo lo cobrado."""
    try:
        return de_centavos(charge['amount_refunded'])
    except (KeyError, TypeError):
        return reserva.monto_pagado


@transaction.atomic
def aplicar_disputa(charge, abierta, empresa):
    """Levanta o baja la bandera de disputa (contracargo).

    No cambia el estado de la reserva: quien decide que hacer con un viaje en
    disputa es una persona, no el sistema. Lo unico que hace falta es que se vea
    en el panel antes de que salgan al mar.
    """
    reserva = _reserva_del_cargo(charge, empresa)
    if reserva is None:
        logger.warning('Disputa de %s sin reserva asociada', charge['id'])
        return None

    reserva.en_disputa = abierta
    reserva.save(update_fields=['en_disputa'])
    logger.error(
        'Reserva %s %s disputa (cargo %s)',
        reserva.pk, 'entro en' if abierta else 'salio de', charge['id'],
    )
    return reserva


def reembolsar(intent, motivo, empresa):
    """Devuelve el cobro completo con el cliente de Stripe de `empresa`. La
    `idempotency_key` va en `options` (segundo argumento), no en `params`
    (Revision 6, N-D) — evita que un reintento del webhook genere un segundo
    reembolso del mismo intent."""
    cliente = configurar_stripe(empresa)
    try:
        cliente.refunds.create(
            {'payment_intent': intent['id']},
            {'idempotency_key': f'refund-{intent["id"]}'},
        )
    except stripe.StripeError:
        logger.exception('Fallo el reembolso de %s (%s)', intent['id'], motivo)
        return False
    return True
