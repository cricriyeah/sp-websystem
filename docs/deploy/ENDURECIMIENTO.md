# Endurecimiento de seguridad — pasos que solo se hacen a mano

Origen: revisión del 20 de agosto de 2026 contra una lista de diez controles.
Cinco ya estaban (HTTPS forzado, contraseñas hasheadas, CSRF, logs sin secretos,
respaldos), uno no aplica (no existe flujo de recuperación de contraseña) y
cuatro faltaban.

Dos de los cuatro se resolvieron en código y ya están en el repo:

- **Sesiones del backoffice** — `SESSION_COOKIE_AGE` a 10 horas y
  `SESSION_SAVE_EVERY_REQUEST` en `config/settings/base.py`. Antes usaban el
  default de Django, dos semanas.
- **Gate anti-bot del checkout** — Cloudflare Turnstile sobre
  `POST /api/reservas/`, ver `backend/apps/bookings/captcha.py`. Se apaga solo
  si su variable no está, igual que Stripe y Resend.

Los dos que quedan son clics en dashboards de terceros. Nadie los puede hacer
desde el repo.

---

## 1. Llaves de Turnstile (termina de encender lo que ya está en código)

El código está puesto pero **inerte** hasta que existan las llaves: sin
`TURNSTILE_SECRET_KEY` la verificación devuelve `True` sin preguntar nada, y el
checkout acepta todo como antes. No es un fallo, es el mismo apagado que usan
Stripe y Resend para que local y CI no necesiten llaves — pero en producción
significa que el gate no está haciendo nada.

1. En https://dash.cloudflare.com → Turnstile → **Add widget**.
2. Dominio: el del sitio en Vercel. Modo: **Managed**.
3. Salen dos llaves, y son un par. Tienen que venir del mismo widget:
   - **Site key** (pública) → Vercel, variable `NEXT_PUBLIC_TURNSTILE_SITE_KEY`.
     Requiere redeploy del frontend para tomar efecto.
   - **Secret key** (privada) → Render, env group `pescadeportiva-secrets`,
     variable `TURNSTILE_SECRET_KEY`. Ya está declarada en `render.yaml` como
     `sync: false`.

**Verificación:** abrir el checkout y crear una reserva. Debe funcionar igual que
siempre — el widget no le pide nada al cliente en el caso normal. Para probar
que el gate sí está activo, mandar un `POST` a `/api/reservas/` sin
`captcha_token` con un `checkout_id` nuevo: debe contestar **403** con la clave
`captcha`. Si contesta 201, la variable no llegó al servicio.

---

## 2. Avisos de los proveedores

Revisado contra la documentación de cada proveedor el 20 de agosto de 2026. La
primera versión de este documento daba rutas que no existen; esto es lo que sí
hay. Resulta ser bastante menos trabajo del que parecía: casi todo viene
encendido de fábrica.

### Stripe

**No existe una alerta por "muchos pagos fallidos".** Stripe no ofrece ese
disparador. Lo que hay es notificación por correo de eventos de la cuenta:

`dashboard.stripe.com/settings/communication-preferences`

Encender ahí:
- **"Un pago es marcado como riesgo elevado"** (por Stripe o por una regla de
  Radar). Es lo más cercano a un aviso de card testing.
- **"Un pago es disputado por el tarjetahabiente"**.

Además, **Radar bloquea card testing por defecto en todas las cuentas**, sin
configurar nada. La protección ya está puesta; lo que falta es enterarse.

Si más adelante se quiere un aviso específico, se arma con una **regla de
revisión** de Radar (`dashboard.stripe.com/radar/rules`): los pagos que la
cumplan caen en la cola de revisión y, con la notificación de riesgo elevado
encendida, llega el correo.

### Render

**No hay alerta ni tope de gasto general.** Los tres servicios están en plan
`starter`, que es de precio fijo — no hay factura que se dispare sola.

Lo único con tope configurable son los **minutos de build**:
Workspace Settings → sección Build Pipeline → **Set spend limit**.

Y Render **ya manda correo solo** al acercarse y al pasarse de los límites de uso
incluido (ancho de banda, etc.). No hay que activarlo.

Lo que sí conviene prender, y vale más que un aviso de gasto: **notificaciones de
fallo por servicio** (Settings del servicio → sección Notifications, o el default
del workspace). Importa sobre todo en los dos cron: `conciliar_pagos` es la red
que atrapa a un cliente que pagó y se quedó sin reserva, y hoy si falla no avisa
a nadie más que a Sentry.

