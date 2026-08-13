# Tasks from Audit 2026-08-12 (bd unavailable — `bd: command not found`)

`bd` CLI is not installed/in PATH in this environment. Tasks below are the markdown
fallback per audit protocol. Re-run `bd create` for each once `bd` is available, or
track manually.

| Priority | Title | Source | Effort |
|----------|-------|--------|--------|
| P0 | SEC: Fix SECURE_SSL_REDIRECT infinite loop — add SECURE_PROXY_SSL_HEADER (production.py:29) | F-01 / WP-01 | 15m |
| P0 | CHORE: Commit 91 pending files (finance app, payments/services.py, notifications) | F-02 / WP-02 | 1-2h |
| P1 | SEC: Untrack backend/db.sqlite3 from git, add to .gitignore | F-03 / WP-03 | 15m |
| P1 | SEC: Add DEFAULT_THROTTLE_CLASSES to public payment/booking endpoints | F-04 / WP-05 | 2h |
| P1 | CHORE: Add CI pipeline (.github/workflows) running backend tests + frontend build | F-05 / WP-04 | 3-4h |
| P1 | CHORE: Wire up Sentry (or equivalent) error tracking | F-06 / WP-06 | 2-3h |
| P2 | CHORE: Install pip-audit, scan backend/requirements.txt for CVEs | F-07 / WP-14 | 30m |
| P2 | CHORE: Add frontend test coverage (Vitest + Playwright) for checkout-view.tsx | F-08 / WP-08 | 1-2 days |
| P2 | SEC: Fix trusted-proxy IP capture in ip_del_cliente (serializers.py:15) | F-09 / WP-07 | 1h |
| P2 | CHORE: Add render.yaml defining cron schedules for conciliar_pagos / limpiar_checkouts_abandonados | F-10 / WP-09 | 2h |
| P2 | DOCS: Write docs/threat-models/TM-payments.md | F-11 / WP-10 | 4h |
| P2 | DOCS: Write docs/vendors/stripe.md and docs/vendors/supabase.md | F-12 / WP-11 | 2h |
| P3 | CHORE: Add security headers (CSP, X-Frame-Options) in next.config.ts + SECURE_HSTS_SECONDS | F-13/F-15 / WP-12 | 1h |
| P3 | CHORE: Move Django admin off default /admin/ path or add IP allowlist | F-14 / WP-13 | 30m |
| P3 | CHORE: Replace stale TODO in hero.tsx:40 with real fleet photography | F-16 | — |

Total: 14 tasks (P0:2 P1:4 P2:6 P3:3 — one P3 item, hero.tsx TODO, is a content/backlog note not a dev task).
