Decision: BLOCKED

# CSO — Notificaciones persistentes del backoffice (+ pago por transferencia)

- Fecha: 2026-10-26
- Alcance: cambios sin commitear sobre HEAD 22026a87 en `.claude/worktrees/agent-a2bd2eef7c5a54777/backend` (notificaciones, avisos de reservas nuevas, `transferencia.py`, `pagar_transferencia_view`, cron de retención).
- Tier de seguridad: standard (el proyecto mueve dinero con Stripe y datos de clientes; el cambio toca un flujo de dinero).
- verdict_quality: substantive (cada hallazgo Alto/Medio lleva archivo:línea y una ejecución propia; lo no ejecutado se declara).
- gate:ship: BLOQUEADO. No se tocó Beads ni `.great_cto/verdicts` (el encargo pidió escribir solo este informe).

## Veredicto en una frase

BLOCKED: `marcar_pagada_por_transferencia` deja vivo el PaymentIntent del checkout y el webhook trata un cobro posterior con tarjeta como "evento repetido", así que el cliente paga dos veces sin reembolso ni registro (H-1, Alto, reproducido). La funcionalidad de notificaciones por sí sola no tiene hallazgos Crítico/Alto y quedaría APPROVED con los Medios abiertos.

## Resumen por severidad

| Id | Severidad | Origen | Título |
|---|---|---|---|
| H-1 | Alto | Preexistente sin publicar (`transferencia.py`) | Cobro con tarjeta posterior a una transferencia se ignora: doble cobro silencioso |
| M-1 | Medio | Preexistente sin publicar (`transferencia.py`) | Con `precio_total` nulo la transferencia no tiene tope de monto |
| M-2 | Medio | Introducido (ampliado) por este cambio | El sondeo de 10 s en todo el admin mantiene viva la sesión deslizante |
| B-1 | Bajo | Introducido | `enlace_seguro` acepta `/\host` y `/<tab>/host` |
| B-2 | Bajo | Preexistente (movido a `avisos.py`) | `?desde=` con fecha imposible produce 500 |
| B-3 | Bajo | Introducido | La garantía "nunca rompe la acción" no cubre armar los argumentos |
| B-4 | Bajo | Introducido | Correo del cliente dentro del texto de la notificación, retenido 90 días |
| B-5 | Bajo | Introducido | El cron recibe el grupo completo de secretos |

Verificado sin hallazgo (aislamiento RLS, IDOR, CSRF, XSS, permisos, retención, dinero en procesos con `avisar()`): ver sección final.

## Método y límites

- Lectura completa de: `tenancy/notificaciones.py`, `tenancy/models.py` (diff), `tenancy/admin.py` (diff), `migrations/0010` y `0011`, `limpiar_notificaciones.py`, `avisos.js`, `marcar_todas_notificaciones.html`, `bookings/avisos.py`, `bookings/transferencia.py`, `pagar_transferencia.html`, diffs de `bookings/admin.py`, `bookings/signals.py`, `payments/services.py`, `notifications/services.py`, `config/urls.py`, `config/settings/base.py`, `render.yaml`, `setup_roles.py`.
- Ejecuté tres sondas propias en SQLite (`manage.py test` sobre módulos acotados de la carpeta scratchpad; no editan el repo) y `makemigrations --check` (sin cambios pendientes).
- NO re-ejecuté la suite de Postgres: el RLS lo evalué por lectura de `0011` y de `tests_notificaciones_rls.py`, y me apoyo en el resultado que informó el encargo (354 tests OK en Postgres). No abrí navegador: lo que afirmo de `avisos.js` sale de leer el código.
- Cumplimiento (`compliance:`): fuera del alcance de este encargo; no se evaluó ninguna lista.

---

## Hallazgos

### [Alto] H-1 Un cobro con tarjeta posterior a "pagada por transferencia" se ignora como evento repetido

