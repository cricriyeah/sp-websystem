# ARCH: Recuperación de contraseña por código al correo (backoffice)

> Lector: el senior-dev que implementa en `backend/` (Django 6, Unfold). Decisión: nueva app `apps/cuentas`
> con código de 6 dígitos guardado como HMAC, Turnstile obligatorio y fail-closed en los dos pasos,
> límites en base de datos y respuesta neutra. Fecha 2026-10-25, rama `feat/marca-sun-baja`. Sin código escrito.

**Señales**: input = correo, código y token de captcha tecleados por un anónimo; boundary = anónimo -> cambio de
credencial de cualquier cuenta (incluida la de superusuario) y app -> Cloudflare / Resend; data = hash del código
10 min + eventos 90 días; money = ninguno directo (una cuenta tomada ve reservas, cobros y reembolsos);
control = límites y tope de intentos, su inverso es negar la recuperación a una víctima (ver §4); execution = envío
fuera de la petición y consumo concurrente del código.
**Tamaño**: Medio (1 app, 2 tablas, 1 migración, ~25 archivos). **Compuerta**: gate:arch obligatorio (input + boundary).

## 1. Problema y no-objetivos

Hoy `/admin/login/` no tiene recuperación (`docs/deploy/ENDURECIMIENTO.md` la marca "no aplica"). Quien olvida la
contraseña depende de que otro la cambie a mano. Se agrega recuperación por código al correo para **todas** las cuentas
con correo y se cierra con Turnstile obligatorio.

**Hallazgo que condiciona todo**: `crear_usuario_con_rol` y `AltaUsuarioForm` **no piden correo**
(`apps/tenancy/usuarios.py`, `apps/bookings/forms.py`); `auth.User.email` es opcional y **no es único**. Sin
corregirlo, nadie puede recuperar nada. Por eso T10 y la acción del dueño (§6).

**No-objetivos**: login con Turnstile o 2FA (WP-27 del REFACTOR-PLAN), recuperación por SMS/WhatsApp, frontend Next.js,
colas externas (Celery/Redis), cambiar el mínimo de contraseña (ver §7), recuperar el *usuario* sin correo.

## 2. Decisiones y alternativas rechazadas

| # | Decisión | Rechazado y por qué |
|---|---|---|
| D1 | App nueva `apps/cuentas`, modelo **por usuario**, sin FK a empresa (no hay RLS ni `empresa_id`, así que el guardarraíl de `tests_rls.py` no lo toca) | Poner en `tenancy`: ya es cajón de sastre y su middleware/RLS invita a atar el código a una empresa |
| D2 | Un solo registro por usuario (`OneToOne`): pedir otro código **sobrescribe** el anterior | Tabla de N códigos con índice parcial único: más estados, más carreras, mismo efecto |
| D3 | HMAC-SHA256 con `SECRET_KEY` sobre `usuario_id:hash_contraseña_actual:código` (`django.utils.crypto.salted_hmac`) | SHA-256 simple: 10^6 combinaciones se rompen offline en ms si se filtra la base. PBKDF2: lento, sin ganancia real con tope de 5 intentos. Atar al hash de la contraseña mata el código si la contraseña cambia por otro camino |
| D4 | **Un solo POST** en el paso 2: correo + código + contraseña nueva x2 | Dos pasos (verificar código -> token -> contraseña): crea un estado intermedio "verificado" que hay que proteger y expira |
| D5 | Paso 1 responde renderizando el paso 2 (sin sesión, sin correo en la URL) | Guardar el correo en `request.session`: cada POST anónimo crearía una fila de sesión (relleno de tabla). Correo en query: queda en logs |
| D6 | Límites contados **en base de datos** (`EventoRecuperacion`) | Cache de archivos: `incr` no es atómico entre los 3 workers de gunicorn y no se comparte entre instancias (`production.py:56`) |
| D7 | Envío del correo en un hilo daemon tras el commit; síncrono en pruebas | Responder tras `requests.post` a Resend (~300 ms solo si la cuenta existe) es un oráculo de existencia. Rellenar con `sleep`: falla si Resend tarda más que el relleno. Cola/cron: infraestructura nueva |
| D8 | Reutilizar el widget y `TURNSTILE_SECRET_KEY` actuales; sumar el hostname del backend al widget y la var `TURNSTILE_SITE_KEY` en Render. Se ata el token a `action` y `hostname` | Segundo widget con segundo secreto: más llaves para el dueño. El ataque de usar un token del checkout público queda cerrado por la verificación de `action` |
| D9 | Enlace "¿Olvidaste...?" **sin tocar** `templates/admin/login.html`: Unfold 0.103 pinta el botón si existe la URL llamada `admin_password_reset` (comprobado en `unfold/templates/admin/login.html`) | Reescribir el bloque del formulario: se rompe con cada actualización de Unfold |
| D10 | Ninguna cuenta se bloquea por pedir recuperación (OWASP: el bloqueo es un arma de negación). El tope de 5 es **por código**, no por cuenta | Bloquear la cuenta tras N fallos de código |

