"""El boton «Reagendar» del popover del calendario (Semana y Dia).

El popover lo pinta `_calendario_detalle.html`; el boton lleva a la pantalla de Reagendar
(`admin:bookings_reserva_reagendar`) con `?volver=<el calendario tal como estaba>`, solo si la
reserva se puede reagendar (`reagendar.puede_reagendarse`) y la persona puede cambiar reservas.
Mes no tiene popover y no cambia.

Cada prueba crea sus propias reservas con nombres propios (`setUpTestData` solo siembra
empresas, usuarios y catalogo, que ninguna prueba modifica).
"""
import html
import importlib
import re
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import Permission
from django.db import connection
from django.http import HttpResponse
from django.test.utils import CaptureQueriesContext
from django.urls import NoReverseMatch, clear_url_caches, path, reverse

from apps.bookings.calendario import Estancia, Evento, Pieza, armar_calendario
from apps.bookings.models import Orden, Reserva, ViajeTransporte
from apps.bookings.tests_calendario_vista import CalendarioVistaBase, lunes_de
from apps.fleet.models import Embarcacion, Paquete, PaqueteServicio
from apps.tenancy import scope
from apps.tenancy.models import MembresiaEmpresa

BOTON = re.compile(r'<a href="([^"]*)" class="cal-boton">Reagendar</a>')


class RutaDeReagendarSiFalta:
    """Registra una ruta de relleno SOLO si la pantalla real de Reagendar aun no esta montada.

    La ruta real la agrega `ReservaAdmin.get_urls` (otra slice). Mientras no exista, el
    `{% url %}` del popover no resolveria y ninguna pantalla del calendario abriria. Con la
    ruta real montada esta clase no hace nada.
    """

    _parche = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            reverse('admin:bookings_reserva_reagendar', args=[1])
            return
        except NoReverseMatch:
            pass
        from apps.bookings.admin import ReservaAdmin

        original = ReservaAdmin.get_urls

        def get_urls(self):
            vista = self.admin_site.admin_view(lambda request, pk: HttpResponse('reagendar'))
            return [path('<int:pk>/reagendar/', vista, name='bookings_reserva_reagendar')] + original(self)

        cls._parche = mock.patch.object(ReservaAdmin, 'get_urls', get_urls)
        cls._parche.start()
        cls._recargar_urls()

    @classmethod
    def tearDownClass(cls):
        if cls._parche is not None:
            cls._parche.stop()
            cls._recargar_urls()
        super().tearDownClass()

    @staticmethod
    def _recargar_urls():
        import config.urls

        importlib.reload(config.urls)
        clear_url_caches()


class BotonReagendarBase(RutaDeReagendarSiFalta, CalendarioVistaBase):
    def setUp(self):
        self.lunes = lunes_de(self.hoy)
        self.martes = self.lunes + timedelta(days=1)

    def reagendar_hrefs(self, respuesta):
        return [html.unescape(h) for h in BOTON.findall(respuesta.content.decode())]

    def url_reagendar(self, reserva):
        return reverse('admin:bookings_reserva_reagendar', args=[reserva.pk])

    def semana(self, usuario=None, **params):
        return self.ver(usuario or self.vendedora, vista='semana', desde=self.lunes.isoformat(), **params)


class PiezaSePuedeReagendarTests(BotonReagendarBase):
    def test_la_pieza_pregunta_a_puede_reagendarse(self):
        reserva = self.reserva(self.alfa, self.pesca_alfa, 'Pieza Uno', self.martes)
        evento = armar_calendario(self.lunes, self.lunes + timedelta(days=6), self.alfa).eventos[0]
        self.assertIsInstance(evento, Evento)

        with mock.patch('apps.bookings.calendario.puede_reagendarse', return_value=False) as pregunta:
            self.assertFalse(evento.se_puede_reagendar)
        pregunta.assert_called_once_with(reserva)
        with mock.patch('apps.bookings.calendario.puede_reagendarse', return_value=True):
            self.assertTrue(evento.se_puede_reagendar)

    def test_una_estancia_tambien_la_tiene(self):
        self.reserva(
            self.beta, self.hotel_beta, 'Pieza Hotel', self.martes, hora=None,
            fecha_salida=self.martes + timedelta(days=2),
        )
        estancia = armar_calendario(self.lunes, self.lunes + timedelta(days=6), self.beta).estancias[0]
        self.assertIsInstance(estancia, Estancia)
        self.assertIsInstance(estancia, Pieza)

        with mock.patch('apps.bookings.calendario.puede_reagendarse', return_value=True):
            self.assertTrue(estancia.se_puede_reagendar)

    def test_responde_con_las_reglas_reales_de_cada_estado(self):
        pagada = self.reserva(self.alfa, self.pesca_alfa, 'Pieza Pagada', self.martes)
        completada = self.reserva(
            self.alfa, self.pesca_alfa, 'Pieza Completada', self.martes, estado=Reserva.Estado.COMPLETADA,
        )
        piezas = {
            e.reserva.pk: e
            for e in armar_calendario(self.lunes, self.lunes + timedelta(days=6), self.alfa).eventos
        }

        self.assertTrue(piezas[pagada.pk].se_puede_reagendar)
        self.assertFalse(piezas[completada.pk].se_puede_reagendar)


