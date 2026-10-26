"""Pantalla de notificaciones, permisos, campana (sondeo + JS/CSS) y aislamiento entre empresas en el admin.

El modelo y la API interna viven en `tests_notificaciones.py`; el RLS y la retencion en `tests_notificaciones_rls.py` y
`tests_limpiar_notificaciones.py`. Aqui se ejercita lo que ve y toca una persona en el navegador.
"""
import re
import shutil
import subprocess
from pathlib import Path
from unittest import mock, skipUnless

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.testing import EmpresaTestCase

from . import notificaciones, scope
from .models import Empresa, LecturaNotificacion, MembresiaEmpresa, Notificacion, Sede

ESTATICOS = Path(__file__).resolve().parent / 'static' / 'tenancy'


def crear(empresa, texto='algo paso', **campos):
    campos.setdefault('nivel', Notificacion.Nivel.EXITO)
    return Notificacion.objects.create(empresa=empresa, texto=texto, **campos)


class ListaDeNotificacionesTests(EmpresaTestCase):
    def setUp(self):
        self.jefe = self.crear_jefe()
        self.client.force_login(self.jefe)
        self.url = reverse('admin:tenancy_notificacion_changelist')

    def test_la_lista_muestra_lo_de_la_empresa_y_resalta_lo_no_leido(self):
        leida = crear(self.empresa, 'texto ya leido')
        crear(self.empresa, 'texto pendiente')
        notificaciones.marcar_leidas(self.jefe, [leida])

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, '<strong>texto pendiente</strong>', html=True)
        self.assertContains(respuesta, 'texto ya leido')
        self.assertNotContains(respuesta, '<strong>texto ya leido</strong>', html=True)

    def test_el_motivo_sale_en_segunda_linea_y_el_enlace_como_abrir(self):
        crear(self.empresa, 'No se pudo avisar', nivel='error', motivo='Resend respondió 402',
              enlace_url='/admin/bookings/reserva/5/change/', enlace_texto='Ver reserva')

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Resend respondió 402')
        self.assertContains(respuesta, '<a href="/admin/bookings/reserva/5/change/">Ver reserva</a>', html=True)

    def test_el_html_en_el_texto_y_el_motivo_sale_escapado(self):
        """R4: el nombre del cliente lo escribe el cliente."""
        crear(self.empresa, 'Nueva reserva: <script>alert(1)</script>', motivo='<img src=x onerror=alert(2)>')

        respuesta = self.client.get(self.url)

        self.assertNotContains(respuesta, '<script>alert(1)</script>')
        self.assertNotContains(respuesta, '<img src=x onerror=alert(2)>')
        self.assertContains(respuesta, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertContains(respuesta, '&lt;img src=x onerror=alert(2)&gt;')

    def test_un_enlace_peligroso_guardado_por_otro_camino_no_se_pinta(self):
        """El guardado ya lo limpia; la lista no confia en eso (defensa en profundidad)."""
        n = crear(self.empresa, 'x')
        Notificacion.objects.filter(pk=n.pk).update(enlace_url='javascript:alert(1)', enlace_texto='Abrir')

        respuesta = self.client.get(self.url)

        self.assertNotContains(respuesta, 'javascript:alert(1)')

    def test_se_filtra_por_tipo_y_por_nivel(self):
        crear(self.empresa, 'una asignacion', tipo='asignacion', nivel='exito')
        crear(self.empresa, 'un reembolso fallido', tipo='reembolso', nivel='error')

        por_tipo = self.client.get(self.url, {'tipo__exact': 'reembolso'})
        por_nivel = self.client.get(self.url, {'nivel__exact': 'exito'})

        self.assertContains(por_tipo, 'un reembolso fallido')
        self.assertNotContains(por_tipo, 'una asignacion')
        self.assertContains(por_nivel, 'una asignacion')
        self.assertNotContains(por_nivel, 'un reembolso fallido')

    def test_es_de_solo_lectura_nadie_agrega_cambia_ni_borra(self):
        n = crear(self.empresa)

        self.assertEqual(self.client.get(reverse('admin:tenancy_notificacion_add')).status_code, 403)
        self.assertEqual(
            self.client.post(reverse('admin:tenancy_notificacion_change', args=[n.pk]), {'texto': 'otro'}).status_code,
            403)
        self.assertEqual(self.client.get(reverse('admin:tenancy_notificacion_delete', args=[n.pk])).status_code, 403)
        n.refresh_from_db()
        self.assertEqual(n.texto, 'algo paso')

    def test_vendedora_y_jefe_la_ven_y_quien_no_tiene_el_permiso_recibe_403(self):
        self.client.force_login(self.crear_vendedora())
        self.assertEqual(self.client.get(self.url).status_code, 200)

        sin_permiso = self.crear_vendedora(username='sin-notificaciones', permisos=[])
        sin_permiso.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(sin_permiso)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_el_menu_lateral_ofrece_notificaciones_solo_a_quien_puede_verlas(self):
        reservas = reverse('admin:bookings_reserva_changelist')

        self.assertContains(self.client.get(reservas), f'href="{self.url}"')

        sin_permiso = self.crear_vendedora(username='sin-menu', permisos=[])
        sin_permiso.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(sin_permiso)
        self.assertNotContains(self.client.get(reservas), f'href="{self.url}"')


class MarcarComoLeidasTests(EmpresaTestCase):
    def setUp(self):
        self.jefe = self.crear_jefe()
        self.vendedora = self.crear_vendedora()
        self.client.force_login(self.jefe)
        self.url = reverse('admin:tenancy_notificacion_changelist')
        self.a1 = crear(self.empresa, 'asignacion 1', tipo='asignacion')
        self.a2 = crear(self.empresa, 'asignacion 2', tipo='asignacion')
        self.r1 = crear(self.empresa, 'reembolso 1', tipo='reembolso')

    def _leidas_por(self, usuario):
        return set(LecturaNotificacion.objects.filter(usuario=usuario).values_list('notificacion_id', flat=True))

    def test_marca_exactamente_las_seleccionadas(self):
        self.client.post(self.url, {
            'action': 'marcar_como_leidas', 'index': '0', '_selected_action': [str(self.a1.pk)],
        })

        self.assertEqual(self._leidas_por(self.jefe), {self.a1.pk})

    def test_con_seleccionar_todas_respeta_el_filtro_activo(self):
        """Ejemplo del ARCH: solo los errores, o solo un tipo, aunque haya mas pendientes."""
        self.client.post(self.url + '?tipo__exact=asignacion', {
            'action': 'marcar_como_leidas', 'select_across': '1', 'index': '0',
            '_selected_action': [str(self.a1.pk)],
        })

        self.assertEqual(self._leidas_por(self.jefe), {self.a1.pk, self.a2.pk})

    def test_lo_que_marca_una_persona_no_lo_marca_para_otra(self):
        """REQ-6."""
        self.client.post(self.url, {
            'action': 'marcar_como_leidas', 'index': '0',
            '_selected_action': [str(self.a1.pk), str(self.a2.pk), str(self.r1.pk)],
        })

        self.assertEqual(notificaciones.contar_no_leidas(self._peticion(self.jefe)), 0)
        self.assertEqual(notificaciones.contar_no_leidas(self._peticion(self.vendedora)), 3)

    def _peticion(self, usuario):
        from .tests_notificaciones import peticion
        return peticion(usuario)

    def test_marcar_dos_veces_no_truena(self):
        datos = {'action': 'marcar_como_leidas', 'index': '0', '_selected_action': [str(self.a1.pk)]}
        self.client.post(self.url, datos)

        respuesta = self.client.post(self.url, datos, follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._leidas_por(self.jefe), {self.a1.pk})

    def test_marcar_todas_pide_confirmacion_y_no_marca_con_un_get(self):
        url = reverse('admin:tenancy_notificacion_marcar_todas')

        respuesta = self.client.get(url)

        self.assertContains(respuesta, 'Vas a marcar como le&iacute;das <strong>3</strong>')
        self.assertEqual(self._leidas_por(self.jefe), set())

    def test_marcar_todas_marca_las_pendientes_de_quien_lo_pide_y_de_nadie_mas(self):
        self.client.post(reverse('admin:tenancy_notificacion_marcar_todas'))

        self.assertEqual(self._leidas_por(self.jefe), {self.a1.pk, self.a2.pk, self.r1.pk})
        self.assertEqual(self._leidas_por(self.vendedora), set())

    def test_marcar_todas_sin_permiso_es_403(self):
        sin_permiso = self.crear_vendedora(username='sin-marcar', permisos=[])
        self.client.force_login(sin_permiso)

        self.assertEqual(self.client.post(reverse('admin:tenancy_notificacion_marcar_todas')).status_code, 403)

    def test_la_lista_ofrece_el_boton_de_marcar_todas(self):
        self.assertContains(self.client.get(self.url), 'Marcar todas como leídas')


class PermisosPorRolTests(EmpresaTestCase):
    def test_los_tres_grupos_pueden_ver_y_ninguno_agregar_cambiar_ni_borrar(self):
        for nombre in ('Vendedora', 'Jefe', 'OperadorPlataforma'):
            with self.subTest(grupo=nombre):
                codenames = set(
                    Group.objects.get(name=nombre).permissions
                    .filter(content_type__app_label='tenancy', content_type__model='notificacion')
                    .values_list('codename', flat=True))
                self.assertEqual(codenames, {'view_notificacion'})

    def test_lecturanotificacion_no_se_da_de_alta_en_ningun_rol(self):
        existe = Group.objects.filter(
            permissions__content_type__app_label='tenancy', permissions__content_type__model='lecturanotificacion',
        ).exists()
        self.assertFalse(existe)


class SondeoConCampanaTests(EmpresaTestCase):
    def setUp(self):
        self.jefe = self.crear_jefe()
        self.client.force_login(self.jefe)
        self.url = reverse('avisos_reservas_nuevas')

    def test_la_primera_consulta_ya_trae_el_conteo_y_la_url_de_la_campana(self):
        crear(self.empresa)
        crear(self.empresa)

        datos = self.client.get(self.url).json()

        self.assertEqual(datos['no_leidas'], 2)
        self.assertEqual(datos['notificaciones_url'], reverse('admin:tenancy_notificacion_changelist'))

    def test_las_consultas_siguientes_tambien_y_el_contrato_de_reservas_sigue_igual(self):
        crear(self.empresa)

        datos = self.client.get(self.url, {'desde': '2000-01-01T00:00:00+00:00'}).json()

        self.assertEqual(datos['no_leidas'], 1)
        for clave in ('desde', 'total', 'reservas'):
            self.assertIn(clave, datos)

    def test_el_conteo_baja_al_marcar_y_es_personal(self):
        n = crear(self.empresa)
        notificaciones.marcar_leidas(self.jefe, [n])

        self.assertEqual(self.client.get(self.url).json()['no_leidas'], 0)
        self.client.force_login(self.crear_vendedora())
        self.assertEqual(self.client.get(self.url).json()['no_leidas'], 1)

    def test_sin_el_permiso_no_hay_campana(self):
        crear(self.empresa)
        sin_permiso = self.crear_vendedora(username='sin-campana', permisos=[])
        sin_permiso.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(sin_permiso)

        datos = self.client.get(self.url).json()

        self.assertEqual((datos['no_leidas'], datos['notificaciones_url']), (0, ''))

    def test_si_el_feed_falla_el_aviso_de_reservas_responde_igual(self):
        with mock.patch('apps.bookings.avisos.contar_no_leidas', side_effect=Exception('feed caido')), \
                self.assertLogs('apps.bookings.avisos', level='ERROR'):
            respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual((datos['total'], datos['no_leidas'], datos['notificaciones_url']), (0, 0, ''))


class AislamientoEnElAdminTests(TestCase):
    """Dos empresas y el operador. TestCase sin alcance ambiente: cada peticion abre el suyo (como en produccion)."""

    def setUp(self):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede aislamiento notif', slug='sede-aislamiento-notif')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='Aislada A', slug='aislada-notif-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='Aislada B', slug='aislada-notif-b')
        self.jefe_a = User.objects.create_user('aislada-jefe-a', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=self.jefe_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        self.operador = User.objects.create_user('aislada-operador', password='x', is_staff=True)
        self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        with scope.como_operador_plataforma():
            self.na = crear(self.empresa_a, 'texto exclusivo de A')
            self.nb = crear(self.empresa_b, 'texto exclusivo de B')
        self.url = reverse('admin:tenancy_notificacion_changelist')

    def test_una_empresa_solo_ve_las_suyas_en_la_lista_y_en_el_conteo(self):
        self.client.force_login(self.jefe_a)

        lista = self.client.get(self.url)
        sondeo = self.client.get(reverse('avisos_reservas_nuevas')).json()

        self.assertContains(lista, 'texto exclusivo de A')
        self.assertNotContains(lista, 'texto exclusivo de B')
        self.assertEqual(sondeo['no_leidas'], 1)

    def test_marcar_todas_o_seleccionar_otra_empresa_no_toca_lo_de_la_otra(self):
        self.client.force_login(self.jefe_a)
        self.client.post(reverse('admin:tenancy_notificacion_marcar_todas'))
        # Colar el id de la notificacion de B en la seleccion: el queryset del admin ya esta acotado a la empresa.
        self.client.post(self.url, {
            'action': 'marcar_como_leidas', 'index': '0', '_selected_action': [str(self.nb.pk)],
        })

        with scope.como_operador_plataforma():
            leidas = set(LecturaNotificacion.objects.values_list('notificacion_id', flat=True))
        self.assertEqual(leidas, {self.na.pk})

    def test_el_operador_de_plataforma_ve_las_de_todas_las_empresas(self):
        self.client.force_login(self.operador)

        lista = self.client.get(self.url)
        sondeo = self.client.get(reverse('avisos_reservas_nuevas')).json()

        self.assertContains(lista, 'texto exclusivo de A')
        self.assertContains(lista, 'texto exclusivo de B')
        self.assertEqual(sondeo['no_leidas'], 2)

    def test_el_operador_marca_como_leidas_las_de_cualquier_empresa(self):
        self.client.force_login(self.operador)

        self.client.post(reverse('admin:tenancy_notificacion_marcar_todas'))

        with scope.como_operador_plataforma():
            self.assertEqual(
                LecturaNotificacion.objects.filter(usuario=self.operador).count(), 2)


class CampanaEstaticosTests(SimpleTestCase):
    """El JS no se puede ejercer sin navegador: se vigilan sus reglas y su sintaxis."""

    def setUp(self):
        self.js = (ESTATICOS / 'avisos.js').read_text(encoding='utf-8')
        self.css = (ESTATICOS / 'avisos.css').read_text(encoding='utf-8')

    def test_lo_que_viene_del_servidor_entra_con_textcontent_nunca_como_html(self):
        # Solo se busca la AUSENCIA de estas APIs en el JS; aqui no se ejecuta nada.
        for prohibido in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write', 'ev' + 'al('):
            self.assertNotIn(prohibido, self.js, prohibido)
        self.assertIn('textContent', self.js)

    def test_la_campana_pinta_99_mas_y_se_oculta_en_cero(self):
        self.assertIn("'99+'", self.js)
        self.assertIn('insignia.hidden = n === 0', self.js)

    def test_el_enlace_de_la_campana_solo_acepta_rutas_del_propio_sitio(self):
        self.assertIn('rutaPropia(datos.notificaciones_url)', self.js)

    def test_las_clases_de_la_campana_y_la_lista_no_llevan_sombras_degradados_ni_lineas_finas(self):
        reglas = [
            (selector.strip(), cuerpo)
            for selector, cuerpo in re.findall(r'([^{}]+)\{([^}]*)\}', self.css)
            if '.aviso-campana' in selector or '.notif-' in selector
        ]
        self.assertGreaterEqual(len(reglas), 6)
        for selector, cuerpo in reglas:
            with self.subTest(selector=selector):
                for prohibido in ('shadow', 'gradient', 'border:', 'border-width', 'outline'):
                    self.assertNotIn(prohibido, cuerpo)
                for radio in re.findall(r'border-radius:\s*([^;]+);', cuerpo):
                    self.assertIn(radio.strip(), ('9999px', '50%', '0'), selector)

    @skipUnless(shutil.which('node'), 'node no esta instalado')
    def test_el_js_tiene_sintaxis_valida(self):
        resultado = subprocess.run(
            ['node', '--check', str(ESTATICOS / 'avisos.js')], capture_output=True, text=True, timeout=60)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