- **Origen**: preexistente sin publicar (`transferencia.py` y la vista `pagar_transferencia_view`); se entrega junto con este cambio.
- **Location**: `backend/apps/bookings/transferencia.py:54-100` (no toca el PaymentIntent) y `backend/apps/payments/services.py:212-214` (`_resolver_cobro_repetido`). El intent queda guardado en la reserva en `backend/apps/payments/views.py:518`.
- **Problem**: el checkout abandonado que la vendedora salda por transferencia ya tiene `stripe_payment_intent_id` (lo escribe `crear-pago`, `views.py:518`; es justo lo que define un checkout "abandonado"). `marcar_pagada_por_transferencia` pasa la reserva a `pagada`, pero deja el PaymentIntent abierto en Stripe (`requires_payment_method`/`requires_action`). Si el cliente completa después la tarjeta en la pestaña que sigue abierta (el escenario que motiva la función: "tuvo problemas con la tarjeta"), llega `payment_intent.succeeded` con el MISMO id que la reserva guarda. `_resolver_cobro_repetido` compara solo ids (`services.py:212`), responde `YA_APLICADO` y no reembolsa ni registra nada. El rechazo de `crear-pago` con 409 no protege: la confirmación de un `client_secret` ya entregado no pasa por nuestro servidor. `conciliar_pagos` tampoco lo recoge (solo mira `pendiente_pago`).
- **Evidence**: failed
  ```
  $ PYTHONPATH=<scratchpad>:. manage.py test probe_h1   # transferencia de 1000 MXN, luego payment_intent.succeeded del intent guardado por 100000 centavos
  H1 resultado=ya_aplicado reembolsar_llamado=False monto_pagado=None monto_transferencia=1000.00
  $ grep -n -i "paymentintent\|payment_intent\|stripe" apps/bookings/transferencia.py
  7:Hace lo mismo que el webhook de Stripe al confirmar un pago (`payments.services.aplicar_pago_exitoso`):
  35:    captura manual en cada cuenta de Stripe y no se pueden saldar a mano de una en una."""
  $ grep -n "stripe_payment_intent_id == intent" apps/payments/services.py
  212:    if reserva.stripe_payment_intent_id == intent['id']:
  ```
  Sonda: `C:\Users\kkjf\AppData\Local\Temp\claude\C--Users-kkjf-desarrollo-sistema-pescadeportiva\725de5d4-633b-42ea-8ec7-b446e0847fdb\scratchpad\probe_h1.py`. Las líneas 7 y 35 de `transferencia.py` son docstrings: el módulo no llama a Stripe. `tests_transferencia.py` no menciona intent ni Stripe, así que ninguna prueba cubre este camino.
- **Why it matters**: sin atacante. Un cliente cobrado dos veces (tarjeta + transferencia) cuyo cargo no aparece en el sistema (`monto_pagado` vacío, sin `MovimientoDinero` de tarjeta, sin aviso, sin alerta) y sin reembolso automático. Se descubre solo por queja o por conciliar Stripe a mano. Clasificación: OWASP A04:2021 Insecure Design, CWE-841 (flujo de negocio mal forzado); consecuencia económica directa.
- **Recommended fix** (dos capas; la 1 evita el cobro, la 2 lo devuelve solo si aun así ocurre):

  Parche 1 — `backend/apps/bookings/transferencia.py`: cerrar el intent abierto antes de anotar el dinero y negarse si ya hay un cobro en curso.

  ```python
  import stripe
  from apps.payments.stripe_client import configurar_stripe

  INTENT_COBRADO_O_EN_CURSO = {'succeeded', 'processing', 'requires_capture'}
  INTENT_ANULABLE = {'requires_payment_method', 'requires_confirmation', 'requires_action'}


  def _cerrar_cobro_con_tarjeta(reserva):
      """El checkout abandonado tiene un PaymentIntent vivo: si queda abierto y el cliente lo completa despues,
      cobra una segunda vez y el webhook lo toma por evento repetido. Falla cerrado: si no se puede anular, no se salda."""
      pi_id = reserva.stripe_payment_intent_id
      empresa = reserva.empresa
      if not pi_id or not empresa.stripe_secret_key:
          return
      cliente = configurar_stripe(empresa)
      try:
          intent = cliente.payment_intents.retrieve(pi_id)
          if intent.status in INTENT_COBRADO_O_EN_CURSO:
              raise ErrorDeTransferencia(
                  'El cliente ya pagó o está pagando con tarjeta esta reserva. No la marques por transferencia: '
                  'revisa el cobro en Stripe.')
          if intent.status in INTENT_ANULABLE:
              cliente.payment_intents.cancel(
                  intent.id, options={'idempotency_key': f'transferencia-{reserva.pk}-cancel'})
      except stripe.InvalidRequestError as exc:
          if getattr(exc, 'code', None) != 'resource_missing':
              raise ErrorDeTransferencia('No se pudo cerrar el cobro con tarjeta pendiente. Intenta de nuevo.') from exc
      except stripe.StripeError as exc:
          raise ErrorDeTransferencia('No se pudo cerrar el cobro con tarjeta pendiente. Intenta de nuevo.') from exc
  ```

  Llamarla dentro de `marcar_pagada_por_transferencia`, justo después del `if not puede_marcarse_pagada(reserva)` (línea 66-68) y antes de asignar `reserva.monto_transferencia` (línea 74). Si luego falla el cupo, el intent ya anulado obliga al cliente a retomar el checkout (`crear-pago` crea uno nuevo): es el costado seguro.

  Parche 2 — `backend/apps/payments/services.py:212`, defensa en profundidad (convierte el caso restante en reembolso automático):

  ```python
  # antes
  if reserva.stripe_payment_intent_id == intent['id']:
  # despues: solo es "evento repetido" si ese intent ya se aplico (dejo monto_pagado)
  if reserva.stripe_payment_intent_id == intent['id'] and reserva.monto_pagado:
  ```

  Pruebas a agregar: (a) `tests_transferencia.py`, intent en `requires_payment_method` se anula con la llave de idempotencia; en `succeeded`/`processing` se rechaza y no se guarda nada; error de Stripe distinto de `resource_missing` rechaza. (b) `payments/tests.py`, el caso de la sonda debe terminar en `DUPLICADO_REEMBOLSADO` y `reembolsar` llamado una vez. Antes de fusionar el parche 2, correr `manage.py test apps.payments` (acotado) porque cambia una rama del webhook.

