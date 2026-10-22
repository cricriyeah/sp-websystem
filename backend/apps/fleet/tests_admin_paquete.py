"""Pruebas del admin de Paquetes (PaqueteAdmin), inlines, resumen y menú lateral."""
from decimal import Decimal
from io import StringIO

from django.conf import settings
from django.contrib import admin
from django.core.management import call_command
from django.forms import inlineformset_factory
from django.urls import reverse

from apps.bookings.models import ReservaOcupacion
from apps.fleet.admin import PaqueteAdmin, PaqueteServicioFormSet
from apps.fleet.enums import TipoTraslado
from apps.fleet.models import Paquete, PaqueteServicio, Servicio, TransporteTarifa
from apps.tenancy import scope
from apps.tenancy.models import Empresa
from apps.testing import EmpresaTestCase


class PaqueteAdminVistasTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.jefe = self.crear_jefe('jefe_paquete')
        self.client.force_login(self.jefe)
        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Aventura Marina',
            slug='aventura-marina',
            precio_ancla=Decimal('7500.00'),
        )

    def test_alta_y_edicion_cargan_200_y_todos_los_campos_editables_en_fieldsets(self):
        # 1. El alta carga con 200
        url_add = reverse('admin:fleet_paquete_add')
        resp_add = self.client.get(url_add)
        self.assertEqual(resp_add.status_code, 200)

        # 2. La edición carga con 200
        url_change = reverse('admin:fleet_paquete_change', args=[self.paquete.pk])
        resp_change = self.client.get(url_change)
        self.assertEqual(resp_change.status_code, 200)

        # 3. Todos los campos editables del modelo están en algún fieldset
        paquete_admin = PaqueteAdmin(Paquete, admin.site)
        fieldsets = paquete_admin.get_fieldsets(None, self.paquete)
        campos_en_fieldsets = {campo for _, opts in fieldsets for campo in opts.get('fields', ())}

        campos_editables = [
            'nombre', 'slug', 'descripcion', 'sede', 'empresa_lider', 'activo',
            'precio_ancla', 'estrategia_precio', 'personas_precio_base', 'precio_persona_extra',
            'pide_hora', 'permite_anticipo', 'porcentaje_anticipo',
        ]
        for campo in campos_editables:
            self.assertIn(campo, campos_en_fieldsets, f"El campo {campo} debe estar en algún fieldset")

        # 4. Cada fieldset tiene título y description explicativa
        for titulo, opts in fieldsets:
            self.assertTrue(titulo, "Cada fieldset debe tener título")
            self.assertTrue(opts.get('description'), f"El fieldset '{titulo}' debe tener description")


class PaqueteAdminResumenTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.paquete_admin = PaqueteAdmin(Paquete, admin.site)
        self.paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Experiencia Completa',
            slug='experiencia-completa',
            precio_ancla=Decimal('6000.00'),
            estrategia_precio='por_grupo',
            personas_precio_base=2,
            precio_persona_extra=Decimal('500.00'),
        )

    def test_alta_nueva_muestra_mensaje_de_guardar_primero(self):
        self.assertIn(
            'Guarda el paquete para ver su resumen.',
            self.paquete_admin.resumen_del_paquete(None),
        )
        paquete_sin_guardar = Paquete(sede=self.sede, empresa_lider=self.empresa)
        self.assertIn(
            'Guarda el paquete para ver su resumen.',
            self.paquete_admin.resumen_del_paquete(paquete_sin_guardar),
        )

    def test_itinerario_correcto_con_hospedaje_y_pesca_varias_salidas(self):
        hospedaje = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Hotel Costa Azul',
            slug='hotel-costa-azul',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
            estrategia_precio='por_noche',
            precio_base=Decimal('1500.00'),
        )
        pesca = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Pesca Deportiva',
            slug='pesca-deportiva',
            tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia',
            estrategia_precio='por_grupo',
            precio_base=Decimal('4500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=hospedaje, dia_estancia=1, noches=3, orden=1,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=pesca, dia_estancia=2, salidas=2, orden=2,
        )

        html = self.paquete_admin.resumen_del_paquete(self.paquete)
        self.assertIn('<strong>Día 1</strong> · Hotel Costa Azul (3 noches)', html)
        self.assertIn('<strong>Día 2 y 3</strong> · Pesca Deportiva (2 salidas)', html)

    def test_precios_por_tamano_de_grupo_iguales_a_precio_total_en(self):
        html = self.paquete_admin.resumen_del_paquete(self.paquete)
        for n in range(1, 9):
            total = self.paquete.precio_total_en('MXN', n)
            self.assertIsNotNone(total)
            self.assertIn(f'${total:,.2f} MXN', html)

    def test_paquete_sin_transporte_no_muestra_cobertura(self):
        pesca = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Pesca en Panga',
            slug='pesca-en-panga',
            tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia',
            estrategia_precio='por_grupo',
            precio_base=Decimal('4000.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=pesca, dia_estancia=1, orden=1,
        )
        html = self.paquete_admin.resumen_del_paquete(self.paquete)
        self.assertNotIn('Cobertura del transporte', html)

    def test_cobertura_transporte_marca_rojo_si_no_cubre_y_no_marca_si_cubre(self):
        transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Aeropuerto',
            slug='traslado-aeropuerto',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            personas_min=1,
            personas_max=4,
            precio=Decimal('4500.00'),
            activo=True,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=transporte, dia_estancia=1, personas_incluidas=2, orden=1,
        )

        # 1. Precio que SÍ cubre la tarifa (6000.00 >= 4500.00)
        self.paquete.precio_ancla = Decimal('6000.00')
        self.paquete.save()
        html_cubre = self.paquete_admin.resumen_del_paquete(self.paquete)
        self.assertIn('Cobertura del transporte', html_cubre)
        self.assertIn('Cubre', html_cubre)
        self.assertNotIn('No cubre', html_cubre)
        self.assertNotIn('color:#dc2626', html_cubre)

        # 2. Precio que NO cubre la tarifa (3000.00 < 4500.00, faltan 1500.00)
        self.paquete.precio_ancla = Decimal('3000.00')
        self.paquete.save()
        html_no_cubre = self.paquete_admin.resumen_del_paquete(self.paquete)
        self.assertIn('Cobertura del transporte', html_no_cubre)
        self.assertIn('No cubre', html_no_cubre)
        self.assertIn('color:#dc2626', html_no_cubre)
        self.assertIn('1,500.00', html_no_cubre)

    def test_nombre_de_servicio_con_html_se_escapa(self):
        xss = Servicio.objects.create(
            empresa=self.empresa,
            nombre='<script>alert("xss")</script>',
            slug='servicio-xss',
            tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia',
            estrategia_precio='por_grupo',
            precio_base=Decimal('2000.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=xss, dia_estancia=1, orden=1,
        )
        html = self.paquete_admin.resumen_del_paquete(self.paquete)
        self.assertNotIn('<script>alert("xss")</script>', html)
        self.assertIn('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;', html)


class PaqueteServicioFormSetErroresTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.s_pesca = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Pesca Deportiva Local',
            slug='pesca-local',
            tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia',
            estrategia_precio='por_grupo',
            precio_base=Decimal('4000.00'),
        )

    def _crear_formset(self, paquete, servicios_datos):
        FormSet = inlineformset_factory(
            Paquete,
            PaqueteServicio,
            formset=PaqueteServicioFormSet,
            fields=['servicio', 'orden', 'dia_estancia', 'salidas', 'noches', 'personas_incluidas'],
            extra=0,
        )
        datos = {
            'servicios_asociados-TOTAL_FORMS': str(len(servicios_datos)),
            'servicios_asociados-INITIAL_FORMS': '0',
            'servicios_asociados-MIN_NUM_FORMS': '0',
            'servicios_asociados-MAX_NUM_FORMS': '1000',
        }
        for i, item in enumerate(servicios_datos):
            servicio = item['servicio']
            datos.update({
                f'servicios_asociados-{i}-servicio': str(servicio.pk),
                f'servicios_asociados-{i}-orden': str(item.get('orden', i + 1)),
                f'servicios_asociados-{i}-dia_estancia': str(item.get('dia_estancia', 1)),
                f'servicios_asociados-{i}-salidas': str(item.get('salidas', 1)),
                f'servicios_asociados-{i}-personas_incluidas': str(item.get('personas_incluidas', 2)),
            })
            if 'noches' in item and item['noches'] is not None:
                datos[f'servicios_asociados-{i}-noches'] = str(item['noches'])
        return FormSet(datos, instance=paquete)

    def test_rechaza_dos_hospedajes_y_nombra_los_componentes(self):
        hosp1 = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Hotel Costa',
            slug='hotel-costa',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
        )
        hosp2 = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Hotel Bahia',
            slug='hotel-bahia',
            tipo_servicio='hospedaje',
            estrategia_cupo='por_noche',
        )
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Dos Hoteles',
            slug='paquete-dos-hoteles',
            precio_ancla=Decimal('5000.00'),
        )
        formset = self._crear_formset(paquete, [
            {'servicio': hosp1, 'noches': 2},
            {'servicio': hosp2, 'noches': 3},
        ])
        self.assertFalse(formset.is_valid())
        errores = formset.non_form_errors()
        self.assertTrue(any('solo puede incluir un hospedaje' in e for e in errores))
        self.assertTrue(any('"Hotel Costa"' in e and '"Hotel Bahia"' in e for e in errores))

    def test_rechaza_anticipo_con_dos_empresas_y_nombra_componentes(self):
        # Crear servicio de otra empresa bajo su propio alcance
        self._alcance.__exit__(None, None, None)
        try:
            otra_empresa = Empresa.objects.create(
                sede=self.sede,
                nombre='Transportes La Paz',
                slug='transp-la-paz',
                activo=True,
                exclusiva=False,
            )
            with scope.con_empresa(otra_empresa):
                s_otra = Servicio.objects.create(
                    empresa=otra_empresa,
                    nombre='Traslado Foraneo',
                    slug='traslado-foraneo',
                    tipo_servicio='transporte',
                    estrategia_cupo='bajo_demanda',
                    estrategia_precio='por_ruta',
                    activo=True,
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Dos Empresas',
            slug='paquete-dos-empresas',
            precio_ancla=Decimal('8000.00'),
            permite_anticipo=True,
        )
        # El paquete junta servicios de dos empresas: validarlo exige ver las dos (RLS), como el operador.
        self._alcance.__exit__(None, None, None)
        try:
            with scope.como_operador_plataforma():
                formset = self._crear_formset(paquete, [
                    {'servicio': self.s_pesca},
                    {'servicio': s_otra},
                ])
                self.assertFalse(formset.is_valid())
                errores = formset.non_form_errors()
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.assertTrue(any('no admite anticipo' in e for e in errores))
        self.assertTrue(any('"Pesca Deportiva Local"' in e and '"Traslado Foraneo"' in e for e in errores))

    def test_rechaza_precio_bajo_la_peor_tarifa_y_nombra_componente(self):
        transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Malecon',
            slug='traslado-malecon',
            tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda',
            estrategia_precio='por_ruta',
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            personas_min=1,
            personas_max=4,
            precio=Decimal('4500.00'),
            activo=True,
        )
        paquete = Paquete.objects.create(
            sede=self.sede,
            empresa_lider=self.empresa,
            nombre='Paquete Bajo Tarifa',
            slug='paquete-bajo-tarifa',
            precio_ancla=Decimal('3500.00'),
            permite_anticipo=False,
        )
        formset = self._crear_formset(paquete, [
            {'servicio': transporte, 'personas_incluidas': 2},
        ])
        self.assertFalse(formset.is_valid())
        errores = formset.non_form_errors()
        self.assertTrue(any('tarifa de transporte' in e for e in errores))
        self.assertTrue(any('"Traslado Malecon"' in e for e in errores))


class MenuYMigracionesTests(EmpresaTestCase):
    def test_makemigrations_check_sin_cambios(self):
        salida = StringIO()
        call_command('makemigrations', check=True, dry_run=True, stdout=salida)

    def test_menu_lateral_y_admin_ocupaciones_de_hospedaje(self):
        # 1. Menú lateral tiene el título unificado
        sidebar = settings.UNFOLD['SIDEBAR']['navigation']
        titulos = [
            item['title']
            for seccion in sidebar
            for item in seccion.get('items', [])
        ]
        self.assertIn('Ocupaciones de hospedaje', titulos)

        # 2. verbose_name_plural del modelo unificado
        self.assertEqual(ReservaOcupacion._meta.verbose_name_plural, 'ocupaciones de hospedaje')

        # 3. La pantalla de changelist de esa lista carga con 200 para un Jefe
        jefe = self.crear_jefe('jefe_ocupaciones')
        self.client.force_login(jefe)
        url = reverse('admin:bookings_reservaocupacion_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ocupaciones de hospedaje')
