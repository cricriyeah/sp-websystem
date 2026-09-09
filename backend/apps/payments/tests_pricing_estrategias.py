"""Pruebas unitarias de las estrategias de precio puras (Pieza 3)."""

from decimal import Decimal
from django.test import SimpleTestCase

from apps.payments.pricing import monto_inicial
from apps.payments.estrategias_precio import (
    DemandaPrecio,
    EstrategiaPrecio,
    PorGrupo,
    PorNoche,
    PorPersona,
    PorRuta,
    TarifaFija,
    TipoEstrategiaPrecio,
    obtener_estrategia_precio,
    registrar_estrategia_precio,
    resolver_precio_base,
    resolver_precio_persona_extra,
    resolver_personas_incluidas,
)


class ConfigPrueba:
    """Mock sencillo de Servicio o Tarifa para pruebas de pricing."""
    def __init__(
        self,
        precio_base=Decimal('4500.00'),
        precio_base_usd=Decimal('260.00'),
        precio_persona_extra=Decimal('500.00'),
        precio_persona_extra_usd=Decimal('30.00'),
        personas_incluidas=3,
    ):
        self.precio_base = precio_base
        self.precio_base_usd = precio_base_usd
        self.precio_persona_extra = precio_persona_extra
        self.precio_persona_extra_usd = precio_persona_extra_usd
        self.personas_incluidas = personas_incluidas


