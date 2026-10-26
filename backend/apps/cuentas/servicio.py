"""Reglas de la recuperacion de contrasena por codigo: pedir el codigo y confirmarlo.

Nada de lo que devuelven estas funciones distingue una cuenta que existe de una que no: el motivo real
vive solo en `EventoRecuperacion.resultado` (bitacora interna). Los limites se cuentan en la base de
datos y no en el cache porque el cache de produccion es de archivos y no es atomico entre procesos.
"""
import ipaddress
import logging
from dataclasses import dataclass
from datetime import timedelta
from functools import partial

from axes.utils import reset as axes_reset
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.notifications.services import enviar_correo_codigo_recuperacion, enviar_correo_contrasena_cambiada

from .envio import despachar
from .models import CodigoRecuperacion, EventoRecuperacion
from .seguridad import Secreto, coincide, generar_codigo, hash_codigo, hash_correo, normalizar_correo

logger = logging.getLogger(__name__)
User = get_user_model()

# Lo que se rechazo por limite no cuenta contra el limite: quien insiste mientras esta limitado no
# extiende su propio bloqueo ni el de la victima. Un envio fallido tampoco: ya conto como `enviado`.
RESULTADOS_QUE_NO_CUENTAN = ('limite_correo', 'limite_global', 'cooldown', 'envio_fallido')

# Usuario sin guardar para el HMAC de relleno: el camino de una cuenta inexistente hace el mismo
# trabajo criptografico que el de una real.
_USUARIO_RELLENO = User(pk=0, password='!')


def _ip_valida(ip):
    """La IP como texto normalizado, o None si no hay o no es una IP (la columna es GenericIPAddressField)."""
    try:
        return str(ipaddress.ip_address(str(ip).strip()))
    except ValueError:
        return None


def _registrar(tipo, resultado, usuario, correo_hash, ip, ahora):
    return EventoRecuperacion.objects.create(
        tipo=tipo, resultado=resultado, usuario=usuario, correo_hash=correo_hash, ip=ip, creado_en=ahora,
    )


def _solicitudes_de_ip(ip, ahora):
    return EventoRecuperacion.objects.filter(
        tipo=EventoRecuperacion.SOLICITUD, ip=ip, creado_en__gte=ahora - timedelta(hours=1),
    ).count()


def ip_excedida_solicitud(ip):
    """True si esta IP ya pidio demasiados codigos en la ultima hora (el 429 de la vista)."""
    ip = _ip_valida(ip)
    return bool(ip) and _solicitudes_de_ip(ip, timezone.now()) >= settings.RECUPERACION_MAX_POR_IP_HORA


def _limite_de_correo(correo_hash, ahora):
    """'cooldown', 'limite_correo' o None. Cuenta lo que se intento con ESE correo tecleado, exista o no."""
    previas = EventoRecuperacion.objects.filter(
        tipo=EventoRecuperacion.SOLICITUD, correo_hash=correo_hash,
    ).exclude(resultado__in=RESULTADOS_QUE_NO_CUENTAN)
    if previas.filter(creado_en__gt=ahora - timedelta(seconds=settings.RECUPERACION_COOLDOWN_SEGUNDOS)).exists():
        return 'cooldown'
    if previas.filter(creado_en__gte=ahora - timedelta(hours=1)).count() >= settings.RECUPERACION_MAX_POR_CORREO_HORA:
        return 'limite_correo'
    if previas.filter(creado_en__gte=ahora - timedelta(days=1)).count() >= settings.RECUPERACION_MAX_POR_CORREO_DIA:
        return 'limite_correo'
    return None


def _tope_global_alcanzado(ahora):
    enviados = EventoRecuperacion.objects.filter(
        tipo=EventoRecuperacion.SOLICITUD, resultado='enviado', creado_en__gte=ahora - timedelta(days=1),
    ).count()
    if enviados >= settings.RECUPERACION_MAX_ENVIOS_DIA:
        # Warning y no error: cada solicitud posterior al tope pasaria por aqui y un atacante agotaria la cuota de
        # Sentry. El tope tambien queda a la vista en la bitacora del admin.
        logger.warning('Se alcanzo el tope diario de correos de recuperacion (%s)', settings.RECUPERACION_MAX_ENVIOS_DIA)
        return True
    return False


def _enviar_codigo(usuario_pk, correo_hash, ip, destino, username, codigo):
    """Corre en el hilo de envio: manda el correo y, si no salio, lo deja en la bitacora."""
    try:
        enviado = enviar_correo_codigo_recuperacion(destino, username, codigo)
    except Exception as exc:  # excepcion deliberada: el mensaje o la traza podrian llevar el codigo
        logger.error('Fallo inesperado al enviar el codigo de recuperacion (%s)', type(exc).__name__)
        enviado = False
    if not enviado:
        EventoRecuperacion.objects.create(
            tipo=EventoRecuperacion.SOLICITUD, resultado='envio_fallido', usuario_id=usuario_pk,
            correo_hash=correo_hash, ip=ip, creado_en=timezone.now(),
        )


