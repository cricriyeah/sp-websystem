"""Pruebas del apartado temporal de cupo para hospedaje y paquetes (Tarea 04)."""

from datetime import date, time, timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone

from apps.bookings.cupo import (
    SinCupoError,
    construir_retrato_hospedaje,
    construir_retrato_paquete,
    elegir_habitaciones,
    evaluar_disponibilidad_hospedaje,
    obtener_recursos_con_ocupaciones,
)
from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar
from apps.bookings.cupo.nucleo import recursos_disponibles_en_rango
from apps.bookings.models import Reserva, ReservaOcupacion
from apps.fleet.models import Paquete, PaqueteServicio, Recurso, Servicio
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca


class ApartadoHospedajeTests(EmpresaTestCase):
    """Pruebas unitarias de selección y apartado temporal de habitaciones."""

    def setUp(self):
        super().setUp()
        self.servicio_hospedaje = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Hotel y Cabañas del Mar',
            slug='hotel-cabanas-mar',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            precio_base=Decimal('2500'),
        )
        # Tres cabañas con capacidades 2, 4 y 6
        self.cabana_chica = Recurso.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            nombre='Cabaña Chica',
            capacidad_maxima=2,
            activo=True,
        )
        self.cabana_mediana = Recurso.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            nombre='Cabaña Mediana',
            capacidad_maxima=4,
            activo=True,
        )
        self.cabana_grande = Recurso.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            nombre='Cabaña Grande',
            capacidad_maxima=6,
            activo=True,
        )
        self.check_in = date.today() + timedelta(days=10)
        self.check_out = date.today() + timedelta(days=15)

    def test_apartar_y_confirmar_eligen_mismas_habitaciones(self):
        """Apartar y confirmar eligen LAS MISMAS habitaciones para el mismo grupo y rango."""
        reserva = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            fecha=self.check_in,
            fecha_salida=self.check_out,
            hora=time(6, 0),
            numero_personas=3,
            nombre_cliente='Ana Ruiz',
            telefono_cliente='+526121234567',
            correo_cliente='ana@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )

        with override_settings(APARTADO_MINUTOS=15):
            retrato = construir_retrato_hospedaje(reserva)
            habitaciones_apartadas = [h['recurso_id'] for h in retrato['habitaciones']]
            # La selección pura directa también coincide
            habitaciones_elegidas = elegir_habitaciones(
                self.servicio_hospedaje, self.check_in, self.check_out, 3, empresa=self.empresa,
            )
            self.assertEqual(habitaciones_apartadas, habitaciones_elegidas)

            # Confirmamos la reserva (simulando webhook/pago)
            reservar_cupo_al_confirmar(reserva)
            habitaciones_confirmadas = list(
                reserva.ocupaciones.values_list('recurso_id', flat=True).order_by('recurso_id')
            )

            # Apartado y confirmación deben elegir exactamente los mismos recursos
            self.assertEqual(habitaciones_apartadas, habitaciones_confirmadas)
            # Para 3 personas entre capacidades 2, 4, 6, debe preferir la mediana (4 pax, menor desperdicio)
            self.assertEqual(habitaciones_confirmadas, [self.cabana_mediana.pk])

    def test_habitacion_apartada_ocupada_en_su_rango_y_solo_para_su_servicio(self):
        """Una habitación apartada aparece ocupada en su rango y solo para su servicio."""
        # Creamos un segundo servicio de hospedaje en la misma empresa con su propio recurso
        servicio_secundario = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Posada de la Bahía',
            slug='posada-bahia',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            precio_base=Decimal('1800'),
        )
        Recurso.objects.create(
            empresa=self.empresa,
            servicio=servicio_secundario,
            nombre='Cabaña Bahía Uno',
            capacidad_maxima=2,
            activo=True,
        )

        # Reserva A aparta la cabaña grande (6 pax)
        reserva_a = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            fecha=self.check_in,
            fecha_salida=self.check_out,
            hora=time(6, 0),
            numero_personas=6,
            nombre_cliente='Carlos Lopez',
            telefono_cliente='+526121234568',
            correo_cliente='carlos@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            apartado_hasta=timezone.now() + timedelta(minutes=15),
        )
        with override_settings(APARTADO_MINUTOS=15):
            reserva_a.apartado_demanda = construir_retrato_hospedaje(reserva_a)
            reserva_a.save(update_fields=['apartado_demanda'])

            # 1. En el rango [check_in, check_out) del mismo servicio, cabaña grande está apartada:
            # no hay lugar para un grupo de 6 en una sola habitación en self.servicio_hospedaje
            disp_mismo_servicio = evaluar_disponibilidad_hospedaje(
                check_in=self.check_in,
                check_out=self.check_out,
                personas=6,
                empresa=self.empresa,
                servicio=self.servicio_hospedaje,
                cantidad_recursos=1,
            )
            self.assertFalse(disp_mismo_servicio)

            # Para más personas que la capacidad conjunta restante (4 + 2 = 6), tampoco cabe
            disp_excede_total = evaluar_disponibilidad_hospedaje(
                check_in=self.check_in,
                check_out=self.check_out,
                personas=7,
                empresa=self.empresa,
                servicio=self.servicio_hospedaje,
            )
            self.assertFalse(disp_excede_total)

            # Cabaña grande no aparece entre los recursos libres en ese rango
            recursos_con_oc = obtener_recursos_con_ocupaciones(
                self.check_in, self.check_out, self.empresa, servicio=self.servicio_hospedaje,
            )
            libres = [r_id for r_id, _ in recursos_disponibles_en_rango(recursos_con_oc, self.check_in, self.check_out)]
            self.assertNotIn(self.cabana_grande.pk, libres)
            self.assertIn(self.cabana_chica.pk, libres)
            self.assertIn(self.cabana_mediana.pk, libres)

            # 2. En fechas contiguas o no traslapadas [check_out, check_out + 5 días), la cabaña grande está libre
            disp_fechas_contiguas = evaluar_disponibilidad_hospedaje(
                check_in=self.check_out,
                check_out=self.check_out + timedelta(days=5),
                personas=6,
                empresa=self.empresa,
                servicio=self.servicio_hospedaje,
                cantidad_recursos=1,
            )
            self.assertTrue(disp_fechas_contiguas)

            # 3. Solo para su servicio: el servicio secundario no se ve afectado por el apartado
            disp_otro_servicio = evaluar_disponibilidad_hospedaje(
                check_in=self.check_in,
                check_out=self.check_out,
                personas=2,
                empresa=self.empresa,
                servicio=servicio_secundario,
            )
            self.assertTrue(disp_otro_servicio)

    def test_la_propia_reserva_se_excluye_a_si_misma(self):
        """La propia reserva se excluye a sí misma al evaluar cupo."""
        # Desactivamos cabaña chica y mediana para que solo quede cabaña grande
        self.cabana_chica.activo = False
        self.cabana_chica.save()
        self.cabana_mediana.activo = False
        self.cabana_mediana.save()

        reserva = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            fecha=self.check_in,
            fecha_salida=self.check_out,
            hora=time(6, 0),
            numero_personas=5,
            nombre_cliente='Maria Torres',
            telefono_cliente='+526121234569',
            correo_cliente='maria@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            apartado_hasta=timezone.now() + timedelta(minutes=15),
        )
        with override_settings(APARTADO_MINUTOS=15):
            reserva.apartado_demanda = construir_retrato_hospedaje(reserva)
            reserva.save(update_fields=['apartado_demanda'])

            # Sin excluir_pk (otro cliente evaluando): no cabe porque la cabaña está apartada
            self.assertFalse(
                evaluar_disponibilidad_hospedaje(
                    self.check_in, self.check_out, 5, self.empresa,
                    servicio=self.servicio_hospedaje,
                )
            )

            # Con excluir_pk=reserva.pk (la propia reserva recargando o avanzando): sí cabe
            self.assertTrue(
                evaluar_disponibilidad_hospedaje(
                    self.check_in, self.check_out, 5, self.empresa,
                    servicio=self.servicio_hospedaje,
                    excluir_pk=reserva.pk,
                )
            )

    def test_apartado_vencido_o_con_setting_cero_no_cuenta(self):
        """Un apartado vencido o con APARTADO_MINUTOS=0 no cuenta como ocupado."""
        self.cabana_chica.activo = False
        self.cabana_chica.save()
        self.cabana_mediana.activo = False
        self.cabana_mediana.save()

        # Caso A: apartado vencido (apartado_hasta en el pasado)
        reserva_vencida = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            fecha=self.check_in,
            fecha_salida=self.check_out,
            hora=time(6, 0),
            numero_personas=5,
            nombre_cliente='Pedro Morales',
            telefono_cliente='+526121234570',
            correo_cliente='pedro@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            apartado_hasta=timezone.now() - timedelta(minutes=5),
            apartado_demanda={
                "v": 1,
                "salidas": [],
                "habitaciones": [{
                    "recurso_id": self.cabana_grande.pk,
                    "inicio": self.check_in.isoformat(),
                    "fin": self.check_out.isoformat(),
                    "servicio_id": self.servicio_hospedaje.pk,
                }],
            },
        )
        with override_settings(APARTADO_MINUTOS=15):
            self.assertTrue(
                evaluar_disponibilidad_hospedaje(
                    self.check_in, self.check_out, 5, self.empresa,
                    servicio=self.servicio_hospedaje,
                )
            )

        # Caso B: APARTADO_MINUTOS=0 con apartado vigente en fecha
        reserva_vencida.apartado_hasta = timezone.now() + timedelta(minutes=15)
        reserva_vencida.save(update_fields=['apartado_hasta'])

        with override_settings(APARTADO_MINUTOS=0):
            # Con el setting apagado, el motor ignora todo apartado
            self.assertTrue(
                evaluar_disponibilidad_hospedaje(
                    self.check_in, self.check_out, 5, self.empresa,
                    servicio=self.servicio_hospedaje,
                )
            )

    def test_restriccion_exclude_nunca_se_entera_no_se_crean_filas(self):
        """La restricción EXCLUDE de ReservaOcupacion nunca se entera (no se crean filas físicas)."""
        reserva = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            fecha=self.check_in,
            fecha_salida=self.check_out,
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Sofia Vargas',
            telefono_cliente='+526121234571',
            correo_cliente='sofia@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
            apartado_hasta=timezone.now() + timedelta(minutes=15),
        )
        with override_settings(APARTADO_MINUTOS=15):
            retrato = construir_retrato_hospedaje(reserva)
            reserva.apartado_demanda = retrato
            reserva.save(update_fields=['apartado_demanda'])

            # Se cuenta virtualmente en el motor
            recursos_con_oc = obtener_recursos_con_ocupaciones(
                self.check_in, self.check_out, self.empresa, servicio=self.servicio_hospedaje,
            )
            hab_apartada_id = retrato['habitaciones'][0]['recurso_id']
            oc_apartada = [
                ocupaciones for r_id, _, ocupaciones in recursos_con_oc if r_id == hab_apartada_id
            ][0]
            self.assertEqual(len(oc_apartada), 1)
            self.assertEqual(oc_apartada[0], (self.check_in, self.check_out))

            # Y NUNCA se creó ninguna fila física en ReservaOcupacion
            self.assertEqual(ReservaOcupacion.objects.count(), 0)

    def test_paquete_con_mar_y_hospedaje_arma_un_solo_retrato_correcto(self):
        """Un paquete con mar Y hospedaje arma un solo retrato correcto."""
        crear_flota(self.empresa)
        srv_pesca = crear_servicio_pesca(self.empresa)

        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Pesca y Cabaña',
            slug='paquete-pesca-cabana',
            precio_ancla=Decimal('7000'),
        )
        PaqueteServicio.objects.create(
            paquete=paquete, servicio=srv_pesca, orden=1, salidas=2, dia_estancia=1,
        )
        PaqueteServicio.objects.create(
            paquete=paquete, servicio=self.servicio_hospedaje, orden=2, noches=3, dia_estancia=1,
        )

        reserva_paquete = Reserva.objects.create(
            empresa=self.empresa,
            paquete=paquete,
            fecha=self.check_in,
            fecha_salida=self.check_in + timedelta(days=3),
            hora=time(6, 0),
            numero_personas=4,
            nombre_cliente='David Morales',
            telefono_cliente='+526121234572',
            correo_cliente='david@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )

        with override_settings(APARTADO_MINUTOS=15):
            retrato = construir_retrato_paquete(reserva_paquete)

            self.assertEqual(retrato['v'], 1)
            # Salidas de mar (2 salidas en días consecutivos)
            self.assertEqual(len(retrato['salidas']), 2)
            fechas_salidas = [s['fecha'] for s in retrato['salidas']]
            self.assertEqual(fechas_salidas, [
                self.check_in.isoformat(),
                (self.check_in + timedelta(days=1)).isoformat(),
            ])
            for s in retrato['salidas']:
                self.assertEqual(s['personas'], 4)
                self.assertEqual(s['servicio_id'], srv_pesca.pk)

            # Habitaciones de hospedaje (rango [check_in, check_in + 3))
            self.assertEqual(len(retrato['habitaciones']), 1)
            hab = retrato['habitaciones'][0]
            self.assertEqual(hab['recurso_id'], self.cabana_mediana.pk)
            self.assertEqual(hab['inicio'], self.check_in.isoformat())
            self.assertEqual(hab['fin'], (self.check_in + timedelta(days=3)).isoformat())
            self.assertEqual(hab['servicio_id'], self.servicio_hospedaje.pk)

    def test_sin_habitaciones_disponibles_lanza_sin_cupo_error(self):
        """Si no hay habitaciones libres para el grupo, lanza SinCupoError."""
        # Ocupamos todas las cabañas confirmadas con otra reserva
        reserva_ocupante = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            fecha=self.check_in,
            fecha_salida=self.check_out,
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Lucia Gomez',
            telefono_cliente='+526121234573',
            correo_cliente='lucia@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PAGADA,
        )
        for cabana in [self.cabana_chica, self.cabana_mediana, self.cabana_grande]:
            ReservaOcupacion.objects.create(
                reserva=reserva_ocupante,
                recurso=cabana,
                empresa=self.empresa,
                fecha_inicio=self.check_in,
                fecha_fin=self.check_out,
                ocupa_cupo=True,
            )

        # Nueva reserva intenta apartar hospedaje directo
        reserva_sin_cupo = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.servicio_hospedaje,
            fecha=self.check_in,
            fecha_salida=self.check_out,
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Gabriel Soto',
            telefono_cliente='+526121234574',
            correo_cliente='gabriel@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        with self.assertRaises(SinCupoError) as ctx:
            construir_retrato_hospedaje(reserva_sin_cupo)
        self.assertIn('No hay habitación disponible', str(ctx.exception))

        # En paquete con componente de hospedaje sin habitaciones libres
        crear_flota(self.empresa)
        srv_pesca = crear_servicio_pesca(self.empresa)
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Sin Cupo Hospedaje',
            slug='paquete-sin-cupo-hospedaje',
            precio_ancla=Decimal('6000'),
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=srv_pesca, orden=1, salidas=1)
        PaqueteServicio.objects.create(paquete=paquete, servicio=self.servicio_hospedaje, orden=2, noches=2)

        reserva_paquete = Reserva.objects.create(
            empresa=self.empresa,
            paquete=paquete,
            fecha=self.check_in,
            fecha_salida=self.check_in + timedelta(days=2),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Raul Mendez',
            telefono_cliente='+526121234575',
            correo_cliente='raul@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        with self.assertRaises(SinCupoError) as ctx_paq:
            construir_retrato_paquete(reserva_paquete)
        self.assertIn('No hay habitación disponible para el componente', str(ctx_paq.exception))
