"""Crea/actualiza el grupo 'Vendedora' con los permisos de docs/contexto-negocio.md
(seccion 5, Roles y permisos). Idempotente: correr de nuevo solo sincroniza permisos.

Los jefes NO usan un grupo: son cuentas Django is_superuser=True (ven/editan todo).
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea/actualiza el grupo 'Vendedora' con permisos operativos (sin acceso financiero)."

    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name='Vendedora')

        permisos = [
            # Reservas: vista operativa completa. Sin delete (se cancela, no se borra).
            ('bookings', 'reserva', ['add', 'change', 'view']),
            # Agenda: repartir panga y capitan de los viajes ya vendidos. Es un
            # proxy de Reserva y por eso tiene permisos propios. Sin add ni
            # delete: una reserva se crea vendiendo y se cancela, no se inventa
            # ni se borra desde la agenda.
            ('bookings', 'agenda', ['change', 'view']),
            # Cupo diario: puede cerrar/reducir el dia cuando falten embarcaciones.
            ('bookings', 'cupodiario', ['add', 'change', 'view']),
            # Checkouts abandonados: lista de recuperacion, solo lectura (el proxy
            # de Reserva no se edita ni se borra a mano, ver CheckoutAbandonadoAdmin).
            ('bookings', 'checkoutabandonado', ['view']),
            # Vendedoras: solo consulta, para tener a la mano su propio codigo de
            # link (?ref=). Darlas de alta o cambiar codigos es cosa de jefes.
            ('bookings', 'vendedora', ['view']),
            # Catalogo de flota: solo consulta, para asignar embarcacion/capitan.
            ('fleet', 'embarcacion', ['view']),
            ('fleet', 'capitan', ['view']),
            # Que panga no sale un dia (mantenimiento, motor). Es trabajo diario
            # suyo, no de los jefes. Con delete a proposito: si marco una fuera
            # por error, o el motor se arreglo antes, tiene que poder deshacerlo
            # — no es un registro historico, es el estado de un dia.
            ('fleet', 'embarcacionnodisponible', ['add', 'change', 'delete', 'view']),
            # fleet.Tarifa deliberadamente fuera: es informacion financiera, solo jefes.
        ]

        perms = []
        for app_label, modelo, acciones in permisos:
            ct = ContentType.objects.get(app_label=app_label, model=modelo)
            for accion in acciones:
                perms.append(Permission.objects.get(content_type=ct, codename=f'{accion}_{modelo}'))

        group.permissions.set(perms)

        self.stdout.write(self.style.SUCCESS(
            f"Grupo 'Vendedora' listo con {len(perms)} permisos."
        ))
