# ARCH: Reagendar reserva

> Lector: quien implementa (3 a 4 devs en paralelo) y el dueño que aprueba el gate.
> Decisión central: reagendar es una pantalla propia en dos pasos (elegir, revisar y confirmar) que delega TODAS las reglas al modelo `Reserva` y al motor de cupo. Al confirmar, manda un correo al cliente con el mismo estilo de `plantilla.py`. No hay migración y no hay permiso nuevo.
> Pedido original: «un botón en la lista de reservas y en el calendario que se llame específicamente reagendar con una vista específica y que mande un correo de confirmación al cliente». Entregado por el arquitecto de great_cto; el dueño delegó las decisiones. Estado: gate:arch aprobado por el dueño (2026-10-28, permiso durable).

```
SIGNALS
  input      nueva fecha/hora/regreso que teclea la vendedora o el jefe (POST); id de reserva en la URL; ?volver= | tratar como hostil: validar en servidor, volver= solo rutas propias (enlace_seguro)
  boundary   correo sale de la empresa al cliente por Resend (admin → exterior); entre empresas: RLS (una vendedora no ve reservas de otra empresa)
  data       historial (LogEntry) y notificación con nombre del cliente y fechas; el feed NO guarda correo ni teléfono (CLAUDE.md); 90 días de retención
  money      el cobro y el precio NO se tocan. El dinero en riesgo es sobreventa de cupo (panga o habitación vendida dos veces) por una carrera
  control    la regla de 48 h: su inverso es que un cliente real no pueda moverse a tiempo. La excepción de Jefe es una vía de abuso si no deja rastro
  execution  correo en transaction.on_commit (llega tras la respuesta); candados de cupo bajo concurrencia; doble clic = doble correo si no hay token
SIZE  Medium: toca reglas de cupo, correo, admin y calendario. Sin servicio ni infraestructura nueva. 0 migraciones.
GATE  gate:arch, forzado por `control`, `execution` y `boundary`. Ningún gate de seguridad extra: no hay dato nuevo ni superficie pública nueva.
```

## 1. Problema

Hoy reagendar es editar `fecha`/`hora` en el formulario de `ReservaAdmin`. Las reglas ya corren en el modelo: `Reserva._validar_cambio_de_fecha` (48 h, `models.py:1177-1192`), el motor de cupo (`validar_cupo_diario`, `models.py:210-229`), una panga y un capitán por día (`models.py:1109-1146`), y la resincronización de salidas, viajes y habitaciones dentro de `_guardar_reserva` (`models.py:918-927`).

Faltan tres cosas:
- No hay un lugar donde se vea qué cambia antes de guardar.
- El admin NO le dice nada al cliente: `ReservaAdmin._avisar_cambio_de_fecha` solo emite un aviso interno que dice «avísale tú» (`admin.py:951-963`).
- Hay trampas silenciosas. La más seria: si se quita la panga al cambiar de día, `aviso_asignacion_enviado_en` sigue puesto y la señal ya no vuelve a mandar el correo de asignación (`signals.py:55-66`).

## 2. Non-goals

- Cambiar precio, cobro o IVA, o tocar Stripe. El `PaymentIntent` solo lleva `reserva_id` en su metadata (`payments/views.py:695`) y el precio no depende de la fecha (`precio_sugerido.py:50`).
- Reagendar `pendiente_pago`, `cancelada` o `completada`.
- Reagendar reservas de una `Orden` cruza-empresa (ver D2).
- Un correo bilingüe. La reserva no guarda idioma (D8).
- WhatsApp: no hay plantilla aprobada por Meta para esto.
- Botón de «reenviar correo». Si falla, se avisa por WhatsApp, igual que en la asignación.
- Re-validar y conservar el vehículo de un traslado (D4).
- Cambiar `_validar_cambio_de_fecha` para el formulario normal del admin. Ese camino queda igual.

## 3. Decisiones numeradas

**D1. Pantalla en dos pasos que delega al modelo.** Paso 1 «Elegir» (GET y POST `paso=revisar`) y paso 2 «Revisar y confirmar» (POST `paso=confirmar`).
- El servicio nuevo `apps/bookings/reagendar.py` asigna los campos nuevos, toma candados, corre `full_clean()` y `save()`. No duplica ninguna regla de cupo: `Reserva.clean()` sigue siendo la única fuente (`models.py:965-1026`).
- Alternativa descartada: guardar directo con un formulario de una sola pantalla, como `pagar_transferencia_view`. El correo es irreversible. Un clic con la fecha mal tecleada le avisa al cliente algo falso y no se puede des-enviar. El paso 2 muestra el «Antes → Ahora» y las consecuencias antes de la acción irreversible.
- Alternativa descartada: reescribir las reglas en el servicio. Divergirían del formulario del admin, de `/api/cupo/` y de la Agenda, que hoy comparten el motor.

