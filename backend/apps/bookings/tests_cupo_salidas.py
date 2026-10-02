"""El cupo cuenta cada salida en su día y no duplica el primer día."""
from datetime import timedelta

from apps.bookings.cupo.adaptador import obtener_contexto_cupo, obtener_contexto_rango
from apps.bookings.models import Reserva, evaluar_cupo
from apps.bookings.tests_salidas import SalidasBase
from apps.fleet.models import Embarcacion


class CupoConSalidasTests(SalidasBase):
    def dia(self, n):
        return self.inicio + timedelta(days=n)

    def test_cada_dia_de_mar_cuenta_un_grupo(self):
        self.reserva_con_salidas(personas=2)
        for n in (1, 2, 3, 4):
            self.assertEqual(obtener_contexto_cupo(self.dia(n), self.empresa).grupos, [2], f'día {n}')
        self.assertEqual(obtener_contexto_cupo(self.dia(5), self.empresa).grupos, [])

    def test_el_primer_dia_no_se_cuenta_dos_veces(self):
        self.reserva_con_salidas(personas=2)
        self.assertEqual(len(obtener_contexto_cupo(self.dia(1), self.empresa).grupos), 1)

    def test_una_reserva_cancelada_no_cuenta(self):
        self.reserva_con_salidas(estado=Reserva.Estado.CANCELADA)
        self.assertEqual(obtener_contexto_cupo(self.dia(2), self.empresa).grupos, [])

    def test_excluir_pk_excluye_tambien_sus_salidas(self):
        reserva = self.reserva_con_salidas()
        self.assertEqual(obtener_contexto_cupo(self.dia(3), self.empresa, excluir_pk=reserva.pk).grupos, [])

    def test_el_rango_cuenta_las_salidas(self):
        self.reserva_con_salidas(personas=3)
        ctx = obtener_contexto_rango(self.dia(0), self.dia(6), self.empresa)
        self.assertEqual(ctx.grupos_por_fecha.get(self.dia(2)), [3])
        self.assertNotIn(self.dia(5), ctx.grupos_por_fecha)

    def test_no_se_puede_vender_una_panga_ya_ocupada_un_dia_intermedio(self):
        Embarcacion.objects.create(empresa=self.empresa, nombre='Panga Unica', clase='chica', capacidad_maxima=3)
        self.reserva_con_salidas(personas=2)
        self.assertEqual(evaluar_cupo(self.dia(3), 2, self.empresa), 'sin_panga')
        self.assertIsNone(evaluar_cupo(self.dia(5), 2, self.empresa))
