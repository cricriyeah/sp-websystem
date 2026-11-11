"""Precios reales de Piratas Adventures (Puerto Chale), confirmados por el dueño el 2026-11-10.

- Tipo de cambio de la sede: 17.5 (el dueño cambia sus dólares a la compra; a 18 perdía en el cambio).
- Safari marino: $14,000 por 8 horas para 6 personas, +$2,000 por persona, hasta 8 (ya estaba; se suma la duración).
- Pesca deportiva: $13,000 por 8 horas, hasta 4 personas (antes $5,000 de relleno).
- Avistamiento de ballena jorobada: $5,000 por 2 horas para 1 a 6 personas, +$600 por persona, hasta 8 (antes $1,100 por
  persona de relleno). Los recorridos de 3 y 4 horas se piden por WhatsApp.
- Anticipo del 30 % en los tres. Licencia de pesca como extra de la pesca, al mismo precio que en La Paz.

Los precios no traen IVA (el sistema lo suma al final). Como la 0053 y la 0055, no pisa lo que alguien ya editó en el
admin: cada valor solo cambia si sigue siendo el de relleno, y la duración solo se llena si está vacía. Corre con
`alcance_operador_migracion` porque bajo RLS, sin alcance, no se ve ninguna fila.
"""
from decimal import Decimal

from django.db import migrations

EMPRESA = 'piratas-adventures'
LICENCIA_PRECIO_SI_NO_HAY_REFERENCIA = Decimal('300.00')

# slug -> {campo: (valor de relleno, valor real)}; `None` como relleno = cambia siempre que esté vacío.
CAMBIOS = {
    'safari-marino': {
        'duracion': ('', '8 h'),
        'duracion_en': ('', '8 h'),
    },
    'pesca-deportiva': {
        'precio_base': (Decimal('5000.00'), Decimal('13000.00')),
        'personas_incluidas': (2, 4),
        'duracion': ('', '8 h'),
        'duracion_en': ('', '8 h'),
    },
    'avistamiento-ballenas': {
        'nombre': ('Avistamiento de ballenas', 'Avistamiento de ballena jorobada'),
        'nombre_en': ('Whale watching', 'Humpback whale watching'),
        'estrategia_precio': ('por_persona', 'por_grupo'),
        'precio_base': (Decimal('1100.00'), Decimal('5000.00')),
        'precio_persona_extra': (Decimal('0.00'), Decimal('600.00')),
        'personas_incluidas': (1, 6),
        'capacidad_maxima': (10, 8),
        'duracion': ('', '2 h'),
        'duracion_en': ('', '2 h'),
        'descripcion': (
            'Avistamiento de ballenas en Puerto Chale.',
            'Dos horas en la bahía para ver a la ballena jorobada, que llega cada invierno a tener a sus crías. El precio '
            'cubre de 1 a 6 personas y caben hasta 2 más por un cargo por persona. Si quieres más tiempo, hay recorridos '
            'de 3 y 4 horas: pídelos por WhatsApp.',
        ),
        'descripcion_en': (
            '',
            'Two hours on the bay to see the humpback whales, which come every winter to give birth. The price covers 1 to '
            '6 people, with room for 2 more at a per-person charge. If you want more time, there are 3- and 4-hour '
            'trips: ask for them on WhatsApp.',
        ),
        'incluye': (
            {},
            {'es': ['Refrescos, aguas naturales, agua mineral y sueros sin costo',
                    'Puedes traer tus propias bebidas y alimentos'],
             'en': ['Sodas, fresh water, mineral water and electrolyte drinks at no cost',
                    'You can bring your own drinks and food']},
        ),
    },
}


def _aplicar(servicio, cambios):
    campos = []
    for campo, (relleno, real) in cambios.items():
        actual = getattr(servicio, campo)
        if actual == relleno or (relleno in ('', {}) and not actual):
            setattr(servicio, campo, real)
            campos.append(campo)
    # Anticipo del 30 %: solo si el servicio aún no tiene uno distinto configurado.
    if not servicio.permite_anticipo or not servicio.porcentaje_anticipo:
        servicio.permite_anticipo = True
        servicio.porcentaje_anticipo = 30
        campos += ['permite_anticipo', 'porcentaje_anticipo']
    if campos:
        servicio.save(update_fields=campos)


def _licencia(apps, empresa, pesca):
    Personalizacion = apps.get_model('fleet', 'Personalizacion')
    ServicioPersonalizacion = apps.get_model('fleet', 'ServicioPersonalizacion')
    if ServicioPersonalizacion.objects.filter(servicio=pesca, personalizacion__tipo='licencia').exists():
        return
    referencia = (ServicioPersonalizacion.objects
                  .filter(servicio__empresa__slug='sal-y-sol', servicio__slug='pesca-deportiva',
                          personalizacion__tipo='licencia')
                  .first())
    licencia, _ = Personalizacion.objects.get_or_create(
        empresa=empresa, nombre='Licencia de pesca',
        defaults=dict(nombre_en='Fishing license', tipo='licencia', tipo_interaccion='check',
                      cobrar_por_persona=True, cantidad_editable=True),
    )
    ServicioPersonalizacion.objects.create(
        servicio=pesca, personalizacion=licencia,
        precio=referencia.precio if referencia else LICENCIA_PRECIO_SI_NO_HAY_REFERENCIA,
    )


def cargar(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion

    Empresa = apps.get_model('tenancy', 'Empresa')
    Sede = apps.get_model('tenancy', 'Sede')
    Servicio = apps.get_model('fleet', 'Servicio')
    with alcance_operador_migracion(schema_editor.connection):
        Sede.objects.filter(slug='puerto-chale', tipo_cambio_usd=Decimal('18')).update(tipo_cambio_usd=Decimal('17.5'))
        empresa = Empresa.objects.filter(slug=EMPRESA).first()
        if empresa is None:
            return
        for slug, cambios in CAMBIOS.items():
            servicio = Servicio.objects.filter(empresa=empresa, slug=slug).first()
            if servicio is not None:
                _aplicar(servicio, cambios)
        pesca = Servicio.objects.filter(empresa=empresa, slug='pesca-deportiva').first()
        if pesca is not None:
            _licencia(apps, empresa, pesca)


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0055_ficha_y_listas_limpias'),
        ('tenancy', '0011_rls_notificacion'),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
