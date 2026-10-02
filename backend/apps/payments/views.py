from decimal import Decimal
import logging
import uuid

import stripe
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Reserva, codigo_promocional_valido, evaluar_codigo_promocional
from apps.fleet.enums import EstrategiaPrecio
from apps.fleet.models import CodigoPromocional
from apps.tenancy import scope

from .estrategias_precio import DemandaPrecio, demanda_traslado, obtener_estrategia_precio
from .extras import congelar_personalizaciones, cotizar_personalizaciones
from .ordenes import ORDEN_TIMEOUT_AUTORIZACION, OrdenCerradaError
from .pricing import (
    a_centavos,
    cargo_por_descuento,
    monto_inicial,
    precio_paquete_total,
)
from .stripe_client import configurar_stripe
from .services import aplicar_disputa, aplicar_pago_exitoso, aplicar_reembolso
from .situacion import Situacion

logger = logging.getLogger(__name__)

INTENT_REUTILIZABLE = {'requires_payment_method', 'requires_confirmation', 'requires_action'}
INTENT_YA_COBRANDO = {'succeeded', 'processing'}


class PagoEnCurso(Exception):
    """El intent de la reserva ya esta cobrando o cobro: no se crea otro."""


class CrearPagoView(APIView):
    """Crea (o reutiliza) el PaymentIntent de Stripe de una reserva, con las
    llaves de la Empresa resuelta por `empresa_slug` en la URL.

    El monto se calcula aqui — tarifa en la moneda de la reserva + amenidades +
    100%/30% — y nunca se confia el total que manda el cliente. Cuenta estandar
    de Stripe, no Connect (ver docs/contexto-negocio.md).

    Es idempotente a proposito: darle dos veces a "Ir a pagar", recargar el
    checkout o cambiar de amenidades reusa el mismo intent en vez de dejar
    intents sueltos que podrian terminar cobrando dos veces.
    """

    throttle_scope = 'pagos'

    def post(self, request, empresa_slug, pk):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            return self._post(request, empresa, pk)

    def _post(self, request, empresa, pk):
        reserva = get_object_or_404(Reserva, pk=pk, empresa=empresa)

        # Los ids de reserva son consecutivos y la API es publica: sin esto,
        # cualquiera podria adivinar un id y generar cobros sobre la reserva de
        # otra persona. El checkout_id lo genera el navegador del cliente.
        if not reserva.checkout_id or str(reserva.checkout_id) != str(request.data.get('checkout_id')):
            return Response({'detail': 'checkout_id invalido para esta reserva.'}, status=403)

        if reserva.estado != Reserva.Estado.PENDIENTE_PAGO:
            return Response({'detail': 'Esta reserva ya no esta pendiente de pago.'}, status=409)

        if reserva.moneda == Reserva.Moneda.USD and not reserva.tipo_cambio:
            return Response({'detail': 'La reserva en USD no tiene tipo de cambio.'}, status=503)

        detalle_a_congelar = None
        if reserva.paquete_id:
            precio_base_servicio = reserva.paquete.precio_total_en(
                reserva.moneda, reserva.personas_del_pedido, reserva.tipo_cambio,
            )
            if precio_base_servicio is None:
                return Response({'detail': f'El paquete no tiene precio en {reserva.moneda}.'}, status=503)
            porcentaje = reserva.paquete.porcentaje_anticipo
            anticipo_disponible = reserva.paquete.anticipo_disponible
        elif reserva.servicio_id:
            estrategia = obtener_estrategia_precio(reserva.servicio.estrategia_precio)
            demanda = DemandaPrecio(
                personas=reserva.numero_personas, moneda=reserva.moneda, noches=reserva.noches,
                tipo_cambio=reserva.tipo_cambio,
            )
            servicio_config = reserva.servicio
            if reserva.servicio.estrategia_precio == EstrategiaPrecio.POR_RUTA:
                detalle_a_congelar = getattr(reserva, 'detalle_transporte', None)
                if detalle_a_congelar is None:
                    return Response({'detail': 'El traslado no tiene detalle configurado.'}, status=503)
                servicio_config = {
                    'tarifas_transporte_activas': list(
                        reserva.servicio.empresa.tarifas_transporte.filter(activo=True)
                    ),
                }
                demanda = demanda_traslado(
                    detalle_a_congelar, reserva.numero_personas, reserva.moneda, reserva.tipo_cambio,
                )
            try:
                precio_base_servicio = estrategia.calcular_base(servicio_config, demanda)
            except ValueError as e:
                return Response({'detail': str(e)}, status=503)
            porcentaje = reserva.servicio.porcentaje_anticipo
            anticipo_disponible = reserva.servicio.anticipo_disponible
        else:
            return Response(
                {'detail': 'La reserva no tiene servicio ni paquete configurado.'}, status=400,
            )

        forma_pago = request.data.get('forma_pago', Reserva.FormaPago.COMPLETO)
        if forma_pago not in Reserva.FormaPago.values:
            return Response({'detail': 'forma_pago invalida.'}, status=400)
        if forma_pago == 'anticipo' and not anticipo_disponible:
            return Response({'detail': 'Este producto no admite pago de anticipo.'}, status=400)

        cargo_extras, extras_a_borrar, extras_a_congelar, error = cotizar_personalizaciones(reserva)
        if error:
            return Response({'detail': error}, status=503)

        subtotal = (
            precio_base_servicio
            + cargo_extras
        )

        codigo_promocional, descuento, error = self._resolver_codigo_promocional(
            request, reserva, subtotal, empresa,
        )
        if error:
            return Response({'detail': error}, status=400)

        precio_total = subtotal - descuento
        monto_a_cobrar = monto_inicial(precio_total, forma_pago, porcentaje=porcentaje)

        if not empresa.stripe_secret_key:
            return Response({'detail': 'Stripe no esta configurado todavia.'}, status=503)

        cliente = configurar_stripe(empresa)
        try:
            intent = self._intent_de(cliente, reserva, monto_a_cobrar)
        except PagoEnCurso:
            return Response(
                {'detail': 'Ya hay un cobro en curso para esta reserva.'}, status=409
            )
        except stripe.StripeError:
            logger.exception('Stripe fallo al preparar el pago de la reserva %s', reserva.pk)
            return Response({'detail': 'No se pudo iniciar el pago. Intenta de nuevo.'}, status=502)

        with transaction.atomic():
            if detalle_a_congelar is not None:
                detalle_a_congelar.numero_personas = reserva.numero_personas
                detalle_a_congelar.precio_calculado = precio_base_servicio
                detalle_a_congelar.save(update_fields=['numero_personas', 'precio_calculado'])
            congelar_personalizaciones(extras_a_borrar, extras_a_congelar)

            reserva.precio_total = precio_total
            reserva.forma_pago = forma_pago
            reserva.stripe_payment_intent_id = intent.id
            reserva.codigo_promocional = codigo_promocional
            reserva.descuento_aplicado = descuento if codigo_promocional else None
            reserva.save(update_fields=[
                'precio_total', 'forma_pago', 'stripe_payment_intent_id',
                'codigo_promocional', 'descuento_aplicado',
            ])

        return Response({
            'client_secret': intent.client_secret,
            'publishable_key': empresa.stripe_publishable_key,
            'monto_a_cobrar': str(monto_a_cobrar),
            'precio_total': str(precio_total),
            'moneda': reserva.moneda,
        })

    def _resolver_codigo_promocional(self, request, reserva, subtotal, empresa):
        """Resuelve el codigo (si vino uno) contra el SUBTOTAL real, con extras
        ya incluidos. `empresa=empresa` explicito (N6): con
        `codigo` ya no unico global, dos Empresas con el mismo codigo sin este
        filtro lanzarian `MultipleObjectsReturned` -> 500 en el checkout, no
        un 400 manejado; se captura explicitamente y se traduce igual que
        "no existe". Mismo mensaje generico sin importar el motivo, para no
        darle pistas a quien prueba codigos al azar.

        Devuelve (promo_o_None, descuento, error_o_None)."""
        codigo_str = (request.data.get('codigo_promocional') or '').strip()
        if not codigo_str:
            return None, 0, None

        try:
            promo = CodigoPromocional.objects.get(codigo=codigo_str.upper(), empresa=empresa)
        except CodigoPromocional.DoesNotExist:
            return None, 0, 'El codigo promocional no es valido.'
        except CodigoPromocional.MultipleObjectsReturned:
            logger.error(
                'Mas de un CodigoPromocional "%s" en la Empresa %s', codigo_str, empresa.slug,
            )
            return None, 0, 'El codigo promocional no es valido.'

        if not codigo_promocional_valido(
            promo, reserva.correo_cliente, monto_viaje=subtotal, moneda=reserva.moneda,
            tipo_cambio=reserva.tipo_cambio,
        ):
            return None, 0, 'El codigo promocional no es valido.'

        return promo, cargo_por_descuento(subtotal, promo.porcentaje_descuento), None

    def _intent_de(self, cliente, reserva, monto):
        """Reusa el intent de la reserva si sigue sin cobrar; si no, crea uno,
        con el `cliente` de Stripe explicito de la Empresa (P1) — nunca
        `stripe.PaymentIntent.*` global. `idempotency_key` va en el segundo
        argumento (`options`), no en `params` (forma real de `stripe==15.4.0`,
        Revision 6 N-D): meterlo en `params` pierde la proteccion de doble
        clic/doble cobro."""
        centavos = a_centavos(monto)
        moneda = reserva.moneda.lower()

        if reserva.stripe_payment_intent_id:
            intent = cliente.payment_intents.retrieve(reserva.stripe_payment_intent_id)
            if intent.status in INTENT_YA_COBRANDO:
                raise PagoEnCurso
            if intent.status in INTENT_REUTILIZABLE:
                if intent.amount == centavos and intent.currency == moneda:
                    return intent
                # Cambio de amenidades o de moneda: se ajusta el mismo intent.
                # El metodo real del servicio es `update`, no `modify`.
                return cliente.payment_intents.update(
                    intent.id, {'amount': centavos, 'currency': moneda},
                )

        return cliente.payment_intents.create(
            {
                'amount': centavos,
                'currency': moneda,
                'metadata': {'reserva_id': reserva.id},
            },
            {'idempotency_key': f'reserva-{reserva.pk}-{moneda}-{centavos}'},
        )


