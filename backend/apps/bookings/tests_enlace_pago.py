"""Pruebas para el generador del enlace de pago por WhatsApp en el backoffice."""

from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, quote, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.fleet.models import Paquete, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca
from apps.bookings.models import Reserva, Vendedora


@override_settings(FRONTEND_URL='https://sitio.example')
class EnlacePagoTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.servicio = crear_servicio_pesca(self.empresa)
        self.url = reverse('admin:bookings_reserva_enlace_pago')

        # Vendedora con perfil activo
        self.usuario_vendedora = self.crear_vendedora('vendedora_enlace')
        self.perfil_vendedora = Vendedora.objects.create(
            usuario=self.usuario_vendedora,
            empresa=self.empresa,
            codigo='ventas-ana',
            activo=True,
        )

        # Jefe sin perfil de vendedora
        self.jefe_sin_perfil = self.crear_jefe('jefe_enlace')

        # Usuario sin permiso de alta (para probar 403 y ocultamiento del boton)
        self.vendedora_sin_permiso = self.crear_vendedora('vendedora_sin_alta', permisos=[])

    def test_url_resolucion_y_permisos(self):
        """La URL se resuelve; anónimo redirige al login y usuario sin permiso de alta da 403."""
        self.assertEqual(self.url, '/admin/bookings/reserva/enlace-de-pago/')

        # Anonimo redirige al login
        resp_anon = self.client.get(self.url)
        self.assertEqual(resp_anon.status_code, 302)
        self.assertIn('/admin/login/', resp_anon.url)

        # Usuario sin permiso de alta da 403
        self.client.force_login(self.vendedora_sin_permiso)
        resp_403 = self.client.get(self.url)
        self.assertEqual(resp_403.status_code, 403)

    def test_get_sin_parametros_muestra_formulario_vacio(self):
        """GET sin query string responde 200, muestra formulario y no genera ningun enlace."""
        self.client.force_login(self.usuario_vendedora)
        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('form', resp.context)
        self.assertIsNone(resp.context['enlace'])
        self.assertFalse(resp.context['mostrar_resultado'])
        self.assertNotContains(resp, 'https://sitio.example')

    def test_vendedora_genera_enlace_servicio_es_y_en(self):
        """Vendedora con perfil genera enlace de servicio con parametros exactos y ref automatico."""
        self.client.force_login(self.usuario_vendedora)
        fecha_viaje = timezone.localdate() + timedelta(days=2)

        datos = {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': fecha_viaje.isoformat(),
            'hora': '06:00',
            'personas': 3,
            'idioma': 'es',
        }
        resp_es = self.client.get(self.url, datos)
        self.assertEqual(resp_es.status_code, 200)
        enlace_es = resp_es.context['enlace']
        self.assertIsNotNone(enlace_es)

        parsed_es = urlparse(enlace_es)
        self.assertEqual(parsed_es.scheme, 'https')
        self.assertEqual(parsed_es.netloc, 'sitio.example')
        self.assertEqual(parsed_es.path, '/es/reservar')

        qs_es = parse_qs(parsed_es.query)
        self.assertEqual(qs_es, {
            'servicio': [self.servicio.slug],
            'empresa': [self.empresa.slug],
            'day': [fecha_viaje.isoformat()],
            'time': ['06:00'],
            'people': ['3'],
            'ref': ['ventas-ana'],
        })

        # Variante en ingles (/en/reservar)
        datos['idioma'] = 'en'
        resp_en = self.client.get(self.url, datos)
        self.assertEqual(resp_en.status_code, 200)
        enlace_en = resp_en.context['enlace']
        parsed_en = urlparse(enlace_en)
        self.assertEqual(parsed_en.path, '/en/reservar')

    def test_paquete_genera_enlace_sin_day_time_people(self):
        """Paquete lleva paquete, sede y ref; NO incluye day, time ni people."""
        paquete = Paquete.objects.create(
            empresa_lider=self.empresa,
            sede=self.sede,
            nombre='Experiencia Aventura',
            slug='experiencia-aventura',
            precio_ancla=Decimal('8500.00'),
            activo=True,
        )
        self.client.force_login(self.usuario_vendedora)
        fecha_viaje = timezone.localdate() + timedelta(days=3)

        # Aunque se envien fecha, hora y personas, deben ser ignorados para paquetes
        datos = {
            'producto': f'paquete:{paquete.pk}',
            'fecha': fecha_viaje.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
        }
        resp = self.client.get(self.url, datos)
        self.assertEqual(resp.status_code, 200)
        enlace = resp.context['enlace']
        self.assertIsNotNone(enlace)

        parsed = urlparse(enlace)
        qs = parse_qs(parsed.query)
        self.assertEqual(qs.get('paquete'), [paquete.slug])
        self.assertEqual(qs.get('sede'), [self.sede.slug])
        self.assertEqual(qs.get('ref'), ['ventas-ana'])
        self.assertNotIn('day', qs)
        self.assertNotIn('time', qs)
        self.assertNotIn('people', qs)

    def test_validaciones_servicio(self):
        """Rechaza fecha pasada/hoy, hora fuera de ventana, personas invalidas y servicio ajeno."""
        self.client.force_login(self.usuario_vendedora)

        # 1. Fecha de hoy rechazada
        resp_hoy = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': timezone.localdate().isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
        })
        self.assertEqual(resp_hoy.status_code, 200)
        self.assertFormError(resp_hoy.context['form'], 'fecha', 'La fecha debe ser a partir de mañana.')
        self.assertIsNone(resp_hoy.context['enlace'])

        # 2. Fecha pasada rechazada
        resp_pasada = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': (timezone.localdate() - timedelta(days=1)).isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
        })
        self.assertFormError(resp_pasada.context['form'], 'fecha', 'La fecha debe ser a partir de mañana.')

        # 3. Hora fuera de ventana (servicio pesca es de 05:00 a 07:00)
        manana = timezone.localdate() + timedelta(days=1)
        resp_hora = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': manana.isoformat(),
            'hora': '14:00',
            'personas': 2,
            'idioma': 'es',
        })
        self.assertFormError(resp_hora.context['form'], 'hora', 'La hora debe estar dentro del horario del servicio (05:00 a 07:00).')

        # 4. Personas 0 o superior al maximo
        resp_p0 = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': manana.isoformat(),
            'hora': '06:00',
            'personas': 0,
            'idioma': 'es',
        })
        self.assertTrue(resp_p0.context['form'].errors.get('personas'))

        resp_p_exceso = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': manana.isoformat(),
            'hora': '06:00',
            'personas': 10,
            'idioma': 'es',
        })
        self.assertFormError(resp_p_exceso.context['form'], 'personas', 'El número de personas no puede superar la capacidad máxima (5).')

        # 5. Servicio de otra empresa: error de campo, no revela su existencia
        otra_empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Externa', slug='empresa-externa', activo=True,
        )
        # EmpresaTestCase mantiene abierto el alcance de su empresa: se sale mientras se
        # siembra la otra y se restaura despues.
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                servicio_ajeno = Servicio.objects.create(
                    empresa=otra_empresa,
                    nombre='Pesca Externa',
                    slug='pesca-externa',
                    tipo_servicio='pesca',
                    activo=True,
                    solo_en_paquete=False,
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        resp_ajeno = self.client.get(self.url, {
            'producto': f'servicio:{servicio_ajeno.pk}',
            'fecha': manana.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
        })
        # Mismo error generico que un id que no existe: no revela que el servicio existe en otra empresa.
        self.assertIn('producto', resp_ajeno.context['form'].errors)
        self.assertIsNone(resp_ajeno.context['enlace'])

    def test_jefe_sin_perfil_atribucion(self):
        """Jefe sin perfil: sin vendedora avisa que no atribuye; con vendedora ajena da error."""
        self.client.force_login(self.jefe_sin_perfil)
        manana = timezone.localdate() + timedelta(days=2)

        # 1. Sin seleccionar vendedora: enlace sin ref y aviso visible
        resp_sin_v = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': manana.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
        })
        self.assertEqual(resp_sin_v.status_code, 200)
        enlace_sin_v = resp_sin_v.context['enlace']
        self.assertIsNotNone(enlace_sin_v)
        self.assertNotIn('ref', parse_qs(urlparse(enlace_sin_v).query))
        self.assertTrue(resp_sin_v.context['sin_atribucion'])
        self.assertContains(resp_sin_v, 'Este enlace no atribuye la venta a nadie')

        # 2. Con vendedora de su empresa: ref atribuido correctamente
        resp_con_v = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': manana.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
            'vendedora': str(self.perfil_vendedora.pk),
        })
        self.assertEqual(resp_con_v.status_code, 200)
        enlace_con_v = resp_con_v.context['enlace']
        self.assertEqual(parse_qs(urlparse(enlace_con_v).query).get('ref'), ['ventas-ana'])
        self.assertFalse(resp_con_v.context['sin_atribucion'])

        # 3. Con vendedora de otra empresa: error en el campo vendedora
        otra_empresa = Empresa.objects.create(
            sede=self.sede, nombre='Segunda Empresa', slug='segunda-empresa', activo=True,
        )
        usuario_ajeno = get_user_model().objects.create_user('vendedora_otra', password='x', is_staff=True)
        # EmpresaTestCase mantiene abierto el alcance de su empresa: se sale mientras se
        # siembra la otra y se restaura despues.
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                vendedora_ajena = Vendedora.objects.create(
                    usuario=usuario_ajeno, empresa=otra_empresa, codigo='ventas-otra', activo=True,
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        resp_v_ajena = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': manana.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
            'vendedora': str(vendedora_ajena.pk),
        })
        self.assertTrue(resp_v_ajena.context['form'].errors.get('vendedora'))
        self.assertIsNone(resp_v_ajena.context['enlace'])

    def test_whatsapp_con_y_sin_telefono(self):
        """Genera el enlace a wa.me con o sin telefono y mensaje codificado."""
        self.client.force_login(self.usuario_vendedora)
        manana = timezone.localdate() + timedelta(days=2)

        # Con telefono a 10 digitos (agrega lada 52)
        resp_con_tel = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': manana.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
            'telefono': '612 123 4567',
        })
        self.assertEqual(resp_con_tel.status_code, 200)
        wa_con_tel = resp_con_tel.context['whatsapp_url']
        enlace = resp_con_tel.context['enlace']
        self.assertTrue(wa_con_tel.startswith('https://wa.me/526121234567?text='))
        self.assertIn(quote(enlace), wa_con_tel)

        # Sin telefono
        resp_sin_tel = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': manana.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
        })
        self.assertEqual(resp_sin_tel.status_code, 200)
        wa_sin_tel = resp_sin_tel.context['whatsapp_url']
        self.assertTrue(wa_sin_tel.startswith('https://wa.me/?text='))
        self.assertIn(quote(resp_sin_tel.context['enlace']), wa_sin_tel)

    def test_sin_frontend_url_muestra_aviso(self):
        """Si FRONTEND_URL no esta configurado muestra aviso claro y no genera enlace roto."""
        self.client.force_login(self.usuario_vendedora)
        manana = timezone.localdate() + timedelta(days=2)

        with override_settings(FRONTEND_URL=''):
            resp = self.client.get(self.url, {
                'producto': f'servicio:{self.servicio.pk}',
                'fecha': manana.isoformat(),
                'hora': '06:00',
                'personas': 2,
                'idioma': 'es',
            })
            self.assertEqual(resp.status_code, 200)
            self.assertIsNone(resp.context['enlace'])
            self.assertTrue(resp.context['sin_frontend_url'])
            self.assertContains(resp, 'FRONTEND_URL')

    def test_no_crea_ninguna_reserva(self):
        """Ninguna llamada al generador escribe ni crea una Reserva."""
        cuenta_inicial = Reserva.objects.count()
        self.client.force_login(self.usuario_vendedora)
        manana = timezone.localdate() + timedelta(days=2)

        self.client.get(self.url)
        self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': manana.isoformat(),
            'hora': '06:00',
            'personas': 2,
            'idioma': 'es',
        })
        self.client.get(self.url, {
            'producto': f'servicio:{self.servicio.pk}',
            'fecha': timezone.localdate().isoformat(),  # Invalido
            'personas': 2,
        })
        self.assertEqual(Reserva.objects.count(), cuenta_inicial)

    def test_boton_enlace_pago_en_changelist(self):
        """El botón Enlace de pago aparece en changelist con permiso y desaparece sin permiso."""
        # Con permiso de alta: el botón Enlace de pago aparece
        self.client.force_login(self.usuario_vendedora)
        resp_con_perm = self.client.get(reverse('admin:bookings_reserva_changelist'))
        self.assertEqual(resp_con_perm.status_code, 200)
        self.assertContains(resp_con_perm, 'Enlace de pago')

        # Sin permiso de alta pero con permiso de ver la lista: el botón no aparece
        solo_ver = self.crear_vendedora('vendedora_solo_ver', permisos=[])
        solo_ver.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(solo_ver)
        resp_sin_perm = self.client.get(reverse('admin:bookings_reserva_changelist'))
        self.assertEqual(resp_sin_perm.status_code, 200)
        self.assertNotContains(resp_sin_perm, 'Enlace de pago')


