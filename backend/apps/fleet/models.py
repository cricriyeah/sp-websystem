from django.db import models


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
