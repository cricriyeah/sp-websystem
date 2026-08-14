# Refactor / Remediation Plan — sistema-pescadeportiva

Work packets ordered by tier. Tier = priority. Effort is wall-clock for one dev.

WP-01 through WP-14 are from the 2026-08-12 audit (11 of 14 done — see
`docs/audit/AUDIT-2026-08-14.md` "Verification of prior findings" for per-item
status). WP-15 onward are from the 2026-08-14 re-audit
(`docs/audit/AUDIT-2026-08-14.md`, findings F-17..F-21), driven by the upcoming
switch to real Stripe keys + real Supabase Postgres.

---

## WP-01: Fix production SSL redirect loop
Tier: 0 | Effort: 15m | Risk: Low
Files: `backend/config/settings/production.py`
Steps:
1. Confirm the header Render's proxy sets for the original scheme (default: `X-Forwarded-Proto`).
2. Add `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` to `production.py` near `SECURE_SSL_REDIRECT = True`.
3. Deploy to a staging/preview Render service first if available; curl the root URL and confirm a single 301 → 200, not a loop.
Tests: manual curl against staging; confirm no redirect loop.
Done when: production URL loads over HTTPS without infinite redirects.

## WP-02: Commit pending work
Tier: 0 | Effort: 1-2h | Risk: Low
Files: all 91 files in `git status --porcelain`
Steps:
1. Review diff for anything that shouldn't be committed (stray local config, real secrets).
2. Split into logical commits: `apps/finance` app, `apps/notifications`, `apps/payments/services.py`, migrations, frontend components.
3. Push to remote.
Tests: `git status --porcelain` returns empty (or only expected local-only files).
Done when: no uncommitted application code remains; remote has a backup of current work.

## WP-03: Untrack db.sqlite3
Tier: 0 | Effort: 15m | Risk: Low (verify no real PII in history first)
Files: `.gitignore`, `backend/db.sqlite3`
Steps:
1. `git log -p -- backend/db.sqlite3` — confirm no real customer data was ever committed to history.
2. Add `backend/db.sqlite3` to `.gitignore`.
3. `git rm --cached backend/db.sqlite3`.
4. If real data was found in history, coordinate a history rewrite (`git filter-repo`) before this is pushed anywhere shared.
Tests: `git ls-files | grep db.sqlite3` returns nothing after the commit.
Done when: sqlite file no longer tracked; local dev DB still works via `local.py`.

## WP-04: Add CI pipeline
Tier: 1 | Effort: 3-4h | Risk: Low
Files: new `.github/workflows/ci.yml`
Steps:
1. Backend job: checkout, setup Python, `pip install -r backend/requirements.txt`, `python manage.py test apps` (from `backend/`, using `local` settings/sqlite).
2. Frontend job: checkout, setup Node, `npm ci`, `npx tsc --noEmit`, `npm run build`.
3. Add `pip-audit -r backend/requirements.txt` and `npm audit --audit-level=high` as non-blocking-first, then promote to blocking once clean.
4. Require the workflow to pass before merge (branch protection, if using PRs).
Tests: push a PR, confirm both jobs run and pass on the current `main`.
Done when: CI is green on `main` and required for future PRs.

## WP-05: Add rate limiting to public payment endpoints
Tier: 1 | Effort: 2h | Risk: Low
Files: `backend/config/settings/base.py`, `backend/apps/payments/views.py`, `backend/apps/bookings/views.py`
Steps:
1. Add `DEFAULT_THROTTLE_CLASSES: ['rest_framework.throttling.AnonRateThrottle']` and a conservative `DEFAULT_THROTTLE_RATES` (e.g. `{'anon': '20/min'}'`) to `REST_FRAMEWORK` in `base.py`.
2. Verify `CrearPagoView` and `ReservaCheckoutView` inherit the default (no `throttle_classes = []` override needed).
3. Add a scoped rate for `StripeWebhookView` bypass if the default throttle would ever block legitimate Stripe retries (webhook traffic is server-to-server, from Stripe's IPs — confirm it isn't throttled by the anon class, or exempt it explicitly).
Tests: hit `crear-pago/` >20 times/min in a local test, confirm 429 after the limit; confirm webhook still processes Stripe test events without throttling.
Done when: anon throttle active on public write endpoints, webhook unaffected.

## WP-06: Wire up error tracking
Tier: 1 | Effort: 2-3h | Risk: Low
Files: `backend/config/settings/base.py` or `production.py`, `backend/requirements.txt`
Steps:
1. Add `sentry-sdk` (or chosen alternative) to `requirements.txt`.
2. Initialize in `production.py` with DSN from env var, `DJANGO_SETTINGS_MODULE`-aware.
3. Confirm `logger.exception(...)` calls in `apps/payments/views.py` and `apps/notifications` surface as Sentry events.
4. Set an alert rule for any exception under the `apps.payments` logger.
Tests: trigger a deliberate exception in staging, confirm it appears in Sentry within a minute.
Done when: webhook/refund/notification failures are visible without reading Render logs.