### [Medio] M-1 Con `precio_total` nulo, la transferencia acepta cualquier monto

- **Origen**: preexistente sin publicar.
- **Location**: `backend/apps/bookings/transferencia.py:69`. `precio_total` solo se escribe en `crear-pago` (`backend/apps/payments/views.py:514`), así que una reserva `pendiente_pago` que no llegó a ese paso tiene `precio_total` nulo y aparece igual en la lista de abandonados (`bookings/admin.py:1873-1876` filtra solo por estado y antigüedad).
- **Problem**: el tope `monto > precio_total` se salta cuando `precio_total is None`. La reserva queda `pagada` con cualquier monto positivo que quepa en el campo.
- **Evidence**: failed
  ```
  $ PYTHONPATH=<scratchpad>:. manage.py test probe_m1   # pendiente(precio_total=None), monto 5000000.00
  M1 aceptado monto_transferencia=5000000.00 estado=pagada
  $ grep -n "precio_total is not None" apps/bookings/transferencia.py
  69:        if reserva.precio_total is not None and monto > reserva.precio_total:
  ```
- **Why it matters**: un error de tecleo (un cero de más) o una persona con permiso de cambiar reservas infla "Entradas por transferencia" y "En el banco" de Finanzas (`MovimientoDinero` lo lee) y aparta cupo de un viaje sin precio. Requiere cuenta con `bookings.change_reserva`; la huella queda (`transferencia_registrada_por`, `MovimientoDinero.registrado_por`, `log_change`), pero el dinero ya contó. OWASP A04:2021, CWE-20.
- **Recommended fix** (`transferencia.py`, antes de la línea 69):

  ```python
  if reserva.precio_total is None:
      raise ErrorDeTransferencia(
          'Esta reserva todavía no tiene precio calculado (el cliente no llegó a pagar). '
          'Fija el precio en la reserva antes de registrar la transferencia.')
  if monto > reserva.precio_total:
  ```
  Decisión de negocio que debe confirmar el dueño: si prefiere permitir el caso sin precio, exigir al menos un segundo paso de confirmación con el monto tecleado de nuevo.

### [Medio] M-2 El sondeo de 10 s en todo el admin impide que expire la sesión

