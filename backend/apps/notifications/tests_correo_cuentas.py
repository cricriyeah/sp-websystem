"""Correos de la recuperacion de contrasena: el codigo y el aviso de cambio.

Estos dos correos llevan o anuncian una credencial, asi que sus reglas son mas estrictas que las de los
correos de reserva: nunca van con copia oculta (`RESEND_BCC` mandaria el codigo al buzon del negocio),
el asunto jamas lleva el codigo, y ningun fallo puede dejar el codigo en un log.
"""
import logging
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from apps.cuentas.seguridad import Secreto
from apps.notifications import plantilla, services

LLAVES = {'RESEND_API_KEY': 'llave-de-prueba', 'RESEND_FROM': 'cuentas@ejemplo.com'}
CODIGO = '483920'
DESTINO = 'Ana.Ruiz@Ejemplo.com'


def _respuesta_ok():
    respuesta = mock.Mock(status_code=200)
    respuesta.raise_for_status.return_value = None
    return respuesta


def _respuesta_con_error(estado=403, texto='dominio no verificado'):
    respuesta = mock.Mock(status_code=estado, text=texto)
    error = requests.HTTPError(f'{estado} Client Error', response=respuesta)
    respuesta.raise_for_status.side_effect = error
    return respuesta


@override_settings(**LLAVES, RESEND_BCC=['negocio@ejemplo.com'])
class CorreoDelCodigoTests(SimpleTestCase):
    def enviar(self, usuario='ana', codigo=None, destino=DESTINO):
        with mock.patch('apps.notifications.services.requests.post', return_value=_respuesta_ok()) as post:
            ok = services.enviar_correo_codigo_recuperacion(destino, usuario, codigo or Secreto(CODIGO))
        return ok, post

    def test_va_solo_a_la_direccion_guardada_y_nunca_con_copia_oculta(self):
        ok, post = self.enviar()
        self.assertTrue(ok)
        cuerpo = post.call_args.kwargs['json']
        self.assertEqual(cuerpo['to'], [DESTINO])
        self.assertNotIn('bcc', cuerpo)
        self.assertNotIn('cc', cuerpo)
        self.assertEqual(cuerpo['from'], 'cuentas@ejemplo.com')

    def test_el_asunto_no_lleva_el_codigo(self):
        _, post = self.enviar()
        asunto = post.call_args.kwargs['json']['subject']
        self.assertEqual(asunto, 'Tu código para recuperar la contraseña')
        self.assertNotIn(CODIGO, asunto)

    def test_html_y_texto_llevan_el_codigo_el_usuario_y_el_vencimiento(self):
        _, post = self.enviar(usuario='ana.ruiz')
        cuerpo = post.call_args.kwargs['json']
        for version in ('html', 'text'):
            with self.subTest(version=version):
                self.assertIn(CODIGO, cuerpo[version])
                self.assertIn('ana.ruiz', cuerpo[version])
                self.assertIn('Usuario', cuerpo[version])
                self.assertIn('10 minutos', cuerpo[version])
                self.assertIn('ignóralo', cuerpo[version])
                self.assertIn('no cambia', cuerpo[version])

    def test_no_pone_enlaces_ni_el_codigo_en_la_vista_previa(self):
        _, post = self.enviar()
        html = post.call_args.kwargs['json']['html']
        self.assertNotIn('href=', html)
        self.assertNotIn('http', html.replace('http-equiv', ''))
        # La vista previa (preheader oculto) sale en la lista de la bandeja: ahi no va el codigo.
        previa = html.split('opacity:0;', 1)[1].split('</div>', 1)[0]
        self.assertNotIn(CODIGO, previa)

    def test_el_nombre_de_usuario_va_escapado(self):
        _, post = self.enviar(usuario='<script>alert(1)</script>')
        cuerpo = post.call_args.kwargs['json']
        self.assertNotIn('<script>', cuerpo['html'])
        self.assertIn('&lt;script&gt;', cuerpo['html'])

    def test_acepta_el_codigo_como_texto_plano_tambien(self):
        _, post = self.enviar(codigo=CODIGO)
        self.assertIn(CODIGO, post.call_args.kwargs['json']['html'])

    @override_settings(RESEND_API_KEY='', RESEND_FROM='')
    def test_sin_resend_configurado_devuelve_false_sin_lanzar_ni_llamar(self):
        with mock.patch('apps.notifications.services.requests.post') as post:
            self.assertFalse(services.enviar_correo_codigo_recuperacion(DESTINO, 'ana', Secreto(CODIGO)))
        post.assert_not_called()

    def test_un_fallo_http_devuelve_false_y_el_log_no_trae_el_codigo_ni_traza(self):
        with mock.patch('apps.notifications.services.requests.post', return_value=_respuesta_con_error()):
            with self.assertLogs('apps.notifications.services', level=logging.WARNING) as logs:
                self.assertFalse(services.enviar_correo_codigo_recuperacion(DESTINO, 'ana', Secreto(CODIGO)))
        salida = '\n'.join(logs.output)
        self.assertNotIn(CODIGO, salida)
        self.assertNotIn('Traceback', salida)
        self.assertTrue(all(registro.exc_info is None for registro in logs.records))
        self.assertIn('403', salida)

    def test_un_timeout_devuelve_false_sin_traza(self):
        with mock.patch('apps.notifications.services.requests.post', side_effect=requests.Timeout('lento')):
            with self.assertLogs('apps.notifications.services', level=logging.WARNING) as logs:
                self.assertFalse(services.enviar_correo_codigo_recuperacion(DESTINO, 'ana', Secreto(CODIGO)))
        self.assertTrue(all(registro.exc_info is None for registro in logs.records))
        self.assertNotIn(CODIGO, '\n'.join(logs.output))

    def test_el_log_de_la_ruta_sin_configurar_tampoco_trae_el_codigo(self):
        with override_settings(RESEND_API_KEY='', RESEND_FROM=''):
            with self.assertLogs('apps.notifications.services', level=logging.INFO) as logs:
                services.enviar_correo_codigo_recuperacion(DESTINO, 'ana', Secreto(CODIGO))
        self.assertNotIn(CODIGO, '\n'.join(logs.output))


