"""Servicio de reagendado (`apps/bookings/reagendar.py`).

El servicio solo asigna campos, toma candados y deja que `Reserva.clean()` y el motor de cupo decidan: aqui se
prueba que respeta esas reglas, que sus dos excepciones al modelo (48 h con autorizacion, codigo promocional ya
vencido) no se filtran al formulario normal del admin, y que lo que no es suyo (precio, cobro) no se mueve.
Las carreras entre dos operadoras viven en `tests_reagendar_carreras.py` (solo Postgres).
"""
from datetime import time, timedelta
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.fleet.models import Capitan, CodigoPromocional, Embarcacion, Paquete
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .models import MovimientoDinero, Orden, Reserva
from .reagendar import (
    ESTADOS_REAGENDABLES, AntesDelCambio, ErrorDeReagendado, motivo_no_reagendable, puede_reagendarse, reagendar,
    token_de,
)


class ReagendarBase(EmpresaTestCase):
    """Una empresa con su flota, el servicio de pesca y dos personas con rol (jefa y vendedora)."""

    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.pesca = crear_servicio_pesca(self.empresa)
        self.jefa = self.crear_jefe('jefa-reagendar')
        self.vendedora = self.crear_vendedora('vendedora-reagendar')
        self.hoy = timezone.localdate()

    def datos_de_reserva(self, **extra):
        datos = dict(
            empresa=self.empresa, servicio=self.pesca, fecha=self.hoy + timedelta(days=10),
            hora=time(6, 0), numero_personas=2, nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
            deslinde_nombre='Ana Ruiz', estado=Reserva.Estado.PAGADA, moneda='MXN',
            precio_total=Decimal('4500.00'), monto_pagado=Decimal('4500.00'),
            forma_pago=Reserva.FormaPago.COMPLETO,
        )
        datos.update(extra)
        return datos

    def crear_reserva(self, **extra):
        reserva = Reserva(**self.datos_de_reserva(**extra))
        reserva.full_clean()
        reserva.save()
        # Como la entrega el admin: cargada de la base, con sus "originales" tomados por `from_db`.
        return Reserva.objects.get(pk=reserva.pk)

    def mover(self, reserva, nueva_fecha, **extra):
        """Reagenda con los valores de una vendedora que no autoriza nada y no avisa al cliente."""
        argumentos = dict(
            nueva_fecha=nueva_fecha, nueva_hora=reserva.hora, nueva_fecha_regreso=None, token=token_de(reserva),
            usuario=self.vendedora, puede_autorizar_48h=False, motivo_excepcion='', avisar_cliente=False,
        )
        argumentos.update(extra)
        return reagendar(reserva.pk, **argumentos)

    def como_jefa(self, **extra):
        return dict(usuario=self.jefa, puede_autorizar_48h=True, **extra)

    def recargar(self, reserva):
        return Reserva.objects.get(pk=reserva.pk)

    def asignar(self, reserva, panga=None, capitan=None):
        """Panga y/o capitan con `save()` completo, como lo haria la Agenda."""
        reserva = self.recargar(reserva)
        reserva.embarcacion = panga
        reserva.capitan = capitan
        reserva.full_clean()
        reserva.save()
        return self.recargar(reserva)

    def capitan(self, nombre='Capitan Beto'):
        return Capitan.objects.create(empresa=self.empresa, nombre=nombre, telefono='6121234567')


