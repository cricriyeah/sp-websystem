from datetime import date, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from apps.fleet.models import Embarcacion
from apps.testing import ApiTestCase, crear_flota

from .admin import telefono_marcable
from .models import (
    CUPO_MAXIMO_DEFAULT,
    MAX_PERSONAS,
    MOTIVO_LLENO,
    MOTIVO_SIN_PANGA,
    caben,
    motivo_sin_lugar,
    proxima_fecha_disponible,
    HORAS_PARA_CONSIDERAR_ABANDONADO,
    CheckoutAbandonado,
    CupoDiario,
    Reserva,
    Vendedora,
)


def envejecer(reserva, **delta):
    """`creado_en` es auto_now_add, hay que reescribirlo con un UPDATE."""
    Reserva.objects.filter(pk=reserva.pk).update(creado_en=timezone.now() - timedelta(**delta))
    return reserva


def datos_reserva(**overrides):
    # Hay tests que llaman Reserva(**datos_reserva()).full_clean() directo, y el
    # motor de cupo le pregunta a la flota: sin pangas no cabe nadie.
    crear_flota()
    base = {
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
    base.update(overrides)
    return base


def crear_reserva(**overrides):
    reserva = Reserva(**datos_reserva(**overrides))
    reserva.full_clean()
    reserva.save()
    return reserva


class VentanaSalidaTests(TestCase):
    def test_hora_fuera_de_la_ventana_es_invalida(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(hora=time(8, 0))).full_clean()


class NumeroPersonasTests(TestCase):
    def test_el_tope_es_la_panga_mas_grande_de_la_flota(self):
        """La flota real son 8 pangas de maximo 3 y 2 de maximo 5.

        El tope estuvo en 6, que no lo cumple ninguna: la web aceptaba y cobraba
        un viaje de 6 personas que despues no habia forma de operar.
        """
        Reserva(**datos_reserva(numero_personas=MAX_PERSONAS)).full_clean()

        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(numero_personas=MAX_PERSONAS + 1)).full_clean()

    def test_seis_personas_ya_no_se_acepta(self):
        # Explicito y no derivado de MAX_PERSONAS: si alguien sube la constante
        # sin comprar una panga mas grande, este test lo detiene.
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(numero_personas=6)).full_clean()

    def test_una_persona_es_valido(self):
        Reserva(**datos_reserva(numero_personas=1)).full_clean()

    def test_no_cabe_en_la_embarcacion_asignada(self):
        chica = Embarcacion.objects.create(
            nombre='La Chica', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3
        )
        reserva = Reserva(**datos_reserva(numero_personas=5, embarcacion=chica))
        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()
        self.assertIn('embarcacion', ctx.exception.message_dict)


class DeslindeTests(TestCase):
    def test_reserva_web_sin_deslinde_es_invalida(self):
        with self.assertRaises(ValidationError) as ctx:
            Reserva(**datos_reserva(deslinde_aceptado=False)).full_clean()
        self.assertIn('deslinde_aceptado', ctx.exception.message_dict)

    def test_reserva_por_whatsapp_no_requiere_deslinde_en_el_sistema(self):
        Reserva(**datos_reserva(
            canal_origen=Reserva.CanalOrigen.WHATSAPP, deslinde_aceptado=False, deslinde_nombre=''
        )).full_clean()


class CupoTests(TestCase):
    def test_pendiente_de_pago_no_ocupa_cupo(self):
        fecha = date.today() + timedelta(days=10)
        for _ in range(CUPO_MAXIMO_DEFAULT + 2):
            crear_reserva(fecha=fecha)
        crear_reserva(fecha=fecha).full_clean()

    def test_se_llena_con_reservas_pagadas(self):
        fecha = date.today() + timedelta(days=10)
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(fecha=fecha, estado=Reserva.Estado.PAGADA)
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(fecha=fecha, estado=Reserva.Estado.PAGADA)).full_clean()

    def test_cupo_diario_override_cierra_el_dia(self):
        fecha = date.today() + timedelta(days=10)
        CupoDiario.objects.create(fecha=fecha, cupo_maximo=0)
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(fecha=fecha, estado=Reserva.Estado.PAGADA)).full_clean()


