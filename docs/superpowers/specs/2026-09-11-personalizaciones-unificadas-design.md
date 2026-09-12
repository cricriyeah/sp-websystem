# Personalizaciones unificadas — check (recomendada/opcional) e input (texto/número/selección)

Rama: `feat/transporte-multi-empresa`, worktree `.claude/worktrees/transporte-multi-empresa`.
Estado del proyecto: sin lanzar (producción es ambiente de pruebas, sin clientes ni
dinero real) — ver `docs/superpowers/plans/` y memoria del usuario. Esto autoriza a
retirar/rediseñar modelos existentes sin resguardo de compatibilidad ni migración de
datos reales.

## Contexto y problema

Hoy existen **dos catálogos paralelos** de "cosas que se le ofrecen al cliente en el
checkout", con reglas distintas e incompletas frente a lo que pide el negocio:

1. **`fleet.ExtrasItem` / `bookings.ReservaExtra`** (legacy, solo pesca): brunch,
   licencia, carnada. Tiene `preseleccionado` pero ningún check está realmente
   "forzado" a nivel modelo — sin embargo el checkout (`checkout-view.tsx`) trata
   `tipo == 'licencia'` como caso especial "necesario" en el modal `AmenitiesReminder`.
   Solo aplica a `Reserva.servicio.tipo_servicio == 'pesca'`, nunca a paquetes ni a
   otros servicios sueltos (transporte, hospedaje). Congela precio al pagar
   (`CrearPagoView._resolver_extras`).
2. **`fleet.Personalizacion` / `fleet.ServicioPersonalizacion`** (más nuevo, paquetes):
   tiene `obligatorio` y `preseleccionado`. En el serializer y en `pricing.py`, todo lo
   que es `obligatorio or preseleccionado` se **auto-incluye siempre en el cobro**, sin
   checkbox, sin forma de que el cliente lo quite — el frontend ni lo muestra
   (`personalizacionesDisponibles` en `checkout-view.tsx` filtra ambos casos). Solo
   aplica cuando la reserva tiene `paquete_id`; un servicio suelto no puede tener
   personalizaciones de este catálogo. No congela precio al pagar: `CrearPagoView`
   vuelve a leer `ServicioPersonalizacion.precio` vigente en `precio_paquete_total`.

Ninguno de los dos resuelve lo que pide el negocio:

- Un check "recomendado" que venga marcado por defecto, que el cliente SÍ pueda
  desmarcar, con un aviso antes de dejarlo pagar sin él (ya existe un modal parecido,
  `AmenitiesReminder`, pero solo para el catálogo legacy y sin esta semántica exacta).
- Un check "opcional" que no venga marcado (esto ya existe y funciona bien en
  `Personalizacion` — se conserva tal cual).
- Un input (pregunta) que puede ser de texto libre, número o selección de una lista,
  marcado como obligatorio (bloquea el pago si queda vacío) o no obligatorio.

## Decisiones ya tomadas con el dueño

1. **Unificar los dos catálogos en uno solo** (`Personalizacion`/`ServicioPersonalizacion`).
   Se retiran `fleet.ExtrasItem` y `bookings.ReservaExtra` por completo. Nada que
   migrar: el proyecto no ha lanzado.
2. **No existe más un check 100% forzado.** El caso legal (licencia de pesca) pasa a
   ser "recomendada" (preseleccionada, con aviso reforzado al desmarcar). El riesgo de
   que alguien la quite es una decisión de negocio ya aceptada por el dueño.
3. **Los inputs siempre son gratis.** Nunca cobran; solo recolectan un dato.
4. **El input tiene tres subtipos**: `texto`, `numero`, `seleccion` (con lista de
   opciones que el jefe define en el admin, por `Personalizacion`).
5. **Bloqueo de pago**: un input obligatorio vacío se valida al crear la Reserva
   (`POST /api/.../reservas/`), que en el flujo real ocurre justo antes de crear el
   pago — equivalente en la práctica a "bloquear al pagar". No se bloquea el avance
   entre pasos anteriores del checkout.
6. **`seed_extras.py` se reescribe** para crear brunch/licencia/carnada como
   `Personalizacion`/`ServicioPersonalizacion` (licencia con `preseleccionado=True`).
7. **`cantidad_editable`/`cobrar_por_persona` siguen existiendo solo para `check`.**
   No aplican a ningún subtipo de input.
8. **La respuesta de un input se ve solo en el detalle de la Reserva en el admin**, no
   en la Agenda.

## Modelo de datos

### `fleet.Personalizacion` (catálogo reutilizable, por Empresa)

Campos que se agregan:

- `tipo_interaccion` — `CharField` con choices `check`, `input_texto`, `input_numero`,
  `input_seleccion`. Default `check`.
