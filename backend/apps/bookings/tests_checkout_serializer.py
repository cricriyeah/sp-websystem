"""Pruebas de ReservaCheckoutSerializer para servicio, paquete, fecha_salida y selecciones."""

import uuid
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from apps.bookings.models import (
    Reserva,
    ReservaPersonalizacion,
)
from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.fleet.models import (
    Paquete,
    PaqueteServicio,
    Personalizacion,
    Recurso,
    Servicio,
    ServicioPersonalizacion,
)
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class ReservaCheckoutSerializerTests(OperadorTestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede Loreto', slug='loreto')
        self.empresa_a = Empresa.objects.create(sede=self.sede, nombre='Tours Loreto', slug='tours-loreto')
        self.empresa_b = Empresa.objects.create(sede=self.sede, nombre='Hotel Loreto', slug='hotel-loreto')

        self.factory = APIRequestFactory()
        self.request = self.factory.post('/api/tours-loreto/reservas/')

        # Servicios empresa A
        self.srv_pesca = Servicio.objects.create(
            empresa=self.empresa_a, nombre='Pesca Deportiva', slug='pesca-deportiva',
            tipo_servicio='pesca', estrategia_cupo='por_recurso_dia',
            precio_base=Decimal('5000.00'), personas_incluidas=3,
        )
        self.srv_snack = Servicio.objects.create(
            empresa=self.empresa_a, nombre='Snacks a bordo', slug='snacks',
            tipo_servicio='otro', estrategia_cupo='bajo_demanda',
            precio_base=Decimal('500.00'),
        )
        self.srv_hospedaje = Servicio.objects.create(
            empresa=self.empresa_a, nombre='Cabaña Marina', slug='cabana-marina',
            tipo_servicio='hospedaje', estrategia_cupo='por_noche',
            precio_base=Decimal('2000.00'), personas_incluidas=2,
        )
        self.recurso_cabana = Recurso.objects.create(
            empresa=self.empresa_a, servicio=self.srv_hospedaje,
            nombre='Cabaña 1', capacidad_maxima=4,
        )

        # Servicio empresa B
        self.srv_b = Servicio.objects.create(
            empresa=self.empresa_b, nombre='Habitación B', slug='hab-b',
            tipo_servicio='hospedaje', estrategia_cupo='por_noche',
            precio_base=Decimal('1500.00'),
        )

        # Personalizaciones para srv_pesca
        self.pers_licencia = Personalizacion.objects.create(
            empresa=self.empresa_a, nombre='Licencia de Pesca',
        )
        self.sp_opcional = ServicioPersonalizacion.objects.create(
            servicio=self.srv_pesca, personalizacion=self.pers_licencia,
            precio=Decimal('250.00'), obligatorio=False, preseleccionado=False, activo=True,
        )

        self.pers_cebo = Personalizacion.objects.create(
            empresa=self.empresa_a, nombre='Cebo Vivo',
        )
        self.sp_obligatoria = ServicioPersonalizacion.objects.create(
            servicio=self.srv_pesca, personalizacion=self.pers_cebo,
            precio=Decimal('100.00'), obligatorio=True, preseleccionado=False, activo=True,
        )

        self.pers_gorra = Personalizacion.objects.create(
            empresa=self.empresa_a, nombre='Gorra Oficial',
        )
        self.sp_preseleccionada = ServicioPersonalizacion.objects.create(
            servicio=self.srv_pesca, personalizacion=self.pers_gorra,
            precio=Decimal('150.00'), obligatorio=False, preseleccionado=True, activo=True,
        )

        # Paquete empresa A
        self.paquete_a = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa_a,
            nombre='Super Pack Loreto', slug='super-pack-loreto',
            precio_ancla=Decimal('7000.00'),
        )
        self.ps_pesca = PaqueteServicio.objects.create(
            paquete=self.paquete_a, servicio=self.srv_pesca, orden=1,
        )
        self.ps_snack = PaqueteServicio.objects.create(
            paquete=self.paquete_a, servicio=self.srv_snack, orden=2,
        )

        # Paquete con hospedaje en empresa A
        self.paquete_hospedaje = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa_a,
            nombre='Pack Pesca + Dormir', slug='pack-pesca-dormir',
            precio_ancla=Decimal('9000.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete_hospedaje, servicio=self.srv_pesca, orden=1,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete_hospedaje, servicio=self.srv_hospedaje, orden=2,
        )

        # Paquete empresa B
        self.paquete_b = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa_b,
            nombre='Pack B', slug='pack-b', precio_ancla=Decimal('5000.00'),
        )

    def _datos_base(self, **overrides):
        datos = {
            'checkout_id': str(uuid.uuid4()),
            'fecha': (date.today() + timedelta(days=10)).isoformat(),
            'hora': '07:00',
            'numero_personas': 2,
            'nombre_cliente': 'Juan Perez',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'juan@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Juan Perez',
        }
        datos.update(overrides)
        return datos

    def test_acepta_reserva_de_servicio_de_la_empresa(self):
        datos = self._datos_base(servicio=self.srv_pesca.slug)
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        reserva = serializer.save()
        self.assertEqual(reserva.servicio, self.srv_pesca)
        self.assertIsNone(reserva.paquete)

    def test_acepta_reserva_de_paquete_de_la_empresa(self):
        datos = self._datos_base(
            paquete=self.paquete_a.slug,
            personalizaciones=[{'id': self.sp_opcional.id, 'cantidad': 2}],
        )
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        reserva = serializer.save()
        self.assertEqual(reserva.paquete, self.paquete_a)
        self.assertIsNone(reserva.servicio)
        self.assertEqual(reserva.personalizaciones_seleccionadas.count(), 1)
        self.assertEqual(reserva.personalizaciones_seleccionadas.first().servicio_personalizacion, self.sp_opcional)
        self.assertEqual(reserva.personalizaciones_seleccionadas.first().cantidad, 2)

    def test_rechaza_paquete_de_otra_empresa(self):
        datos = self._datos_base(paquete=self.paquete_b.slug)
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('paquete', serializer.errors)

    def test_rechaza_servicio_de_otra_empresa(self):
        datos = self._datos_base(servicio=self.srv_b.slug)
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('servicio', serializer.errors)

    def test_rechaza_servicio_y_paquete_juntos(self):
        datos = self._datos_base(servicio=self.srv_pesca.slug, paquete=self.paquete_a.slug)
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertFalse(serializer.is_valid())

    def test_exige_fecha_salida_para_servicio_hospedaje(self):
        # Sin fecha_salida -> invalido
        datos = self._datos_base(servicio=self.srv_hospedaje.slug)
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('fecha_salida', serializer.errors)

        # Con fecha_salida valida -> valido
        fecha_llegada = date.today() + timedelta(days=10)
        datos['fecha'] = fecha_llegada.isoformat()
        datos['fecha_salida'] = (fecha_llegada + timedelta(days=2)).isoformat()
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_exige_fecha_salida_para_paquete_con_hospedaje(self):
        datos = self._datos_base(paquete=self.paquete_hospedaje.slug)
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('fecha_salida', serializer.errors)

        fecha_llegada = date.today() + timedelta(days=10)
        datos['fecha_salida'] = (fecha_llegada + timedelta(days=3)).isoformat()
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_prohibe_fecha_salida_si_ningun_servicio_es_hospedaje(self):
        datos = self._datos_base(
            servicio=self.srv_pesca.slug,
            fecha_salida=(date.today() + timedelta(days=12)).isoformat(),
        )
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('fecha_salida', serializer.errors)

    def test_rechaza_fecha_salida_anterior_o_igual_a_fecha(self):
        fecha_llegada = date.today() + timedelta(days=10)
        datos = self._datos_base(
            servicio=self.srv_hospedaje.slug,
            fecha=fecha_llegada.isoformat(),
            fecha_salida=fecha_llegada.isoformat(),
        )
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('fecha_salida', serializer.errors)

    def test_personalizaciones_solo_acepta_opcionales(self):
        # Obligatoria -> rechazada
        datos = self._datos_base(
            paquete=self.paquete_a.slug,
            personalizaciones=[{'id': self.sp_obligatoria.id, 'cantidad': 1}],
        )
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('personalizaciones', serializer.errors)

        # Preseleccionada -> rechazada (v1 ya las incluye)
        datos = self._datos_base(
            paquete=self.paquete_a.slug,
            personalizaciones=[{'id': self.sp_preseleccionada.id, 'cantidad': 1}],
        )
        serializer = ReservaCheckoutSerializer(
            data=datos, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('personalizaciones', serializer.errors)

    def test_actualizacion_reenvio_sincroniza_personalizaciones(self):
        datos1 = self._datos_base(
            paquete=self.paquete_a.slug,
            personalizaciones=[{'id': self.sp_opcional.id, 'cantidad': 1}],
        )
        serializer1 = ReservaCheckoutSerializer(
            data=datos1, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertTrue(serializer1.is_valid(), serializer1.errors)
        reserva = serializer1.save()

        self.assertEqual(reserva.personalizaciones_seleccionadas.first().cantidad, 1)

        # Reenvío: cambia cantidad de personalización
        datos2 = self._datos_base(
            checkout_id=str(reserva.checkout_id),
            paquete=self.paquete_a.slug,
            personalizaciones=[{'id': self.sp_opcional.id, 'cantidad': 3}],
        )
        serializer2 = ReservaCheckoutSerializer(
            reserva, data=datos2, context={'request': self.request, 'empresa': self.empresa_a},
        )
        self.assertTrue(serializer2.is_valid(), serializer2.errors)
        reserva_act = serializer2.save()

        self.assertEqual(reserva_act.personalizaciones_seleccionadas.count(), 1)
        self.assertEqual(reserva_act.personalizaciones_seleccionadas.first().cantidad, 3)