class EstrategiasPrecioTests(SimpleTestCase):
    """Verifica el cálculo de precios bajo diferentes estrategias y monedas."""

    def setUp(self):
        self.config = ConfigPrueba()

    def test_por_grupo_mxn_dentro_del_cupo(self):
        estrategia = PorGrupo()
        demanda = DemandaPrecio(personas=3, moneda='MXN')
        total = estrategia.calcular_base(self.config, demanda)
        self.assertEqual(total, Decimal('4500.00'))

    def test_demanda_precio_campos_opcionales_traslado_y_compatibilidad(self):
        estrategia = PorGrupo()
        demanda = DemandaPrecio(personas=2, tipo_traslado='recepcion_aeropuerto', zona='centro')
        self.assertEqual(demanda.tipo_traslado, 'recepcion_aeropuerto')
        self.assertEqual(demanda.zona, 'centro')
        # PorGrupo ignora tipo_traslado y zona sin romperse
        total = estrategia.calcular_base(self.config, demanda)
        self.assertEqual(total, Decimal('4500.00'))

    def test_por_grupo_mxn_con_personas_extra(self):
        estrategia = PorGrupo()
        # 5 personas con 3 incluidas = 2 extras ($500 c/u) -> 4500 + 1000 = 5500
        demanda = DemandaPrecio(personas=5, moneda='MXN')
        total = estrategia.calcular_base(self.config, demanda)
        self.assertEqual(total, Decimal('5500.00'))

    def test_por_grupo_usd_con_personas_extra(self):
        estrategia = PorGrupo()
        # 4 personas = 1 extra ($30) -> 260 + 30 = 290
        demanda = DemandaPrecio(personas=4, moneda='USD')
        total = estrategia.calcular_base(self.config, demanda)
        self.assertEqual(total, Decimal('290.00'))

    def test_por_grupo_falla_si_falta_precio_persona_extra(self):
        config_sin_extra = ConfigPrueba(precio_persona_extra_usd=None)
        estrategia = PorGrupo()
        demanda = DemandaPrecio(personas=4, moneda='USD')
        with self.assertRaisesMessage(ValueError, 'No hay cargo por persona extra configurado en USD.'):
            estrategia.calcular_base(config_sin_extra, demanda)

    def test_por_grupo_con_personas_incluidas_personalizadas(self):
        config_custom = ConfigPrueba(personas_incluidas=5)
        estrategia = PorGrupo()
        # 5 personas = dentro del cupo
        self.assertEqual(
            estrategia.calcular_base(config_custom, DemandaPrecio(personas=5, moneda='MXN')),
            Decimal('4500.00'),
        )
        # 6 personas = 1 extra
        self.assertEqual(
            estrategia.calcular_base(config_custom, DemandaPrecio(personas=6, moneda='MXN')),
            Decimal('5000.00'),
        )

    def test_por_persona_mxn_y_usd(self):
        config = ConfigPrueba(precio_base=Decimal('800.00'), precio_base_usd=Decimal('45.00'))
        estrategia = PorPersona()

        demanda_mxn = DemandaPrecio(personas=4, moneda='MXN')
        self.assertEqual(estrategia.calcular_base(config, demanda_mxn), Decimal('3200.00'))

        demanda_usd = DemandaPrecio(personas=3, moneda='USD')
        self.assertEqual(estrategia.calcular_base(config, demanda_usd), Decimal('135.00'))

    def test_tarifa_fija_independiente_de_personas(self):
        config = ConfigPrueba(precio_base=Decimal('12000.00'), precio_base_usd=Decimal('700.00'))
        estrategia = TarifaFija()

        self.assertEqual(
            estrategia.calcular_base(config, DemandaPrecio(personas=1, moneda='MXN')),
            Decimal('12000.00'),
        )
        self.assertEqual(
            estrategia.calcular_base(config, DemandaPrecio(personas=10, moneda='MXN')),
            Decimal('12000.00'),
        )
        self.assertEqual(
            estrategia.calcular_base(config, DemandaPrecio(personas=8, moneda='USD')),
            Decimal('700.00'),
        )

    def test_por_noche_multiplica_noches(self):
        config = ConfigPrueba(precio_base=Decimal('2500.00'), precio_base_usd=Decimal('150.00'))
        estrategia = PorNoche()

        # 1 noche
        self.assertEqual(
            estrategia.calcular_base(config, DemandaPrecio(personas=2, noches=1, moneda='MXN')),
            Decimal('2500.00'),
        )
        # 3 noches
        self.assertEqual(
            estrategia.calcular_base(config, DemandaPrecio(personas=2, noches=3, moneda='MXN')),
            Decimal('7500.00'),
        )
        # 4 noches en USD
        self.assertEqual(
            estrategia.calcular_base(config, DemandaPrecio(personas=2, noches=4, moneda='USD')),
            Decimal('600.00'),
        )

    def test_falla_si_no_hay_precio_en_moneda(self):
        config = ConfigPrueba(precio_base_usd=None)
        estrategia = TarifaFija()
        with self.assertRaisesMessage(ValueError, 'No hay precio configurado en USD.'):
            estrategia.calcular_base(config, DemandaPrecio(personas=2, moneda='USD'))

    def test_soporta_diccionario_de_configuracion(self):
        config_dict = {
            'precio_base': Decimal('1000.00'),
            'precio_persona_extra': Decimal('200.00'),
            'personas_incluidas': 2,
        }
        estrategia = PorGrupo()
        total = estrategia.calcular_base(config_dict, DemandaPrecio(personas=4, moneda='MXN'))
        # 4 personas, 2 incluidas = 2 extras ($200 c/u) -> 1000 + 400 = 1400
        self.assertEqual(total, Decimal('1400.00'))

    def test_soporta_nombres_legacy_precio_y_precio_usd(self):
        # Compatibilidad con el modelo Tarifa que usa 'precio' en vez de 'precio_base'
        config_legacy = {
            'precio': Decimal('4500.00'),
            'precio_usd': Decimal('260.00'),
            'precio_persona_extra': Decimal('500.00'),
            'precio_persona_extra_usd': Decimal('30.00'),
        }
        estrategia = PorGrupo()
        self.assertEqual(
            estrategia.calcular_base(config_legacy, DemandaPrecio(personas=3, moneda='MXN')),
            Decimal('4500.00'),
        )
        self.assertEqual(
            estrategia.calcular_base(config_legacy, DemandaPrecio(personas=3, moneda='USD')),
            Decimal('260.00'),
        )

    def test_registro_de_estrategias(self):
        grupo = obtener_estrategia_precio('por_grupo')
        self.assertIsInstance(grupo, PorGrupo)

        persona = obtener_estrategia_precio('por_persona')
        self.assertIsInstance(persona, PorPersona)

        fija = obtener_estrategia_precio('tarifa_fija')
        self.assertIsInstance(fija, TarifaFija)

        noche = obtener_estrategia_precio('por_noche')
        self.assertIsInstance(noche, PorNoche)

        # Fallback para clave desconocida
        fallback = obtener_estrategia_precio('desconocida')
        self.assertIsInstance(fallback, PorGrupo)

    def test_registrar_estrategia_personalizada(self):
        class EstrategiaPrueba(EstrategiaPrecio):
            clave = 'prueba'
            def calcular_base(self, config, demanda):
                return Decimal('999.00')

        registrar_estrategia_precio('prueba', EstrategiaPrueba())
        obtenida = obtener_estrategia_precio('prueba')
        self.assertIsInstance(obtenida, EstrategiaPrueba)
        self.assertEqual(
            obtenida.calcular_base(self.config, DemandaPrecio(personas=1)),
            Decimal('999.00'),
        )


