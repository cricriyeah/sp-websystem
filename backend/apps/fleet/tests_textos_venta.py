"""Nombre y descripción en inglés (`nombre_en`, `descripcion_en`) y los textos de venta de la migración 0053.

La migración no pisa lo que se editó en el admin: el inglés solo se llena si está vacío y la descripción en
español solo se reemplaza si sigue siendo la del seed.
"""

from decimal import Decimal
from importlib import import_module

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fleet.models import Paquete, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede

textos = import_module('apps.fleet.migrations.0053_textos_venta_catalogo')


class TextosVentaTests(TestCase):
    def setUp(self):
        cache.clear()
        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede Txt', slug='sede-txt')
            self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa Txt', slug='empresa-txt')

    def _servicio(self, **extra):
        with scope.como_operador_plataforma():
            return Servicio.objects.create(
                empresa=self.empresa, nombre='Paseo', slug='paseo-txt', tipo_servicio='paseo',
                precio_base=Decimal('500.00'), pide_hora=False, **extra,
            )

    def _aplicar(self, objeto, campos):
        with scope.como_operador_plataforma():
            textos._aplicar(objeto, campos)
            objeto.refresh_from_db()

    def test_llena_lo_vacio_y_reemplaza_la_descripcion_del_seed(self):
        servicio = self._servicio(descripcion='Texto viejo del seed.')
        self._aplicar(servicio, dict(nombre_en='Tour', es='Nuevo', en='New', viejas=('Texto viejo del seed.',)))
        self.assertEqual((servicio.nombre_en, servicio.descripcion, servicio.descripcion_en), ('Tour', 'Nuevo', 'New'))

    def test_no_pisa_lo_editado_en_el_admin(self):
        servicio = self._servicio(descripcion='La escribió el dueño.', nombre_en='Mine', descripcion_en='Mine too')
        self._aplicar(servicio, dict(nombre_en='Tour', es='Nuevo', en='New', viejas=('Texto viejo del seed.',)))
        self.assertEqual(
            (servicio.nombre_en, servicio.descripcion, servicio.descripcion_en),
            ('Mine', 'La escribió el dueño.', 'Mine too'),
        )

    def test_la_api_publica_manda_los_dos_idiomas(self):
        self._servicio(nombre_en='Boat tour', descripcion='Paseo en lancha.', descripcion_en='A boat ride.')
        with scope.como_operador_plataforma():
            Paquete.objects.create(
                sede=self.sede, empresa_lider=self.empresa, nombre='Combo', nombre_en='Combo deal', slug='combo-txt',
                precio_ancla=Decimal('2000.00'), descripcion_en='Two things.',
            )
        cliente = APIClient()
        servicio = cliente.get('/api/sedes/sede-txt/servicios/').json()[0]
        self.assertEqual((servicio['nombre_en'], servicio['descripcion_en']), ('Boat tour', 'A boat ride.'))
        paquete = cliente.get('/api/sedes/sede-txt/paquetes/').json()[0]
        self.assertEqual((paquete['nombre_en'], paquete['descripcion_en']), ('Combo deal', 'Two things.'))
