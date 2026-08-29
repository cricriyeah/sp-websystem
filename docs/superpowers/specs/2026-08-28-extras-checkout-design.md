# Extras del checkout: Brunch, Transporte, Licencia, Carnada

Fecha: 2026-08-28
Origen: spec técnica propuesta por otro chat de Claude, revisada contra el código
y el negocio real antes de aprobarse. Las secciones "Correcciones sobre la
propuesta original" documentan en qué cambió y por qué.

## El problema

Hoy el checkout solo vende un extra en línea: el lunch (precio fijo por
persona, en `Tarifa`). Bebidas y transporte se piden como intención
(`pide_bebidas`, `pide_transporte`, dos booleanos en `Reserva`) y el agente los
cotiza aparte por WhatsApp, porque su precio depende de datos que no se sabían
al reservar (tipo de bebida, distancia del traslado). Licencia de pesca y
carnada ni siquiera están en el sistema — se cotizan enteras por WhatsApp
(`docs/contexto-negocio.md`, sección Servicio).

El negocio quiere vender los cuatro en el checkout con precio fijo, editable
sin tocar código: **transporte** (resuelto por zona en vez de distancia, para
no depender de geocoding), **licencia** y **carnada** (nuevos, con precio que
cambia por temporada), y renombrar **lunch → brunch** (mismo concepto, texto
nuevo).

## Decisiones de negocio (confirmadas con el usuario, 28 de agosto de 2026)

- **Transporte, licencia y carnada pasan a venderse en el checkout con precio
  fijo.** Dejan de cotizarse por WhatsApp. Esto es un cambio de modelo de
  negocio, no solo técnico, y el usuario lo confirmó explícitamente — la spec
  original lo daba por hecho sin haberlo preguntado.
- **Bebidas queda fuera de esta pieza.** Sigue como está: `pide_bebidas`,
  intención que el agente cotiza aparte. Su precio depende del tipo de bebida,
  no de una zona o de personas, así que no tiene el mismo arreglo que
  transporte.
- **Los precios de transporte que trae la spec original son reales**: 2000
  MXN centro / 1800 MXN periferia, recargo de 1500 MXN desde 4 personas. Se lo
  dio al usuario la persona encargada de los transportes.
