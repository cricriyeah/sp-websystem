from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction

from .enums import (
    EstrategiaCupo,
    EstrategiaPrecio,
    ModoOcupacion,
    TipoServicio,
    TipoTraslado,
    Zona,
)


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
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='tarifa')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['empresa'], name='tarifa_unica_por_empresa'),
        ]

    def save(self, *args, force_insert=False, **kwargs):
        # Una tarifa por Empresa, no una tarifa por sistema: un segundo
        # Tarifa.objects.create(empresa=X) debe actualizar el precio de X, no
        # reventar con IntegrityError sobre la UniqueConstraint de arriba.
        if not self.pk:
            try:
                with transaction.atomic():
                    existente = (
                        Tarifa.objects.select_for_update()
                        .filter(empresa=self.empresa)
                        .first()
                    )
                    if existente:
                        self.pk = existente.pk
                    super().save(*args, **kwargs)
            except IntegrityError:
                # Carrera: otra transacción insertó la tarifa en paralelo.
                # Reintentamos asociando el pk de la tarifa existente.
                existente = Tarifa.objects.filter(empresa=self.empresa).first()
                if existente:
                    self.pk = existente.pk
                    super().save(*args, **kwargs)
                else:
                    raise
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('La tarifa no se puede eliminar, solo editar.')

    def __str__(self):
        return f'Tarifa de {self.empresa}: ${self.precio} MXN'

    @classmethod
    def de(cls, empresa):
        return cls.objects.filter(empresa=empresa).first()

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
    cantidad_editable = models.BooleanField(
        default=False,
        help_text='Si esta marcado, el checkout deja elegir cuantas personas del '
                  'grupo lo necesitan (ej. licencia: alguien puede ya traer la suya '
                  'tramitada aparte), en vez de aplicarlo a todo el grupo. Solo tiene '
                  'sentido junto con "Cobrar por persona".',
    )
    activo = models.BooleanField(default=True)
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='extras_items')

    class Meta:
        ordering = ['tipo', 'nombre']
        verbose_name = 'extra del checkout'
        verbose_name_plural = 'extras del checkout'

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.cantidad_editable and not self.cobrar_por_persona:
            raise ValidationError({
                'cantidad_editable': 'No tiene sentido sin "Cobrar por persona": un '
                                     'precio plano no se reparte por cantidad de gente.',
            })

    def precio_en(self, moneda):
        return self.precio if moneda == 'MXN' else self.precio_usd


class TransporteTarifa(models.Model):
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='tarifas_transporte')
    tipo_traslado = models.CharField(max_length=25, choices=TipoTraslado.choices)
    zona = models.CharField(max_length=10, choices=Zona.choices, blank=True, default='')  # '' salvo redondo_actividad
    personas_min = models.PositiveSmallIntegerField(default=1)
    personas_max = models.PositiveSmallIntegerField(null=True, blank=True)  # None = sin tope superior
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    precio_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['empresa', 'tipo_traslado', 'zona', 'personas_min']
        verbose_name = 'tarifa de transporte'
        verbose_name_plural = 'tarifas de transporte'
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'tipo_traslado', 'zona', 'personas_min'],
                                    name='transportetarifa_unica'),
            models.CheckConstraint(
                name='transportetarifa_zona_solo_actividad',
                condition=(models.Q(tipo_traslado='redondo_actividad') & ~models.Q(zona='')) |
                          (~models.Q(tipo_traslado='redondo_actividad') & models.Q(zona='')),
            ),
        ]

    def __str__(self):
        zona_str = f' ({self.get_zona_display()})' if self.zona else ''
        return f'{self.get_tipo_traslado_display()}{zona_str} [{self.personas_min}-{self.personas_max or "∞"}p]: ${self.precio} MXN'

    def clean(self):
        if self.tipo_traslado == TipoTraslado.REDONDO_ACTIVIDAD and not self.zona:
            raise ValidationError({'zona': 'Redondo actividad requiere zona.'})
        if self.tipo_traslado != TipoTraslado.REDONDO_ACTIVIDAD and self.zona:
            raise ValidationError({'zona': 'Solo redondo actividad lleva zona.'})
        if self.personas_max is not None and self.personas_max < self.personas_min:
            raise ValidationError({'personas_max': 'Debe ser ≥ personas_min.'})

    def precio_en(self, moneda):
        return self.precio if (moneda or 'MXN').upper() == 'MXN' else self.precio_usd


