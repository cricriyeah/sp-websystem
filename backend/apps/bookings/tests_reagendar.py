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
from django.db import OperationalError, transaction
from django.test import override_settings
from django.utils import timezone

from apps.fleet.enums import EstrategiaCupo, EstrategiaPrecio, TipoServicio, TipoTraslado, Zona
from apps.fleet.models import (
    Capitan, CodigoPromocional, Embarcacion, EmbarcacionNoDisponible, Paquete, PaqueteServicio, PuntoEncuentro,
    Recurso, Servicio, Vehiculo,
)
from apps.notifications import plantilla
from apps.tenancy.models import Notificacion
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .cupo import construir_retrato_servicio_suelto
from .cupo.confirmacion import reservar_cupo_al_confirmar
from .models import (
    CupoDiario, DetalleTransporte, MovimientoDinero, Orden, Reserva, ReservaOcupacion, ReservaSalida,
    ViajeTransporte, salida_aware,
)
from .reagendar import (
    ESTADOS_REAGENDABLES, MENSAJE_OCUPADO, AntesDelCambio, ErrorDeReagendado, Propuesta, motivo_no_reagendable,
    proponer, puede_reagendarse, reagendar, token_de,
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

    def plan(self, reserva, nueva_fecha, **extra):
        """`proponer` con la hora actual de la reserva, como la pantalla del paso 1."""
        argumentos = dict(nueva_hora=reserva.hora, nueva_fecha_regreso=None)
        argumentos.update(extra)
        return proponer(reserva, nueva_fecha=nueva_fecha, **argumentos)

    def dia(self, n):
        return self.hoy + timedelta(days=n)

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


class ProponerTests(ReagendarBase):
    """`proponer` es la vista previa del paso 1: solo lee, no toma candados y dice lo mismo que `reagendar`."""

    def test_no_cambia_la_reserva_ni_la_base(self):
        reserva = self.asignar(
            self.crear_reserva(), panga=Embarcacion.objects.filter(capacidad_maxima=3).first(), capitan=self.capitan(),
        )
        antes = (reserva.fecha, reserva.hora, reserva.embarcacion_id, reserva.capitan_id, reserva.estado)

        self.plan(reserva, reserva.fecha + timedelta(days=5))

        self.assertEqual((reserva.fecha, reserva.hora, reserva.embarcacion_id, reserva.capitan_id, reserva.estado), antes)
        guardada = self.recargar(reserva)
        self.assertEqual(
            (guardada.fecha, guardada.hora, guardada.embarcacion_id, guardada.capitan_id, guardada.estado), antes,
        )

    def test_no_toma_candados(self):
        reserva = self.crear_reserva()

        with mock.patch('apps.bookings.models.bloquear_cupo') as del_motor, \
                mock.patch('apps.bookings.reagendar.bloquear_cupo') as de_mar, \
                mock.patch('apps.bookings.reagendar.bloquear_recurso') as de_habitacion:
            self.plan(reserva, reserva.fecha + timedelta(days=5))

        for candado in (del_motor, de_mar, de_habitacion):
            candado.assert_not_called()

    def test_un_servicio_suelto_trae_sus_valores_derivados(self):
        reserva = self.crear_reserva()
        nueva = reserva.fecha + timedelta(days=5)

        propuesta = self.plan(reserva, nueva)

        self.assertIsInstance(propuesta, Propuesta)
        self.assertEqual(propuesta.errores, {})
        self.assertEqual((propuesta.fecha, propuesta.hora), (nueva, time(6, 0)))
        self.assertEqual(
            (propuesta.inicio_paquete, propuesta.fecha_salida, propuesta.fecha_regreso), (None, None, None),
        )
        self.assertEqual(propuesta.dias_de_mar, [nueva])
        self.assertEqual((propuesta.panga, propuesta.capitan, propuesta.motivo_panga), (None, None, ''))
        self.assertEqual(propuesta.vehiculos_a_quitar, 0)
        self.assertEqual((propuesta.motivo_sin_cupo, propuesta.proxima_fecha), (None, None))
        self.assertFalse(propuesta.requiere_excepcion_48h)
        self.assertEqual(propuesta.limite_48h, salida_aware(reserva.fecha, time(6, 0)) - timedelta(hours=48))

    def test_la_hora_nueva_viaja_en_la_propuesta(self):
        reserva = self.crear_reserva()

        propuesta = self.plan(reserva, reserva.fecha, nueva_hora=time(5, 30))

        self.assertEqual(propuesta.errores, {})
        self.assertEqual(propuesta.hora, time(5, 30))

    def test_las_entradas_invalidas_dicen_lo_mismo_que_reagendar(self):
        reserva = self.crear_reserva()
        casos = {
            'igual': dict(nueva_fecha=reserva.fecha),
            'pasada': dict(nueva_fecha=self.dia(-1)),
            'un ano': dict(nueva_fecha=self.dia(366)),
            'hora fuera de la ventana': dict(nueva_fecha=reserva.fecha + timedelta(days=2), nueva_hora=time(9, 0)),
        }
        for nombre, argumentos in casos.items():
            with self.subTest(nombre):
                with self.assertRaises(ErrorDeReagendado) as ctx:
                    self.mover(reserva, **argumentos)

                propuesta = self.plan(reserva, **argumentos)

                self.assertEqual(propuesta.errores, {ctx.exception.campo: ctx.exception.mensaje})

    def test_hoy_se_puede_inyectar(self):
        reserva = self.crear_reserva()

        propuesta = self.plan(reserva, self.dia(12), hoy=self.dia(20))

        self.assertEqual(propuesta.errores, {'nueva_fecha': 'La nueva fecha ya pasó.'})

    def test_una_reserva_que_no_se_puede_reagendar_lo_dice_como_error_general(self):
        reserva = self.crear_reserva(estado=Reserva.Estado.CANCELADA)

        propuesta = self.plan(reserva, reserva.fecha + timedelta(days=5))

        self.assertEqual(propuesta.errores, {'general': motivo_no_reagendable(reserva)})

    def test_faltar_menos_de_48_horas_no_es_un_error_es_una_marca(self):
        reserva = self.crear_reserva(fecha=self.dia(1))

        propuesta = self.plan(reserva, self.dia(10))

        self.assertEqual(propuesta.errores, {})
        self.assertTrue(propuesta.requiere_excepcion_48h)
        self.assertEqual(propuesta.limite_48h, salida_aware(self.dia(1), time(6, 0)) - timedelta(hours=48))

    def test_lleno_el_dia_pedido_dice_por_que_y_cual_es_la_proxima_fecha(self):
        reserva = self.crear_reserva()
        destino = reserva.fecha + timedelta(days=5)
        CupoDiario.objects.create(empresa=self.empresa, fecha=destino, cupo_maximo=1)
        self.crear_reserva(fecha=destino, nombre_cliente='Otra Persona')

        propuesta = self.plan(reserva, destino)

        self.assertEqual(set(propuesta.errores), {'nueva_fecha'})
        self.assertIn('se alcanzo el maximo de viajes del dia', propuesta.errores['nueva_fecha'])
        self.assertIn('se alcanzo el maximo de viajes del dia', propuesta.motivo_sin_cupo)
        self.assertEqual(propuesta.proxima_fecha, destino + timedelta(days=1))
        self.assertIn('La próxima fecha con lugar es', propuesta.errores['nueva_fecha'])

    def test_un_dia_con_lugar_no_trae_motivo_de_cupo(self):
        reserva = self.crear_reserva()

        propuesta = self.plan(reserva, reserva.fecha + timedelta(days=5))

        self.assertIsNone(propuesta.motivo_sin_cupo)
        self.assertIsNone(propuesta.proxima_fecha)

    def test_cambiar_solo_la_hora_no_vuelve_a_pedir_cupo(self):
        # Igual que el modelo (`_cupo_ya_validado`): el tope frena ventas nuevas, no lo ya vendido.
        reserva = self.crear_reserva()
        CupoDiario.objects.create(empresa=self.empresa, fecha=reserva.fecha, cupo_maximo=0)

        propuesta = self.plan(reserva, reserva.fecha, nueva_hora=time(5, 30))

        self.assertEqual(propuesta.errores, {})
        self.assertIsNone(propuesta.motivo_sin_cupo)


class CupoAlReagendarTests(ReagendarBase):
    """El cambio respeta el cupo: el motor decide, el servicio solo lo cuenta con la fila bloqueada."""

    def texto_del_dia(self, fecha):
        return f'{plantilla.DIAS[fecha.weekday()]} {fecha.day} de {plantilla.MESES[fecha.month - 1]} de {fecha.year}'

    def test_un_dia_lleno_falla_con_sin_cupo_y_ofrece_la_proxima_fecha(self):
        reserva = self.crear_reserva()
        destino = reserva.fecha + timedelta(days=5)
        CupoDiario.objects.create(empresa=self.empresa, fecha=destino, cupo_maximo=1)
        self.crear_reserva(fecha=destino, nombre_cliente='Otra Persona')

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, destino)

        self.assertEqual((ctx.exception.codigo, ctx.exception.campo), ('sin_cupo', 'nueva_fecha'))
        self.assertIn('No hay cupo disponible', ctx.exception.mensaje)
        self.assertIn(
            f'La próxima fecha con lugar es el {self.texto_del_dia(destino + timedelta(days=1))}.',
            ctx.exception.mensaje,
        )
        self.assertEqual(self.recargar(reserva).fecha, reserva.fecha)

    def test_un_cupo_diario_en_cero_cierra_el_dia(self):
        reserva = self.crear_reserva()
        destino = reserva.fecha + timedelta(days=5)
        CupoDiario.objects.create(empresa=self.empresa, fecha=destino, cupo_maximo=0)

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, destino)

        self.assertEqual(ctx.exception.codigo, 'sin_cupo')
        self.assertIn('maximo de viajes del dia', ctx.exception.mensaje)

    def test_sin_panga_donde_quepa_el_grupo_tambien_es_sin_cupo(self):
        reserva = self.crear_reserva(numero_personas=5)
        destino = reserva.fecha + timedelta(days=5)
        for grande in Embarcacion.objects.filter(capacidad_maxima=5):
            EmbarcacionNoDisponible.objects.create(empresa=self.empresa, fecha=destino, embarcacion=grande)

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, destino)

        self.assertEqual(ctx.exception.codigo, 'sin_cupo')
        self.assertIn('No queda panga para un grupo de 5 personas', ctx.exception.mensaje)

    @override_settings(APARTADO_MINUTOS=15)
    def test_el_apartado_vigente_de_otro_cliente_cuenta(self):
        reserva = self.crear_reserva()
        destino = reserva.fecha + timedelta(days=5)
        CupoDiario.objects.create(empresa=self.empresa, fecha=destino, cupo_maximo=1)
        ajena = self.crear_reserva(fecha=destino, estado=Reserva.Estado.PENDIENTE_PAGO, nombre_cliente='Otra Persona')
        ajena.apartado_hasta = timezone.now() + timedelta(minutes=15)
        ajena.apartado_demanda = construir_retrato_servicio_suelto(ajena)
        ajena.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, destino)

        self.assertEqual(ctx.exception.codigo, 'sin_cupo')

    @override_settings(APARTADO_MINUTOS=15)
    def test_un_apartado_vencido_ya_no_cuenta(self):
        reserva = self.crear_reserva()
        destino = reserva.fecha + timedelta(days=5)
        CupoDiario.objects.create(empresa=self.empresa, fecha=destino, cupo_maximo=1)
        ajena = self.crear_reserva(fecha=destino, estado=Reserva.Estado.PENDIENTE_PAGO, nombre_cliente='Otra Persona')
        ajena.apartado_hasta = timezone.now() - timedelta(minutes=1)
        ajena.apartado_demanda = construir_retrato_servicio_suelto(ajena)
        ajena.save(update_fields=['apartado_hasta', 'apartado_demanda'])

        self.mover(reserva, destino)

        self.assertEqual(self.recargar(reserva).fecha, destino)

    def test_su_propio_lugar_no_le_estorba_para_cambiar_de_hora_en_el_mismo_dia(self):
        reserva = self.crear_reserva()
        CupoDiario.objects.create(empresa=self.empresa, fecha=reserva.fecha, cupo_maximo=1)

        self.mover(reserva, reserva.fecha, nueva_hora=time(5, 30))

        self.assertEqual(self.recargar(reserva).hora, time(5, 30))

    def test_el_lugar_que_deja_libre_lo_puede_tomar_otro(self):
        reserva = self.crear_reserva()
        CupoDiario.objects.create(empresa=self.empresa, fecha=reserva.fecha, cupo_maximo=1)

        self.mover(reserva, reserva.fecha + timedelta(days=5))

        otra = self.crear_reserva(fecha=reserva.fecha, nombre_cliente='Otra Persona')
        self.assertEqual(otra.fecha, reserva.fecha)

    def test_un_dato_viejo_invalido_fuera_del_formulario_se_nombra_y_manda_a_la_ficha(self):
        reserva = self.crear_reserva()
        Reserva.objects.filter(pk=reserva.pk).update(telefono_cliente='abc')

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, reserva.fecha + timedelta(days=5))

        self.assertEqual(ctx.exception.campo, '')
        self.assertIn('No se puede guardar porque la reserva tiene un dato inválido en', ctx.exception.mensaje)
        self.assertIn('Corrígelo en la ficha.', ctx.exception.mensaje)
        self.assertEqual(self.recargar(reserva).fecha, reserva.fecha)