**D2. Estados reagendables.** Solo `pagada` y `asignada`, y nunca una reserva con `orden_id`.
- Se bloquea además con `en_disputa=True`. El comentario del campo dice que una reserva en disputa «no se toca hasta que Stripe resuelva» (`models.py:644`).
- `pendiente_pago` no ocupa cupo (`models.py:82`): no hay nada agendado que mover y el cliente aún no confirmó. `completada` ya ocurrió. `cancelada` está terminada.
- La Orden queda fuera: cada componente es una `Reserva` de otra empresa y la vendedora de A no puede leer las de B por RLS; mover un componente rompe el paquete; y cada empresa cobra en su propia cuenta con captura manual. `transferencia.py:36-38` hace la misma exclusión. Un componente de orden NO muestra botón; si alguien llega por URL, ve un aviso en español y no se cambia nada.
- Alternativa descartada: permitir `pendiente_pago` (su fecha es editable hoy sin regla de 48 h, y no hay a quién avisar).

**D3. Regla de 48 h: se mantiene para todos; el Jefe y el operador de plataforma pueden saltarla con motivo escrito y rastro.**
- Hoy la regla no admite excepción para nadie (`models.py:1181-1192`). El sitio la promete al cliente («Cambio de fecha: 48 h», `plantilla.py:48-51`).
- Diseño: en el paso 2, si faltan menos de 48 h (o la salida original ya pasó, caso «atrasado»), se muestra un aviso y, solo si quien opera es Jefe de la empresa (`scope.es_jefe_actual`) u operador de plataforma, un campo `motivo_excepcion` obligatorio (10 a 200 caracteres). La vendedora ve el error del modelo más «pídele a un jefe que lo autorice».
- El rastro es doble: el History (`log_change`) lleva «excepción de 48 h autorizada por X: motivo», y la notificación sale en nivel AVISO para toda la empresa.
- Mecanismo: el servicio pone `reserva._excepcion_48h = True` y `_validar_cambio_de_fecha` hace `return` si existe (cambio de 3 líneas en `models.py:1181`). El atributo solo existe en memoria y solo lo pone `reagendar.py` tras verificar rol y motivo.
- Regla adicional (el modelo no la tiene): la nueva salida debe ser futura. Aplica también al jefe.
- Alternativa descartada: excepción para la vendedora con casilla (quita el control sin fricción). Alternativa descartada: regla absoluta (empuja a editar la base a mano).

**D4. Panga, capitán y vehículo al cambiar de día.** Se conserva cada recurso solo si sirve en la(s) nueva(s) fecha(s). Si no, se quita y se avisa. Se evalúan por separado.
- Panga: sirve si está activa, no está en `EmbarcacionNoDisponible` en ninguno de los días de mar nuevos, no la usa otra reserva que ocupa cupo, y su capacidad alcanza. La regla es la de `ContextoAsignacion.pangas_que_sirven` (`admin.py:2313-2321`). `EmbarcacionNoDisponible` NO lo valida `clean()`; solo la Agenda lo filtra. Por eso el servicio lo consulta explícitamente.
- Capitán: sirve si no tiene otro viaje esos días (`models.py:1142-1146`).
- Si cambia el día de una reserva con ambos y alguno se quita, se pone `aviso_asignacion_enviado_en = None`. Sin eso, la reasignación posterior nunca le mandaría al cliente el correo con su capitán (`_le_toca_aviso`, `signals.py:60`). Si se conservan los dos, el flag queda y el correo de reagendado ya nombra capitán y panga.
- `_derivar_estado_de_asignacion` baja `asignada` a `pagada` solo si la panga se quita (`models.py:960-963`).
- El capitán no usa el sistema: la vendedora le avisa por fuera. Por eso la pantalla de éxito y la notificación dicen «Avísale a {capitán} del nuevo día».
- Vehículo de traslado: `sincronizar_viajes` ya lo desasigna cuando cambia la fecha de un tramo, y un cambio solo de hora lo conserva. No se reimplementa. La vista previa lo dice («se quita el vehículo X; asígnalo de nuevo en «Asignar vehículos»»).

