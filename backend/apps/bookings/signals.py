"""Cuando una reserva queda con panga Y capitan, el cliente se entera solo.

Vive en una señal y no en el admin porque la asignacion ocurre en dos lugares
distintos de esa pantalla —el formulario de una reserva y la edicion en linea de
la agenda— y manana podria ocurrir desde una API. La regla del negocio es una;
el codigo que la aplica, tambien.

Nada de lo que pasa aqui puede tumbar el guardado: el reparto de la agenda es
trabajo de operacion y no se cae porque Resend este caido.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.notifications.services import enviar_correo_asignacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa

from .models import Reserva

logger = logging.getLogger(__name__)


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


@receiver(post_save, sender=Reserva, dispatch_uid='bookings.aviso_asignacion')
def avisar_asignacion(sender, instance, **kwargs):
    if not _le_toca_aviso(instance):
        return
    # SET LOCAL muere al COMMIT: el callback no puede depender del alcance de la
    # transaccion que lo encolo (ver "Quien corre fuera del alcance" del plan de
    # expansion multi-sede). Se captura el entero, no el objeto, y se re-resuelve
    # todo -- Reserva incluida -- dentro de un con_empresa nuevo al ejecutarse.
    empresa_id = instance.empresa_id
    transaction.on_commit(lambda: _mandar(instance.pk, empresa_id))


def _mandar(reserva_pk, empresa_id):
    empresa = Empresa.objects.get(pk=empresa_id)
    with scope.con_empresa(empresa):
        try:
            reserva = Reserva.objects.select_related('capitan', 'embarcacion').get(pk=reserva_pk)
        except Reserva.DoesNotExist:
            return

        try:
            enviado = enviar_correo_asignacion(reserva)
        except Exception:
            logger.exception('Fallo el aviso de asignacion de la reserva %s', reserva.pk)
            return

        # Solo se marca si de verdad salio: si Resend estaba caido, el siguiente
        # guardado de esa reserva lo reintenta en vez de darlo por hecho.
        if not enviado:
            return

        Reserva.objects.filter(pk=reserva.pk).update(aviso_asignacion_enviado_en=timezone.now())
