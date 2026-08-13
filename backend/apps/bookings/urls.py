from django.urls import path

from .views import CupoDisponibleView, ReservaCheckoutView

urlpatterns = [
    path('cupo/', CupoDisponibleView.as_view(), name='cupo'),
    path('reservas/', ReservaCheckoutView.as_view(), name='reserva-checkout'),
]
