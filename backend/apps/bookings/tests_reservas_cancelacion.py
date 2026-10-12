from decimal import Decimal

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.formats import date_format

from apps.bookings.models import Reserva
from apps.bookings.tests import crear_reserva
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede
from apps.testing import EmpresaTestCase


class ConfirmacionMalClimaTests(EmpresaTestCase):
    def setUp(self):
        self.usuario = self.crear_vendedora()
        self.client.force_login(self.usuario)
        self.url = reverse('admin:bookings_reserva_changelist')

    def accion(self, reservas, **extra):
        return self.client.post(self.url, {
            'action': 'cancelar_por_mal_clima',
            '_selected_action': [str(reserva.pk) for reserva in reservas],
            **extra,
        })

    def test_orden_de_acciones_deja_cancelacion_al_final(self):
        respuesta = self.client.get(self.url, {'vista': 'todas'})
        acciones = [valor for valor, _ in respuesta.context['action_form'].fields['action'].choices
                    if valor]
        self.assertEqual(
            [accion for accion in acciones if accion != 'delete_selected'],
            ['registrar_liquidacion_en_efectivo', 'marcar_como_venta_mia',
             'confirmar_devolucion', 'cancelar_por_mal_clima'],
        )
        self.assertTrue(dict(respuesta.context['action_form'].fields['action'].choices)[
            'cancelar_por_mal_clima'].startswith('\u26a0'))

    def test_previa_muestra_conteos_monedas_efectivo_y_siguiente_paso(self):
        mxn = crear_reserva(self.empresa, nombre_cliente='Ana MXN', estado=Reserva.Estado.PAGADA,
                            monto_pagado=Decimal('200.00'), monto_efectivo=Decimal('30.00'))
        usd = crear_reserva(self.empresa, nombre_cliente='Beto USD', estado=Reserva.Estado.PAGADA,
                            moneda=Reserva.Moneda.USD, monto_pagado=Decimal('40.00'))
        pendiente = crear_reserva(self.empresa, nombre_cliente='Cora pendiente',
                                  estado=Reserva.Estado.PENDIENTE_PAGO)
        cancelada = crear_reserva(self.empresa, nombre_cliente='Dora cancelada',
                                  estado=Reserva.Estado.CANCELADA,
                                  monto_pagado=Decimal('500.00'))
        respuesta = self.accion([mxn, usd, pendiente, cancelada])
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '3 reservas se cancelar')
        self.assertContains(respuesta, '1 ya cancelada')
        for nombre in ('Ana MXN', 'Beto USD', 'Cora pendiente'):
            self.assertContains(respuesta, nombre)
        self.assertContains(respuesta, date_format(mxn.fecha, 'j M Y'))
        self.assertContains(respuesta, 'Ana MXN &middot; 2 personas')
        self.assertNotContains(respuesta, 'Dora cancelada</')
        self.assertContains(respuesta, '200.00 MXN')
        self.assertContains(respuesta, '40.00 USD')
        self.assertNotContains(respuesta, '500.00 MXN')
        self.assertContains(respuesta, '30.00 MXN en efectivo')
        self.assertContains(respuesta, 'Stripe')
        self.assertContains(respuesta, 'Confirmar devoluci')
        self.assertContains(respuesta, 'S&iacute;, cancelar 3 reservas')
        self.assertContains(respuesta, 'No, volver')
        self.assertContains(respuesta, 'name="csrfmiddlewaretoken"')
        for reserva in (mxn, usd, pendiente, cancelada):
            reserva.refresh_from_db()
            self.assertNotEqual(reserva.cancelada_por_id, self.usuario.pk)

    def test_post_sin_confirmacion_no_cancela_y_con_confirmacion_deja_history(self):
        reserva = crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA,
                                monto_pagado=Decimal('100.00'))
        self.accion([reserva])
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        respuesta = self.accion([reserva], confirmar_cancelacion='si')
        self.assertEqual(respuesta.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
        self.assertEqual(reserva.motivo_cancelacion, 'Mal clima')
        self.assertEqual(reserva.cancelada_por, self.usuario)
        self.assertIsNotNone(reserva.cancelada_en)
        self.assertTrue(reserva.reembolsada)
        self.assertIsNone(reserva.monto_reembolsado)
        self.assertTrue(LogEntry.objects.filter(object_id=str(reserva.pk), user=self.usuario).exists())
        self.assertIn('Stripe', str(list(respuesta.wsgi_request._messages)))

    def test_pendiente_sin_monto_muestra_cero_y_conserva_efecto_de_cancelacion(self):
        pendiente = crear_reserva(self.empresa, estado=Reserva.Estado.PENDIENTE_PAGO,
                                  monto_pagado=None)
        previa = self.accion([pendiente])
        self.assertContains(previa, '0.00 MXN')
        self.accion([pendiente], confirmar_cancelacion='si')
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, Reserva.Estado.CANCELADA)
        self.assertTrue(pendiente.reembolsada)
        self.assertIsNone(pendiente.monto_reembolsado)

    def test_ya_cancelada_se_omite_sin_cambiar_sus_datos_ni_crear_log(self):
        cancelada = crear_reserva(self.empresa, estado=Reserva.Estado.CANCELADA,
                                  motivo_cancelacion='Otro motivo')
        pagada = crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        respuesta = self.accion([cancelada, pagada], confirmar_cancelacion='si')
        self.assertEqual(respuesta.status_code, 302)
        cancelada.refresh_from_db()
        self.assertEqual(cancelada.motivo_cancelacion, 'Otro motivo')
        self.assertIsNone(cancelada.cancelada_por)
        self.assertFalse(LogEntry.objects.filter(object_id=str(cancelada.pk)).exists())

    def test_vendedora_sin_permiso_de_cambio_no_puede_confirmar(self):
        reserva = crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        sin_permiso = self.crear_vendedora(username='sin-cambio', permisos=[])
        sin_permiso.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(sin_permiso)
        respuesta = self.accion([reserva], confirmar_cancelacion='si')
        self.assertEqual(respuesta.status_code, 403)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)

    def test_csrf_rechaza_confirmacion_sin_token(self):
        reserva = crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.usuario)
        respuesta = cliente.post(self.url, {
            'action': 'cancelar_por_mal_clima',
            '_selected_action': [str(reserva.pk)],
            'confirmar_cancelacion': 'si',
        })
        self.assertEqual(respuesta.status_code, 403)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)


class CancelacionMalClimaEmpresasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede clima', slug='sede-clima')
        cls.a = Empresa.objects.create(sede=sede, nombre='Empresa A', slug='clima-a')
        cls.b = Empresa.objects.create(sede=sede, nombre='Empresa B', slug='clima-b')
        cls.operador = get_user_model().objects.create_user('op-clima', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        cls.vendedora = get_user_model().objects.create_user('ven-clima', password='x', is_staff=True)
        cls.vendedora.groups.add(Group.objects.get(name='Vendedora'))
        MembresiaEmpresa.objects.create(user=cls.vendedora, empresa=cls.a,
                                        rol=MembresiaEmpresa.Rol.VENDEDORA)
        with scope.como_operador_plataforma():
            cls.ra = crear_reserva(cls.a, estado=Reserva.Estado.PAGADA)
            cls.rb = crear_reserva(cls.b, estado=Reserva.Estado.PAGADA)

    def accion(self, usuario):
        self.client.force_login(usuario)
        return self.client.post(reverse('admin:bookings_reserva_changelist'), {
            'action': 'cancelar_por_mal_clima',
            '_selected_action': [str(self.ra.pk), str(self.rb.pk)],
            'confirmar_cancelacion': 'si',
        })

    def test_vendedora_solo_cancela_su_empresa(self):
        self.assertEqual(self.accion(self.vendedora).status_code, 302)
        with scope.como_operador_plataforma():
            self.ra.refresh_from_db()
            self.rb.refresh_from_db()
            self.assertEqual(self.ra.estado, Reserva.Estado.CANCELADA)
            self.assertEqual(self.rb.estado, Reserva.Estado.PAGADA)

    def test_operador_cancela_ambas_empresas(self):
        self.assertEqual(self.accion(self.operador).status_code, 302)
        with scope.como_operador_plataforma():
            self.ra.refresh_from_db()
            self.rb.refresh_from_db()
            self.assertEqual(self.ra.estado, Reserva.Estado.CANCELADA)
            self.assertEqual(self.rb.estado, Reserva.Estado.CANCELADA)
