"""IVA del cobro en linea: se suma al final, Stripe cobra el total y el anticipo
se calcula sobre ese total. Los precios del catalogo van sin IVA."""
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from stripe import StripeClient

from apps.bookings.models import Reserva
from apps.fleet.models import CodigoPromocional
from apps.testing import ApiTestCase, crear_servicio_pesca

from .pricing import calcular_iva, con_iva, monto_inicial, tasa_iva
from .tests import LLAVES, crear_reserva, intent_falso
from .tests_orden_paquete import OrdenPaqueteBase

IVA_16 = Decimal('0.16')


@override_settings(IVA_TASA=IVA_16)
class CalculoIvaTests(SimpleTestCase):
    def test_tasa_sale_de_settings(self):
        self.assertEqual(tasa_iva(), IVA_16)

    def test_iva_se_suma_al_final(self):
        self.assertEqual(con_iva(Decimal('4500.00')), (Decimal('720.00'), Decimal('5220.00')))

    def test_iva_redondea_a_centavos(self):
        # 3333.33 * 0.16 = 533.3328
        self.assertEqual(calcular_iva(Decimal('3333.33')), Decimal('533.33'))

    def test_el_anticipo_es_el_30_por_ciento_del_total_con_iva(self):
        _, total = con_iva(Decimal('12000.00'))
        self.assertEqual(total, Decimal('13920.00'))
        self.assertEqual(monto_inicial(total, 'anticipo'), Decimal('4176.00'))

    @override_settings(IVA_TASA=Decimal('0'))
    def test_tasa_cero_no_cambia_el_precio(self):
        self.assertEqual(con_iva(Decimal('4500.00')), (Decimal('0.00'), Decimal('4500.00')))

    def test_tasa_explicita_gana_sobre_settings(self):
        self.assertEqual(con_iva(Decimal('100.00'), Decimal('0.08')), (Decimal('8.00'), Decimal('108.00')))


@override_settings(IVA_TASA=IVA_16, **LLAVES)
class CrearPagoConIvaTests(ApiTestCase):
    def setUp(self):
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_publishable_key'])
        self.servicio = crear_servicio_pesca(
            self.empresa, precio_base=Decimal('4500.00'), precio_persona_extra=Decimal('500.00'),
        )
        self.reserva = crear_reserva(self.empresa, servicio=self.servicio)
        self.url = reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': self.reserva.pk})

    def post(self, **body):
        datos = {'forma_pago': 'completo', 'checkout_id': str(self.reserva.checkout_id)}
        datos.update(body)
        return self.client.post(self.url, datos, content_type='application/json')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_stripe_cobra_el_total_con_iva_y_la_reserva_guarda_el_desglose(self, payment_intents):
        payment_intents.create.return_value = intent_falso(amount=522000)

        response = self.post()

        self.assertEqual(response.status_code, 200, response.content)
        cuerpo = response.json()
        self.assertEqual(cuerpo['monto_a_cobrar'], '5220.00')
        self.assertEqual(cuerpo['precio_total'], '5220.00')
        self.assertEqual(cuerpo['iva'], '720.00')
        self.assertEqual(cuerpo['iva_tasa'], '0.16')
        self.assertEqual(payment_intents.create.call_args.args[0]['amount'], 522000)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.precio_total, Decimal('5220.00'))
        self.assertEqual(self.reserva.iva_monto, Decimal('720.00'))
        self.assertEqual(self.reserva.iva_tasa, IVA_16)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_anticipo_es_el_30_por_ciento_del_total_con_iva(self, payment_intents):
        payment_intents.create.return_value = intent_falso(amount=156600)

        response = self.post(forma_pago='anticipo')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['monto_a_cobrar'], '1566.00')  # 5220 * 0.30
        self.assertEqual(response.json()['precio_total'], '5220.00')
        self.assertEqual(payment_intents.create.call_args.args[0]['amount'], 156600)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_el_descuento_va_antes_del_iva(self, payment_intents):
        payment_intents.create.return_value = intent_falso(amount=469800)
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=Decimal('10'),
        )

        response = self.post(codigo_promocional='VERANO10')

        # 4500 - 10 % = 4050; IVA 648; total 4698.
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['iva'], '648.00')
        self.assertEqual(response.json()['monto_a_cobrar'], '4698.00')
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.descuento_aplicado, Decimal('450.00'))
        # El motor de promociones sigue viendo el subtotal sin IVA: no se rechaza al guardar.
        self.reserva.full_clean()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_el_cliente_no_puede_poner_su_propio_iva(self, payment_intents):
        payment_intents.create.return_value = intent_falso(amount=522000)

        response = self.post(iva='0', iva_tasa='0', precio_total='4500')

        self.assertEqual(response.json()['monto_a_cobrar'], '5220.00')

    @override_settings(IVA_TASA=Decimal('0'))
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_con_tasa_cero_cobra_el_precio_del_catalogo(self, payment_intents):
        payment_intents.create.return_value = intent_falso(amount=450000)

        response = self.post()

        self.assertEqual(response.json()['monto_a_cobrar'], '4500.00')
        self.assertEqual(response.json()['iva'], '0.00')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_pago_completo_recibido_cuadra_con_el_total_con_iva(self, payment_intents):
        from .services import _verificar_monto

        payment_intents.create.return_value = intent_falso(amount=522000)
        self.post()
        self.reserva.refresh_from_db()
        with self.assertNoLogs('apps.payments.services', level='ERROR'):
            _verificar_monto(
                self.reserva, {'currency': 'mxn', 'amount_received': 522000},
            )


class OrdenConIvaTests(OrdenPaqueteBase):
    def _stripe_falso(self):
        clientes = {}

        def para(empresa):
            if empresa.id not in clientes:
                cliente = mock.Mock()
                cliente.payment_intents.create.side_effect = lambda params, options: mock.Mock(
                    id=f'pi_{empresa.id}', client_secret=f'pi_{empresa.id}_sec',
                    amount=params['amount'], currency=params['currency'], status='requires_payment_method',
                )
                clientes[empresa.id] = cliente
            return clientes[empresa.id]
        return para, clientes

    @override_settings(IVA_TASA=IVA_16)
    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_cada_empresa_cobra_su_neto_mas_su_iva(self, configurar):
        para, clientes = self._stripe_falso()
        configurar.side_effect = para
        creada = self.crear().json()
        orden_id = creada['orden_id']

        respuesta = self.client.post(
            f'/api/{self.sede.slug}/ordenes/{orden_id}/crear-pago/',
            {'checkout_id': creada['checkout_id']}, content_type='application/json',
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        pagos = {p['empresa_slug']: p for p in respuesta.json()}
        # Netos sin IVA: pesca 6400, transporte 1650 (ver CrearPagoOrdenTests).
        self.assertEqual(pagos['pesca-op']['monto'], '7424.00')
        self.assertEqual(pagos['pesca-op']['iva'], '1024.00')
        self.assertEqual(pagos['transp-op']['monto'], '1914.00')
        self.assertEqual(pagos['transp-op']['iva'], '264.00')
        cobrado = {
            e: c.payment_intents.create.call_args.args[0]['amount'] for e, c in clientes.items()
        }
        self.assertEqual(sorted(cobrado.values()), [191400, 742400])
        from apps.tenancy import scope
        with scope.como_operador_plataforma():
            reserva = Reserva.objects.get(orden_id=orden_id, empresa=self.pesca)
        self.assertEqual(reserva.precio_total, Decimal('7424.00'))
        self.assertEqual(reserva.iva_monto, Decimal('1024.00'))
        self.assertEqual(reserva.iva_tasa, IVA_16)
