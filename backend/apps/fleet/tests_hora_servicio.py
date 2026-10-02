"""Cada servicio decide si pide hora y en qué rango (hora_apertura/hora_cierre) y paso se ofrece."""
import uuid
from datetime import time
from decimal import Decimal

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.fleet.enums import TipoTraslado
from apps.fleet.models import Servicio, TransporteTarifa
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class HoraDeServicioTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        sede = Sede.objects.create(nombre='Sede Hora', slug='sede-hora')
        self.empresa = Empresa.objects.create(
            sede=sede, nombre='Empresa Hora', slug='empresa-hora', activo=True,
            stripe_secret_key='sk_test_h', stripe_publishable_key='pk_test_h',
        )

    def servicio(self, **extra):
        datos = dict(
            empresa=self.empresa, nombre='Pesca', slug='pesca-h', tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia', precio_base=Decimal('1000.00'),
            hora_apertura=time(5, 0), hora_cierre=time(7, 0),
        )
        datos.update(extra)
        with scope.con_empresa(self.empresa):
            return Servicio.objects.create(**datos)

    def test_por_defecto_pide_hora_cada_15_minutos(self):
        servicio = self.servicio()
        self.assertTrue(servicio.pide_hora)
        self.assertEqual(servicio.paso_hora_minutos, 15)

    def test_un_servicio_que_pide_hora_necesita_su_rango(self):
        servicio = self.servicio(hora_apertura=None, hora_cierre=None)
        with self.assertRaises(ValidationError) as ctx:
            servicio.full_clean()
        self.assertIn('hora_apertura', ctx.exception.message_dict)

    def test_un_servicio_que_no_pide_hora_no_necesita_rango(self):
        servicio = self.servicio(hora_apertura=None, hora_cierre=None, pide_hora=False)
        servicio.full_clean()

    def test_el_paso_minimo_es_5_minutos(self):
        servicio = self.servicio(paso_hora_minutos=2)
        with self.assertRaises(ValidationError) as ctx:
            servicio.full_clean()
        self.assertIn('paso_hora_minutos', ctx.exception.message_dict)

    def test_el_catalogo_publico_manda_el_rango_el_paso_y_si_pide_hora(self):
        self.servicio(paso_hora_minutos=30)
        datos = self.client.get(f'/api/{self.empresa.slug}/servicios/').json()[0]
        self.assertEqual(datos['pide_hora'], True)
        self.assertEqual(datos['hora_apertura'], '05:00:00')
        self.assertEqual(datos['hora_cierre'], '07:00:00')
        self.assertEqual(datos['paso_hora_minutos'], 30)

    def payload(self, servicio, **extra):
        datos = {
            'checkout_id': str(uuid.uuid4()), 'fecha': '2027-03-10', 'hora': '06:00:00',
            'numero_personas': 2, 'nombre_cliente': 'Ana', 'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com', 'moneda': 'MXN', 'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana', 'servicio': servicio.slug, 'personalizaciones': [],
        }
        datos.update(extra)
        return datos

    def validar(self, datos):
        with scope.con_empresa(self.empresa):
            serializador = ReservaCheckoutSerializer(data=datos, context={'empresa': self.empresa})
            return serializador, serializador.is_valid()

    def test_servicio_que_no_pide_hora_acepta_la_reserva_sin_hora(self):
        servicio = self.servicio(pide_hora=False, hora_apertura=None, hora_cierre=None)
        datos = self.payload(servicio)
        datos.pop('hora')
        serializador, valido = self.validar(datos)
        self.assertTrue(valido, serializador.errors)
        self.assertIsNone(serializador.validated_data['hora'])

    def test_servicio_que_pide_hora_la_exige(self):
        servicio = self.servicio()
        datos = self.payload(servicio)
        datos.pop('hora')
        serializador, valido = self.validar(datos)
        self.assertFalse(valido)
        self.assertIn('hora', serializador.errors)

    def test_el_catalogo_de_traslados_manda_el_paso(self):
        with scope.con_empresa(self.empresa):
            Servicio.objects.create(
                empresa=self.empresa, nombre='Traslado', slug='traslado-h', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta', capacidad_maxima=14,
                hora_apertura=time(6, 0), hora_cierre=time(22, 0), paso_hora_minutos=30,
            )
            TransporteTarifa.objects.create(
                empresa=self.empresa, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                personas_min=1, personas_max=4, precio='3500.00',
            )
        servicio = self.client.get(f'/api/{self.empresa.slug}/traslados/').json()['servicio']
        self.assertEqual(servicio['paso_hora_minutos'], 30)
        self.assertEqual(servicio['hora_apertura'], '06:00:00')