## 3. Diseño

### 3.1 Datos (`apps/cuentas/models.py`, migración `0001`)

```
CodigoRecuperacion: usuario OneToOne(AUTH_USER_MODEL, CASCADE) · codigo_hash char(64) · creado_en · vence_en
                    · intentos smallint=0 · consumido_en null
EventoRecuperacion: creado_en (index) · tipo {solicitud, confirmacion} · resultado char(30) · usuario FK null
                    (SET_NULL) · correo_hash char(64, index) · ip GenericIPAddress null     # NUNCA el código
```
`resultado` (cadena corta y fija): `enviado`, `sin_cuenta`, `inactiva`, `sin_correo`, `ambigua`, `limite_correo`,
`limite_global`, `cooldown`, `envio_fallido`, `exito`, `codigo_incorrecto`, `vencido`, `agotado`, `sin_codigo`,
`password_rechazada`. `correo_hash` = `salted_hmac('cuentas-correo', correo_normalizado)`: el límite por correo se aplica
al correo **tecleado**, exista o no. Correo normalizado = `strip().lower()`, `EmailField(max_length=254)`.

### 3.2 URLs y UI (en `config/urls.py`, **antes** de `path('admin/', ...)`)

| Ruta | Nombre | Vista |
|---|---|---|
| `admin/recuperar/` | `admin_password_reset` | paso 1: correo + widget |
| `admin/recuperar/codigo/` | `admin_password_reset_codigo` | paso 2: correo, código, contraseña x2 + widget |

Plantillas `backend/templates/cuentas/recuperar_solicitar.html` y `recuperar_codigo.html`, `{% extends
"unfold/layouts/unauthenticated.html" %}` con `unfold/helpers/field.html` y `EstiloUnfoldMixin` (`apps/tenancy/forms_unfold.py`).
Contexto: `admin.site.each_context(request)` + `turnstile_site_key`. Widget: script
`https://challenges.cloudflare.com/turnstile/v0/api.js` y `<div class="cf-turnstile" data-sitekey data-action>`;
el token llega en `cf-turnstile-response`. Acciones: `recuperar_solicitar` y `recuperar_confirmar`. Atributos:
código `autocomplete="one-time-code" inputmode="numeric" pattern="[0-9]{6}"`, contraseñas `autocomplete="new-password"`.
Decoradores en las dos vistas: `require_http_methods(['GET','POST'])`, `never_cache`, `sensitive_post_parameters`.
Usuario autenticado -> redirige a `admin:index`. Sin `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` o `RESEND_API_KEY`
la vista responde 503 con "Recuperación no disponible, pide a tu jefe que cambie tu contraseña" (estado global, no
depende de la cuenta). Dirección: hereda Unfold tal cual (denso, alto contraste); no se agrega estilo propio.

`<frontend_aesthetics>` NEVER use generic AI-generated aesthetics: overused fonts (Inter, Roboto, Arial, system),
cliché schemes (purple gradients; the cream + serif + terracotta editorial default), predictable layouts,
cookie-cutter components. For regulated/operator UIs prefer dense, restrained, high-contrast, WCAG-AA layouts with a
cohesive context-specific palette and purposeful micro-interactions. `</frontend_aesthetics>`

### 3.3 Paso 1: pedir código (POST `admin/recuperar/`), en este orden

