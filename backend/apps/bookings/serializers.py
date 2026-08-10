from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Reserva, cupo_maximo_del_dia


class CupoSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    cupo_maximo = serializers.IntegerField()
    ocupadas = serializers.IntegerField()
    disponible = serializers.BooleanField()


class ReservaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reserva
        fields = [
            'id', 'fecha', 'hora', 'numero_personas',
            'nombre_cliente', 'telefono_cliente', 'correo_cliente',
            'estado',
        ]
        read_only_fields = ['id', 'estado']

    def create(self, validated_data):
        # canal_origen='web' y estado por defecto (pendiente_pago) — ver modelo.
        # full_clean corre el motor unico de validacion (ventana de salida, cupo
        # si aplicara), ver apps/bookings/models.py y backend/CLAUDE.md.
        reserva = Reserva(canal_origen=Reserva.CanalOrigen.WEB, **validated_data)
        try:
            reserva.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
        reserva.save()
        return reserva
