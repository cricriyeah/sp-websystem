from django.urls import path

from .views import CupoDisponibleView, ReservaCreateView

urlpatterns = [
    path('cupo/', CupoDisponibleView.as_view(), name='cupo'),
    path('reservas/', ReservaCreateView.as_view(), name='reserva-create'),
]
