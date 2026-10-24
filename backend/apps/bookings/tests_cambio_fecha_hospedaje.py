"""Cambiar las fechas o el grupo de un hospedaje ya pagado mueve sus habitaciones.

Segunda auditoria 2026-10-23, hallazgo alto 1: la reserva cambiaba de fechas pero su
`ReservaOcupacion` se quedaba en las viejas, asi que la habitacion seguia bloqueada alli y las
fechas nuevas se podian vender otra vez.
"""
from datetime import timedelta

from django.db import transaction
from django.urls import reverse

from apps.bookings.cupo import SinCupoError
from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar
from apps.bookings.cupo.hospedaje_sync import sincronizar_ocupaciones
from decimal import Decimal

from apps.fleet.models import Paquete, PaqueteServicio, Recurso

from .models import Reserva, ReservaOcupacion
from .tests_alta_cupo_fisico import AltaManualBase


class CambioDeFechaTests(AltaManualBase):
    def datos_en(self, nombre, dias=0):
        entrada = self.llegada + timedelta(days=dias)
        return self.datos(
            servicio=str(self.hotel.pk), nombre_cliente=nombre, fecha=entrada.isoformat(),
            fecha_salida=(entrada + timedelta(days=3)).isoformat(), precio_total='4500.00',
        )

    def vender(self, nombre, dias=0):
        respuesta = self.client.post(self.url, self.datos_en(nombre, dias))
        self.assertEqual(respuesta.status_code, 302)
        return Reserva.objects.get(nombre_cliente=nombre)

    def editar(self, reserva, **extra):
        datos = {
            'nombre_cliente': reserva.nombre_cliente, 'telefono_cliente': reserva.telefono_cliente,
            'correo_cliente': reserva.correo_cliente, 'fecha': reserva.fecha.isoformat(),
            'fecha_salida': reserva.fecha_salida.isoformat() if reserva.fecha_salida else '',
            'numero_personas': str(reserva.numero_personas), 'servicio': str(reserva.servicio_id or ''),
            'canal_origen': reserva.canal_origen, 'estado': reserva.estado, 'moneda': reserva.moneda,
            'forma_pago': reserva.forma_pago, 'precio_total': str(reserva.precio_total or ''),
            'ocupaciones-TOTAL_FORMS': '0', 'ocupaciones-INITIAL_FORMS': '0',
            'componentes-TOTAL_FORMS': '0', 'componentes-INITIAL_FORMS': '0',
            **extra,
        }
        return self.client.post(reverse('admin:bookings_reserva_change', args=[reserva.pk]), datos)

    def nuevas_fechas(self, dias):
        entrada = self.llegada + timedelta(days=dias)
        return {'fecha': entrada.isoformat(), 'fecha_salida': (entrada + timedelta(days=3)).isoformat()}

    def test_cambiar_las_fechas_mueve_la_habitacion(self):
        reserva = self.vender('Mover')
        antes = reserva.ocupaciones.get()
        self.assertEqual(antes.fecha_inicio, self.llegada)

        respuesta = self.editar(reserva, **self.nuevas_fechas(10))

        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and respuesta.context['adminform'].form.errors)
        ocupacion = reserva.ocupaciones.get()
        self.assertEqual(ocupacion.recurso, self.habitacion)
        self.assertEqual(ocupacion.fecha_inicio, self.llegada + timedelta(days=10))
        self.assertEqual(ocupacion.fecha_fin, self.llegada + timedelta(days=13))
        self.assertTrue(ocupacion.ocupa_cupo)

    def test_las_fechas_viejas_quedan_libres_y_las_nuevas_ocupadas(self):
        reserva = self.vender('Mover')
        self.editar(reserva, **self.nuevas_fechas(10))

        # La misma habitacion se puede vender en las fechas viejas...
        otra = self.vender('En las viejas')
        self.assertEqual(otra.ocupaciones.get().recurso, self.habitacion)
        # ...y ya no en las nuevas.
        respuesta = self.client.post(self.url, self.datos_en('En las nuevas', dias=10))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='En las nuevas').exists())

    def test_cambiar_a_fechas_ya_vendidas_avisa_y_no_toca_la_habitacion(self):
        reserva = self.vender('Mover')
        self.vender('Estorba', dias=10)

        respuesta = self.editar(reserva, **self.nuevas_fechas(10))

        self.assertEqual(respuesta.status_code, 200)  # formulario con error, no 500
        reserva.refresh_from_db()
        self.assertEqual(reserva.fecha, self.llegada)
        self.assertEqual(reserva.ocupaciones.get().fecha_inicio, self.llegada)

    def test_un_grupo_mayor_toma_otra_habitacion(self):
        Recurso.objects.filter(pk=self.habitacion.pk).update(capacidad_maxima=3)
        segunda = Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Cabaña 2', capacidad_maxima=3,
        )
        reserva = self.vender('Crece')
        self.assertEqual(reserva.ocupaciones.count(), 1)

        respuesta = self.editar(reserva, numero_personas='5')

        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and respuesta.context['adminform'].form.errors)
        self.assertEqual(
            set(reserva.ocupaciones.values_list('recurso_id', flat=True)), {self.habitacion.pk, segunda.pk},
        )

    def test_corregir_un_dato_cualquiera_no_toca_las_ocupaciones(self):
        reserva = self.vender('Dato')
        antes = reserva.ocupaciones.get()

        respuesta = self.editar(reserva, nombre_cliente='Dato corregido')

        self.assertEqual(respuesta.status_code, 302)
        despues = reserva.ocupaciones.get()
        self.assertEqual(despues.pk, antes.pk)
        self.assertEqual((despues.fecha_inicio, despues.fecha_fin), (antes.fecha_inicio, antes.fecha_fin))

    def test_sin_habitacion_en_el_rango_nuevo_lanza_error_y_deja_las_filas(self):
        reserva = self.vender('Mover')
        self.vender('Estorba', dias=10)
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.fecha = self.llegada + timedelta(days=10)
        reserva.fecha_salida = self.llegada + timedelta(days=13)

        with self.assertRaises(SinCupoError):
            sincronizar_ocupaciones(reserva)

        propia = ReservaOcupacion.objects.get(reserva=reserva)
        self.assertEqual(propia.fecha_inicio, self.llegada)


