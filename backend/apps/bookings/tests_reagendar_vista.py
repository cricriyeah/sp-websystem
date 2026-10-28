"""La vista «Reagendar» del backoffice (ARCH-reagendar-reserva.md §6, DESIGN-reagendar-reserva.md).

El servicio (`apps.bookings.reagendar`) lo escribe otra pieza: aqui se parchea `proponer`, `reagendar` y
`motivo_no_reagendable`, y se prueba lo que es de la vista: permisos, los dos pasos, los textos, el repintado con
errores, `volver` saneado, la casilla del correo, el History y la notificacion persistente.
"""
import re
from datetime import date, time, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bookings import reagendar as servicio
from apps.bookings.reagendar_vista import fecha_larga
from apps.bookings.tests_agenda import datos
from apps.testing import crear_flota, crear_servicio_pesca
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Notificacion, Sede

from .models import DetalleTransporte, Reserva

PROPONER = 'apps.bookings.reagendar.proponer'
REAGENDAR = 'apps.bookings.reagendar.reagendar'
MOTIVO = 'apps.bookings.reagendar.motivo_no_reagendable'
DISPONIBILIDAD = 'apps.bookings.reagendar_vista.disponibilidad_por_fecha'

CORREO = 'ana@example.com'
TELEFONO = '+5216121234567'


def parche_proponer(*args, **kwargs):
    """`mock.patch` de `reagendar.proponer` que tambien funciona mientras la funcion aun no existe.

    La vista solo la usa a traves del modulo (`reagendar.proponer(...)`). El servicio lo entrega otra pieza; con
    `create=True` estas pruebas no dependen de que ya este, y cuando exista el parche la reemplaza igual."""
    kwargs.setdefault('create', True)
    return mock.patch(PROPONER, *args, **kwargs)


class _ErrorDeReagendado(servicio.ErrorDeReagendado):
    """Se arma sin depender de la firma del constructor real: la vista solo lee `.mensaje` y `.campo`."""

    def __init__(self, mensaje, campo=''):
        Exception.__init__(self, mensaje)
        self.mensaje = mensaje
        self.campo = campo


def propuesta(**cambios):
    base = dict(
        fecha=None, hora=None, inicio_paquete=None, fecha_salida=None, fecha_regreso=None, dias_de_mar=[],
        panga=None, capitan=None, motivo_panga='', vehiculos_a_quitar=0, motivo_sin_cupo=None, proxima_fecha=None,
        requiere_excepcion_48h=False, limite_48h=None, errores={},
    )
    base.update(cambios)
    return SimpleNamespace(**base)


def antes_del_cambio(**cambios):
    base = dict(fecha=None, hora=None, inicio_paquete=None, fecha_salida=None, fecha_regreso=None, panga='', capitan='')
    base.update(cambios)
    return SimpleNamespace(**base)


def etiqueta(html, nombre):
    """La etiqueta <input ... name="nombre" ...> completa, o '' si no esta."""
    for etiqueta_input in re.findall(r'<input[^>]*>', html):
        if re.search(rf'name="{re.escape(nombre)}"', etiqueta_input):
            return etiqueta_input
    return ''


class FechaLargaTests(SimpleTestCase):
    def test_dia_de_la_semana_fecha_y_hora_en_un_solo_formato(self):
        self.assertEqual(fecha_larga(date(2026, 12, 8), time(6, 0)), 'martes 8 de diciembre de 2026 · 6:00 a. m.')

    def test_sin_hora_solo_el_dia(self):
        self.assertEqual(fecha_larga(date(2026, 12, 9)), 'miércoles 9 de diciembre de 2026')

    def test_tarde_en_formato_de_doce_horas(self):
        self.assertEqual(fecha_larga(date(2026, 1, 1), time(13, 5)), 'jueves 1 de enero de 2026 · 1:05 p. m.')

    def test_medianoche_y_mediodia(self):
        self.assertTrue(fecha_larga(date(2026, 1, 1), time(0, 0)).endswith('12:00 a. m.'))
        self.assertTrue(fecha_larga(date(2026, 1, 1), time(12, 0)).endswith('12:00 p. m.'))

    def test_sin_fecha_es_vacio(self):
        self.assertEqual(fecha_larga(None, time(6, 0)), '')


