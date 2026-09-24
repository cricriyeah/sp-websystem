from decimal import Decimal
from rest_framework import serializers

from .models import (
    Paquete,
    PaqueteServicio,
    Personalizacion,
    PuntoEncuentro,
    Recurso,
    Servicio,
    ServicioPersonalizacion,
)


class PuntoEncuentroSerializer(serializers.ModelSerializer):
    class Meta:
        model = PuntoEncuentro
        fields = ['id', 'nombre', 'zona']


class ServicioPersonalizacionSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source='personalizacion.nombre', read_only=True)
    tipo = serializers.CharField(source='personalizacion.tipo', read_only=True)
    tipo_interaccion = serializers.CharField(source='personalizacion.tipo_interaccion', read_only=True)
    opciones_seleccion = serializers.JSONField(source='personalizacion.opciones_seleccion', read_only=True)
    aviso_reforzado = serializers.BooleanField(source='personalizacion.aviso_reforzado', read_only=True)
    cobrar_por_persona = serializers.BooleanField(source='personalizacion.cobrar_por_persona', read_only=True)
    cantidad_editable = serializers.BooleanField(source='personalizacion.cantidad_editable', read_only=True)

    class Meta:
        model = ServicioPersonalizacion
        fields = [
            'id', 'personalizacion_id', 'nombre', 'tipo',
            'tipo_interaccion', 'opciones_seleccion', 'aviso_reforzado',
            'cobrar_por_persona', 'cantidad_editable',
            'precio', 'precio_usd', 'obligatorio', 'preseleccionado',
        ]


class ServicioSerializer(serializers.ModelSerializer):
    empresa_slug = serializers.CharField(source='empresa.slug', read_only=True)
    personalizaciones = serializers.SerializerMethodField()

    class Meta:
        model = Servicio
        fields = [
            'id', 'empresa_slug', 'nombre', 'slug', 'tipo_servicio',
            'estrategia_cupo', 'estrategia_precio', 'modo_ocupacion',
            'precio_base', 'precio_base_usd',
            'permite_anticipo', 'porcentaje_anticipo',
            'precio_persona_extra', 'precio_persona_extra_usd',
            'personas_incluidas', 'descripcion', 'activo',
            'personalizaciones',
        ]

    def get_personalizaciones(self, obj):
        qs = obj.servicio_personalizaciones.filter(activo=True, personalizacion__activo=True)
        return ServicioPersonalizacionSerializer(qs, many=True).data


class PaqueteServicioSerializer(serializers.ModelSerializer):
    servicio = ServicioSerializer(read_only=True)

    class Meta:
        model = PaqueteServicio
        fields = [
            'id', 'servicio_id', 'servicio', 'orden',
            'dia_estancia', 'noches', 'personas_incluidas',
        ]


class PaqueteSerializer(serializers.ModelSerializer):
    sede = serializers.CharField(source='sede.nombre', read_only=True)
    sede_slug = serializers.CharField(source='sede.slug', read_only=True)
    empresa_lider = serializers.CharField(source='empresa_lider.nombre', read_only=True)
    empresa_lider_slug = serializers.CharField(source='empresa_lider.slug', read_only=True)
    servicios_asociados = serializers.SerializerMethodField()
    permite_anticipo = serializers.SerializerMethodField()
    es_cruza_empresa = serializers.SerializerMethodField()
    noches = serializers.SerializerMethodField()

    class Meta:
        model = Paquete
        fields = [
            'id', 'sede', 'sede_slug', 'empresa_lider', 'empresa_lider_slug',
            'nombre', 'slug', 'descripcion',
            'precio_ancla', 'precio_ancla_usd', 'regla_precio', 'activo',
            'permite_anticipo', 'porcentaje_anticipo', 'es_cruza_empresa',
            'servicios_asociados', 'noches',
        ]

    def get_permite_anticipo(self, obj):
        return obj.anticipo_disponible

    def get_es_cruza_empresa(self, obj):
        # Una consulta por paquete; aceptable para las listas cortas del catálogo.
        return obj.es_cruza_empresa

    def get_noches(self, obj):
        if self.context.get('sin_componentes'):
            return None  # el catálogo lo completa con los componentes que arma él (catalogo.py)
        return obj.noches

    def get_servicios_asociados(self, obj):
        if self.context.get('sin_componentes'):
            return []  # componentes de otras empresas no se pueden leer desde aquí (RLS)
        qs = obj.servicios_asociados.filter(servicio__activo=True).order_by('orden')
        return PaqueteServicioSerializer(qs, many=True).data

