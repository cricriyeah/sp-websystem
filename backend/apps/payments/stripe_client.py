"""Configuracion del cliente de Stripe, en un solo lugar.

Antes cada punto de entrada hacia `stripe.api_key = settings.STRIPE_SECRET_KEY`
por su cuenta — la vista de cobro, el reembolso y el comando de conciliacion —,
que es como se acaba con tres configuraciones que se van separando entre si.
"""
import stripe
from django.conf import settings


def configurar_stripe():
    """Deja el cliente listo para llamar a la API. Idempotente."""
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = settings.STRIPE_API_VERSION
