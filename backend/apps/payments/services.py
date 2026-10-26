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
from decimal import Decimal

import stripe
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.utils import OperationalError
from django.urls import reverse
from django.utils import timezone

from apps.bookings.cupo import SinCupoError
from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar
from apps.bookings.models import Orden, Reserva
from apps.bookings.orden_lectura import reservas_de_orden
from apps.fleet.enums import EstrategiaPrecio
from apps.notifications.services import (
    notificar_fallo_reembolso,
    notificar_reembolso_sin_cupo,
    notificar_reserva_pagada,
)

try:
    from apps.notifications.services import notificar_orden_pagada
except ImportError:
    def notificar_orden_pagada(orden):
        pass
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Notificacion
from apps.tenancy.notificaciones import registrar_notificacion

from .estrategias_precio import precio_traslado_congelado
from .pricing import a_centavos, con_iva, de_centavos, monto_inicial
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


def aplicar_pago_exitoso(intent, empresa):
    """Reintenta una vez la transacción entera si Postgres aborta por deadlock."""
    for intento in range(2):
        try:
            return _aplicar_pago_exitoso_transaccional(intent, empresa)
        except OperationalError as exc:
            causa = exc.__cause__
            sqlstate = getattr(causa, 'sqlstate', None) or getattr(causa, 'pgcode', None)
            if sqlstate != '40P01' or intento:
                raise
            logger.warning('Deadlock al aplicar el pago %s; se reintenta una vez.', intent['id'])


@transaction.atomic
def _aplicar_pago_exitoso_transaccional(intent, empresa):
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
    reserva.apartado_hasta = None
    reserva.apartado_demanda = None
    try:
        with transaction.atomic():
            reserva.full_clean()
            reserva.save()
            reservar_cupo_al_confirmar(reserva)
    except DjangoValidationError as exc:
        # `codigo_promocional` es la unica clave que Reserva.clean() usa para
        # este rechazo (ver validar_codigo_promocional_en_pago) — cualquier
        # otra cosa (cupo, deslinde, etc.) cae en el motivo generico de abajo.
        if 'codigo_promocional' in getattr(exc, 'error_dict', {}):
            return _cancelar_codigo_promocional_invalido(reserva, intent, empresa)
        if reserva.orden_id:
            return _cancelar_orden_sin_cupo(reserva, intent, empresa)
        causa = 'cupo' if _es_error_sin_cupo(exc) else 'otra'
        motivo = None if causa == 'cupo' else str(exc)
        return _cancelar_sin_cupo(reserva, intent, empresa, motivo=motivo, causa=causa)
    except SinCupoError as exc:
        if reserva.orden_id:
            nombre_servicio = reserva.servicio.nombre if reserva.servicio else 'servicio'
            return _cancelar_orden_sin_cupo(reserva, intent, empresa, motivo=f'sin cupo en {nombre_servicio}')
        return _cancelar_sin_cupo(reserva, intent, empresa, motivo=str(exc), causa='cupo')

    # En linea y en el alcance de esta empresa (el webhook y la conciliacion ya lo abrieron): comparte el COMMIT del
    # cobro, y si el cobro se revierte la notificacion tambien. Nunca lanza.
    _notificar_reserva_nueva(reserva, empresa)

    if reserva.orden_id:
        orden = Orden.objects.select_for_update().get(pk=reserva.orden_id)
        # NO orden.reservas.all() — bajo el RLS de esta empresa solo vería su
        # propia reserva. estado_reservas_de_orden salta RLS, acotado a esta orden.
        filas = reservas_de_orden(orden.pk)  # wrapper de la función SECURITY DEFINER
        todas_pagadas = all(f['estado'] in ('pagada', 'asignada') for f in filas)
        if todas_pagadas:
            if orden.estado != Orden.Estado.CAPTURADA:
                orden.transicionar('capturada')
                orden.save()
            if orden.notificada_en is None:
                notificar_orden_pagada(orden)   # nunca lanza
                orden.notificada_en = timezone.now()
                orden.save(update_fields=['notificada_en'])
    else:
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


