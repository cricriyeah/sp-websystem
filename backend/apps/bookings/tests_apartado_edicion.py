"""Pruebas de que editar una reserva borra el apartado temporal y que el apartado es de solo lectura en la API pública.

Spec: §4.3 («Editar la reserva sin pasar por crear-pago»), §4.1 y §5.
"""
import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.fleet.models import Paquete, PaqueteServicio, Recurso, Servicio
from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca


class ApartadoEdicionTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.servicio = crear_servicio_pesca(
            self.empresa,
            precio_base=Decimal('4500.00'),
            precio_persona_extra=Decimal('500.00'),
        )
        self.fecha = date.today() + timedelta(days=10)
        self.checkout_id = uuid.uuid4()
        self.url = reverse('reserva-checkout', kwargs={'empresa_slug': self.empresa.slug})

        # Mock global de turnstile para las pruebas del checkout
        patcher = mock.patch('apps.bookings.views.verificar_turnstile', return_value=True)
        self.mock_turnstile = patcher.start()
        self.addCleanup(patcher.stop)

    def _crear_reserva_con_apartado(self, **overrides):
        ahora = timezone.now()
        apartado_hasta = ahora + timedelta(minutes=15)
        apartado_demanda = {
            'v': 1,
            'salidas': [{'fecha': self.fecha.isoformat(), 'personas': 2, 'servicio_id': self.servicio.pk}],
            'habitaciones': [],
        }
        datos = {
            'empresa': self.empresa,
            'servicio': self.servicio,
            'fecha': self.fecha,
            'hora': time(6, 0),
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'canal_origen': Reserva.CanalOrigen.WEB,
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'checkout_id': self.checkout_id,
            'estado': Reserva.Estado.PENDIENTE_PAGO,
            'apartado_hasta': apartado_hasta,
            'apartado_demanda': apartado_demanda,
        }
        datos.update(overrides)
        reserva = Reserva(**datos)
        reserva.full_clean()
        reserva.save()
        return reserva

    def _payload_base(self, **overrides):
        datos = {
            'checkout_id': str(self.checkout_id),
            'servicio': self.servicio.slug,
            'fecha': self.fecha.isoformat(),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'captcha_token': 'dummy_token',
        }
        datos.update(overrides)
        return datos

    def test_cambiar_fecha_por_post_reservas_borra_apartado(self):
        reserva = self._crear_reserva_con_apartado()
        self.assertIsNotNone(reserva.apartado_hasta)

        nueva_fecha = self.fecha + timedelta(days=2)
        payload = self._payload_base(fecha=nueva_fecha.isoformat())

        resp = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

        reserva.refresh_from_db()
        self.assertEqual(reserva.fecha, nueva_fecha)
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    def test_cambiar_numero_personas_por_post_reservas_borra_apartado(self):
        reserva = self._crear_reserva_con_apartado()

        payload = self._payload_base(numero_personas=3)
        resp = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

        reserva.refresh_from_db()
        self.assertEqual(reserva.numero_personas, 3)
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    def test_cambiar_hora_por_post_reservas_borra_apartado(self):
        reserva = self._crear_reserva_con_apartado()

        payload = self._payload_base(hora='07:00')
        resp = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

        reserva.refresh_from_db()
        self.assertEqual(reserva.hora, time(7, 0))
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    def test_cambiar_servicio_por_post_reservas_borra_apartado(self):
        reserva = self._crear_reserva_con_apartado()
        otro_servicio = crear_servicio_pesca(
            self.empresa,
            slug='pesca-tarde',
            nombre='Pesca Tarde',
        )

        payload = self._payload_base(servicio=otro_servicio.slug)
        resp = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

        reserva.refresh_from_db()
        self.assertEqual(reserva.servicio, otro_servicio)
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    def test_cambiar_paquete_por_post_reservas_borra_apartado(self):
        paquete_a = Paquete.objects.create(
            sede=self.empresa.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Uno',
            slug='paquete-uno',
            precio_ancla=Decimal('5000.00'),
            estrategia_precio='por_grupo',
            personas_precio_base=2,
            precio_persona_extra=Decimal('500.00'),
            permite_anticipo=False,
            activo=True,
        )
        PaqueteServicio.objects.create(
            paquete=paquete_a,
            servicio=self.servicio,
            orden=1,
            dia_estancia=1,
            salidas=1,
            personas_incluidas=3,
        )

        paquete_b = Paquete.objects.create(
            sede=self.empresa.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Dos',
            slug='paquete-dos',
            precio_ancla=Decimal('6000.00'),
            estrategia_precio='por_grupo',
            personas_precio_base=2,
            precio_persona_extra=Decimal('500.00'),
            permite_anticipo=False,
            activo=True,
        )
        PaqueteServicio.objects.create(
            paquete=paquete_b,
            servicio=self.servicio,
            orden=1,
            dia_estancia=1,
            salidas=1,
            personas_incluidas=3,
        )

        reserva = self._crear_reserva_con_apartado(
            servicio=None,
            paquete=paquete_a,
            inicio_paquete=self.fecha,
            personas_por_servicio={str(self.servicio.pk): 2},
        )

        payload = {
            'checkout_id': str(self.checkout_id),
            'paquete': paquete_b.slug,
            'fecha': self.fecha.isoformat(),
            'numero_personas': 2,
            'personas_por_servicio': {str(self.servicio.pk): 2},
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
        }

        resp = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

        reserva.refresh_from_db()
        self.assertEqual(reserva.paquete, paquete_b)
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    def test_cambiar_fecha_salida_en_hospedaje_borra_apartado(self):
        hospedaje = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Cabana Mar',
            slug='cabana-mar',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            estrategia_precio='por_noche',
            hora_apertura=time(14),
            hora_cierre=time(20),
            activo=True,
        )
        Recurso.objects.create(
            empresa=self.empresa,
            servicio=hospedaje,
            nombre='Habitacion Principal',
            capacidad_maxima=4,
            activo=True,
        )

        fecha_salida_orig = self.fecha + timedelta(days=2)
        reserva = self._crear_reserva_con_apartado(
            servicio=hospedaje,
            hora=time(15, 0),
            fecha_salida=fecha_salida_orig,
        )

        nueva_fecha_salida = self.fecha + timedelta(days=3)
        payload = self._payload_base(
            servicio=hospedaje.slug,
            hora='15:00',
            fecha_salida=nueva_fecha_salida.isoformat(),
        )

        resp = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

        reserva.refresh_from_db()
        self.assertEqual(reserva.fecha_salida, nueva_fecha_salida)
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    def test_cambiar_personas_por_servicio_en_paquete_borra_apartado(self):
        paquete = Paquete.objects.create(
            sede=self.empresa.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Pesca Amigos',
            slug='paquete-pesca-amigos',
            precio_ancla=Decimal('5000.00'),
            estrategia_precio='por_grupo',
            personas_precio_base=2,
            precio_persona_extra=Decimal('500.00'),
            permite_anticipo=False,
            activo=True,
        )
        PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio,
            orden=1,
            dia_estancia=1,
            salidas=1,
            personas_incluidas=4,
        )

        reserva = self._crear_reserva_con_apartado(
            servicio=None,
            paquete=paquete,
            inicio_paquete=self.fecha,
            personas_por_servicio={str(self.servicio.pk): 2},
        )

        payload = {
            'checkout_id': str(self.checkout_id),
            'paquete': paquete.slug,
            'fecha': self.fecha.isoformat(),
            'numero_personas': 2,
            'personas_por_servicio': {str(self.servicio.pk): 3},
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
        }

        resp = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

        reserva.refresh_from_db()
        self.assertEqual(reserva.personas_por_servicio, {str(self.servicio.pk): 3})
        self.assertEqual(reserva.numero_personas, 3)
        self.assertIsNone(reserva.apartado_hasta)
        self.assertIsNone(reserva.apartado_demanda)

    def test_cambiar_solo_nombre_cliente_no_borra_apartado(self):
        reserva = self._crear_reserva_con_apartado()
        apartado_orig = reserva.apartado_hasta
        demanda_orig = reserva.apartado_demanda

        payload = self._payload_base(nombre_cliente='Beatriz Mendez')

        resp = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

        reserva.refresh_from_db()
        self.assertEqual(reserva.nombre_cliente, 'Beatriz Mendez')
        # El apartado debe permanecer intacto porque no cambió ningún campo relevante para el cupo
        self.assertEqual(reserva.apartado_hasta, apartado_orig)
        self.assertEqual(reserva.apartado_demanda, demanda_orig)

    def test_apartado_hasta_no_es_escribible_por_api_publica(self):
        # 1. En la definición del serializador público, la lista de campos es explícita y no los incluye
        serializer = ReservaCheckoutSerializer()
        self.assertNotIn('apartado_hasta', serializer.fields)
        self.assertNotIn('apartado_demanda', serializer.fields)

        # 2. Intento de inyección al crear una reserva nueva
        nuevo_checkout_id = uuid.uuid4()
        payload_crear = {
            'checkout_id': str(nuevo_checkout_id),
            'servicio': self.servicio.slug,
            'fecha': self.fecha.isoformat(),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Carlos Gomez',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'carlos@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Carlos Gomez',
            'captcha_token': 'dummy_token',
            'apartado_hasta': '2026-10-15T12:00:00Z',
            'apartado_demanda': {'v': 1, 'inyeccion': True},
        }

        resp_crear = self.client.post(self.url, payload_crear, content_type='application/json')
        self.assertEqual(resp_crear.status_code, 201, resp_crear.content)

        reserva_creada = Reserva.objects.get(checkout_id=nuevo_checkout_id)
        self.assertIsNone(reserva_creada.apartado_hasta)
        self.assertIsNone(reserva_creada.apartado_demanda)

        # 3. Intento de inyección al editar una reserva existente
        payload_editar = {
            'checkout_id': str(nuevo_checkout_id),
            'servicio': self.servicio.slug,
            'fecha': self.fecha.isoformat(),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Carlos Gomez Corregido',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'carlos@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Carlos Gomez',
            'apartado_hasta': '2026-10-15T12:00:00Z',
            'apartado_demanda': {'v': 1, 'inyeccion': True},
        }

        resp_editar = self.client.post(self.url, payload_editar, content_type='application/json')
        self.assertEqual(resp_editar.status_code, 200, resp_editar.content)

        reserva_creada.refresh_from_db()
        self.assertEqual(reserva_creada.nombre_cliente, 'Carlos Gomez Corregido')
        self.assertIsNone(reserva_creada.apartado_hasta)
        self.assertIsNone(reserva_creada.apartado_demanda)
