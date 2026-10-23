"""Solo lo que sale al mar en panga cuenta contra el cupo de pangas.

Una empresa que ademas vende hospedaje (`por_noche`) o traslados (`bajo_demanda`)
contaba esas reservas como si fueran un grupo mas en una panga: gastaban un lugar
del tope diario y una panga en `caben(...)`, y la pesca se rechazaba (o, ya en el
pago, el webhook devolvia el dinero) por una cama o un traslado.

Las reservas se crean con `objects.create` a proposito, sin pasar por `full_clean`:
lo que se prueba es lo que el motor CUENTA, no la validacion de cada alta.
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from apps.bookings.cupo import (
    construir_retrato_hospedaje,
    construir_retrato_paquete,
    demanda_apartada_del_dia,
    obtener_contexto_cupo,
    obtener_contexto_rango,
)
from apps.bookings.models import (
    MOTIVO_LLENO,
    Agenda,
    CupoDiario,
    Reserva,
    ReservaSalida,
    evaluar_cupo,
    validar_cupo_diario,
)
from apps.bookings.panorama import armar_panorama
from apps.fleet.models import Paquete, PaqueteServicio, Recurso, Servicio
from apps.tenancy import scope
from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca


class BaseCupoSoloMar(ApiTestCase):
    """Flota de 5 pangas (3 de 3 lugares, 2 de 5) y un servicio de cada clase."""

    def setUp(self):
        super().setUp()
        crear_flota(self.empresa, [(3, 3), (2, 5)])
        self.fecha = date.today() + timedelta(days=30)
        self.pesca = crear_servicio_pesca(self.empresa)
        self.paseo = Servicio.objects.create(
            empresa=self.empresa, nombre='Avistamiento', slug='avistamiento', tipo_servicio='paseo',
            estrategia_cupo='por_recurso_dia', precio_base=Decimal('2000.00'),
        )
        self.hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Hotel Casa Arrecife', slug='hotel-casa-arrecife',
            tipo_servicio='hospedaje', estrategia_cupo='por_noche', estrategia_precio='por_noche',
            precio_base=Decimal('2500.00'),
        )
        self.traslado = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado al aeropuerto', slug='traslado-aeropuerto',
            tipo_servicio='transporte', estrategia_cupo='bajo_demanda', precio_base=Decimal('3500.00'),
        )
        self._n = 0

    def reserva(self, servicio, fecha=None, personas=2, estado=Reserva.Estado.PAGADA, **extra):
        self._n += 1
        datos = dict(
            empresa=self.empresa, servicio=servicio, fecha=fecha or self.fecha, hora=time(6, 0),
            numero_personas=personas, nombre_cliente=f'Cliente {self._n}',
            telefono_cliente='+5216121234567', correo_cliente=f'cliente{self._n}@example.com',
            moneda='MXN', canal_origen=Reserva.CanalOrigen.WHATSAPP, estado=estado,
        )
        datos.update(extra)
        return Reserva.objects.create(**datos)

    def paquete(self, slug, *componentes):
        """`componentes`: tuplas (servicio, kwargs de PaqueteServicio)."""
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre=slug, slug=slug,
            precio_ancla=Decimal('9000.00'),
        )
        for orden, (servicio, extra) in enumerate(componentes, start=1):
            PaqueteServicio.objects.create(paquete=paquete, servicio=servicio, orden=orden, **extra)
        return paquete

    def reserva_de_paquete(self, paquete, fecha=None, personas=2, **extra):
        inicio = fecha or self.fecha
        return self.reserva(
            None, fecha=inicio, personas=personas, paquete=paquete, inicio_paquete=inicio,
            fecha_salida=inicio + timedelta(days=3), deslinde_aceptado=True, **extra,
        )

    def vender_hospedaje_y_traslado(self, fecha=None):
        """Dos hospedajes sueltos y un traslado suelto, pagados, ese dia."""
        self.reserva(self.hotel, fecha, fecha_salida=(fecha or self.fecha) + timedelta(days=2))
        self.reserva(self.hotel, fecha, fecha_salida=(fecha or self.fecha) + timedelta(days=3))
        self.reserva(self.traslado, fecha)


class CasoMotivadorTests(BaseCupoSoloMar):
    def test_hospedaje_y_traslado_no_ocupan_panga_ni_lugar_del_dia(self):
        for _ in range(3):
            self.reserva(self.pesca)
        self.vender_hospedaje_y_traslado()

        # Con las 3 pescas ya vendidas quedan 2 pangas: un cuarto grupo cabe.
        self.assertIsNone(evaluar_cupo(self.fecha, 2, self.empresa))
        validar_cupo_diario(self.fecha, 2, self.empresa)  # no debe lanzar

    def test_el_contexto_solo_trae_los_grupos_de_pesca(self):
        self.reserva(self.pesca, personas=3)
        self.reserva(self.pesca, personas=2)
        self.vender_hospedaje_y_traslado()

        ctx = obtener_contexto_cupo(self.fecha, self.empresa)
        self.assertEqual(sorted(ctx.grupos), [2, 3])

    def test_el_endpoint_de_cupo_coincide_con_el_motor(self):
        for _ in range(3):
            self.reserva(self.pesca)
        self.vender_hospedaje_y_traslado()

        cuerpo = self.client.get(
            f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2'
        ).json()
        self.assertTrue(cuerpo['disponible'])
        self.assertIsNone(cuerpo['motivo_no_disponible'])
        self.assertEqual(cuerpo['ocupadas'], 3)

    def test_el_endpoint_de_rango_coincide_con_el_motor(self):
        for _ in range(3):
            self.reserva(self.pesca)
        self.vender_hospedaje_y_traslado()

        cuerpo = self.client.get(
            f'/api/{self.empresa.slug}/cupo/rango/',
            {'desde': str(self.fecha), 'hasta': str(self.fecha), 'personas': '2'},
        ).json()
        self.assertIsNone(cuerpo['dias'][str(self.fecha)])

    def test_la_pesca_si_sigue_llenando_las_pangas(self):
        # Contraprueba: el arreglo no puede aflojar el cupo de lo que si sale al mar.
        for _ in range(5):
            self.reserva(self.pesca)
        self.assertEqual(evaluar_cupo(self.fecha, 2, self.empresa), 'sin_panga')


class TopeDiarioTests(BaseCupoSoloMar):
    def test_con_tope_3_y_3_viajes_de_pesca_el_cuarto_se_rechaza(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=3)
        for _ in range(3):
            self.reserva(self.pesca)

        self.assertEqual(evaluar_cupo(self.fecha, 2, self.empresa), MOTIVO_LLENO)
        with self.assertRaises(ValidationError):
            validar_cupo_diario(self.fecha, 2, self.empresa)

    def test_con_tope_3_dos_pescas_y_un_hospedaje_la_tercera_pesca_entra(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=3)
        self.reserva(self.pesca)
        self.reserva(self.pesca)
        self.reserva(self.hotel, fecha_salida=self.fecha + timedelta(days=2))

        self.assertIsNone(evaluar_cupo(self.fecha, 2, self.empresa))
        validar_cupo_diario(self.fecha, 2, self.empresa)

    def test_con_tope_3_un_traslado_tampoco_gasta_un_viaje(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=3)
        self.reserva(self.pesca)
        self.reserva(self.pesca)
        self.reserva(self.traslado)

        self.assertIsNone(evaluar_cupo(self.fecha, 2, self.empresa))


class RangoTests(BaseCupoSoloMar):
    def test_el_rango_trae_los_mismos_grupos_que_el_dia_suelto(self):
        dias = [self.fecha + timedelta(days=i) for i in range(4)]
        self.reserva(self.pesca, dias[0], personas=3)
        self.reserva(self.pesca, dias[1], personas=2)
        self.reserva(self.pesca, dias[1], personas=4)
        self.reserva(self.hotel, dias[1], fecha_salida=dias[3])
        self.reserva(self.traslado, dias[2])
        self.reserva(self.hotel, dias[2], personas=5, fecha_salida=dias[3])

        rango = obtener_contexto_rango(dias[0], dias[-1], self.empresa)

        for dia in dias:
            with self.subTest(dia=dia):
                suelto = obtener_contexto_cupo(dia, self.empresa)
                self.assertEqual(
                    sorted(rango.grupos_por_fecha.get(dia, [])), sorted(suelto.grupos),
                )
        self.assertEqual(sorted(rango.grupos_por_fecha[dias[1]]), [2, 4])
        self.assertNotIn(dias[2], rango.grupos_por_fecha)

    def test_la_disponibilidad_por_dia_ignora_hospedaje_y_traslado(self):
        from apps.bookings.models import disponibilidad_por_fecha

        for _ in range(3):
            self.reserva(self.pesca)
        self.vender_hospedaje_y_traslado()

        self.assertIsNone(
            disponibilidad_por_fecha(self.fecha, self.fecha, 2, self.empresa)[self.fecha]
        )


class ReservasQueSiCuentanTests(BaseCupoSoloMar):
    def test_una_reserva_de_pesca_anterior_al_catalogo_sin_servicio_sigue_contando(self):
        self.reserva(None, personas=3)  # servicio y paquete nulos: pesca legacy

        ctx = obtener_contexto_cupo(self.fecha, self.empresa)
        self.assertEqual(ctx.grupos, [3])
        rango = obtener_contexto_rango(self.fecha, self.fecha, self.empresa)
        self.assertEqual(rango.grupos_por_fecha[self.fecha], [3])

    def test_un_paseo_de_la_misma_empresa_comparte_la_flota_con_la_pesca(self):
        self.reserva(self.pesca, personas=2)
        self.reserva(self.paseo, personas=3)

        ctx = obtener_contexto_cupo(self.fecha, self.empresa)
        self.assertEqual(sorted(ctx.grupos), [2, 3])
        # 2 + 3 viajes ya vendidos: con 5 pangas y el tope normal, quedan 3 lugares
        # y un sexto grupo no cabe en las pangas.
        for _ in range(3):
            self.reserva(self.paseo)
        self.assertEqual(evaluar_cupo(self.fecha, 2, self.empresa), 'sin_panga')

    def test_un_paquete_con_salidas_al_mar_cuenta_en_cada_fecha_de_salida(self):
        paquete = self.paquete(
            'mar-multidia',
            (self.hotel, dict(noches=4)),
            (self.pesca, dict(dia_estancia=2, salidas=2)),
        )
        reserva = self.reserva_de_paquete(paquete, personas=3)
        self.assertEqual(reserva.salidas.count(), 2)

        dia2 = self.fecha + timedelta(days=1)
        dia3 = self.fecha + timedelta(days=2)
        self.assertEqual(obtener_contexto_cupo(dia2, self.empresa).grupos, [3])
        self.assertEqual(obtener_contexto_cupo(dia3, self.empresa).grupos, [3])
        # Su Reserva.fecha (dia 1) no cuenta: ya tiene salidas, ver backend/CLAUDE.md.
        self.assertEqual(obtener_contexto_cupo(self.fecha, self.empresa).grupos, [])
        rango = obtener_contexto_rango(self.fecha, dia3, self.empresa)
        self.assertEqual(rango.grupos_por_fecha, {dia2: [3], dia3: [3]})

    def test_un_paquete_con_una_sola_salida_al_mar_cuenta_en_su_fecha(self):
        paquete = self.paquete(
            'mar-un-dia',
            (self.hotel, dict(noches=2)),
            (self.pesca, dict(dia_estancia=1, salidas=1)),
        )
        self.reserva_de_paquete(paquete, personas=3)

        self.assertEqual(obtener_contexto_cupo(self.fecha, self.empresa).grupos, [3])
        rango = obtener_contexto_rango(self.fecha, self.fecha, self.empresa)
        self.assertEqual(rango.grupos_por_fecha[self.fecha], [3])

    def test_un_paquete_con_dos_componentes_de_mar_cuenta_un_solo_grupo(self):
        # Sin esto el join por componentes duplicaria la fila de la reserva.
        paquete = self.paquete(
            'mar-doble',
            (self.pesca, dict(dia_estancia=1)),
            (self.paseo, dict(dia_estancia=1)),
        )
        self.reserva_de_paquete(paquete, personas=3)

        self.assertEqual(obtener_contexto_cupo(self.fecha, self.empresa).grupos, [3])
        rango = obtener_contexto_rango(self.fecha, self.fecha, self.empresa)
        self.assertEqual(rango.grupos_por_fecha[self.fecha], [3])

    def test_un_paquete_de_hospedaje_y_traslado_no_cuenta(self):
        paquete = self.paquete(
            'tierra',
            (self.hotel, dict(noches=3)),
            (self.traslado, dict(dia_estancia=1)),
        )
        self.reserva_de_paquete(paquete, personas=4)

        self.assertEqual(obtener_contexto_cupo(self.fecha, self.empresa).grupos, [])
        rango = obtener_contexto_rango(self.fecha, self.fecha, self.empresa)
        self.assertEqual(rango.grupos_por_fecha, {})


@override_settings(APARTADO_MINUTOS=15)
class ApartadoSoloMarTests(BaseCupoSoloMar):
    """Un apartado vigente solo puede reservar lugar de mar."""

    def apartar(self, reserva, retrato):
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva.apartado_demanda = retrato
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

    def test_el_apartado_de_hospedaje_no_aporta_grupos_de_mar(self):
        Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Habitacion 1', capacidad_maxima=4,
        )
        reserva = self.reserva(
            self.hotel, estado=Reserva.Estado.PENDIENTE_PAGO, fecha_salida=self.fecha + timedelta(days=2),
        )
        self.apartar(reserva, construir_retrato_hospedaje(reserva))

        self.assertEqual(demanda_apartada_del_dia(self.empresa, self.fecha), [])
        self.assertEqual(obtener_contexto_cupo(self.fecha, self.empresa).grupos, [])

    def test_el_apartado_de_un_paquete_sin_mar_no_aporta_grupos(self):
        Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Habitacion 2', capacidad_maxima=4,
        )
        paquete = self.paquete(
            'tierra-apartado', (self.hotel, dict(noches=2)), (self.traslado, dict(dia_estancia=1)),
        )
        reserva = self.reserva_de_paquete(paquete, estado=Reserva.Estado.PENDIENTE_PAGO)
        self.apartar(reserva, construir_retrato_paquete(reserva))

        self.assertEqual(obtener_contexto_cupo(self.fecha, self.empresa).grupos, [])
        rango = obtener_contexto_rango(self.fecha, self.fecha, self.empresa)
        self.assertEqual(rango.grupos_por_fecha, {})

    def test_el_apartado_de_un_paquete_con_mar_aporta_solo_el_grupo_de_mar(self):
        Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Habitacion 3', capacidad_maxima=4,
        )
        paquete = self.paquete(
            'mar-apartado', (self.hotel, dict(noches=2)), (self.pesca, dict(dia_estancia=1)),
        )
        reserva = self.reserva_de_paquete(paquete, personas=3, estado=Reserva.Estado.PENDIENTE_PAGO)
        retrato = construir_retrato_paquete(reserva)
        self.apartar(reserva, retrato)

        self.assertEqual(len(retrato['salidas']), 1)
        self.assertEqual(obtener_contexto_cupo(self.fecha, self.empresa).grupos, [3])


class AgendaSoloMarTests(BaseCupoSoloMar):
    def test_el_panorama_no_lista_el_hospedaje_pagado_como_viaje_sin_panga(self):
        self.reserva(self.pesca)
        self.reserva(self.hotel, fecha_salida=self.fecha + timedelta(days=2))
        self.reserva(self.traslado)

        panorama = armar_panorama(self.fecha, self.empresa)

        self.assertEqual([r.servicio_id for r in panorama.sin_repartir[0]], [self.pesca.pk])
        self.assertEqual(panorama.resumen.sin_panga, 1)
        # El numero del dia sale del mismo contexto del motor: un viaje, no tres.
        self.assertEqual(panorama.cupo_dias[0].vendidos, 1)

    def test_el_panorama_cuenta_como_atrasados_solo_los_viajes_de_mar(self):
        ayer = date.today() - timedelta(days=1)
        self.reserva(self.pesca, ayer)
        self.reserva(self.hotel, ayer, fecha_salida=self.fecha)

        panorama = armar_panorama(date.today(), self.empresa)

        self.assertEqual(panorama.resumen.atrasados, 1)

    def test_el_panorama_conserva_los_paquetes_con_mar_y_quita_los_que_no(self):
        con_mar = self.paquete('p-mar', (self.hotel, dict(noches=2)), (self.pesca, dict(dia_estancia=1)))
        sin_mar = self.paquete('p-tierra', (self.hotel, dict(noches=2)), (self.traslado, dict(dia_estancia=1)))
        r_mar = self.reserva_de_paquete(con_mar)
        self.reserva_de_paquete(sin_mar)

        panorama = armar_panorama(self.fecha, self.empresa)

        self.assertEqual([r.pk for r in panorama.sin_repartir[0]], [r_mar.pk])

    def test_la_agenda_por_repartir_no_incluye_hospedaje(self):
        pesca = self.reserva(self.pesca)
        self.reserva(self.hotel, fecha_salida=self.fecha + timedelta(days=2))
        self.reserva(self.traslado)

        self.assertEqual(list(Agenda.por_repartir().values_list('pk', flat=True)), [pesca.pk])


class RevisarCupoSoloMarTests(BaseCupoSoloMar):
    def test_la_auditoria_no_marca_un_dia_por_camas_y_traslados(self):
        from io import StringIO

        from django.core.management import call_command

        fecha = date.today() + timedelta(days=3)
        self.reserva(self.pesca, fecha)
        for _ in range(6):  # sumados a la pesca serian 7 "viajes" contra 5 pangas
            self.reserva(self.hotel, fecha, fecha_salida=fecha + timedelta(days=1))
        self.reserva(self.traslado, fecha)

        # El comando abre su propio scope por empresa: no es reentrante con el del test.
        salida = StringIO()
        self._alcance.__exit__(None, None, None)
        try:
            call_command('revisar_cupo', '--dias', '10', stdout=salida)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        self.assertNotIn('No cierra', salida.getvalue())