1. IP = `apps.bookings.ip_cliente.ip_del_cliente(request)`. Si la IP ya tiene >= 10 solicitudes en 1 h -> 429 genérico (no depende del correo).
2. `verificar_turnstile_obligatorio(token, ip, accion='recuperar_solicitar', hostname=request.get_host() sin puerto)`; falso -> 400 "No pudimos verificar que eres una persona, inténtalo de nuevo". No escribe nada en base.
3. Valida el formato del correo (error de formato no revela nada).
4. Límites por `correo_hash`: cooldown 60 s, 3/h, 10/día; tope global 50 correos/día (protege la cuota de Resend que usan las confirmaciones de clientes). Si se pasa cualquiera: no envía, mismo resultado visible.
5. Elegible = **exactamente una** cuenta con `email__iexact`, `is_active`, `has_usable_password()`. Cero, varias, inactiva o con contraseña inutilizable: no envía (una contraseña inutilizable es un bloqueo deliberado; recuperar lo reabriría).
6. Elegible: `transaction.atomic` + `update_or_create` (hash, `vence_en = ahora + 10 min`, `intentos=0`, `consumido_en=None`); `on_commit` -> `despachar(enviar_correo_codigo_recuperacion, ...)`. No elegible: calcula igualmente un HMAC de relleno.
7. Escribe `EventoRecuperacion` en **ambos** caminos y renderiza el paso 2 con el mismo texto: "Si el correo corresponde a una cuenta activa, te enviamos un código de 6 dígitos. Vence en 10 minutos."
8. Todo el bloque 4-7 va en `try/except Exception` que registra solo `type(exc).__name__`: sin esto `ErrorInesperadoAdminMiddleware` (rutas `/admin/`) redirige distinto para cuentas que existen.

### 3.4 Paso 2: confirmar (POST `admin/recuperar/codigo/`)

1. Límite de IP: >= 20 confirmaciones fallidas en 1 h -> 429. 2. Turnstile obligatorio (`recuperar_confirmar`).
3. Formulario: correo, código `^\d{6}$`, contraseña x2 iguales (`max_length=128`).
4. **Validar la contraseña antes de tocar el código**, siempre y para cualquier correo: `validate_password(p, usuario)` con la cuenta
   real si es elegible o un `User(username=local, email=correo)` sin guardar si no. Así un error de validador no distingue cuentas ni
   revela si el código acertó, y no gasta intento.
5. Consumo atómico (dos bloques `transaction.atomic` separados para que el intento persista aunque falle el código):
   `UPDATE ... SET intentos=intentos+1 WHERE usuario=X AND consumido_en IS NULL AND vence_en>ahora AND intentos<5` (0 filas = vencido/agotado/sin código).
   Luego `hmac.compare_digest(hash_guardado, hash_calculado)`. Acierto: `UPDATE ... SET consumido_en=ahora WHERE pk AND consumido_en IS NULL`; solo
   quien actualiza 1 fila gana. Máximo 5 comparaciones por código aunque lleguen 100 peticiones a la vez.
6. Ganador, en la misma transacción: `set_password` + `save(update_fields=['password'])`; borra las filas de `Session` de ese usuario; `axes.utils.reset(username=)`;
   evento `exito`. Tras el commit: correo "Tu contraseña cambió" (+ copia sin código a `RECUPERACION_AVISO_ADMIN` si existe).
7. Respuesta: 302 a `admin:login` con `messages.success`. **No inicia sesión** (OWASP). Cualquier fallo de código: 400 con un solo texto
   "El código es incorrecto o ya venció. Si fallaste varias veces, pide uno nuevo".
Sesiones: cambiar la contraseña ya invalida todas (Django compara `get_session_auth_hash()` en cada petición, `auth/__init__.py:get_user`); el borrado de filas es higiene y se prueba aparte.

### 3.5 Turnstile obligatorio (`apps/bookings/captcha.py`)

Se extrae `_consultar_siteverify(token, ip)` y `verificar_turnstile` (abierto, para el checkout) se queda con **idéntica** conducta y pruebas.
Nueva `verificar_turnstile_obligatorio(token, ip, *, accion, hostname) -> bool`: `False` si falta `TURNSTILE_SECRET_KEY` (también en local;
allí se usan las llaves de prueba de Cloudflare), token vacío o > 2048 caracteres (sin llamada), error de red, timeout 5 s, HTTP != 200, JSON inválido,
`success != true`, `action != accion` o `hostname != hostname`. Solo `True` si todo cuadra. Loguea error sin el token.

### 3.6 Correo (`apps/notifications/`)