## WP-07: Fix trusted-proxy IP capture for legal evidence
Tier: 1 | Effort: 1h | Risk: Low
Files: `backend/apps/bookings/serializers.py:15-21`
Steps:
1. Confirm with Render docs how many proxy hops sit in front of the app (usually exactly one).
2. Replace `forwarded.split(',')[0]` with logic that takes the IP at the correct trusted-hop position (or adopt `django-ipware` with `proxy_count=1`).
Tests: add a unit test that sends a spoofed multi-value `X-Forwarded-For` and asserts the captured IP is the trusted-hop value, not attacker-controlled.
Done when: deslinde IP capture can't be spoofed by a client-supplied header value.

## WP-08: Add frontend test coverage for checkout
Tier: 2 | Effort: 1-2 days | Risk: Low
Files: `frontend/package.json`, new `frontend/src/components/checkout-view.test.tsx`, new `frontend/e2e/`
Steps:
1. Add Vitest + React Testing Library; cover step transitions and currency-dependent pricing logic in `checkout-view.tsx`.
2. Add one Playwright golden-path spec: load `/es/reservar`, fill form, reach the Stripe Elements mount point (mock Stripe in test mode).
3. Wire both into the CI job from WP-04.
Tests: `npm test` runs and passes; Playwright spec passes against a local dev server.
Done when: a regression in checkout state transitions fails CI, not a customer's browser.

## WP-09: Add render.yaml for cron jobs
Tier: 2 | Effort: 2h | Risk: Low
Files: new `render.yaml`
Steps:
1. Define `cronJobs:` entries for `conciliar_pagos --dias 7` (hourly, per `backend/CLAUDE.md`) and `limpiar_checkouts_abandonados --dias 30` (daily).
2. Reference the existing web service's env vars/build command so schedules and deploy config live in the same reviewable file.
3. Confirm against Render's actual dashboard config before committing (avoid duplicate cron jobs).
Tests: manual `render.yaml` validation (Render CLI or dashboard "Blueprint" import in a scratch environment).
Done when: cron schedule is defined in-repo and matches what's live in Render.

## WP-10: Write payment threat model
Tier: 2 | Effort: 4h | Risk: Low
Files: new `docs/threat-models/TM-payments.md`
Steps:
1. Transcribe the trust-boundary rules already documented in `backend/CLAUDE.md` ("Garantias del cobro") into a threat-model format: webhook as sole source of truth, idempotency guarantees, refund/dispute handling, amount-mismatch logging-not-rejecting rationale.
2. Add a diagram or table of the webhook event types handled (`payment_intent.succeeded`, `charge.refunded`, `charge.dispute.*`) and what state transition each triggers.
3. Cross-reference `docs/contexto-negocio.md` for the business rules the code implements.
Tests: n/a (documentation).
Done when: a new developer can understand the payment trust model without reading `services.py` line by line.

## WP-11: Vendor risk docs
Tier: 2 | Effort: 2h | Risk: Low
Files: new `docs/vendors/stripe.md`, new `docs/vendors/supabase.md`
Steps: one page per vendor — DPA link, breach-notification SLA, data retained, deletion process, sub-processor list if published.
Tests: n/a.
Done when: both pages exist and link to the vendor's current DPA/ToS.

## WP-12: Security headers + HSTS
Tier: 3 | Effort: 1h | Risk: Low
Files: `frontend/next.config.ts`, `backend/config/settings/production.py`
Steps:
1. Add a `headers()` function in `next.config.ts` with baseline CSP (allowing Stripe.js/Elements domains), `X-Frame-Options: DENY`, `Referrer-Policy`.
2. After WP-01 is confirmed working, add `SECURE_HSTS_SECONDS = 31536000`, `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`.
Tests: `curl -I` against staging, confirm headers present.
Done when: both frontend and backend responses carry the new headers.

## WP-13: Admin path hardening
Tier: 3 | Effort: 30m | Risk: Low
Files: `backend/config/urls.py:31`
Steps: move admin off the default `/admin/` path, or add an IP allowlist via middleware/Render firewall rules if available.
Tests: confirm old path 404s, new path serves the admin login.
Done when: admin no longer reachable at the default path.

## WP-14: Backend CVE scan
Tier: 1 | Effort: 30m | Risk: Low
Files: `backend/requirements.txt`
Steps: `pip install pip-audit && pip-audit -r backend/requirements.txt`; triage any findings.
Tests: n/a — one-off scan, then folded into WP-04 CI job.
Done when: current dependency set is confirmed clean or findings are triaged into follow-up tasks.

---

## WP-15: Decouple health check from business data (F-17)
Tier: 0 | Effort: 30m | Risk: Low
Files: `backend/config/urls.py`, new `backend/apps/fleet/views.py` (or a new tiny `apps/core`), `render.yaml`
Steps:
1. Add a `GET /healthz` view that returns 200 based on infra readiness only (e.g. `connection.ensure_connection()` then 200; no `Tarifa` lookup).
2. Mount it in `config/urls.py` outside `/api/` (avoid any future confusion with the public API surface).
3. Change `render.yaml`'s `healthCheckPath` from `/api/tarifa/` to `/healthz`.
4. Leave `/api/tarifa/`'s 503-when-unconfigured behavior untouched — that's correct for its actual client-facing purpose.
Tests: manual curl on a fresh migrated-but-unseeded DB, confirm `/healthz` returns 200 while `/api/tarifa/` still correctly returns 503.
Done when: a freshly migrated, zero-data database passes Render's health check.

