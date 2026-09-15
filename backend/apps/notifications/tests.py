"""Pruebas de las confirmaciones al cliente.

Lo que se protege aqui es que ninguna falla de notificacion tumbe el cobro (el
webhook de Stripe ya recibio el dinero cuando esto corre) y que la copia al
negocio salga oculta y solo cuando esta configurada.
"""
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock

import requests
from django.test import override_settings, TransactionTestCase

from apps.bookings.models import Reserva, ReservaExtra
from apps.fleet.models import Capitan, Embarcacion, ExtrasItem, PuntoEncuentro
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .services import (
    PUNTO_DE_ENCUENTRO,
    _asunto,
    enviar_correo_asignacion,
    enviar_correo_confirmacion,
    notificar_reserva_pagada,
)

LLAVES = {'RESEND_API_KEY': 'test-key', 'RESEND_FROM': 'reservas@ejemplo.com'}


def crear_reserva(empresa):
    return Reserva(
        empresa=empresa,
        servicio=crear_servicio_pesca(empresa),
        fecha=date.today() + timedelta(days=10),
        hora=time(6, 0),
        numero_personas=2,
        nombre_cliente='Ana Ruiz',
        telefono_cliente='+5216121234567',
        correo_cliente='ana@example.com',
        moneda='MXN',
        deslinde_aceptado=True,
        deslinde_nombre='Ana Ruiz',
    )


def crear_reserva_guardada(empresa, **overrides):
    """A diferencia de `crear_reserva()`, esta si queda en la base: hace falta
    tener `pk` para poder colgarle `ReservaExtra`."""
    empresa_real = overrides.get('empresa', empresa)
    crear_flota(empresa_real)
    datos = dict(
        empresa=empresa_real, fecha=date.today() + timedelta(days=10), hora=time(6, 0), numero_personas=2,
        nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567', correo_cliente='ana@example.com',
        canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True, deslinde_nombre='Ana Ruiz',
        moneda='MXN',
    )
    if 'servicio' not in overrides and 'paquete' not in overrides:
        datos['servicio'] = crear_servicio_pesca(empresa_real)
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva



def _cuerpo_enviado(post):
    """El json= de la llamada a Resend."""
    return post.call_args.kwargs['json']


@override_settings(**LLAVES, RESEND_BCC=['operacion@ejemplo.com'])
class CopiaAlNegocioTests(EmpresaTestCase):
    """La copia existe para tener un rastro fuera de la base de datos: si hay que
    restaurar un respaldo y se pierde medio dia de reservas, en ese buzon queda a
    quien hablarle (ver docs/vendors/supabase.md)."""

    @mock.patch('apps.notifications.services.requests.post')
    def test_manda_copia_al_negocio(self, post):
        post.return_value.raise_for_status.return_value = None

        self.assertTrue(enviar_correo_confirmacion(crear_reserva(self.empresa)))
        self.assertEqual(_cuerpo_enviado(post)['bcc'], ['operacion@ejemplo.com'])

    @mock.patch('apps.notifications.services.requests.post')
    def test_la_copia_va_oculta_no_en_el_para(self, post):
        """El cliente no tiene por que ver una direccion interna del negocio."""
        post.return_value.raise_for_status.return_value = None

        enviar_correo_confirmacion(crear_reserva(self.empresa))

        cuerpo = _cuerpo_enviado(post)
        self.assertEqual(cuerpo['to'], ['ana@example.com'])
        self.assertNotIn('operacion@ejemplo.com', cuerpo['to'])
        self.assertNotIn('cc', cuerpo)

    @mock.patch('apps.notifications.services.requests.post')
    def test_el_correo_lleva_lo_necesario_para_reconstruir_la_reserva(self, post):
        """Si esta copia va a servir de rastro, tiene que traer con que ubicar al
        cliente y saber cuando sale."""
        post.return_value.raise_for_status.return_value = None
        reserva = crear_reserva(self.empresa)

        enviar_correo_confirmacion(reserva)

        cuerpo = _cuerpo_enviado(post)
        self.assertIn(reserva.nombre_cliente, cuerpo['html'])
        self.assertIn(str(reserva.fecha), cuerpo['html'])
        self.assertIn('06:00', cuerpo['html'])
        self.assertIn(str(reserva.numero_personas), cuerpo['html'])
        self.assertIn(reserva.correo_cliente, cuerpo['to'])


