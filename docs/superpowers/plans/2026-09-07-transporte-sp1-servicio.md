# SP1 — Transporte como servicio · Tareas ejecutables

> **Para agentic workers:** SUB-SKILL REQUERIDA: `superpowers:subagent-driven-development`
> o `superpowers:executing-plans`, task por task. Los pasos usan checkbox (`- [ ]`).
>
> **Para el agente que ejecuta (Antigravity):** este documento es autosuficiente. NO
> re-derives diseño. Haz las tareas **en orden**, cada una con su ciclo completo
> (test que falla → código → test verde → commit). **PARA AL FINAL DE CADA SECCIÓN**,
> corre el Gate (suite en sqlite Y Postgres) y reporta: `git log --oneline` de la
> sección, resultado de ambos gates, dudas. No arranques la siguiente sección sin luz
> verde. Si una tarea te obliga a una decisión de producto que este documento no
> contempla: **para y pregunta**.
>
> **Empieza por la Sección 0.**

**Goal:** la Empresa 2 (transporte) vende traslados sueltos por la web, con su propio
cobro (un solo PaymentIntent a su cuenta Stripe).

**Architecture:** el transporte es un `fleet.Servicio` de primera clase
(`estrategia_cupo=bajo_demanda`, `estrategia_precio=por_ruta`). El precio sale de un
catálogo nuevo `fleet.TransporteTarifa` (3 tipos de traslado por empresa) vía una
estrategia de precio tipada `PorRuta`. El detalle de cada reserva vive en
`bookings.DetalleTransporte` (satélite OneToOne). Se elimina el transporte-como-add-on
de la reserva de pesca.

**Tech Stack:** Python 3.14, Django 6, DRF, psycopg 3, Postgres con RLS por
`empresa_id`, stripe-python (`StripeClient`), Next.js 16 (Turbopack),
`@stripe/react-stripe-js`.

**Spec:** `docs/superpowers/specs/2026-09-07-transporte-multi-empresa-design.md`
(§1–§3, §6, §7). Léela si algo no cuadra.

**Rama:** `feat/transporte-multi-empresa` (worktree `.claude/worktrees/transporte-multi-empresa`),
basada en `fix/expansion-multi-sede-hallazgos`. **No se mergea a `main` hasta que
`fix/expansion-multi-sede-hallazgos` esté integrada.**

**Prerrequisito recomendado:** la Sección 10 del plan de corrección de hallazgos
(`2026-09-06-correccion-hallazgos-TAREAS-EJECUTABLES.md`) — quitar "servicios
removibles" de paquetes. SP1 **no** lo necesita técnicamente (SP2 sí), pero conviene
mergearlo antes para no arrastrar conflictos en `pricing.py` y `confirmacion.py`.

---

## Global Constraints (aplican a TODA tarea)

Copiadas del plan de corrección de hallazgos; son las mismas.

1. **Un commit por tarea.** Mensaje en español, prosa normal (no caveman), termina con:
   ```
   Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_01GF3fNM82hwu57W1ReSmrhw
   ```
2. **Nada de lógica ni cifras de dinero fuera de `backend/apps/payments/`** (`pricing.py`
   y `estrategias_precio.py`). El resto del código pasa primitivos, no calcula.
3. **RLS fail-closed.** Ninguna consulta nueva depende solo del filtro del ORM. Nunca
   `scope.como_operador_plataforma()` dentro de una vista `AllowAny`. Para cruzar
   empresas: iterar `scope.con_empresa(e)` o función Postgres `SECURITY DEFINER`.
4. **`MXN` y `USD` siempre por separado, nunca sumados.** Cada precio nuevo lleva su
   hermano `_usd` (nullable).
5. **`TextChoices`** para todo enum nuevo o convertido.
6. **Cada modelo nuevo con `empresa_id`** (o que llegue a empresa vía FK) necesita
   migración de política RLS (patrón: `backend/apps/fleet/migrations/0017_rls_catalogo.py`
   o `0020_rls_paquetes.py`) y un test `# postgres-only` de aislamiento. Y hay que
   añadirlo a la whitelist/query del guardarraíl `tenancy/tests_rls.py` (Tarea 8.6 del
   plan de corrección).
7. **Toda data migration que haga `Modelo.objects.create/update/delete` sobre tabla con
   RLS** se envuelve en `with alcance_operador_migracion(schema_editor.connection):`
   (helper en `backend/apps/tenancy/rls.py`).
8. **No romper la garantía del cobro** (`backend/CLAUDE.md`, "Garantías del cobro"): el
   webhook es la única fuente de verdad; idempotencia; congelado de precio al pagar en
   `CrearPagoView`; `_verificar_monto` no rebota.
9. **Verificación sin navegador.** No abrir Chrome. Frontend se verifica con
   `npx.cmd tsc --noEmit`, `npm.cmd run lint`, `npm.cmd run build`. El dueño mira el
   sitio.

---

## Entorno y comandos (Windows, PowerShell o Bash)

- Python del venv: `backend/venv/Scripts/python.exe` (comandos `manage.py` desde `backend/`).
- **Postgres para pruebas** (contenedor `psd-pg`, puerto host 5433, rol `ci_rls`):
  ```bash
  docker run -d --name psd-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=pescadeportiva_test -p 5433:5432 postgres:17
  docker exec psd-pg psql -U postgres -d pescadeportiva_test -v ON_ERROR_STOP=1 -c \
    "CREATE ROLE ci_rls LOGIN PASSWORD 'ci_rls_password_local' NOSUPERUSER NOBYPASSRLS CREATEDB;"
  ```
- **Gate de sección** (correr los dos):
  ```bash
  # sqlite
  backend/venv/Scripts/python.exe manage.py test apps config
  # postgres (dropear la BD de test antes)
  docker exec psd-pg psql -U postgres -c "DROP DATABASE IF EXISTS test_pescadeportiva_test;"
  DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test \
  DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 \
  backend/venv/Scripts/python.exe manage.py test apps config
  ```
- Frontend: `cd frontend && npm.cmd run lint && npx.cmd tsc --noEmit && npm.cmd run build`.

---

## File Map

