from datetime import date, time

from apps.bookings.cupo import (
    ContextoCupo,
    ModoOcupacion,
    PorNoche,
    PorRecursoDia,
    obtener_contexto_cupo,
    obtener_contexto_rango,
    obtener_estrategia,
    registrar_estrategia,
)
from apps.bookings.models import (
    CUPO_MAXIMO_DEFAULT,
    CupoDiario,
    Reserva,
)
from apps.fleet.models import Embarcacion
from apps.testing import EmpresaTestCase, crear_servicio_pesca


class CupoAdaptadorYRegistroTests(EmpresaTestCase):
    """Pruebas de integración del adaptador de datos ORM y el registro de estrategias."""

    def setUp(self):
        super().setUp()
        self.fecha = date(2026, 9, 28)
        self.hora = time(6, 0)
        # Crear pangas en la flota con los campos correctos del modelo Embarcacion
        self.panga1 = Embarcacion.objects.create(
            nombre='Panga Uno',
            clase=Embarcacion.Clase.GRANDE,
            capacidad_maxima=5,
            activa=True,
            empresa=self.empresa,
        )
        self.panga2 = Embarcacion.objects.create(
            nombre='Panga Dos',
            clase=Embarcacion.Clase.CHICA,
            capacidad_maxima=4,
            activa=True,
            empresa=self.empresa,
        )

    def test_obtener_contexto_cupo_dia_sin_reservas(self):
        ctx = obtener_contexto_cupo(self.fecha, self.empresa)
        self.assertEqual(ctx.grupos, [])
        self.assertEqual(ctx.capacidades, [5, 4])
        self.assertEqual(ctx.tope, CUPO_MAXIMO_DEFAULT)

    def test_obtener_contexto_cupo_con_reservas_y_tope(self):
        # Override de tope
        CupoDiario.objects.create(fecha=self.fecha, cupo_maximo=1, empresa=self.empresa)

        reserva = Reserva.objects.create(
            fecha=self.fecha,
            hora=self.hora,
            numero_personas=4,
            nombre_cliente='Juan',
            correo_cliente='juan@test.com',
            telefono_cliente='1234567890',
            estado='pagada',
            empresa=self.empresa,
            servicio=crear_servicio_pesca(self.empresa),
        )

        ctx = obtener_contexto_cupo(self.fecha, self.empresa)
        self.assertEqual(ctx.grupos, [4])
        self.assertEqual(ctx.tope, 1)

        # Con excluir_pk
        ctx_excluido = obtener_contexto_cupo(self.fecha, self.empresa, excluir_pk=reserva.pk)
        self.assertEqual(ctx_excluido.grupos, [])

    def test_obtener_contexto_rango(self):
        f_desde = date(2026, 9, 28)
        f_hasta = date(2026, 9, 29)

        Reserva.objects.create(
            fecha=f_desde,
            hora=self.hora,
            numero_personas=3,
            nombre_cliente='Pedro',
            correo_cliente='pedro@test.com',
            telefono_cliente='1234567890',
            estado='pagada',
            empresa=self.empresa,
            servicio=crear_servicio_pesca(self.empresa),
        )

        ctx_rango = obtener_contexto_rango(f_desde, f_hasta, self.empresa)
        self.assertEqual(len(ctx_rango.fechas), 2)
        self.assertEqual(ctx_rango.grupos_por_fecha[f_desde], [3])
        self.assertEqual(ctx_rango.grupos_por_fecha.get(f_hasta, []), [])
        self.assertEqual(ctx_rango.capacidades_por_fecha[f_desde], [5, 4])

    def test_registro_estrategias(self):
        # 'por_recurso_dia' devuelve PorRecursoDia exclusivo
        est_recurso = obtener_estrategia('por_recurso_dia')
        self.assertIsInstance(est_recurso, PorRecursoDia)
        self.assertEqual(est_recurso.modo_predeterminado, ModoOcupacion.EXCLUSIVO)

        # 'por_noche' devuelve PorNoche
        est_noche = obtener_estrategia('por_noche')
        self.assertIsInstance(est_noche, PorNoche)

        # Servicio desconocido cae al default ('por_recurso_dia')
        est_desconocido = obtener_estrategia('servicio_fantasma')
        self.assertEqual(est_desconocido, obtener_estrategia('por_recurso_dia'))

        # Registro dinámico
        nueva_est = PorRecursoDia(modo=ModoOcupacion.COMPARTIDO)
        registrar_estrategia('tour_snorkeling', nueva_est)
        self.assertEqual(obtener_estrategia('tour_snorkeling'), nueva_est)
