"""Operacion de la recuperacion: auditor de correos de las cuentas, limpieza de la bitacora y su admin."""
import uuid
from datetime import timedelta
from io import StringIO

from django.contrib import admin
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone

from .models import EventoRecuperacion
from .seguridad import hash_correo
from .testing import HASH_RAPIDO, crear_usuario


def _salida(comando, *args, **opciones):
    salida = StringIO()
    call_command(comando, *args, stdout=salida, **opciones)
    return salida.getvalue()


@HASH_RAPIDO
class AuditarCorreosCuentasTests(TestCase):
    def linea_de(self, salida, usuario):
        lineas = [linea for linea in salida.splitlines() if usuario.get_username() in linea]
        self.assertEqual(len(lineas), 1, salida)
        return lineas[0]

    def test_lista_cada_cuenta_con_su_estado_y_el_correo_enmascarado(self):
        con_correo = crear_usuario(correo=f'ana{uuid.uuid4().hex[:5]}@ejemplo.com')
        sin_correo = crear_usuario(correo='')
        duplicada_a = crear_usuario(correo=f'dup{uuid.uuid4().hex[:5]}@ejemplo.com')
        duplicada_b = crear_usuario(correo=duplicada_a.email.upper())
        superusuario = crear_usuario(is_superuser=True)

        salida = _salida('auditar_correos_cuentas')

        self.assertIn('OK', self.linea_de(salida, con_correo))
        self.assertIn('SIN CORREO', self.linea_de(salida, sin_correo))
        self.assertIn('DUPLICADO', self.linea_de(salida, duplicada_a))
        self.assertIn('DUPLICADO', self.linea_de(salida, duplicada_b))
        self.assertIn('superusuario=si', self.linea_de(salida, superusuario))
        self.assertIn('superusuario=no', self.linea_de(salida, con_correo))

    def test_nunca_imprime_una_direccion_completa(self):
        usuario = crear_usuario(correo=f'ana{uuid.uuid4().hex[:5]}@ejemplo.com')
        salida = _salida('auditar_correos_cuentas')
        self.assertNotIn(usuario.email, salida)
        self.assertIn(f'{usuario.email[0]}***@ejemplo.com', self.linea_de(salida, usuario))

    def test_resume_cuantas_faltan_y_cuantas_se_repiten(self):
        crear_usuario(correo='')
        crear_usuario(correo='')
        repetida = crear_usuario(correo=f'r{uuid.uuid4().hex[:5]}@ejemplo.com')
        crear_usuario(correo=repetida.email)
        salida = _salida('auditar_correos_cuentas')
        self.assertIn('2 sin correo', salida)
        self.assertIn('2 con correo repetido', salida)

    def test_no_modifica_nada(self):
        usuario = crear_usuario(correo='')
        _salida('auditar_correos_cuentas')
        usuario.refresh_from_db()
        self.assertEqual(usuario.email, '')


class LimpiarEventosRecuperacionTests(TestCase):
    def evento(self, dias):
        return EventoRecuperacion.objects.create(
            tipo=EventoRecuperacion.SOLICITUD, resultado='enviado', correo_hash=hash_correo('a@b.com'),
            creado_en=timezone.now() - timedelta(days=dias),
        )

    def test_borra_lo_mas_viejo_que_el_plazo_y_conserva_lo_reciente(self):
        viejo, reciente = self.evento(91), self.evento(89)
        salida = _salida('limpiar_eventos_recuperacion', dias=90)
        self.assertEqual(list(EventoRecuperacion.objects.values_list('pk', flat=True)), [reciente.pk])
        self.assertNotIn(viejo.pk, EventoRecuperacion.objects.values_list('pk', flat=True))
        self.assertIn('1 evento', salida)

    def test_el_plazo_por_defecto_es_90_dias(self):
        self.evento(91)
        self.evento(80)
        _salida('limpiar_eventos_recuperacion')
        self.assertEqual(EventoRecuperacion.objects.count(), 1)

    def test_un_plazo_no_positivo_se_rechaza_para_no_vaciar_la_tabla_por_error(self):
        self.evento(1)
        from django.core.management.base import CommandError
        for dias in (0, -5):
            with self.assertRaises(CommandError):
                _salida('limpiar_eventos_recuperacion', dias=dias)
        self.assertEqual(EventoRecuperacion.objects.count(), 1)


@HASH_RAPIDO
class EventoRecuperacionAdminTests(TestCase):
    def setUp(self):
        self.modelo_admin = admin.site._registry[EventoRecuperacion]
        self.operador = crear_usuario()
        self.operador.groups.add(Group.objects.get_or_create(name='OperadorPlataforma')[0])
        self.jefe = crear_usuario()

    def peticion(self, usuario):
        peticion = RequestFactory().get('/admin/')
        peticion.user = usuario
        return peticion

    def test_es_solo_lectura_para_todos_incluido_el_superusuario(self):
        superusuario = crear_usuario(is_superuser=True)
        for usuario in (self.operador, self.jefe, superusuario):
            peticion = self.peticion(usuario)
            self.assertFalse(self.modelo_admin.has_add_permission(peticion))
            self.assertFalse(self.modelo_admin.has_change_permission(peticion))
            self.assertFalse(self.modelo_admin.has_delete_permission(peticion))

    def test_solo_el_operador_de_plataforma_lo_ve(self):
        self.assertTrue(self.modelo_admin.has_view_permission(self.peticion(self.operador)))
        self.assertTrue(self.modelo_admin.has_module_permission(self.peticion(self.operador)))
        self.assertFalse(self.modelo_admin.has_view_permission(self.peticion(self.jefe)))
        self.assertFalse(self.modelo_admin.has_module_permission(self.peticion(self.jefe)))

    def test_el_codigo_no_tiene_admin(self):
        from .models import CodigoRecuperacion
        self.assertNotIn(CodigoRecuperacion, admin.site._registry)
