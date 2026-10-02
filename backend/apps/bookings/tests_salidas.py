"""Modelo ReservaSalida: una salida al mar por día de una reserva de paquete."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from apps.bookings.models import Reserva, ReservaSalida
from apps.fleet.models import Embarcacion, Paquete, PaqueteServicio, Recurso, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class SalidasBase(OperadorTestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede Salidas', slug='sede-salidas')
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa Salidas', slug='empresa-salidas')
        self.pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca Mar', slug='pesca-mar', tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia', precio_base=Decimal('3000.00'),
        )
        self.hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Hotel Mar', slug='hotel-mar', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche', precio_base=Decimal('2000.00'),
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Mar 4 días', slug='mar-4',
            precio_ancla=Decimal('10000.00'),
        )
        self.ps_hotel = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.hotel, orden=1, noches=5)
        self.ps_pesca = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.pesca, orden=2, dia_estancia=2, salidas=4,
        )
        self.inicio = date.today() + timedelta(days=20)

    def reserva_con_salidas(self, estado=Reserva.Estado.PAGADA, personas=2, salidas=4):
        if estado in (Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA, Reserva.Estado.COMPLETADA):
            if not Embarcacion.objects.filter(empresa=self.empresa, activa=True).exists():
                Embarcacion.objects.create(
                    empresa=self.empresa, nombre='Panga del fixture', clase='chica', capacidad_maxima=3,
                )
        reserva = Reserva.objects.create(
            empresa=self.empresa, paquete=self.paquete, fecha=self.inicio + timedelta(days=1),
            inicio_paquete=self.inicio, fecha_salida=self.inicio + timedelta(days=5), hora=time(6, 0),
            numero_personas=personas, nombre_cliente='Cliente Mar', telefono_cliente='+5216121234567',
            correo_cliente='mar@example.com', canal_origen='web', deslinde_aceptado=True, moneda='MXN',
            estado=estado,
        )
        if estado == Reserva.Estado.CANCELADA:
            for i in range(salidas):
                ReservaSalida.objects.create(
                    empresa=self.empresa, reserva=reserva, servicio=self.pesca,
                    fecha=self.inicio + timedelta(days=1 + i),
                )
        return reserva


class ReservaSalidaModelTests(SalidasBase):
    def test_paqueteservicio_guarda_las_salidas(self):
        self.ps_pesca.refresh_from_db()
        self.assertEqual(self.ps_pesca.salidas, 4)
        self.assertEqual(self.ps_hotel.salidas, 1)

    def test_una_reserva_tiene_una_salida_por_dia(self):
        reserva = self.reserva_con_salidas()
        fechas = list(reserva.salidas.order_by('fecha').values_list('fecha', flat=True))
        self.assertEqual(fechas, [self.inicio + timedelta(days=d) for d in (1, 2, 3, 4)])

    def test_no_se_repite_el_mismo_dia_de_la_misma_reserva(self):
        reserva = self.reserva_con_salidas()
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReservaSalida.objects.create(
                    empresa=self.empresa, reserva=reserva, servicio=self.pesca, fecha=self.inicio + timedelta(days=1),
                )


class SincronizacionSalidasTests(SalidasBase):
    def setUp(self):
        super().setUp()
        self.panga = Embarcacion.objects.create(
            empresa=self.empresa, nombre='Panga sincronización', clase='chica', capacidad_maxima=3,
        )
        Embarcacion.objects.create(
            empresa=self.empresa, nombre='Panga libre', clase='chica', capacidad_maxima=3,
        )
        Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Habitación sincronización',
            capacidad_maxima=3, activo=True,
        )

    def _crear_pagada(self):
        reserva = Reserva(
            empresa=self.empresa, paquete=self.paquete, fecha=self.inicio + timedelta(days=1),
            inicio_paquete=self.inicio, fecha_salida=self.inicio + timedelta(days=5), hora=time(6, 0),
            numero_personas=2, nombre_cliente='Cliente Pagado', telefono_cliente='+5216121234567',
            correo_cliente='pagado@example.com', canal_origen='web', deslinde_aceptado=True,
            moneda='MXN', estado=Reserva.Estado.PAGADA,
        )
        reserva.full_clean()
        reserva.save()
        return reserva

    def test_guardar_pagada_crea_salidas_sin_webhook(self):
        reserva = self._crear_pagada()
        self.assertEqual(
            list(reserva.salidas.values_list('fecha', flat=True)),
            [self.inicio + timedelta(days=d) for d in (1, 2, 3, 4)],
        )

    def test_reprogramar_pagada_mueve_salidas_y_cupo(self):
        from apps.bookings.cupo.adaptador import obtener_contexto_cupo

        reserva = self._crear_pagada()
        anterior = self.inicio + timedelta(days=1)
        reserva.inicio_paquete += timedelta(days=7)
        reserva.fecha += timedelta(days=7)
        reserva.fecha_salida += timedelta(days=7)
        reserva.full_clean()
        reserva.save()
        self.assertEqual(
            list(reserva.salidas.values_list('fecha', flat=True)),
            [self.inicio + timedelta(days=d) for d in (8, 9, 10, 11)],
        )
        self.assertEqual(obtener_contexto_cupo(anterior, self.empresa).grupos, [])
        self.assertEqual(obtener_contexto_cupo(self.inicio + timedelta(days=9), self.empresa).grupos, [2])

    def test_guardar_dos_veces_no_duplica_salidas(self):
        reserva = self._crear_pagada()
        reserva.save()
        self.assertEqual(reserva.salidas.count(), 4)

    def test_reprogramar_valida_panga_en_las_fechas_nuevas(self):
        reserva = self._crear_pagada()
        reserva.embarcacion = self.panga
        reserva.full_clean()
        reserva.save()
        otra = Reserva(
            empresa=self.empresa, servicio=self.pesca, fecha=self.inicio + timedelta(days=9),
            hora=time(6, 0), numero_personas=2, nombre_cliente='Otra Salida',
            telefono_cliente='+5216121234567', correo_cliente='otra@example.com',
            canal_origen='whatsapp', moneda='MXN', estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.panga,
        )
        otra.full_clean()
        otra.save()
        reserva.inicio_paquete += timedelta(days=7)
        reserva.fecha += timedelta(days=7)
        reserva.fecha_salida += timedelta(days=7)
        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()
        self.assertIn('embarcacion', ctx.exception.message_dict)

    def test_cancelada_conserva_salidas_sin_ocupar_cupo(self):
        from apps.bookings.cupo.adaptador import obtener_contexto_cupo

        reserva = self._crear_pagada()
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.save()
        self.assertEqual(reserva.salidas.count(), 4)
        self.assertEqual(obtener_contexto_cupo(self.inicio + timedelta(days=2), self.empresa).grupos, [])
