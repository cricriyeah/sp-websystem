"""Paso 1 de la recuperacion: pedir el codigo (`servicio.solicitar_codigo`).

Lo que mas pesa aqui es lo que NO debe pasar: que la respuesta distinga una cuenta que existe de una
que no, y que un solo correo, una sola IP o todo el sistema puedan disparar correos sin tope.
"""
import uuid
from datetime import timedelta
from unittest import mock

from django.forms.models import model_to_dict
from django.test import TestCase
from django.utils import timezone

from .models import CodigoRecuperacion, EventoRecuperacion
from .seguridad import Secreto, hash_codigo, hash_correo
from .servicio import ip_excedida_solicitud, solicitar_codigo
from .testing import HASH_RAPIDO, crear_usuario

IP = '203.0.113.9'


def _en(momento):
    """Congela `timezone.now()` (el servicio lo llama como atributo del modulo, en cada uso)."""
    return mock.patch('django.utils.timezone.now', return_value=momento)


@HASH_RAPIDO
class SolicitarCodigoBase(TestCase):
    def setUp(self):
        parche = mock.patch('apps.cuentas.servicio.enviar_correo_codigo_recuperacion', return_value=True)
        self.enviar = parche.start()
        self.addCleanup(parche.stop)

    def pedir(self, correo, ip=IP):
        # El envio sale en `on_commit`: se ejecuta aqui para poder inspeccionarlo.
        with self.captureOnCommitCallbacks(execute=True):
            return solicitar_codigo(correo, ip)

    def codigo_enviado(self):
        """El codigo en claro que recibio la funcion de correo (llega envuelto en `Secreto`)."""
        secreto = self.enviar.call_args.args[2]
        self.assertIsInstance(secreto, Secreto)
        return secreto.revelar()

    def evento(self, correo, resultado='enviado', hace=timedelta(minutes=10), ip=None, tipo=EventoRecuperacion.SOLICITUD):
        return EventoRecuperacion.objects.create(
            tipo=tipo, resultado=resultado, correo_hash=hash_correo(correo), ip=ip,
            creado_en=timezone.now() - hace,
        )

    def ultimo_evento(self):
        return EventoRecuperacion.objects.order_by('-pk').first()


class SolicitarCuentaValidaTests(SolicitarCodigoBase):
    def test_guarda_el_hash_vence_en_diez_minutos_y_envia_a_la_direccion_guardada(self):
        usuario = crear_usuario()
        ahora = timezone.now()
        with _en(ahora):
            self.assertIsNone(self.pedir(usuario.email))

        codigo = CodigoRecuperacion.objects.get(usuario=usuario)
        enviado = self.codigo_enviado()
        self.assertRegex(enviado, r'^\d{6}$')
        self.assertNotEqual(codigo.codigo_hash, enviado)
        self.assertEqual(codigo.codigo_hash, hash_codigo(usuario, enviado))
        self.assertEqual(codigo.vence_en, ahora + timedelta(minutes=10))
        self.assertEqual(codigo.intentos, 0)
        self.assertIsNone(codigo.consumido_en)
        self.enviar.assert_called_once()
        self.assertEqual(self.enviar.call_args.args[0], usuario.email)
        self.assertEqual(self.enviar.call_args.args[1], usuario.get_username())

    def test_se_envia_a_la_direccion_guardada_aunque_se_tecleo_con_otras_mayusculas(self):
        usuario = crear_usuario(correo=f'Ana.Ruiz.{uuid.uuid4().hex[:6]}@Example.com')
        self.pedir(f'  {usuario.email.upper()} ')
        self.assertEqual(self.enviar.call_args.args[0], usuario.email)
        self.assertTrue(CodigoRecuperacion.objects.filter(usuario=usuario).exists())

    def test_el_correo_sale_despues_del_commit_y_no_antes(self):
        usuario = crear_usuario()
        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            solicitar_codigo(usuario.email, IP)
        self.enviar.assert_not_called()
        self.assertEqual(len(pendientes), 1)

    def test_registra_el_evento_con_ip_y_usuario_pero_sin_el_codigo(self):
        usuario = crear_usuario()
        self.pedir(usuario.email)
        evento = self.ultimo_evento()
        self.assertEqual(evento.tipo, EventoRecuperacion.SOLICITUD)
        self.assertEqual(evento.resultado, 'enviado')
        self.assertEqual(evento.usuario, usuario)
        self.assertEqual(evento.ip, IP)
        self.assertEqual(evento.correo_hash, hash_correo(usuario.email))
        volcado = ' '.join(str(v) for v in model_to_dict(evento).values()) + evento.correo_hash
        self.assertNotIn(self.codigo_enviado(), volcado)
        self.assertNotIn(usuario.email, volcado)

    def test_ningun_campo_de_ningun_modelo_de_la_app_lleva_el_codigo(self):
        usuario = crear_usuario()
        self.pedir(usuario.email)
        codigo = self.codigo_enviado()
        fila = CodigoRecuperacion.objects.get(usuario=usuario)
        self.assertNotIn(codigo, ' '.join(str(v) for v in model_to_dict(fila).values()))
        for evento in EventoRecuperacion.objects.all():
            self.assertNotIn(codigo, ' '.join(str(v) for v in model_to_dict(evento).values()))

    def test_ip_invalida_o_ausente_no_rompe_y_se_guarda_vacia(self):
        usuario = crear_usuario()
        self.pedir(usuario.email, ip=None)
        self.assertIsNone(self.ultimo_evento().ip)
        otro = crear_usuario()
        self.pedir(otro.email, ip='esto-no-es-una-ip')
        self.assertIsNone(self.ultimo_evento().ip)
        self.assertEqual(self.enviar.call_count, 2)


