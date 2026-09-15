"""Pruebas del panel de dinero.

Lo que se protege aqui: que cada peso caiga en el dia en que se movio, que las
monedas no se mezclen, que un reembolso reste, y que la foto completa del dinero
solo la vean los jefes.
"""
import json
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

import unfold

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import formats, timezone

from apps.bookings.models import Reserva
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .services import balances, balances_por_dia, resumen
from .views import PERIODO_DEFAULT, PERIODOS, panel_financiero, rango_del_periodo


def momento(anio, mes, dia, hora=12):
    return timezone.make_aware(datetime(anio, mes, dia, hora, 0))


def crear_reserva(empresa, **overrides):
    empresa_real = overrides.get('empresa', empresa)
    crear_flota(empresa_real)  # el motor de cupo le pregunta a la flota; sin pangas no cabe nadie
    datos = {
        'empresa': empresa_real,
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
    if 'servicio' not in overrides and 'paquete' not in overrides:
        datos['servicio'] = crear_servicio_pesca(empresa_real)
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva



class BalancesTests(EmpresaTestCase):
    def test_el_cobro_con_tarjeta_entra_como_entrada_del_dia_en_que_se_pago(self):
        crear_reserva(self.empresa, monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5))

        del_dia = balances(date(2026, 3, 5), date(2026, 3, 5), empresa=self.empresa)['MXN']

        self.assertEqual(del_dia.tarjeta, Decimal('4500.00'))
        self.assertEqual(del_dia.neto, Decimal('4500.00'))

    def test_el_dinero_cuenta_el_dia_que_entro_no_el_dia_del_viaje(self):
        # Se paga en marzo un viaje de abril: el balance de marzo es el que sube.
        crear_reserva(self.empresa, 
            fecha=date(2026, 4, 20),
            monto_pagado=Decimal('4500.00'),
            pagada_en=momento(2026, 3, 5),
        )

        self.assertEqual(balances(date(2026, 3, 1), date(2026, 3, 31), empresa=self.empresa)['MXN'].tarjeta, Decimal('4500.00'))
        self.assertEqual(balances(date(2026, 4, 1), date(2026, 4, 30), empresa=self.empresa), {})

    def test_tarjeta_y_efectivo_se_reportan_por_separado(self):
        crear_reserva(self.empresa, 
            monto_pagado=Decimal('1350.00'), pagada_en=momento(2026, 3, 5),
            monto_efectivo=Decimal('3150.00'), efectivo_cobrado_en=momento(2026, 3, 5),
        )

        del_dia = balances(date(2026, 3, 5), date(2026, 3, 5), empresa=self.empresa)['MXN']

        self.assertEqual(del_dia.tarjeta, Decimal('1350.00'))
        self.assertEqual(del_dia.efectivo, Decimal('3150.00'))
        self.assertEqual(del_dia.entradas, Decimal('4500.00'))

    def test_el_reembolso_resta_del_balance(self):
        crear_reserva(self.empresa, 
            monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5),
            monto_reembolsado=Decimal('4500.00'), reembolsada_en=momento(2026, 3, 7),
            estado=Reserva.Estado.CANCELADA, reembolsada=True,
        )

        marzo = balances(date(2026, 3, 1), date(2026, 3, 31), empresa=self.empresa)['MXN']

        self.assertEqual(marzo.reembolsos, Decimal('4500.00'))
        self.assertEqual(marzo.neto, Decimal('0.00'))
        # La entrada sigue contando el dia 5 y la salida el dia 7: son dos
        # movimientos distintos, no una entrada que se borra.
        self.assertEqual(balances(date(2026, 3, 5), date(2026, 3, 5), empresa=self.empresa)['MXN'].neto, Decimal('4500.00'))
        self.assertEqual(balances(date(2026, 3, 7), date(2026, 3, 7), empresa=self.empresa)['MXN'].neto, Decimal('-4500.00'))

    def test_marcar_reembolsada_no_es_una_salida_hasta_que_el_dinero_sale(self):
        # La vendedora cancela por mal clima; el reembolso todavia no se ejecuta
        # en Stripe. El dinero sigue en la cuenta y el panel debe decir eso.
        crear_reserva(self.empresa, 
            monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5),
            estado=Reserva.Estado.CANCELADA, reembolsada=True,
        )

        self.assertEqual(balances(empresa=self.empresa)['MXN'].reembolsos, Decimal('0.00'))
        self.assertEqual(balances(empresa=self.empresa)['MXN'].en_cuenta, Decimal('4500.00'))

    def test_pesos_y_dolares_nunca_se_suman(self):
        crear_reserva(self.empresa, monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5))
        crear_reserva(self.empresa, 
            fecha=date.today() + timedelta(days=11),
            moneda=Reserva.Moneda.USD,
            monto_pagado=Decimal('250.00'),
            pagada_en=momento(2026, 3, 5),
        )

        del_dia = balances(date(2026, 3, 5), date(2026, 3, 5), empresa=self.empresa)

        self.assertEqual(del_dia['MXN'].tarjeta, Decimal('4500.00'))
        self.assertEqual(del_dia['USD'].tarjeta, Decimal('250.00'))

    def test_el_efectivo_no_baja_con_un_reembolso(self):
        """Los reembolsos salen por Stripe: descuentan de la cuenta, no de la caja."""
        crear_reserva(self.empresa, 
            monto_pagado=Decimal('1350.00'), pagada_en=momento(2026, 3, 5),
            monto_efectivo=Decimal('3150.00'), efectivo_cobrado_en=momento(2026, 3, 6),
            monto_reembolsado=Decimal('1350.00'), reembolsada_en=momento(2026, 3, 7),
            estado=Reserva.Estado.CANCELADA, reembolsada=True,
        )

        acumulado = balances(empresa=self.empresa)['MXN']

        self.assertEqual(acumulado.en_efectivo, Decimal('3150.00'))
        self.assertEqual(acumulado.en_cuenta, Decimal('0.00'))

    def test_el_historico_omite_los_dias_sin_movimiento(self):
        crear_reserva(self.empresa, monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5))
        crear_reserva(self.empresa, 
            fecha=date.today() + timedelta(days=11),
            monto_pagado=Decimal('4500.00'),
            pagada_en=momento(2026, 3, 20),
        )

        dias = balances_por_dia(date(2026, 3, 1), date(2026, 3, 31), empresa=self.empresa)

        # Mas reciente arriba.
        self.assertEqual([dia for dia, _ in dias], [date(2026, 3, 20), date(2026, 3, 5)])

    def test_el_resumen_arma_dia_mes_y_anio(self):
        hoy = date(2026, 3, 15)
        crear_reserva(self.empresa, monto_pagado=Decimal('100.00'), pagada_en=momento(2026, 3, 15))
        crear_reserva(self.empresa, 
            fecha=date.today() + timedelta(days=11),
            monto_pagado=Decimal('200.00'), pagada_en=momento(2026, 3, 2),
        )
        crear_reserva(self.empresa, 
            fecha=date.today() + timedelta(days=12),
            monto_pagado=Decimal('400.00'), pagada_en=momento(2026, 1, 9),
        )

        datos = resumen(hoy, empresa=self.empresa)

        self.assertEqual(datos['dia']['MXN'].tarjeta, Decimal('100.00'))
        self.assertEqual(datos['mes']['MXN'].tarjeta, Decimal('300.00'))
        self.assertEqual(datos['anio']['MXN'].tarjeta, Decimal('700.00'))


