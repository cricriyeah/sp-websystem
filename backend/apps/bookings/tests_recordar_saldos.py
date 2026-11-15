"""El recordatorio de saldo: un correo, un dia antes del viaje, a quien pago anticipo y debe el resto.

Lo que se protege aqui: que le llegue solo a quien de verdad debe y viaja mañana (en la hora de
su sede), que salga una sola vez, que ofrezca la transferencia por WhatsApp sin datos bancarios,
y que un correo que no sale deje aviso en el backoffice en vez de perderse en silencio.
"""
from datetime import datetime, time, timedelta, timezone as tz
from decimal import Decimal
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

import requests
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.notifications import plantilla
from apps.notifications.correo_recordatorio_saldo import _asunto, _cuerpo_html
from apps.tenancy import scope
from apps.tenancy.models import Notificacion
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .management.commands.recordar_saldos import reservas_por_recordar
from .models import Reserva
from .tests_reagendar import ReagendarBase

LLAVES = {'RESEND_API_KEY': 'test-key', 'RESEND_FROM': 'reservas@ejemplo.com', 'RESEND_BCC': []}
POST = 'apps.notifications.correo_recordatorio_saldo.requests.post'
ZONA = ZoneInfo('America/Mazatlan')


class _Base(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.pesca = crear_servicio_pesca(self.empresa)
        self.manana = timezone.now().astimezone(ZONA).date() + timedelta(days=1)

    def reserva(self, **cambios):
        datos = dict(
            empresa=self.empresa, servicio=self.pesca, fecha=self.manana, hora=time(6, 0),
            numero_personas=2, nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', moneda='MXN', canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True, deslinde_nombre='Ana Ruiz', estado=Reserva.Estado.PAGADA,
            forma_pago=Reserva.FormaPago.ANTICIPO,
            precio_total=Decimal('13907.00'), monto_pagado=Decimal('4172.10'), pagada_en=timezone.now(),
        )
        datos.update(cambios)
        reserva = Reserva(**datos)
        reserva.save()
        return reserva

    def correr(self, *args):
        """El comando abre sus propios alcances: hay que soltar el de la prueba mientras corre."""
        salida = StringIO()
        self._alcance.__exit__(None, None, None)
        try:
            call_command('recordar_saldos', *args, stdout=salida)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        return salida.getvalue()


@override_settings(**LLAVES)
class AQuienLeLlegaTests(_Base):
    @mock.patch(POST)
    def test_anticipo_con_saldo_que_viaja_manana_recibe_el_correo(self, post):
        reserva = self.reserva()

        salida = self.correr()

        self.assertEqual(post.call_count, 1)
        enviado = post.call_args.kwargs['json']
        self.assertEqual(enviado['to'], ['ana@example.com'])
        self.assertIn(f'#{reserva.pk}', enviado['subject'])
        self.assertIn('9,734.90 MXN', enviado['subject'])
        reserva.refresh_from_db()
        self.assertIsNotNone(reserva.recordatorio_saldo_enviado_en)
        self.assertIn('1 recordatorio(s) de saldo enviados, 0 sin enviar', salida)

    @mock.patch(POST)
    def test_no_le_llega_a_quien_no_le_toca(self, post):
        self.reserva(forma_pago=Reserva.FormaPago.COMPLETO, monto_pagado=Decimal('13907.00'))
        self.reserva(fecha=self.manana + timedelta(days=1), nombre_cliente='Viaja pasado mañana')
        self.reserva(fecha=self.manana + timedelta(days=9), nombre_cliente='Viaja en diez dias')
        self.reserva(monto_efectivo=Decimal('9734.90'), efectivo_cobrado_en=timezone.now(),
                     nombre_cliente='Ya liquido en efectivo')
        cancelada = self.reserva(fecha=self.manana + timedelta(days=3))
        Reserva.objects.filter(pk=cancelada.pk).update(
            estado=Reserva.Estado.CANCELADA, fecha=self.manana, reembolsada=True)
        pendiente = self.reserva(fecha=self.manana + timedelta(days=4))
        Reserva.objects.filter(pk=pendiente.pk).update(
            estado=Reserva.Estado.PENDIENTE_PAGO, fecha=self.manana)

        self.correr()

        post.assert_not_called()

    @mock.patch(POST)
    def test_quien_ya_liquido_por_transferencia_no_recibe_nada(self, post):
        self.reserva(monto_transferencia=Decimal('9734.90'), transferencia_registrada_en=timezone.now())

        self.correr()

        post.assert_not_called()

    @mock.patch(POST)
    def test_un_abono_parcial_recuerda_solo_lo_que_falta(self, post):
        self.reserva(monto_transferencia=Decimal('5000.00'), transferencia_registrada_en=timezone.now())

        self.correr()

        self.assertIn('4,734.90 MXN', post.call_args.kwargs['json']['subject'])

    @mock.patch(POST)
    def test_sale_una_sola_vez_aunque_el_comando_corra_dos(self, post):
        self.reserva()

        self.correr()
        self.correr()

        self.assertEqual(post.call_count, 1)

    @mock.patch(POST)
    def test_dry_run_lista_y_no_manda_ni_sella(self, post):
        reserva = self.reserva()

        salida = self.correr('--dry-run')

        post.assert_not_called()
        self.assertIn(f'#{reserva.pk}', salida)
        reserva.refresh_from_db()
        self.assertIsNone(reserva.recordatorio_saldo_enviado_en)


class MananaEsElDeLaSedeTests(_Base):
    def test_de_noche_en_la_sede_manana_no_es_el_manana_de_utc(self):
        """03:00 UTC del dia 10 son las 20:00 del dia 9 en La Paz: mañana es el 10, no el 11."""
        ahora = datetime(2027, 3, 10, 3, 0, tzinfo=tz.utc)
        el_diez = self.reserva(fecha=ahora.date(), nombre_cliente='El diez')
        self.reserva(fecha=ahora.date() + timedelta(days=1), nombre_cliente='El once')

        self.assertEqual([r.pk for r in reservas_por_recordar(ahora)], [el_diez.pk])

    def test_de_dia_en_la_sede_manana_coincide_con_utc(self):
        ahora = datetime(2027, 3, 10, 16, 0, tzinfo=tz.utc)
        self.reserva(fecha=ahora.date(), nombre_cliente='Hoy')
        el_once = self.reserva(fecha=ahora.date() + timedelta(days=1), nombre_cliente='Mañana')

        self.assertEqual([r.pk for r in reservas_por_recordar(ahora)], [el_once.pk])


class LoQueDiceElCorreoTests(_Base):
    def test_dice_cuanto_falta_y_las_dos_formas_de_pagarlo(self):
        reserva = self.reserva()

        texto = plantilla.a_texto(_cuerpo_html(reserva, Decimal('9734.90')))

        self.assertIn('Te quedan 9,734.90 MXN por liquidar.', texto)
        self.assertIn('en efectivo mañana, al llegar', texto)
        self.assertIn(f'escríbenos por WhatsApp con tu folio #{reserva.pk} y te pasamos los datos', texto)

    def test_no_lleva_datos_bancarios(self):
        """Decision del dueño: la transferencia se acuerda por WhatsApp, el correo no trae cuenta."""
        html = _cuerpo_html(self.reserva(), Decimal('9734.90')).lower()

        for palabra in ('clabe', 'cuenta bancaria', 'número de cuenta', 'banco '):
            self.assertNotIn(palabra, html)

    def test_lleva_el_dia_la_hora_de_llegada_y_el_saludo(self):
        reserva = self.reserva()

        texto = plantilla.a_texto(_cuerpo_html(reserva, Decimal('9734.90')))

        self.assertIn('MAÑANA SALES AL MAR', texto)
        self.assertIn('Hola Ana Ruiz, ya casi es el día.', texto)
        self.assertIn(plantilla.dia_largo(self.manana), texto)
        self.assertIn('5:45 a. m. (15 minutos antes)', texto)

    def test_el_nombre_del_cliente_entra_escapado(self):
        reserva = self.reserva(nombre_cliente='<b>Ana</b>')

        self.assertNotIn('<b>Ana</b>', _cuerpo_html(reserva, Decimal('9734.90')))

    def test_el_asunto_lleva_folio_y_saldo(self):
        reserva = self.reserva()

        self.assertEqual(
            _asunto(reserva, Decimal('9734.90')),
            f'Mañana es tu viaje #{reserva.pk}: te quedan 9,734.90 MXN por liquidar',
        )


@override_settings(**LLAVES)
class CuandoElCorreoNoSaleTests(_Base):
    def notificaciones(self):
        return list(Notificacion.objects.filter(empresa=self.empresa, nivel=Notificacion.Nivel.ERROR))

    @mock.patch(POST, side_effect=requests.ConnectionError('sin red'))
    def test_un_fallo_del_proveedor_no_sella_y_avisa_al_backoffice(self, post):
        reserva = self.reserva()

        salida = self.correr()

        reserva.refresh_from_db()
        self.assertIsNone(reserva.recordatorio_saldo_enviado_en)
        self.assertIn('0 recordatorio(s) de saldo enviados, 1 sin enviar', salida)
        (aviso,) = self.notificaciones()
        self.assertIn('Ana Ruiz', aviso.texto)
        self.assertIn(f'#{reserva.pk}', aviso.texto)
        self.assertIn(str(reserva.pk), aviso.enlace_url)

    @mock.patch(POST)
    def test_sin_correo_del_cliente_avisa_para_que_le_escriban(self, post):
        self.reserva(correo_cliente='')

        self.correr()

        post.assert_not_called()
        (aviso,) = self.notificaciones()
        self.assertIn('WhatsApp', aviso.texto)
        self.assertIn('no tiene correo', aviso.motivo)

    @mock.patch(POST)
    def test_un_correo_caido_no_detiene_a_los_demas(self, post):
        post.side_effect = [requests.ConnectionError('sin red'), mock.Mock()]
        self.reserva(nombre_cliente='Primera')
        self.reserva(nombre_cliente='Segunda', fecha=self.manana)

        salida = self.correr()

        self.assertEqual(post.call_count, 2)
        self.assertIn('1 recordatorio(s) de saldo enviados, 1 sin enviar', salida)


class ReagendarBorraElRecordatorioTests(ReagendarBase):
    def test_mover_el_dia_deja_que_salga_otro_recordatorio(self):
        reserva = self.crear_reserva()
        Reserva.objects.filter(pk=reserva.pk).update(recordatorio_saldo_enviado_en=timezone.now())
        reserva = Reserva.objects.get(pk=reserva.pk)

        self.mover(reserva, reserva.fecha + timedelta(days=3))

        reserva.refresh_from_db()
        self.assertIsNone(reserva.recordatorio_saldo_enviado_en)

    def test_cambiar_solo_la_hora_lo_conserva(self):
        reserva = self.crear_reserva()
        Reserva.objects.filter(pk=reserva.pk).update(recordatorio_saldo_enviado_en=timezone.now())
        reserva = Reserva.objects.get(pk=reserva.pk)

        self.mover(reserva, reserva.fecha, nueva_hora=time(7, 0))

        reserva.refresh_from_db()
        self.assertIsNotNone(reserva.recordatorio_saldo_enviado_en)
