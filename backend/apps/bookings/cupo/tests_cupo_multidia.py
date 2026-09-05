"""Pruebas unitarias de cupo multidía (PorNoche, BajoDemanda y traslapes semi-abiertos)."""

from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .estrategias import (
    BajoDemanda,
    DemandaCupo,
    ModoOcupacion,
    PorNoche,
)
from .nucleo import (
    MOTIVO_LLENO,
    MOTIVO_SIN_LUGAR,
    rango_traslapa,
    recursos_disponibles_en_rango,
)
from .registro import obtener_estrategia


class TraslapeSemiAbiertoTests(SimpleTestCase):
    """Pruebas para la función pura rango_traslapa con semántica semi-abierta [check-in, check-out)."""

    def test_fechas_contiguas_no_traslapan(self):
        """Check-out a las 11am y check-in a las 3pm el mismo día: [10, 12) y [12, 14) NO colisionan."""
        d1 = date(2026, 9, 10)
        d2 = date(2026, 9, 12)
        d3 = date(2026, 9, 14)
        self.assertFalse(rango_traslapa(d1, d2, d2, d3))
        self.assertFalse(rango_traslapa(d2, d3, d1, d2))

    def test_fechas_solapadas_traslapan(self):
        """[10, 13) y [12, 15) se traslapan en la noche del 12."""
        d10 = date(2026, 9, 10)
        d12 = date(2026, 9, 12)
        d13 = date(2026, 9, 13)
        d15 = date(2026, 9, 15)
        self.assertTrue(rango_traslapa(d10, d13, d12, d15))
        self.assertTrue(rango_traslapa(d12, d15, d10, d13))

    def test_rango_interior_traslapa(self):
        """Una estadía dentro de otra estadía más larga se traslapa."""
        d1 = date(2026, 9, 1)
        d5 = date(2026, 9, 5)
        d10 = date(2026, 9, 10)
        self.assertTrue(rango_traslapa(d1, d10, d5, d5 + timedelta(days=2)))

    def test_rango_invalido_devuelve_falso(self):
        """Si inicio >= fin en cualquiera de los dos rangos, no traslapa."""
        d1 = date(2026, 9, 10)
        d2 = date(2026, 9, 12)
        self.assertFalse(rango_traslapa(d2, d1, d1, d2))
        self.assertFalse(rango_traslapa(d1, d1, d1, d2))

    def test_recursos_disponibles_en_rango(self):
        """Filtra recursos ocupados y retorna sólo los libres."""
        d10 = date(2026, 9, 10)
        d12 = date(2026, 9, 12)
        d14 = date(2026, 9, 14)

        # Habitación 1: ocupada del 10 al 12 (sale el 12)
        # Habitación 2: ocupada del 12 al 15
        # Habitación 3: libre siempre
        recursos = [
            (1, 4, [(d10, d12)]),
            (2, 2, [(d12, date(2026, 9, 15))]),
            (3, 3, []),
        ]

        # Cliente busca del 12 al 14:
        # Habitación 1 está libre (salida fue el 12)
        # Habitación 2 está ocupada (entrada fue el 12)
        # Habitación 3 está libre
        libres = recursos_disponibles_en_rango(recursos, d12, d14)
        ids_libres = [r_id for r_id, _ in libres]
        self.assertEqual(ids_libres, [1, 3])


