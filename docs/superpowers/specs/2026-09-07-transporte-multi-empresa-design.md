# Diseño — Transporte como servicio y órdenes cruza-empresa

- **Fecha:** 2026-09-07
- **Rama:** `feat/transporte-multi-empresa` (basada en `fix/expansion-multi-sede-hallazgos`)
- **Estado:** PROPUESTO — pendiente de revisión del dueño y del spec-critic
- **Ejecuta:** agente de Antigravity, por plan de tareas (uno por sub-proyecto)
- **Depende de:** que se mergee antes `fix/expansion-multi-sede-hallazgos` (correcciones de hallazgos)

Documentos de plan que salen de este diseño:

- `docs/superpowers/plans/2026-09-07-transporte-sp1-servicio.md`
- `docs/superpowers/plans/2026-09-07-transporte-sp2-orden-cruza-empresa.md`

ADR que este diseño modifica:

- `2026-08-31-expansion-multi-sede-ADRs.md` → ADR-004 (paquetes dejan de tener "servicios removibles")
- `2026-09-06-ADR-005-paquetes-cruza-empresa.md` → deja de estar diferido; decisión = Opción A refinada (modelo B de cobro)

---

## 1. Contexto de negocio (lo que dijo el dueño, 2026-09-07)

El dueño opera el negocio además de programarlo; esta información llega por partes y
ya invalidó supuestos del repo. Lo relevante para este diseño:

### 1.1 Empresas y sedes

- **Empresa de marketing** = operador de plataforma. Sin cuenta Stripe central, a
  propósito (tema fiscal). Cada empresa cobra en SU propia cuenta Stripe. **No** es
  Stripe Connect.
- **Sede La Paz:**
  - **Empresa 1** — pesca deportiva. Salidas de panga 5–7am.
  - **Empresa 2** — transporte. Vende traslados directos por la web, y traslados
    combinados con la pesca de la Empresa 1 (cruza-empresa).
- **Sede La Ventana:** Empresa 3, todo bajo un techo (mono-empresa). No es objetivo de
  este diseño; se beneficia de las generalizaciones de SP1 (horas por servicio, tope
  de personas por servicio).

### 1.2 Precio del transporte (Empresa 2, La Paz)

Todos los viajes son **privados** (camioneta completa). Hay espacio para hielera y
equipo. Camionetas de 11 y de 14 plazas; cuál se manda lo decide el transportista a
mano. Tres tipos de traslado vendibles por el sistema:

| Clave | Recorrido | Precio |
|---|---|---|
| `redondo_aeropuerto` | aeropuerto → hospedaje → actividad → hospedaje → aeropuerto | $4500 hasta 4 personas · $6000 de 5 hasta capacidad |
| `redondo_actividad` | hospedaje → actividad → hospedaje | $1500 si el hospedaje está en zona **centro** · $1800 si está en **periferia** |
| `recepcion_aeropuerto` | aeropuerto → hospedaje (sencillo) | $2700, plano |

- El precio de "5+" en `redondo_aeropuerto` es plano hasta el tope de capacidad (no
  escala por persona).
- `redondo_actividad` no tiene tramo por tamaño en la información que dio el dueño:
  precio plano por zona. (Si más adelante lo tuviera, se agrega otra fila de tarifa;
  el modelo lo soporta.)
- Viajes más largos o fuera de estos patrones: **fuera del sistema**, el cliente
  habla directo con el transportista. La web no los cotiza.
- Todas las cifras son MXN. USD opcional por fila de tarifa (mismo patrón que el
  resto del sistema: dos precios sin tipo de cambio).

### 1.3 Decisión estructural: transporte deja de ser "personalización"

Hasta hoy el transporte era un add-on (`bookings.ReservaTransporte`, OneToOne) dentro
de la reserva de pesca. **Se elimina esa idea.** De ahora en adelante:

- El transporte es un **`Servicio`** de primera clase de la Empresa 2.
- Juntar pesca + transporte es un **`Paquete`** (paquete cruza-empresa: componente de
  la Empresa 1 + componente de la Empresa 2).

Consecuencia directa: el paquete "Pesca + Traslado" es cruza-empresa, lo que estaba
diferido de v1 (ADR-005). Para venderlo hace falta el cobro multi-empresa. Por eso
**SP2 entra en esta ronda**, no después.

### 1.4 Decisión sobre paquetes: no se quitan servicios

Un paquete es un bundle **fijo** con precio propio, pensado para ofrecerse un poco
más barato que la suma de los servicios sueltos. Si el cliente eligió el paquete es
porque le convencieron los servicios agrupados. Por lo tanto:

- El checkout **no** ofrece quitar un servicio de un paquete, ni antes ni durante.
- Las **personalizaciones** de cada servicio del paquete **sí** siguen (licencia,
  brunch, etc.) — no confundir "servicio" con "personalización de un servicio".
- Se elimina todo el mecanismo de "servicios removibles" (ver §5).

---

## 2. Estado actual del código (rama `fix/expansion-multi-sede-hallazgos`)

Lo que ya existe y este diseño reutiliza o modifica:

- **`fleet.Servicio`** — experiencia vendible por empresa. Campos: `estrategia_cupo`
  (`por_recurso_dia` / `por_noche` / `bajo_demanda`), `estrategia_precio`
  (`por_grupo` / `por_persona` / `tarifa_fija` / `por_noche`), `modo_ocupacion`,
  `porcentaje_anticipo`, `precio_base(_usd)`, `precio_persona_extra(_usd)`,
  `personas_incluidas`, `tipo_servicio` (`pesca` / `paseo` / `hospedaje` /
  `bajo_demanda`).
- **`apps/payments/estrategias_precio.py`** — registro polimórfico de estrategias de
  precio: `EstrategiaPrecio` (ABC) → `PorGrupo` / `PorPersona` / `TarifaFija` /
  `PorNoche`, `REGISTRO_ESTRATEGIAS_PRECIO`, `obtener_estrategia_precio(clave)`,
  `registrar_estrategia_precio(clave, obj)`. `DemandaPrecio(personas, moneda, noches)`.