**D5. Precio y cobro: no se tocan.**
- El precio no depende de la fecha (`precio_sugerido.py:50`).
- Efecto indirecto: `clean()` revalida el código promocional en cada guardado de una reserva ocupante (`models.py:1008-1013`; **verificar con prueba**). Una promoción vencida desde la compra haría fallar el reagendado. El servicio pone `reserva._reagendando = True` y `clean()` salta ese bloque cuando existe. El precio ya está congelado y el cliente ya lo pagó.

**D6. Permisos: sin permiso nuevo y sin `setup_roles`.**
- Se exige `bookings.change_reserva` (Vendedora, Jefe y Operador ya lo tienen). Se usa `self.has_change_permission(request, reserva)` y `self.get_object(request, id)` igual que `pagar_transferencia_view` (`admin.py:1442-1446`): otra empresa devuelve 404.
- El Jefe se detecta con `scope.es_jefe_actual(request)` y el operador con `scope.es_operador_plataforma(request.user)`.
- Alternativa descartada: permiso custom. Exige migración de permisos y correr `setup_roles` en Render, que REEMPLAZA los permisos de cada grupo.

**D7. El correo es opcional con la casilla «Avisar al cliente por correo», marcada por defecto.**
- Se desmarca al corregir un error propio de captura. Se deshabilita (y queda desmarcada) si la reserva no tiene correo, con aviso «avísale por WhatsApp».
- Una reagendada sin aviso deja notificación en nivel AVISO («Reagendada sin avisar al cliente») y lo escribe el History.

**D8. Idioma: español, igual que todos los correos al cliente.** `Reserva` no guarda idioma y la plantilla fija `lang="es"` (`plantilla.py:189`). Limitación del sistema, no de esta pieza (R5). Sin correo del cliente: sin envío, mensaje «avísale por WhatsApp» y el cambio igual se hace.

**D9. Cuándo sale el correo: `transaction.on_commit`.**
- `EmpresaScopeMiddleware` envuelve la petición entera en un `atomic` (`middleware.py:33-34`), así que lo encolado corre después de que la vista terminó. Patrón de `transferencia.py:140` y `signals.py:86`.
- Razones frente a enviar en línea: (1) el cliente nunca recibe una fecha que no quedó confirmada; (2) enviar en línea sostendría el candado de cupo hasta 10 s mientras Resend responde (`TIMEOUT_SEGUNDOS = 10`, `services.py:25`); (3) está probado en este repo.
- El resultado llega por el feed: el callback reabre `scope.con_empresa(empresa)` y escribe `registrar_notificacion` (éxito o error con el motivo de `motivo_fallo_aviso`). El mensaje en pantalla dice: «El correo sale en unos segundos; si no sale, te avisa Notificaciones.»
- El correo no puede deshacer el reagendado: va fuera de la transacción, `enviar_correo_reagendado` no lanza, y el callback va en `try/except` que solo registra el tipo de error.

**D10. Concurrencia y orden de candados** (orden documentado en CLAUDE.md y `confirmacion.py:161-170`).
1. `Reserva.objects.select_for_update().get(pk=…)` sin joins (patrón de `transferencia.py:96`). `from_db` toma `_salida_original` y `_cupo_original` de esa fila ya bloqueada.
2. Candados de mar (`bloquear_cupo(empresa_id, dia)`, `candado.py:18-30`) para cada día de mar NUEVO, en orden de fecha.
3. Candados de hospedaje (`bloquear_recurso`, `candado.py:48`) de los recursos activos del servicio de hospedaje, por `pk` ascendente (`hospedaje_sync.py:51-52`).
4. Solo después, `full_clean()` y `save()`.
- Cierra un hueco real: para un paquete de un solo día de mar, `_validar_cupo_de_paquete` evalúa sin candado.
- Bajo Postgres: `SET LOCAL lock_timeout = '5s'`; `OperationalError` por timeout o deadlock (`55P03`/`40P01`) devuelve «El sistema está ocupado confirmando otras reservas de ese día. Intenta otra vez en unos segundos.» Un reintento, como `crear-pago`.
- Token optimista: la pantalla manda (`fecha`, `hora`, `inicio_paquete`, `estado`) tal como los vio. Con la fila bloqueada se comparan con la base. Si difieren: «Esta reserva cambió mientras la revisabas (ahora: …). Revisa y vuelve a elegir.» No se usa `actualizado_en` porque asignar una panga lo mueve.

