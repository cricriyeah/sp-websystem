"""Middleware para atrapar errores inesperados en /admin/ y redirigir con mensaje."""

import logging
import uuid
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.messages.api import MessageFailure
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponseRedirect
from django.urls import Resolver404, reverse
from django.utils.http import url_has_allowed_host_and_scheme

logger = logging.getLogger('apps.errores')

EXCEPCIONES_IGNORADAS = (
    PermissionDenied,
    Http404,
    SuspiciousOperation,
    Resolver404,
)


class ErrorInesperadoAdminMiddleware:
    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):
        if self.get_response:
            return self.get_response(request)
        return None

    def process_exception(self, request, exception):
        path = getattr(request, 'path', '')
        if not path.startswith('/admin/'):
            return None

        if isinstance(exception, EXCEPCIONES_IGNORADAS):
            return None

        # Peticiones AJAX o JSON quedan fuera (se gestionan en su propio canal)
        headers = getattr(request, 'headers', {})
        is_ajax = headers.get('x-requested-with') == 'XMLHttpRequest' or \
            request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
        accept = headers.get('accept', '') or request.META.get('HTTP_ACCEPT', '')
        is_json = 'application/json' in accept
        if is_ajax or is_json:
            return None

        codigo = uuid.uuid4().hex[:8].upper()
        metodo = getattr(request, 'method', '')
        usuario = getattr(request, 'user', None)
        usuario_id = usuario.pk if (usuario and getattr(usuario, 'is_authenticated', False)) else None

        logger.exception(
            "Error inesperado en admin [%s] %s %s (usuario_id=%s)",
            codigo, metodo, path, usuario_id,
        )

        mensaje = (
            f"Algo salió mal (código {codigo}). Es posible que una parte de la operación "
            f"sí se haya aplicado: revisa antes de repetirla. Si se repite, avisa con este código."
        )

        try:
            messages.error(request, mensaje)
        except (MessageFailure, Exception):
            pass

        # Determinar a donde redirigir
        referer = request.META.get('HTTP_REFERER')
        try:
            host = request.get_host()
        except Exception:
            host = None

        destino = None
        if referer and host and url_has_allowed_host_and_scheme(referer, allowed_hosts={host}):
            referer_path = urlparse(referer).path
            if metodo == 'GET':
                if referer_path != path:
                    destino = referer
            else:
                destino = referer

        if not destino:
            destino = reverse('admin:index')

        return HttpResponseRedirect(destino)