def solicitar_codigo(correo, ip):
    """Paso 1. Si el correo corresponde a UNA cuenta activa y recuperable, guarda el hash de un codigo
    nuevo y lo manda (despues del commit, en segundo plano). En cualquier otro caso no hace nada visible.

    Siempre devuelve None: la bitacora lleva el motivo, la respuesta no.
    """
    ahora = timezone.now()
    correo = normalizar_correo(correo)
    correo_hash = hash_correo(correo)
    ip = _ip_valida(ip)

    if not correo:
        # `email__iexact=''` coincidiria con TODAS las cuentas sin correo: ni se busca.
        _registrar(EventoRecuperacion.SOLICITUD, 'sin_correo', None, correo_hash, ip, ahora)
        return None

    # El limite por IP rechaza sin escribir: un cliente limitado no debe poder inflar la bitacora.
    if ip and _solicitudes_de_ip(ip, ahora) >= settings.RECUPERACION_MAX_POR_IP_HORA:
        return None

    motivo = _limite_de_correo(correo_hash, ahora)
    if not motivo and _tope_global_alcanzado(ahora):
        motivo = 'limite_global'
    if motivo:
        _registrar(EventoRecuperacion.SOLICITUD, motivo, None, correo_hash, ip, ahora)
        return None

    cuentas = list(User.objects.filter(email__iexact=correo)[:2])
    usuario = cuentas[0] if len(cuentas) == 1 else None
    if not cuentas:
        motivo = 'sin_cuenta'
    elif usuario is None:
        motivo = 'ambigua'
    elif not usuario.is_active:
        motivo = 'inactiva'
    elif not usuario.has_usable_password():
        # Una contrasena inutilizable es un bloqueo deliberado: recuperar lo reabriria.
        motivo = 'contrasena_inutilizable'

    if motivo:
        hash_codigo(_USUARIO_RELLENO, generar_codigo())
        _registrar(EventoRecuperacion.SOLICITUD, motivo, usuario, correo_hash, ip, ahora)
        return None

    with transaction.atomic():
        # El candado de la fila serializa dos peticiones simultaneas para la misma cuenta; se vuelven a
        # revisar los limites ya con el candado, o las dos pasarian el conteo a la vez.
        usuario = User.objects.select_for_update().get(pk=usuario.pk)
        motivo = _limite_de_correo(correo_hash, ahora)
        if motivo:
            _registrar(EventoRecuperacion.SOLICITUD, motivo, None, correo_hash, ip, ahora)
            return None
        codigo = generar_codigo()
        CodigoRecuperacion.objects.update_or_create(
            usuario=usuario,
            defaults={
                'codigo_hash': hash_codigo(usuario, codigo),
                'creado_en': ahora,
                'vence_en': ahora + timedelta(minutes=settings.RECUPERACION_CODIGO_MINUTOS),
                'intentos': 0,
                'consumido_en': None,
            },
        )
        _registrar(EventoRecuperacion.SOLICITUD, 'enviado', usuario, correo_hash, ip, ahora)
        transaction.on_commit(partial(
            despachar, _enviar_codigo, usuario.pk, correo_hash, ip, usuario.email, usuario.get_username(), codigo,
        ))
    return None


# ---------------------------------------------------------------------------
# Paso 2: confirmar
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Resultado:
    """Lo unico que sabe quien llama. Todo fallo de codigo es el mismo `Resultado(False)`; solo un error
    de la contrasena trae mensajes (y se da igual para cualquier correo, exista o no)."""

    exito: bool
    errores: tuple = ()


FALLO = Resultado(False)


def _fallos_de_ip(ip, ahora):
    return EventoRecuperacion.objects.filter(
        tipo=EventoRecuperacion.CONFIRMACION, ip=ip, creado_en__gte=ahora - timedelta(hours=1),
    ).exclude(resultado='exito').count()


def ip_excedida_confirmacion(ip):
    """True si esta IP ya acumulo demasiadas confirmaciones fallidas en la ultima hora (el 429 de la vista)."""
    ip = _ip_valida(ip)
    return bool(ip) and _fallos_de_ip(ip, timezone.now()) >= settings.RECUPERACION_MAX_FALLOS_IP_HORA


def _cuenta_recuperable(correo):
    """La unica cuenta activa y con contrasena utilizable de ese correo; None si no hay o hay varias."""
    cuentas = list(User.objects.filter(email__iexact=correo)[:2])
    if len(cuentas) == 1 and cuentas[0].is_active and cuentas[0].has_usable_password():
        return cuentas[0]
    return None