class PangaYCapitanAlReagendarTests(ReagendarBase):
    """D4: cada recurso se conserva solo si sirve en el dia nuevo; si no, se quita y se avisa."""

    def setUp(self):
        super().setUp()
        self.pangas = list(Embarcacion.objects.filter(empresa=self.empresa, capacidad_maxima=3).order_by('pk'))
        self.panga, self.otra_panga = self.pangas[0], self.pangas[1]
        self.cap = self.capitan('Beto Cota')

    def reserva_asignada(self, dias=10, **extra):
        """Panga + capitan puestos y el correo de asignacion ya mandado (el estado normal de un viaje repartido)."""
        reserva = self.asignar(self.crear_reserva(fecha=self.dia(dias), **extra), panga=self.panga, capitan=self.cap)
        Reserva.objects.filter(pk=reserva.pk).update(aviso_asignacion_enviado_en=timezone.now())
        return self.recargar(reserva)

    def otra_reserva(self, fecha, **asignacion):
        return self.asignar(self.crear_reserva(fecha=fecha, nombre_cliente='Otra Persona'), **asignacion)

    def test_conserva_panga_y_capitan_si_sirven_el_dia_nuevo(self):
        reserva = self.reserva_asignada()

        resultado = self.mover(reserva, self.dia(15))

        guardada = self.recargar(reserva)
        self.assertEqual((guardada.embarcacion, guardada.capitan), (self.panga, self.cap))
        self.assertEqual(guardada.estado, Reserva.Estado.ASIGNADA)
        self.assertIsNotNone(guardada.aviso_asignacion_enviado_en)
        self.assertEqual((resultado.panga_conservada, resultado.capitan_conservado), (True, True))

    def test_una_reserva_sin_asignar_no_tiene_nada_que_conservar(self):
        reserva = self.crear_reserva()

        resultado = self.mover(reserva, self.dia(15))

        self.assertEqual((resultado.panga_conservada, resultado.capitan_conservado), (None, None))

    def test_quita_la_panga_si_otro_viaje_ya_la_usa_ese_dia(self):
        reserva = self.reserva_asignada()
        self.otra_reserva(self.dia(15), panga=self.panga)

        resultado = self.mover(reserva, self.dia(15))

        guardada = self.recargar(reserva)
        self.assertIsNone(guardada.embarcacion_id)
        self.assertEqual(guardada.capitan, self.cap)
        self.assertEqual(guardada.estado, Reserva.Estado.PAGADA)
        self.assertIsNone(guardada.aviso_asignacion_enviado_en)
        self.assertEqual((resultado.panga_conservada, resultado.capitan_conservado), (False, True))

    def test_quita_el_capitan_si_ya_tiene_viaje_ese_dia(self):
        reserva = self.reserva_asignada()
        self.otra_reserva(self.dia(15), panga=self.otra_panga, capitan=self.cap)

        resultado = self.mover(reserva, self.dia(15))

        guardada = self.recargar(reserva)
        self.assertEqual(guardada.embarcacion, self.panga)
        self.assertIsNone(guardada.capitan_id)
        self.assertEqual(guardada.estado, Reserva.Estado.ASIGNADA)  # la panga basta para estar asignada
        self.assertIsNone(guardada.aviso_asignacion_enviado_en)
        self.assertEqual((resultado.panga_conservada, resultado.capitan_conservado), (True, False))

    def test_quita_la_panga_si_esta_fuera_de_servicio_ese_dia(self):
        # `Reserva.clean()` no mira `EmbarcacionNoDisponible`: solo la Agenda lo filtra. Por eso el servicio lo consulta.
        reserva = self.reserva_asignada()
        EmbarcacionNoDisponible.objects.create(empresa=self.empresa, fecha=self.dia(15), embarcacion=self.panga)

        resultado = self.mover(reserva, self.dia(15))

        guardada = self.recargar(reserva)
        self.assertIsNone(guardada.embarcacion_id)
        self.assertEqual(guardada.estado, Reserva.Estado.PAGADA)
        self.assertIsNone(guardada.aviso_asignacion_enviado_en)
        self.assertFalse(resultado.panga_conservada)

    def test_una_baja_de_otro_dia_no_estorba(self):
        reserva = self.reserva_asignada()
        EmbarcacionNoDisponible.objects.create(empresa=self.empresa, fecha=self.dia(16), embarcacion=self.panga)

        resultado = self.mover(reserva, self.dia(15))

        self.assertTrue(resultado.panga_conservada)

    def test_quita_la_panga_si_ya_no_alcanza_la_capacidad(self):
        reserva = self.reserva_asignada()
        Embarcacion.objects.filter(pk=self.panga.pk).update(capacidad_maxima=1)

        resultado = self.mover(reserva, self.dia(15))

        self.assertIsNone(self.recargar(reserva).embarcacion_id)
        self.assertFalse(resultado.panga_conservada)

    def test_quita_la_panga_si_ya_no_esta_activa(self):
        reserva = self.reserva_asignada()
        Embarcacion.objects.filter(pk=self.panga.pk).update(activa=False)

        resultado = self.mover(reserva, self.dia(15))

        self.assertIsNone(self.recargar(reserva).embarcacion_id)
        self.assertFalse(resultado.panga_conservada)

    def test_si_se_quitan_las_dos_el_viaje_vuelve_a_pagada_sin_aviso_pendiente(self):
        reserva = self.reserva_asignada()
        self.otra_reserva(self.dia(15), panga=self.panga)
        self.otra_reserva(self.dia(15), panga=self.otra_panga, capitan=self.cap)

        resultado = self.mover(reserva, self.dia(15))

        guardada = self.recargar(reserva)
        self.assertEqual((guardada.embarcacion_id, guardada.capitan_id), (None, None))
        self.assertEqual(guardada.estado, Reserva.Estado.PAGADA)
        self.assertIsNone(guardada.aviso_asignacion_enviado_en)
        self.assertEqual((resultado.panga_conservada, resultado.capitan_conservado), (False, False))

    def test_cambiar_solo_la_hora_conserva_lo_asignado(self):
        reserva = self.reserva_asignada()

        resultado = self.mover(reserva, reserva.fecha, nueva_hora=time(5, 30))

        guardada = self.recargar(reserva)
        self.assertEqual((guardada.embarcacion, guardada.capitan), (self.panga, self.cap))
        self.assertIsNotNone(guardada.aviso_asignacion_enviado_en)
        self.assertEqual((resultado.panga_conservada, resultado.capitan_conservado), (True, True))

    def test_con_los_dos_conservados_y_el_aviso_ya_puesto_la_senal_no_manda_otro_correo(self):
        reserva = self.reserva_asignada()

        with mock.patch('apps.bookings.signals.enviar_correo_asignacion', return_value=True) as enviar:
            with self.captureOnCommitCallbacks(execute=True):
                self.mover(reserva, self.dia(15))

        enviar.assert_not_called()

    def test_tras_quitar_algo_la_reasignacion_si_manda_el_correo_de_asignacion(self):
        reserva = self.reserva_asignada()
        self.otra_reserva(self.dia(15), panga=self.panga)
        self.mover(reserva, self.dia(15))

        with mock.patch('apps.bookings.signals.enviar_correo_asignacion', return_value=True) as enviar:
            with self.captureOnCommitCallbacks(execute=True):
                self.asignar(self.recargar(reserva), panga=self.otra_panga, capitan=self.cap)

        self.assertEqual(enviar.call_count, 1)

    def test_la_propuesta_adelanta_lo_que_va_a_pasar_y_por_que(self):
        reserva = self.reserva_asignada()
        self.otra_reserva(self.dia(15), panga=self.panga)
        self.otra_reserva(self.dia(15), panga=self.otra_panga, capitan=self.cap)

        propuesta = self.plan(reserva, self.dia(15))
        conserva = self.plan(reserva, self.dia(16))

        self.assertEqual((propuesta.panga, propuesta.capitan), ('quita', 'quita'))
        self.assertIn(self.panga.nombre, propuesta.motivo_panga)
        self.assertIn(self.cap.nombre, propuesta.motivo_panga)
        self.assertEqual((conserva.panga, conserva.capitan, conserva.motivo_panga), ('conserva', 'conserva', ''))

    def test_la_propuesta_sin_asignar_no_dice_nada_de_panga(self):
        propuesta = self.plan(self.crear_reserva(), self.dia(15))

        self.assertEqual((propuesta.panga, propuesta.capitan), (None, None))


