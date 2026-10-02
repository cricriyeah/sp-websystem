from datetime import date

from django.test import SimpleTestCase

from apps.fleet.calendario_paquete import (
    ComponenteCalendario, fecha_ancla, fecha_de_componente, fecha_salida,
    fechas_de_actividad, fechas_de_componente, inicio_desde_reserva, noches_del_paquete,
)

PESCA_DIA_2 = ComponenteCalendario(dia_estancia=2, estrategia_cupo='por_recurso_dia', noches=None)
HOTEL_3 = ComponenteCalendario(dia_estancia=1, estrategia_cupo='por_noche', noches=3)
TRASLADO_DIA_2 = ComponenteCalendario(dia_estancia=2, estrategia_cupo='bajo_demanda', noches=None)
INICIO = date(2026, 10, 10)


class CalendarioPaqueteTests(SimpleTestCase):
    def test_fechas_de_componente_son_dias_seguidos(self):
        self.assertEqual(
            fechas_de_componente(date(2026, 11, 14), 2, 4),
            [date(2026, 11, 15), date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 18)],
        )

    def test_fechas_de_componente_una_salida_es_el_comportamiento_de_siempre(self):
        self.assertEqual(fechas_de_componente(date(2026, 11, 14), 1), [date(2026, 11, 14)])

    def test_fechas_de_actividad_toma_la_primera_actividad(self):
        componentes = [ComponenteCalendario(1, 'por_noche', 5), ComponenteCalendario(2, 'por_recurso_dia', None, 4)]
        self.assertEqual(
            fechas_de_actividad(date(2026, 11, 14), componentes),
            [date(2026, 11, 15), date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 18)],
        )
        self.assertEqual(fecha_ancla(date(2026, 11, 14), componentes), date(2026, 11, 15))

    def test_fechas_de_actividad_sin_actividad_es_vacia(self):
        self.assertEqual(fechas_de_actividad(date(2026, 11, 14), [ComponenteCalendario(1, 'por_noche', 5)]), [])

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
