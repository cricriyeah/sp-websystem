# Entorno de QA

Copia estable del sistema para que se pruebe (reservas y backoffice) mientras el
frontend se rediseña en otra rama. Es **independiente de producción**: backend,
base de datos, frontend y llaves propios.

| Pieza | Rama | Dónde |
|---|---|---|
| Backend QA (`pescadeportiva-qa-api` y su cron) | `qa/checkout-unificado` | Render, `render.qa.yaml` |
| Base de datos QA | | Postgres nuevo (Supabase u otro), no el de producción |
| Frontend QA | `qa/checkout-unificado` | Proyecto nuevo de Vercel, carpeta raíz `frontend` |
| Rediseño de marca | `feat/rebrand` | Local; no se despliega aquí |

Las correcciones que salgan de la prueba se hacen en `qa/checkout-unificado` y
se llevan a `feat/rebrand` con `git merge qa/checkout-unificado`.

## Orden

1. **Publicar la rama.** `git push -u origin qa/checkout-unificado`. La rama trae
   toda la historia del trabajo multi-empresa, que producción no tiene.
2. **Base de datos.** Crear un Postgres nuevo. Anotar nombre, usuario,
   contraseña, host y puerto.
3. **Stripe en modo de prueba.** Cada empresa cobra con su propia cuenta, así que
   hace falta `sk_test_…` y `pk_test_…` de **cada** empresa que se vaya a probar.
   Esas llaves no van en variables de entorno: se capturan en el admin (paso 8).
4. **Render.** Blueprints > New Blueprint Instance, repo de este proyecto, rama
   `qa/checkout-unificado`, archivo `render.qa.yaml`. Capturar las variables que
   pide (ver lista abajo). Esperar a que `pescadeportiva-qa-api` pase el
   health check `/healthz`.
5. **Vercel.** Proyecto nuevo, mismo repo, rama `qa/checkout-unificado`,
   *Root Directory* `frontend`. Variables:
   - `NEXT_PUBLIC_API_URL` = URL pública de `pescadeportiva-qa-api`
   - `NEXT_PUBLIC_SITE_URL` = URL del propio proyecto de Vercel
   - `NEXT_PUBLIC_EMPRESA_SLUG`, `NEXT_PUBLIC_TRANSPORTE_EMPRESA_SLUG`,
     `NEXT_PUBLIC_WHATSAPP_NUMBER`: los mismos valores que en `frontend/.env.example`
   - `NEXT_PUBLIC_TURNSTILE_SITE_KEY`: dejar sin definir en QA
6. **Webhook de Stripe de prueba, uno por empresa.** En el dashboard de cada
   cuenta de Stripe (modo de prueba) crear un endpoint hacia
   `https://<pescadeportiva-qa-api>/api/<empresa_slug>/stripe/webhook/` y guardar
   su `whsec_…` en esa empresa (paso 8).
7. **Cerrar el círculo.** Con la URL de Vercel ya conocida, poner
   `CORS_ALLOWED_ORIGINS` y `FRONTEND_URL` en Render y redesplegar.
8. **Datos.** Desde la consola (Shell) de `pescadeportiva-qa-api`:
   ```
   python manage.py createsuperuser
   python manage.py seed_catalogo_real
   python manage.py migrar_la_paz_a_empresa   # solo si el seed lo pide
   python manage.py setup_roles
   ```
   Luego, en `/admin/`, abrir cada **Empresa** y capturar `stripe_secret_key`,
   `stripe_publishable_key` y `stripe_webhook_secret` (de prueba).

   Para llevar también las reservas y usuarios de prueba de un SQLite local, se
   hace un volcado (`dumpdata`) y se carga con `loaddata`; se prepara aparte
   porque depende de qué se quiera conservar.

## Variables de Render a capturar

Todas están declaradas en `render.qa.yaml` con `sync: false`.

- **Obligatorias:** `DJANGO_SECRET_KEY` (nueva), `DB_NAME`, `DB_USER`,
  `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DJANGO_ALLOWED_HOSTS` (dominio de
  Render), `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`. Las llaves de Stripe no son
  variables: van por empresa en el admin.
- **No se declaran en QA:** `RESEND_*`, `WHATSAPP_*`, `TURNSTILE_SECRET_KEY`,
  `SENTRY_DSN`. Sin ellas el backend funciona igual y no le escribe a clientes
  reales desde datos de prueba.

## Qué debe probar quien haga el QA

- Paquete de una empresa, paquete cruza-empresa (dos pagos), servicio suelto y
  traslados, en móvil y en escritorio.
- Tarjetas de prueba de Stripe: pago correcto, pago rechazado, y recargar la
  página a medio pago para comprobar la reanudación.
- Cambio de idioma (es/en) en cada paso.
- Backoffice (`/admin/`): reservas, órdenes, pagos, conciliación y roles.

## Pendientes conocidos

- 7 tests `Conciliar*` de `apps/payments/tests.py` fallan y no se han comparado
  con la rama base. Aclararlo antes de dar por buena la conciliación.
- Si Stripe Link sigue activo en el dashboard de prueba, en móvil queda un hueco
  entre el formulario de tarjeta y el botón de pago.
