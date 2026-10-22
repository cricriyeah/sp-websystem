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

    def test_produccion_crea_las_empresas_que_faltan_sin_llaves(self):
        with override_settings(DEBUG=False):
            sembrar(produccion=True)
        with scope.como_operador_plataforma():
            for slug, (nombre, slug_sede) in EMPRESAS_REALES.items():
                empresa = Empresa.objects.get(slug=slug)
                self.assertEqual((empresa.nombre, empresa.sede.slug), (nombre, slug_sede))
                self.assertEqual(empresa.stripe_secret_key, '')
                self.assertFalse(empresa.membresias.exists())

    def test_produccion_respeta_la_empresa_que_ya_existe(self):
        with scope.como_operador_plataforma():
            sede = Sede.objects.get(slug='la-paz')
            Empresa.objects.create(slug='transporte-la-paz', sede=sede, nombre='DLS a mi manera',
                                   stripe_secret_key='sk_test_mia')
        with override_settings(DEBUG=False):
            sembrar(produccion=True)
        with scope.como_operador_plataforma():
            dls = Empresa.objects.get(slug='transporte-la-paz')
            self.assertEqual((dls.nombre, dls.stripe_secret_key), ('DLS a mi manera', 'sk_test_mia'))

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


class DatosConfirmadosTests(TestCase):
    """Lo que el dueño confirmó el 2026-10-21 (precios sin IVA)."""

    def setUp(self):
        dar_de_alta_las_empresas()
        with override_settings(DEBUG=False):
            sembrar(produccion=True)

    def test_sal_y_sol_pesca_8_pangas_de_8_600_usd_y_75_usd_por_extra(self):
        with scope.como_operador_plataforma():
            sal = Empresa.objects.get(slug='sal-y-sol')
            pesca = Servicio.objects.get(empresa=sal, slug='pesca-deportiva')
            self.assertEqual((pesca.precio_base, pesca.precio_persona_extra, pesca.personas_incluidas, pesca.capacidad_maxima),
                             (10800, 1350, 2, 5))  # 600 y 75 USD a 18; 5 por viaje aunque la panga lleve 8
            self.assertEqual(Embarcacion.objects.filter(empresa=sal).count(), 8)
            self.assertEqual(set(Embarcacion.objects.filter(empresa=sal).values_list('capacidad_maxima', flat=True)), {8})
            licencia = pesca.servicio_personalizaciones.get(personalizacion__nombre='Licencia de pesca')
            self.assertEqual(licencia.precio, 300)

    def test_la_ventana_5_pangas_de_8_y_mosca_12000_para_3(self):
        with scope.como_operador_plataforma():
            ventana = Empresa.objects.get(slug='la-ventana-travel')
            mosca = Servicio.objects.get(empresa=ventana, slug='pesca-con-mosca')
            self.assertEqual((mosca.precio_base, mosca.capacidad_maxima, mosca.precio_persona_extra), (12000, 3, 0))
            self.assertEqual(Embarcacion.objects.filter(empresa=ventana).count(), 5)
            self.assertTrue(Servicio.objects.get(empresa=ventana, slug='hospedaje-la-ventana').solo_en_paquete)

    def test_dls_y_puerto_chale_quedan_apagados(self):
        with scope.como_operador_plataforma():
            dls = Empresa.objects.get(slug='transporte-la-paz')
            self.assertFalse(Servicio.objects.get(empresa=dls, slug='traslados-la-paz').activo)
            self.assertFalse(Sede.objects.get(slug='puerto-chale').activo)
