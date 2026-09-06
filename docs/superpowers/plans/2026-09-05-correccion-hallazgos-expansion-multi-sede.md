# Plan de corrección — Hallazgos de la revisión de piezas 1-6 (expansión multi-sede)

Fecha de creación: 2026-09-05
Rama de trabajo: `fix/expansion-multi-sede-hallazgos` (desde `feature/pieza6-frontend-multitenant` @ `491f337`)
Origen: revisión integral de la implementación del agente de Antigravity de las 6 piezas.
Documentos base: `docs/superpowers/specs/2026-08-31-expansion-multi-sede-design.md` y `...-ADRs.md`.

## Decisiones del dueño (2026-09-05, antes de arrancar)

1. **Alcance:** todo, incluido el re-cableado del checkout público para servicios / paquetes / hospedaje.
2. **Hospedaje:** es necesidad de v1. Cablear el flujo multidía completo.
3. **Paquetes cruza-empresa:** resolver el caso ahora (diseño + código). Se escribe ADR-005.
4. **Verificación:** Postgres en Docker en local. La suite completa (RLS, locks, constraints) debe correr verde localmente antes de dar por cerrada cada sección.

## Cómo retomar esto en otra sesión

1. Leer este archivo completo y la memoria `plan-correccion-hallazgos`.
2. `git checkout fix/expansion-multi-sede-hallazgos` (o el worktree en `.claude/worktrees/pieza1-tenancy-sdd`).
3. Mirar el **Registro de avance** al final: dice la última tarea cerrada y la siguiente.
4. Levantar Postgres local (ver Sección 0) antes de tocar cupo, RLS o pagos.
5. Un commit por tarea. Mensaje: `fix(<área>): <qué> [plan H<sección>.<tarea>]`. Prosa normal, español, terminar con las líneas de atribución de la sesión.
6. Al cerrar una tarea, marcar `[x]` aquí y actualizar el Registro de avance + la memoria.

## Convenciones

- **Núcleo puro primero, adaptador después, wiring al final.** Igual que el código existente.
- **TDD donde se pueda:** test que falla → código → verde. Tests de RLS / concurrencia / constraints van marcados `# postgres-only`.
- **Nada de cifras ni lógica de dinero fuera de `apps/payments/pricing.py`** (garantía de `backend/CLAUDE.md` que no se rompe).
- **RLS es fail-closed:** ninguna ruta nueva debe depender solo del filtro del ORM. Si hace falta cruzar empresas, es con `con_empresa` iterado o función `SECURITY DEFINER` explícita y auditada, nunca `como_operador_plataforma()` en ruta pública.
- Si una tarea destapa una decisión de producto no prevista aquí: parar, anotarla en "Preguntas abiertas" al final, y preguntar.

---

## Sección 0 — Preparación y línea base

- [ ] **0.1** Rama `fix/expansion-multi-sede-hallazgos` creada desde `feature/pieza6-frontend-multitenant`. (HECHO al crear el plan.)
- [ ] **0.2** Manual del dueño: arrancar Docker Desktop. Verificar con `docker ps`.
- [ ] **0.3** Levantar Postgres local para pruebas:
  ```
  docker run -d --name psd-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=pescadeportiva_test -p 5432:5432 postgres:17
  docker exec psd-pg psql -U postgres -d pescadeportiva_test -v ON_ERROR_STOP=1 -c \
    "CREATE ROLE ci_rls LOGIN PASSWORD 'ci_rls_password_local' NOSUPERUSER NOBYPASSRLS CREATEDB;"
  ```
- [ ] **0.4** Documentar en `backend/CLAUDE.md` (sección nueva "Correr los tests contra Postgres en local") el bloque de arriba + las env vars (`DJANGO_SETTINGS_MODULE=config.settings.ci DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5432`).
- [ ] **0.5** Correr la suite base y anotar el resultado exacto en el Registro de avance:
  - sqlite: `venv/Scripts/python.exe manage.py test apps config`
  - postgres: mismo con `DJANGO_SETTINGS_MODULE=config.settings.ci` + env vars.
- [ ] **0.6** Frontend base: `npm.cmd run lint`, `npx.cmd tsc --noEmit`, `npm.cmd run build`. Anotar.
- [ ] **0.7** Commit del plan + los ajustes de doc (`docs(plan): plan de corrección de hallazgos`).

---

## Sección 0.8 — Retrofit de la suite de tests para RLS (bloqueante, descubierto en 0.5)

**Hallazgo (2026-09-05):** el baseline en Postgres NO estaba verde. Dos causas:

1. La migración `fleet/0018_crear_servicio_la_paz` reventaba en Postgres bajo un
   rol `NOBYPASSRLS` (finding M2 — arreglado, ver 8.1 movido aquí como 0.8.1).
2. **~95 tests de las apps `fleet`/`bookings`/`payments`/`finance`/`tenancy`
   crean filas tenant-scoped sin abrir `con_empresa`** — pasan en sqlite (sin
   RLS) y revientan en Postgres con «new row violates row-level security
   policy». El "Bloque 8" del plan de Pieza 1 (retrofit de tests, ver memoria
   `plan-pieza1-tenancy-pausado`) nunca se hizo en esta rama; el retrofit de
   `e8566be` fue parcial y jamás se validó contra Postgres.

