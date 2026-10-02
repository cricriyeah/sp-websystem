import json
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from apps.payments.moneda import convertir
from apps.payments.pricing import calcular_total


CASOS = json.loads((Path(__file__).resolve().parents[3] / 'shared' / 'precios_paridad.json').read_text())


class ParidadFrontendTests(SimpleTestCase):
    def test_conversiones(self):
        for caso in CASOS['conversiones']:
            with self.subTest(caso=caso):
                self.assertEqual(
                    convertir(Decimal(caso['monto']), caso['moneda'], Decimal(caso['tipo_cambio'])),
                    Decimal(caso['esperado']),
                )

    def test_paquetes(self):
        for caso in CASOS['paquetes']:
            with self.subTest(caso=caso):
                total = calcular_total(
                    estrategia=caso['estrategia'],
                    base=convertir(Decimal(caso['base']), caso['moneda'], Decimal(caso['tipo_cambio'])),
                    personas_base=caso['personas_base'],
                    extra=convertir(Decimal(caso['extra']), caso['moneda'], Decimal(caso['tipo_cambio'])),
                    personas=caso['personas'],
                )
                self.assertEqual(total, Decimal(caso['esperado']))