`plantilla.correo(...)` hoy trae un pie de "comprobante de reserva": se agrega el kwarg `pie_html=None` y `CAMPO['cuenta']=TINTA`; sin el kwarg la salida no cambia
(`tests_membrete.py` lo vigila). `services.py` gana `enviar_correo_codigo_recuperacion` y `enviar_correo_contrasena_cambiada`, ambas con un helper
`_post_resend_seguro` que **no** usa `logger.exception` (los locales del frame llevarían el código a Sentry, que captura variables locales por defecto).
Reglas: `to` = dirección **guardada** en la cuenta, nunca la tecleada; **sin `bcc`** aunque `RESEND_BCC` exista (copiaría el código al buzón del negocio);
asunto sin código ("Tu código para recuperar la contraseña"); cuerpo con el código en un recuadro, usuario de la cuenta ("Usuario: ..."), "vence en 10 minutos",
"si no lo pediste, ignóralo: tu contraseña no cambia"; versión `text`; datos escapados con `services._html`; sin enlaces. El código viaja como `Secreto`
(`seguridad.py`: `repr`/`str` = `<Secreto>`, `.revelar()` entrega los dígitos) para que ningún repr, traza o log lo imprima.

## 4. Modelo de amenazas

| Amenaza | Mitigación |
|---|---|
| Enumerar cuentas (texto, código HTTP, redirección) | Mismo texto/estado/cabeceras para existente, inexistente, inactiva, sin correo, ambigua y limitada. Validación de contraseña previa e igual para todos. `try/except` anula el redirect distinto del middleware. Prueba compara respuestas |
| Enumerar por tiempo | El envío sale del hilo de la petición; ambos caminos hacen el mismo trabajo de base y un HMAC. Límite práctico, no perfecto: se documenta |
| Fuerza bruta del código | 5 intentos por código (UPDATE condicional atómico), 3 códigos/h y 10/día por correo, 20 fallos/h por IP, Turnstile por intento. 5x3 = 15 intentos/h sobre 10^6 = 1.5e-5/h; tope diario 50 intentos = 5e-5/día por cuenta |
| Comparación con fuga por tiempo | `hmac.compare_digest` sobre dos HMAC de igual longitud |
| Reutilización / código viejo | `consumido_en` por UPDATE condicional; nuevo código sobrescribe; atado al hash de contraseña vigente; vence a 10 min |
| Carrera al consumir | UPDATE atómico (arriba). Prueba con hilos en Postgres |
| Spam de correos a la víctima (bombing) | Cooldown 60 s + 3/h + 10/día por correo tecleado + 10/h por IP + Turnstile |
| Agotar la cuota de Resend (daña confirmaciones a clientes) | Tope global 50 correos/día; al llegar, neutral y `logger.error` (Sentry) |
| Negación a la víctima (el inverso del control) | Un atacante con Turnstile puede sobrescribir/gastar el código de alguien: limitado a 3/h y 10/día, **no bloquea la cuenta** ni el login (Axes sigue por usuario+IP). Residual aceptado; camino manual en §6 |
| Toma de cuenta por correo comprometido | Aviso de cambio al correo (inútil si el atacante lo controla), copia opcional a `RECUPERACION_AVISO_ADMIN`, sesiones previas muertas, auditoría. Mitigación real: 2FA (WP-27). Superusuarios incluidos por pedido del dueño: ver §8 |
| Fijación/robo de sesión | No hay login ni sesión en el flujo. Al cambiar, todas las sesiones del usuario mueren; no se inicia sesión nueva |
| CSRF | `CsrfViewMiddleware` activo + `{% csrf_token %}`; prueba: POST sin token = 403 |
| Cabeceras/caché | `never_cache` (no-store), `X-Frame-Options` por middleware, `Referrer-Policy: same-origin` (default de Django); el código nunca va en URL |
| El código en logs, Sentry o correos de error | `Secreto`, sin `exc_info` ni `logger.exception` con el código en alcance, `sensitive_post_parameters`, eventos sin código, `send_default_pii=False` ya existente. Prueba con `caplog` |
| Copia del código a terceros | Sin `bcc`; Resend conserva el cuerpo unos días en su panel: residual, el código vence a los 10 min |
| Token de captcha reutilizado de otro sitio | `action` y `hostname` exigidos; el token es de un solo uso (300 s) |
| Cuenta inactiva / bloqueada a propósito | No elegible (is_active, contraseña inutilizable) |
| Cuentas con el mismo correo | Si hay más de una, no se envía y se registra `ambigua`; T10 impide duplicados nuevos |
| Contraseña débil | `validate_password` (los 4 validadores vigentes) con el usuario real |
| DoS por contraseña enorme | `max_length=128` |