### Supabase

El **Spend Cap viene encendido por defecto en el plan Pro**. No hay que
activarlo, solo confirmar que sigue puesto:
Organization → Billing → sección **Cost Control**.

Ojo con su límite: las **Compute Hours no están cubiertas** por el cap.

### Resend y WhatsApp

Resend: aviso de cuota del plan. WhatsApp Business: las conversaciones se
facturan por plantilla enviada, revisar el límite en Meta Business. Ninguno de
los dos es urgente mientras el volumen sea el de hoy.

---

## 3. Rol de base de datos con privilegios limitados

**Estado: sin verificar.** `DB_USER` es una variable de entorno y su valor no
está en el repo. La cadena de conexión que Supabase entrega por defecto usa el
rol `postgres`, que es el superusuario del proyecto — así que lo más probable es
que la app esté entrando con la llave maestra.

### Cuidado antes de cambiarlo

El build de Render corre `python manage.py migrate` en cada deploy, y eso
necesita DDL (`CREATE TABLE`, `ALTER TABLE`). **Un rol de solo lectura, o de solo
`SELECT/INSERT/UPDATE/DELETE`, rompe el deploy.** Lo que se busca no es un rol
sin permisos, es un rol que sea dueño del esquema de la aplicación pero **no**
superusuario del servidor: sin acceso a otras bases, sin lectura de archivos del
servidor, sin `COPY FROM PROGRAM`.

### Procedimiento

Correrlo en el SQL Editor de Supabase, conectado como el usuario actual:

```sql
-- 1. Rol propio de la aplicación. Contraseña larga y aleatoria, generada aparte.
CREATE ROLE app_pescadeportiva LOGIN PASSWORD 'PEGAR_AQUI_UNA_LARGA_Y_ALEATORIA';

-- 2. Dueño del esquema donde viven las tablas de Django, para que migrate pueda
--    crear y alterar. No se le da superusuario ni CREATEROLE ni CREATEDB.
GRANT ALL ON SCHEMA public TO app_pescadeportiva;
GRANT ALL ON ALL TABLES IN SCHEMA public TO app_pescadeportiva;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO app_pescadeportiva;

-- 3. Que lo mismo aplique a las tablas que migrate cree en el futuro.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES TO app_pescadeportiva;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON SEQUENCES TO app_pescadeportiva;
```

Después, en Render → env group `pescadeportiva-secrets`, cambiar `DB_USER` y
`DB_PASSWORD` por los del rol nuevo y redesplegar.

### Verificación, en este orden

1. **Que el deploy sobreviva un `migrate`.** Es el paso que falla si los
   permisos quedaron cortos. Comprobarlo antes de dar el cambio por bueno.
2. **Que ya no sea superusuario**, conectado con el rol nuevo:
   ```sql
   SELECT current_user, usesuper FROM pg_user WHERE usename = current_user;
   ```
   `usesuper` debe salir en `false`.

### Si algo sale mal

Volver `DB_USER` y `DB_PASSWORD` a los valores anteriores en Render y
redesplegar. Por eso conviene **no borrar el usuario viejo** hasta que el nuevo
lleve un par de deploys sanos.

---

## 4. Dos ajustes menores pendientes

- **Subir el HSTS a un año.** `SECURE_HSTS_SECONDS` está en `3600` (una hora),
  puesto bajo a propósito mientras el dominio se movía. Ya lleva tiempo sirviendo
  HTTPS estable: cambiar la variable en Render a `31536000`. Ojo, el navegador
  **recuerda** este valor y no hay forma de retirarlo antes de que expire, así
  que se sube cuando el dominio ya es definitivo.
- **Confirmar que Supabase esté en plan Pro y no en Free.** El Free no garantiza
  respaldos. La decisión de no usar Free está escrita en
  `docs/vendors/supabase.md`, pero eso fue una decisión, no un cobro verificado.

---

## Lo que sigue sin cubrir a propósito

- **`sslmode` no está explícito** en `DATABASES`. Supabase acepta TLS pero
  `psycopg` no lo exige por su cuenta. Añadir `'OPTIONS': {'sslmode': 'require'}`
  en `config/settings/production.py` es un cambio de una línea; se dejó fuera de
  esta tanda para no mezclarlo con el cambio de rol, que toca la misma conexión.
- **Rotación de credenciales de base**: sigue sin cadencia definida, ver
  `docs/vendors/supabase.md`.