**D11. Modelo de datos: cero campos, cero migración, sin trabajo de RLS.** El «antes» se calcula en memoria y viaja al callback como datos planos. El History (`django_admin_log`, sin empresa) y la notificación guardan antes/después en texto. Tipo de notificación: `Notificacion.Tipo.CAMBIO_FECHA` (`tenancy/models.py:182`).

**D12. Alcance por tipo de reserva** (el servicio decide qué campos derivan de lo que teclea la persona; las reglas son del modelo):
- Servicio suelto de un día (pesca, paseo, safari, traslado `recepcion_aeropuerto` o `redondo_actividad`): `fecha` y `hora`. La hora se valida con `ventana_horaria()` (`models.py:1051-1057`).
- Hospedaje suelto (`por_noche`): se elige la nueva llegada y la salida se conserva por noches. Las habitaciones se mueven en `save()`.
- Paquete de una empresa: se elige la nueva llegada; `inicio_paquete`, `fecha` (ancla de la actividad) y `fecha_salida` se derivan con `fecha_ancla` y `fecha_salida` de `calendario_paquete.py:41-56`, igual que el alta (`forms_alta_reserva.py:227-252`). La regla de 48 h se mide contra la fecha MÁS TEMPRANA. Las salidas se recrean con `sincronizar_salidas`.
- Traslado `redondo_aeropuerto`: campo extra `nueva_fecha_regreso`. Se actualiza `DetalleTransporte.fecha_regreso` en la misma transacción. **Verificar** que `DetalleTransporte.save()` re-sincroniza los tramos.

**D13. Tres puntos de entrada, una sola pantalla.** Todos llevan a `/admin/bookings/reserva/<id>/reagendar/` (`name='bookings_reserva_reagendar'`, registrada en `ReservaAdmin.get_urls` antes de `super().get_urls()`).
- Lista: acción de fila «Reagendar» en `actions_row` (`admin.py:1103`), con el patrón de `accion_fila_cancelar`. **Verificar** si Unfold permite ocultarla por fila. Plan: visible en todas; en filas no reagendables la vista responde con aviso en español y redirige (nunca 403 ni 500).
- Calendario: botón «Reagendar» en el popover de Semana y Día (`_calendario_detalle.html:49-54`), solo si la reserva se puede reagendar y el usuario tiene `change_reserva`. En Mes no hay popover y cada evento enlaza a la ficha.
- Ficha de la reserva: botón en el resumen (`reserva_change_form.html:29-41`; `_boton_reagendar` análogo a `_boton_pagar_transferencia`, `admin.py:1509-1513`).

## 4. Flujo paso a paso

1. La persona hace clic en «Reagendar» (lista, popover o ficha) con `?volver=<ruta del admin>`.
2. **GET**: `get_object` (404 si otra empresa) → `has_change_permission` (403) → `motivo_no_reagendable` (si hay motivo: aviso en español y redirige a `volver`) → pinta el paso 1 con fecha y hora actuales y, para servicios de mar, «próximas fechas con lugar» (`disponibilidad_por_fecha`, `models.py:171-189`).
3. **POST `paso=revisar`**: valida sintaxis y rangos y llama `proponer(...)` (solo lectura, sin candados). Con errores, repinta el paso 1 con el error junto al campo. Si no, pinta el paso 2.
4. **Paso 2**: «Antes → Ahora», lista de consecuencias, casilla «Avisar al cliente», campo de motivo si aplica y botón de confirmar. Los datos elegidos y el token viajan en campos ocultos.
5. **POST `paso=confirmar`** → `reagendar(...)`, un solo `transaction.atomic()`:
   a. `SET LOCAL lock_timeout` (Postgres).
   b. Bloquea la fila, relee, revalida estado y compara el token.
   c. Calcula fechas derivadas y la regla de 48 h. Sin autorización o sin motivo: `ErrorDeReagendado`. Con ambos: `_excepcion_48h = True`.
   d. Toma los candados en el orden de D10.
   e. Decide qué se conserva (D4); si quita algo, pone `aviso_asignacion_enviado_en = None`.
   f. Asigna campos, pone `_reagendando = True`, `full_clean()`, `save()` y, si aplica, guarda el `DetalleTransporte`.
   g. Si `avisar_cliente` y hay correo: `transaction.on_commit(callback)` con datos planos (no el objeto).
