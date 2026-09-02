"""Utilidades compartidas por los tests de las apps."""

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from apps.fleet.models import Embarcacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede

# Slug deliberadamente distinto del que siembra tenancy.0002_crear_sede_empresa_la_paz
# ('sal-y-sol'): esa fila ya existe, committeada, en cualquier base de test recien
# migrada -- un TestCase normal la ve (su transaccion aisla lo que el test escribe, no
# lo que ya estaba antes de que empezara). Reusar el mismo slug aqui chocaria con
# IntegrityError en el primer test que corriera.
SLUG_EMPRESA_DE_PRUEBA = 'empresa-test'


class EmpresaTestCase(TestCase):
    """Base de tenancy para cualquier test que toque un modelo con FK `empresa`.

    Crea su propia Sede + Empresa en `_pre_setup` (antes de `setUp`, para que corra
    incluso en las ~20 clases de este repo que definen su propio `setUp` sin llamar a
    `super()`) y abre `scope.con_empresa(self.empresa)` para todo el ciclo de vida del
    test -- se cierra simetricamente en `_post_teardown` via el propio manejador de
    contexto guardado en la instancia, no con `addCleanup` (`_post_teardown` ya es el
    gancho simetrico de `_pre_setup`, correr ahi evita depender del orden entre
    cleanups registrados por el test y por esta clase).

    Tambien corre `setup_roles` (idempotente, mismo comando que producción) para que
    los grupos `Jefe`/`Vendedora`/`OperadorPlataforma` con sus permisos reales existan
    en la base de test -- sin esto `crear_jefe`/`crear_vendedora` (abajo) no tendrian
    grupo al que agregar al usuario.
    """

    def _pre_setup(self):
        super()._pre_setup()
        call_command('setup_roles', verbosity=0)
        self.sede = Sede.objects.create(
            nombre='Sede de prueba', slug='sede-test', zona_horaria='America/Mazatlan', activo=True,
        )
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa de prueba', slug=SLUG_EMPRESA_DE_PRUEBA,
            activo=True, exclusiva=False,
        )
        self._alcance = scope.con_empresa(self.empresa)
        self._alcance.__enter__()

    def _post_teardown(self):
        self._alcance.__exit__(None, None, None)
        super()._post_teardown()

    def crear_jefe(self, username='jefa', **extra):
        """Usuario con membresia JEFE de `self.empresa` + grupo Django `Jefe`.

        Reemplaza `User.objects.create_superuser(...)` en toda la suite: los jefes ya
        no llevan `is_superuser` (ver plan, "Operador de plataforma: no es una
        MembresiaEmpresa"), y sin `MembresiaEmpresa`, `EmpresaScopeMiddleware` rechaza
        con 403 antes de que la vista corra.
        """
        extra.setdefault('password', 'x')
        jefe = User.objects.create_user(username, is_staff=True, **extra)
        jefe.groups.add(Group.objects.get(name='Jefe'))
        MembresiaEmpresa.objects.create(user=jefe, empresa=self.empresa, rol=MembresiaEmpresa.Rol.JEFE)
        return jefe

    def crear_vendedora(self, username='vendedora', permisos=None, **extra):
        """Usuario con membresia VENDEDORA de `self.empresa`.

        `permisos=None` (default) agrega el grupo `Vendedora` completo -- caso normal.
        `permisos=[]` u otra lista deja al usuario SIN el grupo, solo con los
        permisos individuales que se le pasen aparte (para probar 403 por falta de un
        permiso puntual sin que el 403 salga en realidad por falta de alcance, que es
        el bug que esta tarea corrige -- ver nota al inicio de este documento).
        """
        extra.setdefault('password', 'x')
        vendedora = User.objects.create_user(username, is_staff=True, **extra)
        if permisos is None:
            vendedora.groups.add(Group.objects.get(name='Vendedora'))
        MembresiaEmpresa.objects.create(
            user=vendedora, empresa=self.empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        return vendedora


class ApiTestCase(EmpresaTestCase):
    """Base para los tests que pegan a la API publica.

    DRF lleva la cuenta de peticiones por IP en el cache de Django, y ese cache
    **no** se reinicia entre tests como si pasa con la base de datos. Sin esto
    una clase hereda el contador de la anterior y revienta con 429 por peticiones
    que no hizo: un fallo que no tiene nada que ver con lo que se estaba probando
    y que ademas aparece y desaparece segun el orden en que corran los tests.

    El throttle queda **activo** durante los tests, no desactivado: es la misma
    configuracion que produccion, y asi un 429 inesperado se descubre aqui y no
    en el checkout de un cliente.
    """

    def _pre_setup(self):
        super()._pre_setup()
        cache.clear()


# La flota real del negocio: 8 pangas de hasta 3 personas y 2 de hasta 5.
FLOTA_REAL = [(8, 3), (2, 5)]


def crear_flota(empresa, composicion=FLOTA_REAL):
    """Da de alta la flota de `empresa` en la base de pruebas. Idempotente.

    Hace falta en cualquier test que cree una reserva: desde que el cupo es
    consciente del tamano del grupo, sin pangas en la base no cabe nadie y la
    validacion rechaza todo. Es el mismo fallo seguro que en produccion — solo que
    ahi la flota se captura una vez y aqui hay que sembrarla.

    `empresa` es obligatorio (antes no existia): sin filtrar por ella, en sqlite
    (sin RLS) la flota de una Empresa cuenta como capacidad de otra.
    """
    existentes = Embarcacion.objects.filter(empresa=empresa)
    if existentes.exists():
        return list(existentes)

    pangas = []
    for cuantas, capacidad in composicion:
        clase = Embarcacion.Clase.CHICA if capacidad <= 3 else Embarcacion.Clase.GRANDE
        for i in range(cuantas):
            pangas.append(Embarcacion(
                empresa=empresa, nombre=f'Panga {capacidad}-{i + 1}',
                clase=clase, capacidad_maxima=capacidad,
            ))
    return Embarcacion.objects.bulk_create(pangas)
