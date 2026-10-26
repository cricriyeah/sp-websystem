Decision: APPROVED

# CSO 2 — Backoffice: Turnstile en login, avisos como tarjetas, sondeo con texto, transferencia (segunda pasada)

Fecha: 2026-10-26 · Base 22026a87 + 31391e04 + cambios sin commitear · Modo: solo lectura (sin suite, sin ejecutar código)
Primera auditoría: `docs/security/CSO-notificaciones-backoffice.md` (H-1, M-1, M-2, B-1, B-2, B-4 ya corregidos; no se repiten).
verdict_quality: moderate (todo hallazgo lleva archivo:línea y mecanismo; nada se ejecutó, así que ningún hallazgo llega a señal 3 por salida de herramienta).

## Veredicto en una frase
APPROVED: no hay Crítico ni Alto; el único Medio es una carrera entre `crear-pago` y la transferencia cuyo daño lo contiene el reembolso automático, y debe cerrarse antes de usar transferencias con clientes reales.

gate:ship: sin bloqueo de seguridad. `gate-check.mjs` no se corrió (solo lectura); el CTO debe correrlo antes de cerrar la compuerta.

## Resumen por severidad
| Sev | N | IDs |
|---|---|---|
| Crítico | 0 | |
| Alto | 0 | |
| Medio | 1 | M-1 |
| Bajo | 6 | B-1 … B-6 |
| Observaciones (sin mecanismo explotable) | 5 | O-1 … O-5 |

Preexistente vs introducido: M-1 es preexistente en `crear-pago` pero se vuelve alcanzable por la transferencia (introducido por 31391e04); B-1 es la clase B-3 de la primera auditoría, que sigue abierta, ahora con un sitio nuevo en la ruta de reembolso; B-2 a B-6 son introducidos por los cambios sin commitear o por 31391e04.

---

## Hallazgos

### [Medio] M-1 `crear-pago` en vuelo reescribe una reserva ya saldada por transferencia y deja un PaymentIntent vivo
- **Mecanismo**: `CrearPagoView` lee la reserva en estado `pendiente_pago` (bloque A, `apps/payments/views.py:112`), llama a Stripe sin candado, y en el bloque C guarda con la instancia vieja: `reserva.stripe_payment_intent_id = intent.id` y `save(update_fields=[precio_total, iva_monto, iva_tasa, forma_pago, stripe_payment_intent_id, ...])` (`apps/payments/views.py:514-524`). No vuelve a bloquear la fila ni revisa `estado`. `marcar_pagada_por_transferencia` bloquea la fila y la salda (`apps/bookings/transferencia.py:93-111`), pero solo anula el intent que ve en `stripe_payment_intent_id` (`transferencia.py:63,128`). Si `crear-pago` arrancó antes y termina después del commit de la transferencia, crea un intent nuevo, lo escribe sobre la reserva ya `pagada` y le devuelve el `client_secret` al cliente.
- **Evidencia**: `views.py:112` (chequeo solo en bloque A), `views.py:518` (escritura sin recheck), `transferencia.py:128` (cierra solo el intent leído bajo candado).
- **Consecuencia**: si el cliente completa esa tarjeta, el webhook cae en `_resolver_cobro_repetido`: el intent coincide con el guardado pero `monto_pagado` está vacío, así que se reembolsa como duplicado (`services.py:214,222-225`). El dinero vuelve, pero el cliente ve un cobro y un reembolso y Stripe no devuelve su comisión. Además `precio_total`/`iva_*`/`forma_pago` de la reserva saldada quedan reescritos. La defensa nueva de `services.py:214` convierte un doble cobro silencioso en un reembolso; no evita el cobro.
- **Probabilidad**: requiere que la vendedora marque la transferencia en la misma ventana (la duración de las llamadas a Stripe) en que el cliente abre el pago por tarjeta. Baja, pero es exactamente el caso de uso (cliente con problemas de tarjeta que a la vez recibe instrucciones de transferir).
- **Arreglo**: en el bloque C de `crear-pago`, dentro de `transaction.atomic()`, hacer `Reserva.objects.select_for_update().get(pk=...)`; si `estado != PENDIENTE_PAGO`, cancelar el intent recién creado (`cancel` con llave de idempotencia) y responder 409 `ya_no_pendiente`; guardar sobre la fila bloqueada y no sobre la instancia vieja.
- **Evidencia (tipo)**: inspección de código; no se reprodujo la carrera. Señal 2.