Sin esto verde, ningún test de RLS / concurrencia / constraint de las secciones
siguientes prueba nada. Va antes que todo lo demás.

- [x] **0.8.1** `fleet/0018`: envolver los writes ORM en
  `apps.tenancy.rls.alcance_operador_migracion(schema_editor.connection)`.
  (HECHO.)
- [ ] **0.8.2** `apps/testing.py::crear_flota`: envolver `bulk_create` en
  `with scope.con_empresa(empresa)`. Es el helper que más setUp usan.
- [ ] **0.8.3** `apps/testing.py`: revisar `crear_jefe`/`crear_vendedora` y
  cualquier otro helper que escriba en tablas con RLS.
- [ ] **0.8.4** `fleet/tests.py`: las clases que crean `Embarcacion`/`Tarifa`/
  `ExtrasItem`/`TransportePrecio`/`CodigoPromocional` sin scope
  (`EmbarcacionTests`, `TarifaTests`, `ExtrasItemTests`, `TransportePrecioTests`,
  `CodigoPromocionalTests`, `CapacidadesDisponiblesTests`, `EmpresaFKTests` no,
  `UnicidadPorEmpresaTests`, `EmbarcacionNoDisponibleUnicidadTests`, ...) →
  helper local `crear_en(empresa, Modelo, **kw)` o `with scope.con_empresa`.
  Las de aislamiento A/B ya lo hacen bien parcialmente — completar.
- [ ] **0.8.5** `bookings/tests_tenancy.py`: `datos_reserva()` y los `setUp` que
  llaman `crear_flota` / crean `Reserva` fuera de scope.
- [ ] **0.8.6** `bookings/tests_ocupacion.py`, `tests_reserva_paquete.py`,
  `tests_concurrencia.py`: mismo patrón.
- [ ] **0.8.7** `fleet/tests_paquetes.py`, `tests_paquetes_api.py`,
  `tests_servicios_api.py`, `tests_catalogo_rls.py`: convertir a
  `EmpresaTestCase` / `ApiTestCase` o wrapper de scope. Ojo: los tests de las
  rutas por Sede ahora recorren varias Empresas — el `setUp` debe crear cada
  Empresa y sus filas en su propio `con_empresa`.
- [ ] **0.8.8** `payments/tests_pricing_paquete.py`, `payments/tests.py`
  (`CrearPagoTests.test_reserva_con_servicio_de_otra_empresa_falla_clean`),
  `finance/tests.py` (`test_sin_empresa_suma_todas`), `tenancy/tests.py`
  (`EmpresaScopedAdminMixinTests`, `MigrarLaPazAEmpresaTests`).
- [ ] **0.8.9** Considerar un helper central `apps/testing.py::crear(empresa, Modelo, **kw)`
  y/o migrar clases a `EmpresaTestCase` en masa donde no prueben aislamiento A/B.
- [ ] **0.8.10** Suite Postgres completa verde (`test apps config`). Ese es el
  baseline real. Commit `test: retrofit de la suite para RLS en Postgres (Bloque 8)`.
- [ ] **0.8.11** Verificar los 2 FAIL (no ERROR) del baseline —
  `finance.tests.test_sin_empresa_suma_todas` (2000≠3000) y
  `tests_concurrencia.test_dias_distintos_no_se_bloquean_entre_si`
  ([None,None]≠[aplicado,aplicado]) — pueden ser cascada de los ERROR de setUp o
  bugs reales. Diagnosticar una vez el resto esté verde.

## Sección 1 — CRÍTICO: seguridad del aislamiento (C1, C2)

### C1 — RLS inerte si el rol de BD tiene BYPASSRLS/superuser

- [ ] **1.1** Núcleo: función `apps/tenancy/rls.py::rol_actual_es_seguro(connection) -> tuple[bool, dict]` que corre `SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user` y devuelve si el rol NO es super y NO tiene bypass. No-op / True en sqlite.
- [ ] **1.2** System check `apps/tenancy/checks.py::revisar_rol_rls` registrado con `@register(Tags.database)`:
  - En sqlite → no reporta nada.
  - En Postgres con rol super/bypass → `Warning tenancy.W001` en `local`/`ci`, **`Error tenancy.E001` cuando `DEBUG=False`** (producción). Mensaje sin credenciales, con hint que apunta al RUNBOOK.
  - Envuelto en `try/except DatabaseError` (corre en `collectstatic`/`migrate` antes de que exista conexión utilizable).
- [ ] **1.3** Test `apps/tenancy/tests_rls.py`: `# postgres-only` — con `ci_rls` el check pasa; simular (mock del fetch) un rol con bypass y ver que sale `E001` con `DEBUG=False`.
- [ ] **1.4** `docs/deploy/RUNBOOK-corte-multi-empresa.md`: sección "Rol de aplicación de Supabase/Render" — crear rol `app_pesca NOSUPERUSER NOBYPASSRLS`, `GRANT`s mínimos, apuntarlo en `DB_USER`. Paso obligatorio de go-live.
- [ ] **1.5** Memoria `pendientes-manuales-produccion`: añadir "crear rol de BD sin BYPASSRLS y ponerlo en `DB_USER` de Render — sin esto RLS no protege nada".

