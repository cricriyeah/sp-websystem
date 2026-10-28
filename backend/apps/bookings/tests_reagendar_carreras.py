"""Reagendar bajo concurrencia (ARCH-reagendar-reserva §10, pruebas de carrera 1 a 6).

Solo corren en Postgres: sqlite serializa toda escritura y `select_for_update`, los candados `pg_advisory_xact_lock`
y `lock_timeout` son no-ops ahi (ver `tests_concurrencia.py`). Cada hilo abre su propia conexion y su propio
`con_empresa`, igual que dos operadoras en dos navegadores.

Las carreras no se dejan al azar. El hilo que "gana" se detiene justo despues de tomar sus candados (parche de
`_evaluar_recursos`, que el servicio llama con todos los candados ya tomados), la prueba espera a que el otro hilo
quede de verdad bloqueado esperando (`pg_locks`, una condicion y no una pausa) y solo entonces suelta al primero.
Asi el orden es siempre el mismo y lo que se prueba es lo que pasa cuando el segundo despierta.
"""
import threading
import time as reloj
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, connections
from django.test import TransactionTestCase

from apps.fleet.models import Recurso, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Notificacion
from apps.testing import crear_flota, crear_servicio_pesca

from . import reagendar as servicio
from .cupo import SinCupoError
from .cupo.confirmacion import reservar_cupo_al_confirmar
from .models import CupoDiario, Reserva, ReservaOcupacion
from .reagendar import ErrorDeReagendado, Resultado, token_de
from .tests_concurrencia import SOLO_POSTGRES, _crear_empresa_de_prueba, _datos

ESPERA = 60


class _Hilos:
    """Corre tareas en hilos con su propia conexion y junta lo que devuelven (o lo que lanzaron)."""

    def __init__(self):
        self.resultados, self.errores, self.hilos = {}, {}, []

    def lanzar(self, nombre, tarea):
        def correr():
            try:
                self.resultados[nombre] = tarea()
            except BaseException as exc:  # noqa: BLE001 -- se re-lanza en el hilo de la prueba
                self.errores[nombre] = exc
            finally:
                connections.close_all()  # sin esto TransactionTestCase no puede truncar al terminar

        hilo = threading.Thread(target=correr, name=nombre)
        self.hilos.append(hilo)
        hilo.start()

    def esperar(self, prueba):
        for hilo in self.hilos:
            hilo.join(timeout=ESPERA)
            prueba.assertFalse(hilo.is_alive(), f'el hilo {hilo.name} no termino: posible bloqueo')
        for error in self.errores.values():
            raise error


