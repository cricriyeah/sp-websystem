from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from apps.fleet.models import (
    ExtrasItem,
    Paquete,
    PaqueteServicio,
    Personalizacion,
    PuntoEncuentro,
    Servicio,
    ServicioPersonalizacion,
    TransportePrecio,
)

from .models import (
    DESLINDE_VERSION,
    Reserva,
    ReservaExtra,
    ReservaPaquetePersonalizacion,
    ReservaPaqueteServicioRemovido,
    ReservaTransporte,
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


class TransporteSeleccionSerializer(serializers.Serializer):
    """Lo que el cliente elige en el paso de Extras, sin precio: el precio lo
    congela `CrearPagoView` al pagar, con el catalogo vigente en ese momento.

    `zona` es lo que manda el cliente solo cuando eligio "otra direccion" —
    si viene `punto_encuentro`, `ReservaCheckoutSerializer` la ignora y usa
    `punto_encuentro.zona`, para que nadie pueda pagar el precio de una zona
    mas barata mandando una `zona` que no corresponde al hotel elegido.
    """

    punto_encuentro = serializers.PrimaryKeyRelatedField(
        queryset=PuntoEncuentro.objects.filter(activo=True), required=False, allow_null=True, default=None,
    )
    direccion_personalizada = serializers.CharField(required=False, allow_blank=True, default='')

    def get_fields(self):
        # El queryset del PrimaryKeyRelatedField se evalua al importar el modulo
        # (cuerpo de clase del serializer padre), sin contexto. `get_fields()` es
        # el unico gancho de DRF que corre por-peticion con `self.context` puesto
        # (`__init__` no vuelve a correr tras el `deepcopy` del padre).
        fields = super().get_fields()
        fields['punto_encuentro'].queryset = PuntoEncuentro.objects.filter(
            activo=True, empresa=self.context['empresa'],
        )
        return fields
    zona = serializers.ChoiceField(
        choices=TransportePrecio.Zona.choices, required=False, allow_blank=True, default='',
    )
    # Cuantas personas del grupo usan el transporte. None = todo el grupo (de
    # siempre). El cargo real (y si aplica el recargo de grupo) lo decide
    # CrearPagoView con el numero de personas ya acotado a la reserva.
    cantidad = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1)


class ExtraSeleccionSerializer(serializers.Serializer):
    """Un item del catalogo que el cliente marco, con cuantas personas lo
    necesitan si el item tiene `cantidad_editable` (ver fleet.ExtrasItem) —
    el backend ignora `cantidad` en los demas. None = todo el grupo."""

    id = serializers.PrimaryKeyRelatedField(queryset=ExtrasItem.objects.filter(activo=True))
    cantidad = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=1)

    def get_fields(self):
        # Ver la nota en TransporteSeleccionSerializer.get_fields.
        fields = super().get_fields()
        fields['id'].queryset = ExtrasItem.objects.filter(activo=True, empresa=self.context['empresa'])
        return fields


class PersonalizacionSeleccionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    cantidad = serializers.IntegerField(required=False, default=1, min_value=1)


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

    `extras`/`transporte` solo escriben la SELECCION (que items, que punto de
    encuentro): el precio queda `null` hasta que se paga. El unico que lo
    congela es `CrearPagoView`, con el catalogo vigente en ese momento — ver
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
    servicios_removidos = serializers.ListField(
        child=serializers.SlugField(), required=False, default=list, write_only=True,
    )
    personalizaciones = PersonalizacionSeleccionSerializer(
        many=True, required=False, default=list, write_only=True,
    )

    # `default=` (no solo `required=False`) para que la clave siempre llegue a
    # validated_data aunque el cliente no la mande — cada envio del checkout
    # reescribe la seleccion completa, y sin el default, omitir la clave (en
    # vez de mandarla vacia) dejaria viva una seleccion vieja que ya no aplica.
    extras = ExtraSeleccionSerializer(many=True, required=False, default=list, write_only=True)
    transporte = TransporteSeleccionSerializer(
        required=False, allow_null=True, default=None, write_only=True,
    )

    class Meta:
        model = Reserva
        fields = [
            'id', 'checkout_id', 'fecha', 'hora', 'numero_personas',
            'nombre_cliente', 'telefono_cliente', 'correo_cliente',
            'moneda', 'deslinde_aceptado', 'deslinde_nombre',
            'pide_bebidas',
            'servicio', 'paquete', 'fecha_salida',
            'servicios_removidos', 'personalizaciones',
            'extras', 'transporte',
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

        servicios_removidos = attrs.get('servicios_removidos', [])
        personalizaciones = attrs.get('personalizaciones', [])

        if servicios_removidos and not paquete:
            raise serializers.ValidationError({'servicios_removidos': 'Los servicios removidos solo aplican para paquetes.'})

        if personalizaciones and not paquete:
            raise serializers.ValidationError({'personalizaciones': 'Las personalizaciones solo aplican para paquetes.'})

        componentes_activos = []
        if paquete:
            servicios_asociados = list(paquete.servicios_asociados.select_related('servicio').all())
            removibles_map = {ps.servicio.slug: ps for ps in servicios_asociados if ps.removible}
            todos_servicios_map = {ps.servicio.slug: ps for ps in servicios_asociados}

            for slug in servicios_removidos:
                if slug not in removibles_map:
                    if slug in todos_servicios_map:
                        raise serializers.ValidationError({'servicios_removidos': f'El servicio {slug} no es removible.'})
                    else:
                        raise serializers.ValidationError({'servicios_removidos': f'El servicio {slug} no pertenece al paquete.'})

            removidos_set = set(servicios_removidos)
            componentes_activos = [ps for ps in servicios_asociados if ps.servicio.slug not in removidos_set]

            if personalizaciones:
                activos_ids = {ps.servicio_id for ps in componentes_activos}
                vistos_ids = set()
                for item in personalizaciones:
                    sp_id = item['id']
                    if sp_id in vistos_ids:
                        raise serializers.ValidationError({'personalizaciones': 'No se puede repetir la misma personalización.'})
                    vistos_ids.add(sp_id)

                    try:
                        sp = ServicioPersonalizacion.objects.select_related('personalizacion', 'servicio').get(id=sp_id)
                    except ServicioPersonalizacion.DoesNotExist:
                        raise serializers.ValidationError({'personalizaciones': f'La personalización {sp_id} no existe.'})

                    if not sp.activo or not sp.personalizacion.activo:
                        raise serializers.ValidationError({'personalizaciones': f'La personalización {sp_id} no está activa.'})

                    if sp.servicio_id not in activos_ids:
                        raise serializers.ValidationError(
                            {'personalizaciones': f'La personalización {sp_id} no pertenece a un componente activo del paquete.'}
                        )

                    if sp.obligatorio or sp.preseleccionado:
                        raise serializers.ValidationError(
                            {'personalizaciones': f'La personalización {sp_id} no es opcional (las obligatorias y preseleccionadas van incluidas).'}
                        )

        es_hospedaje = bool((servicio and servicio.estrategia_cupo == 'por_noche') or any(
            ps.servicio.estrategia_cupo == 'por_noche' for ps in componentes_activos
        ))

        fecha = attrs.get('fecha', getattr(self.instance, 'fecha', None) if self.instance else None)
        fecha_salida = attrs.get('fecha_salida', getattr(self.instance, 'fecha_salida', None) if self.instance else None)

        if es_hospedaje:
            if not fecha_salida:
                raise serializers.ValidationError({'fecha_salida': 'La fecha de salida es requerida para servicios con hospedaje.'})
            if fecha and fecha_salida <= fecha:
                raise serializers.ValidationError({'fecha_salida': 'La fecha de salida debe ser posterior a la fecha de llegada.'})
        else:
            if fecha_salida:
                raise serializers.ValidationError({'fecha_salida': 'La fecha de salida solo aplica para servicios con hospedaje.'})

        numero_personas = attrs.get('numero_personas', getattr(self.instance, 'numero_personas', None) if self.instance else None)
        if numero_personas:
            servicio_dominante = None
            if servicio:
                servicio_dominante = servicio
            elif paquete:
                ps_dom = paquete.servicios_asociados.filter(removible=False).order_by('orden').first() or paquete.servicios_asociados.order_by('orden').first()
                if ps_dom:
                    servicio_dominante = ps_dom.servicio

            if servicio_dominante:
                recursos_activos = servicio_dominante.recursos.filter(activo=True)
                if recursos_activos.exists():
                    cap_max = max(r.capacidad_maxima for r in recursos_activos)
                    if numero_personas > cap_max:
                        raise serializers.ValidationError({
                            'numero_personas': f'El número de personas ({numero_personas}) supera la capacidad máxima ({cap_max}).'
                        })

        return attrs

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
        extras, transporte = self._sacar_extras_y_transporte(validated_data)
        servicios_removidos, personalizaciones = self._sacar_datos_paquete(validated_data)
        # La Empresa la fija la vista (slug de la URL), nunca el payload del
        # cliente. `update()` no la toca: recuperar un checkout conserva su
        # Empresa (y seria la misma, resuelta del mismo slug).
        validated_data['empresa'] = self.context['empresa']
        return self._guardar(Reserva(**validated_data), extras, transporte, servicios_removidos, personalizaciones)

    def update(self, instance, validated_data):
        extras, transporte = self._sacar_extras_y_transporte(validated_data)
        servicios_removidos, personalizaciones = self._sacar_datos_paquete(validated_data)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        return self._guardar(instance, extras, transporte, servicios_removidos, personalizaciones)

    def _sacar_extras_y_transporte(self, validated_data):
        # No son campos del modelo Reserva: hay que sacarlos antes de construirla
        # o de asignarlos con setattr, o revientan contra un atributo que no existe.
        # Con default= en los dos campos (ver arriba) siempre estan presentes.
        return validated_data.pop('extras'), validated_data.pop('transporte')

    def _sacar_datos_paquete(self, validated_data):
        return validated_data.pop('servicios_removidos', []), validated_data.pop('personalizaciones', [])

    def _guardar(self, reserva, extras, transporte, servicios_removidos=None, personalizaciones=None):
        # full_clean corre el motor unico de validacion (ventana de salida, cupo,
        # deslinde, capacidad), ver apps/bookings/models.py y backend/CLAUDE.md.
        # `transporte` puede llegar como `{}` (el cliente manda siempre la forma
        # completa, con el toggle apagado) o como `None`/ausente — los dos
        # significan "sin transporte", ninguno de los dos alcanza a construir
        # una fila valida (punto_encuentro y direccion_personalizada vacios).
        quiere_transporte = bool(transporte and (
            transporte.get('punto_encuentro') or transporte.get('direccion_personalizada')
        ))

        try:
            reserva.full_clean()
            if quiere_transporte:
                # exclude=['reserva']: al crear, la Reserva todavia no tiene pk
                # (se guarda mas abajo) y el FK saldria vacio en esta validacion
                # previa — no es dato que el cliente mande, no hace falta validarlo.
                self._construir_transporte(reserva, transporte).full_clean(exclude=['reserva'])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            )

        reserva.save()

        # Cada envio reescribe la seleccion completa, sin excepciones: una lista
        # vacia borra lo que hubiera, sin transporte borra el traslado.
        # `_sincronizar_extras` corre despues de `reserva.save()` (necesita el pk),
        # asi que no entra al `try` de arriba; se envuelve aparte para que un
        # ValidationError de `ReservaExtra.clean()` (red de seguridad cross-empresa)
        # salga como 400 y no como 500 en una ruta publica.
        try:
            self._sincronizar_extras(reserva, extras)
            if quiere_transporte:
                self._construir_transporte(reserva, transporte).save()
            else:
                ReservaTransporte.objects.filter(reserva=reserva).delete()
            if servicios_removidos is not None:
                self._sincronizar_servicios_removidos(reserva, servicios_removidos)
            if personalizaciones is not None:
                self._sincronizar_personalizaciones(reserva, personalizaciones)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            )

        return reserva

    def _sincronizar_servicios_removidos(self, reserva, slugs_removidos):
        reserva.servicios_removidos.all().delete()
        if not reserva.paquete_id or not slugs_removidos:
            return
        servicios = {
            ps.servicio.slug: ps.servicio
            for ps in reserva.paquete.servicios_asociados.select_related('servicio').all()
        }
        for slug in slugs_removidos:
            srv = servicios.get(slug)
            if srv:
                ReservaPaqueteServicioRemovido.objects.create(reserva=reserva, servicio=srv)

    def _sincronizar_personalizaciones(self, reserva, items_elegidos):
        reserva.paquete_personalizaciones.all().delete()
        if not reserva.paquete_id or not items_elegidos:
            return
        for item in items_elegidos:
            ReservaPaquetePersonalizacion.objects.create(
                reserva=reserva,
                servicio_personalizacion_id=item['id'],
                cantidad=item.get('cantidad', 1),
            )

    def _sincronizar_extras(self, reserva, items_elegidos):
        """Reescribe la seleccion completa: borra lo que ya no viene, crea lo
        que falta. Mismo criterio que el resto del checkout (cada envio
        reescribe la fila), sin precio — eso lo pone CrearPagoView al pagar.

        `items_elegidos` es una lista de `{'id': ExtrasItem, 'cantidad': int|None}`
        (ver `ExtraSeleccionSerializer`). `cantidad` se guarda en
        `cantidad_solicitada` incluso si el item no es `cantidad_editable` — no
        hace daño guardarla, CrearPagoView solo la lee cuando el catalogo la
        habilita — pero nunca se toca `precio_unitario`/`cantidad`, esos son
        exclusivos de CrearPagoView.

        No basta con crear lo que falta: si el cliente ya habia marcado un
        extra y solo cambia la cantidad en un reenvio del checkout, la fila
        existente debe actualizarse tambien, o el cambio se perderia en
        silencio."""
        ids_elegidos = {dato['id'].pk for dato in items_elegidos}
        reserva.extras_seleccionados.exclude(extras_item_id__in=ids_elegidos).delete()

        existentes = {
            extra.extras_item_id: extra
            for extra in reserva.extras_seleccionados.all()
        }
        for dato in items_elegidos:
            item, cantidad = dato['id'], dato['cantidad']
            extra = existentes.get(item.pk)
            if extra is None:
                nuevo = ReservaExtra(reserva=reserva, extras_item=item, cantidad_solicitada=cantidad)
                nuevo.full_clean()
                nuevo.save()
            elif extra.cantidad_solicitada != cantidad:
                extra.cantidad_solicitada = cantidad
                extra.save(update_fields=['cantidad_solicitada'])

    def _construir_transporte(self, reserva, datos):
        """No guarda: full_clean() se llama antes de tocar la base (junto al
        de la Reserva), guardar es responsabilidad de quien llama despues."""
        transporte = None
        if reserva.pk:
            # Sin pk (reserva nueva, aun no guardada) no hay relacion que
            # consultar: el descriptor de Django exige un pk para buscarla.
            try:
                transporte = reserva.transporte
            except ReservaTransporte.DoesNotExist:
                transporte = None
        if transporte is None:
            transporte = ReservaTransporte(reserva=reserva)

        punto_encuentro = datos.get('punto_encuentro')
        transporte.punto_encuentro = punto_encuentro
        transporte.direccion_personalizada = '' if punto_encuentro else datos.get('direccion_personalizada', '')
        # Nunca la que mande el cliente si eligio un hotel del catalogo: se
        # deriva de ahi, o alguien podria pagar el precio de otra zona.
        transporte.zona = punto_encuentro.zona if punto_encuentro else datos.get('zona', '')
        # Cuantas personas del grupo lo usan. None = todo el grupo (de siempre);
        # CrearPagoView es quien la acota al numero de personas real y la congela.
        transporte.personas_solicitadas = datos.get('cantidad')
        return transporte