def _producto_de(reserva):
    if reserva.paquete_id:
        return reserva.paquete.nombre
    if reserva.servicio_id:
        return reserva.servicio.nombre
    return 'Pesca deportiva'


def _enlace_a(reserva):
    return reverse('admin:bookings_reserva_change', args=[reserva.pk])


def _notificar_reserva_nueva(reserva, empresa):
    registrar_notificacion(
        empresa, Notificacion.Nivel.EXITO,
        f'Nueva reserva pagada: {reserva.nombre_cliente} · {_producto_de(reserva)} · {reserva.fecha:%d/%m/%Y}.',
        tipo=Notificacion.Tipo.RESERVA_NUEVA, enlace_url=_enlace_a(reserva), enlace_texto='Ver reserva',
    )


def _resolver_cobro_repetido(reserva, intent, empresa):
    """La reserva ya no esta pendiente. Si es el mismo intent, es Stripe
    reintentando el evento y no hay nada que hacer. Si es OTRO intent, al
    cliente le cobraron dos veces: se devuelve el segundo de inmediato."""
    # Solo es "evento repetido" si ese intent ya se aplico (dejo `monto_pagado`). Una reserva saldada por transferencia
    # conserva el intent del checkout abandonado sin haberlo cobrado: si ese cobro llega, es un doble cobro.
    if reserva.stripe_payment_intent_id == intent['id'] and reserva.monto_pagado:
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

    precio_total = reserva.precio_total
    if reserva.servicio_id and reserva.servicio.estrategia_precio == EstrategiaPrecio.POR_RUTA:
        try:
            neto = precio_traslado_congelado(
                getattr(reserva, 'detalle_transporte', None), reserva.moneda,
            ) - (reserva.descuento_aplicado or 0)
            _, precio_total = con_iva(neto, reserva.iva_tasa or 0)
        except ValueError as exc:
            logger.error('Reserva %s: %s', reserva.pk, exc)
            return
        if precio_total != reserva.precio_total:
            logger.error(
                'Descuadre en el total de la reserva %s: detalle congelado %s, precio_total %s',
                reserva.pk, precio_total, reserva.precio_total,
            )

    porcentaje = (
        reserva.paquete.porcentaje_anticipo
        if reserva.paquete_id
        else (reserva.servicio.porcentaje_anticipo if reserva.servicio_id else 30)
    )
    esperado = a_centavos(monto_inicial(precio_total, reserva.forma_pago, porcentaje=porcentaje))
    if intent['amount_received'] != esperado:
        logger.error(
            'Descuadre en la reserva %s: se esperaban %s centavos y llegaron %s',
            reserva.pk, esperado, intent['amount_received'],
        )


def _cancelar_orden_sin_cupo(reserva, intent, empresa, motivo=None):
    """Compensación de orden: el componente se quedó sin cupo al confirmar.
    Toda la compensación pasa por revertir_orden, incluida esta reserva."""
    from apps.payments.ordenes import revertir_orden

    nombre_servicio = reserva.servicio.nombre if reserva.servicio else 'servicio'
    motivo_real = motivo or f'sin cupo en {nombre_servicio}'

    orden = Orden.objects.select_for_update().get(pk=reserva.orden_id)
    revertir_orden(orden, motivo_real)
    reserva.refresh_from_db()
    return SIN_CUPO_REEMBOLSADO if reserva.reembolsada else FALLO_REEMBOLSO


def _es_error_sin_cupo(exc):
    """Determina si la excepcion corresponde a una falla de cupo.

    Devuelve True si es SinCupoError o una ValidationError cuyos codigos
    (recorriendo error_dict y error_list anidados) incluyen 'sin_cupo'.
    """
    if isinstance(exc, SinCupoError):
        return True
    if not isinstance(exc, DjangoValidationError):
        return False

    vistos = set()

    def _tiene_codigo(e):
        if id(e) in vistos:
            return False
        vistos.add(id(e))

        if getattr(e, 'code', None) == 'sin_cupo':
            return True
        if hasattr(e, 'error_dict'):
            for lista in e.error_dict.values():
                for sub_e in lista:
                    if _tiene_codigo(sub_e):
                        return True
        if hasattr(e, 'error_list'):
            for sub_e in e.error_list:
                if sub_e is not e and _tiene_codigo(sub_e):
                    return True
        return False

    return _tiene_codigo(exc)


