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
from django.utils import formats, timezone

from apps.bookings.models import Reserva
from apps.testing import crear_flota

from .services import balances, balances_por_dia, resumen
from .views import PERIODO_DEFAULT, PERIODOS, rango_del_periodo


def momento(anio, mes, dia, hora=12):
    return timezone.make_aware(datetime(anio, mes, dia, hora, 0))


def crear_reserva(**overrides):
    crear_flota()  # el motor de cupo le pregunta a la flota; sin pangas no cabe nadie
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


class RangoDelPeriodoTests(TestCase):
    """Que cada opcion del select signifique el rango que dice.

    Las fechas son la unica entrada de todo el panel: si el rango sale mal, cada
    cifra de la pantalla sale mal y no hay nada que lo delate.
    """

    def test_hoy_es_un_solo_dia(self):
        hoy = date(2026, 8, 19)
        self.assertEqual(rango_del_periodo('hoy', hoy), (hoy, hoy))

    def test_la_semana_arranca_en_lunes(self):
        # 2026-08-19 es miercoles.
        desde, hasta = rango_del_periodo('semana', date(2026, 8, 19))
        self.assertEqual(desde, date(2026, 8, 17))
        self.assertEqual(hasta, date(2026, 8, 19))

    def test_la_semana_que_cruza_de_mes_no_se_corta(self):
        """Un miercoles 2 de septiembre: la semana empezo el 31 de agosto."""
        desde, hasta = rango_del_periodo('semana', date(2026, 9, 2))
        self.assertEqual(desde, date(2026, 8, 31))
        self.assertEqual(hasta, date(2026, 9, 2))

    def test_el_mes_va_del_primero_a_hoy(self):
        """No al ultimo dia del mes: nadie quiere ver dias que no han pasado."""
        desde, hasta = rango_del_periodo('mes', date(2026, 8, 19))
        self.assertEqual(desde, date(2026, 8, 1))
        self.assertEqual(hasta, date(2026, 8, 19))

    def test_el_mes_pasado_va_completo(self):
        desde, hasta = rango_del_periodo('mes_pasado', date(2026, 8, 19))
        self.assertEqual(desde, date(2026, 7, 1))
        self.assertEqual(hasta, date(2026, 7, 31))

    def test_el_mes_pasado_en_enero_es_diciembre_del_ano_anterior(self):
        desde, hasta = rango_del_periodo('mes_pasado', date(2026, 1, 15))
        self.assertEqual(desde, date(2025, 12, 1))
        self.assertEqual(hasta, date(2025, 12, 31))

    def test_el_mes_pasado_de_un_marzo_da_un_febrero_completo(self):
        """Febrero es el mes que rompe cualquier aritmetica de 30 dias."""
        desde, hasta = rango_del_periodo('mes_pasado', date(2026, 3, 10))
        self.assertEqual(desde, date(2026, 2, 1))
        self.assertEqual(hasta, date(2026, 2, 28))

    def test_el_ano_va_del_primero_de_enero_a_hoy(self):
        desde, hasta = rango_del_periodo('ano', date(2026, 8, 19))
        self.assertEqual(desde, date(2026, 1, 1))
        self.assertEqual(hasta, date(2026, 8, 19))

    def test_un_periodo_inventado_cae_en_el_mes(self):
        """Es pantalla de consulta: una URL mal pegada no devuelve un error."""
        hoy = date(2026, 8, 19)
        self.assertEqual(rango_del_periodo('quincena', hoy), rango_del_periodo('mes', hoy))
        self.assertEqual(rango_del_periodo(None, hoy), rango_del_periodo('mes', hoy))

    def test_todas_las_opciones_del_select_resuelven(self):
        """El select y el resolvedor no pueden separarse: una opcion que la vista
        ofrece pero no sabe resolver caeria en el mes sin decir nada."""
        hoy = date(2026, 8, 19)
        for clave, etiqueta in PERIODOS:
            with self.subTest(periodo=clave):
                desde, hasta = rango_del_periodo(clave, hoy)
                self.assertLessEqual(desde, hasta)
                self.assertTrue(etiqueta)


