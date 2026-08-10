from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tarifa
from .serializers import TarifaSerializer


class TarifaView(APIView):
    """Precio unico del tour, para que el checkout de la web no lo hardcodee."""

    def get(self, request):
        tarifa = Tarifa.actual()
        if tarifa is None:
            return Response({'detail': 'Tarifa no configurada.'}, status=503)
        return Response(TarifaSerializer(tarifa).data)
