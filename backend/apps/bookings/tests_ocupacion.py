"""Pruebas para el modelo ReservaOcupacion y soporte de estadías en Reserva."""

from datetime import date, time, timedelta
from decimal import Decimal
from unittest import mock, skipUnless

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase

from apps.fleet.models import Paquete, PaqueteServicio, Recurso, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase
from apps.bookings.models import Reserva, ReservaOcupacion, ReservaPaqueteComponente


class ReservaOcupacionModelTests(OperadorTestCase):
    """Pruebas de integridad y validaciones de negocio en ReservaOcupacion."""

    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede Baja Sur', slug='sede-baja-sur')
        self.empresa_a = Empresa.objects.create(sede=self.sede, nombre='Hotel Marino Loreto', slug='loreto-hotel')
        self.empresa_b = Empresa.objects.create(sede=self.sede, nombre='Cabañas del Cabo', slug='cabo-cabanas')

        self.servicio_hospedaje = Servicio.objects.create(
            empresa=self.empresa_a,
            nombre='Suite Frente al Mar',
            slug='suite-frente-mar',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            precio_base=3500,
        )

        self.recurso_1 = Recurso.objects.create(
            empresa=self.empresa_a,
            servicio=self.servicio_hospedaje,
            nombre='Cabaña 101',
            capacidad_maxima=4,
        )
        self.recurso_2 = Recurso.objects.create(
            empresa=self.empresa_a,
            servicio=self.servicio_hospedaje,
            nombre='Cabaña 102',
            capacidad_maxima=4,
        )

        self.reserva = Reserva.objects.create(
            empresa=self.empresa_a,
            servicio=self.servicio_hospedaje,
            fecha=date(2026, 10, 10),
            fecha_salida=date(2026, 10, 15),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Juan Perez',
            telefono_cliente='+526121234567',
            correo_cliente='juan@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PAGADA,
        )

    def test_ocupa_cupo_sigue_el_estado_de_la_reserva(self):
        ocupacion = ReservaOcupacion.objects.create(
            reserva=self.reserva,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 10),
            fecha_fin=date(2026, 10, 15),
        )
        self.assertTrue(ocupacion.ocupa_cupo)

        self.reserva.estado = Reserva.Estado.CANCELADA
        self.reserva.save()
        ocupacion.refresh_from_db()
        self.assertFalse(ocupacion.ocupa_cupo)

        self.reserva.estado = Reserva.Estado.PAGADA
        self.reserva.save()
        ocupacion.refresh_from_db()
        self.assertTrue(ocupacion.ocupa_cupo)

    def test_reserva_propiedades_hospedaje(self):
        """Verifica que Reserva calcule noches y fecha_fin_servicio correctamente."""
        self.assertEqual(self.reserva.noches, 5)
        self.assertEqual(self.reserva.fecha_fin_servicio, date(2026, 10, 15))

    def test_reserva_fecha_salida_invalida_falla_clean(self):
        """fecha_salida <= fecha debe lanzar ValidationError."""
        self.reserva.fecha_salida = self.reserva.fecha
        with self.assertRaises(ValidationError) as ctx:
            self.reserva.clean()
        self.assertIn('fecha_salida', ctx.exception.message_dict)

    def test_creacion_ocupacion_exitosa_y_auto_empresa(self):
        """Crea una ocupación y auto-asigna empresa desde la reserva."""
        ocupacion = ReservaOcupacion(
            reserva=self.reserva,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 10),
            fecha_fin=date(2026, 10, 15),
        )
        ocupacion.clean()
        ocupacion.save()

        self.assertEqual(ocupacion.empresa, self.empresa_a)
        self.assertIn('Cabaña 101 [2026-10-10 a 2026-10-15)', str(ocupacion))

    def test_fecha_fin_anterior_a_inicio_falla_clean(self):
        """fecha_fin <= fecha_inicio debe lanzar ValidationError."""
        ocupacion = ReservaOcupacion(
            empresa=self.empresa_a,
            reserva=self.reserva,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 15),
            fecha_fin=date(2026, 10, 10),
        )
        with self.assertRaises(ValidationError) as ctx:
            ocupacion.clean()
        self.assertIn('fecha_fin', ctx.exception.message_dict)

    def test_inconsistencia_de_empresa_en_reserva_falla_clean(self):
        """Ocupación con empresa distinta a la de la reserva debe fallar."""
        ocupacion = ReservaOcupacion(
            empresa=self.empresa_b,
            reserva=self.reserva,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 10),
            fecha_fin=date(2026, 10, 15),
        )
        with self.assertRaises(ValidationError) as ctx:
            ocupacion.clean()
        self.assertIn('empresa', ctx.exception.message_dict)

    def test_inconsistencia_de_empresa_en_recurso_falla_clean(self):
        """Recurso de otra empresa en la ocupación debe fallar."""
        recurso_b = Recurso.objects.create(
            empresa=self.empresa_b,
            nombre='Cabaña B',
            capacidad_maxima=2,
        )
        ocupacion = ReservaOcupacion(
            empresa=self.empresa_a,
            reserva=self.reserva,
            recurso=recurso_b,
            fecha_inicio=date(2026, 10, 10),
            fecha_fin=date(2026, 10, 15),
        )
        with self.assertRaises(ValidationError) as ctx:
            ocupacion.clean()
        self.assertIn('empresa', ctx.exception.message_dict)

    def test_traslape_con_ocupacion_existente_del_mismo_recurso_falla(self):
        """Dos reservas para el mismo recurso en fechas traslapadas no se permiten."""
        ReservaOcupacion.objects.create(
            empresa=self.empresa_a,
            reserva=self.reserva,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 10),
            fecha_fin=date(2026, 10, 15),
        )

        reserva_2 = Reserva.objects.create(
            empresa=self.empresa_a,
            servicio=self.servicio_hospedaje,
            fecha=date(2026, 10, 12),
            fecha_salida=date(2026, 10, 16),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Maria Lopez',
            telefono_cliente='+526121234568',
            correo_cliente='maria@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PAGADA,
        )

        colision = ReservaOcupacion(
            empresa=self.empresa_a,
            reserva=reserva_2,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 12),
            fecha_fin=date(2026, 10, 16),
        )
        with self.assertRaises(ValidationError) as ctx:
            colision.clean()
        self.assertIn('ya está ocupado en el rango', str(ctx.exception))

    def test_fechas_contiguas_del_mismo_recurso_no_colisionan(self):
        """Salida el 15 y entrada el 15 para la misma cabaña NO colisionan (semi-abierto)."""
        ReservaOcupacion.objects.create(
            empresa=self.empresa_a,
            reserva=self.reserva,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 10),
            fecha_fin=date(2026, 10, 15),
        )

        reserva_2 = Reserva.objects.create(
            empresa=self.empresa_a,
            servicio=self.servicio_hospedaje,
            fecha=date(2026, 10, 15),
            fecha_salida=date(2026, 10, 20),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Carlos Ruiz',
            telefono_cliente='+526121234569',
            correo_cliente='carlos@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PAGADA,
        )

        contigua = ReservaOcupacion(
            empresa=self.empresa_a,
            reserva=reserva_2,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 15),
            fecha_fin=date(2026, 10, 20),
        )
        # No debe lanzar excepción
        contigua.clean()
        contigua.save()
        self.assertTrue(contigua.pk is not None)

    def test_ocupacion_de_reserva_cancelada_no_bloquea_recurso(self):
        """Una ocupación cuya reserva está cancelada no bloquea el recurso."""
        self.reserva.estado = Reserva.Estado.CANCELADA
        self.reserva.save(update_fields=['estado'])

        ReservaOcupacion.objects.create(
            empresa=self.empresa_a,
            reserva=self.reserva,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 10),
            fecha_fin=date(2026, 10, 15),
        )

        reserva_2 = Reserva.objects.create(
            empresa=self.empresa_a,
            servicio=self.servicio_hospedaje,
            fecha=date(2026, 10, 10),
            fecha_salida=date(2026, 10, 15),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Ana Torres',
            telefono_cliente='+526121234570',
            correo_cliente='ana@example.com',
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
            estado=Reserva.Estado.PAGADA,
        )

        nueva_ocupacion = ReservaOcupacion(
            empresa=self.empresa_a,
            reserva=reserva_2,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 10),
            fecha_fin=date(2026, 10, 15),
        )
        nueva_ocupacion.clean()
        nueva_ocupacion.save()
        self.assertTrue(nueva_ocupacion.pk is not None)

    def test_adaptador_evaluar_disponibilidad_hospedaje(self):
        """El adaptador calcula disponibilidad de hospedaje consultando recursos y ocupaciones."""
        from apps.bookings.cupo.adaptador import (
            evaluar_disponibilidad_hospedaje,
            obtener_recursos_con_ocupaciones,
        )

        # Cabaña 101 ocupada del 10 al 15
        ReservaOcupacion.objects.create(
            empresa=self.empresa_a,
            reserva=self.reserva,
            recurso=self.recurso_1,
            fecha_inicio=date(2026, 10, 10),
            fecha_fin=date(2026, 10, 15),
        )

        # Cabaña 102 está libre. Cliente busca del 10 al 15 para 2 personas (1 habitación): disponible
        disponible_1_hab = evaluar_disponibilidad_hospedaje(
            check_in=date(2026, 10, 10),
            check_out=date(2026, 10, 15),
            personas=2,
            empresa=self.empresa_a,
            servicio=self.servicio_hospedaje,
            cantidad_recursos=1,
        )
        self.assertTrue(disponible_1_hab)

        # Cliente busca 2 habitaciones del 10 al 15: NO disponible (solo queda 1 libre)
        disponible_2_hab = evaluar_disponibilidad_hospedaje(
            check_in=date(2026, 10, 10),
            check_out=date(2026, 10, 15),
            personas=2,
            empresa=self.empresa_a,
            servicio=self.servicio_hospedaje,
            cantidad_recursos=2,
        )
        self.assertFalse(disponible_2_hab)

        # Del 15 al 20 (check-out del anterior es el 15): ambas habitaciones están disponibles
        disponible_del_15 = evaluar_disponibilidad_hospedaje(
            check_in=date(2026, 10, 15),
            check_out=date(2026, 10, 20),
            personas=6,
            empresa=self.empresa_a,
            servicio=self.servicio_hospedaje,
            cantidad_recursos=2,
        )
        self.assertTrue(disponible_del_15)