- **Origen**: introducido (ampliado). Antes `bookings/reservas-nuevas.js` sondeaba cada 30 s solo en los listados de Reservas y Asignar pangas (`git show HEAD` del `Media` de `ReservaAdmin`); ahora `UNFOLD['SCRIPTS']` carga `avisos.js` en todas las páginas y sondea cada 10 s.
- **Location**: `backend/config/settings/base.py:185` (SCRIPTS), `base.py:562` y `base.py:566` (`SESSION_COOKIE_AGE` 10 h + `SESSION_SAVE_EVERY_REQUEST = True`), `backend/apps/tenancy/static/tenancy/avisos.js:17` (`INTERVALO_MS = 10000`) y `avisos.js:177-184` (solo se detiene con la pestaña oculta).
- **Problem**: el comentario de `base.py:559-561` justifica los 10 h como defensa ante "una laptop olvidada". Con `SAVE_EVERY_REQUEST` cada sondeo renueva la cookie y escribe `django_session`. Una pestaña del admin visible y sin atención (pantalla de mostrador, laptop con la tapa abierta) renueva la sesión de forma indefinida; el límite de 10 h de inactividad deja de existir en la práctica.
- **Evidence**: failed
  ```
  $ grep -n "SESSION_SAVE_EVERY_REQUEST\|SESSION_COOKIE_AGE\|'SCRIPTS'\|INTERVALO_MS =" config/settings/base.py apps/tenancy/static/tenancy/avisos.js
  config/settings/base.py:185:    'SCRIPTS': [lambda request: static('tenancy/avisos.js')],
  config/settings/base.py:562:SESSION_COOKIE_AGE = int(os.environ.get('SESSION_COOKIE_AGE', 60 * 60 * 10))
  config/settings/base.py:566:SESSION_SAVE_EVERY_REQUEST = True
  apps/tenancy/static/tenancy/avisos.js:17:  var INTERVALO_MS = 10000;
  ```
  No lo reproduje en navegador (instrucción de no abrir Chrome); la cadena causal sale de leer Django `SessionMiddleware` (guarda y refresca la cookie en cada respuesta con `SAVE_EVERY_REQUEST`) y el JS.
- **Why it matters**: la superficie de robo por sesión olvidada vuelve a ser ilimitada en el tiempo en un panel con dinero y datos de clientes. OWASP A07:2021, CWE-613 (expiración de sesión insuficiente). Costo adicional: una escritura a `django_session` por sondeo y por pestaña.
- **Recommended fix**: que el sondeo no renueve la sesión. Archivo nuevo `backend/apps/tenancy/middleware_sesion.py`:

  ```python
  from django.contrib.sessions.middleware import SessionMiddleware
  from django.utils.cache import patch_vary_headers

  RUTAS_DE_SONDEO = frozenset({'/admin/avisos/reservas-nuevas/'})


  class SesionSinRenovarEnSondeo(SessionMiddleware):
      """El sondeo de avisos corre solo, sin que la persona haga nada: no cuenta como actividad."""

      def process_response(self, request, response):
          if request.path_info in RUTAS_DE_SONDEO:
              patch_vary_headers(response, ('Cookie',))
              return response
          return super().process_response(request, response)
  ```
  y en `config/settings/base.py` reemplazar `'django.contrib.sessions.middleware.SessionMiddleware'` (MIDDLEWARE, línea ~436) por `'apps.tenancy.middleware_sesion.SesionSinRenovarEnSondeo'`. Prueba: dos GET al sondeo con `SESSION_SAVE_EVERY_REQUEST=True` no cambian `expire_date` de la fila de sesión; un GET a otra ruta sí. Con sesión vencida el sondeo recibe el login (HTML), `avisos.js:149-150` lo detecta y se detiene a los 3 intentos.

### [Bajo] B-1 `enlace_seguro` deja pasar `/\host` y `/<tab>/host`

- **Origen**: introducido.
- **Location**: `backend/apps/tenancy/notificaciones.py:41-47` y su gemela de `avisos.js:101-103` (`rutaPropia`); se pinta en `backend/apps/tenancy/admin.py:215`.
- **Problem**: la validación rechaza `javascript:`, `https://` y `//`, pero acepta una barra seguida de `\` o de tabulador/salto de línea. Los navegadores normalizan `\` a `/` y descartan tabulaciones y saltos al analizar la URL, así que `/\evil.com` y `/<tab>/evil.com` se resuelven como `//evil.com` (redirección abierta). El docstring afirma que un dominio ajeno "nunca debe llegar ahi".
- **Evidence**: failed
  ```
  $ PYTHONPATH=. python probe_enlace.py   # enlace_seguro(...)
  '/admin/x/' -> '/admin/x/'
  'https://evil.com' -> ''
  '//evil.com' -> ''
  'javascript:alert(1)' -> ''
  '/\\evil.com' -> '/\\evil.com'
  '/\t/evil.com' -> '/\t/evil.com'
  '/\n/evil.com' -> '/\n/evil.com'
  ```