def _gestionar_fallo_reembolso(reserva, intent, empresa, motivo):
    """Alerta urgente deduplicada cuando falla el reembolso de una reserva."""
    ahora = timezone.now()
    filas = Reserva.objects.filter(
        pk=reserva.pk,
        alerta_reembolso_fallido_en__isnull=True,
    ).update(alerta_reembolso_fallido_en=ahora)
    if filas:
        monto = de_centavos(intent.get('amount_received') or 0)
        empresa_id = empresa.pk
        reserva_id = reserva.pk
        motivo_alerta = motivo or 'Fallo al procesar el reembolso en Stripe'
        # Sellado una sola vez por reserva (el UPDATE de arriba): una sola notificacion, no una por reintento.
        registrar_notificacion(
            empresa, Notificacion.Nivel.ERROR, f'El reembolso de {reserva.nombre_cliente} falló.',
            motivo=motivo_alerta, tipo=Notificacion.Tipo.REEMBOLSO,
            enlace_url=_enlace_a(reserva), enlace_texto='Ver reserva',
        )

        def _notificar_fallo():
            try:
                with scope.con_empresa(Empresa.objects.get(pk=empresa_id)):
                    r = Reserva.objects.get(pk=reserva_id)
                    notificar_fallo_reembolso(r, monto=monto, motivo=motivo_alerta)
            except Exception:
                logger.exception(
                    'Fallo inesperado al enviar alerta de fallo de reembolso para reserva %s',
                    reserva_id,
                )

        transaction.on_commit(_notificar_fallo)


def _cancelar_sin_cupo(reserva, intent, empresa, motivo=None, causa='cupo'):
    """El dia se lleno mientras el cliente pagaba. Se devuelve el 100% y la
    reserva queda cancelada con el motivo real, para que la vendedora la vea en
    su panel en vez de que desaparezca como 'pendiente de pago'."""
    if not reembolsar(intent, 'sin cupo', empresa):
        _gestionar_fallo_reembolso(reserva, intent, empresa, motivo=motivo or 'Sin cupo')
        return FALLO_REEMBOLSO

    reserva.estado = Reserva.Estado.CANCELADA
    reserva.motivo_cancelacion = motivo or 'Sin cupo disponible al confirmar el pago. Reembolso automatico.'
    reserva.cancelada_en = timezone.now()
    reserva.reembolsada = True
    reserva.monto_reembolsado = de_centavos(intent['amount_received'])
    reserva.reembolsada_en = timezone.now()
    reserva.apartado_hasta = None
    reserva.apartado_demanda = None
    reserva.full_clean()
    reserva.save()

    empresa_id = empresa.pk
    reserva_id = reserva.pk

    def _notificar():
        try:
            with scope.con_empresa(Empresa.objects.get(pk=empresa_id)):
                r = Reserva.objects.select_related('servicio', 'paquete', 'empresa').get(pk=reserva_id)
                notificar_reembolso_sin_cupo(r, causa=causa, motivo=motivo)
        except Exception:
            logger.exception(
                'Fallo inesperado al notificar cancelacion con reembolso de la reserva %s',
                reserva_id,
            )

    transaction.on_commit(_notificar)
    return SIN_CUPO_REEMBOLSADO


def _cancelar_codigo_promocional_invalido(reserva, intent, empresa):
    """El codigo promocional se agoto, vencio o se desactivo mientras el
    cliente pagaba. Mismo remedio que sin cupo: se devuelve el 100% y la
    reserva queda cancelada con el motivo real, no uno prestado de cupo."""
    if not reembolsar(intent, 'codigo promocional invalido', empresa):
        _gestionar_fallo_reembolso(reserva, intent, empresa, motivo='codigo promocional invalido')
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
    reserva.apartado_hasta = None
    reserva.apartado_demanda = None
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