class ExcepcionesDelModeloTests(ReagendarBase):
    """Los dos ganchos que el servicio le pone al modelo no cambian el formulario normal."""

    def test_sin_el_gancho_el_modelo_sigue_exigiendo_48_horas(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))
        reserva.fecha = self.hoy + timedelta(days=9)

        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()

        self.assertIn('fecha', ctx.exception.error_dict)

    def test_con_la_excepcion_de_48_horas_el_modelo_deja_pasar_el_cambio(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))
        reserva.fecha = self.hoy + timedelta(days=9)
        reserva._excepcion_48h = True

        reserva.full_clean()  # no lanza

    def test_la_excepcion_de_48_horas_no_toca_las_demas_reglas_de_fecha(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))
        reserva.fecha = self.hoy + timedelta(days=9)
        reserva._excepcion_48h = True
        reserva.hora = reserva.hora.replace(hour=9)  # fuera de la ventana de pesca (5 a 7)

        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()

        self.assertIn('hora', ctx.exception.error_dict)

    def _reserva_con_codigo_vencido(self):
        codigo = CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO', porcentaje_descuento=Decimal('10'),
        )
        reserva = self.crear_reserva(
            codigo_promocional=codigo, descuento_aplicado=Decimal('450.00'),
            precio_total=Decimal('4050.00'), monto_pagado=Decimal('4050.00'),
        )
        CodigoPromocional.objects.filter(pk=codigo.pk).update(fecha_fin=timezone.now() - timedelta(days=1))
        return Reserva.objects.get(pk=reserva.pk)

    def test_un_codigo_promocional_vencido_ya_bloquea_cualquier_guardado_validado(self):
        # Fija el supuesto de D5: sin el gancho, reagendar fallaria por un codigo que el cliente ya uso.
        reserva = self._reserva_con_codigo_vencido()

        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()

        self.assertIn('codigo_promocional', ctx.exception.error_dict)

    def test_reagendando_no_vuelve_a_validar_el_codigo_promocional(self):
        reserva = self._reserva_con_codigo_vencido()
        reserva._reagendando = True

        reserva.full_clean()  # no lanza

    def test_los_ganchos_solo_existen_en_memoria(self):
        reserva = self.crear_reserva()
        reserva._excepcion_48h = True
        reserva._reagendando = True
        reserva.save()

        recargada = Reserva.objects.get(pk=reserva.pk)

        self.assertFalse(getattr(recargada, '_excepcion_48h', False))
        self.assertFalse(getattr(recargada, '_reagendando', False))


class EstadosReagendablesTests(ReagendarBase):
    def test_solo_pagada_y_asignada_son_reagendables(self):
        self.assertEqual(
            set(ESTADOS_REAGENDABLES), {Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA},
        )

    def test_una_pagada_se_puede_reagendar(self):
        reserva = self.crear_reserva()

        self.assertEqual(motivo_no_reagendable(reserva), '')
        self.assertTrue(puede_reagendarse(reserva))

    def test_una_asignada_se_puede_reagendar(self):
        reserva = self.asignar(self.crear_reserva(), panga=Embarcacion.objects.first())

        self.assertEqual(reserva.estado, Reserva.Estado.ASIGNADA)
        self.assertTrue(puede_reagendarse(reserva))

    def test_pendiente_cancelada_y_completada_no_se_reagendan_y_el_motivo_dice_por_que(self):
        for estado in (
            Reserva.Estado.PENDIENTE_PAGO, Reserva.Estado.CANCELADA, Reserva.Estado.COMPLETADA,
        ):
            with self.subTest(estado=estado):
                reserva = self.crear_reserva(estado=estado)
                motivo = motivo_no_reagendable(reserva)

                self.assertFalse(puede_reagendarse(reserva))
                self.assertIn('solo se reagendan reservas pagadas o asignadas', motivo)
                self.assertIn(estado.label.lower(), motivo.lower())

    def test_el_componente_de_una_orden_no_se_reagenda(self):
        reserva = self.crear_reserva()
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Dos empresas', slug='dos-empresas',
            precio_ancla=Decimal('9000.00'),
        )
        orden = Orden.objects.create(
            sede=self.sede, empresa_lider=self.empresa, paquete=paquete, nombre_cliente='Ana Ruiz',
            telefono_cliente='+5216121234567', correo_cliente='ana@example.com',
        )
        Reserva.objects.filter(pk=reserva.pk).update(orden=orden)

        reserva = self.recargar(reserva)

        self.assertFalse(puede_reagendarse(reserva))
        self.assertIn('paquete de varias empresas', motivo_no_reagendable(reserva))

    def test_una_reserva_en_disputa_no_se_reagenda(self):
        reserva = self.crear_reserva(en_disputa=True)

        self.assertFalse(puede_reagendarse(reserva))
        self.assertIn('en disputa con el banco', motivo_no_reagendable(reserva))

    def test_reagendar_una_no_reagendable_falla_y_no_cambia_nada(self):
        reserva = self.crear_reserva(estado=Reserva.Estado.CANCELADA)
        fecha = reserva.fecha

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, fecha + timedelta(days=3))

        self.assertIn('pagadas o asignadas', ctx.exception.mensaje)
        self.assertEqual(self.recargar(reserva).fecha, fecha)

    def test_reagendar_una_reserva_que_no_existe_falla_con_mensaje(self):
        reserva = self.crear_reserva()
        token = token_de(reserva)
        pk = reserva.pk
        reserva.delete()

        with self.assertRaises(ErrorDeReagendado) as ctx:
            reagendar(
                pk, nueva_fecha=self.hoy + timedelta(days=12), nueva_hora=time(6, 0), nueva_fecha_regreso=None,
                token=token, usuario=self.vendedora, puede_autorizar_48h=False, motivo_excepcion='',
                avisar_cliente=False,
            )

        self.assertIn('No se encontr', ctx.exception.mensaje)


