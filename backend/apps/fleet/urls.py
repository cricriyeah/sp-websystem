from django.urls import path

from .views import (
    ExtrasPublicosView,
    PaqueteDetailView,
    PaquetesPorEmpresaListView,
    PaquetesPorSedeListView,
    SedesListView,
    ServicioDetailView,
    ServiciosListView,
    ServiciosPorSedeListView,
    TarifaView,
)

urlpatterns = [
    path('sedes/', SedesListView.as_view(), name='sedes-list'),
    path('sedes/<slug:sede_slug>/paquetes/', PaquetesPorSedeListView.as_view(), name='paquetes-por-sede'),
    path('sedes/<slug:sede_slug>/paquetes/<slug:slug>/', PaqueteDetailView.as_view(), name='paquete-detail'),
    path('sedes/<slug:sede_slug>/servicios/', ServiciosPorSedeListView.as_view(), name='servicios-por-sede'),
    path('<slug:empresa_slug>/paquetes/', PaquetesPorEmpresaListView.as_view(), name='paquetes-por-empresa'),
    path('<slug:empresa_slug>/tarifa/', TarifaView.as_view(), name='tarifa'),
    path('<slug:empresa_slug>/extras/', ExtrasPublicosView.as_view(), name='extras'),
    path('<slug:empresa_slug>/servicios/', ServiciosListView.as_view(), name='servicios-list'),
    path('<slug:empresa_slug>/servicios/<slug:slug>/', ServicioDetailView.as_view(), name='servicio-detail'),
]
