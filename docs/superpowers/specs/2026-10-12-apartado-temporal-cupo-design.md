# Apartado temporal de cupo en el checkout web

Fecha: 2026-10-12. Rama de trabajo: `feat/backoffice-reservas` (worktree `.claude/worktrees/reservas`). Estado: diseño aprobado por el dueño sección por sección; revisado una vez por un crítico independiente (veredicto «revisión requerida»); esta versión incorpora sus hallazgos y la decisión del dueño de **incluir el hospedaje**.

## 1. Problema

Hoy el cupo se aparta hasta que Stripe confirma el pago. Al dar «listo» en el checkout la reserva queda `pendiente_pago` y **no ocupa cupo** (`ESTADOS_QUE_OCUPAN_CUPO = ['pagada','asignada','completada']`, `backend/apps/bookings/models.py:80-82`; decisión deliberada para que los checkouts abandonados no bloqueen el día). Ni `POST /reservas/` ni `crear-pago` validan cupo; la única validación real ocurre en el webhook (`reservar_cupo_al_confirmar`, `backend/apps/payments/services.py:126`), que reembolsa el 100% si no cabe.

Consecuencias verificadas leyendo el código:

1. Dos clientes pueden pagar el último lugar. La ventana dura todo el tiempo del pago (Stripe, 3D Secure, aviso del webhook), no milisegundos. Quien pierde se reembolsa solo.
2. El sitio no bloquea «Pagar» aunque el día esté lleno (solo muestra un aviso amarillo).
3. La pantalla posterior al pago muestra «¡Tu reserva está confirmada!» en cuanto Stripe aprueba la tarjeta, sin consultar al backend. Si el webhook cancela y reembolsa después, el cliente no se entera: no recibe correo ni WhatsApp (no existe aviso de cancelación) y, si recarga, ve el formulario en blanco.
4. Si el enlace del checkout trae una fecha pasada o inválida, el sitio la cambia a «mañana» sin avisar.

## 2. Objetivos y fuera de alcance

**Objetivos**

- Un apartado temporal de 15 minutos (configurable) tomado al pasar al pago, con candado, de modo que dos clientes no pasen el último lugar.
- Cuando no hay lugar, el cliente vuelve al paso del viaje con sus datos intactos y un aviso, antes de pagar.
- Una pantalla posterior al pago que no mienta.
- Avisar al cliente (correo) y a la empresa (alerta interna) cuando aun así se reembolsa por falta de cupo.
- (Independiente del apartado) avisar en el sitio cuando la fecha de un enlace se cambió por ser inválida.

**Alcance v1 (decidido por el dueño):** servicios sueltos con cupo físico — pesca por embarcación/día y hospedaje por noche — y paquetes de UNA empresa, incluidos los que tienen actividades de mar y hospedaje. Los servicios `bajo_demanda` (transporte) no tienen cupo físico y no apartan.

**Fuera de alcance:** paquetes que cruzan empresas (`Orden`; su validación sigue siendo el reembolso/`revertir_orden` de hoy), WhatsApp al cliente hasta tener una plantilla aprobada por Meta, un contador regresivo en vivo, notificación de cancelación para órdenes de dos empresas, mostrar los apartados en la Agenda/panorama del backoffice.

## 3. Decisiones (con su porqué)

| Decisión | Alternativas descartadas |
|---|---|
| El apartado se guarda en la reserva como un **retrato de la demanda apartada** (`apartado_demanda`, JSON) más su vencimiento (`apartado_hasta`). El motor de cupo cuenta ese retrato mientras `apartado_hasta > ahora`. | Recalcular la demanda al contar a partir de los campos de la reserva (no es definible para hospedaje, que reparte por habitación con intervalos propios; y un cambio posterior de fecha/personas movería el apartado a algo que nunca se validó). Tabla `ApartadoCupo` aparte (migración RLS + purga). Estado nuevo «apartada» en `ESTADOS_QUE_OCUPAN_CUPO` (obliga a revisar 17 consumidores, varios graves: Agenda/panorama, constraint EXCLUDE de hospedaje, regla de 48 h). |
| `ESTADOS_QUE_OCUPAN_CUPO` NO cambia. | — |
| El apartado no crea filas físicas (`ReservaSalida`, `ReservaOcupacion`): el retrato describe fechas y habitaciones y el motor lo suma como ocupación virtual. | Crear filas al apartar (dejaría basura y chocaría con el EXCLUDE de hospedaje). |
| Se toma en `crear-pago`, después de las validaciones tempranas y antes de hablar con Stripe, en una transacción corta propia. | Tomarlo en `POST /reservas/` (bloquearía inventario con formularios a medio llenar y bots); mantener el candado durante las llamadas a Stripe (serializaría todos los pagos del día). |
| Vencimiento pasivo (las consultas ignoran vencidos). | Tarea periódica de purga. |
| Duración 15 min, ajuste `APARTADO_MINUTOS`; `0` = apagado: **el motor ignora cualquier apartado existente** y `crear-pago` no aparta. | Duración fija; contador en vivo. |
| El apartado cuenta para todos (otros clientes web, alta manual del admin, generador de enlaces). La Agenda y el panorama no lo muestran (limitación documentada). | Que el personal pueda «saltarse» un apartado; mostrar apartados en la Agenda. |
| Cliente ve una línea fija «Tu lugar está apartado por 15 minutos» (solo si `crear-pago` devolvió `apartado_hasta`) y el apartado se renueva en silencio al pulsar «Pagar». | Contador regresivo visible (carga atencional extra y riesgo de ansiedad; evidencia débil en ambos sentidos); no decir nada. |

