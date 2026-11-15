"""Correo al cliente un dia antes del viaje, cuando pago anticipo y todavia debe el resto.

Lo manda el comando `recordar_saldos` (cron diario), no una pantalla. Mismo molde que el de
reagendado: la cara sale de `plantilla.correo`, los datos de una persona entran escapados con
`services._html` y `enviar_correo_recordatorio_saldo` nunca lanza; el motivo de un fallo queda
en `reserva.motivo_fallo_aviso`.

Dice cuanto queda y las dos formas de liquidarlo: en efectivo al llegar, o por transferencia
pidiendo los datos por WhatsApp. Los datos bancarios NO van en el correo a proposito (decision
del dueño): ese movimiento se acuerda por WhatsApp y la vendedora lo registra en la reserva.
El backend no conoce el numero publico de WhatsApp, asi que el correo no lleva enlace.
"""
import logging

import requests
from django.conf import settings

from . import plantilla
from .services import (
    TIMEOUT_SEGUNDOS,
    _empresa_de,
    _folio,
    _html,
    _par_punto_de_encuentro,
    _saldo_en_efectivo,
    motivo_para_persona,
)

logger = logging.getLogger(__name__)

TITULOS = {
    'mar': 'Mañana sales al mar',
    'traslado': 'Mañana es tu traslado',
    'estancia': 'Mañana empieza tu viaje',
}


def primer_dia(reserva):
    """El dia que el cliente llega: el inicio del paquete si lo hay, si no la fecha."""
    return reserva.inicio_paquete or reserva.fecha


def saldo_a_recordar(reserva):
    """Lo que falta por liquidar de una reserva con anticipo, o `None` si no debe nada."""
    return _saldo_en_efectivo(reserva)


def _monto(reserva, saldo):
    return f'{saldo:,.2f} {_html(reserva.moneda)}'


def _asunto(reserva, saldo):
    # El folio en el asunto: es lo que el cliente busca en su bandeja cuando necesita escribirnos.
    return f'Mañana es tu viaje{_folio(reserva)}: te quedan {saldo:,.2f} {reserva.moneda} por liquidar'


def _pares(reserva, actividad):
    pares = [('Día', plantilla.dia_largo(primer_dia(reserva)))]
    if reserva.hora:
        if actividad == 'mar':
            pares.append(
                ('Llega a las', plantilla.hora_12(plantilla.quince_antes(reserva.hora)) + ' (15 minutos antes)'))
        pares.append(('Hora de salida' if actividad == 'mar' else 'Hora', plantilla.hora_12(reserva.hora)))
    punto = _par_punto_de_encuentro(reserva, 'Sales de' if actividad == 'mar' else 'Punto de encuentro')
    if punto:
        pares.append(punto)
    pares.append(('Personas', str(reserva.numero_personas)))
    if reserva.capitan_id:
        pares.append(('Capitán', _html(reserva.capitan.nombre)))
    if reserva.embarcacion_id:
        pares.append(('Panga', _html(reserva.embarcacion.nombre)))
    return pares


def _dinero(reserva, saldo):
    return (
        plantilla.bloque_resto(f'Te quedan {_monto(reserva, saldo)} por liquidar.')
        + plantilla.parrafo(
            'Puedes pagarlos en efectivo mañana, al llegar. Si prefieres transferencia, '
            f'escríbenos por WhatsApp con tu folio #{reserva.pk} y te pasamos los datos.')
    )


def _siguiente(actividad):
    frases = []
    if actividad == 'mar':
        frases.append('Llega 15 minutos antes de la hora de salida.')
    frases.append('Si algo cambia de tu lado, escríbenos por WhatsApp y lo vemos.')
    return ''.join(plantilla.parrafo(frase, plantilla.TINTA, 16) for frase in frases)


def _cuerpo_html(reserva, saldo):
    actividad = plantilla.actividad_de(reserva)
    if reserva.servicio_id:
        producto = _html(reserva.servicio.nombre)
    else:
        producto = _html(reserva.paquete.nombre) if reserva.paquete_id else ''
    return plantilla.correo(
        actividad=actividad, empresa=_empresa_de(reserva), titulo=TITULOS.get(actividad, TITULOS['mar']),
        folio=reserva.pk, producto=producto,
        previa=f'Te quedan {saldo:,.2f} {reserva.moneda} por liquidar: en efectivo al llegar o por transferencia.',
        intro_html=f'Hola {_html(reserva.nombre_cliente)}, ya casi es el día.',
        pares=_pares(reserva, actividad), etiqueta_pares='Tu salida' if actividad == 'mar' else 'Tu viaje',
        dinero_html=_dinero(reserva, saldo), siguiente_html=_siguiente(actividad),
    )


def enviar_correo_recordatorio_saldo(reserva):
    """Le recuerda al cliente su saldo. Devuelve True si se mando; nunca lanza.

    Si no se manda, `reserva.motivo_fallo_aviso` dice por que.
    """
    reserva.motivo_fallo_aviso = ''
    saldo = saldo_a_recordar(reserva)
    if not saldo:
        reserva.motivo_fallo_aviso = 'la reserva ya no tiene saldo por liquidar'
        return False
    if not reserva.correo_cliente:
        reserva.motivo_fallo_aviso = 'la reserva no tiene correo del cliente'
        return False
    if not (settings.RESEND_API_KEY and settings.RESEND_FROM):
        logger.info('Resend sin configurar, no se mando el recordatorio de saldo %s', reserva.pk)
        reserva.motivo_fallo_aviso = 'el envio de correos no esta configurado en el servidor'
        return False

    try:
        html = _cuerpo_html(reserva, saldo)
        cuerpo = {
            'from': settings.RESEND_FROM,
            'to': [reserva.correo_cliente],
            'subject': _asunto(reserva, saldo),
            'html': html,
            'text': plantilla.a_texto(html),
        }
        if settings.RESEND_BCC:
            cuerpo['bcc'] = settings.RESEND_BCC
        respuesta = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}'},
            json=cuerpo,
            timeout=TIMEOUT_SEGUNDOS,
        )
        respuesta.raise_for_status()
    except requests.RequestException as error:
        logger.exception('Fallo el recordatorio de saldo de la reserva %s', reserva.pk)
        reserva.motivo_fallo_aviso = f'el proveedor de correo respondio: {motivo_para_persona(error)}'
        return False
    except Exception:  # noqa: BLE001 — contrato: un recordatorio caido no detiene los de las demas reservas
        logger.exception('No se pudo armar el recordatorio de saldo de la reserva %s', reserva.pk)
        reserva.motivo_fallo_aviso = 'no se pudo armar el correo'
        return False
    return True