- **`fleet.TransportePrecio`** — `zona` (`centro` / `periferia`), `precio_base(_usd)`,
  `recargo_grupo(_usd)`, `min_personas_recargo`, `activo`, FK `empresa`,
  `UniqueConstraint(zona, empresa)`.
- **`fleet.PuntoEncuentro`** — catálogo de hoteles/hospedajes conocidos con su `zona`
  ya clasificada, FK `empresa`. Evita depender de geocoding.
- **`bookings.ReservaTransporte`** — OneToOne a `Reserva`. `punto_encuentro` |
  `direccion_personalizada`, `zona` (snapshot, la deriva el servidor),
  `personas_solicitadas`, `numero_personas` / `precio_calculado` (congelados por
  `CrearPagoView`). **Se elimina** en la limpieza previa de SP1 (§3.6.1); lo sustituye
  `DetalleTransporte` (§3.4).
- **`bookings.Reserva`** — `hora` con validador de campo `validar_ventana_salida`
  (5–7am, hardcodeado); `numero_personas` con `MaxValueValidator(MAX_PERSONAS=5)`;
  `servicio` (nullable, vacío = pesca legacy), `paquete` (nullable), `empresa`,
  `fecha` / `fecha_salida`. `clean()` corre cupo según estrategia, deslinde web,
  capacidad de embarcación, "una salida por día", cambio de fecha, consistencia de
  empresa.
- **`bookings/cupo/confirmacion.py::reservar_cupo_al_confirmar`** — al pagar, crea
  `ReservaPaqueteComponente` por cada componente **no removido**; para `bajo_demanda`
  solo crea el componente (sin tocar inventario).
- **`apps/payments/pricing.py`** — todo el dinero en un solo lugar. `cargo_por_transporte`,
  `precio_paquete` / `precio_paquete_total` / `calcular_precio_paquete` (hoy restan
  ajustes de servicios removidos), `monto_inicial` (anticipo), `cargo_por_descuento`.
- **`fleet.Paquete`** — `sede`, `empresa_lider`, `precio_ancla(_usd)`, `regla_precio`
  (default `precio_ancla`), `porcentaje_anticipo`. **`PaqueteServicio`** — `removible`,
  `ajuste_precio(_usd)`. `PaqueteServicio.clean()` prohíbe componentes de otra empresa
  (bloqueo v1 de ADR-005).
- **`bookings.ReservaPaqueteServicioRemovido`** + `servicios_removidos` en
  `ReservaCheckoutSerializer` + filtro "no removido" en `confirmacion.py` y
  `models.py`. **Se elimina todo** (ver §5).
- **Marketplace en checkout** — API bajo `/api/<empresa_slug>/...`. El frontend
  resuelve la empresa del producto (`servicio.empresa_slug` /
  `paquete.empresa_lider_slug`) y `crear-pago` cobra en la cuenta Stripe de esa
  empresa (`pago.publishable_key`).
- **Webhook / `conciliar_pagos`** — el webhook es la única fuente de verdad; corre en
  `transaction.atomic` + `select_for_update`; reembolsa duplicados y pagos sin reserva;
  `conciliar_pagos` es la red de seguridad idempotente (cron horario).
- **`apps/finance`** — solo lectura, agrega por `Reserva`; sin tabla de movimientos.

---

## 3. Sub-proyecto 1 — Transporte como servicio (fundación)

**Objetivo:** la Empresa 2 vende traslados sueltos por la web, con su propio cobro
(un solo PaymentIntent a su cuenta Stripe). Complejidad media, comparable a una pieza
de la expansión multi-sede.

### 3.1 Catálogo de tarifas: `fleet.TransporteTarifa`

Se **reemplaza** `TransportePrecio` (dos filas zona) por `TransporteTarifa`, un
catálogo de tarifas por empresa que cubre los tres tipos de traslado:

```
TransporteTarifa
  empresa            FK tenancy.Empresa (PROTECT)
  tipo_traslado      CharField choices: redondo_aeropuerto | redondo_actividad | recepcion_aeropuerto
  zona               CharField choices centro|periferia, NULL salvo redondo_actividad
  personas_min       PositiveSmallIntegerField (default 1)
  personas_max       PositiveSmallIntegerField (NULL = sin tope superior en esta fila)
  precio             DecimalField (MXN)
  precio_usd         DecimalField (NULL = no se ofrece en USD)
  activo             BooleanField (default True)

  UniqueConstraint(empresa, tipo_traslado, zona, personas_min)
  CheckConstraint: zona no nula  ⟺  tipo_traslado == redondo_actividad
```

- `Zona` (`centro` / `periferia`) se conserva como enum (lo usan `PuntoEncuentro` y
  esta tabla).
- Filas de ejemplo para la Empresa 2 (las carga el jefe en el admin, no hay seed
  productivo):
  - `redondo_aeropuerto`, zona `NULL`, `personas_min=1`, `personas_max=4`, `precio=4500`
  - `redondo_aeropuerto`, zona `NULL`, `personas_min=5`, `personas_max=NULL`, `precio=6000`
  - `redondo_actividad`, zona `centro`, `personas_min=1`, `personas_max=NULL`, `precio=1500`
  - `redondo_actividad`, zona `periferia`, `personas_min=1`, `personas_max=NULL`, `precio=1800`
  - `recepcion_aeropuerto`, zona `NULL`, `personas_min=1`, `personas_max=NULL`, `precio=2700`
- **Sin datos que migrar** (`TransportePrecio` está vacío en producción —
  prelanzamiento). Se borra la tabla vieja y su RLS.

