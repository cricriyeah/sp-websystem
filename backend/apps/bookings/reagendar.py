"""Reagendar una reserva ya pagada: mover su fecha (y hora) sin tocar lo que el cliente pago.

Decisiones en docs/architecture/ARCH-reagendar-reserva.md. Lo esencial:

- Este modulo NO tiene reglas de cupo propias. Asigna los campos nuevos, toma los candados en el orden de la
  confirmacion del pago y deja que `Reserva.full_clean()` y el motor de cupo decidan. Asi el formulario del admin,
  `/api/cupo/`, la Agenda y esta pantalla no pueden contradecirse.
- Precio, cobro e IVA no se tocan. La reserva se guarda COMPLETA (sin `update_fields`) porque las salidas de un
  paquete, los viajes de un traslado y las habitaciones de un hospedaje se resincronizan en `save()`.
- Dos excepciones al modelo, las dos solo en memoria y solo puestas aqui: `_excepcion_48h` (una persona autorizada
  dejo un motivo escrito) y `_reagendando` (un codigo promocional vencido despues de la compra no debe impedir mover
  la fecha de un viaje ya cobrado).
- El correo al cliente sale en `transaction.on_commit`, nunca antes: el cliente no recibe una fecha que no quedo
  confirmada, y el candado de cupo no se sostiene mientras Resend responde.
"""
import logging
from dataclasses import dataclass
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from apps.tenancy import scope
from apps.tenancy.models import Empresa, Notificacion
from apps.tenancy.notificaciones import registrar_notificacion, sin_romper

from .models import HORAS_MINIMAS_CAMBIO_FECHA, Reserva, salida_aware

logger = logging.getLogger(__name__)

ESTADOS_REAGENDABLES = (Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA)

DIAS_MAXIMOS_ADELANTE = 365
MOTIVO_MINIMO = 10
MOTIVO_MAXIMO = 200
SEGUNDOS_DE_ESPERA_POR_CANDADO = 5

MENSAJE_OCUPADO = (
    'El sistema está ocupado confirmando otras reservas de ese día. Intenta otra vez en unos segundos.'
)


class ErrorDeReagendado(Exception):
    """Algo impide reagendar. El mensaje esta escrito para quien opera, no para el log.

    `campo` es el campo del formulario donde debe mostrarse (`nueva_fecha`, `nueva_hora`, `nueva_fecha_regreso`,
    `motivo_excepcion`) o '' si es un error general. `codigo` distingue los que la pantalla trata distinto:
    `sin_cupo`, `token`, `ocupado`, `estado`, `excepcion_48h`, `' '` para el resto.
    """

    def __init__(self, mensaje, campo='', codigo=''):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.campo = campo
        self.codigo = codigo


@dataclass(frozen=True)
class AntesDelCambio:
    """Como estaba la reserva antes de moverla. Datos planos: viaja al correo y al callback de despues del commit.

    `panga` y `capitan` son nombres ('' si no tenia). El modulo de correo lo recibe por duck-typing.
    """

    fecha: date
    hora: time | None
    inicio_paquete: date | None
    fecha_salida: date | None
    fecha_regreso: date | None
    panga: str
    capitan: str


@dataclass(frozen=True)
class Resultado:
    reserva: Reserva
    antes: AntesDelCambio
    excepcion_48h: bool
    correo_encolado: bool


def motivo_no_reagendable(reserva):
    """'' si se puede reagendar; si no, el texto en español de por que no."""
    if reserva.estado not in ESTADOS_REAGENDABLES:
        estado = reserva.get_estado_display()
        return (
            f'Esta reserva está {estado[:1].lower()}{estado[1:]}: solo se reagendan reservas pagadas o asignadas.'
        )
    if reserva.orden_id:
        return (
            'Esta reserva es parte de un paquete de varias empresas. El cambio se coordina con las dos empresas; '
            'aquí no se puede.'
        )
    if reserva.en_disputa:
        return 'Esta reserva está en disputa con el banco. Espera a que Stripe resuelva.'
    return ''


def puede_reagendarse(reserva):
    return motivo_no_reagendable(reserva) == ''


def token_de(reserva):
    """Lo que la pantalla vio de la reserva. Se compara contra la fila bloqueada antes de cambiar nada.

    No es `actualizado_en`: asignar una panga lo mueve y no cambia lo que se esta revisando. Texto plano para que
    viaje en campos ocultos de un formulario."""
    return {
        'fecha': reserva.fecha.isoformat(),
        'hora': reserva.hora.isoformat('seconds') if reserva.hora else '',
        'inicio_paquete': reserva.inicio_paquete.isoformat() if reserva.inicio_paquete else '',
        'estado': str(reserva.estado),
    }


