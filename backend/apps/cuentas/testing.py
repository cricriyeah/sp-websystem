"""Utilidades compartidas por las pruebas de la recuperacion de contrasena."""
import uuid

from django.contrib.auth import get_user_model
from django.test import override_settings

User = get_user_model()

# Hash rapido: PBKDF2 tarda cientos de milisegundos por usuario y estas pruebas crean decenas.
HASH_RAPIDO = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])

PASSWORD_VIEJA = 'Clave-Vieja-9x7!'
PASSWORD_NUEVA = 'Clave-Nueva-4q2#mar'


def sufijo():
    """Identificador unico por llamada: ninguna prueba reusa un usuario o correo literal de otra."""
    return uuid.uuid4().hex[:10]


def crear_usuario(correo=True, password=PASSWORD_VIEJA, **extra):
    """Cuenta de backoffice de prueba. `correo=True` genera uno unico; `False` o '' la deja sin correo."""
    nombre = extra.pop('username', f'cta-{sufijo()}')
    if correo is True:
        correo = f'{nombre}@example.com'
    extra.setdefault('is_staff', True)
    if password is None:
        usuario = User(username=nombre, email=correo or '', **extra)
        usuario.set_unusable_password()
        usuario.save()
        return usuario
    return User.objects.create_user(nombre, email=correo or '', password=password, **extra)
