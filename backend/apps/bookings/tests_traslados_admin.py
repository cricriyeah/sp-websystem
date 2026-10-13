"""Pruebas del admin de Traslados (ViajeTransporteAdmin).

Cubre:
1. Asignar un vehículo desde la lista guarda (list_editable).
2. El selector solo ofrece los vehículos que caben y no están bloqueados ese día/hora.
3. El selector siempre incluye el vehículo actual asignado.
4. Asignar uno que no cabe da el mensaje con el motivo.
5. Asignar uno bloqueado da el mensaje con el motivo.
6. Filtro «Cuándo» (Hoy, Mañana, Próximos 7 días por defecto, Todos) y exclusión de cancelados.
7. Orden: sin vehículo primero, luego fecha y hora (sin hora al final del día).
8. Resumen en el banner: «N sin vehículo» y «Todo asignado».
9. Avisos:
   - Empalme informativo (mismo vehículo a la misma hora).
   - Regreso sin hora ("Falta la hora").
   - Asignación que quedó inválida (vehículo bloqueado o ya no cabe).
10. Una fila sin cambios con un vehículo ahora inválido no impide guardar el resto (has_changed).
11. Permisos por rol: Vendedora y Jefe pueden ver y editar; no hay permisos de alta ni borrado.
12. Aislamiento entre empresas: una empresa no ve viajes ni vehículos de otra.
13. El admin carga sin errores con Vendedora y con Jefe.
14. Cuenta de consultas: la lista no crece por fila (sin N+1).
"""
from contextlib import contextmanager
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import DetalleTransporte, Reserva, ViajeTransporte
from apps.fleet.enums import EstrategiaCupo, EstrategiaPrecio, TipoServicio, TipoTraslado, Zona
from apps.fleet.models import PuntoEncuentro, Servicio, Vehiculo, VehiculoNoDisponible
from apps.tenancy import scope
from apps.tenancy.models import Empresa
from apps.testing import EmpresaTestCase

User = get_user_model()


def _crear_servicio_transporte(empresa):
    return Servicio.objects.create(
        empresa=empresa,
        nombre='Traslado DLS',
        slug=f'traslado-dls-{empresa.slug}',
        tipo_servicio=TipoServicio.TRANSPORTE,
        estrategia_cupo=EstrategiaCupo.BAJO_DEMANDA,
        estrategia_precio=EstrategiaPrecio.POR_RUTA,
        pide_hora=False,
        activo=True,
    )


def _crear_reserva_transporte(
    empresa, servicio, fecha=None, hora=None, numero_personas=2,
    nombre_cliente='Ana Garcia', sentido=TipoTraslado.RECEPCION_AEROPUERTO,
):
    pe, _ = PuntoEncuentro.objects.get_or_create(
        empresa=empresa,
        nombre='Hotel Malecon',
        defaults={'zona': Zona.CENTRO, 'activo': True},
    )
    reserva = Reserva.objects.create(
        empresa=empresa,
        servicio=servicio,
        nombre_cliente=nombre_cliente,
        telefono_cliente='+5216121112233',
        correo_cliente='ana@example.com',
        canal_origen=Reserva.CanalOrigen.WHATSAPP,
        deslinde_aceptado=True,
        deslinde_nombre=nombre_cliente,
        fecha=fecha or (timezone.localdate() + timedelta(days=2)),
        hora=hora or time(10, 0),
        numero_personas=numero_personas,
        estado=Reserva.Estado.PAGADA,
    )
    DetalleTransporte.objects.create(
        reserva=reserva,
        tipo_traslado=sentido,
        punto_encuentro=pe,
        zona=Zona.CENTRO,
    )
    return reserva


@contextmanager
def _fuera_del_alcance(caso):
    """Permite peticiones con self.client que abren su propio alcance sin chocar
    con el que mantiene EmpresaTestCase."""
    caso._alcance.__exit__(None, None, None)
    try:
        yield
    finally:
        caso._alcance = scope.con_empresa(caso.empresa)
        caso._alcance.__enter__()


@contextmanager
def _en_empresa(caso, empresa):
    """Siembra o lee datos de OTRA empresa: con RLS real (Postgres) el alcance de la prueba no
    puede escribir ni ver filas de otra empresa, asi que se cambia de alcance y se restaura."""
    with _fuera_del_alcance(caso):
        with scope.con_empresa(empresa):
            yield