Evidencia externa: Rezgo (retenciones de 5 a 60 min), Resmark (30 min), CartGenie (15 min desde el checkout) y la guía de inventario limitado de Stripe usan retenciones al entrar al pago.

## 4. Arquitectura

### 4.1 Datos

- Migración: `Reserva.apartado_hasta = DateTimeField(null=True, blank=True)`, `Reserva.apartado_demanda = JSONField(null=True, blank=True)` y `Reserva.alerta_reembolso_fallido_en = DateTimeField(null=True, blank=True)` (ver 4.5). La tabla ya tiene RLS; no hay política nueva ni migración de datos.
- Forma del retrato (versionada, para poder cambiarla): 
  `{"v": 1, "salidas": [{"fecha": "AAAA-MM-DD", "personas": N, "servicio_id": S}], "habitaciones": [{"recurso_id": R, "inicio": "AAAA-MM-DD", "fin": "AAAA-MM-DD", "servicio_id": S}]}`
  - `salidas`: una por cada fecha de mar que el pago confirmaría. El retrato **refleja la lista de validación** de `reservar_cupo_al_confirmar` (`fechas_de_componente`, incluidas las fechas de componentes de una sola salida que esa función valida con `Reserva.fecha`, y `personas_de(servicio_id)`); en un servicio suelto, `Reserva.fecha` y `numero_personas`. Puede apartar un día más que lo que después ocuparía la reserva pagada vía `ReservaSalida`: es un sobre-apartado seguro, solo mientras está pendiente, y las pruebas lo fijan.
  - `habitaciones`: las habitaciones concretas elegidas al apartar, con el rango `[inicio, fin)`.
- Ajuste `APARTADO_MINUTOS` (entero, variable de entorno; `0` por defecto en base; local de desarrollo puede fijar 15; las pruebas lo sobreescriben).
- `apartado_hasta` y `apartado_demanda` son **solo de lectura** para la API pública (`ReservaCheckoutSerializer` usa una lista explícita de campos: no se agregan).

### 4.2 Motor de cupo (`backend/apps/bookings/cupo/`)

El conteo del apartado vive SOLO en el adaptador del motor, no en `ESTADOS_QUE_OCUPAN_CUPO`. Un apartado está **vigente** si `APARTADO_MINUTOS > 0`, la reserva sigue `pendiente_pago` y `apartado_hasta > ahora`.

- `obtener_contexto_cupo` (`adaptador.py`): además de las reservas y `ReservaSalida` ocupantes, suma a los grupos del día las entradas `salidas` de los retratos vigentes cuya fecha coincide, excluyendo la reserva evaluada (`excluir_pk`, que el motor ya acepta). Una reserva con apartado nunca cuenta dos veces: sus fechas salen solo del retrato, no de `Reserva.fecha` ni de `ReservaSalida` (que no existen todavía).
- `obtener_contexto_rango` y la cifra `ocupadas` de `/api/cupo/`: mismo criterio, con las mismas consultas agrupadas (los retratos vigentes se cargan en una sola consulta por empresa y rango, sin trabajo por reserva).
- Hospedaje: `obtener_recursos_con_ocupaciones` suma a cada habitación los intervalos `[inicio, fin)` de las entradas `habitaciones` de los retratos vigentes del mismo servicio, excluyendo la reserva evaluada. Con eso `recursos_disponibles_en_rango` y `PorNoche.evaluar_ocupacion` funcionan sin cambios de lógica: una habitación apartada simplemente aparece ocupada en ese rango.
- `bajo_demanda` no aparta.
- Los endpoints públicos (`/api/cupo/`, `/api/cupo/rango/`, `proxima_fecha_disponible`) aceptan el `checkout_id` en una **cabecera `X-Checkout-Id`** (no en la URL, para que ese identificador, que funciona como credencial de la reserva, no quede en los registros de acceso; se agrega a las cabeceras permitidas por CORS). Si coincide con una reserva con apartado vigente, ese apartado se excluye, para que el cliente no se bloquee a sí mismo al volver o recargar. Requiere agregar un parámetro `excluir_pk` a `obtener_contexto_rango`, `disponibilidad_por_fecha` y `proxima_fecha_disponible`, que hoy no lo tienen, y que el frontend (`getCupo`, `getCupoRango`) envíe la cabecera solo cuando existe un `checkout_id` (el calendario del inicio y la barra de reserva corren antes de que exista).
- Consecuencia asumida: `Reserva.clean()` del alta manual del admin, el aviso de disponibilidad del generador de enlaces y cualquier otro llamador de `evaluar_cupo`/`validar_cupo_diario` ven los apartados vigentes. El mensaje de error actual no cambia; la Agenda y el panorama no los muestran.

