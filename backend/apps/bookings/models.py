from collections import defaultdict
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models
from django.utils import timezone

from apps.fleet.models import (
    Capitan,
    CodigoPromocional,
    Embarcacion,
    ExtrasItem,
    capacidades_disponibles,
    capacidades_por_fecha,
)
from apps.tenancy.models import Empresa

from .cupo import (
    DemandaCupo,
    ModoOcupacion,
    MOTIVO_LLENO,
    MOTIVO_SIN_LUGAR,
    MOTIVO_SIN_PANGA,
    bloquear_cupo,
    bloquear_cupo_del_dia,
    caben,
    caben_compartido,
    evaluar_disponibilidad_hospedaje,
    motivo_sin_lugar,
    obtener_contexto_cupo,
    obtener_contexto_rango,
    obtener_estrategia,
    ocupacion_por_rango,
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

# Version del deslinde que el sitio muestra hoy. Al cambiar el texto de
# `checkout.waiver.page` en los diccionarios del frontend hay que subir esta
# fecha, o las constancias nuevas quedaran selladas contra un texto viejo.
DESLINDE_VERSION = '2026-08-21'

# Solo estas cuentan contra el cupo: una reserva pendiente_pago (checkout iniciado
# pero no pagado) no debe bloquear el cupo de otro cliente.
ESTADOS_QUE_OCUPAN_CUPO = ['pagada', 'asignada', 'completada']


def validar_ventana_salida(value):
    """Valida la ventana horaria legacy de pesca (5:00 a 7:00 am). Conservado como helper."""
    if not (VENTANA_SALIDA_INICIO <= value <= VENTANA_SALIDA_FIN):
        raise ValidationError('La hora de salida debe estar entre las 5:00 y las 7:00 am.')


def salida_aware(fecha, hora):
    """Momento de salida como datetime con zona (TIME_ZONE = America/Mazatlan)."""
    return timezone.make_aware(datetime.combine(fecha, hora))


class CupoDiario(models.Model):
    """Tope de viajes que el negocio decide para un dia. Sin registro para un dia
    aplica CUPO_MAXIMO_DEFAULT.

    **No es lo mismo que las pangas fuera de servicio**, y confundirlos es facil.
    Esto es una decision del negocio ("ese sabado solo quiero sacar 4 viajes");
    `fleet.EmbarcacionNoDisponible` es un hecho fisico ("la Lupita esta en
    mantenimiento el jueves"). Son dos condiciones y se cumplen las dos.

    Antes se usaba tambien para reducir el dia cuando iban a faltar embarcaciones.
    Eso ya no: para eso esta el otro modelo, que registra cual falta y por que, y
    ademas le dice al motor de cupo que capacidad se perdio y no solo cuantos
    viajes. Lo que sigue siendo de aqui:

    - **Cerrar el dia entero** con un 0: mal clima pronosticado, festivo, no se
      opera. Con el otro modelo habria que marcar las diez pangas una por una.
    - **Faltan capitanes.** El motor de cupo no sabe nada de capitanes: puede
      vender diez viajes un dia en que solo hay seis disponibles. Hasta que eso se
      modele, este es el unico freno.
    - Cualquier tope que el negocio quiera poner sin una razon fisica detras.
    """

    fecha = models.DateField()
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='cupos_diarios')
    cupo_maximo = models.PositiveSmallIntegerField(
        help_text='Tope de viajes que decide el negocio para este dia. Ponlo en 0 para '
                  'cerrar el dia (mal clima, festivo), o usalo cuando falten capitanes: '
                  'el cupo todavia no sabe contarlos. Si lo que falta es una PANGA no uses '
                  'esto — marcala en "Embarcaciones no disponibles", que registra cual y '
                  'por que.'
    )

    class Meta:
        ordering = ['fecha']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'fecha'], name='cupodiario_unico_por_empresa_fecha'),
        ]

    def __str__(self):
        return f'{self.fecha}: {self.cupo_maximo} viajes'


def cupo_maximo_del_dia(fecha, empresa):
    override = CupoDiario.objects.filter(fecha=fecha, empresa=empresa).first()
    return override.cupo_maximo if override else CUPO_MAXIMO_DEFAULT


