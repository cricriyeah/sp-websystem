"""Pruebas del detalle de traslado en el alta manual de Reserva en el backoffice."""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import DetalleTransporte, Reserva, Vendedora
from apps.bookings.precio_sugerido import sugerir_precio
from apps.fleet.enums import (
    EstrategiaCupo,
    EstrategiaPrecio,
    TipoServicio,
    TipoTraslado,
    Zona,
)
from apps.fleet.models import PuntoEncuentro, Servicio, TransporteTarifa
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
from apps.testing import EmpresaTestCase, crear_flota, crear_servicio_pesca
from .tests import crear_reserva


class AltaTrasladoTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        crear_flota(self.empresa)
        self.url_alta = reverse('admin:bookings_reserva_add')

        # Vendedora con perfil activo en la empresa
        self.usuario_vendedora = self.crear_vendedora('vendedora-traslado')
        self.perfil_vendedora = Vendedora.objects.create(
            usuario=self.usuario_vendedora,
            empresa=self.empresa,
            codigo='vendedora-traslado',
            activo=True,
        )

        # Servicio de transporte de la empresa
        self.servicio_transporte = Servicio.objects.create(
            empresa=self.empresa,
            nombre='Traslado Aeropuerto y Actividades',
            slug='traslado-dls',
            tipo_servicio=TipoServicio.TRANSPORTE,
            estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
            estrategia_precio=EstrategiaPrecio.POR_RUTA,
            pide_hora=False,
            activo=True,
        )

        # Tarifas de transporte activas para calcular el precio
        self.tarifa_actividad = TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            zona=Zona.CENTRO,
            personas_min=1,
            personas_max=4,
            precio=Decimal('1500.00'),
            activo=True,
        )
        self.tarifa_aeropuerto = TransporteTarifa.objects.create(
            empresa=self.empresa,
            tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            zona='',
            personas_min=1,
            personas_max=4,
            precio=Decimal('3500.00'),
            activo=True,
        )

        # Punto de encuentro registrado en la empresa
        self.punto_encuentro = PuntoEncuentro.objects.create(
            empresa=self.empresa,
            nombre='Hotel Costa Baja',
            zona=Zona.CENTRO,
            activo=True,
        )

        # Servicio regular que no es transporte
        self.servicio_pesca = crear_servicio_pesca(self.empresa, precio_base=Decimal('4500.00'))

    def _datos_base(self, **overrides):
        fecha = (timezone.localdate() + timedelta(days=5)).isoformat()
        datos = {
            'nombre_cliente': 'Alejandra Romero',
            'telefono_cliente': '612 123 4567',
            'correo_cliente': 'alejandra@example.com',
            'fecha': fecha,
            'hora': '08:00',
            'numero_personas': '2',
            'servicio': str(self.servicio_transporte.pk),
            'moneda': Reserva.Moneda.MXN,
            'precio_total': '1500.00',
            'ya_pago': 'no',
            'detalle_transporte-TOTAL_FORMS': '1',
            'detalle_transporte-INITIAL_FORMS': '0',
            'detalle_transporte-0-id': '',
            'detalle_transporte-0-tipo_traslado': '',
            'detalle_transporte-0-punto_encuentro': '',
            'detalle_transporte-0-direccion_personalizada': '',
            'detalle_transporte-0-zona': '',
            'detalle_transporte-0-fecha_regreso': '',
        }
        datos.update(overrides)
        return datos

    def test_get_alta_incluye_inline_y_json_script_acotado(self):
        # Crear otra empresa con su propio servicio de transporte
        otra_sede = Sede.objects.create(
            nombre='Otra Sede', slug='otra-sede-test', zona_horaria='America/Mazatlan', activo=True,
        )
        otra_empresa = Empresa.objects.create(
            sede=otra_sede, nombre='Otra Empresa', slug='otra-empresa-test', activo=True,
        )
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                servicio_ajeno = Servicio.objects.create(
                    empresa=otra_empresa,
                    nombre='Traslado Ajeno',
                    slug='traslado-ajeno',
                    tipo_servicio=TipoServicio.TRANSPORTE,
                    estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
                    estrategia_precio=EstrategiaPrecio.POR_RUTA,
                    activo=True,
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        self.client.force_login(self.usuario_vendedora)
        respuesta = self.client.get(self.url_alta)
        self.assertEqual(respuesta.status_code, 200)

        # Incluye el formset de detalle_transporte
        self.assertContains(respuesta, 'detalle_transporte-TOTAL_FORMS')

        # Incluye el json_script con los ids de servicios de transporte de su empresa
        self.assertContains(respuesta, 'id="servicios-transporte-ids"')
        script_contenido = respuesta.content.decode('utf-8')
        start_tag = '<script id="servicios-transporte-ids" type="application/json">'
        end_tag = '</script>'
        self.assertIn(start_tag, script_contenido)
        json_str = script_contenido.split(start_tag)[1].split(end_tag)[0]
        ids = json.loads(json_str)

        self.assertIn(self.servicio_transporte.pk, ids)
        self.assertNotIn(servicio_ajeno.pk, ids)

    def test_post_exitoso_traslado_redondo_actividad(self):
        self.client.force_login(self.usuario_vendedora)
        datos = self._datos_base(
            nombre_cliente='Beatriz Castro',
            ya_pago='no',
            **{
                'detalle_transporte-0-tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
                'detalle_transporte-0-punto_encuentro': str(self.punto_encuentro.pk),
                'detalle_transporte-0-direccion_personalizada': '',
                'detalle_transporte-0-zona': Zona.CENTRO,
            }
        )
        respuesta = self.client.post(self.url_alta, datos)
        self.assertEqual(respuesta.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Beatriz Castro')
        self.assertEqual(reserva.servicio, self.servicio_transporte)
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)

        # UN DetalleTransporte ligado
        detalles = DetalleTransporte.objects.filter(reserva=reserva)
        self.assertEqual(detalles.count(), 1)
        detalle = detalles.first()
        self.assertEqual(detalle.tipo_traslado, TipoTraslado.REDONDO_ACTIVIDAD)
        self.assertEqual(detalle.punto_encuentro, self.punto_encuentro)
        self.assertEqual(detalle.zona, Zona.CENTRO)
        self.assertEqual(detalle.numero_personas, reserva.numero_personas)

        precio_esperado = sugerir_precio(
            servicio=reserva.servicio,
            numero_personas=reserva.numero_personas,
            moneda=reserva.moneda,
            fecha=reserva.fecha,
            detalle_transporte={
                'tipo_traslado': detalle.tipo_traslado,
                'zona': detalle.zona_efectiva(),
                'numero_personas': detalle.numero_personas,
            },
        )
        self.assertEqual(detalle.precio_calculado, precio_esperado)
        self.assertEqual(detalle.precio_calculado, Decimal('1500.00'))

    def test_post_exitoso_traslado_redondo_aeropuerto(self):
        self.client.force_login(self.usuario_vendedora)
        fecha_regreso = (timezone.localdate() + timedelta(days=10)).isoformat()
        datos = self._datos_base(
            nombre_cliente='Carlos Mendoza',
            ya_pago='no',
            precio_total='3500.00',
            **{
                'detalle_transporte-0-tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
                'detalle_transporte-0-punto_encuentro': '',
                'detalle_transporte-0-direccion_personalizada': 'Condominios Marina Real',
                'detalle_transporte-0-zona': '',
                'detalle_transporte-0-fecha_regreso': fecha_regreso,
            }
        )
        respuesta = self.client.post(self.url_alta, datos)
        self.assertEqual(respuesta.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Carlos Mendoza')
        detalles = DetalleTransporte.objects.filter(reserva=reserva)
        self.assertEqual(detalles.count(), 1)
        detalle = detalles.first()
        self.assertEqual(detalle.tipo_traslado, TipoTraslado.REDONDO_AEROPUERTO)
        self.assertEqual(detalle.direccion_personalizada, 'Condominios Marina Real')
        self.assertEqual(detalle.fecha_regreso.isoformat(), fecha_regreso)
        self.assertEqual(detalle.numero_personas, reserva.numero_personas)

        precio_esperado = sugerir_precio(
            servicio=reserva.servicio,
            numero_personas=reserva.numero_personas,
            moneda=reserva.moneda,
            fecha=reserva.fecha,
            detalle_transporte={
                'tipo_traslado': detalle.tipo_traslado,
                'zona': detalle.zona_efectiva(),
                'numero_personas': detalle.numero_personas,
            },
        )
        self.assertEqual(detalle.precio_calculado, precio_esperado)
        self.assertEqual(detalle.precio_calculado, Decimal('3500.00'))

    def test_post_transporte_con_detalle_vacio_falla(self):
        self.client.force_login(self.usuario_vendedora)
        datos = self._datos_base(
            nombre_cliente='Daniel Ortega',
            **{
                'detalle_transporte-0-tipo_traslado': '',
                'detalle_transporte-0-punto_encuentro': '',
                'detalle_transporte-0-direccion_personalizada': '',
                'detalle_transporte-0-zona': '',
                'detalle_transporte-0-fecha_regreso': '',
            }
        )
        respuesta = self.client.post(self.url_alta, datos)
        self.assertEqual(respuesta.status_code, 200)

        inline_formsets = respuesta.context['inline_admin_formsets']
        errores_formsets = [
            fs.formset.non_form_errors()
            for fs in inline_formsets
            if fs.formset.prefix == 'detalle_transporte'
        ]
        self.assertTrue(any('Falta el detalle del traslado' in str(e) for e in errores_formsets))
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Daniel Ortega').exists())
        self.assertFalse(DetalleTransporte.objects.exists())

    def test_post_no_transporte_con_detalle_lleno_falla(self):
        self.client.force_login(self.usuario_vendedora)
        datos = self._datos_base(
            nombre_cliente='Esteban Vargas',
            servicio=str(self.servicio_pesca.pk),
            precio_total='4500.00',
            **{
                'detalle_transporte-0-tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
                'detalle_transporte-0-punto_encuentro': str(self.punto_encuentro.pk),
                'detalle_transporte-0-direccion_personalizada': '',
                'detalle_transporte-0-zona': Zona.CENTRO,
            }
        )
        respuesta = self.client.post(self.url_alta, datos)
        self.assertEqual(respuesta.status_code, 200)

        inline_formsets = respuesta.context['inline_admin_formsets']
        errores_formsets = [
            fs.formset.non_form_errors()
            for fs in inline_formsets
            if fs.formset.prefix == 'detalle_transporte'
        ]
        self.assertTrue(
            any('El detalle de traslado solo aplica a servicios de transporte.' in str(e) for e in errores_formsets)
        )
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Esteban Vargas').exists())
        self.assertFalse(DetalleTransporte.objects.exists())

    def test_post_no_transporte_con_detalle_vacio_exito(self):
        self.client.force_login(self.usuario_vendedora)
        datos = self._datos_base(
            nombre_cliente='Fernanda Ruiz',
            servicio=str(self.servicio_pesca.pk),
            precio_total='4500.00',
            hora='06:00',  # la pesca solo sale entre 05:00 y 07:00
            **{
                'detalle_transporte-0-tipo_traslado': '',
                'detalle_transporte-0-punto_encuentro': '',
                'detalle_transporte-0-direccion_personalizada': '',
                'detalle_transporte-0-zona': '',
                'detalle_transporte-0-fecha_regreso': '',
            }
        )
        respuesta = self.client.post(self.url_alta, datos)
        self.assertEqual(respuesta.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Fernanda Ruiz')
        self.assertEqual(reserva.servicio, self.servicio_pesca)
        self.assertFalse(DetalleTransporte.objects.filter(reserva=reserva).exists())

    def test_punto_encuentro_de_otra_empresa_rechazado(self):
        otra_sede = Sede.objects.create(
            nombre='Otra Sede Dos', slug='otra-sede-dos', zona_horaria='America/Mazatlan', activo=True,
        )
        otra_empresa = Empresa.objects.create(
            sede=otra_sede, nombre='Otra Empresa Dos', slug='otra-empresa-dos', activo=True,
        )
        self._alcance.__exit__(None, None, None)
        try:
            with scope.con_empresa(otra_empresa):
                punto_ajeno = PuntoEncuentro.objects.create(
                    empresa=otra_empresa,
                    nombre='Hotel Ajeno',
                    zona=Zona.CENTRO,
                    activo=True,
                )
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()

        self.client.force_login(self.usuario_vendedora)
        datos = self._datos_base(
            nombre_cliente='Gabriel Soto',
            **{
                'detalle_transporte-0-tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
                'detalle_transporte-0-punto_encuentro': str(punto_ajeno.pk),
                'detalle_transporte-0-zona': Zona.CENTRO,
            }
        )
        respuesta = self.client.post(self.url_alta, datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Reserva.objects.filter(nombre_cliente='Gabriel Soto').exists())
        self.assertFalse(DetalleTransporte.objects.exists())

    def test_operador_alta_traslado_con_empresa_elegida(self):
        operador = get_user_model().objects.create_user('operador_traslado', password='x', is_staff=True)
        operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        self.client.force_login(operador)

        datos = self._datos_base(
            nombre_cliente='Helena Navarro',
            empresa=str(self.empresa.pk),
            ya_pago='no',
            **{
                'detalle_transporte-0-tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
                'detalle_transporte-0-punto_encuentro': str(self.punto_encuentro.pk),
                'detalle_transporte-0-direccion_personalizada': '',
                'detalle_transporte-0-zona': Zona.CENTRO,
            }
        )
        # El operador no pertenece a una empresa: se sale del alcance que abre EmpresaTestCase
        # mientras dura la peticion y se restaura despues.
        self._alcance.__exit__(None, None, None)
        try:
            respuesta = self.client.post(self.url_alta, datos)
        finally:
            self._alcance = scope.con_empresa(self.empresa)
            self._alcance.__enter__()
        self.assertEqual(respuesta.status_code, 302)

        reserva = Reserva.objects.get(nombre_cliente='Helena Navarro')
        self.assertEqual(reserva.empresa, self.empresa)
        self.assertEqual(reserva.servicio, self.servicio_transporte)

        detalles = DetalleTransporte.objects.filter(reserva=reserva)
        self.assertEqual(detalles.count(), 1)
        detalle = detalles.first()
        self.assertEqual(detalle.tipo_traslado, TipoTraslado.REDONDO_ACTIVIDAD)
        self.assertEqual(detalle.punto_encuentro, self.punto_encuentro)
        self.assertEqual(detalle.numero_personas, reserva.numero_personas)
        self.assertEqual(detalle.precio_calculado, Decimal('1500.00'))

    def test_editar_un_traslado_antiguo_sin_detalle_no_exige_el_detalle(self):
        # Una reserva de transporte creada antes de este flujo no tiene detalle: corregir
        # un dato (p. ej. el telefono) no debe pedirselo.
        reserva = crear_reserva(
            self.empresa, servicio=self.servicio_transporte, hora=None,
            nombre_cliente='Ofelia Campos',
        )
        self.client.force_login(self.usuario_vendedora)
        url = reverse('admin:bookings_reserva_change', args=[reserva.pk])
        datos = {
            'nombre_cliente': 'Ofelia Campos',
            'telefono_cliente': '612 999 8888',
            'correo_cliente': reserva.correo_cliente,
            'fecha': reserva.fecha.isoformat(),
            'numero_personas': str(reserva.numero_personas),
            'servicio': str(self.servicio_transporte.pk),
            'moneda': reserva.moneda,
            'estado': reserva.estado,
            'canal_origen': reserva.canal_origen,
            'forma_pago': reserva.forma_pago or '',
            'precio_total': str(reserva.precio_total or ''),
            'detalle_transporte-TOTAL_FORMS': '0',
            'detalle_transporte-INITIAL_FORMS': '0',
        }

        respuesta = self.client.post(url, datos)

        errores = respuesta.context['adminform'].form.errors if respuesta.status_code == 200 else None
        self.assertEqual(respuesta.status_code, 302, errores)
        reserva.refresh_from_db()
        self.assertEqual(reserva.telefono_cliente, '612 999 8888')

    def test_edicion_reserva_transporte_mantiene_detalle(self):
        reserva = crear_reserva(
            self.empresa,
            servicio=self.servicio_transporte,
            hora=None,
            nombre_cliente='Ignacio Paredes',
        )
        detalle = DetalleTransporte.objects.create(
            reserva=reserva,
            tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD,
            punto_encuentro=self.punto_encuentro,
            zona=Zona.CENTRO,
            numero_personas=2,
            precio_calculado=Decimal('1500.00'),
        )
        url_cambio = reverse('admin:bookings_reserva_change', args=[reserva.pk])

        self.client.force_login(self.usuario_vendedora)

        resp_get = self.client.get(url_cambio)
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn('detalle_transporte', [f.formset.prefix for f in resp_get.context['inline_admin_formsets']])
        self.assertContains(resp_get, 'tipo_traslado')

        datos_cambio = {
            'nombre_cliente': reserva.nombre_cliente,
            'telefono_cliente': reserva.telefono_cliente,
            'correo_cliente': reserva.correo_cliente,
            'fecha': reserva.fecha.isoformat(),
            'numero_personas': reserva.numero_personas,
            'servicio': self.servicio_transporte.pk,
            'canal_origen': reserva.canal_origen,
            'estado': reserva.estado,
            'moneda': reserva.moneda,
            'detalle_transporte-TOTAL_FORMS': '1',
            'detalle_transporte-INITIAL_FORMS': '1',
            'detalle_transporte-0-id': str(detalle.pk),
            'detalle_transporte-0-tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
            'detalle_transporte-0-punto_encuentro': '',
            'detalle_transporte-0-direccion_personalizada': 'Hotel Vista Coral',
            'detalle_transporte-0-zona': Zona.CENTRO,
        }
        resp_post = self.client.post(url_cambio, datos_cambio)
        self.assertEqual(resp_post.status_code, 302)

        detalle.refresh_from_db()
        self.assertEqual(detalle.direccion_personalizada, 'Hotel Vista Coral')
        self.assertIsNone(detalle.punto_encuentro)
        self.assertEqual(detalle.zona, Zona.CENTRO)

    def test_post_transporte_con_pago_y_sin_precio_muestra_mensaje_especifico(self):
        self.client.force_login(self.usuario_vendedora)
        datos = self._datos_base(
            nombre_cliente='Julia Rios',
            precio_total='',
            ya_pago='todo_transferencia',
            **{
                'detalle_transporte-0-tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
                'detalle_transporte-0-punto_encuentro': str(self.punto_encuentro.pk),
                'detalle_transporte-0-zona': Zona.CENTRO,
            }
        )
        respuesta = self.client.post(self.url_alta, datos)
        self.assertEqual(respuesta.status_code, 200)
        form = respuesta.context['adminform'].form
        self.assertIn('precio_total', form.errors)
        self.assertIn(
            'Escribe el precio total o elige el tipo de traslado para que se sugiera.',
            form.errors['precio_total'],
        )
