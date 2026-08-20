from collections import defaultdict
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models
from django.utils import timezone

from apps.fleet.models import (
    Capitan,
    Embarcacion,
    capacidades_disponibles,
    capacidades_por_fecha,
)

from .validators import validar_nombre_persona, validar_telefono

VENTANA_SALIDA_INICIO = time(5, 0)
VENTANA_SALIDA_FIN = time(7, 0)

# Sin minimo de personas y sin restriccion de edad; el tope es la embarcacion
# mas grande de la flota (ver docs/contexto-negocio.md, seccion Embarcaciones).
#
# La flota real son 8 pangas de maximo 3 personas y 2 de maximo 5. Estuvo en 6,
# que no lo cumple ninguna: la web aceptaba y cobraba viajes de 6 personas que
# despues no habia panga donde meter. Subir esta constante sin comprar una panga
# mas grande vuelve a abrir ese hueco — el tope de aqui y la flota de alla son el
# mismo numero visto desde dos lados.
MIN_PERSONAS = 1
MAX_PERSONAS = 5

# Cambio de fecha permitido con minimo 48 horas de anticipacion sobre la salida
# original (ver docs/contexto-negocio.md, seccion Cancelaciones y cambios).
HORAS_MINIMAS_CAMBIO_FECHA = 48

# Cuanto se espera antes de dar por abandonado un checkout que quedo en
# pendiente_pago. Con margen: alguien puede tardarse buscando su tarjeta, y no
# queremos hablarle a un cliente que sigue pagando en ese momento.
HORAS_PARA_CONSIDERAR_ABANDONADO = 2

# Capacidad operativa por defecto (8 a 10 viajes/dia, ver docs/contexto-negocio.md).
# Los jefes/vendedora cierran o reducen un dia especifico creando un CupoDiario.
CUPO_MAXIMO_DEFAULT = 10

# Solo estas cuentan contra el cupo: una reserva pendiente_pago (checkout iniciado
# pero no pagado) no debe bloquear el cupo de otro cliente.
ESTADOS_QUE_OCUPAN_CUPO = ['pagada', 'asignada', 'completada']


def validar_ventana_salida(value):
    if not (VENTANA_SALIDA_INICIO <= value <= VENTANA_SALIDA_FIN):
        raise ValidationError('La hora de salida debe estar entre las 5:00 y las 7:00 am.')


def salida_aware(fecha, hora):
    """Momento de salida como datetime con zona (TIME_ZONE = America/Mazatlan)."""
    return timezone.make_aware(datetime.combine(fecha, hora))


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


# Por que no se puede vender un lugar. Viajan al frontend en la respuesta de
# /api/cupo/, porque "ese dia esta lleno" y "no queda panga para tu grupo" son dos
# cosas distintas para el cliente que las lee.
MOTIVO_LLENO = 'lleno'
MOTIVO_SIN_PANGA = 'sin_panga'


def caben(grupos, capacidades):
    """Hay forma de darle a cada grupo una panga donde quepa?

    Las dos listas llegan ordenadas **de mayor a menor**.

    Se emparejan de mayor a menor: el grupo mas grande con la panga mas grande. Si
    a algun grupo le toca una panga mas chica que el, no hay reparto posible — y no
    lo hay con ningun otro orden, porque cualquier reparto valido tendria que darle
    a ese grupo una panga al menos igual de grande, y todas las de arriba ya estan
    ocupadas por grupos aun mayores.

    Con 10 pangas el costo es irrelevante, pero importa que el criterio sea exacto
    y no una heuristica: de esto depende si se cobra o no.
    """
    if len(grupos) > len(capacidades):
        return False
    return all(g <= c for g, c in zip(grupos, capacidades))


def motivo_sin_lugar(personas, grupos, capacidades, tope):
    """Por que no entra un grupo de `personas` mas, o None si si entra.

    `grupos` son los tamanos ya vendidos de ese dia, sin el nuevo. `capacidades`
    viene ordenada de mayor a menor. `tope` es el maximo de viajes del dia.

    Es el nucleo puro del cupo: no toca la base. Lo llaman la validacion al
    guardar, el endpoint /api/cupo/, la busqueda de la proxima fecha y el comando
    revisar_cupo — los cuatro tienen que decidir igual, y por eso deciden aqui.

    El orden de las dos comprobaciones importa: si el dia esta lleno a secas, ese
    es el mensaje util, no el de las pangas.
    """
    if len(grupos) + 1 > tope:
        return MOTIVO_LLENO
    if not caben(sorted([*grupos, personas], reverse=True), capacidades):
        return MOTIVO_SIN_PANGA
    return None


