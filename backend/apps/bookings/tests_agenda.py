"""Pruebas de la pantalla de agenda.

Aparte de `tests.py` porque eso ya cubre las reglas del modelo y pasa de 900
lineas; esto es la superficie del admin: que se liste, que se filtre y que se vea
lo que esta mal.
"""
from datetime import date, time, timedelta

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.fleet.models import Capitan, Embarcacion, EmbarcacionNoDisponible
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca

from .models import Agenda, Reserva
from .panorama import armar_panorama


def datos(empresa, **overrides):
    empresa_real = overrides.get('empresa', empresa)
    base = {
        'empresa': empresa_real,
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
    if 'servicio' not in overrides and 'paquete' not in overrides:
        base['servicio'] = crear_servicio_pesca(empresa_real)
    base.update(overrides)
    return base



def viaje(empresa, **overrides):
    """Se guarda sin full_clean para poder sembrar fechas pasadas: la regla de las
    48 horas no deja reprogramar hacia atras, y aqui hace falta un atrasado."""
    crear_flota(empresa)
    return Reserva.objects.create(**datos(empresa, **overrides))


class AgendaAdminTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())

    def _filas(self, **params):
        respuesta = self.client.get(self.url, params)
        self.assertEqual(respuesta.status_code, 200)
        return {r.pk for r in respuesta.context['cl'].result_list}

    def test_el_modo_manana_trae_solo_manana(self):
        manana = viaje(self.empresa, fecha=date.today() + timedelta(days=1))
        viaje(self.empresa, fecha=date.today() + timedelta(days=2))

        self.assertEqual(self._filas(cuando='manana'), {manana.pk})

    def test_el_modo_semana_trae_los_proximos_siete_dias(self):
        dentro = viaje(self.empresa, fecha=date.today() + timedelta(days=6))
        viaje(self.empresa, fecha=date.today() + timedelta(days=30))

        self.assertEqual(self._filas(cuando='semana'), {dentro.pk})

    def test_el_modo_semana_trae_los_atrasados_sin_repartir(self):
        """Un viaje cobrado que ya paso y nadie repartio es un error que hay que
        ver. Esconderlo no lo arregla."""
        atrasado = viaje(self.empresa, fecha=date.today() - timedelta(days=2))

        self.assertIn(atrasado.pk, self._filas(cuando='semana'))

    def test_el_modo_semana_no_trae_los_atrasados_ya_repartidos(self):
        """Ese se repartio, aunque haya pasado."""
        repartido = viaje(
            self.empresa, fecha=date.today() - timedelta(days=2),
            estado=Reserva.Estado.ASIGNADA,
            embarcacion=Embarcacion.objects.filter(empresa=self.empresa).first(),
        )

        self.assertNotIn(repartido.pk, self._filas(cuando='semana'))

    def test_sin_filtro_abre_en_la_semana(self):
        dentro = viaje(self.empresa, fecha=date.today() + timedelta(days=2))
        viaje(self.empresa, fecha=date.today() + timedelta(days=30))

        self.assertEqual(self._filas(), {dentro.pk})

    def test_avisa_de_un_viaje_asignado_sin_capitan(self):
        viaje(
            self.empresa, fecha=date.today() + timedelta(days=2),
            estado=Reserva.Estado.ASIGNADA,
            embarcacion=Embarcacion.objects.filter(empresa=self.empresa).first(),
        )

        self.assertContains(self.client.get(self.url), 'SIN CAPITAN')

    def test_no_avisa_cuando_el_viaje_tiene_capitan(self):
        viaje(
            self.empresa, fecha=date.today() + timedelta(days=2),
            estado=Reserva.Estado.ASIGNADA,
            embarcacion=Embarcacion.objects.filter(empresa=self.empresa).first(),
            capitan=Capitan.objects.create(
                empresa=self.empresa, nombre='Juan Perez', telefono='+5216121234567'),
        )

        self.assertNotContains(self.client.get(self.url), 'SIN CAPITAN')

    def test_avisa_de_un_viaje_atrasado(self):
        viaje(self.empresa, fecha=date.today() - timedelta(days=2))

        self.assertContains(self.client.get(self.url), 'ATRASADO')

    def test_un_viaje_futuro_sin_panga_no_se_marca(self):
        """No es un error: es el trabajo pendiente, y es a lo que se viene aqui.
        Marcarlo volveria roja la agenda entera y el rojo dejaria de significar
        algo."""
        viaje(self.empresa, fecha=date.today() + timedelta(days=2))

        respuesta = self.client.get(self.url)
        self.assertNotContains(respuesta, 'ATRASADO')
        self.assertNotContains(respuesta, 'SIN CAPITAN')

    def test_la_panga_y_el_capitan_se_editan_en_el_listado(self):
        """El punto entero de la pantalla: repartir sin entrar a cada reserva."""
        viaje(self.empresa, fecha=date.today() + timedelta(days=2))

        formset = self.client.get(self.url).context['cl'].formset

        self.assertIn('embarcacion', formset.forms[0].fields)
        self.assertIn('capitan', formset.forms[0].fields)

    def test_asignar_panga_a_reserva_con_hora_invalida_muestra_error_sin_500(self):
        servicio = crear_servicio_pesca(self.empresa)
        servicio.hora_apertura = time(8, 0)
        servicio.hora_cierre = time(10, 0)
        servicio.save(update_fields=['hora_apertura', 'hora_cierre'])
        reserva = viaje(self.empresa, servicio=servicio, hora=time(17, 0))
        panga = Embarcacion.objects.filter(
            empresa=self.empresa, capacidad_maxima__gte=reserva.numero_personas,
        ).first()
        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(reserva.pk),
            'form-0-embarcacion': str(panga.pk),
            'form-0-capitan': '',
            '_save': 'Guardar',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'hora')
        self.assertContains(respuesta, 'La hora debe estar entre 08:00 y 10:00.')
        reserva.refresh_from_db()
        self.assertIsNone(reserva.embarcacion_id)

    def test_asignar_panga_a_reserva_de_las_cinco_si_funciona(self):
        servicio = crear_servicio_pesca(self.empresa)
        servicio.hora_cierre = time(10, 0)
        servicio.paso_hora_minutos = 15
        servicio.save(update_fields=['hora_cierre', 'paso_hora_minutos'])
        reserva = viaje(self.empresa, servicio=servicio, hora=time(5, 0), numero_personas=5)
        servicio.hora_cierre = time(7, 0)
        servicio.paso_hora_minutos = 30
        servicio.save(update_fields=['hora_cierre', 'paso_hora_minutos'])
        panga = Embarcacion.objects.filter(
            empresa=self.empresa, capacidad_maxima__gte=5,
        ).first()
        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(reserva.pk),
            'form-0-embarcacion': str(panga.pk),
            'form-0-capitan': '',
            '_save': 'Guardar',
        })

        self.assertEqual(respuesta.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.embarcacion_id, panga.pk)

    def test_otra_fila_con_hora_invalida_no_bloquea_la_asignacion(self):
        servicio = crear_servicio_pesca(self.empresa)
        servicio.hora_cierre = time(10, 0)
        servicio.save(update_fields=['hora_cierre'])
        objetivo = viaje(self.empresa, servicio=servicio, hora=time(5, 0))
        otra = viaje(self.empresa, servicio=servicio, hora=time(9, 0))
        servicio.hora_cierre = time(7, 0)
        servicio.paso_hora_minutos = 30
        servicio.save(update_fields=['hora_cierre', 'paso_hora_minutos'])
        panga = Embarcacion.objects.filter(
            empresa=self.empresa, capacidad_maxima__gte=objetivo.numero_personas,
        ).first()

        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '2',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(objetivo.pk),
            'form-0-embarcacion': str(panga.pk),
            'form-0-capitan': '',
            'form-1-id': str(otra.pk),
            'form-1-embarcacion': '',
            'form-1-capitan': '',
            '_save': 'Guardar',
        })

        self.assertEqual(respuesta.status_code, 302)
        objetivo.refresh_from_db()
        otra.refresh_from_db()
        self.assertEqual(objetivo.embarcacion_id, panga.pk)
        self.assertIsNone(otra.embarcacion_id)


class AgendaPermisosTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.vendedora = self.crear_vendedora(username='maria')
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


class AnchoDeColumnasTests(EmpresaTestCase):
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
        crear_flota(self.empresa)
        self.client.force_login(self.crear_jefe())

    def test_la_agenda_carga_la_hoja(self):
        respuesta = self.client.get(reverse('admin:bookings_agenda_changelist'))
        self.assertContains(respuesta, self.HOJA)

    def test_el_listado_de_reservas_carga_la_hoja(self):
        respuesta = self.client.get(reverse('admin:bookings_reserva_changelist'))
        self.assertContains(respuesta, self.HOJA)


class AvisoDeReservasNuevasTests(EmpresaTestCase):
    """El aviso de reservas nuevas vive en las dos pantallas.

    Es un boton flotante que consulta cada 30 segundos y **nunca recarga solo**:
    quien lo ve puede estar a media asignacion de capitan. Estaba solo en el
    listado de Reservas, pero repartir tambien se hace mirando la agenda.
    """

    SCRIPT = 'bookings/reservas-nuevas.js'

    def setUp(self):
        crear_flota(self.empresa)
        self.client.force_login(self.crear_jefe())

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
        viaje(self.empresa)

        cuerpo = self.client.get(
            reverse('admin:bookings_agenda_nuevas'), {'desde': antes}).json()

        self.assertEqual(cuerpo['nuevas'], 1)

    def test_el_endpoint_de_la_agenda_ignora_los_checkouts_sin_pagar(self):
        """Cada checkout abandonado deja una fila en pendiente_pago; avisar de
        esas volveria el contador puro ruido."""
        antes = timezone.now().isoformat()
        viaje(self.empresa, estado=Reserva.Estado.PENDIENTE_PAGO)

        cuerpo = self.client.get(
            reverse('admin:bookings_agenda_nuevas'), {'desde': antes}).json()

        self.assertEqual(cuerpo['nuevas'], 0)