class CorreoDelReagendadoTests(ReagendarBase):
    """D9: el correo sale al confirmar la transaccion y nunca la deshace."""

    def test_el_correo_se_encola_y_no_sale_antes_del_commit(self):
        reserva = self.crear_reserva()
        with mock.patch('apps.bookings.reagendar._mandar_correo') as mandar:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                resultado = self.mover(reserva, self.dia(15), avisar_cliente=True)

            self.assertTrue(resultado.correo_encolado)
            self.assertEqual(len(callbacks), 1)
            mandar.assert_not_called()
            callbacks[0]()
            mandar.assert_called_once_with(reserva.pk, resultado.antes, self.vendedora.pk, self.empresa.pk)

    def test_sin_avisar_o_sin_correo_no_se_encola_nada(self):
        con_correo = self.crear_reserva()
        sin_correo = self.crear_reserva(nombre_cliente='Sin Correo')
        # Un dato viejo: el formulario de hoy no deja guardar una reserva sin correo, pero las hay.
        Reserva.objects.filter(pk=sin_correo.pk).update(correo_cliente='')
        sin_correo = self.recargar(sin_correo)
        with mock.patch('apps.bookings.reagendar._mandar_correo') as mandar:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                no_avisa = self.mover(con_correo, self.dia(15), avisar_cliente=False)
                sin_direccion = self.mover(sin_correo, self.dia(15), avisar_cliente=True)

        self.assertEqual(callbacks, [])
        mandar.assert_not_called()
        self.assertFalse(no_avisa.correo_encolado)
        self.assertFalse(sin_direccion.correo_encolado)

    def test_si_la_transaccion_se_deshace_el_correo_no_sale(self):
        reserva = self.crear_reserva()
        with mock.patch('apps.bookings.reagendar._mandar_correo') as mandar:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                with self.assertRaises(RuntimeError):
                    with transaction.atomic():
                        self.mover(reserva, self.dia(15), avisar_cliente=True)
                        raise RuntimeError('la peticion fallo despues de reagendar')

        self.assertEqual(callbacks, [])
        mandar.assert_not_called()
        self.assertEqual(self.recargar(reserva).fecha, reserva.fecha)

    def test_un_fallo_al_mandar_el_correo_no_deshace_la_fecha_y_deja_constancia(self):
        reserva = self.crear_reserva()
        with mock.patch('apps.bookings.reagendar._enviar_correo', return_value=(False, 'Resend sin configurar')):
            with self.captureOnCommitCallbacks(execute=True):
                self.mover(reserva, self.dia(15), avisar_cliente=True)

        self.assertEqual(self.recargar(reserva).fecha, self.dia(15))
        aviso = Notificacion.objects.get(tipo=Notificacion.Tipo.CAMBIO_FECHA)
        self.assertEqual(aviso.nivel, Notificacion.Nivel.ERROR)
        self.assertEqual(aviso.motivo, 'Resend sin configurar')

    def test_un_error_inesperado_en_el_callback_no_se_propaga(self):
        reserva = self.crear_reserva()
        with mock.patch('apps.bookings.reagendar._enviar_correo', side_effect=RuntimeError('boom')):
            with self.captureOnCommitCallbacks(execute=True):
                self.mover(reserva, self.dia(15), avisar_cliente=True)  # no lanza

        self.assertEqual(self.recargar(reserva).fecha, self.dia(15))

    def test_un_correo_enviado_deja_una_notificacion_de_exito(self):
        reserva = self.crear_reserva()
        with mock.patch('apps.bookings.reagendar._enviar_correo', return_value=(True, '')):
            with self.captureOnCommitCallbacks(execute=True):
                self.mover(reserva, self.dia(15), avisar_cliente=True)

        aviso = Notificacion.objects.get(tipo=Notificacion.Tipo.CAMBIO_FECHA)
        self.assertEqual(aviso.nivel, Notificacion.Nivel.EXITO)
        self.assertNotIn('ana@example.com', aviso.texto)


