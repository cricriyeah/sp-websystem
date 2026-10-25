# Tasks from Audit 2026-08-12 (bd unavailable — `bd: command not found`)

`bd` CLI is not installed/in PATH in this environment. Tasks below are the markdown
fallback per audit protocol. Re-run `bd create` for each once `bd` is available, or
track manually.

| Estado | Priority | Title | Source | Effort |
|--------|----------|-------|--------|--------|
| HECHO 2026-08-12 | P0 | SEC: Fix SECURE_SSL_REDIRECT infinite loop — add SECURE_PROXY_SSL_HEADER (production.py:29) | F-01 / WP-01 | 15m |
| HECHO 2026-08-12 | P0 | CHORE: Commit 91 pending files (finance app, payments/services.py, notifications) | F-02 / WP-02 | 1-2h |
| HECHO 2026-08-12 | P1 | SEC: Untrack backend/db.sqlite3 from git, add to .gitignore | F-03 / WP-03 | 15m |
| HECHO 2026-08-13 | P1 | SEC: Add DEFAULT_THROTTLE_CLASSES to public payment/booking endpoints | F-04 / WP-05 | 2h |
| HECHO 2026-08-13 | P1 | CHORE: Add CI pipeline (.github/workflows) running backend tests + frontend build | F-05 / WP-04 | 3-4h |
| PENDIENTE | P1 | CHORE: Wire up Sentry (or equivalent) error tracking | F-06 / WP-06 | 2-3h |
| HECHO 2026-08-13 | P2 | CHORE: Install pip-audit, scan backend/requirements.txt for CVEs | F-07 / WP-14 | 30m |
| PENDIENTE | P2 | CHORE: Add frontend test coverage (Vitest + Playwright) for checkout-view.tsx | F-08 / WP-08 | 1-2 days |
| HECHO 2026-08-13 | P2 | SEC: Fix trusted-proxy IP capture in ip_del_cliente (serializers.py:15) | F-09 / WP-07 | 1h |
| HECHO 2026-08-13 | P2 | CHORE: Add render.yaml defining cron schedules for conciliar_pagos / limpiar_checkouts_abandonados | F-10 / WP-09 | 2h |
| HECHO 2026-08-13 | P2 | DOCS: Write docs/threat-models/TM-payments.md | F-11 / WP-10 | 4h |
| HECHO 2026-08-13 | P2 | DOCS: Write docs/vendors/stripe.md and docs/vendors/supabase.md | F-12 / WP-11 | 2h |
| HECHO 2026-08-13 | P3 | CHORE: Add security headers (CSP, X-Frame-Options) in next.config.ts + SECURE_HSTS_SECONDS | F-13/F-15 / WP-12 | 1h |
| PENDIENTE | P3 | CHORE: Move Django admin off default /admin/ path or add IP allowlist | F-14 / WP-13 | 30m |
| PENDIENTE | P3 | CHORE: Replace stale TODO in hero.tsx:40 with real fleet photography | F-16 | — |

Total: 14 tasks (P0:2 P1:4 P2:6 P3:3 — one P3 item, hero.tsx TODO, is a content/backlog note not a dev task).
Cerradas: 11. Abiertas: 4.

Al escribir los documentos de proveedor salieron acciones concretas que no eran
parte del hallazgo original, ver `docs/vendors/supabase.md`.

## Decisiones registradas

- **2026-08-14 — Base de datos: seguimos con Supabase, en plan de pago.** Se
  evaluo migrar a Convex y se descarto: Convex no es Postgres ni se conecta a
  Django (no habla SQL, la logica vive en funciones TypeScript suyas), asi que
  migrar significaria reescribir el backend entero — admin de Unfold incluido,
  que es el backoffice completo de la operacion. Ademas Convex no tiene PITR
  (es una solicitud de funcion abierta), o sea que empeoraria justo la
  preocupacion que origino la evaluacion. Se conserva la ventaja de usar Supabase
  solo como Postgres gestionado: cambiar de proveedor sigue siendo un `pg_dump`
  mas variables de entorno.
- **2026-08-14 — Tier gratuito de Supabase descartado**, no garantiza respaldos.
- **2026-08-14 — Sin PITR por ahora, riesgo aceptado.** ~$100 USD/mes es
  desproporcionado al volumen actual. Se acepta ventana de perdida de hasta 24
  horas. Mitigacion implementada: copia oculta de cada confirmacion al negocio
  (`RESEND_BCC`). Mitigacion recomendada pendiente: cron de `pg_dump` cada 6
  horas a almacenamiento externo (~$2/mes) para bajar la ventana a 6 horas.
  Razonamiento completo y criterio de reevaluacion en `docs/vendors/supabase.md`.

## Hallazgo nuevo fuera de la auditoria (2026-08-13)

| Estado | Priority | Title | Effort |
|--------|----------|-------|--------|
| HECHO 2026-08-13 | P0 | DEPLOY: `requirements.txt` no tenia servidor WSGI — sin gunicorn el servicio de Render no arranca. Agregado `gunicorn==26.0.0` + `startCommand` en render.yaml | 15m |

La auditoria no lo detecto porque solo reviso los settings de Django, no el arranque
del proceso: `manage.py runserver` funciona en local y nada senala que falte, hasta que
el deploy no levanta.

---

# Tasks from Re-Audit 2026-08-14 (`bd` still unavailable)

Fuente: `docs/audit/AUDIT-2026-08-14.md` (F-17..F-23). Verificacion de los 12
hallazgos previos marcados HECHO: todos siguen en pie salvo lo ya sabido
(F-06/F-08/F-14/F-16 siguen abiertos, sin cambio de severidad salvo la nota de
F-06 abajo). Motivador de esta pasada: el dueño va a empezar pruebas en
produccion con llaves de Stripe reales y Supabase real.