class ValidarCodigoPromocionalView(APIView):
    """Validacion en vivo del codigo mientras el cliente lo escribe en el
    checkout — solo informativa, no liga a ninguna reserva. La autoritativa
    vuelve a correr en `CrearPagoView`.

    Respuesta siempre `{'valido': bool, 'porcentaje_descuento': str|None}` sin
    importar el motivo del rechazo, para no darle pistas a quien prueba
    codigos al azar.
    """

    throttle_scope = 'codigo_promocional'

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            codigo = request.query_params.get('codigo', '')
            correo_cliente = request.query_params.get('correo_cliente', '')
            promo = evaluar_codigo_promocional(codigo, correo_cliente, empresa)
            return Response({
                'valido': promo is not None,
                'porcentaje_descuento': str(promo.porcentaje_descuento) if promo else None,
            })


class EstadoReservaView(APIView):
    """Estado de la reserva de un checkout, para reponerlo tras un refresh o
    un cierre accidental de la pestana.

    El `checkout_id` es la unica llave (nace en el navegador, sobrevive en
    `sessionStorage`) y sirve como capacidad de acceso — no hace falta login.
    Es de solo lectura y no llama a Stripe.
    """

    throttle_scope = 'estado_reserva'

    ESTADOS_PAGADA = {Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA, Reserva.Estado.COMPLETADA}

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            return self._get(request, empresa)

    def _get(self, request, empresa):
        crudo = request.query_params.get('checkout_id')
        try:
            checkout_id = uuid.UUID(str(crudo))
        except (ValueError, TypeError):
            return Response({'detail': 'checkout_id invalido.'}, status=400)

        reserva = (
            Reserva.objects.filter(checkout_id=checkout_id, empresa=empresa)
            .order_by('-id').first()
        )
        if reserva is None:
            return Response(
                {'detail': 'No se encontro una reserva para este checkout.'}, status=404
            )

        if reserva.estado == Reserva.Estado.CANCELADA:
            return Response({'estado': 'cancelada'})

        if reserva.estado in self.ESTADOS_PAGADA:
            personalizaciones = [
                {
                    'nombre': fila.servicio_personalizacion.personalizacion.nombre,
                    'tipo_interaccion': fila.servicio_personalizacion.personalizacion.tipo_interaccion,
                    'cantidad': fila.cantidad,
                    'respuesta': fila.respuesta,
                    'monto': str(fila.subtotal) if fila.subtotal is not None else None,
                }
                for fila in reserva.personalizaciones_seleccionadas.select_related(
                    'servicio_personalizacion__personalizacion'
                )
            ]
            return Response({
                'estado': 'pagada',
                'reserva_id': reserva.id,
                'fecha': reserva.fecha,
                'fecha_inicio_paquete': reserva.fecha_inicio_paquete,
                'hora': reserva.hora,
                'numero_personas': reserva.numero_personas,
                'personas_por_servicio': reserva.personas_por_servicio,
                'nombre_cliente': reserva.nombre_cliente,
                'correo_cliente': reserva.correo_cliente,
                'moneda': reserva.moneda,
                'forma_pago': reserva.forma_pago,
                'monto_pagado': str(reserva.monto_pagado) if reserva.monto_pagado is not None else None,
                'precio_total': str(reserva.precio_total) if reserva.precio_total is not None else None,
                'personalizaciones': personalizaciones,
                'codigo_promocional': (
                    reserva.codigo_promocional.codigo if reserva.codigo_promocional_id else None
                ),
                'descuento_aplicado': (
                    str(reserva.descuento_aplicado) if reserva.descuento_aplicado is not None else None
                ),
            })

        personalizaciones = [
            {
                'id': fila.servicio_personalizacion_id,
                'cantidad': fila.cantidad,
                'respuesta': fila.respuesta,
            }
            for fila in reserva.personalizaciones_seleccionadas.all()
        ]
        detalle_transporte = None
        if hasattr(reserva, 'detalle_transporte'):
            dt = reserva.detalle_transporte
            detalle_transporte = {
                'tipo_traslado': dt.tipo_traslado,
                'punto_encuentro_id': dt.punto_encuentro_id,
                'direccion_personalizada': dt.direccion_personalizada,
                'zona': dt.zona,
                'fecha_regreso': dt.fecha_regreso,
                'numero_personas': dt.numero_personas,
                'precio_calculado': str(dt.precio_calculado) if dt.precio_calculado is not None else None,
            }
        return Response({
            'estado': 'pendiente_pago',
            'reserva_id': reserva.id,
            'fecha': reserva.fecha,
            'fecha_inicio_paquete': reserva.fecha_inicio_paquete,
            'hora': reserva.hora,
            'numero_personas': reserva.numero_personas,
            'personas_por_servicio': reserva.personas_por_servicio,
            'nombre_cliente': reserva.nombre_cliente,
            'telefono_cliente': reserva.telefono_cliente,
            'correo_cliente': reserva.correo_cliente,
            'moneda': reserva.moneda,
            'forma_pago': reserva.forma_pago,
            'personalizaciones': personalizaciones,
            'detalle_transporte': detalle_transporte,
        })


