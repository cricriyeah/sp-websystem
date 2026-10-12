"""Pruebas del apartado temporal de cupo en el motor (servicio suelto de pesca/recurso por día)."""

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from apps.fleet.models import Embarcacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .cupo import (
    MOTIVO_LLENO,
    MOTIVO_SIN_PANGA,
    apartado_activo,
    construir_retrato_servicio_suelto,
    demanda_apartada_del_dia,
    reservas_con_apartado_vigente,
)
from .models import CupoDiario, Reserva, evaluar_cupo, validar_cupo_diario
from .tests import crear_reserva


class ApartadoMotorCupoTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.servicio = crear_servicio_pesca(self.empresa)
        self.fecha = timezone.localdate() + timedelta(days=5)

    @override_settings(APARTADO_MINUTOS=15)
    def test_apartado_vigente_cuenta_contra_cupo_da_lleno(self):
        crear_flota(self.empresa)
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)

        reserva = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            numero_personas=2,
            nombre_cliente='Ana Ruiz',
        )
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = construir_retrato_servicio_suelto(reserva)
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        motivo = evaluar_cupo(self.fecha, 2, self.empresa)
        self.assertEqual(motivo, MOTIVO_LLENO)

        with self.assertRaises(ValidationError) as ctx:
            validar_cupo_diario(self.fecha, 2, self.empresa)
        self.assertIn('maximo de viajes del dia', str(ctx.exception))

    @override_settings(APARTADO_MINUTOS=15)
    def test_apartado_vigente_cuenta_contra_cupo_da_sin_panga(self):
        # La flota real son 8 pangas de 3 personas y 2 de 5 personas (tope 10 viajes).
        crear_flota(self.empresa)

        # Dos apartados de 4 personas ocupan las dos únicas pangas grandes (capacidad 5).
        r1 = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            numero_personas=4,
            nombre_cliente='Carlos Soto',
        )
        r1.apartado_hasta = timezone.now() + timedelta(minutes=15)
        r1.apartado_demanda = construir_retrato_servicio_suelto(r1)
        r1.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        r2 = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            numero_personas=4,
            nombre_cliente='Elena Gomez',
        )
        r2.apartado_hasta = timezone.now() + timedelta(minutes=15)
        r2.apartado_demanda = construir_retrato_servicio_suelto(r2)
        r2.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        # Un tercer grupo de 4 personas ya no cabe (quedan pangas chicas pero no de 4+).
        motivo = evaluar_cupo(self.fecha, 4, self.empresa)
        self.assertEqual(motivo, MOTIVO_SIN_PANGA)

    @override_settings(APARTADO_MINUTOS=15)
    def test_apartado_vencido_se_ignora(self):
        crear_flota(self.empresa)
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)

        reserva = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            numero_personas=2,
            nombre_cliente='Hugo Perez',
        )
        reserva.apartado_hasta = timezone.now() - timedelta(minutes=1)
        reserva.apartado_demanda = construir_retrato_servicio_suelto(reserva)
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        motivo = evaluar_cupo(self.fecha, 2, self.empresa)
        self.assertIsNone(motivo)

    def test_con_apartado_minutos_cero_se_ignoran_todos(self):
        crear_flota(self.empresa)
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)

        reserva = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            numero_personas=2,
            nombre_cliente='Laura Diaz',
        )
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = construir_retrato_servicio_suelto(reserva)
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        with override_settings(APARTADO_MINUTOS=0):
            self.assertFalse(apartado_activo())
            motivo = evaluar_cupo(self.fecha, 2, self.empresa)
            self.assertIsNone(motivo)

        with override_settings(APARTADO_MINUTOS=15):
            self.assertTrue(apartado_activo())
            motivo = evaluar_cupo(self.fecha, 2, self.empresa)
            self.assertEqual(motivo, MOTIVO_LLENO)

    @override_settings(APARTADO_MINUTOS=15)
    def test_reserva_evaluada_se_excluye_a_si_misma(self):
        crear_flota(self.empresa)
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)

        r = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            numero_personas=2,
            nombre_cliente='Rosa Mora',
        )
        r.apartado_hasta = timezone.now() + timedelta(minutes=15)
        r.apartado_demanda = construir_retrato_servicio_suelto(r)
        r.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        motivo_sin_excluir = evaluar_cupo(self.fecha, 2, self.empresa)
        self.assertEqual(motivo_sin_excluir, MOTIVO_LLENO)

        motivo_excluyendo = evaluar_cupo(self.fecha, 2, self.empresa, excluir_pk=r.pk)
        self.assertIsNone(motivo_excluyendo)

    @override_settings(APARTADO_MINUTOS=15)
    def test_apartado_de_otra_empresa_no_cuenta(self):
        crear_flota(self.empresa)
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)

        empresa_b = Empresa.objects.create(sede=self.sede, nombre='Segunda Empresa', slug='segunda-empresa')
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(empresa_b):
                servicio_b = crear_servicio_pesca(empresa_b)
                crear_flota(empresa_b)
                r_b = crear_reserva(
                    empresa_b,
                    servicio=servicio_b,
                    fecha=self.fecha,
                    estado=Reserva.Estado.PENDIENTE_PAGO,
                    numero_personas=2,
                    nombre_cliente='Mario Luna',
                )
                r_b.apartado_hasta = timezone.now() + timedelta(minutes=15)
                r_b.apartado_demanda = construir_retrato_servicio_suelto(r_b)
                r_b.save(update_fields=['apartado_hasta', 'apartado_demanda'])
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        motivo = evaluar_cupo(self.fecha, 2, self.empresa)
        self.assertIsNone(motivo)

    def test_forma_del_retrato_json(self):
        r = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            numero_personas=3,
            nombre_cliente='Nora Vega',
        )
        retrato = construir_retrato_servicio_suelto(r)
        esperado = {
            "v": 1,
            "salidas": [
                {
                    "fecha": self.fecha.isoformat(),
                    "personas": 3,
                    "servicio_id": self.servicio.pk,
                }
            ],
            "habitaciones": [],
        }
        self.assertEqual(retrato, esperado)

    @override_settings(APARTADO_MINUTOS=15)
    def test_reservas_con_apartado_vigente_solo_trae_pendiente_pago_vigentes(self):
        ahora = timezone.now()

        r_vigente = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            nombre_cliente='Sara Cano',
        )
        r_vigente.apartado_hasta = ahora + timedelta(minutes=15)
        r_vigente.apartado_demanda = construir_retrato_servicio_suelto(r_vigente)
        r_vigente.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        r_vencida = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            nombre_cliente='Pedro Rios',
        )
        r_vencida.apartado_hasta = ahora - timedelta(minutes=5)
        r_vencida.apartado_demanda = construir_retrato_servicio_suelto(r_vencida)
        r_vencida.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        r_sin_demanda = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            nombre_cliente='Tania Mora',
        )
        r_sin_demanda.apartado_hasta = ahora + timedelta(minutes=15)
        r_sin_demanda.apartado_demanda = None
        r_sin_demanda.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        r_pagada = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PAGADA,
            nombre_cliente='Victor Lara',
        )
        r_pagada.apartado_hasta = ahora + timedelta(minutes=15)
        r_pagada.apartado_demanda = construir_retrato_servicio_suelto(r_pagada)
        r_pagada.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        r_cancelada = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.CANCELADA,
            nombre_cliente='Zulema Soto',
        )
        r_cancelada.apartado_hasta = ahora + timedelta(minutes=15)
        r_cancelada.apartado_demanda = construir_retrato_servicio_suelto(r_cancelada)
        r_cancelada.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        vigentes = list(reservas_con_apartado_vigente(self.empresa, ahora=ahora))
        self.assertEqual(vigentes, [r_vigente])

        with override_settings(APARTADO_MINUTOS=0):
            self.assertEqual(list(reservas_con_apartado_vigente(self.empresa, ahora=ahora)), [])