6. La vista: `log_change` con antes/después, motivo de excepción y «Cliente avisado: sí/no/sin correo»; `avisar(...)` en línea (pantalla y feed) en nivel EXITO, o AVISO si hubo excepción o no se avisa. Si quitó panga o capitán, o dejó un capitán, añade «avísale a {capitán}». Redirige a `volver`, o a la ficha si no hay o no es seguro (`enlace_seguro`, `notificaciones.py:59`).
7. Al confirmar la transacción corre el callback: abre `scope.con_empresa(empresa)`, relee la reserva con `select_related`, llama `enviar_correo_reagendado` (nunca lanza) y registra la notificación de éxito o de error con motivo.

Cualquier `ErrorDeReagendado`, `ValidationError`, `SinCupoError` o `IntegrityError` deshace el savepoint: no queda nada a medias. Se repinta el paso 1 con el mensaje.

## 5. Contrato del servicio (`apps/bookings/reagendar.py`, nuevo)

```python
ESTADOS_REAGENDABLES = (Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA)

def motivo_no_reagendable(reserva) -> str   # '' si se puede; texto en español si no
def puede_reagendarse(reserva) -> bool      # == (motivo_no_reagendable(reserva) == '')

@dataclass(frozen=True)
class Propuesta:                            # solo lectura
    fecha; hora; inicio_paquete; fecha_salida; fecha_regreso      # derivados
    dias_de_mar: list[date]
    panga: 'conserva'|'quita'|None; capitan: 'conserva'|'quita'|None; motivo_panga: str
    vehiculos_a_quitar: int
    motivo_sin_cupo: str|None; proxima_fecha: date|None
    requiere_excepcion_48h: bool; limite_48h: datetime|None
    errores: dict[str, str]                 # campo -> mensaje

def proponer(reserva, *, nueva_fecha, nueva_hora=None, nueva_fecha_regreso=None, hoy=None) -> Propuesta

class ErrorDeReagendado(Exception):         # .mensaje, .campo ('' = general)

def reagendar(reserva_pk, *, nueva_fecha, nueva_hora, nueva_fecha_regreso, token,
              usuario, puede_autorizar_48h, motivo_excepcion, avisar_cliente) -> Resultado
# Resultado: reserva, antes (AntesDelCambio), panga_conservada, capitan_conservado,
#            vehiculos_quitados, excepcion_48h, correo_encolado
```

Cambio al modelo (`models.py`, ~6 líneas): `_validar_cambio_de_fecha` retorna si `getattr(self, '_excepcion_48h', False)`; el bloque del código promocional (`models.py:1008-1013`) se salta si `getattr(self, '_reagendando', False)`.

## 6. Contrato de la vista

URL: `GET|POST /admin/bookings/reserva/<id>/reagendar/` · `name='bookings_reserva_reagendar'`.

| Campo | Cuándo aparece | Validación |
|---|---|---|
| `nueva_fecha` (date) | siempre | requerida; hoy ≤ fecha ≤ hoy+365 días |
| `nueva_hora` (time) | si la reserva tiene hora o el servicio tiene ventana | dentro de `ventana_horaria()` (pesca 05:00 a 07:00) |
| `nueva_fecha_regreso` (date) | traslado `redondo_aeropuerto` | posterior a `nueva_fecha` |
| `avisar_cliente` (checkbox) | siempre; deshabilitada sin correo | marcada por defecto |
| `motivo_excepcion` (text) | paso 2, solo Jefe u operador y solo si faltan menos de 48 h | 10 a 200 caracteres, obligatorio en ese caso |
| `paso`, `token_*`, `volver` (ocultos) | siempre | token = fecha, hora, `inicio_paquete` y estado vistos; `volver` solo si `enlace_seguro` |

Errores en español, junto al campo:
- Estado no reagendable: «Esta reserva está {estado}: solo se reagendan reservas pagadas o asignadas.»
- Orden: «Esta reserva es parte de un paquete de varias empresas. El cambio se coordina con las dos empresas; aquí no se puede.»
- En disputa: «Esta reserva está en disputa con el banco. Espera a que Stripe resuelva.»
- Sin cambio: «Elige una fecha u hora distinta de la actual.»
- Pasado: «La nueva fecha ya pasó.»
- Año: «La nueva fecha queda a más de un año. Revisa el año.»
- 48 h (vendedora): el texto del modelo (`models.py:1189-1192`) más «Pídele a un jefe que lo autorice.»
- Sin cupo: el mensaje del motor (código `sin_cupo`) más «La próxima fecha con lugar es {fecha}» (`proxima_fecha_disponible`, `models.py:155-168`) en servicios de mar.
- Token vencido y candado ocupado: los textos de D10.
- Dato inválido en un campo que no está en el formulario: «No se puede guardar porque la reserva tiene un dato inválido en {campo}: {mensaje}. Corrígelo en la ficha.»

