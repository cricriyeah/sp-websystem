# Extras del checkout (Brunch, Transporte, Licencia, Carnada) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vender transporte, licencia de pesca y carnada en el checkout con
precio fijo editable desde el admin, y renombrar el paso "Lunch" a "Extras"
(brunch incluido), sin romper el motor de cobro ni el cupo existentes.

**Architecture:** Catálogo genérico (`fleet.ExtrasItem`, `fleet.TransportePrecio`,
`fleet.PuntoEncuentro`) editable solo por jefes, igual que `fleet.Tarifa`.
Cada reserva congela lo que eligió (al armar el checkout) y lo que le costó
(al pagar) en `bookings.ReservaExtra` / `bookings.ReservaTransporte`.
`CrearPagoView` es el único que escribe el precio congelado — el checkout
solo escribe la selección — para no tener dos cálculos de dinero que puedan
desalinearse. Todo el cálculo vive en `apps/payments/pricing.py`, como
funciones puras sobre primitivos (no sobre instancias de modelo), igual que
ya hace `cargo_por_lunch` hoy.

Tres fases: **A** catálogo + endpoint público con precios ya resueltos por
el servidor (aislado, no toca `Reserva` — genuinamente desplegable e
independiente). **B** modelo de reserva, cálculo real del cobro, correo de
confirmación, y retiro de `lleva_lunch`/`pide_transporte`/`Tarifa.precio_lunch`
(backend). **C** frontend. **B y C no son independientes entre sí** — un
backend con B desplegado y un frontend sin C todavía deja de mandar/leer
campos que el checkout en vivo necesita — así que se despliegan en la misma
ventana. Hoy eso no rompe nada real porque el sitio no ha lanzado
(`[[estado-prelanzamiento]]`), pero la dependencia es real y no hay que
tratarlas como dos releases sueltos.

**Tech Stack:** Django 5 / DRF (backend), Next.js App Router (frontend), Postgres.

**Spec:** `docs/superpowers/specs/2026-08-28-extras-checkout-design.md`

## Global Constraints

- Todo el cálculo de dinero vive en `apps/payments/pricing.py`, nunca en
  otro módulo ni en el frontend (`backend/CLAUDE.md`).
- Cada precio nuevo lleva su par MXN/`_usd` nullable, mismo significado que
  `Tarifa.precio_usd`: `null` = no se ofrece en esa moneda.
- `numero_personas` de transporte es siempre el de la `Reserva`, nunca un
  campo que el cliente llena aparte.
- Sin fechas de vigencia en los catálogos: el precio vigente se edita a
  mano, cada reserva congela su propio snapshot.
- Cualquier modelo nuevo del admin necesita entrar a
  `apps/bookings/management/commands/setup_roles.py` o la vendedora no lo ve.
- El sitio no está lanzado: no hay reservas viejas que migrar
  (`docs/superpowers/specs/2026-08-28-extras-checkout-design.md`, sección
  Riesgos).

---

## File Map

### Fase A — Catálogo + endpoint público con precio resuelto (`fleet`, `payments/pricing.py`; no toca `Reserva`)

| File | Responsibility |
|---|---|
| `backend/apps/fleet/models.py` | Modify: agrega `ExtrasItem` (con `precio_en`), `TransportePrecio` (con `precio_en`/`recargo_en`, misma convención), `PuntoEncuentro`. Catálogo puro, sin lógica de reserva. |
| `backend/apps/fleet/admin.py` | Modify: `ModelAdmin` para los 3 catálogos nuevos, mismo patrón que `TarifaAdmin`. |
| `backend/apps/fleet/serializers.py` | Modify: serializers de los 3 catálogos; el de `ExtrasItem`/`TransportePrecio` incluye el monto ya resuelto para `(personas, moneda)`, no solo el precio de lista crudo. |
| `backend/apps/fleet/views.py` | Modify: `ExtrasPublicosView` (`GET`, query params `personas`/`moneda`, defaults 1/MXN como `/api/cupo/`). Llama a `apps.payments.pricing.cargo_por_extra`/`cargo_por_transporte` — importa el módulo de funciones puras, no modelos de `fleet` hacia `payments`, así que no hay ciclo. |
| `backend/apps/fleet/urls.py` | Modify (archivo existente, ya monta `/api/tarifa/`): agrega la ruta de `/api/extras/`. |
| `backend/apps/fleet/migrations/000X_extras_catalogo.py` | Create: migración de esquema para los 3 modelos nuevos. |
| `backend/apps/fleet/management/commands/seed_extras.py` | Create: comando idempotente (no migración de datos — **cambio hecho durante la implementación**, ver nota) que siembra brunch (copia el precio vigente de `Tarifa.precio_lunch`/`precio_lunch_usd`), licencia, carnada, transporte centro/periferia (2000/1800 MXN, recargo 1500 desde 4 personas, USD en `null`), puntos de encuentro iniciales. Mismo patrón que `setup_roles`: se corre a mano en producción, `manage.py seed_extras`. |
| `backend/apps/fleet/tests.py` | Modify: tests de los 3 modelos nuevos (`precio_en`/`recargo_en`, `unique_together` de zona) y del endpoint (resuelve bien con/sin recargo, defaults de query params, 200 con catálogo vacío). |
| `backend/apps/payments/pricing.py` | Modify: agrega `cargo_por_extra(precio, cobrar_por_persona, numero_personas)` y `cargo_por_transporte(precio_base, recargo_grupo, min_personas_recargo, numero_personas)` — funciones puras sobre primitivos, mismo estilo que `cargo_por_lunch`. Único lugar de cálculo de dinero del sistema. |
| `backend/apps/payments/tests.py` | Modify: agrega tests de las dos funciones nuevas. `cargo_por_lunch` y sus tests **no se tocan en esta fase** — se retiran en la Fase B, junto con el resto de lunch (ver esa fase). |

