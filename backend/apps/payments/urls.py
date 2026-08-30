from django.urls import path

from .views import CrearPagoView, EstadoReservaView, StripeWebhookView, ValidarCodigoPromocionalView

urlpatterns = [
    path('reservas/<int:pk>/crear-pago/', CrearPagoView.as_view(), name='crear-pago'),
    path('reservas/estado/', EstadoReservaView.as_view(), name='reserva-estado'),
    path(
        'codigo-promocional/validar/', ValidarCodigoPromocionalView.as_view(),
        name='codigo-promocional-validar',
    ),
    path('stripe/webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
]
