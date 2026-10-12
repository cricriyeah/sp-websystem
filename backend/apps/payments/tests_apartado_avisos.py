"""Pruebas de avisos de reembolso por falta de cupo (spec §4.5, Tarea 08).

Verifica la clasificación por causa (cupo vs otra), los avisos al cliente y a la
empresa, deduplicación de reintentos, resiliencia ante fallos de red y alerta
urgente única ante fallo de reembolso.
"""
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from unittest import mock
import uuid

import requests
import stripe
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.bookings.cupo.confirmacion import SinCupoError
from apps.bookings.models import CupoDiario, Reserva, ReservaOcupacion
from apps.fleet.models import Paquete, PaqueteServicio, Recurso, Servicio
from apps.payments.pricing import a_centavos
from apps.payments.services import FALLO_REEMBOLSO, SIN_CUPO_REEMBOLSADO, YA_APLICADO, aplicar_pago_exitoso
from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca

LLAVES = {
    'RESEND_API_KEY': 'test-resend-key',
    'RESEND_FROM': 'reservas@ejemplo.test',
    'FRONTEND_URL': 'https://ejemplo.test',
}


def crear_reserva_pendiente(empresa, **overrides):
    datos = {
        'empresa': empresa,
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
        'moneda': 'MXN',
        'precio_total': Decimal('4500.00'),
        'forma_pago': Reserva.FormaPago.COMPLETO,
        'stripe_payment_intent_id': f'pi_test_{uuid.uuid4().hex[:8]}',
    }
    if 'servicio' not in overrides and 'paquete' not in overrides:
        datos['servicio'] = crear_servicio_pesca(
            empresa, precio_base=Decimal('4500.00'), precio_persona_extra=Decimal('0')
        )
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva


def evento_pagado(reserva, amount=None, intent_id=None):
    amount_cents = a_centavos(reserva.precio_total or Decimal('4500.00')) if amount is None else amount
    pi_id = intent_id or reserva.stripe_payment_intent_id or 'pi_test_123'
    return {
        'id': f'evt_{uuid.uuid4().hex[:8]}',
        'type': 'payment_intent.succeeded',
        'data': {
            'object': {
                'id': pi_id,
                'amount_received': amount_cents,
                'currency': reserva.moneda.lower(),
                'created': int(timezone.now().timestamp()),
                'metadata': {'reserva_id': str(reserva.pk)},
            },
        },
    }


