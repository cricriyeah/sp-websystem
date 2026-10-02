"""Una sola panga y un solo capitán cubren todos los días de mar."""
from datetime import time, timedelta

from django.core.exceptions import ValidationError

from apps.bookings.models import Reserva
from apps.bookings.tests_salidas import SalidasBase
from apps.fleet.models import Capitan, Embarcacion, Recurso


class UnaPangaTodaLaEstanciaTests(SalidasBase):
    def setUp(self):
        super().setUp()
        self.p1 = Embarcacion.objects.create(empresa=self.empresa, nombre='P1', clase='chica', capacidad_maxima=3)
        self.p2 = Embarcacion.objects.create(empresa=self.empresa, nombre='P2', clase='chica', capacidad_maxima=3)
        Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Habitación', capacidad_maxima=2, activo=True,
        )
        self.reserva = self.reserva_con_salidas()

    def _suelta(self, dia, embarcacion):
        return Reserva(
            empresa=self.empresa, servicio=self.pesca, fecha=self.inicio + timedelta(days=dia), hora=time(6, 0),
            numero_personas=2, nombre_cliente='Suelta', telefono_cliente='+5216121234567',
            correo_cliente='s@example.com', canal_origen='whatsapp', moneda='MXN',
            estado=Reserva.Estado.ASIGNADA, embarcacion=embarcacion,
        )

    def _asignar(self, reserva, embarcacion):
        reserva.embarcacion = embarcacion
        reserva.full_clean()
        reserva.save()

    def test_poner_la_panga_da_el_viaje_por_asignado(self):
        self._asignar(self.reserva, self.p1)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.ASIGNADA)

    def test_la_panga_del_paquete_choca_con_una_reserva_suelta_en_un_dia_intermedio(self):
        self._asignar(self.reserva, self.p1)
        with self.assertRaises(ValidationError) as ctx:
            self._suelta(3, self.p1).full_clean()
        self.assertIn('embarcacion', ctx.exception.message_dict)

    def test_la_misma_panga_en_un_dia_libre_es_valida(self):
        self._asignar(self.reserva, self.p1)
        self._suelta(6, self.p1).full_clean()

    def test_una_reserva_suelta_ya_asignada_bloquea_la_panga_a_un_paquete(self):
        suelta = self._suelta(3, self.p1)
        suelta.full_clean()
        suelta.save()
        self.reserva.embarcacion = self.p1
        with self.assertRaises(ValidationError) as ctx:
            self.reserva.full_clean()
        self.assertIn('embarcacion', ctx.exception.message_dict)

    def test_dos_paquetes_no_comparten_panga_si_se_traslapan(self):
        self._asignar(self.reserva, self.p1)
        otra = self.reserva_con_salidas()
        otra.embarcacion = self.p1
        with self.assertRaises(ValidationError):
            otra.full_clean()
        otra.embarcacion = self.p2
        otra.full_clean()

    def test_el_capitan_tampoco_se_repite_en_ningun_dia_de_mar(self):
        capitan = Capitan.objects.create(empresa=self.empresa, nombre='Capitán Uno', telefono='6121234567')
        self.reserva.capitan = capitan
        self.reserva.full_clean()
        self.reserva.save()
        suelta = self._suelta(2, self.p2)
        suelta.capitan = capitan
        with self.assertRaises(ValidationError) as ctx:
            suelta.full_clean()
        self.assertIn('capitan', ctx.exception.message_dict)
