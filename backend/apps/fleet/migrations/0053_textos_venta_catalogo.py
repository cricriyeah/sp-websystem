"""Textos de venta del catálogo real (2026-10-22): nombre y descripción en inglés, y la descripción en español
reescrita para la página de detalle.

No pisa lo que alguien ya editó en el admin: el nombre y la descripción en inglés solo se llenan si están vacíos,
y la descripción en español solo se reemplaza si sigue siendo la que dejó `seed_catalogo_real` (o está vacía).
Corre con `alcance_operador_migracion` porque bajo RLS, sin alcance, no se ve ninguna fila.
"""
from django.db import migrations

HOTEL_DISTANCIAS = ('A 1 km de la playa de La Ventana, con restaurantes a menos de 1 km, a 2.2 km del centro de '
                    'La Ventana y a 37 km del aeropuerto de La Paz. Distancias en línea recta: el recorrido real puede variar.')
PIRATAS_COMIDA_ES = ('Refrescos, aguas, agua mineral y sueros van sin costo y, si quieres, comida sencilla como '
                     'sándwiches o burritos. También puedes llevar tus propias bebidas y alimentos.')
PIRATAS_COMIDA_EN = ('Sodas, water, mineral water and electrolyte drinks come at no cost and, if you like, simple food '
                     'such as sandwiches or burritos. You can also bring your own drinks and food.')

