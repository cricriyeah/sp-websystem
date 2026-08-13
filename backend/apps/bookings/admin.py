import re
from urllib.parse import quote

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import path
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import format_html
from django.utils.timesince import timesince
from unfold.admin import ModelAdmin

from .models import (
    ESTADOS_QUE_OCUPAN_CUPO,
    HORAS_PARA_CONSIDERAR_ABANDONADO,
    CheckoutAbandonado,
    CupoDiario,
    Reserva,
    Vendedora,
)

# Lada de Mexico, para completar los telefonos que el cliente escribio a 10 digitos.
LADA_PAIS = '52'


def telefono_marcable(telefono):
    """Telefono en digitos con lada de pais, como lo quieren `wa.me` y `tel:`.

    Los clientes escriben el numero como se les da la gana ('612 123 4567',
    '+52 1 612...'), asi que se limpia todo lo que no sea digito. 10 digitos =
    numero nacional sin lada internacional. Menos de 10 es un numero incompleto:
    devuelve '' y la interfaz muestra el texto crudo en vez de un enlace roto.
    """
    digitos = re.sub(r'\D', '', telefono or '')
    if len(digitos) == 10:
        return LADA_PAIS + digitos
    return digitos if len(digitos) >= 11 else ''


@admin.register(CupoDiario)
class CupoDiarioAdmin(ModelAdmin):
    list_display = ['fecha', 'cupo_maximo']
    ordering = ['fecha']


@admin.register(Vendedora)
class VendedoraAdmin(ModelAdmin):
    """Quienes venden. La comision se liquida fuera del sistema: aqui solo se
    lleva el registro de que venta es de quien."""

    list_display = ['__str__', 'codigo', 'activo', 'link_de_venta', 'ventas_atribuidas']
    list_filter = ['activo']
    search_fields = ['usuario__username', 'usuario__first_name', 'usuario__last_name', 'codigo']
    readonly_fields = ['creado_en']

    @admin.display(description='Su link')
    def link_de_venta(self, obj):
        """El link que le pasa a sus clientes. Quien reserve desde aqui queda
        atribuido a ella sin que tenga que marcarlo despues."""
        return format_html('<code>?ref={}</code>', obj.codigo)

    @admin.display(description='Ventas')
    def ventas_atribuidas(self, obj):
        return obj.ventas.count()


