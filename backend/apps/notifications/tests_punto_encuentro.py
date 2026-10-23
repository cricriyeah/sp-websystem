"""El punto de encuentro de los correos sale de los datos de cada servicio.

Antes el texto «Marina La Costa, Rangel y Navarro, La Paz, BCS» estaba escrito en el codigo y
salia en el correo de confirmacion, en el de asignacion de panga/capitan y en el de paquetes
de TODAS las empresas, aunque la salida fuera de otro lugar. Ahora sale de
`Servicio.punto_salida` (el «Sales de» de la ficha del servicio en el admin); si esta vacio
no se inventa un lugar: el correo dice que se confirma por WhatsApp.
"""
from datetime import date, time, timedelta
from unittest import mock

from django.test import override_settings

from apps.bookings.models import Reserva
from apps.fleet.models import Capitan, Embarcacion
from apps.tenancy.models import Empresa, Sede
from apps.testing import EmpresaTestCase, OperadorTestCase, crear_servicio_pesca

from .services import (
    SIN_PUNTO_DE_ENCUENTRO,
    _cuerpo_asignacion_html,
    _cuerpo_html,
    enviar_correo_asignacion,
)

LLAVES = {'RESEND_API_KEY': 'test-key', 'RESEND_FROM': 'reservas@ejemplo.com'}
MARINA_VIEJA = 'Rangel y Navarro'  # parte del texto que estaba fijo en el codigo


def reserva_de(empresa, servicio):
    return Reserva(
        empresa=empresa, servicio=servicio,
        fecha=date.today() + timedelta(days=10), hora=time(6, 0), numero_personas=2,
        nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567',
        correo_cliente='ana@example.com', moneda='MXN',
        deslinde_aceptado=True, deslinde_nombre='Ana Ruiz',
    )


def asignada(empresa, servicio):
    embarcacion = Embarcacion.objects.create(
        empresa=empresa, nombre='Dona Chuy', clase=Embarcacion.Clase.CHICA, capacidad_maxima=6,
    )
    capitan = Capitan.objects.create(empresa=empresa, nombre='Ramon Geraldo', telefono='+5216129876543')
    reserva = reserva_de(empresa, servicio)
    reserva.estado = Reserva.Estado.ASIGNADA
    reserva.embarcacion = embarcacion
    reserva.capitan = capitan
    reserva.save()
    return reserva


class PuntoDeEncuentroDelCorreoDeAsignacionTests(EmpresaTestCase):
    def test_el_correo_dice_el_punto_de_salida_del_servicio(self):
        servicio = crear_servicio_pesca(self.empresa, punto_salida='Muelle de Bahia de los Sueños')

        html = _cuerpo_asignacion_html(asignada(self.empresa, servicio))

        self.assertIn('Muelle de Bahia de los Sueños', html)
        self.assertNotIn(MARINA_VIEJA, html)

    def test_sin_dato_no_inventa_un_lugar(self):
        servicio = crear_servicio_pesca(self.empresa)  # punto_salida vacio

        html = _cuerpo_asignacion_html(asignada(self.empresa, servicio))

        self.assertNotIn(MARINA_VIEJA, html)
        self.assertNotIn('Marina La Costa', html)
        self.assertIn(SIN_PUNTO_DE_ENCUENTRO, html)

    def test_un_valor_de_solo_espacios_cuenta_como_vacio(self):
        servicio = crear_servicio_pesca(self.empresa, punto_salida='   ')

        html = _cuerpo_asignacion_html(asignada(self.empresa, servicio))

        self.assertIn(SIN_PUNTO_DE_ENCUENTRO, html)

    def test_el_punto_se_escapa(self):
        servicio = crear_servicio_pesca(self.empresa, punto_salida='<b>Muelle</b> & co')

        html = _cuerpo_asignacion_html(asignada(self.empresa, servicio))

        self.assertIn('&lt;b&gt;Muelle&lt;/b&gt; &amp; co', html)
        self.assertNotIn('<b>Muelle</b>', html)

    @override_settings(**LLAVES)
    @mock.patch('apps.notifications.services.requests.post')
    def test_el_envio_usa_el_punto_del_servicio(self, post):
        servicio = crear_servicio_pesca(self.empresa, punto_salida='Muelle Norte')

        self.assertTrue(enviar_correo_asignacion(asignada(self.empresa, servicio)))

        self.assertIn('Muelle Norte', post.call_args.kwargs['json']['html'])


class PuntoDeEncuentroPorEmpresaTests(OperadorTestCase):
    """Cada empresa dice su lugar: el texto ya no es el mismo para todas."""

    def test_dos_empresas_dicen_cada_una_su_lugar(self):
        sede = Sede.objects.create(nombre='Sede pe', slug='sede-pe')
        uno = Empresa.objects.create(sede=sede, nombre='Empresa Uno', slug='uno-pe')
        dos = Empresa.objects.create(sede=sede, nombre='Empresa Dos', slug='dos-pe')
        sin_dato = Empresa.objects.create(sede=sede, nombre='Empresa Tres', slug='tres-pe')
        html_uno = _cuerpo_asignacion_html(
            asignada(uno, crear_servicio_pesca(uno, punto_salida='Marina Uno')))
        html_dos = _cuerpo_asignacion_html(
            asignada(dos, crear_servicio_pesca(dos, punto_salida='Playa Dos')))
        html_tres = _cuerpo_asignacion_html(asignada(sin_dato, crear_servicio_pesca(sin_dato)))

        self.assertIn('Marina Uno', html_uno)
        self.assertNotIn('Playa Dos', html_uno)
        self.assertIn('Playa Dos', html_dos)
        self.assertNotIn('Marina Uno', html_dos)
        self.assertIn(SIN_PUNTO_DE_ENCUENTRO, html_tres)
        self.assertNotIn('Marina', html_tres)


class PuntoDeEncuentroDelCorreoDeConfirmacionTests(EmpresaTestCase):
    def test_la_confirmacion_dice_el_punto_de_salida_del_servicio(self):
        servicio = crear_servicio_pesca(self.empresa, punto_salida='Muelle Norte')

        html = _cuerpo_html(reserva_de(self.empresa, servicio))

        self.assertIn('Muelle Norte', html)
        self.assertNotIn(MARINA_VIEJA, html)

    def test_la_confirmacion_sin_dato_no_inventa_un_lugar(self):
        servicio = crear_servicio_pesca(self.empresa)

        html = _cuerpo_html(reserva_de(self.empresa, servicio))

        self.assertNotIn(MARINA_VIEJA, html)
        self.assertIn(SIN_PUNTO_DE_ENCUENTRO, html)

    def test_un_hospedaje_sin_dato_no_pide_punto_de_encuentro(self):
        # Llegar a un hotel no es «encontrarse» en un muelle: sin dato no se escribe nada.
        servicio = crear_servicio_pesca(
            self.empresa, slug='hotel-pe', nombre='Hotel', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche',
        )

        html = _cuerpo_html(reserva_de(self.empresa, servicio))

        self.assertNotIn('Punto de encuentro', html)
        self.assertNotIn(MARINA_VIEJA, html)
