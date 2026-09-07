# Plan de corrección — Hallazgos de la revisión de piezas 1-6 (expansión multi-sede)

Fecha de creación: 2026-09-05
Rama de trabajo: `fix/expansion-multi-sede-hallazgos` (desde `feature/pieza6-frontend-multitenant` @ `491f337`)
Origen: revisión integral de la implementación del agente de Antigravity de las 6 piezas.
Documentos base: `docs/superpowers/specs/2026-08-31-expansion-multi-sede-design.md` y `...-ADRs.md`.

## Decisiones del dueño (2026-09-05)

**Primera ronda (antes de arrancar):**
1. **Alcance:** todo, incluido el re-cableado del checkout público para servicios / paquetes / hospedaje.
2. **Hospedaje:** es necesidad de v1. Cablear el flujo multidía completo.
3. **Verificación:** Postgres en Docker en local. La suite completa (RLS, locks, constraints) debe correr verde localmente antes de dar por cerrada cada sección.
4. **Orden:** secciones 2→3→4→5→6→7→8→9 en orden.

**Segunda ronda (tras las preguntas abiertas, 2026-09-05):**
5. **Tipos de servicio v1:** enum de 4 valores — `PESCA`, `PASEO`, `HOSPEDAJE`, `BAJO_DEMANDA`. Todos los paseos con embarcación (seasafari, ballenas, tiburón ballena, islas, snorkel) son `PASEO` con la misma regla de cupo (1 viaje/recurso/día). El eje exclusivo/compartido va por el campo `modo_ocupacion`, configurable por Servicio.
6. **Anticipo:** **configurable por Servicio** (campo nuevo, `porcentaje_anticipo` con default 30). Un paquete usa la política de su `empresa_lider` / del servicio dominante — a definir en Sección 4.
7. **Precio de paquete:** `precio_ancla` (número fijo que pone el negocio) **MÁS las personalizaciones por encima**. El servidor arma: `ancla + Σ(personalizaciones obligatorias/preseleccionadas de los servicios componentes) + (personalizaciones opcionales que agregue el cliente) − (ajustes de servicios removidos)`. NO es "ancla incluye todo". Las "personalizaciones" son `fleet.ServicioPersonalizacion` (licencia, brunch, equipo), no el viejo `fleet.ExtrasItem`.
8. **Paquetes v1 = UNA sola empresa.** Todos los servicios componentes deben pertenecer a la `empresa_lider`. Un cobro, una cuenta de Stripe. `Paquete.clean` / `PaqueteServicio.clean` **bloquean con error claro** un paquete cruza-empresa.
9. **Paquetes cruza-empresa = fuera de v1.** El modelo real es: cada empresa cobra a su propia cuenta de Stripe (la empresa de marketing NO tiene cuenta central, a propósito, para no cargar con los impuestos de esas transacciones). Un paquete cruza-empresa implicaría N cobros a N cuentas — Stripe sin Connect no lo permite como "un solo pago percibido". Se dedica un ADR y una tanda propia más adelante. Sección 7 se reduce a: bloquear el caso + escribir el ADR-005 con el planteo del problema.
10. **Reserva de paquete:** `reserva.paquete` seteado, `reserva.servicio` **vacío**. Los servicios componentes se conocen vía `paquete.servicios_asociados`.
11. **Cupo de componentes:** al confirmarse el pago de un paquete, el sistema recorre los servicios componentes y crea el artefacto de cupo de **cada uno** (panga + `CupoDiario` para `PESCA`/`PASEO` exclusivo; `ReservaOcupacion` para `HOSPEDAJE`; nada para `BAJO_DEMANDA`). Tabla nueva `ReservaPaqueteComponente` liga cada componente a la reserva. El cupo de cada parte del paquete es real.
12. **Aviso a empresas componentes:** manual (aplica solo al futuro cruza-empresa; v1 es una sola empresa).
13. **% de plataforma:** nunca en el sistema, siempre fuera. Ningún campo, ninguna vista.

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
- [ ] **2.2** `Servicio`: convertir los 4 campos string a enums `TextChoices` (Decisión 5, cerrada):
  - `tipo_servicio`: `PESCA`, `PASEO`, `HOSPEDAJE`, `BAJO_DEMANDA`. Solo etiqueta de presentación (agenda, catálogo); NO decide cupo.
  - `estrategia_cupo`: `POR_RECURSO_DIA`, `POR_NOCHE`, `BAJO_DEMANDA`. Es lo que decide el cupo.
  - `estrategia_precio`: `POR_GRUPO`, `POR_PERSONA`, `TARIFA_FIJA`, `POR_NOCHE`.
  - `modo_ocupacion`: `EXCLUSIVO`, `COMPARTIDO` (eje independiente, por Servicio).
  - `porcentaje_anticipo`: `PositiveSmallIntegerField(default=30)` (Decisión 6).
  - Migración de datos: `0018` ya siembra `'por_recurso_dia'`/`'por_grupo'`/`'exclusivo'`/`'pesca'` — alinear los valores del enum a esas cadenas para no tener que reescribir la fila.
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