class PuntoEncuentro(models.Model):
    """Catalogo de hoteles/hospedajes conocidos en La Paz, con su zona ya
    clasificada — evita depender de geocoding para una direccion libre."""

    nombre = models.CharField(max_length=150)
    zona = models.CharField(max_length=10, choices=Zona.choices)
    activo = models.BooleanField(default=True)
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='puntos_encuentro')

    class Meta:
        ordering = ['nombre']
        verbose_name = 'punto de encuentro'
        verbose_name_plural = 'puntos de encuentro'

    def __str__(self):
        return f'{self.nombre} ({self.get_zona_display()})'


class CodigoPromocional(models.Model):
    """Codigo de descuento aplicable en el checkout. Editable solo por jefes —
    es dato financiero, igual que `Tarifa` y `ExtrasItem`: la vendedora no
    tiene permisos sobre este modelo (ver `setup_roles`).

    El descuento se calcula y se aplica siempre en el servidor
    (`apps/payments/pricing.py`); el checkout nunca manda mas que el string
    del codigo. Sin tabla de auditoria de usos aparte a proposito: cada uso
    ya deja su rastro en la `Reserva` que lo aplico
    (`bookings.Reserva.codigo_promocional`), mismo principio que ya usa el
    cupo diario (`ESTADOS_QUE_OCUPAN_CUPO`) y el panel de finanzas — un libro
    paralelo de usos solo puede acabar descuadrado con la reserva real. Ver
    `apps/bookings/models.py` (`codigo_promocional_valido`) para donde se
    cuentan esos usos.
    """

    codigo = models.CharField(max_length=20)
    descripcion = models.CharField(
        max_length=200, blank=True, help_text='Uso interno, no se muestra al cliente.'
    )
    porcentaje_descuento = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100'))],
    )
    activo = models.BooleanField(default=True)
    fecha_inicio = models.DateTimeField(null=True, blank=True, help_text='Vacio = vigente desde ya.')
    fecha_fin = models.DateTimeField(null=True, blank=True, help_text='Vacio = sin fecha de expiracion.')
    usos_maximos = models.PositiveIntegerField(null=True, blank=True, help_text='Vacio = sin limite.')
    usos_maximos_por_cliente = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text='Por correo del cliente. Vacio = sin limite.',
    )
    # Dos campos, no uno con tipo de cambio: mismo patron que Tarifa.precio/
    # precio_usd — el negocio fija cada minimo a mano, sin conversion (ver
    # docs/contexto-negocio.md, pesos y dolares nunca se suman).
    monto_minimo = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Minimo en pesos para que aplique. Vacio = sin minimo.',
    )
    monto_minimo_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Minimo en dolares. Vacio = sin minimo en esa moneda.',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='codigos_promocionales')

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'codigo promocional'
        verbose_name_plural = 'codigos promocionales'
        constraints = [
            models.UniqueConstraint(fields=['codigo', 'empresa'], name='codigopromocional_codigo_unico_por_empresa'),
        ]

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        # Normalizado aqui (no solo en el form del admin) para que tambien
        # quede consistente si algo lo crea desde el shell o un fixture.
        self.codigo = self.codigo.strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio >= self.fecha_fin:
            raise ValidationError({'fecha_fin': 'Debe ser posterior a la fecha de inicio.'})

    def monto_minimo_en(self, moneda):
        return self.monto_minimo if moneda == 'MXN' else self.monto_minimo_usd


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

    nombre = models.CharField(max_length=100)
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
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='embarcaciones')

    class Meta:
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['nombre', 'empresa'], name='embarcacion_nombre_unico_por_empresa'),
        ]

    def __str__(self):
        # Con la capacidad, porque el selector de la agenda es donde se asigna una
        # panga a un grupo y ahi hace falta saber cuanta gente lleva.
        return f'{self.nombre} ({self.get_clase_display()}, max. {self.capacidad_maxima})'


class Capitan(models.Model):
    """Catalogo simple. No tiene usuario ni login: no forma parte del auth del sistema."""

    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20)
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='capitanes')

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
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='embarcaciones_no_disponibles')

    class Meta:
        unique_together = ('fecha', 'embarcacion')
        ordering = ['-fecha', 'embarcacion__nombre']
        verbose_name = 'embarcacion no disponible'
        verbose_name_plural = 'embarcaciones no disponibles'

    def __str__(self):
        return f'{self.embarcacion.nombre} fuera el {self.fecha}'


