from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Tarifa(models.Model):
    """Singleton: precio unico del tour, no varia por clase de embarcacion
    (ver docs/contexto-negocio.md, seccion Embarcaciones). Editable solo por jefes.

    Se cobra en pesos o dolares (doc: "Monedas: pesos y dolares"). Son dos precios
    de lista independientes, no una conversion: el negocio fija cada uno a mano y
    el sistema nunca aplica un tipo de cambio. Sin `precio_usd` el checkout solo
    ofrece pesos."""

    precio = models.DecimalField(
        max_digits=10, decimal_places=2, help_text='Precio del tour en pesos (MXN).'
    )
    precio_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Precio del tour en dolares. Vacio = no se ofrece pago en USD.',
    )
    precio_persona_extra = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Cargo en pesos por cada persona arriba de las incluidas en el '
                  'precio del viaje. 0 = el precio no cambia con el numero de personas.',
    )
    precio_persona_extra_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='El mismo cargo en dolares. Vacio = no se puede cobrar en USD un '
                  'viaje que lleve personas extra.',
    )
    precio_lunch = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Precio del lunch en pesos, POR PERSONA. El menu es fijo y cambia '
                  'cada semana, asi que este monto se actualiza aqui.',
    )
    precio_lunch_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='El mismo precio del lunch en dolares, por persona.',
    )
    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, force_insert=False, **kwargs):
        # Siempre la misma fila. Se ignora force_insert a proposito: un segundo
        # Tarifa.objects.create() debe actualizar el precio, no reventar con
        # IntegrityError sobre pk=1.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('La tarifa no se puede eliminar, solo editar.')

    def __str__(self):
        return f'Tarifa: ${self.precio} MXN'

    @classmethod
    def actual(cls):
        return cls.objects.first()

    def precio_en(self, moneda):
        """Precio de lista en la moneda pedida, o None si no esta configurado."""
        return self.precio if moneda == 'MXN' else self.precio_usd

    def persona_extra_en(self, moneda):
        """Cargo por persona adicional en esa moneda. None = sin configurar."""
        return self.precio_persona_extra if moneda == 'MXN' else self.precio_persona_extra_usd

    def lunch_en(self, moneda):
        """Precio del lunch por persona en esa moneda. None = sin configurar."""
        return self.precio_lunch if moneda == 'MXN' else self.precio_lunch_usd


class Embarcacion(models.Model):
    class Clase(models.TextChoices):
        # Sin cifra en la etiqueta a proposito: la capacidad vive en
        # `capacidad_maxima` y unicamente ahi. Decian "(max. 3 personas)" y
        # "(max. 6 personas)" — la segunda era falsa y nadie se entero, porque el
        # numero de verdad estaba en otro campo. `Clase` sigue existiendo porque
        # el negocio piensa en chicas y grandes y la copia del sitio las nombra
        # asi; solo deja de cargar un dato que no le toca.
        CHICA = 'chica', 'Chica'
        GRANDE = 'grande', 'Grande'

    nombre = models.CharField(max_length=100, unique=True)
    clase = models.CharField(max_length=10, choices=Clase.choices)
    capacidad_maxima = models.PositiveSmallIntegerField(
        help_text='Numero maximo de personas que puede llevar esta embarcacion.'
    )
    activa = models.BooleanField(
        default=True,
        help_text='Desmarcalo para sacar la panga de la flota sin borrarla (vendida, '
                  'fuera de servicio). Una panga inactiva deja de contar para el cupo '
                  'pero conserva los viajes historicos que tiene asignados. Mismo '
                  'patron que Vendedora.activo: borrarla dejaria viajes sin panga.',
    )

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        # Con la capacidad, porque el selector de la agenda es donde se asigna una
        # panga a un grupo y ahi hace falta saber cuanta gente lleva.
        return f'{self.nombre} ({self.get_clase_display()}, max. {self.capacidad_maxima})'


class Capitan(models.Model):
    """Catalogo simple. No tiene usuario ni login: no forma parte del auth del sistema."""

    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