- **Todo necesita precio en USD**, igual que el resto del sistema (`Tarifa`
  lleva `precio`/`precio_usd` en cada campo). Se me pasó en la spec original.
  Los montos en USD de transporte, licencia y carnada no los tiene el usuario
  todavía — se seedean en `null` (= "no se ofrece en USD hasta que un jefe lo
  edite en el admin"), mismo significado que ya tiene `precio_usd` en
  `Tarifa`.
- **Modelo de datos: catálogo genérico, no flags nuevos.** El usuario espera
  agregar más extras a futuro y probablemente expandir a más localidades con
  otros servicios (ver `[[plan-expansion-multi-empresa]]`, trabajo futuro, no
  arranca todavía). Un catálogo (`ExtrasItem`) escala mejor que seguir
  agregando booleanos a `Reserva` cada vez que se vende algo nuevo. El lunch
  se migra al mismo catálogo en vez de quedar como el único flag suelto — ver
  "Qué pasa con `lleva_lunch`" más abajo.
- **No se agrega `empresa_id` ni ningún aislamiento multi-negocio en esta
  pieza.** La expansión a 3 empresas es trabajo futuro que explícitamente no
  ha arrancado (`[[plan-expansion-multi-empresa]]`: "no se empieza hasta
  terminar de deployar lo que está en curso ahora"). Diseñar para esa
  expansión ahora sería adelantarse a una decisión que ni siquiera está
  cerrada (sigue pendiente elegir entre FK `empresa_id` o schema separado).
- **Seguir ahora, no esperar al lanzamiento.** `[[cola-de-trabajo]]` decía que
  lo natural era lanzar antes de más feature; el usuario decidió meter esta
  pieza primero de todas formas.

## Correcciones sobre la propuesta original

La spec que trajo el usuario venía de otro chat sin ver el código ni
`docs/contexto-negocio.md`. Contradecía trabajo ya deliberado y traía huecos:

1. **No sabía que transporte/bebidas sin cobro en línea fue decisión
   consciente**, documentada en el docstring de
   `apps/payments/pricing.py`. No estaba mal revertirla — solo que hacía
   falta preguntar, no asumir.
2. **Le faltaba USD por completo.** Cada tabla de precios de la propuesta
   traía un solo campo `precio`.
3. **Pedía el número de personas de transporte por separado**, en vez de
   reusar `Reserva.numero_personas` (el mismo tope `MAX_PERSONAS = 5` que ya
   valida todo el sistema). Dos campos con el mismo dato es la manera clásica
   de que dejen de coincidir.
4. **Traía una tabla de histórico de precios por vigencia**
   (`extras_items_precios_historico`) que el propio sistema no necesita: el
   patrón ya establecido (`Tarifa`, y el propio `reserva_transporte` de la
   spec original) es editar el precio vigente a mano y dejar que cada reserva
   guarde su propio snapshot al pagar. Fechas de vigencia son una solución a
   un problema que el snapshot por reserva ya resuelve.
5. **La función de cálculo la ponía en un módulo aparte.**
   `backend/CLAUDE.md`: *"todo el cálculo de dinero vive en
   `apps/payments/pricing.py`, en un solo lugar"* — es la garantía más
   delicada del sistema y no se parte.
6. **No decía si licencia/carnada se cobran por persona o por reserva.**
   Ver la decisión de diseño más abajo (`cobrar_por_persona`).
7. **No mencionaba permisos de la vendedora** para los catálogos nuevos. Ya
   pasó una vez (la agenda quedó invisible para ella hasta que alguien se
   acordó de `setup_roles`).
8. **Trataba el renombre Lunch→Brunch como una línea de copy.** Es campo de
   modelo, dos claves de API, un componente de frontend completo
   (`amenities-reminder.tsx`) y una migración.

## Qué pasa con `lleva_lunch`

Se elimina el booleano y se migra a una fila de `ExtrasItem` (`tipo='brunch'`,
`cobrar_por_persona=True`, precio = lo que hoy vive en
`Tarifa.precio_lunch`/`precio_lunch_usd`). Motivo: si brunch se queda como
flag suelto y todo lo demás es catálogo, quedan dos sistemas de extras
conviviendo por ningún motivo — el propio caso de uso que justifica el
catálogo (agregar más extras sin tocar modelo) se rompe el mismo día que se
implementa.

`pide_bebidas` **no** se toca: sigue siendo un booleano de intención en
`Reserva`, fuera del alcance de esta pieza.

`pide_transporte` se elimina como booleano: pasa a ser un hecho derivado de
si existe `ReservaTransporte` para esa reserva (`hasattr(reserva,
'transporte')`), porque ahora es una relación real con datos, no solo una
intención.

**Esta pieza vende extras solo por el checkout web.** `ReservaExtra`/
`ReservaTransporte` con precio congelado solo los escribe `CrearPagoView`,
que exige `checkout_id` — la misma guarda que ya existe hoy y que
deliberadamente excluye a las reservas que crea la vendedora por WhatsApp o
teléfono (`canal_origen != 'web'`). Extender el catálogo con precio
congelado al canal de la vendedora es un segundo mecanismo de cobro
(¿quién congela el precio ahí? ¿con qué permiso?) que esta pieza no
resuelve — es una decisión de negocio aparte, no una consecuencia obvia de
esta.

Para no perder la capacidad operativa que ya tiene la vendedora hoy
(anotar que un cliente de WhatsApp quiere algo y cotizarlo/cobrarlo aparte,
en efectivo), se agrega `Reserva.pide_extras_whatsapp` — un booleano
simple, mismo trato que `pide_bebidas`, editable en el admin, sin
selección de catálogo ni precio congelado. `Reserva.tiene_cotizaciones_pendientes`
(hoy `pide_bebidas or pide_transporte`) pasa a `pide_bebidas or
pide_extras_whatsapp`.

**`Tarifa.precio_lunch`/`precio_lunch_usd`/`lunch_en()` se retiran en la
misma pieza**, junto con esos dos campos en `TarifaSerializer` y la
aserción sobre ellos en `apps/fleet/tests.py`. Dejarlos vivos sería
exactamente el "dos sistemas de extras conviviendo" que este cambio existe
para evitar: alguien edita el precio del brunch en `Tarifa` (donde llevaba
meses editándolo) y el checkout, que ya lee de `ExtrasItem`, no se entera.
El retiro va **después** de que la migración de sembrado de `ExtrasItem` ya
haya leído esos campos para copiar el precio (ver Migraciones).

**El nombre de la relación importa**: `ReservaExtra.reserva` usa
`related_name='extras_seleccionados'`, no `'extras'` — `ReservaAdmin` ya
tiene un método de columna llamado `extras()` para
`tiene_cotizaciones_pendientes`, y darle el mismo nombre a la relación
inversa los dejaría indistinguibles a tres líneas de distancia.

`ReservaAdmin.list_filter` pierde `'lleva_lunch'` y `'pide_transporte'`
(un filtro sobre un campo que no existe es `admin.E116`, error de chequeo
de sistema — rompe `manage.py makemigrations`/`migrate`, no solo el admin
en el navegador) y su método de columna `extras()` pasa a listar
`obj.extras_seleccionados.all()` en vez de leer los booleanos viejos. Este
ajuste va en el mismo cambio que quita los campos de `Reserva`, no antes ni
después: un `admin.py` que todavía referencia campos borrados rompe
cualquier comando de Django, incluido el que genera la migración.

## Modelo de datos

### `fleet.ExtrasItem` (catálogo, editable solo por jefes — mismo patrón que
`fleet.Tarifa`: sin permisos para el grupo Vendedora)

| Campo | Tipo | Notas |
|---|---|---|
| id | PK | |
| tipo | `CharField` choices: `brunch`, `licencia`, `carnada`, `otro` | |
| nombre | `CharField` | |
| descripcion | `TextField`, blank | |
| precio | `DecimalField(10,2)` | MXN |
| precio_usd | `DecimalField(10,2)` null/blank | igual que `Tarifa.precio_usd`: vacío = no se ofrece en USD |
| cobrar_por_persona | `BooleanField` default True | brunch y licencia en True; carnada probablemente False (se compra para la panga, no por cabeza) — **queda editable, no hardcodeado, porque no hay certeza de negocio sobre carnada; ver Riesgos** |
| preseleccionado | `BooleanField` default False | True para licencia y carnada al seedear |
| activo | `BooleanField` default True | |

Sin fechas de vigencia (ver corrección 4). Cambiar el precio por temporada es
editar `precio`/`precio_usd` directo, igual que ya se hace con `Tarifa`.

```python
def precio_en(self, moneda):
    return self.precio if moneda == 'MXN' else self.precio_usd
```

### `fleet.TransportePrecio` (catálogo, 2 filas fijas: centro y periferia)

| Campo | Tipo | Notas |
|---|---|---|
| id | PK | |
| zona | `CharField` choices: `centro`, `periferia`, unique | |
| precio_base | `DecimalField(10,2)` | 2000 centro / 1800 periferia, MXN |
| precio_base_usd | `DecimalField(10,2)` null/blank | |
| recargo_grupo | `DecimalField(10,2)` default 0 | 1500 MXN |
| recargo_grupo_usd | `DecimalField(10,2)` null/blank | |
| min_personas_recargo | `PositiveSmallIntegerField` default 4 | |
| activo | `BooleanField` default True | |

### `fleet.PuntoEncuentro` (catálogo de hoteles conocidos en La Paz)

| Campo | Tipo | Notas |
|---|---|---|
| id | PK | |
| nombre | `CharField` | ej. "Hotel CostaBaja" |
| zona | `CharField` choices: `centro`, `periferia` | |
| activo | `BooleanField` default True | |

### `bookings.ReservaExtra` (detalle: qué extras del catálogo eligió cada
reserva, con el precio congelado al momento de pagar)

