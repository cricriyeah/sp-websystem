from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase


class SetupRolesTests(TestCase):
    def test_jefe_no_tiene_permisos_sobre_auth_group(self):
        call_command('setup_roles')
        jefe = Group.objects.get(name='Jefe')
        self.assertFalse(
            jefe.permissions.filter(content_type__app_label='auth', content_type__model='group').exists()
        )
        self.assertTrue(jefe.permissions.filter(codename='view_user').exists())
        self.assertTrue(jefe.permissions.filter(codename='change_user').exists())
        self.assertFalse(jefe.permissions.filter(codename='add_user').exists())
        self.assertFalse(jefe.permissions.filter(codename='delete_user').exists())

    def test_operador_plataforma_si_tiene_auth_group(self):
        call_command('setup_roles')
        operador = Group.objects.get(name='OperadorPlataforma')
        self.assertTrue(
            operador.permissions.filter(content_type__app_label='auth', content_type__model='group').exists()
        )
        self.assertTrue(operador.permissions.filter(codename='add_user').exists())
