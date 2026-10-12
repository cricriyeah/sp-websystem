"""Vista y formulario para generar el enlace de pago por WhatsApp.

Permite a la vendedora armar una URL del checkout web con los parametros
precargados (servicio/paquete, fecha, hora, personas, ref) para mandarselo
al cliente por WhatsApp y cobrar con tarjeta. No crea ninguna reserva ni
guarda datos en base de datos.
"""

from datetime import timedelta
from urllib.parse import quote, urlencode

from django import forms
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.utils import timezone

from apps.fleet.models import Paquete, Servicio
from apps.tenancy import scope
from apps.bookings.models import Vendedora


def obtener_telefono_marcable(telefono):
    """Importacion diferida de telefono_marcable para evitar ciclos de importacion con admin.py."""
    from apps.bookings.admin import telefono_marcable

    return telefono_marcable(telefono)


class EnlacePagoForm(forms.Form):
    """Formulario por GET para configurar el viaje que se enviara al cliente."""

    producto = forms.ChoiceField(
        label='Producto (servicio o paquete)',
        required=True,
        widget=forms.Select(attrs={
            'id': 'id_producto',
            'class': 'border border-base-300 rounded px-3 py-1.5 w-full dark:bg-base-800 dark:border-base-700',
        }),
    )
    fecha = forms.DateField(
        label='Fecha de salida',
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'border border-base-300 rounded px-3 py-1.5 w-full dark:bg-base-800 dark:border-base-700',
        }),
        help_text='Aplica solo para servicios (a partir de mañana).',
    )
    hora = forms.TimeField(
        label='Hora de salida (opcional)',
        required=False,
        widget=forms.TimeInput(attrs={
            'type': 'time',
            'class': 'border border-base-300 rounded px-3 py-1.5 w-full dark:bg-base-800 dark:border-base-700',
        }),
        help_text='Opcional. Dentro del horario del servicio.',
    )
    personas = forms.IntegerField(
        label='Número de personas',
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'min': 1,
            'class': 'border border-base-300 rounded px-3 py-1.5 w-full dark:bg-base-800 dark:border-base-700',
        }),
        help_text='Aplica solo para servicios (mínimo 1 hasta la capacidad máxima).',
    )
    idioma = forms.ChoiceField(
        label='Idioma del checkout',
        choices=[('es', 'Español'), ('en', 'English')],
        initial='es',
        required=True,
        widget=forms.Select(attrs={
            'class': 'border border-base-300 rounded px-3 py-1.5 w-full dark:bg-base-800 dark:border-base-700',
        }),
    )
    vendedora = forms.ChoiceField(
        label='Atribuir a vendedora',
        required=False,
        widget=forms.Select(attrs={
            'class': 'border border-base-300 rounded px-3 py-1.5 w-full dark:bg-base-800 dark:border-base-700',
        }),
        help_text='Selecciona quién recibe la atribución (código ref).',
    )
    telefono = forms.CharField(
        label='Teléfono del cliente (WhatsApp)',
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '612 123 4567',
            'class': 'border border-base-300 rounded px-3 py-1.5 w-full dark:bg-base-800 dark:border-base-700',
        }),
        help_text='Opcional. Para abrir el chat directo con el mensaje listo.',
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.tipo_producto = None
        self.instancia_producto = None
        self.codigo_ref = None

        user = getattr(request, 'user', None)
        es_operador = scope.es_operador_plataforma(user) if user else False
        empresa = scope.empresa_actual(request) if request else None

        # Opciones de producto: solo servicios activos vendibles sueltos y paquetes activos
        if es_operador:
            qs_servicios = (
                Servicio.objects.filter(activo=True, solo_en_paquete=False, empresa__activo=True)
                .select_related('empresa')
                .order_by('empresa__nombre', 'nombre')
            )
            opciones_servicios = [
                (f'servicio:{s.pk}', f'{s.nombre} ({s.empresa.nombre})')
                for s in qs_servicios
            ]
            qs_paquetes = (
                Paquete.objects.filter(activo=True, empresa_lider__activo=True)
                .select_related('empresa_lider', 'sede')
                .order_by('empresa_lider__nombre', 'nombre')
            )
            opciones_paquetes = [
                (f'paquete:{p.pk}', f'{p.nombre} ({p.empresa_lider.nombre})')
                for p in qs_paquetes
            ]
        else:
            if empresa:
                qs_servicios = (
                    Servicio.objects.filter(empresa=empresa, activo=True, solo_en_paquete=False)
                    .order_by('nombre')
                )
                qs_paquetes = (
                    Paquete.objects.filter(empresa_lider=empresa, activo=True)
                    .select_related('sede')
                    .order_by('nombre')
                )
            else:
                qs_servicios = Servicio.objects.none()
                qs_paquetes = Paquete.objects.none()

            opciones_servicios = [(f'servicio:{s.pk}', s.nombre) for s in qs_servicios]
            opciones_paquetes = [(f'paquete:{p.pk}', p.nombre) for p in qs_paquetes]

        choices_producto = [('', '---------')]
        if opciones_servicios:
            choices_producto.append(('Servicios', opciones_servicios))
        if opciones_paquetes:
            choices_producto.append(('Paquetes', opciones_paquetes))
        self.fields['producto'].choices = choices_producto

        # Perfil de vendedora: si la usuaria ya tiene perfil activo, la atribución es suya
        perfil_vendedora = None
        if user and not user.is_anonymous:
            if empresa:
                perfil_vendedora = Vendedora.objects.filter(usuario=user, empresa=empresa, activo=True).first()
            if not perfil_vendedora and not es_operador:
                perfil_vendedora = Vendedora.objects.filter(usuario=user, activo=True).first()
        self.perfil_vendedora = perfil_vendedora

        if perfil_vendedora:
            # Ocultamos el campo: la atribución es fija a quien está usando el admin
            self.fields['vendedora'].widget = forms.HiddenInput()
            self.fields['vendedora'].required = False
        else:
            # Jefe u operador: selector opcional de vendedoras activas
            if es_operador:
                qs_v = (
                    Vendedora.objects.filter(activo=True, empresa__activo=True)
                    .select_related('usuario', 'empresa')
                    .order_by('empresa__nombre', 'usuario__first_name', 'usuario__username')
                )
                opciones_v = [
                    (str(v.pk), f'{v.usuario.get_full_name() or v.usuario.username} ({v.codigo}) · {v.empresa.nombre}')
                    for v in qs_v
                ]
            elif empresa:
                qs_v = (
                    Vendedora.objects.filter(empresa=empresa, activo=True)
                    .select_related('usuario')
                    .order_by('usuario__first_name', 'usuario__username')
                )
                opciones_v = [
                    (str(v.pk), f'{v.usuario.get_full_name() or v.usuario.username} ({v.codigo})')
                    for v in qs_v
                ]
            else:
                opciones_v = []
            self.fields['vendedora'].choices = [('', 'Sin atribuir')] + opciones_v

    def clean(self):
        cleaned_data = super().clean()
        user = getattr(self.request, 'user', None)
        es_operador = scope.es_operador_plataforma(user) if user else False
        empresa = scope.empresa_actual(self.request) if self.request else None

        producto_raw = cleaned_data.get('producto')
        if not producto_raw:
            return cleaned_data

        try:
            tipo, pk_str = producto_raw.split(':', 1)
            pk_int = int(pk_str)
        except (ValueError, TypeError, AttributeError):
            self.add_error('producto', 'Selecciona un producto válido.')
            return cleaned_data

        # 1. Resolver y validar alcance del producto
        if tipo == 'servicio':
            if es_operador:
                servicio = Servicio.objects.filter(pk=pk_int, activo=True, solo_en_paquete=False).select_related('empresa').first()
            elif empresa:
                servicio = Servicio.objects.filter(pk=pk_int, empresa=empresa, activo=True, solo_en_paquete=False).select_related('empresa').first()
            else:
                servicio = None

            if not servicio:
                # No revelar existencia de servicios fuera de alcance
                self.add_error('producto', 'Selecciona un servicio válido.')
                return cleaned_data

            self.tipo_producto = 'servicio'
            self.instancia_producto = servicio
            empresa_producto = servicio.empresa

            # Validar fecha para servicios (debe ser de mañana en adelante)
            fecha = cleaned_data.get('fecha')
            if not fecha:
                self.add_error('fecha', 'La fecha es obligatoria para servicios.')
            else:
                manana = timezone.localdate() + timedelta(days=1)
                if fecha < manana:
                    self.add_error('fecha', 'La fecha debe ser a partir de mañana.')

            # Validar hora si viene especificada
            hora = cleaned_data.get('hora')
            if hora:
                ventana = servicio.ventana_horaria()
                if ventana:
                    apertura, cierre = ventana
                    if hora < apertura or hora > cierre:
                        self.add_error(
                            'hora',
                            f'La hora debe estar dentro del horario del servicio ({apertura.strftime("%H:%M")} a {cierre.strftime("%H:%M")}).',
                        )

            # Validar personas (entre 1 y el máximo)
            personas = cleaned_data.get('personas')
            if not personas or personas < 1:
                self.add_error('personas', 'El número de personas es obligatorio (mínimo 1).')
            else:
                max_personas = servicio.capacidad_maxima if servicio.capacidad_maxima and servicio.capacidad_maxima > 0 else 5
                if personas > max_personas:
                    self.add_error(
                        'personas',
                        f'El número de personas no puede superar la capacidad máxima ({max_personas}).',
                    )

        elif tipo == 'paquete':
            if es_operador:
                paquete = Paquete.objects.filter(pk=pk_int, activo=True).select_related('empresa_lider', 'sede').first()
            elif empresa:
                paquete = Paquete.objects.filter(pk=pk_int, empresa_lider=empresa, activo=True).select_related('empresa_lider', 'sede').first()
            else:
                paquete = None

            if not paquete:
                self.add_error('producto', 'Selecciona un paquete válido.')
                return cleaned_data

            self.tipo_producto = 'paquete'
            self.instancia_producto = paquete
            empresa_producto = paquete.empresa_lider

            # En paquetes no aplican fecha, hora ni personas en el enlace
            cleaned_data['fecha'] = None
            cleaned_data['hora'] = None
            cleaned_data['personas'] = None

        else:
            self.add_error('producto', 'Selecciona un producto válido.')
            return cleaned_data

        # 2. Atribucion (ref)
        if self.perfil_vendedora:
            if self.perfil_vendedora.empresa_id == empresa_producto.id:
                self.codigo_ref = self.perfil_vendedora.codigo
            else:
                perfil_otra = Vendedora.objects.filter(usuario=user, empresa=empresa_producto, activo=True).first()
                self.codigo_ref = perfil_otra.codigo if perfil_otra else None
        else:
            vendedora_id = cleaned_data.get('vendedora')
            if vendedora_id:
                vendedora_obj = Vendedora.objects.filter(pk=vendedora_id, activo=True).select_related('empresa').first()
                if not vendedora_obj:
                    self.add_error('vendedora', 'Selecciona una vendedora válida.')
                elif vendedora_obj.empresa_id != empresa_producto.id:
                    self.add_error('vendedora', 'La vendedora seleccionada no pertenece a la empresa del producto.')
                else:
                    self.codigo_ref = vendedora_obj.codigo
            else:
                self.codigo_ref = None

        return cleaned_data


