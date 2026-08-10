from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ESTADOS_QUE_OCUPAN_CUPO, Reserva, cupo_maximo_del_dia
from .serializers import CupoSerializer, ReservaCreateSerializer


class CupoDisponibleView(APIView):
    """Cupo restante para una fecha, para que el checkout avise antes de pagar
    (la validacion real y definitiva ocurre al confirmar el pago, ver apps/payments)."""

    def get(self, request):
        fecha = request.query_params.get('fecha')
        if not fecha:
            return Response({'detail': 'Falta el parametro fecha.'}, status=400)

        cupo_maximo = cupo_maximo_del_dia(fecha)
        ocupadas = Reserva.objects.filter(fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO).count()
        data = {
            'fecha': fecha,
            'cupo_maximo': cupo_maximo,
            'ocupadas': ocupadas,
            'disponible': ocupadas < cupo_maximo,
        }
        return Response(CupoSerializer(data).data)


class ReservaCreateView(generics.CreateAPIView):
    """Crea la reserva en estado pendiente_pago al iniciar el checkout.
    No ocupa cupo todavia (ver ESTADOS_QUE_OCUPAN_CUPO) — el cupo se valida
    al confirmar el pago, ver apps/payments/views.py."""

    queryset = Reserva.objects.all()
    serializer_class = ReservaCreateSerializer