class BotonEnElPopoverTests(BotonReagendarBase):
    def test_una_pagada_trae_el_boton_con_el_enlace_a_la_pantalla_de_reagendar(self):
        reserva = self.reserva(self.alfa, self.pesca_alfa, 'Boton Pagada', self.martes)

        hrefs = self.reagendar_hrefs(self.semana())

        self.assertEqual(len(hrefs), 1)
        self.assertEqual(urlsplit(hrefs[0]).path, self.url_reagendar(reserva))
        self.assertIn('volver', parse_qs(urlsplit(hrefs[0]).query))

    def test_una_asignada_tambien(self):
        with scope.como_operador_plataforma():
            panga = Embarcacion.objects.create(
                empresa=self.alfa, nombre='Dorado R', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
            )
        reserva = self.reserva(
            self.alfa, self.pesca_alfa, 'Boton Asignada', self.martes,
            estado=Reserva.Estado.ASIGNADA, embarcacion=panga,
        )

        hrefs = self.reagendar_hrefs(self.semana())

        self.assertEqual([urlsplit(h).path for h in hrefs], [self.url_reagendar(reserva)])

    def test_tambien_en_la_vista_dia(self):
        reserva = self.reserva(self.alfa, self.pesca_alfa, 'Boton Dia', self.martes)

        respuesta = self.ver(self.vendedora, vista='dia', desde=self.martes.isoformat())

        self.assertEqual([urlsplit(h).path for h in self.reagendar_hrefs(respuesta)], [self.url_reagendar(reserva)])

    def test_va_junto_a_abrir_reserva_y_asignar_panga(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Boton Junto', self.martes)

        cuerpo = self.semana().content.decode()

        acciones = re.search(r'<p class="cal-det-acciones">(.*?)</p>', cuerpo, re.S).group(1)
        self.assertLess(acciones.index('Abrir reserva'), acciones.index('>Reagendar<'))
        self.assertIn('data-asignar-panga', acciones)

    def test_un_traslado_reagendable_lleva_el_boton_en_cada_tramo(self):
        reserva = self.reserva(self.beta, self.traslado_beta, 'Boton Traslado', self.martes, hora=None)
        with scope.como_operador_plataforma():
            ViajeTransporte.objects.create(
                empresa=self.beta, reserva=reserva, sentido='ida', fecha=self.martes,
            )
            ViajeTransporte.objects.create(
                empresa=self.beta, reserva=reserva, sentido='regreso', fecha=self.martes + timedelta(days=2),
            )

        hrefs = self.reagendar_hrefs(self.semana(self.jefe_beta))

        self.assertEqual({urlsplit(h).path for h in hrefs}, {self.url_reagendar(reserva)})
        self.assertEqual(len(hrefs), 2)

    def test_un_paquete_reagendable_lleva_el_boton_en_su_barra(self):
        with scope.como_operador_plataforma():
            paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.alfa, nombre='Finde R', slug='finde-reagendar',
                precio_ancla=Decimal('9000'),
            )
            PaqueteServicio.objects.create(
                paquete=paquete, servicio=self.pesca_alfa, orden=1, dia_estancia=1, personas_incluidas=3,
            )
        reserva = self.reserva(
            self.alfa, None, 'Boton Paquete', self.martes, paquete=paquete, inicio_paquete=self.martes,
            fecha_salida=self.martes + timedelta(days=2),
        )

        hrefs = self.reagendar_hrefs(self.semana())

        self.assertEqual([urlsplit(h).path for h in hrefs], [self.url_reagendar(reserva)])


