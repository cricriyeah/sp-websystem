from decimal import Decimal

from django import forms

from apps.fleet.enums import TipoServicio
from apps.tenancy import scope
from apps.bookings.models import Reserva, Vendedora
from apps.bookings.precio_sugerido import sugerir_precio
from apps.bookings.limites_servicio import limites_de_servicio

OPCIONES_YA_PAGO = [
    ('no', 'Aún no pagó — no aparta lugar en el cupo hasta que pague'),
    ('todo_transferencia', 'Pagó todo por transferencia — aparta el lugar ahora y revisa el cupo'),
    ('anticipo_transferencia', 'Pagó un anticipo por transferencia — aparta el lugar; el saldo se cobra el día del viaje'),
]


class AltaReservaForm(forms.ModelForm):
    """Formulario especializado para el alta manual de una Reserva en el backoffice.

    Aplica a ventas cerradas por WhatsApp o teléfono. Excluye campos técnicos y de
    registro web (deslinde, stripe, orden, etc.), deriva el estado y montos a partir
    de '¿Ya pagó?' y atribuye automáticamente a la vendedora en sesión.
    """

    ya_pago = forms.ChoiceField(
        choices=OPCIONES_YA_PAGO,
        widget=forms.RadioSelect,
        label='¿Ya pagó?',
        required=True,
    )
    monto_recibido = forms.DecimalField(
        required=False,
        min_value=Decimal('0'),
        decimal_places=2,
        label='Monto recibido (solo si es anticipo)',
    )

    class Meta:
        model = Reserva
        fields = [
            'nombre_cliente',
            'telefono_cliente',
            'correo_cliente',
            'servicio',
            'paquete',
            'fecha',
            'hora',
            'numero_personas',
            'aeropuerto',
            'fecha_salida',
            'inicio_paquete',
            'moneda',
            'precio_total',
            'embarcacion',
            'capitan',
            'vendedora',
            'empresa',
        ]

    def __init__(self, *args, usuario=None, empresa=None, perfil_vendedora=None, **kwargs):
        self.usuario = usuario
        self.empresa = empresa
        self.perfil_vendedora = perfil_vendedora
        super().__init__(*args, **kwargs)

        if self.empresa is None and getattr(self.instance, 'empresa_id', None):
            self.empresa = self.instance.empresa

        if self.perfil_vendedora is None and self.usuario and self.empresa:
            self.perfil_vendedora = Vendedora.objects.filter(
                usuario=self.usuario, empresa=self.empresa, activo=True
            ).first()

        es_operador = False
        es_jefe = False
        if self.usuario:
            es_operador = scope.es_operador_plataforma(self.usuario)
            es_jefe = self.usuario.groups.filter(name='Jefe').exists()

        # Solo el operador de plataforma puede elegir la empresa
        if not es_operador and 'empresa' in self.fields:
            del self.fields['empresa']

        # Vendedora no ve el campo de vendedora (se autoatribuye); jefe y operador sí lo ven
        if not (es_operador or es_jefe):
            if 'vendedora' in self.fields:
                del self.fields['vendedora']
            if self.perfil_vendedora:
                self.instance.vendedora = self.perfil_vendedora
        else:
            if 'vendedora' in self.fields:
                self.fields['vendedora'].required = False
                if self.empresa:
                    self.fields['vendedora'].queryset = Vendedora.objects.filter(
                        empresa=self.empresa, activo=True
                    )
                if self.perfil_vendedora and not self.initial.get('vendedora'):
                    self.fields['vendedora'].initial = self.perfil_vendedora

        # Mostrar límites del servicio en cada opción del selector
        if 'servicio' in self.fields:
            if es_operador:
                self.fields['servicio'].label_from_instance = (
                    lambda s: f"{s.nombre} ({s.empresa.nombre}) — {limites_de_servicio(s)['etiqueta']}"
                )
            else:
                self.fields['servicio'].label_from_instance = (
                    lambda s: f"{s.nombre} — {limites_de_servicio(s)['etiqueta']}"
                )

    def clean(self):
        cleaned_data = super().clean()

        # 1. Asignar empresa en la instancia si fue elegida por operador
        if cleaned_data.get('empresa'):
            self.instance.empresa = cleaned_data['empresa']

        # 2. Canal de origen siempre es WhatsApp en alta manual
        self.instance.canal_origen = Reserva.CanalOrigen.WHATSAPP
        cleaned_data['canal_origen'] = Reserva.CanalOrigen.WHATSAPP

        # 3. Vendedora: vendedora con perfil no elige; jefe/operador eligen opcionalmente
        es_operador = False
        es_jefe = False
        if self.usuario:
            es_operador = scope.es_operador_plataforma(self.usuario)
            es_jefe = self.usuario.groups.filter(name='Jefe').exists()

        if not (es_operador or es_jefe):
            if self.perfil_vendedora:
                self.instance.vendedora = self.perfil_vendedora
                cleaned_data['vendedora'] = self.perfil_vendedora
            else:
                self.instance.vendedora = None
        else:
            vendedora_elegida = cleaned_data.get('vendedora')
            self.instance.vendedora = vendedora_elegida

        # 4. Precio: si viene vacío, sugerir precio con las reglas de negocio
        precio_total = cleaned_data.get('precio_total')
        if precio_total is None:
            servicio = cleaned_data.get('servicio')
            paquete = cleaned_data.get('paquete')
            personas = cleaned_data.get('numero_personas')
            moneda = cleaned_data.get('moneda')
            fecha = cleaned_data.get('fecha')
            if (servicio or paquete) and personas and moneda:
                # `sugerir_precio` devuelve None cuando no hay sugerencia; un error real
                # se propaga en vez de esconderse como «sin sugerencia».
                sugerido = sugerir_precio(
                    servicio=servicio,
                    paquete=paquete,
                    numero_personas=personas,
                    moneda=moneda,
                    fecha=fecha,
                )
                if sugerido is not None:
                    precio_total = sugerido
                    cleaned_data['precio_total'] = precio_total
                    self.instance.precio_total = precio_total

        # 5. Consecuencias de ¿Ya pagó?
        ya_pago = cleaned_data.get('ya_pago')
        if ya_pago in ('todo_transferencia', 'anticipo_transferencia'):
            if precio_total is None:
                servicio = cleaned_data.get('servicio')
                if servicio and getattr(servicio, 'tipo_servicio', None) == TipoServicio.TRANSPORTE:
                    self.add_error(
                        'precio_total',
                        'Escribe el precio total o elige el tipo de traslado para que se sugiera.',
                    )
                else:
                    self.add_error('precio_total', 'Escribe el precio total: no se pudo sugerir para este servicio.')
            else:
                self.instance.precio_total = precio_total

        if ya_pago == 'no':
            self.instance.estado = Reserva.Estado.PENDIENTE_PAGO
            cleaned_data['estado'] = Reserva.Estado.PENDIENTE_PAGO
            self.instance.forma_pago = ''
            cleaned_data['forma_pago'] = ''
            self.instance.monto_transferencia = None
            cleaned_data['monto_transferencia'] = None
            self.instance.monto_pagado = None
            cleaned_data['monto_pagado'] = None
            if precio_total is not None:
                self.instance.precio_total = precio_total
        elif ya_pago == 'todo_transferencia':
            self.instance.estado = Reserva.Estado.PAGADA
            cleaned_data['estado'] = Reserva.Estado.PAGADA
            self.instance.forma_pago = Reserva.FormaPago.COMPLETO
            cleaned_data['forma_pago'] = Reserva.FormaPago.COMPLETO
            if precio_total is not None:
                self.instance.monto_transferencia = precio_total
                cleaned_data['monto_transferencia'] = precio_total
        elif ya_pago == 'anticipo_transferencia':
            monto_recibido = cleaned_data.get('monto_recibido')
            if monto_recibido is None:
                self.add_error('monto_recibido', 'Escribe el monto recibido para el anticipo.')
            elif monto_recibido <= Decimal('0'):
                self.add_error('monto_recibido', 'El monto recibido debe ser mayor a 0.')
            elif precio_total is not None and monto_recibido >= precio_total:
                self.add_error('monto_recibido', 'El anticipo debe ser menor al precio total.')
            else:
                self.instance.estado = Reserva.Estado.PAGADA
                cleaned_data['estado'] = Reserva.Estado.PAGADA
                self.instance.forma_pago = Reserva.FormaPago.ANTICIPO
                cleaned_data['forma_pago'] = Reserva.FormaPago.ANTICIPO
                self.instance.monto_transferencia = monto_recibido
                cleaned_data['monto_transferencia'] = monto_recibido

        return cleaned_data
