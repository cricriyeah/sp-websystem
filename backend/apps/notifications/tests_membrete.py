"""El correo al cliente lleva el membrete del sitio: banda de la empresa, folio, renglones y versión de texto."""
from datetime import date, time, timedelta
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.bookings.models import Reserva
from apps.notifications import plantilla
from apps.notifications.services import (
    _asunto,
    _asunto_asignacion,
    _cuerpo_asignacion_html,
    _cuerpo_html,
    enviar_correo_confirmacion,
)
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca


class PlantillaTests(SimpleTestCase):
    def test_la_banda_es_del_color_de_la_actividad(self):
        for actividad, color in (('mar', '#1b607f'), ('traslado', '#a83226'), ('estancia', '#343f04')):
            html = plantilla.envolver(
                actividad=actividad, empresa='Sal y Sol', titulo='Reserva confirmada', folio=12,
                previa='previa', cuerpo_html='<p>cuerpo</p>',
            )
            self.assertIn(color, html)

    def test_lleva_empresa_folio_y_texto_de_vista_previa(self):
        html = plantilla.envolver(
            actividad='mar', empresa='Sal y Sol', titulo='Reserva confirmada', folio=12,
            previa='2026-12-01 · 06:00', cuerpo_html='<p>cuerpo</p>',
        )
        self.assertIn('Sal y Sol', html)
        self.assertIn('#12', html)
        self.assertIn('2026-12-01 · 06:00', html)
        self.assertIn('color-scheme', html)  # el modo oscuro de Gmail no invierte el fondo a medias

    def test_el_nombre_de_la_empresa_se_escapa(self):
        html = plantilla.envolver(
            actividad='mar', empresa='A&B <script>', titulo='t', folio=1, previa='p', cuerpo_html='',
        )
        self.assertNotIn('<script>', html)
        self.assertIn('A&amp;B &lt;script&gt;', html)

    def test_texto_plano_conserva_el_orden_y_no_trae_etiquetas(self):
        html = plantilla.envolver(
            actividad='mar', empresa='Sal y Sol', titulo='Reserva confirmada', folio=12, previa='p',
            cuerpo_html=plantilla.filas([('Fecha', '2026-12-01'), ('Personas', '2')]),
        )
        texto = plantilla.a_texto(html)
        self.assertNotIn('<', texto)
        self.assertLess(texto.index('Reserva confirmada'), texto.index('Fecha'))
        self.assertLess(texto.index('Fecha'), texto.index('Personas'))
        self.assertIn('2026-12-01', texto)

    def test_los_renglones_vacios_se_omiten(self):
        self.assertNotIn('Regreso', plantilla.filas([('Fecha', '2026-12-01'), ('Regreso', '')]))


@override_settings(RESEND_API_KEY='re_x', RESEND_FROM='reservas@example.com', RESEND_BCC='')
class CorreosConMembreteTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.servicio = crear_servicio_pesca(self.empresa)

    def reserva(self, **extra):
        datos = dict(
            empresa=self.empresa, servicio=self.servicio, fecha=date.today() + timedelta(days=10), hora=time(6, 0),
            numero_personas=2, nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', estado=Reserva.Estado.PAGADA, canal_origen='web',
            deslinde_aceptado=True, moneda='MXN',
        )
        datos.update(extra)
        return Reserva.objects.create(**datos)

    def test_el_asunto_lleva_el_folio_para_que_el_cliente_lo_encuentre_en_su_bandeja(self):
        reserva = self.reserva()
        self.assertIn(f'#{reserva.pk}', _asunto(reserva))
        self.assertIn(f'#{reserva.pk}', _asunto_asignacion(reserva))

    def test_la_confirmacion_trae_banda_folio_y_la_empresa(self):
        reserva = self.reserva()
        html = _cuerpo_html(reserva)
        self.assertIn(self.empresa.nombre, html)
        self.assertIn(f'#{reserva.pk}', html)
        self.assertIn('Reserva confirmada', html)

    def test_el_correo_se_manda_en_html_y_en_texto_plano(self):
        reserva = self.reserva()
        with mock.patch('apps.notifications.services.requests.post') as post:
            self.assertTrue(enviar_correo_confirmacion(reserva))
        cuerpo = post.call_args.kwargs['json']
        self.assertIn('<table', cuerpo['html'])
        self.assertNotIn('<', cuerpo['text'])
        self.assertIn('Ana Ruiz', cuerpo['text'])

    def test_la_asignacion_pone_capitan_panga_y_hora_en_grande(self):
        from apps.fleet.models import Capitan, Embarcacion

        panga = Embarcacion.objects.filter(empresa=self.empresa).first()
        capitan = Capitan.objects.create(empresa=self.empresa, nombre='Chuy Amador')
        reserva = self.reserva(embarcacion=panga, capitan=capitan, estado=Reserva.Estado.ASIGNADA)
        html = _cuerpo_asignacion_html(reserva)
        self.assertIn('Chuy Amador', html)
        self.assertIn(panga.nombre, html)
        self.assertIn('06:00', html)
        self.assertIn('Llega 15 minutos antes', html)