| Campo | Tipo | Notas |
|---|---|---|
| id | PK | |
| reserva | FK a `Reserva`, `related_name='extras_seleccionados'`, `on_delete=CASCADE` | vive y muere con la reserva. Nombre distinto a secas `extras` a propósito: no choca con `ReservaAdmin.extras()`, el método de columna que ya existe |
| extras_item | FK a `fleet.ExtrasItem`, `on_delete=PROTECT` | igual que `embarcacion`/`capitan`: no se puede borrar un item con historial |
| precio_unitario | `DecimalField(10,2)`, null/blank | `null` mientras la reserva sigue `pendiente_pago` — es selección, no cobro todavía. `CrearPagoView` lo llena al pagar, con el precio vigente en ese momento, y es el único que lo escribe |
| cantidad | `PositiveSmallIntegerField`, null/blank | mismo criterio: `null` hasta pagar. `CrearPagoView` lo llena con `numero_personas` de la reserva si `cobrar_por_persona`, si no 1 |
| `Meta.unique_together` | `('reserva', 'extras_item')` | no tiene sentido elegir el mismo item dos veces |

`subtotal` = `precio_unitario * cantidad` si los dos están puestos, si no
`None` (siguen sin precio mientras la reserva es `pendiente_pago` — no es un
0, es "todavía no se sabe"). El inline de solo lectura en `ReservaAdmin`
muestra "—" cuando es `None`, para no reventar al abrir una reserva
abandonada con extras seleccionados.

