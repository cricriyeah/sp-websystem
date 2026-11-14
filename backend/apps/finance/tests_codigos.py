"""Cuanto se uso cada codigo promocional y cuanto dinero se fue en descuento.

Lo que se protege aqui: que el uso salga de las reservas que de verdad lo aplicaron (las mismas
que cuentan contra `usos_maximos`), que cada moneda vaya por separado, que el periodo corte por
la fecha en que se vendio y que cada empresa vea solo lo suyo.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.fleet.models import CodigoPromocional
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import EmpresaTestCase

from .services import uso_de_codigos
from .tests import crear_reserva, momento


class _ConVentas(EmpresaTestCase):
    """Atajos: un codigo y una venta que lo aplico."""

    def codigo(self, texto='VERANO', empresa=None):
        return CodigoPromocional.objects.create(
            empresa=empresa or self.empresa, codigo=texto, porcentaje_descuento=Decimal('10'),
        )

    def venta(self, promo, descuento, total, empresa=None, **extra):
        # Cada venta en su dia de viaje: asi ninguna le quita el cupo a otra.
        self._dia = getattr(self, '_dia', 9) + 1
        datos = {
            'codigo_promocional': promo,
            'descuento_aplicado': Decimal(descuento),
            'precio_total': Decimal(total),
            'monto_pagado': Decimal(total),
            'pagada_en': momento(2026, 3, 5),
            'fecha': date.today() + timedelta(days=self._dia),
        }
        datos.update(extra)
        return crear_reserva(empresa or self.empresa, **datos)


class UsoDeCodigosTests(_ConVentas):
    def test_suma_usos_descuento_y_venta_de_cada_codigo(self):
        verano = self.codigo('VERANO')
        amigos = self.codigo('AMIGOS')
        self.venta(verano, '500.00', '5220.00')
        self.venta(verano, '700.00', '7308.00')
        self.venta(amigos, '100.00', '1044.00')

        filas = {fila.codigo.codigo: fila for fila in uso_de_codigos(empresa=self.empresa)}

        self.assertEqual(filas['VERANO'].usos, 2)
        self.assertEqual(filas['VERANO'].descontado, Decimal('1200.00'))
        self.assertEqual(filas['VERANO'].vendido, Decimal('12528.00'))
        self.assertEqual(filas['VERANO'].moneda, 'MXN')
        self.assertEqual(filas['AMIGOS'].usos, 1)
        self.assertEqual(filas['AMIGOS'].descontado, Decimal('100.00'))

    def test_el_mas_usado_va_primero(self):
        poco = self.codigo('POCO')
        mucho = self.codigo('MUCHO')
        self.venta(poco, '10.00', '100.00')
        self.venta(mucho, '10.00', '100.00')
        self.venta(mucho, '10.00', '100.00')

        self.assertEqual(
            [fila.codigo.codigo for fila in uso_de_codigos(empresa=self.empresa)], ['MUCHO', 'POCO'],
        )

    def test_cada_moneda_va_en_su_renglon_y_no_se_suman(self):
        promo = self.codigo()
        self.venta(promo, '500.00', '5220.00')
        self.venta(promo, '30.00', '313.00', moneda=Reserva.Moneda.USD)

        filas = {fila.moneda: fila for fila in uso_de_codigos(empresa=self.empresa)}

        self.assertEqual(filas['MXN'].descontado, Decimal('500.00'))
        self.assertEqual(filas['MXN'].usos, 1)
        self.assertEqual(filas['USD'].descontado, Decimal('30.00'))
        self.assertEqual(filas['USD'].vendido, Decimal('313.00'))

    def test_solo_cuentan_las_reservas_que_ocupan_cupo(self):
        """Mismo criterio que `usos_maximos`: una pendiente no llego a comprar y una cancelada
        se devolvio, asi que ahi no se fue ningun descuento."""
        promo = self.codigo()
        self.venta(promo, '500.00', '5220.00')
        self.venta(promo, '900.00', '9000.00', estado=Reserva.Estado.PENDIENTE_PAGO,
                   monto_pagado=None, pagada_en=None)
        cancelada = self.venta(promo, '800.00', '8000.00')
        Reserva.objects.filter(pk=cancelada.pk).update(estado=Reserva.Estado.CANCELADA)

        (fila,) = uso_de_codigos(empresa=self.empresa)

        self.assertEqual(fila.usos, 1)
        self.assertEqual(fila.descontado, Decimal('500.00'))

    def test_una_reserva_sin_codigo_no_aparece(self):
        crear_reserva(self.empresa, monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5))

        self.assertEqual(uso_de_codigos(empresa=self.empresa), [])

    def test_el_periodo_corta_por_la_fecha_en_que_se_vendio(self):
        promo = self.codigo()
        self.venta(promo, '500.00', '5220.00', pagada_en=momento(2026, 3, 5))
        self.venta(promo, '700.00', '7308.00', pagada_en=momento(2026, 4, 2))

        (marzo,) = uso_de_codigos(date(2026, 3, 1), date(2026, 3, 31), empresa=self.empresa)
        (todo,) = uso_de_codigos(empresa=self.empresa)

        self.assertEqual(marzo.usos, 1)
        self.assertEqual(marzo.descontado, Decimal('500.00'))
        self.assertEqual(todo.descontado, Decimal('1200.00'))
        self.assertEqual(uso_de_codigos(date(2026, 5, 1), date(2026, 5, 31), empresa=self.empresa), [])

    def test_una_venta_por_transferencia_cuenta_en_el_dia_de_la_transferencia(self):
        """Un checkout abandonado que se salda por transferencia conserva su codigo y no tiene `pagada_en`."""
        promo = self.codigo()
        self.venta(promo, '500.00', '5220.00', monto_pagado=None, pagada_en=None,
                   monto_transferencia=Decimal('5220.00'),
                   transferencia_registrada_en=momento(2026, 3, 20))

        (fila,) = uso_de_codigos(date(2026, 3, 20), date(2026, 3, 20), empresa=self.empresa)

        self.assertEqual(fila.descontado, Decimal('500.00'))

    def test_cada_empresa_ve_solo_sus_codigos_y_sin_empresa_salen_todos(self):
        self.venta(self.codigo('MIO'), '500.00', '5220.00')
        otra_sede = Sede.objects.create(nombre='Sede codigos', slug='sede-uso-codigos')
        otra = Empresa.objects.create(sede=otra_sede, nombre='Otra de codigos', slug='otra-uso-codigos')
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra):
                self.venta(self.codigo('AJENO', empresa=otra), '900.00', '9000.00', empresa=otra)
            with scope.con_empresa(self.empresa):
                propios = [fila.codigo.codigo for fila in uso_de_codigos(empresa=self.empresa)]
            with scope.como_operador_plataforma():
                todos = sorted(fila.codigo.codigo for fila in uso_de_codigos())
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        self.assertEqual(propios, ['MIO'])
        self.assertEqual(todos, ['AJENO', 'MIO'])


class CodigosEnElPanelTests(_ConVentas):
    def setUp(self):
        self.url = reverse('finanzas')

    def test_el_panel_muestra_el_uso_del_periodo(self):
        self.venta(self.codigo('VERANO'), '512.34', '5220.00', pagada_en=timezone.now())
        self.client.force_login(self.crear_jefe())

        respuesta = self.client.get(self.url)

        (fila,) = respuesta.context['codigos']
        self.assertEqual(fila.descontado, Decimal('512.34'))
        self.assertContains(respuesta, 'Códigos promocionales')
        self.assertContains(respuesta, 'VERANO')
        self.assertContains(respuesta, '512.34')
        self.assertContains(respuesta, '5,220.00')

    def test_el_codigo_enlaza_a_sus_reservas(self):
        promo = self.codigo('VERANO')
        self.venta(promo, '500.00', '5220.00', pagada_en=timezone.now())
        self.client.force_login(self.crear_jefe())

        respuesta = self.client.get(self.url)
        enlace = respuesta.context['codigos'][0].enlace

        self.assertIn(f'codigo_promocional__id__exact={promo.pk}', enlace)
        self.assertContains(respuesta, enlace.replace('&', '&amp;'))
        self.assertEqual(self.client.get(enlace).status_code, 200)

    def test_sin_usos_en_el_periodo_lo_dice(self):
        self.venta(self.codigo('VERANO'), '500.00', '5220.00', pagada_en=momento(2020, 1, 5))
        self.client.force_login(self.crear_jefe())

        respuesta = self.client.get(self.url, {'periodo': 'hoy'})

        self.assertEqual(respuesta.context['codigos'], [])
        self.assertContains(respuesta, 'Ningún código usado en este periodo.')

    def test_el_operador_ve_de_que_empresa_es_cada_codigo(self):
        self.venta(self.codigo('VERANO'), '500.00', '5220.00', pagada_en=timezone.now())
        operador = User.objects.create_user('operador-codigos', password='x', is_staff=True)
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        self.client.force_login(operador)

        # El operador entra con su propio alcance: hay que soltar el de la empresa de la prueba.
        self._alcance.__exit__(None, None, None)
        try:
            respuesta = self.client.get(self.url)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        self.assertContains(respuesta, 'VERANO')
        self.assertContains(respuesta, '<th class="font-medium px-3 py-2 text-left">Empresa</th>', html=True)
        self.assertContains(respuesta, self.empresa.nombre)