class ReagendarServicioSueltoTests(ReagendarBase):
    def test_cambia_la_fecha_y_conserva_la_hora_cuando_no_se_pide_otra(self):
        reserva = self.crear_reserva()
        nueva = reserva.fecha + timedelta(days=5)

        resultado = self.mover(reserva, nueva, nueva_hora=None)

        guardada = self.recargar(reserva)
        self.assertEqual(guardada.fecha, nueva)
        self.assertEqual(guardada.hora, time(6, 0))
        self.assertEqual(resultado.reserva.pk, reserva.pk)
        self.assertEqual(guardada.estado, Reserva.Estado.PAGADA)

    def test_cambia_solo_la_hora_dentro_de_la_ventana(self):
        reserva = self.crear_reserva()

        self.mover(reserva, reserva.fecha, nueva_hora=time(5, 30))

        guardada = self.recargar(reserva)
        self.assertEqual(guardada.fecha, reserva.fecha)
        self.assertEqual(guardada.hora, time(5, 30))

    def test_el_resultado_trae_como_estaba_antes(self):
        reserva = self.asignar(
            self.crear_reserva(), panga=Embarcacion.objects.filter(capacidad_maxima=3).first(),
            capitan=self.capitan('Beto Cota'),
        )
        panga = reserva.embarcacion.nombre

        resultado = self.mover(reserva, reserva.fecha + timedelta(days=4))

        self.assertEqual(resultado.antes, AntesDelCambio(
            fecha=reserva.fecha, hora=time(6, 0), inicio_paquete=None, fecha_salida=None,
            fecha_regreso=None, panga=panga, capitan='Beto Cota',
        ))

    def test_el_antes_sin_asignar_trae_cadenas_vacias(self):
        reserva = self.crear_reserva()

        resultado = self.mover(reserva, reserva.fecha + timedelta(days=4))

        self.assertEqual((resultado.antes.panga, resultado.antes.capitan), ('', ''))

    def test_el_antes_es_inmutable(self):
        reserva = self.crear_reserva()
        resultado = self.mover(reserva, reserva.fecha + timedelta(days=4))

        with self.assertRaises(Exception):
            resultado.antes.fecha = self.hoy

    def test_precio_cobro_y_libro_de_dinero_no_se_mueven(self):
        reserva = self.crear_reserva(
            forma_pago=Reserva.FormaPago.ANTICIPO, monto_pagado=Decimal('1350.00'),
            monto_efectivo=Decimal('500.00'), efectivo_cobrado_en=timezone.now(),
            monto_transferencia=Decimal('200.00'), transferencia_registrada_en=timezone.now(),
        )
        dinero_antes = list(MovimientoDinero.objects.filter(reserva=reserva).values_list(
            'concepto', 'monto', 'fecha',
        ).order_by('pk'))
        columnas = ('precio_total', 'monto_pagado', 'monto_efectivo', 'monto_transferencia', 'iva_monto', 'moneda',
                    'descuento_aplicado', 'stripe_payment_intent_id')
        antes = {c: getattr(reserva, c) for c in columnas}
        self.assertTrue(dinero_antes)

        self.mover(reserva, reserva.fecha + timedelta(days=6))

        guardada = self.recargar(reserva)
        self.assertEqual({c: getattr(guardada, c) for c in columnas}, antes)
        self.assertEqual(
            list(MovimientoDinero.objects.filter(reserva=reserva).values_list(
                'concepto', 'monto', 'fecha',
            ).order_by('pk')),
            dinero_antes,
        )

    def test_otros_datos_de_la_reserva_quedan_como_estaban(self):
        reserva = self.crear_reserva()

        self.mover(reserva, reserva.fecha + timedelta(days=6))

        guardada = self.recargar(reserva)
        self.assertEqual(
            (guardada.nombre_cliente, guardada.correo_cliente, guardada.numero_personas, guardada.servicio_id),
            (reserva.nombre_cliente, reserva.correo_cliente, reserva.numero_personas, reserva.servicio_id),
        )

    def test_un_codigo_promocional_vencido_no_bloquea_el_reagendado(self):
        codigo = CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO', porcentaje_descuento=Decimal('10'),
        )
        reserva = self.crear_reserva(
            codigo_promocional=codigo, descuento_aplicado=Decimal('450.00'),
            precio_total=Decimal('4050.00'), monto_pagado=Decimal('4050.00'),
        )
        CodigoPromocional.objects.filter(pk=codigo.pk).update(fecha_fin=timezone.now() - timedelta(days=1))

        self.mover(self.recargar(reserva), reserva.fecha + timedelta(days=3))

        guardada = self.recargar(reserva)
        self.assertEqual(guardada.fecha, reserva.fecha + timedelta(days=3))
        self.assertEqual(guardada.precio_total, Decimal('4050.00'))

    def test_los_ganchos_no_se_filtran_a_la_siguiente_lectura_de_la_reserva(self):
        # El servicio trabaja sobre su propia lectura bloqueada: la reserva que otro codigo carga despues
        # sigue rigiendose por la regla de 48 h.
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))
        self.mover(reserva, self.hoy + timedelta(days=10), **self.como_jefa(motivo_excepcion='Cliente enfermo'))

        otra_vez = self.recargar(reserva)

        self.assertFalse(getattr(otra_vez, '_excepcion_48h', False))
        self.assertFalse(getattr(otra_vez, '_reagendando', False))


