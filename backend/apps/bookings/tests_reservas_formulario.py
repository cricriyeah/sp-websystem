import contextlib
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib import admin
from django.test import RequestFactory
from django.core.management import call_command

from apps.fleet.models import Paquete, PuntoEncuentro, Servicio
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca
from apps.tenancy.models import Empresa
from apps.tenancy import scope

from .models import Reserva, DetalleTransporte, ReservaPaqueteComponente
from .admin import telefono_marcable
from .tests import crear_reserva


class AltaReservaEmpresaTests(EmpresaTestCase):
    def setUp(self):
        self.servicio = crear_servicio_pesca(self.empresa)
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_reserva_add')

    def _datos(self, **extra):
        datos = {
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '612 123 4567',
            'correo_cliente': 'ana@example.com',
            'fecha': (timezone.localdate() + timedelta(days=10)).isoformat(),
            'hora': '06:00',
            'numero_personas': '2',
            'servicio': str(self.servicio.pk),
            'moneda': Reserva.Moneda.MXN,
            # El alta ya no pide estado ni canal: «¿Ya pagó?» decide el estado.
            'ya_pago': 'no',
            **extra,
        }
        for prefijo in ('personalizaciones_seleccionadas', 'ocupaciones', 'componentes', 'detalle_transporte'):
            datos[f'{prefijo}-TOTAL_FORMS'] = '0'
            datos[f'{prefijo}-INITIAL_FORMS'] = '0'
        return datos

    def test_vendedora_crea_servicio_pendiente_sin_elegir_empresa(self):
        self.client.force_login(self.crear_vendedora())
        respuesta = self.client.post(self.url, self._datos(empresa='999999'))
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and (
            respuesta.context['adminform'].form.errors,
            [(fs.formset.prefix, fs.formset.non_form_errors()) for fs in respuesta.context['inline_admin_formsets']],
        ))
        reserva = Reserva.objects.get(nombre_cliente='Ana Ruiz')
        self.assertEqual(reserva.empresa_id, self.empresa.pk)
        self.assertEqual(reserva.servicio_id, self.servicio.pk)

    def test_jefe_crea_paquete_pagado_sin_elegir_empresa(self):
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Paquete prueba',
            slug='paquete-prueba', precio_ancla=1000,
        )
        self.client.force_login(self.crear_jefe())
        respuesta = self.client.post(self.url, self._datos(
            servicio='', paquete=str(paquete.pk), ya_pago='todo_transferencia',
            precio_total='1000.00', empresa='999999',
        ))
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and (
            respuesta.context['adminform'].form.errors,
            [(fs.formset.prefix, fs.formset.non_form_errors()) for fs in respuesta.context['inline_admin_formsets']],
        ))
        reserva = Reserva.objects.get(nombre_cliente='Ana Ruiz')
        self.assertEqual(reserva.empresa_id, self.empresa.pk)
        self.assertEqual(reserva.paquete_id, paquete.pk)

    def test_vendedora_no_crea_con_servicio_de_otra_empresa(self):
        ajena = Empresa.objects.create(sede=self.sede, nombre='Ajena', slug='ajena')
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(ajena):
                servicio_ajeno = crear_servicio_pesca(ajena)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.client.force_login(self.crear_vendedora())
        respuesta = self.client.post(self.url, self._datos(
            servicio=str(servicio_ajeno.pk), empresa=str(ajena.pk),
        ))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Ana Ruiz').exists())

    def test_usuario_sin_empresa_no_puede_crear(self):
        usuario = get_user_model().objects.create_user('sin-empresa', password='x', is_staff=True)
        self.client.force_login(usuario)
        self.assertEqual(self.client.post(self.url, self._datos(empresa=str(self.empresa.pk))).status_code, 403)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Ana Ruiz').exists())

    def test_operador_elije_empresa_en_alta(self):
        operador = get_user_model().objects.create_user('op-alta-post', password='x', is_staff=True)
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        self.client.force_login(operador)
        self._alcance.__exit__(None, None, None)
        try:
            sin_empresa = self.client.post(self.url, self._datos(empresa=''))
            self.assertEqual(sin_empresa.status_code, 200)
            respuesta = self.client.post(self.url, self._datos(empresa=str(self.empresa.pk)))
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and respuesta.context['adminform'].form.errors)
        self.assertEqual(Reserva.objects.get(nombre_cliente='Ana Ruiz').empresa_id, self.empresa.pk)


