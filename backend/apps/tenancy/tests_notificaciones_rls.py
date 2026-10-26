"""RLS de las notificaciones contra Postgres (0011_rls_notificacion).

Solo tienen sentido en Postgres con un rol sin BYPASSRLS (ver "Correr la suite contra Postgres en local" en
backend/CLAUDE.md): en sqlite no existe RLS y estas pruebas pasarian en verde sin probar nada.

Cada prueba crea sus propias Sede/Empresa/usuarios con slugs y nombres propios de esta clase; es una
TransactionTestCase porque la RLS y los candados solo se ejercen con transacciones reales.
"""
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import connection, transaction
from django.db.utils import ProgrammingError
from django.test import TransactionTestCase

from . import notificaciones, scope
from .models import Empresa, LecturaNotificacion, Notificacion, Sede

TABLAS = ('tenancy_notificacion', 'tenancy_lecturanotificacion')


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class NotificacionRLSTests(TransactionTestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='Sede notif RLS', slug='sede-notif-rls')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='Notif A', slug='empresa-notif-rls-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='Notif B', slug='empresa-notif-rls-b')
        self.usuario = User.objects.create_user('notif-rls-usuario', password='x')

    def _crear(self, empresa, texto):
        with scope.con_empresa(empresa):
            return Notificacion.objects.create(empresa=empresa, nivel=Notificacion.Nivel.EXITO, texto=texto)

    def test_las_dos_tablas_tienen_su_politica_y_rls_forzada(self):
        """El guardarrail de tests_rls.py solo mira los prefijos fleet_/bookings_/payments_/finance_, asi que NO ve
        las tablas de tenancy: esta es la red que si las cubre."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_policies WHERE policyname = 'tenancy_alcance' AND tablename = ANY(%s)",
                [list(TABLAS)],
            )
            con_politica = {fila[0] for fila in cursor.fetchall()}
            cursor.execute(
                'SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = ANY(%s)',
                [list(TABLAS)],
            )
            estado = {fila[0]: (fila[1], fila[2]) for fila in cursor.fetchall()}

        self.assertEqual(con_politica, set(TABLAS))
        self.assertEqual(estado, {tabla: (True, True) for tabla in TABLAS})

    def test_una_empresa_no_ve_las_notificaciones_de_otra(self):
        self._crear(self.empresa_a, 'solo de A')
        self._crear(self.empresa_b, 'solo de B')

        with scope.con_empresa(self.empresa_a):
            self.assertEqual(list(Notificacion.objects.values_list('texto', flat=True)), ['solo de A'])
        with scope.con_empresa(self.empresa_b):
            self.assertEqual(list(Notificacion.objects.values_list('texto', flat=True)), ['solo de B'])

    def test_una_empresa_no_ve_las_lecturas_de_otra(self):
        nota_a = self._crear(self.empresa_a, 'de A')
        with scope.con_empresa(self.empresa_a):
            LecturaNotificacion.objects.create(empresa=self.empresa_a, notificacion=nota_a, usuario=self.usuario)

        with scope.con_empresa(self.empresa_b):
            self.assertEqual(LecturaNotificacion.objects.count(), 0)
        with scope.con_empresa(self.empresa_a):
            self.assertEqual(LecturaNotificacion.objects.count(), 1)

    def test_sin_alcance_no_se_ve_nada_y_no_se_puede_escribir(self):
        self._crear(self.empresa_a, 'de A')

        self.assertEqual(Notificacion.objects.count(), 0)
        with self.assertRaises(ProgrammingError), transaction.atomic():
            Notificacion.objects.create(empresa=self.empresa_a, nivel='exito', texto='sin alcance')

    def test_no_se_puede_escribir_a_nombre_de_otra_empresa(self):
        with scope.con_empresa(self.empresa_a):
            with self.assertRaises(ProgrammingError), transaction.atomic():
                Notificacion.objects.create(empresa=self.empresa_b, nivel='exito', texto='colada')

    def test_el_operador_de_plataforma_ve_y_cuenta_las_de_todas_las_empresas(self):
        self._crear(self.empresa_a, 'de A')
        self._crear(self.empresa_b, 'de B')

        with scope.como_operador_plataforma():
            self.assertEqual(Notificacion.objects.count(), 2)

    def test_un_rechazo_de_rls_no_tumba_la_transaccion_de_quien_llama(self):
        """R5 en Postgres: un INSERT rechazado deja abortada la transaccion entera salvo que vaya en su propio
        savepoint. Sin el, la accion del usuario (asignar, cobrar...) se revertiria en silencio al confirmar."""
        with scope.con_empresa(self.empresa_a):
            with transaction.atomic():  # la accion del usuario
                antes = notificaciones.registrar_notificacion(self.empresa_a, 'exito', 'antes')
                with self.assertLogs('apps.tenancy.notificaciones', level='ERROR'):
                    ajena = notificaciones.registrar_notificacion(self.empresa_b, 'exito', 'a nombre de B')
                despues = notificaciones.registrar_notificacion(self.empresa_a, 'exito', 'despues')

        self.assertIsNone(ajena)
        self.assertIsNotNone(antes)
        self.assertIsNotNone(despues)
        with scope.con_empresa(self.empresa_a):
            self.assertEqual(set(Notificacion.objects.values_list('texto', flat=True)), {'antes', 'despues'})

    def test_desde_un_callback_post_commit_que_reabre_su_alcance_si_escribe(self):
        """R2: el patron de `signals._mandar` y del webhook. El callback corre al COMMIT, ya sin el SET LOCAL de la
        transaccion que lo encolo, y reabre `con_empresa` con el id capturado."""
        empresa_id = self.empresa_a.pk

        def callback():
            with scope.con_empresa(Empresa.objects.get(pk=empresa_id)):
                notificaciones.registrar_notificacion(
                    Empresa.objects.get(pk=empresa_id), 'exito', 'desde el callback')

        with scope.con_empresa(self.empresa_a):
            transaction.on_commit(callback)

        with scope.con_empresa(self.empresa_a):
            self.assertEqual(list(Notificacion.objects.values_list('texto', flat=True)), ['desde el callback'])

    def test_un_callback_que_no_reabre_su_alcance_no_escribe_pero_tampoco_truena(self):
        """El mismo callback SIN reabrir el alcance: RLS rechaza el INSERT. `registrar_notificacion` lo registra y
        regresa None; la accion que lo encolo ya se confirmo y no se entera."""
        resultados = []

        def callback_sin_alcance():
            resultados.append(notificaciones.registrar_notificacion(self.empresa_a, 'exito', 'sin alcance'))

        with self.assertLogs('apps.tenancy.notificaciones', level='ERROR'):
            with scope.con_empresa(self.empresa_a):
                transaction.on_commit(callback_sin_alcance)

        self.assertEqual(resultados, [None])
        with scope.como_operador_plataforma():
            self.assertEqual(Notificacion.objects.count(), 0)

    def test_marcar_leidas_solo_escribe_dentro_del_alcance_de_la_empresa(self):
        nota_a = self._crear(self.empresa_a, 'de A')
        nota_b = self._crear(self.empresa_b, 'de B')

        with scope.con_empresa(self.empresa_a):
            notificaciones.marcar_leidas(self.usuario, [nota_a])
            with self.assertRaises(ProgrammingError), transaction.atomic():
                notificaciones.marcar_leidas(self.usuario, [nota_b])

        with scope.como_operador_plataforma():
            self.assertEqual(
                list(LecturaNotificacion.objects.values_list('notificacion_id', flat=True)), [nota_a.pk])
