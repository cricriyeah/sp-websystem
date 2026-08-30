import logging
import uuid

import stripe
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Reserva, codigo_promocional_valido, evaluar_codigo_promocional
from apps.fleet.models import CodigoPromocional, Tarifa, TransportePrecio

from .pricing import (
    a_centavos,
    cargo_por_descuento,
    cargo_por_extra,
    cargo_por_personas,
    cargo_por_transporte,
    monto_inicial,
    personas_extra,
)
from .stripe_client import configurar_stripe
from .services import aplicar_disputa, aplicar_pago_exitoso, aplicar_reembolso

logger = logging.getLogger(__name__)

# Estados en los que un PaymentIntent todavia no cobro nada y se puede reutilizar
# o ajustar. Cualquier otro (succeeded, processing, canceled) exige decision
# explicita — nunca se crea un intent nuevo encima de uno que ya esta cobrando.
INTENT_REUTILIZABLE = {'requires_payment_method', 'requires_confirmation', 'requires_action'}
INTENT_YA_COBRANDO = {'succeeded', 'processing'}


class PagoEnCurso(Exception):
    """El intent de la reserva ya esta cobrando o cobro: no se crea otro."""


class CrearPagoView(APIView):
    """Crea (o reutiliza) el PaymentIntent de Stripe de una reserva.

    El monto se calcula aqui — tarifa en la moneda de la reserva + amenidades +
    100%/30% — y nunca se confia el total que manda el cliente. Cuenta estandar
    de Stripe, no Connect (ver docs/contexto-negocio.md).

    Es idempotente a proposito: darle dos veces a "Ir a pagar", recargar el
    checkout o cambiar de amenidades reusa el mismo intent en vez de dejar
    intents sueltos que podrian terminar cobrando dos veces.
    """

    throttle_scope = 'pagos'

    def post(self, request, pk):
        reserva = get_object_or_404(Reserva, pk=pk)

        # Los ids de reserva son consecutivos y la API es publica: sin esto,
        # cualquiera podria adivinar un id y generar cobros sobre la reserva de
        # otra persona. El checkout_id lo genera el navegador del cliente y solo
        # lo conoce quien abrio ese checkout.
        #
        # Una reserva SIN checkout_id no nacio en el checkout web: la capturo la
        # vendedora (canal WhatsApp) y nadie tiene la llave para cobrarla por
        # aqui. Antes la condicion arrancaba con `reserva.checkout_id and`, asi
        # que para esas el guard entero se saltaba y bastaba adivinar el id para
        # sacarles el client_secret, pisarles el intent o cambiarles la
        # forma_pago a anticipo. Se cobran por otro lado (efectivo o un cobro que
        # arma la vendedora), no por esta ruta.
        if not reserva.checkout_id or str(reserva.checkout_id) != str(request.data.get('checkout_id')):
            return Response({'detail': 'checkout_id invalido para esta reserva.'}, status=403)

        if reserva.estado != Reserva.Estado.PENDIENTE_PAGO:
            return Response({'detail': 'Esta reserva ya no esta pendiente de pago.'}, status=409)

        tarifa = Tarifa.actual()
        if tarifa is None:
            return Response({'detail': 'Tarifa no configurada.'}, status=503)

        precio_tour = tarifa.precio_en(reserva.moneda)
        if precio_tour is None:
            return Response({'detail': f'No hay precio configurado en {reserva.moneda}.'}, status=503)

        # Las personas y los extras salen de la reserva, no del cuerpo de la
        # peticion: son los mismos datos que valida el cupo y que ve la vendedora.
        precio_persona_extra = tarifa.persona_extra_en(reserva.moneda)
        if personas_extra(reserva.numero_personas) and precio_persona_extra is None:
            return Response(
                {'detail': f'No hay cargo por persona extra configurado en {reserva.moneda}.'},
                status=503,
            )

        forma_pago = request.data.get('forma_pago', Reserva.FormaPago.COMPLETO)
        if forma_pago not in Reserva.FormaPago.values:
            return Response({'detail': 'forma_pago invalida.'}, status=400)

        # Extras/transporte se resuelven EN MEMORIA aqui, antes de cualquier
        # guard que pueda cortar con un return (PagoEnCurso -> 409, Stripe
        # caido -> 502): esta ruta hoy no escribe nada antes de asegurar el
        # intent, y un item recongelado/borrado a medias en un doble clic
        # (el segundo mientras el primero sigue `processing`) romperia esa
        # garantia. Solo se persiste todo junto, mas abajo, con el intent ya
        # en la mano.
        cargo_extras, extras_a_borrar, extras_a_congelar, error = self._resolver_extras(reserva)
        if error:
            return Response({'detail': error}, status=503)
        cargo_transporte, transporte_a_borrar, transporte_congelado, error = self._resolver_transporte(reserva)
        if error:
            return Response({'detail': error}, status=503)

        # Bebidas no suma: la cotiza el agente aparte.
        subtotal = (
            precio_tour
            + cargo_por_personas(precio_persona_extra or 0, reserva.numero_personas)
            + cargo_extras
            + cargo_transporte
        )

        # El codigo se resuelve sobre el SUBTOTAL ya completo (con extras y
        # transporte incluidos) — es el primer momento en que ese numero se
        # conoce exacto. La validacion en vivo del checkout no lo conoce
        # (ver evaluar_codigo_promocional) y por eso no revisa monto_minimo;
        # aqui si se revisa, con el total real.
        codigo_promocional, descuento, error = self._resolver_codigo_promocional(request, reserva, subtotal)
        if error:
            return Response({'detail': error}, status=400)

        precio_total = subtotal - descuento
        monto_a_cobrar = monto_inicial(precio_total, forma_pago)

        if not settings.STRIPE_SECRET_KEY:
            return Response({'detail': 'Stripe no esta configurado todavia.'}, status=503)

        configurar_stripe()
        try:
            intent = self._intent_de(reserva, monto_a_cobrar)
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

            if transporte_a_borrar is not None:
                transporte_a_borrar.delete()
            if transporte_congelado is not None:
                transporte, precio_calculado, personas_congeladas = transporte_congelado
                transporte.numero_personas = personas_congeladas
                transporte.precio_calculado = precio_calculado
                transporte.save(update_fields=['numero_personas', 'precio_calculado'])

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
            'publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
            'monto_a_cobrar': str(monto_a_cobrar),
            'moneda': reserva.moneda,
        })

    def _resolver_extras(self, reserva):
        """Recorre lo que el cliente selecciono en el checkout y decide, sin
        tocar la base: que se cae (item desactivado desde que se eligio) y que
        se congela con el precio VIGENTE del catalogo — nunca el que traia la
        reserva desde el checkout. Devuelve (cargo_total, a_borrar, a_congelar, error)."""
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
            # Cantidad editable (ej. licencia: alguien puede ya traer la suya
            # tramitada): se respeta lo que el cliente pidio, acotado al grupo
            # real por si `numero_personas` bajo despues de elegirla — nunca un
            # error, en el peor caso se cobra menos de lo pedido, jamas de mas.
            if item.cantidad_editable and extra.cantidad_solicitada is not None:
                cantidad = max(1, min(extra.cantidad_solicitada, reserva.numero_personas))
            cargo = cargo_por_extra(precio, item.cobrar_por_persona, cantidad)
            cargo_total += cargo
            a_congelar.append((extra, precio, cantidad))
        return cargo_total, a_borrar, a_congelar, None

    def _resolver_transporte(self, reserva):
        """Mismo criterio que `_resolver_extras`, para el traslado (a lo mas
        una fila por reserva). Devuelve (cargo, a_borrar_o_None, congelado_o_None, error)."""
        if not hasattr(reserva, 'transporte'):
            return 0, None, None, None

        transporte = reserva.transporte
        precio_zona = TransportePrecio.objects.filter(zona=transporte.zona, activo=True).first()
        if precio_zona is None:
            return 0, transporte, None, None

        precio_base = precio_zona.precio_en(reserva.moneda)
        recargo = precio_zona.recargo_en(reserva.moneda)
        if precio_base is None:
            return 0, None, None, f'No hay precio de transporte configurado en {reserva.moneda}.'

        # Cuantos suben a la camioneta, no cuantos son en total la reserva: el
        # recargo de grupo existe por espacio en el vehiculo, no por el tamano
        # de la reserva. Acotado al grupo real por si `numero_personas` cambio
        # despues de elegir el transporte.
        personas = reserva.numero_personas
        if transporte.personas_solicitadas is not None:
            personas = max(1, min(transporte.personas_solicitadas, reserva.numero_personas))

        cargo = cargo_por_transporte(
            precio_base, recargo, precio_zona.min_personas_recargo, personas
        )
        return cargo, None, (transporte, cargo, personas), None

    def _resolver_codigo_promocional(self, request, reserva, subtotal):
        """Resuelve el codigo (si vino uno) contra el SUBTOTAL real, con extras
        y transporte ya incluidos — el primer momento en que ese monto se
        conoce exacto (la validacion en vivo del checkout, `evaluar_codigo_promocional`,
        no lo conoce todavia). Mismo mensaje generico sin importar el motivo
        (no existe, vencido, agotado, no alcanza el minimo): mismo principio
        que `codigo_promocional_valido`, para no darle pistas a quien prueba
        codigos al azar sobre cual de esos motivos fue.

        Devuelve (promo_o_None, descuento, error_o_None). No entrar codigo no
        es un error: la mayoria de las reservas no lleva uno."""
        codigo_str = (request.data.get('codigo_promocional') or '').strip()
        if not codigo_str:
            return None, 0, None

        try:
            promo = CodigoPromocional.objects.get(codigo=codigo_str.upper())
        except CodigoPromocional.DoesNotExist:
            return None, 0, 'El codigo promocional no es valido.'

        if not codigo_promocional_valido(
            promo, reserva.correo_cliente, monto_viaje=subtotal, moneda=reserva.moneda,
        ):
            return None, 0, 'El codigo promocional no es valido.'

        return promo, cargo_por_descuento(subtotal, promo.porcentaje_descuento), None

    def _intent_de(self, reserva, monto):
        """Reusa el intent de la reserva si sigue sin cobrar; si no, crea uno.

        La `idempotency_key` cubre el caso del doble clic: dos peticiones iguales
        que llegan a la vez devuelven el mismo intent en vez de dos.
        """
        centavos = a_centavos(monto)
        moneda = reserva.moneda.lower()

        if reserva.stripe_payment_intent_id:
            intent = stripe.PaymentIntent.retrieve(reserva.stripe_payment_intent_id)
            if intent.status in INTENT_YA_COBRANDO:
                raise PagoEnCurso
            if intent.status in INTENT_REUTILIZABLE:
                if intent.amount == centavos and intent.currency == moneda:
                    return intent
                # Cambio de amenidades o de moneda: se ajusta el mismo intent.
                return stripe.PaymentIntent.modify(intent.id, amount=centavos, currency=moneda)

        return stripe.PaymentIntent.create(
            amount=centavos,
            currency=moneda,
            metadata={'reserva_id': reserva.id},
            idempotency_key=f'reserva-{reserva.pk}-{moneda}-{centavos}',
        )