### [Bajo] B-1 `_producto_de(reserva)` se evalúa fuera del `try` de `registrar_notificacion`, ahora también en la ruta de reembolso por falta de cupo
- **Mecanismo**: `registrar_notificacion` atrapa `Exception` solo alrededor del INSERT (`apps/tenancy/notificaciones.py:64-76`). Los argumentos de la llamada se evalúan antes de entrar. `_registrar_cancelacion_sin_cupo` arma `_producto_de(reserva)` y `reserva.fecha:%d/%m/%Y` en la llamada (`apps/payments/services.py:360-365`), y se invoca después de `reembolsar()` y `reserva.save()` (`services.py:372,385-386`). `_notificar_reserva_nueva` hace lo mismo en el camino del pago (`services.py:200-205`, llamado en `services.py:155`). `_producto_de` toca `reserva.paquete.nombre` / `reserva.servicio.nombre` (`services.py:188-193`).
- **Consecuencia**: si esa lectura lanza (FK a un paquete invisible bajo RLS, fila borrada), la excepción sale de `aplicar_pago_exitoso` con el reembolso ya emitido en Stripe y el `save()` deshecho por el rollback del webhook: la reserva queda `pendiente_pago` y `conciliar_pagos` reintenta cada hora con el mismo fallo. En `_notificar_reserva_nueva` el efecto es peor: un cliente que pagó queda sin reserva hasta que se arregle. Las FK son `PROTECT`, así que hoy es improbable; por eso Bajo.
- **Es la clase B-3 de la primera auditoría, sin corregir**; el cambio sin commitear añade un segundo sitio, en la ruta del dinero.
- **Arreglo**: envolver la construcción de argumentos en `registrar_notificacion` no sirve (se evalúan fuera); en `_notificar_reserva_nueva` y `_registrar_cancelacion_sin_cupo` meter `try/except Exception: logger.exception(...)` alrededor de todo el cuerpo, o pasar `texto` como `callable` que `registrar_notificacion` evalúe dentro de su `try`.

### [Bajo] B-2 El sondeo avanza por el mayor `pk`: una notificación que confirma después de otra con `pk` mayor no vuelve a salir como tarjeta
- **Mecanismo**: `ultima` es el mayor `pk` visible (`apps/tenancy/notificaciones.py:147`) y las nuevas son `pk__gt=ultima_id` (`notificaciones.py:150`). El `pk` sale de una secuencia que no es transaccional y cada notificación se escribe dentro de la transacción de toda la petición (`EmpresaScopeMiddleware`, ver CLAUDE.md "Ojo con on_commit"). Si una transacción lenta toma el `pk` 10 y otra toma el 11 y confirma primero, un sondeo entre ambos fija la referencia en 11 y el 10 nunca satisface `pk > 11`.
- **Consecuencia**: se pierde la tarjeta (por ejemplo «El reembolso de X falló», nivel error). La campana sigue contando la no leída (`contar_no_leidas` cuenta por filas, `notificaciones.py:122-130`) y la lista la muestra, así que no es pérdida de dato, pero el aviso inmediato que el diseño promete se pierde. La transferencia amplía la ventana: sostiene el candado y la transacción durante la llamada a Stripe (`transferencia.py:128`).
- **Arreglo**: devolver como referencia el mayor `pk` con margen (p. ej. ignorar `pk` y filtrar por `creado_en > desde_servidor - 30 s`, deduplicando por id en el cliente), o que el JS guarde el conjunto de ids vistos de los últimos minutos.

