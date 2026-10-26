"""Panel de la campana de notificaciones: las ultimas del feed, en JSON, para `tenancy/avisos.js`.

El panel se abre al hacer clic en la campana y se pinta encima de la pantalla actual; la lista completa sigue siendo
la pantalla de Notificaciones del admin. Aqui solo viven los dos endpoints que el panel necesita:

- `panel_notificaciones` (GET): las ultimas, con su estado de leida para ESTA persona, y el conteo de pendientes. Se
  consulta al abrir el panel y no en el sondeo de 10 s: no pesa en cada pagina.
- `marcar_todas_panel` (POST): marca como leidas las pendientes de quien lo pide. Va con token CSRF (lo exige
  `admin_view`); un GET nunca cambia estado.

Los dos respetan el alcance de la empresa (RLS en Postgres, filtro explicito en `notificaciones._del_alcance`) y van en
su propio savepoint: un fallo del feed no debe dejar abortada la transaccion de la peticion ni tumbar la pantalla.
"""
import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import notificaciones

logger = logging.getLogger(__name__)


def _exigir_permiso(request):
    if not request.user.has_perm('tenancy.view_notificacion'):
        raise PermissionDenied


@never_cache
@require_GET
def panel_notificaciones(request):
    _exigir_permiso(request)
    try:
        with transaction.atomic():
            return JsonResponse({
                'notificaciones': notificaciones.recientes_para_el_panel(request),
                'no_leidas': notificaciones.contar_no_leidas(request),
                'todas_url': reverse('admin:tenancy_notificacion_changelist'),
                'marcar_todas_url': reverse('avisos_notificaciones_marcar_todas'),
                # Para el POST de «Marcar todas»: la pagina del admin no siempre trae un formulario con el token.
                'csrf': get_token(request),
            })
    except Exception:
        logger.exception('No se pudo armar el panel de notificaciones.')
        return JsonResponse({'detail': 'No disponible.'}, status=503)


@never_cache
@require_POST
def marcar_todas_panel(request):
    _exigir_permiso(request)
    try:
        with transaction.atomic():
            marcadas = notificaciones.marcar_todas_las_del_alcance(request)
            return JsonResponse({'marcadas': marcadas, 'no_leidas': notificaciones.contar_no_leidas(request)})
    except Exception:
        logger.exception('No se pudo marcar como leidas desde el panel.')
        return JsonResponse({'detail': 'No disponible.'}, status=503)
