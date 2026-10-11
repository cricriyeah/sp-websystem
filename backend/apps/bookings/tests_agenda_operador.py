"""El operador de plataforma no pertenece a una empresa: elige cual agenda mira."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.fleet.models import Capitan, Embarcacion, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede

from .models import Reserva


class AgendaOperadorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede op', slug='sede-op')
        cls.con_pangas = Empresa.objects.create(sede=sede, nombre='Con Pangas', slug='con-pangas')
        cls.otra = Empresa.objects.create(sede=sede, nombre='Otra Flota', slug='otra-flota')
        cls.sin_pangas = Empresa.objects.create(sede=sede, nombre='Sin Pangas', slug='sin-pangas')
        cls.operador = get_user_model().objects.create_user('op-agenda', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        cls.url = reverse('admin:bookings_agenda_changelist')

        with scope.como_operador_plataforma():
            for empresa in (cls.con_pangas, cls.otra):
                Embarcacion.objects.create(
                    empresa=empresa, nombre=f'Panga {empresa.slug}',
                    clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
                )
                Capitan.objects.create(empresa=empresa, nombre=f'Capitan {empresa.slug}', telefono='1')
                servicio = Servicio.objects.create(
                    empresa=empresa, nombre='Pesca', slug='pesca', tipo_servicio='pesca',
                )
                for n in range(2 if empresa == cls.con_pangas else 1):
                    Reserva.objects.create(
                        empresa=empresa, servicio=servicio,
                        fecha=timezone.localdate() + timedelta(days=2),
                        numero_personas=2, nombre_cliente=f'Cliente {empresa.slug} {n}',
                        telefono_cliente='6121234567', correo_cliente='a@example.com',
                        canal_origen=Reserva.CanalOrigen.WEB, estado=Reserva.Estado.PAGADA,
                    )

    def setUp(self):
        self.client.force_login(self.operador)

    def test_sin_empresa_elegida_pide_elegir_y_nunca_dice_todo_asignado(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['agenda_estado'], 'elegir')
        self.assertIsNone(respuesta.context['panorama'])
        self.assertContains(respuesta, 'data-elegir-empresa')
        self.assertNotContains(respuesta, 'Todo asignado')
        self.assertNotContains(respuesta, 'Cliente con-pangas')

    def test_las_pestanas_traen_pendientes_y_marcan_las_empresas_sin_pangas(self):
        pestanas = {p['nombre']: p for p in self.client.get(self.url).context['agenda_pestanas']}

        self.assertEqual(pestanas['Con Pangas']['sin_panga'], 2)
        self.assertEqual(pestanas['Otra Flota']['sin_panga'], 1)
        self.assertFalse(pestanas['Sin Pangas']['aplica'])
        self.assertTrue(pestanas['Con Pangas']['aplica'])

    def test_empresa_elegida_arma_su_panorama_y_su_tabla_solo_con_lo_suyo(self):
        respuesta = self.client.get(self.url, {'empresa': 'con-pangas'})

        self.assertEqual(respuesta.context['agenda_estado'], 'normal')
        self.assertEqual(respuesta.context['panorama'].resumen.sin_panga, 2)
        self.assertEqual(
            [r.embarcacion.nombre for r in respuesta.context['panorama'].renglones],
            ['Panga con-pangas'],
        )
        self.assertContains(respuesta, 'Cliente con-pangas 0')
        self.assertNotContains(respuesta, 'Cliente otra-flota')

    def test_empresa_sin_pangas_lo_dice_en_vez_de_afirmar_que_todo_esta_asignado(self):
        respuesta = self.client.get(self.url, {'empresa': 'sin-pangas'})

        self.assertEqual(respuesta.context['agenda_estado'], 'sin_pangas')
        self.assertIsNone(respuesta.context['panorama'])
        self.assertContains(respuesta, 'data-empresa-sin-pangas')
        self.assertNotContains(respuesta, 'Todo asignado')

    def test_un_slug_que_no_existe_cuenta_como_no_elegido(self):
        respuesta = self.client.get(self.url, {'empresa': 'no-existe'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['agenda_estado'], 'elegir')

    def test_la_ultima_empresa_elegida_se_recuerda(self):
        self.client.get(self.url, {'empresa': 'otra-flota'})

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('empresa=otra-flota', respuesta['Location'])

    def test_el_filtro_de_fecha_conserva_la_empresa_en_las_pestanas(self):
        respuesta = self.client.get(self.url, {'empresa': 'con-pangas', 'cuando': 'semana'})

        for pestana in respuesta.context['agenda_pestanas']:
            self.assertIn('cuando=semana', pestana['url'])

    def test_los_capitanes_ofrecidos_son_los_de_la_empresa_de_la_reserva(self):
        respuesta = self.client.get(self.url, {'empresa': 'con-pangas'})

        formulario = respuesta.context['cl'].formset.forms[0]
        self.assertEqual(
            list(formulario.fields['capitan'].queryset.values_list('nombre', flat=True)),
            ['Capitan con-pangas'],
        )
