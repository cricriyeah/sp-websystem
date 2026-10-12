"""Límites de horario y personas por servicio para el backoffice."""

from apps.bookings.models import MAX_PERSONAS


def limites_de_servicio(servicio) -> dict:
    """Devuelve los límites de horario y capacidad para un servicio.

    Calcula en memoria sin consultas a la base de datos: lee únicamente los
    atributos del objeto ya cargado.
    """
    ventana = servicio.ventana_horaria() if hasattr(servicio, 'ventana_horaria') else None
    if ventana:
        apertura_raw, cierre_raw = ventana
        apertura = apertura_raw[:5] if isinstance(apertura_raw, str) else apertura_raw.strftime('%H:%M')
        cierre = cierre_raw[:5] if isinstance(cierre_raw, str) else cierre_raw.strftime('%H:%M')
    else:
        apertura = None
        cierre = None

    pide_hora = bool(getattr(servicio, 'pide_hora', True))

    horas = None
    if pide_hora and ventana:
        h_ini, m_ini = (
            map(int, apertura.split(':')[:2])
            if isinstance(ventana[0], str)
            else (ventana[0].hour, ventana[0].minute)
        )
        h_fin, m_fin = (
            map(int, cierre.split(':')[:2])
            if isinstance(ventana[1], str)
            else (ventana[1].hour, ventana[1].minute)
        )
        total_ini = h_ini * 60 + m_ini
        total_fin = h_fin * 60 + m_fin
        paso = getattr(servicio, 'paso_hora_minutos', 15) or 15
        if total_ini <= total_fin and paso >= 1:
            horas = [
                f'{m // 60:02d}:{m % 60:02d}'
                for m in range(total_ini, total_fin + 1, paso)
            ]

    cap_max = getattr(servicio, 'capacidad_maxima', None)
    max_personas = cap_max if (cap_max and cap_max > 0) else MAX_PERSONAS
    min_personas = 1

    if pide_hora and ventana:
        etiqueta = f'{apertura} a {cierre} · hasta {max_personas} personas'
    else:
        etiqueta = f'hasta {max_personas} personas'

    return {
        'apertura': apertura,
        'cierre': cierre,
        'horas': horas,
        'pide_hora': pide_hora,
        'min_personas': min_personas,
        'max_personas': max_personas,
        'etiqueta': etiqueta,
    }


def mapa_limites(servicios, prefijo: str = '') -> dict:
    """Construye un mapa `{pk: limites}` (o `{prefijo+pk: limites}`) serializable a JSON.

    Recibe los servicios ya cargados para no ejecutar consultas en bucle.
    """
    return {
        f'{prefijo}{s.pk}' if prefijo else s.pk: limites_de_servicio(s)
        for s in servicios
    }