@override_settings(**LLAVES, RESEND_BCC=[])
class SinCopiaConfiguradaTests(EmpresaTestCase):
    @mock.patch('apps.notifications.services.requests.post')
    def test_sin_bcc_configurado_no_se_manda_la_clave(self, post):
        post.return_value.raise_for_status.return_value = None

        enviar_correo_confirmacion(crear_reserva(self.empresa))

        self.assertNotIn('bcc', _cuerpo_enviado(post))


@override_settings(**LLAVES, RESEND_BCC=['operacion@ejemplo.com'])
class FallosNoTumbanElCobroTests(EmpresaTestCase):
    """El dinero ya entro cuando esto corre: un fallo aqui se registra y se sigue,
    nunca se propaga al webhook (haria que Stripe reintente el evento en bucle)."""

    @mock.patch('apps.notifications.services.requests.post')
    def test_si_resend_falla_devuelve_false_sin_lanzar(self, post):
        post.side_effect = requests.RequestException('resend caido')

        self.assertFalse(enviar_correo_confirmacion(crear_reserva(self.empresa)))

    @mock.patch('apps.notifications.services.requests.post')
    def test_notificar_no_lanza_aunque_los_dos_canales_fallen(self, post):
        post.side_effect = requests.RequestException('todo caido')

        resultado = notificar_reserva_pagada(crear_reserva(self.empresa))

        self.assertEqual(resultado, {'email': False, 'whatsapp': False})


@override_settings(RESEND_API_KEY='', RESEND_FROM='', RESEND_BCC=['operacion@ejemplo.com'])
class SinLlavesTests(EmpresaTestCase):
    @mock.patch('apps.notifications.services.requests.post')
    def test_sin_llaves_de_resend_no_se_llama_a_la_red(self, post):
        """Config local: sin llaves no se manda nada y el cobro sigue igual."""
        self.assertFalse(enviar_correo_confirmacion(crear_reserva(self.empresa)))
        post.assert_not_called()


@override_settings(**LLAVES)
class CorreoDeAsignacionTests(EmpresaTestCase):
    """El segundo correo: el que dice con quien y en que panga sale el cliente.

    El correo de confirmacion se manda cuando entra el pago, y en ese momento
    todavia no hay capitan ni embarcacion: se reparten despues, desde la agenda
    del admin. Este correo cierra ese hueco.
    """

    def _reserva_asignada(self):
        embarcacion = Embarcacion.objects.create(
            empresa=self.empresa, nombre='Dona Chuy',
            clase=Embarcacion.Clase.CHICA, capacidad_maxima=6,
        )
        capitan = Capitan.objects.create(
            empresa=self.empresa, nombre='Ramon Geraldo', telefono='+5216129876543')
        reserva = crear_reserva(self.empresa)
        reserva.estado = Reserva.Estado.ASIGNADA
        reserva.embarcacion = embarcacion
        reserva.capitan = capitan
        reserva.save()
        return reserva

    @mock.patch('apps.notifications.services.requests.post')
    def test_el_correo_lleva_panga_capitan_hora_y_punto_de_encuentro(self, post):
        reserva = self._reserva_asignada()

        self.assertTrue(enviar_correo_asignacion(reserva))

        html = _cuerpo_enviado(post)['html']
        self.assertIn('Dona Chuy', html)
        self.assertIn('Ramon Geraldo', html)
        self.assertIn('06:00', html)
        self.assertIn(PUNTO_DE_ENCUENTRO, html)

    @mock.patch('apps.notifications.services.requests.post')
    def test_no_publica_el_telefono_del_capitan(self, post):
        """El capitan no recibe llamadas de clientes a cualquier hora: todo pasa
        por el numero del negocio. El dato existe en el modelo, no en el correo."""
        reserva = self._reserva_asignada()

        enviar_correo_asignacion(reserva)

        self.assertNotIn('9876543', _cuerpo_enviado(post)['html'])

    @mock.patch('apps.notifications.services.requests.post')
    def test_va_al_cliente_y_no_reusa_el_asunto_de_la_confirmacion(self, post):
        reserva = self._reserva_asignada()

        enviar_correo_asignacion(reserva)

        cuerpo = _cuerpo_enviado(post)
        self.assertEqual(cuerpo['to'], ['ana@example.com'])
        self.assertNotEqual(cuerpo['subject'], _asunto(reserva))

    @mock.patch('apps.notifications.services.requests.post')
    def test_si_resend_falla_devuelve_false_sin_lanzar(self, post):
        post.side_effect = requests.RequestException('boom')

        self.assertFalse(enviar_correo_asignacion(self._reserva_asignada()))


