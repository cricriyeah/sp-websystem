"""Pruebas de endpoints públicos de cupo (/api/cupo/ y /api/cupo/rango/) con apartados temporales."""

from datetime import date, timedelta
import uuid

from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from apps.fleet.models import Embarcacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa
from apps.testing import ApiTestCase, crear_flota, crear_servicio_pesca

from .cupo import (
    MOTIVO_LLENO,
    MOTIVO_SIN_PANGA,
    construir_retrato_servicio_suelto,
)
from .models import (
    CupoDiario,
    Reserva,
    disponibilidad_por_fecha,
    proxima_fecha_disponible,
)
from .tests import crear_reserva


class ApartadoEndpointsPublicosTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.servicio = crear_servicio_pesca(self.empresa)
        crear_flota(self.empresa)
        self.fecha = timezone.localdate() + timedelta(days=5)

    def _crear_reserva_con_apartado(self, fecha=None, personas=2, minutos=15, **extra):
        """Crea una reserva pendiente_pago con retrato y apartado_hasta configurado."""
        fecha_reserva = fecha or self.fecha
        checkout_id = extra.pop('checkout_id', uuid.uuid4())
        nombre = extra.pop('nombre_cliente', 'Ana Ruiz')
        reserva = crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=fecha_reserva,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            numero_personas=personas,
            nombre_cliente=nombre,
            checkout_id=checkout_id,
            **extra,
        )
        reserva.apartado_hasta = timezone.now() + timedelta(minutes=minutos)
        reserva.apartado_demanda = construir_retrato_servicio_suelto(reserva)
        reserva.save(update_fields=['apartado_hasta', 'apartado_demanda'])
        return reserva

    @override_settings(APARTADO_MINUTOS=15)
    def test_sin_cabecera_apartado_ajeno_llena_el_dia(self):
        """Sin cabecera X-Checkout-Id, un apartado vigente ajeno hace que el día salga lleno."""
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)
        self._crear_reserva_con_apartado(nombre_cliente='Carlos Soto')

        url = f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        cuerpo = response.json()
        self.assertFalse(cuerpo['disponible'])
        self.assertEqual(cuerpo['motivo_no_disponible'], MOTIVO_LLENO)
        self.assertEqual(cuerpo['ocupadas'], 1)

    @override_settings(APARTADO_MINUTOS=15)
    def test_con_cabecera_propio_checkout_id_dia_sale_disponible(self):
        """Con la cabecera X-Checkout-Id del propio checkout_id el día sale disponible."""
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)
        r = self._crear_reserva_con_apartado(nombre_cliente='Elena Gomez')

        url = f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2'
        response = self.client.get(url, HTTP_X_CHECKOUT_ID=str(r.checkout_id))

        self.assertEqual(response.status_code, 200)
        cuerpo = response.json()
        self.assertTrue(cuerpo['disponible'])
        self.assertIsNone(cuerpo['motivo_no_disponible'])
        # Su propio apartado se excluye también de ocupadas
        self.assertEqual(cuerpo['ocupadas'], 0)

    @override_settings(APARTADO_MINUTOS=15)
    def test_cabecera_inexistente_o_invalida_se_ignora(self):
        """Cabecera inexistente o con formato no-UUID se ignora sin error."""
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)
        self._crear_reserva_con_apartado(nombre_cliente='Hugo Perez')

        url = f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2'

        # UUID que no corresponde a ninguna reserva
        resp_inexistente = self.client.get(url, HTTP_X_CHECKOUT_ID=str(uuid.uuid4()))
        self.assertEqual(resp_inexistente.status_code, 200)
        self.assertFalse(resp_inexistente.json()['disponible'])
        self.assertEqual(resp_inexistente.json()['motivo_no_disponible'], MOTIVO_LLENO)
        self.assertEqual(resp_inexistente.json()['ocupadas'], 1)

        # Cadena que no es un UUID válido
        resp_invalida = self.client.get(url, HTTP_X_CHECKOUT_ID='cabecera-no-uuid')
        self.assertEqual(resp_invalida.status_code, 200)
        self.assertFalse(resp_invalida.json()['disponible'])
        self.assertEqual(resp_invalida.json()['motivo_no_disponible'], MOTIVO_LLENO)
        self.assertEqual(resp_invalida.json()['ocupadas'], 1)

    @override_settings(APARTADO_MINUTOS=15)
    def test_cabecera_de_otra_empresa_se_ignora(self):
        """Cabecera con checkout_id de otra empresa se ignora sin error."""
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)
        self._crear_reserva_con_apartado(nombre_cliente='Laura Diaz')

        empresa_b = Empresa.objects.create(
            sede=self.sede, nombre='Segunda Empresa', slug='segunda-empresa-test',
        )
        checkout_id_otra = uuid.uuid4()
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(empresa_b):
                servicio_b = crear_servicio_pesca(empresa_b)
                crear_flota(empresa_b)
                r_otra = crear_reserva(
                    empresa_b,
                    servicio=servicio_b,
                    fecha=self.fecha,
                    estado=Reserva.Estado.PENDIENTE_PAGO,
                    numero_personas=2,
                    nombre_cliente='Mario Luna',
                    checkout_id=checkout_id_otra,
                )
                r_otra.apartado_hasta = timezone.now() + timedelta(minutes=15)
                r_otra.apartado_demanda = construir_retrato_servicio_suelto(r_otra)
                r_otra.save(update_fields=['apartado_hasta', 'apartado_demanda'])
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        url = f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2'
        response = self.client.get(url, HTTP_X_CHECKOUT_ID=str(checkout_id_otra))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['disponible'])
        self.assertEqual(response.json()['motivo_no_disponible'], MOTIVO_LLENO)
        self.assertEqual(response.json()['ocupadas'], 1)

    @override_settings(APARTADO_MINUTOS=15)
    def test_rango_cuenta_apartados_y_excluye_propio(self):
        """El endpoint /api/cupo/rango/ cuenta apartados ajenos y excluye el propio por cabecera."""
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)
        r = self._crear_reserva_con_apartado(nombre_cliente='Nora Vega')

        hasta = self.fecha + timedelta(days=2)
        url = f'/api/{self.empresa.slug}/cupo/rango/?desde={self.fecha}&hasta={hasta}&personas=2'

        # Sin cabecera: el día con apartado sale lleno
        resp_sin = self.client.get(url)
        self.assertEqual(resp_sin.status_code, 200)
        dias_sin = resp_sin.json()['dias']
        self.assertEqual(dias_sin[str(self.fecha)], MOTIVO_LLENO)
        self.assertIsNone(dias_sin[str(self.fecha + timedelta(days=1))])

        # Con cabecera propia: el día sale disponible
        resp_con = self.client.get(url, HTTP_X_CHECKOUT_ID=str(r.checkout_id))
        self.assertEqual(resp_con.status_code, 200)
        dias_con = resp_con.json()['dias']
        self.assertIsNone(dias_con[str(self.fecha)])

        # Con cabecera inexistente: sigue saliendo lleno
        resp_inex = self.client.get(url, HTTP_X_CHECKOUT_ID=str(uuid.uuid4()))
        self.assertEqual(resp_inex.status_code, 200)
        self.assertEqual(resp_inex.json()['dias'][str(self.fecha)], MOTIVO_LLENO)

    @override_settings(APARTADO_MINUTOS=15)
    def test_proxima_fecha_disponible_cuenta_apartados_y_excluye_propio(self):
        """proxima_fecha_disponible salta días con apartado ajeno y excluye el propio."""
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)
        r = self._crear_reserva_con_apartado(nombre_cliente='Pedro Rios')

        dia_siguiente = self.fecha + timedelta(days=1)

        # Lógica de modelo
        self.assertEqual(proxima_fecha_disponible(self.fecha, 2, self.empresa), dia_siguiente)
        self.assertEqual(
            proxima_fecha_disponible(self.fecha, 2, self.empresa, excluir_pk=r.pk), self.fecha
        )

        # A través de /api/cupo/
        url = f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2'
        resp_sin = self.client.get(url)
        self.assertEqual(resp_sin.json()['proxima_disponible'], str(dia_siguiente))

        resp_con = self.client.get(url, HTTP_X_CHECKOUT_ID=str(r.checkout_id))
        self.assertEqual(resp_con.json()['proxima_disponible'], str(self.fecha))

    @override_settings(APARTADO_MINUTOS=15)
    def test_ocupadas_suma_apartados_vigentes(self):
        """La cifra 'ocupadas' de /api/cupo/ suma las reservas pagadas y los apartados vigentes."""
        # 1 reserva pagada
        crear_reserva(
            self.empresa,
            servicio=self.servicio,
            fecha=self.fecha,
            estado=Reserva.Estado.PAGADA,
            numero_personas=2,
            nombre_cliente='Rosa Mora',
        )

        # 2 apartados vigentes
        r_hold1 = self._crear_reserva_con_apartado(nombre_cliente='Sara Cano')
        self._crear_reserva_con_apartado(nombre_cliente='Tania Mora')

        url = f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2'

        # Sin cabecera: cuenta la pagada + 2 apartados = 3
        resp_sin = self.client.get(url)
        self.assertEqual(resp_sin.json()['ocupadas'], 3)

        # Con cabecera de r_hold1: excluye r_hold1, quedan 1 pagada + 1 apartado ajeno = 2
        resp_con = self.client.get(url, HTTP_X_CHECKOUT_ID=str(r_hold1.checkout_id))
        self.assertEqual(resp_con.json()['ocupadas'], 2)

    @override_settings(APARTADO_MINUTOS=15)
    def test_apartado_vencido_no_cuenta_en_endpoints(self):
        """Un apartado vencido no ocupa cupo ni suma en ocupadas."""
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)
        self._crear_reserva_con_apartado(minutos=-5, nombre_cliente='Victor Lara')

        url = f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        cuerpo = response.json()
        self.assertTrue(cuerpo['disponible'])
        self.assertIsNone(cuerpo['motivo_no_disponible'])
        self.assertEqual(cuerpo['ocupadas'], 0)

    @override_settings(APARTADO_MINUTOS=0)
    def test_con_apartado_minutos_cero_todo_queda_como_antes(self):
        """Con APARTADO_MINUTOS=0 se ignoran todos los apartados en endpoints y motor."""
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.fecha, cupo_maximo=1)
        r = self._crear_reserva_con_apartado(nombre_cliente='Zulema Soto')

        # Endpoint /api/cupo/
        url_cupo = f'/api/{self.empresa.slug}/cupo/?fecha={self.fecha}&personas=2'
        resp_cupo = self.client.get(url_cupo)
        self.assertTrue(resp_cupo.json()['disponible'])
        self.assertIsNone(resp_cupo.json()['motivo_no_disponible'])
        self.assertEqual(resp_cupo.json()['ocupadas'], 0)
        self.assertEqual(resp_cupo.json()['proxima_disponible'], str(self.fecha))

        # Endpoint /api/cupo/rango/
        url_rango = (
            f'/api/{self.empresa.slug}/cupo/rango/'
            f'?desde={self.fecha}&hasta={self.fecha + timedelta(days=1)}&personas=2'
        )
        resp_rango = self.client.get(url_rango)
        self.assertIsNone(resp_rango.json()['dias'][str(self.fecha)])

        # Modelo
        self.assertEqual(proxima_fecha_disponible(self.fecha, 2, self.empresa), self.fecha)
        self.assertIsNone(
            disponibilidad_por_fecha(self.fecha, self.fecha, 2, self.empresa)[self.fecha]
        )

    def test_cors_allow_headers_incluye_x_checkout_id(self):
        """CORS_ALLOW_HEADERS incluye x-checkout-id."""
        headers_lower = [h.lower() for h in settings.CORS_ALLOW_HEADERS]
        self.assertIn('x-checkout-id', headers_lower)
