"""Panel de la campana: las ultimas notificaciones en JSON y «Marcar todas como leidas» desde el panel.

La pantalla completa de Notificaciones se prueba en `tests_notificaciones_admin.py`; aqui solo lo que toca el panel.
"""
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from apps.testing import EmpresaTestCase

from . import notificaciones, scope
from .models import Empresa, LecturaNotificacion, MembresiaEmpresa, Notificacion, Sede

ESTATICOS = Path(__file__).resolve().parent / 'static' / 'tenancy'


def crear(empresa, texto='algo paso', **campos):
    campos.setdefault('nivel', Notificacion.Nivel.EXITO)
    return Notificacion.objects.create(empresa=empresa, texto=texto, **campos)


class PanelDeNotificacionesTests(EmpresaTestCase):
    def setUp(self):
        self.jefe = self.crear_jefe()
        self.client.force_login(self.jefe)
        self.url = reverse('avisos_notificaciones')

    def test_trae_las_ultimas_con_su_estado_de_leida_y_las_mas_nuevas_primero(self):
        vieja = crear(self.empresa, 'vieja')
        nueva = crear(self.empresa, 'nueva', nivel='error', motivo='Resend 402',
                      enlace_url='/admin/bookings/reserva/5/change/', enlace_texto='Ver reserva')
        notificaciones.marcar_leidas(self.jefe, [vieja])

        datos = self.client.get(self.url).json()

        self.assertEqual([n['id'] for n in datos['notificaciones']], [nueva.pk, vieja.pk])
        primera, segunda = datos['notificaciones']
        self.assertEqual((primera['leida'], segunda['leida']), (False, True))
        self.assertEqual(primera['url'], '/admin/bookings/reserva/5/change/')
        self.assertEqual((primera['enlace_texto'], primera['motivo']), ('Ver reserva', 'Resend 402'))
        self.assertEqual(datos['no_leidas'], 1)
        self.assertEqual(datos['todas_url'], reverse('admin:tenancy_notificacion_changelist'))

    def test_solo_trae_las_ultimas_ocho(self):
        for i in range(12):
            crear(self.empresa, f'n{i}')

        datos = self.client.get(self.url).json()

        self.assertEqual(len(datos['notificaciones']), notificaciones.LIMITE_PANEL)
        self.assertEqual(datos['notificaciones'][0]['texto'], 'n11')

    def test_un_enlace_que_no_es_del_admin_no_sale(self):
        crear(self.empresa, 'x', enlace_url='javascript:alert(1)')

        self.assertEqual(self.client.get(self.url).json()['notificaciones'][0]['url'], '')

    def test_el_html_en_el_texto_viaja_como_texto_plano_en_json(self):
        crear(self.empresa, '<img src=x onerror=alert(1)>')

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta['Content-Type'], 'application/json')
        self.assertEqual(respuesta.json()['notificaciones'][0]['texto'], '<img src=x onerror=alert(1)>')

    def test_no_se_guarda_en_cache(self):
        self.assertIn('no-store', self.client.get(self.url)['Cache-Control'])

    def test_sin_permiso_de_ver_notificaciones_es_403(self):
        crear(self.empresa)
        sin_permiso = self.crear_vendedora(username='sin-panel', permisos=[])
        sin_permiso.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(sin_permiso)

        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(reverse('avisos_notificaciones_marcar_todas')).status_code, 403)

    def test_sin_sesion_manda_al_login(self):
        self.client.logout()

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/admin/login/', respuesta['Location'])

    def test_el_panel_solo_responde_a_get_y_marcar_solo_a_post(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.assertEqual(self.client.get(reverse('avisos_notificaciones_marcar_todas')).status_code, 405)

    def test_si_el_feed_falla_responde_503_y_lo_registra(self):
        with mock.patch('apps.tenancy.vistas_notificaciones.notificaciones.recientes_para_el_panel',
                        side_effect=Exception('feed caido')), \
                self.assertLogs('apps.tenancy.vistas_notificaciones', level='ERROR'):
            respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 503)


