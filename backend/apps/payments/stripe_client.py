"""Configuracion del cliente de Stripe, por Empresa.

Cada Empresa tiene sus propias llaves de Stripe (ver apps.tenancy.models.Empresa)
— con mas de una Empresa, mutar `stripe.api_key` como variable global de proceso
es una condicion de carrera esperando a que dos peticiones de Empresas distintas
se sirvan al mismo tiempo. `configurar_stripe(empresa)` devuelve un cliente
explicito en su lugar; cada call site lo recibe y lo usa, nunca importa `stripe`
para llamar directo a `stripe.PaymentIntent`/`stripe.Refund` con el estado global.
"""
import stripe
from django.conf import settings


def configurar_stripe(empresa):
    """Cliente de Stripe listo para llamar la API con las llaves de `empresa`."""
    return stripe.StripeClient(
        api_key=empresa.stripe_secret_key,
        stripe_version=settings.STRIPE_API_VERSION,
    )