- **Why it matters**: hoy no es alcanzable: las 12 llamadas a `avisar`/`registrar_notificacion` pasan `enlace_url` construido con `reverse(...)` y un entero (`grep -n "enlace_url=" apps` lo confirma). Es endurecimiento de una invariante declarada: el día que un llamador pase texto del cliente, la red se rompe en silencio. CWE-601.
- **Recommended fix** (`notificaciones.py:41-47`):

  ```python
  def enlace_seguro(url):
      url = str(url or '')
      if (len(url) > 300 or not url.startswith('/') or url.startswith('//')
              or '\\' in url or any(ord(c) <= 0x20 or ord(c) == 0x7f for c in url)):
          return ''
      return url
  ```
  y en `avisos.js` `rutaPropia`: añadir `&& !/[\\\u0000-\u0020\u007f]/.test(url)`.

### [Bajo] B-2 `?desde=` con fecha imposible produce 500 (preexistente, movido)

- **Origen**: preexistente. La misma línea estaba en `ReservaAdmin.reservas_nuevas_view` (`git show HEAD:backend/apps/bookings/admin.py`, línea 289) y se movió a `avisos.py`.
- **Location**: `backend/apps/bookings/avisos.py:48`.
- **Problem**: `parse_datetime` devuelve `None` solo si el formato no coincide; si el formato es válido pero el valor no, lanza `ValueError`, que el `if desde is None` no atrapa.
- **Evidence**: failed
  ```
  $ python probe_enlace.py   # parse_datetime('2026-13-45T00:00:00')
  parse_datetime raises ValueError month must be in 1..12, not 13
  $ grep -n "desde = parse_datetime" apps/bookings/avisos.py
  48:    desde = parse_datetime(desde_param)
  ```
- **Why it matters**: una persona autenticada con `view_reserva` puede provocar un 500 (ruido en Sentry) con un parámetro; el JS legítimo solo reenvía el valor que el servidor le dio. Sin fuga ni escalada.
- **Recommended fix**: `try: desde = parse_datetime(desde_param) except ValueError: desde = None` (la rama `None` ya responde 400).

### [Bajo] B-3 "Nunca rompe la acción" cubre el INSERT, no el armado de los argumentos

- **Origen**: introducido.
- **Location**: `backend/apps/payments/services.py:200-205` (`_notificar_reserva_nueva`, llamada en `:155`), `backend/apps/bookings/signals.py:92-110` (`_dejar_constancia`), `backend/apps/bookings/transferencia.py:111-125`.
- **Problem**: `registrar_notificacion` envuelve en `try` solo el `create` (`notificaciones.py:63-75`). Los f-strings y `reverse(...)` que arman sus argumentos se evalúan antes, fuera de ese `try`. `_notificar_reserva_nueva` corre en medio de `_aplicar_pago_exitoso_transaccional` (`services.py:155`), la transacción que marca la reserva pagada; una excepción al armar el texto (por ejemplo `reserva.paquete.nombre` con un paquete no visible bajo RLS) la propagaría y revertiría el pago aplicado. En los callbacks `on_commit` (`_dejar_constancia`, `_avisar_al_cliente`) una excepción sube desde el COMMIT de la petición.
- **Evidence**: failed
  ```
  $ grep -n "def _notificar_reserva_nueva" -A6 apps/payments/services.py
  200:def _notificar_reserva_nueva(reserva, empresa):
  201-    registrar_notificacion(
  202-        empresa, Notificacion.Nivel.EXITO,
  203-        f'Nueva reserva pagada: {reserva.nombre_cliente} · {_producto_de(reserva)} · {reserva.fecha:%d/%m/%Y}.',
  204-        tipo=Notificacion.Tipo.RESERVA_NUEVA, enlace_url=_enlace_a(reserva), enlace_texto='Ver reserva',
  205-    )
  ```
- **Why it matters**: hoy no hay camino que dispare la excepción: en una orden cruza-empresa la reserva de la empresa no líder se crea con `paquete=None` (`views.py:1150`) y la líder lee su propio paquete. Es una garantía que el código promete y no cumple en su totalidad, en la transacción que mueve el dinero.
- **Recommended fix**: envolver el cuerpo de `_notificar_reserva_nueva`, `_dejar_constancia` y `_avisar_al_cliente` (la parte del feed) en `try/except Exception: logger.exception(...)` sin incluir el texto en el log, o mover el armado de argumentos a una función `texto_seguro(lambda: ...)` dentro del `try` de `registrar_notificacion`.