| Archivo | Responsabilidad | Sección |
|---|---|---|
| `backend/apps/fleet/enums.py` | `TipoServicio.TRANSPORTE`, `EstrategiaPrecio.POR_RUTA` | 1, 3 |
| `backend/apps/fleet/models.py` | quitar `TransportePrecio`; añadir `TransporteTarifa`; `Servicio` gana `capacidad_maxima`, `hora_apertura`, `hora_cierre` | 0, 1, 3 |
| `backend/apps/fleet/tarifa_transporte.py` (nuevo) | `resolver_tarifa_transporte(empresa_id, tipo, zona, personas)` — función pura, única fuente de la fila de tarifa | 1 |
| `backend/apps/fleet/migrations/00XX_*.py` | borrar `TransportePrecio`, crear `TransporteTarifa` + RLS, campos de `Servicio`, data-migration de ventana 5–7am para pesca La Paz | 0, 1, 3, 4 |
| `backend/apps/fleet/admin.py` | quitar `TransportePrecioAdmin`; `TransporteTarifaAdmin`; revisar `PuntoEncuentroAdmin` | 0, 1 |
| `backend/apps/payments/estrategias_precio.py` | `DemandaPrecio` gana `tipo_traslado`/`zona`; clase `PorRuta`; registrarla | 2 |
| `backend/apps/payments/pricing.py` | quitar `cargo_por_transporte` | 0 |
| `backend/apps/bookings/models.py` | quitar `ReservaTransporte`; añadir `DetalleTransporte`; mover `validar_ventana_salida` a `Reserva.clean()` gateado por servicio; tope de personas por servicio; auditar saltos de `bajo_demanda` | 0, 4, 5 |
| `backend/apps/bookings/migrations/00XX_*.py` | borrar `ReservaTransporte` (+ su RLS), crear `DetalleTransporte` + RLS | 0, 5 |
| `backend/apps/bookings/serializers.py` | quitar `TransporteSeleccionSerializer` y su wiring del checkout de pesca; nuevo `TrasladoCheckoutSerializer` | 0, 6 |
| `backend/apps/bookings/admin.py` | quitar `ReservaTransporteInline`; `DetalleTransporteInline`; `Agenda` no lista transporte | 0, 5 |
| `backend/apps/payments/views.py` (`CrearPagoView`) | armar `DemandaPrecio` con `tipo_traslado`/`zona` para servicios `por_ruta`; congelar `DetalleTransporte.numero_personas`/`precio_calculado` | 6 |
| `backend/apps/fleet/views.py` | `GET /api/<empresa_slug>/traslados/` — catálogo (servicio + `TransporteTarifa` + `PuntoEncuentro`) | 6 |
| `backend/config/urls.py` | montar la ruta de traslados | 6 |
| `backend/config/settings/base.py` | `UNFOLD['SIDEBAR']`: quitar `TransportePrecio`, añadir `TransporteTarifa` | 1 |
| `frontend/src/app/[lang]/traslados/page.tsx` (nuevo) + `loading.tsx` | server component, trae catálogo + diccionario | 7 |
| `frontend/src/components/traslado-view.tsx` (nuevo) | checkout recortado de traslado (tipo → hospedaje → fechas → personas → cliente → deslinde → pago) | 7 |
| `frontend/src/components/checkout-view.tsx` | quitar el fieldset "transporte" del checkout de pesca | 0 |
| `frontend/src/lib/api.ts` | `getTraslados(empresaSlug)`, `crearReservaTraslado(...)` | 6, 7 |
| `frontend/src/lib/dates.ts` | `MAX_PEOPLE` y la ventana 5–7am dejan de ser universales (se leen del servicio) | 4, 7 |
| `frontend/src/app/[lang]/dictionaries/{es,en}.json` | copy de `/traslados`; quitar claves del transporte-en-pesca | 0, 7 |
| `backend/apps/fleet/tests.py`, `backend/apps/bookings/tests.py`, `backend/apps/payments/tests.py` | tests de cada tarea | todas |

<!-- arch-critic: revisión inline hecha por el orquestador (no se despachó subagente por política de este proyecto). Puntos verificados: (1) `DetalleTransporte` no acopla con `ReservaTransporte` porque este último se borra en Sección 0 antes de crear el nuevo; (2) `resolver_tarifa_transporte` es pura y no importa de `payments` (evita ciclo fleet↔payments — `PorRuta` en payments importa de fleet, no al revés); (3) la generalización de `Reserva.clean()` (Sección 4) va ANTES de `DetalleTransporte` (Sección 5) y de la API (Sección 6) porque ambas dependen de que la ventana horaria y el tope de personas ya no sean fijos; (4) el endpoint de catálogo (Sección 6) no toca `CrearPagoView` hasta su propia tarea. -->

---

## SECCIÓN 0 — Limpieza: transporte deja de ser personalización

Objetivo: borrar el add-on de transporte dentro de la reserva de pesca **antes** de
montar lo nuevo, para no tener dos modelos de precio de transporte a la vez. Sin datos
en producción (prelanzamiento), el borrado es limpio.

### Tarea 0.1 — Quitar el fieldset de transporte del checkout de pesca (frontend)

**Files:**
- Modify: `frontend/src/components/checkout-view.tsx` (fieldset "transporte" ~líneas 1710+ y su estado `transportePrecio`, `transporteSeleccion`, etc.)
- Modify: `frontend/src/lib/api.ts` (payload de `guardarReserva`: quitar el objeto `transporte`)
- Modify: `frontend/src/app/[lang]/dictionaries/{es,en}.json` (bloque `checkout.transporte.*`)

- [x] **Paso 1:** localizar todo lo que renderiza o envía transporte en `checkout-view.tsx` (`grep -n "transporte\|Transporte" frontend/src/components/checkout-view.tsx`).
- [x] **Paso 2:** quitar el `<fieldset>` de transporte, el estado asociado, y el campo `transporte` del cuerpo que se manda a `guardarReserva`.
- [x] **Paso 3:** quitar `checkout.transporte` de las dos dictionaries (y cualquier `checkout.*` que solo use ese bloque). Reiniciar `npm run dev` (Turbopack cachea las dictionaries).
- [x] **Paso 4:** `cd frontend && npx.cmd tsc --noEmit && npm.cmd run lint && npm.cmd run build` → verde.
- [x] **Paso 5:** commit `refactor(checkout): el checkout de pesca deja de ofrecer traslado`.

### Tarea 0.2 — Quitar `TransporteSeleccionSerializer` del checkout serializer

**Files:**
- Modify: `backend/apps/bookings/serializers.py` (quitar `TransporteSeleccionSerializer`, el campo `transporte` de `ReservaCheckoutSerializer`, `_sacar_extras_y_transporte` → `_sacar_extras`, `_construir_transporte`, `quiere_transporte`, la rama de `_guardar` que crea/borra `ReservaTransporte`)
- Modify: `backend/apps/bookings/serializers.py` imports (quitar `TransportePrecio`, `ReservaTransporte`, `PuntoEncuentro` si ya no se usan)
- Test: `backend/apps/bookings/tests.py` (borrar/ajustar los tests de `ReservaCheckoutSerializer` que ejercen `transporte`)

- [x] **Paso 1:** correr los tests actuales de checkout con transporte para ver cuáles vas a borrar: `manage.py test apps.bookings -k transporte -v2`.
- [x] **Paso 2:** quitar el serializer anidado y todo su wiring. `_sacar_extras_y_transporte` pasa a devolver solo extras.
- [x] **Paso 3:** borrar los tests de checkout-de-pesca-con-transporte (el flujo ya no existe). Dejar los de extras intactos.
- [x] **Paso 4:** `manage.py test apps.bookings` → verde.
- [x] **Paso 5:** commit `refactor(bookings): quita transporte del serializer de checkout de pesca`.

### Tarea 0.3 — Quitar `cargo_por_transporte` de `pricing.py`

**Files:**
- Modify: `backend/apps/payments/pricing.py` (quitar `cargo_por_transporte` y su mención en el docstring del módulo)
- Modify: `backend/apps/payments/views.py` / donde `CrearPagoView` sume el transporte (quitar esa rama)
- Test: `backend/apps/payments/tests.py` (quitar tests de `cargo_por_transporte` y del total-con-transporte)

- [x] **Paso 1:** `grep -rn "cargo_por_transporte\|\.transporte\b\|ReservaTransporte" backend/apps/payments/`.
- [x] **Paso 2:** quitar la función y su uso en el cálculo del total. El total de una reserva de pesca ya no incluye transporte.
- [x] **Paso 3:** ajustar `_verificar_monto` si menciona transporte.
- [x] **Paso 4:** `manage.py test apps.payments` → verde.
- [x] **Paso 5:** commit `refactor(payments): quita cargo_por_transporte`.

### Tarea 0.4 — Borrar el inline de admin y el modelo `ReservaTransporte`

