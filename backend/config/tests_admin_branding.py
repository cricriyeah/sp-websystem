from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede


User = get_user_model()


class AdminBrandingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sede = Sede.objects.create(nombre='Sede de prueba', slug='sede-branding')
        cls.transporte = Empresa.objects.create(
            sede=sede, nombre='DLS Transporte', slug='dls-branding',
        )
        cls.ventana = Empresa.objects.create(
            sede=sede, nombre='La Ventana Travel', slug='ventana-branding',
        )

        cls.jefe = User.objects.create_user(username='jefe-branding', password='clave', is_staff=True)
        MembresiaEmpresa.objects.create(
            user=cls.jefe, empresa=cls.transporte, rol=MembresiaEmpresa.Rol.JEFE,
        )
        cls.vendedora = User.objects.create_user(
            username='vendedora-branding', password='clave', is_staff=True,
        )
        MembresiaEmpresa.objects.create(
            user=cls.vendedora, empresa=cls.ventana, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )

        cls.superusuario = User.objects.create_superuser(
            username='operador-branding', password='clave',
        )
        operador, _ = Group.objects.get_or_create(name='OperadorPlataforma')
        cls.superusuario.groups.add(operador)

    def test_jefe_ve_el_nombre_de_su_empresa(self):
        self.client.force_login(self.jefe)
        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['site_header'], 'DLS Transporte')
        self.assertEqual(response.context['site_title'], 'DLS Transporte')

    def test_vendedora_ve_el_nombre_de_su_empresa(self):
        self.client.force_login(self.vendedora)
        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['site_header'], 'La Ventana Travel')
        self.assertEqual(response.context['site_title'], 'La Ventana Travel')

    def test_superusuario_ve_sun_baja_experiences(self):
        self.client.force_login(self.superusuario)
        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['site_header'], 'Sun Baja Experiences')
        self.assertEqual(response.context['site_title'], 'Sun Baja Experiences')

    def test_login_sin_sesion_muestra_sun_baja_experiences(self):
        response = self.client.get('/admin/login/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['site_header'], 'Sun Baja Experiences')
        self.assertEqual(response.context['site_title'], 'Sun Baja Experiences')
