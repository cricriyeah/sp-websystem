"""Retencion de 90 dias de las notificaciones (`manage.py limpiar_notificaciones`).

TransactionTestCase y SIN alcance abierto por la prueba, a proposito: el command corre en produccion con el rol de la
app y sin alcance, asi que si olvidara `como_operador_plataforma()` en Postgres vería cero filas y no borraria nada.
Con un alcance abierto por la prueba ese olvido pasaria en verde (R3 del ARCH).
"""
from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase
from django.utils import timezone

from . import scope
from .models import Empresa, LecturaNotificacion, Notificacion, Sede


class LimpiarNotificacionesTests(TransactionTestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='Sede limpieza', slug='sede-limpieza-notif')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='Limpieza A', slug='limpieza-notif-a')
        # Empresa pausada: su feed tambien se purga, o creceria sin fin.
        self.empresa_b = Empresa.objects.create(
            sede=sede, nombre='Limpieza B', slug='limpieza-notif-b', activo=False)
        self.usuario = User.objects.create_user('limpieza-notif-usuario', password='x')

    def _crear(self, empresa, texto, dias_de_antiguedad):
        with scope.con_empresa(empresa):
            n = Notificacion.objects.create(empresa=empresa, nivel=Notificacion.Nivel.EXITO, texto=texto)
            Notificacion.objects.filter(pk=n.pk).update(creado_en=timezone.now() - timedelta(days=dias_de_antiguedad))
        return n

    def _correr(self, *args):
        salida = StringIO()
        call_command('limpiar_notificaciones', *args, stdout=salida)
        return salida.getvalue()

    def _textos(self):
        with scope.como_operador_plataforma():
            return set(Notificacion.objects.values_list('texto', flat=True))

    def test_borra_las_viejas_de_todas_las_empresas_y_deja_las_recientes(self):
        self._crear(self.empresa_a, 'vieja A', 91)
        self._crear(self.empresa_b, 'vieja B pausada', 120)
        self._crear(self.empresa_a, 'reciente A', 89)
        self._crear(self.empresa_b, 'reciente B', 1)

        salida = self._correr()

        self.assertEqual(self._textos(), {'reciente A', 'reciente B'})
        self.assertIn('2 notificacion(es)', salida)

    def test_el_corte_se_puede_cambiar_con_dias(self):
        self._crear(self.empresa_a, 'de hace 10 dias', 10)
        self._crear(self.empresa_a, 'de hace 2 dias', 2)

        self._correr('--dias', '7')

        self.assertEqual(self._textos(), {'de hace 2 dias'})

    def test_las_lecturas_de_lo_borrado_caen_en_cascada(self):
        vieja = self._crear(self.empresa_a, 'vieja', 100)
        reciente = self._crear(self.empresa_a, 'reciente', 1)
        with scope.con_empresa(self.empresa_a):
            for n in (vieja, reciente):
                LecturaNotificacion.objects.create(empresa=self.empresa_a, notificacion=n, usuario=self.usuario)

        self._correr()

        with scope.como_operador_plataforma():
            self.assertEqual(
                list(LecturaNotificacion.objects.values_list('notificacion_id', flat=True)), [reciente.pk])

    def test_dias_menor_a_uno_se_rechaza_y_no_borra_nada(self):
        self._crear(self.empresa_a, 'vieja', 400)
        for dias in ('0', '-5'):
            with self.subTest(dias=dias), self.assertRaises(CommandError):
                self._correr('--dias', dias)

        self.assertEqual(self._textos(), {'vieja'})
