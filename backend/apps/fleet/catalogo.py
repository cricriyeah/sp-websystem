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

En paquetes que combinan Empresas distintas, las filas de componentes se leen
con el alcance de la líder y cada servicio se serializa con el alcance de su
propia Empresa. Los alcances son secuenciales, nunca anidados.
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
                Servicio.objects.filter(empresa=empresa, activo=True, solo_en_paquete=False)
                .prefetch_related('servicio_personalizaciones__personalizacion')
                .order_by('nombre')
            )
            resultado.extend(ServicioSerializer(qs, many=True).data)
    return resultado


def _componentes_de(paquete, empresas):
    """Componentes del paquete legibles bajo RLS. Las filas de PaqueteServicio se leen con el
    alcance de la líder y SIN unir con Servicio; después cada Servicio se lee y serializa con el
    alcance de SU empresa. Los alcances son secuenciales, nunca anidados."""
    with scope.con_empresa(paquete.empresa_lider):
        filas = list(
            paquete.servicios_asociados.order_by('orden').values(
                'id', 'servicio_id', 'orden', 'dia_estancia', 'salidas', 'noches', 'personas_incluidas', 'empresa_id',
            )
        )
    por_id = {empresa.pk: empresa for empresa in empresas}
    componentes = []
    for fila in filas:
        empresa = por_id.get(fila['empresa_id'])
        if empresa is None:
            continue
        with scope.con_empresa(empresa):
            servicio = (
                Servicio.objects.filter(pk=fila['servicio_id'], empresa=empresa, activo=True)
                .prefetch_related('servicio_personalizaciones__personalizacion')
                .first()
            )
            if servicio is None:
                continue
            componentes.append({
                'id': fila['id'], 'servicio_id': fila['servicio_id'], 'orden': fila['orden'],
                'dia_estancia': fila['dia_estancia'], 'salidas': fila['salidas'], 'noches': fila['noches'],
                'personas_incluidas': fila['personas_incluidas'],
                'servicio': ServicioSerializer(servicio).data,
            })
    return componentes


def _con_componentes(datos, componentes):
    datos = dict(datos)
    datos['servicios_asociados'] = componentes
    datos['noches'] = next(
        (c['noches'] for c in componentes if c['servicio']['estrategia_cupo'] == 'por_noche'), None,
    )
    return datos


def paquetes_de_sede(sede):
    """Lista de dicts serializados de los paquetes activos liderados por cualquiera de las
    Empresas activas de la Sede, con los componentes de todas las empresas que participan."""
    empresas = _empresas_activas_de(sede)
    resultado = []
    for empresa in empresas:
        with scope.con_empresa(empresa):
            paquetes = list(
                Paquete.objects.filter(empresa_lider=empresa, activo=True)
                .select_related('sede', 'empresa_lider').order_by('nombre')
            )
            datos = [PaqueteSerializer(p, context={'sin_componentes': True}).data for p in paquetes]
        for paquete, dato in zip(paquetes, datos):
            resultado.append(_con_componentes(dato, _componentes_de(paquete, empresas)))
    return resultado


def paquete_de_sede(sede, slug):
    """Dict serializado del paquete activo con ese slug en la Sede, o None."""
    empresas = _empresas_activas_de(sede)
    for empresa in empresas:
        with scope.con_empresa(empresa):
            paquete = (
                Paquete.objects.filter(empresa_lider=empresa, slug=slug, activo=True)
                .select_related('sede', 'empresa_lider').first()
            )
            if paquete is None:
                continue
            dato = PaqueteSerializer(paquete, context={'sin_componentes': True}).data
        return _con_componentes(dato, _componentes_de(paquete, empresas))
    return None

