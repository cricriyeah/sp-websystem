"""El admin de codigos promocionales avisa de las trampas que dejaban un codigo "sin limites" muerto.

Dos causas de datos hacen que un codigo creado en el backoffice no aplique en el checkout y
el cliente solo vea «no es valido» (a proposito: la respuesta publica no dice el motivo para
que nadie pruebe codigos al azar):

- un `0` en «usos maximos» (o por cliente) se lee como «cero usos»: el codigo nace agotado.
  El texto de ayuda dice «Vacio = sin limite», pero un 0 es facil de poner;
- el codigo pertenece a UNA empresa (puede repetirse en otra) y el operador de plataforma,
  que ve todas, no tenia forma de ver de cual era.

El admin si puede decir el motivo, asi que la lista muestra la empresa y si el codigo aplica hoy.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva, codigo_promocional_valido, motivo_codigo_no_aplica
from apps.fleet.models import CodigoPromocional
from apps.payments.tests import crear_reserva
from apps.payments.tests_codigo_promocional_admin import formulario_del_admin
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import EmpresaTestCase


class UsosEnCeroTests(EmpresaTestCase):
    def test_cero_usos_maximos_se_rechaza_al_validar(self):
        promo = CodigoPromocional(
            empresa=self.empresa, codigo='CERO', porcentaje_descuento=Decimal('10'), usos_maximos=0,
        )

        with self.assertRaises(ValidationError) as contexto:
            promo.full_clean()

        self.assertIn('usos_maximos', contexto.exception.error_dict)
        self.assertIn('vacío', ' '.join(contexto.exception.messages))

    def test_cero_usos_por_cliente_se_rechaza_al_validar(self):
        promo = CodigoPromocional(
            empresa=self.empresa, codigo='CERO', porcentaje_descuento=Decimal('10'),
            usos_maximos_por_cliente=0,
        )

        with self.assertRaises(ValidationError) as contexto:
            promo.full_clean()

        self.assertIn('usos_maximos_por_cliente', contexto.exception.error_dict)

    def test_vacio_y_uno_o_mas_si_valen(self):
        for usos in (None, 1, 50):
            with self.subTest(usos=usos):
                CodigoPromocional(
                    empresa=self.empresa, codigo=f'OK{usos}', porcentaje_descuento=Decimal('10'),
                    usos_maximos=usos, usos_maximos_por_cliente=usos,
                ).full_clean()

    def test_el_formulario_del_admin_no_guarda_un_cero(self):
        self.client.force_login(self.crear_jefe())

        respuesta = self.client.post(
            reverse('admin:fleet_codigopromocional_add'), formulario_del_admin(usos_maximos='0'),
        )

        self.assertEqual(respuesta.status_code, 200)  # vuelve al formulario con el error
        self.assertFalse(CodigoPromocional.objects.exists())
        self.assertContains(respuesta, 'vacío')


class MotivoPorElQueUnCodigoNoAplicaTests(EmpresaTestCase):
    def codigo(self, **campos):
        return CodigoPromocional.objects.create(
            empresa=self.empresa, codigo=campos.pop('codigo', 'MOTIVO'),
            porcentaje_descuento=Decimal('10'), **campos,
        )

    def test_un_codigo_sin_limites_aplica(self):
        self.assertIsNone(motivo_codigo_no_aplica(self.codigo(), 'ana@example.com'))

    def test_cada_motivo_tiene_nombre(self):
        ahora = timezone.now()
        casos = {
            'desactivado': self.codigo(codigo='A', activo=False),
            'aun_no_empieza': self.codigo(codigo='B', fecha_inicio=ahora + timedelta(days=2)),
            'vencido': self.codigo(codigo='C', fecha_fin=ahora - timedelta(days=2)),
            'agotado': self.codigo(codigo='D', usos_maximos=1),
        }
        crear_reserva(
            self.empresa, codigo_promocional=casos['agotado'], estado=Reserva.Estado.PAGADA,
        )

        for esperado, promo in casos.items():
            with self.subTest(motivo=esperado):
                self.assertEqual(motivo_codigo_no_aplica(promo, 'otro@example.com'), esperado)

    def test_bajo_el_minimo_solo_se_conoce_con_un_monto(self):
        promo = self.codigo(monto_minimo=Decimal('10000'))

        self.assertIsNone(motivo_codigo_no_aplica(promo, 'ana@example.com'))
        self.assertEqual(
            motivo_codigo_no_aplica(promo, 'ana@example.com', monto_viaje=Decimal('4500')),
            'bajo_el_minimo',
        )

    def test_agotado_para_este_cliente(self):
        promo = self.codigo(usos_maximos_por_cliente=1)
        crear_reserva(
            self.empresa, codigo_promocional=promo, estado=Reserva.Estado.PAGADA,
            correo_cliente='repetido@example.com',
        )

        self.assertEqual(
            motivo_codigo_no_aplica(promo, 'repetido@example.com'), 'agotado_por_cliente',
        )
        self.assertIsNone(motivo_codigo_no_aplica(promo, 'otro@example.com'))

    def test_valido_es_lo_mismo_que_sin_motivo(self):
        ahora = timezone.now()
        for promo in (
            self.codigo(codigo='A'),
            self.codigo(codigo='B', activo=False),
            self.codigo(codigo='C', fecha_fin=ahora - timedelta(days=1)),
        ):
            with self.subTest(codigo=promo.codigo):
                self.assertEqual(
                    codigo_promocional_valido(promo, 'ana@example.com'),
                    motivo_codigo_no_aplica(promo, 'ana@example.com') is None,
                )


class ListaDeCodigosParaElOperadorTests(TestCase):
    """El operador de plataforma ve los codigos de todas las empresas: tiene que ver de cual es cada uno."""

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede codigos', slug='sede-codigos')
        cls.sal = Empresa.objects.create(sede=sede, nombre='Sal y Sol Codigos', slug='sal-codigos')
        cls.ventana = Empresa.objects.create(sede=sede, nombre='La Ventana Codigos', slug='ventana-codigos')
        cls.operador = get_user_model().objects.create_user('op-codigos', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        with scope.como_operador_plataforma():
            CodigoPromocional.objects.create(
                empresa=cls.sal, codigo='SOLO10', porcentaje_descuento=Decimal('10'),
            )
            CodigoPromocional.objects.create(
                empresa=cls.ventana, codigo='VIEJO20', porcentaje_descuento=Decimal('20'), activo=False,
            )
        cls.url = reverse('admin:fleet_codigopromocional_changelist')

    def test_la_lista_dice_de_que_empresa_es_cada_codigo(self):
        self.client.force_login(self.operador)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Sal y Sol Codigos')
        self.assertContains(respuesta, 'La Ventana Codigos')

    def test_la_lista_dice_si_aplica_hoy_y_por_que_no(self):
        self.client.force_login(self.operador)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'Aplica')
        self.assertContains(respuesta, 'Desactivado')

    def test_se_puede_filtrar_por_empresa(self):
        self.client.force_login(self.operador)

        respuesta = self.client.get(self.url, {'empresa__id__exact': self.sal.pk})

        self.assertContains(respuesta, 'SOLO10')
        self.assertNotContains(respuesta, 'VIEJO20')


class ListaDeCodigosParaElJefeTests(EmpresaTestCase):
    def test_el_jefe_ve_si_aplica_y_el_motivo_cuando_no(self):
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VIGENTE', porcentaje_descuento=Decimal('10'),
        )
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VENCIDO', porcentaje_descuento=Decimal('10'),
            fecha_fin=timezone.now() - timedelta(days=3),
        )
        self.client.force_login(self.crear_jefe())

        respuesta = self.client.get(reverse('admin:fleet_codigopromocional_changelist'))

        self.assertContains(respuesta, 'Aplica')
        self.assertContains(respuesta, 'Venció')