class CssPropioTests(SimpleTestCase):
    """Regla del dueno: esquinas rectas o circulo, sin sombras ni degradados; nada de Tailwind inventado."""

    def setUp(self):
        ruta = Path(__file__).resolve().parent / 'static' / 'bookings' / 'reagendar.css'
        self.css = ruta.read_text(encoding='utf-8')

    def test_sin_sombras_ni_degradados(self):
        self.assertNotIn('box-shadow', self.css)
        self.assertNotIn('text-shadow', self.css)
        self.assertNotIn('gradient', self.css)

    def test_solo_esquinas_rectas_o_circulo(self):
        for valor in re.findall(r'border-radius:\s*([^;]+);', self.css):
            self.assertIn(valor.strip(), ('0', '50%', '999px'), valor)

    def test_tiene_modo_oscuro(self):
        self.assertIn('.dark', self.css)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede reagendar', slug='sede-reagendar')
        cls.empresa = Empresa.objects.create(sede=sede, nombre='Sal y Sol Test', slug='sal-sol-reagendar')
        cls.otra = Empresa.objects.create(sede=sede, nombre='Otra Empresa', slug='otra-reagendar')
        Usuario = get_user_model()

        cls.jefa = Usuario.objects.create_user('jefa-rg', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=cls.jefa, empresa=cls.empresa, rol=MembresiaEmpresa.Rol.JEFE)
        cls.vendedora = Usuario.objects.create_user('vendedora-rg', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=cls.vendedora, empresa=cls.empresa, rol=MembresiaEmpresa.Rol.VENDEDORA)
        cls.lectora = Usuario.objects.create_user('lectora-rg', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=cls.lectora, empresa=cls.empresa, rol=MembresiaEmpresa.Rol.VENDEDORA)
        cls.lectora.groups.clear()
        cls.lectora.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        cls.jefa_otra = Usuario.objects.create_user('jefa-otra-rg', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=cls.jefa_otra, empresa=cls.otra, rol=MembresiaEmpresa.Rol.JEFE)
        cls.operador = Usuario.objects.create_user('operador-rg', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))

    def setUp(self):
        self.hoy = timezone.localdate()
        self.fecha_actual = self.hoy + timedelta(days=10)
        self.fecha_nueva = self.hoy + timedelta(days=12)
        with scope.como_operador_plataforma():
            crear_flota(self.empresa)
            self.reserva = Reserva.objects.create(**datos(
                self.empresa, fecha=self.fecha_actual, hora=time(6, 0), nombre_cliente='Ana Ruiz',
                telefono_cliente=TELEFONO, correo_cliente=CORREO, numero_personas=3,
            ))
            crear_flota(self.otra)
            self.reserva_ajena = Reserva.objects.create(**datos(self.otra, fecha=self.fecha_actual))
        self.url = reverse('admin:bookings_reserva_reagendar', args=[self.reserva.pk])
        self.ficha = reverse('admin:bookings_reserva_change', args=[self.reserva.pk])
        self.client.force_login(self.jefa)

    def _post(self, **campos):
        datos_post = {'paso': 'revisar', 'nueva_fecha': self.fecha_nueva.isoformat(), 'nueva_hora': '06:00'}
        datos_post.update(campos)
        return self.client.post(self.url, datos_post)

    def _reserva(self):
        """Relee la reserva: con RLS (Postgres) una consulta fuera de un alcance no ve nada."""
        with scope.como_operador_plataforma():
            return Reserva.objects.get(pk=self.reserva.pk)

    def _actualizar(self, **cambios):
        with scope.como_operador_plataforma():
            Reserva.objects.filter(pk=self.reserva.pk).update(**cambios)

    def _html(self, respuesta):
        return respuesta.content.decode()

    def _mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]

    def _resultado(self, **cambios):
        """Lo que devolveria el servicio: la reserva ya con la fecha nueva (solo en memoria)."""
        reserva = self._reserva()
        reserva.fecha = self.fecha_nueva
        base = dict(
            reserva=reserva, antes=antes_del_cambio(fecha=self.fecha_actual, hora=time(6, 0)),
            panga_conservada=False, capitan_conservado=False, vehiculos_quitados=0, excepcion_48h=False,
            correo_encolado=True,
        )
        base.update(cambios)
        return SimpleNamespace(**base)

    def _datos_de_confirmar(self, **campos):
        datos_post = {
            'paso': 'confirmar', 'nueva_fecha': self.fecha_nueva.isoformat(), 'nueva_hora': '06:00',
            'avisar_cliente': '1', 'token_fecha': self.fecha_actual.isoformat(), 'token_hora': '06:00:00',
            'token_inicio_paquete': '', 'token_estado': 'pagada',
        }
        datos_post.update(campos)
        return datos_post


class PermisosYAlcanceTests(_Base):
    def test_una_reserva_de_otra_empresa_es_404(self):
        url = reverse('admin:bookings_reserva_reagendar', args=[self.reserva_ajena.pk])

        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'paso': 'revisar'}).status_code, 404)

    def test_sin_permiso_de_cambiar_reservas_es_403(self):
        self.client.force_login(self.lectora)

        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {'paso': 'revisar'}).status_code, 403)

    def test_la_vendedora_puede_abrirla(self):
        self.client.force_login(self.vendedora)

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_el_operador_de_plataforma_puede_abrirla(self):
        self.client.force_login(self.operador)

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_sin_sesion_manda_al_login(self):
        self.client.logout()

        self.assertEqual(self.client.get(self.url).status_code, 302)


