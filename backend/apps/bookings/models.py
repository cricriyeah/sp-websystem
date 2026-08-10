from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.fleet.models import Capitan, Embarcacion

VENTANA_SALIDA_INICIO = time(5, 0)
VENTANA_SALIDA_FIN = time(7, 0)

# Capacidad operativa por defecto (8 a 10 viajes/dia, ver docs/contexto-negocio.md).
# Los jefes/vendedora cierran o reducen un dia especifico creando un CupoDiario.
CUPO_MAXIMO_DEFAULT = 10

# Solo estas cuentan contra el cupo: una reserva pendiente_pago (checkout iniciado
# pero no pagado) no debe bloquear el cupo de otro cliente.
ESTADOS_QUE_OCUPAN_CUPO = ['pagada', 'asignada', 'completada']


def validar_ventana_salida(value):
    if not (VENTANA_SALIDA_INICIO <= value <= VENTANA_SALIDA_FIN):
        raise ValidationError('La hora de salida debe estar entre las 5:00 y las 7:00 am.')


class CupoDiario(models.Model):
    """Override manual del cupo maximo de viajes para un dia especifico.
    Sin registro para un dia -> aplica CUPO_MAXIMO_DEFAULT."""

    fecha = models.DateField(unique=True)
    cupo_maximo = models.PositiveSmallIntegerField(
        help_text='Cupo maximo de viajes para este dia. Usalo para cerrar o reducir '
                   'el dia cuando se sepa que van a faltar embarcaciones.'
    )

    class Meta:
        ordering = ['fecha']

    def __str__(self):
        return f'{self.fecha}: {self.cupo_maximo} viajes'


def cupo_maximo_del_dia(fecha):
    override = CupoDiario.objects.filter(fecha=fecha).first()
    return override.cupo_maximo if override else CUPO_MAXIMO_DEFAULT


def validar_cupo_diario(fecha, excluir_pk=None):
    """Motor unico de validacion de cupo. Debe usarse tanto para el flujo de pago
    de la web como para la creacion/edicion manual de Reserva (ver backend/CLAUDE.md)."""
    ocupadas = Reserva.objects.filter(fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO)
    if excluir_pk is not None:
        ocupadas = ocupadas.exclude(pk=excluir_pk)
    if ocupadas.count() >= cupo_maximo_del_dia(fecha):
        raise ValidationError(f'No hay cupo disponible para el {fecha}: se alcanzo el maximo de viajes del dia.')


class Reserva(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE_PAGO = 'pendiente_pago', 'Pendiente de pago'
        PAGADA = 'pagada', 'Pagada, sin asignar'
        ASIGNADA = 'asignada', 'Asignada'
        CANCELADA = 'cancelada', 'Cancelada (mal clima)'
        COMPLETADA = 'completada', 'Completada'

    class CanalOrigen(models.TextChoices):
        WEB = 'web', 'Web'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    class Moneda(models.TextChoices):
        MXN = 'MXN', 'Pesos mexicanos'
        USD = 'USD', 'Dolares'

    class FormaPago(models.TextChoices):
        COMPLETO = 'completo', '100% en linea'
        ANTICIPO = 'anticipo', '30% anticipo en linea, resto en efectivo'

    # Datos del viaje
    fecha = models.DateField()
    hora = models.TimeField(validators=[validar_ventana_salida])
    numero_personas = models.PositiveSmallIntegerField()

    # Datos del cliente (no se pide peso ni si sabe nadar, ver docs/contexto-negocio.md)
    nombre_cliente = models.CharField(max_length=150)
    telefono_cliente = models.CharField(max_length=20)
    correo_cliente = models.EmailField()

    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE_PAGO)
    canal_origen = models.CharField(max_length=10, choices=CanalOrigen.choices)

    # Cobro (Stripe, cuenta estandar — ver docs/contexto-negocio.md). precio_total
    # es el tour + amenidades elegidas, calculado en el servidor al crear el pago,
    # nunca confiado del cliente. monto_pagado es lo efectivamente cobrado por
    # Stripe (100% o el 30% de anticipo).
    moneda = models.CharField(max_length=3, choices=Moneda.choices, default=Moneda.MXN)
    forma_pago = models.CharField(max_length=10, choices=FormaPago.choices, blank=True)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True)

    # Quedan vacios hasta que la vendedora asigna manualmente desde su panel.
    embarcacion = models.ForeignKey(
        Embarcacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas'
    )
    capitan = models.ForeignKey(
        Capitan, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas'
    )

    # Unica causa de cancelacion con reembolso es mal clima (ver docs/contexto-negocio.md).
    # El capitan avisa por fuera del sistema; quien ejecuta la cancelacion aqui es
    # la vendedora o los jefes.
    motivo_cancelacion = models.TextField(blank=True)
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reservas_canceladas',
    )
    cancelada_en = models.DateTimeField(null=True, blank=True)
    reembolsada = models.BooleanField(default=False)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha', '-hora']

    def __str__(self):
        return f'{self.nombre_cliente} — {self.fecha} {self.hora}'

    def clean(self):
        if self.estado in ESTADOS_QUE_OCUPAN_CUPO:
            validar_cupo_diario(self.fecha, excluir_pk=self.pk)
        if self.estado != self.Estado.CANCELADA and (self.cancelada_por_id or self.cancelada_en):
            raise ValidationError('cancelada_por/cancelada_en solo aplican cuando estado es cancelada.')