## Sección 4 — Precio: paquete, personalizaciones y noches (A2, A5, B7)

**Modelo de precio del paquete (Decisión 7):** `precio_ancla` + personalizaciones POR ENCIMA.
```
total_paquete(moneda) =
    paquete.precio_ancla_en(moneda)
  + Σ  precio de cada ServicioPersonalizacion (obligatorio o preseleccionado) de los servicios componentes NO removidos
  + Σ  precio de las ServicioPersonalizacion OPCIONALES que el cliente marcó
  − Σ  PaqueteServicio.ajuste_en(moneda) de los servicios removidos (removible=True)
```
`cargar_por_persona` de cada personalización se resuelve como en `pricing.py` hoy. Piso 0.

- [ ] **4.1** `apps/payments/pricing.py`: nueva función pura `precio_paquete_total(paquete, servicios_removidos_pks, personalizaciones_extra_pks, personas, moneda)` que implementa la fórmula de arriba. `calcular_precio_paquete` actual (solo ancla − ajustes) queda como pieza interna o se reemplaza. Cada personalización cuantizada a centavos, `_usd` hermano.
- [ ] **4.2** `fleet/models.py::Paquete.clean()`: validar que `Σ ajuste_precio de servicios removibles <= precio_ancla` (y `_usd`). Error de admin claro. **`PaqueteServicio.clean()`: todos los componentes deben ser de `paquete.empresa_lider`** (Decisión 8 — v1 = una empresa). Un servicio de otra empresa de la sede → `ValidationError` con mensaje que apunta a "paquetes cruza-empresa: fuera de v1, ver ADR-005".
- [ ] **4.3** Anticipo configurable (Decisión 6): `Servicio.porcentaje_anticipo = PositiveSmallIntegerField(default=30)`. `apps/payments/pricing.py::monto_inicial` gana parámetro `porcentaje` (default 30 = `ANTICIPO_PORCENTAJE`). Migración + campo en admin.
- [ ] **4.4** `apps/payments/views.py::CrearPagoView._post`: ramas por tipo de reserva, **en este orden**:
  1. `reserva.paquete_id` → `precio_base = precio_paquete_total(...)`; `porcentaje` = del servicio dominante del paquete o de una regla del paquete (definir: el mínimo de los componentes, o un campo `Paquete.porcentaje_anticipo`). 503 si sin precio en esa moneda.
  2. `reserva.servicio_id` → estrategia de precio del servicio (ya existe) + `DemandaPrecio(..., noches=reserva.noches)`; `porcentaje` = `reserva.servicio.porcentaje_anticipo`.
  3. legacy (`Tarifa`) → como hoy, `porcentaje=30`.
  Extras/transporte/promoción de `ReservaExtra`/`ReservaTransporte` (el sistema viejo) **NO** se suman a un paquete — el paquete usa `ServicioPersonalizacion`. Para servicio suelto: a decidir en 5.x si un servicio no-pesca admite el sistema viejo de extras; por defecto solo pesca legacy lo usa.
- [ ] **4.5** `CrearPagoView`: pasar `noches=reserva.noches` a `DemandaPrecio` en la rama de servicio. `reserva.noches` sale de `fecha_salida` (Sección 5).
- [ ] **4.6** `apps/payments/services.py::_verificar_monto`: recomputar el esperado cubriendo las 3 ramas (misma función `precio_paquete_total` / estrategia). Sigue sin rebotar, solo registra descuadre.
- [ ] **4.7** Tests `tests_pricing_paquete.py`: fórmula con 0 / N removidos, con/sin personalizaciones opcionales, `por_noche` con 1 / 3 noches, anticipo 30/50/100, el webhook no marca descuadre cuando el precio es correcto. `PaqueteServicio.clean` rechaza componente de otra empresa.
- [ ] **4.8** Commit `fix(precio): paquete = ancla + personalizaciones; anticipo configurable; hospedaje por noches`.

