"""Concurrencia del apartado temporal de cupo (spec §5, pruebas a-i).

Solo corren en Postgres: sqlite serializa toda escritura y los candados
(`pg_advisory_xact_lock`, `select_for_update`, `lock_timeout`) son no-ops ahi.
Cada hilo abre su propia conexion y pega a `crear-pago` por HTTP, igual que dos
navegadores. Stripe va simulado a nivel de clase (`StripeClient.payment_intents`),
asi que el mock vale para todos los hilos.
"""
import threading
import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock

import stripe
from django.core.cache import cache
from django.db import connections
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from stripe import StripeClient

from apps.bookings.cupo.candado import bloquear_cupo
from apps.fleet.models import Paquete, PaqueteServicio, Recurso, Servicio
from apps.tenancy import scope
from apps.testing import crear_flota, crear_servicio_pesca

from .models import CUPO_MAXIMO_DEFAULT, Reserva
from .tests_concurrencia import SOLO_POSTGRES, _crear_empresa_de_prueba, _datos, _intent_falso

LLAVES = {'STRIPE_SECRET_KEY': 'sk_test_falsa', 'STRIPE_WEBHOOK_SECRET': 'whsec_falsa'}
ESPERA = 60


def _intent(id='pi_conc', amount=450000, status='requires_payment_method'):
    return mock.Mock(id=id, amount=amount, currency='mxn', status=status, client_secret=f'{id}_secret')


@SOLO_POSTGRES
@override_settings(APARTADO_MINUTOS=15, **LLAVES)
class _ConcurrenciaBase(TransactionTestCase):
    def setUp(self):
        cache.clear()  # el throttle de 'pagos' vive en el cache y no se reinicia solo
        self.empresa = _crear_empresa_de_prueba()
        with scope.con_empresa(self.empresa):
            self.empresa.stripe_secret_key = 'sk_test_falsa'
            self.empresa.stripe_publishable_key = 'pk_test_falsa'
            self.empresa.save(update_fields=['stripe_secret_key', 'stripe_publishable_key'])
            crear_flota(self.empresa)
            self.servicio = crear_servicio_pesca(
                self.empresa, precio_base=Decimal('4500.00'), precio_persona_extra=Decimal('500.00'),
            )
        self.fecha = date.today() + timedelta(days=10)

    # ---- datos ----
    def _llenar_dia(self, lugares_libres):
        with scope.con_empresa(self.empresa):
            for _ in range(CUPO_MAXIMO_DEFAULT - lugares_libres):
                reserva = Reserva(**_datos(
                    self.empresa, servicio=self.servicio, fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                ))
                reserva.full_clean()
                reserva.save()

    def _pendiente(self, nombre, **extra):
        with scope.con_empresa(self.empresa):
            datos = _datos(
                self.empresa, servicio=self.servicio, fecha=self.fecha, nombre_cliente=nombre,
                precio_total=Decimal('4500.00'), forma_pago=Reserva.FormaPago.COMPLETO,
                estado=Reserva.Estado.PENDIENTE_PAGO, checkout_id=uuid.uuid4(),
            )
            datos.update(extra)
            reserva = Reserva(**datos)
            reserva.full_clean()
            reserva.save()
            return reserva

    def _recargar(self, reserva):
        with scope.con_empresa(self.empresa):
            return Reserva.objects.get(pk=reserva.pk)

    # ---- peticiones ----
    def _post(self, reserva):
        url = reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva.pk})
        return Client().post(
            url, {'forma_pago': 'completo', 'checkout_id': str(reserva.checkout_id)},
            content_type='application/json',
        )

    def _hilos(self, *tareas, sincronizar=True):
        """Corre cada tarea en su hilo (y su conexion). Con `sincronizar` todas arrancan a la vez."""
        resultados = [None] * len(tareas)
        errores = [None] * len(tareas)
        arranque = threading.Barrier(len(tareas)) if sincronizar else None

        def correr(i):
            try:
                if arranque is not None:
                    arranque.wait(timeout=10)
                resultados[i] = tareas[i]()
            except Exception as exc:  # noqa: BLE001 -- se re-lanza en el hilo principal
                errores[i] = exc
            finally:
                connections.close_all()  # sin esto TransactionTestCase no puede truncar al terminar

        hilos = [threading.Thread(target=correr, args=(i,)) for i in range(len(tareas))]
        for h in hilos:
            h.start()
        return hilos, resultados, errores

    def _esperar(self, hilos, errores):
        for h in hilos:
            h.join(timeout=ESPERA)
            self.assertFalse(h.is_alive(), 'un hilo no termino: posible bloqueo')
        for e in errores:
            if e is not None:
                raise e

    def _paralelo(self, *tareas):
        hilos, resultados, errores = self._hilos(*tareas)
        self._esperar(hilos, errores)
        return resultados


