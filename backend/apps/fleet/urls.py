from django.urls import path

from .views import TarifaView

urlpatterns = [
    path('tarifa/', TarifaView.as_view(), name='tarifa'),
]
