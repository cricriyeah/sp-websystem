# backend/apps/tenancy/usuarios.py
from contextlib import nullcontext

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.core.management import call_command
from django.db import connection, transaction

from apps.bookings.models import Vendedora
from . import scope
from .models import MembresiaEmpresa

User = get_user_model()


def crear_usuario_con_rol(username, password, nombre, rol, empresa, codigo_vendedora=None):
    """Crea en una sola transacción:
    1. User (is_staff=True, is_active=True, first_name=nombre).
    2. Agrega al grupo Django que corresponde al rol ('Jefe' o 'Vendedora').
    3. Crea MembresiaEmpresa(rol=JEFE|VENDEDORA, empresa).
    4. Si el rol es Vendedora, crea bookings.Vendedora con su código.

    Si los grupos no existen, los crea llamando a setup_roles.
    Valida: usuario repetido, contraseña con los validadores de Django,
    código de vendedora único por empresa y rol válido.
    Respeta RLS operando dentro del alcance adecuado.
    """
    errores = {}

    if not empresa:
        errores['empresa'] = 'La empresa es obligatoria.'

    # 1. Normalización y validación de rol
    rol_str = str(rol).strip() if rol is not None else ''
    if rol == MembresiaEmpresa.Rol.JEFE or rol_str.upper() == 'JEFE':
        rol_enum = MembresiaEmpresa.Rol.JEFE
        nombre_grupo = 'Jefe'
    elif rol == MembresiaEmpresa.Rol.VENDEDORA or rol_str.upper() == 'VENDEDORA':
        rol_enum = MembresiaEmpresa.Rol.VENDEDORA
        nombre_grupo = 'Vendedora'
    else:
        errores['rol'] = f'El rol "{rol}" no es válido. Debe ser Jefe o Vendedora.'
        rol_enum = None
        nombre_grupo = None

    # 2. Validación de nombre de usuario
    username_limpio = (username or '').strip()
    if not username_limpio:
        errores['username'] = 'El nombre de usuario es obligatorio.'
    elif User.objects.filter(username=username_limpio).exists():
        errores['username'] = 'Ya existe una cuenta con ese nombre de usuario.'

    # 3. Validación de contraseña
    if not password:
        errores['password'] = 'La contraseña es obligatoria.'
    else:
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            errores['password'] = exc.messages

    # 4. Validación de código de vendedora
    if rol_enum == MembresiaEmpresa.Rol.VENDEDORA:
        codigo_limpio = (codigo_vendedora or '').strip()
        if not codigo_limpio:
            errores['codigo_vendedora'] = 'El código de vendedora es obligatorio.'
        elif empresa:
            actual = getattr(connection, 'alcance_actual', None)
            if actual is None:
                with scope.con_empresa(empresa):
                    if Vendedora.objects.filter(empresa=empresa, codigo=codigo_limpio).exists():
                        errores['codigo_vendedora'] = 'Ya existe una vendedora con ese código en esta empresa.'
            else:
                if Vendedora.objects.filter(empresa=empresa, codigo=codigo_limpio).exists():
                    errores['codigo_vendedora'] = 'Ya existe una vendedora con ese código en esta empresa.'
    else:
        codigo_limpio = None

    if errores:
        raise DjangoValidationError(errores)

    # 5. Asegurar existencia de grupos Django
    if not Group.objects.filter(name=nombre_grupo).exists():
        call_command('setup_roles', verbosity=0)

    # 6. Manejo de alcance RLS y ejecución atómica
    actual = getattr(connection, 'alcance_actual', None)
    if actual == ('operador',) or actual == ('empresa', empresa.id):
        alcance_cm = nullcontext()
    elif actual is None:
        alcance_cm = scope.con_empresa(empresa)
    else:
        raise PermissionDenied('No se puede crear un usuario fuera del alcance de la empresa actual.')

    with transaction.atomic(), alcance_cm:
        grupo = Group.objects.get(name=nombre_grupo)
        nuevo_user = User.objects.create_user(
            username=username_limpio,
            password=password,
            first_name=nombre or '',
            is_staff=True,
            is_active=True,
        )
        nuevo_user.groups.add(grupo)
        MembresiaEmpresa.objects.create(
            user=nuevo_user,
            empresa=empresa,
            rol=rol_enum,
        )
        if rol_enum == MembresiaEmpresa.Rol.VENDEDORA:
            Vendedora.objects.create(
                usuario=nuevo_user,
                empresa=empresa,
                codigo=codigo_limpio,
            )

    return nuevo_user
