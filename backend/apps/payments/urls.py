from django.urls import path

from .views import (
    CancelarOrdenPublicaView,
    ConfirmarCapturaOrdenView,
    CrearOrdenView,
    CrearPagoOrdenView,
    CrearPagoView,
    EstadoReservaView,
    GetOrdenView,
    ResumenOrdenView,
    ResumenReservaView,
    StripeWebhookView,
    ValidarCodigoPromocionalView,
)

urlpatterns = [
    path(
        '<slug:sede_slug>/ordenes/resumen/', ResumenOrdenView.as_view(),
        name='orden-resumen',
    ),
    path(
        '<slug:sede_slug>/ordenes/', CrearOrdenView.as_view(),
        name='crear-orden',
    ),
    path(
        '<slug:sede_slug>/ordenes/<int:pk>/', GetOrdenView.as_view(),
        name='orden-detalle',
    ),
    path(
        '<slug:sede_slug>/ordenes/<int:pk>/cancelar/', CancelarOrdenPublicaView.as_view(),
        name='cancelar-orden-publica',
    ),
    path(
        '<slug:sede_slug>/ordenes/<int:pk>/crear-pago/', CrearPagoOrdenView.as_view(),
        name='crear-pago-orden',
    ),
    path(
        '<slug:sede_slug>/ordenes/<int:pk>/confirmar-captura/', ConfirmarCapturaOrdenView.as_view(),
        name='confirmar-captura-orden',
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
        '<slug:empresa_slug>/reservas/resumen/', ResumenReservaView.as_view(),
        name='reserva-resumen',
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
