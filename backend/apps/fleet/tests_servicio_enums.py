from decimal import Decimal

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


