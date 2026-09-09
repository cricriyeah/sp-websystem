from datetime import time
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.fleet.enums import EstrategiaCupo, EstrategiaPrecio, ModoOcupacion, TipoServicio
from apps.fleet.models import Servicio
from apps.testing import EmpresaTestCase


class ServicioEnumsTests(EmpresaTestCase):
    def test_campos_usan_choices(self):
        campos_y_enums = [
            ('tipo_servicio', TipoServicio),
            ('estrategia_cupo', EstrategiaCupo),
            ('estrategia_precio', EstrategiaPrecio),
            ('modo_ocupacion', ModoOcupacion),
        ]
        for campo, enum_cls in campos_y_enums:
            choices = dict(Servicio._meta.get_field(campo).choices)
            self.assertEqual(set(choices.keys()), set(enum_cls.values))

    def test_defaults(self):
        self.assertEqual(Servicio._meta.get_field('tipo_servicio').default, 'pesca')
        self.assertEqual(Servicio._meta.get_field('estrategia_cupo').default, 'por_recurso_dia')
        self.assertEqual(Servicio._meta.get_field('estrategia_precio').default, 'por_grupo')
        self.assertEqual(Servicio._meta.get_field('modo_ocupacion').default, 'exclusivo')

    def test_porcentaje_anticipo(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='X',
            slug='x',
            precio_base=Decimal('100'),
        )
        self.assertEqual(servicio.porcentaje_anticipo, 30)

    def test_servicio_transporte_valido(self):
        servicio = Servicio(
            empresa=self.empresa,
            nombre='Traslado Aeropuerto',
            slug='traslado-aeropuerto',
            tipo_servicio=TipoServicio.TRANSPORTE,
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
            precio_base=Decimal('0.00'),
        )
        servicio.full_clean()
        servicio.save()
        self.assertEqual(servicio.tipo_servicio, 'transporte')

    def test_capacidad_maxima(self):
        servicio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Servicio Sin Capacidad',
            slug='servicio-sin-capacidad',
            precio_base=Decimal('100.00'),
        )
        self.assertIsNone(servicio.capacidad_maxima)

        servicio.capacidad_maxima = 14
        servicio.full_clean()
        servicio.save()
        servicio.refresh_from_db()
        self.assertEqual(servicio.capacidad_maxima, 14)

    def test_ventana_horaria(self):
        servicio = Servicio(
            empresa=self.empresa,
            nombre='Servicio Sin Ventana',
            slug='servicio-sin-ventana',
            precio_base=Decimal('100.00'),
        )
        self.assertIsNone(servicio.ventana_horaria())

        servicio.hora_apertura = time(5, 0)
        servicio.hora_cierre = time(7, 0)
        self.assertEqual(servicio.ventana_horaria(), (time(5, 0), time(7, 0)))

    def test_ventana_horaria_clean_rechaza_inconsistencias(self):
        servicio = Servicio(
            empresa=self.empresa,
            nombre='Servicio Invalido',
            slug='servicio-invalido',
            precio_base=Decimal('100.00'),
            hora_apertura=time(5, 0),
        )
        with self.assertRaises(ValidationError):
            servicio.clean()

        servicio.hora_apertura = time(8, 0)
        servicio.hora_cierre = time(6, 0)
        with self.assertRaises(ValidationError):
            servicio.clean()

    def test_data_migration_ventana_pesca(self):
        import importlib
        from django.apps import apps as django_apps
        from django.db import connection

        mig = importlib.import_module('apps.fleet.migrations.0029_servicio_hora_apertura_servicio_hora_cierre')

        class FakeSchemaEditor:
            def __init__(self, conn):
                self.connection = conn

        schema_editor = FakeSchemaEditor(connection)

        pesca = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Pesca Test Migracion',
            slug='pesca-test-migracion',
            tipo_servicio='pesca',
            precio_base=Decimal('100.00'),
            hora_apertura=None,
            hora_cierre=None,
        )
        paseo = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Paseo Test Migracion',
            slug='paseo-test-migracion',
            tipo_servicio='paseo',
            precio_base=Decimal('100.00'),
            hora_apertura=None,
            hora_cierre=None,
        )

        mig.set_ventana_pesca(django_apps, schema_editor)
        pesca.refresh_from_db()
        paseo.refresh_from_db()
        self.assertEqual(pesca.hora_apertura, time(5, 0))
        self.assertEqual(pesca.hora_cierre, time(7, 0))
        self.assertIsNone(paseo.hora_apertura)
        self.assertIsNone(paseo.hora_cierre)

        mig.unset_ventana_pesca(django_apps, schema_editor)
        pesca.refresh_from_db()
        self.assertIsNone(pesca.hora_apertura)
        self.assertIsNone(pesca.hora_cierre)