Sin cambios en `calendario.js` (los botones del popover son enlaces normales) ni en `calendario.css` (`.cal-boton` ya existe).

**Dirección de la vista (la pasada PFD la hace quien arma la vista):**
- Una sola tarea por pantalla.
- El «Antes → Ahora» es el héroe del paso 2, con lo que cambia resaltado.
- Las consecuencias en frases cortas ordenadas por importancia: el cliente recibirá un correo; panga y capitán; vehículo; «el pago no cambia».
- La etiqueta del botón primario sigue a la casilla: «Reagendar y avisar al cliente» o «Reagendar».
- El aviso de 48 h va en línea, no en modal.
- Esquinas rectas o círculo, sin sombras ni degradados.
- CSS propio `static/bookings/reagendar.css`: Unfold sirve su Tailwind ya compilado y una clase nueva no existe.

## 7. Correo al cliente

Módulo nuevo `apps/notifications/correo_reagendado.py`. Se dejan intactos `services.py` y `plantilla.py`; se reutilizan `plantilla.correo(...)`, `plantilla.a_texto`, `services._html`, `services._par_punto_de_encuentro`, `services._saldo_en_efectivo`, `services._empresa_de`.

- Función pública: `enviar_correo_reagendado(reserva, antes) -> bool`. Nunca lanza. Pone `reserva.motivo_fallo_aviso` como `enviar_correo_asignacion` (`services.py:317-358`): sin correo, Resend sin configurar o el motivo que respondió el proveedor (`motivo_para_persona`). Respeta `RESEND_BCC`. Usa una función propia para el POST a Resend; no se refactoriza lo existente.
- `antes` es un dataclass simple (`AntesDelCambio`: `fecha`, `hora`, `inicio_paquete`, `fecha_salida`, `fecha_regreso`, `panga`, `capitan` como nombres).
- **Asunto** (folio, como `_asunto` en `services.py:110-112`): `Reserva reagendada #123 — 2026-12-08 06:00` (con hora «por definir» si no hay).
- **Campo de color**: `plantilla.actividad_de(reserva)` (mar, traslado o estancia).
- **Titular**: «Reserva reagendada». **Folio**: `reserva.pk`. **Producto**: nombre del servicio y empresa. **Intro**: «Hola {nombre}, tu reserva quedó reagendada.» **Vista previa**: nueva fecha, hora y «antes {fecha vieja}».
- **Sección «Tu nueva fecha»**, en filas: Antes (día largo y hora viejos); Ahora (nuevos); Llega a las (mar, 15 min antes); Sales de / Punto de encuentro (de `Servicio.punto_salida`; vacío → «Te lo confirmamos por WhatsApp»; hospedaje sin dato → sin renglón); Personas; Capitán y Panga solo si se conservaron; Paquete: Llegada, Salida y Noches; Traslado: Fecha de regreso.
- **«El dinero»**: solo el bloque de saldo en efectivo si queda saldo («Quedan X MXN por liquidar en efectivo el día del viaje»). Nunca «Pagaste hoy».
- **«Qué sigue»**: «Tu pago sigue vigente: no tienes que pagar de nuevo.» En mar: si se quitó la panga o el capitán, «Te llega otro correo con tu capitán y tu panga en cuanto queden asignados»; si se conservaron, «Tu capitán y tu panga siguen siendo los mismos.» Para todos: «Si esta fecha no te funciona, escríbenos por WhatsApp con tu folio.»
- **Garantías** (`con_garantias=True` solo en mar): el bloque de «48 h» ya dice que se puede cambiar con 48 h desde la fecha vigente, que ahora es la nueva.
- Todo dato de persona pasa por `_html`.
- **Texto plano**: `plantilla.a_texto(html)`, en el mismo orden.

## 8. Integración (archivos)

- `admin.py`: `get_urls` (+1 ruta), `accion_fila_reagendar`, `_boton_reagendar`, entrada nueva en `resumen_reserva`, `actions_row` (`admin.py:1103`). La lógica de la vista vive en un archivo nuevo para no engordar `admin.py`.
- `calendario.py`: propiedad `Pieza.se_puede_reagendar` (`calendario.py:62-84`), que llama a `reagendar.puede_reagendarse`. `_calendario_detalle.html`: botón con `perms.bookings.change_reserva`.
- Sin cambios en `config/urls.py`: la ruta va dentro del admin de Reserva.

