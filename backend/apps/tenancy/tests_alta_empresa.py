"""Alta de empresa en un paso y su lista de pendientes (apps/tenancy/alta_empresa.py)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.tenancy.alta_empresa import estado_de_empresa
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede

User = get_user_model()

DATOS = {
    'sede': '',
    'sede_nueva': 'Loreto',
    'nombre': 'Pesca Loreto',
    'slug': '',
    'correos_aviso': 'jefe@loreto.example',
    'jefe_usuario': 'jefe_loreto',
    'jefe_nombre': 'Ana Loreto',
    'jefe_password': 'una-clave-larga-9271',
}


class AltaEmpresaTests(TestCase):
    def setUp(self):
        call_command('setup_roles', verbosity=0)
        self.operador = User.objects.create_user('operador', password='x', is_staff=True)
        self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        self.client.force_login(self.operador)
        self.url = reverse('admin:tenancy_empresa_alta')

    def test_crea_sede_empresa_jefe_y_membresia_de_una_vez(self):
        resp = self.client.post(self.url, DATOS)

        empresa = Empresa.objects.get(nombre='Pesca Loreto')
        self.assertRedirects(resp, reverse('admin:tenancy_empresa_estado', args=[empresa.pk]))
        self.assertEqual(empresa.slug, 'pesca-loreto')
        self.assertEqual(empresa.sede.nombre, 'Loreto')
        jefe = User.objects.get(username='jefe_loreto')
        self.assertTrue(jefe.is_staff)
        self.assertTrue(jefe.groups.filter(name='Jefe').exists())
        self.assertTrue(MembresiaEmpresa.objects.filter(
            user=jefe, empresa=empresa, rol=MembresiaEmpresa.Rol.JEFE).exists())

    def test_usa_una_sede_existente(self):
        sede = Sede.objects.create(nombre='Cabo', slug='cabo')
        self.client.post(self.url, {**DATOS, 'sede': sede.pk, 'sede_nueva': ''})
        self.assertEqual(Empresa.objects.get(nombre='Pesca Loreto').sede, sede)
        self.assertFalse(Sede.objects.filter(nombre='Loreto').exists())

    def test_pide_una_sede_y_solo_una(self):
        sede = Sede.objects.create(nombre='Cabo', slug='cabo')
        for extra in ({'sede_nueva': ''}, {'sede': sede.pk}):
            resp = self.client.post(self.url, {**DATOS, **extra})
            self.assertEqual(resp.status_code, 200)
        self.assertFalse(Empresa.objects.filter(nombre='Pesca Loreto').exists())

    def test_rechaza_slug_usuario_y_correo_repetidos_o_malos_sin_crear_nada(self):
        sede = Sede.objects.create(nombre='Cabo', slug='cabo')
        Empresa.objects.create(sede=sede, nombre='Otra', slug='pesca-loreto')
        User.objects.create_user('jefe_loreto', password='x')
        resp = self.client.post(self.url, {**DATOS, 'slug': 'pesca-loreto', 'correos_aviso': 'mal'})
        self.assertEqual(resp.status_code, 200)
        for campo in ('slug', 'jefe_usuario', 'correos_aviso'):
            self.assertIn(campo, resp.context['form'].errors)
        self.assertFalse(Sede.objects.filter(nombre='Loreto').exists())

    def test_slug_automatico_no_choca_con_uno_existente(self):
        sede = Sede.objects.create(nombre='Cabo', slug='cabo')
        Empresa.objects.create(sede=sede, nombre='Otra', slug='pesca-loreto')
        self.client.post(self.url, DATOS)
        self.assertEqual(Empresa.objects.get(nombre='Pesca Loreto').slug, 'pesca-loreto-2')

    def test_corre_setup_roles_si_los_grupos_no_existen(self):
        Group.objects.filter(name='Jefe').delete()
        self.client.post(self.url, DATOS)
        self.assertTrue(User.objects.get(username='jefe_loreto').groups.filter(name='Jefe').exists())

    def test_pendientes_y_webhook_se_ven_en_la_pantalla_de_estado(self):
        self.client.post(self.url, DATOS)
        empresa = Empresa.objects.get(nombre='Pesca Loreto')

        resp = self.client.get(reverse('admin:tenancy_empresa_estado', args=[empresa.pk]))

        html = resp.content.decode()
        self.assertIn('/api/pesca-loreto/stripe/webhook/', html)
        self.assertEqual(html.count('data-hecho="si"'), 2)  # empresa creada + jefe
        self.assertEqual(html.count('data-hecho="no"'), 4)  # llaves, vendedora, servicio, flota

    def test_llaves_puestas_marcan_ese_paso(self):
        self.client.post(self.url, DATOS)
        empresa = Empresa.objects.get(nombre='Pesca Loreto')
        empresa.stripe_secret_key = 'sk_test_x'
        empresa.stripe_publishable_key = 'pk_test_x'
        empresa.stripe_webhook_secret = 'whsec_x'
        empresa.save()
        pasos = {p['texto'].split(' (')[0]: p['hecho'] for p in estado_de_empresa(empresa)}
        self.assertTrue(pasos['Llaves de Stripe puestas'])

    def test_el_listado_ofrece_el_alta_y_la_columna_de_pendientes(self):
        self.client.post(self.url, DATOS)
        html = self.client.get(reverse('admin:tenancy_empresa_changelist')).content.decode()
        self.assertIn('alta-accion', html)
        self.assertIn('Alta de empresa', html)
        self.assertIn('4 por hacer', html)

    def test_un_jefe_no_puede_dar_de_alta_empresas(self):
        jefe = User.objects.create_user('jefe', password='x', is_staff=True)
        jefe.groups.add(Group.objects.get(name='Jefe'))
        self.client.force_login(jefe)
        self.assertEqual(self.client.post(self.url, DATOS).status_code, 403)
        self.assertFalse(Empresa.objects.filter(nombre='Pesca Loreto').exists())
