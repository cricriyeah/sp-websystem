from datetime import date, time
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.bookings import personalizaciones
from apps.bookings.models import Reserva
from apps.fleet.models import Personalizacion, Servicio, ServicioPersonalizacion
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class HelperPersonalizacionesTests(OperadorTestCase):
    def setUp(self):
        sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=sede, nombre='Empresa HP', slug='empresa-hp')
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Tour', slug='tour-hp', tipo_servicio='otro',
            estrategia_cupo='bajo_demanda', estrategia_precio='tarifa_fija', precio_base=Decimal('1000.00'),
        )
        otro = Servicio.objects.create(
            empresa=self.empresa, nombre='Otro', slug='otro-hp', tipo_servicio='otro',
            estrategia_cupo='bajo_demanda', estrategia_precio='tarifa_fija', precio_base=Decimal('1000.00'),
        )
        check = Personalizacion.objects.create(empresa=self.empresa, nombre='Brunch', tipo_interaccion='check')
        texto = Personalizacion.objects.create(empresa=self.empresa, nombre='Alergias', tipo_interaccion='input_texto')
        self.sp_check = ServicioPersonalizacion.objects.create(servicio=self.servicio, personalizacion=check, precio=Decimal('100.00'))
        self.sp_texto = ServicioPersonalizacion.objects.create(
            servicio=self.servicio, personalizacion=texto, obligatorio=True,
        )
        self.sp_ajeno = ServicioPersonalizacion.objects.create(servicio=otro, personalizacion=check, precio=Decimal('100.00'))
        self.reserva = Reserva.objects.create(
            empresa=self.empresa, servicio=self.servicio, fecha=date(2026, 11, 1), hora=time(9),
            numero_personas=2, nombre_cliente='Ana', telefono_cliente='1234567890',
            correo_cliente='ana@example.com', moneda='MXN', estado=Reserva.Estado.PENDIENTE_PAGO,
        )

    def test_seleccion_valida(self):
        personalizaciones.validar_seleccion(
            self.servicio, [{'id': self.sp_check.pk}, {'id': self.sp_texto.pk, 'respuesta': 'Ninguna'}],
        )

    def test_rechaza_un_extra_de_otro_servicio(self):
        with self.assertRaises(ValidationError):
            personalizaciones.validar_seleccion(
                self.servicio, [{'id': self.sp_ajeno.pk}, {'id': self.sp_texto.pk, 'respuesta': 'x'}],
            )

    def test_rechaza_repetidos_y_falta_de_obligatorio(self):
        with self.assertRaises(ValidationError):
            personalizaciones.validar_seleccion(self.servicio, [{'id': self.sp_check.pk}, {'id': self.sp_check.pk}])
        with self.assertRaises(ValidationError):
            personalizaciones.validar_seleccion(self.servicio, [{'id': self.sp_check.pk}])

    def test_sincronizar_reescribe_y_omite_respuestas_vacias(self):
        personalizaciones.sincronizar(self.reserva, [{'id': self.sp_check.pk}, {'id': self.sp_texto.pk, 'respuesta': '  '}])
        self.assertEqual(self.reserva.personalizaciones_seleccionadas.count(), 1)
        personalizaciones.sincronizar(self.reserva, [])
        self.assertEqual(self.reserva.personalizaciones_seleccionadas.count(), 0)