### C2 — endpoints públicos con `como_operador_plataforma()` (bypass de RLS)

- [ ] **1.6** Decisión de enfoque (documentar 2 líneas en el commit): reemplazar el bypass por una **función Postgres `SECURITY DEFINER`** `catalogo_sede(sede_id)` que devuelve solo filas activas de empresas activas de esa sede, o por **iteración de `con_empresa` por cada empresa de la sede**. Recomendado: iteración de scopes (sin SQL nuevo, más simple de auditar; la sede tiene pocas empresas).
- [ ] **1.7** `fleet/views.py::PaquetesPorSedeListView`: quitar `como_operador_plataforma()`. Nuevo: resolver empresas de la sede (`Empresa.objects.filter(sede=sede, activo=True)` — tabla sin RLS, ok), y por cada una `with con_empresa(empresa): recolectar sus paquetes liderados`. Unir y serializar. Los paquetes cuyo `empresa_lider` es esa empresa.
- [ ] **1.8** `fleet/views.py::ServiciosPorSedeListView`: igual — iterar empresas de la sede, cada una en su scope, recolectar `Servicio` activos.
- [ ] **1.9** Revisar `PaqueteSerializer` / `ServicioSerializer`: que ningún campo anidado dispare un query fuera del scope activo. Si un paquete cruza-empresa referencia servicios de otra empresa (Sección 7), ese serializer necesita su propio manejo — dejar `TODO` marcado y coordinar con 7.4.
- [ ] **1.10** `throttle_scope` en las 6 vistas nuevas de catálogo (`SedesListView`, `ServiciosListView`, `ServicioDetailView`, `PaquetesPorEmpresaListView`, `PaquetesPorSedeListView`, `ServiciosPorSedeListView`) + rates en `config/settings/base.py` `DEFAULT_THROTTLE_RATES` (`catalogo: '120/min'` o lo que encaje con los demás).
- [ ] **1.11** Tests `fleet/tests_servicios_api.py` / `tests_paquetes_api.py`: `# postgres-only` — crear 2 empresas en la misma sede con data cada una; el endpoint de sede devuelve las dos; **ninguna respuesta incluye filas de una empresa `activo=False`**; con RLS real (rol `ci_rls`) el endpoint no filtra de más ni de menos.
- [ ] **1.12** Commit `fix(seguridad): rutas de catálogo por sede sin bypass de RLS + check de rol de BD`.

---

## Sección 2 — Núcleo de cupo: correctitud (M1, M3, M5)

- [ ] **2.1** `bookings/cupo/nucleo.py`:
  - `rango_traslapa`: un rango con `ini >= fin` sigue devolviendo `False`, pero añadir helper `validar_rango(ini, fin)` que exige `fin > ini` y lo usan los callers de modelo.
  - `ocupacion_por_rango`: default de `tope` pasa de `0` a `None`; con `tope is None` no aplica límite de conteo (solo capacidad). Ajustar `motivo_sin_lugar` para tratar `tope=None` como "sin tope".
  - Tests en `tests_cupo_nucleo.py`.
- [ ] **2.2** `Servicio`: convertir los 4 campos string a enums `TextChoices` con las claves reales:
  - `tipo_servicio`: `PESCA, PASEO, HOSPEDAJE, BAJO_DEMANDA` (o el set que confirme el dueño — ver Preguntas abiertas si aparecen más).
  - `estrategia_cupo`: `POR_RECURSO_DIA, POR_NOCHE, BAJO_DEMANDA`.
  - `estrategia_precio`: `POR_GRUPO, POR_PERSONA, TARIFA_FIJA, POR_NOCHE`.
  - `modo_ocupacion`: `EXCLUSIVO, COMPARTIDO`.
  - Migración de datos que normaliza lo sembrado por `0018` (`'por_recurso_dia'` etc. ya coincide con las claves nuevas si se eligen esos valores).
- [ ] **2.3** `bookings/cupo/registro.py`: el registro se llavea por `estrategia_cupo` (no por `tipo_servicio`). Claves alineadas con el enum de 2.2. `obtener_estrategia(clave)` con default explícito y **log de warning** cuando cae al default por clave desconocida (hoy es silencioso).
- [ ] **2.4** `bookings/models.py::Reserva.clean` y `evaluar_cupo`/`validar_cupo_diario`/`disponibilidad_por_fecha`: resolver la estrategia con `servicio.estrategia_cupo` (default `POR_RECURSO_DIA` cuando `servicio` es None = pesca legacy). `tipo_servicio` deja de decidir cupo; queda como etiqueta de presentación.
- [ ] **2.5** `bookings/cupo/candado.py`:
  - `calcular_clave_candado`: espacio de claves separado por prefijo. `('default', fecha)` → `fecha.toordinal()` (compat pesca intacta). Cualquier otro ámbito → `crc32(f'ambito:{ordinal}') | 0x40000000` (bit alto que el ordinal nunca alcanza en fechas realistas) para que **no pueda colisionar** con el path default.
  - `bloquear_cupo`: firma `(empresa_id, fecha, ambito)` donde `ambito` ahora es `servicio_id` real (no `tipo_servicio`), o `'default'` para pesca legacy.
  - Tests `tests_cupo_candado.py`: `# postgres-only` — dos ámbitos distintos no se bloquean entre sí; default y ámbito nunca colisionan.
