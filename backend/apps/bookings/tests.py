from datetime import date, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from apps.fleet.models import (
    Capitan,
    CodigoPromocional,
    Embarcacion,
    EmbarcacionNoDisponible,
    PuntoEncuentro,
    Servicio,
)
from apps.tenancy import scope
from apps.testing import crear_personalizacion_pesca, ApiTestCase, EmpresaTestCase, OperadorTestCase, crear_flota, crear_servicio_pesca

from .admin import telefono_marcable
from .models import (
    CUPO_MAXIMO_DEFAULT,
    DESLINDE_VERSION,
    MAX_PERSONAS,
    MOTIVO_LLENO,
    MOTIVO_SIN_PANGA,
    caben,
    codigo_promocional_valido,
    evaluar_codigo_promocional,
    motivo_sin_lugar,
    proxima_fecha_disponible,
    validar_codigo_promocional_en_pago,
    HORAS_PARA_CONSIDERAR_ABANDONADO,
    Agenda,
    CheckoutAbandonado,
    CupoDiario,
    DetalleTransporte,
    Reserva,
    Vendedora,
)
from apps.fleet.enums import TipoTraslado, Zona


def envejecer(reserva, **delta):
    """`creado_en` es auto_now_add, hay que reescribirlo con un UPDATE."""
    Reserva.objects.filter(pk=reserva.pk).update(creado_en=timezone.now() - timedelta(**delta))
    return reserva


def datos_reserva(empresa, **overrides):
    # Hay tests que llaman Reserva(**datos_reserva(empresa)).full_clean() directo, y el
    # motor de cupo le pregunta a la flota: sin pangas no cabe nadie.
    empresa_real = overrides.get('empresa', empresa)
    crear_flota(empresa_real)
    base = {
        'empresa': empresa_real,
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
    }
    if 'servicio' not in overrides and 'paquete' not in overrides:
        base['servicio'] = crear_servicio_pesca(empresa_real)
    base.update(overrides)
    return base


def crear_reserva(empresa, **overrides):
    reserva = Reserva(**datos_reserva(empresa, **overrides))
    reserva.full_clean()
    reserva.save()
    return reserva


class VentanaSalidaTests(EmpresaTestCase):
    def test_hora_fuera_de_la_ventana_es_invalida(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, hora=time(8, 0))).full_clean()

    def test_ventana_pesca_limites(self):
        # 04:59 inválida
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, hora=time(4, 59))).full_clean()
        # 05:00 válida
        Reserva(**datos_reserva(self.empresa, hora=time(5, 0))).full_clean()
        # 07:00 válida
        Reserva(**datos_reserva(self.empresa, hora=time(7, 0))).full_clean()
        # 07:01 inválida
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, hora=time(7, 1))).full_clean()


class NumeroPersonasTests(EmpresaTestCase):
    def test_el_tope_es_la_panga_mas_grande_de_la_flota(self):
        """La flota real son 8 pangas de maximo 3 y 2 de maximo 5.

        El tope estuvo en 6, que no lo cumple ninguna: la web aceptaba y cobraba
        un viaje de 6 personas que despues no habia forma de operar.
        """
        Reserva(**datos_reserva(self.empresa, numero_personas=MAX_PERSONAS)).full_clean()

        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, numero_personas=MAX_PERSONAS + 1)).full_clean()

    def test_seis_personas_ya_no_se_acepta(self):
        # Explicito y no derivado de MAX_PERSONAS: si alguien sube la constante
        # sin comprar una panga mas grande, este test lo detiene.
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, numero_personas=6)).full_clean()

    def test_una_persona_es_valido(self):
        Reserva(**datos_reserva(self.empresa, numero_personas=1)).full_clean()

    def test_no_cabe_en_la_embarcacion_asignada(self):
        chica = Embarcacion.objects.create(
            empresa=self.empresa, nombre='La Chica',
            clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
        )
        reserva = Reserva(**datos_reserva(self.empresa, numero_personas=5, embarcacion=chica))
        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()
        self.assertIn('embarcacion', ctx.exception.message_dict)


class DeslindeTests(EmpresaTestCase):
    def test_reserva_web_sin_deslinde_es_invalida(self):
        with self.assertRaises(ValidationError) as ctx:
            Reserva(**datos_reserva(self.empresa, deslinde_aceptado=False)).full_clean()
        self.assertIn('deslinde_aceptado', ctx.exception.message_dict)

    def test_reserva_por_whatsapp_no_requiere_deslinde_en_el_sistema(self):
        Reserva(**datos_reserva(
            self.empresa,
            canal_origen=Reserva.CanalOrigen.WHATSAPP, deslinde_aceptado=False, deslinde_nombre='',
        )).full_clean()


class CupoTests(EmpresaTestCase):
    def test_pendiente_de_pago_no_ocupa_cupo(self):
        fecha = date.today() + timedelta(days=10)
        for _ in range(CUPO_MAXIMO_DEFAULT + 2):
            crear_reserva(self.empresa, fecha=fecha)
        crear_reserva(self.empresa, fecha=fecha).full_clean()

    def test_se_llena_con_reservas_pagadas(self):
        fecha = date.today() + timedelta(days=10)
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(self.empresa, fecha=fecha, estado=Reserva.Estado.PAGADA)
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, fecha=fecha, estado=Reserva.Estado.PAGADA)).full_clean()

    def test_cupo_diario_override_cierra_el_dia(self):
        fecha = date.today() + timedelta(days=10)
        CupoDiario.objects.create(empresa=self.empresa, fecha=fecha, cupo_maximo=0)
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, fecha=fecha, estado=Reserva.Estado.PAGADA)).full_clean()


class CambioDeFechaTests(EmpresaTestCase):
    def test_permitido_con_mas_de_48_horas(self):
        reserva = crear_reserva(
            self.empresa, fecha=date.today() + timedelta(days=10), estado=Reserva.Estado.PAGADA
        )
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.fecha = date.today() + timedelta(days=12)
        reserva.full_clean()

    def test_bloqueado_dentro_de_las_48_horas(self):
        manana = timezone.localtime().date() + timedelta(days=1)
        reserva = crear_reserva(self.empresa, fecha=manana, estado=Reserva.Estado.PAGADA)
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.fecha = manana + timedelta(days=5)
        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()
        self.assertIn('fecha', ctx.exception.message_dict)

    def test_cancelar_por_mal_clima_no_pide_48_horas(self):
        manana = timezone.localtime().date() + timedelta(days=1)
        reserva = crear_reserva(self.empresa, fecha=manana, estado=Reserva.Estado.PAGADA)
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.motivo_cancelacion = 'Mal clima'
        reserva.cancelada_en = timezone.now()
        reserva.reembolsada = True
        reserva.full_clean()


class CodigoPromocionalValidoTests(EmpresaTestCase):
    def crear_codigo(self, **overrides):
        datos = {'empresa': self.empresa, 'codigo': 'VERANO10', 'porcentaje_descuento': Decimal('10')}
        datos.update(overrides)
        return CodigoPromocional.objects.create(**datos)

    def test_codigo_activo_sin_restricciones_es_valido(self):
        promo = self.crear_codigo()
        self.assertTrue(codigo_promocional_valido(promo, 'cliente@example.com'))

    def test_codigo_inactivo_no_es_valido(self):
        promo = self.crear_codigo(activo=False)
        self.assertFalse(codigo_promocional_valido(promo, 'cliente@example.com'))

    def test_antes_de_fecha_inicio_no_es_valido(self):
        promo = self.crear_codigo(fecha_inicio=timezone.now() + timedelta(days=1))
        self.assertFalse(codigo_promocional_valido(promo, 'cliente@example.com'))

    def test_despues_de_fecha_fin_no_es_valido(self):
        promo = self.crear_codigo(fecha_fin=timezone.now() - timedelta(days=1))
        self.assertFalse(codigo_promocional_valido(promo, 'cliente@example.com'))

    def test_no_alcanza_el_monto_minimo(self):
        promo = self.crear_codigo(monto_minimo=Decimal('5000'))
        self.assertFalse(codigo_promocional_valido(
            promo, 'cliente@example.com', monto_viaje=Decimal('4000'), moneda='MXN',
        ))

    def test_alcanza_el_monto_minimo_por_moneda_separado(self):
        promo = self.crear_codigo(monto_minimo=Decimal('5000'), monto_minimo_usd=Decimal('100'))
        self.assertFalse(codigo_promocional_valido(
            promo, 'cliente@example.com', monto_viaje=Decimal('4000'), moneda='MXN',
        ))
        self.assertTrue(codigo_promocional_valido(
            promo, 'cliente@example.com', monto_viaje=Decimal('200'), moneda='USD',
        ))

    def test_usos_maximos_agotados_no_cuenta_pendiente_de_pago(self):
        promo = self.crear_codigo(usos_maximos=1)
        crear_reserva(self.empresa, codigo_promocional=promo)  # pendiente_pago, no ocupa cupo
        self.assertTrue(codigo_promocional_valido(promo, 'otro@example.com'))

        crear_reserva(self.empresa, codigo_promocional=promo, estado=Reserva.Estado.PAGADA)
        self.assertFalse(codigo_promocional_valido(promo, 'otro@example.com'))

    def test_usos_maximos_por_cliente(self):
        promo = self.crear_codigo(usos_maximos_por_cliente=1)
        crear_reserva(
            self.empresa, codigo_promocional=promo, estado=Reserva.Estado.PAGADA,
            correo_cliente='repetido@example.com',
        )
        self.assertFalse(codigo_promocional_valido(promo, 'repetido@example.com'))
        self.assertTrue(codigo_promocional_valido(promo, 'nuevo@example.com'))

    def test_excluir_pk_no_cuenta_la_reserva_propia(self):
        promo = self.crear_codigo(usos_maximos=1)
        reserva = crear_reserva(self.empresa, codigo_promocional=promo, estado=Reserva.Estado.PAGADA)
        self.assertFalse(codigo_promocional_valido(promo, 'otro@example.com'))
        self.assertTrue(codigo_promocional_valido(promo, 'otro@example.com', excluir_pk=reserva.pk))


class EvaluarCodigoPromocionalTests(EmpresaTestCase):
    def test_codigo_vacio_devuelve_none(self):
        self.assertIsNone(evaluar_codigo_promocional('', 'cliente@example.com', self.empresa))

    def test_codigo_inexistente_devuelve_none(self):
        self.assertIsNone(evaluar_codigo_promocional('NOEXISTE', 'cliente@example.com', self.empresa))

    def test_normaliza_mayusculas_y_espacios(self):
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=Decimal('10'))
        promo = evaluar_codigo_promocional(' verano10 ', 'cliente@example.com', self.empresa)
        self.assertIsNotNone(promo)
        self.assertEqual(promo.codigo, 'VERANO10')

    def test_codigo_invalido_devuelve_none(self):
        CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='VIEJO', porcentaje_descuento=Decimal('10'), activo=False,
        )
        self.assertIsNone(evaluar_codigo_promocional('VIEJO', 'cliente@example.com', self.empresa))


class ValidarCodigoPromocionalEnPagoTests(EmpresaTestCase):
    def test_codigo_valido_no_lanza(self):
        promo = CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='OK10', porcentaje_descuento=Decimal('10'))
        validar_codigo_promocional_en_pago(
            promo, 'MXN', Decimal('4500'), 'cliente@example.com', self.empresa)

    def test_codigo_agotado_lanza_con_la_clave_codigo_promocional(self):
        promo = CodigoPromocional.objects.create(
            empresa=self.empresa, codigo='AGOTADO', porcentaje_descuento=Decimal('10'), usos_maximos=1,
        )
        crear_reserva(self.empresa, codigo_promocional=promo, estado=Reserva.Estado.PAGADA)
        with self.assertRaises(ValidationError) as ctx:
            validar_codigo_promocional_en_pago(
                promo, 'MXN', Decimal('4500'), 'otro@example.com', self.empresa)
        self.assertIn('codigo_promocional', ctx.exception.message_dict)