| Estado | Priority | Title | Source | Effort |
|--------|----------|-------|--------|--------|
| HECHO 2026-08-14 | P0 | DEPLOY: healthCheckPath (`/api/tarifa/`) 503-ea hasta crear `Tarifa` a mano — Render cancela el primer deploy por health check fallido. Agregar `/healthz` desacoplado de datos de negocio. | F-17 / WP-15 | 30m |
| HECHO 2026-08-14 | P0 | DOCS: Escribir `docs/deploy/GO-LIVE.md` con la secuencia exacta de primer arranque (env vars, registrar webhook live, createsuperuser, crear Tarifa, setup_roles, altas de vendedora) + `frontend/.env.example` | F-18/F-22/F-23 / WP-16 | 1-2h |
| HECHO 2026-08-14 | P0 | SEC/DATA: Condicion de carrera en `validar_cupo_diario` — dos reservas del mismo dia pagadas en paralelo (Postgres real, sin lock) pueden sobrevender el cupo. select_for_update() solo cubre la reserva propia, no el conteo del dia. No se puede probar con SQLite. | F-19 / WP-17 | 3-4h |
| HECHO 2026-08-14 | P0 | CHORE: Agregar Postgres real a CI (`services: postgres`) — los 139 tests nunca han corrido contra el motor de produccion. Requisito para poder probar F-19 de verdad. | F-20 / WP-18 | 2-3h |
| PENDIENTE | P1 | CHORE: Fijar `stripe.api_version` explicito (hoy usa el default de la cuenta, sin pin) | F-21 / WP-19 | 30m |
| REEVALUAR | P1→P0? | Sentry/alertas (F-06 original) — con F-19 en juego, un sobrecupo o webhook atorado solo se descubre por reclamo de cliente o corriendo `conciliar_pagos --dry-run` a mano. Subir prioridad antes de abrir a produccion real. | F-06 (existente) | 2-3h |

Total nuevo: 6 items (P0:4 P1:2, uno de ellos una re-evaluacion de prioridad de
un hallazgo ya existente, no uno nuevo). F-22/F-23 son items de checklist, no
bugs de codigo — se resuelven escribiendo el documento de WP-16, no con un cambio
de codigo aparte.

## Decisiones/hallazgos de esta pasada que no son tareas

- `docs/threat-models/TM-payments.md` C-3/C-6 asumen que el chequeo de cupo esta
  serializado; no cubren dos reservas *distintas* del mismo dia en paralelo. Se
  recomienda una entrada C-10 una vez resuelto F-19 (WP-17), no una tarea aparte
  — va como parte de ese work packet.
- No se encontro `vercel.json` ni configuracion de despliegue del frontend en el
  repo — se desconoce con certeza donde vive el build de produccion del
  frontend. Pregunta abierta para el mantenedor, no un hallazgo de codigo.

# Tasks from Audit 2026-10-24 (backend/) — bd unavailable (`bd: command not found`)

Fuente: `docs/audit/AUDIT-2026-10-24.md`. Brechas: `docs/governance/GAP-REGISTER.yaml`. Sin P0: nada bloquea el arranque; los P1 son previos a vender en serio. No duplica lo ya conocido (ver sección final del informe).

| Estado | Priority | Title | Source | Effort |
|--------|----------|-------|--------|--------|
| PENDIENTE | P1 | SEC: Subir djangorestframework 3.18.0 -> 3.18.2 (CVE-2026-114138, CVE-2026-114136) y quitar continue-on-error del job pip-audit (ci.yml:121) | B-01 / GAP-1 | 30m |
| PENDIENTE | P1 | SEC: Limite de peticiones evadible con X-Forwarded-For: NUM_PROXIES=1 y cache compartida (base.py:73-110) | B-02 / GAP-2 | 1-2h |
| PENDIENTE | P1 | SEC: Exigir checkout_id en crear-pago y confirmar-captura de ordenes (payments/views.py:1248-1402) | B-03 / GAP-3 | 2h |
| PENDIENTE | P1 | SEC: Cifrar en reposo las llaves secretas de Stripe por empresa antes de capturar sk_live_ (tenancy/models.py:75-78, ADR-002) | B-04 / GAP-4 | 1d |
| PENDIENTE | P1 | OPS: Respaldo previo a migrate en cada deploy, prueba de restauracion y confirmar plan Pro/PITR de Supabase | B-05 / GAP-6 | 3-6h |
| PENDIENTE | P2 | SEC: Verificar rol de Postgres de produccion (pg_roles) y repetir la guardia fuera del build | B-06 / GAP-10 | 2h |
| PENDIENTE | P2 | SEC: Turnstile tambien en CrearOrdenView y aviso de arranque si falta TURNSTILE_SECRET_KEY | B-07 / GAP-7 | 2h |
| PENDIENTE | P2 | OPS: conciliar_pagos debe fallar con codigo distinto de 0 / logger.error ante error de Stripe; latido y monitor externo de /healthz | B-08 / GAP-8 | 2h |
| PENDIENTE | P2 | SEC: Segundo factor para el admin (jefes y operador); ver F-14 de agosto sobre la ruta /admin/ | B-09 / GAP-9 | 1d |
| PENDIENTE | P2 | REFACTOR: Dividir payments/views.py (1638 lineas) y luego bookings/admin.py (2952) sin cambiar logica | B-11 / GAP-11 | 2-4d |
| PENDIENTE | P3 | CHORE: Actualizar ENDURECIMIENTO.md (RLS), agregar *.log a .gitignore, retirar STRIPE_* globales sin uso | B-10,B-12,B-13 / GAP-12 | 1h |

Total: 11 tareas (P0:0 P1:5 P2:5 P3:1).