# Hasta donde se busca un dia con espacio cuando el pedido esta lleno. Tres meses
# cubre de sobra la ventana en que la gente planea un viaje de pesca.
DIAS_BUSQUEDA_DISPONIBILIDAD = 90


def proxima_fecha_disponible(desde, personas, dias=DIAS_BUSQUEDA_DISPONIBILIDAD):
    """Primera fecha donde cabe un grupo de `personas`, o None si no hay en `dias`.

    Se resuelve con **cuatro consultas**, no una por dia: reservas del rango,
    CupoDiario del rango, y las dos de la flota. Antes esta busqueda vivia en el
    navegador (`checkout-view.tsx`) y hacia una peticion por cada dia que probaba:
    hasta 90 seguidas, que con el limite de 60/min por IP terminaban en un 429 que
    el frontend se tragaba en silencio. La ayuda de "te muevo al siguiente dia con
    espacio" dejaba de funcionar justo en temporada alta, que es cuando hace falta.
    El costo no puede volver a crecer con la ventana.
    """
    hasta = desde + timedelta(days=dias - 1)

    grupos_por_fecha = defaultdict(list)
    for fecha, personas_de_esa in Reserva.objects.filter(
        fecha__range=(desde, hasta), estado__in=ESTADOS_QUE_OCUPAN_CUPO
    ).values_list('fecha', 'numero_personas'):
        grupos_por_fecha[fecha].append(personas_de_esa)

    topes = dict(
        CupoDiario.objects.filter(fecha__range=(desde, hasta)).values_list('fecha', 'cupo_maximo')
    )
    capacidades = capacidades_por_fecha(desde, hasta)

    for i in range(dias):
        fecha = desde + timedelta(days=i)
        motivo = motivo_sin_lugar(
            personas,
            grupos_por_fecha[fecha],
            capacidades[fecha],
            topes.get(fecha, CUPO_MAXIMO_DEFAULT),
        )
        if motivo is None:
            return fecha
    return None


def bloquear_cupo_del_dia(fecha):
    """Serializa la validacion de cupo de una fecha entre transacciones.

    Sin esto hay sobreventa: contar y guardar no son una operacion atomica. Dos
    clientes distintos pagando el ultimo lugar del mismo dia al mismo tiempo
    hacen que las dos transacciones cuenten `cupo - 1` ocupadas, las dos pasen la
    validacion y las dos queden confirmadas. Alguien llega al muelle y no hay
    panga. `select_for_update` sobre la reserva propia no lo evita: bloquea la
    fila que se esta pagando, no el conjunto contra el que se cuenta, y una fila
    que todavia no existe no se puede bloquear.

    Un advisory lock de Postgres si sirve para eso: no necesita una fila, se toma
    sobre un numero arbitrario — aqui el ordinal de la fecha, unico y estable por
    dia — y la variante `_xact_` se libera sola al terminar la transaccion, sin
    riesgo de dejarlo colgado si algo revienta a medias.

    Dos condiciones para que proteja de verdad:

    - **Tiene que haber transaccion.** Fuera de una, Postgres la abre y la cierra
      con la propia consulta, asi que el lock se suelta antes de guardar y no
      sirve de nada. Las dos rutas que crean reservas cumplen: el webhook corre
      en `transaction.atomic` (ver apps/payments/services.py) y el admin de
      Django envuelve cada guardado en una transaccion.
    - **Se toma antes de contar**, no despues, o la carrera ya ocurrio.

    En sqlite es un no-op: no tiene advisory locks y no le hacen falta — serializa
    toda escritura con un solo escritor. Ese es justamente el motivo por el que
    esta condicion de carrera era invisible en los tests hasta que el CI empezo a
    correrlos tambien contra Postgres (ver config/settings/ci.py).
    """
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [fecha.toordinal()])


def evaluar_cupo(fecha, personas, excluir_pk=None):
    """Por que no entra un grupo de `personas` ese dia, o None si si entra.

    Solo consulta: **no toma el lock**. La usa `/api/cupo/`, que es una lectura
    informativa, y `validar_cupo_diario`, que si lo toma antes de llamar aqui.
    """
    ocupadas = Reserva.objects.filter(fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO)
    if excluir_pk is not None:
        ocupadas = ocupadas.exclude(pk=excluir_pk)

    return motivo_sin_lugar(
        personas,
        list(ocupadas.values_list('numero_personas', flat=True)),
        capacidades_disponibles(fecha),
        cupo_maximo_del_dia(fecha),
    )


