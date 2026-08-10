# CLAUDE.md — backend/

Notas especificas de este modulo. Contexto de negocio completo: ../docs/contexto-negocio.md.

## Estructura y settings

- Apps viven bajo `apps/` (paquete), no como apps top-level: `apps.fleet`, `apps.bookings`.
  Cada `AppConfig` usa `name = 'apps.<app>'` y `label = '<app>'`.
- Settings split en `config/settings/{base,local,production}.py`. `manage.py` usa
  `local` por defecto; `wsgi.py`/`asgi.py` usan `production` por defecto (Render las sobreescribe
  via `DJANGO_SETTINGS_MODULE` solo si hace falta otra cosa).
- `production.py` lee todo de variables de entorno (`DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`,
  `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DJANGO_ALLOWED_HOSTS`) — falla explicito si faltan, no hay defaults.

## Comandos (Windows, venv en `backend/venv/`)

```
venv/Scripts/python.exe manage.py runserver 8000
venv/Scripts/python.exe manage.py makemigrations
venv/Scripts/python.exe manage.py migrate
```

## Estado de las apps

- `fleet`, `bookings`: modelos + admin implementados. Backoffice basico (item 1 de
  contexto-negocio.md) ya cubre catalogo + reservas + roles, ver abajo.
- `payments`: API implementada (crear PaymentIntent + webhook), ver seccion "API
  publica (frontend)" abajo. `notifications`: carpeta vacia (`__init__.py` solo) —
  sin implementar todavia (WhatsApp + email de confirmacion).
- `fleet.Tarifa`: singleton (`pk` forzado a 1 en `save()`) con el precio unico del tour
  (doc: "precio fijo, no varia por clase"). El frontend ya lee este precio via
  `GET /api/tarifa/` (`reservar/page.tsx`, server-side) — ya no hardcodea 2 precios.

## API publica (frontend)

Sin autenticacion (`AllowAny` en `REST_FRAMEWORK`) — la web nunca loguea, solo crea
reservas/pagos. CORS restringido a los origenes del frontend
(`CORS_ALLOWED_ORIGINS` en `settings/local.py` y `settings/production.py`, esta ultima
via env var). Rutas montadas bajo `/api/` en `config/urls.py`:

- `GET /api/tarifa/` — precio actual del tour (`apps/fleet`).
- `GET /api/cupo/?fecha=YYYY-MM-DD` — cupo restante ese dia, solo informativo
  (`apps/bookings`); la validacion definitiva ocurre al confirmar el pago.
- `POST /api/reservas/` — crea `Reserva` en `pendiente_pago`, `canal_origen='web'`
  (`apps/bookings`). No ocupa cupo todavia.
- `POST /api/reservas/<id>/crear-pago/` — crea el `PaymentIntent` de Stripe. El monto
  (tarifa + amenidades de `apps/payments/pricing.py` + 100%/30% anticipo) se calcula
  siempre en el servidor, nunca se confia el total que manda el cliente
  (`apps/payments`).
- `POST /api/stripe/webhook/` — en `payment_intent.succeeded` marca la reserva
  `pagada` y corre `full_clean()` (motor de cupo). Si el cupo se lleno mientras el
  cliente pagaba, reembolsa automaticamente via `stripe.Refund` y la reserva se queda
  en `pendiente_pago`.

Llaves de Stripe (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`)
se leen de variables de entorno, vacias por defecto en local — `crear-pago` responde
503 si no estan configuradas (el frontend lo maneja mostrando `checkout.paymentUnavailable`).

## Cupo diario

Motor unico en `apps/bookings/models.py`: `validar_cupo_diario(fecha, excluir_pk=None)`,
llamado desde `Reserva.clean()`. Solo cuentan contra el cupo los estados en
`ESTADOS_QUE_OCUPAN_CUPO` (`pagada`, `asignada`, `completada`) — `pendiente_pago` no
bloquea a otros clientes. Override manual de cupo por dia: modelo `CupoDiario`
(sin registro para un dia -> aplica `CUPO_MAXIMO_DEFAULT = 10`). Cualquier flujo nuevo
que cree/edite una `Reserva` (API de pago, panel vendedora) debe llamar
`instance.full_clean()` antes de `save()` para que este motor corra — no duplicar la
logica en otro lado.

## Cancelacion y reembolso

`Reserva` tiene `motivo_cancelacion`, `cancelada_por` (FK user), `cancelada_en`,
`reembolsada`. Accion de admin "Cancelar por mal clima (reembolso completo)" en
`ReservaAdmin` marca los 4 campos de una. Unica causa de cancelacion con reembolso es
mal clima (ver contexto-negocio.md) — no hay flujo de cancelacion sin reembolso todavia.
Auditoria de quien cambio que reserva: el boton "History" nativo del admin de Django
(no se agrego nada custom, ya viene con `django.contrib.admin`).

## Roles: Jefes vs Vendedora

- **Jefes** = cuentas Django con `is_superuser=True`. Ven/editan todo, sin restriccion
  (bypassa el sistema de permisos). No usan un Group.
- **Vendedora** = cuentas `is_staff=True`, `is_superuser=False`, agregadas al grupo
  Django `Vendedora`. Correr `python manage.py setup_roles` (idempotente) para
  crear/sincronizar los permisos del grupo: `Reserva` (add/change/view, sin delete —
  se cancela, no se borra), `CupoDiario` (add/change/view), `Embarcacion`/`Capitan`
  (view only). **`fleet.Tarifa` deliberadamente sin permisos** — es la unica pieza
  financiera hoy, asi el modulo ni aparece en su admin. Cuando exista un dashboard
  financiero real (doc menciona uno para jefes), debe gatear con la misma logica
  (`request.user.is_superuser` o permiso explicito, nunca solo "es staff").
- Crear cuentas de vendedora: `createsuperuser` es solo para jefes. Para vendedora,
  crear un `User` normal (`is_staff=True`) desde el admin o shell y agregarlo al grupo
  `Vendedora`.

## Gotchas

- `bookings.Reserva.hora` valida ventana 5:00–7:00am (`validar_ventana_salida` en `models.py`).
- `embarcacion`/`capitan` en `Reserva` son nullable a proposito: quedan vacios hasta que la
  vendedora asigna manualmente.
