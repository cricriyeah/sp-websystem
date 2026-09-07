# Corrección de hallazgos multi-sede — Tareas ejecutables

> **Para el agente que ejecuta:** este documento es autosuficiente. NO necesitas
> re-derivar diseño. Haz las tareas **en orden**, una por una, con su ciclo
> completo (test que falla → código → test verde → commit). Cada tarea termina
> con un commit. Si una tarea te obliga a tomar una decisión de producto que
> este documento no contempla: **para y pregunta**, no adivines.
>
> **RITMO — PARA AL FINAL DE CADA SECCIÓN.** Haz TODAS las tareas de una sección
> (2, luego 3, luego 4...), corre el **Gate** de esa sección (suite completa en
> sqlite Y en Postgres), y **DETENTE**. Reporta: `git log --oneline` de la
> sección, resultado de ambos gates, y cualquier decisión que hayas tomado o
> duda que tengas. **No arranques la siguiente sección** hasta que te den luz
> verde. Los errores que no se revisan se acumulan sección tras sección.
>
> **Empieza por la Tarea 2.1.** Estado actual: Secciones 0, 0.8 y 1 ya hechas y
> commiteadas; `manage.py test apps config` = 676 verdes en sqlite y Postgres.

**Objetivo:** conectar las piezas 3-6 de la expansión multi-sede (servicios por
capas, precios tipados, cupo multidía/hospedaje, paquetes) al flujo real de
compra, y cerrar los bugs de la revisión.

**Arquitectura:** Django 6 + DRF, Postgres con Row-Level Security (RLS) por
`empresa_id`, núcleos puros + adaptadores + wiring (patrón ya establecido en el
repo). Frontend Next.js 16 (Turbopack). Stripe cuenta estándar por empresa (sin
Connect).

**Stack:** Python 3.14, Django, djangorestframework, psycopg 3, stripe-python
(client `StripeClient`), Next.js 16, `@stripe/react-stripe-js`.

**Docs base (leer si algo no cuadra):**
- `docs/superpowers/plans/2026-09-05-correccion-hallazgos-expansion-multi-sede.md` — plan de alto nivel + **Decisiones del dueño** (frozen) + Registro de avance.
- `docs/superpowers/specs/2026-08-31-expansion-multi-sede-design.md` y `...-ADRs.md` — diseño original.
- `backend/CLAUDE.md` — reglas del backend (cupo, cobro, finanzas). **Léelo entero antes de tocar pagos o cupo.**

---

## Estado al empezar (2026-09-06)

Rama: `fix/expansion-multi-sede-hallazgos` (worktree en `.claude/worktrees/pieza1-tenancy-sdd`).
Ya hecho y commiteado: Secciones 0, 0.8 (retrofit de tests para RLS) y 1 (C1, C2, bug de `scope._con_alcance`). **`manage.py test apps config` = 676 verdes en sqlite Y en Postgres.**

Único cambio sin commitear: `backend/apps/bookings/cupo/nucleo.py` (tarea 2.1, ya hecha) — se commitea en la Tarea 2.1 de abajo.

---

## Constraints globales (aplican a TODA tarea)

1. **Un commit por tarea.** Mensaje en español, prosa normal (no caveman), termina con:
   ```
   Co-Authored-By: <tu firma>
   ```
2. **Nada de lógica ni cifras de dinero fuera de `backend/apps/payments/pricing.py`.** El resto del código pasa primitivos, no calcula.
3. **RLS es fail-closed.** Ninguna consulta nueva puede depender solo del filtro del ORM. Nunca `scope.como_operador_plataforma()` dentro de una vista pública (`permission_classes = []` / `AllowAny`). Para cruzar empresas: iterar `scope.con_empresa(e)` por empresa, o una función Postgres `SECURITY DEFINER` explícita.
4. **`MXN` y `USD` siempre por separado, nunca sumados.** No hay tipo de cambio. Cada precio nuevo lleva su hermano `_usd` (nullable).
5. **`TextChoices`** para cualquier enum nuevo o convertido.
6. **Cada modelo nuevo con `empresa_id` (o que llegue a empresa vía FK) necesita** una migración de política RLS (patrón: copia de `backend/apps/fleet/migrations/0017_rls_catalogo.py` o `0020_rls_paquetes.py`). La lista consolidada de verificación se crea en la Tarea de la Sección 8 (B8); mientras tanto, cada tabla nueva lleva su propio test `# postgres-only` de aislamiento.
7. **Toda data migration que haga `Modelo.objects.create/update/delete` sobre una tabla con RLS** debe envolverse en `with alcance_operador_migracion(schema_editor.connection):` (helper en `backend/apps/tenancy/rls.py`).
8. **No romper la garantía del cobro** (ver `backend/CLAUDE.md`, sección "Garantías del cobro"): el webhook es la única fuente de verdad, idempotencia, congelado de precio al pagar, `_verificar_monto` no rebota.

---

## Entorno y comandos (Windows, PowerShell o Bash)

- Python del venv: `backend/venv/Scripts/python.exe` (todos los comandos `manage.py` corren desde `backend/`).
- **Postgres para pruebas** (contenedor Docker `psd-pg`, puerto host 5433, rol `ci_rls`):
  ```bash
  # si no está corriendo:
  docker run -d --name psd-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=pescadeportiva_test -p 5433:5432 postgres:17
  docker exec psd-pg psql -U postgres -d pescadeportiva_test -v ON_ERROR_STOP=1 -c \
    "CREATE ROLE ci_rls LOGIN PASSWORD 'ci_rls_password_local' NOSUPERUSER NOBYPASSRLS CREATEDB;"
  ```
- **Correr la suite en sqlite** (rápido, NO prueba RLS/locks/constraints):
  ```
  cd backend && venv/Scripts/python.exe manage.py test apps config
  ```
- **Correr la suite en Postgres** (obligatorio antes de cerrar cada sección):
  ```bash
  docker exec psd-pg psql -U postgres -c "DROP DATABASE IF EXISTS test_pescadeportiva_test;"
  cd backend && DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test \
    DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 \
    venv/Scripts/python.exe manage.py test apps config --noinput
  ```
  Para un archivo puntual: reemplaza `apps config` por `apps.bookings.tests_X`.
- **NUNCA uses `--keepdb` entre iteraciones.** Un run interrumpido deja la base a medias y aparecen errores fantasma. Siempre `DROP DATABASE` antes de un run limpio.
- **Frontend** (desde `frontend/`): `npm.cmd run lint` · `npx.cmd tsc --noEmit` · `npm.cmd run build`.

---

## Trampas conocidas (ya me mordieron; NO repetir)

| Trampa | Regla |
|---|---|
| Un test que hace `Modelo.objects.create(empresa=...)` en `TestCase` normal → en Postgres revienta con «new row violates row-level security policy». | Test de UNA empresa → hereda de `apps.testing.EmpresaTestCase` (o `ApiTestCase` si usa `self.client`). Test que abarca varias empresas y NO prueba aislamiento RLS → hereda de `apps.testing.OperadorTestCase`. Test que SÍ prueba aislamiento RLS → `TransactionTestCase` + `with scope.con_empresa(e):` explícito por empresa, `# postgres-only` con `@skipUnless(connection.vendor == 'postgresql', ...)`. |
| `scope.con_empresa(a)` dentro de `scope.con_empresa(b)` con `b != a` → `RuntimeError` (no es reentrante). | Sal de un alcance antes de entrar a otro. En tests A/B usa el helper `_AlcanceOtraEmpresa` de `apps/fleet/tests.py` (cópialo si lo necesitas en otro archivo) o `OperadorTestCase`. |
| `crear_flota(empresa)` (`apps/testing.py`) ya respeta un alcance abierto: solo abre `con_empresa` si `connection.alcance_actual is None`. | No lo envuelvas tú en otro `con_empresa`. |
| Mock de Stripe con `@mock.patch('apps.payments.services.stripe.Refund.create')` → NO intercepta nada (el código usa `StripeClient`). | Usa `@mock.patch.object(StripeClient, 'refunds')` / `@mock.patch.object(StripeClient, 'payment_intents')` (importa `from stripe import StripeClient`). El mock recibido es el objeto `refunds`; asertas sobre `mock.create.assert_called_once()`. |
| `SET LOCAL` (lo que hace `con_empresa`) requiere una transacción abierta. | En un management command, cada iteración `with scope.con_empresa(e):` abre su propia `transaction.atomic()` — ok. En un test `TransactionTestCase`, `setUp` debe abrir el `with` explícito. |
| Un constraint de Postgres en `bookings_reservaocupacion` NO puede referenciar `bookings_reserva.estado`. | Por eso `ReservaOcupacion` gana una columna denormalizada `ocupa_cupo` (bool), mantenida por `Reserva.save()`. El `EXCLUDE` filtra `WHERE (ocupa_cupo)`. |
| `EXCLUDE USING gist` sobre `daterange` necesita la extensión `btree_gist`. | La migración hace `CREATE EXTENSION IF NOT EXISTS btree_gist;` (guard `vendor == 'postgresql'`). |
| Serializer DRF descarta campos que no están en `Meta.fields` **en silencio**. | Al agregar un campo al checkout, agrégalo a `Meta.fields` Y a `validate()`/`create()`/`update()`. |

---

## File Map

