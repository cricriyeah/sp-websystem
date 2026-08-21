"""Disponibilidad de un rango de fechas, para pintar el calendario en gris.

El calendario del hero y el del checkout necesitan saber que dias estan llenos
**antes** de que el cliente toque uno. Preguntar dia por dia ya mato una vez a
este sistema (ver proxima_fecha_disponible): con el limite de 60/min por IP, un
mes son 30 peticiones y dos meses un 429 silencioso.
"""
from datetime import date, time, timedelta

from django.test import TestCase

from apps.fleet.models import EmbarcacionNoDisponible
from apps.testing import ApiTestCase, crear_flota

from .models import (
    MOTIVO_LLENO,
    MOTIVO_SIN_PANGA,
    CupoDiario,
    Reserva,
    disponibilidad_por_fecha,
)


def crear_reserva(fecha, personas):
    """Reserva que ocupa cupo, sin pasar por la validacion del checkout."""
    return Reserva.objects.create(
        fecha=fecha,
        hora=time(6, 0),
        numero_personas=personas,
        nombre_cliente='Cliente',
        telefono_cliente='+5216121234567',
        correo_cliente='cliente@example.com',
        moneda='MXN',
        canal_origen=Reserva.CanalOrigen.WHATSAPP,
        estado=Reserva.Estado.PAGADA,
    )


class DisponibilidadPorFechaTests(TestCase):
    """El calculo puro, sin pasar por HTTP."""

    def setUp(self):
        crear_flota()
        self.lunes = date(2026, 9, 7)

    def test_devuelve_una_entrada_por_dia_del_rango(self):
        mapa = disponibilidad_por_fecha(self.lunes, self.lunes + timedelta(days=6), personas=2)
        self.assertEqual(len(mapa), 7)
        self.assertEqual(min(mapa), self.lunes)
        self.assertEqual(max(mapa), self.lunes + timedelta(days=6))

    def test_un_dia_vacio_esta_disponible(self):
        mapa = disponibilidad_por_fecha(self.lunes, self.lunes, personas=2)
        self.assertIsNone(mapa[self.lunes])

    def test_un_dia_cerrado_por_cupo_diario_sale_lleno(self):
        CupoDiario.objects.create(fecha=self.lunes, cupo_maximo=0)
        mapa = disponibilidad_por_fecha(self.lunes, self.lunes, personas=1)
        self.assertEqual(mapa[self.lunes], MOTIVO_LLENO)

    def test_un_dia_sin_panga_grande_sale_sin_panga_para_un_grupo_grande(self):
        """La flota tiene dos pangas de 5. Ocupadas las dos, un grupo de 4 no cabe
        aunque queden pangas chicas libres y el dia no este lleno."""
        crear_reserva(self.lunes, 5)
        crear_reserva(self.lunes, 5)
        mapa = disponibilidad_por_fecha(self.lunes, self.lunes, personas=4)
        self.assertEqual(mapa[self.lunes], MOTIVO_SIN_PANGA)

    def test_ese_mismo_dia_si_admite_un_grupo_chico(self):
        """El gris depende del tamano del grupo: mismo dia, distinta respuesta."""
        crear_reserva(self.lunes, 5)
        crear_reserva(self.lunes, 5)
        mapa = disponibilidad_por_fecha(self.lunes, self.lunes, personas=2)
        self.assertIsNone(mapa[self.lunes])

    def test_una_panga_fuera_de_servicio_reduce_la_capacidad(self):
        grandes = [e for e in crear_flota() if e.capacidad_maxima == 5]
        for panga in grandes:
            EmbarcacionNoDisponible.objects.create(fecha=self.lunes, embarcacion=panga)

        mapa = disponibilidad_por_fecha(self.lunes, self.lunes, personas=5)
        self.assertEqual(mapa[self.lunes], MOTIVO_SIN_PANGA)

    def test_las_reservas_canceladas_no_ocupan(self):
        reserva = crear_reserva(self.lunes, 5)
        Reserva.objects.filter(pk=reserva.pk).update(estado=Reserva.Estado.CANCELADA)
        mapa = disponibilidad_por_fecha(self.lunes, self.lunes, personas=5)
        self.assertIsNone(mapa[self.lunes])

    def test_el_costo_no_crece_con_el_tamano_del_rango(self):
        """El punto entero de este endpoint. Cuatro consultas para un dia y las
        mismas cuatro para dos meses; si esto se rompe, volvemos al 429."""
        with self.assertNumQueries(4):
            disponibilidad_por_fecha(self.lunes, self.lunes, personas=2)

        with self.assertNumQueries(4):
            disponibilidad_por_fecha(self.lunes, self.lunes + timedelta(days=61), personas=2)


class CupoRangoApiTests(ApiTestCase):
    """El endpoint HTTP."""

    url = '/api/cupo/rango/'

    def setUp(self):
        crear_flota()
        self.lunes = date(2026, 9, 7)

    def pedir(self, **params):
        datos = {'desde': str(self.lunes), 'hasta': str(self.lunes + timedelta(days=6))}
        datos.update({k: str(v) for k, v in params.items()})
        return self.client.get(self.url, datos)

    def test_responde_un_motivo_por_dia(self):
        response = self.pedir(personas=2)
        self.assertEqual(response.status_code, 200)

        dias = response.json()['dias']
        self.assertEqual(len(dias), 7)
        self.assertIsNone(dias[str(self.lunes)])

    def test_marca_el_dia_lleno_con_su_motivo(self):
        CupoDiario.objects.create(fecha=self.lunes, cupo_maximo=0)
        dias = self.pedir(personas=2).json()['dias']
        self.assertEqual(dias[str(self.lunes)], MOTIVO_LLENO)

    def test_personas_es_opcional_y_no_cambia_lo_que_ya_respondia(self):
        self.assertEqual(self.pedir().status_code, 200)

    def test_rechaza_fechas_mal_formadas(self):
        self.assertEqual(self.pedir(desde='ayer').status_code, 400)

    def test_rechaza_un_rango_al_reves(self):
        response = self.client.get(
            self.url, {'desde': str(self.lunes), 'hasta': str(self.lunes - timedelta(days=1))}
        )
        self.assertEqual(response.status_code, 400)

    def test_rechaza_un_rango_mas_largo_que_el_tope(self):
        """Sin tope, una sola peticion puede pedir diez anios y barrer la base."""
        response = self.client.get(
            self.url, {'desde': str(self.lunes), 'hasta': str(self.lunes + timedelta(days=400))}
        )
        self.assertEqual(response.status_code, 400)

    def test_rechaza_un_numero_de_personas_fuera_de_rango(self):
        self.assertEqual(self.pedir(personas=99).status_code, 400)
