"""Las llaves de Stripe de cada Empresa se guardan cifradas y se leen como texto real.

Auditoria 2026-10-24: estaban en texto plano en `tenancy_empresa`. Quien leyera la base (un respaldo, el
panel de Supabase) se llevaba llaves capaces de devolver dinero. Aqui se fija que en la base hay texto
cifrado, que en Python sigue siendo la llave real, que rotar la clave funciona y que perder la clave
nunca borra el dato.
"""
from io import StringIO

from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings

from apps.payments.checks import revisar_cifrado_de_llaves
from apps.tenancy.campos import PREFIJO
from apps.tenancy.models import Empresa, Sede

CLAVE_A = Fernet.generate_key().decode()
CLAVE_B = Fernet.generate_key().decode()
SECRETA = 'sk_test_llave_de_prueba'
WEBHOOK = 'whsec_abc123def456'


def crudo(empresa, campo='stripe_secret_key'):
    """Lo que de verdad hay en la columna, sin pasar por el campo."""
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT {campo} FROM {Empresa._meta.db_table} WHERE id = %s', [empresa.pk])
        return cursor.fetchone()[0]


class LlavesCifradasTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede', slug='sede-cifrado')

    def empresa(self, slug='cifrada', **extra):
        datos = {'stripe_secret_key': SECRETA, 'stripe_webhook_secret': WEBHOOK, 'stripe_publishable_key': 'pk_test_x'}
        datos.update(extra)
        return Empresa.objects.create(sede=self.sede, nombre=slug, slug=slug, **datos)

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A)
    def test_en_la_base_hay_texto_cifrado_y_en_python_la_llave_real(self):
        empresa = self.empresa()

        self.assertTrue(crudo(empresa).startswith(PREFIJO))
        self.assertNotIn(SECRETA, crudo(empresa))
        self.assertTrue(crudo(empresa, 'stripe_webhook_secret').startswith(PREFIJO))
        recargada = Empresa.objects.get(pk=empresa.pk)
        self.assertEqual(recargada.stripe_secret_key, SECRETA)
        self.assertEqual(recargada.stripe_webhook_secret, WEBHOOK)

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A)
    def test_la_llave_publica_no_se_cifra(self):
        empresa = self.empresa()
        self.assertEqual(crudo(empresa, 'stripe_publishable_key'), 'pk_test_x')

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY='')
    def test_sin_clave_se_guarda_en_texto_plano_como_antes(self):
        empresa = self.empresa()
        self.assertEqual(crudo(empresa), SECRETA)
        self.assertEqual(Empresa.objects.get(pk=empresa.pk).stripe_secret_key, SECRETA)

    def test_un_valor_en_texto_plano_anterior_se_lee_y_se_cifra_al_guardar(self):
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=''):
            empresa = self.empresa()
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A):
            self.assertEqual(Empresa.objects.get(pk=empresa.pk).stripe_secret_key, SECRETA)
            cargada = Empresa.objects.get(pk=empresa.pk)
            cargada.save()
            self.assertTrue(crudo(empresa).startswith(PREFIJO))
            self.assertEqual(Empresa.objects.get(pk=empresa.pk).stripe_secret_key, SECRETA)

    def test_guardar_dos_veces_no_cifra_lo_ya_cifrado(self):
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A):
            empresa = self.empresa()
            primero = crudo(empresa)
            Empresa.objects.get(pk=empresa.pk).save()
            # Se vuelve a cifrar el texto real (otro vector), nunca el cifrado encima del cifrado.
            self.assertEqual(Empresa.objects.get(pk=empresa.pk).stripe_secret_key, SECRETA)
            self.assertTrue(crudo(empresa).startswith(PREFIJO))
            self.assertEqual(crudo(empresa).count(PREFIJO), 1)
            self.assertNotEqual(primero, '')

    def test_rotar_la_clave_antepone_la_nueva_y_sigue_leyendo(self):
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A):
            empresa = self.empresa()
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=f'{CLAVE_B},{CLAVE_A}'):
            self.assertEqual(Empresa.objects.get(pk=empresa.pk).stripe_secret_key, SECRETA)
            call_command('cifrar_llaves_stripe', stdout=StringIO())
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_B):  # ya sin la vieja
            self.assertEqual(Empresa.objects.get(pk=empresa.pk).stripe_secret_key, SECRETA)

    def test_con_la_clave_equivocada_devuelve_lo_cifrado_y_guardar_no_borra_el_dato(self):
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A):
            empresa = self.empresa()
            cifrado = crudo(empresa)
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_B):
            ilegible = Empresa.objects.get(pk=empresa.pk)
            self.assertEqual(ilegible.stripe_secret_key, cifrado)  # no se inventa un valor vacio
            ilegible.nombre = 'Otro nombre'
            ilegible.save()
            self.assertEqual(crudo(empresa), cifrado)  # lo cifrado no se vuelve a cifrar
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A):
            self.assertEqual(Empresa.objects.get(pk=empresa.pk).stripe_secret_key, SECRETA)

    def test_llave_vacia_se_queda_vacia(self):
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A):
            empresa = self.empresa(stripe_secret_key='', stripe_webhook_secret='')
            self.assertEqual(crudo(empresa), '')

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A)
    def test_stripe_client_recibe_la_llave_real(self):
        from apps.payments.stripe_client import configurar_stripe

        empresa = self.empresa()
        cliente = configurar_stripe(Empresa.objects.get(pk=empresa.pk))
        self.assertEqual(cliente._requestor.api_key, SECRETA)


class ComandoCifrarLlavesTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede', slug='sede-cmd')
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=''):
            self.empresa = Empresa.objects.create(
                sede=self.sede, nombre='Vieja', slug='vieja', stripe_secret_key=SECRETA,
                stripe_webhook_secret=WEBHOOK, stripe_publishable_key='pk_test_x',
            )

    def correr(self, *args):
        salida = StringIO()
        call_command('cifrar_llaves_stripe', *args, stdout=salida)
        return salida.getvalue()

    def test_sin_clave_se_niega(self):
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=''):
            with self.assertRaises(CommandError):
                self.correr()
        self.assertEqual(crudo(self.empresa), SECRETA)

    def test_con_una_clave_que_no_es_fernet_se_niega(self):
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY='no-es-una-clave'):
            with self.assertRaises(CommandError):
                self.correr()

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A)
    def test_dry_run_cuenta_y_no_escribe(self):
        salida = self.correr('--dry-run')
        self.assertIn('2 valor(es) en texto plano', salida)
        self.assertEqual(crudo(self.empresa), SECRETA)

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A)
    def test_cifra_y_es_idempotente(self):
        self.correr()
        self.assertTrue(crudo(self.empresa).startswith(PREFIJO))
        self.assertTrue(crudo(self.empresa, 'stripe_webhook_secret').startswith(PREFIJO))
        self.assertEqual(Empresa.objects.get(pk=self.empresa.pk).stripe_secret_key, SECRETA)
        salida = self.correr()
        self.assertIn('0 valor(es) cifrados', salida)
        self.assertEqual(Empresa.objects.get(pk=self.empresa.pk).stripe_secret_key, SECRETA)

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A)
    def test_un_valor_ilegible_detiene_el_comando_sin_escribir(self):
        self.correr()
        cifrado = crudo(self.empresa)
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_B):
            with self.assertRaises(CommandError):
                self.correr()
        self.assertEqual(crudo(self.empresa), cifrado)


class ChequeoDeCifradoTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede', slug='sede-chk')

    def empresa(self, secreta=SECRETA, webhook=WEBHOOK):
        return Empresa.objects.create(
            sede=self.sede, nombre='E', slug='e', stripe_secret_key=secreta, stripe_webhook_secret=webhook,
            stripe_publishable_key='pk_test_x',
        )

    def ids(self):
        return [aviso.id for aviso in revisar_cifrado_de_llaves(None)]

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY='')
    def test_una_llave_de_produccion_en_texto_plano_es_un_error(self):
        self.empresa(secreta='sk_live_llave_falsa_de_prueba')
        self.assertEqual(self.ids(), ['payments.E003'])

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A)
    def test_una_llave_de_produccion_cifrada_no_avisa(self):
        self.empresa(secreta='sk_live_llave_falsa_de_prueba')
        self.assertEqual(self.ids(), [])

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY='')
    def test_llaves_de_prueba_en_texto_plano_sin_clave_no_avisan(self):
        self.empresa()
        self.assertEqual(self.ids(), [])

    def test_con_clave_y_texto_plano_pendiente_avisa_que_corra_el_comando(self):
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=''):
            self.empresa()
        with override_settings(STRIPE_KEYS_ENCRYPTION_KEY=CLAVE_A):
            self.assertEqual(self.ids(), ['payments.W003'])

    @override_settings(STRIPE_KEYS_ENCRYPTION_KEY='basura')
    def test_una_clave_que_no_es_fernet_es_un_error(self):
        self.assertEqual(self.ids(), ['payments.E004'])
