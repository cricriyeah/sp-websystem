# Corte a multi-empresa — runbook de producción

Pasos que solo el dueño del negocio puede ejecutar, contra Render/Supabase/Stripe
reales. Ninguno se puede hacer desde el código. Ejecutar en este orden, en una sola
ventana — entre el paso 3 (`migrate`) y el paso 5
(`migrar_la_paz_a_empresa.py`), **todo el staff recibe 403 en el admin** (nadie
tiene `MembresiaEmpresa` todavía).

## 1. Rol de Postgres sin SUPERUSER/BYPASSRLS

En el SQL editor de Supabase, conectado como `postgres`, en este orden exacto
(`REASSIGN OWNED BY` por sí solo no basta en Postgres 15+/Supabase moderno — no
otorga `CREATE` sobre el esquema `public`, que ya no es de acceso libre):

```sql
-- 0. Extension btree_gist requerida para constraints EXCLUDE de hospedaje (bookings_reservaocupacion)
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 1. El rol de aplicacion (DB_USER actual de Render) debe poder recibir el
--    ALTER TABLE de mas abajo.
GRANT <rol_app> TO postgres;

-- 2. Sin esto, el primer CREATE TABLE de tenancy.0001_initial corriendo como
--    <rol_app> falla con "permission denied for schema public".
GRANT USAGE, CREATE ON SCHEMA public TO <rol_app>;

-- 3. Acotado a las tablas/secuencias de la app — NO usar REASSIGN OWNED BY,
--    que es de alcance base-de-datos-completa y arrastra cualquier otro
--    objeto que "postgres" posea ahi.
ALTER TABLE django_migrations OWNER TO <rol_app>;
ALTER TABLE django_content_type OWNER TO <rol_app>;
ALTER TABLE django_session OWNER TO <rol_app>;
ALTER TABLE auth_user OWNER TO <rol_app>;
ALTER TABLE auth_group OWNER TO <rol_app>;
-- ... repetir para cada tabla de fleet_*/bookings_*/payments_*/tenancy_*/
-- finance_*/axes_*: SELECT tablename FROM pg_tables WHERE schemaname = 'public'
-- lista las que falten.
```

Si la conexión de Render pasa por el pooler Supavisor (típico: Render sale por
IPv4, la conexión directa de Supabase es IPv6-only), `DB_USER` en Render lleva el
sufijo de proyecto: `<rol_app>.<project_ref>`, no el rol a secas — confirmar en
el dashboard de Supabase, pestaña Connection Pooling, cuál conexión usa
`render.yaml` antes de tocar nada.

## 2. Un solo rol en todo el pipeline

`<rol_app>` (el `DB_USER` que ya usa Render) corre `migrate` **y** gunicorn **y**
los dos crons (`pescadeportiva-conciliar-pagos`, `pescadeportiva-limpiar-checkouts`)
— no hace falta un segundo rol: `FORCE ROW LEVEL SECURITY` (ya en el código,
migración `tenancy.0003_rls`) somete también al dueño de la tabla. Es el mismo
patrón que ya corre en CI (`ci_rls`, ver Task I3) — si `tests_rls.py` pasó ahí
contra un rol que también hace `migrate`, este paso ya está probado.

## 3. Deploy

Push a `main` con el código de esta pieza. `render.yaml` corre `migrate` dentro
del `buildCommand` del servicio web — desde este punto, RLS está activo y
`empresa_id` es `NOT NULL`, pero **nadie tiene `MembresiaEmpresa` todavía**.

Si `DB_USER` es superusuario o tiene `BYPASSRLS`, el `migrate` (y cualquier
`manage.py check`) **falla con `Error tenancy.E001`** y el deploy no sale — el
system check `apps.tenancy.checks.revisar_rol_rls` lo verifica en cada arranque
con `DEBUG=False`. Corregir el rol (paso 1) antes de reintentar. Este check
convierte el "RLS existe pero no protege nada, sin síntoma visible" del paso 4
en un deploy bloqueado.

## 4. Verificación post-deploy obligatoria (no opcional)

Con la conexión real de la app (no como `postgres`):

```sql
SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;
```

Debe devolver `(false, false)`. Si devuelve cualquier otra cosa, RLS existe en la
base pero **no protege nada** — no seguir al paso 5 hasta que esto dé
`(false, false)`.