@skipUnless(connection.vendor == 'postgresql', 'Constraint EXCLUDE requiere Postgres y btree_gist')
class ReservaOcupacionExcludeConstraintTests(TransactionTestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='Sede Loreto Exclude', slug='sede-loreto-exclude')
        self.empresa = Empresa.objects.create(sede=sede, nombre='Hotel Loreto Exclude', slug='hotel-loreto-exclude')
        with scope.con_empresa(self.empresa):
            self.servicio = Servicio.objects.create(
                empresa=self.empresa,
                nombre='Suite Vista al Mar',
                slug='suite-vista-al-mar',
                tipo_servicio='hospedaje',
                estrategia_cupo='por_noche',
                precio_base=3000,
            )
            self.recurso = Recurso.objects.create(
                empresa=self.empresa,
                servicio=self.servicio,
                nombre='Habitacion 201',
                capacidad_maxima=2,
            )
            self.reserva_pagada_1 = Reserva.objects.create(
                empresa=self.empresa,
                servicio=self.servicio,
                fecha=date(2026, 1, 10),
                fecha_salida=date(2026, 1, 15),
                hora=time(6, 0),
                numero_personas=2,
                nombre_cliente='Cliente 1',
                telefono_cliente='+526121111111',
                correo_cliente='c1@example.com',
                canal_origen=Reserva.CanalOrigen.WEB,
                deslinde_aceptado=True,
                estado=Reserva.Estado.PAGADA,
            )
            self.reserva_pagada_2 = Reserva.objects.create(
                empresa=self.empresa,
                servicio=self.servicio,
                fecha=date(2026, 1, 12),
                fecha_salida=date(2026, 1, 18),
                hora=time(6, 0),
                numero_personas=2,
                nombre_cliente='Cliente 2',
                telefono_cliente='+526122222222',
                correo_cliente='c2@example.com',
                canal_origen=Reserva.CanalOrigen.WEB,
                deslinde_aceptado=True,
                estado=Reserva.Estado.PAGADA,
            )
            self.reserva_cancelada = Reserva.objects.create(
                empresa=self.empresa,
                servicio=self.servicio,
                fecha=date(2026, 1, 10),
                fecha_salida=date(2026, 1, 15),
                hora=time(6, 0),
                numero_personas=2,
                nombre_cliente='Cliente Cancelado',
                telefono_cliente='+526123333333',
                correo_cliente='cc@example.com',
                canal_origen=Reserva.CanalOrigen.WEB,
                deslinde_aceptado=True,
                estado=Reserva.Estado.CANCELADA,
            )

    def test_constraint_rechaza_dos_ocupaciones_traslapadas_del_mismo_recurso(self):
        with scope.con_empresa(self.empresa):
            ReservaOcupacion.objects.create(
                empresa=self.empresa,
                reserva=self.reserva_pagada_1,
                recurso=self.recurso,
                fecha_inicio=date(2026, 1, 10),
                fecha_fin=date(2026, 1, 15),
                ocupa_cupo=True,
            )
            with transaction.atomic():
                with self.assertRaises(IntegrityError):
                    ReservaOcupacion.objects.create(
                        empresa=self.empresa,
                        reserva=self.reserva_pagada_2,
                        recurso=self.recurso,
                        fecha_inicio=date(2026, 1, 12),
                        fecha_fin=date(2026, 1, 18),
                        ocupa_cupo=True,
                    )

    def test_checkout_el_mismo_dia_se_permite(self):
        with scope.con_empresa(self.empresa):
            oc1 = ReservaOcupacion.objects.create(
                empresa=self.empresa,
                reserva=self.reserva_pagada_1,
                recurso=self.recurso,
                fecha_inicio=date(2026, 1, 10),
                fecha_fin=date(2026, 1, 15),
                ocupa_cupo=True,
            )
            oc2 = ReservaOcupacion.objects.create(
                empresa=self.empresa,
                reserva=self.reserva_pagada_2,
                recurso=self.recurso,
                fecha_inicio=date(2026, 1, 15),
                fecha_fin=date(2026, 1, 20),
                ocupa_cupo=True,
            )
            self.assertIsNotNone(oc1.pk)
            self.assertIsNotNone(oc2.pk)

    def test_ocupacion_de_reserva_cancelada_no_estorba(self):
        with scope.con_empresa(self.empresa):
            oc_cancelada = ReservaOcupacion.objects.create(
                empresa=self.empresa,
                reserva=self.reserva_cancelada,
                recurso=self.recurso,
                fecha_inicio=date(2026, 1, 10),
                fecha_fin=date(2026, 1, 15),
                ocupa_cupo=False,
            )
            oc_activa = ReservaOcupacion.objects.create(
                empresa=self.empresa,
                reserva=self.reserva_pagada_2,
                recurso=self.recurso,
                fecha_inicio=date(2026, 1, 12),
                fecha_fin=date(2026, 1, 18),
                ocupa_cupo=True,
            )
            self.assertIsNotNone(oc_cancelada.pk)
            self.assertIsNotNone(oc_activa.pk)


