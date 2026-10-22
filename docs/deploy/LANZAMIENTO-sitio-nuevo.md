# Lanzamiento del sitio nuevo sobre producción (salysoltours.com)

Situación al escribir esto (2026-10-21): producción (`pescadeportiva-api` en Render, el sitio en
`https://www.salysoltours.com` y su Postgres en Supabase) corre `main` tal como quedó el 2026-08-30. **Nunca se
usó: no hay clientes, cuentas ni dinero reales.** Por eso este lanzamiento no migra nada: se **reemplaza** la
versión vieja por la nueva y se parte de una base limpia.

Dos hechos del repositorio que lo hacen simple:

- `main` (ebe44246) es **ancestro** de `feat/marca-sun-baja`: avanzar `main` es un *fast-forward*, sin conflictos y
  **sin push forzado**.
- La versión vieja no se pierde: queda en el historial y se marca con la etiqueta `old/main-2026-08-30`.

Orden obligatorio. El push a `main` dispara el deploy del backend (`render.yaml` corre `migrate` en el build), así que
**la base y las variables se preparan antes del push**, no después.

---

## A. Lo que prepara Claude (sin tocar producción)

- [ ] Suite completa del backend contra Postgres en el commit final (`config.settings.ci`, puerto 5434; Docker encendido).
- [ ] `npm run verificar` en verde.
- [x] `seed_catalogo_real --produccion`: aplica en la base real el catálogo (La Ventana con hotel, avistamiento, pesca con
      mosca, pangas y estudios, más lo de las otras empresas) sin DEBUG, sin llaves falsas y sin datos DEMO. Con pruebas.
- [ ] Rama limpia: nada de prototipos, logs ni archivos de trabajo en lo que se sube.
- [ ] `render.yaml` con las variables nuevas declaradas (`HORAS_MINIMAS_RESERVA`, `APARTADO_MINUTOS`).

## B. Lo que haces tú antes del push

1. **Respaldo** de la base actual (aunque no haya nada que importe): Supabase → Database → Backups.
2. **Base limpia.** Con el SQL editor de Supabase, como `postgres`, en este orden:

   ```sql
   DROP SCHEMA public CASCADE;
   CREATE SCHEMA public;
   GRANT USAGE, CREATE ON SCHEMA public TO <rol_app>;      -- el DB_USER de Render
   CREATE EXTENSION IF NOT EXISTS btree_gist;               -- la usa el hospedaje (restricción EXCLUDE)
   ```

   Con el esquema nuevo `<rol_app>` crea y es dueño de todas las tablas: no hace falta el `ALTER TABLE ... OWNER` del
   runbook de corte. Si Render entra por el pooler (Supavisor), `DB_USER` lleva el sufijo `<rol_app>.<project_ref>`.
3. **El rol no puede ser superusuario ni tener `BYPASSRLS`.** Si lo es, `migrate` falla con `tenancy.E001` y el deploy
   no sale (es la protección, no un error). Se comprueba con:
   `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;` → debe dar `(false, false)`.
4. **Variables en Render** (grupo `pescadeportiva-secrets` y servicio web):

   | Variable | Valor |
   |---|---|
   | `DJANGO_ALLOWED_HOSTS` | el dominio de la API |
   | `CORS_ALLOWED_ORIGINS` | `https://www.salysoltours.com` (y el dominio sin `www` si también sirve) |
   | `FRONTEND_URL` | `https://www.salysoltours.com` |
   | `HORAS_MINIMAS_RESERVA` | `16` |
   | `APARTADO_MINUTOS` | `0` al principio; `15` cuando se pruebe |
   | `STRIPE_*` | **llaves de prueba** (`sk_test_`) en el primer deploy |
   | `RESEND_API_KEY`, `RESEND_FROM`, `RESEND_BCC` | correo de confirmación y copia al negocio |
   | `SENTRY_DSN` | en el **grupo**, para que los cron también reporten |

5. **Variables en Vercel** (proyecto del sitio): `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL`
   (`https://www.salysoltours.com`), `NEXT_PUBLIC_EMPRESA_SLUG=sal-y-sol`, `NEXT_PUBLIC_WHATSAPP_NUMBER` (el real) y,
   si quieres, `NEXT_PUBLIC_HORAS_MINIMAS_RESERVA=16`.

