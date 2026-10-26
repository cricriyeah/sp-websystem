"""Lista las cuentas del backoffice con el estado de su correo (el unico dato que permite recuperar la contrasena).

Solo lee. Imprime el correo enmascarado (`a***@dominio`) para que la salida pueda pegarse en un chat o un ticket
sin regalar direcciones. Correrlo en el Shell de Render despues de cargar los correos:

    python manage.py auditar_correos_cuentas
"""
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


def enmascarar(correo):
    local, _, dominio = correo.partition('@')
    return f'{local[:1]}***@{dominio}'


class Command(BaseCommand):
    help = 'Lista las cuentas con el estado de su correo: con correo, sin correo o repetido. No modifica nada.'

    def handle(self, *args, **opciones):
        cuentas = list(User.objects.order_by('username'))
        repeticiones = Counter(c.email.strip().lower() for c in cuentas if c.email.strip())

        sin_correo = repetidas = 0
        for cuenta in cuentas:
            correo = cuenta.email.strip().lower()
            if not correo:
                estado, visible = 'SIN CORREO', '-'
                sin_correo += 1
            elif repeticiones[correo] > 1:
                estado, visible = 'DUPLICADO', enmascarar(correo)
                repetidas += 1
            else:
                estado, visible = 'OK', enmascarar(correo)
            self.stdout.write(
                f'{cuenta.get_username():<24} superusuario={"si" if cuenta.is_superuser else "no"} '
                f'activa={"si" if cuenta.is_active else "no"} correo={visible} {estado}'
            )

        self.stdout.write(
            f'Total: {len(cuentas)} cuentas, {sin_correo} sin correo, {repetidas} con correo repetido.'
        )
