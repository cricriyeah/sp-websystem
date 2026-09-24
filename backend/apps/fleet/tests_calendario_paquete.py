from datetime import date

from django.test import SimpleTestCase

from apps.fleet.calendario_paquete import (
    ComponenteCalendario, fecha_ancla, fecha_de_componente, fecha_salida,
    inicio_desde_reserva, noches_del_paquete,
)

PESCA_DIA_2 = ComponenteCalendario(dia_estancia=2, estrategia_cupo='por_recurso_dia', noches=None)
HOTEL_3 = ComponenteCalendario(dia_estancia=1, estrategia_cupo='por_noche', noches=3)
TRASLADO_DIA_2 = ComponenteCalendario(dia_estancia=2, estrategia_cupo='bajo_demanda', noches=None)
INICIO = date(2026, 10, 10)


class CalendarioPaqueteTests(SimpleTestCase):
    def test_noches_del_paquete(self):
        self.assertEqual(noches_del_paquete([PESCA_DIA_2, HOTEL_3]), 3)
        self.assertIsNone(noches_del_paquete([PESCA_DIA_2]))

    def test_fecha_de_cada_componente_cuenta_desde_el_dia_1(self):
        self.assertEqual(fecha_de_componente(INICIO, 1), date(2026, 10, 10))
        self.assertEqual(fecha_de_componente(INICIO, 2), date(2026, 10, 11))

    def test_fecha_de_salida_es_inicio_mas_noches(self):
        self.assertEqual(fecha_salida(INICIO, [PESCA_DIA_2, HOTEL_3]), date(2026, 10, 13))
        self.assertIsNone(fecha_salida(INICIO, [PESCA_DIA_2]))

    def test_ancla_es_el_dia_de_la_actividad_operativa(self):
        self.assertEqual(fecha_ancla(INICIO, [PESCA_DIA_2, HOTEL_3, TRASLADO_DIA_2]), date(2026, 10, 11))

    def test_sin_actividad_el_ancla_es_el_inicio(self):
        self.assertEqual(fecha_ancla(INICIO, [HOTEL_3]), INICIO)

    def test_inicio_se_recupera_de_la_reserva(self):
        componentes = [PESCA_DIA_2, HOTEL_3]
        self.assertEqual(inicio_desde_reserva(date(2026, 10, 11), date(2026, 10, 13), componentes), INICIO)
        sin_hotel = [ComponenteCalendario(dia_estancia=1, estrategia_cupo='por_recurso_dia', noches=None)]
        self.assertEqual(inicio_desde_reserva(INICIO, None, sin_hotel), INICIO)
