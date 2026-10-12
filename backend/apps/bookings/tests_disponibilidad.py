"""Paso 4 del rediseno del backoffice: "no hay lugar" visible y accionable desde la Agenda.

El panorama muestra por dia lo que el motor de cupo usa (tope, vendidos, apartados,
cuanto queda) y deja cerrar/reabrir el dia y sacar o devolver una panga. Las acciones
escriben en los mismos modelos de siempre (`CupoDiario`, `EmbarcacionNoDisponible`).
"""
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.fleet.models import Embarcacion, EmbarcacionNoDisponible
from apps.tenancy import scope
from apps.tenancy.models import Empresa
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .models import CUPO_MAXIMO_DEFAULT, CupoDiario, Reserva, evaluar_cupo
from .panorama import armar_panorama


def _viaje(empresa, fecha, **extra):
    datos = {
        'empresa': empresa,
        'servicio': crear_servicio_pesca(empresa),
        'fecha': fecha,
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
        'estado': Reserva.Estado.PAGADA,
    }
    datos.update(extra)
    return Reserva.objects.create(**datos)  # sin full_clean: se siembran dias a proposito llenos


class CupoDelDiaEnElPanoramaTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.fecha = timezone.localdate() + timedelta(days=2)

    def _dia(self, fecha=None):
        panorama = armar_panorama(timezone.localdate(), self.empresa)
        return next(c for c in panorama.cupo_dias if c.fecha == (fecha or self.fecha))

    def test_sin_registro_el_tope_es_el_normal_y_quedan_los_que_faltan(self):
        _viaje(self.empresa, self.fecha)
        _viaje(self.empresa, self.fecha)

        dia = self._dia()

        self.assertEqual(dia.tope, CUPO_MAXIMO_DEFAULT)
        self.assertEqual((dia.vendidos, dia.apartados), (2, 0))
        self.assertEqual(dia.quedan, CUPO_MAXIMO_DEFAULT - 2)
        self.assertFalse(dia.cerrado)

    def test_un_tope_fijado_por_el_negocio_se_ve(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=6)
        _viaje(self.empresa, self.fecha)

        dia = self._dia()

        self.assertEqual(dia.tope, 6)
        self.assertEqual(dia.quedan, 5)

    def test_tope_cero_es_dia_cerrado(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=0)

        dia = self._dia()

        self.assertTrue(dia.cerrado)
        self.assertEqual(dia.quedan, 0)

    @override_settings(APARTADO_MINUTOS=15)
    def test_un_apartado_vigente_se_cuenta_aparte_y_resta_lo_que_queda(self):
        _viaje(self.empresa, self.fecha)
        _viaje(
            self.empresa, self.fecha, estado=Reserva.Estado.PENDIENTE_PAGO,
            apartado_hasta=timezone.now() + timedelta(minutes=10),
            apartado_demanda={'v': 1, 'habitaciones': [], 'salidas': [
                {'fecha': self.fecha.isoformat(), 'personas': 2, 'servicio_id': None},
            ]},
        )

        dia = self._dia()

        self.assertEqual((dia.vendidos, dia.apartados), (1, 1))
        self.assertEqual(dia.quedan, CUPO_MAXIMO_DEFAULT - 2)

    @override_settings(APARTADO_MINUTOS=15)
    def test_un_apartado_vencido_no_cuenta(self):
        _viaje(
            self.empresa, self.fecha, estado=Reserva.Estado.PENDIENTE_PAGO,
            apartado_hasta=timezone.now() - timedelta(minutes=1),
            apartado_demanda={'v': 1, 'habitaciones': [], 'salidas': [
                {'fecha': self.fecha.isoformat(), 'personas': 2, 'servicio_id': None},
            ]},
        )

        dia = self._dia()

        self.assertEqual(dia.apartados, 0)
        self.assertEqual(dia.quedan, CUPO_MAXIMO_DEFAULT)

    def test_quedan_cero_coincide_con_lo_que_dice_el_motor(self):
        """La cifra no se calcula aparte: cuando dice 0, el motor rechaza la venta."""
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=2)
        _viaje(self.empresa, self.fecha)
        _viaje(self.empresa, self.fecha)

        self.assertEqual(self._dia().quedan, 0)
        self.assertEqual(evaluar_cupo(self.fecha, 1, self.empresa), 'lleno')

    def test_la_pantalla_muestra_cuanto_queda_y_los_botones_segun_permiso(self):
        _viaje(self.empresa, self.fecha)
        self.client.force_login(self.crear_vendedora())

        respuesta = self.client.get(reverse('admin:bookings_agenda_changelist'))

        self.assertContains(respuesta, 'data-cupo-dia')
        self.assertContains(respuesta, f'Quedan <b style="">{CUPO_MAXIMO_DEFAULT - 1}</b> de {CUPO_MAXIMO_DEFAULT}')
        self.assertContains(respuesta, 'data-accion-dia="cerrar_dia"')
        # Sacar una panga es tocar su celda vacia: sin una etiqueta repetida en cada celda.
        self.assertContains(respuesta, 'data-tocable')
        self.assertContains(respuesta, 'Toca para sacar esta panga ese día')
        self.assertNotContains(respuesta, 'data-panga-fuera')

    def test_sin_permiso_no_se_pintan_los_botones(self):
        sin_permisos = self.crear_vendedora(username='sinpermisos', permisos=[])
        sin_permisos.user_permissions.add(Permission.objects.get(codename='view_agenda'))
        self.client.force_login(sin_permisos)

        respuesta = self.client.get(reverse('admin:bookings_agenda_changelist'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'data-accion-dia')
        self.assertNotContains(respuesta, 'data-tocable')


class AccionesDeDisponibilidadTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_disponibilidad')
        self.fecha = timezone.localdate() + timedelta(days=2)
        self.panga = Embarcacion.objects.filter(empresa=self.empresa, activa=True).first()
        self.client.force_login(self.crear_vendedora())

    def _post(self, **datos):
        return self.client.post(self.url, {'fecha': self.fecha.isoformat(), **datos})

    def test_cerrar_el_dia_pone_el_tope_en_cero_y_reabrirlo_lo_deja_en_el_normal(self):
        self.assertEqual(self._post(accion='cerrar_dia').status_code, 200)
        self.assertEqual(
            CupoDiario.objects.get(empresa=self.empresa, fecha=self.fecha).cupo_maximo, 0)
        self.assertEqual(evaluar_cupo(self.fecha, 1, self.empresa), 'lleno')

        self.assertEqual(self._post(accion='abrir_dia').status_code, 200)
        self.assertEqual(
            CupoDiario.objects.get(empresa=self.empresa, fecha=self.fecha).cupo_maximo,
            CUPO_MAXIMO_DEFAULT)
        self.assertIsNone(evaluar_cupo(self.fecha, 1, self.empresa))

    def test_marcar_una_panga_fuera_registra_motivo_y_quien(self):
        respuesta = self._post(accion='panga_fuera', embarcacion=self.panga.pk, motivo='Motor')

        self.assertEqual(respuesta.status_code, 200)
        baja = EmbarcacionNoDisponible.objects.get(
            empresa=self.empresa, fecha=self.fecha, embarcacion=self.panga)
        self.assertEqual(baja.motivo, 'Motor')
        self.assertEqual(baja.registrado_por.username, 'vendedora')
        # Repetirlo no duplica ni falla.
        self.assertEqual(self._post(accion='panga_fuera', embarcacion=self.panga.pk).status_code, 200)
        self.assertEqual(EmbarcacionNoDisponible.objects.filter(embarcacion=self.panga).count(), 1)

    def test_no_se_saca_una_panga_que_ya_tiene_un_viaje_ese_dia(self):
        _viaje(self.empresa, self.fecha, estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga)

        respuesta = self._post(accion='panga_fuera', embarcacion=self.panga.pk)

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn('Reasignalo', respuesta.json()['detail'])
        self.assertFalse(EmbarcacionNoDisponible.objects.exists())

    def test_devolver_la_panga_borra_la_baja(self):
        EmbarcacionNoDisponible.objects.create(
            empresa=self.empresa, fecha=self.fecha, embarcacion=self.panga)

        self.assertEqual(self._post(accion='panga_vuelve', embarcacion=self.panga.pk).status_code, 200)

        self.assertFalse(EmbarcacionNoDisponible.objects.exists())

    def test_una_panga_de_otra_empresa_se_rechaza(self):
        otra = Empresa.objects.create(sede=self.sede, nombre='Otra', slug='otra-flota-x')
        ajena = Embarcacion.objects.create(
            empresa=otra, nombre='Ajena', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3)

        respuesta = self._post(accion='panga_fuera', embarcacion=ajena.pk)

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(EmbarcacionNoDisponible.objects.exists())

    def test_un_dia_pasado_o_una_fecha_mala_se_rechazan(self):
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()

        self.assertEqual(
            self.client.post(self.url, {'accion': 'cerrar_dia', 'fecha': ayer}).status_code, 400)
        self.assertEqual(
            self.client.post(self.url, {'accion': 'cerrar_dia', 'fecha': 'nope'}).status_code, 400)
        self.assertFalse(CupoDiario.objects.exists())

    def test_solo_acepta_post_y_acciones_conocidas(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self._post(accion='borrar_todo').status_code, 400)

    def test_sin_el_permiso_del_modelo_la_accion_se_rechaza(self):
        usuario = self.crear_vendedora(username='sinpermisos', permisos=[])
        usuario.user_permissions.add(Permission.objects.get(codename='view_agenda'))
        self.client.force_login(usuario)

        self.assertEqual(self._post(accion='cerrar_dia').status_code, 403)
        self.assertEqual(
            self._post(accion='panga_fuera', embarcacion=self.panga.pk).status_code, 403)
        self.assertFalse(CupoDiario.objects.exists())
        self.assertFalse(EmbarcacionNoDisponible.objects.exists())


class DisponibilidadDelOperadorTests(TestCase):
    """El operador de plataforma elige la empresa: la accion la recibe por `empresa`."""

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        from apps.tenancy.models import Sede

        sede = Sede.objects.create(nombre='Sede op2', slug='sede-op2')
        cls.empresa = Empresa.objects.create(sede=sede, nombre='Flota Op', slug='flota-op')
        cls.operador = get_user_model().objects.create_user('op-disp', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        cls.url = reverse('admin:bookings_agenda_disponibilidad')
        cls.fecha = timezone.localdate() + timedelta(days=3)

    def setUp(self):
        self.client.force_login(self.operador)

    def test_cierra_el_dia_de_la_empresa_elegida(self):
        respuesta = self.client.post(self.url, {
            'accion': 'cerrar_dia', 'fecha': self.fecha.isoformat(), 'empresa': 'flota-op'})

        self.assertEqual(respuesta.status_code, 200)
        with scope.como_operador_plataforma():
            self.assertEqual(
                CupoDiario.objects.get(empresa=self.empresa, fecha=self.fecha).cupo_maximo, 0)

    def test_sin_empresa_pide_elegir(self):
        respuesta = self.client.post(self.url, {
            'accion': 'cerrar_dia', 'fecha': self.fecha.isoformat()})

        self.assertEqual(respuesta.status_code, 400)
