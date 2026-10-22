from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, validate_email
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


class Aeropuerto(models.Model):
    """Un aeropuerto al que un paquete puede traer a la clienta. Cada sede declara los que cubre: el paquete
    de una sede solo ofrece (y solo acepta) los aeropuertos de esa sede. Lo administra el operador de plataforma."""

    codigo = models.SlugField(
        max_length=10, unique=True,
        help_text='Clave corta en minúsculas, la que guarda cada reserva (por ejemplo lap, sjd). No se cambia una vez en uso.',
    )
    nombre = models.CharField(max_length=150, help_text='Como lo ve la clienta, por ejemplo «La Paz (LAP)».')
    sedes = models.ManyToManyField(
        Sede, related_name='aeropuertos', blank=True,
        help_text='Las sedes con traslado a este aeropuerto. Sin sedes, no se ofrece en ningún lado.',
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'aeropuerto'
        verbose_name_plural = 'aeropuertos'

    def __str__(self):
        return self.nombre

    @classmethod
    def de_la_sede(cls, sede):
        """Los aeropuertos activos que cubre la sede, por nombre."""
        return cls.objects.filter(activo=True, sedes=sede).order_by('nombre')


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
    correos_aviso = models.CharField(
        max_length=300, blank=True,
        help_text='A quien se le avisa por correo cada vez que entra una reserva pagada '
                  'de esta Empresa. Varias direcciones separadas por coma. Vacio = no se avisa.',
    )

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
        for correo in self.lista_correos_aviso():
            try:
                validate_email(correo)
            except ValidationError:
                errores['correos_aviso'] = f'"{correo}" no es un correo valido.'
                break
        if errores:
            raise ValidationError(errores)

    def lista_correos_aviso(self):
        return [c.strip() for c in self.correos_aviso.split(',') if c.strip()]


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

    def clean(self):
        # Los grupos Jefe/Vendedora de Django son globales: con roles distintos en dos
        # empresas la cuenta recibiria la union de permisos de modelo (p.ej. editar el
        # catalogo en una empresa donde solo es vendedora). Por eso un usuario tiene el
        # mismo rol en todas sus empresas.
        super().clean()
        if self.user_id is None or not self.rol:
            return
        otro_rol = (MembresiaEmpresa.objects
                    .filter(user_id=self.user_id).exclude(pk=self.pk).exclude(rol=self.rol)
                    .select_related('empresa').first())
        if otro_rol is not None:
            raise ValidationError({'rol': (
                f'Este usuario ya es {otro_rol.get_rol_display()} en {otro_rol.empresa}. '
                'Un usuario debe tener el mismo rol en todas sus empresas.'
            )})

    def __str__(self):
        return f'{self.user} - {self.empresa} ({self.get_rol_display()})'