## WP-16: Go-live checklist doc + first-boot sequencing (F-18, F-22, F-23)
Tier: 0 | Effort: 1-2h | Risk: Low
Files: new `docs/deploy/GO-LIVE.md`
Steps:
1. Write the ordered checklist from `AUDIT-2026-08-14.md`'s "Go-Live Checklist" section as a standalone doc: env vars (with required-vs-optional table from F-22), Stripe live-mode webhook registration, first-boot Shell sequence (`createsuperuser` → create `Tarifa` → `setup_roles` → vendedora accounts), frontend `NEXT_PUBLIC_API_URL` verification (F-23), and the `X-Forwarded-Proto` verification already flagged as open in `TM-payments.md`.
2. Commit `frontend/.env.example` alongside (F-23), mirroring `backend/.env.example`'s format.
Tests: n/a — documentation, but walk it once against a real or scratch Render environment before the actual go-live to confirm no step is missing.
Done when: another person could execute the first production deploy from this doc alone.

## WP-17: Fix cupo-diario race condition under concurrent Postgres writes (F-19)
Tier: 0 | Effort: 3-4h | Risk: Medium (touches the core booking invariant — review carefully)
Files: `backend/apps/bookings/models.py:47-76` (`CupoDiario`, `validar_cupo_diario`), `backend/apps/payments/services.py:56-94` (`aplicar_pago_exitoso`), `backend/apps/payments/management/commands/conciliar_pagos.py` (confirm it goes through the same locked path)
Steps:
1. In `validar_cupo_diario`, acquire a row lock scoped to `fecha` before counting — simplest approach: `CupoDiario.objects.select_for_update().get_or_create(fecha=fecha, defaults={'cupo_maximo': CUPO_MAXIMO_DEFAULT})`, then use that row's `cupo_maximo` (already the pattern `cupo_maximo_del_dia` follows, just without the lock) and only then run the `.count()`.
2. Confirm every caller path that can transition a `Reserva` into `ESTADOS_QUE_OCUPAN_CUPO` runs inside `transaction.atomic()` — webhook path already does; verify admin-driven manual state changes (e.g. cash settlement, manual "Cancelar por mal clima" reversal if any) and `conciliar_pagos` (which calls `aplicar_pago_exitoso`, already atomic) are covered.
3. Double-check `select_for_update()` on a freshly-`get_or_create`'d row doesn't deadlock against itself in SQLite-based tests (SQLite ignores `select_for_update()` per Django docs — no-op there, so this is safe for the existing suite, but see WP-18 to actually prove it works).
Tests: unit test with `TransactionTestCase` for the sequential cases (still must not regress); the real proof is the concurrency test added in WP-18, which requires Postgres.
Done when: two reservations for the same near-full date, paid concurrently via two real threads/connections against Postgres, cannot both succeed when only one slot remains.

## WP-18: Add Postgres to CI, close the portability blind spot (F-20)
Tier: 0 | Effort: 2-3h | Risk: Low
Files: `.github/workflows/ci.yml`, possibly new `backend/config/settings/ci.py`
Steps:
1. Add a `postgres:16` `services:` container to the `backend` CI job (GitHub Actions native support, free).
2. Point `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` at the service container; either reuse `settings/production` with `DEBUG` overridden for test convenience, or add a thin `settings/ci.py` importing from `production.py`'s DB config but relaxing SSL/HSTS checks that don't apply to a CI container.
3. Run `python manage.py test apps` against it in the same job (or a parallel one) as the existing SQLite run — keep both, since SQLite is still useful for fast local iteration.
4. Add the concurrency regression test from WP-17 to this Postgres-backed run specifically (it cannot run meaningfully under SQLite).
Tests: the CI job itself is the test — confirm it goes green with a real Postgres connection, and confirm it goes red if WP-17's fix is reverted locally (sanity-check the test actually catches the bug).
Done when: every backend test, including the new concurrency test, runs against Postgres on every push/PR.

## WP-19: Pin Stripe API version (F-21)
Tier: 1 | Effort: 30m | Risk: Low
Files: `backend/apps/payments/views.py`, `backend/apps/payments/services.py` (or a single shared init point, e.g. `apps/payments/apps.py` `AppConfig.ready()`), `docs/vendors/stripe.md`
Steps:
1. Set `stripe.api_version = '<version tested against live keys>'` once, in one place (avoid repeating the literal across every file that imports `stripe`).
2. Record the pinned version and the date it was last reviewed in `docs/vendors/stripe.md`.
3. Add a note to the go-live checklist (WP-16) to bump this deliberately, not silently, whenever the Stripe SDK is upgraded.
Tests: run the existing payment test suite after pinning, confirm no behavior change (expected — pinning to the version already in effect should be a no-op).
Done when: `stripe.api_version` is explicit in code and documented.
