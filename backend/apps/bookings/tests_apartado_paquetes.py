"""Pruebas para el retrato del apartado temporal de cupo en paquetes de una sola empresa."""

from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from apps.bookings.cupo import (
    construir_retrato_paquete,
    demanda_apartada_del_dia,
    demanda_apartada_por_rango,
    obtener_contexto_cupo,
    obtener_contexto_rango,
)
from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar
from apps.bookings.cupo.salidas import salidas_deseadas
from apps.bookings.models import Reserva, evaluar_cupo
from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.testing import EmpresaTestCase, crear_flota


@override_settings(APARTADO_MINUTOS=15)
class ApartadoPaquetesTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.inicio = date.today() + timedelta(days=10)

        # Servicios de prueba bajo la empresa del caso
        self.pesca_mar = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Pesca Mayor',
            slug='pesca-mayor',
            tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia',
            precio_base=Decimal('4000.00'),
        )
        self.paseo_mar = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Paseo Bahía',
            slug='paseo-bahia',
            tipo_servicio='paseo',
            estrategia_cupo='por_recurso_dia',
            precio_base=Decimal('2000.00'),
        )
        self.hotel = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Cabaña Vista',
            slug='cabana-vista',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            estrategia_precio='por_noche',
            precio_base=Decimal('3000.00'),
        )
        self.transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Transporte Terrestre',
            slug='transporte-terrestre',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            precio_base=Decimal('1500.00'),
        )

        # Paquete multidía con 3 salidas de pesca consecutivas a partir del día 2 de estancia
        self.paquete_multidia = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Mar Multidía',
            slug='paquete-mar-multidia',
            precio_ancla=Decimal('9000.00'),
        )
        self.ps_pesca_multidia = PaqueteServicio.objects.create(
            paquete=self.paquete_multidia,
            servicio=self.pesca_mar,
            orden=1,
            dia_estancia=2,
            salidas=3,
            personas_incluidas=3,
        )

    def _crear_reserva_paquete(self, paquete, **extra):
        inicio = extra.pop('inicio', self.inicio)
        datos = dict(
            empresa=self.empresa,
            paquete=paquete,
            fecha=inicio + timedelta(days=1),
            inicio_paquete=inicio,
            fecha_salida=inicio + timedelta(days=5),
            hora=time(6, 0),
            numero_personas=3,
            nombre_cliente='Ana Lopez',
            telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com',
            canal_origen='web',
            deslinde_aceptado=True,
            deslinde_nombre='Ana Lopez',
            moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        datos.update(extra)
        return Reserva.objects.create(**datos)

    def test_paquete_con_salidas_multidia_genera_retrato_y_cuenta_en_cada_fecha(self):
        """Un paquete con salidas multidía genera una entrada por fecha en el retrato y cuenta en cada una."""
        reserva = self._crear_reserva_paquete(self.paquete_multidia, numero_personas=3)

        retrato = construir_retrato_paquete(reserva)
        self.assertEqual(retrato['v'], 1)
        self.assertEqual(retrato['habitaciones'], [])

        dia2 = self.inicio + timedelta(days=1)
        dia3 = self.inicio + timedelta(days=2)
        dia4 = self.inicio + timedelta(days=3)
        fechas_esperadas = [dia2.isoformat(), dia3.isoformat(), dia4.isoformat()]

        self.assertEqual([s['fecha'] for s in retrato['salidas']], fechas_esperadas)
        self.assertTrue(all(s['personas'] == 3 for s in retrato['salidas']))
        self.assertTrue(all(s['servicio_id'] == self.pesca_mar.pk for s in retrato['salidas']))

        # Guardar el apartado en la reserva
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = retrato
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        # El motor cuenta las 3 personas en cada día de mar
        self.assertEqual(obtener_contexto_cupo(dia2, self.empresa).grupos, [3])
        self.assertEqual(obtener_contexto_cupo(dia3, self.empresa).grupos, [3])
        self.assertEqual(obtener_contexto_cupo(dia4, self.empresa).grupos, [3])

        # Días sin actividad de mar no tienen apartado
        dia1 = self.inicio
        dia5 = self.inicio + timedelta(days=4)
        self.assertEqual(obtener_contexto_cupo(dia1, self.empresa).grupos, [])
        self.assertEqual(obtener_contexto_cupo(dia5, self.empresa).grupos, [])

        # Contexto de rango agrega las demandas de cada fecha
        ctx_rango = obtener_contexto_rango(dia1, dia5, self.empresa)
        self.assertEqual(ctx_rango.grupos_por_fecha.get(dia2, []), [3])
        self.assertEqual(ctx_rango.grupos_por_fecha.get(dia3, []), [3])
        self.assertEqual(ctx_rango.grupos_por_fecha.get(dia4, []), [3])
        self.assertNotIn(dia1, ctx_rango.grupos_por_fecha)

        # Excluir la propia reserva retira la demanda apartada
        self.assertEqual(obtener_contexto_cupo(dia2, self.empresa, excluir_pk=reserva.pk).grupos, [])

    def test_paquete_mezcla_componentes_coincide_con_reservar_cupo_al_confirmar(self):
        """Un paquete que mezcla componentes de varias salidas y de una salida coincide con reservar_cupo_al_confirmar."""
        paquete_mixto = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Mixto Pesca y Paseo',
            slug='paquete-mixto',
            precio_ancla=Decimal('7000.00'),
        )
        # Componente 1: pesca multidía (2 salidas, día de estancia 2 y 3)
        PaqueteServicio.objects.create(
            paquete=paquete_mixto,
            servicio=self.pesca_mar,
            orden=1,
            dia_estancia=2,
            salidas=2,
            personas_incluidas=3,
        )
        # Componente 2: paseo de una sola salida (salidas=1, día de estancia 1)
        PaqueteServicio.objects.create(
            paquete=paquete_mixto,
            servicio=self.paseo_mar,
            orden=2,
            dia_estancia=1,
            salidas=1,
            personas_incluidas=2,
        )

        reserva = self._crear_reserva_paquete(
            paquete_mixto,
            fecha=self.inicio,  # Componente de una sola salida valida contra Reserva.fecha
            inicio_paquete=self.inicio,
            numero_personas=3,
            personas_por_servicio={
                str(self.pesca_mar.pk): 3,
                str(self.paseo_mar.pk): 2,
            },
        )

        retrato = construir_retrato_paquete(reserva)

        # Capturar las llamadas a evaluar_cupo que hace reservar_cupo_al_confirmar
        llamadas_confirmacion = []

        def spy_evaluar_cupo(fecha, personas, empresa, **kwargs):
            llamadas_confirmacion.append((fecha, personas, kwargs.get('servicio_id')))
            return evaluar_cupo(fecha, personas, empresa, **kwargs)

        with mock.patch('apps.bookings.cupo.confirmacion.evaluar_cupo', side_effect=spy_evaluar_cupo):
            reservar_cupo_al_confirmar(reserva)

        # Las entradas de salidas del retrato deben coincidir exactamente con las evaluadas
        entradas_retrato = [
            (date.fromisoformat(s['fecha']), s['personas'], s['servicio_id'])
            for s in retrato['salidas']
        ]
        self.assertEqual(entradas_retrato, llamadas_confirmacion)

    def test_paquete_sin_mar_no_cuenta(self):
        """Un paquete sin componentes de mar devuelve salidas: [] y no cuenta en el motor."""
        paquete_solo_transporte = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Solo Transporte',
            slug='paquete-solo-transporte',
            precio_ancla=Decimal('5000.00'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete_solo_transporte,
            servicio=self.transporte,
            orden=1,
            personas_incluidas=2,
        )

        reserva = self._crear_reserva_paquete(paquete_solo_transporte)
        retrato = construir_retrato_paquete(reserva)

        self.assertEqual(retrato['salidas'], [])
        self.assertEqual(retrato['habitaciones'], [])

        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = retrato
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        self.assertEqual(demanda_apartada_del_dia(self.empresa, reserva.fecha), [])
        self.assertEqual(obtener_contexto_cupo(reserva.fecha, self.empresa).grupos, [])

    @override_settings(APARTADO_MINUTOS=0)
    def test_con_apartado_minutos_cero_no_cuenta(self):
        """Con APARTADO_MINUTOS=0 el motor ignora cualquier apartado existente."""
        reserva = self._crear_reserva_paquete(self.paquete_multidia)
        retrato = construir_retrato_paquete(reserva)

        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = retrato
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        dia2 = self.inicio + timedelta(days=1)
        self.assertEqual(obtener_contexto_cupo(dia2, self.empresa).grupos, [])
        self.assertEqual(
            obtener_contexto_rango(self.inicio, self.inicio + timedelta(days=5), self.empresa).grupos_por_fecha,
            {},
        )

    def test_sobre_apartado_un_dia_de_mas_fijado_por_lista_de_confirmacion(self):
        """El sobre-apartado de un día de más está fijado por la prueba: manda la lista de confirmación.

        Para un paquete que mezcla multidía y un componente de una sola salida:
        - reservar_cupo_al_confirmar valida tanto los días multidía como Reserva.fecha.
        - salidas_deseadas (que creará ReservaSalida al pagarse) solo incluye salidas > 1.
        - El retrato refleja la lista de validación de reservar_cupo_al_confirmar (incluyendo Reserva.fecha),
          apartando ese día de más de forma segura mientras está pendiente.
        """
        paquete_mixto = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Pesca Multidía y Paseo Sencillo',
            slug='paquete-sobre-apartado',
            precio_ancla=Decimal('7500.00'),
        )
        # Pesca de 2 salidas en días 2 y 3 de estancia
        PaqueteServicio.objects.create(
            paquete=paquete_mixto,
            servicio=self.pesca_mar,
            orden=1,
            dia_estancia=2,
            salidas=2,
            personas_incluidas=3,
        )
        # Paseo de 1 salida: validará contra Reserva.fecha (fijada al día 1 de estancia)
        PaqueteServicio.objects.create(
            paquete=paquete_mixto,
            servicio=self.paseo_mar,
            orden=2,
            dia_estancia=1,
            salidas=1,
            personas_incluidas=2,
        )

        dia1 = self.inicio
        reserva = self._crear_reserva_paquete(
            paquete_mixto,
            fecha=dia1,
            inicio_paquete=dia1,
            numero_personas=3,
        )

        retrato = construir_retrato_paquete(reserva)
        fechas_en_retrato = {date.fromisoformat(s['fecha']) for s in retrato['salidas']}
        fechas_en_salidas_deseadas = {dia for _, dia in salidas_deseadas(reserva)}

        # El día 1 (salida única) está en el retrato pero NO en salidas_deseadas
        self.assertIn(dia1, fechas_en_retrato)
        self.assertNotIn(dia1, fechas_en_salidas_deseadas)
        self.assertEqual(len(fechas_en_retrato), len(fechas_en_salidas_deseadas) + 1)

        # Al registrar el apartado, el motor cuenta la demanda en el día 1 (manda la lista del retrato)
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = retrato
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        self.assertEqual(obtener_contexto_cupo(dia1, self.empresa).grupos, [3])

    def test_reserva_con_apartado_no_se_cuenta_dos_veces_al_pasar_a_pagada(self):
        """Una reserva con apartado es la única fuente mientras está pendiente y no se duplica al pagarse."""
        reserva = self._crear_reserva_paquete(self.paquete_multidia, numero_personas=2)
        retrato = construir_retrato_paquete(reserva)

        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = retrato
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        dia2 = self.inicio + timedelta(days=1)
        # Mientras está pendiente, no tiene filas físicas en ReservaSalida
        self.assertEqual(reserva.salidas.count(), 0)
        self.assertEqual(obtener_contexto_cupo(dia2, self.empresa).grupos, [2])

        # Al confirmarse y pasar a PAGADA, sincronizar_salidas crea las ReservaSalida físicas
        reserva.estado = Reserva.Estado.PAGADA
        reserva.save()
        self.assertEqual(reserva.salidas.count(), 3)

        # Aunque apartado_hasta siga en el futuro, reservas_con_apartado_vigente filtra pendiente_pago,
        # por lo que el cupo ocupado sigue siendo exactamente 2 personas (1 grupo), nunca duplicado
        self.assertEqual(obtener_contexto_cupo(dia2, self.empresa).grupos, [2])

    def test_reserva_sin_paquete_o_con_orden_devuelve_retrato_vacio(self):
        """Una reserva sin paquete o con orden cruza-empresa no genera salidas en construir_retrato_paquete."""
        reserva_sin_paquete = Reserva(
            empresa=self.empresa,
            fecha=self.inicio,
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Carlos Ruiz',
            telefono_cliente='+5216121234567',
            correo_cliente='carlos@example.com',
            canal_origen='web',
            moneda='MXN',
            deslinde_aceptado=True,
            deslinde_nombre='Carlos Ruiz',
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        self.assertEqual(
            construir_retrato_paquete(reserva_sin_paquete),
            {"v": 1, "salidas": [], "habitaciones": []},
        )

        reserva_con_orden = Reserva(
            empresa=self.empresa,
            paquete=self.paquete_multidia,
            fecha=self.inicio,
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Carlos Ruiz',
            telefono_cliente='+5216121234567',
            correo_cliente='carlos@example.com',
            canal_origen='web',
            moneda='MXN',
            deslinde_aceptado=True,
            deslinde_nombre='Carlos Ruiz',
            estado=Reserva.Estado.PENDIENTE_PAGO,
            orden_id=123,
        )
        self.assertEqual(
            construir_retrato_paquete(reserva_con_orden),
            {"v": 1, "salidas": [], "habitaciones": []},
        )