### [Bajo] B-3 Los intentos con captcha rechazado no tienen límite y cada token falso cuesta una llamada síncrona a Cloudflare
- **Mecanismo**: el captcha se verifica antes de `authenticate`, por diseño, para que no cuente en Axes (`apps/cuentas/login.py:44-60`, docstring líneas 3-5). Axes solo cuenta fallos de contraseña; el throttle de DRF no cubre `/admin/login/` (`config/settings/base.py:55-58`). Un token no vacío de hasta 2048 caracteres pasa los filtros baratos y dispara `requests.post` con timeout de 5 s (`apps/bookings/captcha.py:92-96`, `TIMEOUT_OBLIGATORIO_SEGUNDOS=5`).
- **Consecuencia**: un anónimo con tokens basura mantiene ocupados los 3 workers de gunicorn (`render.yaml:28`, que además sirven la API de ventas) durante lo que tarde Cloudflare, hasta 5 s por petición si responde lento. Antes de este cambio cada POST al login costaba un hash de contraseña (decenas de ms); ahora puede costar segundos. Cloudflare delante absorbe parte, pero no hay regla en el repositorio.
- **Arreglo**: límite por IP a `/admin/login/` (regla de rate limiting en Cloudflare, o contador en base como el de recuperación, que ya existe en `apps/cuentas`), y bajar el timeout del login a 3 s.

### [Bajo] B-4 Sin llaves el login queda sin captcha y nada lo avisa; la salida de emergencia tampoco deja rastro
- **Mecanismo**: `login_exige_turnstile` exige las dos llaves y la bandera (`apps/cuentas/login.py:31-35`). `TURNSTILE_SITE_KEY` es nueva y la define el dueño a mano en Render (`render.yaml:213-214`, `sync: false`). Con `TURNSTILE_SECRET_KEY` puesta (ya existe para el checkout) y `TURNSTILE_SITE_KEY` vacía, el login no pide captcha y no se registra nada. `LOGIN_TURNSTILE_OBLIGATORIO` solo se lee del entorno (`config/settings/base.py:519`; `!= '0'` tras `strip()`), así que un atacante no puede apagarla; pero dejarla en `0` tras un incidente tampoco emite ninguna señal.
- **Consecuencia**: fail-open silencioso aceptable para local y pruebas; en producción es el mismo estado que antes del cambio, pero el dueño cree que está protegido. Axes sigue limitando a 5 fallos por usuario+IP.
- **Arreglo**: un `django.core.checks.Warning` (o `logger.warning` al arrancar) en `production.py` cuando falte una llave o `LOGIN_TURNSTILE_OBLIGATORIO` sea falso; y una línea en `render.yaml` documentando la variable.

### [Bajo] B-5 Los avisos de Django quedan ocultos por CSS y dependen de que `avisos.js` se ejecute
- **Mecanismo**: `[data-avisos-django] { display: none; }` (`apps/tenancy/static/tenancy/avisos.css:149-151`). Solo `avisos.js` los muestra como tarjetas o, si falla dentro del `try`, los vuelve a mostrar (`avisos.js:97-99`). Si el script no carga o no se ejecuta (404 de manifest tras un deploy, caché vieja, bloqueo, error de sintaxis antes de `iniciar`), el `<ul>` sigue oculto.
- **Consecuencia**: errores como «No se guardó la reserva…» (`apps/bookings/admin.py:1086`) o «No se pudo cerrar el cobro con tarjeta pendiente» (`transferencia.py:79`, que sale por la pantalla propia, no por messages) pueden no verse; la persona cree que guardó. Es de integridad de la información al operador, no de acceso.
- **Arreglo**: ocultar solo cuando el script ya arrancó (`html.avisos-js [data-avisos-django]{display:none}` y que el `<head>` o un `<script>` inline mínimo ponga la clase), o `<noscript><style>…display:block</style></noscript>`.