## 5. Tareas para el senior-dev (TDD: la prueba va primero y se ve fallar)

Rutas relativas a `backend/`. Cada tarea termina con la suite de su alcance en verde.

1. **Captcha obligatorio.** Prueba en `apps/bookings/tests_captcha.py`: sin secreto -> False y `post` no se llama; token vacío / de 2049 caracteres -> False sin llamada;
   éxito con `action` y `hostname` correctos -> True; `action` o `hostname` distintos -> False; `RequestException`, HTTP 500, JSON inválido, `success:false` -> False; las pruebas
   existentes de `verificar_turnstile` (incluida la de falla abierta) pasan **sin editarse**. Código: `apps/bookings/captcha.py`.
2. **Esqueleto.** Crear `apps/cuentas/{__init__,apps,models,admin}.py`, `migrations/0001_initial.py`; `config/settings/base.py`: `INSTALLED_APPS += 'apps.cuentas'`, `TURNSTILE_SITE_KEY`
   y los `RECUPERACION_*` (§6). Pruebas `tests_modelos.py`: `OneToOne`, defaults, el modelo **no** tiene campo `empresa`, migración aplica en SQLite y Postgres, `tests_rls.py` sigue verde.
3. **Primitivas.** `apps/cuentas/seguridad.py` (`Secreto`, `generar_codigo`, `hash_codigo`, `hash_correo`, `coincide`). Pruebas `tests_seguridad.py`: `randbelow` mockeado a 7 da `'000007'`;
   `repr(Secreto)` no contiene dígitos; el hash cambia por usuario, por código y cuando cambia `user.password`; `coincide` llama a `hmac.compare_digest`; `hash_correo` ignora mayúsculas y espacios.
4. **Servicio: pedir.** `apps/cuentas/servicio.py::solicitar_codigo(correo, ip)`. Pruebas `tests_solicitar.py`: inexistente, inactiva, sin correo, duplicada, contraseña inutilizable -> sin fila, sin correo, **mismo resultado**; válida -> hash != código, vence en 10 min, `intentos=0`;
   segunda petición < 60 s no sobrescribe; tras el cooldown sí y el código viejo ya no verifica; 4ª en 1 h, 11ª en el día, tope global 50 e IP 11ª/h -> sin envío; se envía a la dirección guardada aunque se tecleó con otras mayúsculas;
   ningún campo de `EventoRecuperacion` contiene el código.
5. **Servicio: confirmar.** `confirmar_codigo(correo, codigo, password, ip)`. Pruebas `tests_confirmar.py`: éxito cambia la contraseña y consume; código incorrecto suma 1 y da el error genérico; 5 fallos y el 6º **con código correcto** falla; vencido
   (mock de `timezone.now`), reutilizado, de otra cuenta, cuenta inactiva -> falla; contraseña débil o distinta -> error de validador, **sin** gastar intento y **mismo error** para un correo inexistente; contraseña cambiada por otra vía invalida el código;
   cliente con sesión previa queda redirigido a login y sus filas de `Session` desaparecen; `AccessAttempt` del usuario se limpia; sale el aviso de cambio.
6. **Carreras.** `tests_carreras.py` (`TransactionTestCase`, solo Postgres, `skipUnless(connection.vendor == 'postgresql')`): 2 hilos con el código correcto -> exactamente 1 gana; 20 hilos con código incorrecto -> `intentos` nunca pasa de 5.
   Más una prueba determinista del UPDATE condicional que corre también en SQLite.
7. **Vistas, formularios, plantillas, URLs.** `apps/cuentas/{forms,views}.py`, `templates/cuentas/*.html`, rutas en `config/urls.py`. Pruebas `tests_vistas.py`: GET 200 con `cf-turnstile`, `data-sitekey`, `data-action` y csrf; `Cache-Control: no-store`;
   `/admin/login/` contiene el enlace a `admin_password_reset`; POST sin token / Turnstile falso / Cloudflare caído -> 400 y **ni una escritura ni un correo**; respuestas idénticas (estado, cuerpo, cabeceras salvo csrf) para existente vs inexistente vs inactiva;
   429 por IP; POST sin CSRF = 403; usuario autenticado -> redirige; éxito -> 302 a login con mensaje y sin sesión iniciada; ninguna respuesta contiene código ni hash; sin `TURNSTILE_SITE_KEY` -> 503.
