import uuid
from decimal import Decimal

from django.test import TestCase

from apps.bookings.models import Orden, Reserva
from apps.fleet.enums import TipoTraslado
from apps.fleet.models import (
    Paquete, PaqueteServicio, Personalizacion, Servicio, ServicioPersonalizacion, TransporteTarifa,
)
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class OrdenPaqueteBase(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede OP', slug='sede-op-test', activo=True)
        self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca OP', slug='pesca-op', activo=True)
        self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp OP', slug='transp-op', activo=True)
        with scope.como_operador_plataforma():
            self.s_pesca = Servicio.objects.create(
                empresa=self.pesca, nombre='Pesca', slug='pesca-op-s', tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia', precio_base=Decimal('4000.00'),
            )
            self.s_transp = Servicio.objects.create(
                empresa=self.transp, nombre='Traslado', slug='traslado-op-s', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
            )
            TransporteTarifa.objects.create(
                empresa=self.transp, tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD, zona='centro',
                personas_min=1, personas_max=None, precio=Decimal('1500.00'), precio_usd=Decimal('90.00'),
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Pesca + Traslado', slug='pesca-traslado-op',
                precio_ancla=Decimal('7500.00'), precio_ancla_usd=Decimal('450.00'), permite_anticipo=False,
            )
            PaqueteServicio.objects.create(
                paquete=self.paquete, servicio=self.s_pesca, orden=1, dia_estancia=1, personas_incluidas=3,
            )
            PaqueteServicio.objects.create(
                paquete=self.paquete, servicio=self.s_transp, orden=2, dia_estancia=1, personas_incluidas=3,
            )
            brunch = Personalizacion.objects.create(empresa=self.pesca, nombre='Brunch', tipo_interaccion='check')
            silla = Personalizacion.objects.create(empresa=self.transp, nombre='Silla de bebé', tipo_interaccion='check')
            self.sp_brunch = ServicioPersonalizacion.objects.create(
                servicio=self.s_pesca, personalizacion=brunch, precio=Decimal('400.00'), precio_usd=Decimal('23.00'),
            )
            self.sp_silla = ServicioPersonalizacion.objects.create(
                servicio=self.s_transp, personalizacion=silla, precio=Decimal('150.00'), precio_usd=Decimal('9.00'),
            )
        self.url = f'/api/{self.sede.slug}/ordenes/'

    def payload(self, **extra):
        datos = {
            'checkout_id': str(uuid.uuid4()), 'paquete': self.paquete.slug,
            'nombre_cliente': 'Carlos Lopez', 'telefono_cliente': '1234567890',
            'correo_cliente': 'carlos@example.com', 'moneda': 'MXN', 'deslinde_aceptado': True,
            'deslinde_nombre': 'Carlos Lopez', 'fecha': '2026-10-15', 'hora': '07:00:00',
            'componentes': [
                {'servicio': self.s_pesca.slug, 'numero_personas': 2,
                 'personalizaciones': [{'id': self.sp_brunch.pk}]},
                {'servicio': self.s_transp.slug, 'numero_personas': 3,
                 'tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD, 'zona': 'centro',
                 'direccion_personalizada': 'Hotel Marina', 'personalizaciones': [{'id': self.sp_silla.pk}]},
            ],
        }
        datos.update(extra)
        return datos

    def crear(self, **extra):
        return self.client.post(self.url, self.payload(**extra), content_type='application/json')


class CrearOrdenPaqueteTests(OrdenPaqueteBase):
    def test_guarda_personas_por_componente_y_extras_de_cada_servicio(self):
        respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        with scope.como_operador_plataforma():
            r_pesca = Reserva.objects.get(orden_id=respuesta.json()['orden_id'], empresa=self.pesca)
            r_transp = Reserva.objects.get(orden_id=respuesta.json()['orden_id'], empresa=self.transp)
            self.assertEqual(r_pesca.numero_personas, 2)
            self.assertEqual(r_transp.numero_personas, 3)
            self.assertEqual(list(r_pesca.personalizaciones_seleccionadas.values_list('servicio_personalizacion_id', flat=True)), [self.sp_brunch.pk])
            self.assertEqual(list(r_transp.personalizaciones_seleccionadas.values_list('servicio_personalizacion_id', flat=True)), [self.sp_silla.pk])

    def test_rechaza_personas_por_encima_de_lo_incluido(self):
        datos = self.payload()
        datos['componentes'][0]['numero_personas'] = 4
        respuesta = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('lugar', str(respuesta.json()))

    def test_rechaza_un_extra_que_no_es_del_servicio(self):
        datos = self.payload()
        datos['componentes'][0]['personalizaciones'] = [{'id': self.sp_silla.pk}]
        respuesta = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('personalizaciones', respuesta.json())
        with scope.como_operador_plataforma():
            self.assertFalse(Orden.objects.exists())

    def test_rechaza_fecha_por_componente(self):
        datos = self.payload()
        datos['componentes'][0]['fecha'] = '2026-10-20'
        respuesta = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('fecha', respuesta.json())

    def test_el_dia_de_cada_componente_lo_define_el_paquete(self):
        with scope.como_operador_plataforma():
            hotel = Servicio.objects.create(
                empresa=self.pesca, nombre='Cabaña', slug='cabana-op-s', tipo_servicio='hospedaje',
                estrategia_cupo='por_noche', estrategia_precio='por_noche',
            )
            paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Cabaña + Traslado', slug='cabana-traslado-op',
                precio_ancla=Decimal('9000.00'), permite_anticipo=False,
            )
            PaqueteServicio.objects.create(paquete=paquete, servicio=hotel, orden=1, noches=3, personas_incluidas=3)
            PaqueteServicio.objects.create(paquete=paquete, servicio=self.s_transp, orden=2, dia_estancia=2, personas_incluidas=3)
        datos = self.payload(paquete=paquete.slug)
        datos['componentes'] = [
            {'servicio': hotel.slug, 'numero_personas': 2},
            {'servicio': self.s_transp.slug, 'numero_personas': 3, 'tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
             'zona': 'centro', 'direccion_personalizada': 'Hotel Marina'},
        ]
        respuesta = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        with scope.como_operador_plataforma():
            r_hotel = Reserva.objects.get(orden_id=respuesta.json()['orden_id'], servicio=hotel)
            r_transp = Reserva.objects.get(orden_id=respuesta.json()['orden_id'], servicio=self.s_transp)
            self.assertEqual(str(r_hotel.fecha), '2026-10-15')
            self.assertEqual(str(r_hotel.fecha_salida), '2026-10-18')
            self.assertEqual(str(r_transp.fecha), '2026-10-16')
