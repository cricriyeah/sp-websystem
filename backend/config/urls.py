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

from apps.finance.views import panel_financiero

admin.site.site_header = 'Sal y Sol Sportfishing — Backoffice'
admin.site.site_title = 'Sal y Sol Sportfishing'
admin.site.index_title = 'Panel de administracion'

urlpatterns = [
    # Va antes de `admin/`: esa linea se traga todo lo que cuelgue de ahi.
    # `admin_view` le pone el login del admin encima; que solo entren jefes lo
    # decide la vista (ver apps/finance/views.py).
    path('admin/finanzas/', admin.site.admin_view(panel_financiero), name='finanzas'),
    path('admin/', admin.site.urls),
    path('api/', include('apps.fleet.urls')),
    path('api/', include('apps.bookings.urls')),
    path('api/', include('apps.payments.urls')),
]
