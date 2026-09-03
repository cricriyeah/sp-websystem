from django.urls import path

from .views import CupoDisponibleView, CupoRangoView, ReservaCheckoutView

urlpatterns = [
    path('<slug:empresa_slug>/cupo/', CupoDisponibleView.as_view(), name='cupo'),
    path('<slug:empresa_slug>/cupo/rango/', CupoRangoView.as_view(), name='cupo-rango'),
    path('<slug:empresa_slug>/reservas/', ReservaCheckoutView.as_view(), name='reserva-checkout'),
]
