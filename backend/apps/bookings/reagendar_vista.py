"""La pantalla «Reagendar» de una reserva (docs/architecture/ARCH-reagendar-reserva.md §4 y §6,
docs/design/DESIGN-reagendar-reserva.md).

Dos pasos sobre una sola URL: elegir la fecha (GET y POST `paso=revisar`) y revisar y confirmar (POST
`paso=confirmar`). Todas las reglas (48 h, cupo, panga, capitan, hospedaje) viven en `apps.bookings.reagendar` y en
el modelo; esta vista solo pregunta (`proponer`), pinta lo que contesta, y al confirmar llama a `reagendar`, deja la
constancia (History y notificacion persistente) y redirige.

Se llama a las funciones del servicio como `reagendar.proponer(...)` (no importadas por nombre) para que quien las
parchee en una prueba las vea.
"""
import logging
from datetime import timedelta
from urllib.parse import quote, urlparse

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone

from apps.notifications import plantilla
from apps.tenancy import scope
from apps.tenancy.models import Notificacion
from apps.tenancy.notificaciones import avisar, enlace_seguro

from . import reagendar
from .models import disponibilidad_por_fecha

logger = logging.getLogger(__name__)

PLANTILLA = 'bookings/reagendar.html'
DIAS_CON_LUGAR = 60
MAX_FECHAS_CON_LUGAR = 5
MOTIVO_MIN, MOTIVO_MAX = 10, 200

DIAS_CORTOS = ('lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom')
MESES_CORTOS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')

# Lo que la pantalla vio de la reserva y manda de vuelta para que el servicio detecte que cambio mientras tanto.
CAMPOS_DEL_TOKEN = ('fecha', 'hora', 'inicio_paquete', 'estado')

# Nombre del campo que usa el servicio en sus errores -> campo del formulario. Lo demas es un error general.
CAMPOS_DE_ERROR = {
    'fecha': 'nueva_fecha', 'nueva_fecha': 'nueva_fecha',
    'hora': 'nueva_hora', 'nueva_hora': 'nueva_hora',
    'fecha_regreso': 'nueva_fecha_regreso', 'nueva_fecha_regreso': 'nueva_fecha_regreso',
    'motivo_excepcion': 'motivo_excepcion',
}


# ---------------------------------------------------------------------------------------------------------------
# Formato unico de fecha y hora (DESIGN, R3)
# ---------------------------------------------------------------------------------------------------------------

def _partes_de_fecha(fecha, hora=None, con_anio=True):
    """('martes 8 de diciembre de 2026', '6:00 a. m.'); cada parte vacia si no hay dato."""
    if not fecha:
        return '', ''
    dia = f'{plantilla.DIAS[fecha.weekday()]} {fecha.day} de {plantilla.MESES[fecha.month - 1]}'
    if con_anio:
        dia += f' de {fecha.year}'
    return dia, (plantilla.hora_12(hora) if hora else '')


def fecha_larga(fecha, hora=None, con_anio=True):
    """«martes 8 de diciembre de 2026 · 6:00 a. m.»: el unico formato de fecha de la vista y de sus avisos."""
    dia, hora_texto = _partes_de_fecha(fecha, hora, con_anio)
    return f'{dia} · {hora_texto}' if dia and hora_texto else dia


def _chip(fecha):
    return f'{DIAS_CORTOS[fecha.weekday()]} {fecha.day} {MESES_CORTOS[fecha.month - 1]}'


def _correo_enmascarado(correo):
    usuario, _, dominio = (correo or '').partition('@')
    return f'{usuario[:1]}***@{dominio}' if usuario and dominio else ''


# ---------------------------------------------------------------------------------------------------------------
# Formulario del paso 1
# ---------------------------------------------------------------------------------------------------------------