# (empresa, slug) -> nombre_en, descripción en español, descripción en inglés, descripciones viejas del seed
SERVICIOS = {
    ('sal-y-sol', 'pesca-deportiva'): dict(
        nombre_en='Sportfishing',
        es='La panga es solo para tu grupo: hasta 5 personas, con un capitán local que sale contigo entre las 5 y '
           'las 7 de la mañana. Según la temporada, vas tras marlín, dorado o jurel. El desayuno ligero, la comida, '
           'la fruta, las botanas y las bebidas van a bordo, así que tú solo te ocupas de pescar. La licencia de '
           'pesca se tramita aparte, solo para quienes vayan a pescar.',
        en='The panga is yours alone: up to 5 people, with a local captain who heads out with you between 5 and '
           '7 am. Depending on the season, you are after marlin, mahi-mahi or yellowtail. Light breakfast, lunch, '
           'fruit, snacks and drinks are on board, so all you have to do is fish. Fishing licenses are arranged '
           'separately, only for those who will be fishing.',
        viejas=(
            'Viaje de pesca deportiva en La Paz, de 5:00 a 7:00 am de salida, en panga para hasta 8 personas. '
            'La licencia de pesca se tramita aparte, para las personas que elijas.',
            'Viaje de pesca deportiva en La Paz, de 5:00 a 7:00 am de salida, en panga para hasta 5 personas. '
            'La licencia de pesca se tramita aparte, para las personas que elijas.',
        ),
    ),
    ('la-ventana-travel', 'pesca-con-mosca'): dict(
        nombre_en='Fly fishing',
        es='Un día completo de pesca con mosca en las aguas de La Ventana, para ti y hasta dos acompañantes: el '
           'precio es el mismo si van uno, dos o tres. Sales entre las 7 y las 8 de la mañana, con comida ligera, '
           'botanas y bebidas a bordo, y equipo de snorkel para cuando quieras meterte al agua. La licencia de pesca '
           'no está incluida.',
        en='A full day of fly fishing in the waters off La Ventana, for you and up to two companions: the price is '
           'the same whether one, two or three of you go. You head out between 7 and 8 am with a light meal, snacks '
           'and drinks on board, plus snorkel gear for when you want to get in the water. Fishing licenses are not '
           'included.',
        viejas=(
            'Un día de pesca con mosca (fly fishing) en La Ventana, para un grupo de hasta 3 personas, '
            'sin cargo por persona extra. La licencia de pesca no está incluida.',
        ),
    ),
    ('la-ventana-travel', 'avistamiento-ballenas-orcas'): dict(
        nombre_en='Whale and orca watching',
        es='Sales al mar entre las 7 y las 8 de la mañana, desde La Ventana o Bahía de los Sueños, a buscar ballenas '
           'y orcas. Si aparecen y el mar lo permite, se intenta nadar con ellas; después hay snorkel en un arrecife. '
           'Son de 5 a 6 horas en lancha compartida, con algo de comer, aguas, refrescos y el equipo de snorkel. Lo '
           'que se ve depende de la temporada y del mar. ¿Van en grupo? La lancha privada para hasta 10 personas '
           'cuesta $20,000 MXN: pídela por WhatsApp.',
        en='Head out to sea between 7 and 8 am, from La Ventana or Bahía de los Sueños, to look for whales and '
           'orcas. If they show up and the sea allows, you try to swim alongside them; then you snorkel a reef. It '
           'is 5 to 6 hours on a shared boat, with something to eat, water, sodas and snorkel gear. What you see '
           'depends on the season and the sea. Coming as a group? A private boat for up to 10 people is '
           '$20,000 MXN: ask for it on WhatsApp.',
        viejas=(
            'Salida diaria al mar para buscar ballenas y orcas e intentar nadar con ellas, con snorkel en un '
            'arrecife. Precio por persona en lancha compartida; '
            'para un grupo privado (hasta 10 personas) el costo es de $20,000 MXN: consúltalo por WhatsApp.',
        ),
    ),
    ('la-ventana-travel', 'hospedaje-la-ventana'): dict(
        nombre_en='Hotel Casa Arrecife',
        es='Seis estudios para dos personas, cada uno con cama king size, a 1 km de la playa de La Ventana. Tienes '
           'restaurantes a menos de 1 km, el centro del pueblo a 2.2 km y el aeropuerto de La Paz a 37 km '
           '(distancias en línea recta: el camino real puede ser más largo). Los niños de cualquier edad son '
           'bienvenidos.',
        en='Six studios for two, each with a king size bed, 1 km from the beach at La Ventana. Restaurants are less '
           'than 1 km away, the village center 2.2 km and La Paz airport 37 km (straight-line distances: the actual '
           'drive may be longer). Children of all ages are welcome.',
        viejas=(
            'Seis estudios (suites) para 2 personas, cada uno con una cama king size. Precio por noche. '
            + HOTEL_DISTANCIAS,
            'Habitación con hospedaje en La Ventana. Precio por noche.',
        ),
    ),
    ('la-ventana-travel', 'traslado-aeropuerto-la-ventana'): dict(
        nombre_en='Airport transfer',
        es='Te recogen en el aeropuerto, te llevan al hotel y, al terminar tu estancia, te regresan al aeropuerto. '
           'Un solo traslado redondo, sin buscar taxi al llegar.',
        en='You are picked up at the airport, taken to your hotel and, when your stay ends, driven back to the '
           'airport. One round-trip transfer, no hunting for a taxi when you land.',
        viejas=('Traslado redondo aeropuerto-hotel-aeropuerto.',),
    ),
    ('transporte-la-paz', 'traslados-la-paz'): dict(
        nombre_en='Private transfers in La Paz',
        es='Traslados privados en La Paz, solo para tu grupo: del aeropuerto a tu hotel y de regreso, o del hotel a '
           'tu actividad.',
        en='Private transfers in La Paz, just for your group: from the airport to your hotel and back, or from your '
           'hotel to your activity.',
        viejas=('Traslados privados en La Paz: del aeropuerto al hotel y de regreso, y del hotel a la actividad.',),
    ),
    ('piratas-adventures', 'safari-marino'): dict(
        nombre_en='Marine safari',
        es='Una salida al mar en Puerto Chale para un grupo de 6 personas, con lugar para 2 más por un cargo '
           'adicional; si son más, se puede sumar otra embarcación avisando con tiempo. ' + PIRATAS_COMIDA_ES,
        en='A boat trip in Puerto Chale for a group of 6, with room for 2 more for an extra charge; for a bigger '
           'group, another boat can be added with some notice. ' + PIRATAS_COMIDA_EN,
        viejas=(
            'Safari marino en Puerto Chale para un grupo de 6 personas, con hasta 2 personas más '
            'por un cargo adicional. Si el grupo es más grande se puede sumar otra embarcación '
            'avisando con un poco de anticipación.',
        ),
    ),
    ('piratas-adventures', 'pesca-deportiva'): dict(
        nombre_en='Sportfishing',
        es='Pesca deportiva en Puerto Chale para hasta 4 personas. ' + PIRATAS_COMIDA_ES
           + ' La licencia de pesca no está incluida.',
        en='Sportfishing in Puerto Chale for up to 4 people. ' + PIRATAS_COMIDA_EN + ' Fishing licenses are not included.',
        viejas=('Pesca deportiva en Puerto Chale, hasta 4 personas. La licencia de pesca no está incluida.',),
    ),
    ('piratas-adventures', 'avistamiento-ballenas'): dict(nombre_en='Whale watching'),
}