---

## Sección 5 — Checkout: serializer + API (A1, A3, B2)

- [ ] **5.1** Modelos de selección del checkout de paquete:
  - `ReservaPaqueteServicioRemovido(reserva FK, servicio FK, unique_together)` — qué servicios removibles quitó el cliente.
  - `ReservaPaquetePersonalizacion(reserva FK, servicio_personalizacion FK, cantidad, unique_together)` — qué personalizaciones opcionales marcó (las obligatorias/preseleccionadas se dan por incluidas; no hace falta guardarlas salvo para el desglose — decidir).
  - RLS por `reserva.empresa` (política EXISTS como `bookings_reservaextra`). Migraciones + políticas. **Añadir estas tablas + `ReservaPaqueteComponente` (6.x) a la lista de `tests_rls.py` (8.7).**
- [ ] **5.2** `ReservaCheckoutSerializer.Meta.fields`: añadir `servicio` (slug, filtrado por empresa vía `get_fields`), `paquete` (slug, filtrado por `empresa_lider == self.context['empresa']`), `fecha_salida`, `servicios_removidos` (lista de slugs), `personalizaciones` (lista de `{id, cantidad}`), todo write_only salvo lo que se necesite de vuelta.
- [ ] **5.3** `ReservaCheckoutSerializer.validate`:
  - `servicio` y `paquete` **mutuamente excluyentes** (Decisión 10). Si viene `paquete`, `reserva.servicio` queda `None`.
  - `paquete.empresa_lider` debe ser `self.context['empresa']` (si no → 400, "ese paquete no lo lidera esta empresa"). Como v1 es una-empresa, todos los componentes también son de ella.
  - `fecha_salida`: obligatoria y `> fecha` si algún componente (o el servicio) es `HOSPEDAJE` / `estrategia_cupo == POR_NOCHE`; prohibida si ninguno lo es.
  - `servicios_removidos ⊆` los `PaqueteServicio` con `removible=True` del paquete.
  - `personalizaciones ⊆` las `ServicioPersonalizacion` de los servicios componentes NO removidos, con `activo=True`.
  - `numero_personas` contra `personas_incluidas` / capacidad del servicio dominante, no solo `MAX_PERSONAS` de pesca.
- [ ] **5.4** `ReservaCheckoutSerializer.create/update`: persistir `servicio` XOR `paquete`, `fecha_salida`, sincronizar `servicios_removidos` y `personalizaciones` (borrar+recrear, dentro de `con_empresa`).
- [ ] **5.5** `Reserva.clean()`: la estrategia de cupo se resuelve así:
  - reserva de **servicio** → `servicio.estrategia_cupo` (Sección 2). Si `POR_NOCHE` → validar contra ocupaciones (`evaluar_disponibilidad_hospedaje`), si no → `validar_cupo_diario` de un día.
  - reserva de **paquete** → validar el cupo de CADA componente con su propia estrategia (todos en la misma empresa en v1). Si algún componente no cabe → `ValidationError` nombrando cuál.
  - **No** crea `ReservaOcupacion` / `ReservaPaqueteComponente` aquí (eso es Sección 6, al confirmar el pago). `clean()` solo valida disponibilidad, sin lock.
- [ ] **5.6** Endpoint `GET /api/sedes/<sede_slug>/paquetes/<slug>/` (`PaqueteDetailView`) — resuelve slug→objeto de una vez, mismo patrón de scopes que `apps/fleet/catalogo.py`. Mata el N+1 de `reservar/page.tsx` (B2).
- [ ] **5.7** Frontend `reservar/page.tsx`: reemplazar el waterfall `getSedes()`+loop por `getPaqueteDetalle(sedeSlug, paqueteSlug)` (`?sede=` en el query).
- [ ] **5.8** Frontend `api.ts`: `ReservaInput` gana `servicio?`, `fecha_salida?`, `servicios_removidos?`, `personalizaciones?`; `guardarReserva` los manda. `MotivoNoDisponible` += `'sin_lugar'` (B3).
- [ ] **5.9** Frontend `checkout-view.tsx` / `paquete-card.tsx`: la selección de servicios removidos y personalizaciones que ve el cliente es la que se manda; el precio mostrado (`pricing-paquete.ts`) debe coincidir con el que calcula el servidor en `crear-pago`. Ajustar `pricing-paquete.ts` a la fórmula de 4.1.
- [ ] **5.10** Tests: serializer acepta/rechaza combinaciones; `paquete` de otra `empresa_lider` → 400; `Reserva.clean` de paquete valida cada componente; API de detalle de paquete.
- [ ] **5.11** Commit `fix(checkout): serializer y API aceptan servicio, paquete, fecha_salida, componentes y personalizaciones`.