def validar_cupo_diario(fecha, personas, excluir_pk=None):
    """Motor unico de validacion de cupo. Debe usarse tanto para el flujo de pago
    de la web como para la creacion/edicion manual de Reserva (ver backend/CLAUDE.md).

    Dos motivos con dos mensajes distintos, porque son dos problemas distintos para
    quien los lee: el dia se lleno, o el dia tiene espacio pero ya no hay panga
    donde quepa ese grupo.
    """
    # Antes de contar, no despues: ver bloquear_cupo_del_dia. Ahora el lock ademas
    # cubre el ultimo lugar *de ese tamano*, no solo el ultimo lugar.
    bloquear_cupo_del_dia(fecha)

    motivo = evaluar_cupo(fecha, personas, excluir_pk=excluir_pk)
    if motivo == MOTIVO_LLENO:
        raise ValidationError(
            f'No hay cupo disponible para el {fecha}: se alcanzo el maximo de viajes del dia.'
        )
    if motivo == MOTIVO_SIN_PANGA:
        raise ValidationError(
            f'No queda panga para un grupo de {personas} personas el {fecha}. '
            f'Las de mayor capacidad ya estan comprometidas.'
        )


class Vendedora(models.Model):
    """Quien vendio el viaje. Existe para saber que venta es de quien.

    Es un perfil sobre una cuenta de Django (la misma con la que entra al
    backoffice), no un catalogo de personas aparte: asi el registro de ventas
    queda amarrado al usuario que ya usa el sistema. Escala a varias vendedoras
    sin tocar nada — cada una tiene su fila y su codigo.

    **La comision se calcula y se paga fuera del sistema.** Aqui no hay
    porcentajes ni saldos a proposito: lo unico que se lleva es el registro de
    a quien le corresponde cada venta.

    El `codigo` es lo que viaja en el link que ella le pasa a sus clientes
    (`.../es/reservar?ref=<codigo>`): quien reserva desde ese link queda
    atribuido solo, sin que ella tenga que marcarlo despues.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        # PROTECT: borrar la cuenta dejaria ventas sin dueño. Para dar de baja a
        # alguien se desmarca `activo`, no se borra.
        on_delete=models.PROTECT,
        related_name='vendedora',
    )
    codigo = models.SlugField(
        max_length=30, unique=True,
        help_text='Lo que va en el link que le manda a sus clientes: ?ref=<codigo>. '
                  'Solo letras, numeros y guiones.',
    )
    activo = models.BooleanField(
        default=True,
        help_text='Desmarcalo para dar de baja a la vendedora sin perder el historial '
                  'de sus ventas. Un link con el codigo de alguien inactivo ya no atribuye.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['usuario__username']
        verbose_name = 'vendedora'
        verbose_name_plural = 'vendedoras'

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.get_username()

    @classmethod
    def por_codigo(cls, codigo):
        """La vendedora activa de ese codigo, o None. Un codigo que ya no existe
        (o que el cliente escribio mal) nunca debe tumbar un checkout."""
        if not codigo:
            return None
        return cls.objects.filter(codigo=codigo, activo=True).first()


class Reserva(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE_PAGO = 'pendiente_pago', 'Pendiente de pago'
        PAGADA = 'pagada', 'Pagada, sin asignar'
        ASIGNADA = 'asignada', 'Asignada'
        # Mal clima es la unica causa de cancelacion iniciada por el negocio, pero
        # el webhook de pago tambien cancela y reembolsa si el dia se lleno mientras
        # el cliente pagaba — el motivo real vive en motivo_cancelacion.
        CANCELADA = 'cancelada', 'Cancelada (reembolsada)'
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
    numero_personas = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_PERSONAS), MaxValueValidator(MAX_PERSONAS)]
    )

    # Datos del cliente (no se pide peso ni si sabe nadar, ver docs/contexto-negocio.md)
    nombre_cliente = models.CharField(max_length=150, validators=[validar_nombre_persona])
    telefono_cliente = models.CharField(max_length=20, validators=[validar_telefono])
    correo_cliente = models.EmailField()

    # Deslinde de responsabilidad: casilla aceptada + nombre escrito por el cliente,
    # con fecha/hora e IP del momento en que lo acepto (ver docs/contexto-negocio.md,
    # seccion Legal). Se llenan en el servidor, nunca se confian del cliente.
    deslinde_aceptado = models.BooleanField(default=False)
    deslinde_nombre = models.CharField(max_length=150, blank=True)
    deslinde_aceptado_en = models.DateTimeField(null=True, blank=True)
    deslinde_ip = models.GenericIPAddressField(null=True, blank=True)

    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE_PAGO)
    canal_origen = models.CharField(max_length=10, choices=CanalOrigen.choices)

    # A quien le cuenta esta venta. `canal_origen` dice por donde entro la reserva
    # (web o WhatsApp); esto dice quien la vendio, que no es lo mismo: la vendedora
    # le pasa su link a un cliente y la reserva entra como 'web' pero es venta suya.
    # Vacio = venta que llego sola. La atribucion es del que VENDE, no del que
    # administra: asignar la panga o el capitan despues no cambia este campo.
    vendedora = models.ForeignKey(
        Vendedora, on_delete=models.PROTECT, null=True, blank=True, related_name='ventas',
        help_text='Quien vendio este viaje. Se llena solo si el cliente llego por su '
                  'link (?ref=), o a mano desde aqui.',
    )
    vendedora_asignada_en = models.DateTimeField(null=True, blank=True)

    # Identificador que genera el navegador al abrir el checkout. Sirve para que
    # una sesion de checkout ocupe siempre la misma fila: si el cliente corrige
    # la fecha, reintenta tras un error o recarga, se actualiza esta reserva en
    # vez de dejar filas sueltas. Vacio en las reservas que captura la vendedora.
    # Sin unique a proposito: al pagarse, esa fila deja de ser `pendiente_pago` y
    # el mismo navegador puede empezar otro checkout con el mismo identificador.
    checkout_id = models.UUIDField(null=True, blank=True, db_index=True)

    # Cobro (Stripe, cuenta estandar — ver docs/contexto-negocio.md). precio_total
    # es el tour + amenidades elegidas, calculado en el servidor al crear el pago,
    # nunca confiado del cliente. monto_pagado es lo efectivamente cobrado por
    # Stripe (100% o el 30% de anticipo).
    moneda = models.CharField(max_length=3, choices=Moneda.choices, default=Moneda.MXN)
    forma_pago = models.CharField(max_length=10, choices=FormaPago.choices, blank=True)
    precio_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True)

    # Cuando entro el cobro con tarjeta. Es la fecha con la que ese dinero cuenta
    # en el panel de finanzas: `creado_en` es cuando el cliente abrio el checkout
    # y `actualizado_en` se mueve con cualquier edicion posterior, asi que ninguno
    # de los dos sirve para cuadrar un dia.
    pagada_en = models.DateTimeField(null=True, blank=True)

    # Efectivo recibido el dia del viaje: el 70% restante cuando el cliente pago
    # anticipo, y lo que se haya cotizado aparte (bebidas, transporte). Puede
    # superar el saldo del tour justo por eso, asi que no se valida contra el.
    # Sin esto el dinero en efectivo no deja rastro en ningun lado.
    monto_efectivo = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='cobrado en efectivo',
        help_text='Lo que se recibio en efectivo el dia del viaje, incluido lo que '
                  'el agente haya cotizado aparte.',
    )
    efectivo_cobrado_en = models.DateTimeField(null=True, blank=True)
    efectivo_cobrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cobros_en_efectivo',
    )

    # Lo levanta el webhook con charge.dispute.created. La vendedora necesita
    # verlo: una reserva en disputa no se toca hasta que Stripe resuelva.
    en_disputa = models.BooleanField(default=False, verbose_name='en disputa')

    # Extras que pidio el cliente en el checkout. Se guardan aqui y no solo en el
    # cobro porque la operacion los necesita: sin esto nadie sabe cuantos lunches
    # preparar ni a quien hay que cotizarle un traslado.
    #
    # El lunch se cobra en linea (precio por persona, en `Tarifa`). Bebidas y
    # transporte NO: su precio depende del tipo de bebida y de la distancia, asi
    # que quedan como solicitud para que el agente las cotice aparte.
    lleva_lunch = models.BooleanField(default=False, verbose_name='lunch')
    pide_bebidas = models.BooleanField(default=False, verbose_name='bebidas (a cotizar)')
    pide_transporte = models.BooleanField(default=False, verbose_name='transporte (a cotizar)')

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

    # Ojo con la diferencia, el panel de finanzas depende de ella:
    # `reembolsada` = se decidio devolver el dinero (lo marca la vendedora al
    # cancelar por mal clima, antes de que nadie toque Stripe).
    # `monto_reembolsado` / `reembolsada_en` = el dinero ya salio de la cuenta.
    # Lo llena el webhook de Stripe cuando el reembolso se ejecuta de verdad.
    # Solo lo segundo cuenta como salida: el balance del dia refleja dinero que
    # se movio, no intenciones.
    reembolsada = models.BooleanField(default=False)
    monto_reembolsado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Lo que efectivamente se devolvio por Stripe.',
    )
    reembolsada_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha', '-hora']

    def __str__(self):
        return f'{self.nombre_cliente} — {self.fecha} {self.hora}'

    @classmethod
    def from_db(cls, db, field_names, values):
        # Guarda la salida original para poder aplicar la regla de 48 horas en
        # clean() cuando la vendedora reprograma una reserva ya existente.
        instance = super().from_db(db, field_names, values)
        instance._salida_original = (instance.fecha, instance.hora)
        instance._vendedora_original = instance.vendedora_id
        return instance

    def save(self, *args, **kwargs):
        self._derivar_estado_de_asignacion()

        # Si la llamada trae `update_fields` y toca la embarcacion, `estado` tiene
        # que ir en esa lista o el UPDATE no lo escribe: la fila quedaria diciendo
        # `pagada` con una panga puesta. El listado editable del admin guarda asi.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'embarcacion' in update_fields:
            kwargs['update_fields'] = [*update_fields, 'estado']

        # Sella cuando se atribuyo la venta, venga de donde venga (link ?ref= al
        # crear la reserva, panel de la vendedora, shell). Va en save() y no en la
        # vista porque hay varias entradas y todas deben dejar la misma constancia.
        if self.vendedora_id != getattr(self, '_vendedora_original', None):
            self.vendedora_asignada_en = timezone.now() if self.vendedora_id else None
            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'vendedora' in update_fields:
                kwargs['update_fields'] = [*update_fields, 'vendedora_asignada_en']
        super().save(*args, **kwargs)
        self._vendedora_original = self.vendedora_id

    def _derivar_estado_de_asignacion(self):
        """Poner la panga da el viaje por asignado; quitarla lo regresa a pagada.

        Va en save() y no en el admin para que valga igual desde el shell o desde
        cualquier pantalla futura, y va en save() y no en clean() porque clean()
        solo corre cuando alguien valida: un save() directo dejaria el estado
        diciendo una cosa y la panga otra.

        Solo entre esos dos estados. `completada` y `cancelada` son finales y los
        decide una persona, no el efecto secundario de editar un campo; y una
        `pendiente_pago` no es un viaje que repartir.

        El capitan no cuenta: se acordo que poner la panga baste, sabiendo que un
        viaje puede llegar a la salida sin capitan. Eso se avisa en rojo en la
        agenda, no se frena aqui.
        """
        if self.estado == self.Estado.PAGADA and self.embarcacion_id:
            self.estado = self.Estado.ASIGNADA
        elif self.estado == self.Estado.ASIGNADA and not self.embarcacion_id:
            self.estado = self.Estado.PAGADA

    def clean(self):
        if self.estado in ESTADOS_QUE_OCUPAN_CUPO:
            validar_cupo_diario(self.fecha, self.numero_personas, excluir_pk=self.pk)
        if self.estado != self.Estado.CANCELADA and (self.cancelada_por_id or self.cancelada_en):
            raise ValidationError('cancelada_por/cancelada_en solo aplican cuando estado es cancelada.')
        if self.canal_origen == self.CanalOrigen.WEB and not self.deslinde_aceptado:
            raise ValidationError(
                {'deslinde_aceptado': 'La reserva web requiere aceptar el deslinde de responsabilidad.'}
            )
        self._validar_capacidad_embarcacion()
        self._validar_cambio_de_fecha()

    def _validar_capacidad_embarcacion(self):
        if self.embarcacion_id and self.numero_personas > self.embarcacion.capacidad_maxima:
            raise ValidationError({
                'embarcacion': f'{self.embarcacion} admite hasta {self.embarcacion.capacidad_maxima} '
                               f'personas y la reserva es para {self.numero_personas}.',
            })

    @property
    def salida(self):
        return salida_aware(self.fecha, self.hora)

    @property
    def tiene_cotizaciones_pendientes(self):
        """Pidio algo cuyo precio no se cobro en linea y el agente debe cotizar."""
        return self.pide_bebidas or self.pide_transporte

    @property
    def saldo_pendiente(self):
        """Lo que falta por cobrar, ya descontado el efectivo recibido.

        Con forma de pago 'anticipo' arranca en el 70% restante y llega a cero
        cuando la vendedora registra la liquidacion. Con 'completo' deberia ser
        cero desde el principio: si no lo es, hay un descuadre entre lo que el
        servidor calculo y lo que Stripe cobro (ver apps/payments/services.py,
        `_verificar_monto`)."""
        if self.precio_total is None:
            return None
        return self.precio_total - (self.monto_pagado or 0) - (self.monto_efectivo or 0)

    @property
    def liquidado(self):
        """Ya no debe nada del tour."""
        saldo = self.saldo_pendiente
        return saldo is not None and saldo <= 0

    def _validar_cambio_de_fecha(self):
        """Cambio de fecha/hora permitido con minimo 48 horas de anticipacion sobre
        la salida original. No aplica a reservas canceladas (mal clima no avisa con
        48 horas) ni a las que aun no ocupan cupo."""
        original = getattr(self, '_salida_original', None)
        if original is None or self.estado not in ESTADOS_QUE_OCUPAN_CUPO:
            return
        if (self.fecha, self.hora) == original:
            return

        limite = salida_aware(*original) - timedelta(hours=HORAS_MINIMAS_CAMBIO_FECHA)
        if timezone.now() > limite:
            raise ValidationError({
                'fecha': f'El cambio de fecha requiere al menos {HORAS_MINIMAS_CAMBIO_FECHA} horas '
                         f'de anticipacion sobre la salida original ({original[0]} {original[1]}).',
            })


class CheckoutAbandonado(Reserva):
    """Proxy de `Reserva` para la pantalla de recuperacion de la vendedora.

    Son las reservas que quedaron en `pendiente_pago`: el cliente lleno sus datos,
    le dio a pagar y no termino. No ocupan cupo y no valen como reserva, pero si
    son un contacto que ya dijo que dia queria salir — el trabajo de la vendedora
    es hablarles y cerrarlo.

    Es proxy y no un modelo nuevo a proposito: es la misma fila de `Reserva`, vista
    con otro filtro. Si el cliente termina de pagar despues, la fila cambia de
    estado sola y desaparece de aqui.
    """

    class Meta:
        proxy = True
        # Los mas recientes primero: un checkout de hace un rato se recupera mucho
        # mejor que uno de la semana pasada.
        ordering = ['-creado_en']
        verbose_name = 'checkout abandonado'
        verbose_name_plural = 'checkouts abandonados'

    @classmethod
    def abandonados(cls):
        limite = timezone.now() - timedelta(hours=HORAS_PARA_CONSIDERAR_ABANDONADO)
        return cls.objects.filter(estado=Reserva.Estado.PENDIENTE_PAGO, creado_en__lt=limite)


class Agenda(Reserva):
    """Proxy de `Reserva` para repartir los viajes ya vendidos.

    Es la pantalla donde se decide que panga y que capitan le toca a cada viaje.
    Proxy y no modelo nuevo a proposito, igual que `CheckoutAbandonado`: es la
    misma fila vista con otro filtro y otras columnas. Si un viaje se cancela,
    desaparece de aqui solo.

    Lista solo `pagada` y `asignada`, que son los dos estados que todavia se
    pueden repartir. Una cancelada no se reparte, una completada ya salio, y una
    `pendiente_pago` no es una reserva todavia — esa vive en la pantalla de
    checkouts abandonados.
    """

    ESTADOS_EN_AGENDA = [Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA]

    class Meta:
        proxy = True
        # Ascendente, al reves que el listado de Reservas: eso es un historial y
        # ensena lo mas reciente arriba; esto es una agenda y lo que sale primero
        # va primero. De paso, los viajes atrasados quedan hasta arriba solos por
        # ser los mas viejos: lo que esta mal aparece sin que nadie lo ordene.
        ordering = ['fecha', 'hora']
        verbose_name = 'agenda'
        verbose_name_plural = 'agenda'

    @classmethod
    def por_repartir(cls):
        return cls.objects.filter(estado__in=cls.ESTADOS_EN_AGENDA)