### 4.3 Tomar el apartado (`CrearPagoView`, `backend/apps/payments/views.py`)

**Restricción de la estructura actual:** hoy `post()` ejecuta todo `_post` dentro de un solo `with scope.con_empresa(empresa)`, que abre `transaction.atomic()` alrededor de la petición completa (`tenancy/scope.py`: el `SET LOCAL` de RLS lo exige). Un `atomic()` anidado sería solo un savepoint y el candado `pg_advisory_xact_lock` seguiría tomado hasta el commit final, es decir, **durante las llamadas a Stripe**. Por eso `post()` se reestructura en tres bloques, cada uno con su propio `con_empresa` y su propio commit:

- **Bloque A (lectura y validaciones):** las validaciones tempranas que ya existen (checkout_id → 403, reserva ya no pendiente → 409, sin llaves/precio → 503, datos inválidos → 400) y la **lectura del PaymentIntent ya guardado** (`_recuperar_intent`), que se usa **solo** para la salida temprana de abajo; el Bloque C vuelve a consultar el intent (hoy lo hace `_intent_de`) para decidir sobre datos frescos. Si ese intent está `processing` o `succeeded` (el cliente ya pagó y espera el aviso de Stripe), se responde `pago_en_curso` **sin ejecutar la Fase 1 ni tocar el apartado**.
- **Bloque B (Fase 1, transacción corta, solo si `APARTADO_MINUTOS > 0` y el servicio/paquete tiene cupo físico):**
  1. se bloquea la fila de la reserva (`select_for_update`) y se verifica de nuevo `estado == pendiente_pago` (mismo orden que el webhook: primero la fila, después los candados);
  2. se toman los candados del cupo en el mismo orden que `reservar_cupo_al_confirmar` (`bloquear_cupo` por fecha en orden cronológico; `bloquear_recurso` para hospedaje), con un `lock_timeout` corto (p. ej. 5 s), reintento ante deadlock (`40P01`) como ya hace el webhook y, si el candado no se obtiene a tiempo (`55P03`), una respuesta `503 {"detail": "...", "codigo": "reintentar"}` que el frontend muestra como «Intenta de nuevo en unos segundos» (no como un fallo de conexión);
  3. se calcula la demanda con las mismas funciones que usa la confirmación (`fechas_de_componente`, `personas_de`, y para hospedaje la misma selección de habitaciones que `_asignar_cupo_hospedaje`), excluyendo la propia reserva;
  4. si cabe: se escribe `apartado_hasta = ahora + APARTADO_MINUTOS` y `apartado_demanda` (incluidos en `save(update_fields=...)`) y se hace commit, liberando todos los candados **antes** de llamar a Stripe;
  5. si no cabe: se responde sin crear PaymentIntent (409 `sin_cupo`).
- **Bloque C (Fase 2, Stripe y escrituras finales):** la lógica existente de PaymentIntent (`_intent_de`, que consulta de nuevo el intent, congelado de extras, `idempotency_key`) en su propio `con_empresa`. Reglas de liberación:
  - Si Stripe falla (502/timeout) y **esta llamada creó** el apartado (antes no había uno vigente), se libera con una escritura condicional (`UPDATE ... WHERE apartado_hasta = <valor que escribió esta llamada>`), de modo que no borre el apartado que otra llamada concurrente (doble clic, otra pestaña) haya renovado entretanto.
  - Si esta llamada **solo renovó** un apartado que ya existía, no se libera ni se restaura nada: el apartado sigue vigente o vence solo. Un 502 pasajero más un reintento no debe costarle el lugar al cliente.
  - Si `PagoEnCurso` se lanza en este bloque (el cliente empezó a pagar entre el Bloque A y el C, p. ej. desde otra pestaña), el apartado **no se toca**. Lo mismo si Stripe rechaza un `update`/`create` porque el intent pasó a `processing` o `succeeded` en ese instante: ese error se trata como `PagoEnCurso` (responde `pago_en_curso`), nunca como un 502 con liberación.
  - Si la liberación falla, el apartado vence solo.

La respuesta exitosa incluye `apartado_hasta` (ISO 8601) o `null` si no hubo apartado.

