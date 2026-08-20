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
from django.utils import timezone

from apps.fleet.models import Capitan, Embarcacion, EmbarcacionNoDisponible
from apps.testing import crear_flota

from .models import Reserva
from .panorama import armar_panorama


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


class AnchoDeColumnasTests(TestCase):
    """Las columnas de embarcacion y capitan llevan selectores y Unfold le pone
    `min-w-0` y `overflow-hidden` a cada celda, asi que se aprietan hasta quedar
    ilegibles. Se corrige con una hoja propia y no con clases de Tailwind: el
    admin sirve el CSS de Unfold ya compilado y una clase que ellos no usen no
    existe.

    El ancho en si no lo puede ver ningun test — eso se confirma en pantalla. Lo
    que si se puede exigir es que la hoja llegue a las dos pantallas.
    """

    HOJA = 'bookings/admin-columnas.css'

    def setUp(self):
        crear_flota()
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )

    def test_la_agenda_carga_la_hoja(self):
        respuesta = self.client.get(reverse('admin:bookings_agenda_changelist'))
        self.assertContains(respuesta, self.HOJA)

    def test_el_listado_de_reservas_carga_la_hoja(self):
        respuesta = self.client.get(reverse('admin:bookings_reserva_changelist'))
        self.assertContains(respuesta, self.HOJA)


class AvisoDeReservasNuevasTests(TestCase):
    """El aviso de reservas nuevas vive en las dos pantallas.

    Es un boton flotante que consulta cada 30 segundos y **nunca recarga solo**:
    quien lo ve puede estar a media asignacion de capitan. Estaba solo en el
    listado de Reservas, pero repartir tambien se hace mirando la agenda.
    """

    SCRIPT = 'bookings/reservas-nuevas.js'

    def setUp(self):
        crear_flota()
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )

    def test_la_agenda_carga_el_script(self):
        self.assertContains(
            self.client.get(reverse('admin:bookings_agenda_changelist')), self.SCRIPT)

    def test_el_listado_de_reservas_sigue_cargando_el_script(self):
        self.assertContains(
            self.client.get(reverse('admin:bookings_reserva_changelist')), self.SCRIPT)

    def test_la_agenda_tiene_su_propio_endpoint_de_conteo(self):
        cuerpo = self.client.get(reverse('admin:bookings_agenda_nuevas')).json()

        self.assertEqual(cuerpo['nuevas'], 0)
        self.assertIn('desde', cuerpo)

    def test_el_endpoint_de_la_agenda_cuenta_las_que_entraron_despues(self):
        antes = timezone.now().isoformat()
        viaje()

        cuerpo = self.client.get(
            reverse('admin:bookings_agenda_nuevas'), {'desde': antes}).json()

        self.assertEqual(cuerpo['nuevas'], 1)

    def test_el_endpoint_de_la_agenda_ignora_los_checkouts_sin_pagar(self):
        """Cada checkout abandonado deja una fila en pendiente_pago; avisar de
        esas volveria el contador puro ruido."""
        antes = timezone.now().isoformat()
        viaje(estado=Reserva.Estado.PENDIENTE_PAGO)

        cuerpo = self.client.get(
            reverse('admin:bookings_agenda_nuevas'), {'desde': antes}).json()

        self.assertEqual(cuerpo['nuevas'], 0)


