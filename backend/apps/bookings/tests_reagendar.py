"""Servicio de reagendado (`apps/bookings/reagendar.py`).

El servicio solo asigna campos, toma candados y deja que `Reserva.clean()` y el motor de cupo decidan: aqui se
prueba que respeta esas reglas, que sus dos excepciones al modelo (48 h con autorizacion, codigo promocional ya
vencido) no se filtran al formulario normal del admin, y que lo que no es suyo (precio, cobro) no se mueve.
Las carreras entre dos operadoras viven en `tests_reagendar_carreras.py` (solo Postgres).
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.fleet.models import CodigoPromocional
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .models import Reserva


class ReagendarBase(EmpresaTestCase):
    """Una empresa con su flota, el servicio de pesca y dos personas con rol (jefa y vendedora)."""

    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.pesca = crear_servicio_pesca(self.empresa)
        self.jefa = self.crear_jefe('jefa-reagendar')
        self.vendedora = self.crear_vendedora('vendedora-reagendar')
        self.hoy = timezone.localdate()

    def datos_de_reserva(self, **extra):
        datos = dict(
            empresa=self.empresa, servicio=self.pesca, fecha=self.hoy + timedelta(days=10),
            hora=None, numero_personas=2, nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
            deslinde_nombre='Ana Ruiz', estado=Reserva.Estado.PAGADA, moneda='MXN',
            precio_total=Decimal('4500.00'), monto_pagado=Decimal('4500.00'),
            forma_pago=Reserva.FormaPago.COMPLETO,
        )
        datos.update(extra)
        return datos

    def crear_reserva(self, **extra):
        from datetime import time

        extra.setdefault('hora', time(6, 0))
        reserva = Reserva(**self.datos_de_reserva(**extra))
        reserva.full_clean()
        reserva.save()
        # Como la entrega el admin: cargada de la base, con sus "originales" tomados por `from_db`.
        return Reserva.objects.get(pk=reserva.pk)


class ExcepcionesDelModeloTests(ReagendarBase):
    """Los dos ganchos que el servicio le pone al modelo no cambian el formulario normal."""

    def test_sin_el_gancho_el_modelo_sigue_exigiendo_48_horas(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))
        reserva.fecha = self.hoy + timedelta(days=9)

        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()

        self.assertIn('fecha', ctx.exception.error_dict)

    def test_con_la_excepcion_de_48_horas_el_modelo_deja_pasar_el_cambio(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))
        reserva.fecha = self.hoy + timedelta(days=9)
        reserva._excepcion_48h = True

        reserva.full_clean()  # no lanza

    def test_la_excepcion_de_48_horas_no_toca_las_demas_reglas_de_fecha(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))
        reserva.fecha = self.hoy + timedelta(days=9)
        reserva._excepcion_48h = True
        reserva.hora = reserva.hora.replace(hour=9)  # fuera de la ventana de pesca (5 a 7)

        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()

        self.assertIn('hora', ctx.exception.error_dict)

    def _reserva_con_codigo_vencido(self):
        codigo = CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO', porcentaje_descuento=Decimal('10'),
        )
        reserva = self.crear_reserva(
            codigo_promocional=codigo, descuento_aplicado=Decimal('450.00'),
            precio_total=Decimal('4050.00'), monto_pagado=Decimal('4050.00'),
        )
        CodigoPromocional.objects.filter(pk=codigo.pk).update(fecha_fin=timezone.now() - timedelta(days=1))
        return Reserva.objects.get(pk=reserva.pk)

    def test_un_codigo_promocional_vencido_ya_bloquea_cualquier_guardado_validado(self):
        # Fija el supuesto de D5: sin el gancho, reagendar fallaria por un codigo que el cliente ya uso.
        reserva = self._reserva_con_codigo_vencido()

        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()

        self.assertIn('codigo_promocional', ctx.exception.error_dict)

    def test_reagendando_no_vuelve_a_validar_el_codigo_promocional(self):
        reserva = self._reserva_con_codigo_vencido()
        reserva._reagendando = True

        reserva.full_clean()  # no lanza

    def test_los_ganchos_solo_existen_en_memoria(self):
        reserva = self.crear_reserva()
        reserva._excepcion_48h = True
        reserva._reagendando = True
        reserva.save()

        recargada = Reserva.objects.get(pk=reserva.pk)

        self.assertFalse(getattr(recargada, '_excepcion_48h', False))
        self.assertFalse(getattr(recargada, '_reagendando', False))