**Repetición del paso** (volver atrás, cambiar fecha/personas/extras, doble clic, varias pestañas): el apartado pertenece a la reserva; cada `crear-pago` reemplaza el retrato por el recalculado y renueva el vencimiento por un `APARTADO_MINUTOS` completo. Nunca hay dos. **No hay tope de edad ni de renovaciones en v1** (decisión deliberada: un tope necesita estado propio que sobreviva a las ediciones y a los vencimientos, y es una defensa que nadie ha pedido). Riesgo aceptado y acotado: una sola reserva podría renovarse cada pocos minutos para mantener un día apartado; lo limitan el captcha por reserva, el throttle `pagos` por IP y la corta duración del apartado. Se vigila al activarlo y se agrega un tope solo si hace falta.

**Editar la reserva sin pasar por `crear-pago`:** `ReservaCheckoutView` es un upsert por `checkout_id` y `enviar()` llama siempre a `guardarReserva` antes de `crearPago`. El upsert **borra** `apartado_hasta` y `apartado_demanda` cuando cambia cualquier campo relevante para el cupo (fecha, hora, personas, servicio, paquete, fecha_salida, personas_por_servicio). El retrato además hace que, aunque no se borrara, el apartado siguiera describiendo lo que de verdad se validó y no un viaje distinto.

**Contrato de errores de `crear-pago`.** Cuerpo **plano** (hoy toda respuesta de error es `{"detail": "<texto>"}` y el frontend lee ese cuerpo completo como `ApiError.detail`); los casos nuevos añaden campos al mismo objeto, y `detail` sigue siendo un texto legible:

| Caso | Estado | Cuerpo |
|---|---|---|
| Ya no hay lugar | 409 | `{"detail": "...", "codigo": "sin_cupo", "motivo": "lleno" \| "sin_panga" \| "sin_lugar", "proxima_disponible": "AAAA-MM-DD" \| null}` |
| Reserva ya no pendiente | 409 | `{"detail": "...", "codigo": "ya_no_pendiente"}` |
| Cobro en curso | 409 | `{"detail": "...", "codigo": "pago_en_curso"}` |
| Checkout inválido | 403 | `{"detail": "...", "codigo": "checkout_invalido"}` |
| Candado no obtenido a tiempo | 503 | `{"detail": "...", "codigo": "reintentar"}` |
| Sin llaves / sin precio | 503 | sin cambio (`{"detail": "..."}`) |
| Datos inválidos | 400 | sin cambio |

`proxima_disponible` solo se calcula para **servicios sueltos con cupo por embarcación/día** (`proxima_fecha_disponible` revisa un solo día para N personas); es `null` para hospedaje y para **todos los paquetes**, porque ofrecer un día suelto llevaría al cliente a un itinerario que nunca se validó. El frontend decide por `codigo`; **si falta `codigo`** (backend viejo, o los 400/503 sin cambio) se conserva el comportamiento actual por estado HTTP.

### 4.4 Webhook (`payments/services.py`, `bookings/cupo/confirmacion.py`)

Sin cambio de fondo. `reservar_cupo_al_confirmar` y `Reserva.clean()` cuentan excluyendo a la propia reserva y no leen el retrato propio:

- apartado vigente: se confirma;
- apartado vencido y el lugar sigue libre: se confirma;
- apartado vencido y otro tomó el lugar: reembolso del 100% como hoy (`_cancelar_sin_cupo`). **Consecuencia intencional:** el apartado vigente (aunque aún no esté pagado) de otro cliente cuenta contra quien paga tarde; un cliente cuyo apartado ya venció y que paga después puede ser reembolsado porque alguien más tiene el lugar apartado. Es el propósito del apartado: proteger a quien lo tiene vigente.

En hospedaje, `_asignar_cupo_hospedaje` elige las habitaciones libres al confirmar (normalmente las mismas que se apartaron, por ser la misma selección determinista). Al pasar a `pagada` o `cancelada` se limpian `apartado_hasta` y `apartado_demanda`. `conciliar_pagos` aplica las mismas reglas porque llama al mismo servicio. Cambiar `APARTADO_MINUTOS` a `0` desactiva de inmediato el efecto de cualquier apartado existente (el motor lo ignora).

### 4.5 Avisos de reembolso por falta de cupo (`backend/apps/notifications/services.py`)

`_cancelar_sin_cupo` hoy recibe también fallas que no son de cupo (deslinde, regla de 48 h, ventana horaria, otras validaciones de `full_clean`) y **no puede distinguirlas**: `_aplicar_pago_exitoso_transaccional` la llama desde `except DjangoValidationError` sin motivo (`services.py:127-135`) y desde `except SinCupoError` con `motivo=str(exc)` (`:136-140`), y los errores de cupo del modelo son `ValidationError({'fecha': ...})` que comparten clave con otras fallas (`bookings/models.py:229, 253`, `cupo/salidas.py:34`). Mecanismo:

- **Regla:** todo `raise` de falla de cupo lleva `code='sin_cupo'`. **Trampa de Django:** cuando el mensaje es un diccionario, `ValidationError({'fecha': msg}, code='sin_cupo')` **ignora `code=` sin avisar**; en la forma de diccionario el código va en el error interior: `ValidationError({'fecha': ValidationError(msg, code='sin_cupo')})`. Los `raise` de texto simple (los de `estrategias.py`) pueden usar `code=` directamente. Los sitios: en `bookings/cupo/estrategias.py` todas las ramas de `validar` (incluidos los mensajes «No hay cupo disponible…», «No queda panga…», «No hay espacio…»), en `bookings/models.py` `_validar_cupo_hospedaje` y las dos ramas de `_validar_cupo_de_paquete` (incluida «No hay disponibilidad de hospedaje para el servicio…») y en `cupo/salidas.py`. Es el camino de un día de pesca lleno: `Reserva.clean()` → `validar_cupo_diario` → `estrategia.validar`. `SinCupoError` ya es específico.
- `_cancelar_sin_cupo` recibe un argumento explícito `causa`: `"cupo"` si la excepción es `SinCupoError` o una `ValidationError` cuyos códigos incluyen `sin_cupo`. El clasificador **recorre los códigos anidados** (`error_dict` y `error_list`), porque `full_clean` envuelve un error de `clean()` que no es un diccionario bajo `__all__` y el código sobrevive ahí; `"otra"` en cualquier otro caso (con el texto de la excepción como motivo).
- causa = `cupo`: correo al cliente y alerta interna.
- causa = `otra`: solo alerta interna con la causa real; **nunca** el correo «sin cupo».
- **Fallo del reembolso** (`FALLO_REEMBOLSO`: la reserva sigue `pendiente_pago` con el dinero cobrado): alerta interna **urgente** a `Empresa.correos_aviso` con el folio, el monto y el motivo, para que una persona resuelva el reembolso a mano. Es el caso de más riesgo para el cliente y hoy no avisa a nadie. Como la reserva no se cancela, cada reintento de Stripe y cada corrida horaria de `conciliar_pagos` volvería a entrar: se deduplica **una alerta por reserva** con un campo nuevo `alerta_reembolso_fallido_en` (fecha/hora, nullable, en la misma migración que los campos del apartado) que se sella con `Reserva.objects.filter(pk=..., alerta_reembolso_fallido_en__isnull=True).update(alerta_reembolso_fallido_en=ahora)` (nunca con `reserva.save()`: en ese punto el objeto en memoria ya tiene `estado=PAGADA` sin persistir, y `save()` propagaría `ocupa_cupo` y ejecutaría `_derivar_estado_de_asignacion`); el número de filas actualizadas es la prueba de «primera vez» (atómica ante reintentos concurrentes) y la alerta se envía con `on_commit` solo si el `update` afectó una fila.

Los avisos se disparan con `transaction.on_commit`, solo cuando esa llamada hizo la cancelación (un reintento de Stripe no duplica) o, en el caso del fallo de reembolso, cuando `alerta_reembolso_fallido_en` aún está vacío, y con `try/except` que registra y nunca lanza (el webhook debe responder 200).

- Correo al cliente (Resend), en español (la reserva no guarda idioma; decidido para v1): «No pudimos asegurar tu lugar para el {fecha}. Ya solicitamos el reembolso completo de {monto}; tu banco puede tardar en reflejarlo», con un botón «Elegir otra fecha» (enlace del sitio con el viaje precargado, igual que el generador de enlaces).
- Alerta interna a `Empresa.correos_aviso`: «ALERTA: reserva #{folio} · {causa} · reembolsada automáticamente · {nombre} · {teléfono}».
- WhatsApp al cliente: código listo pero apagado; se activa cuando exista `WHATSAPP_TEMPLATE_REEMBOLSO_SIN_CUPO` (plantilla aprobada por Meta con parámetros nombre, fecha, monto, moneda). Tarea manual del dueño.

### 4.6 Frontend

Tres flujos llaman a `crearPago` y cada uno necesita su propio tratamiento:

