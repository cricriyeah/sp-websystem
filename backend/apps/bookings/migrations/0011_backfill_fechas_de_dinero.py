"""Rellena las fechas del dinero en las reservas que ya existian.

El panel de finanzas agrupa por `pagada_en` y `reembolsada_en`, campos que nacen
con esta tanda de migraciones. Sin este relleno, todo lo cobrado antes de hoy
quedaria fuera del historico: no es que valga cero, es que no tendria fecha con
la cual contarlo.

`actualizado_en` es la mejor aproximacion disponible (`creado_en` es cuando el
cliente abrio el checkout, no cuando pago). De aqui en adelante las fechas son
exactas: las sella el webhook con el timestamp de Stripe.
"""
from django.db import migrations, models


def rellenar(apps, schema_editor):
    Reserva = apps.get_model('bookings', 'Reserva')

    Reserva.objects.filter(monto_pagado__isnull=False, pagada_en__isnull=True).update(
        pagada_en=models.F('actualizado_en')
    )

    # Una reserva ya marcada como reembolsada devolvio lo que se habia cobrado:
    # el sistema solo hace reembolsos completos. Si alguna quedo marcada sin que
    # el dinero llegara a salir de Stripe, se corrige a mano desde el admin.
    Reserva.objects.filter(
        reembolsada=True, monto_pagado__isnull=False, monto_reembolsado__isnull=True
    ).update(monto_reembolsado=models.F('monto_pagado'), reembolsada_en=models.F('actualizado_en'))


def revertir(apps, schema_editor):
    """No hay nada que deshacer: los campos se van con la migracion de esquema."""


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0010_reserva_monto_reembolsado_reserva_pagada_en_and_more'),
    ]

    operations = [
        migrations.RunPython(rellenar, revertir),
    ]
