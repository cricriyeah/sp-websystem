from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import Reserva, Vendedora


class CupoSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    cupo_maximo = serializers.IntegerField()
    ocupadas = serializers.IntegerField()
    disponible = serializers.BooleanField()


def ip_del_cliente(request):
    """IP para el registro del deslinde. En Render/Vercel la request llega por
    proxy, asi que la real es la primera de X-Forwarded-For."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class ReservaCheckoutSerializer(serializers.ModelSerializer):
    """Crea o actualiza la reserva de una sesion de checkout.

    Sirve para las dos cosas a proposito: mientras la reserva siga en
    `pendiente_pago`, cada envio del checkout reescribe la misma fila. Asi
    corregir la fecha o reintentar tras un error no deja reservas duplicadas.
    """

    checkout_id = serializers.UUIDField()

    # Codigo de la vendedora que trae el cliente en el link (?ref=). Es
    # write_only: la web lo manda, nadie lo consulta de vuelta. Un codigo
    # inexistente o de alguien dado de baja se ignora en silencio — un link
    # viejo mal copiado no puede impedir que alguien reserve.
    ref = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Reserva
        fields = [
            'id', 'checkout_id', 'fecha', 'hora', 'numero_personas',
            'nombre_cliente', 'telefono_cliente', 'correo_cliente',
            'moneda', 'deslinde_aceptado', 'deslinde_nombre',
            'lleva_lunch', 'pide_bebidas', 'pide_transporte',
            'ref', 'estado',
        ]
        read_only_fields = ['id', 'estado']

    def validate_deslinde_aceptado(self, value):
        # Sin casilla marcada no hay reserva (ver docs/contexto-negocio.md, Legal).
        if not value:
            raise serializers.ValidationError('Debes aceptar el deslinde de responsabilidad.')
        return value

    def validate_deslinde_nombre(self, value):
        if not value.strip():
            raise serializers.ValidationError('Escribe tu nombre para aceptar el deslinde.')
        return value.strip()

    def validate(self, attrs):
        # Una reserva que ya se pago no se toca desde la web: el cupo, el cobro y
        # la asignacion dependen de esos datos.
        if self.instance and self.instance.estado != Reserva.Estado.PENDIENTE_PAGO:
            raise serializers.ValidationError('Esta reserva ya no se puede modificar.')
        return attrs

    def save(self, **kwargs):
        # La fecha/hora e IP del deslinde se sellan aqui, en el servidor, con cada
        # envio: valen como constancia de la ultima version aceptada.
        request = self.context['request']

        # `ref` no es campo del modelo, hay que sacarlo antes de construir la
        # Reserva. Solo se atribuye cuando el codigo resuelve: si no viene ref (o
        # no sirve) se respeta lo que ya tuviera la reserva, para no borrar una
        # atribucion hecha a mano cuando el cliente reenvia el checkout.
        vendedora = Vendedora.por_codigo(self.validated_data.pop('ref', ''))

        return super().save(
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado_en=timezone.now(),
            deslinde_ip=ip_del_cliente(request),
            **({'vendedora': vendedora} if vendedora else {}),
            **kwargs,
        )

    def create(self, validated_data):
        return self._guardar(Reserva(**validated_data))

    def update(self, instance, validated_data):
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        return self._guardar(instance)

    def _guardar(self, reserva):
        # full_clean corre el motor unico de validacion (ventana de salida, cupo,
        # deslinde, capacidad), ver apps/bookings/models.py y backend/CLAUDE.md.
        try:
            reserva.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            )
        reserva.save()
        return reserva