class SolicitarSinEnvioTests(SolicitarCodigoBase):
    """Cinco motivos distintos para no enviar; hacia afuera tienen que verse exactamente igual."""

    def casos(self):
        inactiva = crear_usuario(is_active=False)
        inutilizable = crear_usuario(password=None)
        duplicada_a = crear_usuario(correo=f'dup-{uuid.uuid4().hex[:6]}@example.com')
        crear_usuario(correo=duplicada_a.email.upper())
        sin_correo = crear_usuario(correo='')
        return [
            ('sin_cuenta', f'nadie-{uuid.uuid4().hex[:8]}@example.com'),
            ('inactiva', inactiva.email),
            ('contrasena_inutilizable', inutilizable.email),
            ('ambigua', duplicada_a.email),
            ('sin_correo', ''),
            ('sin_correo', '   '),
            ('sin_correo', sin_correo.email),
        ]

    def test_ningun_caso_crea_codigo_ni_envia_ni_devuelve_nada_distinto(self):
        for motivo, correo in self.casos():
            with self.subTest(motivo=motivo, correo=correo):
                self.assertIsNone(self.pedir(correo))
        self.assertEqual(CodigoRecuperacion.objects.count(), 0)
        self.enviar.assert_not_called()

    def test_cada_caso_deja_su_motivo_en_la_bitacora(self):
        for motivo, correo in self.casos():
            with self.subTest(motivo=motivo, correo=correo):
                self.pedir(correo)
                self.assertEqual(self.ultimo_evento().resultado, motivo)

    def test_un_correo_vacio_no_se_cruza_con_cuentas_que_tampoco_tienen_correo(self):
        crear_usuario(correo='')
        self.pedir('')
        self.assertEqual(CodigoRecuperacion.objects.count(), 0)
        self.enviar.assert_not_called()

    def test_la_cuenta_inexistente_hace_el_mismo_hmac_de_relleno(self):
        """El trabajo criptografico no debe ser lo que delate si la cuenta existe."""
        with mock.patch('apps.cuentas.servicio.hash_codigo', wraps=hash_codigo) as hash_mock:
            self.pedir(f'nadie-{uuid.uuid4().hex[:8]}@example.com')
        hash_mock.assert_called_once()

        usuario = crear_usuario()
        with mock.patch('apps.cuentas.servicio.hash_codigo', wraps=hash_codigo) as hash_mock:
            self.pedir(usuario.email)
        hash_mock.assert_called_once()


