"""Pruebas del panel de dinero.

Lo que se protege aqui: que cada peso caiga en el dia en que se movio, que las
monedas no se mezclen, que un reembolso reste, y que la foto completa del dinero
solo la vean los jefes.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva

from .services import balances, balances_por_dia, resumen


def momento(anio, mes, dia, hora=12):
    return timezone.make_aware(datetime(anio, mes, dia, hora, 0))


def crear_reserva(**overrides):
    datos = {
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
        'estado': Reserva.Estado.PAGADA,
    }
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva


class BalancesTests(TestCase):
    def test_el_cobro_con_tarjeta_entra_como_entrada_del_dia_en_que_se_pago(self):
        crear_reserva(monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5))

        del_dia = balances(date(2026, 3, 5), date(2026, 3, 5))['MXN']

        self.assertEqual(del_dia.tarjeta, Decimal('4500.00'))
        self.assertEqual(del_dia.neto, Decimal('4500.00'))

    def test_el_dinero_cuenta_el_dia_que_entro_no_el_dia_del_viaje(self):
        # Se paga en marzo un viaje de abril: el balance de marzo es el que sube.
        crear_reserva(
            fecha=date(2026, 4, 20),
            monto_pagado=Decimal('4500.00'),
            pagada_en=momento(2026, 3, 5),
        )

        self.assertEqual(balances(date(2026, 3, 1), date(2026, 3, 31))['MXN'].tarjeta, Decimal('4500.00'))
        self.assertEqual(balances(date(2026, 4, 1), date(2026, 4, 30)), {})

    def test_tarjeta_y_efectivo_se_reportan_por_separado(self):
        crear_reserva(
            monto_pagado=Decimal('1350.00'), pagada_en=momento(2026, 3, 5),
            monto_efectivo=Decimal('3150.00'), efectivo_cobrado_en=momento(2026, 3, 5),
        )

        del_dia = balances(date(2026, 3, 5), date(2026, 3, 5))['MXN']

        self.assertEqual(del_dia.tarjeta, Decimal('1350.00'))
        self.assertEqual(del_dia.efectivo, Decimal('3150.00'))
        self.assertEqual(del_dia.entradas, Decimal('4500.00'))

    def test_el_reembolso_resta_del_balance(self):
        crear_reserva(
            monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5),
            monto_reembolsado=Decimal('4500.00'), reembolsada_en=momento(2026, 3, 7),
            estado=Reserva.Estado.CANCELADA, reembolsada=True,
        )

        marzo = balances(date(2026, 3, 1), date(2026, 3, 31))['MXN']

        self.assertEqual(marzo.reembolsos, Decimal('4500.00'))
        self.assertEqual(marzo.neto, Decimal('0.00'))
        # La entrada sigue contando el dia 5 y la salida el dia 7: son dos
        # movimientos distintos, no una entrada que se borra.
        self.assertEqual(balances(date(2026, 3, 5), date(2026, 3, 5))['MXN'].neto, Decimal('4500.00'))
        self.assertEqual(balances(date(2026, 3, 7), date(2026, 3, 7))['MXN'].neto, Decimal('-4500.00'))

    def test_marcar_reembolsada_no_es_una_salida_hasta_que_el_dinero_sale(self):
        # La vendedora cancela por mal clima; el reembolso todavia no se ejecuta
        # en Stripe. El dinero sigue en la cuenta y el panel debe decir eso.
        crear_reserva(
            monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5),
            estado=Reserva.Estado.CANCELADA, reembolsada=True,
        )

        self.assertEqual(balances()['MXN'].reembolsos, Decimal('0.00'))
        self.assertEqual(balances()['MXN'].en_cuenta, Decimal('4500.00'))

    def test_pesos_y_dolares_nunca_se_suman(self):
        crear_reserva(monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5))
        crear_reserva(
            fecha=date.today() + timedelta(days=11),
            moneda=Reserva.Moneda.USD,
            monto_pagado=Decimal('250.00'),
            pagada_en=momento(2026, 3, 5),
        )

        del_dia = balances(date(2026, 3, 5), date(2026, 3, 5))

        self.assertEqual(del_dia['MXN'].tarjeta, Decimal('4500.00'))
        self.assertEqual(del_dia['USD'].tarjeta, Decimal('250.00'))

    def test_el_efectivo_no_baja_con_un_reembolso(self):
        """Los reembolsos salen por Stripe: descuentan de la cuenta, no de la caja."""
        crear_reserva(
            monto_pagado=Decimal('1350.00'), pagada_en=momento(2026, 3, 5),
            monto_efectivo=Decimal('3150.00'), efectivo_cobrado_en=momento(2026, 3, 6),
            monto_reembolsado=Decimal('1350.00'), reembolsada_en=momento(2026, 3, 7),
            estado=Reserva.Estado.CANCELADA, reembolsada=True,
        )

        acumulado = balances()['MXN']

        self.assertEqual(acumulado.en_efectivo, Decimal('3150.00'))
        self.assertEqual(acumulado.en_cuenta, Decimal('0.00'))

    def test_el_historico_omite_los_dias_sin_movimiento(self):
        crear_reserva(monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5))
        crear_reserva(
            fecha=date.today() + timedelta(days=11),
            monto_pagado=Decimal('4500.00'),
            pagada_en=momento(2026, 3, 20),
        )

        dias = balances_por_dia(date(2026, 3, 1), date(2026, 3, 31))

        # Mas reciente arriba.
        self.assertEqual([dia for dia, _ in dias], [date(2026, 3, 20), date(2026, 3, 5)])

    def test_el_resumen_arma_dia_mes_y_anio(self):
        hoy = date(2026, 3, 15)
        crear_reserva(monto_pagado=Decimal('100.00'), pagada_en=momento(2026, 3, 15))
        crear_reserva(
            fecha=date.today() + timedelta(days=11),
            monto_pagado=Decimal('200.00'), pagada_en=momento(2026, 3, 2),
        )
        crear_reserva(
            fecha=date.today() + timedelta(days=12),
            monto_pagado=Decimal('400.00'), pagada_en=momento(2026, 1, 9),
        )

        datos = resumen(hoy)

        self.assertEqual(datos['dia']['MXN'].tarjeta, Decimal('100.00'))
        self.assertEqual(datos['mes']['MXN'].tarjeta, Decimal('300.00'))
        self.assertEqual(datos['anio']['MXN'].tarjeta, Decimal('700.00'))


class PanelTests(TestCase):
    """El panel es la unica pantalla con la foto completa del dinero."""

    def setUp(self):
        self.url = reverse('finanzas')

    def test_los_jefes_lo_ven(self):
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_la_vendedora_no_lo_ve(self):
        vendedora = User.objects.create_user('maria', 'maria@example.com', 'x', is_staff=True)
        self.client.force_login(vendedora)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_sin_sesion_manda_al_login_del_admin(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('login', respuesta['Location'])

    def test_el_menu_lateral_del_admin_lleva_a_finanzas(self):
        """El menu de unfold se arma a mano en `UNFOLD['SIDEBAR']` (config/settings/
        base.py): un link mal escrito ahi tumba el admin entero, no solo su item."""
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )
        respuesta = self.client.get('/admin/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.url)

    def test_un_mes_invalido_en_la_url_no_revienta(self):
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )
        self.assertEqual(self.client.get(self.url, {'mes': 'hola'}).status_code, 200)
