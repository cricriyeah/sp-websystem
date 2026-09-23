"""Campos y reglas de configuración de un paquete."""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.fleet.paquete_reglas import Componente, errores_de_paquete, hay_conflicto_anticipo
from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class CamposDePaqueteServicioTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa CP', slug='empresa-cp')
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca-cp', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='P', slug='p-cp',
            precio_ancla=Decimal('5000.00'),
        )

    def test_defaults_de_estancia_y_personas(self):
        ps = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio, orden=1)
        self.assertEqual(ps.dia_estancia, 1)
        self.assertIsNone(ps.noches)
        self.assertEqual(ps.personas_incluidas, 2)


def _c(nombre='S', empresa=1, estrategia='por_recurso_dia', noches=None, dia=1, personas=2, tope=5):
    return Componente(
        servicio_nombre=nombre, empresa_id=empresa, estrategia_cupo=estrategia,
        noches=noches, dia_estancia=dia, personas_incluidas=personas, tope_personas=tope,
    )


class ReglasDePaqueteTests(SimpleTestCase):
    def errores(self, componentes, permite_anticipo=False):
        return errores_de_paquete(permite_anticipo=permite_anticipo, componentes=componentes)

    def test_paquete_valido_de_una_empresa_con_hospedaje(self):
        componentes = [
            _c('Pesca', dia=2),
            _c('Hotel', estrategia='por_noche', noches=3, dia=1, tope=None),
        ]
        self.assertEqual(self.errores(componentes, permite_anticipo=True), [])

    def test_cruza_empresa_no_admite_anticipo(self):
        errores = self.errores([_c(empresa=1), _c('Traslado', empresa=2, estrategia='bajo_demanda')], permite_anticipo=True)
        self.assertTrue(any('anticipo' in e for e in errores))
        self.assertTrue(hay_conflicto_anticipo(permite_anticipo=True, empresas_ids={1, 2}))
        self.assertFalse(hay_conflicto_anticipo(permite_anticipo=True, empresas_ids={1}))
        self.assertFalse(hay_conflicto_anticipo(permite_anticipo=False, empresas_ids={1, 2}))

    def test_cruza_empresa_solo_un_servicio_por_empresa(self):
        errores = self.errores([_c('A', empresa=1), _c('B', empresa=1), _c('T', empresa=2, estrategia='bajo_demanda')])
        self.assertTrue(any('un servicio por empresa' in e for e in errores))

    def test_solo_un_hospedaje(self):
        errores = self.errores([
            _c('H1', estrategia='por_noche', noches=2, tope=None),
            _c('H2', estrategia='por_noche', noches=2, tope=None),
        ])
        self.assertTrue(any('un hospedaje' in e for e in errores))

    def test_hospedaje_exige_noches_y_los_demas_no_las_admiten(self):
        self.assertTrue(any('noches' in e for e in self.errores([_c('H', estrategia='por_noche', noches=None, tope=None)])))
        self.assertTrue(any('noches' in e for e in self.errores([_c('Pesca', noches=2)])))

    def test_dia_de_estancia(self):
        # Sin hospedaje todo cae el día 1.
        self.assertTrue(any('día' in e for e in self.errores([_c(dia=2)])))
        # Con hospedaje de 2 noches el día 3 (salida) no vale; el 2 sí.
        hotel = _c('Hotel', estrategia='por_noche', noches=2, dia=1, tope=None)
        self.assertTrue(any('día' in e for e in self.errores([_c(dia=3), hotel])))
        self.assertEqual(self.errores([_c(dia=2), hotel]), [])
        # El hospedaje empieza el día 1.
        self.assertTrue(any('día' in e for e in self.errores([_c('Hotel', estrategia='por_noche', noches=2, dia=2, tope=None)])))

    def test_las_actividades_comparten_dia(self):
        hotel = _c('Hotel', estrategia='por_noche', noches=3, dia=1, tope=None)
        errores = self.errores([_c('A', dia=1), _c('B', dia=2), hotel])
        self.assertTrue(any('mismo día' in e for e in errores))

    def test_personas_incluidas_dentro_del_tope(self):
        self.assertTrue(any('personas' in e for e in self.errores([_c(personas=0)])))
        self.assertTrue(any('personas' in e for e in self.errores([_c(personas=6, tope=5)])))
        self.assertEqual(self.errores([_c(personas=14, tope=None)]), [])