@override_settings(FRONTEND_URL='https://sitio.example')
class OperadorEnlacePagoTests(TestCase):
    """El operador de plataforma ve servicios de varias empresas y genera enlaces de cada una."""

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede Operador', slug='sede-operador', activo=True)
        cls.empresa_alfa = Empresa.objects.create(
            sede=sede, nombre='Empresa Alfa', slug='empresa-alfa', activo=True,
        )
        cls.empresa_beta = Empresa.objects.create(
            sede=sede, nombre='Empresa Beta', slug='empresa-beta', activo=True,
        )
        cls.operador = get_user_model().objects.create_user('operador_enlace', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))

        with scope.como_operador_plataforma():
            cls.servicio_alfa = Servicio.objects.create(
                empresa=cls.empresa_alfa,
                nombre='Pesca Alfa',
                slug='pesca-alfa',
                tipo_servicio='pesca',
                activo=True,
                solo_en_paquete=False,
            )
            cls.servicio_beta = Servicio.objects.create(
                empresa=cls.empresa_beta,
                nombre='Pesca Beta',
                slug='pesca-beta',
                tipo_servicio='pesca',
                activo=True,
                solo_en_paquete=False,
            )
        cls.url = reverse('admin:bookings_reserva_enlace_pago')

    def setUp(self):
        self.client.force_login(self.operador)

    def test_operador_ve_multiples_empresas_y_genera_enlace_con_slug_correcto(self):
        manana = timezone.localdate() + timedelta(days=2)

        # 1. Enlace para Empresa Alfa
        resp_alfa = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio_alfa.pk}',
            'fecha': manana.isoformat(),
            'personas': 2,
            'idioma': 'es',
        })
        self.assertEqual(resp_alfa.status_code, 200)
        enlace_alfa = resp_alfa.context['enlace']
        self.assertIsNotNone(enlace_alfa)
        qs_alfa = parse_qs(urlparse(enlace_alfa).query)
        self.assertEqual(qs_alfa.get('empresa'), ['empresa-alfa'])
        self.assertEqual(qs_alfa.get('servicio'), ['pesca-alfa'])

        # 2. Enlace para Empresa Beta
        resp_beta = self.client.get(self.url, {
            'producto': f'servicio:{self.servicio_beta.pk}',
            'fecha': manana.isoformat(),
            'personas': 3,
            'idioma': 'es',
        })
        self.assertEqual(resp_beta.status_code, 200)
        enlace_beta = resp_beta.context['enlace']
        self.assertIsNotNone(enlace_beta)
        qs_beta = parse_qs(urlparse(enlace_beta).query)
        self.assertEqual(qs_beta.get('empresa'), ['empresa-beta'])
        self.assertEqual(qs_beta.get('servicio'), ['pesca-beta'])