class CambioDeFechaDePaqueteTests(AltaManualBase):
    """El caso de La Ventana: paquete con hotel, que se mueve por mal clima."""

    def test_mover_el_paquete_mueve_su_habitacion(self):
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Fin de semana', slug='finde-mover',
            precio_ancla=Decimal('9500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete, servicio=self.pesca, orden=1, dia_estancia=2, personas_incluidas=3,
        )
        PaqueteServicio.objects.create(
            paquete=paquete, servicio=self.hotel, orden=2, noches=3, personas_incluidas=3,
        )
        respuesta = self.client.post(self.url, self.datos(
            paquete=str(paquete.pk), fecha=self.llegada.isoformat(), numero_personas='3', precio_total='9500.00',
        ))
        self.assertEqual(respuesta.status_code, 302)
        reserva = Reserva.objects.get(nombre_cliente='Cliente Hotel')
        self.assertEqual(reserva.ocupaciones.get().fecha_inicio, self.llegada)

        reserva = Reserva.objects.get(pk=reserva.pk)  # cargada de la base, como en el admin
        siete = timedelta(days=7)
        reserva.inicio_paquete = reserva.inicio_paquete + siete
        reserva.fecha = reserva.fecha + siete
        reserva.fecha_salida = reserva.fecha_salida + siete
        reserva.save()

        ocupacion = ReservaOcupacion.objects.get(reserva=reserva)
        self.assertEqual(ocupacion.recurso, self.habitacion)
        self.assertEqual(ocupacion.fecha_inicio, self.llegada + siete)
        self.assertEqual(ocupacion.fecha_fin, self.llegada + siete + timedelta(days=3))


class CancelarMoverYReactivarTests(AltaManualBase):
    """Cancelar, reprogramar estando cancelada y reactivar no deja la habitacion en las fechas viejas."""

    def datos_en(self, nombre, dias=0):
        entrada = self.llegada + timedelta(days=dias)
        return self.datos(
            servicio=str(self.hotel.pk), nombre_cliente=nombre, fecha=entrada.isoformat(),
            fecha_salida=(entrada + timedelta(days=3)).isoformat(), precio_total='4500.00',
        )

    def vender(self, nombre, dias=0):
        respuesta = self.client.post(self.url, self.datos_en(nombre, dias))
        self.assertEqual(respuesta.status_code, 302)
        return Reserva.objects.get(nombre_cliente=nombre)

    def test_reactivada_en_otras_fechas_ocupa_las_nuevas_y_libera_las_viejas(self):
        reserva = self.vender('Viajera')
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.motivo_cancelacion = 'Mal clima'
        reserva.save()
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.fecha = self.llegada + timedelta(days=10)
        reserva.fecha_salida = self.llegada + timedelta(days=13)
        reserva.save()

        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.estado = Reserva.Estado.PAGADA
        with transaction.atomic():
            reserva.save()
            reservar_cupo_al_confirmar(reserva)

        ocupacion = ReservaOcupacion.objects.get(reserva=reserva)
        self.assertEqual(ocupacion.fecha_inicio, self.llegada + timedelta(days=10))
        self.assertTrue(ocupacion.ocupa_cupo)
        # las fechas viejas quedan libres para otra venta y las nuevas ya no
        self.assertEqual(self.client.post(self.url, self.datos_en('En las viejas')).status_code, 302)
        self.assertEqual(self.client.post(self.url, self.datos_en('En las nuevas', dias=10)).status_code, 200)

    def test_guardar_fechas_sin_lugar_no_deja_la_reserva_a_medias(self):
        reserva = self.vender('Mover')
        self.vender('Estorba', dias=10)
        reserva = Reserva.objects.get(pk=reserva.pk)
        reserva.fecha = self.llegada + timedelta(days=10)
        reserva.fecha_salida = self.llegada + timedelta(days=13)

        with self.assertRaises(SinCupoError):
            reserva.save()

        reserva = Reserva.objects.get(pk=reserva.pk)
        self.assertEqual(reserva.fecha, self.llegada)
        self.assertEqual(ReservaOcupacion.objects.get(reserva=reserva).fecha_inicio, self.llegada)
