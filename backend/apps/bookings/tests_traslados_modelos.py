"""Pruebas de los modelos Vehiculo, VehiculoNoDisponible y ViajeTransporte.

Cubre: capacidad, bloqueos de dia completo y de rango, viaje sin hora, vehiculo de
otra empresa, vehiculo inactivo, viaje cancelado, unicidad, horas del bloqueo
incoherentes, y la validacion inversa de VehiculoNoDisponible.
"""
from datetime import date, time, timedelta

from django.core.exceptions import ValidationError

from apps.fleet.enums import EstrategiaCupo, EstrategiaPrecio, TipoServicio, TipoTraslado, Zona
from apps.fleet.models import PuntoEncuentro, Servicio, Vehiculo, VehiculoNoDisponible
from apps.tenancy.models import Empresa, Sede
from apps.tenancy import scope
from apps.testing import EmpresaTestCase

from .models import DetalleTransporte, Reserva, ViajeTransporte


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HOY = date.today()
MANANA = HOY + timedelta(days=1)


def _crear_servicio_transporte(empresa):
    return Servicio.objects.create(
        empresa=empresa,
        nombre='Traslado DLS',
        slug='traslado-dls',
        tipo_servicio=TipoServicio.TRANSPORTE,
        estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
        estrategia_precio=EstrategiaPrecio.POR_RUTA,
        pide_hora=False,
        activo=True,
    )


def _crear_reserva_transporte(empresa, servicio, numero_personas=2):
    """Reserva de transporte en estado PAGADA con su DetalleTransporte."""
    pe = PuntoEncuentro.objects.create(empresa=empresa, nombre='Hotel Mar', zona=Zona.CENTRO, activo=True)
    reserva = Reserva.objects.create(
        empresa=empresa,
        servicio=servicio,
        nombre_cliente='Ana Garcia',
        telefono_cliente='612 111 2222',
        correo_cliente='ana@example.com',
        canal_origen=Reserva.CanalOrigen.WHATSAPP,
        fecha=MANANA,
        numero_personas=numero_personas,
        estado=Reserva.Estado.PAGADA,
    )
    DetalleTransporte.objects.create(
        reserva=reserva,
        tipo_traslado=TipoTraslado.RECEPCION_AEROPUERTO,
        punto_encuentro=pe,
        zona=Zona.CENTRO,
    )
    # El gancho de sincronizacion (tarea 2) ya crea los viajes al pagar; estas pruebas
    # siembran los suyos a mano para controlar fecha, hora y vehiculo.
    ViajeTransporte.objects.filter(reserva=reserva).delete()
    return reserva


def _viaje(empresa, reserva, vehiculo=None, sentido='unico', fecha=None, hora=None, cancelado=False):
    """Crea un ViajeTransporte sin pasar por clean() para sembrar datos de prueba."""
    return ViajeTransporte.objects.create(
        empresa=empresa,
        reserva=reserva,
        sentido=sentido,
        fecha=fecha or MANANA,
        hora=hora,
        vehiculo=vehiculo,
        cancelado=cancelado,
    )


# ---------------------------------------------------------------------------
# Tests de Vehiculo
# ---------------------------------------------------------------------------

