from datetime import timedelta, time
from decimal import Decimal
from html import unescape
import re
from unittest import mock

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.bookings.models import DetalleTransporte, Reserva, Vendedora
from apps.bookings.tests import crear_reserva
from apps.fleet.models import PuntoEncuentro, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede
from apps.testing import EmpresaTestCase


class ReservasListaTests(EmpresaTestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.url = reverse('admin:bookings_reserva_changelist')
        self.client.force_login(self.crear_vendedora())

    def reserva(self, nombre, dias, estado=Reserva.Estado.PAGADA, **campos):
        return crear_reserva(self.empresa, nombre_cliente=nombre,
                             fecha=self.hoy + timedelta(days=dias), estado=estado, **campos)

    def test_pestanas_orden_y_alcances(self):
        ayer = self.reserva('Ayer', -1)
        hoy = self.reserva('Hoy prueba', 0, hora=time(7))
        temprano = self.reserva('Temprano', 1, hora=time(5))
        tarde = self.reserva('Tarde', 1, hora=time(7))
        pendiente = self.reserva('Pendiente', 1, Reserva.Estado.PENDIENTE_PAGO)
        cancelada = self.reserva('Cancelada', 1, Reserva.Estado.CANCELADA)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list],
                         [hoy.pk, temprano.pk, tarde.pk])
        pestanas = {p['clave']: p for p in respuesta.context['reservas_pestanas']}
        self.assertEqual({k: p['conteo'] for k, p in pestanas.items()}, {
            'proximas': 3, 'hoy': 1, 'manana': 2, 'por_cobrar': 0,
            'atencion': 0, 'pasadas': 1, 'todas': 6,
        })
        self.assertTrue(pestanas['proximas']['activa'])
        self.assertContains(respuesta, 'agenda-pestanas')
        self.assertContains(respuesta, 'bookings/reservas-nuevas.js')
        self.assertIn('cliente', respuesta.context['cl'].list_display_links)
        for vista, ids in [('hoy', [hoy.pk]), ('manana', [temprano.pk, tarde.pk]),
                           ('todas', [tarde.pk, cancelada.pk, pendiente.pk, temprano.pk, hoy.pk, ayer.pk])]:
            respuesta = self.client.get(self.url, {'vista': vista})
            self.assertEqual([r.pk for r in respuesta.context['cl'].result_list], ids)

    def test_cobro_y_atencion(self):
        debe = self.reserva('Debe efectivo', 0, forma_pago=Reserva.FormaPago.ANTICIPO,
                            precio_total=Decimal('516.00'), monto_pagado=Decimal('154.80'))
        futuro = self.reserva('Futuro tranquilo', 3, forma_pago=Reserva.FormaPago.ANTICIPO,
                              precio_total=Decimal('516.00'), monto_pagado=Decimal('154.80'))
        descuadre = self.reserva('Descuadre', 0, forma_pago=Reserva.FormaPago.COMPLETO,
                                 precio_total=Decimal('1000'), monto_pagado=Decimal('900'))
        devolucion = self.reserva('Devolución', -1, Reserva.Estado.CANCELADA,
                                  precio_total=Decimal('1200'), monto_pagado=Decimal('1200'))
        self.reserva('Sin pagar prueba', 2, Reserva.Estado.PENDIENTE_PAGO)
        respuesta = self.client.get(self.url, {'vista': 'por_cobrar'})
        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list], [debe.pk])
        self.assertEqual(respuesta.context['reservas_pestanas'][3]['conteo'], 1)
        self.assertContains(respuesta, 'Debe 361.20 MXN en efectivo')
        model_admin = admin.site._registry[Reserva]
        self.assertNotIn('reservas-cobro-urgente', str(model_admin.cobro(futuro)))
        self.assertIn('reservas-cobro-urgente', str(model_admin.cobro(debe)))
        respuesta = self.client.get(self.url, {'vista': 'atencion'})
        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list], [devolucion.pk])
        self.assertContains(respuesta, 'Falta devolver 1,200 MXN')
        respuesta = self.client.get(self.url, {'vista': 'todas'})
        self.assertContains(respuesta, 'Sin pagar')
        self.assertContains(respuesta, 'Descuadre de 100 MXN')
        self.assertContains(respuesta, 'Futuro tranquilo')
        self.assertContains(respuesta, 'Debe 361.20 MXN en efectivo')

    def test_transferencia_total_y_parcial_en_lista_y_cabecera(self):
        total = self.reserva('Transferencia completa', 1,
                             precio_total=Decimal('4500.00'), monto_transferencia=Decimal('4500.00'))
        parcial = self.reserva('Transferencia parcial', 1,
                               forma_pago=Reserva.FormaPago.ANTICIPO,
                               precio_total=Decimal('4500.00'), monto_pagado=Decimal('1350.00'),
                               monto_transferencia=Decimal('2000.00'))
        model_admin = admin.site._registry[Reserva]
        self.assertEqual(model_admin.cobro(total), 'Pagado')
        self.assertEqual(model_admin.cobro(parcial), 'Debe 1,150 MXN en efectivo')
        respuesta = self.client.get(self.url, {'vista': 'proximas'})
        self.assertContains(respuesta, 'Pagado')
        self.assertContains(respuesta, 'Debe 1,150 MXN en efectivo')
        cabecera = self.client.get(reverse('admin:bookings_reserva_change', args=[total.pk]))
        self.assertEqual(cabecera.context['resumen_reserva']['cobro'], 'Pagado')
        cabecera = self.client.get(reverse('admin:bookings_reserva_change', args=[parcial.pk]))
        self.assertEqual(cabecera.context['resumen_reserva']['cobro'], 'Debe 1,150 MXN en efectivo')

    def test_por_cobrar_desconte_transferencia_en_sql(self):
        self.reserva('Ya cubierta', 1, forma_pago=Reserva.FormaPago.ANTICIPO,
                     precio_total=Decimal('4500.00'), monto_pagado=Decimal('1350.00'),
                     monto_transferencia=Decimal('3150.00'))
        pendiente = self.reserva('Aun debe', 1, forma_pago=Reserva.FormaPago.ANTICIPO,
                                  precio_total=Decimal('4500.00'), monto_pagado=Decimal('1350.00'),
                                  monto_transferencia=Decimal('2000.00'))
        respuesta = self.client.get(self.url, {'vista': 'por_cobrar'})
        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list], [pendiente.pk])

    def test_busqueda_filtros_paginacion_y_agrupacion(self):
        self.reserva('Cliente lunes', 1)
        self.reserva('Cliente martes', 2)
        respuesta = self.client.get(self.url, {'vista': 'proximas', 'q': 'Cliente'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'reservas-dia')
        self.assertContains(respuesta, 'vista=proximas')
        self.assertContains(respuesta, 'q=Cliente')
        respuesta = self.client.get(self.url, {'vista': 'todas', 'estado__exact': 'pagada'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['cl'].result_count, 2)
        self.assertNotContains(respuesta, 'reservas-dia')
        respuesta = self.client.get(self.url, {'vista': 'proximas', 'o': '2'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'reservas-dia')
        with mock.patch.object(admin.site._registry[Reserva], 'list_per_page', 1):
            respuesta = self.client.get(self.url, {'vista': 'proximas', 'p': '1'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'vista=proximas')
        self.assertContains(respuesta, 'reservas-dia')

    def test_filtros_frecuentes_antes_de_mas_filtros_y_ayuda_de_busqueda(self):
        vendedora = self.crear_vendedora(username='segunda-vendedora')
        Vendedora.objects.create(usuario=vendedora, empresa=self.empresa, codigo='segunda')
        respuesta = self.client.get(self.url, {'vista': 'todas'})
        html = respuesta.content.decode()
        self.assertContains(respuesta, 'Busca por nombre, tel\u00e9fono o correo del cliente')
        self.assertIn('id="reservas-mas-filtros"', html)
        self.assertNotIn('id="reservas-mas-filtros" open', html)
        lateral = unescape(html[html.index('id="changelist-filter"'):])
        titulos = [re.sub(r'\s+', ' ', titulo).strip().lower()
                   for titulo in re.findall(r'<h3[^>]*>(.*?)</h3>', lateral, re.S)]
        # La disputa es de los filtros a la vista: es lo que hay que ver antes de que
        # el viaje salga, no algo que se busque dentro de \u00abMas filtros\u00bb.
        self.assertEqual(titulos[:5], ['por estado', 'por canal origen', 'por vendedora',
                                      'por forma pago', 'por en disputa'])
        self.assertEqual(titulos[5:7], ['por llegada',
                                       'por requiere atenci\u00f3n (devoluci\u00f3n)'])
        antes, despues = lateral.split('id="reservas-mas-filtros"', 1)
        self.assertEqual(len(re.findall(r'<h3[^>]*>', antes)), 5)
        self.assertIn('llegada', despues)

    def test_filtro_avanzado_activo_abre_seccion_y_muestra_cantidad(self):
        self.reserva('Reserva reciente', 1)
        respuesta = self.client.get(self.url, {'vista': 'todas', 'llegada': 'recientes',
                                                'requiere_atencion': 'si'})
        self.assertContains(respuesta, 'id="reservas-mas-filtros" open')
        self.assertRegex(respuesta.content.decode(), r'M&aacute;s filtros\s*\(2\)')

    def test_deuda_pasada_usd_y_devolucion_parcial(self):
        atrasada = self.reserva('Saldo atrasado', -2,
                                forma_pago=Reserva.FormaPago.ANTICIPO,
                                moneda=Reserva.Moneda.USD,
                                precio_total=Decimal('200'), monto_pagado=Decimal('60'))
        parcial = self.reserva('Devolución parcial', -3, Reserva.Estado.CANCELADA,
                               monto_pagado=Decimal('200'), monto_reembolsado=Decimal('50'))
        respuesta = self.client.get(self.url, {'vista': 'por_cobrar'})
        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list], [atrasada.pk])
        self.assertContains(respuesta, 'Debe 140 USD en efectivo')
        respuesta = self.client.get(self.url, {'vista': 'atencion'})
        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list], [parcial.pk])
        self.assertContains(respuesta, 'Falta devolver 150 MXN')

    def test_columnas_servicio_traslado_asignacion_y_hora_nula(self):
        servicio = Servicio.objects.create(empresa=self.empresa, nombre='Traslado privado',
                                            slug='traslado-prueba', tipo_servicio='transporte',
                                            estrategia_cupo='bajo_demanda', pide_hora=False)
        reserva = self.reserva('Transporte prueba', 1, servicio=servicio, hora=None)
        punto = PuntoEncuentro.objects.create(empresa=self.empresa, nombre='Hotel Azul', zona='centro')
        DetalleTransporte.objects.create(reserva=reserva, tipo_traslado='redondo_actividad',
                                         zona='centro', punto_encuentro=punto)
        respuesta = self.client.get(self.url, {'vista': 'manana'})
        self.assertContains(respuesta, 'Traslado privado')
        self.assertContains(respuesta, 'Redondo actividad')
        self.assertContains(respuesta, 'Centro')
        self.assertContains(respuesta, 'Hotel Azul')
        # Un traslado no se reparte en la Agenda: "Sin panga" aqui seria un pendiente falso.
        self.assertNotContains(respuesta, 'Sin panga')
        self.assertNotContains(respuesta, 'None')
        self.assertEqual(len(respuesta.context['cl'].list_display), 9)  # casilla + ocho columnas

    def test_el_menu_de_acciones_no_se_corrompe_y_eliminar_va_al_final(self):
        self.client.force_login(self.crear_jefe())

        acciones = [a for a, _ in self.client.get(self.url).context['action_form'].fields['action'].choices]
        etiquetas = dict(self.client.get(self.url).context['action_form'].fields['action'].choices)

        self.assertEqual(etiquetas[''], 'Elegir acción')
        self.assertEqual(acciones[-1], 'delete_selected')
        self.assertEqual(acciones[-2], 'cancelar_por_mal_clima')
        self.assertIn('(el 70% restante)', etiquetas['registrar_liquidacion_en_efectivo'])
        self.assertNotIn('verbose_name', ' '.join(map(str, etiquetas.values())))

    def test_los_encabezados_dicen_cliente_y_personas(self):
        self.reserva('Ana', 1)
        html = self.client.get(self.url).content.decode()

        self.assertIn('Cliente', html)
        self.assertNotIn('Nombre cliente', html)
        self.assertNotIn('Numero personas', html)

    def test_pasadas_es_el_historico_de_la_mas_reciente_a_la_mas_antigua(self):
        hace_dos = self.reserva('Hace dos dias', -2)
        ayer = self.reserva('Ayer', -1)
        cancelada = self.reserva('Cancelada vieja', -3, Reserva.Estado.CANCELADA)
        self.reserva('Checkout sin pagar', -1, Reserva.Estado.PENDIENTE_PAGO)
        self.reserva('Futura', 1)

        respuesta = self.client.get(self.url, {'vista': 'pasadas'})

        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list],
                         [ayer.pk, hace_dos.pk, cancelada.pk])
        self.assertTrue(
            {p['clave']: p for p in respuesta.context['reservas_pestanas']}['pasadas']['activa'])

    def test_un_dia_concreto_muestra_todo_lo_de_ese_dia_con_canceladas(self):
        dia = self.hoy + timedelta(days=5)
        tarde = self.reserva('Tarde', 5, hora=time(7))
        temprano = self.reserva('Temprano', 5, hora=time(5))
        cancelada = self.reserva('Cancelada', 5, Reserva.Estado.CANCELADA, hora=time(6))
        self.reserva('Sin pagar', 5, Reserva.Estado.PENDIENTE_PAGO)
        self.reserva('Otro dia', 6)

        respuesta = self.client.get(self.url, {'dia': dia.isoformat()})

        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list],
                         [temprano.pk, cancelada.pk, tarde.pk])
        self.assertEqual(respuesta.context['reservas_dia']['conteo'], 3)
        self.assertTrue(respuesta.context['reservas_dia']['activo'])
        self.assertFalse(any(p['activa'] for p in respuesta.context['reservas_pestanas']))

    def test_las_flechas_van_al_dia_anterior_y_siguiente(self):
        dia = self.hoy + timedelta(days=5)

        selector = self.client.get(self.url, {'dia': dia.isoformat()}).context['reservas_dia']

        self.assertIn(f'dia={(dia - timedelta(days=1)).isoformat()}', selector['anterior'])
        self.assertIn(f'dia={(dia + timedelta(days=1)).isoformat()}', selector['siguiente'])
        # sin dia elegido las flechas parten de hoy
        selector = self.client.get(self.url).context['reservas_dia']
        self.assertFalse(selector['activo'])
        self.assertIn(f'dia={(self.hoy - timedelta(days=1)).isoformat()}', selector['anterior'])

    def test_un_dia_invalido_se_ignora(self):
        respuesta = self.client.get(self.url, {'dia': 'no-es-fecha'})

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context['reservas_dia']['activo'])

    def test_el_dia_conserva_la_busqueda_y_los_filtros(self):
        self.reserva('Ana Ruiz', 5, correo_cliente='ana.ruiz@example.com')
        self.reserva('Beto Soto', 5, correo_cliente='beto.soto@example.com')

        respuesta = self.client.get(self.url, {
            'dia': (self.hoy + timedelta(days=5)).isoformat(), 'q': 'Ana'})

        self.assertEqual([r.nombre_cliente for r in respuesta.context['cl'].result_list], ['Ana Ruiz'])
        self.assertIn(('q', 'Ana'), respuesta.context['reservas_dia']['otros_parametros'])
        self.assertIn('q=Ana', respuesta.context['reservas_dia']['siguiente'])

    def test_quitar_el_dia_vuelve_a_proximas(self):
        selector = self.client.get(self.url, {'dia': self.hoy.isoformat()}).context['reservas_dia']

        self.assertIn('vista=proximas', selector['quitar'])
        self.assertNotIn('dia=', selector['quitar'])

    def test_las_pestanas_van_dentro_de_la_tarjeta_de_busqueda_y_no_sobre_la_tabla(self):
        self.reserva('Ana', 1)
        html = self.client.get(self.url).content.decode()

        # La tarjeta de busqueda (con su relleno) va antes del formulario de resultados;
        # las pestañas deben quedar antes de ese formulario, no dentro de el.
        self.assertLess(html.index('agenda-pestanas'), html.index('id="changelist-form"'))

    def test_el_conteo_del_dia_dice_que_son_reservas(self):
        self.reserva('Ana', 5)
        html = self.client.get(self.url, {'dia': (self.hoy + timedelta(days=5)).isoformat()}).content.decode()

        self.assertRegex(html, r'1 reserva\s*<')
        self.assertIn('data-dia-quitar', html)

    def test_el_panel_ya_no_ofrece_filtros_de_fecha(self):
        self.reserva('Ana', 1)
        html = self.client.get(self.url, {'vista': 'todas'}).content.decode()

        self.assertNotIn('Por fecha', html)
        self.assertNotIn('fecha__year', html)
        self.assertContains(self.client.get(self.url), 'data-dia-selector')

    def test_una_reserva_de_pesca_sin_panga_si_lo_dice(self):
        self.reserva('Pesca sin panga', 1)

        self.assertContains(self.client.get(self.url, {'vista': 'manana'}), 'Sin panga · Sin capitán')

    def test_el_conteo_solo_va_en_rojo_si_es_accionable(self):
        self.reserva('Debe efectivo', 0, forma_pago=Reserva.FormaPago.ANTICIPO,
                     precio_total=Decimal('516.00'), monto_pagado=Decimal('154.80'))

        pestanas = {p['clave']: p for p in self.client.get(self.url).context['reservas_pestanas']}

        self.assertTrue(pestanas['por_cobrar']['urgente'])
        for clave in ('proximas', 'hoy', 'manana', 'atencion', 'pasadas', 'todas'):
            self.assertFalse(pestanas[clave]['urgente'], clave)

    def test_ordenar_cuando_invierte_fecha_y_hora(self):
        temprano = self.reserva('Hora temprana', 1, hora=time(5))
        tarde = self.reserva('Hora tarde', 1, hora=time(7))
        for orden, esperado in [('1', [temprano.pk, tarde.pk]),
                                ('-1', [tarde.pk, temprano.pk])]:
            respuesta = self.client.get(self.url, {'vista': 'todas', 'o': orden})
            self.assertEqual([r.pk for r in respuesta.context['cl'].result_list], esperado)

    def test_consultas_de_lista_no_crecen_por_fila(self):
        self.reserva('Primer viaje', 1)
        with CaptureQueriesContext(connection) as consultas_una:
            self.client.get(self.url, {'vista': 'proximas'})
        for nombre in ('Ana', 'Beto', 'Carla', 'Diana', 'Elena', 'Fabián', 'Gabriela'):
            self.reserva(f'Viaje {nombre}', 1)
        with CaptureQueriesContext(connection) as consultas_ocho:
            self.client.get(self.url, {'vista': 'proximas'})
        self.assertLessEqual(len(consultas_ocho), len(consultas_una) + 2)


class ReservasListaOperadorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        sede = Sede.objects.create(nombre='Sede reservas', slug='sede-reservas')
        cls.a = Empresa.objects.create(sede=sede, nombre='Empresa A', slug='empresa-a')
        cls.b = Empresa.objects.create(sede=sede, nombre='Empresa B', slug='empresa-b')
        cls.operador = get_user_model().objects.create_user('op-reservas', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        cls.vendedora_b = get_user_model().objects.create_user(
            'vendedora-b-reservas', password='x', is_staff=True)
        cls.vendedora_b.groups.add(Group.objects.get(name='Vendedora'))
        MembresiaEmpresa.objects.create(user=cls.vendedora_b, empresa=cls.b,
                                        rol=MembresiaEmpresa.Rol.VENDEDORA)
        with scope.como_operador_plataforma():
            cls.ra = crear_reserva(cls.a, nombre_cliente='Cliente Empresa A', estado=Reserva.Estado.PAGADA)
            cls.rb = crear_reserva(cls.b, nombre_cliente='Cliente Empresa B', estado=Reserva.Estado.PAGADA)

    def test_operador_ve_ambas_empresas_y_sus_conteos(self):
        self.client.force_login(self.operador)
        respuesta = self.client.get(reverse('admin:bookings_reserva_changelist'), {'vista': 'proximas'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['reservas_pestanas'][0]['conteo'], 2)
        self.assertContains(respuesta, 'Cliente Empresa A')
        self.assertContains(respuesta, 'Cliente Empresa B')

    def test_vendedora_de_otra_empresa_solo_ve_sus_filas_y_conteos(self):
        self.client.force_login(self.vendedora_b)
        respuesta = self.client.get(reverse('admin:bookings_reserva_changelist'),
                                    {'vista': 'proximas'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['reservas_pestanas'][0]['conteo'], 1)
        self.assertEqual([r.pk for r in respuesta.context['cl'].result_list], [self.rb.pk])
        self.assertNotContains(respuesta, 'Cliente Empresa A')