class CupoApiTests(ApiTestCase):
    def test_fecha_invalida_responde_400(self):
        response = self.client.get(f'/api/{self.empresa.slug}/cupo/?fecha=no-es-fecha')
        self.assertEqual(response.status_code, 400)

    def test_sin_fecha_responde_400(self):
        self.assertEqual(self.client.get(f'/api/{self.empresa.slug}/cupo/').status_code, 400)

    def test_fecha_valida_responde_el_cupo(self):
        fecha = date.today() + timedelta(days=10)
        crear_reserva(self.empresa, fecha=fecha, estado=Reserva.Estado.PAGADA)
        response = self.client.get(f'/api/{self.empresa.slug}/cupo/?fecha={fecha}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['ocupadas'], 1)
        self.assertTrue(response.json()['disponible'])


class TelefonoMarcableTests(TestCase):
    def test_completa_la_lada_de_pais_a_los_de_10_digitos(self):
        self.assertEqual(telefono_marcable('612 123 4567'), '526121234567')

    def test_respeta_el_que_ya_trae_lada(self):
        self.assertEqual(telefono_marcable('+52 1 612 123 4567'), '5216121234567')

    def test_descarta_el_incompleto(self):
        self.assertEqual(telefono_marcable('612 1234'), '')
        self.assertEqual(telefono_marcable(''), '')
        self.assertEqual(telefono_marcable(None), '')


class CheckoutAbandonadoTests(EmpresaTestCase):
    def test_no_lista_al_que_apenas_empezo(self):
        crear_reserva(self.empresa)  # pendiente_pago, recien creada
        self.assertEqual(CheckoutAbandonado.abandonados().count(), 0)

    def test_lista_al_que_lleva_rato_sin_pagar(self):
        envejecer(crear_reserva(self.empresa), hours=HORAS_PARA_CONSIDERAR_ABANDONADO + 1)
        self.assertEqual(CheckoutAbandonado.abandonados().count(), 1)

    def test_no_lista_las_que_si_pagaron(self):
        envejecer(crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA), hours=48)
        self.assertEqual(CheckoutAbandonado.abandonados().count(), 0)

    def test_el_listado_del_admin_es_solo_lectura(self):
        envejecer(crear_reserva(self.empresa), hours=48)
        self.client.force_login(self.crear_jefe())

        response = self.client.get(reverse('admin:bookings_checkoutabandonado_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'wa.me')
        # Ni superusuario puede agregar o borrar desde aqui.
        self.assertEqual(
            self.client.get(reverse('admin:bookings_checkoutabandonado_add')).status_code, 403
        )

    def test_la_vendedora_puede_verlo(self):
        vendedora = self.crear_vendedora(permisos=[])
        vendedora.user_permissions.add(
            Permission.objects.get(codename='view_checkoutabandonado')
        )
        self.client.force_login(vendedora)
        self.assertEqual(
            self.client.get(reverse('admin:bookings_checkoutabandonado_changelist')).status_code,
            200,
        )


class LimpiarCheckoutsAbandonadosTests(EmpresaTestCase):
    def ejecutar(self, **kwargs):
        # El comando itera todas las Empresas y abre su propio scope.con_empresa
        # por cada una -- no es reentrante con el que EmpresaTestCase ya dejo
        # abierto para self.empresa (ver apps/testing.py y progress.md linea ~133).
        salida = StringIO()
        self._alcance.__exit__(None, None, None)
        try:
            call_command('limpiar_checkouts_abandonados', stdout=salida, **kwargs)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        return salida.getvalue()

    def test_borra_los_viejos(self):
        envejecer(crear_reserva(self.empresa), days=40)
        self.ejecutar()
        self.assertEqual(Reserva.objects.count(), 0)

    def test_respeta_los_recientes(self):
        envejecer(crear_reserva(self.empresa), days=5)
        self.ejecutar()
        self.assertEqual(Reserva.objects.count(), 1)

    def test_nunca_toca_una_reserva_pagada(self):
        envejecer(crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA), days=400)
        self.ejecutar()
        self.assertEqual(Reserva.objects.count(), 1)

    def test_dias_configurable(self):
        envejecer(crear_reserva(self.empresa), days=5)
        self.ejecutar(dias=3)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_dry_run_no_borra(self):
        envejecer(crear_reserva(self.empresa), days=40)
        salida = self.ejecutar(dry_run=True)
        self.assertIn('Se borrarian 1', salida)
        self.assertEqual(Reserva.objects.count(), 1)


class LiquidacionEnEfectivoTests(EmpresaTestCase):
    """El 70% que se cobra en el muelle tiene que dejar rastro."""

    def setUp(self):
        self.jefa = self.crear_jefe()
        self.client.force_login(self.jefa)
        self.url = reverse('admin:bookings_reserva_changelist')

    def reserva_con_anticipo(self):
        reserva = crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        reserva.precio_total = Decimal('4500.00')
        reserva.monto_pagado = Decimal('1350.00')
        reserva.forma_pago = Reserva.FormaPago.ANTICIPO
        reserva.save()
        return reserva

    def liquidar(self, reserva):
        return self.client.post(self.url, {
            'action': 'registrar_liquidacion_en_efectivo',
            '_selected_action': [str(reserva.pk)],
        }, follow=True)

    def test_el_saldo_arranca_en_el_70_por_ciento(self):
        self.assertEqual(self.reserva_con_anticipo().saldo_pendiente, Decimal('3150.00'))

    def test_registrar_la_liquidacion_deja_el_saldo_en_cero(self):
        reserva = self.reserva_con_anticipo()
        self.liquidar(reserva)

        reserva.refresh_from_db()
        self.assertEqual(reserva.monto_efectivo, Decimal('3150.00'))
        self.assertEqual(reserva.saldo_pendiente, Decimal('0.00'))
        self.assertTrue(reserva.liquidado)

    def test_deja_constancia_de_quien_y_cuando_cobro(self):
        reserva = self.reserva_con_anticipo()
        self.liquidar(reserva)

        reserva.refresh_from_db()
        self.assertEqual(reserva.efectivo_cobrado_por, self.jefa)
        self.assertIsNotNone(reserva.efectivo_cobrado_en)

    def test_liquidar_dos_veces_no_cobra_de_mas(self):
        reserva = self.reserva_con_anticipo()
        self.liquidar(reserva)
        self.liquidar(reserva)

        reserva.refresh_from_db()
        self.assertEqual(reserva.monto_efectivo, Decimal('3150.00'))

    def test_una_reserva_pagada_al_100_no_debe_nada(self):
        reserva = crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        reserva.precio_total = Decimal('4500.00')
        reserva.monto_pagado = Decimal('4500.00')
        reserva.forma_pago = Reserva.FormaPago.COMPLETO
        reserva.save()

        self.assertTrue(reserva.liquidado)
        self.liquidar(reserva)

        reserva.refresh_from_db()
        self.assertIsNone(reserva.monto_efectivo)

    def test_se_puede_cobrar_de_mas_por_lo_cotizado_aparte(self):
        # Bebidas y transporte los cotiza el agente y se pagan en efectivo, asi
        # que el efectivo recibido puede superar el saldo del tour.
        reserva = self.reserva_con_anticipo()
        reserva.monto_efectivo = Decimal('3900.00')
        reserva.full_clean()
        reserva.save()

        self.assertEqual(reserva.saldo_pendiente, Decimal('-750.00'))
        self.assertTrue(reserva.liquidado)


class AdminDeCuentasTests(TestCase):
    """auth.User y auth.Group re-registrados con el ModelAdmin de Unfold.

    Django los registra con su ModelAdmin de siempre. La plantilla de Unfold
    `unfold/helpers/add_link.html` corta en `{% if cl.model_admin.show_add_link %}`,
    atributo que solo existe en el ModelAdmin de Unfold, asi que con el registro
    por defecto el listado carga **sin boton de agregar** y no hay forma de dar de
    alta una vendedora desde la interfaz. Ver `admin.py` y `setup_roles`.

    El operador de plataforma es quien de verdad tiene `add`/`delete` sobre
    `auth.user` y todo `auth.group` (H5, `setup_roles.py`) -- Jefe perdio el alta
    directa de usuario (pasa por "Dar de alta vendedora") y todo permiso sobre
    `auth.group`. Sin `MembresiaEmpresa`, asi que no necesita `EmpresaTestCase`.
    """

    def setUp(self):
        call_command('setup_roles', verbosity=0)
        operador = User.objects.create_user('operador', password='x', is_staff=True)
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        self.client.force_login(operador)

    def test_el_listado_de_usuarios_ofrece_el_boton_de_agregar(self):
        html = self.client.get(reverse('admin:auth_user_changelist')).content.decode()
        self.assertIn(reverse('admin:auth_user_add'), html)
        self.assertIn('addlink', html)

    def test_el_listado_de_grupos_ofrece_el_boton_de_agregar(self):
        html = self.client.get(reverse('admin:auth_group_changelist')).content.decode()
        self.assertIn(reverse('admin:auth_group_add'), html)
        self.assertIn('addlink', html)

    def test_el_alta_de_usuario_carga_y_da_de_alta_la_cuenta(self):
        self.assertEqual(self.client.get(reverse('admin:auth_user_add')).status_code, 200)

        self.client.post(reverse('admin:auth_user_add'), {
            'username': 'vendedora_nueva',
            'password1': 'una-contrasena-larga-9',
            'password2': 'una-contrasena-larga-9',
        })
        self.assertTrue(User.objects.filter(username='vendedora_nueva').exists())


class ReservasNuevasAdminTests(EmpresaTestCase):
    """Contador de reservas nuevas del listado del admin (ver ReservaAdmin)."""

    def setUp(self):
        self.url = reverse('admin:bookings_reserva_nuevas')

    def semilla(self):
        """Primera llamada, sin `desde`: devuelve la hora del servidor y cero."""
        body = self.client.get(self.url).json()
        self.assertEqual(body['nuevas'], 0)
        return body['desde']

    def test_anonimo_no_pasa(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_staff_sin_permiso_de_ver_reservas_recibe_403(self):
        vendedora = self.crear_vendedora(username='sin_permisos', permisos=[])
        self.client.force_login(vendedora)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_vendedora_con_permiso_puede_consultar(self):
        vendedora = self.crear_vendedora(permisos=[])
        vendedora.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(vendedora)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_cuenta_las_pagadas_que_entraron_despues(self):
        self.client.force_login(self.crear_jefe())
        desde = self.semilla()

        crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        body = self.client.get(self.url, {'desde': desde}).json()

        self.assertEqual(body['nuevas'], 2)
        # El ancla no se mueve: el contador sigue subiendo hasta que se recargue.
        self.assertEqual(body['desde'], desde)

        crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        self.assertEqual(self.client.get(self.url, {'desde': desde}).json()['nuevas'], 3)

    def test_ignora_los_checkouts_abandonados(self):
        self.client.force_login(self.crear_jefe())
        desde = self.semilla()

        crear_reserva(self.empresa)  # pendiente_pago
        self.assertEqual(self.client.get(self.url, {'desde': desde}).json()['nuevas'], 0)

    def test_ignora_lo_anterior_a_la_carga_de_la_pagina(self):
        self.client.force_login(self.crear_jefe())
        crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        desde = self.semilla()

        self.assertEqual(self.client.get(self.url, {'desde': desde}).json()['nuevas'], 0)

    def test_desde_invalido_responde_400(self):
        self.client.force_login(self.crear_jefe())
        self.assertEqual(self.client.get(self.url, {'desde': 'ayer'}).status_code, 400)


class ReservaApiTests(ApiTestCase):
    CHECKOUT_ID = '11111111-1111-4111-8111-111111111111'

    def payload(self, **overrides):
        servicio = crear_servicio_pesca(self.empresa)
        datos = {
            'checkout_id': self.CHECKOUT_ID,
            'fecha': str(date.today() + timedelta(days=10)),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'USD',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'servicio': servicio.slug,
        }
        datos.update(overrides)
        return datos

    def enviar(self, **overrides):
        return self.client.post(
            f'/api/{self.empresa.slug}/reservas/', self.payload(**overrides),
            content_type='application/json',
        )

    def test_crea_pendiente_de_pago_y_sella_el_deslinde(self):
        response = self.enviar()
        self.assertEqual(response.status_code, 201)

        reserva = Reserva.objects.get(pk=response.json()['id'])
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertEqual(reserva.canal_origen, Reserva.CanalOrigen.WEB)
        self.assertEqual(reserva.moneda, 'USD')
        self.assertIsNotNone(reserva.deslinde_aceptado_en)
        self.assertIsNotNone(reserva.deslinde_ip)
        self.assertEqual(reserva.deslinde_version, DESLINDE_VERSION)

    def test_la_version_del_deslinde_la_pone_el_servidor(self):
        """Una constancia que el propio firmante puede elegir no acredita nada.

        La clausula 8(d) del deslinde promete conservar registro del texto
        aceptado; si el cliente pudiera mandar la version, podria firmar hoy
        diciendo que acepto el texto de hace un ano.
        """
        response = self.enviar(deslinde_version='1999-01-01')
        self.assertEqual(response.status_code, 201)

        reserva = Reserva.objects.get(pk=response.json()['id'])
        self.assertEqual(reserva.deslinde_version, DESLINDE_VERSION)

    def test_un_checkout_id_que_no_es_uuid_da_400_y_no_500(self):
        """La busqueda del upsert corre antes de que el serializer valide nada.

        Con el valor crudo metido directo al filtro de un UUIDField, Postgres
        rechaza la consulta y la ruta — que es publica y sin autenticacion —
        contesta 500. Lo que corresponde es el 400 del serializer.
        """
        # Un entero no entra aqui: DRF lo acepta como UUID (`UUID(int=...)`).
        for basura in ['no-soy-un-uuid', '', {'a': 1}, ['x']]:
            with self.subTest(checkout_id=basura):
                response = self.enviar(checkout_id=basura)
                self.assertEqual(response.status_code, 400)
                self.assertIn('checkout_id', response.json())

    def test_reintentar_el_checkout_no_duplica_la_reserva(self):
        primera = self.enviar()
        segunda = self.enviar()

        self.assertEqual(primera.status_code, 201)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(primera.json()['id'], segunda.json()['id'])
        self.assertEqual(Reserva.objects.count(), 1)

    def test_corregir_los_datos_actualiza_la_misma_reserva(self):
        creada = self.enviar()
        nueva_fecha = str(date.today() + timedelta(days=20))
        self.enviar(fecha=nueva_fecha, numero_personas=5, hora='05:30')

        self.assertEqual(Reserva.objects.count(), 1)
        reserva = Reserva.objects.get(pk=creada.json()['id'])
        self.assertEqual(str(reserva.fecha), nueva_fecha)
        self.assertEqual(reserva.numero_personas, 5)
        self.assertEqual(str(reserva.hora), '05:30:00')

    def test_otro_checkout_id_es_otra_reserva(self):
        self.enviar()
        self.enviar(checkout_id='22222222-2222-4222-8222-222222222222')
        self.assertEqual(Reserva.objects.count(), 2)

    def test_una_reserva_ya_pagada_no_se_reescribe(self):
        creada = self.enviar()
        Reserva.objects.filter(pk=creada.json()['id']).update(estado=Reserva.Estado.PAGADA)

        # El mismo checkout_id ya no encuentra fila editable: empieza una nueva.
        response = self.enviar(numero_personas=5)
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(response.json()['id'], creada.json()['id'])

        pagada = Reserva.objects.get(pk=creada.json()['id'])
        self.assertEqual(pagada.numero_personas, 2)

    def test_sin_checkout_id_no_se_acepta(self):
        response = self.client.post(
            f'/api/{self.empresa.slug}/reservas/', self.payload(checkout_id=None),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('checkout_id', response.json())

    def test_rechaza_sin_deslinde(self):
        response = self.enviar(deslinde_aceptado=False)
        self.assertEqual(response.status_code, 400)
        self.assertIn('deslinde_aceptado', response.json())

    def test_rechaza_hora_fuera_de_la_ventana(self):
        self.assertEqual(self.enviar(hora='09:00').status_code, 400)

    def test_rechaza_mas_de_seis_personas(self):
        self.assertEqual(self.enviar(numero_personas=8).status_code, 400)


class ExtrasApiTests(ApiTestCase):
    """`/api/reservas/` acepta la seleccion de extras del paso Extras del
    checkout. Solo escribe la SELECCION — el precio lo congela CrearPagoView
    al pagar, ver docs/superpowers/specs/2026-08-28-extras-checkout-design.md."""

    CHECKOUT_ID = '11111111-1111-4111-8111-111111111111'

    def payload(self, **overrides):
        servicio = crear_servicio_pesca(self.empresa)
        datos = {
            'checkout_id': self.CHECKOUT_ID,
            'fecha': str(date.today() + timedelta(days=10)),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'servicio': servicio.slug,
        }
        datos.update(overrides)
        return datos

    def enviar(self, **overrides):
        return self.client.post(
            f'/api/{self.empresa.slug}/reservas/', self.payload(**overrides),
            content_type='application/json',
        )

    def test_selecciona_extras_sin_precio(self):
        brunch = crear_personalizacion_pesca(
            empresa=self.empresa, tipo='brunch', nombre='Brunch', precio=Decimal('300'))
        licencia = crear_personalizacion_pesca(
            empresa=self.empresa, tipo='licencia', nombre='Licencia', precio=Decimal('450'))

        response = self.enviar(personalizaciones=[{'id': brunch.pk}, {'id': licencia.pk}])

        self.assertEqual(response.status_code, 201)
        reserva = Reserva.objects.get(pk=response.json()['id'])
        seleccionados = set(reserva.personalizaciones_seleccionadas.values_list('servicio_personalizacion_id', flat=True))
        self.assertEqual(seleccionados, {brunch.pk, licencia.pk})
        for extra in reserva.personalizaciones_seleccionadas.all():
            self.assertIsNone(extra.precio_unitario)
            self.assertEqual(extra.cantidad, 1)

    def test_un_extra_inactivo_no_se_puede_seleccionar(self):
        inactivo = crear_personalizacion_pesca(
            empresa=self.empresa, tipo='carnada', nombre='Carnada', precio=Decimal('200'), activo=False,
        )
        self.assertEqual(self.enviar(personalizaciones=[{'id': inactivo.pk}]).status_code, 400)

    def test_reenviar_el_checkout_reescribe_la_seleccion_completa(self):
        brunch = crear_personalizacion_pesca(
            empresa=self.empresa, tipo='brunch', nombre='Brunch', precio=Decimal('300'))
        licencia = crear_personalizacion_pesca(
            empresa=self.empresa, tipo='licencia', nombre='Licencia', precio=Decimal('450'))
        creada = self.enviar(personalizaciones=[{'id': brunch.pk}])

        self.enviar(personalizaciones=[{'id': licencia.pk}])

        reserva = Reserva.objects.get(pk=creada.json()['id'])
        self.assertEqual(
            set(reserva.personalizaciones_seleccionadas.values_list('servicio_personalizacion_id', flat=True)), {licencia.pk}
        )

    def test_manda_cantidad_para_un_extra_con_cantidad_editable(self):
        licencia = crear_personalizacion_pesca(
            empresa=self.empresa, tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            cantidad_editable=True,
        )

        response = self.enviar(numero_personas=5, personalizaciones=[{'id': licencia.pk, 'cantidad': 2}])

        self.assertEqual(response.status_code, 201)
        reserva = Reserva.objects.get(pk=response.json()['id'])
        extra = reserva.personalizaciones_seleccionadas.get(servicio_personalizacion=licencia)
        self.assertEqual(extra.cantidad, 2)
        # Sin precio ni cantidad congelados: eso sigue siendo trabajo exclusivo
        # de CrearPagoView, la seleccion no lo adelanta.
        self.assertIsNone(extra.precio_unitario)

    def test_reenviar_con_otra_cantidad_actualiza_la_fila_existente(self):
        """Cambiar la cantidad de un extra ya elegido, en un reenvio del
        checkout, debe actualizar la fila — no perderse ni crear una segunda."""
        licencia = crear_personalizacion_pesca(
            empresa=self.empresa, tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            cantidad_editable=True,
        )
        creada = self.enviar(numero_personas=5, personalizaciones=[{'id': licencia.pk, 'cantidad': 2}])

        self.enviar(numero_personas=5, personalizaciones=[{'id': licencia.pk, 'cantidad': 4}])

        reserva = Reserva.objects.get(pk=creada.json()['id'])
        self.assertEqual(reserva.personalizaciones_seleccionadas.count(), 1)
        self.assertEqual(
            reserva.personalizaciones_seleccionadas.get(servicio_personalizacion=licencia).cantidad, 4,
        )


class AtribucionDeVentaTests(ApiTestCase):
    """A quien le cuenta cada venta. La comision se liquida fuera del sistema;
    aqui lo unico que importa es que el registro no se pierda ni se invente."""

    CHECKOUT_ID = '33333333-3333-4333-8333-333333333333'

    def setUp(self):
        self.maria = Vendedora.objects.create(
            usuario=User.objects.create_user('maria', password='x', is_staff=True),
            empresa=self.empresa, codigo='maria',
        )

    def enviar(self, **overrides):
        servicio = crear_servicio_pesca(self.empresa)
        datos = {
            'checkout_id': self.CHECKOUT_ID,
            'fecha': str(date.today() + timedelta(days=10)),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'servicio': servicio.slug,
        }
        datos.update(overrides)
        return self.client.post(
            f'/api/{self.empresa.slug}/reservas/', datos, content_type='application/json',
        )

    def test_el_link_de_la_vendedora_le_atribuye_la_venta(self):
        response = self.enviar(ref='maria')

        reserva = Reserva.objects.get(pk=response.json()['id'])
        self.assertEqual(reserva.vendedora, self.maria)
        self.assertIsNotNone(reserva.vendedora_asignada_en)

    def test_sin_ref_la_venta_queda_sin_atribuir(self):
        reserva = Reserva.objects.get(pk=self.enviar().json()['id'])

        self.assertIsNone(reserva.vendedora)
        self.assertIsNone(reserva.vendedora_asignada_en)

    def test_un_codigo_que_no_existe_no_impide_reservar(self):
        response = self.enviar(ref='quien-sabe')

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(Reserva.objects.get(pk=response.json()['id']).vendedora)

    def test_el_codigo_de_una_vendedora_dada_de_baja_ya_no_atribuye(self):
        self.maria.activo = False
        self.maria.save()

        reserva = Reserva.objects.get(pk=self.enviar(ref='maria').json()['id'])
        self.assertIsNone(reserva.vendedora)

    def test_reenviar_el_checkout_sin_ref_no_borra_la_atribucion(self):
        # El cliente entro por el link, corrige la fecha y reenvia: la reserva es
        # la misma fila y la venta sigue siendo de quien lo trajo.
        creada = self.enviar(ref='maria')
        self.enviar(numero_personas=4)

        reserva = Reserva.objects.get(pk=creada.json()['id'])
        self.assertEqual(reserva.numero_personas, 4)
        self.assertEqual(reserva.vendedora, self.maria)

    def test_atribuir_a_mano_sella_la_fecha(self):
        reserva = crear_reserva(self.empresa)
        self.assertIsNone(reserva.vendedora_asignada_en)

        reserva.vendedora = self.maria
        reserva.save()

        self.assertIsNotNone(Reserva.objects.get(pk=reserva.pk).vendedora_asignada_en)

    def test_quitar_la_atribucion_limpia_la_fecha(self):
        reserva = crear_reserva(self.empresa, vendedora=self.maria)
        reserva.vendedora = None
        reserva.save()

        self.assertIsNone(Reserva.objects.get(pk=reserva.pk).vendedora_asignada_en)

    def test_no_se_puede_borrar_una_vendedora_con_ventas(self):
        """Borrarla dejaria ventas sin dueño: para dar de baja se usa `activo`."""
        crear_reserva(self.empresa, vendedora=self.maria)

        with self.assertRaises(ProtectedError):
            self.maria.delete()


class IpDelDeslindeTests(ApiTestCase):
    """La IP que queda en el deslinde es constancia legal: si el propio cliente
    puede elegirla, no prueba nada. `X-Forwarded-For` es una lista donde cada
    salto agrega al final, asi que lo unico creible es lo que escribio nuestro
    proxy — contando desde la derecha (ver apps/bookings/serializers.py)."""

    CHECKOUT_ID = '44444444-4444-4444-8444-444444444444'

    def enviar(self, **extra):
        servicio = crear_servicio_pesca(self.empresa)
        datos = {
            'checkout_id': self.CHECKOUT_ID,
            'fecha': str(date.today() + timedelta(days=10)),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'servicio': servicio.slug,
        }
        response = self.client.post(
            f'/api/{self.empresa.slug}/reservas/', datos, content_type='application/json', **extra
        )
        self.assertEqual(response.status_code, 201, response.content)
        return Reserva.objects.get(pk=response.json()['id'])

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_ignora_la_ip_que_el_cliente_escribe_a_mano(self):
        """Forma real del header detras de Render: el cliente mando su propio
        `X-Forwarded-For` y el proxy le agrego la IP verdadera al final."""
        reserva = self.enviar(HTTP_X_FORWARDED_FOR='1.2.3.4, 203.0.113.9')

        self.assertEqual(reserva.deslinde_ip, '203.0.113.9')

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_toma_la_ip_del_proxy_cuando_no_hay_nada_inventado(self):
        reserva = self.enviar(HTTP_X_FORWARDED_FOR='203.0.113.9')

        self.assertEqual(reserva.deslinde_ip, '203.0.113.9')

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_sin_proxy_de_confianza_no_se_le_cree_al_header(self):
        """Config local: no hay proxy delante, asi que cualquier
        `X-Forwarded-For` que llegue lo puso el cliente. Se usa la IP de la
        conexion real, que nadie puede inventar."""
        reserva = self.enviar(HTTP_X_FORWARDED_FOR='1.2.3.4', REMOTE_ADDR='198.51.100.7')

        self.assertEqual(reserva.deslinde_ip, '198.51.100.7')

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_header_mas_corto_de_lo_esperado_no_se_adivina(self):
        """Si el proxy no dejo su parte, algo esta mal configurado. Antes que
        registrar un dato falso se cae a la IP de la conexion."""
        reserva = self.enviar(REMOTE_ADDR='198.51.100.7')

        self.assertEqual(reserva.deslinde_ip, '198.51.100.7')


class ThrottleTests(ApiTestCase):
    """Las rutas publicas no piden login: sin limite, cualquiera puede llenar el
    panel de reservas basura o disparar PaymentIntents en masa contra la cuenta
    de Stripe."""

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'consulta': '2/min'})
    def test_pasado_el_limite_responde_429(self):
        url = f'/api/{self.empresa.slug}/cupo/?fecha={date.today() + timedelta(days=10)}'

        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 429)

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'reservas': '1/min'})
    def test_el_limite_es_por_ip_no_global(self):
        """Dos clientes distintos detras de la misma pagina no se estorban."""
        servicio = crear_servicio_pesca(self.empresa)
        datos = {
            'checkout_id': '55555555-5555-4555-8555-555555555555',
            'fecha': str(date.today() + timedelta(days=10)),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'servicio': servicio.slug,
        }

        def enviar(ip):
            return self.client.post(
                f'/api/{self.empresa.slug}/reservas/', datos,
                content_type='application/json', REMOTE_ADDR=ip,
            )

        self.assertEqual(enviar('198.51.100.1').status_code, 201)
        self.assertEqual(enviar('198.51.100.1').status_code, 429)
        # Otra IP arranca con su propio contador.
        self.assertEqual(enviar('198.51.100.2').status_code, 200)

    def test_el_webhook_de_stripe_no_se_limita(self):
        """Stripe reintenta en rafagas cuando algo falla; un 429 aqui es un cobro
        que se queda sin reserva. La firma del evento es lo que autentica esta
        ruta, no el volumen."""
        from apps.payments.views import StripeWebhookView

        self.assertEqual(StripeWebhookView.throttle_classes, [])


