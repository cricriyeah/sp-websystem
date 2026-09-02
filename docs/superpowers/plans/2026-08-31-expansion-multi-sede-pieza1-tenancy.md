# Expansión multi-sede — Pieza 1: Sede/Empresa + RLS + roles-por-empresa Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introducir `Sede` y `Empresa` como los dos niveles de tenancy del marketplace, retrofitear `empresa_id` en todos los modelos existentes de La Paz, aplicar aislamiento en tres capas (ORM + admin + RLS de Postgres), quitar `is_superuser` a los jefes reemplazándolo por rol-por-empresa + operador de plataforma, y mover Stripe (llaves + webhook + conciliación) a una cuenta por Empresa — todo sin romper la operación actual de La Paz.

**Architecture:** Nueva app `apps.tenancy` (`Sede`, `Empresa`, `MembresiaEmpresa`) de la que cuelga un FK `empresa` en cada modelo tenant-scoped existente (`fleet`, `bookings`). El primitivo de alcance vive en `apps/tenancy/scope.py` — `con_empresa(empresa)` / `como_operador_plataforma()` son los ÚNICOS lugares que fijan `SET LOCAL app.current_empresa_id` / `app.operador_plataforma` dentro de una `transaction.atomic()`. `EmpresaScopeMiddleware` envuelve **`__call__`** (no `process_view`: el render de las `TemplateResponse` del admin ocurre dentro de `BaseHandler._get_response`, que corre por debajo de `__call__` pero por encima de `process_view` — envolver solo `process_view` deja el render fuera de la transacción, ver Revisión 3). Dentro de `__call__`, la resolución de URL se hace a mano con `django.urls.resolve(request.path_info)` (antes de que Django la resuelva otra vez internamente) para saber si la ruta trae `empresa_slug`. Las políticas RLS leen esas variables como red de seguridad detrás del filtro normal del ORM/admin — en motores que no son Postgres (sqlite, tests locales) esa red no existe y el aislamiento depende solo del filtro del ORM, obligatorio en cada vista/queryset. `OperadorPlataforma` es un grupo de Django puro (no una fila de `MembresiaEmpresa`). Los roles pasan de `is_superuser` a `MembresiaEmpresa(rol=JEFE|VENDEDORA)` por Empresa + grupo `OperadorPlataforma` para quien cruza empresas; Stripe pasa de una llave global a una llave por `Empresa`, resuelta por petición (no mutando estado global del proceso), con un endpoint de webhook por empresa.

**Revisión 3 del File Map (tercera pasada del architecture-critic).** Las dos rondas previas corrigieron la resolución de alcance y la propiedad de cada pieza de datos. Esta ronda corrige seis fallas críticas y seis significativas más — la más grave: el mecanismo de `process_view` de la Revisión 2 fijaba el alcance y llamaba la vista dentro del `with`, pero **el admin de Django renderiza sus listados de forma perezosa, después de que `process_view` ya devolvió** — así que cada listado seguía viendo cero filas bajo RLS, el mismo bug que la Revisión 2 creía haber cerrado. Resumen de qué cambió:

1. El mecanismo pasa de `process_view` a envolver **`__call__`** completo (incluye el render perezoso del admin). Ver Architecture arriba y "Resolución de alcance" abajo.
2. El middleware no tenía ningún caso para rutas anónimas sin `empresa_slug` (`/healthz`, `/admin/login/`, estáticos) — con la regla anterior, cualquiera de esas devolvía 403 antes de correr: Render nunca pasa su propio healthcheck y nadie puede loguearse jamás. Ahora hay un tercer caso explícito: usuario anónimo → sin alcance, sin tocar ninguna tabla de tenancy.
3. `migrar_la_paz_a_empresa.py` solo movía cuentas `is_superuser=True`: las vendedoras (staff, sin superusuario) se quedaban sin `MembresiaEmpresa` y quedan bloqueadas con 403 en su primer login tras el corte. Y ningún jefe migrado quedaba en el grupo Django `Jefe` (solo con la fila de `MembresiaEmpresa`, que no da permisos). Corregido: el comando cubre ambos roles y ambas pertenencias.
4. Seis restricciones `unique=True` **globales** seguían de pie (`Tarifa` fuerza `pk=1`, `CupoDiario.fecha`, `TransportePrecio.zona`, `CodigoPromocional.codigo`, `Embarcacion.nombre`, `Vendedora.codigo`) — con eso, una segunda Empresa no puede tener su propia tarifa, su propio cupo del mismo día, ni su propio código "VERANO10". Ahora se listan explícitamente como parte del retrofit.
5. El rol de CI cambiaba `POSTGRES_USER`, que es el superusuario que el propio contenedor de Postgres crea al arrancar — renombrarlo no quita el superusuario, solo le cambia el nombre. Corregido: `POSTGRES_USER` se queda como está (es el bootstrap), se crea un rol nuevo sin privilegios aparte y **ese** es el que usa Django para correr los tests.
6. La bandera de no-reentrancia vivía en el objeto de conexión sin ninguna garantía de limpieza: con `CONN_MAX_AGE=0` (el default, no hay override en ningún `settings/*.py`) se cierra el socket pero Python no descarta el wrapper de conexión entre requests del mismo worker — una excepción a medio camino podía dejar la bandera pegada para **todas** las peticiones siguientes de ese worker. Ahora se restaura explícitamente en `finally` y además se resetea por la señal `request_started`.

Además, seis hallazgos significativos (**corregido en Revisión 4, N23: la Revisión 3 los llamaba "seis" y solo enumeraba cuatro** — los otros dos vivían implícitos en el File Map, sin marcar, y precisamente uno de ellos escondía el peor bug nuevo de la Revisión 4, ver N1 abajo): `Empresa.slug`/`activo`/`exclusiva` nunca se habían declarado como campos aunque todo el documento ya los usaba; a `CrearPagoView`/`EstadoReservaView`/`evaluar_codigo_promocional`/`aplicar_pago_exitoso` (segundo lookup) les faltaba el filtro `empresa=` explícito que el propio documento exige; `stripe_client.configurar_stripe` mutaba `stripe.api_key` como variable global de proceso (una condición de carrera esperando a que alguien active workers con hilos); el chequeo de arranque de llaves cruzadas pierde su razón de ser en cuanto las llaves se puedan teclear en el admin en caliente, no solo cargarse al arrancar; `notificar_reserva_pagada` pasa de llamarse dentro de la transacción a `transaction.on_commit(...)`; y `conciliar_pagos` pasa de un guard global de llaves a uno por Empresa.

**Revisión 4 del File Map (cuarta pasada del architecture-critic).** Verificó los seis críticos y seis significativos de la Revisión 3 contra el código real (línea por línea) y contra el texto del documento. Cinco de los seis críticos quedaron genuinamente cerrados. Pero encontró un patrón repetido: **un mecanismo se arregla en un lugar y su hermano se queda con el mismo bug** — y la propia corrección de la Revisión 3 (mover `notificar_reserva_pagada` a `transaction.on_commit`) reintrodujo exactamente el bug que la Revisión 3 acababa de matar en el admin (algo se resuelve en el scope de una transacción y se usa después de que ese scope ya cerró). Resumen de qué cambia en esta revisión:

1. **`SET LOCAL` no sobrevive al COMMIT.** Todo callback de `transaction.on_commit(...)` que toque la base corre **fuera** de cualquier `with scope.con_empresa(...)` que lo haya encolado — bajo RLS ve cero filas, no un error. Se agrega la sección "Quién corre fuera del alcance" (abajo) con la regla general y se corrige el hermano ya existente en `apps/bookings/signals.py` (el aviso de asignación), que hoy fallaría en silencio (su `except Exception` se traga el `RelatedObjectDoesNotExist`/el `.update()` de 0 filas) y **reenviaría el correo duplicado en cada edición de la reserva, para siempre**.
2. **La suite de tests existente no pasa CI tal como estaba planeada.** Con `FORCE ROW LEVEL SECURITY` y el rol de CI sin `BYPASSRLS` (Revisión 3, hallazgo crítico 5), cualquier `objects.create()`/`bulk_create()` fuera de un `con_empresa` — empezando por `apps/testing.py` — falla con violación de política. Se agrega `apps/testing.py` y el resto de archivos de test existentes al File Map.
3. **La expresión exacta de la política RLS lanza excepción, no cero filas, en la segunda transacción de cualquier conexión** (gotcha de Postgres: un GUC de sesión fijado una vez con `SET LOCAL` vuelve a cadena vacía al terminar la transacción, no a indefinido — `''::int` revienta). Corregido con `NULLIF(..., '')`.
4. **El checklist de producción pedía un rol de base sin superuser pero no resolvía quién es dueño de las tablas** — `ENABLE ROW LEVEL SECURITY`/`CREATE POLICY` exigen ownership. Se agrega un runbook explícito de creación de rol + GRANTs + verificación post-deploy de que RLS realmente está activo (riesgo silencioso: en Supabase el rol `postgres` trae `BYPASSRLS` por defecto).
5. **Dos call sites de dinero en `CrearPagoView` seguían sin `empresa=`** (precio de transporte y código promocional) — la lista de "4 call sites, ninguno cubierto por RLS" de la Revisión 3 en realidad tenía 13 sitios reales, faltaban 9. Se corrige la lista completa (ver tabla de call sites bajo "Fuera de Postgres" abajo) y se agregan filas al File Map para cada uno.
6. **Ningún `on_delete` estaba especificado en los FK `empresa` nuevos** (**Revisión 5, B9: son 11, no 8** — los 8 de `fleet` más `Reserva`/`CupoDiario`/`Vendedora` de `bookings`, que la Revisión 4 omitió del conteo aunque la sección "Tablas cubiertas por RLS" ya los listaba correctamente; corregido aquí para que quien convierta esto en tareas bite-sized no escriba 8 checkboxes y deje `Reserva` — el historial de dinero — con el `CASCADE` por defecto) — el default de Django es `CASCADE`; borrar una Empresa desde el admin borraría toda su flota, reservas e historial de dinero. Se fija `on_delete=PROTECT` en los once, coherente con la convención ya existente en el repo (`Vendedora.usuario`, `EmbarcacionNoDisponible.embarcacion`).

Hallazgos significativos adicionales de la Revisión 4, todos incorporados al File Map: el guard del singleton de `TarifaAdmin.has_add_permission` seguía sin escopear; `EmpresaScopedAdminMixin.save_model` no tenía semántica definida para el operador de plataforma (empresa `None` → `IntegrityError`, o pisa la empresa de una fila ajena al editar); `apps/fleet/management/commands/seed_extras.py` no estaba en el File Map y deja de ser idempotente tras el paso 3; `bookings_reservaextra`/`bookings_reservatransporte` quedaban fuera de la lista de tablas con RLS; los `PrimaryKeyRelatedField` del serializer de `Reserva` (`punto_encuentro`, `extras`) aceptan ids de otra Empresa; `Vendedora.por_codigo` (atribución de comisión por `?ref=`) resolvía sin `empresa=`; la ventana entre `migrate` y que un humano teclee las llaves de Stripe en el admin deja el checkout en 503; `Empresa.activo=False` apagaba también la conciliación de dinero ya cobrado (`conciliar_pagos` y el webhook), en vez de solo el catálogo público; `apps/bookings/panorama.py` no estaba en el File Map; no había validación de que las FK de una `Reserva` (`embarcacion`, `capitan`, `vendedora`, `codigo_promocional`, `punto_encuentro`) pertenezcan todas a la misma Empresa — RLS filtra filas, no valida referencias cruzadas que arme el operador de plataforma desde el admin.

**Revisión 5 del File Map (quinta pasada del architecture-critic).** Verificó los 24 puntos de la Revisión 4 contra el código real: 16 resueltos genuinamente, 3 parciales, 5 seguían rotos. El patrón de las cuatro rondas anteriores — "se arregla en un lugar, el hermano queda roto" — se repitió dos veces exactas, ambas ya corregidas arriba: **B1**, la corrección de N16 (Empresa pausada sigue reconciliando dinero) se hizo en las filas de `payments/views.py`/`conciliar_pagos.py` pero la sección "Resolución de alcance" §1 seguía diciendo lo contrario — ahora tiene dos resolutores explícitos, público vs. dinero; y **B7**, la lista de "13 call sites, ahora completa" de la Revisión 4 seguía incompleta — le faltaba el hermano directo de N13, el catálogo público de `fleet/views.py` que alimenta los ids que el serializer valida, más `bookings/views.py:184` (upsert de checkout por `checkout_id` sin `empresa=`, permite que un POST de la Empresa B reescriba una reserva de la A) y varios más — ahora son ~22 sitios, enumerados. Además: **B2**, el runbook de producción (N4) pedía dos roles de Postgres que `render.yaml` no tiene en el mismo pipeline de deploy — corregido a un solo rol dueño, protegido por `FORCE ROW LEVEL SECURITY` (ya en el plan, es lo mismo que hace que CI funcione hoy). **B3**, la migración de `stripe_client` (parte de S3/N-implícito) solo listaba los 4 sitios que *configuran* Stripe, no los 6 que *llaman* la API, y la sintaxis citada no existe en `stripe==15.4.0` — corregido con la lista completa, la forma snake_case real del SDK, `stripe_version` preservado, y la superficie de ~52 tests que necesitan re-parchear el client en vez del módulo. **B6**, el fix de N22 comparaba contra `'postgresql'` pero la matriz real de CI usa `'postgres'` — el `if` nunca disparaba y **todo `tests_rls.py` pasaba en verde sin haber probado RLS una sola vez**; corregido, más una aserción de guardia en el propio test que falla si el rol resulta tener `BYPASSRLS`. **B4**, N13 ofrecía `__init__` como alternativa a `get_fields()` para escopear los `PrimaryKeyRelatedField` del serializer, pero está roto en serializers anidados (deepcopy no re-ejecuta `__init__`) y la vista no pasaba `empresa` al contexto — corregido a solo `get_fields()` más el contexto completo. **B5**, N18 validaba `punto_encuentro` dentro de `Reserva.clean()`, pero ese campo no existe en `Reserva` — vive en `ReservaTransporte`, junto con `ReservaExtra.extras_item`, las dos asociaciones que de verdad deciden precio — corregido moviendo la validación a `clean()` de esos dos modelos y haciendo que `_sincronizar_extras` llame `full_clean()` (hoy no lo hace para `ReservaExtra`). El resto de hallazgos (B8-B17: hilos en tests de concurrencia, conteo de FK 8→11, índice de la política RLS, `MultipleObjectsReturned` mal ubicado, columna sin calificar en `EXISTS`, comparación de logout, MRO de `save_model`, llamador no listado, `checks.py` iterando solo activas) también están incorporados.

**Revisión 6 del File Map (sexta pasada del architecture-critic).** 13 de los 17 puntos de la Revisión 5 quedaron resueltos de verdad (verificado contra el SDK de Stripe instalado y el código real, incluidas las citas más finas: `stripe==15.4.0`, las 52 `mock.patch`, `models.py:356/373/848`). El patrón de "se arregla en un lugar, el hermano queda roto" volvió a aparecer, esta vez dos veces sobre correcciones de esta misma ronda: **N-A**, la corrección de B1 (dos resolutores público/dinero) dejó sin actualizar dos secciones hermanas ("Resolución de alcance" #4 y "Quién corre fuera del alcance" #3) que seguían diciendo que los comandos de management iteran solo `Empresa` activa, contradiciendo la fila de `conciliar_pagos.py` — corregido distinguiendo comandos de catálogo (pueden filtrar `activo=True`) de comandos de dinero (`.all()` siempre). **N-B**, nuevo: dos `ModelAdmin` (`CheckoutAbandonadoAdmin`, `AgendaAdmin`) sobreescriben `get_queryset` sin llamar `super()`, así que "heredan el mixin" no basta — son las dos pantallas con más PII de clientes. **N-C**, el runbook de un solo rol dueño (B2) no ejecuta en Postgres 15+/Supabase moderno tal como estaba escrito — `REASSIGN OWNED BY` no otorga `CREATE` sobre `public`; corregido con los `GRANT` que faltaban y el formato de usuario del pooler Supavisor. **N-D**, la forma exacta del SDK de Stripe tenía dos imprecisiones más: el método es `update`, no `modify`, y `idempotency_key` va en `options`, no en `params` — sin esto se pierde la protección de doble cobro/doble reembolso. **N-E**, la regla de no-reentrancia idempotente podía anular el re-scope del callback de `on_commit` (reintroduciendo N1) si la restauración de la bandera ocurre fuera del `atomic()` — fijado el orden exacto. El resto (N-F a N-J) completa la lista de call sites por tercera vez, enumera llamadores de firmas que cambiaron, y corrige nits de traducción de errores/contrato de objetos sin guardar.

**Revisión 7 del File Map (séptima pasada del architecture-critic).** Los 10 puntos de la Revisión 6 quedaron genuinamente resueltos — el critic verificó incluso los más finos (dirección del orden `finally`/`on_commit` en Django 6.0.8, los `GRANT` de Postgres 15+/Supabase, la firma exacta del SDK de Stripe instalado) y confirmó que la Revisión 6 acertó en los tres. Encontró un hallazgo **crítico real y bloqueante, no un nit**: **`auth.User`/`auth.Group` (ya re-registrados en `bookings/admin.py`) no tenían ninguna fila en el plan** — con los jefes ya sin `is_superuser`, si el grupo `Jefe` conserva permisos sobre `auth.user` (lectura ambigua de "CRUD completo operativo" en `setup_roles.py`), un jefe de la Empresa A puede ver/editar/resetear la contraseña de cualquier usuario del sistema, incluidos jefes de otras Empresas y el operador de plataforma — escalada de privilegios directa que RLS no tapa porque `auth_user` no lleva `empresa_id`. Se consultó al dueño del negocio: decidió que el jefe **conserva** autonomía para dar de alta vendedoras (no exclusivo del operador de plataforma), a cambio de un admin escopeado — nuevas filas `apps/tenancy/admin.py` (`EmpresaScopedUserAdminMixin`) y la acción de alta de un solo paso en `apps/bookings/admin.py`. El resto de hallazgos de la Revisión 7 (queryset sin filtro en `conciliar_pagos.py`, el receptor de `request_started` pisando el guard de no-reentrancia dentro de una transacción de test, una fila de `bookings/admin.py` con un `|` sobrante que le cortaba contenido al renderizar, siete llamadores más sin enumerar, y la desviación de ADR-002 sobre almacenamiento de llaves de Stripe) están todos incorporados.

---

### Resolución de alcance (quién fija `app.current_empresa_id`, y cuándo)

Un único módulo, `apps/tenancy/scope.py`, con tres consumidores — ninguno vuelve a derivar esto por su cuenta. **Revisión 6 (N-J):** dentro de ese módulo, la resolución por slug (punto 1) vive en **dos funciones**, no una — ver el desglose ahí; los otros dos consumidores (puntos 2 y 4) no resuelven por slug y no les aplica esa distinción.

1. **Rutas públicas, siempre con `empresa_slug` en la URL.** Dos resolutores, no uno — **corregido en Revisión 5 (B1)**: la Revisión 4 corrigió `StripeWebhookView`/`conciliar_pagos` para que una Empresa pausada (`activo=False`) siguiera reconciliando dinero (N16), pero esta sección seguía diciendo que *todas* las rutas públicas, webhook incluido, devuelven 404 con `activo=False` — quien implementara esta sección tal cual re-rompía N16 en el primer archivo que la siguiera al pie de la letra.
   - **Catálogo/checkout** (`apps/fleet`, `apps/bookings`, `CrearPagoView`/`EstadoReservaView`/`ValidarCodigoPromocionalView`): `scope.resolver_empresa_publica(slug)` — 404 si el slug no existe **o** `activo=False`. Es dinero *por cobrar*; una Empresa pausada no debe vender.
   - **Dinero ya cobrado** (`StripeWebhookView`, `conciliar_pagos.py`): `scope.resolver_empresa_de_dinero(slug)` — 404 **solo** si el slug no existe; `activo=False` no importa. Ambos viven en `scope.py`, comparten la resolución de `Empresa` por slug, difieren solo en el chequeo de `activo`.
   
   La vista lee `self.kwargs['empresa_slug']`, llama al resolutor que le toca, y envuelve **su propio cuerpo** en `with scope.con_empresa(empresa):`. `EmpresaScopeMiddleware` detecta esta ruta (ver #3 abajo) y no hace nada — deja pasar la petición sin envolverla, la vista se envuelve sola.
2. **Backoffice (admin) con usuario autenticado, sin `empresa_slug` en la URL**: `EmpresaScopeMiddleware.__call__` resuelve `scope.resolver_membresia_o_403(request.user)` (o detecta operador de plataforma) y hace `with scope.con_empresa(empresa): return self.get_response(request)` (o `como_operador_plataforma()`). Como esto envuelve **todo** `get_response`, no solo la llamada a la vista, incluye el render perezoso de `TemplateResponse` que usa el admin — el bug de la Revisión 2.
3. **Usuario anónimo, cualquier ruta sin `empresa_slug`** (`/healthz`, `/admin/login/`, `/admin/logout/`, estáticos): el middleware **no** resuelve alcance — llama `self.get_response(request)` directo, sin `with`. Ninguna tabla de tenancy se consulta para servir estas rutas. Sin este caso, `resolver_membresia_o_403(AnonymousUser)` devolvería `PermissionDenied` antes de que nadie pueda siquiera ver el formulario de login, y el healthcheck de Render (`render.yaml`, `healthCheckPath: /healthz`) nunca pasaría.
4. **Comandos de management y migraciones de datos**: iteran `Empresa` y envuelven cada pasada en `with scope.con_empresa(empresa):` explícito, de forma secuencial, no anidada. **Revisión 6 (N-A):** no todos iteran lo mismo — los de catálogo/operación (`revisar_cupo`, `limpiar_checkouts_abandonados`, `seed_extras`) pueden filtrar `Empresa.objects.filter(activo=True)`; los de dinero (`conciliar_pagos`, el chequeo de arranque de `checks.py`) iteran **`Empresa.objects.all()`, nunca solo `activo=True`** — una Empresa pausada sigue teniendo dinero real por reconciliar (N16). Esta distinción no es opcional por comando, ver fila de cada uno. `conciliar_pagos.py` **no** es consumidor de ningún resolutor por slug (punto 1 arriba) — no resuelve por URL, itera la tabla directamente; se corrige aquí la clasificación errónea de la Revisión 5.

**Mecanismo exacto del middleware** (`apps/tenancy/middleware.py`, `__call__`, no `process_view`):

```
match = intentar_resolver(request.path_info)  # django.urls.resolve, atrapa Resolver404 → deja pasar sin envolver
if match is None or 'empresa_slug' in match.kwargs:
    return self.get_response(request)          # caso 1: ruta pública o no reconocida, sin tocar nada
if request.user.is_anonymous or match.view_name == 'admin:logout':
    return self.get_response(request)           # caso 3: anónimo o cerrando sesión, sin alcance
empresa_o_operador = scope.resolver_membresia_o_403(request.user)  # caso 2
with empresa_o_operador:
    return self.get_response(request)
```

**Revisión 4:** `/admin/logout/` se agrega explícitamente al caso 3. Sin esto, un usuario autenticado con 0 o >1 `MembresiaEmpresa` recibe `PermissionDenied` en **toda** ruta del admin, incluido logout — queda atrapado en el sitio sin poder cerrar sesión salvo borrando cookies a mano. **Revisión 5 (B14):** comparación por `match.view_name` (del `django.urls.resolve()` que el middleware ya hizo dos líneas arriba), no por `request.path_info == reverse('admin:logout')` — `reverse()` incluye `SCRIPT_NAME`, `path_info` no; coinciden hoy porque gunicorn sirve desde la raíz, pero `view_name` es gratis (ya está resuelto) y a prueba de que eso cambie.

`django.urls.resolve()` re-resuelve la URL una segunda vez (Django la resuelve otra vez, internamente, al despachar la vista) — costo aceptado, es una resolución de patrón cacheada, no una consulta a la base. Este archivo asume que no hay `i18n_patterns` ni middleware que reescriba `request.path_info` antes de aquí (cierto hoy — confirmar si se agrega alguno después).

**Resolución de membresía — una sola forma de fallar.** `scope.resolver_membresia_o_403(user)`: si el usuario es del grupo `OperadorPlataforma`, devuelve `como_operador_plataforma()`. Si tiene exactamente una `MembresiaEmpresa`, devuelve `con_empresa(esa_empresa)`. Si tiene cero o más de una, lanza `PermissionDenied` — un solo tipo de excepción, un solo lugar. (Más de una membresía no ocurre en v1 — el dueño confirmó rol de jefe solo por Empresa — así que ese caso es guardia de sanidad, no flujo soportado.)

**No-reentrancia con restauración, no solo bloqueo.** `con_empresa`/`como_operador_plataforma` llevan una bandera en el objeto de conexión (`connection.alcance_actual`). Entrar con un valor **distinto** al ya fijado lanza `RuntimeError`; entrar con el mismo valor es no-op idempotente. Al salir (`__exit__`, **incluida la rama de excepción**, vía `finally`), la bandera se **restaura al valor anterior** (no simplemente se limpia) — así un bloque interior que reentra con el mismo valor no le borra la bandera al bloque exterior que lo llamó. **Revisión 6 (N-E), orden crítico entre este `finally` y el `with transaction.atomic()`:** el `finally` que restaura la bandera vive **dentro** del `with transaction.atomic()` de `con_empresa` (es decir, `con_empresa` es `atomic() + try/finally` anidado, no `try/finally` envolviendo a `atomic()`) — porque Django ejecuta los callbacks de `transaction.on_commit(...)` dentro del `finally` de `Atomic.__exit__`, en el momento del COMMIT real. Si la bandera se restaurara **después** de salir del `atomic()` (por fuera), un callback de `on_commit` que reabre `con_empresa(la_misma_empresa)` (regla de "Quién corre fuera del alcance" #1) encontraría la bandera **todavía puesta** en esa empresa — tomaría la rama no-op idempotente, no emitiría `SET LOCAL` en la transacción nueva del callback, y bajo RLS el callback vería cero filas: exactamente el bug de N1, reintroducido por el mecanismo que lo corrige. El test de `tests_scope.py` que exige "un callback ve `connection.alcance_actual` limpio al ejecutarse" depende de este orden. Además, `apps/tenancy/apps.py` conecta un receptor a `django.core.signals.request_started` que fuerza `connection.alcance_actual = None` al inicio de cada request — red de seguridad final: si algo deja la bandera pegada (una excepción fuera de cualquier `with`, un bug), la siguiente petición del mismo worker arranca limpia en vez de heredar un `RuntimeError` permanente hasta que alguien reinicie el proceso. **Revisión 7 (N7-C) — precisión obligatoria sobre qué restaura este mecanismo:** la restauración de `con_empresa`/`como_operador_plataforma` es de la **bandera Python**, no del `SET LOCAL` de Postgres — un `SET LOCAL` emitido dentro de un `con_empresa` anidado (savepoint) sobrevive a `RELEASE SAVEPOINT` (la salida normal), y lo único que impide que eso corrompa el alcance del bloque exterior es el `RuntimeError` de no-reentrancia con valor distinto: **ese guard sostiene la garantía, no es una simple sanidad**. Por eso el receptor de `request_started` debe llevar `if not connection.in_atomic_block:` — `django.test.Client` dispara esa señal en cada `self.client.post(...)` (`django/test/client.py`), y sin la condición, un test que abre `con_empresa(A)` en `_pre_setup` (fila de `apps/testing.py`) y luego hace una petición a una ruta de la Empresa B vería la bandera borrada a mitad de su propia transacción — `con_empresa(B)` ya no lanzaría `RuntimeError`, emitiría `SET LOCAL = B` en un savepoint, y al salir por la vía normal el GUC se quedaría en B para el resto del test, con las aserciones del test viendo filas de B en silencio: el mismo tipo de fallo que B6 (el arnés que prueba el aislamiento es el que lo pierde, en verde). En producción, `request_started` siempre ocurre en autocommit (fuera de cualquier `con_empresa`), así que la condición no le quita nada a la red de seguridad real.

**Fuera de Postgres (sqlite, local/tests por default).** `con_empresa`/`como_operador_plataforma` siempre abren `transaction.atomic()` (portable), pero el `SET LOCAL` se salta con el mismo criterio que `bloquear_cupo_del_dia` (`if connection.vendor != 'postgresql': return`). En sqlite no hay RLS: el aislamiento depende **enteramente** del filtro `empresa=` explícito en cada queryset. **Revisión 4:** la Revisión 3 afirmaba que esta lista tenía 4 call sites y estaba completa; en realidad tenía 13, faltaban 9 (verificado con `grep` exhaustivo de todo `.objects.` fuera de tests). **Revisión 5 (B7): la lista de 13 de la Revisión 4 seguía sin estar completa** — barrido exhaustivo de `.objects.`/`get_object_or_404` fuera de tests y migraciones encontró ~9 sitios más, el más grave el hermano directo de N13. Lista completa, cada uno con su fila en el File Map:

- `CrearPagoView.get_object_or_404(Reserva, pk=...)` y su lookup de `TransportePrecio`/`CodigoPromocional` (N5, N6)
- `EstadoReservaView` por `checkout_id`
- `evaluar_codigo_promocional` (`bookings/models.py:356`) — el `.get()` con `empresa=` explícito
- `validar_codigo_promocional_en_pago` (`bookings/models.py:373`) — N6, ver también corrección de manejo de excepción abajo
- el segundo lookup de `aplicar_pago_exitoso` por `stripe_payment_intent_id`
- `disponibilidad_por_fecha`/`proxima_fecha_disponible`/`cupo_maximo_del_dia`/`Reserva._validar_una_salida_por_dia`/`CupoDisponibleView` (N8)
- `Vendedora.por_codigo` (N14)
- los `PrimaryKeyRelatedField` de `punto_encuentro`/`extras` en el serializer (N13)
- `bookings/panorama.py` (N17)
- **`apps/fleet/views.py:55/58/61`** — `ExtrasItem.objects.filter(activo=True)`, `TransportePrecio.objects.filter(activo=True)`, `PuntoEncuentro.objects.filter(activo=True)`: el **catálogo público**, la fuente exacta de los ids que N13 blinda en el serializer. Sin `empresa=` explícito aquí, N13 protege la entrada pero el catálogo mismo ya mezcló Empresas. Ver fila de `fleet/views.py` abajo.
- **`apps/bookings/views.py:184`**, en `_pendiente_de` — `Reserva.objects.filter(checkout_id=..., estado=PENDIENTE_PAGO).first()` decide qué fila reescribe el upsert del checkout. Sin `empresa=`, un POST a la ruta de la Empresa B con un `checkout_id` que coincide con una reserva de la A reescribe (y reasigna) la reserva de A.
- **`apps/bookings/admin.py:148`**, `reservas_nuevas_view` — vista custom registrada vía `get_urls()`, no pasa por `get_queryset` así que `EmpresaScopedAdminMixin` no la toca; se sondea cada 30s desde `reservas-nuevas.js`. Gana `empresa=scope.empresa_actual(request)` explícito.
- `revisar_cupo.py`/`limpiar_checkouts_abandonados.py` — sus filas solo decían "envuelve en `con_empresa`"; en sqlite eso no aísla nada por sí solo (la regla del propio documento). Ganan también el filtro `empresa=` explícito en sus querysets internos, no solo el `with`.
- **Revisión 6 (N-F), tercera pasada de este barrido:** `bookings/models.py:264`, `evaluar_cupo` — `Reserva.objects.filter(fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO)`, el queryset central del cupo (lo llaman `/api/cupo/` y `validar_cupo_diario`), ausente de la enumeración de N8 aunque ya está cubierto por la fila de `bookings/models.py`.
- `fleet/models.py:352` y `:355`, `capacidades_disponibles`/`capacidades_por_fecha` — `Embarcacion.objects.filter(activa=True)` y `EmbarcacionNoDisponible.objects.filter(...)`, la otra mitad del motor de cupo: sin `empresa=` explícito, en sqlite las pangas de la Empresa B cuentan como capacidad de la A.
- `bookings/admin.py:298`, acción "Marcar como venta mía" — `Vendedora.objects.filter(usuario=request.user, activo=True).first()` gana `empresa=scope.empresa_actual(request)`; sin esto, bajo RLS un operador de plataforma o un usuario cuya `Vendedora` es de otra Empresa ejecuta la acción y `.first()` devuelve `None` con un mensaje de error engañoso en vez de explicar por qué.
- **Revisión 7 (N7-B):** `conciliar_pagos.py:47` — `Reserva.objects.filter(estado=PENDIENTE_PAGO, ...)` gana `empresa=empresa`; era el único de los tres comandos de management sin el filtro explícito en su queryset, pese a que su fila ya pedía el `with`/guard por Empresa.

Ninguno cubierto "porque ya lo cubre RLS".

**Accesores nombrados**: `scope.empresa_actual(request)` y `scope.es_operador_plataforma(user)`. `EmpresaScopedAdminMixin.get_queryset`, `finance/views.py` y el `permission` lambda de "Finanzas" los llaman; ninguno vuelve a consultar `MembresiaEmpresa`/grupos por su cuenta.

### Operador de plataforma: no es una `MembresiaEmpresa`

`OperadorPlataforma` es **solo** un grupo de Django, nunca una fila de `MembresiaEmpresa` — el operador no pertenece a una sola Empresa. `MembresiaEmpresa.rol` tiene **dos** valores, `JEFE` y `VENDEDORA` (no solo `JEFE` — una vendedora también necesita una fila para que `resolver_membresia_o_403` no la rechace); los permisos Django (qué puede hacer) siguen viniendo de los grupos `Jefe`/`Vendedora`/`OperadorPlataforma` de `setup_roles.py`, el filtrado por fila (qué Empresa ve) lo deciden `EmpresaScopedAdminMixin` + RLS.

### Quién corre fuera del alcance (Revisión 4)

Cuatro sitios ejecutan código fuera de cualquier `with scope.con_empresa(...)` activo, y cada uno necesita su propia respuesta — no basta con envolver el request:

1. **Callbacks de `transaction.on_commit(...)`.** `SET LOCAL` vive dentro de la transacción; al hacer COMMIT, Django ejecuta el callback **después**, en una transacción nueva (o sin ninguna) sin `app.current_empresa_id` fijado. Bajo RLS eso es cero filas, no un error — el bug más peligroso porque no truena, solo calla. **Regla:** todo callback de `on_commit` que toque la base debe capturar `empresa_id` (el entero, no el objeto `Reserva`/`Empresa` con FKs perezosos) antes de encolarse, y reabrir su propio `with scope.con_empresa(Empresa.objects.get(pk=empresa_id)):` al ejecutarse — o, si el dato ya está disponible antes del commit, materializarlo (p. ej. serializar los extras/transporte a un dict) y pasarlo al callback en vez de volver a consultarlo. Aplica a `notificar_reserva_pagada` (fila de `payments/services.py`) y al hermano ya existente en `apps/bookings/signals.py` (fila nueva abajo).
2. **Señales (`post_save`, etc.).** Mismo problema si la señal dispara su propio `on_commit` (caso de `apps/bookings/signals.py`) o si corre síncrona pero fuera del `with` que originó el save (no es el caso hoy — el guardado de `Reserva` siempre ocurre dentro del `con_empresa` de la vista — pero cualquier señal nueva debe verificarlo explícitamente).
3. **Comandos de management.** Ya resuelto por diseño: iteran `Empresa` (consulta sin alcance, tabla sin RLS) y envuelven cada pasada en su propio `con_empresa(empresa)` — ver fila de cada comando en el File Map. **Revisión 6 (N-A):** el filtro de esa consulta no es uniforme — `activo=True` para catálogo/operación, `.objects.all()` para dinero (ver "Resolución de alcance" #4 arriba); esta sección decía `filter(activo=True)` sin distinguir, contradiciendo la fila de `conciliar_pagos.py`. Este es el único de los cuatro que ya estaba bien cubierto **en mecanismo** antes de la Revisión 4 — el filtro exacto se corrigió recién en la Revisión 6.
4. **El test runner.** Cada test que crea filas de modelos tenant-scoped (`ExtrasItem`, `Embarcacion`, `Reserva`, ...) fuera de un `con_empresa` explícito falla bajo `FORCE ROW LEVEL SECURITY` con el rol de CI sin `BYPASSRLS` (Revisión 3, hallazgo crítico 5). Ver fila de `apps/testing.py` y la fila consolidada de tests existentes en el File Map — **superficie de trabajo comparable al retrofit de modelos, no un ajuste menor**.
5. **Hilos de trabajo dentro de un test (Revisión 5, B8).** `apps/bookings/tests_concurrencia.py` (líneas 105-120) lanza dos `threading.Thread`, cada uno con su **propia conexión** de base de datos (comentario explícito en el código), para probar la carrera de `aplicar_pago_exitoso` bajo `select_for_update`. `SET LOCAL` es por conexión: si `ApiTestCase` abre `con_empresa` en `_pre_setup` (punto 4 arriba) sobre la conexión principal, los hilos hijos nunca ven ese alcance — bajo RLS, `aplicar_pago_exitoso` vería cero filas y tomaría la rama de "reserva inexistente", y el test de sobreventa dejaría de probar la carrera. Además, si el `setUp` de esa clase crea sus 11 reservas dentro de un `transaction.atomic()` abierto por `con_empresa`, quedan sin commit — invisibles para las conexiones de los hilos, que es justo la visibilidad cross-conexión que `TransactionTestCase` existe para dar. **Regla:** cada `target` de hilo abre su propio `con_empresa(empresa)` (pasando `empresa_id`, no el objeto), independiente del que abrió el hilo principal. Aplica también a `apps/fleet/tests.py:258` (`EmbarcacionNoDisponibleUnicidadTests`, también `TransactionTestCase` con conexiones propias). Ver fila de la suite de tests existente en el File Map.

### Tablas cubiertas por RLS

`tenancy_sede`, `tenancy_empresa` y `tenancy_membresiaempresa` **NO** llevan RLS (tablas de arranque, candado circular si las protegiera — ver rondas previas). RLS aplica **`FOR ALL`** sobre: `fleet_tarifa`, `fleet_extrasitem`, `fleet_transporteprecio`, `fleet_puntoencuentro`, `fleet_codigopromocional`, `fleet_embarcacion`, `fleet_capitan`, `fleet_embarcacionnodisponible`, `bookings_reserva`, `bookings_cupodiario`, `bookings_vendedora`, con:

```sql
USING (
  empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
  OR current_setting('app.operador_plataforma', true) = 'on'
)
```

(forma de dos argumentos de `current_setting`, no lanza si no está fijada — **corregido en Revisión 4**: sin el `NULLIF`, la expresión original truena con `invalid input syntax for type integer: ""` en cuanto un GUC personalizado se fija una vez en la sesión, porque al terminar la transacción vuelve a cadena vacía, no a indefinido — se dispara en la segunda pasada de cualquier comando que itere Empresas, y en cualquier `TransactionTestCase` que reutilice conexión. **Revisión 5 (B11):** `=` en vez de `IS NOT DISTINCT FROM` — con `empresa_id NOT NULL` (tras el paso 3 del retrofit) la semántica es idéntica (GUC sin fijar → `NULLIF` da NULL → `empresa_id = NULL` es NULL → `USING` lo trata como falso → cero filas, que es justo lo que exige `tests_rls.py`), pero `IS NOT DISTINCT FROM` no es sargable — fuerza *seq scan* incluso con índice sobre `empresa_id`; `=` sí es indexable. **Nota (Revisión 7):** ese índice no es un paso futuro pendiente — `ForeignKey` de Django trae `db_index=True` por defecto, así que llega gratis en `00XX_empresa_nullable.py`, mismo momento en que se agrega la columna). `bookings_reservaextra` y `bookings_reservatransporte` llevan la misma política pero referida a través de su FK a `Reserva` (no tienen `empresa_id` propio — cuelgan de una `Reserva` cuyo `empresa_id` sí lo tiene):

```sql
USING (
  EXISTS (
    SELECT 1 FROM bookings_reserva r
    WHERE r.id = bookings_reservaextra.reserva_id
      AND (r.empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
           OR current_setting('app.operador_plataforma', true) = 'on')
  )
)
```

(**Revisión 5, B13:** `r.id = bookings_reservaextra.reserva_id` — columna calificada explícitamente con el nombre de tabla; la Revisión 4 escribió `r.id = reserva_id` sin calificar, que hoy resuelve bien porque `bookings_reserva` no tiene una columna `reserva_id` propia, pero es un binding implícito que se rompería en silencio el día que la tuviera. Repetir la misma política, calificada igual, para `bookings_reservatransporte`.)

Sin esto (Revisión 4, hallazgo N12) son las dos únicas tablas de negocio sin red de seguridad, y `ReservaExtra.precio_unitario` es dinero congelado. **Consecuencia para código futuro:** con `FORCE ROW LEVEL SECURITY`, cualquier migración de datos (`RunPython`) que toque estas tablas después de `0003_rls` debe envolverse en `scope.como_operador_plataforma()` o verá cero filas en silencio.

**Tech Stack:** Django 6 + Django REST Framework, Postgres (Supabase) en producción / sqlite en local, `stripe` SDK, `django-axes`. Sin librerías nuevas — RLS con SQL crudo (`migrations.RunSQL`).

**Spec:** `docs/superpowers/specs/2026-08-31-expansion-multi-sede-design.md` (diseño, Revisión 2, correcciones 1-8) y `docs/superpowers/specs/2026-08-31-expansion-multi-sede-ADRs.md` (ADR-001 y ADR-002, que esta pieza implementa). `backend/CLAUDE.md` documenta el sistema actual de un solo negocio que esta pieza retrofitea.

## Global Constraints

- Apps viven bajo `apps/<app>` (paquete), `AppConfig.name = 'apps.<app>'`, `label = '<app>'`.
- Settings en `config/settings/{base,local,production,ci}.py`; `production.py` lee todo de variables de entorno, sin defaults.
- Postgres (Supabase) en producción, sqlite en local/tests por default — las pruebas que dependen de Postgres (advisory lock, RLS) se saltan (`skipUnless`) fuera de `connection.vendor == 'postgresql'`. CI corre contra Postgres real.
- **Nunca confiar en `empresa_id`/total que mande el cliente** — el servidor resuelve la Empresa del **slug de la URL** (rutas públicas) o de la **membresía del usuario autenticado** (backoffice), nunca del cuerpo de la petición ni de metadatos de terceros.
- **CI debe correr los tests como un rol de Postgres SIN `SUPERUSER`/`BYPASSRLS`, distinto de `POSTGRES_USER`** (que es el superusuario de arranque del contenedor y debe seguir siéndolo — renombrarlo no elimina el superusuario, solo lo cambia de nombre). El rol de test necesita `CREATEDB`.
- **Sin Stripe Connect en ningún nivel** (ADR-002).
- Comandos de gestión que mutan datos llevan `--dry-run`.
- **Todo FK `empresa` nuevo lleva `on_delete=PROTECT`** (Revisión 4, N7) — el default de Django es `CASCADE`; borrar una `Empresa` desde el admin no debe poder borrar en cascada su flota, reservas ni historial de dinero. Coherente con la convención ya existente en el repo (`Vendedora.usuario`, `EmbarcacionNoDisponible.embarcacion`).
- **Non-goal explícito de esta pieza (Revisión 4, N24):** `MAX_PERSONAS = 5` sigue siendo una constante global (deriva de la panga más grande de La Paz), duplicada en `frontend/src/lib/dates.ts`. No se escopea por Empresa en esta pieza — queda para cuando se implemente el primer servicio nuevo (`Servicio.capacidad_maxima` o similar, ver spec de diseño). Al dar de alta la segunda Empresa con pangas de otra capacidad, este límite hay que revisarlo a mano.
- Pre-lanzamiento (`estado-prelanzamiento`): las reservas de prueba se re-etiquetan a "Sal y Sol"; el corte de rutas/frontend/Stripe es un solo deploy coordinado, sin alias de rutas viejas — no hay tráfico real que proteger durante la ventana.
- Tests: `venv/Scripts/python.exe manage.py test apps` (Windows, venv en `backend/venv/`).

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `apps/tenancy/__init__.py` | Crear | Marcador de paquete. |
| `apps/tenancy/apps.py` | Crear | `AppConfig`. En `ready()`, conecta un receptor a `django.core.signals.request_started` que fuerza `connection.alcance_actual = None` **solo si `not connection.in_atomic_block`** (ver "No-reentrancia con restauración" arriba — **Revisión 7, N7-C**: sin la condición, el receptor pisa la bandera dentro de una transacción ya abierta, no solo entre peticiones HTTP reales). |
| `apps/tenancy/models.py` | Crear | `Sede` (`nombre`, `slug` único, `zona_horaria`, `activo`). `Empresa` (`sede` FK, `nombre`, **`slug`** único e indexado — inmutable después de creada, de él depende la URL del webhook de Stripe configurada en su Dashboard —, **`activo`**, **`exclusiva`**, `stripe_secret_key`/`stripe_webhook_secret`/`stripe_publishable_key` como campos en tabla — decisión v1 explícita, sin gestor de secretos, llaves de prueba pre-lanzamiento, widget de solo-escritura en el admin, nunca logueadas — (**Revisión 7, N7-F: desviación de ADR-002 §2, que pide "referencia a secreto" — enmienda documentada ahí mismo, con disparador de reversión antes de la primera llave `sk_live_`**), con `clean()` validando el prefijo de cada llave (`sk_`/`whsec_`/`pk_`) porque una llave cruzada guardada desde el admin ya no la detecta ningún chequeo de arranque, ver fila de `checks.py`). `MembresiaEmpresa` (`user` FK **con `related_name='membresias'`** (**Revisión 9, N-b**: lo exige el `get_queryset` de `EmpresaScopedUserAdminMixin`, `User.objects.filter(membresias__empresa=...)`), `empresa` FK, `rol` ∈ {`JEFE`, `VENDEDORA`} — `OperadorPlataforma` NO es un valor de este campo —, `unique_together=('user', 'empresa')`). |
| `apps/tenancy/scope.py` | Crear | `con_empresa(empresa)` / `como_operador_plataforma()`: context managers no reentrantes con valor distinto (`RuntimeError`), no-op idempotentes con el mismo valor, que **restauran** (no solo limpian) `connection.alcance_actual` al valor previo en un `finally` al salir — incluida la rama de excepción. **Revisión 6 (N-E):** el `finally` va **dentro** del `with transaction.atomic()` (no envolviéndolo) — ver "No-reentrancia con restauración" arriba para por qué el orden importa con `on_commit`. `transaction.atomic()` siempre (portable); `SET LOCAL` solo en Postgres. `resolver_membresia_o_403(user)` (0 o >1 membresías → `PermissionDenied`, exactamente 1 → esa empresa; operador de plataforma → `como_operador_plataforma()`). **Revisión 5 (B1):** `resolver_empresa_publica(slug)` (404 si no existe o `activo=False`, para catálogo/checkout) y `resolver_empresa_de_dinero(slug)` (404 solo si no existe, para webhook/conciliación) — ver "Resolución de alcance" §1. Accesores `empresa_actual(request)` / `es_operador_plataforma(user)`. |
| `apps/tenancy/middleware.py` | Crear | `EmpresaScopeMiddleware.__call__` (NO `process_view` — ver "Resolución de alcance" arriba para el pseudocódigo exacto y por qué): resuelve `django.urls.resolve(request.path_info)` a mano; si no matchea o trae `empresa_slug`, pasa sin envolver; si el usuario es anónimo, pasa sin envolver; si no, resuelve membresía/operador y envuelve **todo** `self.get_response(request)` (incluye el render perezoso del admin). |
| `apps/tenancy/admin_mixins.py` | Crear | `EmpresaScopedAdminMixin`: `get_queryset` filtra por `scope.empresa_actual(request)` (o no filtra si `scope.es_operador_plataforma`). **Revisión 4 (N10) — `save_model` reescrito con semántica explícita**, la Revisión 3 dejaba el caso del operador de plataforma sin definir (`empresa_actual(request)` es `None` para él, por diseño no tiene `MembresiaEmpresa` → creaba con `empresa=None` → `IntegrityError`, o al editar le pisaba `empresa` con `None` a una fila ajena): (a) en **edición**, `save_model` **nunca** reasigna `empresa` — se preserva el valor existente del objeto; (b) en **creación**, si hay `empresa_actual` la asigna automáticamente; (c) si es operador de plataforma, `empresa` pasa a ser un campo **visible y obligatorio** del formulario (`get_fields`/`get_form` lo excluyen para jefe/vendedora, lo incluyen para operador) — nunca auto-asignado a ciegas. **Revisión 4 (N18), corregido en Revisión 5 (B5):** `formfield_for_foreignkey` escopea las FK hacia otros modelos tenant-scoped (`embarcacion`, `capitan`, `vendedora`, `codigo_promocional` en `ReservaAdmin`, etc.) al `empresa_actual(request)` cuando no es operador de plataforma — **sin `punto_encuentro`**: vive en `ReservaTransporteInline` (`bookings/admin.py:182-188`), que es 100% de solo lectura, así que no hay campo editable por donde entrar ahí. Sin este mixin, RLS filtra filas pero no impide que el propio admin arme una `Reserva` con la panga de la Empresa A y la vendedora de la B. Complementa `Reserva.clean()` (fila de `bookings/models.py`... ver Global Constraints) que valida esa misma consistencia a nivel de modelo, no solo de formulario. |
| `apps/tenancy/admin.py` | Crear | **Restaurada en Revisión 9 (N-a) — se había perdido al mover el mixin de usuarios a `admin_mixins.py` en la Revisión 8.** Registra `Sede`, `Empresa`, `MembresiaEmpresa`. `Sede`/`Empresa` solo los edita el operador de plataforma (`has_module_permission`/`has_*_permission` restringidos a `scope.es_operador_plataforma`) — es donde vive el widget de solo-escritura de las llaves de Stripe (fila de `tenancy/models.py`) y donde se teclean tras el corte (runbook de `production.py`). `MembresiaEmpresa` la edita/borra el operador de plataforma igual que las otras dos (**salvo el alta vía la acción unificada de `bookings/admin.py`, ver esa fila — C1**); no llevan RLS ninguna de las tres (tablas de arranque). |
| `apps/tenancy/admin_mixins.py` (`EmpresaScopedUserAdminMixin`) | Modificar | **Nuevo en Revisión 7 (N7-A), reescrito en Revisión 8 tras hallar una escalada de privilegios en la redacción original — decisión del dueño: jefe conserva autonomía para dar de alta vendedoras, vía admin escopeado, no exclusivo del operador de plataforma.** Vive en este archivo, junto a `EmpresaScopedAdminMixin` (**Revisión 8, H6**: la Revisión 7 lo puso en `tenancy/admin.py`, que solo debe *registrar* modelos — mezclaba módulos y no tenía dueño claro del cambio real, que ocurre en `bookings/admin.py:429-444`). `get_queryset` filtra a los `User` con `membresias__empresa = empresa_actual(request)` (sin filtrar si es operador de plataforma) — `MembresiaEmpresa.user` gana `related_name='membresias'` (fila de `tenancy/models.py`) para que este lookup no dependa del nombre inverso por defecto (**H10**: es expresable y no duplica filas porque `unique_together=('user','empresa')` garantiza como máximo una fila por usuario al filtrar por una sola Empresa — sin ese `unique_together` la garantía se cae en silencio, dejarlo escrito). Una cuenta sin ninguna `MembresiaEmpresa` (la del `--operador` de `migrar_la_paz_a_empresa.py`, o cualquier cuenta de sistema) desaparece de la lista de todo jefe y solo el operador de plataforma puede tocarla — por diseño (**H10**). `has_add_permission` devuelve `False` para no-operadores (**H5/C2**: sin esto, "Agregar usuario" queda accesible con el `UserCreationForm` estándar, que no pasa por ninguna de las garantías de la acción unificada de abajo — el alta real ocurre *solo* por esa acción). `has_change_permission`/`has_delete_permission`/`has_view_permission` (**H11: las tres, no solo dos** — aunque `get_object()` ya deriva de `get_queryset()` así que la fuga real por permisos no existía, agregarla es defensa en profundidad y evita que un implementador crea que los `has_*` son el candado quien en realidad es `get_queryset`) niegan sobre cualquier `User` fuera del conjunto — incluye superusuarios/staff de otras Empresas y al operador de plataforma. **`get_fieldsets(request, obj)` (H1, crítico — el mecanismo real de contención, no `formfield_for_manytomany`):** para quien no es operador de plataforma, el fieldset "Permissions" del `UserAdmin` estándar (`is_active`, `is_staff`, `is_superuser`, `groups`, `user_permissions` — los cinco, verificado contra Django 6 instalado) se **reduce a `('is_active',)`** — los otros cuatro campos **no aparecen en el formulario en absoluto**, no se ponen `readonly`, se quitan del fieldset, porque un campo ausente del form no llega a `cleaned_data` y no hay otra forma de impedir que un jefe se marque `is_superuser=True` a sí mismo o le asigne `user_permissions` arbitrarios vía el M2M sin restringir (la restricción de `groups` sola no cierra ninguna de las dos vías). Consecuencia también correcta: como `groups` no aparece en el form para un jefe, guardar su propia ficha (está en su propio queryset) nunca le borra su membresía al grupo `Jefe` (**H4**, la asignación de grupo real solo ocurre en la acción de abajo, nunca por este formulario). **`VendedoraAdmin.usuario` (H3, fila de `bookings/admin.py` de abajo) también se escopea** — es la única FK hacia `auth.User` en todo el admin sin cubrir por `EmpresaScopedAdminMixin` (que solo escopea FK hacia modelos tenant-scoped) y sin RLS detrás. **H12 — declarado explícitamente:** `auth_user`/`tenancy_membresiaempresa` no llevan RLS (tablas de arranque) — este mixin es la **única** capa de aislamiento sobre usuarios, en cualquier motor, a diferencia de todo lo demás del plan (que tiene RLS como red en Postgres); un filtro olvidado aquí es fuga silenciosa, no "no aparecen mis datos". `apps/tenancy/tests.py` (fila de arriba) debe cubrir este mixin con el mismo rigor que `tests_rls.py` cubre las políticas — no basta "tests del mixin de admin" genérico. **C1:** la fila de registro de `Sede`/`Empresa`/`MembresiaEmpresa` en `tenancy/admin.py` sigue diciendo "solo operador de plataforma los edita" para `MembresiaEmpresa` — salvo el alta vía la acción unificada de `bookings/admin.py`, ver esa fila. |
| `apps/bookings/admin.py` (`UserAdmin`/`GroupAdmin` líneas 429-444, + acción "Dar de alta vendedora") | Modificar | **Nuevo en Revisión 7 (N7-A), corregido en Revisión 8. H6:** esta fila es la dueña del `UserAdmin`/`GroupAdmin` ya existentes en `bookings/admin.py:429-444` — pasan a `class UserAdmin(EmpresaScopedUserAdminMixin, BaseUserAdmin, ModelAdmin)` (orden de MRO explícito, mismo cuidado que B15 exigió para `TarifaAdmin`: el mixin antes que `BaseUserAdmin` para que sus overrides tomen precedencia). `GroupAdmin` **no** lleva el mixin ni ningún escopeo — `Group` no es tenant-scoped y no hay forma de acotarlo por Empresa; el acceso a él se cierra enteramente por permisos (`setup_roles.py`, H5: `Jefe` no recibe ningún permiso sobre `auth.group`, así que `GroupAdmin` es exclusivo del operador de plataforma). Vista/acción de un solo paso, disponible para `Jefe` y operador de plataforma: recibe usuario/contraseña temporal/nombre/código, y en una sola transacción crea el `User` con `User.objects.create_user(...)` (**H8**: nunca `create()` con `password=` en claro — `create_user` hashea; la contraseña además pasa por `password_validation.validate_password()` antes de guardar, traducido a error de formulario si falla; no hay cambio forzado en el primer login — trade-off aceptado, coherente con `estado-prelanzamiento`, la vendedora se queda con la que el jefe tecleó y debe recibirla por canal aparte, declarado aquí para que no se descubra como sorpresa), `is_staff=True`, sin `is_superuser`, **lo agrega al grupo `Vendedora`** (**H7, corrige un garbleado de la Revisión 7 que decía literalmente "lo agrega al grupo `Jefe`" — nunca `Jefe` ni `OperadorPlataforma`, es la vendedora nueva**) + `MembresiaEmpresa(user=nuevo, empresa=<empresa>, rol=VENDEDORA)` + `bookings.Vendedora(usuario=nuevo, empresa=<empresa>, codigo=...)`. **`<empresa>` (H2, crítico — reintroducía N10 literal):** el formulario de la acción lleva un campo `empresa` **visible y obligatorio** cuando `scope.es_operador_plataforma(request.user)` (que no tiene `empresa_actual(request)` — usarlo a ciegas aquí es el mismo `IntegrityError` que N10 ya cerró para `save_model`); oculto y auto-asignado a `empresa_actual(request)` para el jefe. **H9:** colisión de `username` (único global) o de `Vendedora.usuario` (`OneToOneField` único global, decisión N20) con una cuenta de otra Empresa se traduce a error de formulario, no `IntegrityError`/500 — nota aceptada: el mensaje "ese usuario ya existe" necesariamente confirma al jefe de A que existe una cuenta con ese username en otra Empresa, intrínseco a un espacio de nombres de `username` global. Reemplaza el flujo manual de tres pasos sueltos que documenta `backend/CLAUDE.md` §"Roles: Jefes vs Vendedora" (crear `User` desde el admin/shell, agregarlo al grupo, dar de alta `bookings.Vendedora` aparte) — sin este paso unificado, un jefe podría crear el `User` con el `UserAdmin` escopeado pero quedarse sin poder crear la `MembresiaEmpresa`, y la vendedora nueva quedaría bloqueada con 403 en su primer login, el mismo modo de fallo que la Revisión 3 cerró para la ventana de corte. Actualizar `backend/CLAUDE.md` en la misma pieza — **C3: incluye también la sección "Panel de finanzas"**, que todavía dice "Solo superusuarios: la vista corta con `is_superuser`", invalidada por la fila de `apps/finance/views.py`. |
| `apps/tenancy/tests.py` | Crear | Tests de modelos y de `EmpresaScopedAdminMixin`. **Revisión 9 (N-b, ejecuta H12):** `EmpresaScopedUserAdminMixin` gana su propia clase de test, no genérica — cubre: `get_queryset` no muestra usuarios de otra Empresa a un jefe; un jefe no ve ni puede acceder (404, no 403) a la ficha de un usuario sin membresía en su Empresa; `get_fieldsets` de un jefe sobre su propia ficha **no incluye** `is_superuser`/`user_permissions`/`groups`; guardar esa ficha con el POST completo del changelist (simulando que alguien inyecte `is_superuser=on` en el form) no lo escala — es la prueba directa de H1, con el mismo rigor que `tests_rls.py` prueba las políticas, porque este mixin es la única capa sin RLS detrás. |
| `apps/tenancy/tests_scope.py` | Crear | **`TransactionTestCase`** (no `TestCase` — mismo motivo que `tests_rls.py`, ver esa fila). Resolución de membresía (0/1/>1 → `PermissionDenied`); que el middleware envuelve TODO `get_response` (incluye una vista que devuelve `TemplateResponse` sin renderizar hasta después de que la vista retorna, para probar exactamente el bug de la Revisión 2); anidar con valor distinto → `RuntimeError`; anidar con el mismo valor → no-op y la bandera se restaura al salir del interior; una petición que deja la bandera pegada (excepción fuera de cualquier `with`) no contamina la siguiente (dispara `request_started` a mano y verifica `connection.alcance_actual is None`); rutas anónimas (`/healthz`, `/admin/login/`) no lanzan `PermissionDenied`. **Revisión 4:** `/admin/logout/` tampoco lanza `PermissionDenied` para un usuario autenticado sin membresía (N19); un callback registrado con `transaction.on_commit` desde dentro de un `con_empresa` ve `connection.alcance_actual` limpio al ejecutarse (prueba directa del bug N1, no solo del mecanismo que lo corrige). **Revisión 7 (N7-C):** el guard de no-reentrancia sigue vivo después de una petición del test client — abrir `con_empresa(A)`, hacer un `self.client.get(...)` (que dispara `request_started`), y confirmar que entrar a `con_empresa(B)` todavía lanza `RuntimeError` (no que la señal haya borrado la bandera a mitad de la transacción). |
| `apps/tenancy/tests_rls.py` | Crear | `TransactionTestCase`, `skipUnless(connection.vendor == 'postgresql', ...)`. Dos empresas/dos filas con un rol sin `BYPASSRLS` no ven la fila ajena ni por ORM ni por SQL crudo; sin `SET LOCAL`, cero filas (no excepción); un `INSERT` sin el alcance correcto falla (cubre `FOR ALL`). **Revisión 5 (B6):** primera aserción de la clase, antes de cualquier otro test — `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user` debe devolver `(false, false)`, si no `self.fail(...)` explícito. Mismo chequeo que el runbook de producción exige en despliegue (fila de `production.py`), aquí aplicado en CI para que un typo como el de N22/B6 no vuelva a poder pasar inadvertido con toda la suite en verde. |
| `apps/tenancy/migrations/0001_initial.py` | Crear | Migración estándar (`makemigrations`) para `Sede`/`Empresa`/`MembresiaEmpresa`. Sin RLS. |
| `apps/tenancy/migrations/0002_crear_sede_empresa_la_paz.py` | Crear | `RunPython`: crea Sede "La Paz" (`slug='la-paz'`) + Empresa "Sal y Sol" (`slug='sal-y-sol'` — mismo valor que el default de `NEXT_PUBLIC_EMPRESA_SLUG` en el frontend, ver esa fila —, `exclusiva=True`, `activo=True`). Único archivo que crea esta fila. **Revisión 4 (N15):** la fila se crea con `stripe_secret_key`/`stripe_webhook_secret`/`stripe_publishable_key` poblados desde `os.environ.get('STRIPE_SECRET_KEY'/'STRIPE_WEBHOOK_SECRET'/'STRIPE_PUBLISHABLE_KEY', '')` (mismas variables que hoy lee `settings.py` globalmente) — sin esto, entre que `migrate` termina y que un humano teclea las llaves a mano en el admin, el checkout queda en 503 y el webhook falla la verificación de firma. Si el entorno no trae esas variables (deploy nuevo sin Stripe configurado todavía), queda vacío y cae en el guard-por-Empresa de `conciliar_pagos.py`/`CrearPagoView`, no en un crash. |
| `apps/tenancy/migrations/0003_rls.py` | Crear | `RunSQL`: `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` + política `FOR ALL ... USING (...)` (forma exacta, con el fix `NULLIF` de Revisión 4 N3, en "Tablas cubiertas por RLS" arriba) sobre las 11 tablas con `empresa_id` propio, **más** (Revisión 4, N12) `bookings_reservaextra`/`bookings_reservatransporte` con la política `EXISTS` referida por FK (también en "Tablas cubiertas por RLS"). `dependencies = [...]` sobre las migraciones `00XX_empresa_no_null` **y** `00XX_unicidad_por_empresa` de `fleet` y `bookings` (abajo) — el segundo grupo tiene que existir antes de forzar RLS, o las restricciones únicas globales siguen bloqueando una segunda Empresa por debajo de la política. |
| `apps/tenancy/management/commands/migrar_la_paz_a_empresa.py` | Crear | Cambio de rol, humano, `--dry-run`, **`--operador <username>` obligatorio** (aborta sin él). Requiere que `setup_roles.py` ya se haya corrido (los grupos `Jefe`/`Vendedora`/`OperadorPlataforma` deben existir; si no, error explícito, no `Group.DoesNotExist` crudo). **Revisión 4 (B6a):** requiere también que `tenancy.0002_crear_sede_empresa_la_paz` ya haya corrido (la fila "Sal y Sol" debe existir) — error explícito y abortar si no, no `Empresa.DoesNotExist` crudo. En Render esto se cumple por accidente (`migrate` corre en el `buildCommand` antes de que nadie invoque este comando a mano), pero el chequeo evita que se corra fuera de ese orden en otro entorno. Pasos: (1) agrega `--operador` al grupo `OperadorPlataforma` y le quita `is_superuser`, sin crearle `MembresiaEmpresa`; (2) para el resto de cuentas `is_superuser=True`, crea `MembresiaEmpresa(rol=JEFE)` contra "Sal y Sol", las agrega al grupo Django `Jefe` y les quita `is_superuser`; (3) para cada cuenta del grupo `Vendedora` (staff, ya sin superusuario), crea `MembresiaEmpresa(rol=VENDEDORA)` contra "Sal y Sol" — sin este paso quedan bloqueadas con 403 en su primer login post-corte, aunque nunca tuvieron `is_superuser`. NO crea Sede/Empresa ni hace backfill de `empresa_id` (dueños de eso: las migraciones de datos). |
| `apps/fleet/models.py` | Modificar | Agrega FK `empresa` (`on_delete=PROTECT`, Revisión 4 N7, ver Global Constraints) a `Tarifa`, `ExtrasItem`, `TransportePrecio`, `PuntoEncuentro`, `CodigoPromocional`, `Embarcacion`, `Capitan`, `EmbarcacionNoDisponible`. `Tarifa.save()` **deja de forzar `self.pk = 1`** (hoy lo hace en `def save` línea 42, `self.pk = 1` en línea 46 — corregido en Revisión 4, N21, cita imprecisa antes — con eso la tabla solo puede tener una fila en todo el sistema, imposible una tarifa por Empresa); pasa a upsert por `empresa` (`UniqueConstraint(fields=['empresa'])`, `Tarifa.actual()` de cero argumentos **se elimina**, reemplazado por `Tarifa.de(empresa)`). Los demás `unique=True` **globales** pasan a `unique_together`/`UniqueConstraint` con `empresa`: `TransportePrecio.zona`, `CodigoPromocional.codigo`, `Embarcacion.nombre` — sin esto una segunda Empresa no puede tener su propio "centro"/"VERANO10"/panga con nombre repetido. `capacidades_por_fecha` (def línea 339, con los dos querysets sin filtrar en 352/355 — **Revisión 7, N7 menor: corregida la atribución de la Revisión 6, que repartía las dos líneas entre `capacidades_por_fecha` y `capacidades_disponibles`; en realidad `capacidades_disponibles` (línea 369) no tiene queryset propio, es `return capacidades_por_fecha(fecha, fecha)[fecha]` — igual necesita `empresa` para pasarlo, pero el filtro real vive solo en `capacidades_por_fecha`**) recibe `empresa` y filtra `Embarcacion.objects.filter(activa=True, empresa=empresa)`/`EmbarcacionNoDisponible.objects.filter(..., empresa=empresa)`; `capacidades_disponibles` recibe `empresa` y lo reenvía. Sin esto, en sqlite las pangas de la Empresa B cuentan como capacidad de la A. |
| `apps/fleet/admin.py` | Modificar | Los `ModelAdmin` heredan `EmpresaScopedAdminMixin`. **Revisión 4 (N9):** `TarifaAdmin.has_add_permission` (hoy `return not Tarifa.objects.exists()`, guard del singleton `pk=1`) pasa a `return not Tarifa.objects.filter(empresa=scope.empresa_actual(request)).exists() if scope.empresa_actual(request) else True` — sin este cambio, tras quitar `save()`-fuerza-`pk=1`, el guard viejo sigue devolviendo `False` para siempre (ya existe una fila de cualquier Empresa) y una segunda Empresa nunca puede crear su propia Tarifa desde el admin. **Revisión 5 (B15):** `TarifaAdmin.save_model` (`fleet/admin.py:30-32`, hoy solo asigna `actualizado_por`) debe seguir llamando `super().save_model(...)` para que el `save_model` de `EmpresaScopedAdminMixin` (fila de `admin_mixins.py`, N10) corra en la cadena de MRO — declarar explícitamente el orden de herencia (`class TarifaAdmin(EmpresaScopedAdminMixin, admin.ModelAdmin)`) y que ningún `save_model` de subclase omita el `super()`. |
| `apps/fleet/management/commands/seed_extras.py` | Modificar | **Nuevo en Revisión 4 (N11).** No estaba en el File Map. Sus seis `get_or_create` (`ExtrasItem`/`TransportePrecio`/`PuntoEncuentro`, líneas 44/55/68/77/87/97) ganan `empresa=empresa` obligatorio como argumento del comando — tras el paso 3 (`empresa null=False`) fallarían con `IntegrityError`, y bajo RLS sin alcance el lado `get` del `get_or_create` vería cero filas y dejaría de ser idempotente (reinsertaría en cada corrida). Es el comando que da de alta el catálogo de una Empresa nueva — se corre explícitamente por Empresa, no itera todas. |
| `apps/fleet/views.py` | Modificar | Lee `empresa_slug`, resuelve `Empresa` con `scope.resolver_empresa_publica(slug)`, se envuelve en `with scope.con_empresa(empresa):`; su call site de `Tarifa.actual()` pasa a `Tarifa.de(empresa)`. **Revisión 5 (B7):** sus tres querysets del catálogo (líneas 55/58/61 — `ExtrasItem`/`TransportePrecio`/`PuntoEncuentro.objects.filter(activo=True)`) ganan `empresa=empresa` explícito — es el catálogo público, la fuente de los ids que el serializer de `bookings` valida contra la Empresa (N13); sin el filtro aquí, el catálogo mismo ya mezcla Empresas antes de que el checkout entre en juego. |
| `apps/fleet/urls.py` | Modificar | Rutas ganan prefijo `<slug:empresa_slug>/`. |
| `apps/fleet/tests.py` | Modificar | Su call site de `Tarifa.actual()` (línea 29 hoy) pasa a `Tarifa.de(empresa)` con una `Empresa` de prueba. |
| `apps/fleet/migrations/00XX_empresa_nullable.py` | Crear | Paso 1: agrega `empresa` FK **nullable** a los 8 modelos. |
| `apps/fleet/migrations/00XX_backfill_empresa.py` | Crear | Paso 2 (`RunPython`, depende de `tenancy.0002_crear_sede_empresa_la_paz`): asigna `empresa = "Sal y Sol"` a todas las filas existentes. |
| `apps/fleet/migrations/00XX_empresa_no_null.py` | Crear | Paso 3: `empresa` pasa a `null=False`. |
| `apps/fleet/migrations/00XX_unicidad_por_empresa.py` | Crear | Paso 4: quita los `unique=True` globales de `Tarifa`(vía `save()`)/`TransportePrecio.zona`/`CodigoPromocional.codigo`/`Embarcacion.nombre`, agrega los `UniqueConstraint`/`unique_together` con `empresa`. `tenancy.0003_rls` depende de esta migración, no solo de la de paso 3. |
| `apps/bookings/models.py` | Modificar | Agrega FK `empresa` (`on_delete=PROTECT`, ver Global Constraints) a `Reserva`, `CupoDiario`, `Vendedora`. `evaluar_cupo`/`validar_cupo_diario`/`bloquear_cupo_del_dia` reciben `empresa`, re-llavean el advisory lock a `pg_advisory_xact_lock(empresa_id, fecha.toordinal())` (dos argumentos nativos, sin hash). `CupoDiario.fecha` (`unique=True` hoy) y `Vendedora.codigo` (`unique=True` hoy) pasan a `unique_together`/`UniqueConstraint` con `empresa`. `evaluar_codigo_promocional(codigo_str, correo_cliente)` (`bookings/models.py:356`, **corregido en Revisión 5, B7: es este el que hace el `.get()`**, no `codigo_promocional_valido` como decía la Revisión 4) gana un parámetro `empresa` obligatorio y filtra `CodigoPromocional.objects.get(codigo=..., empresa=empresa)` — sin esto, un código de una Empresa valida (o cobra) en el checkout de otra, y en sqlite (sin RLS) nada más lo evita. **Revisión 4 (N6), corregido en Revisión 5 (B12):** `validar_codigo_promocional_en_pago` (línea 373 hoy, `select_for_update().get(pk=promo.pk)` — lookup **por PK**, nunca puede lanzar `MultipleObjectsReturned`, la Revisión 4 pedía manejarlo ahí por error) es la validación *autoritativa* al cobrar — gana `empresa=empresa` en el filtro que la alimenta y pasa a manejar `CodigoPromocional.DoesNotExist` explícitamente (traducido a `ValidationError({'codigo_promocional': ...})`, coherente con el manejo de la línea 377) — ese es el modo de fallo real una vez agregado el filtro por empresa. El `MultipleObjectsReturned` real se maneja en `evaluar_codigo_promocional`/`CrearPagoView` línea 249 (ver fila de `payments/views.py`, N6), donde sí es un `.get()` por `codigo` no-único. **Revisión 7 (N7-E):** `Reserva.clean()` (línea 677) es el llamador de `validar_codigo_promocional_en_pago` y le pasa `empresa=self.empresa`. **Revisión 4 (N8):** `disponibilidad_por_fecha` (línea 183), `proxima_fecha_disponible` (164), `cupo_maximo_del_dia` (108) y `Reserva._validar_una_salida_por_dia` (715) también reciben `empresa` obligatorio y filtran por ella — sin esto, en sqlite/tests una panga de la Empresa A "bloquea" el cupo o la salida-única del día de una panga de la B; RLS lo tapa solo en Postgres. **Revisión 4 (N14):** `Vendedora.por_codigo(codigo)` (línea 430, resuelve `?ref=` del navegador) gana `empresa` obligatorio y filtra por ella — sin `codigo` único global (uno de los seis retirados), `.first()` elegiría arbitrariamente y atribuiría la venta/comisión a la vendedora de otra Empresa. **Revisión 4 (N20):** `Vendedora.usuario` (`OneToOneField`, línea 397) se queda como `unique=True` **global**, deliberadamente — decide que en v1 una vendedora pertenece a una sola Empresa; si alguien necesita trabajar para dos, necesita dos cuentas Django. Documentado aquí para que no se descubra por sorpresa. **Revisión 4 (N18), corregido en Revisión 5 (B5):** `Reserva.clean()` valida que `embarcacion.empresa_id`, `capitan.empresa_id` (si aplica), `vendedora.empresa_id` y `codigo_promocional.empresa_id` sean todos iguales a `self.empresa_id` — lanza `ValidationError` si no. **`punto_encuentro` se retira de aquí** (Revisión 4 lo puso mal: `Reserva` no tiene ese campo — sus FK son exactamente las cuatro de arriba más `efectivo_cobrado_por`/`cancelada_por`, que no participan de esta consistencia). La validación de `punto_encuentro` y de `extras_item` vive en `ReservaTransporte.clean()`/`ReservaExtra.clean()` (ver filas correspondientes) — son las dos tablas que realmente los tienen, y las mismas dos que deciden precio (zona del punto de encuentro, precio del extra). Red de seguridad a nivel de modelo para cuando el admin del operador de plataforma (sin `formfield_for_foreignkey` filtrado, ver fila de `admin_mixins.py`) arma una combinación cruzada entre Empresas. |
| `apps/bookings/admin.py` | Modificar | `ReservaAdmin`, `AgendaAdmin`, `CheckoutAbandonadoAdmin`, `CupoDiarioAdmin`, `VendedoraAdmin` heredan `EmpresaScopedAdminMixin`. **Revisión 9 (N-b, ejecuta H3 de la Revisión 8, referenciado desde la fila de `admin_mixins.py` pero sin aterrizar aquí):** `VendedoraAdmin` gana `formfield_for_foreignkey('usuario', ...)` filtrado a `User.objects.filter(membresias__empresa=scope.empresa_actual(request))` cuando no es operador de plataforma — es la única FK hacia `auth.User` en todo el admin, y `EmpresaScopedAdminMixin` (que solo escopea FK hacia modelos tenant-scoped) no la cubre por construcción; sin este filtro, "Agregar vendedora" lista y permite seleccionar cualquier usuario del sistema, jefes de otras Empresas y el operador de plataforma incluidos. **Revisión 6 (N-B) — heredarlo no basta en dos de ellos:** `CheckoutAbandonadoAdmin.get_queryset` (línea 373, hoy `return CheckoutAbandonado.abandonados()`) y `AgendaAdmin.get_queryset` (línea 537, hoy `return Agenda.por_repartir().select_related(...)`) **sobreescriben sin llamar `super()`** — a diferencia de `ReservaAdmin.get_queryset` (línea 227, que sí lo hace), así que el mixin queda desactivado en las dos pese a "heredarlo". Son las dos pantallas con más PII (teléfono/WhatsApp de clientes en checkouts abandonados; viajes ya pagados en la agenda del día) — en sqlite/tests quedan sin aislar entre Empresas. Corregir a `super().get_queryset(request).filter(...)` (envolviendo la lógica de `abandonados()`/`por_repartir()` sobre el queryset ya escopeado, no reemplazándolo). **Revisión 6 (N-F):** la acción "Marcar como venta mía" (línea 298, `Vendedora.objects.filter(usuario=request.user, activo=True).first()`) gana `empresa=scope.empresa_actual(request)` explícito. Los guardados desde el admin corren dentro de la transacción exterior del middleware — el advisory lock que `full_clean()` tome se sostiene hasta que termine de renderizar la respuesta completa del admin, no solo hasta que el guardado interno haga commit. Aceptado a la escala actual (2 devs, una Sede); revisar si crece el número de Empresas activas simultáneas. **Revisión 5 (B7):** `reservas_nuevas_view` (línea 148, registrada vía `get_urls()`) no pasa por `get_queryset` — el mixin no la toca — así que su `Reserva.objects.filter(creado_en__gt=...).count()` gana `empresa=scope.empresa_actual(request)` explícito; se sondea cada 30s desde `reservas-nuevas.js`, sin el filtro mezclaría el conteo de nuevas reservas de todas las Empresas. (**Revisión 7, N7-D, corregido en Revisión 8:** esta fila tenía un carácter de barra vertical de más — cortaba el renderizado de tabla justo antes del párrafo del advisory lock; corregido, el contenido no se había perdido del documento, solo quedaba huérfano de su fila. Nota de método: esta misma corrección había vuelto a escribir el carácter sin escapar dentro de esta frase — GFM parte celdas por ese carácter incluso dentro de comillas invertidas; la única forma válida de incluirlo dentro de una celda es precederlo de barra invertida.) |
| `apps/bookings/views.py` | Modificar | Lee `empresa_slug`, resuelve `Empresa`, se envuelve en `with scope.con_empresa(empresa):` antes de `evaluar_cupo`/crear `Reserva`. **Revisión 4 (N8):** `CupoDisponibleView` (línea 54, `Reserva.objects.filter(...).count()`) gana `empresa=empresa` explícito. **Revisión 5 (B7):** `_pendiente_de` (línea 184, `Reserva.objects.filter(checkout_id=..., estado=PENDIENTE_PAGO).first()`) gana `empresa=empresa` — decide qué fila reescribe el upsert del checkout; sin el filtro, un POST a la ruta de la Empresa B con un `checkout_id` que coincide con una reserva de la A reescribe y reasigna la reserva de A. **Revisión 5 (B16):** `CupoRangoView` (líneas 74-126, llama `disponibilidad_por_fecha`) pasa `empresa` explícito a esa llamada — cubierto por el cambio de firma de N8, se lista aquí para que no se pierda como llamador. **Revisión 5 (B4):** la vista que instancia `ReservaCheckoutSerializer` (líneas 159-161, hoy `context={'request': request}`) pasa a `context={'request': request, 'empresa': empresa}` — sin esto, `self.context['empresa']` en el serializer (fila de `serializers.py`, N13/B4) es `KeyError` en cada checkout. **Revisión 7 (N7-E):** líneas 50/53/60 pasan `empresa=empresa` a `evaluar_cupo`/`cupo_maximo_del_dia`/`proxima_fecha_disponible` (N8), que lo ganan como parámetro obligatorio. |
| `apps/bookings/panorama.py` | Modificar | **Nuevo en Revisión 4 (N17).** No estaba en el File Map. Sus tres consultas sin filtrar (`Embarcacion`/`EmbarcacionNoDisponible`/`Reserva`, líneas 69, 72, 78) alimentan el panorama de la agenda y ganan `empresa=` explícito — corre dentro del `con_empresa` de la vista que lo llama, pero no puede asumirlo sin el filtro explícito en sqlite/tests. `armar_panorama(fecha)` gana `empresa` obligatorio; **Revisión 6 (N-G):** su único llamador de producción, `AgendaAdmin.changelist_view` (`bookings/admin.py:534`), pasa `scope.empresa_actual(request)`. |
| `apps/bookings/models.py` (`ReservaTransporte`/`ReservaExtra`) | Modificar | **Nuevo en Revisión 5 (B5).** `ReservaTransporte.clean()` (línea 848 hoy, ya valida `punto_encuentro` vs `direccion_personalizada`/zona) gana la validación `punto_encuentro.empresa_id == self.reserva.empresa_id` — es la FK que decide la zona y por tanto el precio del traslado (N5), así que necesita su propia red aparte de N13/B4 en el serializer. `ReservaExtra` gana un `clean()` nuevo con `extras_item.empresa_id == self.reserva.empresa_id` — hoy no existe ningún `clean()` en este modelo. **Revisión 6 (N-I) — contrato de `self.reserva` en `clean()`:** en `serializers.py:204`, `ReservaTransporte.full_clean(exclude=['reserva'])` corre **antes** de `reserva.save()` (línea 210) — `self.reserva` en ese punto es un objeto Python asignado pero sin guardar (`pk=None`), no una fila de base. Eso funciona porque `_construir_transporte` cachea el objeto en el descriptor de la FK; el `clean()` nuevo debe leer `self.reserva.empresa_id` sobre ese objeto cacheado, no volver a resolverlo por `self.reserva_id` (que sería `None` en ese momento) — y debe tratar `self.reserva` no resoluble (`RelatedObjectDoesNotExist`) como "sin objeto que validar", no dejar que la excepción se escape sin traducir. |
| `apps/bookings/serializers.py` | Modificar | El serializer de creación de `Reserva` toma `empresa` del contexto de la vista, nunca del payload del cliente. **Revisión 5 (B5):** `_sincronizar_extras` (línea 249, `ReservaExtra.objects.create(...)`) pasa a llamar `full_clean()` antes de crear — hoy no lo hace en ningún punto del flujo (a diferencia de `ReservaTransporte`, que sí se valida en línea 204 vía `.full_clean(exclude=['reserva'])`), así que el `clean()` nuevo de `ReservaExtra` (fila de arriba) no se ejecutaría nunca sin este cambio. **Revisión 6 (N-H), corregido en Revisión 7 (la opción de "mover la llamada" era imposible — `_sincronizar_extras` necesita `reserva.pk`, que solo existe después de `reserva.save()` en la línea 210, así que no puede entrar al `try` de las líneas 198-208):** el `try/except DjangoValidationError` que traduce a `serializers.ValidationError` se **extiende** para cubrir también la llamada a `_sincronizar_extras` (línea 214) — es la única opción viable. `_sincronizar_extras` se llama hoy **fuera** de ese bloque, así que sin extender el `try`, un `ValidationError` del `clean()` nuevo de `ReservaExtra` sube sin traducir y responde 500 en una ruta pública en vez de 400. En el flujo normal es inalcanzable (B4 ya escopea el queryset del `PrimaryKeyRelatedField`), pero la red de seguridad debe fallar como error de cliente, no de servidor. **Revisión 7 (N7-E):** línea 158 pasa `empresa=empresa` a `Vendedora.por_codigo` (N14). **Revisión 4 (N13), corregido en Revisión 5 (B4):** los `PrimaryKeyRelatedField` de `punto_encuentro` (línea 60, `PuntoEncuentro.objects.filter(activo=True)`) y `extras` (línea 77, `ExtrasItem.objects.filter(activo=True)`) sí aceptan un id elegido por el cliente — su `queryset` gana `empresa=self.context['empresa']`, resuelto **solo vía `get_fields()`** (la Revisión 4 ofrecía `__init__` como alternativa; está rota porque los dos campos viven en serializers **anidados** — `TransporteSeleccionSerializer`, `ExtraSeleccionSerializer` — instanciados en el cuerpo de clase del serializer padre al importar el módulo, momento en que `self.context` está vacío; y `Serializer.get_fields()` hace `copy.deepcopy(self._declared_fields)`, que no vuelve a correr `__init__` en cada request). Sin esto, el checkout aceptaría el punto de encuentro/extra de otra Empresa, que además decide la zona y por tanto el precio del traslado. |
| `apps/bookings/urls.py` | Modificar | Mismo prefijo `<slug:empresa_slug>/`. |
| `apps/bookings/migrations/00XX_empresa_nullable.py` | Crear | Paso 1 para `Reserva`/`CupoDiario`/`Vendedora`. |
| `apps/bookings/migrations/00XX_backfill_empresa.py` | Crear | Paso 2, depende de `tenancy.0002_crear_sede_empresa_la_paz`. |
| `apps/bookings/migrations/00XX_empresa_no_null.py` | Crear | Paso 3. |
| `apps/bookings/migrations/00XX_unicidad_por_empresa.py` | Crear | Paso 4: `CupoDiario.fecha` y `Vendedora.codigo` a `UniqueConstraint` con `empresa`. `tenancy.0003_rls` también depende de esta. |
| `apps/bookings/management/commands/revisar_cupo.py` | Modificar | Itera cada `Empresa` activa, envuelve cada pasada en `scope.con_empresa(empresa)`. **Revisión 5 (B7):** su queryset interno también gana `empresa=empresa` explícito, no solo el `with` — en sqlite el `with` no filtra nada por sí solo (regla del documento en "Fuera de Postgres"). **Revisión 7 (N7-E):** líneas 46/51 pasan `empresa=empresa` a `capacidades_por_fecha`/`cupo_maximo_del_dia`, que lo ganan como parámetro obligatorio (filas de `fleet/models.py`/`bookings/models.py`). |
| `apps/bookings/management/commands/limpiar_checkouts_abandonados.py` | Modificar | Mismo patrón — sin esto, con RLS puesto deja de ver ninguna fila y el cron se vuelve un no-op silencioso. **Revisión 5 (B7):** su queryset (línea 38, filtra `pendiente_pago`) gana `empresa=empresa` explícito — sin él, en sqlite/tests borraría checkouts abandonados de **todas** las Empresas en la primera pasada, no solo la que está iterando. |
| `apps/bookings/management/commands/setup_roles.py` | Modificar | Da permisos Django a tres grupos: `Jefe` (CRUD completo operativo sobre `fleet`/`bookings`/`payments`, **más `auth.view_user` y `auth.change_user` únicamente — Revisión 8, H5, corrige la ambigüedad de "CRUD completo operativo" que la Revisión 7 dejó sin resolver**: sin `auth.add_user` — el alta pasa solo por la acción unificada de `bookings/admin.py`, cuyo `has_add_permission` la bloquea del "Agregar usuario" directo —, sin `auth.delete_user`, y **ningún permiso sobre `auth.group`**, ni `view` — `GroupAdmin` queda exclusivo del operador de plataforma. Alcance aceptado y declarado: un jefe con `change_user` puede resetear la contraseña de otro jefe de **su propia** Empresa, ambos caen en su queryset escopeado; es aceptable, no un descuido), `Vendedora` (sin cambios de permisos), `OperadorPlataforma` (mismos permisos que `Jefe` + `auth.add_user`/`auth.delete_user`/todos los de `auth.group` + los del catálogo de `apps.tenancy`). **Debe correr antes que `migrar_la_paz_a_empresa.py`** — ese comando asume que estos tres grupos ya existen. Hoy este comando solo crea el grupo `Vendedora` (su propio docstring: *"Los jefes NO usan un grupo: son cuentas Django `is_superuser=True`"*) — los grupos `Jefe`/`OperadorPlataforma` se escriben de cero. |
| `apps/bookings/signals.py` | Modificar | **Nuevo en Revisión 4 (N1).** No estaba en el File Map — el hermano del bug de `notificar_reserva_pagada` (ver fila de `payments/services.py`) que la Revisión 3 no encontró porque ya existía en código, no en el plan. El receptor de aviso de asignación ya usa `transaction.on_commit(lambda: _mandar(instance))` (línea 43); ese callback lee `reserva.capitan.nombre`/`reserva.embarcacion.nombre` (FK perezoso, post-commit) y hace `Reserva.objects.filter(pk=reserva.pk).update(aviso_asignacion_enviado_en=ahora)` (línea 59) — ambos sin alcance bajo RLS: el primero lanza `RelatedObjectDoesNotExist` que el `except Exception` de la línea 49 se traga en silencio, y el segundo actualiza 0 filas, así que el sello "ya enviado" nunca se pone y **el correo se reenvía duplicado en cada edición posterior de la misma reserva, indefinidamente**. Se corrige igual que `notificar_reserva_pagada`: capturar `empresa_id` antes de encolar, reabrir `scope.con_empresa(...)` dentro del callback. |
| `apps/testing.py` | Modificar | **Nuevo en Revisión 4 (N2).** Helper de tests compartido — `crear_flota` (usa `Embarcacion.objects.bulk_create`, línea 54) y el chequeo de idempotencia (`Embarcacion.objects.exists()`, línea 44) ganan `empresa` obligatorio; `ApiTestCase` (o la base que corresponda) crea `Sede`+`Empresa` en `_pre_setup`/`setUpClass` y abre `scope.con_empresa(...)` para el ciclo de vida del test. Sin esto, con `FORCE ROW LEVEL SECURITY` y el rol de CI sin `BYPASSRLS` (Revisión 3, crítico 5), el primer `bulk_create` de cualquier test que lo use revienta con violación de política — y como casi todos los tests de `bookings`/`fleet`/`payments` heredan de esta base, es la pieza que decide si la Revisión 4 puede pasar CI en absoluto. **Revisión 5:** el `con_empresa` abierto en `_pre_setup` se cierra simétricamente vía `self.addCleanup(...)` (o `__enter__`/`__exit__` manuales guardados en la instancia) — el texto de la Revisión 4 decía "para el ciclo de vida del test" sin decir cómo se cierra. |
| Suite de tests existente (`apps/bookings/tests.py`, `tests_agenda.py`, `tests_concurrencia.py`, `tests_cupo_rango.py`, `tests_aviso_asignacion.py`, `apps/payments/tests.py`, `apps/notifications/tests.py`, `apps/finance/tests.py`, `config/tests_health.py`) | Modificar | **Nuevo en Revisión 4 (N2).** Cada `setUp`/test que crea filas de un modelo tenant-scoped fuera de `apps/testing.py` (o del helper corregido) gana su propio `Sede`/`Empresa`/`scope.con_empresa(...)` explícito. No es un ajuste cosmético: es superficie de trabajo comparable al retrofit de modelos — 77 clases de test, no una pasada mecánica de buscar-y-reemplazar. **Revisión 5 (B8):** `tests_concurrencia.py` y `apps/fleet/tests.py:258` (`EmbarcacionNoDisponibleUnicidadTests`) usan hilos con conexión propia — no basta el `con_empresa` de `_pre_setup`, cada `target` de hilo necesita el suyo (ver "Quién corre fuera del alcance", punto 5). **Revisión 5 (B3):** `apps/payments/tests.py` necesita además su segunda pasada — los ~52 `mock.patch('stripe.*')` (incluida la aserción directa de `stripe.api_key` en línea 1171) pasan a parchear el `StripeClient` que devuelve `configurar_stripe(empresa)`, ver fila de `stripe_client.py`. |
| `apps/finance/views.py` | Modificar | `panel_financiero` corta con `scope.es_operador_plataforma(request.user)` (ve todas) o `scope.empresa_actual(request)` no vacío (ve la suya), en vez de `is_superuser`. |
| `apps/finance/services.py` | Modificar | `resumen`/`balances`/`balances_por_dia` aceptan un filtro `empresa` opcional (`None` = todas, solo para operador de plataforma). |
| `apps/payments/stripe_client.py` | Modificar | `configurar_stripe(empresa)` **deja de mutar `stripe.api_key` como estado global del proceso** — devuelve un `stripe.StripeClient(api_key=empresa.stripe_secret_key, stripe_version=settings.STRIPE_API_VERSION)` (**Revisión 5, B3: el `stripe_version` se agrega explícitamente** — `stripe_client.py:14` hoy fija `stripe.api_version = settings.STRIPE_API_VERSION` global, pineado a `'2026-07-29.dahlia'` en `base.py:112`; sin pasarlo al constructor, el cambio despinea la versión de API en la ruta del dinero, silenciosamente) que cada call site usa explícitamente con la forma real de `stripe==15.4.0` (`requirements.txt:5`): el client expone accesores **snake_case** por recurso (`cliente.payment_intents.create(...)`, `cliente.refunds.create(...)`), no el estilo `cliente.PaymentIntent.create(...)` de la Revisión 4 (corregido — esa forma no existe en la SDK). Hoy es seguro mutar el global porque `render.yaml` corre `gunicorn --workers 3` sin hilos (un request a la vez por worker); un client explícito no depende de que eso siga siendo cierto si algún día se agregan hilos/`gevent`. **Revisión 5 (B3) — lista completa de los 6 call sites reales de la API** (la Revisión 4 solo listaba los 4 que *configuran* `stripe_client`, no los que *llaman* la API — quedaban 6 sin listar, todos siguen mutando/leyendo el global tal como está hoy): `payments/views.py:270` (`PaymentIntent.retrieve`) → `cliente.payment_intents.retrieve(...)`; `:277` (`PaymentIntent.modify`) → **`cliente.payment_intents.update(...)`** (**Revisión 6, N-D: el servicio no tiene método `modify`, se llama `update`** — la Revisión 5 tradujo mal el nombre); `:279` (`PaymentIntent.create`) → `cliente.payment_intents.create({...}, {'idempotency_key': ...})`; `payments/services.py:260` (`Refund.create`) → `cliente.refunds.create({...}, {'idempotency_key': ...})`; `conciliar_pagos.py:55` (`PaymentIntent.retrieve`) → `cliente.payment_intents.retrieve(...)`. **Revisión 6 (N-D), crítico para dinero:** en la API de servicios de `StripeClient`, la firma es `create(params, options)` / `update(id, params, options)` — `idempotency_key` va en el segundo argumento (`options`, se traduce a la cabecera `Idempotency-Key`), **no** dentro de `params` como con la SDK legacy (`stripe.PaymentIntent.create(..., idempotency_key=...)`, que lo extraía de los kwargs). Traducir mecánicamente metiendo `idempotency_key` en el dict de `params` pierde la protección de doble clic en `payment_intents.create` y de doble reembolso en `refunds.create` — `backend/CLAUDE.md` documenta esa protección como regla que no se rompe. Cada uno de los dos `create` de la ruta de dinero lleva explícitamente `{'idempotency_key': f'...'}` como segundo argumento, y un test que afirme que la cabecera se sigue mandando. **`stripe.Webhook.construct_event` en `payments/views.py:467` NO cambia** — sigue siendo función de módulo, no cuelga del client; solo necesita el `whsec_` por Empresa, no un `StripeClient`. **Revisión 5, cifra corregida en Revisión 6 (N-J):** `apps/payments/tests.py` tiene 52 `mock.patch('stripe.*')` en total (33 `PaymentIntent.create`, 9 `retrieve`, 1 `modify`, 6 `Refund.create`, 3 `Webhook.construct_event`); de esos, **49** (todos menos los 3 de `Webhook.construct_event`, que no cambia — sigue siendo función de módulo) pasan a parchear el `StripeClient` que devuelve `configurar_stripe(empresa)` (p.ej. `mock.patch.object(StripeClient, 'payment_intents')`), más `tests.py:1171` que hoy afirma `stripe.api_key == 'sk_test_x'` directamente. Es superficie de reescritura de tests comparable a la de N2, no un efecto secundario menor. Los cuatro llamadores de *configuración* — `payments/services.py:258` (`reembolsar`), `conciliar_pagos.py:44`, `payments/views.py:132`, y el docstring de `payments/checks.py:21-22` (documentaba un `shell -c` con `configurar_stripe()` sin argumento, ya no válido) — también se migran. |
| `apps/payments/checks.py` | Modificar | El chequeo de arranque itera **`Empresa.objects.all()`** (**Revisión 5, B17: no solo `activo=True`** — con N16 estableciendo que una Empresa pausada sigue moviendo dinero real vía webhook/conciliación, su llave cruzada debe seguir validándose; iterar solo activas la dejaría de chequear justo cuando más importa), envuelto en `try/except (django.db.utils.DatabaseError,)` (cubre `OperationalError`/`ProgrammingError`) devolviendo lista vacía si la tabla no existe (deploy que instala esta pieza, antes de que corra la migración). Pasa a ser un chequeo **secundario**: la validación real está en `Empresa.clean()` (ver fila de `models.py`), porque una llave cruzada tecleada en el admin en caliente nunca pasa por un chequeo de arranque. |
| `apps/payments/services.py` | Modificar | `aplicar_pago_exitoso` gana `empresa` como parámetro obligatorio (lo pasan `views.py:482` y `conciliar_pagos.py:71`, ver fila de `payments/views.py`). `reembolsar()` recibe la `Empresa` como parámetro explícito de quien la llama — no de metadatos del PaymentIntent. **Revisión 6 (N-G):** sus llamadores internos enhebran `empresa` explícitamente — `aplicar_pago_exitoso:76`, `_resolver_cobro_repetido:116`, `_cancelar_sin_cupo:149`, `_cancelar_codigo_promocional_invalido:170`. `_reserva_del_cargo` (línea 198, filtra por `stripe_payment_intent_id`) gana `empresa=empresa` en su filtro (ya cubierto por N-6/N6 arriba) y el parámetro lo enhebran sus dos llamadores, `aplicar_reembolso` y `aplicar_disputa`, que a su vez lo reciben de `StripeWebhookView` (ver fila de `payments/views.py`). `aplicar_pago_exitoso`'s `select_for_update().filter(pk=...)` **y** el segundo lookup por `stripe_payment_intent_id` (línea 198 hoy, usado por reembolso/disputa) ganan `empresa=empresa` explícito en el filtro. `notificar_reserva_pagada(reserva)` (línea 100 hoy, dentro del `@transaction.atomic` de `aplicar_pago_exitoso`) pasa a `transaction.on_commit(...)` — sin esto, el advisory lock de cupo se sostiene durante dos llamadas HTTP salientes (Resend/WhatsApp, 10s de timeout cada una). **Revisión 4 (N1) — regla obligatoria del callback, ver "Quién corre fuera del alcance" arriba:** `SET LOCAL` muere al COMMIT, así que el callback encolado por `on_commit` NO ve el alcance de la transacción que lo encoló. `notificar_reserva_pagada` pasa a capturar `empresa_id = reserva.empresa_id` (entero) **antes** de encolarse y, al ejecutarse, reabre `with scope.con_empresa(Empresa.objects.get(pk=empresa_id)):` alrededor de sus propias consultas (`extras_seleccionados`, `transporte`, `capitan`, `embarcacion` — todas viven en `notifications/services.py`, no en este archivo, pero el re-scope se hace aquí, en el callback que las invoca) — sin esto, bajo RLS el correo de confirmación sale sin los extras/traslado que el cliente pagó. |
| `apps/payments/views.py` | Modificar | Las cuatro vistas leen `empresa_slug` y se envuelven en `with scope.con_empresa(empresa):`. **Revisión 5 (B1):** `CrearPagoView`/`EstadoReservaView`/`ValidarCodigoPromocionalView` resuelven con `scope.resolver_empresa_publica(slug)`; `StripeWebhookView` resuelve con `scope.resolver_empresa_de_dinero(slug)` — no confundir los dos, ver "Resolución de alcance" §1. `CrearPagoView.get_object_or_404(Reserva, pk=pk)` (línea 54 hoy) y `EstadoReservaView`'s `Reserva.objects.filter(checkout_id=...)` (línea 361 hoy) ganan `empresa=empresa` explícito — sin RLS (sqlite, tests) nada más los aísla. `StripeWebhookView` verifica la firma con **su** `webhook_secret` y usa el `StripeClient` de esa empresa. `CrearPagoView` deja de leer `settings.STRIPE_SECRET_KEY`/`STRIPE_PUBLISHABLE_KEY` directo (líneas 129 y 171 hoy); su call site de `Tarifa.actual()` (línea 74 hoy) pasa a `Tarifa.de(empresa)`. **Revisión 4 (N5) — dos call sites de dinero que la Revisión 3 no cubrió:** `precio_zona = TransportePrecio.objects.filter(zona=transporte.zona, activo=True).first()` (línea 211) gana `empresa=empresa`; sin esto, con `zona` ya no único global, `.first()` elige arbitrariamente entre zonas del mismo nombre de distintas Empresas y congela el precio equivocado. **Revisión 4 (N6):** `promo = CodigoPromocional.objects.get(codigo=codigo_str.upper())` (línea 249) gana `empresa=empresa` y pasa a capturar `CodigoPromocional.MultipleObjectsReturned` explícitamente (con `codigo` ya no único global, dos Empresas con el mismo código sin el filtro lanzarían 500 en el checkout, no un 400 manejado) — devuelve 400 "código no válido" en vez de dejar pasar la excepción. **Revisión 4 (N16):** `StripeWebhookView` procesa el evento aunque `empresa.activo` sea `False` — una Empresa pausada (disputa, corte comercial) sigue necesitando reconciliar dinero ya cobrado; `activo=False` solo debe ocultar el catálogo público (404 en las rutas de checkout que resuelven por slug), nunca el webhook ni la conciliación. **Nota aceptada (Revisión 6, N-J):** `EstadoReservaView` sigue bajo `resolver_empresa_publica` (404 con `activo=False`) aunque sirva el ticket de un cliente que ya pagó — decisión consciente, no descuido: se acepta que pausar una Empresa también oculta la confirmación de reservas ya cobradas de esa Empresa, a diferencia del webhook/conciliación que sí deben seguir viéndolas. **Revisión 6 (N-G):** `views.py:482` (`StripeWebhookView`) y `conciliar_pagos.py:71` pasan `empresa` explícito a `aplicar_pago_exitoso`; `ValidarCodigoPromocionalView.get` (línea 305) pasa `empresa` a `evaluar_codigo_promocional` (que lo gana como parámetro obligatorio, fila de `bookings/models.py`); `StripeWebhookView` líneas 485/489/491 pasan `empresa` a `aplicar_reembolso`/`aplicar_disputa`, que a su vez lo enhebran hacia `_reserva_del_cargo` (fila de `payments/services.py`). |
| `apps/payments/urls.py` | Modificar | Las cuatro rutas ganan el prefijo `<slug:empresa_slug>/`. |
| `apps/payments/management/commands/conciliar_pagos.py` | Modificar | Elimina el guard global `if not settings.STRIPE_SECRET_KEY: return`, lo reemplaza por un guard **por Empresa** (una sin llaves se salta con aviso, no aborta el comando). **Revisión 4 (N16):** itera `Empresa.objects.all()` (no solo `activo=True` — una Empresa desactivada puede tener pagos ya cobrados pendientes de reconciliar) y envuelve cada pasada en `scope.con_empresa(empresa)` usando su `StripeClient`; `activo=False` solo apaga el catálogo público, nunca la conciliación de dinero real. **Revisión 7 (N7-B):** su queryset (línea 47, `Reserva.objects.filter(estado=PENDIENTE_PAGO, creado_en__gte=desde).exclude(stripe_payment_intent_id='')`) gana `empresa=empresa` explícito — era el único de los tres comandos de management sin el filtro en el queryset (B7 lo agregó a `revisar_cupo.py`/`limpiar_checkouts_abandonados.py` pero no a este); en sqlite/tests, sin el filtro, una pasada de la Empresa A recorre pendientes de todas las Empresas y les pregunta a Stripe con la llave de A. |
| `config/urls.py` | Modificar | Los `include()` de `api/` no cambian de forma, heredan los prefijos `<slug:empresa_slug>/` de cada app. `admin/finanzas/` no cambia de ruta. |
| `config/settings/base.py` | Modificar | Agrega `apps.tenancy` a `INSTALLED_APPS` (antes de `fleet`/`bookings`); agrega `EmpresaScopeMiddleware` a `MIDDLEWARE` (después de `AuthenticationMiddleware` — necesita `request.user`, y después de `AxesMiddleware` para no interferir con su bloqueo); agrega entradas de `Sede`/`Empresa`/`Membresía` al `UNFOLD['SIDEBAR']` (solo operador de plataforma); reemplaza el `'permission': lambda request: request.user.is_superuser` del link "Finanzas" (línea 233 hoy) por `lambda request: scope.es_operador_plataforma(request.user) or scope.empresa_actual(request) is not None`. |
| `.github/workflows/ci.yml` | Modificar | `POSTGRES_USER`/`POSTGRES_PASSWORD` del servicio **no cambian** (siguen siendo el superusuario de arranque del contenedor `postgres:17`). Se agrega un paso antes de correr los tests que hace `psql` como `postgres` para `CREATE ROLE ci_rls LOGIN PASSWORD '...' NOSUPERUSER NOBYPASSRLS CREATEDB;`, y el paso de tests cambia **solo** `DB_USER`/`DB_PASSWORD` (no `POSTGRES_USER`) a ese rol nuevo. **Revisión 5 (B6, corrige N22):** el valor real de la matriz en `ci.yml:26-33` es `motor: postgres` (no `'postgresql'` — la Revisión 4 escribió el valor equivocado, así que ese `if` nunca sería verdadero: el paso de `CREATE ROLE` nunca correría, `DB_USER` se quedaría en `postgres` — el superusuario de arranque — y **todo `tests_rls.py` pasaría en verde sin haber ejercido una sola política**, el peor tipo de fallo porque el gate que prueba el aislamiento reportaría éxito precisamente porque el aislamiento está desactivado). Ese paso lleva `if: matrix.motor == 'postgres'` y pasa la contraseña vía `PGPASSWORD` en el `env:` del step, no en texto plano en el comando `psql`. |
| `config/settings/ci.py` | Modificar | El default de `DB_USER` deja de ser `'postgres'`, coherente con el rol nuevo — el workflow sigue siendo la fuente de verdad. |
| `frontend/src/lib/api.ts` | Modificar | `API_URL` gana `NEXT_PUBLIC_EMPRESA_SLUG` (default `'sal-y-sol'` en local — mismo slug que crea `tenancy.0002`), y `request()` antepone `/api/${EMPRESA_SLUG}/` en vez de `/api/`. Corte de un solo deploy (ver Global Constraints): sin alias de rutas viejas. |
| `config/settings/production.py` | Modificar | Checklist manual, **runbook reescrito en Revisión 5 (B2)** — la Revisión 4 (N4) pedía un rol de aplicación distinto del que corre `migrate`, pero `render.yaml` corre `migrate` dentro del mismo `buildCommand` del servicio web, con el único `DB_USER` del env group `pescadeportiva-secrets` (compartido con los dos crons) — no hay un segundo rol disponible en el pipeline de deploy tal como existe hoy. Corregido a **un solo rol**, apoyado en que `FORCE ROW LEVEL SECURITY` (ya en el plan) somete también al dueño de la tabla — es lo que ya pasa en CI, donde `ci_rls` corre `migrate` y por tanto es dueño, y `tests_rls.py` igual prueba el aislamiento porque `FORCE` no exime al dueño: (1) crear/confirmar el rol de aplicación (`DB_USER` actual de Render) sin `SUPERUSER`/`BYPASSRLS` — en Supabase, si hoy es el rol `postgres` de arranque (trae `BYPASSRLS` por defecto), migrar a un rol dedicado, **reescrito en Revisión 6 (N-C) porque la receta de la Revisión 5 no ejecuta en Postgres 15+/Supabase moderno**: `REASSIGN OWNED BY postgres TO <rol_app>` por sí solo **no** otorga `CREATE` sobre el esquema `public` (desde PG15, `public` ya no es de acceso libre y en Supabase pertenece a `pg_database_owner` — sin este permiso el primer `CREATE TABLE` de `tenancy.0001_initial` corriendo como `<rol_app>` falla con `permission denied for schema public`, y el deploy del corte no sale), y `REASSIGN` exige además que quien lo ejecuta (`postgres`) sea miembro del rol destino. En el SQL editor de Supabase, como `postgres`, en este orden: `GRANT <rol_app> TO postgres;` → `GRANT USAGE, CREATE ON SCHEMA public TO <rol_app>;` → **por defecto**, `ALTER TABLE <cada tabla de Django> OWNER TO <rol_app>;` acotado a las tablas/secuencias de la app (no `REASSIGN OWNED BY`, que es de alcance base-de-datos-completa y arrastra cualquier otro objeto que `postgres` posea ahí). Si la conexión de Render pasa por el pooler Supavisor (caso típico: Render sale por IPv4, la conexión directa de Supabase es IPv6-only), `DB_USER` lleva el sufijo de proyecto: `<rol_app>.<project_ref>`, no el rol a secas — verificar cuál conexión usa `render.yaml` antes del corte. (2) ese mismo `<rol_app>` corre `migrate` **y** gunicorn **y** los crons — un solo `DB_USER` en todo el pipeline; (3) **verificación post-deploy obligatoria**, no opcional: `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;` ejecutado con la conexión real de la app debe devolver `(false, false)` — si no, RLS existe en la base pero no protege nada, sin ningún síntoma visible; (4) **trade-off aceptado y declarado, no implícito:** como el rol de la app es dueño de las tablas, técnicamente puede correr `ALTER TABLE ... NO FORCE ROW LEVEL SECURITY` y desactivar la protección — la defensa asume que nadie ejecuta SQL arbitrario contra producción con esas credenciales fuera del código de la aplicación; aceptable a la escala actual (2 devs), revisar si el equipo crece; (5) el endpoint de webhook del Dashboard de Stripe se **edita** (no se crea uno nuevo) para apuntar a `<empresa_slug>` — editar conserva el mismo `whsec_`; si en cambio se crea uno nuevo, copiar su `whsec_` a `Empresa.stripe_webhook_secret` antes del corte (ver también `tenancy.0002`, que hace backfill desde variables de entorno); (6) el corte de `frontend/src/lib/api.ts` (env var `NEXT_PUBLIC_EMPRESA_SLUG` en Vercel) se despliega en la misma ventana que este backend; (7) **ventana de bloqueo total, declarada explícitamente:** entre que `migrate` termina (RLS activo, `empresa_id` NOT NULL) y que `migrar_la_paz_a_empresa.py` corre, nadie tiene `MembresiaEmpresa` — todo el staff recibe 403 en el admin. `migrar_la_paz_a_empresa.py` es parte de la ventana de corte, no un paso posterior opcional, y debe correr inmediatamente después de `migrate` y antes de anunciar el corte como terminado; (8) **Revisión 5 (B10):** tras el corte, las tres variables `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`/`STRIPE_PUBLISHABLE_KEY` de Render quedan sin ningún lector en el código (`tenancy.0002` las leyó una sola vez, al crear la fila) — la rotación de llaves se hace de ahí en adelante **en el admin, por Empresa**, no en Render. Dejarlas en Render solo mientras haya riesgo de rollback; después borrarlas o renombrarlas a `STRIPE_*_BOOTSTRAP` para que su único uso quede evidente. Actualizar la sección de llaves de Stripe de `backend/CLAUDE.md` en la misma pieza. |

**Tradeoff aceptado, no arreglado en esta pieza:** las peticiones GET de solo lectura del backoffice (listados, `reservas-nuevas.js` sondeando cada 30s) también quedan envueltas en la transacción exterior del middleware, igual que los guardados del admin (ver fila de `apps/bookings/admin.py`). A la escala actual no es un riesgo real; la solución (eximir métodos seguros) queda aislada a `scope.py`/`middleware.py` si hace falta después.

<!-- arch-critic: APPROVED after round 9 spot-check (2026-09-01). N-a/N-b applied post-check. Ready for bite-sized task writing. -->

---

## Bite-Sized Tasks

Escritas en 6 secciones (forks paralelos, cada uno con el File Map completo en contexto). Orden de ejecución sugerido: Tenancy (T) primero — todo depende de `apps.tenancy` — luego Fleet (F) y Bookings (B) en paralelo entre sí, luego Test Suite Retrofit (X) (depende de T/F/B), luego Payments/Finance (P), luego Infra/CI/Settings/Frontend/Producción (I) al final (el runbook de `production.py` es el corte real, va después de que todo lo demás esté verde en CI).

Nota de verificación cruzada: el fork de Fleet (F) verificó contra el código real de `apps/fleet/tests.py` que la afirmación de la Revisión 5 (B8) sobre `EmbarcacionNoDisponibleUnicidadTests` usando hilos con conexión propia es incorrecta — esa clase no usa `threading.Thread`. La tarea F9 documenta esto en vez de inventar un fix para un bug que no existe; el caso de hilos real (`tests_concurrencia.py`) sigue cubierto en X7.

### Tenancy (T1-T9)

# Tenancy Core + Roles — Tasks T1-T12

> Sección del plan `docs/superpowers/plans/2026-08-31-expansion-multi-sede-pieza1-tenancy.md`
> (File Map aprobado tras 9 rondas de critic). Cubre `apps/tenancy/*` completo, la
> parte de `apps/bookings/admin.py` dueña de `UserAdmin`/`GroupAdmin` + la acción
> "Dar de alta vendedora", `apps/bookings/management/commands/setup_roles.py`, y los
> cambios de `config/settings/base.py`. Verificado contra el código real
% (`backend/config/settings/base.py`, `backend/apps/bookings/admin.py`,
> `backend/apps/bookings/management/commands/setup_roles.py`) antes de escribir cada
> tarea, no solo contra la prosa del File Map.

**Otras secciones consumen de aquí (firmas fijadas en este documento, no cambiarlas
sin avisar a fleet/bookings/payments):**
- `apps.tenancy.models.Sede(nombre, slug, zona_horaria='America/Mazatlan', activo=True)`
- `apps.tenancy.models.Empresa(sede, nombre, slug, activo=True, exclusiva=False, stripe_secret_key='', stripe_webhook_secret='', stripe_publishable_key='')`
- `apps.tenancy.models.MembresiaEmpresa(user, empresa, rol)` — `rol` ∈ `MembresiaEmpresa.Rol.JEFE`/`.VENDEDORA`
- `apps.tenancy.scope.con_empresa(empresa)` — context manager, recibe la **instancia** `Empresa`, no un id.
- `apps.tenancy.scope.como_operador_plataforma()` — context manager, sin argumentos.
- `apps.tenancy.scope.resolver_membresia_o_403(user)` — devuelve un context manager (`con_empresa(...)` o `como_operador_plataforma()`); levanta `django.core.exceptions.PermissionDenied`.
- `apps.tenancy.scope.resolver_empresa_publica(slug)` — devuelve `Empresa` o levanta `django.http.Http404`.
- `apps.tenancy.scope.resolver_empresa_de_dinero(slug)` — igual, pero no exige `activo=True`.
- `apps.tenancy.scope.empresa_actual(request)` — devuelve `Empresa | None`.
- `apps.tenancy.scope.es_operador_plataforma(user)` — devuelve `bool`.
- `apps.tenancy.admin_mixins.EmpresaScopedAdminMixin` — usar primero en el MRO (`class XAdmin(EmpresaScopedAdminMixin, ModelAdmin)`). Declarar `campos_escopeados_por_empresa = ('fk1', 'fk2', ...)` como atributo de clase en la subclase para que `formfield_for_foreignkey` filtre esas FK por `empresa_actual`.
- `apps.tenancy.admin_mixins.EmpresaScopedUserAdminMixin` — para `UserAdmin` (Task B10).

Comando de test (Windows, desde `backend/`):
`venv\Scripts\python.exe manage.py test apps.tenancy`
`venv\Scripts\python.exe manage.py test apps.bookings.tests` (para el fragmento de T8)

---

### Task T1: App `tenancy` — `Sede`/`Empresa`/`MembresiaEmpresa` + migración inicial

**Files:**
- Create: `backend/apps/tenancy/__init__.py`
- Create: `backend/apps/tenancy/apps.py`
- Create: `backend/apps/tenancy/models.py`
- Create: `backend/apps/tenancy/migrations/__init__.py`
- Create: `backend/apps/tenancy/migrations/0001_initial.py`
- Test: `backend/apps/tenancy/tests.py`

**Interfaces:**
- Produces: `Sede`, `Empresa`, `MembresiaEmpresa` (firmas arriba). `Empresa.clean()`
  valida prefijos de llaves Stripe.

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/apps/tenancy/tests.py
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase

from django.contrib.auth import get_user_model

from .models import Empresa, MembresiaEmpresa, Sede

User = get_user_model()


class ModelosTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='La Paz', slug='la-paz')

    def test_empresa_requiere_slug_unico(self):
        Empresa.objects.create(sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol')
        with self.assertRaises(IntegrityError):
            Empresa.objects.create(sede=self.sede, nombre='Otra', slug='sal-y-sol')

    def test_empresa_valida_prefijo_de_llaves_stripe(self):
        empresa = Empresa(
            sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol',
            stripe_secret_key='clave-mala',
        )
        with self.assertRaises(ValidationError):
            empresa.full_clean()

    def test_empresa_acepta_llaves_con_prefijo_correcto(self):
        empresa = Empresa(
            sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol',
            stripe_secret_key='sk_test_x', stripe_webhook_secret='whsec_x',
            stripe_publishable_key='pk_test_x',
        )
        empresa.full_clean()

    def test_membresia_es_unica_por_usuario_y_empresa(self):
        empresa = Empresa.objects.create(sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol')
        user = User.objects.create_user(username='vendedora1', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.VENDEDORA)
        with self.assertRaises(IntegrityError):
            MembresiaEmpresa.objects.create(user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.JEFE)

    def test_related_name_membresias(self):
        empresa = Empresa.objects.create(sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol')
        user = User.objects.create_user(username='jefe1', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=empresa, rol=MembresiaEmpresa.Rol.JEFE)
        self.assertEqual(user.membresias.count(), 1)
```

- [ ] **Step 2: Correr el test, verificar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.tenancy'`

- [ ] **Step 3: Crear el paquete y el `AppConfig`**

```python
# backend/apps/tenancy/__init__.py
```

```python
# backend/apps/tenancy/apps.py
from django.apps import AppConfig
from django.core.signals import request_started
from django.db import connection


class TenancyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenancy'
    label = 'tenancy'

    def ready(self):
        def _limpiar_alcance_huerfano(sender, **kwargs):
            # Revision 7 (N7-C): django.test.Client dispara esta señal dentro de
            # una transaccion de test (_pre_setup abre con_empresa) -- sin el
            # guard, borraria la bandera a mitad de esa transaccion y rompería
            # la garantia de no-reentrancia. En produccion, request_started
            # siempre ocurre en autocommit (fuera de cualquier con_empresa), asi
            # que el guard no le quita nada a la red de seguridad real.
            if not connection.in_atomic_block:
                connection.alcance_actual = None

        request_started.connect(
            _limpiar_alcance_huerfano, dispatch_uid='tenancy_limpiar_alcance_huerfano'
        )
```

```python
# backend/apps/tenancy/models.py
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Sede(models.Model):
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    zona_horaria = models.CharField(max_length=50, default='America/Mazatlan')
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'sede'
        verbose_name_plural = 'sedes'

    def __str__(self):
        return self.nombre


class Empresa(models.Model):
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='empresas')
    nombre = models.CharField(max_length=150)
    slug = models.SlugField(
        max_length=150, unique=True,
        help_text='Inmutable despues de creada: la URL del webhook de Stripe '
                   'configurada en su Dashboard depende de este valor.',
    )
    activo = models.BooleanField(default=True)
    exclusiva = models.BooleanField(
        default=False,
        help_text='Si esta Empresa opera en exclusiva su Sede. Informativo en v1.',
    )
    # Decision v1 explicita (Revision 7, N7-F, enmienda a ADR-002 SS2): llaves en
    # tabla, sin gestor de secretos externo. Llaves de prueba pre-lanzamiento.
    # Nunca logueadas (ver checks.py). Disparador de reversion: antes de la
    # primera llave sk_live_ -- ver ADR-002.
    stripe_secret_key = models.CharField(max_length=200, blank=True)
    stripe_webhook_secret = models.CharField(max_length=200, blank=True)
    stripe_publishable_key = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'empresa'
        verbose_name_plural = 'empresas'

    def __str__(self):
        return self.nombre

    def clean(self):
        errores = {}
        if self.stripe_secret_key and not self.stripe_secret_key.startswith('sk_'):
            errores['stripe_secret_key'] = "Debe empezar con 'sk_'."
        if self.stripe_webhook_secret and not self.stripe_webhook_secret.startswith('whsec_'):
            errores['stripe_webhook_secret'] = "Debe empezar con 'whsec_'."
        if self.stripe_publishable_key and not self.stripe_publishable_key.startswith('pk_'):
            errores['stripe_publishable_key'] = "Debe empezar con 'pk_'."
        if errores:
            raise ValidationError(errores)


class MembresiaEmpresa(models.Model):
    class Rol(models.TextChoices):
        JEFE = 'JEFE', 'Jefe'
        VENDEDORA = 'VENDEDORA', 'Vendedora'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='membresias',
    )
    # on_delete=PROTECT: 'empresa' cae bajo la regla global de este plan (todo FK
    # llamado `empresa` lleva PROTECT) -- borrar una Empresa no debe poder borrar
    # en cascada sus membresias sin que alguien las revise primero.
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='membresias')
    rol = models.CharField(max_length=10, choices=Rol.choices)

    class Meta:
        unique_together = ('user', 'empresa')
        verbose_name = 'membresia de empresa'
        verbose_name_plural = 'membresias de empresa'

    def __str__(self):
        return f'{self.user} - {self.empresa} ({self.get_rol_display()})'
```

- [ ] **Step 4: Agregar la app a `INSTALLED_APPS` (temporal para este paso — el
  cambio completo de `settings/base.py` es la Task I1, pero `makemigrations`
  necesita la app instalada ya)**

```python
# backend/config/settings/base.py — INSTALLED_APPS
    'apps.tenancy',
    'apps.fleet',
    'apps.bookings',
    'apps.payments',
    'apps.notifications',
    'apps.finance',
```

- [ ] **Step 5: Generar la migración**

Run: `venv\Scripts\python.exe manage.py makemigrations tenancy`

Verificar que `backend/apps/tenancy/migrations/0001_initial.py` crea las 3 tablas
sin RLS (`tenancy_sede`, `tenancy_empresa`, `tenancy_membresiaempresa`) — el archivo
generado por Django es correcto tal cual, no requiere edición manual.

- [ ] **Step 6: Correr el test, verificar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy -v 2`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/apps/tenancy/__init__.py backend/apps/tenancy/apps.py backend/apps/tenancy/models.py backend/apps/tenancy/migrations/ backend/apps/tenancy/tests.py backend/config/settings/base.py
git commit -m "feat(tenancy): app tenancy con Sede/Empresa/MembresiaEmpresa"
```

---

### Task T2: Backfill — crear Sede "La Paz" + Empresa "Sal y Sol"

**Files:**
- Create: `backend/apps/tenancy/migrations/0002_crear_sede_empresa_la_paz.py`

**Interfaces:**
- Produces: la fila `Empresa(slug='sal-y-sol')` que consumen `fleet`/`bookings`
  backfills (Task F2 y su equivalente en Task B) y `migrar_la_paz_a_empresa.py` (T10).

- [ ] **Step 1: Escribir la migración**

```python
# backend/apps/tenancy/migrations/0002_crear_sede_empresa_la_paz.py
import os

from django.db import migrations


def crear_sede_y_empresa(apps, schema_editor):
    Sede = apps.get_model('tenancy', 'Sede')
    Empresa = apps.get_model('tenancy', 'Empresa')

    sede = Sede.objects.create(
        nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan', activo=True,
    )
    Empresa.objects.create(
        sede=sede, nombre='Sal y Sol Sportfishing', slug='sal-y-sol',
        activo=True, exclusiva=True,
        # Backfill desde las mismas env vars que hoy lee settings.py global --
        # sin esto, entre que migrate termina y que alguien teclea las llaves a
        # mano en el admin, el checkout queda en 503 (ver Revision 4, N15).
        stripe_secret_key=os.environ.get('STRIPE_SECRET_KEY', ''),
        stripe_webhook_secret=os.environ.get('STRIPE_WEBHOOK_SECRET', ''),
        stripe_publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY', ''),
    )


def eliminar(apps, schema_editor):
    Empresa = apps.get_model('tenancy', 'Empresa')
    Sede = apps.get_model('tenancy', 'Sede')
    Empresa.objects.filter(slug='sal-y-sol').delete()
    Sede.objects.filter(slug='la-paz').delete()


class Migration(migrations.Migration):

    dependencies = [('tenancy', '0001_initial')]

    operations = [migrations.RunPython(crear_sede_y_empresa, eliminar)]
```

- [ ] **Step 2: Verificar manualmente**

Run:
```
venv\Scripts\python.exe manage.py migrate tenancy 0002
venv\Scripts\python.exe manage.py shell -c "from apps.tenancy.models import Empresa; print(Empresa.objects.get(slug='sal-y-sol').nombre)"
```
Expected: `Sal y Sol Sportfishing`

- [ ] **Step 3: Commit**

```bash
git add backend/apps/tenancy/migrations/0002_crear_sede_empresa_la_paz.py
git commit -m "feat(tenancy): backfill de Sede La Paz y Empresa Sal y Sol"
```

---

### Task T3: `scope.py` — primitivos de alcance

**Files:**
- Create: `backend/apps/tenancy/scope.py`
- Test: `backend/apps/tenancy/tests_scope.py`

**Interfaces:**
- Produces: `con_empresa(empresa)`, `como_operador_plataforma()`,
  `resolver_membresia_o_403(user)`, `resolver_empresa_publica(slug)`,
  `resolver_empresa_de_dinero(slug)`, `empresa_actual(request)`,
  `es_operador_plataforma(user)`, `NOMBRE_GRUPO_OPERADOR_PLATAFORMA = 'OperadorPlataforma'`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/apps/tenancy/tests_scope.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
from django.test import TransactionTestCase

from . import scope
from .models import Empresa, MembresiaEmpresa, Sede

User = get_user_model()


class ScopePrimitivoTests(TransactionTestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='La Paz', slug='la-paz')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-b')

    def test_con_empresa_no_falla_con_el_mismo_valor_anidado(self):
        with scope.con_empresa(self.empresa_a):
            with scope.con_empresa(self.empresa_a):
                pass  # no-op idempotente, no debe lanzar

    def test_con_empresa_falla_con_valor_distinto_anidado(self):
        with scope.con_empresa(self.empresa_a):
            with self.assertRaises(RuntimeError):
                with scope.con_empresa(self.empresa_b):
                    pass

    def test_con_empresa_restaura_al_salir(self):
        with scope.con_empresa(self.empresa_a):
            pass
        self.assertIsNone(getattr(connection, 'alcance_actual', None))

    def test_con_empresa_restaura_el_valor_exterior_tras_anidar(self):
        with scope.con_empresa(self.empresa_a):
            with scope.con_empresa(self.empresa_a):
                pass
            self.assertEqual(connection.alcance_actual, ('empresa', self.empresa_a.id))

    def test_resolver_membresia_sin_membresias_lanza_permission_denied(self):
        user = User.objects.create_user(username='huerfano', password='x')
        with self.assertRaises(PermissionDenied):
            scope.resolver_membresia_o_403(user)

    def test_resolver_membresia_con_dos_membresias_lanza_permission_denied(self):
        user = User.objects.create_user(username='dos', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        MembresiaEmpresa.objects.create(user=user, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.JEFE)
        with self.assertRaises(PermissionDenied):
            scope.resolver_membresia_o_403(user)

    def test_resolver_membresia_con_una_membresia_devuelve_con_empresa(self):
        user = User.objects.create_user(username='uno', password='x')
        MembresiaEmpresa.objects.create(user=user, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        with scope.resolver_membresia_o_403(user):
            self.assertEqual(connection.alcance_actual, ('empresa', self.empresa_a.id))

    def test_resolver_membresia_operador_de_plataforma(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        user = User.objects.create_user(username='operador', password='x')
        user.groups.add(grupo)
        with scope.resolver_membresia_o_403(user):
            self.assertEqual(connection.alcance_actual, ('operador',))

    def test_resolver_empresa_publica_404_si_no_existe(self):
        with self.assertRaises(Http404):
            scope.resolver_empresa_publica('no-existe')

    def test_resolver_empresa_publica_404_si_pausada(self):
        self.empresa_a.activo = False
        self.empresa_a.save()
        with self.assertRaises(Http404):
            scope.resolver_empresa_publica('empresa-a')

    def test_resolver_empresa_de_dinero_ignora_activo(self):
        self.empresa_a.activo = False
        self.empresa_a.save()
        empresa = scope.resolver_empresa_de_dinero('empresa-a')
        self.assertEqual(empresa.pk, self.empresa_a.pk)

    def test_es_operador_plataforma(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        user = User.objects.create_user(username='op', password='x')
        self.assertFalse(scope.es_operador_plataforma(user))
        user.groups.add(grupo)
        self.assertTrue(scope.es_operador_plataforma(user))
```

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests_scope -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.tenancy.scope'`

- [ ] **Step 3: Escribir `scope.py`**

```python
# backend/apps/tenancy/scope.py
from contextlib import contextmanager

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.http import Http404

NOMBRE_GRUPO_OPERADOR_PLATAFORMA = 'OperadorPlataforma'


@contextmanager
def _con_alcance(valor, sql):
    """Primitivo compartido. `valor` es una tupla hashable/comparable que
    identifica el alcance: ('empresa', id) o ('operador',). No reentrante con
    un valor distinto (RuntimeError); no-op idempotente con el mismo valor.

    El `finally` que restaura `connection.alcance_actual` vive DENTRO del
    `with transaction.atomic()` (Revision 6, N-E) -- Django ejecuta los
    callbacks de `transaction.on_commit(...)` dentro del `finally` de
    `Atomic.__exit__`, en el momento del COMMIT real. Si la restauracion
    ocurriera fuera del `atomic()`, un callback que reabre `con_empresa` con
    la misma Empresa encontraria la bandera todavia puesta, tomaria la rama
    no-op, y no emitiria `SET LOCAL` en la transaccion nueva del callback --
    bajo RLS eso es cero filas en silencio (el bug N1 original).
    """
    actual = getattr(connection, 'alcance_actual', None)
    ya_puesto = actual == valor
    if actual is not None and not ya_puesto:
        raise RuntimeError(
            f'Ya hay un alcance de tenancy activo ({actual!r}); no se puede '
            f'entrar a {valor!r} sin salir primero.'
        )

    with transaction.atomic():
        if not ya_puesto:
            connection.alcance_actual = valor
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute(sql)
        try:
            yield
        finally:
            if not ya_puesto:
                connection.alcance_actual = actual


@contextmanager
def con_empresa(empresa):
    """`empresa`: instancia de `Empresa`, no un id."""
    # SET LOCAL no soporta parametros ligados de forma confiable entre drivers
    # -- se castea a int explicito (revienta con ValueError si no es un id
    # valido) y se interpola: seguro porque nunca viene de input de usuario.
    with _con_alcance(
        ('empresa', empresa.id),
        f'SET LOCAL app.current_empresa_id = {int(empresa.id)}',
    ):
        yield


@contextmanager
def como_operador_plataforma():
    with _con_alcance(('operador',), "SET LOCAL app.operador_plataforma = 'on'"):
        yield


def resolver_membresia_o_403(user):
    """Devuelve un context manager (`con_empresa(...)` o
    `como_operador_plataforma()`). Un solo tipo de excepcion, un solo lugar:
    0 o >1 `MembresiaEmpresa` -> PermissionDenied. Mas de una membresia no
    ocurre en v1 (el dueño confirmo rol de jefe solo por Empresa) -- es
    guardia de sanidad, no flujo soportado."""
    if es_operador_plataforma(user):
        return como_operador_plataforma()

    from .models import MembresiaEmpresa

    membresias = list(MembresiaEmpresa.objects.filter(user=user).select_related('empresa'))
    if len(membresias) != 1:
        raise PermissionDenied('El usuario no pertenece a exactamente una Empresa.')
    return con_empresa(membresias[0].empresa)


def resolver_empresa_publica(slug):
    """Catalogo/checkout: 404 si el slug no existe O si activo=False -- es
    dinero por cobrar, una Empresa pausada no debe vender."""
    from .models import Empresa

    try:
        return Empresa.objects.get(slug=slug, activo=True)
    except Empresa.DoesNotExist:
        raise Http404('Empresa no encontrada.')


def resolver_empresa_de_dinero(slug):
    """Webhook/conciliacion: 404 SOLO si el slug no existe -- una Empresa
    pausada (disputa, corte comercial) sigue necesitando reconciliar dinero
    ya cobrado (Revision 4, N16)."""
    from .models import Empresa

    try:
        return Empresa.objects.get(slug=slug)
    except Empresa.DoesNotExist:
        raise Http404('Empresa no encontrada.')


def empresa_actual(request):
    """Lee el alcance ya resuelto por el middleware/vista -- no vuelve a
    consultar MembresiaEmpresa por su cuenta."""
    valor = getattr(connection, 'alcance_actual', None)
    if valor is None or valor[0] != 'empresa':
        return None
    from .models import Empresa

    return Empresa.objects.get(pk=valor[1])


def es_operador_plataforma(user):
    if user.is_anonymous:
        return False
    return user.groups.filter(name=NOMBRE_GRUPO_OPERADOR_PLATAFORMA).exists()
```

- [ ] **Step 4: Correr los tests, verificar que pasan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests_scope -v 2`
Expected: PASS (bajo sqlite, `SET LOCAL` se salta pero `connection.alcance_actual`
se prueba igual — la parte de Postgres la cubre la Task T12/`tests_rls.py`)

- [ ] **Step 5: Commit**

```bash
git add backend/apps/tenancy/scope.py backend/apps/tenancy/tests_scope.py
git commit -m "feat(tenancy): primitivos de alcance con_empresa/resolvers"
```

---

### Task T4: `EmpresaScopeMiddleware`

**Files:**
- Create: `backend/apps/tenancy/middleware.py`
- Modify: `backend/apps/tenancy/tests_scope.py`

**Interfaces:**
- Consumes: `scope.resolver_membresia_o_403(user)`.
- Produces: `EmpresaScopeMiddleware` (clase, `__call__` estilo Django moderno).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/apps/tenancy/tests_scope.py (agregar al final del archivo)
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, TemplateResponse
from django.template import Template
from django.test import RequestFactory
from django.urls import path

from .middleware import EmpresaScopeMiddleware


def _vista_prueba_alcance(request):
    # Devuelve una TemplateResponse SIN renderizar hasta despues de que la
    # vista retorna -- reproduce exactamente el bug de la Revision 2 (admin
    # renderiza perezoso, process_view ya habia devuelto).
    assert connection.alcance_actual is not None
    return TemplateResponse(request, Template('{{ x }}'), {'x': 'ok'})


urlpatterns_prueba = [path('probar-alcance/', _vista_prueba_alcance, name='probar_alcance')]


class MiddlewareTests(TransactionTestCase):
    databases = {'default'}

    def setUp(self):
        sede = Sede.objects.create(nombre='La Paz', slug='la-paz')
        self.empresa = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.user = User.objects.create_user(username='jefe', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=self.user, empresa=self.empresa, rol=MembresiaEmpresa.Rol.JEFE)

    def _middleware(self, get_response):
        return EmpresaScopeMiddleware(get_response)

    def test_envuelve_todo_get_response_incluido_render_perezoso(self):
        capturado = {}

        def get_response(request):
            response = _vista_prueba_alcance(request)
            # El render perezoso ocurre DESPUES de que la vista retorna --
            # si el middleware solo envolviera la llamada a la vista
            # (process_view), esto ya estaria fuera del alcance.
            capturado['alcance_al_renderizar'] = connection.alcance_actual
            response.render()
            return response

        request = RequestFactory().get('/admin/bookings/reserva/')
        request.user = self.user
        middleware = self._middleware(get_response)

        import apps.tenancy.middleware as middleware_module
        original_resolve = middleware_module.resolve

        def resolve_admin(path_info):
            class Match:
                kwargs = {}
                view_name = 'admin:bookings_reserva_changelist'
            return Match()

        middleware_module.resolve = resolve_admin
        try:
            middleware(request)
        finally:
            middleware_module.resolve = original_resolve

        self.assertEqual(capturado['alcance_al_renderizar'], ('empresa', self.empresa.id))

    def test_ruta_publica_con_empresa_slug_no_se_envuelve(self):
        def get_response(request):
            self.assertIsNone(getattr(connection, 'alcance_actual', None))
            return HttpResponse('ok')

        request = RequestFactory().get('/api/empresa-a/tarifa/')
        request.user = AnonymousUser()
        middleware = self._middleware(get_response)
        middleware(request)

    def test_usuario_anonimo_no_se_envuelve(self):
        def get_response(request):
            self.assertIsNone(getattr(connection, 'alcance_actual', None))
            return HttpResponse('ok')

        request = RequestFactory().get('/admin/login/')
        request.user = AnonymousUser()
        middleware = self._middleware(get_response)
        middleware(request)

    def test_admin_logout_no_lanza_permission_denied_sin_membresia(self):
        huerfano = User.objects.create_user(username='sin-membresia', password='x', is_staff=True)

        def get_response(request):
            return HttpResponse('ok')

        request = RequestFactory().get('/admin/logout/')
        request.user = huerfano
        middleware = self._middleware(get_response)
        # No debe lanzar PermissionDenied.
        middleware(request)

    def test_una_peticion_que_deja_la_bandera_pegada_no_contamina_la_siguiente(self):
        from django.core.signals import request_started

        def get_response_que_revienta(request):
            raise ValueError('boom')

        middleware = self._middleware(get_response_que_revienta)
        request = RequestFactory().get('/admin/')
        request.user = self.user
        with self.assertRaises(ValueError):
            middleware(request)
        # La bandera puede quedar pegada tras una excepcion fuera de cualquier
        # `with` real de vista -- request_started es la red de seguridad.
        request_started.send(sender=None)
        self.assertIsNone(getattr(connection, 'alcance_actual', None))
```

(Nota: `test_envuelve_todo_get_response_incluido_render_perezoso` parchea
`middleware.resolve` directamente porque `RequestFactory` no monta rutas reales de
`config.urls` — es deliberado, prueba el mecanismo del middleware en aislamiento del
árbol de URLs real, que ya se prueba end-to-end en los tests de vistas de F7/B.)

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests_scope.MiddlewareTests -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.tenancy.middleware'`

- [ ] **Step 3: Escribir `middleware.py`**

```python
# backend/apps/tenancy/middleware.py
from django.urls import Resolver404, resolve

from . import scope


class EmpresaScopeMiddleware:
    """Ver "Resolucion de alcance" en el plan para el pseudocodigo original.
    Envuelve __call__ completo (no process_view): el admin de Django renderiza
    sus listados de forma perezosa, despues de que process_view ya devolvio
    (Revision 3) -- process_view solo no basta."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            match = resolve(request.path_info)
        except Resolver404:
            match = None

        if match is None or 'empresa_slug' in match.kwargs:
            # Ruta publica (se envuelve sola en la vista) o no reconocida.
            return self.get_response(request)

        if request.user.is_anonymous or match.view_name == 'admin:logout':
            # Anonimo o cerrando sesion: sin alcance. Sin este caso, un
            # usuario autenticado con 0/>1 membresias recibe PermissionDenied
            # en TODA ruta del admin, incluido logout (Revision 4, N19).
            return self.get_response(request)

        alcance = scope.resolver_membresia_o_403(request.user)
        with alcance:
            return self.get_response(request)
```

- [ ] **Step 4: Correr los tests, verificar que pasan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests_scope -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/tenancy/middleware.py backend/apps/tenancy/tests_scope.py
git commit -m "feat(tenancy): EmpresaScopeMiddleware envuelve __call__ completo"
```

---

### Task T5: `EmpresaScopedAdminMixin`

**Files:**
- Create: `backend/apps/tenancy/admin_mixins.py`
- Test: `backend/apps/tenancy/tests.py`

**Interfaces:**
- Consumes: `scope.empresa_actual(request)`, `scope.es_operador_plataforma(user)`.
- Produces: `EmpresaScopedAdminMixin` con `get_queryset`, `save_model`, `get_fields`,
  `formfield_for_foreignkey`. Subclases declaran `campos_escopeados_por_empresa`
  (tupla de nombres de FK) como atributo de clase opcional.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/apps/tenancy/tests.py (agregar al final del archivo de la Task T1)
from django.contrib import admin as django_admin
from django.test import RequestFactory

from .admin_mixins import EmpresaScopedAdminMixin


class _ModeloDePrueba(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=50)

    class Meta:
        app_label = 'tenancy'


class _ModeloDePruebaAdmin(EmpresaScopedAdminMixin, django_admin.ModelAdmin):
    fields = ['nombre', 'empresa']


class EmpresaScopedAdminMixinTests(TestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='La Paz', slug='la-paz')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-b')
        self.jefe = User.objects.create_user(username='jefe', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=self.jefe, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)
        self.admin = _ModeloDePruebaAdmin(_ModeloDePrueba, django_admin.site)

    def _request(self, user):
        request = RequestFactory().get('/')
        request.user = user
        return request

    def test_get_fields_oculta_empresa_para_no_operador(self):
        with scope.con_empresa(self.empresa_a):
            fields = self.admin.get_fields(self._request(self.jefe))
        self.assertNotIn('empresa', fields)

    def test_get_fields_muestra_empresa_para_operador_en_creacion(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op', password='x', is_staff=True)
        operador.groups.add(grupo)
        with scope.como_operador_plataforma():
            fields = self.admin.get_fields(self._request(operador), obj=None)
        self.assertIn('empresa', fields)

    def test_get_fields_oculta_empresa_para_operador_en_edicion(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op2', password='x', is_staff=True)
        operador.groups.add(grupo)
        instancia = _ModeloDePrueba(nombre='x', empresa=self.empresa_a)
        with scope.como_operador_plataforma():
            fields = self.admin.get_fields(self._request(operador), obj=instancia)
        self.assertNotIn('empresa', fields)

    def test_save_model_autoasigna_empresa_en_creacion_para_no_operador(self):
        obj = _ModeloDePrueba(nombre='x')
        with scope.con_empresa(self.empresa_a):
            self.admin.save_model(self._request(self.jefe), obj, form=None, change=False)
        self.assertEqual(obj.empresa_id, self.empresa_a.id)
```

(`_ModeloDePrueba` es un modelo abstracto de test; para que `manage.py test` lo
registre sin migración propia, se marca con `Meta.app_label = 'tenancy'` y no se le
genera migración — Django construye su tabla en memoria vía `apps.get_models()`
solo cuando el módulo de test se importa dentro de la corrida de tests. Si el test
runner se queja de tabla inexistente, envolver la clase en `@override_settings` no
hace falta: `TestCase` crea el esquema completo desde las apps instaladas más los
módulos de test cargados antes de la primera corrida — confirmar corriendo el
Step 2 tal cual antes de asumir que hace falta más).

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests.EmpresaScopedAdminMixinTests -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.tenancy.admin_mixins'`

- [ ] **Step 3: Escribir `admin_mixins.py` (solo `EmpresaScopedAdminMixin` en este paso)**

```python
# backend/apps/tenancy/admin_mixins.py
from . import scope


class EmpresaScopedAdminMixin:
    """Va PRIMERO en el MRO: `class XAdmin(EmpresaScopedAdminMixin, ModelAdmin)`.
    Subclases declaran `campos_escopeados_por_empresa = ('fk1', 'fk2')` para que
    `formfield_for_foreignkey` filtre esas FK al `empresa_actual`."""

    campos_escopeados_por_empresa = ()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if scope.es_operador_plataforma(request.user):
            return qs
        return qs.filter(empresa=scope.empresa_actual(request))

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if 'empresa' not in fields:
            return fields
        if obj is not None:
            # Edicion: NUNCA se reasigna empresa, sin importar el rol.
            fields.remove('empresa')
        elif not scope.es_operador_plataforma(request.user):
            # Creacion, no operador: se autoasigna en save_model, no se pide.
            fields.remove('empresa')
        # Creacion + operador: se queda, visible y obligatorio.
        return fields

    def save_model(self, request, obj, form, change):
        if not change and not scope.es_operador_plataforma(request.user):
            obj.empresa = scope.empresa_actual(request)
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in self.campos_escopeados_por_empresa:
            empresa = scope.empresa_actual(request)
            if empresa is not None:
                kwargs['queryset'] = db_field.remote_field.model.objects.filter(empresa=empresa)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
```

- [ ] **Step 4: Correr los tests, verificar que pasan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests.EmpresaScopedAdminMixinTests -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/tenancy/admin_mixins.py backend/apps/tenancy/tests.py
git commit -m "feat(tenancy): EmpresaScopedAdminMixin"
```

---

### Task T6: `EmpresaScopedUserAdminMixin` (H1 — contención de escalada de privilegios)

**Files:**
- Modify: `backend/apps/tenancy/admin_mixins.py`
- Modify: `backend/apps/tenancy/tests.py`

**Interfaces:**
- Consumes: `MembresiaEmpresa.related_name='membresias'` (Task T1).
- Produces: `EmpresaScopedUserAdminMixin` — consumido por `bookings/admin.py` (Task B10).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/apps/tenancy/tests.py (agregar al final)
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .admin_mixins import EmpresaScopedUserAdminMixin


class _UserAdminDePrueba(EmpresaScopedUserAdminMixin, BaseUserAdmin, django_admin.ModelAdmin):
    pass


class EmpresaScopedUserAdminMixinTests(TestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='La Paz', slug='la-paz')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-b')

        self.jefe_a = User.objects.create_user(username='jefe-a', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(user=self.jefe_a, empresa=self.empresa_a, rol=MembresiaEmpresa.Rol.JEFE)

        self.vendedora_b = User.objects.create_user(username='vend-b', password='x', is_staff=True)
        MembresiaEmpresa.objects.create(
            user=self.vendedora_b, empresa=self.empresa_b, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )

        self.admin = _UserAdminDePrueba(User, django_admin.site)

    def _request(self, user):
        request = RequestFactory().get('/')
        request.user = user
        return request

    def test_get_queryset_no_cruza_empresas(self):
        with scope.con_empresa(self.empresa_a):
            qs = self.admin.get_queryset(self._request(self.jefe_a))
        self.assertIn(self.jefe_a, qs)
        self.assertNotIn(self.vendedora_b, qs)

    def test_get_queryset_operador_ve_todo(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op', password='x', is_staff=True)
        operador.groups.add(grupo)
        with scope.como_operador_plataforma():
            qs = self.admin.get_queryset(self._request(operador))
        self.assertIn(self.jefe_a, qs)
        self.assertIn(self.vendedora_b, qs)

    def test_no_ve_ni_puede_acceder_a_ficha_de_usuario_ajeno(self):
        with scope.con_empresa(self.empresa_a):
            self.assertFalse(
                self.admin.has_view_permission(self._request(self.jefe_a), self.vendedora_b)
            )
            self.assertFalse(
                self.admin.has_change_permission(self._request(self.jefe_a), self.vendedora_b)
            )

    def test_has_add_permission_falso_para_no_operador(self):
        with scope.con_empresa(self.empresa_a):
            self.assertFalse(self.admin.has_add_permission(self._request(self.jefe_a)))

    def test_get_fieldsets_de_jefe_no_incluye_campos_de_permisos_completos(self):
        with scope.con_empresa(self.empresa_a):
            fieldsets = self.admin.get_fieldsets(self._request(self.jefe_a), self.jefe_a)
        campos_planos = {campo for _, opciones in fieldsets for campo in opciones.get('fields', ())}
        self.assertNotIn('is_superuser', campos_planos)
        self.assertNotIn('user_permissions', campos_planos)
        self.assertNotIn('groups', campos_planos)
        self.assertIn('is_active', campos_planos)

    def test_get_fieldsets_de_operador_incluye_todo(self):
        grupo, _ = Group.objects.get_or_create(name=scope.NOMBRE_GRUPO_OPERADOR_PLATAFORMA)
        operador = User.objects.create_user(username='op2', password='x', is_staff=True)
        operador.groups.add(grupo)
        with scope.como_operador_plataforma():
            fieldsets = self.admin.get_fieldsets(self._request(operador), operador)
        campos_planos = {campo for _, opciones in fieldsets for campo in opciones.get('fields', ())}
        self.assertIn('is_superuser', campos_planos)

    def test_post_completo_inyectando_is_superuser_no_escala(self):
        """Prueba directa de H1: simula un jefe enviando el form completo del
        changelist con is_superuser=on inyectado a mano (bypaseando el HTML
        real, que ya no pinta el campo) -- ModelForm solo procesa los campos
        de `fields` (derivados de get_fieldsets), asi que un campo ausente de
        ahi nunca llega a `cleaned_data` sin importar que traiga el POST."""
        with scope.con_empresa(self.empresa_a):
            request = self._request(self.jefe_a)
            fieldsets = self.admin.get_fieldsets(request, self.jefe_a)
            form_class = self.admin.get_form(request, self.jefe_a, fieldsets=fieldsets)
            form = form_class(
                data={'is_superuser': 'on', 'is_active': 'on', 'username': 'jefe-a'},
                instance=self.jefe_a,
            )
            self.assertTrue(form.is_valid(), form.errors)
            usuario_actualizado = form.save(commit=False)
            self.assertFalse(usuario_actualizado.is_superuser)
```

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests.EmpresaScopedUserAdminMixinTests -v 2`
Expected: FAIL — `ImportError: cannot import name 'EmpresaScopedUserAdminMixin'`

- [ ] **Step 3: Agregar `EmpresaScopedUserAdminMixin` a `admin_mixins.py`**

```python
# backend/apps/tenancy/admin_mixins.py (agregar al final del archivo)

# Campos del fieldset "Permissions" del UserAdmin de Django (verificado contra
# Django 6 instalado: is_active, is_staff, is_superuser, groups,
# user_permissions). Se identifica el fieldset por CONTENIDO (si trae
# is_superuser o groups), no por el TITULO del fieldset -- el titulo es una
# cadena _() traducida y con LANGUAGE_CODE='es-mx' podria no ser literalmente
# 'Permissions' en tiempo de ejecucion.
CAMPOS_PERMISOS_RESTRINGIDOS = ('is_active',)


class EmpresaScopedUserAdminMixin:
    """Unica capa de aislamiento sobre `auth.User`/`auth.Group` -- esas tablas
    no llevan RLS (son de arranque). Un filtro olvidado aqui es fuga
    silenciosa en CUALQUIER motor, no solo en sqlite/tests."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if scope.es_operador_plataforma(request.user):
            return qs
        return qs.filter(membresias__empresa=scope.empresa_actual(request))

    def _en_alcance(self, request, obj):
        return self.get_queryset(request).filter(pk=obj.pk).exists()

    def has_add_permission(self, request):
        if not scope.es_operador_plataforma(request.user):
            return False
        return super().has_add_permission(request)

    def has_view_permission(self, request, obj=None):
        if obj is not None and not self._en_alcance(request, obj):
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj is not None and not self._en_alcance(request, obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not self._en_alcance(request, obj):
            return False
        return super().has_delete_permission(request, obj)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if scope.es_operador_plataforma(request.user):
            return fieldsets

        nuevos = []
        for titulo, opciones in fieldsets:
            campos = opciones.get('fields', ())
            if 'is_superuser' in campos or 'groups' in campos or 'user_permissions' in campos:
                opciones = {**opciones, 'fields': CAMPOS_PERMISOS_RESTRINGIDOS}
            nuevos.append((titulo, opciones))
        return nuevos
```

- [ ] **Step 4: Correr los tests, verificar que pasan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests.EmpresaScopedUserAdminMixinTests -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/tenancy/admin_mixins.py backend/apps/tenancy/tests.py
git commit -m "feat(tenancy): EmpresaScopedUserAdminMixin, contencion de H1"
```

---

### Task T7: `apps/tenancy/admin.py` — registro de `Sede`/`Empresa`/`MembresiaEmpresa`

**Files:**
- Create: `backend/apps/tenancy/admin.py`

**Interfaces:**
- Consumes: `scope.es_operador_plataforma(request.user)`.

- [ ] **Step 1: Escribir el código (sin test nuevo — el aislamiento de permisos
  ya lo cubre `EmpresaScopedAdminMixinTests`; aquí solo se registra)**

```python
# backend/apps/tenancy/admin.py
from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin

from . import scope
from .models import Empresa, MembresiaEmpresa, Sede


class SoloOperadorPlataformaAdminMixin:
    def has_module_permission(self, request):
        return scope.es_operador_plataforma(request.user)

    def has_view_permission(self, request, obj=None):
        return scope.es_operador_plataforma(request.user)

    def has_add_permission(self, request):
        return scope.es_operador_plataforma(request.user)

    def has_change_permission(self, request, obj=None):
        return scope.es_operador_plataforma(request.user)

    def has_delete_permission(self, request, obj=None):
        return scope.es_operador_plataforma(request.user)


@admin.register(Sede)
class SedeAdmin(SoloOperadorPlataformaAdminMixin, ModelAdmin):
    list_display = ['nombre', 'slug', 'zona_horaria', 'activo']
    prepopulated_fields = {'slug': ('nombre',)}


class EmpresaAdminForm(forms.ModelForm):
    """Las 3 llaves de Stripe son de solo-escritura: PasswordInput nunca
    repinta el valor guardado. Sin el clean() de abajo, dejar el campo vacio
    en un submit (porque nunca se vio el valor actual) borraria la llave ya
    puesta -- clean() la restaura desde la instancia si llega vacio."""

    stripe_secret_key = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    stripe_webhook_secret = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    stripe_publishable_key = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))

    class Meta:
        model = Empresa
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            for campo in ('stripe_secret_key', 'stripe_webhook_secret', 'stripe_publishable_key'):
                if not cleaned.get(campo):
                    cleaned[campo] = getattr(self.instance, campo)
        return cleaned


@admin.register(Empresa)
class EmpresaAdmin(SoloOperadorPlataformaAdminMixin, ModelAdmin):
    form = EmpresaAdminForm
    list_display = ['nombre', 'sede', 'slug', 'activo', 'exclusiva']
    list_filter = ['sede', 'activo']
    fields = [
        'sede', 'nombre', 'slug', 'activo', 'exclusiva',
        'stripe_secret_key', 'stripe_webhook_secret', 'stripe_publishable_key',
    ]


@admin.register(MembresiaEmpresa)
class MembresiaEmpresaAdmin(SoloOperadorPlataformaAdminMixin, ModelAdmin):
    """Salvo el alta vía la acción unificada 'Dar de alta vendedora' en
    `apps/bookings/admin.py` (Task B10) -- ese flujo crea la fila directo, sin
    pasar por este admin."""

    list_display = ['user', 'empresa', 'rol']
    list_filter = ['empresa', 'rol']
    autocomplete_fields = ['user', 'empresa']
```

- [ ] **Step 2: Verificar que el admin carga**

Run: `venv\Scripts\python.exe manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add backend/apps/tenancy/admin.py
git commit -m "feat(tenancy): admin de Sede/Empresa/MembresiaEmpresa, solo operador"
```

---

> **(Tarea duplicada eliminada del ensamblado — el fork de Tenancy tambien escribio bookings/admin.py UserAdmin/GroupAdmin fuera de su alcance asignado. Contenido real: Task B10, seccion Bookings, misma directiva original de esta pieza.)**

---

> **(Tarea duplicada eliminada del ensamblado — el fork de Tenancy tambien escribio setup_roles.py fuera de su alcance asignado. Contenido real: Task B15, seccion Bookings, misma directiva original de esta pieza.)**

---

### Task T10: `migrar_la_paz_a_empresa.py`

**Files:**
- Create: `backend/apps/tenancy/management/commands/__init__.py`
- Create: `backend/apps/tenancy/management/__init__.py`
- Create: `backend/apps/tenancy/management/commands/migrar_la_paz_a_empresa.py`
- Test: `backend/apps/tenancy/tests.py`

**Interfaces:**
- Consumes: grupos `Jefe`/`Vendedora`/`OperadorPlataforma` (Task B15, debe haber
  corrido antes), `Empresa(slug='sal-y-sol')` (Task T2, debe haber corrido antes).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/apps/tenancy/tests.py (agregar al final)
from django.core.management import call_command, CommandError
from io import StringIO


class MigrarLaPazAEmpresaTests(TestCase):
    def setUp(self):
        call_command('setup_roles', stdout=StringIO())
        sede = Sede.objects.create(nombre='La Paz', slug='la-paz')
        self.empresa = Empresa.objects.create(sede=sede, nombre='Sal y Sol', slug='sal-y-sol')

        self.operador = User.objects.create_superuser(username='admin_sistema', password='x')
        self.jefe1 = User.objects.create_superuser(username='jefe1', password='x')
        self.vendedora1 = User.objects.create_user(username='vend1', password='x', is_staff=True)
        self.vendedora1.groups.add(Group.objects.get(name='Vendedora'))

    def test_sin_operador_falla_explicito(self):
        with self.assertRaises(CommandError):
            call_command('migrar_la_paz_a_empresa', stdout=StringIO())

    def test_migra_operador_jefes_y_vendedoras(self):
        call_command('migrar_la_paz_a_empresa', operador='admin_sistema', stdout=StringIO())

        self.operador.refresh_from_db()
        self.assertFalse(self.operador.is_superuser)
        self.assertTrue(self.operador.groups.filter(name='OperadorPlataforma').exists())
        self.assertFalse(MembresiaEmpresa.objects.filter(user=self.operador).exists())

        self.jefe1.refresh_from_db()
        self.assertFalse(self.jefe1.is_superuser)
        self.assertTrue(self.jefe1.groups.filter(name='Jefe').exists())
        self.assertTrue(MembresiaEmpresa.objects.filter(
            user=self.jefe1, empresa=self.empresa, rol=MembresiaEmpresa.Rol.JEFE,
        ).exists())

        self.assertTrue(MembresiaEmpresa.objects.filter(
            user=self.vendedora1, empresa=self.empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
        ).exists())

    def test_dry_run_no_cambia_nada(self):
        call_command('migrar_la_paz_a_empresa', operador='admin_sistema', dry_run=True, stdout=StringIO())
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.is_superuser)
        self.assertFalse(MembresiaEmpresa.objects.exists())

    def test_sin_setup_roles_previo_falla_explicito(self):
        Group.objects.all().delete()
        with self.assertRaises(CommandError):
            call_command('migrar_la_paz_a_empresa', operador='admin_sistema', stdout=StringIO())

    def test_sin_empresa_sal_y_sol_falla_explicito(self):
        self.empresa.delete()
        with self.assertRaises(CommandError):
            call_command('migrar_la_paz_a_empresa', operador='admin_sistema', stdout=StringIO())
```

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests.MigrarLaPazAEmpresaTests -v 2`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Escribir el comando**

```python
# backend/apps/tenancy/management/__init__.py
```
```python
# backend/apps/tenancy/management/commands/__init__.py
```
```python
# backend/apps/tenancy/management/commands/migrar_la_paz_a_empresa.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.tenancy.models import Empresa, MembresiaEmpresa

User = get_user_model()


class Command(BaseCommand):
    help = 'Migra las cuentas de La Paz (is_superuser) a roles por Empresa.'

    def add_arguments(self, parser):
        parser.add_argument('--operador', required=True, help='username que pasa a OperadorPlataforma.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            grupo_jefe = Group.objects.get(name='Jefe')
            grupo_vendedora = Group.objects.get(name='Vendedora')
            grupo_operador = Group.objects.get(name='OperadorPlataforma')
        except Group.DoesNotExist:
            raise CommandError(
                "Los grupos Jefe/Vendedora/OperadorPlataforma no existen todavia. "
                "Correr 'manage.py setup_roles' primero."
            )

        try:
            empresa = Empresa.objects.get(slug='sal-y-sol')
        except Empresa.DoesNotExist:
            raise CommandError(
                "No existe la Empresa 'sal-y-sol'. Correr la migracion "
                "'tenancy.0002_crear_sede_empresa_la_paz' primero."
            )

        try:
            operador = User.objects.get(username=options['operador'])
        except User.DoesNotExist:
            raise CommandError(f"No existe el usuario '{options['operador']}'.")

        dry_run = options['dry_run']
        jefes = list(User.objects.filter(is_superuser=True).exclude(pk=operador.pk))
        vendedoras = list(User.objects.filter(groups=grupo_vendedora, is_superuser=False))

        self.stdout.write(f'Operador de plataforma: {operador.username}')
        self.stdout.write(f'Jefes a migrar: {[u.username for u in jefes]}')
        self.stdout.write(f'Vendedoras a migrar: {[u.username for u in vendedoras]}')

        if dry_run:
            self.stdout.write(self.style.WARNING('--dry-run: no se aplico ningun cambio.'))
            return

        with transaction.atomic():
            operador.groups.add(grupo_operador)
            operador.is_superuser = False
            operador.save(update_fields=['is_superuser'])

            for jefe in jefes:
                MembresiaEmpresa.objects.get_or_create(
                    user=jefe, empresa=empresa, defaults={'rol': MembresiaEmpresa.Rol.JEFE},
                )
                jefe.groups.add(grupo_jefe)
                jefe.is_superuser = False
                jefe.save(update_fields=['is_superuser'])

            for vendedora in vendedoras:
                MembresiaEmpresa.objects.get_or_create(
                    user=vendedora, empresa=empresa, defaults={'rol': MembresiaEmpresa.Rol.VENDEDORA},
                )

        self.stdout.write(self.style.SUCCESS(
            f'Migrados: 1 operador, {len(jefes)} jefe(s), {len(vendedoras)} vendedora(s).'
        ))
```

- [ ] **Step 4: Correr los tests, verificar que pasan**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests.MigrarLaPazAEmpresaTests -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/tenancy/management/
git commit -m "feat(tenancy): comando de migracion de roles La Paz a Empresa"
```

---

> **(Tarea duplicada eliminada del ensamblado — el fork de Tenancy tambien escribio config/settings/base.py fuera de su alcance asignado. Contenido real: Task I1, seccion Infra/CI/Settings/Frontend/Produccion, misma directiva original de esta pieza.)**

---

### Task T12: `tenancy/migrations/0003_rls.py` + `tests_rls.py`

**Files:**
- Create: `backend/apps/tenancy/migrations/0003_rls.py`
- Create: `backend/apps/tenancy/tests_rls.py`

**Interfaces:**
- Consumes: `fleet.migrations.0015_unicidad_por_empresa` (Task F4) y el equivalente
  de `bookings` (Task B, mismo nombre de archivo por convención de este plan:
  `00XX_unicidad_por_empresa`) — **esta migración debe declarar esas dos
  dependencias explícitas**, aunque al escribir esta tarea los archivos de
  `bookings` todavía no existan en disco. Sin ellas, las restricciones únicas
  globales de `fleet`/`bookings` siguen bloqueando una segunda Empresa por
  debajo de la política RLS.

- [ ] **Step 1: Escribir la migración**

```python
# backend/apps/tenancy/migrations/0003_rls.py
from django.db import migrations

TABLAS_CON_EMPRESA_ID = [
    'fleet_tarifa', 'fleet_extrasitem', 'fleet_transporteprecio',
    'fleet_puntoencuentro', 'fleet_codigopromocional', 'fleet_embarcacion',
    'fleet_capitan', 'fleet_embarcacionnodisponible',
    'bookings_reserva', 'bookings_cupodiario', 'bookings_vendedora',
]

SQL_POLITICA = """
ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenancy_alcance ON {tabla}
FOR ALL
USING (
  empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
  OR current_setting('app.operador_plataforma', true) = 'on'
);
"""

SQL_POLITICA_REVERSA = """
DROP POLICY IF EXISTS tenancy_alcance ON {tabla};
ALTER TABLE {tabla} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY;
"""

SQL_POLITICA_EXISTS = """
ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenancy_alcance ON {tabla}
FOR ALL
USING (
  EXISTS (
    SELECT 1 FROM bookings_reserva r
    WHERE r.id = {tabla}.reserva_id
      AND (r.empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
           OR current_setting('app.operador_plataforma', true) = 'on')
  )
);
"""

SQL_POLITICA_EXISTS_REVERSA = SQL_POLITICA_REVERSA


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0002_crear_sede_empresa_la_paz'),
        ('fleet', '0015_unicidad_por_empresa'),
        ('bookings', '00XX_unicidad_por_empresa'),  # nombre real lo fija Task B
    ]

    operations = (
        [
            migrations.RunSQL(
                SQL_POLITICA.format(tabla=tabla),
                SQL_POLITICA_REVERSA.format(tabla=tabla),
            )
            for tabla in TABLAS_CON_EMPRESA_ID
        ]
        + [
            migrations.RunSQL(
                SQL_POLITICA_EXISTS.format(tabla=tabla),
                SQL_POLITICA_EXISTS_REVERSA.format(tabla=tabla),
            )
            for tabla in ('bookings_reservaextra', 'bookings_reservatransporte')
        ]
    )
```

**Nota para quien integre con Task B:** actualizar el literal
`'00XX_unicidad_por_empresa'` de `dependencies` al nombre de archivo real que la
Task B le dé a su migración de paso 4 (mismo patrón de nombre que usa `fleet`,
pero confirmar el número exacto antes de correr `migrate` en cualquier entorno
compartido).

- [ ] **Step 2: Escribir `tests_rls.py`**

```python
# backend/apps/tenancy/tests_rls.py
from django.db import connection
from django.test import TransactionTestCase, skipUnless

from . import scope
from .models import Empresa, Sede


@skipUnless(connection.vendor == 'postgresql', 'RLS solo aplica en Postgres')
class RLSTests(TransactionTestCase):
    def setUp(self):
        sede = Sede.objects.create(nombre='La Paz', slug='la-paz')
        self.empresa_a = Empresa.objects.create(sede=sede, nombre='A', slug='empresa-a')
        self.empresa_b = Empresa.objects.create(sede=sede, nombre='B', slug='empresa-b')

    def test_rol_de_test_no_es_superusuario_ni_bypassrls(self):
        # Revision 5 (B6): primera aserción de la clase -- si esto falla, TODA
        # la suite de RLS pasaria en verde sin haber probado nada.
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user'
            )
            rolsuper, rolbypassrls = cursor.fetchone()
        if rolsuper or rolbypassrls:
            self.fail(
                f'El rol de test ({connection.settings_dict["USER"]}) tiene '
                f'rolsuper={rolsuper} rolbypassrls={rolbypassrls} -- RLS no '
                f'protege nada con este rol. Ver runbook de CI (seccion Infra).'
            )

    def test_dos_empresas_no_se_ven_por_orm(self):
        from apps.fleet.models import Embarcacion

        with scope.con_empresa(self.empresa_a):
            Embarcacion.objects.create(
                nombre='Panga A', clase='chica', capacidad_maxima=3, empresa=self.empresa_a,
            )
        with scope.con_empresa(self.empresa_b):
            Embarcacion.objects.create(
                nombre='Panga B', clase='chica', capacidad_maxima=3, empresa=self.empresa_b,
            )
            self.assertEqual(Embarcacion.objects.count(), 1)
            self.assertEqual(Embarcacion.objects.first().nombre, 'Panga B')

    def test_sin_set_local_devuelve_cero_filas_no_excepcion(self):
        from apps.fleet.models import Embarcacion

        with scope.con_empresa(self.empresa_a):
            Embarcacion.objects.create(
                nombre='Panga A', clase='chica', capacidad_maxima=3, empresa=self.empresa_a,
            )
        # Sin ningun con_empresa activo: SET LOCAL nunca se emitio en esta
        # transaccion nueva -- NULLIF(current_setting(...), '')::int es NULL,
        # la politica USING es NULL (falsa), cero filas.
        self.assertEqual(Embarcacion.objects.count(), 0)

    def test_insert_sin_alcance_falla(self):
        from django.db.utils import ProgrammingError
        from apps.fleet.models import Embarcacion

        with self.assertRaises(ProgrammingError):
            Embarcacion.objects.create(
                nombre='Sin alcance', clase='chica', capacidad_maxima=3, empresa=self.empresa_a,
            )
```

(Se retira el bloque `_Base`/`@skipUnlessDBFeature` de arriba si el repo no usa ese
decorador en ningún otro test — `skipUnless(connection.vendor == 'postgresql', ...)`
es el único mecanismo que hace falta, ya usado en el resto del código
(`bloquear_cupo_del_dia`). Dejar solo el `@skipUnless` real sobre `RLSTests`.)

- [ ] **Step 3: Correr en un entorno con Postgres (CI o local con Postgres),
  verificar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.tenancy.tests_rls -v 2`
Expected: PASS contra Postgres. En sqlite local, `skipUnless` salta la clase
completa (`OK (skipped=1)`), lo cual es el comportamiento esperado hasta que exista
un Postgres local o CI corra.

- [ ] **Step 4: Commit**

```bash
git add backend/apps/tenancy/migrations/0003_rls.py backend/apps/tenancy/tests_rls.py
git commit -m "feat(tenancy): politicas RLS + suite de verificacion contra Postgres"
```

---

## Self-Review (T1-T12)

**Cobertura:** app `tenancy` completa (modelos, scope, middleware, ambos admin
mixins, admin de registro, migraciones 0001-0003), la porción de `bookings/admin.py`
dueña de `UserAdmin`/`GroupAdmin` + alta unificada, `setup_roles.py` con los 3
grupos, `migrar_la_paz_a_empresa.py`, y el wiring de `config/settings/base.py`
(`INSTALLED_APPS`, `MIDDLEWARE`, sidebar, permiso de Finanzas).

**Verificado contra código real** (no solo la prosa del plan): `config/settings/base.py`
completo, `apps/bookings/admin.py` completo (confirmado: `CheckoutAbandonadoAdmin.get_queryset`
y `AgendaAdmin.get_queryset` en efecto no llaman `super()` hoy, tal como dice el
hallazgo N-B del plan — corregirlo es tarea de Task B, no de esta), `setup_roles.py`
completo (confirmado: hoy solo crea el grupo `Vendedora`, tal como dice el plan).

**Placeholders:** ninguno en las secciones de código de producción. El bloque
`_Base`/`@skipUnlessDBFeature` de la Task T12 se marca explícitamente como a
retirar en el mismo paso — no es un placeholder que sobreviva al commit.

**Decisión documentada para revisión del dueño del negocio:** el alcance exacto de
permisos de `Jefe` sobre el catálogo financiero (Task B15) no venía pinneado carácter
por carácter en el plan aprobado ("CRUD completo operativo" es la frase del
documento) — se decidió `add`/`change`/`view` sin `delete` en todo lo que antes
cubría `is_superuser`, coherente con la convención ya existente de "se cancela/
desmarca, no se borra". Confirmar con el dueño antes de desplegar a producción.

**Firmas expuestas (contrato para fleet/bookings/payments/infra):** ver el bloque
al inicio de este documento — sin cambios respecto a lo que Task F ya consumió.

---

### Fleet (F1-F9)

# Fleet Retrofit — Tasks F1-F9

> Sección del plan `docs/superpowers/plans/2026-08-31-expansion-multi-sede-pieza1-tenancy.md`
> (File Map aprobado tras 9 rondas de critic, ver marcador `<!-- arch-critic: APPROVED -->`
> al final de ese archivo). Cubre exclusivamente `apps/fleet/*`.

**Depende de (Task T, tenancy core, se escribe/ejecuta antes o en paralelo pero se
integra antes de correr estos tests):**
- `apps.tenancy.models.Empresa` — `slug` (único), `activo` (bool), FK inversa desde
  aquí vía `empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT)`.
- `apps.tenancy.scope.con_empresa(empresa)` — context manager no reentrante que fija
  `SET LOCAL app.current_empresa_id` (Postgres) dentro de `transaction.atomic()`.
- `apps.tenancy.scope.resolver_empresa_publica(slug)` — devuelve `Empresa` o levanta
  `Http404` (si no existe o `activo=False`).
- `apps.tenancy.admin_mixins.EmpresaScopedAdminMixin` — `get_queryset(self, request)`
  filtra por `scope.empresa_actual(request)` (sin filtrar si es operador de
  plataforma); `save_model(self, request, obj, form, change)` no reasigna `empresa`
  en edición, la autoasigna en creación si hay `empresa_actual`.
- `apps.tenancy.migrations.0002_crear_sede_empresa_la_paz` — crea la fila `Empresa`
  con `slug='sal-y-sol'` que usa el backfill de la Task F2.

Migraciones existentes de `fleet`: la última en disco es `0011_extrasitem_cantidad_editable`.
Este documento agrega `0012`-`0015`.

Comando de test (Windows, desde `backend/`): `venv\Scripts\python.exe manage.py test apps.fleet`

---

### Task F1: `empresa` FK nullable en los 8 modelos de fleet

**Files:**
- Modify: `backend/apps/fleet/models.py`
- Create: `backend/apps/fleet/migrations/0012_empresa_nullable.py`
- Test: `backend/apps/fleet/tests.py`

**Interfaces:**
- Consumes: `apps.tenancy.models.Empresa` (seccion Tenancy).
- Produces: campo `empresa` (nullable por ahora, `on_delete=PROTECT`) en `Tarifa`,
  `ExtrasItem`, `TransportePrecio`, `PuntoEncuentro`, `CodigoPromocional`,
  `Embarcacion`, `Capitan`, `EmbarcacionNoDisponible`. Las Tasks F2-F4 lo endurecen.

- [ ] **Step 1: Escribir el test que falla — el campo no existe todavía**

```python
# backend/apps/fleet/tests.py, agregar al final del archivo
class EmpresaFKTests(TestCase):
    def test_tarifa_tiene_campo_empresa(self):
        campo = Tarifa._meta.get_field('empresa')
        self.assertTrue(campo.null)
        self.assertEqual(campo.remote_field.on_delete.__name__, 'PROTECT')

    def test_embarcacionnodisponible_tiene_campo_empresa(self):
        campo = EmbarcacionNoDisponible._meta.get_field('empresa')
        self.assertTrue(campo.null)
```

- [ ] **Step 2: Correr el test, verificar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.fleet.tests.EmpresaFKTests -v 2`
Expected: FAIL — `FieldDoesNotExist: Tarifa has no field named 'empresa'`

- [ ] **Step 3: Agregar el campo a los 8 modelos**

```python
# backend/apps/fleet/models.py
# Agregar el import al inicio del archivo:
from django.conf import settings
# ... (imports existentes se quedan)

# En cada uno de los 8 modelos, agregar el campo (ejemplo con Tarifa —
# repetir la línea de campo, ajustando related_name, en los otros 7):

class Tarifa(models.Model):
    # ... campos existentes sin cambios ...
    empresa = models.ForeignKey(
        'tenancy.Empresa', on_delete=models.PROTECT, null=True, blank=True,
        related_name='tarifa',
    )
    # resto de la clase sin cambios en este paso (save()/actual() se tocan en F4)

class ExtrasItem(models.Model):
    # ... campos existentes ...
    empresa = models.ForeignKey(
        'tenancy.Empresa', on_delete=models.PROTECT, null=True, blank=True,
        related_name='extras_items',
    )

class TransportePrecio(models.Model):
    # ... campos existentes ...
    empresa = models.ForeignKey(
        'tenancy.Empresa', on_delete=models.PROTECT, null=True, blank=True,
        related_name='precios_transporte',
    )

class PuntoEncuentro(models.Model):
    # ... campos existentes ...
    empresa = models.ForeignKey(
        'tenancy.Empresa', on_delete=models.PROTECT, null=True, blank=True,
        related_name='puntos_encuentro',
    )

class CodigoPromocional(models.Model):
    # ... campos existentes ...
    empresa = models.ForeignKey(
        'tenancy.Empresa', on_delete=models.PROTECT, null=True, blank=True,
        related_name='codigos_promocionales',
    )

class Embarcacion(models.Model):
    # ... campos existentes ...
    empresa = models.ForeignKey(
        'tenancy.Empresa', on_delete=models.PROTECT, null=True, blank=True,
        related_name='embarcaciones',
    )

class Capitan(models.Model):
    # ... campos existentes ...
    empresa = models.ForeignKey(
        'tenancy.Empresa', on_delete=models.PROTECT, null=True, blank=True,
        related_name='capitanes',
    )

class EmbarcacionNoDisponible(models.Model):
    # ... campos existentes ...
    empresa = models.ForeignKey(
        'tenancy.Empresa', on_delete=models.PROTECT, null=True, blank=True,
        related_name='embarcaciones_no_disponibles',
    )
```

- [ ] **Step 4: Generar y revisar la migración**

Run: `venv\Scripts\python.exe manage.py makemigrations fleet --name empresa_nullable`

Verificar que el archivo generado (`backend/apps/fleet/migrations/0012_empresa_nullable.py`)
declara la dependencia cruzada a `tenancy` explícitamente — si `makemigrations` no la
agregó sola (Django no siempre detecta dependencias entre apps con FK de referencia
por string), agregarla a mano:

```python
# backend/apps/fleet/migrations/0012_empresa_nullable.py
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0011_extrasitem_cantidad_editable'),
        ('tenancy', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tarifa', name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='tarifa', to='tenancy.empresa'),
        ),
        migrations.AddField(
            model_name='extrasitem', name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='extras_items', to='tenancy.empresa'),
        ),
        migrations.AddField(
            model_name='transporteprecio', name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='precios_transporte', to='tenancy.empresa'),
        ),
        migrations.AddField(
            model_name='puntoencuentro', name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='puntos_encuentro', to='tenancy.empresa'),
        ),
        migrations.AddField(
            model_name='codigopromocional', name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='codigos_promocionales', to='tenancy.empresa'),
        ),
        migrations.AddField(
            model_name='embarcacion', name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='embarcaciones', to='tenancy.empresa'),
        ),
        migrations.AddField(
            model_name='capitan', name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='capitanes', to='tenancy.empresa'),
        ),
        migrations.AddField(
            model_name='embarcacionnodisponible', name='empresa',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='embarcaciones_no_disponibles', to='tenancy.empresa'),
        ),
    ]
```

- [ ] **Step 5: Correr el test, verificar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.fleet.tests.EmpresaFKTests -v 2`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/apps/fleet/models.py backend/apps/fleet/migrations/0012_empresa_nullable.py backend/apps/fleet/tests.py
git commit -m "feat(fleet): agrega FK empresa nullable a los 8 modelos tenant-scoped"
```

---

### Task F2: Backfill de `empresa` a la Empresa "Sal y Sol"

**Files:**
- Create: `backend/apps/fleet/migrations/0013_backfill_empresa.py`

**Interfaces:**
- Consumes: `apps.tenancy.migrations.0002_crear_sede_empresa_la_paz` (crea la fila
  `Empresa(slug='sal-y-sol')` — Task T). Esta migración debe declarar esa dependencia
  explícita aunque el archivo de `tenancy` todavía no exista en disco al escribir
  esta tarea; el nombre `tenancy.0002_crear_sede_empresa_la_paz` es el contrato fijado
  por el plan.

No hay test unitario de Django para una `RunPython` de datos — se verifica corriendo
`migrate` contra una base con filas preexistentes y confirmando el conteo.

- [ ] **Step 1: Escribir la migración de datos**

```python
# backend/apps/fleet/migrations/0013_backfill_empresa.py
from django.db import migrations


def asignar_empresa(apps, schema_editor):
    Empresa = apps.get_model('tenancy', 'Empresa')
    empresa = Empresa.objects.get(slug='sal-y-sol')

    for nombre_modelo in (
        'Tarifa', 'ExtrasItem', 'TransportePrecio', 'PuntoEncuentro',
        'CodigoPromocional', 'Embarcacion', 'Capitan', 'EmbarcacionNoDisponible',
    ):
        Modelo = apps.get_model('fleet', nombre_modelo)
        Modelo.objects.filter(empresa__isnull=True).update(empresa=empresa)


def revertir(apps, schema_editor):
    for nombre_modelo in (
        'Tarifa', 'ExtrasItem', 'TransportePrecio', 'PuntoEncuentro',
        'CodigoPromocional', 'Embarcacion', 'Capitan', 'EmbarcacionNoDisponible',
    ):
        Modelo = apps.get_model('fleet', nombre_modelo)
        Modelo.objects.update(empresa=None)


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0012_empresa_nullable'),
        ('tenancy', '0002_crear_sede_empresa_la_paz'),
    ]

    operations = [
        migrations.RunPython(asignar_empresa, revertir),
    ]
```

- [ ] **Step 2: Verificar manualmente contra la base local**

Run:
```
venv\Scripts\python.exe manage.py migrate fleet 0013
venv\Scripts\python.exe manage.py shell -c "from apps.fleet.models import Tarifa; print(Tarifa.objects.filter(empresa__isnull=True).count())"
```
Expected: `0` (ninguna fila de `Tarifa` preexistente se queda sin `empresa`). Repetir
la verificación para `Embarcacion`/`CodigoPromocional` si la base local tiene filas.

- [ ] **Step 3: Commit**

```bash
git add backend/apps/fleet/migrations/0013_backfill_empresa.py
git commit -m "feat(fleet): backfill de empresa a Sal y Sol para filas existentes"
```

---

### Task F3: `empresa` pasa a `NOT NULL`

**Files:**
- Modify: `backend/apps/fleet/models.py`
- Create: `backend/apps/fleet/migrations/0014_empresa_no_null.py`
- Test: `backend/apps/fleet/tests.py`

**Interfaces:**
- Produces: campo `empresa` obligatorio (`null=False`) en los 8 modelos.

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/apps/fleet/tests.py
class EmpresaFKTests(TestCase):
    # ... tests de F1 sin cambios ...

    def test_empresa_es_obligatoria_en_tarifa(self):
        campo = Tarifa._meta.get_field('empresa')
        self.assertFalse(campo.null)
```

- [ ] **Step 2: Correr el test, verificar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.fleet.tests.EmpresaFKTests.test_empresa_es_obligatoria_en_tarifa -v 2`
Expected: FAIL — `AssertionError: True is not false`

- [ ] **Step 3: Quitar `null=True, blank=True` en los 8 campos**

```python
# backend/apps/fleet/models.py — en cada uno de los 8 modelos, la línea del campo
# `empresa` pasa de:
#   empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, null=True, blank=True, related_name='...')
# a:
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='...')
```

(Aplicar el mismo cambio — quitar `null=True, blank=True` — a los 8 campos agregados
en la Task F1: `Tarifa.empresa`, `ExtrasItem.empresa`, `TransportePrecio.empresa`,
`PuntoEncuentro.empresa`, `CodigoPromocional.empresa`, `Embarcacion.empresa`,
`Capitan.empresa`, `EmbarcacionNoDisponible.empresa`.)

- [ ] **Step 4: Generar la migración**

Run: `venv\Scripts\python.exe manage.py makemigrations fleet --name empresa_no_null`

```python
# backend/apps/fleet/migrations/0014_empresa_no_null.py
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0013_backfill_empresa'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tarifa', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tarifa', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='extrasitem', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='extras_items', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='transporteprecio', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='precios_transporte', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='puntoencuentro', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='puntos_encuentro', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='codigopromocional', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='codigos_promocionales', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='embarcacion', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='embarcaciones', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='capitan', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='capitanes', to='tenancy.empresa'),
        ),
        migrations.AlterField(
            model_name='embarcacionnodisponible', name='empresa',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='embarcaciones_no_disponibles', to='tenancy.empresa'),
        ),
    ]
```

- [ ] **Step 5: Correr el test, verificar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.fleet.tests.EmpresaFKTests -v 2`
Expected: PASS (las dos pruebas de F1 y la nueva de F3)

- [ ] **Step 6: Commit**

```bash
git add backend/apps/fleet/models.py backend/apps/fleet/migrations/0014_empresa_no_null.py backend/apps/fleet/tests.py
git commit -m "feat(fleet): empresa pasa a obligatoria en los 8 modelos"
```

---

### Task F4: Unicidad por Empresa — `Tarifa.de(empresa)` reemplaza `Tarifa.actual()`, y las 3 restricciones globales pasan a ser por Empresa

**Files:**
- Modify: `backend/apps/fleet/models.py`
- Create: `backend/apps/fleet/migrations/0015_unicidad_por_empresa.py`
- Test: `backend/apps/fleet/tests.py`

**Interfaces:**
- Produces: `Tarifa.de(cls, empresa)` (classmethod, reemplaza `Tarifa.actual()`, que
  se elimina). `Tarifa` gana `UniqueConstraint(fields=['empresa'], name='tarifa_unica_por_empresa')`
  en vez de forzar `pk=1`. `TransportePrecio.zona`, `CodigoPromocional.codigo`,
  `Embarcacion.nombre` dejan de ser `unique=True` global y pasan a
  `UniqueConstraint(fields=['<campo>', 'empresa'], name='<modelo>_<campo>_unico_por_empresa')`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/apps/fleet/tests.py
# Reemplazar TarifaTests.test_es_singleton (usa Tarifa.actual(), que se elimina):

class TarifaTests(TestCase):
    def setUp(self):
        self.empresa_a = _crear_empresa(slug='empresa-a')
        self.empresa_b = _crear_empresa(slug='empresa-b')

    def test_una_tarifa_por_empresa(self):
        Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
        Tarifa.objects.create(precio=Decimal('5000.00'), empresa=self.empresa_a)
        self.assertEqual(Tarifa.objects.filter(empresa=self.empresa_a).count(), 1)
        self.assertEqual(Tarifa.de(self.empresa_a).precio, Decimal('5000.00'))

    def test_cada_empresa_tiene_su_propia_tarifa(self):
        Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
        Tarifa.objects.create(precio=Decimal('3000.00'), empresa=self.empresa_b)
        self.assertEqual(Tarifa.de(self.empresa_a).precio, Decimal('4500.00'))
        self.assertEqual(Tarifa.de(self.empresa_b).precio, Decimal('3000.00'))

    def test_sin_tarifa_de_devuelve_none(self):
        self.assertIsNone(Tarifa.de(self.empresa_b))

    def test_precio_por_moneda(self):
        tarifa = Tarifa.objects.create(
            precio=Decimal('4500.00'), precio_usd=Decimal('260.00'), empresa=self.empresa_a,
        )
        self.assertEqual(tarifa.precio_en('MXN'), Decimal('4500.00'))
        self.assertEqual(tarifa.precio_en('USD'), Decimal('260.00'))

    def test_sin_precio_en_dolares_devuelve_none(self):
        tarifa = Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
        self.assertIsNone(tarifa.precio_en('USD'))


# Agregar clase nueva de test de unicidad por empresa (usa TransactionTestCase por el
# IntegrityError, mismo patrón que EmbarcacionNoDisponibleUnicidadTests):

class UnicidadPorEmpresaTests(TransactionTestCase):
    def setUp(self):
        self.empresa_a = _crear_empresa(slug='empresa-a')
        self.empresa_b = _crear_empresa(slug='empresa-b')

    def test_zona_de_transporte_repetida_en_la_misma_empresa_falla(self):
        TransportePrecio.objects.create(
            zona='centro', precio_base=Decimal('2000'), empresa=self.empresa_a,
        )
        with self.assertRaises(IntegrityError):
            TransportePrecio.objects.create(
                zona='centro', precio_base=Decimal('2100'), empresa=self.empresa_a,
            )

    def test_zona_de_transporte_repetida_entre_empresas_distintas_es_valida(self):
        TransportePrecio.objects.create(
            zona='centro', precio_base=Decimal('2000'), empresa=self.empresa_a,
        )
        TransportePrecio.objects.create(
            zona='centro', precio_base=Decimal('1800'), empresa=self.empresa_b,
        )
        self.assertEqual(TransportePrecio.objects.count(), 2)

    def test_codigo_promocional_repetido_en_la_misma_empresa_falla(self):
        CodigoPromocional.objects.create(
            codigo='VERANO10', porcentaje_descuento=Decimal('10'), empresa=self.empresa_a,
        )
        with self.assertRaises(IntegrityError):
            CodigoPromocional.objects.create(
                codigo='VERANO10', porcentaje_descuento=Decimal('15'), empresa=self.empresa_a,
            )

    def test_codigo_promocional_repetido_entre_empresas_es_valido(self):
        CodigoPromocional.objects.create(
            codigo='VERANO10', porcentaje_descuento=Decimal('10'), empresa=self.empresa_a,
        )
        CodigoPromocional.objects.create(
            codigo='VERANO10', porcentaje_descuento=Decimal('20'), empresa=self.empresa_b,
        )
        self.assertEqual(CodigoPromocional.objects.count(), 2)

    def test_nombre_de_embarcacion_repetido_en_la_misma_empresa_falla(self):
        Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa_a,
        )
        with self.assertRaises(IntegrityError):
            Embarcacion.objects.create(
                nombre='Lupita', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
                empresa=self.empresa_a,
            )

    def test_nombre_de_embarcacion_repetido_entre_empresas_es_valido(self):
        Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa_a,
        )
        Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
            empresa=self.empresa_b,
        )
        self.assertEqual(Embarcacion.objects.count(), 2)
```

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `venv\Scripts\python.exe manage.py test apps.fleet.tests.TarifaTests apps.fleet.tests.UnicidadPorEmpresaTests -v 2`
Expected: FAIL — `AttributeError: type object 'Tarifa' has no attribute 'de'` y las
pruebas de unicidad no lanzan `IntegrityError` todavía (las columnas siguen con
`unique=True` global, así que en realidad sírevientan pero por la razón equivocada:
zona/código/nombre repetidos entre `empresa_a` y `empresa_b` también fallan hoy).

- [ ] **Step 3: Reescribir `Tarifa` y las 3 restricciones globales**

```python
# backend/apps/fleet/models.py

class Tarifa(models.Model):
    """... (docstring sin cambios) ..."""

    precio = models.DecimalField(max_digits=10, decimal_places=2, help_text='Precio del tour en pesos (MXN).')
    precio_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Precio del tour en dolares. Vacio = no se ofrece pago en USD.')
    precio_persona_extra = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Cargo en pesos por cada persona arriba de las incluidas en el precio del viaje. 0 = el precio no cambia con el numero de personas.')
    precio_persona_extra_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='El mismo cargo en dolares. Vacio = no se puede cobrar en USD un viaje que lleve personas extra.')
    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='tarifa')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['empresa'], name='tarifa_unica_por_empresa'),
        ]

    def save(self, *args, force_insert=False, **kwargs):
        # Una tarifa por Empresa, no una tarifa por sistema: un segundo
        # Tarifa.objects.create(empresa=X) debe actualizar el precio de X, no
        # reventar con IntegrityError sobre la UniqueConstraint de arriba.
        if not self.pk:
            existente = Tarifa.objects.filter(empresa=self.empresa).first()
            if existente:
                self.pk = existente.pk
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('La tarifa no se puede eliminar, solo editar.')

    def __str__(self):
        return f'Tarifa de {self.empresa}: ${self.precio} MXN'

    @classmethod
    def de(cls, empresa):
        return cls.objects.filter(empresa=empresa).first()

    def precio_en(self, moneda):
        return self.precio if moneda == 'MXN' else self.precio_usd

    def persona_extra_en(self, moneda):
        return self.precio_persona_extra if moneda == 'MXN' else self.precio_persona_extra_usd
```

```python
# TransportePrecio: quitar unique=True de zona, agregar UniqueConstraint
class TransportePrecio(models.Model):
    # ... Zona sin cambios ...
    zona = models.CharField(max_length=10, choices=Zona.choices)  # unique=True retirado
    # ... resto de campos sin cambios, empresa ya agregado en F1/F3 ...

    class Meta:
        ordering = ['zona']
        verbose_name = 'precio de transporte'
        verbose_name_plural = 'precios de transporte'
        constraints = [
            models.UniqueConstraint(fields=['zona', 'empresa'], name='transporteprecio_zona_unica_por_empresa'),
        ]
```

```python
# CodigoPromocional: quitar unique=True de codigo, agregar UniqueConstraint
class CodigoPromocional(models.Model):
    codigo = models.CharField(max_length=20)  # unique=True retirado
    # ... resto de campos sin cambios ...

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'codigo promocional'
        verbose_name_plural = 'codigos promocionales'
        constraints = [
            models.UniqueConstraint(fields=['codigo', 'empresa'], name='codigopromocional_codigo_unico_por_empresa'),
        ]
```

```python
# Embarcacion: quitar unique=True de nombre, agregar UniqueConstraint
class Embarcacion(models.Model):
    # ... Clase sin cambios ...
    nombre = models.CharField(max_length=100)  # unique=True retirado
    # ... resto de campos sin cambios ...

    class Meta:
        ordering = ['nombre']
        constraints = [
            models.UniqueConstraint(fields=['nombre', 'empresa'], name='embarcacion_nombre_unico_por_empresa'),
        ]
```

- [ ] **Step 4: `capacidades_por_fecha`/`capacidades_disponibles` reciben `empresa`**

```python
# backend/apps/fleet/models.py

def capacidades_por_fecha(desde, hasta, empresa):
    """Capacidad de cada panga que puede salir, por dia, de mayor a menor, para
    esa Empresa. Firma cambia: `empresa` es obligatorio — sin filtro por Empresa,
    en sqlite/tests la flota de una Empresa cuenta como capacidad de otra."""
    activas = list(
        Embarcacion.objects.filter(activa=True, empresa=empresa)
        .values_list('id', 'capacidad_maxima')
    )

    fuera = defaultdict(set)
    for fecha, embarcacion_id in EmbarcacionNoDisponible.objects.filter(
        fecha__range=(desde, hasta), empresa=empresa
    ).values_list('fecha', 'embarcacion_id'):
        fuera[fecha].add(embarcacion_id)

    dias = (hasta - desde).days + 1
    return {
        fecha: sorted(
            (capacidad for pk, capacidad in activas if pk not in fuera[fecha]), reverse=True
        )
        for fecha in (desde + timedelta(days=i) for i in range(dias))
    }


def capacidades_disponibles(fecha, empresa):
    """Las capacidades a flote ese dia para esa Empresa, de mayor a menor."""
    return capacidades_por_fecha(fecha, fecha, empresa)[fecha]
```

- [ ] **Step 5: Actualizar `CapacidadesDisponiblesTests` a la firma nueva**

```python
# backend/apps/fleet/tests.py
class CapacidadesDisponiblesTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')
        self.fecha = date.today() + timedelta(days=10)
        self.chica = Embarcacion.objects.create(
            nombre='Chuy', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
            empresa=self.empresa,
        )
        self.grande = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa,
        )

    def test_devuelve_las_capacidades_de_mayor_a_menor(self):
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [5, 3])

    def test_excluye_las_inactivas(self):
        self.grande.activa = False
        self.grande.save()
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [3])

    def test_excluye_la_marcada_no_disponible_solo_ese_dia(self):
        EmbarcacionNoDisponible.objects.create(
            fecha=self.fecha, embarcacion=self.grande, motivo='Mantenimiento',
            empresa=self.empresa,
        )
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [3])
        self.assertEqual(
            capacidades_disponibles(self.fecha + timedelta(days=1), self.empresa), [5, 3],
        )

    def test_el_rango_no_hace_una_consulta_por_dia(self):
        with self.assertNumQueries(2):
            capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=89), self.empresa)

    def test_el_rango_trae_una_entrada_por_dia(self):
        rango = capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=2), self.empresa)
        self.assertEqual(len(rango), 3)
        self.assertEqual(rango[self.fecha], [5, 3])

    def test_pangas_de_otra_empresa_no_cuentan(self):
        otra_empresa = _crear_empresa(slug='empresa-b')
        Embarcacion.objects.create(
            nombre='Otra panga', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=6,
            empresa=otra_empresa,
        )
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [5, 3])
```

- [ ] **Step 6: Generar la migración**

Run: `venv\Scripts\python.exe manage.py makemigrations fleet --name unicidad_por_empresa`

```python
# backend/apps/fleet/migrations/0015_unicidad_por_empresa.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fleet', '0014_empresa_no_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transporteprecio', name='zona',
            field=models.CharField(choices=[('centro', 'Centro'), ('periferia', 'Periferia')], max_length=10),
        ),
        migrations.AlterField(
            model_name='codigopromocional', name='codigo',
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name='embarcacion', name='nombre',
            field=models.CharField(max_length=100),
        ),
        migrations.AddConstraint(
            model_name='tarifa',
            constraint=models.UniqueConstraint(fields=['empresa'], name='tarifa_unica_por_empresa'),
        ),
        migrations.AddConstraint(
            model_name='transporteprecio',
            constraint=models.UniqueConstraint(fields=['zona', 'empresa'], name='transporteprecio_zona_unica_por_empresa'),
        ),
        migrations.AddConstraint(
            model_name='codigopromocional',
            constraint=models.UniqueConstraint(fields=['codigo', 'empresa'], name='codigopromocional_codigo_unico_por_empresa'),
        ),
        migrations.AddConstraint(
            model_name='embarcacion',
            constraint=models.UniqueConstraint(fields=['nombre', 'empresa'], name='embarcacion_nombre_unico_por_empresa'),
        ),
    ]
```

**Nota para quien escriba `tenancy/migrations/0003_rls.py` (seccion Tenancy):** esa migración
debe declarar `('fleet', '0015_unicidad_por_empresa')` como dependencia — antes de que
esta corra, las restricciones únicas globales de esta pieza siguen bloqueando una
segunda Empresa por debajo de la política RLS.

- [ ] **Step 7: Correr los tests, verificar que pasan**

Run: `venv\Scripts\python.exe manage.py test apps.fleet -v 2`
Expected: PASS — todos los de `TarifaTests`, `UnicidadPorEmpresaTests`,
`CapacidadesDisponiblesTests`.

- [ ] **Step 8: Commit**

```bash
git add backend/apps/fleet/models.py backend/apps/fleet/migrations/0015_unicidad_por_empresa.py backend/apps/fleet/tests.py
git commit -m "feat(fleet): unicidad por empresa en tarifa/transporte/codigo/embarcacion"
```

---

### Task F5: Admin de fleet escopeado por Empresa

**Files:**
- Modify: `backend/apps/fleet/admin.py`

**Interfaces:**
- Consumes: `apps.tenancy.admin_mixins.EmpresaScopedAdminMixin`,
  `apps.tenancy.scope.empresa_actual(request)` (seccion Tenancy).

No hay test unitario nuevo en esta tarea — el aislamiento del admin lo prueba
`apps.tenancy.tests` (Task T, `EmpresaScopedAdminMixin` genérico) más los tests de
`fleet` ya escritos. Aquí solo se verifica manualmente que el admin sigue cargando.

- [ ] **Step 1: Heredar el mixin en los 7 `ModelAdmin` y corregir `TarifaAdmin`**

```python
# backend/apps/fleet/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.tenancy import scope
from apps.tenancy.admin_mixins import EmpresaScopedAdminMixin

from .models import (
    Capitan,
    CodigoPromocional,
    Embarcacion,
    EmbarcacionNoDisponible,
    ExtrasItem,
    PuntoEncuentro,
    Tarifa,
    TransportePrecio,
)


@admin.register(Tarifa)
class TarifaAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'precio', 'precio_usd', 'precio_persona_extra', 'precio_persona_extra_usd',
        'actualizado_en', 'actualizado_por',
    ]
    readonly_fields = ['actualizado_en', 'actualizado_por']

    def has_add_permission(self, request):
        empresa = scope.empresa_actual(request)
        if empresa is None:
            # Operador de plataforma: sin empresa_actual, no hay singleton que
            # guardar — el formulario exige elegir Empresa explícitamente
            # (ver EmpresaScopedAdminMixin.get_fields).
            return True
        return not Tarifa.objects.filter(empresa=empresa).exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.actualizado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(ExtrasItem)
class ExtrasItemAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'nombre', 'tipo', 'precio', 'precio_usd', 'cobrar_por_persona',
        'cantidad_editable', 'preseleccionado', 'activo',
    ]
    list_filter = ['tipo', 'activo']
    list_editable = ['precio', 'precio_usd', 'cantidad_editable', 'activo']
    search_fields = ['nombre']


@admin.register(TransportePrecio)
class TransportePrecioAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'zona', 'precio_base', 'precio_base_usd', 'recargo_grupo', 'recargo_grupo_usd',
        'min_personas_recargo', 'activo',
    ]
    list_editable = ['precio_base', 'precio_base_usd', 'recargo_grupo', 'recargo_grupo_usd', 'activo']


@admin.register(PuntoEncuentro)
class PuntoEncuentroAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'zona', 'activo']
    list_filter = ['zona', 'activo']
    list_editable = ['zona', 'activo']
    search_fields = ['nombre']


@admin.register(CodigoPromocional)
class CodigoPromocionalAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = [
        'codigo', 'porcentaje_descuento', 'activo', 'usos_maximos',
        'usos_maximos_por_cliente', 'fecha_inicio', 'fecha_fin',
    ]
    list_filter = ['activo']
    list_editable = ['porcentaje_descuento', 'activo']
    search_fields = ['codigo', 'descripcion']
    readonly_fields = ['creado_por', 'creado_en', 'actualizado_en']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Embarcacion)
class EmbarcacionAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'clase', 'capacidad_maxima', 'activa']
    list_filter = ['clase', 'activa']
    list_editable = ['activa']
    search_fields = ['nombre']


@admin.register(Capitan)
class CapitanAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['nombre', 'telefono']
    search_fields = ['nombre', 'telefono']


@admin.register(EmbarcacionNoDisponible)
class EmbarcacionNoDisponibleAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    list_display = ['fecha', 'embarcacion', 'motivo', 'registrado_por']
    list_filter = ['fecha', 'embarcacion']
    autocomplete_fields = ['embarcacion']
    readonly_fields = ['registrado_por', 'creado_en']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.registrado_por = request.user
        super().save_model(request, obj, form, change)
```

Nota: `EmpresaScopedAdminMixin` va primero en la herencia (MRO explícito) para que su
`get_queryset`/`save_model` tomen precedencia sobre `ModelAdmin` — mismo patrón exigido
en el resto del plan para `TarifaAdmin`/`UserAdmin`.

- [ ] **Step 2: Verificar manualmente que el admin sigue cargando**

Run: `venv\Scripts\python.exe manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add backend/apps/fleet/admin.py
git commit -m "feat(fleet): admin escopeado por empresa con EmpresaScopedAdminMixin"
```

---

### Task F6: `seed_extras` recibe `empresa` obligatorio

**Files:**
- Modify: `backend/apps/fleet/management/commands/seed_extras.py`
- Test: `backend/apps/fleet/tests.py`

**Interfaces:**
- Consumes: `apps.tenancy.models.Empresa`.
- Produces: `manage.py seed_extras --empresa <slug>` (antes no tomaba argumentos).

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/apps/fleet/tests.py
from django.core.management import call_command
from io import StringIO

class SeedExtrasTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')

    def test_siembra_el_catalogo_para_la_empresa_dada(self):
        call_command('seed_extras', empresa='empresa-a', stdout=StringIO())
        self.assertEqual(ExtrasItem.objects.filter(empresa=self.empresa).count(), 3)
        self.assertEqual(TransportePrecio.objects.filter(empresa=self.empresa).count(), 2)
        self.assertEqual(PuntoEncuentro.objects.filter(empresa=self.empresa).count(), 1)

    def test_es_idempotente(self):
        call_command('seed_extras', empresa='empresa-a', stdout=StringIO())
        call_command('seed_extras', empresa='empresa-a', stdout=StringIO())
        self.assertEqual(ExtrasItem.objects.filter(empresa=self.empresa).count(), 3)

    def test_sin_empresa_falla_explicito(self):
        with self.assertRaises(Exception):
            call_command('seed_extras', stdout=StringIO())
```

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `venv\Scripts\python.exe manage.py test apps.fleet.tests.SeedExtrasTests -v 2`
Expected: FAIL — `TypeError`/`CommandError: unrecognized arguments: --empresa`

- [ ] **Step 3: Agregar el argumento y pasar `empresa=` a los 6 `get_or_create`**

```python
# backend/apps/fleet/management/commands/seed_extras.py
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.fleet.models import ExtrasItem, PuntoEncuentro, TransportePrecio
from apps.tenancy import scope
from apps.tenancy.models import Empresa

PLACEHOLDER_BRUNCH = Decimal('300.00')
PLACEHOLDER_LICENCIA = Decimal('450.00')
PLACEHOLDER_CARNADA = Decimal('200.00')
PRECIO_CENTRO = Decimal('2000.00')
PRECIO_PERIFERIA = Decimal('1800.00')
RECARGO_GRUPO = Decimal('1500.00')
MIN_PERSONAS_RECARGO = 4


class Command(BaseCommand):
    help = 'Siembra el catalogo inicial de extras del checkout para una Empresa (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--empresa', required=True,
            help='Slug de la Empresa a sembrar (apps.tenancy.models.Empresa.slug).',
        )

    def handle(self, *args, **options):
        try:
            empresa = Empresa.objects.get(slug=options['empresa'])
        except Empresa.DoesNotExist:
            raise CommandError(f"No existe una Empresa con slug '{options['empresa']}'.")

        creados = 0
        with scope.con_empresa(empresa):
            _, nuevo = ExtrasItem.objects.get_or_create(
                tipo='brunch', nombre='Paquete de Brunch', empresa=empresa,
                defaults={
                    'descripcion': 'Desayuno y comida. El menu varia cada semana. Incluye '
                                   'bebidas (agua y refrescos) y snacks para el viaje.',
                    'precio': PLACEHOLDER_BRUNCH, 'precio_usd': None,
                    'cobrar_por_persona': True, 'preseleccionado': False, 'activo': True,
                },
            )
            creados += nuevo

            _, nuevo = ExtrasItem.objects.get_or_create(
                tipo='licencia', nombre='Licencia de pesca', empresa=empresa,
                defaults={
                    'precio': PLACEHOLDER_LICENCIA, 'precio_usd': None,
                    'cobrar_por_persona': True, 'preseleccionado': True, 'activo': True,
                    'cantidad_editable': True,
                },
            )
            creados += nuevo

            _, nuevo = ExtrasItem.objects.get_or_create(
                tipo='carnada', nombre='Carnada', empresa=empresa,
                defaults={
                    'precio': PLACEHOLDER_CARNADA, 'precio_usd': None,
                    'cobrar_por_persona': False, 'preseleccionado': True, 'activo': True,
                },
            )
            creados += nuevo

            _, nuevo = TransportePrecio.objects.get_or_create(
                zona='centro', empresa=empresa,
                defaults={
                    'precio_base': PRECIO_CENTRO, 'precio_base_usd': None,
                    'recargo_grupo': RECARGO_GRUPO, 'recargo_grupo_usd': None,
                    'min_personas_recargo': MIN_PERSONAS_RECARGO, 'activo': True,
                },
            )
            creados += nuevo

            _, nuevo = TransportePrecio.objects.get_or_create(
                zona='periferia', empresa=empresa,
                defaults={
                    'precio_base': PRECIO_PERIFERIA, 'precio_base_usd': None,
                    'recargo_grupo': RECARGO_GRUPO, 'recargo_grupo_usd': None,
                    'min_personas_recargo': MIN_PERSONAS_RECARGO, 'activo': True,
                },
            )
            creados += nuevo

            _, nuevo = PuntoEncuentro.objects.get_or_create(
                nombre='Marina La Costa', empresa=empresa, defaults={'zona': 'centro', 'activo': True},
            )
            creados += nuevo

        self.stdout.write(self.style.SUCCESS(
            f"Catalogo de '{empresa.slug}' listo ({creados} filas nuevas)."
        ))
```

Nota: `--empresa` es obligatorio (`required=True`) — sin él, `argparse` levanta
`CommandError` antes de entrar a `handle()`, que es lo que `test_sin_empresa_falla_explicito`
verifica.

- [ ] **Step 4: Correr los tests, verificar que pasan**

Run: `venv\Scripts\python.exe manage.py test apps.fleet.tests.SeedExtrasTests -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/fleet/management/commands/seed_extras.py backend/apps/fleet/tests.py
git commit -m "feat(fleet): seed_extras siembra por empresa, ya no global"
```

---

### Task F7: Catálogo público de fleet resuelve por `empresa_slug`

**Files:**
- Modify: `backend/apps/fleet/views.py`

**Interfaces:**
- Consumes: `apps.tenancy.scope.resolver_empresa_publica(slug)`,
  `apps.tenancy.scope.con_empresa(empresa)`, `Tarifa.de(empresa)` (Task F4).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# backend/apps/fleet/tests.py
class TarifaApiTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')

    def test_sin_tarifa_responde_503(self):
        self.assertEqual(self.client.get('/api/empresa-a/tarifa/').status_code, 503)

    def test_devuelve_todas_las_cifras_del_checkout(self):
        with scope.con_empresa(self.empresa):
            Tarifa.objects.create(
                precio=Decimal('4500.00'), precio_usd=Decimal('260.00'),
                precio_persona_extra=Decimal('500.00'), empresa=self.empresa,
            )
        body = self.client.get('/api/empresa-a/tarifa/').json()
        self.assertEqual(body['precio'], '4500.00')
        self.assertEqual(body['precio_usd'], '260.00')
        self.assertEqual(body['precio_persona_extra'], '500.00')
        self.assertEqual(body['personas_incluidas'], PERSONAS_INCLUIDAS)

    def test_empresa_inexistente_responde_404(self):
        self.assertEqual(self.client.get('/api/no-existe/tarifa/').status_code, 404)

    def test_no_ve_la_tarifa_de_otra_empresa(self):
        otra = _crear_empresa(slug='empresa-b')
        with scope.con_empresa(otra):
            Tarifa.objects.create(precio=Decimal('9999.00'), empresa=otra)
        self.assertEqual(self.client.get('/api/empresa-a/tarifa/').status_code, 503)
```

(Import nuevo al inicio de `tests.py`: `from apps.tenancy import scope`.)

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `venv\Scripts\python.exe manage.py test apps.fleet.tests.TarifaApiTests -v 2`
Expected: FAIL — 404 en vez de 503/200 (la URL sin prefijo `empresa_slug` no existe
todavía).

- [ ] **Step 3: Reescribir las vistas**

```python
# backend/apps/fleet/views.py
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy import scope

from .models import ExtrasItem, PuntoEncuentro, Tarifa, TransportePrecio
from .serializers import (
    ExtrasItemSerializer,
    PuntoEncuentroSerializer,
    TarifaSerializer,
    TransportePrecioSerializer,
)

PERSONAS_MAXIMO_PREVIEW = 50


class TarifaView(APIView):
    """Precio unico del tour de una Empresa, para que el checkout de la web no lo hardcodee."""

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            tarifa = Tarifa.de(empresa)
            if tarifa is None:
                return Response({'detail': 'Tarifa no configurada.'}, status=503)
            return Response(TarifaSerializer(tarifa).data)


class ExtrasPublicosView(APIView):
    """Catalogo de extras del checkout de una Empresa, con el monto ya resuelto
    para `personas`/`moneda`."""

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)

        moneda = request.query_params.get('moneda', 'MXN')
        if moneda not in ('MXN', 'USD'):
            return Response({'detail': 'moneda invalida.'}, status=400)

        crudo = request.query_params.get('personas', '1')
        try:
            personas = int(crudo)
        except ValueError:
            return Response({'detail': 'personas invalida.'}, status=400)
        if not (1 <= personas <= PERSONAS_MAXIMO_PREVIEW):
            return Response({'detail': 'personas invalida.'}, status=400)

        contexto = {'personas': personas, 'moneda': moneda}
        with scope.con_empresa(empresa):
            return Response({
                'extras': ExtrasItemSerializer(
                    ExtrasItem.objects.filter(activo=True, empresa=empresa), many=True, context=contexto
                ).data,
                'transporte': TransportePrecioSerializer(
                    TransportePrecio.objects.filter(activo=True, empresa=empresa), many=True, context=contexto
                ).data,
                'puntos_encuentro': PuntoEncuentroSerializer(
                    PuntoEncuentro.objects.filter(activo=True, empresa=empresa), many=True
                ).data,
            })
```

- [ ] **Step 4: Correr los tests, verificar que pasan (junto con F8, la URL nueva)**

Run (después de completar también la Task F8, que agrega el prefijo de ruta):
`venv\Scripts\python.exe manage.py test apps.fleet.tests.TarifaApiTests apps.fleet.tests.ExtrasPublicosApiTests -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/fleet/views.py
git commit -m "feat(fleet): catalogo publico resuelve empresa por slug de URL"
```

---

### Task F8: Rutas de fleet ganan prefijo `<slug:empresa_slug>/`

**Files:**
- Modify: `backend/apps/fleet/urls.py`
- Modify: `backend/apps/fleet/tests.py` (URLs de `ExtrasPublicosApiTests`)

**Interfaces:**
- Produces: `GET /api/<empresa_slug>/tarifa/`, `GET /api/<empresa_slug>/extras/`
  (antes `/api/tarifa/`, `/api/extras/` sin prefijo).

- [ ] **Step 1: Cambiar `urls.py`**

```python
# backend/apps/fleet/urls.py
from django.urls import path

from .views import ExtrasPublicosView, TarifaView

urlpatterns = [
    path('<slug:empresa_slug>/tarifa/', TarifaView.as_view(), name='tarifa'),
    path('<slug:empresa_slug>/extras/', ExtrasPublicosView.as_view(), name='extras'),
]
```

- [ ] **Step 2: Actualizar el resto de las URLs hardcodeadas en `tests.py`**

```python
# backend/apps/fleet/tests.py
# ExtrasPublicosApiTests: cada self.client.get('/api/extras/...') pasa a
# self.client.get('/api/empresa-a/extras/...'), con self.empresa = _crear_empresa(...)
# en un setUp() nuevo para la clase (ver Task F9 para el helper _crear_empresa
# compartido y el resto del retrofit completo de este archivo).
```

(El retrofit completo de `ExtrasPublicosApiTests`, `EmbarcacionTests`, y las clases
restantes que aún no tocaron F1-F7 se termina en la Task F9 — ahí se reescribe el
archivo completo con todas las URLs y `empresa=` ya corregidas de una vez, para no
dejar el archivo en un estado a medias entre F8 y F9.)

- [ ] **Step 3: Correr `manage.py check` para confirmar que las rutas resuelven**

Run: `venv\Scripts\python.exe manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add backend/apps/fleet/urls.py
git commit -m "feat(fleet): rutas publicas ganan prefijo empresa_slug"
```

---

### Task F9: Retrofit completo de `apps/fleet/tests.py`

**Files:**
- Modify: `backend/apps/fleet/tests.py` (reemplazo completo del archivo)

**Interfaces:**
- Consumes: `apps.tenancy.models.Sede`, `apps.tenancy.models.Empresa`,
  `apps.tenancy.scope.con_empresa(empresa)` (seccion Tenancy). `Tarifa.de(empresa)`,
  `capacidades_por_fecha(desde, hasta, empresa)`, `capacidades_disponibles(fecha, empresa)`
  (Task F4).

**Nota de verificación (2026-09-02):** el plan aprobado (Revisión 5, hallazgo B8)
afirma que `EmbarcacionNoDisponibleUnicidadTests` usa hilos con conexión propia y
necesita el mismo fix de threading que `apps/bookings/tests_concurrencia.py`. Se leyó
el archivo real (`backend/apps/fleet/tests.py:258-269`) para escribir esta tarea: esa
clase **no usa `threading.Thread` en ningún punto** — es un `TransactionTestCase`
llano que solo prueba que un segundo `EmbarcacionNoDisponible.objects.create(...)`
con la misma `(fecha, embarcacion)` lanza `IntegrityError` (necesita
`TransactionTestCase` porque un `IntegrityError` deja inutilizable la transacción de
un `TestCase` normal, no por ninguna razón de concurrencia). El hallazgo B8 del plan
describe con precisión `apps/bookings/tests_concurrencia.py` (esa sí lanza hilos) pero
la mención de `apps/fleet/tests.py:258` en la misma frase es incorrecta — no hay
ningún fix de threading que aplicar aquí. Esta tarea trata la clase como lo que es:
un `TransactionTestCase` que necesita `Sede`/`Empresa`/`empresa=` igual que el resto
del archivo, nada más.

- [ ] **Step 1: Escribir el archivo completo**

```python
# backend/apps/fleet/tests.py
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from io import StringIO

from apps.payments.pricing import PERSONAS_INCLUIDAS
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede

from .models import (
    CodigoPromocional,
    Embarcacion,
    EmbarcacionNoDisponible,
    ExtrasItem,
    PuntoEncuentro,
    Tarifa,
    TransportePrecio,
    capacidades_disponibles,
    capacidades_por_fecha,
)

_CONTADOR_SEDES = iter(range(10_000))


def _crear_empresa(slug):
    n = next(_CONTADOR_SEDES)
    sede = Sede.objects.create(nombre=f'Sede de prueba {n}', slug=f'sede-{n}-{slug}')
    return Empresa.objects.create(sede=sede, nombre=f'Empresa {slug}', slug=slug, activo=True)


class TarifaTests(TestCase):
    def setUp(self):
        self.empresa_a = _crear_empresa(slug='empresa-a')
        self.empresa_b = _crear_empresa(slug='empresa-b')

    def test_una_tarifa_por_empresa(self):
        Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
        Tarifa.objects.create(precio=Decimal('5000.00'), empresa=self.empresa_a)
        self.assertEqual(Tarifa.objects.filter(empresa=self.empresa_a).count(), 1)
        self.assertEqual(Tarifa.de(self.empresa_a).precio, Decimal('5000.00'))

    def test_cada_empresa_tiene_su_propia_tarifa(self):
        Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
        Tarifa.objects.create(precio=Decimal('3000.00'), empresa=self.empresa_b)
        self.assertEqual(Tarifa.de(self.empresa_a).precio, Decimal('4500.00'))
        self.assertEqual(Tarifa.de(self.empresa_b).precio, Decimal('3000.00'))

    def test_sin_tarifa_de_devuelve_none(self):
        self.assertIsNone(Tarifa.de(self.empresa_b))

    def test_precio_por_moneda(self):
        tarifa = Tarifa.objects.create(
            precio=Decimal('4500.00'), precio_usd=Decimal('260.00'), empresa=self.empresa_a,
        )
        self.assertEqual(tarifa.precio_en('MXN'), Decimal('4500.00'))
        self.assertEqual(tarifa.precio_en('USD'), Decimal('260.00'))

    def test_sin_precio_en_dolares_devuelve_none(self):
        tarifa = Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa_a)
        self.assertIsNone(tarifa.precio_en('USD'))


class TarifaApiTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')

    def test_sin_tarifa_responde_503(self):
        self.assertEqual(self.client.get('/api/empresa-a/tarifa/').status_code, 503)

    def test_devuelve_todas_las_cifras_del_checkout(self):
        with scope.con_empresa(self.empresa):
            Tarifa.objects.create(
                precio=Decimal('4500.00'), precio_usd=Decimal('260.00'),
                precio_persona_extra=Decimal('500.00'), empresa=self.empresa,
            )
        body = self.client.get('/api/empresa-a/tarifa/').json()
        self.assertEqual(body['precio'], '4500.00')
        self.assertEqual(body['precio_usd'], '260.00')
        self.assertEqual(body['precio_persona_extra'], '500.00')
        self.assertEqual(body['personas_incluidas'], PERSONAS_INCLUIDAS)

    def test_no_publica_precio_de_lo_que_se_cotiza(self):
        with scope.con_empresa(self.empresa):
            Tarifa.objects.create(precio=Decimal('4500.00'), empresa=self.empresa)
        body = self.client.get('/api/empresa-a/tarifa/').json()
        self.assertNotIn('amenidades', body)

    def test_empresa_inexistente_responde_404(self):
        self.assertEqual(self.client.get('/api/no-existe/tarifa/').status_code, 404)

    def test_no_ve_la_tarifa_de_otra_empresa(self):
        otra = _crear_empresa(slug='empresa-b')
        with scope.con_empresa(otra):
            Tarifa.objects.create(precio=Decimal('9999.00'), empresa=otra)
        self.assertEqual(self.client.get('/api/empresa-a/tarifa/').status_code, 503)


class ExtrasItemTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')

    def test_precio_por_moneda(self):
        item = ExtrasItem.objects.create(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'), precio_usd=Decimal('25'),
            empresa=self.empresa,
        )
        self.assertEqual(item.precio_en('MXN'), Decimal('450'))
        self.assertEqual(item.precio_en('USD'), Decimal('25'))

    def test_sin_precio_en_dolares_devuelve_none(self):
        item = ExtrasItem.objects.create(
            tipo='carnada', nombre='Carnada', precio=Decimal('200'), empresa=self.empresa,
        )
        self.assertIsNone(item.precio_en('USD'))

    def test_cantidad_editable_sin_cobrar_por_persona_no_es_valido(self):
        item = ExtrasItem(
            tipo='carnada', nombre='Carnada', precio=Decimal('200'),
            cobrar_por_persona=False, cantidad_editable=True, empresa=self.empresa,
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_cantidad_editable_con_cobrar_por_persona_es_valido(self):
        item = ExtrasItem(
            tipo='licencia', nombre='Licencia', precio=Decimal('450'),
            cobrar_por_persona=True, cantidad_editable=True, empresa=self.empresa,
        )
        item.full_clean()


class UnicidadPorEmpresaTests(TransactionTestCase):
    def setUp(self):
        self.empresa_a = _crear_empresa(slug='empresa-a')
        self.empresa_b = _crear_empresa(slug='empresa-b')

    def test_zona_de_transporte_repetida_en_la_misma_empresa_falla(self):
        TransportePrecio.objects.create(
            zona='centro', precio_base=Decimal('2000'), empresa=self.empresa_a,
        )
        with self.assertRaises(IntegrityError):
            TransportePrecio.objects.create(
                zona='centro', precio_base=Decimal('2100'), empresa=self.empresa_a,
            )

    def test_zona_de_transporte_repetida_entre_empresas_distintas_es_valida(self):
        TransportePrecio.objects.create(
            zona='centro', precio_base=Decimal('2000'), empresa=self.empresa_a,
        )
        TransportePrecio.objects.create(
            zona='centro', precio_base=Decimal('1800'), empresa=self.empresa_b,
        )
        self.assertEqual(TransportePrecio.objects.count(), 2)

    def test_codigo_promocional_repetido_en_la_misma_empresa_falla(self):
        CodigoPromocional.objects.create(
            codigo='VERANO10', porcentaje_descuento=Decimal('10'), empresa=self.empresa_a,
        )
        with self.assertRaises(IntegrityError):
            CodigoPromocional.objects.create(
                codigo='VERANO10', porcentaje_descuento=Decimal('15'), empresa=self.empresa_a,
            )

    def test_codigo_promocional_repetido_entre_empresas_es_valido(self):
        CodigoPromocional.objects.create(
            codigo='VERANO10', porcentaje_descuento=Decimal('10'), empresa=self.empresa_a,
        )
        CodigoPromocional.objects.create(
            codigo='VERANO10', porcentaje_descuento=Decimal('20'), empresa=self.empresa_b,
        )
        self.assertEqual(CodigoPromocional.objects.count(), 2)

    def test_nombre_de_embarcacion_repetido_en_la_misma_empresa_falla(self):
        Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa_a,
        )
        with self.assertRaises(IntegrityError):
            Embarcacion.objects.create(
                nombre='Lupita', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
                empresa=self.empresa_a,
            )

    def test_nombre_de_embarcacion_repetido_entre_empresas_es_valido(self):
        Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa_a,
        )
        Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
            empresa=self.empresa_b,
        )
        self.assertEqual(Embarcacion.objects.count(), 2)


class ExtrasPublicosApiTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')

    def test_extra_por_persona_multiplica(self):
        with scope.con_empresa(self.empresa):
            ExtrasItem.objects.create(
                tipo='licencia', nombre='Licencia', precio=Decimal('450'),
                cobrar_por_persona=True, empresa=self.empresa,
            )
        body = self.client.get('/api/empresa-a/extras/?personas=3').json()
        self.assertEqual(body['extras'][0]['monto'], '1350.00')

    def test_extra_plano_no_multiplica(self):
        with scope.con_empresa(self.empresa):
            ExtrasItem.objects.create(
                tipo='carnada', nombre='Carnada', precio=Decimal('200'),
                cobrar_por_persona=False, empresa=self.empresa,
            )
        body = self.client.get('/api/empresa-a/extras/?personas=5').json()
        self.assertEqual(body['extras'][0]['monto'], '200.00')

    def test_item_inactivo_no_aparece(self):
        with scope.con_empresa(self.empresa):
            ExtrasItem.objects.create(
                tipo='carnada', nombre='Carnada', precio=Decimal('200'), activo=False,
                empresa=self.empresa,
            )
        body = self.client.get('/api/empresa-a/extras/').json()
        self.assertEqual(body['extras'], [])

    def test_sin_precio_en_la_moneda_pedida_monto_es_null(self):
        with scope.con_empresa(self.empresa):
            ExtrasItem.objects.create(
                tipo='licencia', nombre='Licencia', precio=Decimal('450'), empresa=self.empresa,
            )
        body = self.client.get('/api/empresa-a/extras/?moneda=USD').json()
        self.assertIsNone(body['extras'][0]['monto'])

    def test_transporte_con_recargo_desde_el_minimo(self):
        with scope.con_empresa(self.empresa):
            TransportePrecio.objects.create(
                zona='centro', precio_base=Decimal('2000'), recargo_grupo=Decimal('1500'),
                min_personas_recargo=4, empresa=self.empresa,
            )
        body = self.client.get('/api/empresa-a/extras/?personas=4').json()
        self.assertEqual(body['transporte'][0]['monto'], '3500.00')

    def test_puntos_de_encuentro_activos(self):
        with scope.con_empresa(self.empresa):
            PuntoEncuentro.objects.create(nombre='Hotel CostaBaja', zona='centro', empresa=self.empresa)
            PuntoEncuentro.objects.create(
                nombre='Fuera de servicio', zona='centro', activo=False, empresa=self.empresa,
            )
        body = self.client.get('/api/empresa-a/extras/').json()
        self.assertEqual([p['nombre'] for p in body['puntos_encuentro']], ['Hotel CostaBaja'])

    def test_moneda_invalida_es_400(self):
        self.assertEqual(self.client.get('/api/empresa-a/extras/?moneda=EUR').status_code, 400)

    def test_personas_invalida_es_400(self):
        self.assertEqual(self.client.get('/api/empresa-a/extras/?personas=0').status_code, 400)
        self.assertEqual(self.client.get('/api/empresa-a/extras/?personas=abc').status_code, 400)

    def test_defaults_sin_query_params(self):
        response = self.client.get('/api/empresa-a/extras/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'extras': [], 'transporte': [], 'puntos_encuentro': []})

    def test_empresa_inexistente_responde_404(self):
        self.assertEqual(self.client.get('/api/no-existe/extras/').status_code, 404)

    def test_no_mezcla_catalogo_de_otra_empresa(self):
        otra = _crear_empresa(slug='empresa-b')
        with scope.con_empresa(otra):
            ExtrasItem.objects.create(
                tipo='carnada', nombre='Carnada de otra empresa', precio=Decimal('999'),
                empresa=otra,
            )
        body = self.client.get('/api/empresa-a/extras/').json()
        self.assertEqual(body['extras'], [])


class EmbarcacionTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')

    def test_nace_activa(self):
        panga = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa,
        )
        self.assertTrue(panga.activa)

    def test_la_etiqueta_de_clase_no_carga_la_capacidad(self):
        for clase in Embarcacion.Clase:
            self.assertNotIn('personas', clase.label)

    def test_str_muestra_la_capacidad(self):
        panga = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa,
        )
        self.assertEqual(str(panga), 'Lupita (Grande, max. 5)')


class CapacidadesDisponiblesTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')
        self.fecha = date.today() + timedelta(days=10)
        self.chica = Embarcacion.objects.create(
            nombre='Chuy', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
            empresa=self.empresa,
        )
        self.grande = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=self.empresa,
        )

    def test_devuelve_las_capacidades_de_mayor_a_menor(self):
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [5, 3])

    def test_excluye_las_inactivas(self):
        self.grande.activa = False
        self.grande.save()
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [3])

    def test_excluye_la_marcada_no_disponible_solo_ese_dia(self):
        EmbarcacionNoDisponible.objects.create(
            fecha=self.fecha, embarcacion=self.grande, motivo='Mantenimiento',
            empresa=self.empresa,
        )
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [3])
        self.assertEqual(
            capacidades_disponibles(self.fecha + timedelta(days=1), self.empresa), [5, 3],
        )

    def test_el_rango_no_hace_una_consulta_por_dia(self):
        with self.assertNumQueries(2):
            capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=89), self.empresa)

    def test_el_rango_trae_una_entrada_por_dia(self):
        rango = capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=2), self.empresa)
        self.assertEqual(len(rango), 3)
        self.assertEqual(rango[self.fecha], [5, 3])

    def test_pangas_de_otra_empresa_no_cuentan(self):
        otra_empresa = _crear_empresa(slug='empresa-b')
        Embarcacion.objects.create(
            nombre='Otra panga', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=6,
            empresa=otra_empresa,
        )
        self.assertEqual(capacidades_disponibles(self.fecha, self.empresa), [5, 3])


class CodigoPromocionalTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')

    def test_normaliza_codigo_a_mayusculas_y_sin_espacios(self):
        promo = CodigoPromocional.objects.create(
            codigo=' verano10 ', porcentaje_descuento=Decimal('10'), empresa=self.empresa,
        )
        self.assertEqual(promo.codigo, 'VERANO10')

    def test_codigo_repetido_en_la_misma_empresa_no_se_puede_crear(self):
        CodigoPromocional.objects.create(
            codigo='VERANO10', porcentaje_descuento=Decimal('10'), empresa=self.empresa,
        )
        with self.assertRaises(IntegrityError):
            CodigoPromocional.objects.create(
                codigo='VERANO10', porcentaje_descuento=Decimal('15'), empresa=self.empresa,
            )

    def test_fecha_fin_debe_ser_posterior_a_fecha_inicio(self):
        ahora = timezone.now()
        promo = CodigoPromocional(
            codigo='X', porcentaje_descuento=Decimal('10'), empresa=self.empresa,
            fecha_inicio=ahora, fecha_fin=ahora - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            promo.full_clean()

    def test_monto_minimo_en_devuelve_el_de_la_moneda_pedida(self):
        promo = CodigoPromocional.objects.create(
            codigo='MIN', porcentaje_descuento=Decimal('10'), empresa=self.empresa,
            monto_minimo=Decimal('5000'), monto_minimo_usd=Decimal('300'),
        )
        self.assertEqual(promo.monto_minimo_en('MXN'), Decimal('5000'))
        self.assertEqual(promo.monto_minimo_en('USD'), Decimal('300'))

    def test_porcentaje_fuera_de_rango_no_es_valido(self):
        with self.assertRaises(ValidationError):
            CodigoPromocional(
                codigo='CERO', porcentaje_descuento=Decimal('0'), empresa=self.empresa,
            ).full_clean()
        with self.assertRaises(ValidationError):
            CodigoPromocional(
                codigo='MAS', porcentaje_descuento=Decimal('101'), empresa=self.empresa,
            ).full_clean()


class EmbarcacionNoDisponibleUnicidadTests(TransactionTestCase):
    """Aparte y con TransactionTestCase: un IntegrityError deja inutilizable la
    transaccion que envuelve a un TestCase normal. NO usa hilos (ver nota de
    verificacion de la Task F9 al inicio de este archivo de tareas: la mencion de
    threading del plan aprobado para esta clase especifica es incorrecta)."""

    def test_una_panga_no_se_puede_marcar_dos_veces_el_mismo_dia(self):
        empresa = _crear_empresa(slug='empresa-a')
        fecha = date.today() + timedelta(days=10)
        grande = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5,
            empresa=empresa,
        )
        EmbarcacionNoDisponible.objects.create(fecha=fecha, embarcacion=grande, empresa=empresa)
        with self.assertRaises(IntegrityError):
            EmbarcacionNoDisponible.objects.create(fecha=fecha, embarcacion=grande, empresa=empresa)


class SeedExtrasTests(TestCase):
    def setUp(self):
        self.empresa = _crear_empresa(slug='empresa-a')

    def test_siembra_el_catalogo_para_la_empresa_dada(self):
        call_command('seed_extras', empresa='empresa-a', stdout=StringIO())
        self.assertEqual(ExtrasItem.objects.filter(empresa=self.empresa).count(), 3)
        self.assertEqual(TransportePrecio.objects.filter(empresa=self.empresa).count(), 2)
        self.assertEqual(PuntoEncuentro.objects.filter(empresa=self.empresa).count(), 1)

    def test_es_idempotente(self):
        call_command('seed_extras', empresa='empresa-a', stdout=StringIO())
        call_command('seed_extras', empresa='empresa-a', stdout=StringIO())
        self.assertEqual(ExtrasItem.objects.filter(empresa=self.empresa).count(), 3)

    def test_sin_empresa_falla_explicito(self):
        with self.assertRaises(Exception):
            call_command('seed_extras', stdout=StringIO())

    def test_empresa_inexistente_falla_explicito(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('seed_extras', empresa='no-existe', stdout=StringIO())
```

- [ ] **Step 2: Correr la suite completa de fleet**

Run: `venv\Scripts\python.exe manage.py test apps.fleet -v 2`
Expected: PASS — todas las clases.

- [ ] **Step 3: Commit**

```bash
git add backend/apps/fleet/tests.py
git commit -m "test(fleet): retrofit completo de la suite para multi-empresa"
```

---

## Self-Review (F1-F9)

**Cobertura del alcance asignado:** los 8 modelos con FK `empresa` (F1/F3), las 4
migraciones (F1/F2/F3/F4), `Tarifa.actual()` → `Tarifa.de(empresa)` (F4),
unicidad de `TransportePrecio.zona`/`CodigoPromocional.codigo`/`Embarcacion.nombre`
por Empresa (F4), `capacidades_por_fecha`/`capacidades_disponibles` con `empresa`
(F4), admin escopeado + guard del singleton de `TarifaAdmin` (F5), `seed_extras`
por Empresa (F6), catálogo público resuelto por slug (F7), prefijo de rutas (F8),
retrofit completo de tests (F9) — con la corrección documentada de que
`EmbarcacionNoDisponibleUnicidadTests` no tiene hilos que arreglar.

**Placeholders:** ninguno — cada paso trae código real, verificado contra el archivo
actual del repositorio (`backend/apps/fleet/{models,admin,views,urls,tests}.py`,
`backend/apps/fleet/management/commands/seed_extras.py`), no inventado desde la
prosa del File Map.

**Consistencia de firmas expuestas hacia otros forks/tasks:**
- `Tarifa.de(empresa)` — classmethod, `empresa: Empresa`, devuelve `Tarifa | None`.
- `capacidades_por_fecha(desde, hasta, empresa)` — `desde: date, hasta: date, empresa: Empresa`.
- `capacidades_disponibles(fecha, empresa)` — `fecha: date, empresa: Empresa`.
- Rutas públicas: `GET /api/<empresa_slug>/tarifa/`, `GET /api/<empresa_slug>/extras/`.

**Firmas consumidas de Task T (tenancy), a reconciliar cuando esa tarea se escriba:**
`scope.con_empresa(empresa)`, `scope.resolver_empresa_publica(slug)`,
`scope.empresa_actual(request)`, `apps.tenancy.admin_mixins.EmpresaScopedAdminMixin`,
`apps.tenancy.models.Sede`/`Empresa` (constructor con `nombre`, `slug`, `activo`,
y `Empresa(sede=..., nombre=..., slug=..., activo=...)`).

---

### Bookings (B1-B16)

# Expansión multi-sede — Pieza 1: Bookings Retrofit (Tareas B1-B16)

> Sección de tareas bite-sized del plan `docs/superpowers/plans/2026-08-31-expansion-multi-sede-pieza1-tenancy.md`
> (File Map aprobado tras 9 rondas de critic adversarial, ver `<!-- arch-critic: APPROVED -->` al final de ese
> archivo). Cubre exclusivamente `apps/bookings/*` — modelos, admin, vistas, panorama, serializers, urls,
> management commands y señales. `apps/tenancy/*` (scope.py, middleware.py, admin_mixins.py, modelos) y
> `apps/fleet/*` son secciones de tareas aparte (Task A / Task F) — este documento las CONSUME por nombre, no
> las redefine.
>
> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) o
> superpowers:executing-plans para ejecutar tarea por tarea. Los pasos usan checkbox (`- [ ]`).

**Interfaces externas asumidas** (de `apps.tenancy`/`apps.fleet`/`apps.testing`, aún sin implementar al escribir
este documento — si Task A/Task F/Task T ya corrieron, verificar que las signatures reales coinciden antes de
ejecutar; un desajuste de nombre es un fix de una línea, no una razón para rediseñar):

- `apps.tenancy.scope.con_empresa(empresa)` / `como_operador_plataforma()` — context managers no reentrantes.
- `apps.tenancy.scope.resolver_empresa_publica(slug)` → `Empresa`, lanza `django.http.Http404` si no existe o
  `activo=False`.
- `apps.tenancy.scope.empresa_actual(request)` → `Empresa | None`; `es_operador_plataforma(user)` → `bool`.
- `apps.tenancy.admin_mixins.EmpresaScopedAdminMixin` — `get_queryset` filtra por `empresa_actual(request)` (o
  no filtra si `es_operador_plataforma`); `save_model`/`formfield_for_foreignkey` genéricos ya resueltos ahí.
- `apps.tenancy.admin_mixins.EmpresaScopedUserAdminMixin` — `get_fieldsets` reduce "Permissions" a
  `('is_active',)` para no-operadores; `get_queryset` filtra `User` por `membresias__empresa`.
- `apps.tenancy.models.Sede(nombre, slug, zona_horaria, activo)`.
- `apps.tenancy.models.Empresa(sede, nombre, slug, activo, exclusiva, stripe_secret_key, stripe_webhook_secret,
  stripe_publishable_key)`.
- `apps.tenancy.models.MembresiaEmpresa(user, empresa, rol)`, con `rol` un `TextChoices` con miembros
  `MembresiaEmpresa.Rol.JEFE` / `MembresiaEmpresa.Rol.VENDEDORA`.
- `apps.testing.ApiTestCase` — expone `self.empresa` (una `Empresa` ya creada) desde `_pre_setup`, con
  `scope.con_empresa(self.empresa)` abierto durante el test (seccion Tenancy). `apps.testing.crear_flota(empresa,
  composicion=FLOTA_REAL)` gana `empresa` obligatorio.
- `apps.fleet.models.Embarcacion`, `Capitan`, `ExtrasItem`, `PuntoEncuentro`, `CodigoPromocional`,
  `TransportePrecio`, `EmbarcacionNoDisponible` ganan FK `empresa` (seccion Fleet).
- `apps.fleet.models.capacidades_por_fecha(desde, hasta, empresa)` / `capacidades_disponibles(fecha, empresa)`
  — ya actualizadas por Task F para filtrar por `empresa`.

**Decisión de este documento:** los tests nuevos van en `apps/bookings/tests_tenancy.py` (archivo nuevo), no en
`apps/bookings/tests.py` / `tests_agenda.py` / `tests_concurrencia.py` / etc. — el retrofit de la suite
existente (fila "Suite de tests existente" del File Map, 77 clases) es una tarea aparte y de escala comparable
al retrofit de modelos; tocar esos archivos aquí duplicaría trabajo y generaría conflictos de merge con esa
tarea. Cada tarea de este documento AGREGA clases/funciones nuevas a `tests_tenancy.py` — no lo reescribe.

**Comando de test** (Windows, desde `backend/`): `venv\Scripts\python.exe manage.py test apps.bookings`

**Orden de ejecución:** B1→B4 son secuenciales entre sí (cada migración depende de la anterior). B5-B8 tocan
`models.py` y pueden hacerse en el orden dado (cada una añade código sin pisar la anterior). B9-B10 tocan
`admin.py` (B10 depende de que B9 ya haya importado `EmpresaScopedAdminMixin`/`scope`). B11-B13, B14, B15, B16
son independientes entre sí una vez que B1-B8 están aplicadas.

---

### Task B1: `Reserva`/`CupoDiario`/`Vendedora` — FK `empresa` nullable + `PROTECT`

Primer paso del retrofit: agrega la columna sin tocar todavía ninguna lógica de negocio. Se queda nullable a
propósito — B2 hace el backfill de datos existentes antes de que B3 la cierre a `NOT NULL`.

**Files:**
- Modify: `apps/bookings/models.py` (imports, `CupoDiario`, `Vendedora`, `Reserva`)
- Create: `apps/bookings/migrations/0021_empresa_nullable.py`
- Create: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `apps.tenancy.models.Empresa`, `Sede` (ver cabecera del documento).
- Produces: `Reserva.empresa`, `CupoDiario.empresa`, `Vendedora.empresa` — FK a `tenancy.Empresa`,
  `on_delete=models.PROTECT`, `null=True, blank=True` en este paso (B3 lo cierra). `crear_empresa(**overrides)`
  en `tests_tenancy.py`, consumida por el resto de las tareas de este documento.

- [ ] **Step 1: Escribir el test que falla**

Crear `apps/bookings/tests_tenancy.py`:

```python
from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase

from apps.tenancy.models import Empresa, Sede

from .models import CupoDiario, Vendedora


def crear_empresa(**overrides):
    sede, _ = Sede.objects.get_or_create(
        slug=overrides.pop('sede_slug', 'la-paz'),
        defaults={'nombre': 'La Paz', 'zona_horaria': 'America/Mazatlan', 'activo': True},
    )
    base = {
        'sede': sede, 'nombre': 'Sal y Sol', 'slug': 'sal-y-sol', 'activo': True, 'exclusiva': True,
    }
    base.update(overrides)
    return Empresa.objects.create(**base)


class ReservaEmpresaFKTests(TestCase):
    def test_empresa_protegida_contra_borrado_con_cupo_diario(self):
        empresa = crear_empresa()
        CupoDiario.objects.create(empresa=empresa, fecha='2026-12-01', cupo_maximo=5)

        with self.assertRaises(ProtectedError):
            empresa.delete()

    def test_empresa_protegida_contra_borrado_con_vendedora(self):
        empresa = crear_empresa(slug='otra-empresa', nombre='Otra')
        usuario = get_user_model().objects.create_user('vendedora1', password='x')
        Vendedora.objects.create(usuario=usuario, empresa=empresa, codigo='ref1')

        with self.assertRaises(ProtectedError):
            empresa.delete()
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: falla — `Reserva`/`CupoDiario`/`Vendedora` no tienen campo `empresa`
(`django.core.exceptions.FieldError` o `TypeError: unexpected keyword argument 'empresa'`).

- [ ] **Step 3: Agregar el campo**

En `apps/bookings/models.py`, agregar el import:

```python
from apps.tenancy.models import Empresa
```

En `CupoDiario`, después de `fecha = models.DateField(unique=True)`:

```python
    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, null=True, blank=True, related_name='cupos_diarios',
    )
```

En `Vendedora`, después del campo `usuario`:

```python
    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, null=True, blank=True, related_name='vendedoras',
    )
```

En `Reserva`, después de `numero_personas`:

```python
    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, null=True, blank=True, related_name='reservas',
    )
```

- [ ] **Step 4: Escribir la migración**

Crear `apps/bookings/migrations/0021_empresa_nullable.py`:

```python
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0001_initial'),
        ('bookings', '0020_reservaextra_cantidad_solicitada_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva', name='empresa',
            field=models.ForeignKey(
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='reservas', to='tenancy.empresa',
            ),
        ),
        migrations.AddField(
            model_name='cupodiario', name='empresa',
            field=models.ForeignKey(
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='cupos_diarios', to='tenancy.empresa',
            ),
        ),
        migrations.AddField(
            model_name='vendedora', name='empresa',
            field=models.ForeignKey(
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='vendedoras', to='tenancy.empresa',
            ),
        ),
    ]
```

- [ ] **Step 5: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/bookings/models.py apps/bookings/migrations/0021_empresa_nullable.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): agrega FK empresa nullable a Reserva/CupoDiario/Vendedora"
```

---

### Task B2: Migración de backfill — `empresa = "Sal y Sol"` en filas existentes

Datos ya existentes en producción/dev quedan asignados a la Empresa que `tenancy.0002` crea. Sin `RunPython`
unitario que probar como función pura — se verifica corriendo la migración de verdad.

**Files:**
- Create: `apps/bookings/migrations/0022_backfill_empresa.py`

**Interfaces:**
- Consumes: `tenancy.0002_crear_sede_empresa_la_paz` (crea la fila `Empresa(slug='sal-y-sol')`, Task A).

- [ ] **Step 1: Escribir la migración**

```python
from django.db import migrations


def backfill_empresa(apps, schema_editor):
    Empresa = apps.get_model('tenancy', 'Empresa')
    Reserva = apps.get_model('bookings', 'Reserva')
    CupoDiario = apps.get_model('bookings', 'CupoDiario')
    Vendedora = apps.get_model('bookings', 'Vendedora')

    empresa = Empresa.objects.get(slug='sal-y-sol')
    Reserva.objects.filter(empresa__isnull=True).update(empresa=empresa)
    CupoDiario.objects.filter(empresa__isnull=True).update(empresa=empresa)
    Vendedora.objects.filter(empresa__isnull=True).update(empresa=empresa)


def revertir(apps, schema_editor):
    Reserva = apps.get_model('bookings', 'Reserva')
    CupoDiario = apps.get_model('bookings', 'CupoDiario')
    Vendedora = apps.get_model('bookings', 'Vendedora')
    Reserva.objects.update(empresa=None)
    CupoDiario.objects.update(empresa=None)
    Vendedora.objects.update(empresa=None)


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0002_crear_sede_empresa_la_paz'),
        ('bookings', '0021_empresa_nullable'),
    ]

    operations = [
        migrations.RunPython(backfill_empresa, revertir),
    ]
```

- [ ] **Step 2: Aplicar y verificar**

Run: `venv\Scripts\python.exe manage.py migrate bookings 0022`
Expected: `Applying bookings.0022_backfill_empresa... OK`

Run: `venv\Scripts\python.exe manage.py shell -c "from apps.bookings.models import Reserva, CupoDiario, Vendedora as V; print(Reserva.objects.filter(empresa__isnull=True).count(), CupoDiario.objects.filter(empresa__isnull=True).count(), V.objects.filter(empresa__isnull=True).count())"`
Expected: `0 0 0`

- [ ] **Step 3: Commit**

```bash
git add apps/bookings/migrations/0022_backfill_empresa.py
git commit -m "feat(tenancy): backfill de empresa=Sal y Sol en filas existentes de bookings"
```

---

### Task B3: `empresa` pasa a `NOT NULL`

**Files:**
- Modify: `apps/bookings/models.py` (`Reserva`, `CupoDiario`, `Vendedora`)
- Create: `apps/bookings/migrations/0023_empresa_no_null.py`
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `crear_empresa()` (Task B1).

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests_tenancy.py`:

```python
from django.db.utils import IntegrityError


class EmpresaObligatoriaTests(TestCase):
    def test_cupo_diario_sin_empresa_revienta(self):
        with self.assertRaises(IntegrityError):
            CupoDiario.objects.create(fecha='2026-12-05', cupo_maximo=5)
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.EmpresaObligatoriaTests -v 2`
Expected: FAIL — el campo sigue siendo nullable, `CupoDiario.objects.create(...)` sin `empresa` no revienta
(`AssertionError: IntegrityError not raised`).

- [ ] **Step 3: Quitar `null=True, blank=True` de los tres campos**

En `apps/bookings/models.py`, en `Reserva`, `CupoDiario` y `Vendedora`, el campo `empresa` pasa a:

```python
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='reservas')
```

(mismo patrón para `related_name='cupos_diarios'` y `related_name='vendedoras'` — solo se quitan `null=True,
blank=True`, el resto no cambia).

- [ ] **Step 4: Escribir la migración**

```python
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0022_backfill_empresa'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reserva', name='empresa',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='reservas', to='tenancy.empresa',
            ),
        ),
        migrations.AlterField(
            model_name='cupodiario', name='empresa',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='cupos_diarios', to='tenancy.empresa',
            ),
        ),
        migrations.AlterField(
            model_name='vendedora', name='empresa',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='vendedoras', to='tenancy.empresa',
            ),
        ),
    ]
```

- [ ] **Step 5: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS (todos los tests de B1 y B3).

- [ ] **Step 6: Commit**

```bash
git add apps/bookings/models.py apps/bookings/migrations/0023_empresa_no_null.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): empresa pasa a NOT NULL en Reserva/CupoDiario/Vendedora"
```

---

### Task B4: Unicidad por Empresa — `CupoDiario.fecha` y `Vendedora.codigo`

Quita las restricciones `unique=True` **globales** que impedirían a una segunda Empresa tener su propio cupo
del mismo día o repetir un código de vendedora ya usado por otra Empresa.

**Files:**
- Modify: `apps/bookings/models.py` (`CupoDiario.Meta`, `Vendedora.codigo`/`Meta`)
- Create: `apps/bookings/migrations/0024_unicidad_por_empresa.py`
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `crear_empresa()` (Task B1).
- Produces: `CupoDiario` único por `(empresa, fecha)`; `Vendedora` único por `(empresa, codigo)`. **Esta
  migración es la dependencia que `tenancy.0003_rls` necesita** (junto con la equivalente de `fleet`) antes de
  poder forzar RLS — sin ella, las restricciones globales seguirían bloqueando una segunda Empresa por debajo
  de la política.

- [ ] **Step 1: Escribir el test que falla**

```python
from django.contrib.auth import get_user_model


class UnicidadPorEmpresaTests(TestCase):
    def test_dos_empresas_pueden_tener_cupo_diario_la_misma_fecha(self):
        empresa_a = crear_empresa(slug='empresa-a', nombre='A')
        empresa_b = crear_empresa(slug='empresa-b', nombre='B')
        CupoDiario.objects.create(empresa=empresa_a, fecha='2026-12-10', cupo_maximo=5)
        CupoDiario.objects.create(empresa=empresa_b, fecha='2026-12-10', cupo_maximo=8)  # no debe reventar

    def test_misma_empresa_no_puede_repetir_fecha_de_cupo(self):
        empresa = crear_empresa(slug='empresa-c', nombre='C')
        CupoDiario.objects.create(empresa=empresa, fecha='2026-12-11', cupo_maximo=5)
        with self.assertRaises(IntegrityError):
            CupoDiario.objects.create(empresa=empresa, fecha='2026-12-11', cupo_maximo=8)

    def test_dos_empresas_pueden_repetir_codigo_de_vendedora(self):
        User = get_user_model()
        empresa_a = crear_empresa(slug='empresa-a2', nombre='A2')
        empresa_b = crear_empresa(slug='empresa-b2', nombre='B2')
        Vendedora.objects.create(usuario=User.objects.create_user('v_a'), empresa=empresa_a, codigo='verano10')
        Vendedora.objects.create(usuario=User.objects.create_user('v_b'), empresa=empresa_b, codigo='verano10')
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.UnicidadPorEmpresaTests -v 2`
Expected: FAIL en `test_dos_empresas_pueden_tener_cupo_diario_la_misma_fecha` y en
`test_dos_empresas_pueden_repetir_codigo_de_vendedora` (`IntegrityError: UNIQUE constraint failed`, porque
`fecha`/`codigo` siguen siendo únicos globales).

- [ ] **Step 3: Quitar el `unique=True` global, agregar `UniqueConstraint`**

En `CupoDiario`:

```python
    fecha = models.DateField()
```

```python
    class Meta:
        ordering = ['fecha']
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'fecha'], name='cupodiario_unico_por_empresa_fecha'),
        ]
```

En `Vendedora`:

```python
    codigo = models.SlugField(
        max_length=30,
        help_text='Lo que va en el link que le manda a sus clientes: ?ref=<codigo>. '
                  'Solo letras, numeros y guiones.',
    )
```

```python
    class Meta:
        ordering = ['usuario__username']
        verbose_name = 'vendedora'
        verbose_name_plural = 'vendedoras'
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'codigo'], name='vendedora_unico_por_empresa_codigo'),
        ]
```

- [ ] **Step 4: Escribir la migración**

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0023_empresa_no_null'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cupodiario', name='fecha',
            field=models.DateField(),
        ),
        migrations.AddConstraint(
            model_name='cupodiario',
            constraint=models.UniqueConstraint(
                fields=['empresa', 'fecha'], name='cupodiario_unico_por_empresa_fecha',
            ),
        ),
        migrations.AlterField(
            model_name='vendedora', name='codigo',
            field=models.SlugField(
                max_length=30,
                help_text='Lo que va en el link que le manda a sus clientes: ?ref=<codigo>. '
                          'Solo letras, numeros y guiones.',
            ),
        ),
        migrations.AddConstraint(
            model_name='vendedora',
            constraint=models.UniqueConstraint(
                fields=['empresa', 'codigo'], name='vendedora_unico_por_empresa_codigo',
            ),
        ),
    ]
```

- [ ] **Step 5: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/bookings/models.py apps/bookings/migrations/0024_unicidad_por_empresa.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): unicidad de CupoDiario.fecha y Vendedora.codigo pasa a ser por Empresa"
```

---

### Task B5: Cupo diario y advisory lock — todo el motor gana `empresa`

El motor de cupo (`bloquear_cupo_del_dia`, `evaluar_cupo`, `validar_cupo_diario`, `cupo_maximo_del_dia`,
`disponibilidad_por_fecha`, `proxima_fecha_disponible`, `Reserva._validar_una_salida_por_dia`) es un solo
bloque interconectado — no se puede migrar función por función sin romper las llamadas cruzadas que ya existen
entre ellas, así que es una sola tarea.

**Files:**
- Modify: `apps/bookings/models.py`
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `apps.fleet.models.capacidades_por_fecha(desde, hasta, empresa)`,
  `capacidades_disponibles(fecha, empresa)` (seccion Fleet).
- Produces (firmas nuevas, reemplazan las actuales — quien las llame desde otro archivo debe actualizarse,
  ver B11/B14):
  - `cupo_maximo_del_dia(fecha, empresa)`
  - `bloquear_cupo_del_dia(empresa_id, fecha)` — toma el **entero**, no el objeto `Empresa`.
  - `evaluar_cupo(fecha, personas, empresa, excluir_pk=None)`
  - `validar_cupo_diario(fecha, personas, empresa, excluir_pk=None)`
  - `disponibilidad_por_fecha(desde, hasta, personas, empresa)`
  - `proxima_fecha_disponible(desde, personas, empresa, dias=DIAS_BUSQUEDA_DISPONIBILIDAD)`
  - `Reserva._validar_una_salida_por_dia()` — sin cambio de firma (usa `self.empresa_id`).
  - `datos_reserva(empresa, **overrides)` en `tests_tenancy.py`, consumida por B6-B8, B16.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests_tenancy.py`:

```python
from datetime import date, time, timedelta

from apps.testing import crear_flota

from .models import MOTIVO_SIN_PANGA, Reserva, evaluar_cupo


def datos_reserva(empresa, **overrides):
    crear_flota(empresa)
    base = {
        'empresa': empresa,
        'fecha': date.today() + timedelta(days=15),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
    }
    base.update(overrides)
    return base


class CupoEmpresaAisladoTests(TestCase):
    def test_cupo_de_una_empresa_no_bloquea_a_otra(self):
        empresa_a = crear_empresa(slug='empresa-a3', nombre='A3')
        empresa_b = crear_empresa(slug='empresa-b3', nombre='B3')
        crear_flota(empresa_a, composicion=[(1, 3)])
        crear_flota(empresa_b, composicion=[(1, 3)])
        fecha = date.today() + timedelta(days=20)

        Reserva.objects.create(**datos_reserva(
            empresa_a, fecha=fecha, numero_personas=3, estado=Reserva.Estado.PAGADA,
        ))

        # La empresa A ya usó su única panga de 3; la B, con su propia panga de
        # 3 sin usar, debe seguir aceptando un grupo de 3.
        self.assertIsNone(evaluar_cupo(fecha, 3, empresa_b))
        self.assertEqual(evaluar_cupo(fecha, 3, empresa_a), MOTIVO_SIN_PANGA)
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.CupoEmpresaAisladoTests -v 2`
Expected: `TypeError: evaluar_cupo() takes from 2 to 3 positional arguments but 4 were given` (firma vieja).

- [ ] **Step 3: Implementar**

Reemplazar en `apps/bookings/models.py`:

```python
def cupo_maximo_del_dia(fecha, empresa):
    override = CupoDiario.objects.filter(fecha=fecha, empresa=empresa).first()
    return override.cupo_maximo if override else CUPO_MAXIMO_DEFAULT
```

```python
def proxima_fecha_disponible(desde, personas, empresa, dias=DIAS_BUSQUEDA_DISPONIBILIDAD):
    hasta = desde + timedelta(days=dias - 1)
    for fecha, motivo in sorted(disponibilidad_por_fecha(desde, hasta, personas, empresa).items()):
        if motivo is None:
            return fecha
    return None


def disponibilidad_por_fecha(desde, hasta, personas, empresa):
    grupos_por_fecha = defaultdict(list)
    for fecha, personas_de_esa in Reserva.objects.filter(
        fecha__range=(desde, hasta), estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa=empresa,
    ).values_list('fecha', 'numero_personas'):
        grupos_por_fecha[fecha].append(personas_de_esa)

    topes = dict(
        CupoDiario.objects.filter(fecha__range=(desde, hasta), empresa=empresa)
        .values_list('fecha', 'cupo_maximo')
    )
    capacidades = capacidades_por_fecha(desde, hasta, empresa)

    return {
        fecha: motivo_sin_lugar(
            personas, grupos_por_fecha[fecha], capacidades[fecha], topes.get(fecha, CUPO_MAXIMO_DEFAULT),
        )
        for fecha in (desde + timedelta(days=i) for i in range((hasta - desde).days + 1))
    }
```

```python
def bloquear_cupo_del_dia(empresa_id, fecha):
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [empresa_id, fecha.toordinal()])


def evaluar_cupo(fecha, personas, empresa, excluir_pk=None):
    ocupadas = Reserva.objects.filter(fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa=empresa)
    if excluir_pk is not None:
        ocupadas = ocupadas.exclude(pk=excluir_pk)

    return motivo_sin_lugar(
        personas,
        list(ocupadas.values_list('numero_personas', flat=True)),
        capacidades_disponibles(fecha, empresa),
        cupo_maximo_del_dia(fecha, empresa),
    )


def validar_cupo_diario(fecha, personas, empresa, excluir_pk=None):
    bloquear_cupo_del_dia(empresa.pk, fecha)

    motivo = evaluar_cupo(fecha, personas, empresa, excluir_pk=excluir_pk)
    if motivo == MOTIVO_LLENO:
        raise ValidationError(
            f'No hay cupo disponible para el {fecha}: se alcanzo el maximo de viajes del dia.'
        )
    if motivo == MOTIVO_SIN_PANGA:
        raise ValidationError(
            f'No queda panga para un grupo de {personas} personas el {fecha}. '
            f'Las de mayor capacidad ya estan comprometidas.'
        )
```

En `Reserva.clean()`, la llamada a `validar_cupo_diario` gana `self.empresa`:

```python
    def clean(self):
        if self.estado in ESTADOS_QUE_OCUPAN_CUPO:
            validar_cupo_diario(self.fecha, self.numero_personas, self.empresa, excluir_pk=self.pk)
```

(la llamada a `validar_codigo_promocional_en_pago` dentro del mismo `if`, dos líneas abajo, la toca B6 —
no la muevas todavía.)

En `Reserva._validar_una_salida_por_dia`:

```python
    def _validar_una_salida_por_dia(self):
        del_dia = Reserva.objects.filter(
            fecha=self.fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa_id=self.empresa_id,
        )
        if self.pk:
            del_dia = del_dia.exclude(pk=self.pk)
        ...  # resto sin cambios
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/models.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): motor de cupo y advisory lock ganan empresa obligatorio"
```

---

### Task B6: Código promocional y atribución de vendedora — `empresa` obligatorio

**Files:**
- Modify: `apps/bookings/models.py` (`evaluar_codigo_promocional`, `validar_codigo_promocional_en_pago`,
  `Vendedora.por_codigo`, `Reserva.clean`)
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `apps.fleet.models.CodigoPromocional` con FK `empresa` (seccion Fleet). `datos_reserva()` (Task B5).
- Produces:
  - `evaluar_codigo_promocional(codigo_str, correo_cliente, empresa)`
  - `validar_codigo_promocional_en_pago(promo, moneda, monto_viaje, correo_cliente, empresa, excluir_pk=None)`
  - `Vendedora.por_codigo(codigo, empresa)`

- [ ] **Step 1: Escribir el test que falla**

```python
from apps.fleet.models import CodigoPromocional

from .models import evaluar_codigo_promocional


class CodigoPromocionalEmpresaTests(TestCase):
    def test_codigo_de_una_empresa_no_valida_en_otra(self):
        empresa_a = crear_empresa(slug='empresa-a4', nombre='A4')
        empresa_b = crear_empresa(slug='empresa-b4', nombre='B4')
        CodigoPromocional.objects.create(empresa=empresa_a, codigo='VERANO10', activo=True)

        self.assertIsNotNone(evaluar_codigo_promocional('VERANO10', 'x@example.com', empresa_a))
        self.assertIsNone(evaluar_codigo_promocional('VERANO10', 'x@example.com', empresa_b))
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.CodigoPromocionalEmpresaTests -v 2`
Expected: `TypeError: evaluar_codigo_promocional() takes 2 positional arguments but 3 were given`.

- [ ] **Step 3: Implementar**

```python
def evaluar_codigo_promocional(codigo_str, correo_cliente, empresa):
    if not codigo_str:
        return None
    try:
        promo = CodigoPromocional.objects.get(codigo=codigo_str.strip().upper(), empresa=empresa)
    except CodigoPromocional.DoesNotExist:
        return None
    return promo if codigo_promocional_valido(promo, correo_cliente) else None


def validar_codigo_promocional_en_pago(promo, moneda, monto_viaje, correo_cliente, empresa, excluir_pk=None):
    try:
        promo_bloqueado = CodigoPromocional.objects.select_for_update().get(pk=promo.pk, empresa=empresa)
    except CodigoPromocional.DoesNotExist:
        raise ValidationError({'codigo_promocional': 'El codigo promocional ya no es valido.'})

    if not codigo_promocional_valido(
        promo_bloqueado, correo_cliente, monto_viaje=monto_viaje, moneda=moneda, excluir_pk=excluir_pk,
    ):
        raise ValidationError({'codigo_promocional': 'El codigo promocional ya no es valido.'})
```

En `Vendedora`:

```python
    @classmethod
    def por_codigo(cls, codigo, empresa):
        if not codigo:
            return None
        return cls.objects.filter(codigo=codigo, empresa=empresa, activo=True).first()
```

En `Reserva.clean()`, la llamada que faltaba:

```python
            if self.codigo_promocional_id:
                validar_codigo_promocional_en_pago(
                    self.codigo_promocional, self.moneda,
                    (self.precio_total or 0) + (self.descuento_aplicado or 0),
                    self.correo_cliente, self.empresa, excluir_pk=self.pk,
                )
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/models.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): codigo promocional y atribucion de vendedora ganan empresa obligatorio"
```

---

### Task B7: `Reserva.clean()` — ninguna FK puede pertenecer a otra Empresa

RLS filtra filas por consulta, no valida referencias cruzadas que arme el operador de plataforma desde el
admin (que no tiene `formfield_for_foreignkey` filtrado, ver B9) — esta es la red de seguridad a nivel de
modelo.

**Files:**
- Modify: `apps/bookings/models.py` (`Reserva.clean`, método nuevo `_validar_consistencia_de_empresa`)
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `datos_reserva()` (Task B5). `apps.fleet.models.Embarcacion`/`Capitan`/`CodigoPromocional` con FK
  `empresa` (seccion Fleet).

- [ ] **Step 1: Escribir el test que falla**

```python
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from .models import Vendedora


class ConsistenciaEmpresaReservaTests(TestCase):
    def test_vendedora_de_otra_empresa_no_se_puede_asignar(self):
        empresa_a = crear_empresa(slug='empresa-a5', nombre='A5')
        empresa_b = crear_empresa(slug='empresa-b5', nombre='B5')
        vendedora_b = Vendedora.objects.create(
            usuario=get_user_model().objects.create_user('vb5'), empresa=empresa_b, codigo='vb5',
        )
        reserva = Reserva(**datos_reserva(empresa_a, vendedora=vendedora_b))

        with self.assertRaises(ValidationError):
            reserva.full_clean()
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.ConsistenciaEmpresaReservaTests -v 2`
Expected: FAIL — `full_clean()` pasa sin reventar, no hay validación cruzada todavía.

- [ ] **Step 3: Implementar**

En `Reserva.clean()`, agregar la llamada al final:

```python
        self._validar_capacidad_embarcacion()
        self._validar_una_salida_por_dia()
        self._validar_cambio_de_fecha()
        self._validar_consistencia_de_empresa()
```

Nuevo método:

```python
    def _validar_consistencia_de_empresa(self):
        """Ninguna FK puede pertenecer a otra Empresa. RLS filtra filas por
        consulta, no valida referencias cruzadas que arme el operador de
        plataforma desde el admin (sin formfield_for_foreignkey filtrado)."""
        for campo, relacionado in (
            ('embarcacion', self.embarcacion),
            ('capitan', self.capitan),
            ('vendedora', self.vendedora),
            ('codigo_promocional', self.codigo_promocional),
        ):
            if relacionado is not None and relacionado.empresa_id != self.empresa_id:
                raise ValidationError({
                    campo: f'{relacionado} pertenece a otra Empresa, no se puede usar aqui.',
                })
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/models.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): Reserva.clean valida que embarcacion/capitan/vendedora/codigo sean de la misma empresa"
```

---

### Task B8: `ReservaTransporte.clean()` + `ReservaExtra.clean()` (nuevo)

Las dos asociaciones que de verdad deciden precio (zona del punto de encuentro, precio del extra) — la
consistencia de `Reserva.clean()` (B7) no las cubre porque ninguna vive en `Reserva`.

**Files:**
- Modify: `apps/bookings/models.py` (`ReservaTransporte.clean`, `ReservaExtra` gana `clean()`)
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `datos_reserva()` (Task B5). `apps.fleet.models.ExtrasItem`/`PuntoEncuentro`/`TransportePrecio` con
  FK `empresa` (seccion Fleet).
- Produces: `ReservaExtra.clean()` — no existía antes de esta tarea.

- [ ] **Step 1: Escribir el test que falla**

```python
from decimal import Decimal

from apps.fleet.models import ExtrasItem, PuntoEncuentro, TransportePrecio

from .models import ReservaExtra, ReservaTransporte


class ConsistenciaEmpresaExtrasTransporteTests(TestCase):
    def test_extra_de_otra_empresa_no_se_puede_asociar(self):
        empresa_a = crear_empresa(slug='empresa-a6', nombre='A6')
        empresa_b = crear_empresa(slug='empresa-b6', nombre='B6')
        extra_b = ExtrasItem.objects.create(
            empresa=empresa_b, tipo=ExtrasItem.Tipo.BRUNCH, nombre='Brunch', precio=Decimal('100'), activo=True,
        )
        reserva = Reserva.objects.create(**datos_reserva(empresa_a))

        extra = ReservaExtra(reserva=reserva, extras_item=extra_b)
        with self.assertRaises(ValidationError):
            extra.full_clean()

    def test_punto_encuentro_de_otra_empresa_no_se_puede_asociar(self):
        empresa_a = crear_empresa(slug='empresa-a7', nombre='A7')
        empresa_b = crear_empresa(slug='empresa-b7', nombre='B7')
        punto_b = PuntoEncuentro.objects.create(
            empresa=empresa_b, nombre='Hotel X', zona=TransportePrecio.Zona.CENTRO, activo=True,
        )
        reserva = Reserva.objects.create(**datos_reserva(empresa_a))

        transporte = ReservaTransporte(reserva=reserva, punto_encuentro=punto_b, zona=punto_b.zona)
        with self.assertRaises(ValidationError):
            transporte.full_clean(exclude=['reserva'])
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.ConsistenciaEmpresaExtrasTransporteTests -v 2`
Expected: FAIL en los dos tests — ninguna validación cruzada existe todavía.

- [ ] **Step 3: Implementar**

En `ReservaTransporte.clean()`, agregar al final:

```python
    def clean(self):
        if bool(self.punto_encuentro_id) == bool(self.direccion_personalizada):
            raise ValidationError(
                'Elige un punto de encuentro del catalogo o escribe una direccion, no los dos ni ninguno.'
            )
        if self.punto_encuentro_id and self.zona != self.punto_encuentro.zona:
            raise ValidationError({
                'zona': 'La zona no coincide con la del punto de encuentro elegido.',
            })
        if self.punto_encuentro_id:
            reserva = self._reserva_o_ninguna()
            if reserva is not None and self.punto_encuentro.empresa_id != reserva.empresa_id:
                raise ValidationError({
                    'punto_encuentro': 'Ese punto de encuentro pertenece a otra Empresa.',
                })

    def _reserva_o_ninguna(self):
        """`self.reserva` puede no ser resoluble todavia: en el checkout,
        clean() corre con `exclude=['reserva']` ANTES de que la Reserva tenga
        pk (ver ReservaCheckoutSerializer._guardar). El objeto sigue
        disponible via el descriptor cacheado del FK — no se re-resuelve por
        self.reserva_id, que en ese momento es None."""
        try:
            return self.reserva
        except Reserva.DoesNotExist:
            return None
```

En `ReservaExtra`, agregar el método nuevo (no existía `clean()` en este modelo):

```python
    def clean(self):
        if self.extras_item_id:
            reserva = self._reserva_o_ninguna()
            if reserva is not None and self.extras_item.empresa_id != reserva.empresa_id:
                raise ValidationError({
                    'extras_item': 'Ese extra pertenece a otra Empresa.',
                })

    def _reserva_o_ninguna(self):
        try:
            return self.reserva
        except Reserva.DoesNotExist:
            return None
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/models.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): ReservaTransporte/ReservaExtra validan que su FK sea de la misma empresa"
```

---

### Task B9: Admin — `EmpresaScopedAdminMixin` en los cinco `ModelAdmin` de bookings

`ReservaAdmin` ya llama `super().get_queryset(request)`, así que hereda el filtro del mixin gratis. Los dos que
**no** llamaban `super()` (`CheckoutAbandonadoAdmin`, `AgendaAdmin`) quedaban sin aislar pese a "heredar el
mixin" — son las dos pantallas con más PII (teléfono/WhatsApp de clientes, viajes ya pagados).

**Files:**
- Modify: `apps/bookings/admin.py`
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `apps.tenancy.admin_mixins.EmpresaScopedAdminMixin`, `apps.tenancy.scope.empresa_actual`,
  `es_operador_plataforma` (seccion Tenancy). `crear_empresa()` (Task B1), `datos_reserva()` (Task B5).

- [ ] **Step 1: Escribir el test que falla**

```python
from unittest import mock

from django.test import RequestFactory
from django.utils import timezone

from .admin import AgendaAdmin, CheckoutAbandonadoAdmin
from .models import Agenda, CheckoutAbandonado


class AdminScopingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.empresa_a = crear_empresa(slug='empresa-a8', nombre='A8')
        self.empresa_b = crear_empresa(slug='empresa-b8', nombre='B8')
        r_a = Reserva.objects.create(**datos_reserva(self.empresa_a, estado=Reserva.Estado.PENDIENTE_PAGO))
        r_b = Reserva.objects.create(**datos_reserva(self.empresa_b, estado=Reserva.Estado.PENDIENTE_PAGO))
        Reserva.objects.filter(pk__in=[r_a.pk, r_b.pk]).update(
            creado_en=timezone.now() - timedelta(hours=3)
        )

    def test_checkout_abandonado_admin_aisla_por_empresa(self):
        admin = CheckoutAbandonadoAdmin(CheckoutAbandonado, admin_site=mock.Mock())
        request = self.factory.get('/admin/bookings/checkoutabandonado/')
        with mock.patch('apps.bookings.admin.scope.empresa_actual', return_value=self.empresa_a), \
             mock.patch('apps.bookings.admin.scope.es_operador_plataforma', return_value=False):
            filas = list(admin.get_queryset(request))
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0].empresa_id, self.empresa_a.id)

    def test_agenda_admin_aisla_por_empresa(self):
        reserva_a = Reserva.objects.create(**datos_reserva(
            self.empresa_a, estado=Reserva.Estado.PAGADA, fecha=date.today() + timedelta(days=3),
        ))
        Reserva.objects.create(**datos_reserva(
            self.empresa_b, estado=Reserva.Estado.PAGADA, fecha=date.today() + timedelta(days=3),
        ))
        admin = AgendaAdmin(Agenda, admin_site=mock.Mock())
        request = self.factory.get('/admin/bookings/agenda/')
        with mock.patch('apps.bookings.admin.scope.empresa_actual', return_value=self.empresa_a), \
             mock.patch('apps.bookings.admin.scope.es_operador_plataforma', return_value=False):
            filas = list(admin.get_queryset(request))
        self.assertEqual([f.pk for f in filas], [reserva_a.pk])
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.AdminScopingTests -v 2`
Expected: falla al importar (`ImportError: cannot import name 'scope' from 'apps.bookings.admin'`) o, si el
mock no encuentra el atributo, ambos tests fallan con `AssertionError: 2 != 1` (sin aislar, ven las dos
Empresas).

- [ ] **Step 3: Implementar**

En `apps/bookings/admin.py`, agregar el import:

```python
from apps.tenancy import scope
from apps.tenancy.admin_mixins import EmpresaScopedAdminMixin
```

Cambiar las cinco clases base:

```python
@admin.register(CupoDiario)
class CupoDiarioAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    ...

@admin.register(Vendedora)
class VendedoraAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    ...

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'usuario' and not scope.es_operador_plataforma(request.user):
            kwargs['queryset'] = User.objects.filter(membresias__empresa=scope.empresa_actual(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Reserva)
class ReservaAdmin(AvisoDeReservasNuevasMixin, EmpresaScopedAdminMixin, ModelAdmin):
    ...  # get_queryset ya llama super(), no hace falta tocarlo
```

`CheckoutAbandonadoAdmin`:

```python
@admin.register(CheckoutAbandonado)
class CheckoutAbandonadoAdmin(EmpresaScopedAdminMixin, ModelAdmin):
    ...
    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            estado=Reserva.Estado.PENDIENTE_PAGO,
            creado_en__lt=timezone.now() - timedelta(hours=HORAS_PARA_CONSIDERAR_ABANDONADO),
        )
```

`AgendaAdmin`:

```python
@admin.register(Agenda)
class AgendaAdmin(AvisoDeReservasNuevasMixin, EmpresaScopedAdminMixin, ModelAdmin):
    ...
    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            estado__in=Agenda.ESTADOS_EN_AGENDA
        ).select_related('embarcacion', 'capitan')
```

La acción "Marcar como venta mia" gana el filtro por empresa:

```python
    @admin.action(description='Marcar como venta mia')
    def marcar_como_venta_mia(self, request, queryset):
        vendedora = Vendedora.objects.filter(
            usuario=request.user, empresa=scope.empresa_actual(request), activo=True,
        ).first()
        ...  # resto sin cambios
```

`reservas_nuevas_view` (en `AvisoDeReservasNuevasMixin`) gana el filtro por empresa:

```python
        nuevas = Reserva.objects.filter(
            creado_en__gt=desde, estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa=scope.empresa_actual(request),
        ).count()
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/admin.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): admin de bookings escopeado por empresa (aisla CheckoutAbandonado/Agenda)"
```

---

### Task B10: Admin — `UserAdmin`/`GroupAdmin` escopeados + acción "Dar de alta vendedora"

Con los jefes ya sin `is_superuser`, esta es la única vía para crear una vendedora sin darle a un jefe acceso
de escritura sin restricciones sobre `auth.User`/`auth.Group`.

**Files:**
- Create: `apps/bookings/forms.py`
- Create: `apps/bookings/templates/bookings/alta_vendedora.html`
- Modify: `apps/bookings/admin.py` (bloque `UserAdmin`/`GroupAdmin`, líneas ~429-444 del archivo actual)
- Modify: `backend/CLAUDE.md` (sección "Roles: Jefes vs Vendedora" y frase de "Panel de finanzas")
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `apps.tenancy.admin_mixins.EmpresaScopedUserAdminMixin` (seccion Tenancy) — **no la redefine, solo la usa**.
  `apps.tenancy.models.MembresiaEmpresa` con `Rol.JEFE`/`Rol.VENDEDORA` (seccion Tenancy). `scope.empresa_actual`,
  `scope.es_operador_plataforma` (ya importados en B9).
- Produces: `AltaVendedoraForm` en `apps/bookings/forms.py`. URL `admin:bookings_user_dar_de_alta_vendedora`.

- [ ] **Step 1: Escribir el test que falla**

```python
from django.contrib.auth.models import Group, User
from django.urls import reverse

from apps.tenancy.models import MembresiaEmpresa

from .models import Vendedora


class AltaVendedoraTests(TestCase):
    def setUp(self):
        self.empresa = crear_empresa(slug='empresa-alta', nombre='Alta')
        self.jefe = get_user_model().objects.create_user('jefe1', password='x', is_staff=True)
        self.jefe.groups.add(Group.objects.create(name='Jefe'))
        Group.objects.get_or_create(name='Vendedora')
        MembresiaEmpresa.objects.create(user=self.jefe, empresa=self.empresa, rol=MembresiaEmpresa.Rol.JEFE)

    def test_jefe_da_de_alta_vendedora_sin_elegir_empresa(self):
        self.client.force_login(self.jefe)
        with mock.patch('apps.bookings.admin.scope.empresa_actual', return_value=self.empresa), \
             mock.patch('apps.bookings.admin.scope.es_operador_plataforma', return_value=False):
            response = self.client.post(reverse('admin:bookings_user_dar_de_alta_vendedora'), {
                'username': 'vendedora_nueva', 'password': 'una-clave-larga-123',
                'nombre': 'Nueva Vendedora', 'codigo': 'nueva10',
            })
        self.assertEqual(response.status_code, 302)
        nuevo = User.objects.get(username='vendedora_nueva')
        self.assertTrue(nuevo.groups.filter(name='Vendedora').exists())
        self.assertFalse(nuevo.groups.filter(name='Jefe').exists())
        self.assertTrue(MembresiaEmpresa.objects.filter(
            user=nuevo, empresa=self.empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
        ).exists())
        self.assertTrue(Vendedora.objects.filter(usuario=nuevo, empresa=self.empresa, codigo='nueva10').exists())

    def test_username_repetido_da_error_de_formulario_no_500(self):
        get_user_model().objects.create_user('ya_existe', password='x')
        self.client.force_login(self.jefe)
        with mock.patch('apps.bookings.admin.scope.empresa_actual', return_value=self.empresa), \
             mock.patch('apps.bookings.admin.scope.es_operador_plataforma', return_value=False):
            response = self.client.post(reverse('admin:bookings_user_dar_de_alta_vendedora'), {
                'username': 'ya_existe', 'password': 'una-clave-larga-123',
                'nombre': 'Nueva', 'codigo': 'otro10',
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe una cuenta')
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.AltaVendedoraTests -v 2`
Expected: `NoReverseMatch: Reverse for 'bookings_user_dar_de_alta_vendedora' not found` — la URL no existe todavía.

- [ ] **Step 3: Crear el formulario**

`apps/bookings/forms.py`:

```python
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.tenancy.models import Empresa


class AltaVendedoraForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    nombre = forms.CharField(max_length=150)
    codigo = forms.SlugField(
        max_length=30, help_text='Va en el link que le pasa a sus clientes: ?ref=<codigo>',
    )
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all(), required=False)

    def __init__(self, *args, es_operador=False, **kwargs):
        super().__init__(*args, **kwargs)
        if es_operador:
            self.fields['empresa'].required = True
        else:
            del self.fields['empresa']

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Ya existe una cuenta con ese nombre de usuario.')
        return username

    def clean_password(self):
        password = self.cleaned_data['password']
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            raise forms.ValidationError(exc.messages)
        return password
```

- [ ] **Step 4: Crear la plantilla**

`apps/bookings/templates/bookings/alta_vendedora.html`:

```html
{% extends "admin/base_site.html" %}

{% block content %}
<h1>Dar de alta vendedora</h1>
<form method="post">
  {% csrf_token %}
  {{ form.as_p }}
  <input type="submit" value="Dar de alta">
</form>
{% endblock %}
```

- [ ] **Step 5: Reescribir el bloque `UserAdmin`/`GroupAdmin`**

En `apps/bookings/admin.py`, reemplazar el bloque completo (líneas ~429-444) por:

```python
from django.contrib.auth.password_validation import validate_password  # noqa: F401 (via forms.py)
from django.db import transaction
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from apps.tenancy.admin_mixins import EmpresaScopedUserAdminMixin
from apps.tenancy.models import MembresiaEmpresa

from .forms import AltaVendedoraForm

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(EmpresaScopedUserAdminMixin, BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    def get_urls(self):
        # Antes de super(): el admin termina en un catch-all <path:object_id>/.
        return [
            path(
                'dar-de-alta-vendedora/',
                self.admin_site.admin_view(self.dar_de_alta_vendedora_view),
                name='bookings_user_dar_de_alta_vendedora',
            ),
        ] + super().get_urls()

    def dar_de_alta_vendedora_view(self, request):
        es_operador = scope.es_operador_plataforma(request.user)
        if not (es_operador or request.user.groups.filter(name='Jefe').exists()):
            raise PermissionDenied

        if request.method == 'POST':
            form = AltaVendedoraForm(request.POST, es_operador=es_operador)
            if form.is_valid():
                empresa = form.cleaned_data['empresa'] if es_operador else scope.empresa_actual(request)
                with transaction.atomic():
                    nuevo = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        password=form.cleaned_data['password'],
                        first_name=form.cleaned_data['nombre'],
                        is_staff=True,
                    )
                    nuevo.groups.add(Group.objects.get(name='Vendedora'))
                    MembresiaEmpresa.objects.create(
                        user=nuevo, empresa=empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
                    )
                    Vendedora.objects.create(
                        usuario=nuevo, empresa=empresa, codigo=form.cleaned_data['codigo'],
                    )
                self.message_user(request, f'Vendedora {nuevo.get_username()} dada de alta.')
                return HttpResponseRedirect(reverse('admin:auth_user_changelist'))
        else:
            form = AltaVendedoraForm(es_operador=es_operador)

        return TemplateResponse(
            request, 'bookings/alta_vendedora.html',
            {**self.admin_site.each_context(request), 'form': form, 'title': 'Dar de alta vendedora'},
        )


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
```

(el import `validate_password` en `admin.py` no hace falta — vive en `forms.py`; quitar esa línea si se copió
por error al pegar.)

- [ ] **Step 6: Actualizar `backend/CLAUDE.md`**

En la sección "Roles: Jefes vs Vendedora", reemplazar el párrafo "Crear cuentas de vendedora: ..." por:

```markdown
- Crear cuentas de vendedora: acción "Dar de alta vendedora" en `/admin/auth/user/` (un jefe la ve para su
  propia Empresa; el operador de plataforma elige la Empresa). Crea el `User`, lo agrega al grupo `Vendedora`,
  su `MembresiaEmpresa` y su `bookings.Vendedora` en una sola transacción — reemplaza el flujo manual de tres
  pasos sueltos de antes de la expansión multi-sede.
```

Y en la sección "Panel de finanzas", reemplazar "Solo superusuarios: la vista corta con `is_superuser`" por:

```markdown
Corta con `scope.es_operador_plataforma(request.user)` (ve todas las Empresas) o
`scope.empresa_actual(request)` no vacío (ve la suya) — ya no con `is_superuser` (ver expansión multi-sede).
```

- [ ] **Step 7: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/bookings/forms.py apps/bookings/templates/bookings/alta_vendedora.html apps/bookings/admin.py backend/CLAUDE.md apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): UserAdmin/GroupAdmin escopeados y accion unificada para dar de alta vendedoras"
```

---

### Task B11: Rutas públicas — `empresa_slug`, `con_empresa`, filtros explícitos

**Files:**
- Modify: `apps/bookings/views.py`
- Modify: `apps/bookings/urls.py`
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `apps.tenancy.scope.resolver_empresa_publica(slug)`, `con_empresa(empresa)` (seccion Tenancy).
- Produces: `CupoDisponibleView.get(self, request, empresa_slug)`,
  `CupoRangoView.get(self, request, empresa_slug)`, `ReservaCheckoutView.post(self, request, empresa_slug)`,
  `ReservaCheckoutView._pendiente_de(empresa, checkout_id)` (gana `empresa` como primer argumento).

- [ ] **Step 1: Escribir el test que falla**

```python
from django.urls import reverse


class RutasPublicasEmpresaTests(TestCase):
    def setUp(self):
        self.empresa = crear_empresa(slug='empresa-cupo', nombre='Cupo')
        crear_flota(self.empresa)

    def test_responde_para_slug_valido(self):
        response = self.client.get(
            reverse('cupo', kwargs={'empresa_slug': self.empresa.slug}),
            {'fecha': (date.today() + timedelta(days=5)).isoformat()},
        )
        self.assertEqual(response.status_code, 200)

    def test_404_si_empresa_no_existe(self):
        response = self.client.get(
            reverse('cupo', kwargs={'empresa_slug': 'no-existe'}),
            {'fecha': (date.today() + timedelta(days=5)).isoformat()},
        )
        self.assertEqual(response.status_code, 404)

    def test_404_si_empresa_pausada(self):
        pausada = crear_empresa(slug='empresa-pausada', nombre='Pausada', activo=False)
        response = self.client.get(
            reverse('cupo', kwargs={'empresa_slug': pausada.slug}),
            {'fecha': (date.today() + timedelta(days=5)).isoformat()},
        )
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.RutasPublicasEmpresaTests -v 2`
Expected: `NoReverseMatch: Reverse for 'cupo' with keyword arguments '{'empresa_slug': ...}' not found` — la URL
todavía no acepta ese kwarg.

- [ ] **Step 3: Implementar `urls.py`**

```python
from django.urls import path

from .views import CupoDisponibleView, CupoRangoView, ReservaCheckoutView

urlpatterns = [
    path('<slug:empresa_slug>/cupo/', CupoDisponibleView.as_view(), name='cupo'),
    path('<slug:empresa_slug>/cupo/rango/', CupoRangoView.as_view(), name='cupo-rango'),
    path('<slug:empresa_slug>/reservas/', ReservaCheckoutView.as_view(), name='reserva-checkout'),
]
```

- [ ] **Step 4: Implementar `views.py`**

Agregar el import: `from apps.tenancy import scope`.

```python
class CupoDisponibleView(APIView):
    throttle_scope = 'consulta'

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            fecha = request.query_params.get('fecha')
            if not fecha:
                return Response({'detail': 'Falta el parametro fecha.'}, status=400)
            try:
                fecha = date.fromisoformat(fecha)
            except ValueError:
                return Response({'detail': 'fecha debe tener el formato YYYY-MM-DD.'}, status=400)

            try:
                personas = int(request.query_params.get('personas', MIN_PERSONAS))
            except (TypeError, ValueError):
                return Response({'detail': 'personas debe ser un numero entero.'}, status=400)
            if not (MIN_PERSONAS <= personas <= MAX_PERSONAS):
                return Response(
                    {'detail': f'personas debe estar entre {MIN_PERSONAS} y {MAX_PERSONAS}.'}, status=400,
                )

            motivo = evaluar_cupo(fecha, personas, empresa)
            data = {
                'fecha': fecha,
                'cupo_maximo': cupo_maximo_del_dia(fecha, empresa),
                'ocupadas': Reserva.objects.filter(
                    fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa=empresa,
                ).count(),
                'disponible': motivo is None,
                'proxima_disponible': proxima_fecha_disponible(fecha, personas, empresa),
                'motivo_no_disponible': motivo,
            }
            return Response(CupoSerializer(data).data)


class CupoRangoView(APIView):
    throttle_scope = 'consulta'

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            fechas = {}
            for nombre in ('desde', 'hasta'):
                crudo = request.query_params.get(nombre)
                if not crudo:
                    return Response({'detail': f'Falta el parametro {nombre}.'}, status=400)
                try:
                    fechas[nombre] = date.fromisoformat(crudo)
                except ValueError:
                    return Response({'detail': f'{nombre} debe tener el formato YYYY-MM-DD.'}, status=400)

            desde, hasta = fechas['desde'], fechas['hasta']
            if hasta < desde:
                return Response({'detail': 'hasta no puede ser anterior a desde.'}, status=400)
            if (hasta - desde).days + 1 > MAX_DIAS_RANGO:
                return Response({'detail': f'El rango no puede pasar de {MAX_DIAS_RANGO} dias.'}, status=400)

            try:
                personas = int(request.query_params.get('personas', MIN_PERSONAS))
            except (TypeError, ValueError):
                return Response({'detail': 'personas debe ser un numero entero.'}, status=400)
            if not (MIN_PERSONAS <= personas <= MAX_PERSONAS):
                return Response(
                    {'detail': f'personas debe estar entre {MIN_PERSONAS} y {MAX_PERSONAS}.'}, status=400,
                )

            return Response({
                'dias': {
                    fecha.isoformat(): motivo
                    for fecha, motivo in disponibilidad_por_fecha(desde, hasta, personas, empresa).items()
                }
            })


class ReservaCheckoutView(APIView):
    throttle_scope = 'reservas'

    def post(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            existente = self._pendiente_de(empresa, request.data.get('checkout_id'))

            if existente is None and not verificar_turnstile(
                request.data.get('captcha_token'), ip_del_cliente(request)
            ):
                return Response(
                    {'captcha': 'No pudimos verificar que eres una persona. Recarga e intenta de nuevo.'},
                    status=403,
                )

            serializer = ReservaCheckoutSerializer(
                existente, data=request.data, context={'request': request, 'empresa': empresa},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=200 if existente else 201)

    @staticmethod
    def _pendiente_de(empresa, checkout_id):
        try:
            uuid.UUID(str(checkout_id))
        except (ValueError, TypeError):
            return None

        return Reserva.objects.filter(
            checkout_id=checkout_id, estado=Reserva.Estado.PENDIENTE_PAGO, empresa=empresa,
        ).first()
```

- [ ] **Step 5: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/bookings/views.py apps/bookings/urls.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): rutas publicas de bookings ganan prefijo empresa_slug y con_empresa"
```

---

### Task B12: Panorama de la agenda — `armar_panorama(fecha, empresa)`

**Files:**
- Modify: `apps/bookings/panorama.py`
- Modify: `apps/bookings/admin.py` (una línea, `AgendaAdmin.changelist_view`)
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `scope.empresa_actual` (ya importado en `admin.py` desde B9).
- Produces: `armar_panorama(desde, empresa, dias=DIAS_DEL_PANORAMA)`.

- [ ] **Step 1: Escribir el test que falla**

```python
from .panorama import armar_panorama


class ArmarPanoramaEmpresaTests(TestCase):
    def test_panorama_no_mezcla_pangas_de_otra_empresa(self):
        empresa_a = crear_empresa(slug='empresa-a9', nombre='A9')
        empresa_b = crear_empresa(slug='empresa-b9', nombre='B9')
        crear_flota(empresa_a, composicion=[(1, 3)])
        crear_flota(empresa_b, composicion=[(2, 3)])

        panorama = armar_panorama(date.today(), empresa_a)
        self.assertEqual(len(panorama.renglones), 1)
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.ArmarPanoramaEmpresaTests -v 2`
Expected: `TypeError: armar_panorama() takes from 1 to 2 positional arguments but 2 were given` o, si pasa por
posición, `AssertionError: 3 != 1` (mezcla las pangas de las dos Empresas).

- [ ] **Step 3: Implementar**

```python
def armar_panorama(desde, empresa, dias=DIAS_DEL_PANORAMA):
    fechas = [desde + timedelta(days=i) for i in range(dias)]
    hasta = fechas[-1]

    embarcaciones = list(
        Embarcacion.objects.filter(activa=True, empresa=empresa).order_by('-capacidad_maxima', 'nombre')
    )

    fuera = {(f, e) for f, e in EmbarcacionNoDisponible.objects.filter(
        fecha__range=(desde, hasta), empresa=empresa,
    ).values_list('fecha', 'embarcacion_id')}

    asignadas = {}
    sin_panga = {fecha: [] for fecha in fechas}
    for reserva in Reserva.objects.filter(
        fecha__range=(desde, hasta), estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa=empresa,
    ).select_related('embarcacion'):
        if reserva.embarcacion_id:
            asignadas[(reserva.fecha, reserva.embarcacion_id)] = reserva
        else:
            sin_panga[reserva.fecha].append(reserva)

    renglones = [
        Renglon(
            embarcacion=embarcacion,
            celdas=[
                Celda(
                    reserva=asignadas.get((fecha, embarcacion.pk)),
                    disponible=(fecha, embarcacion.pk) not in fuera,
                )
                for fecha in fechas
            ],
        )
        for embarcacion in embarcaciones
    ]

    return Panorama(
        dias=fechas,
        renglones=renglones,
        sin_repartir=[sin_panga[fecha] for fecha in fechas],
        ocupadas=[
            sum(1 for e in embarcaciones if (fecha, e.pk) in asignadas) for fecha in fechas
        ],
        a_flote=[
            sum(1 for e in embarcaciones if (fecha, e.pk) not in fuera) for fecha in fechas
        ],
    )
```

En `apps/bookings/admin.py`, dentro de `AgendaAdmin.changelist_view` (ya escopeada por B9, esta tarea solo
cambia el argumento de la llamada):

```python
        return super().changelist_view(request, {
            **(extra_context or {}),
            'panorama': armar_panorama(timezone.localdate(), scope.empresa_actual(request)),
        })
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/panorama.py apps/bookings/admin.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): armar_panorama filtra por empresa"
```

---

### Task B13: Serializer del checkout — escopeo por `context['empresa']`

Los `PrimaryKeyRelatedField` de `punto_encuentro`/`extras` viven en serializers **anidados**
(`TransporteSeleccionSerializer`, `ExtraSeleccionSerializer`), instanciados en el cuerpo de clase del
serializer padre al importar el módulo — su `queryset=` se evalúa entonces, sin contexto. La forma correcta de
DRF para un queryset dinámico por-petición es sobrescribir `get_fields()` en el serializer que declara el
campo (no `__init__`, que no vuelve a correr tras el `deepcopy` que hace el padre).

**Files:**
- Modify: `apps/bookings/serializers.py`
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `context={'request': request, 'empresa': empresa}` (ya lo pasa `ReservaCheckoutView`, Task B11).

- [ ] **Step 1: Escribir el test que falla**

```python
import uuid

from rest_framework.test import APIRequestFactory

from .serializers import ReservaCheckoutSerializer


class SerializerEmpresaTests(TestCase):
    def test_extras_de_otra_empresa_no_pasan_el_checkout(self):
        empresa_a = crear_empresa(slug='empresa-a10', nombre='A10')
        empresa_b = crear_empresa(slug='empresa-b10', nombre='B10')
        crear_flota(empresa_a)
        extra_b = ExtrasItem.objects.create(
            empresa=empresa_b, tipo=ExtrasItem.Tipo.BRUNCH, nombre='Brunch', precio=Decimal('100'), activo=True,
        )

        factory = APIRequestFactory()
        request = factory.post('/api/empresa-a10/reservas/')
        serializer = ReservaCheckoutSerializer(data={
            'checkout_id': str(uuid.uuid4()),
            'fecha': (date.today() + timedelta(days=8)).isoformat(),
            'hora': '06:00',
            'numero_personas': 2,
            'nombre_cliente': 'Ana Ruiz',
            'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com',
            'moneda': 'MXN',
            'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz',
            'extras': [{'id': extra_b.pk}],
        }, context={'request': request, 'empresa': empresa_a})

        self.assertFalse(serializer.is_valid())
        self.assertIn('extras', serializer.errors)
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.SerializerEmpresaTests -v 2`
Expected: FAIL — `serializer.is_valid()` da `True` (el queryset de `extras.id` no filtra por empresa todavía,
acepta el id de `empresa_b`).

- [ ] **Step 3: Implementar**

En `TransporteSeleccionSerializer`:

```python
    def get_fields(self):
        fields = super().get_fields()
        fields['punto_encuentro'].queryset = PuntoEncuentro.objects.filter(
            activo=True, empresa=self.context['empresa'],
        )
        return fields
```

En `ExtraSeleccionSerializer`:

```python
    def get_fields(self):
        fields = super().get_fields()
        fields['id'].queryset = ExtrasItem.objects.filter(activo=True, empresa=self.context['empresa'])
        return fields
```

En `ReservaCheckoutSerializer.save()`, la resolución de `ref` gana `empresa`:

```python
        vendedora = Vendedora.por_codigo(self.validated_data.pop('ref', ''), self.context['empresa'])
```

En `_guardar`, extender el `try/except` para cubrir también `_sincronizar_extras` (hoy corre fuera de
cualquier `try`, así que un `ValidationError` de `ReservaExtra.clean()` — Task B8 — se escapa sin traducir y
responde 500 en una ruta pública):

```python
    def _guardar(self, reserva, extras, transporte):
        quiere_transporte = bool(transporte and (
            transporte.get('punto_encuentro') or transporte.get('direccion_personalizada')
        ))

        try:
            reserva.full_clean()
            if quiere_transporte:
                self._construir_transporte(reserva, transporte).full_clean(exclude=['reserva'])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            )

        reserva.save()

        try:
            self._sincronizar_extras(reserva, extras)
            if quiere_transporte:
                self._construir_transporte(reserva, transporte).save()
            else:
                ReservaTransporte.objects.filter(reserva=reserva).delete()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            )

        return reserva
```

Y `_sincronizar_extras` llama `full_clean()` antes de crear (hoy no lo hace en ningún punto del flujo):

```python
    def _sincronizar_extras(self, reserva, items_elegidos):
        ids_elegidos = {dato['id'].pk for dato in items_elegidos}
        reserva.extras_seleccionados.exclude(extras_item_id__in=ids_elegidos).delete()

        existentes = {
            extra.extras_item_id: extra
            for extra in reserva.extras_seleccionados.all()
        }
        for dato in items_elegidos:
            item, cantidad = dato['id'], dato['cantidad']
            extra = existentes.get(item.pk)
            if extra is None:
                nuevo = ReservaExtra(reserva=reserva, extras_item=item, cantidad_solicitada=cantidad)
                nuevo.full_clean()
                nuevo.save()
            elif extra.cantidad_solicitada != cantidad:
                extra.cantidad_solicitada = cantidad
                extra.save(update_fields=['cantidad_solicitada'])
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/serializers.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): serializer del checkout escopea punto_encuentro/extras por empresa"
```

---

### Task B14: Management commands — `revisar_cupo.py` + `limpiar_checkouts_abandonados.py`

Comandos de **catálogo/operación** (no de dinero, a diferencia de `conciliar_pagos.py`, fuera de este
documento): pueden filtrar `Empresa.objects.filter(activo=True)`, ver "Resolución de alcance" §4 del plan
principal.

**Files:**
- Modify: `apps/bookings/management/commands/revisar_cupo.py`
- Modify: `apps/bookings/management/commands/limpiar_checkouts_abandonados.py`
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `apps.tenancy.models.Empresa`, `apps.tenancy.scope.con_empresa` (seccion Tenancy).

- [ ] **Step 1: Escribir el test que falla**

```python
from io import StringIO

from django.core.management import call_command

from apps.fleet.models import Capitan


class ComandosEmpresaTests(TestCase):
    def test_limpiar_checkouts_no_cuenta_doble_entre_empresas(self):
        empresa_a = crear_empresa(slug='empresa-a11', nombre='A11')
        crear_empresa(slug='empresa-b11', nombre='B11')  # sin checkouts viejos
        vieja = Reserva.objects.create(**datos_reserva(empresa_a, estado=Reserva.Estado.PENDIENTE_PAGO))
        Reserva.objects.filter(pk=vieja.pk).update(creado_en=timezone.now() - timedelta(days=40))

        out = StringIO()
        call_command('limpiar_checkouts_abandonados', '--dry-run', stdout=out)

        self.assertIn('Se borrarian 1 checkout', out.getvalue())

    def test_revisar_cupo_no_mezcla_reservas_de_otra_empresa(self):
        empresa_a = crear_empresa(slug='empresa-a12', nombre='A12')
        empresa_b = crear_empresa(slug='empresa-b12', nombre='B12')
        crear_flota(empresa_a, composicion=[(1, 3)])
        crear_flota(empresa_b, composicion=[(1, 3)])
        fecha = date.today() + timedelta(days=30)

        # Dos reservas del mismo dia, cada una en su propia Empresa: cada una
        # cabe sola en su unica panga de 3. Si se mezclaran, "2 viajes
        # vendidos" contra 1 sola panga marcaria un falso problema.
        Reserva.objects.create(**datos_reserva(
            empresa_a, fecha=fecha, numero_personas=3, estado=Reserva.Estado.PAGADA,
        ))
        Reserva.objects.create(**datos_reserva(
            empresa_b, fecha=fecha, numero_personas=3, estado=Reserva.Estado.PAGADA,
        ))

        out = StringIO()
        call_command('revisar_cupo', stdout=out)
        self.assertNotIn('No cierra', out.getvalue())
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.ComandosEmpresaTests -v 2`
Expected: FAIL — ambos comandos todavía no filtran por Empresa, reportan cifras mezcladas.

- [ ] **Step 3: Implementar**

`revisar_cupo.py`:

```python
from apps.bookings.models import ESTADOS_QUE_OCUPAN_CUPO, Reserva, caben, cupo_maximo_del_dia
from apps.fleet.models import capacidades_por_fecha
from apps.tenancy import scope
from apps.tenancy.models import Empresa

DIAS_POR_DEFECTO = 90


class Command(BaseCommand):
    help = 'Lista los dias ya vendidos que no se pueden operar con la flota real, por Empresa.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=DIAS_POR_DEFECTO)

    def handle(self, *args, **options):
        desde = timezone.localdate()
        hasta = desde + timedelta(days=options['dias'] - 1)

        problemas_totales = 0
        for empresa in Empresa.objects.filter(activo=True):
            with scope.con_empresa(empresa):
                problemas_totales += self._revisar_empresa(empresa, desde, hasta)

        if problemas_totales:
            self.stdout.write(f'{problemas_totales} dia(s) por resolver a mano en total.')

    def _revisar_empresa(self, empresa, desde, hasta):
        grupos_por_fecha = {}
        for fecha, personas in Reserva.objects.filter(
            fecha__range=(desde, hasta), estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa=empresa,
        ).values_list('fecha', 'numero_personas'):
            grupos_por_fecha.setdefault(fecha, []).append(personas)

        capacidades = capacidades_por_fecha(desde, hasta, empresa)

        problemas = 0
        for fecha in sorted(grupos_por_fecha):
            grupos = sorted(grupos_por_fecha[fecha], reverse=True)
            if len(grupos) <= cupo_maximo_del_dia(fecha, empresa) and caben(grupos, capacidades[fecha]):
                continue

            problemas += 1
            self.stdout.write(
                f'[{empresa.slug}] {fecha}: {len(grupos)} viajes vendidos '
                f'({", ".join(str(g) for g in grupos)} personas) '
                f'y solo {len(capacidades[fecha])} pangas a flote '
                f'({", ".join(str(c) for c in capacidades[fecha])}). No cierra.'
            )
        return problemas
```

(mantener el resto del archivo — imports de `BaseCommand`/`timezone`/`timedelta` — sin cambios salvo lo de
arriba.)

`limpiar_checkouts_abandonados.py`:

```python
from apps.bookings.models import Reserva
from apps.tenancy import scope
from apps.tenancy.models import Empresa

DIAS_POR_DEFECTO = 30


class Command(BaseCommand):
    help = 'Borra los checkouts abandonados (pendiente_pago) mas viejos que N dias, en todas las Empresas.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=DIAS_POR_DEFECTO)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dias = options['dias']
        limite = timezone.now() - timedelta(days=dias)

        total = 0
        for empresa in Empresa.objects.filter(activo=True):
            with scope.con_empresa(empresa):
                viejos = Reserva.objects.filter(
                    estado=Reserva.Estado.PENDIENTE_PAGO, creado_en__lt=limite, empresa=empresa,
                )
                total += viejos.count()
                if not options['dry_run']:
                    viejos.delete()

        if options['dry_run']:
            self.stdout.write(f'Se borrarian {total} checkout(s) abandonado(s) de mas de {dias} dias.')
            return

        self.stdout.write(self.style.SUCCESS(
            f'{total} checkout(s) abandonado(s) de mas de {dias} dias borrado(s).'
        ))
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/management/commands/revisar_cupo.py apps/bookings/management/commands/limpiar_checkouts_abandonados.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): revisar_cupo y limpiar_checkouts_abandonados iteran por Empresa"
```

---

### Task B15: `setup_roles.py` — permisos exactos de `Jefe`/`Vendedora`/`OperadorPlataforma`

Con los jefes perdiendo `is_superuser`, este comando pasa de crear un solo grupo (`Vendedora`) a ser la única
fuente de permisos Django de los tres roles. Debe correr **antes** de
`migrar_la_paz_a_empresa.py` (seccion Tenancy), que asume que los tres grupos ya existen.

**Files:**
- Modify: `apps/bookings/management/commands/setup_roles.py`
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: modelos `tenancy.Sede`/`tenancy.Empresa`/`tenancy.MembresiaEmpresa` ya registrados como apps
  Django instaladas (seccion Tenancy) — solo se necesitan sus `ContentType`, no se importan directamente.

- [ ] **Step 1: Escribir el test que falla**

```python
class SetupRolesTests(TestCase):
    def test_jefe_no_tiene_permisos_sobre_auth_group(self):
        call_command('setup_roles')
        jefe = Group.objects.get(name='Jefe')
        self.assertFalse(
            jefe.permissions.filter(content_type__app_label='auth', content_type__model='group').exists()
        )
        self.assertTrue(jefe.permissions.filter(codename='view_user').exists())
        self.assertTrue(jefe.permissions.filter(codename='change_user').exists())
        self.assertFalse(jefe.permissions.filter(codename='add_user').exists())
        self.assertFalse(jefe.permissions.filter(codename='delete_user').exists())

    def test_operador_plataforma_si_tiene_auth_group(self):
        call_command('setup_roles')
        operador = Group.objects.get(name='OperadorPlataforma')
        self.assertTrue(
            operador.permissions.filter(content_type__app_label='auth', content_type__model='group').exists()
        )
        self.assertTrue(operador.permissions.filter(codename='add_user').exists())
```

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.SetupRolesTests -v 2`
Expected: `Group.DoesNotExist: Group matching query does not exist.` para `Jefe`/`OperadorPlataforma` — el
comando actual solo crea `Vendedora`.

- [ ] **Step 3: Implementar**

```python
"""Crea/actualiza los grupos 'Jefe', 'Vendedora' y 'OperadorPlataforma' con los
permisos de docs/contexto-negocio.md (seccion 5, Roles y permisos) mas los
ajustes de la expansion multi-sede (ver plan Pieza 1, Revision 8, H5).
Idempotente: correr de nuevo solo sincroniza permisos.

Debe correr ANTES de manage.py migrar_la_paz_a_empresa: ese comando asume
que estos tres grupos ya existen.
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

PERMISOS_VENDEDORA = [
    ('bookings', 'reserva', ['add', 'change', 'view']),
    ('bookings', 'agenda', ['change', 'view']),
    ('bookings', 'cupodiario', ['add', 'change', 'view']),
    ('bookings', 'checkoutabandonado', ['view']),
    ('bookings', 'vendedora', ['view']),
    ('fleet', 'embarcacion', ['view']),
    ('fleet', 'capitan', ['view']),
    ('fleet', 'puntoencuentro', ['view']),
    ('bookings', 'reservaextra', ['view']),
    ('bookings', 'reservatransporte', ['view']),
    ('fleet', 'embarcacionnodisponible', ['add', 'change', 'delete', 'view']),
]

# Todo lo que Vendedora no tiene: borrar, y el catalogo financiero completo
# (antes reservado a is_superuser=True). 'payments' no tiene modelos propios
# en el admin -- el cobro se opera via Stripe, no via CRUD local -- por eso
# no hay fila aparte para esa app.
PERMISOS_JEFE = PERMISOS_VENDEDORA + [
    ('bookings', 'reserva', ['delete']),
    ('bookings', 'cupodiario', ['delete']),
    ('bookings', 'vendedora', ['add', 'change', 'delete']),
    ('fleet', 'embarcacion', ['add', 'change', 'delete']),
    ('fleet', 'capitan', ['add', 'change', 'delete']),
    ('fleet', 'puntoencuentro', ['add', 'change', 'delete']),
    ('fleet', 'extrasitem', ['add', 'change', 'delete', 'view']),
    ('fleet', 'transporteprecio', ['add', 'change', 'delete', 'view']),
    ('fleet', 'codigopromocional', ['add', 'change', 'delete', 'view']),
    ('fleet', 'tarifa', ['add', 'change', 'view']),
    # H5: solo view+change sobre auth.user -- el alta pasa por la accion
    # "Dar de alta vendedora" (apps/bookings/admin.py), cuyo has_add_permission
    # bloquea el "Agregar usuario" directo del UserAdmin. Cero permisos sobre
    # auth.group: GroupAdmin queda exclusivo del operador de plataforma.
    ('auth', 'user', ['view', 'change']),
]

PERMISOS_OPERADOR = PERMISOS_JEFE + [
    ('auth', 'user', ['add', 'delete']),
    ('auth', 'group', ['add', 'change', 'delete', 'view']),
    ('tenancy', 'sede', ['add', 'change', 'delete', 'view']),
    ('tenancy', 'empresa', ['add', 'change', 'delete', 'view']),
    ('tenancy', 'membresiaempresa', ['add', 'change', 'delete', 'view']),
]


class Command(BaseCommand):
    help = "Crea/actualiza los grupos 'Jefe', 'Vendedora' y 'OperadorPlataforma'."

    def handle(self, *args, **options):
        vendedora = self._grupo('Vendedora', PERMISOS_VENDEDORA)
        jefe = self._grupo('Jefe', PERMISOS_JEFE)
        operador = self._grupo('OperadorPlataforma', PERMISOS_OPERADOR)
        self.stdout.write(self.style.SUCCESS(
            f"Grupos listos: Vendedora ({vendedora.permissions.count()}), "
            f"Jefe ({jefe.permissions.count()}), "
            f"OperadorPlataforma ({operador.permissions.count()})."
        ))

    def _grupo(self, nombre, permisos):
        group, _ = Group.objects.get_or_create(name=nombre)
        perms, vistos = [], set()
        for app_label, modelo, acciones in permisos:
            ct = ContentType.objects.get(app_label=app_label, model=modelo)
            for accion in acciones:
                clave = (app_label, modelo, accion)
                if clave in vistos:
                    continue
                vistos.add(clave)
                perms.append(Permission.objects.get(content_type=ct, codename=f'{accion}_{modelo}'))
        group.permissions.set(perms)
        return group
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/management/commands/setup_roles.py apps/bookings/tests_tenancy.py
git commit -m "feat(tenancy): setup_roles crea Jefe y OperadorPlataforma con permisos explicitos"
```

---

### Task B16: Señal de aviso de asignación — re-abre el alcance en el callback

Mismo bug que `notificar_reserva_pagada` (fuera de este documento, ver `apps/payments/services.py`): `SET
LOCAL` muere al COMMIT, así que un callback de `transaction.on_commit` no ve el alcance de la transacción que
lo encoló. Sin este fix, bajo RLS el `.update()` que marca "ya enviado" afecta 0 filas y **el correo se
reenvía duplicado en cada edición de la reserva, para siempre** — silenciado por el `except Exception` que ya
existe.

**Files:**
- Modify: `apps/bookings/signals.py`
- Modify: `apps/bookings/tests_tenancy.py`

**Interfaces:**
- Consumes: `apps.tenancy.scope.con_empresa(empresa)`, `apps.tenancy.models.Empresa` (seccion Tenancy).

- [ ] **Step 1: Escribir el test que falla**

```python
from apps.fleet.models import Capitan


class AvisoAsignacionRescopeTests(TestCase):
    def test_avisa_dentro_del_alcance_reabierto(self):
        empresa = crear_empresa(slug='empresa-aviso', nombre='Aviso')
        crear_flota(empresa)
        embarcacion = Embarcacion.objects.filter(empresa=empresa).first()
        capitan = Capitan.objects.create(empresa=empresa, nombre='Cap', telefono='6120000000')

        with mock.patch('apps.bookings.signals.enviar_correo_asignacion', return_value=True) as enviar_mock:
            with self.captureOnCommitCallbacks(execute=True):
                reserva = Reserva.objects.create(**datos_reserva(
                    empresa, estado=Reserva.Estado.PAGADA, embarcacion=embarcacion, capitan=capitan,
                ))

        enviar_mock.assert_called_once()
        reserva.refresh_from_db()
        self.assertIsNotNone(reserva.aviso_asignacion_enviado_en)
```

(necesita `from apps.fleet.models import Embarcacion` ya importado más arriba en el archivo por B8/B12; si no
está, agregarlo).

- [ ] **Step 2: Confirmar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy.AvisoAsignacionRescopeTests -v 2`
Expected: falla — sin el re-scope, bajo Postgres con RLS el `.update()` afecta 0 filas y
`aviso_asignacion_enviado_en` sigue `None` tras `refresh_from_db()` (en sqlite local sin RLS el bug no se
manifiesta igual, pero el test ya fija el contrato correcto para cuando CI corra contra Postgres).

- [ ] **Step 3: Implementar**

```python
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.notifications.services import enviar_correo_asignacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa

from .models import Reserva

logger = logging.getLogger(__name__)


def _le_toca_aviso(reserva):
    if not (reserva.embarcacion_id and reserva.capitan_id):
        return False
    if reserva.aviso_asignacion_enviado_en is not None:
        return False
    if reserva.estado == Reserva.Estado.CANCELADA:
        return False
    return reserva.fecha >= timezone.localdate()


@receiver(post_save, sender=Reserva, dispatch_uid='bookings.aviso_asignacion')
def avisar_asignacion(sender, instance, **kwargs):
    if not _le_toca_aviso(instance):
        return
    # SET LOCAL muere al COMMIT: el callback no puede depender del alcance de
    # la transaccion que lo encolo (ver "Quien corre fuera del alcance" del
    # plan principal). Se captura el entero, no el objeto, y se re-resuelve
    # todo -- Reserva incluida -- dentro de un con_empresa nuevo al ejecutarse.
    empresa_id = instance.empresa_id
    transaction.on_commit(lambda: _mandar(instance.pk, empresa_id))


def _mandar(reserva_pk, empresa_id):
    empresa = Empresa.objects.get(pk=empresa_id)
    with scope.con_empresa(empresa):
        try:
            reserva = Reserva.objects.select_related('capitan', 'embarcacion').get(pk=reserva_pk)
        except Reserva.DoesNotExist:
            return

        try:
            enviado = enviar_correo_asignacion(reserva)
        except Exception:
            logger.exception('Fallo el aviso de asignacion de la reserva %s', reserva.pk)
            return

        if not enviado:
            return

        Reserva.objects.filter(pk=reserva.pk).update(aviso_asignacion_enviado_en=timezone.now())
```

- [ ] **Step 4: Confirmar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_tenancy -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/signals.py apps/bookings/tests_tenancy.py
git commit -m "fix(tenancy): aviso de asignacion reabre el alcance dentro del callback on_commit"
```

---

## Self-Review

**Cobertura del File Map (sección bookings):** las 17 filas de `apps/bookings/*` del File Map principal están
cubiertas — modelos/FK/unicidad (B1-B4), motor de cupo (B5), código promocional/atribución (B6), consistencia
cruzada (B7-B8), admin genérico + usuarios (B9-B10), rutas públicas (B11), panorama (B12), serializer (B13),
comandos (B14), roles (B15), señal (B16). `backend/CLAUDE.md` se actualiza dentro de B10 (fila C3 del plan
principal). Lo único explícitamente fuera de alcance: la fila "Suite de tests existente" (retrofit de los 77
tests actuales) y todo lo de `apps/payments/*`/`apps/finance/*`/`apps/tenancy/*`/`apps/fleet/*` — tareas
aparte por diseño (ver cabecera).

**Placeholders:** ninguno — cada paso trae código completo, sin "TBD"/"similar a la tarea N".

**Consistencia de tipos/firmas entre tareas:** verificado que `evaluar_cupo`/`validar_cupo_diario`/
`cupo_maximo_del_dia`/`disponibilidad_por_fecha`/`proxima_fecha_disponible` (B5), `evaluar_codigo_promocional`/
`validar_codigo_promocional_en_pago`/`Vendedora.por_codigo` (B6) y `armar_panorama` (B12) se llaman en B11/B14
con la misma firma exacta con la que quedan definidas — no hay una tarea posterior usando un nombre de
parámetro o un orden distinto al que fijó la tarea que la introdujo.

---

### Test Suite Retrofit (X1-X13)

# Grupo X — Retrofit de la suite de tests existente

> Sección de tareas bite-sized del plan `docs/superpowers/plans/2026-08-31-expansion-multi-sede-pieza1-tenancy.md`
> (File Map ya aprobado, ver `<!-- arch-critic: APPROVED after round 9 spot-check -->` al final de ese
> archivo). Cubre únicamente las dos filas **`apps/testing.py`** y **`Suite de tests existente`** del
> File Map. NO cubre `apps/fleet/tests.py` (incluido su propio caso de threading,
> `EmbarcacionNoDisponibleUnicidadTests`) — eso pertenece al grupo de tareas de `fleet`.

**Prerrequisitos de este grupo (de otros grupos de tareas del mismo plan, deben estar mergeados antes de
empezar):** `apps.tenancy.models.{Sede, Empresa, MembresiaEmpresa}` y `apps.tenancy.scope.con_empresa`
existen y funcionan; `fleet`/`bookings` ya tienen el FK `empresa` aplicado (los 11 modelos de
"Tablas cubiertas por RLS"); `apps/bookings/management/commands/setup_roles.py` ya crea los tres grupos
Django (`Jefe`, `Vendedora`, `OperadorPlataforma`) con los permisos de la Revisión 8 (H5). Sin esto no
hay `empresa` que pasar ni grupos que asignar — estas tareas no son ejecutables antes.

**Nota de método sobre TDD en este grupo:** salvo la Tarea X1 (introduce comportamiento nuevo:
`EmpresaTestCase`, helpers), el resto de tareas **adaptan tests ya verdes a un esquema nuevo** — no hay
comportamiento nuevo que TDD-ear, el comportamiento ya está probado por los tests existentes. El ciclo de
cada tarea es: aplicar el retrofit → correr el archivo → corregir lo que rompa → correr la app completa →
commit. Se declara aquí una sola vez para no repetirlo en cada tarea.

**Hallazgo de esta sección, no cubierto en el File Map original:** con `EmpresaScopeMiddleware` envolviendo
`__call__` para todo usuario autenticado (caso 2 de "Resolución de alcance"), **cualquier test que haga
`self.client.force_login(...)` contra una vista del admin ahora pasa por
`scope.resolver_membresia_o_403(user)`**. Los ~26 call sites de este grupo que hoy usan
`User.objects.create_superuser(...)` para simular un jefe, o `User.objects.create_user(..., is_staff=True)`
sin membresía para simular una vendedora, dejarían de resolver alcance (0 membresías, no está en
`OperadorPlataforma`) y toda petición devolvería 403 — **incluidos los tests que hoy esperan 200**, y los
tests que hoy esperan 403 por *falta de permiso Django* pasarían igual pero por la razón equivocada (el
403 de alcance, no el de permiso), dejando de probar lo que dicen probar. Se corrige con dos helpers nuevos
en `EmpresaTestCase` (Tarea X1) que sustituyen `create_superuser`/`create_user(is_staff=True)` sueltos en
todo este grupo.

---

### Task X1: `apps/testing.py` — helpers de tenancy para toda la suite

**Files:**
- Modify: `apps/testing.py`
- Create: `apps/tests_testing.py`

**Interfaces:**
- Consumes: `apps.tenancy.models.Sede`, `apps.tenancy.models.Empresa`,
  `apps.tenancy.models.MembresiaEmpresa` (campo `rol`, choices `MembresiaEmpresa.Rol.JEFE` /
  `MembresiaEmpresa.Rol.VENDEDORA` — mismo patrón `TextChoices` interno que `Reserva.Estado`/
  `Embarcacion.Clase` en este repo; si la tarea que escribió `tenancy/models.py` usó otro nombre de
  atributo para las choices, ajustar solo esa referencia, la forma del resto no cambia).
  `apps.tenancy.scope.con_empresa(empresa)` (context manager, no reentrante con valor distinto,
  restaura al salir — ver plan, sección "Resolución de alcance").
  `apps.fleet.models.Embarcacion`. `django.contrib.auth.models.User`/`Group`.
  `django.core.management.call_command`.
- Produces: `EmpresaTestCase(TestCase)` — clase base nueva, con `self.sede`/`self.empresa` ya creados y
  el alcance ya abierto en cada test. `ApiTestCase(EmpresaTestCase)` — la que ya existe hoy, ahora hereda
  el setup de tenancy además de su `cache.clear()` propio. `crear_flota(empresa, composicion=FLOTA_REAL)`
  — firma nueva, `empresa` es ahora el primer argumento **obligatorio**. Dos métodos nuevos en
  `EmpresaTestCase`: `self.crear_jefe(username='jefa', **extra) -> User` y
  `self.crear_vendedora(username='vendedora', permisos=None, **extra) -> User` (ver Step 3).

- [ ] **Step 1: Escribir el test que falla**

Nuevo archivo `apps/tests_testing.py`:

```python
"""Pruebas del propio helper de tests — si esto se rompe, se rompe TODO lo demás."""
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase

from apps.testing import ApiTestCase, EmpresaTestCase, crear_flota
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede


class EmpresaTestCaseTests(TestCase):
    def test_crea_su_propia_sede_y_empresa(self):
        class Caso(EmpresaTestCase):
            def runTest(self):
                pass

        caso = Caso()
        caso._pre_setup()
        try:
            self.assertIsInstance(caso.sede, Sede)
            self.assertIsInstance(caso.empresa, Empresa)
            self.assertEqual(caso.empresa.slug, 'empresa-test')
            self.assertTrue(caso.empresa.activo)
        finally:
            caso._post_teardown()

    def test_no_choca_con_la_empresa_sembrada_por_la_migracion_de_datos(self):
        """`tenancy.0002_crear_sede_empresa_la_paz` ya deja una fila con
        slug='sal-y-sol' committeada antes de que arranque cualquier test — un
        TestCase normal ve esa fila (su transaccion no la oculta, solo aisla lo
        que el propio test escribe). Si EmpresaTestCase reusara ese mismo slug,
        el segundo `Empresa.objects.create(slug='sal-y-sol', ...)` reventaria con
        IntegrityError en el primer test que corriera. Por eso EmpresaTestCase usa
        un slug distinto ('empresa-test') a proposito."""
        self.assertTrue(Empresa.objects.filter(slug='sal-y-sol').exists())

    def test_el_alcance_queda_abierto_durante_el_test_y_cerrado_despues(self):
        class Caso(EmpresaTestCase):
            def runTest(self):
                pass

        caso = Caso()
        caso._pre_setup()
        alcance_durante = connection.alcance_actual
        caso._post_teardown()

        self.assertEqual(alcance_durante, caso.empresa.pk)
        self.assertIsNone(connection.alcance_actual)

    def test_crear_jefe_resuelve_alcance_como_jefe_de_su_empresa(self):
        class Caso(EmpresaTestCase):
            def runTest(self):
                pass

        caso = Caso()
        caso._pre_setup()
        try:
            jefe = caso.crear_jefe()
            self.assertTrue(Group.objects.get(name='Jefe').user_set.filter(pk=jefe.pk).exists())
            self.assertTrue(
                MembresiaEmpresa.objects.filter(
                    user=jefe, empresa=caso.empresa, rol=MembresiaEmpresa.Rol.JEFE,
                ).exists()
            )
        finally:
            caso._post_teardown()

    def test_crear_vendedora_sin_permisos_extra_no_tiene_ninguno(self):
        class Caso(EmpresaTestCase):
            def runTest(self):
                pass

        caso = Caso()
        caso._pre_setup()
        try:
            vendedora = caso.crear_vendedora(permisos=[])
            self.assertFalse(vendedora.user_permissions.exists())
            self.assertTrue(
                MembresiaEmpresa.objects.filter(
                    user=vendedora, empresa=caso.empresa,
                    rol=MembresiaEmpresa.Rol.VENDEDORA,
                ).exists()
            )
        finally:
            caso._post_teardown()


class CrearFlotaTests(ApiTestCase):
    def test_exige_empresa_como_primer_argumento(self):
        with self.assertRaises(TypeError):
            crear_flota()

    def test_crea_la_flota_solo_para_su_empresa(self):
        otra_sede = Sede.objects.create(nombre='Otra Sede', slug='otra-sede', zona_horaria='America/Mazatlan')
        otra_empresa = Empresa.objects.create(sede=otra_sede, nombre='Otra', slug='otra', activo=True)

        propia = crear_flota(self.empresa)
        self.assertTrue(all(p.empresa_id == self.empresa.pk for p in propia))

        # crear_flota de otra empresa no debe ver ni reusar la de self.empresa.
        from apps.tenancy import scope
        with scope.con_empresa(otra_empresa):
            ajena = crear_flota(otra_empresa)
        self.assertTrue(all(p.empresa_id == otra_empresa.pk for p in ajena))
        self.assertEqual(len(propia), len(ajena))
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `venv\Scripts\python.exe manage.py test apps.tests_testing -v 2`
Expected: FAIL — `ImportError: cannot import name 'EmpresaTestCase' from 'apps.testing'` (no existe
todavía), y `crear_flota()` hoy no exige `empresa`.

- [ ] **Step 3: Implementación mínima**

`apps/testing.py` completo:

```python
"""Utilidades compartidas por los tests de las apps."""

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from apps.fleet.models import Embarcacion
from apps.tenancy import scope
from apps.tenancy.models import Empresa, MembresiaEmpresa, Sede

# Slug deliberadamente distinto del que siembra tenancy.0002_crear_sede_empresa_la_paz
# ('sal-y-sol'): esa fila ya existe, committeada, en cualquier base de test recien
# migrada -- un TestCase normal la ve (su transaccion aisla lo que el test escribe, no
# lo que ya estaba antes de que empezara). Reusar el mismo slug aqui chocaria con
# IntegrityError en el primer test que corriera.
SLUG_EMPRESA_DE_PRUEBA = 'empresa-test'


class EmpresaTestCase(TestCase):
    """Base de tenancy para cualquier test que toque un modelo con FK `empresa`.

    Crea su propia Sede + Empresa en `_pre_setup` (antes de `setUp`, para que corra
    incluso en las ~20 clases de este repo que definen su propio `setUp` sin llamar a
    `super()`) y abre `scope.con_empresa(self.empresa)` para todo el ciclo de vida del
    test -- se cierra simetricamente en `_post_teardown` via el propio manejador de
    contexto guardado en la instancia, no con `addCleanup` (`_post_teardown` ya es el
    gancho simetrico de `_pre_setup`, correr ahi evita depender del orden entre
    cleanups registrados por el test y por esta clase).

    Tambien corre `setup_roles` (idempotente, mismo comando que producción) para que
    los grupos `Jefe`/`Vendedora`/`OperadorPlataforma` con sus permisos reales existan
    en la base de test -- sin esto `crear_jefe`/`crear_vendedora` (abajo) no tendrian
    grupo al que agregar al usuario.
    """

    def _pre_setup(self):
        super()._pre_setup()
        call_command('setup_roles', verbosity=0)
        self.sede = Sede.objects.create(
            nombre='Sede de prueba', slug='sede-test', zona_horaria='America/Mazatlan', activo=True,
        )
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Empresa de prueba', slug=SLUG_EMPRESA_DE_PRUEBA,
            activo=True, exclusiva=False,
        )
        self._alcance = scope.con_empresa(self.empresa)
        self._alcance.__enter__()

    def _post_teardown(self):
        self._alcance.__exit__(None, None, None)
        super()._post_teardown()

    def crear_jefe(self, username='jefa', **extra):
        """Usuario con membresia JEFE de `self.empresa` + grupo Django `Jefe`.

        Reemplaza `User.objects.create_superuser(...)` en toda la suite: los jefes ya
        no llevan `is_superuser` (ver plan, "Operador de plataforma: no es una
        MembresiaEmpresa"), y sin `MembresiaEmpresa`, `EmpresaScopeMiddleware` rechaza
        con 403 antes de que la vista corra.
        """
        extra.setdefault('password', 'x')
        jefe = User.objects.create_user(username, is_staff=True, **extra)
        jefe.groups.add(Group.objects.get(name='Jefe'))
        MembresiaEmpresa.objects.create(user=jefe, empresa=self.empresa, rol=MembresiaEmpresa.Rol.JEFE)
        return jefe

    def crear_vendedora(self, username='vendedora', permisos=None, **extra):
        """Usuario con membresia VENDEDORA de `self.empresa`.

        `permisos=None` (default) agrega el grupo `Vendedora` completo -- caso normal.
        `permisos=[]` u otra lista deja al usuario SIN el grupo, solo con los
        permisos individuales que se le pasen aparte (para probar 403 por falta de un
        permiso puntual sin que el 403 salga en realidad por falta de alcance, que es
        el bug que esta tarea corrige -- ver nota al inicio de este documento).
        """
        extra.setdefault('password', 'x')
        vendedora = User.objects.create_user(username, is_staff=True, **extra)
        if permisos is None:
            vendedora.groups.add(Group.objects.get(name='Vendedora'))
        MembresiaEmpresa.objects.create(
            user=vendedora, empresa=self.empresa, rol=MembresiaEmpresa.Rol.VENDEDORA,
        )
        return vendedora


class ApiTestCase(EmpresaTestCase):
    """Base para los tests que pegan a la API publica.

    DRF lleva la cuenta de peticiones por IP en el cache de Django, y ese cache
    **no** se reinicia entre tests como si pasa con la base de datos. Sin esto
    una clase hereda el contador de la anterior y revienta con 429 por peticiones
    que no hizo: un fallo que no tiene nada que ver con lo que se estaba probando
    y que ademas aparece y desaparece segun el orden en que corran los tests.

    El throttle queda **activo** durante los tests, no desactivado: es la misma
    configuracion que produccion, y asi un 429 inesperado se descubre aqui y no
    en el checkout de un cliente.
    """

    def _pre_setup(self):
        super()._pre_setup()
        cache.clear()


# La flota real del negocio: 8 pangas de hasta 3 personas y 2 de hasta 5.
FLOTA_REAL = [(8, 3), (2, 5)]


def crear_flota(empresa, composicion=FLOTA_REAL):
    """Da de alta la flota de `empresa` en la base de pruebas. Idempotente.

    Hace falta en cualquier test que cree una reserva: desde que el cupo es
    consciente del tamano del grupo, sin pangas en la base no cabe nadie y la
    validacion rechaza todo. Es el mismo fallo seguro que en produccion — solo que
    ahi la flota se captura una vez y aqui hay que sembrarla.

    `empresa` es obligatorio (antes no existia): sin filtrar por ella, en sqlite
    (sin RLS) la flota de una Empresa cuenta como capacidad de otra.
    """
    existentes = Embarcacion.objects.filter(empresa=empresa)
    if existentes.exists():
        return list(existentes)

    pangas = []
    for cuantas, capacidad in composicion:
        clase = Embarcacion.Clase.CHICA if capacidad <= 3 else Embarcacion.Clase.GRANDE
        for i in range(cuantas):
            pangas.append(Embarcacion(
                empresa=empresa, nombre=f'Panga {capacidad}-{i + 1}',
                clase=clase, capacidad_maxima=capacidad,
            ))
    return Embarcacion.objects.bulk_create(pangas)
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.tests_testing -v 2`
Expected: PASS, las 6 pruebas.

- [ ] **Step 5: Commit**

```bash
git add apps/testing.py apps/tests_testing.py
git commit -m "test: retrofit de apps/testing.py para tenancy (Sede/Empresa/roles por test)"
```

---

### Task X2: `apps/bookings/tests.py` — helpers de datos + primeras 4 clases

Archivo más grande de la suite (32 clases, ~1500 líneas). Se divide en dos tareas (X2, X3) para no
exceder el tamaño bite-sized; el resto de clases del archivo se completa en la Tarea X3.

**Files:**
- Modify: `apps/bookings/tests.py:1-330` aprox. (imports, helpers de módulo, y las clases
  `VentanaSalidaTests` a `CupoTests`, líneas 80-149 antes del retrofit).

**Interfaces:**
- Consumes: `apps.testing.EmpresaTestCase`, `crear_flota(empresa, ...)` (Tarea X1).
- Produces: `datos_reserva(empresa, **overrides) -> dict` (firma nueva, `empresa` primero) y
  `crear_reserva(empresa, **overrides) -> Reserva` — el resto de este archivo (Tarea X3) y
  `apps/finance/tests.py`/`apps/payments/tests.py` (que definen su **propia** copia local de estas dos
  funciones, no las importan de aquí) usan el mismo patrón, no estas funciones directamente.

- [ ] **Step 1: Cambiar los helpers de módulo**

`apps/bookings/tests.py`, reemplazar las líneas 48-77 (`envejecer` se queda igual, `datos_reserva` y
`crear_reserva` cambian):

```python
def datos_reserva(empresa, **overrides):
    # Hay tests que llaman Reserva(**datos_reserva(empresa)).full_clean() directo, y el
    # motor de cupo le pregunta a la flota: sin pangas no cabe nadie.
    crear_flota(empresa)
    base = {
        'empresa': empresa,
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
    }
    base.update(overrides)
    return base


def crear_reserva(empresa, **overrides):
    reserva = Reserva(**datos_reserva(empresa, **overrides))
    reserva.full_clean()
    reserva.save()
    return reserva
```

- [ ] **Step 2: Retrofit de las primeras 4 clases (patrón completo, demostrado)**

Líneas 80-149 — cambiar la base de clase de `TestCase` a `EmpresaTestCase` y enhebrar `self.empresa` en
cada llamada a `datos_reserva`/`crear_reserva`:

```python
class VentanaSalidaTests(EmpresaTestCase):
    def test_hora_fuera_de_la_ventana_es_invalida(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, hora=time(8, 0))).full_clean()


class NumeroPersonasTests(EmpresaTestCase):
    def test_el_tope_es_la_panga_mas_grande_de_la_flota(self):
        Reserva(**datos_reserva(self.empresa, numero_personas=MAX_PERSONAS)).full_clean()

        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, numero_personas=MAX_PERSONAS + 1)).full_clean()

    def test_seis_personas_ya_no_se_acepta(self):
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(self.empresa, numero_personas=6)).full_clean()

    def test_una_persona_es_valido(self):
        Reserva(**datos_reserva(self.empresa, numero_personas=1)).full_clean()

    def test_no_cabe_en_la_embarcacion_asignada(self):
        chica = Embarcacion.objects.create(
            empresa=self.empresa, nombre='La Chica',
            clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
        )
        reserva = Reserva(**datos_reserva(self.empresa, numero_personas=5, embarcacion=chica))
        with self.assertRaises(ValidationError) as ctx:
            reserva.full_clean()
        self.assertIn('embarcacion', ctx.exception.message_dict)


class DeslindeTests(EmpresaTestCase):
    def test_reserva_web_sin_deslinde_es_invalida(self):
        with self.assertRaises(ValidationError) as ctx:
            Reserva(**datos_reserva(self.empresa, deslinde_aceptado=False)).full_clean()
        self.assertIn('deslinde_aceptado', ctx.exception.message_dict)  # ajustar a la aserción real de cada test


class CupoTests(EmpresaTestCase):
    # Mismo patrón: cada Reserva(**datos_reserva(...)) / crear_reserva(...) de esta clase
    # gana self.empresa como primer argumento posicional; sin más cambios de lógica.
    ...
```

**Nota:** `DeslindeTests`/`CupoTests` arriba muestran solo el primer método como plantilla — el resto de
métodos de cada clase existente sigue exactamente igual salvo agregar `self.empresa` como primer argumento
a cada `datos_reserva(...)`/`crear_reserva(...)`/`Reserva(**datos_reserva(...))` que ya tuviera. No hay
lógica de aserción que cambie.

- [ ] **Step 3: Agregar el import**

`apps/bookings/tests.py`, en el bloque de imports (línea 23):

```python
from apps.testing import ApiTestCase, EmpresaTestCase, crear_flota
```

- [ ] **Step 4: Correr las 4 clases retrofiteadas**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests.VentanaSalidaTests apps.bookings.tests.NumeroPersonasTests apps.bookings.tests.DeslindeTests apps.bookings.tests.CupoTests -v 2`
Expected: FAIL en este punto — el resto del archivo (líneas 150+) todavía llama a
`datos_reserva()`/`crear_reserva()` con la firma vieja (sin `empresa`), y el import del módulo fallaría al
cargar la clase `CupoTests` si esta referencia algo de más abajo. Es esperado: la Tarea X3 completa el
archivo. Verificar en su lugar que el **error** es `TypeError: datos_reserva() missing 1 required
positional argument: 'empresa'` apuntando a líneas de la Tarea X3, no un error dentro de las 4 clases ya
retrofiteadas.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/tests.py
git commit -m "test: retrofit parcial de bookings/tests.py — helpers de datos + primeras 4 clases (1/2)"
```

---

### Task X3: `apps/bookings/tests.py` — resto de clases (28 restantes)

**Files:**
- Modify: `apps/bookings/tests.py:150-1519` (resto del archivo, tras la Tarea X2).

**Interfaces:**
- Consumes: `datos_reserva(empresa, **overrides)`, `crear_reserva(empresa, **overrides)` (Tarea X2),
  `EmpresaTestCase.crear_jefe()`/`.crear_vendedora()` (Tarea X1).
- Produces: nada nuevo — cierra el archivo, ningún otro archivo de este grupo lo importa.

- [ ] **Step 1: Retrofit mecánico — cambiar `TestCase` por `EmpresaTestCase`**

Las siguientes clases heredan hoy `TestCase` directo y pasan a heredar `EmpresaTestCase` (una palabra por
clase, sin más cambios en la firma de la clase):

`CambioDeFechaTests` (150), `CodigoPromocionalValidoTests` (179), `EvaluarCodigoPromocionalTests` (240),
`ValidarCodigoPromocionalEnPagoTests` (260), `TelefonoMarcableTests` (292, no crea filas tenant-scoped —
**no** necesita el cambio, se deja `TestCase`), `CheckoutAbandonadoTests` (305),
`LimpiarCheckoutsAbandonadosTests` (342), `LiquidacionEnEfectivoTests` (375),
`AdminDeCuentasTests` (450), `ReservasNuevasAdminTests` (484), `ReservaTransporteCleanTests` (814),
`ValidacionDeContactoTests` (1045, verificar si crea `Reserva`/`Embarcacion` — si no, se deja igual),
`ProximaFechaDisponibleTests` (1082), `CabenTests` (1151, función pura sobre listas de tuplas, **no**
toca modelos — se deja `TestCase`), `MotivoSinLugarTests` (1182, mismo caso, se deja `TestCase`),
`CupoPorTamanoDelGrupoTests` (1200), `RevisarCupoTests` (1314), `AgendaListaTests` (1345),
`TransicionDeAsignacionTests` (1386), `UnaSalidaPorDiaTests` (1474).
Las que ya heredan `ApiTestCase` (`CupoApiTests` 275, `ReservaApiTests` 546, `ExtrasYTransporteApiTests`
665, `AtribucionDeVentaTests` 850, `IpDelDeslindeTests` 938, `ThrottleTests` 997,
`CupoApiDevuelveProximaTests` 1139, `CupoApiPorTamanoTests` 1271) **no cambian de base** — `ApiTestCase`
ya hereda de `EmpresaTestCase` desde la Tarea X1, heredan el setup de tenancy automáticamente.

**Antes de tocar cada clase, revisar si de verdad crea una fila tenant-scoped** (`Reserva`, `Embarcacion`,
`CupoDiario`, `Vendedora`, `ExtrasItem`, `TransportePrecio`, `CodigoPromocional`, `PuntoEncuentro`,
`Capitan`) — las que no (funciones puras, parsers, tests de formato de texto) se dejan en `TestCase`, no
por ahorro sino porque forzar `EmpresaTestCase` en una clase que no la necesita es ruido que confunde al
próximo lector sobre qué prueba de verdad depende de tenancy.

- [ ] **Step 2: Enhebrar `self.empresa` en cada llamada — patrón completo, tres ejemplos representativos**

```python
class CambioDeFechaTests(EmpresaTestCase):
    def test_reprogramar_con_menos_de_48_horas_es_invalido(self):
        reserva = crear_reserva(self.empresa, fecha=date.today() + timedelta(days=10))
        reserva.fecha = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            reserva.full_clean()
```

```python
class CodigoPromocionalValidoTests(EmpresaTestCase):
    def test_codigo_existente_y_activo_es_valido(self):
        CodigoPromocional.objects.create(empresa=self.empresa, codigo='VERANO10', porcentaje_descuento=10)
        self.assertTrue(codigo_promocional_valido('VERANO10', self.empresa))
```

(`codigo_promocional_valido`/`evaluar_codigo_promocional`/`validar_codigo_promocional_en_pago` ganan
`empresa` como parámetro obligatorio en la retrofit de `apps/bookings/models.py`, fuera del alcance de
este grupo de tareas — aquí solo se actualiza el *call site* del test para pasarlo.)

```python
class RevisarCupoTests(EmpresaTestCase):
    def test_lista_los_dias_que_la_flota_no_puede_operar(self):
        crear_reserva(self.empresa, numero_personas=5)
        salida = StringIO()
        call_command('revisar_cupo', stdout=salida)
        self.assertIn('...', salida.getvalue())  # aserción real sin cambios, solo el setup gana self.empresa
```

Aplicar el mismo patrón (agregar `self.empresa` como primer argumento a toda llamada existente de
`datos_reserva(...)`, `crear_reserva(...)`, `Embarcacion.objects.create(...)`,
`CodigoPromocional.objects.create(...)`, `ExtrasItem.objects.create(...)`,
`TransportePrecio.objects.create(...)`, `CupoDiario.objects.create(...)`, `Vendedora.objects.create(...)`,
`PuntoEncuentro.objects.create(...)`, `Capitan.objects.create(...)`) al resto de métodos de las clases
listadas en el Step 1 — sin cambios en ninguna aserción existente.

- [ ] **Step 3: Reemplazar `create_superuser`/`create_user(is_staff=True)` sueltos**

Los 9 call sites de este archivo (líneas 320, 379-380, 461, 503, 509, 513, 528, 535, 542 en el archivo
original, antes del retrofit — buscar `create_superuser`/`create_user.*is_staff` tras aplicar los Steps 1-2
porque los números de línea ya se habrán movido) pasan de:

```python
self.client.force_login(User.objects.create_superuser('jefa', password='x'))
```

a:

```python
self.client.force_login(self.crear_jefe())
```

y de:

```python
vendedora = User.objects.create_user('sin_permisos', password='x', is_staff=True)
self.client.force_login(vendedora)
self.assertEqual(self.client.get(self.url).status_code, 403)
```

(caso `ReservasNuevasAdminTests.test_staff_sin_permiso_de_ver_reservas_recibe_403`, línea 501-504) a:

```python
vendedora = self.crear_vendedora(username='sin_permisos', permisos=[])
self.client.force_login(vendedora)
self.assertEqual(self.client.get(self.url).status_code, 403)
```

(sin el grupo `Vendedora`, la membresía de empresa igual resuelve pero el permiso Django `view_reserva`
sigue faltando — el 403 ahora sí viene del chequeo de permiso que el test dice probar, no del alcance) y

```python
vendedora = User.objects.create_user('vendedora', password='x', is_staff=True)
vendedora.user_permissions.add(Permission.objects.get(codename='view_reserva'))
self.client.force_login(vendedora)
```

(línea 506-509) a:

```python
vendedora = self.crear_vendedora(username='vendedora', permisos=[])
vendedora.user_permissions.add(Permission.objects.get(codename='view_reserva'))
self.client.force_login(vendedora)
```

- [ ] **Step 4: Correr el archivo completo**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests -v 2`
Expected: PASS, las 32 clases.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/tests.py
git commit -m "test: retrofit de bookings/tests.py para tenancy — resto de clases (2/2)"
```

---

### Task X4: `apps/bookings/tests_agenda.py`

**Files:**
- Modify: `apps/bookings/tests_agenda.py`

**Interfaces:**
- Consumes: `apps.testing.EmpresaTestCase`, `crear_flota(empresa)`, `.crear_jefe()`, `.crear_vendedora()`
  (Tarea X1). `apps.bookings.panorama.armar_panorama(fecha, empresa)` (firma nueva tras la retrofit de
  `apps/bookings/panorama.py`, fuera de este grupo — ver fila del File Map).

- [ ] **Step 1: Helpers de módulo**

Reemplazar `datos`/`viaje` (líneas 23-44):

```python
def datos(empresa, **overrides):
    base = {
        'empresa': empresa,
        'fecha': date.today() + timedelta(days=3),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
        'estado': Reserva.Estado.PAGADA,
    }
    base.update(overrides)
    return base


def viaje(empresa, **overrides):
    """Se guarda sin full_clean para poder sembrar fechas pasadas: la regla de las
    48 horas no deja reprogramar hacia atras, y aqui hace falta un atrasado."""
    crear_flota(empresa)
    return Reserva.objects.create(**datos(empresa, **overrides))
```

- [ ] **Step 2: `AgendaAdminTests` — patrón completo**

```python
class AgendaAdminTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(self.crear_jefe())

    def _filas(self, **params):
        respuesta = self.client.get(self.url, params)
        self.assertEqual(respuesta.status_code, 200)
        return {r.pk for r in respuesta.context['cl'].result_list}

    def test_el_modo_manana_trae_solo_manana(self):
        manana = viaje(self.empresa, fecha=date.today() + timedelta(days=1))
        viaje(self.empresa, fecha=date.today() + timedelta(days=2))

        self.assertEqual(self._filas(cuando='manana'), {manana.pk})

    # ... el resto de métodos de esta clase: mismo patrón, self.empresa como
    # primer argumento de cada viaje(...).
```

- [ ] **Step 3: `AgendaPermisosTests` — ya sigue casi el patrón correcto, simplificar**

Líneas 134-157, hoy:

```python
class AgendaPermisosTests(TestCase):
    def setUp(self):
        crear_flota()
        call_command('setup_roles')
        self.vendedora = User.objects.create_user(
            'maria', 'maria@example.com', 'x', is_staff=True)
        self.vendedora.groups.add(Group.objects.get(name='Vendedora'))
        self.client.force_login(self.vendedora)
```

pasa a:

```python
class AgendaPermisosTests(EmpresaTestCase):
    def setUp(self):
        crear_flota(self.empresa)
        self.vendedora = self.crear_vendedora(username='maria')
        self.client.force_login(self.vendedora)
```

(`call_command('setup_roles')` ya no hace falta aquí explícito — `EmpresaTestCase._pre_setup` lo corre
para toda la suite. `crear_vendedora` ya agrega el grupo `Vendedora` por default.) El resto de la clase
(los 3 tests) no cambia.

- [ ] **Step 4: `MenuLateralTests` — sin cambios**

No crea filas tenant-scoped (lee `settings.UNFOLD['SIDEBAR']` directo) — se deja `TestCase`, sin retrofit.

- [ ] **Step 5: `AnchoDeColumnasTests`/`AvisoDeReservasNuevasTests` — mismo patrón que Step 2**

```python
class AnchoDeColumnasTests(EmpresaTestCase):
    HOJA = 'bookings/admin-columnas.css'

    def setUp(self):
        crear_flota(self.empresa)
        self.client.force_login(self.crear_jefe())

    # resto de métodos sin cambios


class AvisoDeReservasNuevasTests(EmpresaTestCase):
    SCRIPT = 'bookings/reservas-nuevas.js'

    def setUp(self):
        crear_flota(self.empresa)
        self.client.force_login(self.crear_jefe())

    # resto de métodos: cada llamada a armar_panorama/queries internas del endpoint
    # de conteo ya recibe self.empresa via la vista (retrofit de bookings/views.py,
    # fuera de este grupo) — nada que enhebrar aquí a mano.
```

- [ ] **Step 6: Actualizar imports**

```python
from apps.testing import EmpresaTestCase, crear_flota
```

Quitar el import de `TestCase` si ya ninguna clase del archivo lo usa (verificar `MenuLateralTests` sigue
necesitándolo).

- [ ] **Step 7: Correr el archivo**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_agenda -v 2`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/bookings/tests_agenda.py
git commit -m "test: retrofit de bookings/tests_agenda.py para tenancy"
```

---

### Task X5: `apps/bookings/tests_cupo_rango.py`

**Files:**
- Modify: `apps/bookings/tests_cupo_rango.py`

**Interfaces:**
- Consumes: `apps.testing.ApiTestCase`, `crear_flota(empresa)` (Tarea X1).
  `disponibilidad_por_fecha(fecha_inicio, fecha_fin, personas, empresa)` (firma nueva tras retrofit de
  `bookings/models.py`, fuera de este grupo).

- [ ] **Step 1: Helper de módulo + clase de test**

```python
def crear_reserva(empresa, fecha, personas):
    """Reserva que ocupa cupo, sin pasar por la validacion del checkout."""
    return Reserva.objects.create(
        empresa=empresa,
        fecha=fecha,
        hora=time(6, 0),
        numero_personas=personas,
        nombre_cliente='Cliente',
        telefono_cliente='+5216121234567',
        correo_cliente='cliente@example.com',
        moneda='MXN',
        canal_origen=Reserva.CanalOrigen.WHATSAPP,
        estado=Reserva.Estado.PAGADA,
    )


class DisponibilidadPorFechaTests(EmpresaTestCase):
    """El calculo puro, sin pasar por HTTP."""

    def setUp(self):
        crear_flota(self.empresa)
        self.lunes = date(2026, 9, 7)

    def test_devuelve_una_entrada_por_dia_del_rango(self):
        mapa = disponibilidad_por_fecha(
            self.lunes, self.lunes + timedelta(days=6), personas=2, empresa=self.empresa,
        )
        self.assertEqual(len(mapa), 7)
        self.assertEqual(min(mapa), self.lunes)
        self.assertEqual(max(mapa), self.lunes + timedelta(days=6))

    def test_un_dia_vacio_esta_disponible(self):
        mapa = disponibilidad_por_fecha(self.lunes, self.lunes, personas=2, empresa=self.empresa)
        self.assertIsNone(mapa[self.lunes])

    def test_un_dia_cerrado_por_cupo_diario_sale_lleno(self):
        CupoDiario.objects.create(empresa=self.empresa, fecha=self.lunes, cupo_maximo=0)
        mapa = disponibilidad_por_fecha(self.lunes, self.lunes, personas=1, empresa=self.empresa)
        self.assertEqual(mapa[self.lunes], MOTIVO_LLENO)
```

(Este archivo hoy solo tiene la clase mostrada, 60 líneas — no hay clases adicionales que retrofitear con
"mismo patrón".)

- [ ] **Step 2: Import**

```python
from apps.testing import EmpresaTestCase, crear_flota
```

(cambia de `TestCase` a `EmpresaTestCase`; ya no se necesita `ApiTestCase` aquí, esta clase no pega a la
API HTTP.)

- [ ] **Step 3: Correr el archivo**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_cupo_rango -v 2`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/bookings/tests_cupo_rango.py
git commit -m "test: retrofit de bookings/tests_cupo_rango.py para tenancy"
```

---

### Task X6: `apps/bookings/tests_aviso_asignacion.py`

**Files:**
- Modify: `apps/bookings/tests_aviso_asignacion.py`

**Interfaces:**
- Consumes: `apps.testing.EmpresaTestCase` (Tarea X1). Prueba el comportamiento de
  `apps/bookings/signals.py` corregido en la Tarea N1 del plan (re-abre `scope.con_empresa(...)` dentro
  del callback de `transaction.on_commit`, ver "Quién corre fuera del alcance" #1 en el plan).

- [ ] **Step 1: `setUp` — patrón completo**

```python
class AvisoDeAsignacionTests(EmpresaTestCase):
    def setUp(self):
        self.embarcacion = Embarcacion.objects.create(
            empresa=self.empresa, nombre='Dona Chuy',
            clase=Embarcacion.Clase.CHICA, capacidad_maxima=6,
        )
        self.capitan = Capitan.objects.create(
            empresa=self.empresa, nombre='Ramon Geraldo', telefono='+5216129876543',
        )
        self.reserva = Reserva.objects.create(
            empresa=self.empresa,
            fecha=date.today() + timedelta(days=10),
            hora=time(6, 0),
            numero_personas=2,
            nombre_cliente='Ana Ruiz',
            telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com',
            moneda='MXN',
            deslinde_aceptado=True,
            deslinde_nombre='Ana Ruiz',
            estado=Reserva.Estado.PAGADA,
            canal_origen=Reserva.CanalOrigen.WEB,
        )
```

El resto de la clase (`_asignar`, y los 4+ métodos `test_*`) no cambia — ninguno crea filas nuevas fuera
de `setUp`.

- [ ] **Step 2: Test nuevo — cubre directamente el bug N1 que esta clase existe para prevenir**

Agregar al final de la clase, después de los tests existentes (`test_guardar_de_nuevo_no_reenvia`,
`test_cambiar_de_capitan_no_reenvia`, etc.):

```python
    def test_el_correo_se_manda_bajo_rls_aunque_el_alcance_de_la_vista_ya_haya_cerrado(self):
        """Regresión directa de la Revisión 4, N1: `notificar_reserva_pagada`/el
        aviso de asignación corren en `transaction.on_commit`, fuera del `with
        scope.con_empresa(...)` que los encoló — antes de la corrección, bajo RLS
        el `.update()` que sella `aviso_asignacion_enviado_en` afectaba 0 filas y
        el correo se reenviaba en cada edición, para siempre."""
        with mock.patch(ENVIO, return_value=True):
            self._asignar()
        primer_envio = Reserva.objects.get(pk=self.reserva.pk).aviso_asignacion_enviado_en
        self.assertIsNotNone(primer_envio)

        # Simula exactamente lo que el bug dejaba pasar: guardar la reserva otra
        # vez con el mismo estado, fuera de cualquier alcance nuevo abierto a mano.
        with mock.patch(ENVIO, return_value=True) as enviar:
            self.reserva.refresh_from_db()
            self.reserva.numero_personas = 3
            with self.captureOnCommitCallbacks(execute=True):
                self.reserva.save()

        enviar.assert_not_called()
        self.assertEqual(
            Reserva.objects.get(pk=self.reserva.pk).aviso_asignacion_enviado_en, primer_envio,
        )
```

(Este test solo tiene sentido correr contra Postgres con RLS activo — en sqlite pasaría igual con o sin
el fix de N1, porque no hay política que filtre el `.update()`. Se deja sin `skipUnless` a propósito: en
sqlite prueba que el `.update()` sigue siendo correcto por lógica de negocio aunque no ejerza RLS; el CI
de Postgres es quien de verdad ejerce el escenario del bug.)

- [ ] **Step 3: Import**

```python
from apps.testing import EmpresaTestCase
```

(quita el import de `TestCase` si ya no se usa en el archivo.)

- [ ] **Step 4: Correr el archivo**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_aviso_asignacion -v 2`
Expected: PASS, incluido el test nuevo.

- [ ] **Step 5: Commit**

```bash
git add apps/bookings/tests_aviso_asignacion.py
git commit -m "test: retrofit de tests_aviso_asignacion.py + regresión directa de N1"
```

---

### Task X7: `apps/bookings/tests_concurrencia.py` — caso especial de hilos

**No es retrofit mecánico.** `TransactionTestCase` no admite `EmpresaTestCase` tal cual (hereda de
`TestCase`, que envuelve cada test en una transacción que `TransactionTestCase` no usa — y el problema real
de esta clase es que cada hilo abre **su propia conexión**, que `con_empresa` del hilo principal no cubre;
ver plan, "Quién corre fuera del alcance" #5).

**Files:**
- Modify: `apps/bookings/tests_concurrencia.py`

**Interfaces:**
- Consumes: `apps.tenancy.scope.con_empresa(empresa)` (usado dentro de cada `target` de hilo, pasando
  `empresa_id` capturado antes de lanzar el hilo — no el objeto `Empresa`, para no depender de un FK
  perezoso resuelto en la conexión equivocada). `crear_flota(empresa)`.

- [ ] **Step 1: Helper de datos + `setUp` de las dos clases**

```python
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


def _crear_empresa_de_prueba():
    """`TransactionTestCase` trunca las tablas entre casos -- no hereda el `setUp`
    de `EmpresaTestCase` (pensado para `TestCase`, transaccional). Cada test de este
    archivo crea su propia Sede/Empresa desde cero, igual que hacía antes con la
    flota."""
    sede = Sede.objects.create(nombre='Sede concurrencia', slug='sede-concurrencia', zona_horaria='America/Mazatlan')
    return Empresa.objects.create(sede=sede, nombre='Empresa concurrencia', slug='empresa-concurrencia', activo=True)


def _datos(empresa, **overrides):
    base = {
        'empresa': empresa,
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
    }
    base.update(overrides)
    return base
```

- [ ] **Step 2: `SobreventaConcurrenteTests.setUp` — envolver en `con_empresa` propio, commiteado**

```python
@SOLO_POSTGRES
class SobreventaConcurrenteTests(TransactionTestCase):
    """El ultimo lugar del dia solo se puede vender una vez."""

    def setUp(self):
        self.empresa = _crear_empresa_de_prueba()
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            self.fecha = date.today() + timedelta(days=10)

            # Se llena el dia hasta dejar exactamente un lugar libre.
            for _ in range(CUPO_MAXIMO_DEFAULT - 1):
                reserva = Reserva(**_datos(self.empresa, fecha=self.fecha, estado=Reserva.Estado.PAGADA))
                reserva.full_clean()
                reserva.save()

            # Dos clientes distintos, los dos a punto de pagar ese ultimo lugar.
            self.pendientes = []
            for nombre in ('Cliente Uno', 'Cliente Dos'):
                reserva = Reserva(**_datos(
                    self.empresa, fecha=self.fecha, nombre_cliente=nombre,
                    precio_total=Decimal('4500.00'), forma_pago=Reserva.FormaPago.COMPLETO,
                ))
                reserva.full_clean()
                reserva.save()
                self.pendientes.append(reserva)
        # `con_empresa` abre `transaction.atomic()` -- al salir del `with` aquí, en
        # setUp, ese atomic hace COMMIT de verdad (TransactionTestCase no envuelve el
        # test en una transacción exterior como TestCase sí hace) -- las filas quedan
        # committeadas y visibles para las conexiones nuevas que abrirán los hilos.
        # Sin este `with` explícito, la Revisión 5 (B8) advertía justo este caso:
        # datos creados dentro de un atomic no commiteado son invisibles cross-conexión,
        # justo la visibilidad que TransactionTestCase existe para dar.
```

- [ ] **Step 3: `_pagar_en_paralelo` — cada hilo abre su propio alcance**

```python
    def _pagar_en_paralelo(self):
        """Aplica los dos pagos a la vez, cada uno en su propio hilo y conexion.

        Devuelve la lista de resultados de aplicar_pago_exitoso.
        """
        import threading

        from apps.payments.services import aplicar_pago_exitoso

        empresa_id = self.empresa.pk  # capturado ANTES de lanzar el hilo: el objeto
        # `Empresa` resuelto en la conexión principal no debe cruzar al hilo, cada
        # hilo debe resolver el suyo en su propia conexión (ver plan, punto 1 de
        # "Quién corre fuera del alcance" -- misma regla que un callback on_commit).
        resultados = [None, None]
        errores = [None, None]
        arrancar = threading.Barrier(2)

        def pagar(indice):
            try:
                arrancar.wait(timeout=10)
                empresa_del_hilo = Empresa.objects.get(pk=empresa_id)
                with scope.con_empresa(empresa_del_hilo):
                    resultados[indice] = aplicar_pago_exitoso(_intent_falso(self.pendientes[indice]))
            except Exception as exc:  # noqa: BLE001 — se re-lanza en el hilo principal
                errores[indice] = exc
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=pagar, args=(i,)) for i in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=30)

        for e in errores:
            if e is not None:
                raise e
        return resultados
```

Los dos métodos `test_*` de `SobreventaConcurrenteTests` no cambian — siguen filtrando por
`fecha=self.fecha`/`pk__in=[...]`, que ya identifican filas únicas sin necesitar `empresa=` explícito en
la aserción (aunque agregarlo no estorba: `Reserva.objects.filter(fecha=self.fecha, empresa=self.empresa, ...)`
es más preciso y se recomienda).

- [ ] **Step 4: `LockDelDiaTests` — mismo patrón, más simple**

```python
@SOLO_POSTGRES
class LockDelDiaTests(TransactionTestCase):
    """El lock es por fecha, no global: dos dias distintos no deben estorbarse."""

    def setUp(self):
        self.empresa = _crear_empresa_de_prueba()
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)

    def test_dias_distintos_no_se_bloquean_entre_si(self, refund=None):
        import threading

        from apps.payments.services import APLICADO, aplicar_pago_exitoso

        empresa_id = self.empresa.pk
        with scope.con_empresa(self.empresa):
            reservas = []
            for i in range(2):
                reserva = Reserva(**_datos(
                    self.empresa, fecha=date.today() + timedelta(days=10 + i),
                    precio_total=Decimal('4500.00'), forma_pago=Reserva.FormaPago.COMPLETO,
                ))
                reserva.full_clean()
                reserva.save()
                reservas.append(reserva)

        resultados = [None, None]
        arrancar = threading.Barrier(2)

        def pagar(indice):
            try:
                arrancar.wait(timeout=10)
                empresa_del_hilo = Empresa.objects.get(pk=empresa_id)
                with scope.con_empresa(empresa_del_hilo):
                    resultados[indice] = aplicar_pago_exitoso(_intent_falso(reservas[indice]))
            finally:
                connections.close_all()

        hilos = [threading.Thread(target=pagar, args=(i,)) for i in range(2)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=30)

        self.assertEqual(resultados, [APLICADO, APLICADO])
```

(el decorador `@mock.patch('apps.payments.services.stripe.Refund.create')` existente se conserva tal
cual sobre el método — se omitió arriba solo para no repetir la firma completa; restaurar el decorador y
el parámetro `refund` como estaban.)

- [ ] **Step 5: Correr el archivo (requiere Postgres — `skipUnless` lo salta en sqlite)**

Run: `venv\Scripts\python.exe manage.py test apps.bookings.tests_concurrencia -v 2`
Expected en sqlite local: `OK (skipped=4)`. Expected en CI (Postgres, rol sin `BYPASSRLS`): PASS real,
las 3 pruebas ejercitando la carrera bajo RLS.

- [ ] **Step 6: Commit**

```bash
git add apps/bookings/tests_concurrencia.py
git commit -m "test: retrofit de tests_concurrencia.py — con_empresa propio por hilo"
```

---

### Task X8: `apps/payments/tests.py` — retrofit mecánico (helpers + clases sin mocks de Stripe)

Archivo más grande junto con `bookings/tests.py` (9 clases, ~1200 líneas, 52 `mock.patch('stripe.*')`).
Se divide en dos tareas: esta (helpers de datos + clases que no tocan `stripe_client`) y la Tarea X9
(reescritura de los 52 mocks contra `StripeClient`).

**Files:**
- Modify: `apps/payments/tests.py` (helper `crear_reserva`, `LlavesDeStripeCruzadasTests` — no toca
  modelos tenant-scoped, se deja `TestCase` sin cambios —, y `seleccionar_extra`/`seleccionar_transporte`).

**Interfaces:**
- Consumes: `apps.testing.ApiTestCase`, `crear_flota(empresa)` (Tarea X1).

- [ ] **Step 1: Helper `crear_reserva`**

Líneas 89-107 aprox., agrega `empresa` como primer argumento, mismo patrón que en `bookings/tests.py`:

```python
def crear_reserva(empresa, **overrides):
    crear_flota(empresa)
    datos = {
        'empresa': empresa,
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
    }
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva
```

- [ ] **Step 2: `seleccionar_extra`/`seleccionar_transporte` ganan `empresa=` en sus `create()` internos**

Estos dos métodos viven dentro de una clase con `setUp` propio (ver Step 3) — se muestran aquí porque su
retrofit es idéntico en cada una de las clases que los redefinen:

```python
    def seleccionar_extra(self, reserva=None, cantidad_solicitada=1, **overrides):
        datos = {
            'empresa': self.empresa,
            'tipo': ExtrasItem.Tipo.BRUNCH, 'nombre': 'Brunch', 'precio': Decimal('300'),
            'precio_usd': Decimal('18'), 'cobrar_por_persona': True,
        }
        datos.update(overrides)
        item = ExtrasItem.objects.create(**datos)
        return ReservaExtra.objects.create(
            reserva=reserva or self.reserva, extras_item=item, cantidad_solicitada=cantidad_solicitada,
        )

    def seleccionar_transporte(self, reserva=None, zona=TransportePrecio.Zona.CENTRO, **precio_overrides):
        datos = {
            'empresa': self.empresa, 'zona': zona, 'precio_base': Decimal('2000'),
            'recargo_grupo': Decimal('1500'), 'min_personas_recargo': 4,
        }
        datos.update(precio_overrides)
        TransportePrecio.objects.create(**datos)
        return ReservaTransporte.objects.create(
            reserva=reserva or self.reserva, zona=zona, direccion_personalizada='Malecon 123',
        )
```

- [ ] **Step 3: Cambiar base de clase — lista completa**

Todas las clases de este archivo que crean `Reserva`/`Tarifa`/`ExtrasItem`/`TransportePrecio`/
`CodigoPromocional` pasan de `TestCase`/`ApiTestCase` sin tenancy a heredar de `ApiTestCase`
(ya trae tenancy desde la Tarea X1) o `EmpresaTestCase` según corresponda:
`LlavesDeStripeCruzadasTests` — **sin cambios**, no toca modelos.
El resto (`CrearPagoView...Tests`, la clase con `seleccionar_extra`/`seleccionar_transporte`,
`WebhookTests`, `ConciliarPagosTests`, `VersionDeApiTests` — este último tampoco toca modelos, sin
cambios) ya heredan `ApiTestCase`/`TestCase` según el patrón de la Tarea X1 — cada `setUp` de estas
clases gana `self.empresa` como ya viene de la base, y cada `Tarifa.objects.create(precio=...)` /
`crear_reserva(...)` interno gana `empresa=self.empresa` / `self.empresa` como primer argumento.

Ejemplo concreto — `setUp` de la clase que hoy empieza en la línea 855 (webhook):

```python
    def setUp(self):
        Tarifa.objects.create(empresa=self.empresa, precio=Decimal('4500.00'))
        self.reserva = crear_reserva(self.empresa)
        self.reserva.precio_total = Decimal('4500.00')
        self.reserva.forma_pago = Reserva.FormaPago.COMPLETO
        self.reserva.stripe_payment_intent_id = 'pi_1'
        self.reserva.save()
```

- [ ] **Step 4: Import**

```python
from apps.testing import ApiTestCase, crear_flota
```

- [ ] **Step 5: Correr las clases que no dependen de los mocks de Stripe (el resto falla hasta la Tarea X9)**

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.LlavesDeStripeCruzadasTests apps.payments.tests.VersionDeApiTests -v 2`
Expected: PASS — estas dos no crean `Reserva`/tocan `stripe_client`, no dependen de la Tarea X9.

- [ ] **Step 6: Commit**

```bash
git add apps/payments/tests.py
git commit -m "test: retrofit parcial de payments/tests.py — helpers y setUp (1/2)"
```

---

### Task X9: `apps/payments/tests.py` — reescritura de los 52 mocks de Stripe

**Files:**
- Modify: `apps/payments/tests.py` (continúa sobre el archivo de la Tarea X8).

**Interfaces:**
- Consumes: `apps.payments.stripe_client.configurar_stripe(empresa) -> stripe.StripeClient` y
  `StripeClient` (clase del SDK `stripe==15.4.0`) — firma nueva de la retrofit de `stripe_client.py`,
  fuera de este grupo de tareas (ver fila de `apps/payments/stripe_client.py` en el File Map, Revisión 5
  B3 / Revisión 6 N-D).

- [ ] **Step 1: Patrón 1 — `PaymentIntent.create` (33 sitios)**

De:

```python
    @mock.patch('stripe.PaymentIntent.create')
    def test_cobra_lo_que_calcula_el_servidor_no_lo_que_manda_el_cliente(self, create):
        create.return_value = intent_falso()
        response = self.post(precio_total='1.00', total=1, lleva_lunch=True, amenities=['lunch'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(create.call_args.kwargs['amount'], a_centavos(Decimal('4500.00')))
        self.assertEqual(response.json()['monto_a_cobrar'], '4500.00')
```

a:

```python
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_cobra_lo_que_calcula_el_servidor_no_lo_que_manda_el_cliente(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        response = self.post(precio_total='1.00', total=1, lleva_lunch=True, amenities=['lunch'])

        self.assertEqual(response.status_code, 200)
        # payment_intents.create(params, options) -- el monto vive en params, primer
        # argumento posicional, no en kwargs como con la SDK legacy.
        self.assertEqual(
            payment_intents.create.call_args.args[0]['amount'], a_centavos(Decimal('4500.00')),
        )
        self.assertEqual(response.json()['monto_a_cobrar'], '4500.00')
```

Aplicar el mismo cambio (`@mock.patch('stripe.PaymentIntent.create')` con parámetro `create` →
`@mock.patch.object(StripeClient, 'payment_intents')` con parámetro `payment_intents`, y
`create.call_args.kwargs[...]` → `payment_intents.create.call_args.args[0][...]`) a los 33 sitios de este
patrón: líneas 219, 229, 241, 252, 260, 267, 274, 282, 297, 313, 325, 341, 354, 366, 374, 386, 402, 423,
438, 453, 460, 473, 488, 504, 519, 530, 561, 575, 584, 593, 603, 613, 622 (numeración del archivo antes
del retrofit de la Tarea X8 — reubicar por contenido del test, no por número de línea, tras aplicar X8).
Donde el test también verifica `idempotency_key` (ninguno de los 33 lo hace hoy explícito salvo los que se
listan en el Step 4 de abajo), usar `call_args.args[1]['idempotency_key']`, no `kwargs`.

- [ ] **Step 2: Patrón 2 — `PaymentIntent.retrieve` (9 sitios)**

De:

```python
    @mock.patch('stripe.PaymentIntent.retrieve')
    def test_aplica_el_pago_que_el_webhook_nunca_entrego(self, retrieve):
        retrieve.return_value = self.intent_stripe()
        self.ejecutar()
```

a:

```python
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_aplica_el_pago_que_el_webhook_nunca_entrego(self, payment_intents):
        payment_intents.retrieve.return_value = self.intent_stripe()
        self.ejecutar()
```

Aplicar a los 9 sitios de este patrón: líneas 422, 459, 472 (junto con `modify`, ver Step 3), 487, 1111,
1120, 1129, 1137, 1143.

- [ ] **Step 3: `PaymentIntent.modify` → `payment_intents.update` (1 sitio) — línea 471**

De:

```python
    @mock.patch('stripe.PaymentIntent.modify')
    @mock.patch('stripe.PaymentIntent.retrieve')
    @mock.patch('stripe.PaymentIntent.create')
    def test_...(self, create, retrieve, modify):
```

a (un solo mock cubre las tres llamadas, porque las tres cuelgan del mismo `payment_intents` del
`StripeClient` — **no** son tres parches separados):

```python
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_...(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        payment_intents.retrieve.return_value = self.intent_stripe()
        payment_intents.update.return_value = self.intent_stripe()  # antes: .modify
```

(revisar el cuerpo del test para saber qué combinación de `create`/`retrieve`/`update` necesita realmente
— este es el único sitio de los 52 donde tres decoradores colapsan en uno solo con tres atributos del
mismo mock, porque `PaymentIntent.create/retrieve/modify` eran tres funciones de módulo independientes y
`payment_intents` es un solo objeto con tres métodos.)

- [ ] **Step 4: Patrón 3 — `Refund.create` (6 sitios) + protección de `idempotency_key`**

De:

```python
    @mock.patch('stripe.Refund.create')
    def test_un_segundo_cobro_distinto_se_reembolsa(self, refund):
        self.entregar(evento_pagado(self.reserva.pk, intent_id='pi_1'))
        self.entregar(evento_pagado(self.reserva.pk, intent_id='pi_2'))

        refund.assert_called_once()
        self.assertEqual(refund.call_args.kwargs['payment_intent'], 'pi_2')
```

a:

```python
    @mock.patch.object(StripeClient, 'refunds')
    def test_un_segundo_cobro_distinto_se_reembolsa(self, refunds):
        self.entregar(evento_pagado(self.reserva.pk, intent_id='pi_1'))
        self.entregar(evento_pagado(self.reserva.pk, intent_id='pi_2'))

        refunds.create.assert_called_once()
        self.assertEqual(refunds.create.call_args.args[0]['payment_intent'], 'pi_2')
```

Aplicar a los 6 sitios: líneas 890, 899, 911, 916, 936, 960 (el de la línea 960,
`side_effect=stripe.APIConnectionError(...)`, pasa a `refunds.create.side_effect = stripe.APIConnectionError('stripe caido')`
— el `side_effect` se asigna al atributo del mock, no al decorador).

**Test nuevo — protección de doble reembolso, no existía antes porque la SDK legacy no distinguía
`params`/`options`:**

```python
    @mock.patch.object(StripeClient, 'refunds')
    def test_el_reembolso_manda_idempotency_key_en_options_no_en_params(self, refunds):
        """Regresión directa de la Revisión 6, N-D: `idempotency_key` en `params`
        en vez de `options` pierde la protección de doble reembolso — Stripe la
        ignoraría como un campo más del payload, no como la cabecera
        `Idempotency-Key`."""
        self.entregar(evento_pagado(99999))  # pago sin reserva -> se reembolsa

        refunds.create.assert_called_once()
        params, options = refunds.create.call_args.args
        self.assertNotIn('idempotency_key', params)
        self.assertIn('idempotency_key', options)
```

- [ ] **Step 5: `Webhook.construct_event` — NO cambia (3 sitios, verificar y dejar intactos)**

Líneas 863, 984, 1015 — `stripe.Webhook.construct_event` sigue siendo función de módulo (ver plan,
fila de `stripe_client.py`: "NO cambia — sigue siendo función de módulo, no cuelga del client"). Confirmar
que estos 3 `mock.patch('stripe.Webhook.construct_event', ...)` se dejan exactamente como están — no
tocarlos es parte correcta de esta tarea, no un olvido.

- [ ] **Step 6: `stripe.api_key` — línea 1171**

De:

```python
    def test_configurar_stripe_fija_llave_y_version(self):
        from apps.payments.stripe_client import configurar_stripe

        with override_settings(STRIPE_SECRET_KEY='sk_test_x', STRIPE_API_VERSION='2026-07-29.dahlia'):
            configurar_stripe()

        self.assertEqual(stripe.api_key, 'sk_test_x')
        self.assertEqual(stripe.api_version, '2026-07-29.dahlia')
```

a (clase `VersionDeApiTests` pasa a `EmpresaTestCase`, ya no `TestCase`, porque `configurar_stripe` ahora
recibe una `Empresa`):

```python
class VersionDeApiTests(EmpresaTestCase):
    def test_configurar_stripe_devuelve_un_client_con_la_llave_y_version_de_la_empresa(self):
        from apps.payments.stripe_client import configurar_stripe

        self.empresa.stripe_secret_key = 'sk_test_x'
        self.empresa.save()

        with override_settings(STRIPE_API_VERSION='2026-07-29.dahlia'):
            cliente = configurar_stripe(self.empresa)

        self.assertEqual(cliente.api_key, 'sk_test_x')
        self.assertEqual(cliente.stripe_version, '2026-07-29.dahlia')
```

- [ ] **Step 7: Import**

```python
from apps.payments.stripe_client import StripeClient
```

- [ ] **Step 8: Correr el archivo completo**

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests -v 2`
Expected: PASS, las 9 clases (incluidas las de la Tarea X8).

- [ ] **Step 9: Commit**

```bash
git add apps/payments/tests.py
git commit -m "test: reescribe los 52 mocks de stripe.* contra StripeClient (2/2)"
```

---

### Task X10: `apps/notifications/tests.py`

**Files:**
- Modify: `apps/notifications/tests.py`

**Interfaces:**
- Consumes: `apps.testing.EmpresaTestCase`, `crear_flota(empresa)` (Tarea X1).

- [ ] **Step 1: Helpers de módulo**

```python
def crear_reserva(empresa):
    return Reserva(
        empresa=empresa,
        fecha=date.today() + timedelta(days=10),
        hora=time(6, 0),
        numero_personas=2,
        nombre_cliente='Ana Ruiz',
        telefono_cliente='+5216121234567',
        correo_cliente='ana@example.com',
        moneda='MXN',
        deslinde_aceptado=True,
        deslinde_nombre='Ana Ruiz',
    )


def crear_reserva_guardada(empresa, **overrides):
    """A diferencia de `crear_reserva()`, esta si queda en la base: hace falta
    tener `pk` para poder colgarle `ReservaExtra`/`ReservaTransporte`."""
    crear_flota(empresa)
    datos = dict(
        empresa=empresa, fecha=date.today() + timedelta(days=10), hora=time(6, 0), numero_personas=2,
        nombre_cliente='Ana Ruiz', telefono_cliente='+5216121234567', correo_cliente='ana@example.com',
        canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True, deslinde_nombre='Ana Ruiz',
        moneda='MXN',
    )
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva
```

- [ ] **Step 2: Cambiar base de clase y enhebrar `self.empresa`**

Todas las clases del archivo que llaman `crear_reserva(...)`/`crear_reserva_guardada(...)` o crean
`Capitan`/`Embarcacion`/`ExtrasItem`/`PuntoEncuentro` pasan de `TestCase` a `EmpresaTestCase`; cada
llamada gana `self.empresa` como primer argumento. Ejemplo (primera clase del archivo, patrón para el
resto):

```python
class ConfirmacionAlClienteTests(EmpresaTestCase):
    def setUp(self):
        self.reserva = crear_reserva_guardada(self.empresa)

    def test_...(self):
        embarcacion = Embarcacion.objects.create(
            empresa=self.empresa, nombre='...', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3,
        )
        # resto del test sin cambios
```

- [ ] **Step 3: Import**

```python
from apps.testing import EmpresaTestCase, crear_flota
```

- [ ] **Step 4: Correr el archivo**

Run: `venv\Scripts\python.exe manage.py test apps.notifications.tests -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/notifications/tests.py
git commit -m "test: retrofit de notifications/tests.py para tenancy"
```

---

### Task X11: `apps/finance/tests.py`

**Files:**
- Modify: `apps/finance/tests.py`

**Interfaces:**
- Consumes: `apps.testing.EmpresaTestCase`, `crear_flota(empresa)`, `.crear_jefe()`, `.crear_vendedora()`
  (Tarea X1). `apps.finance.services.{resumen,balances,balances_por_dia}(..., empresa=None)` (firma
  nueva de la retrofit de `finance/services.py`, fuera de este grupo — `empresa=None` sigue siendo válido
  en los tests de `BalancesTests` si esa clase corre como operador de plataforma; ver Step 2).

- [ ] **Step 1: Helper `crear_reserva`**

```python
def crear_reserva(empresa, **overrides):
    crear_flota(empresa)
    datos = {
        'empresa': empresa,
        'fecha': date.today() + timedelta(days=10),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
        'estado': Reserva.Estado.PAGADA,
    }
    datos.update(overrides)
    reserva = Reserva(**datos)
    reserva.full_clean()
    reserva.save()
    return reserva
```

- [ ] **Step 2: `BalancesTests` — pasa `empresa=self.empresa` a los servicios**

```python
class BalancesTests(EmpresaTestCase):
    def test_el_cobro_con_tarjeta_entra_como_entrada_del_dia_en_que_se_pago(self):
        crear_reserva(self.empresa, monto_pagado=Decimal('4500.00'), pagada_en=momento(2026, 3, 5))

        del_dia = balances(date(2026, 3, 5), date(2026, 3, 5), empresa=self.empresa)['MXN']

        self.assertEqual(del_dia.tarjeta, Decimal('4500.00'))
        self.assertEqual(del_dia.neto, Decimal('4500.00'))
```

Aplicar el mismo patrón (`self.empresa` en `crear_reserva(...)` y `empresa=self.empresa` en
`balances(...)`/`balances_por_dia(...)`/`resumen(...)`) al resto de métodos de esta clase.

- [ ] **Step 3: `PanelTests` — jefe/vendedora + prueba de aislamiento nueva**

```python
class PanelTests(EmpresaTestCase):
    """El panel es la unica pantalla con la foto completa del dinero."""

    def setUp(self):
        self.url = reverse('finanzas')

    def test_los_jefes_lo_ven(self):
        self.client.force_login(self.crear_jefe())
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_la_vendedora_no_lo_ve(self):
        self.client.force_login(self.crear_vendedora(username='maria'))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_sin_sesion_manda_al_login_del_admin(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('login', respuesta['Location'])

    def test_el_menu_lateral_del_admin_lleva_a_finanzas(self):
        self.client.force_login(self.crear_jefe())
        respuesta = self.client.get('/admin/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.url)

    def test_un_mes_invalido_en_la_url_no_revienta(self):
        self.client.force_login(self.crear_jefe())
        self.assertEqual(self.client.get(self.url, {'mes': 'hola'}).status_code, 200)

    def test_el_jefe_de_una_empresa_no_ve_dinero_de_otra(self):
        """Nuevo: `panel_financiero` corta con `scope.empresa_actual(request)`, no
        con `is_superuser` (retrofit de finance/views.py, fuera de este grupo) —
        este test prueba que el filtro real aplica, no solo que la pantalla carga."""
        crear_reserva(self.empresa, monto_pagado=Decimal('4500.00'), pagada_en=timezone.now())

        otra_sede = Sede.objects.create(nombre='Otra', slug='otra-sede-panel', zona_horaria='America/Mazatlan')
        otra_empresa = Empresa.objects.create(sede=otra_sede, nombre='Otra Empresa', slug='otra-empresa-panel', activo=True)
        with scope.con_empresa(otra_empresa):
            crear_reserva(otra_empresa, monto_pagado=Decimal('9999.00'), pagada_en=timezone.now())

        self.client.force_login(self.crear_jefe())
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, '4,500.00')
        self.assertNotContains(respuesta, '9,999.00')
```

- [ ] **Step 4: Import**

```python
from apps.testing import EmpresaTestCase, crear_flota
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede
```

- [ ] **Step 5: Correr el archivo**

Run: `venv\Scripts\python.exe manage.py test apps.finance.tests -v 2`
Expected: PASS, incluido el test de aislamiento nuevo.

- [ ] **Step 6: Commit**

```bash
git add apps/finance/tests.py
git commit -m "test: retrofit de finance/tests.py + prueba de aislamiento entre empresas"
```

---

### Task X12: `config/tests_health.py`

**Files:**
- Modify: `config/tests_health.py`

**Interfaces:**
- Consumes: `apps.tenancy.models.Empresa` (para resolver el slug de la ruta pública de tarifa).

- [ ] **Step 1: `HealthzTests` — sin cambios de fondo**

`/healthz` es una ruta anónima sin `empresa_slug` (caso 3 de "Resolución de alcance" del plan) — el
middleware la deja pasar sin resolver alcance, y no toca ninguna tabla de tenancy. Las 4 pruebas que
solo pegan a `/healthz` (`test_responde_200_con_la_base_vacia`,
`test_reporta_503_si_la_base_no_contesta`, `test_el_503_no_publica_los_datos_de_la_conexion`,
`test_no_depende_de_servicios_externos`) **no cambian una sola línea**.

- [ ] **Step 2: `test_la_ruta_de_tarifa_si_falla_sin_datos` — la ruta ya no existe sin slug**

`apps/fleet/urls.py` gana el prefijo `<slug:empresa_slug>/` (ver File Map) — `/api/tarifa/` sin slug deja
de existir (404 de Django, no 503 de la vista). El test documentaba por qué esa ruta no podía ser el
health check; sigue siendo verdad, solo cambia la URL con la que se demuestra:

De:

```python
    def test_la_ruta_de_tarifa_si_falla_sin_datos(self):
        """Deja constancia de por que /api/tarifa/ no puede ser el health check.

        Si algun dia esta ruta deja de dar 503 sin tarifa, este test falla y
        obliga a releer la decision en vez de asumirla.
        """
        self.assertEqual(self.client.get('/api/tarifa/').status_code, 503)
```

a:

```python
    def test_la_ruta_de_tarifa_si_falla_sin_datos(self):
        """Deja constancia de por que /api/<empresa>/tarifa/ no puede ser el health
        check.

        Si algun dia esta ruta deja de dar 503 sin tarifa, este test falla y
        obliga a releer la decision en vez de asumirla.
        """
        sede = Sede.objects.create(nombre='Sede health', slug='sede-health', zona_horaria='America/Mazatlan')
        empresa = Empresa.objects.create(sede=sede, nombre='Empresa health', slug='empresa-health', activo=True)

        self.assertEqual(self.client.get(f'/api/{empresa.slug}/tarifa/').status_code, 503)
```

- [ ] **Step 3: Import**

```python
from apps.tenancy.models import Empresa, Sede
```

- [ ] **Step 4: Correr el archivo**

Run: `venv\Scripts\python.exe manage.py test config.tests_health -v 2`
Expected: PASS, las 5 pruebas.

- [ ] **Step 5: Commit**

```bash
git add config/tests_health.py
git commit -m "test: retrofit de config/tests_health.py — ruta de tarifa con slug de empresa"
```

---

### Task X13: Suite completa del grupo

**Files:** ninguno — solo verificación, cierre del grupo de tareas.

**Interfaces:** ninguna.

- [ ] **Step 1: Correr toda la suite de `apps` (sqlite local)**

Run: `venv\Scripts\python.exe manage.py test apps`
Expected: PASS completo (las clases `@SOLO_POSTGRES` de `tests_concurrencia.py` se saltan, esperado en
sqlite).

- [ ] **Step 2: Si hay CI/Postgres local disponible, correr también ahí**

Run (con `DJANGO_SETTINGS_MODULE=config.settings.ci` y el rol `ci_rls` ya creado por el paso de CI, ver
fila de `.github/workflows/ci.yml` en el File Map, fuera de este grupo): `venv\Scripts\python.exe manage.py test apps`
Expected: PASS completo, sin `skipped` — es la única corrida que de verdad ejerce `tests_rls.py` y los 3
tests de `tests_concurrencia.py`.

- [ ] **Step 3: Commit final del grupo (si Step 1/2 forzaron algún ajuste de última hora)**

```bash
git add -A
git commit -m "test: cierre del retrofit de la suite de tests existente para tenancy"
```

(Omitir este commit si los Steps 1-2 no requirieron ningún cambio adicional — las 12 tareas anteriores ya
dejaron todo committeado.)

---

### Payments/Finance/Stripe (P1-P8)

# Expansión multi-sede — Pieza 1 — Sección P: Payments / Finance / Stripe

> Esta sección es **parte** del plan de implementación de
> `docs/superpowers/plans/2026-08-31-expansion-multi-sede-pieza1-tenancy.md`
> (File Map aprobado tras 9 rondas de architecture-critic — ver el marcador
> `<!-- arch-critic: APPROVED -->` al final de ese archivo). Cubre exclusivamente
> las filas de `apps/finance/*`, `apps/payments/*` y
> `apps/payments/management/commands/conciliar_pagos.py`. Otras secciones cubren
> `apps/tenancy`, `apps/fleet`, `apps/bookings` y el retrofit masivo de la suite
> de tests existente (`apps/testing.py` + las 77 clases listadas en la fila
> "Suite de tests existente" del File Map, incluida `apps/payments/tests.py`).

**Orden de ejecución:** esta sección asume que ya corrieron, en este orden:
tenancy (Sede/Empresa/scope/RLS) → fleet (FK `empresa`, `Tarifa.de(empresa)`) →
bookings (FK `empresa` en `Reserva`, `evaluar_codigo_promocional(codigo, correo,
empresa)`). Las tareas P1–P8 de aquí van después, en el orden en que están
numeradas — cada una asume que las anteriores de esta misma sección ya se
aplicaron (P5 usa `configurar_stripe(empresa)` de P1; P6 usa las funciones de
P5; P8 usa P1).

**Interfaces que esta sección consume, fijadas por otras secciones — no
redefinir sus nombres/firmas aquí:**

- `apps.tenancy.models.Empresa` — campos `slug`, `activo`, `exclusiva`,
  `stripe_secret_key`, `stripe_webhook_secret`, `stripe_publishable_key`.
- `apps.tenancy.models.Sede` — campos `nombre`, `slug`, `zona_horaria`.
- `apps.tenancy.scope.con_empresa(empresa)` — context manager no reentrante,
  fija `connection.alcance_actual` y (en Postgres) `SET LOCAL
  app.current_empresa_id`.
- `apps.tenancy.scope.resolver_empresa_publica(slug)` — 404 si el slug no
  existe **o** `activo=False`.
- `apps.tenancy.scope.resolver_empresa_de_dinero(slug)` — 404 **solo** si el
  slug no existe; `activo=False` no importa (dinero ya cobrado).
- `apps.tenancy.scope.empresa_actual(request)` / `es_operador_plataforma(user)`.
- `apps.fleet.models.Tarifa.de(empresa)` — reemplaza `Tarifa.actual()`.
- `apps.fleet.models.TransportePrecio` / `CodigoPromocional` — ganan FK
  `empresa` (`CodigoPromocional.codigo` deja de ser único global).
- `apps.bookings.models.Reserva` — gana FK `empresa` (`on_delete=PROTECT`,
  `null=False`).
- `apps.bookings.models.evaluar_codigo_promocional(codigo_str, correo_cliente,
  empresa)` — gana `empresa` como tercer parámetro obligatorio.
- `apps.bookings.models.codigo_promocional_valido(...)` — **sin cambios de
  firma**, sigue validando un `CodigoPromocional` ya resuelto.

**Nota de coordinación sobre tests existentes:** las tareas P5/P6 cambian la
firma de `aplicar_pago_exitoso`, `reembolsar`, `aplicar_reembolso`,
`aplicar_disputa` y el mecanismo de Stripe (de `stripe.PaymentIntent.*` global a
`cliente.payment_intents.*` por Empresa). Las clases de test **preexistentes**
en `apps/payments/tests.py` que ejercitan ese flujo completo (`PaymentIntentTests`,
`WebhookTests`, y las ~52 `mock.patch('stripe.*')` del archivo) **quedarán en
rojo** hasta que corra la tarea de la sección "Suite de tests existente" — esa
tarea es la dueña de adaptarlas (retrofit masivo, fuera de esta sección). Las
tareas de aquí solo agregan clases de test **nuevas**, acotadas al
comportamiento que cada una introduce, y dejan explícito en cada paso qué
seguirá en rojo. La única excepción es `LlavesDeStripeCruzadasTests` (P2): esa
clase no es parte del inventario de 52 mocks de Stripe (usa `override_settings`,
no mockea `stripe.*`) y su comportamiento cambia por completo con esta sección
— P2 la reemplaza directamente.

**Comando de test** (Windows, desde `backend/`):
`venv\Scripts\python.exe manage.py test apps.payments apps.finance`

---

### Task P1: `apps/payments/stripe_client.py` — cliente por Empresa, sin estado global

**Files:**
- Modify: `backend/apps/payments/stripe_client.py`
- Test: `backend/apps/payments/tests.py` (agregar al final)

**Interfaces:**
- Consumes: `apps.tenancy.models.Empresa.stripe_secret_key` (str),
  `settings.STRIPE_API_VERSION` (ya existe en `config/settings/base.py`).
- Produces: `configurar_stripe(empresa) -> stripe.StripeClient` — reemplaza la
  firma vieja de cero argumentos. Consumido por P5, P6, P8.

- [ ] **Step 1: Escribe el test que falla**

Agrega al final de `backend/apps/payments/tests.py`:

```python
class ConfigurarStripeTests(TestCase):
    """configurar_stripe(empresa) devuelve un cliente explicito, sin tocar
    stripe.api_key/api_version como estado global del proceso."""

    def setUp(self):
        sede = Sede.objects.create(
            nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan',
        )
        self.empresa = Empresa.objects.create(
            sede=sede, nombre='Sal y Sol', slug='sal-y-sol',
            stripe_secret_key='sk_test_abc', stripe_webhook_secret='whsec_abc',
            stripe_publishable_key='pk_test_abc',
        )

    @mock.patch('apps.payments.stripe_client.stripe.StripeClient')
    def test_usa_las_llaves_de_la_empresa(self, mock_cliente_cls):
        from django.conf import settings as django_settings

        resultado = configurar_stripe(self.empresa)

        mock_cliente_cls.assert_called_once_with(
            api_key='sk_test_abc', stripe_version=django_settings.STRIPE_API_VERSION,
        )
        self.assertIs(resultado, mock_cliente_cls.return_value)

    def test_no_muta_stripe_api_key_global(self):
        api_key_antes = getattr(stripe, 'api_key', None)
        configurar_stripe(self.empresa)
        self.assertEqual(getattr(stripe, 'api_key', None), api_key_antes)
```

Agrega los imports que falten al encabezado de `apps/payments/tests.py`:
`from apps.tenancy.models import Empresa, Sede` y
`from .stripe_client import configurar_stripe` (si no está ya).

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.ConfigurarStripeTests -v 2`
Expected: FAIL — `configurar_stripe() takes 0 positional arguments but 1 was given`.

- [ ] **Step 2: Implementación mínima**

Reemplaza el contenido completo de `backend/apps/payments/stripe_client.py`:

```python
"""Configuracion del cliente de Stripe, por Empresa.

Cada Empresa tiene sus propias llaves de Stripe (ver apps.tenancy.models.Empresa)
— con mas de una Empresa, mutar `stripe.api_key` como variable global de proceso
es una condicion de carrera esperando a que dos peticiones de Empresas distintas
se sirvan al mismo tiempo. `configurar_stripe(empresa)` devuelve un cliente
explicito en su lugar; cada call site lo recibe y lo usa, nunca importa `stripe`
para llamar directo a `stripe.PaymentIntent`/`stripe.Refund` con el estado global.
"""
import stripe
from django.conf import settings


def configurar_stripe(empresa):
    """Cliente de Stripe listo para llamar la API con las llaves de `empresa`."""
    return stripe.StripeClient(
        api_key=empresa.stripe_secret_key,
        stripe_version=settings.STRIPE_API_VERSION,
    )
```

- [ ] **Step 3: Corre el test, verifica que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.ConfigurarStripeTests -v 2`
Expected: PASS (2 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/apps/payments/stripe_client.py backend/apps/payments/tests.py
git commit -m "feat(payments): configurar_stripe por Empresa, sin estado global"
```

---

### Task P2: `apps/payments/checks.py` — llaves cruzadas, por Empresa

**Files:**
- Modify: `backend/apps/payments/checks.py`
- Modify: `backend/apps/payments/tests.py:29-84` (reemplaza `LLAVES` +
  `LlavesDeStripeCruzadasTests` — esa clase prueba comportamiento que este
  task elimina; no es parte del inventario de 52 mocks de Stripe, así que se
  reemplaza aquí, no en el retrofit de la suite existente)

**Interfaces:**
- Consumes: `apps.tenancy.models.Empresa` (todas las filas, activas o no —
  este check nunca decide con `activo`).
- Produces: sin cambio de superficie pública — sigue siendo
  `revisar_llaves_de_stripe(app_configs, **kwargs)` registrado con
  `@register()`, solo cambia de dónde lee las llaves.

- [ ] **Step 1: Escribe el test que falla**

En `backend/apps/payments/tests.py`, reemplaza el bloque completo (línea 29 a
84 del archivo actual: la constante `LLAVES` y toda la clase
`LlavesDeStripeCruzadasTests`) por:

```python
class RevisarLlavesDeStripeTests(TestCase):
    """Check de arranque que detecta una llave de Stripe puesta en el campo
    equivocado, ahora por fila de Empresa en vez de por variable de entorno.

    Nace de un caso real en produccion: en Render quedo el signing secret del
    webhook (`whsec_...`) dentro de `STRIPE_SECRET_KEY`. Con una Empresa por
    marca, cada una trae sus propias llaves en su propia fila — el check
    revisa cada una por separado y el mensaje identifica cual.
    """

    def setUp(self):
        self.sede = Sede.objects.create(
            nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan',
        )

    def _crear_empresa(self, slug, secreta='sk_test_ok', webhook='whsec_ok'):
        return Empresa.objects.create(
            sede=self.sede, nombre=slug, slug=slug,
            stripe_secret_key=secreta, stripe_webhook_secret=webhook,
            stripe_publishable_key='pk_test_ok',
        )

    def test_llaves_correctas_no_reportan_nada(self):
        self._crear_empresa('sal-y-sol')
        self.assertEqual(revisar_llaves_de_stripe(None), [])

    def test_llaves_vacias_no_reportan_nada(self):
        # Vacio significa "Stripe apagado para esta Empresa", comportamiento
        # documentado (crear-pago responde 503), no una llave cruzada.
        self._crear_empresa('sin-stripe', secreta='', webhook='')
        self.assertEqual(revisar_llaves_de_stripe(None), [])

    def test_el_signing_secret_dentro_de_la_llave_secreta(self):
        self._crear_empresa('sal-y-sol', secreta='whsec_falsa', webhook='whsec_ok')
        errores = revisar_llaves_de_stripe(None)
        self.assertEqual([e.id for e in errores], ['payments.E001'])
        self.assertIn('sal-y-sol', errores[0].msg)

    def test_la_llave_secreta_dentro_del_signing_secret(self):
        self._crear_empresa('sal-y-sol', secreta='sk_test_ok', webhook='sk_test_falsa')
        errores = revisar_llaves_de_stripe(None)
        self.assertEqual([e.id for e in errores], ['payments.E002'])

    def test_dos_empresas_cada_una_reporta_la_suya(self):
        self._crear_empresa('cruzada', secreta='whsec_falsa')
        self._crear_empresa('correcta')
        errores = revisar_llaves_de_stripe(None)
        self.assertEqual(len(errores), 1)
        self.assertIn('cruzada', errores[0].msg)

    def test_el_mensaje_no_incluye_el_valor_de_la_llave(self):
        self._crear_empresa('sal-y-sol', secreta='whsec_secretisimo')
        texto = ' '.join(f'{e.msg} {e.hint}' for e in revisar_llaves_de_stripe(None))
        self.assertNotIn('secretisimo', texto)

    def test_tabla_inexistente_no_revienta(self):
        # Ventana entre que corre collectstatic/migrate y que tenancy.0001
        # crea la tabla — el check debe callar, no tronar el deploy.
        with mock.patch(
            'apps.payments.checks.Empresa.objects.all',
            side_effect=DatabaseError('relation "tenancy_empresa" does not exist'),
        ):
            self.assertEqual(revisar_llaves_de_stripe(None), [])
```

Agrega a los imports de `apps/payments/tests.py`:
`from django.db.utils import DatabaseError`.

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.RevisarLlavesDeStripeTests -v 2`
Expected: FAIL — el check sigue leyendo `settings.STRIPE_SECRET_KEY`, así que
`test_el_signing_secret_dentro_de_la_llave_secreta` no encuentra error alguno
(las Empresas creadas en el test no las toca el check viejo).

- [ ] **Step 2: Implementación mínima**

Reemplaza el contenido completo de `backend/apps/payments/checks.py`:

```python
"""Check de arranque para las llaves de Stripe, una fila de Empresa a la vez.

Con una Empresa por marca (ver apps.tenancy), cada una trae sus propias llaves
en `Empresa.stripe_secret_key`/`stripe_webhook_secret`. Este check es la red de
seguridad de ARRANQUE: detecta una llave cruzada que ya haya quedado guardada
(migracion de datos, fixture, el backfill de `tenancy.0002`) sin hablar con la
red. La validacion que de verdad importa corre en `Empresa.clean()`
(apps/tenancy/models.py) — un jefe que teclea una llave cruzada en el admin la
ve rechazada ahi mismo, en caliente; este check no cubre eso, solo lo que ya
esta en la base al arrancar.

Envuelto en try/except DatabaseError: en el deploy que instala esta pieza, el
check corre durante `collectstatic`/`migrate` antes de que la tabla
`tenancy_empresa` exista.
"""
from django.core.checks import Error, register
from django.db.utils import DatabaseError

# (atributo de Empresa, prefijo que le pone Stripe, codigo, como se llama en el dashboard).
LLAVES_DE_STRIPE = (
    (
        'stripe_secret_key',
        'sk_',
        'payments.E001',
        'la llave secreta (Developers -> API keys)',
    ),
    (
        'stripe_webhook_secret',
        'whsec_',
        'payments.E002',
        'el signing secret del endpoint (Developers -> Webhooks)',
    ),
)


@register()
def revisar_llaves_de_stripe(app_configs, **kwargs):
    """Reporta, por Empresa, las llaves de Stripe que no tienen el prefijo de
    su tipo. El mensaje **nunca incluye el valor** de la llave, solo el slug
    de la Empresa y el nombre del campo.
    """
    from apps.tenancy.models import Empresa

    try:
        empresas = list(Empresa.objects.all())
    except DatabaseError:
        return []

    errores = []
    for empresa in empresas:
        for atributo, prefijo, codigo, de_donde_sale in LLAVES_DE_STRIPE:
            valor = getattr(empresa, atributo, '')
            if valor and not valor.startswith(prefijo):
                errores.append(Error(
                    f'Empresa "{empresa.slug}": {atributo} no empieza con "{prefijo}", '
                    f'asi que no es la llave que este campo espera.',
                    hint=(
                        f'Parece una llave de Stripe capturada en el campo equivocado. '
                        f'En {atributo} va {de_donde_sale}. Corrigela en el admin '
                        f'(Empresas -> {empresa.slug}). Ver docs/deploy/GO-LIVE.md, Fase 5.'
                    ),
                    id=codigo,
                ))

    return errores
```

- [ ] **Step 3: Corre el test, verifica que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.RevisarLlavesDeStripeTests -v 2`
Expected: PASS (7 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/apps/payments/checks.py backend/apps/payments/tests.py
git commit -m "fix(payments): check de llaves de Stripe cruzadas, por Empresa"
```

---

### Task P3: `apps/finance/services.py` — filtro `empresa` opcional

**Files:**
- Modify: `backend/apps/finance/services.py`
- Test: `backend/apps/finance/tests.py` (agregar al final)

**Interfaces:**
- Consumes: `apps.bookings.models.Reserva.empresa` (FK, de la sección bookings).
- Produces: `balances(desde=None, hasta=None, empresa=None)`,
  `balances_por_dia(desde, hasta, empresa=None)`, `resumen(hoy=None,
  empresa=None)` — `empresa=None` sigue significando "todas" (comportamiento
  de hoy, sin cambio para quien no pasa el argumento). Consumido por P4.

- [ ] **Step 1: Escribe el test que falla**

Agrega al final de `backend/apps/finance/tests.py`:

```python
class BalancesFiltradosPorEmpresaTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(
            nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan',
        )
        self.empresa_a = Empresa.objects.create(
            sede=self.sede, nombre='A', slug='empresa-a',
            stripe_secret_key='sk_a', stripe_webhook_secret='whsec_a',
            stripe_publishable_key='pk_a',
        )
        self.empresa_b = Empresa.objects.create(
            sede=self.sede, nombre='B', slug='empresa-b',
            stripe_secret_key='sk_b', stripe_webhook_secret='whsec_b',
            stripe_publishable_key='pk_b',
        )
        crear_flota()
        self.hoy = date.today()
        with scope.con_empresa(self.empresa_a):
            self._crear_reserva_pagada(self.empresa_a, Decimal('1000.00'))
        with scope.con_empresa(self.empresa_b):
            self._crear_reserva_pagada(self.empresa_b, Decimal('2000.00'))

    def _crear_reserva_pagada(self, empresa, monto):
        reserva = Reserva(
            empresa=empresa, fecha=self.hoy + timedelta(days=10), hora=time(6, 0),
            numero_personas=2, nombre_cliente='Cliente', telefono_cliente='+5216121234567',
            correo_cliente='cliente@example.com', canal_origen=Reserva.CanalOrigen.WEB,
            deslinde_aceptado=True, deslinde_nombre='Cliente', checkout_id=uuid.uuid4(),
            moneda='MXN', estado=Reserva.Estado.PAGADA,
            monto_pagado=monto, pagada_en=timezone.now(),
        )
        reserva.full_clean()
        reserva.save()
        return reserva

    def test_sin_empresa_suma_todas(self):
        total = balances()['MXN'].tarjeta
        self.assertEqual(total, Decimal('3000.00'))

    def test_con_empresa_solo_esa(self):
        total = balances(empresa=self.empresa_a)['MXN'].tarjeta
        self.assertEqual(total, Decimal('1000.00'))

    def test_resumen_respeta_el_filtro(self):
        acumulado = resumen(self.hoy, empresa=self.empresa_b)['acumulado']['MXN'].tarjeta
        self.assertEqual(acumulado, Decimal('2000.00'))
```

Agrega a `apps/finance/tests.py` los imports que falten:
`import uuid`, `from datetime import time, timedelta`, `from decimal import Decimal`,
`from django.utils import timezone`, `from apps.bookings.models import Reserva`,
`from apps.tenancy import scope`, `from apps.tenancy.models import Empresa, Sede`,
`from apps.testing import crear_flota`, `from .services import balances, resumen`
(los que no estén ya).

Run: `venv\Scripts\python.exe manage.py test apps.finance.tests.BalancesFiltradosPorEmpresaTests -v 2`
Expected: FAIL — `balances() got an unexpected keyword argument 'empresa'`.

- [ ] **Step 2: Implementación mínima**

En `backend/apps/finance/services.py`, agrega tras `MOVIMIENTOS` (línea 39) el
helper de queryset base:

```python
def _reservas(empresa):
    return Reserva.objects.filter(empresa=empresa) if empresa is not None else Reserva.objects.all()
```

Reemplaza `def balances(desde=None, hasta=None):` (línea 100) y su cuerpo por:

```python
def balances(desde=None, hasta=None, empresa=None):
    """Balance por moneda del periodo. Sin fechas, todo el historico. Sin
    `empresa`, todas las Empresas juntas (uso: operador de plataforma).

    Devuelve solo las monedas que tuvieron movimiento; un negocio que nunca
    cobro en dolares no tiene por que ver una columna de dolares vacia.
    """
    resultado = {}
    for atributo, campo_monto, campo_fecha in MOVIMIENTOS:
        for fila in _sumar(_reservas(empresa), campo_monto, campo_fecha, desde, hasta):
            balance = resultado.setdefault(fila['moneda'], Balance(moneda=fila['moneda']))
            setattr(balance, atributo, fila['total'] or CERO)
    return dict(sorted(resultado.items()))
```

Reemplaza `def balances_por_dia(desde, hasta):` (línea 114) y su cuerpo por:

```python
def balances_por_dia(desde, hasta, empresa=None):
    """Historico: un balance por dia (y por moneda) del rango pedido.

    Los dias sin un solo movimiento no aparecen — en temporada baja la tabla
    seria mayormente ceros.
    """
    resultado = {}
    for atributo, campo_monto, campo_fecha in MOVIMIENTOS:
        filas = _sumar(
            _reservas(empresa), campo_monto, campo_fecha, desde, hasta, agrupar_por_dia=True
        )
        for fila in filas:
            del_dia = resultado.setdefault(fila['dia'], {})
            balance = del_dia.setdefault(fila['moneda'], Balance(moneda=fila['moneda']))
            setattr(balance, atributo, fila['total'] or CERO)

    return [
        (dia, dict(sorted(por_moneda.items())))
        for dia, por_moneda in sorted(resultado.items(), reverse=True)
    ]
```

Reemplaza `def resumen(hoy=None):` (línea 138) y su cuerpo por:

```python
def resumen(hoy=None, empresa=None):
    """Todo lo que pinta el panel, en una sola llamada."""
    hoy = hoy or date.today()
    inicio_mes = hoy.replace(day=1)
    inicio_anio = hoy.replace(month=1, day=1)

    return {
        'dia': balances(hoy, hoy, empresa=empresa),
        'mes': balances(inicio_mes, hoy, empresa=empresa),
        'anio': balances(inicio_anio, hoy, empresa=empresa),
        'acumulado': balances(empresa=empresa),
    }
```

- [ ] **Step 3: Corre el test, verifica que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.finance.tests.BalancesFiltradosPorEmpresaTests -v 2`
Expected: PASS (3 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/apps/finance/services.py backend/apps/finance/tests.py
git commit -m "feat(finance): balances/resumen aceptan filtro empresa opcional"
```

---

### Task P4: `apps/finance/views.py` — permiso por membresía/operador, no `is_superuser`

**Files:**
- Modify: `backend/apps/finance/views.py`
- Test: `backend/apps/finance/tests.py` (agregar al final)

**Interfaces:**
- Consumes: `apps.tenancy.scope.es_operador_plataforma(user)`,
  `apps.tenancy.scope.empresa_actual(request)`; `balances`/`balances_por_dia`/
  `resumen` con `empresa=` de P3.
- Produces: sin cambio de superficie pública — sigue siendo `panel_financiero(request)`.

- [ ] **Step 1: Escribe el test que falla**

Agrega al final de `backend/apps/finance/tests.py`:

```python
class PanelFinancieroPermisoTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='jefe', password='x', is_staff=True)

    @mock.patch('apps.finance.views.scope.empresa_actual')
    @mock.patch('apps.finance.views.scope.es_operador_plataforma')
    def test_sin_membresia_ni_operador_403(self, mock_operador, mock_empresa_actual):
        mock_operador.return_value = False
        mock_empresa_actual.return_value = None
        request = self.factory.get('/admin/finanzas/')
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            panel_financiero(request)

    @mock.patch('apps.finance.views.scope.empresa_actual')
    @mock.patch('apps.finance.views.scope.es_operador_plataforma')
    @mock.patch('apps.finance.views.resumen')
    @mock.patch('apps.finance.views.balances')
    @mock.patch('apps.finance.views.balances_por_dia')
    def test_jefe_ve_solo_su_empresa(
        self, mock_balances_por_dia, mock_balances, mock_resumen,
        mock_operador, mock_empresa_actual,
    ):
        mock_operador.return_value = False
        empresa = mock.Mock()
        mock_empresa_actual.return_value = empresa
        mock_resumen.return_value = {'dia': {}, 'mes': {}, 'anio': {}, 'acumulado': {}}
        mock_balances.return_value = {}
        mock_balances_por_dia.return_value = []

        request = self.factory.get('/admin/finanzas/')
        request.user = self.user
        panel_financiero(request)

        self.assertEqual(mock_resumen.call_args.kwargs.get('empresa'), empresa)
        self.assertEqual(mock_balances.call_args.kwargs.get('empresa'), empresa)
        self.assertEqual(mock_balances_por_dia.call_args.kwargs.get('empresa'), empresa)

    @mock.patch('apps.finance.views.scope.empresa_actual')
    @mock.patch('apps.finance.views.scope.es_operador_plataforma')
    @mock.patch('apps.finance.views.resumen')
    @mock.patch('apps.finance.views.balances')
    @mock.patch('apps.finance.views.balances_por_dia')
    def test_operador_de_plataforma_ve_todas(
        self, mock_balances_por_dia, mock_balances, mock_resumen,
        mock_operador, mock_empresa_actual,
    ):
        mock_operador.return_value = True
        mock_empresa_actual.return_value = None
        mock_resumen.return_value = {'dia': {}, 'mes': {}, 'anio': {}, 'acumulado': {}}
        mock_balances.return_value = {}
        mock_balances_por_dia.return_value = []

        request = self.factory.get('/admin/finanzas/')
        request.user = self.user
        panel_financiero(request)

        self.assertIsNone(mock_resumen.call_args.kwargs.get('empresa'))
```

Agrega a los imports: `from unittest import mock`, `from django.contrib.auth import
get_user_model`, `from django.test import RequestFactory`, `from
django.core.exceptions import PermissionDenied`, `from .views import
panel_financiero`, y `User = get_user_model()` a nivel de módulo si no existe ya.

Run: `venv\Scripts\python.exe manage.py test apps.finance.tests.PanelFinancieroPermisoTests -v 2`
Expected: FAIL — `test_sin_membresia_ni_operador_403` no lanza `PermissionDenied`
porque hoy la vista corta con `is_superuser` (el usuario del test no lo es, así
que sí debería fallar, pero por la razón vieja) y los otros dos tests fallan
porque `resumen`/`balances`/`balances_por_dia` se siguen llamando sin
`empresa=`.

- [ ] **Step 2: Implementación mínima**

En `backend/apps/finance/views.py`, agrega el import (junto a los existentes,
tras `from .services import ...`):

```python
from apps.tenancy import scope
```

Reemplaza el cuerpo de `panel_financiero` (líneas 136-176) por:

```python
def panel_financiero(request):
    """Entradas, salidas y balance del dia, del mes y del año.

    El operador de plataforma ve todas las Empresas juntas; un jefe (o
    vendedora con membresia) ve solo la suya. Ya no corta con `is_superuser`
    — los jefes dejaron de serlo (ver apps.tenancy), el corte real es
    membresia-o-operador.
    """
    operador = scope.es_operador_plataforma(request.user)
    empresa = None if operador else scope.empresa_actual(request)
    if not operador and empresa is None:
        raise PermissionDenied

    hoy = date.today()
    periodo = request.GET.get('periodo', PERIODO_DEFAULT)
    if periodo not in dict(PERIODOS):
        periodo = PERIODO_DEFAULT
    desde, hasta = rango_del_periodo(periodo, hoy)

    mes = _mes_pedido(request, hoy)
    ultimo_dia = mes.replace(day=monthrange(mes.year, mes.month)[1])
    siguiente = _mes_vecino(mes, 1)

    return render(request, 'finance/panel.html', {
        **admin.site.each_context(request),
        'title': 'Finanzas',
        'hoy': hoy,
        **resumen(hoy, empresa=empresa),
        'periodos': PERIODOS,
        'periodo': periodo,
        'periodo_etiqueta': dict(PERIODOS)[periodo],
        'periodo_desde': desde,
        'periodo_hasta': hasta,
        'saldo_periodo': balances(desde, hasta, empresa=empresa),
        'grafica': _grafica_de_entradas(desde, hasta, empresa=empresa),
        'mes_visto': mes,
        'mes_anterior': _mes_vecino(mes, -1),
        'mes_siguiente': siguiente if siguiente <= hoy.replace(day=1) else None,
        'dias': balances_por_dia(mes, ultimo_dia, empresa=empresa),
    })
```

`_grafica_de_entradas` (línea 57) gana `empresa=None` y lo reenvía a
`balances_por_dia` — reemplaza su firma y la llamada interna:

```python
def _grafica_de_entradas(desde, hasta, empresa=None):
    entradas_por_dia = {
        dia: {moneda: saldo.entradas for moneda, saldo in por_moneda.items()}
        for dia, por_moneda in balances_por_dia(desde, hasta, empresa=empresa)
    }
```

(el resto del cuerpo de `_grafica_de_entradas` no cambia).

- [ ] **Step 3: Corre el test, verifica que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.finance.tests.PanelFinancieroPermisoTests -v 2`
Expected: PASS (3 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/apps/finance/views.py backend/apps/finance/tests.py
git commit -m "fix(finance): panel_financiero corta con membresia/operador, no is_superuser"
```

---

### Task P5: `apps/payments/services.py` — alcance por Empresa + fix N1 (`on_commit`) + StripeClient

**Files:**
- Modify: `backend/apps/payments/services.py`
- Test: `backend/apps/payments/tests.py` (agregar al final)

**Interfaces:**
- Consumes: `apps.tenancy.scope.con_empresa(empresa)`,
  `apps.tenancy.models.Empresa`, `configurar_stripe(empresa)` (P1).
- Produces: `aplicar_pago_exitoso(intent, empresa)`, `reembolsar(intent, motivo,
  empresa)`, `aplicar_reembolso(charge, empresa)`, `aplicar_disputa(charge,
  abierta, empresa)`, `_reserva_del_cargo(objeto, empresa)` — las cinco ganan
  `empresa` como parámetro obligatorio. Consumido por P6 (views) y P8
  (`conciliar_pagos`).

**Nota de alcance:** este task NO retrofitea las clases de test preexistentes
que llaman `aplicar_pago_exitoso(intent)` con un solo argumento (`PaymentIntentTests`
y afines) — eso es de la tarea de retrofit de la suite existente. Solo agrega
tests nuevos para el comportamiento que introduce aquí.

- [ ] **Step 1: Escribe el test que falla**

Agrega al final de `backend/apps/payments/tests.py`:

```python
class NotificarReservaPagadaOnCommitTests(TransactionTestCase):
    """TransactionTestCase, no TestCase: transaction.on_commit solo dispara
    con un commit real — TestCase envuelve cada test en una transaccion que
    nunca comitea, y el callback nunca correria.

    Prueba directa del bug N1 (Revision 4): SET LOCAL muere al COMMIT, asi que
    el callback de on_commit debe reabrir su propio con_empresa — si no lo
    hace, este test lo detecta viendo connection.alcance_actual en None (o en
    la Empresa equivocada) dentro del callback.
    """

    def setUp(self):
        self.sede = Sede.objects.create(
            nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan',
        )
        self.empresa = Empresa.objects.create(
            sede=self.sede, nombre='Sal y Sol', slug='sal-y-sol',
            stripe_secret_key='sk_test_x', stripe_webhook_secret='whsec_x',
            stripe_publishable_key='pk_x',
        )
        crear_flota()

    def _crear_reserva(self):
        reserva = Reserva(
            empresa=self.empresa, fecha=date.today() + timedelta(days=10),
            hora=time(6, 0), numero_personas=2, nombre_cliente='Ana Ruiz',
            telefono_cliente='+5216121234567', correo_cliente='ana@example.com',
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
            deslinde_nombre='Ana Ruiz', checkout_id=uuid.uuid4(), moneda='MXN',
        )
        with scope.con_empresa(self.empresa):
            reserva.full_clean()
            reserva.save()
        return reserva

    @mock.patch('apps.payments.services.notificar_reserva_pagada')
    def test_el_callback_ve_el_alcance_correcto_tras_el_commit(self, mock_notificar):
        reserva = self._crear_reserva()
        intent = {
            'id': 'pi_1', 'amount_received': 157500, 'currency': 'mxn',
            'metadata': {'reserva_id': str(reserva.pk)},
            'created': int(timezone.now().timestamp()),
        }

        capturado = {}

        def _espia(reserva_arg):
            capturado['alcance'] = connection.alcance_actual
            capturado['reserva_id'] = reserva_arg.pk

        mock_notificar.side_effect = _espia

        with scope.con_empresa(self.empresa):
            resultado = aplicar_pago_exitoso(intent, self.empresa)

        self.assertEqual(resultado, APLICADO)
        mock_notificar.assert_called_once()
        self.assertEqual(capturado['alcance'], self.empresa.pk)
        self.assertEqual(capturado['reserva_id'], reserva.pk)


class ReembolsarTests(TestCase):
    def setUp(self):
        sede = Sede.objects.create(
            nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan',
        )
        self.empresa = Empresa.objects.create(
            sede=sede, nombre='Sal y Sol', slug='sal-y-sol',
            stripe_secret_key='sk_test_x', stripe_webhook_secret='whsec_x',
            stripe_publishable_key='pk_x',
        )

    @mock.patch('apps.payments.services.configurar_stripe')
    def test_idempotency_key_va_en_options_no_en_params(self, mock_configurar):
        cliente = mock.Mock()
        mock_configurar.return_value = cliente

        resultado = reembolsar({'id': 'pi_1'}, 'prueba', self.empresa)

        self.assertTrue(resultado)
        mock_configurar.assert_called_once_with(self.empresa)
        params, options = cliente.refunds.create.call_args.args
        self.assertEqual(params, {'payment_intent': 'pi_1'})
        self.assertNotIn('idempotency_key', params)
        self.assertEqual(options, {'idempotency_key': 'refund-pi_1'})

    @mock.patch('apps.payments.services.configurar_stripe')
    def test_stripe_error_devuelve_false(self, mock_configurar):
        cliente = mock.Mock()
        cliente.refunds.create.side_effect = stripe.StripeError('boom')
        mock_configurar.return_value = cliente
        self.assertFalse(reembolsar({'id': 'pi_1'}, 'prueba', self.empresa))


class ReservaDelCargoAisladaPorEmpresaTests(TestCase):
    def setUp(self):
        sede = Sede.objects.create(
            nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan',
        )
        self.empresa_a = Empresa.objects.create(
            sede=sede, nombre='A', slug='empresa-a',
            stripe_secret_key='sk_a', stripe_webhook_secret='whsec_a',
            stripe_publishable_key='pk_a',
        )
        self.empresa_b = Empresa.objects.create(
            sede=sede, nombre='B', slug='empresa-b',
            stripe_secret_key='sk_b', stripe_webhook_secret='whsec_b',
            stripe_publishable_key='pk_b',
        )
        crear_flota()
        with scope.con_empresa(self.empresa_a):
            self.reserva_a = Reserva(
                empresa=self.empresa_a, fecha=date.today() + timedelta(days=10),
                hora=time(6, 0), numero_personas=2, nombre_cliente='Ana',
                telefono_cliente='+5216121234567', correo_cliente='ana@example.com',
                canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
                deslinde_nombre='Ana', checkout_id=uuid.uuid4(), moneda='MXN',
                stripe_payment_intent_id='pi_compartido',
            )
            self.reserva_a.full_clean()
            self.reserva_a.save()

    def test_no_encuentra_la_reserva_de_otra_empresa(self):
        self.assertIsNone(
            _reserva_del_cargo({'payment_intent': 'pi_compartido'}, self.empresa_b)
        )

    def test_encuentra_la_reserva_de_su_propia_empresa(self):
        encontrada = _reserva_del_cargo({'payment_intent': 'pi_compartido'}, self.empresa_a)
        self.assertEqual(encontrada.pk, self.reserva_a.pk)
```

Agrega a los imports de `apps/payments/tests.py`: `import uuid`, `from
django.db import connection`, `from django.test import TransactionTestCase`
(junto al `TestCase` ya importado), `from django.utils import timezone`, `from
apps.tenancy import scope`, `from apps.tenancy.models import Empresa, Sede`,
`from .services import (APLICADO, _reserva_del_cargo, aplicar_pago_exitoso,
reembolsar)` (los que falten).

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.NotificarReservaPagadaOnCommitTests apps.payments.tests.ReembolsarTests apps.payments.tests.ReservaDelCargoAisladaPorEmpresaTests -v 2`
Expected: FAIL — `aplicar_pago_exitoso() takes 1 positional argument but 2
were given`, `reembolsar() takes 2 positional arguments but 3 were given`,
`_reserva_del_cargo() takes 1 positional argument but 2 were given`.

- [ ] **Step 2: Implementación mínima**

Reemplaza el contenido completo de `backend/apps/payments/services.py`:

```python
"""Aplicacion de un pago exitoso a su reserva, por Empresa.

Vive aparte de las vistas porque tiene dos entradas: el webhook de Stripe (la
normal) y `manage.py conciliar_pagos` (la red de seguridad, para cuando una
entrega del webhook se pierde). Las dos deben decidir exactamente lo mismo, asi
que la logica no se duplica. `empresa` es obligatorio en toda funcion publica
de aqui: nunca se infiere de metadatos del PaymentIntent, siempre la resuelve
quien llama (el webhook, por el slug de la URL; conciliar_pagos, iterando).
"""
import logging
from datetime import UTC, datetime

import stripe
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.notifications.services import notificar_reserva_pagada
from apps.tenancy import scope
from apps.tenancy.models import Empresa

from .pricing import a_centavos, de_centavos, monto_inicial
from .stripe_client import configurar_stripe

logger = logging.getLogger(__name__)

# Resultados posibles, para que quien llame pueda reportar que paso.
APLICADO = 'aplicado'
YA_APLICADO = 'ya_aplicado'
DUPLICADO_REEMBOLSADO = 'duplicado_reembolsado'
SIN_CUPO_REEMBOLSADO = 'sin_cupo_reembolsado'
CODIGO_INVALIDO_REEMBOLSADO = 'codigo_invalido_reembolsado'
SIN_RESERVA_REEMBOLSADO = 'sin_reserva_reembolsado'
FALLO_REEMBOLSO = 'fallo_reembolso'


def _reserva_id_de(intent):
    """El `metadata` llega como dict cuando viene del webhook y como StripeObject
    cuando viene de `payment_intents.retrieve`, y ese ultimo no tiene `.get`."""
    try:
        return intent['metadata']['reserva_id']
    except (KeyError, TypeError):
        return None


def _momento_del_pago(intent):
    """Cuando cobro Stripe, no cuando nos enteramos.

    Importa para el panel de finanzas: `conciliar_pagos` puede aplicar horas o
    dias despues un pago cuyo webhook se perdio, y ese dinero tiene que caer en
    el dia en que entro o el balance de ese dia nunca cuadra. Si el intent no
    trae `created` (eventos viejos, pruebas), se usa la hora actual.
    """
    try:
        return datetime.fromtimestamp(intent['created'], UTC)
    except (KeyError, TypeError, ValueError, OSError):
        return timezone.now()


@transaction.atomic
def aplicar_pago_exitoso(intent, empresa):
    """Marca la reserva como pagada, o devuelve el dinero si ya no procede.

    `intent` es el PaymentIntent de Stripe (el del evento o el que se recupera
    al conciliar). `empresa` es la Empresa duena del webhook/comando que
    llama — nunca se infiere de metadatos del intent. Devuelve una de las
    constantes de arriba.
    """
    # select_for_update serializa dos entregas simultaneas del mismo evento
    # (Stripe reintenta y puede solapar): sin el, las dos verian la reserva en
    # pendiente_pago y las dos la marcarian pagada. empresa=empresa: sin
    # RLS (sqlite, tests) nada mas aisla el pk de otra Empresa.
    reserva = (
        Reserva.objects.select_for_update()
        .filter(pk=_reserva_id_de(intent), empresa=empresa)
        .first()
    )

    if reserva is None:
        logger.error('Pago %s sin reserva asociada, se reembolsa', intent['id'])
        return (
            SIN_RESERVA_REEMBOLSADO
            if reembolsar(intent, 'pago sin reserva', empresa)
            else FALLO_REEMBOLSO
        )

    if reserva.estado != Reserva.Estado.PENDIENTE_PAGO:
        return _resolver_cobro_repetido(reserva, intent, empresa)

    _verificar_monto(reserva, intent)

    reserva.monto_pagado = de_centavos(intent['amount_received'])
    reserva.pagada_en = _momento_del_pago(intent)
    reserva.stripe_payment_intent_id = intent['id']
    reserva.estado = Reserva.Estado.PAGADA
    try:
        reserva.full_clean()
        reserva.save()
    except DjangoValidationError as exc:
        # `codigo_promocional` es la unica clave que Reserva.clean() usa para
        # este rechazo (ver validar_codigo_promocional_en_pago) — cualquier
        # otra cosa (cupo, deslinde, etc.) cae en el motivo generico de abajo.
        if 'codigo_promocional' in getattr(exc, 'error_dict', {}):
            return _cancelar_codigo_promocional_invalido(reserva, intent, empresa)
        return _cancelar_sin_cupo(reserva, intent, empresa)

    # Revision 4 (N1): SET LOCAL muere al COMMIT — un callback de on_commit
    # corre FUERA del `with scope.con_empresa(...)` que encolo esta
    # transaccion. Bajo RLS eso es cero filas, no un error: el bug mas
    # peligroso porque no truena, solo calla. Se captura el entero (no el
    # objeto Empresa, con FKs perezosos) antes de encolar, y el callback
    # reabre su propio alcance al ejecutarse.
    empresa_id = empresa.pk

    def _notificar():
        with scope.con_empresa(Empresa.objects.get(pk=empresa_id)):
            notificar_reserva_pagada(reserva)

    transaction.on_commit(_notificar)
    return APLICADO


def _resolver_cobro_repetido(reserva, intent, empresa):
    """La reserva ya no esta pendiente. Si es el mismo intent, es Stripe
    reintentando el evento y no hay nada que hacer. Si es OTRO intent, al
    cliente le cobraron dos veces: se devuelve el segundo de inmediato."""
    if reserva.stripe_payment_intent_id == intent['id']:
        logger.info('Evento repetido del pago %s, ya aplicado', intent['id'])
        return YA_APLICADO

    logger.error(
        'Cobro duplicado en la reserva %s: ya pagada con %s y llego %s. Se reembolsa el segundo.',
        reserva.pk, reserva.stripe_payment_intent_id, intent['id'],
    )
    return (
        DUPLICADO_REEMBOLSADO
        if reembolsar(intent, 'cobro duplicado', empresa)
        else FALLO_REEMBOLSO
    )


def _verificar_monto(reserva, intent):
    """Compara lo que cobro Stripe contra lo que este servidor habia calculado.

    No rechaza el pago — el dinero ya entro y rebotarlo dejaria al cliente sin
    viaje y sin dinero hasta el reembolso — pero deja el descuadre en el log y
    visible en el admin (precio_total contra monto_pagado).
    """
    if intent['currency'].upper() != reserva.moneda:
        logger.error(
            'Moneda distinta en la reserva %s: se esperaba %s y llego %s',
            reserva.pk, reserva.moneda, intent['currency'].upper(),
        )
        return

    if reserva.precio_total is None:
        logger.error('Reserva %s sin precio_total al recibir el pago', reserva.pk)
        return

    esperado = a_centavos(monto_inicial(reserva.precio_total, reserva.forma_pago))
    if intent['amount_received'] != esperado:
        logger.error(
            'Descuadre en la reserva %s: se esperaban %s centavos y llegaron %s',
            reserva.pk, esperado, intent['amount_received'],
        )


def _cancelar_sin_cupo(reserva, intent, empresa):
    """El dia se lleno mientras el cliente pagaba. Se devuelve el 100% y la
    reserva queda cancelada con el motivo real, para que la vendedora la vea en
    su panel en vez de que desaparezca como 'pendiente de pago'."""
    if not reembolsar(intent, 'sin cupo', empresa):
        return FALLO_REEMBOLSO

    reserva.estado = Reserva.Estado.CANCELADA
    reserva.motivo_cancelacion = 'Sin cupo disponible al confirmar el pago. Reembolso automatico.'
    reserva.cancelada_en = timezone.now()
    reserva.reembolsada = True
    reserva.monto_reembolsado = de_centavos(intent['amount_received'])
    reserva.reembolsada_en = timezone.now()
    reserva.full_clean()
    reserva.save()
    return SIN_CUPO_REEMBOLSADO


def _cancelar_codigo_promocional_invalido(reserva, intent, empresa):
    """El codigo promocional se agoto, vencio o se desactivo mientras el
    cliente pagaba. Mismo remedio que sin cupo: se devuelve el 100% y la
    reserva queda cancelada con el motivo real, no uno prestado de cupo."""
    if not reembolsar(intent, 'codigo promocional invalido', empresa):
        return FALLO_REEMBOLSO

    reserva.estado = Reserva.Estado.CANCELADA
    reserva.motivo_cancelacion = (
        'El codigo promocional ya no era valido al confirmar el pago '
        '(se agoto, vencio o se desactivo). Reembolso automatico.'
    )
    reserva.cancelada_en = timezone.now()
    reserva.reembolsada = True
    reserva.monto_reembolsado = de_centavos(intent['amount_received'])
    reserva.reembolsada_en = timezone.now()
    reserva.full_clean()
    reserva.save()
    return CODIGO_INVALIDO_REEMBOLSADO


def _reserva_del_cargo(objeto, empresa):
    """La reserva a la que pertenece un Charge o un Dispute, via su
    PaymentIntent, acotada a `empresa` — sin RLS (sqlite, tests) nada mas
    evita que un stripe_payment_intent_id repetido entre Empresas (no deberia
    pasar, pero no hay unicidad que lo garantice) cruce el reembolso/disputa
    a la reserva equivocada."""
    try:
        intent_id = objeto['payment_intent']
    except (KeyError, TypeError):
        return None
    if not intent_id:
        return None
    return (
        Reserva.objects.select_for_update()
        .filter(stripe_payment_intent_id=intent_id, empresa=empresa)
        .first()
    )


@transaction.atomic
def aplicar_reembolso(charge, empresa):
    """Marca la reserva como reembolsada cuando el dinero se devuelve.

    Cubre los reembolsos hechos a mano desde el panel de Stripe: sin esto, los
    jefes devuelven el dinero y la reserva sigue figurando como cobrada.
    """
    reserva = _reserva_del_cargo(charge, empresa)
    if reserva is None:
        logger.warning('Reembolso de %s sin reserva asociada', charge['id'])
        return None

    reserva.reembolsada = True
    reserva.monto_reembolsado = _monto_devuelto(charge, reserva)
    reserva.reembolsada_en = reserva.reembolsada_en or timezone.now()
    reserva.save(update_fields=['reembolsada', 'monto_reembolsado', 'reembolsada_en'])
    logger.info('Reserva %s marcada como reembolsada por el cargo %s', reserva.pk, charge['id'])
    return reserva


def _monto_devuelto(charge, reserva):
    """Lo que Stripe reporta devuelto en ese cargo. `amount_refunded` es
    acumulado (cubre reembolsos parciales); si no viene, se asume que se
    devolvio todo lo cobrado."""
    try:
        return de_centavos(charge['amount_refunded'])
    except (KeyError, TypeError):
        return reserva.monto_pagado


@transaction.atomic
def aplicar_disputa(charge, abierta, empresa):
    """Levanta o baja la bandera de disputa (contracargo).

    No cambia el estado de la reserva: quien decide que hacer con un viaje en
    disputa es una persona, no el sistema. Lo unico que hace falta es que se vea
    en el panel antes de que salgan al mar.
    """
    reserva = _reserva_del_cargo(charge, empresa)
    if reserva is None:
        logger.warning('Disputa de %s sin reserva asociada', charge['id'])
        return None

    reserva.en_disputa = abierta
    reserva.save(update_fields=['en_disputa'])
    logger.error(
        'Reserva %s %s disputa (cargo %s)',
        reserva.pk, 'entro en' if abierta else 'salio de', charge['id'],
    )
    return reserva


def reembolsar(intent, motivo, empresa):
    """Devuelve el cobro completo con el cliente de Stripe de `empresa`. La
    `idempotency_key` va en `options` (segundo argumento), no en `params`
    (Revision 6, N-D) — evita que un reintento del webhook genere un segundo
    reembolso del mismo intent."""
    cliente = configurar_stripe(empresa)
    try:
        cliente.refunds.create(
            {'payment_intent': intent['id']},
            {'idempotency_key': f'refund-{intent["id"]}'},
        )
    except stripe.StripeError:
        logger.exception('Fallo el reembolso de %s (%s)', intent['id'], motivo)
        return False
    return True
```

- [ ] **Step 3: Corre el test, verifica que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.NotificarReservaPagadaOnCommitTests apps.payments.tests.ReembolsarTests apps.payments.tests.ReservaDelCargoAisladaPorEmpresaTests -v 2`
Expected: PASS (5 tests). El resto de `apps.payments.tests` (`PaymentIntentTests`,
`WebhookTests` y similares) sigue en rojo — es la tarea de retrofit de la suite
existente la que los pone en verde.

- [ ] **Step 4: Commit**

```bash
git add backend/apps/payments/services.py backend/apps/payments/tests.py
git commit -m "fix(payments): aplicar_pago_exitoso por Empresa, fix N1 (on_commit pierde alcance)"
```

---

### Task P6: `apps/payments/views.py` — `empresa_slug` + StripeClient en las 4 vistas

**Files:**
- Modify: `backend/apps/payments/views.py`
- Test: `backend/apps/payments/tests.py` (agregar al final)

**Interfaces:**
- Consumes: `apps.tenancy.scope.con_empresa`,
  `resolver_empresa_publica`/`resolver_empresa_de_dinero` (tenancy);
  `Tarifa.de(empresa)` (fleet); `evaluar_codigo_promocional(codigo, correo,
  empresa)` (bookings); `configurar_stripe(empresa)`, `aplicar_pago_exitoso`,
  `aplicar_reembolso`, `aplicar_disputa` (P5).
- Produces: `CrearPagoView.post(self, request, empresa_slug, pk)`,
  `EstadoReservaView.get(self, request, empresa_slug)`,
  `ValidarCodigoPromocionalView.get(self, request, empresa_slug)`,
  `StripeWebhookView.post(self, request, empresa_slug)` — las cuatro ganan
  `empresa_slug` como kwarg de URL. Consumido por P7 (`urls.py` debe mandar
  ese kwarg).

**Nota de alcance:** igual que P5, este task no retrofitea las clases de test
preexistentes que llaman a estas vistas con la firma vieja (sin `empresa_slug`)
o mockean `stripe.PaymentIntent.*`/`stripe.Refund.*` globales — eso es la tarea
de retrofit de la suite existente. Los tests de aquí ejercitan directamente el
código nuevo (algunos con mocks de ORM/Stripe para no depender de esa tarea).

- [ ] **Step 1: Escribe el test que falla**

Agrega al final de `backend/apps/payments/tests.py`:

```python
class IntentDeTests(TestCase):
    """_intent_de habla con el StripeClient explicito (P1), no con el modulo
    stripe global, y usa la forma real del SDK: update (no modify),
    idempotency_key en options (no en params)."""

    def setUp(self):
        self.view = CrearPagoView()
        self.reserva = mock.Mock(stripe_payment_intent_id='', pk=42, moneda='MXN')

    def test_crea_intent_nuevo_con_idempotency_en_options(self):
        cliente = mock.Mock()
        cliente.payment_intents.create.return_value = mock.Mock(id='pi_new')

        self.view._intent_de(cliente, self.reserva, Decimal('100.00'))

        params, options = cliente.payment_intents.create.call_args.args
        self.assertNotIn('idempotency_key', params)
        self.assertEqual(params['amount'], 10000)
        self.assertEqual(params['currency'], 'mxn')
        self.assertEqual(options, {'idempotency_key': 'reserva-42-mxn-10000'})

    def test_reutiliza_intent_reutilizable_mismo_monto(self):
        self.reserva.stripe_payment_intent_id = 'pi_1'
        cliente = mock.Mock()
        cliente.payment_intents.retrieve.return_value = mock.Mock(
            status='requires_payment_method', amount=10000, currency='mxn', id='pi_1',
        )

        resultado = self.view._intent_de(cliente, self.reserva, Decimal('100.00'))

        cliente.payment_intents.update.assert_not_called()
        self.assertEqual(resultado.id, 'pi_1')

    def test_ajusta_intent_con_update_no_modify(self):
        self.reserva.stripe_payment_intent_id = 'pi_1'
        cliente = mock.Mock()
        cliente.payment_intents.retrieve.return_value = mock.Mock(
            status='requires_payment_method', amount=5000, currency='mxn', id='pi_1',
        )

        self.view._intent_de(cliente, self.reserva, Decimal('100.00'))

        cliente.payment_intents.update.assert_called_once_with(
            'pi_1', {'amount': 10000, 'currency': 'mxn'},
        )

    def test_intent_ya_cobrando_lanza_pago_en_curso(self):
        self.reserva.stripe_payment_intent_id = 'pi_1'
        cliente = mock.Mock()
        cliente.payment_intents.retrieve.return_value = mock.Mock(status='succeeded')

        with self.assertRaises(PagoEnCurso):
            self.view._intent_de(cliente, self.reserva, Decimal('100.00'))


class ResolverCodigoPromocionalMultipleTests(TestCase):
    """N6: dos Empresas con el mismo codigo (posible tras quitar unique=True
    global) no debe reventar el checkout con 500."""

    def setUp(self):
        self.view = CrearPagoView()
        self.sede = Sede.objects.create(
            nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan',
        )
        self.empresa_a = Empresa.objects.create(
            sede=self.sede, nombre='A', slug='empresa-a',
            stripe_secret_key='sk_a', stripe_webhook_secret='whsec_a',
            stripe_publishable_key='pk_a',
        )

    @mock.patch('apps.payments.views.CodigoPromocional.objects')
    def test_multiple_objects_returned_da_400_no_500(self, mock_objects):
        mock_objects.get.side_effect = CodigoPromocional.MultipleObjectsReturned
        reserva = mock.Mock(correo_cliente='cliente@example.com', moneda='MXN')

        _, descuento, error = self.view._resolver_codigo_promocional(
            mock.Mock(data={'codigo_promocional': 'VERANO10'}),
            reserva, Decimal('1000.00'), self.empresa_a,
        )

        self.assertEqual(descuento, 0)
        self.assertEqual(error, 'El codigo promocional no es valido.')


class StripeWebhookViewUsaLaEmpresaDelSlugTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch('apps.payments.views.aplicar_pago_exitoso')
    @mock.patch('apps.payments.views.scope.con_empresa')
    @mock.patch('apps.payments.views.scope.resolver_empresa_de_dinero')
    @mock.patch('apps.payments.views.stripe.Webhook.construct_event')
    def test_usa_el_webhook_secret_de_la_empresa_aunque_este_pausada(
        self, mock_construct, mock_resolver, mock_con_empresa, mock_aplicar,
    ):
        # Revision 4 (N16): activo=False no debe impedir procesar dinero ya
        # cobrado — por eso el webhook resuelve con resolver_empresa_de_dinero,
        # no con resolver_empresa_publica.
        empresa = mock.Mock(stripe_webhook_secret='whsec_empresa_x', activo=False)
        mock_resolver.return_value = empresa
        mock_con_empresa.return_value.__enter__ = mock.Mock()
        mock_con_empresa.return_value.__exit__ = mock.Mock(return_value=False)
        mock_construct.return_value = {
            'id': 'evt_1', 'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_1'}},
        }

        request = self.factory.post(
            '/api/sal-y-sol/stripe/webhook/', data=b'{}',
            content_type='application/json', HTTP_STRIPE_SIGNATURE='firma',
        )
        response = StripeWebhookView.as_view()(request, empresa_slug='sal-y-sol')

        mock_resolver.assert_called_once_with('sal-y-sol')
        self.assertEqual(mock_construct.call_args.args[2], 'whsec_empresa_x')
        mock_aplicar.assert_called_once_with({'id': 'pi_1'}, empresa)
        self.assertEqual(response.status_code, 200)


class EstadoReservaViewFiltraPorEmpresaTests(TestCase):
    @mock.patch('apps.payments.views.scope.con_empresa')
    @mock.patch('apps.payments.views.scope.resolver_empresa_publica')
    @mock.patch('apps.payments.views.Reserva.objects.filter')
    def test_filtra_la_reserva_por_empresa(self, mock_filter, mock_resolver, mock_con_empresa):
        empresa = mock.Mock()
        mock_resolver.return_value = empresa
        mock_con_empresa.return_value.__enter__ = mock.Mock()
        mock_con_empresa.return_value.__exit__ = mock.Mock(return_value=False)
        mock_filter.return_value.order_by.return_value.first.return_value = None

        request = RequestFactory().get(
            '/api/sal-y-sol/reservas/estado/',
            {'checkout_id': '11111111-1111-4111-8111-111111111111'},
        )
        EstadoReservaView.as_view()(request, empresa_slug='sal-y-sol')

        mock_filter.assert_called_once_with(
            checkout_id=uuid.UUID('11111111-1111-4111-8111-111111111111'), empresa=empresa,
        )


class ValidarCodigoPromocionalViewPasaLaEmpresaTests(TestCase):
    @mock.patch('apps.payments.views.evaluar_codigo_promocional')
    @mock.patch('apps.payments.views.scope.con_empresa')
    @mock.patch('apps.payments.views.scope.resolver_empresa_publica')
    def test_pasa_la_empresa_resuelta(self, mock_resolver, mock_con_empresa, mock_evaluar):
        empresa = mock.Mock()
        mock_resolver.return_value = empresa
        mock_con_empresa.return_value.__enter__ = mock.Mock()
        mock_con_empresa.return_value.__exit__ = mock.Mock(return_value=False)
        mock_evaluar.return_value = None

        request = RequestFactory().get(
            '/api/sal-y-sol/codigo-promocional/validar/',
            {'codigo': 'VERANO10', 'correo_cliente': 'a@example.com'},
        )
        ValidarCodigoPromocionalView.as_view()(request, empresa_slug='sal-y-sol')

        mock_evaluar.assert_called_once_with('VERANO10', 'a@example.com', empresa)
```

Agrega a los imports de `apps/payments/tests.py`: `from decimal import Decimal`
(si no está), `from django.test import RequestFactory`, `from apps.tenancy
import scope`, `from apps.tenancy.models import Empresa, Sede`, `from .views
import (CrearPagoView, EstadoReservaView, PagoEnCurso, StripeWebhookView,
ValidarCodigoPromocionalView)`.

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.IntentDeTests apps.payments.tests.ResolverCodigoPromocionalMultipleTests apps.payments.tests.StripeWebhookViewUsaLaEmpresaDelSlugTests apps.payments.tests.EstadoReservaViewFiltraPorEmpresaTests apps.payments.tests.ValidarCodigoPromocionalViewPasaLaEmpresaTests -v 2`
Expected: FAIL — `_intent_de() missing 1 required positional argument: 'cliente'`
(hoy no lo recibe), `_resolver_codigo_promocional() missing 1 required
positional argument: 'empresa'`, `StripeWebhookView.as_view()() got an
unexpected keyword argument 'empresa_slug'` (y equivalentes en las otras dos).

- [ ] **Step 2: Implementación mínima**

Reemplaza el contenido completo de `backend/apps/payments/views.py`:

```python
import logging
import uuid

import stripe
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Reserva, codigo_promocional_valido, evaluar_codigo_promocional
from apps.fleet.models import CodigoPromocional, Tarifa, TransportePrecio
from apps.tenancy import scope

from .pricing import (
    a_centavos,
    cargo_por_descuento,
    cargo_por_extra,
    cargo_por_personas,
    cargo_por_transporte,
    monto_inicial,
    personas_extra,
)
from .stripe_client import configurar_stripe
from .services import aplicar_disputa, aplicar_pago_exitoso, aplicar_reembolso

logger = logging.getLogger(__name__)

INTENT_REUTILIZABLE = {'requires_payment_method', 'requires_confirmation', 'requires_action'}
INTENT_YA_COBRANDO = {'succeeded', 'processing'}


class PagoEnCurso(Exception):
    """El intent de la reserva ya esta cobrando o cobro: no se crea otro."""


class CrearPagoView(APIView):
    """Crea (o reutiliza) el PaymentIntent de Stripe de una reserva, con las
    llaves de la Empresa resuelta por `empresa_slug` en la URL.

    El monto se calcula aqui — tarifa en la moneda de la reserva + amenidades +
    100%/30% — y nunca se confia el total que manda el cliente. Cuenta estandar
    de Stripe, no Connect (ver docs/contexto-negocio.md).

    Es idempotente a proposito: darle dos veces a "Ir a pagar", recargar el
    checkout o cambiar de amenidades reusa el mismo intent en vez de dejar
    intents sueltos que podrian terminar cobrando dos veces.
    """

    throttle_scope = 'pagos'

    def post(self, request, empresa_slug, pk):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            return self._post(request, empresa, pk)

    def _post(self, request, empresa, pk):
        reserva = get_object_or_404(Reserva, pk=pk, empresa=empresa)

        # Los ids de reserva son consecutivos y la API es publica: sin esto,
        # cualquiera podria adivinar un id y generar cobros sobre la reserva de
        # otra persona. El checkout_id lo genera el navegador del cliente.
        if not reserva.checkout_id or str(reserva.checkout_id) != str(request.data.get('checkout_id')):
            return Response({'detail': 'checkout_id invalido para esta reserva.'}, status=403)

        if reserva.estado != Reserva.Estado.PENDIENTE_PAGO:
            return Response({'detail': 'Esta reserva ya no esta pendiente de pago.'}, status=409)

        tarifa = Tarifa.de(empresa)
        if tarifa is None:
            return Response({'detail': 'Tarifa no configurada.'}, status=503)

        precio_tour = tarifa.precio_en(reserva.moneda)
        if precio_tour is None:
            return Response({'detail': f'No hay precio configurado en {reserva.moneda}.'}, status=503)

        precio_persona_extra = tarifa.persona_extra_en(reserva.moneda)
        if personas_extra(reserva.numero_personas) and precio_persona_extra is None:
            return Response(
                {'detail': f'No hay cargo por persona extra configurado en {reserva.moneda}.'},
                status=503,
            )

        forma_pago = request.data.get('forma_pago', Reserva.FormaPago.COMPLETO)
        if forma_pago not in Reserva.FormaPago.values:
            return Response({'detail': 'forma_pago invalida.'}, status=400)

        cargo_extras, extras_a_borrar, extras_a_congelar, error = self._resolver_extras(reserva)
        if error:
            return Response({'detail': error}, status=503)
        cargo_transporte, transporte_a_borrar, transporte_congelado, error = self._resolver_transporte(
            reserva, empresa,
        )
        if error:
            return Response({'detail': error}, status=503)

        subtotal = (
            precio_tour
            + cargo_por_personas(precio_persona_extra or 0, reserva.numero_personas)
            + cargo_extras
            + cargo_transporte
        )

        codigo_promocional, descuento, error = self._resolver_codigo_promocional(
            request, reserva, subtotal, empresa,
        )
        if error:
            return Response({'detail': error}, status=400)

        precio_total = subtotal - descuento
        monto_a_cobrar = monto_inicial(precio_total, forma_pago)

        if not empresa.stripe_secret_key:
            return Response({'detail': 'Stripe no esta configurado todavia.'}, status=503)

        cliente = configurar_stripe(empresa)
        try:
            intent = self._intent_de(cliente, reserva, monto_a_cobrar)
        except PagoEnCurso:
            return Response(
                {'detail': 'Ya hay un cobro en curso para esta reserva.'}, status=409
            )
        except stripe.StripeError:
            logger.exception('Stripe fallo al preparar el pago de la reserva %s', reserva.pk)
            return Response({'detail': 'No se pudo iniciar el pago. Intenta de nuevo.'}, status=502)

        with transaction.atomic():
            for extra in extras_a_borrar:
                extra.delete()
            for extra, precio_unitario, cantidad in extras_a_congelar:
                extra.precio_unitario = precio_unitario
                extra.cantidad = cantidad
                extra.save(update_fields=['precio_unitario', 'cantidad'])

            if transporte_a_borrar is not None:
                transporte_a_borrar.delete()
            if transporte_congelado is not None:
                transporte, precio_calculado, personas_congeladas = transporte_congelado
                transporte.numero_personas = personas_congeladas
                transporte.precio_calculado = precio_calculado
                transporte.save(update_fields=['numero_personas', 'precio_calculado'])

            reserva.precio_total = precio_total
            reserva.forma_pago = forma_pago
            reserva.stripe_payment_intent_id = intent.id
            reserva.codigo_promocional = codigo_promocional
            reserva.descuento_aplicado = descuento if codigo_promocional else None
            reserva.save(update_fields=[
                'precio_total', 'forma_pago', 'stripe_payment_intent_id',
                'codigo_promocional', 'descuento_aplicado',
            ])

        return Response({
            'client_secret': intent.client_secret,
            'publishable_key': empresa.stripe_publishable_key,
            'monto_a_cobrar': str(monto_a_cobrar),
            'moneda': reserva.moneda,
        })

    def _resolver_extras(self, reserva):
        """Recorre lo que el cliente selecciono en el checkout y decide, sin
        tocar la base: que se cae (item desactivado desde que se eligio) y que
        se congela con el precio VIGENTE del catalogo. Devuelve (cargo_total,
        a_borrar, a_congelar, error). Sin filtro `empresa=` propio: opera sobre
        `reserva.extras_seleccionados`, ya acotado por la reserva misma."""
        cargo_total = 0
        a_borrar = []
        a_congelar = []
        for extra in reserva.extras_seleccionados.select_related('extras_item'):
            item = extra.extras_item
            if not item.activo:
                a_borrar.append(extra)
                continue
            precio = item.precio_en(reserva.moneda)
            if precio is None:
                return 0, [], [], f'No hay precio de "{item.nombre}" configurado en {reserva.moneda}.'
            cantidad = reserva.numero_personas if item.cobrar_por_persona else 1
            if item.cantidad_editable and extra.cantidad_solicitada is not None:
                cantidad = max(1, min(extra.cantidad_solicitada, reserva.numero_personas))
            cargo = cargo_por_extra(precio, item.cobrar_por_persona, cantidad)
            cargo_total += cargo
            a_congelar.append((extra, precio, cantidad))
        return cargo_total, a_borrar, a_congelar, None

    def _resolver_transporte(self, reserva, empresa):
        """Mismo criterio que `_resolver_extras`, para el traslado (a lo mas
        una fila por reserva). Devuelve (cargo, a_borrar_o_None,
        congelado_o_None, error). `empresa=empresa` explicito: sin RLS
        (sqlite/tests) nada mas evita que una zona con el mismo nombre de
        otra Empresa congele el precio equivocado (N5)."""
        if not hasattr(reserva, 'transporte'):
            return 0, None, None, None

        transporte = reserva.transporte
        precio_zona = TransportePrecio.objects.filter(
            zona=transporte.zona, activo=True, empresa=empresa,
        ).first()
        if precio_zona is None:
            return 0, transporte, None, None

        precio_base = precio_zona.precio_en(reserva.moneda)
        recargo = precio_zona.recargo_en(reserva.moneda)
        if precio_base is None:
            return 0, None, None, f'No hay precio de transporte configurado en {reserva.moneda}.'

        personas = reserva.numero_personas
        if transporte.personas_solicitadas is not None:
            personas = max(1, min(transporte.personas_solicitadas, reserva.numero_personas))

        cargo = cargo_por_transporte(
            precio_base, recargo, precio_zona.min_personas_recargo, personas
        )
        return cargo, None, (transporte, cargo, personas), None

    def _resolver_codigo_promocional(self, request, reserva, subtotal, empresa):
        """Resuelve el codigo (si vino uno) contra el SUBTOTAL real, con extras
        y transporte ya incluidos. `empresa=empresa` explicito (N6): con
        `codigo` ya no unico global, dos Empresas con el mismo codigo sin este
        filtro lanzarian `MultipleObjectsReturned` -> 500 en el checkout, no
        un 400 manejado; se captura explicitamente y se traduce igual que
        "no existe". Mismo mensaje generico sin importar el motivo, para no
        darle pistas a quien prueba codigos al azar.

        Devuelve (promo_o_None, descuento, error_o_None)."""
        codigo_str = (request.data.get('codigo_promocional') or '').strip()
        if not codigo_str:
            return None, 0, None

        try:
            promo = CodigoPromocional.objects.get(codigo=codigo_str.upper(), empresa=empresa)
        except CodigoPromocional.DoesNotExist:
            return None, 0, 'El codigo promocional no es valido.'
        except CodigoPromocional.MultipleObjectsReturned:
            logger.error(
                'Mas de un CodigoPromocional "%s" en la Empresa %s', codigo_str, empresa.slug,
            )
            return None, 0, 'El codigo promocional no es valido.'

        if not codigo_promocional_valido(
            promo, reserva.correo_cliente, monto_viaje=subtotal, moneda=reserva.moneda,
        ):
            return None, 0, 'El codigo promocional no es valido.'

        return promo, cargo_por_descuento(subtotal, promo.porcentaje_descuento), None

    def _intent_de(self, cliente, reserva, monto):
        """Reusa el intent de la reserva si sigue sin cobrar; si no, crea uno,
        con el `cliente` de Stripe explicito de la Empresa (P1) — nunca
        `stripe.PaymentIntent.*` global. `idempotency_key` va en el segundo
        argumento (`options`), no en `params` (forma real de `stripe==15.4.0`,
        Revision 6 N-D): meterlo en `params` pierde la proteccion de doble
        clic/doble cobro."""
        centavos = a_centavos(monto)
        moneda = reserva.moneda.lower()

        if reserva.stripe_payment_intent_id:
            intent = cliente.payment_intents.retrieve(reserva.stripe_payment_intent_id)
            if intent.status in INTENT_YA_COBRANDO:
                raise PagoEnCurso
            if intent.status in INTENT_REUTILIZABLE:
                if intent.amount == centavos and intent.currency == moneda:
                    return intent
                # Cambio de amenidades o de moneda: se ajusta el mismo intent.
                # El metodo real del servicio es `update`, no `modify`.
                return cliente.payment_intents.update(
                    intent.id, {'amount': centavos, 'currency': moneda},
                )

        return cliente.payment_intents.create(
            {
                'amount': centavos,
                'currency': moneda,
                'metadata': {'reserva_id': reserva.id},
            },
            {'idempotency_key': f'reserva-{reserva.pk}-{moneda}-{centavos}'},
        )


class ValidarCodigoPromocionalView(APIView):
    """Validacion en vivo del codigo mientras el cliente lo escribe en el
    checkout — solo informativa, no liga a ninguna reserva. La autoritativa
    vuelve a correr en `CrearPagoView`.

    Respuesta siempre `{'valido': bool, 'porcentaje_descuento': str|None}` sin
    importar el motivo del rechazo, para no darle pistas a quien prueba
    codigos al azar.
    """

    throttle_scope = 'codigo_promocional'

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            codigo = request.query_params.get('codigo', '')
            correo_cliente = request.query_params.get('correo_cliente', '')
            promo = evaluar_codigo_promocional(codigo, correo_cliente, empresa)
            return Response({
                'valido': promo is not None,
                'porcentaje_descuento': str(promo.porcentaje_descuento) if promo else None,
            })


class EstadoReservaView(APIView):
    """Estado de la reserva de un checkout, para reponerlo tras un refresh o
    un cierre accidental de la pestana.

    El `checkout_id` es la unica llave (nace en el navegador, sobrevive en
    `sessionStorage`) y sirve como capacidad de acceso — no hace falta login.
    Es de solo lectura y no llama a Stripe.
    """

    throttle_scope = 'estado_reserva'

    ESTADOS_PAGADA = {Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA, Reserva.Estado.COMPLETADA}

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            return self._get(request, empresa)

    def _get(self, request, empresa):
        crudo = request.query_params.get('checkout_id')
        try:
            checkout_id = uuid.UUID(str(crudo))
        except (ValueError, TypeError):
            return Response({'detail': 'checkout_id invalido.'}, status=400)

        reserva = (
            Reserva.objects.filter(checkout_id=checkout_id, empresa=empresa)
            .order_by('-id').first()
        )
        if reserva is None:
            return Response(
                {'detail': 'No se encontro una reserva para este checkout.'}, status=404
            )

        if reserva.estado == Reserva.Estado.CANCELADA:
            return Response({'estado': 'cancelada'})

        if reserva.estado in self.ESTADOS_PAGADA:
            transporte = getattr(reserva, 'transporte', None)
            return Response({
                'estado': 'pagada',
                'reserva_id': reserva.id,
                'fecha': reserva.fecha,
                'hora': reserva.hora,
                'numero_personas': reserva.numero_personas,
                'nombre_cliente': reserva.nombre_cliente,
                'correo_cliente': reserva.correo_cliente,
                'moneda': reserva.moneda,
                'forma_pago': reserva.forma_pago,
                'monto_pagado': str(reserva.monto_pagado) if reserva.monto_pagado is not None else None,
                'precio_total': str(reserva.precio_total) if reserva.precio_total is not None else None,
                'extras': [
                    {
                        'nombre': extra.extras_item.nombre,
                        'cobrar_por_persona': extra.extras_item.cobrar_por_persona,
                        'monto': str(extra.subtotal) if extra.subtotal is not None else None,
                        'cantidad': extra.cantidad,
                    }
                    for extra in reserva.extras_seleccionados.select_related('extras_item').all()
                ],
                'transporte': (
                    {'monto': str(transporte.precio_calculado), 'numero_personas': transporte.numero_personas}
                    if transporte is not None and transporte.precio_calculado is not None
                    else None
                ),
                'codigo_promocional': (
                    reserva.codigo_promocional.codigo if reserva.codigo_promocional_id else None
                ),
                'descuento_aplicado': (
                    str(reserva.descuento_aplicado) if reserva.descuento_aplicado is not None else None
                ),
            })

        transporte = getattr(reserva, 'transporte', None)
        return Response({
            'estado': 'pendiente_pago',
            'reserva_id': reserva.id,
            'fecha': reserva.fecha,
            'hora': reserva.hora,
            'numero_personas': reserva.numero_personas,
            'nombre_cliente': reserva.nombre_cliente,
            'telefono_cliente': reserva.telefono_cliente,
            'correo_cliente': reserva.correo_cliente,
            'moneda': reserva.moneda,
            'forma_pago': reserva.forma_pago,
            'extras': [
                {'id': extra.extras_item_id, 'cantidad': extra.cantidad_solicitada}
                for extra in reserva.extras_seleccionados.all()
            ],
            'transporte': {
                'punto_encuentro': transporte.punto_encuentro_id,
                'direccion_personalizada': transporte.direccion_personalizada,
                'zona': transporte.zona,
                'cantidad': transporte.personas_solicitadas,
            } if transporte else None,
        })


class StripeWebhookView(APIView):
    """Confirma el pago y marca la reserva como pagada.

    Resuelve la Empresa con `resolver_empresa_de_dinero` (Revision 4, N16):
    a diferencia de las rutas de catalogo/checkout, procesa el evento aunque
    `empresa.activo` sea False — una Empresa pausada sigue necesitando
    reconciliar dinero ya cobrado.
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def post(self, request, empresa_slug):
        empresa = scope.resolver_empresa_de_dinero(empresa_slug)

        try:
            evento = stripe.Webhook.construct_event(
                request.body,
                request.headers.get('Stripe-Signature', ''),
                empresa.stripe_webhook_secret,
            )
        except (ValueError, stripe.SignatureVerificationError):
            return Response(status=400)

        objeto = evento['data']['object']

        # Cualquier error aqui devolveria 500 y Stripe reintentaria el evento en
        # bucle. Se registra y se responde 200: el reintento no arreglaria nada.
        try:
            with scope.con_empresa(empresa):
                if evento['type'] == 'payment_intent.succeeded':
                    aplicar_pago_exitoso(objeto, empresa)
                elif evento['type'] == 'charge.refunded':
                    aplicar_reembolso(objeto, empresa)
                elif evento['type'] == 'charge.dispute.created':
                    aplicar_disputa(objeto, True, empresa)
                elif evento['type'] in ('charge.dispute.closed', 'charge.dispute.funds_reinstated'):
                    aplicar_disputa(objeto, False, empresa)
        except Exception:
            logger.exception('Fallo procesando %s (%s)', evento['id'], evento['type'])

        return Response(status=200)
```

- [ ] **Step 3: Corre el test, verifica que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.IntentDeTests apps.payments.tests.ResolverCodigoPromocionalMultipleTests apps.payments.tests.StripeWebhookViewUsaLaEmpresaDelSlugTests apps.payments.tests.EstadoReservaViewFiltraPorEmpresaTests apps.payments.tests.ValidarCodigoPromocionalViewPasaLaEmpresaTests -v 2`
Expected: PASS (7 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/apps/payments/views.py backend/apps/payments/tests.py
git commit -m "feat(payments): empresa_slug + StripeClient explicito en las 4 vistas"
```

---

### Task P7: `apps/payments/urls.py` — prefijo `empresa_slug`

**Files:**
- Modify: `backend/apps/payments/urls.py`
- Test: `backend/apps/payments/tests.py` (agregar al final)

**Interfaces:**
- Consumes: `CrearPagoView`, `EstadoReservaView`, `ValidarCodigoPromocionalView`,
  `StripeWebhookView` (P6, ya aceptan `empresa_slug`).
- Produces: rutas montadas bajo `/api/<empresa_slug>/...` (el `include('apps.
  payments.urls')` en `config/urls.py` ya monta bajo `/api/`, sin cambio ahí).

- [ ] **Step 1: Escribe el test que falla**

Agrega al final de `backend/apps/payments/tests.py`:

```python
class PaymentsUrlsTests(TestCase):
    def test_crear_pago_incluye_el_slug(self):
        url = reverse('crear-pago', kwargs={'empresa_slug': 'sal-y-sol', 'pk': 1})
        self.assertEqual(url, '/api/sal-y-sol/reservas/1/crear-pago/')

    def test_reserva_estado_incluye_el_slug(self):
        url = reverse('reserva-estado', kwargs={'empresa_slug': 'sal-y-sol'})
        self.assertEqual(url, '/api/sal-y-sol/reservas/estado/')

    def test_codigo_promocional_validar_incluye_el_slug(self):
        url = reverse('codigo-promocional-validar', kwargs={'empresa_slug': 'sal-y-sol'})
        self.assertEqual(url, '/api/sal-y-sol/codigo-promocional/validar/')

    def test_stripe_webhook_incluye_el_slug(self):
        url = reverse('stripe-webhook', kwargs={'empresa_slug': 'sal-y-sol'})
        self.assertEqual(url, '/api/sal-y-sol/stripe/webhook/')
```

Agrega a los imports de `apps/payments/tests.py`: `from django.urls import reverse`.

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.PaymentsUrlsTests -v 2`
Expected: FAIL — `NoReverseMatch: Reverse for 'crear-pago' with keyword
arguments '{'empresa_slug': 'sal-y-sol', 'pk': 1}' not found.`

- [ ] **Step 2: Implementación mínima**

Reemplaza el contenido completo de `backend/apps/payments/urls.py`:

```python
from django.urls import path

from .views import CrearPagoView, EstadoReservaView, StripeWebhookView, ValidarCodigoPromocionalView

urlpatterns = [
    path(
        '<slug:empresa_slug>/reservas/<int:pk>/crear-pago/', CrearPagoView.as_view(),
        name='crear-pago',
    ),
    path(
        '<slug:empresa_slug>/reservas/estado/', EstadoReservaView.as_view(),
        name='reserva-estado',
    ),
    path(
        '<slug:empresa_slug>/codigo-promocional/validar/', ValidarCodigoPromocionalView.as_view(),
        name='codigo-promocional-validar',
    ),
    path(
        '<slug:empresa_slug>/stripe/webhook/', StripeWebhookView.as_view(),
        name='stripe-webhook',
    ),
]
```

- [ ] **Step 3: Corre el test, verifica que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.PaymentsUrlsTests -v 2`
Expected: PASS (4 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/apps/payments/urls.py backend/apps/payments/tests.py
git commit -m "feat(payments): rutas ganan el prefijo empresa_slug"
```

---

### Task P8: `apps/payments/management/commands/conciliar_pagos.py` — por Empresa

**Files:**
- Modify: `backend/apps/payments/management/commands/conciliar_pagos.py`
- Test: `backend/apps/payments/tests.py` (agregar al final)

**Interfaces:**
- Consumes: `apps.tenancy.scope.con_empresa`, `apps.tenancy.models.Empresa`,
  `configurar_stripe(empresa)` (P1), `aplicar_pago_exitoso(intent, empresa)` (P5).
- Produces: sin cambio de superficie pública — sigue siendo el comando
  `conciliar_pagos [--dias N] [--dry-run]`, ahora itera por Empresa por dentro.

- [ ] **Step 1: Escribe el test que falla**

Agrega al final de `backend/apps/payments/tests.py`:

```python
class ConciliarPagosPorEmpresaTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(
            nombre='La Paz', slug='la-paz', zona_horaria='America/Mazatlan',
        )
        self.empresa_con_llave = Empresa.objects.create(
            sede=self.sede, nombre='Con llave', slug='con-llave',
            stripe_secret_key='sk_test_x', stripe_webhook_secret='whsec_x',
            stripe_publishable_key='pk_x',
        )
        self.empresa_sin_llave = Empresa.objects.create(
            sede=self.sede, nombre='Sin llave', slug='sin-llave',
            stripe_secret_key='', stripe_webhook_secret='', stripe_publishable_key='',
        )

    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_se_salta_empresas_sin_llave_sin_abortar_el_comando(self, mock_configurar):
        salida = StringIO()
        call_command('conciliar_pagos', '--dry-run', stdout=salida)

        mock_configurar.assert_called_once_with(self.empresa_con_llave)
        texto = salida.getvalue()
        self.assertIn('sin-llave', texto)
        self.assertIn('sin llave de Stripe', texto)

    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_itera_tambien_empresas_pausadas(self, mock_configurar):
        # Revision 4 (N16): una Empresa pausada puede tener dinero ya cobrado
        # pendiente de reconciliar — el comando no debe saltarsela por activo=False.
        self.empresa_con_llave.activo = False
        self.empresa_con_llave.save(update_fields=['activo'])

        call_command('conciliar_pagos', '--dry-run', stdout=StringIO())

        mock_configurar.assert_called_once_with(self.empresa_con_llave)

    @mock.patch('apps.payments.management.commands.conciliar_pagos.configurar_stripe')
    def test_filtra_las_reservas_pendientes_por_empresa(self, mock_configurar):
        cliente = mock.Mock()
        mock_configurar.return_value = cliente
        crear_flota()
        with scope.con_empresa(self.empresa_con_llave):
            reserva = Reserva(
                empresa=self.empresa_con_llave, fecha=date.today() + timedelta(days=10),
                hora=time(6, 0), numero_personas=2, nombre_cliente='Ana',
                telefono_cliente='+5216121234567', correo_cliente='ana@example.com',
                canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True,
                deslinde_nombre='Ana', checkout_id=uuid.uuid4(), moneda='MXN',
                stripe_payment_intent_id='pi_pendiente',
            )
            reserva.full_clean()
            reserva.save()

        cliente.payment_intents.retrieve.return_value = mock.Mock(status='requires_payment_method')
        call_command('conciliar_pagos', '--dry-run', stdout=StringIO())

        cliente.payment_intents.retrieve.assert_called_once_with('pi_pendiente')
```

Agrega a los imports de `apps/payments/tests.py`: `from apps.payments.
management.commands.conciliar_pagos import Command as ConciliarPagosCommand`
no es necesario (se invoca via `call_command`), pero sí `from apps.tenancy
import scope` y `from apps.tenancy.models import Empresa, Sede` si aún no
están (ya agregados en tasks anteriores de esta sección).

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.ConciliarPagosPorEmpresaTests -v 2`
Expected: FAIL — el comando de hoy usa `settings.STRIPE_SECRET_KEY` global y
`configurar_stripe()` sin argumento; `mock_configurar.assert_called_once_with
(self.empresa_con_llave)` falla porque `configurar_stripe` (aún sin migrar)
no existe con esa firma en el módulo del comando, y el comando aborta entero
si no hay `STRIPE_SECRET_KEY` en settings en vez de saltarse por Empresa.

- [ ] **Step 2: Implementación mínima**

Reemplaza el contenido completo de
`backend/apps/payments/management/commands/conciliar_pagos.py`:

```python
"""Red de seguridad del webhook de Stripe, una Empresa a la vez.

Lo normal es que el webhook marque la reserva como pagada en segundos. Pero si
una entrega se pierde de forma permanente (el backend estaba caido, el
`webhook_secret` de esa Empresa estaba mal, Stripe se rindio tras sus
reintentos), queda un cliente que pago y no tiene reserva. Nadie se entera
hasta que reclama.

Este comando busca, por cada Empresa con llave de Stripe configurada, reservas
en `pendiente_pago` que ya tengan un PaymentIntent, le pregunta a Stripe como
quedo, y aplica exactamente la misma logica que el webhook (ver
apps/payments/services.py). Itera TODAS las Empresas, activas o no (Revision 4,
N16): una pausada puede tener dinero ya cobrado pendiente de reconciliar.
Pensado para un cron cada hora.
"""
from datetime import timedelta

import stripe
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import Reserva
from apps.payments.services import aplicar_pago_exitoso
from apps.payments.stripe_client import configurar_stripe
from apps.tenancy import scope
from apps.tenancy.models import Empresa

DIAS_POR_DEFECTO = 7


class Command(BaseCommand):
    help = 'Aplica los pagos que Stripe confirmo pero cuyo webhook nunca llego, por Empresa.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=DIAS_POR_DEFECTO,
            help=f'Hasta que antiguedad revisar. Por defecto {DIAS_POR_DEFECTO}.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo dice que haria, sin tocar ni la base ni Stripe.',
        )

    def handle(self, *args, **options):
        desde = timezone.now() - timedelta(days=options['dias'])
        total_revisadas = total_aplicadas = 0

        for empresa in Empresa.objects.all():
            if not empresa.stripe_secret_key:
                self.stdout.write(f'Empresa {empresa.slug}: sin llave de Stripe, se salta.')
                continue

            with scope.con_empresa(empresa):
                revisadas, aplicadas = self._conciliar_empresa(empresa, desde, options)
            total_revisadas += revisadas
            total_aplicadas += aplicadas

        resumen = (
            f'{total_revisadas} reserva(s) revisada(s), '
            f'{total_aplicadas} con pago confirmado en Stripe.'
        )
        self.stdout.write(
            self.style.WARNING(f'[dry-run] {resumen}') if options['dry_run']
            else self.style.SUCCESS(resumen)
        )

    def _conciliar_empresa(self, empresa, desde, options):
        cliente = configurar_stripe(empresa)
        pendientes = Reserva.objects.filter(
            estado=Reserva.Estado.PENDIENTE_PAGO, creado_en__gte=desde, empresa=empresa,
        ).exclude(stripe_payment_intent_id='')

        revisadas = aplicadas = 0
        for reserva in pendientes:
            revisadas += 1
            try:
                intent = cliente.payment_intents.retrieve(reserva.stripe_payment_intent_id)
            except stripe.StripeError as exc:
                self.stderr.write(f'Reserva {reserva.pk}: no se pudo consultar Stripe ({exc}).')
                continue

            if intent.status != 'succeeded':
                continue

            if options['dry_run']:
                self.stdout.write(
                    f'Reserva {reserva.pk}: pago {intent.id} esta succeeded por '
                    f'{intent.amount_received / 100} {intent.currency.upper()} y sigue pendiente.'
                )
                aplicadas += 1
                continue

            resultado = aplicar_pago_exitoso(intent, empresa)
            aplicadas += 1
            self.stdout.write(f'Reserva {reserva.pk}: {resultado}.')

        return revisadas, aplicadas
```

- [ ] **Step 3: Corre el test, verifica que pasa**

Run: `venv\Scripts\python.exe manage.py test apps.payments.tests.ConciliarPagosPorEmpresaTests -v 2`
Expected: PASS (3 tests).

- [ ] **Step 4: Commit**

```bash
git add backend/apps/payments/management/commands/conciliar_pagos.py backend/apps/payments/tests.py
git commit -m "fix(payments): conciliar_pagos itera por Empresa, incluidas las pausadas"
```

---

## Self-Review de la sección P

**Cobertura contra las filas del File Map que le tocan a esta sección** (todas
verificadas con una tarea que las cubre):

- `apps/finance/views.py` → P4. `apps/finance/services.py` → P3.
- `apps/payments/stripe_client.py` → P1. `apps/payments/checks.py` → P2.
- `apps/payments/services.py` → P5. `apps/payments/views.py` → P6.
- `apps/payments/urls.py` → P7.
- `apps/payments/management/commands/conciliar_pagos.py` → P8.

**Fuera de esta sección a propósito** (dueño explícito en el preámbulo): el
retrofit masivo de `apps/payments/tests.py` (~52 `mock.patch('stripe.*')` +
`PaymentIntentTests`/`WebhookTests` con la firma vieja) — sección "Suite de
tests existente"; `apps/testing.py` (helper `ApiTestCase`/`crear_flota` con
`Sede`/`Empresa`) — misma sección; `apps/tenancy/*`, `apps/fleet/*`,
`apps/bookings/*` — secciones propias.

**Escaneo de placeholders:** sin "TBD"/"TODO"/"implementar despues" en ningún
paso; cada Step 2 trae el archivo completo a escribir, no un diff descrito en
prosa; cada test trae aserciones concretas, no un comentario "probar que
funciona".

**Consistencia de tipos/firmas entre tareas:**
`configurar_stripe(empresa) -> stripe.StripeClient` (P1) es exactamente lo que
P5 (`reembolsar`), P6 (`CrearPagoView._post`) y P8 (`_conciliar_empresa`)
importan y llaman. `aplicar_pago_exitoso(intent, empresa)`,
`aplicar_reembolso(charge, empresa)`, `aplicar_disputa(charge, abierta,
empresa)` (P5) son exactamente lo que P6 (`StripeWebhookView.post`) y P8
llaman — mismo orden de argumentos en los tres sitios. `balances`/
`balances_por_dia`/`resumen` (P3) con `empresa=None` como kwarg-only-en-la-
práctica es lo que P4 llama con `empresa=empresa` en los tres casos. El
nombre `connection.alcance_actual` (P5, test de `on_commit`) es el fijado por
la sección tenancy en `apps/tenancy/scope.py` — no se inventa un nombre nuevo
aquí.

---

### Infra/CI/Settings/Frontend/Producción (I1-I5)

# Tareas bite-sized — Sección I: Infra / CI / Settings / Frontend / Producción

> Fragmento del plan `2026-08-31-expansion-multi-sede-pieza1-tenancy.md` (File Map ya
> aprobado tras 9 rondas de architecture-critic, ver marcador al final de ese
> documento). Esta sección cubre exclusivamente las filas del File Map de
> `config/settings/base.py`, `config/urls.py`, `.github/workflows/ci.yml`,
> `config/settings/ci.py`, `frontend/src/lib/api.ts` y `config/settings/production.py`.
> El resto de secciones (tenancy core, fleet, bookings, payments/finance) se escriben
> en archivos de tareas aparte.

**Dependencia dura de esta sección:** las Tasks I1 y I3 asumen que el paquete
`apps/tenancy/` ya existe con al menos `__init__.py` + `apps.py` (`AppConfig.name =
'apps.tenancy'`) y, para I1, que `apps/tenancy/scope.py` expone
`es_operador_plataforma(user) -> bool` y `empresa_actual(request) -> Empresa | None`,
y que `apps/tenancy/admin.py` registra `Sede`/`Empresa`/`MembresiaEmpresa` (para que
existan las URLs de admin `admin:tenancy_sede_changelist`, etc.). Sin eso, `manage.py
test` falla al poblar `INSTALLED_APPS`, no con un fallo de test — es un fallo de
orden de ejecución, no de esta sección. Ejecutar la sección de tenancy core primero.

Comando de test (Windows, desde `backend/`): `venv\Scripts\python.exe manage.py test config`

---

### Task I1: `config/settings/base.py` — apps.tenancy, middleware, sidebar y permiso de Finanzas

**Files:**
- Modify: `backend/config/settings/base.py` (INSTALLED_APPS líneas 12-40, MIDDLEWARE
  líneas 295-310, UNFOLD líneas 137-293)
- Create: `backend/config/tests_tenancy_settings.py`

**Interfaces:**
- Consumes: `apps.tenancy.scope.es_operador_plataforma(user) -> bool`,
  `apps.tenancy.scope.empresa_actual(request) -> Empresa | None` (de la app `tenancy`,
  ya debe existir — ver dependencia dura arriba). `admin:tenancy_sede_changelist`,
  `admin:tenancy_empresa_changelist`, `admin:tenancy_membresiaempresa_changelist`
  (nombres de URL que registra `apps/tenancy/admin.py`).
- Produces: `apps.tenancy.middleware.EmpresaScopeMiddleware` referenciado por su
  dotted path en `MIDDLEWARE` — cualquier tarea que module ese middleware debe
  mantener el nombre de clase y la ruta del módulo, o esta entrada de settings queda
  apuntando a nada.

- [ ] **Step 1: Escribir los tests que fallan (import de settings + INSTALLED_APPS/MIDDLEWARE)**

Crear `backend/config/tests_tenancy_settings.py`:

```python
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase


def _item_por_titulo(titulo):
    for grupo in settings.UNFOLD['SIDEBAR']['navigation']:
        for item in grupo['items']:
            if item['title'] == titulo:
                return item
    raise AssertionError(f"No se encontro el item {titulo!r} en UNFOLD['SIDEBAR']")


class TenancyInstalledAppsTests(SimpleTestCase):
    def test_apps_tenancy_antes_de_fleet_y_bookings(self):
        apps = settings.INSTALLED_APPS
        self.assertIn('apps.tenancy', apps)
        self.assertLess(apps.index('apps.tenancy'), apps.index('apps.fleet'))
        self.assertLess(apps.index('apps.tenancy'), apps.index('apps.bookings'))


class EmpresaScopeMiddlewareOrderTests(SimpleTestCase):
    def test_middleware_va_despues_de_auth_y_de_axes(self):
        mw = settings.MIDDLEWARE
        idx_auth = mw.index('django.contrib.auth.middleware.AuthenticationMiddleware')
        idx_axes = mw.index('axes.middleware.AxesMiddleware')
        idx_scope = mw.index('apps.tenancy.middleware.EmpresaScopeMiddleware')
        self.assertGreater(idx_scope, idx_auth)
        self.assertGreater(idx_scope, idx_axes)


class SidebarTenancyTests(SimpleTestCase):
    def test_sede_empresa_membresia_solo_operador_de_plataforma(self):
        for titulo in ('Sedes', 'Empresas', 'Membresias'):
            item = _item_por_titulo(titulo)
            with mock.patch(
                'apps.tenancy.scope.es_operador_plataforma', return_value=True
            ):
                self.assertTrue(item['permission'](mock.Mock()), titulo)
            with mock.patch(
                'apps.tenancy.scope.es_operador_plataforma', return_value=False
            ):
                self.assertFalse(item['permission'](mock.Mock()), titulo)


class FinanzasPermisoTests(SimpleTestCase):
    def test_visible_para_operador_de_plataforma(self):
        item = _item_por_titulo('Finanzas')
        with mock.patch(
            'apps.tenancy.scope.es_operador_plataforma', return_value=True
        ):
            self.assertTrue(item['permission'](mock.Mock()))

    def test_visible_para_jefe_o_vendedora_con_empresa(self):
        item = _item_por_titulo('Finanzas')
        with mock.patch(
            'apps.tenancy.scope.es_operador_plataforma', return_value=False
        ), mock.patch(
            'apps.tenancy.scope.empresa_actual', return_value=mock.Mock()
        ):
            self.assertTrue(item['permission'](mock.Mock()))

    def test_oculto_sin_membresia_ni_operador(self):
        item = _item_por_titulo('Finanzas')
        with mock.patch(
            'apps.tenancy.scope.es_operador_plataforma', return_value=False
        ), mock.patch('apps.tenancy.scope.empresa_actual', return_value=None):
            self.assertFalse(item['permission'](mock.Mock()))
```

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `venv\Scripts\python.exe manage.py test config.tests_tenancy_settings -v 2`
Expected: FAIL — `TenancyInstalledAppsTests` con `AssertionError` (`'apps.tenancy' not
in list`), el resto con `ValueError`/`AssertionError` (middleware no está en la lista,
o no existe ningún item `'Sedes'`/`'Empresas'`/`'Membresias'` y `Finanzas` sigue
comparando contra `is_superuser`).

- [ ] **Step 3: INSTALLED_APPS + MIDDLEWARE**

En `backend/config/settings/base.py`, agregar `'apps.tenancy',` a `INSTALLED_APPS`
justo antes de `'apps.fleet',` (línea 35 hoy):

```python
    'apps.tenancy',
    'apps.fleet',
    'apps.bookings',
    'apps.payments',
    'apps.notifications',
    'apps.finance',
]
```

Y en `MIDDLEWARE`, agregar la entrada nueva al final de la lista (después de
`axes.middleware.AxesMiddleware`, línea 309 hoy):

```python
    'axes.middleware.AxesMiddleware',
    # Al final de todo: necesita request.user (AuthenticationMiddleware) y no debe
    # interferir con el bloqueo de fuerza bruta de Axes.
    'apps.tenancy.middleware.EmpresaScopeMiddleware',
]
```

- [ ] **Step 4: Correr los dos primeros tests, verificar que pasan**

Run: `venv\Scripts\python.exe manage.py test config.tests_tenancy_settings.TenancyInstalledAppsTests config.tests_tenancy_settings.EmpresaScopeMiddlewareOrderTests -v 2`
Expected: PASS (2 tests)

- [ ] **Step 5: Import de `scope` + entradas de sidebar para Sede/Empresa/Membresía**

En `backend/config/settings/base.py`, agregar el import junto a los demás, antes de
`UNFOLD = {`:

```python
from apps.tenancy import scope
```

En el bloque `'Sistema'` de `UNFOLD['SIDEBAR']['navigation']` (líneas 265-282 hoy),
agregar tres items nuevos al principio de su lista `'items'`, antes de `'Usuarios'`:

```python
            {
                'title': 'Sistema',
                'separator': True,
                'items': [
                    {
                        'title': 'Sedes',
                        'icon': 'location_on',
                        'link': reverse_lazy('admin:tenancy_sede_changelist'),
                        'permission': lambda request: scope.es_operador_plataforma(
                            request.user
                        ),
                    },
                    {
                        'title': 'Empresas',
                        'icon': 'store',
                        'link': reverse_lazy('admin:tenancy_empresa_changelist'),
                        'permission': lambda request: scope.es_operador_plataforma(
                            request.user
                        ),
                    },
                    {
                        'title': 'Membresias',
                        'icon': 'badge',
                        'link': reverse_lazy(
                            'admin:tenancy_membresiaempresa_changelist'
                        ),
                        'permission': lambda request: scope.es_operador_plataforma(
                            request.user
                        ),
                    },
                    {
                        'title': 'Usuarios',
                        'icon': 'person',
                        'link': reverse_lazy('admin:auth_user_changelist'),
                        'permission': lambda request: request.user.has_perm('auth.view_user'),
                    },
                    {
                        'title': 'Grupos',
                        'icon': 'group',
                        'link': reverse_lazy('admin:auth_group_changelist'),
                        'permission': lambda request: request.user.has_perm('auth.view_group'),
                    },
                ],
            },
```

(Solo se insertan los tres items nuevos antes de `'Usuarios'`; `'Usuarios'` y
`'Grupos'` se quedan exactamente como estaban.)

- [ ] **Step 6: Correr el test de sidebar, verificar que pasa**

Run: `venv\Scripts\python.exe manage.py test config.tests_tenancy_settings.SidebarTenancyTests -v 2`
Expected: PASS

- [ ] **Step 7: Reemplazar el permiso de "Finanzas"**

En el bloque `'Dinero'` de `UNFOLD['SIDEBAR']['navigation']` (línea 233 hoy), cambiar:

```python
                        'permission': lambda request: request.user.is_superuser,
```

por:

```python
                        'permission': lambda request: (
                            scope.es_operador_plataforma(request.user)
                            or scope.empresa_actual(request) is not None
                        ),
```

- [ ] **Step 8: Correr todos los tests del archivo, verificar que pasan**

Run: `venv\Scripts\python.exe manage.py test config.tests_tenancy_settings -v 2`
Expected: PASS (7 tests)

- [ ] **Step 9: Commit**

```bash
git add backend/config/settings/base.py backend/config/tests_tenancy_settings.py
git commit -m "feat(tenancy): registra apps.tenancy, EmpresaScopeMiddleware y sidebar/permiso de Finanzas por membresia"
```

---

### Task I2: `config/urls.py` — guardarraíl de que las rutas base no llevan prefijo de Empresa

**Files:**
- Test: `backend/config/tests_urls_sin_prefijo_empresa.py`
- Modify: ninguno — el File Map de la Revisión 5 en adelante es explícito: *"Los
  `include()` de `api/` no cambian de forma, heredan los prefijos
  `<slug:empresa_slug>/` de cada app. `admin/finanzas/` no cambia de ruta."* El
  prefijo se agrega dentro de `apps/fleet/urls.py`, `apps/bookings/urls.py`,
  `apps/payments/urls.py` (tareas de otras secciones), nunca en `config/urls.py`.

**Interfaces:**
- Consumes: nada nuevo.
- Produces: nada nuevo — esta tarea es un test de regresión, para que quien toque
  `config/urls.py` más tarde (al agregar el prefijo dentro de cada app) no lo suba
  por error un nivel, lo que rompería `/healthz` (deja de pasar el healthcheck de
  Render) y `/admin/finanzas/` (deja de resolver para nadie).

- [ ] **Step 1: Escribir el test de regresión**

Crear `backend/config/tests_urls_sin_prefijo_empresa.py`:

```python
from django.test import SimpleTestCase
from django.urls import reverse


class RutasSinPrefijoDeEmpresaTests(SimpleTestCase):
    """
    Guardarraíl para la expansión multi-sede: el prefijo `<slug:empresa_slug>/`
    vive dentro de cada `apps/<app>/urls.py`, nunca en `config/urls.py`. Si
    alguien lo sube un nivel, `/healthz` deja de resolver donde Render lo espera
    y `/admin/finanzas/` deja de resolver donde el admin lo espera.
    """

    def test_healthz_sin_prefijo(self):
        self.assertEqual(reverse('healthz'), '/healthz')

    def test_finanzas_sin_prefijo(self):
        self.assertEqual(reverse('finanzas'), '/admin/finanzas/')

    def test_admin_index_sin_prefijo(self):
        self.assertEqual(reverse('admin:index'), '/admin/')
```

- [ ] **Step 2: Correr el test — nota sobre el resultado esperado**

Run: `venv\Scripts\python.exe manage.py test config.tests_urls_sin_prefijo_empresa -v 2`
Expected: **PASS de inmediato** — a diferencia del resto de tareas de este plan, esta
no requiere ningún cambio de implementación (el File Map dice explícitamente que
`config/urls.py` no cambia de forma). El test existe para que el PASS se rompa
(y avise) el día que alguien sí lo cambie por error, no para guiar una
implementación pendiente.

- [ ] **Step 3: Commit**

```bash
git add backend/config/tests_urls_sin_prefijo_empresa.py
git commit -m "test(urls): guardarraiel de que config/urls.py no lleva prefijo de empresa"
```

---

### Task I3: `.github/workflows/ci.yml` + `config/settings/ci.py` — rol de Postgres sin `BYPASSRLS` en CI

**Files:**
- Modify: `backend/config/settings/ci.py:22`
- Create: `backend/config/tests_settings_ci_db_user.py`
- Modify: `.github/workflows/ci.yml` (servicio `postgres` líneas 37-52, pasos líneas
  54-77)

**Interfaces:**
- Consumes: nada nuevo (usa `os.environ` y el motor `postgres:17` ya declarado en
  `ci.yml`).
- Produces: el rol `ci_rls` (login, `NOSUPERUSER NOBYPASSRLS CREATEDB`, sin
  `BYPASSRLS`) que `apps/tenancy/tests_rls.py` (otra sección) asume que existe y usa
  para probar que las políticas RLS realmente filtran filas — sin este rol, ese
  archivo de tests no tiene contra qué correr.

**Parte A — `config/settings/ci.py` (TDD, es código Python real).**

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/config/tests_settings_ci_db_user.py`:

```python
import importlib
import os
from unittest import mock

from django.test import SimpleTestCase


class DefaultDbUserYaNoEsPostgresTests(SimpleTestCase):
    """
    `config/settings/ci.py` deja de asumir el superusuario `postgres` como
    default de `DB_USER` — el rol nuevo (`ci_rls`, ver .github/workflows/ci.yml)
    es el que CI usa de verdad. Recarga el módulo con `DB_USER` ausente del
    entorno para leer su valor de default sin depender de qué settings module
    esté activo mientras corre este test.
    """

    def test_default_db_user_es_ci_rls(self):
        entorno_sin_db_user = {k: v for k, v in os.environ.items() if k != 'DB_USER'}
        with mock.patch.dict(os.environ, entorno_sin_db_user, clear=True):
            modulo = importlib.import_module('config.settings.ci')
            importlib.reload(modulo)
            self.assertEqual(modulo.DATABASES['default']['USER'], 'ci_rls')
```

- [ ] **Step 2: Correr el test, verificar que falla**

Run: `venv\Scripts\python.exe manage.py test config.tests_settings_ci_db_user -v 2`
Expected: FAIL — `AssertionError: 'postgres' != 'ci_rls'`

- [ ] **Step 3: Cambiar el default**

En `backend/config/settings/ci.py:22`, cambiar:

```python
        'USER': os.environ.get('DB_USER', 'postgres'),
```

por:

```python
        'USER': os.environ.get('DB_USER', 'ci_rls'),
```

- [ ] **Step 4: Correr el test, verificar que pasa**

Run: `venv\Scripts\python.exe manage.py test config.tests_settings_ci_db_user -v 2`
Expected: PASS

- [ ] **Step 5: Commit de la parte A**

```bash
git add backend/config/settings/ci.py backend/config/tests_settings_ci_db_user.py
git commit -m "fix(ci): default de DB_USER deja de ser el superusuario postgres"
```

**Parte B — `.github/workflows/ci.yml` (checklist operacional, no hay test que corra
en este repo para un workflow de GitHub Actions — se verifica corriendo el workflow
de verdad en un push, ver Step 4).**

- [ ] **Step 1: Agregar el paso que crea el rol `ci_rls`, después de "pip install" y
  antes de "Tests"**

En `.github/workflows/ci.yml`, entre el paso `- run: pip install -r requirements.txt`
(línea 63 hoy) y el paso `- name: Tests (${{ matrix.motor }})` (línea 69 hoy),
insertar:

```yaml
      - run: pip install -r requirements.txt

      # POSTGRES_USER/POSTGRES_PASSWORD del servicio de arriba NO cambian: es el
      # superusuario de arranque del contenedor postgres:17, renombrarlo no le
      # quita el superusuario. Este rol nuevo es el que corre `migrate` y los
      # tests, sin SUPERUSER ni BYPASSRLS, para que tests_rls.py pruebe el
      # aislamiento de verdad en vez de pasar en verde por estar exento de él.
      - name: Crear rol de test sin privilegios (para probar RLS de verdad)
        if: matrix.motor == 'postgres'
        env:
          PGPASSWORD: postgres
        run: |
          psql -h localhost -U postgres -d pescadeportiva_test -v ON_ERROR_STOP=1 -c \
            "CREATE ROLE ci_rls LOGIN PASSWORD 'ci_rls_password_local' NOSUPERUSER NOBYPASSRLS CREATEDB;"

      - name: Tests (${{ matrix.motor }})
```

(`psql` viene preinstalado en el runner `ubuntu-latest` de GitHub Actions — no hace
falta un paso de instalación aparte. Si un cambio de imagen del runner lo quita,
`psql: command not found` lo hace evidente de inmediato, no en silencio.)

- [ ] **Step 2: Cambiar `DB_USER`/`DB_PASSWORD` del paso de tests, dejando
  `POSTGRES_USER`/`POSTGRES_PASSWORD` del servicio intactos**

En el mismo archivo, el bloque `env:` del paso `Tests (${{ matrix.motor }})`
(líneas 70-76 hoy) cambia de:

```yaml
        env:
          DJANGO_SETTINGS_MODULE: ${{ matrix.settings }}
          DB_NAME: pescadeportiva_test
          DB_USER: postgres
          DB_PASSWORD: postgres
          DB_HOST: localhost
          DB_PORT: "5432"
```

a:

```yaml
        env:
          DJANGO_SETTINGS_MODULE: ${{ matrix.settings }}
          DB_NAME: pescadeportiva_test
          # ci_rls, no postgres: el rol sin BYPASSRLS creado arriba. La rama
          # sqlite (config.settings.local) ignora estas dos variables por
          # completo — DATABASES ahi esta fijo a sqlite3, no lee el entorno —
          # asi que no hace falta condicionarlas por matrix.motor.
          DB_USER: ci_rls
          DB_PASSWORD: ci_rls_password_local
          DB_HOST: localhost
          DB_PORT: "5432"
```

(`services.postgres.env.POSTGRES_USER`/`POSTGRES_PASSWORD`, líneas 41-42, se
quedan exactamente como están — siguen siendo `postgres`/`postgres`, el
superusuario que arranca el contenedor y que Step 1 usa para crear `ci_rls`.)

- [ ] **Step 3: Revisar el YAML resultante a mano**

No hay linter de YAML en este repo. Releer el archivo completo
(`.github/workflows/ci.yml`) y confirmar: indentación consistente (2 espacios,
como el resto del archivo), el paso nuevo tiene `if: matrix.motor == 'postgres'`
(no `'postgresql'` — ese fue exactamente el bug que dejaba `tests_rls.py` en verde
sin haber probado RLS una sola vez, ver Revisión 5/B6 del plan), y `PGPASSWORD` va
en `env:`, nunca en el comando `psql` de la línea `run:`.

- [ ] **Step 4: Verificar corriendo el workflow de verdad**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: crea rol ci_rls sin BYPASSRLS para probar RLS de verdad en CI"
git push
```

Abrir la corrida en GitHub Actions (pestaña Actions del repo) y confirmar que el
job `backend (postgres)` pasa, específicamente el paso "Crear rol de test sin
privilegios" (sin error de `psql`) y el paso "Tests (postgres)" (sin error de
autenticación de `ci_rls`). El job `backend (sqlite)` debe seguir pasando sin
cambios — es la prueba de que dejar `DB_USER`/`DB_PASSWORD` sin condicionar por
`matrix.motor` no le afecta.

---

### Task I4: `frontend/src/lib/api.ts` — prefijo `NEXT_PUBLIC_EMPRESA_SLUG`

**Files:**
- Modify: `frontend/src/lib/api.ts:1` (declaración de `API_URL`) y `:174-194`
  (función `request`)
- Modify: `frontend/.env.example`
- Modify: `frontend/.env.local`

**Interfaces:**
- Consumes: nada del backend directamente — asume que el backend monta sus rutas
  bajo `/api/<empresa_slug>/` (tarea de la sección de tenancy/fleet/bookings/
  payments) y que `tenancy.0002_crear_sede_empresa_la_paz` crea la Empresa con
  `slug='sal-y-sol'` (mismo valor que el default de aquí).
- Produces: nada que otra tarea de esta sección consuma.

**Nota de método (por qué no hay pasos "rojo/verde" de test unitario aquí):** este
repo no tiene runner de tests de unidad en el frontend (`frontend/package.json` solo
declara `dev`/`build`/`start`/`lint`, sin `jest`/`vitest` en `devDependencies`) — la
verificación real de cambios de frontend en este proyecto es `tsc --noEmit` +
`npm run build` (decisión ya tomada del proyecto, ver memoria "Verificación sin
navegador"). Los pasos de abajo siguen ese patrón en vez de inventar un test que no
existe en el repo.

- [ ] **Step 1: Agregar la constante `EMPRESA_SLUG`**

En `frontend/src/lib/api.ts:1`, cambiar:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
```

por:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
// Mismo slug que crea `tenancy.0002_crear_sede_empresa_la_paz` en el backend.
const EMPRESA_SLUG = process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol';
```

- [ ] **Step 2: Anteponer el prefijo dentro de `request()`**

En `frontend/src/lib/api.ts:174-189` (función `request`), cambiar:

```typescript
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
```

por:

```typescript
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Cada ruta exportada de este archivo empieza con '/api/' (ver getTarifa,
  // getCupo, etc. mas abajo) — se reescribe aqui, en un solo lugar, en vez de
  // que cada funcion exportada tenga que acordarse del slug.
  const rutaConEmpresa = path.startsWith('/api/')
    ? `/api/${EMPRESA_SLUG}${path.slice(4)}`
    : path;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${rutaConEmpresa}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
```

(Ninguna de las funciones exportadas cambia: siguen llamando `request('/api/tarifa/')`,
etc. — la reescritura ocurre en el único punto de salida real, dentro de `request`.)

- [ ] **Step 3: Verificar tipos**

Run (desde `frontend/`): `npx tsc --noEmit`
Expected: sin errores.

- [ ] **Step 4: Agregar la variable a los archivos de entorno**

En `frontend/.env.example`, agregar (junto a las demás `NEXT_PUBLIC_*`):

```
# Slug de la Empresa que sirve este frontend — antepone /api/<slug>/ a cada
# llamada del backend (ver src/lib/api.ts). Mismo valor que el slug de la
# Empresa creada por tenancy.0002_crear_sede_empresa_la_paz en el backend.
NEXT_PUBLIC_EMPRESA_SLUG=sal-y-sol
```

En `frontend/.env.local`, agregar la misma línea (es el valor real que usa el dev
server local, no un placeholder — coincide con el slug real de "Sal y Sol"):

```
NEXT_PUBLIC_EMPRESA_SLUG=sal-y-sol
```

- [ ] **Step 5: Levantar el dev server y confirmar una llamada real**

Run (desde `frontend/`, con el backend corriendo en `localhost:8000` ya con el
prefijo de empresa activo — depende de la sección backend de esta pieza): `npm run dev`

Abrir `http://localhost:3000/es/reservar` y, en las herramientas de red del
navegador, confirmar que la petición a la tarifa sale como
`GET http://localhost:8000/api/sal-y-sol/tarifa/`, no `GET
http://localhost:8000/api/tarifa/`. Si el backend de esta sesión de desarrollo
todavía no tiene el prefijo montado (sección backend sin terminar), esta petición
da 404 — es la señal correcta de que el cambio de frontend ya está listo y falta el
de backend, no un error de este cambio.

- [ ] **Step 6: Build de producción**

Run (desde `frontend/`): `npm run build`
Expected: build limpio, sin errores de tipos ni de lint.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/.env.example frontend/.env.local
git commit -m "feat(frontend): antepone NEXT_PUBLIC_EMPRESA_SLUG a cada llamada de la API"
```

**Pendiente manual, fuera del repo (no parte de esta tarea, anotar para la ventana
de corte de producción — ver Task I5):** agregar `NEXT_PUBLIC_EMPRESA_SLUG=sal-y-sol`
a las variables de entorno del proyecto en Vercel y redesplegar.

---

### Task I5: `config/settings/production.py` — runbook del corte a rol único + RLS + Stripe por Empresa

**Files:**
- Create: `docs/deploy/RUNBOOK-corte-multi-empresa.md`
- Modify: `backend/CLAUDE.md` (sección "Roles: Jefes vs Vendedora" y "Panel de
  finanzas" — actualizar las referencias a `is_superuser` que esta pieza invalida;
  **Revisión 7, C3** del plan)

**Interfaces:**
- Consumes: el rol de Postgres `ci_rls` creado en Task I3 es la prueba de que el
  patrón (`FORCE ROW LEVEL SECURITY` sostiene incluso al dueño de las tablas) ya
  funciona en CI antes de repetirlo en producción.
- Produces: nada que otra tarea del código consuma — es un documento operacional,
  igual que `docs/deploy/GO-LIVE.md` y `docs/deploy/ENDURECIMIENTO.md`, que ya
  existen en este repo con el mismo propósito (pasos que solo el dueño del negocio
  puede ejecutar, contra dashboards de Render/Supabase/Stripe reales).

`config/settings/production.py` en sí **no cambia de código** — ya lee
`DB_USER`/`DB_PASSWORD`/etc. genéricos de variables de entorno sin ningún default
(`os.environ['DB_USER']`, línea 22 hoy); el trabajo de esta tarea es enteramente
operacional, con SQL y pasos exactos, no una prueba automatizada.

- [ ] **Step 1: Crear el runbook**

Crear `docs/deploy/RUNBOOK-corte-multi-empresa.md`:

```markdown
# Corte a multi-empresa — runbook de producción

Pasos que solo el dueño del negocio puede ejecutar, contra Render/Supabase/Stripe
reales. Ninguno se puede hacer desde el código. Ejecutar en este orden, en una sola
ventana — entre el paso 3 (`migrate`) y el paso 5
(`migrar_la_paz_a_empresa.py`), **todo el staff recibe 403 en el admin** (nadie
tiene `MembresiaEmpresa` todavía).

## 1. Rol de Postgres sin SUPERUSER/BYPASSRLS

En el SQL editor de Supabase, conectado como `postgres`, en este orden exacto
(`REASSIGN OWNED BY` por sí solo no basta en Postgres 15+/Supabase moderno — no
otorga `CREATE` sobre el esquema `public`, que ya no es de acceso libre):

\`\`\`sql
-- 1. El rol de aplicacion (DB_USER actual de Render) debe poder recibir el
--    ALTER TABLE de mas abajo.
GRANT <rol_app> TO postgres;

-- 2. Sin esto, el primer CREATE TABLE de tenancy.0001_initial corriendo como
--    <rol_app> falla con "permission denied for schema public".
GRANT USAGE, CREATE ON SCHEMA public TO <rol_app>;

-- 3. Acotado a las tablas/secuencias de la app — NO usar REASSIGN OWNED BY,
--    que es de alcance base-de-datos-completa y arrastra cualquier otro
--    objeto que "postgres" posea ahi.
ALTER TABLE django_migrations OWNER TO <rol_app>;
ALTER TABLE django_content_type OWNER TO <rol_app>;
ALTER TABLE django_session OWNER TO <rol_app>;
ALTER TABLE auth_user OWNER TO <rol_app>;
ALTER TABLE auth_group OWNER TO <rol_app>;
-- ... repetir para cada tabla de fleet_*/bookings_*/payments_*/tenancy_*/
-- finance_*/axes_*: SELECT tablename FROM pg_tables WHERE schemaname = 'public'
-- lista las que falten.
\`\`\`

Si la conexión de Render pasa por el pooler Supavisor (típico: Render sale por
IPv4, la conexión directa de Supabase es IPv6-only), `DB_USER` en Render lleva el
sufijo de proyecto: `<rol_app>.<project_ref>`, no el rol a secas — confirmar en
el dashboard de Supabase, pestaña Connection Pooling, cuál conexión usa
`render.yaml` antes de tocar nada.

## 2. Un solo rol en todo el pipeline

`<rol_app>` (el `DB_USER` que ya usa Render) corre `migrate` **y** gunicorn **y**
los dos crons (`pescadeportiva-conciliar-pagos`, `pescadeportiva-limpiar-checkouts`)
— no hace falta un segundo rol: `FORCE ROW LEVEL SECURITY` (ya en el código,
migración `tenancy.0003_rls`) somete también al dueño de la tabla. Es el mismo
patrón que ya corre en CI (`ci_rls`, ver Task I3) — si `tests_rls.py` pasó ahí
contra un rol que también hace `migrate`, este paso ya está probado.

## 3. Deploy

Push a `main` con el código de esta pieza. `render.yaml` corre `migrate` dentro
del `buildCommand` del servicio web — desde este punto, RLS está activo y
`empresa_id` es `NOT NULL`, pero **nadie tiene `MembresiaEmpresa` todavía**.

## 4. Verificación post-deploy obligatoria (no opcional)

Con la conexión real de la app (no como `postgres`):

\`\`\`sql
SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;
\`\`\`

Debe devolver `(false, false)`. Si devuelve cualquier otra cosa, RLS existe en la
base pero **no protege nada**, sin ningún síntoma visible desde la aplicación —
no seguir al paso 5 hasta que esto dé `(false, false)`.

## 5. Migrar cuentas — cierra la ventana de bloqueo del paso 3

Por SSH shell de Render (`pescadeportiva-api` → Shell):

\`\`\`bash
python manage.py setup_roles
python manage.py migrar_la_paz_a_empresa --operador <tu-username>
\`\`\`

(`setup_roles` primero — `migrar_la_paz_a_empresa` exige que los grupos `Jefe`/
`Vendedora`/`OperadorPlataforma` ya existan.) Confirmar que puedes entrar al
admin con tu cuenta antes de anunciar el corte como terminado — es la prueba de
que la ventana de bloqueo cerró.

## 6. Endpoint de webhook de Stripe

En el Dashboard de Stripe → Developers → Webhooks, **editar** (no crear uno
nuevo) el endpoint existente para que apunte a la ruta con el slug:
`https://pescadeportiva-api.onrender.com/api/sal-y-sol/stripe/webhook/`. Editar
conserva el mismo `whsec_`; si en vez de editar se crea uno nuevo, copiar su
`whsec_` nuevo a `Empresa.stripe_webhook_secret` en el admin (`/admin/tenancy/
empresa/`) antes de dar el corte por terminado.

## 7. Corte del frontend (misma ventana)

En Vercel, proyecto `sal-y-sol-sportfishing` → Settings → Environment Variables,
agregar `NEXT_PUBLIC_EMPRESA_SLUG=sal-y-sol` (ver Task I4) y redesplegar
(`vercel --prod` desde `frontend/`, o el redeploy del dashboard).

## 8. Limpieza de variables de Stripe en Render

Después de este corte, `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`/
`STRIPE_PUBLISHABLE_KEY` del environment group `pescadeportiva-secrets` **ya no
tienen ningún lector en el código** (`tenancy.0002_crear_sede_empresa_la_paz` las
leyó una sola vez, al crear la fila de "Sal y Sol" — de ahí en adelante las
llaves se rotan en el admin, por Empresa). Dejarlas en Render solo mientras haya
riesgo de rollback de esta pieza; después borrarlas o renombrarlas a
`STRIPE_*_BOOTSTRAP` para que quede evidente que ya no las lee nadie.

## Trade-off aceptado, declarado (no un descuido)

El rol `<rol_app>` es dueño de las tablas, así que técnicamente puede correr
`ALTER TABLE ... NO FORCE ROW LEVEL SECURITY` y desactivar la protección. La
defensa asume que nadie ejecuta SQL arbitrario contra producción con esas
credenciales fuera del código de la aplicación — aceptable a la escala actual
(2 devs), revisar si el equipo crece.
```

- [ ] **Step 2: Actualizar `backend/CLAUDE.md` — sección "Roles: Jefes vs Vendedora"**

Esta sección hoy dice *"Jefes = cuentas Django con `is_superuser=True`"* y *"Crear
cuentas de vendedora: ... agregarlo al grupo `Vendedora` y darle de alta su fila en
`bookings.Vendedora` con su código de link"* (flujo manual de tres pasos). Ambas
afirmaciones quedan invalidadas por esta pieza (jefes pasan a `MembresiaEmpresa` +
grupo `Jefe`, sin `is_superuser`; el alta de vendedora pasa a la acción unificada de
`apps/bookings/admin.py`, ver el plan). Reemplazar el contenido de esa sección
citando `MembresiaEmpresa(rol=JEFE|VENDEDORA)` y la acción "Dar de alta vendedora"
como flujo único, en vez del procedimiento manual de tres pasos.

- [ ] **Step 3: Actualizar `backend/CLAUDE.md` — sección "Panel de finanzas"**

Esta sección hoy dice *"Solo superusuarios: la vista corta con `is_superuser`"*.
Reemplazar por la regla nueva: visible para el operador de plataforma (ve todas las
Empresas) o para cualquier usuario con `MembresiaEmpresa` en una Empresa (ve la
suya) — ver Task I1, permiso de "Finanzas" en `UNFOLD['SIDEBAR']`.

- [ ] **Step 4: Commit**

```bash
git add docs/deploy/RUNBOOK-corte-multi-empresa.md backend/CLAUDE.md
git commit -m "docs: runbook de produccion para el corte a multi-empresa y actualiza CLAUDE.md"
```

Este runbook se ejecuta manualmente, una sola vez, en la ventana real de corte —
no antes de que el resto de las secciones del plan (tenancy core, fleet, bookings,
payments/finance) estén completas y con CI en verde.

---

## Self-Review de esta sección

**Cobertura de las filas del File Map en alcance:** `config/settings/base.py` (I1),
`config/urls.py` (I2, no-op documentado), `.github/workflows/ci.yml` +
`config/settings/ci.py` (I3), `frontend/src/lib/api.ts` (I4),
`config/settings/production.py` (I5, runbook). Las cinco filas de esta sección están
cubiertas — ninguna quedó fuera.

**Placeholders:** ninguno — cada paso trae código/SQL/YAML real, sin "TODO" ni
"agrega lo que corresponda". El único punto explícitamente marcado como fuera de
esta tarea es el redeploy de Vercel (Task I4, nota final) y los pasos 6-8 del
runbook (Task I5) — ambos son acciones humanas contra dashboards de terceros, no
código, documentadas con el comando/ruta exacta, igual que
`docs/deploy/ENDURECIMIENTO.md` ya hace en este repo.

**Consistencia de tipos/nombres:** `scope.es_operador_plataforma`/
`scope.empresa_actual` usados igual en I1 que en el resto del plan (File Map,
sección "Accesores nombrados"). `EMPRESA_SLUG`/`NEXT_PUBLIC_EMPRESA_SLUG` con el
mismo valor de default (`'sal-y-sol'`) en I4 y en la fila de
`tenancy.0002_crear_sede_empresa_la_paz` del File Map. `ci_rls` es el mismo nombre
de rol en la Parte A y la Parte B de I3, y el mismo que el runbook de I5 usa como
referencia de que el patrón ya está probado.

**Orden de ejecución real:** I1 y I3-Parte-A dependen de que el esqueleto de
`apps/tenancy` ya exista (ver nota de dependencia dura al inicio del archivo) — se
listan en este orden porque así lo pidió el encargo, pero el ejecutor debe correr
primero la sección de tenancy core. I5 depende de que todas las demás secciones
del plan estén completas y en verde en CI antes de ejecutarse contra producción
real — es la última tarea de todo el plan, no solo de esta sección.
