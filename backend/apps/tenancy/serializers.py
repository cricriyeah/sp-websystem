from decimal import Decimal

from django.core.cache import cache
from rest_framework import serializers

from .models import Sede

# /api/sedes/ se pide en cada carga del hub: el resumen del catálogo se cachea unos minutos.
RESUMEN_TTL_SEGUNDOS = 300


def resumen_de_sede(sede):
    """El «desde» y los tipos del catálogo de la sede, para las tarjetas del hub.

    El mínimo toma `precio_base` por servicio y `precio_ancla` por paquete, sin los servicios
    por ruta (no tienen un precio que anunciar); en empate gana el servicio. USD hacia arriba
    al dólar entero, como el cobro. Lee con `servicios_de_sede`/`paquetes_de_sede`, que abren
    el alcance de cada empresa: una consulta directa aquí devolvería nada bajo RLS.
    """
    # Import local: fleet importa de tenancy y al revés habría un ciclo.
    from apps.fleet.catalogo import paquetes_de_sede, servicios_de_sede
    from apps.payments.moneda import convertir

    servicios = servicios_de_sede(sede)
    paquetes = paquetes_de_sede(sede)
    candidatos = [
        (Decimal(s['precio_base']), s['estrategia_precio'], 'servicio')
        for s in servicios
        if s['estrategia_precio'] != 'por_ruta' and s['precio_base'] is not None
    ] + [
        (Decimal(p['precio_ancla']), p['estrategia_precio'], 'paquete')
        for p in paquetes
        if p['precio_ancla'] is not None
    ]
    desde = None
    for monto, base, tipo in candidatos:
        if desde is None or monto < desde[0]:
            desde = (monto, base, tipo)
    tipos = sorted({s['tipo_servicio'] for s in servicios} | ({'paquete'} if paquetes else set()))
    return {
        'desde': None if desde is None else {
            'monto_mxn': str(desde[0]),
            'monto_usd': str(convertir(desde[0], 'USD', sede.tipo_cambio_usd)),
            'base': desde[1],
            'tipo': desde[2],
        },
        'tipos': tipos,
    }


class SedeSerializer(serializers.ModelSerializer):
    resumen = serializers.SerializerMethodField()

    class Meta:
        model = Sede
        fields = ['id', 'nombre', 'slug', 'zona_horaria', 'tipo_cambio_usd', 'resumen']

    def get_resumen(self, sede):
        return cache.get_or_set(f'sede-resumen:{sede.pk}', lambda: resumen_de_sede(sede), RESUMEN_TTL_SEGUNDOS)