class ReagendarValidacionesTests(ReagendarBase):
    def test_pedir_lo_mismo_que_ya_tiene_falla(self):
        reserva = self.crear_reserva()

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, reserva.fecha)

        self.assertEqual(ctx.exception.campo, 'nueva_fecha')
        self.assertEqual(ctx.exception.mensaje, 'Elige una fecha u hora distinta de la actual.')

    def test_una_fecha_pasada_falla(self):
        reserva = self.crear_reserva()

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.hoy - timedelta(days=1))

        self.assertEqual(ctx.exception.campo, 'nueva_fecha')
        self.assertEqual(ctx.exception.mensaje, 'La nueva fecha ya pasó.')
        self.assertEqual(self.recargar(reserva).fecha, reserva.fecha)

    def test_una_fecha_pasada_falla_tambien_para_la_jefa(self):
        reserva = self.crear_reserva()

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.hoy - timedelta(days=1), **self.como_jefa(motivo_excepcion='Motivo valido aqui'))

        self.assertEqual(ctx.exception.mensaje, 'La nueva fecha ya pasó.')

    def test_a_mas_de_un_ano_falla(self):
        reserva = self.crear_reserva()

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.hoy + timedelta(days=366))

        self.assertEqual(ctx.exception.campo, 'nueva_fecha')
        self.assertEqual(ctx.exception.mensaje, 'La nueva fecha queda a más de un año. Revisa el año.')

    def test_exactamente_a_un_ano_si_se_puede(self):
        reserva = self.crear_reserva()

        self.mover(reserva, self.hoy + timedelta(days=365))

        self.assertEqual(self.recargar(reserva).fecha, self.hoy + timedelta(days=365))

    def test_una_hora_fuera_de_la_ventana_del_servicio_falla_en_su_campo(self):
        reserva = self.crear_reserva()

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, reserva.fecha + timedelta(days=2), nueva_hora=time(9, 0))

        self.assertEqual(ctx.exception.campo, 'nueva_hora')
        self.assertIn('05:00', ctx.exception.mensaje)
        self.assertIn('07:00', ctx.exception.mensaje)
        self.assertEqual(self.recargar(reserva).fecha, reserva.fecha)

    def test_ningun_fallo_deja_cambios_a_medias(self):
        reserva = self.crear_reserva()
        antes = (reserva.fecha, reserva.hora, reserva.estado, reserva.aviso_asignacion_enviado_en)

        for argumentos in (
            dict(nueva_fecha=self.hoy - timedelta(days=2)),
            dict(nueva_fecha=reserva.fecha + timedelta(days=2), nueva_hora=time(9, 0)),
        ):
            with self.assertRaises(ErrorDeReagendado):
                self.mover(reserva, **argumentos)

        guardada = self.recargar(reserva)
        self.assertEqual((guardada.fecha, guardada.hora, guardada.estado, guardada.aviso_asignacion_enviado_en), antes)


