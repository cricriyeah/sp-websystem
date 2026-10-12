import re
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote, urlencode

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, models, transaction
from django.db.models.functions import Coalesce
from django.forms.forms import NON_FIELD_ERRORS
from django.http import HttpResponseRedirect, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join
from django.utils.timesince import timesince
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from apps.fleet.models import (
    Embarcacion, EmbarcacionNoDisponible, Paquete, PuntoEncuentro, Recurso, Servicio,
)
from apps.payments.situacion import requiere_atencion, situacion_de_orden, situacion_de_reserva
from apps.notifications.services import enlace_retomar_orden
from apps.tenancy import scope
from apps.tenancy.admin_mixins import EmpresaScopedAdminMixin, EmpresaScopedUserAdminMixin
from apps.tenancy.models import Empresa, MembresiaEmpresa

from .forms import AltaVendedoraForm

from .models import (
    ESTADOS_QUE_OCUPAN_CUPO,
    HORAS_PARA_CONSIDERAR_ABANDONADO,
    HORAS_RECIEN_LLEGADA,
    HORAS_RESERVAS_NUEVAS,
    Agenda,
    CheckoutAbandonado,
    CupoDiario,
    DetalleTransporte,
    Orden,
    Reserva,
    ReservaPersonalizacion,
    ReservaOcupacion,
    ReservaPaqueteComponente,
    Vendedora,
)
from .panorama import armar_panorama
from .orden_lectura import reservas_de_orden

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
        return [
            ('recientes', f'Recien llegadas ({HORAS_RECIEN_LLEGADA}h)'),
            ('nuevas', f'Nuevas ({HORAS_RESERVAS_NUEVAS}h, ya pagadas)'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'recientes':
            return queryset.filter(
                creado_en__gte=timezone.now() - timedelta(hours=HORAS_RECIEN_LLEGADA))
        if self.value() == 'nuevas':
            return queryset.filter(
                estado__in=ESTADOS_QUE_OCUPAN_CUPO,
                creado_en__gte=timezone.now() - timedelta(hours=HORAS_RESERVAS_NUEVAS),
            )
        return queryset


class RequiereAtencionFilter(admin.SimpleListFilter):
    title = 'requiere atención (devolución)'
    parameter_name = 'requiere_atencion'

    def lookups(self, request, model_admin):
        return (('si', 'Sí'),)

    def queryset(self, request, queryset):
        if self.value() != 'si':
            return queryset
        return queryset.filter(consulta_devolucion_pendiente())


def consulta_devolucion_pendiente():
    """La misma condición que `requiere_atencion(situacion_de_reserva(...))`.

    Una cancelada requiere confirmación si se cobró algo y aún no se devolvió
    todo. Se expresa en SQL para los conteos y el filtro sin leer todas las filas.
    """
    return (
        models.Q(estado=Reserva.Estado.CANCELADA, monto_pagado__gt=0)
        & (models.Q(monto_reembolsado__isnull=True)
           | models.Q(monto_reembolsado__lt=models.F('monto_pagado')))
    )


class VistaReservasFilter(admin.SimpleListFilter):
    """Registra `?vista=`; las pestañas se dibujan en la plantilla."""

    title = 'vista'
    parameter_name = 'vista'

    def lookups(self, request, model_admin):
        return []

    def has_output(self):
        return False

    def queryset(self, request, queryset):
        return queryset


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


class ReservaPersonalizacionInline(admin.TabularInline):
    model = ReservaPersonalizacion
    extra = 0
    fields = [
        'servicio_personalizacion', 'cantidad', 'respuesta',
        'precio_unitario', 'subtotal_mostrado',
    ]
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


@admin.register(Orden)
class OrdenAdmin(ModelAdmin):
    # Paquete tiene RLS por empresa lider: un JOIN lo ocultaria junto con
    # la orden. Solo sede se puede unir sin perder ordenes compartidas.
    list_select_related = ('sede',)
    list_display = ['nombre_cliente', 'paquete_mostrado', 'sede', 'estado', 'atencion_col', 'contacto', 'creado_en', 'total']
    exclude = ['paquete']
    readonly_fields = [field.name for field in Orden._meta.fields if field.name != 'paquete'] + [
        'paquete_mostrado', 'total', 'reservas_componentes',
    ]
    actions = ['cancelar_orden', 'confirmar_devolucion_orden']

    def get_queryset(self, request):
        # Orden se comparte por sede, no por empresa_lider. Replica RLS tambien
        # en SQLite; EmpresaScopedAdminMixin requiere un FK empresa inexistente.
        queryset = super().get_queryset(request)
        if scope.es_operador_plataforma(request.user):
            return queryset
        empresa = scope.empresa_actual(request)
        return queryset.filter(sede_id=empresa.sede_id) if empresa else queryset.none()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not (scope.es_operador_plataforma(request.user) or request.user.groups.filter(name='Jefe').exists()):
            actions.pop('cancelar_orden', None)
        if not (
            scope.es_operador_plataforma(request.user)
            or request.user.groups.filter(name__in=['Jefe', 'Vendedora']).exists()
        ):
            actions.pop('confirmar_devolucion_orden', None)
        return actions

    @admin.display(description='Atención')
    def atencion_col(self, obj):
        # Una lectura de componentes por orden en la página; el listado pagina pocas filas.
        filas = reservas_de_orden(obj.pk)
        pagos = [
            {
                'estado_pi': None,
                'monto_pagado': fila['monto_pagado'],
                'monto_reembolsado': fila['monto_reembolsado'],
            }
            for fila in filas
        ]
        s = situacion_de_orden(estado_orden=obj.estado, pagos=pagos)
        return '⚠️ Confirmar devolución' if requiere_atencion(s) else ''

    @admin.display(description='Retomar')
    def contacto(self, obj):
        if obj.estado != Orden.Estado.AUTORIZANDO or obj.retomar_notificado_en is None:
            return '—'
        enlace = enlace_retomar_orden(obj)
        numero = telefono_marcable(obj.telefono_cliente)
        if not enlace or not numero:
            return '—'
        mensaje = (
            f'Hola {obj.nombre_cliente}, le escribimos de Sal y Sol. '
            f'Su reservación sigue abierta y puede retomar el pago aquí: {enlace}'
        )
        return format_html(
            '<a href="https://wa.me/{}?text={}" target="_blank" rel="noopener">WhatsApp</a>',
            numero, quote(mensaje),
        )

    @admin.action(description='Confirmar devolución de orden (ya se resolvió fuera del sistema)')
    def confirmar_devolucion_orden(self, request, queryset):
        if not (
            scope.es_operador_plataforma(request.user)
            or request.user.groups.filter(name__in=['Jefe', 'Vendedora']).exists()
        ):
            raise PermissionDenied

        from apps.tenancy.models import Empresa

        confirmadas = 0
        ordenes = list(queryset)
        # El request del admin ya tiene un alcance activo. Como en revertir_orden,
        # cada reserva se escribe bajo su empresa y al final se restaura el alcance.
        prev_alcance = getattr(connection, 'alcance_actual', None)
        connection.alcance_actual = None
        try:
            for orden in ordenes:
                confirmadas_en_orden = 0
                for fila in reservas_de_orden(orden.pk):
                    empresa = Empresa.objects.get(pk=fila['empresa_id'])
                    with scope.con_empresa(empresa):
                        reserva = Reserva.objects.get(pk=fila['reserva_id'])
                        s = situacion_de_reserva(
                            estado=reserva.estado, monto_pagado=reserva.monto_pagado,
                            monto_reembolsado=reserva.monto_reembolsado,
                        )
                        if not requiere_atencion(s):
                            continue
                        reserva.reembolsada = True
                        reserva.monto_reembolsado = reserva.monto_pagado
                        reserva.reembolsada_en = timezone.now()
                        reserva.save(update_fields=['reembolsada', 'monto_reembolsado', 'reembolsada_en'])
                        self.log_change(request, reserva, 'Devolución confirmada fuera del sistema.')
                        confirmadas += 1
                        confirmadas_en_orden += 1
                if confirmadas_en_orden:
                    self.log_change(request, orden, 'Devolución de componentes confirmada fuera del sistema.')
        finally:
            connection.alcance_actual = prev_alcance
            if connection.vendor == 'postgresql' and prev_alcance:
                with connection.cursor() as cursor:
                    if prev_alcance[0] == 'empresa':
                        cursor.execute(f'SET LOCAL app.current_empresa_id = {int(prev_alcance[1])}')
                    elif prev_alcance[0] == 'operador':
                        cursor.execute("SET LOCAL app.operador_plataforma = 'on'")
        self.message_user(request, f'{confirmadas} reserva(s) de orden marcadas como devolución confirmada.')

    @admin.action(description='Cancelar orden (revertir pagos pendientes)')
    def cancelar_orden(self, request, queryset):
        if not (scope.es_operador_plataforma(request.user) or request.user.groups.filter(name='Jefe').exists()):
            raise PermissionDenied
        from apps.payments import ordenes

        for orden in queryset:
            try:
                ordenes.revertir_orden(orden, 'cancelada desde el admin')
            except ordenes.OrdenCerradaError as exc:
                self.message_user(request, f'Orden #{orden.pk}: {exc}', level='warning')
        self.message_user(request, 'Cancelacion de ordenes procesada.')

    @admin.display(description='Paquete')
    def paquete_mostrado(self, obj):
        try:
            return str(obj.paquete)
        except Paquete.DoesNotExist:
            # El identificador pertenece a la orden visible; el catalogo de
            # la empresa hermana sigue protegido por su propia politica RLS.
            return f'Paquete #{obj.paquete_id}'

    @admin.display(description='Total')
    def total(self, obj):
        return sum((fila['monto_pagado'] or Decimal('0.00')
                    for fila in reservas_de_orden(obj.pk)), Decimal('0.00'))

    @admin.display(description='Reservas de la orden')
    def reservas_componentes(self, obj):
        # El related manager solo ve la reserva propia bajo RLS. La lectura
        # SECURITY DEFINER incluye los componentes de las empresas hermanas.
        filas = reservas_de_orden(obj.pk)
        if not filas:
            return '—'
        return format_html(
            '<table><thead><tr><th>Reserva</th><th>Estado</th><th>Cargo ({})</th>'
            '</tr></thead><tbody>{}</tbody></table>',
            obj.moneda,
            format_html_join('', '<tr><td><a href="{}">#{}</a></td><td>{}</td><td>{}</td></tr>', (
                (reverse('admin:bookings_reserva_change', args=[fila['reserva_id']]),
                 fila['reserva_id'], dict(Reserva.Estado.choices).get(fila['estado'], fila['estado']),
                 format(fila['monto_pagado'] or Decimal('0.00'), '.2f'))
                for fila in filas
            )),
        )


@admin.register(Reserva)
class ReservaAdmin(AvisoDeReservasNuevasMixin, EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'cuando', 'nombre_cliente', 'numero_personas', 'servicio_resumen',
        'estado', 'cobro', 'extras', 'asignacion',
    ]
    list_display_links = ['nombre_cliente']
    list_filter = [
        VistaReservasFilter, LlegadaFilter, RequiereAtencionFilter,
        'estado', 'canal_origen', 'vendedora', 'fecha', 'forma_pago', 'en_disputa',
        'pide_bebidas', 'pide_extras_whatsapp',
        'embarcacion', 'capitan', 'reembolsada', 'codigo_promocional', 'paquete',
    ]
    search_fields = ['nombre_cliente', 'telefono_cliente', 'correo_cliente']
    date_hierarchy = 'fecha'
    autocomplete_fields = ['embarcacion', 'capitan', 'vendedora', 'paquete']
    inlines = [
        ReservaPersonalizacionInline,
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
        'confirmar_devolucion',
    ]
    change_list_template = 'bookings/reservas_changelist.html'
    VISTAS = (
        ('proximas', 'Próximas'), ('hoy', 'Hoy'), ('manana', 'Mañana'),
        ('por_cobrar', 'Por cobrar'), ('atencion', 'Requieren atención'),
        ('todas', 'Todas'),
    )

    @staticmethod
    def _es_listado(request):
        match = request.resolver_match
        return match is not None and match.url_name == 'bookings_reserva_changelist'

    def _vista(self, request):
        pedida = request.GET.get('vista')
        if pedida in dict(self.VISTAS):
            return pedida
        if request.method == 'POST':
            # Las acciones masivas existentes también se invocan directamente
            # contra la URL sin query string (p. ej. desde integraciones).
            return 'todas'
        # Enlaces históricos con búsqueda o filtro mantienen el alcance de antes.
        return 'todas' if request.GET else 'proximas'

    @staticmethod
    def _saldo_sql():
        dinero = models.DecimalField(max_digits=12, decimal_places=2)
        return models.ExpressionWrapper(
            models.F('precio_total')
            - Coalesce('monto_pagado', models.Value(Decimal('0.00')), output_field=dinero)
            - Coalesce('monto_efectivo', models.Value(Decimal('0.00')), output_field=dinero),
            output_field=dinero,
        )

    def _consulta_vista(self, vista, hoy):
        activos = models.Q(estado__in=[Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA])
        if vista == 'proximas':
            return activos & models.Q(fecha__gte=hoy)
        if vista == 'hoy':
            return activos & models.Q(fecha=hoy)
        if vista == 'manana':
            return activos & models.Q(fecha=hoy + timedelta(days=1))
        if vista == 'por_cobrar':
            return (activos & models.Q(fecha__lte=hoy + timedelta(days=1))
                    & models.Q(_saldo_lista__gt=0, forma_pago=Reserva.FormaPago.ANTICIPO))
        if vista == 'atencion':
            return consulta_devolucion_pendiente()
        return models.Q()

    def changelist_view(self, request, extra_context=None):
        hoy = timezone.localdate()
        vista = self._vista(request)
        # `super(ReservaAdmin, self)` aplica el mixin de empresa y deja todas las
        # empresas visibles al operador. Una agregación, sin precargas por fila.
        base = super(ReservaAdmin, self).get_queryset(request).annotate(
            _saldo_lista=self._saldo_sql())
        conteos = base.aggregate(**{
            clave: models.Count('pk', filter=self._consulta_vista(clave, hoy))
            for clave, _ in self.VISTAS
        })

        def enlace(clave):
            consulta = request.GET.copy()
            consulta['vista'] = clave
            consulta.pop('p', None)
            consulta.pop('o', None)
            return f'{request.path}?{consulta.urlencode()}'

        pestanas = [dict(clave=clave, nombre=nombre, conteo=conteos[clave],
                         activa=clave == vista, url=enlace(clave))
                    for clave, nombre in self.VISTAS]
        respuesta = super().changelist_view(request, {
            **(extra_context or {}), 'reservas_pestanas': pestanas,
        })
        if (getattr(respuesta, 'context_data', None) and 'cl' in respuesta.context_data
                and vista != 'todas' and request.GET.get('o', '1') in ('1', '-1')):
            # La página ya está paginada y ordenada. Sólo se marca la primera fila
            # de cada día; Unfold conserva sus tbody, casillas y acciones intactos.
            cl = respuesta.context_data['cl']
            filas = list(cl.result_list)
            anterior = None
            for reserva in filas:
                reserva._inicio_dia_lista = reserva.fecha != anterior
                anterior = reserva.fecha
            cl.result_list = filas
        return respuesta

    def get_ordering(self, request):
        # Al ordenar la columna Cuándo, la hora sigue la misma dirección.
        if self._es_listado(request) and request.GET.get('o') == '1':
            return ['fecha', 'hora']
        if self._es_listado(request) and request.GET.get('o') == '-1':
            return ['-fecha', '-hora']
        if self._es_listado(request) and self._vista(request) != 'todas':
            return ['fecha', 'hora']
        return ['-fecha', '-hora']

    def requiere_atencion_col(self, obj):
        s = situacion_de_reserva(
            estado=obj.estado, monto_pagado=obj.monto_pagado, monto_reembolsado=obj.monto_reembolsado,
        )
        return '⚠️ Confirmar devolución' if requiere_atencion(s) else ''
    requiere_atencion_col.short_description = 'Atención'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not (
            scope.es_operador_plataforma(request.user)
            or request.user.groups.filter(name__in=['Jefe', 'Vendedora']).exists()
        ):
            actions.pop('confirmar_devolucion', None)
        return actions

    @admin.action(description='Confirmar devolución (ya se resolvió fuera del sistema)')
    def confirmar_devolucion(self, request, queryset):
        if not (
            scope.es_operador_plataforma(request.user)
            or request.user.groups.filter(name__in=['Jefe', 'Vendedora']).exists()
        ):
            raise PermissionDenied
        confirmadas = 0
        for reserva in queryset:
            s = situacion_de_reserva(
                estado=reserva.estado, monto_pagado=reserva.monto_pagado,
                monto_reembolsado=reserva.monto_reembolsado,
            )
            if not requiere_atencion(s):
                continue
            reserva.reembolsada = True
            reserva.monto_reembolsado = reserva.monto_pagado
            reserva.reembolsada_en = timezone.now()
            reserva.save(update_fields=['reembolsada', 'monto_reembolsado', 'reembolsada_en'])
            self.log_change(request, reserva, 'Devolución confirmada fuera del sistema.')
            confirmadas += 1
        self.message_user(request, f'{confirmadas} reserva(s) marcadas como devolución confirmada.')

    def get_queryset(self, request):
        # El desglose operativo muestra solo checks, sin respuestas de inputs.
        qs = super().get_queryset(request).select_related(
            'vendedora__usuario', 'servicio', 'paquete', 'embarcacion', 'capitan',
            'detalle_transporte__punto_encuentro',
        ).prefetch_related(
            'personalizaciones_seleccionadas__servicio_personalizacion__personalizacion'
        )
        if not self._es_listado(request):
            return qs
        return qs.annotate(_saldo_lista=self._saldo_sql()).filter(
            self._consulta_vista(self._vista(request), timezone.localdate()))

    @admin.display(description='Cuándo', ordering='fecha')
    def cuando(self, obj):
        formato = 'D j M' if obj.fecha.year == timezone.localdate().year else 'D j M Y'
        fecha = date_format(obj.fecha, formato)
        hora = f' · {obj.hora:%H:%M}' if obj.hora else ''
        if not getattr(obj, '_inicio_dia_lista', False):
            return f'{fecha}{hora}'
        hoy = timezone.localdate()
        etiqueta = ('Hoy' if obj.fecha == hoy else 'Mañana' if obj.fecha == hoy + timedelta(days=1)
                    else fecha)
        return format_html('<span class="reservas-dia">{}</span>{}{}', etiqueta, fecha, hora)

    @admin.display(description='Servicio')
    def servicio_resumen(self, obj):
        nombre = obj.paquete.nombre if obj.paquete_id else (
            obj.servicio.nombre if obj.servicio_id else 'Sin servicio')
        if not obj.servicio_id or obj.servicio.tipo_servicio != 'transporte':
            return nombre
        try:
            detalle = obj.detalle_transporte
        except DetalleTransporte.DoesNotExist:
            return nombre
        partes = [detalle.get_tipo_traslado_display()]
        if detalle.zona:
            partes.append(detalle.get_zona_display())
        if detalle.punto_encuentro_id:
            partes.append(detalle.punto_encuentro.nombre)
        elif detalle.direccion_personalizada:
            partes.append(detalle.direccion_personalizada)
        return format_html('{}<br><small>{}</small>', nombre, ' · '.join(partes))

    @admin.display(description='Asignación')
    def asignacion(self, obj):
        if not obj.embarcacion_id and not obj.capitan_id:
            return 'Sin panga · Sin capitán'
        return f'{obj.embarcacion.nombre if obj.embarcacion_id else "Sin panga"} · {obj.capitan.nombre if obj.capitan_id else "Sin capitán"}'

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        empresa = scope.empresa_actual(request)
        if empresa and not initial.get('servicio') and not initial.get('paquete'):
            servicio = Servicio.objects.filter(
                empresa=empresa, slug='pesca-deportiva',
                tipo_servicio='pesca', activo=True,
            ).first()
            if servicio:
                initial['servicio'] = servicio.pk
        return initial

    class Media:
        # Aviso de reservas nuevas en el listado, ver reservas_nuevas_view.
        js = ['bookings/reservas-nuevas.js']
        # Ancho de las columnas de asignacion, ver el propio archivo.
        css = {'all': ['bookings/admin-columnas.css']}

    @admin.display(description='Orden')
    def orden_link(self, obj):
        if obj.orden_id is None:
            return '—'
        return format_html('<a href="{}">Orden #{}</a>',
                           reverse('admin:bookings_orden_change', args=[obj.orden_id]), obj.orden_id)

    @admin.display(description='Extras')
    def extras(self, obj):
        """Que compro el cliente en el checkout web. Lo que va a cotizar el
        agente se marca en naranja: son las que le faltan por resolver antes
        del viaje."""
        partes = [
            fila.servicio_personalizacion.personalizacion.nombre
            for fila in obj.personalizaciones_seleccionadas.all()
            if fila.servicio_personalizacion.personalizacion.tipo_interaccion == 'check'
        ]
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
        """Un hecho breve; rojo sólo para deuda vencida, devolución o descuadre."""
        def monto(valor):
            return (f'{valor:,.0f}' if valor == valor.to_integral_value()
                    else f'{valor:,.2f}')

        situacion = situacion_de_reserva(
            estado=obj.estado, monto_pagado=obj.monto_pagado,
            monto_reembolsado=obj.monto_reembolsado,
        )
        if requiere_atencion(situacion):
            resta = (obj.monto_pagado or Decimal('0')) - (obj.monto_reembolsado or Decimal('0'))
            return format_html('<span class="reservas-cobro-urgente">{}</span>',
                               f'Devolver {monto(resta)} {obj.moneda}')
        if obj.estado == Reserva.Estado.PENDIENTE_PAGO:
            return 'Sin pagar'
        saldo = obj.saldo_pendiente
        if saldo is None:
            return '—'
        if saldo <= 0:
            return 'Pagado'
        if obj.forma_pago == Reserva.FormaPago.ANTICIPO:
            texto = f'Debe {monto(saldo)} {obj.moneda} en efectivo'
            if obj.fecha <= timezone.localdate():
                return format_html('<span class="reservas-cobro-urgente">{}</span>', texto)
            return texto
        return format_html('<span class="reservas-cobro-urgente">{}</span>',
                           f'Descuadre de {monto(saldo)} {obj.moneda}')

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
            f'Vimos que empezo su reserva para el {obj.fecha_inicio_paquete}'
            f'{obj.hora.strftime(" a las %H:%M") if obj.hora else ""} '
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


class EmpresaAgendaFilter(admin.SimpleListFilter):
    """Registra `?empresa=` como parametro conocido del listado de la Agenda.

    No filtra ni se dibuja: Django descarta un filtro sin salida (`has_output`) pero
    antes le deja consumir su parametro, y eso evita que el listado lo rechace como un
    campo inexistente. El filtrado real esta en `AgendaAdmin.get_queryset` y las
    pestañas de la plantilla son la interfaz. Los enlaces de los demas filtros y de la
    paginacion lo conservan solos.
    """

    title = 'empresa'
    parameter_name = 'empresa'

    def lookups(self, request, model_admin):
        return []

    def has_output(self):
        return False

    def queryset(self, request, queryset):
        return queryset


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


class ContextoAsignacion:
    """Lo que ya esta tomado cada dia, para ofrecer solo las pangas que sirven.

    Una consulta por cada dia distinto del listado (no por fila) y una por flota,
    asi que una semana de agenda son unas diez consultas y no cien. Vive lo que
    dura la peticion: se crea en `get_changelist_form`.
    """

    def __init__(self):
        self._dias = {}
        self._flota = {}

    def _pangas(self, empresa_id):
        if empresa_id not in self._flota:
            self._flota[empresa_id] = list(
                Embarcacion.objects.filter(empresa_id=empresa_id, activa=True)
                .values_list('pk', 'capacidad_maxima')
            )
        return self._flota[empresa_id]

    def _tomado(self, fecha, empresa_id):
        clave = (fecha, empresa_id)
        if clave not in self._dias:
            del_dia = Reserva.objects.filter(
                models.Q(fecha=fecha) | models.Q(salidas__fecha=fecha),
                estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa_id=empresa_id,
            ).distinct().values_list('pk', 'embarcacion_id', 'capitan_id')
            fuera = EmbarcacionNoDisponible.objects.filter(
                fecha=fecha, empresa_id=empresa_id,
            ).values_list('embarcacion_id', flat=True)
            self._dias[clave] = (list(del_dia), set(fuera))
        return self._dias[clave]

    def pangas_que_sirven(self, reserva):
        """Libres ese dia y con lugar para el grupo. Misma regla que `clean()`:
        una sola salida por dia y no pasar la capacidad."""
        del_dia, fuera = self._tomado(reserva.fecha, reserva.empresa_id)
        tomadas = {panga for pk, panga, _ in del_dia if panga and pk != reserva.pk}
        return [
            pk for pk, capacidad in self._pangas(reserva.empresa_id)
            if pk not in tomadas and pk not in fuera and capacidad >= reserva.numero_personas
        ]

    def capitanes_ocupados(self, reserva):
        """Los que ya tienen viaje ese dia, sin contar el de esta misma reserva."""
        del_dia, _ = self._tomado(reserva.fecha, reserva.empresa_id)
        return {capitan for pk, _, capitan in del_dia if capitan and pk != reserva.pk}


class AgendaForm(forms.ModelForm):
    # Lo pone `AgendaAdmin.get_changelist_form`; sin el, el formulario ofrece todo
    # y la validacion del modelo sigue rechazando lo que no sirve.
    contexto = None

    class Meta:
        model = Agenda
        fields = ['embarcacion', 'capitan']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aligerar_selectores()
        # Solo al mostrar. Al guardar el formulario queda con todas las opciones a
        # proposito: si una ya no sirve, el modelo contesta "X ya tiene un viaje el
        # ..." y eso explica mas que "escoja una opcion valida".
        if self.contexto is not None and self.instance.pk and not self.is_bound:
            self._ofrecer_solo_lo_que_sirve(self.instance)

    def _aligerar_selectores(self):
        """Menos ruido por fila: nombre y capacidad en vez de la descripcion larga, y
        sin los botones de agregar/editar/borrar salvo "agregar" en el capitan.

        Siete viajes eran catorce selectores y catorce botones. La panga es catalogo
        de jefes: no se crea ni se edita desde repartir. El capitan si, porque
        faltar uno es justo lo que se resuelve sin salir de la pantalla.
        """
        self.fields['embarcacion'].label_from_instance = (
            lambda panga: f'{panga.nombre} ({panga.capacidad_maxima})'
        )
        for campo, puede_crear in (('embarcacion', False), ('capitan', True)):
            envoltorio = self.fields[campo].widget
            if hasattr(envoltorio, 'can_add_related'):
                envoltorio.can_add_related = envoltorio.can_add_related and puede_crear
                envoltorio.can_change_related = False
                envoltorio.can_delete_related = False
                envoltorio.can_view_related = False

    def _ofrecer_solo_lo_que_sirve(self, reserva):
        """Lo que no esta libre o no cabe no se ofrece, en vez de enterarse al guardar."""
        pangas = self.fields['embarcacion']
        ids = set(self.contexto.pangas_que_sirven(reserva))
        if reserva.embarcacion_id:
            ids.add(reserva.embarcacion_id)  # la actual nunca desaparece del selector
        pangas.queryset = pangas.queryset.filter(pk__in=ids).order_by('-capacidad_maxima', 'nombre')
        pangas.empty_label = 'Elegir panga' if ids else 'Sin pangas libres donde quepan'

        capitanes = self.fields['capitan']
        ocupados = self.contexto.capitanes_ocupados(reserva) - {reserva.capitan_id}
        capitanes.queryset = capitanes.queryset.filter(empresa_id=reserva.empresa_id).exclude(pk__in=ocupados)
        capitanes.empty_label = 'Elegir capitan'

    def _post_clean(self):
        # El listado envia todas las reservas visibles, aunque solo se cambie
        # una. Una fila intacta no se guarda y no debe revalidarse contra un
        # horario de servicio que pudo cambiar despues de la venta.
        if not self.has_changed():
            return
        super()._post_clean()

    def _update_errors(self, errors):
        # La agenda solo edita panga y capitan. Una reserva antigua puede tener
        # un dato invalido (por ejemplo la hora); Django no puede asociar ese
        # error a un campo ausente y lanzaria un 500 al guardar el listado.
        if hasattr(errors, 'error_dict'):
            errores = {campo: list(mensajes) for campo, mensajes in errors.error_dict.items()}
            for campo in list(errores):
                if campo in self.fields or campo == NON_FIELD_ERRORS:
                    continue
                etiqueta = self.instance._meta.get_field(campo).verbose_name
                errores.setdefault(NON_FIELD_ERRORS, []).extend(
                    ValidationError(f'{etiqueta}: {mensaje}')
                    for error in errores.pop(campo)
                    for mensaje in error.messages
                )
            errors = ValidationError(errores)
        super()._update_errors(errors)


@admin.register(Agenda)
class AgendaAdmin(AvisoDeReservasNuevasMixin, EmpresaScopedAdminMixin, ModelAdmin):
    """Repartir los viajes ya vendidos: que panga y que capitan le toca a cada uno.

    Se edita en el propio listado, que es el punto entero de la pantalla: con ocho
    o diez viajes en un fin de semana, entrar a cada reserva son treinta clics
    para lo que en la cabeza es una sola decision.
    """

    # "Aviso" va pegado a la panga y al capitan, no al final: es lo que dice que falta
    # (SIN CAPITAN / ATRASADO) y a la derecha quedaba fuera de pantalla.
    list_display = [
        'dia', 'hora', 'nombre_cliente', 'numero_personas',
        'embarcacion', 'capitan', 'aviso', 'avisado',
    ]
    list_editable = ['embarcacion', 'capitan']
    list_display_links = ['nombre_cliente']
    list_filter = [CuandoFilter]
    search_fields = ['nombre_cliente', 'telefono_cliente']
    # Sin `autocomplete_fields` a proposito: el autocompletado trae todas las
    # pangas sin saber de que fila viene. Con un selector normal cada fila ofrece
    # solo las pangas libres y con lugar para su grupo (`ContextoAsignacion`).
    list_per_page = 50

    # La cuadricula de dias x pangas va encima de la tabla, ver la plantilla.
    change_list_template = 'bookings/agenda_changelist.html'

    def get_changelist_form(self, request, **kwargs):
        # Un formulario con su propio contexto por peticion: lo tomado cada dia se
        # consulta una vez y lo comparten todas las filas.
        formulario = type('AgendaFormConContexto', (AgendaForm,), {'contexto': ContextoAsignacion()})
        return super().get_changelist_form(request, form=formulario, **kwargs)

    class Media:
        # Mismo aviso de reservas nuevas que el listado de Reservas: repartir
        # tambien se hace mirando esta pantalla.
        js = ['bookings/reservas-nuevas.js', 'bookings/panorama.js']
        css = {'all': ['bookings/admin-columnas.css']}

    SESION_EMPRESA = 'agenda_empresa'

    @staticmethod
    def _es_listado(request):
        match = request.resolver_match
        return match is not None and match.url_name == 'bookings_agenda_changelist'

    def get_list_filter(self, request):
        if scope.es_operador_plataforma(request.user):
            return [EmpresaAgendaFilter, CuandoFilter]
        return [CuandoFilter]

    def changelist_view(self, request, extra_context=None):
        """Mete el panorama de la semana en el contexto del listado.

        Siempre los proximos 7 dias, **sin seguir el filtro de fechas**. En el
        modo "Manana" quedaria una sola columna y en "Recien llegadas" no hay
        ventana de fechas que dibujar; ademas es justo cerrando el dia de manana
        cuando mas sirve ver la semana completa alrededor.

        El operador de plataforma no pertenece a una empresa: elige cual mirar
        (`_contexto_operador`). Sin eso el panorama salia vacio y decia "Todo asignado".
        """
        if scope.es_operador_plataforma(request.user):
            respuesta, contexto = self._contexto_operador(request)
            if respuesta is not None:
                return respuesta
        else:
            contexto = {
                'panorama': armar_panorama(timezone.localdate(), scope.empresa_actual(request)),
            }
        return super().changelist_view(request, {**(extra_context or {}), **contexto})

    def _contexto_operador(self, request):
        """`(redireccion, contexto)`: pestañas de empresa, la elegida y su panorama.

        La ultima empresa elegida se recuerda en la sesion y se vuelve a poner en la
        URL; no se elige una por el operador (es una pantalla donde se escribe).
        """
        empresas = list(Empresa.objects.filter(activo=True).order_by('nombre'))
        por_slug = {e.slug: e for e in empresas}
        pedida = request.GET.get('empresa')

        if pedida in por_slug:
            request.session[self.SESION_EMPRESA] = pedida
        elif not pedida:
            recordada = request.session.get(self.SESION_EMPRESA)
            if recordada in por_slug and request.method == 'GET':
                consulta = request.GET.copy()
                consulta['empresa'] = recordada
                return HttpResponseRedirect(f'{request.path}?{consulta.urlencode()}'), None
        elif request.session.get(self.SESION_EMPRESA) == pedida:
            del request.session[self.SESION_EMPRESA]
        elegida = por_slug.get(pedida)

        con_pangas = set(
            Embarcacion.objects.filter(activa=True).values_list('empresa_id', flat=True)
        )
        sin_panga = dict(
            Reserva.objects.filter(estado=Reserva.Estado.PAGADA, embarcacion__isnull=True)
            .exclude(
                models.Q(servicio__estrategia_cupo='bajo_demanda') |
                models.Q(servicio__tipo_servicio='transporte')
            )
            .values_list('empresa_id').annotate(n=models.Count('pk'))
        )
        resto = request.GET.copy()
        resto.pop('empresa', None)
        resto.pop('p', None)

        def enlace(empresa):
            return f'{request.path}?{urlencode({**resto.dict(), "empresa": empresa.slug})}'

        pestanas = [
            {
                'nombre': e.nombre,
                'url': enlace(e),
                'activa': e == elegida,
                'aplica': e.pk in con_pangas,
                'sin_panga': sin_panga.get(e.pk, 0),
            }
            for e in empresas
        ]

        if elegida is None:
            estado = 'elegir'
        elif elegida.pk not in con_pangas:
            estado = 'sin_pangas'
        else:
            estado = 'normal'

        return None, {
            'agenda_pestanas': pestanas,
            'agenda_estado': estado,
            'agenda_empresa': elegida,
            'panorama': (
                armar_panorama(timezone.localdate(), elegida) if estado == 'normal' else None
            ),
        }

    def get_queryset(self, request):
        # `super()` aplica el filtro por empresa del mixin; se replica el criterio
        # de `Agenda.por_repartir()` sin perder el aislamiento. `embarcacion` y
        # `capitan` salen en el listado: sin `select_related` es una consulta por fila.
        qs = super().get_queryset(request)
        if scope.es_operador_plataforma(request.user) and self._es_listado(request):
            # El operador ve una empresa a la vez, la que eligio. Sin eleccion valida
            # no hay filas: ninguna empresa se reparte por defecto. Fuera del listado
            # (abrir una reserva) no aplica, ahi no viaja `?empresa=`.
            qs = qs.filter(empresa__slug=request.GET.get('empresa') or None)
        return qs.filter(
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
        # Lo que no tiene panga va primero: es el trabajo de esta pantalla. Dentro de
        # cada grupo, por fecha y hora, asi que los atrasados siguen arriba.
        return [models.F('embarcacion_id').asc(nulls_first=True), 'fecha', 'hora']

    def has_add_permission(self, request):
        # Una reserva se crea vendiendo, no se inventa desde aqui.
        return False

    def has_delete_permission(self, request, obj=None):
        # Una reserva se cancela, no se borra (ver docs/contexto-negocio.md).
        return False

    @admin.display(description='Fecha', ordering='fecha')
    def dia(self, obj):
        """"Sab 10 Oct", igual que los encabezados del panorama: una sola forma de
        decir el dia en toda la pantalla. El ano solo si no es el actual."""
        formato = 'D j M' if obj.fecha.year == timezone.localdate().year else 'D j M Y'
        return date_format(obj.fecha, formato)

    @admin.display(description='Avisado')
    def avisado(self, obj):
        """Si al cliente ya le salio el correo con su capitan y su panga.

        Importa porque un cambio posterior de capitan NO se reenvia solo: esa
        llamada la hace la vendedora, y para hacerla necesita saber que fue lo
        ultimo que el cliente leyo.

        Solo tiene sentido cuando ya hay panga: antes no hay nada que avisar, y una
        cruz roja en cada viaje pendiente le quitaba al rojo su significado.
        Gris y no rojo: "pendiente" es lo normal hasta que se asigna.
        """
        if obj.estado != Reserva.Estado.ASIGNADA:
            return '—'
        if obj.aviso_asignacion_enviado_en is not None:
            return format_html('<span style="color:#15803d">{}</span>', 'Enviado')
        return format_html('<span style="color:#6b7280">{}</span>', 'Pendiente')

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
