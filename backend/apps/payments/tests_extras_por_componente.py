"""Un extra por persona multiplica por las personas de SU servicio."""
import uuid
from decimal import Decimal

from django.core.cache import cache
from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from apps.bookings.admin import CheckoutAbandonadoAdmin
from apps.bookings.models import CheckoutAbandonado, Reserva
from apps.bookings.tests_paquete_estancia import FixturePaqueteEstancia
from apps.fleet.models import Paquete, PaqueteServicio, Personalizacion, Servicio, ServicioPersonalizacion
from apps.payments.pricing import precio_paquete_total
from apps.notifications.services import _cuerpo_html
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class ExtrasPorComponenteTests(OperadorTestCase):
    def setUp(self):
        sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        empresa = Empresa.objects.create(sede=sede, nombre='Empresa EC', slug='empresa-ec')
        self.pesca = Servicio.objects.create(
            empresa=empresa, nombre='Pesca', slug='pesca-ec', tipo_servicio='pesca', precio_base=Decimal('4000.00'),
        )
        self.hotel = Servicio.objects.create(
            empresa=empresa, nombre='Cabaña', slug='cabana-ec', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche',
        )
        self.paquete = Paquete.objects.create(
            sede=sede, empresa_lider=empresa, nombre='P', slug='p-ec', precio_ancla=Decimal('9500.00'),
        )
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.pesca, orden=1, personas_incluidas=4)
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.hotel, orden=2, noches=2)
        brunch = Personalizacion.objects.create(
            empresa=empresa, nombre='Brunch', tipo_interaccion='check', cobrar_por_persona=True,
        )
        desayuno = Personalizacion.objects.create(
            empresa=empresa, nombre='Desayuno', tipo_interaccion='check', cobrar_por_persona=True,
        )
        self.sp_brunch = ServicioPersonalizacion.objects.create(
            servicio=self.pesca, personalizacion=brunch, precio=Decimal('100.00'),
        )
        self.sp_desayuno = ServicioPersonalizacion.objects.create(
            servicio=self.hotel, personalizacion=desayuno, precio=Decimal('50.00'),
        )

    def test_cada_extra_multiplica_por_las_personas_de_su_servicio(self):
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[self.sp_brunch.pk, self.sp_desayuno.pk],
            personas=4,
            personas_por_servicio={self.pesca.pk: 3, self.hotel.pk: 2},
        )
        # 9500 + brunch 100×3 + desayuno 50×2
        self.assertEqual(total, Decimal('9900.00'))

    def test_sin_mapa_usa_las_personas_generales(self):
        total = precio_paquete_total(
            self.paquete, personalizaciones_extra=[self.sp_brunch.pk], personas=4,
        )
        self.assertEqual(total, Decimal('9900.00'))


class EstadoReservaPaqueteTests(FixturePaqueteEstancia, TestCase):
    def setUp(self):
        cache.clear()
        with scope.como_operador_plataforma():
            self.sembrar()

    def _guardar(self, estado):
        with scope.como_operador_plataforma():
            reserva = self.reserva(
                estado=estado,
                checkout_id=uuid.uuid4(),
                personas_por_servicio={str(self.pesca.pk): 3, str(self.hotel.pk): 2},
                forma_pago=Reserva.FormaPago.COMPLETO,
                precio_total=Decimal('9500.00'),
                monto_pagado=Decimal('9500.00') if estado == Reserva.Estado.PAGADA else None,
            )
            reserva.save()
        return reserva

    def _estado(self, reserva):
        return self.client.get(
            reverse('reserva-estado', kwargs={'empresa_slug': self.empresa.slug}),
            {'checkout_id': str(reserva.checkout_id)},
        )

    def test_pagada_devuelve_inicio_y_personas_de_cada_servicio(self):
        reserva = self._guardar(Reserva.Estado.PAGADA)
        respuesta = self._estado(reserva)
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['estado'], 'pagada')
        self.assertEqual(datos['fecha_inicio_paquete'], '2026-10-10')
        self.assertEqual(datos['personas_por_servicio'], {str(self.pesca.pk): 3, str(self.hotel.pk): 2})

    def test_pendiente_devuelve_inicio_y_personas_de_cada_servicio(self):
        reserva = self._guardar(Reserva.Estado.PENDIENTE_PAGO)
        respuesta = self._estado(reserva)
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['estado'], 'pendiente_pago')
        self.assertEqual(datos['fecha_inicio_paquete'], '2026-10-10')
        self.assertEqual(datos['personas_por_servicio'], {str(self.pesca.pk): 3, str(self.hotel.pk): 2})

    def test_correo_de_confirmacion_muestra_el_inicio_del_paquete(self):
        reserva = self._guardar(Reserva.Estado.PAGADA)
        with scope.con_empresa(self.empresa):
            cuerpo = _cuerpo_html(reserva)
        self.assertIn('<strong>Fecha:</strong> 2026-10-10', cuerpo)

    def test_contacto_de_checkout_abandonado_muestra_el_inicio_del_paquete(self):
        reserva = self._guardar(Reserva.Estado.PENDIENTE_PAGO)
        contacto = str(CheckoutAbandonadoAdmin(CheckoutAbandonado, admin.site).contacto(reserva))
        self.assertIn('2026-10-10', contacto)
