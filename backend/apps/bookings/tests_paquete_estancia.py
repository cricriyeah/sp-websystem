"""Reserva de paquete de una sola empresa: personas por componente y estancia."""
from datetime import date, time
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.bookings.models import Reserva
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
