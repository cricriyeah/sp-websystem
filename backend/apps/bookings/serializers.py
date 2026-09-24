from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.fleet.calendario_paquete import ComponenteCalendario, fecha_ancla, fecha_salida as calcular_salida
from apps.fleet.enums import TipoServicio, TipoTraslado
from apps.fleet.models import (
    Paquete,
    PaqueteServicio,
    Personalizacion,
    PuntoEncuentro,
    Servicio,
    ServicioPersonalizacion,
)

from .models import (
    DESLINDE_VERSION,
    DetalleTransporte,
    Reserva,
    ReservaPersonalizacion,
    Vendedora,
)
from .validators import validar_nombre_persona


class CupoSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    cupo_maximo = serializers.IntegerField()
    ocupadas = serializers.IntegerField()
    disponible = serializers.BooleanField()
    # Primera fecha con espacio PARA ESE GRUPO a partir de la pedida. Evita que el
    # navegador tenga que preguntar dia por dia (ver models.proxima_fecha_disponible).
    proxima_disponible = serializers.DateField(allow_null=True)
    # 'lleno' | 'sin_panga' | null. Sin esto el frontend no puede decir la verdad
    # de por que no se puede: "ese dia esta lleno" y "el dia tiene espacio pero ya
    # no hay panga para tu grupo" son mensajes distintos para el cliente.
    motivo_no_disponible = serializers.CharField(allow_null=True)


def ip_del_cliente(request):
    """IP para el registro del deslinde.

    `X-Forwarded-For` es una lista `cliente, proxy1, proxy2...` donde cada salto
    **agrega al final** la IP de quien le hablo. La parte izquierda la puede
    escribir el propio cliente antes de que su peticion toque nuestro proxy, asi
    que tomar la primera entrada dejaria la constancia legal del deslinde a
    merced justo de quien la firma: bastaria mandar `X-Forwarded-For: 1.2.3.4`
    para quedar registrado con una IP inventada.

    La unica posicion que el cliente no puede falsificar es la que escribio
    nuestro propio proxy, contando desde la derecha tantos saltos como proxies de
    confianza haya delante (`TRUSTED_PROXY_COUNT`: 1 en Render, 0 en local).
    Si el header viene mas corto de lo que deberia, no se adivina — se cae a
    `REMOTE_ADDR`, que es la IP de la conexion real y nadie puede inventar.
    """
    saltos = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)
    partes = [p.strip() for p in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if p.strip()]
    if saltos > 0 and len(partes) >= saltos:
        return partes[-saltos]
    return request.META.get('REMOTE_ADDR')


class PersonalizacionSeleccionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    cantidad = serializers.IntegerField(required=False, default=1, min_value=1)
    respuesta = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        trim_whitespace=False,
    )


class SlugOrNullRelatedField(serializers.SlugRelatedField):
    def to_internal_value(self, data):
        if data == '' or data is None:
            return None
        return super().to_internal_value(data)


