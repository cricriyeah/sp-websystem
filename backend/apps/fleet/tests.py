from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.payments.pricing import PERSONAS_INCLUIDAS
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import ApiTestCase, EmpresaTestCase

from .enums import TipoTraslado
from .models import (
    CodigoPromocional,
    Embarcacion,
    EmbarcacionNoDisponible,
    ExtrasItem,
    PuntoEncuentro,
    Tarifa,
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
    # F1 dejo estos dos en null=True (paso transitorio); F3 los cerro a
    # obligatorios para los 8 modelos -- no queda un estado "nullable" real
    # en ningun punto del historial final.
    def test_tarifa_tiene_campo_empresa(self):
        campo = Tarifa._meta.get_field('empresa')
        self.assertFalse(campo.null)
        self.assertEqual(campo.remote_field.on_delete.__name__, 'PROTECT')

    def test_embarcacionnodisponible_tiene_campo_empresa(self):
        campo = EmbarcacionNoDisponible._meta.get_field('empresa')
        self.assertFalse(campo.null)

    def test_empresa_es_obligatoria_en_tarifa(self):
        campo = Tarifa._meta.get_field('empresa')
        self.assertFalse(campo.null)


class TarifaTests(TestCase):
    """Aislamiento A/B: abre el alcance de cada Empresa a mano (no puede haber
    un `con_empresa` ambiente porque hay dos Empresas distintas)."""

    def setUp(self):
        self.empresa_a = _crear_empresa(slug='empresa-a')
        self.empresa_b = _crear_empresa(slug='empresa-b')

    def test_una_tarifa_por_empresa(self):
        with scope.con_empresa(self.empresa_a):
            Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
            Tarifa.objects.create(precio=Decimal('5000.00'), empresa=self.empresa_a)
            self.assertEqual(Tarifa.objects.filter(empresa=self.empresa_a).count(), 1)
            self.assertEqual(Tarifa.de(self.empresa_a).precio, Decimal('5000.00'))

    def test_cada_empresa_tiene_su_propia_tarifa(self):
        with scope.con_empresa(self.empresa_a):
            Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
            self.assertEqual(Tarifa.de(self.empresa_a).precio, Decimal('4500.00'))
        with scope.con_empresa(self.empresa_b):
            Tarifa.objects.create(precio=Decimal('3000.00'), empresa=self.empresa_b)
            self.assertEqual(Tarifa.de(self.empresa_b).precio, Decimal('3000.00'))

    def test_sin_tarifa_de_devuelve_none(self):
        with scope.con_empresa(self.empresa_b):
            self.assertIsNone(Tarifa.de(self.empresa_b))

    def test_precio_por_moneda(self):
        with scope.con_empresa(self.empresa_a):
            tarifa = Tarifa.objects.create(
                precio=Decimal('4500.00'), precio_usd=Decimal('260.00'), empresa=self.empresa_a,
            )
        self.assertEqual(tarifa.precio_en('MXN'), Decimal('4500.00'))
        self.assertEqual(tarifa.precio_en('USD'), Decimal('260.00'))

    def test_sin_precio_en_dolares_devuelve_none(self):
        with scope.con_empresa(self.empresa_a):
            tarifa = Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
        self.assertIsNone(tarifa.precio_en('USD'))

    def test_carrera_creacion_simultanea_actualiza_no_revienta(self):
        from unittest.mock import patch
        with scope.con_empresa(self.empresa_a):
            Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
            t2 = Tarifa(precio=Decimal('6000.00'), empresa=self.empresa_a)
            # Simulamos que select_for_update no vio la fila existente (carrera de concurrencia)
            with patch.object(Tarifa.objects, 'select_for_update', return_value=Tarifa.objects.none()):
                t2.save()
            self.assertEqual(Tarifa.objects.filter(empresa=self.empresa_a).count(), 1)
            self.assertEqual(Tarifa.de(self.empresa_a).precio, Decimal('6000.00'))


class TarifaApiTests(ApiTestCase):
    def test_sin_tarifa_responde_503(self):
        self.assertEqual(
            self.client.get(f'/api/{self.empresa.slug}/tarifa/').status_code, 503,
        )

    def test_devuelve_todas_las_cifras_del_checkout(self):
        Tarifa.objects.create(
            precio=Decimal('4500.00'), precio_usd=Decimal('260.00'),
            precio_persona_extra=Decimal('500.00'), empresa=self.empresa,
        )
        body = self.client.get(f'/api/{self.empresa.slug}/tarifa/').json()
        self.assertEqual(body['precio'], '4500.00')
        self.assertEqual(body['precio_usd'], '260.00')
        self.assertEqual(body['precio_persona_extra'], '500.00')
        self.assertEqual(body['personas_incluidas'], PERSONAS_INCLUIDAS)

    def test_no_publica_precio_de_lo_que_se_cotiza(self):
        Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa)
        body = self.client.get(f'/api/{self.empresa.slug}/tarifa/').json()
        self.assertNotIn('amenidades', body)

    def test_empresa_inexistente_responde_404(self):
        self.assertEqual(self.client.get('/api/no-existe/tarifa/').status_code, 404)

    def test_no_ve_la_tarifa_de_otra_empresa(self):
        otra = _crear_empresa(slug='empresa-b')
        with self._alcance_otra(otra):
            Tarifa.objects.create(precio=Decimal('9999.00'), empresa=otra)
        self.assertEqual(
            self.client.get(f'/api/{self.empresa.slug}/tarifa/').status_code, 503,
        )

    def _alcance_otra(self, otra):
        # con_empresa no es reentrante con un valor distinto: se cierra el
        # alcance de self.empresa (abierto por EmpresaTestCase), se hace el
        # trabajo en el de `otra`, y se reabre el propio para el teardown.
        cm = _AlcanceOtraEmpresa(self, otra)
        return cm


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