class ValidacionDeContactoTests(EmpresaTestCase):
    """El telefono y el nombre se aprietan distinto a proposito.

    El telefono es con lo que la vendedora contacta al cliente: uno invalido es
    alguien en el muelle a las 6 am sin que nadie lo espere. El nombre se aprieta
    poco — la regla intuitiva ("solo letras") rompe personas reales.
    """

    def test_telefono_con_letras_no_pasa(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, telefono_cliente='asdf')).full_clean()

    def test_telefono_incompleto_no_pasa(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, telefono_cliente='612 123')).full_clean()

    def test_acepta_el_telefono_como_lo_escribe_la_gente(self):
        for numero in ('6121234567', '612 123 4567', '(612) 123-4567', '+52 1 612 123 4567'):
            with self.subTest(numero=numero):
                Reserva(**datos_reserva(self.empresa, telefono_cliente=numero)).full_clean()

    def test_nombre_con_numeros_no_pasa(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, nombre_cliente='12345')).full_clean()

    def test_nombre_sin_ninguna_letra_no_pasa(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, nombre_cliente='-----')).full_clean()

    def test_no_rechaza_nombres_reales(self):
        """El fallo caro aqui no es guardar un nombre raro: es dejar a una
        persona sin poder reservar por llamarse como se llama."""
        for nombre in ("Jose Munoz", "José Muñoz", "O'Brien", "Garcia-Lopez", "Ana de la Torre"):
            with self.subTest(nombre=nombre):
                Reserva(**datos_reserva(
                    self.empresa, nombre_cliente=nombre, deslinde_nombre=nombre)).full_clean()


