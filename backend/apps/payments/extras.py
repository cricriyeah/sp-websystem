"""Cotización y congelado de extras (personalizaciones) de una Reserva.

Único lugar donde se calcula el cargo de extras: lo usan `CrearPagoView` (reserva
suelta o paquete de una empresa) y `CrearPagoOrdenView` (cada reserva de la orden)."""
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.fleet.models import Personalizacion, ServicioPersonalizacion
from apps.payments.pricing import cantidad_efectiva, cargo_personalizacion


def cotizar_personalizaciones(reserva):
    """Valida y cotiza el catálogo vigente de la reserva.

    Devuelve `(cargo_total, a_borrar, a_congelar, error)`. No escribe nada: los
    renglones inválidos se eliminan y los precios se congelan únicamente después de
    que Stripe acepte crear o actualizar el PaymentIntent (`congelar_personalizaciones`).
    """
    if reserva.paquete_id:
        activos_ids = list(
            reserva.paquete.servicios_asociados.filter(
                servicio__activo=True
            ).values_list('servicio_id', flat=True)
        )
        disponibles = {
            sp.pk: sp
            for sp in ServicioPersonalizacion.objects.filter(
                servicio_id__in=activos_ids,
                servicio__empresa=reserva.empresa,
                personalizacion__empresa=reserva.empresa,
                activo=True,
                personalizacion__activo=True,
            ).select_related('servicio', 'personalizacion')
        }
    else:
        disponibles = {
            sp.pk: sp
            for sp in ServicioPersonalizacion.objects.filter(
                servicio=reserva.servicio,
                activo=True,
                personalizacion__activo=True,
            ).select_related('servicio', 'personalizacion')
        }
    seleccionadas = list(
        reserva.personalizaciones_seleccionadas.select_related(
            'servicio_personalizacion__servicio',
            'servicio_personalizacion__personalizacion',
        )
    )
    seleccionadas_por_id = {
        fila.servicio_personalizacion_id: fila for fila in seleccionadas
    }

    faltantes = [
        sp.personalizacion.nombre
        for sp in disponibles.values()
        if (
            sp.personalizacion.tipo_interaccion != Personalizacion.TipoInteraccion.CHECK
            and sp.obligatorio
            and sp.pk not in seleccionadas_por_id
        )
    ]
    if faltantes:
        return 0, [], [], f'Falta responder "{faltantes[0]}" antes de pagar.'

    cargo_total = Decimal('0.00')
    a_borrar = []
    a_congelar = []
    for fila in seleccionadas:
        sp = disponibles.get(fila.servicio_personalizacion_id)
        if sp is None:
            a_borrar.append(fila)
            continue

        # Usa las relaciones ya verificadas del catálogo vigente para que
        # full_clean también detecte una configuración que dejó de ser válida.
        fila.servicio_personalizacion = sp
        try:
            sp.full_clean()
            fila.full_clean()
        except DjangoValidationError:
            return 0, [], [], (
                f'La configuración de "{sp.personalizacion.nombre}" cambió. '
                'Revisa tu selección antes de pagar.'
            )

        if sp.personalizacion.tipo_interaccion != Personalizacion.TipoInteraccion.CHECK:
            a_congelar.append((fila, None, 1))
            continue

        try:
            precio = sp.precio_en(reserva.moneda, reserva.tipo_cambio)
        except ValueError:
            return 0, [], [], (
                f'No se pudo cotizar "{sp.personalizacion.nombre}" en {reserva.moneda}: '
                'la reserva no tiene tipo de cambio.'
            )
        # Las personas de un extra son las de SU servicio, no las del pedido entero.
        personas = reserva.personas_de(sp.servicio_id)
        cantidad = cantidad_efectiva(
            cobrar_por_persona=sp.personalizacion.cobrar_por_persona,
            cantidad_editable=sp.personalizacion.cantidad_editable,
            personas=personas,
            cantidad=fila.cantidad,
        )
        cargo_total += cargo_personalizacion(
            precio,
            cobrar_por_persona=sp.personalizacion.cobrar_por_persona,
            cantidad_editable=sp.personalizacion.cantidad_editable,
            personas=personas,
            cantidad=cantidad,
        )
        a_congelar.append((fila, precio, cantidad))

    return cargo_total, a_borrar, a_congelar, None


def congelar_personalizaciones(a_borrar, a_congelar):
    """Congela precio y cantidad ya cotizados. Llamar dentro de una transacción."""
    for extra in a_borrar:
        extra.delete()
    for extra, precio_unitario, cantidad in a_congelar:
        extra.precio_unitario = precio_unitario
        extra.cantidad = cantidad
        extra.save(update_fields=['precio_unitario', 'cantidad'])
