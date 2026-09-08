"""Siembra el catalogo inicial de extras del checkout (brunch, licencia,
carnada, transporte por zona, puntos de encuentro) para una Empresa dada.
Idempotente: correr de nuevo no duplica filas, solo crea las que falten.

No es una migracion de datos a proposito: una migracion queda en la cadena
que corre `manage.py test` para construir la base de pruebas, y sus efectos
no se revierten por test (solo lo que pasa DENTRO de cada test se revierte) —
asi que cualquier prueba en cualquier app que cuente filas de ExtrasItem
quedaria contaminada para siempre por el sembrado. Un comando corre una vez
por Empresa en produccion, a mano, y la base de pruebas nunca lo ve.

El precio del brunch NO se copia de `Tarifa.precio_lunch`: ese campo se retira
en la misma pieza que agrega este comando (ver
docs/superpowers/specs/2026-08-28-extras-checkout-design.md), asi que para
cuando este comando existe en el codigo ya no hay de donde copiarlo. Queda
como placeholder, igual que licencia y carnada — el usuario pone el precio
real en el admin la primera vez.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.fleet.models import ExtrasItem, PuntoEncuentro
from apps.tenancy import scope
from apps.tenancy.models import Empresa

# Precios reales que dio el usuario (28 de agosto de 2026). Brunch, licencia y carnada
# quedan como placeholder — el usuario los edita en el admin cuando tenga los precios
# reales (el de brunch era el que ya vivia en Tarifa.precio_lunch).
PLACEHOLDER_BRUNCH = Decimal('300.00')
PLACEHOLDER_LICENCIA = Decimal('450.00')
PLACEHOLDER_CARNADA = Decimal('200.00')


class Command(BaseCommand):
    help = 'Siembra el catalogo inicial de extras del checkout para una Empresa (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa', required=True,
            help='Slug de la Empresa a sembrar (apps.tenancy.models.Empresa.slug).',
        )

    def handle(self, *args, **options):
        try:
            empresa = Empresa.objects.get(slug=options['empresa'])
        except Empresa.DoesNotExist:
            raise CommandError(f"No existe una Empresa con slug '{options['empresa']}'.")

        creados = 0
        with scope.con_empresa(empresa):
            _, nuevo = ExtrasItem.objects.get_or_create(
                tipo='brunch', nombre='Paquete de Brunch', empresa=empresa,
                defaults={
                    'descripcion': 'Desayuno y comida. El menu varia cada semana. Incluye '
                                   'bebidas (agua y refrescos) y snacks para el viaje.',
                    'precio': PLACEHOLDER_BRUNCH, 'precio_usd': None,
                    'cobrar_por_persona': True, 'preseleccionado': False, 'activo': True,
                },
            )
            creados += nuevo

            _, nuevo = ExtrasItem.objects.get_or_create(
                tipo='licencia', nombre='Licencia de pesca', empresa=empresa,
                defaults={
                    'precio': PLACEHOLDER_LICENCIA, 'precio_usd': None,
                    'cobrar_por_persona': True, 'preseleccionado': True, 'activo': True,
                    # Alguien del grupo puede ya traer su licencia tramitada aparte
                    # (se tramita por dia/semana/mes/año) — el checkout deja elegir
                    # a cuantos se las tramita el negocio, no forzar a todo el grupo.
                    'cantidad_editable': True,
                },
            )
            creados += nuevo

            _, nuevo = ExtrasItem.objects.get_or_create(
                tipo='carnada', nombre='Carnada', empresa=empresa,
                defaults={
                    'precio': PLACEHOLDER_CARNADA, 'precio_usd': None,
                    'cobrar_por_persona': False, 'preseleccionado': True, 'activo': True,
                },
            )
            creados += nuevo

            _, nuevo = PuntoEncuentro.objects.get_or_create(
                nombre='Marina La Costa', empresa=empresa, defaults={'zona': 'centro', 'activo': True},
            )
            creados += nuevo

        self.stdout.write(self.style.SUCCESS(
            f"Catalogo de '{empresa.slug}' listo ({creados} filas nuevas)."
        ))
