from django.urls import path

from .views import CupoDisponibleView, CupoRangoView, ReservaCheckoutView

urlpatterns = [
    path('cupo/', CupoDisponibleView.as_view(), name='cupo'),
    path('cupo/rango/', CupoRangoView.as_view(), name='cupo-rango'),
    path('reservas/', ReservaCheckoutView.as_view(), name='reserva-checkout'),
]
