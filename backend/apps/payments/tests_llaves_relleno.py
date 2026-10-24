from django.test import TestCase

from apps.tenancy.models import Empresa, Sede

from .checks import revisar_llaves_de_relleno


class LlavesDeRellenoTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede', slug='sede-relleno')

    def _empresa(self, slug, secreta='sk_test_real', webhook='whsec_real', activo=True):
        return Empresa.objects.create(
            sede=self.sede, nombre=slug, slug=slug, activo=activo,
            stripe_secret_key=secreta, stripe_webhook_secret=webhook,
            stripe_publishable_key='pk_test_real',
        )

    def test_llaves_reales_no_avisan(self):
        self._empresa('real')
        self.assertEqual(revisar_llaves_de_relleno(None), [])

    def test_llaves_de_relleno_avisan_por_empresa_y_por_campo(self):
        self._empresa('piratas', secreta='sk_test_CAMBIAME', webhook='whsec_CAMBIAME')
        avisos = revisar_llaves_de_relleno(None)
        self.assertEqual([a.id for a in avisos], ['payments.W001', 'payments.W001'])
        self.assertTrue(all('piratas' in a.msg for a in avisos))

    def test_el_aviso_no_incluye_el_valor_de_la_llave(self):
        self._empresa('piratas', secreta='sk_test_CAMBIAME_secreto', webhook='whsec_real')
        avisos = revisar_llaves_de_relleno(None)
        self.assertEqual(len(avisos), 1)
        self.assertNotIn('secreto', avisos[0].msg + avisos[0].hint)

    def test_una_empresa_apagada_no_avisa(self):
        self._empresa('apagada', secreta='sk_test_CAMBIAME', webhook='whsec_CAMBIAME', activo=False)
        self.assertEqual(revisar_llaves_de_relleno(None), [])

    def test_mezclar_prueba_y_produccion_avisa(self):
        self._empresa('a', secreta='sk_test_a')
        self._empresa('b', secreta='sk_live_b')
        avisos = revisar_llaves_de_relleno(None)
        self.assertEqual([a.id for a in avisos], ['payments.W002'])

    def test_todas_en_prueba_no_avisan_de_mezcla(self):
        self._empresa('a', secreta='sk_test_a')
        self._empresa('b', secreta='sk_test_b')
        self.assertEqual(revisar_llaves_de_relleno(None), [])

    def test_llaves_vacias_no_avisan(self):
        self._empresa('sin-stripe', secreta='', webhook='')
        self.assertEqual(revisar_llaves_de_relleno(None), [])
