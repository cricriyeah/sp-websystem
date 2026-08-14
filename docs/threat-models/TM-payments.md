# Modelo de amenazas — Cobro y reservas

Fecha: 2026-08-13 · Alcance: `apps/payments`, `apps/bookings` (API pública), checkout web
Origen: hallazgo F-11 de `docs/audit/AUDIT-2026-08-12.md`

Este documento describe qué se protege en el flujo de pago, dónde están las
fronteras de confianza, qué ataque es plausible en cada una y qué control lo
detiene hoy. Buena parte de las reglas ya estaban implementadas y documentadas en
`backend/CLAUDE.md`; lo que faltaba era ponerlas en un formato donde se pueda
revisar si alguna se rompe.

Lo que **no** es: un checklist de certificación. `PROJECT.md` declara PCI-DSS en
alcance y el sistema califica para SAQ-A, no porque exista este documento sino
por cómo está construida la integración (ver "Alcance PCI-DSS").

## Activos que se protegen

| Activo | Dónde vive | Por qué importa |
|---|---|---|
| Dinero cobrado | Stripe | Un descuadre es dinero real de un cliente real |
| Cupo del día | `bookings.Reserva` + `CupoDiario` | Vender más lugares de los que hay = alguien se queda en el muelle |
| Constancia del deslinde | `Reserva.deslinde_*` | Es la evidencia legal si hay un accidente en el mar |
| PII del cliente | `Reserva`: nombre, teléfono, correo, IP | Obligación legal y confianza |
| Datos de tarjeta | **En ningún lado nuestro** | Ver "Alcance PCI-DSS" |

## Fronteras de confianza

```
[Navegador del cliente]
   │
   ├──(A)──> API pública Django          sin autenticación, AllowAny
   │
   └──(B)──> Stripe Elements (iframe)    el PAN nunca toca nuestro servidor
                  │
                  ▼
             [Stripe]
                  │
                  └──(C)──> Webhook Django           autenticado por firma
                                 │
                                 ├──(D)──> Postgres (Supabase)
                                 │
                                 └──(E)──> Resend / WhatsApp

[Jefes / vendedora] ──(F)──> Django admin            sesión autenticada
```

Todo lo que entra por A y C es **hostil hasta que se demuestre lo contrario**.
A no tiene login por diseño de negocio: el cliente reserva sin crear cuenta.

---

## (A) Navegador → API pública

Rutas: `POST /api/reservas/`, `POST /api/reservas/<id>/crear-pago/`,
`GET /api/cupo/`, `GET /api/tarifa/`.

### A-1 · Generar cobros sobre la reserva de otra persona
Los ids de reserva son consecutivos y la API es pública: adivinar `id=47` es
trivial.
**Control:** `checkout_id` (UUID v4 que genera el navegador y solo conoce quien
abrió ese checkout) se compara antes de cualquier operación —
`apps/payments/views.py:47`, 403 si no coincide. El upsert de reserva filtra por
`checkout_id` además del estado (`apps/bookings/views.py`).

### A-2 · Manipular el total a pagar
**Control:** el cliente nunca manda cifras. Manda qué amenidades quiere y si paga
completo o anticipo; el monto se arma en el servidor desde `Reserva` + `Tarifa`
en `apps/payments/pricing.py`, con `Decimal` y cuantización explícita a centavos.
El frontend tampoco tiene precios: los pide a `GET /api/tarifa/` (no hay ninguna
cifra hardcodeada, ver `frontend/CLAUDE.md`).

### A-3 · Abuso por volumen
Sin login nada impedía pegarle en bucle: reservas basura que ensucian el panel de
la vendedora, o PaymentIntents en masa contra la cuenta de Stripe.
**Control:** `ScopedRateThrottle` por IP — 20/min en reservas y pagos, 60/min en
consultas (`config/settings/base.py`, configurable por variable de entorno).
**Limitación conocida:** el contador vive en el caché local del proceso. Con
`gunicorn --workers 3` el límite efectivo es ~3× el configurado. Aceptable al
volumen actual; si hace falta exactitud, mover el caché a Redis.

### A-4 · Falsificar la IP de la constancia del deslinde
`X-Forwarded-For` es una lista donde cada salto agrega al final, y el cliente
puede escribir la parte izquierda antes de tocar nuestro proxy. Tomar la primera
entrada dejaba la evidencia legal a merced justo de quien la firma.
**Control:** se cuenta desde la derecha tantos saltos como proxies de confianza
haya (`TRUSTED_PROXY_COUNT`: 1 en Render, 0 en local) —
`apps/bookings/serializers.py`. Si el header viene más corto de lo esperado no se
adivina: cae a `REMOTE_ADDR`. Cubierto por `IpDelDeslindeTests`.