class PanelPorPeriodoTests(TestCase):
    """El select de periodo y la grafica de entrada diaria."""

    def setUp(self):
        self.url = reverse('finanzas')
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )

    def test_el_select_ofrece_todas_las_opciones(self):
        respuesta = self.client.get(self.url)
        for clave, etiqueta in PERIODOS:
            with self.subTest(periodo=clave):
                self.assertContains(respuesta, f'value="{clave}"')
                self.assertContains(respuesta, etiqueta)

    def test_el_periodo_pedido_llega_al_contexto(self):
        respuesta = self.client.get(self.url, {'periodo': 'semana'})
        self.assertEqual(respuesta.context['periodo'], 'semana')

    def test_un_periodo_inventado_no_revienta_y_cae_en_el_mes(self):
        respuesta = self.client.get(self.url, {'periodo': 'quincena'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['periodo'], PERIODO_DEFAULT)

    def test_la_grafica_solo_trae_las_monedas_con_movimiento(self):
        hoy = date.today()
        crear_reserva(monto_pagado=Decimal('4500.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        grafica = self.client.get(self.url, {'periodo': 'hoy'}).context['grafica']

        self.assertEqual(list(grafica), ['MXN'])

    def test_cada_barra_trae_su_dia_su_monto_y_su_altura(self):
        hoy = date.today()
        crear_reserva(monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        barras = self.client.get(self.url, {'periodo': 'hoy'}).context['grafica']['MXN']

        self.assertEqual(len(barras), 1)
        self.assertEqual(barras[0].dia, hoy)
        self.assertEqual(barras[0].monto, Decimal('1000.00'))
        self.assertEqual(barras[0].altura, 100)

    def test_la_barra_mas_alta_es_el_dia_mayor_y_las_otras_se_escalan_contra_el(self):
        hoy = date.today()
        ayer = hoy - timedelta(days=1)
        crear_reserva(monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(ayer, time(12, 0))))
        crear_reserva(monto_pagado=Decimal('500.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        barras = self.client.get(self.url, {'periodo': 'semana'}).context['grafica']['MXN']
        por_dia = {b.dia: b for b in barras}

        self.assertEqual(por_dia[ayer].altura, 100)
        self.assertEqual(por_dia[hoy].altura, 50)

    def test_la_grafica_incluye_los_dias_sin_movimiento_del_periodo(self):
        """Un hueco en la grafica es informacion: se ve que ese dia no entro nada.

        La tabla del historico si los omite, pero ahi cada renglon es un dato; en
        una barra el vacio es el dato."""
        hoy = date.today()
        crear_reserva(monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        barras = self.client.get(self.url, {'periodo': 'mes'}).context['grafica']['MXN']

        self.assertEqual(len(barras), hoy.day)
        self.assertEqual(barras[0].dia, hoy.replace(day=1))
        self.assertEqual(barras[-1].dia, hoy)

    def test_un_periodo_sin_ningun_movimiento_no_divide_entre_cero(self):
        respuesta = self.client.get(self.url, {'periodo': 'hoy'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['grafica'], {})

    def test_el_efectivo_tambien_cuenta_en_la_barra(self):
        """La barra es lo que ENTRO ese dia, no solo lo que cobro Stripe."""
        hoy = date.today()
        momento_hoy = timezone.make_aware(datetime.combine(hoy, time(12, 0)))
        crear_reserva(monto_pagado=Decimal('1000.00'), pagada_en=momento_hoy,
                      monto_efectivo=Decimal('500.00'), efectivo_cobrado_en=momento_hoy)

        barras = self.client.get(self.url, {'periodo': 'hoy'}).context['grafica']['MXN']

        self.assertEqual(barras[0].monto, Decimal('1500.00'))

    def test_el_balance_mostrado_es_el_del_periodo_elegido(self):
        """Es el punto del select: filtrar los balances, no solo la grafica."""
        hoy = date.today()
        hace_diez = hoy - timedelta(days=10)
        crear_reserva(monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))
        crear_reserva(monto_pagado=Decimal('7000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hace_diez, time(12, 0))))

        de_hoy = self.client.get(self.url, {'periodo': 'hoy'}).context['saldo_periodo']
        del_ano = self.client.get(self.url, {'periodo': 'ano'}).context['saldo_periodo']

        self.assertEqual(de_hoy['MXN'].tarjeta, Decimal('1000.00'))
        self.assertEqual(del_ano['MXN'].tarjeta, Decimal('8000.00'))

    def test_el_periodo_elegido_se_nombra_en_la_pantalla(self):
        respuesta = self.client.get(self.url, {'periodo': 'mes_pasado'})
        self.assertEqual(respuesta.context['periodo_etiqueta'], 'Mes pasado')

    def test_un_dia_con_poco_dinero_no_se_ve_como_un_dia_sin_nada(self):
        """500 pesos contra un dia de 100 mil redondean a 0% de altura.

        Una barra invisible miente: dice "ese dia no entro nada" cuando si entro.
        El piso de 1% no distorsiona la lectura y salva el dato."""
        hoy = date.today()
        ayer = hoy - timedelta(days=1)
        crear_reserva(monto_pagado=Decimal('100000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(ayer, time(12, 0))))
        crear_reserva(monto_pagado=Decimal('100.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        barras = self.client.get(self.url, {'periodo': 'semana'}).context['grafica']['MXN']
        por_dia = {b.dia: b for b in barras}

        self.assertEqual(por_dia[hoy].altura, 1)

    def test_un_dia_sin_movimiento_si_tiene_altura_cero(self):
        """El piso es para el dinero chico, no para el vacio."""
        hoy = date.today()
        crear_reserva(monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        barras = self.client.get(self.url, {'periodo': 'mes'}).context['grafica']['MXN']

        self.assertEqual(barras[0].altura, 0)

    def test_la_grafica_rotula_el_primer_y_el_ultimo_dia(self):
        """Sin las dos fechas de los extremos, las barras no dicen de cuando son."""
        hoy = date.today()
        crear_reserva(monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        respuesta = self.client.get(self.url, {'periodo': 'mes'})

        primero = hoy.replace(day=1)
        self.assertContains(respuesta, formats.date_format(primero, 'j M'))
        self.assertContains(respuesta, formats.date_format(hoy, 'j M'))
        # Y nunca el objeto crudo.
        self.assertNotContains(respuesta, 'Barra(dia=')