MOTIVO_REEMBOLSO_DESDE_STRIPE = (
    'Reembolso completo hecho desde el panel de Stripe. '
    'La reserva se cancelo sola al registrarse la devolucion.'
)

# Estados en los que un reembolso total cancela la reserva: la salida todavia no
# ocurre y la reserva esta ocupando cupo, panga y capitan. Una `completada` ya
# viajo (se anota el dinero, no se reescribe la historia) y una `cancelada` ya
# soltó todo.
ESTADOS_QUE_SE_CANCELAN_AL_REEMBOLSAR = (Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA)


@transaction.atomic
def aplicar_reembolso(charge, empresa):
    """Registra un reembolso hecho en Stripe (`charge.refunded`).

    Cubre los reembolsos hechos a mano desde el panel de Stripe: sin esto, los
    jefes devuelven el dinero y la reserva sigue figurando como cobrada, con su
    cupo, su panga y su capitan ocupados.

    - **Parcial** (se devolvio menos de lo cobrado): solo anota cuanto salio. La
      reserva sigue en pie; ni se cancela ni se marca `reembolsada`.
    - **Total**: la deja igual que la accion «Cancelar por mal clima» + reembolso
      (cancelada, `reembolsada`, cupo y panga liberados).

    `amount_refunded` del cargo es acumulado, asi que el evento es idempotente
    por construccion: el que no sube lo ya anotado (un reintento de Stripe, o uno
    atrasado que llega despues de otro mayor) no cambia nada. Un evento que si
    sube el monto es un reembolso nuevo y actualiza `reembolsada_en`.
    """
    reserva = _reserva_del_cargo(charge, empresa)
    if reserva is None:
        logger.warning('Reembolso de %s sin reserva asociada', charge['id'])
        return None

    if reserva.estado == Reserva.Estado.PENDIENTE_PAGO:
        # El reembolso le gano la carrera a `payment_intent.succeeded`: todavia no
        # hay cobro registrado y anotar la salida sin su entrada descuadraria
        # finanzas. Queda en el log para que se concilie a mano.
        logger.error(
            'Reembolso del cargo %s llego antes que el pago de la reserva %s (sigue pendiente_pago); '
            'no se registra.', charge['id'], reserva.pk,
        )
        return None

    devuelto = _monto_devuelto(charge, reserva)
    if devuelto <= (reserva.monto_reembolsado or Decimal('0.00')):
        logger.info('Reembolso del cargo %s ya registrado en la reserva %s', charge['id'], reserva.pk)
        return reserva

    reserva.monto_reembolsado = devuelto
    reserva.reembolsada_en = timezone.now()

    if not _es_reembolso_total(charge, reserva, devuelto):
        reserva.save(update_fields=['monto_reembolsado', 'reembolsada_en'])
        logger.info(
            'Reserva %s: reembolso parcial de %s por el cargo %s', reserva.pk, devuelto, charge['id'],
        )
        registrar_notificacion(
            empresa, Notificacion.Nivel.AVISO,
            f'Reembolso parcial registrado: {devuelto:.2f} {reserva.moneda} · {reserva.nombre_cliente}.',
            tipo=Notificacion.Tipo.REEMBOLSO, enlace_url=_enlace_a(reserva), enlace_texto='Ver reserva',
        )
        return reserva

    reserva.reembolsada = True
    if reserva.estado in ESTADOS_QUE_SE_CANCELAN_AL_REEMBOLSAR:
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.motivo_cancelacion = reserva.motivo_cancelacion or MOTIVO_REEMBOLSO_DESDE_STRIPE
        reserva.cancelada_en = timezone.now()
        reserva.apartado_hasta = None
        reserva.apartado_demanda = None
        # Guardado completo (no `update_fields`): es lo que libera las ocupaciones
        # de hospedaje, los componentes del paquete y los viajes de transporte, y
        # lo que hace que el aviso de asignacion ya no le toque a esta reserva.
        # Sin `full_clean()`: el dinero ya salio de Stripe y ninguna validacion
        # puede impedir que la reserva lo refleje.
        reserva.save()
    else:
        reserva.save(update_fields=['monto_reembolsado', 'reembolsada_en', 'reembolsada'])
    logger.info('Reserva %s: reembolso total por el cargo %s (%s)', reserva.pk, charge['id'], reserva.estado)
    cancelada = ' La reserva quedó cancelada.' if reserva.estado == Reserva.Estado.CANCELADA else ''
    registrar_notificacion(
        empresa, Notificacion.Nivel.AVISO,
        f'Reembolso total registrado: {devuelto:.2f} {reserva.moneda} · {reserva.nombre_cliente}.{cancelada}',
        tipo=Notificacion.Tipo.REEMBOLSO, enlace_url=_enlace_a(reserva), enlace_texto='Ver reserva',
    )
    return reserva


