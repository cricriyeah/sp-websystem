"""El correo al cliente cuando se le reagenda la reserva (ARCH-reagendar-reserva.md §7 y §10).

Se prueba con `AntesDelCambio` simulado: el dataclass real vive en `apps/bookings/reagendar.py`
y el correo solo lee sus atributos (fecha, hora, inicio_paquete, fecha_salida, fecha_regreso,
panga, capitan). Cada prueba crea sus propios datos; ninguna depende del orden.
"""
from dataclasses import dataclass
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Optional
from unittest import mock

import requests
from django.test import override_settings

from apps.bookings.models import DetalleTransporte, Reserva
from apps.fleet.enums import TipoTraslado
from apps.fleet.models import Capitan, Embarcacion
from apps.testing import EmpresaTestCase, crear_servicio_pesca

from . import correo_reagendado
from .correo_reagendado import _asunto, _cuerpo_html, enviar_correo_reagendado
from .services import SIN_PUNTO_DE_ENCUENTRO

LLAVES = {'RESEND_API_KEY': 'test-key', 'RESEND_FROM': 'reservas@ejemplo.com'}
POST = 'apps.notifications.correo_reagendado.requests.post'

# Fechas fijas: lunes 7 y martes 15 de diciembre de 2026.
FECHA_VIEJA = date(2026, 12, 7)
FECHA_NUEVA = date(2026, 12, 15)


@dataclass
class Antes:
    """Doble de `AntesDelCambio`: lo que el correo lee de «como estaba»."""
    fecha: date = FECHA_VIEJA
    hora: Optional[time] = time(6, 0)
    inicio_paquete: Optional[date] = None
    fecha_salida: Optional[date] = None
    fecha_regreso: Optional[date] = None
    panga: str = ''
    capitan: str = ''


def _enviado(post):
    return post.call_args.kwargs['json']


