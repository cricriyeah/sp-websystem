# backend/apps/tenancy/admin_mixins.py
from . import scope


class EmpresaScopedAdminMixin:
    """Va PRIMERO en el MRO: `class XAdmin(EmpresaScopedAdminMixin, ModelAdmin)`.
    Subclases declaran `campos_escopeados_por_empresa = ('fk1', 'fk2')` para que
    `formfield_for_foreignkey` filtre esas FK al `empresa_actual`."""

    campos_escopeados_por_empresa = ()
    empresa_campo = 'empresa'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if scope.es_operador_plataforma(request.user):
            return qs
        return qs.filter(**{self.empresa_campo: scope.empresa_actual(request)})

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if self.empresa_campo not in fields:
            return fields
        if obj is not None:
            # Edicion: NUNCA se reasigna empresa, sin importar el rol.
            fields.remove(self.empresa_campo)
        elif not scope.es_operador_plataforma(request.user):
            # Creacion, no operador: se autoasigna en save_model, no se pide.
            fields.remove(self.empresa_campo)
        # Creacion + operador: se queda, visible y obligatorio.
        return fields

    def save_model(self, request, obj, form, change):
        if not change and not scope.es_operador_plataforma(request.user):
            setattr(obj, self.empresa_campo, scope.empresa_actual(request))
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in self.campos_escopeados_por_empresa:
            empresa = scope.empresa_actual(request)
            if empresa is not None:
                kwargs['queryset'] = db_field.remote_field.model.objects.filter(empresa=empresa)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# Campos del fieldset "Permissions" del UserAdmin de Django (verificado contra
# Django 6 instalado: is_active, is_staff, is_superuser, groups,
# user_permissions). Se identifica el fieldset por CONTENIDO (si trae
# is_superuser o groups), no por el TITULO del fieldset -- el titulo es una
# cadena _() traducida y con LANGUAGE_CODE='es-mx' podria no ser literalmente
# 'Permissions' en tiempo de ejecucion.
CAMPOS_PERMISOS_RESTRINGIDOS = ('is_active',)


class EmpresaScopedUserAdminMixin:
    """Unica capa de aislamiento sobre `auth.User`/`auth.Group` -- esas tablas
    no llevan RLS (son de arranque). Un filtro olvidado aqui es fuga
    silenciosa en CUALQUIER motor, no solo en sqlite/tests."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if scope.es_operador_plataforma(request.user):
            return qs
        return qs.filter(membresias__empresa=scope.empresa_actual(request))

    def _en_alcance(self, request, obj):
        return self.get_queryset(request).filter(pk=obj.pk).exists()

    def has_add_permission(self, request):
        if not scope.es_operador_plataforma(request.user):
            return False
        return super().has_add_permission(request)

    def has_view_permission(self, request, obj=None):
        if obj is not None and not self._en_alcance(request, obj):
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None and not self._en_alcance(request, obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not self._en_alcance(request, obj):
            return False
        return super().has_delete_permission(request, obj)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if scope.es_operador_plataforma(request.user):
            return fieldsets

        nuevos = []
        for titulo, opciones in fieldsets:
            campos = opciones.get('fields', ())
            if 'is_superuser' in campos or 'groups' in campos or 'user_permissions' in campos:
                opciones = {**opciones, 'fields': CAMPOS_PERMISOS_RESTRINGIDOS}
            nuevos.append((titulo, opciones))
        return nuevos