class ReservaCleanHospedajeYPaqueteTests(OperadorTestCase):
    """Pruebas para Reserva.clean() en ramas de hospedaje y paquete (Tarea 5.5)."""

    def setUp(self):
        from apps.fleet.models import Paquete, PaqueteServicio
        from apps.bookings.models import ReservaPaqueteServicioRemovido

        self.sede = Sede.objects.create(nombre='Sede Loreto Cupo', slug='loreto-cupo')
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Tours & Cabañas', slug='tours-cabanas')

        self.srv_pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca-55', tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia', precio_base=Decimal('3000'),
        )
        self.srv_hospedaje = Servicio.objects.create(
            empresa=self.empresa, nombre='Cabaña', slug='cabana-55', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', precio_base=Decimal('1500'),
        )
        self.recurso = Recurso.objects.create(
            empresa=self.empresa, servicio=self.srv_hospedaje,
            nombre='Cabaña Única', capacidad_maxima=4, activo=True,
        )

        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa,
            nombre='Pack Pesca Hospedaje', slug='pack-pesca-hospedaje',
            precio_ancla=Decimal('4500'),
        )
        self.ps1 = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.srv_pesca, orden=1, removible=False)
        self.ps2 = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.srv_hospedaje, orden=2, removible=True)

    def test_reserva_hospedaje_sin_disponibilidad_falla_full_clean(self):
        # Ocupamos la cabaña en esas fechas con una reserva pagada
        r_existente = Reserva.objects.create(
            empresa=self.empresa, servicio=self.srv_hospedaje,
            fecha=date(2026, 12, 1), fecha_salida=date(2026, 12, 5),
            hora=time(6, 0), numero_personas=2, nombre_cliente='A', telefono_cliente='+526121234567',
            correo_cliente='a@a.com', estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
        )
        ReservaOcupacion.objects.create(
            reserva=r_existente, recurso=self.recurso, empresa=self.empresa,
            fecha_inicio=date(2026, 12, 1), fecha_fin=date(2026, 12, 5), ocupa_cupo=True,
        )

        # Nueva reserva intentando las mismas fechas en estado PAGADA
        r_nueva = Reserva(
            empresa=self.empresa, servicio=self.srv_hospedaje,
            fecha=date(2026, 12, 2), fecha_salida=date(2026, 12, 4),
            hora=time(6, 0), numero_personas=2, nombre_cliente='B', telefono_cliente='+526121234567',
            correo_cliente='b@b.com', estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            r_nueva.full_clean()
        self.assertIn('fecha', ctx.exception.message_dict)

    def test_reserva_hospedaje_con_disponibilidad_pasa_full_clean(self):
        r_nueva = Reserva(
            empresa=self.empresa, servicio=self.srv_hospedaje,
            fecha=date(2026, 12, 10), fecha_salida=date(2026, 12, 15),
            hora=time(6, 0), numero_personas=2, nombre_cliente='B', telefono_cliente='+526121234567',
            correo_cliente='b@b.com', estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
        )
        r_nueva.full_clean()  # No debe lanzar ValidationError

    def test_reserva_paquete_con_componente_hospedaje_sin_cupo_falla_full_clean(self):
        # Cabaña ocupada
        r_existente = Reserva.objects.create(
            empresa=self.empresa, servicio=self.srv_hospedaje,
            fecha=date(2026, 12, 1), fecha_salida=date(2026, 12, 5),
            hora=time(6, 0), numero_personas=2, nombre_cliente='A', telefono_cliente='+526121234567',
            correo_cliente='a@a.com', estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
        )
        ReservaOcupacion.objects.create(
            reserva=r_existente, recurso=self.recurso, empresa=self.empresa,
            fecha_inicio=date(2026, 12, 1), fecha_fin=date(2026, 12, 5), ocupa_cupo=True,
        )
        from apps.testing import crear_flota
        crear_flota(self.empresa)

        r_paquete = Reserva(
            empresa=self.empresa, paquete=self.paquete,
            fecha=date(2026, 12, 2), fecha_salida=date(2026, 12, 4),
            hora=time(6, 0), numero_personas=2, nombre_cliente='C', telefono_cliente='+526121234567',
            correo_cliente='c@c.com', estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
        )
        with self.assertRaises(ValidationError) as ctx:
            r_paquete.full_clean()
        self.assertIn('fecha', ctx.exception.message_dict)

    def test_reserva_paquete_valida_cupo_de_todos_sus_componentes(self):
        # Cabaña ocupada
        r_existente = Reserva.objects.create(
            empresa=self.empresa, servicio=self.srv_hospedaje,
            fecha=date(2026, 12, 1), fecha_salida=date(2026, 12, 5),
            hora=time(6, 0), numero_personas=2, nombre_cliente='A', telefono_cliente='+526121234567',
            correo_cliente='a@a.com', estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
        )
        ReservaOcupacion.objects.create(
            reserva=r_existente, recurso=self.recurso, empresa=self.empresa,
            fecha_inicio=date(2026, 12, 1), fecha_fin=date(2026, 12, 5), ocupa_cupo=True,
        )

        # Flota para pesca
        from apps.testing import crear_flota
        crear_flota(self.empresa)

        # Reserva de paquete intentando saltarse cabaña
        r_paquete = Reserva.objects.create(
            empresa=self.empresa, paquete=self.paquete,
            fecha=date(2026, 12, 2),
            hora=time(6, 0), numero_personas=2, nombre_cliente='C', telefono_cliente='+526121234567',
            correo_cliente='c@c.com', estado=Reserva.Estado.PENDIENTE_PAGO,
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
        )
        from apps.bookings.models import ReservaPaqueteServicioRemovido
        ReservaPaqueteServicioRemovido.objects.create(reserva=r_paquete, servicio=self.srv_hospedaje)

        r_paquete.estado = Reserva.Estado.PAGADA
        with self.assertRaises(ValidationError) as ctx:
            r_paquete.full_clean()
        self.assertIn('fecha', ctx.exception.message_dict)

    def test_reservar_cupo_al_confirmar_reserva_todos_los_componentes(self):
        from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar
        from apps.testing import crear_flota
        crear_flota(self.empresa)
        r_paquete = Reserva.objects.create(
            empresa=self.empresa, paquete=self.paquete,
            fecha=date(2026, 12, 10), fecha_salida=date(2026, 12, 12),
            hora=time(6, 0), numero_personas=2, nombre_cliente='C', telefono_cliente='+526121234567',
            correo_cliente='c@c.com', estado=Reserva.Estado.PENDIENTE_PAGO,
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
        )
        reservar_cupo_al_confirmar(r_paquete)
        componentes = set(r_paquete.componentes.values_list('servicio_id', flat=True))
        self.assertEqual(len(componentes), 2)
        self.assertIn(self.srv_pesca.pk, componentes)
        self.assertIn(self.srv_hospedaje.pk, componentes)



class CancelacionLiberaCupoTests(OperadorTestCase):
    """Pruebas de que cancelar una reserva libera ocupaciones y componentes (Tarea 6.4)."""

    def setUp(self):
        super().setUp()
        self.sede = Sede.objects.create(nombre='Sede Loreto', slug='sede-loreto')
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Hotel y Pesca Loreto', slug='loreto-hotel-pesca')
        self.srv_hospedaje = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Habitación Vista Mar',
            slug='hab-vista-mar',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            precio_base=Decimal('2000.00'),
        )
        self.recurso = Recurso.objects.create(
            empresa=self.empresa,
            servicio=self.srv_hospedaje,
            nombre='Habitación 1',
            capacidad_maxima=2,
        )

    def test_cancelar_hospedaje_libera_ocupacion_y_permite_otra_reserva(self):
        r1 = Reserva.objects.create(
            empresa=self.empresa,
            servicio=self.srv_hospedaje,
            fecha=date(2026, 11, 1),
            fecha_salida=date(2026, 11, 5),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Cliente Uno',
            telefono_cliente='+526121234567',
            correo_cliente='uno@example.com',
            estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
        )
        oc1 = ReservaOcupacion.objects.create(
            reserva=r1,
            recurso=self.recurso,
            empresa=self.empresa,
            fecha_inicio=r1.fecha,
            fecha_fin=r1.fecha_salida,
            ocupa_cupo=True,
        )

        # Una segunda reserva en las mismas fechas falla validación de disponibilidad
        r2 = Reserva(
            empresa=self.empresa,
            servicio=self.srv_hospedaje,
            fecha=date(2026, 11, 2),
            fecha_salida=date(2026, 11, 4),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Cliente Dos',
            telefono_cliente='+526121234568',
            correo_cliente='dos@example.com',
            estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
        )
        with self.assertRaises(ValidationError):
            r2.full_clean()

        # Acción de cancelar (simulando cancelar_por_mal_clima en admin)
        from django.contrib.auth import get_user_model
        from apps.bookings.admin import ReservaAdmin
        from django.contrib.admin.sites import AdminSite
        admin = ReservaAdmin(Reserva, AdminSite())
        request = mock.Mock()
        request.user = get_user_model().objects.create_user(username='admin_test')
        admin.cancelar_por_mal_clima(request, Reserva.objects.filter(pk=r1.pk))

        oc1.refresh_from_db()
        self.assertFalse(oc1.ocupa_cupo)

        # Ahora r2 pasa validación y puede crearse
        r2.full_clean()
        r2.save()
        self.assertEqual(r2.estado, Reserva.Estado.PAGADA)

    def test_cancelar_paquete_libera_ocupacion_y_marca_componentes_liberados(self):
        s_pesca = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Pesca en Panga',
            slug='pesca-panga',
            tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia',
            precio_base=Decimal('3000.00'),
        )
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Pesca y Cabaña',
            slug='pesca-cabana',
            precio_ancla=Decimal('5000.00'),
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=self.srv_hospedaje, orden=1)
        PaqueteServicio.objects.create(paquete=paquete, servicio=s_pesca, orden=2)

        r = Reserva.objects.create(
            empresa=self.empresa,
            paquete=paquete,
            fecha=date(2026, 11, 10),
            fecha_salida=date(2026, 11, 12),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Cliente Paquete',
            telefono_cliente='+526121234569',
            correo_cliente='paq@example.com',
            estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True,
        )
        oc = ReservaOcupacion.objects.create(
            reserva=r,
            recurso=self.recurso,
            empresa=self.empresa,
            fecha_inicio=r.fecha,
            fecha_fin=r.fecha_salida,
            ocupa_cupo=True,
        )
        comp_hotel = ReservaPaqueteComponente.objects.create(
            reserva=r,
            servicio=self.srv_hospedaje,
            empresa=self.empresa,
            estado_cupo=ReservaPaqueteComponente.EstadoCupo.OK,
        )
        comp_pesca = ReservaPaqueteComponente.objects.create(
            reserva=r,
            servicio=s_pesca,
            empresa=self.empresa,
            estado_cupo=ReservaPaqueteComponente.EstadoCupo.OK,
        )

        r.estado = Reserva.Estado.CANCELADA
        r.motivo_cancelacion = 'Mal clima'
        r.full_clean()
        r.save()

        oc.refresh_from_db()
        comp_hotel.refresh_from_db()
        comp_pesca.refresh_from_db()

        self.assertFalse(oc.ocupa_cupo)
        self.assertEqual(comp_hotel.estado_cupo, ReservaPaqueteComponente.EstadoCupo.LIBERADO)
        self.assertEqual(comp_pesca.estado_cupo, ReservaPaqueteComponente.EstadoCupo.LIBERADO)



