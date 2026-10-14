from datetime import date, time, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib import admin
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.bookings.models import Reserva
from apps.fleet.models import Embarcacion, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede


class AccionesDeFilaAdminTests(TestCase):
    def setUp(self):
        call_command('setup_roles', stdout=StringIO())

        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede Acciones Fila', slug='sede-acciones-fila')
            self.empresa_a = Empresa.objects.create(
                sede=self.sede, nombre='Empresa A', slug='empresa-a-acciones',
            )
            self.empresa_b = Empresa.objects.create(
                sede=self.sede, nombre='Empresa B', slug='empresa-b-acciones',
            )

            self.servicio_a = Servicio.objects.create(
                empresa=self.empresa_a,
                nombre='Pesca A',
                slug='pesca-a-acciones',
                tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia',
                activo=True,
            )
            self.embarcacion_a = Embarcacion.objects.create(
                empresa=self.empresa_a,
                nombre='Embarcacion A',
                capacidad_maxima=4,
                activa=True,
            )
            self.reserva_a = Reserva.objects.create(
                empresa=self.empresa_a,
                servicio=self.servicio_a,
                embarcacion=self.embarcacion_a,
                fecha=date.today() + timedelta(days=5),
                hora=time(6, 0),
                numero_personas=2,
                nombre_cliente='Cliente A',
                telefono_cliente='+5216121234567',
                correo_cliente='clientea@example.com',
                canal_origen=Reserva.CanalOrigen.WEB,
                deslinde_aceptado=True,
                deslinde_nombre='Cliente A',
                precio_total=Decimal('1000.00'),
                monto_pagado=Decimal('1000.00'),
                estado=Reserva.Estado.PAGADA,
            )

            self.servicio_b = Servicio.objects.create(
                empresa=self.empresa_b,
                nombre='Pesca B',
                slug='pesca-b-acciones',
                tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia',
                activo=True,
            )
            self.reserva_b = Reserva.objects.create(
                empresa=self.empresa_b,
                servicio=self.servicio_b,
                fecha=date.today() + timedelta(days=5),
                hora=time(6, 0),
                numero_personas=2,
                nombre_cliente='Cliente B',
                telefono_cliente='+5216121234568',
                correo_cliente='clienteb@example.com',
                canal_origen=Reserva.CanalOrigen.WEB,
                deslinde_aceptado=True,
                deslinde_nombre='Cliente B',
                precio_total=Decimal('1000.00'),
                monto_pagado=Decimal('1000.00'),
                estado=Reserva.Estado.PAGADA,
            )

            # Usuarios con membresía
            self.vendedora_a = User.objects.create_user(
                username='vendedora_a_fila', password='password123', is_staff=True,
            )
            self.vendedora_a.groups.add(Group.objects.get(name='Vendedora'))
            MembresiaEmpresa.objects.create(
                user=self.vendedora_a,
                empresa=self.empresa_a,
                rol=MembresiaEmpresa.Rol.VENDEDORA,
            )

            self.jefe_a = User.objects.create_user(
                username='jefe_a_fila', password='password123', is_staff=True,
            )
            self.jefe_a.groups.add(Group.objects.get(name='Jefe'))
            MembresiaEmpresa.objects.create(
                user=self.jefe_a,
                empresa=self.empresa_a,
                rol=MembresiaEmpresa.Rol.JEFE,
            )

            self.operador = User.objects.create_user(
                username='operador_fila', password='password123', is_staff=True,
            )
            self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))

            # Usuario con membresía pero sólo permisos de lectura en Reserva
            grupo_solo_ver, _ = Group.objects.get_or_create(name='SoloVerReserva')
            ct_reserva = ContentType.objects.get(app_label='bookings', model='reserva')
            perm_view_reserva = Permission.objects.get(content_type=ct_reserva, codename='view_reserva')
            grupo_solo_ver.permissions.add(perm_view_reserva)

            self.usuario_solo_ver = User.objects.create_user(
                username='solo_ver_fila', password='password123', is_staff=True,
            )
            self.usuario_solo_ver.groups.add(grupo_solo_ver)
            MembresiaEmpresa.objects.create(
                user=self.usuario_solo_ver,
                empresa=self.empresa_a,
                rol=MembresiaEmpresa.Rol.VENDEDORA,
            )

    def test_lista_reservas_vendedora(self):
        """Lista de Reservas de una vendedora: la respuesta contiene el texto/URL de
        la acción de fila Editar y Cancelar, y NO contiene Eliminar (/delete/)."""
        self.client.force_login(self.vendedora_a)
        response = self.client.get(reverse('admin:bookings_reserva_changelist'))
        self.assertEqual(response.status_code, 200)

        # Acciones Editar y Cancelar visibles
        self.assertContains(response, 'Editar')
        self.assertContains(response, 'Cancelar')
        url_editar = reverse('admin:bookings_reserva_accion_fila_editar', args=[self.reserva_a.pk])
        url_cancelar = reverse('admin:bookings_reserva_accion_fila_cancelar', args=[self.reserva_a.pk])
        self.assertContains(response, url_editar)
        self.assertContains(response, url_cancelar)

        # NO contiene acción ni link de Eliminar (/delete/)
        self.assertNotContains(response, 'Eliminar')
        url_delete = reverse('admin:bookings_reserva_delete', args=[self.reserva_a.pk])
        self.assertNotContains(response, url_delete)

    def test_lista_reservas_operador_tampoco_tiene_eliminar(self):
        """NO aparece Eliminar en Reservas para nadie (ni operador)."""
        self.client.force_login(self.operador)
        response = self.client.get(reverse('admin:bookings_reserva_changelist'))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'Editar')
        self.assertContains(response, 'Cancelar')
        url_delete = reverse('admin:bookings_reserva_delete', args=[self.reserva_a.pk])
        self.assertNotContains(response, url_delete)

    def test_permisos_eliminar_jefe_vs_ver_vendedora_embarcacion(self):
        """Lista de un modelo con permiso de borrado para el jefe (Embarcacion)
        muestra Eliminar para el jefe; la vendedora, en un modelo donde solo puede ver,
        ve 'Ver' y no Editar ni Eliminar."""
        # 1. Jefe en Embarcacion
        self.client.force_login(self.jefe_a)
        response_jefe = self.client.get(reverse('admin:fleet_embarcacion_changelist'))
        self.assertEqual(response_jefe.status_code, 200)
        self.assertContains(response_jefe, 'Editar')
        self.assertContains(response_jefe, 'Eliminar')
        url_eliminar_jefe = reverse('admin:fleet_embarcacion_accion_fila_eliminar', args=[self.embarcacion_a.pk])
        self.assertContains(response_jefe, url_eliminar_jefe)
        url_ver_jefe = reverse('admin:fleet_embarcacion_accion_fila_ver', args=[self.embarcacion_a.pk])
        self.assertNotContains(response_jefe, url_ver_jefe)

        # 2. Vendedora en Embarcacion
        self.client.force_login(self.vendedora_a)
        response_vendedora = self.client.get(reverse('admin:fleet_embarcacion_changelist'))
        self.assertEqual(response_vendedora.status_code, 200)
        self.assertContains(response_vendedora, 'Ver')
        url_ver_vendedora = reverse('admin:fleet_embarcacion_accion_fila_ver', args=[self.embarcacion_a.pk])
        self.assertContains(response_vendedora, url_ver_vendedora)
        self.assertNotContains(
            response_vendedora,
            reverse('admin:fleet_embarcacion_accion_fila_editar', args=[self.embarcacion_a.pk]),
        )
        self.assertNotContains(
            response_vendedora,
            reverse('admin:fleet_embarcacion_accion_fila_eliminar', args=[self.embarcacion_a.pk]),
        )

    def test_accion_fila_cancelar_get_vendedora_y_aislamiento(self):
        """Ejecutar accion_fila_cancelar por GET como vendedora devuelve la página
        de confirmación (200, contiene 'Confirmar cancelaci'); para una reserva de
        OTRA empresa devuelve 404 (aislamiento)."""
        self.client.force_login(self.vendedora_a)

        # Reserva de su propia empresa: 200 con confirmación
        url_cancelar_propia = reverse('admin:bookings_reserva_accion_fila_cancelar', args=[self.reserva_a.pk])
        response_propia = self.client.get(url_cancelar_propia)
        self.assertEqual(response_propia.status_code, 200)
        self.assertContains(response_propia, 'Confirmar cancelaci')

        # Reserva de otra empresa: 404 por aislamiento
        url_cancelar_otra = reverse('admin:bookings_reserva_accion_fila_cancelar', args=[self.reserva_b.pk])
        response_otra = self.client.get(url_cancelar_otra)
        self.assertEqual(response_otra.status_code, 404)

    def test_accion_fila_cancelar_post_ejecuta_cancelacion(self):
        """POST a la confirmación de cancelación ejecuta la cancelación de esa reserva."""
        self.client.force_login(self.vendedora_a)
        url_cancelar = reverse('admin:bookings_reserva_accion_fila_cancelar', args=[self.reserva_a.pk])

        # POST directo a la acción de fila con confirmación
        response = self.client.post(url_cancelar, {'confirmar_cancelacion': 'si'})
        self.assertEqual(response.status_code, 302)
        self.reserva_a.refresh_from_db()
        self.assertEqual(self.reserva_a.estado, Reserva.Estado.CANCELADA)
        self.assertEqual(self.reserva_a.motivo_cancelacion, 'Mal clima')

    def test_usuario_sin_permiso_url_directa_403(self):
        """Un usuario sin permiso no puede entrar a la URL de la acción de fila de
        Eliminar/Cancelar directamente (403)."""
        # 1. Vendedora intentando entrar a la URL de Eliminar de Embarcacion (no tiene delete)
        self.client.force_login(self.vendedora_a)
        url_eliminar = reverse('admin:fleet_embarcacion_accion_fila_eliminar', args=[self.embarcacion_a.pk])
        response_eliminar = self.client.get(url_eliminar)
        self.assertEqual(response_eliminar.status_code, 403)

        # 2. Usuario sin permiso de change intentando entrar a la URL de Cancelar de Reserva
        self.client.force_login(self.usuario_solo_ver)
        url_cancelar = reverse('admin:bookings_reserva_accion_fila_cancelar', args=[self.reserva_a.pk])
        response_cancelar = self.client.get(url_cancelar)
        self.assertEqual(response_cancelar.status_code, 403)

    def test_redireccion_editar_y_ver(self):
        """Las acciones de fila Editar y Ver redirigen a la página de change del objeto."""
        self.client.force_login(self.jefe_a)

        # Editar en Embarcacion redirige a change
        url_editar = reverse('admin:fleet_embarcacion_accion_fila_editar', args=[self.embarcacion_a.pk])
        resp_editar = self.client.get(url_editar)
        self.assertEqual(resp_editar.status_code, 302)
        expected_change = reverse('admin:fleet_embarcacion_change', args=[self.embarcacion_a.pk])
        self.assertEqual(resp_editar.url, expected_change)

        # Ver en Embarcacion redirige a change
        url_ver = reverse('admin:fleet_embarcacion_accion_fila_ver', args=[self.embarcacion_a.pk])
        resp_ver = self.client.get(url_ver)
        self.assertEqual(resp_ver.status_code, 302)
        self.assertEqual(resp_ver.url, expected_change)

    def test_unfold_checks_actions_row_todos_los_model_admins(self):
        """Ningún ModelAdmin registrado (admin.site._registry) hace explotar
        manage.py check en actions_row ni _get_base_actions_row()."""
        for model, model_admin in admin.site._registry.items():
            if not hasattr(model_admin, '_get_base_actions_row'):
                continue  # admins de terceros (axes) que no son de Unfold
            with self.subTest(model=model.__name__):
                base_actions = model_admin._get_base_actions_row()
                self.assertIsInstance(base_actions, list)
                errors = model_admin.check()
                e129_errors = [e for e in errors if e.id == 'admin.E129']
                self.assertEqual(e129_errors, [])
