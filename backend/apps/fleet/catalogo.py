"""Catálogo público por Sede, sin desactivar RLS.

Una Sede agrupa varias Empresas aisladas (ADR-001). El catálogo de cara al
cliente necesita mostrar las experiencias de todas ellas juntas, pero **no** a
costa de `como_operador_plataforma()` en una ruta pública: eso apaga RLS para
toda la petición y convierte cualquier filtro olvidado en fuga silenciosa —
exactamente lo que ADR-001 quería evitar.

En su lugar se itera Empresa por Empresa, cada una dentro de su propio
`con_empresa(...)`, y se serializa dentro del alcance. RLS sigue activa en cada
tramo; una Empresa nunca ve datos de otra. La Sede tiene pocas Empresas, así que
el costo (una transacción corta por Empresa) es aceptable para un GET.

Paquetes que combinan Empresas distintas (cruza-empresa) se resuelven en la
Sección 7 del plan de corrección (ADR-005): la política RLS de
`fleet_paqueteservicio` hoy solo deja ver los componentes al `empresa_lider`, así
que un componente de otra Empresa no se renderiza todavía por esta vía. No hay
paquetes cruza-empresa sembrados aún.
"""
from apps.tenancy import scope
from apps.tenancy.models import Empresa

from .models import Paquete, Servicio
from .serializers import PaqueteSerializer, ServicioSerializer


def _empresas_activas_de(sede):
    # tenancy_empresa no lleva RLS; esta consulta corre fuera de todo alcance.
    return list(Empresa.objects.filter(sede=sede, activo=True).order_by('nombre'))


def servicios_de_sede(sede):
    """Lista de dicts serializados de los servicios activos de todas las
    Empresas activas de la Sede."""
    resultado = []
    for empresa in _empresas_activas_de(sede):
        with scope.con_empresa(empresa):
            qs = (
                Servicio.objects.filter(empresa=empresa, activo=True)
                .prefetch_related('servicio_personalizaciones__personalizacion')
                .order_by('nombre')
            )
            resultado.extend(ServicioSerializer(qs, many=True).data)
    return resultado


def paquetes_de_sede(sede):
    """Lista de dicts serializados de los paquetes activos liderados por
    cualquiera de las Empresas activas de la Sede."""
    resultado = []
    for empresa in _empresas_activas_de(sede):
        with scope.con_empresa(empresa):
            qs = (
                Paquete.objects.filter(empresa_lider=empresa, activo=True)
                .select_related('sede', 'empresa_lider')
                .prefetch_related('servicios_asociados__servicio')
                .order_by('nombre')
            )
            resultado.extend(PaqueteSerializer(qs, many=True).data)
    return resultado


def paquete_de_sede(sede, slug):
    """Devuelve el dict serializado del paquete activo con ese slug en la Sede,
    o None si no existe."""
    for empresa in _empresas_activas_de(sede):
        with scope.con_empresa(empresa):
            paquete = (
                Paquete.objects.filter(empresa_lider=empresa, slug=slug, activo=True)
                .select_related('sede', 'empresa_lider')
                .prefetch_related('servicios_asociados__servicio')
                .first()
            )
            if paquete is not None:
                return PaqueteSerializer(paquete).data
    return None

