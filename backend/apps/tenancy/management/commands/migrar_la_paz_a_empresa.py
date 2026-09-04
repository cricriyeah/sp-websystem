"""Migra las cuentas de La Paz (`is_superuser`) a roles por Empresa.

Antes de la expansion multi-sede, "jefe" era `is_superuser=True` sin Group ni
MembresiaEmpresa. Este comando es el paso unico que convierte esas cuentas
reales al modelo nuevo: un operador de plataforma (sin MembresiaEmpresa, ve
todas las Empresas) y el resto de superusuarios pasan a Jefe de 'sal-y-sol'
(unica Empresa que existe en este punto del despliegue). Las vendedoras ya
usan el grupo Django `Vendedora`, solo ganan su MembresiaEmpresa.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.tenancy.models import Empresa, MembresiaEmpresa

User = get_user_model()


class Command(BaseCommand):
    help = 'Migra las cuentas de La Paz (is_superuser) a roles por Empresa.'

    def add_arguments(self, parser):
        parser.add_argument('--operador', required=True, help='username que pasa a OperadorPlataforma.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            grupo_jefe = Group.objects.get(name='Jefe')
            grupo_vendedora = Group.objects.get(name='Vendedora')
            grupo_operador = Group.objects.get(name='OperadorPlataforma')
        except Group.DoesNotExist:
            raise CommandError(
                "Los grupos Jefe/Vendedora/OperadorPlataforma no existen todavia. "
                "Correr 'manage.py setup_roles' primero."
            )

        try:
            empresa = Empresa.objects.get(slug='sal-y-sol')
        except Empresa.DoesNotExist:
            raise CommandError(
                "No existe la Empresa 'sal-y-sol'. Correr la migracion "
                "'tenancy.0002_crear_sede_empresa_la_paz' primero."
            )

        try:
            operador = User.objects.get(username=options['operador'])
        except User.DoesNotExist:
            raise CommandError(f"No existe el usuario '{options['operador']}'.")

        dry_run = options['dry_run']
        jefes = list(User.objects.filter(is_superuser=True).exclude(pk=operador.pk))
        vendedoras = list(User.objects.filter(groups=grupo_vendedora, is_superuser=False))

        self.stdout.write(f'Operador de plataforma: {operador.username}')
        self.stdout.write(f'Jefes a migrar: {[u.username for u in jefes]}')
        self.stdout.write(f'Vendedoras a migrar: {[u.username for u in vendedoras]}')

        if dry_run:
            self.stdout.write(self.style.WARNING('--dry-run: no se aplico ningun cambio.'))
            return

        with transaction.atomic():
            operador.groups.add(grupo_operador)
            operador.is_superuser = False
            operador.save(update_fields=['is_superuser'])

            for jefe in jefes:
                MembresiaEmpresa.objects.get_or_create(
                    user=jefe, empresa=empresa, defaults={'rol': MembresiaEmpresa.Rol.JEFE},
                )
                jefe.groups.add(grupo_jefe)
                jefe.is_superuser = False
                jefe.save(update_fields=['is_superuser'])

            for vendedora in vendedoras:
                MembresiaEmpresa.objects.get_or_create(
                    user=vendedora, empresa=empresa, defaults={'rol': MembresiaEmpresa.Rol.VENDEDORA},
                )

        self.stdout.write(self.style.SUCCESS(
            f'Migrados: 1 operador, {len(jefes)} jefe(s), {len(vendedoras)} vendedora(s).'
        ))
