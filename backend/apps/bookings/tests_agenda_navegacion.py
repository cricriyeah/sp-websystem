"""«Asignar pangas» (la Agenda) llega a cualquier fecha y su buscador sirve.

La dueña no podia repartir pangas fuera de la semana en curso: el listado solo
miraba de hoy a hoy+7 y el buscador se intersectaba con esa misma ventana, asi que
buscar a un cliente de la semana siguiente devolvia cero resultados. Aqui se fija:

- sin ningun filtro la vista sigue siendo la semana de siempre;
- `?periodo=` (lo que ya armaba el Calendario) o `?desde=&hasta=` (el formulario de
  la pantalla) llevan a cualquier rango;
- el buscador, sin rango elegido, mira todas las fechas; con rango, dentro de el;
- el panorama arranca donde arranca el rango, para ver que panga queda libre ESA semana.
"""
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.fleet.models import Embarcacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import EmpresaTestCase, crear_flota

from .models import Reserva
from .panorama import armar_panorama
from .tests_agenda import viaje


def periodo(desde, hasta):
    return f'{desde.isoformat()}_{hasta.isoformat()}'


class AgendaBuscadorTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())
        self.hoy = date.today()

    def filas(self, **params):
        respuesta = self.client.get(self.url, params)
        self.assertEqual(respuesta.status_code, 200)
        return {r.pk for r in respuesta.context['cl'].result_list}

    def test_buscar_a_un_cliente_de_dentro_de_un_mes_lo_encuentra(self):
        lejano = viaje(self.empresa, fecha=self.hoy + timedelta(days=33), nombre_cliente='Zacarias Lejano')
        viaje(self.empresa, fecha=self.hoy + timedelta(days=2), nombre_cliente='Otra Persona')

        self.assertEqual(self.filas(q='Zacarias'), {lejano.pk})

    def test_buscar_por_telefono_tambien_sale_de_la_semana(self):
        lejano = viaje(
            self.empresa, fecha=self.hoy + timedelta(days=21), telefono_cliente='+5216129998877',
        )
        viaje(self.empresa, fecha=self.hoy + timedelta(days=1), telefono_cliente='+5216121110000')

        self.assertEqual(self.filas(q='9998877'), {lejano.pk})

    def test_buscar_sin_rango_tambien_trae_lo_ya_pasado_y_sin_repartir(self):
        atrasado = viaje(self.empresa, fecha=self.hoy - timedelta(days=12), nombre_cliente='Beto Atrasado')

        self.assertEqual(self.filas(q='Beto'), {atrasado.pk})

    def test_buscar_con_rango_elegido_se_queda_dentro_del_rango(self):
        dentro = viaje(self.empresa, fecha=self.hoy + timedelta(days=40), nombre_cliente='Perez Dentro')
        viaje(self.empresa, fecha=self.hoy + timedelta(days=60), nombre_cliente='Perez Fuera')

        pedido = periodo(self.hoy + timedelta(days=38), self.hoy + timedelta(days=45))

        self.assertEqual(self.filas(q='Perez', periodo=pedido), {dentro.pk})

    def test_buscar_dentro_de_manana_respeta_manana(self):
        manana = viaje(self.empresa, fecha=self.hoy + timedelta(days=1), nombre_cliente='Luna Manana')
        viaje(self.empresa, fecha=self.hoy + timedelta(days=9), nombre_cliente='Luna Lejos')

        self.assertEqual(self.filas(q='Luna', cuando='manana'), {manana.pk})

    def test_sin_buscar_la_vista_sigue_siendo_la_semana(self):
        dentro = viaje(self.empresa, fecha=self.hoy + timedelta(days=3))
        viaje(self.empresa, fecha=self.hoy + timedelta(days=33))

        self.assertEqual(self.filas(), {dentro.pk})

    def test_el_formulario_de_busqueda_conserva_el_rango_elegido(self):
        dia = self.hoy + timedelta(days=40)
        viaje(self.empresa, fecha=dia)

        respuesta = self.client.get(self.url, {'periodo': periodo(dia, dia)})

        self.assertContains(respuesta, f'name="periodo" value="{periodo(dia, dia)}"')

    def test_buscar_sin_rango_avisa_que_mira_todas_las_fechas(self):
        viaje(self.empresa, fecha=self.hoy + timedelta(days=33), nombre_cliente='Zacarias Lejano')

        respuesta = self.client.get(self.url, {'q': 'Zacarias'})

        self.assertContains(respuesta, 'data-buscando-en-todas')
        self.assertEqual(respuesta.context['agenda_periodo']['modo'], 'busqueda')

    def test_buscar_con_rango_no_dice_todas_las_fechas(self):
        dia = self.hoy + timedelta(days=40)
        viaje(self.empresa, fecha=dia, nombre_cliente='Zacarias Lejano')

        respuesta = self.client.get(self.url, {'q': 'Zacarias', 'periodo': periodo(dia, dia)})

        self.assertNotContains(respuesta, 'data-buscando-en-todas')


class AgendaNavegarSemanasTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())
        self.hoy = date.today()

    def nav(self, **params):
        respuesta = self.client.get(self.url, params)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.context['agenda_periodo']

    @staticmethod
    def periodo_de(enlace):
        return parse_qs(urlparse(enlace).query)['periodo'][0]

    def test_la_vista_normal_ofrece_la_semana_siguiente_y_la_anterior(self):
        nav = self.nav()

        self.assertEqual(nav['modo'], 'semana')
        self.assertEqual(
            self.periodo_de(nav['siguiente']),
            periodo(self.hoy + timedelta(days=7), self.hoy + timedelta(days=13)),
        )
        self.assertEqual(
            self.periodo_de(nav['anterior']),
            periodo(self.hoy - timedelta(days=7), self.hoy - timedelta(days=1)),
        )

    def test_desde_un_rango_las_flechas_avanzan_su_propia_longitud(self):
        desde, hasta = self.hoy + timedelta(days=14), self.hoy + timedelta(days=20)

        nav = self.nav(periodo=periodo(desde, hasta))

        self.assertEqual(nav['modo'], 'periodo')
        self.assertEqual(
            self.periodo_de(nav['siguiente']),
            periodo(hasta + timedelta(days=1), hasta + timedelta(days=7)),
        )
        self.assertEqual(
            self.periodo_de(nav['anterior']),
            periodo(desde - timedelta(days=7), desde - timedelta(days=1)),
        )

    def test_un_rango_de_un_mes_avanza_de_mes_en_mes(self):
        desde, hasta = self.hoy + timedelta(days=30), self.hoy + timedelta(days=59)

        nav = self.nav(periodo=periodo(desde, hasta))

        self.assertEqual(
            self.periodo_de(nav['siguiente']),
            periodo(hasta + timedelta(days=1), hasta + timedelta(days=30)),
        )

    def test_hay_un_enlace_para_volver_a_la_semana_de_siempre(self):
        desde, hasta = self.hoy + timedelta(days=14), self.hoy + timedelta(days=20)

        nav = self.nav(periodo=periodo(desde, hasta))

        self.assertNotIn('periodo', nav['esta_semana'])
        self.assertNotIn('cuando', nav['esta_semana'])

    def test_los_enlaces_conservan_la_busqueda_solo_si_hay_rango(self):
        # Una busqueda sin rango mira todo; al saltar de semana se deja la busqueda
        # (si no, la flecha "siguiente" no cambiaria nada de lo que se ve).
        nav = self.nav(q='Zacarias')

        self.assertNotIn('q=', nav['siguiente'])

    def test_con_rango_las_flechas_conservan_la_busqueda(self):
        desde, hasta = self.hoy + timedelta(days=14), self.hoy + timedelta(days=20)

        nav = self.nav(periodo=periodo(desde, hasta), q='Perez')

        self.assertIn('q=Perez', nav['siguiente'])
        self.assertIn('q=Perez', nav['anterior'])

    def test_elegir_proximos_7_dias_en_el_filtro_ignora_el_rango_y_la_barra_lo_dice(self):
        desde, hasta = self.hoy + timedelta(days=14), self.hoy + timedelta(days=20)
        dentro = viaje(self.empresa, fecha=self.hoy + timedelta(days=2))
        viaje(self.empresa, fecha=desde)

        respuesta = self.client.get(self.url, {'cuando': 'semana', 'periodo': periodo(desde, hasta)})

        self.assertEqual({r.pk for r in respuesta.context['cl'].result_list}, {dentro.pk})
        self.assertEqual(respuesta.context['agenda_periodo']['modo'], 'semana')

    def test_atrasadas_con_rango_conserva_atrasadas_al_navegar(self):
        desde, hasta = self.hoy - timedelta(days=14), self.hoy - timedelta(days=8)

        nav = self.nav(cuando='atrasadas', periodo=periodo(desde, hasta))

        self.assertEqual(nav['modo'], 'atrasadas')
        self.assertIn('cuando=atrasadas', nav['anterior'])
        self.assertIn('cuando=atrasadas', nav['siguiente'])

    def test_el_listado_trae_el_rango_al_que_se_navega(self):
        lejano = viaje(self.empresa, fecha=self.hoy + timedelta(days=9))
        viaje(self.empresa, fecha=self.hoy + timedelta(days=3))

        nav = self.nav()
        respuesta = self.client.get(nav['siguiente'])

        self.assertEqual({r.pk for r in respuesta.context['cl'].result_list}, {lejano.pk})

    def test_la_pantalla_dibuja_las_flechas_y_el_formulario_de_fechas(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'data-periodo-anterior')
        self.assertContains(respuesta, 'data-periodo-siguiente')
        self.assertContains(respuesta, 'name="desde"')
        self.assertContains(respuesta, 'name="hasta"')