class MarcarTodasDesdeElPanelTests(EmpresaTestCase):
    def setUp(self):
        self.jefe = self.crear_jefe()
        self.client.force_login(self.jefe)
        self.url = reverse('avisos_notificaciones_marcar_todas')

    def test_marca_las_pendientes_de_quien_lo_pide_y_solo_las_suyas(self):
        a, b = crear(self.empresa, 'a'), crear(self.empresa, 'b')
        otra = self.crear_vendedora()

        datos = self.client.post(self.url).json()

        self.assertEqual((datos['marcadas'], datos['no_leidas']), (2, 0))
        self.assertEqual(
            set(LecturaNotificacion.objects.filter(usuario=self.jefe).values_list('notificacion_id', flat=True)),
            {a.pk, b.pk})
        self.assertFalse(LecturaNotificacion.objects.filter(usuario=otra).exists())

    def test_es_idempotente(self):
        crear(self.empresa)
        self.client.post(self.url)

        datos = self.client.post(self.url).json()

        self.assertEqual(datos['marcadas'], 0)
        self.assertEqual(LecturaNotificacion.objects.count(), 1)

    def test_exige_el_token_csrf(self):
        crear(self.empresa)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.jefe)

        self.assertEqual(cliente.post(self.url).status_code, 403)
        self.assertFalse(LecturaNotificacion.objects.exists())

        token = cliente.get(reverse('avisos_notificaciones')).json()['csrf']
        self.assertEqual(cliente.post(self.url, HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertTrue(LecturaNotificacion.objects.filter(usuario=self.jefe).exists())


class AislamientoDelPanelTests(TestCase):
    """Dos empresas y el operador. TestCase sin alcance ambiente: cada peticion abre el suyo (como en produccion)."""

    def setUp(self):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede panel notif', slug='sede-panel-notif')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='Panel A', slug='panel-notif-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='Panel B', slug='panel-notif-b')
        self.jefe_a = User.objects.create_user('panel-jefe-a', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=self.jefe_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        self.operador = User.objects.create_user('panel-operador', password='x', is_staff=True)
        self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        with scope.como_operador_plataforma():
            self.na = crear(self.empresa_a, 'texto exclusivo de A')
            self.nb = crear(self.empresa_b, 'texto exclusivo de B')

    def test_una_empresa_solo_ve_las_suyas_en_el_panel(self):
        self.client.force_login(self.jefe_a)

        datos = self.client.get(reverse('avisos_notificaciones')).json()

        self.assertEqual([n['texto'] for n in datos['notificaciones']], ['texto exclusivo de A'])
        self.assertEqual(datos['no_leidas'], 1)

    def test_marcar_todas_no_toca_lo_de_la_otra_empresa(self):
        self.client.force_login(self.jefe_a)

        self.client.post(reverse('avisos_notificaciones_marcar_todas'))

        with scope.como_operador_plataforma():
            leidas = set(LecturaNotificacion.objects.values_list('notificacion_id', flat=True))
        self.assertEqual(leidas, {self.na.pk})

    def test_el_operador_ve_y_marca_las_de_todas_las_empresas(self):
        self.client.force_login(self.operador)

        datos = self.client.get(reverse('avisos_notificaciones')).json()
        self.assertEqual({n['texto'] for n in datos['notificaciones']},
                         {'texto exclusivo de A', 'texto exclusivo de B'})

        self.client.post(reverse('avisos_notificaciones_marcar_todas'))
        with scope.como_operador_plataforma():
            self.assertEqual(LecturaNotificacion.objects.filter(usuario=self.operador).count(), 2)


class PanelEstaticosTests(SimpleTestCase):
    """El JS no se ejerce sin navegador: se vigilan sus reglas."""

    def setUp(self):
        self.js = (ESTATICOS / 'avisos.js').read_text(encoding='utf-8')

    def test_la_campana_es_un_boton_que_abre_el_panel_y_no_un_enlace(self):
        self.assertIn("campana = el('button', 'aviso-campana')", self.js)
        self.assertIn("'aria-expanded'", self.js)

    def test_el_panel_se_cierra_con_escape_y_con_clic_fuera(self):
        self.assertIn("evento.key === 'Escape'", self.js)
        self.assertIn('panel.contains(evento.target)', self.js)

    def test_los_enlaces_del_panel_solo_aceptan_rutas_del_propio_sitio(self):
        self.assertIn('rutaPropia(n.url)', self.js)
        self.assertIn('rutaPropia(datos.todas_url)', self.js)
        self.assertIn('rutaPropia(datos.marcar_todas_url)', self.js)

    def test_marcar_todas_manda_el_token_csrf(self):
        self.assertIn("'X-CSRFToken'", self.js)


class AvisosEnSegundoPlanoEstaticosTests(SimpleTestCase):
    """El sondeo sigue con la pestana oculta y avisa fuera de la pantalla: reglas del JS, sin navegador."""

    def setUp(self):
        self.js = (ESTATICOS / 'avisos.js').read_text(encoding='utf-8')

    def test_el_ritmo_lo_marca_un_worker_con_respaldo_de_setinterval(self):
        self.assertIn('new window.Worker(', self.js)
        self.assertIn('window.setInterval(consultar, INTERVALO_MS)', self.js)

    def test_ocultar_la_pestana_ya_no_detiene_el_sondeo(self):
        manejador = self.js.split("document.addEventListener('visibilitychange'")[1].split('});')[0]
        self.assertNotIn('parar()', manejador)

    def test_la_notificacion_del_sistema_solo_sale_con_permiso_y_fuera_de_vista(self):
        funcion = self.js.split('function avisarAlSistema(')[1].split('\n  }\n')[0]
        self.assertIn('fueraDeVista()', funcion)
        self.assertIn("permission !== 'granted'", funcion)

    def test_el_permiso_se_pide_solo_desde_un_clic_en_el_boton_de_la_tarjeta(self):
        self.assertEqual(self.js.count('requestPermission'), 1)
        self.assertIn("texto: 'Activar'", self.js)