| Flujo | Archivos | Qué necesita |
|---|---|---|
| Servicio suelto | `components/checkout-view.tsx`, `stripe-panel.tsx` | puntos 1 a 5 y 7 de abajo |
| Paquete de una empresa | `components/pedido/pedido-paquete.tsx`, `use-pago-pedido.ts` | hoy `ejecutarEnvio` manda cualquier error de `crearPago` por `mensajeDeError` a `setFase('formulario')`. Añadir la rama `sin_cupo`: vuelve a `formulario` con el aviso «El cupo de tu itinerario se agotó; elige otra fecha de inicio» (sin `proxima_disponible`, que es `null` para paquetes) y los datos del pedido en memoria. Ya existen la fase `confirmando` con `getEstadoReserva` cada 5 s, el estado de falla `cancelada` y `reiniciar` / `soltarIntentoAnterior` (genera `checkout_id` nuevo): se reutilizan, ajustando el intervalo a 2 s y el texto. **También necesita la línea fija y la renovación** (`pedido-paquete.tsx` renderiza `StripePanel` en dos sitios): `use-pago-pedido.ts` es dueño de `crearPago`, `forma_pago` y el código promocional, así que implementa `antesDePagar` y la confirmación de monto distinto, y los pasa a `StripePanel` |
| Traslado | `components/traslado-view.tsx` | el servicio es `bajo_demanda` y no aparta, así que no recibe `sin_cupo`; solo se verifica que el nuevo mapeo por `codigo` no cambie su comportamiento |

Cambio común: `lib/errores.ts` hoy mapea cualquier 409 a «cobro en curso» y `clasificar()` llama `sin_cupo` a cualquier 409; ambos pasan a decidir por `codigo` (con respaldo al comportamiento actual si falta). Esto incluye el **503 `reintentar`**: hoy `errores.ts` manda todo 503 a `checkout.paymentUnavailable` («pagos no disponibles»), que sería un mensaje falso para un candado ocupado. Con `codigo = reintentar` se muestra la clave nueva «Intenta de nuevo en unos segundos»; durante una renovación el cliente **se queda en el formulario de pago** y no se bloquea ningún cobro.

1. **Sin lugar al dar «listo»** (servicio suelto): el cliente vuelve al paso del viaje (`setPhase('form')`, reabrir `viaje`) con **el formulario conservado en memoria** (no depende de `getEstadoReserva`), ve el aviso existente (`checkout.dayFullOffer` o `checkout.noBoatForGroupNotice`) más la clave nueva «El cupo se agotó mientras llenabas tus datos. Tus datos siguen guardados.», y el botón `checkout.takeOffered` si llegó `proxima_disponible`. Como la reserva sigue pendiente, al reenviar se reutiliza por `checkout_id`.
2. **Línea fija** sobre el formulario de la tarjeta (`stripe-panel.tsx`): «Tu lugar está apartado por 15 minutos», **solo si `crear-pago` devolvió `apartado_hasta`** (no aparece con `APARTADO_MINUTOS=0`, servicios sin cupo físico ni órdenes). Sin reloj.
3. **Renovación silenciosa**: la hace el **componente que conoce la reserva** (`checkout-view.tsx` en servicio suelto, `use-pago-pedido.ts` en paquetes), no `StripePanel`, que hoy solo recibe `client_secret` y `publishable_key`. `StripePanel` recibe un callback `antesDePagar()` que se invoca **en cada clic de «Pagar»** (sin comparar relojes: el reloj del navegador puede estar desfasado por minutos y un reloj atrasado se saltaría la renovación; la renovación es idempotente y barata). `antesDePagar` vuelve a llamar a `crear-pago` **reenviando idénticos `forma_pago` y `codigo_promocional`** (si no, el servidor tomaría `completo` y sin código y modificaría el monto del PaymentIntent). Si el monto devuelto difiere del que el cliente vio, **no se cobra**: se muestra el monto nuevo y se pide confirmar. Si hay lugar, se renueva y se continúa con `stripe.confirmPayment()`; si no, vuelve al inicio con el aviso del punto 1. Si la respuesta es `pago_en_curso` o `ya_no_pendiente` (doble clic tras empezar a pagar, otra pestaña, o el webhook acaba de marcar la reserva pagada), **no se llama a `confirmPayment`**: se pasa directo al polling de «Estamos confirmando tu lugar…» del punto 4.
4. **Pantalla posterior honesta**: al terminar `stripe.confirmPayment()` la fase pasa a «Estamos confirmando tu lugar…» y se consulta `getEstadoReserva(checkoutId)` cada 2 s hasta ~12 s (patrón ya usado en `use-pago-pedido.ts`). `pagada` → confirmación como hoy; `cancelada` → «No fue posible asegurar tu lugar. Tu pago se reembolsa al 100%.» con botón «Elegir otra fecha»; sin respuesta a tiempo → «Estamos confirmando tu pago. Si en unos minutos no recibes un correo, escríbenos» (no se promete un correo: si el reembolso automático falla, la reserva sigue `pendiente_pago` y ese caso solo genera una alerta interna, ver 4.5).
5. **Volver tras una cancelación**: una reserva `cancelada` ya no la reutiliza el upsert (`_pendiente_de` filtra `pendiente_pago`), así que «Elegir otra fecha» **genera un `checkout_id` nuevo**, rellena el formulario con el estado que el navegador conserva en memoria y **reinicia el widget de Turnstile** (el token es de un solo uso y se exige al crear una reserva nueva).
6. Claves de diccionario nuevas (es y en): línea del apartado, aviso de cupo agotado, «Intenta de nuevo en unos segundos», titular y cuerpo de «lugar no asegurado / reembolso», estado «confirmando», «seguimos confirmando».
7. **Tarea independiente (no depende del apartado): fecha inválida en el enlace.** Cuando `parseBookingQuery` descarta la fecha (pasada, mal formada) y el sitio usa «mañana», se muestra una vez el aviso «Actualizamos la fecha de tu viaje al {fecha}» (clave existente `feedback.dateChanged`) en el checkout de servicio suelto.