class PanelTests(EmpresaTestCase):
    """El panel es la unica pantalla con la foto completa del dinero."""

    def setUp(self):
        self.url = reverse('finanzas')

    def test_los_jefes_lo_ven(self):
        self.client.force_login(self.crear_jefe())
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_la_vendedora_no_lo_ve(self):
        vendedora = User.objects.create_user('maria', 'maria@example.com', 'x', is_staff=True)
        self.client.force_login(vendedora)
        self._alcance.__exit__(None, None, None)
        try:
            self.assertEqual(self.client.get(self.url).status_code, 403)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

    def test_sin_sesion_manda_al_login_del_admin(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('login', respuesta['Location'])

    def test_el_menu_lateral_del_admin_lleva_a_finanzas(self):
        self.client.force_login(self.crear_jefe(is_superuser=True))
        respuesta = self.client.get('/admin/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.url)

    def test_un_mes_invalido_en_la_url_no_revienta(self):
        self.client.force_login(self.crear_jefe())
        self.assertEqual(self.client.get(self.url, {'mes': 'hola'}).status_code, 200)

    def test_el_jefe_de_una_empresa_no_ve_dinero_de_otra(self):
        """Nuevo: `panel_financiero` corta con `scope.empresa_actual(request)`, no
        con `is_superuser` (retrofit de finance/views.py, fuera de este grupo) —
        este test prueba que el filtro real aplica, no solo que la pantalla carga."""
        crear_reserva(self.empresa, monto_pagado=Decimal('4500.00'), pagada_en=timezone.now())

        otra_sede = Sede.objects.create(nombre='Otra', slug='otra-sede-panel', zona_horaria='America/Mazatlan')
        otra_empresa = Empresa.objects.create(sede=otra_sede, nombre='Otra Empresa', slug='otra-empresa-panel', activo=True)
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                crear_reserva(otra_empresa, monto_pagado=Decimal('9999.00'), pagada_en=timezone.now())
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        self.client.force_login(self.crear_jefe())
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, '4,500.00')
        self.assertNotContains(respuesta, '9,999.00')


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


class PanelPorPeriodoTests(EmpresaTestCase):
    """El select de periodo y la grafica de entrada diaria."""

    def setUp(self):
        self.url = reverse('finanzas')
        self.client.force_login(self.crear_jefe())

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

    def test_el_balance_mostrado_es_el_del_periodo_elegido(self):
        """Es el punto del select: filtrar los balances, no solo la grafica."""
        hoy = date.today()
        hace_diez = hoy - timedelta(days=10)
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))
        crear_reserva(self.empresa, monto_pagado=Decimal('7000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hace_diez, time(12, 0))))

        de_hoy = self.client.get(self.url, {'periodo': 'hoy'}).context['saldo_periodo']
        del_ano = self.client.get(self.url, {'periodo': 'ano'}).context['saldo_periodo']

        self.assertEqual(de_hoy['MXN'].tarjeta, Decimal('1000.00'))
        self.assertEqual(del_ano['MXN'].tarjeta, Decimal('8000.00'))

    def test_el_periodo_elegido_se_nombra_en_la_pantalla(self):
        respuesta = self.client.get(self.url, {'periodo': 'mes_pasado'})
        self.assertEqual(respuesta.context['periodo_etiqueta'], 'Mes pasado')

    def _serie(self, periodo, moneda='MXN'):
        """El JSON que la vista le entrega al canvas de Chart.js."""
        grafica = self.client.get(self.url, {'periodo': periodo}).context['grafica']
        return json.loads(grafica[moneda])

    def test_solo_grafica_las_monedas_con_movimiento(self):
        """Una grafica plana de dolares en un mes que solo cobro pesos es ruido."""
        hoy = date.today()
        crear_reserva(self.empresa, monto_pagado=Decimal('4500.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        grafica = self.client.get(self.url, {'periodo': 'hoy'}).context['grafica']

        self.assertEqual(list(grafica), ['MXN'])

    def test_un_periodo_sin_movimiento_no_grafica_nada(self):
        self.assertEqual(self.client.get(self.url, {'periodo': 'hoy'}).context['grafica'], {})

    def test_una_etiqueta_y_un_dato_por_cada_dia_del_periodo(self):
        """Los dias vacios se grafican a proposito: en una grafica el hueco es el dato."""
        hoy = date.today()
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        serie = self._serie('mes')

        self.assertEqual(len(serie['labels']), hoy.day)
        self.assertEqual(len(serie['datasets'][0]['data']), hoy.day)
        self.assertEqual(serie['datasets'][0]['data'][0], 0)
        self.assertEqual(serie['datasets'][0]['data'][-1], 1000.0)

    def test_el_dato_de_cada_dia_es_lo_que_entro_ese_dia(self):
        """Tarjeta mas efectivo: la barra es lo que ENTRO, no solo lo que cobro Stripe."""
        hoy = date.today()
        cuando = timezone.make_aware(datetime.combine(hoy, time(12, 0)))
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'), pagada_en=cuando,
                      monto_efectivo=Decimal('500.00'), efectivo_cobrado_en=cuando)

        self.assertEqual(self._serie('hoy')['datasets'][0]['data'], [1500.0])

    def test_el_color_sigue_al_tema_del_admin(self):
        """Se manda la variable CSS, no un color fijo: el app.js de Unfold la
        resuelve contra el tema, asi que la grafica cambia con el modo oscuro y
        con el color primario que se configure."""
        hoy = date.today()
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        self.assertIn('var(--color-primary', self._serie('hoy')['datasets'][0]['backgroundColor'])

    def test_la_moneda_nombra_la_serie(self):
        """MXN y USD nunca se mezclan: cada grafica dice de que moneda habla."""
        hoy = date.today()
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        self.assertIn('MXN', self._serie('hoy')['datasets'][0]['label'])

    def test_la_pagina_pinta_un_canvas_por_moneda(self):
        """El canvas con class="chart" es lo que el app.js de Unfold busca para
        instanciar Chart.js. Sin esa clase y sin data-value no se dibuja nada."""
        hoy = date.today()
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        html = self.client.get(self.url, {'periodo': 'hoy'}).content.decode()

        self.assertRegex(html, r'<canvas[^>]*class="[^"]*chart[^"]*"[^>]*data-type="bar"')
        self.assertIn('data-value', html)

    def test_las_barras_no_se_quedan_con_el_grosor_de_sparkline_de_unfold(self):
        """Unfold trae `maxBarThickness: 4` en sus opciones por defecto.

        Tiene sentido para sus graficas de tarjeta, que son sparklines; en una
        grafica mensual a todo lo ancho deja unas rayitas de 4px ilegibles. Se
        corrige en el dataset y no mandando `options` propias, porque el app.js
        **reemplaza** sus opciones enteras si se le pasan — y ahi se irian la
        rejilla punteada, los colores del tema y el tooltip.
        """
        hoy = date.today()
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        dataset = self._serie('mes')['datasets'][0]

        self.assertGreater(dataset['maxBarThickness'], 4)

    def test_no_se_mandan_opciones_propias_al_canvas(self):
        """Mandar `options` tira las de Unfold completas. Ver el test de arriba."""
        hoy = date.today()
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'),
                      pagada_en=timezone.make_aware(datetime.combine(hoy, time(12, 0))))

        html = self.client.get(self.url, {'periodo': 'hoy'}).content.decode()

        self.assertNotIn('data-options', html)


class BalancesFiltradosPorEmpresaTests(TestCase):
    def setUp(self):
        # Slug distinto de 'la-paz' -- ya existe, sembrado por
        # tenancy.0002_crear_sede_empresa_la_paz (ver apps/testing.py).
        self.sede = Sede.objects.create(
            nombre='Sede finance test', slug='sede-finance-test', zona_horaria='America/Mazatlan',
        )
        self.empresa_a = Empresa.objects.create(
            sede=self.sede, nombre='A', slug='empresa-a',
            stripe_secret_key='sk_a', stripe_webhook_secret='whsec_a',
            stripe_publishable_key='pk_a',
        )
        self.empresa_b = Empresa.objects.create(
            sede=self.sede, nombre='B', slug='empresa-b',
            stripe_secret_key='sk_b', stripe_webhook_secret='whsec_b',
            stripe_publishable_key='pk_b',
        )
        self.hoy = date.today()
        with scope.con_empresa(self.empresa_a):
            crear_flota(self.empresa_a)
            self._crear_reserva_pagada(self.empresa_a, Decimal('1000.00'))
        with scope.con_empresa(self.empresa_b):
            crear_flota(self.empresa_b)
            self._crear_reserva_pagada(self.empresa_b, Decimal('2000.00'))

    def _crear_reserva_pagada(self, empresa, monto):
        reserva = Reserva(
            empresa=empresa, servicio=crear_servicio_pesca(empresa),
            fecha=self.hoy + timedelta(days=10), hora=time(6, 0),
            numero_personas=2, nombre_cliente='Cliente', telefono_cliente='+5216121234567',
            correo_cliente='cliente@example.com', canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True, deslinde_nombre='Cliente', checkout_id=uuid.uuid4(),
            moneda='MXN', estado=Reserva.Estado.PAGADA,
            monto_pagado=monto, pagada_en=timezone.now(),
        )
        reserva.full_clean()
        reserva.save()
        return reserva

    def test_sin_empresa_suma_todas(self):
        # `balances()` no abre alcance por su cuenta (lo hace la vista): el
        # "consolidado sin filtro" se ejecuta como operador de plataforma.
        with scope.como_operador_plataforma():
            total = balances()['MXN'].tarjeta
        self.assertEqual(total, Decimal('3000.00'))

    def test_con_empresa_solo_esa(self):
        with scope.con_empresa(self.empresa_a):
            total = balances(empresa=self.empresa_a)['MXN'].tarjeta
        self.assertEqual(total, Decimal('1000.00'))

    def test_resumen_respeta_el_filtro(self):
        with scope.con_empresa(self.empresa_b):
            acumulado = resumen(self.hoy, empresa=self.empresa_b)['acumulado']['MXN'].tarjeta
        self.assertEqual(acumulado, Decimal('2000.00'))


class PanelFinancieroPermisoTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='jefe', password='x', is_staff=True)

    @mock.patch('apps.finance.views.scope.empresa_actual')
    @mock.patch('apps.finance.views.scope.es_operador_plataforma')
    def test_sin_membresia_ni_operador_403(self, mock_operador, mock_empresa_actual):
        mock_operador.return_value = False
        mock_empresa_actual.return_value = None
        request = self.factory.get('/admin/finanzas/')
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            panel_financiero(request)

    @mock.patch('apps.finance.views.scope.empresa_actual')
    @mock.patch('apps.finance.views.scope.es_operador_plataforma')
    @mock.patch('apps.finance.views.resumen')
    @mock.patch('apps.finance.views.balances')
    @mock.patch('apps.finance.views.balances_por_dia')
    def test_jefe_ve_solo_su_empresa(
        self, mock_balances_por_dia, mock_balances, mock_resumen,
        mock_operador, mock_empresa_actual,
    ):
        mock_operador.return_value = False
        empresa = mock.Mock()
        mock_empresa_actual.return_value = empresa
        mock_resumen.return_value = {'dia': {}, 'mes': {}, 'anio': {}, 'acumulado': {}}
        mock_balances.return_value = {}
        mock_balances_por_dia.return_value = []

        request = self.factory.get('/admin/finanzas/')
        request.user = self.user
        panel_financiero(request)

        self.assertEqual(mock_resumen.call_args.kwargs.get('empresa'), empresa)
        self.assertEqual(mock_balances.call_args.kwargs.get('empresa'), empresa)
        self.assertEqual(mock_balances_por_dia.call_args.kwargs.get('empresa'), empresa)

    @mock.patch('apps.finance.views.scope.empresa_actual')
    @mock.patch('apps.finance.views.scope.es_operador_plataforma')
    @mock.patch('apps.finance.views.resumen')
    @mock.patch('apps.finance.views.balances')
    @mock.patch('apps.finance.views.balances_por_dia')
    def test_operador_de_plataforma_ve_todas(
        self, mock_balances_por_dia, mock_balances, mock_resumen,
        mock_operador, mock_empresa_actual,
    ):
        mock_operador.return_value = True
        mock_empresa_actual.return_value = None
        mock_resumen.return_value = {'dia': {}, 'mes': {}, 'anio': {}, 'acumulado': {}}
        mock_balances.return_value = {}
        mock_balances_por_dia.return_value = []

        request = self.factory.get('/admin/finanzas/')
        request.user = self.user
        panel_financiero(request)

        self.assertIsNone(mock_resumen.call_args.kwargs.get('empresa'))
