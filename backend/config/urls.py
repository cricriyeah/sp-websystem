"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from apps.bookings.vistas_calendario import calendario
from apps.finance.views import movimientos_financieros, panel_financiero
from apps.fleet.views import TrasladosView
from apps.tenancy.inicio import vista_avanzada, vista_saldos

from .health import healthz

admin.site.site_header = 'Sun Baja Experiences'
admin.site.site_title = 'Sun Baja Experiences'
admin.site.index_title = 'Panel de administracion'

urlpatterns = [
    # Sonda del balanceador de Render (ver config/health.py). Deliberadamente
    # fuera de `api/`: no es parte de la API publica y no debe llevar prefijo que
    # invite a versionarla.
    path('healthz', healthz, name='healthz'),

    # Va antes de `admin/`: esa linea se traga todo lo que cuelgue de ahi.
    # `admin_view` le pone el login del admin encima; que solo entren jefes lo
    # decide la vista (ver apps/finance/views.py).
    path('admin/finanzas/movimientos/', admin.site.admin_view(movimientos_financieros), name='finanzas_movimientos'),
    path('admin/finanzas/', admin.site.admin_view(panel_financiero), name='finanzas'),
    # Calendario de solo lectura: `admin_view` pone el login; el permiso (ver reservas) lo decide la vista.
    path('admin/calendario/', admin.site.admin_view(calendario), name='calendario'),
    path('admin/avanzado/',admin.site.admin_view(vista_avanzada), name='admin_avanzado'),
    path('admin/saldos-por-cobrar/', admin.site.admin_view(vista_saldos), name='saldos_por_cobrar'),
    path('admin/', admin.site.urls),
    path('api/<slug:empresa_slug>/traslados/', TrasladosView.as_view(), name='traslados'),
    path('api/', include('apps.fleet.urls')),
    path('api/', include('apps.bookings.urls')),
    path('api/', include('apps.payments.urls')),
]

handler403 = 'config.errores.error_403'
handler404 = 'config.errores.error_404'
handler500 = 'config.errores.error_500'