class RecienLlegadasTests(TestCase):
    """Lo ultimo que entro al sistema, sin importar para cuando sea el viaje.

    En la agenda es una tercera opcion del mismo filtro "Cuando" y no un filtro
    aparte: si fuera aparte se sumaria a la ventana de fechas, y una reserva que
    entro hoy para diciembre no apareceria — que es justo lo que se quiere ver.
    """

    def setUp(self):
        crear_flota()
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )

    def _envejecer(self, reserva, horas):
        Reserva.objects.filter(pk=reserva.pk).update(
            creado_en=timezone.now() - timedelta(hours=horas))
        return reserva

    def _filas(self, url, **params):
        respuesta = self.client.get(url, params)
        self.assertEqual(respuesta.status_code, 200)
        return [r.pk for r in respuesta.context['cl'].result_list]

    def test_la_agenda_trae_lo_recien_llegado_aunque_el_viaje_sea_lejano(self):
        lejano = viaje(fecha=date.today() + timedelta(days=120))

        url = reverse('admin:bookings_agenda_changelist')
        self.assertIn(lejano.pk, self._filas(url, cuando='recientes'))
        # Y sigue fuera de la ventana de la semana, que es lo correcto.
        self.assertNotIn(lejano.pk, self._filas(url, cuando='semana'))

    def test_la_agenda_no_trae_lo_que_entro_hace_mas_de_48_horas(self):
        vieja = self._envejecer(viaje(fecha=date.today() + timedelta(days=120)), horas=72)

        self.assertNotIn(
            vieja.pk,
            self._filas(reverse('admin:bookings_agenda_changelist'), cuando='recientes'))

    def test_lo_recien_llegado_sale_ordenado_por_llegada(self):
        """Con el orden por fecha de viaje, lo que acaba de entrar quedaria
        enterrado entre lo de la semana — lo contrario de para que sirve."""
        primera = self._envejecer(viaje(fecha=date.today() + timedelta(days=2)), horas=10)
        segunda = viaje(fecha=date.today() + timedelta(days=90))

        filas = self._filas(
            reverse('admin:bookings_agenda_changelist'), cuando='recientes')

        self.assertEqual(filas, [segunda.pk, primera.pk])

    def test_el_listado_de_reservas_tiene_su_propio_filtro(self):
        reciente = viaje(fecha=date.today() + timedelta(days=120))
        vieja = self._envejecer(viaje(fecha=date.today() + timedelta(days=90)), horas=72)

        filas = self._filas(
            reverse('admin:bookings_reserva_changelist'), llegada='recientes')

        self.assertIn(reciente.pk, filas)
        self.assertNotIn(vieja.pk, filas)

    def test_el_listado_de_reservas_sin_el_filtro_las_trae_todas(self):
        reciente = viaje(fecha=date.today() + timedelta(days=120))
        vieja = self._envejecer(viaje(fecha=date.today() + timedelta(days=90)), horas=72)

        filas = self._filas(reverse('admin:bookings_reserva_changelist'))

        self.assertIn(reciente.pk, filas)
        self.assertIn(vieja.pk, filas)


