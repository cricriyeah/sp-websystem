from django.contrib import admin

from .models import Reserva


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = [
        'fecha', 'hora', 'nombre_cliente', 'numero_personas',
        'estado', 'canal_origen', 'embarcacion', 'capitan',
    ]
    list_filter = ['estado', 'canal_origen', 'fecha', 'embarcacion', 'capitan']
    search_fields = ['nombre_cliente', 'telefono_cliente', 'correo_cliente']
    date_hierarchy = 'fecha'
    autocomplete_fields = ['embarcacion', 'capitan']