class AgendaFormularioDeFechasTests(EmpresaTestCase):
    """El formulario manda `desde` y `hasta`; la pantalla los vuelve `?periodo=`."""

    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())
        self.hoy = date.today()

    def a_donde_manda(self, **params):
        respuesta = self.client.get(self.url, params)
        self.assertEqual(respuesta.status_code, 302)
        destino = urlparse(respuesta['Location'])
        self.assertEqual(destino.path, self.url)
        return {k: v[0] for k, v in parse_qs(destino.query).items()}

    def test_desde_y_hasta_se_vuelven_un_periodo(self):
        desde, hasta = self.hoy + timedelta(days=30), self.hoy + timedelta(days=36)

        consulta = self.a_donde_manda(desde=desde.isoformat(), hasta=hasta.isoformat())

        self.assertEqual(consulta, {'periodo': periodo(desde, hasta)})

    def test_solo_desde_es_esa_semana(self):
        desde = self.hoy + timedelta(days=30)

        consulta = self.a_donde_manda(desde=desde.isoformat(), hasta='')

        self.assertEqual(consulta, {'periodo': periodo(desde, desde + timedelta(days=6))})

    def test_un_rango_al_reves_se_acomoda(self):
        desde, hasta = self.hoy + timedelta(days=30), self.hoy + timedelta(days=36)

        consulta = self.a_donde_manda(desde=hasta.isoformat(), hasta=desde.isoformat())

        self.assertEqual(consulta, {'periodo': periodo(desde, hasta)})

    def test_fechas_rotas_vuelven_a_la_semana_de_siempre(self):
        consulta = self.a_donde_manda(desde='manana', hasta='2026-13-45')

        self.assertEqual(consulta, {})

    def test_conserva_la_empresa_las_atrasadas_y_la_busqueda_y_suelta_la_pagina(self):
        # `atrasadas` es el unico modo que se combina con un rango (las de esa semana).
        desde, hasta = self.hoy + timedelta(days=30), self.hoy + timedelta(days=36)

        consulta = self.a_donde_manda(
            desde=desde.isoformat(), hasta=hasta.isoformat(), empresa='x', p='3',
            cuando='atrasadas', q='perez',
        )

        self.assertEqual(consulta, {
            'periodo': periodo(desde, hasta), 'empresa': 'x', 'cuando': 'atrasadas', 'q': 'perez',
        })

    def test_manana_y_semana_se_sueltan_porque_ignoran_el_rango(self):
        # Con `cuando=manana` el rango nuevo no se veria: la pantalla seguiria en manana.
        desde, hasta = self.hoy + timedelta(days=30), self.hoy + timedelta(days=36)

        for modo in ('manana', 'semana', 'recientes'):
            with self.subTest(cuando=modo):
                consulta = self.a_donde_manda(
                    desde=desde.isoformat(), hasta=hasta.isoformat(), cuando=modo,
                )

                self.assertEqual(consulta, {'periodo': periodo(desde, hasta)})

    def test_el_destino_abre_el_rango(self):
        desde, hasta = self.hoy + timedelta(days=30), self.hoy + timedelta(days=36)
        lejano = viaje(self.empresa, fecha=desde + timedelta(days=2))

        respuesta = self.client.get(
            self.url, {'desde': desde.isoformat(), 'hasta': hasta.isoformat()}, follow=True,
        )

        self.assertEqual({r.pk for r in respuesta.context['cl'].result_list}, {lejano.pk})


