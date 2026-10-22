# backend/apps/tenancy/admin.py
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action

from . import scope
from .acciones_fila import AccionesDeFilaMixin
from .alta_empresa import AltaEmpresaForm, dar_de_alta_empresa, estado_de_empresa, url_del_webhook
from .models import Aeropuerto, Empresa, MembresiaEmpresa, Sede


class SoloOperadorPlataformaAdminMixin:
    def has_module_permission(self, request):
        return scope.es_operador_plataforma(request.user)

    def has_view_permission(self, request, obj=None):
        return scope.es_operador_plataforma(request.user)

    def has_add_permission(self, request):
        return scope.es_operador_plataforma(request.user)

    def has_change_permission(self, request, obj=None):
        return scope.es_operador_plataforma(request.user)

    def has_delete_permission(self, request, obj=None):
        return scope.es_operador_plataforma(request.user)


@admin.register(Sede)
class SedeAdmin(SoloOperadorPlataformaAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    list_display = ['nombre', 'slug', 'zona_horaria', 'tipo_cambio_usd', 'activo']
    prepopulated_fields = {'slug': ('nombre',)}
    search_fields = ['nombre', 'slug']


@admin.register(Aeropuerto)
class AeropuertoAdmin(SoloOperadorPlataformaAdminMixin, ModelAdmin):
    """Los aeropuertos de la Baja que ofrece el checkout de los paquetes: LAP, CSL, SJD y LTO, los únicos que existen.
    No se crean ni se borran aquí; solo se ajusta qué sedes tienen traslado a cada uno y si está activo."""

    list_display = ['nombre', 'codigo', 'sedes_cubiertas', 'activo']
    list_filter = ['activo', 'sedes']
    search_fields = ['nombre', 'codigo']
    readonly_fields = ['codigo', 'nombre']
    filter_horizontal = ['sedes']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Sedes que cubre')
    def sedes_cubiertas(self, obj):
        return ', '.join(sede.nombre for sede in obj.sedes.all()) or '—'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('sedes')


class EmpresaAdminForm(forms.ModelForm):
    """Las 3 llaves de Stripe son de solo-escritura: PasswordInput nunca
    repinta el valor guardado. Sin el clean() de abajo, dejar el campo vacio
    en un submit (porque nunca se vio el valor actual) borraria la llave ya
    puesta -- clean() la restaura desde la instancia si llega vacio."""

    stripe_secret_key = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    stripe_webhook_secret = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    stripe_publishable_key = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))

    class Meta:
        model = Empresa
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            for campo in ('stripe_secret_key', 'stripe_webhook_secret', 'stripe_publishable_key'):
                if not cleaned.get(campo):
                    cleaned[campo] = getattr(self.instance, campo)
        return cleaned


@admin.register(Empresa)
class EmpresaAdmin(SoloOperadorPlataformaAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    form = EmpresaAdminForm
    list_display = ['nombre', 'sede', 'slug', 'activo', 'exclusiva', 'pendientes']
    actions_list = ['accion_alta_empresa']
    list_filter = ['sede', 'activo']
    search_fields = ['nombre', 'slug']
    fields = [
        'sede', 'nombre', 'slug', 'activo', 'exclusiva',
        'correos_aviso',
        'stripe_secret_key', 'stripe_webhook_secret', 'stripe_publishable_key',
    ]

    def get_urls(self):
        # Antes de super(): el admin termina en un catch-all <path:object_id>/.
        return [
            path('alta/', self.admin_site.admin_view(self.alta_view), name='tenancy_empresa_alta'),
            path('<int:object_id>/estado/', self.admin_site.admin_view(self.estado_view),
                 name='tenancy_empresa_estado'),
        ] + super().get_urls()

    @action(description='Alta de empresa', url_path='alta-accion', permissions=['add'])
    def accion_alta_empresa(self, request):
        return HttpResponseRedirect(reverse('admin:tenancy_empresa_alta'))

    @admin.display(description='Pendientes')
    def pendientes(self, obj):
        faltan = sum(1 for paso in estado_de_empresa(obj) if not paso['hecho'])
        texto = f'{faltan} por hacer' if faltan else 'Lista'
        return format_html('<a href="{}">{}</a>', reverse('admin:tenancy_empresa_estado', args=[obj.pk]), texto)

    def alta_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method == 'POST':
            form = AltaEmpresaForm(request.POST)
            if form.is_valid():
                empresa = dar_de_alta_empresa(form.cleaned_data)
                messages.success(request, f'{empresa.nombre} dada de alta. Esto es lo que falta para que venda.')
                return HttpResponseRedirect(reverse('admin:tenancy_empresa_estado', args=[empresa.pk]))
        else:
            form = AltaEmpresaForm()
        return TemplateResponse(request, 'tenancy/alta_empresa.html', {
            **self.admin_site.each_context(request), 'form': form, 'title': 'Alta de empresa',
        })

    def estado_view(self, request, object_id):
        if not self.has_view_permission(request):
            raise PermissionDenied
        empresa = get_object_or_404(Empresa, pk=object_id)
        pasos = estado_de_empresa(empresa)
        return TemplateResponse(request, 'tenancy/estado_empresa.html', {
            **self.admin_site.each_context(request),
            'title': f'{empresa.nombre}: qué falta', 'empresa': empresa, 'pasos': pasos,
            'pendientes': sum(1 for paso in pasos if not paso['hecho']),
            'webhook': url_del_webhook(empresa, request),
        })


@admin.register(MembresiaEmpresa)
class MembresiaEmpresaAdmin(SoloOperadorPlataformaAdminMixin, AccionesDeFilaMixin, ModelAdmin):
    """Salvo el alta vía la acción unificada 'Dar de alta vendedora' en
    `apps/bookings/admin.py` (Task B10) -- ese flujo crea la fila directo, sin
    pasar por este admin."""

    list_display = ['user', 'empresa', 'rol']
    list_filter = ['empresa', 'rol']
    autocomplete_fields = ['user', 'empresa']

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.user_id == request.user.pk:
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.user_id == request.user.pk:
            return False
        return super().has_change_permission(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.filter(user_id=request.user.pk).exists():
            messages.error(request, 'No puedes quitarte tu propia membresía.')
            queryset = queryset.exclude(user_id=request.user.pk)
            if not queryset.exists():
                return
        super().delete_queryset(request, queryset)

