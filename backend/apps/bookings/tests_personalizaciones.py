import uuid
from datetime import time, timedelta
from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import RequestFactory, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.bookings.admin import ReservaAdmin
from apps.bookings.models import Reserva, ReservaPersonalizacion
from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.fleet.models import Paquete, Personalizacion, Servicio, ServicioPersonalizacion
from apps.fleet.serializers import ServicioSerializer
from apps.testing import EmpresaTestCase, OperadorTestCase, crear_servicio_pesca
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.tenancy.rls import alcance_operador_migracion


class PersonalizacionesModelTests(EmpresaTestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Paseo',
            slug='paseo',
            tipo_servicio='otro',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='tarifa_fija',
            precio_base=Decimal('1000.00'),
        )
        self.p = Personalizacion.objects.create(
            empresa=self.empresa,
            nombre='Pregunta',
            tipo_interaccion='input_numero',
        )
        self.sp = ServicioPersonalizacion.objects.create(
            servicio=self.servicio,
            personalizacion=self.p,
            precio=0,
            obligatorio=True,
        )
        self.reserva = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio,
            fecha=timezone.localdate() + timedelta(days=10),
            hora=time(6),
            numero_personas=3,
            nombre_cliente='Juan Perez',
            telefono_cliente='+5216121234567',
            correo_cliente='juan@example.com',
            moneda='MXN',
            deslinde_aceptado=True,
            canal_origen=Reserva.CanalOrigen.WEB,
        )

    def test_reserva_necesita_producto(self):
        self.reserva.servicio = None
        self.reserva.paquete = None
        with self.assertRaisesMessage(ValidationError, 'Selecciona un servicio o paquete'):
            self.reserva.full_clean()

    def test_reserva_no_acepta_servicio_y_paquete_a_la_vez(self):
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Exclusividad',
            slug='paquete-exclusividad',
            precio_ancla=Decimal('5000'),
        )
        self.reserva.paquete = paquete
        with self.assertRaisesMessage(ValidationError, 'No puedes seleccionar servicio y paquete a la vez'):
            self.reserva.full_clean()

    def test_numero_cero_es_valido_e_input_no_tiene_subtotal(self):
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            respuesta='0',
        )
        fila.full_clean()
        self.assertIsNone(fila.subtotal)

    def test_numero_no_finito_es_invalido(self):
        for respuesta in ('NaN', 'Infinity', '-Infinity', 'abc'):
            with self.subTest(respuesta=respuesta):
                fila = ReservaPersonalizacion(
                    reserva=self.reserva,
                    servicio_personalizacion=self.sp,
                    respuesta=respuesta,
                )
                with self.assertRaises(ValidationError):
                    fila.full_clean()

    def test_subtotal_check_congelado(self):
        self.p.tipo_interaccion = 'check'
        self.p.save(update_fields=['tipo_interaccion'])
        self.sp.obligatorio = False
        self.sp.save(update_fields=['obligatorio'])
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            cantidad=2,
            precio_unitario=Decimal('450'),
        )
        self.assertEqual(fila.subtotal, Decimal('900'))

    def test_check_no_acepta_respuesta(self):
        self.p.tipo_interaccion = 'check'
        self.p.save(update_fields=['tipo_interaccion'])
        self.sp.obligatorio = False
        self.sp.save(update_fields=['obligatorio'])
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            respuesta='texto inesperado',
        )
        with self.assertRaises(ValidationError):
            fila.full_clean()

    def test_input_obligatorio_requiere_respuesta(self):
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            respuesta='   ',
        )
        with self.assertRaises(ValidationError):
            fila.full_clean()

    def test_input_no_acepta_cantidad_ni_precio(self):
        for cambios in ({'cantidad': 2}, {'precio_unitario': Decimal('1')}):
            with self.subTest(cambios=cambios):
                fila = ReservaPersonalizacion(
                    reserva=self.reserva,
                    servicio_personalizacion=self.sp,
                    respuesta='3',
                    **cambios,
                )
                with self.assertRaises(ValidationError):
                    fila.full_clean()

    def test_seleccion_debe_pertenecer_a_opciones(self):
        self.p.tipo_interaccion = 'input_seleccion'
        self.p.opciones_seleccion = ['A', 'B']
        self.p.save(update_fields=['tipo_interaccion', 'opciones_seleccion'])
        fila = ReservaPersonalizacion(
            reserva=self.reserva,
            servicio_personalizacion=self.sp,
            respuesta='C',
        )
        with self.assertRaises(ValidationError):
            fila.full_clean()


