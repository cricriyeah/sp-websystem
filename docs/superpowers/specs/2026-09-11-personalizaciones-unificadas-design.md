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

Una revisión adversarial de esta spec encontró que resolver esto bien para pesca
simple (el checkout más usado) obliga a retirar también `fleet.Tarifa` — ver la
sección dedicada más abajo. No es alcance añadido por gusto: sin eso, unificar los
catálogos le quita brunch/licencia/carnada al checkout de pesca sin paquete.

## Decisiones ya tomadas con el dueño

1. **Unificar los dos catálogos en uno solo** (`Personalizacion`/`ServicioPersonalizacion`).
   Se retiran `fleet.ExtrasItem` y `bookings.ReservaExtra` por completo. Nada que
   migrar: el proyecto no ha lanzado.
2. **No existe más un check 100% forzado.** El caso legal (licencia de pesca) pasa a
   ser "recomendada" (preseleccionada), con un aviso **reforzado** al desmarcar: texto
   e icono de advertencia distintos al de una recomendada normal, no solo el mismo
   modal genérico. El riesgo de que alguien la quite es una decisión de negocio ya
   aceptada por el dueño — pero el aviso reforzado necesita un mecanismo explícito
   para no depender de comparar un string libre (ver `aviso_reforzado` en el modelo).
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
9. **Pesca deportiva "legado" (sin paquete ni servicio explícito) deja de existir como
   caso especial: pasa a resolverse siempre contra un `Servicio` real**, igual que ya
   se hizo con transporte. Es la única forma de que brunch/licencia/carnada le
   apliquen: `ServicioPersonalizacion` requiere un `Servicio`, y hoy ese camino no
   tiene ninguno (usa `fleet.Tarifa` directo). `fleet.Tarifa` se retira junto con
   `ExtrasItem`/`ReservaExtra`.

## Modelo de datos

### `fleet.Personalizacion` (catálogo reutilizable, por Empresa)

Campos que se agregan:

- `tipo_interaccion` — `CharField` con choices `check`, `input_texto`, `input_numero`,
  `input_seleccion`. Default `check`.
- `opciones_seleccion` — `JSONField(default=list, blank=True)`. Lista de strings.
  Solo tiene sentido si `tipo_interaccion == input_seleccion`.
- `aviso_reforzado` — `BooleanField(default=False)`. Solo tiene sentido si
  `tipo_interaccion == check`. Marca que, al desmarcar esta personalización cuando es
  recomendada, el modal de aviso usa la variante reforzada (texto/ícono de advertencia
  distinto), en vez de la genérica. Reemplaza el `tipo == 'licencia'` hardcodeado que
  usa hoy `AmenitiesReminder` para decidir esto — un campo explícito y validado, no un
  string libre que puede escribirse mal sin que nada lo detecte.

Campos que se conservan sin cambio de forma, pero con validación nueva:

- `tipo` (bebida/licencia/carnada/otro) sigue siendo una etiqueta libre de
  agrupación visual — **eje independiente** de `tipo_interaccion` y de
  `aviso_reforzado`. Sigue sin `TextChoices` (es y seguirá siendo texto libre); no se
  usa para decidir ningún comportamiento del checkout, solo para agrupar visualmente
  si el frontend lo necesita.
- `cobrar_por_persona`, `cantidad_editable`: válidos solo si `tipo_interaccion == check`.

`clean()` nuevo:

