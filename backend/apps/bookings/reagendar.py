"""Reagendar una reserva ya pagada: mover su fecha (y hora) sin tocar lo que el cliente pago.

Decisiones en docs/architecture/ARCH-reagendar-reserva.md. Lo esencial:

- Este modulo NO tiene reglas de cupo propias. Asigna los campos nuevos, toma los candados en el orden de la
  confirmacion del pago y deja que `Reserva.full_clean()` y el motor de cupo decidan. Asi el formulario del admin,
  `/api/cupo/`, la Agenda y esta pantalla no pueden contradecirse.
- `proponer` (solo lectura, sin candados, para la vista previa) y `reagendar` (todo o nada, con candados) comparten
  las mismas funciones de validacion y de derivacion de fechas: lo que la vista previa promete es lo que el
  servicio hace.
- Precio, cobro e IVA no se tocan. La reserva se guarda COMPLETA (sin `update_fields`) porque las salidas de un
  paquete, los viajes de un traslado y las habitaciones de un hospedaje se resincronizan en `save()`.
- Dos excepciones al modelo, las dos solo en memoria y solo puestas aqui: `_excepcion_48h` (una persona autorizada
  dejo un motivo escrito) y `_reagendando` (un codigo promocional vencido despues de la compra no debe impedir mover
  la fecha de un viaje ya cobrado).
- Panga y capitan se conservan solo si siguen sirviendo el dia nuevo; si no, se quitan y se deja el aviso de
  asignacion por mandar. Los vehiculos de un traslado los suelta `sincronizar_viajes` al cambiar de dia.
- El correo al cliente sale en `transaction.on_commit`, nunca antes: el cliente no recibe una fecha que no quedo
  confirmada, y el candado de cupo no se sostiene mientras Resend responde.
"""
import copy
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, OperationalError, connection, models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from apps.fleet.calendario_paquete import fecha_ancla, fecha_salida as calcular_salida
from apps.fleet.enums import TipoServicio, TipoTraslado
from apps.fleet.models import EmbarcacionNoDisponible
from apps.notifications import plantilla
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Notificacion
from apps.tenancy.notificaciones import registrar_notificacion, sin_romper

from . import traslados
from .cupo import DemandaCupo, SinCupoError, bloquear_cupo, bloquear_recurso, obtener_contexto_cupo, obtener_estrategia
from .cupo.hospedaje_sync import hospedajes_de
from .models import (
    DIAS_BUSQUEDA_DISPONIBILIDAD, ESTADOS_QUE_OCUPAN_CUPO, HORAS_MINIMAS_CAMBIO_FECHA, Reserva, ViajeTransporte,
    _validar_cupo_de_paquete, _validar_cupo_hospedaje, disponibilidad_por_fecha, salida_aware,
)

logger = logging.getLogger(__name__)

ESTADOS_REAGENDABLES = (Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA)

DIAS_MAXIMOS_ADELANTE = 365
MOTIVO_MINIMO = 10
MOTIVO_MAXIMO = 200
SEGUNDOS_DE_ESPERA_POR_CANDADO = 5

# SQLSTATE de Postgres: 55P03 = el candado no se obtuvo en `lock_timeout`; 40P01 = deadlock.
SQLSTATE_CANDADO_NO_DISPONIBLE = '55P03'
SQLSTATE_DEADLOCK = '40P01'

MENSAJE_OCUPADO = (
    'El sistema está ocupado confirmando otras reservas de ese día. Intenta otra vez en unos segundos.'
)

# Campo del modelo en el que falla una validacion -> campo del formulario de la pantalla. Un campo que no esta aqui
# no se puede corregir desde la pantalla de reagendar y manda a la ficha.
CAMPOS_DE_LA_PANTALLA = {
    'fecha': 'nueva_fecha', 'fecha_salida': 'nueva_fecha', 'inicio_paquete': 'nueva_fecha', '__all__': 'nueva_fecha',
    'hora': 'nueva_hora', 'fecha_regreso': 'nueva_fecha_regreso',
}


