"""Contexto del Inicio de Unfold, calculado bajo el alcance de la petición."""

from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.db.models import DecimalField, F, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import (
    Agenda, CheckoutAbandonado, ESTADOS_QUE_OCUPAN_CUPO, Reserva,
)
from apps.finance.services import balances

from . import scope
from .models import Empresa, MembresiaEmpresa
from .permisos_unfold import puede_ver_finanzas


def _url(nombre, **filtros):
    base = reverse(nombre)
    return f'{base}?{urlencode(filtros)}' if filtros else base


def _conteos(empresa, hoy, ahora):
    reservas = Reserva.objects.filter(empresa=empresa)
    cero = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))
    saldo_cubierto = Coalesce(F('monto_pagado'), cero) + Coalesce(F('monto_efectivo'), cero)
    return {
        'manana': Agenda.por_repartir().filter(
            empresa=empresa, fecha=hoy + timedelta(days=1), embarcacion__isnull=True,
        ).count(),
        'efectivo': reservas.filter(
            estado__in=[Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA],
            precio_total__gt=saldo_cubierto,
        ).count(),
        'nuevas': reservas.filter(
            estado__in=ESTADOS_QUE_OCUPAN_CUPO,
            creado_en__gte=ahora - timedelta(hours=24),
        ).count(),
        'abandonados': CheckoutAbandonado.abandonados().filter(empresa=empresa).count(),
    }


def _tarjetas(conteos, ahora):
    reservas = 'admin:bookings_reserva_changelist'
    return [
        {
            'clave': 'manana', 'titulo': 'Viajes de mañana sin panga',
            'numero': conteos['manana'], 'accion': 'Abrir Agenda',
            'url': _url('admin:bookings_agenda_changelist', cuando='manana'),
        },
        {
            'clave': 'efectivo', 'titulo': 'Saldos en efectivo por cobrar',
            'numero': conteos['efectivo'], 'accion': 'Ver reservas',
            'url': _url(reservas, estado__in='pagada,asignada'),
        },
        {
            'clave': 'nuevas', 'titulo': 'Reservas nuevas',
            'numero': conteos['nuevas'], 'accion': 'Ver reservas',
            'url': _url(
                reservas, estado__in=','.join(ESTADOS_QUE_OCUPAN_CUPO),
                creado_en__gte=(ahora - timedelta(hours=24)).isoformat(),
            ),
        },
        {
            'clave': 'abandonados', 'titulo': 'Checkouts por recuperar',
            'numero': conteos['abandonados'], 'accion': 'Ver checkouts',
            'url': _url('admin:bookings_checkoutabandonado_changelist'),
        },
    ]


def _rol(request):
    if scope.es_operador_plataforma(request.user):
        return 'operador', None
    empresa = scope.empresa_actual(request)
    if empresa is None:
        raise PermissionDenied
    rol = MembresiaEmpresa.objects.get(user=request.user, empresa=empresa).rol
    if rol == MembresiaEmpresa.Rol.JEFE:
        return 'jefe', empresa
    if rol == MembresiaEmpresa.Rol.VENDEDORA:
        return 'vendedora', empresa
    raise PermissionDenied


def puede_abrir_avanzado(request):
    rol, _ = _rol(request)
    return rol in ('jefe', 'operador')


def contexto_inicio(request, context):
    """Callback de Unfold; la vista avanzada reutiliza el índice sin hacer conteos."""
    if context.get('inicio_avanzado'):
        return context

    rol, empresa = _rol(request)
    ahora = timezone.now()
    hoy = timezone.localdate(ahora)
    if rol == 'operador':
        inicio = {
            'rol': rol,
            'filas': [
                {'empresa': e.nombre, 'conteos': _conteos(e, hoy, ahora)}
                for e in Empresa.objects.order_by('nombre')
            ],
        }
    else:
        inicio = {'rol': rol, 'tarjetas': _tarjetas(_conteos(empresa, hoy, ahora), ahora)}
        if rol == 'jefe':
            inicio['atrasados'] = Reserva.objects.filter(
                empresa=empresa, estado=Reserva.Estado.PAGADA, fecha__lt=hoy,
            ).count()
            if puede_ver_finanzas(request):
                dia = balances(hoy, hoy, empresa=empresa)
                mes = balances(hoy.replace(day=1), hoy, empresa=empresa)
                inicio['dinero'] = [
                    {
                        'moneda': moneda,
                        'hoy': dia[moneda].entradas if moneda in dia else Decimal('0.00'),
                        'mes': mes[moneda].entradas if moneda in mes else Decimal('0.00'),
                    }
                    for moneda in sorted(dia.keys() | mes.keys())
                ]
    return {**context, 'inicio': inicio}


def vista_avanzada(request):
    """El mismo índice del admin, mostrando la lista completa de aplicaciones."""
    from django.contrib import admin

    if not puede_abrir_avanzado(request):
        raise PermissionDenied
    return admin.site.index(request, extra_context={
        'inicio_avanzado': True,
        'title': 'Ajustes y vista avanzada',
    })