@admin.register(Reserva)
class ReservaAdmin(ModelAdmin):
    list_display = [
        'fecha', 'hora', 'nombre_cliente', 'numero_personas',
        'estado', 'canal_origen', 'vendedora', 'cobro', 'extras',
        'embarcacion', 'capitan', 'reembolsada',
    ]
    list_filter = [
        'estado', 'canal_origen', 'vendedora', 'fecha', 'forma_pago', 'en_disputa',
        'lleva_lunch', 'pide_bebidas', 'pide_transporte',
        'embarcacion', 'capitan', 'reembolsada',
    ]
    search_fields = ['nombre_cliente', 'telefono_cliente', 'correo_cliente']
    date_hierarchy = 'fecha'
    autocomplete_fields = ['embarcacion', 'capitan', 'vendedora']
    # El deslinde es el registro legal de lo que acepto el cliente: se consulta,
    # no se edita (ver docs/contexto-negocio.md, seccion Legal). Las fechas y los
    # montos del cobro los sella el sistema desde Stripe: editarlos a mano
    # descuadraria el panel de finanzas.
    readonly_fields = [
        'cancelada_por', 'cancelada_en', 'creado_en', 'actualizado_en',
        'deslinde_aceptado', 'deslinde_nombre', 'deslinde_aceptado_en', 'deslinde_ip',
        'efectivo_cobrado_en', 'efectivo_cobrado_por', 'en_disputa',
        'vendedora_asignada_en', 'pagada_en', 'monto_reembolsado', 'reembolsada_en',
    ]
    actions = [
        'cancelar_por_mal_clima', 'registrar_liquidacion_en_efectivo', 'marcar_como_venta_mia',
    ]

    def get_queryset(self, request):
        # `vendedora` sale en el listado: sin esto es una consulta por fila.
        return super().get_queryset(request).select_related('vendedora__usuario')

    class Media:
        # Aviso de reservas nuevas en el listado, ver reservas_nuevas_view.
        js = ['bookings/reservas-nuevas.js']

    @admin.display(description='Extras')
    def extras(self, obj):
        """Que pidio el cliente. Lo que va a cotizar el agente se marca en naranja:
        son las que le faltan por resolver antes del viaje."""
        partes = []
        if obj.lleva_lunch:
            partes.append(f'{obj.numero_personas} lunch')
        if not obj.tiene_cotizaciones_pendientes:
            return ', '.join(partes) or '—'

        a_cotizar = [
            etiqueta for pedido, etiqueta in
            ((obj.pide_bebidas, 'bebidas'), (obj.pide_transporte, 'transporte'))
            if pedido
        ]
        return format_html(
            '{}<span style="color:#c2410c">{} (por cotizar)</span>',
            f'{", ".join(partes)} · ' if partes else '',
            ', '.join(a_cotizar),
        )

    @admin.display(description='Cobro')
    def cobro(self, obj):
        """Cuanto se ha recibido contra el total, y que falta.

        En rojo cuando la reserva es de pago completo y aun asi falta dinero: eso
        no deberia pasar nunca y significa que lo que cobro Stripe no cuadra con
        lo que calculo el servidor."""
        if obj.precio_total is None:
            return '—'

        recibido = (obj.monto_pagado or 0) + (obj.monto_efectivo or 0)
        resumen = f'{recibido} / {obj.precio_total} {obj.moneda}'
        if obj.monto_efectivo:
            resumen = f'{resumen} (incl. {obj.monto_efectivo} en efectivo)'

        saldo = obj.saldo_pendiente
        if saldo <= 0:
            return resumen

        if obj.forma_pago == Reserva.FormaPago.ANTICIPO:
            return format_html('{} <small>(faltan {} en efectivo)</small>', resumen, saldo)
        if obj.estado == Reserva.Estado.PENDIENTE_PAGO:
            return resumen
        return format_html(
            '<span style="color:#b91c1c">{} (descuadre de {})</span>', resumen, saldo
        )

    def get_urls(self):
        # Va antes de super(): las URLs del admin terminan en un catch-all
        # `<path:object_id>/` que si no se tragaria 'nuevas/'.
        return [
            path(
                'nuevas/',
                self.admin_site.admin_view(self.reservas_nuevas_view),
                name='bookings_reserva_nuevas',
            ),
        ] + super().get_urls()

    def reservas_nuevas_view(self, request):
        """Cuantas reservas entraron desde que la vendedora cargo el listado.

        Sin `desde` devuelve la hora del servidor y cero: asi el navegador nunca
        usa su propio reloj como referencia. Con `desde` cuenta solo las que ya
        ocupan cupo (pagadas en adelante) — los checkouts abandonados dejan filas
        en pendiente_pago y avisar de esas volveria el contador puro ruido.
        """
        if not self.has_view_permission(request):
            raise PermissionDenied

        desde_param = request.GET.get('desde')
        if not desde_param:
            return JsonResponse({'desde': timezone.now().isoformat(), 'nuevas': 0})

        desde = parse_datetime(desde_param)
        if desde is None:
            return JsonResponse({'detail': 'desde invalido.'}, status=400)
        if timezone.is_naive(desde):
            desde = timezone.make_aware(desde)

        nuevas = Reserva.objects.filter(
            creado_en__gt=desde, estado__in=ESTADOS_QUE_OCUPAN_CUPO
        ).count()
        return JsonResponse({'desde': desde.isoformat(), 'nuevas': nuevas})

    @admin.action(description='Marcar como venta mia')
    def marcar_como_venta_mia(self, request, queryset):
        """Para las ventas que la vendedora cerro por WhatsApp o por telefono.

        Cuando el cliente entra por su link (?ref=) la atribucion ya viene sola;
        esto es para el resto. Se autoasigna a quien esta usando el sistema — no
        se puede atribuir una venta a otra persona desde aqui — y queda en el
        History de cada reserva quien la reclamo y cuando.
        """
        vendedora = Vendedora.objects.filter(usuario=request.user, activo=True).first()
        if vendedora is None:
            self.message_user(
                request,
                'Tu cuenta no esta dada de alta como vendedora, no se atribuyo nada.',
                level='warning',
            )
            return

        marcadas = 0
        for reserva in queryset.exclude(vendedora=vendedora):
            reserva.vendedora = vendedora
            reserva.save(update_fields=['vendedora'])
            marcadas += 1
        self.message_user(request, f'{marcadas} venta(s) atribuida(s) a {vendedora}.')

    @admin.action(description='Cancelar por mal clima (reembolso completo)')
    def cancelar_por_mal_clima(self, request, queryset):
        """Marca la decision de devolver el dinero. La salida no aparece en el
        panel de finanzas hasta que el reembolso se ejecuta en Stripe y llega el
        evento `charge.refunded`: ahi se sella cuanto salio y cuando."""
        actualizadas = 0
        for reserva in queryset.exclude(estado=Reserva.Estado.CANCELADA):
            reserva.estado = Reserva.Estado.CANCELADA
            reserva.motivo_cancelacion = reserva.motivo_cancelacion or 'Mal clima'
            reserva.cancelada_por = request.user
            reserva.cancelada_en = timezone.now()
            reserva.reembolsada = True
            reserva.full_clean()
            reserva.save()
            actualizadas += 1
        self.message_user(request, f'{actualizadas} reserva(s) cancelada(s) y marcada(s) para reembolso.')

    @admin.action(description='Registrar liquidacion en efectivo (el 70% restante)')
    def registrar_liquidacion_en_efectivo(self, request, queryset):
        """Deja constancia del efectivo que se recibio el dia del viaje.

        Rellena el saldo exacto que faltaba del tour, que es el caso normal. Si
        ademas se cobro algo cotizado aparte (bebidas, transporte), la vendedora
        corrige el monto a mano en la reserva.
        """
        liquidadas = omitidas = 0
        for reserva in queryset:
            saldo = reserva.saldo_pendiente
            if saldo is None or saldo <= 0:
                omitidas += 1
                continue

            reserva.monto_efectivo = (reserva.monto_efectivo or 0) + saldo
            reserva.efectivo_cobrado_en = timezone.now()
            reserva.efectivo_cobrado_por = request.user
            reserva.full_clean()
            reserva.save()
            liquidadas += 1

        aviso = f'{liquidadas} reserva(s) liquidada(s).'
        if omitidas:
            aviso += f' {omitidas} se omitieron: no debian nada.'
        self.message_user(request, aviso)


