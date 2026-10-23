"""Un paquete con traslado crea sus tramos en «Asignar vehiculos».

Auditoria 2026-10-23: un paquete de La Ventana que incluye el traslado del aeropuerto no creaba
ningun ViajeTransporte, asi que el traslado no aparecia en la pantalla de vehiculos. El checkout no
pide la hora del vuelo (solo el aeropuerto), por eso los tramos nacen sin hora y la pantalla los
marca «Falta la hora de vuelo» para que la vendedora la capture.
"""
from datetime import time, timedelta
from decimal import Decimal

from django.urls import reverse

from apps.fleet.models import Paquete, PaqueteServicio, Servicio

from .models import Reserva, ViajeTransporte
from .tests_alta_cupo_fisico import AltaManualBase


class ViajesDePaqueteBase(AltaManualBase):
    def setUp(self):
        super().setUp()
        self.traslado = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado del aeropuerto', slug='traslado-paq',
            tipo_servicio='transporte', estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
            capacidad_maxima=14, solo_en_paquete=True, pide_hora=False,
        )
        self.paquete = self.crear_paquete('con-traslado', hotel=True)

    def crear_paquete(self, slug, *, hotel):
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre=f'Paquete {slug}', slug=slug,
            precio_ancla=Decimal('9500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete, servicio=self.pesca, orden=1, dia_estancia=2 if hotel else 1, personas_incluidas=3,
        )
        if hotel:
            PaqueteServicio.objects.create(
                paquete=paquete, servicio=self.hotel, orden=2, noches=3, personas_incluidas=3,
            )
        PaqueteServicio.objects.create(
            paquete=paquete, servicio=self.traslado, orden=3, dia_estancia=1, personas_incluidas=3,
        )
        return paquete

    def vender_paquete(self, paquete=None, **extra):
        respuesta = self.client.post(self.url, self.datos(
            nombre_cliente='Viajera', paquete=str((paquete or self.paquete).pk), fecha=self.llegada.isoformat(),
            numero_personas='3', precio_total='9500.00', **extra,
        ))
        self.assertEqual(respuesta.status_code, 302)
        return Reserva.objects.get(nombre_cliente='Viajera')

    def tramos(self, reserva):
        return {v.sentido: v for v in ViajeTransporte.objects.filter(reserva=reserva)}


class ViajesDePaqueteTests(ViajesDePaqueteBase):
    def test_la_venta_manual_crea_ida_a_la_llegada_y_regreso_a_la_salida_sin_hora(self):
        reserva = self.vender_paquete()

        tramos = self.tramos(reserva)
        self.assertEqual(set(tramos), {'ida', 'regreso'})
        self.assertEqual(tramos['ida'].fecha, self.llegada)
        self.assertEqual(tramos['regreso'].fecha, self.llegada + timedelta(days=3))
        self.assertTrue(all(t.hora is None and not t.cancelado and t.empresa_id == self.empresa.pk for t in tramos.values()))

    def test_pagar_una_reserva_pendiente_del_paquete_los_crea_igual_que_el_webhook(self):
        reserva = self.vender_paquete(ya_pago='no')
        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 0)

        reserva.estado = Reserva.Estado.PAGADA  # lo mismo que hace aplicar_pago_exitoso antes de guardar
        reserva.save()

        self.assertEqual(set(self.tramos(reserva)), {'ida', 'regreso'})

    def test_cancelar_el_paquete_cancela_sus_tramos(self):
        reserva = self.vender_paquete()

        reserva.estado = Reserva.Estado.CANCELADA
        reserva.save()

        self.assertTrue(all(t.cancelado for t in self.tramos(reserva).values()))

    def test_un_paquete_sin_traslado_no_crea_tramos(self):
        PaqueteServicio.objects.filter(paquete=self.paquete, servicio=self.traslado).delete()

        reserva = self.vender_paquete()

        self.assertEqual(ViajeTransporte.objects.filter(reserva=reserva).count(), 0)

    def test_sin_hospedaje_ida_y_regreso_caen_el_dia_del_traslado(self):
        paquete = self.crear_paquete('sin-hotel', hotel=False)

        reserva = self.vender_paquete(paquete)

        tramos = self.tramos(reserva)
        self.assertEqual({t.fecha for t in tramos.values()}, {self.llegada})
        self.assertEqual(set(tramos), {'ida', 'regreso'})

    def test_la_hora_de_vuelo_capturada_no_se_pierde_al_guardar_la_reserva(self):
        reserva = self.vender_paquete()
        ViajeTransporte.objects.filter(reserva=reserva).update(hora=time(14, 30))

        reserva.nombre_cliente = 'Viajera Corregida'
        reserva.save()

        self.assertEqual({t.hora for t in self.tramos(reserva).values()}, {time(14, 30)})

    def test_cambiar_el_inicio_del_paquete_mueve_los_tramos_y_suelta_el_vehiculo(self):
        reserva = self.vender_paquete()

        reserva.inicio_paquete = self.llegada + timedelta(days=1)
        reserva.fecha = self.llegada + timedelta(days=2)
        reserva.fecha_salida = self.llegada + timedelta(days=4)
        reserva.save()

        tramos = self.tramos(reserva)
        self.assertEqual(tramos['ida'].fecha, self.llegada + timedelta(days=1))
        self.assertEqual(tramos['regreso'].fecha, self.llegada + timedelta(days=4))


class PantallaDeVehiculosConPaqueteTests(ViajesDePaqueteBase):
    def setUp(self):
        super().setUp()
        self.reserva = self.vender_paquete()
        Reserva.objects.filter(pk=self.reserva.pk).update(aeropuerto='lap')
        self.lista = reverse('admin:bookings_viajetransporte_changelist')

    def test_los_tramos_del_paquete_salen_marcados_falta_hora_de_vuelo(self):
        respuesta = self.client.get(self.lista, {'cuando': 'todos'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Falta la hora de vuelo', count=2)  # ida y regreso
        self.assertContains(respuesta, 'Aeropuerto LAP')

    def test_la_vendedora_captura_la_hora_de_vuelo_de_la_ida_y_el_regreso(self):
        ida = ViajeTransporte.objects.get(reserva=self.reserva, sentido='ida')
        regreso = ViajeTransporte.objects.get(reserva=self.reserva, sentido='regreso')

        respuesta = self.client.post(self.lista, {
            'form-TOTAL_FORMS': '2', 'form-INITIAL_FORMS': '2', 'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(ida.pk), 'form-0-hora': '13:15',
            'form-1-id': str(regreso.pk), 'form-1-hora': '09:40',
            '_save': 'Guardar',
        })

        self.assertEqual(respuesta.status_code, 302)
        ida.refresh_from_db()
        regreso.refresh_from_db()
        self.assertEqual(ida.hora, time(13, 15))
        self.assertEqual(regreso.hora, time(9, 40))
        self.assertNotContains(self.client.get(self.lista, {'cuando': 'todos'}), 'Falta la hora de vuelo')
