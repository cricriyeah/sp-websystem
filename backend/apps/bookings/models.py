from datetime import time

from django.core.exceptions import ValidationError
from django.db import models

from apps.fleet.models import Capitan, Embarcacion

VENTANA_SALIDA_INICIO = time(5, 0)
VENTANA_SALIDA_FIN = time(7, 0)


def validar_ventana_salida(value):
    if not (VENTANA_SALIDA_INICIO <= value <= VENTANA_SALIDA_FIN):
        raise ValidationError('La hora de salida debe estar entre las 5:00 y las 7:00 am.')


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

    # Quedan vacios hasta que la vendedora asigna manualmente desde su panel.
    embarcacion = models.ForeignKey(
        Embarcacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas'
    )
    capitan = models.ForeignKey(
        Capitan, on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas'
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha', '-hora']

    def __str__(self):
        return f'{self.nombre_cliente} — {self.fecha} {self.hora}'