class ExtrasItemTests(EmpresaTestCase):
    def test_precio_por_moneda(self):
        item = ExtrasItem.objects.create(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'), precio_usd=Decimal('25'),
            empresa=self.empresa,
        )
        self.assertEqual(item.precio_en('MXN'), Decimal('450'))
        self.assertEqual(item.precio_en('USD'), Decimal('25'))

    def test_sin_precio_en_dolares_devuelve_none(self):
        item = ExtrasItem.objects.create(
            tipo='carnada', nombre='Carnada', precio=Decimal('200'), empresa=self.empresa,
        )
        self.assertIsNone(item.precio_en('USD'))

    def test_cantidad_editable_sin_cobrar_por_persona_no_es_valido(self):
        item = ExtrasItem(
            tipo='carnada', nombre='Carnada', precio=Decimal('200'),
            cobrar_por_persona=False, cantidad_editable=True, empresa=self.empresa,
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_cantidad_editable_con_cobrar_por_persona_es_valido(self):
        item = ExtrasItem(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            cobrar_por_persona=True, cantidad_editable=True, empresa=self.empresa,
        )
        item.full_clean()


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


class ExtrasPublicosApiTests(ApiTestCase):
    def test_extra_por_persona_multiplica(self):
        ExtrasItem.objects.create(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            cobrar_por_persona=True, empresa=self.empresa,
        )
        body = self.client.get(f'/api/{self.empresa.slug}/extras/?personas=3').json()
        self.assertEqual(body['extras'][0]['monto'], '1350.00')

    def test_extra_plano_no_multiplica(self):
        ExtrasItem.objects.create(
            tipo='carnada', nombre='Carnada', precio=Decimal('200'),
            cobrar_por_persona=False, empresa=self.empresa,
        )
        body = self.client.get(f'/api/{self.empresa.slug}/extras/?personas=5').json()
        self.assertEqual(body['extras'][0]['monto'], '200.00')

    def test_item_inactivo_no_aparece(self):
        ExtrasItem.objects.create(
            tipo='carnada', nombre='Carnada', precio=Decimal('200'), activo=False,
            empresa=self.empresa,
        )
        body = self.client.get(f'/api/{self.empresa.slug}/extras/').json()
        self.assertEqual(body['extras'], [])

    def test_sin_precio_en_la_moneda_pedida_monto_es_null(self):
        ExtrasItem.objects.create(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'), empresa=self.empresa,
        )
        body = self.client.get(f'/api/{self.empresa.slug}/extras/?moneda=USD').json()
        self.assertIsNone(body['extras'][0]['monto'])

    def test_puntos_de_encuentro_activos(self):
        PuntoEncuentro.objects.create(nombre='Hotel CostaBaja', zona='centro', empresa=self.empresa)
        PuntoEncuentro.objects.create(
            nombre='Fuera de servicio', zona='centro', activo=False, empresa=self.empresa,
        )
        body = self.client.get(f'/api/{self.empresa.slug}/extras/').json()
        self.assertEqual([p['nombre'] for p in body['puntos_encuentro']], ['Hotel CostaBaja'])

    def test_moneda_invalida_es_400(self):
        self.assertEqual(
            self.client.get(f'/api/{self.empresa.slug}/extras/?moneda=EUR').status_code, 400,
        )

    def test_personas_invalida_es_400(self):
        self.assertEqual(
            self.client.get(f'/api/{self.empresa.slug}/extras/?personas=0').status_code, 400,
        )
        self.assertEqual(
            self.client.get(f'/api/{self.empresa.slug}/extras/?personas=abc').status_code, 400,
        )

    def test_defaults_sin_query_params(self):
        response = self.client.get(f'/api/{self.empresa.slug}/extras/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'extras': [], 'puntos_encuentro': []})

    def test_empresa_inexistente_responde_404(self):
        self.assertEqual(self.client.get('/api/no-existe/extras/').status_code, 404)

    def test_no_mezcla_catalogo_de_otra_empresa(self):
        otra = _crear_empresa(slug='empresa-b')
        with _AlcanceOtraEmpresa(self, otra):
            ExtrasItem.objects.create(
                tipo='carnada', nombre='Carnada de otra empresa', precio=Decimal('999'),
                empresa=otra,
            )
        body = self.client.get(f'/api/{self.empresa.slug}/extras/').json()
        self.assertEqual(body['extras'], [])


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
    def test_siembra_el_catalogo_para_la_empresa_dada(self):
        call_command('seed_extras', empresa=self.empresa.slug, stdout=StringIO())
        self.assertEqual(ExtrasItem.objects.filter(empresa=self.empresa).count(), 3)
        self.assertEqual(PuntoEncuentro.objects.filter(empresa=self.empresa).count(), 1)

    def test_es_idempotente(self):
        call_command('seed_extras', empresa=self.empresa.slug, stdout=StringIO())
        call_command('seed_extras', empresa=self.empresa.slug, stdout=StringIO())
        self.assertEqual(ExtrasItem.objects.filter(empresa=self.empresa).count(), 3)

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