### `bookings.ReservaTransporte` (detalle: transporte de una reserva)

| Campo | Tipo | Notas |
|---|---|---|
| id | PK | |
| reserva | `OneToOneField` a `Reserva`, `related_name='transporte'`, `on_delete=CASCADE` | |
| punto_encuentro | FK a `fleet.PuntoEncuentro`, null/blank, `on_delete=PROTECT` | null si el cliente escribió dirección propia |
| direccion_personalizada | `CharField`, blank | solo si no eligió del catálogo |
| zona | `CharField` choices `centro`/`periferia` | snapshot explícito: viene del catálogo o lo elige el cliente, pero siempre queda aquí. Se guarda en cuanto el cliente elige, no espera al pago |
| numero_personas | `PositiveSmallIntegerField`, null/blank | `null` hasta pagar. `CrearPagoView` lo llena con `reserva.numero_personas` al momento de pagar — **no** un campo que el cliente llena aparte (corrección 3) |
| precio_calculado | `DecimalField(10,2)`, null/blank | `null` hasta pagar; lo llena `CrearPagoView`, único que lo escribe |

`ReservaTransporte.clean()`: exige `punto_encuentro` o
`direccion_personalizada`, nunca los dos vacíos ni los dos con valor —
una reserva sin ninguno de los dos es un traslado pagado que nadie sabe
dónde recoger.

**`zona` no se puede falsificar cuando viene de un hotel del catálogo.**
Si el cliente eligió `punto_encuentro`, el serializer ignora cualquier
`zona` que venga en el cuerpo de la petición y usa
`punto_encuentro.zona` — si no, alguien podría elegir un hotel de centro
(2000 MXN) y mandar `zona=periferia` (1800 MXN) y pagar el precio
equivocado, porque `zona` es justo el dato que decide qué fila de
`TransportePrecio` se cobra. `ReservaTransporte.clean()` además rechaza
guardar si `punto_encuentro` está puesto y `zona` no coincide con
`punto_encuentro.zona` (defensa en el modelo, no solo en el serializer).
Solo cuando el cliente usa "otra dirección" `zona` es un dato que él
elige de verdad — ahí no hay forma de validarla contra nada, es un
riesgo que se acepta (ver Riesgos).

**Los catálogos que puede elegir el cliente se filtran a `activo=True`**
en el serializer (el `queryset` de los campos de `ExtrasItem` y
`PuntoEncuentro`, y el que resuelve `TransportePrecio` por zona) — sin
esto, alguien podría mandar el id de un item desactivado y seguir
comprándolo. Si un item se desactiva **después** de que el cliente ya lo
seleccionó pero **antes** de pagar, `CrearPagoView` lo quita de la
reserva (borra el `ReservaExtra`/`ReservaTransporte` correspondiente y no
lo suma al total) en vez de bloquear el pago del resto — desactivar un
item es una decisión de "dejar de venderlo de aquí en adelante", no un
motivo para trabar un pago que ya iba en curso.