class ReservaCheckoutSerializer(serializers.ModelSerializer):
    """Crea o actualiza la reserva de una sesion de checkout.

    Sirve para las dos cosas a proposito: mientras la reserva siga en
    `pendiente_pago`, cada envio del checkout reescribe la misma fila. Asi
    corregir la fecha o reintentar tras un error no deja reservas duplicadas.

    `personalizaciones` escribe la selección completa: el precio queda `null`
    hasta que se paga. El unico que lo congela es `CrearPagoView`, con el
    catalogo vigente en ese momento — ver
    docs/superpowers/specs/2026-08-28-extras-checkout-design.md.
    """

    checkout_id = serializers.UUIDField()

    # Codigo de la vendedora que trae el cliente en el link (?ref=). Es
    # write_only: la web lo manda, nadie lo consulta de vuelta. Un codigo
    # inexistente o de alguien dado de baja se ignora en silencio — un link
    # viejo mal copiado no puede impedir que alguien reserve.
    ref = serializers.CharField(required=False, allow_blank=True, write_only=True)

    servicio = SlugOrNullRelatedField(
        slug_field='slug', queryset=Servicio.objects.filter(activo=True), required=False, allow_null=True,
    )
    paquete = SlugOrNullRelatedField(
        slug_field='slug', queryset=Paquete.objects.filter(activo=True), required=False, allow_null=True,
    )
    fecha_salida = serializers.DateField(required=False, allow_null=True)
    personas_por_servicio = serializers.DictField(
        child=serializers.IntegerField(min_value=1), required=False,
    )
    fecha_inicio_paquete = serializers.DateField(read_only=True)
    personalizaciones = PersonalizacionSeleccionSerializer(
        many=True, required=False, default=list, write_only=True,
    )

    class Meta:
        model = Reserva
        fields = [
            'id', 'checkout_id', 'fecha', 'hora', 'numero_personas',
            'nombre_cliente', 'telefono_cliente', 'correo_cliente',
            'moneda', 'deslinde_aceptado', 'deslinde_nombre',
            'pide_bebidas',
            'servicio', 'paquete', 'fecha_salida',
            'personas_por_servicio', 'fecha_inicio_paquete',
            'personalizaciones',
            'ref', 'estado',
        ]
        read_only_fields = ['id', 'estado']

    def get_fields(self):
        fields = super().get_fields()
        empresa = self.context.get('empresa')
        if empresa:
            fields['servicio'].queryset = Servicio.objects.filter(activo=True, empresa=empresa)
            fields['paquete'].queryset = Paquete.objects.filter(activo=True, empresa_lider=empresa)
        return fields

    def validate_deslinde_aceptado(self, value):
        # Sin casilla marcada no hay reserva (ver docs/contexto-negocio.md, Legal).
        if not value:
            raise serializers.ValidationError('Debes aceptar el deslinde de responsabilidad.')
        return value

    def validate_deslinde_nombre(self, value):
        if not value.strip():
            raise serializers.ValidationError('Escribe tu nombre para aceptar el deslinde.')
        # Mismo criterio que `nombre_cliente`: esto es constancia legal, y un
        # deslinde firmado como "12345" no acredita a nadie. El campo del modelo
        # es `blank=True` (las reservas por WhatsApp no lo llevan), asi que la
        # regla se aplica aqui, donde ya se sabe que viene con contenido.
        try:
            validar_nombre_persona(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return value.strip()

    def validate(self, attrs):
        # Una reserva que ya se pago no se toca desde la web: el cupo, el cobro y
        # la asignacion dependen de esos datos.
        if self.instance and self.instance.estado != Reserva.Estado.PENDIENTE_PAGO:
            raise serializers.ValidationError('Esta reserva ya no se puede modificar.')

        empresa = self.context.get('empresa')

        servicio = attrs.get('servicio')
        if servicio is None and self.instance and 'servicio' not in attrs:
            servicio = self.instance.servicio

        paquete = attrs.get('paquete')
        if paquete is None and self.instance and 'paquete' not in attrs:
            paquete = self.instance.paquete

        if servicio and paquete:
            raise serializers.ValidationError('No puedes especificar servicio y paquete al mismo tiempo.')

        if paquete and empresa and paquete.empresa_lider_id != empresa.id:
            raise serializers.ValidationError({'paquete': 'El paquete no pertenece a esta empresa.'})

        if servicio and empresa and servicio.empresa_id != empresa.id:
            raise serializers.ValidationError({'servicio': 'El servicio no pertenece a esta empresa.'})

        personalizaciones = attrs.get('personalizaciones', [])

        es_servicio_personalizable = bool(
            servicio and not paquete
        )
        if personalizaciones and not paquete and not es_servicio_personalizable:
            raise serializers.ValidationError({
                'personalizaciones': 'Las personalizaciones todavía no aplican a este servicio.',
            })

        if es_servicio_personalizable:
            disponibles = {
                sp.pk: sp
                for sp in ServicioPersonalizacion.objects.filter(
                    servicio=servicio,
                    servicio__empresa=empresa,
                    personalizacion__empresa=empresa,
                    activo=True,
                    personalizacion__activo=True,
                ).select_related('personalizacion', 'servicio')
            }
            vistos = set()
            for item in personalizaciones:
                sp = disponibles.get(item['id'])
                if sp is None or item['id'] in vistos:
                    raise serializers.ValidationError({
                        'personalizaciones': 'Selección inválida o repetida.',
                    })
                vistos.add(sp.pk)
                self._validar_respuesta_personalizacion(sp, item)
            for sp in disponibles.values():
                if (
                    sp.personalizacion.tipo_interaccion != 'check'
                    and sp.obligatorio
                    and sp.pk not in vistos
                ):
                    raise serializers.ValidationError({
                        'personalizaciones': f'Falta responder: {sp.personalizacion.nombre}.',
                    })

        componentes_activos = []
        if paquete:
            componentes_activos = list(
                paquete.servicios_asociados.filter(servicio__activo=True).select_related('servicio').order_by('orden')
            )
            activos_ids = {ps.servicio_id for ps in componentes_activos}
            disponibles = {
                sp.pk: sp
                for sp in ServicioPersonalizacion.objects.filter(
                    servicio_id__in=activos_ids,
                    servicio__empresa=empresa,
                    personalizacion__empresa=empresa,
                    activo=True,
                    personalizacion__activo=True,
                ).select_related('personalizacion', 'servicio')
            }
            vistos = set()
            for item in personalizaciones:
                sp = disponibles.get(item['id'])
                if sp is None or item['id'] in vistos:
                    raise serializers.ValidationError({
                        'personalizaciones': 'Selección inválida o repetida.',
                    })
                vistos.add(sp.pk)
                self._validar_respuesta_personalizacion(sp, item)
            for sp in disponibles.values():
                if (
                    sp.personalizacion.tipo_interaccion != 'check'
                    and sp.obligatorio
                    and sp.pk not in vistos
                ):
                    raise serializers.ValidationError({
                        'personalizaciones': f'Falta responder: {sp.personalizacion.nombre}.',
                    })

        fecha = attrs.get('fecha', getattr(self.instance, 'fecha_inicio_paquete', None) if self.instance else None)
        fecha_salida_cliente = attrs.get('fecha_salida')

        if paquete:
            # El paquete define noches, día de cada servicio y lugares incluidos: el
            # cliente solo elige el inicio y cuántas personas van a cada servicio.
            if paquete.es_cruza_empresa:
                raise serializers.ValidationError({
                    'paquete': 'Este paquete es de dos empresas y se reserva como orden, no como reserva.',
                })
            try:
                paquete.validar_configuracion()
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'paquete': exc.messages})
            if fecha_salida_cliente:
                raise serializers.ValidationError({'fecha_salida': 'La fecha de salida la define el paquete.'})
            attrs = self._derivar_de_paquete(attrs, fecha, componentes_activos)
        else:
            es_hospedaje = bool(servicio and servicio.estrategia_cupo == 'por_noche')
            fecha_salida = attrs.get('fecha_salida', getattr(self.instance, 'fecha_salida', None) if self.instance else None)
            if es_hospedaje:
                if not fecha_salida:
                    raise serializers.ValidationError({'fecha_salida': 'La fecha de salida es requerida para servicios con hospedaje.'})
                if fecha and fecha_salida <= fecha:
                    raise serializers.ValidationError({'fecha_salida': 'La fecha de salida debe ser posterior a la fecha de llegada.'})
            elif fecha_salida:
                raise serializers.ValidationError({'fecha_salida': 'La fecha de salida solo aplica para servicios con hospedaje.'})

        if not paquete:
            numero_personas = attrs.get('numero_personas', getattr(self.instance, 'numero_personas', None) if self.instance else None)
            if numero_personas and servicio:
                recursos_activos = servicio.recursos.filter(activo=True)
                if recursos_activos.exists():
                    cap_max = max(r.capacidad_maxima for r in recursos_activos)
                    if numero_personas > cap_max:
                        raise serializers.ValidationError({
                            'numero_personas': f'El número de personas ({numero_personas}) supera la capacidad máxima ({cap_max}).'
                        })

        return attrs

    def _derivar_de_paquete(self, attrs, inicio, componentes):
        if inicio is None:
            raise serializers.ValidationError({'fecha': 'Elige la fecha de inicio del paquete.'})
        personas = attrs.get('personas_por_servicio', {})
        esperadas = {str(ps.servicio_id): ps for ps in componentes}
        if set(personas) != set(esperadas):
            raise serializers.ValidationError({
                'personas_por_servicio': 'Indica cuántas personas van a cada servicio del paquete.',
            })
        for clave, ps in esperadas.items():
            if personas[clave] > ps.personas_incluidas:
                raise serializers.ValidationError({
                    'personas_por_servicio': (
                        f'"{ps.servicio.nombre}" incluye {ps.personas_incluidas} lugar(es) en este paquete.'
                    ),
                })
            if ps.servicio.estrategia_cupo == 'por_noche':
                habitaciones = ps.servicio.recursos.filter(activo=True)
                if habitaciones.exists() and personas[clave] > max(r.capacidad_maxima for r in habitaciones):
                    raise serializers.ValidationError({
                        'personas_por_servicio': f'Ninguna habitación de "{ps.servicio.nombre}" admite {personas[clave]} personas.',
                    })

        # El motor de cupo cuenta `numero_personas` (las del componente principal) para todas las
        # actividades del día; por eso todas las actividades del paquete van con el mismo número.
        actividades = {
            personas[str(ps.servicio_id)] for ps in componentes if ps.servicio.estrategia_cupo == 'por_recurso_dia'
        }
        if len(actividades) > 1:
            raise serializers.ValidationError({
                'personas_por_servicio': 'Las actividades del paquete van con el mismo número de personas.',
            })

        calendario = [
            ComponenteCalendario(ps.dia_estancia, ps.servicio.estrategia_cupo, ps.noches) for ps in componentes
        ]
        principal = next(
            (ps for ps in componentes if ps.servicio.estrategia_cupo == 'por_recurso_dia'),
            componentes[0] if componentes else None,
        )
        attrs['fecha'] = fecha_ancla(inicio, calendario)
        attrs['inicio_paquete'] = inicio
        attrs['fecha_salida'] = calcular_salida(inicio, calendario)
        if principal is not None:
            attrs['numero_personas'] = personas[str(principal.servicio_id)]
        return attrs

    def _validar_respuesta_personalizacion(self, sp, item):
        fila = ReservaPersonalizacion(
            servicio_personalizacion=sp,
            cantidad=item.get('cantidad', 1),
            respuesta=item.get('respuesta', ''),
        )
        try:
            fila.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'personalizaciones': exc.messages})

    def save(self, **kwargs):
        # La fecha/hora e IP del deslinde se sellan aqui, en el servidor, con cada
        # envio: valen como constancia de la ultima version aceptada.
        request = self.context['request']

        # `ref` no es campo del modelo, hay que sacarlo antes de construir la
        # Reserva. Solo se atribuye cuando el codigo resuelve: si no viene ref (o
        # no sirve) se respeta lo que ya tuviera la reserva, para no borrar una
        # atribucion hecha a mano cuando el cliente reenvia el checkout.
        vendedora = Vendedora.por_codigo(self.validated_data.pop('ref', ''), self.context['empresa'])

        return super().save(
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado_en=timezone.now(),
            deslinde_ip=ip_del_cliente(request),
            # La version la pone el servidor y no el cliente: una constancia que
            # el propio firmante puede elegir no acredita nada.
            deslinde_version=DESLINDE_VERSION,
            **({'vendedora': vendedora} if vendedora else {}),
            **kwargs,
        )

    def create(self, validated_data):
        personalizaciones = self._sacar_datos_paquete(validated_data)
        # La Empresa la fija la vista (slug de la URL), nunca el payload del
        # cliente. `update()` no la toca: recuperar un checkout conserva su
        # Empresa (y seria la misma, resuelta del mismo slug).
        validated_data['empresa'] = self.context['empresa']
        return self._guardar(Reserva(**validated_data), personalizaciones)

    def update(self, instance, validated_data):
        personalizaciones = self._sacar_datos_paquete(validated_data)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        return self._guardar(instance, personalizaciones)

    def _sacar_datos_paquete(self, validated_data):
        return validated_data.pop('personalizaciones', [])

    def _guardar(self, reserva, personalizaciones):
        # full_clean corre el motor unico de validacion (ventana de salida, cupo,
        # deslinde, capacidad), ver apps/bookings/models.py y backend/CLAUDE.md.
        try:
            with transaction.atomic():
                reserva.full_clean()
                reserva.save()

                # Cada envio reescribe la seleccion completa, sin excepciones:
                # una lista vacia borra lo que hubiera.
                self._sincronizar_personalizaciones(reserva, personalizaciones)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            )

        return reserva

    def _sincronizar_personalizaciones(self, reserva, items_elegidos):
        reserva.personalizaciones_seleccionadas.all().delete()
        aplica = reserva.paquete_id or reserva.servicio_id
        if not aplica or not items_elegidos:
            return
        for item in items_elegidos:
            respuesta = item.get('respuesta', '')
            sp = ServicioPersonalizacion.objects.select_related('personalizacion').get(
                pk=item['id'],
            )
            if sp.personalizacion.tipo_interaccion != 'check' and not respuesta.strip():
                continue
            fila = ReservaPersonalizacion(
                reserva=reserva,
                servicio_personalizacion=sp,
                cantidad=item.get('cantidad', 1),
                respuesta=respuesta,
            )
            fila.full_clean()
            fila.save()

