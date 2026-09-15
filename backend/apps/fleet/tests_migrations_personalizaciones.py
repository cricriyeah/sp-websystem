from datetime import date, time
from decimal import Decimal
from unittest import skipUnless

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.tenancy.rls import alcance_operador_migracion


class PersonalizacionMigration0030Tests(TransactionTestCase):
    """Prueba la migracion de datos 0030_personalizacion_tipo_interaccion.

    Verifica que:
    1. Las asociaciones de tipo check con obligatorio=True se normalizan a obligatorio=False y preseleccionado=True.
    2. Los precios (precio y precio_usd) se conservan intactos.
    3. Una base con catalogo vacio migra sin errores y no recibe semillas espurias.
    """
    migrate_from = [('fleet', '0029_servicio_hora_apertura_servicio_hora_cierre')]
    migrate_to = [('fleet', '0030_personalizacion_tipo_interaccion')]

    def _restaurar_esquema(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def setUp(self):
        super().setUp()
        # Registrar restauracion del esquema antes de cualquier operacion que pueda fallar,
        # garantizando que se ejecute incluso si setUp falla a la mitad.
        self.addCleanup(self._restaurar_esquema)

        self.executor = MigrationExecutor(connection)
        # Asegurar estado en migrate_from
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps

        # Crear datos de prueba con modelos historicos previos bajo alcance de operador
        # para respetar RLS en PostgreSQL con rol sin BYPASSRLS
        SedeModel = old_apps.get_model('tenancy', 'Sede')
        EmpresaModel = old_apps.get_model('tenancy', 'Empresa')
        ServicioModel = old_apps.get_model('fleet', 'Servicio')
        PersonalizacionModel = old_apps.get_model('fleet', 'Personalizacion')
        SPModel = old_apps.get_model('fleet', 'ServicioPersonalizacion')

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                self.sede = SedeModel.objects.using(connection.alias).create(
                    nombre='Sede Mig', slug='sede-mig'
                )
                self.empresa = EmpresaModel.objects.using(connection.alias).create(
                    sede=self.sede, nombre='Empresa Mig', slug='empresa-mig', activo=True
                )
                self.servicio = ServicioModel.objects.using(connection.alias).create(
                    empresa=self.empresa, nombre='Tour Mig', slug='tour-mig'
                )

                # SP 1: check obligatorio=True, preseleccionado=False con precios
                self.p1 = PersonalizacionModel.objects.using(connection.alias).create(
                    empresa=self.empresa, nombre='Check Obligatorio'
                )
                self.sp1 = SPModel.objects.using(connection.alias).create(
                    servicio=self.servicio, personalizacion=self.p1,
                    obligatorio=True, preseleccionado=False,
                    precio=Decimal('250.00'), precio_usd=Decimal('15.00')
                )

                # SP 2: check ya opcional (obligatorio=False, preseleccionado=False)
                self.p2 = PersonalizacionModel.objects.using(connection.alias).create(
                    empresa=self.empresa, nombre='Check Opcional'
                )
                self.sp2 = SPModel.objects.using(connection.alias).create(
                    servicio=self.servicio, personalizacion=self.p2,
                    obligatorio=False, preseleccionado=False,
                    precio=Decimal('100.00'), precio_usd=None
                )

    def test_migracion_normaliza_checks_obligatorios_a_preseleccionados(self):
        # Ejecutar migracion hacia 0030
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps

        SPModel = new_apps.get_model('fleet', 'ServicioPersonalizacion')
        PersonalizacionModel = new_apps.get_model('fleet', 'Personalizacion')

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                sp1 = SPModel.objects.using(connection.alias).get(pk=self.sp1.pk)
                self.assertFalse(sp1.obligatorio)
                self.assertTrue(sp1.preseleccionado)
                self.assertEqual(sp1.precio, Decimal('250.00'))
                self.assertEqual(sp1.precio_usd, Decimal('15.00'))

                sp2 = SPModel.objects.using(connection.alias).get(pk=self.sp2.pk)
                self.assertFalse(sp2.obligatorio)
                self.assertFalse(sp2.preseleccionado)
                self.assertEqual(sp2.precio, Decimal('100.00'))
                self.assertIsNone(sp2.precio_usd)

                # Verificar campos default en Personalizacion
                p1 = PersonalizacionModel.objects.using(connection.alias).get(pk=self.p1.pk)
                self.assertEqual(p1.tipo_interaccion, 'check')
                self.assertEqual(p1.opciones_seleccion, [])
                self.assertFalse(p1.aviso_reforzado)

    def test_catalogo_vacio_migra_sin_semillas_y_sin_errores(self):
        # Asegurar catálogo vacío borrando los registros creados en setUp
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                old_apps.get_model('fleet', 'ServicioPersonalizacion').objects.using(connection.alias).all().delete()
                old_apps.get_model('fleet', 'Personalizacion').objects.using(connection.alias).all().delete()

        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps

        SPModel = new_apps.get_model('fleet', 'ServicioPersonalizacion')
        PersonalizacionModel = new_apps.get_model('fleet', 'Personalizacion')
        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                self.assertEqual(SPModel.objects.using(connection.alias).count(), 0)
                self.assertEqual(PersonalizacionModel.objects.using(connection.alias).count(), 0)


@skipUnless(connection.vendor == 'postgresql', 'La conservación de RLS requiere Postgres')
class ReservaPersonalizacionPolicyRenameMigrationTests(TransactionTestCase):
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
                    nombre='Sede policy rename', slug='sede-policy-rename',
                )
                empresa = Empresa.objects.using(connection.alias).create(
                    sede=sede, nombre='Empresa policy rename',
                    slug='empresa-policy-rename', activo=True,
                )
                servicio = Servicio.objects.using(connection.alias).create(
                    empresa=empresa, nombre='Servicio policy rename',
                    slug='servicio-policy-rename',
                )
                personalizacion = Personalizacion.objects.using(connection.alias).create(
                    empresa=empresa, nombre='Personalización policy rename',
                )
                sp = ServicioPersonalizacion.objects.using(connection.alias).create(
                    servicio=servicio, personalizacion=personalizacion,
                    precio=Decimal('75.00'),
                )
                reserva = Reserva.objects.using(connection.alias).create(
                    empresa=empresa, servicio=servicio,
                    fecha=date(2026, 12, 10), hora=time(9), numero_personas=2,
                    nombre_cliente='Cliente policy', telefono_cliente='6121234567',
                    correo_cliente='policy@example.com', moneda='MXN',
                    deslinde_aceptado=True,
                )
                fila = ReservaPaquetePersonalizacion.objects.using(connection.alias).create(
                    reserva=reserva, servicio_personalizacion=sp, cantidad=2,
                )
                self.fila_pk = fila.pk
                self.reserva_pk = reserva.pk
                self.sp_pk = sp.pk

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT policyname FROM pg_policies WHERE tablename=%s ORDER BY policyname',
                ['bookings_reservapaquetepersonalizacion'],
            )
            self.politicas_antes = cursor.fetchall()
        self.assertEqual(self.politicas_antes, [('tenancy_alcance',)])

    def test_rename_preserva_fila_y_policy_en_la_tabla_nueva(self):
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps
        ReservaPersonalizacion = new_apps.get_model('bookings', 'ReservaPersonalizacion')

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                fila = ReservaPersonalizacion.objects.using(connection.alias).get(pk=self.fila_pk)
        self.assertEqual(fila.reserva_id, self.reserva_pk)
        self.assertEqual(fila.servicio_personalizacion_id, self.sp_pk)
        self.assertEqual(fila.cantidad, 2)

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT policyname FROM pg_policies WHERE tablename=%s ORDER BY policyname',
                ['bookings_reservapersonalizacion'],
            )
            politicas_despues = cursor.fetchall()
            cursor.execute(
                'SELECT policyname FROM pg_policies WHERE tablename=%s',
                ['bookings_reservapaquetepersonalizacion'],
            )
            politicas_nombre_viejo = cursor.fetchall()

        self.assertEqual(politicas_despues, self.politicas_antes)
        self.assertEqual(politicas_nombre_viejo, [])