Nunca hay `numero_personas` de transporte distinto al de la reserva: se lee
de `reserva.numero_personas` en el momento de calcular y se guarda aquí solo
para que el dato sobreviva si el precio base cambia después.

## Cálculo de dinero (`apps/payments/pricing.py`)

Se agregan funciones puras al módulo existente — no uno nuevo (corrección 5).
Reciben primitivos, no instancias de modelo, igual que `cargo_por_lunch` ya lo
hace hoy: quien llama resuelve `precio_en(moneda)` antes, `pricing.py` no
necesita saber qué es un `ExtrasItem`. Así se prueban sin tocar la base de
datos y no crean una dependencia de `fleet` hacia `payments` ni al revés.

```python
def cargo_por_extra(precio, cobrar_por_persona, numero_personas):
    """precio ya resuelto en la moneda que toque. None si no hay precio ahi."""
    if precio is None:
        return None
    cantidad = numero_personas if cobrar_por_persona else 1
    return Decimal(precio) * cantidad


def cargo_por_transporte(precio_base, recargo_grupo, min_personas_recargo, numero_personas):
    """precio_base/recargo_grupo ya resueltos en la moneda que toque.
    None si no hay precio base en esa moneda."""
    if precio_base is None:
        return None
    cargo = Decimal(precio_base)
    if numero_personas >= min_personas_recargo:
        cargo += Decimal(recargo_grupo or 0)
    return cargo
```

`fleet.TransportePrecio` gana los mismos accesores por moneda que ya tiene
`ExtrasItem`, para que quien llama a `pricing.py` use una sola convención:

```python
def precio_en(self, moneda):
    return self.precio_base if moneda == 'MXN' else self.precio_base_usd

def recargo_en(self, moneda):
    return self.recargo_grupo if moneda == 'MXN' else self.recargo_grupo_usd
```

**`cargo_por_lunch` se retira** en la misma pieza que quita
`Tarifa.precio_lunch`/`precio_lunch_usd`/`lunch_en()` (ver "Qué pasa con
`lleva_lunch`" — el brunch ahora es un `ExtrasItem` más, cobra por
`cargo_por_extra` igual que licencia). El docstring del módulo, que hoy dice
*"Bebidas y transporte: no se cobran en linea"*, se corrige: transporte sí se
cobra ahora, bebidas sigue sin cobrarse.

**Quién escribe el precio congelado, y cuándo — una sola respuesta:**
`CrearPagoView` es el único que escribe `ReservaExtra.precio_unitario`,
`ReservaExtra.cantidad` y `ReservaTransporte.precio_calculado`, en el momento
de pagar, con el precio **vigente** del catálogo en ese instante — no el que
el cliente vio en pantalla ni el que mandó el formulario. El checkout
(`ReservaCheckoutSerializer`) solo escribe la **selección** (qué
`ExtrasItem`, qué `punto_encuentro`/`direccion_personalizada`/`zona`): los
campos de precio de `ReservaExtra`/`ReservaTransporte` quedan `null` hasta
ese momento. Con esto hay un solo lugar que decide cuánto cuesta algo — la
misma garantía que ya tiene `precio_total` — y no dos cálculos que pueden
desalinearse si un jefe edita un precio entre el envío del formulario y el
pago.

`CrearPagoView` hace todo esto dentro de una sola `transaction.atomic()`:
recalcula cada `ReservaExtra`/`ReservaTransporte` de la reserva con el precio
vigente, los guarda, arma `precio_total`, y crea/reutiliza el intent de
Stripe. Si algún item ya no tiene precio en la moneda de la reserva, 503,
mismo patrón que ya usa con `precio_lunch` hoy.

## Flujo del checkout

`ReservaCheckoutSerializer` acepta la selección de extras y los datos de
transporte como parte del mismo envío que ya hace hoy con `lleva_lunch`.
Mientras la reserva esté `pendiente_pago`, cada envío del formulario
reescribe la selección completa: borra los `ReservaExtra` de esa reserva que
ya no vengan en la lista nueva, crea los que falten (sin tocar precio,
`null` hasta que se pague), y hace `update_or_create` sobre
`ReservaTransporte`. Una reserva que ya no está `pendiente_pago` no se toca
desde la web — la misma regla que ya existe en
`ReservaCheckoutSerializer.validate()`.

