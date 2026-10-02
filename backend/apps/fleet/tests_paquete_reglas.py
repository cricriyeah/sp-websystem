"""Campos y reglas de configuración de un paquete."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.test import SimpleTestCase

from apps.fleet.paquete_reglas import Componente, errores_de_paquete, hay_conflicto_anticipo
from apps.fleet.admin import PaqueteServicioFormSet
from apps.fleet.enums import TipoTraslado
from apps.fleet.models import TransporteTarifa
from apps.fleet.tarifa_transporte import peor_tarifa
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


class EmpresaDelComponenteTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca EC', slug='pesca-ec2')
        self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp EC', slug='transp-ec2')
        self.s_pesca = Servicio.objects.create(
            empresa=self.pesca, nombre='Pesca', slug='pesca-ec2-s', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.s_transp = Servicio.objects.create(
            empresa=self.transp, nombre='Traslado', slug='traslado-ec2-s', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre='P', slug='p-ec2', precio_ancla=Decimal('9000.00'),
            permite_anticipo=False,
        )

    def test_el_componente_copia_la_empresa_de_su_servicio(self):
        ps = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.s_transp, orden=1)
        self.assertEqual(ps.empresa_id, self.transp.pk)

    def test_es_cruza_empresa_cuenta_sobre_la_copia_sin_unir_con_servicio(self):
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.s_pesca, orden=1)
        self.assertFalse(self.paquete.es_cruza_empresa)
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.s_transp, orden=2)
        self.assertTrue(self.paquete.es_cruza_empresa)
        # La consulta no debe unir con fleet_servicio (RLS lo oculta entre empresas).
        with self.assertNumQueries(1):
            self.paquete.es_cruza_empresa

    def test_migracion_de_datos_rellena_empresa_en_filas_viejas(self):
        import importlib
        import pkgutil
        from types import SimpleNamespace

        from django.apps import apps as django_apps
        from django.db import connection

        import apps.fleet.migrations as paquete_migraciones

        nombre = next(
            n for _, n, _ in pkgutil.iter_modules(paquete_migraciones.__path__)
            if n.endswith('_paqueteservicio_empresa')
        )
        modulo = importlib.import_module(f'apps.fleet.migrations.{nombre}')
        ps = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.s_transp, orden=1)
        PaqueteServicio.objects.filter(pk=ps.pk).update(empresa=None)
        modulo.rellenar_empresa(django_apps, SimpleNamespace(connection=connection))
        ps.refresh_from_db()
        self.assertEqual(ps.empresa_id, self.transp.pk)


def _c(nombre='S', empresa=1, estrategia='por_recurso_dia', noches=None, dia=1, personas=2, tope=5):
    return Componente(
        servicio_nombre=nombre, empresa_id=empresa, estrategia_cupo=estrategia,
        noches=noches, dia_estancia=dia, personas_incluidas=personas, tope_personas=tope,
    )


class ReglasDePaqueteTests(SimpleTestCase):
    def errores(self, componentes, permite_anticipo=False):
        return errores_de_paquete(permite_anticipo=permite_anticipo, componentes=componentes)

    def test_paquete_valido_de_una_empresa_con_hospedaje(self):
        componentes = [
            _c('Pesca', dia=2),
            _c('Hotel', estrategia='por_noche', noches=3, dia=1, tope=None),
        ]
        self.assertEqual(self.errores(componentes, permite_anticipo=True), [])

    def test_cruza_empresa_no_admite_anticipo(self):
        errores = self.errores([_c(empresa=1), _c('Traslado', empresa=2, estrategia='bajo_demanda')], permite_anticipo=True)
        self.assertTrue(any('anticipo' in e for e in errores))
        self.assertTrue(hay_conflicto_anticipo(permite_anticipo=True, empresas_ids={1, 2}))
        self.assertFalse(hay_conflicto_anticipo(permite_anticipo=True, empresas_ids={1}))
        self.assertFalse(hay_conflicto_anticipo(permite_anticipo=False, empresas_ids={1, 2}))

    def test_cruza_empresa_solo_un_servicio_por_empresa(self):
        errores = self.errores([_c('A', empresa=1), _c('B', empresa=1), _c('T', empresa=2, estrategia='bajo_demanda')])
        self.assertTrue(any('un servicio por empresa' in e for e in errores))

    def test_solo_un_hospedaje(self):
        errores = self.errores([
            _c('H1', estrategia='por_noche', noches=2, tope=None),
            _c('H2', estrategia='por_noche', noches=2, tope=None),
        ])
        self.assertTrue(any('un hospedaje' in e for e in errores))

    def test_hospedaje_exige_noches_y_los_demas_no_las_admiten(self):
        self.assertTrue(any('noches' in e for e in self.errores([_c('H', estrategia='por_noche', noches=None, tope=None)])))
        self.assertTrue(any('noches' in e for e in self.errores([_c('Pesca', noches=2)])))

    def test_dia_de_estancia(self):
        # Sin hospedaje todo cae el día 1.
        self.assertTrue(any('día' in e for e in self.errores([_c(dia=2)])))
        # Con hospedaje de 2 noches el día 3 (salida) no vale; el 2 sí.
        hotel = _c('Hotel', estrategia='por_noche', noches=2, dia=1, tope=None)
        self.assertTrue(any('día' in e for e in self.errores([_c(dia=3), hotel])))
        self.assertEqual(self.errores([_c(dia=2), hotel]), [])
        # El hospedaje empieza el día 1.
        self.assertTrue(any('día' in e for e in self.errores([_c('Hotel', estrategia='por_noche', noches=2, dia=2, tope=None)])))

    def test_las_actividades_comparten_dia(self):
        hotel = _c('Hotel', estrategia='por_noche', noches=3, dia=1, tope=None)
        errores = self.errores([_c('A', dia=1), _c('B', dia=2), hotel])
        self.assertTrue(any('mismos días' in e for e in errores))

    def _actividad(self, dia, salidas, empresa_id=1):
        return Componente(
            servicio_nombre='Pesca', empresa_id=empresa_id, estrategia_cupo='por_recurso_dia', noches=None,
            dia_estancia=dia, personas_incluidas=2, tope_personas=3, salidas=salidas,
        )

    def _hotel(self, noches):
        return Componente(
            servicio_nombre='Hotel', empresa_id=1, estrategia_cupo='por_noche', noches=noches,
            dia_estancia=1, personas_incluidas=2, tope_personas=None,
        )

    def test_salidas_seguidas_dentro_de_la_estancia_son_validas(self):
        self.assertEqual(self.errores([self._hotel(5), self._actividad(2, 4)]), [])
        self.assertEqual(self.errores([self._hotel(7), self._actividad(2, 6)]), [])

    def test_las_salidas_no_pueden_pasar_de_la_estancia(self):
        self.assertTrue(any('fuera de la estancia' in e for e in self.errores([self._hotel(5), self._actividad(2, 5)])))

    def test_sin_hospedaje_no_hay_salidas_multiples(self):
        self.assertTrue(any('dura un día' in e for e in self.errores([self._actividad(1, 3)])))

    def test_salidas_solo_para_actividades(self):
        hotel = Componente(
            servicio_nombre='Hotel', empresa_id=1, estrategia_cupo='por_noche', noches=3,
            dia_estancia=1, personas_incluidas=2, tope_personas=None, salidas=2,
        )
        self.assertTrue(any('solo aplican a actividades' in e for e in self.errores([hotel])))

    def test_las_actividades_deben_compartir_los_mismos_dias(self):
        errores = self.errores([self._hotel(5), self._actividad(2, 4), self._actividad(2, 3)])
        self.assertTrue(any('mismos días' in e for e in errores))

    def test_actividad_multidia_no_puede_compartir_paquete_con_otra_actividad_de_mar(self):
        errores = self.errores([self._hotel(5), self._actividad(2, 4), self._actividad(2, 4)])
        self.assertIn(
            'Una actividad de varios días no puede acompañarse de otra actividad de mar en el mismo paquete.',
            errores,
        )

    def test_salidas_multiples_no_se_admiten_entre_dos_empresas(self):
        traslado = Componente(
            servicio_nombre='Traslado', empresa_id=2, estrategia_cupo='bajo_demanda', noches=None,
            dia_estancia=1, personas_incluidas=2, tope_personas=None,
        )
        self.assertTrue(any('una sola empresa' in e for e in self.errores([self._actividad(1, 2), traslado])))

    def test_personas_incluidas_dentro_del_tope(self):
        self.assertTrue(any('personas' in e for e in self.errores([_c(personas=0)])))
        self.assertTrue(any('personas' in e for e in self.errores([_c(personas=6, tope=5)])))
        self.assertEqual(self.errores([_c(personas=14, tope=None)]), [])


class ConfiguracionDePaqueteTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca CM', slug='pesca-cm')
        self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp CM', slug='transp-cm')
        self.s_pesca = Servicio.objects.create(
            empresa=self.pesca, nombre='Pesca', slug='pesca-cm-s', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.s_transp = Servicio.objects.create(
            empresa=self.transp, nombre='Traslado', slug='traslado-cm-s', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
        )

    def _paquete_cruza(self, slug, precio='9000.00', **extra):
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre=slug, slug=slug,
            precio_ancla=Decimal(precio), **extra,
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=self.s_pesca, orden=1)
        PaqueteServicio.objects.create(paquete=paquete, servicio=self.s_transp, orden=2)
        return paquete

    def test_peor_tarifa_toma_la_mas_alta_aplicable_al_grupo(self):
        for tipo, minimo, maximo, precio in (
            (TipoTraslado.REDONDO_AEROPUERTO, 1, 4, '4500.00'),
            (TipoTraslado.REDONDO_AEROPUERTO, 5, None, '6000.00'),
            (TipoTraslado.RECEPCION_AEROPUERTO, 1, None, '2700.00'),
        ):
            TransporteTarifa.objects.create(
                empresa=self.transp, tipo_traslado=tipo, personas_min=minimo, personas_max=maximo, precio=precio,
            )
        tarifas = list(self.transp.tarifas_transporte.filter(activo=True))
        self.assertEqual(peor_tarifa(tarifas, personas=2, moneda='MXN'), Decimal('4500.00'))
        self.assertEqual(peor_tarifa(tarifas, personas=8, moneda='MXN'), Decimal('6000.00'))
        self.assertEqual(peor_tarifa(tarifas, personas=2, moneda='USD', tipo_cambio=Decimal('18')), Decimal('250.00'))

    def test_validar_configuracion_exige_que_el_precio_cubra_la_peor_tarifa(self):
        TransporteTarifa.objects.create(
            empresa=self.transp, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            personas_min=1, personas_max=None, precio=Decimal('4500.00'),
        )
        paquete = self._paquete_cruza('c-cm', precio='4000.00', permite_anticipo=False)
        with self.assertRaises(ValidationError) as ctx:
            paquete.validar_configuracion()
        self.assertIn('tarifa de transporte', str(ctx.exception))

    def test_validar_configuracion_rechaza_anticipo_en_paquete_de_dos_empresas(self):
        paquete = self._paquete_cruza('d-cm', permite_anticipo=True)
        with self.assertRaises(ValidationError) as ctx:
            paquete.validar_configuracion()
        self.assertIn('anticipo', str(ctx.exception))

    def test_validar_configuracion_con_componentes_leidos_por_el_llamador_solo_valida_estructura(self):
        paquete = self._paquete_cruza('e-cm', permite_anticipo=True)
        from apps.fleet.models import componente_desde

        componentes = [
            componente_desde(self.s_pesca, noches=None, dia_estancia=1, personas_incluidas=2),
            componente_desde(self.s_transp, noches=None, dia_estancia=1, personas_incluidas=2),
        ]
        with self.assertRaises(ValidationError):
            paquete.validar_configuracion(componentes)

    def test_clean_del_modelo_no_lee_filas_viejas(self):
        # Activar el anticipo sobre un paquete de dos empresas NO falla en Paquete.clean:
        # lo atrapa el formset del admin (estado nuevo) y validar_configuracion (venta).
        paquete = self._paquete_cruza('f-cm', permite_anticipo=False)
        paquete.permite_anticipo = True
        paquete.full_clean()

    def _formset(self, paquete, filas):
        FormSet = inlineformset_factory(
            Paquete, PaqueteServicio, formset=PaqueteServicioFormSet,
            fields=['servicio', 'orden', 'dia_estancia', 'noches', 'personas_incluidas'], extra=0,
        )
        existentes = list(paquete.servicios_asociados.order_by('pk'))
        deseados = {servicio.pk for servicio in filas}
        existentes_ids = {ps.servicio_id for ps in existentes}
        nuevos = [servicio for servicio in filas if servicio.pk not in existentes_ids]
        datos = {
            'servicios_asociados-TOTAL_FORMS': str(len(existentes) + len(nuevos)),
            'servicios_asociados-INITIAL_FORMS': str(len(existentes)),
            'servicios_asociados-MIN_NUM_FORMS': '0', 'servicios_asociados-MAX_NUM_FORMS': '1000',
        }
        for i, ps in enumerate(existentes):
            datos.update({
                f'servicios_asociados-{i}-id': str(ps.pk),
                f'servicios_asociados-{i}-servicio': str(ps.servicio_id),
                f'servicios_asociados-{i}-orden': str(ps.orden),
                f'servicios_asociados-{i}-dia_estancia': str(ps.dia_estancia),
                f'servicios_asociados-{i}-personas_incluidas': str(ps.personas_incluidas),
            })
            if ps.noches is not None:
                datos[f'servicios_asociados-{i}-noches'] = str(ps.noches)
            if ps.servicio_id not in deseados:
                datos[f'servicios_asociados-{i}-DELETE'] = 'on'
        for i, servicio in enumerate(nuevos, start=len(existentes)):
            datos.update({
                f'servicios_asociados-{i}-servicio': str(servicio.pk),
                f'servicios_asociados-{i}-orden': str(i + 1),
                f'servicios_asociados-{i}-dia_estancia': '1',
                f'servicios_asociados-{i}-personas_incluidas': '2',
            })
        return FormSet(datos, instance=paquete)

    def test_formset_rechaza_anticipo_con_dos_empresas(self):
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre='g', slug='g-cm',
            precio_ancla=Decimal('9000.00'), permite_anticipo=True,
        )
        formset = self._formset(paquete, [self.s_pesca, self.s_transp])
        self.assertFalse(formset.is_valid())
        self.assertTrue(any('anticipo' in e for e in formset.non_form_errors()))

    def test_formset_acepta_quitar_el_traslado_y_dejar_anticipo_en_el_mismo_envio(self):
        paquete = self._paquete_cruza('h-cm', permite_anticipo=False)
        paquete.permite_anticipo = True  # el usuario lo activa en el mismo envío en que quita el traslado
        formset = self._formset(paquete, [self.s_pesca])
        self.assertTrue(formset.is_valid(), formset.non_form_errors())

    def test_formset_valida_el_precio_contra_la_peor_tarifa(self):
        TransporteTarifa.objects.create(
            empresa=self.transp, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            personas_min=1, personas_max=None, precio=Decimal('4500.00'),
        )
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre='i', slug='i-cm',
            precio_ancla=Decimal('4000.00'), permite_anticipo=False,
        )
        formset = self._formset(paquete, [self.s_pesca, self.s_transp])
        self.assertFalse(formset.is_valid())
        self.assertTrue(any('tarifa de transporte' in e for e in formset.non_form_errors()))
