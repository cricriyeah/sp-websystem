"""Pruebas del panel de finanzas simplificado y enlaces al detalle de movimientos.

Cubre el Paso 7 (Tarea 2):
1. Cada cifra distinta de cero del panel es un enlace a finanzas_movimientos con
   concepto, moneda y fechas correctas. Cifras en cero no son enlaces.
2. De punta a punta: siguiendo el enlace de una cifra con el cliente Django, el
   total calculado en Movimientos coincide exactamente con la cifra del panel.
3. Las tres tarjetas del acumulado («Lo que debería haber») enlazan a
   stripe / efectivo / transferencia sin fechas de filtro.
4. El panel ya no contiene las secciones fijas «Hoy ·», «Mes en curso» ni
   «Año en curso», y conserva el selector de periodo, la gráfica, el histórico
   y la línea de ayuda «Toca una cifra para ver las reservas que la forman.».
"""
import html
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.finance.services import balances, resumen
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca


def momento(anio, mes, dia, hora=12):
    return timezone.make_aware(datetime(anio, mes, dia, hora, 0))


def crear_reserva(empresa, **overrides):
    empresa_real = overrides.get('empresa', empresa)
    crear_flota(empresa_real)
    datos = {
        'empresa': empresa_real,
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Carlos Vega',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'carlos@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Carlos Vega',
        'estado': Reserva.Estado.PAGADA,
    }
    if 'servicio' not in overrides and 'paquete' not in overrides:
        datos['servicio'] = crear_servicio_pesca(empresa_real)
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva


class PanelSimplificacionEstructuraTests(EmpresaTestCase):
    """Simplificación del panel: eliminación de secciones fijas y elementos conservados."""

    def setUp(self):
        super().setUp()
        self.url = reverse('finanzas')
        self.client.force_login(self.crear_jefe())

    def test_panel_ya_no_contiene_secciones_fijas_hoy_mes_ano(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Hoy ·')
        self.assertNotContains(resp, 'Mes en curso')
        self.assertNotContains(resp, 'Año en curso')
        self.assertNotContains(resp, 'Ano en curso')

    def test_panel_conserva_selector_grafica_e_historico(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="periodo"')
        self.assertContains(resp, 'Historico ·')

    def test_panel_muestra_linea_de_ayuda_bajo_el_titulo(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Toca una cifra para ver las reservas que la forman.')

    def test_contexto_panel_no_expone_dia_mes_ni_anio(self):
        resp = self.client.get(self.url)
        self.assertNotIn('dia', resp.context)
        self.assertNotIn('mes', resp.context)
        self.assertNotIn('anio', resp.context)
        self.assertIn('acumulado', resp.context)
        self.assertIn('saldo_periodo', resp.context)


class TarjetasAcumuladoEnlacesTests(EmpresaTestCase):
    """Las tres tarjetas 'Lo que debería haber' enlazan a stripe, efectivo y transferencia sin fechas."""

    def setUp(self):
        super().setUp()
        self.url = reverse('finanzas')
        self.client.force_login(self.crear_jefe())

    def test_tarjetas_acumulado_distintas_de_cero_enlazan_sin_fechas(self):
        crear_reserva(
            self.empresa,
            monto_pagado=Decimal('5000.00'),
            pagada_en=momento(2026, 8, 10),
            monto_efectivo=Decimal('1500.00'),
            efectivo_cobrado_en=momento(2026, 8, 11),
            monto_transferencia=Decimal('2000.00'),
            transferencia_registrada_en=momento(2026, 8, 12),
        )
        crear_reserva(
            self.empresa,
            fecha=date.today() + timedelta(days=12),
            monto_pagado=Decimal('1000.00'),
            pagada_en=momento(2026, 8, 1),
            monto_reembolsado=Decimal('1000.00'),
            reembolsada_en=momento(2026, 8, 15),
            estado=Reserva.Estado.CANCELADA,
            reembolsada=True,
        )

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

        # En la cuenta: 5000 - 1000 = 4000
        url_movimientos = reverse('finanzas_movimientos')
        enlace_stripe = f'{url_movimientos}?concepto=stripe&moneda=MXN'
        enlace_efectivo = f'{url_movimientos}?concepto=efectivo&moneda=MXN'
        enlace_transferencia = f'{url_movimientos}?concepto=transferencia&moneda=MXN'

        self.assertContains(resp, enlace_stripe)
        self.assertContains(resp, enlace_efectivo)
        self.assertContains(resp, enlace_transferencia)

        # Ninguno debe llevar fechas desde o hasta
        contenido = resp.content.decode()
        for enlace in [enlace_stripe, enlace_efectivo, enlace_transferencia]:
            patron = rf'href="{re.escape(enlace)}[^"]*"'
            coincidencias = re.findall(patron, contenido)
            for coincidencia in coincidencias:
                self.assertNotIn('desde=', coincidencia)
                self.assertNotIn('hasta=', coincidencia)

    def test_tarjetas_acumulado_en_cero_no_son_enlaces(self):
        # Solo creamos un movimiento en efectivo: tarjeta y banco quedan en cero
        crear_reserva(
            self.empresa,
            monto_efectivo=Decimal('1200.00'),
            efectivo_cobrado_en=momento(2026, 8, 10),
        )

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

        contenido = resp.content.decode()
        # Efectivo sí es enlace
        self.assertIn('concepto=efectivo&moneda=MXN', contenido)
        # Stripe y Transferencia no tienen enlace porque su saldo es 0.00
        self.assertNotIn('concepto=stripe&moneda=MXN', contenido)
        self.assertNotIn('concepto=transferencia&moneda=MXN', contenido)


class TablaPeriodoEnlacesTests(EmpresaTestCase):
    """Cifras de la tabla del periodo seleccionado enlazan con concepto, moneda y fechas."""

    def setUp(self):
        super().setUp()
        self.url = reverse('finanzas')
        self.client.force_login(self.crear_jefe())

    def test_cifras_periodo_distintas_de_cero_son_enlaces_con_fechas(self):
        hoy = date.today()
        cuando = timezone.make_aware(datetime.combine(hoy, time(12, 0)))

        crear_reserva(
            self.empresa,
            monto_pagado=Decimal('3000.00'),
            pagada_en=cuando,
            monto_efectivo=Decimal('1000.00'),
            efectivo_cobrado_en=cuando,
            monto_transferencia=Decimal('1500.00'),
            transferencia_registrada_en=cuando,
        )
        crear_reserva(
            self.empresa,
            fecha=hoy + timedelta(days=15),
            monto_pagado=Decimal('500.00'),
            pagada_en=cuando,
            monto_reembolsado=Decimal('500.00'),
            reembolsada_en=cuando,
            estado=Reserva.Estado.CANCELADA,
            reembolsada=True,
        )

        resp = self.client.get(self.url, {'periodo': 'hoy'})
        self.assertEqual(resp.status_code, 200)

        fecha_str = hoy.strftime('%Y-%m-%d')
        frag_fechas = f'desde={fecha_str}&hasta={fecha_str}'

        self.assertContains(resp, f'concepto=tarjeta&moneda=MXN&{frag_fechas}')
        self.assertContains(resp, f'concepto=efectivo&moneda=MXN&{frag_fechas}')
        self.assertContains(resp, f'concepto=transferencia&moneda=MXN&{frag_fechas}')
        self.assertContains(resp, f'concepto=reembolsos&moneda=MXN&{frag_fechas}')
        self.assertContains(resp, f'concepto=todos&moneda=MXN&{frag_fechas}')

    def test_cifras_periodo_en_cero_no_son_enlaces(self):
        hoy = date.today()
        cuando = timezone.make_aware(datetime.combine(hoy, time(12, 0)))

        # Solo tarjeta: efectivo, transferencia y reembolsos quedan en 0.00
        crear_reserva(
            self.empresa,
            monto_pagado=Decimal('2000.00'),
            pagada_en=cuando,
        )

        resp = self.client.get(self.url, {'periodo': 'hoy'})
        self.assertEqual(resp.status_code, 200)

        fecha_str = hoy.strftime('%Y-%m-%d')
        frag_fechas = f'desde={fecha_str}&hasta={fecha_str}'

        # Tarjeta y balance neto (2000) son enlaces
        self.assertContains(resp, f'concepto=tarjeta&moneda=MXN&{frag_fechas}')
        self.assertContains(resp, f'concepto=todos&moneda=MXN&{frag_fechas}')

        # Cero no se enlaza
        self.assertNotContains(resp, f'concepto=efectivo&moneda=MXN&{frag_fechas}')
        self.assertNotContains(resp, f'concepto=transferencia&moneda=MXN&{frag_fechas}')
        self.assertNotContains(resp, f'concepto=reembolsos&moneda=MXN&{frag_fechas}')


class HistoricoDiaEnlacesTests(EmpresaTestCase):
    """En la tabla del histórico día por día, cada cifra enlaza con desde=hasta=ese_dia."""

    def setUp(self):
        super().setUp()
        self.url = reverse('finanzas')
        self.client.force_login(self.crear_jefe())

    def test_cifras_historico_dia_enlazan_con_desde_hasta_ese_dia(self):
        dia_10 = momento(2026, 4, 10, 10)
        dia_15 = momento(2026, 4, 15, 12)

        # Dia 10: tarjeta, efectivo, transferencia, reembolso
        crear_reserva(
            self.empresa,
            fecha=date(2026, 4, 20),
            monto_pagado=Decimal('2000.00'),
            pagada_en=dia_10,
            monto_efectivo=Decimal('800.00'),
            efectivo_cobrado_en=dia_10,
            monto_transferencia=Decimal('1200.00'),
            transferencia_registrada_en=dia_10,
        )
        crear_reserva(
            self.empresa,
            fecha=date(2026, 4, 21),
            monto_pagado=Decimal('400.00'),
            pagada_en=dia_10,
            monto_reembolsado=Decimal('400.00'),
            reembolsada_en=dia_10,
            estado=Reserva.Estado.CANCELADA,
            reembolsada=True,
        )

        # Dia 15: solo tarjeta
        crear_reserva(
            self.empresa,
            fecha=date(2026, 4, 25),
            monto_pagado=Decimal('1500.00'),
            pagada_en=dia_15,
        )

        resp = self.client.get(self.url, {'mes': '2026-04'})
        self.assertEqual(resp.status_code, 200)

        # Verificación para el dia 10
        fechas_10 = 'desde=2026-04-10&hasta=2026-04-10'
        self.assertContains(resp, f'concepto=tarjeta&moneda=MXN&{fechas_10}')
        self.assertContains(resp, f'concepto=efectivo&moneda=MXN&{fechas_10}')
        self.assertContains(resp, f'concepto=transferencia&moneda=MXN&{fechas_10}')
        self.assertContains(resp, f'concepto=reembolsos&moneda=MXN&{fechas_10}')
        self.assertContains(resp, f'concepto=todos&moneda=MXN&{fechas_10}')

        # Verificación para el dia 15
        fechas_15 = 'desde=2026-04-15&hasta=2026-04-15'
        self.assertContains(resp, f'concepto=tarjeta&moneda=MXN&{fechas_15}')
        self.assertContains(resp, f'concepto=todos&moneda=MXN&{fechas_15}')
        self.assertNotContains(resp, f'concepto=efectivo&moneda=MXN&{fechas_15}')
        self.assertNotContains(resp, f'concepto=transferencia&moneda=MXN&{fechas_15}')
        self.assertNotContains(resp, f'concepto=reembolsos&moneda=MXN&{fechas_15}')


class PuntaAPuntaMovimientosTotalCoincideTests(EmpresaTestCase):
    """Siguiendo el enlace de cada cifra del panel, el total en Movimientos coincide exactamente."""

    def setUp(self):
        super().setUp()
        self.url_panel = reverse('finanzas')
        self.client.force_login(self.crear_jefe())

        self.hoy = date.today()
        cuando_hoy = timezone.make_aware(datetime.combine(self.hoy, time(10, 0)))

        # Reservas en MXN
        crear_reserva(
            self.empresa,
            fecha=self.hoy + timedelta(days=10),
            monto_pagado=Decimal('3500.00'),
            pagada_en=cuando_hoy,
            monto_efectivo=Decimal('1200.00'),
            efectivo_cobrado_en=cuando_hoy,
            monto_transferencia=Decimal('1800.00'),
            transferencia_registrada_en=cuando_hoy,
        )
        crear_reserva(
            self.empresa,
            fecha=self.hoy + timedelta(days=11),
            monto_pagado=Decimal('600.00'),
            pagada_en=cuando_hoy,
            monto_reembolsado=Decimal('600.00'),
            reembolsada_en=cuando_hoy,
            estado=Reserva.Estado.CANCELADA,
            reembolsada=True,
        )

        # Reserva en USD
        crear_reserva(
            self.empresa,
            fecha=self.hoy + timedelta(days=12),
            moneda=Reserva.Moneda.USD,
            monto_pagado=Decimal('250.00'),
            pagada_en=cuando_hoy,
            monto_efectivo=Decimal('80.00'),
            efectivo_cobrado_en=cuando_hoy,
        )

    def _extraer_url_por_texto(self, contenido_html, texto):
        """Extrae el href del primer enlace cuyo texto visible sea exactamente el buscado."""
        patron = rf'<a\s+href="([^"]+)"[^>]*>\s*{re.escape(texto)}\s*</a>'
        match = re.search(patron, contenido_html)
        self.assertIsNotNone(match, f"No se encontró enlace con texto: {texto}")
        return html.unescape(match.group(1))

    def test_enlace_tarjeta_periodo_total_coincide(self):
        resp_panel = self.client.get(self.url_panel, {'periodo': 'hoy'})
        url_detalle = self._extraer_url_por_texto(resp_panel.content.decode(), '4,100.00')

        resp_movs = self.client.get(url_detalle)
        self.assertEqual(resp_movs.status_code, 200)
        self.assertEqual(resp_movs.context['totales']['MXN'], Decimal('4100.00'))

    def test_enlace_efectivo_periodo_total_coincide(self):
        resp_panel = self.client.get(self.url_panel, {'periodo': 'hoy'})
        url_detalle = self._extraer_url_por_texto(resp_panel.content.decode(), '1,200.00')

        resp_movs = self.client.get(url_detalle)
        self.assertEqual(resp_movs.status_code, 200)
        self.assertEqual(resp_movs.context['totales']['MXN'], Decimal('1200.00'))

    def test_enlace_transferencia_periodo_total_coincide(self):
        resp_panel = self.client.get(self.url_panel, {'periodo': 'hoy'})
        url_detalle = self._extraer_url_por_texto(resp_panel.content.decode(), '1,800.00')

        resp_movs = self.client.get(url_detalle)
        self.assertEqual(resp_movs.status_code, 200)
        self.assertEqual(resp_movs.context['totales']['MXN'], Decimal('1800.00'))

    def test_enlace_reembolsos_periodo_total_coincide(self):
        resp_panel = self.client.get(self.url_panel, {'periodo': 'hoy'})
        url_detalle = self._extraer_url_por_texto(resp_panel.content.decode(), '−600.00')

        resp_movs = self.client.get(url_detalle)
        self.assertEqual(resp_movs.status_code, 200)
        self.assertEqual(resp_movs.context['totales']['MXN'], Decimal('600.00'))

    def test_enlace_balance_neto_periodo_total_coincide(self):
        # 4100 tarjeta + 1200 efectivo + 1800 transf - 600 reembolsos = 6500
        resp_panel = self.client.get(self.url_panel, {'periodo': 'hoy'})
        url_detalle = self._extraer_url_por_texto(resp_panel.content.decode(), '6,500.00')

        resp_movs = self.client.get(url_detalle)
        self.assertEqual(resp_movs.status_code, 200)
        self.assertEqual(resp_movs.context['totales']['MXN'], Decimal('6500.00'))

    def test_enlace_tarjeta_acumulado_stripe_total_coincide(self):
        # En la cuenta: tarjeta (4100) - reembolsos (600) = 3500
        resp_panel = self.client.get(self.url_panel)
        url_detalle = self._extraer_url_por_texto(resp_panel.content.decode(), '3,500.00')

        resp_movs = self.client.get(url_detalle)
        self.assertEqual(resp_movs.status_code, 200)
        self.assertEqual(resp_movs.context['totales']['MXN'], Decimal('3500.00'))

    def test_enlace_tarjeta_acumulado_banco_total_coincide(self):
        # En el banco: transferencias registradas = 1800
        resp_panel = self.client.get(self.url_panel)
        url_detalle = self._extraer_url_por_texto(resp_panel.content.decode(), '1,800.00')

        resp_movs = self.client.get(url_detalle)
        self.assertEqual(resp_movs.status_code, 200)
        self.assertEqual(resp_movs.context['totales']['MXN'], Decimal('1800.00'))

    def test_enlace_usd_periodo_total_coincide(self):
        # Tarjeta USD: 250
        resp_panel = self.client.get(self.url_panel, {'periodo': 'hoy'})
        url_detalle = self._extraer_url_por_texto(resp_panel.content.decode(), '250.00')

        resp_movs = self.client.get(url_detalle)
        self.assertEqual(resp_movs.status_code, 200)
        self.assertEqual(resp_movs.context['totales']['USD'], Decimal('250.00'))
