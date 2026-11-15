"""Le recuerda su saldo, un dia antes del viaje, a quien pago anticipo y todavia debe el resto.

Para un cron diario en Render, a media manana de la sede (16:00 UTC = 9:00 en America/Mazatlan):

    python manage.py recordar_saldos

Que reservas: `pagada` o `asignada`, con forma de pago `anticipo`, sin reembolso, con saldo
mayor a cero y cuyo primer dia (inicio del paquete, o la fecha) es MAÑANA en la zona horaria de
su sede. Una orden cruza-empresa nunca entra: siempre se paga completa.

Una sola vez por reserva: `Reserva.recordatorio_saldo_enviado_en` se sella con un `UPDATE`
condicional ANTES de mandar (dos corridas a la vez no mandan dos correos) y se suelta si el
correo no salio, para que una corrida posterior del mismo dia lo reintente. Reagendar a otro dia
lo borra (`reagendar.py`): la fecha nueva merece su recordatorio.

Corre con el rol de la app (sin BYPASSRLS): las candidatas se leen con alcance de operador y cada
reserva se procesa en el alcance de SU empresa, en su propia transaccion, para que un fallo a la
mitad no deshaga los sellos de los correos que ya salieron.

Un correo que no sale (sin correo del cliente, Resend caido) deja una notificacion de error en el
backoffice de la empresa: alguien tiene que avisarle por WhatsApp.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.notifications.correo_recordatorio_saldo import (
    enviar_correo_recordatorio_saldo,
    primer_dia,
    saldo_a_recordar,
)
from apps.tenancy import scope
from apps.tenancy.models import Notificacion
from apps.tenancy.notificaciones import registrar_notificacion


def reservas_por_recordar(ahora=None):
    """Las reservas a las que hoy les toca el recordatorio. Leer dentro de un alcance que las vea."""
    ahora = ahora or timezone.now()
    # Prefiltro ancho en UTC; el «mañana» exacto se decide abajo con la zona de cada sede.
    hoy_utc = ahora.date()
    dias = [hoy_utc + timedelta(days=n) for n in (0, 1, 2)]
    candidatas = Reserva.objects.filter(
        estado__in=[Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA],
        forma_pago=Reserva.FormaPago.ANTICIPO,
        reembolsada=False,
        orden__isnull=True,
        recordatorio_saldo_enviado_en__isnull=True,
    ).filter(
        Q(inicio_paquete__in=dias) | Q(inicio_paquete__isnull=True, fecha__in=dias),
    ).select_related('empresa__sede', 'servicio', 'paquete', 'capitan', 'embarcacion').order_by('pk')

    por_recordar = []
    for reserva in candidatas:
        manana = ahora.astimezone(ZoneInfo(reserva.empresa.sede.zona_horaria)).date() + timedelta(days=1)
        if primer_dia(reserva) == manana and saldo_a_recordar(reserva):
            por_recordar.append(reserva)
    return por_recordar


class Command(BaseCommand):
    help = 'Manda el recordatorio de saldo a las reservas con anticipo que viajan mañana.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo lista; no manda ni sella nada.')

    def handle(self, *args, dry_run=False, **opciones):
        with scope.como_operador_plataforma():
            reservas = reservas_por_recordar()

        if dry_run:
            for reserva in reservas:
                self.stdout.write(
                    f'#{reserva.pk} {reserva.empresa.slug} {primer_dia(reserva)} '
                    f'saldo {saldo_a_recordar(reserva)} {reserva.moneda}')
            self.stdout.write(f'{len(reservas)} recordatorio(s) por mandar (dry-run, no se mando nada).')
            return

        enviados = fallidos = 0
        for reserva in reservas:
            with scope.con_empresa(reserva.empresa):
                resultado = self._recordar(reserva)
            if resultado is True:
                enviados += 1
            elif resultado is False:
                fallidos += 1
        self.stdout.write(f'{enviados} recordatorio(s) de saldo enviados, {fallidos} sin enviar.')

    def _recordar(self, reserva):
        """True si salio, False si no salio, None si otra corrida ya lo tenia."""
        pendientes = Reserva.objects.filter(pk=reserva.pk, recordatorio_saldo_enviado_en__isnull=True)
        if not pendientes.update(recordatorio_saldo_enviado_en=timezone.now()):
            return None
        if enviar_correo_recordatorio_saldo(reserva):
            return True

        Reserva.objects.filter(pk=reserva.pk).update(recordatorio_saldo_enviado_en=None)
        registrar_notificacion(
            reserva.empresa, Notificacion.Nivel.ERROR,
            f'No se pudo recordar su saldo a {reserva.nombre_cliente} (reserva #{reserva.pk}, viaja mañana). '
            'Avísale por WhatsApp.',
            motivo=getattr(reserva, 'motivo_fallo_aviso', ''),
            enlace_url=reverse('admin:bookings_reserva_change', args=[reserva.pk]),
            enlace_texto='Abrir reserva',
        )
        return False
