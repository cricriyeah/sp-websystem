"""Aviso de reservas nuevas, para cualquier pantalla del admin (`/admin/avisos/reservas-nuevas/`).

El admin es HTML renderizado en el servidor y no hay conexion abierta con el navegador, asi que el aviso es una
pregunta corta y frecuente: `tenancy/avisos.js` pregunta cada 10 segundos (solo con la pestana a la vista) que
entro desde la ultima vez. No es instantaneo; es lo bastante cerca para atender a un cliente a tiempo.

"Entro" es la ultima vez que la reserva se volvio una venta: cuando se creo, cuando se pago con tarjeta o cuando
se anoto una transferencia. Contar solo `creado_en` perdia las que se crean en la web, se quedan esperando y se
pagan despues (o las que la vendedora marca pagadas por transferencia). Las `pendiente_pago` no cuentan: cada
checkout abandonado deja una y avisar de esas seria puro ruido.
"""
import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import DateTimeField, F
from django.db.models.functions import Coalesce, Greatest
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.tenancy import scope
from apps.tenancy.notificaciones import contar_no_leidas

from .models import ESTADOS_QUE_OCUPAN_CUPO, Reserva

logger = logging.getLogger(__name__)

MAXIMO_AVISOS = 5


def reservas_nuevas(request):
    """JSON con las reservas que entraron despues de `?desde=`.

    Sin `desde` solo devuelve la hora del servidor: el navegador nunca usa su propio reloj como referencia. La
    respuesta trae `desde` ya adelantado a la hora en que se consulto, tomada ANTES de la consulta, para que la
    siguiente pregunta no pierda una reserva que entre mientras esta se arma ni repita una ya avisada.
    """
    if not request.user.has_perm('bookings.view_reserva'):
        raise PermissionDenied

    ahora = timezone.now()
    desde_param = request.GET.get('desde')
    campana = _de_la_campana(request)
    if not desde_param:
        return JsonResponse({'desde': ahora.isoformat(), 'total': 0, 'reservas': [], **campana})
    try:
        desde = parse_datetime(desde_param)
    except ValueError:  # formato valido, fecha imposible (mes 13)
        desde = None
    if desde is None:
        return JsonResponse({'detail': 'desde invalido.'}, status=400)
    if timezone.is_naive(desde):
        desde = timezone.make_aware(desde)

    consulta = Reserva.objects.filter(estado__in=ESTADOS_QUE_OCUPAN_CUPO)
    empresa = scope.empresa_actual(request)
    if empresa is not None:
        consulta = consulta.filter(empresa=empresa)
    elif not scope.es_operador_plataforma(request.user):
        consulta = consulta.none()

    entro_en = Greatest(
        F('creado_en'),
        Coalesce('pagada_en', F('creado_en')),
        Coalesce('transferencia_registrada_en', F('creado_en')),
        output_field=DateTimeField(),
    )
    nuevas = (
        consulta.annotate(entro_en=entro_en)
        .filter(entro_en__gt=desde, entro_en__lte=ahora)
        .select_related('servicio', 'paquete')
        .order_by('-entro_en')
    )
    total = nuevas.count()
    reservas = [_como_aviso(r) for r in nuevas[:MAXIMO_AVISOS]]
    return JsonResponse({'desde': ahora.isoformat(), 'total': total, 'reservas': reservas, **campana})


def _de_la_campana(request):
    """Lo que necesita la campana de notificaciones (`tenancy/avisos.js`) en la misma respuesta del sondeo, sin
    otra peticion: cuantas no ha leido esta persona y a donde lleva la campana. Sin permiso de ver notificaciones no
    hay URL y el JS no pinta campana. Un fallo del feed jamas debe tumbar el aviso de reservas: queda en el log y
    la campana se calla (el savepoint evita dejar abortada la transaccion de la peticion en Postgres)."""
    if not request.user.has_perm('tenancy.view_notificacion'):
        return {'no_leidas': 0, 'notificaciones_url': ''}
    try:
        with transaction.atomic():
            return {
                'no_leidas': contar_no_leidas(request),
                'notificaciones_url': reverse('admin:tenancy_notificacion_changelist'),
            }
    except Exception:
        logger.exception('No se pudo contar las notificaciones sin leer.')
        return {'no_leidas': 0, 'notificaciones_url': ''}


def _como_aviso(reserva):
    producto = ''
    if reserva.paquete_id:
        producto = reserva.paquete.nombre
    elif reserva.servicio_id:
        producto = reserva.servicio.nombre
    return {
        'id': reserva.pk,
        'cliente': reserva.nombre_cliente,
        'producto': producto,
        'fecha': reserva.fecha.isoformat(),
        'hora': reserva.hora.strftime('%H:%M') if reserva.hora else '',
        'personas': reserva.numero_personas,
        'url': reverse('admin:bookings_reserva_change', args=[reserva.pk]),
    }
