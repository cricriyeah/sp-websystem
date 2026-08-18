# Puesta en producción — guion de primer arranque

Origen: hallazgos F-18, F-22 y F-23 de `docs/audit/AUDIT-2026-08-14.md`.

Este documento es para seguirse **en orden**, con el sistema enfrente. No es una
referencia para leer de corrido: cada paso deja el sistema en un estado
verificable, y el siguiente asume que el anterior pasó.

La regla que gobierna todo lo de abajo: **ninguna llave se escribe en el repo, ni
se pega en un chat, ni se manda por mensaje.** Se capturan una sola vez en el
dashboard del proveedor. Si alguna llega a aparecer en un log, un screenshot o
una conversación, la respuesta correcta es rotarla, no borrar el mensaje.

---

## Fase 0 — Antes de tocar nada

- [ ] Confirmar el plan de Supabase (**no** el gratuito, ver
      `docs/vendors/supabase.md`). Anotar si se activó PITR o si sigue vigente el
      riesgo aceptado de perder hasta 24 horas.
- [ ] Tener a la mano el dominio que va a usar el sitio y el que va a usar la API.
- [ ] Verificar que el CI está en verde en `main`. Si está en rojo, no se
      despliega: el CI corre los mismos 146 tests contra Postgres, que es el
      motor de producción.

---

## Fase 1 — Base de datos (Supabase)

1. Crear el proyecto de Supabase en la región más cercana a los clientes.
2. De la cadena de conexión salen cinco valores. Se capturan en Render en la
   Fase 2; **no se escriben aquí ni en ningún archivo del repo**:
   `DB_NAME` · `DB_USER` · `DB_PASSWORD` · `DB_HOST` · `DB_PORT`

No hay nada que crear a mano dentro de la base todavía. Las tablas las crea
`migrate` en el primer deploy.

---

## Fase 2 — Variables de entorno en Render

`render.yaml` ya declara todas y las marca `sync: false`, que significa "este
valor se captura en el dashboard, nunca en el repo". Se cargan en el
**environment group** `pescadeportiva-secrets`, salvo las tres que son propias
del servicio web.

### Obligatorias — sin ellas el proceso no arranca

Estas se leen con `os.environ[...]`, sin valor por defecto. Si falta una, el
servicio muere al arrancar con `KeyError` y el deploy no llega a estar vivo.

| Variable | De dónde sale |
|---|---|
| `DJANGO_SECRET_KEY` | Generar una cadena larga y aleatoria. No reutilizar la de desarrollo |
| `DB_NAME` `DB_USER` `DB_PASSWORD` `DB_HOST` | Supabase, Fase 1 |

### Obligatorias en la práctica — el proceso arranca pero el sitio no sirve

Tienen valor por defecto, así que **no fallan de forma ruidosa**. Son las dos que
más tiempo hacen perder:

| Variable | Qué pasa si falta |
|---|---|
| `DJANGO_ALLOWED_HOSTS` | Con `DEBUG=False` y la lista vacía, Django responde **400 a todas las peticiones**, incluida la sonda de salud. El deploy se cancela con un error que no menciona esta variable. Va el dominio de la API, separado por comas si hay varios |
| `CORS_ALLOWED_ORIGINS` | El backend responde bien si lo pruebas con `curl`, pero **el navegador bloquea toda llamada desde el frontend**. El checkout aparece roto sin ningún error en los logs del backend. Va la URL del frontend, con `https://` y sin barra final |

### Opcionales — cada una apaga su función, sin romper el resto

