"""Reserva de paquete de una sola empresa: personas por componente y estancia."""
import uuid
from datetime import date, time
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.bookings.models import Reserva
from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class FixturePaqueteEstancia:
    """Paquete de una empresa: pesca el día 2 + hospedaje de 3 noches."""

    def sembrar(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa PE', slug='empresa-pe')
        self.pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca-pe', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Cabaña', slug='cabana-pe', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche',
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Fin de semana', slug='finde-pe',
            precio_ancla=Decimal('9500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.pesca, orden=1, dia_estancia=2, personas_incluidas=3,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.hotel, orden=2, noches=3, personas_incluidas=2,
        )

    def reserva(self, **extra):
        datos = dict(
            empresa=self.empresa, paquete=self.paquete, fecha=date(2026, 10, 11),
            inicio_paquete=date(2026, 10, 10), fecha_salida=date(2026, 10, 13), hora=time(6),
            numero_personas=3, nombre_cliente='Ana', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', canal_origen='web', deslinde_aceptado=True,
            deslinde_nombre='Ana', estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        datos.update(extra)
        return Reserva(**datos)


class PersonasPorServicioTests(FixturePaqueteEstancia, OperadorTestCase):
    def setUp(self):
        self.sembrar()

    def test_personas_de_usa_el_mapa_y_cae_en_numero_personas(self):
        reserva = self.reserva(personas_por_servicio={str(self.hotel.pk): 2})
        self.assertEqual(reserva.personas_de(self.hotel.pk), 2)
        self.assertEqual(reserva.personas_de(self.pesca.pk), 3)  # no separado: numero_personas

    def test_fecha_inicio_del_paquete_es_la_guardada(self):
        self.assertEqual(self.reserva().fecha_inicio_paquete, date(2026, 10, 10))

    def test_sin_inicio_guardado_cae_en_la_fecha(self):
        # Reservas anteriores a este campo o de servicio suelto.
        self.assertEqual(self.reserva(inicio_paquete=None).fecha_inicio_paquete, date(2026, 10, 11))

    def test_editar_las_noches_del_paquete_no_mueve_el_inicio_de_una_reserva_vendida(self):
        reserva = self.reserva()
        PaqueteServicio.objects.filter(paquete=self.paquete, servicio=self.hotel).update(noches=5)
        self.assertEqual(reserva.fecha_inicio_paquete, date(2026, 10, 10))

    def test_el_inicio_no_puede_ser_posterior_a_la_actividad_ni_a_la_salida(self):
        with self.assertRaises(ValidationError) as ctx:
            self.reserva(inicio_paquete=date(2026, 10, 12)).full_clean()
        self.assertIn('inicio_paquete', ctx.exception.message_dict)
        with self.assertRaises(ValidationError) as ctx:
            self.reserva(fecha=date(2026, 10, 10), inicio_paquete=date(2026, 10, 10),
                         fecha_salida=date(2026, 10, 10)).full_clean()
        self.assertTrue(ctx.exception.message_dict)


class SerializadorPaqueteTests(FixturePaqueteEstancia, OperadorTestCase):
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

    def validar(self, **extra):
        serializador = ReservaCheckoutSerializer(data=self.payload(**extra), context={'empresa': self.empresa})
        return serializador, serializador.is_valid()

    def test_deriva_fecha_ancla_salida_y_personas_principales(self):
        serializador, valido = self.validar()
        self.assertTrue(valido, serializador.errors)
        datos = serializador.validated_data
        self.assertEqual(str(datos['fecha']), '2026-10-11')
        self.assertEqual(str(datos['fecha_salida']), '2026-10-13')
        self.assertEqual(datos['numero_personas'], 3)

    def test_rechaza_fecha_de_salida_enviada_por_el_cliente(self):
        serializador, valido = self.validar(fecha_salida='2026-10-20')
        self.assertFalse(valido)
        self.assertIn('fecha_salida', serializador.errors)

    def test_rechaza_mas_personas_que_las_incluidas(self):
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 4, str(self.hotel.pk): 2})
        self.assertFalse(valido)
        self.assertIn('personas_por_servicio', serializador.errors)

    def test_exige_personas_de_cada_servicio_del_paquete(self):
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 2})
        self.assertFalse(valido)
        self.assertIn('personas_por_servicio', serializador.errors)

    def test_menos_personas_en_el_hospedaje_es_valido(self):
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 3, str(self.hotel.pk): 1})
        self.assertTrue(valido, serializador.errors)

    def test_guarda_el_inicio_elegido_por_el_cliente(self):
        serializador, valido = self.validar()
        self.assertTrue(valido, serializador.errors)
        self.assertEqual(str(serializador.validated_data['inicio_paquete']), '2026-10-10')

    def test_rechaza_un_paquete_de_dos_empresas(self):
        otra = Empresa.objects.create(sede=self.sede, nombre='Transp PE', slug='transp-pe')
        traslado = Servicio.objects.create(
            empresa=otra, nombre='Traslado', slug='traslado-pe', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
        )
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=traslado, orden=3)
        serializador, valido = self.validar()
        self.assertFalse(valido)
        self.assertIn('paquete', serializador.errors)

    def test_rechaza_un_paquete_mal_configurado(self):
        PaqueteServicio.objects.filter(paquete=self.paquete, servicio=self.hotel).update(noches=None)
        serializador, valido = self.validar()
        self.assertFalse(valido)
        self.assertIn('paquete', serializador.errors)

    def test_las_actividades_deben_ir_con_las_mismas_personas(self):
        segunda = Servicio.objects.create(
            empresa=self.empresa, nombre='Paseo', slug='paseo-pe', tipo_servicio='paseo',
            precio_base=Decimal('1000.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=segunda, orden=3, dia_estancia=2, personas_incluidas=3,
        )
        serializador, valido = self.validar(personas_por_servicio={
            str(self.pesca.pk): 3, str(self.hotel.pk): 2, str(segunda.pk): 2,
        })
        self.assertFalse(valido)
        self.assertIn('personas_por_servicio', serializador.errors)

    def test_guardar_y_reenviar_actualiza_la_misma_reserva(self):
        from rest_framework.test import APIRequestFactory

        peticion = APIRequestFactory().post('/x')
        peticion.META['REMOTE_ADDR'] = '127.0.0.1'
        contexto = {'empresa': self.empresa, 'request': peticion}
        primero = ReservaCheckoutSerializer(data=self.payload(), context=contexto)
        self.assertTrue(primero.is_valid(), primero.errors)
        reserva = primero.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.inicio_paquete, date(2026, 10, 10))
        self.assertEqual(reserva.personas_de(self.hotel.pk), 2)
        segundo = ReservaCheckoutSerializer(
            reserva, data=self.payload(fecha='2026-10-12', checkout_id=str(reserva.checkout_id)), context=contexto,
        )
        self.assertTrue(segundo.is_valid(), segundo.errors)
        segundo.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.inicio_paquete, date(2026, 10, 12))
        self.assertEqual(Reserva.objects.filter(paquete=self.paquete).count(), 1)