class RecienLlegadasTests(EmpresaTestCase):
    """Lo ultimo que entro al sistema, sin importar para cuando sea el viaje.

    En la agenda es una tercera opcion del mismo filtro "Cuando" y no un filtro
    aparte: si fuera aparte se sumaria a la ventana de fechas, y una reserva que
    entro hoy para diciembre no apareceria — que es justo lo que se quiere ver.
    """

    def setUp(self):
        crear_flota(self.empresa)
        self.client.force_login(self.crear_jefe())

    def _envejecer(self, reserva, horas):
        Reserva.objects.filter(pk=reserva.pk).update(
            creado_en=timezone.now() - timedelta(hours=horas))
        return reserva

    def _filas(self, url, **params):
        respuesta = self.client.get(url, params)
        self.assertEqual(respuesta.status_code, 200)
        return [r.pk for r in respuesta.context['cl'].result_list]

    def test_la_agenda_trae_lo_recien_llegado_aunque_el_viaje_sea_lejano(self):
        lejano = viaje(self.empresa, fecha=date.today() + timedelta(days=120))

        url = reverse('admin:bookings_agenda_changelist')
        self.assertIn(lejano.pk, self._filas(url, cuando='recientes'))
        # Y sigue fuera de la ventana de la semana, que es lo correcto.
        self.assertNotIn(lejano.pk, self._filas(url, cuando='semana'))

    def test_la_agenda_no_trae_lo_que_entro_hace_mas_de_48_horas(self):
        vieja = self._envejecer(
            viaje(self.empresa, fecha=date.today() + timedelta(days=120)), horas=72)

        self.assertNotIn(
            vieja.pk,
            self._filas(reverse('admin:bookings_agenda_changelist'), cuando='recientes'))

    def test_lo_recien_llegado_sale_ordenado_por_llegada(self):
        """Con el orden por fecha de viaje, lo que acaba de entrar quedaria
        enterrado entre lo de la semana — lo contrario de para que sirve."""
        primera = self._envejecer(
            viaje(self.empresa, fecha=date.today() + timedelta(days=2)), horas=10)
        segunda = viaje(self.empresa, fecha=date.today() + timedelta(days=90))

        filas = self._filas(
            reverse('admin:bookings_agenda_changelist'), cuando='recientes')

        self.assertEqual(filas, [segunda.pk, primera.pk])

    def test_el_listado_de_reservas_tiene_su_propio_filtro(self):
        reciente = viaje(self.empresa, fecha=date.today() + timedelta(days=120))
        vieja = self._envejecer(
            viaje(self.empresa, fecha=date.today() + timedelta(days=90)), horas=72)

        filas = self._filas(
            reverse('admin:bookings_reserva_changelist'), llegada='recientes')

        self.assertIn(reciente.pk, filas)
        self.assertNotIn(vieja.pk, filas)

    def test_el_listado_de_reservas_sin_el_filtro_las_trae_todas(self):
        reciente = viaje(self.empresa, fecha=date.today() + timedelta(days=120))
        vieja = self._envejecer(
            viaje(self.empresa, fecha=date.today() + timedelta(days=90)), horas=72)

        filas = self._filas(reverse('admin:bookings_reserva_changelist'))

        self.assertIn(reciente.pk, filas)
        self.assertIn(vieja.pk, filas)