@override_settings(**LLAVES)
class EscapadoDelCorreoTests(EmpresaTestCase):
    """Lo que escribe el cliente no puede volverse markup del correo.

    `validar_nombre_persona` acepta acentos, apostrofos y guiones porque son
    parte de nombres reales y solo rechaza digitos, asi que un `<a href=...>`
    pasa la validacion. Los cuerpos se arman con f-strings y no con plantillas,
    de modo que nadie escapa por nosotros. El correo no lo lee solo el cliente:
    con `RESEND_BCC` la copia cae en el buzon del negocio.
    """

    NOMBRE_CON_MARKUP = 'Ana <a href="https://malo.tld">Confirma aqui</a>'

    @mock.patch('apps.notifications.services.requests.post')
    def test_el_nombre_no_se_convierte_en_un_enlace(self, post):
        reserva = crear_reserva(self.empresa)
        reserva.nombre_cliente = self.NOMBRE_CON_MARKUP

        self.assertTrue(enviar_correo_confirmacion(reserva))

        html = _cuerpo_enviado(post)['html']
        self.assertNotIn('<a href', html)
        self.assertIn('&lt;a href', html)

    @mock.patch('apps.notifications.services.requests.post')
    def test_el_nombre_de_la_panga_tampoco(self, post):
        """El catalogo lo escriben los jefes desde el admin, no un extraño, pero
        el escapado es del renderizado y no de la confianza en la fuente."""
        embarcacion = Embarcacion.objects.create(
            empresa=self.empresa, nombre='Dona <b>Chuy</b>',
            clase=Embarcacion.Clase.CHICA, capacidad_maxima=6,
        )
        capitan = Capitan.objects.create(
            empresa=self.empresa, nombre='Ramon Geraldo', telefono='+5216129876543')
        reserva = crear_reserva(self.empresa)
        reserva.nombre_cliente = self.NOMBRE_CON_MARKUP
        reserva.estado = Reserva.Estado.ASIGNADA
        reserva.embarcacion = embarcacion
        reserva.capitan = capitan
        reserva.save()

        self.assertTrue(enviar_correo_asignacion(reserva))

        html = _cuerpo_enviado(post)['html']
        self.assertNotIn('<a href', html)
        self.assertNotIn('Dona <b>Chuy</b>', html)
        self.assertIn('Dona &lt;b&gt;Chuy&lt;/b&gt;', html)

    @mock.patch('apps.notifications.services.requests.post')
    def test_un_nombre_con_apostrofo_sigue_leyendose_bien(self, post):
        """El escapado no puede romper un nombre real. `escape` convierte el
        apostrofo en `&#x27;`, que el correo pinta como apostrofo: lo que ve el
        cliente es O'Brien, no la entidad."""
        reserva = crear_reserva(self.empresa)
        reserva.nombre_cliente = "Ana O'Brien Garcia-Lopez"

        enviar_correo_confirmacion(reserva)

        self.assertIn('Ana O&#x27;Brien Garcia-Lopez', _cuerpo_enviado(post)['html'])


@override_settings(**LLAVES)
class ExtrasEnElCorreoTests(EmpresaTestCase):
    """`_cuerpo_html` lista lo que se compro en el checkout (ya pagado) y avisa
    de lo que sigue pendiente de cotizar. Antes nada probaba esta funcion
    porque el guard de llaves vacias corta antes de llegar a ella."""

    @mock.patch('apps.notifications.services.requests.post')
    def test_lista_brunch_licencia_y_carnada_pagados(self, post):
        reserva = crear_reserva_guardada(self.empresa)
        for tipo, nombre in (('brunch', 'Brunch'), ('licencia', 'Licencia'), ('carnada', 'Carnada')):
            item = ExtrasItem.objects.create(
                empresa=self.empresa, tipo=tipo, nombre=nombre, precio=Decimal('300'))
            ReservaExtra.objects.create(
                reserva=reserva, extras_item=item, precio_unitario=Decimal('300'), cantidad=2,
            )

        self.assertTrue(enviar_correo_confirmacion(reserva))

        html = _cuerpo_enviado(post)['html']
        self.assertIn('Brunch', html)
        self.assertIn('Licencia', html)
        self.assertIn('Carnada', html)

    @mock.patch('apps.notifications.services.requests.post')
    def test_reserva_sin_extras_no_muestra_nada_de_mas(self, post):
        reserva = crear_reserva_guardada(self.empresa)

        self.assertTrue(enviar_correo_confirmacion(reserva))

        html = _cuerpo_enviado(post)['html']
        self.assertNotIn('incluido en tu pago', html)
        self.assertIn(PUNTO_DE_ENCUENTRO, html)

    @mock.patch('apps.notifications.services.requests.post')
    def test_bebidas_pendientes_avisa_sin_prometer_extras(self, post):
        reserva = crear_reserva_guardada(self.empresa, pide_bebidas=True)

        self.assertTrue(enviar_correo_confirmacion(reserva))

        html = _cuerpo_enviado(post)['html']
        self.assertIn('Pediste bebidas', html)
        self.assertNotIn('Pediste bebidas y extras', html)


