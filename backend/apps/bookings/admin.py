import re
from datetime import timedelta
from urllib.parse import quote

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import format_html
from django.utils.timesince import timesince
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from apps.fleet.models import PuntoEncuentro, Recurso, Servicio
from apps.tenancy import scope
from apps.tenancy.admin_mixins import EmpresaScopedAdminMixin, EmpresaScopedUserAdminMixin
from apps.tenancy.models import MembresiaEmpresa

from .forms import AltaVendedoraForm

from .models import (
    ESTADOS_QUE_OCUPAN_CUPO,
    HORAS_PARA_CONSIDERAR_ABANDONADO,
    Agenda,
    CheckoutAbandonado,
    CupoDiario,
    DetalleTransporte,
    Reserva,
    ReservaExtra,
    ReservaOcupacion,
    ReservaPaqueteComponente,
    Vendedora,
)
from .panorama import armar_panorama

# Que tan atras llega "recien llegadas". 48 horas cubre un fin de semana y lo que
# entro mientras nadie miraba, sin que la lista deje de ser corta.
HORAS_RECIEN_LLEGADA = 48

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
class CupoDiarioAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['fecha', 'cupo_maximo']
    ordering = ['fecha']


@admin.register(Vendedora)
class VendedoraAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    """Quienes venden. La comision se liquida fuera del sistema: aqui solo se
    lleva el registro de que venta es de quien."""

    list_display = ['__str__', 'codigo', 'activo', 'link_de_venta', 'ventas_atribuidas']
    list_filter = ['activo']
    search_fields = ['usuario__username', 'usuario__first_name', 'usuario__last_name', 'codigo']
    readonly_fields = ['creado_en']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # `usuario` no lleva FK `empresa` (es `auth.User`): se filtra por membresia,
        # no con `campos_escopeados_por_empresa`. El operador de plataforma ve todo.
        if db_field.name == 'usuario' and not scope.es_operador_plataforma(request.user):
            kwargs['queryset'] = User.objects.filter(membresias__empresa=scope.empresa_actual(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='Su link')
    def link_de_venta(self, obj):
        """El link que le pasa a sus clientes. Quien reserve desde aqui queda
        atribuido a ella sin que tenga que marcarlo despues."""
        return format_html('<code>?ref={}</code>', obj.codigo)

    @admin.display(description='Ventas')
    def ventas_atribuidas(self, obj):
        return obj.ventas.count()


class LlegadaFilter(admin.SimpleListFilter):
    """Lo ultimo que entro al sistema, sin importar para cuando sea el viaje.

    En el listado de Reservas si puede ser un filtro aparte: aqui no hay ninguna
    ventana de fechas con la que chocar. En la agenda es una opcion del filtro
    "Cuando" justo porque ahi si la hay.
    """

    title = 'llegada'
    parameter_name = 'llegada'

    def lookups(self, request, model_admin):
        return [('recientes', f'Recien llegadas ({HORAS_RECIEN_LLEGADA}h)')]

    def queryset(self, request, queryset):
        if self.value() != 'recientes':
            return queryset
        return queryset.filter(
            creado_en__gte=timezone.now() - timedelta(hours=HORAS_RECIEN_LLEGADA))


class AvisoDeReservasNuevasMixin:
    """Contador de reservas nuevas para un listado del admin.

    El admin es HTML renderizado en el servidor: no hay push ni reactividad. Esto
    le da a cada listado un endpoint `nuevas/` que dice cuantas reservas entraron
    desde que se cargo la pagina, y `bookings/reservas-nuevas.js` lo consulta cada
    30 segundos para pintar un boton flotante.

    Lo comparten el listado de Reservas y la Agenda: en las dos se esta mirando la
    pantalla cuando entra una reserva nueva. Cada admin registra su propia URL con
    su nombre, y el JS arma el endpoint relativo a la pagina en la que esta.
    """

    def get_urls(self):
        # Va antes de super(): las URLs del admin terminan en un catch-all
        # `<path:object_id>/` que si no se tragaria 'nuevas/'.
        return [
            path(
                'nuevas/',
                self.admin_site.admin_view(self.reservas_nuevas_view),
                name=f'bookings_{self.model._meta.model_name}_nuevas',
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
            creado_en__gt=desde, estado__in=ESTADOS_QUE_OCUPAN_CUPO,
            empresa=scope.empresa_actual(request),
        ).count()
        return JsonResponse({'desde': desde.isoformat(), 'nuevas': nuevas})


class ReservaExtraInline(admin.TabularInline):
    """Solo lectura: es historial de lo que se vendio en el checkout web, el
    unico que congela precio (ver CrearPagoView). No se edita desde aqui
    porque no hay un segundo mecanismo que congele precio."""

    model = ReservaExtra
    extra = 0
    fields = ['extras_item', 'cantidad_solicitada', 'precio_unitario', 'cantidad', 'subtotal_mostrado']
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Subtotal')
    def subtotal_mostrado(self, obj):
        return obj.subtotal if obj.subtotal is not None else '—'


class ReservaOcupacionInline(admin.TabularInline):
    model = ReservaOcupacion
    extra = 0
    fields = ['recurso', 'fecha_inicio', 'fecha_fin', 'creado_en']
    readonly_fields = ['creado_en']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'recurso' and not scope.es_operador_plataforma(request.user):
            kwargs['queryset'] = Recurso.objects.filter(empresa=scope.empresa_actual(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request, obj=None):
        if obj is not None and obj.estado in ESTADOS_QUE_OCUPAN_CUPO:
            return False
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.estado in ESTADOS_QUE_OCUPAN_CUPO:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.estado in ESTADOS_QUE_OCUPAN_CUPO:
            return False
        return super().has_delete_permission(request, obj)


class ReservaPaqueteComponenteInline(admin.TabularInline):
    model = ReservaPaqueteComponente
    extra = 0
    fields = ['servicio', 'estado_cupo', 'creado_en']
    readonly_fields = ['creado_en']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'servicio' and not scope.es_operador_plataforma(request.user):
            kwargs['queryset'] = Servicio.objects.filter(empresa=scope.empresa_actual(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request, obj=None):
        if obj is not None and obj.estado in ESTADOS_QUE_OCUPAN_CUPO:
            return False
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.estado in ESTADOS_QUE_OCUPAN_CUPO:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.estado in ESTADOS_QUE_OCUPAN_CUPO:
            return False
        return super().has_delete_permission(request, obj)


class DetalleTransporteInline(admin.StackedInline):
    model = DetalleTransporte
    extra = 0
    fields = [
        'tipo_traslado', 'punto_encuentro', 'direccion_personalizada', 'zona',
        'fecha_regreso', 'numero_personas', 'precio_calculado',
    ]
    readonly_fields = ['numero_personas', 'precio_calculado']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'punto_encuentro' and not scope.es_operador_plataforma(request.user):
            kwargs['queryset'] = PuntoEncuentro.objects.filter(empresa=scope.empresa_actual(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ReservaOcupacion)
class ReservaOcupacionAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['recurso', 'reserva', 'fecha_inicio', 'fecha_fin', 'creado_en']
    list_filter = ['recurso', 'fecha_inicio', 'fecha_fin']
    search_fields = ['recurso__nombre', 'reserva__nombre_cliente']
    readonly_fields = ['creado_en']


@admin.register(ReservaPaqueteComponente)
class ReservaPaqueteComponenteAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['reserva', 'servicio', 'estado_cupo', 'creado_en']
    list_filter = ['estado_cupo', 'servicio']
    search_fields = ['reserva__nombre_cliente', 'servicio__nombre']
    readonly_fields = ['creado_en']


@admin.register(Reserva)
class ReservaAdmin(AvisoDeReservasNuevasMixin, EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'fecha', 'hora', 'nombre_cliente', 'numero_personas',
        'estado', 'canal_origen', 'vendedora', 'cobro', 'extras',
        'embarcacion', 'capitan', 'reembolsada',
    ]
    list_filter = [
        LlegadaFilter,
        'estado', 'canal_origen', 'vendedora', 'fecha', 'forma_pago', 'en_disputa',
        'pide_bebidas', 'pide_extras_whatsapp',
        'embarcacion', 'capitan', 'reembolsada', 'codigo_promocional', 'paquete',
    ]
    search_fields = ['nombre_cliente', 'telefono_cliente', 'correo_cliente']
    date_hierarchy = 'fecha'
    autocomplete_fields = ['embarcacion', 'capitan', 'vendedora', 'paquete']
    inlines = [
        ReservaExtraInline,
        ReservaOcupacionInline,
        ReservaPaqueteComponenteInline,
        DetalleTransporteInline,
    ]
    # El deslinde es el registro legal de lo que acepto el cliente: se consulta,
    # no se edita (ver docs/contexto-negocio.md, seccion Legal). Las fechas y los
    # montos del cobro los sella el sistema desde Stripe: editarlos a mano
    # descuadraria el panel de finanzas.
    readonly_fields = [
        'cancelada_por', 'cancelada_en', 'creado_en', 'actualizado_en',
        'deslinde_aceptado', 'deslinde_nombre', 'deslinde_aceptado_en', 'deslinde_ip',
        'deslinde_version',
        'efectivo_cobrado_en', 'efectivo_cobrado_por', 'en_disputa',
        'vendedora_asignada_en', 'pagada_en', 'monto_reembolsado', 'reembolsada_en',
        'aviso_asignacion_enviado_en',
        # Se congelan en CrearPagoView junto con precio_total: editarlos aqui a
        # mano los desincronizaria de ese numero y del conteo de usos del codigo.
        'codigo_promocional', 'descuento_aplicado',
    ]
    actions = [
        'cancelar_por_mal_clima', 'registrar_liquidacion_en_efectivo', 'marcar_como_venta_mia',
    ]

    def get_queryset(self, request):
        # `vendedora` sale en el listado: sin esto es una consulta por fila.
        # `extras_seleccionados` los lee la columna `extras()`, mismo motivo.
        return super().get_queryset(request).select_related('vendedora__usuario').prefetch_related(
            'extras_seleccionados__extras_item'
        )

    class Media:
        # Aviso de reservas nuevas en el listado, ver reservas_nuevas_view.
        js = ['bookings/reservas-nuevas.js']
        # Ancho de las columnas de asignacion, ver el propio archivo.
        css = {'all': ['bookings/admin-columnas.css']}

    @admin.display(description='Extras')
    def extras(self, obj):
        """Que compro el cliente en el checkout web. Lo que va a cotizar el
        agente se marca en naranja: son las que le faltan por resolver antes
        del viaje."""
        partes = [item.extras_item.nombre for item in obj.extras_seleccionados.all()]
        if not obj.tiene_cotizaciones_pendientes:
            return ', '.join(partes) or '—'

        a_cotizar = [
            etiqueta for pedido, etiqueta in
            ((obj.pide_bebidas, 'bebidas'), (obj.pide_extras_whatsapp, 'extras'))
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

    @admin.action(description='Marcar como venta mia')
    def marcar_como_venta_mia(self, request, queryset):
        """Para las ventas que la vendedora cerro por WhatsApp o por telefono.

        Cuando el cliente entra por su link (?ref=) la atribucion ya viene sola;
        esto es para el resto. Se autoasigna a quien esta usando el sistema — no
        se puede atribuir una venta a otra persona desde aqui — y queda en el
        History de cada reserva quien la reclamo y cuando.
        """
        vendedora = Vendedora.objects.filter(
            usuario=request.user, empresa=scope.empresa_actual(request), activo=True,
        ).first()
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
class CheckoutAbandonadoAdmin(EmpresaScopedAdminMixin, ModelAdmin):
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
        # `super()` aplica el filtro por empresa del mixin; aqui se replica lo que
        # hace `CheckoutAbandonado.abandonados()` (mismo criterio, sin perder el
        # aislamiento).
        return super().get_queryset(request).filter(
            estado=Reserva.Estado.PENDIENTE_PAGO,
            creado_en__lt=timezone.now() - timedelta(hours=HORAS_PARA_CONSIDERAR_ABANDONADO),
        )

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


# ---------------------------------------------------------------------------
# Cuentas del backoffice (auth.User / auth.Group)
#
# Django ya trae admin para las dos, pero registrado con su ModelAdmin de
# siempre. Unfold sobreescribe las plantillas del admin de todo el sitio, y las
# suyas solo pintan el boton "Add" (y el resto de la barra de acciones) cuando
# el ModelAdmin lleva su mixin. Sin esto la lista de Usuarios carga pero no hay
# forma de agregar uno desde la interfaz — que es justo como se dan de alta las
# vendedoras (ver `setup_roles` y ../CLAUDE.md, "Roles: Jefes vs Vendedora").
#
# Viven aqui y no en su propia app porque `setup_roles` tambien es de bookings:
# los roles del backoffice son una sola cosa y conviene que se lean juntos.
#
# Se re-registran heredando del UserAdmin/GroupAdmin de Django para no perder
# nada suyo: el flujo de cambio de contraseña, los filtros de permisos y el
# buscador siguen siendo los de Django.
# ---------------------------------------------------------------------------
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(EmpresaScopedUserAdminMixin, BaseUserAdmin, ModelAdmin):
    # Los formularios de Unfold son los de Django con sus widgets. Sin ellos el
    # campo de contraseña se pinta sin estilo y el enlace para cambiarla no sale.
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    def get_urls(self):
        # Antes de super(): el admin termina en un catch-all <path:object_id>/.
        return [
            path(
                'dar-de-alta-vendedora/',
                self.admin_site.admin_view(self.dar_de_alta_vendedora_view),
                name='bookings_user_dar_de_alta_vendedora',
            ),
        ] + super().get_urls()

    def dar_de_alta_vendedora_view(self, request):
        """Unico flujo para crear una vendedora: cuenta + grupo + MembresiaEmpresa
        + bookings.Vendedora en una transaccion. Un jefe la da de alta para su
        propia Empresa; el operador de plataforma elige cual."""
        es_operador = scope.es_operador_plataforma(request.user)
        if not (es_operador or request.user.groups.filter(name='Jefe').exists()):
            raise PermissionDenied

        if request.method == 'POST':
            form = AltaVendedoraForm(request.POST, es_operador=es_operador)
            if form.is_valid():
                empresa = form.cleaned_data['empresa'] if es_operador else scope.empresa_actual(request)
                with transaction.atomic():
                    nuevo = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        password=form.cleaned_data['password'],
                        first_name=form.cleaned_data['nombre'],
                        is_staff=True,
                    )
                    nuevo.groups.add(Group.objects.get(name='Vendedora'))
                    MembresiaEmpresa.objects.create(
                        user=nuevo, empresa=empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
                    )
                    Vendedora.objects.create(
                        usuario=nuevo, empresa=empresa, codigo=form.cleaned_data['codigo'],
                    )
                self.message_user(request, f'Vendedora {nuevo.get_username()} dada de alta.')
                return HttpResponseRedirect(reverse('admin:auth_user_changelist'))
        else:
            form = AltaVendedoraForm(es_operador=es_operador)

        return TemplateResponse(
            request, 'bookings/alta_vendedora.html',
            {**self.admin_site.each_context(request), 'form': form, 'title': 'Dar de alta vendedora'},
        )


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


# Los avisos de la agenda. El texto va como argumento y no incrustado: desde
# Django 5 `format_html` sin argumentos es un error, y asi ademas queda escapado.
AVISO = '<span style="color:#dc2626;font-weight:600">{}</span>'


class CuandoFilter(admin.SimpleListFilter):
    """Los dos modos de usar la agenda, que son dos rangos de fechas y nada mas.

    "Cerrar el dia" y "repartir la semana" no son dos pantallas: es la misma tabla
    mirando distintos dias.
    """

    title = 'cuando'
    parameter_name = 'cuando'

    def lookups(self, request, model_admin):
        return [
            ('manana', 'Manana'),
            ('semana', 'Proximos 7 dias'),
            ('recientes', f'Recien llegadas ({HORAS_RECIEN_LLEGADA}h)'),
        ]

    def queryset(self, request, queryset):
        hoy = timezone.localdate()

        if self.value() == 'recientes':
            # Lo ultimo que entro al sistema, **sin** la ventana de fechas: una
            # reserva que llego hoy para diciembre tiene que aparecer. Por eso es
            # una opcion de este filtro y no un filtro aparte, que se sumaria a la
            # ventana y la dejaria fuera.
            return queryset.filter(
                creado_en__gte=timezone.now() - timedelta(hours=HORAS_RECIEN_LLEGADA))

        if self.value() == 'manana':
            # Cerrar el dia se hace la tarde anterior: si la salida es a las 6am,
            # a esa hora ya nadie esta asignando pangas.
            return queryset.filter(fecha=hoy + timedelta(days=1))

        # Por defecto, repartir la semana. Los atrasados sin repartir entran a
        # proposito: un viaje cobrado que ya paso y nadie asigno es un error que
        # hay que ver. Los que si se repartieron no: esos ya se resolvieron,
        # aunque hayan pasado.
        return queryset.filter(
            models.Q(fecha__range=(hoy, hoy + timedelta(days=7)))
            | models.Q(fecha__lt=hoy, estado=Reserva.Estado.PAGADA)
        )


@admin.register(Agenda)
class AgendaAdmin(AvisoDeReservasNuevasMixin, EmpresaScopedAdminMixin, ModelAdmin):
    """Repartir los viajes ya vendidos: que panga y que capitan le toca a cada uno.

    Se edita en el propio listado, que es el punto entero de la pantalla: con ocho
    o diez viajes en un fin de semana, entrar a cada reserva son treinta clics
    para lo que en la cabeza es una sola decision.
    """

    list_display = [
        'fecha', 'hora', 'nombre_cliente', 'numero_personas',
        'embarcacion', 'capitan', 'avisado', 'aviso',
    ]
    list_editable = ['embarcacion', 'capitan']
    list_display_links = ['nombre_cliente']
    list_filter = [CuandoFilter]
    search_fields = ['nombre_cliente', 'telefono_cliente']
    autocomplete_fields = ['embarcacion', 'capitan']
    list_per_page = 50

    # La cuadricula de dias x pangas va encima de la tabla, ver la plantilla.
    change_list_template = 'bookings/agenda_changelist.html'

    class Media:
        # Mismo aviso de reservas nuevas que el listado de Reservas: repartir
        # tambien se hace mirando esta pantalla.
        js = ['bookings/reservas-nuevas.js', 'bookings/panorama.js']
        css = {'all': ['bookings/admin-columnas.css']}

    def changelist_view(self, request, extra_context=None):
        """Mete el panorama de la semana en el contexto del listado.

        Siempre los proximos 7 dias, **sin seguir el filtro de fechas**. En el
        modo "Manana" quedaria una sola columna y en "Recien llegadas" no hay
        ventana de fechas que dibujar; ademas es justo cerrando el dia de manana
        cuando mas sirve ver la semana completa alrededor.
        """
        return super().changelist_view(request, {
            **(extra_context or {}),
            'panorama': armar_panorama(timezone.localdate(), scope.empresa_actual(request)),
        })

    def get_queryset(self, request):
        # `super()` aplica el filtro por empresa del mixin; se replica el criterio
        # de `Agenda.por_repartir()` sin perder el aislamiento. `embarcacion` y
        # `capitan` salen en el listado: sin `select_related` es una consulta por fila.
        return super().get_queryset(request).filter(
            estado__in=Agenda.ESTADOS_EN_AGENDA
        ).exclude(
            models.Q(servicio__estrategia_cupo='bajo_demanda') |
            models.Q(servicio__tipo_servicio='transporte')
        ).select_related('embarcacion', 'capitan')

    def get_ordering(self, request):
        """Lo recien llegado se ordena por llegada, no por fecha de viaje.

        Con el orden normal (fecha, hora) lo que acaba de entrar quedaria
        enterrado entre lo de la semana, que es lo contrario de para que sirve ese
        modo.
        """
        if request.GET.get(CuandoFilter.parameter_name) == 'recientes':
            return ['-creado_en']
        return super().get_ordering(request)

    def has_add_permission(self, request):
        # Una reserva se crea vendiendo, no se inventa desde aqui.
        return False

    def has_delete_permission(self, request, obj=None):
        # Una reserva se cancela, no se borra (ver docs/contexto-negocio.md).
        return False

    @admin.display(description='Avisado', boolean=True)
    def avisado(self, obj):
        """Si al cliente ya le salio el correo con su capitan y su panga.

        Importa porque un cambio posterior de capitan NO se reenvia solo: esa
        llamada la hace la vendedora, y para hacerla necesita saber que fue lo
        ultimo que el cliente leyo.
        """
        return obj.aviso_asignacion_enviado_en is not None

    @admin.display(description='Aviso')
    def aviso(self, obj):
        """Lo que esta mal, en rojo y sin ambiguedad.

        Un viaje `pagada` sin panga y con fecha futura NO se marca: eso no es un
        error, es el trabajo pendiente y es justo a lo que se viene a esta
        pantalla. Marcarlo volveria roja la agenda entera el primer dia y el rojo
        dejaria de significar algo.
        """
        if obj.estado == Reserva.Estado.PAGADA and obj.fecha < timezone.localdate():
            return format_html(AVISO, 'ATRASADO')
        if obj.estado == Reserva.Estado.ASIGNADA and not obj.capitan_id:
            return format_html(AVISO, 'SIN CAPITAN')
        return '—'
