"""Telefono con codigo de pais (ARCH-telefono-con-pais, backend).

El backend solo acepta MAS que antes, nunca menos: todo lo que ya pasaba (o fallaba)
sigue igual, y se agregan los internacionales con `+` de 7 a 9 digitos (Andorra,
Groenlandia, Malvinas) que antes se rechazaban por tener menos de 10.
"""
import time as reloj
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca

from .models import Reserva
from .telefono import LADA_PAIS, telefono_marcable
from .validators import validar_telefono


def pasa(numero):
    try:
        validar_telefono(numero)
    except ValidationError:
        return False
    return True


class ValidarTelefonoInternacionalTests(SimpleTestCase):
    def test_acepta_los_internacionales_cortos_con_mas(self):
        for numero in ('+376 312 345', '+299 321000', '+47 41234567', '+500 51234'):
            with self.subTest(numero=numero):
                self.assertTrue(pasa(numero))

    def test_sigue_aceptando_los_formatos_de_siempre(self):
        for numero in ('612 123 4567', '6121234567', '+52 1 612 123 4567', '(612) 123-4567',
                       '+526121234567', '+52 612 123 4567', '+1 212 555 1234'):
            with self.subTest(numero=numero):
                self.assertTrue(pasa(numero))

    def test_sigue_rechazando_lo_que_no_es_un_telefono(self):
        for numero in ('+52 612 123', '+1 212', '+1 2125551', '+52 6121234', '123', 'asdf', '+', '',
                       '612 123', '+376 31', '376 312 345'):
            with self.subTest(numero=numero):
                self.assertFalse(pasa(numero))

    def test_los_digitos_no_ascii_no_pasan_como_telefono(self):
        # Arabes y de ancho completo: `\d` los contaba y el validador los dejaba pasar.
        for texto in ('+٥٢٦١٢١٢٣٤٥٦٧', '٦١٢١٢٣٤٥٦٧٨', '＋５２６１２１２３４５６７'):
            with self.assertRaises(ValidationError, msg=texto):
                validar_telefono(texto)

    def test_los_cortos_solo_valen_con_el_mas_adelante(self):
        # Sin el `+` un numero de 9 digitos sigue siendo incompleto (podria ser mexicano a medias).
        self.assertFalse(pasa('376312345'))
        self.assertFalse(pasa('376 312 345 +'))

    def test_rechaza_mas_de_15_digitos(self):
        self.assertFalse(pasa('+1234567890123456'))
        self.assertTrue(pasa('+123456789012345'))

    def test_los_mensajes_de_error_no_cambian(self):
        with self.assertRaises(ValidationError) as incompleto:
            validar_telefono('+1 212')
        self.assertIn('esta incompleto', incompleto.exception.messages[0])
        with self.assertRaises(ValidationError) as letras:
            validar_telefono('asdf')
        self.assertIn('solo puede llevar numeros', letras.exception.messages[0])
        with self.assertRaises(ValidationError) as largo:
            validar_telefono('+1234567890123456')
        self.assertIn('mas de 15 digitos', largo.exception.messages[0])

    def test_entrada_hostil_con_digitos_no_ascii_no_cuenta_como_internacional_corto(self):
        # Digitos arabes: miden 9 pero no son digitos de marcar.
        self.assertFalse(pasa('+٣٧٦٣١٢٣٤٥'))
        # Mezcla: 8 ASCII + 1 arabe no se cuela como corto.
        self.assertFalse(pasa('+376 312 34٥'))

    def test_cadenas_enormes_se_rechazan_rapido(self):
        for texto in ('+' + '1' * 200_000, '+' + ' ' * 200_000 + '1', '(' * 200_000, '9' * 200_000):
            with self.subTest(largo=len(texto)):
                inicio = reloj.monotonic()
                self.assertFalse(pasa(texto))
                self.assertLess(reloj.monotonic() - inicio, 1.0)

    def test_el_error_no_lleva_el_numero(self):
        for numero in ('+1 212', '+376 31', 'asdf-7788'):
            with self.assertRaises(ValidationError) as ctx:
                validar_telefono(numero)
            self.assertNotIn(numero, ' '.join(ctx.exception.messages))


class TelefonoMarcableTests(SimpleTestCase):
    def test_con_mas_devuelve_los_digitos_sin_anteponer_52(self):
        self.assertEqual(telefono_marcable('+47 41234567'), '4741234567')
        self.assertEqual(telefono_marcable('+376 312 345'), '376312345')
        self.assertEqual(telefono_marcable('+526121234567'), '526121234567')
        self.assertEqual(telefono_marcable('+52 1 612 123 4567'), '5216121234567')

    def test_sin_mas_se_comporta_como_siempre(self):
        self.assertEqual(telefono_marcable('612 123 4567'), '526121234567')
        self.assertEqual(telefono_marcable('(612) 123-4567'), '526121234567')
        self.assertEqual(telefono_marcable('526121234567'), '526121234567')
        self.assertEqual(telefono_marcable('612'), '')
        self.assertEqual(telefono_marcable('612 1234'), '')
        self.assertEqual(telefono_marcable(''), '')
        self.assertEqual(telefono_marcable(None), '')

    def test_con_mas_pero_incompleto_devuelve_vacio(self):
        self.assertEqual(telefono_marcable('+52 612 123'), '')
        self.assertEqual(telefono_marcable('+1 212'), '')
        self.assertEqual(telefono_marcable('+'), '')

    def test_solo_cuenta_digitos_ascii(self):
        self.assertEqual(telefono_marcable('+٣٧٦٣١٢٣٤٥'), '')

    def test_cadena_enorme_responde_rapido(self):
        inicio = reloj.monotonic()
        telefono_marcable('+' + '1' * 200_000)
        self.assertLess(reloj.monotonic() - inicio, 1.0)

    def test_la_lada_de_pais_sigue_siendo_52(self):
        self.assertEqual(LADA_PAIS, '52')

    def test_admin_sigue_exportando_los_nombres(self):
        # `vistas_enlace_pago.py` y varias pruebas los importan de aqui.
        from apps.bookings import admin

        self.assertIs(admin.telefono_marcable, telefono_marcable)
        self.assertEqual(admin.LADA_PAIS, LADA_PAIS)