@override_settings(
    RESEND_API_KEY='test-resend-key',
    RESEND_FROM='reservas@ejemplo.com',
    RESEND_BCC=['operacion@ejemplo.com'],
    WHATSAPP_TOKEN='test-wa-token',
    WHATSAPP_PHONE_NUMBER_ID='test-wa-phone-id',
    WHATSAPP_TEMPLATE='confirmacion_v1',
    WHATSAPP_TEMPLATE_LANG='es_MX',
)
class NotificarOrdenPagadaTest(TransactionTestCase):
    def setUp(self):
        from apps.bookings.models import DetalleTransporte, Orden, Reserva
        from apps.fleet.enums import TipoTraslado
        from apps.fleet.models import Paquete, PaqueteServicio, Servicio
        from apps.tenancy import scope
        from apps.tenancy.models import Empresa, Sede

        self.sede = Sede.objects.create(nombre='Sede Notif', slug='sede-notif', zona_horaria='America/Mazatlan')
        self.empresa_1 = Empresa.objects.create(
            nombre='Empresa Pesca Notif',
            slug='emp-notif-pesca',
            sede=self.sede,
            stripe_secret_key='sk_test_n1',
            stripe_publishable_key='pk_test_n1',
        )
        self.empresa_2 = Empresa.objects.create(
            nombre='Empresa Transporte Notif',
            slug='emp-notif-transporte',
            sede=self.sede,
            stripe_secret_key='sk_test_n2',
            stripe_publishable_key='pk_test_n2',
        )
        with scope.como_operador_plataforma():
            self.servicio_1 = Servicio.objects.create(
                empresa=self.empresa_1,
                nombre='Pesca en Panga',
                slug='pesca-notif',
                tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia',
            )
            self.servicio_2 = Servicio.objects.create(
                empresa=self.empresa_2,
                nombre='Traslado Aeropuerto',
                slug='transporte-notif',
                tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda',
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                nombre='Paquete Pesca y Traslado',
                slug='paquete-notif',
                precio_ancla=Decimal('5000.00'),
                activo=True,
            )
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_1, orden=1)
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio_2, orden=2)

        with scope.con_empresa(self.empresa_1):
            self.orden = Orden.objects.create(
                sede=self.sede,
                empresa_lider=self.empresa_1,
                paquete=self.paquete,
                nombre_cliente='Carlos Mendoza',
                telefono_cliente='+5216129876543',
                correo_cliente='carlos@example.com',
                moneda='MXN',
                estado=Orden.Estado.CAPTURADA,
            )
            self.reserva_1 = Reserva.objects.create(
                empresa=self.empresa_1,
                servicio=self.servicio_1,
                paquete=self.paquete,
                orden=self.orden,
                fecha=date(2026, 12, 1),
                hora=time(6, 30),
                numero_personas=3,
                nombre_cliente='Carlos Mendoza',
                telefono_cliente='+5216129876543',
                correo_cliente='carlos@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PAGADA,
                monto_pagado=Decimal('3500.00'),
                moneda='MXN',
                deslinde_aceptado=True,
            )
        with scope.con_empresa(self.empresa_2):
            self.reserva_2 = Reserva.objects.create(
                empresa=self.empresa_2,
                servicio=self.servicio_2,
                paquete=None,
                orden=self.orden,
                fecha=date(2026, 11, 30),
                hora=time(15, 0),
                numero_personas=3,
                nombre_cliente='Carlos Mendoza',
                telefono_cliente='+5216129876543',
                correo_cliente='carlos@example.com',
                canal_origen='web',
                estado=Reserva.Estado.PAGADA,
                monto_pagado=Decimal('1500.00'),
                moneda='MXN',
                deslinde_aceptado=True,
            )
            DetalleTransporte.objects.create(
                reserva=self.reserva_2,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                direccion_personalizada='Hotel Gran Baja',
                fecha_regreso=date(2026, 12, 3),
            )

    @mock.patch('apps.notifications.services.enviar_whatsapp_confirmacion')
    @mock.patch('apps.notifications.services.requests.post')
    def test_notificar_orden_pagada_correo_combinado_y_whatsapp_por_empresa(self, mock_post, mock_wa):
        """Tarea 5.4: Un correo combinado con 2 componentes + 2 llamadas a WhatsApp (una por empresa)."""
        from apps.notifications.services import notificar_orden_pagada
        from apps.bookings.models import Orden
        from apps.tenancy import scope
        from django.db import connection

        mock_post.return_value.raise_for_status.return_value = None

        # Como el webhook del último proveedor: sin relaciones de la líder en caché.
        with scope.con_empresa(self.empresa_2):
            orden = Orden.objects.get(pk=self.orden.pk)
            notificar_orden_pagada(orden)
            if connection.vendor == 'postgresql':
                self.assertEqual(list(Reserva.objects.values_list('id', flat=True)), [self.reserva_2.pk])

        # 1. Un solo correo enviado via Resend al correo del cliente
        mock_post.assert_called_once()
        cuerpo = mock_post.call_args.kwargs['json']
        self.assertEqual(cuerpo['to'], ['carlos@example.com'])
        self.assertEqual(cuerpo['bcc'], ['operacion@ejemplo.com'])
        self.assertIn('Paquete Pesca y Traslado', cuerpo['subject'])

        html = cuerpo['html']
        self.assertIn('Carlos Mendoza', html)
        self.assertIn('Paquete Pesca y Traslado', html)
        # Componente pesca
        self.assertIn('Pesca en Panga', html)
        self.assertIn('2026-12-01', html)
        self.assertIn('06:30', html)
        self.assertIn(PUNTO_DE_ENCUENTRO, html)
        # Componente traslado
        self.assertIn('Hotel Gran Baja', html)
        self.assertIn('2026-11-30', html)
        self.assertIn('15:00', html)
        self.assertIn('2026-12-03', html)

        # 2. Dos llamadas a WhatsApp: una por cada reserva/empresa
        self.assertEqual(mock_wa.call_count, 2)
        reservas_llamadas = {call.args[0].id for call in mock_wa.call_args_list}
        self.assertEqual(reservas_llamadas, {self.reserva_1.id, self.reserva_2.id})

    @mock.patch('apps.notifications.services.enviar_whatsapp_confirmacion')
    @mock.patch('apps.notifications.services.requests.post')
    def test_notificar_orden_pagada_fallo_correo_no_propaga_y_manda_whatsapp(self, mock_post, mock_wa):
        """Si el correo falla, no propaga el error y aun asi se intenta WhatsApp."""
        from apps.notifications.services import notificar_orden_pagada

        mock_post.side_effect = requests.RequestException('Resend error')

        # No debe lanzar excepción
        notificar_orden_pagada(self.orden)

        # Se intentó el correo
        mock_post.assert_called_once()
        # Se llamó a WhatsApp para ambas empresas a pesar del fallo de correo
        self.assertEqual(mock_wa.call_count, 2)

    @mock.patch('apps.notifications.services.enviar_whatsapp_confirmacion')
    @mock.patch('apps.notifications.services.requests.post')
    def test_notificar_orden_pagada_llamada_bajo_rls_de_una_empresa(self, mock_post, mock_wa):
        """Desde aplicar_pago_exitoso se llama dentro de scope.con_empresa(empresa_1).
        No debe colisionar con el tenancy ni dejar de ver la reserva de la empresa 2."""
        from apps.notifications.services import notificar_orden_pagada
        from apps.tenancy import scope

        mock_post.return_value.raise_for_status.return_value = None

        with scope.con_empresa(self.empresa_1):
            notificar_orden_pagada(self.orden)

        mock_post.assert_called_once()
        self.assertEqual(mock_wa.call_count, 2)