class ProximaFechaDisponibleTests(EmpresaTestCase):
    """La busqueda del siguiente dia con espacio vive en el servidor.

    Antes la hacia el navegador con una peticion por dia — hasta 90 seguidas,
    que con el limite de 60/min terminaban en 429 y el frontend se lo tragaba
    en silencio.
    """

    def setUp(self):
        # Dos de estos tests no crean ninguna reserva, asi que nadie sembraria la
        # flota por ellos y sin pangas no cabria nadie.
        crear_flota(self.empresa)

    def test_si_el_dia_pedido_tiene_espacio_se_devuelve_ese(self):
        fecha = date.today() + timedelta(days=10)
        self.assertEqual(proxima_fecha_disponible(fecha, 2, self.empresa), fecha)

    def test_salta_los_dias_llenos(self):
        primero = date.today() + timedelta(days=10)
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(self.empresa, fecha=primero, estado=Reserva.Estado.PAGADA)

        self.assertEqual(
            proxima_fecha_disponible(primero, 2, self.empresa), primero + timedelta(days=1))

    def test_respeta_el_cupo_cerrado_a_mano(self):
        primero = date.today() + timedelta(days=10)
        CupoDiario.objects.create(empresa=self.empresa, fecha=primero, cupo_maximo=0)

        self.assertEqual(
            proxima_fecha_disponible(primero, 2, self.empresa), primero + timedelta(days=1))

    def test_sin_ningun_dia_libre_devuelve_none(self):
        desde = date.today() + timedelta(days=10)
        for i in range(3):
            CupoDiario.objects.create(
                empresa=self.empresa, fecha=desde + timedelta(days=i), cupo_maximo=0)

        self.assertIsNone(proxima_fecha_disponible(desde, 2, self.empresa, dias=3))

    def test_no_hace_una_consulta_por_dia(self):
        """El punto entero del cambio: el costo no crece con la ventana.

        Cuatro consultas fijas: reservas del rango, CupoDiario del rango, y las dos
        de la flota (pangas activas y las marcadas fuera).
        """
        desde = date.today() + timedelta(days=10)
        with self.assertNumQueries(4):
            proxima_fecha_disponible(desde, 2, self.empresa, dias=90)

    def test_salta_los_dias_sin_panga_para_ese_grupo(self):
        """El dia tiene lugares libres, pero no para un grupo de 4."""
        primero = date.today() + timedelta(days=10)
        crear_reserva(self.empresa, fecha=primero, numero_personas=4, estado=Reserva.Estado.PAGADA)
        crear_reserva(self.empresa, fecha=primero, numero_personas=4, estado=Reserva.Estado.PAGADA)

        self.assertEqual(
            proxima_fecha_disponible(primero, 4, self.empresa), primero + timedelta(days=1))
        self.assertEqual(proxima_fecha_disponible(primero, 2, self.empresa), primero)


class CupoApiDevuelveProximaTests(ApiTestCase):
    def test_la_respuesta_trae_la_proxima_fecha_disponible(self):
        fecha = date.today() + timedelta(days=10)
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(self.empresa, fecha=fecha, estado=Reserva.Estado.PAGADA)

        cuerpo = self.client.get(f'/api/{self.empresa.slug}/cupo/?fecha={fecha}').json()

        self.assertFalse(cuerpo['disponible'])
        self.assertEqual(cuerpo['proxima_disponible'], str(fecha + timedelta(days=1)))


class CabenTests(TestCase):
    """El criterio que decide si se cobra o no. Exacto, no heuristica."""

    FLOTA = [5, 5, 3, 3, 3, 3, 3, 3, 3, 3]

    def test_sin_grupos_siempre_cabe(self):
        self.assertTrue(caben([], self.FLOTA))

    def test_mas_grupos_que_pangas_no_cabe(self):
        self.assertFalse(caben([2] * 11, self.FLOTA))

    def test_tres_grupos_de_cuatro_no_caben_en_dos_pangas_grandes(self):
        self.assertFalse(caben([4, 4, 4], self.FLOTA))

    def test_dos_de_cuatro_y_ocho_de_tres_si_caben(self):
        """El caso apretado que si es operable: no puede rechazarse."""
        self.assertTrue(caben([4, 4, 3, 3, 3, 3, 3, 3, 3, 3], self.FLOTA))

    def test_un_grupo_mas_grande_que_la_panga_mas_grande_no_cabe(self):
        self.assertFalse(caben([6], [5]))

    def test_no_depende_del_orden_de_llegada(self):
        """Se emparejan de mayor a menor, asi que el resultado es el mismo vengan
        como vengan."""
        grupos = [4, 2, 4, 3]
        self.assertEqual(
            caben(sorted(grupos, reverse=True), self.FLOTA),
            caben(sorted(list(reversed(grupos)), reverse=True), self.FLOTA),
        )


class MotivoSinLugarTests(TestCase):
    FLOTA = [5, 5, 3, 3, 3, 3, 3, 3, 3, 3]

    def test_si_cabe_no_hay_motivo(self):
        self.assertIsNone(motivo_sin_lugar(2, [], self.FLOTA, tope=10))

    def test_el_tope_de_viajes_manda_sobre_el_de_pangas(self):
        """Si el dia esta lleno a secas, ese es el mensaje util."""
        self.assertEqual(motivo_sin_lugar(4, [2] * 10, self.FLOTA, tope=10), MOTIVO_LLENO)

    def test_sin_panga_para_ese_grupo(self):
        self.assertEqual(motivo_sin_lugar(4, [4, 4], self.FLOTA, tope=10), MOTIVO_SIN_PANGA)

    def test_un_grupo_chico_si_entra_el_mismo_dia(self):
        """Se acabaron las grandes, no el dia."""
        self.assertIsNone(motivo_sin_lugar(2, [4, 4], self.FLOTA, tope=10))


class CupoPorTamanoDelGrupoTests(EmpresaTestCase):
    """Un dia puede tener lugares libres y aun asi no poder recibir a un grupo de
    4: solo dos pangas de la flota lo llevan."""

    def setUp(self):
        crear_flota(self.empresa)
        self.fecha = date.today() + timedelta(days=10)

    def _vender(self, personas):
        return crear_reserva(
            self.empresa, fecha=self.fecha, numero_personas=personas, estado=Reserva.Estado.PAGADA
        )

    def test_un_tercer_grupo_de_cuatro_se_rechaza(self):
        self._vender(4)
        self._vender(4)
        with self.assertRaises(ValidationError) as ctx:
            Reserva(**datos_reserva(self.empresa, fecha=self.fecha, numero_personas=4,
                                    estado=Reserva.Estado.PAGADA)).full_clean()
        self.assertIn('No queda panga', str(ctx.exception))

    def test_un_grupo_chico_el_mismo_dia_si_se_acepta(self):
        """El dia no esta lleno, solo se acabaron las pangas grandes."""
        self._vender(4)
        self._vender(4)
        Reserva(**datos_reserva(self.empresa, fecha=self.fecha, numero_personas=2,
                                estado=Reserva.Estado.PAGADA)).full_clean()

    def test_un_dia_lleno_a_secas_da_el_mensaje_del_tope_de_viajes(self):
        for _ in range(CUPO_MAXIMO_DEFAULT):
            self._vender(2)
        with self.assertRaises(ValidationError) as ctx:
            Reserva(**datos_reserva(self.empresa, fecha=self.fecha, numero_personas=2,
                                    estado=Reserva.Estado.PAGADA)).full_clean()
        self.assertIn('maximo de viajes', str(ctx.exception))

    def test_el_cupo_cerrado_a_mano_manda_sobre_la_flota(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=3)
        for _ in range(3):
            self._vender(2)
        with self.assertRaises(ValidationError) as ctx:
            Reserva(**datos_reserva(self.empresa, fecha=self.fecha, numero_personas=2,
                                    estado=Reserva.Estado.PAGADA)).full_clean()
        self.assertIn('maximo de viajes', str(ctx.exception))

    def test_editar_una_reserva_no_la_cuenta_contra_si_misma(self):
        self._vender(4)
        reserva = self._vender(4)
        reserva.nombre_cliente = 'Ana Ruiz Corregido'
        reserva.full_clean()

    def test_una_reserva_cancelada_libera_su_panga(self):
        self._vender(4)
        cancelada = self._vender(4)
        cancelada.estado = Reserva.Estado.CANCELADA
        cancelada.save()

        Reserva(**datos_reserva(self.empresa, fecha=self.fecha, numero_personas=4,
                                estado=Reserva.Estado.PAGADA)).full_clean()

    def test_una_panga_marcada_fuera_reduce_el_cupo_de_ese_dia(self):
        grande = Embarcacion.objects.filter(empresa=self.empresa, capacidad_maxima=5).first()
        EmbarcacionNoDisponible.objects.create(
            empresa=self.empresa, fecha=self.fecha, embarcacion=grande, motivo='Motor'
        )
        self._vender(4)
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, fecha=self.fecha, numero_personas=4,
                                    estado=Reserva.Estado.PAGADA)).full_clean()