### [Bajo] B-6 La llamada a Stripe de `_cerrar_cobro_con_tarjeta` corre con la fila bloqueada y dentro de la transacción de toda la petición
- **Mecanismo**: `select_for_update` en `transferencia.py:93`, llamada de red a Stripe en `transferencia.py:128`, y el candado se libera hasta el COMMIT externo (el `atomic` de `EmpresaScopeMiddleware`). El timeout del SDK no está fijado en este módulo y gunicorn mata al worker a los 60 s (`render.yaml:28`).
- **Consecuencia**: durante la llamada, el webhook de ese mismo cobro y la vista de `crear-pago` esperan el candado. Si el worker muere después del `cancel` y antes del COMMIT, el intent queda anulado y la reserva `pendiente_pago`: seguro para el dinero (nadie cobra), pero obliga a rehacer el checkout. El resto del comportamiento verificado abajo.
- **Arreglo**: fijar `max_network_retries`/timeout corto (≤ 20 s) en `configurar_stripe` para el cliente de esta ruta. No cubierto: no leí `configurar_stripe` (ver "No cubierto").

---

## Observaciones (sin mecanismo explotable hoy)
- **O-1** `https://challenges.cloudflare.com/turnstile/v0/api.js` se ejecuta en la página donde se teclea la contraseña (`templates/admin/login.html:25`). Cloudflare no permite SRI ni alojarlo propio; es la contrapartida conocida de usar Turnstile. Se acepta; no se añade más código de terceros a esa página.
- **O-2** El `onerror="turnstileLoginNoCargo()"` inline (`login.html:25`) funciona porque no hay CSP (`config/settings/` no define `CSP`). Si se añade una CSP, ese manejador exige `unsafe-inline`; moverlo a `addEventListener` en `login-turnstile.js`.
- **O-3** `motivo` de las notificaciones de correo fallido incluye el `message` del JSON de Resend, hasta 200 caracteres (`apps/notifications/services.py:70-80`), guardado 90 días y servido en el JSON del sondeo (`notificaciones.py:152-158`). Los mensajes de validación de Resend no repiten la dirección del destinatario; si algún día lo hicieran, el correo del cliente volvería al feed (la clase B-4 de la primera auditoría).
- **O-4** La vendedora tiene `view_notificacion`, así que ve montos de reembolsos de su empresa (`services.py:507-535`). Ya los ve en la columna Cobro de Reservas; no hay dato nuevo.
- **O-5** `scope.empresa_actual` hace un `Empresa.objects.get` por llamada (`scope.py:132`); el sondeo la invoca 3 veces por petición. Costo despreciable a este volumen.

---

## Verificado sin hallazgo (con evidencia)

**1. Turnstile en el login**
- Orden: el captcha corre en `clean()` antes de `super().clean()`, que es el que llama a `authenticate` (`login.py:44-60`). Un captcha malo no llega a Axes ni a la contraseña; la prueba lo vigila (`tests_login.py:51-56`).
- Falla cerrada con llaves: sin petición, sin token, token vacío o mayor de 2048, Cloudflare caído, estado ≠ 200, JSON roto, `success` distinto de `True`, `action` u `hostname` distintos, todo devuelve `False` (`captcha.py:89-119`). `action` exacto `login` (`login.py:23,53`) y `hostname` de `request.get_host()`, validado contra `ALLOWED_HOSTS` (`production.py:13`) y comparado sin distinguir mayúsculas.
- Token reutilizable: un token del checkout (otro `action`, otro hostname) no sirve (`tests_login.py:102-111`); uno de recuperar (`recuperar_solicitar`/`recuperar_confirmar`, `cuentas/views.py:65-67`) tampoco, por `action`; y Cloudflare invalida el token al verificarlo. Un token minted en el frontend tiene hostname del frontend.
- Mensaje: un único texto para token ausente o inválido (`login.py:25-28,59`), idéntico para cuentas existentes y no existentes; no hay oráculo de cuentas. El mensaje de credenciales malas sigue siendo el de Django.
- XSS: `data-sitekey="{{ form.turnstile_site_key }}"` va autoescapado (`login.html:16`); `login-turnstile.js` solo escribe una cadena fija con `textContent` (líneas 28-29).
- CSRF: el widget se inserta dentro de `#login-form` y no toca el token CSRF; `LoginConTurnstile.__init__(request=None, *args, **kwargs)` coincide con la firma que usa `AdminSite.login`.
- Salida de emergencia: solo lee `os.environ` (`base.py:519`), no hay parámetro de petición, cookie ni modelo que la altere.