class HospedajeYPaqueteBase(ReagendarBase):
    """Un hotel con una habitacion y un paquete de una empresa: 3 noches y una salida al mar el dia 2."""

    def setUp(self):
        super().setUp()
        self.hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Hotel Mar', slug='hotel-mar', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche', precio_base=Decimal('2000.00'),
        )
        self.habitacion = Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Habitación 1', capacidad_maxima=3, activo=True,
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Mar 3 noches', slug='mar-3-noches',
            precio_ancla=Decimal('9000.00'),
        )
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.hotel, orden=1, noches=3)
        self.ps_pesca = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.pesca, orden=2, dia_estancia=2, salidas=1,
        )

    def crear_paquete(self, dias=20, salidas=1, **extra):
        """Un paquete pagado que empieza en `dias`: la actividad cae el dia 2 y el hotel sale a las 3 noches."""
        PaqueteServicio.objects.filter(pk=self.ps_pesca.pk).update(salidas=salidas)
        inicio = self.dia(dias)
        reserva = self.crear_reserva(
            servicio=None, paquete=self.paquete, fecha=inicio + timedelta(days=1), inicio_paquete=inicio,
            fecha_salida=inicio + timedelta(days=3), **extra,
        )
        reservar_cupo_al_confirmar(reserva)
        return self.recargar(reserva)

    def crear_hospedaje(self, dias=20, **extra):
        llegada = self.dia(dias)
        reserva = self.crear_reserva(
            servicio=self.hotel, fecha=llegada, fecha_salida=llegada + timedelta(days=3), hora=None, **extra,
        )
        reservar_cupo_al_confirmar(reserva)
        return self.recargar(reserva)

    def ocupa_la_habitacion(self, desde, hasta):
        """Otra venta que ya tiene la habitacion en [desde, hasta)."""
        ajena = self.crear_reserva(
            servicio=self.hotel, fecha=desde, fecha_salida=hasta, hora=None, nombre_cliente='Otra Persona',
        )
        ReservaOcupacion.objects.create(
            reserva=ajena, recurso=self.habitacion, empresa=self.empresa, fecha_inicio=desde, fecha_fin=hasta,
            ocupa_cupo=True,
        )