**Files:**
- Modify: `backend/apps/bookings/admin.py` (quitar `ReservaTransporteInline` y su uso en `ReservaAdmin.inlines`; quitar import)
- Modify: `backend/apps/bookings/models.py` (borrar `class ReservaTransporte`)
- Create: `backend/apps/bookings/migrations/00XX_borra_reservatransporte.py` — `DeleteModel('ReservaTransporte')`. Si tenía política RLS en `0032_rls_checkout_paquete` o similar, la migración también dropea la política (`RunSQL` con `DROP POLICY IF EXISTS ...`). Sin datos productivos → no hace falta backfill; si hicieras alguno, envolver en `alcance_operador_migracion`.
- Modify: `backend/apps/bookings/tests.py` (quitar tests que instancien `ReservaTransporte`)
- Modify: `backend/apps/tenancy/tests_rls.py` (quitar `bookings_reservatransporte` de la whitelist del guardarraíl)

- [x] **Paso 1:** `grep -rn "ReservaTransporte" backend/` — confirmar que solo quedan admin, models, migración vieja, tests.
- [x] **Paso 2:** quitar del admin, borrar el modelo, `makemigrations bookings`.
- [x] **Paso 3:** revisar la migración generada: que sea `DeleteModel` limpio; añadir a mano el `DROP POLICY` si aplica.
- [x] **Paso 4:** `migrate` en sqlite; Gate de sección lo prueba en Postgres.
- [x] **Paso 5:** commit `refactor(bookings): elimina el modelo ReservaTransporte`.

### Tarea 0.5 — Borrar `TransportePrecio`

**Files:**
- Modify: `backend/apps/fleet/models.py` (borrar `class TransportePrecio`; **conservar** el enum `Zona` moviéndolo a nivel de módulo o a `PuntoEncuentro` — lo usan `PuntoEncuentro` y, en la Sección 1, `TransporteTarifa`)
- Modify: `backend/apps/fleet/admin.py` (quitar `@admin.register(TransportePrecio)` y su clase)
- Modify: `backend/apps/fleet/models.py` — `PuntoEncuentro.zona` ahora apunta a `Zona` reubicado
- Create: `backend/apps/fleet/migrations/00XX_borra_transporteprecio.py` — `DeleteModel` + `DROP POLICY` de su RLS (ver `fleet/migrations/*rls*`)
- Modify: `backend/config/settings/base.py` (`UNFOLD['SIDEBAR']` — quitar el link a `TransportePrecio`; **cuidado**: un link mal escrito tumba el admin entero)
- Modify: `backend/apps/fleet/tests.py`, `backend/apps/tenancy/tests_rls.py` (whitelist)

- [x] **Paso 1:** `grep -rn "TransportePrecio" backend/`.
- [x] **Paso 2:** reubicar `Zona` (queda como `class Zona(models.TextChoices)` a nivel de módulo en `fleet/models.py` o en `fleet/enums.py`).
- [x] **Paso 3:** borrar modelo + admin + link del SIDEBAR. `makemigrations fleet`.
- [x] **Paso 4:** `migrate` sqlite.
- [x] **Paso 5:** commit `refactor(fleet): elimina TransportePrecio (lo reemplaza TransporteTarifa)`.

### Gate Sección 0

- [x] `manage.py test apps config` verde en **sqlite Y Postgres** (drop antes).
- [x] `check --deploy --fail-level WARNING` con `config.settings.production` + env de relleno.
- [x] Frontend `lint` · `tsc --noEmit` · `build` verdes.
- [x] `grep -rn "ReservaTransporte\|TransportePrecio\|cargo_por_transporte" backend/ frontend/src/` → **cero** (salvo migraciones históricas anteriores a las de borrado).
- [x] Commit `docs(plan): SP1 Sección 0 cerrada`. **PARA y reporta.**

---

## SECCIÓN 1 — `TransporteTarifa` (catálogo de precios)

### Tarea 1.1 — Modelo `TransporteTarifa`

**Files:**
- Modify: `backend/apps/fleet/enums.py` — nuevo:
  ```python
  class TipoTraslado(models.TextChoices):
      REDONDO_AEROPUERTO = 'redondo_aeropuerto', 'Redondo con aeropuerto'
      REDONDO_ACTIVIDAD = 'redondo_actividad', 'Redondo actividad'
      RECEPCION_AEROPUERTO = 'recepcion_aeropuerto', 'Recepción aeropuerto'
  ```
- Modify: `backend/apps/fleet/models.py` — nuevo modelo:
  ```python
  class TransporteTarifa(models.Model):
      empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='tarifas_transporte')
      tipo_traslado = models.CharField(max_length=25, choices=TipoTraslado.choices)
      zona = models.CharField(max_length=10, choices=Zona.choices, blank=True, default='')  # '' salvo redondo_actividad
      personas_min = models.PositiveSmallIntegerField(default=1)
      personas_max = models.PositiveSmallIntegerField(null=True, blank=True)  # None = sin tope superior
      precio = models.DecimalField(max_digits=10, decimal_places=2)
      precio_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
      activo = models.BooleanField(default=True)

      class Meta:
          ordering = ['empresa', 'tipo_traslado', 'zona', 'personas_min']
          constraints = [
              models.UniqueConstraint(fields=['empresa', 'tipo_traslado', 'zona', 'personas_min'],
                                      name='transportetarifa_unica'),
              models.CheckConstraint(
                  name='transportetarifa_zona_solo_actividad',
                  condition=(models.Q(tipo_traslado='redondo_actividad') & ~models.Q(zona='')) |
                            (~models.Q(tipo_traslado='redondo_actividad') & models.Q(zona='')),
              ),
          ]

      def clean(self):
          if self.personas_max is not None and self.personas_max < self.personas_min:
              raise ValidationError({'personas_max': 'Debe ser ≥ personas_min.'})

      def precio_en(self, moneda):
          return self.precio if (moneda or 'MXN').upper() == 'MXN' else self.precio_usd
  ```
- Test: `backend/apps/fleet/tests.py::TransporteTarifaTest`

- [ ] **Paso 1: test que falla** — crear tarifa `redondo_actividad` sin zona → `ValidationError` (CheckConstraint); `recepcion_aeropuerto` con zona → `ValidationError`; `personas_max < personas_min` → `ValidationError`; `precio_en('USD')` con `precio_usd=None` → `None`.
- [ ] **Paso 2:** correr → falla (modelo no existe).
- [ ] **Paso 3:** añadir enum + modelo. `makemigrations fleet`.
- [ ] **Paso 4:** correr → verde (sqlite; el CheckConstraint real se prueba en Postgres en el Gate).
- [ ] **Paso 5:** commit `feat(fleet): modelo TransporteTarifa (catálogo de precios de traslado)`.

### Tarea 1.2 — Migración RLS de `TransporteTarifa`

**Files:**
- Create: `backend/apps/fleet/migrations/00XX_rls_transportetarifa.py` (copia el patrón de `0017_rls_catalogo.py` / `0020_rls_paquetes.py`: `ENABLE ROW LEVEL SECURITY` + política `tenancy_alcance` USING `empresa_id = current_setting('app.current_empresa_id')::int` con el escape para operador de plataforma).
- Modify: `backend/apps/tenancy/tests_rls.py` — añadir `fleet_transportetarifa` a la query/whitelist del guardarraíl (Tarea 8.6 del plan de corrección).
- Test: `backend/apps/fleet/tests.py` — test `# postgres-only`: crear 2 empresas, una tarifa cada una, `scope.con_empresa(e1)` solo ve la suya.

- [ ] **Paso 1: test que falla** (postgres-only) — aislamiento de `TransporteTarifa` por empresa.
- [ ] **Paso 2:** correr contra Postgres → falla (sin política).
- [ ] **Paso 3:** escribir la migración RLS.
- [ ] **Paso 4:** correr contra Postgres → verde.
- [ ] **Paso 5:** commit `feat(fleet): política RLS para TransporteTarifa`.

### Tarea 1.3 — `resolver_tarifa_transporte` (función pura)

