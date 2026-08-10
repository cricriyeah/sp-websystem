from django.contrib import admin
from django.utils import timezone
from unfold.admin import ModelAdmin

from .models import CupoDiario, Reserva


@admin.register(CupoDiario)
class CupoDiarioAdmin(ModelAdmin):
    list_display = ['fecha', 'cupo_maximo']
    ordering = ['fecha']


@admin.register(Reserva)
class ReservaAdmin(ModelAdmin):
    list_display = [
        'fecha', 'hora', 'nombre_cliente', 'numero_personas',
        'estado', 'canal_origen', 'embarcacion', 'capitan', 'reembolsada',
    ]
    list_filter = ['estado', 'canal_origen', 'fecha', 'embarcacion', 'capitan', 'reembolsada']
    search_fields = ['nombre_cliente', 'telefono_cliente', 'correo_cliente']
    date_hierarchy = 'fecha'
    autocomplete_fields = ['embarcacion', 'capitan']
    readonly_fields = ['cancelada_por', 'cancelada_en', 'creado_en', 'actualizado_en']
    actions = ['cancelar_por_mal_clima']

    @admin.action(description='Cancelar por mal clima (reembolso completo)')
    def cancelar_por_mal_clima(self, request, queryset):
        actualizadas = 0
        for reserva in queryset.exclude(estado=Reserva.Estado.CANCELADA):
            reserva.estado = Reserva.Estado.CANCELADA
            reserva.motivo_cancelacion = reserva.motivo_cancelacion or 'Mal clima'
            reserva.cancelada_por = request.user
            reserva.cancelada_en = timezone.now()
            reserva.reembolsada = True
            reserva.full_clean()
            reserva.save()
            actualizadas += 1
        self.message_user(request, f'{actualizadas} reserva(s) cancelada(s) y marcada(s) para reembolso.')
