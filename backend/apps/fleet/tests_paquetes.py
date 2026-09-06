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

    def test_asociacion_paquete_servicios_misma_sede(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Pesca y Hotel',
            slug='pesca-hotel',
            precio_ancla=Decimal('8000.00'),
            precio_ancla_usd=Decimal('470.00'),
        )
        ps1 = PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio_pesca,
            orden=1,
            removible=False,
            ajuste_precio=Decimal('0.00'),
        )
        # Servicio de otra empresa (hotel), pero en la misma sede (La Paz): permitido
        ps2 = PaqueteServicio(
            paquete=paquete,
            servicio=self.servicio_hotel,
            orden=2,
            removible=True,
            ajuste_precio=Decimal('3000.00'),
            ajuste_precio_usd=Decimal('175.00'),
        )
        ps2.clean()
        ps2.save()

        self.assertEqual(paquete.servicios_asociados.count(), 2)
        self.assertEqual(ps2.ajuste_en('MXN'), Decimal('3000.00'))
        self.assertEqual(ps2.ajuste_en('USD'), Decimal('175.00'))
        self.assertEqual(str(ps1), 'Pesca y Hotel -> Pesca Deportiva Día Completo')

    def test_validacion_servicio_distinta_sede_falla(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Paquete La Paz',
            slug='paquete-lp',
            precio_ancla=Decimal('5000.00'),
        )
        ps_invalido = PaqueteServicio(
            paquete=paquete,
            servicio=self.servicio_cabo,  # Servicio de Los Cabos en paquete de La Paz
            orden=1,
        )
        with self.assertRaises(ValidationError) as ctx:
            ps_invalido.clean()
        self.assertIn('servicio', ctx.exception.message_dict)

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
