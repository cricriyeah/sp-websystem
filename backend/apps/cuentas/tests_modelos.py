"""Esqueleto de la recuperacion de contrasena: los dos modelos y su migracion.

Los modelos son **por usuario**, sin empresa: una cuenta de Django no pertenece a una empresa
(la membresia es otra tabla) y atar el codigo a una empresa invitaria a filtrarlo por RLS, que aqui
estorba (la persona que recupera su contrasena todavia no tiene alcance).
"""
from io import StringIO

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import models
from django.test import TestCase
from django.utils import timezone

from .models import CodigoRecuperacion, EventoRecuperacion

User = get_user_model()


class ModelosCuentasTests(TestCase):
    def test_la_app_esta_instalada_con_etiqueta_cuentas(self):
        self.assertEqual(apps.get_app_config('cuentas').name, 'apps.cuentas')

    def test_codigo_es_uno_por_usuario(self):
        campo = CodigoRecuperacion._meta.get_field('usuario')
        self.assertIsInstance(campo, models.OneToOneField)
        self.assertEqual(campo.remote_field.on_delete, models.CASCADE)

    def test_codigo_no_guarda_el_codigo_en_claro(self):
        nombres = {f.name for f in CodigoRecuperacion._meta.get_fields()}
        self.assertIn('codigo_hash', nombres)
        self.assertNotIn('codigo', nombres)
        self.assertEqual(CodigoRecuperacion._meta.get_field('codigo_hash').max_length, 64)

    def test_valores_por_defecto_del_codigo(self):
        usuario = User.objects.create_user('cuentas-modelo-1', password='x')
        ahora = timezone.now()
        codigo = CodigoRecuperacion.objects.create(usuario=usuario, codigo_hash='a' * 64, vence_en=ahora)
        codigo.refresh_from_db()
        self.assertEqual(codigo.intentos, 0)
        self.assertIsNone(codigo.consumido_en)
        self.assertIsNotNone(codigo.creado_en)

    def test_borrar_el_usuario_borra_su_codigo(self):
        usuario = User.objects.create_user('cuentas-modelo-2', password='x')
        CodigoRecuperacion.objects.create(usuario=usuario, codigo_hash='a' * 64, vence_en=timezone.now())
        usuario.delete()
        self.assertEqual(CodigoRecuperacion.objects.count(), 0)

    def test_evento_conserva_el_registro_si_se_borra_el_usuario(self):
        usuario = User.objects.create_user('cuentas-modelo-3', password='x')
        evento = EventoRecuperacion.objects.create(
            tipo=EventoRecuperacion.SOLICITUD, resultado='enviado', usuario=usuario, correo_hash='b' * 64,
        )
        usuario.delete()
        evento.refresh_from_db()
        self.assertIsNone(evento.usuario)

    def test_evento_admite_ip_vacia_y_no_tiene_campo_de_codigo(self):
        evento = EventoRecuperacion.objects.create(
            tipo=EventoRecuperacion.CONFIRMACION, resultado='exito', correo_hash='c' * 64,
        )
        self.assertIsNone(evento.ip)
        nombres = {f.name for f in EventoRecuperacion._meta.get_fields()}
        self.assertFalse({'codigo', 'codigo_hash', 'password'} & nombres)

    def test_ningun_modelo_de_la_app_tiene_campo_de_empresa(self):
        """Fuera del guardarrail de RLS a proposito (ver el docstring del modulo)."""
        for modelo in apps.get_app_config('cuentas').get_models():
            nombres = {f.name for f in modelo._meta.get_fields()}
            self.assertFalse(
                {n for n in nombres if n.startswith('empresa')}, f'{modelo.__name__} no debe llevar empresa'
            )

    def test_las_tablas_no_caen_bajo_los_prefijos_del_guardarrail_rls(self):
        for modelo in apps.get_app_config('cuentas').get_models():
            self.assertTrue(modelo._meta.db_table.startswith('cuentas_'))

    def test_no_hay_migraciones_pendientes(self):
        salida = StringIO()
        # `check=True` sale con SystemExit(1) si el modelo y la migracion difieren.
        call_command('makemigrations', 'cuentas', check=True, dry_run=True, stdout=salida)
