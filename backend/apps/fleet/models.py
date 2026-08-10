from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Tarifa(models.Model):
    """Singleton: precio unico del tour, no varia por clase de embarcacion
    (ver docs/contexto-negocio.md, seccion Embarcaciones). Editable solo por jefes."""

    precio = models.DecimalField(max_digits=10, decimal_places=2)
    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('La tarifa no se puede eliminar, solo editar.')

    def __str__(self):
        return f'Tarifa: ${self.precio} MXN'

    @classmethod
    def actual(cls):
        return cls.objects.first()


class Embarcacion(models.Model):
    class Clase(models.TextChoices):
        CHICA = 'chica', 'Chica (máx. 3 personas)'
        GRANDE = 'grande', 'Grande (máx. 6 personas)'

    nombre = models.CharField(max_length=100, unique=True)
    clase = models.CharField(max_length=10, choices=Clase.choices)
    capacidad_maxima = models.PositiveSmallIntegerField(
        help_text='Numero maximo de personas que puede llevar esta embarcacion.'
    )

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.get_clase_display()})'


class Capitan(models.Model):
    """Catalogo simple. No tiene usuario ni login: no forma parte del auth del sistema."""

    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
