# backend/apps/tenancy/admin_mixins.py
from . import scope


class EmpresaScopedAdminMixin:
    """Va PRIMERO en el MRO: `class XAdmin(EmpresaScopedAdminMixin, ModelAdmin)`.
    Subclases declaran `campos_escopeados_por_empresa = ('fk1', 'fk2')` para que
    `formfield_for_foreignkey` filtre esas FK al `empresa_actual`."""

    campos_escopeados_por_empresa = ()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if scope.es_operador_plataforma(request.user):
            return qs
        return qs.filter(empresa=scope.empresa_actual(request))

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if 'empresa' not in fields:
            return fields
        if obj is not None:
            # Edicion: NUNCA se reasigna empresa, sin importar el rol.
            fields.remove('empresa')
        elif not scope.es_operador_plataforma(request.user):
            # Creacion, no operador: se autoasigna en save_model, no se pide.
            fields.remove('empresa')
        # Creacion + operador: se queda, visible y obligatorio.
        return fields

    def save_model(self, request, obj, form, change):
        if not change and not scope.es_operador_plataforma(request.user):
            obj.empresa = scope.empresa_actual(request)
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in self.campos_escopeados_por_empresa:
            empresa = scope.empresa_actual(request)
            if empresa is not None:
                kwargs['queryset'] = db_field.remote_field.model.objects.filter(empresa=empresa)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