class ApartadoPescaConcurrenteTests(_ConcurrenciaBase):
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_a_dos_crear_pago_por_el_ultimo_lugar_solo_uno_pasa(self, pi):
        """(a) Exactamente uno recibe 200 y el otro 409 sin_cupo; Stripe se llama una vez."""
        pi.create.return_value = _intent()
        self._llenar_dia(1)
        r1, r2 = self._pendiente('Cliente Uno'), self._pendiente('Cliente Dos')

        respuestas = self._paralelo(lambda: self._post(r1), lambda: self._post(r2))

        self.assertEqual(sorted(r.status_code for r in respuestas), [200, 409])
        perdedora = next(r for r in respuestas if r.status_code == 409)
        self.assertEqual(perdedora.json()['codigo'], 'sin_cupo')
        self.assertEqual(pi.create.call_count, 1)
        con_apartado = [r for r in (self._recargar(r1), self._recargar(r2)) if r.apartado_hasta]
        self.assertEqual(len(con_apartado), 1)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_d_el_candado_se_libera_antes_de_llamar_a_stripe(self, pi):
        """(d) Mientras la primera llamada esta DENTRO de Stripe, una segunda toma el candado y termina."""
        en_stripe, soltar, llamadas = threading.Event(), threading.Event(), []

        def crear(*args, **kwargs):
            n = len(llamadas)
            llamadas.append(n)
            if n == 0:
                en_stripe.set()
                soltar.wait(ESPERA)
            return _intent(id=f'pi_d{n}')

        pi.create.side_effect = crear
        self._llenar_dia(2)
        r1, r2 = self._pendiente('Cliente Uno'), self._pendiente('Cliente Dos')

        hilos1, res1, err1 = self._hilos(lambda: self._post(r1), sincronizar=False)
        try:
            self.assertTrue(en_stripe.wait(30), 'la primera llamada nunca llego a Stripe')
            hilos2, res2, err2 = self._hilos(lambda: self._post(r2), sincronizar=False)
            self._esperar(hilos2, err2)
            # Si el candado siguiera tomado, esta tardaria el lock_timeout de 5 s y daria 503.
            self.assertEqual(res2[0].status_code, 200)
        finally:
            soltar.set()
        self._esperar(hilos1, err1)
        self.assertEqual(res1[0].status_code, 200)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_e_pago_en_curso_no_toca_el_apartado(self, pi):
        """(e) Con el PaymentIntent en processing/succeeded se responde 409 y el apartado queda igual."""
        for estado in ('processing', 'succeeded'):
            with self.subTest(estado=estado):
                pi.retrieve.return_value = _intent(id='pi_e', status=estado)
                reserva = self._pendiente(
                    'Cliente Uno', stripe_payment_intent_id='pi_e',
                    apartado_hasta=timezone.now() + timedelta(minutes=10),
                    apartado_demanda={'v': 1, 'salidas': [], 'habitaciones': []},
                )
                antes = self._recargar(reserva)

                respuesta = self._post(reserva)

                self.assertEqual(respuesta.status_code, 409)
                self.assertEqual(respuesta.json()['codigo'], 'pago_en_curso')
                despues = self._recargar(reserva)
                self.assertEqual(despues.apartado_hasta, antes.apartado_hasta)
                self.assertEqual(despues.apartado_demanda, antes.apartado_demanda)
                pi.create.assert_not_called()

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_g_liberar_tras_un_fallo_de_stripe_no_borra_el_apartado_renovado(self, pi):
        """(g) La llamada 1 falla en Stripe despues de que la 2 renovo: su liberacion es condicional."""
        en_stripe, soltar, llamadas = threading.Event(), threading.Event(), []

        def crear(*args, **kwargs):
            n = len(llamadas)
            llamadas.append(n)
            if n == 0:
                en_stripe.set()
                soltar.wait(ESPERA)
                raise stripe.APIConnectionError('red caida')
            return _intent(id='pi_g')

        pi.create.side_effect = crear
        pi.retrieve.return_value = _intent(id='pi_g')
        reserva = self._pendiente('Cliente Uno')

        hilos1, res1, err1 = self._hilos(lambda: self._post(reserva), sincronizar=False)
        try:
            self.assertTrue(en_stripe.wait(30))
            hilos2, res2, err2 = self._hilos(lambda: self._post(reserva), sincronizar=False)
            self._esperar(hilos2, err2)
            self.assertEqual(res2[0].status_code, 200)
        finally:
            soltar.set()
        self._esperar(hilos1, err1)

        self.assertEqual(res1[0].status_code, 502)
        renovado = self._recargar(reserva)
        self.assertIsNotNone(renovado.apartado_hasta, 'la liberacion de la llamada 1 borro el apartado renovado')
        self.assertEqual(renovado.apartado_hasta.isoformat(), res2[0].json()['apartado_hasta'])

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_h_candado_no_obtenido_a_tiempo_responde_503_reintentar(self, pi):
        """(h) Con el candado del dia ocupado, crear-pago agota su lock_timeout y pide reintentar."""
        pi.create.return_value = _intent()
        reserva = self._pendiente('Cliente Uno')

        with scope.con_empresa(self.empresa):  # abre una transaccion que conserva el candado
            bloquear_cupo(self.empresa.pk, self.fecha, servicio_id=self.servicio.pk)
            hilos, res, err = self._hilos(lambda: self._post(reserva), sincronizar=False)
            self._esperar(hilos, err)

        self.assertEqual(res[0].status_code, 503)
        self.assertEqual(res[0].json()['codigo'], 'reintentar')
        pi.create.assert_not_called()
        self.assertIsNone(self._recargar(reserva).apartado_hasta)

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_i_el_intent_pasa_a_processing_entre_el_bloque_a_y_el_c(self, pi):
        """(i) Responde pago_en_curso y el apartado ya tomado NO se libera."""
        lecturas = []

        def retrieve(*args, **kwargs):
            lecturas.append(1)
            # 1a lectura (Bloque A): sin cobrar. Las siguientes (Bloque C): ya procesando.
            return _intent(id='pi_i', status='requires_payment_method' if len(lecturas) == 1 else 'processing')

        pi.retrieve.side_effect = retrieve
        reserva = self._pendiente('Cliente Uno', stripe_payment_intent_id='pi_i')

        respuesta = self._post(reserva)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()['codigo'], 'pago_en_curso')
        self.assertIsNotNone(self._recargar(reserva).apartado_hasta)
        pi.create.assert_not_called()

    @mock.patch.object(StripeClient, 'refunds')
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_f_renovar_a_la_vez_que_llega_el_webhook_no_produce_deadlock(self, pi, refunds):
        """(f) Renovacion y webhook sobre la misma reserva terminan sin bloquearse y la reserva queda pagada."""
        from apps.payments.services import aplicar_pago_exitoso

        pi.create.return_value = _intent(id='pi_f')
        pi.retrieve.return_value = _intent(id='pi_f')
        reserva = self._pendiente('Cliente Uno', stripe_payment_intent_id='pi_f')
        intent_pagado = _intent_falso(reserva)
        empresa_id = self.empresa.pk

        def webhook():
            from apps.tenancy.models import Empresa
            empresa = Empresa.objects.get(pk=empresa_id)
            with scope.con_empresa(empresa):
                return aplicar_pago_exitoso(intent_pagado, empresa)

        respuestas = self._paralelo(lambda: self._post(reserva), webhook)

        self.assertIn(respuestas[0].status_code, (200, 409))
        final = self._recargar(reserva)
        self.assertEqual(final.estado, Reserva.Estado.PAGADA)
        self.assertIsNone(final.apartado_hasta)
        self.assertIsNone(final.apartado_demanda)