### [Bajo] B-4 El correo del cliente queda en el texto de la notificación 90 días

- **Origen**: introducido.
- **Location**: `backend/apps/bookings/signals.py:100`.
- **Problem**: el texto de éxito de asignación incluye `reserva.correo_cliente`; el nombre ya identifica la reserva y el enlace "Ver reserva" lleva al dato vivo. La notificación no tiene FK a la reserva, así que borrar o anonimizar la reserva (derecho de supresión) no limpia esa copia hasta que el cron la purga a los 90 días.
- **Evidence**: failed
  ```
  $ grep -n "Correo enviado a" apps/bookings/signals.py
  100:            f'Panga y capitán asignados. Correo enviado a {reserva.correo_cliente} ({reserva.nombre_cliente}).',
  ```
- **Why it matters**: copia innecesaria de un dato personal, visible a todo el personal de la empresa con `view_notificacion`. Impacto bajo: ya ven la reserva.
- **Recommended fix**: `'Panga y capitán asignados. Correo enviado a {nombre}.'` (sin la dirección). Mismo criterio para cualquier texto futuro: nombre sí, correo y teléfono no.

### [Bajo] B-5 El cron de retención hereda todos los secretos

- **Origen**: introducido (convención ya existente en los demás servicios).
- **Location**: `render.yaml:143-150` (`- fromGroup: pescadeportiva-secrets`).
- **Problem**: `limpiar_notificaciones` solo necesita la base de datos y `DJANGO_SECRET_KEY`; el grupo trae además las llaves de Stripe, Resend, WhatsApp y la llave de cifrado de llaves. Un fallo del cron (o un volcado de entorno en un log de Render) expone más de lo necesario.
- **Evidence**: failed
  ```
  $ grep -n "fromGroup" ../render.yaml
  74:      - fromGroup: pescadeportiva-secrets
  95:      - fromGroup: pescadeportiva-secrets
  113:      - fromGroup: pescadeportiva-secrets
  131:      - fromGroup: pescadeportiva-secrets
  150:      - fromGroup: pescadeportiva-secrets
  ```
- **Why it matters**: privilegio mínimo; no hay secreto escrito en el archivo (verificado: el bloque nuevo solo trae `DJANGO_SETTINGS_MODULE`, `PYTHON_VERSION` y el grupo). Los otros cuatro servicios hacen lo mismo.
- **Recommended fix**: grupo de entorno separado (`pescadeportiva-db`) con solo las variables `DB_*` y `DJANGO_SECRET_KEY`, usado por los crons de limpieza. No bloquea.

---

## Observaciones (sin severidad: no hay mecanismo de explotación)

1. Las vendedoras ven en Notificaciones montos de reembolsos y de cobros en efectivo de toda la empresa, aunque Finanzas es solo de jefes y operador (`finance/views.py:153`, `puede_ver_finanzas`). No es escalada: el monto por reserva ya lo ve la vendedora en Reservas (columna Cobro); lo que no ve es el balance consolidado. Si el dueño quiere separar, hay que filtrar por `tipo` según rol en `NotificacionAdmin.get_queryset` (`tenancy/admin.py:179`).
2. La lista de Notificaciones no muestra la empresa; para el operador de plataforma (ve las cuatro) cuesta saber a cuál pertenece cada fila. Agregar `empresa` a `list_display` solo para el operador.
3. `Notificacion.empresa` y `LecturaNotificacion.empresa` son `PROTECT` (`0010_notificacion.py:28,41`): borrar una Empresa con historial queda bloqueado. Es el comportamiento correcto (se da de baja con `activo`), solo conviene saberlo.
4. El guardarraíl `test_guardarrail_toda_tabla_con_empresa_tiene_politica` no cubre `tenancy_*` (lo documenta `backend/CLAUDE.md`); la red real es `tests_notificaciones_rls.py:34`. Cualquier tabla nueva de `tenancy` con `empresa_id` necesita su propia prueba igual.

## Hypotheses (no verificadas; no son hallazgos)

- Costo del sondeo con tabla grande: `contar_no_leidas` (`notificaciones.py:121-129`) hace un `NOT EXISTS` por cada notificación de la empresa (hasta 90 días) cuando la persona ya leyó casi todo, porque el `LIMIT 100` solo corta cuando hay 100 sin leer. Para el operador (todas las empresas) la cuenta crece con las cuatro. No medí tiempos con volumen realista ni corrí `EXPLAIN`; con el volumen esperado (decenas de reservas por día) es improbable que importe. Si se mide más de unos 50 ms por sondeo, añadir una marca de agua por usuario además de las filas de lectura, o limitar el conteo a los últimos 30 días.