class SinBotonTests(BotonReagendarBase):
    def assertSinBoton(self, respuesta, nombre):
        self.assertContains(respuesta, nombre)  # la reserva se ve: lo que falta es solo el boton
        self.assertEqual(self.reagendar_hrefs(respuesta), [])

    def test_una_cancelada_no(self):
        self.reserva(
            self.alfa, self.pesca_alfa, 'Sin Cancelada', self.martes, estado=Reserva.Estado.CANCELADA,
        )

        self.assertSinBoton(self.semana(canceladas='1'), 'Sin Cancelada')

    def test_una_completada_no(self):
        self.reserva(
            self.alfa, self.pesca_alfa, 'Sin Completada', self.martes, estado=Reserva.Estado.COMPLETADA,
        )

        self.assertSinBoton(self.semana(), 'Sin Completada')

    def test_un_componente_de_orden_no(self):
        with scope.como_operador_plataforma():
            paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.alfa, nombre='Orden R', slug='orden-reagendar',
                precio_ancla=Decimal('5000'),
            )
            orden = Orden.objects.create(
                sede=self.sede, empresa_lider=self.alfa, paquete=paquete, nombre_cliente='Sin Orden',
                telefono_cliente='+5216121234567', correo_cliente='o@example.com',
            )
        self.reserva(self.alfa, self.pesca_alfa, 'Sin Orden', self.martes, orden=orden)

        self.assertSinBoton(self.semana(), 'Sin Orden')

    def test_una_en_disputa_no(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Sin Disputa', self.martes, en_disputa=True)

        self.assertSinBoton(self.semana(), 'Sin Disputa')

    def test_quien_solo_puede_ver_reservas_no_lo_ve(self):
        solo_ver = self.usuario('solo-ver-reagendar', self.alfa, MembresiaEmpresa.Rol.VENDEDORA)
        solo_ver.groups.clear()
        solo_ver.user_permissions.add(Permission.objects.get(codename='view_reserva', content_type__app_label='bookings'))
        self.reserva(self.alfa, self.pesca_alfa, 'Sin Permiso', self.martes)

        respuesta = self.semana(solo_ver)

        self.assertContains(respuesta, 'Abrir reserva')
        self.assertSinBoton(respuesta, 'Sin Permiso')

    def test_en_mes_no_hay_popover_ni_boton(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Sin Mes', self.martes)

        respuesta = self.ver(self.vendedora, vista='mes', desde=self.lunes.replace(day=1).isoformat())

        self.assertEqual(self.reagendar_hrefs(respuesta), [])
        self.assertNotContains(respuesta, '/reagendar/')


class VolverTests(BotonReagendarBase):
    def test_volver_es_el_calendario_tal_como_estaba(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Volver Exacto', self.martes)

        hrefs = self.reagendar_hrefs(self.semana(canceladas='1'))

        volver = parse_qs(urlsplit(hrefs[0]).query)['volver'][0]
        destino = urlsplit(volver)
        self.assertEqual(destino.path, reverse('calendario'))
        self.assertEqual(
            parse_qs(destino.query),
            {'vista': ['semana'], 'desde': [self.lunes.isoformat()], 'canceladas': ['1']},
        )

    def test_un_parametro_hostil_no_rompe_el_atributo_ni_se_cuela_como_html(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Volver Hostil', self.martes)

        respuesta = self.ver(self.vendedora, vista='semana', desde='"><script>alert(1)</script>')

        cuerpo = respuesta.content.decode()
        self.assertNotIn('<script>alert(1)</script>', cuerpo)
        for crudo in re.findall(r'<a href="([^"]*)" class="cal-boton">Reagendar</a>', cuerpo):
            self.assertNotIn('<', crudo)
            self.assertNotIn('>', crudo)
        # La vista cae al valor por defecto con una fecha rota, y el enlace conserva la URL pedida
        # tal cual (la pantalla de Reagendar la valida antes de redirigir).
        for href in self.reagendar_hrefs(respuesta):
            volver = parse_qs(urlsplit(href).query)['volver'][0]
            self.assertTrue(volver.startswith('/admin/calendario/?'))
            self.assertNotIn('<', volver)


class SinConsultasPorFilaTests(BotonReagendarBase):
    def consultas(self, **params):
        usuario = self.vendedora
        self.client.force_login(usuario)
        self.client.get(self.url, params)  # calienta caches de contenttypes y permisos del proceso
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(self.url, params)
        self.assertEqual(respuesta.status_code, 200)
        return len(capturadas), respuesta

    def test_las_consultas_no_crecen_con_el_numero_de_reservas(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Fila 0', self.martes, hora=None)
        una, respuesta_una = self.consultas(vista='semana', desde=self.lunes.isoformat())
        self.assertEqual(len(self.reagendar_hrefs(respuesta_una)), 1)

        for i in range(1, 10):
            self.reserva(self.alfa, self.pesca_alfa, f'Fila {i}', self.martes + timedelta(days=i % 3), hora=None)
        diez, respuesta_diez = self.consultas(vista='semana', desde=self.lunes.isoformat())

        self.assertEqual(len(self.reagendar_hrefs(respuesta_diez)), 10)
        self.assertEqual(diez, una)

    def test_lo_mismo_en_la_vista_dia(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Dia 0', self.martes, hora=None)
        una, _ = self.consultas(vista='dia', desde=self.martes.isoformat())

        for i in range(1, 10):
            self.reserva(self.alfa, self.pesca_alfa, f'Dia {i}', self.martes, hora=None)
        diez, respuesta = self.consultas(vista='dia', desde=self.martes.isoformat())

        self.assertEqual(len(self.reagendar_hrefs(respuesta)), 10)
        self.assertEqual(diez, una)