@admin.register(CheckoutAbandonado)
class CheckoutAbandonadoAdmin(ModelAdmin):
    """Lista de recuperacion: quien empezo a reservar y no termino de pagar.

    Solo lectura. No es una reserva todavia, no hay nada que editar aqui — lo que
    se hace es hablarle al cliente para que termine el pago en la web. Tampoco se
    borra a mano: de eso se encarga `manage.py limpiar_checkouts_abandonados`.
    """

    list_display = ['creado_hace', 'contacto', 'nombre_cliente', 'fecha', 'hora', 'numero_personas', 'moneda']
    list_filter = ['fecha', 'moneda']
    search_fields = ['nombre_cliente', 'telefono_cliente', 'correo_cliente']
    date_hierarchy = 'creado_en'

    def get_queryset(self, request):
        return CheckoutAbandonado.abandonados()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Abandonado hace', ordering='-creado_en')
    def creado_hace(self, obj):
        return timesince(obj.creado_en, timezone.now())

    @admin.display(description='Contacto')
    def contacto(self, obj):
        """WhatsApp con el mensaje ya escrito, mas llamada y correo.

        El texto se manda prellenado para que la vendedora no lo teclee cada vez
        (ni tenga que acordarse de la fecha que pidio el cliente)."""
        numero = telefono_marcable(obj.telefono_cliente)
        if not numero:
            return format_html('{} <small>(numero incompleto)</small>', obj.telefono_cliente or '—')

        mensaje = (
            f'Hola {obj.nombre_cliente}, le escribimos de Sal y Sol Sportfishing. '
            f'Vimos que empezo su reserva para el {obj.fecha} a las {obj.hora:%H:%M} '
            f'y quedo pendiente el pago. ¿Le ayudamos a terminarla?'
        )
        return format_html(
            '<a href="https://wa.me/{}?text={}" target="_blank" rel="noopener">WhatsApp</a> · '
            '<a href="tel:+{}">Llamar</a> · '
            '<a href="mailto:{}">Correo</a>',
            numero, quote(mensaje), numero, obj.correo_cliente,
        )