# Hasta donde se busca un dia con espacio cuando el pedido esta lleno. Tres meses
# cubre de sobra la ventana en que la gente planea un viaje de pesca.
DIAS_BUSQUEDA_DISPONIBILIDAD = 90


def proxima_fecha_disponible(desde, personas, empresa, dias=DIAS_BUSQUEDA_DISPONIBILIDAD, estrategia_cupo='por_recurso_dia'):
    """Primera fecha donde cabe un grupo de `personas`, o None si no hay en `dias`.

    Se resuelve con cuatro consultas mediante el adaptador de cupo, no una por dia.
    """
    hasta = desde + timedelta(days=dias - 1)
    for fecha, motivo in sorted(disponibilidad_por_fecha(desde, hasta, personas, empresa, estrategia_cupo=estrategia_cupo).items()):
        if motivo is None:
            return fecha
    return None


def disponibilidad_por_fecha(desde, hasta, personas, empresa, estrategia_cupo='por_recurso_dia'):
    """Por que no cabe un grupo de `personas` cada dia del rango, o None si cabe.

    `{fecha: None | MOTIVO_LLENO | MOTIVO_SIN_PANGA}`, una entrada por dia,
    extremos incluidos. Resuelve con cuatro consultas para todo el rango delegando
    en la estrategia configurada (PorRecursoDia por defecto).
    """
    ctx = obtener_contexto_rango(desde, hasta, empresa)
    estrategia = obtener_estrategia(estrategia_cupo)
    res_rango = estrategia.evaluar_rango(
        fechas=ctx.fechas,
        grupos_por_fecha=ctx.grupos_por_fecha,
        capacidades_por_fecha=ctx.capacidades_por_fecha,
        topes_por_fecha=ctx.topes_por_fecha,
        personas=personas,
    )
    return {fecha: item.motivo for fecha, item in res_rango.items()}


def evaluar_cupo(fecha, personas, empresa, excluir_pk=None, estrategia_cupo='por_recurso_dia', servicio_id=None):
    """Por que no entra un grupo de `personas` ese dia, o None si si entra.

    Solo consulta: **no toma el lock**. La usa `/api/cupo/`, que es una lectura
    informativa, y `validar_cupo_diario`, que si lo toma antes de llamar aqui.
    """
    ctx = obtener_contexto_cupo(fecha, empresa, excluir_pk=excluir_pk)
    estrategia = obtener_estrategia(estrategia_cupo)
    demanda = DemandaCupo(fecha=fecha, personas=personas, excluir_pk=excluir_pk)
    resultado = estrategia.evaluar(
        demanda=demanda,
        grupos=ctx.grupos,
        capacidades=ctx.capacidades,
        tope=ctx.tope,
    )
    return resultado.motivo


def validar_cupo_diario(fecha, personas, empresa, excluir_pk=None, estrategia_cupo='por_recurso_dia', servicio_id=None):
    """Motor unico de validacion de cupo. Debe usarse tanto para el flujo de pago
    de la web como para la creacion/edicion manual de Reserva (ver backend/CLAUDE.md).

    Dos motivos con dos mensajes distintos, porque son dos problemas distintos para
    quien los lee: el dia se lleno, o el dia tiene espacio pero ya no hay panga
    donde quepa ese grupo.
    """
    # Antes de contar, no despues: ver bloquear_cupo. Ahora el lock ademas
    # cubre el ultimo lugar *de ese tamano*, no solo el ultimo lugar.
    bloquear_cupo(empresa.pk, fecha, servicio_id=servicio_id)
    ctx = obtener_contexto_cupo(fecha, empresa, excluir_pk=excluir_pk)
    estrategia = obtener_estrategia(estrategia_cupo)
    demanda = DemandaCupo(fecha=fecha, personas=personas, excluir_pk=excluir_pk)
    estrategia.validar(
        demanda=demanda,
        grupos=ctx.grupos,
        capacidades=ctx.capacidades,
        tope=ctx.tope,
    )


