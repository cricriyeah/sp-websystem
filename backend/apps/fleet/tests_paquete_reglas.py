"""Campos y reglas de configuración de un paquete."""
from decimal import Decimal

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class CamposDePaqueteServicioTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa CP', slug='empresa-cp')
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca-cp', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='P', slug='p-cp',
            precio_ancla=Decimal('5000.00'),
        )

    def test_defaults_de_estancia_y_personas(self):
        ps = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio, orden=1)
        self.assertEqual(ps.dia_estancia, 1)
        self.assertIsNone(ps.noches)
        self.assertEqual(ps.personas_incluidas, 2)
