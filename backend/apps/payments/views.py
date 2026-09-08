from decimal import Decimal
import logging
import uuid

import stripe
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Reserva, codigo_promocional_valido, evaluar_codigo_promocional
from apps.fleet.models import CodigoPromocional, Tarifa
from apps.tenancy import scope

from .estrategias_precio import DemandaPrecio, obtener_estrategia_precio
from .pricing import (
    a_centavos,
    cargo_por_descuento,
    cargo_por_extra,
    cargo_por_personas,
    monto_inicial,
    personas_extra,
    precio_paquete_total,
)
from .stripe_client import configurar_stripe
from .services import aplicar_disputa, aplicar_pago_exitoso, aplicar_reembolso

logger = logging.getLogger(__name__)

INTENT_REUTILIZABLE = {'requires_payment_method', 'requires_confirmation', 'requires_action'}
INTENT_YA_COBRANDO = {'succeeded', 'processing'}


class PagoEnCurso(Exception):
    """El intent de la reserva ya esta cobrando o cobro: no se crea otro."""


class CrearPagoView(APIView):
    """Crea (o reutiliza) el PaymentIntent de Stripe de una reserva, con las
    llaves de la Empresa resuelta por `empresa_slug` en la URL.

    El monto se calcula aqui — tarifa en la moneda de la reserva + amenidades +
    100%/30% — y nunca se confia el total que manda el cliente. Cuenta estandar
    de Stripe, no Connect (ver docs/contexto-negocio.md).

    Es idempotente a proposito: darle dos veces a "Ir a pagar", recargar el
    checkout o cambiar de amenidades reusa el mismo intent en vez de dejar
    intents sueltos que podrian terminar cobrando dos veces.
    """

    throttle_scope = 'pagos'

    def post(self, request, empresa_slug, pk):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            return self._post(request, empresa, pk)

    def _post(self, request, empresa, pk):
        reserva = get_object_or_404(Reserva, pk=pk, empresa=empresa)

        # Los ids de reserva son consecutivos y la API es publica: sin esto,
        # cualquiera podria adivinar un id y generar cobros sobre la reserva de
        # otra persona. El checkout_id lo genera el navegador del cliente.
        if not reserva.checkout_id or str(reserva.checkout_id) != str(request.data.get('checkout_id')):
            return Response({'detail': 'checkout_id invalido para esta reserva.'}, status=403)

        if reserva.estado != Reserva.Estado.PENDIENTE_PAGO:
            return Response({'detail': 'Esta reserva ya no esta pendiente de pago.'}, status=409)

        if reserva.paquete_id:
            extras_pers = list(reserva.paquete_personalizaciones.values_list('servicio_personalizacion_id', 'cantidad')) if hasattr(reserva, 'paquete_personalizaciones') else []
            precio_base_servicio = precio_paquete_total(
                reserva.paquete,
                personalizaciones_extra=extras_pers,
                personas=reserva.numero_personas,
                moneda=reserva.moneda,
            )
            if precio_base_servicio is None:
                return Response({'detail': f'El paquete no tiene precio en {reserva.moneda}.'}, status=503)
            porcentaje = reserva.paquete.porcentaje_anticipo
        elif reserva.servicio_id:
            estrategia = obtener_estrategia_precio(reserva.servicio.estrategia_precio)
            demanda = DemandaPrecio(personas=reserva.numero_personas, moneda=reserva.moneda, noches=reserva.noches)
            try:
                precio_base_servicio = estrategia.calcular_base(reserva.servicio, demanda)
            except ValueError as e:
                return Response({'detail': str(e)}, status=503)
            porcentaje = reserva.servicio.porcentaje_anticipo
        else:
            tarifa = Tarifa.de(empresa)
            if tarifa is None:
                return Response({'detail': 'Tarifa no configurada.'}, status=503)

            precio_tour = tarifa.precio_en(reserva.moneda)
            if precio_tour is None:
                return Response({'detail': f'No hay precio configurado en {reserva.moneda}.'}, status=503)

            precio_persona_extra = tarifa.persona_extra_en(reserva.moneda)
            if personas_extra(reserva.numero_personas) and precio_persona_extra is None:
                return Response(
                    {'detail': f'No hay cargo por persona extra configurado en {reserva.moneda}.'},
                    status=503,
                )
            precio_base_servicio = precio_tour + cargo_por_personas(precio_persona_extra or 0, reserva.numero_personas)
            porcentaje = 30

        forma_pago = request.data.get('forma_pago', Reserva.FormaPago.COMPLETO)
        if forma_pago not in Reserva.FormaPago.values:
            return Response({'detail': 'forma_pago invalida.'}, status=400)

        if reserva.paquete_id or (reserva.servicio_id and reserva.servicio.tipo_servicio != 'pesca'):
            cargo_extras, extras_a_borrar, extras_a_congelar = Decimal('0.00'), [], []
        else:
            cargo_extras, extras_a_borrar, extras_a_congelar, error = self._resolver_extras(reserva)
            if error:
                return Response({'detail': error}, status=503)

        subtotal = (
            precio_base_servicio
            + cargo_extras
        )

        codigo_promocional, descuento, error = self._resolver_codigo_promocional(
            request, reserva, subtotal, empresa,
        )
        if error:
            return Response({'detail': error}, status=400)

        precio_total = subtotal - descuento
        monto_a_cobrar = monto_inicial(precio_total, forma_pago, porcentaje=porcentaje)

        if not empresa.stripe_secret_key:
            return Response({'detail': 'Stripe no esta configurado todavia.'}, status=503)

        cliente = configurar_stripe(empresa)
        try:
            intent = self._intent_de(cliente, reserva, monto_a_cobrar)
        except PagoEnCurso:
            return Response(
                {'detail': 'Ya hay un cobro en curso para esta reserva.'}, status=409
            )
        except stripe.StripeError:
            logger.exception('Stripe fallo al preparar el pago de la reserva %s', reserva.pk)
            return Response({'detail': 'No se pudo iniciar el pago. Intenta de nuevo.'}, status=502)

        with transaction.atomic():
            for extra in extras_a_borrar:
                extra.delete()
            for extra, precio_unitario, cantidad in extras_a_congelar:
                extra.precio_unitario = precio_unitario
                extra.cantidad = cantidad
                extra.save(update_fields=['precio_unitario', 'cantidad'])

            reserva.precio_total = precio_total
            reserva.forma_pago = forma_pago
            reserva.stripe_payment_intent_id = intent.id
            reserva.codigo_promocional = codigo_promocional
            reserva.descuento_aplicado = descuento if codigo_promocional else None
            reserva.save(update_fields=[
                'precio_total', 'forma_pago', 'stripe_payment_intent_id',
                'codigo_promocional', 'descuento_aplicado',
            ])

        return Response({
            'client_secret': intent.client_secret,
            'publishable_key': empresa.stripe_publishable_key,
            'monto_a_cobrar': str(monto_a_cobrar),
            'moneda': reserva.moneda,
        })

    def _resolver_extras(self, reserva):
        """Recorre lo que el cliente selecciono en el checkout y decide, sin
        tocar la base: que se cae (item desactivado desde que se eligio) y que
        se congela con el precio VIGENTE del catalogo. Devuelve (cargo_total,
        a_borrar, a_congelar, error). Sin filtro `empresa=` propio: opera sobre
        `reserva.extras_seleccionados`, ya acotado por la reserva misma."""
        cargo_total = 0
        a_borrar = []
        a_congelar = []
        for extra in reserva.extras_seleccionados.select_related('extras_item'):
            item = extra.extras_item
            if not item.activo:
                a_borrar.append(extra)
                continue
            precio = item.precio_en(reserva.moneda)
            if precio is None:
                return 0, [], [], f'No hay precio de "{item.nombre}" configurado en {reserva.moneda}.'
            cantidad = reserva.numero_personas if item.cobrar_por_persona else 1
            if item.cantidad_editable and extra.cantidad_solicitada is not None:
                cantidad = max(1, min(extra.cantidad_solicitada, reserva.numero_personas))
            cargo = cargo_por_extra(precio, item.cobrar_por_persona, cantidad)
            cargo_total += cargo
            a_congelar.append((extra, precio, cantidad))
        return cargo_total, a_borrar, a_congelar, None

    def _resolver_codigo_promocional(self, request, reserva, subtotal, empresa):
        """Resuelve el codigo (si vino uno) contra el SUBTOTAL real, con extras
        ya incluidos. `empresa=empresa` explicito (N6): con
        `codigo` ya no unico global, dos Empresas con el mismo codigo sin este
        filtro lanzarian `MultipleObjectsReturned` -> 500 en el checkout, no
        un 400 manejado; se captura explicitamente y se traduce igual que
        "no existe". Mismo mensaje generico sin importar el motivo, para no
        darle pistas a quien prueba codigos al azar.

        Devuelve (promo_o_None, descuento, error_o_None)."""
        codigo_str = (request.data.get('codigo_promocional') or '').strip()
        if not codigo_str:
            return None, 0, None

        try:
            promo = CodigoPromocional.objects.get(codigo=codigo_str.upper(), empresa=empresa)
        except CodigoPromocional.DoesNotExist:
            return None, 0, 'El codigo promocional no es valido.'
        except CodigoPromocional.MultipleObjectsReturned:
            logger.error(
                'Mas de un CodigoPromocional "%s" en la Empresa %s', codigo_str, empresa.slug,
            )
            return None, 0, 'El codigo promocional no es valido.'

        if not codigo_promocional_valido(
            promo, reserva.correo_cliente, monto_viaje=subtotal, moneda=reserva.moneda,
        ):
            return None, 0, 'El codigo promocional no es valido.'

        return promo, cargo_por_descuento(subtotal, promo.porcentaje_descuento), None

    def _intent_de(self, cliente, reserva, monto):
        """Reusa el intent de la reserva si sigue sin cobrar; si no, crea uno,
        con el `cliente` de Stripe explicito de la Empresa (P1) — nunca
        `stripe.PaymentIntent.*` global. `idempotency_key` va en el segundo
        argumento (`options`), no en `params` (forma real de `stripe==15.4.0`,
        Revision 6 N-D): meterlo en `params` pierde la proteccion de doble
        clic/doble cobro."""
        centavos = a_centavos(monto)
        moneda = reserva.moneda.lower()

        if reserva.stripe_payment_intent_id:
            intent = cliente.payment_intents.retrieve(reserva.stripe_payment_intent_id)
            if intent.status in INTENT_YA_COBRANDO:
                raise PagoEnCurso
            if intent.status in INTENT_REUTILIZABLE:
                if intent.amount == centavos and intent.currency == moneda:
                    return intent
                # Cambio de amenidades o de moneda: se ajusta el mismo intent.
                # El metodo real del servicio es `update`, no `modify`.
                return cliente.payment_intents.update(
                    intent.id, {'amount': centavos, 'currency': moneda},
                )

        return cliente.payment_intents.create(
            {
                'amount': centavos,
                'currency': moneda,
                'metadata': {'reserva_id': reserva.id},
            },
            {'idempotency_key': f'reserva-{reserva.pk}-{moneda}-{centavos}'},
        )


