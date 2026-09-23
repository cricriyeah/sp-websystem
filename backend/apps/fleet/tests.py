from datetime import date, time, timedelta
from decimal import Decimal
from io import StringIO

from unittest import skipUnless

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede
from apps.testing import crear_personalizacion_pesca, ApiTestCase, EmpresaTestCase, crear_servicio_pesca

from .enums import TipoTraslado
from .tarifa_transporte import TarifaTransporteNoConfigurada, resolver_tarifa_transporte
from .models import (
    CodigoPromocional,
    Embarcacion,
    EmbarcacionNoDisponible,
    Personalizacion,
    PuntoEncuentro,
    Servicio,
    ServicioPersonalizacion,
    TransporteTarifa,
    capacidades_disponibles,
    capacidades_por_fecha,
)

_CONTADOR_SEDES = iter(range(10_000))


def _crear_empresa(slug):
    n = next(_CONTADOR_SEDES)
    sede = Sede.objects.create(nombre=f'Sede de prueba {n}', slug=f'sede-{n}-{slug}')
    return Empresa.objects.create(sede=sede, nombre=f'Empresa {slug}', slug=slug, activo=True)


class EmpresaFKTests(TestCase):
    # El vínculo a Empresa es obligatorio desde F3.
    def test_embarcacionnodisponible_tiene_campo_empresa(self):
        campo = EmbarcacionNoDisponible._meta.get_field('empresa')
        self.assertFalse(campo.null)


class PescaServicioApiTests(ApiTestCase):
    def test_devuelve_los_cuatro_precios_y_personas_incluidas(self):
        crear_servicio_pesca(self.empresa, precio_base=Decimal('5100'),
                            precio_base_usd=Decimal('300'),
                            precio_persona_extra=Decimal('600'),
                            precio_persona_extra_usd=Decimal('35'))
        response = self.client.get(f'/api/{self.empresa.slug}/servicios/pesca-deportiva/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        for campo, valor in {'precio_base': '5100.00', 'precio_base_usd': '300.00',
                             'precio_persona_extra': '600.00',
                             'precio_persona_extra_usd': '35.00',
                             'personas_incluidas': 3}.items():
            self.assertEqual(body[campo], valor)
        self.assertNotIn('amenidades', body)

    def test_precio_usd_no_configurado_se_publica_como_null(self):
        crear_servicio_pesca(self.empresa, precio_base_usd=None,
                            precio_persona_extra_usd=None)
        body = self.client.get(f'/api/{self.empresa.slug}/servicios/pesca-deportiva/').json()
        self.assertIsNone(body['precio_base_usd'])
        self.assertIsNone(body['precio_persona_extra_usd'])

    def test_servicio_ausente_responde_404(self):
        self.assertEqual(self.client.get(
            f'/api/{self.empresa.slug}/servicios/pesca-deportiva/').status_code, 404)

    def test_empresa_inexistente_responde_404(self):
        self.assertEqual(self.client.get(
            '/api/no-existe/servicios/pesca-deportiva/').status_code, 404)

    def test_no_ve_precios_de_otra_empresa(self):
        crear_servicio_pesca(self.empresa, precio_base=Decimal('5100'))
        otra = _crear_empresa(slug='empresa-b')
        with self._alcance_otra(otra):
            crear_servicio_pesca(otra, precio_base=Decimal('9999'))
        body = self.client.get(f'/api/{self.empresa.slug}/servicios/pesca-deportiva/').json()
        self.assertEqual(body['precio_base'], '5100.00')

    def _alcance_otra(self, otra):
        # con_empresa no es reentrante con un valor distinto: se cierra el
        # alcance de self.empresa (abierto por EmpresaTestCase), se hace el
        # trabajo en el de `otra`, y se reabre el propio para el teardown.
        cm = _AlcanceOtraEmpresa(self, otra)
        return cm


@override_settings(DEBUG=True)
class SeedLocalDemoPescaTests(TestCase):
    def test_crea_pesca_con_precios_y_ventana_y_respeta_configuracion_existente(self):
        empresa = Empresa.objects.get(slug='sal-y-sol')
        with scope.con_empresa(empresa):
            Servicio.objects.filter(empresa=empresa, slug='pesca-deportiva').delete()
        call_command('seed_local_demo', stdout=StringIO())
        with scope.con_empresa(empresa):
            pesca = Servicio.objects.get(empresa=empresa, slug='pesca-deportiva')
            self.assertEqual((pesca.precio_base, pesca.precio_base_usd,
                              pesca.precio_persona_extra, pesca.precio_persona_extra_usd),
                             (Decimal('4500'), Decimal('260'), Decimal('500'), Decimal('30')))
            self.assertEqual((pesca.hora_apertura, pesca.hora_cierre), (time(5), time(7)))
            pesca.precio_base = Decimal('5100')
            pesca.precio_base_usd = None
            pesca.precio_persona_extra = Decimal('600')
            pesca.precio_persona_extra_usd = None
            pesca.hora_cierre = time(6, 30)
            pesca.save()
        empresa.stripe_secret_key = 'sk_test_personalizada'
        empresa.stripe_publishable_key = 'pk_test_personalizada'
        empresa.stripe_webhook_secret = 'whsec_personalizada'
        empresa.save()
        call_command('seed_local_demo', stdout=StringIO())
        with scope.con_empresa(empresa):
            pesca.refresh_from_db()
            self.assertEqual(Servicio.objects.filter(empresa=empresa, slug='pesca-deportiva').count(), 1)
            self.assertEqual((pesca.precio_base, pesca.precio_base_usd,
                              pesca.precio_persona_extra, pesca.precio_persona_extra_usd),
                             (Decimal('5100'), None, Decimal('600'), None))
            self.assertEqual(pesca.hora_cierre, time(6, 30))
        empresa.refresh_from_db()
        self.assertEqual((empresa.stripe_secret_key, empresa.stripe_publishable_key,
                          empresa.stripe_webhook_secret),
                         ('sk_test_personalizada', 'pk_test_personalizada', 'whsec_personalizada'))