**Files:**
- Create: `backend/apps/fleet/tarifa_transporte.py`:
  ```python
  """Resolución de la fila de TransporteTarifa que aplica a una demanda concreta.
  Función pura sobre un queryset ya scopeado por RLS; no calcula dinero (eso es
  estrategias_precio.PorRuta), solo elige la fila."""

  class TarifaTransporteNoConfigurada(Exception):
      pass

  def resolver_tarifa_transporte(tarifas, *, tipo_traslado, zona, personas):
      """`tarifas`: iterable de TransporteTarifa (ya filtrado por empresa+activo).
      Devuelve la fila cuyo tipo/zona coinciden y cuyo rango
      [personas_min, personas_max] contiene `personas`. Lanza
      TarifaTransporteNoConfigurada si no hay ninguna."""
      zona_norm = zona or ''
      for t in tarifas:
          if t.tipo_traslado != tipo_traslado:
              continue
          if t.zona != zona_norm:
              continue
          if personas < t.personas_min:
              continue
          if t.personas_max is not None and personas > t.personas_max:
              continue
          return t
      raise TarifaTransporteNoConfigurada(
          f'No hay tarifa de transporte para tipo={tipo_traslado} zona={zona_norm!r} personas={personas}.'
      )
  ```
- Test: `backend/apps/fleet/tests.py::ResolverTarifaTransporteTest`

- [ ] **Paso 1: test que falla** — con las 5 filas de ejemplo del spec §3.1: `redondo_aeropuerto`+4 personas → fila $4500; +5 → $6000; +14 → $6000; `redondo_actividad`+centro → $1500; +periferia → $1800; `recepcion_aeropuerto` → $2700 para cualquier tamaño; tipo sin fila → `TarifaTransporteNoConfigurada`.
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** escribir la función.
- [ ] **Paso 4:** correr → verde.
- [ ] **Paso 5:** commit `feat(fleet): resolver_tarifa_transporte (elige la fila de tarifa)`.

### Tarea 1.4 — `TransporteTarifaAdmin` + SIDEBAR

**Files:**
- Modify: `backend/apps/fleet/admin.py` — `TransporteTarifaAdmin(EmpresaScopedAdminMixin, ModelAdmin)`; `list_display = ['tipo_traslado', 'zona', 'personas_min', 'personas_max', 'precio', 'precio_usd', 'activo']`; `list_editable = ['precio', 'precio_usd', 'activo']`. Permiso: solo jefes (dato financiero — mismo criterio que `Tarifa`/`CodigoPromocional`; que **no** entre en `setup_roles` para la vendedora).
- Modify: `backend/apps/bookings/setup_roles.py` (o donde viva) — confirmar que `TransporteTarifa` NO se le da a `Vendedora`.
- Modify: `backend/config/settings/base.py` — `UNFOLD['SIDEBAR']`: añadir `TransporteTarifa` en el grupo del catálogo. **Verificar el string exacto del modelo** (`fleet.transportetarifa`) para no tumbar el admin.
- Test: `backend/apps/fleet/tests.py` — la vendedora recibe 403 en `/admin/fleet/transportetarifa/`; el jefe de la Empresa 2 la ve; el jefe de la Empresa 1 no ve filas de la Empresa 2.

- [ ] **Paso 1: test que falla** — permisos del admin de `TransporteTarifa`.
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** registrar el admin, ajustar SIDEBAR, `setup_roles`.
- [ ] **Paso 4:** correr → verde; abrir `/admin/` con runserver y confirmar que no reventó (revisión rápida del propio agente, no del dueño).
- [ ] **Paso 5:** commit `feat(fleet): admin de TransporteTarifa (solo jefes)`.

### Gate Sección 1

- [ ] Suite verde sqlite + Postgres (drop antes).
- [ ] `check --deploy` verde.
- [ ] El guardarraíl de RLS (`tenancy/tests_rls.py`) pasa con `TransporteTarifa` dentro.
- [ ] Commit `docs(plan): SP1 Sección 1 cerrada`. **PARA y reporta.**

---

## SECCIÓN 2 — Estrategia de precio `POR_RUTA`

### Tarea 2.1 — `DemandaPrecio` gana `tipo_traslado` y `zona`

**Files:**
- Modify: `backend/apps/payments/estrategias_precio.py`:
  ```python
  @dataclass(frozen=True)
  class DemandaPrecio:
      personas: int
      moneda: str = 'MXN'
      noches: int = 1
      tipo_traslado: str | None = None
      zona: str | None = None
  ```
- Test: `backend/apps/payments/tests.py` — las estrategias existentes (`PorGrupo`, etc.) siguen funcionando sin pasar los campos nuevos.

- [ ] **Paso 1: test que falla** — construir `DemandaPrecio(personas=2, tipo_traslado='recepcion_aeropuerto')` y que `PorGrupo` la ignore sin romper.
- [ ] **Paso 2:** correr → falla (campo no existe).
- [ ] **Paso 3:** añadir los dos campos opcionales.
- [ ] **Paso 4:** correr toda la suite de `payments` → verde (nada más se rompe).
- [ ] **Paso 5:** commit `feat(payments): DemandaPrecio acepta tipo_traslado y zona`.

### Tarea 2.2 — `EstrategiaPrecio.POR_RUTA` + clase `PorRuta`

**Files:**
- Modify: `backend/apps/fleet/enums.py` — `EstrategiaPrecio.POR_RUTA = 'por_ruta', 'Por ruta (transporte)'`
- Modify: `backend/apps/payments/estrategias_precio.py`:
  ```python
  from apps.fleet.tarifa_transporte import resolver_tarifa_transporte, TarifaTransporteNoConfigurada

  class TipoEstrategiaPrecio(StrEnum):
      ...
      POR_RUTA = 'por_ruta'

  class PorRuta(EstrategiaPrecio):
      """Precio de un traslado: la fila de TransporteTarifa que aplica a
      (tipo_traslado, zona, personas). El precio sale entero de la tabla —
      no usa precio_base ni personas_incluidas del Servicio."""
      clave = TipoEstrategiaPrecio.POR_RUTA

      def calcular_base(self, servicio_config, demanda: DemandaPrecio) -> Decimal:
          tarifas = _obtener_campo(servicio_config, ['tarifas_transporte_activas'])
          if tarifas is None:
              raise ValueError('PorRuta necesita servicio_config.tarifas_transporte_activas')
          if not demanda.tipo_traslado:
              raise ValueError('PorRuta necesita demanda.tipo_traslado')
          try:
              fila = resolver_tarifa_transporte(
                  tarifas, tipo_traslado=demanda.tipo_traslado,
                  zona=demanda.zona, personas=demanda.personas,
              )
          except TarifaTransporteNoConfigurada as e:
              raise ValueError(str(e)) from e
          precio = fila.precio_en(demanda.moneda_normalizada)
          if precio is None:
              raise ValueError(f'La tarifa no tiene precio en {demanda.moneda_normalizada}.')
          return Decimal(precio).quantize(CENTAVOS, rounding=ROUND_HALF_UP)

  REGISTRO_ESTRATEGIAS_PRECIO[TipoEstrategiaPrecio.POR_RUTA] = PorRuta()
  ```
  **Nota de dependencia:** `payments` importa de `fleet` (no al revés). `fleet` no
  importa de `payments`. Sin ciclo.
- Test: `backend/apps/payments/tests.py::PorRutaTest`

- [ ] **Paso 1: test que falla** — `PorRuta().calcular_base(config, demanda)` con una lista de tarifas de prueba: precio correcto por tipo/zona/tamaño en MXN y USD; moneda sin precio → `ValueError`; `tipo_traslado` faltante → `ValueError`; sin fila → `ValueError`.
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** añadir enum + clase + registro.
- [ ] **Paso 4:** correr → verde. `obtener_estrategia_precio('por_ruta')` devuelve `PorRuta`.
- [ ] **Paso 5:** commit `feat(payments): estrategia de precio PorRuta para traslados`.