## 9. Permisos y despliegue

- Sin permiso nuevo, sin `setup_roles`, sin variable de entorno nueva (usa `RESEND_API_KEY`, `RESEND_FROM` y `RESEND_BCC` existentes).
- Solo backend, sin migración. Rollback = revertir el commit.
- Observabilidad: `logger.info` con ids (reserva, usuario) y sin texto del cliente; fallo de correo con `logger.exception` (patrón de `services.py:355`).

## 10. Pruebas (TDD, rojo antes que verde)

**`apps/bookings/tests_reagendar.py` (servicio):**
- Reagenda pagada y asignada; rechaza pendiente, cancelada, completada, con orden y en disputa.
- 48 h: vendedora bloqueada; jefe con motivo pasa; jefe sin motivo falla; salida original pasada solo con excepción.
- Nueva fecha pasada falla incluso para jefe; sin cambio falla; tope de un año.
- Cupo: día lleno, `sin_panga` y `CupoDiario` en 0 dan `sin_cupo`; el apartado vigente de otro cliente cuenta.
- Panga y capitán: se conservan si sirven; se quitan si hay choque, `EmbarcacionNoDisponible` o capacidad. Si se quita algo, `aviso_asignacion_enviado_en` queda en `None` y la reasignación posterior sí manda el correo de asignación. `asignada` baja a `pagada` si se quita la panga.
- Con ambos conservados y flag ya puesto, la señal no manda correo de asignación.
- Paquete: derivación de `inicio_paquete`, `fecha` y `fecha_salida`; salidas recreadas; hospedaje mueve habitaciones; sin habitación → mensaje sin cambios; la regla de 48 h usa la fecha más temprana.
- Traslado: vehículo desasignado al cambiar de día y conservado si solo cambia la hora; `fecha_regreso` actualiza los tramos.
- Promoción vencida no bloquea (D5).
- `precio_total`, `monto_*` y `MovimientoDinero` idénticos antes y después.
- Token vencido; doble envío del mismo formulario: el segundo falla y solo hay un correo encolado.
- `on_commit` con `captureOnCommitCallbacks`: el correo no sale si hay rollback; el fallo del envío no deshace la fecha.

**`apps/notifications/tests_correo_reagendado.py`:** asunto con folio; antes/ahora; punto de encuentro de `Servicio.punto_salida`; escape HTML de un nombre malicioso; texto plano; variantes mar, traslado y estancia/paquete; sin correo → `False` con motivo; Resend caído (mock) → `False` sin lanzar, con `motivo_fallo_aviso`; `RESEND_BCC`.

**`apps/bookings/tests_reagendar_vista.py`:** 404 de otra empresa (RLS); 403 sin `change_reserva`; el operador puede; los dos pasos y el repintado con errores; el campo de motivo solo lo ve un jefe; `volver` malicioso (`//evil`, `javascript:`) se ignora; casilla deshabilitada sin correo; acción de fila y botón de la ficha apuntan a la URL; fila no reagendable → aviso y redirige; History y notificación creadas (texto sin correo ni teléfono); callback: éxito y error con motivo.

**`apps/bookings/tests_calendario_reagendar.py`:** el popover trae «Reagendar» solo en reservas reagendables y para quien tiene permiso; no en canceladas, completadas ni órdenes.

**Concurrencia (solo Postgres; sqlite no prueba nada aquí):**
1. Dos reagendados al último lugar del mismo día: gana exactamente uno, el otro recibe `sin_cupo`.
2. Doble envío de la misma reserva: un solo cambio y un solo correo.
3. Reagendar contra el webhook de reembolso total (cancelación): el estado se revalida bajo candado.
4. Reagendar hospedaje contra la venta de la última habitación: nadie queda con la habitación duplicada (`EXCLUDE`).
5. Intercambio A: d1→d2 y B: d2→d1 a la vez: sin deadlock (o con reintento y mensaje).
6. Rol sin `BYPASSRLS` (`ci_rls`): el servicio, el callback y la notificación escriben dentro de `con_empresa`.