8. **Correo.** `plantilla.py` (`pie_html`, `CAMPO['cuenta']`), `services.py` (2 funciones + `_post_resend_seguro`). Pruebas `apps/notifications/tests_correo_cuentas.py`: el payload a Resend tiene `to=[guardado]`, **sin `bcc`** con `RESEND_BCC` puesto, asunto sin código,
   html y text con código y usuario, HTML escapado; Resend sin configurar -> False sin excepción; fallo HTTP -> `caplog` sin el código; `tests_membrete.py` sin cambios.
9. **Envío en segundo plano.** `apps/cuentas/envio.py::despachar(fn, *args)`: hilo daemon con `try/except` que registra solo la clase de error y cierra su conexión; síncrono si `'test' in sys.argv`. Pruebas: con el modo hilo forzado la vista no llama a `requests.post` en el hilo de la petición;
   un fallo del envío escribe evento `envio_fallido` y no rompe la respuesta.
10. **Correo en las altas.** `AltaUsuarioForm` (obligatorio, único sin distinguir mayúsculas), `crear_usuario_con_rol(..., email='')` (opcional en el servicio para no romper pruebas existentes), `UserChangeForm` del `UserAdmin` con `clean_email` que rechaza duplicados.
    Pruebas en `apps/tenancy/tests_alta_usuario.py` y `tests_usuarios_admin.py`. Verificar con la prueba existente que el jefe puede cambiar la contraseña de su vendedora (camino manual); si no puede, **reportarlo**, no ampliarlo aquí.
11. **Operación.** Comandos `auditar_correos_cuentas` (lista usuario, superusuario sí/no, con/sin correo, duplicado; correos enmascarados `a***@dominio`) y `limpiar_eventos_recuperacion --dias 90`; `EventoRecuperacionAdmin` solo lectura para operador.
    Pruebas: salida del auditor, borrado por antigüedad, admin sin add/change/delete.
12. **Docs y despliegue.** `render.yaml` (`TURNSTILE_SITE_KEY` `sync: false`, `RECUPERACION_AVISO_ADMIN` opcional), `docs/deploy/ENDURECIMIENTO.md` (reemplazar "no aplica", pasos de Cloudflare), sección en `backend/CLAUDE.md`.

**Compuertas de aceptación (congelar antes de implementar; no se editan al construir)**:
SQLite `venv/Scripts/python.exe manage.py test apps.cuentas apps.bookings.tests_captcha apps.notifications apps.tenancy.tests_alta_usuario`; Postgres con
`DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=127.0.0.1 DB_PORT=5434 STRIPE_SECRET_KEY= STRIPE_WEBHOOK_SECRET=` y `manage.py test apps config`;
`manage.py makemigrations --check --dry-run`; `manage.py check --deploy --fail-level WARNING` con `config.settings.production`; `grep -rn --exclude='tests_*.py' "logger.exception\|exc_info" apps/cuentas` sin resultados.

## 6. Variables de entorno y acciones del dueño en Render y Cloudflare

| Variable | Dónde | Estado |
|---|---|---|
| `TURNSTILE_SECRET_KEY` | Render (existe en `render.yaml`) | **Obligatoria**: sin ella la recuperación responde 503 (cierra) |
| `TURNSTILE_SITE_KEY` | Render, **nueva**, `sync: false` | El mismo valor que `NEXT_PUBLIC_TURNSTILE_SITE_KEY` en Vercel (es un par con el secreto) |
| `RESEND_API_KEY`, `RESEND_FROM` | Render (existen) | Obligatorias; sin ellas 503 |
| `RECUPERACION_AVISO_ADMIN` | Render, opcional | Correos (CSV) que reciben un aviso, sin código, de cada cambio de contraseña. Recomendado: el del dueño |
| `RECUPERACION_CODIGO_MINUTOS=10`, `_MAX_INTENTOS=5`, `_MAX_POR_CORREO_HORA=3`, `_MAX_POR_CORREO_DIA=10`, `_COOLDOWN_SEGUNDOS=60`, `_MAX_POR_IP_HORA=10`, `_MAX_FALLOS_IP_HORA=20`, `_MAX_ENVIOS_DIA=50` | No definirlas | Defaults en `base.py`; solo para afinar sin tocar código |