### Fase B — Reserva, cobro real, correo, retiro de `lleva_lunch` (backend; se despliega junto con Fase C)

| File | Responsibility |
|---|---|
| `backend/apps/bookings/models.py` | Modify: agrega `ReservaExtra` (`related_name='extras_seleccionados'` — a propósito distinto de `'extras'`, que ya es el nombre del método de columna en `ReservaAdmin`; `subtotal` devuelve `None` si `precio_unitario`/`cantidad` siguen sin poner) y `ReservaTransporte` (con `clean()`: exactamente uno de `punto_encuentro`/`direccion_personalizada`, **y** si `punto_encuentro` está puesto, `zona` tiene que coincidir con `punto_encuentro.zona` — si no, rechaza); elimina `lleva_lunch` y `pide_transporte` de `Reserva`; agrega `Reserva.pide_extras_whatsapp` (booleano simple, mismo trato que `pide_bebidas`, para reservas que crea la vendedora fuera del checkout web); `tiene_cotizaciones_pendientes` pasa a `pide_bebidas or pide_extras_whatsapp`. |
| `backend/apps/fleet/models.py` | Modify (segunda pasada, después de que la Fase A ya sembró `ExtrasItem` con esos valores): elimina `Tarifa.precio_lunch`, `precio_lunch_usd`, `lunch_en()`. |
| `backend/apps/fleet/serializers.py` | Modify: quita `precio_lunch`/`precio_lunch_usd` de `TarifaSerializer` y corrige su docstring ("precio del lunch", "bebidas y transporte no tienen precio en linea" — ya no es cierto para transporte). |
| `backend/apps/fleet/tests.py` | Modify: quita el kwarg `precio_lunch=Decimal('300.00')` de los `Tarifa.objects.create(...)` de los tests existentes (si no, `TypeError: unexpected keyword argument`) y la aserción sobre `precio_lunch` en la respuesta de `/api/tarifa/`. |
| `backend/apps/bookings/migrations/000X_reserva_extra_transporte.py` | Create: agrega `ReservaExtra`/`ReservaTransporte`, quita los 2 campos viejos de `Reserva`. |
| `backend/apps/fleet/migrations/000Z_drop_tarifa_lunch.py` | Create: quita los 2 campos de `Tarifa`. Depende de que Fase A (`000Y_seed_extras`) ya haya corrido. |
| `backend/apps/bookings/admin.py` | Modify, en el mismo cambio que quita los campos de `Reserva` (un `list_filter`/método sobre un campo borrado es `admin.E116`, rompe cualquier `manage.py`, no solo el admin en el navegador): quita `'lleva_lunch'`/`'pide_transporte'` de `list_filter`, agrega `'pide_extras_whatsapp'`; el método de columna `extras()` (hoy arma su lista de "por cotizar" con la tupla `((obj.pide_bebidas, 'bebidas'), (obj.pide_transporte, 'transporte'))`) pasa a leer `obj.extras_seleccionados.all()` para lo comprado **y** cambia esa tupla a `((obj.pide_bebidas, 'bebidas'), (obj.pide_extras_whatsapp, 'extras'))` — el mismo par que ahora evalúa `tiene_cotizaciones_pendientes`, para que el aviso y la lista nunca puedan discrepar; agrega inlines de solo lectura de `ReservaExtra`/`ReservaTransporte` (es historial de la venta — vendida por el checkout web, que es el único que congela precio en esta pieza; ver spec "Esta pieza vende extras solo por el checkout web"). No se edita ahí porque no hay un segundo mecanismo que congele precio fuera de `CrearPagoView`. |
| `backend/apps/bookings/serializers.py` | Modify: `ReservaCheckoutSerializer` acepta la selección de extras (ids de `ExtrasItem`, filtrados a `activo=True` en el queryset del campo) y los datos de transporte (`punto_encuentro` filtrado a `activo=True`, `direccion_personalizada`, `zona`) en vez de `lleva_lunch`/`pide_transporte`. Si viene `punto_encuentro`, ignora cualquier `zona` del cuerpo de la petición y usa `punto_encuentro.zona` — solo con "otra dirección" `zona` es lo que mandó el cliente. Escribe solo la selección — precio, cantidad y `numero_personas` de transporte quedan `null` hasta que se pague. Llama `full_clean()` también sobre el `ReservaTransporte`, junto al de la `Reserva`. |
| `backend/apps/bookings/tests.py` | Modify: tests del serializer con selección de extras/transporte, de `ReservaTransporte.clean()` (rechaza los dos vacíos, rechaza los dos con valor, rechaza `zona` que no coincide con la del `punto_encuentro`), y de que mandar la `zona` de un hotel distinta a la real se ignora/se rechaza en vez de aceptarse. |
| `backend/apps/bookings/management/commands/setup_roles.py` | Modify: agrega permiso de vista de `fleet.PuntoEncuentro`, `bookings.ReservaExtra` y `bookings.ReservaTransporte` al grupo Vendedora — sin los dos últimos, Django quita en silencio los inlines nuevos de su vista de `ReservaAdmin` (`get_inline_instances` los descarta sin permiso, sin error) y ella deja de ver qué compró el cliente. `fleet.ExtrasItem`/`TransportePrecio` **sin** permisos para Vendedora — mismo trato que `fleet.Tarifa`, son precios. |
| `backend/apps/payments/pricing.py` | Modify (segunda pasada): quita `cargo_por_lunch`; corrige el docstring del módulo (transporte ya no es "no se cobra en línea", solo bebidas sigue así). |
| `backend/apps/payments/views.py` | Modify: `CrearPagoView` — el recálculo de extras/transporte (qué fila se cae por inactiva, qué precio vigente le toca a cada una) se hace **en memoria primero**, antes de cualquier `return` de guarda (`PagoEnCurso` → 409, precio faltante → 503). Solo se persiste — borrados, precios congelados y `reserva.save(update_fields=[...])` — en el mismo bloque final que ya crea/reutiliza el intent, dentro de la `transaction.atomic()` que ya existe implícita en ese método. Ningún `return` temprano puede dejar a medias una fila recongelada o borrada: hoy esa ruta no escribe nada (el único write es después de la guarda), y con este cambio dejaría de serlo si el orden no se respeta — un doble clic mientras el primer intent sigue `processing` no debe reescribir precios ni borrar selecciones. `EstadoReservaView` — en la rama `pendiente_pago`, devuelve la selección actual (ids/datos, no precios) en vez de `lleva_lunch`. |
| `backend/apps/payments/tests.py` | Modify (segunda pasada): quita `cargo_por_lunch` del bloque de imports (rompe la carga del módulo entero si no) y borra `test_el_lunch_es_uno_por_persona`; quita los kwargs `precio_lunch`/`precio_lunch_usd` de los `Tarifa.objects.create(...)` existentes; reemplaza `test_sin_precio_de_lunch_en_dolares…` por el equivalente con un `ExtrasItem` sin `precio_usd`; reescribe `test_bebidas_y_transporte_no_suman_al_cobro` a "bebidas no suma, transporte sí" (ya no usa `.update(pide_transporte=True)`, que ahora es `FieldError`); reescribe `test_el_lunch_se_cobra_por_cada_persona` como brunch vía `ReservaExtra` (usaba `.update(lleva_lunch=True)`, ahora `FieldError`); reescribe `test_cambiar_los_extras_ajusta_el_intent_en_vez_de_duplicarlo` para que el cambio de extras sea crear/borrar un `ReservaExtra` entre los dos `post()` — es la única prueba de que un cambio de monto ajusta el intent en vez de duplicarlo, no puede perderse en la reescritura; agrega test de que `crear-pago` congela el precio vigente del catálogo (no el que traía la reserva al momento del envío del formulario), test de que un item desactivado entre la selección y el pago se cae del total sin bloquear el resto, y test de que un 409 por pago en curso (doble clic) no deja precios recongelados ni filas borradas a medias. |
| `backend/apps/notifications/services.py` | Modify: `_cuerpo_html` deja de leer `reserva.lleva_lunch`/`reserva.pide_transporte`. Lista `reserva.extras_seleccionados.all()` (brunch/licencia/carnada compradas) y usa `reserva.transporte` si existe (punto de encuentro real, no el texto fijo de Marina La Costa) para lo que sea traslado pagado; el párrafo de "esto se cotiza aparte" (hoy arma su lista con `((obj.pide_bebidas, 'bebidas'), (obj.pide_transporte, 'transporte'))`) cambia esa tupla a `((reserva.pide_bebidas, 'bebidas'), (reserva.pide_extras_whatsapp, 'extras'))` — el mismo par que evalúa `tiene_cotizaciones_pendientes`, para que el correo nunca diga "Pediste ." con la lista vacía mientras el aviso sigue disparando. |
| `backend/apps/notifications/tests.py` | Modify: test de `_cuerpo_html` bajo `override_settings(RESEND_API_KEY=..., RESEND_FROM=...)` — hoy nada prueba esta función porque el guard de claves vacías corta antes de llegar a ella. Casos: reserva con brunch+licencia+carnada+transporte, reserva sin extras, reserva con `pide_bebidas` pendiente. |