class CupoApiPorTamanoTests(ApiTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.fecha = date.today() + timedelta(days=10)

    def test_sin_personas_responde_como_antes(self):
        """Compatibilidad: nada que llame a la API vieja se puede romper."""
        cuerpo = self.client.get(f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}').json()
        self.assertTrue(cuerpo['disponible'])
        self.assertIsNone(cuerpo['motivo_no_disponible'])
        self.assertEqual(cuerpo['cupo_maximo'], CUPO_MAXIMO_DEFAULT)

    def test_un_grupo_de_cuatro_sin_pangas_grandes_libres(self):
        crear_reserva(self.empresa, fecha=self.fecha, numero_personas=4, estado=Reserva.Estado.PAGADA)
        crear_reserva(self.empresa, fecha=self.fecha, numero_personas=4, estado=Reserva.Estado.PAGADA)

        grande = self.client.get(
            f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=4').json()
        self.assertFalse(grande['disponible'])
        self.assertEqual(grande['motivo_no_disponible'], MOTIVO_SIN_PANGA)
        self.assertEqual(grande['proxima_disponible'], str(self.fecha + timedelta(days=1)))

        chico = self.client.get(
            f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2').json()
        self.assertTrue(chico['disponible'])
        self.assertIsNone(chico['motivo_no_disponible'])

    def test_un_dia_lleno_dice_lleno(self):
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(self.empresa, fecha=self.fecha, numero_personas=2, estado=Reserva.Estado.PAGADA)

        cuerpo = self.client.get(
            f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2').json()
        self.assertEqual(cuerpo['motivo_no_disponible'], MOTIVO_LLENO)

    def test_personas_que_no_es_numero_da_400(self):
        respuesta = self.client.get(
            f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=cuatro')
        self.assertEqual(respuesta.status_code, 400)

    def test_personas_fuera_del_rango_da_400(self):
        for valor in (0, MAX_PERSONAS + 1):
            with self.subTest(personas=valor):
                respuesta = self.client.get(
                    f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas={valor}')
                self.assertEqual(respuesta.status_code, 400)


class RevisarCupoTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.fecha = date.today() + timedelta(days=10)

    def _salida(self, **opciones):
        # revisar_cupo itera todas las Empresas y abre su propio scope.con_empresa
        # por cada una -- no es reentrante con el que EmpresaTestCase ya dejo
        # abierto para self.empresa (ver apps/testing.py y progress.md linea ~133).
        salida = StringIO()
        self._alcance.__exit__(None, None, None)
        try:
            call_command('revisar_cupo', stdout=salida, **opciones)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        return salida.getvalue()

    def test_no_reporta_nada_cuando_todos_los_dias_cierran(self):
        crear_reserva(self.empresa, fecha=self.fecha, numero_personas=4, estado=Reserva.Estado.PAGADA)
        self.assertNotIn(str(self.fecha), self._salida())

    def test_encuentra_un_dia_vendido_que_no_es_operable(self):
        """Tres grupos de 4 con solo dos pangas grandes: se vendio antes de que el
        motor supiera de tamanos y hay que resolverlo a mano.

        Se usa Reserva.objects.create sin full_clean a proposito: es exactamente la
        fila que este comando existe para encontrar.
        """
        for _ in range(3):
            Reserva.objects.create(**datos_reserva(
                self.empresa, fecha=self.fecha, numero_personas=4, estado=Reserva.Estado.PAGADA
            ))

        salida = self._salida()
        self.assertIn(str(self.fecha), salida)
        self.assertIn('4, 4, 4', salida)


class AgendaListaTests(EmpresaTestCase):
    """La agenda reparte lo vendido: solo lo que todavia se puede repartir."""

    def setUp(self):
        crear_flota(self.empresa)
        self.fecha = date.today() + timedelta(days=3)

    def test_lista_las_pagadas_y_las_asignadas(self):
        pagada = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA)
        asignada = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA)
        asignada.embarcacion = Embarcacion.objects.filter(empresa=self.empresa).first()
        asignada.estado = Reserva.Estado.ASIGNADA
        asignada.save()

        en_agenda = set(Agenda.por_repartir().values_list('pk', flat=True))

        self.assertEqual(en_agenda, {pagada.pk, asignada.pk})

    def test_no_lista_las_que_no_se_reparten(self):
        """Una cancelada no se reparte, una completada ya salio, y una
        pendiente_pago no es una reserva todavia."""
        crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.COMPLETADA)
        Reserva.objects.create(**datos_reserva(
            self.empresa, fecha=self.fecha, estado=Reserva.Estado.CANCELADA))
        Reserva.objects.create(**datos_reserva(
            self.empresa, fecha=self.fecha, estado=Reserva.Estado.PENDIENTE_PAGO))

        self.assertEqual(Agenda.por_repartir().count(), 0)

    def test_ordena_lo_que_sale_primero_primero(self):
        """Al reves que el listado de Reservas, que es un historial."""
        tarde = crear_reserva(self.empresa, fecha=self.fecha + timedelta(days=1),
                              estado=Reserva.Estado.PAGADA)
        temprano = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA)

        self.assertEqual(
            list(Agenda.por_repartir().values_list('pk', flat=True)),
            [temprano.pk, tarde.pk],
        )

    def test_no_lista_reservas_de_transporte_ni_bajo_demanda(self):
        servicio_transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Aeropuerto',
            slug='traslado-aeropuerto',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
        )
        reserva_transporte = Reserva.objects.create(
            empresa=self.empresa,
            servicio=servicio_transporte,
            fecha=self.fecha,
            hora=time(10, 0),
            numero_personas=2,
            nombre_cliente='Ana Pasajera',
            canal_origen='web',
            deslinde_aceptado=True,
            estado=Reserva.Estado.PAGADA,
        )
        self.assertNotIn(reserva_transporte.pk, Agenda.por_repartir().values_list('pk', flat=True))

    def test_detalle_transporte_inline_en_reserva_admin(self):
        from apps.bookings.admin import DetalleTransporteInline, ReservaAdmin
        self.assertIn(DetalleTransporteInline, ReservaAdmin.inlines)

    def test_agenda_admin_queryset_excluye_transporte(self):
        from django.test import RequestFactory
        from apps.bookings.admin import AgendaAdmin
        from apps.bookings.models import Agenda
        factory = RequestFactory()
        request = factory.get('/admin/bookings/agenda/')
        request.user = self.crear_jefe()
        servicio_transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado',
            slug='traslado-admin',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
        )
        reserva_transporte = Reserva.objects.create(
            empresa=self.empresa,
            servicio=servicio_transporte,
            fecha=self.fecha,
            hora=time(10, 0),
            numero_personas=2,
            nombre_cliente='Ana Pasajera',
            canal_origen='web',
            deslinde_aceptado=True,
            estado=Reserva.Estado.PAGADA,
        )
        admin_obj = AgendaAdmin(Agenda, None)
        qs = admin_obj.get_queryset(request)
        self.assertNotIn(reserva_transporte.pk, qs.values_list('pk', flat=True))


class TransicionDeAsignacionTests(EmpresaTestCase):
    """Poner la panga da el viaje por asignado; quitarla lo regresa.

    El capitan no entra en esto a proposito: se acordo que poner la panga baste,
    sabiendo que un viaje puede llegar a la salida sin capitan. La compensacion es
    el aviso en rojo de la agenda, no una validacion que frene el trabajo.
    """

    def setUp(self):
        crear_flota(self.empresa)
        self.panga = Embarcacion.objects.filter(empresa=self.empresa).first()
        self.capitan = Capitan.objects.create(
            empresa=self.empresa, nombre='Juan Perez', telefono='+5216121234567')
        self.fecha = date.today() + timedelta(days=3)

    def test_ponerle_panga_a_una_pagada_la_deja_asignada(self):
        reserva = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA)

        reserva.embarcacion = self.panga
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.ASIGNADA)

    def test_quitarle_la_panga_a_una_asignada_la_regresa_a_pagada(self):
        reserva = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA)
        reserva.embarcacion = self.panga
        reserva.save()

        reserva.embarcacion = None
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)

    def test_guardar_solo_la_embarcacion_tambien_mueve_el_estado(self):
        """El listado editable del admin puede guardar con update_fields; si
        `estado` no va en esa lista, el UPDATE no lo escribe y la fila queda
        diciendo `pagada` con una panga puesta."""
        reserva = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA)

        reserva.embarcacion = self.panga
        reserva.save(update_fields=['embarcacion'])

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.ASIGNADA)

    def test_el_capitan_solo_no_asigna_el_viaje(self):
        """Sin panga no hay viaje repartido, por mucho capitan que tenga."""
        reserva = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA)

        reserva.capitan = self.capitan
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)

    def test_una_completada_no_se_mueve(self):
        """Estados finales: los decide una persona, no un efecto secundario."""
        reserva = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.COMPLETADA)

        reserva.embarcacion = self.panga
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.COMPLETADA)

    def test_una_cancelada_no_se_mueve(self):
        reserva = Reserva.objects.create(**datos_reserva(
            self.empresa, fecha=self.fecha, estado=Reserva.Estado.CANCELADA))

        reserva.embarcacion = self.panga
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)

    def test_una_pendiente_de_pago_no_se_asigna_por_ponerle_panga(self):
        """Un checkout sin pagar no es un viaje que repartir."""
        reserva = Reserva.objects.create(**datos_reserva(
            self.empresa, fecha=self.fecha, estado=Reserva.Estado.PENDIENTE_PAGO))

        reserva.embarcacion = self.panga
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)


class UnaSalidaPorDiaTests(EmpresaTestCase):
    """Una panga hace un solo viaje al dia, y un capitan tambien.

    Las salidas son de 5 a 7am y el viaje dura de 6 a 7 horas, asi que escalonar
    dos salidas con la misma panga no existe. El repo decia lo contrario hasta
    esta tarea (ver backend/CLAUDE.md).
    """

    def setUp(self):
        crear_flota(self.empresa)
        self.panga = Embarcacion.objects.filter(empresa=self.empresa).first()
        self.capitan = Capitan.objects.create(
            empresa=self.empresa, nombre='Juan Perez', telefono='+5216121234567')
        self.fecha = date.today() + timedelta(days=3)

    def test_la_misma_panga_dos_veces_el_mismo_dia_se_rechaza(self):
        crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                      embarcacion=self.panga)

        otra = Reserva(**datos_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA))
        otra.embarcacion = self.panga
        with self.assertRaises(ValidationError) as ctx:
            otra.full_clean()

        self.assertIn('embarcacion', ctx.exception.message_dict)
        self.assertIn('una sola salida por dia', str(ctx.exception))

    def test_el_mismo_capitan_dos_veces_el_mismo_dia_se_rechaza(self):
        crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                      capitan=self.capitan)

        otra = Reserva(**datos_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA))
        otra.capitan = self.capitan
        with self.assertRaises(ValidationError) as ctx:
            otra.full_clean()

        self.assertIn('capitan', ctx.exception.message_dict)

    def test_la_misma_panga_en_dias_distintos_se_acepta(self):
        crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                      embarcacion=self.panga)

        otra = Reserva(**datos_reserva(self.empresa, fecha=self.fecha + timedelta(days=1),
                                       estado=Reserva.Estado.PAGADA))
        otra.embarcacion = self.panga
        otra.full_clean()

    def test_una_cancelada_suelta_su_panga(self):
        cancelada = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                                  embarcacion=self.panga)
        cancelada.estado = Reserva.Estado.CANCELADA
        cancelada.save()

        otra = Reserva(**datos_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA))
        otra.embarcacion = self.panga
        otra.full_clean()

    def test_editar_una_reserva_ya_asignada_no_choca_consigo_misma(self):
        reserva = crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                                embarcacion=self.panga)

        reserva.nombre_cliente = 'Ana Ruiz Corregido'
        reserva.full_clean()

    def test_una_reserva_sin_panga_no_choca_con_otra_sin_panga(self):
        """Dos viajes sin repartir el mismo dia son lo normal, no un choque."""
        crear_reserva(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA)

        Reserva(**datos_reserva(
            self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA)).full_clean()


class InlinesAdminOcupacionYComponentesTests(EmpresaTestCase):
    """Pruebas de permisos de los inlines ReservaOcupacionInline y ReservaPaqueteComponenteInline (Tarea 6.6)."""

    def setUp(self):
        super().setUp()
        from django.contrib.admin.sites import AdminSite
        from apps.bookings.admin import ReservaOcupacionInline, ReservaPaqueteComponenteInline
        self.site = AdminSite()
        self.ocupacion_inline = ReservaOcupacionInline(Reserva, self.site)
        self.componente_inline = ReservaPaqueteComponenteInline(Reserva, self.site)
        self.request = mock.Mock()

    def test_inlines_bloqueados_en_estado_pagado(self):
        r_pagada = crear_reserva(self.empresa, estado=Reserva.Estado.PAGADA)
        for inline in (self.ocupacion_inline, self.componente_inline):
            self.assertFalse(inline.has_add_permission(self.request, r_pagada))
            self.assertFalse(inline.has_change_permission(self.request, r_pagada))
            self.assertFalse(inline.has_delete_permission(self.request, r_pagada))

    def test_inlines_bloqueados_en_estado_asignada(self):
        r_asignada = crear_reserva(self.empresa, estado=Reserva.Estado.ASIGNADA)
        for inline in (self.ocupacion_inline, self.componente_inline):
            self.assertFalse(inline.has_add_permission(self.request, r_asignada))
            self.assertFalse(inline.has_change_permission(self.request, r_asignada))
            self.assertFalse(inline.has_delete_permission(self.request, r_asignada))

    def test_inlines_editables_en_pendiente_pago(self):
        r_pendiente = crear_reserva(self.empresa, estado=Reserva.Estado.PENDIENTE_PAGO)
        for inline in (self.ocupacion_inline, self.componente_inline):
            self.assertTrue(inline.has_add_permission(self.request, r_pendiente))
            self.assertTrue(inline.has_change_permission(self.request, r_pendiente))
            self.assertTrue(inline.has_delete_permission(self.request, r_pendiente))


class VentanaHorariaTest(EmpresaTestCase):
    def test_pesca_legacy_sin_servicio_valida_ventana_5_a_7(self):
        # 06:00 pasa
        r_ok = Reserva(**datos_reserva(self.empresa, servicio=None, hora=time(6, 0)))
        r_ok._validar_ventana_horaria()

        # 09:00 falla
        r_fail = Reserva(**datos_reserva(self.empresa, servicio=None, hora=time(9, 0)))
        with self.assertRaises(ValidationError) as ctx:
            r_fail._validar_ventana_horaria()
        self.assertIn('hora', ctx.exception.message_dict)

    def test_servicio_con_ventana_propia(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Tour Tarde',
            slug='tour-tarde',
            tipo_servicio='paseo',
            hora_apertura=time(14, 0),
            hora_cierre=time(18, 0),
        )
        # 15:00 pasa
        r_ok = Reserva(**datos_reserva(self.empresa, servicio=servicio, hora=time(15, 0)))
        r_ok.full_clean()

        # 06:00 falla
        r_fail = Reserva(**datos_reserva(self.empresa, servicio=servicio, hora=time(6, 0)))
        with self.assertRaises(ValidationError) as ctx:
            r_fail.full_clean()
        self.assertIn('hora', ctx.exception.message_dict)

    def test_servicio_sin_ventana_permite_cualquier_hora(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Libre',
            slug='traslado-libre',
            tipo_servicio='transporte',
            hora_apertura=None,
            hora_cierre=None,
        )
        # 22:00 pasa
        r_ok = Reserva(**datos_reserva(self.empresa, servicio=servicio, hora=time(22, 0)))
        r_ok.full_clean()


