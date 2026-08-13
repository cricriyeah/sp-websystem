from rest_framework import serializers

from apps.payments.pricing import PERSONAS_INCLUIDAS

from .models import Tarifa


class TarifaSerializer(serializers.ModelSerializer):
    """Todas las cifras que necesita el checkout, para que la web no duplique
    ninguna: precio del viaje, cargo por persona adicional y precio del lunch.

    `precio` es el de pesos; los `*_usd` vienen en null cuando el negocio
    todavia no fijo ese precio en dolares. Bebidas y transporte no aparecen: no
    tienen precio en linea, los cotiza el agente (ver apps/payments/pricing.py).
    """

    personas_incluidas = serializers.SerializerMethodField()

    class Meta:
        model = Tarifa
        fields = [
            'precio', 'precio_usd',
            'precio_persona_extra', 'precio_persona_extra_usd', 'personas_incluidas',
            'precio_lunch', 'precio_lunch_usd',
        ]

    def get_personas_incluidas(self, obj):
        return PERSONAS_INCLUIDAS