class TrasladoCheckoutSerializer(ReservaCheckoutSerializer):
    """Checkout de transporte; comparte atribucion y constancia legal del checkout."""

    servicio = serializers.SlugRelatedField(slug_field='slug', queryset=Servicio.objects.none())
    deslinde_aceptado = serializers.BooleanField(required=True)
    deslinde_nombre = serializers.CharField(required=True, max_length=150)
    forma_pago = serializers.ChoiceField(choices=Reserva.FormaPago.choices)
    tipo_traslado = serializers.ChoiceField(
        choices=TipoTraslado.choices, source='detalle_transporte.tipo_traslado',
    )
    punto_encuentro = serializers.PrimaryKeyRelatedField(
        queryset=PuntoEncuentro.objects.none(), required=False, allow_null=True,
        default=None, source='detalle_transporte.punto_encuentro',
    )
    direccion_personalizada = serializers.CharField(
        required=False, allow_blank=True, default='', max_length=255,
        source='detalle_transporte.direccion_personalizada',
    )
    zona = serializers.CharField(
        required=False, allow_blank=True, default='', source='detalle_transporte.zona',
    )
    fecha_regreso = serializers.DateField(
        required=False, allow_null=True, default=None, source='detalle_transporte.fecha_regreso',
    )

    class Meta(ReservaCheckoutSerializer.Meta):
        fields = [
            'id', 'checkout_id', 'servicio', 'tipo_traslado', 'punto_encuentro',
            'direccion_personalizada', 'zona', 'fecha', 'hora', 'fecha_regreso',
            'numero_personas', 'nombre_cliente', 'telefono_cliente', 'correo_cliente',
            'deslinde_aceptado', 'deslinde_nombre', 'moneda', 'forma_pago', 'ref', 'estado',
        ]

    def get_fields(self):
        fields = serializers.ModelSerializer.get_fields(self)
        empresa = self.context['empresa']
        fields['servicio'].queryset = Servicio.objects.filter(
            empresa=empresa, activo=True, tipo_servicio=TipoServicio.TRANSPORTE,
        )
        fields['punto_encuentro'].queryset = PuntoEncuentro.objects.filter(empresa=empresa, activo=True)
        return fields

    def create(self, validated_data):
        detalle_data = validated_data.pop('detalle_transporte')
        reserva = Reserva(empresa=self.context['empresa'], **validated_data)
        return self._guardar_traslado(reserva, detalle_data)

    def update(self, instance, validated_data):
        detalle_data = validated_data.pop('detalle_transporte')
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        return self._guardar_traslado(instance, detalle_data)

    @transaction.atomic
    def _guardar_traslado(self, reserva, detalle_data):
        punto = detalle_data['punto_encuentro']
        if punto:
            detalle_data['zona'] = punto.zona
        detalle = DetalleTransporte.objects.filter(reserva=reserva).first() if reserva.pk else None
        if detalle is None:
            detalle = DetalleTransporte(reserva=reserva)
        for campo, valor in detalle_data.items():
            setattr(detalle, campo, valor)
        try:
            reserva.full_clean()
            reserva.save()
            # La FK requiere una reserva persistida; atomic revierte ambas si falla.
            detalle.reserva = reserva
            detalle.full_clean()
            detalle.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            )
        return reserva
