"""Pruebas de catálogos de vehículos, bloqueos, menú lateral y permisos (Tarea 03).

Cubre:
1. Permisos por rol: Vendedora ve vehículos pero no los edita; Jefe sí los edita;
   bloqueos (VehiculoNoDisponible) los gestionan ambos; viajes (ViajeTransporte)
   tienen view/change.
2. Carga del admin de cada modelo con cada rol (Vendedora, Jefe, OperadorPlataforma).
3. Menú lateral (UNFOLD['SIDEBAR']) muestra u oculta ítems según los permisos del usuario.
4. El campo `registrado_por` se sella automáticamente con el usuario autenticado
   al crear un bloqueo y permanece de solo lectura.
5. Aislamiento entre empresas: una vendedora no ve ni puede editar vehículos ni bloqueos
   de otra empresa, y el autocompletado filtra por empresa actual.
6. Validación inversa: bloquear un vehículo con un viaje asignado ese día es rechazado
   por el formulario del admin con el mensaje explicativo correspondiente.
"""
from contextlib import contextmanager
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse

from apps.bookings.models import DetalleTransporte, Reserva, ViajeTransporte
from apps.fleet.enums import EstrategiaCupo, EstrategiaPrecio, TipoServicio, TipoTraslado, Zona
from apps.fleet.models import PuntoEncuentro, Servicio, Vehiculo, VehiculoNoDisponible
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa
from apps.testing import EmpresaTestCase

User = get_user_model()


def _crear_servicio_transporte(empresa):
    return Servicio.objects.create(
        empresa=empresa,
        nombre='Traslado DLS',
        slug='traslado-dls',
        tipo_servicio=TipoServicio.TRANSPORTE,
        estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
        estrategia_precio=EstrategiaPrecio.POR_RUTA,
        pide_hora=False,
        activo=True,
    )


def _crear_reserva_transporte(empresa, servicio, fecha=None, hora=None, numero_personas=2):
    pe, _ = PuntoEncuentro.objects.get_or_create(
        empresa=empresa,
        nombre='Hotel Malecon',
        defaults={'zona': Zona.CENTRO, 'activo': True},
    )
    reserva = Reserva.objects.create(
        empresa=empresa,
        servicio=servicio,
        nombre_cliente='Ana Garcia',
        telefono_cliente='+5216121112233',
        correo_cliente='ana@example.com',
        canal_origen=Reserva.CanalOrigen.WHATSAPP,
        deslinde_aceptado=True,
        deslinde_nombre='Ana Garcia',
        fecha=fecha or (date.today() + timedelta(days=5)),
        hora=hora or time(10, 0),
        numero_personas=numero_personas,
        estado=Reserva.Estado.PAGADA,
    )
    DetalleTransporte.objects.create(
        reserva=reserva,
        tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
        punto_encuentro=pe,
        zona=Zona.CENTRO,
    )
    return reserva


@contextmanager
def _fuera_del_alcance(caso):
    """Las peticiones de un operador o de otra empresa abren su propio alcance en el middleware:
    no pueden correr dentro del de UNA empresa que mantiene abierto EmpresaTestCase."""
    caso._alcance.__exit__(None, None, None)
    try:
        yield
    finally:
        caso._alcance = scope.con_empresa(caso.empresa)
        caso._alcance.__enter__()