class MontoInicialTests(SimpleTestCase):
    def test_monto_inicial_con_porcentaje_anticipo(self):
        self.assertEqual(monto_inicial(Decimal('1000.00'), 'anticipo', porcentaje=50), Decimal('500.00'))

    def test_monto_inicial_completo_ignora_porcentaje(self):
        self.assertEqual(monto_inicial(Decimal('1000.00'), 'completo', porcentaje=50), Decimal('1000.00'))

    def test_monto_inicial_anticipo_default_30(self):
        self.assertEqual(monto_inicial(Decimal('1000.00'), 'anticipo'), Decimal('300.00'))


class TarifaFalsa:
    def __init__(self, tipo_traslado, zona='', personas_min=1, personas_max=None, precio=Decimal('1000.00'), precio_usd=None):
        self.tipo_traslado = tipo_traslado
        self.zona = zona
        self.personas_min = personas_min
        self.personas_max = personas_max
        self.precio = precio
        self.precio_usd = precio_usd

    def precio_en(self, moneda):
        return self.precio if (moneda or 'MXN').upper() == 'MXN' else self.precio_usd


class PorRutaTest(SimpleTestCase):
    def setUp(self):
        self.tarifas = [
            TarifaFalsa('redondo_aeropuerto', '', 1, 4, Decimal('4500.00'), Decimal('260.00')),
            TarifaFalsa('redondo_aeropuerto', '', 5, None, Decimal('6000.00'), Decimal('350.00')),
            TarifaFalsa('redondo_actividad', 'centro', 1, None, Decimal('1500.00'), None),
        ]
        self.config = {'tarifas_transporte_activas': self.tarifas}
        self.estrategia = PorRuta()

    def test_calcular_base_mxn_y_usd(self):
        demanda_mxn = DemandaPrecio(personas=3, moneda='MXN', tipo_traslado='redondo_aeropuerto')
        self.assertEqual(self.estrategia.calcular_base(self.config, demanda_mxn), Decimal('4500.00'))

        demanda_usd = DemandaPrecio(personas=6, moneda='USD', tipo_traslado='redondo_aeropuerto')
        self.assertEqual(self.estrategia.calcular_base(self.config, demanda_usd), Decimal('350.00'))

    def test_calcular_base_con_zona(self):
        demanda = DemandaPrecio(personas=2, tipo_traslado='redondo_actividad', zona='centro')
        self.assertEqual(self.estrategia.calcular_base(self.config, demanda), Decimal('1500.00'))

    def test_falla_si_falta_tarifas_en_config(self):
        demanda = DemandaPrecio(personas=2, tipo_traslado='redondo_aeropuerto')
        with self.assertRaisesMessage(ValueError, 'PorRuta necesita servicio_config.tarifas_transporte_activas'):
            self.estrategia.calcular_base({}, demanda)

    def test_falla_si_falta_tipo_traslado(self):
        demanda = DemandaPrecio(personas=2)
        with self.assertRaisesMessage(ValueError, 'PorRuta necesita demanda.tipo_traslado'):
            self.estrategia.calcular_base(self.config, demanda)

    def test_falla_si_no_hay_tarifa_para_la_demanda(self):
        demanda = DemandaPrecio(personas=2, tipo_traslado='recepcion_aeropuerto')
        with self.assertRaisesMessage(ValueError, 'No hay tarifa de transporte'):
            self.estrategia.calcular_base(self.config, demanda)

    def test_falla_si_moneda_no_tiene_precio(self):
        demanda = DemandaPrecio(personas=2, moneda='USD', tipo_traslado='redondo_actividad', zona='centro')
        with self.assertRaisesMessage(ValueError, 'La tarifa no tiene precio en USD.'):
            self.estrategia.calcular_base(self.config, demanda)

    def test_registro_contiene_por_ruta(self):
        obtenida = obtener_estrategia_precio('por_ruta')
        self.assertIsInstance(obtenida, PorRuta)