class PersonalizacionesSerializerTests(OperadorTestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede serializer', slug='sede-serializer')
        self.empresa = Empresa.objects.create(
            sede=self.sede,
            nombre='Empresa serializer',
            slug='empresa-serializer',
        )
        self.otra_empresa = Empresa.objects.create(
            sede=self.sede,
            nombre='Otra empresa',
            slug='otra-empresa-serializer',
        )
        self.servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Paseo',
            slug='paseo',
            tipo_servicio='otro',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='tarifa_fija',
            precio_base=Decimal('1000.00'),
        )
        self.servicio_pesca = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Pesca',
            slug='pesca',
            tipo_servicio='pesca',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='tarifa_fija',
            precio_base=Decimal('1000.00'),
        )
        self.otro_servicio = Servicio.objects.create(
            empresa=self.otra_empresa,
            nombre='Paseo ajeno',
            slug='paseo-ajeno',
            tipo_servicio='otro',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='tarifa_fija',
            precio_base=Decimal('900.00'),
        )
        self.p_numero = Personalizacion.objects.create(
            empresa=self.empresa,
            nombre='Edad',
            tipo_interaccion='input_numero',
        )
        self.sp_numero = ServicioPersonalizacion.objects.create(
            servicio=self.servicio,
            personalizacion=self.p_numero,
            precio=0,
            obligatorio=True,
        )
        self.p_check = Personalizacion.objects.create(
            empresa=self.empresa,
            nombre='Foto',
            tipo_interaccion='check',
        )
        self.sp_check = ServicioPersonalizacion.objects.create(
            servicio=self.servicio,
            personalizacion=self.p_check,
            precio=Decimal('100.00'),
            preseleccionado=True,
        )
        self.p_seleccion = Personalizacion.objects.create(
            empresa=self.empresa,
            nombre='Menú',
            tipo_interaccion='input_seleccion',
            opciones_seleccion=['A', 'B'],
        )
        self.sp_seleccion = ServicioPersonalizacion.objects.create(
            servicio=self.servicio,
            personalizacion=self.p_seleccion,
            precio=0,
        )
        self.p_ajena = Personalizacion.objects.create(
            empresa=self.otra_empresa,
            nombre='Ajena',
        )
        self.sp_ajena = ServicioPersonalizacion.objects.create(
            servicio=self.otro_servicio,
            personalizacion=self.p_ajena,
            precio=Decimal('50.00'),
        )
        self.request = APIRequestFactory().post('/api/empresa-serializer/reservas/')

    def datos(self, **cambios):
        datos = {
            'checkout_id': str(uuid.uuid4()),
            'servicio': self.servicio.slug,
            'fecha': (timezone.localdate() + timedelta(days=10)).isoformat(),
            'hora': '06:00',
            'numero_personas': 3,
            'nombre_cliente': 'Juan Perez',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'juan@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Juan Perez',
            'personalizaciones': [],
            'extras': [],
        }
        datos.update(cambios)
        return datos

    def serializer(self, *, instance=None, data=None):
        return ReservaCheckoutSerializer(
            instance,
            data=data or self.datos(),
            context={'empresa': self.empresa, 'request': self.request},
        )

    def test_rechaza_input_obligatorio_ausente_y_acepta_cero(self):
        malo = self.serializer()
        self.assertFalse(malo.is_valid())
        self.assertIn('personalizaciones', malo.errors)

        bueno = self.serializer(data=self.datos(
            personalizaciones=[{'id': self.sp_numero.pk, 'respuesta': '0'}],
        ))
        self.assertTrue(bueno.is_valid(), bueno.errors)
        guardada = bueno.save()
        self.assertEqual(guardada.personalizaciones_seleccionadas.get().respuesta, '0')

    def test_rechaza_ids_repetidos_ajenos_e_inactivos(self):
        casos = (
            [
                {'id': self.sp_numero.pk, 'respuesta': '1'},
                {'id': self.sp_numero.pk, 'respuesta': '2'},
            ],
            [
                {'id': self.sp_numero.pk, 'respuesta': '1'},
                {'id': self.sp_ajena.pk},
            ],
        )
        for personalizaciones in casos:
            with self.subTest(personalizaciones=personalizaciones):
                serializer = self.serializer(data=self.datos(personalizaciones=personalizaciones))
                self.assertFalse(serializer.is_valid())
                self.assertIn('personalizaciones', serializer.errors)

        self.sp_seleccion.activo = False
        self.sp_seleccion.save(update_fields=['activo'])
        serializer = self.serializer(data=self.datos(personalizaciones=[
            {'id': self.sp_numero.pk, 'respuesta': '1'},
            {'id': self.sp_seleccion.pk, 'respuesta': 'A'},
        ]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('personalizaciones', serializer.errors)

    def test_rechaza_respuesta_de_check_cantidad_de_input_y_seleccion_invalida(self):
        casos = (
            [{'id': self.sp_numero.pk, 'respuesta': '1'}, {'id': self.sp_check.pk, 'respuesta': 'sí'}],
            [{'id': self.sp_numero.pk, 'respuesta': '1', 'cantidad': 2}],
            [{'id': self.sp_numero.pk, 'respuesta': '1'}, {'id': self.sp_seleccion.pk, 'respuesta': 'C'}],
        )
        for personalizaciones in casos:
            with self.subTest(personalizaciones=personalizaciones):
                serializer = self.serializer(data=self.datos(personalizaciones=personalizaciones))
                self.assertFalse(serializer.is_valid())
                self.assertIn('personalizaciones', serializer.errors)

    def test_recomendada_puede_quedar_desmarcada(self):
        serializer = self.serializer(data=self.datos(
            personalizaciones=[{'id': self.sp_numero.pk, 'respuesta': '4'}],
        ))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        reserva = serializer.save()
        self.assertFalse(
            reserva.personalizaciones_seleccionadas.filter(
                servicio_personalizacion=self.sp_check,
            ).exists()
        )

    def test_actualizacion_vacia_borra_selecciones(self):
        serializer = self.serializer(data=self.datos(personalizaciones=[
            {'id': self.sp_numero.pk, 'respuesta': '4'},
            {'id': self.sp_check.pk},
        ]))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        reserva = serializer.save()

        self.sp_numero.obligatorio = False
        self.sp_numero.save(update_fields=['obligatorio'])
        actualizacion = self.serializer(
            instance=reserva,
            data=self.datos(checkout_id=str(reserva.checkout_id), personalizaciones=[]),
        )
        self.assertTrue(actualizacion.is_valid(), actualizacion.errors)
        actualizacion.save()
        self.assertEqual(reserva.personalizaciones_seleccionadas.count(), 0)

    def test_actualizacion_invalida_no_cambia_reserva_ni_selecciones(self):
        serializer = self.serializer(data=self.datos(
            personalizaciones=[{'id': self.sp_numero.pk, 'respuesta': '4'}],
        ))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        reserva = serializer.save()
        nombre_original = reserva.nombre_cliente

        invalida = self.serializer(
            instance=reserva,
            data=self.datos(
                checkout_id=str(reserva.checkout_id),
                nombre_cliente='Nombre cambiado',
                personalizaciones=[{'id': self.sp_numero.pk, 'respuesta': 'NaN'}],
            ),
        )
        self.assertFalse(invalida.is_valid())
        reserva.refresh_from_db()
        self.assertEqual(reserva.nombre_cliente, nombre_original)
        self.assertEqual(reserva.personalizaciones_seleccionadas.get().respuesta, '4')

    def test_pesca_explicita_rechaza_contrato_nuevo(self):
        serializer = self.serializer(data=self.datos(
            servicio=self.servicio_pesca.slug,
            personalizaciones=[{'id': self.sp_numero.pk, 'respuesta': '4'}],
        ))
        self.assertFalse(serializer.is_valid())
        self.assertIn('personalizaciones', serializer.errors)

    def test_catalogo_expone_tipo_opciones_y_aviso(self):
        self.p_seleccion.aviso_reforzado = False
        datos = ServicioSerializer(self.servicio).data
        fila = next(p for p in datos['personalizaciones'] if p['id'] == self.sp_seleccion.pk)
        self.assertEqual(fila['tipo_interaccion'], 'input_seleccion')
        self.assertEqual(fila['opciones_seleccion'], ['A', 'B'])
        self.assertFalse(fila['aviso_reforzado'])


class PersonalizacionesAdminTests(EmpresaTestCase):
    def test_vendedora_ve_respuesta_sin_permisos_de_edicion(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Paseo admin', slug='paseo-admin',
            tipo_servicio='otro', estrategia_cupo='bajo_demanda',
            estrategia_precio='tarifa_fija', precio_base=Decimal('1000.00'),
        )
        personalizacion = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Hotel', tipo_interaccion='input_texto',
        )
        sp = ServicioPersonalizacion.objects.create(
            servicio=servicio, personalizacion=personalizacion,
        )
        reserva = Reserva.objects.create(
            empresa=self.empresa, servicio=servicio,
            fecha=timezone.localdate() + timedelta(days=10), hora=time(8),
            numero_personas=2, nombre_cliente='Ana Perez',
            telefono_cliente='6121234567', correo_cliente='ana@example.com',
            moneda='MXN', deslinde_aceptado=True,
        )
        ReservaPersonalizacion.objects.create(
            reserva=reserva, servicio_personalizacion=sp, respuesta='Hotel Central',
        )
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)

        respuesta = self.client.get(reverse('admin:bookings_reserva_change', args=[reserva.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Hotel Central')
        self.assertTrue(vendedora.has_perm('bookings.view_reservapersonalizacion'))
        self.assertFalse(vendedora.has_perm('bookings.change_reservapersonalizacion'))
        self.assertFalse(vendedora.has_perm('fleet.change_serviciopersonalizacion'))

class ReservaPersonalizacionMigration0045Tests(TransactionTestCase):
    migrate_from = [
        ('bookings', '0044_rls_orden_sin_current_query'),
        ('fleet', '0030_personalizacion_tipo_interaccion'),
    ]
    migrate_to = [('bookings', '0045_rename_reservapersonalizacion')]

    def _restaurar_esquema(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def setUp(self):
        super().setUp()
        self.addCleanup(self._restaurar_esquema)
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        old_apps = self.executor.loader.project_state(self.migrate_from).apps

        Sede = old_apps.get_model('tenancy', 'Sede')
        Empresa = old_apps.get_model('tenancy', 'Empresa')
        Servicio = old_apps.get_model('fleet', 'Servicio')
        Personalizacion = old_apps.get_model('fleet', 'Personalizacion')
        ServicioPersonalizacion = old_apps.get_model('fleet', 'ServicioPersonalizacion')
        Reserva = old_apps.get_model('bookings', 'Reserva')
        ReservaPaquetePersonalizacion = old_apps.get_model(
            'bookings', 'ReservaPaquetePersonalizacion',
        )

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                sede = Sede.objects.using(connection.alias).create(
                    nombre='Sede rename',
                    slug='sede-rename',
                )
                empresa = Empresa.objects.using(connection.alias).create(
                    sede=sede,
                    nombre='Empresa rename',
                    slug='empresa-rename',
                    activo=True,
                )
                servicio = Servicio.objects.using(connection.alias).create(
                    empresa=empresa,
                    nombre='Servicio rename',
                    slug='servicio-rename',
                )
                personalizacion = Personalizacion.objects.using(connection.alias).create(
                    empresa=empresa,
                    nombre='Personalización rename',
                )
                sp = ServicioPersonalizacion.objects.using(connection.alias).create(
                    servicio=servicio,
                    personalizacion=personalizacion,
                    precio=Decimal('125.00'),
                )
                reserva = Reserva.objects.using(connection.alias).create(
                    empresa=empresa,
                    servicio=servicio,
                    fecha=timezone.localdate() + timedelta(days=10),
                    hora=time(6),
                    numero_personas=2,
                    nombre_cliente='Cliente migración',
                    telefono_cliente='+5216121234567',
                    correo_cliente='migracion@example.com',
                    moneda='MXN',
                    deslinde_aceptado=True,
                )
                fila = ReservaPaquetePersonalizacion.objects.using(connection.alias).create(
                    reserva=reserva,
                    servicio_personalizacion=sp,
                    cantidad=2,
                )
                self.fila_pk = fila.pk
                self.reserva_pk = reserva.pk
                self.sp_pk = sp.pk

    def test_rename_preserva_fila_y_deja_snapshot_vacio(self):
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        new_apps = self.executor.loader.project_state(self.migrate_to).apps
        ReservaPersonalizacion = new_apps.get_model(
            'bookings', 'ReservaPersonalizacion',
        )

        with transaction.atomic(using=connection.alias):
            with alcance_operador_migracion(connection):
                fila = ReservaPersonalizacion.objects.using(connection.alias).get(
                    pk=self.fila_pk,
                )
                self.assertEqual(fila.reserva_id, self.reserva_pk)
                self.assertEqual(fila.servicio_personalizacion_id, self.sp_pk)
                self.assertEqual(fila.cantidad, 2)
                self.assertEqual(fila.respuesta, '')
                self.assertIsNone(fila.precio_unitario)


class ReservaAdminInitialDataTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.site = AdminSite()
        self.admin = ReservaAdmin(Reserva, self.site)
        self.rf = RequestFactory()
        self.servicio_pesca = crear_servicio_pesca(self.empresa)
        self.jefe = self.crear_jefe()
        self.vendedora = self.crear_vendedora()

    def test_get_add_inicializa_pesca_para_jefe_y_vendedora(self):
        for user in (self.jefe, self.vendedora):
            with self.subTest(user=user.username):
                request = self.rf.get('/admin/bookings/reserva/add/')
                request.user = user
                initial = self.admin.get_changeform_initial_data(request)
                self.assertEqual(initial.get('servicio'), self.servicio_pesca.pk)

    def test_formulario_real_admin_bajo_vendedora_y_jefe(self):
        for user in (self.jefe, self.vendedora):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse('admin:bookings_reserva_add'))
                self.assertEqual(response.status_code, 200)
                form = response.context_data['adminform'].form
                self.assertEqual(form.initial.get('servicio'), self.servicio_pesca.pk)

    def test_empresa_b_con_mismo_slug_nunca_se_usa(self):
        self._alcance.__exit__(None, None, None)
        try:
            with scope.como_operador_plataforma():
                empresa_b = Empresa.objects.create(
                    sede=self.sede,
                    nombre='Empresa B',
                    slug='empresa-b',
                    activo=True,
                )
                servicio_b = Servicio.objects.create(
                    empresa=empresa_b,
                    nombre='Pesca B',
                    slug='pesca-deportiva',
                    tipo_servicio='pesca',
                    activo=True,
                    precio_base=Decimal('6000'),
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        request = self.rf.get('/admin/bookings/reserva/add/')
        request.user = self.jefe
        initial = self.admin.get_changeform_initial_data(request)
        self.assertEqual(initial.get('servicio'), self.servicio_pesca.pk)
        self.assertNotEqual(initial.get('servicio'), servicio_b.pk)

    def test_formulario_de_edicion_no_reemplaza_servicio(self):
        otro_servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Paseo Especial',
            slug='paseo-especial',
            tipo_servicio='otro',
            precio_base=Decimal('2000'),
        )
        reserva = Reserva.objects.create(
            empresa=self.empresa,
            servicio=otro_servicio,
            fecha=timezone.localdate() + timedelta(days=5),
            hora=time(8),
            numero_personas=2,
            nombre_cliente='Cliente Edicion',
            deslinde_aceptado=True,
            canal_origen=Reserva.CanalOrigen.WEB,
        )
        request = self.rf.get(f'/admin/bookings/reserva/{reserva.pk}/change/')
        request.user = self.jefe
        response = self.admin.changeform_view(request, object_id=str(reserva.pk))
        form = response.context_data['adminform'].form
        self.assertEqual(form.instance.servicio_id, otro_servicio.pk)

    def test_paquete_explicito_en_initial_no_se_combina_con_pesca(self):
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Combinado',
            slug='paquete-comb',
            precio_ancla=Decimal('7000'),
        )
        request = self.rf.get(f'/admin/bookings/reserva/add/?paquete={paquete.pk}')
        request.user = self.jefe
        initial = self.admin.get_changeform_initial_data(request)
        self.assertEqual(str(initial.get('paquete')), str(paquete.pk))
        self.assertNotIn('servicio', initial)

    def test_operador_sin_empresa_no_recibe_default(self):
        operador = User.objects.create_user('operador_admin', is_staff=True, password='x')
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        self._alcance.__exit__(None, None, None)
        try:
            with scope.como_operador_plataforma():
                request = self.rf.get('/admin/bookings/reserva/add/')
                request.user = operador
                initial = self.admin.get_changeform_initial_data(request)
                self.assertNotIn('servicio', initial)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