| Archivo | Responsabilidad | Secciones |
|---|---|---|
| `backend/apps/fleet/models.py` | `Servicio` gana enums + `porcentaje_anticipo`; `PaqueteServicio.clean` bloquea cruza-empresa | 2, 4 |
| `backend/apps/fleet/enums.py` **(nuevo)** | `TextChoices`: `TipoServicio`, `EstrategiaCupo`, `EstrategiaPrecio`, `ModoOcupacion` — una sola fuente de verdad | 2 |
| `backend/apps/bookings/cupo/registro.py` | Registro de estrategias llaveado por `estrategia_cupo` (no `tipo_servicio`) | 2 |
| `backend/apps/bookings/cupo/candado.py` | `bloquear_cupo` re-llaveado por `(empresa, servicio_id, fecha)` sin colisión con el path pesca | 2 |
| `backend/apps/bookings/cupo/nucleo.py` | `tope=None`, `validar_rango`, `elegir_recursos` (función pura) | 2, 6 |
| `backend/apps/bookings/models.py` | `Reserva.clean` resuelve estrategia por `servicio.estrategia_cupo`; `ReservaOcupacion.ocupa_cupo`; `Reserva.save` mantiene `ocupa_cupo` | 2, 3, 5, 6 |
| `backend/apps/bookings/models_paquete_componente.py` **(nuevo, o dentro de models.py)** | `ReservaPaqueteComponente`, `ReservaPaqueteServicioRemovido`, `ReservaPaquetePersonalizacion` | 5, 6 |
| `backend/apps/bookings/migrations/00XX_*` | FK + enums + `ocupa_cupo` + `EXCLUDE` + tablas de checkout de paquete + políticas RLS | 2, 3, 5, 6 |
| `backend/apps/payments/pricing.py` | `precio_paquete_total()`, `monto_inicial(..., porcentaje)` | 4 |
| `backend/apps/payments/estrategias_precio.py` | (sin cambio estructural; ya soporta `noches`) | 4 |
| `backend/apps/payments/views.py::CrearPagoView` | 3 ramas de precio (paquete / servicio+noches / legacy); anticipo por servicio | 4, 5 |
| `backend/apps/payments/services.py::aplicar_pago_exitoso` | crea el cupo de cada componente/servicio multidía al confirmar; reembolso si algo se llenó | 6 |
| `backend/apps/bookings/serializers.py::ReservaCheckoutSerializer` | acepta `servicio`, `paquete`, `fecha_salida`, `servicios_removidos`, `personalizaciones` | 5 |
| `backend/apps/fleet/views.py` + `catalogo.py` | `PaqueteDetailView` (resuelve slug→objeto) | 5 |
| `backend/apps/tenancy/tests_rls.py` | lista consolidada de tablas con RLS (mantener al día) | 2, 3, 5, 6 |
| `frontend/src/lib/api.ts` | tipos + `guardarReserva` con campos nuevos; `getPaqueteDetalle` | 5 |
| `frontend/src/lib/pricing-paquete.ts` | fórmula de precio de paquete alineada con backend | 5 |
| `frontend/src/app/[lang]/reservar/page.tsx` + `components/checkout-view.tsx` + `paquete-card.tsx` | pasan servicio/paquete/fecha_salida/selección al checkout | 5 |
| `docs/superpowers/specs/2026-09-06-ADR-005-paquetes-cruza-empresa.md` **(nuevo)** | planteo del problema, fuera de v1 | 7 |
| `backend/config/settings/base.py` | import perezoso de `scope` en lambdas de UNFOLD | 8 |
| `backend/apps/tenancy/admin_mixins.py` | jefe no edita usuarios ajenos | 8 |

<!-- arch-critic: omitido a propósito — el diseño ya está validado en la práctica (Secciones 0/0.8/1 construidas y verdes en Postgres); las trampas de acoplamiento (RLS, reentrancia de scope, GUC) ya se toparon y resolvieron. -->

---

# SECCIÓN 2 — Cupo: resolver la estrategia por `estrategia_cupo` (no `tipo_servicio`)

**Problema:** `Servicio.estrategia_cupo` y `Servicio.modo_ocupacion` son **campos muertos** —
el cupo se resuelve por `tipo_servicio` vía `REGISTRO_ESTRATEGIAS`, y las claves ni coinciden
(`estrategia_cupo` default `'por_recurso_dia'` no existe en el registro). El advisory lock se
llavea por `tipo_servicio` (string) en vez de por servicio real.

**Valores de enum (Decisión 5, frozen — alineados a lo que ya siembra `fleet/0018`):**
`TipoServicio`: `pesca`/`paseo`/`hospedaje`/`bajo_demanda` · `EstrategiaCupo`: `por_recurso_dia`/`por_noche`/`bajo_demanda` · `EstrategiaPrecio`: `por_grupo`/`por_persona`/`tarifa_fija`/`por_noche` · `ModoOcupacion`: `exclusivo`/`compartido`

---

### Tarea 2.1 — Commit del cambio ya hecho en `nucleo.py`

`backend/apps/bookings/cupo/nucleo.py` ya está modificado en disco: `ocupacion_por_rango` usa
`topes_por_fecha.get(fecha)` (default `None`, antes `0`); `motivo_sin_lugar` exclusivo trata
`tope=None` como "sin tope"; nueva fn pura `validar_rango(fecha_inicio, fecha_fin) -> str | None`.

1. `cd backend && git diff apps/bookings/cupo/nucleo.py` — confirma que es solo eso.
2. Añade a `apps/bookings/cupo/tests_cupo_nucleo.py`:
   - `test_ocupacion_por_rango_sin_tope_no_marca_lleno`: `ocupacion_por_rango(fechas=[f], grupos_por_fecha={f:[3]}, capacidades_por_fecha={f:[5,3]}, topes_por_fecha={}, personas=3, modo=MODO_EXCLUSIVO)` → `{f: None}`.
   - `test_validar_rango`: `(1/1, 1/3)→None`, `(1/3, 1/3)→str`, `(1/3, 1/1)→str`, `(None, 1/1)→None`.
3. `venv/Scripts/python.exe manage.py test apps.bookings.cupo.tests_cupo_nucleo` → PASS.
4. Commit: `fix(cupo): núcleo trata tope ausente como 'sin tope' + validar_rango`.

---

### Tarea 2.2 — Enums de `Servicio` en `apps/fleet/enums.py`

**Files:** Create `backend/apps/fleet/enums.py` · Modify `backend/apps/fleet/models.py` (`Servicio`) · migración `fleet/0021_servicio_enums_y_anticipo` · Test `apps/fleet/tests_servicio_enums.py`.

**Produce:** `apps.fleet.enums.{TipoServicio, EstrategiaCupo, EstrategiaPrecio, ModoOcupacion}` (todas `models.TextChoices`) + `Servicio.porcentaje_anticipo: PositiveSmallIntegerField(default=30)`.

1. **Crea `apps/fleet/enums.py`** con las 4 `TextChoices` (valores exactos de arriba; el `label` de cada una es texto libre en español).
2. **Test que falla** (`apps/fleet/tests_servicio_enums.py`, hereda de `apps.testing.EmpresaTestCase`):
   - `test_campos_usan_choices`: para cada uno de los 4 campos, `set(dict(Servicio._meta.get_field(c).choices)) == set(Enum.values)`.
   - `test_defaults`: `get_field('tipo_servicio').default == 'pesca'`, `estrategia_cupo == 'por_recurso_dia'`, `estrategia_precio == 'por_grupo'`, `modo_ocupacion == 'exclusivo'`.
   - `test_porcentaje_anticipo`: `Servicio.objects.create(empresa=self.empresa, nombre='X', slug='x', precio_base=Decimal('100')).porcentaje_anticipo == 30`.
3. Run → FAIL.
4. **Modifica `Servicio`** (import `from .enums import ...` arriba del archivo): los 4 campos pasan a `models.CharField(max_length=20, choices=<Enum>.choices, default=<Enum>.<VALOR>)`; añade `porcentaje_anticipo = models.PositiveSmallIntegerField(default=30, help_text='% del total que se cobra en línea. 30=anticipo, 100=completo.')`.
5. `venv/Scripts/python.exe manage.py makemigrations fleet --name servicio_enums_y_anticipo` → renómbrala a `0021_...`. Debe ser `AlterField`×4 + `AddField`. **Sin data migration** (los valores sembrados por 0018 ya son válidos).
6. sqlite: `test apps.fleet.tests_servicio_enums` → PASS.
7. Postgres (drop + `test apps.fleet apps.bookings.cupo --noinput`) → OK.
8. Commit: `feat(fleet): Servicio con enums tipados + porcentaje_anticipo configurable`.

---

### Tarea 2.3 — Registro de estrategias de cupo por `estrategia_cupo`

**Files:** Modify `backend/apps/bookings/cupo/registro.py` · Test `apps/bookings/tests_cupo_estrategias.py`.

**Produce:** `obtener_estrategia(clave: str) -> EstrategiaCupo`. `clave` = valor de `EstrategiaCupo`. Default `'por_recurso_dia'` con `logging.warning` si la clave es desconocida.