## 11. Riesgos

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | Doble clic o dos operadoras mandan dos correos o pisan una fecha | Media | Medio | Token optimista bajo fila bloqueada (D10); prueba 2 de carreras |
| R2 | Carrera de cupo sobrevende el último lugar | Baja | Alto | Candados previos en el orden de D10; la `EXCLUDE` protege hospedaje; pruebas 1, 4 y 5 |
| R3 | Un fallo de Resend deja al cliente sin aviso y nadie lo ve | Media | Medio | Notificación persistente con motivo (≤10 s en la campana), aviso en pantalla que lo anticipa, fallback «avísale por WhatsApp» |
| R4 | Abuso de la excepción de 48 h | Baja | Medio | Solo Jefe u operador, motivo obligatorio, rastro en History y notificación AVISO para toda la empresa |
| R5 | Cliente anglófono recibe el correo en español | Media | Bajo | Igual que los demás correos; mejora transversal (capturar idioma en checkout) |
| R6 | `full_clean()` falla por un dato viejo ajeno al formulario | Media | Bajo | Mensaje que nombra el campo y manda a corregirlo en la ficha |
| R7 | La promoción vencida bloquea el reagendado | Media | Medio | Flag `_reagendando` y prueba roja primero |
| R8 | Cliente recibe el correo de asignación y el de reagendado a la vez | Baja | Bajo | Caso raro; se documenta |
| R9 | Servicio desactivado desde la venta cambia `fecha_ancla` de un paquete | Baja | Medio | La vista previa muestra la fecha derivada antes de confirmar |
| R10 | Unfold no oculta la acción de fila por fila | Media | Bajo | Botón visible en todas las filas con aviso al entrar |
| R11 | Dos operadoras avisan al capitán de forma distinta | Media | Bajo | El aviso «avísale a {capitán}» está en pantalla y feed |

## 12. Archivos a tocar, con dueño disjunto

| Dueño | Archivos (exclusivos) | Contrato que consume |
|---|---|---|
| **A: núcleo** | `apps/bookings/reagendar.py` (nuevo), `apps/bookings/models.py` (solo `_validar_cambio_de_fecha` y el bloque promo de `clean()`), `apps/bookings/tests_reagendar.py`, `apps/bookings/tests_reagendar_carreras.py` | `enviar_correo_reagendado(reserva, antes)` de B |
| **B: correo** | `apps/notifications/correo_reagendado.py` (nuevo), `apps/notifications/tests_correo_reagendado.py` | `AntesDelCambio` definido aquí |
| **C: admin y vista** | `apps/bookings/admin.py`, `apps/bookings/reagendar_vista.py` (nuevo), `templates/bookings/reagendar.html`, `static/bookings/reagendar.css`, `templates/bookings/reserva_change_form.html`, `apps/bookings/tests_reagendar_vista.py` | `proponer`, `reagendar`, `ErrorDeReagendado`, `motivo_no_reagendable` de A |
| **D: calendario** | `apps/bookings/calendario.py`, `templates/bookings/_calendario_detalle.html`, `apps/bookings/tests_calendario_reagendar.py` | `puede_reagendarse(reserva) -> bool` de A |
| **Coordinador (al final)** | `backend/CLAUDE.md` (sección Reagendar), cierre de gate | — |

- Orden: A y B arrancan en paralelo (A usa un stub de B). D arranca ya con un stub de `puede_reagendarse`. C arranca con stubs de A y se integra cuando A termine.
- Antes de armar la vista C: pasada de perception-first-design (instrucción del dueño; sin taste).
- Antes de integrar: correr la suite completa contra Postgres con `ci_rls`.
- `models.py` es compartido; solo A lo edita y solo en las dos zonas indicadas.

## 13. Definición de terminado

- Botón «Reagendar» exacto en lista, calendario (Semana y Día) y ficha.
- Vista de dos pasos con mensajes en español.
- Correo con asunto con folio, antes/ahora y texto plano; el fallo no deshace el cambio y deja notificación con motivo.
- Historial y notificación persistente en cada reagendado.
- Cero migraciones; precio y cobro intactos.
- Suite verde en SQLite y Postgres (`ci_rls`); las pruebas de carrera en Postgres.

## 14. Revisión Well-Architected (resumen)

- Operación: sin infraestructura nueva, deploy solo backend, rollback = revertir el commit.
- Seguridad: autorización por objeto + RLS, `volver` saneado, texto del cliente escapado, sin PII nueva en el feed.
- Confiabilidad: candados ordenados, token optimista, correo post-commit sin efecto sobre los datos.
- Rendimiento: unas diez consultas por pantalla, sin bucles por fila.
- Costo: sin componentes cloud nuevos; un correo de Resend por reagendado.
- Sostenibilidad: reutiliza el motor y las plantillas existentes.

## Historial

- 2026-10-28 v1: ARCH del architect; gate:arch aprobado por el dueño (permiso durable «ejecuta el plan sin mi permiso»).
