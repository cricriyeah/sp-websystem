"""Los correos al cliente salen en español o en ingles.

Lo que se protege aqui: que el idioma salga del sitio en el que compro y, si no hay, de la lada
del telefono; que un correo en ingles no traiga pedazos en español (ni al reves); que el español
siga saliendo igual que antes; y que el idioma de un correo no se le pegue al siguiente.
"""
from datetime import date, time
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.bookings.models import Reserva
from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.bookings.telefono import idioma_por_telefono

from . import plantilla, services
from .correo_reagendado import enviar_correo_reagendado
from .correo_recordatorio_saldo import enviar_correo_recordatorio_saldo
from .idioma import en_idioma, idioma_actual, idioma_de, tr
from .tests_correo_reagendado import Antes, _Base

LLAVES = {'RESEND_API_KEY': 'test-key', 'RESEND_FROM': 'reservas@ejemplo.com', 'RESEND_BCC': []}
# Textos que solo existen en español: ninguno puede colarse en un correo en ingles.
SOLO_ESPANOL = (
    'Lo que reservaste', 'El dinero', 'Qué sigue', 'Si algo cambia', 'Pagaste hoy', 'Folio', 'Hola ',
    'Personas', 'Sales de', 'Llega a las', 'Guarda este correo', 'por liquidar', 'escríbenos', 'Día',
    'diciembre', 'a. m.',
)


def _enviado(post):
    return post.call_args.kwargs['json']


class IdiomaPorTelefonoTests(SimpleTestCase):
    def test_lada_mexicana_o_numero_nacional_es_espanol(self):
        for telefono in ('+5216121234567', '+52 612 123 4567', '6121234567', '612 123 4567', '', None):
            with self.subTest(telefono=telefono):
                self.assertEqual(idioma_por_telefono(telefono), 'es')

    def test_cualquier_otra_lada_es_ingles(self):
        for telefono in ('+16195551234', '+1 (619) 555-1234', '+14165551234', '+447911123456', '+33612345678'):
            with self.subTest(telefono=telefono):
                self.assertEqual(idioma_por_telefono(telefono), 'en')


class IdiomaDeLaReservaTests(SimpleTestCase):
    def test_el_idioma_del_sitio_manda_sobre_la_lada(self):
        self.assertEqual(Reserva(idioma='es', telefono_cliente='+16195551234').idioma_cliente, 'es')
        self.assertEqual(Reserva(idioma='en', telefono_cliente='+5216121234567').idioma_cliente, 'en')

    def test_sin_idioma_guardado_decide_la_lada(self):
        self.assertEqual(Reserva(telefono_cliente='+16195551234').idioma_cliente, 'en')
        self.assertEqual(Reserva(telefono_cliente='6121234567').idioma_cliente, 'es')

    def test_el_checkout_guarda_solo_es_o_en(self):
        validar = ReservaCheckoutSerializer().validate_idioma

        self.assertEqual(validar('en'), 'en')
        self.assertEqual(validar('ES'), 'es')
        self.assertEqual(validar('en-US'), 'en')
        # Un valor raro no rompe el checkout: se guarda vacio y decide la lada.
        self.assertEqual(validar('fr'), '')
        self.assertEqual(validar(''), '')


class ElIdiomaNoSeQuedaPegadoTests(SimpleTestCase):
    def test_fuera_del_bloque_todo_vuelve_a_espanol(self):
        with en_idioma('en'):
            self.assertEqual(tr('hola', 'hi'), 'hi')
            self.assertEqual(plantilla.dia_largo(date(2026, 12, 7)), 'Monday, December 7')
            self.assertEqual(plantilla.hora_12(time(6, 0)), '6:00 AM')
            self.assertEqual(plantilla.hora_12(time(13, 30)), '1:30 PM')
        self.assertEqual(idioma_actual(), 'es')
        self.assertEqual(plantilla.dia_largo(date(2026, 12, 7)), 'Lunes 7 de diciembre')
        self.assertEqual(plantilla.hora_12(time(6, 0)), '6:00 a. m.')

    def test_un_codigo_desconocido_es_espanol(self):
        with en_idioma('fr'):
            self.assertEqual(idioma_actual(), 'es')
        self.assertEqual(idioma_de(object()), 'es')


