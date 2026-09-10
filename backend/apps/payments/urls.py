from django.urls import path

from .views import (
    CrearOrdenView,
    CrearPagoView,
    EstadoReservaView,
    StripeWebhookView,
    ValidarCodigoPromocionalView,
)

urlpatterns = [
    path(
        '<slug:sede_slug>/ordenes/', CrearOrdenView.as_view(),
        name='crear-orden',
    ),
    path(
        '<slug:empresa_slug>/reservas/<int:pk>/crear-pago/', CrearPagoView.as_view(),
        name='crear-pago',
    ),
    path(
        '<slug:empresa_slug>/reservas/estado/', EstadoReservaView.as_view(),
        name='reserva-estado',
    ),
    path(
        '<slug:empresa_slug>/codigo-promocional/validar/', ValidarCodigoPromocionalView.as_view(),
        name='codigo-promocional-validar',
    ),
    path(
        '<slug:empresa_slug>/stripe/webhook/', StripeWebhookView.as_view(),
        name='stripe-webhook',
    ),
]
