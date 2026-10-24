"""Hospedaje suelto: el precio es noches x habitaciones, no una sola habitacion.

Auditoria 2026-10-23 (latente: hoy el hotel real solo se vende dentro de paquetes): `PorNoche`
cobraba `precio_base x noches` aunque el grupo necesitara varias habitaciones.
"""
import uuid
from datetime import date, time
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from stripe import StripeClient

from apps.bookings.models import Reserva
from apps.fleet.models import Recurso, Servicio
from apps.testing import ApiTestCase

from .estrategias_precio import DemandaPrecio, PorNoche, habitaciones_para_precio


class PorNocheConHabitacionesTests(ApiTestCase):
    def setUp(self):
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_publishable_key'])
        self.hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Hotel', slug='hotel-hab', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche', precio_base=Decimal('1500.00'),
        )

    def habitaciones(self, *capacidades, activas=True):
        for i, cap in enumerate(capacidades, start=1):
            Recurso.objects.create(
                empresa=self.empresa, servicio=self.hotel, nombre=f'H{i}', capacidad_maxima=cap, activo=activas,
            )

    def test_la_estrategia_multiplica_noches_por_habitaciones(self):
        demanda = DemandaPrecio(personas=5, noches=3, habitaciones=2)
        self.assertEqual(PorNoche().calcular_base(self.hotel, demanda), Decimal('9000.00'))

    def test_sin_habitaciones_en_la_demanda_cobra_una(self):
        self.assertEqual(
            PorNoche().calcular_base(self.hotel, DemandaPrecio(personas=2, noches=3)), Decimal('4500.00'),
        )

    def test_habitaciones_necesarias_salen_de_las_capacidades_de_las_habitaciones_activas(self):
        self.habitaciones(2, 2, 2)
        self.assertEqual(habitaciones_para_precio(self.hotel, 2), 1)
        self.assertEqual(habitaciones_para_precio(self.hotel, 3), 2)
        self.assertEqual(habitaciones_para_precio(self.hotel, 5), 3)

    def test_una_habitacion_inactiva_no_cuenta(self):
        self.habitaciones(2, 2)
        Recurso.objects.filter(nombre='H2').update(activo=False)
        self.assertEqual(habitaciones_para_precio(self.hotel, 2), 1)

    def test_sin_habitaciones_configuradas_o_que_no_alcanzan_cobra_una(self):
        self.assertEqual(habitaciones_para_precio(self.hotel, 4), 1)
        self.habitaciones(2)
        self.assertEqual(habitaciones_para_precio(self.hotel, 9), 1)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_crear_pago_cobra_las_habitaciones_que_necesita_el_grupo(self, payment_intents):
        payment_intents.create.return_value = mock.Mock(
            id='pi_hab', amount=900000, currency='mxn', status='requires_payment_method', client_secret='s',
        )
        self.habitaciones(2, 2, 2)
        reserva = Reserva.objects.create(
            empresa=self.empresa, servicio=self.hotel, fecha=date(2026, 10, 1), fecha_salida=date(2026, 10, 3),
            hora=time(7, 0), numero_personas=5, nombre_cliente='Juan Perez', telefono_cliente='1234567890',
            correo_cliente='juan@test.com', moneda='MXN', estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=uuid.uuid4(),
        )
        url = reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk})

        respuesta = self.client.post(
            url, {'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)}, content_type='application/json',
        )

        self.assertEqual(respuesta.status_code, 200)
        # 2 noches x 3 habitaciones (5 personas, de a 2) x 1500
        self.assertEqual(respuesta.json()['monto_a_cobrar'], '9000.00')
        reserva.refresh_from_db()
        self.assertEqual(reserva.precio_total, Decimal('9000.00'))
