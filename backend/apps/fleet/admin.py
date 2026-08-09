from django.contrib import admin

from .models import Capitan, Embarcacion


@admin.register(Embarcacion)
class EmbarcacionAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'clase', 'capacidad_maxima']
    list_filter = ['clase']
    search_fields = ['nombre']


@admin.register(Capitan)
class CapitanAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'telefono']
    search_fields = ['nombre', 'telefono']