```
if tipo_interaccion == 'input_seleccion' and not opciones_seleccion:
    error: "Las personalizaciones de selección necesitan al menos una opción."
if tipo_interaccion != 'input_seleccion' and opciones_seleccion:
    error: "Las opciones de selección solo aplican al tipo 'selección'."
if tipo_interaccion != 'check' and (cobrar_por_persona or cantidad_editable or aviso_reforzado):
    error: "'Cobrar por persona', 'cantidad editable' y 'aviso reforzado' solo aplican a personalizaciones tipo check."
if cantidad_editable and not cobrar_por_persona:
    error: "'Cantidad editable' requiere 'cobrar por persona' — no hay grupo completo del que recortar si no cobra por persona."
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

**RLS**: el rename se hace con `migrations.RenameModel` (que en Django también
renombra la tabla física vía `ALTER TABLE ... RENAME TO ...`), nunca como
drop+recreate. Postgres ata las políticas RLS al OID de la tabla, no a su nombre, así
que la política `tenancy_alcance` ya aplicada en
`apps/bookings/migrations/0032_rls_checkout_paquete.py` (sobre
`bookings_reservapaquetepersonalizacion`, vía `EXISTS` contra `reserva_id`) sigue
vigente después del rename sin necesidad de una migración RLS nueva. **La cobertura
RLS real de esta tabla hoy no vive en `tests_rls.py`**, sino en
`apps/bookings/tests_checkout_paquete.py` (clase `ReservaCheckoutPaqueteRLSTests`:
`test_empresa_b_no_ve_personalizaciones_de_empresa_a`,
`test_empresa_a_ve_sus_propias_filas`) — esos tests se renombran/actualizan al nuevo
nombre de modelo y related_name, y se les agrega el caso nuevo de servicio suelto
(antes solo se ejercitaba desde paquetes). Al dropear `ExtrasItem`/`ReservaExtra`,
Postgres elimina sus políticas RLS junto con las tablas — no hace falta una migración
de limpieza aparte, pero **`apps/tenancy/tests_rls.py:98-103`
(`test_guardarrail_toda_tabla_con_empresa_tiene_politica`) tiene una whitelist
hardcodeada por nombre de tabla que incluye literalmente `'bookings_reservaextra'` y
`'bookings_reservapaquetepersonalizacion'`** — se actualiza esa whitelist para
reflejar el rename y el drop, o el guardarraíl falla en CI señalando tablas que ya no
existen con ese nombre.

`clean()` nuevo:

```
tipo_interaccion = servicio_personalizacion.personalizacion.tipo_interaccion
if tipo_interaccion == 'check':
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

## Retiro de `fleet.Tarifa`: pesca simple pasa a ser un `Servicio` real

**Este es el hallazgo más importante de la revisión adversarial y cambia el alcance
de la spec.** `Reserva.servicio` es `null=True` con el comentario "Vacío = pesca
deportiva (legacy)" (`apps/bookings/models.py:429-432`). El flujo real de
`/reservar` **sin** `?servicio=` ni `?paquete=` (el booking bar de la portada, el
camino más usado hoy) deja `servicio=None` y resuelve el precio contra
`fleet.Tarifa` (`CrearPagoView._post`, rama `else` en torno a la línea 103). Sin
arreglar esto, la unificación **le quita brunch/licencia/carnada al checkout de
pesca simple**, que es exactamente donde más se usan hoy — una regresión
silenciosa, no una mejora.

La buena noticia: **ya existe** el `Servicio` que necesitamos. La migración
`apps/fleet/migrations/0018_crear_servicio_la_paz.py` ya creó, para la Empresa
`sal-y-sol`, un `Servicio(slug='pesca-deportiva', tipo_servicio='pesca',
estrategia_precio='por_grupo', precio_base=<el de Tarifa>, precio_persona_extra=<el
de Tarifa>, personas_incluidas=3)` — con los mismos números que tenía `Tarifa` en
ese momento. La estrategia `PorGrupo` (`apps/payments/estrategias_precio.py:99-118`)
reproduce exactamente la fórmula de `Tarifa` (precio base + recargo por persona
arriba de `personas_incluidas`) leyendo esos mismos campos, que `Servicio` ya tiene.
**No hace falta código de precio nuevo**, solo:

1. **Migración de datos** (patrón igual al de `0018`, generalizado a *todas* las
   Empresas que hoy tengan una `Tarifa`, no solo `sal-y-sol`): por cada Empresa con
   `Tarifa`, `get_or_create` un `Servicio(slug='pesca-deportiva', ...)` con esos
   valores, si no existe ya uno con ese slug para esa Empresa. **La migración también
   fija `hora_apertura=VENTANA_SALIDA_INICIO` / `hora_cierre=VENTANA_SALIDA_FIN`**
   (las constantes legacy de `apps/bookings/models.py`, hoy 5:00-7:00am) — sin esto,
   `Servicio.ventana_horaria()` devuelve `None` (sin restricción) y
   `_validar_ventana_horaria` deja de aplicar el candado horario a pesca simple en
   cuanto `servicio_id` deja de ser `None`, una regresión silenciosa en el checkout más
   usado. **El `Servicio` "pesca-deportiva" de `sal-y-sol` ya existe** (creado por
   `0018_crear_servicio_la_paz.py`, sin estos campos) — `get_or_create` no actualiza un
   registro existente vía `defaults`, así que para esa Empresa la migración nueva debe
   hacer un `update()` explícito de `hora_apertura`/`hora_cierre` sobre el `Servicio` ya
   creado, no solo `get_or_create` con `defaults`.