class PasoUnoTests(_Base):
    def test_muestra_el_encabezado_la_pregunta_y_la_fecha_de_ahora(self):
        respuesta = self.client.get(self.url)
        html = self._html(respuesta)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'Reagendar reserva #{self.reserva.pk}')
        self.assertContains(respuesta, 'Ana Ruiz')
        self.assertContains(respuesta, '3 personas')
        self.assertContains(respuesta, '¿Para cuándo?')
        self.assertContains(respuesta, f'Ahora: {fecha_larga(self.fecha_actual, time(6, 0))}')
        self.assertContains(respuesta, 'Revisar cambio')
        self.assertContains(respuesta, 'Volver a la reserva')
        self.assertContains(respuesta, 'Se revisa el lugar y la panga antes de confirmar.')
        self.assertIn(f'value="{self.fecha_actual.isoformat()}"', etiqueta(html, 'nueva_fecha'))
        self.assertIn('type="date"', etiqueta(html, 'nueva_fecha'))
        self.assertIn('value="06:00"', etiqueta(html, 'nueva_hora'))
        self.assertIn('value="revisar"', etiqueta(html, 'paso'))

    def test_el_nombre_del_cliente_se_escapa(self):
        self._actualizar(nombre_cliente='<script>alert(1)</script>')

        respuesta = self.client.get(self.url)

        self.assertNotContains(respuesta, '<script>alert(1)</script>')
        self.assertContains(respuesta, '&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_el_paso_uno_no_pide_fecha_de_regreso_en_un_servicio_normal(self):
        respuesta = self.client.get(self.url)

        self.assertNotContains(respuesta, 'Nueva fecha de regreso')

    def test_un_traslado_redondo_de_aeropuerto_pide_la_fecha_de_regreso(self):
        with scope.como_operador_plataforma():
            traslado = crear_servicio_pesca(
                self.empresa, slug='traslado-rg', nombre='Traslado', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', hora_apertura=None, hora_cierre=None,
            )
            reserva = Reserva.objects.create(**datos(self.empresa, servicio=traslado, fecha=self.fecha_actual, hora=None))
            DetalleTransporte.objects.create(
                reserva=reserva, tipo_traslado='redondo_aeropuerto', direccion_personalizada='Hotel',
                fecha_regreso=self.fecha_actual + timedelta(days=3),
            )
        url = reverse('admin:bookings_reserva_reagendar', args=[reserva.pk])

        respuesta = self.client.get(url)
        html = self._html(respuesta)

        self.assertContains(respuesta, 'Nueva fecha de regreso')
        self.assertIn(f'value="{(self.fecha_actual + timedelta(days=3)).isoformat()}"',
                      etiqueta(html, 'nueva_fecha_regreso'))
        self.assertNotContains(respuesta, 'Próximas fechas con lugar')

    def test_un_servicio_sin_hora_ni_ventana_no_pide_hora(self):
        with scope.como_operador_plataforma():
            traslado = crear_servicio_pesca(
                self.empresa, slug='traslado-sin-hora', nombre='Traslado', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', hora_apertura=None, hora_cierre=None,
            )
            reserva = Reserva.objects.create(**datos(self.empresa, servicio=traslado, fecha=self.fecha_actual, hora=None))

        respuesta = self.client.get(reverse('admin:bookings_reserva_reagendar', args=[reserva.pk]))

        self.assertEqual(etiqueta(self._html(respuesta), 'nueva_hora'), '')


class FechasConLugarTests(_Base):
    def _disponibilidad(self, libres):
        mapa = {self.hoy + timedelta(days=n): (None if n in libres else 'lleno') for n in range(1, 61)}
        return mock.patch(DISPONIBILIDAD, return_value=mapa)

    def test_muestra_hasta_cinco_fechas_con_lugar_como_chips(self):
        with self._disponibilidad({2, 3, 4, 5, 6, 7, 8}) as parche:
            respuesta = self.client.get(self.url)
        html = self._html(respuesta)

        self.assertContains(respuesta, 'Próximas fechas con lugar')
        self.assertEqual(len(re.findall(r'data-fecha="\d{4}-\d{2}-\d{2}"', html)), 5)
        self.assertIn(f'data-fecha="{(self.hoy + timedelta(days=2)).isoformat()}"', html)
        self.assertNotIn(f'data-fecha="{(self.hoy + timedelta(days=7)).isoformat()}"', html)
        # El cupo de la propia reserva no cuenta contra ella misma.
        self.assertEqual(parche.call_args.kwargs.get('excluir_pk'), self.reserva.pk)

    def test_el_chip_dice_dia_corto_y_fecha(self):
        manana = self.hoy + timedelta(days=1)
        with self._disponibilidad({1}):
            respuesta = self.client.get(self.url)

        dias = ('lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom')
        meses = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')
        self.assertContains(respuesta, f'{dias[manana.weekday()]} {manana.day} {meses[manana.month - 1]}')

    def test_sin_lugar_en_dos_meses_lo_dice(self):
        with self._disponibilidad(set()):
            respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'No hay lugar en los próximos 60 días.')

    def test_un_servicio_que_no_es_de_mar_no_ofrece_chips(self):
        with scope.como_operador_plataforma():
            hospedaje = crear_servicio_pesca(
                self.empresa, slug='hotel-rg', nombre='Hotel', tipo_servicio='hospedaje',
                estrategia_cupo='por_noche', hora_apertura=None, hora_cierre=None,
            )
            reserva = Reserva.objects.create(**datos(self.empresa, servicio=hospedaje, fecha=self.fecha_actual, hora=None))

        with mock.patch(DISPONIBILIDAD) as parche:
            respuesta = self.client.get(reverse('admin:bookings_reserva_reagendar', args=[reserva.pk]))

        parche.assert_not_called()
        self.assertNotContains(respuesta, 'Próximas fechas con lugar')


