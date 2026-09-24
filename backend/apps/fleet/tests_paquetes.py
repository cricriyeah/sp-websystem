"""Pruebas unitarias de modelos Paquete y PaqueteServicio (Pieza 5)."""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class PaquetesModelTests(OperadorTestCase):
    def setUp(self):
        self.sede_lp, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.sede_csl = Sede.objects.create(nombre='Cabo San Lucas', slug='cabo-san-lucas-test')

        self.empresa_pesca = Empresa.objects.create(
            sede=self.sede_lp, nombre='Pesca La Paz Test', slug='pesca-lp-test'
        )
        self.empresa_hotel = Empresa.objects.create(
            sede=self.sede_lp, nombre='Hotel Malecón Test', slug='hotel-malecon-test'
        )
        self.empresa_cabo = Empresa.objects.create(
            sede=self.sede_csl, nombre='Tours Cabo Test', slug='tours-cabo-test'
        )

        self.servicio_pesca = Servicio.objects.create(
            empresa=self.empresa_pesca,
            nombre='Pesca Deportiva Día Completo',
            slug='pesca-dia-completo',
            tipo_servicio='pesca',
            precio_base=Decimal('5000.00'),
            precio_base_usd=Decimal('290.00'),
        )
        self.servicio_paseo = Servicio.objects.create(
            empresa=self.empresa_pesca,
            nombre='Paseo Costero',
            slug='paseo-costero',
            tipo_servicio='paseo',
            precio_base=Decimal('3500.00'),
            precio_base_usd=Decimal('200.00'),
        )
        self.servicio_hotel = Servicio.objects.create(
            empresa=self.empresa_hotel,
            nombre='Estadía 2 Noches',
            slug='estadia-2-noches',
            tipo_servicio='hospedaje',
            precio_base=Decimal('3500.00'),
            precio_base_usd=Decimal('200.00'),
        )
        self.servicio_cabo = Servicio.objects.create(
            empresa=self.empresa_cabo,
            nombre='Snorkel Los Cabos',
            slug='snorkel-los-cabos',
            tipo_servicio='paseo',
            precio_base=Decimal('2000.00'),
            precio_base_usd=Decimal('120.00'),
        )

    def test_crear_paquete_exitoso(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Fin de Semana Inolvidable',
            slug='fin-de-semana',
            descripcion='Pesca y hospedaje frente al malecón',
            precio_ancla=Decimal('7500.00'),
            precio_ancla_usd=Decimal('440.00'),
        )
        self.assertEqual(str(paquete), 'Fin de Semana Inolvidable (La Paz)')
        self.assertEqual(paquete.precio_en('MXN'), Decimal('7500.00'))
        self.assertEqual(paquete.precio_en('USD'), Decimal('440.00'))

    def test_validacion_empresa_lider_misma_sede(self):
        paquete_invalido = Paquete(
            sede=self.sede_lp,
            empresa_lider=self.empresa_cabo,  # Empresa de Los Cabos en Sede La Paz
            nombre='Paquete Mixto Inválido',
            slug='paquete-invalido',
            precio_ancla=Decimal('6000.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            paquete_invalido.clean()
        self.assertIn('empresa_lider', ctx.exception.message_dict)

    def test_unicidad_slug_por_sede(self):
        Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Aventura Marina',
            slug='aventura-marina',
            precio_ancla=Decimal('5000.00'),
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Paquete.objects.create(
                    sede=self.sede_lp,
                    empresa_lider=self.empresa_pesca,
                    nombre='Aventura Marina Duplicada',
                    slug='aventura-marina',
                    precio_ancla=Decimal('5200.00'),
                )
        # Mismo slug en otra sede sí es permitido
        paquete_otra_sede = Paquete.objects.create(
            sede=self.sede_csl,
            empresa_lider=self.empresa_cabo,
            nombre='Aventura Marina Cabo',
            slug='aventura-marina',
            precio_ancla=Decimal('5500.00'),
        )
        self.assertIsNotNone(paquete_otra_sede.pk)

    def test_asociacion_paquete_servicios_misma_empresa(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Pesca y Paseo',
            slug='pesca-paseo',
            precio_ancla=Decimal('8000.00'),
            precio_ancla_usd=Decimal('470.00'),
        )
        ps1 = PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio_pesca,
            orden=1,
        )
        ps2 = PaqueteServicio(
            paquete=paquete,
            servicio=self.servicio_paseo,
            orden=2,
        )
        ps2.clean()
        ps2.save()

        self.assertEqual(paquete.servicios_asociados.count(), 2)
        self.assertEqual(str(ps1), 'Pesca y Paseo -> Pesca Deportiva Día Completo')

    def test_paquete_servicio_acepta_componente_otra_empresa_misma_sede(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Paquete La Paz',
            slug='paquete-lp',
            precio_ancla=Decimal('5000.00'),
        )
        # Servicio de otra empresa (hotel), misma sede (La Paz): debe aceptarse (cierra ADR-005)
        ps_valido = PaqueteServicio(
            paquete=paquete,
            servicio=self.servicio_hotel,
            orden=1,
        )
        # full_clean no debe lanzar ValidationError
        ps_valido.full_clean()
        ps_valido.save()
        self.assertEqual(ps_valido.servicio.empresa, self.empresa_hotel)
        self.assertEqual(ps_valido.paquete.empresa_lider, self.empresa_pesca)

    def test_paquete_servicio_rechaza_componente_otra_sede(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Paquete La Paz',
            slug='paquete-lp-otra-sede',
            precio_ancla=Decimal('5000.00'),
        )
        # Servicio de empresa en otra sede (Cabo San Lucas): debe rechazarse
        ps_otra_sede = PaqueteServicio(
            paquete=paquete,
            servicio=self.servicio_cabo,
            orden=1,
        )
        with self.assertRaises(ValidationError) as ctx:
            ps_otra_sede.full_clean()
        self.assertIn('servicio', ctx.exception.message_dict)
        self.assertIn('El servicio debe pertenecer a una empresa de la misma sede que el paquete.', ctx.exception.message_dict['servicio'])

    def test_paquete_servicio_mono_empresa_sigue_siendo_valido(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Paquete Mono',
            slug='paquete-mono',
            precio_ancla=Decimal('5000.00'),
        )
        ps_mono = PaqueteServicio(
            paquete=paquete,
            servicio=self.servicio_pesca,
            orden=1,
        )
        ps_mono.full_clean()
        ps_mono.save()

    def test_paquete_clean_con_componentes_no_valida_ajustes(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Paquete Componentes',
            slug='paquete-componentes',
            precio_ancla=Decimal('1000.00'),
            precio_ancla_usd=Decimal('60.00'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio_pesca,
        )
        PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio_paseo,
        )
        # Paquete cerrado: clean() pasa sin validar ajustes de componentes
        paquete.clean()

    def test_unicidad_paquete_servicio(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Paquete Test',
            slug='paquete-test',
            precio_ancla=Decimal('4000.00'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio_pesca,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                PaqueteServicio.objects.create(
                    paquete=paquete,
                    servicio=self.servicio_pesca,
                )

    def test_paquete_cruza_empresa_validar_configuracion_precio_cubre_transporte(self):
        from apps.fleet.models import TransporteTarifa
        from apps.fleet.enums import TipoTraslado
        empresa_transporte = Empresa.objects.create(
            sede=self.sede_lp, nombre='Transporte LP Test', slug='transporte-lp-test'
        )
        servicio_transporte = Servicio.objects.create(
            empresa=empresa_transporte,
            nombre='Traslado Aeropuerto',
            slug='traslado-aero',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
        )
        TransporteTarifa.objects.create(
            empresa=empresa_transporte,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            personas_min=1,
            personas_max=4,
            precio=Decimal('2700.00'),
            precio_usd=Decimal('160.00'),
        )
        paquete_invalido = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Paquete Barato Invalido',
            slug='paquete-barato-invalido',
            precio_ancla=Decimal('2000.00'),  # 2000 < 2700
            precio_ancla_usd=Decimal('100.00'),
            permite_anticipo=False,
        )
        PaqueteServicio.objects.create(
            paquete=paquete_invalido,
            servicio=self.servicio_pesca,
            orden=1,
        )
        ps_transporte = PaqueteServicio(
            paquete=paquete_invalido,
            servicio=servicio_transporte,
            orden=2,
        )
        ps_transporte.full_clean()
        ps_transporte.save()
        paquete_invalido.full_clean()
        with self.assertRaises(ValidationError) as ctx:
            paquete_invalido.validar_configuracion()
        mensajes = ' '.join(ctx.exception.messages)
        self.assertIn('no puede ser menor que la tarifa de transporte', mensajes)
        self.assertIn('tarifa de transporte en USD', mensajes)