def _normalizar_token(token):
    """El mismo token con fechas y horas en su forma canonica ('06:00' y '06:00:00' son la misma hora)."""
    token = token or {}
    normalizado = {}
    for clave in ('fecha', 'hora', 'inicio_paquete', 'estado'):
        valor = token.get(clave, '')
        if isinstance(valor, str):
            valor = valor.strip()
            if clave in ('fecha', 'inicio_paquete'):
                valor = parse_date(valor) if valor else None
            elif clave == 'hora':
                valor = parse_time(valor) if valor else None
        if isinstance(valor, time):
            valor = valor.isoformat('seconds')
        elif isinstance(valor, date):
            valor = valor.isoformat()
        normalizado[clave] = '' if valor is None else str(valor)
    return normalizado


def _como_estaba(reserva):
    return AntesDelCambio(
        fecha=reserva.fecha,
        hora=reserva.hora,
        inicio_paquete=reserva.inicio_paquete,
        fecha_salida=reserva.fecha_salida,
        fecha_regreso=None,
        panga=reserva.embarcacion.nombre if reserva.embarcacion_id else '',
        capitan=reserva.capitan.nombre if reserva.capitan_id else '',
    )


def _limite_de_48_horas(reserva):
    """El momento a partir del cual ya no se puede mover sin autorizacion: 48 h antes de la salida original."""
    return salida_aware(reserva.fecha, reserva.hora) - timedelta(hours=HORAS_MINIMAS_CAMBIO_FECHA)


def _validar_entrada(reserva, nueva_fecha, nueva_hora, hoy):
    """Errores de lo que tecleo la persona, antes de tocar nada. Lanza `ErrorDeReagendado`."""
    if nueva_fecha is None:
        raise ErrorDeReagendado('Elige la nueva fecha.', 'nueva_fecha')
    hora = nueva_hora if nueva_hora is not None else reserva.hora
    if (nueva_fecha, hora) == (reserva.fecha, reserva.hora):
        raise ErrorDeReagendado('Elige una fecha u hora distinta de la actual.', 'nueva_fecha')
    if nueva_fecha < hoy:
        raise ErrorDeReagendado('La nueva fecha ya pasó.', 'nueva_fecha')
    if nueva_fecha > hoy + timedelta(days=DIAS_MAXIMOS_ADELANTE):
        raise ErrorDeReagendado('La nueva fecha queda a más de un año. Revisa el año.', 'nueva_fecha')
    ventana = reserva.servicio.ventana_horaria() if reserva.servicio_id else None
    if nueva_hora is not None and ventana and not (ventana[0] <= nueva_hora <= ventana[1]):
        raise ErrorDeReagendado(
            f'La hora debe estar entre {ventana[0]:%H:%M} y {ventana[1]:%H:%M}.', 'nueva_hora',
        )
    return hora


def _autorizar_48_horas(reserva, puede_autorizar_48h, motivo_excepcion):
    """True si hizo falta la excepcion (y quedo autorizada); False si no hacia falta. Lanza si falta autorizacion."""
    if timezone.now() <= _limite_de_48_horas(reserva):
        return False
    if not puede_autorizar_48h:
        original = f'{reserva.fecha} {reserva.hora}' if reserva.hora else f'{reserva.fecha}'
        raise ErrorDeReagendado(
            f'El cambio de fecha requiere al menos {HORAS_MINIMAS_CAMBIO_FECHA} horas de anticipación sobre la '
            f'salida original ({original}). Pídele a un jefe que lo autorice.',
            'nueva_fecha', 'excepcion_48h',
        )
    motivo = (motivo_excepcion or '').strip()
    if not MOTIVO_MINIMO <= len(motivo) <= MOTIVO_MAXIMO:
        raise ErrorDeReagendado(
            f'Faltan menos de {HORAS_MINIMAS_CAMBIO_FECHA} horas para la salida. Escribe el motivo de la '
            f'excepción, de {MOTIVO_MINIMO} a {MOTIVO_MAXIMO} caracteres.',
            'motivo_excepcion', 'excepcion_48h',
        )
    return True


