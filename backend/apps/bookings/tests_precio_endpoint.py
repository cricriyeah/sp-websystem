"""Pruebas para el endpoint de precio sugerido y sus recursos estaticos en el backoffice."""

from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.bookings.admin import ReservaAdmin
from apps.bookings.precio_sugerido import sugerir_precio
from apps.fleet.enums import (
    EstrategiaCupo,
    EstrategiaPrecio,
    TipoServicio,
    TipoTraslado,
    Zona,
)
from apps.fleet.models import (
    Paquete,
    PaqueteServicio,
    Servicio,
    TransporteTarifa,
)
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca


class PrecioSugeridoEndpointTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.servicio_pesca = crear_servicio_pesca(
            self.empresa,
            precio_base=Decimal('4500.00'),
            precio_persona_extra=Decimal('500.00'),
            personas_incluidas=3,
        )
        self.url = reverse('admin:bookings_reserva_precio_sugerido')

    def test_vendedora_cotiza_servicio_pesca_de_su_empresa(self):
        """Vendedora pide precio de pesca de su empresa y coincide con sugerir_precio."""
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)

        esperado_mxn = sugerir_precio(
            servicio=self.servicio_pesca,
            numero_personas=2,
            moneda='MXN',
        )
        self.assertIsNotNone(esperado_mxn)

        respuesta = self.client.get(self.url, {
            'servicio': self.servicio_pesca.pk,
            'personas': 2,
            'moneda': 'MXN',
        })
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['precio'], str(esperado_mxn))
        self.assertEqual(datos['moneda'], 'MXN')
        self.assertEqual(datos['etiqueta'], 'Sugerido: 4,500 MXN')

        # Cotizacion en USD usando el tipo de cambio de la sede
        esperado_usd = sugerir_precio(
            servicio=self.servicio_pesca,
            numero_personas=2,
            moneda='USD',
        )
        self.assertIsNotNone(esperado_usd)

        respuesta_usd = self.client.get(self.url, {
            'servicio': self.servicio_pesca.pk,
            'personas': 2,
            'moneda': 'USD',
        })
        self.assertEqual(respuesta_usd.status_code, 200)
        datos_usd = respuesta_usd.json()
        self.assertEqual(datos_usd['precio'], str(esperado_usd))
        self.assertEqual(datos_usd['moneda'], 'USD')

    def test_servicio_de_otra_empresa_devuelve_precio_none(self):
        """Un servicio ajeno a la empresa de la vendedora no se cotiza."""
        otra_sede = Sede.objects.create(
            nombre='Otra Sede', slug='otra-sede', zona_horaria='America/Mazatlan',
        )
        otra_empresa = Empresa.objects.create(
            sede=otra_sede, nombre='Otra Empresa', slug='otra-empresa',
        )
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                servicio_ajeno = crear_servicio_pesca(otra_empresa)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)

        respuesta = self.client.get(self.url, {
            'servicio': servicio_ajeno.pk,
            'personas': 2,
            'moneda': 'MXN',
        })
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertIsNone(datos['precio'])
        self.assertIsNone(datos['etiqueta'])

    def test_parametros_invalidos_o_faltantes_devuelven_200_con_precio_none(self):
        """Entradas incorrectas o ausentes devuelven status 200 con precio None sin 500."""
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)

        casos = [
            {},  # Sin parametros
            {'servicio': self.servicio_pesca.pk, 'personas': 'abc', 'moneda': 'MXN'},  # Personas no entero
            {'servicio': self.servicio_pesca.pk, 'personas': 2, 'moneda': 'EUR'},  # Moneda invalida
            {'servicio': 'xyz', 'personas': 2, 'moneda': 'MXN'},  # Servicio no entero
            {'paquete': 'xyz', 'personas': 2, 'moneda': 'MXN'},  # Paquete no entero
            {'servicio': self.servicio_pesca.pk, 'paquete': 1, 'personas': 2, 'moneda': 'MXN'},  # Ambos presentes
            {'servicio': self.servicio_pesca.pk, 'personas': 0, 'moneda': 'MXN'},  # Personas < 1
        ]
        for params in casos:
            with self.subTest(params=params):
                respuesta = self.client.get(self.url, params)
                self.assertEqual(respuesta.status_code, 200)
                datos = respuesta.json()
                self.assertIsNone(datos.get('precio'))
                self.assertIsNone(datos.get('etiqueta'))

    def test_usuario_sin_permiso_de_alta_ni_cambio_recibe_403(self):
        """Un usuario sin permiso para add o change en Reserva recibe 403."""
        usuario_sin_permisos = self.crear_vendedora(username='sin_permisos', permisos=[])
        self.client.force_login(usuario_sin_permisos)

        respuesta = self.client.get(self.url, {
            'servicio': self.servicio_pesca.pk,
            'personas': 2,
            'moneda': 'MXN',
        })
        self.assertEqual(respuesta.status_code, 403)

    def test_usuario_anonimo_redirige_a_login(self):
        """Peticiones sin autenticar son redirigidas al login del admin."""
        self.client.logout()

        respuesta = self.client.get(self.url, {
            'servicio': self.servicio_pesca.pk,
            'personas': 2,
            'moneda': 'MXN',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/login/', respuesta.url)

    def test_metodo_post_no_permitido(self):
        """Solo se admite el metodo GET en este endpoint."""
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)

        respuesta = self.client.post(self.url, {
            'servicio': self.servicio_pesca.pk,
            'personas': 2,
            'moneda': 'MXN',
        })
        self.assertEqual(respuesta.status_code, 405)

    def test_paquete_de_una_empresa_calcula_precio(self):
        """Paquete dentro de la empresa lider devuelve sugerencia igual a sugerir_precio."""
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Pesca Grupo',
            slug='paquete-pesca-grupo',
            precio_ancla=Decimal('7500.00'),
            estrategia_precio=EstrategiaPrecio.POR_GRUPO,
            personas_precio_base=3,
            precio_persona_extra=Decimal('500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio_pesca,
            orden=1,
            dia_estancia=1,
            personas_incluidas=3,
        )
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)

        esperado = sugerir_precio(paquete=paquete, numero_personas=3, moneda='MXN')
        self.assertIsNotNone(esperado)

        respuesta = self.client.get(self.url, {
            'paquete': paquete.pk,
            'personas': 3,
            'moneda': 'MXN',
        })
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['precio'], str(esperado))
        self.assertEqual(datos['moneda'], 'MXN')
        self.assertEqual(datos['etiqueta'], 'Sugerido: 7,500 MXN')

    def test_traslado_con_tipo_traslado_y_zona_calcula_tarifa(self):
        """Traslado con tipo y zona calcula contra TransporteTarifa activa."""
        servicio_transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Servicio Traslados',
            slug='servicio-traslados',
            tipo_servicio=TipoServicio.TRANSPORTE,
            estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
            estrategia_precio=EstrategiaPrecio.POR_RUTA,
            activo=True,
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            zona=Zona.CENTRO,
            personas_min=1,
            personas_max=4,
            precio=Decimal('1500.00'),
            activo=True,
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
            personas_min=1,
            personas_max=4,
            precio=Decimal('4500.00'),
            activo=True,
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
            personas_min=5,
            personas_max=10,
            precio=Decimal('6000.00'),
            activo=True,
        )
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)

        # 1. Redondo actividad con zona
        respuesta_act = self.client.get(self.url, {
            'servicio': servicio_transporte.pk,
            'personas': 2,
            'moneda': 'MXN',
            'tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
            'zona': Zona.CENTRO,
        })
        self.assertEqual(respuesta_act.status_code, 200)
        datos_act = respuesta_act.json()
        self.assertEqual(datos_act['precio'], '1500.00')
        self.assertEqual(datos_act['etiqueta'], 'Sugerido: 1,500 MXN')

        # 2. Redondo aeropuerto con personas_traslado escalonando tarifa
        respuesta_aero = self.client.get(self.url, {
            'servicio': servicio_transporte.pk,
            'personas': 2,
            'moneda': 'MXN',
            'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
            'personas_traslado': 6,
        })
        self.assertEqual(respuesta_aero.status_code, 200)
        datos_aero = respuesta_aero.json()
        self.assertEqual(datos_aero['precio'], '6000.00')
        self.assertEqual(datos_aero['etiqueta'], 'Sugerido: 6,000 MXN')

    def test_operador_cotiza_servicio_sin_filtro_de_empresa(self):
        """El operador de plataforma puede consultar cotizaciones de cualquier empresa."""
        otra_sede = Sede.objects.create(
            nombre='Otra Sede Op', slug='otra-sede-op', zona_horaria='America/Mazatlan',
        )
        otra_empresa = Empresa.objects.create(
            sede=otra_sede, nombre='Otra Empresa Op', slug='otra-empresa-op',
        )
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                servicio_ajeno = crear_servicio_pesca(otra_empresa)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        operador = get_user_model().objects.create_user('op_test', password='x', is_staff=True)
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        self.client.force_login(operador)

        self._alcance.__exit__(None, None, None)
        try:
            respuesta = self.client.get(self.url, {
                'servicio': servicio_ajeno.pk,
                'personas': 2,
                'moneda': 'MXN',
            })
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['precio'], '4500.00')
        self.assertEqual(datos['etiqueta'], 'Sugerido: 4,500 MXN')

    def test_js_esta_en_media_y_existe_archivo_y_se_incluye_en_alta(self):
        """Verifica el registro en Media, existencia fisica del JS e inclusion en el HTML."""
        # 1. En ReservaAdmin.Media
        self.assertIn('bookings/alta-reserva.js', ReservaAdmin.Media.js)

        # 2. Archivo fisico en static/bookings/
        ruta_archivo = Path(__file__).resolve().parent / 'static' / 'bookings' / 'alta-reserva.js'
        self.assertTrue(ruta_archivo.is_file(), f'El archivo {ruta_archivo} debe existir en el disco.')

        # 3. La pagina de alta de Reserva incluye alta-reserva.js en el HTML servido
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)
        url_alta = reverse('admin:bookings_reserva_add')
        respuesta = self.client.get(url_alta)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'bookings/alta-reserva.js')