class _AlcanceOtraEmpresa:
    def __init__(self, caso, otra):
        self.caso = caso
        self.otra = otra

    def __enter__(self):
        self.caso._alcance.__exit__(None, None, None)
        self._cm = scope.con_empresa(self.otra)
        self._cm.__enter__()
        return self

    def __exit__(self, *exc):
        self._cm.__exit__(*exc)
        self.caso._alcance = scope.con_empresa(self.caso.empresa)
        self.caso._alcance.__enter__()
        return False


class PersonalizacionesPescaTests(EmpresaTestCase):
    def test_precio_por_moneda(self):
        sp = crear_personalizacion_pesca(
            self.empresa, nombre='Licencia', tipo='licencia', precio=Decimal('450'), precio_usd=Decimal('25'))
        self.assertEqual(sp.precio_en('MXN'), Decimal('450'))
        self.assertEqual(sp.precio_en('USD'), Decimal('25'))

    def test_sin_precio_en_dolares_devuelve_none(self):
        sp = crear_personalizacion_pesca(self.empresa, nombre='Carnada', tipo='carnada', precio=Decimal('200'))
        self.assertIsNone(sp.precio_en('USD'))

    def test_cantidad_editable_sin_cobrar_por_persona_no_es_valido(self):
        p = Personalizacion(empresa=self.empresa, nombre='Carnada', tipo='carnada',
                            cobrar_por_persona=False, cantidad_editable=True)
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_cantidad_editable_con_cobrar_por_persona_es_valido(self):
        p = Personalizacion(empresa=self.empresa, nombre='Licencia', tipo='licencia',
                            cobrar_por_persona=True, cantidad_editable=True)
        p.full_clean()


class UnicidadPorEmpresaTests(TransactionTestCase):
    """Aislamiento A/B con TransactionTestCase (un IntegrityError deja
    inutilizable la transaccion de un TestCase). Alcance por Empresa a mano."""

    def setUp(self):
        self.empresa_a = _crear_empresa(slug='empresa-a')
        self.empresa_b = _crear_empresa(slug='empresa-b')

    def test_codigo_promocional_repetido_en_la_misma_empresa_falla(self):
        with scope.con_empresa(self.empresa_a):
            CodigoPromocional.objects.create(
                codigo='VERANO10', porcentaje_descuento=Decimal('10'), empresa=self.empresa_a,
            )
            with self.assertRaises(IntegrityError):
                CodigoPromocional.objects.create(
                    codigo='VERANO10', porcentaje_descuento=Decimal('15'), empresa=self.empresa_a,
                )

    def test_codigo_promocional_repetido_entre_empresas_es_valido(self):
        with scope.con_empresa(self.empresa_a):
            CodigoPromocional.objects.create(
                codigo='VERANO10', porcentaje_descuento=Decimal('10'), empresa=self.empresa_a,
            )
        with scope.con_empresa(self.empresa_b):
            CodigoPromocional.objects.create(
                codigo='VERANO10', porcentaje_descuento=Decimal('20'), empresa=self.empresa_b,
            )
        with scope.como_operador_plataforma():
            self.assertEqual(CodigoPromocional.objects.count(), 2)

    def test_nombre_de_embarcacion_repetido_en_la_misma_empresa_falla(self):
        with scope.con_empresa(self.empresa_a):
            Embarcacion.objects.create(
                nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
                empresa=self.empresa_a,
            )
            with self.assertRaises(IntegrityError):
                Embarcacion.objects.create(
                    nombre='Lupita', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
                    empresa=self.empresa_a,
                )

    def test_nombre_de_embarcacion_repetido_entre_empresas_es_valido(self):
        with scope.con_empresa(self.empresa_a):
            Embarcacion.objects.create(
                nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
                empresa=self.empresa_a,
            )
        with scope.con_empresa(self.empresa_b):
            Embarcacion.objects.create(
                nombre='Lupita', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
                empresa=self.empresa_b,
            )
        with scope.como_operador_plataforma():
            self.assertEqual(Embarcacion.objects.count(), 2)