- [ ] **2.6** Ajustar todos los call sites de `bloquear_cupo` / `evaluar_cupo` / `validar_cupo_diario` (grep) para pasar `servicio_id`.
- [ ] **2.7** Suite verde (sqlite + postgres). Commit `fix(cupo): estrategia por servicio, lock re-llaveado sin colisión, núcleo endurecido`.

---

## Sección 3 — Modelo de datos de hospedaje (A4, parte de datos)

- [ ] **3.1** Migración `bookings/xxxx_ocupacion_exclude.py`:
  - `CREATE EXTENSION IF NOT EXISTS btree_gist;` (guard vendor postgres).
  - `ALTER TABLE bookings_reservaocupacion ADD CONSTRAINT ocupacion_sin_traslape EXCLUDE USING gist (recurso_id WITH =, daterange(fecha_inicio, fecha_fin, '[)') WITH &&) WHERE (...)` — el `WHERE` limita a ocupaciones cuya reserva ocupa cupo. Como el estado vive en `bookings_reserva`, no en la fila de ocupación, el `WHERE` no puede referenciarlo directo: **añadir columna denormalizada `ocupa_cupo` (bool) a `ReservaOcupacion`**, mantenida por señal / `save()` de `Reserva` cuando cambia de estado, y el `EXCLUDE ... WHERE (ocupa_cupo)`.
  - Reversible.
- [ ] **3.2** `ReservaOcupacion`: campo `ocupa_cupo = BooleanField(default=True, db_index=True)`. `Reserva.save()` (o señal `post_save`) actualiza `ocupaciones.update(ocupa_cupo=<estado in ESTADOS_QUE_OCUPAN_CUPO>)` cuando el estado cambia. Cubrir transición pagada→cancelada (libera) y pendiente→pagada (ocupa).
- [ ] **3.3** `ReservaOcupacion.clean()`: acotar el query de overlap por `empresa_id`, por `fecha_inicio__lt / fecha_fin__gt` (no traer todo el histórico del recurso), y por `ocupa_cupo=True`. Sigue siendo la red de seguridad a nivel app; el constraint es la garantía dura.
- [ ] **3.4** Índice `(recurso_id, fecha_inicio, fecha_fin)` para el query anterior.
- [ ] **3.5** `bookings/cupo/candado.py::bloquear_recurso(empresa_id, recurso_id)` — advisory lock keyed `(empresa_id, crc32('recurso:'+recurso_id) | 0x40000000)`. Se toma antes de evaluar/crear ocupaciones multidía.
- [ ] **3.6** Tests `tests_ocupacion.py`: `# postgres-only` — el constraint rechaza dos ocupaciones traslapadas del mismo recurso; checkout el mismo día (`[a,b)` y `[b,c)`) sí se permite; una reserva cancelada libera el rango (baja `ocupa_cupo`, otra reserva puede tomarlo).
- [ ] **3.7** Commit `fix(hospedaje): constraint EXCLUDE anti-traslape + lock por recurso`.

---

## Sección 4 — Precio: paquete y noches (A2, A5, B7)

- [ ] **4.1** `apps/payments/pricing.py`: `calcular_precio_paquete` ya existe. Añadir tope: nueva función `precio_paquete` valida que `suma_ajustes <= precio_ancla` (ya tiene piso 0; añadir aviso/log si un ajuste individual > ancla o si la suma la supera). Sin cambiar la firma.
- [ ] **4.2** `fleet/models.py::Paquete.clean()` o `PaqueteServicio.clean()`: validar `Σ ajuste_precio de servicios removibles <= precio_ancla` (y el `_usd` correspondiente). Error de admin claro.
- [ ] **4.3** `apps/payments/views.py::CrearPagoView._post`: rama nueva **antes** de la de `reserva.servicio` / `Tarifa`:
  ```
  if reserva.paquete_id:
      removidos = list(reserva.servicios_removidos.values_list('servicio_id', flat=True))  # ver 5.x
      precio_base_servicio = calcular_precio_paquete(reserva.paquete, removidos, reserva.moneda)
      if precio_base_servicio is None: return 503 (sin precio en esa moneda)
  ```
  Extras/transporte/promoción siguen sumándose igual sobre ese `precio_base_servicio` (confirmar con el dueño si un paquete admite extras sueltos — ver Preguntas abiertas).
- [ ] **4.4** `CrearPagoView`: `DemandaPrecio(personas=..., moneda=..., noches=reserva.noches)` — pasar noches. `reserva.noches` sale de `fecha_salida` (Sección 5).
- [ ] **4.5** `apps/payments/services.py::_verificar_monto`: recomputar el esperado cubriendo el path paquete (misma función `calcular_precio_paquete`). Sigue sin rebotar, solo registra descuadre.
- [ ] **4.6** Tests `tests_pricing_paquete.py` + `tests_pricing_estrategias.py`: paquete con 0 / 1 / N servicios removidos; `por_noche` con 1 / 3 noches; el webhook no marca descuadre cuando el precio es correcto.
- [ ] **4.7** Commit `fix(precio): checkout cobra paquete por ancla y hospedaje por noches`.

