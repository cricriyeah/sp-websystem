"""La disputa (contracargo) tiene que verse en el admin.

El webhook ya levantaba `en_disputa`, pero el campo estaba en el bloque
colapsado «Registro del sistema» y su filtro entre los avanzados: la
vendedora no tenia forma de enterarse de que un cliente disputo el cobro de
un viaje a punto de salir.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone

from apps.testing import EmpresaTestCase

from .models import Reserva
from .tests import crear_reserva


class DisputaVisibleEnElAdminTests(EmpresaTestCase):
    def setUp(self):
        self.model_admin = admin.site._registry[Reserva]
        self.client.force_login(self.crear_vendedora())
        self.lista = reverse('admin:bookings_reserva_changelist')

    def reserva(self, nombre, **campos):
        datos = dict(
            estado=Reserva.Estado.PAGADA, forma_pago=Reserva.FormaPago.COMPLETO,
            precio_total=Decimal('4500.00'), monto_pagado=Decimal('4500.00'),
            fecha=timezone.localdate() + timedelta(days=3),
        )
        datos.update(campos)
        return crear_reserva(self.empresa, nombre_cliente=nombre, **datos)

    def test_la_fila_marca_la_disputa_en_la_columna_de_cobro(self):
        en_disputa = self.reserva('Con disputa', en_disputa=True)
        normal = self.reserva('Normal')

        texto = str(self.model_admin.cobro(en_disputa))
        self.assertIn('En disputa', texto)
        self.assertIn('reservas-cobro-urgente', texto)
        self.assertIn('Pagado', texto)  # no esconde el estado del cobro
        self.assertNotIn('En disputa', str(self.model_admin.cobro(normal)))

    def test_el_listado_la_muestra_y_la_cabecera_de_la_reserva_tambien(self):
        en_disputa = self.reserva('Con disputa', en_disputa=True)

        self.assertContains(self.client.get(self.lista, {'vista': 'todas'}), 'En disputa')
        cabecera = self.client.get(reverse('admin:bookings_reserva_change', args=[en_disputa.pk]))
        self.assertContains(cabecera, 'En disputa')

    def test_el_filtro_de_disputa_esta_a_la_vista_y_filtra(self):
        en_disputa = self.reserva('Con disputa', en_disputa=True)
        self.reserva('Normal')

        respuesta = self.client.get(self.lista, {'vista': 'todas', 'en_disputa__exact': '1'})

        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list], [en_disputa.pk])
        visibles = [getattr(spec, 'field_path', None) for spec in respuesta.context['filtros_reservas_visibles']]
        self.assertIn('en_disputa', visibles)

    def test_el_campo_esta_junto_al_cobro_y_no_en_el_bloque_colapsado(self):
        reserva = self.reserva('Con disputa', en_disputa=True)
        request = type('R', (), {'user': self.crear_jefe(username='jefa-d')})()

        fieldsets = dict(self.model_admin.get_fieldsets(request, reserva))

        self.assertIn('en_disputa', fieldsets['Cobro']['fields'])
        self.assertNotIn('en_disputa', fieldsets['Registro del sistema']['fields'])
        self.assertIn('en_disputa', self.model_admin.readonly_fields)
