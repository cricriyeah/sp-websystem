"""Los paquetes de La Ventana dicen cuántas salidas al mar llevan, no «del día 2 al N» (cliente, 2026-11-13).

«Seafari diario de orcas y fauna marina, del día 2 al 5» pasa a «4 salidas al mar para ver ballenas» (5 noches) y
«... del día 2 al 7» a «6 salidas al mar para ver ballenas» (7 noches), con las palabras que pidió el cliente. La
descripción cambia igual: «del día 2 al N, sales cada día de seafari» pasa a «sales K días al mar de seafari».

Como la 0056, no pisa lo que alguien ya editó en el admin: el renglón y el fragmento solo se cambian si siguen con el
texto que dejó la 0056.
"""
from django.db import migrations

# slug -> (noches, salidas al mar)
PAQUETES = {'paquete-5-noches': (5, 4), 'paquete-7-noches': (7, 6)}


def _cambios(noches, salidas):
    return dict(
        incluye={
            'es': (f'Seafari diario de orcas y fauna marina, del día 2 al {noches}',
                   f'{salidas} salidas al mar para ver ballenas'),
            'en': (f'Daily orca and marine life seafari, from day 2 to day {noches}',
                   f'{salidas} sea trips to see whales'),
        },
        descripcion=(f'y, del día 2 al {noches}, sales cada día de seafari:',
                     f'y sales {salidas} días al mar de seafari:'),
        descripcion_en=(f'and, from day 2 to day {noches}, head out every day on a seafari:',
                        f'and head out to sea on {salidas} seafari trips:'),
    )


def cargar(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Paquete = apps.get_model('fleet', 'Paquete')
    with alcance_operador_migracion(schema_editor.connection):
        for slug, (noches, salidas) in PAQUETES.items():
            cambios = _cambios(noches, salidas)
            for paquete in Paquete.objects.filter(sede__slug='la-ventana', slug=slug):
                campos = []
                for campo in ('descripcion', 'descripcion_en'):
                    viejo, nuevo = cambios[campo]
                    texto = getattr(paquete, campo) or ''
                    if viejo in texto:
                        setattr(paquete, campo, texto.replace(viejo, nuevo))
                        campos.append(campo)
                lista = paquete.incluye or {}
                nueva = {
                    idioma: [cambios['incluye'][idioma][1] if r == cambios['incluye'][idioma][0] else r for r in renglones]
                    if idioma in cambios['incluye'] and isinstance(renglones, list) else renglones
                    for idioma, renglones in lista.items()
                }
                if nueva != lista:
                    paquete.incluye = nueva
                    campos.append('incluye')
                if campos:
                    paquete.save(update_fields=campos)


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0058_piratas_ballena_gris'),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