2. **`reservar/page.tsx`**: cuando no hay `?servicio=` ni `?paquete=` en la URL, en
   vez de llamar a `getTarifa(empresaSlug)` resuelve
   `getServicioDetalle('pesca-deportiva', empresaSlug)` — el mismo camino que ya usa
   un servicio suelto explícito, con el slug fijo como default. Se retira `getTarifa`
   de `frontend/src/lib/api.ts` y el tipo que lo acompaña.
2.1. **`checkout-view.tsx` deja de recibir/usar `tarifa`** (ya no hay caso en que
   `paquete`/`servicio` estén los dos vacíos, así que el tercer eslabón de cada
   cadena `paquete ? ... : servicio ? ... : tarifa ? ...` se elimina, no se rellena):
   - `tieneProducto` (línea 375, hoy `Boolean(tarifa || paquete || servicioId ||
     servicio)`) pasa a `Boolean(paquete || servicioId || servicio)`.
   - `usdDisponible` (568-569) y `tourPrice` (570-576) pierden su rama `tarifa` final
     (`: tarifa?.precio_usd != null` / `: tarifa ? Number(...) : null`), quedando en
     `: null` cuando no hay ni `paquete` ni `servicio` — caso que, con el punto 4 de
     abajo, ya no debería ocurrir en producción, pero el `null` de cierre se conserva
     como guardia defensiva, no se retira.
   - La misma poda aplica a cualquier otro punto de `checkout-view.tsx` que lea
     `tarifa.precio_persona_extra`/`tarifa.precio_persona_extra_usd` (línea ~671) —
     se reemplaza por `servicio.precio_persona_extra`/`precio_persona_extra_usd`
     (campos que `ServicioCatalogo` ya expone, ver `fleet.Servicio`).
3. **`CrearPagoView`**: se retira la rama `else` que resuelve `Tarifa.de(empresa)`
   (líneas ~103-119) — con el paso 2, `reserva.servicio_id` siempre viene resuelto
   para una reserva de pesca simple, así que solo queda la rama `elif
   reserva.servicio_id`.
4. **`Reserva.clean()`**: nueva regla — una Reserva debe tener `servicio_id` o
   `paquete_id` (al menos uno). Ya no es válido dejar los dos vacíos. (Una reserva de
   paquete sigue con `servicio=None` + `paquete` seteado, sin cambio ahí.)
5. Se retiran `fleet.Tarifa`, `fleet.TarifaView` (`GET /api/<empresa>/tarifa/`),
   `TarifaSerializer`, y sus usos en `apps/fleet/admin.py`,
   `apps/fleet/management/commands/seed_local_demo.py` (se reemplaza por la creación
   directa del `Servicio` "pesca-deportiva" con esos datos), `config/health.py` (si el
   health check consulta `Tarifa`, pasa a consultar el `Servicio` canónico), y
   cualquier otro de los ~33 archivos que hoy referencian `Tarifa`/`getTarifa` (correr
   `rg -n "Tarifa|getTarifa" ` antes de dar el retiro por completo — mismo caveat de
   metodología que con `ExtrasItem`).
6. **`Reserva.clean()` — efecto colateral en toda prueba/flujo que crea una Reserva
   sin `servicio`.** La regla "servicio o paquete, al menos uno" no es solo un
   candado nuevo para el checkout web: `servicio=None` es hoy la convención activa
   que usan los helpers de prueba `datos_reserva`/`crear_reserva` en
   `apps/bookings/tests.py`, `apps/bookings/tests_tenancy.py`,
   `apps/bookings/tests_cupo_rango.py`, `apps/bookings/tests_concurrencia.py`,
   `apps/payments/tests.py`, `apps/finance/tests.py` y `apps/notifications/tests.py`
   — ninguno de ellos sobre personalizaciones, todos con `.full_clean()`. Esta
   búsqueda **no** la cubre el grep de `Tarifa|getTarifa` ni el de
   `extras_seleccionados|...`: es un efecto transversal de la nueva regla de
   `clean()`, no del retiro de un modelo. Antes de aplicar la regla, cada uno de
   esos helpers debe pasar un `servicio` (una fixture compartida al `Servicio`
   "pesca-deportiva" de la Empresa de prueba, creada una vez por `setUp`/`TestCase`).
