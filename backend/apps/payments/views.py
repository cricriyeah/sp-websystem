import logging

import stripe
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Reserva
from apps.fleet.models import Tarifa

from .pricing import a_centavos, cargo_por_lunch, cargo_por_personas, monto_inicial, personas_extra
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
        if reserva.checkout_id and str(reserva.checkout_id) != str(request.data.get('checkout_id')):
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

        precio_lunch = tarifa.lunch_en(reserva.moneda)
        if reserva.lleva_lunch and precio_lunch is None:
            return Response(
                {'detail': f'No hay precio de lunch configurado en {reserva.moneda}.'}, status=503
            )

        forma_pago = request.data.get('forma_pago', Reserva.FormaPago.COMPLETO)
        if forma_pago not in Reserva.FormaPago.values:
            return Response({'detail': 'forma_pago invalida.'}, status=400)

        # Bebidas y transporte no suman: los cotiza el agente aparte.
        precio_total = (
            precio_tour
            + cargo_por_personas(precio_persona_extra or 0, reserva.numero_personas)
            + (cargo_por_lunch(precio_lunch, reserva.numero_personas) if reserva.lleva_lunch else 0)
        )
        monto_a_cobrar = monto_inicial(precio_total, forma_pago)

        if not settings.STRIPE_SECRET_KEY:
            return Response({'detail': 'Stripe no esta configurado todavia.'}, status=503)

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            intent = self._intent_de(reserva, monto_a_cobrar)
        except PagoEnCurso:
            return Response(
                {'detail': 'Ya hay un cobro en curso para esta reserva.'}, status=409
            )
        except stripe.StripeError:
            logger.exception('Stripe fallo al preparar el pago de la reserva %s', reserva.pk)
            return Response({'detail': 'No se pudo iniciar el pago. Intenta de nuevo.'}, status=502)

        reserva.precio_total = precio_total
        reserva.forma_pago = forma_pago
        reserva.stripe_payment_intent_id = intent.id
        reserva.save(update_fields=['precio_total', 'forma_pago', 'stripe_payment_intent_id'])

        return Response({
            'client_secret': intent.client_secret,
            'publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
            'monto_a_cobrar': str(monto_a_cobrar),
            'moneda': reserva.moneda,
        })

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