Pasos manuales: (1) Cloudflare -> Turnstile -> el widget del checkout -> agregar el **hostname del backend** (el de `/admin/`) a su lista de dominios;
(2) copiar la site key a `TURNSTILE_SITE_KEY` en Render; (3) confirmar que `TURNSTILE_SECRET_KEY` está puesta de verdad (hoy el checkout falla abierto si no, y no se nota);
(4) cargar el correo de **cada** cuenta (admin -> Usuarios -> editar) y correr `manage.py auditar_correos_cuentas` en el Shell de Render; (5) probar con una cuenta de verdad.
Local: llaves de prueba de Cloudflare, sitekey `1x00000000000000000000AA` y secreto `1x0000000000000000000000000000000AA`; con `DEBUG` y sin Resend el código se
imprime con `print` (nunca por `logging`) para poder probar a mano.

**Cuenta sin correo**: no puede recuperarse sola. Vendedora o jefe: lo cambia su jefe u operador con "Cambiar contraseña" del admin de Usuarios y de paso carga su correo.
Operador o superusuario sin correo: `python manage.py changepassword <usuario>` en el Shell de Render y cargar el correo después.

## 7. Seguridad, rollback y costo

**Safeguards (marcar en revisión)**: [ ] el código jamás se guarda, loguea ni se devuelve en claro (Secreto + caplog); [ ] Turnstile fail-closed en ambos pasos, con `action` y `hostname`;
[ ] respuesta idéntica para cualquier correo; [ ] consumo por UPDATE condicional atómico; [ ] sin `bcc` en correos de cuenta; [ ] al cambiar: sesiones muertas, aviso enviado, Axes limpio; [ ] `verificar_turnstile` del checkout intacto.
**Estándares**: OWASP Forgot Password Cheat Sheet (mensaje y tiempo uniformes, límites, no bloquear la cuenta, no iniciar sesión, aviso por correo); ASVS 4.0.3 V2.2.1, V2.5.5, V2.7.2 (10 min), V2.7.3 (un uso), V2.7.5 (solo hash), V2.7.6 (CSPRNG, 6 dígitos), V3.3.3 (cerrar sesiones). V2.5.6 prefiere un TOTP: el correo es el piso mientras no exista 2FA.
**Rollback**: código -> revertir el commit; el enlace del login desaparece solo (la URL deja de existir). Datos -> `0001` solo crea dos tablas nuevas sin dependientes: `migrate cuentas zero` las borra sin tocar nada existente. Nada de lo existente cambia de esquema.
**Costo**: sin componentes de nube nuevos; Turnstile es gratis; unos pocos correos al mes por Resend (tope 50/día).
**Observabilidad**: eventos consultables en el admin; `logger.error` con el tope global y los fallos de Resend se ven en Sentry. SLO: sin objetivo propio (flujo de baja frecuencia).

## 8. Riesgos abiertos y decisiones del dueño

Nada bloquea el diseño. Pendientes que sí necesitan al dueño:
1. **Correos de las cuentas existentes** (acción, §6.4): hasta que se carguen, la función no ayuda a nadie.
2. **¿Turnstile también en el login?** Se leyó "turnstile obligatorio" como el de la recuperación. Ponerlo en `/admin/login/` exige un `AuthenticationForm` propio que convive con Axes, y si fallara cerrado una caída de Cloudflare dejaría sin entrar a todo el personal. No se incluye; si lo quiere, es otra tarea con su propia decisión.
3. **Superusuarios y operador recuperables por correo** (como se pidió): quien controle ese buzón controla todo el sistema. Se recomienda `RECUPERACION_AVISO_ADMIN` y que esas cuentas usen un correo con verificación en dos pasos; WP-27 (2FA) cierra el riesgo de fondo.
4. **Mínimo de contraseña**: `MinimumLengthValidator` está en 8; ASVS V2.1.1 pide 12. Cambiarlo toca todas las altas y pruebas; se deja fuera salvo que lo decida.

Riesgos técnicos aceptados: hilo daemon que se pierde si Render recicla el worker (el usuario vuelve a pedir tras 60 s); Resend caído = nadie se recupera (camino manual de §6); `FileBasedCache` no se usa para nada crítico aquí a propósito.

VERDICT: ARCH-READY