### Gate Sección 2

- [ ] Suite verde sqlite + Postgres.
- [ ] Commit `docs(plan): SP1 Sección 2 cerrada`. **PARA y reporta.**

---

## SECCIÓN 3 — `Servicio`: tipo transporte, capacidad y ventana horaria

### Tarea 3.1 — `TipoServicio.TRANSPORTE`

**Files:**
- Modify: `backend/apps/fleet/enums.py` — `TipoServicio.TRANSPORTE = 'transporte', 'Transporte / Traslado'`
- Create: migración de fleet (solo `AlterField` de `choices`, no cambia datos)
- Test: `backend/apps/fleet/tests.py` — crear un `Servicio(tipo_servicio='transporte', estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta')` válido.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** añadir el choice, `makemigrations`.
- [ ] **Paso 4:** correr → verde.
- [ ] **Paso 5:** commit `feat(fleet): TipoServicio.TRANSPORTE`.

### Tarea 3.2 — `Servicio.capacidad_maxima`

**Files:**
- Modify: `backend/apps/fleet/models.py` — `Servicio`:
  ```python
  capacidad_maxima = models.PositiveSmallIntegerField(
      null=True, blank=True,
      help_text='Tope de personas por reserva de este servicio. Vacío = usa MAX_PERSONAS (5).',
  )
  ```
- Create: migración `AddField`
- Test: `backend/apps/fleet/tests.py` — default `None`; se puede poner `14`.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2 → 5:** ciclo. Commit `feat(fleet): Servicio.capacidad_maxima`.

### Tarea 3.3 — `Servicio.hora_apertura` / `hora_cierre` + data-migration de pesca La Paz

**Files:**
- Modify: `backend/apps/fleet/models.py` — `Servicio`:
  ```python
  hora_apertura = models.TimeField(null=True, blank=True,
      help_text='Inicio de la ventana horaria de salida. Vacío = sin restricción.')
  hora_cierre = models.TimeField(null=True, blank=True,
      help_text='Fin de la ventana horaria de salida. Vacío = sin restricción.')

  def clean(self):
      super().clean()
      if bool(self.hora_apertura) != bool(self.hora_cierre):
          raise ValidationError('Configura las dos horas de la ventana o ninguna.')
      if self.hora_apertura and self.hora_cierre and self.hora_apertura > self.hora_cierre:
          raise ValidationError({'hora_cierre': 'Debe ser ≥ hora_apertura.'})

  def ventana_horaria(self):
      """(apertura, cierre) o None si el servicio no restringe la hora."""
      if self.hora_apertura and self.hora_cierre:
          return (self.hora_apertura, self.hora_cierre)
      return None
  ```
- Create: migración `AddField` × 2 + **data-migration** que pone `hora_apertura=time(5,0)`,
  `hora_cierre=time(7,0)` en todo `Servicio` con `tipo_servicio='pesca'`. Envolver en
  `alcance_operador_migracion` (RLS). Reversible: `RunPython(forward, backward)` donde
  `backward` limpia los dos campos en los de pesca.
- Test: `backend/apps/fleet/tests.py` — `ventana_horaria()` devuelve `None` sin config, `(5:00, 7:00)` con; `clean()` rechaza una sola hora.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** añadir campos + `clean` + `ventana_horaria` + migración con data-migration.
- [ ] **Paso 4:** correr → verde; `migrate` y verificar que los `Servicio` de pesca quedaron con la ventana (test de la data-migration con `django-test-migrations` o un test que corra `migrate` y consulte).
- [ ] **Paso 5:** commit `feat(fleet): ventana horaria configurable por Servicio`.

### Gate Sección 3

- [ ] Suite verde sqlite + Postgres.
- [ ] Commit `docs(plan): SP1 Sección 3 cerrada`. **PARA y reporta.**

---

## SECCIÓN 4 — Generalizar `Reserva.clean()`

Objetivo: que la ventana 5–7am y el tope `MAX_PERSONAS=5` dejen de estar hardcodeados
para toda reserva. Es una corrección real: hoy un `Servicio` de hospedaje/paseo/transporte
vendido por web se topa con un 400 al pagar por la validación de campo de `hora`.

### Tarea 4.1 — Mover la ventana de salida del validador de campo a `clean()`

**Files:**
- Modify: `backend/apps/bookings/models.py`:
  - Quitar `validators=[validar_ventana_salida]` del campo `Reserva.hora` (queda `hora = models.TimeField()`).
  - En `Reserva.clean()`, añadir:
    ```python
    self._validar_ventana_horaria()

    def _validar_ventana_horaria(self):
        if self.servicio_id:
            ventana = self.servicio.ventana_horaria()
        else:
            ventana = (VENTANA_SALIDA_INICIO, VENTANA_SALIDA_FIN)  # pesca legacy
        if ventana and not (ventana[0] <= self.hora <= ventana[1]):
            raise ValidationError({'hora': f'La hora debe estar entre {ventana[0]:%H:%M} y {ventana[1]:%H:%M}.'})
    ```
  - `validar_ventana_salida` se conserva como helper (lo usan tests / posible reutilización) pero ya no es validador de campo. Actualizar su docstring.
- Create: migración `AlterField` de `Reserva.hora` (quitar el validador — Django genera la migración por el cambio de `validators`).
- Test: `backend/apps/bookings/tests.py::VentanaHorariaTest` — reserva de pesca legacy (sin servicio) a las 06:00 pasa, a las 09:00 falla; reserva con servicio `ventana (14:00, 18:00)` a las 15:00 pasa, a las 06:00 falla; reserva con servicio sin ventana a cualquier hora pasa.

- [ ] **Paso 1: test que falla** — los 3 casos de arriba (el de "servicio sin ventana a las 22:00" falla hoy por el validador de campo).
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** quitar el validador de campo, añadir `_validar_ventana_horaria` a `clean()`, migración.
- [ ] **Paso 4:** correr → verde. **Correr toda la suite de bookings** — hay ~30 tests que crean reservas; los que asumían el 400 por hora fuera de 5–7am sin llamar `full_clean` podrían cambiar. Ajustar los que rompan (deben seguir probando lo mismo vía `clean()`).
- [ ] **Paso 5:** commit `fix(bookings): la ventana horaria de salida es por Servicio, no global`.

### Tarea 4.2 — Tope de personas por servicio

**Files:**
- Modify: `backend/apps/bookings/models.py`:
  - `Reserva.numero_personas` — quitar `MaxValueValidator(MAX_PERSONAS)` del campo (dejar `MinValueValidator(MIN_PERSONAS)`).
  - En `clean()`:
    ```python
    self._validar_tope_personas()

    def _validar_tope_personas(self):
        tope = MAX_PERSONAS
        if self.servicio_id and self.servicio.capacidad_maxima:
            tope = self.servicio.capacidad_maxima
        if self.numero_personas > tope:
            raise ValidationError({'numero_personas': f'Máximo {tope} personas para este servicio.'})
    ```
  - `_validar_capacidad_embarcacion` sigue igual (aplica solo si hay `embarcacion`).
- Create: migración `AlterField` de `numero_personas`.
- Test: `backend/apps/bookings/tests.py` — pesca legacy: 5 pasa, 6 falla; servicio con `capacidad_maxima=14`: 14 pasa, 15 falla; servicio sin `capacidad_maxima`: cae en `MAX_PERSONAS`.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** quitar validador de campo, añadir `_validar_tope_personas`, migración.
- [ ] **Paso 4:** correr suite de bookings → verde (ajustar tests que dependían del `MaxValueValidator` de campo).
- [ ] **Paso 5:** commit `fix(bookings): el tope de personas es por Servicio (capacidad_maxima)`.

