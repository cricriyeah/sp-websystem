"""Crea/actualiza los grupos 'Jefe', 'Vendedora' y 'OperadorPlataforma' con los
permisos de docs/contexto-negocio.md (seccion 5, Roles y permisos) mas los
ajustes de la expansion multi-sede (ver plan Pieza 1, Revision 8, H5).
Idempotente: correr de nuevo solo sincroniza permisos.

Debe correr ANTES de manage.py migrar_la_paz_a_empresa: ese comando asume
que estos tres grupos ya existen.
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

PERMISOS_VENDEDORA = [
    ('bookings', 'orden', ['view']),
    ('bookings', 'reserva', ['add', 'change', 'view']),
    ('bookings', 'agenda', ['change', 'view']),
    ('bookings', 'cupodiario', ['add', 'change', 'view']),
    ('bookings', 'checkoutabandonado', ['view']),
    ('bookings', 'vendedora', ['view']),
    ('bookings', 'detalletransporte', ['view', 'add', 'change']),
    ('fleet', 'embarcacion', ['view']),
    ('fleet', 'capitan', ['view']),
    ('fleet', 'puntoencuentro', ['view']),
    ('fleet', 'paquete', ['view']),
    ('bookings', 'reservapersonalizacion', ['view']),
    ('fleet', 'embarcacionnodisponible', ['add', 'change', 'delete', 'view']),
    ('bookings', 'viajetransporte', ['view', 'change']),
    ('fleet', 'vehiculo', ['view']),
    ('fleet', 'vehiculonodisponible', ['add', 'change', 'delete', 'view']),
    # Vista y edición de su propio usuario (con queryset acotado a sí misma en el admin)
    ('auth', 'user', ['view', 'change']),
    # Notificaciones del backoffice: solo ver. Las crea `avisar()`, las borra el cron de retención y «marcar como
    # leídas» escribe la lectura de la propia persona (se gatea con este permiso).
    ('tenancy', 'notificacion', ['view']),
]

# Todo lo que Vendedora no tiene: borrar, y el catalogo financiero completo
# (antes reservado a is_superuser=True). 'payments' no tiene modelos propios
# en el admin -- el cobro se opera via Stripe, no via CRUD local -- por eso
# no hay fila aparte para esa app.
PERMISOS_JEFE = PERMISOS_VENDEDORA + [
    ('bookings', 'reserva', ['delete']),
    ('bookings', 'cupodiario', ['delete']),
    ('bookings', 'vendedora', ['add', 'change', 'delete']),
    ('bookings', 'detalletransporte', ['delete']),
    ('fleet', 'embarcacion', ['add', 'change', 'delete']),
    ('fleet', 'capitan', ['add', 'change', 'delete']),
    ('fleet', 'puntoencuentro', ['add', 'change', 'delete']),
    ('fleet', 'vehiculo', ['add', 'change', 'delete']),
    ('fleet', 'transportetarifa', ['add', 'change', 'delete', 'view']),
    ('fleet', 'codigopromocional', ['add', 'change', 'delete', 'view']),
    # Catalogo multi-sede: el jefe configura sus propios servicios, recursos,
    # personalizaciones y paquetes (RLS los acota a su Empresa).
    ('fleet', 'servicio', ['add', 'change', 'delete', 'view']),
    ('fleet', 'recurso', ['add', 'change', 'delete', 'view']),
    ('fleet', 'personalizacion', ['add', 'change', 'delete', 'view']),
    ('fleet', 'serviciopersonalizacion', ['add', 'change', 'delete', 'view']),
    ('fleet', 'paquete', ['add', 'change', 'delete', 'view']),
    ('fleet', 'paqueteservicio', ['add', 'change', 'delete', 'view']),
    # Ocupaciones y componentes: los pone el sistema al confirmar el pago; el
    # jefe solo los consulta.
    ('bookings', 'reservaocupacion', ['view']),
    ('bookings', 'reservapaquetecomponente', ['view']),
]


PERMISOS_OPERADOR = PERMISOS_JEFE + [
    ('auth', 'user', ['add', 'delete']),
    ('auth', 'group', ['add', 'change', 'delete', 'view']),
    ('tenancy', 'sede', ['add', 'change', 'delete', 'view']),
    ('tenancy', 'empresa', ['add', 'change', 'delete', 'view']),
    ('tenancy', 'membresiaempresa', ['add', 'change', 'delete', 'view']),
]


class Command(BaseCommand):
    help = "Crea/actualiza los grupos 'Jefe', 'Vendedora' y 'OperadorPlataforma'."

    def handle(self, *args, **options):
        vendedora = self._grupo('Vendedora', PERMISOS_VENDEDORA)
        jefe = self._grupo('Jefe', PERMISOS_JEFE)
        operador = self._grupo('OperadorPlataforma', PERMISOS_OPERADOR)
        self.stdout.write(self.style.SUCCESS(
            f"Grupos listos: Vendedora ({vendedora.permissions.count()}), "
            f"Jefe ({jefe.permissions.count()}), "
            f"OperadorPlataforma ({operador.permissions.count()})."
        ))

        from apps.tenancy.roles import sincronizar_todos

        total_sync = sincronizar_todos()
        self.stdout.write(self.style.SUCCESS(
            f"Usuarios sincronizados: {total_sync}."
        ))

    def _grupo(self, nombre, permisos):
        group, _ = Group.objects.get_or_create(name=nombre)
        perms, vistos = [], set()
        for app_label, modelo, acciones in permisos:
            ct = ContentType.objects.get(app_label=app_label, model=modelo)
            for accion in acciones:
                clave = (app_label, modelo, accion)
                if clave in vistos:
                    continue
                vistos.add(clave)
                perms.append(Permission.objects.get(content_type=ct, codename=f'{accion}_{modelo}'))
        group.permissions.set(perms)
        return group
