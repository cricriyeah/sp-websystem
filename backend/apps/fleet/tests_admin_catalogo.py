"""Pruebas del admin de catálogo para Servicio (ServicioAdmin).

Cubre:
1. La página de alta y edición carga (200) con jefe y con operador.
2. Todos los campos editables del modelo aparecen en algún fieldset.
3. Los bloques están en el HTML con su título; los campos con ayuda nueva muestran su texto.
4. conditional_fields solo referencia campos NO obligatorios contra el modelo.
5. Guardar un Servicio de hospedaje sin campos de horario funciona (POST completo).
6. Guardar un Servicio de pesca con horario funciona (POST completo).
7. Guardar un Servicio con operador de plataforma asignando empresa funciona (POST completo).
8. python manage.py makemigrations --check no detecta cambios.
"""
from datetime import time
from decimal import Decimal
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.fleet.admin import AYUDA_CAMPOS_SERVICIO, ServicioAdmin
from apps.fleet.models import Servicio
from apps.tenancy import scope
from apps.testing import EmpresaTestCase, crear_servicio_pesca

User = get_user_model()


# Un POST del admin con inlines siempre lleva los datos de control de cada formset anidado;
# sin ellos Django rechaza el envio entero.
INLINE_PERSONALIZACIONES = {
    'servicio_personalizaciones-TOTAL_FORMS': '0',
    'servicio_personalizaciones-INITIAL_FORMS': '0',
    'servicio_personalizaciones-MIN_NUM_FORMS': '0',
    'servicio_personalizaciones-MAX_NUM_FORMS': '1000',
}


class ServicioAdminCatalogoTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.jefe = self.crear_jefe(username='jefa_catalogo')

    def test_pagina_alta_y_edicion_carga_con_jefe(self):
        """Alta y edición responden 200 con jefe y todos los campos del form están en fieldsets."""
        self.client.force_login(self.jefe)
        servicio = crear_servicio_pesca(self.empresa)

        resp_add = self.client.get(reverse('admin:fleet_servicio_add'))
        self.assertEqual(resp_add.status_code, 200)

        resp_change = self.client.get(reverse('admin:fleet_servicio_change', args=[servicio.pk]))
        self.assertEqual(resp_change.status_code, 200)

        for resp in (resp_add, resp_change):
            form = resp.context['adminform'].form
            fieldsets = resp.context['adminform'].fieldsets
            campos_en_fieldsets = {campo for _, opts in fieldsets for campo in opts['fields']}
            for nombre_campo in form.fields.keys():
                self.assertIn(
                    nombre_campo,
                    campos_en_fieldsets,
                    f'El campo {nombre_campo} está en el formulario pero no en ningún fieldset',
                )

    def test_pagina_alta_y_edicion_carga_con_operador(self):
        """Alta y edición responden 200 con operador y empresa está presente en alta."""
        operador = User.objects.create_user('operador_catalogo', is_staff=True, password='x')
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        servicio = crear_servicio_pesca(self.empresa)

        self._alcance.__exit__(None, None, None)
        try:
            self.client.force_login(operador)
            resp_add = self.client.get(reverse('admin:fleet_servicio_add'))
            self.assertEqual(resp_add.status_code, 200)

            resp_change = self.client.get(reverse('admin:fleet_servicio_change', args=[servicio.pk]))
            self.assertEqual(resp_change.status_code, 200)

            for resp in (resp_add, resp_change):
                form = resp.context['adminform'].form
                fieldsets = resp.context['adminform'].fieldsets
                campos_en_fieldsets = {campo for _, opts in fieldsets for campo in opts['fields']}
                for nombre_campo in form.fields.keys():
                    self.assertIn(
                        nombre_campo,
                        campos_en_fieldsets,
                        f'El campo {nombre_campo} está en el formulario pero no en ningún fieldset',
                    )

            form_add = resp_add.context['adminform'].form
            self.assertIn('empresa', form_add.fields)
            campos_add = {campo for _, opts in resp_add.context['adminform'].fieldsets for campo in opts['fields']}
            self.assertIn('empresa', campos_add)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

    def test_bloques_en_html_con_titulo_y_ayuda_nueva(self):
        """Los 6 títulos de bloques y los textos de ayuda contextual aparecen en el HTML."""
        self.client.force_login(self.jefe)
        resp = self.client.get(reverse('admin:fleet_servicio_add'))
        self.assertEqual(resp.status_code, 200)

        titulos_esperados = [
            'Qué es',
            'Cupo',
            'Precio',
            'Horario',
            'Anticipo y visibilidad',
            'Registro',
        ]
        for titulo in titulos_esperados:
            self.assertContains(resp, titulo)

        for campo, texto_ayuda in AYUDA_CAMPOS_SERVICIO.items():
            self.assertContains(resp, texto_ayuda)

    def test_conditional_fields_solo_referencia_campos_no_obligatorios(self):
        """conditional_fields sólo apunta a campos con default, blank=True o null=True."""
        condicionales = ServicioAdmin.conditional_fields
        self.assertTrue(len(condicionales) > 0)
        for nombre_campo in condicionales.keys():
            campo_modelo = Servicio._meta.get_field(nombre_campo)
            es_no_obligatorio = campo_modelo.has_default() or campo_modelo.blank or campo_modelo.null
            self.assertTrue(
                es_no_obligatorio,
                f'El campo {nombre_campo} en conditional_fields es obligatorio en el modelo',
            )

    def test_guardar_servicio_hospedaje_sin_horario(self):
        """Guardar un hospedaje sin marcar «pide hora» (y sin horas) tiene éxito."""
        self.client.force_login(self.jefe)
        datos = {
            'nombre': 'Cabaña Los Pinos',
            'slug': 'cabana-los-pinos',
            'tipo_servicio': 'hospedaje',
            'descripcion': 'Cabaña frente al mar',
            'activo': 'on',
            'estrategia_cupo': 'por_noche',
            'modo_ocupacion': 'exclusivo',
            'capacidad_maxima': '4',
            'estrategia_precio': 'por_noche',
            'precio_base': '2200.00',
            'permite_anticipo': 'on',
            'porcentaje_anticipo': '30',
        }
        resp = self.client.post(reverse('admin:fleet_servicio_add'), {**INLINE_PERSONALIZACIONES, **datos})
        self.assertEqual(resp.status_code, 302)

        hospedaje = Servicio.objects.get(slug='cabana-los-pinos')
        self.assertEqual(hospedaje.tipo_servicio, 'hospedaje')
        self.assertFalse(hospedaje.pide_hora)
        self.assertIsNone(hospedaje.hora_apertura)
        self.assertIsNone(hospedaje.hora_cierre)
        self.assertEqual(hospedaje.empresa, self.empresa)

    def test_pide_hora_sin_horas_se_rechaza_con_el_mensaje_del_modelo(self):
        """No se cambia nada en silencio: si «pide hora» queda marcado, el modelo exige el rango."""
        self.client.force_login(self.jefe)
        datos = {
            'nombre': 'Cabaña Con Hora', 'slug': 'cabana-con-hora', 'tipo_servicio': 'hospedaje',
            'activo': 'on', 'estrategia_cupo': 'por_noche', 'modo_ocupacion': 'exclusivo',
            'capacidad_maxima': '4', 'estrategia_precio': 'por_noche', 'precio_base': '2200.00',
            'pide_hora': 'on', 'permite_anticipo': 'on', 'porcentaje_anticipo': '30',
        }

        resp = self.client.post(reverse('admin:fleet_servicio_add'), {**INLINE_PERSONALIZACIONES, **datos})

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'necesita su rango')
        self.assertFalse(Servicio.objects.filter(slug='cabana-con-hora').exists())

    def test_guardar_servicio_pesca_con_horario(self):
        """Guardar un servicio de pesca con horario y recargo de grupo persiste íntegro."""
        self.client.force_login(self.jefe)
        datos = {
            'nombre': 'Pesca en Altamar',
            'slug': 'pesca-altamar',
            'tipo_servicio': 'pesca',
            'descripcion': 'Jornada matutina de pesca deportiva',
            'activo': 'on',
            'estrategia_cupo': 'por_recurso_dia',
            'modo_ocupacion': 'exclusivo',
            'capacidad_maxima': '5',
            'estrategia_precio': 'por_grupo',
            'precio_base': '4800.00',
            'precio_persona_extra': '600.00',
            'personas_incluidas': '3',
            'pide_hora': 'on',
            'paso_hora_minutos': '15',
            'hora_apertura': '06:00',
            'hora_cierre': '07:30',
            'permite_anticipo': 'on',
            'porcentaje_anticipo': '30',
        }
        resp = self.client.post(reverse('admin:fleet_servicio_add'), {**INLINE_PERSONALIZACIONES, **datos})
        self.assertEqual(resp.status_code, 302)

        pesca = Servicio.objects.get(slug='pesca-altamar')
        self.assertEqual(pesca.tipo_servicio, 'pesca')
        self.assertTrue(pesca.pide_hora)
        self.assertEqual(pesca.hora_apertura, time(6, 0))
        self.assertEqual(pesca.hora_cierre, time(7, 30))
        self.assertEqual(pesca.precio_base, Decimal('4800.00'))
        self.assertEqual(pesca.precio_persona_extra, Decimal('600.00'))
        self.assertEqual(pesca.personas_incluidas, 3)

    def test_guardar_servicio_con_operador(self):
        """Un operador de plataforma puede crear un servicio asignando explícitamente la empresa."""
        operador = User.objects.create_user('operador_creador', is_staff=True, password='x')
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))

        self._alcance.__exit__(None, None, None)
        try:
            self.client.force_login(operador)
            datos = {
                'empresa': str(self.empresa.pk),
                'nombre': 'Paseo en Velero',
                'slug': 'paseo-velero',
                'tipo_servicio': 'paseo',
                'descripcion': 'Paseo por la bahía al atardecer',
                'activo': 'on',
                'estrategia_cupo': 'bajo_demanda',
                'modo_ocupacion': 'exclusivo',
                'capacidad_maxima': '6',
                'estrategia_precio': 'tarifa_fija',
                'precio_base': '3500.00',
                'pide_hora': 'on',
                'paso_hora_minutos': '30',
                'hora_apertura': '09:00',
                'hora_cierre': '18:00',
                'permite_anticipo': 'on',
                'porcentaje_anticipo': '30',
            }
            resp = self.client.post(reverse('admin:fleet_servicio_add'), {**INLINE_PERSONALIZACIONES, **datos})
            self.assertEqual(resp.status_code, 302)

            with scope.como_operador_plataforma():  # la petición dejó la conexión sin alcance
                velero = Servicio.objects.get(slug='paseo-velero')
            self.assertEqual(velero.empresa_id, self.empresa.pk)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

    def test_makemigrations_check(self):
        """Verifica que ningún cambio de admin o ayuda haya generado migraciones pendientes."""
        out = io.StringIO()
        call_command('makemigrations', check=True, dry_run=True, stdout=out)
