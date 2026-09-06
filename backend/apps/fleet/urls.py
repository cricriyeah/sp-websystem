from django.urls import path

from .views import (
    ExtrasPublicosView,
    PaquetesPorEmpresaListView,
    PaquetesPorSedeListView,
    ServicioDetailView,
    ServiciosListView,
    TarifaView,
)

urlpatterns = [
    path('sedes/<slug:sede_slug>/paquetes/', PaquetesPorSedeListView.as_view(), name='paquetes-por-sede'),
    path('<slug:empresa_slug>/paquetes/', PaquetesPorEmpresaListView.as_view(), name='paquetes-por-empresa'),
    path('<slug:empresa_slug>/tarifa/', TarifaView.as_view(), name='tarifa'),
    path('<slug:empresa_slug>/extras/', ExtrasPublicosView.as_view(), name='extras'),
    path('<slug:empresa_slug>/servicios/', ServiciosListView.as_view(), name='servicios-list'),
    path('<slug:empresa_slug>/servicios/<slug:slug>/', ServicioDetailView.as_view(), name='servicio-detail'),
]
