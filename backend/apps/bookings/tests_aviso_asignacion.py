"""El aviso automatico de "ya sabemos con quien sales".

El correo de confirmacion sale cuando entra el pago, y en ese momento todavia no
hay panga ni capitan: se reparten despues, a mano, desde la agenda del admin.
Este disparador cierra ese hueco sin que nadie se acuerde de mandarlo.

Lo que se protege aqui es sobre todo que NO se mande de mas: el cliente recibe
este correo una vez, y guardar la reserva otras diez veces desde el admin no le
llena el buzon.
"""
from datetime import date, time, timedelta
from unittest import mock

from django.test import TestCase

from apps.fleet.models import Capitan, Embarcacion

from .models import Reserva

ENVIO = 'apps.bookings.signals.enviar_correo_asignacion'


class AvisoDeAsignacionTests(TestCase):
    def setUp(self):
        self.embarcacion = Embarcacion.objects.create(
            nombre='Dona Chuy', clase=Embarcacion.Clase.CHICA, capacidad_maxima=6
        )
        self.capitan = Capitan.objects.create(nombre='Ramon Geraldo', telefono='+5216129876543')
        self.reserva = Reserva.objects.create(
            fecha=date.today() + timedelta(days=10),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Ana Ruiz',
            telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com',
            moneda='MXN',
            deslinde_aceptado=True,
            deslinde_nombre='Ana Ruiz',
            estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB,
        )

    def _asignar(self, embarcacion=True, capitan=True):
        if embarcacion:
            self.reserva.embarcacion = self.embarcacion
        if capitan:
            self.reserva.capitan = self.capitan
        self.reserva.estado = Reserva.Estado.ASIGNADA
        with self.captureOnCommitCallbacks(execute=True):
            self.reserva.save()

    def test_al_quedar_panga_y_capitan_se_manda_el_correo(self):
        with mock.patch(ENVIO, return_value=True) as enviar:
            self._asignar()

        enviar.assert_called_once_with(self.reserva)
        self.reserva.refresh_from_db()
        self.assertIsNotNone(self.reserva.aviso_asignacion_enviado_en)

    def test_con_panga_pero_sin_capitan_no_se_manda(self):
        """Poner solo la panga ya deja la reserva en `asignada`, y el admin la
        marca "SIN CAPITAN" en rojo. Mandar el correo ahi seria avisarle al
        cliente de un capitan que todavia no existe."""
        with mock.patch(ENVIO, return_value=True) as enviar:
            self._asignar(capitan=False)

        enviar.assert_not_called()

    def test_guardar_de_nuevo_no_reenvia(self):
        with mock.patch(ENVIO, return_value=True):
            self._asignar()

        with mock.patch(ENVIO, return_value=True) as enviar:
            self.reserva.numero_personas = 3
            with self.captureOnCommitCallbacks(execute=True):
                self.reserva.save()

        enviar.assert_not_called()

    def test_cambiar_de_capitan_no_reenvia(self):
        """Decision del negocio: el cambio lo avisa la vendedora a mano, porque
        sabe si al cliente le importa y si ya esta en el muelle."""
        with mock.patch(ENVIO, return_value=True):
            self._asignar()

        otro = Capitan.objects.create(nombre='Luis Mendoza', telefono='+5216125554433')
        with mock.patch(ENVIO, return_value=True) as enviar:
            self.reserva.capitan = otro
            with self.captureOnCommitCallbacks(execute=True):
                self.reserva.save()

        enviar.assert_not_called()

    def test_una_reserva_cancelada_no_recibe_aviso(self):
        self.reserva.estado = Reserva.Estado.CANCELADA
        with mock.patch(ENVIO, return_value=True) as enviar:
            self.reserva.embarcacion = self.embarcacion
            self.reserva.capitan = self.capitan
            with self.captureOnCommitCallbacks(execute=True):
                self.reserva.save()

        enviar.assert_not_called()

    def test_un_viaje_que_ya_paso_no_recibe_aviso(self):
        """Reasignar historico para cuadrar la contabilidad es normal; mandarle
        al cliente el capitan de un viaje de hace un mes, no."""
        Reserva.objects.filter(pk=self.reserva.pk).update(fecha=date.today() - timedelta(days=3))
        self.reserva.refresh_from_db()

        with mock.patch(ENVIO, return_value=True) as enviar:
            self._asignar()

        enviar.assert_not_called()

    def test_si_el_correo_falla_no_se_marca_como_enviado(self):
        """Asi el siguiente guardado lo reintenta en vez de darlo por hecho."""
        with mock.patch(ENVIO, return_value=False):
            self._asignar()

        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.aviso_asignacion_enviado_en)

    def test_guardar_la_reserva_no_truena_si_el_correo_lanza(self):
        """El reparto de la agenda no se cae porque Resend este mal."""
        with mock.patch(ENVIO, side_effect=RuntimeError('boom')):
            self._asignar()

        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.capitan, self.capitan)
