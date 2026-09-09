"""Verificacion de las politicas RLS de 0003_rls.py contra Postgres.

Solo tienen sentido en Postgres -- sqlite no tiene RLS. `skipUnless` salta
toda la clase en local; el CI de Postgres es quien de verdad la ejerce.
"""
from unittest import skipUnless

from django.db import connection
from django.test import TransactionTestCase

from . import scope
from .models import Empresa, Sede


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class RLSTests(TransactionTestCase):
    def setUp(self):
        # Slugs deliberadamente distintos de los que siembra
        # tenancy.0002_crear_sede_empresa_la_paz ('la-paz'/'sal-y-sol'): esa fila
        # ya existe, committeada, en cualquier base recien migrada.
        sede = Sede.objects.create(nombre='Sede RLS', slug='sede-rls')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-rls-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-rls-b')

    def test_rol_de_test_no_es_superusuario_ni_bypassrls(self):
        # Primera aserción de la clase -- si esto falla, TODA la suite de RLS
        # pasaria en verde sin haber probado nada.
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user'
            )
            rolsuper, rolbypassrls = cursor.fetchone()
        if rolsuper or rolbypassrls:
            self.fail(
                f'El rol de test ({connection.settings_dict["USER"]}) tiene '
                f'rolsuper={rolsuper} rolbypassrls={rolbypassrls} -- RLS no '
                f'protege nada con este rol. Ver runbook de CI (seccion Infra).'
            )

    def test_dos_empresas_no_se_ven_por_orm(self):
        from apps.fleet.models import Embarcacion

        with scope.con_empresa(self.empresa_a):
            Embarcacion.objects.create(
                nombre='Panga A', clase='chica', capacidad_maxima=3, empresa=self.empresa_a,
            )
        with scope.con_empresa(self.empresa_b):
            Embarcacion.objects.create(
                nombre='Panga B', clase='chica', capacidad_maxima=3, empresa=self.empresa_b,
            )
            self.assertEqual(Embarcacion.objects.count(), 1)
            self.assertEqual(Embarcacion.objects.first().nombre, 'Panga B')

    def test_sin_set_local_devuelve_cero_filas_no_excepcion(self):
        from apps.fleet.models import Embarcacion

        with scope.con_empresa(self.empresa_a):
            Embarcacion.objects.create(
                nombre='Panga A', clase='chica', capacidad_maxima=3, empresa=self.empresa_a,
            )
        # Sin ningun con_empresa activo: SET LOCAL nunca se emitio en esta
        # transaccion nueva -- NULLIF(current_setting(...), '')::int es NULL,
        # la politica USING es NULL (falsa), cero filas.
        self.assertEqual(Embarcacion.objects.count(), 0)

    def test_insert_sin_alcance_falla(self):
        from django.db.utils import ProgrammingError

        from apps.fleet.models import Embarcacion

        with self.assertRaises(ProgrammingError):
            Embarcacion.objects.create(
                nombre='Sin alcance', clase='chica', capacidad_maxima=3, empresa=self.empresa_a,
            )

    def test_guardarrail_toda_tabla_con_empresa_tiene_politica(self):
        """Guardarraíl RLS (# postgres-only): verifica en Postgres que toda tabla con
        empresa_id o empresa_lider_id tenga su política tenancy_alcance en pg_policies,
        y que las tablas secundarias en la whitelist (vía FK EXISTS) también la tengan."""
        with connection.cursor() as cursor:
            # 1. Tablas de las apps de negocio con columna empresa_id o empresa_lider_id
            cursor.execute("""
                SELECT DISTINCT c.relname
                FROM pg_class c
                JOIN pg_attribute a ON a.attrelid = c.oid
                WHERE a.attname IN ('empresa_id', 'empresa_lider_id')
                  AND c.relkind = 'r'
                  AND c.relname LIKE ANY(ARRAY['fleet_%', 'bookings_%', 'payments_%', 'finance_%'])
                ORDER BY c.relname;
            """)
            tablas_con_columna = {row[0] for row in cursor.fetchall()}

            # 2. Tablas secundarias que llegan a empresa vía FK (sin columna empresa_id propia)
            whitelist_via_fk = {
                'bookings_reservaextra',
                'fleet_serviciopersonalizacion',
                'fleet_paqueteservicio',
                'bookings_reservapaquetepersonalizacion',
                'bookings_detalletransporte',
            }

            # 3. Consultar pg_policies
            cursor.execute("""
                SELECT tablename, policyname
                FROM pg_policies
                WHERE policyname = 'tenancy_alcance'
                  AND tablename LIKE ANY(ARRAY['fleet_%', 'bookings_%', 'payments_%', 'finance_%']);
            """)
            politicas_por_tabla = {row[0]: row[1] for row in cursor.fetchall()}

            # Aserción 1: Toda tabla con empresa_id / empresa_lider_id debe tener política tenancy_alcance
            sin_politica = tablas_con_columna - set(politicas_por_tabla.keys())
            self.assertEqual(
                sin_politica,
                set(),
                f"Tablas con columna de empresa que no tienen política RLS 'tenancy_alcance': {sin_politica}",
            )

            # Aserción 2: Todas las tablas de la whitelist vía FK deben tener política tenancy_alcance
            whitelist_sin_politica = whitelist_via_fk - set(politicas_por_tabla.keys())
            self.assertEqual(
                whitelist_sin_politica,
                set(),
                f"Tablas en whitelist vía FK que no tienen política RLS 'tenancy_alcance': {whitelist_sin_politica}",
            )

            # Aserción 3: Toda tabla protegida en las apps debe estar en tablas_con_columna o en whitelist
            todas_esperadas = tablas_con_columna | whitelist_via_fk
            politicas_inesperadas = set(politicas_por_tabla.keys()) - todas_esperadas
            self.assertEqual(
                politicas_inesperadas,
                set(),
                f"Tablas con política RLS que no están catalogadas ni en columnas ni en whitelist: {politicas_inesperadas}",
            )

    def test_detalle_transporte_aislamiento(self):
        from datetime import date, time
        from apps.bookings.models import DetalleTransporte, Reserva
        from apps.fleet.enums import TipoTraslado, Zona
        from apps.fleet.models import PuntoEncuentro, Servicio

        with scope.con_empresa(self.empresa_a):
            s_a = Servicio.objects.create(
                empresa=self.empresa_a,
                nombre='Traslado A',
                slug='traslado-a',
                tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda',
                estrategia_precio='por_ruta',
            )
            r_a = Reserva.objects.create(
                empresa=self.empresa_a,
                servicio=s_a,
                fecha=date(2026, 10, 1),
                hora=time(10, 0),
                numero_personas=2,
                nombre_cliente='Cliente A',
                canal_origen='web',
                deslinde_aceptado=True,
            )
            p_a = PuntoEncuentro.objects.create(
                empresa=self.empresa_a,
                nombre='Hotel A',
                zona=Zona.CENTRO,
            )
            DetalleTransporte.objects.create(
                reserva=r_a,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                punto_encuentro=p_a,
                fecha_regreso=date(2026, 10, 5),
            )

        with scope.con_empresa(self.empresa_b):
            s_b = Servicio.objects.create(
                empresa=self.empresa_b,
                nombre='Traslado B',
                slug='traslado-b',
                tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda',
                estrategia_precio='por_ruta',
            )
            r_b = Reserva.objects.create(
                empresa=self.empresa_b,
                servicio=s_b,
                fecha=date(2026, 10, 1),
                hora=time(10, 0),
                numero_personas=2,
                nombre_cliente='Cliente B',
                canal_origen='web',
                deslinde_aceptado=True,
            )
            p_b = PuntoEncuentro.objects.create(
                empresa=self.empresa_b,
                nombre='Hotel B',
                zona=Zona.CENTRO,
            )
            DetalleTransporte.objects.create(
                reserva=r_b,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                punto_encuentro=p_b,
                fecha_regreso=date(2026, 10, 5),
            )

            # Bajo empresa_b, solo debe ver el DetalleTransporte de empresa_b
            self.assertEqual(DetalleTransporte.objects.count(), 1)
            self.assertEqual(DetalleTransporte.objects.first().reserva.empresa_id, self.empresa_b.id)

        # Sin empresa activa, no ve nada
        self.assertEqual(DetalleTransporte.objects.count(), 0)