1. **Test que falla** (`SimpleTestCase`): `obtener_estrategia('por_recurso_dia')→PorRecursoDia`, `'por_noche'→PorNoche`, `'bajo_demanda'→BajoDemanda`; `obtener_estrategia('inexistente')` emite `WARNING` en el logger `apps.bookings.cupo.registro` y devuelve `PorRecursoDia`.
2. Run → FAIL.
3. **Reemplaza `registro.py` entero:**
   ```python
   """Registro de estrategias de cupo, llaveado por Servicio.estrategia_cupo."""
   import logging
   from .estrategias import BajoDemanda, EstrategiaCupo, ModoOcupacion, PorNoche, PorRecursoDia

   logger = logging.getLogger(__name__)
   REGISTRO_ESTRATEGIAS: dict[str, EstrategiaCupo] = {
       'por_recurso_dia': PorRecursoDia(modo=ModoOcupacion.EXCLUSIVO),
       'por_noche': PorNoche(),
       'bajo_demanda': BajoDemanda(),
   }
   _DEFAULT = 'por_recurso_dia'

   def registrar_estrategia(clave: str, estrategia: EstrategiaCupo) -> None:
       REGISTRO_ESTRATEGIAS[clave] = estrategia

   def obtener_estrategia(clave: str = _DEFAULT) -> EstrategiaCupo:
       est = REGISTRO_ESTRATEGIAS.get(clave)
       if est is None:
           logger.warning('estrategia_cupo desconocida %r, se usa %r', clave, _DEFAULT)
           est = REGISTRO_ESTRATEGIAS[_DEFAULT]
       return est
   ```
   (El `modo_ocupacion` es un eje aparte: `PorRecursoDia` lo lee de `DemandaCupo.modo` en tiempo de evaluación. Aquí solo se registra el modo por defecto.)
4. Run → PASS.
5. Commit: `fix(cupo): registro de estrategias llaveado por estrategia_cupo, no tipo_servicio`.

---

### Tarea 2.4 — `Reserva.clean` y funciones de cupo usan `servicio.estrategia_cupo`

**Files:** Modify `backend/apps/bookings/models.py` (`proxima_fecha_disponible`, `disponibilidad_por_fecha`, `evaluar_cupo`, `validar_cupo_diario`, `Reserva.clean`) · `apps/bookings/views.py` (confirmar 3 call sites) · Test en `tests_cupo_estrategias.py`.

1. **Test de regresión** (`EmpresaTestCase`, con `crear_flota(self.empresa)` en setUp y un `Servicio(tipo_servicio='pesca', estrategia_cupo='por_recurso_dia')`):
   - `test_reserva_de_servicio_pesca_valida_cupo`: `Reserva(..., servicio=self.servicio_pesca, estado=PAGADA).full_clean()` no revienta.
   - `test_reserva_legacy_sin_servicio_sigue_validando`: igual sin `servicio`.
   Run → PASS ya (fijan que el refactor no rompe).
2. **Refactor en `models.py`:**
   - Renombra el parámetro `tipo_servicio='pesca'` → `estrategia_cupo='por_recurso_dia'` en las 4 funciones; pásalo a `obtener_estrategia(estrategia_cupo)`.
   - Añade parámetro `servicio_id=None` a `evaluar_cupo` y `validar_cupo_diario`; `validar_cupo_diario` llama `bloquear_cupo(empresa.pk, fecha, servicio_id=servicio_id)` (ver 2.5).
   - En `Reserva.clean`, reemplaza el bloque `tipo_srv = self.servicio.tipo_servicio if self.servicio_id else 'pesca'` + `validar_cupo_diario(..., tipo_servicio=tipo_srv)` por:
     ```python
     estrategia_cupo = self.servicio.estrategia_cupo if self.servicio_id else 'por_recurso_dia'
     # TODO Sección 5: rama por_noche (hospedaje) — necesita fecha_salida en el serializer.
     validar_cupo_diario(
         self.fecha, self.numero_personas, self.empresa,
         excluir_pk=self.pk, estrategia_cupo=estrategia_cupo, servicio_id=self.servicio_id,
     )
     ```
   - **NO cablees la rama `por_noche` todavía** — hasta Sección 5 ningún flujo público crea reservas con servicio hospedaje, así que la rama de un día es inofensiva.
3. `apps/bookings/views.py` (~57, ~67, ~133): las llamadas del endpoint `/api/<empresa>/cupo/` son pesca legacy — déjalas con el default (`'por_recurso_dia'`, sin `servicio_id`). Solo confirma que compilan.
4. sqlite: `test apps.bookings` → OK.
5. Commit: `fix(cupo): Reserva.clean resuelve la estrategia por servicio.estrategia_cupo`.

---

### Tarea 2.5 — Advisory lock por `(empresa, servicio_id, fecha)` sin colisión

**Files:** Modify `backend/apps/bookings/cupo/candado.py` + `models.py::validar_cupo_diario` · Test `apps/bookings/tests_cupo_candado.py`.

**Produce:** `bloquear_cupo(empresa_id, fecha, servicio_id: int | None = None)`. `servicio_id=None` → key2 = `fecha.toordinal()` (compat pesca legacy). `servicio_id` int → key2 = `(crc32(f'{servicio_id}:{ordinal}') & 0x3FFFFFFF) | 0x40000000` — **bit 30 forzado → nunca colisiona** con un `toordinal()` realista.

1. **Test que falla** (`SimpleTestCase`, sobre `calcular_clave_candado`): `calcular_clave_candado(f, servicio_id=None) == f.toordinal()`; para `sid` en `1..500`, `calcular_clave_candado(f, sid) != legacy` y `>= 0x40000000`; `calcular_clave_candado(f,1) != calcular_clave_candado(f,2)`.
2. Run → FAIL.
3. **Reemplaza `candado.py` entero** (firma `bloquear_cupo(empresa_id, fecha, servicio_id=None)`, `calcular_clave_candado(fecha, servicio_id=None)`, `bloquear_cupo_del_dia(empresa_id, fecha)` = compat). Ver el código en la trampa "bit 30" arriba.
4. Ajusta `validar_cupo_diario` para pasar `servicio_id=`. Grep `bloquear_cupo` fuera de `/cupo/` y tests.
5. Postgres (drop + `test apps.bookings --noinput`) → OK.
6. Commit: `fix(cupo): advisory lock por (empresa, servicio, fecha) sin colisión con el path legacy`.

---

### Tarea 2.6 — Gate: suite completa verde

1. sqlite: `test apps config` → `OK`. 2. Postgres (drop + `test apps config --noinput`) → `OK`. 3. Actualiza el Registro de avance: "Sección 2 cerrada @ <sha>". Commit `docs(plan): Sección 2 cerrada`. **DETENTE y reporta: git log de la sección + resultado de ambos gates.**

---

# SECCIÓN 3 — Hospedaje: modelo de datos (`ReservaOcupacion` con constraint anti-doble-booking)

**Problema:** `ReservaOcupacion` (pieza 4) solo tiene validación de traslape en `.clean()` (que
solo corre en el admin), **sin lock ni constraint de BD**. Dos reservas concurrentes de la misma
habitación/rango → doble booking. Además nada del flujo de pago crea filas de ocupación (Sección 6).

---

### Tarea 3.1 — Columna `ocupa_cupo` en `ReservaOcupacion`, mantenida por `Reserva.save()`

**Files:** Modify `backend/apps/bookings/models.py` (`ReservaOcupacion`, `Reserva.save`) · migración `bookings/0029_reservaocupacion_ocupa_cupo` · Test `apps/bookings/tests_ocupacion.py`.

**Por qué:** un `EXCLUDE` de Postgres en `bookings_reservaocupacion` NO puede referenciar
`bookings_reserva.estado` (tabla distinta). Se denormaliza: `ocupa_cupo` (bool) refleja si la
reserva de esa ocupación está en `ESTADOS_QUE_OCUPAN_CUPO`.

1. **Test que falla** (`apps.testing.OperadorTestCase` — abarca varias empresas/servicios):
   - `test_ocupa_cupo_sigue_el_estado_de_la_reserva`: crea `Reserva(estado=PAGADA)` + `ReservaOcupacion` → `ocupa_cupo is True`. Cambia `reserva.estado = CANCELADA`, `reserva.save()` → recarga la ocupación → `ocupa_cupo is False`. Vuelve a `PAGADA`, `save()` → `True`.
2. Run → FAIL (`ocupa_cupo` no existe).
3. **Modifica `ReservaOcupacion`:** añade `ocupa_cupo = models.BooleanField(default=True, db_index=True)`.
4. **Modifica `ReservaOcupacion.save`:** si `self.ocupa_cupo` no fue seteado explícitamente y hay reserva, `self.ocupa_cupo = reserva.estado in ESTADOS_QUE_OCUPAN_CUPO`.
5. **Modifica `Reserva.save`** (al final, después de `super().save()`): si el estado cambió hacia/desde `ESTADOS_QUE_OCUPAN_CUPO`, propaga:
   ```python
   nuevo = self.estado in ESTADOS_QUE_OCUPAN_CUPO
   self.ocupaciones.exclude(ocupa_cupo=nuevo).update(ocupa_cupo=nuevo)
   ```
   (usa `related_name='ocupaciones'`; guarda el estado previo con el mismo patrón `_vendedora_original` que ya usa `save` para no hacer el UPDATE en cada guardado.)