class PersonalizacionesPescaApiTests(ApiTestCase):
    def catalogo(self):
        crear_servicio_pesca(self.empresa)
        return self.client.get(f'/api/{self.empresa.slug}/servicios/pesca-deportiva/').json()['personalizaciones']

    def test_precio_unitario_por_persona_y_flags(self):
        sp = crear_personalizacion_pesca(self.empresa, nombre='Licencia', tipo='licencia',
            precio=Decimal('450'), cobrar_por_persona=True, cantidad_editable=True, preseleccionado=True)
        item = self.catalogo()[0]
        self.assertEqual(item['id'], sp.pk)
        self.assertEqual(item['precio'], '450.00')
        self.assertTrue(item['cobrar_por_persona'])
        self.assertTrue(item['cantidad_editable'])
        self.assertTrue(item['preseleccionado'])

    def test_precio_plano(self):
        crear_personalizacion_pesca(self.empresa, nombre='Carnada', tipo='carnada',
                                  precio=Decimal('200'), cobrar_por_persona=False)
        item = self.catalogo()[0]
        self.assertEqual(item['precio'], '200.00')
        self.assertFalse(item['cobrar_por_persona'])

    def test_item_inactivo_no_aparece(self):
        crear_personalizacion_pesca(self.empresa, nombre='Carnada', tipo='carnada', activo=False)
        self.assertEqual(self.catalogo(), [])

    def test_sin_precio_usd_es_null(self):
        crear_personalizacion_pesca(self.empresa, nombre='Licencia', tipo='licencia', precio=Decimal('450'))
        self.assertIsNone(self.catalogo()[0]['precio_usd'])

    def test_catalogo_vacio(self):
        self.assertEqual(self.catalogo(), [])

    def test_endpoint_retirado(self):
        self.assertEqual(self.client.get(f'/api/{self.empresa.slug}/extras/').status_code, 404)

    def test_empresa_inexistente_responde_404(self):
        self.assertEqual(self.client.get('/api/no-existe/servicios/pesca-deportiva/').status_code, 404)

    def test_no_mezcla_catalogo_de_otra_empresa(self):
        otra = _crear_empresa(slug='empresa-b')
        with _AlcanceOtraEmpresa(self, otra):
            crear_personalizacion_pesca(otra, nombre='Carnada ajena', tipo='carnada', precio=Decimal('999'))
        self.assertEqual(self.catalogo(), [])


class EmbarcacionTests(EmpresaTestCase):
    def test_nace_activa(self):
        panga = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa,
        )
        self.assertTrue(panga.activa)

    def test_la_etiqueta_de_clase_no_carga_la_capacidad(self):
        for clase in Embarcacion.Clase:
            self.assertNotIn('personas', clase.label)

    def test_str_muestra_la_capacidad(self):
        panga = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa,
        )
        self.assertEqual(str(panga), 'Lupita (Grande, max. 5)')


class CapacidadesDisponiblesTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.fecha = date.today() + timedelta(days=10)
        self.chica = Embarcacion.objects.create(
            nombre='Chuy', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
            empresa=self.empresa,
        )
        self.grande = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa,
        )

    def test_devuelve_las_capacidades_de_mayor_a_menor(self):
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [5, 3])

    def test_excluye_las_inactivas(self):
        self.grande.activa = False
        self.grande.save()
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [3])

    def test_excluye_la_marcada_no_disponible_solo_ese_dia(self):
        EmbarcacionNoDisponible.objects.create(
            fecha=self.fecha, embarcacion=self.grande, motivo='Mantenimiento',
            empresa=self.empresa,
        )
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [3])
        self.assertEqual(
            capacidades_disponibles(self.fecha + timedelta(days=1), self.empresa), [5, 3],
        )

    def test_el_rango_no_hace_una_consulta_por_dia(self):
        with self.assertNumQueries(2):
            capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=89), self.empresa)

    def test_el_rango_trae_una_entrada_por_dia(self):
        rango = capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=2), self.empresa)
        self.assertEqual(len(rango), 3)
        self.assertEqual(rango[self.fecha], [5, 3])

    def test_pangas_de_otra_empresa_no_cuentan(self):
        otra_empresa = _crear_empresa(slug='empresa-b')
        with _AlcanceOtraEmpresa(self, otra_empresa):
            Embarcacion.objects.create(
                nombre='Otra panga', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=6,
                empresa=otra_empresa,
            )
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [5, 3])