class SolicitarLimitesTests(SolicitarCodigoBase):
    def test_segunda_peticion_antes_de_60_segundos_no_sobrescribe(self):
        usuario = crear_usuario()
        inicio = timezone.now()
        with _en(inicio):
            self.pedir(usuario.email)
        primero = CodigoRecuperacion.objects.get(usuario=usuario).codigo_hash

        with _en(inicio + timedelta(seconds=30)):
            self.pedir(usuario.email)

        self.assertEqual(CodigoRecuperacion.objects.get(usuario=usuario).codigo_hash, primero)
        self.assertEqual(self.enviar.call_count, 1)
        self.assertEqual(self.ultimo_evento().resultado, 'cooldown')

    def test_tras_el_cooldown_si_se_envia_otro_y_el_viejo_ya_no_verifica(self):
        usuario = crear_usuario()
        inicio = timezone.now()
        with _en(inicio):
            self.pedir(usuario.email)
        viejo = self.codigo_enviado()
        CodigoRecuperacion.objects.filter(usuario=usuario).update(intentos=3)

        with _en(inicio + timedelta(seconds=61)):
            self.pedir(usuario.email)

        fila = CodigoRecuperacion.objects.get(usuario=usuario)
        self.assertEqual(self.enviar.call_count, 2)
        self.assertEqual(fila.intentos, 0)
        self.assertIsNone(fila.consumido_en)
        nuevo = self.codigo_enviado()
        self.assertEqual(fila.codigo_hash, hash_codigo(usuario, nuevo))
        if nuevo != viejo:  # 1 en un millon que el generador repita
            self.assertNotEqual(fila.codigo_hash, hash_codigo(usuario, viejo))

    def test_la_cuarta_solicitud_en_una_hora_no_envia(self):
        usuario = crear_usuario()
        inicio = timezone.now()
        for n in range(3):
            with _en(inicio + timedelta(seconds=61 * n)):
                self.pedir(usuario.email)
        self.assertEqual(self.enviar.call_count, 3)

        with _en(inicio + timedelta(seconds=61 * 3)):
            self.pedir(usuario.email)

        self.assertEqual(self.enviar.call_count, 3)
        self.assertEqual(self.ultimo_evento().resultado, 'limite_correo')

    def test_pasada_la_hora_vuelve_a_enviar(self):
        usuario = crear_usuario()
        inicio = timezone.now()
        for n in range(3):
            with _en(inicio + timedelta(seconds=61 * n)):
                self.pedir(usuario.email)
        with _en(inicio + timedelta(hours=1, minutes=5)):
            self.pedir(usuario.email)
        self.assertEqual(self.enviar.call_count, 4)

    def test_la_solicitud_once_en_el_dia_no_envia(self):
        usuario = crear_usuario()
        for n in range(1, 11):  # cada dos horas: ninguna cuenta contra el limite por hora
            self.evento(usuario.email, hace=timedelta(hours=2 * n - 1))
        self.pedir(usuario.email)
        self.enviar.assert_not_called()
        self.assertEqual(self.ultimo_evento().resultado, 'limite_correo')

    def test_nueve_en_el_dia_todavia_deja_enviar(self):
        usuario = crear_usuario()
        for n in range(1, 10):
            self.evento(usuario.email, hace=timedelta(hours=2 * n - 1))
        self.pedir(usuario.email)
        self.enviar.assert_called_once()

    def test_lo_rechazado_no_extiende_el_bloqueo(self):
        """Quien insiste mientras esta limitado no se queda limitado para siempre: solo cuentan los envios."""
        usuario = crear_usuario()
        for _ in range(5):
            self.evento(usuario.email, resultado='limite_correo', hace=timedelta(minutes=5))
            self.evento(usuario.email, resultado='cooldown', hace=timedelta(minutes=5))
        self.pedir(usuario.email)
        self.enviar.assert_called_once()

    def test_el_limite_cuenta_igual_para_una_cuenta_que_no_existe(self):
        """Si solo contara para cuentas reales, el limite mismo delataria cuales existen."""
        correo = f'nadie-{uuid.uuid4().hex[:8]}@example.com'
        inicio = timezone.now()
        for n in range(3):
            with _en(inicio + timedelta(seconds=61 * n)):
                self.pedir(correo)
        with _en(inicio + timedelta(seconds=61 * 3)):
            self.pedir(correo)
        self.assertEqual(self.ultimo_evento().resultado, 'limite_correo')

    def test_el_limite_es_por_correo_tecleado_sin_distinguir_mayusculas(self):
        usuario = crear_usuario()
        self.pedir(usuario.email)
        self.pedir(usuario.email.upper())
        self.assertEqual(self.enviar.call_count, 1)
        self.assertEqual(self.ultimo_evento().resultado, 'cooldown')

    def test_tope_global_de_50_correos_al_dia(self):
        usuario = crear_usuario()
        for n in range(50):
            self.evento(f'otro-{n}@example.com', hace=timedelta(hours=3))
        with self.assertLogs('apps.cuentas.servicio', level='WARNING') as registro:
            self.pedir(usuario.email)
        # Warning y no error: un atacante no debe poder agotar la cuota de Sentry con cada solicitud.
        self.assertTrue(all(r.levelname == 'WARNING' for r in registro.records))
        self.enviar.assert_not_called()
        self.assertEqual(self.ultimo_evento().resultado, 'limite_global')
        self.assertFalse(CodigoRecuperacion.objects.filter(usuario=usuario).exists())

    def test_con_49_correos_en_el_dia_todavia_envia(self):
        usuario = crear_usuario()
        for n in range(49):
            self.evento(f'otro-{n}@example.com', hace=timedelta(hours=3))
        self.pedir(usuario.email)
        self.enviar.assert_called_once()

    def test_el_tope_global_no_cuenta_lo_que_no_se_envio(self):
        usuario = crear_usuario()
        for n in range(60):
            self.evento(f'otro-{n}@example.com', resultado='sin_cuenta', hace=timedelta(hours=3))
        self.pedir(usuario.email)
        self.enviar.assert_called_once()

    def test_la_solicitud_once_de_una_misma_ip_en_una_hora_no_envia(self):
        usuario = crear_usuario()
        for n in range(10):
            self.evento(f'otro-{n}@example.com', ip=IP, hace=timedelta(minutes=20))
        antes = EventoRecuperacion.objects.count()
        self.pedir(usuario.email)
        self.enviar.assert_not_called()
        self.assertFalse(CodigoRecuperacion.objects.filter(usuario=usuario).exists())
        # Rechazar por IP no escribe: un cliente limitado no debe poder inflar la tabla.
        self.assertEqual(EventoRecuperacion.objects.count(), antes)

    def test_nueve_de_la_misma_ip_todavia_deja_enviar(self):
        usuario = crear_usuario()
        for n in range(9):
            self.evento(f'otro-{n}@example.com', ip=IP, hace=timedelta(minutes=20))
        self.pedir(usuario.email)
        self.enviar.assert_called_once()

    def test_otra_ip_no_comparte_el_limite(self):
        usuario = crear_usuario()
        for n in range(10):
            self.evento(f'otro-{n}@example.com', ip='198.51.100.77', hace=timedelta(minutes=20))
        self.pedir(usuario.email)
        self.enviar.assert_called_once()


