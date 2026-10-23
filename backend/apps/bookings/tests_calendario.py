"""El módulo puro del Calendario: de reservas a eventos y estancias.

Lo que se protege aqui: que una reserva deje UNA marca por vista (un paquete es su
barra de estancia y no se repite en cada dia de mar), que lo que no es una reserva
todavia (`pendiente_pago`) nunca se vea, que "sin panga" y "atrasada" salgan de la
misma regla que la Agenda, y que el hallazgo cuente reservas y no eventos.
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.bookings.calendario import ATRASADA, SIN_PANGA, armar_calendario, tira_de_pangas
from apps.bookings.models import CupoDiario, Reserva, ViajeTransporte
from apps.fleet.models import (
    Embarcacion, EmbarcacionNoDisponible, Paquete, PaqueteServicio, Servicio, Vehiculo,
)
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase, crear_flota

# Miercoles. La semana que lo contiene va del lunes 19 al domingo 25 de octubre de 2026.
HOY = date(2026, 10, 21)
LUNES = date(2026, 10, 19)
DOMINGO = date(2026, 10, 25)


def dia(n):
    """El dia `n` de octubre de 2026."""
    return date(2026, 10, n)


class CalendarioBase(OperadorTestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede cal', slug='sede-cal')
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Sal Cal', slug='sal-cal')
        self.pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca-cal', tipo_servicio='pesca',
        )
        self.hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Cabaña', slug='cabana-cal', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche',
        )
        self.traslado = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado', slug='traslado-cal', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
        )
        self.tour = Servicio.objects.create(
            empresa=self.empresa, nombre='Safari', slug='safari-cal', tipo_servicio='paseo',
            estrategia_cupo='bajo_demanda',
        )
        self.panga = Embarcacion.objects.create(
            empresa=self.empresa, nombre='Dorado', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
        )
        self.n = 0

    def reserva(self, **extra):
        """Una reserva pagada de pesca; cada llamada con otro nombre de cliente."""
        self.n += 1
        datos = dict(
            empresa=self.empresa, servicio=self.pesca, fecha=HOY + timedelta(days=1), hora=time(6),
            numero_personas=2, nombre_cliente=f'Cliente {self.n}', telefono_cliente='+5216121234567',
            correo_cliente='c@example.com', canal_origen=Reserva.CanalOrigen.WHATSAPP,
            estado=Reserva.Estado.PAGADA,
        )
        datos.update(extra)
        return Reserva.objects.create(**datos)

    def hospedaje(self, entrada, salida, **extra):
        return self.reserva(servicio=self.hotel, fecha=entrada, fecha_salida=salida, hora=None, **extra)

    def traslado_redondo(self, ida, regreso, **extra):
        reserva = self.reserva(servicio=self.traslado, fecha=ida, hora=None, **extra)
        viajes = [
            ViajeTransporte.objects.create(
                empresa=self.empresa, reserva=reserva, sentido='ida', fecha=ida, hora=time(9),
            ),
            ViajeTransporte.objects.create(
                empresa=self.empresa, reserva=reserva, sentido='regreso', fecha=regreso,
            ),
        ]
        return reserva, viajes

    def armar(self, desde=LUNES, hasta=DOMINGO, **extra):
        extra.setdefault('hoy', HOY)
        return armar_calendario(desde, hasta, self.empresa, **extra)

    def nombres(self, piezas):
        return sorted(p.reserva.nombre_cliente for p in piezas)


class SembrarPaquete:
    """Paquete de una empresa: pesca el dia 2 + hospedaje de 3 noches (inicio martes 20)."""

    def sembrar_paquete(self, salidas=1, con_hotel=True):
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Fin de semana', slug='finde-cal',
            precio_ancla=Decimal('9500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.pesca, orden=1, dia_estancia=2,
            personas_incluidas=3, salidas=salidas,
        )
        if con_hotel:
            PaqueteServicio.objects.create(
                paquete=self.paquete, servicio=self.hotel, orden=2, noches=3, personas_incluidas=2,
            )

    def reserva_paquete(self, inicio=dia(20), noches=3, **extra):
        return self.reserva(
            servicio=None, paquete=self.paquete, inicio_paquete=inicio, fecha=inicio + timedelta(days=1),
            fecha_salida=inicio + timedelta(days=noches) if noches else None, **extra,
        )


class EventosDeMarTests(CalendarioBase):
    def test_pesca_suelta_es_un_evento_en_su_dia_con_su_hora(self):
        reserva = self.reserva(fecha=dia(22), hora=time(6, 30))

        cal = self.armar()

        self.assertEqual(len(cal.eventos), 1)
        evento = cal.eventos[0]
        self.assertEqual(evento.reserva, reserva)
        self.assertEqual((evento.fecha, evento.hora, evento.tipo), (dia(22), time(6, 30), 'mar'))
        self.assertEqual(cal.estancias, [])

    def test_lo_que_cae_fuera_del_rango_no_aparece(self):
        self.reserva(fecha=LUNES - timedelta(days=1))
        self.reserva(fecha=DOMINGO + timedelta(days=1))
        dentro = self.reserva(fecha=DOMINGO)

        self.assertEqual([e.reserva for e in self.armar().eventos], [dentro])

    def test_se_ven_pagada_asignada_y_completada_y_nunca_la_pendiente_de_pago(self):
        self.reserva(estado=Reserva.Estado.PAGADA, nombre_cliente='Pagada')
        self.reserva(estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga, nombre_cliente='Asignada')
        self.reserva(estado=Reserva.Estado.COMPLETADA, nombre_cliente='Completada')
        self.reserva(estado=Reserva.Estado.PENDIENTE_PAGO, nombre_cliente='Pendiente')

        self.assertEqual(self.nombres(self.armar().eventos), ['Asignada', 'Completada', 'Pagada'])
        # Ni siquiera con el interruptor de canceladas: una pendiente no es una reserva.
        self.assertNotIn('Pendiente', self.nombres(self.armar(canceladas=True).eventos))

    def test_la_cancelada_solo_sale_con_el_interruptor_y_se_pinta_cancelada(self):
        self.reserva(estado=Reserva.Estado.CANCELADA, nombre_cliente='Cancelada')

        self.assertEqual(self.armar().eventos, [])
        eventos = self.armar(canceladas=True).eventos
        self.assertEqual([e.estilo for e in eventos], ['cancelada'])

    def test_ordena_por_dia_y_luego_por_hora_dejando_sin_hora_al_final(self):
        self.reserva(fecha=dia(22), hora=None, nombre_cliente='Sin hora')
        self.reserva(fecha=dia(22), hora=time(7), nombre_cliente='Tarde')
        self.reserva(fecha=dia(22), hora=time(5), nombre_cliente='Temprano')
        self.reserva(fecha=dia(20), hora=time(7), nombre_cliente='Antes')

        orden = [e.reserva.nombre_cliente for e in self.armar().eventos]

        self.assertEqual(orden, ['Antes', 'Temprano', 'Tarde', 'Sin hora'])

    def test_un_tour_bajo_demanda_es_un_evento_que_nunca_pide_panga(self):
        self.reserva(servicio=self.tour, fecha=dia(22))

        evento = self.armar().eventos[0]

        self.assertEqual((evento.tipo, evento.marca, evento.estilo), ('mar', None, 'asignada'))

    def test_solo_la_empresa_pedida(self):
        otra = Empresa.objects.create(sede=self.sede, nombre='Otra', slug='otra-cal')
        otro_servicio = Servicio.objects.create(empresa=otra, nombre='Pesca', slug='pesca-otra')
        self.reserva(nombre_cliente='Mia')
        self.reserva(empresa=otra, servicio=otro_servicio, nombre_cliente='Ajena')

        self.assertEqual(self.nombres(self.armar().eventos), ['Mia'])
        todas = armar_calendario(LUNES, DOMINGO, None, hoy=HOY)
        self.assertEqual(self.nombres(todas.eventos), ['Ajena', 'Mia'])


class EstanciasTests(SembrarPaquete, CalendarioBase):
    def test_hospedaje_es_una_estancia_de_la_entrada_a_la_salida(self):
        reserva = self.hospedaje(dia(21), dia(24))

        cal = self.armar()

        self.assertEqual(cal.eventos, [])
        self.assertEqual(len(cal.estancias), 1)
        estancia = cal.estancias[0]
        self.assertEqual(estancia.reserva, reserva)
        self.assertEqual((estancia.inicio, estancia.fin, estancia.noches), (dia(21), dia(24), 3))
        self.assertEqual(estancia.tipo, 'hospedaje')

    def test_la_estancia_que_cruza_el_borde_aparece_en_las_dos_semanas_con_las_mismas_fechas(self):
        self.hospedaje(dia(23), dia(28))

        esta = self.armar().estancias
        siguiente = self.armar(LUNES + timedelta(days=7), DOMINGO + timedelta(days=7)).estancias

        self.assertEqual([(e.inicio, e.fin) for e in esta], [(dia(23), dia(28))])
        self.assertEqual([(e.inicio, e.fin) for e in siguiente], [(dia(23), dia(28))])

    def test_la_estancia_que_empezo_antes_y_sigue_ahi_tambien_cuenta(self):
        self.hospedaje(dia(10), dia(30))

        self.assertEqual(len(self.armar().estancias), 1)

    def test_la_que_sale_el_lunes_en_la_manana_no_ocupa_esa_semana(self):
        # Salida exclusiva: se va el lunes 19 por la manana, la ultima noche fue la del domingo 18.
        self.hospedaje(dia(15), LUNES)

        self.assertEqual(self.armar().estancias, [])

    def test_hospedaje_cancelado_solo_con_el_interruptor(self):
        self.hospedaje(dia(21), dia(23), estado=Reserva.Estado.CANCELADA)

        self.assertEqual(self.armar().estancias, [])
        self.assertEqual([e.estilo for e in self.armar(canceladas=True).estancias], ['cancelada'])

    def test_paquete_es_una_sola_estancia_con_noches_y_dias_de_mar(self):
        self.sembrar_paquete()
        reserva = self.reserva_paquete()

        cal = self.armar()

        self.assertEqual(len(cal.estancias), 1)
        estancia = cal.estancias[0]
        self.assertEqual(estancia.reserva, reserva)
        self.assertEqual((estancia.inicio, estancia.fin), (dia(20), dia(23)))
        self.assertEqual((estancia.noches, estancia.dias_de_mar, estancia.tipo), (3, 1, 'paquete'))

    def test_sus_dias_de_mar_no_se_repiten_como_eventos_en_semana_o_mes(self):
        self.sembrar_paquete()
        self.reserva_paquete()

        self.assertEqual(self.armar().eventos, [])

    def test_en_la_vista_dia_los_dias_de_mar_si_son_renglones_propios(self):
        self.sembrar_paquete()
        reserva = self.reserva_paquete()

        cal = self.armar(dia(21), dia(21), dias_de_mar=True)

        self.assertEqual([(e.reserva, e.fecha, e.tipo) for e in cal.eventos], [(reserva, dia(21), 'dia_de_mar')])
        self.assertEqual(len(cal.estancias), 1)  # la estancia tambien esta ese dia

    def test_paquete_de_varios_dias_de_mar_los_toma_de_sus_salidas(self):
        crear_flota(self.empresa)
        self.sembrar_paquete(salidas=3)
        reserva = self.reserva_paquete(noches=4)

        cal = self.armar(dias_de_mar=True)

        self.assertEqual(cal.estancias[0].dias_de_mar, 3)
        self.assertEqual(
            [(e.reserva, e.fecha) for e in cal.eventos],
            [(reserva, dia(21)), (reserva, dia(22)), (reserva, dia(23))],
        )

    def test_paquete_sin_hospedaje_dura_lo_que_duran_sus_dias_de_mar(self):
        crear_flota(self.empresa)
        self.sembrar_paquete(salidas=3, con_hotel=False)
        self.reserva_paquete(noches=0)

        estancia = self.armar().estancias[0]

        self.assertEqual((estancia.inicio, estancia.fin), (dia(20), dia(24)))
        self.assertIsNone(estancia.noches)
        self.assertEqual(estancia.dias_de_mar, 3)

    def test_paquete_sin_nada_de_mar_no_tiene_dias_de_mar(self):
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Descanso', slug='descanso-cal',
            precio_ancla=Decimal('5000.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.hotel, orden=1, noches=2, personas_incluidas=2,
        )
        self.reserva(servicio=None, paquete=self.paquete, inicio_paquete=dia(20), fecha=dia(20), fecha_salida=dia(22))

        cal = self.armar(dias_de_mar=True)

        self.assertEqual(cal.estancias[0].dias_de_mar, 0)
        self.assertEqual(cal.eventos, [])


class TrasladosTests(CalendarioBase):
    def test_cada_tramo_es_un_evento_en_su_propia_fecha_y_hora(self):
        reserva, (ida, regreso) = self.traslado_redondo(dia(20), dia(24))

        eventos = self.armar().eventos

        self.assertEqual(
            [(e.reserva, e.fecha, e.hora, e.tipo, e.tramo) for e in eventos],
            [(reserva, dia(20), time(9), 'traslado', ida), (reserva, dia(24), None, 'traslado', regreso)],
        )

    def test_solo_los_tramos_que_caen_en_el_periodo(self):
        self.traslado_redondo(dia(20), dia(28))

        self.assertEqual([e.fecha for e in self.armar().eventos], [dia(20)])
        self.assertEqual([e.fecha for e in self.armar(dia(26), dia(31)).eventos], [dia(28)])

    def test_un_tramo_cancelado_no_se_ve_salvo_con_el_interruptor(self):
        _, (ida, regreso) = self.traslado_redondo(dia(20), dia(24))
        ViajeTransporte.objects.filter(pk=regreso.pk).update(cancelado=True)

        self.assertEqual([e.fecha for e in self.armar().eventos], [dia(20)])
        con = self.armar(canceladas=True).eventos
        self.assertEqual([(e.fecha, e.estilo) for e in con], [(dia(20), 'asignada'), (dia(24), 'cancelada')])

    def test_un_traslado_nunca_lleva_marca_de_sin_panga_aunque_no_tenga_vehiculo(self):
        self.traslado_redondo(dia(20), dia(24))
        self.assertEqual([e.marca for e in self.armar().eventos], [None, None])

    def test_el_vehiculo_asignado_viaja_con_el_tramo(self):
        van = Vehiculo.objects.create(empresa=self.empresa, nombre='Van 1', lugares=8)
        _, (ida, _) = self.traslado_redondo(dia(20), dia(24))
        ViajeTransporte.objects.filter(pk=ida.pk).update(vehiculo=van)

        self.assertEqual(self.armar().eventos[0].tramo.vehiculo, van)


class MarcasTests(SembrarPaquete, CalendarioBase):
    def test_pagada_sin_panga_con_fecha_de_hoy_o_futura_es_sin_panga(self):
        self.reserva(fecha=HOY)
        self.reserva(fecha=HOY + timedelta(days=3))

        self.assertEqual([(e.marca, e.estilo) for e in self.armar().eventos], [(SIN_PANGA, SIN_PANGA)] * 2)

    def test_pagada_sin_panga_con_fecha_pasada_es_atrasada(self):
        self.reserva(fecha=HOY - timedelta(days=1))

        evento = self.armar().eventos[0]

        self.assertEqual((evento.marca, evento.estilo), (ATRASADA, ATRASADA))

    def test_asignada_y_completada_no_llevan_marca(self):
        self.reserva(estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga)
        self.reserva(estado=Reserva.Estado.COMPLETADA, fecha=HOY - timedelta(days=1))

        self.assertEqual(
            [(e.marca, e.estilo) for e in self.armar().eventos],
            [(None, 'completada'), (None, 'asignada')],
        )

    def test_un_hospedaje_pagado_se_pinta_como_asignado_y_nunca_sin_panga(self):
        self.hospedaje(dia(21), dia(23))

        estancia = self.armar().estancias[0]

        self.assertEqual((estancia.marca, estancia.estilo), (None, 'asignada'))

    def test_un_paquete_con_dia_de_mar_y_sin_panga_se_trata_como_el_viaje_de_mar(self):
        self.sembrar_paquete()
        self.reserva_paquete()

        estancia = self.armar().estancias[0]

        self.assertEqual((estancia.marca, estancia.estilo), (SIN_PANGA, SIN_PANGA))

    def test_un_paquete_con_panga_ya_asignada_va_callado(self):
        self.sembrar_paquete()
        self.reserva_paquete(embarcacion=self.panga)

        self.assertEqual(self.armar().estancias[0].estilo, 'asignada')

    def test_un_paquete_sin_nada_de_mar_nunca_pide_panga(self):
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Descanso', slug='descanso-cal',
            precio_ancla=Decimal('5000.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.hotel, orden=1, noches=2, personas_incluidas=2,
        )
        self.reserva(servicio=None, paquete=self.paquete, inicio_paquete=dia(20), fecha=dia(20), fecha_salida=dia(22))

        self.assertIsNone(self.armar().estancias[0].marca)

    def test_la_marca_sale_de_la_regla_de_la_agenda(self):
        # Lo que la Agenda no reparte (bajo demanda y traslados) tampoco se marca aqui.
        from apps.bookings.panorama import sin_lo_que_no_se_reparte

        self.reserva(servicio=self.tour, nombre_cliente='Tour')
        self.reserva(nombre_cliente='Pesca')
        se_reparten = set(
            sin_lo_que_no_se_reparte(Reserva.objects.all()).values_list('nombre_cliente', flat=True)
        )

        marcadas = {e.reserva.nombre_cliente for e in self.armar().eventos if e.marca}

        self.assertEqual(marcadas, {'Pesca'})
        self.assertTrue(marcadas <= se_reparten)


class HallazgoTests(SembrarPaquete, CalendarioBase):
    def test_sin_reservas_todo_en_cero(self):
        hallazgo = self.armar().hallazgo
        self.assertEqual((hallazgo.total, hallazgo.sin_panga, hallazgo.atrasadas), (0, 0, 0))

    def test_cuenta_reservas_y_no_eventos(self):
        self.sembrar_paquete()
        self.reserva_paquete()  # una estancia + un dia de mar
        self.traslado_redondo(dia(20), dia(24))  # dos tramos
        self.reserva(fecha=dia(22), estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga)

        cal = self.armar(dias_de_mar=True)

        self.assertGreater(len(cal.eventos) + len(cal.estancias), 3)
        self.assertEqual(cal.hallazgo.total, 3)

    def test_sin_panga_y_atrasadas_se_cuentan_aparte(self):
        self.reserva(fecha=dia(22), nombre_cliente='A')
        self.reserva(fecha=dia(23), nombre_cliente='B')
        self.reserva(fecha=dia(19), nombre_cliente='C')  # lunes, antes de hoy
        self.reserva(fecha=dia(24), estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga)

        hallazgo = self.armar().hallazgo

        self.assertEqual((hallazgo.total, hallazgo.sin_panga, hallazgo.atrasadas), (4, 2, 1))

    def test_el_paquete_sin_panga_cuenta_una_vez(self):
        self.sembrar_paquete()
        self.reserva_paquete()

        hallazgo = self.armar(dias_de_mar=True).hallazgo

        self.assertEqual((hallazgo.total, hallazgo.sin_panga), (1, 1))

    def test_canceladas_y_pendientes_no_cuentan_aunque_se_muestren(self):
        self.reserva(estado=Reserva.Estado.CANCELADA)
        self.reserva(estado=Reserva.Estado.PENDIENTE_PAGO)

        hallazgo = self.armar(canceladas=True).hallazgo

        self.assertEqual(hallazgo.total, 0)

    def test_el_hallazgo_no_cambia_con_el_interruptor_de_canceladas(self):
        self.reserva(fecha=dia(22))
        self.reserva(estado=Reserva.Estado.CANCELADA)

        self.assertEqual(self.armar().hallazgo, self.armar(canceladas=True).hallazgo)

    def test_el_hallazgo_puede_acotarse_a_un_rango_menor_que_lo_dibujado(self):
        # La vista Mes dibuja semanas completas, pero "este mes" no cuenta los dias grises.
        self.reserva(fecha=dia(20))
        self.reserva(fecha=dia(24))

        cal = self.armar(hallazgo_de=(dia(22), dia(25)))

        self.assertEqual(len(cal.eventos), 2)
        self.assertEqual(cal.hallazgo.total, 1)

    def test_todo_asignado_cuando_nada_pide_panga(self):
        self.reserva(fecha=dia(22), estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga)
        self.hospedaje(dia(21), dia(23))

        hallazgo = self.armar().hallazgo

        self.assertEqual((hallazgo.total, hallazgo.sin_panga, hallazgo.atrasadas), (2, 0, 0))
        self.assertTrue(hallazgo.todo_asignado)


class ConsultasTests(SembrarPaquete, CalendarioBase):
    def sembrar_variado(self, veces):
        for i in range(veces):
            self.reserva(fecha=dia(20 + i % 5), embarcacion=self.panga if i % 2 else None)
            self.hospedaje(dia(20), dia(22))
            self.reserva_paquete()
            self.traslado_redondo(dia(20), dia(24))

    def consultas(self):
        with CaptureQueriesContext(connection) as capturadas:
            self.armar(dias_de_mar=True)
        return len(capturadas)

    def test_las_consultas_no_crecen_con_el_numero_de_reservas(self):
        self.sembrar_paquete()
        self.sembrar_variado(1)
        pocas = self.consultas()
        self.sembrar_variado(5)

        muchas = self.consultas()

        self.assertEqual(muchas, pocas)
        self.assertLessEqual(muchas, 12)


class TiraDePangasTests(CalendarioBase):
    def setUp(self):
        super().setUp()
        self.panga.delete()  # esta empresa arma su flota de diez en cada test
        crear_flota(self.empresa)

    def test_empresa_sin_pangas_no_tiene_tira(self):
        otra = Empresa.objects.create(sede=self.sede, nombre='Sin flota', slug='sin-flota')

        self.assertIsNone(tira_de_pangas(LUNES, DOMINGO, otra))

    def test_cuenta_los_viajes_vendidos_sobre_la_flota_del_dia(self):
        for _ in range(3):
            self.reserva(fecha=dia(22))

        tira = tira_de_pangas(LUNES, DOMINGO, self.empresa)

        self.assertEqual((tira[dia(22)].ocupadas, tira[dia(22)].capacidad), (3, 10))
        self.assertEqual((tira[dia(23)].ocupadas, tira[dia(23)].capacidad), (0, 10))
        self.assertEqual(len(tira), 7)  # una entrada por dia, extremos incluidos

    def test_una_panga_fuera_de_servicio_baja_la_flota_de_ese_dia(self):
        panga = Embarcacion.objects.filter(empresa=self.empresa).first()
        EmbarcacionNoDisponible.objects.create(
            empresa=self.empresa, embarcacion=panga, fecha=dia(22), motivo='motor',
        )

        tira = tira_de_pangas(LUNES, DOMINGO, self.empresa)

        self.assertEqual(tira[dia(22)].capacidad, 9)
        self.assertEqual(tira[dia(23)].capacidad, 10)

    def test_el_tope_del_dia_manda_cuando_es_menor_que_la_flota(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=dia(22), cupo_maximo=6)

        tira = tira_de_pangas(LUNES, DOMINGO, self.empresa)

        self.assertEqual(tira[dia(22)].capacidad, 6)

    def test_lleno_cuando_ya_no_admite_otra_salida(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=dia(22), cupo_maximo=2)
        self.reserva(fecha=dia(22))
        self.reserva(fecha=dia(22))
        self.reserva(fecha=dia(23))

        tira = tira_de_pangas(LUNES, DOMINGO, self.empresa)

        self.assertTrue(tira[dia(22)].lleno)
        self.assertFalse(tira[dia(23)].lleno)

    def test_un_dia_cerrado_cuenta_como_lleno(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=dia(22), cupo_maximo=0)

        tira = tira_de_pangas(LUNES, DOMINGO, self.empresa)

        self.assertTrue(tira[dia(22)].lleno)
        self.assertTrue(tira[dia(22)].cerrado)