class TarifaAServicioMigration0031Tests(TransactionTestCase):
    """Prueba la migracion de datos 0031_tarifa_a_servicio.

    Verifica que:
    1. Empresa con Tarifa y Servicio previo: actualiza precios y ventana horaria
       en el Servicio existente (conservando nombre/slug/activo).
    2. Empresa con Tarifa y sin Servicio: crea un nuevo Servicio canónico 'pesca-deportiva'.
    3. Reserva histórica sin producto (servicio=None, paquete=None) se backfillea al servicio correspondiente.
    4. Reserva de paquete (paquete!=None, servicio=None) no se modifica.
    5. Empresa sin Tarifa con Reserva huérfana (sin producto): falla explícitamente antes de inventar precio.
    """
    migrate_from = [
        ('fleet', '0030_personalizacion_tipo_interaccion'),
        ('bookings', '0044_rls_orden_sin_current_query'),
    ]
    migrate_to = [
        ('fleet', '0031_tarifa_a_servicio'),
    ]

    def _restaurar_esquema(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def setUp(self):
        super().setUp()
        self.addCleanup(self._restaurar_esquema)
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)

    def test_migracion_actualiza_servicio_existente_y_crea_nuevo_con_backfill(self):
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        SedeH = old_apps.get_model('tenancy', 'Sede')
        EmpresaH = old_apps.get_model('tenancy', 'Empresa')
        TarifaH = old_apps.get_model('fleet', 'Tarifa')
        ServicioH = old_apps.get_model('fleet', 'Servicio')
        PaqueteH = old_apps.get_model('fleet', 'Paquete')
        ReservaH = old_apps.get_model('bookings', 'Reserva')

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                sede = SedeH.objects.using(connection.alias).create(
                    nombre='Sede Mig 0031', slug='sede-mig-0031',
                )
                # Empresa 1: con Tarifa y Servicio previo
                empresa1 = EmpresaH.objects.using(connection.alias).create(
                    sede_id=sede.pk, nombre='Empresa Previa', slug='empresa-previa', activo=True,
                )
                TarifaH.objects.using(connection.alias).create(
                    empresa_id=empresa1.pk, precio=Decimal('5100'),
                    precio_usd=Decimal('300'), precio_persona_extra=Decimal('600'),
                    precio_persona_extra_usd=Decimal('35'),
                )
                s_previo = ServicioH.objects.using(connection.alias).create(
                    empresa_id=empresa1.pk, nombre='Pesca Existente',
                    slug='pesca-deportiva', tipo_servicio='pesca', precio_base=Decimal('1'),
                    hora_apertura=None, hora_cierre=None, activo=True,
                )
                reserva_pesca1 = ReservaH.objects.using(connection.alias).create(
                    empresa_id=empresa1.pk, fecha=date(2026, 12, 1), hora=time(6),
                    numero_personas=3, nombre_cliente='Cliente 1', telefono_cliente='6121111111',
                    correo_cliente='c1@example.com', moneda='MXN', deslinde_aceptado=True,
                )
                paquete1 = PaqueteH.objects.using(connection.alias).create(
                    nombre='Paquete Mig', slug='paquete-mig',
                    empresa_lider_id=empresa1.pk, sede_id=sede.pk, precio_ancla=Decimal('7000'),
                )
                reserva_paquete1 = ReservaH.objects.using(connection.alias).create(
                    empresa_id=empresa1.pk, paquete_id=paquete1.pk, fecha=date(2026, 12, 2),
                    hora=time(6), numero_personas=3, nombre_cliente='Cliente Paquete',
                    telefono_cliente='6121111112', correo_cliente='cp@example.com',
                    moneda='MXN', deslinde_aceptado=True,
                )

                # Empresa 2: con Tarifa y sin Servicio
                empresa2 = EmpresaH.objects.using(connection.alias).create(
                    sede_id=sede.pk, nombre='Empresa Nueva', slug='empresa-nueva', activo=True,
                )
                TarifaH.objects.using(connection.alias).create(
                    empresa_id=empresa2.pk, precio=Decimal('4200'),
                    precio_usd=None, precio_persona_extra=Decimal('500'),
                    precio_persona_extra_usd=None,
                )
                reserva_pesca2 = ReservaH.objects.using(connection.alias).create(
                    empresa_id=empresa2.pk, fecha=date(2026, 12, 3), hora=time(6),
                    numero_personas=4, nombre_cliente='Cliente 2', telefono_cliente='6121111113',
                    correo_cliente='c2@example.com', moneda='MXN', deslinde_aceptado=True,
                )

        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        actual = self.executor.loader.project_state(self.migrate_to).apps
        ServicioHistorico = actual.get_model('fleet', 'Servicio')
        ReservaHistorica = actual.get_model('bookings', 'Reserva')

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                # Comprobar Empresa 1 (actualización de precios y ventana horaria, preserva nombre)
                s1 = ServicioHistorico.objects.using(connection.alias).get(
                    empresa_id=empresa1.pk, slug='pesca-deportiva',
                )
                self.assertEqual(s1.pk, s_previo.pk)
                self.assertEqual(s1.nombre, 'Pesca Existente')
                self.assertEqual(s1.tipo_servicio, 'pesca')
                self.assertEqual(s1.precio_base, Decimal('5100'))
                self.assertEqual(s1.precio_base_usd, Decimal('300'))
                self.assertEqual(s1.precio_persona_extra, Decimal('600'))
                self.assertEqual(s1.precio_persona_extra_usd, Decimal('35'))
                self.assertEqual(s1.personas_incluidas, 3)
                self.assertEqual((s1.hora_apertura, s1.hora_cierre), (time(5), time(7)))
                self.assertEqual(s1.estrategia_cupo, 'por_recurso_dia')
                self.assertEqual(s1.estrategia_precio, 'por_grupo')
                self.assertEqual(s1.modo_ocupacion, 'exclusivo')

                r1 = ReservaHistorica.objects.using(connection.alias).get(pk=reserva_pesca1.pk)
                self.assertEqual(r1.servicio_id, s1.pk)

                rp = ReservaHistorica.objects.using(connection.alias).get(pk=reserva_paquete1.pk)
                self.assertIsNone(rp.servicio_id)
                self.assertEqual(rp.paquete_id, paquete1.pk)

                # Comprobar Empresa 2 (creación con defaults)
                s2 = ServicioHistorico.objects.using(connection.alias).get(
                    empresa_id=empresa2.pk, slug='pesca-deportiva',
                )
                self.assertEqual(s2.nombre, 'Pesca Deportiva')
                self.assertTrue(s2.activo)
                self.assertEqual(s2.tipo_servicio, 'pesca')
                self.assertEqual(s2.precio_base, Decimal('4200'))
                self.assertIsNone(s2.precio_base_usd)
                self.assertEqual(s2.precio_persona_extra, Decimal('500'))
                self.assertIsNone(s2.precio_persona_extra_usd)
                self.assertEqual(s2.personas_incluidas, 3)
                self.assertEqual((s2.hora_apertura, s2.hora_cierre), (time(5), time(7)))

                r2 = ReservaHistorica.objects.using(connection.alias).get(pk=reserva_pesca2.pk)
                self.assertEqual(r2.servicio_id, s2.pk)

    def test_empresa_sin_tarifa_con_reserva_huerfana_falla_explicito(self):
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        SedeH = old_apps.get_model('tenancy', 'Sede')
        EmpresaH = old_apps.get_model('tenancy', 'Empresa')
        ReservaH = old_apps.get_model('bookings', 'Reserva')

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                sede = SedeH.objects.using(connection.alias).create(
                    nombre='Sede Mig Huerfana', slug='sede-mig-huerfana',
                )
                empresa3 = EmpresaH.objects.using(connection.alias).create(
                    sede_id=sede.pk, nombre='Empresa Sin Tarifa', slug='empresa-sin-tarifa', activo=True,
                )
                reserva_huerfana = ReservaH.objects.using(connection.alias).create(
                    empresa_id=empresa3.pk, fecha=date(2026, 12, 4), hora=time(6),
                    numero_personas=2, nombre_cliente='Cliente Huerfano',
                    telefono_cliente='6121111114', correo_cliente='ch@example.com',
                    moneda='MXN', deslinde_aceptado=True,
                )

        try:
            self.executor.loader.build_graph()
            with self.assertRaisesRegex(
                RuntimeError,
                rf'Falta configurar Servicio de pesca para empresa {empresa3.pk}',
            ):
                self.executor.migrate(self.migrate_to)
        finally:
            with transaction.atomic(using=connection.alias):
                with alcance_operador_migracion(connection):
                    ReservaH.objects.using(connection.alias).filter(pk=reserva_huerfana.pk).delete()

