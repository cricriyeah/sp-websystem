from django.test import SimpleTestCase
from django.urls import reverse


class RutasSinPrefijoDeEmpresaTests(SimpleTestCase):
    """
    Guardarraíl para la expansión multi-sede: el prefijo `<slug:empresa_slug>/`
    vive dentro de cada `apps/<app>/urls.py`, nunca en `config/urls.py`. Si
    alguien lo sube un nivel, `/healthz` deja de resolver donde Render lo espera
    y `/admin/finanzas/` deja de resolver donde el admin lo espera.
    """

    def test_healthz_sin_prefijo(self):
        self.assertEqual(reverse('healthz'), '/healthz')

    def test_finanzas_sin_prefijo(self):
        self.assertEqual(reverse('finanzas'), '/admin/finanzas/')

    def test_admin_index_sin_prefijo(self):
        self.assertEqual(reverse('admin:index'), '/admin/')
