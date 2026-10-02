"""La confirmación ocupa cada día de mar o revierte el cobro completo."""
import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.bookings.cupo import SinCupoError
from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar
from apps.fleet.models import Paquete, PaqueteServicio, Recurso, Servicio, capacidades_disponibles
from apps.payments.services import APLICADO, aplicar_pago_exitoso
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import crear_flota


class AplicarPagoSalidasMultidiaTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(
            nombre='Sede Pago Salidas', slug='sede-pago-salidas', zona_horaria='America/Mazatlan',
        )
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa Pago Salidas', slug='empresa-pago-salidas',
            stripe_secret_key='sk_test_pago_salidas', stripe_webhook_secret='whsec_pago_salidas',
            stripe_publishable_key='pk_test_pago_salidas',
        )

    def _paquete_de_mar(self, noches=5, dia=2, salidas=4):
        s_pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca Mar', slug='pesca-mar', tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia', precio_base=Decimal('3000.00'), activo=True,
        )
        s_hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Hotel Mar', slug='hotel-mar', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche', precio_base=Decimal('2000.00'), activo=True,
        )
        Recurso.objects.create(empresa=self.empresa, servicio=s_hotel, nombre='Hab 1', capacidad_maxima=2, activo=True)
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Mar', slug='mar',
            precio_ancla=Decimal('10000.00'), permite_anticipo=False, activo=True,
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=s_hotel, orden=1, noches=noches)
        PaqueteServicio.objects.create(paquete=paquete, servicio=s_pesca, orden=2, dia_estancia=dia, salidas=salidas)
        return paquete, s_pesca

    def _reserva_pendiente(self, paquete, inicio, dia=2, noches=5):
        reserva = Reserva(
            empresa=self.empresa, paquete=paquete, fecha=inicio + timedelta(days=dia - 1), inicio_paquete=inicio,
            fecha_salida=inicio + timedelta(days=noches), hora=time(6, 0), numero_personas=2,
            nombre_cliente='Cliente Mar', telefono_cliente='+5216121234567', correo_cliente='mar@example.com',
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True, deslinde_nombre='Cliente Mar',
            checkout_id=uuid.uuid4(), moneda='MXN', precio_total=Decimal('10000.00'),
            forma_pago=Reserva.FormaPago.COMPLETO,
        )
        reserva.save()
        return reserva

    def _intent(self, reserva):
        return {
            'id': f'pi_mar_{reserva.pk}', 'amount_received': 1000000, 'currency': 'mxn',
            'metadata': {'reserva_id': str(reserva.pk)}, 'created': int(timezone.now().timestamp()),
        }

    def test_confirmar_el_pago_crea_una_salida_por_dia_de_mar(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, _ = self._paquete_de_mar()
            reserva = self._reserva_pendiente(paquete, inicio)
            self.assertEqual(aplicar_pago_exitoso(self._intent(reserva), self.empresa), APLICADO)
            fechas = list(reserva.salidas.order_by('fecha').values_list('fecha', flat=True))
        self.assertEqual(fechas, [inicio + timedelta(days=d) for d in (1, 2, 3, 4)])

    def test_sin_cupo_en_un_dia_intermedio_no_deja_salidas_y_reembolsa(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, s_pesca = self._paquete_de_mar()
            reserva = self._reserva_pendiente(paquete, inicio)
            tope = len(capacidades_disponibles(inicio + timedelta(days=2), self.empresa))
            for i in range(tope):
                Reserva.objects.create(
                    empresa=self.empresa, servicio=s_pesca, fecha=inicio + timedelta(days=2), hora=time(6, 0),
                    numero_personas=3, nombre_cliente=f'Lleno {i}', telefono_cliente='+5216121234567',
                    correo_cliente=f'l{i}@example.com', canal_origen='whatsapp', moneda='MXN',
                    estado=Reserva.Estado.PAGADA,
                )
            with mock.patch('apps.payments.services.reembolsar', return_value=True) as reembolso:
                aplicar_pago_exitoso(self._intent(reserva), self.empresa)
            reserva.refresh_from_db()
            self.assertEqual(reserva.salidas.count(), 0)
            self.assertEqual(reserva.ocupaciones.count(), 0)
            self.assertEqual(reserva.componentes.count(), 0)
            self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
            reembolso.assert_called_once()

    def test_locks_de_dos_actividades_siguen_orden_de_fecha_global(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, _ = self._paquete_de_mar()
            paseo = Servicio.objects.create(
                empresa=self.empresa, nombre='Paseo Mar', slug='paseo-mar', tipo_servicio='paseo',
                estrategia_cupo='por_recurso_dia', precio_base=Decimal('3000.00'), activo=True,
            )
            PaqueteServicio.objects.create(
                paquete=paquete, servicio=paseo, orden=3, dia_estancia=2, salidas=4,
            )
            reserva = self._reserva_pendiente(paquete, inicio)
            fechas_bloqueadas = []
            with mock.patch('apps.bookings.cupo.confirmacion.bloquear_cupo',
                            side_effect=lambda empresa_id, fecha, servicio_id: fechas_bloqueadas.append(fecha)):
                reservar_cupo_al_confirmar(reserva)
            self.assertEqual(fechas_bloqueadas, sorted(fechas_bloqueadas))
            self.assertEqual(len(fechas_bloqueadas), 8)

    def test_un_grupo_que_no_cabe_en_una_habitacion_ocupa_dos(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, _ = self._paquete_de_mar()
            hotel = Servicio.objects.get(slug='hotel-mar')
            Recurso.objects.create(empresa=self.empresa, servicio=hotel, nombre='Hab 2', capacidad_maxima=2, activo=True)
            reserva = self._reserva_pendiente(paquete, inicio)
            Reserva.objects.filter(pk=reserva.pk).update(
                numero_personas=3, personas_por_servicio={str(hotel.pk): 3},
            )
            reserva.refresh_from_db()
            with mock.patch('apps.payments.services.reembolsar', return_value=True):
                resultado = aplicar_pago_exitoso(self._intent(reserva), self.empresa)
            self.assertEqual(resultado, APLICADO)
            self.assertEqual(reserva.ocupaciones.count(), 2)

    def test_si_no_alcanzan_las_habitaciones_juntas_no_se_confirma(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, _ = self._paquete_de_mar()
            hotel = Servicio.objects.get(slug='hotel-mar')
            reserva = self._reserva_pendiente(paquete, inicio)
            Reserva.objects.filter(pk=reserva.pk).update(
                numero_personas=3, personas_por_servicio={str(hotel.pk): 3},
            )
            reserva.refresh_from_db()
            with mock.patch('apps.payments.services.reembolsar', return_value=True):
                aplicar_pago_exitoso(self._intent(reserva), self.empresa)
            reserva.refresh_from_db()
            self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
            self.assertEqual(reserva.ocupaciones.count(), 0)

    def test_habitacion_ocupada_en_parte_de_la_estancia_no_cuenta_como_libre(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, _ = self._paquete_de_mar()
            hotel = Servicio.objects.get(slug='hotel-mar')
            segunda = Recurso.objects.create(
                empresa=self.empresa, servicio=hotel, nombre='Hab 2', capacidad_maxima=2, activo=True,
            )
            ocupante = Reserva.objects.create(
                empresa=self.empresa, servicio=hotel, fecha=inicio + timedelta(days=2),
                fecha_salida=inicio + timedelta(days=3), hora=time(6, 0), numero_personas=1,
                nombre_cliente='Ocupante', telefono_cliente='+5216121234567',
                correo_cliente='ocupante@example.com', canal_origen='whatsapp', moneda='MXN',
                estado=Reserva.Estado.PAGADA,
            )
            from apps.bookings.models import ReservaOcupacion
            ReservaOcupacion.objects.create(
                empresa=self.empresa, reserva=ocupante, recurso=segunda,
                fecha_inicio=inicio + timedelta(days=2), fecha_fin=inicio + timedelta(days=3),
            )
            reserva = self._reserva_pendiente(paquete, inicio)
            Reserva.objects.filter(pk=reserva.pk).update(
                numero_personas=3, personas_por_servicio={str(hotel.pk): 3},
            )
            reserva.refresh_from_db()
            with mock.patch('apps.payments.services.reembolsar', return_value=True):
                aplicar_pago_exitoso(self._intent(reserva), self.empresa)
            reserva.refresh_from_db()
            self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
            self.assertEqual(reserva.ocupaciones.count(), 0)

    def test_sin_habitaciones_activas_se_reembolsa(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, _ = self._paquete_de_mar()
            hotel = Servicio.objects.get(slug='hotel-mar')
            hotel.recursos.update(activo=False)
            reserva = self._reserva_pendiente(paquete, inicio)
            with self.assertRaises(SinCupoError):
                reservar_cupo_al_confirmar(reserva)
            with mock.patch('apps.payments.services.reembolsar', return_value=True):
                aplicar_pago_exitoso(self._intent(reserva), self.empresa)
            reserva.refresh_from_db()
            self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