class HospedajeSueltoTests(HospedajeYPaqueteBase):
    def test_la_nueva_llegada_conserva_las_noches_y_mueve_la_habitacion(self):
        reserva = self.crear_hospedaje(dias=20)

        self.mover(reserva, self.dia(30), nueva_hora=None)

        guardada = self.recargar(reserva)
        self.assertEqual((guardada.fecha, guardada.fecha_salida), (self.dia(30), self.dia(33)))
        ocupacion = guardada.ocupaciones.get()
        self.assertEqual((ocupacion.recurso, ocupacion.fecha_inicio, ocupacion.fecha_fin), (
            self.habitacion, self.dia(30), self.dia(33)))
        self.assertTrue(ocupacion.ocupa_cupo)

    def test_la_propuesta_trae_la_salida_nueva(self):
        reserva = self.crear_hospedaje(dias=20)

        propuesta = self.plan(reserva, self.dia(30))

        self.assertEqual(propuesta.errores, {})
        self.assertEqual((propuesta.fecha, propuesta.fecha_salida), (self.dia(30), self.dia(33)))
        self.assertEqual(propuesta.dias_de_mar, [])
        self.assertEqual((propuesta.proxima_fecha, propuesta.panga, propuesta.capitan), (None, None, None))

    def test_sin_habitacion_en_las_fechas_nuevas_falla_y_no_cambia_nada(self):
        reserva = self.crear_hospedaje(dias=20)
        self.ocupa_la_habitacion(self.dia(30), self.dia(33))

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.dia(30), nueva_hora=None)

        self.assertEqual((ctx.exception.codigo, ctx.exception.campo), ('sin_cupo', 'nueva_fecha'))
        self.assertIn('hospedaje', ctx.exception.mensaje)
        guardada = self.recargar(reserva)
        self.assertEqual((guardada.fecha, guardada.fecha_salida), (self.dia(20), self.dia(23)))
        self.assertEqual(guardada.ocupaciones.get().fecha_inicio, self.dia(20))

    def test_la_propuesta_tambien_avisa_que_no_hay_habitacion(self):
        reserva = self.crear_hospedaje(dias=20)
        self.ocupa_la_habitacion(self.dia(30), self.dia(33))

        propuesta = self.plan(reserva, self.dia(30))

        self.assertIn('nueva_fecha', propuesta.errores)
        self.assertIn('hospedaje', propuesta.errores['nueva_fecha'])
        self.assertIsNone(propuesta.proxima_fecha)  # la proxima fecha con lugar es solo del mar

    def test_la_habitacion_vieja_queda_libre_para_otra_venta(self):
        reserva = self.crear_hospedaje(dias=20)

        self.mover(reserva, self.dia(30), nueva_hora=None)

        otra = self.plan(self.crear_hospedaje(dias=40, nombre_cliente='Otra Persona'), self.dia(20))
        self.assertEqual(otra.errores, {})


