"""Pruebas de la sincronización de viajes de transporte (bookings/traslados.py).

Cubre:
- Los tres tipos de traslado crean los viajes correctos (fechas, horas, sentidos).
- Idempotencia: llamar dos veces no duplica viajes.
- Cambio de fecha quita el vehículo y cambio de hora lo conserva.
- Cambio de tipo de traslado borra viajes obsoletos y crea los nuevos.
- Cancelar quita el vehículo y reactivar vuelve a poner los viajes activos.
- No pisa la hora del regreso ya capturada.
- El detalle se crea DESPUÉS de la reserva pagada (el segundo gancho).
- Borrar el detalle borra los viajes (señal post_delete).
- Una reserva de pesca o sin detalle no genera viajes.
- Si sincronizar_viajes lanza una excepción, la reserva igual se guarda y aplicar_pago_exitoso no falla.
- Comando manage.py sincronizar_viajes_transporte (con y sin --dry-run).
- Función de la migración de datos 0053.
"""
from datetime import date, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.utils import timezone

from apps.bookings.models import DetalleTransporte, Reserva, ViajeTransporte
from apps.bookings.traslados import sincronizar_viajes
from apps.fleet.enums import (
    EstrategiaCupo,
    EstrategiaPrecio,
    TipoServicio,
    TipoTraslado,
    Zona,
)
from apps.fleet.models import PuntoEncuentro, Servicio, Vehiculo
from apps.tenancy import scope
from apps.testing import EmpresaTestCase, crear_servicio_pesca

HOY = date.today()
MANANA = HOY + timedelta(days=1)
PASADO_MANANA = HOY + timedelta(days=2)
EN_TRES_DIAS = HOY + timedelta(days=3)


