"""Paso 2 de la recuperacion: confirmar el codigo y poner la contrasena nueva (`servicio.confirmar_codigo`)."""
import uuid
from datetime import timedelta
from unittest import mock

from axes.models import AccessAttempt
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import CodigoRecuperacion, EventoRecuperacion
from .seguridad import hash_correo
from .servicio import confirmar_codigo, ip_excedida_confirmacion, solicitar_codigo
from .testing import HASH_RAPIDO, PASSWORD_NUEVA, PASSWORD_VIEJA, crear_usuario

IP = '203.0.113.9'


def _en(momento):
    return mock.patch('django.utils.timezone.now', return_value=momento)


@HASH_RAPIDO
class ConfirmarBase(TestCase):
    def setUp(self):
        parche = mock.patch('apps.cuentas.servicio.enviar_correo_codigo_recuperacion', return_value=True)
        self.enviar = parche.start()
        self.addCleanup(parche.stop)
        parche = mock.patch('apps.cuentas.servicio.enviar_correo_contrasena_cambiada', return_value=True)
        self.aviso = parche.start()
        self.addCleanup(parche.stop)

    def pedir_codigo(self, usuario):
        with self.captureOnCommitCallbacks(execute=True):
            solicitar_codigo(usuario.email, IP)
        return self.enviar.call_args.args[2].revelar()

    def confirmar(self, usuario_o_correo, codigo, password=PASSWORD_NUEVA, ip=IP):
        correo = getattr(usuario_o_correo, 'email', usuario_o_correo)
        with self.captureOnCommitCallbacks(execute=True):
            return confirmar_codigo(correo, codigo, password, ip)

    def codigo_malo(self, bueno):
        return f'{(int(bueno) + 1) % 10**6:06d}'

    def ultimo_evento(self):
        return EventoRecuperacion.objects.order_by('-pk').first()


