from datetime import date, time
from decimal import Decimal

from apps.bookings.models import Reserva, ReservaPersonalizacion
from apps.fleet.models import Personalizacion, Servicio, ServicioPersonalizacion
from apps.payments.extras import congelar_personalizaciones, cotizar_personalizaciones
from apps.testing import ApiTestCase


class ExtrasModuloTests(ApiTestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Tour', slug='tour-em', tipo_servicio='otro',
            estrategia_cupo='bajo_demanda', estrategia_precio='tarifa_fija', precio_base=Decimal('1000.00'),
        )
        check = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Brunch', tipo_interaccion='check', cobrar_por_persona=True,
        )
        self.sp = ServicioPersonalizacion.objects.create(
            servicio=self.servicio, personalizacion=check, precio=Decimal('100.00'), precio_usd=Decimal('6.00'),
        )
        self.reserva = Reserva.objects.create(
            empresa=self.empresa, servicio=self.servicio, fecha=date(2026, 11, 1), hora=time(9),
            numero_personas=3, nombre_cliente='Ana', telefono_cliente='1234567890',
            correo_cliente='ana@example.com', moneda='MXN', estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        self.fila = ReservaPersonalizacion.objects.create(reserva=self.reserva, servicio_personalizacion=self.sp)

    def test_cotiza_por_persona_sin_escribir(self):
        cargo, a_borrar, a_congelar, error = cotizar_personalizaciones(self.reserva)
        self.assertIsNone(error)
        self.assertEqual(cargo, Decimal('300.00'))
        self.assertEqual(a_borrar, [])
        self.fila.refresh_from_db()
        self.assertIsNone(self.fila.precio_unitario)  # cotizar no escribe

    def test_congelar_guarda_precio_y_cantidad(self):
        _, a_borrar, a_congelar, _ = cotizar_personalizaciones(self.reserva)
        congelar_personalizaciones(a_borrar, a_congelar)
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.precio_unitario, Decimal('100.00'))
        self.assertEqual(self.fila.cantidad, 3)

    def test_sin_precio_en_la_moneda_devuelve_error(self):
        self.sp.precio_usd = None
        self.sp.save(update_fields=['precio_usd'])
        self.reserva.moneda = 'USD'
        _, _, _, error = cotizar_personalizaciones(self.reserva)
        self.assertIn('USD', error)