class TopePersonasTest(EmpresaTestCase):
    def test_pesca_legacy_tope_5(self):
        # 5 pasa
        r_5 = Reserva(**datos_reserva(self.empresa, servicio=None, numero_personas=5))
        r_5._validar_tope_personas()

        # 6 falla
        r_6 = Reserva(**datos_reserva(self.empresa, servicio=None, numero_personas=6))
        with self.assertRaises(ValidationError) as ctx:
            r_6._validar_tope_personas()
        self.assertIn('numero_personas', ctx.exception.message_dict)

    def test_servicio_con_capacidad_maxima_14(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Van Grande',
            slug='van-grande',
            tipo_servicio='transporte',
            capacidad_maxima=14,
        )
        # 14 pasa
        r_14 = Reserva(**datos_reserva(self.empresa, servicio=servicio, numero_personas=14))
        r_14.full_clean()

        # 15 falla
        r_15 = Reserva(**datos_reserva(self.empresa, servicio=servicio, numero_personas=15))
        with self.assertRaises(ValidationError) as ctx:
            r_15.full_clean()
        self.assertIn('numero_personas', ctx.exception.message_dict)

    def test_servicio_sin_capacidad_maxima_cae_en_default(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Servicio Sin Tope',
            slug='servicio-sin-tope',
            tipo_servicio='paseo',
            capacidad_maxima=None,
        )
        # 5 pasa
        r_5 = Reserva(**datos_reserva(self.empresa, servicio=servicio, numero_personas=5))
        r_5.full_clean()

        # 6 falla
        r_6 = Reserva(**datos_reserva(self.empresa, servicio=servicio, numero_personas=6))
        with self.assertRaises(ValidationError) as ctx:
            r_6.full_clean()
        self.assertIn('numero_personas', ctx.exception.message_dict)


class BajoDemandaCleanTest(EmpresaTestCase):
    def test_reserva_bajo_demanda_sin_panga_ni_cupo_pasa_con_deslinde(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Aeropuerto',
            slug='traslado-aeropuerto',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
        )
        # Nota: self.empresa no tiene pangas ni CupoDiario creados
        # Estado PAGADA (que ocupa cupo si estuviera activo)
        reserva = Reserva(
            empresa=self.empresa,
            servicio=servicio,
            fecha=date.today() + timedelta(days=5),
            hora=time(10, 0),
            numero_personas=4,
            nombre_cliente='Carlos Mora',
            telefono_cliente='+5216121112233',
            correo_cliente='carlos@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            deslinde_nombre='Carlos Mora',
            estado=Reserva.Estado.PAGADA,
        )
        reserva.full_clean()
        reserva.save()
        self.assertIsNotNone(reserva.pk)

    def test_reserva_bajo_demanda_web_exige_deslinde(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Aeropuerto',
            slug='traslado-aeropuerto',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
        )
        reserva = Reserva(
            empresa=self.empresa,
            servicio=servicio,
            fecha=date.today() + timedelta(days=5),
            hora=time(10, 0),
            numero_personas=4,
            nombre_cliente='Carlos Mora',
            telefono_cliente='+5216121112233',
            correo_cliente='carlos@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=False,
            estado=Reserva.Estado.PAGADA,
        )
        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()
        self.assertIn('deslinde_aceptado', ctx.exception.message_dict)

    def test_reserva_bajo_demanda_ignora_cupo_diario_lleno(self):
        fecha = date.today() + timedelta(days=5)
        # Cerramos el cupo diario para esa fecha
        CupoDiario.objects.create(empresa=self.empresa, fecha=fecha, cupo_maximo=1)
        crear_reserva(self.empresa, fecha=fecha, estado=Reserva.Estado.PAGADA)

        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Aeropuerto',
            slug='traslado-aeropuerto',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
        )
        reserva = Reserva(
            empresa=self.empresa,
            servicio=servicio,
            fecha=fecha,
            hora=time(10, 0),
            numero_personas=4,
            nombre_cliente='Carlos Mora',
            telefono_cliente='+5216121112233',
            correo_cliente='carlos@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            deslinde_nombre='Carlos Mora',
            estado=Reserva.Estado.PAGADA,
        )
        # Debe pasar sin lanzar ValidationError de cupo
        reserva.full_clean()
        reserva.save()
        self.assertIsNotNone(reserva.pk)


class DetalleTransporteTest(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.servicio_transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado',
            slug='traslado',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
        )
        self.reserva = Reserva.objects.create(
            **datos_reserva(
                self.empresa,
                servicio=self.servicio_transporte,
                fecha=date(2026, 10, 1),
                hora=time(10, 0),
            )
        )
        self.punto = PuntoEncuentro.objects.create(
            empresa=self.empresa,
            nombre='Hotel Sol',
            zona=Zona.CENTRO,
        )

    def test_xor_punto_y_direccion_ambos_falla(self):
        dt = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            punto_encuentro=self.punto,
            direccion_personalizada='Av. Principal 123',
            fecha_regreso=date(2026, 10, 5),
        )
        with self.assertRaises(ValidationError) as ctx:
            dt.clean()
        self.assertIn('Elige un punto de encuentro del catálogo o escribe una dirección, no ambos ni ninguno.', str(ctx.exception))

    def test_xor_punto_y_direccion_ninguno_falla(self):
        dt = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            punto_encuentro=None,
            direccion_personalizada='',
            fecha_regreso=date(2026, 10, 5),
        )
        with self.assertRaises(ValidationError) as ctx:
            dt.clean()
        self.assertIn('Elige un punto de encuentro del catálogo o escribe una dirección, no ambos ni ninguno.', str(ctx.exception))

    def test_zona_distinta_a_la_del_punto_encuentro_falla(self):
        dt = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            punto_encuentro=self.punto,
            zona=Zona.PERIFERIA,
            fecha_regreso=date(2026, 10, 5),
        )
        with self.assertRaises(ValidationError) as ctx:
            dt.clean()
        self.assertIn('zona', ctx.exception.message_dict)

    def test_punto_encuentro_otra_empresa_falla(self):
        from apps.tenancy.models import Empresa
        otra_empresa = Empresa.objects.create(sede=self.empresa.sede, nombre='Otra', slug='otra')
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                punto_ajeno = PuntoEncuentro.objects.create(
                    empresa=otra_empresa,
                    nombre='Hotel Ajeno',
                    zona=Zona.CENTRO,
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        dt = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            punto_encuentro=punto_ajeno,
            fecha_regreso=date(2026, 10, 5),
        )
        with self.assertRaises(ValidationError) as ctx:
            dt.clean()
        self.assertIn('punto_encuentro', ctx.exception.message_dict)

    def test_redondo_actividad_sin_zona_ni_punto_falla(self):
        dt = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            direccion_personalizada='Calle 5 #10',
            zona='',
        )
        with self.assertRaises(ValidationError) as ctx:
            dt.clean()
        self.assertIn('zona', ctx.exception.message_dict)

    def test_redondo_aeropuerto_sin_fecha_regreso_falla(self):
        dt = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            punto_encuentro=self.punto,
            fecha_regreso=None,
        )
        with self.assertRaises(ValidationError) as ctx:
            dt.clean()
        self.assertIn('fecha_regreso', ctx.exception.message_dict)

    def test_no_aeropuerto_con_fecha_regreso_falla(self):
        dt = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            punto_encuentro=self.punto,
            fecha_regreso=date(2026, 10, 5),
        )
        with self.assertRaises(ValidationError) as ctx:
            dt.clean()
        self.assertIn('fecha_regreso', ctx.exception.message_dict)

    def test_fecha_regreso_anterior_o_igual_a_llegada_falla(self):
        # Misma fecha que reserva.fecha (2026-10-01)
        dt = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            punto_encuentro=self.punto,
            fecha_regreso=date(2026, 10, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            dt.clean()
        self.assertIn('fecha_regreso', ctx.exception.message_dict)

        # Fecha anterior
        dt.fecha_regreso = date(2026, 9, 30)
        with self.assertRaises(ValidationError) as ctx:
            dt.clean()
        self.assertIn('fecha_regreso', ctx.exception.message_dict)

    def test_redondo_aeropuerto_valido_pasa(self):
        dt = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            punto_encuentro=self.punto,
            fecha_regreso=date(2026, 10, 5),
        )
        dt.full_clean()
        dt.save()
        self.assertIsNotNone(dt.pk)

    def test_zona_efectiva(self):
        # 1. Redondo actividad con punto de encuentro (hotel en Zona.CENTRO)
        dt1 = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            punto_encuentro=self.punto,
        )
        self.assertEqual(dt1.zona_efectiva(), Zona.CENTRO)

        # 2. Redondo actividad con direccion personalizada y zona periferia
        dt2 = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            direccion_personalizada='Casa particular #44',
            zona=Zona.PERIFERIA,
        )
        self.assertEqual(dt2.zona_efectiva(), Zona.PERIFERIA)

        # 3. Redondo aeropuerto -> ''
        dt3 = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            punto_encuentro=self.punto,
            fecha_regreso=date(2026, 10, 5),
        )
        self.assertEqual(dt3.zona_efectiva(), '')

        # 4. Recepcion aeropuerto -> ''
        dt4 = DetalleTransporte(
            reserva=self.reserva,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            punto_encuentro=self.punto,
        )
        self.assertEqual(dt4.zona_efectiva(), '')






class TrasladoCheckoutTest(ApiTestCase):
    def setUp(self):
        import uuid
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado', slug='traslado',
            tipo_servicio='transporte', estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta', capacidad_maxima=14,
        )
        self.punto = PuntoEncuentro.objects.create(
            empresa=self.empresa, nombre='Hotel Sol', zona=Zona.CENTRO,
        )
        self.payload = {
            'checkout_id': str(uuid.uuid4()), 'servicio': self.servicio.slug,
            'tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
            'punto_encuentro': self.punto.pk, 'zona': Zona.PERIFERIA,
            'fecha': (date.today() + timedelta(days=10)).isoformat(), 'hora': '14:00',
            'numero_personas': 12, 'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567', 'correo_cliente': 'ana@example.com',
            'deslinde_aceptado': True, 'deslinde_nombre': 'Ana Ruiz',
            'moneda': 'MXN', 'forma_pago': 'completo',
        }

    def post(self, **changes):
        return self.client.post(f'/api/{self.empresa.slug}/reservas/',
                                {**self.payload, **changes}, content_type='application/json')

    def test_crea_reserva_y_detalle_con_zona_del_catalogo(self):
        response = self.post(precio_total='0.01', precio_calculado='0.01')
        self.assertEqual(response.status_code, 201, response.data)
        reserva = Reserva.objects.get(pk=response.data['id'])
        self.assertEqual(reserva.servicio, self.servicio)
        self.assertEqual(reserva.empresa, self.empresa)
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
        self.assertEqual(reserva.canal_origen, 'web')
        self.assertEqual(reserva.forma_pago, 'completo')
        self.assertEqual(reserva.deslinde_version, DESLINDE_VERSION)
        self.assertIsNotNone(reserva.deslinde_aceptado_en)
        self.assertEqual(reserva.detalle_transporte.zona, Zona.CENTRO)
        self.assertIsNone(reserva.detalle_transporte.precio_calculado)
        self.assertIsNone(reserva.detalle_transporte.numero_personas)
        self.assertIsNone(reserva.precio_total)
        self.assertFalse(reserva.ocupaciones.exists())

    def test_direccion_propia_y_zona(self):
        response = self.post(punto_encuentro=None, direccion_personalizada='Casa 123')
        self.assertEqual(response.status_code, 201, response.data)
        detalle = DetalleTransporte.objects.get(reserva_id=response.data['id'])
        self.assertEqual(detalle.direccion_personalizada, 'Casa 123')
        self.assertEqual(detalle.zona, Zona.PERIFERIA)

    def test_xor_y_zona_requerida_sin_reserva_parcial(self):
        for cambios in ({'direccion_personalizada': 'Casa 123'},
                        {'punto_encuentro': None},
                        {'punto_encuentro': None, 'direccion_personalizada': 'Casa 123', 'zona': ''}):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.post(**cambios).status_code, 400)
                self.assertFalse(Reserva.objects.exists())

    def test_deslinde_y_capacidad(self):
        for changes in ({'deslinde_aceptado': False}, {'deslinde_nombre': ''},
                        {'numero_personas': 15}):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(**changes).status_code, 400)
        for field in ('deslinde_nombre', 'deslinde_aceptado'):
            value = self.payload.pop(field)
            self.assertEqual(self.post().status_code, 400)
            self.payload[field] = value
        self.assertFalse(Reserva.objects.exists())

    def test_fecha_regreso_segun_tipo(self):
        for changes in (
            {'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO},
            {'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO, 'fecha_regreso': self.payload['fecha']},
            {'fecha_regreso': (date.today() + timedelta(days=11)).isoformat()},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.post(**changes).status_code, 400)
                self.assertFalse(Reserva.objects.exists())
        response = self.post(tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                             fecha_regreso=(date.today() + timedelta(days=11)).isoformat())
        self.assertEqual(response.status_code, 201, response.data)

    def test_upsert_actualiza_detalle_y_revierte_cambios_invalidos(self):
        first = self.post()
        self.assertEqual(first.status_code, 201, first.data)
        response = self.post(punto_encuentro=None, direccion_personalizada='Casa nueva', numero_personas=8)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['id'], first.data['id'])
        self.assertEqual(self.post(direccion_personalizada='Ambos', numero_personas=4).status_code, 400)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.numero_personas, 8)
        self.assertEqual(DetalleTransporte.objects.count(), 1)
        self.assertEqual(reserva.detalle_transporte.direccion_personalizada, 'Casa nueva')

    def test_catalogo_inactivo_rechazado(self):
        self.punto.activo = False
        self.punto.save()
        self.assertEqual(self.post().status_code, 400)
        self.servicio.activo = False
        self.servicio.save()
        self.assertEqual(self.post().status_code, 400)
        self.assertFalse(Reserva.objects.exists())

    def test_catalogo_empresa_ajena_rechazado(self):
        from apps.tenancy.models import Empresa
        otra = Empresa.objects.create(sede=self.sede, nombre='Otra', slug='otra')
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra):
                punto = PuntoEncuentro.objects.create(empresa=otra, nombre='Otro hotel', zona=Zona.CENTRO)
                servicio = Servicio.objects.create(
                    empresa=otra, nombre='Ajeno', slug='ajeno', tipo_servicio='transporte',
                    estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.assertEqual(self.post(punto_encuentro=punto.pk).status_code, 400)
        self.assertEqual(self.post(servicio=servicio.slug).status_code, 400)
        self.assertFalse(Reserva.objects.exists())

    @mock.patch('apps.bookings.views.verificar_turnstile')
    def test_captcha_solo_al_crear(self, verificar):
        verificar.return_value = False
        self.assertEqual(self.post(captcha_token='invalido').status_code, 403)
        verificar.return_value = True
        self.assertEqual(self.post(captcha_token='valido').status_code, 201)
        verificar.reset_mock()
        self.assertEqual(self.post(numero_personas=8).status_code, 200)
        verificar.assert_not_called()

    def test_reenvio_sin_servicio_o_con_pesca_no_omite_validacion_del_traslado(self):
        self.assertEqual(self.post().status_code, 201)
        self.payload.pop('servicio')
        self.assertEqual(self.post().status_code, 400)
        pesca = Servicio.objects.create(empresa=self.empresa, nombre='Pesca', slug='pesca')
        self.assertEqual(self.post(servicio=pesca.slug).status_code, 400)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.servicio, self.servicio)
        self.assertEqual(DetalleTransporte.objects.count(), 1)

    def test_ref_se_conserva_al_reenviar(self):
        vendedora = Vendedora.objects.create(
            usuario=User.objects.create_user('maria'), empresa=self.empresa, codigo='maria',
        )
        response = self.post(ref='maria')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.post().status_code, 200)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.vendedora, vendedora)
        self.assertIsNotNone(reserva.vendedora_asignada_en)


