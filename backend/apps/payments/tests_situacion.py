from decimal import Decimal

from django.test import SimpleTestCase

from apps.payments.situacion import Situacion, requiere_atencion, situacion_de_orden, situacion_de_reserva


class SituacionDeReservaTests(SimpleTestCase):
    def test_pendiente_sin_intent_es_sin_pago(self):
        self.assertEqual(
            situacion_de_reserva(estado='pendiente_pago', monto_pagado=None, monto_reembolsado=None),
            Situacion.SIN_PAGO,
        )

    def test_pendiente_con_intent_activo_es_pago_en_proceso(self):
        # Ya se intento cobrar (existe stripe_payment_intent_id): no ofrecer "Descartar"
        # como si nada hubiera pasado mientras el cobro puede seguir en curso.
        self.assertEqual(
            situacion_de_reserva(
                estado='pendiente_pago', monto_pagado=None, monto_reembolsado=None,
                tiene_intent_activo=True,
            ),
            Situacion.PAGO_EN_PROCESO,
        )

    def test_pagada_es_confirmada(self):
        for estado in ('pagada', 'asignada', 'completada'):
            with self.subTest(estado=estado):
                self.assertEqual(
                    situacion_de_reserva(estado=estado, monto_pagado=Decimal('4500'), monto_reembolsado=None),
                    Situacion.CONFIRMADA,
                )

    def test_cancelada_sin_cobro_es_liberada(self):
        self.assertEqual(
            situacion_de_reserva(estado='cancelada', monto_pagado=None, monto_reembolsado=None),
            Situacion.CANCELADA_LIBERADA,
        )

    def test_cancelada_con_cobro_sin_reembolso_requiere_atencion(self):
        s = situacion_de_reserva(estado='cancelada', monto_pagado=Decimal('4500'), monto_reembolsado=None)
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))

    def test_cancelada_con_reembolso_parcial_sigue_requiriendo_atencion(self):
        # Regresion del hallazgo #2 del review: un reembolso de $1 sobre $4500 pagados
        # NO es "ya solicitamos tu devolucion".
        s = situacion_de_reserva(estado='cancelada', monto_pagado=Decimal('4500'), monto_reembolsado=Decimal('1'))
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))

    def test_cancelada_con_reembolso_completo_ya_solicitado(self):
        s = situacion_de_reserva(estado='cancelada', monto_pagado=Decimal('4500'), monto_reembolsado=Decimal('4500'))
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_SOLICITADA)
        self.assertFalse(requiere_atencion(s))


def _pago(estado_pi=None, pagado=None, reembolsado=None):
    return {'estado_pi': estado_pi, 'monto_pagado': pagado, 'monto_reembolsado': reembolsado}


class SituacionDeOrdenTests(SimpleTestCase):
    def test_armando_es_sin_pago(self):
        self.assertEqual(situacion_de_orden(estado_orden='armando', pagos=[]), Situacion.SIN_PAGO)

    def test_autorizando_sin_ningun_intent_todavia_es_pago_en_proceso(self):
        pagos = [_pago(None), _pago(None)]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.PAGO_EN_PROCESO)

    def test_autorizando_con_ningun_pago_intentado_es_sin_pago(self):
        # Regresion: la orden ya existe y sus PaymentIntents se crearon, pero el cliente
        # aun no puso una tarjeta (`requires_payment_method` en todos). Decir "Tu banco
        # esta procesando tu pago" seria falso: nadie ha pagado nada.
        pagos = [_pago('requires_payment_method'), _pago('requires_payment_method')]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.SIN_PAGO)

    def test_autorizando_con_un_pago_en_proceso_real_sigue_siendo_pago_en_proceso(self):
        for estado_pi in ('processing', 'requires_action', 'requires_confirmation'):
            with self.subTest(estado_pi=estado_pi):
                pagos = [_pago(estado_pi), _pago('requires_payment_method')]
                self.assertEqual(
                    situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.PAGO_EN_PROCESO,
                )

    def test_autorizando_con_una_retenida_y_otra_pendiente_es_retenido_parcial(self):
        pagos = [_pago('requires_capture'), _pago('requires_payment_method')]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.RETENIDO_PARCIAL)

    def test_autorizando_con_todas_retenidas_es_confirmando_cobro(self):
        pagos = [_pago('requires_capture'), _pago('requires_capture')]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.CONFIRMANDO_COBRO)

    def test_autorizando_con_una_succeeded_y_otra_retenida_es_confirmando_cobro(self):
        # Regresion del hallazgo #4: antes esta combinacion volvia RETENIDO_PARCIAL,
        # como si al cliente le faltara pagar algo. Ambos pagos ya tienen dinero
        # comprometido (uno cobrado, el otro retenido); no hay nada pendiente de pagar.
        pagos = [_pago('succeeded', pagado=Decimal('6400')), _pago('requires_capture')]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.CONFIRMANDO_COBRO)

    def test_autorizando_con_todas_succeeded_es_confirmando_cobro(self):
        # Regresion del hallazgo #4: antes daba PAGO_EN_PROCESO (0 en requires_capture),
        # como si nadie hubiera pagado nada.
        pagos = [_pago('succeeded', pagado=Decimal('6400')), _pago('succeeded', pagado=Decimal('1650'))]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.CONFIRMANDO_COBRO)

    def test_autorizada_es_confirmando_cobro(self):
        self.assertEqual(situacion_de_orden(estado_orden='autorizada', pagos=[]), Situacion.CONFIRMANDO_COBRO)

    def test_capturada_es_confirmada(self):
        self.assertEqual(situacion_de_orden(estado_orden='capturada', pagos=[]), Situacion.CONFIRMADA)

    def test_cancelada_con_un_cobro_sin_reembolsar_requiere_atencion(self):
        pagos = [_pago(pagado=Decimal('6400')), _pago(pagado=None)]
        s = situacion_de_orden(estado_orden='cancelada', pagos=pagos)
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))

    def test_cancelada_con_reembolso_parcial_sigue_requiriendo_atencion(self):
        pagos = [_pago(pagado=Decimal('6400'), reembolsado=Decimal('1'))]
        s = situacion_de_orden(estado_orden='cancelada', pagos=pagos)
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))

    def test_cancelada_con_reembolso_confirmado(self):
        pagos = [_pago(pagado=Decimal('6400'), reembolsado=Decimal('6400'))]
        self.assertEqual(situacion_de_orden(estado_orden='cancelada', pagos=pagos), Situacion.CANCELADA_DEVOLUCION_SOLICITADA)

    def test_cancelada_sin_ningun_cobro_y_void_confirmado_es_liberada(self):
        pagos = [_pago('canceled'), _pago(None)]
        self.assertEqual(situacion_de_orden(estado_orden='cancelada', pagos=pagos), Situacion.CANCELADA_LIBERADA)

    def test_cancelada_con_void_fallido_no_es_liberada(self):
        # Regresion critica del hallazgo #2 del review (B:3390 original): si el
        # `payment_intents.cancel` fallo (StripeError atrapado en revertir_orden), el
        # PI real sigue en requires_capture. Nunca decir "se libero" en ese caso.
        pagos = [_pago('requires_capture'), _pago(None)]
        s = situacion_de_orden(estado_orden='cancelada', pagos=pagos)
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))