### Fase C — Frontend (se despliega junto con Fase B, no antes ni después)

| File | Responsibility |
|---|---|
| `frontend/src/lib/api.ts` | Modify: tipos de `ExtrasItem`/`TransportePrecio`/`PuntoEncuentro` (con el monto ya resuelto que trae `/api/extras/`); quita `lleva_lunch`/`precio_lunch`/`precio_lunch_usd`. |
| `frontend/src/app/[lang]/dictionaries/es.json` / `en.json` | Modify: copy del paso Extras (brunch, transporte, licencia, carnada); quita las claves de "lunch". |
| `frontend/src/components/checkout-view.tsx` | Modify: reemplaza el bloque de lunch por el paso Extras completo. Pide `/api/extras/?personas=N&moneda=M` cada vez que cambian `people`/moneda/selección y muestra los montos que trae la respuesta — no reimplementa `cobrar_por_persona` ni el umbral de recargo, esas reglas viven solo en el servidor. Envía la selección al serializer. |
| `frontend/src/components/amenities-reminder.tsx` | Modify: itera sobre los extras faltantes en vez de solo lunch. |

## Restricciones de orden (de la revisión del crítico de arquitectura, 2 pasadas)

1. **Cambio hecho durante la implementación de la Fase A, no estaba en la
   versión aprobada por el crítico:** el sembrado del catálogo dejó de ser
   una migración de datos y pasó a ser `manage.py seed_extras`, un comando
   idempotente. Al correr las pruebas, `Ran 100 tests` con la migración de
   datos incluida mostró que Django aplica las migraciones **una sola vez**
   al construir la base de pruebas, y el rollback por test (`TestCase`) solo
   deshace lo que pasa *dentro* de cada test — así que las filas sembradas
   por migración quedaban como línea base **para todo el suite**, no solo
   para `apps.fleet`, y las pruebas nuevas que asumían catálogo vacío
   fallaban. Un comando de gestión no corre nunca durante `manage.py test`
   (solo lo ejecuta alguien a mano en producción), así que este problema
   desaparece por completo — y de paso se cae solo el riesgo original que el
   crítico señaló (`apps.get_model` vs. import en vivo de `Tarifa`): un
   comando de gestión corre contra el *modelo actual* de la app ya cargada,
   no dentro de una migración con modelo histórico, así que un import normal
   (`from apps.fleet.models import Tarifa`) es correcto y no hay nada que
   resolver con `apps.get_model`.