class ValidacionReservaOrdenTest(OperadorTestCase):
    def setUp(self):
        from apps.bookings.models import Orden
        from apps.fleet.models import Paquete
        from apps.tenancy.models import Empresa, Sede

        self.fecha = date.today() + timedelta(days=30)
        self.sede = Sede.objects.create(nombre='Sede Clean Orden', slug='sede-clean-orden')
        self.empresa_pesca = Empresa.objects.create(
            sede=self.sede, nombre='Pesca Clean Orden', slug='pesca-clean-orden',
        )
        self.empresa_transporte = Empresa.objects.create(
            sede=self.sede, nombre='Transporte Clean Orden', slug='transporte-clean-orden',
        )
        self.pesca = Servicio.objects.create(
            empresa=self.empresa_pesca, nombre='Pesca Clean', slug='pesca-clean',
            tipo_servicio='pesca', estrategia_cupo='por_recurso_dia',
        )
        self.transporte = Servicio.objects.create(
            empresa=self.empresa_transporte, nombre='Transporte Clean', slug='transporte-clean',
            tipo_servicio='transporte', estrategia_cupo='bajo_demanda', capacidad_maxima=14,
        )
        self.hospedaje = Servicio.objects.create(
            empresa=self.empresa_pesca, nombre='Hospedaje Clean', slug='hospedaje-clean',
            tipo_servicio='hospedaje', estrategia_cupo='por_noche', capacidad_maxima=4,
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa_pesca,
            nombre='Paquete Clean Orden', slug='paquete-clean-orden',
            precio_ancla=Decimal('5000.00'),
        )
        self.paquete_ajeno = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa_transporte,
            nombre='Paquete Ajeno Clean', slug='paquete-ajeno-clean',
            precio_ancla=Decimal('5000.00'),
        )
        self.orden = Orden.objects.create(
            sede=self.sede, empresa_lider=self.empresa_pesca, paquete=self.paquete,
            nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com',
        )

    def _reserva(self, empresa, servicio, **extra):
        return Reserva(
            empresa=empresa, servicio=servicio, orden=self.orden,
            fecha=self.fecha, hora=time(6, 0), numero_personas=2,
            nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True, estado=Reserva.Estado.PAGADA, **extra,
        )

    def _clean_bajo_empresa(self, reserva):
        self._alcance_operador.__exit__(None, None, None)
        try:
            with scope.con_empresa(reserva.empresa):
                reserva.clean()
        finally:
            self._alcance_operador = scope.como_operador_plataforma()
            self._alcance_operador.__enter__()

    @mock.patch('apps.bookings.models._validar_cupo_hospedaje')
    @mock.patch('apps.bookings.models._validar_cupo_de_paquete')
    @mock.patch('apps.bookings.models.validar_cupo_diario')
    def test_lider_con_paquete_valida_solo_cupo_de_pesca(
        self, validar_diario, validar_paquete, validar_hospedaje,
    ):
        reserva = self._reserva(self.empresa_pesca, self.pesca, paquete=self.paquete)

        self._clean_bajo_empresa(reserva)

        validar_diario.assert_called_once_with(
            self.fecha, 2, self.empresa_pesca,
            excluir_pk=None, estrategia_cupo='por_recurso_dia', servicio_id=self.pesca.pk,
        )
        validar_paquete.assert_not_called()
        validar_hospedaje.assert_not_called()

    @mock.patch('apps.bookings.models._validar_cupo_hospedaje')
    @mock.patch('apps.bookings.models._validar_cupo_de_paquete')
    @mock.patch('apps.bookings.models.validar_cupo_diario')
    def test_transporte_bajo_demanda_no_valida_cupo(
        self, validar_diario, validar_paquete, validar_hospedaje,
    ):
        reserva = self._reserva(self.empresa_transporte, self.transporte)

        self._clean_bajo_empresa(reserva)

        validar_diario.assert_not_called()
        validar_paquete.assert_not_called()
        validar_hospedaje.assert_not_called()

    @mock.patch('apps.bookings.models._validar_cupo_hospedaje')
    @mock.patch('apps.bookings.models._validar_cupo_de_paquete')
    @mock.patch('apps.bookings.models.validar_cupo_diario')
    def test_hospedaje_conserva_validacion_del_rango_de_noches(
        self, validar_diario, validar_paquete, validar_hospedaje,
    ):
        reserva = self._reserva(
            self.empresa_pesca, self.hospedaje,
            fecha_salida=self.fecha + timedelta(days=3),
        )

        self._clean_bajo_empresa(reserva)

        validar_hospedaje.assert_called_once_with(reserva)
        validar_diario.assert_not_called()
        validar_paquete.assert_not_called()

    @mock.patch('apps.bookings.models.validar_cupo_diario')
    def test_orden_no_relaja_consistencia_del_servicio(self, validar_diario):
        reserva = self._reserva(self.empresa_pesca, self.transporte)

        with self.assertRaises(ValidationError) as ctx:
            self._clean_bajo_empresa(reserva)

        self.assertIn('servicio', ctx.exception.message_dict)

    @mock.patch('apps.bookings.models._validar_cupo_de_paquete')
    @mock.patch('apps.bookings.models.validar_cupo_diario')
    def test_orden_no_relaja_consistencia_del_paquete(self, validar_diario, validar_paquete):
        reserva = self._reserva(
            self.empresa_pesca, self.pesca, paquete=self.paquete_ajeno,
        )

        with self.assertRaises(ValidationError) as ctx:
            self._clean_bajo_empresa(reserva)

        self.assertIn('paquete', ctx.exception.message_dict)


class OrdenModelTest(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        from apps.fleet.models import Paquete
        from apps.tenancy.models import Empresa
        self.sede = self.empresa.sede
        self.otra_empresa = Empresa.objects.create(
            sede=self.sede, nombre='Otra', slug='otra-empresa',
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Test',
            slug='paquete-test',
            precio_ancla=Decimal('5000.00'),
        )

    def test_orden_creacion_valida(self):
        from apps.bookings.models import Orden
        orden = Orden.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            paquete=self.paquete,
            nombre_cliente='Juan Perez',
            telefono_cliente='1234567890',
            correo_cliente='juan@example.com',
            forma_pago=Reserva.FormaPago.COMPLETO,
        )
        self.assertEqual(orden.estado, Orden.Estado.ARMANDO)
        self.assertEqual(orden.moneda, Reserva.Moneda.MXN)

    def test_forma_pago_anticipo_falla(self):
        from apps.bookings.models import Orden
        orden = Orden(
            sede=self.sede,
            empresa_lider=self.empresa,
            paquete=self.paquete,
            nombre_cliente='Juan Perez',
            telefono_cliente='1234567890',
            correo_cliente='juan@example.com',
            forma_pago=Reserva.FormaPago.ANTICIPO,
        )
        with self.assertRaises(ValidationError) as ctx:
            orden.clean()
        self.assertIn('forma_pago', ctx.exception.message_dict)

    def test_empresa_lider_distinta_al_paquete_falla(self):
        from apps.bookings.models import Orden
        orden = Orden(
            sede=self.sede,
            empresa_lider=self.otra_empresa,
            paquete=self.paquete,
            nombre_cliente='Juan Perez',
            telefono_cliente='1234567890',
            correo_cliente='juan@example.com',
            forma_pago=Reserva.FormaPago.COMPLETO,
        )
        with self.assertRaises(ValidationError) as ctx:
            orden.clean()
        self.assertIn('empresa_lider', ctx.exception.message_dict)

    def test_transiciones_validas_e_invalidas(self):
        from apps.bookings.models import Orden
        orden = Orden.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            paquete=self.paquete,
            nombre_cliente='Juan Perez',
            telefono_cliente='1234567890',
            correo_cliente='juan@example.com',
        )
        with self.assertRaises(ValidationError):
            orden.transicionar(Orden.Estado.CAPTURADA)

        orden.transicionar(Orden.Estado.AUTORIZANDO)
        self.assertEqual(orden.estado, Orden.Estado.AUTORIZANDO)

        orden.transicionar(Orden.Estado.CAPTURADA)
        self.assertEqual(orden.estado, Orden.Estado.CAPTURADA)

        with self.assertRaises(ValidationError):
            orden.transicionar(Orden.Estado.CANCELADA)

        orden_cancelada = Orden.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            paquete=self.paquete,
            nombre_cliente='Juan Perez',
            telefono_cliente='1234567890',
            correo_cliente='juan@example.com',
        )
        orden_cancelada.transicionar(Orden.Estado.CANCELADA)
        with self.assertRaises(ValidationError):
            orden_cancelada.transicionar(Orden.Estado.ARMANDO)

    def test_reserva_orden_fk(self):
        from apps.bookings.models import Orden
        orden = Orden.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            paquete=self.paquete,
            nombre_cliente='Juan Perez',
            telefono_cliente='1234567890',
            correo_cliente='juan@example.com',
        )
        reserva = Reserva.objects.create(
            **datos_reserva(
                self.empresa,
                orden=orden,
                paquete=self.paquete,
            )
        )
        self.assertEqual(reserva.orden, orden)
        self.assertIn(reserva, orden.reservas.all())

    def test_orden_crea_n_reservas_mismo_deslinde_y_full_clean_pasa(self):
        import uuid
        from apps.bookings.models import DESLINDE_VERSION, Orden
        from apps.fleet.enums import TipoTraslado
        from apps.fleet.models import PaqueteServicio, Servicio, TransporteTarifa

        self.paquete.permite_anticipo = False
        self.paquete.save(update_fields=['permite_anticipo'])

        self._alcance.__exit__(None, None, None)
        try:
            with scope.como_operador_plataforma():
                servicio_transporte = Servicio.objects.create(
                    empresa=self.otra_empresa,
                    nombre='Traslado Orden',
                    slug='traslado-orden',
                    tipo_servicio='transporte',
                    estrategia_cupo='bajo_demanda',
                    estrategia_precio='por_ruta',
                )
                TransporteTarifa.objects.create(
                    empresa=self.otra_empresa,
                    tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                    personas_min=1,
                    personas_max=4,
                    precio=Decimal('2000.00'),
                )
                servicio_pesca = Servicio.objects.create(
                    empresa=self.empresa,
                    nombre='Pesca Orden Test',
                    slug='pesca-orden-test',
                    tipo_servicio='pesca',
                    estrategia_cupo='por_recurso_dia',
                    precio_base=Decimal('3000.00'),
                )
                PaqueteServicio.objects.create(paquete=self.paquete, servicio=servicio_pesca, orden=1)
                PaqueteServicio.objects.create(paquete=self.paquete, servicio=servicio_transporte, orden=2)

            payload = {
                'checkout_id': str(uuid.uuid4()),
                'paquete': self.paquete.slug,
                'nombre_cliente': 'Juan Perez',
                'telefono_cliente': '1234567890',
                'correo_cliente': 'juan@example.com',
                'deslinde_aceptado': True,
                'deslinde_nombre': 'Juan Perez',
                'fecha': (date.today() + timedelta(days=15)).isoformat(),
                'hora': '07:00:00',
                'componentes': [
                    {'servicio': servicio_pesca.slug, 'numero_personas': 2},
                    {'servicio': servicio_transporte.slug, 'numero_personas': 2},
                ],
                'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
                'direccion_personalizada': 'Calle Marina 123',
                'fecha_regreso': (date.today() + timedelta(days=17)).isoformat(),
            }
            res = self.client.post(f'/api/{self.sede.slug}/ordenes/', payload, content_type='application/json')
            self.assertEqual(res.status_code, 201)
            data = res.json()
            self.assertIn('orden_id', data)

            with scope.como_operador_plataforma():
                orden_creada = Orden.objects.get(pk=data['orden_id'])
                reservas = list(orden_creada.reservas.all().order_by('id'))
                self.assertGreaterEqual(len(reservas), 2)

                timestamp_base = reservas[0].deslinde_aceptado_en
                ip_base = reservas[0].deslinde_ip
                for r in reservas:
                    self.assertTrue(r.deslinde_aceptado)
                    self.assertEqual(r.deslinde_nombre, 'Juan Perez')
                    self.assertEqual(r.deslinde_version, DESLINDE_VERSION)
                    self.assertEqual(r.deslinde_version, '2026-09-11')
                    self.assertIsNotNone(r.deslinde_aceptado_en)
                    self.assertEqual(r.deslinde_aceptado_en, timestamp_base)
                    self.assertIsNotNone(r.deslinde_ip)
                    self.assertEqual(r.deslinde_ip, ip_base)

            # full_clean() pasa en cada reserva bajo su propia empresa
            for r in reservas:
                with scope.con_empresa(r.empresa):
                    r.full_clean()
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()