class PasoDosTests(_Base):
    def _revisar(self, **cambios):
        with parche_proponer(return_value=propuesta(fecha=self.fecha_nueva, hora=time(6, 0), **cambios)) as parche:
            respuesta = self._post()
        return respuesta, parche

    def test_pide_al_servicio_la_propuesta_con_lo_que_se_tecleo(self):
        regreso = self.fecha_nueva + timedelta(days=2)
        with parche_proponer(return_value=propuesta(fecha=self.fecha_nueva, hora=time(7, 0))) as parche:
            self._post(nueva_hora='07:00', nueva_fecha_regreso=regreso.isoformat())

        parche.assert_called_once()
        self.assertEqual(parche.call_args.args[0].pk, self.reserva.pk)
        self.assertEqual(parche.call_args.kwargs['nueva_fecha'], self.fecha_nueva)
        self.assertEqual(parche.call_args.kwargs['nueva_hora'], time(7, 0))

    def test_muestra_el_antes_y_el_ahora_con_el_mismo_formato(self):
        respuesta, _ = self._revisar()
        html = self._html(respuesta)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Revisa antes de confirmar')
        self.assertContains(respuesta, fecha_larga(self.fecha_actual))
        self.assertContains(respuesta, fecha_larga(self.fecha_nueva))
        self.assertIn('Antes', html)
        self.assertIn('Ahora', html)
        self.assertContains(respuesta, 'Cambiar la fecha')

    def test_resalta_solo_la_parte_que_cambio(self):
        respuesta, _ = self._revisar()
        html = self._html(respuesta)

        # Cambio la fecha; la hora (6:00 a. m.) es la misma y no se resalta.
        self.assertRegex(html, r'rg-cambio[^>]*>\s*' + re.escape(fecha_larga(self.fecha_nueva)))
        self.assertNotRegex(html, r'rg-cambio[^>]*>\s*6:00 a\. m\.')

    def test_la_casilla_viene_marcada_y_el_boton_dice_reagendar_y_avisar(self):
        respuesta, _ = self._revisar()
        html = self._html(respuesta)

        casilla = etiqueta(html, 'avisar_cliente')
        self.assertIn('checked', casilla)
        self.assertNotIn('disabled', casilla)
        self.assertContains(respuesta, 'Avisar al cliente por correo')
        self.assertContains(respuesta, 'Reagendar y avisar al cliente')
        self.assertContains(respuesta, 'El cliente recibirá un correo con la nueva fecha.')
        self.assertContains(respuesta, 'Ana Ruiz · a***@example.com')
        self.assertNotContains(respuesta, CORREO)

    def test_las_dos_etiquetas_del_boton_viajan_para_que_la_casilla_las_cambie(self):
        respuesta, _ = self._revisar()

        self.assertContains(respuesta, 'data-texto-con-aviso="Reagendar y avisar al cliente"')
        self.assertContains(respuesta, 'data-texto-sin-aviso="Reagendar"')
        self.assertContains(respuesta, 'data-texto-enviando="Reagendando…"')

    def test_sin_correo_la_casilla_va_deshabilitada_y_desmarcada(self):
        self._actualizar(correo_cliente='')

        respuesta, _ = self._revisar()
        casilla = etiqueta(self._html(respuesta), 'avisar_cliente')

        self.assertIn('disabled', casilla)
        self.assertNotIn('checked', casilla)
        self.assertContains(respuesta, 'Esta reserva no tiene correo.')
        self.assertContains(respuesta, 'El cliente no tiene correo. Avísale por WhatsApp.')
        self.assertNotContains(respuesta, 'Reagendar y avisar al cliente')

    def test_el_pago_no_cambia_y_el_lugar_viejo_queda_libre(self):
        respuesta, _ = self._revisar()

        self.assertContains(respuesta, f'El pago no cambia. El lugar del {fecha_larga(self.fecha_actual)} queda libre.')

    def test_dice_que_pasa_con_la_panga_y_el_capitan(self):
        Reserva.objects.filter(pk=self.reserva.pk)  # la panga viene en la propuesta; el nombre de la reserva
        with scope.como_operador_plataforma():
            from apps.fleet.models import Capitan, Embarcacion
            panga = Embarcacion.objects.filter(empresa=self.empresa).first()
            capitan = Capitan.objects.create(empresa=self.empresa, nombre='Beto Lugo', telefono='1')
            self._actualizar(embarcacion=panga, capitan=capitan)

        casos = [
            (dict(panga='conserva', capitan='conserva'),
             f'Se conservan la panga {panga.nombre} y el capitán Beto Lugo.'),
            (dict(panga='quita', capitan='conserva'),
             f'Se quita la panga {panga.nombre}: hay que asignar otra en «Asignar pangas».'),
            (dict(panga='conserva', capitan='conserva'), 'Avísale al capitán Beto Lugo del nuevo día.'),
        ]
        for cambios, texto in casos:
            with self.subTest(texto=texto):
                respuesta, _ = self._revisar(**cambios)
                self.assertContains(respuesta, texto)

    def test_el_motivo_de_quitar_la_panga_se_muestra(self):
        with scope.como_operador_plataforma():
            from apps.fleet.models import Embarcacion
            panga = Embarcacion.objects.filter(empresa=self.empresa).first()
            self._actualizar(embarcacion=panga)

        respuesta, _ = self._revisar(panga='quita', motivo_panga='Ya sale con otro cliente ese día.')

        self.assertContains(respuesta, 'Ya sale con otro cliente ese día.')

    def test_avisa_del_vehiculo_que_se_quita(self):
        respuesta, _ = self._revisar(vehiculos_a_quitar=1)

        self.assertContains(respuesta, '«Asignar vehículos»')

    def test_los_datos_elegidos_y_el_token_viajan_en_campos_ocultos(self):
        respuesta, _ = self._revisar()
        html = self._html(respuesta)

        self.assertIn('value="confirmar"', etiqueta(html, 'paso'))
        self.assertIn(f'value="{self.fecha_nueva.isoformat()}"', etiqueta(html, 'nueva_fecha'))
        self.assertIn('value="06:00"', etiqueta(html, 'nueva_hora'))
        self.assertIn(f'value="{self.fecha_actual.isoformat()}"', etiqueta(html, 'token_fecha'))
        self.assertIn('value="06:00:00"', etiqueta(html, 'token_hora'))
        self.assertIn('value="pagada"', etiqueta(html, 'token_estado'))
        self.assertIn('token_inicio_paquete', html)

    def test_ningun_dato_de_dinero_aparece(self):
        respuesta, _ = self._revisar()

        for palabra in ('IVA', 'Saldo', 'Total de la reserva', 'MXN'):
            self.assertNotContains(respuesta, palabra)

    def test_cambiar_la_fecha_regresa_al_paso_uno_con_lo_tecleado(self):
        campos = self._datos_de_confirmar(nueva_hora='05:30', volver_a_elegir='1')
        with parche_proponer() as proponer, mock.patch(REAGENDAR) as reagendar:
            respuesta = self.client.post(self.url, campos)
        html = self._html(respuesta)

        proponer.assert_not_called()
        reagendar.assert_not_called()
        self.assertContains(respuesta, '¿Para cuándo?')
        self.assertNotContains(respuesta, 'Revisa antes de confirmar')
        self.assertIn(f'value="{self.fecha_nueva.isoformat()}"', etiqueta(html, 'nueva_fecha'))
        self.assertIn('value="05:30"', etiqueta(html, 'nueva_hora'))
        self.assertIn('value="revisar"', etiqueta(html, 'paso'))

    def test_el_primer_boton_del_formulario_es_el_de_confirmar(self):
        """Enter dentro del campo del motivo manda el primer boton: tiene que ser el primario, no «Cambiar la fecha»."""
        respuesta, _ = self._revisar(requiere_excepcion_48h=True)
        # Solo el formulario de la pantalla: Unfold trae mas botones de envio en la paleta de comandos y el idioma.
        formulario = re.search(r'<form[^>]*id="rg-confirmar-form".*?</form>', self._html(respuesta), re.S).group(0)

        botones = re.findall(r'<button[^>]*type="submit"[^>]*>', formulario)

        self.assertEqual(len(botones), 2)
        self.assertNotIn('volver_a_elegir', botones[0])
        self.assertIn('volver_a_elegir', botones[1])

    def test_el_paso_dos_no_tiene_casilla_ni_consecuencias_para_la_vendedora_bloqueada(self):
        self.client.force_login(self.vendedora)
        with parche_proponer(return_value=propuesta(
                fecha=self.fecha_nueva, hora=time(6, 0), requiere_excepcion_48h=True)):
            respuesta = self._post()

        self.assertEqual(etiqueta(self._html(respuesta), 'avisar_cliente'), '')
        self.assertNotContains(respuesta, 'El cliente recibirá un correo')
        self.assertNotContains(respuesta, 'Cambiar la fecha')