2. `fleet/migrations/000Z_drop_tarifa_lunch` (Fase B) debe aplicarse
   **después** de correr `manage.py seed_extras` en cada entorno (local,
   producción) — si se corre el comando después de que esa migración ya
   quitó `precio_lunch`/`precio_lunch_usd`, el brunch se siembra con
   `Tarifa.precio_lunch` inexistente. Esto es un paso operativo (correr el
   comando antes de desplegar la Fase B), no algo que el código pueda
   forzar solo — igual que `setup_roles` ya es un paso manual documentado
   en `pendientes-manuales-produccion`.
2. Dentro de la Fase B, el ajuste de `bookings/admin.py` va en el **mismo** cambio que quita `lleva_lunch`/`pide_transporte` de `Reserva` — un admin roto por un campo inexistente tumba `manage.py makemigrations` antes de que la migración se pueda generar.
3. Fases B y C se despliegan en la misma ventana (ver Architecture).
4. Esta pieza vende extras con precio congelado **solo por el checkout web** (`CrearPagoView`, que exige `checkout_id`). No se agrega un segundo mecanismo que congele precio desde el admin — ver spec, sección "Qué pasa con `lleva_lunch`".
5. En `CrearPagoView`, el recálculo/borrado de extras se hace en memoria antes de cualquier `return` de guarda (409 pago en curso, 503 sin precio); solo se persiste en el mismo bloque final que ya escribe `precio_total` y el intent. Un `return` temprano no debe dejar nada a medias escrito.

<!-- arch-critic: APPROVED (3 pasadas — la 3a no encontró Critical, los 3 Significant que quedaban se corrigieron inline sin relanzar, ver notas de sesión) -->
