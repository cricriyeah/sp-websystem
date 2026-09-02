# backend/apps/tenancy/middleware.py
from django.urls import Resolver404, resolve

from . import scope


class EmpresaScopeMiddleware:
    """Ver "Resolucion de alcance" en el plan para el pseudocodigo original.
    Envuelve __call__ completo (no process_view): el admin de Django renderiza
    sus listados de forma perezosa, despues de que process_view ya devolvio
    (Revision 3) -- process_view solo no basta."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            match = resolve(request.path_info)
        except Resolver404:
            match = None

        if match is None or 'empresa_slug' in match.kwargs:
            # Ruta publica (se envuelve sola en la vista) o no reconocida.
            return self.get_response(request)

        if request.user.is_anonymous or match.view_name == 'admin:logout':
            # Anonimo o cerrando sesion: sin alcance. Sin este caso, un
            # usuario autenticado con 0/>1 membresias recibe PermissionDenied
            # en TODA ruta del admin, incluido logout (Revision 4, N19).
            return self.get_response(request)

        alcance = scope.resolver_membresia_o_403(request.user)
        with alcance:
            return self.get_response(request)
