"""El apartado temporal de cupo esta encendido en la configuracion de produccion.

El apartado («tu lugar esta guardado hasta las HH:MM») nunca se vio en produccion porque
`render.yaml` declaraba `APARTADO_MINUTOS=0`, que lo apaga (`apartado_activo()`). Las pruebas del
apartado fijan su propio valor con `override_settings`, asi que ninguna se enteraba de lo que
Render le iba a dar al servicio. Esta lee el valor de `render.yaml` y corre el pago con el.
"""
import re
import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from stripe import StripeClient

from apps.bookings.cupo.apartado import apartado_activo
from apps.bookings.models import Reserva
from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca

from .tests_apartado_crear_pago import LLAVES, intent_falso

RENDER_YAML = Path(settings.BASE_DIR).parent / 'render.yaml'


def apartado_minutos_de_render():
    """El valor que `render.yaml` le da a APARTADO_MINUTOS en el servicio web (sin PyYAML)."""
    texto = RENDER_YAML.read_text(encoding='utf-8')
    coincidencia = re.search(
        r'^\s*-\s*key:\s*APARTADO_MINUTOS\s*\n\s*value:\s*"?(\d+)"?', texto, re.MULTILINE,
    )
    if coincidencia is None:
        raise AssertionError('render.yaml no declara APARTADO_MINUTOS: Render usaria el default (0, apagado).')
    return int(coincidencia.group(1))


class RenderEnciendeElApartadoTests(ApiTestCase):
    def test_render_yaml_declara_15_minutos(self):
        self.assertEqual(apartado_minutos_de_render(), 15)

    @override_settings(**LLAVES)
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_con_el_valor_de_render_el_pago_aparta_el_cupo_y_devuelve_el_vencimiento(self, payment_intents):
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_publishable_key'])
        crear_flota(self.empresa)
        servicio = crear_servicio_pesca(self.empresa, precio_base=Decimal('4500.00'))
        reserva = Reserva.objects.create(
            empresa=self.empresa, servicio=servicio, fecha=date.today() + timedelta(days=10),
            hora=time(6, 0), numero_personas=2, nombre_cliente='Ana Ruiz',
            telefono_cliente='+5216121234567', correo_cliente='ana@example.com', moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO, checkout_id=uuid.uuid4(),
            deslinde_aceptado=True, deslinde_nombre='Ana Ruiz',
        )
        payment_intents.create.return_value = intent_falso()
        minutos = apartado_minutos_de_render()

        with override_settings(APARTADO_MINUTOS=minutos):
            self.assertTrue(apartado_activo())
            respuesta = self.client.post(
                reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk}),
                {'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)},
                content_type='application/json',
            )

        self.assertEqual(respuesta.status_code, 200)
        reserva.refresh_from_db()
        self.assertIsNotNone(reserva.apartado_hasta)
        self.assertEqual(respuesta.json()['apartado_hasta'], reserva.apartado_hasta.isoformat())
        self.assertGreater(reserva.apartado_hasta, timezone.now() + timedelta(minutes=minutos - 1))
