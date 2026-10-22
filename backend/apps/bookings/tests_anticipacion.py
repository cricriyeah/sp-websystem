"""Anticipación mínima de la reserva web: 16 horas contra la salida, en la hora de la sede."""
from datetime import date, datetime, time, timezone as tz
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from apps.bookings.anticipacion import anticipacion_insuficiente

SEDE = SimpleNamespace(zona_horaria='America/Mazatlan')  # UTC-7 todo el año
# 11:00 pm del 9 de octubre en la sede = 06:00 UTC del 10.
AHORA = datetime(2026, 10, 10, 6, 0, tzinfo=tz.utc)


@override_settings(HORAS_MINIMAS_RESERVA=16)
class AnticipacionMinimaTests(SimpleTestCase):
    def test_a_las_11_pm_no_se_reserva_la_salida_de_las_7_am(self):
        self.assertIsNotNone(anticipacion_insuficiente(SEDE, date(2026, 10, 10), time(7, 0), ahora=AHORA))

    def test_con_16_horas_justas_se_puede(self):
        # 11 pm + 16 h = 3 pm del día siguiente.
        self.assertIsNone(anticipacion_insuficiente(SEDE, date(2026, 10, 10), time(15, 0), ahora=AHORA))
        self.assertIsNotNone(anticipacion_insuficiente(SEDE, date(2026, 10, 10), time(14, 59), ahora=AHORA))

    def test_dos_dias_antes_siempre_cumple(self):
        self.assertIsNone(anticipacion_insuficiente(SEDE, date(2026, 10, 11), time(5, 0), ahora=AHORA))

    def test_una_fecha_pasada_no_cumple(self):
        self.assertIsNotNone(anticipacion_insuficiente(SEDE, date(2026, 10, 1), time(7, 0), ahora=AHORA))

    def test_usa_el_dia_de_la_sede_no_el_utc(self):
        # En UTC ya es 10 de octubre, pero en la sede sigue siendo el 9: «desde mañana» es el 10.
        self.assertIsNone(anticipacion_insuficiente(SEDE, date(2026, 10, 10), None, ahora=AHORA))
        self.assertIsNotNone(anticipacion_insuficiente(SEDE, date(2026, 10, 9), None, ahora=AHORA))

    def test_sin_hora_rige_desde_manana(self):
        self.assertIsNotNone(anticipacion_insuficiente(SEDE, date(2026, 10, 9), None, ahora=AHORA))


@override_settings(HORAS_MINIMAS_RESERVA=0)
class ReglaApagadaTests(SimpleTestCase):
    def test_con_cero_horas_no_se_exige_nada(self):
        self.assertIsNone(anticipacion_insuficiente(SEDE, date(2026, 10, 1), time(7, 0), ahora=AHORA))
