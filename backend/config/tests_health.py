"""Pruebas de la sonda de salud.

Lo que se protege aqui es la leccion de F-17: el `healthCheckPath` de Render no
debe depender de datos de negocio, o el primer deploy contra una base vacia se
cancela solo. Ver config/health.py.
"""
from unittest import mock

from django.test import TestCase

from apps.fleet.models import Tarifa


class HealthzTests(TestCase):
    def test_responde_200_con_la_base_vacia(self):
        """El caso que rompia el deploy: base recien migrada, cero filas.

        /api/tarifa/ contesta 503 aqui — por eso no sirve como health check.
        """
        self.assertFalse(Tarifa.objects.exists())

        respuesta = self.client.get('/healthz')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {'status': 'ok', 'database': 'ok'})

    def test_la_ruta_de_tarifa_si_falla_sin_datos(self):
        """Deja constancia de por que /api/tarifa/ no puede ser el health check.

        Si algun dia esta ruta deja de dar 503 sin tarifa, este test falla y
        obliga a releer la decision en vez de asumirla.
        """
        self.assertEqual(self.client.get('/api/tarifa/').status_code, 503)

    def test_reporta_503_si_la_base_no_contesta(self):
        """Un deploy con credenciales mal puestas debe morir en el health check,
        que es cuando todavia se puede revertir sin que nadie lo note."""
        with mock.patch('config.health.connection') as conexion:
            conexion.cursor.side_effect = Exception('could not connect to server')

            respuesta = self.client.get('/healthz')

        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json()['database'], 'unreachable')

    def test_el_503_no_publica_los_datos_de_la_conexion(self):
        """La ruta es publica y sin autenticacion. Los errores de psycopg traen
        el host, el puerto y el usuario de la base: eso va al log, nunca al
        cuerpo de la respuesta."""
        detalle = (
            'connection to server at "db.abcdefgh.supabase.co" (10.0.0.1), port 5432 '
            'failed: FATAL: password authentication failed for user "postgres"'
        )
        with mock.patch('config.health.connection') as conexion:
            conexion.cursor.side_effect = Exception(detalle)

            with self.assertLogs('config.health', level='ERROR') as registro:
                respuesta = self.client.get('/healthz')

        cuerpo = respuesta.content.decode()
        for filtracion in ('supabase.co', '5432', 'postgres', '10.0.0.1'):
            self.assertNotIn(filtracion, cuerpo)

        # Pero quien si puede leerlo —el log de Render— lo tiene completo.
        self.assertIn('supabase.co', registro.output[0])

    def test_no_depende_de_servicios_externos(self):
        """Que Stripe o Resend esten caidos no significa que esta version deba
        salir de servicio: la sonda no debe llamarlos."""
        with mock.patch('requests.post') as post, mock.patch('stripe.PaymentIntent.retrieve') as intent:
            self.assertEqual(self.client.get('/healthz').status_code, 200)

        post.assert_not_called()
        intent.assert_not_called()