class ErroresDelPasoUnoTests(_Base):
    def test_el_error_del_servicio_sale_bajo_el_campo_y_conserva_lo_tecleado(self):
        error = {'nueva_fecha': 'Elige una fecha u hora distinta de la actual.'}
        with parche_proponer(return_value=propuesta(errores=error)):
            respuesta = self._post(nueva_hora='05:30')
        html = self._html(respuesta)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '¿Para cuándo?')
        self.assertContains(respuesta, 'Elige una fecha u hora distinta de la actual.')
        self.assertNotContains(respuesta, 'Revisa antes de confirmar')
        self.assertIn(f'value="{self.fecha_nueva.isoformat()}"', etiqueta(html, 'nueva_fecha'))
        self.assertIn('value="05:30"', etiqueta(html, 'nueva_hora'))
        self.assertIn('role="alert"', html)

    def test_un_error_de_la_hora_sale_bajo_la_hora(self):
        with parche_proponer(return_value=propuesta(errores={'nueva_hora': 'Esa hora está fuera de la ventana.'})):
            respuesta = self._post()

        self.assertContains(respuesta, 'Esa hora está fuera de la ventana.')

    def test_un_error_sin_campo_conocido_sale_como_banda_general(self):
        with parche_proponer(return_value=propuesta(errores={'': 'No se puede guardar: dato inválido.'})):
            respuesta = self._post()

        self.assertContains(respuesta, 'No se puede guardar: dato inválido.')
        self.assertContains(respuesta, 'rg-banda')

    def test_sin_lugar_usa_el_motivo_y_la_proxima_fecha_con_lugar(self):
        proxima = self.fecha_nueva + timedelta(days=1)
        with parche_proponer(return_value=propuesta(
                motivo_sin_cupo='Ese día ya no hay lugar.', proxima_fecha=proxima)):
            respuesta = self._post()

        self.assertContains(respuesta, 'Ese día ya no hay lugar.')
        self.assertContains(respuesta, f'La próxima fecha con lugar es el {fecha_larga(proxima)}.')
        self.assertNotContains(respuesta, 'Revisa antes de confirmar')

    def test_una_fecha_vacia_o_rota_no_llega_al_servicio(self):
        for texto in ('', 'mañana', '2026-13-45'):
            with self.subTest(fecha=texto), parche_proponer() as parche:
                respuesta = self._post(nueva_fecha=texto)
                parche.assert_not_called()
                self.assertContains(respuesta, 'Elige una fecha.')

    def test_una_hora_rota_no_llega_al_servicio(self):
        with parche_proponer() as parche:
            respuesta = self._post(nueva_hora='25:99')

        parche.assert_not_called()
        self.assertContains(respuesta, 'Escribe la hora como 06:00.')


class AvisoDe48HorasTests(_Base):
    def _revisar_con_48h(self, usuario):
        self.client.force_login(usuario)
        limite = timezone.now() + timedelta(hours=10)
        with parche_proponer(return_value=propuesta(
                fecha=self.fecha_nueva, hora=time(6, 0), requiere_excepcion_48h=True, limite_48h=limite)):
            return self._post()

    def test_el_jefe_ve_el_aviso_y_el_campo_del_motivo(self):
        respuesta = self._revisar_con_48h(self.jefa)
        html = self._html(respuesta)

        self.assertContains(respuesta, 'Faltan menos de 48 horas para la salida original. Como jefe puedes autorizar el cambio.')
        self.assertContains(respuesta, 'Motivo de la excepción')
        self.assertContains(respuesta, 'Queda registrado en el historial y avisa a toda la empresa.')
        self.assertTrue(etiqueta(html, 'motivo_excepcion'))
        self.assertContains(respuesta, 'Reagendar y avisar al cliente')

    def test_el_operador_de_plataforma_tambien_puede_autorizar(self):
        respuesta = self._revisar_con_48h(self.operador)

        self.assertTrue(etiqueta(self._html(respuesta), 'motivo_excepcion'))

    def test_la_vendedora_queda_bloqueada_sin_boton_de_confirmar(self):
        respuesta = self._revisar_con_48h(self.vendedora)
        html = self._html(respuesta)

        self.assertContains(respuesta, 'Faltan menos de 48 horas para la salida original, así que no se puede '
                                       'reagendar desde aquí. Pídele a un jefe que lo autorice.')
        self.assertEqual(etiqueta(html, 'motivo_excepcion'), '')
        self.assertNotContains(respuesta, 'Reagendar y avisar al cliente')
        self.assertNotIn('value="confirmar"', html)
        self.assertContains(respuesta, 'Volver a la reserva')

    def test_sin_el_aviso_nadie_ve_el_campo_del_motivo(self):
        with parche_proponer(return_value=propuesta(fecha=self.fecha_nueva, hora=time(6, 0))):
            respuesta = self._post()

        self.assertEqual(etiqueta(self._html(respuesta), 'motivo_excepcion'), '')
        self.assertNotContains(respuesta, 'Faltan menos de 48 horas')


