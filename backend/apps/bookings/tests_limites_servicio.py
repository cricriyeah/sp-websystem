"""Pruebas unitarias para el helper limites_de_servicio y mapa_limites."""

from datetime import time
import json
from unittest.mock import MagicMock

from django.test import TestCase

from apps.bookings.limites_servicio import limites_de_servicio, mapa_limites
from apps.bookings.models import MAX_PERSONAS


class LimitesServicioTests(TestCase):
    def test_servicio_con_ventana_completa(self):
        """Un servicio con ventana horaria y pide_hora=True calcula horas y etiqueta con horario."""
        servicio = MagicMock()
        servicio.pk = 10
        servicio.hora_apertura = time(5, 0)
        servicio.hora_cierre = time(7, 0)
        servicio.ventana_horaria.return_value = (time(5, 0), time(7, 0))
        servicio.pide_hora = True
        servicio.paso_hora_minutos = 15
        servicio.capacidad_maxima = 5

        limites = limites_de_servicio(servicio)

        self.assertEqual(limites['apertura'], '05:00')
        self.assertEqual(limites['cierre'], '07:00')
        self.assertEqual(
            limites['horas'],
            ['05:00', '05:15', '05:30', '05:45', '06:00', '06:15', '06:30', '06:45', '07:00'],
        )
        self.assertTrue(limites['pide_hora'])
        self.assertEqual(limites['min_personas'], 1)
        self.assertEqual(limites['max_personas'], 5)
        self.assertEqual(limites['etiqueta'], '05:00 a 07:00 · hasta 5 personas')

    def test_servicio_sin_ventana(self):
        """Un servicio sin ventana horaria devuelve apertura/cierre/horas en None y omite el horario."""
        servicio = MagicMock()
        servicio.pk = 20
        servicio.hora_apertura = None
        servicio.hora_cierre = None
        servicio.ventana_horaria.return_value = None
        servicio.pide_hora = False
        servicio.capacidad_maxima = 4

        limites = limites_de_servicio(servicio)

        self.assertIsNone(limites['apertura'])
        self.assertIsNone(limites['cierre'])
        self.assertIsNone(limites['horas'])
        self.assertFalse(limites['pide_hora'])
        self.assertEqual(limites['min_personas'], 1)
        self.assertEqual(limites['max_personas'], 4)
        self.assertEqual(limites['etiqueta'], 'hasta 4 personas')

    def test_servicio_pide_hora_falso_omite_horario_en_etiqueta(self):
        """Si pide_hora es False, la etiqueta no muestra horario y horas es None."""
        servicio = MagicMock()
        servicio.pk = 30
        servicio.hora_apertura = time(14, 0)
        servicio.hora_cierre = time(18, 0)
        servicio.ventana_horaria.return_value = (time(14, 0), time(18, 0))
        servicio.pide_hora = False
        servicio.paso_hora_minutos = 60
        servicio.capacidad_maxima = 8

        limites = limites_de_servicio(servicio)

        self.assertEqual(limites['apertura'], '14:00')
        self.assertEqual(limites['cierre'], '18:00')
        self.assertIsNone(limites['horas'])
        self.assertFalse(limites['pide_hora'])
        self.assertEqual(limites['min_personas'], 1)
        self.assertEqual(limites['max_personas'], 8)
        self.assertEqual(limites['etiqueta'], 'hasta 8 personas')

    def test_maximo_por_defecto_cuando_capacidad_maxima_falta_o_cero(self):
        """Si capacidad_maxima es None o <= 0, toma el tope por defecto MAX_PERSONAS."""
        servicio_none = MagicMock()
        servicio_none.pk = 41
        servicio_none.ventana_horaria.return_value = None
        servicio_none.pide_hora = False
        servicio_none.capacidad_maxima = None

        limites_none = limites_de_servicio(servicio_none)
        self.assertEqual(limites_none['max_personas'], MAX_PERSONAS)
        self.assertEqual(limites_none['etiqueta'], f'hasta {MAX_PERSONAS} personas')

        servicio_cero = MagicMock()
        servicio_cero.pk = 42
        servicio_cero.ventana_horaria.return_value = None
        servicio_cero.pide_hora = False
        servicio_cero.capacidad_maxima = 0

        limites_cero = limites_de_servicio(servicio_cero)
        self.assertEqual(limites_cero['max_personas'], MAX_PERSONAS)
        self.assertEqual(limites_cero['etiqueta'], f'hasta {MAX_PERSONAS} personas')

    def test_paso_hora_minutos_personalizado(self):
        """El intervalo entre horas respeta paso_hora_minutos del servicio."""
        servicio = MagicMock()
        servicio.pk = 50
        servicio.hora_apertura = time(8, 0)
        servicio.hora_cierre = time(10, 0)
        servicio.ventana_horaria.return_value = (time(8, 0), time(10, 0))
        servicio.pide_hora = True
        servicio.paso_hora_minutos = 30
        servicio.capacidad_maxima = 3

        limites = limites_de_servicio(servicio)
        self.assertEqual(limites['horas'], ['08:00', '08:30', '09:00', '09:30', '10:00'])

    def test_sin_consultas_a_base_de_datos(self):
        """limites_de_servicio y mapa_limites no ejecutan ninguna consulta a la base de datos."""
        servicio = MagicMock()
        servicio.pk = 60
        servicio.hora_apertura = time(6, 0)
        servicio.hora_cierre = time(8, 0)
        servicio.ventana_horaria.return_value = (time(6, 0), time(8, 0))
        servicio.pide_hora = True
        servicio.paso_hora_minutos = 15
        servicio.capacidad_maxima = 5

        with self.assertNumQueries(0):
            limites = limites_de_servicio(servicio)
            mapa = mapa_limites([servicio], prefijo='servicio:')

        self.assertIn('servicio:60', mapa)
        self.assertEqual(mapa['servicio:60'], limites)

    def test_mapa_limites_serializable_a_json(self):
        """mapa_limites genera una estructura serializable a JSON con o sin prefijo."""
        s1 = MagicMock()
        s1.pk = 1
        s1.ventana_horaria.return_value = (time(5, 0), time(7, 0))
        s1.pide_hora = True
        s1.paso_hora_minutos = 15
        s1.capacidad_maxima = 3

        s2 = MagicMock()
        s2.pk = 2
        s2.ventana_horaria.return_value = None
        s2.pide_hora = False
        s2.capacidad_maxima = 6

        mapa_con_prefijo = mapa_limites([s1, s2], prefijo='servicio:')
        serializado_prefijo = json.dumps(mapa_con_prefijo)
        self.assertIn('"servicio:1"', serializado_prefijo)
        self.assertIn('"servicio:2"', serializado_prefijo)

        mapa_sin_prefijo = mapa_limites([s1, s2])
        serializado_sin_prefijo = json.dumps(mapa_sin_prefijo)
        self.assertIn('"1"', serializado_sin_prefijo)
        self.assertIn('"2"', serializado_sin_prefijo)