class EstrategiaPorNocheTests(SimpleTestCase):
    """Pruebas unitarias para la estrategia PorNoche."""

    def setUp(self):
        self.estrategia = PorNoche()

    def test_demanda_cupo_propiedades(self):
        """DemandaCupo calcula noches y fecha_salida correctamente."""
        demanda = DemandaCupo(
            fecha=date(2026, 9, 10),
            fecha_fin=date(2026, 9, 14),
            personas=3,
            cantidad_recursos=2,
        )
        self.assertEqual(demanda.noches, 4)
        self.assertEqual(demanda.fecha_salida, date(2026, 9, 14))

        # Sin fecha_fin: default 1 noche
        demanda_dia = DemandaCupo(fecha=date(2026, 9, 10), personas=2)
        self.assertEqual(demanda_dia.noches, 1)
        self.assertEqual(demanda_dia.fecha_salida, date(2026, 9, 11))

    def test_evaluar_ocupacion_disponible(self):
        """Hay recursos libres con capacidad suficiente para hospedar al grupo."""
        d10 = date(2026, 9, 10)
        d14 = date(2026, 9, 14)
        recursos = [
            (101, 4, []),  # Cabaña 1: cap 4, libre
            (102, 2, []),  # Cabaña 2: cap 2, libre
        ]
        demanda = DemandaCupo(
            fecha=d10,
            fecha_fin=d14,
            personas=3,
            cantidad_recursos=1,
        )
        res = self.estrategia.evaluar_ocupacion(demanda, recursos)
        self.assertTrue(res.disponible)
        self.assertIsNone(res.motivo)

    def test_evaluar_ocupacion_sin_suficientes_recursos(self):
        """Se solicitan 2 habitaciones pero sólo hay 1 disponible."""
        d10 = date(2026, 9, 10)
        d13 = date(2026, 9, 13)
        recursos = [
            (101, 4, [(d10, d13)]),  # Hab 101 ocupada
            (102, 4, []),            # Hab 102 libre
        ]
        demanda = DemandaCupo(
            fecha=d10,
            fecha_fin=d13,
            personas=4,
            cantidad_recursos=2,
        )
        res = self.estrategia.evaluar_ocupacion(demanda, recursos)
        self.assertFalse(res.disponible)
        self.assertEqual(res.motivo, MOTIVO_SIN_LUGAR)

    def test_evaluar_ocupacion_capacidad_insuficiente(self):
        """Hay 2 habitaciones libres, pero su capacidad sumada es menor que las personas."""
        d10 = date(2026, 9, 10)
        d12 = date(2026, 9, 12)
        recursos = [
            (101, 2, []),  # cap 2
            (102, 2, []),  # cap 2
        ]
        demanda = DemandaCupo(
            fecha=d10,
            fecha_fin=d12,
            personas=5,  # 5 personas no caben en 2+2=4
            cantidad_recursos=2,
        )
        res = self.estrategia.evaluar_ocupacion(demanda, recursos)
        self.assertFalse(res.disponible)
        self.assertEqual(res.motivo, MOTIVO_SIN_LUGAR)

    def test_validar_lanza_validation_error(self):
        """validar lanza ValidationError explicativo cuando no hay cupo."""
        demanda = DemandaCupo(
            fecha=date(2026, 9, 10),
            fecha_fin=date(2026, 9, 12),
            personas=4,
        )
        with self.assertRaises(ValidationError) as ctx:
            self.estrategia.validar(
                demanda=demanda,
                grupos=[2, 2],
                capacidades=[2, 2],
                tope=2,
            )
        self.assertIn('No hay espacio disponible para 4 personas', str(ctx.exception))

    def test_evaluar_rango(self):
        """evaluar_rango evalúa la disponibilidad para cada fecha."""
        d1 = date(2026, 9, 10)
        d2 = date(2026, 9, 11)
        res = self.estrategia.evaluar_rango(
            fechas=[d1, d2],
            grupos_por_fecha={d1: [2], d2: []},
            capacidades_por_fecha={d1: [4], d2: [4]},
            topes_por_fecha={d1: 1, d2: 1},
            personas=2,
        )
        self.assertFalse(res[d1].disponible)
        self.assertTrue(res[d2].disponible)


class EstrategiaBajoDemandaTests(SimpleTestCase):
    """Pruebas unitarias para la estrategia BajoDemanda."""

    def setUp(self):
        self.estrategia = BajoDemanda()

    def test_disponibilidad_inmediata_sin_tope(self):
        """Bajo demanda siempre está disponible si no hay tope estricto."""
        demanda = DemandaCupo(fecha=date(2026, 9, 10), personas=10)
        res = self.estrategia.evaluar(demanda, grupos=[1, 2, 3], capacidades=[], tope=0)
        self.assertTrue(res.disponible)

    def test_tope_suave_opcional(self):
        """Si se especifica un tope > 0, respeta el límite."""
        demanda = DemandaCupo(fecha=date(2026, 9, 10), personas=2)
        # Tope 2, ya hay 2 grupos -> lleno
        res = self.estrategia.evaluar(demanda, grupos=[1, 1], capacidades=[], tope=2)
        self.assertFalse(res.disponible)
        self.assertEqual(res.motivo, MOTIVO_LLENO)

    def test_evaluar_rango_siempre_disponible(self):
        """evaluar_rango devuelve disponible=True para todas las fechas solicitadas."""
        fechas = [date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)]
        res = self.estrategia.evaluar_rango(
            fechas=fechas,
            grupos_por_fecha={},
            capacidades_por_fecha={},
            topes_por_fecha={},
            personas=4,
        )
        for f in fechas:
            self.assertTrue(res[f].disponible)


class RegistroEstrategiasTests(SimpleTestCase):
    """Pruebas para el registro centralizado de estrategias de cupo."""

    def test_obtener_estrategia_por_noche(self):
        estrategia = obtener_estrategia('por_noche')
        self.assertIsInstance(estrategia, PorNoche)

    def test_obtener_estrategia_hospedaje(self):
        estrategia = obtener_estrategia('hospedaje')
        self.assertIsInstance(estrategia, PorNoche)

    def test_obtener_estrategia_bajo_demanda(self):
        estrategia = obtener_estrategia('bajo_demanda')
        self.assertIsInstance(estrategia, BajoDemanda)
