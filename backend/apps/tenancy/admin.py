# backend/apps/tenancy/admin.py
from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin

from . import scope
from .models import Empresa, MembresiaEmpresa, Sede


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
class SedeAdmin(SoloOperadorPlataformaAdminMixin, ModelAdmin):
    list_display = ['nombre', 'slug', 'zona_horaria', 'tipo_cambio_usd', 'activo']
    prepopulated_fields = {'slug': ('nombre',)}
    search_fields = ['nombre', 'slug']


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
class EmpresaAdmin(SoloOperadorPlataformaAdminMixin, ModelAdmin):
    form = EmpresaAdminForm
    list_display = ['nombre', 'sede', 'slug', 'activo', 'exclusiva']
    list_filter = ['sede', 'activo']
    search_fields = ['nombre', 'slug']
    fields = [
        'sede', 'nombre', 'slug', 'activo', 'exclusiva',
        'stripe_secret_key', 'stripe_webhook_secret', 'stripe_publishable_key',
    ]


@admin.register(MembresiaEmpresa)
class MembresiaEmpresaAdmin(SoloOperadorPlataformaAdminMixin, ModelAdmin):
    """Salvo el alta vía la acción unificada 'Dar de alta vendedora' en
    `apps/bookings/admin.py` (Task B10) -- ese flujo crea la fila directo, sin
    pasar por este admin."""

    list_display = ['user', 'empresa', 'rol']
    list_filter = ['empresa', 'rol']
    autocomplete_fields = ['user', 'empresa']