`ReservaTransporte.clean()` exige que venga `punto_encuentro` **o**
`direccion_personalizada`, nunca los dos vacíos ni los dos con valor. El
serializer llama `full_clean()` sobre el `ReservaTransporte` en el mismo paso
en que ya llama `reserva.full_clean()`.

**Endpoint público nuevo, resuelto en servidor — no cifras crudas:**
`GET /api/extras/?personas=N&moneda=MXN` (en `apps/fleet`, junto a los
modelos que sirve — mismo archivo que ya monta `/api/tarifa/`). Devuelve cada
`ExtrasItem`/`TransportePrecio` activo **con el monto ya calculado** para
esos `personas`/`moneda` (llama a `pricing.cargo_por_extra`/
`cargo_por_transporte` del lado del servidor), más `PuntoEncuentro` activos.
Así el frontend nunca reimplementa "si `cobrar_por_persona` multiplica" ni
"si `numero_personas >= min_personas_recargo` suma el recargo" — esas son
reglas de dinero y `backend/CLAUDE.md` exige que vivan en un solo lugar. Sin
`personas`, asume 1; sin `moneda`, `MXN` — mismos defaults permisivos que ya
usa `/api/cupo/`.

`EstadoReservaView` (recuperación de checkout abandonado) devuelve además la
selección de extras y transporte existentes en la rama `pendiente_pago`
(ids y datos de selección, no precios — los precios no existen todavía en
ese punto), igual que ya devuelve `lleva_lunch`.

## El correo de confirmación (`apps/notifications/services.py`)

`_cuerpo_html` hoy lee `reserva.lleva_lunch` y `reserva.pide_transporte`
directo, y anuncia un punto de encuentro fijo en texto (`Marina La Costa`)
sin importar si la reserva compró traslado a otra dirección. Al quitar esos
dos campos de `Reserva`, esta función revienta con `AttributeError`.

Esto no es un detalle menor: `notificar_reserva_pagada` corre dentro de la
misma transacción que marca la reserva como pagada
(`aplicar_pago_exitoso`, `apps/payments/services.py`), y aunque su
docstring dice "nunca lanza", un `AttributeError` ahí no está atrapado —
revienta la transacción completa, la reserva se queda en `pendiente_pago`
sin `monto_pagado` aunque Stripe ya cobró, el webhook responde 200 igual
(así que Stripe no reintenta), y `conciliar_pagos` la vuelve a intentar cada
hora y falla exactamente igual cada vez. Es plata cobrada y reserva
fantasma, en silencio.

Se corrige en la misma pieza que quita los campos: `_cuerpo_html` pasa a
leer `reserva.extras_seleccionados.all()` (brunch/licencia/carnada
compradas) y `reserva.transporte` (si existe, el punto de encuentro real en
vez del texto fijo), y el párrafo de "esto se cotiza aparte" se recorta a
solo bebidas.

## Qué pasa con `lleva_lunch`

## Frontend — paso "Extras" (antes "Lunch")

Un solo componente grande hoy (`checkout-view.tsx`), no steps separados en
archivos propios — se sigue ese patrón, no se inventa uno nuevo. Cambios:

- **Brunch**: card informativa, ya no afecta el copy de "elegir menú" (nunca
  lo hizo — el menú siempre fue fijo). Texto nuevo en ambos diccionarios.
- **Transporte**: toggle sí/no. Si sí: selector de `PuntoEncuentro` (trae
  zona) o "Otra dirección" (texto libre + select de zona obligatorio). Usa
  `people` (el estado que ya existe en `checkout-view.tsx` para el número de
  pasajeros del tour) para pedir `/api/extras/?personas=...` — no se vuelve
  a preguntar el número de personas.
- **Licencia y carnada**: checkboxes preseleccionados según
  `ExtrasItem.preseleccionado`, con el monto que ya viene resuelto de
  `/api/extras/`.
