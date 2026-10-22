from decimal import Decimal

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.forms import BaseInlineFormSet
from unfold.admin import ModelAdmin, TabularInline

from apps.tenancy import scope
from apps.tenancy.acciones_fila import AccionesDeFilaMixin
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
from .incluye import INCLUYE_MAX_CARACTERES, INCLUYE_MAX_RENGLONES, lineas_de_texto
from .paquete_reglas import errores_de_paquete
from .tarifa_transporte import peor_tarifa


@admin.register(TransporteTarifa)
class TransporteTarifaAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    list_display = [
        'tipo_traslado', 'zona', 'personas_min', 'personas_max',
        'precio', 'activo',
    ]
    list_editable = ['precio', 'activo']


@admin.register(PuntoEncuentro)
class PuntoEncuentroAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    list_display = ['nombre', 'zona', 'activo']
    list_filter = ['zona', 'activo']
    list_editable = ['zona', 'activo']
    search_fields = ['nombre']


@admin.register(CodigoPromocional)
class CodigoPromocionalAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
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
class EmbarcacionAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
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
class CapitanAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    list_display = ['nombre', 'telefono']
    search_fields = ['nombre', 'telefono']


@admin.register(EmbarcacionNoDisponible)
class EmbarcacionNoDisponibleAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
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
class VehiculoAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    list_display = ['nombre', 'lugares', 'activo']
    list_filter = ['activo']
    list_editable = ['activo']
    search_fields = ['nombre']


@admin.register(VehiculoNoDisponible)
class VehiculoNoDisponibleAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
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