---

## Sección 5 — Checkout: serializer + API (A1, A3, B2)

- [ ] **5.1** Modelo para la selección de componentes removidos de un paquete: tabla `ReservaPaqueteServicioRemovido(reserva FK, servicio FK)` con `unique_together`, RLS por `reserva.empresa` (política EXISTS como `bookings_reservaextra`). Migración + política.
- [ ] **5.2** `ReservaCheckoutSerializer.Meta.fields`: añadir `servicio` (slug, `SlugRelatedField` filtrado por empresa vía `get_fields` como ya se hace con extras), `paquete` (slug, filtrado por sede + `empresa_lider`), `fecha_salida`, `servicios_removidos` (lista de slugs de servicio, write_only).
- [ ] **5.3** `ReservaCheckoutSerializer.validate`:
  - `fecha_salida` obligatoria y `> fecha` **si** el servicio/paquete es multidía (`estrategia_cupo == POR_NOCHE`); prohibida si no lo es.
  - `servicio` y `paquete` mutuamente excluyentes (o definir precedencia — ver Preguntas abiertas).
  - `servicios_removidos ⊆` los `PaqueteServicio` `removible=True` del paquete.
  - `numero_personas` contra el `personas_incluidas` / capacidad del servicio, no solo `MAX_PERSONAS` de pesca.
- [ ] **5.4** `ReservaCheckoutSerializer.create/update`: persistir `servicio`, `paquete`, `fecha_salida`, y sincronizar `servicios_removidos` (borra+recrea como extras).
- [ ] **5.5** `Reserva.clean()`: para servicio/paquete multidía, en vez de `validar_cupo_diario` de un día → `bloquear_recurso` + `evaluar_disponibilidad_hospedaje(check_in, check_out, personas, empresa, servicio, ...)`. Si no cabe → `ValidationError`. **No** crea `ReservaOcupacion` aquí (eso es Sección 6, al confirmar el pago).
- [ ] **5.6** Endpoint `GET /api/sedes/<sede_slug>/paquetes/<slug>/` (`PaqueteDetailView`) para resolver slug→objeto de una vez. Mismo patrón de scopes sin bypass que 1.7.
- [ ] **5.7** Frontend `reservar/page.tsx`: reemplazar el waterfall `getSedes()`+loop por `getPaqueteDetalle(sedeSlug, paqueteSlug)`. `sedeSlug` viene en el query (`?sede=`).
- [ ] **5.8** Frontend `api.ts`: `ReservaInput` gana `servicio?`, `fecha_salida?`, `servicios_removidos?`; `guardarReserva` los manda. `MotivoNoDisponible` += `'sin_lugar'`.
- [ ] **5.9** Frontend `checkout-view.tsx`: pasar la selección de componentes removidos (de `paquete-card` / query) a `guardarReserva`. El "ahorro" mostrado y el enviado deben coincidir.
- [ ] **5.10** Tests: serializer acepta/rechaza las combinaciones; `Reserva.clean` multidía valida contra ocupaciones; API de detalle de paquete.
- [ ] **5.11** Commit `fix(checkout): serializer y API aceptan servicio, paquete, fecha_salida y componentes removidos`.

---

## Sección 6 — Confirmación de pago crea la ocupación (A3, A4 wiring)

- [ ] **6.1** `apps/payments/services.py::aplicar_pago_exitoso`: tras marcar `PAGADA` y antes del `on_commit`, si la reserva es de un servicio/paquete con recurso finito multidía:
  - `bloquear_recurso(empresa_id, recurso_id)` para cada recurso candidato (o lock por servicio).
  - Re-evaluar `evaluar_disponibilidad_hospedaje`. Si ya no cabe → `_cancelar_sin_cupo` (reembolso 100%, misma rama que pesca).
  - Si cabe → elegir recurso(s) concreto(s) y crear las filas `ReservaOcupacion` (`fecha_inicio=fecha`, `fecha_fin=fecha_fin_servicio`, `ocupa_cupo=True`) dentro de la misma transacción. El constraint `EXCLUDE` es la última red.
- [ ] **6.2** Selección de recurso: función pura en el núcleo `elegir_recursos(libres, personas, cantidad)` — el más chico que cabe, o combinación para `cantidad_recursos > 1`. Determinista y testeable.
- [ ] **6.3** Cancelación / reembolso (`_cancelar_sin_cupo`, `_cancelar_codigo_promocional_invalido`, acción de admin "Cancelar por mal clima", `charge.refunded`): al pasar a `CANCELADA`, `Reserva.save()` baja `ocupa_cupo` de sus ocupaciones (cubierto por 3.2) — verificar con test explícito.
- [ ] **6.4** `manage.py revisar_cupo` y `conciliar_pagos`: sin cambio funcional, pero añadir test de que una reserva de hospedaje conciliada crea su ocupación igual que el webhook.
- [ ] **6.5** Admin: `ReservaOcupacionInline` en `ReservaAdmin` pasa a mayormente solo-lectura para reservas ya pagadas (la ocupación la pone el sistema); dejar editable solo para reservas manuales `pendiente_pago` / WhatsApp.
- [ ] **6.6** Tests `tests_ocupacion.py` / `tests.py` (payments): `# postgres-only` — dos reservas de hospedaje pagando el último cuarto en paralelo: una queda `PAGADA` con ocupación, la otra `CANCELADA + reembolsada`. Reembolso libera el rango.
- [ ] **6.7** Commit `fix(hospedaje): el pago confirma y reserva el recurso multidía, con reembolso si se llenó`.

