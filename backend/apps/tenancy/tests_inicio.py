"""El Inicio muestra trabajo y dinero solo dentro del alcance del usuario."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.fleet.models import Embarcacion, Servicio

from . import scope
from .models import Empresa, MembresiaEmpresa, Sede


class InicioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede inicio', slug='sede-inicio')
        cls.empresa_a = Empresa.objects.create(sede=sede, nombre='Empresa A', slug='inicio-a')
        cls.empresa_b = Empresa.objects.create(sede=sede, nombre='Empresa B', slug='inicio-b')
        cls.vendedora = cls._usuario('venta-inicio', 'Vendedora', cls.empresa_a)
        cls.jefe = cls._usuario('jefe-inicio', 'Jefe', cls.empresa_a)
        cls.operador = cls._usuario('operador-inicio', 'OperadorPlataforma', None)

        with scope.como_operador_plataforma():
            cls.servicio_a = Servicio.objects.create(
                empresa=cls.empresa_a, nombre='Pesca A', slug='pesca-a', tipo_servicio='pesca',
            )
            cls.servicio_b = Servicio.objects.create(
                empresa=cls.empresa_b, nombre='Pesca B', slug='pesca-b', tipo_servicio='pesca',
            )
            cls.panga_a = Embarcacion.objects.create(
                empresa=cls.empresa_a, nombre='Panga de prueba',
                clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
            )

    @classmethod
    def _usuario(cls, username, grupo, empresa):
        user = get_user_model().objects.create_user(username, password='x', is_staff=True)
        user.groups.add(Group.objects.get(name=grupo))
        if empresa:
            MembresiaEmpresa.objects.create(
                user=user, empresa=empresa, rol=grupo.upper(),
            )
        return user

    def _reserva(self, empresa, *, estado=Reserva.Estado.PAGADA, fecha=None,
                 precio='100.00', pagado='30.00', efectivo=None, creada_hace=None,
                 moneda=Reserva.Moneda.MXN, pagada_en=None):
        servicio = self.servicio_a if empresa == self.empresa_a else self.servicio_b
        reserva = Reserva.objects.create(
            empresa=empresa, servicio=servicio,
            fecha=fecha or timezone.localdate() + timedelta(days=1),
            numero_personas=2, nombre_cliente='Ana Ruiz',
            telefono_cliente='6121234567', correo_cliente='ana@example.com',
            canal_origen=Reserva.CanalOrigen.WEB, estado=estado, moneda=moneda,
            embarcacion=self.panga_a if estado == Reserva.Estado.ASIGNADA else None,
            precio_total=Decimal(precio), monto_pagado=Decimal(pagado),
            monto_efectivo=Decimal(efectivo) if efectivo is not None else None,
            pagada_en=pagada_en,
        )
        if creada_hace is not None:
            Reserva.objects.filter(pk=reserva.pk).update(
                creado_en=timezone.now() - timedelta(hours=creada_hace))
        return reserva

    def _contexto(self, user, empresa=None):
        from .inicio import contexto_inicio

        request = RequestFactory().get('/admin/')
        request.user = user
        alcance = scope.con_empresa(empresa) if empresa else scope.como_operador_plataforma()
        with alcance:
            return contexto_inicio(request, {})['inicio']

    def test_vendedora_ve_cuatro_tarjetas_y_solo_su_empresa(self):
        with scope.como_operador_plataforma():
            self._reserva(self.empresa_a)
            self._reserva(self.empresa_a, estado=Reserva.Estado.ASIGNADA, efectivo='70.00')
            self._reserva(self.empresa_a, estado=Reserva.Estado.PENDIENTE_PAGO, creada_hace=3)
            self._reserva(self.empresa_b)
            self._reserva(self.empresa_b, estado=Reserva.Estado.PENDIENTE_PAGO, creada_hace=3)

        inicio = self._contexto(self.vendedora, self.empresa_a)
        self.assertEqual(inicio['rol'], 'vendedora')
        self.assertEqual(
            {t['clave']: t['numero'] for t in inicio['tarjetas']},
            {'manana': 1, 'efectivo': 1, 'nuevas': 2, 'abandonados': 1},
        )
        self.assertEqual(len(inicio['tarjetas']), 4)
        self.assertNotIn('dinero', inicio)
        self.assertNotIn('atrasados', inicio)
        self.assertIn('cuando=manana', inicio['tarjetas'][0]['url'])

    def test_los_conteos_respetan_estados_y_ventanas_de_tiempo(self):
        with scope.con_empresa(self.empresa_a):
            self._reserva(self.empresa_a, creada_hace=25)
            self._reserva(self.empresa_a, estado=Reserva.Estado.PENDIENTE_PAGO, creada_hace=1)
            self._reserva(self.empresa_a, estado=Reserva.Estado.CANCELADA, creada_hace=4)
            self._reserva(self.empresa_a, fecha=timezone.localdate() + timedelta(days=2))

        conteos = {t['clave']: t['numero'] for t in self._contexto(self.vendedora, self.empresa_a)['tarjetas']}
        self.assertEqual(conteos, {'manana': 1, 'efectivo': 2, 'nuevas': 1, 'abandonados': 0})

    def test_jefe_ve_atrasados_y_entradas_separadas_por_moneda(self):
        ahora = timezone.now()
        primer_dia = timezone.localtime(ahora).replace(
            day=1, hour=12, minute=0, second=0, microsecond=0,
        )
        with scope.con_empresa(self.empresa_a):
            self._reserva(self.empresa_a, fecha=timezone.localdate() - timedelta(days=1),
                          pagada_en=ahora, precio='100.00', pagado='30.00')
            if timezone.localdate(ahora).day > 1:
                self._reserva(self.empresa_a, precio='20.00', pagado='20.00',
                              pagada_en=primer_dia)
            self._reserva(self.empresa_a, estado=Reserva.Estado.ASIGNADA,
                          moneda=Reserva.Moneda.USD, precio='40.00', pagado='40.00',
                          pagada_en=ahora)
        with scope.con_empresa(self.empresa_b):
            self._reserva(self.empresa_b, pagada_en=ahora, precio='900.00', pagado='900.00')

        inicio = self._contexto(self.jefe, self.empresa_a)
        self.assertEqual(inicio['rol'], 'jefe')
        self.assertEqual(inicio['atrasados'], 1)
        self.assertEqual(len(inicio['tarjetas']), 4)
        self.assertEqual(
            {fila['moneda']: (fila['hoy'], fila['mes']) for fila in inicio['dinero']},
            {'MXN': (Decimal('30.00'), Decimal('50.00') if timezone.localdate(ahora).day > 1
                     else Decimal('30.00')),
             'USD': (Decimal('40.00'), Decimal('40.00'))},
        )

    def test_operador_ve_una_fila_con_cuatro_conteos_por_empresa(self):
        with scope.con_empresa(self.empresa_a):
            self._reserva(self.empresa_a)
        with scope.con_empresa(self.empresa_b):
            self._reserva(self.empresa_b, estado=Reserva.Estado.PENDIENTE_PAGO, creada_hace=3)

        inicio = self._contexto(self.operador)
        self.assertEqual(inicio['rol'], 'operador')
        self.assertNotIn('tarjetas', inicio)
        self.assertEqual(
            [(fila['empresa'], fila['conteos']) for fila in inicio['filas']],
            [('Empresa A', {'manana': 1, 'efectivo': 1, 'nuevas': 1, 'abandonados': 0}),
             ('Empresa B', {'manana': 0, 'efectivo': 0, 'nuevas': 0, 'abandonados': 1}),
             ('Sal y Sol Sportfishing', {'manana': 0, 'efectivo': 0, 'nuevas': 0, 'abandonados': 0})],
        )

    def test_inicio_y_vista_avanzada_respetan_el_rol(self):
        self.client.force_login(self.vendedora)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Viajes de mañana')
        self.assertNotContains(response, 'Ajustes y vista avanzada')
        self.assertNotContains(response, 'Axes')
        self.assertEqual(self.client.get(reverse('admin_avanzado')).status_code, 403)

        self.client.force_login(self.jefe)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Ajustes y vista avanzada')
        response = self.client.get(reverse('admin_avanzado'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Embarcaciones')

        self.client.force_login(self.operador)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Empresa A')
        self.assertNotContains(response, 'inicio-tarjeta')
        self.assertEqual(self.client.get(reverse('admin_avanzado')).status_code, 200)

    def test_los_enlaces_de_las_tarjetas_abren_listados_del_admin(self):
        with scope.con_empresa(self.empresa_a):
            self._reserva(self.empresa_a)
            self._reserva(self.empresa_a, estado=Reserva.Estado.PENDIENTE_PAGO, creada_hace=3)
        self.client.force_login(self.vendedora)
        for tarjeta in self._contexto(self.vendedora, self.empresa_a)['tarjetas']:
            with self.subTest(tarjeta=tarjeta['clave']):
                self.assertEqual(self.client.get(tarjeta['url']).status_code, 200)