class ApartadoHospedajeConcurrenteTests(_ConcurrenciaBase):
    def setUp(self):
        super().setUp()
        with scope.con_empresa(self.empresa):
            self.hotel = Servicio.objects.create(
                empresa=self.empresa, nombre='Hotel Prueba', slug='hotel-prueba',
                tipo_servicio='hospedaje', estrategia_cupo='por_noche', precio_base=Decimal('2500'),
            )
            Recurso.objects.create(
                empresa=self.empresa, servicio=self.hotel, nombre='Cabana Unica',
                capacidad_maxima=4, activo=True,
            )

    def _reserva_hotel(self, nombre):
        with scope.con_empresa(self.empresa):
            return Reserva.objects.create(**_datos(
                self.empresa, servicio=self.hotel, fecha=self.fecha, fecha_salida=self.fecha + timedelta(days=3),
                hora=time(14, 0), nombre_cliente=nombre, estado=Reserva.Estado.PENDIENTE_PAGO,
                checkout_id=uuid.uuid4(), precio_total=Decimal('7500.00'), forma_pago=Reserva.FormaPago.COMPLETO,
            ))

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_b_dos_crear_pago_por_la_ultima_habitacion_solo_uno_pasa(self, pi):
        """(b) Una sola cabana y dos clientes: uno 200, otro 409 sin_cupo."""
        pi.create.return_value = _intent(amount=750000)
        r1, r2 = self._reserva_hotel('Cliente Uno'), self._reserva_hotel('Cliente Dos')

        respuestas = self._paralelo(lambda: self._post(r1), lambda: self._post(r2))

        self.assertEqual(sorted(r.status_code for r in respuestas), [200, 409])
        perdedora = next(r for r in respuestas if r.status_code == 409)
        self.assertEqual(perdedora.json()['codigo'], 'sin_cupo')
        self.assertEqual(
            len([r for r in (self._recargar(r1), self._recargar(r2)) if r.apartado_hasta]), 1,
        )

    @mock.patch.object(StripeClient, 'payment_intents')
    def test_c_paquete_con_mar_y_hospedaje_no_deja_apartados_a_medias(self, pi):
        """(c) Dos paquetes mar + hospedaje por la misma cabana: el que pierde no deja apartado alguno."""
        pi.create.return_value = _intent(amount=700000)
        with scope.con_empresa(self.empresa):
            paquete = Paquete.objects.create(
                sede=self.empresa.sede, empresa_lider=self.empresa, nombre='Paquete Pesca y Cabana',
                slug='paquete-pesca-cabana', precio_ancla=Decimal('7000'),
            )
            PaqueteServicio.objects.create(paquete=paquete, servicio=self.servicio, orden=1, salidas=1, dia_estancia=1)
            PaqueteServicio.objects.create(
                paquete=paquete, servicio=self.hotel, orden=2, noches=3, dia_estancia=1,
            )

            def paquete_pendiente(nombre):
                return Reserva.objects.create(**_datos(
                    self.empresa, paquete=paquete, fecha=self.fecha, fecha_salida=self.fecha + timedelta(days=3),
                    hora=time(6, 0), nombre_cliente=nombre, estado=Reserva.Estado.PENDIENTE_PAGO,
                    checkout_id=uuid.uuid4(), precio_total=Decimal('7000.00'),
                    forma_pago=Reserva.FormaPago.COMPLETO,
                ))

            r1, r2 = paquete_pendiente('Cliente Uno'), paquete_pendiente('Cliente Dos')

        respuestas = self._paralelo(lambda: self._post(r1), lambda: self._post(r2))

        self.assertEqual(sorted(r.status_code for r in respuestas), [200, 409])
        for reserva in (self._recargar(r1), self._recargar(r2)):
            # O tiene el retrato completo (mar + habitacion) o no tiene nada: nunca la mitad.
            if reserva.apartado_hasta is None:
                self.assertIsNone(reserva.apartado_demanda)
            else:
                self.assertEqual(len(reserva.apartado_demanda['habitaciones']), 1)
                self.assertGreaterEqual(len(reserva.apartado_demanda['salidas']), 1)
