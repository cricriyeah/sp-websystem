"""Paquete de una empresa con hospedaje y traslado: la clienta elige el aeropuerto y queda en la reserva."""
from decimal import Decimal

from apps.bookings.serializers import ReservaCheckoutSerializer
from apps.fleet.models import PaqueteServicio, Servicio
from apps.testing import OperadorTestCase

from .tests_paquete_estancia import FixturePaqueteEstancia


class AeropuertoDePaqueteTests(FixturePaqueteEstancia, OperadorTestCase):
    def setUp(self):
        self.sembrar()
        self.traslado = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado', slug='traslado-pe', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta', capacidad_maxima=14,
            solo_en_paquete=True,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.traslado, orden=3, dia_estancia=1, personas_incluidas=3,
        )

    def payload(self, **extra):
        datos = {
            'checkout_id': '6f1a5c3e-0000-4000-8000-000000000001', 'fecha': '2026-10-10', 'hora': '06:00:00',
            'numero_personas': 3, 'nombre_cliente': 'Ana Ruiz', 'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com', 'moneda': 'MXN', 'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz', 'paquete': self.paquete.slug, 'personalizaciones': [],
            'personas_por_servicio': {
                str(self.pesca.pk): 3, str(self.hotel.pk): 2, str(self.traslado.pk): 3,
            },
        }
        datos.update(extra)
        return datos

    def validar(self, **extra):
        serializador = ReservaCheckoutSerializer(data=self.payload(**extra), context={'empresa': self.empresa})
        return serializador, serializador.is_valid()

    def test_con_hospedaje_y_traslado_exige_el_aeropuerto(self):
        serializador, valido = self.validar()
        self.assertFalse(valido)
        self.assertIn('aeropuerto', serializador.errors)

    def test_con_aeropuerto_es_valido_y_viaja_en_los_datos(self):
        serializador, valido = self.validar(aeropuerto='sjd')
        self.assertTrue(valido, serializador.errors)
        self.assertEqual(serializador.validated_data['aeropuerto'], 'sjd')

    def test_un_aeropuerto_que_no_existe_se_rechaza(self):
        serializador, valido = self.validar(aeropuerto='xxx')
        self.assertFalse(valido)
        self.assertIn('aeropuerto', serializador.errors)

    def test_un_paquete_sin_traslado_no_pide_aeropuerto(self):
        PaqueteServicio.objects.filter(servicio=self.traslado).delete()
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 3, str(self.hotel.pk): 2})
        self.assertTrue(valido, serializador.errors)


class CoberturaDeAeropuertosTests(AeropuertoDePaqueteTests):
    """Cada sede declara los aeropuertos que cubre: el paquete solo ofrece y acepta esos."""

    def quitar_a_la_sede(self, codigo):
        from apps.tenancy.models import Aeropuerto

        Aeropuerto.objects.get(codigo=codigo).sedes.remove(self.sede)

    def test_un_aeropuerto_que_la_sede_no_cubre_se_rechaza(self):
        self.quitar_a_la_sede('sjd')
        serializador, valido = self.validar(aeropuerto='sjd')
        self.assertFalse(valido)
        self.assertIn('aeropuerto', serializador.errors)

    def test_uno_que_si_cubre_sigue_valido(self):
        self.quitar_a_la_sede('sjd')
        serializador, valido = self.validar(aeropuerto='lap')
        self.assertTrue(valido, serializador.errors)

    def test_un_aeropuerto_inactivo_no_se_acepta(self):
        from apps.tenancy.models import Aeropuerto

        Aeropuerto.objects.filter(codigo='sjd').update(activo=False)
        serializador, valido = self.validar(aeropuerto='sjd')
        self.assertFalse(valido)

    def test_una_sede_sin_aeropuertos_no_lo_exige(self):
        for codigo in ('lap', 'csl', 'sjd', 'lto'):
            self.quitar_a_la_sede(codigo)
        serializador, valido = self.validar()
        self.assertTrue(valido, serializador.errors)

    def test_un_aeropuerto_nuevo_dado_de_alta_se_puede_elegir(self):
        from apps.tenancy.models import Aeropuerto

        nuevo = Aeropuerto.objects.create(codigo='mxl', nombre='Mexicali (MXL)')
        nuevo.sedes.add(self.sede)
        serializador, valido = self.validar(aeropuerto='mxl')
        self.assertTrue(valido, serializador.errors)

    def test_el_catalogo_de_paquetes_expone_los_aeropuertos_de_la_sede(self):
        from apps.fleet.serializers import PaqueteSerializer

        self.quitar_a_la_sede('sjd')
        datos = PaqueteSerializer(self.paquete, context={'sin_componentes': True}).data
        codigos = [a['codigo'] for a in datos['aeropuertos']]
        self.assertEqual(sorted(codigos), ['csl', 'lap', 'lto'])
        self.assertEqual({a['codigo']: a['nombre'] for a in datos['aeropuertos']}['lap'], 'La Paz (LAP)')

    def test_los_cuatro_aeropuertos_de_la_baja_vienen_dados_de_alta(self):
        from apps.tenancy.models import Aeropuerto

        self.assertEqual(sorted(Aeropuerto.objects.values_list('codigo', flat=True)), ['csl', 'lap', 'lto', 'sjd'])
