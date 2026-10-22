"""`seed_catalogo_real --produccion`: apto para la base real (sin DEBUG, sin empresas nuevas, sin lanchas DEMO)."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.fleet.management.commands.seed_catalogo_real import EMPRESAS_REALES
from apps.fleet.models import Embarcacion, Recurso, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.tenancy import scope


def sembrar(**opciones):
    call_command('seed_catalogo_real', stdout=StringIO(), **opciones)


def dar_de_alta_las_empresas():
    with scope.como_operador_plataforma():
        for slug, (nombre, slug_sede) in EMPRESAS_REALES.items():
            sede = Sede.objects.get(slug=slug_sede)
            Empresa.objects.get_or_create(slug=slug, defaults=dict(sede=sede, nombre=nombre))


class SembradoDeProduccionTests(TestCase):
    """El comando abre sus propios alcances de tenancy: no puede correr dentro del de operador de `OperadorTestCase`."""

    def test_sin_produccion_y_sin_debug_se_niega(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                sembrar()

    def test_produccion_exige_que_las_empresas_ya_existan(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError) as ctx:
                sembrar(produccion=True)
        self.assertIn('Alta de empresa', str(ctx.exception))
        with scope.como_operador_plataforma():
            self.assertFalse(Empresa.objects.filter(slug='piratas-adventures').exists())

    def test_produccion_no_se_combina_con_limpiar_demo(self):
        with self.assertRaises(CommandError):
            sembrar(produccion=True, limpiar_demo=True)

    def test_con_las_empresas_dadas_de_alta_siembra_sin_lanchas_ni_habitaciones_demo(self):
        dar_de_alta_las_empresas()
        with override_settings(DEBUG=False):
            sembrar(produccion=True)
        with scope.como_operador_plataforma():
            ventana = Empresa.objects.get(slug='la-ventana-travel')
            self.assertTrue(Servicio.objects.filter(empresa=ventana, slug='avistamiento-ballenas-orcas').exists())
            self.assertFalse(Servicio.objects.filter(empresa=ventana, slug__startswith='tour-isla-cerralvo').exists())
            nombres = set(Recurso.objects.filter(empresa=ventana).values_list('nombre', flat=True))
            self.assertFalse(any(n.startswith('DEMO') for n in nombres), nombres)
            self.assertEqual(sum(n.startswith('Estudio') for n in nombres), 6)
            self.assertEqual(Embarcacion.objects.filter(empresa=ventana).count(), 5)

    def test_sembrar_dos_veces_no_duplica_nada(self):
        dar_de_alta_las_empresas()
        with override_settings(DEBUG=False):
            sembrar(produccion=True)
            sembrar(produccion=True)
        with scope.como_operador_plataforma():
            ventana = Empresa.objects.get(slug='la-ventana-travel')
            self.assertEqual(Servicio.objects.filter(empresa=ventana, slug='pesca-con-mosca').count(), 1)
            self.assertEqual(Embarcacion.objects.filter(empresa=ventana).count(), 5)
