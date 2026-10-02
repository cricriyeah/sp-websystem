"""Siembra personalizaciones de pesca por Empresa sin modificar precios capturados."""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.fleet.models import Personalizacion, PuntoEncuentro, Servicio, ServicioPersonalizacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa

PLACEHOLDER_BRUNCH = Decimal('300.00')
PLACEHOLDER_LICENCIA = Decimal('450.00')
PLACEHOLDER_CARNADA = Decimal('200.00')


class Command(BaseCommand):
    help = 'Siembra las personalizaciones iniciales de pesca para una Empresa (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', required=True, help='Slug de la Empresa a sembrar.')

    def handle(self, *args, **options):
        try:
            empresa = Empresa.objects.get(slug=options['empresa'])
        except Empresa.DoesNotExist:
            raise CommandError(f"No existe una Empresa con slug '{options['empresa']}'.")

        creados = 0
        with scope.con_empresa(empresa), transaction.atomic():
            # Solo se necesita la PK, incluso con un esquema anterior a los campos nuevos.
            servicio = Servicio.objects.filter(
                empresa=empresa, slug='pesca-deportiva', tipo_servicio='pesca',
            ).only('id').first()
            if servicio is None:
                raise CommandError(f"Falta pesca-deportiva en empresa '{empresa.slug}'.")
            semillas = [
                ('Paquete de Brunch', 'brunch', True, False, False, False, PLACEHOLDER_BRUNCH),
                ('Licencia de pesca', 'licencia', True, True, True, True, PLACEHOLDER_LICENCIA),
                ('Carnada', 'carnada', False, False, False, True, PLACEHOLDER_CARNADA),
            ]
            for nombre, tipo, por_persona, editable, reforzado, recomendada, precio in semillas:
                p, nuevo = Personalizacion.objects.get_or_create(
                    empresa=empresa, nombre=nombre,
                    defaults=dict(tipo=tipo, tipo_interaccion='check', cobrar_por_persona=por_persona,
                                  cantidad_editable=editable, aviso_reforzado=reforzado, activo=True),
                )
                creados += nuevo
                _, nuevo = ServicioPersonalizacion.objects.get_or_create(
                    servicio=servicio, personalizacion=p,
                    defaults=dict(precio=precio, obligatorio=False,
                                  preseleccionado=recomendada, activo=True),
                )
                creados += nuevo
            _, nuevo = PuntoEncuentro.objects.get_or_create(
                nombre='Marina La Costa', empresa=empresa, defaults={'zona': 'centro', 'activo': True},
            )
            creados += nuevo
        self.stdout.write(self.style.SUCCESS(
            f"Catalogo de '{empresa.slug}' listo ({creados} filas nuevas)."
        ))