7. **`ReservaAdmin` no restringe `servicio`** — hoy una vendedora puede crear a mano
   una reserva de pesca por WhatsApp dejando `servicio` en blanco (confía en el
   default legacy). Con la regla nueva, eso empieza a fallar con un error de
   validación. Se agrega un default al formulario del admin (`servicio` inicializado
   al `Servicio` "pesca-deportiva" de la Empresa activa al abrir el formulario de
   alta) para que el flujo manual siga funcionando sin que la vendedora tenga que
   aprender a elegirlo.

No hay usuarios reales de `/reservar` sin parámetros que perder: es exactamente el
mismo Servicio de pesca que ya se ofrece explícitamente por catálogo, solo que ahora
también es el default cuando no se especifica nada.

**Orden de despliegue**: backend (Render) y frontend (Vercel) se despliegan por
separado. La regla nueva de `Reserva.clean()` (punto 4: servicio o paquete, al menos
uno) y el cambio de `reservar/page.tsx` (punto 2: deja de mandar los dos vacíos) son
un solo cambio atómico de negocio aunque vivan en repos/servicios distintos — si el
backend llega a producción antes que el frontend, todo `POST /api/reservas/` de pesca
simple (el checkout más usado) devuelve 400 hasta que el segundo deploy alcance. Se
despliega primero el frontend (que ya deja de mandar la combinación vacía) y se
verifica un ciclo de reservas real antes de desplegar el backend con la regla de
`clean()` activa — nunca al revés.

## Precio y congelado (corrige una inconsistencia existente)

Hoy `ExtrasItem` congela precio al pagar (`CrearPagoView._resolver_extras` escribe
`precio_unitario`/`cantidad` en `ReservaExtra` en el momento de `crear-pago`), pero
`ServicioPersonalizacion` en un paquete **no** — `precio_paquete_total` relee el precio
vigente del catálogo cada vez, incluso en `CrearPagoView`. Es una inconsistencia que se
corrige como parte de esta unificación: **todo el catálogo unificado congela precio al
pagar**, con el mismo patrón que ya usa `ExtrasItem` hoy.

Cambios en `ReservaPersonalizacion`:

- Se agrega un único campo `precio_unitario` (`DecimalField(null=True, blank=True)`),
  mismo patrón exacto que `ReservaExtra.precio_unitario` hoy — sin campo de moneda
  propio, porque `Reserva.moneda` ya fija la moneda del cobro completo, igual que pasa
  con `ReservaExtra`. `null` mientras la reserva sigue `pendiente_pago`; solo
  `CrearPagoView` lo llena, con el precio vigente de `ServicioPersonalizacion` en ese
  momento.
- Se agrega la property `subtotal` (`precio_unitario * cantidad`, `None` si
  `precio_unitario` es `None`), igual que `ReservaExtra.subtotal` hoy — la usa
  `EstadoReservaView` y el admin para mostrar el monto real cobrado, no el precio
  unitario suelto.

Cambios en `pricing.py`:

- Se retira la auto-inclusión `es_incluida = sp.obligatorio or sp.preseleccionado` de
  `precio_paquete_total`. El total se arma **únicamente** con las filas
  `ReservaPersonalizacion` que existen para la Reserva — recomendada y opcional pesan
  igual en el cálculo; la única diferencia entre ambas es el estado inicial del
  checkbox en el frontend (ver más abajo) y el aviso al desmarcar.
- **Se unifica también la fórmula de cantidad, porque hoy los dos catálogos calculan
  distinto y combinarlos tal cual cobraría doble.** `precio_paquete_total` hoy
  multiplica `mult` (personas, si `cobrar_por_persona`) **por** `cant` (la cantidad
  elegida por el cliente, si el ítem viene en el payload) — dos factores
  independientes. `cargo_por_extra`/`_resolver_extras` (el catálogo legacy) usa **una
  sola** cantidad: el grupo completo, o el valor recortado que el cliente eligió si
  `cantidad_editable` (`min(cantidad_solicitada, numero_personas)`) — nunca los dos
  multiplicados. La fórmula unificada adopta la semántica legacy (una sola cantidad,
  no dos factores):

  ```
  cantidad_efectiva =
      cantidad_editable
          ? max(1, min(cantidad_solicitada_del_cliente, numero_personas))
          : (cobrar_por_persona ? numero_personas : 1)

  cargo = sp.precio_en(moneda) * cantidad_efectiva
  ```

  `cantidad_editable=True` sin `cobrar_por_persona=True` no tiene sentido de negocio
  (no hay "grupo completo" del que recortar) y ya lo prohíbe la relación entre esos
  dos campos tal como se usan hoy (ver `ExtrasItem.cantidad_editable`, mismo supuesto).
  Se agrega esa combinación a las validaciones de `clean()` de `Personalizacion`:
  `cantidad_editable` requiere `cobrar_por_persona=True`.
