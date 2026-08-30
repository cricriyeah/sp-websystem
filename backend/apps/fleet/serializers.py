from rest_framework import serializers

from apps.payments.pricing import PERSONAS_INCLUIDAS, cargo_por_extra, cargo_por_transporte

from .models import ExtrasItem, PuntoEncuentro, Tarifa, TransportePrecio


class TarifaSerializer(serializers.ModelSerializer):
    """Cifras del tour, para que la web no las duplique: precio del viaje y
    cargo por persona adicional. Los extras del checkout (brunch, licencia,
    carnada, transporte) ya no viven aqui, vienen de `/api/extras/` — ver
    ExtrasPublicosView.

    `precio` es el de pesos; los `*_usd` vienen en null cuando el negocio
    todavia no fijo ese precio en dolares. Bebidas no aparece: no tiene
    precio en linea, la cotiza el agente (ver apps/payments/pricing.py).
    """

    personas_incluidas = serializers.SerializerMethodField()

    class Meta:
        model = Tarifa
        fields = [
            'precio', 'precio_usd',
            'precio_persona_extra', 'precio_persona_extra_usd', 'personas_incluidas',
        ]

    def get_personas_incluidas(self, obj):
        return PERSONAS_INCLUIDAS


class ExtrasItemSerializer(serializers.ModelSerializer):
    """El monto ya viene resuelto para `(personas, moneda)` — la web nunca
    reimplementa si un extra cobra por persona ni ninguna otra regla de
    dinero, eso vive solo en apps/payments/pricing.py (ver ExtrasPublicosView)."""

    monto = serializers.SerializerMethodField()

    class Meta:
        model = ExtrasItem
        fields = [
            'id', 'tipo', 'nombre', 'descripcion', 'cobrar_por_persona',
            'cantidad_editable', 'preseleccionado', 'monto',
        ]

    def get_monto(self, obj):
        monto = cargo_por_extra(
            obj.precio_en(self.context['moneda']), obj.cobrar_por_persona, self.context['personas']
        )
        return str(monto) if monto is not None else None


class TransportePrecioSerializer(serializers.ModelSerializer):
    """Igual que ExtrasItemSerializer: `monto` ya trae base + recargo (si
    aplica) resuelto para `(personas, moneda)`."""

    monto = serializers.SerializerMethodField()

    class Meta:
        model = TransportePrecio
        fields = ['zona', 'min_personas_recargo', 'monto']

    def get_monto(self, obj):
        moneda = self.context['moneda']
        monto = cargo_por_transporte(
            obj.precio_en(moneda), obj.recargo_en(moneda), obj.min_personas_recargo,
            self.context['personas'],
        )
        return str(monto) if monto is not None else None


class PuntoEncuentroSerializer(serializers.ModelSerializer):
    class Meta:
        model = PuntoEncuentro
        fields = ['id', 'nombre', 'zona']