class ErrorDeReagendado(Exception):
    """Algo impide reagendar. El mensaje esta escrito para quien opera, no para el log.

    `campo` es el campo del formulario donde debe mostrarse (`nueva_fecha`, `nueva_hora`, `nueva_fecha_regreso`,
    `motivo_excepcion`) o '' si es un error general. `codigo` distingue los que la pantalla trata distinto:
    `sin_cupo`, `token`, `ocupado`, `estado`, `excepcion_48h`, o '' para el resto.
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
class Propuesta:
    """Lo que pasaria si se reagendara, calculado sin tocar nada. La pantalla del paso 2 la pinta tal cual.

    `fecha` es el valor nuevo de `Reserva.fecha` (en un paquete, el dia de la actividad) e `inicio_paquete` la nueva
    llegada. `panga` y `capitan` son 'conserva' | 'quita' | None (None = la reserva no tenia). Un error de lo que se
    tecleo o de falta de cupo va en `errores` (campo -> mensaje); faltar menos de 48 h NO es un error: es
    `requiere_excepcion_48h`, y lo resuelve quien puede autorizar.
    """

    fecha: date | None = None
    hora: time | None = None
    inicio_paquete: date | None = None
    fecha_salida: date | None = None
    fecha_regreso: date | None = None
    dias_de_mar: list = field(default_factory=list)
    panga: str | None = None
    capitan: str | None = None
    motivo_panga: str = ''
    vehiculos_a_quitar: int = 0
    motivo_sin_cupo: str | None = None
    proxima_fecha: date | None = None
    requiere_excepcion_48h: bool = False
    limite_48h: datetime | None = None
    errores: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Resultado:
    """`panga_conservada` y `capitan_conservado`: True si los tenia y siguen, False si los tenia y se quitaron,
    None si no tenia."""

    reserva: Reserva
    antes: AntesDelCambio
    excepcion_48h: bool
    correo_encolado: bool
    panga_conservada: bool | None = None
    capitan_conservado: bool | None = None
    vehiculos_quitados: int = 0


@dataclass(frozen=True)
class _Fechas:
    """Los campos de fecha que `Reserva` tendria despues del cambio."""

    fecha: date
    hora: time | None
    inicio_paquete: date | None
    fecha_salida: date | None
    fecha_regreso: date | None  # solo el traslado redondo con aeropuerto; None en cualquier otro


@dataclass(frozen=True)
class _Entrada:
    """Lo tecleado ya validado, mas lo que de ahi se deduce."""

    hora: time | None
    regreso: date | None
    cambia_llegada: bool
    regreso_actual: date | None


@dataclass(frozen=True)
class _Recursos:
    panga: str | None
    capitan: str | None
    motivo: str


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
            # Un campo oculto manipulado ('2026-02-31', '25:00:00') no es un 500: queda como texto y no coincide.
            try:
                if clave in ('fecha', 'inicio_paquete'):
                    valor = parse_date(valor) if valor else None
                elif clave == 'hora':
                    valor = parse_time(valor) if valor else None
            except ValueError:
                pass
        if isinstance(valor, time):
            valor = valor.isoformat('seconds')
        elif isinstance(valor, date):
            valor = valor.isoformat()
        normalizado[clave] = '' if valor is None else str(valor)
    return normalizado


# ---------------------------------------------------------------------------------------------------------------
# Que tipo de reserva es (D12)
# ---------------------------------------------------------------------------------------------------------------

def _es_paquete(reserva):
    """Paquete de UNA empresa. Un componente de orden cruza-empresa ni siquiera llega aqui (`motivo_no_reagendable`)."""
    return bool(reserva.paquete_id) and not reserva.orden_id


def _es_hospedaje(reserva):
    return not reserva.paquete_id and bool(reserva.servicio_id) and reserva.servicio.estrategia_cupo == 'por_noche'


def _es_mar_suelto(reserva):
    """Pesca, paseo o safari sueltos, y la pesca anterior al catalogo (sin servicio): lo unico para lo que se
    sugiere la proxima fecha con lugar."""
    return not reserva.paquete_id and (not reserva.servicio_id or reserva.servicio.estrategia_cupo == 'por_recurso_dia')


def _es_de_mar(reserva):
    """Sale al mar: necesita panga y capitan y cuenta contra el cupo de pangas del dia."""
    if reserva.paquete_id:
        return any(
            ps.servicio.estrategia_cupo == 'por_recurso_dia'
            for ps in reserva.paquete.servicios_asociados.select_related('servicio')
        )
    return _es_mar_suelto(reserva)


def _regreso_de(reserva):
    """(fecha de regreso actual, si la reserva pide fecha de regreso, su DetalleTransporte).

    Solo el traslado `redondo_aeropuerto` tiene fecha de regreso propia; en los demas `pide` es False.
    """
    servicio = reserva.servicio if reserva.servicio_id else None
    if servicio is None or servicio.tipo_servicio != TipoServicio.TRANSPORTE:
        return None, False, None
    try:
        detalle = reserva.detalle_transporte
    except ObjectDoesNotExist:
        return None, False, None
    if detalle.tipo_traslado != TipoTraslado.REDONDO_AEROPUERTO:
        return None, False, detalle
    return detalle.fecha_regreso, True, detalle


def _fecha_texto(fecha, con_anio=True):
    """«martes 8 de diciembre de 2026», el formato de fecha que la pantalla y sus avisos usan en todos lados."""
    texto = f'{plantilla.DIAS[fecha.weekday()]} {fecha.day} de {plantilla.MESES[fecha.month - 1]}'
    return f'{texto} de {fecha.year}' if con_anio else texto


def _como_estaba(reserva, fecha_regreso):
    return AntesDelCambio(
        fecha=reserva.fecha,
        hora=reserva.hora,
        inicio_paquete=reserva.inicio_paquete,
        fecha_salida=reserva.fecha_salida,
        fecha_regreso=fecha_regreso,
        panga=reserva.embarcacion.nombre if reserva.embarcacion_id else '',
        capitan=reserva.capitan.nombre if reserva.capitan_id else '',
    )


# ---------------------------------------------------------------------------------------------------------------
# Lo tecleado: validaciones que comparten `proponer` y `reagendar`
# ---------------------------------------------------------------------------------------------------------------

def _validar_entrada(reserva, nueva_fecha, nueva_hora, nueva_fecha_regreso, hoy):
    """Errores de lo que tecleo la persona, antes de tocar nada. Lanza `ErrorDeReagendado`.

    En un paquete `nueva_fecha` es la nueva LLEGADA. Lo que ya estaba y no se mueve no se vuelve a juzgar: un
    cliente que ya llego y solo cambia su vuelo de regreso conserva su llegada (pasada) sin que eso sea un error.
    """
    if nueva_fecha is None:
        raise ErrorDeReagendado('Elige la nueva fecha.', 'nueva_fecha')
    hora = nueva_hora if nueva_hora is not None else reserva.hora
    regreso_actual, pide_regreso, _ = _regreso_de(reserva)
    regreso = nueva_fecha_regreso if pide_regreso else None
    if pide_regreso:
        if regreso is None:
            raise ErrorDeReagendado('Elige la fecha de regreso.', 'nueva_fecha_regreso')
        if regreso <= nueva_fecha:
            raise ErrorDeReagendado('La fecha de regreso debe ser posterior a la de llegada.', 'nueva_fecha_regreso')

    cambia_llegada = (nueva_fecha, hora) != (reserva.fecha_inicio_paquete, reserva.hora)
    cambia_regreso = pide_regreso and regreso != regreso_actual
    if not (cambia_llegada or cambia_regreso):
        raise ErrorDeReagendado('Elige una fecha u hora distinta de la actual.', 'nueva_fecha')
    if cambia_llegada:
        if nueva_fecha < hoy:
            raise ErrorDeReagendado('La nueva fecha ya pasó.', 'nueva_fecha')
        if nueva_fecha > hoy + timedelta(days=DIAS_MAXIMOS_ADELANTE):
            raise ErrorDeReagendado('La nueva fecha queda a más de un año. Revisa el año.', 'nueva_fecha')
    if cambia_regreso:
        if regreso < hoy:
            raise ErrorDeReagendado('La nueva fecha de regreso ya pasó.', 'nueva_fecha_regreso')
        if regreso > hoy + timedelta(days=DIAS_MAXIMOS_ADELANTE):
            raise ErrorDeReagendado('La fecha de regreso queda a más de un año. Revisa el año.', 'nueva_fecha_regreso')
    ventana = reserva.servicio.ventana_horaria() if reserva.servicio_id else None
    if nueva_hora is not None and ventana and not (ventana[0] <= nueva_hora <= ventana[1]):
        raise ErrorDeReagendado(
            f'La hora debe estar entre {ventana[0]:%H:%M} y {ventana[1]:%H:%M}.', 'nueva_hora',
        )
    return _Entrada(hora=hora, regreso=regreso, cambia_llegada=cambia_llegada, regreso_actual=regreso_actual)


def _derivar(reserva, nueva_fecha, entrada):
    """Las fechas que `Reserva` tendria con la llegada nueva (D12). La misma funcion para la vista previa y el guardado."""
    if _es_paquete(reserva):
        calendario = reserva.paquete.componentes_calendario()
        return _Fechas(
            fecha=fecha_ancla(nueva_fecha, calendario), hora=entrada.hora, inicio_paquete=nueva_fecha,
            fecha_salida=calcular_salida(nueva_fecha, calendario), fecha_regreso=None,
        )
    if _es_hospedaje(reserva):
        salida = nueva_fecha + timedelta(days=reserva.noches) if reserva.fecha_salida else None
        return _Fechas(
            fecha=nueva_fecha, hora=entrada.hora, inicio_paquete=None, fecha_salida=salida, fecha_regreso=None,
        )
    return _Fechas(
        fecha=nueva_fecha, hora=entrada.hora, inicio_paquete=reserva.inicio_paquete,
        fecha_salida=reserva.fecha_salida, fecha_regreso=entrada.regreso,
    )


def _poner(reserva, fechas):
    reserva.fecha = fechas.fecha
    reserva.hora = fechas.hora
    reserva.inicio_paquete = fechas.inicio_paquete
    reserva.fecha_salida = fechas.fecha_salida


# ---------------------------------------------------------------------------------------------------------------
# Regla de 48 horas
# ---------------------------------------------------------------------------------------------------------------

def _salida_afectada(reserva, entrada):
    """(fecha, hora) original MAS TEMPRANA de lo que se mueve: de ahi se miden las 48 horas.

    En un paquete es la llegada (lo primero que el cliente va a vivir), no el dia de la actividad. Si solo cambia
    el regreso de un traslado, es el regreso original: quien ya llego puede mover su vuelo de vuelta mientras
    ese vuelo siga lejos.
    """
    if entrada.cambia_llegada or entrada.regreso_actual is None:
        inicio = reserva.fecha_inicio_paquete
        return inicio, reserva.hora if inicio == reserva.fecha else None
    return entrada.regreso_actual, None


def _limite_de_48_horas(salida):
    return salida_aware(*salida) - timedelta(hours=HORAS_MINIMAS_CAMBIO_FECHA)


def _autorizar_48_horas(salida, puede_autorizar_48h, motivo_excepcion):
    """True si hizo falta la excepcion (y quedo autorizada); False si no hacia falta. Lanza si falta autorizacion."""
    if timezone.now() <= _limite_de_48_horas(salida):
        return False
    if not puede_autorizar_48h:
        original = f'{salida[0]} {salida[1]:%H:%M}' if salida[1] else f'{salida[0]}'
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


# ---------------------------------------------------------------------------------------------------------------
# Cupo
# ---------------------------------------------------------------------------------------------------------------

def _motivo_sin_cupo(reserva):
    """El texto del motor si `reserva` (con sus fechas nuevas ya puestas) no cabe; None si cabe. SOLO LEE.

    Es la rama de cupo de `Reserva.clean()` sin el candado: la vista previa no puede tomar candados (la
    transaccion de la peticion los sostendria hasta el final). Las funciones que llama ya existen y no bloquean
    (`_validar_cupo_de_paquete`, `_validar_cupo_hospedaje`); solo la del servicio de mar se repite aqui porque
    `validar_cupo_diario` toma el candado antes de contar. Igual que el modelo, no vuelve a pedir cupo si nada de
    lo que lo decide cambio (un cambio solo de hora).
    """
    if reserva._cupo_ya_validado():
        return None
    try:
        if reserva.paquete_id:
            _validar_cupo_de_paquete(reserva)
        elif reserva.servicio_id and reserva.servicio.estrategia_cupo == 'por_noche':
            _validar_cupo_hospedaje(reserva)
        elif reserva.servicio_id and reserva.servicio.estrategia_cupo == 'bajo_demanda':
            return None
        else:
            estrategia = reserva.servicio.estrategia_cupo if reserva.servicio_id else 'por_recurso_dia'
            contexto = obtener_contexto_cupo(reserva.fecha, reserva.empresa, excluir_pk=reserva.pk)
            obtener_estrategia(estrategia).validar(
                demanda=DemandaCupo(fecha=reserva.fecha, personas=reserva.numero_personas, excluir_pk=reserva.pk),
                grupos=contexto.grupos, capacidades=contexto.capacidades, tope=contexto.tope,
            )
    except ValidationError as exc:
        return ' '.join(exc.messages)
    return None


def _proxima_fecha(reserva, despues_de, fecha_actual):
    """Primer dia despues de `despues_de` en que cabe el grupo de `reserva`, o None. Solo servicio suelto de mar.

    No cuenta el lugar de la propia reserva (`excluir_pk`), asi que se salta su dia actual: ofrecer volver adonde
    ya esta no es una respuesta."""
    if not _es_mar_suelto(reserva):
        return None
    desde = despues_de + timedelta(days=1)
    estrategia = reserva.servicio.estrategia_cupo if reserva.servicio_id else 'por_recurso_dia'
    mapa = disponibilidad_por_fecha(
        desde, desde + timedelta(days=DIAS_BUSQUEDA_DISPONIBILIDAD - 1), reserva.numero_personas, reserva.empresa,
        estrategia_cupo=estrategia, excluir_pk=reserva.pk,
    )
    for fecha, motivo in sorted(mapa.items()):
        if motivo is None and fecha != fecha_actual:
            return fecha
    return None


def _con_proxima_fecha(texto, proxima):
    if proxima is None:
        return texto
    texto = texto.rstrip()
    if not texto.endswith('.'):
        texto += '.'
    return f'{texto} La próxima fecha con lugar es el {_fecha_texto(proxima)}.'


def _tomar_candados(reserva, dias_de_mar):
    """D10, pasos 2 y 3: los dias de mar NUEVOS en orden de fecha y luego las habitaciones por `pk`.

    El mismo orden que la confirmacion del pago (`confirmacion.py`) y `sincronizar_ocupaciones`, para que dos
    operaciones a la vez no se esperen una a la otra en circulo. Cierra ademas un hueco: un paquete de un solo
    dia de mar evalua su cupo (`_validar_cupo_de_paquete`) sin candado."""
    for dia in dias_de_mar:
        bloquear_cupo(reserva.empresa_id, dia)
    for servicio, *_ in hospedajes_de(reserva):
        for recurso in servicio.recursos.filter(activo=True).order_by('pk'):
            bloquear_recurso(reserva.empresa_id, recurso.pk)


# ---------------------------------------------------------------------------------------------------------------
# Panga, capitan y vehiculos (D4)
# ---------------------------------------------------------------------------------------------------------------

def _dias_de_mar(reserva):
    """Los dias en que `reserva` (con sus fechas nuevas ya puestas) usa panga, en orden; [] si no sale al mar."""
    if not _es_de_mar(reserva):
        return []
    return sorted(set(reserva._fechas_de_viaje()))


def _evaluar_recursos(reserva, dias):
    """Si su panga y su capitan siguen sirviendo en `dias`. SOLO LEE.

    Panga: activa, que alcance para el grupo, que no este fuera de servicio (`EmbarcacionNoDisponible`, que
    `Reserva.clean()` NO mira: solo la Agenda lo filtra) y que ningun otro viaje que ocupa cupo la use ese dia.
    Capitan: que ningun otro viaje lo tenga ese dia. Son las mismas condiciones que `_validar_una_salida_por_dia`
    y la lista de pangas de la Agenda; se evaluan por separado porque se pueden quitar por separado.
    """
    panga = reserva.embarcacion if reserva.embarcacion_id else None
    capitan = reserva.capitan if reserva.capitan_id else None
    if not dias or (panga is None and capitan is None):
        return _Recursos(None if panga is None else 'conserva', None if capitan is None else 'conserva', '')

    motivos_panga, motivos_capitan = [], []
    if panga is not None:
        if not panga.activa:
            motivos_panga.append(f'La panga {panga.nombre} ya no está activa.')
        if reserva.numero_personas > panga.capacidad_maxima:
            motivos_panga.append(
                f'La panga {panga.nombre} lleva hasta {panga.capacidad_maxima} personas y la reserva es para '
                f'{reserva.numero_personas}.'
            )
        fuera = EmbarcacionNoDisponible.objects.filter(
            empresa_id=reserva.empresa_id, embarcacion_id=panga.pk, fecha__in=dias,
        ).order_by('fecha').values_list('fecha', flat=True)
        for dia in fuera:
            motivos_panga.append(f'La panga {panga.nombre} no sale el {_fecha_texto(dia, con_anio=False)}.')
    for dia in dias:
        del_dia = Reserva.objects.filter(
            models.Q(fecha=dia) | models.Q(salidas__fecha=dia),
            estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa_id=reserva.empresa_id,
        ).exclude(pk=reserva.pk).distinct()
        if panga is not None and del_dia.filter(embarcacion_id=panga.pk).exists():
            motivos_panga.append(f'La panga {panga.nombre} ya tiene un viaje el {_fecha_texto(dia, con_anio=False)}.')
        if capitan is not None and del_dia.filter(capitan_id=capitan.pk).exists():
            motivos_capitan.append(
                f'El capitán {capitan.nombre} ya tiene un viaje el {_fecha_texto(dia, con_anio=False)}.'
            )
    return _Recursos(
        panga=None if panga is None else ('quita' if motivos_panga else 'conserva'),
        capitan=None if capitan is None else ('quita' if motivos_capitan else 'conserva'),
        motivo=' '.join(motivos_panga + motivos_capitan),
    )


def _viajes_con_vehiculo(reserva):
    """[(pk, sentido, fecha)] de los tramos que tienen un vehiculo asignado."""
    return list(reserva.viajes_transporte.filter(vehiculo__isnull=False).values_list('pk', 'sentido', 'fecha'))


def _vehiculos_a_quitar(reserva, detalle, con_vehiculo):
    """Cuantos de esos tramos cambiarian de dia (o desaparecerian) con las fechas nuevas ya puestas en `reserva`.

    Usa los tramos que `sincronizar_viajes` va a pedir, no una cuenta aparte: asi la vista previa no puede decir
    una cosa y el guardado hacer otra."""
    if not con_vehiculo:
        return 0
    if _es_paquete(reserva):
        deseados = traslados._tramos_de_paquete(reserva)
    else:
        deseados = traslados._tramos_de_servicio_de_transporte(reserva, detalle)
    if deseados is None:
        return 0
    return sum(1 for _, sentido, fecha in con_vehiculo if sentido not in deseados or deseados[sentido]['fecha'] != fecha)


# ---------------------------------------------------------------------------------------------------------------
# Vista previa
# ---------------------------------------------------------------------------------------------------------------

def proponer(reserva, *, nueva_fecha, nueva_hora=None, nueva_fecha_regreso=None, hoy=None):
    """Que pasaria si se reagendara `reserva`, sin tocar nada y sin candados (solo para mostrarlo).

    No es una garantia: entre esta vista previa y la confirmacion alguien puede llenar el dia. La garantia la da
    `reagendar`, que bloquea y revalida. Nunca modifica `reserva` (la pantalla sigue mostrando su «Antes»): trabaja
    sobre una copia.
    """
    hoy = hoy or timezone.localdate()
    motivo = motivo_no_reagendable(reserva)
    if motivo:
        return Propuesta(errores={'general': motivo})
    try:
        entrada = _validar_entrada(reserva, nueva_fecha, nueva_hora, nueva_fecha_regreso, hoy)
    except ErrorDeReagendado as exc:
        return Propuesta(errores={exc.campo or 'general': exc.mensaje})

    fechas = _derivar(reserva, nueva_fecha, entrada)
    limite = _limite_de_48_horas(_salida_afectada(reserva, entrada))

    copia = copy.copy(reserva)
    _poner(copia, fechas)
    dias = _dias_de_mar(copia)
    recursos = _evaluar_recursos(copia, dias)

    detalle = copy.copy(_regreso_de(reserva)[2])
    if detalle is not None and fechas.fecha_regreso is not None:
        detalle.fecha_regreso = fechas.fecha_regreso
    quitar = _vehiculos_a_quitar(copia, detalle, _viajes_con_vehiculo(reserva))

    errores, motivo_sin_cupo, proxima = {}, _motivo_sin_cupo(copia), None
    if motivo_sin_cupo:
        proxima = _proxima_fecha(copia, fechas.fecha, reserva.fecha)
        errores['nueva_fecha'] = _con_proxima_fecha(motivo_sin_cupo, proxima)
    return Propuesta(
        fecha=fechas.fecha, hora=fechas.hora, inicio_paquete=fechas.inicio_paquete, fecha_salida=fechas.fecha_salida,
        fecha_regreso=fechas.fecha_regreso, dias_de_mar=dias, panga=recursos.panga, capitan=recursos.capitan,
        motivo_panga=recursos.motivo, vehiculos_a_quitar=quitar, motivo_sin_cupo=motivo_sin_cupo,
        proxima_fecha=proxima, requiere_excepcion_48h=timezone.now() > limite, limite_48h=limite, errores=errores,
    )


# ---------------------------------------------------------------------------------------------------------------
# Guardado
# ---------------------------------------------------------------------------------------------------------------

def _es_sin_cupo(exc):
    """`exc` (o algo anidado en ella) lleva el codigo `sin_cupo` que todo rechazo de cupo del sistema lleva."""
    if getattr(exc, 'code', None) == 'sin_cupo':
        return True
    hijos = [error for lista in getattr(exc, 'error_dict', {}).values() for error in lista]
    hijos += getattr(exc, 'error_list', [])
    return any(hijo is not exc and _es_sin_cupo(hijo) for hijo in hijos)


def _error_de_validacion(exc, reserva):
    """Traduce una `ValidationError` del modelo al error que la pantalla sabe mostrar.

    Lo que falla en un campo de fecha u hora se muestra junto a su campo; lo que falla en un dato que esta pantalla
    no deja corregir (un telefono viejo, por ejemplo) nombra el campo y manda a la ficha."""
    codigo = 'sin_cupo' if _es_sin_cupo(exc) else ''
    errores = getattr(exc, 'error_dict', None)
    if errores is None:
        return ErrorDeReagendado(' '.join(exc.messages), 'nueva_fecha', codigo)
    de_la_pantalla = {campo: lista for campo, lista in errores.items() if campo in CAMPOS_DE_LA_PANTALLA}
    if de_la_pantalla:
        campo = next(iter(de_la_pantalla))
        mensaje = ' '.join(m for lista in de_la_pantalla.values() for m in ValidationError(lista).messages)
        return ErrorDeReagendado(mensaje, CAMPOS_DE_LA_PANTALLA[campo], codigo)
    campo, lista = next(iter(errores.items()))
    try:
        etiqueta = str(reserva._meta.get_field(campo).verbose_name)
    except FieldDoesNotExist:  # el error viene de otro modelo (p. ej. el detalle del traslado): se nombra tal cual
        etiqueta = campo
    mensaje = ' '.join(ValidationError(lista).messages).rstrip('.')
    return ErrorDeReagendado(
        f'No se puede guardar porque la reserva tiene un dato inválido en {etiqueta}: {mensaje}. '
        'Corrígelo en la ficha.',
    )


def _sqlstate(exc):
    causa = exc.__cause__ or exc
    return getattr(causa, 'sqlstate', None) or getattr(causa, 'pgcode', None)


def reagendar(
    reserva_pk, *, nueva_fecha, nueva_hora, nueva_fecha_regreso, token, usuario, puede_autorizar_48h,
    motivo_excepcion, avisar_cliente,
):
    """Mueve la reserva a la nueva fecha (y hora) y devuelve un `Resultado`. Todo o nada.

    `puede_autorizar_48h` lo decide quien llama (jefe u operador de plataforma); aqui solo se exige ademas un
    motivo escrito. Lanza `ErrorDeReagendado` y no deja nada a medias.

    Un candado que no se obtiene en `SEGUNDOS_DE_ESPERA_POR_CANDADO` o un deadlock con otra operacion se
    reintenta UNA vez (el deadlock) y despues se le dice a la persona que intente de nuevo, como `crear-pago`.
    """
    for intento in range(2):
        try:
            return _reagendar_en_transaccion(
                reserva_pk, nueva_fecha=nueva_fecha, nueva_hora=nueva_hora, nueva_fecha_regreso=nueva_fecha_regreso,
                token=token, usuario=usuario, puede_autorizar_48h=puede_autorizar_48h,
                motivo_excepcion=motivo_excepcion, avisar_cliente=avisar_cliente,
            )
        except OperationalError as exc:
            sqlstate = _sqlstate(exc)
            if sqlstate == SQLSTATE_DEADLOCK and intento == 0:
                logger.warning('Deadlock al reagendar la reserva %s; se reintenta.', reserva_pk)
                continue
            if sqlstate in (SQLSTATE_CANDADO_NO_DISPONIBLE, SQLSTATE_DEADLOCK):
                raise ErrorDeReagendado(MENSAJE_OCUPADO, codigo='ocupado') from exc
            raise


def _reagendar_en_transaccion(
    reserva_pk, *, nueva_fecha, nueva_hora, nueva_fecha_regreso, token, usuario, puede_autorizar_48h,
    motivo_excepcion, avisar_cliente,
):
    with transaction.atomic():
        if connection.vendor == 'postgresql':
            # Sin esto un candado ocupado nos dejaria esperando sin limite a la peticion entera.
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL lock_timeout = '{SEGUNDOS_DE_ESPERA_POR_CANDADO}s'")

        # D10, paso 1: la fila primero y sin joins. `from_db` toma sus "originales" de esta fila ya bloqueada.
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

        entrada = _validar_entrada(reserva, nueva_fecha, nueva_hora, nueva_fecha_regreso, timezone.localdate())
        excepcion = _autorizar_48_horas(_salida_afectada(reserva, entrada), puede_autorizar_48h, motivo_excepcion)

        regreso_actual, _, detalle = _regreso_de(reserva)
        antes = _como_estaba(reserva, regreso_actual)
        con_vehiculo = [pk for pk, _, _ in _viajes_con_vehiculo(reserva)]
        fechas = _derivar(reserva, nueva_fecha, entrada)
        _poner(reserva, fechas)
        if detalle is not None and fechas.fecha_regreso is not None:
            detalle.fecha_regreso = fechas.fecha_regreso

        dias = _dias_de_mar(reserva)
        _tomar_candados(reserva, dias)

        # Con los candados ya tomados: lo que ahora sirve, sirve hasta el commit.
        recursos = _evaluar_recursos(reserva, dias)
        if recursos.panga == 'quita':
            reserva.embarcacion = None
        if recursos.capitan == 'quita':
            reserva.capitan = None
        if 'quita' in (recursos.panga, recursos.capitan):
            # Sin esto, la reasignacion de despues nunca le mandaria al cliente el correo con su capitan
            # (`signals._le_toca_aviso`): el sistema creeria que ya se lo mando.
            reserva.aviso_asignacion_enviado_en = None

        reserva._reagendando = True
        reserva._excepcion_48h = excepcion
        # Un correo en blanco es un dato viejo que no impide mover la fecha (se avisa por WhatsApp); lo demas si.
        excluir = [] if reserva.correo_cliente else ['correo_cliente']
        cambia_detalle = detalle is not None and fechas.fecha_regreso is not None
        try:
            reserva.full_clean(exclude=excluir)
            if cambia_detalle:
                detalle.full_clean()
            reserva.save()
            if cambia_detalle:
                detalle.save()
        except ValidationError as exc:
            error = _error_de_validacion(exc, reserva)
            if error.codigo == 'sin_cupo' and error.campo == 'nueva_fecha':
                proxima = _proxima_fecha(reserva, fechas.fecha, antes.fecha)
                error = ErrorDeReagendado(_con_proxima_fecha(error.mensaje, proxima), error.campo, error.codigo)
            raise error from exc
        except SinCupoError as exc:
            raise ErrorDeReagendado(str(exc), 'nueva_fecha', 'sin_cupo') from exc
        except IntegrityError as exc:
            # La restriccion EXCLUDE de habitaciones: otra venta se quedo con ese lugar entre la revision y el guardado.
            raise ErrorDeReagendado(
                'Ya no hay lugar en esas fechas: otra reserva se quedó con él mientras se guardaba. '
                'Elige otra fecha.', 'nueva_fecha', 'sin_cupo',
            ) from exc

        vehiculos_quitados = (
            len(con_vehiculo)
            - ViajeTransporte.objects.filter(pk__in=con_vehiculo, vehiculo__isnull=False).count()
        ) if con_vehiculo else 0

        correo_encolado = bool(avisar_cliente and reserva.correo_cliente)
        if correo_encolado:
            pk, empresa_id = reserva.pk, reserva.empresa_id
            usuario_id = getattr(usuario, 'pk', None)
            transaction.on_commit(lambda: _mandar_correo(pk, antes, usuario_id, empresa_id))

    logger.info(
        'Reserva %s reagendada por el usuario %s (excepcion 48 h: %s).',
        reserva_pk, getattr(usuario, 'pk', None), excepcion,
    )
    return Resultado(
        reserva=reserva, antes=antes, excepcion_48h=excepcion, correo_encolado=correo_encolado,
        panga_conservada=None if recursos.panga is None else recursos.panga == 'conserva',
        capitan_conservado=None if recursos.capitan is None else recursos.capitan == 'conserva',
        vehiculos_quitados=vehiculos_quitados,
    )


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