| Variable | Si falta |
|---|---|
| `STRIPE_SECRET_KEY` | `crear-pago` responde 503 y el checkout muestra "pago no disponible". El resto del sitio funciona |
| `STRIPE_PUBLISHABLE_KEY` | El formulario de tarjeta no monta |
| `STRIPE_WEBHOOK_SECRET` | Los webhooks se rechazan con 400. **El dinero entra y ninguna reserva se marca pagada** — el caso más caro de esta tabla |
| `RESEND_API_KEY` `RESEND_FROM` | No se manda correo de confirmación. El cobro sigue funcionando |
| `RESEND_BCC` | El negocio no recibe copia. Ver `docs/vendors/supabase.md`: es el rastro fuera de la base |
| `WHATSAPP_TOKEN` `WHATSAPP_PHONE_NUMBER_ID` | No se manda WhatsApp. El cobro sigue funcionando |
| `SENTRY_DSN` | No llega aviso de ningún error. Todo sigue funcionando, pero un webhook que empieza a fallar se descubre por reclamo del cliente. Va en el **grupo**, no en el servicio web: los cron también la necesitan, y `conciliar_pagos` sin vigilancia es el punto ciego más caro |

### Con valor por defecto — solo tocar si hace falta

| Variable | Default | Nota |
|---|---|---|
| `DB_PORT` | `5432` | |
| `TRUSTED_PROXY_COUNT` | `1` en producción | Un salto: el balanceador de Render. Subirlo solo si de verdad se mete un CDN delante — cada salto de más es una posición de `X-Forwarded-For` que el cliente puede escribir a mano |
| `SECURE_HSTS_SECONDS` | `3600` | Subir a `31536000` tras un par de días con HTTPS estable. El navegador **recuerda** este valor y no se puede retirar antes de que expire |
| `THROTTLE_RESERVAS` `THROTTLE_PAGOS` | `20/min` | Por IP |
| `THROTTLE_CONSULTA` | `60/min` | Por IP |
| `WHATSAPP_TEMPLATE` | `reserva_confirmada` | La plantilla debe estar aprobada por Meta y recibir 4 parámetros |
| `WHATSAPP_TEMPLATE_LANG` | `es_MX` | |

**Verificación de esta fase:** las cinco obligatorias están cubiertas por
`render.yaml`. Para reconfirmarlo tras cualquier cambio en settings:

```bash
python - <<'PY'
import re, pathlib
codigo = "".join(pathlib.Path(f).read_text() for f in
    ('backend/config/settings/base.py', 'backend/config/settings/production.py'))
obligatorias = set(re.findall(r"os\.environ\['([A-Z_]+)'\]", codigo))
provistas = set(re.findall(r'- key: ([A-Z_]+)', pathlib.Path('render.yaml').read_text()))
faltan = obligatorias - provistas
print("FALTAN EN render.yaml:", faltan or "ninguna")
PY
```

---

## Fase 3 — Primer deploy

El `buildCommand` de `render.yaml` corre `collectstatic` y `migrate`. El
`startCommand` levanta gunicorn con 3 workers.

- [ ] Crear el Blueprint en Render apuntando a este repo.
- [ ] Confirmar que el health check apunta a `/healthz` y **no** a `/api/tarifa/`.
      Esa ruta responde 503 mientras no exista la fila de `Tarifa`, y como en una
      base recién migrada no existe, el deploy se cancelaría solo (F-17).

