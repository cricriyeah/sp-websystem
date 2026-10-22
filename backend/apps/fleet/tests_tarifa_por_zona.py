"""La vuelta completa (redondo con aeropuerto y de actividad) se cobra por la zona del hotel; la recepción, no."""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.bookings.models import DetalleTransporte
from apps.fleet.enums import TipoTraslado, Zona
from apps.fleet.tarifa_transporte import TarifaTransporteNoConfigurada, resolver_tarifa_transporte


def tarifa(tipo, zona, precio, minimo=1, maximo=None):
    return SimpleNamespace(tipo_traslado=tipo, zona=zona, personas_min=minimo, personas_max=maximo, precio=Decimal(precio))


DLS = [
    tarifa(TipoTraslado.RECEPCION_AEROPUERTO, '', '2700'),
    tarifa(TipoTraslado.REDONDO_AEROPUERTO, Zona.CENTRO, '3500'),
    tarifa(TipoTraslado.REDONDO_AEROPUERTO, Zona.PERIFERIA, '3800'),
]


class TarifaPorZonaTests(SimpleTestCase):
    def test_la_vuelta_completa_cuesta_segun_la_zona(self):
        centro = resolver_tarifa_transporte(DLS, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona=Zona.CENTRO, personas=3)
        periferia = resolver_tarifa_transporte(DLS, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona=Zona.PERIFERIA, personas=3)
        self.assertEqual((centro.precio, periferia.precio), (Decimal('3500'), Decimal('3800')))

    def test_la_recepcion_tiene_precio_unico(self):
        t = resolver_tarifa_transporte(DLS, tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO, zona='', personas=6)
        self.assertEqual(t.precio, Decimal('2700'))

    def test_una_empresa_sin_zonas_cobra_igual_aunque_el_hotel_tenga_zona(self):
        sin_zonas = [tarifa(TipoTraslado.REDONDO_AEROPUERTO, '', '3500', 1, 4), tarifa(TipoTraslado.REDONDO_AEROPUERTO, '', '6500', 5)]
        t = resolver_tarifa_transporte(sin_zonas, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona=Zona.CENTRO, personas=2)
        self.assertEqual(t.precio, Decimal('3500'))

    def test_sin_zona_y_con_tarifas_por_zona_no_hay_tarifa(self):
        with self.assertRaises(TarifaTransporteNoConfigurada):
            resolver_tarifa_transporte(DLS, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona='', personas=2)


class ZonaEfectivaTests(SimpleTestCase):
    def detalle(self, tipo, punto_zona=None, direccion=''):
        d = DetalleTransporte(tipo_traslado=tipo, direccion_personalizada=direccion)
        if punto_zona:
            d.punto_encuentro_id = 1
            d.__dict__['_state'].fields_cache['punto_encuentro'] = SimpleNamespace(zona=punto_zona)
        return d

    def test_redondo_con_aeropuerto_usa_la_zona_del_hotel(self):
        self.assertEqual(self.detalle(TipoTraslado.REDONDO_AEROPUERTO, Zona.CENTRO).zona_efectiva(), Zona.CENTRO)

    def test_una_direccion_escrita_es_periferia(self):
        self.assertEqual(self.detalle(TipoTraslado.REDONDO_AEROPUERTO, direccion='Calle 5').zona_efectiva(), Zona.PERIFERIA)

    def test_la_recepcion_no_lleva_zona(self):
        self.assertEqual(self.detalle(TipoTraslado.RECEPCION_AEROPUERTO, Zona.CENTRO).zona_efectiva(), '')

    def test_sin_hotel_ni_direccion_el_aeropuerto_no_lleva_zona(self):
        self.assertEqual(self.detalle(TipoTraslado.REDONDO_AEROPUERTO).zona_efectiva(), '')