class ValidarCodigoPromocionalView(APIView):
    """Validacion en vivo del codigo mientras el cliente lo escribe en el
    checkout — solo informativa, no liga a ninguna reserva. La autoritativa
    vuelve a correr en `CrearPagoView`.

    Respuesta siempre `{'valido': bool, 'porcentaje_descuento': str|None}` sin
    importar el motivo del rechazo, para no darle pistas a quien prueba
    codigos al azar.
    """

    throttle_scope = 'codigo_promocional'

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            codigo = request.query_params.get('codigo', '')
            correo_cliente = request.query_params.get('correo_cliente', '')
            promo = evaluar_codigo_promocional(codigo, correo_cliente, empresa)
            return Response({
                'valido': promo is not None,
                'porcentaje_descuento': str(promo.porcentaje_descuento) if promo else None,
            })


class EstadoReservaView(APIView):
    """Estado de la reserva de un checkout, para reponerlo tras un refresh o
    un cierre accidental de la pestana.

    El `checkout_id` es la unica llave (nace en el navegador, sobrevive en
    `sessionStorage`) y sirve como capacidad de acceso — no hace falta login.
    Es de solo lectura y no llama a Stripe.
    """

    throttle_scope = 'estado_reserva'

    ESTADOS_PAGADA = {Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA, Reserva.Estado.COMPLETADA}

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            return self._get(request, empresa)

    def _get(self, request, empresa):
        crudo = request.query_params.get('checkout_id')
        try:
            checkout_id = uuid.UUID(str(crudo))
        except (ValueError, TypeError):
            return Response({'detail': 'checkout_id invalido.'}, status=400)

        reserva = (
            Reserva.objects.filter(checkout_id=checkout_id, empresa=empresa)
            .order_by('-id').first()
        )
        if reserva is None:
            return Response(
                {'detail': 'No se encontro una reserva para este checkout.'}, status=404
            )

        if reserva.estado == Reserva.Estado.CANCELADA:
            return Response({'estado': 'cancelada'})

        if reserva.estado in self.ESTADOS_PAGADA:
            return Response({
                'estado': 'pagada',
                'reserva_id': reserva.id,
                'fecha': reserva.fecha,
                'hora': reserva.hora,
                'numero_personas': reserva.numero_personas,
                'nombre_cliente': reserva.nombre_cliente,
                'correo_cliente': reserva.correo_cliente,
                'moneda': reserva.moneda,
                'forma_pago': reserva.forma_pago,
                'monto_pagado': str(reserva.monto_pagado) if reserva.monto_pagado is not None else None,
                'precio_total': str(reserva.precio_total) if reserva.precio_total is not None else None,
                'extras': [
                    {
                        'nombre': extra.extras_item.nombre,
                        'cobrar_por_persona': extra.extras_item.cobrar_por_persona,
                        'monto': str(extra.subtotal) if extra.subtotal is not None else None,
                        'cantidad': extra.cantidad,
                    }
                    for extra in reserva.extras_seleccionados.select_related('extras_item').all()
                ],
                'codigo_promocional': (
                    reserva.codigo_promocional.codigo if reserva.codigo_promocional_id else None
                ),
                'descuento_aplicado': (
                    str(reserva.descuento_aplicado) if reserva.descuento_aplicado is not None else None
                ),
            })

        return Response({
            'estado': 'pendiente_pago',
            'reserva_id': reserva.id,
            'fecha': reserva.fecha,
            'hora': reserva.hora,
            'numero_personas': reserva.numero_personas,
            'nombre_cliente': reserva.nombre_cliente,
            'telefono_cliente': reserva.telefono_cliente,
            'correo_cliente': reserva.correo_cliente,
            'moneda': reserva.moneda,
            'forma_pago': reserva.forma_pago,
            'extras': [
                {'id': extra.extras_item_id, 'cantidad': extra.cantidad_solicitada}
                for extra in reserva.extras_seleccionados.all()
            ],
        })


