from datetime import date, timedelta
from unittest import TestCase

from apps.bookings.cupo.nucleo import (
    MODO_COMPARTIDO,
    MODO_EXCLUSIVO,
    MOTIVO_LLENO,
    MOTIVO_SIN_LUGAR,
    MOTIVO_SIN_PANGA,
    caben,
    caben_compartido,
    elegir_recursos,
    motivo_sin_lugar,
    ocupacion_por_rango,
    validar_rango,
)


class CupoNucleoPuroTests(TestCase):
    """Pruebas unitarias de las funciones puras del algoritmo de cupo."""

    def test_caben_algoritmo_exclusivo(self):
        # Mismo número de grupos que recursos, caben exactamente
        self.assertTrue(caben([4, 3, 2], [5, 4, 3]))
        self.assertTrue(caben([4], [4]))

        # Más grupos que recursos
        self.assertFalse(caben([2, 2], [5]))

        # El caso clásico de pesca: un grupo de 4 personas con 2 pangas de 3 personas
        # Aunque hay 6 plazas libres en total, no hay ninguna panga individual para 4
        self.assertFalse(caben([4], [3, 3]))

        # Emparejamiento por orden descendente
        self.assertTrue(caben([5, 3], [5, 3]))
        self.assertFalse(caben([5, 4], [5, 3]))

    def test_caben_compartido(self):
        # Grupos suman 2 + 3 = 5 <= 8
        self.assertTrue(caben_compartido([2, 3], 8))
        # Grupos suman 5 + 4 = 9 > 8
        self.assertFalse(caben_compartido([5, 4], 8))
        # Grupos vacíos
        self.assertTrue(caben_compartido([], 10))

    def test_motivo_sin_lugar_modo_exclusivo(self):
        capacidades = [5, 5, 3, 3]
        tope = 3

        # 1. Cabe perfectamente
        self.assertIsNone(motivo_sin_lugar(personas=4, grupos=[3], capacidades=capacidades, tope=tope))

        # 2. Se alcanza el tope de viajes (tope=3, ya hay 3 vendidos)
        self.assertEqual(
            motivo_sin_lugar(personas=2, grupos=[3, 3, 3], capacidades=capacidades, tope=tope),
            MOTIVO_LLENO,
        )

        # 3. Hay tope (hay 1 vendido de 3), pero el grupo no cabe en las pangas restantes
        # Ya hay una panga de 5 ocupada por el grupo de 5. Queda [5, 3, 3].
        # Si llega un grupo de 6, no hay panga donde quepa
        self.assertEqual(
            motivo_sin_lugar(personas=6, grupos=[5], capacidades=capacidades, tope=tope),
            MOTIVO_SIN_PANGA,
        )

        # Si ya se ocuparon las dos de 5 (grupos [4, 4]), y llega un grupo de 4,
        # solo quedan las de 3: sin_panga
        self.assertEqual(
            motivo_sin_lugar(personas=4, grupos=[4, 4], capacidades=capacidades, tope=tope),
            MOTIVO_SIN_PANGA,
        )

    def test_motivo_sin_lugar_modo_compartido(self):
        # Modo compartido: panga/vehículo con capacidad 10
        capacidades = [10]
        tope = 5  # máximo 5 reservas independientes

        # 1. Caben personas
        self.assertIsNone(
            motivo_sin_lugar(
                personas=3, grupos=[2, 2], capacidades=capacidades, tope=tope, modo=MODO_COMPARTIDO
            )
        )

        # 2. Excede tope de reservas
        self.assertEqual(
            motivo_sin_lugar(
                personas=1, grupos=[1, 1, 1, 1, 1], capacidades=capacidades, tope=tope, modo=MODO_COMPARTIDO
            ),
            MOTIVO_LLENO,
        )

        # 3. Excede capacidad acumulada (ya hay 2+3+3 = 8, llegan 3 personas -> 11 > 10)
        self.assertEqual(
            motivo_sin_lugar(
                personas=3, grupos=[2, 3, 3], capacidades=capacidades, tope=tope, modo=MODO_COMPARTIDO
            ),
            MOTIVO_SIN_LUGAR,
        )

    def test_motivo_sin_lugar_modo_invalido(self):
        with self.assertRaises(ValueError):
            motivo_sin_lugar(personas=2, grupos=[], capacidades=[5], tope=5, modo='inexistente')

    def test_ocupacion_por_rango(self):
        dia1 = date(2026, 9, 10)
        dia2 = date(2026, 9, 11)
        dia3 = date(2026, 9, 12)
        fechas = [dia1, dia2, dia3]

        grupos = {
            dia1: [],          # libre
            dia2: [4, 4],      # ocupan las de 5
            dia3: [3, 3, 3],   # lleno por tope=3
        }
        capacidades = {
            dia1: [5, 5, 3],
            dia2: [5, 5, 3],
            dia3: [5, 5, 3],
        }
        topes = {
            dia1: 3,
            dia2: 3,
            dia3: 3,
        }

        # Buscamos cupo para grupo de 4 personas
        resultado = ocupacion_por_rango(fechas, grupos, capacidades, topes, personas=4, modo=MODO_EXCLUSIVO)

        self.assertIsNone(resultado[dia1])
        self.assertEqual(resultado[dia2], MOTIVO_SIN_PANGA)
        self.assertEqual(resultado[dia3], MOTIVO_LLENO)

    def test_ocupacion_por_rango_sin_tope_no_marca_lleno(self):
        f = date(2026, 9, 10)
        resultado = ocupacion_por_rango(
            fechas=[f],
            grupos_por_fecha={f: [3]},
            capacidades_por_fecha={f: [5, 3]},
            topes_por_fecha={},
            personas=3,
            modo=MODO_EXCLUSIVO,
        )
        self.assertEqual(resultado, {f: None})

    def test_validar_rango(self):
        self.assertIsNone(validar_rango(date(2026, 1, 1), date(2026, 1, 3)))
        self.assertIsInstance(validar_rango(date(2026, 1, 3), date(2026, 1, 3)), str)
        self.assertIsInstance(validar_rango(date(2026, 1, 3), date(2026, 1, 1)), str)
        self.assertIsNone(validar_rango(None, date(2026, 1, 1)))

    def test_elegir_recursos_un_recurso_que_cabe(self):
        # 1 recurso con capacidad suficiente
        libres = [(10, 2), (20, 4), (30, 6)]
        # Para 3 personas y cantidad 1, debe elegir 20 (capacidad 4, menos desperdicio que 30)
        self.assertEqual(elegir_recursos(libres, personas=3, cantidad=1), [20])

    def test_elegir_recursos_prefiere_mas_chico_que_alcanza(self):
        # Prefiere el que minimiza desperdicio
        libres = [(1, 2), (2, 5), (3, 3)]
        # Para 2 personas, elige 1 (capacidad 2, desperdicio 0)
        self.assertEqual(elegir_recursos(libres, personas=2, cantidad=1), [1])
        # Para 3 personas, elige 3 (capacidad 3, desperdicio 0)
        self.assertEqual(elegir_recursos(libres, personas=3, cantidad=1), [3])

    def test_elegir_recursos_combinacion_de_dos(self):
        # 2 recursos necesarios
        libres = [(1, 2), (2, 2), (3, 5)]
        # Para 4 personas con 2 habitaciones, elige [1, 2] (2+2=4, desperdicio 0)
        self.assertEqual(elegir_recursos(libres, personas=4, cantidad=2), [1, 2])
        # Para 6 personas con 2 habitaciones, elige [1, 3] (2+5=7, desperdicio 1 frente a 2+5=7)
        resultado = elegir_recursos(libres, personas=6, cantidad=2)
        self.assertIn(resultado, ([1, 3], [2, 3]))

    def test_elegir_recursos_imposible_retorna_none(self):
        libres = [(1, 2), (2, 2)]
        # Excede capacidad total
        self.assertIsNone(elegir_recursos(libres, personas=5, cantidad=2))
        # Recursos disponibles insuficientes para la cantidad pedida
        self.assertIsNone(elegir_recursos(libres, personas=1, cantidad=3))

    def test_elegir_recursos_tie_breaker_determinista(self):
        # Dos recursos con misma capacidad y mismo desperdicio
        libres = [(5, 4), (2, 4)]
        self.assertEqual(elegir_recursos(libres, personas=3, cantidad=1), [2])

