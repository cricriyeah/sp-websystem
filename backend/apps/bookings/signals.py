"""Cuando una reserva queda con panga Y capitan, el cliente se entera solo.

Vive en una señal y no en el admin porque la asignacion ocurre en dos lugares
distintos de esa pantalla —el formulario de una reserva y la edicion en linea de
la agenda— y manana podria ocurrir desde una API. La regla del negocio es una;
el codigo que la aplica, tambien.

Nada de lo que pasa aqui puede tumbar el guardado: el reparto de la agenda es
trabajo de operacion y no se cae porque Resend este caido.
"""
import logging
import threading

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from apps.notifications.services import enviar_correo_asignacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Notificacion
from apps.tenancy.notificaciones import registrar_notificacion, sin_romper

from .models import DetalleTransporte, Reserva

logger = logging.getLogger(__name__)

# El correo sale al confirmar la transaccion, ya fuera de la pantalla que guardo. Aqui queda lo que paso para que
# esa pantalla se lo diga a quien asigno (ver `AvisoDeAsignacionMixin` en admin.py). Va por hilo: cada peticion
# del admin corre completa en uno, y el tope evita que crezca si el aviso sale desde un lugar sin pantalla.
_resultados = threading.local()
TOPE_DE_RESULTADOS = 50


def _anotar_resultado(reserva, enviado, motivo=''):
    lista = getattr(_resultados, 'lista', None)
    if lista is None:
        lista = _resultados.lista = []
    if len(lista) < TOPE_DE_RESULTADOS:
        lista.append({
            'reserva_pk': reserva.pk, 'cliente': reserva.nombre_cliente, 'correo': reserva.correo_cliente,
            'enviado': enviado, 'motivo': motivo,
        })


def tomar_resultados_de_aviso():
    """Los resultados de aviso de este hilo desde la ultima vez, y los borra."""
    lista = getattr(_resultados, 'lista', None) or []
    _resultados.lista = []
    return lista


def _le_toca_aviso(reserva):
    """`estado == asignada` NO sirve como condicion: poner solo la panga ya hace
    esa transicion, y entonces el correo anunciaria un capitan que no existe."""
    if not (reserva.embarcacion_id and reserva.capitan_id):
        return False
    if reserva.aviso_asignacion_enviado_en is not None:
        return False
    if reserva.estado == Reserva.Estado.CANCELADA:
        return False
    # Reasignar un viaje pasado para cuadrar la contabilidad es normal; avisarle
    # al cliente del capitan de un viaje que ya ocurrio, no.
    return reserva.fecha >= timezone.localdate()


@receiver(post_save, dispatch_uid='bookings.aviso_asignacion')
def avisar_asignacion(sender, instance, **kwargs):
    # Sin `sender=Reserva` a proposito: Django manda la senal con la clase proxy como emisor, y la pantalla
    # «Asignar pangas» guarda a traves del proxy `Agenda`. Con `sender=Reserva` el aviso nunca salia al asignar
    # panga y capitan desde ahi. El isinstance cubre a Reserva y a cualquier proxy suyo.
    if not isinstance(instance, Reserva):
        return
    if not _le_toca_aviso(instance):
        return
    # SET LOCAL muere al COMMIT: el callback no puede depender del alcance de la
    # transaccion que lo encolo (ver "Quien corre fuera del alcance" del plan de
    # expansion multi-sede). Se captura el entero, no el objeto, y se re-resuelve
    # todo -- Reserva incluida -- dentro de un con_empresa nuevo al ejecutarse.
    empresa_id = instance.empresa_id
    # Quien guardo, si lo hizo una persona desde el admin (`AvisoDeAsignacionMixin.save_model` lo anota): para que
    # la notificacion diga quien asigno. Un entero, no el objeto: el callback corre despues del commit.
    actor_id = getattr(instance, '_asignado_por_id', None)
    transaction.on_commit(lambda: _mandar(instance.pk, empresa_id, actor_id))


@sin_romper
def _dejar_constancia(empresa, reserva, enviado, motivo, actor):
    """Escribe en el feed de notificaciones como termino el correo de asignacion. Corre dentro del `con_empresa` que
    `_mandar` reabrio (el alcance de la transaccion que encolo el callback ya murio con su COMMIT) y nunca lanza.

    Es la UNICA via confiable de decirle a alguien que paso con el correo: sale despues de que la pantalla que pidio la
    asignacion ya respondio (el COMMIT que lo dispara es el de la peticion entera, no el de la vista), asi que el
    aviso verde/rojo de esa pantalla no lo alcanza (ver `AvisoDeAsignacionMixin`)."""
    enlace = reverse('admin:bookings_reserva_change', args=[reserva.pk])
    if enviado:
        registrar_notificacion(
            empresa, Notificacion.Nivel.EXITO,
            f'Panga y capitán asignados. Correo enviado a {reserva.nombre_cliente}.',
            tipo=Notificacion.Tipo.ASIGNACION, actor=actor, enlace_url=enlace, enlace_texto='Ver reserva',
        )
    else:
        registrar_notificacion(
            empresa, Notificacion.Nivel.ERROR,
            f'No se pudo enviar el correo de asignación a {reserva.nombre_cliente}. La asignación sí quedó '
            'guardada; avísale por WhatsApp.',
            tipo=Notificacion.Tipo.ASIGNACION, motivo=motivo, actor=actor,
            enlace_url=enlace, enlace_texto='Ver reserva',
        )


def _mandar(reserva_pk, empresa_id, actor_id=None):
    empresa = Empresa.objects.get(pk=empresa_id)
    with scope.con_empresa(empresa):
        try:
            reserva = Reserva.objects.select_related('capitan', 'embarcacion').get(pk=reserva_pk)
        except Reserva.DoesNotExist:
            return
        actor = get_user_model().objects.filter(pk=actor_id).first() if actor_id else None

        try:
            enviado = enviar_correo_asignacion(reserva)
        except Exception:
            logger.exception('Fallo el aviso de asignacion de la reserva %s', reserva.pk)
            motivo = 'ocurrio un error inesperado al armar o mandar el correo (queda en el registro)'
            _anotar_resultado(reserva, False, motivo)
            _dejar_constancia(empresa, reserva, False, motivo, actor)
            return

        # Solo se marca si de verdad salio: si Resend estaba caido, el siguiente
        # guardado de esa reserva lo reintenta en vez de darlo por hecho.
        if not enviado:
            motivo = getattr(reserva, 'motivo_fallo_aviso', '') or 'el correo no salio'
            _anotar_resultado(reserva, False, motivo)
            _dejar_constancia(empresa, reserva, False, motivo, actor)
            return

        Reserva.objects.filter(pk=reserva.pk).update(aviso_asignacion_enviado_en=timezone.now())
        _anotar_resultado(reserva, True)
        _dejar_constancia(empresa, reserva, True, '', actor)


@receiver(post_delete, sender=DetalleTransporte, dispatch_uid='bookings.detalle_transporte_post_delete')
def borrar_viajes_al_borrar_detalle(sender, instance, **kwargs):
    """Borrar el DetalleTransporte borra los viajes de transporte de esa reserva (spec §5)."""
    reserva_id = getattr(instance, 'reserva_id', None)
    if reserva_id:
        from apps.bookings.traslados import borrar_viajes_reserva_seguro

        borrar_viajes_reserva_seguro(reserva_id)