---

## Sección 7 — Paquetes cruza-empresa (M6)

- [ ] **7.1** Escribir `docs/superpowers/specs/2026-09-05-expansion-multi-sede-ADR-005-paquetes-cruza-empresa.md`:
  - Cobro: `empresa_lider` cobra el total con su cuenta Stripe (ADR-002/004, sin Connect). El reparto a las otras empresas se liquida **fuera del sistema**, igual que la comisión de vendedora y el % de plataforma. El sistema solo registra la atribución.
  - Cupo de componentes de otras empresas: al confirmar el paquete, cada componente valida y reserva cupo **en el scope de su propia empresa** (`con_empresa(componente.empresa)`), con su propio lock. Si cualquier componente no tiene cupo → se cae todo el paquete → reembolso 100% desde `empresa_lider`.
  - Lectura del catálogo cruza-empresa: iteración de scopes (Sección 1), no bypass.
  - Qué pasa si una empresa componente está `activo=False`: el paquete no se puede vender (se filtra del catálogo).
- [ ] **7.2** `fleet/models.py::PaqueteServicio`: quitar la regla que obliga misma empresa; mantener "misma **sede**" (ya está). Añadir property `empresa` = `servicio.empresa`. `Paquete.clean`: al menos un componente debe ser de `empresa_lider` (el líder tiene que aportar algo), salvo que el dueño diga lo contrario.
- [ ] **7.3** `ReservaPaqueteComponente` (tabla nueva) o reutilizar `ReservaOcupacion` + `servicio`: registrar, por reserva de paquete, qué componente pertenece a qué empresa y su cupo/ocupación. Decidir el modelo mínimo. Cada fila con `empresa_id` del componente y RLS por esa empresa.
- [ ] **7.4** `aplicar_pago_exitoso` para paquete: loop por componente:
  - `with con_empresa(comp.empresa): bloquear + evaluar + crear ocupación/cupo`.
  - Todo o nada: si un componente falla, revertir (la transacción externa hace rollback) y `_cancelar_sin_cupo` con reembolso desde `empresa_lider`.
  - Cuidado con `SET LOCAL` anidado: `con_empresa` no es reentrante con valor distinto — hay que **salir** del scope del líder antes de entrar al del componente. Rediseñar el bloque para abrir cada scope de forma secuencial, no anidada, o usar un helper que haga `SET LOCAL` puntual por consulta.
- [ ] **7.5** `_notificar` / notificaciones: el cliente recibe un correo; las empresas componentes ¿reciben aviso? (memoria `recordatorios-manuales` dice que los avisos de asignación se mandan a mano — probablemente aplica igual). Confirmar en Preguntas abiertas.
- [ ] **7.6** Serializers de catálogo: un `PaqueteSerializer` que arma la vista del paquete leyendo cada componente en su scope (o precomputando en la vista con la iteración de 1.7). Sin N+1 cross-scope descontrolado.
- [ ] **7.7** Campo de atribución: `Paquete` o `PaqueteServicio` con `porcentaje_plataforma` / nota de liquidación, solo visible para el operador de plataforma (como la comisión). Confirmar si hace falta en v1 o es post-lanzamiento.
- [ ] **7.8** Tests `tests_paquetes.py`: `# postgres-only` — paquete con componentes de empresa A (líder) y B; el pago crea ocupación en ambos scopes; si B no tiene cupo, todo se reembolsa; el catálogo de sede muestra el paquete solo si A y B están activas.
- [ ] **7.9** Commit `feat(paquetes): soporte cruza-empresa con cobro por líder y cupo por componente (ADR-005)`.

---

## Sección 8 — MEDIO / BAJO restantes

- [ ] **8.1** (M2) `apps/tenancy/migrations/_helpers.py::con_alcance_operador(schema_editor)` — context manager que emite `SET LOCAL app.operador_plataforma='on'` en Postgres, no-op en sqlite. Envolver los writes ORM de `fleet/0018` y cualquier data migration futura. Nota en `backend/CLAUDE.md`.
- [ ] **8.2** (M4) `config/settings/base.py`: sacar `from apps.tenancy import scope` del cuerpo del módulo; los lambdas de `UNFOLD['SIDEBAR']` importan `scope` perezosamente dentro del lambda (`lambda request: __import__('apps.tenancy.scope', fromlist=['es_operador_plataforma']).es_operador_plataforma(request.user)` o un helper en un módulo aparte que sí se pueda importar tarde).
- [ ] **8.3** (B3) Ya cubierto en 5.8 (frontend `MotivoNoDisponible`). Verificar que `catalogo/page.tsx` y el calendario manejan `'sin_lugar'`.
- [ ] **8.4** (B4) `fleet/models.py::Tarifa.save`: usar `update_or_create` real o `select_for_update` sobre la fila de esa empresa; evitar el race de dos `create(empresa=X)`.
- [ ] **8.5** (B5) `apps/tenancy/admin_mixins.py::EmpresaScopedUserAdminMixin`: para jefe (no operador), además de ocultar `is_superuser/groups/user_permissions`, hacer `password` y `email` de solo-lectura sobre usuarios que no sean él mismo. O directamente: jefe solo puede `is_active`.
- [ ] **8.6** (B6) `PaquetesPorSedeListView`: `get_object_or_404(Sede, slug=sede_slug, activo=True)`.
- [ ] **8.7** (B8) `apps/tenancy/tests_rls.py`: la lista consolidada de tablas con RLS incluye `fleet_servicio`, `fleet_recurso`, `fleet_personalizacion`, `fleet_serviciopersonalizacion`, `fleet_paquete`, `fleet_paqueteservicio`, `bookings_reservaocupacion`, `bookings_reservapaqueteservicioremovido` (5.1) y las de Sección 7. Test que falla si una tabla con `empresa_id`/`empresa_lider_id` no tiene política.
- [ ] **8.8** Commit `fix(varios): migraciones con alcance de operador, settings sin import temprano, endurecimiento de admin`.