class PanoramaTests(EmpresaTestCase):
    """La cuadricula de dias x pangas que va arriba de la agenda.

    Responde la pregunta que la tabla no responde: que panga tengo libre el
    jueves. Solo lectura — repartir se sigue haciendo en la tabla.
    """

    def setUp(self):
        crear_flota(self.empresa)
        self.hoy = date.today()
        self.grande = Embarcacion.objects.filter(
            empresa=self.empresa, capacidad_maxima=5).order_by('nombre').first()

    def test_un_renglon_por_panga_activa_y_una_columna_por_dia(self):
        panorama = armar_panorama(self.hoy, self.empresa, dias=7)

        self.assertEqual(len(panorama.dias), 7)
        self.assertEqual(panorama.dias[0], self.hoy)
        self.assertEqual(
            len(panorama.renglones),
            Embarcacion.objects.filter(empresa=self.empresa, activa=True).count(),
        )
        self.assertTrue(all(len(r.celdas) == 7 for r in panorama.renglones))

    def test_las_pangas_grandes_van_arriba(self):
        """Son las escasas: solo dos llevan mas de 3 personas."""
        capacidades = [
            r.embarcacion.capacidad_maxima
            for r in armar_panorama(self.hoy, self.empresa).renglones
        ]

        self.assertEqual(capacidades, sorted(capacidades, reverse=True))

    def test_una_panga_inactiva_no_tiene_renglon(self):
        self.grande.activa = False
        self.grande.save()

        pangas = [r.embarcacion.pk for r in armar_panorama(self.hoy, self.empresa).renglones]

        self.assertNotIn(self.grande.pk, pangas)

    def test_el_viaje_asignado_cae_en_su_celda(self):
        reserva = viaje(
            self.empresa, fecha=self.hoy + timedelta(days=2),
            estado=Reserva.Estado.ASIGNADA, embarcacion=self.grande,
        )

        renglon = self._renglon_de(armar_panorama(self.hoy, self.empresa), self.grande)

        self.assertEqual(renglon.celdas[2].reserva.pk, reserva.pk)
        self.assertIsNone(renglon.celdas[1].reserva)

    def test_una_panga_fuera_de_servicio_no_se_ve_igual_que_una_libre(self):
        """Vacio significa disponible. Confundir las dos haria asignar un viaje a
        una panga que no sale."""
        EmbarcacionNoDisponible.objects.create(
            empresa=self.empresa, fecha=self.hoy + timedelta(days=3),
            embarcacion=self.grande, motivo='Motor',
        )

        renglon = self._renglon_de(armar_panorama(self.hoy, self.empresa), self.grande)

        self.assertFalse(renglon.celdas[3].disponible)
        self.assertTrue(renglon.celdas[2].disponible)

    def test_los_viajes_sin_panga_no_se_pierden(self):
        """No tienen renglon donde caer: sin esto serian invisibles, que es lo
        peor que puede hacer un panorama."""
        pendiente = viaje(self.empresa, fecha=self.hoy + timedelta(days=1))

        panorama = armar_panorama(self.hoy, self.empresa)

        self.assertEqual([r.pk for r in panorama.sin_repartir[1]], [pendiente.pk])
        self.assertEqual(panorama.sin_repartir[0], [])

    def test_el_conteo_del_pie_cuadra(self):
        viaje(self.empresa, fecha=self.hoy, estado=Reserva.Estado.ASIGNADA, embarcacion=self.grande)
        EmbarcacionNoDisponible.objects.create(
            empresa=self.empresa, fecha=self.hoy,
            embarcacion=Embarcacion.objects.filter(
                empresa=self.empresa, capacidad_maxima=3).first(),
        )

        panorama = armar_panorama(self.hoy, self.empresa)

        self.assertEqual(panorama.ocupadas[0], 1)
        self.assertEqual(panorama.a_flote[0], 9)

    def test_una_cancelada_libera_su_celda(self):
        cancelada = viaje(
            self.empresa, fecha=self.hoy, estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.grande,
        )
        Reserva.objects.filter(pk=cancelada.pk).update(estado=Reserva.Estado.CANCELADA)

        renglon = self._renglon_de(armar_panorama(self.hoy, self.empresa), self.grande)

        self.assertIsNone(renglon.celdas[0].reserva)

    def test_no_crece_en_consultas_con_los_dias(self):
        """Fijas: reservas del rango, los dias de mar de paquetes, pangas activas, las marcadas fuera,
        los atrasados y el contexto de cupo del rango (tope y apartados por dia, 4 consultas). Sin
        ninguna por celda ni por dia — son 70 celdas con la flota completa."""
        with self.assertNumQueries(9):
            armar_panorama(self.hoy, self.empresa, dias=7)
        with self.assertNumQueries(9):
            armar_panorama(self.hoy, self.empresa, dias=1)

    def test_el_resumen_cuenta_lo_que_falta(self):
        viaje(self.empresa, fecha=self.hoy + timedelta(days=1))
        viaje(
            self.empresa, fecha=self.hoy + timedelta(days=2),
            estado=Reserva.Estado.ASIGNADA, embarcacion=self.grande,
        )
        viaje(self.empresa, fecha=self.hoy - timedelta(days=2))

        resumen = armar_panorama(self.hoy, self.empresa).resumen

        self.assertEqual(
            (resumen.sin_panga, resumen.sin_capitan, resumen.atrasados), (1, 1, 1))
        self.assertFalse(resumen.todo_al_dia)

    def test_el_resumen_de_una_semana_limpia_dice_que_todo_esta_al_dia(self):
        capitan = Capitan.objects.create(
            empresa=self.empresa, nombre='Juan Perez', telefono='+5216121234567')
        viaje(
            self.empresa, fecha=self.hoy + timedelta(days=2),
            estado=Reserva.Estado.ASIGNADA, embarcacion=self.grande, capitan=capitan,
        )

        self.assertTrue(armar_panorama(self.hoy, self.empresa).resumen.todo_al_dia)

    def test_cada_celda_sabe_su_fecha(self):
        """`panorama.js` marca las pangas libres del dia de la reserva tocada."""
        renglon = self._renglon_de(armar_panorama(self.hoy, self.empresa), self.grande)

        self.assertEqual(
            [c.fecha for c in renglon.celdas][:2], [self.hoy, self.hoy + timedelta(days=1)])

    def _renglon_de(self, panorama, embarcacion):
        return next(r for r in panorama.renglones if r.embarcacion.pk == embarcacion.pk)


