"""El `to` de WhatsApp Business sale con codigo de pais y sin `+` (ARCH-telefono-con-pais).

Meta pide el numero en digitos con codigo de pais. Antes se mandaba el texto crudo del
cliente ('612 123 4567'); ahora pasa por `telefono_marcable()`.
"""
from unittest import mock

from django.test import override_settings

from apps.testing import EmpresaTestCase

from .services import enviar_whatsapp_confirmacion, enviar_whatsapp_reembolso_sin_cupo
from .tests import crear_reserva

WHATSAPP = dict(
    WHATSAPP_TOKEN='test-wa-token',
    WHATSAPP_PHONE_NUMBER_ID='test-wa-phone-id',
    WHATSAPP_TEMPLATE='confirmacion_v1',
    WHATSAPP_TEMPLATE_LANG='es_MX',
    WHATSAPP_TEMPLATE_REEMBOLSO_SIN_CUPO='reembolso_v1',
)


@override_settings(**WHATSAPP)
class DestinoDeWhatsAppTests(EmpresaTestCase):
    def _destino(self, enviar, telefono):
        reserva = crear_reserva(self.empresa)
        reserva.telefono_cliente = telefono
        with mock.patch('apps.notifications.services.requests.post') as post:
            post.return_value.raise_for_status.return_value = None
            self.assertTrue(enviar(reserva))
        return post.call_args.kwargs['json']['to']

    def test_confirmacion_con_el_formato_nuevo_sale_sin_mas(self):
        self.assertEqual(self._destino(enviar_whatsapp_confirmacion, '+526121234567'), '526121234567')
        self.assertEqual(self._destino(enviar_whatsapp_confirmacion, '+47 41234567'), '4741234567')
        self.assertEqual(self._destino(enviar_whatsapp_confirmacion, '+376 312 345'), '376312345')

    def test_confirmacion_con_el_formato_viejo_completa_la_lada(self):
        self.assertEqual(self._destino(enviar_whatsapp_confirmacion, '612 123 4567'), '526121234567')
        self.assertEqual(self._destino(enviar_whatsapp_confirmacion, '(612) 123-4567'), '526121234567')

    def test_si_no_se_puede_marcar_se_conserva_el_valor_original(self):
        # No empeora lo de hoy: un dato raro viaja como antes y Meta decide.
        self.assertEqual(self._destino(enviar_whatsapp_confirmacion, '612 1234'), '612 1234')

    def test_reembolso_sin_cupo_usa_el_mismo_destino(self):
        self.assertEqual(self._destino(enviar_whatsapp_reembolso_sin_cupo, '+526121234567'), '526121234567')
        self.assertEqual(self._destino(enviar_whatsapp_reembolso_sin_cupo, '612 123 4567'), '526121234567')
        self.assertEqual(self._destino(enviar_whatsapp_reembolso_sin_cupo, '+47 41234567'), '4741234567')
        self.assertEqual(self._destino(enviar_whatsapp_reembolso_sin_cupo, '612 1234'), '612 1234')
