import uuid
from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    ESTADOS_QUE_OCUPAN_CUPO,
    Reserva,
    cupo_maximo_del_dia,
    proxima_fecha_disponible,
)
from .serializers import CupoSerializer, ReservaCheckoutSerializer


class CupoDisponibleView(APIView):
    """Cupo restante para una fecha, para que el checkout avise antes de pagar
    (la validacion real y definitiva ocurre al confirmar el pago, ver apps/payments)."""

    throttle_scope = 'consulta'

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
            # Se responde siempre, tambien cuando el dia pedido si tiene
            # espacio: asi el navegador nunca necesita una segunda vuelta.
            'proxima_disponible': proxima_fecha_disponible(fecha, 1),
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

    throttle_scope = 'reservas'

    def post(self, request):
        existente = self._pendiente_de(request.data.get('checkout_id'))

        serializer = ReservaCheckoutSerializer(
            existente, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200 if existente else 201)

    @staticmethod
    def _pendiente_de(checkout_id):
        """La reserva sin pagar de este checkout, si la hay.

        El valor llega crudo del request: esta busqueda es la que decide que
        instancia recibe el serializer, asi que corre **antes** de que el
        serializer valide nada. Metido directo al filtro de un `UUIDField`, uno
        mal formado revienta con `ValidationError` (o `AttributeError`, si no es
        ni texto) y esta ruta — publica y sin autenticacion — contesta 500.

        Aqui solo se decide si hay algo que buscar. Si no es un UUID no se busca:
        el 400 lo da el serializer, que es a quien le toca.
        """
        try:
            uuid.UUID(str(checkout_id))
        except (ValueError, TypeError):
            return None

        return Reserva.objects.filter(
            checkout_id=checkout_id, estado=Reserva.Estado.PENDIENTE_PAGO
        ).first()