@override_settings(**LLAVES)
class CorreosEnInglesTests(_Base):
    def en_ingles(self, **cambios):
        datos = dict(
            idioma='en', nombre_cliente='John Smith', fecha=date(2026, 12, 7), hora=time(6, 0),
            precio_total=Decimal('13907.00'), monto_pagado=Decimal('4172.10'),
            forma_pago=Reserva.FormaPago.ANTICIPO,
        )
        datos.update(cambios)
        return self.reserva(servicio=self.servicio_de(nombre_en='Sportfishing', punto_salida='Marina La Costa'), **datos)

    def sin_espanol(self, texto):
        for frase in SOLO_ESPANOL:
            self.assertNotIn(frase, texto, f'«{frase}» se colo en un correo en ingles')

    @mock.patch('apps.notifications.services.requests.post')
    def test_la_confirmacion(self, post):
        reserva = self.en_ingles()

        self.assertTrue(services.enviar_correo_confirmacion(reserva))

        enviado = _enviado(post)
        texto = enviado['text']
        self.assertEqual(enviado['subject'], f'Booking confirmed #{reserva.pk} — 2026-12-07 06:00')
        self.assertIn('<html lang="en">', enviado['html'])
        for frase in (
            'BOOKING CONFIRMED', "Hi John Smith, you're booked.", 'Sportfishing', 'WHAT YOU BOOKED',
            'Monday, December 7', '6:00 AM', 'Arrive by', '5:45 AM (15 minutes early)', 'Departs from',
            'Marina La Costa', 'Guests', 'Paid today', '9734.90 MXN left to pay in cash on the day of your trip.',
            "You'll get a second email with your captain's name", 'IF PLANS CHANGE', 'If the weather turns',
            'Change your date at no cost up to 48 hours before departure.', 'Keep this email as your booking record.',
        ):
            self.assertIn(frase, texto)
        self.sin_espanol(texto)
        self.assertEqual(idioma_actual(), 'es')

    @mock.patch('apps.notifications.services.requests.post')
    def test_la_asignacion_de_capitan(self, post):
        panga, capitan = self.panga_y_capitan()
        reserva = self.en_ingles(embarcacion=panga, capitan=capitan)

        self.assertTrue(services.enviar_correo_asignacion(reserva))

        enviado = _enviado(post)
        self.assertEqual(enviado['subject'], f'Your captain and panga #{reserva.pk} — 2026-12-07 06:00')
        for frase in ('YOUR CAPTAIN: RAMON', 'Hi John Smith, your captain and panga are set.', 'Departure',
                      'Captain', 'Be there 15 minutes before departure.',
                      'You still have 9734.90 MXN to pay in cash on the day of your trip.'):
            self.assertIn(frase, enviado['text'])
        self.sin_espanol(enviado['text'])

    @mock.patch('apps.notifications.correo_reagendado.requests.post')
    def test_el_reagendado(self, post):
        reserva = self.en_ingles()

        self.assertTrue(enviar_correo_reagendado(reserva, Antes(fecha=date(2026, 12, 1))))

        enviado = _enviado(post)
        self.assertEqual(enviado['subject'], f'Booking rescheduled #{reserva.pk} — 2026-12-07 06:00')
        for frase in ('BOOKING RESCHEDULED', 'Hi John Smith, your booking has a new date.', 'YOUR NEW DATE',
                      'Before', 'Tuesday, December 1', 'Now', 'Monday, December 7',
                      'Your payment carries over. There is nothing new to pay.'):
            self.assertIn(frase, enviado['text'])
        self.sin_espanol(enviado['text'])

    @mock.patch('apps.notifications.correo_recordatorio_saldo.requests.post')
    def test_el_recordatorio_de_saldo(self, post):
        reserva = self.en_ingles()

        self.assertTrue(enviar_correo_recordatorio_saldo(reserva))

        enviado = _enviado(post)
        self.assertEqual(enviado['subject'], f'Your trip is tomorrow #{reserva.pk}: 9,734.90 MXN left to pay')
        for frase in ('OUT TO SEA TOMORROW', 'Hi John Smith, the day is almost here.',
                      'You have 9,734.90 MXN left to pay.', 'You can pay it in cash tomorrow when you arrive.',
                      f'message us on WhatsApp with your booking number #{reserva.pk} and we will send you the details'):
            self.assertIn(frase, enviado['text'])
        self.sin_espanol(enviado['text'])

    @mock.patch('apps.notifications.services.requests.post')
    def test_el_reembolso_por_falta_de_cupo(self, post):
        reserva = self.en_ingles()

        with override_settings(FRONTEND_URL='https://sitio.example'):
            self.assertTrue(services.enviar_correo_reembolso_sin_cupo(reserva))

        enviado = _enviado(post)
        self.assertEqual(enviado['subject'], 'We could not hold your spot — 2026-12-07')
        self.assertIn('Hi John Smith,', enviado['html'])
        self.assertIn('We have already requested a full refund of 4172.10 MXN', enviado['html'])
        self.assertIn('Pick another date', enviado['html'])
        self.assertIn('https://sitio.example/en/reservar?', enviado['html'])

    @mock.patch('apps.notifications.services.requests.post')
    def test_sin_nombre_en_ingles_en_el_catalogo_usa_el_de_espanol(self, post):
        reserva = self.reserva(idioma='en', servicio=self.servicio_de(nombre='Pesca deportiva', nombre_en=''))

        services.enviar_correo_confirmacion(reserva)

        self.assertIn('Pesca deportiva', _enviado(post)['text'])