class AgendaPanoramaDelRangoTests(EmpresaTestCase):
    """La cuadricula arranca donde arranca el rango: es la que dice que panga queda libre."""

    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())
        self.hoy = date.today()
        self.panga = Embarcacion.objects.filter(empresa=self.empresa).first()

    def test_con_un_rango_futuro_el_panorama_arranca_en_su_primer_dia(self):
        desde = self.hoy + timedelta(days=21)

        respuesta = self.client.get(self.url, {'periodo': periodo(desde, desde + timedelta(days=6))})

        panorama = respuesta.context['panorama']
        self.assertEqual(panorama.dias[0], desde)
        self.assertEqual(len(panorama.dias), 7)

    def test_el_panorama_de_una_semana_futura_muestra_lo_asignado_esa_semana(self):
        dia = self.hoy + timedelta(days=22)
        viaje(
            self.empresa, fecha=dia, estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga,
            nombre_cliente='Carlos Futuro',
        )

        respuesta = self.client.get(self.url, {'periodo': periodo(dia, dia + timedelta(days=6))})

        self.assertContains(respuesta, 'Carlos Futuro')

    def test_sin_rango_el_panorama_sigue_arrancando_hoy(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context['panorama'].dias[0], self.hoy)

    def test_un_rango_pasado_no_mueve_el_panorama_al_pasado(self):
        # Cerrar el dia o sacar una panga de un dia que ya paso se rechaza; la cuadricula
        # sigue mostrando desde hoy.
        pasado = self.hoy - timedelta(days=10)

        respuesta = self.client.get(self.url, {'periodo': periodo(pasado, pasado + timedelta(days=6))})

        self.assertEqual(respuesta.context['panorama'].dias[0], self.hoy)

    def test_un_rango_que_cruza_hoy_arranca_hoy(self):
        respuesta = self.client.get(
            self.url,
            {'periodo': periodo(self.hoy - timedelta(days=3), self.hoy + timedelta(days=3))},
        )

        self.assertEqual(respuesta.context['panorama'].dias[0], self.hoy)

    def test_los_atrasados_del_resumen_no_incluyen_lo_de_esta_semana(self):
        # Con el panorama en la semana 3, un viaje pagado de pasado manana todavia no
        # esta atrasado: "atrasado" es lo que ya paso, no lo que queda antes de la
        # cuadricula.
        viaje(self.empresa, fecha=self.hoy + timedelta(days=2))
        desde = self.hoy + timedelta(days=21)

        panorama = armar_panorama(desde, self.empresa, hoy=self.hoy)

        self.assertEqual(panorama.resumen.atrasados, 0)

    def test_los_atrasados_de_verdad_siguen_contandose(self):
        viaje(self.empresa, fecha=self.hoy - timedelta(days=2))
        desde = self.hoy + timedelta(days=21)

        panorama = armar_panorama(desde, self.empresa, hoy=self.hoy)

        self.assertEqual(panorama.resumen.atrasados, 1)

    def test_el_titulo_dice_que_semana_es_cuando_no_es_la_de_hoy(self):
        desde = self.hoy + timedelta(days=21)

        respuesta = self.client.get(self.url, {'periodo': periodo(desde, desde + timedelta(days=6))})

        self.assertContains(respuesta, 'data-panorama-rango')


class AgendaNavegacionOperadorTests(TestCase):
    """El operador mira una empresa a la vez; navegar por fechas no la pierde."""

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede nav', slug='sede-nav')
        cls.empresa = Empresa.objects.create(sede=sede, nombre='Con Flota Nav', slug='con-flota-nav')
        cls.operador = get_user_model().objects.create_user('op-nav', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        cls.url = reverse('admin:bookings_agenda_changelist')
        cls.hoy = date.today()
        with scope.como_operador_plataforma():
            crear_flota(cls.empresa)
            cls.lejano = viaje(
                cls.empresa, fecha=cls.hoy + timedelta(days=40), nombre_cliente='Zacarias Operador',
            )

    def test_las_flechas_conservan_la_empresa(self):
        self.client.force_login(self.operador)

        respuesta = self.client.get(self.url, {'empresa': 'con-flota-nav'})

        nav = respuesta.context['agenda_periodo']
        for enlace in (nav['anterior'], nav['siguiente'], nav['esta_semana']):
            self.assertIn('empresa=con-flota-nav', enlace)

    def test_el_formulario_de_fechas_lleva_la_empresa_oculta(self):
        self.client.force_login(self.operador)

        respuesta = self.client.get(self.url, {'empresa': 'con-flota-nav'})

        self.assertContains(respuesta, '<input type="hidden" name="empresa" value="con-flota-nav">')

    def test_el_operador_busca_en_todas_las_fechas_de_su_empresa(self):
        self.client.force_login(self.operador)

        respuesta = self.client.get(self.url, {'empresa': 'con-flota-nav', 'q': 'Zacarias'})

        self.assertEqual({r.pk for r in respuesta.context['cl'].result_list}, {self.lejano.pk})

    def test_el_formulario_de_fechas_del_operador_conserva_la_empresa(self):
        self.client.force_login(self.operador)
        dia = self.hoy + timedelta(days=40)

        respuesta = self.client.get(
            self.url, {'empresa': 'con-flota-nav', 'desde': dia.isoformat(), 'hasta': dia.isoformat()},
        )

        self.assertEqual(respuesta.status_code, 302)
        consulta = parse_qs(urlparse(respuesta['Location']).query)
        self.assertEqual(consulta['empresa'], ['con-flota-nav'])
        self.assertEqual(consulta['periodo'], [periodo(dia, dia)])
