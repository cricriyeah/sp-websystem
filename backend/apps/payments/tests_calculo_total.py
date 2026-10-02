"""Cálculo único del precio base: total = base + max(0, personas - personas_base) x extra."""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.payments.pricing import calcular_total


class CalcularTotalTests(SimpleTestCase):
    def total(self, **kw):
        datos = dict(
            estrategia='por_grupo', base=Decimal('4500'), personas=3, personas_base=3, extra=Decimal('500'),
        )
        datos.update(kw)
        return calcular_total(**datos)

    def test_por_grupo_dentro_de_las_personas_base_es_el_precio_base(self):
        for personas in (1, 2, 3):
            self.assertEqual(self.total(personas=personas), Decimal('4500.00'))

    def test_por_grupo_cobra_extra_por_cada_persona_sobre_la_base(self):
        self.assertEqual(self.total(personas=4), Decimal('5000.00'))
        self.assertEqual(self.total(personas=5), Decimal('5500.00'))

    def test_por_grupo_sin_extra_es_precio_fijo(self):
        self.assertEqual(self.total(personas=9, extra=Decimal('0')), Decimal('4500.00'))

    def test_por_persona_multiplica_e_ignora_base_y_extra(self):
        self.assertEqual(
            self.total(estrategia='por_persona', base=Decimal('800'), personas=4, personas_base=1, extra=Decimal('99')),
            Decimal('3200.00'),
        )

    def test_personas_menores_a_uno_cuentan_como_una(self):
        self.assertEqual(self.total(estrategia='por_persona', base=Decimal('800'), personas=0), Decimal('800.00'))

    def test_cuantiza_a_centavos(self):
        self.assertEqual(self.total(base=Decimal('10.005'), personas=1), Decimal('10.01'))

    def test_estrategia_desconocida_falla(self):
        with self.assertRaises(ValueError):
            self.total(estrategia='por_ruta')

    def test_exige_argumentos_por_nombre(self):
        with self.assertRaises(TypeError):
            calcular_total('por_grupo', Decimal('1'), 1, 1, Decimal('0'))
