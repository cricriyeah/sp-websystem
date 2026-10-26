"""El aviso en pantalla de lo que paso DESPUES de que la vista respondio (correo de asignacion, reembolsos...).

En produccion la transaccion de la peticion se confirma cuando la vista ya respondio, asi que la pantalla que guardo no
puede saber el resultado: lo trae el sondeo, con el texto de las notificaciones nuevas (`nuevas_desde`).
"""
from decimal import Decimal
from unittest import mock

from django.urls import reverse

from apps.bookings.cupo import SinCupoError
from apps.payments.services import _cancelar_sin_cupo
from apps.tenancy import scope
from apps.tenancy.models import Notificacion
from apps.tenancy.notificaciones import registrar_notificacion
from apps.testing import EmpresaTestCase

from .models import Reserva
from .tests_transferencia import NOTIFICAR, pendiente
from .transferencia import ErrorDeTransferencia, marcar_pagada_por_transferencia


class SondeoTraeElTextoDeLasNotificacionesTests(EmpresaTestCase):
    def setUp(self):
        self.client.force_login(self.crear_jefe())
        self.url = reverse('avisos_reservas_nuevas')

    def _anotar(self, nivel, texto, tipo=Notificacion.Tipo.ASIGNACION, empresa=None, **extra):
        empresa = empresa or self.empresa
        with scope.con_empresa(empresa):
            return registrar_notificacion(empresa, nivel, texto, tipo=tipo, **extra)

    def test_sin_referencia_solo_se_entrega_la_referencia_y_no_el_historial(self):
        vieja = self._anotar(Notificacion.Nivel.EXITO, 'Vieja')

        datos = self.client.get(self.url).json()

        self.assertEqual(datos['notif_ultima'], vieja.pk)
        self.assertEqual(datos['notificaciones_nuevas'], [])

    def test_con_referencia_llegan_las_nuevas_con_su_texto_y_su_motivo(self):
        base = self._anotar(Notificacion.Nivel.EXITO, 'Base')
        nueva = self._anotar(
            Notificacion.Nivel.ERROR, 'No se pudo avisar a Ana.', motivo='el proveedor de correo respondió: dominio',
            enlace_url='/admin/bookings/reserva/5/change/', enlace_texto='Ver reserva')

        datos = self.client.get(self.url, {'notif': base.pk, 'vistas': str(base.pk)}).json()

        self.assertEqual(datos['notif_ultima'], nueva.pk)
        self.assertEqual(datos['notificaciones_nuevas_total'], 1)
        item, = datos['notificaciones_nuevas']
        self.assertEqual(item['nivel'], 'error')
        self.assertEqual(item['texto'], 'No se pudo avisar a Ana.')
        self.assertIn('dominio', item['motivo'])
        self.assertEqual(item['url'], '/admin/bookings/reserva/5/change/')

    def test_lo_que_el_navegador_dice_haber_visto_no_se_repite(self):
        ultima = self._anotar(Notificacion.Nivel.EXITO, 'Visto')

        datos = self.client.get(self.url, {'notif': ultima.pk, 'vistas': str(ultima.pk)}).json()

        self.assertEqual(datos['notificaciones_nuevas'], [])
        self.assertEqual(datos['notificaciones_nuevas_total'], 0)

    def test_una_notificacion_que_se_confirma_despues_de_otra_con_pk_mayor_no_se_pierde(self):
        # El pk se asigna al insertar y no al confirmar: B (pk mayor) ya se vio, A (pk menor) se confirmo despues.
        a = self._anotar(Notificacion.Nivel.ERROR, 'Se confirmo tarde')
        b = self._anotar(Notificacion.Nivel.EXITO, 'Ya vista')

        datos = self.client.get(self.url, {'notif': b.pk, 'vistas': str(b.pk)}).json()

        self.assertEqual([n['id'] for n in datos['notificaciones_nuevas']], [a.pk])

    def test_lo_viejo_que_el_navegador_nunca_vio_no_aparece_como_nuevo(self):
        from datetime import timedelta
        from django.utils import timezone

        vieja = self._anotar(Notificacion.Nivel.EXITO, 'De hace mucho')
        Notificacion.objects.filter(pk=vieja.pk).update(creado_en=timezone.now() - timedelta(minutes=10))
        referencia = self._anotar(Notificacion.Nivel.EXITO, 'Referencia')

        datos = self.client.get(self.url, {'notif': referencia.pk, 'vistas': str(referencia.pk)}).json()

        self.assertEqual(datos['notificaciones_nuevas'], [])

    def test_sin_referencia_se_entregan_los_ids_recientes_para_marcarlos_como_vistos(self):
        a = self._anotar(Notificacion.Nivel.EXITO, 'Reciente')

        datos = self.client.get(self.url).json()

        self.assertIn(a.pk, datos['notif_recientes'])
        self.assertEqual(datos['notificaciones_nuevas'], [])

    def test_las_vistas_mal_formadas_se_ignoran(self):
        a = self._anotar(Notificacion.Nivel.EXITO, 'Base')
        nueva = self._anotar(Notificacion.Nivel.AVISO, 'Nueva')

        datos = self.client.get(self.url, {'notif': a.pk, 'vistas': f'{a.pk},x,,-1,1.5, 7 ;DROP'}).json()

        self.assertEqual([n['id'] for n in datos['notificaciones_nuevas']], [nueva.pk])

    def test_la_reserva_nueva_no_sale_dos_veces(self):
        base = self._anotar(Notificacion.Nivel.EXITO, 'Base')
        self._anotar(Notificacion.Nivel.EXITO, 'Nueva reserva pagada: Ana', tipo=Notificacion.Tipo.RESERVA_NUEVA)

        datos = self.client.get(self.url, {'notif': base.pk, 'vistas': str(base.pk)}).json()

        self.assertEqual(datos['notificaciones_nuevas'], [])

    def test_muestra_las_mas_recientes_y_cuenta_el_resto(self):
        base = self._anotar(Notificacion.Nivel.EXITO, 'Base')
        for i in range(5):
            self._anotar(Notificacion.Nivel.AVISO, f'Aviso {i}')

        datos = self.client.get(self.url, {'notif': base.pk, 'vistas': str(base.pk)}).json()

        self.assertEqual(datos['notificaciones_nuevas_total'], 5)
        self.assertEqual([n['texto'] for n in datos['notificaciones_nuevas']], ['Aviso 4', 'Aviso 3', 'Aviso 2'])

    def test_una_referencia_rota_se_trata_como_sin_referencia(self):
        self._anotar(Notificacion.Nivel.EXITO, 'Algo')

        for basura in ('abc', '-3', '1.5', ''):
            with self.subTest(basura=basura):
                datos = self.client.get(self.url, {'notif': basura}).json()
                self.assertEqual(datos['notificaciones_nuevas'], [])

    def test_sin_permiso_de_ver_notificaciones_no_llega_nada(self):
        sin_permiso = self.crear_vendedora(username='sinnotif', permisos=[])
        from django.contrib.auth.models import Permission
        sin_permiso.user_permissions.add(Permission.objects.get(codename='view_reserva'))
        self.client.force_login(sin_permiso)
        self._anotar(Notificacion.Nivel.EXITO, 'Secreta')

        datos = self.client.get(self.url, {'notif': 0}).json()

        self.assertEqual(datos['notificaciones_url'], '')
        self.assertNotIn('notificaciones_nuevas', datos)