6. **Modifica `ReservaOcupacion.clean`:** el query de traslape añade `ocupa_cupo=True` en vez de (o además de) el JOIN por `reserva__estado__in`, y acota por fechas: `.filter(recurso_id=..., ocupa_cupo=True, fecha_inicio__lt=self.fecha_fin, fecha_fin__gt=self.fecha_inicio, empresa_id=self.empresa_id)`.
7. Migración: `makemigrations bookings --name reservaocupacion_ocupa_cupo`. Debe ser `AddField` + un `RunPython` que rellene `ocupa_cupo` de las filas existentes según el estado de su reserva (envuelto en `alcance_operador_migracion` — constraint global #7).
8. sqlite + Postgres (`test apps.bookings.tests_ocupacion apps.bookings.tests_ocupacion_rls`) → OK.
9. Commit: `feat(hospedaje): ReservaOcupacion.ocupa_cupo denormalizado, sincronizado por Reserva.save`.

---

### Tarea 3.2 — Constraint `EXCLUDE` anti-traslape + `btree_gist`

**Files:** migración `bookings/0030_reservaocupacion_exclude` · Test `apps/bookings/tests_ocupacion.py` (`# postgres-only`).

1. **Test que falla** (`TransactionTestCase` + `@skipUnless(connection.vendor == 'postgresql', ...)`, con `with scope.con_empresa(e):`):
   - `test_constraint_rechaza_dos_ocupaciones_traslapadas_del_mismo_recurso`: crea una ocupación `[1/10, 1/15)` `ocupa_cupo=True`; crear otra `[1/12, 1/18)` del mismo recurso → `django.db.utils.IntegrityError`.
   - `test_checkout_el_mismo_dia_se_permite`: `[1/10, 1/15)` y `[1/15, 1/20)` del mismo recurso → ambas OK (intervalo semi-abierto).
   - `test_ocupacion_de_reserva_cancelada_no_estorba`: `[1/10, 1/15)` con `ocupa_cupo=False` no bloquea `[1/12, 1/18)`.
2. **Migración** `RunPython` con guard `vendor == 'postgresql'`:
   ```sql
   CREATE EXTENSION IF NOT EXISTS btree_gist;
   ALTER TABLE bookings_reservaocupacion ADD CONSTRAINT ocupacion_sin_traslape
     EXCLUDE USING gist (
       recurso_id WITH =,
       daterange(fecha_inicio, fecha_fin, '[)') WITH &&
     ) WHERE (ocupa_cupo);
   ```
   Reversa: `DROP CONSTRAINT IF EXISTS ocupacion_sin_traslape;` (no dropear la extensión — otros objetos podrían usarla).
   Índice extra para el query de `clean()`: `CREATE INDEX IF NOT EXISTS idx_ocupacion_recurso_rango ON bookings_reservaocupacion (recurso_id, fecha_inicio, fecha_fin);`
3. Postgres (`test apps.bookings.tests_ocupacion --noinput`) → OK. sqlite: la migración es no-op → `test apps.bookings.tests_ocupacion` → los tests `# postgres-only` se saltan, el resto verde.
4. Commit: `feat(hospedaje): constraint EXCLUDE anti-doble-booking en ReservaOcupacion`.

---

### Tarea 3.3 — `bloquear_recurso` (lock por recurso, para hospedaje)

**Files:** Modify `backend/apps/bookings/cupo/candado.py` · Test `apps/bookings/tests_cupo_candado.py`.

**Produce:** `bloquear_recurso(empresa_id: int, recurso_id: int) -> None` — `pg_advisory_xact_lock(empresa_id, (crc32(f'recurso:{recurso_id}') & 0x3FFFFFFF) | 0x40000000)`. Mismo espacio de bit-30 que el lock de servicio (no colisiona con el legacy; puede colisionar con un lock de servicio de otra fecha — aceptable, solo sobre-serializa).

1. **Test:** `calcular_clave_recurso(recurso_id)` distinto por recurso, `>= 0x40000000`, `!= toordinal` de cualquier fecha 2020-2035.
2. Implementa `calcular_clave_recurso` + `bloquear_recurso` en `candado.py`. Exporta ambos desde `apps/bookings/cupo/__init__.py`.
3. Postgres `test apps.bookings.tests_cupo_candado --noinput` → OK.
4. Commit: `feat(hospedaje): bloquear_recurso — advisory lock por (empresa, recurso)`.

---

### Tarea 3.4 — Gate Sección 3

sqlite + Postgres `test apps config` → `OK`. Registro de avance: "Sección 3 cerrada @ <sha>". Commit. **DETENTE y reporta.**

---

# SECCIÓN 4 — Precio: paquete (= ancla + personalizaciones), noches, anticipo configurable

**Fórmula de precio de paquete (Decisión 7, frozen):**
```
total_paquete(moneda) =
    paquete.precio_en(moneda)                                              # el ancla
  + Σ  sp.precio_en(moneda) de cada ServicioPersonalizacion (obligatorio o preseleccionado)
       de los servicios componentes NO removidos, con activo=True
  + Σ  sp.precio_en(moneda) de las ServicioPersonalizacion OPCIONALES que el cliente marcó
  − Σ  PaqueteServicio.ajuste_en(moneda) de los servicios removidos (removible=True)
```
Cada personalización que `cobrar_por_persona` se multiplica por `personas` (mismo criterio que
`cargo_por_extra` en `pricing.py` hoy). Piso 0. Cuantizado a centavos, `ROUND_HALF_UP`.

---

### Tarea 4.1 — `precio_paquete_total()` en `pricing.py`

**Files:** Modify `backend/apps/payments/pricing.py` · Test `apps/payments/tests_pricing_paquete.py`.

**Produce:**
```python
def precio_paquete_total(paquete, *, servicios_removidos_ids: set[int],
                         personalizaciones_extra: list[tuple[int, int]],  # (servicio_personalizacion_id, cantidad)
                         personas: int, moneda: str) -> Decimal | None:
    """Precio final de un paquete. None si el paquete no tiene precio en `moneda`."""
```

1. **Tests** (`OperadorTestCase` — necesita Paquete + Servicios + ServicioPersonalizacion de una empresa):
   - sin removidos ni extras → `== paquete.precio_en(moneda) + Σ(obligatorias/preseleccionadas)`.
   - un servicio removido → resta su `ajuste_en(moneda)` y deja de contar sus personalizaciones.
   - personalización opcional marcada → suma su precio (× personas si `cobrar_por_persona`).
   - paquete sin `precio_ancla_usd`, moneda USD → `None`.
   - piso 0: ajustes que superan el ancla → `Decimal('0.00')`.
2. Implementa `precio_paquete_total` en `pricing.py` (funciones puras, recibe el objeto `paquete` y traversa `paquete.servicios_asociados` / `servicio.servicio_personalizaciones` — está permitido leer relaciones aquí, es el único lugar donde vive la matemática). Deja `calcular_precio_paquete` viejo como wrapper o bórralo si nadie más lo usa (grep).
3. sqlite + Postgres `test apps.payments.tests_pricing_paquete` → OK.
4. Commit: `feat(precio): precio_paquete_total = ancla + personalizaciones − ajustes`.

---

### Tarea 4.2 — `PaqueteServicio.clean` bloquea cruza-empresa; `Paquete.clean` valida Σajustes

**Files:** Modify `backend/apps/fleet/models.py` (`Paquete.clean`, `PaqueteServicio.clean`) · Test `apps/fleet/tests_paquetes.py`.

1. **Tests** (`OperadorTestCase`):
   - `PaqueteServicio` cuyo `servicio.empresa != paquete.empresa_lider` → `ValidationError({'servicio': ...})` con mensaje "paquetes cruza-empresa: fuera de v1, ver ADR-005".
   - `PaqueteServicio` de la misma empresa_lider → OK.
   - `Paquete` con `Σ ajuste_precio de removibles > precio_ancla` → `ValidationError({'precio_ancla': ...})`. (Ojo: el `Paquete.clean` que valida esto necesita los `PaqueteServicio` ya guardados — es una validación de "estado del paquete", corre al guardar el paquete o vía una acción/check; documenta que en el admin se dispara al re-guardar el paquete tras editar sus componentes.)
2. **Modifica** `PaqueteServicio.clean`: reemplaza la regla actual (misma sede) por **misma empresa_lider**. `Paquete.clean`: suma `ajuste_precio` (y `_usd`) de `self.servicios_asociados.filter(removible=True)` y compara con `precio_ancla` (y `_usd`).
3. **Actualiza `apps/fleet/tests_paquetes.py`** y `tests_paquetes_api.py`: los tests que hoy crean paquetes con servicios de `empresa_hotel` (otra empresa) deben cambiar a servicios de la misma empresa líder (v1). El test de "componente cruza-empresa" pasa a ser "componente cruza-empresa → ValidationError".
4. sqlite + Postgres `test apps.fleet` → OK.
5. Commit: `fix(fleet): paquete v1 = una sola empresa; ajustes ≤ ancla`.

---

### Tarea 4.3 — Anticipo configurable en `monto_inicial`

**Files:** Modify `backend/apps/payments/pricing.py` (`monto_inicial`) · Modify `backend/apps/fleet/models.py` (`Paquete.porcentaje_anticipo`) · migración fleet · Test `apps/payments/tests_pricing_estrategias.py`.

1. `monto_inicial` hoy: `monto_inicial(precio_total, forma_pago)`. Nuevo: `monto_inicial(precio_total, forma_pago, porcentaje=None)`. Si `forma_pago == COMPLETO` → 100%. Si `ANTICIPO` → `porcentaje or 30` (%). Mantén `ANTICIPO_PORCENTAJE` para el default.
2. **Añade `Paquete.porcentaje_anticipo = models.PositiveSmallIntegerField(default=30)`** (Decisión: campo propio del paquete, no derivado). Migración `fleet/0022`.
3. **Tests:** `monto_inicial(1000, ANTICIPO, porcentaje=50) == 500`; `monto_inicial(1000, COMPLETO, porcentaje=50) == 1000`; `monto_inicial(1000, ANTICIPO) == 300`.
4. Grep todos los call sites de `monto_inicial` (`views.py`, `services.py::_verificar_monto`) — no rompas los que no pasan `porcentaje` (default correcto).
5. sqlite + Postgres `test apps.payments` → OK.
6. Commit: `feat(precio): monto_inicial acepta porcentaje de anticipo; Paquete.porcentaje_anticipo`.

---

### Tarea 4.4 — `CrearPagoView._post`: 3 ramas de precio

**Files:** Modify `backend/apps/payments/views.py::CrearPagoView._post` · Test `apps/payments/tests.py::CrearPagoTests`.

Estructura (reemplaza el bloque `if reserva.servicio: ... else: tarifa = Tarifa.de(empresa) ...`):
```python
if reserva.paquete_id:
    removidos = set(reserva.servicios_removidos.values_list('servicio_id', flat=True))
    extras_pers = list(reserva.paquete_personalizaciones.values_list('servicio_personalizacion_id', 'cantidad'))
    precio_base_servicio = precio_paquete_total(
        reserva.paquete, servicios_removidos_ids=removidos,
        personalizaciones_extra=extras_pers, personas=reserva.numero_personas,
        moneda=reserva.moneda,
    )
    if precio_base_servicio is None:
        return Response({'detail': f'El paquete no tiene precio en {reserva.moneda}.'}, status=503)
    porcentaje = reserva.paquete.porcentaje_anticipo
elif reserva.servicio_id:
    estrategia = obtener_estrategia_precio(reserva.servicio.estrategia_precio)
    demanda = DemandaPrecio(personas=reserva.numero_personas, moneda=reserva.moneda, noches=reserva.noches)
    try:
        precio_base_servicio = estrategia.calcular_base(reserva.servicio, demanda)
    except ValueError as e:
        return Response({'detail': str(e)}, status=503)
    porcentaje = reserva.servicio.porcentaje_anticipo
else:
    # ... rama Tarifa legacy actual, sin cambios ...
    porcentaje = 30
```
Y `monto_a_cobrar = monto_inicial(precio_total, forma_pago, porcentaje=porcentaje)`.
**Los `ReservaExtra`/`ReservaTransporte` (sistema viejo) NO se suman a un paquete** — para un
paquete, `cargo_extras` y `cargo_transporte` = 0 (o salta `_resolver_extras`/`_resolver_transporte`
cuando `reserva.paquete_id`). Para servicio suelto no-pesca: por defecto tampoco (solo pesca legacy usa ese sistema — pregunta menor abierta en el plan de alto nivel; si el dueño no dijo otra cosa, asume "solo pesca legacy").

1. **Tests** (`CrearPagoTests`, `ApiTestCase`): crea un `Servicio` `por_noche` + `Paquete` de la empresa; monta reservas de cada tipo; verifica el `monto_a_cobrar` de la respuesta contra el cálculo esperado; verifica que `por_noche` con `fecha_salida` a 3 noches cobra 3×; verifica que un paquete con `porcentaje_anticipo=100` cobra el total.
   (Estas reservas se crean directo en el test con `Reserva.objects.create(...)` bajo el scope de `ApiTestCase` — el serializer las acepta en Sección 5, aquí se prueba solo el cálculo de `crear-pago`.)
2. sqlite + Postgres `test apps.payments.tests` → OK.
3. Commit: `fix(precio): crear-pago cobra paquete por su fórmula y hospedaje por noches`.

---

### Tarea 4.5 — `_verificar_monto` cubre las 3 ramas

**Files:** Modify `backend/apps/payments/services.py::_verificar_monto` · Test `apps/payments/tests.py`.

`_verificar_monto` recomputa `esperado`. Hoy usa `monto_inicial(reserva.precio_total, reserva.forma_pago)`.
`reserva.precio_total` ya está congelado por `crear-pago`, así que **basta con pasar el `porcentaje` correcto**:
`porcentaje = reserva.paquete.porcentaje_anticipo if reserva.paquete_id else (reserva.servicio.porcentaje_anticipo if reserva.servicio_id else 30)`.
No recalcula la fórmula del paquete (el precio ya está congelado). Sigue sin rebotar, solo `logger.error` el descuadre.

1. Test: webhook con el monto correcto para un paquete `porcentaje_anticipo=100` → sin `logger.error` de descuadre.
2. Commit: `fix(precio): _verificar_monto usa el porcentaje de anticipo correcto por tipo de reserva`.

---

### Tarea 4.6 — Gate Sección 4

sqlite + Postgres `test apps config` → `OK`. Registro: "Sección 4 cerrada @ <sha>". Commit. **DETENTE y reporta.**

---

# SECCIÓN 5 — Checkout: el serializer y la API aceptan servicio / paquete / fecha_salida

**Problema:** `ReservaCheckoutSerializer` no tiene `servicio`, `paquete`, `fecha_salida`,
`servicios_removidos`, `personalizaciones`. El frontend ya manda `paquete` y **DRF lo descarta en
silencio** → toda reserva se cobra como pesca legacy.

---

### Tarea 5.1 — Modelos de selección del checkout de paquete

**Files:** Modify `backend/apps/bookings/models.py` (2 modelos nuevos) · migración `bookings/0031_checkout_paquete` + `bookings/0032_rls_checkout_paquete` · Test `apps/bookings/tests_checkout_paquete.py`.

```python
class ReservaPaqueteServicioRemovido(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='servicios_removidos')
    servicio = models.ForeignKey('fleet.Servicio', on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['reserva', 'servicio'], name='reservapaqueteserviciorem_unico')]

class ReservaPaquetePersonalizacion(models.Model):
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='paquete_personalizaciones')
    servicio_personalizacion = models.ForeignKey('fleet.ServicioPersonalizacion', on_delete=models.PROTECT)
    cantidad = models.PositiveSmallIntegerField(default=1)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['reserva', 'servicio_personalizacion'], name='reservapaquetepers_unico')]
```

- Migración de datos: ninguna. Migración de esquema: `0031`.
- **RLS** (`0032`, patrón `SQL_POLITICA_EXISTS` de `bookings/0003_rls`): política `EXISTS (SELECT 1 FROM bookings_reserva r WHERE r.id = <tabla>.reserva_id AND (r.empresa_id = NULLIF(current_setting('app.current_empresa_id', true),'')::int OR current_setting('app.operador_plataforma', true) = 'on'))`.
- Test `# postgres-only`: una empresa no ve las filas de otra.
- Commit: `feat(checkout): modelos de selección de paquete (servicios removidos, personalizaciones)`.

---

### Tarea 5.2-5.4 — `ReservaCheckoutSerializer`

**Files:** Modify `backend/apps/bookings/serializers.py` · Test `apps/bookings/tests_tenancy.py::SerializerEmpresaTests` (o archivo nuevo `tests_checkout_serializer.py`).

- **5.2 `Meta.fields`** += `servicio` (slug), `paquete` (slug), `fecha_salida`, `servicios_removidos` (lista de slugs, write_only), `personalizaciones` (lista de `{id, cantidad}`, write_only). `servicio`/`paquete` como `SlugRelatedField` filtrados por empresa/`empresa_lider` en `get_fields` (mismo patrón que `ExtraSeleccionSerializer.get_fields`, que ya filtra por `self.context['empresa']`).
- **5.3 `validate`:**
  - `servicio` y `paquete` mutuamente excluyentes (400 si ambos).
  - `paquete.empresa_lider_id == self.context['empresa'].id` (400 si no).
  - `fecha_salida`: requerida y `> fecha` si algún componente del paquete (o el servicio) tiene `estrategia_cupo == 'por_noche'`; prohibida si ninguno.
  - `servicios_removidos ⊆ {ps.servicio for ps in paquete.servicios_asociados if ps.removible}`.
  - `personalizaciones`: cada `id` es una `ServicioPersonalizacion` `activo=True` de un servicio componente NO removido.
  - `numero_personas` contra `personas_incluidas`/capacidad del servicio dominante, no solo `MAX_PERSONAS`.
- **5.4 `create`/`update`:** persiste `servicio` XOR `paquete`, `fecha_salida`; sincroniza `servicios_removidos` y `paquete_personalizaciones` (borrar+recrear, dentro del scope de la empresa — el serializer ya corre bajo `con_empresa` desde la vista).
- Tests: acepta reserva de servicio; acepta reserva de paquete de la empresa; rechaza `paquete` de otra `empresa_lider` (400); rechaza `servicio`+`paquete` juntos; exige `fecha_salida` para hospedaje.
- Commit: `fix(checkout): serializer acepta servicio, paquete, fecha_salida y selección de paquete`.

---

### Tarea 5.5 — `Reserva.clean`: rama `por_noche` y rama paquete

**Files:** Modify `backend/apps/bookings/models.py::Reserva.clean` · Test `apps/bookings/tests_ocupacion.py`.

Reemplaza el `# TODO Sección 5` que dejaste en 2.4:
```python
if self.estado in ESTADOS_QUE_OCUPAN_CUPO:
    if self.paquete_id:
        _validar_cupo_de_paquete(self)   # helper nuevo: recorre servicios_asociados NO removidos
    elif self.servicio_id and self.servicio.estrategia_cupo == 'por_noche':
        _validar_cupo_hospedaje(self)     # helper nuevo: evaluar_disponibilidad_hospedaje(fecha, fecha_salida, personas, empresa, servicio)
    else:
        estrategia_cupo = self.servicio.estrategia_cupo if self.servicio_id else 'por_recurso_dia'
        validar_cupo_diario(self.fecha, self.numero_personas, self.empresa,
                            excluir_pk=self.pk, estrategia_cupo=estrategia_cupo, servicio_id=self.servicio_id)
```
- `_validar_cupo_hospedaje`: llama `apps.bookings.cupo.evaluar_disponibilidad_hospedaje(self.fecha, self.fecha_fin_servicio, self.numero_personas, self.empresa, servicio=self.servicio, excluir_pk=self.pk)` (ya existe en `cupo/adaptador.py`); si `False` → `ValidationError({'fecha': 'No hay disponibilidad de hospedaje en esas fechas.'})`. **Sin lock aquí** (el lock va en Sección 6, al confirmar el pago).
- `_validar_cupo_de_paquete`: para cada `PaqueteServicio` NO removido (los `servicios_removidos` de la reserva), según `ps.servicio.estrategia_cupo`: `por_recurso_dia` → `evaluar_cupo(fecha, personas, empresa, servicio_id=ps.servicio_id, estrategia_cupo='por_recurso_dia')`; `por_noche` → `evaluar_disponibilidad_hospedaje(...)`; `bajo_demanda` → siempre OK. Si alguno no cabe → `ValidationError` nombrando el servicio.
- Tests (`OperadorTestCase`): reserva de servicio hospedaje sin disponibilidad → `full_clean()` revienta; con disponibilidad → OK. Reserva de paquete con un componente hospedaje sin cupo → revienta.
- Commit: `fix(cupo): Reserva.clean valida hospedaje multidía y cupo por componente de paquete`.

---

### Tarea 5.6 — `PaqueteDetailView`

**Files:** Modify `backend/apps/fleet/views.py` + `apps/fleet/urls.py` + `apps/fleet/catalogo.py` · Test `apps/fleet/tests_paquetes_api.py`.

- `GET /api/sedes/<sede_slug>/paquetes/<slug>/` → `PaqueteDetailView`. Resuelve la sede (`get_object_or_404(Sede, slug=..., activo=True)`), busca el paquete activo por slug **iterando empresas de la sede en su `con_empresa`** (helper nuevo `paquete_de_sede(sede, slug)` en `catalogo.py`, mismo patrón que `paquetes_de_sede`). 404 si no existe. `throttle_scope = 'catalogo'`.
- Test: devuelve el paquete correcto; 404 para slug inexistente; 404 si la sede está inactiva.
- Commit: `feat(catálogo): endpoint de detalle de paquete por sede+slug`.

---

### Tarea 5.7-5.9 — Frontend

**Files:** `frontend/src/lib/api.ts`, `frontend/src/lib/pricing-paquete.ts`, `frontend/src/app/[lang]/reservar/page.tsx`, `frontend/src/components/checkout-view.tsx`, `frontend/src/components/paquete-card.tsx`.

- **5.7** `api.ts`: `getPaqueteDetalle(sedeSlug, paqueteSlug)` → `GET /api/sedes/${sedeSlug}/paquetes/${paqueteSlug}/`. `reservar/page.tsx`: reemplaza el `getSedes()` + loop `getPaquetesSede` por `getPaqueteDetalle` (el `?sede=` ya viene en el query; si no viene, cae a `getSedes()` para ubicar la sede del paquete — o pide `?sede=` obligatorio y muestra error si falta).
- **5.8** `api.ts`: `ReservaInput` += `servicio?: string`, `fecha_salida?: string`, `servicios_removidos?: string[]`, `personalizaciones?: {id: number; cantidad: number}[]`. `guardarReserva` los manda tal cual. `type MotivoNoDisponible = 'lleno' | 'sin_panga' | 'sin_lugar'` (B3); revisa que `checkout-view.tsx` y el calendario del catálogo manejan `'sin_lugar'` (tratarlo igual que `'sin_panga'`).
- **5.9** `checkout-view.tsx` / `paquete-card.tsx`: la selección de servicios removidos y personalizaciones opcionales que ve el cliente se manda en `guardarReserva`. `pricing-paquete.ts` se reescribe para calcular la fórmula de 4.1 (ancla + personalizaciones − ajustes) — el precio que muestra debe coincidir con el que devuelve `crear-pago`.
- Verificación: `npm.cmd run lint`, `npx.cmd tsc --noEmit`, `npm.cmd run build` verdes. (No hay tests de frontend; el dueño revisa la UI a mano — ver memoria `verificacion-sin-navegador`.)
- Commit: `fix(frontend): checkout manda servicio/paquete/fecha_salida/selección; detalle de paquete sin waterfall`.

---

### Tarea 5.10 — Gate Sección 5

sqlite + Postgres `test apps config` → `OK`. Frontend `lint`/`tsc`/`build` → OK. Registro: "Sección 5 cerrada @ <sha>". Commit. **DETENTE y reporta.**

---

# SECCIÓN 6 — El pago confirma y reserva el cupo de cada componente

**Problema:** `aplicar_pago_exitoso` marca la reserva `PAGADA` pero **no crea `ReservaOcupacion`
ni reserva cupo de los componentes de un paquete**. El hospedaje puede sobrevenderse.

---

### Tarea 6.1 — `ReservaPaqueteComponente`

**Files:** Modify `backend/apps/bookings/models.py` · migración `bookings/0033` + `0034_rls` · Test.

```python
class ReservaPaqueteComponente(models.Model):
    class EstadoCupo(models.TextChoices):
        OK = 'ok', 'Cupo reservado'
        LIBERADO = 'liberado', 'Liberado (reserva cancelada)'
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='componentes')
    servicio = models.ForeignKey('fleet.Servicio', on_delete=models.PROTECT)
    empresa = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT)   # = servicio.empresa
    estado_cupo = models.CharField(max_length=10, choices=EstadoCupo.choices, default=EstadoCupo.OK)
    creado_en = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['reserva', 'servicio'], name='reservapaquetecomponente_unico')]
```
RLS por `empresa_id` (patrón `SQL_POLITICA` directo, como `bookings_reservaocupacion`). Test `# postgres-only` de aislamiento. Commit.

---

### Tarea 6.2 — `elegir_recursos` (núcleo puro)

**Files:** Modify `backend/apps/bookings/cupo/nucleo.py` · Test `tests_cupo_nucleo.py`.

```python
def elegir_recursos(libres: list[tuple[int, int]], personas: int, cantidad: int) -> list[int] | None:
    """`libres` = [(recurso_id, capacidad), ...]. Devuelve los ids de `cantidad`
    recursos cuyo total de capacidad >= personas, prefiriendo los más chicos que
    alcanzan (menos desperdicio). None si no se puede."""
```
Determinista, testeable sin BD. Tests: 1 recurso que cabe; combinación de 2; imposible → None; prefiere el más chico.
Commit: `feat(hospedaje): elegir_recursos — selección determinista de recursos para una ocupación`.

---

### Tarea 6.3 — `aplicar_pago_exitoso` crea el cupo al confirmar

**Files:** Modify `backend/apps/payments/services.py::aplicar_pago_exitoso` · Create helper `apps/bookings/cupo/confirmacion.py` (o dentro de `services.py`) · Test `apps/payments/tests.py` + `tests_concurrencia.py`.

**Define `class SinCupoError(Exception)`** en `apps/bookings/cupo/__init__.py` (o `services.py`); su `str()` es el mensaje que verá la vendedora en `Reserva.motivo_cancelacion`.
Firma del helper: `reservar_cupo_al_confirmar(reserva) -> None` (lanza `SinCupoError`).

Tras `reserva.estado = PAGADA; reserva.full_clean(); reserva.save()` y **antes** de encolar `_notificar`:
```python
try:
    _reservar_cupo_al_confirmar(reserva)   # helper nuevo
except SinCupoError as e:
    return _cancelar_sin_cupo(reserva, intent, empresa)   # reembolso 100%, mensaje = str(e)
```
`_reservar_cupo_al_confirmar(reserva)`:
- **servicio hospedaje** (`reserva.servicio.estrategia_cupo == 'por_noche'`): `bloquear_recurso` por cada recurso candidato del servicio → `obtener_recursos_con_ocupaciones` → `elegir_recursos` → crear `ReservaOcupacion(fecha_inicio=reserva.fecha, fecha_fin=reserva.fecha_fin_servicio, ocupa_cupo=True)` por cada recurso elegido. Si `elegir_recursos` devuelve `None` → `raise SinCupoError('No hay habitación disponible en esas fechas.')`.
- **paquete**: por cada `PaqueteServicio` NO removido:
  - `por_recurso_dia`: `bloquear_cupo(empresa.pk, reserva.fecha, servicio_id=ps.servicio_id)` + `evaluar_cupo(...)`; si lleno → `SinCupoError`. Crear `ReservaPaqueteComponente(estado_cupo=OK)`. (La asignación concreta de panga sigue siendo manual en la agenda.)
  - `por_noche`: como el caso hospedaje de arriba, + `ReservaPaqueteComponente`.
  - `bajo_demanda`: solo `ReservaPaqueteComponente(estado_cupo=OK)`.
- **servicio pesca/paseo normal, o legacy**: nada nuevo (el `full_clean()` de arriba ya validó; la panga se asigna en la agenda).
- **v1: todos los componentes son de `reserva.empresa`** → todo corre en el alcance ya abierto por el webhook. NO abras `con_empresa` anidado.
- Todo dentro de la `@transaction.atomic` de `aplicar_pago_exitoso`: si un `SinCupoError` sale, el rollback deshace las ocupaciones parciales y `_cancelar_sin_cupo` reembolsa.

Tests:
- Reserva de servicio hospedaje pagada → se crea `ReservaOcupacion` con el rango correcto.
- `# postgres-only`: dos reservas de hospedaje pagando la última habitación en paralelo → una `PAGADA` con ocupación, la otra `CANCELADA + reembolsada`; `refunds.create` llamado una vez (mock `@mock.patch.object(StripeClient, 'refunds')`).
- Paquete con componente hospedaje sin cupo → toda la reserva `CANCELADA + reembolsada`, sin `ReservaOcupacion` huérfana.
Commit: `fix(hospedaje): el pago reserva el cupo de cada servicio/componente multidía; reembolso si algo se llenó`.

---

### Tarea 6.4 — Cancelación libera el cupo

**Files:** Modify `backend/apps/bookings/models.py` · Test.

`Reserva.save()` (Tarea 3.1 Paso 5) ya baja `ocupa_cupo` de las `ReservaOcupacion` al pasar a un estado
que no ocupa cupo. Extiende: también marca `ReservaPaqueteComponente.estado_cupo = LIBERADO`.
Tests: acción de admin "Cancelar por mal clima" sobre una reserva de hospedaje → sus `ReservaOcupacion`
quedan `ocupa_cupo=False` y otra reserva puede tomar el rango. Igual para un paquete.
Commit: `fix(hospedaje): cancelar una reserva libera sus ocupaciones y componentes`.

---

### Tarea 6.5 — `conciliar_pagos` también crea el cupo

**Files:** Test `apps/payments/tests.py` (el comando ya llama `aplicar_pago_exitoso`, que ahora hace todo).

Solo añade un test: una reserva de hospedaje `pendiente_pago` con PaymentIntent `succeeded` en Stripe → `conciliar_pagos` la marca `PAGADA` **y crea su `ReservaOcupacion`**. Commit `test(hospedaje): conciliar_pagos crea el cupo igual que el webhook`.

---

### Tarea 6.6 — Admin

**Files:** Modify `backend/apps/bookings/admin.py`.

`ReservaOcupacionInline` y un `ReservaPaqueteComponenteInline` nuevo: `has_add_permission`/`has_change_permission`/`has_delete_permission` devuelven `False` cuando `obj` (la reserva) está en un estado pagado — la ocupación la pone el sistema. Editables solo para `pendiente_pago` / reservas de WhatsApp. Commit.

---

### Tarea 6.7 — Gate Sección 6

sqlite + Postgres `test apps config` → `OK`. Registro: "Sección 6 cerrada @ <sha>". Commit. **DETENTE y reporta.**

---

# SECCIÓN 6.5 — Marketplace real en el checkout (empresa dinámica en el frontend)

**Problema:** el frontend tiene un solo `NEXT_PUBLIC_EMPRESA_SLUG` fijo. El catálogo
(`/api/sedes/...`) muestra paquetes y servicios de **todas** las empresas de una sede, pero el
checkout siempre postea a esa empresa fija → comprar un ítem de otra empresa da 400
("el paquete no pertenece a esta empresa") o crea la reserva en la empresa equivocada. Es la razón
de ser de toda la expansión multi-sede; tiene que quedar en v1.

**El backend ya está listo:** todos los endpoints son `/api/<empresa_slug>/...`, `crear-pago`
devuelve la `publishable_key` **de esa empresa** en su respuesta, y `stripe-panel.tsx` ya monta
Stripe con `pago.publishable_key` (verificado). **NO se toca el backend salvo un campo en un
serializer.** Todo el trabajo es de frontend + threading de un string.

**Regla:** el checkout resuelve la empresa **del ítem que el cliente eligió**, no del deploy:
- reserva de **paquete** → `paquete.empresa_lider_slug`
- reserva de **servicio suelto** → `servicio.empresa_slug` (campo nuevo, Tarea 6.5.1)
- **pesca legacy** (sin servicio ni paquete) → `NEXT_PUBLIC_EMPRESA_SLUG` (el propio del deploy)

---

### Tarea 6.5.1 — `empresa_slug` en el catálogo de servicios

**Files:** Modify `backend/apps/fleet/serializers.py::ServicioSerializer` · Test `apps/fleet/tests_servicios_api.py` / `tests_paquetes_api.py`.

1. `ServicioSerializer.Meta.fields` += `'empresa_slug'`; añade `empresa_slug = serializers.CharField(source='empresa.slug', read_only=True)`.
2. Test: `GET /api/sedes/<sede>/servicios/` — cada ítem trae `empresa_slug` correcto (distinto por empresa cuando la sede tiene varias). El `ServicioSerializer` anidado en `PaqueteServicioSerializer` también lo trae (no molesta).
3. Verifica que `ServicioSerializer` cuando lo usa `ServiciosListView` (ruta `/api/<empresa>/servicios/`) sigue funcionando — `obj.empresa.slug` está disponible.
4. Commit: `feat(catálogo): ServicioSerializer expone empresa_slug`.

---

### Tarea 6.5.2 — `request()` y las funciones de `api.ts` aceptan `empresaSlug`

**Files:** Modify `frontend/src/lib/api.ts` · (no hay tests de frontend — verifica con `tsc`/`build` y razonando las URLs).

1. **`request()`** gana un 3er parámetro:
   ```ts
   async function request<T>(path: string, init?: RequestInit, empresaSlug?: string): Promise<T> {
     const slug = empresaSlug ?? EMPRESA_SLUG;
     const rutaConEmpresa = path.startsWith('/api/sedes')
       ? path
       : path.startsWith('/api/')
       ? `/api/${slug}${path.slice(4)}`
       : path;
     // ...resto igual...
   }
   ```
2. Estas 8 funciones ganan un parámetro `empresaSlug?: string` (opcional, **al final**, para no romper llamadas existentes) y lo pasan como 3er arg a `request()`:
   - `getTarifa(empresaSlug?)`
   - `getExtras(personas, moneda, empresaSlug?)`
   - `getCupo(fecha, personas, empresaSlug?)`
   - `getCupoRango(desde, hasta, personas, empresaSlug?)`
   - `guardarReserva(data, empresaSlug?)`
   - `crearPago(reservaId, data, empresaSlug?)`
   - `getEstadoReserva(checkoutId, empresaSlug?)`
   - `validarCodigoPromocional(codigo, correoCliente, empresaSlug?)`
   Ejemplo: `export const getTarifa = (empresaSlug?: string) => request<Tarifa>('/api/tarifa/', undefined, empresaSlug);`
3. Omitir el parámetro = comportamiento actual (usa `EMPRESA_SLUG`). Nada existente se rompe.
4. `tsc --noEmit` limpio.
5. Commit: `feat(frontend): api.ts acepta empresaSlug por llamada para checkout multi-empresa`.

---

### Tarea 6.5.3 — Los enlaces de servicios sueltos llevan la empresa

**Files:** Modify `frontend/src/components/servicios-sueltos-section.tsx` (y donde salga `ServicioCatalogo`) · Modify `frontend/src/lib/api.ts` (`type ServicioCatalogo` += `empresa_slug: string`).

1. `type ServicioCatalogo` += `empresa_slug: string`.
2. `servicios-sueltos-section.tsx:103`: el `href` pasa de `/${lang}/reservar?servicio=${servicio.slug}&moneda=${moneda}` a `.../reservar?servicio=${servicio.slug}&empresa=${servicio.empresa_slug}&moneda=${moneda}`.
3. `paquete-card.tsx`: verifica que el enlace de paquete ya incluye algo que identifique la empresa; si solo tiene `&sede=`, añade `&paquete_empresa=${paquete.empresa_lider_slug}` (o usa `getPaqueteDetalle` en `page.tsx` que ya devuelve `empresa_lider_slug`).
4. `tsc`/`build` limpios.
5. Commit: `feat(frontend): enlaces de servicios sueltos llevan la empresa del servicio`.

---

### Tarea 6.5.4 — `reservar/page.tsx` resuelve la empresa y la pasa a `CheckoutView`

**Files:** Modify `frontend/src/app/[lang]/reservar/page.tsx` · Modify `frontend/src/components/checkout-view.tsx`.

1. **`reservar/page.tsx`** (server component). Lee los query params y calcula `empresaSlug`:
   - `?paquete=<slug>&sede=<sede>` → ya resuelve el paquete con `getPaqueteDetalle(sede, slug)` → `empresaSlug = paquete.empresa_lider_slug`.
   - `?servicio=<slug>&empresa=<empresa>` → `empresaSlug = empresa` (del query). (Opcional: validar que el servicio existe llamando `getServiciosSede` y buscando el slug; si no, confiar en el query.)
   - Ninguno → `empresaSlug = process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol'` (pesca legacy).
   - **`getTarifa()` en esta página**: si `empresaSlug` != el del deploy y NO hay servicio/paquete → es raro (pesca legacy de otra empresa); para v1 basta `getTarifa(empresaSlug)`.
   - Pasa `empresaSlug` (string) como prop nueva a `<CheckoutView empresaSlug={empresaSlug} ... />`.
2. **`checkout-view.tsx`**:
   - Nueva prop `empresaSlug: string`.
   - Cada llamada a las 6 funciones de `api.ts` pasa `empresaSlug` como último arg:
     `getCupo(day, people, empresaSlug)`, `validarCodigoPromocional(codigo, contact.email, empresaSlug)`, `getExtras(people, moneda, empresaSlug)`, `getEstadoReserva(checkoutId, empresaSlug)`, `guardarReserva({...}, empresaSlug)`, `crearPago(reserva.id, {...}, empresaSlug)`.
   - **Stripe:** NO cambia. `crear-pago` devuelve `pago.publishable_key` de la empresa correcta y `stripe-panel.tsx` ya la usa. Solo confirma que sigue así.
3. `tsc --noEmit` + `npm.cmd run build` limpios.
4. Commit: `feat(frontend): el checkout usa la empresa del ítem elegido, no la del deploy`.

---

### Tarea 6.5.5 — Verificación manual (no hay tests de frontend)

Razona y anota en el reporte, para cada flujo, la URL final de `guardarReserva` y `crearPago`:
- **Pesca legacy** (`/reservar` sin params): `/api/<EMPRESA_SLUG>/reservas/` y `/api/<EMPRESA_SLUG>/reservas/<id>/crear-pago/`.
- **Servicio suelto de la misma empresa**: igual.
- **Paquete de la misma empresa**: `/api/<empresa_lider_slug>/reservas/` (== EMPRESA_SLUG en v1 si el deploy es de esa empresa).
- **Paquete/servicio de OTRA empresa de la sede**: `/api/<otra_empresa>/reservas/` — la reserva se crea en la otra empresa, el cobro usa SU cuenta de Stripe (`pago.publishable_key`), el webhook de esa empresa la confirma.

Si algún flujo no da la URL esperada, arréglalo antes de cerrar.

---

### Tarea 6.5.6 — Gate Sección 6.5

1. Backend: `test apps.fleet` sqlite + Postgres → OK (solo cambió `ServicioSerializer`).
2. Frontend: `npm.cmd run lint` · `npx.cmd tsc --noEmit` · `npm.cmd run build` → todo verde.
3. Registro de avance: "Sección 6.5 cerrada @ <sha>". Commit `docs(plan): Sección 6.5 cerrada`. **DETENTE y reporta** (incluye la tabla de URLs de la Tarea 6.5.5).

---

# SECCIÓN 7 — Cruza-empresa: bloquear + ADR-005 (fuera de v1)

### Tarea 7.1 — Confirmar el bloqueo + test

`PaqueteServicio.clean` (Tarea 4.2) ya rechaza componentes de otra empresa. Añade un test explícito
en `apps/fleet/tests_paquetes.py` si no lo cubriste: `PaqueteServicio(servicio=<de empresa B>, paquete=<líder A>).full_clean()` → `ValidationError` cuyo mensaje menciona "ADR-005". Commit si hubo cambio.

### Tarea 7.2 — Escribir `docs/superpowers/specs/2026-09-06-ADR-005-paquetes-cruza-empresa.md`

Contenido (prosa, no código):
- **Contexto:** cada empresa proveedora tiene su propia cuenta de Stripe. La empresa de marketing (operador de plataforma) **no tiene cuenta central a propósito** — así no carga con los impuestos de todas esas transacciones. No se usa Stripe Connect.
- **Problema:** un paquete cruza-empresa (pesca de A + hotel de B) implica que el dinero de cada servicio vaya a la cuenta de su empresa → N cobros a N cuentas. Stripe sin Connect no permite un solo `PaymentElement` que confirme N PaymentIntents de N cuentas distintas como "un solo pago percibido".
- **Estado v1:** bloqueado (`PaqueteServicio.clean`). Paquetes v1 = una sola empresa (`empresa_lider`).
- **Lo que ya quedó preparado:** `Paquete` tiene `sede` + `empresa_lider`; `ReservaPaqueteComponente` tiene `empresa` por componente (aunque v1 no lo use); el catálogo por sede itera empresas en su scope.
- **Opciones a evaluar cuando se retome** (sin recomendación cerrada): (a) N PaymentIntents secuenciales en el checkout con reembolsos parciales si un componente se cae; (b) `empresa_lider` cobra su parte online y las demás mandan link de pago aparte que envía la vendedora; (c) revisar si Stripe Connect con **direct charges** evita el problema fiscal (el cargo se crea en la cuenta conectada, el dinero nunca toca la plataforma).
- **Estado:** PROPUESTO, sin fecha.

Commit: `docs(adr): ADR-005 paquetes cruza-empresa (fuera de v1)`.

---

# SECCIÓN 8 — Deuda menor

### Tarea 8.1 — Nota en `backend/CLAUDE.md`
Añade en la sección de comandos/migraciones: "Toda data migration que haga `Modelo.objects.create/update/delete` sobre una tabla con RLS debe envolverse en `with apps.tenancy.rls.alcance_operador_migracion(schema_editor.connection):` — si no, revienta en Postgres bajo el rol de la app." Commit `docs: nota sobre alcance_operador_migracion en data migrations`.

### Tarea 8.2 — Import perezoso de `scope` en settings (M4)
`backend/config/settings/base.py`: quita `from apps.tenancy import scope` del cuerpo del módulo. Crea `backend/apps/tenancy/permisos_unfold.py` con funciones `puede_ver_finanzas(request)`, `es_operador(request)` que importan `scope` adentro. Los lambdas de `UNFOLD['SIDEBAR']` llaman esas funciones (import perezoso de `apps.tenancy.permisos_unfold` dentro del lambda, o al inicio de `UNFOLD = {...}` que corre después de apps). Verifica `manage.py check` limpio. Commit.

### Tarea 8.3 — `MotivoNoDisponible` frontend (B3)
Ya cubierto en Tarea 5.8. Si 5.8 no se hizo aún, hazlo aquí: `type MotivoNoDisponible = 'lleno' | 'sin_panga' | 'sin_lugar'` en `api.ts`, manejo en `checkout-view.tsx`. Commit.

### Tarea 8.4 — `Tarifa.save` race (B4)
`backend/apps/fleet/models.py::Tarifa.save`: reemplaza el `if not self.pk: existente = Tarifa.objects.filter(empresa=self.empresa).first(); if existente: self.pk = existente.pk` por un `select_for_update` dentro de una transacción, o documenta que el `UniqueConstraint(empresa)` + un `try/except IntegrityError` que reintenta como update es aceptable. Test: dos `Tarifa.objects.create(empresa=X)` seguidos → la segunda actualiza, no revienta. Commit.

### Tarea 8.5 — Jefe no edita usuarios ajenos (B5)
`backend/apps/tenancy/admin_mixins.py::EmpresaScopedUserAdminMixin`: para un jefe (no operador), además de ocultar `is_superuser`/`groups`/`user_permissions`, hacer `password` y `email` de solo lectura sobre usuarios que no sean él mismo (`get_readonly_fields`). Test: jefe intenta cambiar el email de otro usuario de su empresa vía admin → el campo no es editable. Commit.

### Tarea 8.6 — Lista consolidada de RLS (B8)
`backend/apps/tenancy/tests_rls.py`: añade un test `# postgres-only` que consulta `pg_policies` y verifica que **toda tabla con una columna `empresa_id` o `empresa_lider_id`** tiene una política `tenancy_alcance` (o equivalente vía EXISTS). Query: `SELECT c.relname FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid WHERE a.attname IN ('empresa_id','empresa_lider_id') AND c.relkind='r' AND c.relname LIKE ANY(ARRAY['fleet_%','bookings_%','payments_%','finance_%'])` menos las que llegan a empresa vía FK sin columna propia (whitelist explícita: `bookings_reservaextra`, `bookings_reservatransporte`, `fleet_serviciopersonalizacion`, `bookings_reservapaqueteserviciorem*`, `bookings_reservapaquetepers*`). El test falla si aparece una tabla nueva sin política. Commit `test(rls): guardarraíl — toda tabla con empresa_id tiene política`.

### Tarea 8.7 — Gate Sección 8
sqlite + Postgres `test apps config` → `OK`. Commit `docs(plan): Sección 8 cerrada`.

---

# SECCIÓN 9 — Cierre

- [x] **9.1** `manage.py test apps config` verde en sqlite Y Postgres (drop antes).
- [x] **9.2** `check --deploy --fail-level WARNING` con `config.settings.production` + env de relleno (ver `.github/workflows/ci.yml` para los valores).
- [x] **9.3** Frontend `npm.cmd run lint` · `npx.cmd tsc --noEmit` · `npm.cmd run build` verdes.
- [x] **9.4** Repasa los diffs de todas las secciones: ningún `como_operador_plataforma()` en vista `AllowAny`; ningún filtro de empresa olvidado; ninguna cifra fuera de `pricing.py`; toda tabla nueva con RLS + en el guardarraíl de 8.6.
- [x] **9.5** Actualiza `backend/CLAUDE.md` (cupo por `estrategia_cupo`, hospedaje, paquetes v1 una-empresa, `ReservaPaqueteComponente`), `frontend/CLAUDE.md` (campos nuevos del checkout), `docs/deploy/RUNBOOK-corte-multi-empresa.md` (paso: `CREATE EXTENSION btree_gist` en la BD de producción antes de migrar; sembrar `Servicio`/`Recurso`/`Paquete` reales).
- [x] **9.6** Actualiza `docs/superpowers/specs/2026-08-31-...-ADRs.md`: ADR-003/004 pasan a IMPLEMENTADO con nota de las desviaciones; enlaza ADR-005.
- [x] **9.7** Memoria (`C:\Users\kkjf\.claude\projects\C--Users-kkjf-desarrollo-sistema-pescadeportiva\memory\`): marca `plan-correccion-hallazgos` como completado; mueve lo que quede a `pendientes-manuales-produccion` (`btree_gist`, rol de BD sin BYPASSRLS, sembrar catálogo real).
- [x] **9.8** Resumen para el dueño: qué migraciones corren en producción y en qué orden; qué pasos manuales quedan.
- [ ] **9.9** Integración de la rama: PR contra `feature/pieza6-frontend-multitenant` o merge, según decida el dueño. (Pendiente decisión del dueño).

---

## Autorrevisión (para el que ejecuta, al terminar cada sección)

1. **¿El test que escribiste falla ANTES de la implementación?** Si nunca lo viste rojo, no sabes si prueba algo.
2. **¿Corriste Postgres, no solo sqlite?** sqlite no tiene RLS, ni locks, ni `EXCLUDE`. La mitad de los bugs de este proyecto son invisibles en sqlite.
3. **¿Dropeaste `test_pescadeportiva_test` antes del run de Postgres?** Si no, los errores que ves pueden ser de un run anterior a medias.
4. **¿El commit tiene SOLO los archivos de esa tarea?** `git status` antes de `git add`.
5. **¿Rompiste algún test existente?** El gate de sección corre `test apps config` entero por eso.