Esto ya lo verifica automáticamente el system check `tenancy.E001` en cada
`migrate`/`check` con `DEBUG=False` (paso 3), así que en la práctica un deploy
con el rol equivocado ni siquiera llega hasta aquí. La consulta manual queda
como confirmación de que el check corrió contra la conexión real (pooler
incluido).

## 5. Migrar cuentas — cierra la ventana de bloqueo del paso 3

Por SSH shell de Render (`pescadeportiva-api` → Shell):

```bash
python manage.py setup_roles
python manage.py migrar_la_paz_a_empresa --operador <tu-username>
```

(`setup_roles` primero — `migrar_la_paz_a_empresa` exige que los grupos `Jefe`/
`Vendedora`/`OperadorPlataforma` ya existan.) Confirmar que puedes entrar al
admin con tu cuenta antes de anunciar el corte como terminado — es la prueba de
que la ventana de bloqueo cerró.

## 6. Endpoint de webhook de Stripe

En el Dashboard de Stripe → Developers → Webhooks, **editar** (no crear uno
nuevo) el endpoint existente para que apunte a la ruta con el slug:
`https://pescadeportiva-api.onrender.com/api/sal-y-sol/stripe/webhook/`. Editar
conserva el mismo `whsec_`; si en vez de editar se crea uno nuevo, copiar su
`whsec_` nuevo a `Empresa.stripe_webhook_secret` en el admin (`/admin/tenancy/
empresa/`) antes de dar el corte por terminado.

## 7. Corte del frontend (misma ventana)

En Vercel, proyecto `sal-y-sol-sportfishing` → Settings → Environment Variables,
agregar `NEXT_PUBLIC_EMPRESA_SLUG=sal-y-sol` (ver Task I4) y redesplegar
(`vercel --prod` desde `frontend/`, o el redeploy del dashboard).

## 8. Limpieza de variables de Stripe en Render

Después de este corte, `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`/
`STRIPE_PUBLISHABLE_KEY` del environment group `pescadeportiva-secrets` **ya no
tienen ningún lector en el código** (`tenancy.0002_crear_sede_empresa_la_paz` las
leyó una sola vez, al crear la fila de "Sal y Sol" — de ahí en adelante las
llaves se rotan en el admin, por Empresa). Dejarlas en Render solo mientras haya
riesgo de rollback de esta pieza; después borrarlas o renombrarlas a
`STRIPE_*_BOOTSTRAP` para que quede evidente que ya no las lee nadie.

## 9. Sembrar catálogo real de servicios y paquetes

Para habilitar tours alternativos, experiencias o empresas de hospedaje:

1. Crear la `Empresa` en `/admin/tenancy/empresa/` vinculada a la `Sede` correspondiente.
2. Configurar las credenciales de Stripe de esa empresa (`stripe_publishable_key`, `stripe_secret_key`, `stripe_webhook_secret`).
3. Registrar sus servicios en `/admin/fleet/servicio/`:
   - Configurar `tipo_servicio`, `estrategia_cupo` (`por_recurso_dia`, `por_noche`, `bajo_demanda`) y `estrategia_precio`.
   - Si es hospedaje (`por_noche`): dar de alta las habitaciones o unidades en `/admin/fleet/recurso/` vinculadas al servicio.
4. Si se ofrecen paquetes: crear el `Paquete` en `/admin/fleet/paquete/` con su `precio_ancla` y asociar los servicios componentes en `/admin/fleet/paqueteservicio/` (todos deben pertenecer a la misma `empresa_lider`).
5. **Importante:** Las empresas nuevas **no requieren `Tarifa` legacy**. El modelo `Tarifa` singleton por empresa aplica únicamente a empresas con flujo clásico de pesca deportiva mono-tarifa (`sal-y-sol`). Las empresas nuevas operan al 100% mediante `Servicio` y `Paquete`.

## Trade-off aceptado, declarado (no un descuido)

El rol `<rol_app>` es dueño de las tablas, así que técnicamente puede correr
`ALTER TABLE ... NO FORCE ROW LEVEL SECURITY` y desactivar la protección. La
defensa asume que nadie ejecuta SQL arbitrario contra producción con esas
credenciales fuera del código de la aplicación — aceptable a la escala actual
(2 devs), revisar si el equipo crece.
