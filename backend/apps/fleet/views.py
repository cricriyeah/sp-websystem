from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy import scope

from .models import ExtrasItem, PuntoEncuentro, Tarifa, TransportePrecio
from .serializers import (
    ExtrasItemSerializer,
    PuntoEncuentroSerializer,
    TarifaSerializer,
    TransportePrecioSerializer,
)

# Tope defensivo del preview de precio, no una regla de negocio: el limite real
# de personas por viaje (MAX_PERSONAS) vive en apps.bookings y este endpoint no
# depende de esa app a proposito, para no crear un ciclo fleet<->bookings. Solo
# evita una multiplicacion absurda si alguien manda `personas` gigante.
PERSONAS_MAXIMO_PREVIEW = 50


class TarifaView(APIView):
    """Precio unico del tour de una Empresa, para que el checkout de la web no lo hardcodee."""

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            tarifa = Tarifa.de(empresa)
            if tarifa is None:
                return Response({'detail': 'Tarifa no configurada.'}, status=503)
            return Response(TarifaSerializer(tarifa).data)


class ExtrasPublicosView(APIView):
    """Catalogo de extras del checkout de una Empresa (brunch, licencia, carnada,
    transporte, puntos de encuentro) con el monto ya resuelto para
    `personas`/`moneda`.

    La web nunca calcula si un extra cobra por persona ni si aplica el
    recargo de grupo: pide este endpoint con el numero de personas y la
    moneda que tenga en pantalla y muestra lo que responde, igual que ya
    hace con `/api/<empresa_slug>/tarifa/`.
    """

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)

        moneda = request.query_params.get('moneda', 'MXN')
        if moneda not in ('MXN', 'USD'):
            return Response({'detail': 'moneda invalida.'}, status=400)

        crudo = request.query_params.get('personas', '1')
        try:
            personas = int(crudo)
        except ValueError:
            return Response({'detail': 'personas invalida.'}, status=400)
        if not (1 <= personas <= PERSONAS_MAXIMO_PREVIEW):
            return Response({'detail': 'personas invalida.'}, status=400)

        contexto = {'personas': personas, 'moneda': moneda}
        with scope.con_empresa(empresa):
            return Response({
                'extras': ExtrasItemSerializer(
                    ExtrasItem.objects.filter(activo=True, empresa=empresa), many=True, context=contexto
                ).data,
                'transporte': TransportePrecioSerializer(
                    TransportePrecio.objects.filter(activo=True, empresa=empresa), many=True, context=contexto
                ).data,
                'puntos_encuentro': PuntoEncuentroSerializer(
                    PuntoEncuentro.objects.filter(activo=True, empresa=empresa), many=True
                ).data,
            })
