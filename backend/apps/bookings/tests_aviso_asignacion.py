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

from apps.fleet.models import Capitan, Embarcacion
from apps.testing import EmpresaTestCase

from .models import Reserva

ENVIO = 'apps.bookings.signals.enviar_correo_asignacion'


class AvisoDeAsignacionTests(EmpresaTestCase):
    def setUp(self):
        self.embarcacion = Embarcacion.objects.create(
            empresa=self.empresa, nombre='Dona Chuy',
            clase=Embarcacion.Clase.CHICA, capacidad_maxima=6,
        )
        self.capitan = Capitan.objects.create(
            empresa=self.empresa, nombre='Ramon Geraldo', telefono='+5216129876543',
        )
        self.reserva = Reserva.objects.create(
            empresa=self.empresa,
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
            # _mandar (B16) re-resuelve la Reserva bajo su propio con_empresa y
            # sella aviso_asignacion_enviado_en con un .update() -- no toca este
            # objeto en memoria. Sin refrescar, self.reserva seguiria creyendo
            # que nunca se mando (mismo motivo que la prueba de regresion N1 de
            # abajo hace el mismo refresh: asi es como llegaria una edicion real,
            # en una peticion nueva que vuelve a leer de la base).
            self.reserva.refresh_from_db()
            self.reserva.numero_personas = 3
            with self.captureOnCommitCallbacks(execute=True):
                self.reserva.save()

        enviar.assert_not_called()

    def test_cambiar_de_capitan_no_reenvia(self):
        """Decision del negocio: el cambio lo avisa la vendedora a mano, porque
        sabe si al cliente le importa y si ya esta en el muelle."""
        with mock.patch(ENVIO, return_value=True):
            self._asignar()

        otro = Capitan.objects.create(
            empresa=self.empresa, nombre='Luis Mendoza', telefono='+5216125554433')
        with mock.patch(ENVIO, return_value=True) as enviar:
            self.reserva.refresh_from_db()
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

    def test_el_correo_se_manda_bajo_rls_aunque_el_alcance_de_la_vista_ya_haya_cerrado(self):
        """Regresión directa de la Revisión 4, N1: `notificar_reserva_pagada`/el
        aviso de asignación corren en `transaction.on_commit`, fuera del `with
        scope.con_empresa(...)` que los encoló — antes de la corrección, bajo RLS
        el `.update()` que sella `aviso_asignacion_enviado_en` afectaba 0 filas y
        el correo se reenviaba en cada edición, para siempre."""
        with mock.patch(ENVIO, return_value=True):
            self._asignar()
        primer_envio = Reserva.objects.get(pk=self.reserva.pk).aviso_asignacion_enviado_en
        self.assertIsNotNone(primer_envio)

        # Simula exactamente lo que el bug dejaba pasar: guardar la reserva otra
        # vez con el mismo estado, fuera de cualquier alcance nuevo abierto a mano.
        with mock.patch(ENVIO, return_value=True) as enviar:
            self.reserva.refresh_from_db()
            self.reserva.numero_personas = 3
            with self.captureOnCommitCallbacks(execute=True):
                self.reserva.save()

        enviar.assert_not_called()
        self.assertEqual(
            Reserva.objects.get(pk=self.reserva.pk).aviso_asignacion_enviado_en, primer_envio,
        )
