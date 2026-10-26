"""Marcar como pagada, por transferencia, una reserva que se quedo esperando el pago.

Caso real: el cliente empezo a reservar en la web, tuvo problemas con la tarjeta o con la plataforma y prefiere
transferir. La vendedora retoma ese checkout abandonado, recibe la transferencia y la marca pagada. Una sola
definicion de "se puede" y de "como se hace", para que la pantalla y las pruebas no puedan decidir distinto.

Hace lo mismo que el webhook de Stripe al confirmar un pago (`payments.services.aplicar_pago_exitoso`):
la reserva pasa a `pagada`, se suelta el apartado temporal, se valida y se aparta el cupo de verdad, y al
confirmar la transaccion sale el correo de confirmacion al cliente. Lo unico distinto es el dinero: entra por
`monto_transferencia` (con su sello de fecha y usuario, que es lo que lee Finanzas) y no por `monto_pagado`.
"""
from decimal import Decimal, InvalidOperation

import stripe
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.bookings.cupo import SinCupoError
from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar
from apps.notifications.services import notificar_reserva_pagada
from apps.payments.stripe_client import configurar_stripe
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Notificacion
from apps.tenancy.notificaciones import registrar_notificacion

from .models import Reserva


class ErrorDeTransferencia(Exception):
    """Algo impide marcarla pagada. El mensaje esta escrito para quien opera, no para el log."""


def puede_marcarse_pagada(reserva):
    """Solo una reserva suelta que sigue esperando el pago. Las de una orden cruza-empresa se cobran con
    captura manual en cada cuenta de Stripe y no se pueden saldar a mano de una en una."""
    return reserva.estado == Reserva.Estado.PENDIENTE_PAGO and reserva.orden_id is None


def monto_sugerido(reserva):
    """Lo que normalmente se transfiere: el total de la reserva."""
    return reserva.precio_total


def _como_decimal(monto):
    try:
        valor = Decimal(str(monto).strip())
    except (InvalidOperation, ValueError):
        raise ErrorDeTransferencia('El monto no es un número válido.') from None
    if not valor.is_finite() or valor <= 0:
        raise ErrorDeTransferencia('El monto de la transferencia debe ser mayor que cero.')
    return valor.quantize(Decimal('0.01'))


INTENT_COBRADO_O_EN_CURSO = {'succeeded', 'processing', 'requires_capture'}
INTENT_ANULABLE = {'requires_payment_method', 'requires_confirmation', 'requires_action'}


def _cerrar_cobro_con_tarjeta(reserva):
    """El checkout abandonado tiene un PaymentIntent vivo: si queda abierto y el cliente lo completa despues, cobra una
    segunda vez y el webhook lo toma por evento repetido. Falla cerrado: si no se puede anular, no se salda."""
    pi_id = reserva.stripe_payment_intent_id
    empresa = reserva.empresa
    if not pi_id or not empresa.stripe_secret_key:
        return
    cliente = configurar_stripe(empresa)
    try:
        intent = cliente.payment_intents.retrieve(pi_id)
        if intent.status in INTENT_COBRADO_O_EN_CURSO:
            raise ErrorDeTransferencia(
                'El cliente ya pagó o está pagando con tarjeta esta reserva. No la marques por transferencia: '
                'revisa el cobro en Stripe.')
        if intent.status in INTENT_ANULABLE:
            cliente.payment_intents.cancel(
                intent.id, options={'idempotency_key': f'transferencia-{reserva.pk}-cancel'})
    except stripe.InvalidRequestError as exc:
        if getattr(exc, 'code', None) != 'resource_missing':
            raise ErrorDeTransferencia('No se pudo cerrar el cobro con tarjeta pendiente. Intenta de nuevo.') from exc
    except stripe.StripeError as exc:
        raise ErrorDeTransferencia('No se pudo cerrar el cobro con tarjeta pendiente. Intenta de nuevo.') from exc


