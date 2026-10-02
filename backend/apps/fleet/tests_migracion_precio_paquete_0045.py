from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from apps.fleet.models import Paquete
from apps.tenancy.rls import alcance_operador_migracion


class PrecioPaqueteMigration0045Tests(TransactionTestCase):
    migrate_from = [('fleet', '0044_quitar_precios_usd')]
    migrate_to = [('fleet', '0045_normalizar_precio_paquete')]

    def setUp(self):
        super().setUp()
        self.addCleanup(self._restaurar)
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        self.executor.loader.build_graph()
        old = self.executor.loader.project_state(self.migrate_from).apps
        with transaction.atomic(), alcance_operador_migracion(connection):
            sede = old.get_model('tenancy', 'Sede').objects.create(
                nombre='Migración paquete', slug='migracion-paquete',
            )
            empresa = old.get_model('tenancy', 'Empresa').objects.create(
                sede=sede, nombre='Empresa migración', slug='empresa-migracion', activo=True,
            )
            servicio = old.get_model('fleet', 'Servicio').objects.create(
                empresa=empresa, nombre='Pesca', slug='pesca-migracion',
            )
            Paquete = old.get_model('fleet', 'Paquete')
            fijo = Paquete.objects.create(
                sede=sede, empresa_lider=empresa, nombre='Fijo', slug='fijo',
                precio_ancla=Decimal('5000.00'), precio_por_persona=False,
            )
            por_persona = Paquete.objects.create(
                sede=sede, empresa_lider=empresa, nombre='Individual', slug='individual',
                precio_ancla=Decimal('1200.00'), precio_por_persona=True,
            )
            old.get_model('fleet', 'PaqueteServicio').objects.create(
                paquete=fijo, servicio=servicio, personas_incluidas=5,
            )
            self.fijo_pk, self.individual_pk = fijo.pk, por_persona.pk

    def _restaurar(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_migra_dos_paquetes_bajo_rls_y_revierte_sin_extra(self):
        self.executor.migrate(self.migrate_to)
        self.executor.loader.build_graph()
        actual = self.executor.loader.project_state(self.migrate_to).apps
        Paquete = actual.get_model('fleet', 'Paquete')
        with transaction.atomic(), alcance_operador_migracion(connection):
            fijo = Paquete.objects.get(pk=self.fijo_pk)
            individual = Paquete.objects.get(pk=self.individual_pk)
            self.assertEqual(
                (fijo.estrategia_precio, fijo.personas_precio_base, fijo.precio_persona_extra),
                ('por_grupo', 5, Decimal('0.00')),
            )
            self.assertEqual(
                (individual.estrategia_precio, individual.personas_precio_base,
                 individual.precio_persona_extra),
                ('por_persona', 1, Decimal('0.00')),
            )
        self.executor.migrate(self.migrate_from)
        viejo = self.executor.loader.project_state(self.migrate_from).apps.get_model('fleet', 'Paquete')
        with transaction.atomic(), alcance_operador_migracion(connection):
            self.assertFalse(viejo.objects.get(pk=self.fijo_pk).precio_por_persona)
            self.assertTrue(viejo.objects.get(pk=self.individual_pk).precio_por_persona)

    def test_reversa_rechaza_extra_que_no_puede_representar(self):
        self.executor.migrate(self.migrate_to)
        self.executor.loader.build_graph()
        actual = self.executor.loader.project_state(self.migrate_to).apps.get_model('fleet', 'Paquete')
        with transaction.atomic(), alcance_operador_migracion(connection):
            actual.objects.filter(pk=self.fijo_pk).update(precio_persona_extra=Decimal('500.00'))
        with self.assertRaisesRegex(RuntimeError, 'precio_persona_extra'):
            self.executor.migrate(self.migrate_from)
        with transaction.atomic(), alcance_operador_migracion(connection):
            actual.objects.filter(pk=self.fijo_pk).update(precio_persona_extra=Decimal('0.00'))


class PrecioPaqueteFieldsTests(TestCase):
    def test_configuracion_por_persona_normaliza_campos_inertes(self):
        paquete = Paquete(
            estrategia_precio='por_persona', personas_precio_base=4,
            precio_persona_extra=Decimal('300.00'),
        )
        paquete.clean()
        self.assertEqual(paquete.personas_precio_base, 1)
        self.assertEqual(paquete.precio_persona_extra, Decimal('0'))

    def test_rechaza_base_cero_extra_negativo_y_estrategia_no_admitida(self):
        with self.assertRaises(ValidationError):
            Paquete(estrategia_precio='por_grupo', personas_precio_base=0).clean()
        with self.assertRaises(ValidationError):
            Paquete(estrategia_precio='por_grupo', precio_persona_extra=Decimal('-1')).clean()
        with self.assertRaises(ValidationError):
            Paquete(estrategia_precio='por_ruta').clean()

    def test_el_selector_de_paquete_solo_tiene_dos_estrategias(self):
        choices = dict(Paquete._meta.get_field('estrategia_precio').choices)
        self.assertEqual(set(choices), {'por_grupo', 'por_persona'})


class PrecioPaqueteFinal0046Tests(TransactionTestCase):
    migrate_from = [('fleet', '0045_normalizar_precio_paquete')]
    migrate_to = [('fleet', '0046_quitar_precio_por_persona')]

    def test_quita_solo_el_campo_antiguo_y_conserva_estrategia(self):
        executor = MigrationExecutor(connection)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        ))
        executor.migrate(self.migrate_from)
        executor.loader.build_graph()
        viejo = executor.loader.project_state(self.migrate_from).apps
        with transaction.atomic(), alcance_operador_migracion(connection):
            sede = viejo.get_model('tenancy', 'Sede').objects.create(
                nombre='Migración final', slug='migracion-final',
            )
            empresa = viejo.get_model('tenancy', 'Empresa').objects.create(
                sede=sede, nombre='Empresa final', slug='empresa-final', activo=True,
            )
            paquete = viejo.get_model('fleet', 'Paquete').objects.create(
                sede=sede, empresa_lider=empresa, nombre='Individual', slug='individual',
                precio_ancla=Decimal('1200.00'), precio_por_persona=True,
                estrategia_precio='por_persona',
            )
        executor.migrate(self.migrate_to)
        nuevo = executor.loader.project_state(self.migrate_to).apps.get_model('fleet', 'Paquete')
        self.assertNotIn('precio_por_persona', [f.name for f in nuevo._meta.fields])
        with transaction.atomic(), alcance_operador_migracion(connection):
            self.assertEqual(nuevo.objects.get(pk=paquete.pk).estrategia_precio, 'por_persona')