- `opciones_seleccion` — `JSONField(default=list, blank=True)`. Lista de strings.
  Solo tiene sentido si `tipo_interaccion == input_seleccion`.

Campos que se conservan sin cambio de forma, pero con validación nueva:

- `tipo` (bebida/licencia/carnada/otro) sigue siendo una etiqueta libre de
  agrupación visual — **eje independiente** de `tipo_interaccion**. No se tocan sus
  choices ni su uso en el modal de aviso.
- `cobrar_por_persona`, `cantidad_editable`: válidos solo si `tipo_interaccion == check`.

`clean()` nuevo:

```
if tipo_interaccion == 'input_seleccion' and not opciones_seleccion:
    error: "Las personalizaciones de selección necesitan al menos una opción."
if tipo_interaccion != 'input_seleccion' and opciones_seleccion:
    error: "Las opciones de selección solo aplican al tipo 'selección'."
if tipo_interaccion != 'check' and (cobrar_por_persona or cantidad_editable):
    error: "'Cobrar por persona' y 'cantidad editable' solo aplican a personalizaciones tipo check."
```

### `fleet.ServicioPersonalizacion` (precio + comportamiento por Servicio)

Sin campos nuevos — se **redefine el significado** de los dos booleanos existentes
según el `tipo_interaccion` de su `Personalizacion`:

- `preseleccionado`: solo tiene efecto si `tipo_interaccion == check`.
  `True` = recomendada (checkbox marcado por defecto, se puede desmarcar con aviso).
  `False` = opcional (checkbox sin marcar). Para cualquier `input_*`, debe quedar en
  `False` (no aplica).
- `obligatorio`: solo tiene efecto si `tipo_interaccion` es `input_*`.
  `True` = obligatoria (bloquea la creación de la Reserva si `respuesta` viene vacía).
  `False` = no obligatoria. Para `check`, debe quedar en `False` (ya no existe el
  forzado — ver decisión 2).

`clean()` nuevo:

```
if personalizacion.tipo_interaccion == 'check' and obligatorio:
    error: "obligatorio ya no aplica a personalizaciones tipo check; usa preseleccionado."
if personalizacion.tipo_interaccion != 'check' and preseleccionado:
    error: "preseleccionado solo aplica a personalizaciones tipo check."
if personalizacion.tipo_interaccion != 'check' and (precio or precio_usd):
    error: "Las personalizaciones tipo input no pueden tener precio."
```

(La restricción de empresa cruzada entre `servicio`/`personalizacion` ya existe y se
conserva sin cambio.)

### `bookings.ReservaPaquetePersonalizacion` → renombrado a `bookings.ReservaPersonalizacion`

Deja de ser exclusivo de paquete: representa "esta `ServicioPersonalizacion` aplica a
esta Reserva", ya sea porque el Servicio es un componente de un Paquete o porque es
el Servicio directo de una reserva suelta.

- Se agrega `respuesta` — `TextField(blank=True, default='')`. Guarda el texto,
  número (como texto) o la opción elegida, según el subtipo del input. Vacío para
  filas de tipo `check`.
- `cantidad` se conserva (solo relevante para `check`; para `input_*` siempre `1`,
  validado en `clean()`).
- `related_name` de la FK a `Reserva` cambia de `paquete_personalizaciones` a
  `personalizaciones_seleccionadas` (refleja que ya no es exclusivo de paquete).

`clean()` nuevo:

```
if servicio_personalizacion.personalizacion.tipo_interaccion == 'check':
    if respuesta: error: "Un check no lleva respuesta."
else:
    if cantidad != 1: error: "La cantidad no aplica a un input."
    if tipo_interaccion == 'input_numero': respuesta debe parsear como número.
    if tipo_interaccion == 'input_seleccion': respuesta debe estar en opciones_seleccion.
