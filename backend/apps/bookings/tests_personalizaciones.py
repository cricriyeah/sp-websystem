from datetime import time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.bookings.models import Reserva, ReservaPersonalizacion
from apps.fleet.models import Personalizacion, Servicio, ServicioPersonalizacion
from apps.testing import EmpresaTestCase
from apps.tenancy.rls import alcance_operador_migracion


class PersonalizacionesModelTests(EmpresaTestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Paseo',
            slug='paseo',
            tipo_servicio='otro',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='tarifa_fija',
            precio_base=Decimal('1000.00'),
        )
        self.p = Personalizacion.objects.create(
            empresa=self.empresa,
            nombre='Pregunta',
            tipo_interaccion='input_numero',
        )
        self.sp = ServicioPersonalizacion.objects.create(
            servicio=self.servicio,
            personalizacion=self.p,
            precio=0,
            obligatorio=True,
        )
        self.reserva = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio,
            fecha=timezone.localdate() + timedelta(days=10),
            hora=time(6),
            numero_personas=3,
            nombre_cliente='Juan Perez',
            telefono_cliente='+5216121234567',
            correo_cliente='juan@example.com',
            moneda='MXN',
            deslinde_aceptado=True,
        )

    def test_numero_cero_es_valido_e_input_no_tiene_subtotal(self):
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            respuesta='0',
        )
        fila.full_clean()
        self.assertIsNone(fila.subtotal)

    def test_numero_no_finito_es_invalido(self):
        for respuesta in ('NaN', 'Infinity', '-Infinity', 'abc'):
            with self.subTest(respuesta=respuesta):
                fila = ReservaPersonalizacion(
                    reserva=self.reserva,
                    servicio_personalizacion=self.sp,
                    respuesta=respuesta,
                )
                with self.assertRaises(ValidationError):
                    fila.full_clean()

    def test_subtotal_check_congelado(self):
        self.p.tipo_interaccion = 'check'
        self.p.save(update_fields=['tipo_interaccion'])
        self.sp.obligatorio = False
        self.sp.save(update_fields=['obligatorio'])
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            cantidad=2,
            precio_unitario=Decimal('450'),
        )
        self.assertEqual(fila.subtotal, Decimal('900'))

    def test_check_no_acepta_respuesta(self):
        self.p.tipo_interaccion = 'check'
        self.p.save(update_fields=['tipo_interaccion'])
        self.sp.obligatorio = False
        self.sp.save(update_fields=['obligatorio'])
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            respuesta='texto inesperado',
        )
        with self.assertRaises(ValidationError):
            fila.full_clean()

    def test_input_obligatorio_requiere_respuesta(self):
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            respuesta='   ',
        )
        with self.assertRaises(ValidationError):
            fila.full_clean()

    def test_input_no_acepta_cantidad_ni_precio(self):
        for cambios in ({'cantidad': 2}, {'precio_unitario': Decimal('1')}):
            with self.subTest(cambios=cambios):
                fila = ReservaPersonalizacion(
                    reserva=self.reserva,
                    servicio_personalizacion=self.sp,
                    respuesta='3',
                    **cambios,
                )
                with self.assertRaises(ValidationError):
                    fila.full_clean()

    def test_seleccion_debe_pertenecer_a_opciones(self):
        self.p.tipo_interaccion = 'input_seleccion'
        self.p.opciones_seleccion = ['A', 'B']
        self.p.save(update_fields=['tipo_interaccion', 'opciones_seleccion'])
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            respuesta='C',
        )
        with self.assertRaises(ValidationError):
            fila.full_clean()


class ReservaPersonalizacionMigration0045Tests(TransactionTestCase):
    migrate_from = [
        ('bookings', '0044_rls_orden_sin_current_query'),
        ('fleet', '0030_personalizacion_tipo_interaccion'),
    ]
    migrate_to = [('bookings', '0045_rename_reservapersonalizacion')]

    def _restaurar_esquema(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def setUp(self):
        super().setUp()
        self.addCleanup(self._restaurar_esquema)
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps

        Sede = old_apps.get_model('tenancy', 'Sede')
        Empresa = old_apps.get_model('tenancy', 'Empresa')
        Servicio = old_apps.get_model('fleet', 'Servicio')
        Personalizacion = old_apps.get_model('fleet', 'Personalizacion')
        ServicioPersonalizacion = old_apps.get_model('fleet', 'ServicioPersonalizacion')
        Reserva = old_apps.get_model('bookings', 'Reserva')
        ReservaPaquetePersonalizacion = old_apps.get_model(
            'bookings', 'ReservaPaquetePersonalizacion',
        )

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                sede = Sede.objects.using(connection.alias).create(
                    nombre='Sede rename',
                    slug='sede-rename',
                )
                empresa = Empresa.objects.using(connection.alias).create(
                    sede=sede,
                    nombre='Empresa rename',
                    slug='empresa-rename',
                    activo=True,
                )
                servicio = Servicio.objects.using(connection.alias).create(
                    empresa=empresa,
                    nombre='Servicio rename',
                    slug='servicio-rename',
                )
                personalizacion = Personalizacion.objects.using(connection.alias).create(
                    empresa=empresa,
                    nombre='Personalización rename',
                )
                sp = ServicioPersonalizacion.objects.using(connection.alias).create(
                    servicio=servicio,
                    personalizacion=personalizacion,
                    precio=Decimal('125.00'),
                )
                reserva = Reserva.objects.using(connection.alias).create(
                    empresa=empresa,
                    servicio=servicio,
                    fecha=timezone.localdate() + timedelta(days=10),
                    hora=time(6),
                    numero_personas=2,
                    nombre_cliente='Cliente migración',
                    telefono_cliente='+5216121234567',
                    correo_cliente='migracion@example.com',
                    moneda='MXN',
                    deslinde_aceptado=True,
                )
                fila = ReservaPaquetePersonalizacion.objects.using(connection.alias).create(
                    reserva=reserva,
                    servicio_personalizacion=sp,
                    cantidad=2,
                )
                self.fila_pk = fila.pk
                self.reserva_pk = reserva.pk
                self.sp_pk = sp.pk

    def test_rename_preserva_fila_y_deja_snapshot_vacio(self):
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps
        ReservaPersonalizacion = new_apps.get_model(
            'bookings', 'ReservaPersonalizacion',
        )

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                fila = ReservaPersonalizacion.objects.using(connection.alias).get(
                    pk=self.fila_pk,
                )
                self.assertEqual(fila.reserva_id, self.reserva_pk)
                self.assertEqual(fila.servicio_personalizacion_id, self.sp_pk)
                self.assertEqual(fila.cantidad, 2)
                self.assertEqual(fila.respuesta, '')
                self.assertIsNone(fila.precio_unitario)
