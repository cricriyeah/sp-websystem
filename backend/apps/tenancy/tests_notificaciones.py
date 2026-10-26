"""Notificaciones persistentes del backoffice (ver docs/architecture/ARCH-notificaciones-backoffice.md).

Esta parte cubre el modelo y la API interna (`apps/tenancy/notificaciones.py`). El aislamiento entre empresas, la
retencion y el rechazo de RLS viven en `tests_notificaciones_rls.py` (solo Postgres).
"""
from unittest import mock

from django.contrib import messages
from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError, transaction
from django.test import RequestFactory

from apps.testing import EmpresaTestCase

from . import notificaciones
from .models import LecturaNotificacion, Notificacion


class ModeloNotificacionTests(EmpresaTestCase):
    def _notificacion(self, **campos):
        campos.setdefault('nivel', Notificacion.Nivel.EXITO)
        campos.setdefault('texto', 'Listo')
        return Notificacion.objects.create(empresa=self.empresa, **campos)

    def test_guarda_lo_que_paso_con_sus_valores_por_omision(self):
        n = self._notificacion()
        n.refresh_from_db()

        self.assertEqual(n.tipo, Notificacion.Tipo.OTRO)
        self.assertEqual((n.motivo, n.enlace_url, n.enlace_texto), ('', '', ''))
        self.assertIsNone(n.actor)
        self.assertIsNotNone(n.creado_en)

    def test_la_mas_reciente_va_primero(self):
        vieja = self._notificacion(texto='vieja')
        nueva = self._notificacion(texto='nueva')

        self.assertEqual(list(Notificacion.objects.all()), [nueva, vieja])

    def test_una_persona_no_puede_leer_dos_veces_la_misma(self):
        n = self._notificacion()
        usuario = User.objects.create_user('lectora-unica', password='x')
        LecturaNotificacion.objects.create(empresa=self.empresa, notificacion=n, usuario=usuario)

        with self.assertRaises(IntegrityError), transaction.atomic():
            LecturaNotificacion.objects.create(empresa=self.empresa, notificacion=n, usuario=usuario)

    def test_dos_personas_si_pueden_leer_la_misma(self):
        n = self._notificacion()
        for nombre in ('lectora-a', 'lectora-b'):
            usuario = User.objects.create_user(nombre, password='x')
            LecturaNotificacion.objects.create(empresa=self.empresa, notificacion=n, usuario=usuario)

        self.assertEqual(n.lecturas.count(), 2)

    def test_borrar_la_notificacion_borra_sus_lecturas(self):
        n = self._notificacion()
        usuario = User.objects.create_user('lectora-cascada', password='x')
        LecturaNotificacion.objects.create(empresa=self.empresa, notificacion=n, usuario=usuario)

        n.delete()

        self.assertFalse(LecturaNotificacion.objects.exists())

    def test_borrar_al_actor_conserva_la_notificacion_sin_dueno(self):
        actor = User.objects.create_user('actor-que-se-va', password='x')
        n = self._notificacion(actor=actor)

        actor.delete()

        n.refresh_from_db()
        self.assertIsNone(n.actor)


def peticion(usuario=None):
    """Una peticion con la maquinaria de mensajes de Django, como la que llega a una vista del admin."""
    request = RequestFactory().post('/admin/')
    request.user = usuario if usuario is not None else AnonymousUser()
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def mensajes_de(request):
    return [(m.level, m.message) for m in request._messages]


