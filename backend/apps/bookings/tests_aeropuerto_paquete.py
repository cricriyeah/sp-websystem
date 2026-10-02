"""Paquete de una empresa con hospedaje y traslado: la clienta elige el aeropuerto y queda en la reserva."""
from decimal import Decimal

from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.fleet.models import PaqueteServicio, Servicio
from apps.testing import OperadorTestCase

from .tests_paquete_estancia import FixturePaqueteEstancia


class AeropuertoDePaqueteTests(FixturePaqueteEstancia, OperadorTestCase):
    def setUp(self):
        self.sembrar()
        self.traslado = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado', slug='traslado-pe', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta', capacidad_maxima=14,
            solo_en_paquete=True,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.traslado, orden=3, dia_estancia=1, personas_incluidas=3,
        )

    def payload(self, **extra):
        datos = {
            'checkout_id': '6f1a5c3e-0000-4000-8000-000000000001', 'fecha': '2026-10-10', 'hora': '06:00:00',
            'numero_personas': 3, 'nombre_cliente': 'Ana Ruiz', 'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com', 'moneda': 'MXN', 'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz', 'paquete': self.paquete.slug, 'personalizaciones': [],
            'personas_por_servicio': {
                str(self.pesca.pk): 3, str(self.hotel.pk): 2, str(self.traslado.pk): 3,
            },
        }
        datos.update(extra)
        return datos

    def validar(self, **extra):
        serializador = ReservaCheckoutSerializer(data=self.payload(**extra), context={'empresa': self.empresa})
        return serializador, serializador.is_valid()

    def test_con_hospedaje_y_traslado_exige_el_aeropuerto(self):
        serializador, valido = self.validar()
        self.assertFalse(valido)
        self.assertIn('aeropuerto', serializador.errors)

    def test_con_aeropuerto_es_valido_y_viaja_en_los_datos(self):
        serializador, valido = self.validar(aeropuerto='sjd')
        self.assertTrue(valido, serializador.errors)
        self.assertEqual(serializador.validated_data['aeropuerto'], 'sjd')

    def test_un_aeropuerto_que_no_existe_se_rechaza(self):
        serializador, valido = self.validar(aeropuerto='xxx')
        self.assertFalse(valido)
        self.assertIn('aeropuerto', serializador.errors)

    def test_un_paquete_sin_traslado_no_pide_aeropuerto(self):
        PaqueteServicio.objects.filter(servicio=self.traslado).delete()
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 3, str(self.hotel.pk): 2})
        self.assertTrue(valido, serializador.errors)