class ConfirmacionComponenteOrdenTest(OperadorTestCase):
    def setUp(self):
        from apps.bookings.models import Orden
        from apps.fleet.models import Paquete, PaqueteServicio, Recurso
        from apps.tenancy.models import Empresa, Sede

        self.fecha = date.today() + timedelta(days=30)
        self.sede = Sede.objects.create(nombre='Sede Orden Cupo', slug='sede-orden-cupo')
        self.empresa_pesca = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Pesca', slug='empresa-pesca-orden',
        )
        self.empresa_transporte = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Transporte', slug='empresa-transporte-orden',
        )
        self.pesca = Servicio.objects.create(
            empresa=self.empresa_pesca, nombre='Pesca Orden', slug='pesca-orden',
            tipo_servicio='pesca', estrategia_cupo='por_recurso_dia',
        )
        self.transporte = Servicio.objects.create(
            empresa=self.empresa_transporte, nombre='Transporte Orden', slug='transporte-orden',
            tipo_servicio='transporte', estrategia_cupo='bajo_demanda',
        )
        self.hospedaje = Servicio.objects.create(
            empresa=self.empresa_pesca, nombre='Hospedaje Orden', slug='hospedaje-orden',
            tipo_servicio='hospedaje', estrategia_cupo='por_noche',
        )
        self.habitacion = Recurso.objects.create(
            empresa=self.empresa_pesca, servicio=self.hospedaje,
            nombre='Habitacion Orden', capacidad_maxima=4,
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa_pesca,
            nombre='Paquete Orden Cupo', slug='paquete-orden-cupo',
            precio_ancla=Decimal('5000.00'),
        )
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.pesca, orden=1)
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.transporte, orden=2)
        self.orden = Orden.objects.create(
            sede=self.sede, empresa_lider=self.empresa_pesca, paquete=self.paquete,
            nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com',
        )
        crear_flota(self.empresa_pesca)

    def _reserva(self, empresa, servicio, **extra):
        return Reserva.objects.create(
            empresa=empresa, servicio=servicio, orden=self.orden,
            fecha=self.fecha, hora=time(6, 0), numero_personas=2,
            nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True, **extra,
        )

    def _confirmar_bajo_empresa(self, reserva):
        from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar

        self._alcance_operador.__exit__(None, None, None)
        try:
            with scope.con_empresa(reserva.empresa):
                reservar_cupo_al_confirmar(reserva)
        finally:
            self._alcance_operador = scope.como_operador_plataforma()
            self._alcance_operador.__enter__()

    def test_pesca_lider_reserva_solo_su_servicio(self):
        reserva = self._reserva(self.empresa_pesca, self.pesca, paquete=self.paquete)
        self._confirmar_bajo_empresa(reserva)

        componente = reserva.componentes.get()
        self.assertEqual(componente.servicio, self.pesca)
        self.assertEqual(componente.empresa, self.empresa_pesca)
        self.assertEqual(componente.estado_cupo, componente.EstadoCupo.OK)

    def test_transporte_no_toca_inventario_y_crea_componente(self):
        reserva = self._reserva(self.empresa_transporte, self.transporte)
        self._confirmar_bajo_empresa(reserva)

        self.assertFalse(reserva.ocupaciones.exists())
        componente = reserva.componentes.get()
        self.assertEqual(componente.servicio, self.transporte)
        self.assertEqual(componente.empresa, self.empresa_transporte)
        self.assertEqual(componente.estado_cupo, componente.EstadoCupo.OK)

    def test_pesca_llena_lanza_sin_cupo(self):
        from apps.bookings.cupo import SinCupoError
        CupoDiario.objects.create(
            empresa=self.empresa_pesca, fecha=self.fecha, cupo_maximo=0,
        )
        reserva = self._reserva(self.empresa_pesca, self.pesca, paquete=self.paquete)

        with self.assertRaises(SinCupoError):
            self._confirmar_bajo_empresa(reserva)
        self.assertFalse(reserva.componentes.exists())

    def test_hospedaje_de_orden_crea_ocupacion_y_componente(self):
        reserva = self._reserva(
            self.empresa_pesca, self.hospedaje,
            fecha_salida=self.fecha + timedelta(days=2),
        )
        self._confirmar_bajo_empresa(reserva)

        self.assertTrue(reserva.ocupaciones.filter(recurso=self.habitacion).exists())
        componente = reserva.componentes.get()
        self.assertEqual(componente.servicio, self.hospedaje)
        self.assertEqual(componente.empresa, self.empresa_pesca)
        self.assertEqual(componente.estado_cupo, componente.EstadoCupo.OK)



class OrdenAdminTests(TestCase):
    def setUp(self):
        from apps.bookings.models import Orden
        from apps.fleet.models import Paquete
        from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede

        call_command('setup_roles', stdout=StringIO())
        with scope.como_operador_plataforma():
            sede = Sede.objects.create(nombre='Admin Orden', slug='admin-orden')
            self.a = Empresa.objects.create(sede=sede, nombre='A', slug='admin-a')
            self.b = Empresa.objects.create(sede=sede, nombre='B', slug='admin-b')
            otra_sede = Sede.objects.create(nombre='Otra sede', slug='admin-otra')
            otra = Empresa.objects.create(sede=otra_sede, nombre='C', slug='admin-c')
            self.ordenes = []
            for empresa in (self.a, otra):
                paquete = Paquete.objects.create(
                    sede=empresa.sede, empresa_lider=empresa, nombre='Paquete admin',
                    slug=f'paquete-{empresa.slug}', precio_ancla=Decimal('350.00'),
                )
                self.ordenes.append(Orden.objects.create(
                    sede=empresa.sede, empresa_lider=empresa, paquete=paquete,
                    nombre_cliente=f'Cliente {empresa.slug}', telefono_cliente='+5216121234567',
                    correo_cliente='cliente@example.com',
                ))
            self.orden = self.ordenes[0]
            self.reservas = [Reserva.objects.create(**datos_reserva(
                empresa, orden=self.orden, monto_pagado=monto,
            )) for empresa, monto in ((self.a, Decimal('100.00')), (self.b, Decimal('250.00')))]
        self.usuarios = {}
        for grupo in ('Vendedora', 'Jefe', 'OperadorPlataforma'):
            user = User.objects.create_user(username=f'orden-{grupo}', is_staff=True)
            user.groups.add(Group.objects.get(name=grupo))
            if grupo != 'OperadorPlataforma':
                MembresiaEmpresa.objects.create(user=user, empresa=self.b, rol=(
                    MembresiaEmpresa.Rol.JEFE if grupo == 'Jefe' else MembresiaEmpresa.Rol.VENDEDORA
                ))
            self.usuarios[grupo] = user

    def test_admin_y_sidebar_abren_para_los_tres_roles(self):
        for rol, user in self.usuarios.items():
            with self.subTest(rol=rol):
                self.client.force_login(user)
                for url in ('/admin/', '/admin/bookings/orden/'):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotContains(response, 'Traceback')
                    self.assertContains(response, '/admin/bookings/orden/')
                self.assertContains(response, self.orden.nombre_cliente)
                if rol != 'OperadorPlataforma':
                    self.assertNotContains(response, self.ordenes[1].nombre_cliente)
                else:
                    self.assertContains(response, self.ordenes[1].nombre_cliente)
                self.assertEqual('cancelar_orden' in response.context['cl'].model_admin.get_actions(
                    response.wsgi_request), rol != 'Vendedora')

    def test_vendedora_detalle_total_y_componentes_cruzan_empresas(self):
        from django.db import connection
        self.client.force_login(self.usuarios['Vendedora'])
        response = self.client.get(f'/admin/bookings/orden/{self.orden.pk}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_change_permission'])
        self.assertFalse(response.context['has_add_permission'])
        self.assertFalse(response.context['has_delete_permission'])
        for reserva in self.reservas:
            self.assertContains(response, reverse('admin:bookings_reserva_change', args=[reserva.pk]))
        self.assertContains(response, '100.00')
        self.assertContains(response, '250.00')
        with scope.con_empresa(self.b):
            if connection.vendor == 'postgresql':
                self.assertEqual(self.orden.reservas.count(), 1)
            self.assertEqual(response.context['adminform'].model_admin.total(self.orden), Decimal('350.00'))
        self.assertEqual(self.client.post(
            f'/admin/bookings/orden/{self.orden.pk}/change/', {'estado': 'cancelada'},
        ).status_code, 403)
        self.assertEqual(self.client.get('/admin/bookings/orden/add/').status_code, 403)
        self.assertEqual(self.client.get(
            f'/admin/bookings/orden/{self.orden.pk}/delete/',
        ).status_code, 403)
        self.assertEqual(self.client.get(
            f'/admin/bookings/orden/{self.ordenes[1].pk}/change/',
        ).status_code, 302)

    def test_vendedora_no_puede_forzar_cancelacion(self):
        from django.contrib import admin
        from django.core.exceptions import PermissionDenied
        from django.test import RequestFactory
        from apps.bookings.models import Orden
        self.client.force_login(self.usuarios['Vendedora'])
        with mock.patch('apps.payments.ordenes.revertir_orden') as revertir:
            self.client.post('/admin/bookings/orden/', {
                'action': 'cancelar_orden', '_selected_action': [self.orden.pk],
            })
            request = RequestFactory().post('/admin/bookings/orden/')
            request.user = self.usuarios['Vendedora']
            with self.assertRaises(PermissionDenied):
                admin.site._registry[Orden].cancelar_orden(request, Orden.objects.none())
            revertir.assert_not_called()

    def test_jefe_y_operador_cancelan_con_servicio_real(self):
        from apps.bookings.models import Orden
        from apps.payments import ordenes
        for rol in ('Jefe', 'OperadorPlataforma'):
            with self.subTest(rol=rol):
                with scope.como_operador_plataforma():
                    Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.ARMANDO)
                self.client.force_login(self.usuarios[rol])
                with mock.patch('apps.payments.ordenes.configurar_stripe'), mock.patch(
                    'apps.payments.ordenes.revertir_orden', wraps=ordenes.revertir_orden,
                ) as revertir:
                    response = self.client.post('/admin/bookings/orden/', {
                        'action': 'cancelar_orden', '_selected_action': [self.orden.pk],
                    })
                self.assertEqual(response.status_code, 302)
                revertir.assert_called_once_with(self.orden, 'cancelada desde el admin')
                with scope.con_empresa(self.b):
                    self.orden.refresh_from_db()
                    self.assertEqual(self.orden.estado, Orden.Estado.CANCELADA)

    def test_reserva_enlaza_a_orden_y_admite_reserva_suelta(self):
        from django.contrib import admin
        model_admin = admin.site._registry[Reserva]
        self.assertIn('orden_link', model_admin.list_display)
        self.assertIn(reverse('admin:bookings_orden_change', args=[self.orden.pk]),
                      model_admin.orden_link(self.reservas[1]))
        self.assertEqual(model_admin.orden_link(Reserva()), '—')