class _Base(EmpresaTestCase):
    def reserva(self, servicio=None, **cambios):
        datos = dict(
            empresa=self.empresa, servicio=servicio or crear_servicio_pesca(self.empresa),
            fecha=FECHA_NUEVA, hora=time(7, 0), numero_personas=2,
            nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', moneda='MXN',
            deslinde_aceptado=True, deslinde_nombre='Ana Ruiz',
            estado=Reserva.Estado.PAGADA,
        )
        datos.update(cambios)
        reserva = Reserva(**datos)
        reserva.save()
        return reserva

    def panga_y_capitan(self, nombre_panga='Dona Chuy', nombre_capitan='Ramon Geraldo'):
        panga = Embarcacion.objects.create(
            empresa=self.empresa, nombre=nombre_panga, clase=Embarcacion.Clase.CHICA, capacidad_maxima=6)
        capitan = Capitan.objects.create(empresa=self.empresa, nombre=nombre_capitan, telefono='+5216129876543')
        return panga, capitan

    def servicio_de(self, **overrides):
        return crear_servicio_pesca(self.empresa, **overrides)

    def traslado(self):
        return crear_servicio_pesca(
            self.empresa, slug='traslado-rg', nombre='Traslado aeropuerto', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta')

    def hospedaje(self, **overrides):
        return crear_servicio_pesca(
            self.empresa, slug='hotel-rg', nombre='Hotel Costa', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche', **overrides)


class AsuntoTests(_Base):
    def test_lleva_el_folio_la_nueva_fecha_y_la_hora(self):
        reserva = self.reserva()

        self.assertEqual(_asunto(reserva), f'Reserva reagendada #{reserva.pk} — 2026-12-15 07:00')

    def test_sin_hora_dice_por_definir(self):
        reserva = self.reserva(hora=None)

        self.assertEqual(_asunto(reserva), f'Reserva reagendada #{reserva.pk} — 2026-12-15 por definir')

    @override_settings(**LLAVES)
    @mock.patch(POST)
    def test_el_asunto_viaja_a_resend(self, post):
        reserva = self.reserva()

        self.assertTrue(enviar_correo_reagendado(reserva, Antes()))

        self.assertEqual(_enviado(post)['subject'], _asunto(reserva))
        self.assertEqual(_enviado(post)['to'], ['ana@example.com'])


class CuerpoTests(_Base):
    def test_titular_folio_producto_e_intro(self):
        reserva = self.reserva()

        html = _cuerpo_html(reserva, Antes())

        self.assertIn('RESERVA REAGENDADA', html)
        self.assertIn(f'#{reserva.pk}', html)
        self.assertIn('Pesca Deportiva', html)
        self.assertIn('Empresa de prueba', html)
        self.assertIn('Hola Ana Ruiz, tu reserva quedó reagendada.', html)

    def test_muestra_lo_de_antes_y_lo_de_ahora(self):
        reserva = self.reserva()

        html = _cuerpo_html(reserva, Antes(fecha=FECHA_VIEJA, hora=time(6, 0)))

        self.assertIn('TU NUEVA FECHA', html)  # los titulos de seccion van en mayusculas
        self.assertIn('Antes', html)
        self.assertIn('Lunes 7 de diciembre', html)
        self.assertIn('6:00 a. m.', html)
        self.assertIn('Ahora', html)
        self.assertIn('Martes 15 de diciembre', html)
        self.assertIn('7:00 a. m.', html)

    def test_la_vista_previa_lleva_la_nueva_fecha_y_la_vieja(self):
        html = _cuerpo_html(self.reserva(), Antes())

        self.assertIn('2026-12-15 · 07:00 · antes 2026-12-07', html)

    def test_sin_hora_ni_antes_ni_ahora_dice_la_hora(self):
        reserva = self.reserva(hora=None)

        html = _cuerpo_html(reserva, Antes(hora=None))

        self.assertIn('Martes 15 de diciembre', html)
        self.assertIn('por definir', html)

    def test_nunca_dice_pagaste_hoy(self):
        reserva = self.reserva(
            forma_pago=Reserva.FormaPago.ANTICIPO, precio_total=Decimal('4500.00'),
            monto_pagado=Decimal('1350.00'))

        self.assertNotIn('Pagaste', _cuerpo_html(reserva, Antes()))
        self.assertNotIn('Pagaste', _cuerpo_html(self.reserva(monto_pagado=Decimal('4500.00')), Antes()))

    def test_con_saldo_en_efectivo_dice_cuanto_queda(self):
        reserva = self.reserva(
            forma_pago=Reserva.FormaPago.ANTICIPO, precio_total=Decimal('4500.00'),
            monto_pagado=Decimal('1350.00'))

        html = _cuerpo_html(reserva, Antes())

        self.assertIn('EL DINERO', html)
        self.assertIn('Quedan 3150.00 MXN por liquidar en efectivo el día del viaje.', html)

    def test_sin_saldo_no_hay_seccion_de_dinero(self):
        reserva = self.reserva(
            forma_pago=Reserva.FormaPago.COMPLETO, precio_total=Decimal('4500.00'),
            monto_pagado=Decimal('4500.00'))

        self.assertNotIn('EL DINERO', _cuerpo_html(reserva, Antes()))

    def test_que_sigue_dice_que_el_pago_sigue_vigente_y_como_escribir(self):
        html = _cuerpo_html(self.reserva(), Antes())

        self.assertIn('QUÉ SIGUE', html)
        self.assertIn('Tu pago sigue vigente: no tienes que pagar de nuevo.', html)
        self.assertIn('Si esta fecha no te funciona, escríbenos por WhatsApp con tu folio.', html)

    def test_personas(self):
        self.assertIn('>3<', _cuerpo_html(self.reserva(numero_personas=3), Antes()))


class PuntoDeEncuentroTests(_Base):
    def test_sale_del_punto_de_salida_del_servicio(self):
        reserva = self.reserva(self.servicio_de(punto_salida='Muelle Norte'))

        html = _cuerpo_html(reserva, Antes())

        self.assertIn('Sales de', html)
        self.assertIn('Muelle Norte', html)

    def test_sin_dato_dice_que_se_confirma_por_whatsapp(self):
        html = _cuerpo_html(self.reserva(), Antes())

        self.assertIn(SIN_PUNTO_DE_ENCUENTRO, html)
        self.assertNotIn('Rangel y Navarro', html)

    def test_el_punto_se_escapa(self):
        reserva = self.reserva(self.servicio_de(punto_salida='<b>Muelle</b> & co'))

        html = _cuerpo_html(reserva, Antes())

        self.assertIn('&lt;b&gt;Muelle&lt;/b&gt; &amp; co', html)
        self.assertNotIn('<b>Muelle</b>', html)

    def test_hospedaje_sin_dato_no_lleva_renglon(self):
        html = _cuerpo_html(self.reserva(self.hospedaje(), fecha_salida=FECHA_NUEVA + timedelta(days=2)), Antes())

        self.assertNotIn('Punto de encuentro', html)
        self.assertNotIn('Sales de', html)
        self.assertNotIn(SIN_PUNTO_DE_ENCUENTRO, html)


class EscapadoTests(_Base):
    NOMBRE_MALICIOSO = 'Ana <a href="https://malo.tld">Confirma aqui</a>'

    def test_el_nombre_del_cliente_no_se_vuelve_enlace(self):
        reserva = self.reserva(nombre_cliente=self.NOMBRE_MALICIOSO)

        html = _cuerpo_html(reserva, Antes())

        self.assertNotIn('<a href', html)
        self.assertIn('&lt;a href', html)

    def test_los_nombres_de_panga_y_capitan_tambien(self):
        panga, capitan = self.panga_y_capitan('Dona <b>Chuy</b>', 'Ramon <i>G</i>')
        reserva = self.reserva(embarcacion=panga, capitan=capitan, estado=Reserva.Estado.ASIGNADA)

        html = _cuerpo_html(reserva, Antes(panga='Dona <b>Chuy</b>', capitan='Ramon <i>G</i>'))

        self.assertNotIn('<b>Chuy</b>', html)
        self.assertIn('Dona &lt;b&gt;Chuy&lt;/b&gt;', html)
        self.assertNotIn('<i>G</i>', html)

    @override_settings(**LLAVES)
    @mock.patch(POST)
    def test_el_html_enviado_a_resend_va_escapado(self, post):
        # El texto plano si dice «<a href...>» (es texto, no markup): lo que importa es el html.
        enviar_correo_reagendado(self.reserva(nombre_cliente=self.NOMBRE_MALICIOSO), Antes())

        self.assertNotIn('<a href', _enviado(post)['html'])
        self.assertIn('&lt;a href', _enviado(post)['html'])


class TextoPlanoTests(_Base):
    @override_settings(**LLAVES)
    @mock.patch(POST)
    def test_el_texto_trae_lo_mismo_sin_etiquetas_y_en_el_mismo_orden(self, post):
        enviar_correo_reagendado(self.reserva(), Antes())

        texto = _enviado(post)['text']

        self.assertNotIn('<', texto)
        self.assertIn('RESERVA REAGENDADA', texto)
        self.assertIn('Hola Ana Ruiz, tu reserva quedó reagendada.', texto)
        orden = [texto.index(s) for s in ('TU NUEVA FECHA', 'Antes', 'Ahora', 'QUÉ SIGUE')]
        self.assertEqual(orden, sorted(orden))
        self.assertIn('Tu pago sigue vigente', texto)


class MarTests(_Base):
    def test_dice_a_que_hora_llegar(self):
        html = _cuerpo_html(self.reserva(), Antes())

        self.assertIn('Llega a las', html)
        self.assertIn('6:45 a. m. (15 minutos antes)', html)

    def test_lleva_las_garantias(self):
        html = _cuerpo_html(self.reserva(), Antes())

        self.assertIn('SI ALGO CAMBIA', html)
        self.assertIn('48 H', html)

    def test_si_se_conservaron_panga_y_capitan_los_dice_y_avisa_que_siguen(self):
        panga, capitan = self.panga_y_capitan()
        reserva = self.reserva(embarcacion=panga, capitan=capitan, estado=Reserva.Estado.ASIGNADA)

        html = _cuerpo_html(reserva, Antes(panga='Dona Chuy', capitan='Ramon Geraldo'))

        self.assertIn('Capitán', html)
        self.assertIn('Ramon Geraldo', html)
        self.assertIn('Panga', html)
        self.assertIn('Dona Chuy', html)
        self.assertIn('Tu capitán y tu panga siguen siendo los mismos.', html)
        self.assertNotIn('Te llega otro correo', html)

    def test_si_se_quitaron_no_los_muestra_y_avisa_que_llega_otro_correo(self):
        reserva = self.reserva()  # ahora sin panga ni capitan

        html = _cuerpo_html(reserva, Antes(panga='Dona Chuy', capitan='Ramon Geraldo'))

        self.assertNotIn('Dona Chuy', html)
        self.assertNotIn('Ramon Geraldo', html)
        self.assertNotIn('>Capitán<', html)
        self.assertNotIn('>Panga<', html)
        self.assertIn('Te llega otro correo con tu capitán y tu panga en cuanto queden asignados.', html)
        self.assertNotIn('siguen siendo los mismos', html)

    def test_si_solo_se_quito_el_capitan_la_panga_se_muestra_y_llega_otro_correo(self):
        panga, _capitan = self.panga_y_capitan()
        reserva = self.reserva(embarcacion=panga, estado=Reserva.Estado.ASIGNADA)

        html = _cuerpo_html(reserva, Antes(panga='Dona Chuy', capitan='Ramon Geraldo'))

        self.assertIn('Dona Chuy', html)
        self.assertNotIn('Ramon Geraldo', html)
        self.assertIn('Te llega otro correo', html)
        self.assertNotIn('siguen siendo los mismos', html)

    def test_si_nunca_hubo_asignacion_tambien_promete_el_correo(self):
        html = _cuerpo_html(self.reserva(), Antes())

        self.assertIn('Te llega otro correo', html)


class TrasladoTests(_Base):
    def _traslado(self, **cambios):
        reserva = self.reserva(self.traslado(), **cambios)
        DetalleTransporte.objects.create(
            reserva=reserva, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            direccion_personalizada='Hotel Gran Baja', fecha_regreso=date(2026, 12, 20))
        return Reserva.objects.get(pk=reserva.pk)

    def test_dice_la_fecha_de_regreso_y_usa_el_campo_de_traslado(self):
        html = _cuerpo_html(self._traslado(), Antes())

        self.assertIn('Fecha de regreso', html)
        self.assertIn('Domingo 20 de diciembre', html)
        self.assertIn('#a83226', html)  # campo de color de traslado

    def test_un_traslado_no_lleva_garantias_ni_hora_de_llegada_ni_panga(self):
        html = _cuerpo_html(self._traslado(), Antes())

        self.assertNotIn('SI ALGO CAMBIA', html)
        self.assertNotIn('Llega a las', html)
        self.assertNotIn('Te llega otro correo', html)
        self.assertNotIn('siguen siendo los mismos', html)

    def test_el_punto_de_encuentro_es_el_del_traslado(self):
        html = _cuerpo_html(self._traslado(), Antes())

        self.assertIn('Hotel Gran Baja', html)

    def test_sin_detalle_no_revienta(self):
        reserva = self.reserva(self.traslado())  # sin DetalleTransporte

        html = _cuerpo_html(reserva, Antes())

        self.assertNotIn('Fecha de regreso', html)


class EstanciaTests(_Base):
    def test_hospedaje_dice_llegada_salida_y_noches(self):
        reserva = self.reserva(self.hospedaje(), fecha_salida=FECHA_NUEVA + timedelta(days=3))

        html = _cuerpo_html(reserva, Antes())

        self.assertIn('Llegada', html)
        self.assertIn('Martes 15 de diciembre', html)
        self.assertIn('Salida', html)
        self.assertIn('Viernes 18 de diciembre', html)
        self.assertIn('Noches', html)
        self.assertIn('>3<', html)
        self.assertIn('#343f04', html)  # campo verde de estancia
        self.assertNotIn('SI ALGO CAMBIA', html)
        self.assertNotIn('Llega a las', html)

    def test_en_un_paquete_la_fecha_es_la_de_inicio_no_la_de_la_actividad(self):
        inicio = date(2026, 12, 14)
        reserva = self.reserva(
            self.hospedaje(), fecha=date(2026, 12, 15), inicio_paquete=inicio, fecha_salida=date(2026, 12, 17))

        html = _cuerpo_html(reserva, Antes(
            fecha=date(2026, 12, 2), inicio_paquete=date(2026, 12, 1), fecha_salida=date(2026, 12, 4)))

        self.assertIn('Lunes 14 de diciembre', html)  # Ahora y Llegada
        self.assertIn('Martes 1 de diciembre', html)  # Antes
        self.assertNotIn('Martes 15 de diciembre', html)
        self.assertIn('Noches', html)
        self.assertIn('>3<', html)
        self.assertIn('antes 2026-12-01', html)
        self.assertEqual(_asunto(reserva), f'Reserva reagendada #{reserva.pk} — 2026-12-14 07:00')


class FallosTests(_Base):
    @override_settings(**LLAVES)
    @mock.patch(POST)
    def test_sin_correo_del_cliente_devuelve_false_con_motivo_y_no_llama_a_la_red(self, post):
        reserva = self.reserva(correo_cliente='')

        self.assertFalse(enviar_correo_reagendado(reserva, Antes()))

        self.assertEqual(reserva.motivo_fallo_aviso, 'la reserva no tiene correo del cliente')
        post.assert_not_called()

    @override_settings(RESEND_API_KEY='', RESEND_FROM='')
    @mock.patch(POST)
    def test_sin_resend_devuelve_false_con_motivo_y_no_llama_a_la_red(self, post):
        reserva = self.reserva()

        self.assertFalse(enviar_correo_reagendado(reserva, Antes()))

        self.assertEqual(reserva.motivo_fallo_aviso, 'el envio de correos no esta configurado en el servidor')
        post.assert_not_called()

    @override_settings(**LLAVES)
    @mock.patch(POST)
    def test_resend_caido_devuelve_false_sin_lanzar_y_dice_por_que(self, post):
        post.side_effect = requests.ConnectionError('resend caido')
        reserva = self.reserva()

        self.assertFalse(enviar_correo_reagendado(reserva, Antes()))

        self.assertIn('resend caido', reserva.motivo_fallo_aviso)
        self.assertIn('proveedor de correo', reserva.motivo_fallo_aviso)

    @override_settings(**LLAVES)
    @mock.patch(POST)
    def test_si_resend_rechaza_el_motivo_es_su_mensaje(self, post):
        respuesta = mock.Mock()
        respuesta.text = '{"message": "El dominio no esta verificado"}'
        respuesta.json.return_value = {'message': 'El dominio no esta verificado'}
        post.return_value.raise_for_status.side_effect = requests.HTTPError('403', response=respuesta)
        reserva = self.reserva()

        self.assertFalse(enviar_correo_reagendado(reserva, Antes()))

        self.assertIn('El dominio no esta verificado', reserva.motivo_fallo_aviso)

    @override_settings(**LLAVES)
    @mock.patch(POST)
    def test_si_no_se_puede_armar_el_correo_tampoco_lanza(self, post):
        reserva = self.reserva()

        with mock.patch.object(correo_reagendado, '_cuerpo_html', side_effect=RuntimeError('boom')):
            self.assertFalse(enviar_correo_reagendado(reserva, Antes()))

        self.assertTrue(reserva.motivo_fallo_aviso)
        post.assert_not_called()

    @override_settings(**LLAVES)
    @mock.patch(POST)
    def test_un_envio_exitoso_deja_el_motivo_vacio(self, post):
        reserva = self.reserva()
        reserva.motivo_fallo_aviso = 'de una vez anterior'

        self.assertTrue(enviar_correo_reagendado(reserva, Antes()))

        self.assertEqual(reserva.motivo_fallo_aviso, '')

    @override_settings(**LLAVES)
    @mock.patch(POST)
    def test_un_antes_incompleto_no_lo_rompe(self, post):
        """`antes` se lee con getattr: un objeto sin atributos no tumba el correo."""
        self.assertTrue(enviar_correo_reagendado(self.reserva(), object()))


class CopiaAlNegocioTests(_Base):
    @override_settings(**LLAVES, RESEND_BCC=['operacion@ejemplo.com'])
    @mock.patch(POST)
    def test_manda_copia_oculta_al_negocio(self, post):
        self.assertTrue(enviar_correo_reagendado(self.reserva(), Antes()))

        cuerpo = _enviado(post)
        self.assertEqual(cuerpo['bcc'], ['operacion@ejemplo.com'])
        self.assertEqual(cuerpo['to'], ['ana@example.com'])
        self.assertNotIn('cc', cuerpo)

    @override_settings(**LLAVES, RESEND_BCC=[])
    @mock.patch(POST)
    def test_sin_bcc_configurado_no_manda_la_clave(self, post):
        self.assertTrue(enviar_correo_reagendado(self.reserva(), Antes()))

        self.assertNotIn('bcc', _enviado(post))