@override_settings(**LLAVES)
class QuienRecibeCadaIdiomaTests(_Base):
    @mock.patch('apps.notifications.services.requests.post')
    def test_quien_compro_en_espanol_recibe_espanol_aunque_su_telefono_sea_extranjero(self, post):
        reserva = self.reserva(idioma='es', telefono_cliente='+16195551234')

        services.enviar_correo_confirmacion(reserva)

        enviado = _enviado(post)
        self.assertTrue(enviado['subject'].startswith('Reserva confirmada'))
        self.assertIn('LO QUE RESERVASTE', enviado['text'])
        self.assertIn('<html lang="es">', enviado['html'])

    @mock.patch('apps.notifications.services.requests.post')
    def test_una_venta_a_mano_con_lada_extranjera_recibe_ingles(self, post):
        reserva = self.reserva(telefono_cliente='+16195551234')

        services.enviar_correo_confirmacion(reserva)

        self.assertTrue(_enviado(post)['subject'].startswith('Booking confirmed'))

    @mock.patch('apps.notifications.services.requests.post')
    def test_una_venta_a_mano_con_numero_nacional_recibe_espanol(self, post):
        reserva = self.reserva(telefono_cliente='6121234567')

        services.enviar_correo_confirmacion(reserva)

        self.assertTrue(_enviado(post)['subject'].startswith('Reserva confirmada'))


class PlantillaDeWhatsappTests(_Base):
    WHATSAPP = {'WHATSAPP_TOKEN': 't', 'WHATSAPP_PHONE_NUMBER_ID': '1', 'WHATSAPP_TEMPLATE_LANG': 'es_MX'}

    def idioma_enviado(self, reserva, **ajustes):
        with override_settings(**self.WHATSAPP, **ajustes), \
                mock.patch('apps.notifications.services.requests.post') as post:
            services.enviar_whatsapp_confirmacion(reserva)
        return post.call_args.kwargs['json']['template']['language']['code']

    def test_sin_plantilla_en_ingles_todos_reciben_la_de_siempre(self):
        self.assertEqual(self.idioma_enviado(self.reserva(idioma='en')), 'es_MX')

    def test_con_plantilla_en_ingles_la_recibe_solo_quien_compro_en_ingles(self):
        self.assertEqual(self.idioma_enviado(self.reserva(idioma='en'), WHATSAPP_TEMPLATE_LANG_EN='en_US'), 'en_US')
        self.assertEqual(
            self.idioma_enviado(self.reserva(idioma='es', fecha=date(2026, 12, 16)), WHATSAPP_TEMPLATE_LANG_EN='en_US'),
            'es_MX',
        )
