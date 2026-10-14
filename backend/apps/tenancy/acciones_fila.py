from django.http import HttpResponseRedirect
from django.urls import reverse
from unfold.decorators import action


class AccionesDeFilaMixin:
    """Columna de acciones por fila en las listas del admin (Unfold actions_row).

    Muestra Editar (o Ver si solo tiene permiso de lectura) y Eliminar
    (si tiene permiso de borrado).
    """

    actions_row = ['accion_fila_editar', 'accion_fila_ver', 'accion_fila_eliminar']

    def get_actions_row(self, request):
        actions = super().get_actions_row(request)
        has_change = self.has_change_permission(request)
        resultado = []
        for act in actions:
            fname = getattr(act.method, 'original_function_name', None) or act.method.__name__
            if fname == 'accion_fila_ver' and has_change:
                continue
            if fname == 'accion_fila_editar' and not has_change:
                continue
            resultado.append(act)
        return resultado

    @action(
        description='Editar',
        url_path='editar',
        permissions=['change'],
        extra_options={'display_in_dropdown': False},
    )
    def accion_fila_editar(self, request, object_id=None, *args, **kwargs):
        object_id = object_id or kwargs.get('object_id')
        opts = self.model._meta
        admin_site_name = self.admin_site.name if hasattr(self, 'admin_site') and self.admin_site else 'admin'
        return HttpResponseRedirect(
            reverse(f'{admin_site_name}:{opts.app_label}_{opts.model_name}_change', args=[object_id])
        )

    @action(
        description='Ver',
        url_path='ver',
        permissions=['view'],
        extra_options={'display_in_dropdown': False},
    )
    def accion_fila_ver(self, request, object_id=None, *args, **kwargs):
        object_id = object_id or kwargs.get('object_id')
        opts = self.model._meta
        admin_site_name = self.admin_site.name if hasattr(self, 'admin_site') and self.admin_site else 'admin'
        return HttpResponseRedirect(
            reverse(f'{admin_site_name}:{opts.app_label}_{opts.model_name}_change', args=[object_id])
        )

    @action(
        description='Eliminar',
        url_path='eliminar',
        permissions=['delete'],
        extra_options={'display_in_dropdown': False},
    )
    def accion_fila_eliminar(self, request, object_id=None, *args, **kwargs):
        object_id = object_id or kwargs.get('object_id')
        opts = self.model._meta
        admin_site_name = self.admin_site.name if hasattr(self, 'admin_site') and self.admin_site else 'admin'
        return HttpResponseRedirect(
            reverse(f'{admin_site_name}:{opts.app_label}_{opts.model_name}_delete', args=[object_id])
        )