class CambioDeFechaTests(TestCase):
    def test_permitido_con_mas_de_48_horas(self):
        reserva = crear_reserva(
            fecha=date.today() + timedelta(days=10), estado=Reserva.Estado.PAGADA
        )
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.fecha = date.today() + timedelta(days=12)
        reserva.full_clean()

    def test_bloqueado_dentro_de_las_48_horas(self):
        manana = timezone.localtime().date() + timedelta(days=1)
        reserva = crear_reserva(fecha=manana, estado=Reserva.Estado.PAGADA)
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.fecha = manana + timedelta(days=5)
        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()
        self.assertIn('fecha', ctx.exception.message_dict)

    def test_cancelar_por_mal_clima_no_pide_48_horas(self):
        manana = timezone.localtime().date() + timedelta(days=1)
        reserva = crear_reserva(fecha=manana, estado=Reserva.Estado.PAGADA)
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.motivo_cancelacion = 'Mal clima'
        reserva.cancelada_en = timezone.now()
        reserva.reembolsada = True
        reserva.full_clean()


class CupoApiTests(ApiTestCase):
    def test_fecha_invalida_responde_400(self):
        response = self.client.get('/api/cupo/?fecha=no-es-fecha')
        self.assertEqual(response.status_code, 400)

    def test_sin_fecha_responde_400(self):
        self.assertEqual(self.client.get('/api/cupo/').status_code, 400)

    def test_fecha_valida_responde_el_cupo(self):
        fecha = date.today() + timedelta(days=10)
        crear_reserva(fecha=fecha, estado=Reserva.Estado.PAGADA)
        response = self.client.get(f'/api/cupo/?fecha={fecha}')
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