class MockIntent(dict):
    """Objeto que soporta acceso por atributo (.status, .id...) y por clave (['metadata'])."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status = self.get('status', 'succeeded')
        self.id = self.get('id', '')
        self.amount_received = self.get('amount_received', 0)
        self.currency = self.get('currency', 'mxn')


@override_settings(**LLAVES)
class ApartadoAvisosTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_webhook_secret = 'whsec_falsa'
        self.empresa.correos_aviso = 'avisos@ejemplo.com'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_webhook_secret', 'correos_aviso'])
        crear_flota(self.empresa)

    def entregar_webhook(self, evento):
        with mock.patch('stripe.Webhook.construct_event', return_value=evento):
            with self.captureOnCommitCallbacks(execute=True):
                return self.client.post(
                    reverse('stripe-webhook', kwargs={'empresa_slug': self.empresa.slug}),
                    '{}',
                    content_type='application/json',
                    HTTP_STRIPE_SIGNATURE='firma_valida',
                )

    @mock.patch('apps.notifications.services.requests.post')
    @mock.patch('apps.payments.services.reembolsar', return_value=True)
    def test_dia_pesca_lleno_clean_clasifica_cupo_y_manda_correo(self, mock_reembolsar, mock_post):
        """Un día de pesca lleno pasando por Reserva.clean() se clasifica cupo y manda el correo."""
        mock_post.return_value.raise_for_status.return_value = None
        reserva = crear_reserva_pendiente(self.empresa)

        # Llenar el cupo del día (tope 0 viajes) para que Reserva.clean() falle por cupo
        CupoDiario.objects.create(empresa=self.empresa, fecha=reserva.fecha, cupo_maximo=0)

        response = self.entregar_webhook(evento_pagado(reserva))
        self.assertEqual(response.status_code, 200)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva.reembolsada)
        mock_reembolsar.assert_called_once()

        # Debe mandar correo al cliente y alerta a la empresa
        destinatarios = [c.kwargs['json']['to'] for c in mock_post.call_args_list]
        self.assertIn([reserva.correo_cliente], destinatarios)
        self.assertIn(['avisos@ejemplo.com'], destinatarios)

        # Verificar contenido del correo al cliente
        llamadas_cliente = [c for c in mock_post.call_args_list if c.kwargs['json']['to'] == [reserva.correo_cliente]]
        self.assertEqual(len(llamadas_cliente), 1)
        correo_json = llamadas_cliente[0].kwargs['json']
        self.assertIn('No pudimos asegurar tu lugar', correo_json['subject'])
        self.assertIn('No pudimos asegurar tu lugar para el', correo_json['html'])
        self.assertIn('Ya solicitamos el reembolso completo', correo_json['html'])
        self.assertIn('Elegir otra fecha', correo_json['html'])
        self.assertIn('reservar?', correo_json['html'])

        # Verificar alerta interna con formato de spec
        llamadas_empresa = [c for c in mock_post.call_args_list if c.kwargs['json']['to'] == ['avisos@ejemplo.com']]
        self.assertEqual(len(llamadas_empresa), 1)
        alerta_json = llamadas_empresa[0].kwargs['json']
        self.assertIn(f'ALERTA: reserva #{reserva.pk} · cupo · reembolsada automáticamente', alerta_json['subject'])

    @mock.patch('apps.notifications.services.requests.post')
    @mock.patch('apps.payments.services.reembolsar', return_value=True)
    def test_hospedaje_lleno_clasifica_cupo_y_manda_correo(self, mock_reembolsar, mock_post):
        """Un hospedaje lleno (forma de diccionario) se clasifica cupo y manda el correo."""
        mock_post.return_value.raise_for_status.return_value = None
        srv_hospedaje = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Hotel Los Arcos',
            slug='hotel-los-arcos',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            estrategia_precio='por_noche',
            precio_base=Decimal('2000.00'),
            pide_hora=False,
        )
        recurso = Recurso.objects.create(
            empresa=self.empresa, servicio=srv_hospedaje, nombre='Habitacion Mar', capacidad_maxima=2,
        )
        fecha_ini = date.today() + timedelta(days=10)
        fecha_fin = date.today() + timedelta(days=12)

        # Ocupar la única habitación en esas fechas
        res_ocupante = crear_reserva_pendiente(
            self.empresa,
            servicio=srv_hospedaje,
            fecha=fecha_ini,
            fecha_salida=fecha_fin,
            nombre_cliente='Carlos Mendoza',
            correo_cliente='carlos@example.com',
        )
        res_ocupante.estado = Reserva.Estado.PAGADA
        res_ocupante.save(update_fields=['estado'])
        ReservaOcupacion.objects.create(
            empresa=self.empresa,
            reserva=res_ocupante,
            recurso=recurso,
            fecha_inicio=fecha_ini,
            fecha_fin=fecha_fin,
            ocupa_cupo=True,
        )

        # Reserva pendiente que intenta ocupar las mismas fechas
        reserva = crear_reserva_pendiente(
            self.empresa,
            servicio=srv_hospedaje,
            fecha=fecha_ini,
            fecha_salida=fecha_fin,
            nombre_cliente='Laura Gomez',
            correo_cliente='laura@example.com',
        )

        response = self.entregar_webhook(evento_pagado(reserva))
        self.assertEqual(response.status_code, 200)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva.reembolsada)

        destinatarios = [c.kwargs['json']['to'] for c in mock_post.call_args_list]
        self.assertIn([reserva.correo_cliente], destinatarios)
        self.assertIn(['avisos@ejemplo.com'], destinatarios)

        llamadas_empresa = [c for c in mock_post.call_args_list if c.kwargs['json']['to'] == ['avisos@ejemplo.com']]
        self.assertIn(f'ALERTA: reserva #{reserva.pk} · cupo · reembolsada automáticamente', llamadas_empresa[0].kwargs['json']['subject'])

    @mock.patch('apps.notifications.services.requests.post')
    @mock.patch('apps.payments.services.reembolsar', return_value=True)
    def test_paquete_lleno_clasifica_cupo_y_manda_correo(self, mock_reembolsar, mock_post):
        """Un paquete lleno (forma de diccionario) se clasifica cupo y manda el correo."""
        mock_post.return_value.raise_for_status.return_value = None
        srv_pesca = crear_servicio_pesca(
            self.empresa, precio_base=Decimal('4500.00'), precio_persona_extra=Decimal('0')
        )
        paquete = Paquete.objects.create(
            sede=self.empresa.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Pesca Total',
            slug='paquete-pesca-total',
            precio_ancla=Decimal('4500.00'),
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=srv_pesca, orden=1, salidas=1)

        fecha = date.today() + timedelta(days=10)
        reserva = crear_reserva_pendiente(
            self.empresa,
            paquete=paquete,
            servicio=None,
            fecha=fecha,
            nombre_cliente='Sofia Perez',
            correo_cliente='sofia@example.com',
        )

        # Llenar el cupo del servicio del paquete
        CupoDiario.objects.create(empresa=self.empresa, fecha=fecha, cupo_maximo=0)

        response = self.entregar_webhook(evento_pagado(reserva))
        self.assertEqual(response.status_code, 200)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva.reembolsada)

        destinatarios = [c.kwargs['json']['to'] for c in mock_post.call_args_list]
        self.assertIn([reserva.correo_cliente], destinatarios)
        self.assertIn(['avisos@ejemplo.com'], destinatarios)

        llamadas_empresa = [c for c in mock_post.call_args_list if c.kwargs['json']['to'] == ['avisos@ejemplo.com']]
        self.assertIn(f'ALERTA: reserva #{reserva.pk} · cupo · reembolsada automáticamente', llamadas_empresa[0].kwargs['json']['subject'])

    @mock.patch('apps.notifications.services.requests.post')
    @mock.patch('apps.payments.services.reembolsar', return_value=True)
    def test_salidas_py_save_clasifica_cupo_y_manda_correo(self, mock_reembolsar, mock_post):
        """El error de salidas.py (que llega por Reserva.save()) se clasifica cupo y manda el correo."""
        mock_post.return_value.raise_for_status.return_value = None
        reserva = crear_reserva_pendiente(self.empresa)

        # Simular que al momento de guardar (bajo candado de salidas), validar_cupo_salidas_bajo_candado
        # lanza un error de salidas.py con code='sin_cupo'
        error_salidas = DjangoValidationError({
            'fecha': DjangoValidationError('No hay cupo disponible para el 2026-05-10 (lleno).', code='sin_cupo')
        })
        orig_save = Reserva.save

        def save_con_error(reserva_inst, *args, **kwargs):
            if reserva_inst.estado == Reserva.Estado.PAGADA:
                raise error_salidas
            return orig_save(reserva_inst, *args, **kwargs)

        with mock.patch.object(Reserva, 'save', save_con_error):
            response = self.entregar_webhook(evento_pagado(reserva))
            self.assertEqual(response.status_code, 200)

        destinatarios = [c.kwargs['json']['to'] for c in mock_post.call_args_list]
        self.assertIn([reserva.correo_cliente], destinatarios)
        self.assertIn(['avisos@ejemplo.com'], destinatarios)

        llamadas_empresa = [c for c in mock_post.call_args_list if c.kwargs['json']['to'] == ['avisos@ejemplo.com']]
        self.assertIn(f'ALERTA: reserva #{reserva.pk} · cupo · reembolsada automáticamente', llamadas_empresa[0].kwargs['json']['subject'])

    @mock.patch('apps.notifications.services.requests.post')
    @mock.patch('apps.payments.services.reembolsar', return_value=True)
    def test_falla_no_cupo_produce_alerta_interna_pero_no_correo_cliente(self, mock_reembolsar, mock_post):
        """Una falla de full_clean que NO es de cupo produce la alerta interna pero NO el correo al cliente."""
        mock_post.return_value.raise_for_status.return_value = None
        reserva = crear_reserva_pendiente(self.empresa)

        # Corromper el deslinde para que full_clean falle por deslinde no aceptado (sin code='sin_cupo')
        Reserva.objects.filter(pk=reserva.pk).update(deslinde_aceptado=False)

        response = self.entregar_webhook(evento_pagado(reserva))
        self.assertEqual(response.status_code, 200)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva.reembolsada)

        destinatarios = [c.kwargs['json']['to'] for c in mock_post.call_args_list]
        # NO debe enviar correo al cliente
        self.assertNotIn([reserva.correo_cliente], destinatarios)
        # SÍ debe enviar alerta interna a la empresa
        self.assertIn(['avisos@ejemplo.com'], destinatarios)

        llamadas_empresa = [c for c in mock_post.call_args_list if c.kwargs['json']['to'] == ['avisos@ejemplo.com']]
        self.assertIn(f'ALERTA: reserva #{reserva.pk} · otra · reembolsada automáticamente', llamadas_empresa[0].kwargs['json']['subject'])

    @mock.patch('apps.notifications.services.requests.post')
    @mock.patch('apps.payments.services.reembolsar', return_value=True)
    def test_correo_sale_una_sola_vez_aunque_webhook_se_reintente(self, mock_reembolsar, mock_post):
        """El correo sale una sola vez aunque el webhook se reintente."""
        mock_post.return_value.raise_for_status.return_value = None
        reserva = crear_reserva_pendiente(self.empresa)
        CupoDiario.objects.create(empresa=self.empresa, fecha=reserva.fecha, cupo_maximo=0)

        evento = evento_pagado(reserva)

        # Primera entrega
        resp1 = self.entregar_webhook(evento)
        self.assertEqual(resp1.status_code, 200)

        llamadas_cliente_1 = [c for c in mock_post.call_args_list if c.kwargs['json']['to'] == [reserva.correo_cliente]]
        self.assertEqual(len(llamadas_cliente_1), 1)

        # Segunda entrega (reintento del webhook con el mismo evento)
        resp2 = self.entregar_webhook(evento)
        self.assertEqual(resp2.status_code, 200)

        llamadas_cliente_2 = [c for c in mock_post.call_args_list if c.kwargs['json']['to'] == [reserva.correo_cliente]]
        self.assertEqual(len(llamadas_cliente_2), 1)

    @mock.patch('apps.notifications.services.requests.post')
    @mock.patch('apps.payments.services.reembolsar', return_value=True)
    def test_fallo_servicio_correo_no_tumba_webhook(self, mock_reembolsar, mock_post):
        """Nada tumba el webhook: un fallo del servicio de correo responde 200."""
        mock_post.side_effect = requests.RequestException('Resend no disponible')
        reserva = crear_reserva_pendiente(self.empresa)
        CupoDiario.objects.create(empresa=self.empresa, fecha=reserva.fecha, cupo_maximo=0)

        response = self.entregar_webhook(evento_pagado(reserva))
        self.assertEqual(response.status_code, 200)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(reserva.reembolsada)

    @mock.patch('apps.notifications.services.requests.post')
    @mock.patch('apps.payments.services.reembolsar', return_value=True)
    def test_whatsapp_apagado_sin_ajuste_y_envia_con_ajuste(self, mock_reembolsar, mock_post):
        """WhatsApp no envía sin el ajuste WHATSAPP_TEMPLATE_REEMBOLSO_SIN_CUPO, y envía cuando existe."""
        mock_post.return_value.raise_for_status.return_value = None
        reserva = crear_reserva_pendiente(self.empresa)
        CupoDiario.objects.create(empresa=self.empresa, fecha=reserva.fecha, cupo_maximo=0)

        # 1. Sin el ajuste (default: vacío): no llama a la API de WhatsApp de Meta
        self.entregar_webhook(evento_pagado(reserva))
        urls_llamadas = [c.args[0] for c in mock_post.call_args_list if c.args]
        self.assertFalse(any('graph.facebook.com' in url for url in urls_llamadas))

        # 2. Con el ajuste configurado
        mock_post.reset_mock()
        reserva_2 = crear_reserva_pendiente(self.empresa, nombre_cliente='Mateo Diaz', correo_cliente='mateo@example.com')
        CupoDiario.objects.filter(empresa=self.empresa, fecha=reserva_2.fecha).delete()
        CupoDiario.objects.create(empresa=self.empresa, fecha=reserva_2.fecha, cupo_maximo=0)

        with override_settings(
            WHATSAPP_TEMPLATE_REEMBOLSO_SIN_CUPO='plantilla_reembolso_cupo',
            WHATSAPP_TOKEN='token_meta_test',
            WHATSAPP_PHONE_NUMBER_ID='phone_id_123',
        ):
            self.entregar_webhook(evento_pagado(reserva_2))

        urls_llamadas_2 = [c.args[0] for c in mock_post.call_args_list if c.args]
        self.assertTrue(any('graph.facebook.com' in url for url in urls_llamadas_2))
        llamada_wa = [c for c in mock_post.call_args_list if c.args and 'graph.facebook.com' in c.args[0]][0]
        self.assertEqual(llamada_wa.kwargs['json']['template']['name'], 'plantilla_reembolso_cupo')
        self.assertEqual(llamada_wa.kwargs['json']['to'], reserva_2.telefono_cliente)

    @mock.patch('apps.notifications.services.requests.post')
    @mock.patch('apps.payments.services.reembolsar', return_value=False)
    def test_fallo_reembolso_alerta_una_sola_vez_con_reintentos_y_conciliar_pagos(self, mock_reembolsar, mock_post):
        """El fallo de reembolso alerta una sola vez aunque el webhook se reintente y conciliar_pagos corra varias veces."""
        mock_post.return_value.raise_for_status.return_value = None
        reserva = crear_reserva_pendiente(self.empresa)
        CupoDiario.objects.create(empresa=self.empresa, fecha=reserva.fecha, cupo_maximo=0)

        evento = evento_pagado(reserva)

        # 1. Primera entrega del webhook: falla reembolso -> alerta urgente
        resp1 = self.entregar_webhook(evento)
        self.assertEqual(resp1.status_code, 200)

        reserva.refresh_from_db()
        # Sigue en pendiente_pago
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertFalse(reserva.reembolsada)
        self.assertIsNotNone(reserva.alerta_reembolso_fallido_en)

        alertas_urgentes_1 = [
            c for c in mock_post.call_args_list
            if 'URGENTE: Fallo de reembolso' in c.kwargs['json'].get('subject', '')
        ]
        self.assertEqual(len(alertas_urgentes_1), 1)

        # 2. Reintento del webhook: alerta_reembolso_fallido_en ya está seteado -> no se duplica
        resp2 = self.entregar_webhook(evento)
        self.assertEqual(resp2.status_code, 200)

        alertas_urgentes_2 = [
            c for c in mock_post.call_args_list
            if 'URGENTE: Fallo de reembolso' in c.kwargs['json'].get('subject', '')
        ]
        self.assertEqual(len(alertas_urgentes_2), 1)

        # 3. Conciliar pagos corre varias veces: tampoco duplica
        intent_falso = MockIntent({
            'id': reserva.stripe_payment_intent_id,
            'status': 'succeeded',
            'amount_received': a_centavos(reserva.precio_total),
            'currency': reserva.moneda.lower(),
            'created': int(timezone.now().timestamp()),
            'metadata': {'reserva_id': str(reserva.pk)},
        })

        with mock.patch.object(stripe.StripeClient, 'payment_intents') as mock_pi:
            mock_pi.retrieve.return_value = intent_falso
            with self.captureOnCommitCallbacks(execute=True):
                call_command('conciliar_pagos')
            with self.captureOnCommitCallbacks(execute=True):
                call_command('conciliar_pagos')

        alertas_urgentes_3 = [
            c for c in mock_post.call_args_list
            if 'URGENTE: Fallo de reembolso' in c.kwargs['json'].get('subject', '')
        ]
        self.assertEqual(len(alertas_urgentes_3), 1)
