from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from apps.tenancy import scope
from apps.tenancy.admin_mixins import EmpresaScopedAdminMixin

from .models import (
    Capitan,
    CodigoPromocional,
    Embarcacion,
    EmbarcacionNoDisponible,
    ExtrasItem,
    Paquete,
    PaqueteServicio,
    Personalizacion,
    PuntoEncuentro,
    Recurso,
    Servicio,
    ServicioPersonalizacion,
    Tarifa,
)


@admin.register(Tarifa)
class TarifaAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'precio', 'precio_usd', 'precio_persona_extra', 'precio_persona_extra_usd',
        'actualizado_en', 'actualizado_por',
    ]
    readonly_fields = ['actualizado_en', 'actualizado_por']

    def has_add_permission(self, request):
        empresa = scope.empresa_actual(request)
        if empresa is None:
            # Operador de plataforma: sin empresa_actual, no hay singleton que
            # guardar — el formulario exige elegir Empresa explicitamente
            # (ver EmpresaScopedAdminMixin.get_fields).
            return True
        return not Tarifa.objects.filter(empresa=empresa).exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.actualizado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(ExtrasItem)
class ExtrasItemAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    """Precios editables sin deploy. Sin permisos para Vendedora, mismo trato
    que Tarifa: es informacion financiera."""

    list_display = [
        'nombre', 'tipo', 'precio', 'precio_usd', 'cobrar_por_persona',
        'cantidad_editable', 'preseleccionado', 'activo',
    ]
    list_filter = ['tipo', 'activo']
    list_editable = ['precio', 'precio_usd', 'cantidad_editable', 'activo']
    search_fields = ['nombre']


@admin.register(PuntoEncuentro)
class PuntoEncuentroAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'zona', 'activo']
    list_filter = ['zona', 'activo']
    list_editable = ['zona', 'activo']
    search_fields = ['nombre']


@admin.register(CodigoPromocional)
class CodigoPromocionalAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    """Sin permisos para Vendedora, mismo trato que Tarifa/ExtrasItem: es
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
        'modo_ocupacion', 'precio_base', 'precio_base_usd', 'activo',
    ]
    list_filter = ['tipo_servicio', 'estrategia_cupo', 'estrategia_precio', 'modo_ocupacion', 'activo']
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
    list_display = ['nombre', 'tipo', 'cobrar_por_persona', 'cantidad_editable', 'activo']
    list_filter = ['tipo', 'cobrar_por_persona', 'cantidad_editable', 'activo']
    list_editable = ['cobrar_por_persona', 'cantidad_editable', 'activo']
    search_fields = ['nombre']


class PaqueteServicioInline(TabularInline):
    model = PaqueteServicio
    extra = 1
    fields = ['servicio', 'orden']
    autocomplete_fields = ['servicio']


@admin.register(Paquete)
class PaqueteAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    empresa_campo = 'empresa_lider'
    list_display = ['nombre', 'sede', 'empresa_lider', 'precio_ancla', 'precio_ancla_usd', 'activo']
    list_filter = ['sede', 'activo']
    list_editable = ['precio_ancla', 'precio_ancla_usd', 'activo']
    search_fields = ['nombre', 'slug', 'descripcion']
    prepopulated_fields = {'slug': ('nombre',)}
    inlines = [PaqueteServicioInline]

