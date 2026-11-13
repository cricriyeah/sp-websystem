"""Puerto Chale ve ballena gris de enero a marzo y ballena jorobada a finales de año (dueño, 2026-11-13).

La 0057 dejó el servicio de Piratas Adventures como «Avistamiento de ballena jorobada». Ahora se llama
«Avistamiento de ballenas» y la descripción nombra a las dos especies. Como la 0057, no pisa lo que alguien ya editó
en el admin: cada campo solo cambia si sigue con el texto que dejó la 0057.
"""
from django.db import migrations

EMPRESA = 'piratas-adventures'
SLUG = 'avistamiento-ballenas'

# campo: (texto que dejó la 0057, texto nuevo)
CAMBIOS = {
    'nombre': ('Avistamiento de ballena jorobada', 'Avistamiento de ballenas'),
    'nombre_en': ('Humpback whale watching', 'Whale watching'),
    'descripcion': (
        'Dos horas en la bahía para ver a la ballena jorobada, que llega cada invierno a tener a sus crías. El precio '
        'cubre de 1 a 6 personas y caben hasta 2 más por un cargo por persona. Si quieres más tiempo, hay recorridos '
        'de 3 y 4 horas: pídelos por WhatsApp.',
        'Dos horas en Bahía Magdalena para ver ballenas. De enero a marzo, la ballena gris llega a tener a sus crías; '
        'a finales de año pasa la ballena jorobada. El precio cubre de 1 a 6 personas y caben hasta 2 más por un '
        'cargo por persona. Si quieres más tiempo, hay recorridos de 3 y 4 horas: pídelos por WhatsApp.',
    ),
    'descripcion_en': (
        'Two hours on the bay to see the humpback whales, which come every winter to give birth. The price covers 1 to '
        '6 people, with room for 2 more at a per-person charge. If you want more time, there are 3- and 4-hour '
        'trips: ask for them on WhatsApp.',
        'Two hours on Magdalena Bay to see whales. From January to March, the gray whales come to give birth; late in '
        'the year, humpback whales pass through. The price covers 1 to 6 people, with room for 2 more at a per-person '
        'charge. If you want more time, there are 3- and 4-hour trips: ask for them on WhatsApp.',
    ),
}


def cargar(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Servicio = apps.get_model('fleet', 'Servicio')
    with alcance_operador_migracion(schema_editor.connection):
        servicio = Servicio.objects.filter(empresa__slug=EMPRESA, slug=SLUG).first()
        if servicio is None:
            return
        campos = []
        for campo, (anterior, nuevo) in CAMBIOS.items():
            if getattr(servicio, campo) == anterior:
                setattr(servicio, campo, nuevo)
                campos.append(campo)
        if campos:
            servicio.save(update_fields=campos)


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0057_puerto_chale_precios_reales'),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
