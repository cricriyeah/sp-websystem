# backend/apps/tenancy/roles.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command

from .models import MembresiaEmpresa

GRUPO_POR_ROL = {
    MembresiaEmpresa.Rol.JEFE: 'Jefe',
    MembresiaEmpresa.Rol.VENDEDORA: 'Vendedora',
}


def asegurar_grupo(nombre):
    """Devuelve el Group con ese nombre; si no existe, corre setup_roles y lo devuelve."""
    try:
        return Group.objects.get(name=nombre)
    except Group.DoesNotExist:
        call_command('setup_roles', verbosity=0)
        return Group.objects.get(name=nombre)


def sincronizar_grupos_de_usuario(user):
    """Calcula el conjunto de roles que el usuario tiene en TODAS sus membresías;
    para cada rol presente asegura que está en su grupo; para cada rol ausente
    lo saca de su grupo (solo Jefe y Vendedora; jamás toca OperadorPlataforma ni
    otros grupos). Idempotente. Si el usuario no tiene pk o ya no existe, no hace nada.
    """
    if not user or not getattr(user, 'pk', None):
        return

    User = get_user_model()
    if not User.objects.filter(pk=user.pk).exists():
        return

    roles_presentes = set(
        MembresiaEmpresa.objects.filter(user_id=user.pk).values_list('rol', flat=True)
    )

    for rol, nombre_grupo in GRUPO_POR_ROL.items():
        if rol in roles_presentes:
            grupo = asegurar_grupo(nombre_grupo)
            user.groups.add(grupo)
        else:
            try:
                grupo = Group.objects.get(name=nombre_grupo)
                user.groups.remove(grupo)
            except Group.DoesNotExist:
                pass


def sincronizar_todos():
    """Recorre los usuarios con al menos una membresía y llama a sincronizar_grupos_de_usuario.
    Devuelve cuántos usuarios se sincronizaron.
    Solo sincroniza usuarios con membresías, para no quitar permisos por accidente
    a operadores o cuentas especiales.
    """
    User = get_user_model()
    usuarios = User.objects.filter(membresias__isnull=False).distinct()
    total = 0
    for u in usuarios:
        sincronizar_grupos_de_usuario(u)
        total += 1
    return total
