"""Pruebas para el modelo ReservaOcupacion y soporte de estadías en Reserva."""

from datetime import date, time, timedelta
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase

from apps.fleet.models import Recurso, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase
from apps.bookings.models import Reserva, ReservaOcupacion


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