class StripeWebhookView(APIView):
    """Confirma el pago y marca la reserva como pagada.

    Resuelve la Empresa con `resolver_empresa_de_dinero` (Revision 4, N16):
    a diferencia de las rutas de catalogo/checkout, procesa el evento aunque
    `empresa.activo` sea False — una Empresa pausada sigue necesitando
    reconciliar dinero ya cobrado.
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def post(self, request, empresa_slug):
        empresa = scope.resolver_empresa_de_dinero(empresa_slug)

        try:
            evento = stripe.Webhook.construct_event(
                request.body,
                request.headers.get('Stripe-Signature', ''),
                empresa.stripe_webhook_secret,
            )
        except (ValueError, stripe.SignatureVerificationError):
            return Response(status=400)

        objeto = evento['data']['object']

        # Cualquier error aqui devolveria 500 y Stripe reintentaria el evento en
        # bucle. Se registra y se responde 200: el reintento no arreglaria nada.
        try:
            with scope.con_empresa(empresa):
                if evento['type'] == 'payment_intent.succeeded':
                    aplicar_pago_exitoso(objeto, empresa)
                elif evento['type'] == 'charge.refunded':
                    aplicar_reembolso(objeto, empresa)
                elif evento['type'] == 'charge.dispute.created':
                    aplicar_disputa(objeto, True, empresa)
                elif evento['type'] in ('charge.dispute.closed', 'charge.dispute.funds_reinstated'):
                    aplicar_disputa(objeto, False, empresa)
        except Exception:
            logger.exception('Fallo procesando %s (%s)', evento['id'], evento['type'])

        return Response(status=200)