def _motivo_sin_intento(usuario, ahora):
    """Por que el UPDATE condicional no encontro un codigo que pueda recibir un intento (solo para la bitacora)."""
    fila = CodigoRecuperacion.objects.filter(usuario=usuario).first()
    if fila is None or fila.consumido_en is not None:
        return 'sin_codigo'
    if fila.vence_en <= ahora:
        return 'vencido'
    return 'agotado'


def _cerrar_sesiones(usuario):
    """Borra las filas de `Session` de esa cuenta. Cambiar la contrasena ya las invalida (Django compara el
    hash de la sesion en cada peticion); esto es higiene para que no queden en la tabla."""
    uid = str(usuario.pk)
    ids = [
        sesion.pk for sesion in Session.objects.filter(expire_date__gt=timezone.now()).iterator()
        if sesion.get_decoded().get('_auth_user_id') == uid
    ]
    Session.objects.filter(pk__in=ids).delete()


def confirmar_codigo(correo, codigo, password, ip):
    """Paso 2. Si el codigo es el vigente de esa cuenta, pone la contrasena nueva. Devuelve `Resultado`.

    Orden deliberado: 1) validar la contrasena ANTES de tocar el codigo y para cualquier correo, asi un
    error de validador ni distingue cuentas ni gasta un intento; 2) sumar el intento con un UPDATE
    condicional (maximo `RECUPERACION_MAX_INTENTOS` aunque lleguen cien peticiones a la vez);
    3) comparar en tiempo constante; 4) consumir el codigo con otro UPDATE condicional: solo quien
    actualiza una fila gana.
    """
    ahora = timezone.now()
    correo = normalizar_correo(correo)
    correo_hash = hash_correo(correo)
    ip = _ip_valida(ip)
    codigo = Secreto(codigo)
    usuario = _cuenta_recuperable(correo) if correo else None

    candidato = usuario or User(username=correo.split('@')[0], email=correo)
    try:
        validate_password(password, candidato)
    except ValidationError as error:
        _registrar(EventoRecuperacion.CONFIRMACION, 'password_rechazada', usuario, correo_hash, ip, ahora)
        return Resultado(False, tuple(error.messages))

    if usuario is None:
        hash_codigo(_USUARIO_RELLENO, codigo)  # mismo trabajo criptografico que una cuenta real
        _registrar(EventoRecuperacion.CONFIRMACION, 'sin_codigo', None, correo_hash, ip, ahora)
        return FALLO

    # Bloque 1: el intento se cuenta y se confirma (commit) aunque despues falle la comparacion.
    with transaction.atomic():
        sumados = CodigoRecuperacion.objects.filter(
            usuario=usuario, consumido_en__isnull=True, vence_en__gt=ahora,
            intentos__lt=settings.RECUPERACION_MAX_INTENTOS,
        ).update(intentos=F('intentos') + 1)
    if sumados == 0:
        _registrar(EventoRecuperacion.CONFIRMACION, _motivo_sin_intento(usuario, ahora), usuario, correo_hash, ip, ahora)
        return FALLO

    guardado = CodigoRecuperacion.objects.filter(usuario=usuario).values_list('codigo_hash', flat=True).first()

    # Bloque 2: comparar y, si acierta, consumir y cambiar la contrasena en una sola transaccion.
    with transaction.atomic():
        # Con el candado de la fila: si otra peticion ya cambio la contrasena, el hash se recalcula con
        # la nueva y la comparacion falla (un codigo esta atado a la contrasena vigente).
        bloqueado = User.objects.select_for_update().get(pk=usuario.pk)
        if not coincide(guardado, hash_codigo(bloqueado, codigo)):
            gano = False
        else:
            gano = CodigoRecuperacion.objects.filter(
                usuario=bloqueado, codigo_hash=guardado, consumido_en__isnull=True,
            ).update(consumido_en=ahora) == 1
        if gano:
            bloqueado.set_password(password)
            bloqueado.save(update_fields=['password'])
            _cerrar_sesiones(bloqueado)
            axes_reset(username=bloqueado.get_username())
            _registrar(EventoRecuperacion.CONFIRMACION, 'exito', bloqueado, correo_hash, ip, ahora)
            transaction.on_commit(partial(
                despachar, enviar_correo_contrasena_cambiada, bloqueado.email, bloqueado.get_username(),
                tuple(settings.RECUPERACION_AVISO_ADMIN),
            ))
    if not gano:
        _registrar(EventoRecuperacion.CONFIRMACION, 'codigo_incorrecto', usuario, correo_hash, ip, ahora)
        return FALLO
    return Resultado(True)
