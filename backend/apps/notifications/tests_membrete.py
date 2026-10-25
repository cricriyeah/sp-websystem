"""Los correos al cliente siguen la página de confirmación del sitio: campo de color, titular, datos, dinero, qué sigue."""
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


class CorreoTests(SimpleTestCase):
    def correo(self, **extra):
        datos = dict(
            actividad='mar', empresa='Sal y Sol', titulo='Reserva confirmada', folio=12, producto='Pesca deportiva',
            intro_html='Hola Ana', previa='2026-12-07 · 06:00',
            pares=[('Día', 'Lunes 7 de diciembre'), ('Sales de', 'Marina Costa Baja')],
            dinero_html=plantilla.bloque_pagado('3240.00 MXN'), siguiente_html='<p>sigue</p>', con_garantias=True,
        )
        datos.update(extra)
        return plantilla.correo(**datos)

    def test_el_campo_es_el_color_de_la_actividad(self):
        for actividad, color in (('mar', '#1b607f'), ('traslado', '#a83226'), ('estancia', '#343f04')):
            self.assertIn(color, self.correo(actividad=actividad))

    def test_sigue_el_orden_de_la_confirmacion_del_sitio(self):
        texto = plantilla.a_texto(self.correo())
        orden = ['RESERVA CONFIRMADA', 'Pesca deportiva', 'LO QUE RESERVASTE', 'EL DINERO', 'QUÉ SIGUE', 'SI ALGO CAMBIA']
        posiciones = [texto.index(parte) for parte in orden]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_los_titulares_van_en_mayusculas_y_negrita_como_el_sitio(self):
        html = self.correo()
        self.assertIn('RESERVA CONFIRMADA', html)
        self.assertIn('LO QUE RESERVASTE', html)
        self.assertIn('Consolas', html)  # la fuente de titulares del sitio no se carga en correo: se usa su equivalente

    def test_lleva_folio_empresa_y_texto_de_vista_previa(self):
        html = self.correo()
        for texto in ('Sal y Sol', '#12', '2026-12-07 · 06:00', 'color-scheme'):
            self.assertIn(texto, html)

    def test_las_garantias_son_las_del_sitio_con_sus_cifras(self):
        html = self.correo()
        for texto in ('100 %', '48 h', 'Si el mal clima impide salir, hay reembolso completo.',
                      'Puedes cambiar la fecha con al menos 48 horas de anticipación.'):
            self.assertIn(texto, html)
        self.assertNotIn('SI ALGO CAMBIA', self.correo(con_garantias=False))

    def test_sin_dinero_ni_siguiente_no_hay_esas_secciones(self):
        html = self.correo(dinero_html='', siguiente_html='', con_garantias=False)
        self.assertNotIn('EL DINERO', html)
        self.assertNotIn('QUÉ SIGUE', html)

    def test_sin_adornos_prohibidos(self):
        html = self.correo()
        for prohibido in ('gradient', 'box-shadow', 'text-shadow', 'border-radius', 'border-top:1px'):
            self.assertNotIn(prohibido, html)

    @override_settings(FRONTEND_URL='https://sitio.example/')
    def test_lleva_el_logo_de_la_marca_con_su_texto_alternativo(self):
        html = self.correo()
        self.assertIn('<img src="https://sitio.example/correo/sunbajaexperience-blanco.png"', html)
        self.assertIn('alt="Sun Baja Experience"', html)
        self.assertEqual(html.count('<img'), 1)
        # El logo va dentro del campo de color, antes del titular.
        self.assertLess(html.index('<img'), html.index('RESERVA CONFIRMADA'))

    @override_settings(FRONTEND_URL='')
    def test_sin_url_del_sitio_no_pone_una_imagen_rota(self):
        self.assertNotIn('<img', self.correo())

    def test_el_titular_se_escapa_y_no_rompe_entidades(self):
        html = self.correo(titulo='A&B <x>')
        self.assertNotIn('<x>', html)
        self.assertIn('A&amp;B &lt;X&gt;', html)

    def test_el_nombre_de_la_empresa_se_escapa(self):
        html = self.correo(empresa='A&B <script>')
        self.assertNotIn('<script>', html)

    def test_texto_plano_sin_etiquetas(self):
        self.assertNotIn('<', plantilla.a_texto(self.correo()))

    def test_los_datos_vacios_se_omiten(self):
        self.assertNotIn('Regreso', self.correo(pares=[('Día', 'Lunes'), ('Regreso', '')]))


@override_settings(RESEND_API_KEY='re_x', RESEND_FROM='reservas@example.com', RESEND_BCC='')
class CorreosComoElSitioTests(EmpresaTestCase):
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

    def test_la_confirmacion_trae_dia_hora_llegada_y_folio(self):
        reserva = self.reserva()
        html = _cuerpo_html(reserva)
        self.assertIn(plantilla.dia_largo(reserva.fecha), html)
        self.assertIn('6:00 a. m.', html)
        self.assertIn('5:45 a. m.', html)  # llega 15 minutos antes
        self.assertIn('Marina Costa Baja, La Paz', html)
        self.assertIn(f'#{reserva.pk}', html)
        self.assertIn(self.empresa.nombre, html)
        self.assertIn('SI ALGO CAMBIA', html)  # la pesca lleva las garantias del sitio

    def test_el_anticipo_muestra_lo_pagado_y_el_saldo(self):
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

    def test_la_asignacion_dice_con_quien_sale_y_a_que_hora_llegar(self):
        from apps.fleet.models import Capitan, Embarcacion

        panga = Embarcacion.objects.filter(empresa=self.empresa).first()
        capitan = Capitan.objects.create(empresa=self.empresa, nombre='Chuy Amador')
        reserva = self.reserva(embarcacion=panga, capitan=capitan, estado=Reserva.Estado.ASIGNADA)
        html = _cuerpo_asignacion_html(reserva)
        self.assertIn('SALES CON CHUY', html)
        self.assertIn('Chuy Amador', html)
        self.assertIn(panga.nombre, html)
        self.assertIn('5:45 a. m.', html)
        self.assertIn('Hora de salida', html)
        self.assertIn('6:00 a. m.', html)
        self.assertNotIn('9876543', html)
