from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from apps.fleet.models import ExtrasItem, PuntoEncuentro, TransportePrecio

from .models import DESLINDE_VERSION, Reserva, ReservaExtra, ReservaTransporte, Vendedora
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
    zona = serializers.ChoiceField(
        choices=TransportePrecio.Zona.choices, required=False, allow_blank=True, default='',
    )


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

    # `default=` (no solo `required=False`) para que la clave siempre llegue a
    # validated_data aunque el cliente no la mande — cada envio del checkout
    # reescribe la seleccion completa, y sin el default, omitir la clave (en
    # vez de mandarla vacia) dejaria viva una seleccion vieja que ya no aplica.
    extras = serializers.PrimaryKeyRelatedField(
        queryset=ExtrasItem.objects.filter(activo=True), many=True,
        required=False, default=list, write_only=True,
    )
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
            'extras', 'transporte',
            'ref', 'estado',
        ]
        read_only_fields = ['id', 'estado']

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
        return attrs

    def save(self, **kwargs):
        # La fecha/hora e IP del deslinde se sellan aqui, en el servidor, con cada
        # envio: valen como constancia de la ultima version aceptada.
        request = self.context['request']

        # `ref` no es campo del modelo, hay que sacarlo antes de construir la
        # Reserva. Solo se atribuye cuando el codigo resuelve: si no viene ref (o
        # no sirve) se respeta lo que ya tuviera la reserva, para no borrar una
        # atribucion hecha a mano cuando el cliente reenvia el checkout.
        vendedora = Vendedora.por_codigo(self.validated_data.pop('ref', ''))

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
        return self._guardar(Reserva(**validated_data), extras, transporte)

    def update(self, instance, validated_data):
        extras, transporte = self._sacar_extras_y_transporte(validated_data)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        return self._guardar(instance, extras, transporte)

    def _sacar_extras_y_transporte(self, validated_data):
        # No son campos del modelo Reserva: hay que sacarlos antes de construirla
        # o de asignarlos con setattr, o revientan contra un atributo que no existe.
        # Con default= en los dos campos (ver arriba) siempre estan presentes.
        return validated_data.pop('extras'), validated_data.pop('transporte')

    def _guardar(self, reserva, extras, transporte):
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
        self._sincronizar_extras(reserva, extras)
        if quiere_transporte:
            self._construir_transporte(reserva, transporte).save()
        else:
            ReservaTransporte.objects.filter(reserva=reserva).delete()

        return reserva

    def _sincronizar_extras(self, reserva, items_elegidos):
        """Reescribe la seleccion completa: borra lo que ya no viene, crea lo
        que falta. Mismo criterio que el resto del checkout (cada envio
        reescribe la fila), sin precio — eso lo pone CrearPagoView al pagar."""
        ids_elegidos = {item.pk for item in items_elegidos}
        reserva.extras_seleccionados.exclude(extras_item_id__in=ids_elegidos).delete()
        ids_existentes = set(reserva.extras_seleccionados.values_list('extras_item_id', flat=True))
        ReservaExtra.objects.bulk_create([
            ReservaExtra(reserva=reserva, extras_item=item)
            for item in items_elegidos if item.pk not in ids_existentes
        ])

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
        return transporte
