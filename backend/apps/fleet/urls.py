from django.urls import path

from .views import ExtrasPublicosView, TarifaView

urlpatterns = [
    path('tarifa/', TarifaView.as_view(), name='tarifa'),
    path('extras/', ExtrasPublicosView.as_view(), name='extras'),
]