## C. El despliegue (Claude, solo con tu "dale")

1. `git tag old/main-2026-08-30 origin/main` y subir la etiqueta.
2. `git push origin feat/marca-sun-baja:main` (avance sin fuerza). Esto dispara Render y el CI de GitHub.
3. Vigilar el build de Render: `migrate` debe terminar sin errores y `GET /healthz` responder 200.
4. Vercel: si el sitio se despliega por CLI, redesplegar (`vercel --prod` desde `frontend/`); si está ligado a `main`, se
   despliega solo. Después del backend, no antes.

## D. Justo después del deploy (shell de Render, servicio `pescadeportiva-api`)

```bash
python manage.py setup_roles
python manage.py createsuperuser            # tu cuenta
python manage.py migrar_la_paz_a_empresa --operador <tu-usuario>
```

Entrar a `/admin/` con esa cuenta antes de seguir: es la prueba de que cerró la ventana en que el staff recibe 403.
Luego, en este orden:

1. Sistema → **Aeropuertos**: deben estar LAP, CSL, SJD y LTO.
2. **Alta de empresa** para cada una de las cuatro (jefe, vendedora, llaves de Stripe, flota o vehículos). La pantalla
   muestra la URL del webhook de cada una.
3. Sembrar el catálogo real con `python manage.py seed_catalogo_real --produccion` (idempotente; exige que las cuatro
   empresas ya existan; no crea llaves de Stripe, ni lanchas ni habitaciones «DEMO», ni borra nada). Al final imprime el
   **relleno sin confirmar** que dejó: noche de hospedaje (2,500), tarifas del traslado de La Ventana (3,500 / 6,500),
   precio por persona de los paquetes, pesca de Piratas Adventures y los horarios salvo los de Sal y Sol. Corregirlos en
   el admin **antes de vender**. La flota (pangas, vehículos) también se captura a mano.
4. `python manage.py revisar_cupo --dias 90` (debe salir vacío con una base nueva).

## E. Stripe: primero en prueba, después dinero real

1. Por cada empresa: crear el webhook en su Stripe a `https://<api>/api/<slug>/stripe/webhook/` y pegar su `whsec_`
   junto con sus llaves en el admin (Empresas → la empresa). Falta uno y **el dinero entra sin que la reserva se marque
   pagada**.
2. Con llaves de prueba y la tarjeta `4242 4242 4242 4242`: una reserva completa de cada empresa, un paquete de dos
   empresas, una cancelación por mal clima y la conciliación (`manage.py conciliar_pagos --dry-run`).
3. Dos navegadores por el último lugar de un día con `APARTADO_MINUTOS=15`: el segundo debe volver al paso del viaje.
4. Solo entonces: llaves `sk_live_`/`pk_live_` por empresa, **webhooks nuevos** (cambia el `whsec_`) y una compra real
   de monto bajo, reembolsada.

## F. Antes de anunciar el sitio

- [ ] Precios reales en todo el catálogo (hoy hay de relleno: pesca de Piratas, noche de hospedaje, paquetes, USD).
- [ ] Número oficial de WhatsApp y, si se quiere el aviso por WhatsApp, la plantilla aprobada por Meta.
- [ ] Número de días de la garantía en el texto de reembolso.
- [ ] Textos legales revisados por quien corresponda (privacidad, deslinde).
- [ ] Cloudflare Turnstile (anti-bot) con el dominio final: llave pública en Vercel, privada en Render.
- [ ] Alertas de gasto en Stripe, Render y Supabase.
- [ ] `SECURE_HSTS_SECONDS` a `31536000` después de un par de días con HTTPS estable.
- [ ] Apagar o reapuntar el QA si ya no se usa.

## Si algo sale mal

- **El deploy de Render falla en `migrate`:** casi siempre es el rol (`tenancy.E001`) o falta `btree_gist`. Se corrige en
  Supabase y se reintenta el deploy; no hay datos que proteger.
- **Volver a la versión vieja:** `git push --force-with-lease origin old/main-2026-08-30:main` y redesplegar. Es un push
  forzado y se hace solo con tu autorización expresa; con la base ya reseteada, la versión vieja tendría que recrear su
  esquema.
- **Webhook sin configurar:** reservas sin marcar pagadas aunque el cobro entró. `conciliar_pagos` las rescata, pero no
  sustituye al webhook.
