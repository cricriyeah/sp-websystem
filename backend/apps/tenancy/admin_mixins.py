# backend/apps/tenancy/admin_mixins.py
from django.core.exceptions import ValidationError

from . import scope
from .models import MembresiaEmpresa


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

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        if obj is not None or scope.es_operador_plataforma(request.user):
            return form_class

        empresa = scope.empresa_actual(request)
        campo = self.empresa_campo

        class FormularioConEmpresa(form_class):
            def __init__(self, *args, **form_kwargs):
                instancia = form_kwargs.get('instance')
                if instancia is None:
                    instancia = self._meta.model()
                    form_kwargs['instance'] = instancia
                setattr(instancia, campo, empresa)
                super().__init__(*args, **form_kwargs)

        return FormularioConEmpresa

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

    def _empresa_del_usuario(self, request):
        empresa = scope.empresa_actual(request)
        if empresa is None and getattr(request, 'user', None) and request.user.is_authenticated:
            membresia = MembresiaEmpresa.objects.filter(user=request.user).select_related('empresa').first()
            if membresia:
                empresa = membresia.empresa
        return empresa

    def _es_jefe(self, user, empresa=None):
        if user.is_anonymous or scope.es_operador_plataforma(user):
            return False
        if user.groups.filter(name='Jefe').exists():
            return True
        if empresa is not None:
            return MembresiaEmpresa.objects.filter(
                user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.JEFE,
            ).exists()
        return MembresiaEmpresa.objects.filter(
            user=user, rol=MembresiaEmpresa.Rol.JEFE,
        ).exists()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not getattr(request, 'user', None) or request.user.is_anonymous:
            return qs.none()
        if scope.es_operador_plataforma(request.user):
            return qs

        empresa = self._empresa_del_usuario(request)
        if self._es_jefe(request.user, empresa):
            if empresa is None:
                return qs.none()
            return qs.filter(membresias__empresa=empresa).distinct()

        # Vendedora (y cualquier otro usuario no jefe/operador): solo ella misma
        return qs.filter(pk=request.user.pk)

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
        if obj is None:
            return super().has_change_permission(request, None)

        if not self._en_alcance(request, obj):
            return False

        if scope.es_operador_plataforma(request.user):
            return super().has_change_permission(request, obj)

        # Cada usuario puede editar su propio usuario (nombre, correo, contraseña)
        if obj.pk == request.user.pk:
            return super().has_change_permission(request, obj)

        # Una vendedora no puede editar a nadie más que a sí misma
        empresa = self._empresa_del_usuario(request)
        if not self._es_jefe(request.user, empresa):
            return False

        # El jefe no puede editar a otro jefe ni a un operador
        if scope.es_operador_plataforma(obj) or obj.groups.filter(name='Jefe').exists():
            return False

        # El jefe solo puede editar a las vendedoras de su empresa
        es_vendedora = MembresiaEmpresa.objects.filter(
            user=obj, empresa=empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
        ).exists()
        if not es_vendedora:
            return False

        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Nadie salvo el operador puede borrar usuarios; un usuario no puede borrarse a sí mismo
        if not scope.es_operador_plataforma(request.user):
            return False
        if obj is not None and obj.pk == request.user.pk:
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

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        # Un usuario no puede desactivarse a sí mismo (is_active es de solo lectura sobre sí mismo).
        # Para otros usuarios (jefe editando vendedora), is_active es editable.
        # NUNCA agregar 'password' ni 'email' a readonly_fields: la edición de contraseñas
        # se restringe vía has_change_permission para evitar KeyError en UserChangeForm.
        if obj is not None and obj.pk == request.user.pk:
            if 'is_active' not in readonly_fields:
                readonly_fields.append('is_active')
        return tuple(readonly_fields)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form_class = super().get_form(request, obj, change=change, **kwargs)
        if obj is not None and obj.pk == request.user.pk:
            class FormularioUsuarioPropio(form_class):
                def clean_is_active(self):
                    is_active = self.cleaned_data.get('is_active')
                    if is_active is False:
                        raise ValidationError('No puedes desactivar tu propio usuario.')
                    return is_active

            return FormularioUsuarioPropio
        return form_class

    def save_model(self, request, obj, form, change):
        if change and obj.pk == request.user.pk and not obj.is_active:
            obj.is_active = True
        super().save_model(request, obj, form, change)

