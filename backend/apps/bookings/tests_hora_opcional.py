"""La hora de salida es opcional: un paquete que no la pide (pide_hora=False) guarda la reserva sin hora."""
import uuid
from datetime import date

from apps.bookings.models import Reserva
from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.fleet.models import Paquete
from apps.notifications.services import hora_texto
from apps.testing import OperadorTestCase

from .tests_paquete_estancia import FixturePaqueteEstancia


class HoraOpcionalTests(FixturePaqueteEstancia, OperadorTestCase):
    def setUp(self):
        self.sembrar()

    def payload(self, **extra):
        datos = {
            'checkout_id': str(uuid.uuid4()), 'fecha': '2026-10-10', 'hora': '06:00:00',
            'numero_personas': 3, 'nombre_cliente': 'Ana Ruiz', 'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com', 'moneda': 'MXN', 'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz', 'paquete': self.paquete.slug, 'personalizaciones': [],
            'personas_por_servicio': {str(self.pesca.pk): 3, str(self.hotel.pk): 2},
        }
        datos.update(extra)
        return datos

    def validar(self, quitar_hora=False, **extra):
        datos = self.payload(**extra)
        if quitar_hora:
            datos.pop('hora')
        serializador = ReservaCheckoutSerializer(data=datos, context={'empresa': self.empresa})
        return serializador, serializador.is_valid()

    def sin_hora(self):
        Paquete.objects.filter(pk=self.paquete.pk).update(pide_hora=False)
        self.paquete.refresh_from_db()

    def test_por_defecto_el_paquete_pide_hora(self):
        self.assertTrue(self.paquete.pide_hora)

    def test_paquete_que_pide_hora_la_exige(self):
        serializador, valido = self.validar(quitar_hora=True)
        self.assertFalse(valido)
        self.assertIn('hora', serializador.errors)

    def test_paquete_que_no_pide_hora_acepta_la_reserva_sin_hora(self):
        self.sin_hora()
        serializador, valido = self.validar(quitar_hora=True)
        self.assertTrue(valido, serializador.errors)
        self.assertIsNone(serializador.validated_data['hora'])

    def test_paquete_que_no_pide_hora_descarta_la_que_llegue(self):
        self.sin_hora()
        serializador, valido = self.validar(hora='06:00:00')
        self.assertTrue(valido, serializador.errors)
        self.assertIsNone(serializador.validated_data['hora'])

    def test_servicio_suelto_sin_hora_sigue_siendo_invalido(self):
        serializador, valido = self.validar(
            quitar_hora=True, paquete=None, servicio=self.pesca.slug, personas_por_servicio={},
        )
        self.assertFalse(valido)
        self.assertIn('hora', serializador.errors)

    def test_reserva_sin_hora_se_guarda_y_su_salida_cuenta_desde_el_inicio_del_dia(self):
        reserva = self.reserva(hora=None)
        reserva.save()
        reserva.refresh_from_db()
        self.assertIsNone(reserva.hora)
        self.assertEqual(reserva.salida.date(), date(2026, 10, 11))
        self.assertEqual(reserva.salida.hour, 0)

    def test_el_texto_de_la_hora_dice_por_definir_cuando_no_hay(self):
        self.assertEqual(hora_texto(self.reserva(hora=None)), 'por definir')
        self.assertEqual(hora_texto(self.reserva()), '06:00')