class CheckoutAbandonadoTests(TestCase):
    def test_no_lista_al_que_apenas_empezo(self):
        crear_reserva()  # pendiente_pago, recien creada
        self.assertEqual(CheckoutAbandonado.abandonados().count(), 0)

    def test_lista_al_que_lleva_rato_sin_pagar(self):
        envejecer(crear_reserva(), hours=HORAS_PARA_CONSIDERAR_ABANDONADO + 1)
        self.assertEqual(CheckoutAbandonado.abandonados().count(), 1)

    def test_no_lista_las_que_si_pagaron(self):
        envejecer(crear_reserva(estado=Reserva.Estado.PAGADA), hours=48)
        self.assertEqual(CheckoutAbandonado.abandonados().count(), 0)

    def test_el_listado_del_admin_es_solo_lectura(self):
        envejecer(crear_reserva(), hours=48)
        self.client.force_login(User.objects.create_superuser('jefa', password='x'))

        response = self.client.get(reverse('admin:bookings_checkoutabandonado_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'wa.me')
        # Ni superusuario puede agregar o borrar desde aqui.
        self.assertEqual(
            self.client.get(reverse('admin:bookings_checkoutabandonado_add')).status_code, 403
        )

    def test_la_vendedora_puede_verlo(self):
        vendedora = User.objects.create_user('vendedora', password='x', is_staff=True)
        vendedora.user_permissions.add(
            Permission.objects.get(codename='view_checkoutabandonado')
        )
        self.client.force_login(vendedora)
        self.assertEqual(
            self.client.get(reverse('admin:bookings_checkoutabandonado_changelist')).status_code,
            200,
        )


class LimpiarCheckoutsAbandonadosTests(TestCase):
    def ejecutar(self, **kwargs):
        salida = StringIO()
        call_command('limpiar_checkouts_abandonados', stdout=salida, **kwargs)
        return salida.getvalue()

    def test_borra_los_viejos(self):
        envejecer(crear_reserva(), days=40)
        self.ejecutar()
        self.assertEqual(Reserva.objects.count(), 0)

    def test_respeta_los_recientes(self):
        envejecer(crear_reserva(), days=5)
        self.ejecutar()
        self.assertEqual(Reserva.objects.count(), 1)

    def test_nunca_toca_una_reserva_pagada(self):
        envejecer(crear_reserva(estado=Reserva.Estado.PAGADA), days=400)
        self.ejecutar()
        self.assertEqual(Reserva.objects.count(), 1)

    def test_dias_configurable(self):
        envejecer(crear_reserva(), days=5)
        self.ejecutar(dias=3)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_dry_run_no_borra(self):
        envejecer(crear_reserva(), days=40)
        salida = self.ejecutar(dry_run=True)
        self.assertIn('Se borrarian 1', salida)
        self.assertEqual(Reserva.objects.count(), 1)


class LiquidacionEnEfectivoTests(TestCase):
    """El 70% que se cobra en el muelle tiene que dejar rastro."""

    def setUp(self):
        self.jefa = User.objects.create_superuser('jefa', password='x')
        self.client.force_login(self.jefa)
        self.url = reverse('admin:bookings_reserva_changelist')

    def reserva_con_anticipo(self):
        reserva = crear_reserva(estado=Reserva.Estado.PAGADA)
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
        reserva = crear_reserva(estado=Reserva.Estado.PAGADA)
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
    """

    def setUp(self):
        self.client.force_login(User.objects.create_superuser('jefa', password='x'))

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


class ReservasNuevasAdminTests(TestCase):
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
        vendedora = User.objects.create_user('sin_permisos', password='x', is_staff=True)
        self.client.force_login(vendedora)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_vendedora_con_permiso_puede_consultar(self):
        vendedora = User.objects.create_user('vendedora', password='x', is_staff=True)
        vendedora.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(vendedora)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_cuenta_las_pagadas_que_entraron_despues(self):
        self.client.force_login(User.objects.create_superuser('jefa', password='x'))
        desde = self.semilla()

        crear_reserva(estado=Reserva.Estado.PAGADA)
        crear_reserva(estado=Reserva.Estado.PAGADA)
        body = self.client.get(self.url, {'desde': desde}).json()

        self.assertEqual(body['nuevas'], 2)
        # El ancla no se mueve: el contador sigue subiendo hasta que se recargue.
        self.assertEqual(body['desde'], desde)

        crear_reserva(estado=Reserva.Estado.PAGADA)
        self.assertEqual(self.client.get(self.url, {'desde': desde}).json()['nuevas'], 3)

    def test_ignora_los_checkouts_abandonados(self):
        self.client.force_login(User.objects.create_superuser('jefa', password='x'))
        desde = self.semilla()

        crear_reserva()  # pendiente_pago
        self.assertEqual(self.client.get(self.url, {'desde': desde}).json()['nuevas'], 0)

    def test_ignora_lo_anterior_a_la_carga_de_la_pagina(self):
        self.client.force_login(User.objects.create_superuser('jefa', password='x'))
        crear_reserva(estado=Reserva.Estado.PAGADA)
        desde = self.semilla()

        self.assertEqual(self.client.get(self.url, {'desde': desde}).json()['nuevas'], 0)

    def test_desde_invalido_responde_400(self):
        self.client.force_login(User.objects.create_superuser('jefa', password='x'))
        self.assertEqual(self.client.get(self.url, {'desde': 'ayer'}).status_code, 400)


class ReservaApiTests(ApiTestCase):
    CHECKOUT_ID = '11111111-1111-4111-8111-111111111111'

    def payload(self, **overrides):
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
        }
        datos.update(overrides)
        return datos

    def enviar(self, **overrides):
        return self.client.post(
            '/api/reservas/', self.payload(**overrides), content_type='application/json'
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
            '/api/reservas/', self.payload(checkout_id=None), content_type='application/json'
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


class AtribucionDeVentaTests(ApiTestCase):
    """A quien le cuenta cada venta. La comision se liquida fuera del sistema;
    aqui lo unico que importa es que el registro no se pierda ni se invente."""

    CHECKOUT_ID = '33333333-3333-4333-8333-333333333333'

    def setUp(self):
        self.maria = Vendedora.objects.create(
            usuario=User.objects.create_user('maria', password='x', is_staff=True),
            codigo='maria',
        )

    def enviar(self, **overrides):
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
        }
        datos.update(overrides)
        return self.client.post('/api/reservas/', datos, content_type='application/json')

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
        reserva = crear_reserva()
        self.assertIsNone(reserva.vendedora_asignada_en)

        reserva.vendedora = self.maria
        reserva.save()

        self.assertIsNotNone(Reserva.objects.get(pk=reserva.pk).vendedora_asignada_en)

    def test_quitar_la_atribucion_limpia_la_fecha(self):
        reserva = crear_reserva(vendedora=self.maria)
        reserva.vendedora = None
        reserva.save()

        self.assertIsNone(Reserva.objects.get(pk=reserva.pk).vendedora_asignada_en)

    def test_no_se_puede_borrar_una_vendedora_con_ventas(self):
        """Borrarla dejaria ventas sin dueño: para dar de baja se usa `activo`."""
        crear_reserva(vendedora=self.maria)

        with self.assertRaises(ProtectedError):
            self.maria.delete()


class IpDelDeslindeTests(ApiTestCase):
    """La IP que queda en el deslinde es constancia legal: si el propio cliente
    puede elegirla, no prueba nada. `X-Forwarded-For` es una lista donde cada
    salto agrega al final, asi que lo unico creible es lo que escribio nuestro
    proxy — contando desde la derecha (ver apps/bookings/serializers.py)."""

    CHECKOUT_ID = '44444444-4444-4444-8444-444444444444'

    def enviar(self, **extra):
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
        }
        response = self.client.post(
            '/api/reservas/', datos, content_type='application/json', **extra
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
        url = f'/api/cupo/?fecha={date.today() + timedelta(days=10)}'

        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 429)

    @mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'reservas': '1/min'})
    def test_el_limite_es_por_ip_no_global(self):
        """Dos clientes distintos detras de la misma pagina no se estorban."""
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
        }

        def enviar(ip):
            return self.client.post(
                '/api/reservas/', datos, content_type='application/json', REMOTE_ADDR=ip
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


class ValidacionDeContactoTests(TestCase):
    """El telefono y el nombre se aprietan distinto a proposito.

    El telefono es con lo que la vendedora contacta al cliente: uno invalido es
    alguien en el muelle a las 6 am sin que nadie lo espere. El nombre se aprieta
    poco — la regla intuitiva ("solo letras") rompe personas reales.
    """

    def test_telefono_con_letras_no_pasa(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(telefono_cliente='asdf')).full_clean()

    def test_telefono_incompleto_no_pasa(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(telefono_cliente='612 123')).full_clean()

    def test_acepta_el_telefono_como_lo_escribe_la_gente(self):
        for numero in ('6121234567', '612 123 4567', '(612) 123-4567', '+52 1 612 123 4567'):
            with self.subTest(numero=numero):
                Reserva(**datos_reserva(telefono_cliente=numero)).full_clean()

    def test_nombre_con_numeros_no_pasa(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(nombre_cliente='12345')).full_clean()

    def test_nombre_sin_ninguna_letra_no_pasa(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(nombre_cliente='-----')).full_clean()

    def test_no_rechaza_nombres_reales(self):
        """El fallo caro aqui no es guardar un nombre raro: es dejar a una
        persona sin poder reservar por llamarse como se llama."""
        for nombre in ("Jose Munoz", "José Muñoz", "O'Brien", "Garcia-Lopez", "Ana de la Torre"):
            with self.subTest(nombre=nombre):
                Reserva(**datos_reserva(nombre_cliente=nombre, deslinde_nombre=nombre)).full_clean()


class ProximaFechaDisponibleTests(TestCase):
    """La busqueda del siguiente dia con espacio vive en el servidor.

    Antes la hacia el navegador con una peticion por dia — hasta 90 seguidas,
    que con el limite de 60/min terminaban en 429 y el frontend se lo tragaba
    en silencio.
    """

    def test_si_el_dia_pedido_tiene_espacio_se_devuelve_ese(self):
        fecha = date.today() + timedelta(days=10)
        self.assertEqual(proxima_fecha_disponible(fecha), fecha)

    def test_salta_los_dias_llenos(self):
        primero = date.today() + timedelta(days=10)
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(fecha=primero, estado=Reserva.Estado.PAGADA)

        self.assertEqual(proxima_fecha_disponible(primero), primero + timedelta(days=1))

    def test_respeta_el_cupo_cerrado_a_mano(self):
        primero = date.today() + timedelta(days=10)
        CupoDiario.objects.create(fecha=primero, cupo_maximo=0)

        self.assertEqual(proxima_fecha_disponible(primero), primero + timedelta(days=1))

    def test_sin_ningun_dia_libre_devuelve_none(self):
        desde = date.today() + timedelta(days=10)
        for i in range(3):
            CupoDiario.objects.create(fecha=desde + timedelta(days=i), cupo_maximo=0)

        self.assertIsNone(proxima_fecha_disponible(desde, dias=3))

    def test_no_hace_una_consulta_por_dia(self):
        """El punto entero del cambio: el costo no crece con la ventana."""
        desde = date.today() + timedelta(days=10)
        with self.assertNumQueries(2):
            proxima_fecha_disponible(desde, dias=90)


class CupoApiDevuelveProximaTests(ApiTestCase):
    def test_la_respuesta_trae_la_proxima_fecha_disponible(self):
        fecha = date.today() + timedelta(days=10)
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(fecha=fecha, estado=Reserva.Estado.PAGADA)

        cuerpo = self.client.get(f'/api/cupo/?fecha={fecha}').json()

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