### Tarea 4.3 — Auditar que `bajo_demanda` salta panga/capitán/cupo pero exige deslinde

**Files:**
- Modify: `backend/apps/bookings/models.py::Reserva.clean()` — revisar cada `_validar_*`:
  - `_validar_una_salida_por_dia` — envolver en `if self.servicio_id is None or self.servicio.estrategia_cupo == 'por_recurso_dia'`.
  - `_validar_capacidad_embarcacion` — ya es no-op sin `embarcacion`; dejar.
  - `validar_cupo_diario` / `_validar_cupo_de_paquete` / `_validar_cupo_hospedaje` — ya se ramifican por `estrategia_cupo`; confirmar que `bajo_demanda` no llama a ninguna.
  - Deslinde web (`canal_origen == WEB and not deslinde_aceptado`) — **se conserva** para transporte.
- Test: `backend/apps/bookings/tests.py::BajoDemandaCleanTest` — reserva de un `Servicio` `bajo_demanda` sin `embarcacion` ni `CupoDiario`: `full_clean()` pasa; la misma sin `deslinde_aceptado` y `canal_origen='web'`: falla.

- [ ] **Paso 1: test que falla** (si `_validar_una_salida_por_dia` hoy tira para `bajo_demanda`).
- [ ] **Paso 2:** correr → ver el estado real.
- [ ] **Paso 3:** añadir el gate de `estrategia_cupo` donde haga falta.
- [ ] **Paso 4:** correr → verde.
- [ ] **Paso 5:** commit `fix(bookings): clean() de una reserva bajo_demanda no exige panga ni cupo`.

### Tarea 4.4 — Frontend: `dates.ts` deja de asumir 5–7am y MAX 5 universales

**Files:**
- Modify: `frontend/src/lib/dates.ts` — `MAX_PEOPLE` y las constantes de ventana horaria pasan a ser el **default de pesca**; el checkout de pesca los sigue usando, pero se exponen funciones que aceptan override desde el servicio/paquete cargado.
- Modify: las dos dictionaries si algún texto menciona "5 a 7 am" o "hasta 5 personas" de forma que no aplique a otros servicios (el checkout de pesca puede seguir diciéndolo).
- Test: no hay test de unidad de frontend en el repo; `tsc`/`lint`/`build`.

- [ ] **Paso 1:** identificar los usos de `MAX_PEOPLE` y de la ventana horaria en el frontend.
- [ ] **Paso 2:** parametrizar (el checkout de pesca pasa los valores de pesca; `/traslados` pasará los del servicio en la Sección 7).
- [ ] **Paso 3:** `tsc --noEmit` · `lint` · `build` verdes.
- [ ] **Paso 4:** commit `refactor(frontend): el tope de personas y la ventana horaria salen del servicio`.

### Gate Sección 4

- [ ] Suite verde sqlite + Postgres (esta sección toca `Reserva.clean()`, corre TODA la suite).
- [ ] `check --deploy` verde.
- [ ] Frontend `lint` · `tsc` · `build` verdes.
- [ ] Repaso: ningún test de reserva quedó probando "menos" que antes (la ventana y el tope siguen validándose, solo que parametrizados).
- [ ] Commit `docs(plan): SP1 Sección 4 cerrada`. **PARA y reporta.**

---

## SECCIÓN 5 — `bookings.DetalleTransporte`

### Tarea 5.1 — Modelo `DetalleTransporte`

**Files:**
- Modify: `backend/apps/bookings/models.py`:
  ```python
  class DetalleTransporte(models.Model):
      """El traslado que ampara una Reserva de servicio de transporte.
      El recorrido lo define `tipo_traslado`; no hay armador de tramos libre
      (los viajes a medida están fuera del sistema)."""
      reserva = models.OneToOneField(Reserva, on_delete=models.CASCADE, related_name='detalle_transporte')
      tipo_traslado = models.CharField(max_length=25, choices=TipoTraslado.choices)
      punto_encuentro = models.ForeignKey('fleet.PuntoEncuentro', on_delete=models.PROTECT, null=True, blank=True)
      direccion_personalizada = models.CharField(max_length=255, blank=True, default='')
      zona = models.CharField(max_length=10, choices=Zona.choices, blank=True, default='')
      fecha_regreso = models.DateField(null=True, blank=True,
          help_text='Solo redondo_aeropuerto: día de salida al aeropuerto.')
      numero_personas = models.PositiveSmallIntegerField(null=True, blank=True)  # congela CrearPagoView
      precio_calculado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

      def clean(self):
          if bool(self.punto_encuentro_id) == bool(self.direccion_personalizada):
              raise ValidationError('Elige un punto de encuentro del catálogo o escribe una dirección, no ambos ni ninguno.')
          if self.punto_encuentro_id and self.zona and self.zona != self.punto_encuentro.zona:
              raise ValidationError({'zona': 'La zona no coincide con la del punto de encuentro.'})
          reserva = self._reserva_o_ninguna()
          if self.punto_encuentro_id and reserva is not None and self.punto_encuentro.empresa_id != reserva.empresa_id:
              raise ValidationError({'punto_encuentro': 'Ese punto de encuentro pertenece a otra Empresa.'})
          es_actividad = self.tipo_traslado == TipoTraslado.REDONDO_ACTIVIDAD
          if es_actividad and not (self.zona or self.punto_encuentro_id):
              raise ValidationError({'zona': 'El redondo de actividad necesita zona (del hotel o elegida).'})
          es_aeropuerto = self.tipo_traslado == TipoTraslado.REDONDO_AEROPUERTO
          if es_aeropuerto and not self.fecha_regreso:
              raise ValidationError({'fecha_regreso': 'El redondo con aeropuerto necesita fecha de regreso.'})
          if not es_aeropuerto and self.fecha_regreso:
              raise ValidationError({'fecha_regreso': 'Solo aplica al redondo con aeropuerto.'})
          if self.fecha_regreso and reserva is not None and self.fecha_regreso <= reserva.fecha:
              raise ValidationError({'fecha_regreso': 'Debe ser posterior a la fecha de llegada.'})

      def _reserva_o_ninguna(self):
          try:
              return self.reserva
          except Reserva.DoesNotExist:
              return None

      def zona_efectiva(self):
          """La zona que manda al precio: la del hotel si hay hotel, si no la elegida.
          Para tipos que no son redondo_actividad, '' (el precio no depende de zona)."""
          if self.tipo_traslado != TipoTraslado.REDONDO_ACTIVIDAD:
              return ''
          if self.punto_encuentro_id:
              return self.punto_encuentro.zona
          return self.zona
  ```
- Create: migración `CreateModel`.
- Test: `backend/apps/bookings/tests.py::DetalleTransporteTest` — cada rama de `clean()`; `zona_efectiva()` para los 3 tipos.

- [ ] **Paso 1: test que falla** — XOR punto/dirección; zona vs hotel; empresa cruzada; `fecha_regreso` según tipo; `zona_efectiva()`.
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** añadir modelo + migración.
- [ ] **Paso 4:** correr → verde.
- [ ] **Paso 5:** commit `feat(bookings): modelo DetalleTransporte`.

### Tarea 5.2 — RLS de `DetalleTransporte`

