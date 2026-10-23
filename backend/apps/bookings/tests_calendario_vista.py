"""La pantalla `/admin/calendario/`: permisos, estado en la URL y las tres vistas.

Las fechas son relativas a hoy (la vista lee `timezone.localdate()`), asi que las
pruebas no caducan. `desde` ancla el periodo; la semana siempre empieza en lunes.
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import CupoDiario, Reserva, ViajeTransporte
from apps.fleet.models import Embarcacion, Paquete, PaqueteServicio, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede
from apps.testing import crear_flota

User = get_user_model()


def lunes_de(fecha):
    return fecha - timedelta(days=fecha.weekday())


class CalendarioVistaBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.url = reverse('calendario')
        cls.hoy = timezone.localdate()
        cls.sede = Sede.objects.create(nombre='Sede vista', slug='sede-vista')
        cls.alfa = Empresa.objects.create(sede=cls.sede, nombre='Alfa Pesca', slug='alfa-pesca')
        cls.beta = Empresa.objects.create(sede=cls.sede, nombre='Beta Travel', slug='beta-travel')
        cls.vendedora = cls.usuario('vendedora-alfa', cls.alfa, MembresiaEmpresa.Rol.VENDEDORA)
        cls.jefe_beta = cls.usuario('jefe-beta', cls.beta, MembresiaEmpresa.Rol.JEFE)
        cls.operador = User.objects.create_user('operador-cal', password='x', is_staff=True)
        cls.operador.groups.add(Group.objects.get(name='OperadorPlataforma'))
        cls.sin_permiso = cls.usuario('sin-permiso', cls.alfa, MembresiaEmpresa.Rol.VENDEDORA)
        cls.sin_permiso.groups.clear()

        with scope.como_operador_plataforma():
            cls.pesca_alfa = Servicio.objects.create(
                empresa=cls.alfa, nombre='Pesca', slug='pesca-alfa', tipo_servicio='pesca',
            )
            cls.pesca_beta = Servicio.objects.create(
                empresa=cls.beta, nombre='Pesca', slug='pesca-beta', tipo_servicio='pesca',
            )
            cls.hotel_beta = Servicio.objects.create(
                empresa=cls.beta, nombre='Cabaña', slug='cabana-beta', tipo_servicio='hospedaje',
                estrategia_cupo='por_noche', estrategia_precio='por_noche',
            )
            cls.traslado_beta = Servicio.objects.create(
                empresa=cls.beta, nombre='Traslado', slug='traslado-beta', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda',
            )

    @staticmethod
    def usuario(nombre, empresa, rol):
        usuario = User.objects.create_user(nombre, password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=usuario, empresa=empresa, rol=rol)
        return usuario

    @classmethod
    def reserva(cls, empresa, servicio, nombre, fecha, **extra):
        datos = dict(
            empresa=empresa, servicio=servicio, fecha=fecha, hora=time(6), numero_personas=2,
            nombre_cliente=nombre, telefono_cliente='+5216121234567', correo_cliente='c@example.com',
            canal_origen=Reserva.CanalOrigen.WHATSAPP, estado=Reserva.Estado.PAGADA,
        )
        datos.update(extra)
        with scope.como_operador_plataforma():
            return Reserva.objects.create(**datos)

    def ver(self, usuario, **params):
        self.client.force_login(usuario)
        return self.client.get(self.url, params)


class PermisosTests(CalendarioVistaBase):
    def test_un_anonimo_va_al_login(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('/admin/login/', respuesta['Location'])

    def test_staff_sin_ver_reservas_recibe_403(self):
        self.assertEqual(self.ver(self.sin_permiso).status_code, 403)

    def test_la_vendedora_entra_y_ve_solo_lo_de_su_empresa(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Cliente Alfa', self.hoy + timedelta(days=1))
        self.reserva(self.beta, self.pesca_beta, 'Cliente Beta', self.hoy + timedelta(days=1))

        respuesta = self.ver(self.vendedora, desde=lunes_de(self.hoy).isoformat(), vista='mes')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Cliente Alfa')
        self.assertNotContains(respuesta, 'Cliente Beta')
        self.assertNotContains(respuesta, 'name="empresa"')  # el selector es del operador
        self.assertEqual(respuesta.context['empresa'], self.alfa)

    def test_la_vendedora_no_puede_pedir_la_empresa_de_otro(self):
        self.reserva(self.beta, self.pesca_beta, 'Cliente Beta', self.hoy)

        respuesta = self.ver(self.vendedora, empresa='beta-travel', vista='mes')

        self.assertNotContains(respuesta, 'Cliente Beta')
        self.assertEqual(respuesta.context['empresa'], self.alfa)

    def test_el_jefe_ve_su_empresa(self):
        self.reserva(self.beta, self.pesca_beta, 'Cliente Beta', self.hoy, estado=Reserva.Estado.COMPLETADA)

        self.assertContains(self.ver(self.jefe_beta, vista='dia'), 'Cliente Beta')


class OperadorTests(CalendarioVistaBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.reserva(cls.alfa, cls.pesca_alfa, 'Cliente Alfa', cls.hoy)
        cls.reserva(cls.beta, cls.pesca_beta, 'Cliente Beta', cls.hoy)

    def test_abre_en_la_primera_empresa_por_nombre_y_ofrece_todas(self):
        respuesta = self.ver(self.operador, vista='dia')

        self.assertEqual(respuesta.context['empresa'], self.alfa)
        self.assertContains(respuesta, 'name="empresa"')
        self.assertContains(respuesta, 'Todas')
        self.assertContains(respuesta, 'Beta Travel')
        self.assertContains(respuesta, 'Cliente Alfa')
        self.assertNotContains(respuesta, 'Cliente Beta')

    def test_elegir_otra_empresa(self):
        respuesta = self.ver(self.operador, vista='dia', empresa='beta-travel')

        self.assertContains(respuesta, 'Cliente Beta')
        self.assertNotContains(respuesta, 'Cliente Alfa')

    def test_todas_junta_las_empresas_y_pone_la_empresa_como_texto_corto(self):
        respuesta = self.ver(self.operador, vista='dia', empresa='todas')

        self.assertIsNone(respuesta.context['empresa'])
        self.assertContains(respuesta, 'Cliente Alfa')
        self.assertContains(respuesta, 'Cliente Beta')
        self.assertContains(respuesta, 'data-empresa-corta')

    def test_una_sola_empresa_no_repite_su_nombre_en_cada_renglon(self):
        self.assertNotContains(self.ver(self.operador, vista='dia'), 'data-empresa-corta')

    def test_una_empresa_que_no_existe_cae_en_la_primera(self):
        respuesta = self.ver(self.operador, empresa='no-existe')

        self.assertEqual(respuesta.context['empresa'], self.alfa)


class EstadoEnLaUrlTests(CalendarioVistaBase):
    def test_por_defecto_es_la_semana_actual_que_empieza_en_lunes(self):
        respuesta = self.ver(self.vendedora)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['vista'], 'semana')
        self.assertEqual(respuesta.context['desde'], lunes_de(self.hoy))
        self.assertEqual(respuesta.context['hasta'], lunes_de(self.hoy) + timedelta(days=6))

    def test_cualquier_dia_de_la_semana_ancla_su_lunes(self):
        miercoles = date(2026, 10, 21)

        respuesta = self.ver(self.vendedora, desde=miercoles.isoformat())

        self.assertEqual(respuesta.context['desde'], date(2026, 10, 19))

    def test_el_mes_cubre_semanas_completas_de_lunes_a_domingo(self):
        respuesta = self.ver(self.vendedora, vista='mes', desde='2026-10-15')

        self.assertEqual(respuesta.context['desde'], date(2026, 9, 28))  # octubre 2026 empieza en jueves
        self.assertEqual(respuesta.context['hasta'], date(2026, 11, 1))
        self.assertEqual(len(respuesta.context['mes']['semanas']), 5)

    def test_un_mes_de_seis_semanas(self):
        respuesta = self.ver(self.vendedora, vista='mes', desde='2026-08-10')  # agosto 2026: sabado a lunes

        self.assertEqual(len(respuesta.context['mes']['semanas']), 6)

    def test_la_vista_dia_es_un_solo_dia(self):
        respuesta = self.ver(self.vendedora, vista='dia', desde='2026-10-21')

        self.assertEqual((respuesta.context['desde'], respuesta.context['hasta']), (date(2026, 10, 21), date(2026, 10, 21)))

    def test_parametros_rotos_caen_en_los_valores_por_defecto(self):
        respuesta = self.ver(self.vendedora, vista='anual', desde='no-es-fecha', canceladas='quizas', empresa='x')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['vista'], 'semana')
        self.assertEqual(respuesta.context['desde'], lunes_de(self.hoy))
        self.assertFalse(respuesta.context['canceladas'])

    def test_una_fecha_imposible_tambien_cae_en_hoy(self):
        respuesta = self.ver(self.vendedora, desde='2026-02-31')

        self.assertEqual(respuesta.context['desde'], lunes_de(self.hoy))

    def test_las_tres_vistas_responden(self):
        for vista in ('dia', 'semana', 'mes'):
            with self.subTest(vista=vista):
                respuesta = self.ver(self.vendedora, vista=vista)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, f'data-calendario-vista="{vista}"')

    def test_anterior_hoy_y_siguiente_conservan_el_estado(self):
        respuesta = self.ver(self.vendedora, vista='semana', desde='2026-10-21', canceladas='1')
        ctx = respuesta.context

        self.assertIn('desde=2026-10-12', ctx['anterior_url'])
        self.assertIn('desde=2026-10-26', ctx['siguiente_url'])
        self.assertNotIn('desde=', ctx['hoy_url'])
        for url in (ctx['anterior_url'], ctx['hoy_url'], ctx['siguiente_url']):
            self.assertIn('vista=semana', url)
            self.assertIn('canceladas=1', url)

    def test_anterior_y_siguiente_del_mes_y_del_dia(self):
        mes = self.ver(self.vendedora, vista='mes', desde='2026-01-15').context
        dia = self.ver(self.vendedora, vista='dia', desde='2026-03-01').context

        self.assertIn('desde=2025-12-01', mes['anterior_url'])
        self.assertIn('desde=2026-02-01', mes['siguiente_url'])
        self.assertIn('desde=2026-02-28', dia['anterior_url'])
        self.assertIn('desde=2026-03-02', dia['siguiente_url'])

    def test_el_operador_conserva_la_empresa_en_los_enlaces(self):
        ctx = self.ver(self.operador, empresa='beta-travel').context

        self.assertIn('empresa=beta-travel', ctx['siguiente_url'])

    def test_el_interruptor_de_canceladas_enciende_y_apaga(self):
        apagado = self.ver(self.vendedora, vista='mes', desde='2026-10-15').context
        encendido = self.ver(self.vendedora, vista='mes', desde='2026-10-15', canceladas='1').context

        self.assertIn('canceladas=1', apagado['canceladas_url'])
        self.assertNotIn('canceladas', encendido['canceladas_url'])
        self.assertIn('desde=2026-10-01', apagado['canceladas_url'])


class ContenidoTests(CalendarioVistaBase):
    def setUp(self):
        self.lunes = lunes_de(self.hoy)

    def semana(self, usuario=None, **params):
        return self.ver(usuario or self.vendedora, desde=self.lunes.isoformat(), **params)

    def test_pendiente_de_pago_nunca_se_ve(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Abandonado', self.lunes, estado=Reserva.Estado.PENDIENTE_PAGO)

        self.assertNotContains(self.semana(canceladas='1'), 'Abandonado')

    def test_la_cancelada_solo_con_el_interruptor(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Cancelado Pérez', self.lunes, estado=Reserva.Estado.CANCELADA)

        self.assertNotContains(self.semana(), 'Cancelado Pérez')
        self.assertContains(self.semana(canceladas='1'), 'Cancelado Pérez')

    def test_periodo_vacio_conserva_el_marco_y_lo_dice_en_una_frase(self):
        respuesta = self.semana()

        self.assertContains(respuesta, 'Sin reservas esta semana')
        self.assertContains(respuesta, 'data-calendario-vista="semana"')
        self.assertContains(respuesta, 'Sin reservas del')  # el hallazgo

    def test_el_vacio_dice_el_periodo_de_cada_vista(self):
        self.assertContains(self.ver(self.vendedora, vista='mes'), 'Sin reservas este mes')
        self.assertContains(self.ver(self.vendedora, vista='dia'), 'Sin reservas este día')

    def test_el_hallazgo_cuenta_reservas_y_enlaza_a_asignar_pangas(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Futuro 1', self.hoy)
        self.reserva(self.alfa, self.pesca_alfa, 'Futuro 2', self.hoy)
        self.reserva(
            self.alfa, self.pesca_alfa, 'Ya asignado', self.hoy,
            estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga_alfa,
        )

        respuesta = self.ver(self.vendedora, vista='mes', desde=self.hoy.isoformat())

        hallazgo = respuesta.context['hallazgo']
        self.assertEqual((hallazgo.total, hallazgo.sin_panga, hallazgo.atrasadas), (3, 2, 0))
        self.assertContains(respuesta, '3 reservas')
        self.assertContains(respuesta, '2 pagadas sin panga')
        agenda = reverse('admin:bookings_agenda_changelist')
        self.assertContains(respuesta, f'{agenda}?periodo=')
        self.assertNotContains(respuesta, 'atrasada')

    def test_las_atrasadas_enlazan_con_su_filtro(self):
        pasado = self.hoy - timedelta(days=5)
        self.reserva(self.alfa, self.pesca_alfa, 'Viejo', pasado)

        respuesta = self.ver(self.vendedora, vista='dia', desde=pasado.isoformat())

        self.assertContains(respuesta, '1 atrasada')
        self.assertContains(respuesta, 'cuando=atrasadas')

    def test_con_todo_asignado_el_hallazgo_no_lleva_enlace(self):
        self.reserva(
            self.alfa, self.pesca_alfa, 'Listo', self.hoy,
            estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga_alfa,
        )

        respuesta = self.ver(self.vendedora, vista='mes', desde=self.hoy.isoformat())

        self.assertContains(respuesta, '1 reserva, todas asignadas')
        self.assertNotContains(respuesta, 'periodo=')

    def test_el_hallazgo_del_operador_en_una_empresa_lleva_su_slug_al_asignar(self):
        self.reserva(self.alfa, self.pesca_alfa, 'Futuro', self.hoy)

        respuesta = self.ver(self.operador, vista='mes', desde=self.hoy.isoformat(), empresa='alfa-pesca')

        self.assertContains(respuesta, 'empresa=alfa-pesca')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with scope.como_operador_plataforma():
            cls.panga_alfa = Embarcacion.objects.create(
                empresa=cls.alfa, nombre='Dorado', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
            )


class SemanaTests(CalendarioVistaBase):
    def setUp(self):
        self.lunes = lunes_de(self.hoy)

    def semana(self, usuario=None, **params):
        return self.ver(usuario or self.vendedora, vista='semana', desde=self.lunes.isoformat(), **params)

    def test_un_evento_es_una_sola_linea_con_hora_cliente_y_personas(self):
        self.reserva(self.alfa, self.pesca_alfa, 'García', self.lunes, hora=time(6), numero_personas=4)

        respuesta = self.semana()

        self.assertContains(respuesta, 'data-evento')
        self.assertContains(respuesta, '6:00')
        self.assertContains(respuesta, 'García')
        self.assertContains(respuesta, '· 4')

    def test_el_evento_es_un_enlace_a_la_reserva_aunque_no_haya_javascript(self):
        reserva = self.reserva(self.alfa, self.pesca_alfa, 'García', self.lunes)

        respuesta = self.semana()

        self.assertContains(respuesta, f'href="{reverse("admin:bookings_reserva_change", args=[reserva.pk])}"')

    def test_siete_columnas_lunes_a_domingo_y_el_numero_del_dia_enlaza_a_la_vista_dia(self):
        respuesta = self.semana()

        dias = respuesta.context['semana']['dias']
        self.assertEqual([d['fecha'] for d in dias], [self.lunes + timedelta(days=i) for i in range(7)])
        self.assertTrue(all('vista=dia' in d['url_dia'] for d in dias))
        self.assertTrue(dias[5]['fin_de_semana'] and dias[6]['fin_de_semana'] and not dias[4]['fin_de_semana'])
        self.assertEqual([d['fecha'] for d in dias if d['es_hoy']], [self.hoy])

    def test_mas_de_seis_eventos_muestran_cinco_y_un_mas_que_lleva_al_dia(self):
        for i in range(7):
            self.reserva(self.alfa, self.pesca_alfa, f'Cliente {i}', self.lunes, hora=time(5, i))

        respuesta = self.semana()

        lunes = respuesta.context['semana']['dias'][0]
        self.assertEqual((len(lunes['eventos']), lunes['n_mas']), (5, 2))
        self.assertContains(respuesta, '+2 más')
        self.assertContains(respuesta, f'vista=dia&amp;desde={self.lunes.isoformat()}')

    def test_seis_eventos_se_muestran_todos(self):
        for i in range(6):
            self.reserva(self.alfa, self.pesca_alfa, f'Cliente {i}', self.lunes, hora=time(5, i))

        lunes = self.semana().context['semana']['dias'][0]

        self.assertEqual((len(lunes['eventos']), lunes['n_mas']), (6, 0))

    def test_la_estancia_es_una_barra_con_noches_y_dias_de_mar(self):
        self.reserva(
            self.beta, self.hotel_beta, 'Pérez', self.lunes + timedelta(days=1), hora=None,
            fecha_salida=self.lunes + timedelta(days=6),
        )

        respuesta = self.semana(self.jefe_beta)

        barra = respuesta.context['semana']['barras'][0]
        self.assertEqual((barra['col'], barra['span'], barra['carril']), (2, 5, 1))
        self.assertContains(respuesta, 'Pérez · 5 noches')

    def test_la_barra_que_sigue_fuera_de_la_semana_lleva_el_borde_recto(self):
        self.reserva(
            self.beta, self.hotel_beta, 'Larga', self.lunes - timedelta(days=2), hora=None,
            fecha_salida=self.lunes + timedelta(days=9),
        )

        barra = self.semana(self.jefe_beta).context['semana']['barras'][0]

        self.assertEqual((barra['col'], barra['span']), (1, 7))
        self.assertTrue(barra['continua_antes'] and barra['continua_despues'])

    def test_estancias_que_se_solapan_van_en_carriles_distintos(self):
        for nombre in ('Uno', 'Dos'):
            self.reserva(
                self.beta, self.hotel_beta, nombre, self.lunes + timedelta(days=1), hora=None,
                fecha_salida=self.lunes + timedelta(days=3),
            )

        barras = self.semana(self.jefe_beta).context['semana']['barras']

        self.assertEqual(sorted(b['carril'] for b in barras), [1, 2])

    def test_el_paquete_es_solo_su_barra_y_no_se_repite_como_evento(self):
        with scope.como_operador_plataforma():
            hotel = Servicio.objects.create(
                empresa=self.alfa, nombre='Cabaña', slug='cabana-alfa', tipo_servicio='hospedaje',
                estrategia_cupo='por_noche', estrategia_precio='por_noche',
            )
            paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.alfa, nombre='Finde', slug='finde-vista',
                precio_ancla=Decimal('9000'),
            )
            PaqueteServicio.objects.create(
                paquete=paquete, servicio=self.pesca_alfa, orden=1, dia_estancia=2, personas_incluidas=3,
            )
            PaqueteServicio.objects.create(paquete=paquete, servicio=hotel, orden=2, noches=3, personas_incluidas=2)
        inicio = self.lunes + timedelta(days=1)
        self.reserva(
            self.alfa, None, 'Paquete Ruiz', inicio + timedelta(days=1), paquete=paquete, inicio_paquete=inicio,
            fecha_salida=inicio + timedelta(days=3),
        )

        semana = self.semana()
        dia = self.ver(self.vendedora, vista='dia', desde=(inicio + timedelta(days=1)).isoformat())

        self.assertEqual(sum(len(d['eventos']) for d in semana.context['semana']['dias']), 0)
        self.assertContains(semana, 'Paquete Ruiz · 3 noches · 1 al mar')
        self.assertEqual(len(dia.context['dia']['mar']), 1)  # en la vista Dia si es un renglon propio

    def test_un_traslado_de_ida_y_regreso_son_dos_eventos_marcados(self):
        reserva = self.reserva(self.beta, self.traslado_beta, 'Traslado Soto', self.lunes, hora=None)
        with scope.como_operador_plataforma():
            ViajeTransporte.objects.create(
                empresa=self.beta, reserva=reserva, sentido='ida', fecha=self.lunes, hora=time(9),
            )
            ViajeTransporte.objects.create(
                empresa=self.beta, reserva=reserva, sentido='regreso', fecha=self.lunes + timedelta(days=3),
            )

        respuesta = self.semana(self.jefe_beta)

        self.assertContains(respuesta, 'Ida')
        self.assertContains(respuesta, 'Regreso')
        self.assertEqual(sum(len(d['eventos']) for d in respuesta.context['semana']['dias']), 2)

    def test_la_marca_de_sin_panga_y_de_atrasada(self):
        ayer = self.hoy - timedelta(days=1)
        self.reserva(self.alfa, self.pesca_alfa, 'Sin Panga', self.hoy)
        self.reserva(self.alfa, self.pesca_alfa, 'Tarde', ayer)

        hoy = self.ver(self.vendedora, vista='dia', desde=self.hoy.isoformat())
        pasado = self.ver(self.vendedora, vista='dia', desde=ayer.isoformat())

        self.assertContains(hoy, 'cal-ev--sin_panga')
        self.assertNotContains(hoy, 'cal-ev--atrasada')
        self.assertContains(pasado, 'cal-ev--atrasada')

    def test_el_popover_trae_el_detalle_y_las_acciones(self):
        reserva = self.reserva(
            self.alfa, self.pesca_alfa, 'García', self.hoy, precio_total=Decimal('4500'),
            monto_pagado=Decimal('1350'), telefono_cliente='+5216125550000',
        )

        respuesta = self.ver(self.vendedora, vista='semana', desde=self.hoy.isoformat())

        self.assertContains(respuesta, '+5216125550000')
        self.assertContains(respuesta, 'Abrir reserva')
        self.assertContains(respuesta, 'data-asignar-panga')  # el menu lateral tambien dice «Asignar pangas»
        self.assertContains(respuesta, 'MXN')
        self.assertContains(respuesta, 'WhatsApp')
        asignar = f'{reverse("admin:bookings_agenda_changelist")}?periodo={reserva.fecha.isoformat()}_{reserva.fecha.isoformat()}'
        self.assertContains(respuesta, asignar)

    def test_una_asignada_no_ofrece_asignar_panga(self):
        self.reserva(
            self.alfa, self.pesca_alfa, 'Listo', self.hoy,
            estado=Reserva.Estado.ASIGNADA, embarcacion=self.panga,
        )

        respuesta = self.ver(self.vendedora, vista='semana', desde=self.hoy.isoformat())

        self.assertContains(respuesta, 'Abrir reserva')
        self.assertNotContains(respuesta, 'data-asignar-panga')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with scope.como_operador_plataforma():
            cls.panga = Embarcacion.objects.create(
                empresa=cls.alfa, nombre='Dorado', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
            )


class MesTests(CalendarioVistaBase):
    def setUp(self):
        self.primero = self.hoy.replace(day=1)

    def mes(self, usuario=None, **params):
        return self.ver(usuario or self.vendedora, vista='mes', desde=self.primero.isoformat(), **params)

    def dia_del_mes(self, respuesta, fecha):
        for semana in respuesta.context['mes']['semanas']:
            for dia in semana['dias']:
                if dia['fecha'] == fecha:
                    return dia

    def test_cada_celda_enlaza_a_su_dia_y_los_renglones_no_son_enlaces(self):
        self.reserva(self.alfa, self.pesca_alfa, 'García', self.primero, hora=time(6))

        respuesta = self.mes()

        self.assertContains(respuesta, f'vista=dia&amp;desde={self.primero.isoformat()}')
        self.assertNotContains(respuesta, 'data-evento')  # el popover y los enlaces son de Semana y Dia
        self.assertContains(respuesta, '6:00 García')

    def test_dos_renglones_y_un_mas(self):
        for i in range(5):
            self.reserva(self.alfa, self.pesca_alfa, f'Cliente {i}', self.primero, hora=time(5, i))

        dia = self.dia_del_mes(self.mes(), self.primero)

        self.assertEqual((len(dia['lineas']), dia['n_mas']), (2, 3))
        self.assertContains(self.mes(), '+3 más')

    def test_los_dias_de_otro_mes_van_en_gris(self):
        respuesta = self.mes()
        semanas = respuesta.context['mes']['semanas']
        fuera = [d for s in semanas for d in s['dias'] if d['fecha'].month != self.primero.month]
        dentro = [d for s in semanas for d in s['dias'] if d['fecha'].month == self.primero.month]

        self.assertTrue(fuera and all(d['otro_mes'] for d in fuera))
        self.assertFalse(any(d['otro_mes'] for d in dentro))

    def test_estancias_mas_de_dos_barras_pasan_a_mas(self):
        for i in range(3):
            self.reserva(
                self.beta, self.hotel_beta, f'Huesped {i}', self.primero + timedelta(days=1), hora=None,
                fecha_salida=self.primero + timedelta(days=3),
            )

        respuesta = self.mes(self.jefe_beta)

        barras = [b for s in respuesta.context['mes']['semanas'] for b in s['barras']]
        self.assertEqual(sorted(b['carril'] for b in barras), [1, 2])
        self.assertEqual(self.dia_del_mes(respuesta, self.primero + timedelta(days=1))['n_mas'], 1)

    def test_el_mes_no_pinta_la_tira_de_pangas_pero_si_marca_lleno(self):
        crear_flota(self.alfa)
        dia_lleno = self.hoy
        with scope.como_operador_plataforma():
            CupoDiario.objects.create(empresa=self.alfa, fecha=dia_lleno, cupo_maximo=0)

        respuesta = self.ver(self.vendedora, vista='mes', desde=dia_lleno.replace(day=1).isoformat())

        self.assertNotContains(respuesta, 'data-tira')
        self.assertEqual(self.dia_del_mes(respuesta, dia_lleno)['lleno'], True)
        self.assertContains(respuesta, 'Lleno')

    def test_con_todas_no_hay_lleno_ni_tira(self):
        crear_flota(self.alfa)

        respuesta = self.ver(self.operador, vista='mes', empresa='todas', desde=self.primero.isoformat())

        self.assertNotContains(respuesta, 'Lleno')


class TiraDePangasVistaTests(CalendarioVistaBase):
    def test_semana_y_dia_muestran_los_viajes_sobre_la_flota(self):
        crear_flota(self.alfa)
        lunes = lunes_de(self.hoy)
        for i in range(3):
            self.reserva(self.alfa, self.pesca_alfa, f'Cliente {i}', lunes)

        semana = self.ver(self.vendedora, vista='semana', desde=lunes.isoformat())
        dia = self.ver(self.vendedora, vista='dia', desde=lunes.isoformat())

        self.assertContains(semana, 'data-tira')
        self.assertContains(semana, '3 de 10 pangas')
        self.assertContains(dia, '3 de 10 pangas')

    def test_una_empresa_sin_pangas_no_pinta_tira(self):
        respuesta = self.ver(self.jefe_beta, vista='semana')

        self.assertNotContains(respuesta, 'data-tira')

    def test_con_todas_no_se_pinta(self):
        crear_flota(self.alfa)

        self.assertNotContains(self.ver(self.operador, vista='semana', empresa='todas'), 'data-tira')


class ConsultasDeLaVistaTests(CalendarioVistaBase):
    def sembrar(self, cuantas):
        # Todas de hoy, que cae en el dia, la semana y el mes de las tres vistas: con una vista
        # vacia no corren los prefetch y el conteo variaria por otra razon que un N+1.
        for i in range(cuantas):
            self.reserva(self.alfa, self.pesca_alfa, f'Cliente {i}', self.hoy, hora=time(5, i % 60))

    def consultas(self, **params):
        self.client.force_login(self.vendedora)
        with CaptureQueriesContext(connection) as capturadas:
            self.client.get(self.url, params)
        return len(capturadas)

    def test_las_consultas_no_crecen_con_las_reservas(self):
        for vista in ('dia', 'semana', 'mes'):
            with self.subTest(vista=vista):
                with scope.como_operador_plataforma():
                    Reserva.objects.all().delete()
                self.sembrar(2)
                pocas = self.consultas(vista=vista)
                self.sembrar(30)
                self.assertEqual(self.consultas(vista=vista), pocas)
