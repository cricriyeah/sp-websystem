"""El plazo de cambio de fecha que dice el correo es el de lo que se compró (política «Cambios y cancelaciones»)."""
from decimal import Decimal

from apps.bookings.models import Reserva
from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.testing import EmpresaTestCase

from . import plantilla


class PlazoDeCambioTests(EmpresaTestCase):
    def servicio(self, slug, tipo, cupo='bajo_demanda'):
        return Servicio.objects.create(empresa=self.empresa, nombre=slug, slug=slug, tipo_servicio=tipo,
                                       estrategia_cupo=cupo)

    def paquete(self, slug, *servicios):
        paquete = Paquete.objects.create(sede=self.sede, empresa_lider=self.empresa, nombre=slug, slug=slug,
                                         precio_ancla=Decimal('1000'), activo=True)
        for orden, servicio in enumerate(servicios, start=1):
            PaqueteServicio.objects.create(paquete=paquete, servicio=servicio, orden=orden)
        return paquete

    def test_pesca_suelta_48_horas(self):
        reserva = Reserva(empresa=self.empresa, servicio=self.servicio('pesca', 'pesca', 'por_recurso_dia'))
        self.assertEqual(plantilla.plazo_de(reserva), 'dia')

    def test_traslado_24_horas(self):
        reserva = Reserva(empresa=self.empresa, servicio=self.servicio('traslado', 'transporte'))
        self.assertEqual(plantilla.plazo_de(reserva), 'traslado')

    def test_paquete_con_hotel_30_dias(self):
        paquete = self.paquete('seafari-5', self.servicio('hotel', 'hospedaje', 'por_noche'),
                               self.servicio('seafari', 'paseo', 'por_recurso_dia'))
        self.assertEqual(plantilla.plazo_de(Reserva(empresa=self.empresa, paquete=paquete)), 'paquete')

    def test_paquete_sin_hotel_es_de_un_dia(self):
        paquete = self.paquete('pesca-traslado', self.servicio('pesca', 'pesca', 'por_recurso_dia'),
                               self.servicio('traslado', 'transporte'))
        self.assertEqual(plantilla.plazo_de(Reserva(empresa=self.empresa, paquete=paquete)), 'dia')
