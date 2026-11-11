"""La Ventana vende un seafari de orcas y fauna marina, no un «avistamiento de ballenas y orcas» (dueño, 2026-11-11).

Las orcas visitan la zona todo el año; desde abril llegan ballenas jorobadas y mobulas. El nado se ofrece solo con
orcas: con ballenas lo prohíbe la NOM-131-SEMARNAT-2010, así que los textos ya no prometen «nadar con ballenas».
Cambia el nombre, la descripción y la lista de «incluye» del servicio y de los paquetes de 5 y 7 noches.

Como la 0053 y la 0055, no pisa lo que alguien ya editó en el admin: cada campo solo se reemplaza si sigue siendo
uno de los textos que dejaron el seed o las migraciones anteriores, y en las listas solo se cambia el renglón viejo.
Corre con `alcance_operador_migracion` porque bajo RLS, sin alcance, no se ve ninguna fila.
"""
from django.db import migrations

SERVICIO = ('la-ventana-travel', 'avistamiento-ballenas-orcas')

SERVICIO_TEXTOS = dict(
    nombre=({'Avistamiento de ballenas y orcas'}, 'Seafari: orcas y fauna marina'),
    nombre_en=({'Whale and orca watching'}, 'Seafari: orcas and marine life'),
    descripcion=(
        {
            # 0055
            'Sales al mar en lancha compartida a buscar ballenas y orcas. Si aparecen y el mar lo permite, se intenta '
            'nadar con ellas; después hay snorkel en un arrecife. Lo que se ve depende de la temporada y del mar. ¿Van en '
            'grupo? La lancha privada para hasta 10 personas cuesta $20,000 MXN: pídela por WhatsApp.',
            # seed_catalogo_real
            'Salida diaria al mar para buscar ballenas y orcas e intentar nadar con ellas, con snorkel en un arrecife. '
            'Precio por persona en lancha compartida; para un grupo privado (hasta 10 personas) el costo es de $20,000 '
            'MXN: consúltalo por WhatsApp.',
        },
        'Sales al mar en lancha compartida a buscar orcas, que visitan esta zona todo el año, y lo que el mar traiga '
        'ese día: delfines y lobos marinos casi siempre y, desde abril, ballenas jorobadas y mobulas. Si aparecen orcas '
        'y el mar lo permite, puedes meterte al agua con ellas; después hay snorkel en un arrecife. Lo que se ve depende '
        'del mar. ¿Van en grupo? La lancha privada para hasta 10 personas cuesta $20,000 MXN: pídela por WhatsApp.',
    ),
    descripcion_en=(
        {
            'Head out to sea on a shared boat to look for whales and orcas. If they show up and the sea allows, you try '
            'to swim alongside them; then you snorkel a reef. What you see depends on the season and the sea. Coming as '
            'a group? A private boat for up to 10 people is $20,000 MXN: ask for it on WhatsApp.',
        },
        'Head out to sea on a shared boat to look for orcas, which visit the area all year round, and whatever the sea '
        'brings that day: dolphins and sea lions most days and, from April, humpback whales and mobula rays. If orcas '
        'show up and the sea allows, you can get in the water with them; then you snorkel a reef. What you see depends '
        'on the sea. Coming as a group? A private boat for up to 10 people is $20,000 MXN: ask for it on WhatsApp.',
    ),
)
SERVICIO_INCLUYE = {
    'es': ('Intento de nado con ballenas u orcas, si el mar lo permite', 'Nado con orcas, si aparecen y el mar lo permite'),
    'en': ('A try at swimming with whales or orcas, sea permitting', 'Swimming with orcas, if they show up and the sea allows'),
}


def _paquete(noches, palabra_es, palabra_en):
    comun_es = (f'{palabra_es} noches en La Ventana con todo resuelto: te recogen en el aeropuerto, duermes en el Hotel '
                f'Casa Arrecife y, del día 2 al {noches}, ')
    cierre_es = (', con comida ligera, botanas, bebidas y equipo de snorkel a bordo. Al final te llevan de vuelta al '
                 'aeropuerto. Las comidas en tierra corren por tu cuenta: hay restaurantes a menos de 1 km del hotel.')
    comun_en = (f'{palabra_en} nights in La Ventana, all arranged: you are picked up at the airport, stay at Hotel Casa '
                f'Arrecife and, from day 2 to day {noches}, ')
    cierre_en = (', with a light meal, snacks, drinks and snorkel gear on board. At the end, you are driven back to the '
                 'airport. Meals on land are on you: there are restaurants less than 1 km from the hotel.')
    return dict(
        textos=dict(
            nombre=({f'Paquete {noches} noches'}, f'Seafari {noches} noches'),
            nombre_en=({f'{noches}-night package'}, f'{noches}-night Seafari'),
            descripcion=(
                {
                    comun_es + 'sales cada día al mar a buscar ballenas y orcas' + cierre_es,  # 0053
                    f'{noches} noches de hospedaje, traslado redondo de aeropuerto y '
                    f'avistamiento de ballenas y orcas del día 2 al {noches}.',  # seed
                },
                comun_es + 'sales cada día de seafari: orcas, delfines, lobos marinos y, desde abril, ballenas '
                           'jorobadas y mobulas' + cierre_es,
            ),
            descripcion_en=(
                {comun_en + 'head out to sea every day to look for whales and orcas' + cierre_en},
                comun_en + 'head out every day on a seafari: orcas, dolphins, sea lions and, from April, humpback '
                           'whales and mobula rays' + cierre_en,
            ),
        ),
        incluye={
            'es': (f'Salidas al mar para ver ballenas y orcas, del día 2 al {noches}',
                   f'Seafari diario de orcas y fauna marina, del día 2 al {noches}'),
            'en': (f'Sea trips to see whales and orcas, from day 2 to day {noches}',
                   f'Daily orca and marine life seafari, from day 2 to day {noches}'),
        },
    )


PAQUETES = {
    ('la-ventana', 'paquete-5-noches'): _paquete(5, 'Cinco', 'Five'),
    ('la-ventana', 'paquete-7-noches'): _paquete(7, 'Siete', 'Seven'),
}


def _aplicar(objeto, textos, incluye):
    cambios = []
    for campo, (viejos, nuevo) in textos.items():
        if getattr(objeto, campo) in viejos:
            setattr(objeto, campo, nuevo)
            cambios.append(campo)
    lista = objeto.incluye or {}
    nueva = {idioma: [incluye[idioma][1] if r == incluye[idioma][0] else r for r in renglones]
             if idioma in incluye and isinstance(renglones, list) else renglones
             for idioma, renglones in lista.items()}
    if nueva != lista:
        objeto.incluye = nueva
        cambios.append('incluye')
    if cambios:
        objeto.save(update_fields=cambios)


def cargar(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Servicio = apps.get_model('fleet', 'Servicio')
    Paquete = apps.get_model('fleet', 'Paquete')
    with alcance_operador_migracion(schema_editor.connection):
        empresa, slug = SERVICIO
        for servicio in Servicio.objects.filter(empresa__slug=empresa, slug=slug):
            _aplicar(servicio, SERVICIO_TEXTOS, SERVICIO_INCLUYE)
        for (sede, slug), datos in PAQUETES.items():
            for paquete in Paquete.objects.filter(sede__slug=sede, slug=slug):
                _aplicar(paquete, datos['textos'], datos['incluye'])


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0055_ficha_y_listas_limpias'),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