- El frontend **no calcula ningún monto**: cada vez que cambia `people`,
  `moneda` o la selección, vuelve a pedir `/api/extras/?personas=N&moneda=M`
  y muestra los montos que trae la respuesta. Sumar lo seleccionado para el
  total en pantalla sí es aritmética de UI (una suma, no una regla de
  negocio); qué cobra cada item y si aplica recargo lo decide siempre el
  servidor. El total real y definitivo lo arma `crear-pago`, igual que hoy.

Renombrar en dictionaries: `lunchStepHeadline` → `extrasStepHeadline`,
`extrasSummaryWithLunch`/`NoLunch` → texto que resuma extras en general (no
solo brunch), `checkout.amenities.lunch` → `checkout.amenities.brunch`,
`lunchPerPerson` se queda (aplica a cualquier item por persona). Reemplaza
`amenities-reminder.tsx` (hoy solo sabe de lunch) por una versión que itera
sobre los extras faltantes.

## Riesgos y lo que queda abierto

- **`cobrar_por_persona` de carnada y licencia no viene resuelto de negocio.**
  Licencia de pesca suele ser individual (cada quien la suya) y carnada suele
  comprarse para la panga completa, no por cabeza — pero es una suposición,
  no un dato confirmado como los precios de transporte. Por eso el campo es
  editable desde el admin en vez de estar hardcodeado: si la suposición está
  mal, se corrige sin deploy. Seedear con licencia en `True` y carnada en
  `False`, y que el usuario lo confirme la primera vez que abra el admin de
  `ExtrasItem`.
- **Precios en USD de transporte, licencia y carnada quedan en `null` al
  seedear** hasta que el usuario los dé. Mientras tanto, una reserva en
  dólares que quiera esos extras recibe 503 en `crear-pago` (mismo
  comportamiento que ya tiene `Tarifa` cuando falta `precio_lunch_usd`) — no
  bloquea el resto del checkout, solo ese extra.
- **Migración de datos**: el sitio no se ha lanzado
  (`[[estado-prelanzamiento]]`), así que no hace falta migrar reservas viejas
  con `lleva_lunch=True` a `ReservaExtra`. Si esto cambia antes de
  implementar, hay que revisarlo primero.
- **No se valida cupo de camionetas de transporte.** El transporte no tiene
  motor de disponibilidad propio (a diferencia de las pangas): se asume que
  siempre hay transporte disponible. Si el negocio dice lo contrario, es
  trabajo aparte.
- **Permisos de la vendedora**: `fleet.ExtrasItem` y `fleet.TransportePrecio`
  quedan sin permisos para el grupo Vendedora, mismo trato que
  `fleet.Tarifa` — son precios, información financiera que ven los jefes.
  `fleet.PuntoEncuentro` sí lleva permiso de vista para la vendedora: es un
  catálogo operativo (qué hotel es de qué zona), no un precio.
- **El sembrado del catálogo es un comando (`manage.py seed_extras`), no una
  migración de datos** — se decidió así implementando la Fase A: una
  migración de datos corre una sola vez al construir la base de pruebas y
  sus filas quedan como línea base para **todo** el suite (el rollback por
  test no las toca, solo deshace lo que pasa dentro de cada test), así que
  contamina cualquier prueba futura que cuente filas de `ExtrasItem`. Un
  comando de gestión nunca corre durante `manage.py test`. Es un paso manual
  más en producción, mismo trato que `setup_roles` — hay que correrlo
  **antes** de aplicar la migración de Fase B que borra
  `Tarifa.precio_lunch`/`precio_lunch_usd`, o el brunch se siembra con un
  precio que ya no existe.
- **Backend y frontend se despliegan juntos.** El sitio no se ha lanzado, así
  que no hay ventana de compatibilidad que cuidar entre que el backend deja
  de mandar `lleva_lunch` en `EstadoReservaView` y el frontend deja de
  leerlo — pero si se llegara a desplegar el backend sin el frontend
  actualizado, el checkout en producción dejaría de mostrar el estado de
  brunch al recuperar una sesión (el campo simplemente no vendría). No es
  un problema hoy porque no hay tráfico real; sí lo sería después del
  lanzamiento, y en ese caso las dos partes de esta pieza deben
  desplegarse en la misma ventana, no por separado.
