"""Borra de la bitacora de recuperacion los eventos de hace mas de N dias (90 por defecto).

La bitacora (`EventoRecuperacion`) alimenta los limites de uso, que solo miran el ultimo dia: lo viejo ya
no sirve para nada y guarda IPs. Para un cron mensual en Render:

    python manage.py limpiar_eventos_recuperacion --dias 90
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.cuentas.models import EventoRecuperacion


class Command(BaseCommand):
    help = 'Borra los eventos de recuperacion de contrasena mas viejos que --dias (por defecto 90).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=90)

    def handle(self, *args, dias, **opciones):
        if dias < 1:
            # Con 0 o negativo el corte caeria en el futuro y se borraria TODA la bitacora.
            raise CommandError('--dias debe ser al menos 1.')
        corte = timezone.now() - timedelta(days=dias)
        borrados, _ = EventoRecuperacion.objects.filter(creado_en__lt=corte).delete()
        self.stdout.write(f'Se borraron {borrados} evento(s) de hace mas de {dias} dias.')
