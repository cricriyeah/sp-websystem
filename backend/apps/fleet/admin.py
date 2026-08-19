from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Capitan, Embarcacion, EmbarcacionNoDisponible, Tarifa


@admin.register(Tarifa)
class TarifaAdmin(ModelAdmin):
    list_display = [
        'precio', 'precio_usd', 'precio_persona_extra', 'precio_persona_extra_usd',
        'actualizado_en', 'actualizado_por',
    ]
    readonly_fields = ['actualizado_en', 'actualizado_por']

    def has_add_permission(self, request):
        return not Tarifa.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.actualizado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Embarcacion)
class EmbarcacionAdmin(ModelAdmin):
    list_display = ['nombre', 'clase', 'capacidad_maxima', 'activa']
    list_filter = ['clase', 'activa']
    list_editable = ['activa']
    search_fields = ['nombre']


@admin.register(Capitan)
class CapitanAdmin(ModelAdmin):
    list_display = ['nombre', 'telefono']
    search_fields = ['nombre', 'telefono']


@admin.register(EmbarcacionNoDisponible)
class EmbarcacionNoDisponibleAdmin(ModelAdmin):
    """Aqui se marca que una panga no sale un dia. Mientras no exista la agenda
    operativa, este es el unico lugar para hacerlo."""

    list_display = ['fecha', 'embarcacion', 'motivo', 'registrado_por']
    list_filter = ['fecha', 'embarcacion']
    autocomplete_fields = ['embarcacion']
    readonly_fields = ['registrado_por', 'creado_en']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.registrado_por = request.user
        super().save_model(request, obj, form, change)