class VolverTests(_Base):
    def test_un_volver_propio_se_conserva_y_se_usa_al_terminar(self):
        lista = reverse('admin:bookings_reserva_changelist') + '?vista=hoy'
        with parche_proponer(return_value=propuesta(fecha=self.fecha_nueva, hora=time(6, 0))):
            respuesta = self.client.post(self.url + '?volver=' + lista, {
                'paso': 'revisar', 'nueva_fecha': self.fecha_nueva.isoformat(), 'nueva_hora': '06:00',
                'volver': lista,
            })
        self.assertIn(f'value="{lista}"', etiqueta(self._html(respuesta), 'volver').replace('&amp;', '&'))

        with mock.patch(REAGENDAR, return_value=self._resultado()), parche_proponer(return_value=propuesta()):
            final = self.client.post(self.url, self._datos_de_confirmar(volver=lista))
        self.assertRedirects(final, lista, fetch_redirect_response=False)

    def test_un_volver_hostil_se_ignora(self):
        for hostil in ('//evil.example/x', 'javascript:alert(1)', 'https://evil.example', '/\\evil.example'):
            with self.subTest(volver=hostil):
                respuesta = self.client.get(self.url, {'volver': hostil})
                self.assertNotContains(respuesta, 'evil')
                self.assertNotContains(respuesta, 'javascript:')

                with mock.patch(REAGENDAR, return_value=self._resultado()), parche_proponer(return_value=propuesta()):
                    final = self.client.post(self.url, self._datos_de_confirmar(volver=hostil))
                self.assertRedirects(final, self.ficha, fetch_redirect_response=False)

    def test_sin_volver_se_regresa_a_la_ficha(self):
        with mock.patch(REAGENDAR, return_value=self._resultado()), parche_proponer(return_value=propuesta()):
            final = self.client.post(self.url, self._datos_de_confirmar())

        self.assertRedirects(final, self.ficha, fetch_redirect_response=False)


class ReservaNoReagendableTests(_Base):
    def test_get_avisa_en_espanol_y_redirige_sin_formulario(self):
        with mock.patch(MOTIVO, return_value='Esta reserva está cancelada: solo se reagendan reservas pagadas o asignadas.'):
            respuesta = self.client.get(self.url)

        self.assertRedirects(respuesta, self.ficha, fetch_redirect_response=False)
        self.assertIn('Esta reserva está cancelada: solo se reagendan reservas pagadas o asignadas.',
                      self._mensajes(respuesta))

    def test_post_tampoco_llama_al_servicio(self):
        with mock.patch(MOTIVO, return_value='Esta reserva está en disputa con el banco. Espera a que Stripe resuelva.'), \
                parche_proponer() as proponer, mock.patch(REAGENDAR) as reagendar:
            respuesta = self.client.post(self.url, self._datos_de_confirmar())

        self.assertRedirects(respuesta, self.ficha, fetch_redirect_response=False)
        proponer.assert_not_called()
        reagendar.assert_not_called()

    def test_redirige_a_volver_cuando_es_seguro(self):
        lista = reverse('admin:bookings_reserva_changelist')
        with mock.patch(MOTIVO, return_value='No.'):
            respuesta = self.client.get(self.url, {'volver': lista})

        self.assertRedirects(respuesta, lista, fetch_redirect_response=False)