class VehiculoTests(EmpresaTestCase):

    def setUp(self):
        super().setUp()
        self.vehiculo = Vehiculo.objects.create(empresa=self.empresa, nombre='Van Blanca', lugares=6)

    def test_str(self):
        self.assertIn('Van Blanca', str(self.vehiculo))
        self.assertIn('6', str(self.vehiculo))

    def test_lugares_minimo_uno(self):
        """El validador de MinValueValidator(1) rechaza cero lugares."""
        v = Vehiculo(empresa=self.empresa, nombre='Moto', lugares=0)
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_nombre_unico_por_empresa(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Vehiculo.objects.create(empresa=self.empresa, nombre='Van Blanca', lugares=8)


# ---------------------------------------------------------------------------
# Tests de VehiculoNoDisponible
# ---------------------------------------------------------------------------

class VehiculoNoDisponibleTests(EmpresaTestCase):

    def setUp(self):
        super().setUp()
        self.vehiculo = Vehiculo.objects.create(empresa=self.empresa, nombre='Sedan Azul', lugares=4)
        self.servicio = _crear_servicio_transporte(self.empresa)
        self.reserva = _crear_reserva_transporte(self.empresa, self.servicio, numero_personas=2)

    def _bloqueo(self, **kwargs):
        b = VehiculoNoDisponible(
            empresa=self.empresa,
            vehiculo=self.vehiculo,
            fecha=MANANA,
            **kwargs,
        )
        b.full_clean()
        return b

    # -- Validacion de horas --

    def test_bloqueo_dia_completo_valido(self):
        """Sin horas es bloqueo de dia completo: no falla."""
        self._bloqueo()  # no lanza

    def test_bloqueo_con_rango_valido(self):
        self._bloqueo(hora_desde=time(8, 0), hora_hasta=time(12, 0))

    def test_bloqueo_solo_hora_desde_rechazado(self):
        with self.assertRaises(ValidationError):
            self._bloqueo(hora_desde=time(8, 0))

    def test_bloqueo_solo_hora_hasta_rechazado(self):
        with self.assertRaises(ValidationError):
            self._bloqueo(hora_hasta=time(12, 0))

    def test_horas_invertidas_rechazado(self):
        with self.assertRaises(ValidationError):
            self._bloqueo(hora_desde=time(14, 0), hora_hasta=time(8, 0))

    def test_horas_iguales_rechazado(self):
        with self.assertRaises(ValidationError):
            self._bloqueo(hora_desde=time(10, 0), hora_hasta=time(10, 0))

    # -- Validacion de empresa --

    def test_vehiculo_de_otra_empresa_rechazado(self):
        otra_sede = Sede.objects.create(nombre='Otra', slug='otra-t', zona_horaria='America/Mazatlan', activo=True)
        otra_empresa = Empresa.objects.create(sede=otra_sede, nombre='Otra Emp', slug='otra-t-e', activo=True)
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                vehiculo_ajeno = Vehiculo.objects.create(empresa=otra_empresa, nombre='Camioneta', lugares=8)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        b = VehiculoNoDisponible(empresa=self.empresa, vehiculo=vehiculo_ajeno, fecha=MANANA)
        with self.assertRaises(ValidationError) as cm:
            b.full_clean()
        self.assertIn('vehiculo', cm.exception.message_dict)

    # -- Validacion inversa: no se puede bloquear si hay viajes asignados --

    def test_no_bloquea_dia_completo_con_viaje_asignado(self):
        """Dia completo choca con cualquier viaje del dia."""
        _viaje(self.empresa, self.reserva, vehiculo=self.vehiculo, fecha=MANANA)
        with self.assertRaises(ValidationError):
            self._bloqueo()

    def test_no_bloquea_rango_con_viaje_con_hora_dentro(self):
        """Rango de 8 a 12: un viaje a las 10 choca."""
        _viaje(self.empresa, self.reserva, vehiculo=self.vehiculo, fecha=MANANA, hora=time(10, 0))
        with self.assertRaises(ValidationError):
            self._bloqueo(hora_desde=time(8, 0), hora_hasta=time(12, 0))

    def test_rango_no_choca_con_viaje_con_hora_fuera(self):
        """Rango de 8 a 12: un viaje a las 14 NO choca."""
        _viaje(self.empresa, self.reserva, vehiculo=self.vehiculo, fecha=MANANA, hora=time(14, 0))
        self._bloqueo(hora_desde=time(8, 0), hora_hasta=time(12, 0))  # no lanza

    def test_rango_no_choca_con_viaje_sin_hora(self):
        """Rango de horas: un viaje sin hora no choca con el rango (spec §4)."""
        _viaje(self.empresa, self.reserva, vehiculo=self.vehiculo, fecha=MANANA, hora=None)
        self._bloqueo(hora_desde=time(8, 0), hora_hasta=time(12, 0))  # no lanza

    def test_dia_completo_choca_con_viaje_sin_hora(self):
        """Dia completo si choca con un viaje sin hora."""
        _viaje(self.empresa, self.reserva, vehiculo=self.vehiculo, fecha=MANANA, hora=None)
        with self.assertRaises(ValidationError):
            self._bloqueo()

    def test_viaje_cancelado_no_impide_bloqueo(self):
        """Un viaje cancelado no bloquea el vehiculo: la asignacion se limpio."""
        _viaje(self.empresa, self.reserva, vehiculo=self.vehiculo, fecha=MANANA, cancelado=True)
        self._bloqueo()  # no lanza

    def test_viaje_de_otro_dia_no_impide_bloqueo(self):
        """Un viaje en otra fecha no tiene nada que ver."""
        otro_dia = MANANA + timedelta(days=1)
        _viaje(self.empresa, self.reserva, vehiculo=self.vehiculo, fecha=otro_dia)
        self._bloqueo()  # MANANA, no lanza


# ---------------------------------------------------------------------------
# Tests de ViajeTransporte
# ---------------------------------------------------------------------------

class ViajeTransporteTests(EmpresaTestCase):

    def setUp(self):
        super().setUp()
        self.vehiculo = Vehiculo.objects.create(empresa=self.empresa, nombre='Minivan', lugares=5)
        self.servicio = _crear_servicio_transporte(self.empresa)
        self.reserva = _crear_reserva_transporte(self.empresa, self.servicio, numero_personas=3)

    def _viaje_limpio(self, **kwargs):
        """ViajeTransporte que pasa por full_clean."""
        v = ViajeTransporte(
            empresa=self.empresa,
            reserva=self.reserva,
            sentido=ViajeTransporte.Sentido.UNICO,
            fecha=MANANA,
            **kwargs,
        )
        v.full_clean()
        return v

    # -- Capacidad --

    def test_grupo_cabe_en_vehiculo(self):
        """3 personas en una van de 5: valid."""
        self._viaje_limpio(vehiculo=self.vehiculo)  # no lanza

    def test_grupo_no_cabe_en_vehiculo(self):
        """6 personas en una van de 5: no cabe."""
        reserva_grande = _crear_reserva_transporte(self.empresa, self.servicio, numero_personas=6)
        v = ViajeTransporte(
            empresa=self.empresa, reserva=reserva_grande,
            sentido=ViajeTransporte.Sentido.UNICO, fecha=MANANA,
            vehiculo=self.vehiculo,
        )
        with self.assertRaises(ValidationError) as cm:
            v.full_clean()
        self.assertIn('vehiculo', cm.exception.message_dict)

    # -- Vehiculo de otra empresa --

    def test_vehiculo_de_otra_empresa_rechazado(self):
        otra_sede = Sede.objects.create(nombre='Otra S', slug='otra-s2', zona_horaria='America/Mazatlan', activo=True)
        otra_empresa = Empresa.objects.create(sede=otra_sede, nombre='Otra E', slug='otra-e2', activo=True)
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                vehiculo_ajeno = Vehiculo.objects.create(empresa=otra_empresa, nombre='Auto', lugares=4)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        with self.assertRaises(ValidationError) as cm:
            self._viaje_limpio(vehiculo=vehiculo_ajeno)
        self.assertIn('vehiculo', cm.exception.message_dict)

    # -- Vehiculo inactivo --

    def test_vehiculo_inactivo_rechazado(self):
        self.vehiculo.activo = False
        self.vehiculo.save()
        with self.assertRaises(ValidationError) as cm:
            self._viaje_limpio(vehiculo=self.vehiculo)
        self.assertIn('vehiculo', cm.exception.message_dict)

    # -- Bloqueo de dia completo --

    def test_vehiculo_bloqueado_dia_completo(self):
        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=self.vehiculo, fecha=MANANA,
        )
        with self.assertRaises(ValidationError) as cm:
            self._viaje_limpio(vehiculo=self.vehiculo)
        self.assertIn('vehiculo', cm.exception.message_dict)

    # -- Bloqueo de rango con viaje con hora --

    def test_viaje_con_hora_dentro_del_rango_rechazado(self):
        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=self.vehiculo, fecha=MANANA,
            hora_desde=time(8, 0), hora_hasta=time(12, 0),
        )
        with self.assertRaises(ValidationError) as cm:
            self._viaje_limpio(vehiculo=self.vehiculo, hora=time(10, 0))
        self.assertIn('vehiculo', cm.exception.message_dict)

    def test_viaje_con_hora_fuera_del_rango_valido(self):
        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=self.vehiculo, fecha=MANANA,
            hora_desde=time(8, 0), hora_hasta=time(12, 0),
        )
        self._viaje_limpio(vehiculo=self.vehiculo, hora=time(14, 0))  # no lanza

    # -- Viaje sin hora con bloqueo de rango y de dia completo --

    def test_viaje_sin_hora_no_choca_con_rango(self):
        """Sin hora en el viaje, un bloqueo de rango no lo toca (spec §4)."""
        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=self.vehiculo, fecha=MANANA,
            hora_desde=time(8, 0), hora_hasta=time(12, 0),
        )
        self._viaje_limpio(vehiculo=self.vehiculo, hora=None)  # no lanza

    def test_viaje_sin_hora_choca_con_dia_completo(self):
        """Sin hora en el viaje, un bloqueo de dia completo si lo toca."""
        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=self.vehiculo, fecha=MANANA,
        )
        with self.assertRaises(ValidationError) as cm:
            self._viaje_limpio(vehiculo=self.vehiculo, hora=None)
        self.assertIn('vehiculo', cm.exception.message_dict)

    # -- Viaje cancelado no se asigna --

    def test_viaje_cancelado_no_se_asigna(self):
        v = ViajeTransporte(
            empresa=self.empresa, reserva=self.reserva,
            sentido=ViajeTransporte.Sentido.UNICO, fecha=MANANA,
            vehiculo=self.vehiculo, cancelado=True,
        )
        with self.assertRaises(ValidationError) as cm:
            v.full_clean()
        self.assertIn('vehiculo', cm.exception.message_dict)

    # -- Viaje sin vehiculo asignado es valido (pendiente de asignar) --

    def test_viaje_sin_vehiculo_valido(self):
        self._viaje_limpio(vehiculo=None)  # no lanza

    # -- Unicidad (reserva, sentido) --

    def test_unicidad_reserva_sentido(self):
        from django.db import IntegrityError
        _viaje(self.empresa, self.reserva, sentido='unico', fecha=MANANA)
        with self.assertRaises(IntegrityError):
            _viaje(self.empresa, self.reserva, sentido='unico', fecha=MANANA)
