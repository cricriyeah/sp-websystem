"""Vista para responder con el precio sugerido en el formulario de alta de Reserva."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed, JsonResponse

from apps.bookings.models import Reserva
from apps.bookings.precio_sugerido import sugerir_precio
from apps.fleet.models import Paquete, Servicio
from apps.tenancy import scope


def formatear_etiqueta(precio: Decimal, moneda: str) -> str:
    """Etiqueta legible con separador de miles; sin decimales si es entero."""
    if precio == precio.to_integral_value():
        monto_str = f'{precio:,.0f}'
    else:
        monto_str = f'{precio:,.2f}'
    return f'Sugerido: {monto_str} {moneda}'


def respuesta_precio_sugerido(modelo_admin, request) -> JsonResponse:
    """Calcula y devuelve el precio sugerido en JSON para el alta de reserva.

    Responde 200 con {'precio': None, 'etiqueta': None} ante cualquier entrada
    invalida o faltante, evitando errores 500 en el formulario administrativo.
    """
    # 1. Permisos del admin: alta o edicion de reservas
    if not (modelo_admin.has_add_permission(request) or modelo_admin.has_change_permission(request)):
        raise PermissionDenied

    # 2. Metodo: solo GET
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    # 3. Parametros y validacion basica
    try:
        servicio_param = request.GET.get('servicio', '').strip()
        paquete_param = request.GET.get('paquete', '').strip()

        # servicio y paquete son mutuamente excluyentes y obligatorios
        tiene_servicio = bool(servicio_param)
        tiene_paquete = bool(paquete_param)
        if (tiene_servicio and tiene_paquete) or (not tiene_servicio and not tiene_paquete):
            return JsonResponse({'precio': None, 'etiqueta': None})

        servicio_id = int(servicio_param) if tiene_servicio else None
        paquete_id = int(paquete_param) if tiene_paquete else None

        # Personas: entero mayor o igual a 1
        personas_param = request.GET.get('personas', '').strip()
        personas_int = int(personas_param)
        if personas_int < 1:
            return JsonResponse({'precio': None, 'etiqueta': None})

        # Moneda: 'MXN' o 'USD'
        moneda = request.GET.get('moneda', '').strip().upper()
        if moneda not in (Reserva.Moneda.MXN, Reserva.Moneda.USD):
            return JsonResponse({'precio': None, 'etiqueta': None})

        # Datos opcionales de traslado
        tipo_traslado = request.GET.get('tipo_traslado', '').strip()
        detalle_transporte = None
        if tipo_traslado:
            zona = request.GET.get('zona', '').strip()
            p_traslado_param = request.GET.get('personas_traslado', '').strip()
            p_traslado_int = None
            if p_traslado_param:
                p_traslado_int = int(p_traslado_param)
                if p_traslado_int < 1:
                    return JsonResponse({'precio': None, 'etiqueta': None})
            detalle_transporte = {
                'tipo_traslado': tipo_traslado,
                'zona': zona,
                'numero_personas': p_traslado_int,
            }

        fecha = request.GET.get('fecha', '').strip() or None
        fecha_salida = request.GET.get('fecha_salida', '').strip() or None

    except (TypeError, ValueError):
        # Parametros no enteros o malformados devuelven respuesta sin sugerencia
        return JsonResponse({'precio': None, 'etiqueta': None})

    # 4. Alcance de empresa (tenancy)
    es_operador = scope.es_operador_plataforma(request.user)
    empresa = scope.empresa_actual(request)

    servicio = None
    paquete = None

    if servicio_id is not None:
        if es_operador:
            servicio = Servicio.objects.filter(pk=servicio_id).first()
        else:
            if not empresa:
                return JsonResponse({'precio': None, 'moneda': moneda, 'etiqueta': None})
            servicio = Servicio.objects.filter(pk=servicio_id, empresa=empresa).first()
        if not servicio:
            return JsonResponse({'precio': None, 'moneda': moneda, 'etiqueta': None})

    if paquete_id is not None:
        if es_operador:
            paquete = Paquete.objects.filter(pk=paquete_id).first()
        else:
            if not empresa:
                return JsonResponse({'precio': None, 'moneda': moneda, 'etiqueta': None})
            paquete = Paquete.objects.filter(pk=paquete_id, empresa_lider=empresa).first()
        if not paquete:
            return JsonResponse({'precio': None, 'moneda': moneda, 'etiqueta': None})

    # 5. Calculo del precio sugerido
    precio = sugerir_precio(
        servicio=servicio,
        paquete=paquete,
        numero_personas=personas_int,
        moneda=moneda,
        fecha=fecha,
        fecha_salida=fecha_salida,
        detalle_transporte=detalle_transporte,
    )

    if precio is None:
        return JsonResponse({'precio': None, 'moneda': moneda, 'etiqueta': None})

    return JsonResponse({
        'precio': f'{precio:.2f}',
        'moneda': moneda,
        'etiqueta': formatear_etiqueta(precio, moneda),
    })
