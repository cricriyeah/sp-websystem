# Refactor / Remediation Plan — sistema-pescadeportiva — 2026-08-12

Work packets ordered by tier. Tier = priority. Effort is wall-clock for one dev.

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
