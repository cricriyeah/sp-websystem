"""Pruebas de la pantalla de agenda.

Aparte de `tests.py` porque eso ya cubre las reglas del modelo y pasa de 900
lineas; esto es la superficie del admin: que se liste, que se filtre y que se vea
lo que esta mal.
"""
from datetime import date, time, timedelta

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.fleet.models import Capitan, Embarcacion
from apps.testing import crear_flota

from .models import Reserva


def datos(**overrides):
    base = {
        'fecha': date.today() + timedelta(days=3),
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
    base.update(overrides)
    return base


def viaje(**overrides):
    """Se guarda sin full_clean para poder sembrar fechas pasadas: la regla de las
    48 horas no deja reprogramar hacia atras, y aqui hace falta un atrasado."""
    crear_flota()
    return Reserva.objects.create(**datos(**overrides))


class AgendaAdminTests(TestCase):
    def setUp(self):
        crear_flota()
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )

    def _filas(self, **params):
        respuesta = self.client.get(self.url, params)
        self.assertEqual(respuesta.status_code, 200)
        return {r.pk for r in respuesta.context['cl'].result_list}

    def test_el_modo_manana_trae_solo_manana(self):
        manana = viaje(fecha=date.today() + timedelta(days=1))
        viaje(fecha=date.today() + timedelta(days=2))

        self.assertEqual(self._filas(cuando='manana'), {manana.pk})

    def test_el_modo_semana_trae_los_proximos_siete_dias(self):
        dentro = viaje(fecha=date.today() + timedelta(days=6))
        viaje(fecha=date.today() + timedelta(days=30))

        self.assertEqual(self._filas(cuando='semana'), {dentro.pk})

    def test_el_modo_semana_trae_los_atrasados_sin_repartir(self):
        """Un viaje cobrado que ya paso y nadie repartio es un error que hay que
        ver. Esconderlo no lo arregla."""
        atrasado = viaje(fecha=date.today() - timedelta(days=2))

        self.assertIn(atrasado.pk, self._filas(cuando='semana'))

    def test_el_modo_semana_no_trae_los_atrasados_ya_repartidos(self):
        """Ese se repartio, aunque haya pasado."""
        repartido = viaje(fecha=date.today() - timedelta(days=2),
                          estado=Reserva.Estado.ASIGNADA,
                          embarcacion=Embarcacion.objects.first())

        self.assertNotIn(repartido.pk, self._filas(cuando='semana'))

    def test_sin_filtro_abre_en_la_semana(self):
        dentro = viaje(fecha=date.today() + timedelta(days=2))
        viaje(fecha=date.today() + timedelta(days=30))

        self.assertEqual(self._filas(), {dentro.pk})

    def test_avisa_de_un_viaje_asignado_sin_capitan(self):
        viaje(fecha=date.today() + timedelta(days=2),
              estado=Reserva.Estado.ASIGNADA,
              embarcacion=Embarcacion.objects.first())

        self.assertContains(self.client.get(self.url), 'SIN CAPITAN')

    def test_no_avisa_cuando_el_viaje_tiene_capitan(self):
        viaje(fecha=date.today() + timedelta(days=2),
              estado=Reserva.Estado.ASIGNADA,
              embarcacion=Embarcacion.objects.first(),
              capitan=Capitan.objects.create(nombre='Juan Perez',
                                             telefono='+5216121234567'))

        self.assertNotContains(self.client.get(self.url), 'SIN CAPITAN')

    def test_avisa_de_un_viaje_atrasado(self):
        viaje(fecha=date.today() - timedelta(days=2))

        self.assertContains(self.client.get(self.url), 'ATRASADO')

    def test_un_viaje_futuro_sin_panga_no_se_marca(self):
        """No es un error: es el trabajo pendiente, y es a lo que se viene aqui.
        Marcarlo volveria roja la agenda entera y el rojo dejaria de significar
        algo."""
        viaje(fecha=date.today() + timedelta(days=2))

        respuesta = self.client.get(self.url)
        self.assertNotContains(respuesta, 'ATRASADO')
        self.assertNotContains(respuesta, 'SIN CAPITAN')

    def test_la_panga_y_el_capitan_se_editan_en_el_listado(self):
        """El punto entero de la pantalla: repartir sin entrar a cada reserva."""
        viaje(fecha=date.today() + timedelta(days=2))

        formset = self.client.get(self.url).context['cl'].formset

        self.assertIn('embarcacion', formset.forms[0].fields)
        self.assertIn('capitan', formset.forms[0].fields)


class AgendaPermisosTests(TestCase):
    def setUp(self):
        crear_flota()
        call_command('setup_roles')
        self.vendedora = User.objects.create_user(
            'maria', 'maria@example.com', 'x', is_staff=True)
        self.vendedora.groups.add(Group.objects.get(name='Vendedora'))
        self.client.force_login(self.vendedora)

    def test_la_vendedora_ve_la_agenda(self):
        respuesta = self.client.get(reverse('admin:bookings_agenda_changelist'))
        self.assertEqual(respuesta.status_code, 200)

    def test_la_vendedora_no_puede_agregar_desde_la_agenda(self):
        """Una reserva se crea vendiendo, no se inventa desde aqui."""
        respuesta = self.client.get(reverse('admin:bookings_agenda_add'))
        self.assertEqual(respuesta.status_code, 403)

    def test_la_vendedora_puede_marcar_una_panga_fuera_de_servicio(self):
        """Hueco heredado de la pieza del cupo: el modelo se creo sin darle el
        permiso, y marcar que la Lupita esta en mantenimiento es trabajo suyo."""
        respuesta = self.client.get(
            reverse('admin:fleet_embarcacionnodisponible_add'))
        self.assertEqual(respuesta.status_code, 200)


class MenuLateralTests(TestCase):
    """El menu de unfold se arma a mano en `UNFOLD['SIDEBAR']` (config/settings/
    base.py): un modelo nuevo no aparece solo. Sin esto la pantalla existe, tiene
    su URL y funciona — pero nadie la encuentra salvo hundida en "todas las
    aplicaciones", que es tanto como no tenerla.

    Se revisa la configuracion y no el HTML de `/admin/` a proposito: esa pagina
    lista todas las apps (`show_all_applications`), asi que buscar la URL ahi pasa
    aunque el menu lateral no la tenga. La primera version de esta prueba hacia
    justo eso y pasaba sin que el menu existiera.
    """

    def _enlaces_del_menu(self):
        return {
            str(item['link'])
            for grupo in settings.UNFOLD['SIDEBAR']['navigation']
            for item in grupo['items']
        }

    def test_el_menu_lleva_a_la_agenda(self):
        self.assertIn(
            reverse('admin:bookings_agenda_changelist'), self._enlaces_del_menu())

    def test_el_menu_lleva_a_las_embarcaciones_no_disponibles(self):
        """Marcar que una panga no sale un dia es trabajo diario. Llego con la
        pieza del cupo y se quedo sin entrada en el menu."""
        self.assertIn(
            reverse('admin:fleet_embarcacionnodisponible_changelist'),
            self._enlaces_del_menu())