class EdicionReservaFormularioTests(EmpresaTestCase):
    def setUp(self):
        self.reserva = crear_reserva(self.empresa, estado=Reserva.Estado.PENDIENTE_PAGO)
        self.url = reverse('admin:bookings_reserva_change', args=[self.reserva.pk])
        self.admin = admin.site._registry[Reserva]

    def _request(self, usuario):
        request = RequestFactory().get(self.url)
        request.user = usuario
        return request

    def test_fieldsets_en_orden_y_cubren_campos_del_modelo(self):
        usuario = self.crear_jefe()
        fieldsets = self.admin.get_fieldsets(self._request(usuario), self.reserva)
        self.assertEqual([nombre for nombre, _ in fieldsets], [
            'Cliente', 'Viaje', 'Cobro', 'Asignación', 'Cancelación', 'Registro del sistema',
        ])
        campos = [campo for _, opciones in fieldsets for campo in opciones['fields']]
        esperados = {campo.name for campo in Reserva._meta.fields} - {'id', 'empresa'}
        self.assertEqual(set(campos) - {'personas_por_servicio_legible'}, esperados)
        self.assertEqual(len(campos), len(set(campos)))
        self.assertIn('collapse', fieldsets[-1][1]['classes'])
        self.assertIn('collapse', fieldsets[-2][1]['classes'])
        self.assertIn('monto_transferencia', fieldsets[2][1]['fields'])
        self.assertTrue({'transferencia_registrada_en', 'transferencia_registrada_por'} <= set(fieldsets[-1][1]['fields']))
        self.assertTrue({'apartado_hasta', 'apartado_demanda', 'alerta_reembolso_fallido_en'} <= set(fieldsets[-1][1]['fields']))
        self.reserva.estado = Reserva.Estado.CANCELADA
        self.assertNotIn('collapse', self.admin.get_fieldsets(self._request(usuario), self.reserva)[-2][1].get('classes', ()))

    def test_resumen_muestra_mismos_formatos_y_whatsapp(self):
        self.client.force_login(self.crear_vendedora())
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'reserva-resumen')
        self.assertContains(respuesta, f'https://wa.me/{telefono_marcable(self.reserva.telefono_cliente)}')
        for valor in (self.admin.cuando(self.reserva), self.admin.cobro(self.reserva),
                      self.admin.servicio_resumen(self.reserva), self.admin.asignacion(self.reserva)):
            self.assertIn(str(valor), respuesta.content.decode())

    def test_lectura_por_rol_y_aviso_sin_guardar(self):
        vendedora = self.crear_vendedora()
        jefe = self.crear_jefe()
        operador = get_user_model().objects.create_user('operador-form', password='x', is_staff=True)
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        protegidos = {'stripe_payment_intent_id', 'checkout_id', 'orden',
                      'personas_por_servicio', 'vendedora'}
        for usuario in (vendedora, jefe, operador):
            readonly = set(self.admin.get_readonly_fields(self._request(usuario), self.reserva))
            if usuario == vendedora:
                self.assertTrue(protegidos <= readonly)
                self.assertFalse({'precio_total', 'monto_pagado', 'monto_efectivo', 'monto_transferencia',
                                  'forma_pago', 'moneda'} & readonly)
            else:
                self.assertFalse(protegidos & readonly)
            self.assertTrue({'transferencia_registrada_en', 'transferencia_registrada_por'} <= readonly)
            self.client.force_login(usuario)
            if usuario == operador:
                self._alcance.__exit__(None, None, None)
                try:
                    respuesta = self.client.get(self.url)
                finally:
                    self._alcance = scope.con_empresa(self.empresa)
                    self._alcance.__enter__()
            else:
                respuesta = self.client.get(self.url)
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, 'warn-unsaved-form')

    def _datos_edicion(self, **extra):
        datos = {
            'nombre_cliente': self.reserva.nombre_cliente,
            'telefono_cliente': self.reserva.telefono_cliente,
            'correo_cliente': self.reserva.correo_cliente,
            'fecha': self.reserva.fecha.isoformat(),
            'hora': self.reserva.hora.strftime('%H:%M') if self.reserva.hora else '',
            'numero_personas': str(self.reserva.numero_personas),
            'servicio': str(self.reserva.servicio_id or ''),
            'paquete': str(self.reserva.paquete_id or ''),
            'canal_origen': self.reserva.canal_origen,
            'estado': self.reserva.estado,
            'moneda': self.reserva.moneda,
            'forma_pago': self.reserva.forma_pago,
            **extra,
        }
        return datos

    def test_post_vendedora_guarda_dinero_pero_ignora_stripe_y_atribucion(self):
        otra = self.crear_vendedora(username='otra')
        self.reserva.stripe_payment_intent_id = 'pi_original'
        self.reserva.save(update_fields=['stripe_payment_intent_id'])
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)
        respuesta = self.client.post(self.url, self._datos_edicion(
            precio_total='4500.00', monto_pagado='1000.00', monto_transferencia='500.00',
            stripe_payment_intent_id='pi_falso', vendedora=str(otra.pk),
            personas_por_servicio='{"999": 5}', empresa='999999',
        ))
        self.assertEqual(respuesta.status_code, 302, getattr(respuesta, 'context', None) and respuesta.context['adminform'].form.errors)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.precio_total, 4500)
        self.assertEqual(self.reserva.monto_pagado, 1000)
        self.assertEqual(self.reserva.monto_transferencia, 500)
        self.assertIsNotNone(self.reserva.transferencia_registrada_en)
        self.assertEqual(self.reserva.transferencia_registrada_por, vendedora)
        self.assertEqual(self.reserva.stripe_payment_intent_id, 'pi_original')
        self.assertEqual(self.reserva.empresa_id, self.empresa.pk)
        self.assertIsNone(self.reserva.vendedora_id)
        self.assertEqual(self.reserva.personas_por_servicio, {})

    def test_sello_de_transferencia_es_el_del_primer_registro(self):
        vendedora = self.crear_vendedora()
        self.client.force_login(vendedora)
        self.assertEqual(self.client.post(self.url, self._datos_edicion(
            precio_total='4500.00', monto_transferencia='100.00')).status_code, 302)
        self.reserva.refresh_from_db()
        primero = self.reserva.transferencia_registrada_en
        self.assertEqual(self.reserva.transferencia_registrada_por, vendedora)
        self.assertIsNotNone(primero)

        self.assertEqual(self.client.post(self.url, self._datos_edicion(
            precio_total='4500.00', monto_transferencia='100.00', nombre_cliente='Nombre nuevo')).status_code, 302)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.transferencia_registrada_en, primero)

        self.assertEqual(self.client.post(self.url, self._datos_edicion(
            precio_total='4500.00', monto_transferencia='200.00')).status_code, 302)
        self.reserva.refresh_from_db()
        # Corregir o completar el importe NO mueve el dinero ya registrado a la fecha de hoy:
        # Finanzas lo ve en el dia del primer registro (igual que el efectivo).
        self.assertEqual(self.reserva.transferencia_registrada_en, primero)
        self.assertEqual(self.reserva.transferencia_registrada_por, vendedora)

        # Quitar el importe borra el sello; uno nuevo lleva su propia fecha.
        self.assertEqual(self.client.post(self.url, self._datos_edicion(
            precio_total='4500.00', monto_transferencia='0.00')).status_code, 302)
        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.transferencia_registrada_en)
        self.assertEqual(self.client.post(self.url, self._datos_edicion(
            precio_total='4500.00', monto_transferencia='300.00')).status_code, 302)
        self.reserva.refresh_from_db()
        self.assertGreater(self.reserva.transferencia_registrada_en, primero)

    def test_alta_por_rol_y_borrado_fuera_de_guardado(self):
        vendedora = self.crear_vendedora()
        jefe = self.crear_jefe()
        operador = get_user_model().objects.create_user('op-alta', password='x', is_staff=True)
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        for usuario in (vendedora, jefe, operador):
            self.client.force_login(usuario)
            if usuario == operador:
                self._alcance.__exit__(None, None, None)
            try:
                alta = self.client.get(reverse('admin:bookings_reserva_add'))
                edicion = self.client.get(self.url)
            finally:
                if usuario == operador:
                    self._alcance = scope.con_empresa(self.empresa)
                    self._alcance.__enter__()
            self.assertEqual(alta.status_code, 200)
            self.assertEqual(edicion.status_code, 200)
            self.assertNotContains(alta, 'reserva-resumen')
            self.assertEqual('empresa' in alta.context['adminform'].form.fields, usuario == operador)
            if usuario == operador:
                self.assertEqual(alta.context['adminform'].fieldsets[1][1]['fields'][0], 'empresa')
            self.assertFalse(edicion.context['show_delete'])
            self.assertEqual('Eliminar reserva' in edicion.content.decode(), usuario != vendedora)
            delete_url = reverse('admin:bookings_reserva_delete', args=[self.reserva.pk])
            self.assertEqual(edicion.content.decode().count(f'href="{delete_url}"'),
                             0 if usuario == vendedora else 1)
            if usuario == jefe:
                confirmacion = self.client.get(reverse('admin:bookings_reserva_delete', args=[self.reserva.pk]))
                self.assertEqual(confirmacion.status_code, 200)
                self.assertContains(confirmacion, 'delete-confirmation')
                self.assertTrue(Reserva.objects.filter(pk=self.reserva.pk).exists())

    def test_personas_por_servicio_nombres_y_servicio_eliminado(self):
        self.assertEqual(self.admin.personas_por_servicio_legible(self.reserva), '—')
        self.reserva.personas_por_servicio = {
            str(self.reserva.servicio_id): 3, '999999': 2,
        }
        self.assertEqual(self.admin.personas_por_servicio_legible(self.reserva),
                         'Pesca Deportiva 3 · servicio eliminado 2')
        self.reserva.personas_por_servicio = {'²': 1}
        self.assertEqual(self.admin.personas_por_servicio_legible(self.reserva),
                         'servicio eliminado 1')

    def test_inlines_vacios_no_muestran_tablas_y_fila_existente_si(self):
        self.client.force_login(self.crear_jefe())
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.context['inline_admin_formsets'], [])
        ReservaPaqueteComponente.objects.create(
            reserva=self.reserva, servicio=self.reserva.servicio, empresa=self.empresa,
        )
        respuesta = self.client.get(self.url)
        self.assertEqual([f.formset.prefix for f in respuesta.context['inline_admin_formsets']], ['componentes'])

    def test_vendedora_puede_buscar_paquete_propio_sin_editar_catalogo(self):
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Paquete elegible',
            slug='elegible', precio_ancla=1000,
        )
        usuario = self.crear_vendedora()
        self.assertTrue(usuario.has_perm('fleet.view_paquete'))
        self.assertFalse(usuario.has_perm('fleet.change_paquete'))
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('admin:autocomplete'), {
            'app_label': 'bookings', 'model_name': 'reserva', 'field_name': 'paquete',
            'term': 'elegible',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(str(paquete.pk), [fila['id'] for fila in respuesta.json()['results']])


class TrasladoInlineFormularioTests(EmpresaTestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado', slug='traslado-form',
            tipo_servicio='transporte', estrategia_cupo='bajo_demanda', pide_hora=False,
        )
        self.reserva = crear_reserva(self.empresa, servicio=self.servicio, hora=None)
        self.punto = PuntoEncuentro.objects.create(
            empresa=self.empresa, nombre='Hotel Azul', zona='centro',
        )
        self.detalle = DetalleTransporte.objects.create(
            reserva=self.reserva, tipo_traslado='redondo_actividad',
            punto_encuentro=self.punto, zona='centro',
        )
        self.url = reverse('admin:bookings_reserva_change', args=[self.reserva.pk])

    def test_setup_roles_permite_detalle_y_lectura_de_paquete(self):
        call_command('setup_roles', verbosity=0)
        permisos_primera = {
            nombre: set(Group.objects.get(name=nombre).permissions.values_list('codename', flat=True))
            for nombre in ('Vendedora', 'Jefe', 'OperadorPlataforma')
        }
        call_command('setup_roles', verbosity=0)
        for nombre in ('Vendedora', 'Jefe', 'OperadorPlataforma'):
            permisos = set(Group.objects.get(name=nombre).permissions.values_list('codename', flat=True))
            self.assertEqual(permisos, permisos_primera[nombre])
            self.assertTrue({'view_detalletransporte', 'add_detalletransporte',
                             'change_detalletransporte', 'view_paquete'} <= permisos)
            self.assertEqual('delete_detalletransporte' in permisos, nombre != 'Vendedora')

    def test_tres_roles_ven_y_guardan_detalle(self):
        usuarios = [self.crear_vendedora(), self.crear_jefe()]
        operador = get_user_model().objects.create_user('op-traslado', password='x', is_staff=True)
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        usuarios.append(operador)
        for usuario in usuarios:
            self.client.force_login(usuario)
            if usuario == operador:
                self._alcance.__exit__(None, None, None)
            try:
                respuesta = self.client.get(self.url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn('detalle_transporte', [f.formset.prefix for f in respuesta.context['inline_admin_formsets']])
                self.assertContains(respuesta, 'tipo_traslado')
                datos = {
                    'nombre_cliente': self.reserva.nombre_cliente,
                    'telefono_cliente': self.reserva.telefono_cliente,
                    'correo_cliente': self.reserva.correo_cliente,
                    'fecha': self.reserva.fecha.isoformat(),
                    'numero_personas': self.reserva.numero_personas,
                    'servicio': self.servicio.pk,
                    'canal_origen': self.reserva.canal_origen,
                    'estado': self.reserva.estado,
                    'moneda': self.reserva.moneda,
                    'detalle_transporte-TOTAL_FORMS': '1',
                    'detalle_transporte-INITIAL_FORMS': '1',
                    'detalle_transporte-0-id': str(self.detalle.pk),
                    'detalle_transporte-0-tipo_traslado': 'redondo_actividad',
                    'detalle_transporte-0-punto_encuentro': '',
                    'detalle_transporte-0-direccion_personalizada': f'Hotel {usuario.username}',
                    'detalle_transporte-0-zona': 'centro',
                }
                guardada = self.client.post(self.url, datos)
                self.assertEqual(guardada.status_code, 302, getattr(guardada, 'context', None) and (
                    guardada.context['adminform'].form.errors,
                    [(fs.formset.prefix, fs.formset.errors) for fs in guardada.context['inline_admin_formsets']],
                ))
                # Sin el alcance de la empresa (el operador no lo tiene) la lectura necesita el del operador.
                with scope.como_operador_plataforma() if usuario == operador else contextlib.nullcontext():
                    self.detalle.refresh_from_db()
                self.assertEqual(self.detalle.direccion_personalizada, f'Hotel {usuario.username}')
            finally:
                if usuario == operador:
                    self._alcance = scope.con_empresa(self.empresa)
                    self._alcance.__enter__()

    def test_traslado_sin_detalle_ofrece_agregarlo(self):
        self.detalle.delete()
        self.client.force_login(self.crear_vendedora())
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('detalle_transporte', [f.formset.prefix for f in respuesta.context['inline_admin_formsets']])
        self.assertTrue(respuesta.context['inline_admin_formsets'][0].has_add_permission)

    def test_detalle_rechaza_zona_incompatible(self):
        self.client.force_login(self.crear_vendedora())
        datos = {
            'nombre_cliente': self.reserva.nombre_cliente,
            'telefono_cliente': self.reserva.telefono_cliente,
            'correo_cliente': self.reserva.correo_cliente,
            'fecha': self.reserva.fecha.isoformat(),
            'numero_personas': self.reserva.numero_personas,
            'servicio': self.servicio.pk,
            'canal_origen': self.reserva.canal_origen,
            'estado': self.reserva.estado,
            'moneda': self.reserva.moneda,
            'detalle_transporte-TOTAL_FORMS': '1',
            'detalle_transporte-INITIAL_FORMS': '1',
            'detalle_transporte-0-id': str(self.detalle.pk),
            'detalle_transporte-0-tipo_traslado': 'redondo_actividad',
            'detalle_transporte-0-punto_encuentro': str(self.punto.pk),
            'detalle_transporte-0-zona': 'periferia',
        }
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('La zona no coincide con la del punto de encuentro',
                      str([(f.formset.errors, f.formset.non_form_errors())
                           for f in respuesta.context['inline_admin_formsets']]))
        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.zona, 'centro')

    def test_vendedora_no_puede_elegir_punto_de_otra_empresa(self):
        ajena = Empresa.objects.create(sede=self.sede, nombre='Ajena', slug='ajena-traslado')
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(ajena):
                punto_ajeno = PuntoEncuentro.objects.create(
                    empresa=ajena, nombre='Hotel ajeno', zona='centro',
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.client.force_login(self.crear_vendedora())
        respuesta = self.client.post(self.url, {
            'nombre_cliente': self.reserva.nombre_cliente,
            'telefono_cliente': self.reserva.telefono_cliente,
            'correo_cliente': self.reserva.correo_cliente,
            'fecha': self.reserva.fecha.isoformat(),
            'numero_personas': self.reserva.numero_personas,
            'servicio': self.servicio.pk,
            'canal_origen': self.reserva.canal_origen,
            'estado': self.reserva.estado,
            'moneda': self.reserva.moneda,
            'detalle_transporte-TOTAL_FORMS': '1',
            'detalle_transporte-INITIAL_FORMS': '1',
            'detalle_transporte-0-id': str(self.detalle.pk),
            'detalle_transporte-0-tipo_traslado': 'redondo_actividad',
            'detalle_transporte-0-punto_encuentro': str(punto_ajeno.pk),
            'detalle_transporte-0-zona': 'centro',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('punto_encuentro', str(respuesta.context['inline_admin_formsets'][0].formset.errors))
        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.punto_encuentro_id, self.punto.pk)