class Servicio(models.Model):
    """Experiencia vendible en una sede/empresa.

    Define estrategia de cupo, estrategia de precio, modo de ocupación y tarifas base.
    """
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='servicios')
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150)
    tipo_servicio = models.CharField(
        max_length=20, choices=TipoServicio.choices, default=TipoServicio.PESCA,
    )
    estrategia_cupo = models.CharField(
        max_length=20, choices=EstrategiaCupo.choices, default=EstrategiaCupo.POR_RECURSO_DIA,
    )
    estrategia_precio = models.CharField(
        max_length=20, choices=EstrategiaPrecio.choices, default=EstrategiaPrecio.POR_GRUPO,
    )
    modo_ocupacion = models.CharField(
        max_length=20, choices=ModoOcupacion.choices, default=ModoOcupacion.EXCLUSIVO,
    )
    porcentaje_anticipo = models.PositiveSmallIntegerField(
        default=30,
        help_text='% del total que se cobra en línea. 30=anticipo, 100=completo.',
    )
    precio_base = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Precio base del servicio en MXN.'
    )
    precio_base_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Precio base del servicio en USD. Opcional.'
    )
    precio_persona_extra = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Cargo por persona adicional arriba del cupo incluido en MXN.'
    )
    precio_persona_extra_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Cargo por persona adicional arriba del cupo incluido en USD.'
    )
    personas_incluidas = models.PositiveSmallIntegerField(
        default=3,
        help_text='Cantidad de personas incluidas en el precio base antes de cobrar recargo.'
    )
    capacidad_maxima = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Tope de personas por reserva de este servicio. Vacío = usa MAX_PERSONAS (5).',
    )
    hora_apertura = models.TimeField(
        null=True, blank=True,
        help_text='Inicio de la ventana horaria de salida. Vacío = sin restricción.',
    )
    hora_cierre = models.TimeField(
        null=True, blank=True,
        help_text='Fin de la ventana horaria de salida. Vacío = sin restricción.',
    )
    descripcion = models.TextField(blank=True, default='')
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'slug'], name='servicio_unico_por_empresa_slug'),
        ]
        ordering = ['empresa', 'nombre']
        verbose_name = 'servicio'
        verbose_name_plural = 'servicios'

    def __str__(self):
        return f"{self.nombre} ({self.empresa})"

    def precio_en(self, moneda):
        """Precio de lista en la moneda pedida, o None si no esta configurado."""
        return self.precio_base if (moneda or 'MXN').upper() == 'MXN' else self.precio_base_usd

    def persona_extra_en(self, moneda):
        """Cargo por persona adicional en esa moneda. None = sin configurar."""
        return self.precio_persona_extra if (moneda or 'MXN').upper() == 'MXN' else self.precio_persona_extra_usd

    def clean(self):
        super().clean()
        if bool(self.hora_apertura) != bool(self.hora_cierre):
            raise ValidationError('Configura las dos horas de la ventana o ninguna.')
        if self.hora_apertura and self.hora_cierre and self.hora_apertura > self.hora_cierre:
            raise ValidationError({'hora_cierre': 'Debe ser ≥ hora_apertura.'})

    def ventana_horaria(self):
        """(apertura, cierre) o None si el servicio no restringe la hora."""
        if self.hora_apertura and self.hora_cierre:
            return (self.hora_apertura, self.hora_cierre)
        return None



class Recurso(models.Model):
    """Activo físico asignable a reservas (panga, guía, habitación, etc.)."""
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='recursos')
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, blank=True, related_name='recursos'
    )
    nombre = models.CharField(max_length=100)
    capacidad_maxima = models.PositiveSmallIntegerField()
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'nombre'], name='recurso_unico_por_empresa_nombre'),
        ]
        ordering = ['empresa', 'nombre']
        verbose_name = 'recurso'
        verbose_name_plural = 'recursos'

    def __str__(self):
        return f"{self.nombre} ({self.capacidad_maxima} pax) - {self.empresa}"

    def clean(self):
        super().clean()
        if self.servicio_id and self.servicio.empresa_id != self.empresa_id:
            raise ValidationError({'servicio': 'El servicio debe pertenecer a la misma empresa que el recurso.'})


