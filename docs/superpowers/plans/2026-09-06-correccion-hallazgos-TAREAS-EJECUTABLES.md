# Corrección de hallazgos multi-sede — Tareas ejecutables

> **Para el agente que ejecuta:** este documento es autosuficiente. NO necesitas
> re-derivar diseño. Haz las tareas **en orden**, una por una, con su ciclo
> completo (test que falla → código → test verde → commit). Cada tarea termina
> con un commit. Si una tarea te obliga a tomar una decisión de producto que
> este documento no contempla: **para y pregunta**, no adivines.

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

1. sqlite: `test apps config` → `OK`. 2. Postgres (drop + `test apps config --noinput`) → `OK`. 3. Actualiza el Registro de avance del plan de alto nivel: "Sección 2 cerrada @ <sha>". Commit `docs(plan): Sección 2 cerrada`.

---
