"""Precio sugerido del hospedaje suelto en el alta manual: noches x habitaciones.

Antes `sugerir_precio` nunca recibia la salida y cotizaba SIEMPRE una noche de una habitacion.
"""
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse

from apps.fleet.models import Recurso

from .precio_sugerido import sugerir_precio
from .tests_alta_cupo_fisico import AltaManualBase


class PrecioSugeridoDeHospedajeTests(AltaManualBase):
    def setUp(self):
        super().setUp()
        Recurso.objects.filter(pk=self.habitacion.pk).update(capacidad_maxima=2)
        Recurso.objects.create(empresa=self.empresa, servicio=self.hotel, nombre='Cabaña 2', capacidad_maxima=2)
        Recurso.objects.create(empresa=self.empresa, servicio=self.hotel, nombre='Cabaña 3', capacidad_maxima=2)
        self.salida = self.llegada + timedelta(days=3)

    def sugerido(self, personas, **extra):
        return sugerir_precio(
            servicio=self.hotel, numero_personas=personas, moneda='MXN', fecha=self.llegada,
            fecha_salida=self.salida, **extra,
        )

    def test_cotiza_las_noches_de_la_estancia(self):
        self.assertEqual(self.sugerido(2), Decimal('4500.00'))  # 3 noches x 1 habitacion x 1500

    def test_cotiza_una_habitacion_por_cada_dos_personas(self):
        self.assertEqual(self.sugerido(5), Decimal('13500.00'))  # 3 noches x 3 habitaciones x 1500

    def test_sin_salida_cotiza_una_noche(self):
        precio = sugerir_precio(
            servicio=self.hotel, numero_personas=2, moneda='MXN', fecha=self.llegada,
        )
        self.assertEqual(precio, Decimal('1500.00'))

    def test_acepta_las_fechas_como_texto_del_endpoint(self):
        precio = sugerir_precio(
            servicio=self.hotel, numero_personas=3, moneda='MXN', fecha=self.llegada.isoformat(),
            fecha_salida=self.salida.isoformat(),
        )
        self.assertEqual(precio, Decimal('9000.00'))  # 3 noches x 2 habitaciones

    def test_el_endpoint_del_admin_recibe_la_salida(self):
        respuesta = self.client.get(reverse('admin:bookings_reserva_precio_sugerido'), {
            'servicio': self.hotel.pk, 'personas': 5, 'moneda': 'MXN',
            'fecha': self.llegada.isoformat(), 'fecha_salida': self.salida.isoformat(),
        })

        self.assertEqual(respuesta.json()['precio'], '13500.00')

    def test_el_alta_sin_precio_rellena_el_total_de_toda_la_estancia(self):
        respuesta = self.client.post(self.url, self.datos(
            servicio=str(self.hotel.pk), fecha=self.llegada.isoformat(), fecha_salida=self.salida.isoformat(),
            numero_personas='5', precio_total='',
        ))
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and respuesta.context['adminform'].form.errors)

        from .models import Reserva
        reserva = Reserva.objects.get(nombre_cliente='Cliente Hotel')
        self.assertEqual(reserva.precio_total, Decimal('13500.00'))