class PermisosCatalogosTrasladosTests(EmpresaTestCase):
    """Verifica permisos de auth y permisos HTTP en el admin para Vendedora y Jefe."""

    def setUp(self):
        super().setUp()
        self.vendedora = self.crear_vendedora('vendedora_ana')
        self.jefe = self.crear_jefe('jefa_elena')

    def test_permisos_vendedora_y_jefe_sobre_modelos(self):
        """Vendedora solo ve vehiculos; jefe tiene CRUD. Ambos gestionan bloqueos."""
        # Vendedora: vehiculo solo view
        self.assertTrue(self.vendedora.has_perm('fleet.view_vehiculo'))
        self.assertFalse(self.vendedora.has_perm('fleet.add_vehiculo'))
        self.assertFalse(self.vendedora.has_perm('fleet.change_vehiculo'))
        self.assertFalse(self.vendedora.has_perm('fleet.delete_vehiculo'))

        # Vendedora: vehiculonodisponible completo
        self.assertTrue(self.vendedora.has_perm('fleet.view_vehiculonodisponible'))
        self.assertTrue(self.vendedora.has_perm('fleet.add_vehiculonodisponible'))
        self.assertTrue(self.vendedora.has_perm('fleet.change_vehiculonodisponible'))
        self.assertTrue(self.vendedora.has_perm('fleet.delete_vehiculonodisponible'))

        # Vendedora: viajetransporte view y change
        self.assertTrue(self.vendedora.has_perm('bookings.view_viajetransporte'))
        self.assertTrue(self.vendedora.has_perm('bookings.change_viajetransporte'))

        # Jefe: vehiculo completo
        self.assertTrue(self.jefe.has_perm('fleet.view_vehiculo'))
        self.assertTrue(self.jefe.has_perm('fleet.add_vehiculo'))
        self.assertTrue(self.jefe.has_perm('fleet.change_vehiculo'))
        self.assertTrue(self.jefe.has_perm('fleet.delete_vehiculo'))

        # Jefe: vehiculonodisponible completo
        self.assertTrue(self.jefe.has_perm('fleet.view_vehiculonodisponible'))
        self.assertTrue(self.jefe.has_perm('fleet.add_vehiculonodisponible'))
        self.assertTrue(self.jefe.has_perm('fleet.change_vehiculonodisponible'))
        self.assertTrue(self.jefe.has_perm('fleet.delete_vehiculonodisponible'))

        # Jefe: viajetransporte view y change
        self.assertTrue(self.jefe.has_perm('bookings.view_viajetransporte'))
        self.assertTrue(self.jefe.has_perm('bookings.change_viajetransporte'))

    def test_vendedora_ve_vehiculo_pero_no_lo_edita_en_admin(self):
        """Vendedora puede consultar vehiculos pero no crearlos, editarlos ni borrarlos."""
        vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Blanca', lugares=6, activo=True,
        )
        self.client.force_login(self.vendedora)

        # Puede ver el listado
        resp_lista = self.client.get(reverse('admin:fleet_vehiculo_changelist'))
        self.assertEqual(resp_lista.status_code, 200)
        self.assertContains(resp_lista, 'Van Blanca')

        # Puede ver la ficha pero sin permiso de cambio
        resp_detalle = self.client.get(reverse('admin:fleet_vehiculo_change', args=[vehiculo.pk]))
        self.assertEqual(resp_detalle.status_code, 200)
        self.assertFalse(resp_detalle.context['has_change_permission'])

        # No puede acceder a la vista de alta ni enviar altas
        resp_add = self.client.get(reverse('admin:fleet_vehiculo_add'))
        self.assertEqual(resp_add.status_code, 403)

        # No puede enviar cambios
        resp_post_change = self.client.post(
            reverse('admin:fleet_vehiculo_change', args=[vehiculo.pk]),
            {'nombre': 'Van Modificada', 'lugares': 8, 'activo': True},
        )
        self.assertEqual(resp_post_change.status_code, 403)

        # No puede borrar
        resp_delete = self.client.post(
            reverse('admin:fleet_vehiculo_delete', args=[vehiculo.pk]),
            {'post': 'yes'},
        )
        self.assertEqual(resp_delete.status_code, 403)

    def test_jefe_puede_crear_y_editar_vehiculo_en_admin(self):
        """Jefe puede dar de alta y modificar vehiculos desde el admin."""
        self.client.force_login(self.jefe)

        # Acceso al formulario de alta
        resp_get_add = self.client.get(reverse('admin:fleet_vehiculo_add'))
        self.assertEqual(resp_get_add.status_code, 200)

        # Alta de vehiculo
        resp_post_add = self.client.post(
            reverse('admin:fleet_vehiculo_add'),
            {'nombre': 'Suburban Negra', 'lugares': 7, 'activo': True},
        )
        self.assertEqual(resp_post_add.status_code, 302)
        vehiculo = Vehiculo.objects.get(nombre='Suburban Negra', empresa=self.empresa)
        self.assertEqual(vehiculo.lugares, 7)

        # Modificacion de vehiculo
        resp_post_change = self.client.post(
            reverse('admin:fleet_vehiculo_change', args=[vehiculo.pk]),
            {'nombre': 'Suburban Modificada', 'lugares': 8, 'activo': True},
        )
        self.assertEqual(resp_post_change.status_code, 302)
        vehiculo.refresh_from_db()
        self.assertEqual(vehiculo.nombre, 'Suburban Modificada')
        self.assertEqual(vehiculo.lugares, 8)

    def test_ambos_roles_gestionan_bloqueos_en_admin(self):
        """Tanto Vendedora como Jefe pueden crear, consultar y borrar bloqueos."""
        vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Ejecutiva', lugares=6, activo=True,
        )

        for rol_nombre, usuario, offset_dias in (
            ('Vendedora', self.vendedora, 2),
            ('Jefe', self.jefe, 3),
        ):
            with self.subTest(rol=rol_nombre):
                self.client.force_login(usuario)
                fecha_bloqueo = date.today() + timedelta(days=offset_dias)

                # Formulario de alta
                resp_get = self.client.get(reverse('admin:fleet_vehiculonodisponible_add'))
                self.assertEqual(resp_get.status_code, 200)

                # Crear bloqueo
                resp_post = self.client.post(
                    reverse('admin:fleet_vehiculonodisponible_add'),
                    {
                        'vehiculo': vehiculo.pk,
                        'fecha': fecha_bloqueo.isoformat(),
                        'motivo': f'Bloqueo por {rol_nombre}',
                    },
                )
                self.assertEqual(resp_post.status_code, 302)
                bloqueo = VehiculoNoDisponible.objects.get(
                    vehiculo=vehiculo, fecha=fecha_bloqueo, empresa=self.empresa,
                )
                self.assertEqual(bloqueo.registrado_por, usuario)

                # Consulta de edicion
                resp_change = self.client.get(
                    reverse('admin:fleet_vehiculonodisponible_change', args=[bloqueo.pk])
                )
                self.assertEqual(resp_change.status_code, 200)
                self.assertTrue(resp_change.context['has_change_permission'])

                # Borrado
                resp_del = self.client.post(
                    reverse('admin:fleet_vehiculonodisponible_delete', args=[bloqueo.pk]),
                    {'post': 'yes'},
                )
                self.assertEqual(resp_del.status_code, 302)
                self.assertFalse(
                    VehiculoNoDisponible.objects.filter(pk=bloqueo.pk).exists()
                )


