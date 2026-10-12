"""Pruebas unitarias para la funcion sugerir_precio de alta manual de reservas.

Compara cada resultado contra el calculo oficial de apps.payments (checkout web)
respetando el alcance de tenancy con EmpresaTestCase.
"""

from decimal import Decimal

from apps.bookings.models import Reserva
from apps.bookings.precio_sugerido import sugerir_precio
from apps.fleet.enums import (
    EstrategiaCupo,
    EstrategiaPrecio,
    TipoServicio,
    TipoTraslado,
    Zona,
)
from apps.fleet.models import (
    Paquete,
    PaqueteServicio,
    Servicio,
    TransporteTarifa,
)
from apps.payments.estrategias_precio import (
    DemandaPrecio,
    obtener_estrategia_precio,
)
from apps.tenancy import scope
from apps.tenancy.models import Empresa
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca


class SugerirPrecioTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.servicio_pesca = crear_servicio_pesca(
            self.empresa,
            precio_base=Decimal('4500.00'),
            precio_persona_extra=Decimal('500.00'),
            personas_incluidas=3,
        )

    # -------------------------------------------------------------------------
    # 1. Pesca por grupo (dentro y fuera de las personas incluidas)
    # -------------------------------------------------------------------------
    def test_pesca_por_grupo_dentro_de_personas_incluidas(self):
        """Para grupos <= personas_incluidas, el checkout cobra solo precio_base."""
        estrategia = obtener_estrategia_precio(self.servicio_pesca.estrategia_precio)

        for personas in (1, 2, 3):
            with self.subTest(personas=personas):
                demanda = DemandaPrecio(personas=personas, moneda='MXN')
                esperado = estrategia.calcular_base(self.servicio_pesca, demanda)
                sugerido = sugerir_precio(
                    servicio=self.servicio_pesca,
                    numero_personas=personas,
                    moneda='MXN',
                )
                self.assertEqual(sugerido, esperado)
                self.assertEqual(sugerido, Decimal('4500.00'))

    def test_pesca_por_grupo_fuera_de_personas_incluidas(self):
        """Para grupos > personas_incluidas, suma precio_persona_extra por cada adicional."""
        estrategia = obtener_estrategia_precio(self.servicio_pesca.estrategia_precio)

        for personas, esperado_manual in ((4, Decimal('5000.00')), (5, Decimal('5500.00'))):
            with self.subTest(personas=personas):
                demanda = DemandaPrecio(personas=personas, moneda='MXN')
                esperado = estrategia.calcular_base(self.servicio_pesca, demanda)
                sugerido = sugerir_precio(
                    servicio=self.servicio_pesca,
                    numero_personas=personas,
                    moneda='MXN',
                )
                self.assertEqual(sugerido, esperado)
                self.assertEqual(sugerido, esperado_manual)

    # -------------------------------------------------------------------------
    # 2. Precios en USD (derivados del tipo de cambio de la sede)
    # -------------------------------------------------------------------------
    def test_pesca_por_grupo_en_usd(self):
        """En USD cada monto se convierte hacia arriba al dolar entero segun la sede."""
        estrategia = obtener_estrategia_precio(self.servicio_pesca.estrategia_precio)
        tipo_cambio = self.empresa.sede.tipo_cambio_usd  # 18.0000

        for personas in (2, 5):
            with self.subTest(personas=personas):
                demanda = DemandaPrecio(
                    personas=personas,
                    moneda='USD',
                    tipo_cambio=tipo_cambio,
                )
                esperado = estrategia.calcular_base(self.servicio_pesca, demanda)
                sugerido = sugerir_precio(
                    servicio=self.servicio_pesca,
                    numero_personas=personas,
                    moneda='USD',
                )
                self.assertEqual(sugerido, esperado)
                self.assertIsInstance(sugerido, Decimal)

    # -------------------------------------------------------------------------
    # 3. Paquete de una sola empresa (por grupo y por persona)
    # -------------------------------------------------------------------------
    def test_paquete_una_empresa_por_grupo(self):
        """Paquete mono-empresa por grupo: cubre personas_precio_base mas extras."""
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Pesca Grupo',
            slug='paquete-pesca-grupo',
            precio_ancla=Decimal('7500.00'),
            estrategia_precio=EstrategiaPrecio.POR_GRUPO,
            personas_precio_base=3,
            precio_persona_extra=Decimal('500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio_pesca,
            orden=1,
            dia_estancia=1,
            personas_incluidas=3,
        )

        # En MXN dentro de personas base
        esperado_mxn_3 = paquete.precio_total_en('MXN', 3, None)
        sugerido_mxn_3 = sugerir_precio(paquete=paquete, numero_personas=3, moneda='MXN')
        self.assertEqual(sugerido_mxn_3, esperado_mxn_3)
        self.assertEqual(sugerido_mxn_3, Decimal('7500.00'))

        # En MXN con personas extra
        esperado_mxn_5 = paquete.precio_total_en('MXN', 5, None)
        sugerido_mxn_5 = sugerir_precio(paquete=paquete, numero_personas=5, moneda='MXN')
        self.assertEqual(sugerido_mxn_5, esperado_mxn_5)
        self.assertEqual(sugerido_mxn_5, Decimal('8500.00'))

        # En USD
        esperado_usd = paquete.precio_total_en('USD', 5, self.empresa.sede.tipo_cambio_usd)
        sugerido_usd = sugerir_precio(paquete=paquete, numero_personas=5, moneda='USD')
        self.assertEqual(sugerido_usd, esperado_usd)

    def test_paquete_una_empresa_por_persona(self):
        """Paquete mono-empresa por persona: precio ancla multiplicado por personas."""
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Pesca Por Persona',
            slug='paquete-pesca-por-persona',
            precio_ancla=Decimal('2000.00'),
            estrategia_precio=EstrategiaPrecio.POR_PERSONA,
            personas_precio_base=1,
            precio_persona_extra=Decimal('0.00'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete,
            servicio=self.servicio_pesca,
            orden=1,
            dia_estancia=1,
            personas_incluidas=4,
        )

        esperado_mxn = paquete.precio_total_en('MXN', 3, None)
        sugerido_mxn = sugerir_precio(paquete=paquete, numero_personas=3, moneda='MXN')
        self.assertEqual(sugerido_mxn, esperado_mxn)
        self.assertEqual(sugerido_mxn, Decimal('6000.00'))

        esperado_usd = paquete.precio_total_en('USD', 3, self.empresa.sede.tipo_cambio_usd)
        sugerido_usd = sugerir_precio(paquete=paquete, numero_personas=3, moneda='USD')
        self.assertEqual(sugerido_usd, esperado_usd)

    # -------------------------------------------------------------------------
    # 4. Traslados (con datos, sin datos, incompletos, fuera de tarifa)
    # -------------------------------------------------------------------------
    def test_traslado_con_datos_resuelve_tarifa_correcta(self):
        """Con detalle_transporte completo cotiza contra TransporteTarifa activa."""
        servicio_transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Servicio Traslados',
            slug='servicio-traslados',
            tipo_servicio=TipoServicio.TRANSPORTE,
            estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
            estrategia_precio=EstrategiaPrecio.POR_RUTA,
            activo=True,
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
            personas_min=1,
            personas_max=4,
            precio=Decimal('4500.00'),
            activo=True,
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
            personas_min=5,
            personas_max=14,
            precio=Decimal('6000.00'),
            activo=True,
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            zona=Zona.CENTRO,
            personas_min=1,
            personas_max=4,
            precio=Decimal('1500.00'),
            activo=True,
        )

        tarifas = list(self.empresa.tarifas_transporte.filter(activo=True))
        estrategia_ruta = obtener_estrategia_precio(EstrategiaPrecio.POR_RUTA)

        # Redondo aeropuerto para 3 personas en MXN
        detalle_aeropuerto = {
            'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
            'zona': '',
            'numero_personas': 3,
        }
        demanda = DemandaPrecio(
            personas=3,
            moneda='MXN',
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
        )
        esperado = estrategia_ruta.calcular_base({'tarifas_transporte_activas': tarifas}, demanda)
        sugerido = sugerir_precio(
            servicio=servicio_transporte,
            numero_personas=3,
            moneda='MXN',
            detalle_transporte=detalle_aeropuerto,
        )
        self.assertEqual(sugerido, esperado)
        self.assertEqual(sugerido, Decimal('4500.00'))

        # Redondo aeropuerto para 6 personas (salto de escalon tarifario)
        detalle_aeropuerto_6 = {
            'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
            'zona': '',
            'numero_personas': 6,
        }
        demanda_6 = DemandaPrecio(
            personas=6,
            moneda='MXN',
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
        )
        esperado_6 = estrategia_ruta.calcular_base({'tarifas_transporte_activas': tarifas}, demanda_6)
        sugerido_6 = sugerir_precio(
            servicio=servicio_transporte,
            numero_personas=6,
            moneda='MXN',
            detalle_transporte=detalle_aeropuerto_6,
        )
        self.assertEqual(sugerido_6, esperado_6)
        self.assertEqual(sugerido_6, Decimal('6000.00'))

        # Redondo actividad con zona centro
        detalle_actividad = {
            'tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
            'zona': Zona.CENTRO,
            'numero_personas': 2,
        }
        demanda_act = DemandaPrecio(
            personas=2,
            moneda='MXN',
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            zona=Zona.CENTRO,
        )
        esperado_act = estrategia_ruta.calcular_base({'tarifas_transporte_activas': tarifas}, demanda_act)
        sugerido_act = sugerir_precio(
            servicio=servicio_transporte,
            numero_personas=2,
            moneda='MXN',
            detalle_transporte=detalle_actividad,
        )
        self.assertEqual(sugerido_act, esperado_act)
        self.assertEqual(sugerido_act, Decimal('1500.00'))

        # En USD
        demanda_usd = DemandaPrecio(
            personas=3,
            moneda='USD',
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
            tipo_cambio=self.empresa.sede.tipo_cambio_usd,
        )
        esperado_usd = estrategia_ruta.calcular_base({'tarifas_transporte_activas': tarifas}, demanda_usd)
        sugerido_usd = sugerir_precio(
            servicio=servicio_transporte,
            numero_personas=3,
            moneda='USD',
            detalle_transporte=detalle_aeropuerto,
        )
        self.assertEqual(sugerido_usd, esperado_usd)

    def test_traslado_sin_datos_o_incompletos_devuelve_none(self):
        """Un traslado sin detalle o con datos incompletos no se puede cotizar."""
        servicio_transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Incompleto',
            slug='traslado-incompleto',
            tipo_servicio=TipoServicio.TRANSPORTE,
            estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
            estrategia_precio=EstrategiaPrecio.POR_RUTA,
            activo=True,
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            personas_min=1,
            personas_max=4,
            precio=Decimal('4500.00'),
            activo=True,
        )

        # Sin detalle_transporte
        self.assertIsNone(
            sugerir_precio(servicio=servicio_transporte, numero_personas=3, moneda='MXN', detalle_transporte=None)
        )

        # Con dict vacio o sin tipo_traslado
        self.assertIsNone(
            sugerir_precio(servicio=servicio_transporte, numero_personas=3, moneda='MXN', detalle_transporte={})
        )
        self.assertIsNone(
            sugerir_precio(
                servicio=servicio_transporte,
                numero_personas=3,
                moneda='MXN',
                detalle_transporte={'tipo_traslado': ''},
            )
        )

        # Redondo actividad sin zona (zona requerida)
        self.assertIsNone(
            sugerir_precio(
                servicio=servicio_transporte,
                numero_personas=2,
                moneda='MXN',
                detalle_transporte={'tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD, 'zona': ''},
            )
        )

        # Personas fuera del rango de tarifas (e.g. 25 personas cuando el maximo es 4)
        self.assertIsNone(
            sugerir_precio(
                servicio=servicio_transporte,
                numero_personas=25,
                moneda='MXN',
                detalle_transporte={'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO, 'zona': '', 'numero_personas': 25},
            )
        )

    # -------------------------------------------------------------------------
    # 5. Paquete cruza-empresa → None
    # -------------------------------------------------------------------------
    def test_paquete_cruza_empresa_devuelve_none(self):
        """Un paquete con servicios de dos empresas se vende como Orden, no como Reserva."""
        otra_empresa = Empresa.objects.create(
            sede=self.sede,
            nombre='Empresa Segunda',
            slug='empresa-segunda',
            activo=True,
        )
        # Salir temporalmente del alcance de self.empresa para sembrar en otra_empresa
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                servicio_otra = Servicio.objects.create(
                    empresa=otra_empresa,
                    nombre='Hospedaje Asociado',
                    slug='hospedaje-asociado',
                    tipo_servicio=TipoServicio.HOSPEDAJE,
                    estrategia_cupo=EstrategiaCupo.POR_NOCHE,
                    estrategia_precio=EstrategiaPrecio.POR_NOCHE,
                    precio_base=Decimal('2500.00'),
                    activo=True,
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        paquete_cruza = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Combinado',
            slug='paquete-combinado',
            precio_ancla=Decimal('10000.00'),
            estrategia_precio=EstrategiaPrecio.POR_GRUPO,
            personas_precio_base=2,
            precio_persona_extra=Decimal('500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete_cruza,
            servicio=self.servicio_pesca,
            orden=1,
            dia_estancia=1,
            personas_incluidas=2,
        )
        PaqueteServicio.objects.create(
            paquete=paquete_cruza,
            servicio=servicio_otra,
            orden=2,
            dia_estancia=1,
            noches=2,
            personas_incluidas=2,
        )

        self.assertTrue(paquete_cruza.es_cruza_empresa)
        self.assertIsNone(sugerir_precio(paquete=paquete_cruza, numero_personas=2, moneda='MXN'))

    # -------------------------------------------------------------------------
    # 6. Personas invalidas (< 1 o no enteras) → None
    # -------------------------------------------------------------------------
    def test_personas_invalidas_devuelve_none(self):
        """numero_personas menor a 1, nulo o no entero debe devolver None sin excepcion."""
        self.assertIsNone(sugerir_precio(servicio=self.servicio_pesca, numero_personas=0, moneda='MXN'))
        self.assertIsNone(sugerir_precio(servicio=self.servicio_pesca, numero_personas=-1, moneda='MXN'))
        self.assertIsNone(sugerir_precio(servicio=self.servicio_pesca, numero_personas=None, moneda='MXN'))
        self.assertIsNone(sugerir_precio(servicio=self.servicio_pesca, numero_personas='invalido', moneda='MXN'))
        self.assertIsNone(sugerir_precio(servicio=self.servicio_pesca, numero_personas=False, moneda='MXN'))
        self.assertIsNone(sugerir_precio(servicio=self.servicio_pesca, numero_personas=True, moneda='MXN'))

    # -------------------------------------------------------------------------
    # 7. Servicio sin precio USD → None
    # -------------------------------------------------------------------------
    def test_servicio_sin_precio_usd_devuelve_none(self):
        """Si la sede no tiene tipo de cambio o es invalido, sugerir en USD devuelve None."""
        self.sede.tipo_cambio_usd = Decimal('0.0000')
        self.sede.save()

        # Al no haber tipo de cambio valido, no se puede calcular en USD
        self.assertIsNone(
            sugerir_precio(servicio=self.servicio_pesca, numero_personas=2, moneda='USD')
        )

    # -------------------------------------------------------------------------
    # 8. Otros servicios con su estrategia (tarifa_fija y por_persona)
    # -------------------------------------------------------------------------
    def test_otros_servicios_con_estrategia_fija_y_por_persona(self):
        """Verifica que servicios con tarifa_fija y por_persona se calculen segun su estrategia."""
        servicio_fijo = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Entrada Parque',
            slug='entrada-parque',
            tipo_servicio=TipoServicio.PASEO,
            estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
            estrategia_precio=EstrategiaPrecio.TARIFA_FIJA,
            precio_base=Decimal('800.00'),
            activo=True,
        )
        demanda_fija = DemandaPrecio(personas=4, moneda='MXN')
        esperado_fijo = obtener_estrategia_precio(EstrategiaPrecio.TARIFA_FIJA).calcular_base(
            servicio_fijo, demanda_fija
        )
        sugerido_fijo = sugerir_precio(servicio=servicio_fijo, numero_personas=4, moneda='MXN')
        self.assertEqual(sugerido_fijo, esperado_fijo)
        self.assertEqual(sugerido_fijo, Decimal('800.00'))

        servicio_persona = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Paseo Guiado',
            slug='paseo-guiado',
            tipo_servicio=TipoServicio.PASEO,
            estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
            estrategia_precio=EstrategiaPrecio.POR_PERSONA,
            precio_base=Decimal('650.00'),
            activo=True,
        )
        demanda_persona = DemandaPrecio(personas=3, moneda='MXN')
        esperado_persona = obtener_estrategia_precio(EstrategiaPrecio.POR_PERSONA).calcular_base(
            servicio_persona, demanda_persona
        )
        sugerido_persona = sugerir_precio(servicio=servicio_persona, numero_personas=3, moneda='MXN')
        self.assertEqual(sugerido_persona, esperado_persona)
        self.assertEqual(sugerido_persona, Decimal('1950.00'))

    # -------------------------------------------------------------------------
    # 9. Servicio bajo demanda sin tarifa → None
    # -------------------------------------------------------------------------
    def test_servicio_bajo_demanda_sin_tarifa_devuelve_none(self):
        """Un servicio sin precio base configurado (0.00 o None) debe devolver None."""
        servicio_sin_precio = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Servicio Sin Precio',
            slug='servicio-sin-precio',
            tipo_servicio=TipoServicio.BAJO_DEMANDA,
            estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
            estrategia_precio=EstrategiaPrecio.POR_GRUPO,
            precio_base=Decimal('0.00'),
            activo=True,
        )
        self.assertIsNone(
            sugerir_precio(servicio=servicio_sin_precio, numero_personas=2, moneda='MXN')
        )

    # -------------------------------------------------------------------------
    # 10. Casos borde de contrato
    # -------------------------------------------------------------------------
    def test_casos_borde_contrato(self):
        """Verifica exclusion mutua, monedas no soportadas y parametros invalidos."""
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Simple',
            slug='paquete-simple',
            precio_ancla=Decimal('5000.00'),
            estrategia_precio=EstrategiaPrecio.POR_GRUPO,
        )

        # Ambos especificados
        self.assertIsNone(
            sugerir_precio(
                servicio=self.servicio_pesca,
                paquete=paquete,
                numero_personas=2,
                moneda='MXN',
            )
        )

        # Ninguno especificado
        self.assertIsNone(sugerir_precio(numero_personas=2, moneda='MXN'))

        # Moneda no valida
        self.assertIsNone(
            sugerir_precio(servicio=self.servicio_pesca, numero_personas=2, moneda='EUR')
        )
        self.assertIsNone(
            sugerir_precio(servicio=self.servicio_pesca, numero_personas=2, moneda='')
        )
        self.assertIsNone(
            sugerir_precio(servicio=self.servicio_pesca, numero_personas=2, moneda=None)
        )