class ReglaDe48HorasTests(ReagendarBase):
    def test_la_vendedora_no_puede_mover_una_salida_que_esta_a_menos_de_48_horas(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.hoy + timedelta(days=10))

        self.assertEqual(ctx.exception.campo, 'nueva_fecha')
        self.assertIn('48 horas', ctx.exception.mensaje)
        self.assertIn('Pídele a un jefe que lo autorice.', ctx.exception.mensaje)
        self.assertEqual(self.recargar(reserva).fecha, self.hoy + timedelta(days=1))

    def test_la_jefa_con_motivo_puede_saltarla_y_queda_marcado(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))

        resultado = self.mover(
            reserva, self.hoy + timedelta(days=10), **self.como_jefa(motivo_excepcion='El cliente perdió su vuelo'),
        )

        self.assertTrue(resultado.excepcion_48h)
        self.assertEqual(self.recargar(reserva).fecha, self.hoy + timedelta(days=10))

    def test_la_jefa_sin_motivo_no_puede(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.hoy + timedelta(days=10), **self.como_jefa(motivo_excepcion=''))

        self.assertEqual(ctx.exception.campo, 'motivo_excepcion')
        self.assertEqual(self.recargar(reserva).fecha, self.hoy + timedelta(days=1))

    def test_el_motivo_de_la_excepcion_pide_entre_10_y_200_caracteres_sin_contar_espacios_de_mas(self):
        casos = {
            'corto': ('x' * 9, False),
            'solo espacios': (' ' * 25, False),
            'espacios que lo dejan corto': ('  ' + 'x' * 9 + '  ', False),
            'diez': ('x' * 10, True),
            'doscientos': ('x' * 200, True),
            'doscientos uno': ('x' * 201, False),
        }
        for nombre, (motivo, debe_pasar) in casos.items():
            with self.subTest(nombre):
                reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))
                if debe_pasar:
                    self.mover(reserva, self.hoy + timedelta(days=10), **self.como_jefa(motivo_excepcion=motivo))
                    self.assertEqual(self.recargar(reserva).fecha, self.hoy + timedelta(days=10))
                else:
                    with self.assertRaises(ErrorDeReagendado) as ctx:
                        self.mover(reserva, self.hoy + timedelta(days=10), **self.como_jefa(motivo_excepcion=motivo))
                    self.assertEqual(ctx.exception.campo, 'motivo_excepcion')
                    self.assertEqual(self.recargar(reserva).fecha, self.hoy + timedelta(days=1))

    def test_una_salida_que_ya_paso_solo_se_mueve_con_la_excepcion(self):
        reserva = self.crear_reserva(fecha=self.hoy - timedelta(days=3))

        with self.assertRaises(ErrorDeReagendado):
            self.mover(reserva, self.hoy + timedelta(days=10))

        resultado = self.mover(
            reserva, self.hoy + timedelta(days=10), **self.como_jefa(motivo_excepcion='Se cobró y nadie la repartió'),
        )
        self.assertTrue(resultado.excepcion_48h)

    def test_con_mas_de_48_horas_la_jefa_no_necesita_motivo_y_no_se_marca_excepcion(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=3))

        resultado = self.mover(reserva, self.hoy + timedelta(days=12), **self.como_jefa(motivo_excepcion=''))

        self.assertFalse(resultado.excepcion_48h)

    def test_la_vendedora_si_puede_cuando_faltan_mas_de_48_horas(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=3))

        resultado = self.mover(reserva, self.hoy + timedelta(days=12))

        self.assertFalse(resultado.excepcion_48h)

    def test_poder_autorizar_no_basta_si_el_motivo_es_solo_espacios(self):
        reserva = self.crear_reserva(fecha=self.hoy + timedelta(days=1))

        with self.assertRaises(ErrorDeReagendado):
            self.mover(reserva, self.hoy + timedelta(days=10), puede_autorizar_48h=True, motivo_excepcion='   ')