class AdminCargaRolesTests(EmpresaTestCase):
    """El changelist y el admin index cargan sin error para cada rol."""

    def setUp(self):
        super().setUp()
        self.vendedora = self.crear_vendedora('vendedora_carga')
        self.jefe = self.crear_jefe('jefa_carga')

        self.operador = User.objects.create_user('operador_carga', password='x', is_staff=True)
        self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))

        self.vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Carga', lugares=10, activo=True,
        )
        self.bloqueo = VehiculoNoDisponible.objects.create(
            empresa=self.empresa,
            vehiculo=self.vehiculo,
            fecha=date.today() + timedelta(days=4),
            motivo='Revision rutinaria',
        )

    def test_admin_de_cada_modelo_carga_con_cada_rol(self):
        """Verifica que el admin index y changelists de vehiculos y bloqueos respondan 200."""
        usuarios = [
            ('Vendedora', self.vendedora),
            ('Jefe', self.jefe),
            ('OperadorPlataforma', self.operador),
        ]
        urls = [
            reverse('admin:index'),
            reverse('admin:fleet_vehiculo_changelist'),
            reverse('admin:fleet_vehiculonodisponible_changelist'),
        ]

        for rol_nombre, usuario in usuarios:
            self.client.force_login(usuario)
            for url in urls:
                with self.subTest(rol=rol_nombre, url=url):
                    with _fuera_del_alcance(self):
                        resp = self.client.get(url)
                    self.assertEqual(resp.status_code, 200)
                    self.assertNotContains(resp, 'Traceback')