class SolicitarEnvioFallidoTests(SolicitarCodigoBase):
    def test_si_el_correo_no_salio_queda_en_la_bitacora_y_la_respuesta_no_cambia(self):
        usuario = crear_usuario()
        self.enviar.return_value = False
        self.assertIsNone(self.pedir(usuario.email))
        self.assertEqual(self.ultimo_evento().resultado, 'envio_fallido')
        self.assertEqual(self.ultimo_evento().usuario, usuario)

    def test_si_la_funcion_de_correo_lanza_no_se_propaga_ni_se_loguea_el_codigo(self):
        usuario = crear_usuario()
        self.enviar.side_effect = RuntimeError('boom')
        with self.assertLogs('apps.cuentas.servicio', level='ERROR') as logs:
            self.assertIsNone(self.pedir(usuario.email))
        self.assertEqual(self.ultimo_evento().resultado, 'envio_fallido')
        self.assertIn('RuntimeError', '\n'.join(logs.output))
        self.assertNotIn('Traceback', '\n'.join(logs.output))

    def test_un_envio_fallido_no_gasta_el_cupo_de_solicitudes_del_correo(self):
        usuario = crear_usuario()
        for _ in range(5):
            self.evento(usuario.email, resultado='envio_fallido', hace=timedelta(minutes=5))
        self.pedir(usuario.email)
        self.enviar.assert_called_once()


class IpExcedidaSolicitudTests(SolicitarCodigoBase):
    def test_diez_en_la_ultima_hora_excede_y_nueve_no(self):
        for n in range(9):
            self.evento(f'o-{n}@example.com', ip=IP, hace=timedelta(minutes=5))
        self.assertFalse(ip_excedida_solicitud(IP))
        self.evento('o-9@example.com', ip=IP, hace=timedelta(minutes=5))
        self.assertTrue(ip_excedida_solicitud(IP))

    def test_las_de_hace_mas_de_una_hora_no_cuentan(self):
        for n in range(15):
            self.evento(f'o-{n}@example.com', ip=IP, hace=timedelta(minutes=61))
        self.assertFalse(ip_excedida_solicitud(IP))

    def test_las_confirmaciones_no_cuentan_como_solicitudes(self):
        for n in range(15):
            self.evento(f'o-{n}@example.com', ip=IP, tipo=EventoRecuperacion.CONFIRMACION)
        self.assertFalse(ip_excedida_solicitud(IP))

    def test_sin_ip_conocida_no_excede(self):
        self.assertFalse(ip_excedida_solicitud(None))
        self.assertFalse(ip_excedida_solicitud(''))