---

## Sección 6 — Confirmación de pago crea el cupo de cada componente (A3, A4 wiring)

- [ ] **6.1** Modelo `ReservaPaqueteComponente(reserva FK, servicio FK, empresa FK, estado_cupo, recurso FK null, unique_together(reserva, servicio))` — una fila por servicio del paquete, con el resultado de reservar su cupo. `empresa` = `servicio.empresa` (en v1 = `reserva.empresa`). RLS por `empresa`.
- [ ] **6.2** `apps/payments/services.py::aplicar_pago_exitoso`: tras marcar `PAGADA`, antes del `on_commit`:
  - reserva de **servicio suelto**: si `estrategia_cupo == POR_NOCHE` → `bloquear_recurso` + `evaluar_disponibilidad_hospedaje` + crear `ReservaOcupacion`. Si no → como hoy (el `full_clean()` ya valida cupo de pesca; la asignación de panga es manual en la agenda).
  - reserva de **paquete**: recorrer `paquete.servicios_asociados` NO removidos; por cada componente, según su `estrategia_cupo`:
    - exclusivo día (`PESCA`/`PASEO`) → contar `CupoDiario` de esa empresa/fecha, tomar lock `(empresa, servicio, fecha)`; si lleno → cae todo. Crear `ReservaPaqueteComponente(estado_cupo=OK)`; la asignación concreta de panga sigue manual en la agenda.
    - `POR_NOCHE` → `bloquear_recurso` + `evaluar_disponibilidad_hospedaje` + `elegir_recursos` + crear `ReservaOcupacion` ligada + `ReservaPaqueteComponente`.
    - `BAJO_DEMANDA` → `ReservaPaqueteComponente(estado_cupo=OK)` sin más.
  - **Todo o nada:** si un componente no tiene cupo → la transacción hace rollback y se va a `_cancelar_sin_cupo` (reembolso 100% con la cuenta de `reserva.empresa` = la única empresa en v1). El mensaje nombra el componente.
  - En v1 todos los componentes son de `reserva.empresa`, así que **no hay `con_empresa` anidado** — todo corre en el alcance ya abierto por el webhook. (El loop multi-scope es Sección 7.)
- [ ] **6.3** Núcleo puro `elegir_recursos(libres, personas, cantidad_recursos)` — el/los recurso(s) más chico(s) que caben. Determinista, testeable sin base.
- [ ] **6.4** Cancelación / reembolso: al pasar a `CANCELADA`, `Reserva.save()` baja `ocupa_cupo` de sus `ReservaOcupacion` (Sección 3.2) y marca `ReservaPaqueteComponente` como liberado. Test explícito para pesca, hospedaje y paquete.
- [ ] **6.5** `manage.py conciliar_pagos`: test de que una reserva de hospedaje/paquete conciliada crea sus artefactos de cupo igual que el webhook.
- [ ] **6.6** Admin: `ReservaOcupacionInline` y un `ReservaPaqueteComponenteInline` mayormente solo-lectura para reservas ya pagadas; editables solo para `pendiente_pago` / WhatsApp.
- [ ] **6.7** Tests `# postgres-only`: dos reservas de hospedaje pagando el último cuarto en paralelo → una `PAGADA` con ocupación, la otra `CANCELADA + reembolsada`; el reembolso libera el rango. Paquete con componente de hospedaje sin cupo → todo el paquete se reembolsa.
- [ ] **6.8** Commit `fix(hospedaje): el pago reserva el cupo de cada componente/servicio multidía, con reembolso si algo se llenó`.

---

## Sección 7 — Paquetes cruza-empresa: bloquear + documentar (M6)

**Decisión 8/9: fuera de v1.** Esta sección NO construye el multi-cobro. Solo:

- [ ] **7.1** Confirmar que `PaqueteServicio.clean()` (Sección 4.2) rechaza cualquier componente de una empresa distinta a `paquete.empresa_lider`, con mensaje claro. Test.
- [ ] **7.2** Escribir `docs/superpowers/specs/2026-09-05-expansion-multi-sede-ADR-005-paquetes-cruza-empresa.md` con:
  - El planteo: cada empresa tiene su cuenta de Stripe, la empresa de marketing NO tiene cuenta central (a propósito, para no cargar impuestos de esas transacciones), y no se usa Connect. Un paquete cruza-empresa implica N cobros a N cuentas.
  - Por qué el "un solo pago percibido por el cliente" no es trivial sin Connect (Stripe no permite un PaymentElement que confirme N PaymentIntents de N cuentas distintas como un solo cargo).
  - Opciones a evaluar cuando se retome: (a) N PaymentIntents secuenciales en el checkout con reembolsos parciales; (b) empresa_lider cobra su parte online y las demás mandan link de pago aparte; (c) Stripe Connect (revisar si "direct charges" evita el problema fiscal — el cargo se crea en la cuenta conectada, el dinero nunca toca a la plataforma).
  - Qué queda preparado hoy: `Paquete` tiene `sede` + `empresa_lider`; `PaqueteServicio` valida misma sede; el cupo por componente y `ReservaPaqueteComponente` ya soportan `empresa` distinta por componente (aunque v1 no lo use).
  - Estado: PROPUESTO, sin fecha.
- [ ] **7.3** Commit `docs(adr): ADR-005 paquetes cruza-empresa (fuera de v1, planteo del problema)`.

---

## Sección 8 — MEDIO / BAJO restantes

- [x] **8.1** (M2) — HECHO en 0.8.1: `apps/tenancy/rls.py::alcance_operador_migracion(connection)` envuelve los writes ORM de `fleet/0018`. Falta: nota en `backend/CLAUDE.md` sobre usarlo en cualquier data migration futura sobre tablas con RLS.
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

## Preguntas abiertas

**Todas resueltas 2026-09-05 (ver "Decisiones del dueño, segunda ronda" arriba):**
- ✅ Extras encima del ancla → son las `ServicioPersonalizacion` de los componentes, y SÍ suman (Decisión 7).
- ✅ `servicio` vs `paquete` → excluyentes; paquete deja `reserva.servicio` vacío (Decisión 10).
- ✅ Tipos de servicio v1 → `PESCA`, `PASEO`, `HOSPEDAJE`, `BAJO_DEMANDA` (Decisión 5).
- ✅ Aviso a empresas componentes → manual (Decisión 12).
- ✅ % de plataforma → nunca en el sistema (Decisión 13).
- ✅ Anticipo hospedaje → configurable por Servicio, default 30% (Decisión 6).
- ✅ Paquetes cruza-empresa → fuera de v1; v1 = una sola empresa por paquete (Decisiones 8, 9).