class PaqueteReagendarTests(HospedajeYPaqueteBase):
    def test_la_propuesta_deriva_inicio_actividad_y_salida_del_paquete(self):
        reserva = self.crear_paquete(dias=20)

        propuesta = self.plan(reserva, self.dia(30))

        self.assertEqual(propuesta.errores, {})
        self.assertEqual(propuesta.inicio_paquete, self.dia(30))
        self.assertEqual(propuesta.fecha, self.dia(31))        # la actividad, el dia 2
        self.assertEqual(propuesta.fecha_salida, self.dia(33))  # tres noches
        self.assertEqual(propuesta.dias_de_mar, [self.dia(31)])

    def test_reagendar_guarda_las_tres_fechas_derivadas(self):
        reserva = self.crear_paquete(dias=20)

        self.mover(reserva, self.dia(30))

        guardada = self.recargar(reserva)
        self.assertEqual(
            (guardada.inicio_paquete, guardada.fecha, guardada.fecha_salida), (self.dia(30), self.dia(31), self.dia(33)),
        )
        self.assertEqual(guardada.estado, Reserva.Estado.PAGADA)

    def test_el_antes_trae_el_inicio_y_la_salida_originales(self):
        reserva = self.crear_paquete(dias=20)

        resultado = self.mover(reserva, self.dia(30))

        self.assertEqual(resultado.antes.inicio_paquete, self.dia(20))
        self.assertEqual((resultado.antes.fecha, resultado.antes.fecha_salida), (self.dia(21), self.dia(23)))

    def test_la_habitacion_del_hotel_se_mueve_con_el_paquete(self):
        reserva = self.crear_paquete(dias=20)

        self.mover(reserva, self.dia(30))

        ocupacion = self.recargar(reserva).ocupaciones.get()
        self.assertEqual((ocupacion.fecha_inicio, ocupacion.fecha_fin), (self.dia(30), self.dia(33)))

    def test_las_salidas_al_mar_se_recrean_en_los_dias_nuevos(self):
        reserva = self.crear_paquete(dias=20, salidas=2)
        self.assertEqual(
            sorted(reserva.salidas.values_list('fecha', flat=True)), [self.dia(21), self.dia(22)],
        )

        self.mover(reserva, self.dia(30))

        self.assertEqual(
            sorted(ReservaSalida.objects.filter(reserva=reserva).values_list('fecha', flat=True)),
            [self.dia(31), self.dia(32)],
        )

    def test_la_propuesta_lista_todos_los_dias_de_mar(self):
        reserva = self.crear_paquete(dias=20, salidas=2)

        propuesta = self.plan(reserva, self.dia(30))

        self.assertEqual(propuesta.dias_de_mar, [self.dia(31), self.dia(32)])

    def test_cupo_de_mar_lleno_en_cualquiera_de_los_dias_nuevos_falla(self):
        reserva = self.crear_paquete(dias=20, salidas=2)
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.dia(32), cupo_maximo=0)

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.dia(30))

        self.assertEqual(ctx.exception.codigo, 'sin_cupo')
        guardada = self.recargar(reserva)
        self.assertEqual(guardada.inicio_paquete, self.dia(20))
        self.assertEqual(
            sorted(guardada.salidas.values_list('fecha', flat=True)), [self.dia(21), self.dia(22)],
        )

    def test_sin_habitacion_en_las_fechas_nuevas_falla_con_mensaje_y_sin_cambios(self):
        reserva = self.crear_paquete(dias=20)
        self.ocupa_la_habitacion(self.dia(30), self.dia(33))

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.dia(30))

        self.assertEqual(ctx.exception.codigo, 'sin_cupo')
        guardada = self.recargar(reserva)
        self.assertEqual(
            (guardada.inicio_paquete, guardada.fecha, guardada.fecha_salida), (self.dia(20), self.dia(21), self.dia(23)),
        )
        self.assertEqual(guardada.ocupaciones.get().fecha_inicio, self.dia(20))

    def test_pedir_la_misma_llegada_es_no_cambiar_nada(self):
        reserva = self.crear_paquete(dias=20)

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.dia(20))

        self.assertEqual(ctx.exception.mensaje, 'Elige una fecha u hora distinta de la actual.')

    def test_la_regla_de_48_horas_mide_contra_la_fecha_mas_temprana_del_paquete(self):
        # La llegada es en 2 dias y la actividad en 3: contra la actividad aun habria margen, contra la
        # llegada (lo primero que el cliente ya va a vivir) ya no.
        reserva = self.crear_paquete(dias=2)

        propuesta = self.plan(reserva, self.dia(20))
        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.dia(20))

        self.assertTrue(propuesta.requiere_excepcion_48h)
        self.assertEqual(propuesta.limite_48h, salida_aware(self.dia(2), None) - timedelta(hours=48))
        self.assertEqual(ctx.exception.codigo, 'excepcion_48h')
        self.assertEqual(self.recargar(reserva).inicio_paquete, self.dia(2))

    def test_la_jefa_con_motivo_si_puede_mover_un_paquete_que_ya_esta_cerca(self):
        reserva = self.crear_paquete(dias=2)

        resultado = self.mover(
            reserva, self.dia(20), **self.como_jefa(motivo_excepcion='El cliente cambió su vuelo'),
        )

        self.assertTrue(resultado.excepcion_48h)
        self.assertEqual(self.recargar(reserva).inicio_paquete, self.dia(20))

    def test_con_margen_suficiente_la_vendedora_mueve_el_paquete_sin_excepcion(self):
        reserva = self.crear_paquete(dias=5)

        resultado = self.mover(reserva, self.dia(20))

        self.assertFalse(resultado.excepcion_48h)

    def test_panga_y_capitan_de_un_paquete_se_evaluan_en_todos_sus_dias_de_mar(self):
        reserva = self.crear_paquete(dias=20, salidas=2)
        panga = Embarcacion.objects.filter(capacidad_maxima=3).order_by('pk').first()
        reserva = self.asignar(reserva, panga=panga)
        # La misma panga esta ocupada el SEGUNDO dia de mar del paquete ya movido.
        ajena = self.asignar(self.crear_reserva(fecha=self.dia(32), nombre_cliente='Otra Persona'), panga=panga)
        self.assertEqual(ajena.embarcacion_id, panga.pk)

        resultado = self.mover(reserva, self.dia(30))

        self.assertFalse(resultado.panga_conservada)
        self.assertIsNone(self.recargar(reserva).embarcacion_id)

    def test_un_paquete_con_traslado_pierde_el_vehiculo_al_cambiar_de_dia(self):
        transporte = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado DLS', slug='traslado-dls', tipo_servicio=TipoServicio.TRANSPORTE,
            estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA, estrategia_precio=EstrategiaPrecio.POR_RUTA, activo=True,
        )
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=transporte, orden=3, dia_estancia=1)
        van = Vehiculo.objects.create(empresa=self.empresa, nombre='Van', lugares=8, activo=True)
        reserva = self.crear_paquete(dias=20)
        self.assertEqual(reserva.viajes_transporte.count(), 2)
        ViajeTransporte.objects.filter(reserva=reserva).update(vehiculo=van)

        propuesta = self.plan(reserva, self.dia(30))
        resultado = self.mover(reserva, self.dia(30))

        self.assertEqual(propuesta.vehiculos_a_quitar, 2)
        self.assertEqual(resultado.vehiculos_quitados, 2)
        viajes = ViajeTransporte.objects.filter(reserva=reserva)
        self.assertEqual(
            {(v.sentido, v.fecha, v.vehiculo_id) for v in viajes},
            {('ida', self.dia(30), None), ('regreso', self.dia(33), None)},
        )


