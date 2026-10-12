"""Pruebas de visualización de límites de servicio y avisos de disponibilidad en pantallas."""

from datetime import time, timedelta
from urllib.parse import parse_qs, urlparse

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.fleet.models import Embarcacion, EmbarcacionNoDisponible, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca
from apps.bookings.models import CUPO_MAXIMO_DEFAULT, Reserva, Vendedora


@override_settings(FRONTEND_URL='https://sitio.example')
class LimitesPantallasTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.servicio = crear_servicio_pesca(self.empresa)
        self.url_enlace = reverse('admin:bookings_reserva_enlace_pago')
        self.url_alta = reverse('admin:bookings_reserva_add')

        # Vendedora activa con perfil
        self.usuario_vendedora = self.crear_vendedora('vendedora_pantallas')
        self.perfil_vendedora = Vendedora.objects.create(
            usuario=self.usuario_vendedora,
            empresa=self.empresa,
            codigo='ventas-ana',
            activo=True,
        )

    def test_generador_enlace_opciones_y_json_script(self):
        """El generador contiene la etiqueta en la opción del servicio y el json_script limites-servicios."""
        self.client.force_login(self.usuario_vendedora)
        resp = self.client.get(self.url_enlace)

        self.assertEqual(resp.status_code, 200)
        # Etiqueta en el HTML de las opciones
        self.assertContains(resp, f'{self.servicio.nombre} — 05:00 a 07:00 · hasta 5 personas')
        # Script JSON presente
        self.assertContains(resp, 'id="limites-servicios"')

        # Mapa en contexto con datos reales
        mapa = resp.context['limites_servicios']
        clave = f'servicio:{self.servicio.pk}'
        self.assertIn(clave, mapa)
        self.assertEqual(mapa[clave]['apertura'], '05:00')
        self.assertEqual(mapa[clave]['cierre'], '07:00')
        self.assertEqual(mapa[clave]['max_personas'], 5)

    def test_alta_reserva_opciones_y_json_script_aislamiento_empresa(self):
        """El alta contiene la etiqueta en la opción del servicio, el json_script y no muestra otra empresa."""
        self.client.force_login(self.usuario_vendedora)

        # Sembrar otra empresa con su propio servicio saliendo del alcance actual
        self._alcance.__exit__(None, None, None)
        try:
            otra_empresa = Empresa.objects.create(
                sede=self.sede, nombre='Otra Empresa', slug='otra-empresa', activo=True,
            )
            with scope.con_empresa(otra_empresa):
                servicio_ajeno = Servicio.objects.create(
                    empresa=otra_empresa,
                    nombre='Pesca Exclusiva Ajena',
                    slug='pesca-ajena',
                    hora_apertura=time(6, 0),
                    hora_cierre=time(8, 0),
                    activo=True,
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        resp = self.client.get(self.url_alta)
        self.assertEqual(resp.status_code, 200)

        # Servicio de la empresa visible con su etiqueta de límites
        self.assertContains(resp, f'{self.servicio.nombre} — 05:00 a 07:00 · hasta 5 personas')
        self.assertContains(resp, 'id="limites-servicios"')

        # Servicio de otra empresa NO aparece
        self.assertNotContains(resp, 'Pesca Exclusiva Ajena')
        mapa = resp.context['limites_servicios']
        self.assertIn(self.servicio.pk, mapa)
        self.assertNotIn(servicio_ajeno.pk, mapa)

    def test_cambio_dinamico_capacidad_maxima_y_horario(self):
        """Modificar capacidad_maxima o hora_cierre del servicio actualiza etiqueta y mapa dinámicamente."""
        self.client.force_login(self.usuario_vendedora)

        self.servicio.capacidad_maxima = 8
        self.servicio.hora_cierre = time(9, 0)
        self.servicio.save()

        # 1. En el generador de enlace
        resp_enlace = self.client.get(self.url_enlace)
        self.assertContains(resp_enlace, f'{self.servicio.nombre} — 05:00 a 09:00 · hasta 8 personas')
        mapa_enlace = resp_enlace.context['limites_servicios']
        self.assertEqual(mapa_enlace[f'servicio:{self.servicio.pk}']['cierre'], '09:00')
        self.assertEqual(mapa_enlace[f'servicio:{self.servicio.pk}']['max_personas'], 8)

        # 2. En el alta de reserva
        resp_alta = self.client.get(self.url_alta)
        self.assertContains(resp_alta, f'{self.servicio.nombre} — 05:00 a 09:00 · hasta 8 personas')
        mapa_alta = resp_alta.context['limites_servicios']
        self.assertEqual(mapa_alta[self.servicio.pk]['cierre'], '09:00')
        self.assertEqual(mapa_alta[self.servicio.pk]['max_personas'], 8)

    def test_aviso_disponibilidad_con_cupo_linea_verde(self):
        """Con cupo disponible el generador muestra la línea verde y genera el enlace."""
        crear_flota(self.empresa)
        self.client.force_login(self.usuario_vendedora)
        fecha_viaje = timezone.localdate() + timedelta(days=2)

        resp = self.client.get(self.url_enlace, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': fecha_viaje.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context['enlace'])
        self.assertIsNotNone(resp.context['disponibilidad'])
        self.assertTrue(resp.context['disponibilidad']['disponible'])
        self.assertContains(resp, 'Hoy hay lugar para 2 personas ese día (se confirma al pagar)')

    def test_aviso_disponibilidad_dia_lleno_linea_naranja(self):
        """Llenando el día a CUPO_MAXIMO_DEFAULT se muestra la línea naranja de 'ya no quedan viajes' y el enlace sigue apareciendo."""
        crear_flota(self.empresa)
        self.client.force_login(self.usuario_vendedora)
        fecha_viaje = timezone.localdate() + timedelta(days=3)

        # Sembrar 10 reservas pagadas para llenar el día (nombres de personas sin dígitos)
        nombres = [
            'Ana Ruiz', 'Beto Cruz', 'Carlos Soto', 'Diana Lopez', 'Elena Gomez',
            'Fabio Mora', 'Gloria Vega', 'Hugo Rios', 'Ines Silva', 'Jorge Paz',
        ]
        self.assertEqual(len(nombres), CUPO_MAXIMO_DEFAULT)
        for nombre in nombres:
            Reserva.objects.create(
                empresa=self.empresa,
                servicio=self.servicio,
                fecha=fecha_viaje,
                hora=time(6, 0),
                numero_personas=2,
                nombre_cliente=nombre,
                telefono_cliente='+5216121234567',
                correo_cliente='cliente@example.com',
                canal_origen=Reserva.CanalOrigen.WEB,
                deslinde_aceptado=True,
                estado=Reserva.Estado.PAGADA,
            )

        resp = self.client.get(self.url_enlace, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': fecha_viaje.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
        })
        self.assertEqual(resp.status_code, 200)
        # El enlace sigue funcionando
        self.assertIsNotNone(resp.context['enlace'])
        self.assertIsNotNone(resp.context['disponibilidad'])
        self.assertFalse(resp.context['disponibilidad']['disponible'])
        self.assertEqual(resp.context['disponibilidad']['motivo'], 'lleno')

        # Aviso naranja con el motivo legible
        mensaje_esperado = (
            'Ese día ya no tiene lugar para 2 personas (ya no quedan viajes). '
            'Puedes mandar el enlace, pero el cliente verá que no hay disponibilidad; ofrécele otra fecha.'
        )
        self.assertContains(resp, mensaje_esperado)

    def test_aviso_disponibilidad_sin_panga_linea_naranja(self):
        """Si no queda embarcación donde quepa el grupo se muestra la línea naranja de 'no queda una embarcación'."""
        crear_flota(self.empresa)
        self.client.force_login(self.usuario_vendedora)
        fecha_viaje = timezone.localdate() + timedelta(days=4)

        # Las únicas pangas de 5 personas se marcan como no disponibles ese día
        pangas_grandes = Embarcacion.objects.filter(empresa=self.empresa, capacidad_maxima=5)
        self.assertTrue(pangas_grandes.exists())
        for panga in pangas_grandes:
            EmbarcacionNoDisponible.objects.create(
                empresa=self.empresa,
                fecha=fecha_viaje,
                embarcacion=panga,
                motivo='Mantenimiento de motor',
            )

        # Cotizamos un grupo de 5 personas
        resp = self.client.get(self.url_enlace, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': fecha_viaje.isoformat(),
            'hora': '06:00',
            'personas': 5,
            'idioma': 'es',
        })
        self.assertEqual(resp.status_code, 200)
        # El enlace sigue funcionando
        self.assertIsNotNone(resp.context['enlace'])
        self.assertIsNotNone(resp.context['disponibilidad'])
        self.assertFalse(resp.context['disponibilidad']['disponible'])
        self.assertEqual(resp.context['disponibilidad']['motivo'], 'sin_panga')

        mensaje_esperado = (
            'Ese día ya no tiene lugar para 5 personas (no queda una embarcación donde quepa el grupo). '
            'Puedes mandar el enlace, pero el cliente verá que no hay disponibilidad; ofrécele otra fecha.'
        )
        self.assertContains(resp, mensaje_esperado)

    def test_servicio_sin_cupo_por_recurso_dia_sin_linea(self):
        """Un servicio sin cupo por recurso/día (e.g. transporte o bajo demanda) no muestra aviso de disponibilidad."""
        crear_flota(self.empresa)
        self.client.force_login(self.usuario_vendedora)
        fecha_viaje = timezone.localdate() + timedelta(days=5)

        servicio_traslado = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Privado',
            slug='traslado-privado',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            activo=True,
            solo_en_paquete=False,
        )

        resp = self.client.get(self.url_enlace, {
            'producto': f'servicio:{servicio_traslado.pk}',
            'fecha': fecha_viaje.isoformat(),
            'personas': 2,
            'idioma': 'es',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context['enlace'])
        self.assertIsNone(resp.context['disponibilidad'])
        self.assertNotContains(resp, 'Hoy hay lugar para')
        self.assertNotContains(resp, 'Ese día ya no tiene lugar')
