"""Correo al cliente cuando se le reagenda la reserva (ARCH-reagendar-reserva.md §7).

Mismo molde que el de asignacion (`services.enviar_correo_asignacion`): la cara sale de
`plantilla.correo`, los datos de una persona entran escapados con `services._html`, y
`enviar_correo_reagendado` nunca lanza: reagendar ya cambio la fecha y un correo caido no
puede deshacerla. El motivo de un fallo queda en `reserva.motivo_fallo_aviso` para que la
pantalla de quien reagenda lo diga.

Este correo nunca habla de dinero cobrado: el pago no cambia al mover la fecha. Solo dice
cuanto queda por liquidar en efectivo, si queda algo.
"""
import logging

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from . import plantilla
from .services import (
    TIMEOUT_SEGUNDOS,
    _empresa_de,
    _folio,
    _html,
    _par_punto_de_encuentro,
    _saldo_en_efectivo,
    hora_texto,
    motivo_para_persona,
)

logger = logging.getLogger(__name__)


def _vigente(objeto):
    """El primer dia que ve el cliente: el inicio del paquete si lo hay, si no la fecha.

    Sirve tanto para la reserva como para `antes` (se lee con getattr: el dataclass vive en
    `apps/bookings/reagendar.py` y este modulo solo necesita sus atributos).
    """
    return getattr(objeto, 'inicio_paquete', None) or getattr(objeto, 'fecha', None)


def _asunto(reserva):
    # El folio en el asunto: es lo que el cliente busca en su bandeja cuando necesita escribirnos.
    return f'Reserva reagendada{_folio(reserva)} — {_vigente(reserva)} {hora_texto(reserva)}'


def _dia_con_hora(fecha, hora):
    """«Lunes 7 de diciembre · 6:00 a. m.» (sin la hora si la reserva no la tiene)."""
    if not fecha:
        return ''
    dia = plantilla.dia_largo(fecha)
    return f'{dia} · {plantilla.hora_12(hora)}' if hora else dia


def _detalle_transporte(reserva):
    try:
        return reserva.detalle_transporte
    except (ObjectDoesNotExist, ValueError):  # sin detalle, o reserva aun sin guardar
        return None


def _quitaron_algo(reserva, antes):
    """Tenia panga o capitan y ya no: la asignacion hay que repetirla."""
    return bool(
        (getattr(antes, 'panga', '') and not reserva.embarcacion_id)
        or (getattr(antes, 'capitan', '') and not reserva.capitan_id)
    )


def _pares(reserva, antes, actividad):
    pares = []
    fecha_vieja = _vigente(antes)
    if fecha_vieja:
        pares.append(('Antes', _dia_con_hora(fecha_vieja, getattr(antes, 'hora', None))))
    pares.append(('Ahora', _dia_con_hora(_vigente(reserva), reserva.hora)))
    if actividad == 'mar' and reserva.hora:
        pares.append(('Llega a las', plantilla.hora_12(plantilla.quince_antes(reserva.hora)) + ' (15 minutos antes)'))

    detalle = _detalle_transporte(reserva) if actividad == 'traslado' else None
    punto_del_traslado = ''
    if detalle:
        punto_del_traslado = (
            detalle.punto_encuentro.nombre if detalle.punto_encuentro_id else detalle.direccion_personalizada)
    if punto_del_traslado:
        # El traslado dice el punto que eligio el cliente; el del servicio es la ficha del catalogo.
        pares.append(('Punto de encuentro', _html(punto_del_traslado)))
    else:
        punto = _par_punto_de_encuentro(reserva, 'Sales de' if actividad == 'mar' else 'Punto de encuentro')
        if punto:
            pares.append(punto)

    pares.append(('Personas', str(reserva.numero_personas)))
    # Capitan y panga solo si se conservaron; si se quitaron, el correo no los nombra.
    if reserva.capitan_id:
        pares.append(('Capitán', _html(reserva.capitan.nombre)))
    if reserva.embarcacion_id:
        pares.append(('Panga', _html(reserva.embarcacion.nombre)))

    inicio = _vigente(reserva)
    if reserva.fecha_salida and inicio:
        pares += [
            ('Llegada', plantilla.dia_largo(inicio)),
            ('Salida', plantilla.dia_largo(reserva.fecha_salida)),
            ('Noches', str(max((reserva.fecha_salida - inicio).days, 1))),
        ]
    if detalle and detalle.fecha_regreso:
        pares.append(('Fecha de regreso', plantilla.dia_largo(detalle.fecha_regreso)))
    return pares


