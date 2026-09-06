from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy import scope

from .models import ExtrasItem, Paquete, PuntoEncuentro, Servicio, Tarifa, TransportePrecio
from .serializers import (
    ExtrasItemSerializer,
    PaqueteSerializer,
    PuntoEncuentroSerializer,
    ServicioSerializer,
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


class ServiciosListView(APIView):
    """Lista publica de servicios activos para una empresa/sede."""

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            servicios = Servicio.objects.filter(empresa=empresa, activo=True)
            return Response(ServicioSerializer(servicios, many=True).data)


class ServicioDetailView(APIView):
    """Detalle publico de un servicio por slug para una empresa/sede."""

    def get(self, request, empresa_slug, slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            servicio = get_object_or_404(Servicio, empresa=empresa, slug=slug, activo=True)
            return Response(ServicioSerializer(servicio).data)


class PaquetesPorSedeListView(APIView):
    """Catalogo publico de experiencias empaquetadas activas por localidad/sede."""

    def get(self, request, sede_slug):
        from apps.tenancy.models import Sede
        sede = get_object_or_404(Sede, slug=sede_slug)
        with scope.como_operador_plataforma():
            paquetes = (
                Paquete.objects.filter(sede=sede, activo=True, empresa_lider__activo=True)
                .select_related('sede', 'empresa_lider')
                .prefetch_related('servicios_asociados__servicio')
            )
            return Response(PaqueteSerializer(paquetes, many=True).data)


class PaquetesPorEmpresaListView(APIView):
    """Paquetes liderados por una empresa especifica."""

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            paquetes = (
                Paquete.objects.filter(empresa_lider=empresa, activo=True)
                .select_related('sede', 'empresa_lider')
                .prefetch_related('servicios_asociados__servicio')
            )
            return Response(PaqueteSerializer(paquetes, many=True).data)


class SedesListView(APIView):
    """Lista publica de localidades/sedes activas para el selector del frontend."""

    def get(self, request):
        from apps.tenancy.models import Sede
        from apps.tenancy.serializers import SedeSerializer

        sedes = Sede.objects.filter(activo=True).order_by('nombre')
        return Response(SedeSerializer(sedes, many=True).data)


class ServiciosPorSedeListView(APIView):
    """Catalogo publico de servicios sueltos activos por localidad/sede (camino secundario)."""

    def get(self, request, sede_slug):
        from apps.tenancy.models import Sede

        sede = get_object_or_404(Sede, slug=sede_slug)
        with scope.como_operador_plataforma():
            servicios = (
                Servicio.objects.filter(empresa__sede=sede, activo=True, empresa__activo=True)
                .select_related('empresa')
                .prefetch_related('servicio_personalizaciones__personalizacion')
                .order_by('nombre')
            )
            return Response(ServicioSerializer(servicios, many=True).data)