class ReservaConTelefonoInternacionalTests(ApiTestCase):
    """Un POST a `reservas/` con un numero corto del extranjero ya no devuelve 400."""

    def enviar(self, telefono):
        servicio = crear_servicio_pesca(self.empresa)
        crear_flota(self.empresa)
        datos = {
            'checkout_id': str(uuid.uuid4()),
            'fecha': str(date.today() + timedelta(days=10)),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': telefono,
            'correo_cliente': 'ana@example.com',
            'moneda': 'USD',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'servicio': servicio.slug,
        }
        return self.client.post(
            f'/api/{self.empresa.slug}/reservas/', datos, content_type='application/json',
        )

    def test_andorra_se_guarda_tal_cual(self):
        respuesta = self.enviar('+376 312 345')
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(Reserva.objects.get(pk=respuesta.json()['id']).telefono_cliente, '+376 312 345')

    def test_el_compacto_nuevo_y_los_formatos_viejos_pasan(self):
        for telefono in ('+526121234567', '+47 41234567', '612 123 4567', '(612) 123-4567'):
            with self.subTest(telefono=telefono):
                respuesta = self.enviar(telefono)
                self.assertEqual(respuesta.status_code, 201, respuesta.content)

    def test_un_numero_imposible_sigue_dando_400(self):
        for telefono in ('+52 612 123', '+1 212', 'asdf'):
            with self.subTest(telefono=telefono):
                self.assertEqual(self.enviar(telefono).status_code, 400)


class OrdenConTelefonoInternacionalTests(TestCase):
    """Lo mismo para `ordenes/` (paquete de dos empresas), que tambien hace `full_clean()`."""

    def setUp(self):
        super().setUp()
        from apps.fleet.enums import TipoTraslado
        from apps.fleet.models import Paquete, PaqueteServicio, Servicio, TransporteTarifa
        from apps.tenancy import scope
        from apps.tenancy.models import Empresa, Sede

        self.sede = Sede.objects.create(nombre='Sede Tel', slug='sede-tel', activo=True)
        self.lider = Empresa.objects.create(sede=self.sede, nombre='Pesca Tel', slug='pesca-tel', activo=True)
        self.transporte = Empresa.objects.create(sede=self.sede, nombre='Transporte Tel', slug='transp-tel', activo=True)
        with scope.como_operador_plataforma():
            self.pesca = Servicio.objects.create(
                empresa=self.lider, nombre='Pesca Tel', slug='pesca-svc-tel', tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia', precio_base=Decimal('4000.00'),
            )
            self.traslado = Servicio.objects.create(
                empresa=self.transporte, nombre='Traslado Tel', slug='traslado-svc-tel', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
            )
            TransporteTarifa.objects.create(
                empresa=self.transporte, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                personas_min=1, personas_max=4, precio=Decimal('2000.00'),
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.lider, nombre='Pesca y Traslado Tel',
                slug='paquete-tel', precio_ancla=Decimal('5000.00'), permite_anticipo=False,
            )
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.pesca, orden=1)
            PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.traslado, orden=2)

    def enviar(self, telefono):
        from apps.fleet.enums import TipoTraslado

        inicio = date.today() + timedelta(days=15)
        datos = {
            'checkout_id': str(uuid.uuid4()),
            'paquete': self.paquete.slug,
            'nombre_cliente': 'Carlos Lopez',
            'telefono_cliente': telefono,
            'correo_cliente': 'carlos@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Carlos Lopez',
            'fecha': str(inicio),
            'hora': '07:00:00',
            'componentes': [
                {'servicio': self.pesca.slug, 'numero_personas': 2},
                {'servicio': self.traslado.slug, 'numero_personas': 2},
            ],
            'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
            'direccion_personalizada': 'Calle Marina 123',
            'fecha_regreso': str(inicio + timedelta(days=2)),
        }
        return self.client.post(f'/api/{self.sede.slug}/ordenes/', datos, content_type='application/json')

    def test_andorra_no_devuelve_400(self):
        respuesta = self.enviar('+376 312 345')
        self.assertEqual(respuesta.status_code, 201, respuesta.content)

    def test_un_numero_imposible_sigue_dando_400(self):
        self.assertEqual(self.enviar('+52 612 123').status_code, 400)
