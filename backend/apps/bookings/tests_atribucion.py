"""De dónde llegó el cliente: lo que manda el navegador se limpia, se guarda y nunca rompe el checkout."""
from datetime import date, timedelta

from django.test import SimpleTestCase

from apps.testing import ApiTestCase, crear_servicio_pesca

from . import atribucion
from .models import Reserva


class LimpiarTests(SimpleTestCase):
    def test_solo_pasan_las_claves_conocidas_como_texto(self):
        limpio = atribucion.limpiar({
            'utm_source': ' facebook ', 'utm_campaign': 'semana-santa', 'fbclid': 'abc',
            'precio_total': '1', 'utm_medium': 3, 'utm_term': '', 'landing': '/es/sede/la-paz',
        })
        self.assertEqual(limpio, {'utm_source': 'facebook', 'utm_campaign': 'semana-santa', 'fbclid': 'abc',
                                  'landing': '/es/sede/la-paz'})

    def test_recorta_lo_largo_y_tolera_basura(self):
        self.assertEqual(len(atribucion.limpiar({'utm_source': 'x' * 5000})['utm_source']), atribucion.LARGO_MAXIMO)
        for basura in (None, 'texto', [1, 2], 7):
            self.assertEqual(atribucion.limpiar(basura), {})

    def test_resumen_para_el_admin(self):
        self.assertEqual(atribucion.resumen({'utm_source': 'ig', 'utm_medium': 'paid', 'utm_campaign': 'orcas'}),
                         'Meta · paid · orcas')
        self.assertEqual(atribucion.resumen({'gclid': 'x'}), 'Google')
        self.assertEqual(atribucion.resumen({'fbclid': 'x'}), 'Meta')
        self.assertEqual(atribucion.resumen({'referrer': 'tripadvisor.com'}), 'Llegó desde tripadvisor.com')
        self.assertEqual(atribucion.resumen({}), '')


class AtribucionEnLaReservaWebTests(ApiTestCase):
    CHECKOUT_ID = '22222222-2222-4222-8222-222222222222'

    def enviar(self, **extra):
        servicio = crear_servicio_pesca(self.empresa)
        datos = {
            'checkout_id': self.CHECKOUT_ID,
            'fecha': str(date.today() + timedelta(days=10)), 'hora': '06:00', 'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz', 'telefono_cliente': '+5216121234567', 'correo_cliente': 'ana@example.com',
            'moneda': 'MXN', 'deslinde_aceptado': True, 'deslinde_nombre': 'Ana Ruiz', 'servicio': servicio.slug,
            **extra,
        }
        return self.client.post(f'/api/{self.empresa.slug}/reservas/', datos, content_type='application/json')

    def test_se_guarda_limpia(self):
        respuesta = self.enviar(atribucion={'utm_source': 'facebook', 'fbclid': 'abc', 'otra': 'no'})
        self.assertEqual(respuesta.status_code, 201)
        reserva = Reserva.objects.get(pk=respuesta.json()['id'])
        self.assertEqual(reserva.atribucion, {'utm_source': 'facebook', 'fbclid': 'abc'})
        self.assertNotIn('atribucion', respuesta.json())

    def test_basura_no_rompe_el_checkout(self):
        self.assertEqual(self.enviar(atribucion='no soy un objeto').status_code, 201)

    def test_reenviar_sin_atribucion_no_borra_la_que_habia(self):
        primera = self.enviar(atribucion={'utm_source': 'google'})
        self.enviar()
        self.assertEqual(Reserva.objects.get(pk=primera.json()['id']).atribucion, {'utm_source': 'google'})