---

## Sección 9 — Cierre y verificación

- [ ] **9.1** Suite completa verde en Postgres (Docker) y en sqlite: `manage.py test apps config`.
- [ ] **9.2** `manage.py check --deploy --fail-level WARNING` con settings de producción.
- [ ] **9.3** Frontend: `lint`, `tsc --noEmit`, `build` verdes.
- [ ] **9.4** Repasar diffs de todas las secciones por fugas: ningún `como_operador_plataforma()` en ruta con `permission_classes` vacío; ningún filtro de empresa olvidado; ninguna cifra fuera de `pricing.py`.
- [ ] **9.5** Actualizar `backend/CLAUDE.md` (cupo por servicio, hospedaje, paquetes cruza-empresa, tests contra Postgres), `frontend/CLAUDE.md` (nuevos campos del checkout), `docs/deploy/RUNBOOK-corte-multi-empresa.md` (rol de BD).
- [ ] **9.6** Actualizar `docs/superpowers/specs/...-ADRs.md`: ADR-003/004 pasan de PROPUESTO a ACEPTADO/IMPLEMENTADO con nota de las desviaciones; enlazar ADR-005.
- [ ] **9.7** Memoria: marcar el plan como completado, mover lo que quede a `pendientes-manuales-produccion`, actualizar `plan-pieza1-tenancy-pausado` / `cola-de-trabajo` según corresponda.
- [ ] **9.8** Resumen para el dueño: qué cambió, qué migraciones corren en producción y en qué orden, qué pasos manuales quedan (rol de BD, `btree_gist`, sembrar servicios/recursos/paquetes reales).
- [ ] **9.9** Decidir integración de la rama (`superpowers:finishing-a-development-branch`): merge a `feature/pieza6-frontend-multitenant` o PR.

---

## Preguntas abiertas (llenar cuando aparezcan; parar y preguntar si bloquean)

- ¿Un paquete admite extras sueltos (brunch, transporte) encima del ancla, o el ancla es todo?
- ¿`servicio` y `paquete` en la misma reserva: excluyentes, o un paquete "es" un servicio contenedor?
- Set exacto de `tipo_servicio` de v1 (¿seasafari, ballenas, tiburón ballena, islas, snorkel como valores separados, o todos `PASEO`?).
- ¿Las empresas componentes de un paquete reciben algún aviso automático, o todo manual como los avisos de asignación?
- ¿El % de plataforma / atribución de liquidación cruza-empresa se registra en v1 o es post-lanzamiento?
- ¿Hospedaje cobra anticipo 30% igual que pesca, o 100% por adelantado?

---

## Registro de avance

Formato: `<fecha> — <sección.tarea> — <estado> — <nota / SHA>`.

- 2026-09-05 — Plan creado. Rama `fix/expansion-multi-sede-hallazgos` desde `491f337`.
- 2026-09-05 — 0.2-0.6: Docker + Postgres 5433 + rol `ci_rls` listos (`docker: psd-pg`). Baseline: **sqlite VERDE (exit 0)**; **Postgres ROJO** — migración `fleet/0018` reventaba (M2) y, tras arreglarla, **671 tests / 2 FAIL / 95 ERROR**, casi todos "test crea fila tenant sin `con_empresa`" (Bloque 8 de Pieza 1 nunca hecho). Frontend `lint`+`tsc` verdes.
- 2026-09-05 — 0.8.1 HECHO: `fleet/0018` envuelto en `alcance_operador_migracion` (`apps/tenancy/rls.py` nuevo). Migración Postgres pasa.
- 2026-09-05 — Commits en `fix/expansion-multi-sede-hallazgos`:
  - `880d0c4` fix(tenancy): C1 (system check `revisar_rol_rls` bloquea deploy si el rol de BD evade RLS) + M2 (`alcance_operador_migracion`, `fleet/0018` ya migra en Postgres).
  - `2fe7f07` fix(seguridad): C2 (`apps/fleet/catalogo.py`; `fleet/views.py` sin `como_operador_plataforma()`; `throttle_scope='catalogo'` en las 6 vistas + rate). Verificado en sqlite; Postgres pendiente de 0.8.
  - `46b3156` test: 0.8.2 `crear_flota` abre `con_empresa`.
  - `e18a8e0` test: 0.8.4 `fleet/tests.py` retrofit completo — 54 verdes sqlite+Postgres (eran 25 ERROR).
  - `4159956` test: 0.8.8 parcial — `tenancy/tests.py` (2 tests A/B de CupoDiario + migrar-test + `tests_checks` databases). `apps.tenancy`+`apps.fleet.tests` = 105 verdes en Postgres.