**Nueva pendiente menor (no bloquea, decidir en Sección 4.4):**
- ¿El % de anticipo de un paquete sale del servicio dominante, del mínimo de los componentes, o de un campo propio `Paquete.porcentaje_anticipo`? (Recomendación: campo propio, default 30.)
- ¿Un servicio suelto que NO es pesca (un `PASEO`) admite el sistema viejo de `ReservaExtra`/`ReservaTransporte`, o solo `ServicioPersonalizacion`? (Recomendación: solo `ServicioPersonalizacion` para servicios nuevos; el sistema viejo queda solo para la pesca legacy.)

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
- 2026-09-05 — Segunda ronda de decisiones del dueño respondida y volcada al plan: Secciones 4-7 reescritas (paquetes v1 = una empresa; cruza-empresa fuera de v1 → Sección 7 se reduce a bloquear + ADR-005; precio = ancla + personalizaciones; anticipo configurable por servicio; `servicio` XOR `paquete`; cupo por componente con `ReservaPaqueteComponente`). Preguntas abiertas todas cerradas salvo 2 menores no bloqueantes (ver esa sección).
- 2026-09-06 — Sección 2 cerrada @ 4187d57: Tareas 2.1 a 2.5 completadas (enums tipados en Servicio, registro por estrategia_cupo, Reserva.clean resolviendo por estrategia_cupo, advisory lock por empresa/servicio_id/fecha). Gate: sqlite 685 verdes, Postgres 685 verdes. Siguiente: Sección 3.
- 2026-09-06 — Sección 3 cerrada @ d8eedd5: Tareas 3.1 a 3.3 completadas (ReservaOcupacion.ocupa_cupo sincronizado por Reserva.save, constraint EXCLUDE USING gist anti-doble-booking, bloquear_recurso advisory lock por empresa/recurso). Gate: sqlite 692 verdes, Postgres 692 verdes. Siguiente: Sección 4.
- 2026-09-06 — Sección 4 cerrada @ e89c46f: Tareas 4.1 a 4.5 completadas (precio_paquete_total ancla + personalizaciones − ajustes, PaqueteServicio v1 mono-empresa y validación de suma de ajustes en Paquete, Paquete.porcentaje_anticipo y monto_inicial con porcentaje, CrearPagoView con 3 ramas de precio y sin extras legacy en paquetes, _verificar_monto con porcentaje de anticipo correcto). Gate: sqlite 705 verdes, Postgres 705 verdes. Siguiente: Sección 5.
- 2026-09-06 — Sección 5 cerrada @ 54285fc: Tareas 5.1 a 5.9 completadas (modelos ReservaPaqueteServicioRemovido y ReservaPaquetePersonalizacion con migraciones RLS, ReservaCheckoutSerializer con servicio/paquete/fecha_salida/personalizaciones/removidos, Reserva.clean con validación de hospedaje multidia y disponibilidad de componentes de paquete, PaqueteDetailView directo por sede+slug, frontend checkout y pricing sincronizados con build y lint limpios). Gate: sqlite 731 verdes, Postgres 731 verdes. Siguiente: Sección 6.
- 2026-09-06 — Sección 6 cerrada @ 4772ad1: Tareas 6.1 a 6.7 completadas (ReservaPaqueteComponente con política RLS, elegir_recursos determinista, SinCupoError y reservar_cupo_al_confirmar con rollback y reembolso en pago y conciliación, Reserva.save sincroniza estado_cupo LIBERADO/OK, inlines de ocupaciones y componentes en admin de Reserva). Gate: sqlite 748 verdes, Postgres 748 verdes (rol ci_rls, NOBYPASSRLS). Siguiente: Sección 6.5.
- 2026-09-06 — Sección 6.5 cerrada @ 01533f4: Tareas 6.5.1 a 6.5.6 completadas (ServicioSerializer expone empresa_slug, api.ts acepta empresaSlug opcional en request y 8 funciones, enlaces de catálogo llevan empresa, reservar/page.tsx resuelve empresa dinámicamente y la inyecta en CheckoutView). Gate: apps.fleet sqlite 88 verdes, Postgres 88 verdes, frontend lint/tsc/build limpios. Siguiente: Sección 7.
- 2026-09-06 — Sección 7 cerrada @ 3741b5e: Tareas 7.1 a 7.3 completadas (test explícito en PaquetesModelTests validando que PaqueteServicio.clean rechaza componentes de otra empresa mencionando 'ADR-005', redacción de ADR-005 en docs/superpowers/specs/2026-09-06-ADR-005-paquetes-cruza-empresa.md cubriendo contexto fiscal de Stripe, problema multi-cuenta, estado v1 bloqueado, arquitectura preparada y opciones futuras a evaluar). Gate: apps.fleet sqlite 88 verdes, Postgres 88 verdes. Siguiente: Sección 8.
- 2026-09-07 — Sección 8 cerrada @ 2fa127d: Tareas 8.1 a 8.6 completadas (documentación en backend/CLAUDE.md de alcance_operador_migracion y reactivación cancelada a pagada, import perezoso de scope para Unfold vía apps.tenancy.permisos_unfold, MotivoNoDisponible verificado en frontend, Tarifa.save con select_for_update y rescate de IntegrityError ante carreras de inserción, EmpresaScopedUserAdminMixin restringe email y password a solo lectura para usuarios ajenos, guardarraíl RLS en tests_rls.py verificando que toda tabla con empresa_id o empresa_lider_id y tablas en whitelist vía FK poseen política tenancy_alcance). Gate: apps+config sqlite 753 verdes, Postgres 753 verdes (rol ci_rls, NOBYPASSRLS). Siguiente: Sección 9 (Cierre).
- 2026-09-07 — Sección 9 cerrada: Cierre y verificación integral completados (753 tests verdes en SQLite y Postgres CI, deploy check limpio, frontend lint/tsc/build limpios, repaso de fugas sin llamadas indebidas, documentación de CLAUDE.md y RUNBOOK actualizada, ADRs cerrados, memoria de proyecto completada). Rama lista para handoff al dueño.
