from decimal import Decimal, ROUND_HALF_UP

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Reserva
from apps.fleet.models import Tarifa

from .pricing import AMENITY_PRICE

ANTICIPO_PORCENTAJE = Decimal('0.30')


class CrearPagoView(APIView):
    """Crea el PaymentIntent de Stripe para una reserva pendiente_pago.
    El monto se calcula aqui (tarifa + amenidades + 100%/30% anticipo),
    nunca se confia el total enviado por el cliente. Cuenta estandar de
    Stripe, no Connect (ver docs/contexto-negocio.md)."""

    def post(self, request, pk):
        reserva = get_object_or_404(Reserva, pk=pk)
        if reserva.estado != Reserva.Estado.PENDIENTE_PAGO:
            return Response({'detail': 'Esta reserva ya no esta pendiente de pago.'}, status=409)

        tarifa = Tarifa.actual()
        if tarifa is None:
            return Response({'detail': 'Tarifa no configurada.'}, status=503)

        amenities = request.data.get('amenities', [])
        forma_pago = request.data.get('forma_pago', Reserva.FormaPago.COMPLETO)
        if forma_pago not in Reserva.FormaPago.values:
            return Response({'detail': 'forma_pago invalida.'}, status=400)

        amenities_total = sum(AMENITY_PRICE[a] for a in amenities if a in AMENITY_PRICE)
        precio_total = tarifa.precio + Decimal(amenities_total)
        monto_a_cobrar = (
            precio_total if forma_pago == Reserva.FormaPago.COMPLETO
            else (precio_total * ANTICIPO_PORCENTAJE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )

        if not settings.STRIPE_SECRET_KEY:
            return Response({'detail': 'Stripe no esta configurado todavia.'}, status=503)

        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.create(
            amount=int(monto_a_cobrar * 100),
            currency=reserva.moneda.lower(),
            metadata={'reserva_id': reserva.id},
        )

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


class StripeWebhookView(APIView):
    """Confirma el pago y marca la reserva como pagada. Aqui corre la
    validacion definitiva de cupo (ver Reserva.clean) — si el cupo se llenó
    entre el checkout y el pago, se reembolsa automaticamente."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.headers.get('Stripe-Signature', '')

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(status=400)

        if event['type'] == 'payment_intent.succeeded':
            intent = event['data']['object']
            reserva_id = intent['metadata']['reserva_id']
            reserva = Reserva.objects.filter(pk=reserva_id).first()

            if reserva and reserva.estado == Reserva.Estado.PENDIENTE_PAGO:
                reserva.monto_pagado = Decimal(intent['amount_received']) / 100
                reserva.estado = Reserva.Estado.PAGADA
                try:
                    reserva.full_clean()
                    reserva.save()
                except DjangoValidationError:
                    # Cupo se lleno mientras el cliente pagaba: reembolso completo,
                    # la reserva se queda pendiente_pago (no ocupa cupo).
                    stripe.api_key = settings.STRIPE_SECRET_KEY
                    stripe.Refund.create(payment_intent=intent['id'])

        return Response(status=200)