## 5. Pruebas

SQLite (suite normal):

- Motor: un apartado vigente cuenta, uno vencido se ignora, `APARTADO_MINUTOS=0` los ignora todos, la reserva evaluada se excluye a sí misma; `/api/cupo/`, el rango y `proxima_fecha_disponible` cuentan los apartados y aceptan `checkout_id` para excluir el propio.
- Retrato: servicio suelto, paquete con salidas multidía (sin doble conteo con `ReservaSalida`/`Reserva.fecha`), paquete sin componentes de mar (no cuenta), hospedaje (la habitación apartada aparece ocupada en su rango y solo para su servicio), `bajo_demanda` no aparta.
- `crear-pago`: `409 sin_cupo` con `motivo` y `proxima_disponible` (nulo en hospedaje); los otros 409 con su `codigo`; renovación al repetir; liberación del apartado si Stripe falla o hay cobro en curso; `APARTADO_MINUTOS=0` conserva el comportamiento actual.
- Edición: cambiar fecha, personas, servicio, paquete o fecha_salida por `POST /reservas/` borra el apartado; `apartado_hasta` no es escribible desde la API pública.
- Webhook: se confirma con apartado vigente, se confirma si venció pero sigue libre, reembolsa si venció y otro tomó el lugar; se limpian los dos campos al pagar y al cancelar.
- Avisos: el correo solo sale por causa de cupo y una vez; se clasifican `cupo` y mandan el correo un día de pesca lleno (`Reserva.clean()`, texto simple), un hospedaje lleno y un paquete lleno (forma de diccionario) y el error de `cupo/salidas.py` (que llega por `Reserva.save()`, no por `full_clean`, y lo atrapa el mismo `except DjangoValidationError`); una falla de `full_clean` que no es de cupo (p. ej. regla de 48 h) produce la alerta interna pero no el correo al cliente; el fallo de reembolso alerta una sola vez aunque el webhook se reintente y `conciliar_pagos` corra varias veces; la alerta interna sale por cualquier causa; nada tumba el webhook; WhatsApp apagado por defecto.

Postgres (Docker; sin él no se prueba lo importante; SQLite no muestra los candados porque son no-op): pruebas de concurrencia en el estilo de `tests_concurrencia.py` (`threading.Barrier`, `TransactionTestCase`, `@SOLO_POSTGRES`): (a) dos `crear-pago` simultáneos por el último lugar de pesca: exactamente uno 200 y el otro 409; (b) dos por la última habitación; (c) un paquete con mar y hospedaje donde un solo lugar basta para fallar: no queda ningún apartado a medias; (d) el candado se libera antes de la llamada a Stripe; (e) un `crear-pago` repetido mientras el PaymentIntent está `processing` o `succeeded` no toca el apartado; (f) una renovación concurrente con el webhook de la misma reserva no produce deadlock; (g) una liberación tras un fallo de Stripe no borra el apartado renovado por otra llamada concurrente (escritura condicional); (h) un candado no obtenido a tiempo responde `503 reintentar`; (i) si el intent pasa a `processing`/`succeeded` entre el Bloque A y el C, la respuesta es `pago_en_curso` y el apartado no se libera. Se corren con `config.settings.ci` y el rol sin `BYPASSRLS` (ver `backend/CLAUDE.md`). Son condición para dar el trabajo por terminado.

Frontend: `tsc`, `eslint` y `build` (el proyecto casi no tiene pruebas automáticas); el dueño revisa el sitio.

## 6. Despliegue

Orden: migración; backend con `APARTADO_MINUTOS=0`; frontend que ya decide por `detail.codigo`; al final, `APARTADO_MINUTOS=15`. Con la función apagada el sistema se comporta como hoy, y un sitio viejo nunca ve el nuevo `409 sin_cupo`. Reservas existentes: los dos campos nuevos son nulos, así que no hay apartados vigentes. Actualizar `backend/CLAUDE.md` (secciones «Cupo diario» y «Garantias del cobro») con la regla del apartado, el retrato y el contrato de errores.

## 7. Riesgos y vigilancia

