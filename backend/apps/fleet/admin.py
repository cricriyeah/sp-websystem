from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Capitan, Embarcacion, Tarifa


@admin.register(Tarifa)
class TarifaAdmin(ModelAdmin):
    list_display = ['precio', 'actualizado_en', 'actualizado_por']
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
    list_display = ['nombre', 'clase', 'capacidad_maxima']
    list_filter = ['clase']
    search_fields = ['nombre']


@admin.register(Capitan)
class CapitanAdmin(ModelAdmin):
    list_display = ['nombre', 'telefono']
    search_fields = ['nombre', 'telefono']
