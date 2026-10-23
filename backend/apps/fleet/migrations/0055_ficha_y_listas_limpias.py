"""La ficha de la página de detalle (2026-10-22): duración y punto de salida de cada servicio, el nombre en inglés de
la licencia de pesca, y las listas de «incluye» y las descripciones sin la logística que ahora vive en la ficha
(horario, duración, cupo y reglas de precio).

Como la 0053, no pisa lo que alguien ya editó en el admin: cada lista y cada descripción solo se reemplaza si sigue
siendo exactamente la que dejaron el seed o la 0053, y los campos nuevos solo se llenan si están vacíos.
Corre con `alcance_operador_migracion` porque bajo RLS, sin alcance, no se ve ninguna fila.
"""
from django.db import migrations

# (empresa, slug) -> lista vieja y nueva, descripciones viejas (0053) y nuevas, ficha
SERVICIOS = {
    ('sal-y-sol', 'pesca-deportiva'): dict(
        incluye_viejo={
            'es': ['Desayuno ligero y comida a bordo', 'Aperitivos: fruta y frituras', 'Bebidas',
                   'Cubre 1 o 2 personas; desde la tercera se suma un cargo por persona'],
            'en': ['Light breakfast and lunch on board', 'Snacks: fruit and chips', 'Drinks',
                   'Covers 1 or 2 people; from the third on, a per-person charge applies'],
        },
        incluye={
            'es': ['Panga privada con capitán local', 'Desayuno ligero y comida a bordo',
                   'Aperitivos: fruta y frituras', 'Bebidas'],
            'en': ['Private panga with a local captain', 'Light breakfast and lunch on board',
                   'Snacks: fruit and chips', 'Drinks'],
        },
        es_viejo='La panga es solo para tu grupo: hasta 5 personas, con un capitán local que sale contigo entre las 5 y '
                 'las 7 de la mañana. Según la temporada, vas tras marlín, dorado o jurel. El desayuno ligero, la comida, '
                 'la fruta, las botanas y las bebidas van a bordo, así que tú solo te ocupas de pescar. La licencia de '
                 'pesca se tramita aparte, solo para quienes vayan a pescar.',
        en_viejo='The panga is yours alone: up to 5 people, with a local captain who heads out with you between 5 and '
                 '7 am. Depending on the season, you are after marlin, mahi-mahi or yellowtail. Light breakfast, lunch, '
                 'fruit, snacks and drinks are on board, so all you have to do is fish. Fishing licenses are arranged '
                 'separately, only for those who will be fishing.',
        es='La panga es solo para tu grupo, con un capitán local que sale contigo al amanecer. Según la temporada, vas '
           'tras marlín, dorado o jurel. La comida y las bebidas van a bordo, así que tú solo te ocupas de pescar. La '
           'licencia de pesca se tramita aparte, solo para quienes vayan a pescar.',
        en='The panga is yours alone, with a local captain who heads out with you at dawn. Depending on the season, you '
           'are after marlin, mahi-mahi or yellowtail. Food and drinks are on board, so all you have to do is fish. '
           'Fishing licenses are arranged separately, only for those who will be fishing.',
        ficha=dict(duracion='6–7 h', duracion_en='6–7 h', punto_salida='Marina La Costa',
                   punto_salida_en='Marina La Costa'),
    ),
    ('la-ventana-travel', 'pesca-con-mosca'): dict(
        incluye_viejo={
            'es': ['Un día de pesca con mosca', 'Salida de 7:00 a 8:00 am', 'Para 3 personas como máximo',
                   'Comida ligera, aperitivos y bebidas incluidos', 'Equipo para snorkelear'],
            'en': ['A full day of fly fishing', 'Departure from 7:00 to 8:00 am', 'For 3 people at most',
                   'Light meal, snacks and drinks included', 'Snorkeling gear'],
        },
        incluye={
            'es': ['Panga para ti y hasta dos acompañantes', 'Comida ligera, aperitivos y bebidas',
                   'Equipo para snorkelear'],
            'en': ['A panga for you and up to two companions', 'Light meal, snacks and drinks', 'Snorkeling gear'],
        },
        es_viejo='Un día completo de pesca con mosca en las aguas de La Ventana, para ti y hasta dos acompañantes: el '
                 'precio es el mismo si van uno, dos o tres. Sales entre las 7 y las 8 de la mañana, con comida ligera, '
                 'botanas y bebidas a bordo, y equipo de snorkel para cuando quieras meterte al agua. La licencia de pesca '
                 'no está incluida.',
        en_viejo='A full day of fly fishing in the waters off La Ventana, for you and up to two companions: the price is '
                 'the same whether one, two or three of you go. You head out between 7 and 8 am with a light meal, snacks '
                 'and drinks on board, plus snorkel gear for when you want to get in the water. Fishing licenses are not '
                 'included.',
        es='Un día completo de pesca con mosca en las aguas de La Ventana, para ti y hasta dos acompañantes: el precio '
           'es el mismo si van uno, dos o tres. Entre lance y lance hay comida a bordo, y equipo de snorkel para cuando '
           'quieras meterte al agua. La licencia de pesca no está incluida.',
        en='A full day of fly fishing in the waters off La Ventana, for you and up to two companions: the price is the '
           'same whether one, two or three of you go. Between casts there is food on board, plus snorkel gear for when '
           'you want to get in the water. Fishing licenses are not included.',
        ficha=dict(duracion='Día completo', duracion_en='Full day'),
    ),
    ('la-ventana-travel', 'avistamiento-ballenas-orcas'): dict(
        incluye_viejo={
            'es': ['Salida diaria, de 7:00 a 8:00 am, de La Ventana o Bahía de los Sueños',
                   'El tour dura de 5 a 6 horas aproximadamente', 'Algo de comer, aguas y refrescos',
                   'Equipo para snorkelear', 'Snorkel en un arrecife', 'Buscamos animales para intentar nadar con ellos'],
            'en': ['Daily departure, 7:00 to 8:00 am, from La Ventana or Bahía de los Sueños',
                   'The tour lasts about 5 to 6 hours', 'Some food, water and soft drinks', 'Snorkeling gear',
                   'Snorkeling at a reef', 'We look for animals to try to swim with them'],
        },
        incluye={
            'es': ['Algo de comer, aguas y refrescos', 'Equipo para snorkelear', 'Snorkel en un arrecife',
                   'Intento de nado con ballenas u orcas, si el mar lo permite'],
            'en': ['Some food, water and soft drinks', 'Snorkeling gear', 'Snorkeling at a reef',
                   'A try at swimming with whales or orcas, sea permitting'],
        },
        es_viejo='Sales al mar entre las 7 y las 8 de la mañana, desde La Ventana o Bahía de los Sueños, a buscar ballenas '
                 'y orcas. Si aparecen y el mar lo permite, se intenta nadar con ellas; después hay snorkel en un arrecife. '
                 'Son de 5 a 6 horas en lancha compartida, con algo de comer, aguas, refrescos y el equipo de snorkel. Lo '
                 'que se ve depende de la temporada y del mar. ¿Van en grupo? La lancha privada para hasta 10 personas '
                 'cuesta $20,000 MXN: pídela por WhatsApp.',
        en_viejo='Head out to sea between 7 and 8 am, from La Ventana or Bahía de los Sueños, to look for whales and '
                 'orcas. If they show up and the sea allows, you try to swim alongside them; then you snorkel a reef. It '
                 'is 5 to 6 hours on a shared boat, with something to eat, water, sodas and snorkel gear. What you see '
                 'depends on the season and the sea. Coming as a group? A private boat for up to 10 people is '
                 '$20,000 MXN: ask for it on WhatsApp.',
        es='Sales al mar en lancha compartida a buscar ballenas y orcas. Si aparecen y el mar lo permite, se intenta '
           'nadar con ellas; después hay snorkel en un arrecife. Lo que se ve depende de la temporada y del mar. ¿Van en '
           'grupo? La lancha privada para hasta 10 personas cuesta $20,000 MXN: pídela por WhatsApp.',
        en='Head out to sea on a shared boat to look for whales and orcas. If they show up and the sea allows, you try '
           'to swim alongside them; then you snorkel a reef. What you see depends on the season and the sea. Coming as '
           'a group? A private boat for up to 10 people is $20,000 MXN: ask for it on WhatsApp.',
        ficha=dict(duracion='5–6 h', duracion_en='5–6 h', punto_salida='La Ventana o Bahía de los Sueños',
                   punto_salida_en='La Ventana or Bahía de los Sueños'),
    ),
}

