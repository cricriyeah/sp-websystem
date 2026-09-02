# backend/apps/tenancy/scope.py
from contextlib import contextmanager

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.http import Http404

NOMBRE_GRUPO_OPERADOR_PLATAFORMA = 'OperadorPlataforma'


@contextmanager
def _con_alcance(valor, sql):
    """Primitivo compartido. `valor` es una tupla hashable/comparable que
    identifica el alcance: ('empresa', id) o ('operador',). No reentrante con
    un valor distinto (RuntimeError); no-op idempotente con el mismo valor.

    El `finally` que restaura `connection.alcance_actual` vive DENTRO del
    `with transaction.atomic()` (Revision 6, N-E) -- Django ejecuta los
    callbacks de `transaction.on_commit(...)` dentro del `finally` de
    `Atomic.__exit__`, en el momento del COMMIT real. Si la restauracion
    ocurriera fuera del `atomic()`, un callback que reabre `con_empresa` con
    la misma Empresa encontraria la bandera todavia puesta, tomaria la rama
    no-op, y no emitiria `SET LOCAL` en la transaccion nueva del callback --
    bajo RLS eso es cero filas en silencio (el bug N1 original).
    """
    actual = getattr(connection, 'alcance_actual', None)
    ya_puesto = actual == valor
    if actual is not None and not ya_puesto:
        raise RuntimeError(
            f'Ya hay un alcance de tenancy activo ({actual!r}); no se puede '
            f'entrar a {valor!r} sin salir primero.'
        )

    with transaction.atomic():
        if not ya_puesto:
            connection.alcance_actual = valor
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute(sql)
        try:
            yield
        finally:
            if not ya_puesto:
                connection.alcance_actual = actual


@contextmanager
def con_empresa(empresa):
    """`empresa`: instancia de `Empresa`, no un id."""
    # SET LOCAL no soporta parametros ligados de forma confiable entre drivers
    # -- se castea a int explicito (revienta con ValueError si no es un id
    # valido) y se interpola: seguro porque nunca viene de input de usuario.
    with _con_alcance(
        ('empresa', empresa.id),
        f'SET LOCAL app.current_empresa_id = {int(empresa.id)}',
    ):
        yield


@contextmanager
def como_operador_plataforma():
    with _con_alcance(('operador',), "SET LOCAL app.operador_plataforma = 'on'"):
        yield


def resolver_membresia_o_403(user):
    """Devuelve un context manager (`con_empresa(...)` o
    `como_operador_plataforma()`). Un solo tipo de excepcion, un solo lugar:
    0 o >1 `MembresiaEmpresa` -> PermissionDenied. Mas de una membresia no
    ocurre en v1 (el dueno confirmo rol de jefe solo por Empresa) -- es
    guardia de sanidad, no flujo soportado."""
    if es_operador_plataforma(user):
        return como_operador_plataforma()

    from .models import MembresiaEmpresa

    membresias = list(MembresiaEmpresa.objects.filter(user=user).select_related('empresa'))
    if len(membresias) != 1:
        raise PermissionDenied('El usuario no pertenece a exactamente una Empresa.')
    return con_empresa(membresias[0].empresa)


def resolver_empresa_publica(slug):
    """Catalogo/checkout: 404 si el slug no existe O si activo=False -- es
    dinero por cobrar, una Empresa pausada no debe vender."""
    from .models import Empresa

    try:
        return Empresa.objects.get(slug=slug, activo=True)
    except Empresa.DoesNotExist:
        raise Http404('Empresa no encontrada.')


def resolver_empresa_de_dinero(slug):
    """Webhook/conciliacion: 404 SOLO si el slug no existe -- una Empresa
    pausada (disputa, corte comercial) sigue necesitando reconciliar dinero
    ya cobrado (Revision 4, N16)."""
    from .models import Empresa

    try:
        return Empresa.objects.get(slug=slug)
    except Empresa.DoesNotExist:
        raise Http404('Empresa no encontrada.')


def empresa_actual(request):
    """Lee el alcance ya resuelto por el middleware/vista -- no vuelve a
    consultar MembresiaEmpresa por su cuenta."""
    valor = getattr(connection, 'alcance_actual', None)
    if valor is None or valor[0] != 'empresa':
        return None
    from .models import Empresa

    return Empresa.objects.get(pk=valor[1])


def es_operador_plataforma(user):
    if user.is_anonymous:
        return False
    return user.groups.filter(name=NOMBRE_GRUPO_OPERADOR_PLATAFORMA).exists()
