"""Descripción es/en de las personalizaciones (se muestra bajo cada extra en el checkout)."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.fleet.models import Personalizacion, Servicio, ServicioPersonalizacion
from apps.fleet.serializers import ServicioPersonalizacionSerializer
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class PersonalizacionDescripcionTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede Desc', slug='sede-desc')
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa Desc', slug='empresa-desc')

    def _personalizacion(self, **extra):
        with scope.como_operador_plataforma():
            return Personalizacion.objects.create(empresa=self.empresa, nombre=extra.pop('nombre', 'Brunch'), **extra)

    def test_descripcion_vale_vacia_por_defecto(self):
        self.assertEqual(self._personalizacion().descripcion, {})

    def test_una_personalizacion_sin_descripcion_es_valida(self):
        self._personalizacion().full_clean()

    def test_acepta_es_y_en_y_recorta_espacios(self):
        p = self._personalizacion(descripcion={'es': '  Desayuno a bordo ', 'en': ' Breakfast on board'})
        p.full_clean()
        self.assertEqual(p.descripcion, {'es': 'Desayuno a bordo', 'en': 'Breakfast on board'})

    def test_acepta_solo_un_idioma(self):
        self._personalizacion(descripcion={'es': 'Solo en español'}).full_clean()

    def test_rechaza_lo_que_no_es_un_objeto(self):
        for valor in (['es'], 'texto', 5):
            p = self._personalizacion(nombre=f'X{valor!r}', descripcion=valor)
            with self.assertRaises(ValidationError) as ctx:
                p.full_clean()
            self.assertIn('descripcion', ctx.exception.message_dict)

    def test_rechaza_claves_distintas_de_es_y_en(self):
        p = self._personalizacion(descripcion={'es': 'ok', 'fr': 'non'})
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn('descripcion', ctx.exception.message_dict)

    def test_rechaza_valores_que_no_son_texto(self):
        p = self._personalizacion(descripcion={'es': 5})
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn('descripcion', ctx.exception.message_dict)

    def test_rechaza_mas_de_160_caracteres(self):
        p = self._personalizacion(descripcion={'es': 'a' * 161})
        with self.assertRaises(ValidationError) as ctx:
            p.full_clean()
        self.assertIn('descripcion', ctx.exception.message_dict)
        self._personalizacion(nombre='Justo', descripcion={'es': 'a' * 160}).full_clean()

    def test_el_serializer_la_expone_tal_cual(self):
        with scope.como_operador_plataforma():
            servicio = Servicio.objects.create(
                empresa=self.empresa, nombre='Pesca', slug='pesca-desc', tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia', estrategia_precio='por_grupo', modo_ocupacion='exclusivo',
                precio_base=Decimal('100.00'),
            )
            p = Personalizacion.objects.create(
                empresa=self.empresa, nombre='Brunch', descripcion={'es': 'Desayuno', 'en': 'Breakfast'},
            )
            sp = ServicioPersonalizacion.objects.create(servicio=servicio, personalizacion=p, precio=Decimal('50.00'))
            datos = ServicioPersonalizacionSerializer(sp).data
        self.assertEqual(datos['descripcion'], {'es': 'Desayuno', 'en': 'Breakfast'})

    def test_el_serializer_da_objeto_vacio_sin_descripcion(self):
        with scope.como_operador_plataforma():
            servicio = Servicio.objects.create(
                empresa=self.empresa, nombre='Pesca', slug='pesca-desc2', tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia', estrategia_precio='por_grupo', modo_ocupacion='exclusivo',
                precio_base=Decimal('100.00'),
            )
            p = Personalizacion.objects.create(empresa=self.empresa, nombre='Carnada')
            sp = ServicioPersonalizacion.objects.create(servicio=servicio, personalizacion=p)
            datos = ServicioPersonalizacionSerializer(sp).data
        self.assertEqual(datos['descripcion'], {})


class PersonalizacionAdminFormTests(TestCase):
    """El admin captura la descripción en dos campos de texto y la guarda en el JSON."""

    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede Form', slug='sede-form')
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa Form', slug='empresa-form')

    def _datos(self, **extra):
        datos = {
            'empresa': self.empresa.pk, 'nombre': 'Brunch', 'tipo': 'otro', 'tipo_interaccion': 'check',
            'opciones_seleccion': '[]', 'activo': 'on',
        }
        datos.update(extra)
        return datos

    def test_guarda_los_dos_idiomas_en_el_json(self):
        from apps.fleet.admin import PersonalizacionAdminForm
        form = PersonalizacionAdminForm(self._datos(descripcion_es=' Desayuno ', descripcion_en='Breakfast'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.descripcion, {'es': 'Desayuno', 'en': 'Breakfast'})

    def test_vacia_si_no_se_escribe_nada(self):
        from apps.fleet.admin import PersonalizacionAdminForm
        form = PersonalizacionAdminForm(self._datos())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.descripcion, {})

    def test_al_editar_precarga_lo_guardado(self):
        from apps.fleet.admin import PersonalizacionAdminForm
        with scope.como_operador_plataforma():
            p = Personalizacion.objects.create(
                empresa=self.empresa, nombre='Brunch', descripcion={'es': 'Desayuno', 'en': 'Breakfast'},
            )
        form = PersonalizacionAdminForm(instance=p)
        self.assertEqual(form.fields['descripcion_es'].initial, 'Desayuno')
        self.assertEqual(form.fields['descripcion_en'].initial, 'Breakfast')

    def test_rechaza_mas_de_160_caracteres(self):
        from apps.fleet.admin import PersonalizacionAdminForm
        form = PersonalizacionAdminForm(self._datos(descripcion_es='a' * 161))
        self.assertFalse(form.is_valid())
        self.assertIn('descripcion_es', form.errors)