class CodigoPromocionalTests(EmpresaTestCase):
    def test_normaliza_codigo_a_mayusculas_y_sin_espacios(self):
        promo = CodigoPromocional.objects.create(
            codigo=' verano10 ', porcentaje_descuento=Decimal('10'), empresa=self.empresa,
        )
        self.assertEqual(promo.codigo, 'VERANO10')

    def test_codigo_repetido_en_la_misma_empresa_no_se_puede_crear(self):
        CodigoPromocional.objects.create(
            codigo='VERANO10', porcentaje_descuento=Decimal('10'), empresa=self.empresa,
        )
        with self.assertRaises(IntegrityError):
            CodigoPromocional.objects.create(
                codigo='VERANO10', porcentaje_descuento=Decimal('15'), empresa=self.empresa,
            )

    def test_fecha_fin_debe_ser_posterior_a_fecha_inicio(self):
        ahora = timezone.now()
        promo = CodigoPromocional(
            codigo='X', porcentaje_descuento=Decimal('10'), empresa=self.empresa,
            fecha_inicio=ahora, fecha_fin=ahora - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            promo.full_clean()

    def test_monto_minimo_en_devuelve_el_de_la_moneda_pedida(self):
        promo = CodigoPromocional.objects.create(
            codigo='MIN', porcentaje_descuento=Decimal('10'), empresa=self.empresa,
            monto_minimo=Decimal('5000'), monto_minimo_usd=Decimal('300'),
        )
        self.assertEqual(promo.monto_minimo_en('MXN'), Decimal('5000'))
        self.assertEqual(promo.monto_minimo_en('USD'), Decimal('300'))

    def test_porcentaje_fuera_de_rango_no_es_valido(self):
        with self.assertRaises(ValidationError):
            CodigoPromocional(
                codigo='CERO', porcentaje_descuento=Decimal('0'), empresa=self.empresa,
            ).full_clean()
        with self.assertRaises(ValidationError):
            CodigoPromocional(
                codigo='MAS', porcentaje_descuento=Decimal('101'), empresa=self.empresa,
            ).full_clean()


class EmbarcacionNoDisponibleUnicidadTests(TransactionTestCase):
    """Aparte y con TransactionTestCase: un IntegrityError deja inutilizable la
    transaccion que envuelve a un TestCase normal. NO usa hilos (ver nota de
    verificacion de la Task F9 en el plan: la mencion de threading para esta
    clase especifica es incorrecta)."""

    def test_una_panga_no_se_puede_marcar_dos_veces_el_mismo_dia(self):
        empresa = _crear_empresa(slug='empresa-a')
        fecha = date.today() + timedelta(days=10)
        with scope.con_empresa(empresa):
            grande = Embarcacion.objects.create(
                nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
                empresa=empresa,
            )
            EmbarcacionNoDisponible.objects.create(fecha=fecha, embarcacion=grande, empresa=empresa)
            with self.assertRaises(IntegrityError):
                EmbarcacionNoDisponible.objects.create(
                    fecha=fecha, embarcacion=grande, empresa=empresa,
                )


class SeedExtrasTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_servicio_pesca(self.empresa)

    def test_reejecutar_preserva_precio_capturado_y_flags(self):
        call_command('seed_extras', empresa=self.empresa.slug, stdout=StringIO())
        sp = ServicioPersonalizacion.objects.get(personalizacion__nombre='Licencia de pesca')
        sp.precio = Decimal('777')
        sp.save(update_fields=['precio'])
        call_command('seed_extras', empresa=self.empresa.slug, stdout=StringIO())
        sp.refresh_from_db()
        self.assertEqual(sp.precio, Decimal('777'))
        self.assertTrue(sp.preseleccionado)
        self.assertTrue(sp.personalizacion.aviso_reforzado)
        self.assertTrue(sp.personalizacion.cantidad_editable)
        self.assertTrue(sp.personalizacion.cobrar_por_persona)

    def test_servicio_faltante_falla_sin_sembrar(self):
        Servicio.objects.filter(empresa=self.empresa).delete()
        with self.assertRaisesRegex(CommandError, 'Falta pesca-deportiva'):
            call_command('seed_extras', empresa=self.empresa.slug, stdout=StringIO())
        self.assertEqual(Personalizacion.objects.count(), 0)

    def test_siembra_el_catalogo_para_la_empresa_dada(self):
        call_command('seed_extras', empresa=self.empresa.slug, stdout=StringIO())
        self.assertEqual(Personalizacion.objects.filter(empresa=self.empresa).count(), 3)
        self.assertEqual(PuntoEncuentro.objects.filter(empresa=self.empresa).count(), 1)

    def test_es_idempotente(self):
        call_command('seed_extras', empresa=self.empresa.slug, stdout=StringIO())
        call_command('seed_extras', empresa=self.empresa.slug, stdout=StringIO())
        self.assertEqual(Personalizacion.objects.filter(empresa=self.empresa).count(), 3)

    def test_sin_empresa_falla_explicito(self):
        with self.assertRaises(Exception):
            call_command('seed_extras', stdout=StringIO())

    def test_empresa_inexistente_falla_explicito(self):
        with self.assertRaises(CommandError):
            call_command('seed_extras', empresa='no-existe', stdout=StringIO())


class TransporteTarifaTest(EmpresaTestCase):
    def test_redondo_actividad_sin_zona_falla_validacion(self):
        tarifa = TransporteTarifa(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            zona='',
            personas_min=1,
            personas_max=4,
            precio=Decimal('1500.00'),
        )
        with self.assertRaises(ValidationError):
            tarifa.full_clean()

    def test_recepcion_aeropuerto_con_zona_falla_validacion(self):
        tarifa = TransporteTarifa(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
            zona='centro',
            personas_min=1,
            personas_max=4,
            precio=Decimal('2700.00'),
        )
        with self.assertRaises(ValidationError):
            tarifa.full_clean()

    def test_personas_max_menor_que_personas_min_falla(self):
        tarifa = TransporteTarifa(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
            personas_min=5,
            personas_max=3,
            precio=Decimal('4500.00'),
        )
        with self.assertRaises(ValidationError):
            tarifa.full_clean()

    def test_precio_en_usd_con_precio_usd_none_devuelve_none(self):
        tarifa = TransporteTarifa(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
            personas_min=1,
            personas_max=4,
            precio=Decimal('4500.00'),
            precio_usd=None,
        )
        tarifa.full_clean()
        self.assertEqual(tarifa.precio_en('MXN'), Decimal('4500.00'))
        self.assertIsNone(tarifa.precio_en('USD'))


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class TransporteTarifaRLSTests(TransactionTestCase):
    def setUp(self):
        self.empresa_a = _crear_empresa(slug='rls-transporte-a')
        self.empresa_b = _crear_empresa(slug='rls-transporte-b')

    def test_aislamiento_de_transportetarifa_por_empresa(self):
        with scope.con_empresa(self.empresa_a):
            TransporteTarifa.objects.create(
                empresa=self.empresa_a,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                personas_min=1,
                personas_max=4,
                precio=Decimal('4500.00'),
            )
        with scope.con_empresa(self.empresa_b):
            TransporteTarifa.objects.create(
                empresa=self.empresa_b,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                personas_min=1,
                personas_max=4,
                precio=Decimal('5000.00'),
            )
            self.assertEqual(TransporteTarifa.objects.count(), 1)
            self.assertEqual(TransporteTarifa.objects.first().precio, Decimal('5000.00'))

        with scope.con_empresa(self.empresa_a):
            self.assertEqual(TransporteTarifa.objects.count(), 1)
            self.assertEqual(TransporteTarifa.objects.first().precio, Decimal('4500.00'))


class ResolverTarifaTransporteTest(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.tarifas = [
            # 1. Redondo aeropuerto 1-4 personas
            TransporteTarifa.objects.create(
                empresa=self.empresa,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                zona='',
                personas_min=1,
                personas_max=4,
                precio=Decimal('4500.00'),
            ),
            # 2. Redondo aeropuerto 5-14 personas
            TransporteTarifa.objects.create(
                empresa=self.empresa,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                zona='',
                personas_min=5,
                personas_max=14,
                precio=Decimal('6000.00'),
            ),
            # 3. Redondo actividad - centro
            TransporteTarifa.objects.create(
                empresa=self.empresa,
                tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
                zona='centro',
                personas_min=1,
                personas_max=None,
                precio=Decimal('1500.00'),
            ),
            # 4. Redondo actividad - periferia
            TransporteTarifa.objects.create(
                empresa=self.empresa,
                tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
                zona='periferia',
                personas_min=1,
                personas_max=None,
                precio=Decimal('1800.00'),
            ),
            # 5. Recepción aeropuerto
            TransporteTarifa.objects.create(
                empresa=self.empresa,
                tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
                zona='',
                personas_min=1,
                personas_max=None,
                precio=Decimal('2700.00'),
            ),
        ]

    def test_resuelve_redondo_aeropuerto_segun_personas(self):
        t4 = resolver_tarifa_transporte(
            self.tarifas, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona='', personas=4
        )
        self.assertEqual(t4.precio, Decimal('4500.00'))

        t5 = resolver_tarifa_transporte(
            self.tarifas, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona='', personas=5
        )
        self.assertEqual(t5.precio, Decimal('6000.00'))

        t14 = resolver_tarifa_transporte(
            self.tarifas, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona='', personas=14
        )
        self.assertEqual(t14.precio, Decimal('6000.00'))

    def test_resuelve_redondo_actividad_por_zona(self):
        tc = resolver_tarifa_transporte(
            self.tarifas, tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD, zona='centro', personas=2
        )
        self.assertEqual(tc.precio, Decimal('1500.00'))

        tp = resolver_tarifa_transporte(
            self.tarifas, tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD, zona='periferia', personas=2
        )
        self.assertEqual(tp.precio, Decimal('1800.00'))

    def test_resuelve_recepcion_aeropuerto_cualquier_tamano(self):
        t1 = resolver_tarifa_transporte(
            self.tarifas, tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO, zona='', personas=1
        )
        self.assertEqual(t1.precio, Decimal('2700.00'))

        t14 = resolver_tarifa_transporte(
            self.tarifas, tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO, zona='', personas=14
        )
        self.assertEqual(t14.precio, Decimal('2700.00'))

    def test_tipo_o_rango_sin_tarifa_lanza_excepcion(self):
        with self.assertRaises(TarifaTransporteNoConfigurada):
            resolver_tarifa_transporte(
                self.tarifas, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona='', personas=15
            )
        with self.assertRaises(TarifaTransporteNoConfigurada):
            resolver_tarifa_transporte(
                self.tarifas, tipo_traslado='tipo_inexistente', zona='', personas=2
            )


class TransporteTarifaAdminTest(EmpresaTestCase):
    def test_vendedora_recibe_403_en_changelist(self):
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)
        url = reverse('admin:fleet_transportetarifa_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_jefe_ve_sus_tarifas_y_no_las_de_otra_empresa(self):
        empresa_2 = _crear_empresa(slug='empresa-dos')
        t1 = TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            personas_min=1,
            personas_max=4,
            precio=Decimal('4500.00'),
        )
        with _AlcanceOtraEmpresa(self, empresa_2):
            t2 = TransporteTarifa.objects.create(
                empresa=empresa_2,
                tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                personas_min=1,
                personas_max=4,
                precio=Decimal('5000.00'),
            )

        jefe_1 = self.crear_jefe(username='jefe1')
        self.client.force_login(jefe_1)
        url = reverse('admin:fleet_transportetarifa_changelist')
        response_1 = self.client.get(url)
        self.assertEqual(response_1.status_code, 200)
        self.assertContains(response_1, '4500.00')
        self.assertNotContains(response_1, '5000.00')

        jefe_2 = User.objects.create_user('jefe2', is_staff=True, password='x')
        jefe_2.groups.add(Group.objects.get(name='Jefe'))
        MembresiaEmpresa.objects.create(user=jefe_2, empresa=empresa_2, rol=MembresiaEmpresa.Rol.JEFE)
        self.client.force_login(jefe_2)
        self._alcance.__exit__(None, None, None)
        try:
            response_2 = self.client.get(url)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.assertEqual(response_2.status_code, 200)
        self.assertContains(response_2, '5000.00')
        self.assertNotContains(response_2, '4500.00')





class TrasladosViewTest(TestCase):
    """Cada empresa abre su propio alcance; no hay un tenant ambiente."""

    def setUp(self):
        from .models import Servicio

        cache.clear()
        self.empresa_a = _crear_empresa('traslados-a')
        self.empresa_b = _crear_empresa('traslados-b')
        self.catalogos = {}
        for empresa in (self.empresa_a, self.empresa_b):
            empresa.stripe_secret_key = f'sk_test_{empresa.slug}'
            empresa.stripe_publishable_key = f'pk_test_{empresa.slug}'
            empresa.save()
            with scope.con_empresa(empresa):
                servicio = Servicio.objects.create(
                    empresa=empresa, nombre=f'Traslados {empresa.slug}', slug='traslado',
                    tipo_servicio='transporte', estrategia_cupo='bajo_demanda',
                    estrategia_precio='por_ruta', capacidad_maxima=14, permite_anticipo=False,
                )
                tarifa = TransporteTarifa.objects.create(
                    empresa=empresa, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
                    personas_min=1, personas_max=4, precio='4500.00',
                )
                punto = PuntoEncuentro.objects.create(empresa=empresa, nombre=empresa.slug, zona='centro')
                self.catalogos[empresa.pk] = (servicio, tarifa, punto)

    def catalogo(self, empresa):
        return self.client.get(f'/api/{empresa.slug}/traslados/')

    def test_empresa_dos_devuelve_catalogo_completo(self):
        servicio, tarifa, punto = self.catalogos[self.empresa_b.pk]
        respuesta = self.catalogo(self.empresa_b)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {
            'servicio': {'slug': servicio.slug, 'nombre': servicio.nombre,
                         'capacidad_maxima': 14, 'porcentaje_anticipo': 30,
                         'empresa_slug': self.empresa_b.slug, 'hora_apertura': None, 'hora_cierre': None},
            'tarifas': [{'tipo_traslado': tarifa.tipo_traslado, 'zona': '', 'personas_min': 1,
                         'personas_max': 4, 'precio': '4500.00', 'precio_usd': None}],
            'puntos_encuentro': [{'id': punto.pk, 'nombre': punto.nombre, 'zona': 'centro'}],
            'publishable_key': self.empresa_b.stripe_publishable_key,
        })

    def test_solo_tarifas_y_puntos_activos(self):
        with scope.con_empresa(self.empresa_b):
            TransporteTarifa.objects.create(
                empresa=self.empresa_b, tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
                precio='1800.00', activo=False,
            )
            PuntoEncuentro.objects.create(empresa=self.empresa_b, nombre='Cerrado', zona='centro', activo=False)
        respuesta = self.catalogo(self.empresa_b)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.json()['tarifas']), 1)
        self.assertEqual(len(respuesta.json()['puntos_encuentro']), 1)

    def test_sin_servicio_activo_responde_404(self):
        with scope.con_empresa(self.empresa_b):
            servicio = self.catalogos[self.empresa_b.pk][0]
            servicio.activo = False
            servicio.save()
        self.assertEqual(self.catalogo(self.empresa_b).status_code, 404)
        self.assertEqual(self.catalogo(_crear_empresa('sin-transporte')).status_code, 404)

    def test_empresa_inactiva_o_inexistente_responde_404(self):
        self.empresa_b.activo = False
        self.empresa_b.save()
        self.assertEqual(self.catalogo(self.empresa_b).status_code, 404)
        self.assertEqual(self.client.get('/api/desconocida/traslados/').status_code, 404)

    def test_stripe_sin_configurar_responde_503(self):
        for campo in ('stripe_secret_key', 'stripe_publishable_key'):
            with self.subTest(campo=campo):
                anterior = getattr(self.empresa_b, campo)
                setattr(self.empresa_b, campo, '')
                self.empresa_b.save()
                self.assertEqual(self.catalogo(self.empresa_b).status_code, 503)
                setattr(self.empresa_b, campo, anterior)
                self.empresa_b.save()

    @skipUnless(connection.vendor == 'postgresql', 'RLS requiere PostgreSQL')
    def test_rls_real_aisla_catalogos_y_cierra_alcance(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user')
            self.assertEqual(cursor.fetchone(), (False, False))
        for empresa in (self.empresa_b, self.empresa_a):
            with scope.con_empresa(empresa):
                self.assertEqual(set(TransporteTarifa.objects.values_list('empresa_id', flat=True)), {empresa.pk})
                self.assertEqual(set(PuntoEncuentro.objects.values_list('empresa_id', flat=True)), {empresa.pk})
            respuesta = self.catalogo(empresa)
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta.json()['puntos_encuentro'][0]['id'], self.catalogos[empresa.pk][2].pk)
            self.assertFalse(TransporteTarifa.objects.exists())
            self.assertFalse(PuntoEncuentro.objects.exists())


