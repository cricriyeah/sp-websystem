"""Notas para el capitán: el cliente las escribe en el checkout y se guardan en su reserva."""
from datetime import date, timedelta

from apps.testing import ApiTestCase, crear_servicio_pesca

from . import tests_telefono
from .models import NOTAS_CLIENTE_MAX, Reserva


class NotasEnLaReservaWebTests(ApiTestCase):
    CHECKOUT_ID = '33333333-3333-4333-8333-333333333333'

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

    def test_se_guardan_sin_espacios_de_sobra(self):
        respuesta = self.enviar(notas_cliente='  Es el cumpleaños de mi papá  ')
        self.assertEqual(respuesta.status_code, 201)
        reserva = Reserva.objects.get(pk=respuesta.json()['id'])
        self.assertEqual(reserva.notas_cliente, 'Es el cumpleaños de mi papá')
        self.assertNotIn('notas_cliente', respuesta.json())

    def test_son_opcionales(self):
        respuesta = self.enviar()
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Reserva.objects.get(pk=respuesta.json()['id']).notas_cliente, '')

    def test_mas_largas_del_tope_se_rechazan(self):
        respuesta = self.enviar(notas_cliente='x' * (NOTAS_CLIENTE_MAX + 1))
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('notas_cliente', respuesta.json())

    def test_reenviar_sin_notas_no_borra_las_que_habia(self):
        primera = self.enviar(notas_cliente='Primera vez pescando')
        self.enviar()
        self.assertEqual(Reserva.objects.get(pk=primera.json()['id']).notas_cliente, 'Primera vez pescando')

    def test_reenviar_con_otras_notas_las_cambia(self):
        primera = self.enviar(notas_cliente='Primera vez pescando')
        self.enviar(notas_cliente='')
        self.assertEqual(Reserva.objects.get(pk=primera.json()['id']).notas_cliente, '')


class NotasEnLaOrdenTests(tests_telefono.OrdenConTelefonoInternacionalTests):
    """En un paquete de dos empresas la misma nota llega a la reserva de cada una (reusa el paquete de esa clase)."""

    def test_la_nota_se_copia_a_cada_reserva_de_la_orden(self):
        from unittest import mock

        from apps.tenancy import scope

        original = self.client.post

        def con_notas(url, datos, **kwargs):
            datos = {**datos, 'notas_cliente': '  Vamos con un niño de 8 años  '}
            return original(url, datos, **kwargs)

        with mock.patch.object(self.client, 'post', con_notas):
            respuesta = self.enviar('+5216121234567')
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        with scope.como_operador_plataforma():
            notas = set(Reserva.objects.filter(nombre_cliente='Carlos Lopez').values_list('notas_cliente', flat=True))
        self.assertEqual(notas, {'Vamos con un niño de 8 años'})
