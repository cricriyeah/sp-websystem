"""Cifra (o vuelve a cifrar con la clave nueva) las llaves de Stripe guardadas en `tenancy_empresa`.

Se corre una vez, DESPUES de poner `STRIPE_KEYS_ENCRYPTION_KEY` en Render; y otra vez al rotar la clave
(anteponer la nueva a la lista, correr esto, retirar la vieja). Es idempotente: lo ya cifrado con la
clave vigente solo se vuelve a escribir con un nuevo vector de inicializacion.

    python manage.py cifrar_llaves_stripe --dry-run   # dice cuantas llaves cifraria, sin tocar nada
    python manage.py cifrar_llaves_stripe
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.tenancy.campos import PREFIJO, Ilegible, claves_de_cifrado, clave_valida
from apps.tenancy.models import Empresa

CAMPOS = ('stripe_secret_key', 'stripe_webhook_secret')


class Command(BaseCommand):
    help = 'Cifra las llaves de Stripe de cada Empresa con STRIPE_KEYS_ENCRYPTION_KEY.'
    # Es el comando que ARREGLA lo que el chequeo payments.E003 marca (una sk_live_ en texto plano):
    # si los chequeos corrieran antes, el propio comando se negaria a correr.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo cuenta, sin escribir.')

    def handle(self, *args, **options):
        claves = claves_de_cifrado()
        if not claves:
            raise CommandError('STRIPE_KEYS_ENCRYPTION_KEY no esta definida: no hay con que cifrar.')
        if not all(clave_valida(clave) for clave in claves):
            raise CommandError('STRIPE_KEYS_ENCRYPTION_KEY tiene una clave que no es una clave Fernet valida.')

        tabla = Empresa._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT id, slug, stripe_secret_key, stripe_webhook_secret FROM {tabla}')
            filas = cursor.fetchall()

        a_cifrar = 0
        for pk, slug, secreta, webhook in filas:
            en_texto = [campo for campo, valor in zip(CAMPOS, (secreta, webhook)) if valor and not valor.startswith(PREFIJO)]
            if en_texto:
                a_cifrar += len(en_texto)
                self.stdout.write(f'Empresa {slug}: en texto plano {", ".join(en_texto)}.')
            if options['dry_run']:
                continue
            empresa = Empresa.objects.get(pk=pk)
            if any(isinstance(getattr(empresa, campo), Ilegible) for campo in CAMPOS):
                raise CommandError(
                    f'Empresa {slug}: un valor guardado no se pudo descifrar con las claves actuales. '
                    'No se escribio nada para no perderlo; revisa STRIPE_KEYS_ENCRYPTION_KEY.'
                )
            if not (empresa.stripe_secret_key or empresa.stripe_webhook_secret):
                continue
            empresa.save(update_fields=list(CAMPOS))

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'{a_cifrar} valor(es) en texto plano. No se escribio nada (--dry-run).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Listo: {len(filas)} empresa(s) revisadas, {a_cifrar} valor(es) cifrados.'))