class MenuSidebarTests(EmpresaTestCase):
    """El menú lateral (UNFOLD['SIDEBAR']) refleja la presencia de los ítems según permisos."""

    def setUp(self):
        super().setUp()
        self.vendedora = self.crear_vendedora('vendedora_menu')
        self.jefe = self.crear_jefe('jefa_menu')

        # Usuario staff con membresía pero sin grupos ni permisos
        self.usuario_sin_permisos = User.objects.create_user(
            'staff_sin_permisos', password='x', is_staff=True,
        )
        MembresiaEmpresa.objects.create(
            user=self.usuario_sin_permisos,
            empresa=self.empresa,
            rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        # La señal de la membresía le da el grupo Vendedora; esta cuenta no debe tener permisos.
        self.usuario_sin_permisos.groups.clear()

    def test_menu_muestra_items_segun_permiso(self):
        """Vendedora y Jefe ven los enlaces en la barra lateral; usuario sin permiso no los ve."""
        url_vehiculos = reverse('admin:fleet_vehiculo_changelist')
        url_bloqueos = reverse('admin:fleet_vehiculonodisponible_changelist')

        # Vendedora ve ambos (tiene view_vehiculo y view_vehiculonodisponible)
        self.client.force_login(self.vendedora)
        resp_vendedora = self.client.get(reverse('admin:index'))
        self.assertEqual(resp_vendedora.status_code, 200)
        self.assertContains(resp_vendedora, url_vehiculos)
        self.assertContains(resp_vendedora, url_bloqueos)

        # Jefe ve ambos
        self.client.force_login(self.jefe)
        resp_jefe = self.client.get(reverse('admin:index'))
        self.assertEqual(resp_jefe.status_code, 200)
        self.assertContains(resp_jefe, url_vehiculos)
        self.assertContains(resp_jefe, url_bloqueos)

        # Usuario sin permisos no ve ninguno de los dos
        self.client.force_login(self.usuario_sin_permisos)
        resp_sin_perm = self.client.get(reverse('admin:index'))
        self.assertEqual(resp_sin_perm.status_code, 200)
        self.assertNotContains(resp_sin_perm, url_vehiculos)
        self.assertNotContains(resp_sin_perm, url_bloqueos)


class SelloRegistradoPorTests(EmpresaTestCase):
    """`registrado_por` se sella automáticamente al crear y es de solo lectura."""

    def setUp(self):
        super().setUp()
        self.vendedora = self.crear_vendedora('vendedora_sello')
        self.vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Sprinter Blanca', lugares=12, activo=True,
        )

    def test_registrado_por_se_sella_al_crear_bloqueo(self):
        """Al crear un bloqueo por el admin, `registrado_por` toma el request.user."""
        self.client.force_login(self.vendedora)
        fecha_bloqueo = date.today() + timedelta(days=6)

        resp = self.client.post(
            reverse('admin:fleet_vehiculonodisponible_add'),
            {
                'vehiculo': self.vehiculo.pk,
                'fecha': fecha_bloqueo.isoformat(),
                'motivo': 'Mantenimiento en agencia',
            },
        )
        self.assertEqual(resp.status_code, 302)

        bloqueo = VehiculoNoDisponible.objects.get(
            vehiculo=self.vehiculo, fecha=fecha_bloqueo, empresa=self.empresa,
        )
        self.assertEqual(bloqueo.registrado_por, self.vendedora)
        self.assertEqual(bloqueo.empresa, self.empresa)

        # En la pantalla de edicion `registrado_por` y `creado_en` son readonly
        resp_change = self.client.get(
            reverse('admin:fleet_vehiculonodisponible_change', args=[bloqueo.pk])
        )
        self.assertEqual(resp_change.status_code, 200)
        readonly = resp_change.context['adminform'].model_admin.readonly_fields
        self.assertIn('registrado_por', readonly)
        self.assertIn('creado_en', readonly)