```

### Retiro de `fleet.ExtrasItem` y `bookings.ReservaExtra`

Se eliminan ambos modelos. Una migración de Django los dropea (no hay datos reales
que preservar). Todo lo que hoy lee/escribe estos modelos se reescribe contra
`Personalizacion`/`ServicioPersonalizacion`/`ReservaPersonalizacion` (ver más abajo el
inventario completo de los 17 archivos backend afectados).

## Precio y congelado (corrige una inconsistencia existente)

Hoy `ExtrasItem` congela precio al pagar (`CrearPagoView._resolver_extras` escribe
`precio_unitario`/`cantidad` en `ReservaExtra` en el momento de `crear-pago`), pero
`ServicioPersonalizacion` en un paquete **no** — `precio_paquete_total` relee el precio
vigente del catálogo cada vez, incluso en `CrearPagoView`. Es una inconsistencia que se
corrige como parte de esta unificación: **todo el catálogo unificado congela precio al
pagar**, con el mismo patrón que ya usa `ExtrasItem` hoy.

Cambios en `ReservaPersonalizacion`:

- Se agregan `precio_unitario` y `precio_unitario_moneda` (o reutilizar un único campo
  ya que `Reserva.moneda` es fija por reserva) — `null=True, blank=True` mientras la
  reserva sigue `pendiente_pago`, igual que `ReservaExtra.precio_unitario` hoy. Solo
  `CrearPagoView` los llena, con el precio vigente de `ServicioPersonalizacion` en ese
  momento.

Cambios en `pricing.py`:

- Se retira la auto-inclusión `es_incluida = sp.obligatorio or sp.preseleccionado` de
  `precio_paquete_total`. El total se arma **únicamente** con las filas
  `ReservaPersonalizacion` que existen para la Reserva — recomendada y opcional pesan
  igual en el cálculo; la única diferencia entre ambas es el estado inicial del
  checkbox en el frontend (ver más abajo) y el aviso al desmarcar.
- Se generaliza `precio_paquete_total` (o se agrega una función hermana) para que
  funcione también sobre una Reserva de servicio suelto, no solo de paquete: el total
  es `precio_base_del_servicio_o_paquete + Σ precio de las ServicioPersonalizacion tipo
  check seleccionadas` (los `input_*` nunca suman, siempre validado en `clean()` a
  precio 0).
- `CrearPagoView` deja de tener una rama separada `_resolver_extras` para
  `ExtrasItem`; usa el mismo camino para paquete y para servicio suelto, congelando
  `precio_unitario` en cada `ReservaPersonalizacion` de tipo `check` de la reserva.

## Backend: generalizar el serializer más allá de paquetes

En `apps/bookings/serializers.py`:

- Se quita la validación `"Las personalizaciones solo aplican para paquetes"`. El
  conjunto de `ServicioPersonalizacion` válidas para una Reserva se resuelve así:
  - Si hay `paquete`: unión de `ServicioPersonalizacion` de cada componente activo
    (como hoy).
  - Si hay `servicio` (reserva suelta): las `ServicioPersonalizacion` de ese Servicio.
- Se quita la validación `"la personalización no es opcional (obligatorias/preseleccionadas
  van incluidas)"` — ya no existe esa categoría de "no se puede enviar explícito"; el
  payload de `personalizaciones` es la fuente de verdad completa de qué checks están
  marcados (recomendada u opcional, el front manda el estado real, incluida cualquier
  recomendada que el cliente haya desmarcado).
- Nueva validación: para cada `ServicioPersonalizacion` de tipo `input_*` con
  `obligatorio=True` que aplique a la Reserva (por Paquete o por Servicio directo), debe
  existir una entrada en el payload con `respuesta` no vacía — si no, 400. Formato:
  - `input_numero`: `respuesta` debe convertir a `Decimal`/`float` sin error.
  - `input_seleccion`: `respuesta` debe ser exactamente una de
    `personalizacion.opciones_seleccion`.
- `_sincronizar_personalizaciones` (o su nuevo nombre) crea/actualiza filas de
  `ReservaPersonalizacion` para AMBOS casos (paquete y servicio suelto), guardando
  `cantidad` (checks) o `respuesta` (inputs) según corresponda.

`PersonalizacionSeleccionSerializer` (el serializer de cada ítem del payload) gana un
campo `respuesta` opcional (string, default `''`).

## Frontend (`checkout-view.tsx` + `pricing-paquete.ts`)

- `personalizacionesDisponibles` deja de filtrar `obligatorio`/`preseleccionado`: **todo**
  `ServicioPersonalizacion` activo del Paquete o del Servicio suelto se muestra.
- Estado inicial: los `check` con `preseleccionado=true` (recomendada) inicializan
  `personalizaciones` como marcados (hoy el estado arranca vacío `[]` — cambia a
  arrancar con los ids de las recomendadas). Los `opcional` arrancan sin marcar, igual
  que hoy.
- Al desmarcar una recomendada, mismo patrón de aviso que `AmenitiesReminder` (se
  reutiliza/generaliza ese componente en vez de crear uno nuevo): antes de dejar
  avanzar al pago, un modal muestra qué recomendadas quedaron sin marcar, con opción
  de volver a marcarlas o continuar sin ellas.
- Los `input_texto`/`input_numero`/`input_seleccion` se pintan como campo de texto,
  `<input type="number">`, o `<select>` con `opciones_seleccion`, en el mismo bloque de
  "Personalizaciones". Los obligatorios muestran un asterisco; si el cliente intenta
  avanzar/pagar con uno vacío, error inline junto al campo (usa el mismo mecanismo de
  validación que ya existe para otros campos requeridos del checkout) — el submit no
  sale hasta llenarlo.
- Este bloque deja de estar condicionado a `paquete`: aparece también cuando
  `servicio` está seteado directamente (pesca legacy, transporte, cualquier servicio
  suelto con `ServicioPersonalizacion` asociadas).