class ConfirmarTests(_Base):
    def _confirmar(self, resultado=None, usuario=None, propuesta_=None, **campos):
        if usuario is not None:
            self.client.force_login(usuario)
        with parche_proponer(return_value=propuesta_ or propuesta(fecha=self.fecha_nueva, hora=time(6, 0))), \
                mock.patch(REAGENDAR, return_value=resultado or self._resultado()) as parche:
            respuesta = self.client.post(self.url, self._datos_de_confirmar(**campos))
        return respuesta, parche

    def _notificaciones(self):
        with scope.como_operador_plataforma():
            return list(Notificacion.objects.filter(empresa=self.empresa))

    def _entradas(self):
        return list(LogEntry.objects.filter(object_id=str(self.reserva.pk), action_flag=CHANGE))

    def test_llama_al_servicio_con_los_datos_el_token_y_quien_lo_hace(self):
        _, parche = self._confirmar()

        parche.assert_called_once()
        self.assertEqual(parche.call_args.args, (self.reserva.pk,))
        llamada = parche.call_args.kwargs
        self.assertEqual(llamada['nueva_fecha'], self.fecha_nueva)
        self.assertEqual(llamada['nueva_hora'], time(6, 0))
        self.assertIsNone(llamada['nueva_fecha_regreso'])
        self.assertEqual(llamada['usuario'], self.jefa)
        self.assertTrue(llamada['puede_autorizar_48h'])
        self.assertEqual(llamada['motivo_excepcion'], '')
        self.assertTrue(llamada['avisar_cliente'])
        self.assertEqual(llamada['token'], {
            'fecha': self.fecha_actual.isoformat(), 'hora': '06:00:00', 'inicio_paquete': '', 'estado': 'pagada',
        })

    def test_la_vendedora_no_puede_autorizar_la_excepcion(self):
        _, parche = self._confirmar(usuario=self.vendedora)

        self.assertFalse(parche.call_args.kwargs['puede_autorizar_48h'])

    def test_el_operador_si_puede_autorizar_la_excepcion(self):
        _, parche = self._confirmar(usuario=self.operador)

        self.assertTrue(parche.call_args.kwargs['puede_autorizar_48h'])

    def test_deja_constancia_en_el_history_con_el_antes_y_el_despues(self):
        self._confirmar()

        entradas = self._entradas()
        self.assertEqual(len(entradas), 1)
        mensaje = entradas[0].get_change_message()
        self.assertIn('Reagendada', mensaje)
        self.assertIn(fecha_larga(self.fecha_actual, time(6, 0)), mensaje)
        self.assertIn(fecha_larga(self.fecha_nueva, time(6, 0)), mensaje)
        self.assertIn('Cliente avisado: sí', mensaje)
        self.assertEqual(entradas[0].user, self.jefa)

    def test_deja_una_notificacion_persistente_de_exito_sin_datos_de_contacto(self):
        respuesta, _ = self._confirmar()

        notificaciones = self._notificaciones()
        self.assertEqual(len(notificaciones), 1)
        aviso = notificaciones[0]
        self.assertEqual(aviso.tipo, Notificacion.Tipo.CAMBIO_FECHA)
        self.assertEqual(aviso.nivel, Notificacion.Nivel.EXITO)
        self.assertIn('Ana Ruiz', aviso.texto)
        for dato in (CORREO, TELEFONO, '6121234567'):
            self.assertNotIn(dato, aviso.texto + aviso.motivo)
        self.assertEqual(aviso.enlace_url, self.ficha)
        self.assertEqual(aviso.actor, self.jefa)

    def test_el_aviso_en_pantalla_dice_cuando_sale_el_correo(self):
        respuesta, _ = self._confirmar()

        mensajes = self._mensajes(respuesta)
        self.assertTrue(any(
            'Reagendaste a Ana Ruiz al ' in m and 'El correo sale en unos segundos; si no sale, te avisa Notificaciones.' in m
            for m in mensajes), mensajes)
        self.assertRedirects(respuesta, self.ficha, fetch_redirect_response=False)

    def test_sin_avisar_al_cliente_el_aviso_es_ambar_y_el_history_lo_dice(self):
        campos = self._datos_de_confirmar()
        del campos['avisar_cliente']
        with parche_proponer(return_value=propuesta()), \
                mock.patch(REAGENDAR, return_value=self._resultado(correo_encolado=False)) as parche:
            respuesta = self.client.post(self.url, campos)

        self.assertFalse(parche.call_args.kwargs['avisar_cliente'])
        aviso = self._notificaciones()[0]
        self.assertEqual(aviso.nivel, Notificacion.Nivel.AVISO)
        self.assertIn('Reagendada sin avisar al cliente. Avísale tú.', aviso.texto)
        self.assertIn('Cliente avisado: no', self._entradas()[0].get_change_message())
        self.assertTrue(any('Reagendada sin avisar al cliente. Avísale tú.' in m for m in self._mensajes(respuesta)))

    def test_una_reserva_sin_correo_avisa_por_whatsapp(self):
        self._actualizar(correo_cliente='')
        campos = self._datos_de_confirmar()
        del campos['avisar_cliente']
        with parche_proponer(return_value=propuesta()), \
                mock.patch(REAGENDAR, return_value=self._resultado(correo_encolado=False)) as parche:
            respuesta = self.client.post(self.url, campos)

        self.assertFalse(parche.call_args.kwargs['avisar_cliente'])
        self.assertIn('Cliente avisado: sin correo', self._entradas()[0].get_change_message())
        self.assertEqual(self._notificaciones()[0].nivel, Notificacion.Nivel.AVISO)
        self.assertTrue(any('El cliente no tiene correo. Avísale por WhatsApp.' in m for m in self._mensajes(respuesta)))

    def test_una_excepcion_de_48h_deja_el_motivo_en_el_history_y_avisa_en_ambar(self):
        motivo = 'El cliente perdió el vuelo por una tormenta.'
        propuesta_ = propuesta(fecha=self.fecha_nueva, hora=time(6, 0), requiere_excepcion_48h=True)
        _, parche = self._confirmar(
            resultado=self._resultado(excepcion_48h=True), propuesta_=propuesta_, motivo_excepcion=motivo)

        self.assertEqual(parche.call_args.kwargs['motivo_excepcion'], motivo)
        mensaje = self._entradas()[0].get_change_message()
        self.assertIn('excepción de 48 h', mensaje)
        self.assertIn(motivo, mensaje)
        self.assertIn('jefa-rg', mensaje)
        aviso = self._notificaciones()[0]
        self.assertEqual(aviso.nivel, Notificacion.Nivel.AVISO)
        self.assertIn('excepción de 48 h', aviso.texto)

    def test_el_motivo_corto_vuelve_al_paso_dos_sin_llamar_al_servicio(self):
        propuesta_ = propuesta(fecha=self.fecha_nueva, hora=time(6, 0), requiere_excepcion_48h=True)
        respuesta, parche = self._confirmar(propuesta_=propuesta_, motivo_excepcion='corto')

        parche.assert_not_called()
        self.assertContains(respuesta, 'Revisa antes de confirmar')
        self.assertContains(respuesta, 'Escribe entre 10 y 200 caracteres.')
        self.assertEqual(self._entradas(), [])
        self.assertEqual(self._notificaciones(), [])

    def test_una_vendedora_no_puede_saltarse_la_regla_de_48h_con_un_post_directo(self):
        propuesta_ = propuesta(fecha=self.fecha_nueva, hora=time(6, 0), requiere_excepcion_48h=True)
        respuesta, parche = self._confirmar(
            usuario=self.vendedora, propuesta_=propuesta_, motivo_excepcion='Me lo pidió la jefa por teléfono.')

        parche.assert_not_called()
        self.assertContains(respuesta, 'Pídele a un jefe que lo autorice.')

    def test_un_error_con_campo_vuelve_al_paso_uno_bajo_ese_campo(self):
        error = _ErrorDeReagendado('Esta reserva cambió mientras la revisabas. Revisa y vuelve a elegir.', 'nueva_fecha')
        with parche_proponer(return_value=propuesta()), mock.patch(REAGENDAR, side_effect=error):
            respuesta = self.client.post(self.url, self._datos_de_confirmar())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '¿Para cuándo?')
        self.assertContains(respuesta, 'Esta reserva cambió mientras la revisabas. Revisa y vuelve a elegir.')
        self.assertEqual(self._entradas(), [])
        self.assertEqual(self._notificaciones(), [])

    def test_un_error_general_sale_en_una_banda_y_no_deja_rastro(self):
        error = _ErrorDeReagendado('El sistema está ocupado confirmando otras reservas de ese día. '
                                   'Intenta otra vez en unos segundos.')
        with parche_proponer(return_value=propuesta()), mock.patch(REAGENDAR, side_effect=error):
            respuesta = self.client.post(self.url, self._datos_de_confirmar())

        self.assertContains(respuesta, 'El sistema está ocupado confirmando otras reservas de ese día.')
        self.assertContains(respuesta, 'rg-banda')
        self.assertEqual(self._entradas(), [])
        self.assertEqual(self._notificaciones(), [])

    def test_si_la_propuesta_ya_trae_errores_no_se_confirma(self):
        _, parche = self._confirmar(propuesta_=propuesta(errores={'nueva_fecha': 'La nueva fecha ya pasó.'}))

        parche.assert_not_called()

    def test_dice_a_que_capitan_avisar(self):
        with scope.como_operador_plataforma():
            from apps.fleet.models import Capitan
            Capitan.objects.create(empresa=self.empresa, nombre='Beto Lugo', telefono='1')
        resultado = self._resultado(
            antes=antes_del_cambio(fecha=self.fecha_actual, hora=time(6, 0), panga='Panga 3-1', capitan='Beto Lugo'),
            capitan_conservado=True)

        respuesta, _ = self._confirmar(resultado=resultado)

        self.assertIn('Avísale al capitán Beto Lugo del nuevo día.', self._notificaciones()[0].texto)
        self.assertTrue(any('Avísale al capitán Beto Lugo del nuevo día.' in m for m in self._mensajes(respuesta)))

    def test_el_operador_deja_la_notificacion_en_la_empresa_de_la_reserva(self):
        self._confirmar(usuario=self.operador)

        self.assertEqual(len(self._notificaciones()), 1)

    def test_otra_empresa_no_puede_confirmar_una_reserva_ajena(self):
        self.client.force_login(self.jefa_otra)
        with mock.patch(REAGENDAR) as parche:
            respuesta = self.client.post(self.url, self._datos_de_confirmar())

        self.assertEqual(respuesta.status_code, 404)
        parche.assert_not_called()