class TrasladoBase(ReagendarBase):
    def setUp(self):
        super().setUp()
        self.transporte = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado Privado', slug='traslado-privado',
            tipo_servicio=TipoServicio.TRANSPORTE, estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
            estrategia_precio=EstrategiaPrecio.POR_RUTA, pide_hora=False, activo=True,
        )
        self.punto = PuntoEncuentro.objects.create(
            empresa=self.empresa, nombre='Hotel Los Arcos', zona=Zona.CENTRO, activo=True,
        )
        self.van = Vehiculo.objects.create(empresa=self.empresa, nombre='Van Ejecutiva', lugares=8, activo=True)

    def crear_traslado(self, tipo=TipoTraslado.REDONDO_AEROPUERTO, dias=10, regreso=13, hora=time(10, 0), **extra):
        reserva = self.crear_reserva(servicio=self.transporte, fecha=self.dia(dias), hora=hora, **extra)
        DetalleTransporte.objects.create(
            reserva=reserva, tipo_traslado=tipo, punto_encuentro=self.punto, zona=Zona.CENTRO,
            fecha_regreso=self.dia(regreso) if tipo == TipoTraslado.REDONDO_AEROPUERTO else None, numero_personas=2,
        )
        ViajeTransporte.objects.filter(reserva=reserva).update(vehiculo=self.van)
        return self.recargar(reserva)

    def viajes(self, reserva):
        return {v.sentido: (v.fecha, v.hora, v.vehiculo_id) for v in ViajeTransporte.objects.filter(reserva=reserva)}


class TrasladoRedondoDeAeropuertoTests(TrasladoBase):
    def test_la_fecha_de_regreso_nueva_actualiza_el_detalle_y_los_tramos(self):
        reserva = self.crear_traslado()

        resultado = self.mover(reserva, self.dia(20), nueva_hora=time(10, 0), nueva_fecha_regreso=self.dia(24))

        self.assertEqual(DetalleTransporte.objects.get(reserva=reserva).fecha_regreso, self.dia(24))
        self.assertEqual(self.recargar(reserva).fecha, self.dia(20))
        self.assertEqual(self.viajes(reserva), {
            'ida': (self.dia(20), time(10, 0), None), 'regreso': (self.dia(24), None, None),
        })
        self.assertEqual(resultado.vehiculos_quitados, 2)

    def test_el_antes_trae_la_fecha_de_regreso_original(self):
        reserva = self.crear_traslado()

        resultado = self.mover(reserva, self.dia(20), nueva_fecha_regreso=self.dia(24))

        self.assertEqual(resultado.antes.fecha_regreso, self.dia(13))

    def test_la_propuesta_trae_el_regreso_y_cuantos_vehiculos_se_quitan(self):
        reserva = self.crear_traslado()

        propuesta = self.plan(reserva, self.dia(20), nueva_fecha_regreso=self.dia(24))

        self.assertEqual(propuesta.errores, {})
        self.assertEqual((propuesta.fecha, propuesta.fecha_regreso), (self.dia(20), self.dia(24)))
        self.assertEqual(propuesta.vehiculos_a_quitar, 2)

    def test_solo_cambiar_la_hora_conserva_los_vehiculos(self):
        reserva = self.crear_traslado()

        propuesta = self.plan(reserva, reserva.fecha, nueva_hora=time(12, 0), nueva_fecha_regreso=self.dia(13))
        resultado = self.mover(
            reserva, reserva.fecha, nueva_hora=time(12, 0), nueva_fecha_regreso=self.dia(13),
        )

        self.assertEqual(propuesta.vehiculos_a_quitar, 0)
        self.assertEqual(resultado.vehiculos_quitados, 0)
        self.assertEqual(self.viajes(reserva)['ida'], (self.dia(10), time(12, 0), self.van.pk))
        self.assertEqual(self.viajes(reserva)['regreso'][2], self.van.pk)

    def test_cambiar_solo_el_regreso_deja_el_vehiculo_de_la_ida(self):
        reserva = self.crear_traslado()

        resultado = self.mover(reserva, reserva.fecha, nueva_hora=reserva.hora, nueva_fecha_regreso=self.dia(15))

        self.assertEqual(resultado.vehiculos_quitados, 1)
        viajes = self.viajes(reserva)
        self.assertEqual(viajes['ida'][2], self.van.pk)
        self.assertEqual(viajes['regreso'], (self.dia(15), None, None))

    def test_mover_solo_el_regreso_de_un_viaje_que_ya_empezo_mide_las_48_horas_contra_el_regreso(self):
        reserva = self.crear_traslado(dias=-1, regreso=10)  # el cliente ya llego; su regreso sigue lejos

        propuesta = self.plan(reserva, reserva.fecha, nueva_fecha_regreso=self.dia(15), hoy=self.hoy)
        resultado = self.mover(reserva, reserva.fecha, nueva_hora=reserva.hora, nueva_fecha_regreso=self.dia(15))

        self.assertFalse(propuesta.requiere_excepcion_48h)
        self.assertFalse(resultado.excepcion_48h)
        self.assertEqual(DetalleTransporte.objects.get(reserva=reserva).fecha_regreso, self.dia(15))

    def test_sin_fecha_de_regreso_no_se_reagenda(self):
        reserva = self.crear_traslado()

        with self.assertRaises(ErrorDeReagendado) as ctx:
            self.mover(reserva, self.dia(20))

        self.assertEqual((ctx.exception.campo, ctx.exception.mensaje), ('nueva_fecha_regreso', 'Elige la fecha de regreso.'))
        self.assertEqual(self.recargar(reserva).fecha, self.dia(10))

    def test_el_regreso_tiene_que_ser_posterior_a_la_llegada(self):
        reserva = self.crear_traslado()

        for regreso in (self.dia(20), self.dia(19)):
            with self.subTest(regreso=regreso):
                with self.assertRaises(ErrorDeReagendado) as ctx:
                    self.mover(reserva, self.dia(20), nueva_fecha_regreso=regreso)

                self.assertEqual(ctx.exception.campo, 'nueva_fecha_regreso')
                self.assertEqual(self.plan(reserva, self.dia(20), nueva_fecha_regreso=regreso).errores, {
                    'nueva_fecha_regreso': ctx.exception.mensaje,
                })
        self.assertEqual(DetalleTransporte.objects.get(reserva=reserva).fecha_regreso, self.dia(13))

    def test_un_traslado_de_otro_tipo_ignora_la_fecha_de_regreso(self):
        reserva = self.crear_traslado(tipo=TipoTraslado.RECEPCION_AEROPUERTO)

        resultado = self.mover(reserva, self.dia(20), nueva_fecha_regreso=self.dia(25))

        self.assertIsNone(DetalleTransporte.objects.get(reserva=reserva).fecha_regreso)
        self.assertEqual(self.viajes(reserva), {'unico': (self.dia(20), time(10, 0), None)})
        self.assertEqual(resultado.vehiculos_quitados, 1)
        self.assertIsNone(resultado.antes.fecha_regreso)