class ConfirmarExitoTests(ConfirmarBase):
    def test_cambia_la_contrasena_consume_el_codigo_y_registra_el_exito(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)

        resultado = self.confirmar(usuario, codigo)

        self.assertTrue(resultado.exito)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(PASSWORD_NUEVA))
        self.assertFalse(usuario.check_password(PASSWORD_VIEJA))
        self.assertIsNotNone(CodigoRecuperacion.objects.get(usuario=usuario).consumido_en)
        evento = self.ultimo_evento()
        self.assertEqual((evento.tipo, evento.resultado, evento.usuario), (EventoRecuperacion.CONFIRMACION, 'exito', usuario))

    def test_no_se_puede_reutilizar_el_codigo(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        self.assertTrue(self.confirmar(usuario, codigo).exito)
        self.assertFalse(self.confirmar(usuario, codigo, password='Otra-Clave-8k3$zeta').exito)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(PASSWORD_NUEVA))

    @override_settings(RECUPERACION_AVISO_ADMIN=['dueno@ejemplo.com'])
    def test_manda_el_aviso_de_cambio_a_la_cuenta_y_la_copia_al_admin_despues_del_commit(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            confirmar_codigo(usuario.email, codigo, PASSWORD_NUEVA, IP)
        self.aviso.assert_not_called()
        self.assertEqual(len(pendientes), 1)
        pendientes[0]()
        self.aviso.assert_called_once_with(usuario.email, usuario.get_username(), ('dueno@ejemplo.com',))

    def test_tecleado_con_otras_mayusculas_tambien_funciona(self):
        usuario = crear_usuario(correo=f'Mix.{uuid.uuid4().hex[:6]}@Ejemplo.com')
        codigo = self.pedir_codigo(usuario)
        self.assertTrue(self.confirmar(f'  {usuario.email.upper()} ', codigo).exito)

    def test_no_inicia_sesion_por_si_solo(self):
        """El servicio no sabe de sesiones nuevas: solo mata las viejas (ver la vista para el cliente)."""
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        self.confirmar(usuario, codigo)
        self.assertEqual(Session.objects.count(), 0)


class ConfirmarFallosTests(ConfirmarBase):
    def test_codigo_incorrecto_suma_un_intento_y_da_el_error_generico(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        resultado = self.confirmar(usuario, self.codigo_malo(codigo))
        self.assertFalse(resultado.exito)
        self.assertEqual(resultado.errores, ())
        fila = CodigoRecuperacion.objects.get(usuario=usuario)
        self.assertEqual(fila.intentos, 1)
        self.assertIsNone(fila.consumido_en)
        self.assertEqual(self.ultimo_evento().resultado, 'codigo_incorrecto')
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(PASSWORD_VIEJA))

    def test_tras_cinco_fallos_el_sexto_intento_con_el_codigo_correcto_tambien_falla(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        for _ in range(5):
            self.assertFalse(self.confirmar(usuario, self.codigo_malo(codigo)).exito)
        self.assertFalse(self.confirmar(usuario, codigo).exito)
        self.assertEqual(self.ultimo_evento().resultado, 'agotado')
        self.assertEqual(CodigoRecuperacion.objects.get(usuario=usuario).intentos, 5)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(PASSWORD_VIEJA))

    def test_vencido_falla(self):
        usuario = crear_usuario()
        inicio = timezone.now()
        with _en(inicio):
            codigo = self.pedir_codigo(usuario)
        with _en(inicio + timedelta(minutes=10, seconds=1)):
            self.assertFalse(self.confirmar(usuario, codigo).exito)
        self.assertEqual(self.ultimo_evento().resultado, 'vencido')

    def test_justo_antes_de_vencer_todavia_sirve(self):
        usuario = crear_usuario()
        inicio = timezone.now()
        with _en(inicio):
            codigo = self.pedir_codigo(usuario)
        with _en(inicio + timedelta(minutes=9, seconds=59)):
            self.assertTrue(self.confirmar(usuario, codigo).exito)

    def test_el_codigo_de_otra_cuenta_no_sirve(self):
        duena = crear_usuario()
        otra = crear_usuario()
        codigo_de_la_duena = self.pedir_codigo(duena)
        codigo_de_la_otra = self.pedir_codigo(otra)
        if codigo_de_la_duena != codigo_de_la_otra:  # 1 en un millon que el generador repita
            self.assertFalse(self.confirmar(otra, codigo_de_la_duena).exito)
        otra.refresh_from_db()
        self.assertTrue(otra.check_password(PASSWORD_VIEJA))

    def test_sin_haber_pedido_codigo_falla(self):
        usuario = crear_usuario()
        self.assertFalse(self.confirmar(usuario, '123456').exito)
        self.assertEqual(self.ultimo_evento().resultado, 'sin_codigo')

    def test_cuenta_desactivada_despues_de_pedir_el_codigo_falla(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        usuario.is_active = False
        usuario.save()
        self.assertFalse(self.confirmar(usuario, codigo).exito)

    def test_contrasena_cambiada_por_otra_via_invalida_el_codigo(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        usuario.set_password('Cambiada-Por-Otro-7mR!')
        usuario.save()
        self.assertFalse(self.confirmar(usuario, codigo).exito)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password('Cambiada-Por-Otro-7mR!'))

    def test_dos_cuentas_con_el_mismo_correo_no_se_recuperan(self):
        a = crear_usuario(correo=f'dup-{uuid.uuid4().hex[:6]}@ejemplo.com')
        crear_usuario(correo=a.email.upper())
        self.assertFalse(self.confirmar(a.email, '123456').exito)


class ConfirmarContrasenaTests(ConfirmarBase):
    def test_contrasena_debil_da_error_de_validador_sin_gastar_intento(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        resultado = self.confirmar(usuario, codigo, password='12345678')
        self.assertFalse(resultado.exito)
        self.assertTrue(resultado.errores)
        self.assertEqual(CodigoRecuperacion.objects.get(usuario=usuario).intentos, 0)
        self.assertEqual(self.ultimo_evento().resultado, 'password_rechazada')
        # El mismo codigo sigue sirviendo con una contrasena buena.
        self.assertTrue(self.confirmar(usuario, codigo).exito)

    def test_contrasena_parecida_al_usuario_se_rechaza_con_el_usuario_real(self):
        usuario = crear_usuario(username=f'maria{uuid.uuid4().hex[:5]}')
        codigo = self.pedir_codigo(usuario)
        resultado = self.confirmar(usuario, codigo, password=f'{usuario.username}123')
        self.assertFalse(resultado.exito)
        self.assertTrue(resultado.errores)

    def test_el_error_de_validador_es_el_mismo_para_un_correo_que_no_existe(self):
        usuario = crear_usuario()
        self.pedir_codigo(usuario)
        existente = self.confirmar(usuario, '000000', password='12345678')
        inexistente = self.confirmar(f'nadie-{uuid.uuid4().hex[:8]}@ejemplo.com', '000000', password='12345678')
        self.assertEqual(existente, inexistente)

    def test_el_fallo_de_codigo_se_ve_igual_para_cuenta_real_e_inexistente(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        real = self.confirmar(usuario, self.codigo_malo(codigo))
        inexistente = self.confirmar(f'nadie-{uuid.uuid4().hex[:8]}@ejemplo.com', '123456')
        self.assertEqual(real, inexistente)


class ConfirmarEfectosTests(ConfirmarBase):
    def test_cierra_las_sesiones_de_esa_cuenta_y_deja_las_de_las_demas(self):
        usuario = crear_usuario()
        otra = crear_usuario()
        cliente_usuario, cliente_otra = Client(), Client()
        cliente_usuario.force_login(usuario)
        cliente_otra.force_login(otra)
        self.assertEqual(Session.objects.count(), 2)

        codigo = self.pedir_codigo(usuario)
        self.assertTrue(self.confirmar(usuario, codigo).exito)

        self.assertEqual(Session.objects.count(), 1)
        self.assertTrue(Session.objects.filter(session_key=cliente_otra.cookies['sessionid'].value).exists())
        self.assertFalse(Session.objects.filter(session_key=cliente_usuario.cookies['sessionid'].value).exists())

    def test_limpia_el_bloqueo_por_intentos_del_login(self):
        usuario = crear_usuario()
        for nombre in (usuario.get_username(), 'otro-usuario'):
            AccessAttempt.objects.create(
                username=nombre, ip_address='198.51.100.4', user_agent='', http_accept='', path_info='/admin/login/',
                attempt_time=timezone.now(), get_data='', post_data='', failures_since_start=5,
            )
        codigo = self.pedir_codigo(usuario)
        self.assertTrue(self.confirmar(usuario, codigo).exito)
        self.assertFalse(AccessAttempt.objects.filter(username=usuario.get_username()).exists())
        self.assertTrue(AccessAttempt.objects.filter(username='otro-usuario').exists())

    def test_un_fallo_no_toca_sesiones_ni_bloqueos(self):
        usuario = crear_usuario()
        Client().force_login(usuario)
        AccessAttempt.objects.create(
            username=usuario.get_username(), ip_address='198.51.100.4', user_agent='', http_accept='',
            path_info='/admin/login/', attempt_time=timezone.now(), get_data='', post_data='', failures_since_start=5,
        )
        codigo = self.pedir_codigo(usuario)
        self.confirmar(usuario, self.codigo_malo(codigo))
        self.assertEqual(Session.objects.count(), 1)
        self.assertEqual(AccessAttempt.objects.count(), 1)


class ConsumoCondicionalTests(ConfirmarBase):
    """El UPDATE condicional que hace seguro el conteo de intentos (corre tambien en SQLite)."""

    def test_el_codigo_ya_consumido_no_suma_intentos(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        self.confirmar(usuario, codigo)
        self.confirmar(usuario, self.codigo_malo(codigo))
        self.assertEqual(CodigoRecuperacion.objects.get(usuario=usuario).intentos, 1)

    def test_el_codigo_vencido_no_suma_intentos(self):
        usuario = crear_usuario()
        inicio = timezone.now()
        with _en(inicio):
            codigo = self.pedir_codigo(usuario)
        with _en(inicio + timedelta(minutes=11)):
            self.confirmar(usuario, self.codigo_malo(codigo))
        self.assertEqual(CodigoRecuperacion.objects.get(usuario=usuario).intentos, 0)

    def test_nunca_pasa_de_cinco_aunque_se_insista(self):
        usuario = crear_usuario()
        codigo = self.pedir_codigo(usuario)
        for _ in range(12):
            self.confirmar(usuario, self.codigo_malo(codigo))
        self.assertEqual(CodigoRecuperacion.objects.get(usuario=usuario).intentos, 5)


class LimiteDeFallosPorIpTests(ConfirmarBase):
    def fallo(self, n, ip=IP, resultado='codigo_incorrecto', hace=timedelta(minutes=5)):
        for i in range(n):
            EventoRecuperacion.objects.create(
                tipo=EventoRecuperacion.CONFIRMACION, resultado=resultado, correo_hash=hash_correo(f'x{i}@e.com'),
                ip=ip, creado_en=timezone.now() - hace,
            )

    def test_veinte_fallos_en_la_hora_exceden_y_diecinueve_no(self):
        self.fallo(19)
        self.assertFalse(ip_excedida_confirmacion(IP))
        self.fallo(1)
        self.assertTrue(ip_excedida_confirmacion(IP))

    def test_los_exitos_y_los_viejos_y_otras_ips_no_cuentan(self):
        self.fallo(30, resultado='exito')
        self.fallo(30, hace=timedelta(minutes=61))
        self.fallo(30, ip='198.51.100.7')
        self.assertFalse(ip_excedida_confirmacion(IP))

    def test_sin_ip_no_excede(self):
        self.assertFalse(ip_excedida_confirmacion(None))
