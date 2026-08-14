"""Pruebas de las confirmaciones al cliente.

Lo que se protege aqui es que ninguna falla de notificacion tumbe el cobro (el
webhook de Stripe ya recibio el dinero cuando esto corre) y que la copia al
negocio salga oculta y solo cuando esta configurada.
"""
from datetime import date, time, timedelta
from unittest import mock

import requests
from django.test import TestCase, override_settings

from apps.bookings.models import Reserva

from .services import enviar_correo_confirmacion, notificar_reserva_pagada

LLAVES = {'RESEND_API_KEY': 'test-key', 'RESEND_FROM': 'reservas@ejemplo.com'}


def crear_reserva():
    return Reserva(
        fecha=date.today() + timedelta(days=10),
        hora=time(6, 0),
        numero_personas=2,
        nombre_cliente='Ana Ruiz',
        telefono_cliente='+5216121234567',
        correo_cliente='ana@example.com',
        moneda='MXN',
        deslinde_aceptado=True,
        deslinde_nombre='Ana Ruiz',
    )


def _cuerpo_enviado(post):
    """El json= de la llamada a Resend."""
    return post.call_args.kwargs['json']


@override_settings(**LLAVES, RESEND_BCC=['operacion@ejemplo.com'])
class CopiaAlNegocioTests(TestCase):
    """La copia existe para tener un rastro fuera de la base de datos: si hay que
    restaurar un respaldo y se pierde medio dia de reservas, en ese buzon queda a
    quien hablarle (ver docs/vendors/supabase.md)."""

    @mock.patch('apps.notifications.services.requests.post')
    def test_manda_copia_al_negocio(self, post):
        post.return_value.raise_for_status.return_value = None

        self.assertTrue(enviar_correo_confirmacion(crear_reserva()))
        self.assertEqual(_cuerpo_enviado(post)['bcc'], ['operacion@ejemplo.com'])

    @mock.patch('apps.notifications.services.requests.post')
    def test_la_copia_va_oculta_no_en_el_para(self, post):
        """El cliente no tiene por que ver una direccion interna del negocio."""
        post.return_value.raise_for_status.return_value = None

        enviar_correo_confirmacion(crear_reserva())

        cuerpo = _cuerpo_enviado(post)
        self.assertEqual(cuerpo['to'], ['ana@example.com'])
        self.assertNotIn('operacion@ejemplo.com', cuerpo['to'])
        self.assertNotIn('cc', cuerpo)

    @mock.patch('apps.notifications.services.requests.post')
    def test_el_correo_lleva_lo_necesario_para_reconstruir_la_reserva(self, post):
        """Si esta copia va a servir de rastro, tiene que traer con que ubicar al
        cliente y saber cuando sale."""
        post.return_value.raise_for_status.return_value = None
        reserva = crear_reserva()

        enviar_correo_confirmacion(reserva)

        cuerpo = _cuerpo_enviado(post)
        self.assertIn(reserva.nombre_cliente, cuerpo['html'])
        self.assertIn(str(reserva.fecha), cuerpo['html'])
        self.assertIn('06:00', cuerpo['html'])
        self.assertIn(str(reserva.numero_personas), cuerpo['html'])
        self.assertIn(reserva.correo_cliente, cuerpo['to'])


@override_settings(**LLAVES, RESEND_BCC=[])
class SinCopiaConfiguradaTests(TestCase):
    @mock.patch('apps.notifications.services.requests.post')
    def test_sin_bcc_configurado_no_se_manda_la_clave(self, post):
        post.return_value.raise_for_status.return_value = None

        enviar_correo_confirmacion(crear_reserva())

        self.assertNotIn('bcc', _cuerpo_enviado(post))


@override_settings(**LLAVES, RESEND_BCC=['operacion@ejemplo.com'])
class FallosNoTumbanElCobroTests(TestCase):
    """El dinero ya entro cuando esto corre: un fallo aqui se registra y se sigue,
    nunca se propaga al webhook (haria que Stripe reintente el evento en bucle)."""

    @mock.patch('apps.notifications.services.requests.post')
    def test_si_resend_falla_devuelve_false_sin_lanzar(self, post):
        post.side_effect = requests.RequestException('resend caido')

        self.assertFalse(enviar_correo_confirmacion(crear_reserva()))

    @mock.patch('apps.notifications.services.requests.post')
    def test_notificar_no_lanza_aunque_los_dos_canales_fallen(self, post):
        post.side_effect = requests.RequestException('todo caido')

        resultado = notificar_reserva_pagada(crear_reserva())

        self.assertEqual(resultado, {'email': False, 'whatsapp': False})


@override_settings(RESEND_API_KEY='', RESEND_FROM='', RESEND_BCC=['operacion@ejemplo.com'])
class SinLlavesTests(TestCase):
    @mock.patch('apps.notifications.services.requests.post')
    def test_sin_llaves_de_resend_no_se_llama_a_la_red(self, post):
        """Config local: sin llaves no se manda nada y el cobro sigue igual."""
        self.assertFalse(enviar_correo_confirmacion(crear_reserva()))
        post.assert_not_called()