def _paquete(noches, palabra_es, palabra_en):
    return dict(
        nombre_en=f'{noches}-night package',
        es=f'{palabra_es} noches en La Ventana con todo resuelto: te recogen en el aeropuerto, duermes en el Hotel '
           f'Casa Arrecife y, del día 2 al {noches}, sales cada día al mar a buscar ballenas y orcas, con comida '
           f'ligera, botanas, bebidas y equipo de snorkel a bordo. Al final te llevan de vuelta al aeropuerto. Las '
           f'comidas en tierra corren por tu cuenta: hay restaurantes a menos de 1 km del hotel.',
        en=f'{palabra_en} nights in La Ventana, all arranged: you are picked up at the airport, stay at Hotel Casa '
           f'Arrecife and, from day 2 to day {noches}, head out to sea every day to look for whales and orcas, with '
           f'a light meal, snacks, drinks and snorkel gear on board. At the end, you are driven back to the airport. '
           f'Meals on land are on you: there are restaurants less than 1 km from the hotel.',
        viejas=(f'{noches} noches de hospedaje, traslado redondo de aeropuerto y '
                f'avistamiento de ballenas y orcas del día 2 al {noches}.',),
    )


# (sede, slug) -> lo mismo que SERVICIOS
PAQUETES = {
    ('la-ventana', 'paquete-5-noches'): _paquete(5, 'Cinco', 'Five'),
    ('la-ventana', 'paquete-7-noches'): _paquete(7, 'Siete', 'Seven'),
}


def _aplicar(objeto, textos):
    cambios = []
    if not objeto.nombre_en and textos.get('nombre_en'):
        objeto.nombre_en = textos['nombre_en']
        cambios.append('nombre_en')
    if 'es' in textos and (not objeto.descripcion or objeto.descripcion in textos['viejas']):
        objeto.descripcion = textos['es']
        cambios.append('descripcion')
    if 'en' in textos and not objeto.descripcion_en:
        objeto.descripcion_en = textos['en']
        cambios.append('descripcion_en')
    if cambios:
        objeto.save(update_fields=cambios)


def cargar_textos(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Servicio = apps.get_model('fleet', 'Servicio')
    Paquete = apps.get_model('fleet', 'Paquete')
    with alcance_operador_migracion(schema_editor.connection):
        for (empresa, slug), textos in SERVICIOS.items():
            for servicio in Servicio.objects.filter(empresa__slug=empresa, slug=slug):
                _aplicar(servicio, textos)
        for (sede, slug), textos in PAQUETES.items():
            for paquete in Paquete.objects.filter(sede__slug=sede, slug=slug):
                _aplicar(paquete, textos)


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0052_nombre_descripcion_en'),
    ]

    operations = [
        migrations.RunPython(cargar_textos, migrations.RunPython.noop),
    ]