class TrasladosSyncTests(EmpresaTestCase):

    def setUp(self):
        super().setUp()
        self.servicio_transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Privado DLS',
            slug='traslado-privado-dls',
            tipo_servicio=TipoServicio.TRANSPORTE,
            estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
            estrategia_precio=EstrategiaPrecio.POR_RUTA,
            pide_hora=False,
            activo=True,
        )
        self.punto_encuentro = PuntoEncuentro.objects.create(
            empresa=self.empresa,
            nombre='Hotel Los Arcos',
            zona=Zona.CENTRO,
            activo=True,
        )
        self.vehiculo = Vehiculo.objects.create(
            empresa=self.empresa,
            nombre='Van Ejecutiva',
            lugares=8,
            activo=True,
        )

    def _crear_reserva_pagada(self, fecha=None, hora=None, numero_personas=2):
        return Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_transporte,
            nombre_cliente='Valeria Morales',
            telefono_cliente='612 123 4567',
            correo_cliente='valeria@example.com',
            canal_origen=Reserva.CanalOrigen.WHATSAPP,
            fecha=fecha or MANANA,
            hora=hora or time(9, 0),
            numero_personas=numero_personas,
            estado=Reserva.Estado.PAGADA,
        )

    # -------------------------------------------------------------------------
    # 1. Los tres tipos de traslado crean los viajes correctos
    # -------------------------------------------------------------------------

    def test_recepcion_aeropuerto_crea_viaje_unico(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(10, 30))
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            punto_encuentro=self.punto_encuentro,
            zona=Zona.CENTRO,
        )
        viajes = ViajeTransporte.objects.filter(reserva=reserva)
        self.assertEqual(viajes.count(), 1)
        viaje = viajes.first()
        self.assertEqual(viaje.sentido, ViajeTransporte.Sentido.UNICO)
        self.assertEqual(viaje.fecha, MANANA)
        self.assertEqual(viaje.hora, time(10, 30))
        self.assertIsNone(viaje.vehiculo)
        self.assertFalse(viaje.cancelado)
        self.assertEqual(viaje.empresa_id, self.empresa.id)

    def test_redondo_actividad_crea_ida_y_regreso(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(8, 0))
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            punto_encuentro=self.punto_encuentro,
            zona=Zona.CENTRO,
        )
        viajes = ViajeTransporte.objects.filter(reserva=reserva).order_by('sentido')
        self.assertEqual(viajes.count(), 2)

        ida = viajes.get(sentido=ViajeTransporte.Sentido.IDA)
        regreso = viajes.get(sentido=ViajeTransporte.Sentido.REGRESO)

        self.assertEqual(ida.fecha, MANANA)
        self.assertEqual(ida.hora, time(8, 0))
        self.assertFalse(ida.cancelado)

        self.assertEqual(regreso.fecha, MANANA)
        self.assertIsNone(regreso.hora)
        self.assertFalse(regreso.cancelado)

    def test_redondo_aeropuerto_crea_ida_y_regreso_con_fecha_regreso(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(11, 0))
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            direccion_personalizada='Colonia Bellavista cien',
            fecha_regreso=EN_TRES_DIAS,
        )
        viajes = ViajeTransporte.objects.filter(reserva=reserva).order_by('sentido')
        self.assertEqual(viajes.count(), 2)

        ida = viajes.get(sentido=ViajeTransporte.Sentido.IDA)
        regreso = viajes.get(sentido=ViajeTransporte.Sentido.REGRESO)

        self.assertEqual(ida.fecha, MANANA)
        self.assertEqual(ida.hora, time(11, 0))

        self.assertEqual(regreso.fecha, EN_TRES_DIAS)
        self.assertIsNone(regreso.hora)

    # -------------------------------------------------------------------------
    # 2. Idempotencia: llamar dos veces no duplica viajes
    # -------------------------------------------------------------------------

    def test_idempotencia_no_duplica_viajes(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(9, 0))
        detalle = DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            punto_encuentro=self.punto_encuentro,
            zona=Zona.CENTRO,
        )
        ids_iniciales = set(ViajeTransporte.objects.filter(reserva=reserva).values_list('pk', flat=True))
        self.assertEqual(len(ids_iniciales), 2)

        # Segunda llamada explícita
        sincronizar_viajes(reserva, detalle=detalle)
        ids_segunda = set(ViajeTransporte.objects.filter(reserva=reserva).values_list('pk', flat=True))
        self.assertEqual(ids_iniciales, ids_segunda)

        # Tercera llamada desde reserva.save()
        reserva.save()
        ids_tercera = set(ViajeTransporte.objects.filter(reserva=reserva).values_list('pk', flat=True))
        self.assertEqual(ids_iniciales, ids_tercera)

    # -------------------------------------------------------------------------
    # 3. Cambio de fecha quita vehículo y cambio de hora lo conserva
    # -------------------------------------------------------------------------

    def test_cambio_de_fecha_quita_vehiculo(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(9, 0))
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            direccion_personalizada='Zona Dorada dos',
        )
        viaje = ViajeTransporte.objects.get(reserva=reserva)
        viaje.vehiculo = self.vehiculo
        viaje.save()

        # Cambiar la fecha de la reserva
        reserva.fecha = PASADO_MANANA
        reserva.save()

        viaje.refresh_from_db()
        self.assertEqual(viaje.fecha, PASADO_MANANA)
        self.assertIsNone(viaje.vehiculo)

    def test_cambio_de_hora_conserva_vehiculo(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(9, 0))
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            direccion_personalizada='Zona Dorada dos',
        )
        viaje = ViajeTransporte.objects.get(reserva=reserva)
        viaje.vehiculo = self.vehiculo
        viaje.save()

        # Cambiar solo la hora
        reserva.hora = time(14, 0)
        reserva.save()

        viaje.refresh_from_db()
        self.assertEqual(viaje.hora, time(14, 0))
        self.assertEqual(viaje.vehiculo_id, self.vehiculo.id)

    # -------------------------------------------------------------------------
    # 4. Cambio de tipo de traslado
    # -------------------------------------------------------------------------

    def test_cambio_de_tipo_borra_viajes_obsoletos_y_crea_nuevos(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(9, 0))
        detalle = DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            punto_encuentro=self.punto_encuentro,
            zona=Zona.CENTRO,
        )
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 2)

        # Cambiar a recepcion_aeropuerto (solo tramo unico)
        detalle.tipo_traslado = TipoTraslado.RECEPCION_AEROPUERTO
        detalle.save()

        viajes = ViajeTransporte.objects.filter(reserva=reserva)
        self.assertEqual(viajes.count(), 1)
        self.assertEqual(viajes.first().sentido, ViajeTransporte.Sentido.UNICO)

    # -------------------------------------------------------------------------
    # 5. Cancelar quita vehículo y reactivar los vuelve a poner
    # -------------------------------------------------------------------------

    def test_cancelar_quita_vehiculo_y_reactivar_restablece(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(9, 0))
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            direccion_personalizada='Terminal uno',
        )
        viaje = ViajeTransporte.objects.get(reserva=reserva)
        viaje.vehiculo = self.vehiculo
        viaje.save()

        # Cancelar la reserva
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.save()

        viaje.refresh_from_db()
        self.assertTrue(viaje.cancelado)
        self.assertIsNone(viaje.vehiculo)

        # Reactivar la reserva a pagada
        reserva.estado = Reserva.Estado.PAGADA
        reserva.save()

        viaje.refresh_from_db()
        self.assertFalse(viaje.cancelado)
        self.assertIsNone(viaje.vehiculo)

    # -------------------------------------------------------------------------
    # 6. No pisa la hora del regreso ya capturada
    # -------------------------------------------------------------------------

    def test_no_pisa_hora_regreso_ya_capturada(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(8, 0))
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            punto_encuentro=self.punto_encuentro,
            zona=Zona.CENTRO,
        )
        regreso = ViajeTransporte.objects.get(reserva=reserva, sentido=ViajeTransporte.Sentido.REGRESO)
        self.assertIsNone(regreso.hora)

        # La vendedora captura la hora de regreso en la agenda
        regreso.hora = time(16, 45)
        regreso.save()

        # Re-guardar la reserva no debe sobreescribir la hora del regreso
        reserva.nombre_cliente = 'Valeria Rios'
        reserva.save()

        regreso.refresh_from_db()
        self.assertEqual(regreso.hora, time(16, 45))

    # -------------------------------------------------------------------------
    # 7. Detalle creado DESPUÉS de la reserva pagada (segundo gancho)
    # -------------------------------------------------------------------------

    def test_detalle_creado_despues_de_reserva_pagada(self):
        # Crear reserva sin detalle
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(9, 0))
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 0)

        # Alta posterior del detalle (como ocurre en checkout o admin manual)
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            direccion_personalizada='Calle Sonora cincuenta',
        )

        # El gancho en DetalleTransporte.save() creó los viajes
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 1)

    # -------------------------------------------------------------------------
    # 8. Borrar detalle borra los viajes (señal post_delete)
    # -------------------------------------------------------------------------

    def test_borrar_detalle_borra_viajes(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(9, 0))
        detalle = DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            punto_encuentro=self.punto_encuentro,
            zona=Zona.CENTRO,
        )
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 2)

        # Borrar el detalle debe eliminar los viajes asociados
        detalle.delete()
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 0)

    # -------------------------------------------------------------------------
    # 9. Reserva de pesca o sin detalle no genera viajes
    # -------------------------------------------------------------------------

    def test_reserva_pesca_o_sin_detalle_no_genera_viajes(self):
        servicio_pesca = crear_servicio_pesca(self.empresa)
        reserva_pesca = Reserva.objects.create(
            empresa=self.empresa,
            servicio=servicio_pesca,
            nombre_cliente='Santiago Cruz',
            telefono_cliente='612 222 3333',
            correo_cliente='santiago@example.com',
            canal_origen=Reserva.CanalOrigen.WHATSAPP,
            fecha=MANANA,
            hora=time(6, 0),
            numero_personas=2,
            estado=Reserva.Estado.PAGADA,
        )
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva_pesca).count(), 0)

        # Reserva de transporte pero sin detalle
        reserva_transporte = self._crear_reserva_pagada()
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva_transporte).count(), 0)

        # Reserva con servicio_id nulo
        reserva_transporte.servicio_id = None
        sincronizar_viajes(reserva_transporte)
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva_transporte).count(), 0)

    # -------------------------------------------------------------------------
    # 10. Excepción en sincronizar_viajes no impide guardar ni cobrar
    # -------------------------------------------------------------------------

    @mock.patch('apps.bookings.traslados.sincronizar_viajes')
    def test_excepcion_en_sincronizar_viajes_no_falla_guardado(self, mock_sync):
        mock_sync.side_effect = RuntimeError('Fallo simulado en sincronización')

        # Guardar la reserva no lanza la excepción
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(9, 0))
        self.assertIsNotNone(reserva.pk)

        # Modificar y re-guardar tampoco lanza
        reserva.nombre_cliente = 'Andrea Beltran'
        reserva.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.nombre_cliente, 'Andrea Beltran')

    @mock.patch('apps.bookings.traslados.sincronizar_viajes')
    def test_excepcion_en_sincronizar_viajes_no_tumba_aplicar_pago_exitoso(self, mock_sync):
        mock_sync.side_effect = RuntimeError('Fallo simulado en sincronización')

        reserva = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_transporte,
            nombre_cliente='Raul Castaneda',
            telefono_cliente='612 444 5555',
            correo_cliente='raul@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            deslinde_nombre='Raul Castaneda',
            fecha=MANANA,
            hora=time(10, 0),
            numero_personas=2,
            precio_total=Decimal('4200.00'),
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            direccion_personalizada='Calle Hidalgo diez',
        )

        from apps.payments.services import APLICADO, aplicar_pago_exitoso

        intent = {
            'id': 'pi_test_simulacion_gancho',
            'amount_received': 420000,
            'created': 1700000000,
        }
        intent['metadata'] = {'reserva_id': str(reserva.pk)}
        intent['currency'] = 'mxn'
        resultado = aplicar_pago_exitoso(intent, self.empresa)
        self.assertEqual(resultado, APLICADO)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)

    # -------------------------------------------------------------------------
    # 11. Comando sincronizar_viajes_transporte (con y sin --dry-run)
    # -------------------------------------------------------------------------

    def _correr_comando(self, *args, **kwargs):
        """El comando recorre todas las empresas con su propio alcance: no puede correr dentro del
        alcance de UNA empresa que mantiene abierto EmpresaTestCase, asi que se sale y se restaura."""
        self._alcance.__exit__(None, None, None)
        try:
            call_command('sincronizar_viajes_transporte', *args, **kwargs)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

    def test_comando_sincronizar_viajes_transporte(self):
        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(8, 30))
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            direccion_personalizada='Zona Malecon tres',
        )
        # Borrar el viaje para simular estado no sincronizado
        ViajeTransporte.objects.filter(reserva=reserva).delete()
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 0)

        # Ejecutar con --dry-run: no crea viajes
        out = StringIO()
        self._correr_comando('--dry-run', stdout=out)
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 0)

        # Ejecutar sin --dry-run: crea los viajes
        out = StringIO()
        self._correr_comando(stdout=out)
        self.assertIn('Se sincronizaron viajes', out.getvalue())
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 1)

    # -------------------------------------------------------------------------
    # 12. Migración de datos 0058
    # -------------------------------------------------------------------------

    def test_migracion_de_datos_crea_viajes_para_reservas_existentes(self):
        import importlib

        crear_viajes_existentes = importlib.import_module(
            'apps.bookings.migrations.0058_viajes_transporte_existentes'
        ).crear_viajes_existentes
        from django.apps import apps as django_apps
        from django.db import connection

        reserva = self._crear_reserva_pagada(fecha=MANANA, hora=time(9, 15))
        DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            punto_encuentro=self.punto_encuentro,
            zona=Zona.CENTRO,
        )
        # Borrar viajes generados por el gancho
        ViajeTransporte.objects.filter(reserva=reserva).delete()
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 0)

        crear_viajes_existentes(django_apps, mock.Mock(connection=connection))

        viajes = ViajeTransporte.objects.filter(reserva=reserva).order_by('sentido')
        self.assertEqual(viajes.count(), 2)
        ida = viajes.get(sentido=ViajeTransporte.Sentido.IDA)
        regreso = viajes.get(sentido=ViajeTransporte.Sentido.REGRESO)

        self.assertEqual(ida.fecha, MANANA)
        self.assertEqual(ida.hora, time(9, 15))
        self.assertEqual(regreso.fecha, MANANA)
        self.assertIsNone(regreso.hora)