### A-5 · Modificar una reserva ya pagada
Cambiar fecha o número de personas después de pagar alteraría cupo, cobro y
asignación.
**Control:** `ReservaCheckoutSerializer.validate` rechaza cualquier reserva cuyo
estado ya no sea `pendiente_pago`.

### A-6 · Reservar sin aceptar el deslinde
**Control:** `Reserva.clean()` exige `deslinde_aceptado` para toda reserva con
`canal_origen='web'`. Vive en el modelo y no en la vista, así que aplica igual
desde la API, el admin y el shell. Los 4 campos del deslinde son readonly en el
admin: son constancia, no datos editables.

### A-7 · Ocupar cupo sin pagar
**Control:** `pendiente_pago` **no** cuenta contra el cupo
(`ESTADOS_QUE_OCUPAN_CUPO`). Un checkout abandonado no le bloquea el día a nadie.
La validación definitiva de cupo corre al confirmar el pago, no al reservar.

---

## (B) Navegador → Stripe · datos de tarjeta

El número de tarjeta se captura en un iframe servido por `js.stripe.com`
(`@stripe/react-stripe-js`, `PaymentElement`) y viaja del navegador a Stripe sin
pasar por nuestro backend ni por nuestro dominio.

**Control adicional (nuevo):** el CSP de `frontend/next.config.ts` limita
`script-src` y `frame-src` a `js.stripe.com` / `hooks.stripe.com`, y pone
`frame-ancestors 'none'` para que nadie pueda montar el checkout dentro de un
iframe ajeno (clickjacking sobre un formulario de pago).

**Lo que rompería esto** — y con ello el alcance SAQ-A:
- Capturar campos de tarjeta propios en vez de usar Elements.
- Pasar datos de tarjeta por nuestro backend hacia Stripe.
- Aflojar `script-src` a un origen arbitrario: un script inyectado podría leer
  el formulario antes de que Stripe lo aísle.

---

## (C) Stripe → webhook

Ruta: `POST /api/stripe/webhook/`. Es la **única fuente de verdad del cobro**:
nada se marca pagado desde el navegador, porque el navegador puede cerrarse a
media confirmación.

### C-1 · Webhook falsificado
Cualquiera puede hacer POST a esa URL diciendo "esta reserva ya pagó".
**Control:** `stripe.Webhook.construct_event` valida la firma contra
`STRIPE_WEBHOOK_SECRET`; firma inválida = 400 y no se procesa nada
(`apps/payments/views.py`). Es el único caso en que el webhook no responde 200.

### C-2 · Reproceso del mismo evento (replay)
Stripe reintenta las entregas.
**Control:** `_resolver_cobro_repetido` compara el intent del evento contra el ya
registrado en la reserva; si es el mismo, se ignora (`YA_APLICADO`).

### C-3 · Dos entregas simultáneas del mismo evento
Sin serialización las dos verían la reserva en `pendiente_pago` y las dos la
marcarían pagada.
**Control:** `aplicar_pago_exitoso` corre en `transaction.atomic` con
`select_for_update` sobre la reserva.

### C-4 · Cobro duplicado con otro PaymentIntent
Al cliente le cobraron dos veces.
**Control:** se detecta (intent distinto sobre reserva ya pagada) y se reembolsa
el segundo automáticamente, con log de nivel `error`.

### C-5 · Pago sin reserva asociada
`metadata.reserva_id` no resuelve.
**Control:** se reembolsa. Nunca se deja dinero cobrado sin contrapartida.

### C-6 · El día se llenó mientras el cliente pagaba
**Control:** `full_clean()` corre el motor de cupo dentro de la transacción; si
falla, `_cancelar_sin_cupo` reembolsa el 100% y deja la reserva `cancelada` +
`reembolsada` con el motivo real, para que la vendedora lo vea en su panel en vez
de que la reserva desaparezca.

### C-7 · Reembolso duplicado
**Control:** `idempotency_key=f'refund-{intent_id}'` en `stripe.Refund.create`.
Si el reembolso falla, la reserva **no** se marca `reembolsada` — el estado nunca
miente sobre dónde está el dinero.

### C-8 · Entrega del webhook perdida para siempre
Backend caído, secret mal puesto, o Stripe se rinde tras sus reintentos. Resultado:
un cliente que pagó y no tiene reserva.
**Control:** `manage.py conciliar_pagos` le pregunta a Stripe cómo quedó cada pago
pendiente y aplica exactamente lo mismo que el webhook (misma función, dos
entradas). Programado cada hora en `render.yaml`. Es idempotente.