class StripeWebhookView(APIView):
    """Confirma el pago y marca la reserva como pagada.

    Resuelve la Empresa con `resolver_empresa_de_dinero` (Revision 4, N16):
    a diferencia de las rutas de catalogo/checkout, procesa el evento aunque
    `empresa.activo` sea False — una Empresa pausada sigue necesitando
    reconciliar dinero ya cobrado.
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def post(self, request, empresa_slug):
        empresa = scope.resolver_empresa_de_dinero(empresa_slug)

        try:
            evento = stripe.Webhook.construct_event(
                request.body,
                request.headers.get('Stripe-Signature', ''),
                empresa.stripe_webhook_secret,
            )
        except (ValueError, stripe.SignatureVerificationError):
            return Response(status=400)

        objeto = evento['data']['object']

        # Cualquier error aqui devolveria 500 y Stripe reintentaria el evento en
        # bucle. Se registra y se responde 200: el reintento no arreglaria nada.
        try:
            with scope.con_empresa(empresa):
                if evento['type'] == 'payment_intent.succeeded':
                    aplicar_pago_exitoso(objeto, empresa)
                elif evento['type'] == 'payment_intent.amount_capturable_updated':
                    from apps.notifications.services import notificar_orden_retenida

                    orden_id = objeto.get('metadata', {}).get('orden_id')
                    if orden_id and str(orden_id).isdigit():
                        orden = _buscar_orden(empresa.sede, pk=int(orden_id))
                        if orden:
                            notificar_orden_retenida(orden, _reservas_info_de_orden(orden))
                elif evento['type'] == 'charge.refunded':
                    aplicar_reembolso(objeto, empresa)
                elif evento['type'] == 'charge.dispute.created':
                    aplicar_disputa(objeto, True, empresa)
                elif evento['type'] in ('charge.dispute.closed', 'charge.dispute.funds_reinstated'):
                    aplicar_disputa(objeto, False, empresa)
        except Exception:
            logger.exception('Fallo procesando %s (%s)', evento['id'], evento['type'])

        return Response(status=200)


def _buscar_paquete_en_sede(sede, paquete_slug):
    """Busca un paquete activo en la sede iterando sobre las empresas activas,
    respetando la política RLS de fleet_paquete."""
    from apps.fleet.models import Paquete
    from apps.tenancy.models import Empresa

    for emp in Empresa.objects.filter(sede=sede, activo=True):
        with scope.con_empresa(emp):
            p = Paquete.objects.filter(empresa_lider=emp, sede=sede, slug=paquete_slug, activo=True).first()
            if p:
                return p
    return None


def _buscar_servicios_de_paquete(sede, paquete):
    """Resuelve los servicios asociados a un paquete cruza-empresa.
    Lee los PaqueteServicio bajo el scope de la empresa líder, y luego
    obtiene cada Servicio bajo el scope de su propia empresa."""
    from apps.fleet.models import PaqueteServicio, Servicio
    from apps.tenancy.models import Empresa

    empresa_lider = Empresa.objects.get(pk=paquete.empresa_lider_id)
    with scope.con_empresa(empresa_lider):
        servicio_ids = list(
            PaqueteServicio.objects.filter(paquete_id=paquete.id)
            .order_by('orden')
            .values_list('servicio_id', flat=True)
        )

    empresas_sede = list(Empresa.objects.filter(sede=sede, activo=True))
    servicios = []
    for s_id in servicio_ids:
        srv = None
        for emp in empresas_sede:
            with scope.con_empresa(emp):
                s = Servicio.objects.filter(id=s_id, empresa=emp).select_related('empresa').first()
                if s:
                    srv = s
                    break
        if srv:
            servicios.append(srv)
    return servicios


def _buscar_orden(sede, pk=None, checkout_id=None):
    """Busca una orden de la sede bajo el contexto RLS de las empresas de la sede."""
    from apps.bookings.models import Orden
    from apps.tenancy.models import Empresa

    for emp in Empresa.objects.filter(sede=sede, activo=True):
        with scope.con_empresa(emp):
            qs = Orden.objects.filter(sede=sede)
            if pk is not None:
                qs = qs.filter(pk=pk)
            if checkout_id is not None:
                qs = qs.filter(checkout_id=checkout_id)
            orden = qs.first()
            if orden:
                return orden
    return None


class CrearOrdenView(APIView):
    """Crea o reanuda una Orden cruza-empresa en estado 'armando' con sus N Reservas.

    Endpoint público (AllowAny). Cada escritura se ejecuta bajo el contexto RLS
    de la empresa correspondiente vía `scope.con_empresa(empresa)`:
    - La Orden se escribe bajo `scope.con_empresa(paquete.empresa_lider)`
    - Cada Reserva bajo `scope.con_empresa(componente.empresa)`
    - Solo la Reserva líder lleva `paquete` seteado; las demás solo llevan `orden` + `servicio`
    - Para el componente de transporte se crea `DetalleTransporte`
    """

    throttle_scope = 'reservas'
    def post(self, request, sede_slug):
        from datetime import date as _date

        from apps.bookings import personalizaciones as extras_reserva
        from django.utils import timezone
        from apps.bookings.models import DESLINDE_VERSION, DetalleTransporte, Orden, Reserva, Vendedora
        from apps.bookings.serializers import ip_del_cliente
        from apps.fleet.calendario_paquete import (
            ComponenteCalendario, fecha_de_componente, fecha_salida as calcular_salida, noches_del_paquete,
        )
        from apps.fleet.models import PuntoEncuentro, componente_desde
        from apps.fleet.paquete_reglas import errores_de_paquete
        from apps.tenancy.models import Sede
        from django.core.exceptions import ValidationError as DjangoValidationError

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)

        checkout_id_raw = request.data.get('checkout_id')
        checkout_id = None
        if checkout_id_raw:
            try:
                checkout_id = uuid.UUID(str(checkout_id_raw))
            except (ValueError, TypeError):
                return Response({'checkout_id': 'checkout_id debe ser un UUID válido.'}, status=400)

        paquete_slug = request.data.get('paquete')
        if not paquete_slug:
            return Response({'paquete': 'Falta el parámetro paquete.'}, status=400)

        paquete = _buscar_paquete_en_sede(sede, paquete_slug)
        if not paquete:
            raise Http404('No se encontró el paquete solicitado.')

        servicios = _buscar_servicios_de_paquete(sede, paquete)
        empresas_ids = {paquete.empresa_lider_id} | {s.empresa_id for s in servicios}
        if len(empresas_ids) <= 1:
            return Response(
                {'detail': 'Este paquete no es cruza-empresa. Debe reservarse mediante el flujo habitual de reservas.'},
                status=400,
            )

        with scope.con_empresa(paquete.empresa_lider):
            # El orden por defecto une Servicio y RLS oculta los de otras empresas.
            filas_ps = {
                fila['servicio_id']: fila
                for fila in paquete.servicios_asociados.order_by('orden').values(
                    'servicio_id', 'dia_estancia', 'noches', 'personas_incluidas', 'salidas',
                )
            }
        servicios = [s for s in servicios if s.id in filas_ps]
        calendario = [
            ComponenteCalendario(
                dia_estancia=filas_ps[s.id]['dia_estancia'], estrategia_cupo=s.estrategia_cupo,
                noches=filas_ps[s.id]['noches'], salidas=filas_ps[s.id]['salidas'],
            )
            for s in servicios
        ]
        errores = errores_de_paquete(
            permite_anticipo=paquete.permite_anticipo,
            componentes=[
                componente_desde(
                    s, noches=filas_ps[s.id]['noches'], dia_estancia=filas_ps[s.id]['dia_estancia'],
                    personas_incluidas=filas_ps[s.id]['personas_incluidas'], salidas=filas_ps[s.id]['salidas'],
                )
                for s in servicios
            ],
        )
        if errores:
            return Response({'paquete': errores}, status=400)
        try:
            inicio = _date.fromisoformat(str(request.data.get('fecha')))
        except ValueError:
            return Response({'fecha': 'Elige la fecha de inicio del paquete.'}, status=400)
        hay_hospedaje = noches_del_paquete(calendario) is not None

        deslinde_aceptado = request.data.get('deslinde_aceptado')
        deslinde_nombre = request.data.get('deslinde_nombre')
        if not deslinde_aceptado or not deslinde_nombre:
            return Response(
                {'deslinde_aceptado': 'Debe aceptar el deslinde de responsabilidad indicando su nombre.'},
                status=400,
            )
        deslinde_aceptado_en = timezone.now()
        deslinde_ip = ip_del_cliente(request)

        nombre_cliente = request.data.get('nombre_cliente', '').strip()
        telefono_cliente = request.data.get('telefono_cliente', '').strip()
        correo_cliente = request.data.get('correo_cliente', '').strip()
        moneda = (request.data.get('moneda') or Reserva.Moneda.MXN).upper()
        ref = request.data.get('ref', '').strip()

        componentes_data = request.data.get('componentes', [])

        def _buscar_datos_comp(servicio):
            if isinstance(componentes_data, list):
                for item in componentes_data:
                    if isinstance(item, dict) and item.get('servicio') in (servicio.slug, servicio.id, str(servicio.id)):
                        return item
            elif isinstance(componentes_data, dict):
                if servicio.slug in componentes_data:
                    return componentes_data[servicio.slug]
                if servicio.tipo_servicio in componentes_data:
                    return componentes_data[servicio.tipo_servicio]
            return {}

        try:
            with transaction.atomic():
                orden_existente = None
                if checkout_id:
                    orden_existente = _buscar_orden(sede, checkout_id=checkout_id)
                    if orden_existente and orden_existente.estado not in [Orden.Estado.ARMANDO, Orden.Estado.AUTORIZANDO]:
                        orden_existente = None

                if orden_existente:
                    orden = orden_existente
                    orden.nombre_cliente = nombre_cliente
                    orden.telefono_cliente = telefono_cliente
                    orden.correo_cliente = correo_cliente
                    orden.moneda = moneda
                    orden.forma_pago = Reserva.FormaPago.COMPLETO
                    with scope.con_empresa(paquete.empresa_lider):
                        orden.full_clean()
                        orden.save()
                else:
                    orden = Orden(
                        sede=sede,
                        empresa_lider=paquete.empresa_lider,
                        paquete=paquete,
                        checkout_id=checkout_id,
                        nombre_cliente=nombre_cliente,
                        telefono_cliente=telefono_cliente,
                        correo_cliente=correo_cliente,
                        moneda=moneda,
                        forma_pago=Reserva.FormaPago.COMPLETO,
                        estado=Orden.Estado.ARMANDO,
                    )
                    with scope.con_empresa(paquete.empresa_lider):
                        orden.full_clean()
                        orden.save()

                reservas_resultado = []
                personas_pedido = []  # (servicio, personas) de cada componente
                for servicio in servicios:
                    empresa = servicio.empresa
                    es_lider = (empresa.id == paquete.empresa_lider_id)
                    ps = filas_ps[servicio.id]
                    comp_d = _buscar_datos_comp(servicio)
                    if comp_d.get('fecha') or (hay_hospedaje and comp_d.get('fecha_regreso')):
                        raise DjangoValidationError({'fecha': 'Las fechas de cada servicio las define el paquete.'})

                    fecha = fecha_de_componente(inicio, ps['dia_estancia'])
                    personas = comp_d.get('numero_personas') or ps['personas_incluidas']
                    if personas > ps['personas_incluidas']:
                        raise DjangoValidationError({
                            'numero_personas': f'"{servicio.nombre}" incluye {ps["personas_incluidas"]} lugar(es) en este paquete.',
                        })
                    personas_pedido.append((servicio, personas))
                    hora = (
                        comp_d.get('hora') or request.data.get('hora', '07:00:00')
                    ) if paquete.pide_hora else None

                    with scope.con_empresa(empresa):
                        reserva = None
                        if orden_existente:
                            reserva = Reserva.objects.filter(orden=orden, empresa=empresa, servicio=servicio).first()

                        if reserva is None:
                            reserva = Reserva(
                                empresa=empresa,
                                servicio=servicio,
                                paquete=paquete if es_lider else None,
                                orden=orden,
                                canal_origen='web',
                                estado=Reserva.Estado.PENDIENTE_PAGO,
                            )
                        reserva.fecha = fecha
                        reserva.fecha_salida = calcular_salida(inicio, calendario) if servicio.estrategia_cupo == 'por_noche' else None
                        reserva.hora = hora
                        reserva.numero_personas = personas
                        reserva.nombre_cliente = nombre_cliente
                        reserva.telefono_cliente = telefono_cliente
                        reserva.correo_cliente = correo_cliente
                        reserva.moneda = moneda
                        reserva.tipo_cambio = orden.tipo_cambio  # un solo valor para toda la orden
                        reserva.forma_pago = Reserva.FormaPago.COMPLETO
                        reserva.deslinde_aceptado = True
                        reserva.deslinde_nombre = deslinde_nombre
                        reserva.deslinde_aceptado_en = deslinde_aceptado_en
                        reserva.deslinde_ip = deslinde_ip
                        reserva.deslinde_version = DESLINDE_VERSION
                        if es_lider and ref:
                            vendedora = Vendedora.por_codigo(ref, empresa)
                            if vendedora:
                                reserva.vendedora = vendedora
                        reserva.full_clean()
                        reserva.save()

                        if servicio.tipo_servicio == 'transporte':
                            tipo_traslado = comp_d.get('tipo_traslado') or request.data.get('tipo_traslado')
                            pe_id = comp_d.get('punto_encuentro') or request.data.get('punto_encuentro')
                            dir_pers = comp_d.get('direccion_personalizada') or request.data.get('direccion_personalizada', '')
                            zona = comp_d.get('zona') or request.data.get('zona', '')
                            fecha_regreso = (
                                calcular_salida(inicio, calendario)
                                if (hay_hospedaje and tipo_traslado == 'redondo_aeropuerto')
                                else comp_d.get('fecha_regreso') or request.data.get('fecha_regreso')
                            )

                            punto_encuentro = None
                            if pe_id:
                                punto_encuentro = PuntoEncuentro.objects.filter(empresa=empresa, id=pe_id).first()
                                if punto_encuentro:
                                    zona = punto_encuentro.zona

                            detalle = DetalleTransporte.objects.filter(reserva=reserva).first()
                            if detalle is None:
                                detalle = DetalleTransporte(reserva=reserva)
                            detalle.tipo_traslado = tipo_traslado
                            detalle.punto_encuentro = punto_encuentro
                            detalle.direccion_personalizada = dir_pers
                            detalle.zona = zona
                            detalle.fecha_regreso = fecha_regreso
                            detalle.full_clean()
                            detalle.save()

                        items = comp_d.get('personalizaciones') or []
                        extras_reserva.validar_seleccion(servicio, items)
                        extras_reserva.sincronizar(reserva, items)

                        reservas_resultado.append({
                            'id': reserva.id,
                            'empresa_slug': empresa.slug,
                            'servicio': servicio.slug,
                        })

                if paquete.precio_depende_de_personas:
                    total_personas = max(p for _, p in personas_pedido)
                    if any(sv.estrategia_cupo == 'por_recurso_dia' and p != total_personas for sv, p in personas_pedido):
                        raise DjangoValidationError({
                            'numero_personas': 'En este paquete la actividad va con todas las personas; '
                                               'hospedaje y traslado pueden llevar menos.',
                        })

            return Response(
                {
                    'orden_id': orden.id,
                    'checkout_id': str(orden.checkout_id) if orden.checkout_id else None,
                    'estado': orden.estado,
                    'reservas': reservas_resultado,
                },
                status=200 if orden_existente else 201,
            )
        except DjangoValidationError as exc:
            return Response(exc.message_dict if hasattr(exc, 'message_dict') else {'detail': str(exc)}, status=400)

    def get(self, request, sede_slug):
        return GetOrdenView().get(request, sede_slug=sede_slug)


class CrearPagoOrdenView(APIView):
    """Resuelve el reparto del paquete de la orden y crea (o reutiliza) los N
    PaymentIntents con captura manual en Stripe, uno por empresa.
    Transiciona la orden a 'autorizando'.
    Devuelve la lista de pagos. Idempotente. 409 si la orden ya está capturada o cancelada.
    """

    throttle_scope = 'pagos'
    permission_classes = []

    def post(self, request, sede_slug, pk):
        from decimal import Decimal

        from apps.bookings.models import DetalleTransporte, Orden, Reserva
        from apps.bookings.orden_lectura import reservas_de_orden
        from apps.fleet.models import TransporteTarifa
        from apps.fleet.tarifa_transporte import TarifaTransporteNoConfigurada, resolver_tarifa_transporte
        from apps.tenancy.models import Empresa, Sede
        from .extras import congelar_personalizaciones, cotizar_personalizaciones
        from .ordenes import OrdenCerradaError, crear_pagos_orden
        from .pricing import monto_por_empresa, personas_cobradas

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        orden = _buscar_orden(sede, pk=pk)
        if not orden:
            raise Http404('No se encontró la orden solicitada.')

        if orden.estado in (Orden.Estado.CAPTURADA, Orden.Estado.CANCELADA):
            return Response({'detail': f'La orden ya está {orden.estado}.'}, status=409)

        if orden.moneda == Reserva.Moneda.USD and not orden.tipo_cambio:
            return Response({'detail': 'La orden en USD no tiene tipo de cambio.'}, status=400)

        with scope.con_empresa(orden.empresa_lider):
            paquete = orden.paquete
            ancla = paquete.precio_en(orden.moneda, orden.tipo_cambio)
        if ancla is None:
            return Response({'detail': f'El paquete no tiene precio en {orden.moneda}.'}, status=400)

        componentes = []
        extras_por_empresa = {}
        por_congelar = []
        personas_por_servicio = {}
        for fila in reservas_de_orden(orden.id):
            empresa = Empresa.objects.get(pk=fila['empresa_id'])
            es_lider = (empresa.id == orden.empresa_lider_id)
            with scope.con_empresa(empresa):
                reserva = Reserva.objects.select_related('servicio', 'paquete', 'empresa').get(pk=fila['reserva_id'])
                personas_por_servicio[reserva.servicio_id] = reserva.numero_personas
                monto_fijo = None
                if not es_lider and reserva.servicio and reserva.servicio.tipo_servicio == 'transporte':
                    detalle = DetalleTransporte.objects.filter(reserva=reserva).first()
                    if detalle is None:
                        return Response({'detail': 'El traslado no tiene detalle configurado.'}, status=400)
                    tarifas = TransporteTarifa.objects.filter(empresa=empresa, activo=True)
                    try:
                        tarifa = resolver_tarifa_transporte(
                            tarifas, tipo_traslado=detalle.tipo_traslado,
                            zona=detalle.zona_efectiva(), personas=reserva.numero_personas,
                        )
                    except TarifaTransporteNoConfigurada as exc:
                        return Response({'detail': str(exc)}, status=400)
                    monto_fijo = tarifa.precio_en(orden.moneda, orden.tipo_cambio)
                    if monto_fijo is None:
                        return Response(
                            {'detail': f'Falta la tarifa de transporte en {orden.moneda}.'}, status=400,
                        )
                cargo, a_borrar, a_congelar, error = cotizar_personalizaciones(reserva)
            if error:
                return Response({'detail': error}, status=503)
            componentes.append({'empresa_id': empresa.id, 'es_lider': es_lider, 'monto_fijo': monto_fijo})
            extras_por_empresa[empresa.id] = extras_por_empresa.get(empresa.id, Decimal('0.00')) + Decimal(cargo)
            por_congelar.append((empresa, a_borrar, a_congelar))

        precio_paquete = paquete.precio_total_en(
            orden.moneda, personas_cobradas(paquete, personas_por_servicio), orden.tipo_cambio,
        )

        try:
            reparto = monto_por_empresa(
                precio_paquete=precio_paquete, componentes=componentes, moneda=orden.moneda,
            )
            for empresa_id, cargo in extras_por_empresa.items():
                reparto[empresa_id] = reparto.get(empresa_id, Decimal('0.00')) + cargo
            pagos = crear_pagos_orden(orden, reparto)
            for empresa, a_borrar, a_congelar in por_congelar:
                with scope.con_empresa(empresa), transaction.atomic():
                    congelar_personalizaciones(a_borrar, a_congelar)
        except OrdenCerradaError as exc:
            return Response({'detail': str(exc)}, status=409)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        except stripe.StripeError as exc:
            logger.exception('Fallo al crear pagos para la orden %s: %s', orden.id, exc)
            return Response({'detail': 'No se pudo iniciar el cobro con Stripe. Intenta de nuevo.'}, status=502)

        if orden.estado == Orden.Estado.ARMANDO:
            with scope.con_empresa(orden.empresa_lider):
                orden.transicionar(Orden.Estado.AUTORIZANDO)
                orden.save(update_fields=['estado'])

        return Response(pagos, status=200)


class ConfirmarCapturaOrdenView(APIView):
    """Confirma y captura los N PaymentIntents de la orden en Stripe.
    Si todos están 'requires_capture', los captura y devuelve {'estado': 'autorizada'}.
    Si alguno falló autorización o captura, revierte la orden completa y devuelve {'estado': 'cancelada', 'motivo': ...}.
    """

    throttle_scope = 'pagos'
    permission_classes = []

    def post(self, request, sede_slug, pk):
        from apps.bookings.models import Orden, Reserva
        from apps.bookings.orden_lectura import reservas_de_orden
        from apps.tenancy.models import Empresa, Sede
        from .ordenes import confirmar_captura

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        orden = _buscar_orden(sede, pk=pk)
        if not orden:
            raise Http404('No se encontró la orden solicitada.')

        if orden.estado == Orden.Estado.CAPTURADA:
            return Response({'estado': orden.estado}, status=200)

        confirmar_captura(orden)
        with scope.con_empresa(orden.empresa_lider):
            orden.refresh_from_db()

        if orden.estado == Orden.Estado.CANCELADA:
            motivo = 'Cancelada'
            filas = reservas_de_orden(orden.id)
            for f in filas:
                empresa = Empresa.objects.get(pk=f['empresa_id'])
                with scope.con_empresa(empresa):
                    r_canc = Reserva.objects.filter(pk=f['reserva_id']).exclude(motivo_cancelacion='').first()
                    if r_canc and r_canc.motivo_cancelacion:
                        motivo = r_canc.motivo_cancelacion
                        break
            return Response({'estado': orden.estado, 'motivo': motivo}, status=200)

        if orden.estado == Orden.Estado.AUTORIZANDO:
            with scope.con_empresa(orden.empresa_lider):
                orden.transicionar(Orden.Estado.AUTORIZADA)
                orden.save(update_fields=['estado'])

        return Response({'estado': orden.estado}, status=200)


def _reservas_info_de_orden(orden):
    """Detalle por reserva con el estado fresco de cada PaymentIntent en Stripe."""
    from apps.bookings.orden_lectura import reservas_de_orden
    from apps.fleet.models import Servicio
    from apps.tenancy.models import Empresa

    filas = reservas_de_orden(orden.id)
    reservas_info = []

    for fila in filas:
        empresa = Empresa.objects.get(pk=fila['empresa_id'])
        servicio = None
        if fila.get('servicio_id'):
            with scope.con_empresa(empresa):
                servicio = Servicio.objects.filter(pk=fila['servicio_id']).first()
        pi_id = fila.get('stripe_payment_intent_id')

        estado_pi = None
        client_secret = None
        monto = None

        if pi_id and empresa.stripe_secret_key:
            try:
                cliente = configurar_stripe(empresa)
                intent = cliente.payment_intents.retrieve(pi_id)
                estado_pi = getattr(intent, 'status', None)
                client_secret = getattr(intent, 'client_secret', None)
                if hasattr(intent, 'amount') and intent.amount is not None:
                    monto = str(Decimal(intent.amount) / Decimal(100))
            except stripe.StripeError:
                pass

        reservas_info.append({
            'reserva_id': fila['reserva_id'],
            'empresa_slug': empresa.slug,
            'servicio': servicio.slug if servicio else '',
            'pago': {
                'estado_pi': estado_pi,
                'client_secret': client_secret,
                'publishable_key': empresa.stripe_publishable_key,
                'monto': monto,
            },
        })

    return reservas_info


class GetOrdenView(APIView):
    """Devuelve el estado de una Orden y el detalle de sus pagos para que el
    frontend reanude el checkout desde el primer pago pendiente.
    Permite consultar por pk en la URL (`.../ordenes/<id>/`) o por query param (`.../ordenes/?checkout_id=...`).
    """

    throttle_scope = 'estado_reserva'
    permission_classes = []

    def get(self, request, sede_slug, pk=None):
        from apps.bookings.models import Orden
        from apps.tenancy.models import Sede

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)

        if pk is not None:
            orden = _buscar_orden(sede, pk=pk)
        else:
            checkout_id = request.query_params.get('checkout_id')
            if not checkout_id:
                return Response({'checkout_id': 'Se requiere el parámetro checkout_id o id en la ruta.'}, status=400)
            try:
                cid = uuid.UUID(str(checkout_id))
            except (ValueError, TypeError):
                return Response({'checkout_id': 'UUID inválido.'}, status=400)
            orden = _buscar_orden(sede, checkout_id=cid)

        if not orden:
            raise Http404('No se encontró la orden solicitada.')

        reservas_info = _reservas_info_de_orden(orden)
        from apps.notifications.services import notificar_orden_retenida
        notificar_orden_retenida(orden, reservas_info)
        return Response({
            'id': orden.id,
            'checkout_id': str(orden.checkout_id) if orden.checkout_id else None,
            'estado': orden.estado,
            'reservas': reservas_info,
        }, status=200)


def _nombre_producto(paquete, servicio):
    if paquete:
        return paquete.nombre
    if servicio:
        return servicio.nombre
    return 'tu reserva'


class ResumenReservaView(APIView):
    """Resumen sin datos personales para el aviso "Continuar reservación" (spec §10.1).
    No llama a Stripe: la situación sale de lo que el webhook/conciliar_pagos ya dejaron en la BD."""

    throttle_scope = 'estado_reserva'

    def get(self, request, empresa_slug):
        from .situacion import situacion_de_reserva

        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            crudo = request.query_params.get('checkout_id')
            try:
                checkout_id = uuid.UUID(str(crudo))
            except (ValueError, TypeError):
                return Response({'detail': 'checkout_id inválido.'}, status=400)
            # Predicado explícito de empresa además del scope RLS: SQLite no aísla filas.
            reserva = (
                Reserva.objects.filter(checkout_id=checkout_id, empresa=empresa)
                .order_by('-id').first()
            )
            if reserva is None:
                return Response({'detail': 'No se encontró.'}, status=404)
            situacion = situacion_de_reserva(
                estado=reserva.estado, monto_pagado=reserva.monto_pagado,
                monto_reembolsado=reserva.monto_reembolsado,
                tiene_intent_activo=bool(reserva.stripe_payment_intent_id),
            )
            return Response({
                'situacion': situacion,
                'producto': _nombre_producto(reserva.paquete, reserva.servicio),
                'monto': str(reserva.monto_pagado) if reserva.monto_pagado is not None else None,
                'moneda': reserva.moneda,
                'forma_pago': reserva.forma_pago,
                'folio': reserva.id,
                'vence_en': None,
            })


def _pagos_de_orden(orden, reservas_info):
    """Cruza el estado de Stripe con los reembolsos guardados por reserva_id."""
    from apps.bookings.orden_lectura import reservas_de_orden

    reembolsos = {f['reserva_id']: f.get('monto_reembolsado') for f in reservas_de_orden(orden.id)}
    return [
        {
            'estado_pi': r['pago']['estado_pi'],
            'monto_pagado': Decimal(r['pago']['monto']) if r['pago'].get('monto') else None,
            'monto_reembolsado': reembolsos.get(r['reserva_id']),
        }
        for r in reservas_info
    ]


def _resumen_de_orden(orden, *, status_override=None):
    """Contrato completo compartido por resumen y cancelación de una orden."""
    from .situacion import situacion_de_orden

    reservas_info = _reservas_info_de_orden(orden)
    from apps.notifications.services import notificar_orden_retenida
    notificar_orden_retenida(orden, reservas_info)
    pagos = _pagos_de_orden(orden, reservas_info)
    situacion = situacion_de_orden(estado_orden=orden.estado, pagos=pagos)
    vence_en = None
    if situacion in (Situacion.RETENIDO_PARCIAL, Situacion.PAGO_EN_PROCESO):
        vence_en = (orden.actualizado_en + ORDEN_TIMEOUT_AUTORIZACION).isoformat()
    with scope.con_empresa(orden.empresa_lider):
        producto = _nombre_producto(orden.paquete, None)
    return Response({
        'situacion': situacion,
        'producto': producto,
        'moneda': orden.moneda,
        'forma_pago': orden.forma_pago,
        'montos': [
            {
                'empresa': r['empresa_slug'], 'monto': r['pago']['monto'],
                'monto_reembolsado': str(p['monto_reembolsado']) if p['monto_reembolsado'] else None,
                'estado': p['estado_pi'],
            }
            for r, p in zip(reservas_info, pagos)
        ],
        'folio': orden.id,
        'vence_en': vence_en,
        'actualizado_en': orden.actualizado_en.isoformat(),
    }, status=status_override or 200)


class ResumenOrdenView(APIView):
    """Resumen sin datos personales de una Orden, con estado fresco de Stripe."""

    throttle_scope = 'estado_reserva'
    permission_classes = []

    def get(self, request, sede_slug):
        from apps.tenancy.models import Sede

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        crudo = request.query_params.get('checkout_id')
        try:
            checkout_id = uuid.UUID(str(crudo))
        except (ValueError, TypeError):
            return Response({'detail': 'checkout_id inválido.'}, status=400)
        orden = _buscar_orden(sede, checkout_id=checkout_id)
        if not orden:
            return Response({'detail': 'No se encontró.'}, status=404)
        return _resumen_de_orden(orden)


class CancelarOrdenPublicaView(APIView):
    """Cancela la orden del cliente tras comprobar la posesión de checkout_id."""

    throttle_scope = 'pagos'
    permission_classes = []

    def post(self, request, sede_slug, pk):
        from apps.payments.ordenes import revertir_orden
        from apps.tenancy.models import Sede

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        orden = _buscar_orden(sede, pk=pk)
        if not orden:
            raise Http404('No se encontró la orden solicitada.')
        crudo = request.data.get('checkout_id')
        if not orden.checkout_id or str(orden.checkout_id) != str(crudo):
            return Response({'detail': 'checkout_id inválido para esta orden.'}, status=403)

        try:
            revertir_orden(orden, 'cancelada por el cliente desde "Continuar reservación"')
        except OrdenCerradaError:
            with scope.con_empresa(orden.empresa_lider):
                orden.refresh_from_db()
            return _resumen_de_orden(orden, status_override=409)

        with scope.con_empresa(orden.empresa_lider):
            orden.refresh_from_db()
        return _resumen_de_orden(orden)

