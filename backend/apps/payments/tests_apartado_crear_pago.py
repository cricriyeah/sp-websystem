"""Pruebas del apartado temporal de cupo en CrearPagoView (Tarea 05)."""

import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from stripe import StripeClient

from apps.bookings.models import (
    CupoDiario,
    Reserva,
    ReservaOcupacion,
)
from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.fleet.models import Paquete, PaqueteServicio, Recurso, Servicio
from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca

LLAVES = {'STRIPE_SECRET_KEY': 'sk_test_falsa', 'STRIPE_WEBHOOK_SECRET': 'whsec_falsa'}


def intent_falso(id='pi_1', amount=450000, status='requires_payment_method', currency='mxn'):
    return mock.Mock(
        id=id,
        amount=amount,
        currency=currency,
        status=status,
        client_secret=f'{id}_secret',
    )


@override_settings(APARTADO_MINUTOS=15, **LLAVES)
class ApartadoCrearPagoTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.empresa.stripe_secret_key = 'sk_test_falsa'
        self.empresa.stripe_publishable_key = 'pk_test_falsa'
        self.empresa.save(update_fields=['stripe_secret_key', 'stripe_publishable_key'])

        crear_flota(self.empresa)

        self.servicio = crear_servicio_pesca(
            self.empresa,
            precio_base=Decimal('4500.00'),
            precio_persona_extra=Decimal('500.00'),
        )
        self.fecha_viaje = date.today() + timedelta(days=10)
        self.checkout_id = uuid.uuid4()
        self.reserva = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio,
            fecha=self.fecha_viaje,
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Ana Ruiz',
            telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com',
            moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=self.checkout_id,
            deslinde_aceptado=True,
            deslinde_nombre='Ana Ruiz',
        )
        self.url = reverse(
            'crear-pago',
            kwargs={'empresa_slug': self.empresa.slug, 'pk': self.reserva.pk},
        )

    def post_pago(self, reserva=None, checkout_id=None, **extra):
        r = reserva or self.reserva
        cid = checkout_id if checkout_id is not None else str(r.checkout_id)
        url = reverse(
            'crear-pago',
            kwargs={'empresa_slug': self.empresa.slug, 'pk': r.pk},
        )
        payload = {
            'forma_pago': 'completo',
            'checkout_id': cid,
        }
        payload.update(extra)
        return self.client.post(url, payload, content_type='application/json')

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_apartado_exitoso_escribe_vencimiento_correcto_y_responde_con_apartado_hasta(
        self, payment_intents
    ):
        payment_intents.create.return_value = intent_falso()
        antes = timezone.now()

        resp = self.post_pago()

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('apartado_hasta', data)
        self.assertIsNotNone(data['apartado_hasta'])
        self.assertEqual(data['client_secret'], 'pi_1_secret')

        self.reserva.refresh_from_db()
        self.assertIsNotNone(self.reserva.apartado_hasta)
        self.assertIsNotNone(self.reserva.apartado_demanda)
        self.assertGreaterEqual(
            self.reserva.apartado_hasta, antes + timedelta(minutes=14, seconds=55)
        )
        self.assertLessEqual(
            self.reserva.apartado_hasta, timezone.now() + timedelta(minutes=15, seconds=5)
        )
        self.assertEqual(data['apartado_hasta'], self.reserva.apartado_hasta.isoformat())

        # El retrato describe la demanda apartada
        demanda = self.reserva.apartado_demanda
        self.assertEqual(demanda.get('v'), 1)
        self.assertEqual(len(demanda.get('salidas', [])), 1)
        self.assertEqual(
            demanda['salidas'][0]['fecha'], self.fecha_viaje.isoformat()
        )
        self.assertEqual(demanda['salidas'][0]['personas'], 2)
        payment_intents.create.assert_called_once()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_cupo_servicio_suelto_devuelve_409_con_motivo_y_proxima_disponible_sin_intent(
        self, payment_intents
    ):
        # Llenar el día cerrando el cupo a 0 viajes
        CupoDiario.objects.create(
            empresa=self.empresa,
            fecha=self.fecha_viaje,
            cupo_maximo=0,
        )

        resp = self.post_pago()

        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertEqual(data.get('codigo'), 'sin_cupo')
        self.assertEqual(data.get('motivo'), 'lleno')
        self.assertIsNotNone(data.get('proxima_disponible'))
        self.assertIn('detail', data)

        # No se debe crear PaymentIntent si no cabe
        payment_intents.create.assert_not_called()
        payment_intents.update.assert_not_called()

        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.apartado_hasta)
        self.assertIsNone(self.reserva.apartado_demanda)
        self.assertFalse(self.reserva.stripe_payment_intent_id)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_cupo_por_tamano_grupo_devuelve_motivo_sin_panga(self, payment_intents):
        # Flota con solo una panga de capacidad 3
        self.empresa.embarcaciones.all().delete()
        self.empresa.embarcaciones.create(
            nombre='Panga Chica',
            capacidad_maxima=3,
            activa=True,
        )
        self.reserva.numero_personas = 4
        self.reserva.save(update_fields=['numero_personas'])

        resp = self.post_pago()

        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertEqual(data.get('codigo'), 'sin_cupo')
        self.assertEqual(data.get('motivo'), 'sin_panga')
        self.assertIn('detail', data)
        payment_intents.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_cupo_hospedaje_devuelve_409_con_proxima_disponible_null(
        self, payment_intents
    ):
        servicio_hotel = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Hotel Cabaña del Sol',
            slug='hotel-cabana-sol',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            estrategia_precio='por_noche',
            precio_base=Decimal('2000.00'),
        )
        recurso = Recurso.objects.create(
            empresa=self.empresa,
            servicio=servicio_hotel,
            nombre='Cabaña Única',
            capacidad_maxima=2,
            activo=True,
        )
        check_in = date.today() + timedelta(days=10)
        check_out = date.today() + timedelta(days=13)

        # Reserva que ya ocupa la cabaña
        otra_reserva = Reserva.objects.create(
            empresa=self.empresa,
            servicio=servicio_hotel,
            fecha=check_in,
            fecha_salida=check_out,
            numero_personas=2,
            nombre_cliente='Beatriz Lopez',
            telefono_cliente='+5216129876543',
            correo_cliente='beatriz@example.com',
            moneda='MXN',
            estado=Reserva.Estado.PAGADA,
            checkout_id=uuid.uuid4(),
            deslinde_aceptado=True,
            deslinde_nombre='Beatriz Lopez',
        )
        ReservaOcupacion.objects.create(
            reserva=otra_reserva,
            recurso=recurso,
            empresa=self.empresa,
            fecha_inicio=check_in,
            fecha_fin=check_out,
            ocupa_cupo=True,
        )

        reserva_hotel = Reserva.objects.create(
            empresa=self.empresa,
            servicio=servicio_hotel,
            fecha=check_in,
            fecha_salida=check_out,
            numero_personas=2,
            nombre_cliente='Carlos Soto',
            telefono_cliente='+5216121112233',
            correo_cliente='carlos@example.com',
            moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=uuid.uuid4(),
            deslinde_aceptado=True,
            deslinde_nombre='Carlos Soto',
        )

        resp = self.post_pago(reserva=reserva_hotel)

        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertEqual(data.get('codigo'), 'sin_cupo')
        self.assertEqual(data.get('motivo'), 'sin_lugar')
        # Próxima disponible DEBE ser null para hospedaje
        self.assertIsNone(data.get('proxima_disponible'))
        payment_intents.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_sin_cupo_paquete_devuelve_409_con_proxima_disponible_null(
        self, payment_intents
    ):
        servicio_hotel = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Cabaña Paquete',
            slug='cabana-paquete',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            estrategia_precio='por_noche',
            precio_base=Decimal('1500.00'),
        )
        recurso = Recurso.objects.create(
            empresa=self.empresa,
            servicio=servicio_hotel,
            nombre='Habitación 1',
            capacidad_maxima=2,
            activo=True,
        )
        paquete = Paquete.objects.create(
            sede=self.empresa.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Mar y Noche',
            slug='paquete-mar-noche',
            precio_ancla=Decimal('7000.00'),
            estrategia_precio='por_grupo',
            permite_anticipo=False,
        )
        PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio,
            orden=1,
            dia_estancia=1,
            personas_incluidas=2,
            salidas=1,
        )
        PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=servicio_hotel,
            orden=2,
            dia_estancia=1,
            personas_incluidas=2,
            noches=1,
        )

        check_in = date.today() + timedelta(days=10)
        check_out = date.today() + timedelta(days=11)

        # Cabaña ocupada por otra reserva
        ocupante = Reserva.objects.create(
            empresa=self.empresa,
            servicio=servicio_hotel,
            fecha=check_in,
            fecha_salida=check_out,
            numero_personas=2,
            nombre_cliente='David Mora',
            telefono_cliente='+5216124445566',
            correo_cliente='david@example.com',
            moneda='MXN',
            estado=Reserva.Estado.PAGADA,
            checkout_id=uuid.uuid4(),
            deslinde_aceptado=True,
            deslinde_nombre='David Mora',
        )
        ReservaOcupacion.objects.create(
            reserva=ocupante,
            recurso=recurso,
            empresa=self.empresa,
            fecha_inicio=check_in,
            fecha_fin=check_out,
            ocupa_cupo=True,
        )

        reserva_paquete = Reserva.objects.create(
            empresa=self.empresa,
            paquete=paquete,
            fecha=check_in,
            inicio_paquete=check_in,
            fecha_salida=check_out,
            numero_personas=2,
            personas_por_servicio={
                str(self.servicio.pk): 2,
                str(servicio_hotel.pk): 2,
            },
            nombre_cliente='Elena Ramos',
            telefono_cliente='+5216127778899',
            correo_cliente='elena@example.com',
            moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=uuid.uuid4(),
            deslinde_aceptado=True,
            deslinde_nombre='Elena Ramos',
        )

        resp = self.post_pago(reserva=reserva_paquete)

        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertEqual(data.get('codigo'), 'sin_cupo')
        # Próxima disponible DEBE ser null para todos los paquetes
        self.assertIsNone(data.get('proxima_disponible'))
        payment_intents.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_renovacion_al_repetir_el_paso_renueva_minutos_completos(
        self, payment_intents
    ):
        payment_intents.create.return_value = intent_falso()
        resp1 = self.post_pago()
        self.assertEqual(resp1.status_code, 200)

        self.reserva.refresh_from_db()
        primer_vencimiento = self.reserva.apartado_hasta

        # Simular que el apartado está próximo a vencer en 2 minutos
        vencimiento_corto = timezone.now() + timedelta(minutes=2)
        self.reserva.apartado_hasta = vencimiento_corto
        self.reserva.save(update_fields=['apartado_hasta'])

        # Repetir el paso (reutiliza intent en status reutilizable)
        payment_intents.retrieve.return_value = intent_falso()
        antes_segundo = timezone.now()
        resp2 = self.post_pago()

        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()

        self.reserva.refresh_from_db()
        segundo_vencimiento = self.reserva.apartado_hasta

        # Se renueva por 15 minutos completos desde el momento de la llamada
        self.assertGreater(segundo_vencimiento, vencimiento_corto)
        self.assertGreaterEqual(
            segundo_vencimiento, antes_segundo + timedelta(minutes=14, seconds=55)
        )
        self.assertEqual(data2['apartado_hasta'], segundo_vencimiento.isoformat())

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_pasado_el_tope_no_se_renueva_el_apartado_pero_el_pago_sigue(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        self.assertEqual(self.post_pago().status_code, 200)
        vencimiento = timezone.now() + timedelta(minutes=2)
        Reserva.objects.filter(pk=self.reserva.pk).update(
            apartado_hasta=vencimiento, creado_en=timezone.now() - timedelta(minutes=50),
        )

        payment_intents.retrieve.return_value = intent_falso()
        resp = self.post_pago()

        self.assertEqual(resp.status_code, 200)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.apartado_hasta, vencimiento)  # no se movio
        self.assertEqual(resp.json()['apartado_hasta'], vencimiento.isoformat())

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_pasado_el_tope_no_se_crea_un_apartado_nuevo(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        Reserva.objects.filter(pk=self.reserva.pk).update(creado_en=timezone.now() - timedelta(minutes=50))

        resp = self.post_pago()

        self.assertEqual(resp.status_code, 200)
        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.apartado_hasta)
        self.assertIsNone(resp.json()['apartado_hasta'])

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_una_misma_persona_no_sostiene_mas_de_tres_apartados(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        for n in range(3):
            Reserva.objects.create(
                empresa=self.empresa, servicio=self.servicio, fecha=self.fecha_viaje + timedelta(days=n + 1),
                hora=time(6, 0), numero_personas=1, nombre_cliente='Ana Ruiz', telefono_cliente='+5210000000000',
                correo_cliente='ANA@example.com', moneda='MXN', estado=Reserva.Estado.PENDIENTE_PAGO,
                checkout_id=uuid.uuid4(), deslinde_aceptado=True, deslinde_nombre='Ana Ruiz',
                apartado_hasta=timezone.now() + timedelta(minutes=10),
                apartado_demanda={'v': 1, 'salidas': [], 'habitaciones': []},
            )

        resp = self.post_pago()

        self.assertEqual(resp.status_code, 200)
        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.apartado_hasta)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_otra_persona_no_cuenta_para_el_limite(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        for n in range(3):
            Reserva.objects.create(
                empresa=self.empresa, servicio=self.servicio, fecha=self.fecha_viaje + timedelta(days=n + 1),
                hora=time(6, 0), numero_personas=1, nombre_cliente='Otra', telefono_cliente='+5210000000001',
                correo_cliente='otra@example.com', moneda='MXN', estado=Reserva.Estado.PENDIENTE_PAGO,
                checkout_id=uuid.uuid4(), deslinde_aceptado=True, deslinde_nombre='Otra',
                apartado_hasta=timezone.now() + timedelta(minutes=10),
                apartado_demanda={'v': 1, 'salidas': [], 'habitaciones': []},
            )

        resp = self.post_pago()

        self.assertEqual(resp.status_code, 200)
        self.reserva.refresh_from_db()
        self.assertIsNotNone(self.reserva.apartado_hasta)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_un_apartado_activo_bloquea_a_otra_reserva(self, payment_intents):
        # Configurar la flota para que solo quepa 1 viaje
        self.empresa.embarcaciones.all().delete()
        self.empresa.embarcaciones.create(
            nombre='Panga Única',
            capacidad_maxima=3,
            activa=True,
        )

        payment_intents.create.return_value = intent_falso(id='pi_cliente_a')
        # Cliente A toma el apartado
        resp_a = self.post_pago()
        self.assertEqual(resp_a.status_code, 200)

        # Cliente B intenta apartar para la misma fecha
        reserva_b = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio,
            fecha=self.fecha_viaje,
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Fernando Diaz',
            telefono_cliente='+5216123334455',
            correo_cliente='fernando@example.com',
            moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=uuid.uuid4(),
            deslinde_aceptado=True,
            deslinde_nombre='Fernando Diaz',
        )

        resp_b = self.post_pago(reserva=reserva_b)
        self.assertEqual(resp_b.status_code, 409)
        data_b = resp_b.json()
        self.assertEqual(data_b.get('codigo'), 'sin_cupo')
        # Cliente B no crea PaymentIntent
        self.assertEqual(payment_intents.create.call_count, 1)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_error_403_checkout_invalido(self, payment_intents):
        otro_id = uuid.uuid4()
        resp = self.post_pago(checkout_id=str(otro_id))

        self.assertEqual(resp.status_code, 403)
        self.assertEqual(
            resp.json(),
            {
                'detail': 'checkout_id invalido para esta reserva.',
                'codigo': 'checkout_invalido',
            },
        )
        payment_intents.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_error_409_ya_no_pendiente(self, payment_intents):
        self.reserva.estado = Reserva.Estado.CANCELADA
        self.reserva.save(update_fields=['estado'])

        resp = self.post_pago()

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            resp.json(),
            {
                'detail': 'Esta reserva ya no esta pendiente de pago.',
                'codigo': 'ya_no_pendiente',
            },
        )
        payment_intents.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_error_409_pago_en_curso_salida_temprana_bloque_a(self, payment_intents):
        self.reserva.stripe_payment_intent_id = 'pi_en_curso'
        self.reserva.save(update_fields=['stripe_payment_intent_id'])

        payment_intents.retrieve.return_value = intent_falso(
            id='pi_en_curso', status='processing'
        )

        resp = self.post_pago()

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            resp.json(),
            {
                'detail': 'Ya hay un cobro en curso para esta reserva.',
                'codigo': 'pago_en_curso',
            },
        )
        # Bloque B no se ejecuta ni se crea nuevo intent
        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.apartado_hasta)
        payment_intents.create.assert_not_called()

    @override_settings(APARTADO_MINUTOS=0)
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_apartado_minutos_cero_conserva_comportamiento_previo(
        self, payment_intents
    ):
        payment_intents.create.return_value = intent_falso()
        # Con cupo_maximo=0, si el apartado estuviera activo rechazaría con 409.
        # Con APARTADO_MINUTOS=0 no valida cupo en crear-pago y responde 200.
        CupoDiario.objects.create(
            empresa=self.empresa,
            fecha=self.fecha_viaje,
            cupo_maximo=0,
        )

        resp = self.post_pago()

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data['apartado_hasta'])
        self.assertEqual(data['monto_a_cobrar'], '4500.00')
        self.assertEqual(data['precio_total'], '4500.00')
        self.assertEqual(data['moneda'], 'MXN')
        self.assertEqual(data['client_secret'], 'pi_1_secret')

        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.apartado_hasta)
        self.assertIsNone(self.reserva.apartado_demanda)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_servicio_bajo_demanda_no_aparta(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        servicio_transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Aeropuerto',
            slug='traslado-aeropuerto',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_persona',
            precio_base=Decimal('800.00'),
        )
        reserva_traslado = Reserva.objects.create(
            empresa=self.empresa,
            servicio=servicio_transporte,
            fecha=self.fecha_viaje,
            hora=time(10, 0),
            numero_personas=2,
            nombre_cliente='Gabriel Soto',
            telefono_cliente='+5216128889900',
            correo_cliente='gabriel@example.com',
            moneda='MXN',
            estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=uuid.uuid4(),
            deslinde_aceptado=True,
            deslinde_nombre='Gabriel Soto',
        )

        resp = self.post_pago(reserva=reserva_traslado)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data['apartado_hasta'])

        reserva_traslado.refresh_from_db()
        self.assertIsNone(reserva_traslado.apartado_hasta)
        self.assertIsNone(reserva_traslado.apartado_demanda)

    def test_editar_reserva_por_checkout_borra_apartado_si_cambia_campo_cupo(self):
        # Simular reserva con apartado vigente
        self.reserva.apartado_hasta = timezone.now() + timedelta(minutes=15)
        self.reserva.apartado_demanda = {'v': 1, 'salidas': [{'fecha': str(self.fecha_viaje), 'personas': 2}]}
        self.reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        nueva_fecha = self.fecha_viaje + timedelta(days=2)
        serializer = ReservaCheckoutSerializer(
            instance=self.reserva,
            data={
                'checkout_id': self.reserva.checkout_id,
                'fecha': nueva_fecha,
                'hora': '06:00',
                'numero_personas': 2,
                'nombre_cliente': 'Ana Ruiz',
                'telefono_cliente': '+5216121234567',
                'correo_cliente': 'ana@example.com',
                'moneda': 'MXN',
                'servicio': self.servicio.slug,
                'deslinde_aceptado': True,
                'deslinde_nombre': 'Ana Ruiz',
            },
            context={'request': mock.Mock(META={}), 'empresa': self.empresa},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.apartado_hasta)
        self.assertIsNone(self.reserva.apartado_demanda)
        self.assertEqual(self.reserva.fecha, nueva_fecha)

    def test_editar_reserva_por_checkout_conserva_apartado_si_no_cambian_campos_cupo(self):
        # Simular reserva con apartado vigente
        vencimiento = timezone.now() + timedelta(minutes=15)
        demanda = {'v': 1, 'salidas': [{'fecha': str(self.fecha_viaje), 'personas': 2}]}
        self.reserva.apartado_hasta = vencimiento
        self.reserva.apartado_demanda = demanda
        self.reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        # Solo cambia el nombre del cliente
        serializer = ReservaCheckoutSerializer(
            instance=self.reserva,
            data={
                'checkout_id': self.reserva.checkout_id,
                'fecha': self.fecha_viaje,
                'hora': '06:00',
                'numero_personas': 2,
                'nombre_cliente': 'Ana Maria Ruiz',
                'telefono_cliente': '+5216121234567',
                'correo_cliente': 'ana@example.com',
                'moneda': 'MXN',
                'servicio': self.servicio.slug,
                'deslinde_aceptado': True,
                'deslinde_nombre': 'Ana Ruiz',
            },
            context={'request': mock.Mock(META={}), 'empresa': self.empresa},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.nombre_cliente, 'Ana Maria Ruiz')
        self.assertIsNotNone(self.reserva.apartado_hasta)
        self.assertIsNotNone(self.reserva.apartado_demanda)