### C-9 · Excepción no controlada devuelve 500
Stripe reintentaría en bucle un evento que no se va a arreglar solo.
**Control:** el webhook captura toda excepción, la registra y responde 200.

---

## (D) Django → Postgres

PII almacenada: `nombre_cliente`, `telefono_cliente`, `correo_cliente`,
`deslinde_ip`, `deslinde_nombre`. **Ningún dato de tarjeta.**

Credenciales por variable de entorno, sin defaults (`production.py` falla
explícito si falta alguna). Conexión gestionada por Supabase sobre TLS.
`db.sqlite3` está fuera de git desde el 2026-08-12 (hallazgo F-03).

Ver `docs/vendors/supabase.md` para retención, respaldos y notificación de brecha.

---

## (F) Admin

Sesión autenticada de Django. Dos roles (`docs/contexto-negocio.md`):

- **Jefes** = `is_superuser`. Ven todo, incluido el panel de finanzas y la Tarifa.
- **Vendedora** = `is_staff` + grupo `Vendedora`. Sin permiso sobre `fleet.Tarifa`
  (el módulo ni aparece), sin acceso a `/admin/finanzas/` (la vista corta con
  `is_superuser`, nunca con "es staff"), sin permiso de borrado sobre `Reserva`
  (se cancela, no se borra).

Auditoría de cambios: el historial nativo del admin de Django.

**Pendiente conocido (F-14):** el admin está en la ruta `/admin/` por defecto.
Con la autenticación actual el riesgo es bajo; cambiar la ruta solo reduciría el
ruido de bots.

---

## Alcance PCI-DSS

El sistema califica para **SAQ-A**: el número de tarjeta nunca es transmitido,
procesado ni almacenado por nuestros sistemas. Se captura dentro de un iframe de
Stripe y va directo a Stripe, que es **PCI DSS Level 1 service provider**
certificado anualmente por un QSA independiente.

Nuestra obligación bajo SAQ-A se reduce a: no tocar datos de tarjeta, servir el
checkout sobre HTTPS, mantener la integridad de la página que carga Elements
(de ahí el CSP), y gestionar bien las llaves de API.

Cualquiera de los cambios listados en (B) sacaría al sistema de SAQ-A y lo movería
a SAQ-D, que es un régimen de cumplimiento sustancialmente más caro.

---

## Riesgos aceptados

Decisiones deliberadas, no descuidos. Cambiarlas requiere una razón de negocio,
no solo una preferencia técnica.

**`_verificar_monto` registra el descuadre pero no rechaza el pago.**
Rechazarlo dejaría a un cliente que ya le pagó a Stripe sin viaje y sin dinero
hasta que alguien procese el reembolso. Se registra en el log y queda visible en
el admin (columna "Cobro", en rojo) para revisión humana.

**La doble asignación de panga/capitán no se valida.**
La vendedora puede querer escalonar dos salidas con la misma embarcación. Es
criterio suyo, no del sistema.

**Una disputa no cambia el estado de la reserva.**
`en_disputa` es una bandera visible en el panel; qué hacer con un viaje en
contracargo lo decide una persona.

**El throttle no es exacto entre workers.** Ver A-3.

**La comisión de la vendedora se calcula y se paga fuera del sistema.** Aquí solo
se registra a quién le corresponde cada venta; no hay porcentajes ni saldos que
puedan descuadrarse.

---

## Huecos abiertos

| Id | Hueco | Consecuencia | Estado |
|---|---|---|---|
| F-06 | Sin servicio de alertas de error | Un webhook fallando en silencio solo se descubre por reclamo del cliente o corriendo `conciliar_pagos --dry-run` a mano. `LOGGING` ya manda todo al log de Render, pero nadie recibe aviso. | Abierto — requiere cuenta de Sentry |
| F-08 | `checkout-view.tsx` sin pruebas | 522 líneas manejando la máquina de estados de Stripe Elements, sin red de seguridad ante un cambio | Abierto |
| — | Comportamiento real de `X-Forwarded-Proto`/`X-Forwarded-For` en Render sin verificar | A-4 y el fix de F-01 se apoyan en documentación ambigua del proveedor | Verificar con `curl` contra producción en el primer deploy |

## Revisión

Este documento se revisa cuando cambie cualquiera de estos archivos:
`apps/payments/services.py`, `apps/payments/views.py`, `apps/payments/pricing.py`,
`apps/bookings/serializers.py`, `frontend/src/components/checkout-view.tsx`.