class FormularioElegir(forms.Form):
    """Sintaxis de lo que se teclea. Los rangos (futuro, tope de un ano, cupo) los decide el servicio."""

    nueva_fecha = forms.DateField(
        input_formats=['%Y-%m-%d'], error_messages={'required': 'Elige una fecha.', 'invalid': 'Elige una fecha.'})
    nueva_hora = forms.TimeField(
        required=False, input_formats=['%H:%M', '%H:%M:%S'],
        error_messages={'invalid': 'Escribe la hora como 06:00.'})
    nueva_fecha_regreso = forms.DateField(
        required=False, input_formats=['%Y-%m-%d'],
        error_messages={'required': 'Elige la fecha de regreso.', 'invalid': 'Elige la fecha de regreso.'})

    def __init__(self, *args, pide_regreso=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nueva_fecha_regreso'].required = pide_regreso


# ---------------------------------------------------------------------------------------------------------------
# Lo que se pinta (funciones puras o casi: se prueban sin pasar por el navegador)
# ---------------------------------------------------------------------------------------------------------------

def _grupo(titulo, fecha_antes, hora_antes, fecha_ahora, hora_ahora):
    dia_antes, hora_antes_txt = _partes_de_fecha(fecha_antes, hora_antes)
    dia_ahora, hora_ahora_txt = _partes_de_fecha(fecha_ahora, hora_ahora)
    return {
        'titulo': titulo,
        'antes': {'fecha': dia_antes, 'hora': hora_antes_txt},
        'ahora': {'fecha': dia_ahora, 'hora': hora_ahora_txt},
        'cambio_fecha': fecha_antes != fecha_ahora,
        'cambio_hora': hora_antes != hora_ahora,
    }


def armar_grupos(reserva, propuesta, regreso_antes=None):
    """El heroe del paso 2: filas Antes y Ahora con la misma forma. Un paquete suma Llegada y Salida; un traslado
    redondo de aeropuerto, el Regreso. Solo lo que cambio va resaltado (`cambio_fecha` / `cambio_hora`)."""
    hora_ahora = propuesta.hora if propuesta.hora is not None else reserva.hora
    if getattr(reserva, 'paquete_id', None):
        fecha_antes = reserva.inicio_paquete or reserva.fecha
        fecha_ahora = propuesta.inicio_paquete or propuesta.fecha
        grupos = [_grupo('Llegada', fecha_antes, reserva.hora, fecha_ahora, hora_ahora)]
        if reserva.fecha_salida or propuesta.fecha_salida:
            grupos.append(_grupo('Salida', reserva.fecha_salida, None, propuesta.fecha_salida, None))
    else:
        grupos = [_grupo('', reserva.fecha, reserva.hora, propuesta.fecha, hora_ahora)]
    if regreso_antes or propuesta.fecha_regreso:
        grupos.append(_grupo('Regreso', regreso_antes, None, propuesta.fecha_regreso, None))
    return grupos


def _frase_de_mar(propuesta, panga, capitan):
    """Que pasa con la panga y el capitan, en una o dos frases cortas."""
    frases = []
    if propuesta.panga and panga:
        if propuesta.panga == 'conserva' and propuesta.capitan == 'conserva' and capitan:
            return f'Se conservan la panga {panga} y el capitán {capitan}.'
        if propuesta.panga == 'conserva':
            frases.append(f'Se conserva la panga {panga}.')
        else:
            frases.append(f'Se quita la panga {panga}: hay que asignar otra en «Asignar pangas».')
    if propuesta.capitan and capitan:
        if propuesta.capitan == 'conserva':
            frases.append(f'Se conserva el capitán {capitan}.')
        else:
            frases.append(f'Se quita el capitán {capitan}: hay que asignar otro en «Asignar pangas».')
    return ' '.join(frases)


def armar_consecuencias(reserva, propuesta, *, avisar_marcado, tiene_correo, fecha_antes, vehiculos=()):
    """Hasta cuatro frases, de la mas a la menos importante. Cada una es {'texto', 'detalle', 'alterno'}: `alterno`
    es el texto cuando la casilla del correo se desmarca (lo cambia el JS de la pantalla)."""
    consecuencias = []
    con_aviso = 'El cliente recibirá un correo con la nueva fecha.'
    sin_aviso = 'No se avisará al cliente. Avísale tú.'
    if not tiene_correo:
        consecuencias.append({'texto': 'El cliente no tiene correo. Avísale por WhatsApp.'})
    else:
        consecuencias.append({
            'texto': con_aviso if avisar_marcado else sin_aviso,
            'con_aviso': con_aviso, 'sin_aviso': sin_aviso,
        })

    panga = reserva.embarcacion.nombre if reserva.embarcacion_id else ''
    capitan = reserva.capitan.nombre if reserva.capitan_id else ''
    frase = _frase_de_mar(propuesta, panga, capitan)
    if capitan and propuesta.capitan in ('conserva', 'quita'):
        frase = f'{frase} Avísale al capitán {capitan} del nuevo día.'.strip()
    if frase:
        consecuencias.append({'texto': frase, 'detalle': propuesta.motivo_panga or ''})

    if propuesta.vehiculos_a_quitar:
        if len(vehiculos) == 1:
            texto = f'Se quita el vehículo {vehiculos[0]}: asígnalo de nuevo en «Asignar vehículos».'
        elif vehiculos:
            texto = f'Se quitan los vehículos {" y ".join(vehiculos)}: asígnalos de nuevo en «Asignar vehículos».'
        else:
            texto = 'Se quita el vehículo asignado: asígnalo de nuevo en «Asignar vehículos».'
        consecuencias.append({'texto': texto})

    consecuencias.append({'texto': f'El pago no cambia. El lugar del {fecha_antes} queda libre.'})
    return consecuencias


# ---------------------------------------------------------------------------------------------------------------
# Datos de la reserva
# ---------------------------------------------------------------------------------------------------------------

def _servicio_de(reserva):
    return reserva.servicio if reserva.servicio_id else None


def _regreso_actual(reserva):
    """`DetalleTransporte.fecha_regreso` si la reserva es un traslado redondo de aeropuerto, si no `None`."""
    servicio = _servicio_de(reserva)
    if servicio is None or servicio.tipo_servicio != 'transporte':
        return None, False
    detalle = getattr(reserva, 'detalle_transporte', None) if hasattr(reserva, 'detalle_transporte') else None
    if detalle is None or detalle.tipo_traslado != 'redondo_aeropuerto':
        return None, False
    return detalle.fecha_regreso, True


def _muestra_hora(reserva):
    servicio = _servicio_de(reserva)
    return reserva.hora is not None or bool(servicio and servicio.ventana_horaria())


def _es_de_mar(reserva):
    """Pesca, paseo o safari sueltos: lo unico para lo que la pantalla sugiere fechas con lugar."""
    if reserva.paquete_id:
        return False
    servicio = _servicio_de(reserva)
    return servicio is None or servicio.estrategia_cupo == 'por_recurso_dia'


def fechas_con_lugar(reserva, hoy):
    """Hasta cinco dias de los proximos 60 en que cabe el grupo (sin contar el lugar de la propia reserva)."""
    try:
        with transaction.atomic():  # savepoint: una consulta que falle no tumba la pantalla
            mapa = disponibilidad_por_fecha(
                hoy + timedelta(days=1), hoy + timedelta(days=DIAS_CON_LUGAR), reserva.numero_personas,
                reserva.empresa, estrategia_cupo='por_recurso_dia', excluir_pk=reserva.pk,
            )
    except Exception:  # sugerencia opcional: sin ella la persona igual puede teclear la fecha
        logger.exception('No se pudieron calcular las fechas con lugar (reserva=%s).', reserva.pk)
        return []
    libres = [fecha for fecha, motivo in sorted(mapa.items()) if motivo is None and fecha != reserva.fecha]
    return libres[:MAX_FECHAS_CON_LUGAR]


def _vehiculos_asignados(reserva):
    return [
        viaje.vehiculo.nombre
        for viaje in reserva.viajes_transporte.select_related('vehiculo').filter(vehiculo__isnull=False)
    ]


def _token_de(reserva):
    return {
        'fecha': reserva.fecha.isoformat() if reserva.fecha else '',
        'hora': reserva.hora.isoformat() if reserva.hora else '',
        'inicio_paquete': reserva.inicio_paquete.isoformat() if reserva.inicio_paquete else '',
        'estado': reserva.estado,
    }


def _token_enviado(post):
    return {campo: post.get(f'token_{campo}', '') for campo in CAMPOS_DEL_TOKEN}


def _errores_del_servicio(propuesta):
    """{campo del formulario | 'general': [mensajes]} a partir de `Propuesta.errores` y el aviso de falta de cupo."""
    crudos = dict(propuesta.errores or {})
    if not crudos and propuesta.motivo_sin_cupo:
        crudos['nueva_fecha'] = propuesta.motivo_sin_cupo
    if propuesta.motivo_sin_cupo and propuesta.proxima_fecha and 'nueva_fecha' in crudos \
            and 'próxima fecha' not in crudos['nueva_fecha'].lower():
        crudos['nueva_fecha'] += f' La próxima fecha con lugar es el {fecha_larga(propuesta.proxima_fecha)}.'
    return _agrupar_errores(crudos.items())


def _agrupar_errores(pares):
    errores = {}
    for campo, mensaje in pares:
        errores.setdefault(CAMPOS_DE_ERROR.get(campo, 'general'), []).append(str(mensaje))
    return {campo: ' '.join(mensajes) for campo, mensajes in errores.items()}


# ---------------------------------------------------------------------------------------------------------------
# La vista
# ---------------------------------------------------------------------------------------------------------------

def _pinta(modelo_admin, request, reserva, **extra):
    ficha = reverse('admin:bookings_reserva_change', args=[reserva.pk])
    regreso, pide_regreso = _regreso_actual(reserva)
    contexto = {
        **modelo_admin.admin_site.each_context(request),
        'opts': modelo_admin.model._meta,
        'title': f'Reagendar reserva #{reserva.pk}',
        'reserva': reserva,
        'linea_de_la_reserva': ' · '.join([
            reserva.nombre_cliente, modelo_admin.servicio_resumen(reserva), reserva.empresa.nombre,
            f'{reserva.numero_personas} persona{"" if reserva.numero_personas == 1 else "s"}',
        ]),
        'ahora_texto': fecha_larga(
            reserva.inicio_paquete or reserva.fecha if reserva.paquete_id else reserva.fecha, reserva.hora),
        'ficha_url': ficha,
        'muestra_hora': _muestra_hora(reserva),
        'pide_regreso': pide_regreso,
        'errores': {},
        'valores': {},
        'paso': 1,
    }
    contexto.update(extra)
    return TemplateResponse(request, PLANTILLA, contexto)


def _valores_iniciales(reserva):
    regreso, _ = _regreso_actual(reserva)
    inicial = reserva.inicio_paquete or reserva.fecha if reserva.paquete_id else reserva.fecha
    return {
        'nueva_fecha': inicial.isoformat() if inicial else '',
        'nueva_hora': reserva.hora.strftime('%H:%M') if reserva.hora else '',
        'nueva_fecha_regreso': regreso.isoformat() if regreso else '',
    }


def _valores_enviados(post):
    return {campo: post.get(campo, '') for campo in ('nueva_fecha', 'nueva_hora', 'nueva_fecha_regreso')}


def _paso_uno(modelo_admin, request, reserva, volver, valores, errores=None):
    hoy = timezone.localdate()
    es_de_mar = _es_de_mar(reserva)
    libres = fechas_con_lugar(reserva, hoy) if es_de_mar else []
    return _pinta(
        modelo_admin, request, reserva, paso=1, valores=valores, errores=errores or {}, volver=volver,
        es_de_mar=es_de_mar,
        chips=[{'iso': fecha.isoformat(), 'texto': _chip(fecha)} for fecha in libres],
        dias_con_lugar=DIAS_CON_LUGAR,
    )


def _paso_dos(modelo_admin, request, reserva, volver, valores, propuesta, *, puede_autorizar, avisar_marcado=True,
              errores=None, motivo=''):
    tiene_correo = bool(reserva.correo_cliente)
    regreso_antes, _ = _regreso_actual(reserva)
    grupos = armar_grupos(reserva, propuesta, regreso_antes)
    fecha_antes = reserva.inicio_paquete or reserva.fecha if reserva.paquete_id else reserva.fecha
    avisar_marcado = avisar_marcado and tiene_correo
    consecuencias = armar_consecuencias(
        reserva, propuesta, avisar_marcado=avisar_marcado, tiene_correo=tiene_correo,
        fecha_antes=fecha_larga(fecha_antes),
        vehiculos=_vehiculos_asignados(reserva) if propuesta.vehiculos_a_quitar else (),
    )
    requiere = bool(propuesta.requiere_excepcion_48h)
    return _pinta(
        modelo_admin, request, reserva, paso=2, valores=valores, errores=errores or {}, volver=volver,
        grupos=grupos, consecuencias=consecuencias,
        token=_token_de(reserva),
        tiene_correo=tiene_correo, avisar_marcado=avisar_marcado,
        correo_ayuda=f'{reserva.nombre_cliente} · {_correo_enmascarado(reserva.correo_cliente)}' if tiene_correo else '',
        pide_motivo=requiere and puede_autorizar,
        bloqueada_por_48h=requiere and not puede_autorizar,
        motivo=motivo, motivo_min=MOTIVO_MIN, motivo_max=MOTIVO_MAX,
    )


def _puede_autorizar_48h(request):
    return bool(scope.es_jefe_actual(request) or scope.es_operador_plataforma(request.user))


def responder(modelo_admin, request, object_id):
    """`GET|POST /admin/bookings/reserva/<id>/reagendar/` (`ReservaAdmin.reagendar_view` delega aqui)."""
    reserva = modelo_admin.get_object(request, object_id)
    if reserva is None:
        raise Http404('Reserva no encontrada')
    if not modelo_admin.has_change_permission(request, reserva):
        raise PermissionDenied

    ficha = reverse('admin:bookings_reserva_change', args=[reserva.pk])
    # `volver` viene de la URL o de un campo oculto: ambos son entrada del navegador. Solo rutas propias.
    volver = enlace_seguro(request.POST.get('volver') or request.GET.get('volver'))

    motivo_bloqueo = reagendar.motivo_no_reagendable(reserva)
    if motivo_bloqueo:
        modelo_admin.message_user(request, motivo_bloqueo, messages.WARNING)
        return HttpResponseRedirect(volver or ficha)

    if request.method == 'POST' and request.POST.get('volver_a_elegir'):
        # «Cambiar la fecha» del paso 2: de vuelta al paso 1 con lo que la persona habia tecleado (no con la fecha
        # actual de la reserva), sin llamar al servicio. Es un boton aparte y no un `paso` nuevo porque el
        # formulario del paso 2 ya lleva `paso=confirmar`.
        return _paso_uno(modelo_admin, request, reserva, volver, _valores_enviados(request.POST))

    paso = request.POST.get('paso') if request.method == 'POST' else ''
    if paso not in ('revisar', 'confirmar'):
        return _paso_uno(modelo_admin, request, reserva, volver, _valores_iniciales(reserva))

    valores = _valores_enviados(request.POST)
    _, pide_regreso = _regreso_actual(reserva)
    formulario = FormularioElegir(request.POST, pide_regreso=pide_regreso)
    if not formulario.is_valid():
        errores = {campo: ' '.join(mensajes) for campo, mensajes in formulario.errors.items()}
        return _paso_uno(modelo_admin, request, reserva, volver, valores, errores)

    nueva_fecha = formulario.cleaned_data['nueva_fecha']
    nueva_hora = formulario.cleaned_data['nueva_hora']
    nueva_fecha_regreso = formulario.cleaned_data['nueva_fecha_regreso']
    propuesta = reagendar.proponer(
        reserva, nueva_fecha=nueva_fecha, nueva_hora=nueva_hora, nueva_fecha_regreso=nueva_fecha_regreso)
    errores = _errores_del_servicio(propuesta)
    if errores:
        return _paso_uno(modelo_admin, request, reserva, volver, valores, errores)

    puede_autorizar = _puede_autorizar_48h(request)
    if paso == 'revisar':
        return _paso_dos(modelo_admin, request, reserva, volver, valores, propuesta, puede_autorizar=puede_autorizar)

    # paso == 'confirmar'
    avisar_marcado = request.POST.get('avisar_cliente') == '1'
    motivo = (request.POST.get('motivo_excepcion') or '').strip()
    requiere = bool(propuesta.requiere_excepcion_48h)

    def paso_dos_con(errores_del_paso):
        return _paso_dos(
            modelo_admin, request, reserva, volver, valores, propuesta, puede_autorizar=puede_autorizar,
            avisar_marcado=avisar_marcado, errores=errores_del_paso, motivo=motivo)

    if requiere and not puede_autorizar:
        return paso_dos_con({})  # la vendedora no llega a confirmar: el servidor no se fia del boton ausente
    if requiere and not MOTIVO_MIN <= len(motivo) <= MOTIVO_MAX:
        return paso_dos_con({'motivo_excepcion': f'Escribe entre {MOTIVO_MIN} y {MOTIVO_MAX} caracteres.'})

    try:
        resultado = reagendar.reagendar(
            reserva.pk, nueva_fecha=nueva_fecha, nueva_hora=nueva_hora, nueva_fecha_regreso=nueva_fecha_regreso,
            token=_token_enviado(request.POST), usuario=request.user, puede_autorizar_48h=puede_autorizar,
            motivo_excepcion=motivo if requiere else '', avisar_cliente=avisar_marcado,
        )
    except reagendar.ErrorDeReagendado as exc:
        campo = CAMPOS_DE_ERROR.get(exc.campo, 'general')
        if campo == 'motivo_excepcion':
            return paso_dos_con({campo: exc.mensaje})
        return _paso_uno(modelo_admin, request, reserva, volver, valores, {campo: exc.mensaje})

    _dejar_constancia(modelo_admin, request, resultado, avisar_marcado, motivo)
    return HttpResponseRedirect(volver or ficha)


# ---------------------------------------------------------------------------------------------------------------
# Constancia: History y notificacion persistente
# ---------------------------------------------------------------------------------------------------------------

def _dia_vigente(objeto):
    """El primer dia que ve el cliente: el inicio del paquete si lo hay, si no la fecha."""
    return getattr(objeto, 'inicio_paquete', None) or getattr(objeto, 'fecha', None)


def _quien_avisa(resultado, avisar_marcado):
    """'sí' | 'no' | 'sin correo' para el History."""
    if resultado.correo_encolado:
        return 'sí'
    if avisar_marcado and not resultado.reserva.correo_cliente:
        return 'sin correo'
    return 'no' if not resultado.reserva.correo_cliente is False else 'no'


def _dejar_constancia(modelo_admin, request, resultado, avisar_marcado, motivo):
    reserva = resultado.reserva
    antes = resultado.antes
    ficha = reverse('admin:bookings_reserva_change', args=[reserva.pk])
    sin_correo = not reserva.correo_cliente
    if resultado.correo_encolado:
        avisado = 'sí'
    elif sin_correo:
        avisado = 'sin correo'
    else:
        avisado = 'no'

    antes_largo = fecha_larga(_dia_vigente(antes), getattr(antes, 'hora', None))
    ahora_largo = fecha_larga(_dia_vigente(reserva), reserva.hora)
    mensaje = f'Reagendada de {antes_largo} a {ahora_largo}. Cliente avisado: {avisado}.'
    if resultado.excepcion_48h:
        # En minusculas y seguido del usuario: es el texto de ARCH D3 («excepción de 48 h autorizada por X: motivo»).
        mensaje += f' Con excepción de 48 h autorizada por {request.user.get_username()}: {motivo}'
    modelo_admin.log_change(request, reserva, mensaje)

    capitan = getattr(antes, 'capitan', '') or ''
    aviso_capitan = f' Avísale al capitán {capitan} del nuevo día.' if capitan else ''
    antes_corto = _dia_vigente(antes).strftime('%d/%m/%Y') if _dia_vigente(antes) else ''
    ahora_corto = _dia_vigente(reserva).strftime('%d/%m/%Y')
    # El feed dura 90 dias y no se anonimiza: nombre y fechas, nunca el correo ni el telefono.
    texto = f'Reagendaste a {reserva.nombre_cliente} del {antes_corto} al {ahora_corto}.'
    ambar = False
    if resultado.excepcion_48h:
        texto += ' Se autorizó una excepción de 48 h.'
        ambar = True
    if resultado.correo_encolado:
        pantalla = (f'Reagendaste a {reserva.nombre_cliente} al {fecha_larga(_dia_vigente(reserva), con_anio=False)}. '
                    'El correo sale en unos segundos; si no sale, te avisa Notificaciones.')
    else:
        ambar = True
        cierre = ('El cliente no tiene correo. Avísale por WhatsApp.' if sin_correo
                  else 'Reagendada sin avisar al cliente. Avísale tú.')
        texto += f' {cierre}'
        pantalla = (f'Reagendaste a {reserva.nombre_cliente} al {fecha_larga(_dia_vigente(reserva), con_anio=False)}. '
                    f'{cierre}')
    if resultado.excepcion_48h:
        pantalla += ' Se autorizó una excepción de 48 h.'
    texto += aviso_capitan
    pantalla += aviso_capitan

    avisar(
        request, Notificacion.Nivel.AVISO if ambar else Notificacion.Nivel.EXITO, texto,
        empresa=reserva.empresa, tipo=Notificacion.Tipo.CAMBIO_FECHA,
        motivo=motivo if resultado.excepcion_48h else '',
        enlace_url=ficha, enlace_texto='Ver reserva', mensaje=pantalla,
    )


def url_de_reagendar(reserva_pk, volver=''):
    """La URL de la pantalla, con `?volver=` solo si es una ruta propia."""
    url = reverse('admin:bookings_reserva_reagendar', args=[reserva_pk])
    volver = enlace_seguro(volver)
    return f'{url}?volver={quote(volver, safe="/")}' if volver else url


def volver_desde_referer(request, por_defecto):
    """De donde venia la persona (lista con sus filtros): solo si el Referer es de este mismo sitio."""
    referer = request.META.get('HTTP_REFERER', '')
    partes = urlparse(referer)
    if partes.netloc and partes.netloc != request.get_host():
        return por_defecto
    ruta = partes.path + (f'?{partes.query}' if partes.query else '')
    return enlace_seguro(ruta) or por_defecto
