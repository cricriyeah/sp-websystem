from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ESTADOS_QUE_OCUPAN_CUPO, Reserva, cupo_maximo_del_dia
from .serializers import CupoSerializer, ReservaCheckoutSerializer


class CupoDisponibleView(APIView):
    """Cupo restante para una fecha, para que el checkout avise antes de pagar
    (la validacion real y definitiva ocurre al confirmar el pago, ver apps/payments)."""

    def get(self, request):
        fecha = request.query_params.get('fecha')
        if not fecha:
            return Response({'detail': 'Falta el parametro fecha.'}, status=400)

        try:
            fecha = date.fromisoformat(fecha)
        except ValueError:
            return Response({'detail': 'fecha debe tener el formato YYYY-MM-DD.'}, status=400)

        cupo_maximo = cupo_maximo_del_dia(fecha)
        ocupadas = Reserva.objects.filter(fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO).count()
        data = {
            'fecha': fecha,
            'cupo_maximo': cupo_maximo,
            'ocupadas': ocupadas,
            'disponible': ocupadas < cupo_maximo,
        }
        return Response(CupoSerializer(data).data)


class ReservaCheckoutView(APIView):
    """Guarda la reserva de una sesion de checkout, en estado pendiente_pago.

    No ocupa cupo todavia (ver ESTADOS_QUE_OCUPAN_CUPO) — el cupo se valida al
    confirmar el pago, ver apps/payments/views.py.

    Es un upsert por `checkout_id`: el navegador manda el mismo identificador
    durante toda la sesion, asi que reintentar tras un error o corregir la fecha
    reescribe la misma fila en vez de dejar reservas abandonadas duplicadas.
    """

    def post(self, request):
        checkout_id = request.data.get('checkout_id')
        existente = (
            Reserva.objects.filter(
                checkout_id=checkout_id, estado=Reserva.Estado.PENDIENTE_PAGO
            ).first()
            if checkout_id
            else None
        )

        serializer = ReservaCheckoutSerializer(
            existente, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200 if existente else 201)