def _campo_del_cargo(charge, nombre):
    """Un dato del `Charge`, o None. Llega como dict o como StripeObject segun
    la entrada, y un StripeObject no siempre tiene `.get`."""
    try:
        return charge[nombre]
    except (KeyError, TypeError, AttributeError):
        return None


def _monto_devuelto(charge, reserva):
    """Lo que Stripe reporta devuelto en ese cargo. `amount_refunded` es
    acumulado (cubre reembolsos parciales); si no viene, se asume que se
    devolvio todo lo cobrado."""
    devuelto = _campo_del_cargo(charge, 'amount_refunded')
    if devuelto is None:
        return reserva.monto_pagado or Decimal('0.00')
    return de_centavos(devuelto)


def _es_reembolso_total(charge, reserva, devuelto):
    """True si ya se devolvio todo lo cobrado. Stripe pone `refunded=true` solo
    cuando el cargo se devolvio completo; ademas se compara contra lo que esta
    reserva cobro, que es lo que importa si el cargo trae otro monto."""
    if _campo_del_cargo(charge, 'refunded') is True:
        return True
    cobrado = reserva.monto_pagado
    if not cobrado:
        centavos = _campo_del_cargo(charge, 'amount_captured') or _campo_del_cargo(charge, 'amount')
        cobrado = de_centavos(centavos) if centavos else None
    return bool(cobrado) and devuelto >= cobrado


@transaction.atomic
def aplicar_disputa(charge, abierta, empresa, resultado=None):
    """Levanta o baja la bandera de disputa (contracargo).

    No cambia el estado de la reserva: quien decide que hacer con un viaje en
    disputa es una persona, no el sistema. Lo unico que hace falta es que se vea
    en el panel antes de que salgan al mar.

    `resultado` es el `status` con que Stripe cierra la disputa. `lost` significa que
    Stripe se quedo con el dinero: se anota como salida aparte (`contracargo_perdido`) para
    que Finanzas no siga contando ese monto «en la cuenta». `won` borra una anotacion
    anterior. Es idempotente: repetir el evento deja lo mismo.
    """
    reserva = _reserva_del_cargo(charge, empresa)
    if reserva is None:
        logger.warning('Disputa de %s sin reserva asociada', charge['id'])
        return None

    reserva.en_disputa = abierta
    campos = ['en_disputa']
    if not abierta and resultado == 'lost':
        monto = _campo_del_cargo(charge, 'amount')
        if monto and reserva.contracargo_perdido is None:
            reserva.contracargo_perdido = de_centavos(monto)
            reserva.contracargo_perdido_en = timezone.now()
            campos += ['contracargo_perdido', 'contracargo_perdido_en']
    elif not abierta and resultado == 'won' and reserva.contracargo_perdido is not None:
        reserva.contracargo_perdido = None
        reserva.contracargo_perdido_en = None
        campos += ['contracargo_perdido', 'contracargo_perdido_en']
    reserva.save(update_fields=campos)
    logger.error(
        'Reserva %s %s disputa (cargo %s)%s',
        reserva.pk, 'entro en' if abierta else 'salio de', charge['id'],
        f', resultado {resultado}' if resultado else '',
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