def reagendar(
    reserva_pk, *, nueva_fecha, nueva_hora, nueva_fecha_regreso, token, usuario, puede_autorizar_48h,
    motivo_excepcion, avisar_cliente,
):
    """Mueve la reserva a la nueva fecha (y hora) y devuelve un `Resultado`. Todo o nada.

    `puede_autorizar_48h` lo decide quien llama (jefe u operador de plataforma); aqui solo se exige ademas un
    motivo escrito. Lanza `ErrorDeReagendado` y no deja nada a medias.
    """
    with transaction.atomic():
        reserva = Reserva.objects.select_for_update().filter(pk=reserva_pk).first()
        if reserva is None:
            raise ErrorDeReagendado('No se encontró la reserva.', codigo='estado')
        motivo = motivo_no_reagendable(reserva)
        if motivo:
            raise ErrorDeReagendado(motivo, codigo='estado')
        if _normalizar_token(token) != _normalizar_token(token_de(reserva)):
            ahora = f'{reserva.fecha} {reserva.hora}' if reserva.hora else f'{reserva.fecha}'
            raise ErrorDeReagendado(
                f'Esta reserva cambió mientras la revisabas (ahora: {ahora}). Revisa y vuelve a elegir.',
                codigo='token',
            )

        hoy = timezone.localdate()
        hora = _validar_entrada(reserva, nueva_fecha, nueva_hora, hoy)
        excepcion = _autorizar_48_horas(reserva, puede_autorizar_48h, motivo_excepcion)

        antes = _como_estaba(reserva)
        reserva.fecha = nueva_fecha
        reserva.hora = hora
        reserva._reagendando = True
        reserva._excepcion_48h = excepcion
        try:
            reserva.full_clean()
            reserva.save()
        except ValidationError as exc:
            raise ErrorDeReagendado(' '.join(exc.messages), 'nueva_fecha') from exc

        correo_encolado = bool(avisar_cliente and reserva.correo_cliente)
        if correo_encolado:
            pk, empresa_id = reserva.pk, reserva.empresa_id
            usuario_id = getattr(usuario, 'pk', None)
            transaction.on_commit(lambda: _mandar_correo(pk, antes, usuario_id, empresa_id))

    logger.info(
        'Reserva %s reagendada por el usuario %s (excepcion 48 h: %s).',
        reserva_pk, getattr(usuario, 'pk', None), excepcion,
    )
    return Resultado(reserva=reserva, antes=antes, excepcion_48h=excepcion, correo_encolado=correo_encolado)


def _mandar_correo(reserva_pk, antes, usuario_id, empresa_id):
    """Corre despues del COMMIT, ya fuera de la pantalla. Nunca lanza: el cambio de fecha ya quedo."""
    try:
        empresa = Empresa.objects.get(pk=empresa_id)
        with scope.con_empresa(empresa):
            reserva = Reserva.objects.select_related(
                'servicio', 'paquete', 'capitan', 'embarcacion', 'empresa',
            ).filter(pk=reserva_pk).first()
            if reserva is None:
                return
            actor = get_user_model().objects.filter(pk=usuario_id).first() if usuario_id else None
            enviado, motivo = _enviar_correo(reserva, antes)
            _dejar_constancia(empresa, reserva, enviado, motivo, actor)
    except Exception as exc:
        logger.error('Fallo el correo de reagendado de la reserva %s (%s).', reserva_pk, type(exc).__name__)


def _enviar_correo(reserva, antes):
    """(enviado, motivo). El modulo de correo se importa aqui, ya en el callback: no se necesita para reagendar."""
    try:
        from apps.notifications.correo_reagendado import enviar_correo_reagendado

        if enviar_correo_reagendado(reserva, antes):
            return True, ''
        return False, getattr(reserva, 'motivo_fallo_aviso', '') or 'el correo no salió'
    except Exception as exc:
        logger.error('Fallo al armar el correo de reagendado de la reserva %s (%s).', reserva.pk, type(exc).__name__)
        return False, 'ocurrió un error inesperado al armar o mandar el correo'


@sin_romper
def _dejar_constancia(empresa, reserva, enviado, motivo, actor):
    """Escribe en el feed como termino el correo. Corre dentro del `con_empresa` que `_mandar_correo` reabrio."""
    enlace = reverse('admin:bookings_reserva_change', args=[reserva.pk])
    if enviado:
        registrar_notificacion(
            empresa, Notificacion.Nivel.EXITO, f'Correo de reagendado enviado a {reserva.nombre_cliente}.',
            tipo=Notificacion.Tipo.CAMBIO_FECHA, actor=actor, enlace_url=enlace, enlace_texto='Ver reserva',
        )
    else:
        registrar_notificacion(
            empresa, Notificacion.Nivel.ERROR,
            f'No se pudo enviar el correo de reagendado a {reserva.nombre_cliente}. La nueva fecha sí quedó '
            'guardada; avísale por WhatsApp.',
            tipo=Notificacion.Tipo.CAMBIO_FECHA, motivo=motivo, actor=actor,
            enlace_url=enlace, enlace_texto='Ver reserva',
        )