- **Nota de proceso:** NO usar `--keepdb` entre corridas iterativas — un run interrumpido deja la base a medias y aparecen errores fantasma. Dropear `test_pescadeportiva_test` antes de cada corrida limpia: `docker exec psd-pg psql -U postgres -c "DROP DATABASE IF EXISTS test_pescadeportiva_test;"`.
- **Baseline Postgres tras 0.8.1-0.8.4/0.8.8-parcial:** quedan ~70 ERROR + ~6 FAIL en: `bookings/tests_tenancy` (11E+4F), `bookings/tests_ocupacion` (10E), `fleet/tests_paquetes_api` (9E), `fleet/tests_servicios_api` (6E), `fleet/tests_paquetes` (6E), `payments/tests_pricing_paquete` (5E), `bookings/tests_reserva_paquete` (4E), `payments/tests` (1E), `bookings/tests_concurrencia` (2E+1F), `finance/tests` (1E+1F), `fleet/tests_paquetes_rls` (1E), `bookings/tests_ocupacion_rls` (1E).
- **Patrones ya establecidos** (aplicar a los demás): clase de una Empresa → `EmpresaTestCase`/`ApiTestCase`; A/B → `with scope.con_empresa(X)` por bloque + conteos cruza-empresa bajo `scope.como_operador_plataforma()`; vaivén de scope → helper `_AlcanceOtraEmpresa` (copiar de `apps/fleet/tests.py`).
- 2026-09-05 (cont.) — Retrofit 0.8 continuado, todos verificados clase por clase en Postgres:
  - `07e1634` — `scope._con_alcance` ahora RESETEA la GUC de RLS al salir (bug: `SET LOCAL` dura hasta el COMMIT, no hasta el fin del `with`; tras `como_operador_plataforma()` la RLS quedaba apagada el resto de la transacción del test). + `OperadorTestCase`. + retrofit tests_paquetes/servicios_api/pricing_paquete/reserva_paquete/paquetes_rls.
  - `apps/testing.py::crear_flota` ahora respeta un alcance ya abierto (operador o con_empresa), solo abre `con_empresa` si `alcance_actual is None`. `OperadorTestCase` + `crear` helper.
  - `bookings/tests_ocupacion.py` → OperadorTestCase; `tests_ocupacion_rls.py` → setUp con `con_empresa` por Empresa. (11 verdes PG)
  - `bookings/tests_tenancy.py` → 10 clases a `OperadorTestCase`, 4 quedan `TestCase` (pegan a vista/comando/on_commit) con `crear_reserva` helper + scope explícito. IntegrityError-asserts envueltos en `transaction.atomic()`. (25 verdes PG)
  - `finance/tests.py::BalancesFiltradosPorEmpresaTests` → 3 tests envuelven la llamada a `balances()`/`resumen()` en el alcance que la vista daría.
  - `payments/tests.py::CrearPagoTests.test_reserva_con_servicio_de_otra_empresa_falla_clean` → siembra el servicio ajeno con el vaivén de alcance.
  - `bookings/tests_concurrencia.py` → 3 bugs de retrofit: `aplicar_pago_exitoso(...)` sin `empresa`; mock de refund obsoleto (`stripe.Refund.create` → `@mock.patch.object(StripeClient, 'refunds')`); conteos post-carrera sin alcance. (3 verdes PG)
  - `fleet/tests_paquetes_api.py` — aserción de componentes del paquete cruza-empresa hecha RLS-agnóstica (1 en PG por RLS, 2 en sqlite; Sección 7 unifica).
- 2026-09-05 — **Sección 0.8 CERRADA.** `23045f9` commitea el batch final. `test apps config` completo: **sqlite 676 verdes, Postgres 676 verdes (rol `ci_rls`, NOBYPASSRLS)**. Primera vez que la suite de Postgres pasa en esta rama.
  - Falta actualizar CI: el workflow ya corre la matriz sqlite+postgres pero con Postgres 17 y `ci_rls` creado en el step — verificar que sigue coincidiendo (puerto 5432 en CI vs 5433 local; el `render.yaml`/CI usa 5432, sin cambio necesario).
- **Estado:** Secciones 0, 0.8 y 1 (C1, C2) hechas. `nucleo.py` (tarea 2.1, tope `None` + `validar_rango`) modificado, verificado en ambas suites, SIN commitear — va con el primer commit de Sección 2.
- **Siguiente sesión:** commitear `nucleo.py` y arrancar Sección 2 (2.2 enums de Servicio, 2.3 registro por `estrategia_cupo`, 2.4 `Reserva.clean` usa `servicio.estrategia_cupo`, 2.5 candado re-llaveado). Recordar: dropear `test_pescadeportiva_test` antes de cada corrida limpia de Postgres; NO `--keepdb` entre iteraciones.
