"""`incluye` de Servicio y Paquete: lista es/en de lo que trae cada producto (Task 9.0, paso 1b).

La tarjeta y la página de detalle la pintan; nunca se deriva de `descripcion`.
"""

from decimal import Decimal

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fleet.admin import PaqueteAdminForm, ServicioAdminForm
from apps.fleet.incluye import lineas_de_texto
from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class IncluyeModeloTests(TestCase):
    def setUp(self):
        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede Inc', slug='sede-inc')
            self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa Inc', slug='empresa-inc')

    def _servicio(self, **extra):
        with scope.como_operador_plataforma():
            return Servicio.objects.create(
                empresa=self.empresa, nombre=extra.pop('nombre', 'Paseo'), slug=extra.pop('slug', 'paseo-inc'),
                tipo_servicio='paseo', precio_base=Decimal('500.00'), pide_hora=False, **extra,
            )

    def _paquete(self, **extra):
        with scope.como_operador_plataforma():
            return Paquete.objects.create(
                sede=self.sede, empresa_lider=self.empresa, nombre='Combo', slug=extra.pop('slug', 'combo-inc'),
                precio_ancla=Decimal('2000.00'), **extra,
            )

    def _error_en_incluye(self, objeto):
        with self.assertRaises(ValidationError) as ctx:
            objeto.full_clean()
        self.assertIn('incluye', ctx.exception.message_dict)

    def test_vacio_por_defecto_y_valido(self):
        servicio = self._servicio()
        self.assertEqual(servicio.incluye, {})
        servicio.full_clean()
        self.assertEqual(self._paquete().incluye, {})

    def test_acepta_listas_es_y_en_y_recorta_espacios(self):
        servicio = self._servicio(incluye={'es': ['  Equipo de pesca ', 'Bebidas'], 'en': ['Fishing gear']})
        servicio.full_clean()
        self.assertEqual(servicio.incluye, {'es': ['Equipo de pesca', 'Bebidas'], 'en': ['Fishing gear']})

    def test_el_paquete_valida_igual(self):
        paquete = self._paquete(incluye={'es': ['Hospedaje'], 'en': ['Lodging']})
        paquete.full_clean()
        self._error_en_incluye(self._paquete(slug='combo-mal', incluye={'fr': ['Logement']}))

    def test_rechaza_lo_que_no_es_un_objeto(self):
        for i, valor in enumerate((['es'], 'texto', 5)):
            self._error_en_incluye(self._servicio(slug=f'mal-{i}', incluye=valor))

    def test_rechaza_claves_distintas_de_es_y_en(self):
        self._error_en_incluye(self._servicio(incluye={'es': ['ok'], 'fr': ['non']}))

    def test_cada_idioma_es_una_lista_de_textos_no_vacios(self):
        self._error_en_incluye(self._servicio(slug='a', incluye={'es': 'Equipo'}))
        self._error_en_incluye(self._servicio(slug='b', incluye={'es': ['Equipo', '   ']}))
        self._error_en_incluye(self._servicio(slug='c', incluye={'es': [5]}))

    def test_maximo_8_renglones_de_80_caracteres(self):
        self._servicio(slug='ocho', incluye={'es': [f'Renglón {i}' for i in range(8)]}).full_clean()
        self._error_en_incluye(self._servicio(slug='nueve', incluye={'es': [f'Renglón {i}' for i in range(9)]}))
        self._servicio(slug='ochenta', incluye={'es': ['a' * 80]}).full_clean()
        self._error_en_incluye(self._servicio(slug='largo', incluye={'es': ['a' * 81]}))


class IncluyeAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede IncApi', slug='sede-incapi')
            self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa IncApi', slug='empresa-incapi')
            self.servicio = Servicio.objects.create(
                empresa=self.empresa, nombre='Pesca', slug='pesca-incapi', tipo_servicio='pesca',
                precio_base=Decimal('1000.00'), incluye={'es': ['Equipo'], 'en': ['Gear']},
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.empresa, nombre='Combo', slug='combo-incapi',
                precio_ancla=Decimal('2000.00'), activo=True, incluye={'es': ['Todo'], 'en': ['Everything']},
            )
            PaqueteServicio.objects.create(
                paquete=self.paquete, servicio=self.servicio, orden=1, dia_estancia=1, personas_incluidas=1,
            )

    def test_el_detalle_del_servicio_lo_trae(self):
        datos = self.client.get('/api/empresa-incapi/servicios/pesca-incapi/').json()
        self.assertEqual(datos['incluye'], {'es': ['Equipo'], 'en': ['Gear']})

    def test_el_paquete_lo_trae_y_tambien_cada_servicio_asociado(self):
        datos = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/{self.paquete.slug}/').json()
        self.assertEqual(datos['incluye'], {'es': ['Todo'], 'en': ['Everything']})
        self.assertEqual(datos['servicios_asociados'][0]['servicio']['incluye'], {'es': ['Equipo'], 'en': ['Gear']})


class IncluyeAdminTests(TestCase):
    def test_un_renglon_por_linea_sin_vacios(self):
        self.assertEqual(lineas_de_texto('  Equipo \n\n Bebidas\r\n'), ['Equipo', 'Bebidas'])
        self.assertEqual(lineas_de_texto(''), [])

    def test_los_formularios_traen_un_cuadro_por_idioma_con_lo_guardado(self):
        servicio = Servicio(incluye={'es': ['Equipo', 'Bebidas'], 'en': ['Gear']})
        form = ServicioAdminForm(instance=servicio)
        self.assertEqual(form.fields['incluye_es'].initial, 'Equipo\nBebidas')
        self.assertEqual(form.fields['incluye_en'].initial, 'Gear')
        self.assertNotIn('incluye', form.fields)
        self.assertIn('incluye_es', PaqueteAdminForm(instance=Paquete()).fields)
