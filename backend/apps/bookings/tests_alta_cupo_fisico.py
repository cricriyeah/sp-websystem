"""Venta manual de hospedaje y paquetes: aparta habitacion y componentes igual que el webhook.

Auditoria 2026-10-23, hallazgo critico 1: una reserva de hospedaje o paquete capturada a mano
como pagada no creaba `ReservaOcupacion` ni componentes, asi que la misma habitacion se podia
vender otra vez en la web. Estas pruebas fijan que el alta del admin pasa por la misma funcion
que el webhook (`reservar_cupo_al_confirmar`) y que, si ya no hay habitacion, el formulario
contesta con un error en espanol y no con un 500.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from apps.bookings.cupo import SinCupoError
from apps.bookings.cupo.adaptador import evaluar_disponibilidad_hospedaje
from apps.fleet.models import Paquete, PaqueteServicio, Recurso, Servicio
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .models import Reserva, ReservaOcupacion, ReservaPaqueteComponente, Vendedora


class AltaManualBase(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.pesca = crear_servicio_pesca(self.empresa)
        self.hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Cabaña', slug='cabana', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche', precio_base=Decimal('1500'),
        )
        self.habitacion = Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Cabaña 1', capacidad_maxima=4,
        )
        self.url = reverse('admin:bookings_reserva_add')
        self.usuario = self.crear_vendedora('vendedora-cupo-fisico')
        Vendedora.objects.create(
            usuario=self.usuario, empresa=self.empresa, codigo='vend-cupo-fisico', activo=True,
        )
        self.client.force_login(self.usuario)
        self.llegada = timezone.localdate() + timedelta(days=20)

    def datos(self, **extra):
        datos = {
            'nombre_cliente': 'Cliente Hotel',
            'telefono_cliente': '612 123 4567',
            'correo_cliente': 'hotel@example.com',
            'numero_personas': '2',
            'moneda': Reserva.Moneda.MXN,
            'ya_pago': 'todo_transferencia',
            'detalle_transporte-TOTAL_FORMS': '1',
            'detalle_transporte-INITIAL_FORMS': '0',
        }
        datos.update(extra)
        return datos

    def datos_hospedaje(self, **extra):
        return self.datos(
            servicio=str(self.hotel.pk), fecha=self.llegada.isoformat(),
            fecha_salida=(self.llegada + timedelta(days=3)).isoformat(),
            precio_total='4500.00', **extra,
        )


class HospedajeSueltoManualTests(AltaManualBase):
    def test_la_venta_pagada_a_mano_aparta_la_habitacion(self):
        respuesta = self.client.post(self.url, self.datos_hospedaje())
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and respuesta.context['adminform'].form.errors)

        reserva = Reserva.objects.get(nombre_cliente='Cliente Hotel')
        ocupacion = ReservaOcupacion.objects.get(reserva=reserva)
        self.assertEqual(ocupacion.recurso, self.habitacion)
        self.assertEqual(ocupacion.fecha_inicio, self.llegada)
        self.assertEqual(ocupacion.fecha_fin, self.llegada + timedelta(days=3))
        self.assertTrue(ocupacion.ocupa_cupo)

    def test_con_la_habitacion_apartada_la_web_ya_no_la_ve_libre(self):
        self.client.post(self.url, self.datos_hospedaje())

        libre = evaluar_disponibilidad_hospedaje(
            check_in=self.llegada, check_out=self.llegada + timedelta(days=3),
            personas=2, empresa=self.empresa, servicio=self.hotel,
        )
        self.assertFalse(libre)

    def test_la_misma_habitacion_no_se_vende_dos_veces_a_mano(self):
        self.client.post(self.url, self.datos_hospedaje())

        respuesta = self.client.post(self.url, self.datos_hospedaje(nombre_cliente='Segundo Cliente'))

        self.assertEqual(respuesta.status_code, 200)  # se vuelve a mostrar el formulario, no un 500
        errores = respuesta.context['adminform'].form.errors
        self.assertIn('fecha', errores)
        self.assertIn('No hay disponibilidad de hospedaje', str(errores['fecha']))
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Segundo Cliente').exists())

    def test_sin_pagar_no_aparta_habitacion(self):
        self.client.post(self.url, self.datos_hospedaje(ya_pago='no'))

        self.assertEqual(ReservaOcupacion.objects.count(), 0)

    def test_anticipo_tambien_aparta_la_habitacion(self):
        self.client.post(self.url, self.datos_hospedaje(ya_pago='anticipo_transferencia', monto_recibido='1000'))

        self.assertEqual(ReservaOcupacion.objects.filter(reserva__nombre_cliente='Cliente Hotel').count(), 1)

    def test_si_otra_venta_gana_la_habitacion_al_guardar_avisa_sin_romper(self):
        # La validacion del formulario pasa y, justo antes de guardar, otra venta se queda la habitacion.
        with mock.patch(
            'apps.bookings.admin.reservar_cupo_al_confirmar',
            side_effect=SinCupoError('No hay habitación disponible en esas fechas.'),
        ):
            respuesta = self.client.post(self.url, self.datos_hospedaje(), follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'No hay habitación disponible en esas fechas.')
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Cliente Hotel').exists())


class PaqueteManualTests(AltaManualBase):
    def setUp(self):
        super().setUp()
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Fin de semana', slug='finde',
            precio_ancla=Decimal('9500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.pesca, orden=1, dia_estancia=2, personas_incluidas=3,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.hotel, orden=2, noches=3, personas_incluidas=3,
        )

    def datos_paquete(self, **extra):
        return self.datos(
            paquete=str(self.paquete.pk), fecha=self.llegada.isoformat(), numero_personas='3',
            precio_total='9500.00', **extra,
        )

    def test_el_paquete_pagado_a_mano_crea_componentes_y_aparta_la_habitacion(self):
        respuesta = self.client.post(self.url, self.datos_paquete())
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and respuesta.context['adminform'].form.errors)

        reserva = Reserva.objects.get(nombre_cliente='Cliente Hotel')
        componentes = ReservaPaqueteComponente.objects.filter(reserva=reserva)
        self.assertEqual(
            {c.servicio_id for c in componentes}, {self.pesca.pk, self.hotel.pk},
        )
        self.assertTrue(all(c.estado_cupo == 'ok' for c in componentes))
        ocupacion = ReservaOcupacion.objects.get(reserva=reserva)
        self.assertEqual(ocupacion.recurso, self.habitacion)
        self.assertEqual(ocupacion.fecha_inicio, self.llegada)
        self.assertEqual(ocupacion.fecha_fin, self.llegada + timedelta(days=3))

    def test_las_fechas_del_paquete_salen_de_su_definicion_y_el_dia_de_inicio(self):
        self.client.post(self.url, self.datos_paquete())

        reserva = Reserva.objects.get(nombre_cliente='Cliente Hotel')
        self.assertEqual(reserva.inicio_paquete, self.llegada)
        self.assertEqual(reserva.fecha, self.llegada + timedelta(days=1))  # la pesca es el dia 2
        self.assertEqual(reserva.fecha_salida, self.llegada + timedelta(days=3))  # 3 noches

    def test_la_salida_tecleada_que_no_coincide_con_el_paquete_se_rechaza(self):
        respuesta = self.client.post(
            self.url, self.datos_paquete(fecha_salida=(self.llegada + timedelta(days=9)).isoformat()),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('fecha_salida', respuesta.context['adminform'].form.errors)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Cliente Hotel').exists())

    def test_el_alta_ya_no_pide_el_inicio_del_paquete_a_mano(self):
        respuesta = self.client.get(self.url)

        self.assertNotIn('inicio_paquete', respuesta.context['adminform'].form.fields)

    def test_el_paquete_no_se_vende_si_la_habitacion_ya_esta_tomada(self):
        self.client.post(self.url, self.datos_hospedaje())

        respuesta = self.client.post(self.url, self.datos_paquete(nombre_cliente='Paquete Tarde'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Paquete Tarde').exists())
