"""Pruebas unitarias de modelos Paquete y PaqueteServicio (Pieza 5)."""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.fleet.models import Paquete, PaqueteServicio, Servicio, TransporteTarifa
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
        )
        self.servicio_paseo = Servicio.objects.create(
            empresa=self.empresa_pesca,
            nombre='Paseo Costero',
            slug='paseo-costero',
            tipo_servicio='paseo',
            precio_base=Decimal('3500.00'),
        )
        self.servicio_hotel = Servicio.objects.create(
            empresa=self.empresa_hotel,
            nombre='Estadía 2 Noches',
            slug='estadia-2-noches',
            tipo_servicio='hospedaje',
            precio_base=Decimal('3500.00'),
        )
        self.servicio_cabo = Servicio.objects.create(
            empresa=self.empresa_cabo,
            nombre='Snorkel Los Cabos',
            slug='snorkel-los-cabos',
            tipo_servicio='paseo',
            precio_base=Decimal('2000.00'),
        )

    def test_crear_paquete_exitoso(self):
        paquete = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Fin de Semana Inolvidable',
            slug='fin-de-semana',
            descripcion='Pesca y hospedaje frente al malecón',
            precio_ancla=Decimal('7500.00'),
        )
        self.assertEqual(str(paquete), 'Fin de Semana Inolvidable (La Paz)')
        self.assertEqual(paquete.precio_en('MXN'), Decimal('7500.00'))
        self.assertEqual(paquete.precio_en('USD', Decimal('18')), Decimal('417.00'))  # 416.67 -> 417

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
        )
        paquete_invalido = Paquete.objects.create(
            sede=self.sede_lp,
            empresa_lider=self.empresa_pesca,
            nombre='Paquete Barato Invalido',
            slug='paquete-barato-invalido',
            precio_ancla=Decimal('2000.00'),  # 2000 < 2700
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


class PaquetePrecioPorPersonaTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa PPP', slug='empresa-ppp')

    def _paquete(self, **extra):
        datos = dict(
            sede=self.sede, empresa_lider=self.empresa, nombre='Paquete PPP', slug='paquete-ppp',
            precio_ancla=Decimal('45000.00'),
        )
        datos.update(extra)
        return Paquete.objects.create(**datos)

    def test_por_defecto_el_precio_es_un_total_fijo(self):
        paquete = self._paquete()
        self.assertEqual(paquete.estrategia_precio, 'por_grupo')
        self.assertEqual(paquete.precio_total_en('MXN', 3), Decimal('45000.00'))

    def test_por_persona_multiplica_en_mxn_y_usd(self):
        paquete = self._paquete(estrategia_precio='por_persona')
        self.assertEqual(paquete.precio_total_en('MXN', 3), Decimal('135000.00'))
        self.assertEqual(paquete.precio_total_en('USD', 2, Decimal('18')), Decimal('5000.00'))

    def test_usd_sin_tipo_de_cambio_falla(self):
        paquete = self._paquete(estrategia_precio='por_persona')
        with self.assertRaises(ValueError):
            paquete.precio_total_en('USD', 2)

    def _traslado(self, precio):
        servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado PPP', slug='traslado-ppp', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta', capacidad_maxima=14,
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa, tipo_traslado='redondo_aeropuerto', zona='', personas_min=1,
            personas_max=None, precio=Decimal(precio),
        )
        return servicio

    def test_validar_configuracion_revisa_cada_tamano_de_grupo(self):
        servicio = self._traslado('5000.00')
        paquete = self._paquete(
            estrategia_precio='por_persona', precio_ancla=Decimal('4000.00'),
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=servicio, personas_incluidas=2)
        with self.assertRaises(ValidationError) as ctx:
            paquete.validar_configuracion()
        self.assertTrue(any('tarifa de transporte' in m for m in ctx.exception.messages))

    def test_validar_configuracion_acepta_un_precio_que_cubre_el_traslado(self):
        servicio = self._traslado('3500.00')
        paquete = self._paquete(estrategia_precio='por_persona')
        PaqueteServicio.objects.create(paquete=paquete, servicio=servicio, personas_incluidas=2)
        paquete.validar_configuracion()

    def test_por_grupo_con_extra_revisa_la_tarifa_de_cada_tamano(self):
        servicio = self._traslado('3500.00')
        TransporteTarifa.objects.filter(empresa=self.empresa).update(personas_max=1)
        TransporteTarifa.objects.create(
            empresa=self.empresa, tipo_traslado='redondo_aeropuerto', zona='',
            personas_min=2, personas_max=2, precio=Decimal('5000.00'),
        )
        paquete = self._paquete(
            estrategia_precio='por_grupo', personas_precio_base=1,
            precio_persona_extra=Decimal('1000.00'), precio_ancla=Decimal('4000.00'),
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=servicio, personas_incluidas=2)
        paquete.validar_configuracion()

    def test_el_catalogo_publico_expone_la_estrategia_y_sus_parametros(self):
        from apps.fleet.serializers import PaqueteSerializer
        paquete = self._paquete(estrategia_precio='por_persona')
        datos = PaqueteSerializer(paquete).data
        self.assertEqual(datos['estrategia_precio'], 'por_persona')
        self.assertEqual(datos['personas_precio_base'], 1)
        self.assertEqual(datos['precio_persona_extra'], '0.00')
        self.assertTrue(datos['precio_depende_de_personas'])
        self.assertNotIn('precio_por_persona', datos)