- `AmenitiesReminder` (y su tipo `ExtraPendiente`) se generaliza para trabajar sobre
  `ServicioPersonalizacion`/`Personalizacion` en vez de `ExtrasItem` — mismo
  componente, nueva fuente de datos.

## Admin

Hoy no existe ningún inline para `ReservaPaquetePersonalizacion` en `ReservaAdmin` —
se agrega `ReservaPersonalizacionInline` (solo lectura, mismo criterio que
`ReservaExtraInline`: es historial de lo que se congeló al pagar) mostrando
`servicio_personalizacion`, `cantidad`, `respuesta`, `precio_unitario`. Reemplaza a
`ReservaExtraInline` (que se elimina junto con `ExtrasItem`/`ReservaExtra`).

## Semilla (`seed_extras.py`)

Se reescribe para crear, sobre el Servicio de pesca de la Empresa demo:

- `Personalizacion` "Brunch" (`tipo=brunch`, `tipo_interaccion=check`,
  `cobrar_por_persona=True`), `ServicioPersonalizacion(preseleccionado=False)`.
- `Personalizacion` "Licencia de pesca" (`tipo=licencia`, `tipo_interaccion=check`),
  `ServicioPersonalizacion(preseleccionado=True)` — recomendada, ya no forzada.
- `Personalizacion` "Carnada" (`tipo=carnada`, `tipo_interaccion=check`),
  `ServicioPersonalizacion(preseleccionado=True)`.

Mismo criterio de idempotencia que tiene hoy (`get_or_create` por nombre/empresa).

## Inventario de archivos backend afectados (17, de la búsqueda de `ReservaExtra`/`ExtrasItem`)

`apps/bookings/admin.py`, `apps/notifications/tests.py`, `apps/payments/tests.py`,
`apps/bookings/tests.py`, `apps/bookings/models.py`, `apps/fleet/models.py`,
`apps/payments/pricing.py`, `apps/bookings/serializers.py`, `apps/fleet/tests.py`,
`apps/fleet/views.py`, `apps/fleet/admin.py`, `apps/bookings/tests_tenancy.py`,
`apps/fleet/management/commands/seed_extras.py`, `apps/fleet/serializers.py`,
`apps/fleet/migrations/0013_backfill_empresa.py` (histórico, no se toca — las
migraciones viejas se quedan, la eliminación es una migración nueva),
`apps/fleet/migrations/0008_extrasitem_puntoencuentro_transporteprecio.py` (ídem,
histórico), `apps/bookings/migrations/0018_remove_reserva_lleva_lunch_and_more.py`
(ídem, histórico).

Los tests que hoy cubren `ExtrasItem`/`ReservaExtra` se reescriben contra el catálogo
unificado (mismos escenarios de negocio: brunch por persona, licencia recomendada,
carnada, cantidad editable, congelado de precio al pagar).

## Pruebas

TDD de siempre, en el orden natural de las capas:

1. **Modelo**: `clean()` de `Personalizacion` (input_seleccion necesita opciones,
   cobrar_por_persona/cantidad_editable solo en check), `clean()` de
   `ServicioPersonalizacion` (obligatorio solo en input, preseleccionado solo en
   check, precio 0 en input), `clean()` de `ReservaPersonalizacion` (respuesta vacía
   en check, formato numero/seleccion en input).
2. **Pricing**: fórmula sin auto-inclusión, congelado de precio al pagar (paquete y
   servicio suelto), `cobrar_por_persona` multiplicando bien.
3. **Serializer**: personalizaciones en servicio suelto (nuevo), bloqueo por input
   obligatorio vacío, formato de `input_numero`/`input_seleccion`, aceptación de
   recomendada explícitamente desmarcada.
4. **Admin**: `ReservaPersonalizacionInline` muestra lo esperado.
5. **Frontend**: estado inicial de recomendada/opcional, aviso al desmarcar
   (reutilizando `AmenitiesReminder`), bloqueo de submit con input obligatorio vacío,
   render de los tres subtipos de input.

Suite completa (`manage.py test apps config`) en SQLite y Postgres antes de cerrar,
como en el cierre de SP2. Frontend: `lint`, `tsc --noEmit`, `build`.

## Fuera de alcance (explícito)

- No se agrega la respuesta del input a la Agenda operativa (decisión 8).
- No se agrega ningún tipo de input adicional (fecha, archivo, etc.) — solo
  texto/número/selección.
- No se toca el checkout cruza-empresa (`paquete-checkout.tsx`/`Orden`) — hoy no tiene
  personalizaciones y esto no se lo agrega; es un checkout distinto (ver
  `2026-09-07-transporte-multi-empresa-design.md`).
- No hay migración de datos reales (nada lanzado): la migración que retira
  `ExtrasItem`/`ReservaExtra` simplemente dropea las tablas.