**Resolución de tarifa** (función pura, en `fleet` o `payments`): dado
`(empresa, tipo_traslado, zona, personas)` devuelve la fila cuyo rango
`[personas_min, personas_max]` contiene `personas` y cuya `zona` coincide (o ambas
NULL). Cero filas → error de configuración explícito (mismo criterio que "catálogo
`Embarcacion` incompleto → el sitio deja de vender": fallo seguro, no silencioso).

### 3.2 Estrategia de precio `por_ruta`

- Nueva clave en `fleet.enums.EstrategiaPrecio`: `POR_RUTA = 'por_ruta'`.
- Nueva clase `PorRuta(EstrategiaPrecio)` en `estrategias_precio.py`, registrada en
  `REGISTRO_ESTRATEGIAS_PRECIO`.
- `DemandaPrecio` gana dos campos opcionales: `tipo_traslado: str | None = None`,
  `zona: str | None = None`. Los demás flujos no los pasan y no cambian.
- `PorRuta.calcular_base(servicio_config, demanda)`:
  1. Resuelve la fila de `TransporteTarifa` con
     `(servicio_config.empresa_id, demanda.tipo_traslado, demanda.zona, demanda.personas)`.
  2. Devuelve `fila.precio` o `fila.precio_usd` según `demanda.moneda`, cuantizado a
     centavos. `None`/ausente en esa moneda → `ValueError` (igual que las demás
     estrategias).
- **No** se usa `precio_persona_extra` ni `personas_incluidas` del `Servicio` para
  transporte: el precio sale entero de la tabla de tarifas.

### 3.3 El `Servicio` de transporte

Un `fleet.Servicio` por empresa de transporte:

- `tipo_servicio` = **nuevo** `TipoServicio.TRANSPORTE = 'transporte'` (para que el
  frontend lo renderice como traslado y no como experiencia).
- `estrategia_cupo` = `bajo_demanda` (no hay inventario de camionetas; se coordina a
  mano). No toma advisory lock, no valida cupo previo.
- `estrategia_precio` = `por_ruta`.
- `modo_ocupacion` = irrelevante para `bajo_demanda`; se deja `exclusivo` por defecto.
- `porcentaje_anticipo` configurable por el jefe. Para traslados el dueño puede poner
  `100` (cobro completo en línea) — ya es un campo existente, sin cambios.
- `capacidad_maxima` = **nuevo** campo en `Servicio` (`PositiveSmallIntegerField`,
  NULL = usa `MAX_PERSONAS` global). Para el servicio de transporte se pone `14`.

### 3.4 Modelo de la reserva de transporte

`bookings.ReservaTransporte` (OneToOne) **se elimina** y se sustituye por
`bookings.DetalleTransporte`, satélite de la `Reserva` de transporte:

```
DetalleTransporte
  reserva            OneToOneField Reserva (CASCADE, related_name='detalle_transporte')
  tipo_traslado      CharField choices (= TransporteTarifa.tipo_traslado)
  punto_encuentro    FK fleet.PuntoEncuentro (PROTECT, NULL) — el hospedaje del cliente
  direccion_personalizada  CharField(255, blank)
  zona               CharField choices centro|periferia (snapshot; lo deriva el servidor)
  fecha_regreso      DateField (NULL) — solo redondo_aeropuerto: día de salida al aeropuerto
  numero_personas    PositiveSmallIntegerField (NULL hasta pagar; lo congela CrearPagoView)
  precio_calculado   DecimalField (NULL hasta pagar; lo congela CrearPagoView)

  clean():
    - punto_encuentro XOR direccion_personalizada (uno y solo uno)
    - si punto_encuentro: zona == punto_encuentro.zona  (no se confía la del cliente)
    - si punto_encuentro: punto_encuentro.empresa_id == reserva.empresa_id
    - zona obligatoria ⟺ tipo_traslado == redondo_actividad; en los otros dos se ignora
    - fecha_regreso presente ⟺ tipo_traslado == redondo_aeropuerto; y > reserva.fecha
```

- El recorrido lo define `tipo_traslado`; no hay armador de tramos libre (los viajes
  a medida están fuera del sistema).
- La `zona` solo se pide/usa para `redondo_actividad`. Para los otros tipos el precio
  no depende de zona.
- `numero_personas` de la `Reserva` de transporte es el tamaño del grupo; alimenta la
  resolución de tarifa.

### 3.5 Generalizaciones en `bookings.Reserva` (correctitud, no solo transporte)

Estas dos reglas están hoy hardcodeadas para pesca y rompen cualquier servicio que no
sea salida de panga (transporte, y también hospedaje/paseo si se venden por web):

1. **Ventana horaria por servicio.** `fleet.Servicio` gana `hora_apertura` /
   `hora_cierre` (`TimeField`, NULL). El validador de campo `validar_ventana_salida`
   sale de `Reserva.hora` y pasa a `Reserva.clean()`:
   - Si `servicio_id` y el servicio tiene ventana → `hora` debe caer dentro.
   - Si no hay servicio (pesca legacy) → ventana 5–7am (constantes actuales).
   - Si el servicio no tiene ventana configurada → `hora` libre.
   - Migración de datos: los servicios de pesca de La Paz nacen con `hora_apertura
     = 05:00`, `hora_cierre = 07:00`.
   - `frontend/src/lib/dates.ts` deja de asumir 5–7am fijo para toda reserva.
2. **Tope de personas por servicio.** `Reserva.numero_personas` deja de validar
   contra `MAX_PERSONAS` global. En `clean()`:
   - Tope efectivo = `servicio.capacidad_maxima` si está, si no `MAX_PERSONAS` (5).
   - `MAX_PERSONAS` sigue siendo el default de pesca legacy.
   - El mismo tope viaja al frontend (`MAX_PEOPLE` deja de ser una constante única;
     se lee del servicio/paquete cargado).

3. **Reglas que se saltan para `estrategia_cupo == 'bajo_demanda'`** (ya casi todas
   lo hacen, se audita y se cierra el hueco):
   - `_validar_una_salida_por_dia` — no aplica (no hay panga ni capitán).
   - `_validar_capacidad_embarcacion` — no aplica (no hay `embarcacion`).
   - `validar_cupo_diario` — ya no se llama para `bajo_demanda`.
   - El **deslinde web sigue obligatorio** para transporte (`canal_origen='web'`).

### 3.6 API

- **`GET /api/<empresa_slug>/traslados/`** — devuelve el `Servicio` de transporte de
  esa empresa + el catálogo de `TransporteTarifa` (tipos, zonas, rangos, precios en
  ambas monedas) + los `PuntoEncuentro` activos con su zona. Sin cifras hardcodeadas
  en el frontend, mismo principio que `/api/tarifa/`. 404 si la empresa no tiene
  servicio de transporte activo.
- **`POST /api/<empresa_slug>/reservas/`** — acepta un servicio de transporte. El
  serializer:
  - Exige `tipo_traslado`, `punto_encuentro` (slug/id) o `direccion_personalizada`,
    `fecha`, `hora`, `numero_personas`; `fecha_regreso` si `redondo_aeropuerto`;
    `zona` solo si `direccion_personalizada` + `redondo_actividad` (con hotel del
    catálogo la deriva de `punto_encuentro.zona`).
  - Crea la `Reserva` (`servicio=<transporte>`, `empresa=<Empresa 2>`,
    `estado=pendiente_pago`) + `DetalleTransporte`. No ocupa cupo.
  - Deslinde igual que hoy.
- **`POST /api/<empresa_slug>/reservas/<id>/crear-pago/`** — `CrearPagoView` calcula
  el total con `PorRuta` (única fuente del precio), congela
  `DetalleTransporte.numero_personas` / `precio_calculado` y
  `Reserva.precio_total` / `forma_pago`, aplica `porcentaje_anticipo` del servicio,
  crea el PaymentIntent en la cuenta Stripe de la Empresa 2. Idempotente igual que hoy.
- **Webhook** — sin cambios de fondo: marca `pagada`, corre `full_clean()`,
  `reservar_cupo_al_confirmar` (Caso C: `bajo_demanda` directo → nada que reservar),
  dispara notificación.

### 3.6.1 Limpieza previa: transporte deja de ser personalización (dentro de SP1)

Como el transporte pasa a ser `Servicio` + (en SP2) `Paquete`, el add-on actual
sobra. SP1 lo quita **antes** de montar lo nuevo, para no arrastrar dos modelos de
precio de transporte a la vez:

- `bookings.ReservaTransporte` (OneToOne) → se elimina (migración de borrado con
  `alcance_operador_migracion`; sin datos en producción).
- `fleet.TransportePrecio` (dos filas zona) → se elimina; lo reemplaza
  `TransporteTarifa` (§3.1).
- `pricing.py::cargo_por_transporte` → se elimina.
- El fieldset "transporte" dentro de `checkout-view.tsx` (checkout de pesca) y sus
  claves de diccionario → se eliminan. Quien quiera pesca + traslado esperará al
  paquete de SP2; mientras tanto el checkout de pesca no ofrece traslado.
- `fleet.PuntoEncuentro` **se conserva** (lo usa `DetalleTransporte` y
  `TransporteTarifa`).

### 3.7 Frontend

- Nueva ruta **`/[lang]/traslados`** (o `/[lang]/traslados/[empresa]` si hay varias
  empresas de transporte; hoy solo la Empresa 2). Server component que trae el
  catálogo con `getDictionary` + fetch a `/api/<slug>/traslados/`.
- Checkout recortado, reutilizando `checkout-section-card`, `checkout-stepper`,
  `checkout-footer`, el bloque de datos del cliente, el deslinde y el
  `PaymentElement`:
  1. **Tipo de traslado** — 3 tarjetas (`redondo_aeropuerto` / `redondo_actividad` /
     `recepcion_aeropuerto`) con su descripción de recorrido y precio.
  2. **Hospedaje** — selector de `PuntoEncuentro` (autocompletar) o "otra dirección"
     (texto libre + selector de zona, solo si `redondo_actividad`).
  3. **Fechas** — `fecha` (llegada / día de actividad) y, si `redondo_aeropuerto`,
     `fecha_regreso`. `hora` con el `TimeField` casero existente, sin restricción
     5–7am.
  4. **Personas** — número simple, tope = `capacidad_maxima` del servicio.
  5. **Datos del cliente + deslinde + pago** — idénticos al checkout de pesca.
- El precio mostrado siempre viene del backend (resolución de tarifa server-side al
  pedir cotización, y congelado en `crear-pago`).
- El sub-bloque de transporte que hoy vive dentro de `checkout-view.tsx` (fieldset
  "transporte" del checkout de pesca) ya se eliminó en la limpieza previa de SP1
  (§3.6.1).

### 3.8 Admin

- `TransporteTarifaAdmin` — solo jefes de la empresa (dato financiero, mismo criterio
  que `Tarifa` / `CodigoPromocional`: la vendedora no lo ve). `list_editable` en
  `precio` / `precio_usd` / `activo`.
- `PuntoEncuentroAdmin` — ya existe; se revisa que esté scopeado por empresa.
- `ReservaAdmin` — el inline de transporte pasa de `ReservaTransporte` a
  `DetalleTransporte`. La agenda (`Agenda` proxy) no lista reservas de transporte
  (no llevan panga/capitán); se filtra por `estrategia_cupo` o `tipo_servicio`.
- `SIDEBAR` de Unfold — alta del modelo nuevo (un link mal escrito tumba el admin
  entero; ver `admin-unfold-trampas`).

### 3.9 Qué NO incluye SP1

- Nada cruza-empresa. Un traslado de SP1 se cobra a una sola cuenta Stripe.
- No hay inventario ni cupo de camionetas.
- No hay itinerarios a medida.
- El paquete "Pesca + Traslado" es SP2.

---

## 4. Sub-proyecto 2 — Órdenes cruza-empresa (paquete Pesca + Traslado)

**Objetivo:** vender un paquete cuyos componentes son de empresas distintas (Empresa 1
pesca + Empresa 2 transporte), cobrando a cada empresa en su propia cuenta Stripe.
Complejidad alta: introduce una máquina de estados de pago.

### 4.1 Modelo de cobro — "auth de todos, luego capture" (modelo B, refina ADR-005 Opción A)

Con cuentas Stripe independientes no hay split de un pago. Un paquete cruza-empresa se
cobra con **N PaymentIntents, uno por empresa**, en modo `capture_method='manual'`:

1. Se crean N PaymentIntents (uno por empresa/cuenta Stripe), cada uno por el monto de
   esa empresa. Suman el total del paquete.
2. El cliente **autoriza** los N con su tarjeta (N confirmaciones en el frontend —
   Stripe Elements no maneja varias cuentas en un formulario). Cada autorización es un
   *hold*, no un cargo firme.
3. Si **todas** las autorizaciones quedan `requires_capture` → se **capturan** las N.
   Ahí sí hay N cargos reales en el estado de cuenta del cliente, uno por empresa.
4. Si **alguna** autorización falla o el cliente abandona antes de terminar → se
   **cancela** (`PaymentIntent.cancel`, void) cada autorización ya hecha. El hold se
   suelta solo en días; **nunca hubo cobro**, no hay reembolsos.

Ventaja sobre "N cargos secuenciales" (Opción A cruda): la ventana de fallo es
diminuta (capturar tras autorizar casi nunca falla) y el caso de fallo se resuelve con
`void`, no con `refund`. El cliente **sí** ve N cargos en su estado de cuenta (uno por
empresa) — es el costo de no usar Connect.

**Alternativa que el dueño está descartando a sabiendas** (ADR-005 Opción B): la
`empresa_lider` cobra su parte online al reservar y las empresas colaboradoras mandan
enlaces de pago por separado, coordinados por la vendedora. Cero máquina de estados,
pero el cliente paga en dos momentos distintos y la vendedora tiene trabajo manual en
cada reserva. El dueño quiere que el cliente pague todo en el checkout ("lo vive como
una compra"), así que se va con el modelo B. Si el volumen de paquetes cruza-empresa
resulta muy bajo al lanzar, Opción B sigue siendo un repliegue válido.

**Límite duro de Stripe:** una autorización de tarjeta expira (típico 7 días, algunas
2). La captura ocurre segundos después de la última autorización, así que en el camino
feliz no es problema; pero `ORDEN_TIMEOUT_AUTORIZACION` (§4.5) **debe** ser holgadamente
menor a 7 días — 24 h es seguro.

### 4.2 `bookings.Orden`

```
Orden
  empresa_lider     FK tenancy.Empresa (PROTECT) — = paquete.empresa_lider
  sede              FK tenancy.Sede (PROTECT)
  paquete           FK fleet.Paquete (PROTECT)
  checkout_id       UUIDField (db_index) — mismo propósito que Reserva.checkout_id
  cliente_*         nombre / telefono / correo (una vez, no por reserva)
  moneda            CharField choices MXN|USD
  forma_pago        CharField choices completo|anticipo
  estado            CharField choices:
                      armando            (reservas creadas, sin PaymentIntents)
                      autorizando        (PaymentIntents creados, esperando N auths)
                      autorizada         (las N auth OK, listo para capturar)
                      capturada          (las N capturadas → reservas pagadas)
                      cancelada          (alguna auth falló / timeout → voids emitidos)
  creado_en / actualizado_en

Reserva (campo nuevo)
  orden             FK bookings.Orden (SET_NULL, NULL, related_name='reservas')
```

- Una `Orden` agrupa 2..N `Reserva`, una por empresa proveedora. Cada `Reserva`
  conserva su `empresa`, su `servicio` (componente del paquete), su
  `stripe_payment_intent_id` propio, su webhook propio.
- La `Reserva` de la `empresa_lider` lleva `paquete` seteado; las demás llevan
  `paquete=NULL` y `servicio=<su componente>` (o se decide en el plan que todas
  lleven `paquete` para el admin — decisión de detalle, no de arquitectura).
- `checkout_id` en `Orden` para que un checkout reintentado reutilice la misma orden.

### 4.3 Paquete cruza-empresa (cierra ADR-005)

- `PaqueteServicio.clean()` deja de exigir que el componente sea de `empresa_lider`.
  Nueva regla: el componente pertenece a **alguna empresa de la misma `sede`** que el
  paquete.
- `Paquete` gana (o se confirma que ya sirve) la capacidad de listar sus componentes
  con su empresa. `ReservaPaqueteComponente.empresa` ya existe justo para esto.
- El precio del paquete cruza-empresa sigue siendo **un precio fijo** (§5): el jefe de
  la `empresa_lider` lo fija.
- **Reparto entre empresas** (decisión del dueño, 2026-09-07): *transporte a su
  tarifa, pesca se lleva el resto*. No hay campo nuevo. El componente de transporte
  se cobra al precio de su `TransporteTarifa` resuelto para el
  `(tipo_traslado, zona, personas)` del paquete; el resto
  (`precio_paquete − monto_transporte`) va a la `Reserva`/cuenta de la `empresa_lider`
  (pesca).
  - `Paquete.clean()` valida `precio_paquete ≥ monto_transporte` en cada moneda
    configurada (si no, el reparto de pesca sería negativo → error de configuración
    explícito, mismo criterio que un catálogo incompleto).
  - Si el paquete llegara a tener >2 componentes cobrables de empresas distintas, cada
    componente de tipo conocido (transporte) va a su tarifa y solo **una** empresa
    (la líder) absorbe el residuo. Fuera de v1 igualmente (§4.9).
- Generaliza a: `monto_por_empresa(orden) -> {empresa_id: Decimal}` en
  `apps/payments/pricing.py` (función pura, única fuente del reparto).

### 4.4 Pago de la orden

- **`POST /api/<sede_slug>/ordenes/`** — crea la `Orden` (`armando`) + las N `Reserva`
  (`pendiente_pago`), una por empresa, con su componente. Deslinde una vez (se copia a
  cada reserva web). No ocupa cupo.
- **`POST /api/<sede_slug>/ordenes/<id>/crear-pago/`** — calcula el reparto por empresa
  (`PaqueteServicio.monto_empresa`), crea N PaymentIntents `capture_method='manual'`,
  cada uno en la cuenta Stripe de su empresa, con `metadata` `{orden_id, reserva_id,
  empresa_id}`. Devuelve la lista `[{empresa, monto, client_secret, publishable_key}]`.
  Idempotente: si la orden ya tiene PaymentIntents sin capturar, los reutiliza /
  ajusta; si ya está `capturada`, 409.
- **`POST /api/<sede_slug>/ordenes/<id>/confirmar-captura/`** — lo llama el frontend
  cuando el cliente terminó las N autorizaciones. Verifica con Stripe que los N
  PaymentIntents estén `requires_capture`; si sí, captura los N (`PaymentIntent.capture`),
  marca `Orden.capturada`. Si alguno no está listo o falla → cancela (void) los que sí
  y marca `Orden.cancelada`. **La captura y el void llevan `idempotency_key`.**
- **Webhook** (por empresa, ya scopeado) — en `payment_intent.succeeded` (que para
  manual capture llega tras el `capture`) marca **su** `Reserva` como `pagada`, corre
  `full_clean()`, `reservar_cupo_al_confirmar`, y **evalúa la orden**: si todas sus
  reservas están `pagadas` → `Orden.capturada` (idempotente) + **notificación**:
  **correo combinado** (pesca + traslado, un solo mensaje disparado una sola vez al
  cerrarse la orden) + **WhatsApp por empresa** (cada empresa manda el suyo con su
  plantilla de Meta ya aprobada, como hoy). Si el cupo de su componente se llenó
  mientras el cliente pagaba → reembolsa **su** cargo y llama
  `revertir_orden(orden, motivo)` (§4.7.1) para void/refund del resto, marca
  `Orden.cancelada`. (Este es el camino delicado; el plan lo detalla como sección
  propia con tests de cada rama.)

### 4.4.1 Confirmación de cupo por componente (rework de `confirmacion.py`)

`reservar_cupo_al_confirmar` hoy (Caso B) itera **todos** los
`paquete.servicios_asociados` desde una sola `Reserva` y crea un
`ReservaPaqueteComponente` por cada uno, escribiendo bajo la `empresa` de esa reserva.
Eso es lógica **mono-empresa** y no sirve para una orden cruza-empresa: escribiría
componentes/ocupaciones de la Empresa 2 bajo el contexto RLS de la Empresa 1.

SP2 lo separa:

- Cada `Reserva` de una orden tiene `servicio` = **su** componente y `empresa` = la
  dueña de ese componente.
- Para una reserva que es "un componente de una orden" (`reserva.orden` no nula), el
  webhook de esa empresa corre una variante que reserva **solo su `servicio`**
  (según su `estrategia_cupo`) y crea **un** `ReservaPaqueteComponente` para su
  componente, todo bajo su propio contexto de empresa.
- El Caso B actual (iterar todos los componentes desde una reserva) queda solo para
  paquetes **mono-empresa** (`reserva.paquete` no nula y sin `reserva.orden`).
- Si el cupo de su componente falla → `SinCupoError` → el webhook reembolsa **su**
  cargo y dispara la compensación de la orden (§4.4, §4.10).

### 4.5 `conciliar_pagos` entiende órdenes

- Hoy busca `Reserva` en `pendiente_pago` con PaymentIntent y le pregunta a Stripe.
- Nuevo: para reservas con `orden`, resuelve a nivel orden — si los N PaymentIntents
  están `succeeded` aplica las N; si unos sí y otros no y pasó el timeout
  (`ORDEN_TIMEOUT_AUTORIZACION`, p.ej. 24 h), emite void/refund de los pagados y marca
  `Orden.cancelada`. Sigue siendo idempotente.
- Comando de apoyo `manage.py revisar_ordenes` — lista órdenes atascadas en
  `autorizando` / `autorizada` para que la vendedora las vea.

### 4.6 (movido a SP1 §3.6.1)

La eliminación de "transporte como personalización" (`ReservaTransporte`,
`cargo_por_transporte`, `TransportePrecio`, fieldset del checkout de pesca) ocurre en
la limpieza previa de SP1. SP2 solo **re-introduce** el transporte como componente de
un `Paquete` cruza-empresa.

### 4.7 Admin de órdenes

- `OrdenAdmin` — solo lectura para la vendedora, con las N reservas ligadas visibles,
  el estado de la orden, y los N cargos con su estado en Stripe. Acción "cancelar
  orden (void de autorizaciones pendientes)" para el operador/jefe.
- `ReservaAdmin` — columna/enlace a la orden cuando la reserva pertenece a una.
- Panel de finanzas — cada `Reserva` de la orden ya deja su rastro por separado
  (`monto_pagado` / `pagada_en` por empresa); **no** se agrega tabla de movimientos de
  orden. La orden es agrupación de UI, el dinero se sigue leyendo de cada reserva.

### 4.7.1 Puntos delicados de tenancy y compensación

- **RLS de `Orden`.** `Orden` no tiene un `empresa_id` único (cruza empresas). Se
  scopea por `sede` (política RLS sede-scoped, como `Empresa`/`Sede` mismas) y el
  operador de plataforma la ve completa. El guardarraíl "toda tabla con `empresa_id`
  tiene política" no aplica a `Orden`; se documenta la excepción como con `Sede`.
- **Compensación.** Cuando una parte de la orden falla tras haber capturado/pagado
  otra, hay que devolver lo cobrado: `refund` de los PaymentIntents ya capturados y
  `cancel` de los que solo están autorizados. Un helper `revertir_orden(orden, motivo)`
  centraliza esto, con `idempotency_key` por operación y tolerante a reintentos (una
  segunda llamada no vuelve a reembolsar). Vive en `apps/payments/services.py` junto a
  `aplicar_pago_exitoso`.
- **`forma_pago` en órdenes cruza-empresa.** Restringido a `completo` (100% en línea)
  — decisión del dueño, 2026-09-07. El anticipo repartido entre empresas (quién cobra
  el efectivo, cómo concilia cada panel de finanzas) no paga su costo. El checkout de
  un paquete cruza-empresa **no** ofrece "anticipo"; el `Servicio` suelto de transporte
  (SP1) y la pesca suelta siguen permitiéndolo.
- **Disputa (chargeback) sobre un cargo de la orden.** `Reserva.en_disputa` por
  reserva, no cambia el estado ni de la reserva ni de la orden — lo resuelve una
  persona, igual que hoy para reservas sueltas.
- **Data migrations con RLS.** Quitar `ReservaPaqueteServicioRemovido` y
  `ReservaTransporte`, y cualquier backfill, se envuelve en
  `apps.tenancy.rls.alcance_operador_migracion(...)` (ver `backend/CLAUDE.md`).

### 4.8 Frontend de la orden

- El checkout de un `Paquete` cruza-empresa detecta que el paquete tiene componentes
  de >1 empresa y entra en modo orden:
  1. Un solo formulario de datos del cliente + deslinde.
  2. Al pagar: crea la orden, pide `crear-pago`, recibe la lista de N pagos.
  3. Monta N `PaymentElement` en secuencia: *"Paso 1 de 2 — Pesca (Empresa 1): $X"*,
     *"Paso 2 de 2 — Traslado (Empresa 2): $Y"*. Cada uno confirma su PaymentIntent
     (`stripe.confirmPayment` con `capture_method` manual → queda `requires_capture`).
  4. Tras el último, llama `confirmar-captura`. Pantalla de éxito o de "no se pudo
     completar el segundo pago, no se te cobró nada".
- Si el cliente cierra a mitad: la orden queda `autorizando`; `conciliar_pagos` /
  `revisar_ordenes` la limpia tras el timeout (void de lo autorizado).

### 4.9 Alcance mínimo de SP2

- Solo **"un componente base de una empresa + un componente de traslado de otra
  empresa"** — orden de 2 cobros. No carrito general de N empresas arbitrarias.
- Un solo paquete cruza-empresa en producción al lanzar: "Pesca + Traslado" (La Paz).
- Reparto por empresa configurado a mano por el jefe (`PaqueteServicio.monto_empresa`).

---

## 5. Cambio transversal: paquetes sin "servicios removibles"

Aplica a SP2 y **también** al código ya mergeado en `fix/expansion-multi-sede-hallazgos`.
Se ejecuta como **sección nueva del plan de corrección de hallazgos**
(`2026-09-06-correccion-hallazgos-TAREAS-EJECUTABLES.md`), y SP2 lo tiene como
prerrequisito.

Se elimina:

- `bookings.ReservaPaqueteServicioRemovido` (modelo + migración de borrado + su RLS en
  `0032_rls_checkout_paquete`).
- `PaqueteServicio.removible`, `PaqueteServicio.ajuste_precio`, `ajuste_precio_usd`.
- `ReservaCheckoutSerializer.servicios_removidos` (ListField + validaciones +
  `_sincronizar_servicios_removidos`).
- El filtro "no removido" en `bookings/cupo/confirmacion.py` y en
  `bookings/models.py` (~línea 225, `_validar_cupo_de_paquete`).
- La resta de ajustes en `pricing.py`: `precio_paquete(precio_ancla, ajustes_removidos)`
  → `precio_paquete(precio_paquete)` (identidad sobre el precio fijo);
  `precio_paquete_total` deja de restar `ps.ajuste_en(moneda)`;
  `calcular_precio_paquete(paquete, servicios_removidos_pks, moneda)` pierde el
  parámetro.
- La validación en `Paquete.clean()` de "suma de ajustes de removibles no supera el
  ancla" (ya no hay ajustes).

Se renombra (opcional, decisión del plan): `Paquete.precio_ancla` → `precio_paquete`,
`regla_precio` se retira (siempre es precio fijo). Mantener `precio_ancla` como nombre
es aceptable si el rename añade mucho ruido de migración; lo que importa es que **no
se resta nada**.

Se conserva intacto:

- `ReservaPaquetePersonalizacion` y `ReservaPaqueteComponente`.
- Las personalizaciones por servicio siguen sumando al precio del paquete
  (obligatorias/preseleccionadas + opcionales marcadas), como hoy.
- `Paquete.porcentaje_anticipo`.

Frontend: `paquete-card.tsx` y `checkout-view.tsx` — se quita cualquier control de
"quitar servicio del paquete"; se dejan los toggles de personalización.

---

## 6. Errores y casos límite

| Caso | Manejo |
|---|---|
| `TransporteTarifa` sin fila para `(tipo, zona, personas)` | Error de configuración explícito en `crear-pago` (500 con log claro); el checkout de traslados no deja llegar ahí porque el catálogo viene del backend. |
| Cliente manda `zona` que no coincide con su hotel | `DetalleTransporte.clean()` rechaza; el serializer ni siquiera la lee cuando hay `punto_encuentro`. |
| Grupo > `capacidad_maxima` del servicio de transporte | Rechazo en `Reserva.clean()` y en el frontend (tope leído del servicio). |
| SP2: auth 1 OK, auth 2 falla | `confirmar-captura` hace void de auth 1; `Orden.cancelada`; frontend muestra "no se te cobró nada". |
| SP2: cliente cierra tras auth 1, antes de auth 2 | Orden queda `autorizando`; `conciliar_pagos` / `revisar_ordenes` hace void tras `ORDEN_TIMEOUT_AUTORIZACION`. |
| SP2: ambas auth OK, capture 2 falla (raro) | Se capturó 1: `conciliar_pagos` reintenta la captura de 2; si sigue fallando tras N intentos, refund de 1 + `Orden.cancelada` + alerta a la vendedora. |
| SP2: cupo de un componente se llenó mientras el cliente pagaba | El webhook de esa empresa reembolsa su cargo y llama `revertir_orden` (void/refund del resto); `Orden.cancelada`. |
| SP2: autorización expira antes de capturar (timeout largo) | No debe pasar: `ORDEN_TIMEOUT_AUTORIZACION` (24 h) ≪ 7 días. Si aun así una expira, `conciliar_pagos` la detecta `canceled` y hace `revertir_orden`. |
| SP2: chargeback sobre un cargo de la orden ya capturada | `Reserva.en_disputa=True` en esa reserva; orden queda `capturada`; lo resuelve una persona. |
| Webhook perdido en una orden | `conciliar_pagos` orden-aware lo recupera (misma garantía que hoy para reservas sueltas). |
| Doble entrega del mismo webhook | `transaction.atomic` + `select_for_update` sobre la reserva y la orden; idempotente. |
| `ref` (código de vendedora) en una orden cruza-empresa | Se aplica solo a la `Reserva` de la `empresa_lider` (el código pertenece a una vendedora de una empresa). Las demás reservas de la orden quedan sin `vendedora`. |

---

## 7. Estrategia de pruebas

Mismo estándar que la expansión multi-sede: suite corre en SQLite (rápida) y en
Postgres con rol `ci_rls` sin `BYPASSRLS` (RLS, advisory locks y constraints reales).

**SP1:**

- `TransporteTarifa`: resolución de fila por `(tipo, zona, personas)`, rangos límite
  (4 vs 5 personas), zona obligatoria solo en `redondo_actividad`, cero filas → error.
- `PorRuta`: precio correcto por tipo/zona/tamaño en MXN y USD; moneda sin precio →
  `ValueError`.
- `DetalleTransporte.clean()`: XOR punto/dirección, zona vs hotel, empresa cruzada,
  `fecha_regreso` según tipo.
- `Reserva.clean()` generalizado: ventana horaria por servicio (dentro/fuera/sin
  ventana/pesca legacy 5–7am), tope de personas por servicio, `bajo_demanda` salta
  panga/capacidad/cupo pero exige deslinde web.
- `CrearPagoView` para transporte: congela precio y personas, anticipo del servicio,
  PaymentIntent en la cuenta de la Empresa 2, idempotencia.
- RLS: `TransporteTarifa` / `DetalleTransporte` aislados por empresa; guardarraíl
  "toda tabla con `empresa_id` tiene política" sigue verde.
- Frontend: `tsc --noEmit`, `eslint`, `build` limpios; la ruta `/traslados` renderiza
  con el catálogo mockeado. (Verificación visual la hace el dueño — ver
  `verificacion-sin-navegador`.)

**SP2:**

- `Orden`: transiciones de estado válidas e inválidas; `checkout_id` reutiliza orden.
- Paquete cruza-empresa: `PaqueteServicio.clean()` acepta componente de otra empresa
  de la misma sede, rechaza de otra sede; Σ repartos == precio del paquete.
- `crear-pago` de orden: N PaymentIntents en N cuentas, montos = reparto, metadata
  correcta, idempotencia (409 si capturada).
- `confirmar-captura`: las N `requires_capture` → captura todas; una no lista → void
  de las demás + `cancelada`.
- Webhook orden-aware: última reserva pagada → `Orden.capturada` + notificación
  combinada una sola vez; cupo lleno → compensación sobre los demás pagos.
- `conciliar_pagos` orden-aware: recupera webhook perdido; void tras timeout de orden
  incompleta; idempotente en segunda vuelta.
- Cada rama de la tabla de §6 tiene su test.
- Cleanup de "servicios removibles": la suite de paquetes sigue verde tras quitar el
  mecanismo; no queda referencia a `servicios_removidos` / `removible` /
  `ajuste_precio` en código ni en migraciones activas.

---

## 8. Secuencia de entrega

1. **Prerrequisito** (plan de corrección de hallazgos, sección nueva): quitar
   "servicios removibles" de paquetes. Independiente, se puede mergear a
   `fix/expansion-multi-sede-hallazgos` por separado.
2. **SP1** — transporte como servicio. Rama `feat/transporte-multi-empresa`. Se puede
   probar y (cuando mergee hallazgos) desplegar solo: la Empresa 2 vende traslados
   sueltos.
3. **SP2** — órdenes cruza-empresa + paquete Pesca + Traslado. Encima de SP1.

Ninguna de las 3 se mergea a `main` hasta que `fix/expansion-multi-sede-hallazgos`
esté mergeada (o se rebasa este trabajo sobre `main` ya con las correcciones dentro).

---

## 9. Decisiones del dueño (2026-09-07) y preguntas que quedan

**Resueltas:**

- **Reparto por empresa:** transporte a su `TransporteTarifa`, pesca (líder) se lleva
  el residuo. Sin campo nuevo. `Paquete.clean()` valida `precio_paquete ≥
  monto_transporte`. (§4.3)
- **Notificación combinada:** correo combinado (menciona pesca + traslado) + WhatsApp
  **por empresa** con las plantillas de Meta ya aprobadas. No se abre plantilla nueva
  en Meta para v1. (§4.4)
- **`forma_pago`:** paquetes cruza-empresa solo `completo` (100% en línea). (§4.7.1)
- **Deslinde:** **un solo deslinde** ampara a todas las empresas; el cliente marca una
  sola casilla. El texto actual del deslinde es específico de pesca y nunca se revisó
  para esto — hay una tarea de redacción (revisar/ampliar el texto para cubrir
  traslado y cualquier actividad, versión nueva de `deslinde_version`), con el texto
  final **pendiente de visto bueno del dueño / abogado antes de lanzar**. La estructura
  (una casilla, un `deslinde_*` por reserva copiado de la orden) no espera a eso.

**Que quedan (no bloquean los planes):**

1. `redondo_actividad` — ¿algún día tendrá precio por tamaño de grupo (como
   `redondo_aeropuerto`), o siempre plano por zona? El modelo lo soporta con otra fila
   de `TransporteTarifa`; es solo saber si cargarla.
2. Atribución de venta — si el `?ref=` es de una vendedora de la Empresa 1, ¿la parte
   de traslado (Empresa 2) también cuenta para ella? El plan asume que el `ref` se
   aplica solo a la `Reserva` de la `empresa_lider`. (La comisión se calcula fuera del
   sistema; esto solo define qué guarda el registro.)
3. Texto final del deslinde ampliado (ver arriba).
