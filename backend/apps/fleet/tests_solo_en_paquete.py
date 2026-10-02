"""Un servicio marcado `solo_en_paquete` no se vende suelto: ni se lista, ni se
consulta, ni se compra por la ruta de traslados, ni se reserva directo."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.bookings.serializers import ReservaCheckoutSerializer, TrasladoCheckoutSerializer
from apps.fleet.enums import TipoTraslado
from apps.fleet.models import Servicio, TransporteTarifa
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class SoloEnPaqueteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        sede = Sede.objects.create(nombre='Sede SP', slug='sede-sp')
        self.empresa = Empresa.objects.create(
            sede=sede, nombre='Empresa SP', slug='empresa-sp', activo=True,
            stripe_secret_key='sk_test_sp', stripe_publishable_key='pk_test_sp',
        )
        with scope.con_empresa(self.empresa):
            self.traslado = Servicio.objects.create(
                empresa=self.empresa, nombre='Traslado paquete', slug='traslado-paquete',
                tipo_servicio='transporte', estrategia_cupo='bajo_demanda',
                estrategia_precio='por_ruta', capacidad_maxima=14, permite_anticipo=False,
                solo_en_paquete=True,
            )
            self.suelto = Servicio.objects.create(
                empresa=self.empresa, nombre='Hospedaje suelto', slug='hospedaje-suelto',
                tipo_servicio='hospedaje', estrategia_cupo='por_noche', estrategia_precio='por_noche',
            )
            TransporteTarifa.objects.create(
                empresa=self.empresa, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                personas_min=1, personas_max=4, precio='3500.00',
            )

    def test_por_defecto_se_vende_suelto(self):
        self.assertFalse(self.suelto.solo_en_paquete)

    def test_lista_por_empresa_omite_el_servicio(self):
        slugs = [s['slug'] for s in self.client.get(f'/api/{self.empresa.slug}/servicios/').json()]
        self.assertEqual(slugs, ['hospedaje-suelto'])

    def test_lista_por_sede_omite_el_servicio(self):
        slugs = [s['slug'] for s in self.client.get('/api/sedes/sede-sp/servicios/').json()]
        self.assertEqual(slugs, ['hospedaje-suelto'])

    def test_detalle_responde_404(self):
        self.assertEqual(self.client.get(f'/api/{self.empresa.slug}/servicios/traslado-paquete/').status_code, 404)

    def test_catalogo_de_traslados_responde_404(self):
        self.assertEqual(self.client.get(f'/api/{self.empresa.slug}/traslados/').status_code, 404)

    def test_reserva_directa_no_acepta_el_servicio(self):
        campo = ReservaCheckoutSerializer(context={'empresa': self.empresa}).fields['servicio']
        self.assertNotIn(self.traslado, campo.queryset)
        self.assertIn(self.suelto, campo.queryset)

    def test_checkout_de_traslado_no_acepta_el_servicio(self):
        campo = TrasladoCheckoutSerializer(context={'empresa': self.empresa}).fields['servicio']
        self.assertNotIn(self.traslado, campo.queryset)