class PersonalizacionInteraccionTests(EmpresaTestCase):
    def test_input_no_puede_cobrar_por_persona(self):
        p = Personalizacion(empresa=self.empresa, nombre='Nombre pasajero',
                            tipo_interaccion='input_texto', cobrar_por_persona=True)
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_opciones_son_lista_no_vacia_de_strings_no_vacios(self):
        for opciones in ([], 'A', [1], ['  '], ['A', 'A']):
            with self.subTest(opciones=opciones):
                p = Personalizacion(empresa=self.empresa, nombre='Menú',
                    tipo_interaccion='input_seleccion', opciones_seleccion=opciones)
                with self.assertRaises(ValidationError):
                    p.full_clean()

    def test_input_gratis_y_check_opcional(self):
        s = Servicio.objects.create(empresa=self.empresa, nombre='Servicio', slug='s')
        p = Personalizacion.objects.create(empresa=self.empresa, nombre='Pregunta',
                                           tipo_interaccion='input_texto')
        sp = ServicioPersonalizacion(servicio=s, personalizacion=p, obligatorio=True,
                                     precio=Decimal('0.00'), precio_usd=None)
        sp.full_clean()
        sp.precio = Decimal('1.00')
        with self.assertRaises(ValidationError):
            sp.full_clean()

    def test_combinaciones_invalidas_personalizacion_y_servicio(self):
        # 1. check con obligatorio=True falla
        s = Servicio.objects.create(empresa=self.empresa, nombre='Servicio 2', slug='s2')
        p_check = Personalizacion.objects.create(empresa=self.empresa, nombre='Check',
                                                 tipo_interaccion='check')
        sp_check = ServicioPersonalizacion(servicio=s, personalizacion=p_check,
                                           obligatorio=True, preseleccionado=False)
        with self.assertRaises(ValidationError):
            sp_check.full_clean()

        # 2. input con preseleccionado=True falla
        p_input = Personalizacion.objects.create(empresa=self.empresa, nombre='Input',
                                                 tipo_interaccion='input_texto')
        sp_input = ServicioPersonalizacion(servicio=s, personalizacion=p_input,
                                           preseleccionado=True, precio=Decimal('0.00'))
        with self.assertRaises(ValidationError):
            sp_input.full_clean()

        # 3. cantidad_editable sin cobrar_por_persona falla
        p_edit = Personalizacion(empresa=self.empresa, nombre='Editable',
                                 tipo_interaccion='check', cantidad_editable=True,
                                 cobrar_por_persona=False)
        with self.assertRaises(ValidationError):
            p_edit.full_clean()

        # 4. input con aviso_reforzado falla
        p_reforzado = Personalizacion(empresa=self.empresa, nombre='Input Reforzado',
                                      tipo_interaccion='input_texto', aviso_reforzado=True)
        with self.assertRaises(ValidationError):
            p_reforzado.full_clean()

        # 5. opciones en texto (tipo no seleccion) falla
        p_opts_texto = Personalizacion(empresa=self.empresa, nombre='Texto con opciones',
                                       tipo_interaccion='input_texto',
                                       opciones_seleccion=['Opcion 1'])
        with self.assertRaises(ValidationError):
            p_opts_texto.full_clean()

        # 6. asociacion de otra Empresa con PKs reales bajo su propio alcance falla con mensaje específico
        otra_empresa = _crear_empresa('otra-empresa-test')
        # Salir temporalmente del alcance de self.empresa para entrar al de otra_empresa
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                p_otra = Personalizacion.objects.create(empresa=otra_empresa, nombre='Otra Empresa',
                                                       tipo_interaccion='check')
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        self.assertIsNotNone(p_otra.pk)
        self.assertIsNotNone(s.pk)
        sp_cruzada = ServicioPersonalizacion(servicio=s, personalizacion=p_otra)
        with self.assertRaises(ValidationError) as ctx:
            sp_cruzada.clean()
        self.assertIn('personalizacion', ctx.exception.message_dict)
        self.assertEqual(
            ctx.exception.message_dict['personalizacion'],
            ['La personalización debe pertenecer a la misma empresa que el servicio.']
        )

    def test_cambiar_catalogo_a_input_rechaza_si_asociaciones_tienen_precio_o_preseleccionado(self):
        s = Servicio.objects.create(empresa=self.empresa, nombre='Servicio Cat', slug='scat')
        p = Personalizacion.objects.create(empresa=self.empresa, nombre='Check con precio',
                                           tipo_interaccion='check')
        sp = ServicioPersonalizacion.objects.create(servicio=s, personalizacion=p,
                                                   precio=Decimal('150.00'),
                                                   preseleccionado=True)
        # Cambiar p a input_texto sin haber limpiado sp debe fallar en clean()
        p.tipo_interaccion = 'input_texto'
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn('tipo_interaccion', ctx.exception.message_dict)

    def test_cambiar_catalogo_a_input_permite_asociaciones_gratuitas_no_preseleccionadas(self):
        s1 = Servicio.objects.create(empresa=self.empresa, nombre='Servicio Cat 1', slug='scat1')
        s2 = Servicio.objects.create(empresa=self.empresa, nombre='Servicio Cat 2', slug='scat2')
        p = Personalizacion.objects.create(empresa=self.empresa, nombre='Check a Input Valido',
                                           tipo_interaccion='check')
        # Asociación 1: precio=0, precio_usd=None, preseleccionado=False
        ServicioPersonalizacion.objects.create(servicio=s1, personalizacion=p,
                                              precio=Decimal('0.00'), precio_usd=None,
                                              preseleccionado=False)
        # Asociación 2: precio=0, precio_usd=0, preseleccionado=False
        ServicioPersonalizacion.objects.create(servicio=s2, personalizacion=p,
                                              precio=Decimal('0.00'), precio_usd=Decimal('0.00'),
                                              preseleccionado=False)

        # Cambiar p a input_texto o input_numero o input_seleccion debe permitirse sin error
        for nuevo_tipo in ('input_texto', 'input_numero'):
            with self.subTest(tipo=nuevo_tipo):
                p.tipo_interaccion = nuevo_tipo
                p.full_clean()

        # Para input_seleccion requiere opciones
        p.tipo_interaccion = 'input_seleccion'
        p.opciones_seleccion = ['Opción A', 'Opción B']
        p.full_clean()

    def test_input_rechaza_precios_distintos_de_cero_incluyendo_negativos(self):
        s = Servicio.objects.create(empresa=self.empresa, nombre='Servicio Precios', slug='sprec')
        p = Personalizacion.objects.create(empresa=self.empresa, nombre='Input Pregunta',
                                           tipo_interaccion='input_texto')
        # precio_usd=None y precio=0 es válido
        sp = ServicioPersonalizacion(servicio=s, personalizacion=p,
                                     precio=Decimal('0.00'), precio_usd=None)
        sp.full_clean()

        # precio_usd=0 y precio=0 es válido
        sp.precio_usd = Decimal('0.00')
        sp.full_clean()

        # Valores distintos de cero (positivos y negativos) deben fallar
        precios_invalidos = [
            (Decimal('-10.00'), None),
            (Decimal('10.00'), None),
            (Decimal('0.00'), Decimal('-5.00')),
            (Decimal('0.00'), Decimal('5.00')),
            (Decimal('-1.00'), Decimal('-1.00')),
        ]
        for mxn, usd in precios_invalidos:
            with self.subTest(precio_mxn=mxn, precio_usd=usd):
                sp.precio = mxn
                sp.precio_usd = usd
                with self.assertRaises(ValidationError) as ctx:
                    sp.full_clean()
                self.assertIn('precio', ctx.exception.message_dict)

    def test_cambiar_catalogo_a_input_rechaza_asociaciones_con_precio_negativo(self):
        s = Servicio.objects.create(empresa=self.empresa, nombre='Servicio Negativo', slug='sneg')
        p = Personalizacion.objects.create(empresa=self.empresa, nombre='Check Negativo',
                                           tipo_interaccion='check')
        sp = ServicioPersonalizacion.objects.create(servicio=s, personalizacion=p,
                                                   precio=Decimal('-50.00'),
                                                   preseleccionado=False)
        p.tipo_interaccion = 'input_texto'
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn('tipo_interaccion', ctx.exception.message_dict)