class TokenOptimistaTests(ReagendarBase):
    def test_si_alguien_movio_la_reserva_mientras_se_revisaba_falla_y_dice_como_esta_ahora(self):
        reserva = self.crear_reserva()
        token = token_de(reserva)
        Reserva.objects.filter(pk=reserva.pk).update(fecha=reserva.fecha + timedelta(days=1))
        ahora = reserva.fecha + timedelta(days=1)

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, reserva.fecha + timedelta(days=5), token=token)

        self.assertIn('cambió mientras la revisabas', ctx.exception.mensaje)
        self.assertIn(str(ahora), ctx.exception.mensaje)
        self.assertEqual(self.recargar(reserva).fecha, ahora)

    def test_un_cambio_de_hora_tambien_invalida_el_token(self):
        reserva = self.crear_reserva()
        token = token_de(reserva)
        Reserva.objects.filter(pk=reserva.pk).update(hora=time(5, 0))

        with self.assertRaises(ErrorDeReagendado):
            self.mover(reserva, reserva.fecha + timedelta(days=5), token=token)

    def test_un_cambio_de_estado_tambien_invalida_el_token(self):
        reserva = self.crear_reserva()
        token = token_de(reserva)
        Reserva.objects.filter(pk=reserva.pk).update(estado=Reserva.Estado.ASIGNADA)

        with self.assertRaises(ErrorDeReagendado):
            self.mover(reserva, reserva.fecha + timedelta(days=5), token=token)

    def test_asignar_la_panga_a_medias_de_la_revision_cuenta_como_cambio(self):
        reserva = self.crear_reserva()
        token = token_de(reserva)
        self.asignar(reserva, panga=Embarcacion.objects.first())

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, reserva.fecha + timedelta(days=5), token=token)

        self.assertIn('cambió mientras la revisabas', ctx.exception.mensaje)

    def test_sin_token_no_se_reagenda(self):
        reserva = self.crear_reserva()

        with self.assertRaises(ErrorDeReagendado):
            self.mover(reserva, reserva.fecha + timedelta(days=5), token=None)

        self.assertEqual(self.recargar(reserva).fecha, reserva.fecha)

    def test_el_token_acepta_lo_que_manda_el_formulario_como_texto(self):
        reserva = self.crear_reserva()
        token = {
            'fecha': reserva.fecha.isoformat(), 'hora': '06:00', 'inicio_paquete': '',
            'estado': Reserva.Estado.PAGADA.value,
        }

        self.mover(reserva, reserva.fecha + timedelta(days=5), token=token)

        self.assertEqual(self.recargar(reserva).fecha, reserva.fecha + timedelta(days=5))

    def test_el_token_de_una_reserva_sin_hora_ni_inicio_va_con_cadenas_vacias(self):
        reserva = self.crear_reserva(hora=None)

        self.assertEqual(token_de(reserva), {
            'fecha': reserva.fecha.isoformat(), 'hora': '', 'inicio_paquete': '', 'estado': 'pagada',
        })

    def test_enviar_dos_veces_el_mismo_formulario_solo_cambia_una_vez(self):
        reserva = self.crear_reserva()
        token = token_de(reserva)
        nueva = reserva.fecha + timedelta(days=5)
        with mock.patch('apps.bookings.reagendar._mandar_correo') as mandar:
            with self.captureOnCommitCallbacks(execute=True):
                self.mover(reserva, nueva, token=token, avisar_cliente=True)
                with self.assertRaises(ErrorDeReagendado):
                    self.mover(reserva, nueva, token=token, avisar_cliente=True)

        self.assertEqual(self.recargar(reserva).fecha, nueva)
        self.assertEqual(mandar.call_count, 1)