class AislamientoEmpresasCatalogosTests(EmpresaTestCase):
    """Aislamiento entre empresas para Vehiculo y VehiculoNoDisponible."""

    def setUp(self):
        super().setUp()
        self.vendedora_alfa = self.crear_vendedora('vendedora_alfa')
        self.vehiculo_alfa = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Alfa Uno', lugares=6, activo=True,
        )
        self.bloqueo_alfa = VehiculoNoDisponible.objects.create(
            empresa=self.empresa,
            vehiculo=self.vehiculo_alfa,
            fecha=date.today() + timedelta(days=3),
            motivo='Servicio exclusivo Alfa',
        )

        # Segunda empresa con su propia vendedora y datos
        self.otra_empresa = Empresa.objects.create(
            sede=self.sede,
            nombre='Empresa Beta',
            slug='empresa-beta-traslados',
            activo=True,
            exclusiva=False,
        )
        self.user_beta = User.objects.create_user(
            'vendedora_beta', password='x', is_staff=True,
        )
        self.user_beta.groups.add(Group.objects.get(name='Vendedora'))
        MembresiaEmpresa.objects.create(
            user=self.user_beta, empresa=self.otra_empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )

        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(self.otra_empresa):
                self.vehiculo_beta = Vehiculo.objects.create(
                    empresa=self.otra_empresa,
                    nombre='Van Beta Dos',
                    lugares=8,
                    activo=True,
                )
                self.bloqueo_beta = VehiculoNoDisponible.objects.create(
                    empresa=self.otra_empresa,
                    vehiculo=self.vehiculo_beta,
                    fecha=date.today() + timedelta(days=4),
                    motivo='Servicio exclusivo Beta',
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

    def test_vendedora_no_ve_vehiculos_ni_bloqueos_de_otra_empresa(self):
        """El listado y el detalle de vehiculos y bloqueos filtran por empresa actual."""
        # Vendedora Alfa solo ve datos de Empresa Alfa
        self.client.force_login(self.vendedora_alfa)

        resp_v_alfa = self.client.get(reverse('admin:fleet_vehiculo_changelist'))
        self.assertEqual(resp_v_alfa.status_code, 200)
        self.assertContains(resp_v_alfa, self.vehiculo_alfa.nombre)
        self.assertNotContains(resp_v_alfa, self.vehiculo_beta.nombre)

        # Acceder directamente al vehiculo ajeno falla (302 o 404 por get_queryset)
        resp_v_ajeno = self.client.get(
            reverse('admin:fleet_vehiculo_change', args=[self.vehiculo_beta.pk])
        )
        self.assertIn(resp_v_ajeno.status_code, (302, 404))

        # Bloqueos Alfa
        resp_b_alfa = self.client.get(reverse('admin:fleet_vehiculonodisponible_changelist'))
        self.assertEqual(resp_b_alfa.status_code, 200)
        self.assertContains(resp_b_alfa, 'Servicio exclusivo Alfa')
        self.assertNotContains(resp_b_alfa, 'Servicio exclusivo Beta')

        resp_b_ajeno = self.client.get(
            reverse('admin:fleet_vehiculonodisponible_change', args=[self.bloqueo_beta.pk])
        )
        self.assertIn(resp_b_ajeno.status_code, (302, 404))

        # Vendedora Beta solo ve datos de Empresa Beta
        with _fuera_del_alcance(self):
            self.client.force_login(self.user_beta)

            resp_v_beta = self.client.get(reverse('admin:fleet_vehiculo_changelist'))
            self.assertEqual(resp_v_beta.status_code, 200)
            self.assertContains(resp_v_beta, self.vehiculo_beta.nombre)
            self.assertNotContains(resp_v_beta, self.vehiculo_alfa.nombre)

            resp_b_beta = self.client.get(reverse('admin:fleet_vehiculonodisponible_changelist'))
            self.assertEqual(resp_b_beta.status_code, 200)
            self.assertContains(resp_b_beta, 'Servicio exclusivo Beta')
            self.assertNotContains(resp_b_beta, 'Servicio exclusivo Alfa')

        def test_autocompletado_de_vehiculos_solo_muestra_vehiculos_propios(self):
            """El endpoint autocomplete del admin acota el selector a la empresa del usuario."""
            self.client.force_login(self.vendedora_alfa)
            url_auto = reverse('admin:autocomplete')

            resp = self.client.get(url_auto, {
                'app_label': 'fleet',
                'model_name': 'vehiculonodisponible',
                'field_name': 'vehiculo',
                'term': '',
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            textos = [r['text'] for r in data.get('results', [])]

            self.assertTrue(any(self.vehiculo_alfa.nombre in t for t in textos))
            self.assertFalse(any(self.vehiculo_beta.nombre in t for t in textos))


class BloqueoConViajeAsignadoRechazoTests(EmpresaTestCase):
    """Validación inversa: el formulario de VehiculoNoDisponible rechaza bloquear un vehículo con viaje."""

    def setUp(self):
        super().setUp()
        self.vendedora = self.crear_vendedora('vendedora_bloqueo')
        self.servicio_transporte = _crear_servicio_transporte(self.empresa)
        self.vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Traslados DLS', lugares=5, activo=True,
        )
        self.fecha_viaje = date.today() + timedelta(days=5)
        self.reserva = _crear_reserva_transporte(
            self.empresa, self.servicio_transporte, fecha=self.fecha_viaje,
        )

        # Aseguramos el viaje activo asignado a este vehiculo
        viaje = ViajeTransporte.objects.filter(reserva=self.reserva).first()
        if viaje is None:
            viaje = ViajeTransporte.objects.create(
                empresa=self.empresa,
                reserva=self.reserva,
                sentido=ViajeTransporte.Sentido.UNICO,
                fecha=self.fecha_viaje,
                hora=time(10, 0),
                vehiculo=self.vehiculo,
                cancelado=False,
            )
        else:
            viaje.fecha = self.fecha_viaje
            viaje.hora = time(10, 0)
            viaje.vehiculo = self.vehiculo
            viaje.cancelado = False
            viaje.save()
        self.viaje = viaje

    def test_bloquear_vehiculo_con_viaje_asignado_lo_rechaza_formulario_con_mensaje(self):
        """Intento de bloqueo para una fecha con viaje asignado no cancelado se rechaza con error."""
        self.client.force_login(self.vendedora)

        resp = self.client.post(
            reverse('admin:fleet_vehiculonodisponible_add'),
            {
                'vehiculo': self.vehiculo.pk,
                'fecha': self.fecha_viaje.isoformat(),
                'motivo': 'Bloqueo conflictivo con viaje',
            },
        )
        # El formulario falla: status 200 (re-renderiza con errores, no 302)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            VehiculoNoDisponible.objects.filter(motivo='Bloqueo conflictivo con viaje').exists()
        )
        self.assertContains(resp, f'El vehiculo ya tiene asignado el viaje #{self.viaje.pk}')
        self.assertContains(resp, 'Cancela o reasigna ese viaje antes de bloquearlo.')

    def test_bloquear_vehiculo_con_viaje_cancelado_es_aceptado(self):
        """Un viaje cancelado no impide bloquear el vehículo."""
        self.viaje.cancelado = True
        self.viaje.save(update_fields=['cancelado'])

        self.client.force_login(self.vendedora)
        resp = self.client.post(
            reverse('admin:fleet_vehiculonodisponible_add'),
            {
                'vehiculo': self.vehiculo.pk,
                'fecha': self.fecha_viaje.isoformat(),
                'motivo': 'Bloqueo con viaje cancelado',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            VehiculoNoDisponible.objects.filter(motivo='Bloqueo con viaje cancelado').exists()
        )

    def test_bloquear_vehiculo_en_otra_fecha_es_aceptado(self):
        """Bloquear en una fecha distinta a la del viaje funciona sin problemas."""
        fecha_otra = self.fecha_viaje + timedelta(days=2)

        self.client.force_login(self.vendedora)
        resp = self.client.post(
            reverse('admin:fleet_vehiculonodisponible_add'),
            {
                'vehiculo': self.vehiculo.pk,
                'fecha': fecha_otra.isoformat(),
                'motivo': 'Bloqueo en fecha sin viaje',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            VehiculoNoDisponible.objects.filter(motivo='Bloqueo en fecha sin viaje').exists()
        )
