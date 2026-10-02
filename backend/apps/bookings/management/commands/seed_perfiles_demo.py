"""Siembra en LOCAL un perfil de jefe y uno de vendedor por cada Empresa activa.

NO usar en producción: todas las cuentas comparten la contraseña que se pasa.
Idempotente: una cuenta existente conserva su contraseña.

  jefe-<slug>      grupo Jefe, MembresiaEmpresa(JEFE)
  vendedor-<slug>  grupo Vendedora, MembresiaEmpresa(VENDEDORA) + bookings.Vendedora
                   con código `ventas-<slug>` (link de atribución ?ref=ventas-<slug>)

Requiere haber corrido `setup_roles` (crea los grupos).

Uso:  venv/Scripts/python.exe manage.py seed_perfiles_demo --password <clave>
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bookings.models import Vendedora
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa

PERFILES = (
    (MembresiaEmpresa.Rol.JEFE, 'jefe', 'Jefe'),
    (MembresiaEmpresa.Rol.VENDEDORA, 'vendedor', 'Vendedora'),
)


class Command(BaseCommand):
    help = 'Siembra un jefe y un vendedor por Empresa para pruebas locales.'

    def add_arguments(self, parser):
        parser.add_argument('--password', required=True, help='Contraseña de las cuentas nuevas (mín. 8).')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Solo para local (DEBUG=True).')
        password = options['password']
        if len(password) < 8:
            raise CommandError('La contraseña debe tener al menos 8 caracteres.')

        User = get_user_model()
        with transaction.atomic(), scope.como_operador_plataforma():
            for empresa in Empresa.objects.filter(activo=True).order_by('id'):
                for rol, prefijo, grupo in PERFILES:
                    username = f'{prefijo}-{empresa.slug}'
                    usuario, creado = User.objects.get_or_create(
                        username=username,
                        defaults=dict(is_staff=True, first_name=f'{grupo} {empresa.nombre}'),
                    )
                    if creado:
                        usuario.set_password(password)
                        usuario.save(update_fields=['password'])
                    usuario.groups.add(Group.objects.get(name=grupo))
                    MembresiaEmpresa.objects.get_or_create(
                        user=usuario, empresa=empresa, defaults=dict(rol=rol),
                    )
                    if rol == MembresiaEmpresa.Rol.VENDEDORA:
                        Vendedora.objects.get_or_create(
                            usuario=usuario,
                            defaults=dict(empresa=empresa, codigo=f'ventas-{empresa.slug}'),
                        )
                    self.stdout.write(f'  {username}: {"creado" if creado else "ya existía"}')
