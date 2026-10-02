"""El tipo de cambio de la sede se congela en la reserva/orden al pasar a USD."""
import uuid
from datetime import date, time, timedelta
from decimal import Decimal

from apps.bookings.models import Orden, Reserva
from apps.fleet.models import Paquete, Servicio
from apps.testing import EmpresaTestCase


class TipoCambioCongeladoTests(EmpresaTestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca', tipo_servicio='pesca',
            precio_base=Decimal('4500.00'),
        )

    def reserva(self, moneda='MXN'):
        reserva = Reserva(
            empresa=self.empresa, servicio=self.servicio, checkout_id=uuid.uuid4(),
            fecha=date.today() + timedelta(days=10), hora=time(6), numero_personas=2,
            nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', moneda=moneda, canal_origen='web',
            deslinde_aceptado=True, deslinde_nombre='Ana Ruiz',
        )
        reserva.full_clean()
        reserva.save()
        return reserva

    def test_reserva_mxn_no_guarda_tipo_de_cambio(self):
        self.assertIsNone(self.reserva('MXN').tipo_cambio)

    def test_reserva_usd_guarda_el_de_la_sede(self):
        self.sede.tipo_cambio_usd = Decimal('17.5000')
        self.sede.save()
        self.assertEqual(self.reserva('USD').tipo_cambio, Decimal('17.5000'))

    def test_cambiar_la_sede_despues_no_mueve_la_reserva(self):
        reserva = self.reserva('USD')
        original = reserva.tipo_cambio
        self.sede.tipo_cambio_usd = Decimal('25.0000')
        self.sede.save()
        reserva.nombre_cliente = 'Ana Ruiz Perez'
        reserva.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.tipo_cambio, original)

    def test_pasar_de_usd_a_mxn_lo_limpia_y_volver_a_usd_toma_el_actual(self):
        reserva = self.reserva('USD')
        reserva.moneda = 'MXN'
        reserva.save()
        self.assertIsNone(reserva.tipo_cambio)
        self.sede.tipo_cambio_usd = Decimal('20.0000')
        self.sede.save()
        reserva.moneda = 'USD'
        reserva.save()
        self.assertEqual(reserva.tipo_cambio, Decimal('20.0000'))

    def test_la_reserva_de_una_orden_conserva_el_valor_que_le_pasan(self):
        reserva = self.reserva('USD')
        reserva.tipo_cambio = Decimal('19.0000')
        reserva.save()
        self.assertEqual(reserva.tipo_cambio, Decimal('19.0000'))
