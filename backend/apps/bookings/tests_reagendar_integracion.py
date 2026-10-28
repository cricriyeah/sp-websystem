"""Vista y servicio de Reagendar juntos, sin parchear `proponer` ni `reagendar`.

Las pruebas de la vista parchean el servicio y las del servicio no pasan por la pantalla: nadie probaba que el
contrato de `Propuesta` / `Resultado` que lee la vista sea el que el servicio entrega. Esto recorre
paso 1 -> paso 2 -> confirmar contra la base real.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.admin.models import LogEntry

from apps.bookings.tests_reagendar_vista import _Base

from .models import Reserva

CORREO = 'apps.notifications.correo_reagendado.enviar_correo_reagendado'


class RecorridoCompletoTests(_Base):
    def test_revisar_pinta_el_antes_y_el_ahora_del_servicio_real(self):
        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Revisa antes de confirmar')
        self.assertContains(respuesta, 'Reagendar y avisar al cliente')

    def test_confirmar_mueve_la_fecha_deja_constancia_y_manda_el_correo(self):
        with mock.patch(CORREO, return_value=True) as correo:
            with self.captureOnCommitCallbacks(execute=True):
                respuesta = self.client.post(self.url, self._datos_de_confirmar())

        self.assertEqual(respuesta.status_code, 302)
        reserva = self._reserva()
        self.assertEqual(reserva.fecha, self.fecha_nueva)
        self.assertEqual(correo.call_count, 1)
        self.assertTrue(
            LogEntry.objects.filter(object_id=str(self.reserva.pk), action_flag=2).exists(),
        )

    def test_sin_marcar_la_casilla_no_sale_correo(self):
        datos = self._datos_de_confirmar()
        datos.pop('avisar_cliente')
        with mock.patch(CORREO, return_value=True) as correo:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(self.url, datos)

        self.assertEqual(self._reserva().fecha, self.fecha_nueva)
        correo.assert_not_called()

    def test_doble_envio_solo_mueve_una_vez_y_el_segundo_repinta_con_el_error(self):
        with mock.patch(CORREO, return_value=True) as correo:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(self.url, self._datos_de_confirmar())
                segundo = self.client.post(self.url, self._datos_de_confirmar())

        self.assertEqual(segundo.status_code, 200)
        self.assertContains(segundo, 'Elige una fecha u hora distinta de la actual')
        self.assertEqual(correo.call_count, 1)

    def test_menos_de_48_horas_la_vendedora_queda_bloqueada_y_la_jefa_pasa_con_motivo(self):
        self._actualizar(fecha=self.hoy + timedelta(days=1))
        proxima = self._reserva().fecha
        datos = self._datos_de_confirmar(token_fecha=proxima.isoformat())

        self.client.force_login(self.vendedora)
        bloqueada = self.client.post(self.url, datos)
        self.assertEqual(self._reserva().fecha, proxima)
        self.assertEqual(bloqueada.status_code, 200)

        self.client.force_login(self.jefa)
        with mock.patch(CORREO, return_value=True):
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(self.url, {**datos, 'motivo_excepcion': 'El cliente perdio su vuelo'})
        self.assertEqual(self._reserva().fecha, self.fecha_nueva)

    def test_un_token_manipulado_con_fecha_imposible_no_da_500(self):
        datos = self._datos_de_confirmar(token_fecha='2026-02-31', token_hora='25:00:00')
        with mock.patch(CORREO, return_value=True) as correo:
            with self.captureOnCommitCallbacks(execute=True):
                respuesta = self.client.post(self.url, datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'cambió mientras la revisabas')
        self.assertEqual(self._reserva().fecha, self.fecha_actual)
        correo.assert_not_called()
