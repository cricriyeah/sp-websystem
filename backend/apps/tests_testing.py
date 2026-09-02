"""Pruebas del propio helper de tests — si esto se rompe, se rompe TODO lo demás."""
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase

from apps.testing import ApiTestCase, EmpresaTestCase, crear_flota
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede


class EmpresaTestCaseTests(TestCase):
    def test_crea_su_propia_sede_y_empresa(self):
        class Caso(EmpresaTestCase):
            def runTest(self):
                pass

        caso = Caso()
        caso._pre_setup()
        try:
            self.assertIsInstance(caso.sede, Sede)
            self.assertIsInstance(caso.empresa, Empresa)
            self.assertEqual(caso.empresa.slug, 'empresa-test')
            self.assertTrue(caso.empresa.activo)
        finally:
            caso._post_teardown()

    def test_no_choca_con_la_empresa_sembrada_por_la_migracion_de_datos(self):
        """`tenancy.0002_crear_sede_empresa_la_paz` ya deja una fila con
        slug='sal-y-sol' committeada antes de que arranque cualquier test — un
        TestCase normal ve esa fila (su transaccion no la oculta, solo aisla lo
        que el propio test escribe). Si EmpresaTestCase reusara ese mismo slug,
        el segundo `Empresa.objects.create(slug='sal-y-sol', ...)` reventaria con
        IntegrityError en el primer test que corriera. Por eso EmpresaTestCase usa
        un slug distinto ('empresa-test') a proposito."""
        self.assertTrue(Empresa.objects.filter(slug='sal-y-sol').exists())

    def test_el_alcance_queda_abierto_durante_el_test_y_cerrado_despues(self):
        class Caso(EmpresaTestCase):
            def runTest(self):
                pass

        caso = Caso()
        caso._pre_setup()
        alcance_durante = connection.alcance_actual
        caso._post_teardown()

        self.assertEqual(alcance_durante, ('empresa', caso.empresa.pk))
        self.assertIsNone(connection.alcance_actual)

    def test_crear_jefe_resuelve_alcance_como_jefe_de_su_empresa(self):
        class Caso(EmpresaTestCase):
            def runTest(self):
                pass

        caso = Caso()
        caso._pre_setup()
        try:
            jefe = caso.crear_jefe()
            self.assertTrue(Group.objects.get(name='Jefe').user_set.filter(pk=jefe.pk).exists())
            self.assertTrue(
                MembresiaEmpresa.objects.filter(
                    user=jefe, empresa=caso.empresa, rol=MembresiaEmpresa.Rol.JEFE,
                ).exists()
            )
        finally:
            caso._post_teardown()

    def test_crear_vendedora_sin_permisos_extra_no_tiene_ninguno(self):
        class Caso(EmpresaTestCase):
            def runTest(self):
                pass

        caso = Caso()
        caso._pre_setup()
        try:
            vendedora = caso.crear_vendedora(permisos=[])
            self.assertFalse(vendedora.user_permissions.exists())
            self.assertTrue(
                MembresiaEmpresa.objects.filter(
                    user=vendedora, empresa=caso.empresa,
                    rol=MembresiaEmpresa.Rol.VENDEDORA,
                ).exists()
            )
        finally:
            caso._post_teardown()


class CrearFlotaTests(ApiTestCase):
    def test_exige_empresa_como_primer_argumento(self):
        with self.assertRaises(TypeError):
            crear_flota()

    def test_crea_la_flota_solo_para_su_empresa(self):
        otra_sede = Sede.objects.create(nombre='Otra Sede', slug='otra-sede', zona_horaria='America/Mazatlan')
        otra_empresa = Empresa.objects.create(sede=otra_sede, nombre='Otra', slug='otra', activo=True)

        propia = crear_flota(self.empresa)
        self.assertTrue(all(p.empresa_id == self.empresa.pk for p in propia))

        # crear_flota de otra empresa no debe ver ni reusar la de self.empresa.
        # con_empresa no es reentrante con un valor distinto: hay que cerrar el
        # alcance abierto por ApiTestCase._pre_setup antes de abrir el de
        # otra_empresa, y reabrir el propio (nuevo context manager -- el que
        # guarda self._alcance ya se uso una vez) para que _post_teardown lo
        # cierre simetrico.
        #
        # Composicion con capacidad distinta a proposito: crear_flota nombra
        # 'Panga {capacidad}-{i}' sin distinguir empresa, y Embarcacion.nombre
        # sigue siendo unique=True GLOBAL hasta que Fleet lo vuelva
        # unique_together con empresa (tarea posterior de este mismo plan) --
        # cualquier capacidad ya usada por FLOTA_REAL (3 o 5) chocaria con los
        # nombres que 'propia' ya creo arriba.
        from apps.tenancy import scope
        self._alcance.__exit__(None, None, None)
        with scope.con_empresa(otra_empresa):
            ajena = crear_flota(otra_empresa, composicion=[(2, 4)])
        self._alcance = scope.con_empresa(self.empresa)
        self._alcance.__enter__()

        self.assertTrue(all(p.empresa_id == otra_empresa.pk for p in ajena))
        self.assertEqual(len(ajena), 2)