class AvisarTests(EmpresaTestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('avisa-usuario', password='x')

    def test_muestra_el_aviso_de_django_y_guarda_la_notificacion(self):
        request = peticion(self.usuario)

        n = notificaciones.avisar(
            request, Notificacion.Nivel.EXITO, 'Panga y capitán asignados.',
            tipo=Notificacion.Tipo.ASIGNACION, motivo='', enlace_url='/admin/bookings/reserva/1/change/',
            enlace_texto='Ver reserva',
        )

        self.assertEqual(mensajes_de(request), [(messages.SUCCESS, 'Panga y capitán asignados.')])
        n.refresh_from_db()
        self.assertEqual(n.empresa, self.empresa)
        self.assertEqual(n.actor, self.usuario)
        self.assertEqual(n.tipo, Notificacion.Tipo.ASIGNACION)
        self.assertEqual(n.nivel, Notificacion.Nivel.EXITO)
        self.assertEqual((n.enlace_url, n.enlace_texto), ('/admin/bookings/reserva/1/change/', 'Ver reserva'))

    def test_cada_nivel_se_pinta_con_su_color_de_django(self):
        esperado = {
            Notificacion.Nivel.EXITO: messages.SUCCESS,
            Notificacion.Nivel.AVISO: messages.WARNING,
            Notificacion.Nivel.ERROR: messages.ERROR,
        }
        for nivel, color in esperado.items():
            with self.subTest(nivel=nivel):
                request = peticion(self.usuario)
                notificaciones.avisar(request, nivel, 'x')
                self.assertEqual(mensajes_de(request)[0][0], color)

    def test_con_motivo_el_aviso_de_pantalla_junta_texto_y_motivo_pero_se_guardan_separados(self):
        request = peticion(self.usuario)

        n = notificaciones.avisar(
            request, Notificacion.Nivel.ERROR, 'No se pudo enviar el correo.', motivo='Resend respondió 402',
        )

        self.assertEqual(mensajes_de(request), [(messages.ERROR, 'No se pudo enviar el correo. Resend respondió 402')])
        self.assertEqual((n.texto, n.motivo), ('No se pudo enviar el correo.', 'Resend respondió 402'))

    def test_la_pantalla_puede_decir_otra_cosa_que_lo_guardado(self):
        """Un parrafo de instrucciones sirve en pantalla pero no en el feed."""
        request = peticion(self.usuario)

        n = notificaciones.avisar(
            request, Notificacion.Nivel.AVISO, 'Reserva cancelada: Ana.', mensaje='Reserva cancelada: Ana. Ahora devuelve el dinero.',
        )

        self.assertEqual(mensajes_de(request), [(messages.WARNING, 'Reserva cancelada: Ana. Ahora devuelve el dinero.')])
        self.assertEqual(n.texto, 'Reserva cancelada: Ana.')

    def test_un_usuario_anonimo_no_queda_como_actor(self):
        n = notificaciones.avisar(peticion(), Notificacion.Nivel.AVISO, 'x')

        self.assertIsNone(n.actor)

    def test_sin_peticion_solo_guarda_y_necesita_la_empresa_explicita(self):
        n = notificaciones.avisar(None, Notificacion.Nivel.EXITO, 'Hecho', empresa=self.empresa)

        self.assertEqual((n.empresa, n.texto), (self.empresa, 'Hecho'))
        self.assertIsNone(n.actor)

    def test_la_empresa_explicita_manda_sobre_la_del_alcance(self):
        """El operador de plataforma trabaja sin empresa activa: el llamador pasa la de la reserva, y esa no se
        pisa con la del alcance (que ni siquiera se consulta)."""
        distinta = mock.Mock(name='empresa-del-alcance')

        with mock.patch('apps.tenancy.notificaciones.scope.empresa_actual', return_value=distinta) as del_alcance:
            n = notificaciones.avisar(peticion(self.usuario), Notificacion.Nivel.EXITO, 'x', empresa=self.empresa)

        self.assertEqual(n.empresa, self.empresa)
        del_alcance.assert_not_called()

    def test_sin_empresa_no_se_guarda_pero_el_aviso_de_pantalla_si_sale(self):
        request = peticion(self.usuario)

        with mock.patch('apps.tenancy.notificaciones.scope.empresa_actual', return_value=None), \
                self.assertLogs('apps.tenancy.notificaciones', level='WARNING'):
            n = notificaciones.avisar(request, Notificacion.Nivel.EXITO, 'x')

        self.assertIsNone(n)
        self.assertEqual(len(mensajes_de(request)), 1)
        self.assertFalse(Notificacion.objects.exists())

    def test_si_guardar_falla_no_se_propaga_y_el_aviso_de_pantalla_ya_salio(self):
        """R5: un feed caido nunca tumba una venta."""
        request = peticion(self.usuario)

        with mock.patch.object(Notificacion.objects, 'create', side_effect=Exception('base caida')), \
                self.assertLogs('apps.tenancy.notificaciones', level='ERROR'):
            n = notificaciones.avisar(request, Notificacion.Nivel.EXITO, 'Se guardó la reserva')

        self.assertIsNone(n)
        self.assertEqual(mensajes_de(request), [(messages.SUCCESS, 'Se guardó la reserva')])

    def test_un_texto_demasiado_largo_se_recorta_en_vez_de_perderse(self):
        """Un motivo largo de Stripe o un nombre enorme no debe hacer que la notificacion no se guarde."""
        n = notificaciones.registrar_notificacion(
            self.empresa, Notificacion.Nivel.ERROR, 'a' * 500, motivo='b' * 500, enlace_texto='c' * 100,
        )

        n.refresh_from_db()
        self.assertEqual(len(n.texto), 300)
        self.assertTrue(n.texto.endswith('…'))
        self.assertEqual(len(n.motivo), 300)
        self.assertEqual(len(n.enlace_texto), 40)

    def test_el_enlace_solo_puede_ser_una_ruta_del_propio_admin(self):
        """El enlace se pinta como href: ni un esquema `javascript:` ni un dominio ajeno deben llegar ahi."""
        casos = {
            '/admin/bookings/reserva/7/change/': '/admin/bookings/reserva/7/change/',
            'javascript:alert(1)': '',
            'https://malo.example/robo': '',
            '//malo.example/robo': '',
            '/' + 'x' * 400: '',
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada[:40]):
                n = notificaciones.registrar_notificacion(
                    self.empresa, Notificacion.Nivel.EXITO, 'x', enlace_url=entrada, enlace_texto='Ver',
                )
                self.assertEqual(n.enlace_url, esperado)

    def test_el_texto_con_html_se_guarda_tal_cual_en_texto_plano(self):
        """No se limpia ni se escapa al guardar: se escapa al MOSTRAR (autoescape del admin, textContent en el JS)."""
        n = notificaciones.registrar_notificacion(
            self.empresa, Notificacion.Nivel.EXITO, 'Nueva reserva: <script>alert(1)</script>',
        )

        n.refresh_from_db()
        self.assertEqual(n.texto, 'Nueva reserva: <script>alert(1)</script>')


class ContarNoLeidasTests(EmpresaTestCase):
    def setUp(self):
        self.ver = Permission.objects.get(content_type__app_label='tenancy', codename='view_notificacion')
        self.ana = self._usuario('conteo-ana')
        self.beto = self._usuario('conteo-beto')

    def _usuario(self, nombre, con_permiso=True):
        usuario = User.objects.create_user(nombre, password='x')
        if con_permiso:
            usuario.user_permissions.add(self.ver)
        return usuario

    def _crear(self, cuantas=1):
        return [
            Notificacion.objects.create(empresa=self.empresa, nivel=Notificacion.Nivel.EXITO, texto=f'n{i}')
            for i in range(cuantas)
        ]

    def test_sin_el_permiso_de_ver_son_cero(self):
        self._crear(3)
        sin_permiso = self._usuario('conteo-sin-permiso', con_permiso=False)

        self.assertEqual(notificaciones.contar_no_leidas(peticion(sin_permiso)), 0)

    def test_un_anonimo_cuenta_cero(self):
        self._crear(2)

        self.assertEqual(notificaciones.contar_no_leidas(peticion()), 0)

    def test_cuenta_las_que_la_persona_no_ha_leido(self):
        self._crear(3)

        self.assertEqual(notificaciones.contar_no_leidas(peticion(self.ana)), 3)

    def test_marcar_leidas_baja_el_conteo(self):
        notas = self._crear(3)

        notificaciones.marcar_leidas(self.ana, notas[:2])

        self.assertEqual(notificaciones.contar_no_leidas(peticion(self.ana)), 1)

    def test_lo_que_una_persona_marca_no_se_marca_para_otra(self):
        """REQ-6: el estado de leida es personal."""
        notas = self._crear(2)

        notificaciones.marcar_leidas(self.ana, notas)

        self.assertEqual(notificaciones.contar_no_leidas(peticion(self.ana)), 0)
        self.assertEqual(notificaciones.contar_no_leidas(peticion(self.beto)), 2)

    def test_el_conteo_se_corta_en_tope_mas_uno_para_pintar_99_mas(self):
        Notificacion.objects.bulk_create([
            Notificacion(empresa=self.empresa, nivel='exito', texto=f'm{i}') for i in range(105)
        ])

        self.assertEqual(notificaciones.contar_no_leidas(peticion(self.ana)), 100)
        self.assertEqual(notificaciones.contar_no_leidas(peticion(self.ana), tope=3), 4)

    def test_marcar_dos_veces_no_duplica_ni_truena(self):
        notas = self._crear(2)

        notificaciones.marcar_leidas(self.ana, notas)
        notificaciones.marcar_leidas(self.ana, notas)

        self.assertEqual(LecturaNotificacion.objects.filter(usuario=self.ana).count(), 2)

    def test_las_lecturas_llevan_la_empresa_de_su_notificacion(self):
        nota, = self._crear(1)

        notificaciones.marcar_leidas(self.ana, [nota])

        self.assertEqual(LecturaNotificacion.objects.get(usuario=self.ana).empresa, self.empresa)
