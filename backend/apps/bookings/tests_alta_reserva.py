"""Pruebas del flujo de alta manual de Reserva en el backoffice."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.fleet.models import Paquete, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .models import CupoDiario, Reserva, Vendedora
from .tests import crear_reserva


class AltaReservaTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.servicio = crear_servicio_pesca(self.empresa)
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_reserva_add')

        # Vendedora con perfil activo
        self.usuario_vendedora = self.crear_vendedora('vendedora-alta')
        self.perfil_vendedora = Vendedora.objects.create(
            usuario=self.usuario_vendedora,
            empresa=self.empresa,
            codigo='vendedora-alta',
            activo=True,
        )

        # Jefe sin perfil
        self.jefe_sin_perfil = self.crear_jefe('jefe-sin-perfil')

        # Jefe con perfil
        self.jefe_con_perfil = self.crear_jefe('jefe-con-perfil')
        self.perfil_jefe = Vendedora.objects.create(
            usuario=self.jefe_con_perfil,
            empresa=self.empresa,
            codigo='jefe-alta',
            activo=True,
        )

    def _datos(self, **extra):
        datos = {
            'nombre_cliente': 'Cliente Alta',
            'telefono_cliente': '612 123 4567',
            'correo_cliente': 'cliente@example.com',
            'fecha': (timezone.localdate() + timedelta(days=5)).isoformat(),
            'hora': '06:00',
            'numero_personas': '2',
            'servicio': str(self.servicio.pk),
            'moneda': Reserva.Moneda.MXN,
            'precio_total': '4500.00',
            # El alta incluye el formset del detalle de traslado: un navegador manda siempre
            # sus campos de gestion (una fila vacia, que se ignora si no es un traslado).
            'detalle_transporte-TOTAL_FORMS': '1',
            'detalle_transporte-INITIAL_FORMS': '0',
            **extra,
        }
        return datos

    def test_get_alta_fieldsets_reducidos_y_opciones_por_rol(self):
        # 1. Vendedora
        self.client.force_login(self.usuario_vendedora)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)

        form = respuesta.context['adminform'].form
        fieldsets = respuesta.context['adminform'].fieldsets

        # Fieldsets reducidos y en orden
        nombres_fs = [nombre for nombre, _ in fieldsets]
        self.assertEqual(nombres_fs, ['Cliente', 'Viaje', 'Cobro', 'Asignación'])
        self.assertIn('collapse', fieldsets[3][1].get('classes', ()))

        # Sin estado ni canal_origen en el formulario
        self.assertNotIn('estado', form.fields)
        self.assertNotIn('canal_origen', form.fields)
        self.assertNotIn('vendedora', form.fields)

        # 'ya_pago' con tres opciones y consecuencias en etiquetas
        self.assertIn('ya_pago', form.fields)
        opciones = dict(form.fields['ya_pago'].choices)
        self.assertIn('no', opciones)
        self.assertIn('todo_transferencia', opciones)
        self.assertIn('anticipo_transferencia', opciones)
        self.assertIn('no aparta lugar en el cupo', opciones['no'])
        self.assertIn('aparta el lugar ahora y revisa el cupo', opciones['todo_transferencia'])
        self.assertIn('saldo se cobra el día del viaje', opciones['anticipo_transferencia'])

        # Sin opción preseleccionada
        self.assertIsNone(form['ya_pago'].value())

        # 2. Jefe sin perfil: vendedora es visible y opcional
        self.client.force_login(self.jefe_sin_perfil)
        resp_jefe = self.client.get(self.url)
        form_jefe = resp_jefe.context['adminform'].form
        self.assertIn('vendedora', form_jefe.fields)
        self.assertFalse(form_jefe.fields['vendedora'].required)
        self.assertIsNone(form_jefe['vendedora'].value())

        # 3. Jefe con perfil: vendedora es visible con su perfil preseleccionado
        self.client.force_login(self.jefe_con_perfil)
        resp_jefe_con = self.client.get(self.url)
        form_jefe_con = resp_jefe_con.context['adminform'].form
        self.assertIn('vendedora', form_jefe_con.fields)
        self.assertEqual(form_jefe_con.fields['vendedora'].initial, self.perfil_jefe)

    def test_post_exitoso_opcion_no(self):
        self.client.force_login(self.usuario_vendedora)
        datos = self._datos(ya_pago='no')
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Cliente Alta')
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertEqual(reserva.forma_pago, '')
        self.assertIsNone(reserva.monto_transferencia)
        self.assertIsNone(reserva.transferencia_registrada_en)
        self.assertIsNone(reserva.transferencia_registrada_por)
        self.assertEqual(reserva.canal_origen, Reserva.CanalOrigen.WHATSAPP)
        self.assertEqual(reserva.vendedora, self.perfil_vendedora)
        self.assertEqual(reserva.empresa, self.empresa)

        # No ocupa cupo
        from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO
        self.assertNotIn(reserva.estado, ESTADOS_QUE_OCUPAN_CUPO)

    def test_post_exitoso_opcion_todo_transferencia(self):
        self.client.force_login(self.usuario_vendedora)
        datos = self._datos(ya_pago='todo_transferencia', precio_total='4500.00')
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Cliente Alta')
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(reserva.forma_pago, Reserva.FormaPago.COMPLETO)
        self.assertEqual(reserva.monto_transferencia, Decimal('4500.00'))
        self.assertIsNotNone(reserva.transferencia_registrada_en)
        self.assertEqual(reserva.transferencia_registrada_por, self.usuario_vendedora)
        self.assertEqual(reserva.canal_origen, Reserva.CanalOrigen.WHATSAPP)
        self.assertEqual(reserva.vendedora, self.perfil_vendedora)
        self.assertEqual(reserva.empresa, self.empresa)

        # Ocupa cupo
        from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO
        self.assertIn(reserva.estado, ESTADOS_QUE_OCUPAN_CUPO)

    def test_post_exitoso_opcion_anticipo_transferencia(self):
        self.client.force_login(self.usuario_vendedora)
        datos = self._datos(
            ya_pago='anticipo_transferencia',
            precio_total='4500.00',
            monto_recibido='1500.00',
        )
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Cliente Alta')
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)
        self.assertEqual(reserva.forma_pago, Reserva.FormaPago.ANTICIPO)
        self.assertEqual(reserva.monto_transferencia, Decimal('1500.00'))
        self.assertIsNotNone(reserva.transferencia_registrada_en)
        self.assertEqual(reserva.transferencia_registrada_por, self.usuario_vendedora)
        self.assertEqual(reserva.canal_origen, Reserva.CanalOrigen.WHATSAPP)
        self.assertEqual(reserva.vendedora, self.perfil_vendedora)
        self.assertEqual(reserva.empresa, self.empresa)

        # Ocupa cupo
        from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO
        self.assertIn(reserva.estado, ESTADOS_QUE_OCUPAN_CUPO)

    def test_anticipo_con_monto_recibido_invalido_falla(self):
        self.client.force_login(self.usuario_vendedora)
        casos = ['', '0', '-100', '4500.00', '5000.00']
        for monto in casos:
            with self.subTest(monto=monto):
                datos = self._datos(
                    nombre_cliente=f'Invalido {monto}',
                    ya_pago='anticipo_transferencia',
                    precio_total='4500.00',
                    monto_recibido=monto,
                )
                respuesta = self.client.post(self.url, datos)
                self.assertEqual(respuesta.status_code, 200)
                form = respuesta.context['adminform'].form
                self.assertIn('monto_recibido', form.errors)
                self.assertFalse(Reserva.objects.filter(nombre_cliente=f'Invalido {monto}').exists())

    def test_alta_sin_precio_se_rellena_con_sugerencia(self):
        self.client.force_login(self.usuario_vendedora)
        datos = self._datos(
            precio_total='',
            ya_pago='todo_transferencia',
            numero_personas='2',
            moneda=Reserva.Moneda.MXN,
        )
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Cliente Alta')
        self.assertEqual(reserva.precio_total, Decimal('4500.00'))
        self.assertEqual(reserva.monto_transferencia, Decimal('4500.00'))

    def test_alta_sin_precio_sin_sugerencia_falla_opciones_2_y_3_y_pasa_opcion_1(self):
        servicio_sin_precio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Servicio Sin Precio',
            slug='sin-precio',
            tipo_servicio='pesca',
            precio_base=0,  # el campo es obligatorio; 0 = sin precio configurado, no hay sugerencia
            hora_apertura=timezone.datetime.strptime('05:00', '%H:%M').time(),
            hora_cierre=timezone.datetime.strptime('07:00', '%H:%M').time(),
            activo=True,
        )
        self.client.force_login(self.usuario_vendedora)

        # Opcion todo_transferencia: error en precio_total
        datos2 = self._datos(
            nombre_cliente='Sin Sugerencia Dos',
            servicio=str(servicio_sin_precio.pk),
            precio_total='',
            ya_pago='todo_transferencia',
        )
        resp2 = self.client.post(self.url, datos2)
        self.assertEqual(resp2.status_code, 200)
        form2 = resp2.context['adminform'].form
        self.assertIn('precio_total', form2.errors)
        self.assertIn('no se pudo sugerir', str(form2.errors['precio_total']))
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Sin Sugerencia Dos').exists())

        # Opcion anticipo_transferencia: error en precio_total
        datos3 = self._datos(
            nombre_cliente='Sin Sugerencia Tres',
            servicio=str(servicio_sin_precio.pk),
            precio_total='',
            ya_pago='anticipo_transferencia',
            monto_recibido='1000.00',
        )
        resp3 = self.client.post(self.url, datos3)
        self.assertEqual(resp3.status_code, 200)
        form3 = resp3.context['adminform'].form
        self.assertIn('precio_total', form3.errors)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Sin Sugerencia Tres').exists())

        # Opcion no: se permite guardar con precio_total vacio
        datos1 = self._datos(
            nombre_cliente='Sin Sugerencia Uno',
            servicio=str(servicio_sin_precio.pk),
            precio_total='',
            ya_pago='no',
        )
        resp1 = self.client.post(self.url, datos1)
        self.assertEqual(resp1.status_code, 302)
        reserva1 = Reserva.objects.get(nombre_cliente='Sin Sugerencia Uno')
        self.assertIsNone(reserva1.precio_total)

    def test_cupo_lleno_o_hora_fuera_de_ventana_error_formulario_legible(self):
        self.client.force_login(self.usuario_vendedora)

        # Cupo lleno
        fecha_cerrada = timezone.localdate() + timedelta(days=20)
        CupoDiario.objects.create(empresa=self.empresa, fecha=fecha_cerrada, cupo_maximo=0)

        datos_cupo = self._datos(
            nombre_cliente='Cupo Lleno',
            fecha=fecha_cerrada.isoformat(),
            ya_pago='todo_transferencia',
        )
        resp_cupo = self.client.post(self.url, datos_cupo)
        self.assertEqual(resp_cupo.status_code, 200)
        form_cupo = resp_cupo.context['adminform'].form
        self.assertTrue('fecha' in form_cupo.errors or form_cupo.non_field_errors())
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Cupo Lleno').exists())

        # Hora fuera de ventana (pesca abre 5:00 a 7:00 am)
        datos_hora = self._datos(
            nombre_cliente='Hora Invalida',
            hora='14:00',
            ya_pago='todo_transferencia',
        )
        resp_hora = self.client.post(self.url, datos_hora)
        self.assertEqual(resp_hora.status_code, 200)
        form_hora = resp_hora.context['adminform'].form
        self.assertIn('hora', form_hora.errors)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Hora Invalida').exists())

    def test_manipulacion_en_post_es_ignorada(self):
        otra_vendedora = self.crear_vendedora('otra-vendedora')
        perfil_otra = Vendedora.objects.create(
            usuario=otra_vendedora, empresa=self.empresa, codigo='otra-cod', activo=True
        )
        self.client.force_login(self.usuario_vendedora)

        datos = self._datos(
            canal_origen='web',
            estado=Reserva.Estado.PAGADA,
            ya_pago='no',
            vendedora=str(perfil_otra.pk),
        )
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Cliente Alta')
        self.assertEqual(reserva.canal_origen, Reserva.CanalOrigen.WHATSAPP)
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertEqual(reserva.vendedora, self.perfil_vendedora)


class AltaReservaOperadorTests(TestCase):
    def setUp(self):
        call_command('setup_roles', verbosity=0)
        self.sede = Sede.objects.create(
            nombre='Sede Operador', slug='sede-op', zona_horaria='America/Mazatlan', activo=True
        )
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Operador', slug='empresa-op', activo=True
        )
        with scope.como_operador_plataforma():
            crear_flota(self.empresa)
            self.servicio = crear_servicio_pesca(self.empresa)

        self.operador = get_user_model().objects.create_user(
            'operador-alta-test', password='x', is_staff=True
        )
        self.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        self.url = reverse('admin:bookings_reserva_add')
        self.client.force_login(self.operador)

    def test_operador_elige_empresa_en_alta_y_sin_perfil_vendedora_queda_vacia(self):
        resp_get = self.client.get(self.url)
        self.assertEqual(resp_get.status_code, 200)
        form_get = resp_get.context['adminform'].form
        self.assertIn('empresa', form_get.fields)
        self.assertIn('vendedora', form_get.fields)

        datos = {
            'nombre_cliente': 'Cliente Operador',
            'telefono_cliente': '612 123 4567',
            'correo_cliente': 'operador@example.com',
            'fecha': (timezone.localdate() + timedelta(days=5)).isoformat(),
            'hora': '06:00',
            'numero_personas': '2',
            'empresa': str(self.empresa.pk),
            'servicio': str(self.servicio.pk),
            'moneda': Reserva.Moneda.MXN,
            'precio_total': '4500.00',
            'ya_pago': 'no',
            'detalle_transporte-TOTAL_FORMS': '1',
            'detalle_transporte-INITIAL_FORMS': '0',
        }
        resp_post = self.client.post(self.url, datos)
        self.assertEqual(resp_post.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Cliente Operador')
        self.assertEqual(reserva.empresa, self.empresa)
        self.assertIsNone(reserva.vendedora)


class EdicionReservaNoCambioTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.servicio = crear_servicio_pesca(self.empresa)
        self.reserva = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            precio_total=Decimal('4500.00'),
        )
        self.url = reverse('admin:bookings_reserva_change', args=[self.reserva.pk])
        self.vendedora = self.crear_vendedora('vendedora-edicion')
        Vendedora.objects.create(
            usuario=self.vendedora, empresa=self.empresa, codigo='vend-edicion', activo=True
        )
        self.client.force_login(self.vendedora)

    def test_edicion_reserva_conserva_secciones_y_cabecera(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)

        fieldsets = respuesta.context['adminform'].fieldsets
        nombres_fs = [nombre for nombre, _ in fieldsets]
        self.assertEqual(nombres_fs, [
            'Cliente', 'Viaje', 'Cobro', 'Asignación', 'Cancelación', 'Registro del sistema',
        ])
        self.assertContains(respuesta, 'reserva-resumen')
        self.assertContains(respuesta, 'Cliente')

        form = respuesta.context['adminform'].form
        # En la edicion, forma_pago, canal_origen y estado siguen en el formulario
        self.assertIn('estado', form.fields)
        self.assertIn('forma_pago', form.fields)
