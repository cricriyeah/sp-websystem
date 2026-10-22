"""La columna nueva deja intactas las reservas creadas antes de B1."""

from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.fleet.models import Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class ReservaTransferenciaMigration0054Tests(TransactionTestCase):
    def test_reserva_existente_conserva_transferencia_nula(self):
        executor = MigrationExecutor(connection)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()))
        sede = Sede.objects.create(nombre='Migración transferencia', slug='migracion-transferencia')
        empresa = Empresa.objects.create(sede=sede, nombre='Empresa migración', slug='empresa-migracion')
        with scope.como_operador_plataforma():  # las tablas con RLS no dejan insertar sin alcance
            servicio = Servicio.objects.create(empresa=empresa, nombre='Servicio migración', slug='servicio-migracion')
            reserva = Reserva.objects.create(
                empresa=empresa, servicio=servicio, fecha=timezone.localdate() + timedelta(days=10),
                numero_personas=2, nombre_cliente='Cliente anterior', telefono_cliente='6121234567',
                correo_cliente='anterior@example.com', canal_origen='whatsapp',
            )

        executor.migrate([('bookings', '0053_tipo_cambio_reserva_orden')])

        executor = MigrationExecutor(connection)
        executor.migrate([('bookings', '0054_reserva_monto_transferencia_and_more')])
        nueva = executor.loader.project_state(
            [('bookings', '0054_reserva_monto_transferencia_and_more')]).apps.get_model('bookings', 'Reserva')
        with scope.como_operador_plataforma():
            conservada = nueva.objects.get(pk=reserva.pk)
        self.assertIsNone(conservada.monto_transferencia)
        self.assertIsNone(conservada.transferencia_registrada_en)
        self.assertIsNone(conservada.transferencia_registrada_por_id)