@override_settings(**LLAVES, RESEND_BCC=['negocio@ejemplo.com'])
class CorreoDeContrasenaCambiadaTests(SimpleTestCase):
    def enviar(self, **extra):
        with mock.patch('apps.notifications.services.requests.post', return_value=_respuesta_ok()) as post:
            ok = services.enviar_correo_contrasena_cambiada(DESTINO, 'ana.ruiz', **extra)
        return ok, post

    def test_avisa_a_la_direccion_guardada_sin_copia_oculta(self):
        ok, post = self.enviar()
        self.assertTrue(ok)
        post.assert_called_once()
        cuerpo = post.call_args.kwargs['json']
        self.assertEqual(cuerpo['to'], [DESTINO])
        self.assertNotIn('bcc', cuerpo)
        self.assertEqual(cuerpo['subject'], 'Tu contraseña cambió')

    def test_dice_quien_y_que_hacer_si_no_fue_el(self):
        _, post = self.enviar()
        cuerpo = post.call_args.kwargs['json']
        for version in ('html', 'text'):
            with self.subTest(version=version):
                self.assertIn('ana.ruiz', cuerpo[version])
                self.assertIn('Si no fuiste tú', cuerpo[version])

    def test_la_copia_al_administrador_es_un_correo_aparte_y_sin_bcc(self):
        ok, post = self.enviar(copia_a=['dueno@ejemplo.com', 'jefa@ejemplo.com'])
        self.assertTrue(ok)
        self.assertEqual(post.call_count, 2)
        para_el_usuario, para_el_admin = (llamada.kwargs['json'] for llamada in post.call_args_list)
        self.assertEqual(para_el_usuario['to'], [DESTINO])
        self.assertEqual(para_el_admin['to'], ['dueno@ejemplo.com', 'jefa@ejemplo.com'])
        self.assertNotIn('bcc', para_el_admin)
        self.assertIn('ana.ruiz', para_el_admin['html'])
        self.assertNotIn('Si no fuiste tú', para_el_admin['html'])

    def test_si_falla_la_copia_al_admin_el_aviso_al_usuario_cuenta_como_enviado(self):
        respuestas = [_respuesta_ok(), _respuesta_con_error()]
        with mock.patch('apps.notifications.services.requests.post', side_effect=respuestas):
            with self.assertLogs('apps.notifications.services', level=logging.WARNING):
                self.assertTrue(
                    services.enviar_correo_contrasena_cambiada(DESTINO, 'ana.ruiz', copia_a=['dueno@ejemplo.com'])
                )

    @override_settings(RESEND_API_KEY='', RESEND_FROM='')
    def test_sin_resend_configurado_devuelve_false(self):
        with mock.patch('apps.notifications.services.requests.post') as post:
            self.assertFalse(services.enviar_correo_contrasena_cambiada(DESTINO, 'ana'))
        post.assert_not_called()

    def test_un_fallo_http_devuelve_false_sin_traza(self):
        with mock.patch('apps.notifications.services.requests.post', return_value=_respuesta_con_error(500)):
            with self.assertLogs('apps.notifications.services', level=logging.WARNING) as logs:
                self.assertFalse(services.enviar_correo_contrasena_cambiada(DESTINO, 'ana'))
        self.assertTrue(all(registro.exc_info is None for registro in logs.records))


class PlantillaConPieTests(SimpleTestCase):
    def correo(self, **extra):
        return plantilla.correo(actividad='cuenta', empresa='Sun Baja Experience', titulo='Tu código', **extra)

    def test_existe_el_campo_de_color_de_cuenta(self):
        self.assertEqual(plantilla.CAMPO['cuenta'], plantilla.TINTA)
        self.assertIn(plantilla.TINTA, self.correo())

    def test_con_pie_propio_reemplaza_el_de_comprobante_de_reserva(self):
        html = self.correo(pie_html='<p>Pie de cuenta</p>')
        self.assertIn('Pie de cuenta', html)
        self.assertNotIn('es tu comprobante', html)

    def test_sin_pie_propio_la_salida_es_la_de_siempre(self):
        html = self.correo()
        self.assertIn('Guarda este correo: es tu comprobante.', html)
        self.assertEqual(html, self.correo(pie_html=None))