class Personalizacion(models.Model):
    """Catálogo de complementos y extras reutilizables."""
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='personalizaciones')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50, default='otro')
    cobrar_por_persona = models.BooleanField(default=False)
    cantidad_editable = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'nombre'], name='personalizacion_unica_por_empresa_nombre'),
        ]
        ordering = ['empresa', 'nombre']
        verbose_name = 'personalización'
        verbose_name_plural = 'personalizaciones'

    def __str__(self):
        return f"{self.nombre} ({self.empresa})"


class ServicioPersonalizacion(models.Model):
    """Asociación de un complemento a un servicio específico con su precio."""
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='servicio_personalizaciones')
    personalizacion = models.ForeignKey(Personalizacion, on_delete=models.PROTECT, related_name='en_servicios')
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    precio_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    obligatorio = models.BooleanField(default=False)
    preseleccionado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['servicio', 'personalizacion'],
                name='personalizacion_unica_por_servicio'
            ),
        ]
        ordering = ['servicio', 'personalizacion__nombre']
        verbose_name = 'personalización de servicio'
        verbose_name_plural = 'personalizaciones de servicios'

    def __str__(self):
        return f"{self.servicio.nombre} - {self.personalizacion.nombre} (${self.precio})"

    def clean(self):
        super().clean()
        if self.servicio_id and self.personalizacion_id:
            if self.servicio.empresa_id != self.personalizacion.empresa_id:
                raise ValidationError({
                    'personalizacion': 'La personalización debe pertenecer a la misma empresa que el servicio.'
                })

    def precio_en(self, moneda):
        """Precio de la personalización en la moneda solicitada."""
        return self.precio if (moneda or 'MXN').upper() == 'MXN' else self.precio_usd


class Paquete(models.Model):
    """Producto de primera clase vendible y editable in-place (Perception-First Design).

    Agrupa múltiples servicios bajo una experiencia y un precio ancla.
    Radicado en una Sede geográfica con una empresa_lider titular del cobro.
    """
    sede = models.ForeignKey('tenancy.Sede', on_delete=models.PROTECT, related_name='paquetes')
    empresa_lider = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='paquetes_liderados')
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150)
    descripcion = models.TextField(blank=True, default='')
    precio_ancla = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Precio ancla del paquete en pesos (MXN).'
    )
    precio_ancla_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Precio ancla del paquete en dólares (USD). Opcional.'
    )
    regla_precio = models.CharField(max_length=50, default='precio_ancla')
    porcentaje_anticipo = models.PositiveSmallIntegerField(default=30)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['sede', 'slug'], name='paquete_unico_por_sede_slug'),
        ]
        ordering = ['sede', 'nombre']
        verbose_name = 'paquete'
        verbose_name_plural = 'paquetes'

    def __str__(self):
        return f"{self.nombre} ({self.sede})"

    def clean(self):
        super().clean()
        if self.sede_id and self.empresa_lider_id:
            if self.empresa_lider.sede_id != self.sede_id:
                raise ValidationError({
                    'empresa_lider': 'La empresa líder debe pertenecer a la misma sede que el paquete.'
                })
        if self.pk:
            for ps in self.servicios_asociados.select_related('servicio', 'servicio__empresa').all():
                if ps.servicio.tipo_servicio == 'transporte':
                    tarifas = ps.servicio.empresa.tarifas_transporte.filter(activo=True)
                    if tarifas.exists():
                        tarifa_min_mxn = min(t.precio for t in tarifas)
                        if self.precio_ancla is not None and self.precio_ancla < tarifa_min_mxn:
                            raise ValidationError({
                                'precio_ancla': f'El precio del paquete ({self.precio_ancla}) no puede ser menor que la tarifa de transporte ({tarifa_min_mxn}).'
                            })
                        tarifas_usd = [t.precio_usd for t in tarifas if t.precio_usd is not None]
                        if tarifas_usd and self.precio_ancla_usd is not None:
                            tarifa_min_usd = min(tarifas_usd)
                            if self.precio_ancla_usd < tarifa_min_usd:
                                raise ValidationError({
                                    'precio_ancla_usd': f'El precio en USD del paquete ({self.precio_ancla_usd}) no puede ser menor que la tarifa de transporte en USD ({tarifa_min_usd}).'
                                })

    def precio_en(self, moneda):
        """Precio ancla en la moneda pedida, o None si no está configurado."""
        return self.precio_ancla if (moneda or 'MXN').upper() == 'MXN' else self.precio_ancla_usd