class IncluyeAdminFormMixin(forms.Form):
    """Lo que incluye, capturado en dos cuadros de texto (un renglón por línea) en vez de JSON."""
    incluye_es = forms.CharField(
        label='Qué incluye (español)', required=False, widget=forms.Textarea(attrs={'rows': 4}),
        help_text=f'Un renglón por línea, hasta {INCLUYE_MAX_RENGLONES} de {INCLUYE_MAX_CARACTERES} caracteres. '
                  'La tarjeta y la página del servicio lo muestran tal cual.',
    )
    incluye_en = forms.CharField(
        label='Qué incluye (inglés)', required=False, widget=forms.Textarea(attrs={'rows': 4}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        incluye = self.instance.incluye if self.instance and isinstance(self.instance.incluye, dict) else {}
        self.fields['incluye_es'].initial = '\n'.join(incluye.get('es', []))
        self.fields['incluye_en'].initial = '\n'.join(incluye.get('en', []))

    def _post_clean(self):
        # Antes de validar el modelo: su clean() revisa los límites de lo que armamos aquí.
        lineas = {idioma: lineas_de_texto(self.cleaned_data.get(f'incluye_{idioma}')) for idioma in ('es', 'en')}
        self.instance.incluye = {idioma: renglones for idioma, renglones in lineas.items() if renglones}
        super()._post_clean()


class ServicioAdminForm(IncluyeAdminFormMixin, forms.ModelForm):
    class Meta:
        model = Servicio
        exclude = ['incluye']

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
class ServicioAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
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
            'fields': ('nombre', 'nombre_en', 'slug', 'tipo_servicio', 'descripcion', 'descripcion_en', 'incluye_es', 'incluye_en', 'activo'),
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
class RecursoAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    list_display = ['nombre', 'servicio', 'capacidad_maxima', 'activo']
    list_filter = ['servicio', 'activo']
    list_editable = ['capacidad_maxima', 'activo']
    search_fields = ['nombre']


class PersonalizacionAdminForm(forms.ModelForm):
    """La descripción por idioma se captura en dos campos de texto: nadie edita JSON a mano."""
    descripcion_es = forms.CharField(
        label='Descripción (español)', required=False, max_length=Personalizacion.DESCRIPCION_MAX,
        help_text='Texto corto que el checkout muestra bajo el extra. Déjalo vacío si no hace falta.',
    )
    descripcion_en = forms.CharField(
        label='Descripción (inglés)', required=False, max_length=Personalizacion.DESCRIPCION_MAX,
    )

    class Meta:
        model = Personalizacion
        exclude = ['descripcion']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        descripcion = self.instance.descripcion if self.instance and isinstance(self.instance.descripcion, dict) else {}
        self.fields['descripcion_es'].initial = descripcion.get('es', '')
        self.fields['descripcion_en'].initial = descripcion.get('en', '')

    def _post_clean(self):
        # Antes de validar el modelo: su clean() revisa y recorta lo que armamos aquí.
        textos = {
            'es': (self.cleaned_data.get('descripcion_es') or '').strip(),
            'en': (self.cleaned_data.get('descripcion_en') or '').strip(),
        }
        self.instance.descripcion = {idioma: texto for idioma, texto in textos.items() if texto}
        super()._post_clean()


@admin.register(Personalizacion)
class PersonalizacionAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    form = PersonalizacionAdminForm
    list_display = ['nombre', 'tipo', 'tipo_interaccion', 'cobrar_por_persona', 'cantidad_editable', 'aviso_reforzado', 'activo']
    list_filter = ['tipo', 'tipo_interaccion', 'cobrar_por_persona', 'cantidad_editable', 'aviso_reforzado', 'activo']
    list_editable = ['cobrar_por_persona', 'cantidad_editable', 'aviso_reforzado', 'activo']
    search_fields = ['nombre']


AYUDA_CAMPOS_PAQUETE = {
    'nombre': 'Nombre público de la experiencia o paquete.',
    'slug': 'Identificador único en URL para el catálogo y la web.',
    'descripcion': 'Detalle de la experiencia, actividades y servicios incluidos.',
    'sede': 'Destino geográfico donde opera este paquete.',
    'empresa_lider': 'Empresa titular responsable del cobro de la experiencia.',
    'activo': 'Si está activo, el paquete estará disponible en el catálogo.',
}

AYUDA_CAMPOS_PAQUETE_SERVICIO = {
    'orden': 'Posición en la que se lista este servicio dentro del itinerario.',
    'dia_estancia': 'Día del paquete en que inicia el servicio (el día 1 es la fecha de inicio elegida por el cliente).',
    'salidas': 'Solo actividades: días seguidos que se repite la salida a partir del día indicado. Ejemplo: día 2 con 2 salidas = días 2 y 3.',
    'noches': 'Solo hospedaje: noches incluidas a partir del día 1. No aplica a otros servicios.',
    'personas_incluidas': 'Personas que lleva este servicio por defecto. Al menos 1 y no más que la capacidad máxima del servicio; el cliente puede usar menos sin que baje el precio del paquete.',
}


class PaqueteAdminForm(IncluyeAdminFormMixin, forms.ModelForm):
    class Meta:
        model = Paquete
        exclude = ['incluye']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'porcentaje_anticipo' in self.fields:
            self.fields['porcentaje_anticipo'].required = False
        for campo, ayuda in AYUDA_CAMPOS_PAQUETE.items():
            if campo in self.fields and not self.fields[campo].help_text:
                self.fields[campo].help_text = ayuda

    def clean_porcentaje_anticipo(self):
        valor = self.cleaned_data.get('porcentaje_anticipo')
        return valor if valor is not None else 30


class PaqueteServicioInlineForm(forms.ModelForm):
    class Meta:
        model = PaqueteServicio
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo, ayuda in AYUDA_CAMPOS_PAQUETE_SERVICIO.items():
            if campo in self.fields:
                self.fields[campo].help_text = ayuda


def _dinero(valor):
    """Importe con separador de miles y dos decimales, como texto listo para `format_html`."""
    return f'{valor:,.2f}'


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
        errores_crudos = errores_de_paquete(
            permite_anticipo=self.instance.permite_anticipo,
            componentes=[componente_de(ps) for ps in filas],
        )

        errores = []
        hospedajes = [ps for ps in filas if ps.servicio and ps.servicio.estrategia_cupo == 'por_noche']
        servicios_nombres = ', '.join(f'"{ps.servicio.nombre}"' for ps in filas if ps.servicio)

        for err in errores_crudos:
            if err == 'Un paquete solo puede incluir un hospedaje.':
                nombres_hosp = ', '.join(f'"{ps.servicio.nombre}"' for ps in hospedajes)
                errores.append(f'{nombres_hosp}: Un paquete solo puede incluir un hospedaje.')
            elif err.startswith('Un paquete con servicios de dos empresas no admite anticipo'):
                errores.append(f'{servicios_nombres}: {err}')
            elif err == 'En un paquete de dos empresas solo puede haber un servicio por empresa.':
                errores.append(f'{servicios_nombres}: En un paquete de dos empresas solo puede haber un servicio por empresa.')
            elif err.startswith('Las actividades del paquete deben ocurrir'):
                actividades = [ps for ps in filas if ps.servicio and ps.servicio.estrategia_cupo == 'por_recurso_dia']
                act_nombres = ', '.join(f'"{ps.servicio.nombre}"' for ps in actividades)
                errores.append(f'{act_nombres}: {err}')
            elif err.startswith('Una actividad de varios días'):
                actividades = [ps for ps in filas if ps.servicio and (ps.salidas or 1) > 1]
                act_nombres = ', '.join(f'"{ps.servicio.nombre}"' for ps in actividades)
                errores.append(f'{act_nombres}: {err}')
            else:
                errores.append(err)

        for ps in filas:
            if not ps.servicio or ps.servicio.tipo_servicio != 'transporte':
                continue
            personas = ps.personas_incluidas if ps.personas_incluidas is not None else 1
            err_dict = errores_de_precio_contra_transporte(
                self.instance, [(ps.servicio, personas)],
            )
            for msg in err_dict.values():
                errores.append(f'"{ps.servicio.nombre}": {msg}')

        if errores:
            raise ValidationError(errores)


class PaqueteServicioInline(TabularInline):
    model = PaqueteServicio
    form = PaqueteServicioInlineForm
    formset = PaqueteServicioFormSet
    extra = 1
    description = (
        'Componentes incluidos: el día 1 es la fecha de inicio elegida por el cliente. '
        'Las salidas de actividades se repiten en días seguidos. '
        'Las noches aplican solo a hospedaje (a partir del día 1). '
        'Personas incluidas son las que lleva ese servicio por defecto (el cliente puede usar menos sin que baje el precio). '
        'El orden determina la secuencia en el itinerario.'
    )
    fields = ['servicio', 'orden', 'dia_estancia', 'salidas', 'noches', 'personas_incluidas']
    autocomplete_fields = ['servicio']


@admin.register(Paquete)
class PaqueteAdmin(EmpresaScopedAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    empresa_campo = 'empresa_lider'
    form = PaqueteAdminForm
    exclude = ['regla_precio', 'incluye']
    list_display = [
        'nombre', 'sede', 'empresa_lider', 'precio_ancla', 'estrategia_precio',
        'personas_precio_base', 'precio_persona_extra', 'pide_hora',
        'permite_anticipo', 'porcentaje_anticipo', 'activo',
    ]
    list_filter = ['sede', 'activo']
    list_editable = ['precio_ancla', 'activo']
    search_fields = ['nombre', 'slug', 'descripcion']
    prepopulated_fields = {'slug': ('nombre',)}
    readonly_fields = ['resumen_del_paquete', 'creado_en', 'actualizado_en']
    inlines = [PaqueteServicioInline]

    fieldsets = [
        ('Resumen', {
            'description': 'Vista previa del itinerario, tarifas calculadas y cobertura de transporte.',
            'fields': ('resumen_del_paquete',),
        }),
        ('Qué es', {
            'description': 'Identificación básica del paquete, sede y empresa líder.',
            'fields': ('nombre', 'nombre_en', 'slug', 'descripcion', 'descripcion_en', 'incluye_es', 'incluye_en', 'sede', 'empresa_lider', 'activo'),
        }),
        ('Precio', {
            'description': 'Esquema de cobro y tarifas base en pesos (MXN).',
            'fields': ('precio_ancla', 'estrategia_precio', 'personas_precio_base', 'precio_persona_extra'),
        }),
        ('Reserva', {
            'description': 'Definición de selección de horario por el cliente al reservar.',
            'fields': ('pide_hora',),
        }),
        ('Anticipo', {
            'description': 'Condiciones de cobro fraccionado en línea.',
            'fields': ('permite_anticipo', 'porcentaje_anticipo'),
        }),
        ('Registro', {
            'classes': ('collapse',),
            'description': 'Marcas de tiempo de auditoría del sistema.',
            'fields': ('creado_en', 'actualizado_en'),
        }),
    ]

    conditional_fields = {
        'porcentaje_anticipo': 'permite_anticipo == true',
    }

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'porcentaje_anticipo':
            kwargs['required'] = False
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield and db_field.name in AYUDA_CAMPOS_PAQUETE and not formfield.help_text:
            formfield.help_text = AYUDA_CAMPOS_PAQUETE[db_field.name]
        return formfield

    @admin.display(description='Resumen del paquete')
    def resumen_del_paquete(self, obj):
        if not obj or not obj.pk:
            return mark_safe('<p style="color:#6b7280;margin:0;">Guarda el paquete para ver su resumen.</p>')

        # 1. Itinerario
        componentes = list(
            obj.servicios_asociados.select_related('servicio')
            .order_by('dia_estancia', 'orden', 'servicio__nombre')
        )
        items_itinerario = []
        if not componentes:
            items_itinerario.append(mark_safe('<li><em>Sin componentes configurados.</em></li>'))
        else:
            for ps in componentes:
                servicio = ps.servicio
                if not servicio:
                    continue
                salidas = max(1, ps.salidas or 1)
                if servicio.estrategia_cupo == 'por_noche':
                    dia_str = f'Día {ps.dia_estancia}'
                    noches = ps.noches or 0
                    detalle = f'{servicio.nombre} ({noches} noche{"s" if noches != 1 else ""})'
                elif salidas > 1:
                    dia_fin = ps.dia_estancia + salidas - 1
                    dia_str = f'Día {ps.dia_estancia} y {dia_fin}' if salidas == 2 else f'Día {ps.dia_estancia} a {dia_fin}'
                    detalle = f'{servicio.nombre} ({salidas} salidas)'
                elif servicio.estrategia_cupo == 'por_recurso_dia':
                    dia_str = f'Día {ps.dia_estancia}'
                    detalle = f'{servicio.nombre} (1 salida)'
                else:
                    dia_str = f'Día {ps.dia_estancia}'
                    detalle = f'{servicio.nombre}'

                items_itinerario.append(
                    format_html(
                        '<li style="margin-bottom:4px;"><strong>{}</strong> · {}</li>',
                        dia_str, detalle
                    )
                )

        itinerario_html = format_html(
            '<div style="margin-bottom:14px;">'
            '<h4 style="margin:0 0 6px 0;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#4b5563;">Itinerario</h4>'
            '<ul style="margin:0;padding-left:18px;">{}</ul>'
            '</div>',
            format_html_join('', '{}', ((item,) for item in items_itinerario))
        )

        # 2. Precio por tamaño de grupo (1 a 8 personas)
        filas_precios = []
        for n in range(1, 9):
            total = obj.precio_total_en('MXN', n)
            if total is not None:
                filas_precios.append(
                    format_html(
                        '<div style="padding:6px 10px;border:1px solid rgba(156,163,175,0.25);border-radius:6px;text-align:center;">'
                        '<div style="font-size:11px;color:#6b7280;">{} persona{}</div>'
                        '<div style="font-size:13px;font-weight:600;">${} MXN</div>'
                        '</div>',
                        n, 's' if n != 1 else '', _dinero(total)
                    )
                )
            else:
                filas_precios.append(
                    format_html(
                        '<div style="padding:6px 10px;border:1px solid rgba(156,163,175,0.25);border-radius:6px;text-align:center;">'
                        '<div style="font-size:11px;color:#6b7280;">{} persona{}</div>'
                        '<div style="font-size:13px;color:#9ca3af;">—</div>'
                        '</div>',
                        n, 's' if n != 1 else ''
                    )
                )

        precios_html = format_html(
            '<div style="margin-bottom:14px;">'
            '<h4 style="margin:0 0 6px 0;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#4b5563;">Precio por tamaño de grupo (MXN)</h4>'
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;">{}</div>'
            '</div>',
            format_html_join('', '{}', ((fila,) for fila in filas_precios))
        )

        # 3. Cobertura del transporte
        traslados = [ps for ps in componentes if ps.servicio and ps.servicio.tipo_servicio == 'transporte']
        transporte_html = ''
        if traslados:
            filas_transporte = []
            for ps in traslados:
                tarifas = list(ps.servicio.empresa.tarifas_transporte.filter(activo=True))
                filas_servicio = []
                for n in range(1, ps.personas_incluidas + 1):
                    peor_mxn = peor_tarifa(tarifas, personas=n, moneda='MXN')
                    total = obj.precio_total_en('MXN', n)
                    if peor_mxn is not None and total is not None:
                        if total < peor_mxn:
                            faltante = peor_mxn - total
                            badge = format_html(
                                '<span style="color:#dc2626;font-weight:600;">No cubre (falta ${} MXN)</span> '
                                '<span style="color:#6b7280;font-size:12px;">(Precio ${} vs Peor tarifa ${})</span>',
                                _dinero(faltante), _dinero(total), _dinero(peor_mxn)
                            )
                        else:
                            badge = format_html(
                                '<span style="color:#15803d;font-weight:600;">Cubre</span> '
                                '<span style="color:#6b7280;font-size:12px;">(Precio ${} vs Peor tarifa ${})</span>',
                                _dinero(total), _dinero(peor_mxn)
                            )
                    elif peor_mxn is None:
                        badge = mark_safe('<span style="color:#9ca3af;">Sin tarifa aplicable</span>')
                    else:
                        badge = mark_safe('<span style="color:#9ca3af;">Sin precio de paquete</span>')

                    filas_servicio.append(
                        format_html(
                            '<li style="margin-bottom:3px;"><strong>{} persona{}:</strong> {}</li>',
                            n, 's' if n != 1 else '', badge
                        )
                    )

                filas_transporte.append(
                    format_html(
                        '<div style="margin-top:6px;">'
                        '<div style="font-weight:500;font-size:13px;margin-bottom:4px;">{} (hasta {} personas incluidas):</div>'
                        '<ul style="margin:0;padding-left:18px;">{}</ul>'
                        '</div>',
                        ps.servicio.nombre, ps.personas_incluidas,
                        format_html_join('', '{}', ((f,) for f in filas_servicio))
                    )
                )

            transporte_html = format_html(
                '<div>'
                '<h4 style="margin:0 0 6px 0;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#4b5563;">Cobertura del transporte</h4>'
                '{}'
                '</div>',
                format_html_join('', '{}', ((ft,) for ft in filas_transporte))
            )

        return format_html(
            '<div style="display:flex;flex-direction:column;gap:10px;padding:14px;border:1px solid rgba(156,163,175,0.3);border-radius:8px;">'
            '{}{}{}'
            '</div>',
            itinerario_html, precios_html, transporte_html
        )