- Se generaliza `precio_paquete_total` (o se agrega una función hermana) para que
  funcione también sobre una Reserva de servicio suelto, no solo de paquete: el total
  es `precio_base_del_servicio_o_paquete + Σ cargo (fórmula de arriba) de las
  ServicioPersonalizacion tipo check seleccionadas` (los `input_*` nunca suman,
  siempre validado en `clean()` a precio 0).
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
  de volver a marcarlas o continuar sin ellas. Las que tienen `aviso_reforzado=true`
  van en su propia sección del modal (mismo lugar donde hoy `AmenitiesReminder` separa
  "necesarios" de "opcionales", pero la condición deja de ser `tipo === 'licencia'` y
  pasa a ser el campo `aviso_reforzado` que trae cada `ServicioPersonalizacion`), con
  copy y estilo de advertencia más fuertes que las demás recomendadas.
- Un `check` con `cantidad_editable=true` (ej. "¿cuántos del grupo ya traen su propia
  licencia?") muestra un stepper numérico junto al checkbox, de 1 a `numero_personas`,
  con el mismo control +/- que ya existe hoy para extras (`ajustarCantidadExtra`/
  `cantidadDeExtra` en `checkout-view.tsx`) — se porta esa lógica al nuevo bloque
  unificado, generalizada a operar por `ServicioPersonalizacion.id` en vez de por
  `ExtrasItem.id`. Un `check` sin `cantidad_editable` no muestra stepper (aplica a todo
  el grupo, como hoy).
- Los `input_texto`/`input_numero`/`input_seleccion` se pintan como campo de texto,
  `<input type="number">`, o `<select>` con `opciones_seleccion`, en el mismo bloque de
  "Personalizaciones". Los obligatorios muestran un asterisco.
- **Validación de inputs obligatorios**: esto es plomería nueva, no una reutilización
  del mecanismo de contacto existente. Hoy `erroresCampo`/`CampoContacto`/
  `ORDEN_CAMPOS` son una unión cerrada de tres campos fijos (`fullName`, `phone`,
  `email`) con un arreglo de foco fijo — no sirve tal cual para una lista de
  personalizaciones cuyo tamaño y contenido dependen del Paquete/Servicio en tiempo de
  ejecución. Se agrega un estado de errores propio, indexado por
  `ServicioPersonalizacion.id` (p. ej. `erroresPersonalizacion: Record<number,
  string>`), calculado al intentar avanzar/pagar: cualquier input obligatorio sin
  `respuesta` no vacía se marca ahí, se hace scroll/foco al primero en orden de
  aparición en el bloque de personalizaciones (mismo patrón de "primero en foco" que
  `ORDEN_CAMPOS`, pero sobre un arreglo dinámico), y el submit no sale mientras existan
  entradas en ese estado.
- Este bloque deja de estar condicionado a `paquete`: aparece también cuando
  `servicio` está seteado directamente — pesca (ahora siempre vía el `Servicio`
  "pesca-deportiva", ver más arriba) y cualquier otro servicio suelto con
  `ServicioPersonalizacion` asociadas. **Transporte no es un caso especial**: es un
  `Servicio` como cualquier otro (`tipo_servicio='transporte'`) y el mecanismo le
  aplica igual de forma genérica. Lo que sí queda fuera de esta pasada es cablear su
  checkout concreto: `TrasladoCheckoutSerializer`
  (`apps/bookings/serializers.py:395-469`, subclase con su propio `Meta.fields` sin
  `personalizaciones` y su propio `create`/`_guardar_traslado`) y
  `frontend/src/components/traslado-view.tsx` no se tocan aquí porque nadie pidió
  personalizaciones para traslados todavía y hoy no tienen ninguna — no hay
  regresión al dejarlos fuera. Cuando se pida, es el mismo mecanismo genérico, no uno
  nuevo.
- `AmenitiesReminder` (y su tipo `ExtraPendiente`) se generaliza para trabajar sobre
  `ServicioPersonalizacion`/`Personalizacion` en vez de `ExtrasItem` — mismo
  componente, nueva fuente de datos, con `aviso_reforzado` reemplazando la comparación
  `tipo === 'licencia'` que separa sus dos secciones.

## Recuperación de checkout (`EstadoReservaView`)

`GET /api/<empresa>/estado-reserva/` (`apps/payments/views.py`, clase
`EstadoReservaView`) tiene dos ramas que leen `reserva.extras_seleccionados` y se
rompen (`AttributeError`) en cuanto `ReservaExtra` desaparece — no es un dato que
quede desactualizado, es un endpoint que revienta:

- Rama `pagada` (línea ~352): expone `extras` con `nombre`, `cobrar_por_persona`,
  `monto` (usa `extra.subtotal`, ya congelado) y `cantidad`, para la pantalla de
  confirmación tras el pago.
- Rama `pendiente_pago` (línea ~380): expone `extras` con `id`/`cantidad` (usa
  `cantidad_solicitada`, sin congelar todavía), para reanudar un checkout abandonado
  a medio llenar.

Ambas se reescriben contra `reserva.personalizaciones_seleccionadas` (el nuevo
`related_name`), cambiando la clave de la respuesta de `extras` a
`personalizaciones`:

- `pagada`: por cada `ReservaPersonalizacion`, `{ nombre, tipo_interaccion, monto,
  cantidad, respuesta }`, donde `monto = precio_unitario * cantidad` (igual que
  `ReservaExtra.subtotal` hoy — `apps/bookings/models.py`, no el precio unitario
  suelto: reportar solo `precio_unitario` subestima el cobro real de un check
  `cobrar_por_persona` con `cantidad > 1`). Se agrega una property `subtotal` a
  `ReservaPersonalizacion` que replique `ReservaExtra.subtotal` (`None` si
  `precio_unitario` es `None`, o si la fila es de tipo input). `null` para filas de
  tipo input.
- `pendiente_pago`: por cada `ReservaPersonalizacion`, `{ id (del
  ServicioPersonalizacion), cantidad, respuesta }` — sin precio, porque aún no se
  congela.

En el frontend, `frontend/src/lib/api.ts` (tipos `EstadoReservaPendiente.extras` /
`EstadoReservaPagada.extras`) y `checkout-view.tsx` (`recuperadoExtras`,
`lineasExtrasRecuperadas`, y la restauración de `extrasSeleccionados`/
`cantidadesExtras` al reanudar un checkout) se actualizan para leer
`personalizaciones` con esta forma nueva, incluyendo restaurar la `respuesta` de
cualquier input que el cliente ya había llenado antes de abandonar el checkout.

## Admin

Hoy no existe ningún inline para `ReservaPaquetePersonalizacion` en `ReservaAdmin` —
se agrega `ReservaPersonalizacionInline` (solo lectura, mismo criterio que
`ReservaExtraInline`: es historial de lo que se congeló al pagar) mostrando
`servicio_personalizacion`, `cantidad`, `respuesta`, `precio_unitario`. Reemplaza a
`ReservaExtraInline` (que se elimina junto con `ExtrasItem`/`ReservaExtra`).

## Migración de datos: catálogo real de `ExtrasItem`

`seed_extras.py` no es solo un script de demo: su docstring dice explícitamente que
corre una vez por Empresa **en producción**, sembrando brunch/licencia/carnada con
precios *placeholder* que el dueño reemplaza a mano en el admin. Esos precios reales
ya capturados no se pierden: la migración que dropea `ExtrasItem`/`ReservaExtra`
incluye un paso previo de **migración de datos** (no solo de esquema) que, por cada
`ExtrasItem` existente, crea su `Personalizacion`/`ServicioPersonalizacion`
equivalente preservando `nombre`, `precio`/`precio_usd`, `tipo`,
`cobrar_por_persona`, `cantidad_editable`, y fijando `preseleccionado=True` +
`aviso_reforzado=True` para el que tenga `tipo == 'licencia'` (mismo criterio que la
decisión 2). Se corre y se verifica **antes** de dropear las tablas viejas en el mismo
despliegue. `seed_extras.py` se reescribe para el caso de una Empresa nueva sin
`ExtrasItem` previos (demo o alta real); no vuelve a correr sobre una Empresa que ya
tuvo su migración de datos.

## Semilla (`seed_extras.py`)

Se reescribe para crear, sobre el Servicio de pesca de la Empresa demo:

- `Personalizacion` "Brunch" (`tipo=brunch`, `tipo_interaccion=check`,
  `cobrar_por_persona=True`), `ServicioPersonalizacion(preseleccionado=False)`.
- `Personalizacion` "Licencia de pesca" (`tipo=licencia`, `tipo_interaccion=check`,
  `aviso_reforzado=True`), `ServicioPersonalizacion(preseleccionado=True)` —
  recomendada con aviso reforzado, ya no forzada.
- `Personalizacion` "Carnada" (`tipo=carnada`, `tipo_interaccion=check`),
  `ServicioPersonalizacion(preseleccionado=True)`.

Mismo criterio de idempotencia que tiene hoy (`get_or_create` por nombre/empresa).

## Inventario de archivos backend afectados

La búsqueda por nombre de clase (`ReservaExtra`/`ExtrasItem`) da 17 archivos, pero esa
búsqueda **subcuenta** los archivos que solo acceden a los datos por el nombre del
manager relacionado (`extras_seleccionados`, `paquete_personalizaciones`) o por
función auxiliar (`_resolver_extras`), sin mencionar la clase. Antes de dar el
inventario por cerrado en la fase de implementación, correr también:
`rg -n "extras_seleccionados|paquete_personalizaciones|_resolver_extras|cargo_por_extra"`.

Confirmado por esa segunda búsqueda: **`apps/payments/views.py`** (contiene
`CrearPagoView._resolver_extras`, que esta spec requiere reescribir en la sección
"Precio y congelado") no aparece en la lista original y debe añadirse explícitamente.

Esa misma búsqueda encuentra un segundo archivo fuera de la lista original, más grave
porque no es un test: **`apps/notifications/services.py:91`** —
`_cuerpo_html()` itera `reserva.extras_seleccionados.select_related('extras_item')`
para armar el desglose de brunch/licencia/carnada del correo de confirmación. Esa
llamada queda **fuera** del único `try/except` de la función (que solo atrapa el POST
a Resend), y `notificar_reserva_pagada()` documenta "nunca lanza" pero evalúa
`enviar_correo_confirmacion` antes que `enviar_whatsapp_confirmacion` — si el primero
lanza `AttributeError` en cuanto `ReservaExtra` se elimine, el segundo nunca se
ejecuta. El webhook de pago atrapa la excepción con un `except Exception` genérico y
responde 200 igual, así que la falla es silenciosa: **toda reserva pagada con éxito
dejaría de mandar correo Y WhatsApp de confirmación**, sin que ningún test lo
detecte. Se reescribe `_cuerpo_html` contra `reserva.personalizaciones_seleccionadas`
(el nuevo `related_name`), filtrando a las filas de tipo `check` (las de tipo `input_*`
no tienen precio ni pertenecen al desglose de cobro); se agrega un test en
`apps/notifications/tests.py` que cubra explícitamente una reserva con
personalizaciones tipo check para el correo de confirmación (hoy ese archivo solo
aparece en la lista base por referenciar la clase, no por tener este escenario).

Lista base (17, por nombre de clase): `apps/bookings/admin.py`,
`apps/notifications/tests.py`, `apps/payments/tests.py`, `apps/bookings/tests.py`,
`apps/bookings/models.py`, `apps/fleet/models.py`, `apps/payments/pricing.py`,
`apps/bookings/serializers.py`, `apps/fleet/tests.py`, `apps/fleet/views.py`,
`apps/fleet/admin.py`, `apps/bookings/tests_tenancy.py`,
`apps/fleet/management/commands/seed_extras.py`, `apps/fleet/serializers.py`,
`apps/fleet/migrations/0013_backfill_empresa.py` (histórico, no se toca — las
migraciones viejas se quedan, la eliminación es una migración nueva),
`apps/fleet/migrations/0008_extrasitem_puntoencuentro_transporteprecio.py` (ídem,
histórico), `apps/bookings/migrations/0018_remove_reserva_lleva_lunch_and_more.py`
(ídem, histórico). Más `apps/payments/views.py` y `apps/notifications/services.py`
(confirmados arriba).

**Inventario del rename `ReservaPaquetePersonalizacion` → `ReservaPersonalizacion`**
(búsqueda por nombre de clase, aparte de la anterior): además de los archivos ya
tocados por el retiro de `ExtrasItem`, el rename afecta a
`apps/bookings/tests_checkout_paquete.py` (import + ~9 usos directos de
`ReservaPaquetePersonalizacion.objects.create/count` y de
`reserva.paquete_personalizaciones`, incluida la clase RLS mencionada arriba),
`apps/bookings/tests_checkout_serializer.py` (import + usos de
`reserva.paquete_personalizaciones`), y `apps/tenancy/tests_rls.py` (whitelist
hardcodeada, ver sección "RLS" arriba).

Los tests que hoy cubren `ExtrasItem`/`ReservaExtra` se reescriben contra el catálogo
unificado (mismos escenarios de negocio: brunch por persona, licencia recomendada,
carnada, cantidad editable, congelado de precio al pagar).

## Pruebas

TDD de siempre, en el orden natural de las capas:

1. **Modelo**: `clean()` de `Personalizacion` (input_seleccion necesita opciones,
   cobrar_por_persona/cantidad_editable/aviso_reforzado solo en check), `clean()` de
   `ServicioPersonalizacion` (obligatorio solo en input, preseleccionado solo en
   check, precio 0 en input), `clean()` de `ReservaPersonalizacion` (respuesta vacía
   en check, formato numero/seleccion en input).
1.5. **RLS** (`tests_rls.py`, Postgres): la política `tenancy_alcance` de
   `bookings_reservapersonalizacion` (renombrada) sigue aislando por empresa después
   del rename, para el caso paquete (como ya se probaba) y para el caso servicio
   suelto (nuevo).
2. **Pricing**: fórmula sin auto-inclusión, congelado de precio al pagar (paquete y
   servicio suelto), `cobrar_por_persona` multiplicando bien.
3. **Serializer**: personalizaciones en servicio suelto (nuevo), bloqueo por input
   obligatorio vacío, formato de `input_numero`/`input_seleccion`, aceptación de
   recomendada explícitamente desmarcada.
4. **Admin**: `ReservaPersonalizacionInline` muestra lo esperado.
5. **Migración pesca→Servicio**: la migración de datos crea/reutiliza el `Servicio`
   "pesca-deportiva" por Empresa con los valores de `Tarifa`; `CrearPagoView` sin la
   rama `Tarifa` cobra igual que antes para una reserva de pesca simple (incluida la
   fórmula unificada de `cobrar_por_persona`/`cantidad_editable`);
   `Reserva.clean()` rechaza una reserva sin `servicio` ni `paquete`; los helpers de
   construcción de Reserva en los siete archivos listados arriba (`datos_reserva`/
   `crear_reserva` en la mayoría; `_datos` en `apps/bookings/tests_concurrencia.py`,
   que no sigue ese mismo nombre) pasan a usar una fixture compartida de `Servicio`
   pesca en vez de dejarlo implícito, incluyendo fijar una ventana horaria explícita
   en esa fixture para no perder cobertura de `VentanaSalidaTests` (ver la migración
   de `hora_apertura`/`hora_cierre` más arriba);
   `ReservaAdmin` sigue permitiendo alta manual sin fricción con el default nuevo.
6. **Recuperación de checkout**: `EstadoReservaView` en `pendiente_pago` y en
   `pagada` reporta `personalizaciones` (checks y respuestas de input) en vez de
   `extras`, para pesca simple y para paquete.
7. **Frontend**: estado inicial de recomendada/opcional, aviso al desmarcar
   (reutilizando `AmenitiesReminder`, con la sección de `aviso_reforzado`), stepper de
   cantidad, bloqueo de submit con input obligatorio vacío, render de los tres
   subtipos de input, reanudación de checkout restaurando `respuesta`.

Suite completa (`manage.py test apps config`) en SQLite y Postgres antes de cerrar,
como en el cierre de SP2. Frontend: `lint`, `tsc --noEmit`, `build`.

## Fuera de alcance (explícito)

- No se agrega la respuesta del input a la Agenda operativa (decisión 8).
- No se agrega ningún tipo de input adicional (fecha, archivo, etc.) — solo
  texto/número/selección.
- No se toca el checkout cruza-empresa (`paquete-checkout.tsx`/`Orden`) — hoy no tiene
  personalizaciones y esto no se lo agrega; es un checkout distinto (ver
  `2026-09-07-transporte-multi-empresa-design.md`).
- No se cablea `TrasladoCheckoutSerializer`/`traslado-view.tsx` — transporte es un
  `Servicio` genérico y el mecanismo ya le aplica, pero nadie pidió personalizaciones
  ahí todavía y hoy no tiene ninguna (no es una limitación de diseño, es que no se
  pidió).
- No hay migración de datos reales de negocio (nada lanzado): las migraciones que
  retiran `ExtrasItem`/`ReservaExtra`/`Tarifa` dropean tablas o mueven configuración
  de precio ya existente a `Servicio` — no hay reservas ni pagos reales que
  preservar.