---

## Verificado sin hallazgo (con evidencia)

1. **RLS de las dos tablas.** `0011_rls_notificacion.py:12-21` aplica `ENABLE` + `FORCE ROW LEVEL SECURITY` y la política `tenancy_alcance FOR ALL USING (empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int OR current_setting('app.operador_plataforma', true) = 'on')` a `tenancy_notificacion` y `tenancy_lecturanotificacion`; es la política de `bookings/0065`. Sin cláusula `WITH CHECK`, Postgres usa el `USING` también para INSERT/UPDATE, así que no se puede escribir a nombre de otra empresa (`tests_notificaciones_rls.py:78`). `LecturaNotificacion.empresa_id` se copia de la notificación (`notificaciones.py:136`). `makemigrations --check`: sin cambios; el estado coincide con `0010`/`0011`. Dependencia de `0010` en `0009_llaves_stripe_cifradas` es la hoja anterior.
2. **IDOR en lista, detalle, historial y acciones.** Todo pasa por `NotificacionAdmin.get_queryset` (`tenancy/admin.py:179`) que arranca de `EmpresaScopedAdminMixin.get_queryset` (`admin_mixins.py:15-20`: operador ve todo; el resto `filter(empresa=empresa_actual)`, y con `empresa_actual` nula devuelve vacío). `marcar_como_leidas` (`admin.py:222`) opera sobre el `queryset` ya acotado, así que un id de otra empresa en el POST se descarta; `marcar_todas_view` (`admin.py:232-250`) parte del mismo `get_queryset`. Pruebas: `tests_notificaciones_admin.py:281, 291, 303, 313`. El sondeo (`bookings/avisos.py:54-59`) acota por `empresa_actual` y deja vacío al usuario sin empresa que no es operador. `contar_no_leidas` y `_del_alcance` (`notificaciones.py:108-129`) filtran por empresa, y `Exists(ya_leida)` usa `usuario=user`: la lectura es de la persona.
3. **Escritura desde señales/webhook/hilos.** `registrar_notificacion` escribe en línea dentro de un savepoint propio (`notificaciones.py:64`), por lo que un rechazo de RLS no aborta la transacción del llamador (`tests_notificaciones_rls.py:90`). Los callbacks `on_commit` reabren `scope.con_empresa(Empresa.objects.get(pk=...))` antes de escribir: `signals.py:_mandar`, `transferencia.py:105`. El webhook y `conciliar_pagos` ya corren dentro de `con_empresa` (`payments/views.py:877-889`; `conciliar_pagos.py:56, 171-172`). No hay `on_commit` dentro de `avisar`/`registrar_notificacion`. Un rollback deshace la notificación de éxito (comparten transacción). Todos los llamadores de `avisar` desde el admin pasan `empresa=` explícito, necesario para el operador (`bookings/admin.py:125, 303-312, 964, 1455`). La lista `threading.local` de `signals.py` se vacía al inicio de cada POST (`bookings/admin.py` `changelist_view`/`changeform_view`), por lo que un resultado de otra petición del mismo hilo no se muestra a otra persona.
4. **XSS / inyección.** `texto` y `motivo` salen por `format_html` con argumentos (`tenancy/admin.py:193-215`); no hay `mark_safe` ni `|safe` en los archivos nuevos (`grep` solo encuentra la palabra en un docstring). Los avisos de Django se pintan con `{{ message }}` autoescapado en las plantillas de Unfold (`unfold/helpers/messages/error.html`). `avisos.js` no usa `innerHTML`, `insertAdjacentHTML`, `outerHTML`, `document.write` ni `eval` (grep sin coincidencias); todo dato del servidor entra con `textContent` (`avisos.js:37, 59-60, 87, 129`); `notificaciones_url` pasa por `rutaPropia` (ver B-1 para el hueco menor). Prueba: `tests_notificaciones_admin.py:56, 67, 330, 340`.
5. **Permisos y CSRF.** `NotificacionAdmin` niega add/change/delete incluso al operador (`admin.py:170-177`); las acciones usan `permissions=['view']`. `LecturaNotificacion` no está en admin ni en roles (`tests_notificaciones_admin.py:205`). `marcar_todas` cambia estado solo por POST con `{% csrf_token %}` (`marcar_todas_notificaciones.html:16`) y la vista pasa por `admin_site.admin_view` (aplica `csrf_protect`); el GET solo confirma. Igual `pagar_transferencia_view`: `get_object` acotado por empresa, `has_change_permission`, `csrf_token` en `pagar_transferencia.html`, y la acción de fila `accion_fila_transferencia` revalida con `get_queryset`.
6. **Fuga de datos.** `Notificacion` no guarda tokens, códigos ni llaves; `_recortar` acota texto y motivo a 300 caracteres (`notificaciones.py:35-38`); el motivo de fallo del correo es el `message` del JSON de Resend o el cuerpo/`str(error)` recortado a 200 (`notifications/services.py:70-80`), sin cabeceras ni llave. `registrar_notificacion` no loguea el texto (`notificaciones.py:71-74`). El motivo de reembolso fallido es el texto de validación o "Sin cupo" (`services.py:333`), no la respuesta cruda de Stripe. Reservas con datos del cliente: ver B-4.
7. **Retención.** `limpiar_notificaciones` rechaza `--dias < 1` (`limpiar_notificaciones.py:28-30`), corre bajo `scope.como_operador_plataforma()` (`:32`; sin él RLS devuelve cero filas, hay prueba `tests_limpiar_notificaciones.py:44`), borra únicamente `creado_en__lt=corte` (`:33`), las lecturas caen por `CASCADE` y repetirlo no hace nada nuevo. El cron `15 9 * * *` (`render.yaml:133-150`) no lleva secretos escritos (ver B-5). Crecimiento acotado: los eventos repetidos de Stripe no duplican notificaciones (`aplicar_reembolso` sale antes si `devuelto <= monto_reembolsado`, `services.py:481`; el fallo de reembolso se sella una vez con el `UPDATE` de `:325-328`; un pago repetido sale antes en `:120-121`).
8. **Dinero en procesos con `avisar()`.** Las llamadas van después de la mutación y no la condicionan: cancelación por mal clima (`bookings/admin.py` tras el `with transaction.atomic()`), efectivo (después de `liquidar_saldo_en_efectivo`, que conserva su candado y su recálculo), cambio de fecha (`_avisar_cambio_de_fecha` tras guardar), reembolsos de Stripe (después de `reserva.save`). `avisar` no lanza (`notificaciones.py:89-105`) salvo por B-3. `pagar_transferencia_view` (aparte de H-1 y M-1): permiso de cambiar reservas, solo `pendiente_pago` sin orden (`transferencia.py:33-36`), monto decimal finito > 0 con dos decimales (`:44-51`), fila bloqueada con `select_for_update` y estado releído (`:63-68`) de modo que el doble clic no duplica (`tests_transferencia.py:78`), `MovimientoDinero` por `Reserva.save()`, `full_clean` y `reservar_cupo_al_confirmar` en la misma transacción, correo y notificación solo `on_commit`.
9. **Carga.** Un sondeo por pestaña visible cada 10 s; se detiene con la pestaña oculta y tras 3 fallos (`avisos.js:159-164, 177-184`). `contar_no_leidas` está acotado a 100 filas (`notificaciones.py:129`). Índices: `notif_empresa_creado`, `notif_empresa_tipo`, `lectura_unica_por_usuario` (`0010_notificacion.py:46-61`). Sin escrituras en el sondeo salvo la sesión (M-2). Tabla acotada por la retención de 90 días.

## Preexistente vs. introducido

- Preexistente (sin publicar, se entrega en este mismo árbol): H-1, M-1 (`transferencia.py` y su vista), B-2 (movido de `admin.py` a `avisos.py`).
- Introducido por las notificaciones: M-2 (ampliación del sondeo), B-1, B-3, B-4, B-5.

## Orden de arreglo sugerido

1. H-1 parches 1 y 2 con sus pruebas (desbloquea el veredicto).
2. M-1 (cinco líneas) y M-2 (middleware de 10 líneas); ambos Medios deberían cerrarse antes de publicar.
3. Los Bajos pueden salir después; B-1 y B-3 son endurecimiento de invariantes que el código ya declara.

VERDICT: BLOCKED reason="H-1: tras marcar pagada por transferencia, un cobro con tarjeta del mismo checkout se ignora como evento repetido (reproducido: resultado=ya_aplicado, sin reembolso)"
