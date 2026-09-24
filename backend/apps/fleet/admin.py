from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from unfold.admin import ModelAdmin, TabularInline

from apps.tenancy import scope
from apps.tenancy.admin_mixins import EmpresaScopedAdminMixin

from .models import (
    Capitan,
    CodigoPromocional,
    Embarcacion,
    EmbarcacionNoDisponible,
    Paquete,
    PaqueteServicio,
    Personalizacion,
    PuntoEncuentro,
    Recurso,
    Servicio,
    ServicioPersonalizacion,
    TransporteTarifa,
    componente_de,
    errores_de_precio_contra_transporte,
)
from .paquete_reglas import errores_de_paquete


@admin.register(TransporteTarifa)
class TransporteTarifaAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'tipo_traslado', 'zona', 'personas_min', 'personas_max',
        'precio', 'precio_usd', 'activo',
    ]
    list_editable = ['precio', 'precio_usd', 'activo']


@admin.register(PuntoEncuentro)
class PuntoEncuentroAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'zona', 'activo']
    list_filter = ['zona', 'activo']
    list_editable = ['zona', 'activo']
    search_fields = ['nombre']


@admin.register(CodigoPromocional)
class CodigoPromocionalAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    """Sin permisos para Vendedora, mismo trato que Servicio/ServicioPersonalizacion: es
    informacion financiera. El uso de cada codigo no se audita aqui — se ve
    en la lista de Reservas (columna/filtro `codigo_promocional`), la misma
    fuente que ya cuenta contra `usos_maximos`."""

    list_display = [
        'codigo', 'porcentaje_descuento', 'activo', 'usos_maximos',
        'usos_maximos_por_cliente', 'fecha_inicio', 'fecha_fin',
    ]
    list_filter = ['activo']
    list_editable = ['porcentaje_descuento', 'activo']
    search_fields = ['codigo', 'descripcion']
    readonly_fields = ['creado_por', 'creado_en', 'actualizado_en']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Embarcacion)
class EmbarcacionAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'clase', 'capacidad_maxima', 'activa']
    list_filter = ['clase', 'activa']
    list_editable = ['activa']
    search_fields = ['nombre']


@admin.register(Capitan)
class CapitanAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'telefono']
    search_fields = ['nombre', 'telefono']


@admin.register(EmbarcacionNoDisponible)
class EmbarcacionNoDisponibleAdmin(EmpresaScopedAdminMixin, ModelAdmin):
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


class ServicioPersonalizacionInline(TabularInline):
    model = ServicioPersonalizacion
    extra = 1
    fields = ['personalizacion', 'precio', 'precio_usd', 'obligatorio', 'preseleccionado', 'activo']


@admin.register(Servicio)
class ServicioAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'nombre', 'tipo_servicio', 'estrategia_cupo', 'estrategia_precio',
        'modo_ocupacion', 'precio_base', 'precio_base_usd',
        'permite_anticipo', 'porcentaje_anticipo', 'activo',
    ]
    list_filter = ['tipo_servicio', 'estrategia_cupo', 'estrategia_precio', 'modo_ocupacion', 'permite_anticipo', 'activo']
    list_editable = ['precio_base', 'precio_base_usd', 'activo']
    search_fields = ['nombre', 'slug', 'descripcion']
    prepopulated_fields = {'slug': ('nombre',)}
    inlines = [ServicioPersonalizacionInline]


@admin.register(Recurso)
class RecursoAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'servicio', 'capacidad_maxima', 'activo']
    list_filter = ['servicio', 'activo']
    list_editable = ['capacidad_maxima', 'activo']
    search_fields = ['nombre']


@admin.register(Personalizacion)
class PersonalizacionAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'tipo', 'tipo_interaccion', 'cobrar_por_persona', 'cantidad_editable', 'aviso_reforzado', 'activo']
    list_filter = ['tipo', 'tipo_interaccion', 'cobrar_por_persona', 'cantidad_editable', 'aviso_reforzado', 'activo']
    list_editable = ['cobrar_por_persona', 'cantidad_editable', 'aviso_reforzado', 'activo']
    search_fields = ['nombre']


class PaqueteServicioFormSet(BaseInlineFormSet):
    """Valida el paquete completo con lo que el usuario acaba de escribir, no con la BD vieja."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        filas = [
            form.instance for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE')
        ]
        errores = errores_de_paquete(
            permite_anticipo=self.instance.permite_anticipo,
            componentes=[componente_de(ps) for ps in filas],
        )
        errores += list(errores_de_precio_contra_transporte(
            self.instance, [(ps.servicio, ps.personas_incluidas) for ps in filas],
        ).values())
        if errores:
            raise ValidationError(errores)


class PaqueteServicioInline(TabularInline):
    model = PaqueteServicio
    formset = PaqueteServicioFormSet
    extra = 1
    fields = ['servicio', 'orden', 'dia_estancia', 'noches', 'personas_incluidas']
    autocomplete_fields = ['servicio']


@admin.register(Paquete)
class PaqueteAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    empresa_campo = 'empresa_lider'
    list_display = ['nombre', 'sede', 'empresa_lider', 'precio_ancla', 'precio_ancla_usd', 'permite_anticipo', 'porcentaje_anticipo', 'activo']
    list_filter = ['sede', 'activo']
    list_editable = ['precio_ancla', 'precio_ancla_usd', 'activo']
    search_fields = ['nombre', 'slug', 'descripcion']
    prepopulated_fields = {'slug': ('nombre',)}
    inlines = [PaqueteServicioInline]