def marcar_pagada_por_transferencia(reserva_pk, monto, usuario):
    """Registra la transferencia y deja la reserva pagada. Devuelve la reserva.

    Vuelve a leer la fila con candado: la pantalla pudo mostrar una reserva que otra persona (o el propio
    cliente, pagando con tarjeta) ya cambio. Dos clics a la vez se turnan y el segundo ya no la encuentra
    pendiente. Si no hay cupo, nada se guarda (la transaccion entera se deshace) y el mensaje dice por que.
    """
    monto = _como_decimal(monto)
    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().filter(pk=reserva_pk).first()
        if reserva is None:
            raise ErrorDeTransferencia('No se encontró la reserva.')
        if not puede_marcarse_pagada(reserva):
            raise ErrorDeTransferencia(
                'Esta reserva ya no está esperando el pago: se pagó, se canceló o es parte de un paquete de varias empresas.')
        if reserva.precio_total is None:
            raise ErrorDeTransferencia(
                'Esta reserva todavía no tiene precio calculado (el cliente no llegó a pagar). '
                'Fija el precio en la reserva antes de registrar la transferencia.')
        if monto > reserva.precio_total:
            raise ErrorDeTransferencia(
                f'El monto ({monto}) es mayor que el total de la reserva ({reserva.precio_total} {reserva.moneda}).')
        _cerrar_cobro_con_tarjeta(reserva)

        reserva._usuario_dinero = usuario
        reserva.monto_transferencia = monto
        reserva.transferencia_registrada_en = timezone.now()
        reserva.transferencia_registrada_por = usuario
        reserva.pagada_en = reserva.transferencia_registrada_en
        reserva.estado = Reserva.Estado.PAGADA
        reserva.apartado_hasta = None
        reserva.apartado_demanda = None
        try:
            reserva.full_clean()
            reserva.save()
            reservar_cupo_al_confirmar(reserva)
        except SinCupoError as exc:
            raise ErrorDeTransferencia(f'Ya no hay lugar para esa fecha: {exc}') from exc
        except DjangoValidationError as exc:
            raise ErrorDeTransferencia('No se pudo confirmar: ' + ' '.join(exc.messages)) from exc
        except IntegrityError as exc:
            raise ErrorDeTransferencia('Ya no hay habitación disponible esas fechas.') from exc

        # El correo sale al confirmar la transaccion, ya con la reserva guardada, y dentro de su propio alcance
        # de empresa: SET LOCAL de la transaccion muere al COMMIT (mismo cuidado que en el webhook).
        empresa_id = reserva.empresa_id
        pk = reserva.pk
        # El resultado se llena cuando el correo sale, que es al confirmar la transaccion MAS EXTERNA: dentro del admin
        # eso pasa despues de que la vista respondio, asi que la pantalla no debe dar por fallido un resultado vacio.
        reserva.resultado_notificacion = resultado = {}
        transaction.on_commit(lambda: _avisar_al_cliente(pk, empresa_id, resultado, usuario, monto))
    return reserva


def _avisar_al_cliente(reserva_pk, empresa_id, resultado, usuario=None, monto=None):
    empresa = Empresa.objects.get(pk=empresa_id)
    with scope.con_empresa(empresa):
        reserva = Reserva.objects.select_related('servicio', 'paquete').filter(pk=reserva_pk).first()
        if reserva is None:
            return
        resultado.update(notificar_reserva_pagada(reserva))  # nunca lanza

        # Constancia en el feed, ya dentro del alcance reabierto (el de la transaccion que encolo esto murio al COMMIT).
        enlace = reverse('admin:bookings_reserva_change', args=[reserva.pk])
        registrar_notificacion(
            empresa, Notificacion.Nivel.EXITO,
            f'Reserva pagada por transferencia: {reserva.nombre_cliente} · {monto} {reserva.moneda}.',
            tipo=Notificacion.Tipo.RESERVA_NUEVA, actor=usuario, enlace_url=enlace, enlace_texto='Ver reserva',
        )
        if not resultado.get('email'):
            registrar_notificacion(
                empresa, Notificacion.Nivel.AVISO,
                f'No se pudo mandar el correo de confirmación a {reserva.nombre_cliente}. Avísale por WhatsApp.',
                tipo=Notificacion.Tipo.TRANSFERENCIA, actor=usuario,
                motivo='' if reserva.correo_cliente else 'la reserva no tiene correo del cliente',
                enlace_url=enlace, enlace_texto='Ver reserva',
            )