class TrasladosAdminTests(EmpresaTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse('admin:bookings_viajetransporte_changelist')
        self.jefe = self.crear_jefe('jefe_carlos')
        self.vendedora = self.crear_vendedora('vendedora_laura')
        self.servicio = _crear_servicio_transporte(self.empresa)
        self.client.force_login(self.jefe)

    def test_admin_carga_sin_errores_con_vendedora_y_jefe(self):
        """El admin responde 200 para Jefe y para Vendedora."""
        # Jefe
        resp_jefe = self.client.get(self.url)
        self.assertEqual(resp_jefe.status_code, 200)

        # Vendedora
        self.client.force_login(self.vendedora)
        resp_vendedora = self.client.get(self.url)
        self.assertEqual(resp_vendedora.status_code, 200)

    def test_asignar_vehiculo_desde_la_lista_guarda(self):
        """Asignar un vehículo mediante list_editable guarda correctamente."""
        vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Ejecutiva', lugares=6, activo=True,
        )
        reserva = _crear_reserva_transporte(self.empresa, self.servicio, numero_personas=4)
        viaje = reserva.viajes_transporte.first()
        self.assertIsNone(viaje.vehiculo_id)

        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(viaje.pk),
            'form-0-vehiculo': str(vehiculo.pk),
            '_save': 'Guardar',
        })

        self.assertEqual(respuesta.status_code, 302)
        viaje.refresh_from_db()
        self.assertEqual(viaje.vehiculo_id, vehiculo.pk)

    def test_la_hora_del_regreso_se_captura_en_la_lista_y_la_de_la_ida_no(self):
        """El regreso llega sin hora (el checkout no la pide): se captura aqui. La hora de la ida
        viene de la reserva y no se edita desde esta lista."""
        reserva = _crear_reserva_transporte(
            self.empresa, self.servicio, hora=time(9, 0), sentido=TipoTraslado.REDONDO_ACTIVIDAD,
        )
        ida = reserva.viajes_transporte.get(sentido=ViajeTransporte.Sentido.IDA)
        regreso = reserva.viajes_transporte.get(sentido=ViajeTransporte.Sentido.REGRESO)
        self.assertIsNone(regreso.hora)

        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '2',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(ida.pk),
            'form-0-hora': '03:00',
            'form-1-id': str(regreso.pk),
            'form-1-hora': '16:30',
            '_save': 'Guardar',
        })

        self.assertEqual(respuesta.status_code, 302)
        ida.refresh_from_db()
        regreso.refresh_from_db()
        self.assertEqual(ida.hora, time(9, 0))      # la de la ida no se toca
        self.assertEqual(regreso.hora, time(16, 30))

    def test_selector_solo_ofrece_vehiculos_que_caben_y_no_estan_bloqueados(self):
        """El selector de cada fila solo ofrece vehículos activos que caben y no están bloqueados."""
        fecha_viaje = timezone.localdate() + timedelta(days=3)
        hora_viaje = time(10, 0)
        reserva = _crear_reserva_transporte(
            self.empresa, self.servicio, fecha=fecha_viaje, hora=hora_viaje, numero_personas=4,
        )
        viaje = reserva.viajes_transporte.first()

        v_pequeno = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Sedan Chico', lugares=2, activo=True,
        )
        v_adecuado = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Suburban Grande', lugares=6, activo=True,
        )
        v_bloqueado = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Sprinter Bloqueada', lugares=10, activo=True,
        )
        v_inactivo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Minivan Inactiva', lugares=6, activo=False,
        )

        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=v_bloqueado, fecha=fecha_viaje,
            hora_desde=time(9, 0), hora_hasta=time(12, 0), registrado_por=self.jefe,
        )

        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)

        formset = respuesta.context['cl'].formset
        form = formset.forms[0]
        opciones = {valor for valor, _etiqueta in form.fields['vehiculo'].choices if valor}  # lo que se dibuja de verdad

        self.assertIn(v_adecuado.pk, opciones)
        self.assertNotIn(v_pequeno.pk, opciones)     # no cabe (2 < 4)
        self.assertNotIn(v_bloqueado.pk, opciones)   # bloqueado a las 10:00
        self.assertNotIn(v_inactivo.pk, opciones)    # inactivo

    def test_selector_siempre_incluye_el_vehiculo_actual(self):
        """El vehículo actual asignado nunca desaparece del selector de la fila."""
        fecha_viaje = timezone.localdate() + timedelta(days=3)
        v_actual = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Actual', lugares=6, activo=True,
        )
        reserva = _crear_reserva_transporte(
            self.empresa, self.servicio, fecha=fecha_viaje, numero_personas=4,
        )
        viaje = reserva.viajes_transporte.first()
        viaje.vehiculo = v_actual
        viaje.save()

        # Se bloquea después de haber sido asignado
        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=v_actual, fecha=fecha_viaje,
            registrado_por=self.jefe,
        )

        respuesta = self.client.get(self.url)
        formset = respuesta.context['cl'].formset
        form = formset.forms[0]
        opciones = {valor for valor, _etiqueta in form.fields['vehiculo'].choices if valor}  # lo que se dibuja de verdad

        self.assertIn(v_actual.pk, opciones)

    def test_asignar_vehiculo_que_no_cabe_da_mensaje_del_motivo(self):
        """Si se intenta guardar un vehículo donde el grupo no cabe, clean() da el motivo."""
        v_chico = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Sedan Familiar', lugares=2, activo=True,
        )
        reserva = _crear_reserva_transporte(
            self.empresa, self.servicio, numero_personas=4,
        )
        viaje = reserva.viajes_transporte.first()

        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(viaje.pk),
            'form-0-vehiculo': str(v_chico.pk),
            '_save': 'Guardar',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'tiene 2 lugar(es) y la reserva es para 4 persona(s)')
        viaje.refresh_from_db()
        self.assertIsNone(viaje.vehiculo_id)

    def test_asignar_vehiculo_bloqueado_da_mensaje_del_motivo(self):
        """Si se intenta guardar un vehículo bloqueado, clean() explica el motivo."""
        fecha_viaje = timezone.localdate() + timedelta(days=2)
        hora_viaje = time(11, 0)
        v_bloqueado = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Servicio', lugares=6, activo=True,
        )
        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=v_bloqueado, fecha=fecha_viaje,
            registrado_por=self.jefe,
        )
        reserva = _crear_reserva_transporte(
            self.empresa, self.servicio, fecha=fecha_viaje, hora=hora_viaje, numero_personas=3,
        )
        viaje = reserva.viajes_transporte.first()

        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(viaje.pk),
            'form-0-vehiculo': str(v_bloqueado.pk),
            '_save': 'Guardar',
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'esta bloqueado el')
        viaje.refresh_from_db()
        self.assertIsNone(viaje.vehiculo_id)

    def test_filtro_cuando_y_exclusion_de_cancelados(self):
        """Filtro Cuándo con Hoy, Mañana, Próximos 7 días (por defecto), Todos, y exclusión de cancelados."""
        hoy = timezone.localdate()
        manana = hoy + timedelta(days=1)
        en_semana = hoy + timedelta(days=4)
        lejano = hoy + timedelta(days=25)

        r_hoy = _crear_reserva_transporte(self.empresa, self.servicio, fecha=hoy, nombre_cliente='Cliente Hoy')
        r_manana = _crear_reserva_transporte(self.empresa, self.servicio, fecha=manana, nombre_cliente='Cliente Manana')
        r_semana = _crear_reserva_transporte(self.empresa, self.servicio, fecha=en_semana, nombre_cliente='Cliente Semana')
        r_lejano = _crear_reserva_transporte(self.empresa, self.servicio, fecha=lejano, nombre_cliente='Cliente Lejano')

        v_hoy = r_hoy.viajes_transporte.first()
        v_manana = r_manana.viajes_transporte.first()
        v_semana = r_semana.viajes_transporte.first()
        v_lejano = r_lejano.viajes_transporte.first()

        # Viaje cancelado no debe verse bajo ningún filtro
        r_cancelada = _crear_reserva_transporte(self.empresa, self.servicio, fecha=hoy, nombre_cliente='Cliente Cancelado')
        v_cancelado = r_cancelada.viajes_transporte.first()
        v_cancelado.cancelado = True
        v_cancelado.save()

        def _pks(params=None):
            resp = self.client.get(self.url, params or {})
            self.assertEqual(resp.status_code, 200)
            return {item.pk for item in resp.context['cl'].result_list}

        # Por defecto: próximos 7 días
        pks_default = _pks()
        self.assertIn(v_hoy.pk, pks_default)
        self.assertIn(v_manana.pk, pks_default)
        self.assertIn(v_semana.pk, pks_default)
        self.assertNotIn(v_lejano.pk, pks_default)
        self.assertNotIn(v_cancelado.pk, pks_default)

        # Modo hoy
        pks_hoy = _pks({'cuando': 'hoy'})
        self.assertIn(v_hoy.pk, pks_hoy)
        self.assertNotIn(v_manana.pk, pks_hoy)
        self.assertNotIn(v_cancelado.pk, pks_hoy)

        # Modo mañana
        pks_manana = _pks({'cuando': 'manana'})
        self.assertIn(v_manana.pk, pks_manana)
        self.assertNotIn(v_hoy.pk, pks_manana)

        # Modo todos
        pks_todos = _pks({'cuando': 'todos'})
        self.assertIn(v_hoy.pk, pks_todos)
        self.assertIn(v_manana.pk, pks_todos)
        self.assertIn(v_semana.pk, pks_todos)
        self.assertIn(v_lejano.pk, pks_todos)
        self.assertNotIn(v_cancelado.pk, pks_todos)

    def test_orden_sin_vehiculo_primero_luego_fecha_y_hora(self):
        """Orden: sin vehículo primero, luego fecha y hora (sin hora al final del día)."""
        fecha = timezone.localdate() + timedelta(days=1)
        vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Orden', lugares=8, activo=True,
        )

        r1 = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(10, 0), nombre_cliente='Primero Asignado')
        v1 = r1.viajes_transporte.first()
        v1.vehiculo = vehiculo
        v1.save()

        r2 = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(8, 0), nombre_cliente='Sin Asignar Ocho')
        v2 = r2.viajes_transporte.first()

        r3 = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(14, 0), nombre_cliente='Sin Asignar Catorce')
        v3 = r3.viajes_transporte.first()

        # Viaje sin hora
        r4 = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=None, nombre_cliente='Sin Hora Pendiente')
        v4 = r4.viajes_transporte.first()
        ViajeTransporte.objects.filter(pk=v4.pk).update(hora=None)
        v4.refresh_from_db()

        resp = self.client.get(self.url, {'cuando': 'manana'})
        pks_ordenados = [item.pk for item in resp.context['cl'].result_list]

        # Esperado: sin vehículo primero (08:00, 14:00, sin hora al final del día), luego el asignado
        self.assertEqual(pks_ordenados, [v2.pk, v3.pk, v4.pk, v1.pk])

    def test_resumen_banner(self):
        """La línea de resumen indica «N sin vehículo» o «Todo asignado»."""
        fecha = timezone.localdate() + timedelta(days=2)
        vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Resumen', lugares=6, activo=True,
        )
        reserva = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha)
        viaje = reserva.viajes_transporte.first()

        # 1 sin vehículo
        resp1 = self.client.get(self.url)
        self.assertEqual(resp1.context['sin_vehiculo'], 1)
        self.assertEqual(resp1.context['resumen_traslados'], '1 sin vehículo')
        self.assertContains(resp1, '1 sin vehículo')

        # Asignar vehículo -> Todo asignado
        viaje.vehiculo = vehiculo
        viaje.save()

        resp2 = self.client.get(self.url)
        self.assertEqual(resp2.context['sin_vehiculo'], 0)
        self.assertEqual(resp2.context['resumen_traslados'], 'Todo asignado')
        self.assertContains(resp2, 'Todo asignado')

    def test_avisos_empalme_regreso_sin_hora_y_asignacion_invalida(self):
        """Verifica avisos de empalme, regreso sin hora y asignación que quedó inválida."""
        fecha = timezone.localdate() + timedelta(days=2)
        hora = time(10, 0)
        vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Alfa', lugares=6, activo=True,
        )

        # 1. Empalme: dos viajes asignados al mismo vehículo, fecha y hora
        r1 = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=hora, nombre_cliente='Cliente Uno')
        v1 = r1.viajes_transporte.first()
        v1.vehiculo = vehiculo
        v1.save()

        r2 = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=hora, nombre_cliente='Cliente Dos')
        v2 = r2.viajes_transporte.first()
        v2.vehiculo = vehiculo
        v2.save()

        # 2. Regreso sin hora
        r_redondo = _crear_reserva_transporte(
            self.empresa, self.servicio, fecha=fecha, hora=hora,
            nombre_cliente='Cliente Redondo', sentido=TipoTraslado.REDONDO_ACTIVIDAD,
        )
        # El viaje de regreso se genera sin hora
        v_regreso = r_redondo.viajes_transporte.get(sentido=ViajeTransporte.Sentido.REGRESO)
        self.assertIsNone(v_regreso.hora)

        # 3. Asignación que quedó inválida por bloqueo posterior
        v_invalido = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Beta', lugares=6, activo=True,
        )
        r3 = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(15, 0), nombre_cliente='Cliente Invalido')
        v3 = r3.viajes_transporte.first()
        v3.vehiculo = v_invalido
        v3.save()
        # Se registra un bloqueo sobre v_invalido
        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=v_invalido, fecha=fecha,
            registrado_por=self.jefe,
        )

        resp = self.client.get(self.url)
        html = resp.content.decode()

        self.assertIn('Mismo vehículo a la misma hora que #', html)
        self.assertIn('Falta la hora', html)
        self.assertIn('El vehículo ya no cabe o está bloqueado', html)

    def test_fila_sin_cambios_con_vehiculo_invalido_no_impide_guardar_el_resto(self):
        """Una fila sin cambios con un vehículo que ya no sirve no impide guardar el resto."""
        fecha = timezone.localdate() + timedelta(days=2)
        v_bloqueado = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Uno', lugares=6, activo=True,
        )
        v_disponible = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Dos', lugares=6, activo=True,
        )

        # Fila 1: ya tiene v_bloqueado asignado
        r1 = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(9, 0), nombre_cliente='Cliente Bloqueado')
        viaje1 = r1.viajes_transporte.first()
        viaje1.vehiculo = v_bloqueado
        viaje1.save()

        # Se bloquea v_bloqueado posteriormente
        VehiculoNoDisponible.objects.create(
            empresa=self.empresa, vehiculo=v_bloqueado, fecha=fecha, registrado_por=self.jefe,
        )

        # Fila 2: sin vehículo, se asignará a v_disponible
        r2 = _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(11, 0), nombre_cliente='Cliente Nuevo')
        viaje2 = r2.viajes_transporte.first()

        # POST del formset con fila 1 intacta y fila 2 cambiada
        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '2',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(viaje1.pk),
            'form-0-vehiculo': str(v_bloqueado.pk),
            'form-1-id': str(viaje2.pk),
            'form-1-vehiculo': str(v_disponible.pk),
            '_save': 'Guardar',
        })

        self.assertEqual(respuesta.status_code, 302)
        viaje2.refresh_from_db()
        self.assertEqual(viaje2.vehiculo_id, v_disponible.pk)
        viaje1.refresh_from_db()
        self.assertEqual(viaje1.vehiculo_id, v_bloqueado.pk)

    def test_sin_alta_ni_borrado_manual(self):
        """has_add_permission y has_delete_permission devuelven False."""
        admin_instance = self.client.get(self.url).context['cl'].model_admin
        request = self.client.get(self.url).wsgi_request

        self.assertFalse(admin_instance.has_add_permission(request))
        self.assertFalse(admin_instance.has_delete_permission(request))

        # Intento directo de GET a la vista add da 403
        url_add = reverse('admin:bookings_viajetransporte_add')
        resp_add = self.client.get(url_add)
        self.assertEqual(resp_add.status_code, 403)

    def test_vendedora_puede_asignar_vehiculo(self):
        """La vendedora tiene permiso para cambiar el vehículo desde el changelist."""
        self.client.force_login(self.vendedora)
        vehiculo = Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Vendedora', lugares=6, activo=True,
        )
        reserva = _crear_reserva_transporte(self.empresa, self.servicio, numero_personas=3)
        viaje = reserva.viajes_transporte.first()

        respuesta = self.client.post(self.url, {
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(viaje.pk),
            'form-0-vehiculo': str(vehiculo.pk),
            '_save': 'Guardar',
        })
        self.assertEqual(respuesta.status_code, 302)
        viaje.refresh_from_db()
        self.assertEqual(viaje.vehiculo_id, vehiculo.pk)

    def test_aislamiento_entre_empresas(self):
        """Una empresa no ve ni puede asignar viajes ni vehículos de otra empresa."""
        otra_empresa = Empresa.objects.create(
            sede=self.sede, nombre='Otra Empresa Traslados', slug='otra-empresa-traslados',
            activo=True, exclusiva=False,
        )
        with _en_empresa(self, otra_empresa):
            servicio_otra = _crear_servicio_transporte(otra_empresa)
            v_otra = Vehiculo.objects.create(
                empresa=otra_empresa, nombre='Van de Otra', lugares=6, activo=True,
            )
            r_otra = _crear_reserva_transporte(
                otra_empresa, servicio_otra, nombre_cliente='Cliente Ajeno',
            )
            viaje_otra = r_otra.viajes_transporte.first()

        # Jefe de self.empresa consulta su listado
        resp = self.client.get(self.url)
        pks_visibles = {item.pk for item in resp.context['cl'].result_list}
        self.assertNotIn(viaje_otra.pk, pks_visibles)

        # Vehículo de otra empresa no se ofrece en el selector
        r_propia = _crear_reserva_transporte(self.empresa, self.servicio, nombre_cliente='Cliente Propio')
        resp_propia = self.client.get(self.url)
        form = resp_propia.context['cl'].formset.forms[0]
        opciones = {valor for valor, _etiqueta in form.fields['vehiculo'].choices if valor}  # lo que se dibuja de verdad
        self.assertNotIn(v_otra.pk, opciones)

    def test_un_post_falsificado_no_toca_datos_de_otra_empresa(self):
        """Aunque se invente el cuerpo del POST: ni se asigna un vehiculo propio a un viaje ajeno,
        ni se asigna un vehiculo ajeno a un viaje propio, ni se cambia la hora de un regreso ajeno."""
        otra_empresa = Empresa.objects.create(
            sede=self.sede, nombre='Otra Empresa Falsificada', slug='otra-empresa-falsificada',
            activo=True, exclusiva=False,
        )
        v_propio = Vehiculo.objects.create(empresa=self.empresa, nombre='Van Propia', lugares=6, activo=True)
        with _en_empresa(self, otra_empresa):
            servicio_otra = _crear_servicio_transporte(otra_empresa)
            v_otra = Vehiculo.objects.create(empresa=otra_empresa, nombre='Van Ajena', lugares=6, activo=True)
            reserva_otra = _crear_reserva_transporte(
                otra_empresa, servicio_otra, nombre_cliente='Cliente Ajeno',
                sentido=TipoTraslado.REDONDO_ACTIVIDAD,
            )
            viaje_ajeno = reserva_otra.viajes_transporte.get(sentido=ViajeTransporte.Sentido.REGRESO)
        reserva_propia = _crear_reserva_transporte(self.empresa, self.servicio, nombre_cliente='Cliente Propio')
        viaje_propio = reserva_propia.viajes_transporte.first()

        base = {
            'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000', '_save': 'Guardar',
        }
        # 1) viaje ajeno con vehiculo propio y hora nueva
        self.client.post(self.url, {
            **base, 'form-0-id': str(viaje_ajeno.pk),
            'form-0-vehiculo': str(v_propio.pk), 'form-0-hora': '03:00',
        })
        # 2) viaje propio con un vehiculo ajeno
        respuesta = self.client.post(self.url, {
            **base, 'form-0-id': str(viaje_propio.pk), 'form-0-vehiculo': str(v_otra.pk),
        })

        with _en_empresa(self, otra_empresa):
            viaje_ajeno.refresh_from_db()
        viaje_propio.refresh_from_db()
        self.assertIsNone(viaje_ajeno.vehiculo_id)
        self.assertIsNone(viaje_ajeno.hora)
        self.assertIsNone(viaje_propio.vehiculo_id)
        self.assertEqual(respuesta.status_code, 200)  # se rechaza con error de formulario, no se guarda

    def test_cuenta_consultas_no_crece_por_fila(self):
        """La lista no genera consultas adicionales por fila (sin N+1)."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        fecha = timezone.localdate() + timedelta(days=2)
        Vehiculo.objects.create(
            empresa=self.empresa, nombre='Van Medir', lugares=6, activo=True,
        )
        # Crear 2 viajes
        _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(8, 0), nombre_cliente='Consulta Uno')
        _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(9, 0), nombre_cliente='Consulta Dos')

        # Medir consultas con 2 viajes
        with CaptureQueriesContext(connection) as ctx_2:
            self.client.get(self.url, {'cuando': 'semana'})
        n_consultas = len(ctx_2)

        # Agregar 3 viajes más para la misma fecha (total 5)
        _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(10, 0), nombre_cliente='Consulta Tres')
        _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(11, 0), nombre_cliente='Consulta Cuatro')
        _crear_reserva_transporte(self.empresa, self.servicio, fecha=fecha, hora=time(12, 0), nombre_cliente='Consulta Cinco')

        # Con 5 filas, la cantidad de consultas debe ser exactamente la misma
        with self.assertNumQueries(n_consultas):
            self.client.get(self.url, {'cuando': 'semana'})
