"""Verificacion de las politicas RLS de 0003_rls.py contra Postgres.

Solo tienen sentido en Postgres -- sqlite no tiene RLS. `skipUnless` salta
toda la clase en local; el CI de Postgres es quien de verdad la ejerce.
"""
from unittest import skipUnless

from django.db import connection
from django.test import TransactionTestCase

from . import scope
from .models import Empresa, Sede


# Tablas secundarias que llegan a empresa vía FK. ReservaExtra permanece hasta
# la Tarea 11; el rename de Tarea 2 ya usa el nombre físico nuevo.
WHITELIST_VIA_FK = {
    'fleet_serviciopersonalizacion',
    'fleet_paqueteservicio',
    'bookings_reservapersonalizacion',
    'bookings_detalletransporte',
}


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
            # Nota: bookings_orden tiene empresa_lider_id y su política tenancy_alcance es
            # sede-scoped (las órdenes cruzan empresas de la misma sede, permitiendo lectura
            # a empresas de la misma sede e INSERT público vía WITH CHECK).

            # 2. Tablas secundarias que llegan a empresa vía FK (sin columna empresa_id propia)
            whitelist_via_fk = WHITELIST_VIA_FK

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

    def test_whitelist_conserva_nombre_nuevo_y_extra_legacy(self):
        self.assertIn('bookings_reservapersonalizacion', WHITELIST_VIA_FK)

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

    def test_orden_sede_scoped_rls(self):
        from decimal import Decimal
        from apps.bookings.models import Orden
        from apps.fleet.models import Paquete

        # Dos sedes
        sede_b = Sede.objects.create(nombre='Sede B', slug='sede-b')
        empresa_b2 = Empresa.objects.create(sede=sede_b, nombre='B2', slug='empresa-b2')

        with scope.como_operador_plataforma():
            paq_a = Paquete.objects.create(
                sede=self.empresa_a.sede,
                empresa_lider=self.empresa_a,
                nombre='Paquete A',
                slug='paquete-a',
                precio_ancla=Decimal('1000.00'),
            )
            paq_b = Paquete.objects.create(
                sede=sede_b,
                empresa_lider=empresa_b2,
                nombre='Paquete B',
                slug='paquete-b',
                precio_ancla=Decimal('1000.00'),
            )

        # 1. INSERT con scope.con_empresa(<empresa de esa sede>): funciona (INSERT + RETURNING)
        with scope.con_empresa(self.empresa_a):
            orden_a = Orden.objects.create(
                sede=self.empresa_a.sede,
                empresa_lider=self.empresa_a,
                paquete=paq_a,
                nombre_cliente='Cliente A',
                telefono_cliente='1234567890',
                correo_cliente='a@example.com',
            )
        with scope.con_empresa(empresa_b2):
            orden_b = Orden.objects.create(
                sede=sede_b,
                empresa_lider=empresa_b2,
                paquete=paq_b,
                nombre_cliente='Cliente B',
                telefono_cliente='1234567890',
                correo_cliente='b@example.com',
            )

        # 2. INSERT crudo sin RETURNING y sin contexto: sigue pasando por WITH CHECK
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO bookings_orden (
                    sede_id, empresa_lider_id, paquete_id, nombre_cliente,
                    telefono_cliente, correo_cliente, moneda, forma_pago,
                    estado, creado_en, actualizado_en
                ) VALUES (
                    %s, %s, %s, 'Cliente Crudo', '1234567890', 'crudo@example.com',
                    'MXN', 'completo', 'armando', NOW(), NOW()
                );
            """, [self.empresa_a.sede_id, self.empresa_a.id, paq_a.id])

        # 3. Jefe / vendedora de empresa_a (sede_a): ve orden_a + orden cruda, NO ve orden_b
        with scope.con_empresa(self.empresa_a):
            ordenes_a = list(Orden.objects.all())
            self.assertEqual(len(ordenes_a), 2)
            for o in ordenes_a:
                self.assertEqual(o.sede_id, self.empresa_a.sede_id)

        # 4. Jefe / vendedora de empresa_b2 (sede_b): ve orden_b, NO ve órdenes de sede_a
        with scope.con_empresa(empresa_b2):
            ordenes_b = list(Orden.objects.all())
            self.assertEqual(len(ordenes_b), 1)
            self.assertEqual(ordenes_b[0].id, orden_b.id)

            # Prueba de que no hay bypass por current_query() ~* '^\s*INSERT':
            # Un INSERT INTO ... SELECT ... desde empresa_b2 NO debe poder leer órdenes de sede_a
            with connection.cursor() as cursor:
                cursor.execute("CREATE TEMP TABLE tmp_ordenes_leidas (orden_id bigint);")
                cursor.execute(
                    "INSERT INTO tmp_ordenes_leidas SELECT id FROM bookings_orden WHERE sede_id = %s;",
                    [self.empresa_a.sede_id],
                )
                cursor.execute("SELECT COUNT(*) FROM tmp_ordenes_leidas;")
                leidas_sede_a = cursor.fetchone()[0]
                cursor.execute("DROP TABLE tmp_ordenes_leidas;")
                self.assertEqual(
                    leidas_sede_a,
                    0,
                    f"Vulnerabilidad RLS detectada: se leyeron {leidas_sede_a} órdenes de otra sede vía INSERT INTO ... SELECT",
                )

        # 5. Operador de plataforma: ve todas (orden_a + orden_b + orden cruda = 3)
        with scope.como_operador_plataforma():
            self.assertEqual(Orden.objects.count(), 3)

        # 6. Sin contexto de empresa (público): no ve ninguna (0 filas)
        self.assertEqual(Orden.objects.count(), 0)

    def test_escape_explicito_funcion_estado_reservas_en_pg_proc(self):
        """Verifica que la función SECURITY DEFINER estado_reservas_de_orden exista
        y pertenezca a la whitelist de escapes explícitos de RLS."""
        WHITELIST_FUNCIONES_ESCAPE = {'estado_reservas_de_orden'}
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT proname FROM pg_proc
                JOIN pg_namespace n ON pg_proc.pronamespace = n.oid
                WHERE n.nspname = 'public' AND prosecdef = true;
            """)
            funciones_secdef = {row[0] for row in cursor.fetchall()}
            self.assertTrue(
                WHITELIST_FUNCIONES_ESCAPE.issubset(funciones_secdef),
                f"Funciones SECURITY DEFINER esperadas no encontradas: {WHITELIST_FUNCIONES_ESCAPE - funciones_secdef}",
            )

    def test_estado_reservas_de_orden_security_definer(self):
        from decimal import Decimal
        from datetime import date, time
        from apps.bookings.models import Orden, Reserva
        from apps.bookings.orden_lectura import reservas_de_orden
        from apps.fleet.models import Paquete, Servicio

        with scope.como_operador_plataforma():
            paq = Paquete.objects.create(
                sede=self.empresa_a.sede,
                empresa_lider=self.empresa_a,
                nombre='Paquete Mixto',
                slug='paquete-mixto',
                precio_ancla=Decimal('1000.00'),
            )
            s_a = Servicio.objects.create(
                empresa=self.empresa_a,
                nombre='Pesca A',
                slug='pesca-a',
            )
            s_b = Servicio.objects.create(
                empresa=self.empresa_b,
                nombre='Traslado B',
                slug='traslado-b',
            )

        with scope.con_empresa(self.empresa_a):
            orden = Orden.objects.create(
                sede=self.empresa_a.sede,
                empresa_lider=self.empresa_a,
                paquete=paq,
                nombre_cliente='Cliente Cruzado',
                telefono_cliente='1234567890',
                correo_cliente='cruzado@example.com',
            )
            r_a = Reserva.objects.create(
                empresa=self.empresa_a,
                servicio=s_a,
                orden=orden,
                fecha=date(2026, 10, 1),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Cruzado',
                canal_origen='web',
                deslinde_aceptado=True,
            )

        with scope.con_empresa(self.empresa_b):
            r_b = Reserva.objects.create(
                empresa=self.empresa_b,
                servicio=s_b,
                orden=orden,
                fecha=date(2026, 10, 1),
                hora=time(7, 0),
                numero_personas=2,
                nombre_cliente='Cliente Cruzado',
                canal_origen='web',
                deslinde_aceptado=True,
            )

        # Bajo el contexto de la Empresa A:
        with scope.con_empresa(self.empresa_a):
            # El ORM normal solo ve la reserva de Empresa A (1 fila)
            self.assertEqual(orden.reservas.count(), 1)
            self.assertEqual(orden.reservas.first().id, r_a.id)

            # La función SECURITY DEFINER ve las 2 reservas de la orden
            filas = reservas_de_orden(orden.id)
            self.assertEqual(len(filas), 2)
            ids = {f['reserva_id'] for f in filas}
            self.assertEqual(ids, {r_a.id, r_b.id})