class PanoramaEnLaAgendaTests(EmpresaTestCase):
    """La cuadricula se pinta dentro del listado de la agenda, plegable."""

    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())

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
        viaje(
            self.empresa, fecha=date.today() + timedelta(days=1),
            estado=Reserva.Estado.ASIGNADA,
            embarcacion=Embarcacion.objects.filter(
                empresa=self.empresa, capacidad_maxima=5).first(),
        )

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


class AsignarDesdeLaAgendaTests(EmpresaTestCase):
    """Lo que se ve y se ofrece al asignar: pendientes primero, y solo las pangas que
    sirven. Guardar sigue validando en el modelo; esto evita llegar al error."""

    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())
        self.manana = date.today() + timedelta(days=1)
        self.grandes = list(Embarcacion.objects.filter(
            empresa=self.empresa, capacidad_maxima=5).order_by('nombre'))
        self.chicas = list(Embarcacion.objects.filter(
            empresa=self.empresa, capacidad_maxima=3).order_by('nombre'))

    def _forma_de(self, reserva):
        formset = self.client.get(self.url).context['cl'].formset
        return next(f for f in formset.forms if f.instance.pk == reserva.pk)

    def _opciones(self, reserva, campo='embarcacion'):
        return set(self._forma_de(reserva).fields[campo].queryset.values_list('pk', flat=True))

    def test_un_grupo_de_cinco_solo_ve_las_pangas_donde_cabe(self):
        reserva = viaje(self.empresa, fecha=self.manana, numero_personas=5)

        self.assertEqual(self._opciones(reserva), {p.pk for p in self.grandes})

    def test_una_panga_ya_tomada_ese_dia_no_se_ofrece(self):
        viaje(
            self.empresa, fecha=self.manana, estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.grandes[0], nombre_cliente='Otra',
        )
        reserva = viaje(self.empresa, fecha=self.manana, numero_personas=5)

        self.assertEqual(self._opciones(reserva), {self.grandes[1].pk})

    def test_una_panga_fuera_de_servicio_no_se_ofrece(self):
        EmbarcacionNoDisponible.objects.create(
            empresa=self.empresa, fecha=self.manana, embarcacion=self.grandes[0], motivo='Motor')
        reserva = viaje(self.empresa, fecha=self.manana, numero_personas=5)

        self.assertEqual(self._opciones(reserva), {self.grandes[1].pk})

    def test_la_panga_ya_asignada_sigue_en_su_selector(self):
        reserva = viaje(
            self.empresa, fecha=self.manana, estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.grandes[0], numero_personas=5,
        )

        self.assertIn(self.grandes[0].pk, self._opciones(reserva))

    def test_otra_fecha_no_estorba(self):
        viaje(
            self.empresa, fecha=self.manana + timedelta(days=1), estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.grandes[0], nombre_cliente='Otra',
        )
        reserva = viaje(self.empresa, fecha=self.manana, numero_personas=5)

        self.assertEqual(self._opciones(reserva), {p.pk for p in self.grandes})

    def test_un_capitan_con_viaje_ese_dia_no_se_ofrece(self):
        ocupado = Capitan.objects.create(empresa=self.empresa, nombre='Ocupado', telefono='1')
        libre = Capitan.objects.create(empresa=self.empresa, nombre='Libre', telefono='2')
        viaje(
            self.empresa, fecha=self.manana, estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.chicas[0], capitan=ocupado, nombre_cliente='Otra',
        )
        reserva = viaje(self.empresa, fecha=self.manana)

        self.assertEqual(self._opciones(reserva, 'capitan'), {libre.pk})

    def test_sin_pangas_libres_el_selector_lo_dice(self):
        for panga in self.grandes:
            viaje(
                self.empresa, fecha=self.manana, estado=Reserva.Estado.ASIGNADA,
                embarcacion=panga, nombre_cliente=f'Otra {panga.pk}',
            )
        reserva = viaje(self.empresa, fecha=self.manana, numero_personas=5)

        self.assertEqual(
            self._forma_de(reserva).fields['embarcacion'].empty_label,
            'Sin pangas libres donde quepan',
        )

    def test_al_guardar_una_panga_tomada_el_modelo_explica_por_que(self):
        """El selector ya no la ofrece, pero un formulario viejo o una pestana
        abierta mucho rato puede mandarla: el error tiene que decir la razon."""
        viaje(
            self.empresa, fecha=self.manana, estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.grandes[0], nombre_cliente='Otra',
        )
        reserva = viaje(self.empresa, fecha=self.manana, numero_personas=5)

        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(reserva.pk),
            'form-0-embarcacion': str(self.grandes[0].pk),
            'form-0-capitan': '',
            '_save': 'Guardar',
        })

        self.assertContains(respuesta, 'ya tiene un viaje')
        reserva.refresh_from_db()
        self.assertIsNone(reserva.embarcacion_id)

    def test_lo_que_no_tiene_panga_va_primero(self):
        asignada = viaje(
            self.empresa, fecha=self.manana, estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.grandes[0], nombre_cliente='Con panga',
        )
        pendiente = viaje(
            self.empresa, fecha=self.manana + timedelta(days=3), nombre_cliente='Sin panga',
        )

        filas = [r.pk for r in self.client.get(self.url).context['cl'].result_list]

        self.assertEqual(filas, [pendiente.pk, asignada.pk])

    def test_el_aviso_va_pegado_a_la_panga_y_no_al_final(self):
        from .admin import AgendaAdmin

        columnas = AgendaAdmin.list_display
        self.assertLess(columnas.index('capitan'), columnas.index('aviso'))
        self.assertLess(columnas.index('aviso'), columnas.index('avisado'))

    def test_el_resumen_y_los_pendientes_se_pintan_con_nombre_y_grupo(self):
        viaje(self.empresa, fecha=self.manana, numero_personas=3)

        html = self.client.get(self.url).content.decode()

        self.assertIn('data-resumen', html)
        self.assertIn('Sin panga (1)', html)
        self.assertIn('data-pendiente', html)
        self.assertIn('Ana Ruiz', html)
        self.assertIn('3 pers', html)
        self.assertIn('Pangas ocupadas', html)

    def test_una_semana_sin_pendientes_dice_todo_asignado(self):
        html = self.client.get(self.url).content.decode()

        self.assertIn('Todo asignado', html)
        self.assertNotRegex(html, r'data-todo-asignado\s+hidden')

    def test_con_algo_pendiente_no_dice_todo_asignado(self):
        viaje(self.empresa, fecha=self.manana)

        html = self.client.get(self.url).content.decode()

        self.assertRegex(html, r'data-todo-asignado\s+hidden')

    def test_el_resumen_esta_en_el_titulo_y_no_dentro_de_la_cuadricula(self):
        """Bajo la columna "Panga" se leia como datos de una panga."""
        viaje(self.empresa, fecha=self.manana)

        html = self.client.get(self.url).content.decode()

        self.assertLess(html.index('<summary'), html.index('data-resumen'))
        self.assertLess(html.index('data-resumen'), html.index('</summary>'))

    def test_los_viajes_sin_panga_van_arriba_de_las_pangas(self):
        """Con diez pangas, si lo pendiente fuera al final quedaria bajo el pliegue,
        lejos de las celdas donde hay que soltarlo."""
        viaje(self.empresa, fecha=self.manana)

        html = self.client.get(self.url).content.decode()

        self.assertLess(html.index('data-pendiente'), html.index('data-celda'))

    def test_la_ayuda_esta_junto_a_la_cuadricula_y_no_al_final(self):
        html = self.client.get(self.url).content.decode()

        self.assertLess(html.index('data-panorama-ayuda'), html.index('data-celda'))

    def test_el_resumen_vive_en_la_fila_de_pendientes_y_no_aparte(self):
        viaje(self.empresa, fecha=self.manana)
        viaje(self.empresa, fecha=date.today() - timedelta(days=1), nombre_cliente='Tarde')

        html = self.client.get(self.url).content.decode()

        self.assertEqual(html.count('data-resumen'), 1)
        self.assertIn('>1</b> atrasado', html)

    def test_el_selector_de_panga_muestra_nombre_y_capacidad_sin_botones_extra(self):
        reserva = viaje(self.empresa, fecha=self.manana, numero_personas=5)

        forma = self._forma_de(reserva)
        panga = forma.fields['embarcacion']
        self.assertEqual(panga.label_from_instance(self.grandes[0]), f'{self.grandes[0].nombre} (5)')
        self.assertFalse(panga.widget.can_add_related)
        self.assertFalse(panga.widget.can_change_related)
        self.assertFalse(panga.widget.can_delete_related)

    def test_el_capitan_conserva_poder_crearse_desde_la_agenda(self):
        reserva = viaje(self.empresa, fecha=self.manana)

        capitan = self._forma_de(reserva).fields['capitan']
        self.assertTrue(capitan.widget.can_add_related)
        self.assertFalse(capitan.widget.can_change_related)
        self.assertFalse(capitan.widget.can_delete_related)

    def test_avisado_no_pone_rojo_en_lo_que_aun_no_tiene_panga(self):
        """Una cruz roja en cada viaje pendiente le quitaba al rojo su significado."""
        viaje(self.empresa, fecha=self.manana)

        html = self.client.get(self.url).content.decode()

        self.assertNotIn('icon-no', html)
        self.assertNotIn('Pendiente', html)  # sin panga todavia: no hay nada que avisar

    def test_avisado_dice_pendiente_o_enviado_cuando_ya_hay_panga(self):
        from django.contrib import admin as django_admin

        from .admin import AgendaAdmin

        sin_aviso = viaje(
            self.empresa, fecha=self.manana, estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.grandes[0], nombre_cliente='Sin aviso',
        )
        con_aviso = viaje(
            self.empresa, fecha=self.manana, estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.grandes[1], nombre_cliente='Con aviso',
            aviso_asignacion_enviado_en=timezone.now(),
        )
        sin_panga = viaje(self.empresa, fecha=self.manana, nombre_cliente='Sin panga')

        modelo = AgendaAdmin(Agenda, django_admin.site)
        self.assertIn('Pendiente', modelo.avisado(sin_aviso))
        self.assertIn('Enviado', modelo.avisado(con_aviso))
        self.assertEqual(modelo.avisado(sin_panga), '—')

    def test_la_fecha_se_dice_como_en_el_panorama(self):
        from django.contrib import admin as django_admin

        from .admin import AgendaAdmin

        reserva = viaje(self.empresa, fecha=date.today() + timedelta(days=1))
        texto = AgendaAdmin(Agenda, django_admin.site).dia(reserva)

        self.assertIn(str((date.today() + timedelta(days=1)).day), texto)
        self.assertNotIn(' de ', texto)  # nada de "10 de Octubre de 2026"

    def test_el_pie_y_el_contador_los_mantiene_el_script(self):
        viaje(self.empresa, fecha=self.manana)

        html = self.client.get(self.url).content.decode()

        self.assertIn('data-sin-panga="1"', html)

    def test_la_celda_ocupada_dice_de_que_reserva_es_para_celebrar_al_guardar(self):
        reserva = viaje(
            self.empresa, fecha=self.manana, estado=Reserva.Estado.ASIGNADA,
            embarcacion=self.grandes[0], nombre_cliente='Con panga',
        )

        html = self.client.get(self.url).content.decode()

        self.assertIn(f'data-reserva="{reserva.pk}"', html)

    def test_el_movimiento_respeta_reducir_movimiento(self):
        """Quien pide menos movimiento no ve nada desplazarse: ni en CSS ni en el
        script. Los cambios se siguen viendo, como fundidos."""
        from pathlib import Path

        estaticos = Path(__file__).parent / 'static' / 'bookings'
        self.assertIn('prefers-reduced-motion', (estaticos / 'admin-columnas.css').read_text(encoding='utf-8'))
        self.assertIn('prefers-reduced-motion', (estaticos / 'panorama.js').read_text(encoding='utf-8'))

    def test_las_celdas_llevan_los_datos_que_usa_el_script(self):
        html = self.client.get(self.url).content.decode()

        for atributo in ['data-celda', 'data-fecha=', 'data-embarcacion=', 'data-capacidad=']:
            self.assertIn(atributo, html)
