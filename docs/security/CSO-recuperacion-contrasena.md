Decision: APPROVED

# CSO — Recuperación de contraseña por código al correo (backoffice)

Fecha: 2026-10-25 · Rama: feat/marca-sun-baja (worktree qa, cambios sin commit) · Diseño: `docs/architecture/ARCH-recuperacion-contrasena-backoffice.md`
verdict_quality: substantive (cada punto del checklist cita archivo:línea o salida de prueba; los hallazgos son falsables).
Alcance: solo lectura. No se editó código ni pruebas. `gate-check`/Beads no se ejecutaron (la instrucción prohíbe Beads): el cierre de `gate:ship` queda a cargo del invocador.

## Resultado

0 Critical, 0 Major, 5 Minor, 4 Nit. Ninguno es explotable para tomar una cuenta ni para enumerar cuentas por la respuesta HTTP. Los controles del diseño están en el código.

## Pruebas ejecutadas

| Suite | Resultado |
|---|---|
| SQLite: `apps.cuentas apps.bookings.tests_captcha apps.notifications.tests_correo_cuentas` | 183 tests, OK (3 omitidas: las carreras, que exigen Postgres) |
| Postgres 5434 (rol `ci_rls`, sin BYPASSRLS): `apps.cuentas apps.bookings.tests_captcha apps.tenancy.tests_rls` | 174 tests, 1 FAIL (H-01, prueba inestable; no es un defecto del producto). Las carreras (`tests_carreras.py`) y el guardarraíl RLS pasaron. |
| Sondeo manual: `GET /admin/recuperar/` anónimo | 200; `Cache-Control: no-store, private`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`; el HTML no contiene nombres de modelos del menú (Reserva, Finanzas, Calendario, Usuarios, Embarcación). |

## Checklist

| # | Punto | Estado | Evidencia |
|---|---|---|---|
| 1 | Código: `secrets`, 6 dígitos, solo HMAC | PASS | `seguridad.py:45` `secrets.randbelow(10**6)`; `:56-57` HMAC-SHA256 con `SECRET_KEY` sobre `[pk, password, codigo]` en JSON; `models.py:20` solo `codigo_hash`; `Secreto` (`seguridad.py:18-36`) imprime `<Secreto>` en repr/str/format |
| 1 | `compare_digest`, vence, un uso, intentos atómicos | PASS | `seguridad.py:78`; vence `servicio.py:164`; intento con UPDATE condicional `servicio.py:263-266`; consumo con UPDATE `:281-283` (`== 1`); `select_for_update` `:153` y `:277` |
| 1 | Atado a la contraseña vigente; uno nuevo invalida el anterior | PASS | `seguridad.py:56` incluye `usuario.password`; `servicio.py:159-168` `update_or_create` reinicia hash, vencimiento, intentos y consumo. Pruebas: `test_contrasena_cambiada_por_otra_via_invalida_el_codigo`, `test_tras_el_cooldown_si_se_envia_otro_y_el_viejo_ya_no_verifica` |
| 2 | Misma respuesta y mismo HTTP en los 4 casos | PASS | `views.py:97-105` el paso 1 siempre devuelve la misma página; `servicio.py:129-148` cuenta inexistente, inactiva, inutilizable, ambigua y limitada salen sin señal. Prueba `test_la_respuesta_es_la_misma_para_existente_inexistente_inactiva_e_inutilizable` (ver H-01) |
| 2 | Oráculo del middleware | PASS | `views.py:97-100` y `:136-140` atrapan `Exception` y registran solo la clase; `middleware_errores.py` (`process_exception`, que llama a `logger.exception`) no se alcanza desde estas rutas |
| 2 | Tiempo homogéneo | PASS con reserva | Envío en hilo (`envio.py:44-52`), HMAC de relleno `servicio.py:146` y `:257`. No hay medición; ver H-09 |
| 2 | Orden de validación de contraseña | PASS | `servicio.py:249-254` valida antes de tocar el código y con un candidato falso si no hay cuenta; no gasta intento |
| 3 | Turnstile obligatorio, falla cerrada | PASS | `captcha.py:89` sin secreto/acción/hostname; `:93-94` token vacío o >2048; `:97-99` red caída; `:101-103` status≠200; `:105-109` JSON inválido; `:111` `success is not True`; `:113-118` `action` y `hostname` iguales. Ambos pasos: `views.py:88` y `:126` |
| 3 | `verificar_turnstile` del checkout sin cambio | PASS | El diff solo extrae `_consultar_siteverify` (mismos parámetros, `TIMEOUT_SEGUNDOS`); `captcha.py:62-74` conserva el comportamiento abierto. Pruebas `test_sin_secret_el_checkout_funciona_igual_que_antes`, `test_si_cloudflare_no_responde_deja_pasar` |
| 3 | Secreto no logueado, timeout, sin SSRF | PASS | URL constante `captcha.py:22`; timeout 5 s `:26`; los logs llevan solo clase/código HTTP; prueba `test_el_log_de_error_no_lleva_el_token`. `hostname` sale de `request.get_host()` (`views.py:62`), validado contra `ALLOWED_HOSTS` (`production.py:13`) |
| 4 | Límites por correo, IP y global en BD | PASS | Correo `servicio.py:67-78` (cooldown 60 s, 3/h, 10/día); IP `:55-64` y `:192-201` (429); global `:81-89`; contados en BD, repetidos bajo candado `:154` |
| 4 | IP no falsificable por `X-Forwarded-For` | PASS | `views.py:82` usa `ip_del_cliente`; `ip_cliente.py:ip_del_cliente` recorre el header de derecha a izquierda saltando proxies propios. Límite documentado en ese módulo (Worker/WARP de Cloudflare); `production.py:47` `TRUSTED_PROXY_COUNT` por defecto 1 |
| 4 | Sin bloqueo de la cuenta de la víctima | PASS con reserva | Nada toca `is_active`/Axes al pedir recuperación; lo rechazado por límite no cuenta (`servicio.py:34`). El flujo de recuperación sí se puede degradar: H-03 |
| 5 | Tras el cambio | PASS | Validadores `servicio.py:251`; sesiones `:222-230` y `:287` (además Django invalida por hash de sesión); Axes `:288`; aviso `:290-293` en `on_commit`; no inicia sesión (`views.py:144` redirige al login) |
| 5 | Sin `bcc`, plantillas escapadas | PASS | `bcc` solo en funciones previas (`services.py:246,320,538,589,814`), ninguno en `services.py` desde la línea 1022; destino = `usuario.email` guardado (`servicio.py:171`); JSON a Resend, sin cabeceras construibles. `_html(usuario)` y `escape(digitos)` (`services.py` `_cuerpo_codigo_html`); `grep safe\|mark_safe\|autoescape` en `apps/cuentas` y `templates/cuentas` vacío |
| 6 | Web | PASS | CSRF por defecto (`base.py:430`), prueba `test_un_post_sin_csrf_es_403`; `require_http_methods(['GET','POST'])`, `never_cache`, `sensitive_post_parameters()` (`views.py:70-73`); código solo por POST (`recuperar_codigo.html` `method="post"`); `Referrer-Policy: same-origin`; sin CSP configurada (no hay nada que romper con `challenges.cloudflare.com`); autocomplete `one-time-code`/`new-password` (`forms.py:18-33`); `next` no se lee en ninguna de las dos vistas |
| 7 | Multi-tenant/RLS | PASS | Modelos sin empresa (`models.py:1-4`); `auth_user` no lleva RLS (`admin_mixins.py:76-79`), así que la consulta anónima por correo no depende de alcance; `tests_rls` pasó en Postgres sin BYPASSRLS. `EventoRecuperacionAdmin` (`admin.py:25-39`): solo operador ve; add/change/delete en `False` aun para superusuario; `CodigoRecuperacion` no se registra |
| 8 | Alta de usuarios (T10) | PASS | Formulario: correo obligatorio y único (`bookings/forms.py:27-32`, `:91-95`); servicio: opcional pero válido y único (`usuarios.py:54-66`); edición: solo valida unicidad si el correo cambió (`admin.py:1755-1763`), no rompe cuentas viejas. Auditor: correo enmascarado `a***@dominio` (`auditar_correos_cuentas.py:enmascarar`), prueba `test_nunca_imprime_una_direccion_completa` |
| 9 | Logs/Sentry | PASS | `grep -rn --exclude='tests_*.py' "logger.exception\|exc_info\|print(" apps/cuentas` vacío (ejecutado, sin salida). Solo `logger.error(... type(exc).__name__)` (`views.py:100,139`, `servicio.py:97`, `envio.py:30`) |
| 10 | Pruebas negativas | PASS | Enumeración (`tests_vistas.py:190`, `tests_confirmar.py:195-210`), intentos (`:98-120`, `:270`), expiración (`:122`), reutilización (`:65`), carreras con hilos (`tests_carreras.py:61,74,82`, corren en Postgres), Turnstile fail-closed (`tests_captcha.py:102-200`), código ausente de logs/respuestas/eventos (`tests_vistas.py:327,340`) |
| 11 | Config | PASS con reserva | Defaults seguros en `base.py` (sin `TURNSTILE_SITE_KEY` o sin Resend → 503, `views.py:43-47`); ningún secreto en código. Falta declarar las variables nuevas en `render.yaml`: H-05 |
| 12 | Residuales aceptados | Confirmados | Ver sección al final |

## Hallazgos

| ID | Sev | Archivo:línea | Mecanismo → consecuencia | Arreglo |
|---|---|---|---|---|
| H-01 | Minor | `apps/cuentas/tests_vistas.py:197-207` | La prueba compara `_cabeceras(respuesta)` completas entre cuatro respuestas; esas cabeceras incluyen `Expires` (con segundos). Observado en la corrida de Postgres: `Expires: ...23:27:10 GMT` contra `...23:27:09 GMT` → FAIL cuando la serie de peticiones cruza un segundo. CI intermitente en la prueba de enumeración, la que más importa. | Excluir `Expires`, `Last-Modified`, `Date` y `Set-Cookie` de la comparación en `_cabeceras`, o congelar el reloj con `freezegun`/`mock` de `timezone.now` y `http_date`. |
| H-02 | Minor | `apps/cuentas/servicio.py:81-89` | Una vez alcanzado el tope diario, cada solicitud que pasa Turnstile y los límites de IP/correo ejecuta `logger.error`. Con `SENTRY_DSN` (`production.py:101-110`) cada una es un evento. Un atacante con varias IPs puede agotar la cuota gratuita (5 000/mes, según el comentario de `production.py`) y tapar las alertas del webhook de Stripe. | Registrar el error solo en la transición: no registrar si ya existe un `EventoRecuperacion` con `resultado='limite_global'` en las últimas 24 h; o bajar a `warning`. |
| H-03 | Minor | `servicio.py:67-78`, `:159-168`, `:263-266` | Quien conoce un correo de cuenta y resuelve Turnstile puede (a) consumir las 3 solicitudes/hora de ese correo, tras lo cual la víctima pide y no recibe nada, (b) pasados 60 s, sobrescribir el código vigente de la víctima, y (c) gastar sus 5 intentos con contraseñas válidas. Consecuencia: negación de la recuperación por una hora o un día, no del inicio de sesión ni toma de cuenta. El diseño lo acepta como coste del límite por correo; el texto "sin DoS inverso" solo vale para el login. Además, con ≥5 correos conocidos (10/día cada uno) se llega al tope global de 50 y se cierra la recuperación para todos hasta el día siguiente. | Aceptar y documentarlo en CLAUDE.md ("recuperación degradable; plan B: el jefe cambia la contraseña / `changepassword`", ya descrito). Opcional: alertar (H-02 corregido) cuando un correo llega a `limite_correo` ≥ N veces/día. |
| H-04 | Minor | `servicio.py:41-46`, `:55-58`, `:192-196` | El límite por IP usa la dirección completa. Un cliente IPv6 con un /64 rota direcciones y evade los 10 solicitudes/h y 20 fallos/h por IP. No debilita el código (el techo real son los 5 intentos y 10 códigos/día por correo, ver H-06) pero sí el control anti-spam por IP y el 429. | En `_ip_valida`, para IPv6 devolver la red /64 (`ipaddress.ip_network(f'{ip}/64', strict=False)`) como clave; la columna es `GenericIPAddressField`, guardar la dirección y contar por prefijo. |
| H-05 | Minor | `render.yaml:171` (solo `TURNSTILE_SECRET_KEY`); `render.yaml:81-107` (crons) | El Blueprint no declara `TURNSTILE_SITE_KEY` ni `RECUPERACION_AVISO_ADMIN`, ni un cron mensual para `limpiar_eventos_recuperacion`. Consecuencia: tras un redeploy limpio la recuperación responde 503 hasta que alguien cree la variable a mano, y la bitácora no se purga (crece lento, limitado por los límites de IP). | Añadir ambas variables con `sync: false` y un cron `python manage.py limpiar_eventos_recuperacion --dias 90`. |
| H-06 | Nit | `base.py` `RECUPERACION_MAX_POR_CORREO_DIA=10` × `RECUPERACION_MAX_INTENTOS=5` | Presupuesto de adivinanza: 50 intentos/día/cuenta sobre 10^6 códigos = 5·10^-5 por día; sostenido un año ≈ 1,8 % para una cuenta, cada intento con Turnstile, contraseña válida y 10 correos/día a la víctima más aviso al cambiar. Riesgo bajo y observable, pero no nulo para jefes/operador. | Alertar si un correo agota intentos en ≥3 códigos distintos al día; o código de 8 dígitos (10^8) si se quiere margen. |
| H-07 | Nit | `views.py:135-137` | `datos = form.cleaned_data` guarda `codigo` y la contraseña en claro como variable local del frame de la vista. Si una excepción no atrapada ocurre después (render, mensajes), el SDK de Sentry adjunta variables locales por defecto (`production.py:104-117` no fija `include_local_variables=False`; `send_default_pii=False` no lo desactiva). El código es de un solo uso y vence en 10 min. | Pasar los valores directo (`confirmar_codigo(form.cleaned_data[...])`) y `del datos` antes de responder, o `include_local_variables=False` en `sentry_sdk.init`. |
| H-08 | Nit | `forms.py:18-19` | `RegexField(r'^\d{6}$')` acepta dígitos Unicode (p. ej. árabe-índicos) en Python 3. No son explotables (el HMAC se calcula sobre texto distinto y no coincide), pero gastan un intento y contradicen "6 dígitos". | Usar `[0-9]{6}` y `re.ASCII`. |
| H-09 | Nit | `servicio.py:150-173` frente a `:145-148`; `:261-297` frente a `:256-259` | El camino de cuenta real hace una transacción con `select_for_update`, `update_or_create`, dos inserciones y arranca un hilo; el de cuenta inexistente un HMAC y una inserción. La diferencia es de milisegundos y no está medida. Acotada por 10 solicitudes/h/IP y Turnstile (con H-04 se relaja). | Aceptado por el diseño; si se quiere cerrar, medir con 200 muestras por camino y, de haber diferencia, rellenar con una consulta dummy o un `sleep` jitter. |

Notas sin severidad:
- Duplicados de correo: no hay restricción única en BD, solo verificación al guardar (`usuarios.py:62-65`, `bookings/forms.py:91-95`, `bookings/admin.py:1755-1763`); una carrera crea dos cuentas con el mismo correo, y entonces ninguna se recupera (`ambigua`, falla cerrada). Aceptable.
- Un correo mal tecleado por el jefe al cargar la cuenta entrega los códigos a un tercero. No hay verificación de posesión del correo en el alta. Control operativo: la prueba con "una cuenta real" que pide CLAUDE.md, más el aviso `RECUPERACION_AVISO_ADMIN` en cada cambio.

## Residuales aceptados (punto 12)

- `UserAttributeSimilarityValidator` (`base.py:474`): con cuenta real el validador ve nombre/apellido/correo reales (`servicio.py:249`); quien adivine esos datos obtiene un rechazo distinto. Exige Turnstile + contraseña que cumpla los demás validadores; cada intento cuenta contra el límite de 20 fallos/h/IP. Riesgo bajo; confirmado.
- Mínimo de contraseña 8 (`MinimumLengthValidator` por defecto): ASVS v4 2.1.1 pide 12. Riesgo medio-bajo para cuentas con dinero; recomendado subir a 12 en `AUTH_PASSWORD_VALIDATORS` en un cambio aparte (afecta altas y cambios del admin).
- Superusuarios y operador recuperables por correo: quien controle el buzón controla la cuenta. Mitigado por el aviso en cada cambio, el correo de aviso al administrador y la sesión cerrada; el cierre real es 2FA, fuera de alcance. Riesgo medio, aceptado.

## Antes de publicar (operativo, no son hallazgos de código)

1. Poner `TURNSTILE_SITE_KEY` (el par del secreto) y agregar el hostname del backend al widget en Cloudflare; confirmar que `TURNSTILE_SECRET_KEY` existe en Render (`captcha.py:89`: sin ella la recuperación cierra, pero el checkout falla abierto).
2. Poner `RECUPERACION_AVISO_ADMIN` con el correo del dueño.
3. Cargar el correo de cada cuenta y correr `manage.py auditar_correos_cuentas` en el Shell de Render; probar con una cuenta real.

VERDICT: APPROVED