**Verificación:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://TU-API.onrender.com/healthz
```

`200` = el proceso vive y la base contesta. `503` = la base no es alcanzable,
revisar las credenciales de la Fase 2.

---

## Fase 4 — Datos que deben existir antes de vender

Una base recién migrada está vacía. Sin estos pasos el sitio está arriba pero no
se puede operar. Se corren desde la Shell de Render, en el servicio web:

- [ ] **Superusuario** — sin esto no hay forma de entrar al backoffice.
  ```bash
  python manage.py createsuperuser
  ```

- [ ] **Roles** — crea el grupo `Vendedora` con sus permisos. Es idempotente.
  ```bash
  python manage.py setup_roles
  ```

- [ ] **Tarifa** — es un singleton y **el sitio no vende sin ella**:
      `/api/tarifa/` responde 503 y el checkout arranca en estado "no
      disponible". Se crea desde el admin, en *Dinero → Tarifa*. Hacen falta:
      precio del tour en MXN, y opcionalmente en USD (sin `precio_usd` la web
      solo ofrece pesos), precio por persona extra y precio del lunch en cada
      moneda que se vaya a ofrecer.

- [ ] **Vendedoras** (si aplica) — crear el `User` con `is_staff=True`, agregarlo
      al grupo `Vendedora`, y darle de alta su fila en *Catálogo → Vendedoras*
      con su código de link. Ver `backend/CLAUDE.md`, sección "Registro de ventas".

- [ ] **Cupo diario** — opcional. Sin registro, aplica el default de 10 viajes.

**Verificación:**

```bash
curl -s https://TU-API.onrender.com/api/tarifa/
```

Debe devolver los precios, no un 503.

---

## Fase 5 — Stripe, primero en modo prueba

**No empezar con llaves `sk_live_`.** El sistema no distingue entre modo prueba y
modo real: son las mismas variables. Eso permite ejercitar el flujo completo
contra la base de producción real sin mover un peso.

1. [ ] Capturar en Render las llaves de **prueba** (`sk_test_...`, `pk_test_...`)
       desde https://dashboard.stripe.com/test/apikeys
2. [ ] Registrar el endpoint del webhook en el dashboard de Stripe (modo prueba):
       ```
       https://TU-API.onrender.com/api/stripe/webhook/
       ```
       Eventos que hay que suscribir — los cuatro, no solo el primero:
       - `payment_intent.succeeded`
       - `charge.refunded`
       - `charge.dispute.created`
       - `charge.dispute.closed` y `charge.dispute.funds_reinstated`
3. [ ] Copiar el *signing secret* que Stripe genera al crear el endpoint
       (`whsec_...`) a `STRIPE_WEBHOOK_SECRET` en Render, y redesplegar.

### Pruebas a correr, en este orden

Con [tarjetas de prueba de Stripe](https://docs.stripe.com/testing):

- [ ] **Reserva y cobro completo** (`4242 4242 4242 4242`). Verificar en el admin
      que la reserva quedó `pagada`, con `monto_pagado` y `pagada_en`.
- [ ] **Anticipo del 30%** — verificar que `saldo_pendiente` cuadra.
- [ ] **Correo de confirmación** — que llegue al cliente y que la copia llegue a
      `RESEND_BCC`.
- [ ] **Pago rechazado** (`4000 0000 0000 0002`) — la reserva debe quedarse en
      `pendiente_pago`, no cancelarse.
- [ ] **Doble clic en pagar** — no debe generar dos cobros. La `idempotency_key`
      lo cubre, pero conviene verlo.
- [ ] **Reembolso desde el panel de Stripe** — la reserva debe quedar marcada
      `reembolsada` sola, vía el webhook `charge.refunded`.
- [ ] **Día lleno** — cerrar un día con un `CupoDiario` de 0 e intentar pagarlo.
      Debe reembolsarse solo y quedar cancelada con el motivo real.
- [ ] **Conciliación** — `python manage.py conciliar_pagos --dry-run` no debe
      reportar nada pendiente después de las pruebas anteriores.

---

## Fase 6 — Frontend (Vercel)

Las tres variables van en el proyecto de Vercel. Ver `frontend/.env.example`.

| Variable | Valor en producción |
|---|---|
| `NEXT_PUBLIC_API_URL` | La URL del servicio de Render |
| `NEXT_PUBLIC_SITE_URL` | El dominio real del sitio |
| `NEXT_PUBLIC_WHATSAPP_NUMBER` | El número real del negocio, solo dígitos con lada |

**Lo que hay que tener presente:** las variables `NEXT_PUBLIC_*` **se graban en el
build**, no se leen al arrancar. Cambiar una en Vercel no surte efecto hasta
volver a desplegar. Si después de corregir la URL el sitio sigue apuntando al
backend viejo, falta el redeploy — no es un caché del navegador.

Segunda consecuencia: `NEXT_PUBLIC_API_URL` queda dentro del CSP que sirve el
frontend (`frontend/next.config.ts` la mete en `connect-src`). Un cambio de
dominio de la API sin redeploy deja al navegador bloqueando las llamadas.

- [ ] Confirmar que `CORS_ALLOWED_ORIGINS` en Render tiene exactamente este
      dominio. Es el otro extremo del mismo cable.

**Verificación:** abrir el checkout en el navegador con la consola abierta y
llegar hasta el formulario de tarjeta. Cero errores de CORS y cero de CSP.

---

## Fase 7 — Paso a dinero real

Solo cuando toda la Fase 5 pasó.

- [ ] Cambiar en Render a las llaves `sk_live_...` / `pk_live_...`
- [ ] **Registrar otra vez el endpoint del webhook, ahora en modo real.** Es un
      endpoint distinto con un *signing secret* distinto. Actualizar
      `STRIPE_WEBHOOK_SECRET` con el nuevo valor — el de prueba no sirve aquí, y
      el síntoma es que el dinero entra y ninguna reserva se marca pagada.
- [ ] Redesplegar.
- [ ] Hacer **una** reserva real de monto bajo, con tarjeta propia, y reembolsarla
      desde el panel de Stripe. Confirma la cadena completa con dinero de verdad.
- [ ] Completar el SAQ-A en el dashboard de Stripe (lo dan prellenado para
      integraciones vía Elements). Ver `docs/vendors/stripe.md`.
- [ ] Subir `SECURE_HSTS_SECONDS` a `31536000` tras un par de días estables.

---

## Verificaciones que no exponen ningún secreto

Todas se pueden correr y reportar sin revelar un valor:

| Comprobación | Cómo | Qué confirma |
|---|---|---|
| Proceso y base | `curl .../healthz` → 200 | Credenciales de base correctas |
| Datos de negocio | `curl .../api/tarifa/` → 200 | Tarifa creada |
| Stripe configurado | Crear reserva y pedir pago; 503 = falta la llave | `STRIPE_SECRET_KEY` presente |
| Webhook alcanzable | "Send test webhook" desde el dashboard de Stripe | Ruta y `STRIPE_WEBHOOK_SECRET` correctos |
| CORS | Abrir el checkout con la consola del navegador | `CORS_ALLOWED_ORIGINS` correcto |
| Cobros sin aplicar | `conciliar_pagos --dry-run` | Ningún pago quedó sin reserva |

---

## Si algo sale mal

- **El deploy se cancela sin explicación clara** → casi siempre es el health
  check. Revisar `DJANGO_ALLOWED_HOSTS` (400 a todo) o las credenciales de base
  (503 en `/healthz`).
- **El sitio carga pero el checkout no** → CORS o CSP. Los dos se ven en la
  consola del navegador, no en los logs del backend.
- **Entró dinero y no hay reserva** → `STRIPE_WEBHOOK_SECRET` equivocado, o el
  endpoint registrado en el modo que no es. `conciliar_pagos` recupera esos
  pagos: para eso existe, y corre cada hora por cron.
- **Volver atrás** → Render permite redesplegar un commit anterior desde el
  dashboard. Ojo: eso **no** revierte las migraciones. Ninguna migración de este
  proyecto borra datos, pero conviene tener el respaldo del día a mano.

---

## Lo que sigue abierto al momento de escribir esto

- **F-06 — cerrado.** Hay alertas de error vía Sentry (`SENTRY_DSN`), disponibles
  para la web y para los dos cron. Siguen sin llegar a ningún lado si la variable
  no se captura: la función se enciende sola cuando existe, y su ausencia no
  rompe el arranque ni deja rastro de que falta.
- **F-21 — cerrado.** `STRIPE_API_VERSION` fijada explícitamente en settings, así
  que actualizar la librería ya no mueve la versión de la API en silencio.
- **Llaves cruzadas.** Un `whsec_` capturado dentro de `STRIPE_SECRET_KEY` tumbó
  el checkout completo en producción, y el síntoma (502 y un error genérico en la
  web) no apuntaba a la causa por ningún lado. Ahora hay un check de arranque que
  lo convierte en un deploy que no sale (`backend/apps/payments/checks.py`). Lo
  que ese check **no** puede decir es si la llave es válida, solo si tiene la
  forma que le toca: una `sk_test_` de otra cuenta pasa igual.
- **Respaldos** — decisión registrada en `docs/vendors/supabase.md`: sin PITR,
  ventana de pérdida de hasta 24 horas. Mientras siga así, **tomar un respaldo
  manual antes de correr cualquier migración**.
