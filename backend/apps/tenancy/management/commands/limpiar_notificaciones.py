"""Borra las notificaciones del backoffice de hace mas de N dias (90 por defecto).

Las `LecturaNotificacion` caen en cascada con su notificacion. Para un cron diario en Render:

    python manage.py limpiar_notificaciones --dias 90

El command corre con el rol de la app (sin BYPASSRLS) y SIN alcance de empresa: sin `como_operador_plataforma()` la
politica RLS le deja ver cero filas y el `DELETE` no borraria nada, en silencio. Se usa el alcance de operador (y no un
recorrido por las empresas activas) para incluir tambien a las empresas pausadas: si no, sus notificaciones crecerian
sin fin. `EventoRecuperacion` no tiene este problema porque esta fuera de RLS; esta tabla no.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.tenancy import scope
from apps.tenancy.models import Notificacion


class Command(BaseCommand):
    help = 'Borra las notificaciones del backoffice mas viejas que --dias (por defecto 90).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=90)

    def handle(self, *args, dias, **opciones):
        if dias < 1:
            # Con 0 o negativo el corte caeria en el futuro y se borraria TODO el feed.
            raise CommandError('--dias debe ser al menos 1.')
        corte = timezone.now() - timedelta(days=dias)
        with scope.como_operador_plataforma():
            _, por_modelo = Notificacion.objects.filter(creado_en__lt=corte).delete()
        borradas = por_modelo.get(Notificacion._meta.label, 0)
        self.stdout.write(f'Se borraron {borradas} notificacion(es) de hace mas de {dias} dias.')
