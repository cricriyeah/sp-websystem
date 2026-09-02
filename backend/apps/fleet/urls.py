from django.urls import path

from .views import ExtrasPublicosView, TarifaView

urlpatterns = [
    path('<slug:empresa_slug>/tarifa/', TarifaView.as_view(), name='tarifa'),
    path('<slug:empresa_slug>/extras/', ExtrasPublicosView.as_view(), name='extras'),
]
