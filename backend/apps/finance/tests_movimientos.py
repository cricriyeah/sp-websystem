"""Pruebas de la pantalla de Movimientos financieros y control de acceso.

Cubre:
- Totales de Movimientos contra balances() para todos los conceptos y monedas.
- Filtros por fechas, moneda y concepto; desglose de múltiples movimientos por reserva.
- Resiliencia ante parámetros inválidos.
- Independencia del total respecto a la página en paginación.
- Restricción de acceso: jefe 200, vendedora con membresía 403, operador 200,
  aislamiento estricto por empresa.
- Ocultamiento de Finanzas en el menú lateral Unfold para vendedoras.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.finance.services import balances, movimientos, totales_de_movimientos
from apps.tenancy.permisos_unfold import puede_ver_finanzas
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
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
        'nombre_cliente': 'Beatriz Soto',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'beatriz@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Beatriz Soto',
        'estado': Reserva.Estado.PAGADA,
    }
    if 'servicio' not in overrides and 'paquete' not in overrides:
        datos['servicio'] = crear_servicio_pesca(empresa_real)
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva


class MovimientosTotalesCoincidenConBalancesTests(EmpresaTestCase):
    """El total de Movimientos debe coincidir exactamente con balances()."""

    def setUp(self):
        super().setUp()
        # Sembrado en MXN
        crear_reserva(
            self.empresa,
            monto_pagado=Decimal('5000.00'),
            pagada_en=momento(2026, 10, 5, 10),
        )
        crear_reserva(
            self.empresa,
            monto_efectivo=Decimal('1500.00'),
            efectivo_cobrado_en=momento(2026, 10, 6, 11),
        )
        crear_reserva(
            self.empresa,
            monto_transferencia=Decimal('2000.00'),
            transferencia_registrada_en=momento(2026, 10, 7, 12),
        )
        crear_reserva(
            self.empresa,
            monto_pagado=Decimal('1200.00'),
            pagada_en=momento(2026, 10, 1, 9),
            monto_reembolsado=Decimal('1200.00'),
            reembolsada_en=momento(2026, 10, 8, 14),
            estado=Reserva.Estado.CANCELADA,
            reembolsada=True,
        )
        # Sembrado en USD
        crear_reserva(
            self.empresa,
            moneda=Reserva.Moneda.USD,
            monto_pagado=Decimal('300.00'),
            pagada_en=momento(2026, 10, 5, 10),
        )
        crear_reserva(
            self.empresa,
            moneda=Reserva.Moneda.USD,
            monto_efectivo=Decimal('100.00'),
            efectivo_cobrado_en=momento(2026, 10, 6, 11),
        )
        crear_reserva(
            self.empresa,
            moneda=Reserva.Moneda.USD,
            monto_transferencia=Decimal('150.00'),
            transferencia_registrada_en=momento(2026, 10, 7, 12),
        )
        crear_reserva(
            self.empresa,
            moneda=Reserva.Moneda.USD,
            monto_pagado=Decimal('80.00'),
            pagada_en=momento(2026, 10, 1, 9),
            monto_reembolsado=Decimal('80.00'),
            reembolsada_en=momento(2026, 10, 8, 14),
            estado=Reserva.Estado.CANCELADA,
            reembolsada=True,
        )

    def test_totales_sin_fechas_coinciden_con_balances_dos_monedas(self):
        b = balances(empresa=self.empresa)

        # Tarjeta
        tot_tarjeta = totales_de_movimientos(movimientos(concepto='tarjeta', empresa=self.empresa), concepto='tarjeta')
        self.assertEqual(tot_tarjeta['MXN'], b['MXN'].tarjeta)
        self.assertEqual(tot_tarjeta['USD'], b['USD'].tarjeta)

        # Efectivo
        tot_efectivo = totales_de_movimientos(movimientos(concepto='efectivo', empresa=self.empresa), concepto='efectivo')
        self.assertEqual(tot_efectivo['MXN'], b['MXN'].efectivo)
        self.assertEqual(tot_efectivo['USD'], b['USD'].efectivo)

        # Transferencia
        tot_transf = totales_de_movimientos(movimientos(concepto='transferencia', empresa=self.empresa), concepto='transferencia')
        self.assertEqual(tot_transf['MXN'], b['MXN'].transferencia)
        self.assertEqual(tot_transf['USD'], b['USD'].transferencia)

        # Reembolsos
        tot_reembolsos = totales_de_movimientos(movimientos(concepto='reembolsos', empresa=self.empresa), concepto='reembolsos')
        self.assertEqual(tot_reembolsos['MXN'], b['MXN'].reembolsos)
        self.assertEqual(tot_reembolsos['USD'], b['USD'].reembolsos)

        # Stripe («En la cuenta» = tarjeta − reembolsos)
        tot_stripe = totales_de_movimientos(movimientos(concepto='stripe', empresa=self.empresa), concepto='stripe')
        self.assertEqual(tot_stripe['MXN'], b['MXN'].en_cuenta)
        self.assertEqual(tot_stripe['USD'], b['USD'].en_cuenta)

        # Todos (neto = entradas − reembolsos)
        tot_todos = totales_de_movimientos(movimientos(concepto='todos', empresa=self.empresa), concepto='todos')
        self.assertEqual(tot_todos['MXN'], b['MXN'].neto)
        self.assertEqual(tot_todos['USD'], b['USD'].neto)

    def test_totales_con_fechas_acotadas_coinciden_con_balances(self):
        desde = date(2026, 10, 5)
        hasta = date(2026, 10, 7)
        b = balances(desde, hasta, empresa=self.empresa)

        for concepto, atributo in [
            ('tarjeta', 'tarjeta'),
            ('efectivo', 'efectivo'),
            ('transferencia', 'transferencia'),
            ('reembolsos', 'reembolsos'),
            ('stripe', 'en_cuenta'),
            ('todos', 'neto'),
        ]:
            with self.subTest(concepto=concepto):
                tot = totales_de_movimientos(
                    movimientos(desde, hasta, concepto=concepto, empresa=self.empresa), concepto=concepto)
                self.assertEqual(tot.get('MXN', Decimal('0.00')), getattr(b.get('MXN'), atributo, Decimal('0.00')))
                self.assertEqual(tot.get('USD', Decimal('0.00')), getattr(b.get('USD'), atributo, Decimal('0.00')))


class MovimientosFiltrosTests(EmpresaTestCase):
    """Filtros de servicio por fechas, concepto y moneda."""

    def test_reserva_con_tarjeta_y_reembolso_aparece_en_dos_filas(self):
        reserva = crear_reserva(
            self.empresa,
            monto_pagado=Decimal('3000.00'),
            pagada_en=momento(2026, 10, 2, 9),
            monto_reembolsado=Decimal('1000.00'),
            reembolsada_en=momento(2026, 10, 5, 12),
            estado=Reserva.Estado.CANCELADA,
            reembolsada=True,
        )

        filas = movimientos(concepto='todos', empresa=self.empresa)
        self.assertEqual(len(filas), 2)
        pks = [f.reserva.pk for f in filas]
        self.assertEqual(pks, [reserva.pk, reserva.pk])

        # Más reciente primero: el reembolso (5 oct) va antes que el cobro (2 oct)
        self.assertEqual(filas[0].concepto, 'reembolsos')
        self.assertEqual(filas[0].monto, Decimal('1000.00'))
        self.assertEqual(filas[0].fecha, momento(2026, 10, 5, 12))

        self.assertEqual(filas[1].concepto, 'tarjeta')
        self.assertEqual(filas[1].monto, Decimal('3000.00'))
        self.assertEqual(filas[1].fecha, momento(2026, 10, 2, 9))

    def test_filtro_por_fechas_limites_inclusivos(self):
        crear_reserva(
            self.empresa,
            monto_pagado=Decimal('1000.00'),
            pagada_en=momento(2026, 10, 2, 10),
            monto_reembolsado=Decimal('500.00'),
            reembolsada_en=momento(2026, 10, 5, 15),
            estado=Reserva.Estado.CANCELADA,
            reembolsada=True,
        )

        # Límite inferior exacto
        dia_2 = movimientos(desde=date(2026, 10, 2), hasta=date(2026, 10, 2), empresa=self.empresa)
        self.assertEqual(len(dia_2), 1)
        self.assertEqual(dia_2[0].concepto, 'tarjeta')

        # Límite superior exacto
        dia_5 = movimientos(desde=date(2026, 10, 5), hasta=date(2026, 10, 5), empresa=self.empresa)
        self.assertEqual(len(dia_5), 1)
        self.assertEqual(dia_5[0].concepto, 'reembolsos')

        # Rango intermedio vacío
        vacio = movimientos(desde=date(2026, 10, 3), hasta=date(2026, 10, 4), empresa=self.empresa)
        self.assertEqual(len(vacio), 0)

    def test_filtro_por_moneda_y_por_concepto(self):
        crear_reserva(
            self.empresa,
            moneda=Reserva.Moneda.MXN,
            monto_pagado=Decimal('1000.00'),
            pagada_en=momento(2026, 10, 1),
        )
        crear_reserva(
            self.empresa,
            moneda=Reserva.Moneda.USD,
            monto_pagado=Decimal('100.00'),
            pagada_en=momento(2026, 10, 1),
        )
        crear_reserva(
            self.empresa,
            moneda=Reserva.Moneda.MXN,
            monto_efectivo=Decimal('500.00'),
            efectivo_cobrado_en=momento(2026, 10, 1),
        )

        solo_mxn = movimientos(moneda='MXN', empresa=self.empresa)
        self.assertEqual(len(solo_mxn), 2)
        self.assertTrue(all(f.moneda == 'MXN' for f in solo_mxn))

        solo_usd = movimientos(moneda='USD', empresa=self.empresa)
        self.assertEqual(len(solo_usd), 1)
        self.assertEqual(solo_usd[0].moneda, 'USD')

        solo_efectivo = movimientos(concepto='efectivo', empresa=self.empresa)
        self.assertEqual(len(solo_efectivo), 1)
        self.assertEqual(solo_efectivo[0].concepto, 'efectivo')


class MovimientosParametrosInvalidosTests(EmpresaTestCase):
    """Parámetros GET inválidos no deben causar HTTP 500."""

    def setUp(self):
        super().setUp()
        self.url = reverse('finanzas_movimientos')
        self.client.force_login(self.crear_jefe())

    def test_fechas_concepto_moneda_y_pagina_invalidas_responden_200(self):
        respuestas = [
            self.client.get(self.url, {'desde': 'invalido', 'hasta': '2026-99-99'}),
            self.client.get(self.url, {'concepto': 'inventado'}),
            self.client.get(self.url, {'moneda': 'EUR'}),
            self.client.get(self.url, {'pagina': 'abc'}),
            self.client.get(self.url, {'pagina': '-5'}),
            self.client.get(self.url, {'pagina': '99999'}),
        ]
        for resp in respuestas:
            self.assertEqual(resp.status_code, 200)


class MovimientosPaginacionTests(EmpresaTestCase):
    """La paginación no altera el total reportado al pie."""

    def setUp(self):
        super().setUp()
        self.url = reverse('finanzas_movimientos')
        self.client.force_login(self.crear_jefe())
        nombres = [
            'Ana', 'Beatriz', 'Carlos', 'David', 'Elena', 'Fernando', 'Gabriela', 'Hector',
            'Ines', 'Jorge', 'Karla', 'Luis', 'Manuel', 'Natalia', 'Oscar', 'Patricia',
            'Rosa', 'Sergio', 'Teresa', 'Valeria',
        ]
        apellidos = ['Ruiz', 'Soto', 'Mendoza', 'Lopez']
        for i in range(55):
            nom = f"{nombres[i % len(nombres)]} {apellidos[(i // len(nombres)) % len(apellidos)]}"
            crear_reserva(
                self.empresa,
                fecha=date.today() + timedelta(days=10 + i),  # un dia cada una: el cupo diario es por dia
                nombre_cliente=nom,
                deslinde_nombre=nom,
                monto_pagado=Decimal('100.00'),
                pagada_en=momento(2026, 10, 1) + timedelta(minutes=i),
            )

    def test_el_total_no_depende_de_la_pagina(self):
        pag1 = self.client.get(self.url, {'pagina': '1'})
        pag2 = self.client.get(self.url, {'pagina': '2'})

        self.assertEqual(len(pag1.context['filas']), 50)
        self.assertEqual(len(pag2.context['filas']), 5)

        total_esperado = Decimal('5500.00')
        self.assertEqual(pag1.context['totales']['MXN'], total_esperado)
        self.assertEqual(pag2.context['totales']['MXN'], total_esperado)
        self.assertEqual(pag1.context['totales'], pag2.context['totales'])


class MovimientosAccesoTests(EmpresaTestCase):
    """Control de acceso estricto y aislamiento por empresa."""

    def setUp(self):
        super().setUp()
        self.url_movimientos = reverse('finanzas_movimientos')
        self.url_panel = reverse('finanzas')

    def test_jefe_obtiene_200_en_panel_y_movimientos(self):
        self.client.force_login(self.crear_jefe())
        self.assertEqual(self.client.get(self.url_movimientos).status_code, 200)
        self.assertEqual(self.client.get(self.url_panel).status_code, 200)

    def test_vendedora_con_membresia_recibe_403(self):
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)
        self.assertEqual(self.client.get(self.url_movimientos).status_code, 403)
        self.assertEqual(self.client.get(self.url_panel).status_code, 403)

    def test_usuario_sin_membresia_recibe_403(self):
        usuario = User.objects.create_user('usuario_sin_empresa', password='x', is_staff=True)
        self.client.force_login(usuario)
        self._alcance.__exit__(None, None, None)
        try:
            self.assertEqual(self.client.get(self.url_movimientos).status_code, 403)
            self.assertEqual(self.client.get(self.url_panel).status_code, 403)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

    def test_operador_de_plataforma_ve_varias_empresas(self):
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'), pagada_en=momento(2026, 10, 1))

        otra_sede = Sede.objects.create(nombre='Otra Sede', slug='otra-sede-movs')
        otra_empresa = Empresa.objects.create(sede=otra_sede, nombre='Otra Empresa', slug='otra-empresa-movs')

        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                crear_reserva(otra_empresa, monto_pagado=Decimal('2000.00'), pagada_en=momento(2026, 10, 2))

            operador = User.objects.create_user('operador_global', password='x', is_staff=True)
            operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
            self.client.force_login(operador)

            resp_mov = self.client.get(self.url_movimientos)
            self.assertEqual(resp_mov.status_code, 200)
            self.assertEqual(resp_mov.context['totales']['MXN'], Decimal('3000.00'))

            resp_pan = self.client.get(self.url_panel)
            self.assertEqual(resp_pan.status_code, 200)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

    def test_aislamiento_por_empresa_para_jefe(self):
        crear_reserva(self.empresa, monto_pagado=Decimal('1000.00'), pagada_en=momento(2026, 10, 1))

        otra_sede = Sede.objects.create(nombre='Sede Aislada', slug='sede-aislada')
        otra_empresa = Empresa.objects.create(sede=otra_sede, nombre='Empresa Aislada', slug='empresa-aislada')

        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                crear_reserva(otra_empresa, monto_pagado=Decimal('9999.00'), pagada_en=momento(2026, 10, 2))

            self.client.force_login(self.crear_jefe())
            resp_mov = self.client.get(self.url_movimientos)
            self.assertEqual(resp_mov.status_code, 200)
            self.assertContains(resp_mov, '1,000.00')
            self.assertNotContains(resp_mov, '9,999.00')

            resp_pan = self.client.get(self.url_panel)
            self.assertContains(resp_pan, '1,000.00')
            self.assertNotContains(resp_pan, '9,999.00')
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()


class MenuSidebarTests(EmpresaTestCase):
    """El acceso lateral en Unfold oculta Finanzas a vendedoras."""

    def test_elemento_finanzas_se_oculta_a_vendedora(self):
        vendedora = self.crear_vendedora()
        rf = RequestFactory()
        req = rf.get('/admin/')
        req.user = vendedora
        self.assertFalse(puede_ver_finanzas(req))

        self.client.force_login(vendedora)
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse('finanzas'))
        self.assertNotContains(resp, reverse('finanzas_movimientos'))

    def test_elemento_finanzas_se_muestra_a_jefe(self):
        jefe = self.crear_jefe()
        rf = RequestFactory()
        req = rf.get('/admin/')
        req.user = jefe
        self.assertTrue(puede_ver_finanzas(req))

        self.client.force_login(jefe)
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('finanzas'))


class PlantillaMovimientosDetalleTests(EmpresaTestCase):
    """Detalle visual: enlaces a reservas, reembolsos en rojo y enlaces de Stripe."""

    def setUp(self):
        super().setUp()
        self.url = reverse('finanzas_movimientos')
        self.client.force_login(self.crear_jefe())

    def test_enlace_a_reserva_y_formato_de_reembolso(self):
        reserva = crear_reserva(
            self.empresa,
            monto_pagado=Decimal('2000.00'),
            pagada_en=momento(2026, 10, 1),
            monto_reembolsado=Decimal('500.00'),
            reembolsada_en=momento(2026, 10, 2),
            stripe_payment_intent_id='pi_test_12345',
            estado=Reserva.Estado.CANCELADA,
            reembolsada=True,
        )

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        # Enlace al admin de la reserva
        url_reserva = reverse('admin:bookings_reserva_change', args=[reserva.pk])
        self.assertContains(resp, f'href="{url_reserva}"')
        self.assertContains(resp, f'#{reserva.pk}')
        # Reembolso con signo menos y clase de color rojo
        self.assertContains(resp, 'text-red-600')
        self.assertContains(resp, '−500.00')
        # Enlace a Stripe para tarjeta y reembolsos
        self.assertContains(resp, 'pi_test_12345')
        self.assertContains(resp, 'Ver pago')

    def test_sin_movimientos_muestra_mensaje_vacio(self):
        resp = self.client.get(self.url, {'concepto': 'transferencia'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Sin movimientos en este filtro.')
