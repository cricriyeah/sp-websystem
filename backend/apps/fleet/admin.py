from decimal import Decimal

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone
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
    Vehiculo,
    VehiculoNoDisponible,
    componente_de,
    errores_de_precio_contra_transporte,
)
from .paquete_reglas import errores_de_paquete


@admin.register(TransporteTarifa)
class TransporteTarifaAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'tipo_traslado', 'zona', 'personas_min', 'personas_max',
        'precio', 'activo',
    ]
    list_editable = ['precio', 'activo']


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
    list_display = ['nombre', 'clase', 'capacidad_maxima', 'activa', 'fuera_hoy']
    list_filter = ['clase', 'activa']
    list_editable = ['activa']
    search_fields = ['nombre']

    @admin.display(description='Fuera hoy')
    def fuera_hoy(self, obj):
        """`activa` es la flota permanente; una baja de un dia vive en
        `EmbarcacionNoDisponible`. Sin esta columna una panga dada de baja hoy
        seguia viendose como activa y parecia que la baja no habia pasado."""
        baja = obj.no_disponibles.filter(fecha=timezone.localdate()).first()
        if baja is None:
            return '—'
        return f'Fuera hoy: {baja.motivo}' if baja.motivo else 'Fuera hoy'


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


@admin.register(Vehiculo)
class VehiculoAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'lugares', 'activo']
    list_filter = ['activo']
    list_editable = ['activo']
    search_fields = ['nombre']


@admin.register(VehiculoNoDisponible)
class VehiculoNoDisponibleAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    """Bloqueos de vehiculos para traslados (dia completo o rango de horas)."""

    campos_escopeados_por_empresa = ('vehiculo',)
    list_display = ['fecha', 'vehiculo', 'hora_desde', 'hora_hasta', 'motivo', 'registrado_por']
    list_filter = ['fecha', 'vehiculo']
    autocomplete_fields = ['vehiculo']
    readonly_fields = ['registrado_por', 'creado_en']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.registrado_por = request.user
        super().save_model(request, obj, form, change)


class ServicioPersonalizacionInline(TabularInline):
    model = ServicioPersonalizacion
    extra = 1
    fields = ['personalizacion', 'precio', 'obligatorio', 'preseleccionado', 'activo']


AYUDA_CAMPOS_SERVICIO = {
    'tipo_servicio': 'Tipo de actividad: define cómo opera el servicio (pesca, paseo, hospedaje, bajo demanda o transporte).',
    'estrategia_cupo': 'Control de cupo: por recurso por día (embarcaciones), por noche (hospedaje) o bajo demanda sin tope previo.',
    'modo_ocupacion': 'Exclusivo reserva el recurso completo para un solo grupo; compartido permite combinar varios grupos.',
    'estrategia_precio': 'Cálculo de tarifa: por grupo (base más personas extra), por persona, tarifa fija, por noche o por ruta.',
    'capacidad_maxima': 'Número máximo de personas por reserva. Si se deja vacío, el sistema aplica el tope predeterminado (5).',
    'hora_apertura': 'Hora más temprana permitida para iniciar la salida. Obligatoria si el servicio pide hora.',
    'hora_cierre': 'Hora límite para iniciar la salida. Debe ser igual o posterior a la hora de apertura.',
    'paso_hora_minutos': 'Intervalo en minutos entre cada opción de horario que verá el cliente (ej. 15, 30 o 60 min).',
    'solo_en_paquete': 'Si se activa, el servicio no se vende por separado ni aparece en el catálogo web; solo dentro de paquetes.',
}


class ServicioAdminForm(forms.ModelForm):
    class Meta:
        model = Servicio
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ('paso_hora_minutos', 'porcentaje_anticipo', 'precio_persona_extra', 'personas_incluidas'):
            if campo in self.fields:
                self.fields[campo].required = False
        for campo, ayuda in AYUDA_CAMPOS_SERVICIO.items():
            if campo in self.fields:
                self.fields[campo].help_text = ayuda

    def clean_paso_hora_minutos(self):
        valor = self.cleaned_data.get('paso_hora_minutos')
        return valor if valor is not None else 15

    def clean_porcentaje_anticipo(self):
        valor = self.cleaned_data.get('porcentaje_anticipo')
        return valor if valor is not None else 30

    def clean_precio_persona_extra(self):
        valor = self.cleaned_data.get('precio_persona_extra')
        return valor if valor is not None else Decimal('0.00')

    def clean_personas_incluidas(self):
        valor = self.cleaned_data.get('personas_incluidas')
        return valor if valor is not None else 3