class ValidarCodigoPromocionalView(APIView):
    """Validacion en vivo del codigo mientras el cliente lo escribe en el
    checkout — igual que `/api/cupo/`, es solo informativa y no liga a ninguna
    reserva. La autoritativa vuelve a correr en `CrearPagoView`, que si conoce
    el subtotal exacto (con extras y transporte) y es quien de verdad congela
    el descuento.

    Respuesta siempre `{'valido': bool, 'porcentaje_descuento': str|None}` sin
    importar el motivo del rechazo (no existe, vencido, agotado): mismo
    principio que `codigo_promocional_valido`, para no darle pistas a quien
    prueba codigos al azar.
    """

    throttle_scope = 'codigo_promocional'

    def get(self, request):
        codigo = request.query_params.get('codigo', '')
        correo_cliente = request.query_params.get('correo_cliente', '')
        promo = evaluar_codigo_promocional(codigo, correo_cliente)
        return Response({
            'valido': promo is not None,
            'porcentaje_descuento': str(promo.porcentaje_descuento) if promo else None,
        })


class EstadoReservaView(APIView):
    """Estado de la reserva de un checkout, para reponerlo tras un refresh o un
    cierre accidental de la pestana.

    El `checkout_id` es la unica llave: nace en el navegador
    (`crypto.randomUUID()`, ver frontend/src/components/checkout-view.tsx) y
    sobrevive en `sessionStorage`. Nadie mas lo conoce y no es adivinable (UUID4,
    122 bits al azar), asi que sirve como capacidad de acceso igual que ya lo usa
    `CrearPagoView` — no hace falta login para que esto siga siendo del cliente
    que abrio ese checkout.

    Es de solo lectura y no llama a Stripe: solo lee lo que ya quedo guardado en
    la `Reserva`. Retomar un pago sigue pasando por `crear-pago`, que ya sabe
    reusar el intent o devolver 409 si sigue cobrando — duplicar esa logica aqui
    solo agregaria una segunda fuente de verdad y una dependencia de red mas a
    una consulta que debe ser rapida y no debe poder tumbarse si Stripe esta
    lento.

    Cada rama del estado devuelve solo lo que esa pantalla necesita — no hay
    campo que sirva para las tres a la vez:
    - `cancelada`: nada mas. No hay pantalla que reconstruir.
    - `pendiente_pago`: lo que hace falta para reponer el formulario y, si el
      cliente decide continuar, volver a pedir el cobro. Sin `stripe_payment_intent_id`
      ni ningun dato de Stripe.
    - `pagada` (incluye asignada/completada, que son pagada + reparto interno):
      lo que pide `BookingConfirmation`. Sin telefono ni ningun dato que esa
      pantalla no muestre — no se manda de vuelta mas de lo que ya se le iba a
      ensenar al propio cliente.
    """

    throttle_scope = 'estado_reserva'

    # pagada/asignada/completada son la misma cosa para el cliente que reconecta:
    # ya le cobraron. Que panga y capitan le toquen es reparto interno, no algo
    # que el checkout necesite distinguir.
    ESTADOS_PAGADA = {Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA, Reserva.Estado.COMPLETADA}

    def get(self, request):
        crudo = request.query_params.get('checkout_id')
        try:
            checkout_id = uuid.UUID(str(crudo))
        except (ValueError, TypeError):
            return Response({'detail': 'checkout_id invalido.'}, status=400)

        # Un checkout_id no es unico en la tabla a proposito (ver
        # bookings.Reserva.checkout_id): el mismo navegador puede dejar mas de
        # una fila con el mismo identificador si el cliente reserva dos viajes
        # en la misma pestana. La ultima es siempre la que le corresponde a la
        # sesion de checkout que esta corriendo ahora.
        reserva = Reserva.objects.filter(checkout_id=checkout_id).order_by('-id').first()
        if reserva is None:
            return Response(
                {'detail': 'No se encontro una reserva para este checkout.'}, status=404
            )

        if reserva.estado == Reserva.Estado.CANCELADA:
            return Response({'estado': 'cancelada'})

        if reserva.estado in self.ESTADOS_PAGADA:
            transporte = getattr(reserva, 'transporte', None)
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
                # str() a proposito: el encoder de DRF convierte un Decimal a
                # float (4500.0), no a texto, y eso pierde precision de centavos
                # justo en un monto de dinero (mismo motivo que `crear-pago`
                # con `monto_a_cobrar`).
                'monto_pagado': str(reserva.monto_pagado) if reserva.monto_pagado is not None else None,
                'precio_total': str(reserva.precio_total) if reserva.precio_total is not None else None,
                # Desglose ya congelado al pagar (`ReservaExtra`/`ReservaTransporte`,
                # ver `CrearPagoView`): el precio que de verdad se cobro, no el
                # vigente del catalogo hoy. Sin esto la confirmacion de un
                # checkout recuperado solo podia enseñar el total.
                'extras': [
                    {
                        'nombre': extra.extras_item.nombre,
                        'cobrar_por_persona': extra.extras_item.cobrar_por_persona,
                        'monto': str(extra.subtotal) if extra.subtotal is not None else None,
                        # Cantidad ya congelada (ver CrearPagoView): con
                        # `cantidad_editable` puede ser menor que `numero_personas`
                        # de la reserva, y el ticket necesita saberlo para no
                        # mostrar "(N de M)" con el M equivocado.
                        'cantidad': extra.cantidad,
                    }
                    for extra in reserva.extras_seleccionados.select_related('extras_item').all()
                ],
                'transporte': (
                    {'monto': str(transporte.precio_calculado), 'numero_personas': transporte.numero_personas}
                    if transporte is not None and transporte.precio_calculado is not None
                    else None
                ),
                # Igual que extras/transporte: el descuento ya congelado en
                # `CrearPagoView`, no el porcentaje vigente del codigo hoy.
                'codigo_promocional': (
                    reserva.codigo_promocional.codigo if reserva.codigo_promocional_id else None
                ),
                'descuento_aplicado': (
                    str(reserva.descuento_aplicado) if reserva.descuento_aplicado is not None else None
                ),
            })

        # Solo queda pendiente_pago: es el unico otro valor de Estado.
        # La seleccion de extras/transporte se devuelve por id — no hay precio
        # que reponer todavia, eso solo existe desde que se paga.
        transporte = getattr(reserva, 'transporte', None)
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
            'transporte': {
                'punto_encuentro': transporte.punto_encuentro_id,
                'direccion_personalizada': transporte.direccion_personalizada,
                'zona': transporte.zona,
                'cantidad': transporte.personas_solicitadas,
            } if transporte else None,
        })


