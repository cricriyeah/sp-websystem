"""El servidor rechaza el pago de anticipo cuando el producto no lo admite."""
from apps.payments.tests import TrasladoPagoFixture
from apps.testing import ApiTestCase


class AnticipoNoPermitidoTest(TrasladoPagoFixture, ApiTestCase):
    def test_servicio_sin_anticipo_rechaza_forma_pago_anticipo(self):
        self.servicio.permite_anticipo = False
        self.servicio.save(update_fields=['permite_anticipo'])
        respuesta = self.post(self.reserva(), forma_pago='anticipo')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('anticipo', respuesta.json()['detail'].lower())

    def test_servicio_sin_anticipo_acepta_pago_completo(self):
        self.servicio.permite_anticipo = False
        self.servicio.save(update_fields=['permite_anticipo'])
        respuesta = self.post(self.reserva(), forma_pago='completo')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['monto_a_cobrar'], '4500.00')

    def test_servicio_con_anticipo_cobra_solo_el_porcentaje(self):
        self.servicio.permite_anticipo = True
        self.servicio.porcentaje_anticipo = 30
        self.servicio.save(update_fields=['permite_anticipo', 'porcentaje_anticipo'])
        respuesta = self.post(self.reserva(), forma_pago='anticipo')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['monto_a_cobrar'], '1350.00')