def _validar_cupo_hospedaje(reserva):
    disponible = evaluar_disponibilidad_hospedaje(
        check_in=reserva.fecha,
        check_out=reserva.fecha_fin_servicio,
        personas=reserva.numero_personas,
        empresa=reserva.empresa,
        servicio=reserva.servicio,
        excluir_pk=reserva.pk,
    )
    if not disponible:
        raise ValidationError({'fecha': 'No hay disponibilidad de hospedaje en esas fechas.'})


def _validar_cupo_de_paquete(reserva):
    for ps in reserva.paquete.servicios_asociados.select_related('servicio').all():
        estrategia = ps.servicio.estrategia_cupo
        if estrategia == 'por_recurso_dia':
            motivo = evaluar_cupo(
                reserva.fecha, reserva.numero_personas, reserva.empresa,
                excluir_pk=reserva.pk, estrategia_cupo='por_recurso_dia',
                servicio_id=ps.servicio_id,
            )
            if motivo:
                raise ValidationError({
                    'fecha': f'No hay cupo disponible para el servicio {ps.servicio.nombre} ({motivo}).'
                })
        elif estrategia == 'por_noche':
            disponible = evaluar_disponibilidad_hospedaje(
                check_in=reserva.fecha,
                check_out=reserva.fecha_fin_servicio,
                personas=reserva.numero_personas,
                empresa=reserva.empresa,
                servicio=ps.servicio,
                excluir_pk=reserva.pk,
            )
            if not disponible:
                raise ValidationError({
                    'fecha': f'No hay disponibilidad de hospedaje para el servicio {ps.servicio.nombre} en esas fechas.'
                })
        elif estrategia == 'bajo_demanda':
            continue


def codigo_promocional_valido(promo, correo_cliente, monto_viaje=None, moneda=None, excluir_pk=None):
    """Si este codigo se puede aplicar ahora mismo, para este cliente y (si se
    conoce) este monto/moneda.

    Deliberadamente no dice POR QUE no aplica (inactivo, vencido, agotado, ya
    usado por este cliente, no alcanza el minimo): distinguirlo le daria
    pistas a quien prueba codigos al azar sobre cual de esos motivos fue.

    Sin lock: quien necesita el lock antes de contar (la confirmacion del
    pago) lo toma antes de llamar aqui, igual que `evaluar_cupo` vs
    `validar_cupo_diario`.

    Los usos se cuentan contando `Reserva` que ya lo aplicaron
    (`ESTADOS_QUE_OCUPAN_CUPO`), no con un contador aparte — mismo principio
    que el cupo diario y el panel de finanzas: un numero guardado a mano se
    puede desincronizar de la reserva real, contar la reserva no.
    """
    if not promo.activo:
        return False

    ahora = timezone.now()
    if promo.fecha_inicio and ahora < promo.fecha_inicio:
        return False
    if promo.fecha_fin and ahora > promo.fecha_fin:
        return False

    if monto_viaje is not None:
        minimo = promo.monto_minimo_en(moneda)
        if minimo is not None and monto_viaje < minimo:
            return False

    usados = Reserva.objects.filter(codigo_promocional=promo, estado__in=ESTADOS_QUE_OCUPAN_CUPO)
    if excluir_pk is not None:
        usados = usados.exclude(pk=excluir_pk)

    if promo.usos_maximos is not None and usados.count() >= promo.usos_maximos:
        return False

    if promo.usos_maximos_por_cliente is not None and correo_cliente:
        usados_de_este_cliente = usados.filter(correo_cliente__iexact=correo_cliente.strip())
        if usados_de_este_cliente.count() >= promo.usos_maximos_por_cliente:
            return False

    return True


def evaluar_codigo_promocional(codigo_str, correo_cliente, empresa):
    """Validacion en vivo, mientras el cliente escribe el codigo en el
    checkout: sin lock y sin `monto_viaje` (extras/transporte todavia no se
    resuelven en ese paso, asi que `monto_minimo` no se puede evaluar aqui
    todavia — lo confirma crear-pago, que si conoce el total exacto).
    None si el codigo no existe o no aplica; el CodigoPromocional si si.
    """
    if not codigo_str:
        return None
    try:
        promo = CodigoPromocional.objects.get(codigo=codigo_str.strip().upper(), empresa=empresa)
    except CodigoPromocional.DoesNotExist:
        return None
    return promo if codigo_promocional_valido(promo, correo_cliente) else None