class StripeWebhookView(APIView):
    """Confirma el pago y marca la reserva como pagada.

    Es la unica fuente de verdad del cobro: el navegador puede cerrarse a media
    confirmacion, asi que nada se marca pagado desde el frontend. Aqui corre la
    validacion definitiva de cupo y aqui se detecta y devuelve cualquier cobro
    duplicado.
    """

    authentication_classes = []
    permission_classes = []
    # Sin limite de peticiones, explicito para que nadie se lo ponga despues por
    # simetria con las otras vistas: Stripe reintenta en rafagas cuando algo
    # falla y un 429 aqui es un cobro que se queda sin reserva. Lo que autentica
    # esta ruta es la firma del evento, no el volumen.
    throttle_classes = []

    def post(self, request):
        try:
            evento = stripe.Webhook.construct_event(
                request.body,
                request.headers.get('Stripe-Signature', ''),
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.SignatureVerificationError):
            return Response(status=400)

        objeto = evento['data']['object']

        # Cualquier error aqui devolveria 500 y Stripe reintentaria el evento en
        # bucle. Se registra y se responde 200: el reintento no arreglaria nada y
        # el dinero ya se movio.
        try:
            if evento['type'] == 'payment_intent.succeeded':
                aplicar_pago_exitoso(objeto)
            elif evento['type'] == 'charge.refunded':
                # Cubre los reembolsos hechos a mano desde el panel de Stripe.
                aplicar_reembolso(objeto)
            elif evento['type'] == 'charge.dispute.created':
                # El objeto es un Dispute, no un Charge, pero tambien trae
                # `payment_intent`, que es lo unico que hace falta.
                aplicar_disputa(objeto, True)
            elif evento['type'] in ('charge.dispute.closed', 'charge.dispute.funds_reinstated'):
                aplicar_disputa(objeto, False)
        except Exception:
            logger.exception('Fallo procesando %s (%s)', evento['id'], evento['type'])

        return Response(status=200)
