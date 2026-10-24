"""Un codigo promocional creado como lo crea la dueña funciona en el checkout.

Nace de la prueba A4 del 2026-10-23: creo un codigo en el backoffice SIN fecha limite, SIN
maximo de usos y SIN minimo, y el checkout no lo acepto. Aqui se recorre el camino completo
con el formulario real del admin (campos vacios incluidos): crear el codigo, validarlo en
vivo, cobrarlo en `crear-pago` y revalidarlo cuando entra el pago.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.test import Client, override_settings
from django.urls import reverse

from apps.bookings.models import Reserva
from apps.fleet.models import CodigoPromocional
from stripe import StripeClient
from apps.testing import ApiTestCase, crear_servicio_pesca

from .tests import CHECKOUT_ID, LLAVES, crear_reserva, evento_pagado, intent_falso


def formulario_del_admin(**campos):
    """Lo que manda el navegador al guardar el formulario con todo lo opcional vacio."""
    datos = {
        'codigo': 'SOL10',
        'descripcion': '',
        'porcentaje_descuento': '10',
        'activo': 'on',
        'fecha_inicio_0': '', 'fecha_inicio_1': '',
        'fecha_fin_0': '', 'fecha_fin_1': '',
        'usos_maximos': '',
        'usos_maximos_por_cliente': '',
        'monto_minimo': '',
        '_save': 'Guardar',
    }
    datos.update(campos)
    return datos


@override_settings(**LLAVES)
class CodigoCreadoDesdeElAdminTests(ApiTestCase):
    def setUp(self):
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.save(update_fields=[
            'stripe_secret_key', 'stripe_publishable_key', 'stripe_webhook_secret',
        ])
        self.servicio = crear_servicio_pesca(
            self.empresa, precio_base=Decimal('4500.00'), precio_persona_extra=Decimal('0'),
        )
        self.reserva = crear_reserva(self.empresa, servicio=self.servicio)

        self.admin = Client()
        self.admin.force_login(self.crear_jefe())
        self.publico = Client()

    def crear_codigo(self, **campos):
        respuesta = self.admin.post(
            reverse('admin:fleet_codigopromocional_add'), formulario_del_admin(**campos),
        )
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context_data', None) and
                         respuesta.context_data['adminform'].form.errors)
        return CodigoPromocional.objects.get(empresa=self.empresa)

    def validar(self, codigo, correo='ana@example.com', subtotal='4500.00'):
        return self.publico.get(
            reverse('codigo-promocional-validar', kwargs={'empresa_slug': self.empresa.slug}),
            {'codigo': codigo, 'correo_cliente': correo, 'subtotal': subtotal},
        ).json()

    def pagar(self, **cuerpo):
        datos = {'forma_pago': 'completo', 'checkout_id': str(self.reserva.checkout_id)}
        datos.update(cuerpo)
        return self.publico.post(
            reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': self.reserva.pk}),
            datos, content_type='application/json',
        )

    def test_el_formulario_vacio_guarda_un_codigo_sin_ningun_limite(self):
        promo = self.crear_codigo()

        self.assertEqual(promo.codigo, 'SOL10')
        self.assertTrue(promo.activo)
        self.assertIsNone(promo.fecha_inicio)
        self.assertIsNone(promo.fecha_fin)
        self.assertIsNone(promo.usos_maximos)
        self.assertIsNone(promo.usos_maximos_por_cliente)
        self.assertIsNone(promo.monto_minimo)

    def test_el_checkout_lo_valida_en_vivo(self):
        self.crear_codigo()

        self.assertEqual(
            self.validar('SOL10'),
            {'valido': True, 'porcentaje_descuento': '10.00', 'descuento': '450.00'},
        )

    def test_el_checkout_lo_valida_sin_correo_porque_el_cliente_aun_no_lo_escribe(self):
        self.crear_codigo()

        self.assertTrue(self.validar('SOL10', correo='')['valido'])

    def test_escrito_en_minusculas_y_con_espacios(self):
        self.crear_codigo(codigo=' sol10 ')

        for escrito in ('sol10', ' SOL10 ', 'Sol10'):
            with self.subTest(escrito=escrito):
                self.assertTrue(self.validar(escrito)['valido'])

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_crear_pago_aplica_el_descuento(self, payment_intents):
        payment_intents.create.return_value = intent_falso(amount=405000)
        self.crear_codigo()

        respuesta = self.pagar(codigo_promocional='SOL10')

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()['monto_a_cobrar'], '4050.00')
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.codigo_promocional.codigo, 'SOL10')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_crear_pago_en_dolares_con_un_codigo_sin_minimo(self, payment_intents):
        reserva = crear_reserva(
            self.empresa, servicio=self.servicio, moneda='USD',
            checkout_id='33333333-3333-4333-8333-333333333333',
        )
        payment_intents.create.return_value = intent_falso(amount=1000, currency='usd')
        self.crear_codigo()

        respuesta = self.publico.post(
            reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk}),
            {'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id),
             'codigo_promocional': 'SOL10'},
            content_type='application/json',
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_el_webhook_no_lo_rechaza_al_confirmar_el_pago(self, payment_intents):
        payment_intents.create.return_value = intent_falso(id='pi_promo', amount=405000)
        self.crear_codigo()
        self.assertEqual(self.pagar(codigo_promocional='SOL10').status_code, 200)

        with mock.patch('stripe.Webhook.construct_event', return_value=evento_pagado(
            self.reserva.pk, intent_id='pi_promo', amount=405000,
        )):
            respuesta = self.publico.post(
                reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                '{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='falsa',
            )

        self.assertEqual(respuesta.status_code, 200)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.PAGADA)
        self.assertFalse(self.reserva.reembolsada)

    def test_el_mismo_cliente_puede_usarlo_en_otra_reserva_si_no_hay_limite(self):
        promo = self.crear_codigo()
        crear_reserva(
            self.empresa, servicio=self.servicio, codigo_promocional=promo,
            estado=Reserva.Estado.PAGADA, fecha=date.today() + timedelta(days=20),
            checkout_id='44444444-4444-4444-8444-444444444444',
        )

        self.assertTrue(self.validar('SOL10')['valido'])