@SOLO_POSTGRES
class ReagendarConcurrenteTests(TransactionTestCase):
    def setUp(self):
        self.empresa = _crear_empresa_de_prueba()
        self.empresa_id = self.empresa.pk
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            self.pesca = crear_servicio_pesca(self.empresa)
            self.hotel = Servicio.objects.create(
                empresa=self.empresa, nombre='Cabaña', slug='cabana', tipo_servicio='hospedaje',
                estrategia_cupo='por_noche', estrategia_precio='por_noche', precio_base=Decimal('1500.00'),
            )
            self.habitacion = Recurso.objects.create(
                empresa=self.empresa, servicio=self.hotel, nombre='Cabaña 1', capacidad_maxima=4,
            )
        self.hoy = date.today()

    # ---- datos ----
    def dia(self, n):
        return self.hoy + timedelta(days=n)

    def crear(self, nombre, fecha, **extra):
        with scope.con_empresa(self.empresa):
            datos = _datos(
                self.empresa, servicio=extra.pop('servicio', self.pesca), fecha=fecha, nombre_cliente=nombre,
                estado=Reserva.Estado.PAGADA, moneda='MXN', **extra,
            )
            reserva = Reserva(**datos)
            reserva.full_clean()
            reserva.save()
            if reserva.servicio.estrategia_cupo == 'por_noche':
                reservar_cupo_al_confirmar(reserva)
            return Reserva.objects.get(pk=reserva.pk)

    def crear_hospedaje(self, nombre, llegada):
        return self.crear(
            nombre, llegada, servicio=self.hotel, fecha_salida=llegada + timedelta(days=3), hora=None,
        )

    def recargar(self, reserva):
        with scope.con_empresa(self.empresa):
            return Reserva.objects.get(pk=reserva.pk)

    def cupo_de_un_lugar(self, fecha):
        with scope.con_empresa(self.empresa):
            CupoDiario.objects.create(empresa=self.empresa, fecha=fecha, cupo_maximo=1)

    # ---- tareas de hilo ----
    def reagendar(self, reserva, nueva_fecha, *, token=None, hora=time(6, 0), regreso=None, avisar=False):
        """Lo que haria la pantalla: reagendar dentro del `con_empresa` de la peticion. Devuelve el `Resultado` o el
        `ErrorDeReagendado` (los dos son respuestas validas de una carrera)."""
        token = token or token_de(reserva)

        def tarea():
            empresa = Empresa.objects.get(pk=self.empresa_id)
            try:
                with scope.con_empresa(empresa):  # el COMMIT de la peticion es el de este bloque
                    return servicio.reagendar(
                        reserva.pk, nueva_fecha=nueva_fecha, nueva_hora=hora, nueva_fecha_regreso=regreso,
                        token=token, usuario=None, puede_autorizar_48h=False, motivo_excepcion='',
                        avisar_cliente=avisar,
                    )
            except ErrorDeReagendado as exc:
                return exc
        return tarea

    def retener_a(self, nombre):
        """El hilo `nombre` se detiene con sus candados tomados hasta que la prueba lo suelte."""
        tiene, soltar = threading.Event(), threading.Event()
        real = servicio._evaluar_recursos

        def evaluar(*args, **kwargs):
            if threading.current_thread().name == nombre:
                tiene.set()
                if not soltar.wait(ESPERA):
                    raise AssertionError(f'nadie solto a {nombre}')
            return real(*args, **kwargs)

        return mock.patch.object(servicio, '_evaluar_recursos', evaluar), tiene, soltar

    def esperar_a_que_alguien_quede_bloqueado(self):
        """Condicion, no pausa: hasta que otra conexion de esta base este esperando un candado o una fila."""
        limite = reloj.monotonic() + ESPERA
        while reloj.monotonic() < limite:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT count(*) FROM pg_locks WHERE NOT granted AND pid IN '
                    '(SELECT pid FROM pg_stat_activity WHERE datname = current_database())'
                )
                if cursor.fetchone()[0]:
                    return
            reloj.sleep(0.05)
        self.fail('ninguna conexion quedo esperando un candado')

    # ---- 1 ----
    def test_1_dos_reagendados_al_ultimo_lugar_del_mismo_dia_solo_uno_pasa(self):
        destino = self.dia(30)
        self.cupo_de_un_lugar(destino)
        a, b = self.crear('Cliente Uno', self.dia(10)), self.crear('Cliente Dos', self.dia(11))
        parche, tiene, soltar = self.retener_a('A')
        hilos = _Hilos()

        with parche:
            hilos.lanzar('A', self.reagendar(a, destino))
            self.assertTrue(tiene.wait(ESPERA), 'A nunca llego a tener sus candados')
            hilos.lanzar('B', self.reagendar(b, destino))
            self.esperar_a_que_alguien_quede_bloqueado()
            soltar.set()
            hilos.esperar(self)

        self.assertIsInstance(hilos.resultados['A'], Resultado)
        self.assertIsInstance(hilos.resultados['B'], ErrorDeReagendado)
        self.assertEqual(hilos.resultados['B'].codigo, 'sin_cupo')
        self.assertEqual(self.recargar(a).fecha, destino)
        self.assertEqual(self.recargar(b).fecha, self.dia(11))  # la perdedora no se movio
        with scope.con_empresa(self.empresa):
            self.assertEqual(Reserva.objects.filter(fecha=destino).count(), 1)

    # ---- 2 ----
    def test_2_el_doble_envio_de_la_misma_reserva_cambia_una_vez_y_manda_un_correo(self):
        reserva = self.crear('Cliente Uno', self.dia(10))
        token = token_de(reserva)
        destino = self.dia(20)
        parche, tiene, soltar = self.retener_a('A')
        hilos = _Hilos()

        with mock.patch.object(servicio, '_mandar_correo') as mandar, parche:
            hilos.lanzar('A', self.reagendar(reserva, destino, token=token, avisar=True))
            self.assertTrue(tiene.wait(ESPERA), 'A nunca llego a tener la fila')
            hilos.lanzar('B', self.reagendar(reserva, destino, token=token, avisar=True))
            self.esperar_a_que_alguien_quede_bloqueado()  # B espera la fila de A
            soltar.set()
            hilos.esperar(self)

        self.assertIsInstance(hilos.resultados['A'], Resultado)
        self.assertIsInstance(hilos.resultados['B'], ErrorDeReagendado)
        self.assertEqual(hilos.resultados['B'].codigo, 'token')
        self.assertEqual(self.recargar(reserva).fecha, destino)
        self.assertEqual(mandar.call_count, 1)

    # ---- 3 ----
    def test_3_si_el_reembolso_total_cancela_la_reserva_el_reagendado_lo_ve_bajo_candado(self):
        reserva = self.crear('Cliente Uno', self.dia(10))
        token = token_de(reserva)
        tiene, soltar = threading.Event(), threading.Event()
        hilos = _Hilos()

        def cancelar():
            """Lo que hace el webhook de `charge.refunded`: fila bloqueada, estado a cancelada."""
            empresa = Empresa.objects.get(pk=self.empresa_id)
            with scope.con_empresa(empresa):
                bloqueada = Reserva.objects.select_for_update().get(pk=reserva.pk)
                tiene.set()
                if not soltar.wait(ESPERA):
                    raise AssertionError('nadie solto la cancelacion')
                bloqueada.estado = Reserva.Estado.CANCELADA
                bloqueada.reembolsada = True
                bloqueada.motivo_cancelacion = 'Reembolso total hecho desde el panel de Stripe.'
                bloqueada.save()

        hilos.lanzar('C', cancelar)
        self.assertTrue(tiene.wait(ESPERA), 'la cancelacion nunca tomo la fila')
        hilos.lanzar('A', self.reagendar(reserva, self.dia(20), token=token))
        self.esperar_a_que_alguien_quede_bloqueado()
        soltar.set()
        hilos.esperar(self)

        self.assertIsInstance(hilos.resultados['A'], ErrorDeReagendado)
        self.assertEqual(hilos.resultados['A'].codigo, 'estado')
        final = self.recargar(reserva)
        self.assertEqual((final.estado, final.fecha), (Reserva.Estado.CANCELADA, self.dia(10)))

    # ---- 4 ----
    def test_4_reagendar_hospedaje_contra_la_venta_de_la_ultima_habitacion_no_la_duplica(self):
        uno = self.crear_hospedaje('Hotel Uno', self.dia(10))
        destino = self.dia(30)
        parche, tiene, soltar = self.retener_a('A')
        hilos = _Hilos()

        def vender():
            """Otra venta de la misma habitacion en las fechas a las que se esta moviendo `uno`."""
            empresa = Empresa.objects.get(pk=self.empresa_id)
            try:
                with scope.con_empresa(empresa):
                    venta = Reserva(**_datos(
                        empresa, servicio=self.hotel, fecha=destino, fecha_salida=destino + timedelta(days=3),
                        hora=None, nombre_cliente='Hotel Dos', estado=Reserva.Estado.PAGADA, moneda='MXN',
                    ))
                    venta.full_clean()
                    venta.save()
                    reservar_cupo_al_confirmar(venta)
                return 'vendida'
            except (SinCupoError, ValidationError, IntegrityError):
                return 'sin_lugar'

        with parche:
            hilos.lanzar('A', self.reagendar(uno, destino, hora=None))
            self.assertTrue(tiene.wait(ESPERA), 'A nunca llego a tener sus candados')
            hilos.lanzar('V', vender)
            self.esperar_a_que_alguien_quede_bloqueado()  # la venta espera el candado de la habitacion
            soltar.set()
            hilos.esperar(self)

        self.assertIsInstance(hilos.resultados['A'], Resultado)
        self.assertEqual(hilos.resultados['V'], 'sin_lugar')
        with scope.con_empresa(self.empresa):
            ocupantes = ReservaOcupacion.objects.filter(
                recurso=self.habitacion, ocupa_cupo=True, fecha_inicio__lt=destino + timedelta(days=3),
                fecha_fin__gt=destino,
            )
            self.assertEqual([o.reserva_id for o in ocupantes], [uno.pk])

    # ---- 5 ----
    def test_5_dos_reservas_que_se_intercambian_el_dia_no_se_traban(self):
        d1, d2 = self.dia(10), self.dia(11)
        self.cupo_de_un_lugar(d1)
        self.cupo_de_un_lugar(d2)
        a, b = self.crear('Cliente Uno', d1), self.crear('Cliente Dos', d2)
        hilos = _Hilos()
        arranque = threading.Barrier(2)

        def a_la_vez(tarea):
            def sincronizada():
                arranque.wait(timeout=10)
                return tarea()
            return sincronizada

        hilos.lanzar('A', a_la_vez(self.reagendar(a, d2)))
        hilos.lanzar('B', a_la_vez(self.reagendar(b, d1)))
        hilos.esperar(self)  # si hubiera un deadlock sin salida, el join de arriba fallaria

        for resultado in hilos.resultados.values():
            self.assertIsInstance(resultado, (Resultado, ErrorDeReagendado))
            if isinstance(resultado, ErrorDeReagendado):
                self.assertIn(resultado.codigo, ('sin_cupo', 'ocupado'))
        with scope.con_empresa(self.empresa):
            for dia in (d1, d2):  # el tope de un viaje por dia se respeta pase lo que pase
                self.assertLessEqual(Reserva.objects.filter(fecha=dia).count(), 1)

    # ---- 6 ----
    def test_6_con_un_rol_sin_bypassrls_el_servicio_el_callback_y_la_notificacion_escriben_en_su_alcance(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user')
            self.assertEqual(cursor.fetchone(), (False, False), 'la prueba solo vale con un rol sujeto a RLS')
        reserva = self.crear('Cliente Uno', self.dia(10))
        destino = self.dia(20)

        with mock.patch.object(servicio, '_enviar_correo', return_value=(True, '')):
            with scope.con_empresa(self.empresa):
                servicio.reagendar(
                    reserva.pk, nueva_fecha=destino, nueva_hora=time(6, 0), nueva_fecha_regreso=None,
                    token=token_de(reserva), usuario=None, puede_autorizar_48h=False, motivo_excepcion='',
                    avisar_cliente=True,
                )
                with connection.cursor() as cursor:
                    cursor.execute('SHOW lock_timeout')
                    self.assertEqual(cursor.fetchone()[0], '5s')
            # Al salir del bloque se hizo el COMMIT y corrio el callback, que reabrio su propio alcance.

        with scope.con_empresa(self.empresa):
            self.assertEqual(Reserva.objects.get(pk=reserva.pk).fecha, destino)
            avisos = Notificacion.objects.filter(tipo=Notificacion.Tipo.CAMBIO_FECHA)
            self.assertEqual([a.nivel for a in avisos], [Notificacion.Nivel.EXITO])