@admin.register(Servicio)
class ServicioAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    form = ServicioAdminForm
    list_display = [
        'nombre', 'tipo_servicio', 'estrategia_cupo', 'estrategia_precio',
        'modo_ocupacion', 'precio_base',
        'permite_anticipo', 'porcentaje_anticipo', 'activo',
    ]
    list_filter = ['tipo_servicio', 'estrategia_cupo', 'estrategia_precio', 'modo_ocupacion', 'permite_anticipo', 'activo']
    list_editable = ['precio_base', 'activo']
    search_fields = ['nombre', 'slug', 'descripcion']
    prepopulated_fields = {'slug': ('nombre',)}
    readonly_fields = ['creado_en', 'actualizado_en']
    inlines = [ServicioPersonalizacionInline]

    fieldsets = [
        ('Qué es', {
            'description': 'Identificación básica del servicio y su disponibilidad general.',
            'fields': ('nombre', 'slug', 'tipo_servicio', 'descripcion', 'activo'),
        }),
        ('Cupo', {
            'description': 'Control de inventario, modo de asignación y capacidad de pasajeros.',
            'fields': ('estrategia_cupo', 'modo_ocupacion', 'capacidad_maxima'),
        }),
        ('Precio', {
            'description': 'Esquema de cobro y tarifas base en pesos (MXN).',
            'fields': ('estrategia_precio', 'precio_base', 'precio_persona_extra', 'personas_incluidas'),
        }),
        ('Horario', {
            'description': 'Ventana de salida y selección de horario por el cliente.',
            'fields': ('pide_hora', 'paso_hora_minutos', 'hora_apertura', 'hora_cierre'),
        }),
        ('Anticipo y visibilidad', {
            'description': 'Cobro fraccionado en línea y exclusividad de venta en paquetes.',
            'fields': ('permite_anticipo', 'porcentaje_anticipo', 'solo_en_paquete'),
        }),
        ('Registro', {
            'classes': ('collapse',),
            'description': 'Marcas de tiempo de auditoría del sistema.',
            'fields': ('creado_en', 'actualizado_en'),
        }),
    ]

    conditional_fields = {
        # El interruptor «pide hora» siempre se ve y es el que decide si se muestran las horas: ocultarlas
        # por el tipo de servicio obligaria a cambiar datos en silencio (el modelo exige el rango si pide hora).
        'paso_hora_minutos': 'pide_hora == true',
        'hora_apertura': 'pide_hora == true',
        'hora_cierre': 'pide_hora == true',
        'porcentaje_anticipo': 'permite_anticipo == true',
        'precio_persona_extra': "estrategia_precio == 'por_grupo'",
        'personas_incluidas': "estrategia_precio == 'por_grupo'",
    }

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj is None and scope.es_operador_plataforma(request.user):
            primer_titulo, primer_opts = fieldsets[0]
            fields = primer_opts.get('fields', ())
            if 'empresa' not in fields:
                fieldsets = [
                    (primer_titulo, {**primer_opts, 'fields': ('empresa',) + tuple(fields)}),
                    *fieldsets[1:],
                ]
        return fieldsets

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in (
            'paso_hora_minutos', 'porcentaje_anticipo',
            'precio_persona_extra', 'personas_incluidas',
        ):
            kwargs['required'] = False
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield and db_field.name in AYUDA_CAMPOS_SERVICIO:
            formfield.help_text = AYUDA_CAMPOS_SERVICIO[db_field.name]
        return formfield


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
    fields = ['servicio', 'orden', 'dia_estancia', 'salidas', 'noches', 'personas_incluidas']
    autocomplete_fields = ['servicio']


@admin.register(Paquete)
class PaqueteAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    empresa_campo = 'empresa_lider'
    list_display = [
        'nombre', 'sede', 'empresa_lider', 'precio_ancla', 'estrategia_precio',
        'personas_precio_base', 'precio_persona_extra', 'pide_hora',
        'permite_anticipo', 'porcentaje_anticipo', 'activo',
    ]
    list_filter = ['sede', 'activo']
    list_editable = ['precio_ancla', 'activo']
    search_fields = ['nombre', 'slug', 'descripcion']
    prepopulated_fields = {'slug': ('nombre',)}
    inlines = [PaqueteServicioInline]
