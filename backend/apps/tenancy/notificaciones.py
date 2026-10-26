"""Notificaciones persistentes del backoffice: la API que usan los procesos para dejar constancia de lo que paso.

Diseno completo y decisiones en docs/architecture/ARCH-notificaciones-backoffice.md. Lo esencial:

- `avisar(request, ...)`: desde una vista del admin. Muestra el aviso verde/ambar/rojo de Django Y guarda la
  `Notificacion`. Es la unica funcion que hace las dos cosas.
- `registrar_notificacion(empresa, ...)`: desde un disparador sin pantalla (senal, webhook, hilo). Solo guarda, y
  debe llamarse DENTRO del `scope.con_empresa(empresa)` que esos disparadores ya reabren.
- Ambas escriben EN LINEA en la transaccion y el alcance que esten activos: nada de `transaction.on_commit`
  aqui adentro. `SET LOCAL` muere en el COMMIT y un INSERT en un callback sin alcance cae en cero filas en
  silencio bajo RLS (el bug N1 de `scope.py`). Si la accion hace rollback, la notificacion de exito se deshace
  con ella: no se afirma un exito que no ocurrio.
- NUNCA rompen la accion del usuario: atrapan cualquier excepcion, la registran y devuelven `None`.
"""
import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, OuterRef

from . import scope
from .models import LecturaNotificacion, Notificacion

logger = logging.getLogger(__name__)

_NIVEL_A_MESSAGE = {
    Notificacion.Nivel.EXITO: messages.SUCCESS,
    Notificacion.Nivel.AVISO: messages.WARNING,
    Notificacion.Nivel.ERROR: messages.ERROR,
}

TOPE_NO_LEIDAS = 99


def _recortar(texto, largo):
    """Cabe en la columna: un motivo largo de Stripe o un nombre enorme no debe hacer que se pierda el aviso."""
    texto = str(texto or '')
    return texto if len(texto) <= largo else texto[: largo - 1] + '…'


def enlace_seguro(url):
    """Solo rutas del propio admin. El enlace se pinta como href en la lista y en el JS; un esquema como
    `javascript:` o un dominio ajeno nunca debe llegar ahi, venga de donde venga."""
    url = str(url or '')
    if (len(url) > 300 or not url.startswith('/') or url.startswith('//')
            or '\\' in url or any(ord(c) <= 0x20 or ord(c) == 0x7f for c in url)):
        return ''
    return url


def registrar_notificacion(empresa, nivel, texto, *, tipo=Notificacion.Tipo.OTRO, motivo='', actor=None,
                           enlace_url='', enlace_texto=''):
    """Guarda UNA notificacion en la transaccion y el alcance actuales. Nunca lanza: regresa `None` si no pudo.

    El `INSERT` va en su propio savepoint. Sin el, en Postgres un rechazo (RLS sin alcance, un valor que no cabe)
    deja abortada la transaccion de quien llama: la excepcion se atrapa aqui, pero el `COMMIT` de la accion del
    usuario (asignar, cobrar, reembolsar) se convierte en un `ROLLBACK` silencioso.

    No registra el texto en el log: trae datos del cliente y el log va a Sentry.
    """
    if empresa is None:
        logger.warning('Notificacion sin empresa, no se guarda (tipo=%s).', tipo)
        return None
    try:
        with transaction.atomic():
            return Notificacion.objects.create(
                empresa=empresa, nivel=nivel, tipo=tipo,
                texto=_recortar(texto, 300), motivo=_recortar(motivo, 300), actor=actor,
                enlace_url=enlace_seguro(enlace_url), enlace_texto=_recortar(enlace_texto, 40),
            )
    except Exception:
        logger.exception(
            'No se pudo guardar la notificacion (empresa=%s, tipo=%s, nivel=%s).',
            getattr(empresa, 'pk', None), tipo, nivel,
        )
        return None


def avisar(request, nivel, texto, *, empresa=None, tipo=Notificacion.Tipo.OTRO, motivo='', enlace_url='',
           enlace_texto='', mensaje=None):
    """Dice lo que paso (aviso de Django) y lo deja guardado (notificacion). Nunca rompe la accion del usuario.

    `request=None` (flujo sin pantalla): solo guarda, y `empresa` es obligatoria. Con `request` la empresa sale del
    alcance activo; el operador de plataforma no tiene empresa activa, asi que quien lo llama pasa `empresa=` (la
    de la reserva) o la notificacion no se guarda.

    `mensaje` es el texto de PANTALLA cuando debe ser distinto del guardado (por ejemplo, un parrafo de instrucciones
    que no tiene sentido en el feed). Por omision la pantalla dice lo mismo que se guarda: texto + motivo.
    """
    if mensaje is None:
        mensaje = f'{texto} {motivo}'.strip() if motivo else texto
    try:
        if request is not None and hasattr(request, '_messages'):
            messages.add_message(request, _NIVEL_A_MESSAGE.get(nivel, messages.INFO), mensaje)
        if empresa is None and request is not None:
            empresa = scope.empresa_actual(request)
        actor = getattr(request, 'user', None)
        if actor is not None and getattr(actor, 'is_anonymous', True):
            actor = None
    except Exception:
        logger.exception('Fallo al preparar la notificacion (tipo=%s).', tipo)
        return None
    return registrar_notificacion(
        empresa, nivel, texto, tipo=tipo, motivo=motivo, actor=actor,
        enlace_url=enlace_url, enlace_texto=enlace_texto,
    )


def _del_alcance(request):
    """Las notificaciones que la persona puede ver: las de su empresa, o todas si es operador de plataforma.

    RLS ya acota en Postgres; el filtro explicito es para sqlite (sin RLS) y como segunda barrera."""
    qs = Notificacion.objects.all()
    empresa = scope.empresa_actual(request)
    if empresa is not None:
        return qs.filter(empresa=empresa)
    if scope.es_operador_plataforma(request.user):
        return qs
    return qs.none()


def contar_no_leidas(request, tope=TOPE_NO_LEIDAS):
    """No leidas de ESTA persona en su alcance. Devuelve como mucho `tope + 1` (100 se pinta «99+») para no
    contar miles. 0 sin sesion o sin permiso de ver notificaciones."""
    user = getattr(request, 'user', None)
    if user is None or user.is_anonymous or not user.has_perm('tenancy.view_notificacion'):
        return 0
    ya_leida = LecturaNotificacion.objects.filter(notificacion=OuterRef('pk'), usuario=user)
    sin_leer = _del_alcance(request).annotate(_leida=Exists(ya_leida)).filter(_leida=False)
    return sin_leer.order_by().values('pk')[: tope + 1].count()


def marcar_leidas(usuario, notificaciones):
    """Crea la lectura de `usuario` para cada notificacion del iterable. Idempotente (`ignore_conflicts` sobre la
    restriccion unica): dos clics no duplican. Solo escribe lecturas del propio `usuario`."""
    filas = [
        LecturaNotificacion(empresa_id=n.empresa_id, notificacion_id=n.pk, usuario=usuario)
        for n in notificaciones
    ]
    LecturaNotificacion.objects.bulk_create(filas, ignore_conflicts=True)