def validar_codigo_promocional_en_pago(promo, moneda, monto_viaje, correo_cliente, empresa, excluir_pk=None):
    """Revalidacion autoritativa al confirmar el pago (webhook). Toma el lock
    de la fila del codigo antes de contar — mismo principio que
    `bloquear_cupo_del_dia`, pero aqui si hay una fila real que bloquear (el
    codigo, no "el dia"), asi que `select_for_update` alcanza sin necesitar
    un advisory lock.

    Lanza ValidationError con la clave `codigo_promocional` (no un mensaje
    plano) para que `apps/payments/services.py` distinga este rechazo del de
    cupo y cancele con el motivo real, no uno prestado.
    """
    try:
        promo_bloqueado = CodigoPromocional.objects.select_for_update().get(pk=promo.pk, empresa=empresa)
    except CodigoPromocional.DoesNotExist:
        raise ValidationError({'codigo_promocional': 'El codigo promocional ya no es valido.'})

    if not codigo_promocional_valido(
        promo_bloqueado, correo_cliente, monto_viaje=monto_viaje, moneda=moneda, excluir_pk=excluir_pk,
    ):
        raise ValidationError({'codigo_promocional': 'El codigo promocional ya no es valido.'})


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
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='vendedoras')
    codigo = models.SlugField(
        max_length=30,
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
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='vendedora_unico_por_empresa_codigo'),
        ]

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.get_username()

    @classmethod
    def por_codigo(cls, codigo, empresa):
        """La vendedora activa de ese codigo, o None. Un codigo que ya no existe
        (o que el cliente escribio mal) nunca debe tumbar un checkout."""
        if not codigo:
            return None
        return cls.objects.filter(codigo=codigo, empresa=empresa, activo=True).first()


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
    fecha_salida = models.DateField(
        null=True, blank=True,
        help_text='Fecha de check-out / fin de servicio. Vacio en servicios de un solo dia.'
    )
    hora = models.TimeField()
    numero_personas = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_PERSONAS)]
    )
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='reservas')
    servicio = models.ForeignKey(
        'fleet.Servicio', on_delete=models.PROTECT, null=True, blank=True, related_name='reservas',
        help_text='Servicio o experiencia que ampara esta reserva. Vacio = pesca deportiva (legacy).'
    )
    paquete = models.ForeignKey(
        'fleet.Paquete', on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas',
        help_text='Paquete que ampara esta reserva.'
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
    # Que version del texto acepto. La clausula 8(d) del deslinde promete
    # conservar "un registro del texto aceptado", y sin esto una constancia
    # apunta a lo que diga el sitio hoy, no a lo que el cliente leyo ese dia.
    deslinde_version = models.CharField(max_length=20, blank=True)

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

    # Igual que extras/transporte: se congela en CrearPagoView, nunca antes.
    # PROTECT porque descuento_aplicado (y precio_total) ya lo asumen —
    # borrar el codigo dejaria reservas historicas sin de donde salio su
    # descuento. Un codigo se desactiva (`activo=False`), no se borra.
    codigo_promocional = models.ForeignKey(
        'fleet.CodigoPromocional', on_delete=models.PROTECT, null=True, blank=True,
        related_name='reservas',
    )
    # Monto ya restado de precio_total (que es SIEMPRE el total final, post
    # descuento — es lo que de verdad cobro Stripe). El subtotal antes del
    # descuento se recupera como precio_total + descuento_aplicado, para no
    # tener un tercer numero que pueda desincronizarse de los otros dos.
    descuento_aplicado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Cuando entro el cobro con tarjeta. Es la fecha con la que ese dinero cuenta
    # en el panel de finanzas: `creado_en` es cuando el cliente abrio el checkout
    # y `actualizado_en` se mueve con cualquier edicion posterior, asi que ninguno
    # de los dos sirve para cuadrar un dia.
    pagada_en = models.DateTimeField(null=True, blank=True)

    # Cuando salio el segundo correo, el que dice con que capitan y en que panga
    # sale el cliente. Existe para que no salga dos veces: la agenda se guarda
    # muchas veces por reserva y el cliente recibe este aviso una sola.
    aviso_asignacion_enviado_en = models.DateTimeField(null=True, blank=True)

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

    # Brunch, licencia y carnada se venden con precio congelado
    # solo por el checkout web (ver ReservaExtra mas abajo,
    # y CrearPagoView, que es quien los escribe). Bebidas sigue sin precio en
    # linea: depende del tipo de bebida, no de algo que el catalogo resuelva.
    pide_bebidas = models.BooleanField(default=False, verbose_name='bebidas (a cotizar)')

    # Reservas que crea la vendedora fuera del checkout web (WhatsApp,
    # telefono) no tienen forma de congelar precio de catalogo — esta pieza
    # es web-only a proposito (ver docs/superpowers/specs/2026-08-28-extras-checkout-design.md,
    # seccion "Que pasa con lleva_lunch"). Mismo trato simple que pide_bebidas:
    # solo anota que el cliente quiere algo, se cotiza y cobra aparte.
    pide_extras_whatsapp = models.BooleanField(default=False, verbose_name='extras (a cotizar, reserva manual)')

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

    @property
    def noches(self):
        if self.fecha_salida and self.fecha_salida > self.fecha:
            return (self.fecha_salida - self.fecha).days
        return 1

    @property
    def fecha_fin_servicio(self):
        return self.fecha_salida or (self.fecha + timedelta(days=1))

    @classmethod
    def from_db(cls, db, field_names, values):
        # Guarda la salida original para poder aplicar la regla de 48 horas en
        # clean() cuando la vendedora reprograma una reserva ya existente.
        #
        # Solo si fecha/hora vinieron cargadas: una consulta con campos
        # restringidos (por ejemplo, la que arma el collector de borrado de
        # Django al revisar el PROTECT de `vendedora`) instancia con `fecha`
        # diferido. Leerlo aqui dispara `refresh_from_db(fields=['fecha'])`,
        # que vuelve a llamar a `from_db()` — y si esa segunda consulta
        # tambien viene restringida, se repite para siempre (RecursionError,
        # visto de verdad al borrar una Vendedora con reservas).
        instance = super().from_db(db, field_names, values)
        if 'fecha' in field_names and 'hora' in field_names:
            instance._salida_original = (instance.fecha, instance.hora)
        if 'vendedora' in field_names or 'vendedora_id' in field_names:
            instance._vendedora_original = instance.vendedora_id
        if 'estado' in field_names:
            instance._estado_original = instance.estado
        return instance

    def save(self, *args, **kwargs):
        estado_previo = getattr(self, '_estado_original', None)
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
        if self.pk and estado_previo is not None:
            era_ocupante = estado_previo in ESTADOS_QUE_OCUPAN_CUPO
            es_ocupante = self.estado in ESTADOS_QUE_OCUPAN_CUPO
            if era_ocupante != es_ocupante:
                self.ocupaciones.exclude(ocupa_cupo=es_ocupante).update(ocupa_cupo=es_ocupante)
                nuevo_estado_cupo = (
                    ReservaPaqueteComponente.EstadoCupo.OK
                    if es_ocupante
                    else ReservaPaqueteComponente.EstadoCupo.LIBERADO
                )
                self.componentes.exclude(estado_cupo=nuevo_estado_cupo).update(estado_cupo=nuevo_estado_cupo)
        self._estado_original = self.estado

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
        if self.fecha_salida and self.fecha_salida <= self.fecha:
            raise ValidationError({'fecha_salida': 'La fecha de salida debe ser posterior a la fecha de inicio.'})
        if self.estado in ESTADOS_QUE_OCUPAN_CUPO:
            if self.paquete_id:
                _validar_cupo_de_paquete(self)
            elif self.servicio_id and self.servicio.estrategia_cupo == 'por_noche':
                _validar_cupo_hospedaje(self)
            else:
                estrategia_cupo = self.servicio.estrategia_cupo if self.servicio_id else 'por_recurso_dia'
                validar_cupo_diario(
                    self.fecha, self.numero_personas, self.empresa,
                    excluir_pk=self.pk, estrategia_cupo=estrategia_cupo, servicio_id=self.servicio_id,
                )
            if self.codigo_promocional_id:
                validar_codigo_promocional_en_pago(
                    self.codigo_promocional, self.moneda,
                    (self.precio_total or 0) + (self.descuento_aplicado or 0),
                    self.correo_cliente, self.empresa, excluir_pk=self.pk,
                )
        if self.estado != self.Estado.CANCELADA and (self.cancelada_por_id or self.cancelada_en):
            raise ValidationError('cancelada_por/cancelada_en solo aplican cuando estado es cancelada.')
        if self.canal_origen == self.CanalOrigen.WEB and not self.deslinde_aceptado:
            raise ValidationError(
                {'deslinde_aceptado': 'La reserva web requiere aceptar el deslinde de responsabilidad.'}
            )
        self._validar_ventana_horaria()
        self._validar_tope_personas()
        self._validar_capacidad_embarcacion()
        self._validar_una_salida_por_dia()
        self._validar_cambio_de_fecha()
        self._validar_consistencia_de_empresa()

    def _validar_ventana_horaria(self):
        if self.servicio_id:
            ventana = self.servicio.ventana_horaria()
        else:
            ventana = (VENTANA_SALIDA_INICIO, VENTANA_SALIDA_FIN)  # pesca legacy
        if self.hora and ventana and not (ventana[0] <= self.hora <= ventana[1]):
            raise ValidationError({'hora': f'La hora debe estar entre {ventana[0]:%H:%M} y {ventana[1]:%H:%M}.'})

    def _validar_tope_personas(self):
        tope = MAX_PERSONAS
        if self.servicio_id and self.servicio.capacidad_maxima:
            tope = self.servicio.capacidad_maxima
        if self.numero_personas and self.numero_personas > tope:
            raise ValidationError({'numero_personas': f'Máximo {tope} personas para este servicio.'})


    def _validar_consistencia_de_empresa(self):
        """Ninguna FK puede pertenecer a otra Empresa. RLS filtra filas por
        consulta, no valida referencias cruzadas que arme el operador de
        plataforma desde el admin (sin formfield_for_foreignkey filtrado)."""
        for campo, relacionado in (
            ('embarcacion', self.embarcacion),
            ('capitan', self.capitan),
            ('vendedora', self.vendedora),
            ('codigo_promocional', self.codigo_promocional),
            ('servicio', self.servicio),
        ):
            if relacionado is not None and relacionado.empresa_id != self.empresa_id:
                raise ValidationError({
                    campo: f'{relacionado} pertenece a otra Empresa, no se puede usar aqui.',
                })
        if self.paquete_id and self.paquete.empresa_lider_id != self.empresa_id:
            raise ValidationError({
                'paquete': f'{self.paquete} tiene como empresa líder a {self.paquete.empresa_lider}, no coincide con la empresa de la reserva.',
            })

    def _validar_capacidad_embarcacion(self):
        if self.embarcacion_id and self.numero_personas > self.embarcacion.capacidad_maxima:
            raise ValidationError({
                'embarcacion': f'{self.embarcacion} admite hasta {self.embarcacion.capacidad_maxima} '
                               f'personas y la reserva es para {self.numero_personas}.',
            })

    def _validar_una_salida_por_dia(self):
        """Una panga hace un solo viaje al dia, y un capitan tambien.

        Las salidas son de 5 a 7am y el viaje dura de 6 a 7 horas: no hay forma de
        escalonar dos salidas con la misma panga. `backend/CLAUDE.md` decia lo
        contrario ("la doble asignacion no se valida a proposito") y esa nota se
        corrige junto con este cambio.

        Cuentan los estados que ya ocupan cupo: una reserva cancelada suelta su
        panga y su capitan para que otro viaje del dia los use.

        La regla ya estaba medio vigente sin que nadie la escribiera — el motor de
        cupo exige que haya al menos tantas pangas a flote como viajes, o sea, ya
        vende como si cada panga hiciera una sola salida diaria. Esto la hace
        cumplir del otro lado, al repartir.
        """
        del_dia = Reserva.objects.filter(
            fecha=self.fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa_id=self.empresa_id,
        )
        if self.pk:
            del_dia = del_dia.exclude(pk=self.pk)

        if self.embarcacion_id and del_dia.filter(embarcacion_id=self.embarcacion_id).exists():
            raise ValidationError({
                'embarcacion': f'{self.embarcacion.nombre} ya tiene un viaje el {self.fecha}. '
                               f'Una panga hace una sola salida por dia.',
            })

        if self.capitan_id and del_dia.filter(capitan_id=self.capitan_id).exists():
            raise ValidationError({
                'capitan': f'{self.capitan.nombre} ya tiene un viaje el {self.fecha}. '
                           f'Un capitan hace una sola salida por dia.',
            })

    @property
    def salida(self):
        return salida_aware(self.fecha, self.hora)

    @property
    def tiene_cotizaciones_pendientes(self):
        """Pidio algo cuyo precio no se cobro en linea y el agente debe cotizar."""
        return self.pide_bebidas or self.pide_extras_whatsapp

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


class ReservaOcupacion(models.Model):
    """Asignación de un recurso físico a una reserva en un intervalo semi-abierto [fecha_inicio, fecha_fin).

    Permite que una reserva ocupe 1..N recursos (ej. múltiples habitaciones)
    o recursos a lo largo de un rango multidía de hospedaje.
    """

    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name='ocupaciones'
    )
    reserva = models.ForeignKey(
        Reserva, on_delete=models.CASCADE, related_name='ocupaciones'
    )
    recurso = models.ForeignKey(
        'fleet.Recurso', on_delete=models.PROTECT, related_name='ocupaciones'
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    ocupa_cupo = models.BooleanField(default=True, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha_inicio', 'recurso']
        verbose_name = 'ocupación de recurso'
        verbose_name_plural = 'ocupaciones de recursos'

    def __init__(self, *args, **kwargs):
        self._ocupa_cupo_explicito = 'ocupa_cupo' in kwargs
        super().__init__(*args, **kwargs)

    def __str__(self):
        nombre_recurso = getattr(self.recurso, 'nombre', str(self.recurso_id)) if self.recurso_id else 'Sin recurso'
        return f'{nombre_recurso} [{self.fecha_inicio} a {self.fecha_fin}) - Reserva #{self.reserva_id}'

    def _reserva_o_ninguna(self):
        try:
            return self.reserva
        except (Reserva.DoesNotExist, AttributeError):
            return None

    def _recurso_o_ninguno(self):
        try:
            return self.recurso
        except Exception:
            return None

    def save(self, *args, **kwargs):
        reserva = self._reserva_o_ninguna()
        if self.reserva_id and not self.empresa_id and reserva is not None:
            self.empresa_id = reserva.empresa_id
        if not getattr(self, '_ocupa_cupo_explicito', False) and reserva is not None:
            self.ocupa_cupo = reserva.estado in ESTADOS_QUE_OCUPAN_CUPO
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        reserva = self._reserva_o_ninguna()
        if reserva is not None and not self.empresa_id:
            self.empresa_id = reserva.empresa_id

        if self.fecha_inicio and self.fecha_fin and self.fecha_fin <= self.fecha_inicio:
            raise ValidationError({
                'fecha_fin': 'La fecha de fin debe ser posterior a la fecha de inicio.'
            })

        if reserva is not None and self.empresa_id and reserva.empresa_id != self.empresa_id:
            raise ValidationError({
                'empresa': 'La empresa de la ocupación debe coincidir con la de la reserva.'
            })

        recurso = self._recurso_o_ninguno()
        if recurso is not None and self.empresa_id and recurso.empresa_id != self.empresa_id:
            raise ValidationError({
                'empresa': 'El recurso debe pertenecer a la misma empresa que la ocupación.'
            })

        if self.recurso_id and self.fecha_inicio and self.fecha_fin:
            if reserva is not None and reserva.estado not in ESTADOS_QUE_OCUPAN_CUPO:
                return

            qs = ReservaOcupacion.objects.filter(
                recurso_id=self.recurso_id,
                ocupa_cupo=True,
                fecha_inicio__lt=self.fecha_fin,
                fecha_fin__gt=self.fecha_inicio,
                empresa_id=self.empresa_id,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if self.reserva_id:
                qs = qs.exclude(reserva_id=self.reserva_id)

            nombre = recurso.nombre if recurso is not None else str(self.recurso_id)
            ocupacion = qs.first()
            if ocupacion:
                raise ValidationError(
                    f'El recurso {nombre} ya está ocupado en el rango '
                    f'[{ocupacion.fecha_inicio} a {ocupacion.fecha_fin}) por la reserva #{ocupacion.reserva_id}.'
                )


class ReservaExtra(models.Model):
    """Un extra del catalogo (brunch, licencia, carnada) que el cliente eligio
    en el checkout, para esta reserva.

    `precio_unitario`/`cantidad` quedan en null mientras la reserva sigue
    `pendiente_pago`: esta fila es solo la SELECCION. El unico que congela el
    precio es `CrearPagoView` (apps/payments/views.py), con el precio vigente
    del catalogo al momento de pagar — asi hay un solo lugar que decide
    cuanto cuesta algo, igual que ya pasa con `precio_total`.
    """

    reserva = models.ForeignKey(
        Reserva, on_delete=models.CASCADE, related_name='extras_seleccionados',
    )
    extras_item = models.ForeignKey(ExtrasItem, on_delete=models.PROTECT)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cantidad = models.PositiveSmallIntegerField(null=True, blank=True)
    # Lo que el cliente eligio en el checkout para un extra con `cantidad_editable`
    # (ver fleet.ExtrasItem). Null = todo el grupo (comportamiento de siempre). El
    # congelado real, `cantidad`, lo sigue poniendo solo CrearPagoView.
    cantidad_solicitada = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('reserva', 'extras_item')
        verbose_name = 'extra seleccionado'
        verbose_name_plural = 'extras seleccionados'

    def __str__(self):
        return f'{self.extras_item.nombre} — reserva {self.reserva_id}'

    @property
    def subtotal(self):
        if self.precio_unitario is None or self.cantidad is None:
            return None
        return self.precio_unitario * self.cantidad

    def clean(self):
        if self.extras_item_id:
            reserva = self._reserva_o_ninguna()
            if reserva is not None and self.extras_item.empresa_id != reserva.empresa_id:
                raise ValidationError({
                    'extras_item': 'Ese extra pertenece a otra Empresa.',
                })

    def _reserva_o_ninguna(self):
        try:
            return self.reserva
        except Reserva.DoesNotExist:
            return None


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


class ReservaPaquetePersonalizacion(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='paquete_personalizaciones')
    servicio_personalizacion = models.ForeignKey('fleet.ServicioPersonalizacion', on_delete=models.PROTECT)
    cantidad = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['reserva', 'servicio_personalizacion'], name='reservapaquetepers_unico')
        ]
        verbose_name = 'personalización de paquete'
        verbose_name_plural = 'personalizaciones de paquete'

    def __str__(self):
        return f"Personalización #{self.servicio_personalizacion_id} (x{self.cantidad}) en Reserva #{self.reserva_id}"


class ReservaPaqueteComponente(models.Model):
    class EstadoCupo(models.TextChoices):
        OK = 'ok', 'Cupo reservado'
        LIBERADO = 'liberado', 'Liberado (reserva cancelada)'

    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='componentes')
    servicio = models.ForeignKey('fleet.Servicio', on_delete=models.PROTECT)
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT)  # = servicio.empresa
    estado_cupo = models.CharField(max_length=10, choices=EstadoCupo.choices, default=EstadoCupo.OK)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['reserva', 'servicio'], name='reservapaquetecomponente_unico')
        ]
        verbose_name = 'componente de paquete'
        verbose_name_plural = 'componentes de paquete'

    def __str__(self):
        return f"Componente {self.servicio} ({self.estado_cupo}) en Reserva #{self.reserva_id}"