class PanoramaTests(TestCase):
    """La cuadricula de dias x pangas que va arriba de la agenda.

    Responde la pregunta que la tabla no responde: que panga tengo libre el
    jueves. Solo lectura — repartir se sigue haciendo en la tabla.
    """

    def setUp(self):
        crear_flota()
        self.hoy = date.today()
        self.grande = Embarcacion.objects.filter(capacidad_maxima=5).order_by('nombre').first()

    def test_un_renglon_por_panga_activa_y_una_columna_por_dia(self):
        panorama = armar_panorama(self.hoy, dias=7)

        self.assertEqual(len(panorama.dias), 7)
        self.assertEqual(panorama.dias[0], self.hoy)
        self.assertEqual(len(panorama.renglones), Embarcacion.objects.filter(activa=True).count())
        self.assertTrue(all(len(r.celdas) == 7 for r in panorama.renglones))

    def test_las_pangas_grandes_van_arriba(self):
        """Son las escasas: solo dos llevan mas de 3 personas."""
        capacidades = [r.embarcacion.capacidad_maxima for r in armar_panorama(self.hoy).renglones]

        self.assertEqual(capacidades, sorted(capacidades, reverse=True))

    def test_una_panga_inactiva_no_tiene_renglon(self):
        self.grande.activa = False
        self.grande.save()

        pangas = [r.embarcacion.pk for r in armar_panorama(self.hoy).renglones]

        self.assertNotIn(self.grande.pk, pangas)

    def test_el_viaje_asignado_cae_en_su_celda(self):
        reserva = viaje(fecha=self.hoy + timedelta(days=2),
                        estado=Reserva.Estado.ASIGNADA, embarcacion=self.grande)

        renglon = self._renglon_de(armar_panorama(self.hoy), self.grande)

        self.assertEqual(renglon.celdas[2].reserva.pk, reserva.pk)
        self.assertIsNone(renglon.celdas[1].reserva)

    def test_una_panga_fuera_de_servicio_no_se_ve_igual_que_una_libre(self):
        """Vacio significa disponible. Confundir las dos haria asignar un viaje a
        una panga que no sale."""
        EmbarcacionNoDisponible.objects.create(
            fecha=self.hoy + timedelta(days=3), embarcacion=self.grande, motivo='Motor')

        renglon = self._renglon_de(armar_panorama(self.hoy), self.grande)

        self.assertFalse(renglon.celdas[3].disponible)
        self.assertTrue(renglon.celdas[2].disponible)

    def test_los_viajes_sin_panga_no_se_pierden(self):
        """No tienen renglon donde caer: sin esto serian invisibles, que es lo
        peor que puede hacer un panorama."""
        pendiente = viaje(fecha=self.hoy + timedelta(days=1))

        panorama = armar_panorama(self.hoy)

        self.assertEqual([r.pk for r in panorama.sin_repartir[1]], [pendiente.pk])
        self.assertEqual(panorama.sin_repartir[0], [])

    def test_el_conteo_del_pie_cuadra(self):
        viaje(fecha=self.hoy, estado=Reserva.Estado.ASIGNADA, embarcacion=self.grande)
        EmbarcacionNoDisponible.objects.create(
            fecha=self.hoy, embarcacion=Embarcacion.objects.filter(capacidad_maxima=3).first())

        panorama = armar_panorama(self.hoy)

        self.assertEqual(panorama.ocupadas[0], 1)
        self.assertEqual(panorama.a_flote[0], 9)

    def test_una_cancelada_libera_su_celda(self):
        cancelada = viaje(fecha=self.hoy, estado=Reserva.Estado.ASIGNADA,
                          embarcacion=self.grande)
        Reserva.objects.filter(pk=cancelada.pk).update(estado=Reserva.Estado.CANCELADA)

        renglon = self._renglon_de(armar_panorama(self.hoy), self.grande)

        self.assertIsNone(renglon.celdas[0].reserva)

    def test_no_crece_en_consultas_con_los_dias(self):
        """Tres fijas: reservas del rango, pangas activas y las marcadas fuera.
        Sin ninguna por celda — son 70 celdas con la flota completa."""
        with self.assertNumQueries(3):
            armar_panorama(self.hoy, dias=7)

    def _renglon_de(self, panorama, embarcacion):
        return next(r for r in panorama.renglones if r.embarcacion.pk == embarcacion.pk)


class PanoramaEnLaAgendaTests(TestCase):
    """La cuadricula se pinta dentro del listado de la agenda, plegable."""

    def setUp(self):
        crear_flota()
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )

    def test_la_agenda_trae_el_panorama_en_su_contexto(self):
        panorama = self.client.get(self.url).context['panorama']

        self.assertEqual(len(panorama.dias), 7)
        self.assertEqual(len(panorama.renglones), 10)

    def test_el_panorama_no_sigue_al_filtro_de_fechas(self):
        """Siempre los proximos 7 dias. En "Manana" quedaria una sola columna y
        en "Recien llegadas" no hay ventana de fechas que dibujar; y es cerrando
        el dia de manana cuando mas sirve ver la semana completa."""
        for modo in ['manana', 'recientes', 'semana']:
            with self.subTest(modo=modo):
                panorama = self.client.get(self.url, {'cuando': modo}).context['panorama']
                self.assertEqual(len(panorama.dias), 7)
                self.assertEqual(panorama.dias[0], date.today())

    def test_la_cuadricula_se_pinta_y_es_plegable(self):
        viaje(fecha=date.today() + timedelta(days=1),
              estado=Reserva.Estado.ASIGNADA,
              embarcacion=Embarcacion.objects.filter(capacidad_maxima=5).first())

        html = self.client.get(self.url).content.decode()

        self.assertIn('<details', html)
        self.assertIn('data-panorama', html)
        self.assertIn('Ana Ruiz', html)

    def test_el_script_del_toggle_se_carga(self):
        self.assertContains(self.client.get(self.url), 'bookings/panorama.js')

    def test_el_listado_de_reservas_no_trae_panorama(self):
        """Es una ayuda para repartir, no para el historial."""
        respuesta = self.client.get(reverse('admin:bookings_reserva_changelist'))

        self.assertIsNone(respuesta.context.get('panorama'))