- Hospedaje: la selección de habitaciones al apartar debe ser la misma función y el mismo orden que usa la confirmación; si divergen, el cliente podría perder el lugar apartado (se cubre con pruebas de ambos lados y el reembolso de siempre como red de seguridad).
- Consultas de cupo con retratos vigentes: una consulta agrupada por empresa y rango; medir y, si hace falta, indexar `apartado_hasta`.
- Relojes y husos: `apartado_hasta` con zona horaria; comparar siempre con `timezone.now()`.
- Un mismo cliente con varias reservas para el mismo día cuenta varias veces (aceptado). Sin tope de renovación (ver 4.3): riesgo aceptado y vigilado.
- El personal puede quedar bloqueado en el alta manual por un apartado que la Agenda no muestra; se libera solo en minutos (limitación documentada).
- `Reserva.save()` y `clean()` no deben tratar un apartado vigente como ocupante: no se toca `ESTADOS_QUE_OCUPAN_CUPO`.

## 8. Pendientes fuera de este trabajo

- Plantilla de WhatsApp aprobada por Meta para el reembolso (tarea manual del dueño).
- Apartado para paquetes que cruzan empresas.
- Contador visible, si algún día hay datos que lo justifiquen.
- Idioma del cliente en la reserva (hoy los correos son solo en español).
- Mostrar apartados vigentes en la Agenda/panorama.

## 9. Plan de ejecución (delegado a agy, tareas de menos de 25 min; revisión, pruebas y commits por Claude)

1. Migración única con los tres campos (`apartado_hasta`, `apartado_demanda`, `alerta_reembolso_fallido_en`), ajuste `APARTADO_MINUTOS` y conteo de retratos en el motor para servicio suelto de cupo por embarcación/día.
2. Endpoints públicos con la cabecera `X-Checkout-Id`: parámetro `excluir_pk` en `obtener_contexto_rango`, `disponibilidad_por_fecha` y `proxima_fecha_disponible`, cabecera permitida en CORS, y `getCupo`/`getCupoRango` del frontend.
3. Funciones que construyen el retrato de paquetes (salidas multidía y componentes de una salida) y su integración con el motor; prueba con un paquete que mezcle componentes de una sola salida y de varias salidas (sin hospedaje: el paquete con mar y hospedaje se prueba en las tareas 4 y 11).
4. Hospedaje: **primero extraer** de `_asignar_cupo_hospedaje` (`bookings/cupo/confirmacion.py`) una función pura `elegir_habitaciones(...)` (hoy la selección está mezclada con la toma de candados y la creación de `ReservaOcupacion`), que la confirmación y el apartado llamen por igual, con un orden determinista de `servicio.recursos` (por `pk`; hoy no está ordenado); después, el apartado de habitaciones e integración con `obtener_recursos_con_ocupaciones`. La prueba debe comprobar que apartar y confirmar eligen las mismas habitaciones.
5. `crear-pago`: reestructurar `post()` en los bloques A/B/C con commits separados, orden de candados (fila de la reserva primero), `lock_timeout` y reintento de deadlock (sin tope de edad en v1), liberación solo de lo que esa llamada creó con escritura condicional, contrato de errores con cuerpo plano y `codigo`, borrado del apartado al editar la reserva.
6. Webhook: limpieza de campos, gating con `APARTADO_MINUTOS`, pruebas de casos límite.
7. Avisos con causa: `code='sin_cupo'` en los errores de cupo del modelo y de las salidas, argumento `causa` en `_cancelar_sin_cupo`, correo (solo causa cupo), alerta interna (cualquier causa), alerta urgente deduplicada por `alerta_reembolso_fallido_en` para `FALLO_REEMBOLSO`, WhatsApp apagado.
8. Frontend servicio suelto: decisión por `codigo`, regreso al viaje, línea fija, renovación por el padre con `forma_pago`/código promocional, pantalla honesta, reinicio de Turnstile y `checkout_id` nuevo tras cancelar, diccionarios.
9. Frontend paquete de una empresa (`pedido-paquete.tsx`, `use-pago-pedido.ts`) y verificación de `traslado-view.tsx`.
10. Frontend independiente: aviso de fecha cambiada en el enlace.
11. Pruebas de concurrencia en Postgres (requiere Docker): último lugar de pesca, última habitación, paquete con mar y hospedaje sin apartados a medias, **y una que demuestre que el candado ya no está tomado mientras se llama a Stripe** (la llamada a Stripe simulada se bloquea y una segunda petición toma el candado sin esperar); más la actualización de `backend/CLAUDE.md`.

---
Status: APPROVED
Critic verdict: Round 8 (after seven adversarial rounds that found and closed, among others, the lock held across Stripe calls, the release of a paying customer's hold, the incoherent hold-age cap (removed), the missing hospedaje design, and the Django `code=` dict-form trap) found the spec consistent end to end, with no contradictions or missing failure handling that would make an implementer build the wrong thing. Pending: owner's review of the written spec.
