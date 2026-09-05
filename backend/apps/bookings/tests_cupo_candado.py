from datetime import date
from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.bookings.cupo.candado import (
    bloquear_cupo,
    bloquear_cupo_del_dia,
    calcular_clave_candado,
)


class CupoCandadoTests(TestCase):
    """Pruebas del advisory lock re-llaveado por empresa y ámbito."""

    def test_calcular_clave_candado_default(self):
        f = date(2026, 9, 25)
        # Modo default o None usa exactamente fecha.toordinal()
        self.assertEqual(calcular_clave_candado(f), f.toordinal())
        self.assertEqual(calcular_clave_candado(f, ambito=None), f.toordinal())
        self.assertEqual(calcular_clave_candado(f, ambito='default'), f.toordinal())

    def test_calcular_clave_candado_con_ambitos_distintos(self):
        f = date(2026, 9, 25)
        k_pesca = calcular_clave_candado(f, ambito='pesca')
        k_tour = calcular_clave_candado(f, ambito='tour_playas')
        k_hotel = calcular_clave_candado(f, ambito='hotel_cabañas')

        # Las claves entre distintos ámbitos son distintas
        self.assertNotEqual(k_pesca, k_tour)
        self.assertNotEqual(k_pesca, k_hotel)
        self.assertNotEqual(k_tour, k_hotel)

        # Todas están acotadas al rango signed 32-bit positivo de Postgres
        for k in [k_pesca, k_tour, k_hotel]:
            self.assertGreaterEqual(k, 0)
            self.assertLessEqual(k, 0x7FFFFFFF)

    def test_calcular_clave_candado_determinista(self):
        f = date(2026, 9, 25)
        k1 = calcular_clave_candado(f, ambito='recurso_42')
        k2 = calcular_clave_candado(f, ambito='recurso_42')
        self.assertEqual(k1, k2)

    @patch('apps.bookings.cupo.candado.connection')
    def test_bloquear_cupo_en_postgresql(self, mock_conn):
        mock_conn.vendor = 'postgresql'
        cursor_mock = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = cursor_mock

        f = date(2026, 9, 25)
        bloquear_cupo(empresa_id=10, fecha=f, ambito='pesca')

        clave_esperada = calcular_clave_candado(f, ambito='pesca')
        cursor_mock.execute.assert_called_once_with(
            'SELECT pg_advisory_xact_lock(%s, %s)',
            [10, clave_esperada],
        )

    @patch('apps.bookings.cupo.candado.connection')
    def test_bloquear_cupo_del_dia_compatibilidad(self, mock_conn):
        mock_conn.vendor = 'postgresql'
        cursor_mock = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = cursor_mock

        f = date(2026, 9, 25)
        bloquear_cupo_del_dia(empresa_id=5, fecha=f)

        cursor_mock.execute.assert_called_once_with(
            'SELECT pg_advisory_xact_lock(%s, %s)',
            [5, f.toordinal()],
        )

    @patch('apps.bookings.cupo.candado.connection')
    def test_bloquear_cupo_en_sqlite_es_noop(self, mock_conn):
        mock_conn.vendor = 'sqlite'
        bloquear_cupo(empresa_id=1, fecha=date(2026, 9, 25))
        mock_conn.cursor.assert_not_called()
