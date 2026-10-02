from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Sede(models.Model):
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    zona_horaria = models.CharField(max_length=50, default='America/Mazatlan')
    tipo_cambio_usd = models.DecimalField(
        max_digits=8, decimal_places=4, default=Decimal('18.0000'), db_default=Decimal('18.0000'),
        validators=[MinValueValidator(Decimal('0.0001'))],
        help_text='Pesos por 1 dólar. Todos los precios se guardan en pesos; el precio en dólares se '
                  'calcula con este valor y se redondea hacia arriba al dólar entero.',
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'sede'
        verbose_name_plural = 'sedes'

    def __str__(self):
        return self.nombre


class Empresa(models.Model):
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='empresas')
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(
        max_length=150, unique=True,
        help_text='Inmutable despues de creada: la URL del webhook de Stripe '
                   'configurada en su Dashboard depende de este valor.',
    )
    activo = models.BooleanField(default=True)
    exclusiva = models.BooleanField(
        default=False,
        help_text='Si esta Empresa opera en exclusiva su Sede. Informativo en v1.',
    )
    # Decision v1 explicita (Revision 7, N7-F, enmienda a ADR-002 SS2): llaves en
    # tabla, sin gestor de secretos externo. Llaves de prueba pre-lanzamiento.
    # Nunca logueadas (ver checks.py). Disparador de reversion: antes de la
    # primera llave sk_live_ -- ver ADR-002.
    stripe_secret_key = models.CharField(max_length=200, blank=True)
    stripe_webhook_secret = models.CharField(max_length=200, blank=True)
    stripe_publishable_key = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'empresa'
        verbose_name_plural = 'empresas'

    def __str__(self):
        return self.nombre

    def clean(self):
        errores = {}
        if self.stripe_secret_key and not self.stripe_secret_key.startswith('sk_'):
            errores['stripe_secret_key'] = "Debe empezar con 'sk_'."
        if self.stripe_webhook_secret and not self.stripe_webhook_secret.startswith('whsec_'):
            errores['stripe_webhook_secret'] = "Debe empezar con 'whsec_'."
        if self.stripe_publishable_key and not self.stripe_publishable_key.startswith('pk_'):
            errores['stripe_publishable_key'] = "Debe empezar con 'pk_'."
        if errores:
            raise ValidationError(errores)


class MembresiaEmpresa(models.Model):
    class Rol(models.TextChoices):
        JEFE = 'JEFE', 'Jefe'
        VENDEDORA = 'VENDEDORA', 'Vendedora'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='membresias',
    )
    # on_delete=PROTECT: 'empresa' cae bajo la regla global de este plan (todo FK
    # llamado `empresa` lleva PROTECT) -- borrar una Empresa no debe poder borrar
    # en cascada sus membresias sin que alguien las revise primero.
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='membresias')
    rol = models.CharField(max_length=10, choices=Rol.choices)

    class Meta:
        unique_together = ('user', 'empresa')
        verbose_name = 'membresia de empresa'
        verbose_name_plural = 'membresias de empresa'

    def __str__(self):
        return f'{self.user} - {self.empresa} ({self.get_rol_display()})'