def _siguiente(reserva, antes, actividad):
    frases = ['Tu pago sigue vigente: no tienes que pagar de nuevo.']
    if actividad == 'mar':
        habia = bool(getattr(antes, 'panga', '') or getattr(antes, 'capitan', ''))
        if habia and not _quitaron_algo(reserva, antes):
            frases.append('Tu capitán y tu panga siguen siendo los mismos.')
        else:
            frases.append('Te llega otro correo con tu capitán y tu panga en cuanto queden asignados.')
    frases.append('Si esta fecha no te funciona, escríbenos por WhatsApp con tu folio.')
    return ''.join(plantilla.parrafo(f, plantilla.TINTA, 16) for f in frases)


def _cuerpo_html(reserva, antes):
    actividad = plantilla.actividad_de(reserva)
    pendiente = _saldo_en_efectivo(reserva)
    dinero = ''
    if pendiente:
        dinero = plantilla.bloque_resto(
            f'Quedan {pendiente} {_html(reserva.moneda)} por liquidar en efectivo el día del viaje.')
    if reserva.servicio_id:
        producto = _html(reserva.servicio.nombre)
    else:
        producto = _html(reserva.paquete.nombre) if reserva.paquete_id else ''
    antes_texto = f' · antes {_vigente(antes)}' if _vigente(antes) else ''
    return plantilla.correo(
        actividad=actividad, empresa=_empresa_de(reserva), titulo='Reserva reagendada', folio=reserva.pk,
        producto=producto,
        previa=f'{_vigente(reserva)} · {hora_texto(reserva)}{antes_texto}',
        intro_html=f'Hola {_html(reserva.nombre_cliente)}, tu reserva quedó reagendada.',
        pares=_pares(reserva, antes, actividad), etiqueta_pares='Tu nueva fecha',
        dinero_html=dinero, siguiente_html=_siguiente(reserva, antes, actividad),
        con_garantias=(actividad == 'mar'),
    )


def _post_resend(cuerpo):
    """El POST a Resend. Propio de este correo: no se toca el de `services.py`."""
    respuesta = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
        json=cuerpo,
        timeout=TIMEOUT_SEGUNDOS,
    )
    respuesta.raise_for_status()


def enviar_correo_reagendado(reserva, antes):
    """Avisa al cliente de su nueva fecha. Devuelve True si se mando; nunca lanza.

    `antes` es como estaba la reserva (fecha, hora, inicio_paquete, fecha_salida, fecha_regreso y
    los nombres de la panga y el capitan). Si no se manda, `reserva.motivo_fallo_aviso` dice por que.
    """
    reserva.motivo_fallo_aviso = ''
    if not reserva.correo_cliente:
        reserva.motivo_fallo_aviso = 'la reserva no tiene correo del cliente'
        return False
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando el aviso de reagendado %s', reserva.pk)
        reserva.motivo_fallo_aviso = 'el envio de correos no esta configurado en el servidor'
        return False

    try:
        html = _cuerpo_html(reserva, antes)
        cuerpo = {
            'from': settings.RESEND_FROM,
            'to': [reserva.correo_cliente],
            'subject': _asunto(reserva),
            'html': html,
            'text': plantilla.a_texto(html),
        }
        if settings.RESEND_BCC:
            cuerpo['bcc'] = settings.RESEND_BCC
        _post_resend(cuerpo)
    except requests.RequestException as error:
        logger.exception('Fallo el aviso de reagendado de la reserva %s', reserva.pk)
        reserva.motivo_fallo_aviso = f'el proveedor de correo respondio: {motivo_para_persona(error)}'
        return False
    except Exception:  # noqa: BLE001 — contrato: este aviso jamas deshace un reagendado ya guardado
        logger.exception('No se pudo armar el aviso de reagendado de la reserva %s', reserva.pk)
        reserva.motivo_fallo_aviso = 'no se pudo armar el correo'
        return False
    return True
