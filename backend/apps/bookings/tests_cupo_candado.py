from datetime import date
from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.bookings.cupo.candado import (
    bloquear_cupo,
    bloquear_cupo_del_dia,
    calcular_clave_candado,
)


class CupoCandadoTests(TestCase):
    """Pruebas del advisory lock re-llaveado por (empresa, servicio_id, fecha)."""

    def test_calcular_clave_candado_sin_colision_bit30(self):
        f = date(2026, 9, 25)
        legacy = f.toordinal()
        self.assertEqual(calcular_clave_candado(f, servicio_id=None), legacy)
        for sid in range(1, 501):
            k = calcular_clave_candado(f, servicio_id=sid)
            self.assertNotEqual(k, legacy)
            self.assertGreaterEqual(k, 0x40000000)
            self.assertLessEqual(k, 0x7FFFFFFF)
        self.assertNotEqual(
            calcular_clave_candado(f, servicio_id=1),
            calcular_clave_candado(f, servicio_id=2),
        )

    def test_calcular_clave_candado_default(self):
        f = date(2026, 9, 25)
        # Modo default o None usa exactamente fecha.toordinal()
        self.assertEqual(calcular_clave_candado(f), f.toordinal())
        self.assertEqual(calcular_clave_candado(f, servicio_id=None), f.toordinal())

    def test_calcular_clave_candado_determinista(self):
        f = date(2026, 9, 25)
        k1 = calcular_clave_candado(f, servicio_id=42)
        k2 = calcular_clave_candado(f, servicio_id=42)
        self.assertEqual(k1, k2)

    @patch('apps.bookings.cupo.candado.connection')
    def test_bloquear_cupo_en_postgresql(self, mock_conn):
        mock_conn.vendor = 'postgresql'
        cursor_mock = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = cursor_mock

        f = date(2026, 9, 25)
        bloquear_cupo(empresa_id=10, fecha=f, servicio_id=42)

        clave_esperada = calcular_clave_candado(f, servicio_id=42)
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