class PuntosDeEntradaTests(_Base):
    def test_la_lista_ofrece_la_accion_de_fila_reagendar(self):
        respuesta = self.client.get(reverse('admin:bookings_reserva_changelist'), {'vista': 'todas'})

        self.assertContains(respuesta, 'Reagendar')

    def test_la_accion_de_fila_lleva_a_la_vista_y_regresa_a_la_lista(self):
        lista = reverse('admin:bookings_reserva_changelist')
        accion = reverse('admin:bookings_reserva_accion_fila_reagendar', args=[self.reserva.pk])

        respuesta = self.client.get(accion)

        self.assertRedirects(respuesta, f'{self.url}?volver={lista}', fetch_redirect_response=False)

    def test_la_accion_de_fila_vuelve_a_la_lista_con_sus_filtros(self):
        lista = reverse('admin:bookings_reserva_changelist') + '?vista=hoy'
        accion = reverse('admin:bookings_reserva_accion_fila_reagendar', args=[self.reserva.pk])

        respuesta = self.client.get(accion, HTTP_REFERER=f'http://testserver{lista}')

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta['Location'].startswith(self.url + '?volver='))
        self.assertIn('vista%3Dhoy', respuesta['Location'])

    def test_la_accion_de_fila_ignora_un_referer_de_otro_sitio(self):
        accion = reverse('admin:bookings_reserva_accion_fila_reagendar', args=[self.reserva.pk])

        respuesta = self.client.get(accion, HTTP_REFERER='https://evil.example/x')

        self.assertNotIn('evil', respuesta['Location'])

    def test_la_accion_de_fila_de_otra_empresa_es_404(self):
        accion = reverse('admin:bookings_reserva_accion_fila_reagendar', args=[self.reserva_ajena.pk])

        self.assertEqual(self.client.get(accion).status_code, 404)

    def test_la_ficha_trae_el_boton_apuntando_a_la_vista(self):
        respuesta = self.client.get(self.ficha)

        self.assertContains(respuesta, 'Reagendar')
        self.assertContains(respuesta, f'href="{self.url}?volver={self.ficha}"')

    def test_la_ficha_de_una_reserva_no_reagendable_no_trae_el_boton(self):
        with mock.patch(MOTIVO, return_value='No se puede.'):
            respuesta = self.client.get(self.ficha)

        self.assertNotContains(respuesta, self.url)

    def test_quien_solo_puede_ver_no_ve_el_boton(self):
        self.client.force_login(self.lectora)

        respuesta = self.client.get(self.ficha)

        self.assertNotContains(respuesta, self.url)