def enlace_pago_view(modelo_admin, request):
    """Generador de enlace de pago por WhatsApp (GET, no escribe nada en base de datos)."""
    if not modelo_admin.has_add_permission(request):
        raise PermissionDenied

    hay_parametros = bool(request.GET)
    if hay_parametros:
        form = EnlacePagoForm(request.GET, request=request)
    else:
        form = EnlacePagoForm(request=request)

    base_frontend = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
    enlace = None
    whatsapp_url = None
    codigo_ref = None

    if hay_parametros and form.is_valid():
        codigo_ref = form.codigo_ref
        idioma = form.cleaned_data.get('idioma') or 'es'

        if base_frontend:
            if form.tipo_producto == 'servicio':
                servicio = form.instancia_producto
                params = {
                    'servicio': servicio.slug,
                    'empresa': servicio.empresa.slug,
                    'day': form.cleaned_data['fecha'].isoformat(),
                }
                if form.cleaned_data.get('hora'):
                    params['time'] = form.cleaned_data['hora'].strftime('%H:%M')
                params['people'] = form.cleaned_data['personas']
                if codigo_ref:
                    params['ref'] = codigo_ref
                enlace = f'{base_frontend}/{idioma}/reservar?{urlencode(params)}'

            elif form.tipo_producto == 'paquete':
                paquete = form.instancia_producto
                params = {
                    'paquete': paquete.slug,
                    'sede': paquete.sede.slug,
                }
                if codigo_ref:
                    params['ref'] = codigo_ref
                enlace = f'{base_frontend}/{idioma}/reservar?{urlencode(params)}'

            # Construccion del enlace a WhatsApp
            telefono = form.cleaned_data.get('telefono', '').strip()
            numero = obtener_telefono_marcable(telefono) if telefono else ''

            if idioma == 'en':
                mensaje = f'Hello, here is your link to book and pay by card: {enlace}'
            else:
                mensaje = f'Hola, aquí está tu enlace para reservar y pagar con tarjeta: {enlace}'

            if numero:
                whatsapp_url = f'https://wa.me/{numero}?text={quote(mensaje)}'
            else:
                whatsapp_url = f'https://wa.me/?text={quote(mensaje)}'

    contexto = {
        **modelo_admin.admin_site.each_context(request),
        'opts': modelo_admin.model._meta,
        'title': 'Enlace de pago',
        'titulo': 'Enlace de pago',
        'form': form,
        'enlace': enlace,
        'whatsapp_url': whatsapp_url,
        'codigo_ref': codigo_ref,
        'sin_atribucion': form.is_bound and form.is_valid() and not codigo_ref,
        'sin_frontend_url': bool(hay_parametros and form.is_valid() and not base_frontend),
        'mostrar_resultado': bool(enlace),
    }

    return TemplateResponse(request, 'bookings/enlace_pago.html', contexto)


# Alias con el estilo analogo a respuesta_precio_sugerido
respuesta_enlace_pago = enlace_pago_view
