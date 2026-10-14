"""Vistas para el manejo de errores HTTP 403, 404 y 500."""

import logging
import uuid

from django.http import HttpResponseServerError
from django.shortcuts import render
from django.template.loader import render_to_string

logger = logging.getLogger('apps.errores')


def _datos_request(request):
    """Extrae metodo, ruta e id de usuario sin datos personales."""
    if not request:
        return '', '', None
    metodo = getattr(request, 'method', '')
    ruta = getattr(request, 'path', '')
    usuario = getattr(request, 'user', None)
    usuario_id = usuario.pk if (usuario and getattr(usuario, 'is_authenticated', False)) else None
    return metodo, ruta, usuario_id


def error_403(request, exception=None):
    """Manejo de error 403 (Permiso denegado)."""
    codigo = uuid.uuid4().hex[:8].upper()
    metodo, ruta, usuario_id = _datos_request(request)
    es_admin = ruta.startswith('/admin/')

    if es_admin:
        logger.warning(
            "Error 403 [%s] %s %s (usuario_id=%s)",
            codigo, metodo, ruta, usuario_id,
        )

    contexto = {
        'codigo': codigo,
        'base_template': 'admin/base_site.html' if es_admin else 'base_error_simple.html',
    }
    return render(request, '403.html', contexto, status=403)


def error_404(request, exception=None):
    """Manejo de error 404 (Pagina no encontrada)."""
    codigo = uuid.uuid4().hex[:8].upper()
    metodo, ruta, usuario_id = _datos_request(request)
    es_admin = ruta.startswith('/admin/')

    if es_admin:
        logger.warning(
            "Error 404 [%s] %s %s (usuario_id=%s)",
            codigo, metodo, ruta, usuario_id,
        )

    contexto = {
        'codigo': codigo,
        'base_template': 'admin/base_site.html' if es_admin else 'base_error_simple.html',
    }
    return render(request, '404.html', contexto, status=404)


def error_500(request=None):
    """Manejo de error 500 (Error del servidor). Nunca debe lanzar excepcion."""
    try:
        codigo = uuid.uuid4().hex[:8].upper()
        metodo, ruta, usuario_id = _datos_request(request)
        logger.error(
            "Error 500 [%s] %s %s (usuario_id=%s)",
            codigo, metodo, ruta, usuario_id,
        )
        contenido = render_to_string('500.html', {'codigo': codigo})
        return HttpResponseServerError(contenido)
    except Exception:
        # Fallback de emergencia por si la plantilla fallara
        return HttpResponseServerError(
            "<!DOCTYPE html><html><body><h1>Algo salio mal</h1>"
            "<p>Codigo de referencia: ERROR</p>"
            "<a href=\"/admin/\">Volver al panel</a></body></html>"
        )

