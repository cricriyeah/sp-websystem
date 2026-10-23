"""La Agenda («Asignar pangas») acepta los enlaces que arma el Calendario.

El hallazgo del Calendario ("3 pagadas sin panga", "1 atrasada") y el boton «Asignar
panga» del popover llevan a la Agenda con un `?periodo=AAAA-MM-DD_AAAA-MM-DD` y, para
las atrasadas, `?cuando=atrasadas`. Sin estos filtros el listado rechazaria el
parametro (redirige con `?e=1`) o lo ignoraria y abriria en la semana.
"""
from datetime import date, timedelta

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
from .tests_agenda import viaje


def periodo(desde, hasta):
    return f'{desde.isoformat()}_{hasta.isoformat()}'


class AgendaPorPeriodoTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())
        self.hoy = date.today()

    def filas(self, **params):
        respuesta = self.client.get(self.url, params)
        self.assertEqual(respuesta.status_code, 200)
        return {r.pk for r in respuesta.context['cl'].result_list}

    def test_el_periodo_trae_solo_los_viajes_de_ese_rango_aunque_sean_lejanos(self):
        dentro = viaje(self.empresa, fecha=self.hoy + timedelta(days=40))
        viaje(self.empresa, fecha=self.hoy + timedelta(days=50))
        viaje(self.empresa, fecha=self.hoy + timedelta(days=2))

        pedido = periodo(self.hoy + timedelta(days=38), self.hoy + timedelta(days=42))

        self.assertEqual(self.filas(periodo=pedido), {dentro.pk})

    def test_un_dia_es_un_periodo_de_un_dia(self):
        uno = viaje(self.empresa, fecha=self.hoy + timedelta(days=5))
        viaje(self.empresa, fecha=self.hoy + timedelta(days=6))

        dia = self.hoy + timedelta(days=5)

        self.assertEqual(self.filas(periodo=periodo(dia, dia)), {uno.pk})

    def test_el_periodo_incluye_viajes_pasados_ya_repartidos(self):
        # Mirar la semana que paso desde el Calendario: lo repartido tambien se ve.
        pasado = self.hoy - timedelta(days=3)
        repartido = viaje(
            self.empresa, fecha=pasado, estado=Reserva.Estado.ASIGNADA,
            embarcacion=Embarcacion.objects.filter(empresa=self.empresa).first(),
        )

        self.assertEqual(self.filas(periodo=periodo(pasado, pasado)), {repartido.pk})

    def test_un_periodo_roto_se_ignora_y_vuelve_la_semana_de_siempre(self):
        dentro = viaje(self.empresa, fecha=self.hoy + timedelta(days=2))
        viaje(self.empresa, fecha=self.hoy + timedelta(days=30))

        for roto in ('hola', '2026-13-01_2026-13-02', '2026-10-05', f'{periodo(self.hoy, self.hoy)}_x'):
            with self.subTest(periodo=roto):
                self.assertEqual(self.filas(periodo=roto), {dentro.pk})

    def test_un_periodo_al_reves_se_ignora(self):
        dentro = viaje(self.empresa, fecha=self.hoy + timedelta(days=2))

        self.assertEqual(
            self.filas(periodo=periodo(self.hoy + timedelta(days=9), self.hoy)), {dentro.pk},
        )

    def test_atrasadas_son_las_pagadas_sin_panga_de_fecha_pasada(self):
        atrasada = viaje(self.empresa, fecha=self.hoy - timedelta(days=4))
        viaje(self.empresa, fecha=self.hoy + timedelta(days=1))
        viaje(
            self.empresa, fecha=self.hoy - timedelta(days=4), estado=Reserva.Estado.ASIGNADA,
            embarcacion=Embarcacion.objects.filter(empresa=self.empresa).first(),
        )

        self.assertEqual(self.filas(cuando='atrasadas'), {atrasada.pk})

    def test_atrasadas_dentro_del_periodo_que_se_estaba_mirando(self):
        esta_semana = viaje(self.empresa, fecha=self.hoy - timedelta(days=2))
        viaje(self.empresa, fecha=self.hoy - timedelta(days=20))

        pedido = periodo(self.hoy - timedelta(days=6), self.hoy)

        self.assertEqual(self.filas(cuando='atrasadas', periodo=pedido), {esta_semana.pk})

    def test_atrasadas_aparece_entre_las_opciones_del_filtro(self):
        respuesta = self.client.get(self.url)

        self.assertIn('atrasadas', [clave for clave, _ in respuesta.context['cl'].filter_specs[0].lookup_choices])


class AgendaPeriodoOperadorTests(TestCase):
    """El operador elige empresa; el periodo no debe romper ni perder esa eleccion."""

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede ap', slug='sede-ap')
        cls.empresa = Empresa.objects.create(sede=sede, nombre='Con Flota', slug='con-flota')
        cls.operador = get_user_model().objects.create_user('op-periodo', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        cls.url = reverse('admin:bookings_agenda_changelist')
        cls.hoy = date.today()
        with scope.como_operador_plataforma():
            crear_flota(cls.empresa)
            cls.lejano = viaje(cls.empresa, fecha=cls.hoy + timedelta(days=40))

    def test_el_operador_con_empresa_y_periodo(self):
        self.client.force_login(self.operador)
        dia = self.hoy + timedelta(days=40)

        respuesta = self.client.get(self.url, {'empresa': 'con-flota', 'periodo': periodo(dia, dia)})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual({r.pk for r in respuesta.context['cl'].result_list}, {self.lejano.pk})

    def test_las_pestanas_de_empresa_conservan_el_periodo(self):
        self.client.force_login(self.operador)
        dia = self.hoy + timedelta(days=40)

        respuesta = self.client.get(self.url, {'empresa': 'con-flota', 'periodo': periodo(dia, dia)})

        for pestana in respuesta.context['agenda_pestanas']:
            self.assertIn('periodo=', pestana['url'])