EXTRAS_EN = {'Licencia de pesca': 'Fishing license'}


def _aplicar(servicio, datos):
    cambios = []
    if servicio.incluye == datos['incluye_viejo']:
        servicio.incluye = datos['incluye']
        cambios.append('incluye')
    if servicio.descripcion == datos['es_viejo']:
        servicio.descripcion = datos['es']
        cambios.append('descripcion')
    if servicio.descripcion_en == datos['en_viejo']:
        servicio.descripcion_en = datos['en']
        cambios.append('descripcion_en')
    for campo, valor in datos['ficha'].items():
        if not getattr(servicio, campo):
            setattr(servicio, campo, valor)
            cambios.append(campo)
    if cambios:
        servicio.save(update_fields=cambios)


def cargar(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Servicio = apps.get_model('fleet', 'Servicio')
    Personalizacion = apps.get_model('fleet', 'Personalizacion')
    with alcance_operador_migracion(schema_editor.connection):
        for (empresa, slug), datos in SERVICIOS.items():
            for servicio in Servicio.objects.filter(empresa__slug=empresa, slug=slug):
                _aplicar(servicio, datos)
        for nombre, nombre_en in EXTRAS_EN.items():
            Personalizacion.objects.filter(nombre=nombre, nombre_en='').update(nombre_en=nombre_en)


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0054_ficha_servicio_nombre_en_extra'),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
