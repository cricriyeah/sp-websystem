from django.urls import path

from .views import CrearPagoView, StripeWebhookView

urlpatterns = [
    path('reservas/<int:pk>/crear-pago/', CrearPagoView.as_view(), name='crear-pago'),
    path('stripe/webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
]