class AnularElCobroEsLoUltimoTests(EmpresaTestCase):
    """Si algo falla antes de saldar (cupo), el intent de Stripe NO se anula: el cliente aun puede pagar con tarjeta."""

    def test_sin_cupo_no_se_toca_stripe(self):
        self.empresa.stripe_secret_key = 'sk_test_abc'
        self.empresa.save()
        reserva = pendiente(self.empresa, stripe_payment_intent_id='pi_abandonado')
        cliente = mock.Mock()
        cliente.payment_intents.retrieve.return_value = mock.Mock(status='requires_payment_method', id='pi_abandonado')

        with mock.patch('apps.bookings.transferencia.configurar_stripe', return_value=cliente), \
                mock.patch('apps.bookings.transferencia.reservar_cupo_al_confirmar', side_effect=SinCupoError('lleno')), \
                mock.patch(NOTIFICAR, return_value={}):
            with self.assertRaises(ErrorDeTransferencia):
                marcar_pagada_por_transferencia(reserva.pk, '1000', self.crear_jefe())

        cliente.payment_intents.cancel.assert_not_called()
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)


class CancelarSinCupoDejaConstanciaTests(EmpresaTestCase):
    def test_el_reembolso_automatico_por_falta_de_cupo_queda_en_el_feed(self):
        reserva = pendiente(self.empresa, nombre_cliente='Ana Ruiz')
        intent = {'id': 'pi_x', 'amount_received': 100000, 'metadata': {'reserva_id': str(reserva.pk)}}

        with scope.con_empresa(self.empresa), mock.patch('apps.payments.services.reembolsar', return_value=True):
            _cancelar_sin_cupo(reserva, intent, self.empresa)
            n = Notificacion.objects.get(tipo=Notificacion.Tipo.REEMBOLSO)

        self.assertEqual(n.nivel, Notificacion.Nivel.AVISO)
        self.assertIn('Ana Ruiz', n.texto)
        self.assertIn('Sin cupo', n.texto)
        reserva.refresh_from_db()
        self.assertEqual(reserva.monto_reembolsado, Decimal('1000.00'))