class CandadosYTiempoDeEsperaTests(HospedajeYPaqueteBase):
    """D10 sin Postgres: el ORDEN de los candados del servicio y como se traducen sus fallos."""

    def error_de_postgres(self, sqlstate):
        """Como llega de psycopg a Django: un `OperationalError` cuya causa trae el SQLSTATE."""
        causa = Exception('error del servidor')
        causa.sqlstate = sqlstate
        exc = OperationalError('el candado no se pudo tomar')
        exc.__cause__ = causa
        return exc

    def test_primero_los_dias_de_mar_en_orden_de_fecha_y_luego_las_habitaciones(self):
        Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Habitación 2', capacidad_maxima=3, activo=True,
        )
        reserva = self.crear_paquete(dias=20, salidas=2)
        manager = mock.Mock()

        with mock.patch('apps.bookings.reagendar.bloquear_cupo', manager.mar), \
                mock.patch('apps.bookings.reagendar.bloquear_recurso', manager.habitacion):
            self.mover(reserva, self.dia(30))

        recursos = list(Recurso.objects.filter(servicio=self.hotel, activo=True).order_by('pk').values_list('pk', flat=True))
        self.assertEqual(manager.mock_calls, [
            mock.call.mar(self.empresa.pk, self.dia(31)),
            mock.call.mar(self.empresa.pk, self.dia(32)),
            *[mock.call.habitacion(self.empresa.pk, pk) for pk in recursos],
        ])

    def test_un_servicio_suelto_de_mar_bloquea_solo_su_dia_nuevo(self):
        reserva = self.crear_reserva()
        manager = mock.Mock()

        with mock.patch('apps.bookings.reagendar.bloquear_cupo', manager.mar), \
                mock.patch('apps.bookings.reagendar.bloquear_recurso', manager.habitacion):
            self.mover(reserva, self.dia(15))

        self.assertEqual(manager.mock_calls, [mock.call.mar(self.empresa.pk, self.dia(15))])

    def test_un_candado_ocupado_se_traduce_a_un_mensaje_y_no_deja_cambios(self):
        reserva = self.crear_reserva()

        with mock.patch('apps.bookings.reagendar.bloquear_cupo', side_effect=self.error_de_postgres('55P03')):
            with self.assertRaises(ErrorDeReagendado) as ctx:
                self.mover(reserva, self.dia(15))

        self.assertEqual((ctx.exception.mensaje, ctx.exception.codigo), (MENSAJE_OCUPADO, 'ocupado'))
        self.assertEqual(self.recargar(reserva).fecha, reserva.fecha)

    def test_un_deadlock_se_reintenta_una_vez(self):
        reserva = self.crear_reserva()
        real = mock.Mock(side_effect=[self.error_de_postgres('40P01'), None])

        with mock.patch('apps.bookings.reagendar.bloquear_cupo', real):
            self.mover(reserva, self.dia(15))

        self.assertEqual(real.call_count, 2)
        self.assertEqual(self.recargar(reserva).fecha, self.dia(15))

    def test_dos_deadlocks_seguidos_dicen_que_el_sistema_esta_ocupado(self):
        reserva = self.crear_reserva()
        real = mock.Mock(side_effect=self.error_de_postgres('40P01'))

        with mock.patch('apps.bookings.reagendar.bloquear_cupo', real):
            with self.assertRaises(ErrorDeReagendado) as ctx:
                self.mover(reserva, self.dia(15))

        self.assertEqual(ctx.exception.mensaje, MENSAJE_OCUPADO)
        self.assertEqual(real.call_count, 2)

    def test_otro_error_de_la_base_no_se_disfraza_de_ocupado(self):
        reserva = self.crear_reserva()

        with mock.patch('apps.bookings.reagendar.bloquear_cupo', side_effect=self.error_de_postgres('08006')):
            with self.assertRaises(OperationalError):
                self.mover(reserva, self.dia(15))
