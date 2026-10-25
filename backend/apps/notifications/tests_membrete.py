"""Los correos al cliente son el boleto (dirección A): campo de color, hora enorme, datos, perforación y talón."""
from datetime import date, time, timedelta
from decimal import Decimal
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


class FormatosTests(SimpleTestCase):
    def test_dia_largo_en_espanol(self):
        self.assertEqual(plantilla.dia_largo(date(2026, 12, 7)), 'Lunes 7 de diciembre')

    def test_hora_en_12_horas(self):
        self.assertEqual(plantilla.hora_12(time(6, 0)), '6:00 a. m.')
        self.assertEqual(plantilla.hora_12(time(0, 5)), '12:05 a. m.')
        self.assertEqual(plantilla.hora_12(time(12, 30)), '12:30 p. m.')
        self.assertEqual(plantilla.hora_12(time(15, 45)), '3:45 p. m.')

    def test_la_llegada_es_quince_minutos_antes(self):
        self.assertEqual(plantilla.quince_antes(time(6, 0)), time(5, 45))
        self.assertEqual(plantilla.quince_antes(time(0, 10)), time(23, 55))


class BoletoTests(SimpleTestCase):
    def boleto(self, **extra):
        datos = dict(
            actividad='mar', empresa='Sal y Sol', linea1='Lunes 7 de diciembre', linea2='6:00 a. m.', folio=12,
            previa='2026-12-07 · 06:00', pares=[('Sales de', 'Marina Costa Baja')], talon_html='<b>dinero</b>',
        )
        datos.update(extra)
        return plantilla.boleto(**datos)

    def test_el_campo_es_el_color_de_la_actividad(self):
        for actividad, color in (('mar', '#1b607f'), ('traslado', '#a83226'), ('estancia', '#343f04')):
            self.assertIn(color, self.boleto(actividad=actividad))

    def test_lleva_empresa_dia_hora_folio_y_texto_de_vista_previa(self):
        html = self.boleto()
        for texto in ('Sal y Sol', 'Lunes 7 de diciembre', '6:00 a. m.', '#12', '2026-12-07 · 06:00', 'color-scheme'):
            self.assertIn(texto, html)

    def test_la_perforacion_separa_el_boleto_del_talon(self):
        self.assertIn('border-radius:5px', self.boleto())
        self.assertNotIn('border-radius:5px', self.boleto(folio='', talon_html=''))  # sin talon no hay perforacion

    def test_sin_hora_no_hay_linea_enorme(self):
        self.assertNotIn('font:800 84px', self.boleto(linea2=''))

    def test_las_reglas_de_la_casa_no_se_rompen(self):
        html = self.boleto()
        for prohibido in ('gradient', 'box-shadow', 'text-shadow', 'monospace', 'text-transform:uppercase', 'border-top:1px'):
            self.assertNotIn(prohibido, html)

    def test_el_nombre_de_la_empresa_se_escapa(self):
        html = self.boleto(empresa='A&B <script>')
        self.assertNotIn('<script>', html)
        self.assertIn('A&amp;B &lt;script&gt;', html)

    def test_texto_plano_conserva_el_orden_y_no_trae_etiquetas(self):
        texto = plantilla.a_texto(self.boleto(pares=[('Sales de', 'Marina'), ('Personas', '2')]))
        self.assertNotIn('<', texto)
        self.assertLess(texto.index('Lunes 7 de diciembre'), texto.index('Sales de'))
        self.assertLess(texto.index('Sales de'), texto.index('Personas'))

    def test_los_datos_vacios_se_omiten(self):
        self.assertNotIn('Regreso', self.boleto(pares=[('Sales de', 'Marina'), ('Regreso', '')]))


@override_settings(RESEND_API_KEY='re_x', RESEND_FROM='reservas@example.com', RESEND_BCC='')
class CorreosConBoletoTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.servicio = crear_servicio_pesca(self.empresa)
        self.servicio.punto_salida = 'Marina Costa Baja, La Paz'
        self.servicio.save()

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

    def test_la_confirmacion_es_un_boleto_con_dia_hora_llegada_y_folio(self):
        reserva = self.reserva()
        html = _cuerpo_html(reserva)
        self.assertIn(plantilla.dia_largo(reserva.fecha), html)
        self.assertIn('6:00 a. m.', html)
        self.assertIn('5:45 a. m.', html)  # llega 15 minutos antes
        self.assertIn('Marina Costa Baja, La Paz', html)
        self.assertIn(f'#{reserva.pk}', html)
        self.assertIn(self.empresa.nombre, html)

    def test_el_anticipo_muestra_lo_pagado_y_el_saldo_en_el_talon(self):
        reserva = self.reserva(
            forma_pago=Reserva.FormaPago.ANTICIPO, precio_total=Decimal('10800.00'), monto_pagado=Decimal('3240.00'),
        )
        html = _cuerpo_html(reserva)
        self.assertIn('Pagaste hoy', html)
        self.assertIn('3240.00 MXN', html)
        self.assertIn('Quedan 7560.00 MXN', html)
        self.assertIn('por liquidar en efectivo', html)

    def test_pago_completo_no_habla_de_saldo(self):
        reserva = self.reserva(precio_total=Decimal('10800.00'), monto_pagado=Decimal('10800.00'))
        self.assertNotIn('por liquidar en efectivo', _cuerpo_html(reserva))

    def test_el_correo_se_manda_en_html_y_en_texto_plano(self):
        reserva = self.reserva()
        with mock.patch('apps.notifications.services.requests.post') as post:
            self.assertTrue(enviar_correo_confirmacion(reserva))
        cuerpo = post.call_args.kwargs['json']
        self.assertIn('<table', cuerpo['html'])
        self.assertNotIn('<', cuerpo['text'])
        self.assertIn('Ana Ruiz', cuerpo['text'])

    def test_la_asignacion_pone_la_llegada_en_grande_y_con_quien_sale(self):
        from apps.fleet.models import Capitan, Embarcacion

        panga = Embarcacion.objects.filter(empresa=self.empresa).first()
        capitan = Capitan.objects.create(empresa=self.empresa, nombre='Chuy Amador')
        reserva = self.reserva(embarcacion=panga, capitan=capitan, estado=Reserva.Estado.ASIGNADA)
        html = _cuerpo_asignacion_html(reserva)
        self.assertIn('Sales con Chuy', html)
        self.assertIn('Chuy Amador', html)
        self.assertIn(panga.nombre, html)
        self.assertIn('5:45 a. m.', html)
        self.assertIn('La panga sale a las 6:00 a. m.', html)
        self.assertNotIn('9876543', html)
