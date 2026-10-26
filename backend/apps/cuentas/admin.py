"""Bitacora de la recuperacion de contrasena en el admin: solo lectura y solo para el operador de plataforma.

No se registra `CodigoRecuperacion`: es un hash de un solo uso y no hay nada que una persona deba ver ahi.
"""
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.tenancy import scope

from .models import EventoRecuperacion


@admin.register(EventoRecuperacion)
class EventoRecuperacionAdmin(ModelAdmin):
    list_display = ('creado_en', 'tipo', 'resultado', 'usuario', 'ip')
    list_filter = ('tipo', 'resultado')
    search_fields = ('usuario__username', 'ip')
    ordering = ('-creado_en',)
    list_per_page = 50

    def _es_operador(self, request):
        return scope.es_operador_plataforma(request.user)

    def has_module_permission(self, request):
        return self._es_operador(request)

    def has_view_permission(self, request, obj=None):
        return self._es_operador(request)

    # Una bitacora no se edita ni se limpia a mano (ni el superusuario): para eso esta
    # `manage.py limpiar_eventos_recuperacion`.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
