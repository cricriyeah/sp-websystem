from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.fleet.models import Paquete
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca
from apps.tenancy.models import Empresa
from apps.tenancy import scope

from .models import Reserva


class AltaReservaEmpresaTests(EmpresaTestCase):
    def setUp(self):
        self.servicio = crear_servicio_pesca(self.empresa)
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_reserva_add')

    def _datos(self, **extra):
        datos = {
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '612 123 4567',
            'correo_cliente': 'ana@example.com',
            'fecha': (timezone.localdate() + timedelta(days=10)).isoformat(),
            'hora': '06:00',
            'numero_personas': '2',
            'servicio': str(self.servicio.pk),
            'canal_origen': Reserva.CanalOrigen.WHATSAPP,
            'estado': Reserva.Estado.PENDIENTE_PAGO,
            'moneda': Reserva.Moneda.MXN,
            'forma_pago': Reserva.FormaPago.COMPLETO,
            **extra,
        }
        for prefijo in ('personalizaciones_seleccionadas', 'ocupaciones', 'componentes', 'detalle_transporte'):
            datos[f'{prefijo}-TOTAL_FORMS'] = '0'
            datos[f'{prefijo}-INITIAL_FORMS'] = '0'
        return datos

    def test_vendedora_crea_servicio_pendiente_sin_elegir_empresa(self):
        self.client.force_login(self.crear_vendedora())
        respuesta = self.client.post(self.url, self._datos(empresa='999999'))
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and (
            respuesta.context['adminform'].form.errors,
            [(fs.formset.prefix, fs.formset.non_form_errors()) for fs in respuesta.context['inline_admin_formsets']],
        ))
        reserva = Reserva.objects.get(nombre_cliente='Ana Ruiz')
        self.assertEqual(reserva.empresa_id, self.empresa.pk)
        self.assertEqual(reserva.servicio_id, self.servicio.pk)

    def test_jefe_crea_paquete_pagado_sin_elegir_empresa(self):
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Paquete prueba',
            slug='paquete-prueba', precio_ancla=1000,
        )
        self.client.force_login(self.crear_jefe())
        respuesta = self.client.post(self.url, self._datos(
            servicio='', paquete=str(paquete.pk), estado=Reserva.Estado.PAGADA,
            precio_total='1000.00', monto_pagado='1000.00', empresa='999999',
        ))
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and (
            respuesta.context['adminform'].form.errors,
            [(fs.formset.prefix, fs.formset.non_form_errors()) for fs in respuesta.context['inline_admin_formsets']],
        ))
        reserva = Reserva.objects.get(nombre_cliente='Ana Ruiz')
        self.assertEqual(reserva.empresa_id, self.empresa.pk)
        self.assertEqual(reserva.paquete_id, paquete.pk)

    def test_vendedora_no_crea_con_servicio_de_otra_empresa(self):
        ajena = Empresa.objects.create(sede=self.sede, nombre='Ajena', slug='ajena')
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(ajena):
                servicio_ajeno = crear_servicio_pesca(ajena)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.client.force_login(self.crear_vendedora())
        respuesta = self.client.post(self.url, self._datos(
            servicio=str(servicio_ajeno.pk), empresa=str(ajena.pk),
        ))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Ana Ruiz').exists())

    def test_usuario_sin_empresa_no_puede_crear(self):
        usuario = get_user_model().objects.create_user('sin-empresa', password='x', is_staff=True)
        self.client.force_login(usuario)
        self.assertEqual(self.client.post(self.url, self._datos(empresa=str(self.empresa.pk))).status_code, 403)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Ana Ruiz').exists())
