from collections import defaultdict
from datetime import timedelta

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


class ExtrasItem(models.Model):
    """Catalogo de extras del checkout: brunch, licencia, carnada. Editable solo
    por jefes, igual que `Tarifa` (es precio, informacion financiera).

    Sin fechas de vigencia a proposito: el precio vigente se edita a mano,
    igual que ya se hace con `Tarifa`, y cada reserva congela su propio precio
    al pagar (`bookings.ReservaExtra.precio_unitario`) — eso ya resuelve lo que
    una tabla de historico resolveria, sin la tabla.
    """

    class Tipo(models.TextChoices):
        BRUNCH = 'brunch', 'Brunch'
        LICENCIA = 'licencia', 'Licencia de pesca'
        CARNADA = 'carnada', 'Carnada'
        OTRO = 'otro', 'Otro'

    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, help_text='Precio en pesos (MXN).')
    precio_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Precio en dolares. Vacio = no se ofrece en USD.',
    )
    cobrar_por_persona = models.BooleanField(
        default=True,
        help_text='Marcado: el precio se multiplica por el numero de personas de '
                  'la reserva (igual que el brunch). Sin marcar: precio plano, se '
                  'cobra una sola vez por reserva.',
    )
    preseleccionado = models.BooleanField(
        default=False,
        help_text='Viene marcado por defecto en el checkout (licencia y carnada).',
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['tipo', 'nombre']
        verbose_name = 'extra del checkout'
        verbose_name_plural = 'extras del checkout'

    def __str__(self):
        return self.nombre

    def precio_en(self, moneda):
        return self.precio if moneda == 'MXN' else self.precio_usd


class TransportePrecio(models.Model):
    """Precio de traslado por zona. Dos filas fijas: centro y periferia."""

    class Zona(models.TextChoices):
        CENTRO = 'centro', 'Centro'
        PERIFERIA = 'periferia', 'Periferia'

    zona = models.CharField(max_length=10, choices=Zona.choices, unique=True)
    precio_base = models.DecimalField(max_digits=10, decimal_places=2, help_text='Precio en pesos (MXN).')
    precio_base_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Precio en dolares. Vacio = no se ofrece en USD.',
    )
    recargo_grupo = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Se suma al precio base desde `min_personas_recargo` personas.',
    )
    recargo_grupo_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    min_personas_recargo = models.PositiveSmallIntegerField(default=4)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['zona']
        verbose_name = 'precio de transporte'
        verbose_name_plural = 'precios de transporte'

    def __str__(self):
        return f'Transporte {self.get_zona_display()}: ${self.precio_base} MXN'

    def precio_en(self, moneda):
        return self.precio_base if moneda == 'MXN' else self.precio_base_usd

    def recargo_en(self, moneda):
        return self.recargo_grupo if moneda == 'MXN' else self.recargo_grupo_usd


class PuntoEncuentro(models.Model):
    """Catalogo de hoteles/hospedajes conocidos en La Paz, con su zona ya
    clasificada — evita depender de geocoding para una direccion libre."""

    nombre = models.CharField(max_length=150)
    zona = models.CharField(max_length=10, choices=TransportePrecio.Zona.choices)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'punto de encuentro'
        verbose_name_plural = 'puntos de encuentro'

    def __str__(self):
        return f'{self.nombre} ({self.get_zona_display()})'


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


class EmbarcacionNoDisponible(models.Model):
    """Una panga que no puede salir un dia concreto: mantenimiento, motor, lo que sea.

    Se registra **que falta**, no cuantas hay. Un conteo ("hoy hay 7") es un dato
    que nadie puede auditar despues; "la Lupita esta en mantenimiento el jueves"
    si. Sin registro para una fecha, ese dia esta la flota activa completa.

    No se confunde con `CupoDiario` (en `apps/bookings`), que es un tope de viajes
    que decide el negocio: son dos cosas distintas y meterlas en un solo numero las
    volveria imposibles de separar. Un dia puede tener las 10 pangas y un
    `CupoDiario` de 6 porque no hay capitanes; o el tope de 10 y solo 7 pangas a
    flote.
    """

    fecha = models.DateField()
    embarcacion = models.ForeignKey(
        # PROTECT: si esta panga tiene historial de bajas, borrarla dejaria
        # registros huerfanos. Para sacarla de la flota se desmarca `activa`.
        Embarcacion, on_delete=models.PROTECT, related_name='no_disponibles',
    )
    motivo = models.CharField(
        max_length=200, blank=True,
        help_text='Mantenimiento, motor descompuesto, prestada. Opcional.',
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='embarcaciones_dadas_de_baja',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('fecha', 'embarcacion')
        ordering = ['-fecha', 'embarcacion__nombre']
        verbose_name = 'embarcacion no disponible'
        verbose_name_plural = 'embarcaciones no disponibles'

    def __str__(self):
        return f'{self.embarcacion.nombre} fuera el {self.fecha}'


def capacidades_por_fecha(desde, hasta):
    """Capacidad de cada panga que puede salir, por dia, de mayor a menor.

    `{fecha: [5, 3, 3, ...]}` con una entrada por cada dia del rango, incluidos
    los dias en que no falta ninguna.

    Son **dos consultas para todo el rango**, no una por dia: de aqui cuelga la
    busqueda de los proximos 90 dias del checkout, y esa busqueda ya murio una vez
    por hacer una peticion por dia (ver bookings.proxima_fecha_disponible).

    La flota no sabe nada de reservas a proposito: esto responde que hay a flote,
    no que esta vendido.
    """
    activas = list(Embarcacion.objects.filter(activa=True).values_list('id', 'capacidad_maxima'))

    fuera = defaultdict(set)
    for fecha, embarcacion_id in EmbarcacionNoDisponible.objects.filter(
        fecha__range=(desde, hasta)
    ).values_list('fecha', 'embarcacion_id'):
        fuera[fecha].add(embarcacion_id)

    dias = (hasta - desde).days + 1
    return {
        fecha: sorted(
            (capacidad for pk, capacidad in activas if pk not in fuera[fecha]), reverse=True
        )
        for fecha in (desde + timedelta(days=i) for i in range(dias))
    }


def capacidades_disponibles(fecha):
    """Las capacidades a flote ese dia, de mayor a menor.

    Es el caso de un dia de `capacidades_por_fecha`, y se implementa asi para que
    la ruta de una fecha y la de 90 dias no puedan discrepar nunca.
    """
    return capacidades_por_fecha(fecha, fecha)[fecha]
