from decimal import Decimal
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PersonalizacionMigration0030Tests(TransactionTestCase):
    """Prueba la migracion de datos 0030_personalizacion_tipo_interaccion.

    Verifica que:
    1. Las asociaciones de tipo check con obligatorio=True se normalizan a obligatorio=False y preseleccionado=True.
    2. Los precios (precio y precio_usd) se conservan intactos.
    3. Una base con catalogo vacio migra sin errores y no recibe semillas espurias.
    """
    migrate_from = [('fleet', '0029_servicio_hora_apertura_servicio_hora_cierre')]
    migrate_to = [('fleet', '0030_personalizacion_tipo_interaccion')]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        # Asegurar estado en migrate_from
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps

        # Crear datos de prueba con modelos historicos previos
        SedeModel = old_apps.get_model('tenancy', 'Sede')
        EmpresaModel = old_apps.get_model('tenancy', 'Empresa')
        ServicioModel = old_apps.get_model('fleet', 'Servicio')
        PersonalizacionModel = old_apps.get_model('fleet', 'Personalizacion')
        SPModel = old_apps.get_model('fleet', 'ServicioPersonalizacion')

        self.sede = SedeModel.objects.create(nombre='Sede Mig', slug='sede-mig')
        self.empresa = EmpresaModel.objects.create(
            sede=self.sede, nombre='Empresa Mig', slug='empresa-mig', activo=True
        )
        self.servicio = ServicioModel.objects.create(
            empresa=self.empresa, nombre='Tour Mig', slug='tour-mig'
        )

        # SP 1: check obligatorio=True, preseleccionado=False con precios
        self.p1 = PersonalizacionModel.objects.create(
            empresa=self.empresa, nombre='Check Obligatorio'
        )
        self.sp1 = SPModel.objects.create(
            servicio=self.servicio, personalizacion=self.p1,
            obligatorio=True, preseleccionado=False,
            precio=Decimal('250.00'), precio_usd=Decimal('15.00')
        )

        # SP 2: check ya opcional (obligatorio=False, preseleccionado=False)
        self.p2 = PersonalizacionModel.objects.create(
            empresa=self.empresa, nombre='Check Opcional'
        )
        self.sp2 = SPModel.objects.create(
            servicio=self.servicio, personalizacion=self.p2,
            obligatorio=False, preseleccionado=False,
            precio=Decimal('100.00'), precio_usd=None
        )

    def tearDown(self):
        # Restaurar migraciones al estado actual para no afectar otros tests
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_migracion_normaliza_checks_obligatorios_a_preseleccionados(self):
        # Ejecutar migracion hacia 0030
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps

        SPModel = new_apps.get_model('fleet', 'ServicioPersonalizacion')
        PersonalizacionModel = new_apps.get_model('fleet', 'Personalizacion')

        sp1 = SPModel.objects.get(pk=self.sp1.pk)
        self.assertFalse(sp1.obligatorio)
        self.assertTrue(sp1.preseleccionado)
        self.assertEqual(sp1.precio, Decimal('250.00'))
        self.assertEqual(sp1.precio_usd, Decimal('15.00'))

        sp2 = SPModel.objects.get(pk=self.sp2.pk)
        self.assertFalse(sp2.obligatorio)
        self.assertFalse(sp2.preseleccionado)
        self.assertEqual(sp2.precio, Decimal('100.00'))
        self.assertIsNone(sp2.precio_usd)

        # Verificar campos default en Personalizacion
        p1 = PersonalizacionModel.objects.get(pk=self.p1.pk)
        self.assertEqual(p1.tipo_interaccion, 'check')
        self.assertEqual(p1.opciones_seleccion, [])
        self.assertFalse(p1.aviso_reforzado)

    def test_catalogo_vacio_migra_sin_semillas_y_sin_errores(self):
        # Asegurar catálogo vacío borrando los registros creados en setUp
        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        old_apps.get_model('fleet', 'ServicioPersonalizacion').objects.all().delete()
        old_apps.get_model('fleet', 'Personalizacion').objects.all().delete()

        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps

        SPModel = new_apps.get_model('fleet', 'ServicioPersonalizacion')
        PersonalizacionModel = new_apps.get_model('fleet', 'Personalizacion')
        self.assertEqual(SPModel.objects.count(), 0)
        self.assertEqual(PersonalizacionModel.objects.count(), 0)