class CrearServicioPescaHelperTests(EmpresaTestCase):
    def test_crear_servicio_pesca_defaults_y_no_duplica(self):
        from datetime import time
        from decimal import Decimal
        from apps.testing import crear_servicio_pesca

        s1 = crear_servicio_pesca(self.empresa)
        self.assertEqual(s1.slug, 'pesca-deportiva')
        self.assertEqual(s1.tipo_servicio, 'pesca')
        self.assertEqual(s1.estrategia_cupo, 'por_recurso_dia')
        self.assertEqual(s1.estrategia_precio, 'por_grupo')
        self.assertEqual(s1.modo_ocupacion, 'exclusivo')
        self.assertEqual(s1.precio_base, Decimal('4500'))
        self.assertEqual(s1.precio_base_usd, Decimal('260'))
        self.assertEqual(s1.precio_persona_extra, Decimal('500'))
        self.assertEqual(s1.precio_persona_extra_usd, Decimal('30'))
        self.assertEqual(s1.personas_incluidas, 3)
        self.assertEqual(s1.hora_apertura, time(5))
        self.assertEqual(s1.hora_cierre, time(7))
        self.assertTrue(s1.activo)

        # Llamarlo dos veces no duplica y devuelve la misma instancia
        s2 = crear_servicio_pesca(self.empresa)
        self.assertEqual(s1.pk, s2.pk)
        self.assertEqual(Servicio.objects.filter(empresa=self.empresa, slug='pesca-deportiva').count(), 1)