**Files:**
- Create: migración RLS. `DetalleTransporte` **no tiene `empresa_id` propio** — llega a empresa vía `reserva.empresa_id`. Patrón: política `USING (EXISTS (SELECT 1 FROM bookings_reserva r WHERE r.id = reserva_id AND r.empresa_id = current_setting(...)::int))`, igual que la que tenía `ReservaExtra` / `ReservaTransporte`. Ver la migración RLS de `ReservaExtra`.
- Modify: `backend/apps/tenancy/tests_rls.py` — añadir `bookings_detalletransporte` a la whitelist de "llega a empresa vía FK".
- Test: `# postgres-only` — dos empresas, una reserva de transporte cada una, aislamiento.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(bookings): política RLS para DetalleTransporte`.

### Tarea 5.3 — `DetalleTransporteInline` en el admin; `Agenda` no lista transporte

**Files:**
- Modify: `backend/apps/bookings/admin.py` — `DetalleTransporteInline(admin.StackedInline)`; en `ReservaAdmin.inlines` reemplazar `ReservaTransporteInline` (ya borrado en 0.4) por el nuevo. Campos `numero_personas`/`precio_calculado` readonly (los congela `CrearPagoView`).
- Modify: `backend/apps/bookings/admin.py` — `Agenda.por_repartir()` / el queryset del proxy: excluir reservas cuyo `servicio.estrategia_cupo == 'bajo_demanda'` o `servicio.tipo_servicio == 'transporte'` (no llevan panga/capitán). Confirmar que `Agenda` filtra por `estado in [PAGADA, ASIGNADA]` y añadir el filtro de tipo.
- Test: `backend/apps/bookings/tests.py` — una reserva de transporte `pagada` NO aparece en `Agenda.por_repartir()`.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(bookings): admin de DetalleTransporte; la agenda ignora traslados`.

### Gate Sección 5

- [ ] Suite verde sqlite + Postgres.
- [ ] Guardarraíl RLS pasa con `DetalleTransporte`.
- [ ] Commit `docs(plan): SP1 Sección 5 cerrada`. **PARA y reporta.**

---

## SECCIÓN 6 — API de traslados

### Tarea 6.1 — `GET /api/<empresa_slug>/traslados/` (catálogo)

**Files:**
- Modify: `backend/apps/fleet/views.py` — `TrasladosView(APIView)` (`permission_classes = []`, `AllowAny`). Resuelve la empresa por `empresa_slug` (mismo patrón que las demás vistas de marketplace, bajo el contexto RLS de esa empresa). Devuelve:
  ```json
  {
    "servicio": {"slug": "...", "nombre": "...", "capacidad_maxima": 14,
                 "porcentaje_anticipo": 100, "empresa_slug": "...",
                 "hora_apertura": null, "hora_cierre": null},
    "tarifas": [{"tipo_traslado": "redondo_aeropuerto", "zona": "",
                 "personas_min": 1, "personas_max": 4, "precio": "4500.00", "precio_usd": null}, ...],
    "puntos_encuentro": [{"id": 1, "nombre": "Hotel X", "zona": "centro"}, ...],
    "publishable_key": "pk_..."
  }
  ```
  404 si la empresa no tiene `Servicio` de transporte activo. 503 si Stripe no configurado (igual que `/api/tarifa/`).
- Modify: `backend/config/urls.py` — montar la ruta.
- Modify: `frontend/src/lib/api.ts` — `getTraslados(empresaSlug): Promise<TrasladosCatalogo>`.
- Test: `backend/apps/fleet/tests.py::TrasladosViewTest` — la Empresa 2 devuelve su catálogo; una empresa sin servicio de transporte → 404; RLS: no se filtran tarifas de otra empresa.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2 → 5:** ciclo. Commit `feat(fleet): endpoint GET /api/<empresa>/traslados/`.

### Tarea 6.2 — `TrasladoCheckoutSerializer` + `POST /api/<empresa_slug>/reservas/` para transporte

**Files:**
- Modify: `backend/apps/bookings/serializers.py` — `TrasladoCheckoutSerializer` (o extender `ReservaCheckoutSerializer` con una rama por `tipo_servicio`). Acepta: `checkout_id`, `servicio` (slug), `tipo_traslado`, `punto_encuentro` (id) | `direccion_personalizada` (+`zona` si `redondo_actividad`), `fecha`, `hora`, `fecha_regreso` (si `redondo_aeropuerto`), `numero_personas`, datos del cliente, `deslinde_aceptado`, `deslinde_nombre`, `moneda`, `forma_pago`, `ref` (opcional).
  - Crea `Reserva(servicio=<transporte>, empresa=<empresa del servicio>, estado=PENDIENTE_PAGO, canal_origen='web')` + `DetalleTransporte`. `zona` del `DetalleTransporte` se deriva del `punto_encuentro` si viene del catálogo (nunca se confía la del cliente).
  - No ocupa cupo. `full_clean()` antes de `save()` (motor de validación).
- Modify: `backend/apps/bookings/views.py` — la vista de creación de reservas enruta a este serializer cuando el servicio es de transporte.
- Modify: `frontend/src/lib/api.ts` — `crearReservaTraslado(empresaSlug, payload)`.
- Test: `backend/apps/bookings/tests.py::TrasladoCheckoutTest` — crea reserva + detalle; zona derivada del hotel ignora la que mande el cliente; deslinde obligatorio; `numero_personas` > `capacidad_maxima` → 400.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2 → 5:** ciclo. Commit `feat(bookings): checkout de reserva de traslado`.

### Tarea 6.3 — `CrearPagoView` calcula el precio de un traslado con `PorRuta`

**Files:**
- Modify: `backend/apps/payments/views.py` (`CrearPagoView`) — cuando `reserva.servicio.estrategia_precio == 'por_ruta'`:
  - Arma `servicio_config` con `tarifas_transporte_activas` = `list(reserva.servicio.empresa.tarifas_transporte.filter(activo=True))` (bajo RLS de esa empresa).
  - Arma `DemandaPrecio(personas=reserva.numero_personas, moneda=reserva.moneda, tipo_traslado=reserva.detalle_transporte.tipo_traslado, zona=reserva.detalle_transporte.zona_efectiva())`.
  - `precio_base = obtener_estrategia_precio('por_ruta').calcular_base(servicio_config, demanda)`.
  - **Congela** `reserva.detalle_transporte.numero_personas` y `.precio_calculado`; `reserva.precio_total`, `reserva.forma_pago`; aplica `reserva.servicio.porcentaje_anticipo` vía `monto_inicial`.
  - Crea el PaymentIntent en la cuenta Stripe de la empresa del servicio (`stripe_client` por empresa, ya existe). Idempotente igual que hoy.
  - `_verificar_monto` en el webhook recalcula con la misma demanda (lee del `DetalleTransporte` congelado).
- Test: `backend/apps/payments/tests.py::CrearPagoTrasladoTest` — total correcto por tipo/zona/tamaño; congela detalle; anticipo 100% del servicio de transporte; idempotencia (segunda llamada no crea intent nuevo); `_verificar_monto` cuadra.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2 → 5:** ciclo. Commit `feat(payments): CrearPagoView cotiza traslados (PorRuta)`.

### Tarea 6.4 — Webhook: una reserva de traslado pagada no reserva cupo

**Files:**
- Modify: `backend/apps/bookings/cupo/confirmacion.py::reservar_cupo_al_confirmar` — Caso C ya cubre `bajo_demanda` directo (no hace nada). Añadir test explícito para transporte.
- Modify: `backend/apps/notifications/services.py` — que la notificación de una reserva de transporte diga lo correcto (punto de encuentro / tipo de traslado, no "capitán/panga"). Si la plantilla de WhatsApp no aplica, el correo alcanza.
- Test: `backend/apps/payments/tests.py` — webhook de una reserva de traslado → `pagada`, sin `ReservaOcupacion` ni `ReservaPaqueteComponente`, notificación disparada sin romper.