class PaqueteServicio(models.Model):
    """Asociación entre un Paquete y un Servicio incluido en él."""
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE, related_name='servicios_asociados')
    servicio = models.ForeignKey(Servicio, on_delete=models.PROTECT, related_name='paquetes_incluidos')
    orden = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['paquete', 'servicio'], name='paqueteservicio_unico'),
        ]
        ordering = ['paquete', 'orden', 'servicio__nombre']
        verbose_name = 'servicio de paquete'
        verbose_name_plural = 'servicios de paquetes'

    def __str__(self):
        return f"{self.paquete.nombre} -> {self.servicio.nombre}"

    def clean(self):
        super().clean()
        if self.paquete_id and self.servicio_id:
            if self.servicio.empresa.sede_id != self.paquete.sede_id:
                raise ValidationError({
                    'servicio': 'El servicio debe pertenecer a una empresa de la misma sede que el paquete.'
                })
            # (ADR-005 Revisión 2: se elimina la regla de "misma empresa_lider").
            if self.servicio.tipo_servicio == 'transporte':
                tarifas = self.servicio.empresa.tarifas_transporte.filter(activo=True)
                if tarifas.exists():
                    tarifa_min_mxn = min(t.precio for t in tarifas)
                    if self.paquete.precio_ancla is not None and self.paquete.precio_ancla < tarifa_min_mxn:
                        raise ValidationError({
                            'servicio': f'El precio del paquete ({self.paquete.precio_ancla}) no puede ser menor que la tarifa de transporte ({tarifa_min_mxn}).'
                        })
                    tarifas_usd = [t.precio_usd for t in tarifas if t.precio_usd is not None]
                    if tarifas_usd and self.paquete.precio_ancla_usd is not None:
                        tarifa_min_usd = min(tarifas_usd)
                        if self.paquete.precio_ancla_usd < tarifa_min_usd:
                            raise ValidationError({
                                'servicio': f'El precio en USD del paquete ({self.paquete.precio_ancla_usd}) no puede ser menor que la tarifa de transporte en USD ({tarifa_min_usd}).'
                            })


def capacidades_por_fecha(desde, hasta, empresa):
    """Capacidad de cada panga que puede salir, por dia, de mayor a menor, para
    esa Empresa. `empresa` es obligatorio — sin filtro por Empresa, en
    sqlite/tests la flota de una Empresa cuenta como capacidad de otra.

    `{fecha: [5, 3, 3, ...]}` con una entrada por cada dia del rango, incluidos
    los dias en que no falta ninguna.

    Son **dos consultas para todo el rango**, no una por dia: de aqui cuelga la
    busqueda de los proximos 90 dias del checkout, y esa busqueda ya murio una vez
    por hacer una peticion por dia (ver bookings.proxima_fecha_disponible).

    La flota no sabe nada de reservas a proposito: esto responde que hay a flote,
    no que esta vendido.
    """
    activas = list(
        Embarcacion.objects.filter(activa=True, empresa=empresa)
        .values_list('id', 'capacidad_maxima')
    )

    fuera = defaultdict(set)
    for fecha, embarcacion_id in EmbarcacionNoDisponible.objects.filter(
        fecha__range=(desde, hasta), empresa=empresa
    ).values_list('fecha', 'embarcacion_id'):
        fuera[fecha].add(embarcacion_id)

    dias = (hasta - desde).days + 1
    return {
        fecha: sorted(
            (capacidad for pk, capacidad in activas if pk not in fuera[fecha]), reverse=True
        )
        for fecha in (desde + timedelta(days=i) for i in range(dias))
    }


def capacidades_disponibles(fecha, empresa):
    """Las capacidades a flote ese dia para esa Empresa, de mayor a menor.

    Es el caso de un dia de `capacidades_por_fecha`, y se implementa asi para que
    la ruta de una fecha y la de 90 dias no puedan discrepar nunca.
    """
    return capacidades_por_fecha(fecha, fecha, empresa)[fecha]
