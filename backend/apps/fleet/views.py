from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy import scope

from .catalogo import paquete_de_sede, paquetes_de_sede, servicios_de_sede
from .enums import TipoServicio
from .models import Paquete, PuntoEncuentro, Servicio, TransporteTarifa
from .serializers import (
    PaqueteSerializer,
    PuntoEncuentroSerializer,
    ServicioSerializer,
)

class ServiciosListView(APIView):
    """Lista publica de servicios activos para una empresa/sede."""

    throttle_scope = 'catalogo'

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            servicios = (
                Servicio.objects.filter(empresa=empresa, activo=True, solo_en_paquete=False)
                .prefetch_related('servicio_personalizaciones__personalizacion')
                .order_by('nombre')
            )
            return Response(ServicioSerializer(servicios, many=True).data)


class ServicioDetailView(APIView):
    """Detalle publico de un servicio por slug para una empresa/sede."""

    throttle_scope = 'catalogo'

    def get(self, request, empresa_slug, slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            servicio = get_object_or_404(Servicio, empresa=empresa, slug=slug, activo=True, solo_en_paquete=False)
            return Response(ServicioSerializer(servicio).data)


class PaquetesPorSedeListView(APIView):
    """Catalogo publico de experiencias empaquetadas activas por localidad/sede.

    Recorre las Empresas de la Sede cada una en su propio alcance RLS (ver
    apps.fleet.catalogo) -- nunca `como_operador_plataforma()` en una ruta
    publica.
    """

    throttle_scope = 'catalogo'

    def get(self, request, sede_slug):
        from apps.tenancy.models import Sede

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        return Response(paquetes_de_sede(sede))


class PaquetesPorEmpresaListView(APIView):
    """Paquetes liderados por una empresa especifica."""

    throttle_scope = 'catalogo'

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

    throttle_scope = 'catalogo'

    def get(self, request):
        from apps.tenancy.models import Sede
        from apps.tenancy.serializers import SedeSerializer

        sedes = Sede.objects.filter(activo=True).order_by('nombre')
        return Response(SedeSerializer(sedes, many=True).data)


class ServiciosPorSedeListView(APIView):
    """Catalogo publico de servicios sueltos activos por localidad/sede (camino secundario).

    Mismo criterio que PaquetesPorSedeListView: una transaccion por Empresa,
    RLS activa en cada tramo.
    """

    throttle_scope = 'catalogo'

    def get(self, request, sede_slug):
        from apps.tenancy.models import Sede

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        return Response(servicios_de_sede(sede))


class PaqueteDetailView(APIView):
    """Detalle publico de un paquete por sede y slug."""

    throttle_scope = 'catalogo'

    def get(self, request, sede_slug, slug):
        from apps.tenancy.models import Sede

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        data = paquete_de_sede(sede, slug)
        if data is None:
            return Response({'detail': 'Paquete no encontrado.'}, status=404)
        return Response(data)


class TrasladosView(APIView):
    """Catalogo de traslados de una empresa, consultado bajo su alcance RLS."""

    permission_classes = []
    throttle_scope = 'catalogo'

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            servicio = Servicio.objects.filter(
                empresa=empresa, activo=True, solo_en_paquete=False, tipo_servicio=TipoServicio.TRANSPORTE,
            ).order_by('pk').first()
            if servicio is None:
                raise Http404('Servicio de transporte no encontrado.')
            if not empresa.stripe_secret_key or not empresa.stripe_publishable_key:
                return Response({'detail': 'Stripe no configurado.'}, status=503)
            return Response({
                'servicio': {
                    'slug': servicio.slug,
                    'nombre': servicio.nombre,
                    'capacidad_maxima': servicio.capacidad_maxima,
                    'porcentaje_anticipo': servicio.porcentaje_anticipo,
                    'permite_anticipo': servicio.permite_anticipo,
                    'empresa_slug': empresa.slug,
                    'tipo_cambio_usd': str(empresa.sede.tipo_cambio_usd),
                    'hora_apertura': servicio.hora_apertura.isoformat() if servicio.hora_apertura else None,
                    'hora_cierre': servicio.hora_cierre.isoformat() if servicio.hora_cierre else None,
                    'paso_hora_minutos': servicio.paso_hora_minutos,
                },
                'tarifas': [{
                    'tipo_traslado': tarifa.tipo_traslado,
                    'zona': tarifa.zona,
                    'personas_min': tarifa.personas_min,
                    'personas_max': tarifa.personas_max,
                    'precio': str(tarifa.precio),
                } for tarifa in TransporteTarifa.objects.filter(empresa=empresa, activo=True)],
                'puntos_encuentro': PuntoEncuentroSerializer(
                    PuntoEncuentro.objects.filter(empresa=empresa, activo=True), many=True,
                ).data,
                'publishable_key': empresa.stripe_publishable_key,
            })