- [ ] **Paso 1: test que falla / confirma.**
- [ ] **Paso 2 → 5:** ciclo. Commit `feat(notifications): aviso de reserva de traslado`.

### Gate Sección 6

- [ ] Suite verde sqlite + Postgres.
- [ ] `check --deploy` verde.
- [ ] Prueba manual del agente (runserver + curl): `GET /api/<empresa2>/traslados/` devuelve catálogo; `POST` crea reserva; `crear-pago` cotiza. (Sin navegador.)
- [ ] Commit `docs(plan): SP1 Sección 6 cerrada`. **PARA y reporta.**

---

## SECCIÓN 7 — Frontend `/traslados`

### Tarea 7.1 — Ruta y server component

**Files:**
- Create: `frontend/src/app/[lang]/traslados/page.tsx` — server component. `await params`, `getDictionary(lang)`, fetch a `getTraslados(<empresa 2 slug>)`. Si 404 / 503 → estado "no disponible" (igual que el checkout de pesca cuando falla `/api/tarifa/`).
- Create: `frontend/src/app/[lang]/traslados/loading.tsx`.
- Modify: `frontend/src/app/[lang]/dictionaries/{es,en}.json` — bloque `traslados.*` (títulos, descripción de cada tipo de recorrido, labels, textos de error). Reiniciar `npm run dev`.
- Test: `tsc --noEmit` · `lint` · `build`.

- [ ] **Paso 1:** crear ruta + loading + claves de diccionario.
- [ ] **Paso 2:** `tsc` · `lint` · `build` verdes.
- [ ] **Paso 3:** commit `feat(frontend): ruta /traslados con catálogo server-side`.

### Tarea 7.2 — `traslado-view.tsx` (checkout recortado)

**Files:**
- Create: `frontend/src/components/traslado-view.tsx` — client component. Reutiliza `checkout-section-card`, `checkout-stepper`, `checkout-footer`, el bloque de datos del cliente y el deslinde de `checkout-view.tsx` (extraer a componentes compartidos si hoy están inline). Pasos:
  1. Tipo de traslado (3 tarjetas, precio de `catalogo.tarifas`).
  2. Hospedaje: `<FieldPopover>` con los `puntos_encuentro`, o "otra dirección" (texto + selector de zona solo si `redondo_actividad`).
  3. Fechas: `DateField` para `fecha` y, si `redondo_aeropuerto`, `fecha_regreso`. `TimeField` sin restricción 5–7am (el servicio de transporte no tiene ventana). Nada de `<input type="date">` ni `<select>` nativos.
  4. Personas: número simple, tope = `catalogo.servicio.capacidad_maxima`.
  5. Datos del cliente + deslinde + `PaymentElement`.
- El precio mostrado se pide al backend (cotización server-side) y se re-congela en `crear-pago`. Nunca se calcula en el cliente.
- Modify: `frontend/src/app/[lang]/traslados/page.tsx` — montar `<TrasladoView>`.
- Modify: `frontend/src/lib/ref.ts` usage — el `?ref=` ya se captura global (`RefCapture` en el layout); solo hay que mandarlo en `crearReservaTraslado`.
- Test: `tsc` · `lint` · `build`.

- [ ] **Paso 1:** construir el componente reutilizando lo que ya existe.
- [ ] **Paso 2:** `tsc` · `lint` · `build` verdes.
- [ ] **Paso 3:** commit `feat(frontend): checkout de traslados`.

### Tarea 7.3 — Enlace a `/traslados` desde el catálogo / navegación

**Files:**
- Modify: `frontend/src/app/[lang]/catalogo/` o el nav — un punto de entrada visible a `/traslados` para la sede La Paz. Perception-First: es un servicio suelto secundario, no domina la página.
- Modify: dictionaries si hace falta el label.
- Test: `tsc` · `lint` · `build`.

- [ ] **Paso 1 → 3:** ciclo. Commit `feat(frontend): enlace a /traslados en el catálogo`.

### Gate Sección 7

- [ ] Frontend `lint` · `tsc --noEmit` · `build` verdes.
- [ ] El agente arranca `npm run dev` + backend y confirma que `/es/traslados` renderiza el catálogo real (revisión propia, no del dueño). El dueño hace la verificación visual final.
- [ ] Commit `docs(plan): SP1 Sección 7 cerrada`. **PARA y reporta.**

---

## SECCIÓN 8 — Cierre SP1

- [ ] **8.1** `manage.py test apps config` verde en sqlite Y Postgres (drop antes).
- [ ] **8.2** `check --deploy --fail-level WARNING` con `config.settings.production` + env de relleno.
- [ ] **8.3** Frontend `npm.cmd run lint` · `npx.cmd tsc --noEmit` · `npm.cmd run build` verdes.
- [ ] **8.4** Repaso de diffs: ninguna cifra fuera de `payments/`; ningún `como_operador_plataforma()` en vista `AllowAny`; `TransporteTarifa` y `DetalleTransporte` con RLS + en el guardarraíl de `tenancy/tests_rls.py`; cero referencias a `ReservaTransporte`/`TransportePrecio`/`cargo_por_transporte`.
- [ ] **8.5** Actualizar `backend/CLAUDE.md` — sección nueva "Transporte como servicio": `TransporteTarifa`, `PorRuta`, `DetalleTransporte`, ventana horaria por servicio, `capacidad_maxima`, la ruta `/api/<empresa>/traslados/`. Actualizar la nota de "Gotchas" sobre `validar_ventana_salida` (ya no es validador de campo). Actualizar `frontend/CLAUDE.md` — ruta `/traslados`.
- [ ] **8.6** Actualizar `docs/superpowers/specs/2026-08-31-...-ADRs.md` — ADR-004 Revisión 2 (`POR_RUTA`) pasa de "pendiente" a implementada.
- [ ] **8.7** Sembrar catálogo de prueba en local: `Servicio` de transporte de la Empresa 2 + las 5 filas de `TransporteTarifa` del spec §3.1 + unos `PuntoEncuentro`. Añadir al comando `seed_local_demo` o a un `seed_transporte`.
- [ ] **8.8** Memoria (`C:\Users\kkjf\.claude\projects\C--Users-kkjf-desarrollo-sistema-pescadeportiva\memory\`): actualizar `plan-transporte-multi-empresa` — SP1 hecho, pendiente SP2. Anotar en `pendientes-manuales-produccion` los pasos de producción: crear el `Servicio` de transporte real, cargar `TransporteTarifa` reales, cargar `PuntoEncuentro` reales, poner `porcentaje_anticipo` del servicio.
- [ ] **8.9** Resumen para el dueño: qué migraciones corren y en qué orden; qué se carga a mano en el admin; qué queda para SP2.
- [ ] **8.10** Commit `docs(plan): SP1 completado`. **PARA. SP2 arranca con su propio plan y luz verde del dueño.**

---

## Autorrevisión (para el que ejecuta, al terminar cada sección)

1. **¿El test que escribiste falla ANTES de la implementación?** Si nunca lo viste rojo, no sabes si prueba algo.
2. **¿Corriste Postgres, no solo sqlite?** sqlite no tiene RLS, ni locks, ni CheckConstraint real.
3. **¿Dropeaste `test_pescadeportiva_test` antes del run de Postgres?**
4. **¿El commit tiene SOLO los archivos de esa tarea?** `git status` antes de `git add`.
5. **¿Rompiste algún test existente?** El gate de sección corre `test apps config` entero por eso. La Sección 4 (toca `Reserva.clean()`) es la de mayor riesgo de regresión.
6. **¿Alguna cifra de dinero se coló fuera de `apps/payments/`?**