**2. Avisos como tarjetas**
- El servidor renderiza `{{ message }}` autoescapado en las plantillas de Unfold (`success.html`, `error.html`); todo `message_user`/`messages.*` del repositorio pasa una cadena simple (grep de `message_user(` y `messages.` en `apps/`); no hay `mark_safe` en mensajes. `tests_login.py:132-136` comprueba el escape.
- El JS lee con `textContent` (`avisos.js:89`) y crea nodos con `el()` que usa `textContent` (`avisos.js:40-45`); no hay `innerHTML`/`outerHTML`/`insertAdjacentHTML` (vigilado en `tests_login.py:158-159`). Un mensaje con HTML se aplana a texto.
- URLs: `rutaPropia` exige `/` inicial, rechaza `//`, `\`, espacios y control (`avisos.js:229-231`); coincide con `enlace_seguro` del servidor (`notificaciones.py:41-48`). `datos.notificaciones_url` pasa por `rutaPropia` antes de usarse (`avisos.js:254`) y en `avisos.js:299` es el mismo valor ya validado.
- `localStorage` guarda solo `'1'`/`'0'` (sonido); `sessionStorage` solo un entero validado con `/^[0-9]+$/` (`avisos.js:272`). Web Audio no recibe datos del servidor.

**3. Sondeo con texto**
- Fuga entre empresas: `_del_alcance` filtra por la empresa del alcance, y devuelve todo solo a operador de plataforma; sin empresa y sin ser operador, `none()` (`notificaciones.py:109-119`). `empresa_actual` lee el alcance resuelto por el middleware, no un parámetro (`scope.py:124-132`); RLS cubre las dos tablas (CLAUDE.md, prueba `tests_notificaciones_rls.py`). Una cuenta sin membresía ni grupo de operador recibe 403 del middleware antes de llegar a la vista.
- Permisos: sin `view_notificacion` el JSON no trae texto (`avisos.py:86-87`, `notificaciones.py:144-145`).
- `notif`: `_entero` solo acepta enteros ≥ 0 (`avisos.py:103-109`); se usa únicamente como cota inferior `pk__gt` dentro del alcance, así que no hay IDOR (pedir `notif=0` devuelve el propio historial de ≤ 90 días que ya lista el admin). Un valor enorme provocaría una excepción que `except Exception` de `avisos.py:98` convierte en «campana callada», con un `logger.exception` por sondeo (ruido de Sentry, no fuga).
- El `sessionStorage` de una pestaña sobrevive a un cambio de usuario en la misma pestaña, pero la referencia solo acota `pk__gt` dentro del alcance del nuevo usuario: no revela filas de otra empresa.
- Inyección: solo ORM y parámetros enteros; `desde` pasa por `parse_datetime` con captura de `ValueError` (`avisos.py:48-53`).
- Caché: el endpoint va con `admin.site.admin_view(...)` (`config/urls.py:49`), que aplica `never_cache`; el JSON con nombres de clientes no se cachea en Cloudflare ni en navegador.
- Carga: por sondeo ~7 consultas acotadas (`LIMIT 100`, `[:3]`, `[:5]`); `visibilitychange` detiene los sondeos de pestañas ocultas (`avisos.js:344-352`).

**4. Middleware de sesión**
- `RUTAS_DE_SONDEO` es un `frozenset` constante con una sola ruta, comparada con `request.path_info` exacto (`middleware_sesion.py:10,17`). No hay entrada del cliente que añada rutas ni forma de que otra URL coincida (no se normaliza). El sondeo solo lee; esa vista no escribe en sesión. El login y el logout viven en otras rutas, así que su `Set-Cookie` no se pierde. Un `flush()` de sesión por cambio de hash de contraseña en esa ruta no manda la cookie de borrado, lo que es inocuo: el servidor ya la invalidó. El mensaje en cola de Django no se consume porque la vista no itera `messages`.

**5. Transferencia y dinero**
- Orden y atomicidad: `_cerrar_cobro_con_tarjeta` corre al final, tras `full_clean`, `save` y `reservar_cupo_al_confirmar` (`transferencia.py:114-128`); un fallo de cupo, validación o integridad sale antes y deja el intent vivo, y un fallo de Stripe levanta `ErrorDeTransferencia` dentro del `atomic` y revierte todo lo anterior.
- Falla cerrada: `succeeded`, `processing` y `requires_capture` rechazan (`transferencia.py:56,70-73`); cualquier `StripeError` rechaza, salvo `resource_missing` (`77-81`). Si el intent pasa a `succeeded` entre el `retrieve` y el `cancel`, Stripe rechaza el `cancel` con `InvalidRequestError` distinto de `resource_missing`, y se rechaza.
- Doble clic: la segunda petición espera el `select_for_update` (`transferencia.py:93`) y encuentra `pagada`; `puede_marcarse_pagada` la rechaza (`35-38`). La llave de idempotencia `transferencia-{pk}-cancel` repite la misma respuesta. Un intent ya `canceled` no vuelve a cancelarse (`74-76`).
- `precio_total is None` y `monto > precio_total` rechazan (`99-105`); `monto` se parsea con `Decimal`, finito y positivo (`46-53`). La plantilla escapa `monto`, `error` y datos del cliente (`pagar_transferencia.html:7-30`).
- `_resolver_cobro_repetido` solo da por repetido un intent que ya dejó `monto_pagado` (`services.py:214`): un cobro con tarjeta posterior a la transferencia se reembolsa (cierra el H-1 anterior, con la salvedad de M-1). `_registrar_cancelacion_sin_cupo` corre dentro de la transacción del webhook y el INSERT va en savepoint propio (`notificaciones.py:65`); su único riesgo es B-1.

**6. render.yaml**
- Sin cambios sin commitear; el cron `pescadeportiva-limpiar-notificaciones` (`render.yaml:136-150`) no choca de horario con los otros (`15 9 * * *`). Omitir `setup_roles` del `buildCommand` es correcto: `group.permissions.set` reemplaza los permisos de cada grupo y correrlo en cada deploy borraría ajustes manuales; el costo es que, hasta correrlo una vez a mano, nadie tiene `view_notificacion` y no aparece campana ni lista (falla cerrada). Ningún secreto en el archivo. El cron hereda todo el grupo de secretos (B-5 de la primera auditoría, sin cambio; sigue siendo menor).

---

## No cubierto
- `configurar_stripe` (timeout y reintentos del SDK) y el cuerpo completo de `CrearPagoView`: solo se leyeron los tramos citados.
- Comportamiento real de Axes 8.3.1 con un formulario que lanza `ValidationError` antes de `authenticate` (se razona desde el código del repositorio y la prueba `tests_login.py:51-56`, no desde el paquete).
- Configuración del widget en Cloudflare (dominios, modo) y de las variables reales en Render.
- `apps/tenancy/static/tenancy/avisos.css` fuera de la regla de ocultación; `limpiar_notificaciones`; `EmpresaScopeMiddleware` completo (solo líneas citadas).
- Cualquier ejecución: no se corrieron pruebas ni el servidor.

## Orden de arreglo sugerido
1. M-1 (recheck de estado bajo candado en el bloque C de `crear-pago`).
2. B-4 (aviso al arrancar si faltan llaves o la salida de emergencia está activa) y B-3 (límite por IP al login).
3. B-1 (try/except alrededor de los dos sitios de notificación en la ruta de pago/reembolso).
4. B-2, B-5, B-6.

VERDICT: APPROVED — sin Crítico ni Alto; M-1 debe cerrarse antes de operar transferencias con clientes reales.
