# Checkout unificado de paquetes — diseño

Fecha: 2026-09-21. Autor de las decisiones: el dueño. Contador consultado para el
punto fiscal (D1). Derivación de UX hecha con perception-first-design (Modo 2).

Planes que implementan este diseño:
- `docs/superpowers/plans/2026-09-21-checkout-unificado-backend.md`
- `docs/superpowers/plans/2026-09-21-checkout-unificado-frontend.md`

## 1. Decisiones fijas (no reabrir sin el dueño)

- **D1. Sin Stripe Connect.** Cada empresa cobra directo en su propia cuenta de
  Stripe. En un paquete de dos empresas el cliente llena el formulario de tarjeta
  una vez por empresa, en secuencia. El contador confirmó que el sitio funciona
  solo como vitrina (las empresas son independientes, cada una factura su parte y
  la comisión de la plataforma se arregla fuera del sistema) y que dos formularios
  de pago no son problema. El modelo B del ADR-005 (N PaymentIntents con captura
  manual, `revertir_orden`) se queda tal cual.
- **D2. Misma experiencia para paquete de una empresa y de dos.** Mismo layout,
  misma estructura, una sola URL de cara al cliente: `/[lang]/reservar?paquete=…`.
  Cuando N=1 se omiten piezas, nunca se cambia la estructura. `/reservar-paquete`
  desaparece. Los servicios sueltos siguen en `/reservar` con `CheckoutView`.
- **D3. Extras agrupados por servicio**, no por empresa. Cada extra se cobra a la
  empresa dueña de su servicio (`ServicioPersonalizacion → Servicio → Empresa`). El
  cliente ve un solo total.
- **D4. Reglas de anticipo.** Servicio individual: sí, configurable (¿permite? +
  porcentaje). Paquete de una sola empresa: sí, configurable en el propio paquete;
  el anticipo de sus servicios se ignora. Paquete de dos empresas: nunca; el sistema
  lo impide. El porcentaje es editable.
- **D5. USD obligatorio también en paquetes de dos empresas.** La moneda se elige
  una vez para todo el pedido. Sin tipo de cambio: cada precio USD se captura a mano.
- **D6. Noches definidas por el paquete.** El cliente no elige noches ni fecha de
  salida en un paquete. El paquete fija las noches del hospedaje; el servidor calcula
  la salida.
- **D7. Día de cada componente definido por el paquete** (`dia_estancia`, 1 = día
  de llegada). El cliente solo elige la fecha de inicio del paquete.
- **D8. Personas por componente.** El cliente elige cuántas personas van a cada
  componente (ej. hospedaje ≠ actividad), con tope en lo que el paquete incluye
  (`personas_incluidas`). El precio del paquete no cambia si van menos. Los extras
  `cobrar_por_persona` multiplican por las personas de su propio servicio.
- **D9. Sin anticipo en paquetes de dos empresas** implica pago completo y captura
  manual; ya es el comportamiento de `CrearOrdenView`.
- **D10. Continuar reservación (APROBADA por el dueño, 2026-09-21; incluye fase 2 desde ya).** Cualquier checkout
  a medias (servicio suelto, paquete de una o de dos empresas) se puede retomar desde la portada y
  desde cualquier página del sitio, con un aviso visible. Detalle en la §10.

## 2. Requisitos de percepción (PFD Modo 2)

- **R1** Cada dato se pide una sola vez por pedido; cada pantalla ≤ 4-5 bloques y
  ≤ 4-7 campos; el contexto (empresa, monto, posición, lo ya autorizado) está en
  pantalla y no en la memoria del usuario. (Cowan 2010; Sweller 1988)
- **R2** El paso de pago 2 se registra como *avance*, no como repetición, en ≤ 50 ms:
  el ✓ del pago anterior y el sujeto nuevo (otra empresa, otro monto) son
  prominentes sin leer. (Lindgaard et al. 2006; Fogg 2003)
- **R3** Una sola anatomía repetida: mismas piezas en el mismo orden en cada paso de
  pago y en el checkout de una empresa (caso N=1). La identidad de cada paso vive en
  el contenido, no en la estructura. (Reber & Schwarz 1999; Wertheimer 1923)
- **R4** La predicción se fija **antes** del primer pago: N cargos, cada uno con
  empresa y monto, que suman exactamente el total mostrado, y lo que ocurre con la
  captura. Cada afirmación es cierta. (Clark 2013; Kahneman & Tversky 1979)
- **R5** Cada botón predice su resultado y su lugar en la secuencia (empresa + monto
  + posición); tras cada pago hay una sola acción primaria; al reanudar se reconstruye
  la secuencia en el paso correcto. (Pirolli & Card 1999; Thaler & Sunstein 2008)

## 3. Flujo y pantallas (aprobado por el dueño)

Una página, pasos como estado interno, `sessionStorage` para reanudar. Los pasos ya
completados se colapsan a una línea con "Cambiar" (mismo patrón que `CheckoutView`).
Montos del ejemplo: paquete 7,500 MXN, brunch 400, silla de bebé 150.

```
Reserva tu paquete                    [ MXN | USD ]        <- solo si TODOS los
Pesca + Traslado · La Paz                                     precios tienen USD

① Tus datos                (nombre, teléfono, correo)   -- una sola vez
② Pesca deportiva · de Sal y Sol
   Inicio del paquete · Hora · Personas (tope del paquete)
   ☐ Brunch              +$400
   ☐ Licencia de pesca   +$250
③ Traslado · de Transportes La Paz
   Tipo · Punto de recogida · Personas (tope del paquete)
   ☐ Silla de bebé       +$150
   (hospedaje: "3 noches · sales el 14 de octubre", solo texto)
④ Confirmar pedido
```

**Confirmar pedido** (el aviso solo si N > 1):

```
Tu pedido                                  Total $8,050
Pagarás en 2 cargos, uno por empresa:
  1  Sal y Sol                 $6,400
  2  Transportes La Paz        $1,650
Suman $8,050. Primero se autorizan los pagos y solo entonces se cobran.
Si algo falla, se libera o se te reembolsa lo autorizado.
[ ¿Pagar todo ahora | solo el anticipo? ]   <- solo paquete de 1 empresa con anticipo
☐ Acepto el deslinde
[ Continuar al pago 1 de 2 ]
```

**Pagos** (misma anatomía en todos; el ya hecho queda arriba con peso visual):

```
Pago 1 de 2
● Sal y Sol  $6,400      ○ Transportes La Paz  $1,650
[ tarjeta / Link / monedero ]
[ Pagar $6,400 a Sal y Sol · 1 de 2 ]

✓ Sal y Sol  $6,400 — autorizado
Pago 2 de 2 · el último
● Transportes La Paz  $1,650
[ tarjeta ]
[ Pagar $1,650 a Transportes La Paz · 2 de 2 ]
```

Con **una empresa**: "Confirmar pedido" sin el aviso; un solo pago, botón
"Pagar $X", sin "1 de 1" ni barra de progreso.

La empresa se muestra en tres puntos: etiqueta secundaria en cada grupo de servicio,
en el resumen y de forma prominente en cada pago. No en cada campo (R1).

**Texto sujeto a verificación y sin garantías absolutas:** el sistema autoriza todos los pagos y solo
entonces captura (modelo B). Si algo falla, `revertir_orden` cancela las autorizaciones o
reembolsa lo ya capturado; pero un reembolso puede tardar o fallar, y mientras tanto el cargo
existe. Por eso el aviso y el mensaje de fallo dicen "se libera o se te reembolsa lo
autorizado" y **no** prometen "no se te cobra". Antes de fijar el texto hay que comprobar con
una tarjeta de prueba cómo aparece en el banco un cargo autorizado y no capturado (sección 9).

## 4. Modelo de datos

Sin tablas nuevas (evita políticas RLS y la lista blanca de `tests_rls.py`). Solo
columnas.

**`fleet.Servicio` y `fleet.Paquete`**
- `permite_anticipo` BooleanField, default `True` (conserva el comportamiento actual).
- `porcentaje_anticipo` con validadores 1..99.
- Migración de datos: filas con `porcentaje_anticipo >= 100` → `permite_anticipo=False`
  y `porcentaje_anticipo=30`.
- `Paquete.es_cruza_empresa` (property) y `Paquete.anticipo_disponible` =
  `permite_anticipo and not es_cruza_empresa`. `Servicio.anticipo_disponible` =
  `permite_anticipo`.

**`fleet.PaqueteServicio`**
- `dia_estancia` PositiveSmallInteger, default 1.
- `noches` PositiveSmallInteger, null. Solo componentes `por_noche` (los hospedajes que ya estaban en un paquete quedan con 1 noche por omisión; el dueño ajusta el valor real).
- `personas_incluidas` PositiveSmallInteger, default 2.
- `empresa` FK a `tenancy.Empresa`, no editable: copia de `servicio.empresa`. Permite contar las
  empresas de un paquete sin unir con `Servicio`, que RLS oculta entre empresas (la política de
  `fleet_paqueteservicio` solo deja ver las filas al alcance de la empresa líder).

**`bookings.Reserva`** (paquete de una sola empresa)
- `personas_por_servicio` JSONField, default `dict`: `{"<servicio_id>": n}`.
- `numero_personas` pasa a ser las personas del componente operativo principal
  (el primer componente `por_recurso_dia`; si no hay, el primero por `orden`).
- `inicio_paquete` DateField, null: primer día del paquete que eligió el cliente. Se **guarda**;
  no se deriva de las noches del catálogo (editarlas no debe mover reservas ya vendidas).
  `Reserva.fecha_inicio_paquete` = `inicio_paquete` o, si no hay, `fecha`.

## 5. Calendario del paquete (regla única, módulo puro)

`apps/fleet/calendario_paquete.py` es la única fuente de esta aritmética; backend y
frontend la replican con el mismo vector de prueba (sección 7).

Dado `inicio` (fecha de inicio elegida por el cliente):
- fecha de un componente = `inicio + (dia_estancia − 1)` días.
- `fecha_salida` del hospedaje = `inicio + noches`.
- `fecha_regreso` de un traslado `redondo_aeropuerto` = `inicio + noches` si el
  paquete tiene hospedaje; si no, la elige el cliente como hoy.

**Paquete de una sola empresa (una `Reserva`).** El motor de cupo, la agenda y la
regla de una salida por día leen `Reserva.fecha`, así que `Reserva.fecha` debe ser el
día de la actividad operativa (ancla): `fecha` = `inicio + (dia_ancla − 1)`, donde
`dia_ancla` es el `dia_estancia` de los componentes `por_recurso_dia` (todos deben
coincidir). Si no hay ninguno, `fecha = inicio`. El inicio del paquete se guarda en
`Reserva.inicio_paquete`.

**Paquete de dos empresas (una `Reserva` por componente).** Cada reserva lleva su
propia fecha calculada.

Reglas de validación de un paquete (`apps/fleet/paquete_reglas.py`):
1. Cruza-empresa ⇒ `permite_anticipo=False`.
2. Cruza-empresa ⇒ como máximo un componente por empresa (`crear_pagos_orden` reparte
   por empresa y asume una reserva por empresa).
3. A lo más un componente `por_noche`.
4. `por_noche` ⇒ `noches ≥ 1`; los demás ⇒ `noches` vacío.
5. `dia_estancia ≥ 1`. Con hospedaje: `dia_estancia ≤ noches` (la actividad cae antes
   del día de salida; límite v1). Sin hospedaje: `dia_estancia = 1` (paquete de un día).
6. Los componentes `por_recurso_dia` comparten el mismo `dia_estancia`.
7. `1 ≤ personas_incluidas ≤ tope del servicio` (`capacidad_maxima`, o 5 si es de
   `por_recurso_dia` sin capacidad; el hospedaje se valida contra habitaciones al
   reservar, no aquí).
8. Precio del paquete ≥ peor tarifa de transporte aplicable a `personas_incluidas`
   (en MXN y, si hay precio USD, en USD).
9. Paquete de una empresa: las actividades (`por_recurso_dia`) van con el mismo número de personas
   (el motor de cupo cuenta un solo `numero_personas` por reserva). El tope global de 5 personas no
   aplica a reservas de paquete: cada componente tiene el suyo (`personas_incluidas`).

Cuándo se validan: en el admin, con el estado **nuevo** del formulario (el modelo no valida entre
filas porque leería la BD vieja); y **antes de vender** (reserva de paquete y orden), leyendo la
configuración bajo RLS. Un paquete guardado por otra vía (shell, script) no llega a cobrarse mal.

## 6. Contrato de API

**Catálogo** `GET /api/sedes/<sede>/paquetes/<slug>/` — debe devolver los componentes de **todas**
las empresas del paquete también bajo RLS (Tarea 2.7 del backend), y agrega:
- Paquete: `permite_anticipo` (efectivo: false si es cruza-empresa), `porcentaje_anticipo`,
  `es_cruza_empresa`, `noches` (del componente por noche o null).
- `servicios_asociados[i]`: `dia_estancia`, `noches`, `personas_incluidas`.
- Servicio: `permite_anticipo`, `porcentaje_anticipo`.

**Paquete de una empresa** `POST /api/<empresa>/reservas/` — `fecha` es el inicio del
paquete; nuevo `personas_por_servicio`; `fecha_salida` se rechaza (400) porque la
define el paquete. La respuesta trae `fecha_inicio_paquete` (solo lectura); el estado de la reserva (`pendiente_pago` y
`pagada`) también devuelve `fecha_inicio_paquete` y `personas_por_servicio`.
`POST …/crear-pago/` rechaza `forma_pago=anticipo` (400) si el producto no lo admite.

**Paquete de dos empresas** `POST /api/<sede>/ordenes/` — `fecha` es el inicio;
`componentes[]` con `{servicio, numero_personas, hora?, tipo_traslado?,
punto_encuentro?, direccion_personalizada?, zona?, personalizaciones:[{id, cantidad?,
respuesta?}]}`. El servidor rechaza `fecha` por componente y `fecha_regreso` cuando el
paquete tiene hospedaje. `POST …/crear-pago/` devuelve la misma lista de pagos de hoy
(`empresa_slug`, `monto`, `client_secret`, `publishable_key`) y responde 400 si falta
un precio del paquete o de la tarifa de traslado en la moneda pedida; un **extra** sin precio en la
moneda responde 503 (como el cobro de una reserva suelta) y la UI lo deshabilita en esa moneda.

## 7. Dinero y vector de prueba compartido

Reparto (ya existe, `pricing.monto_por_empresa`): cada componente de transporte va a su
tarifa; la líder absorbe el residuo. Nuevo: a cada empresa se le suman los extras de sus
propios servicios.

**Vector** (backend y frontend deben coincidir): paquete 7,500 MXN; traslado
`redondo_actividad` zona `centro` a 1,500; brunch (pesca) 400 fijo; silla de bebé
(traslado) 150 fijo. Resultado: Sal y Sol (líder) = 7,500 − 1,500 + 400 = **6,400**;
Transportes La Paz = 1,500 + 150 = **1,650**; total **8,050**.

Extras `cobrar_por_persona`: precio × personas del componente dueño del extra.

## 8. Fuera de alcance (v1)

- Actividad en el día de salida del hospedaje (`dia_estancia = noches + 1`).
- Dos hospedajes en un mismo paquete; dos servicios de una misma empresa en un paquete
  cruza-empresa.
- Anticipo en paquetes de dos empresas.
- Mostrar los extras en el correo combinado de la orden (`notificar_orden_pagada`).
- Reservar un paquete de una empresa a través de `Orden` (se mantiene `Reserva` única
  para conservar el anticipo).

## 9. Pendientes del dueño (no bloquean construir)

- Verificar con tarjeta de prueba cómo aparece en el banco un cargo autorizado y no
  capturado; con eso se fija el texto del aviso de "Confirmar pedido".
- Garantía monetaria: confirmar con el dueño y con `revertir_orden` qué se le dice al cliente cuando
  una empresa alcanzó a capturar antes de que otra fallara (hoy: "se libera o se te reembolsa lo
  autorizado").
- Texto de "el precio no cambia si se usan menos lugares" (lugares no usados sin
  reembolso): necesita visto bueno del dueño o del abogado, igual que el deslinde.
- Cargar precios USD de las tarifas de transporte y de los paquetes de dos empresas.
- Qué hacer con la Sección 10 de SP2: se cierra tal cual, este diseño no la reemplaza.

## 10. Continuar reservación (APROBADA por el dueño 2026-09-21, incluida la fase 2 — correo/WhatsApp para otros dispositivos)

**Problema.** Hoy un checkout solo se recupera si el cliente vuelve a la misma URL en la misma
pestaña (`checkout_id` en `sessionStorage`). Si cierra la pestaña o vuelve por la portada o por
Google, no ve nada y empieza de cero; en un paquete de dos empresas eso puede dejar un pago ya
autorizado y una orden a medias. Debe funcionar para **todos** los servicios y paquetes.

**Requisitos (R1-R5 de esta pieza).**
- R1 Una sola decisión y pocas señales: el aviso lleva una acción principal y como máximo tres
  datos de reconocimiento (producto, estado en palabras, hace cuánto).
- R2 Prominente y personal: visible sin hacer scroll al volver, con peso propio, y **cero píxeles**
  para quien no tiene nada pendiente (la primera impresión de un visitante nuevo no cambia).
- R3 Continuidad reconocible: el destino repite los mismos nombres, el mismo paso y los datos ya
  llenados; nunca parece un checkout nuevo y vacío.
- R4 Verdad sobre el dinero primero: dice qué está pagado o autorizado y qué falta, solo con lo que
  el servidor confirma; sin urgencia inventada; descartar nunca se siente como perder algo pagado.
- R5 Un botón que predice su resultado y cae en el paso exacto; todo estado de falla deja una
  siguiente acción clara.

**Solución.**
1. *Puntero, no datos.* El navegador guarda en `localStorage` un puntero versionado, máx. 3 y con
   vigencia de 7 días: `{ tipo: "reserva"|"orden"|"traslado", checkoutId, ordenId?, sedeSlug,
   empresaSlug, productoSlug, productoNombre, ruta, actualizadoEn }`. **Nada de tarjeta, nombre,
   teléfono ni correo.** La fuente de verdad es el servidor. Se escribe al primer guardado en el
   servidor (`guardarReserva`, `crearOrden`), se actualiza al avanzar y se borra al pagar/cancelar.
2. *Un componente, dos presentaciones.* `ContinuarReservacion`: **banda delgada** justo bajo el
   header en la portada (encima del hero, empujando el contenido con una transición de altura; solo
   para quien tiene algo pendiente) y **chip** en el header en el resto de las páginas (sedes,
   catálogo, servicio). En la portada solo se muestra la banda, no el chip. No aparece dentro del
   checkout. Es un componente autocontenido, sin tocar el layout del hero.
3. *Qué dice.* Producto + estado + antigüedad: "Pesca + Traslado · falta el pago 2 de 2 · hace
   20 min". Con dinero ya autorizado añade el monto pendiente y la hora real de vencimiento de la
   autorización (24 h, `ORDEN_TIMEOUT_AUTORIZACION`): un dato verdadero, no presión. Sin monto ni
   datos personales cuando no hay pago autorizado.
4. *Acción.* Principal: "Continuar reservación" (con dinero en juego: "Terminar mi pago"). Al hacer
   clic se siembra la sesión con el `checkoutId`/`ordenId` del puntero y se navega a la `ruta` del
   producto; el checkout repone lo llenado desde el servidor y salta al paso correcto (pagos hechos
   marcados con ✓). Requiere que el servidor devuelva el estado pendiente completo de reservas y de
   órdenes (incluida una orden en `armando`).
5. *Validación antes de afirmar.* La banda consulta un resumen sin datos personales; solo entonces se
   muestra. Si el servidor dice que ya no existe o expiró, la banda pasa a un mensaje neutro con una
   sola acción ("Empezar una nueva reservación de {producto}"); si una orden se canceló, una sola vez:
   "Tu reserva anterior se canceló y lo retenido se liberó" (texto exacto final en §10.1).
6. *Descartar.* Sin pago retenido: "Descartar" solo borra el puntero. Con pago retenido: no hay
   "X" simple; la única salida es "Cancelar y liberar lo retenido", con confirmación que dice qué
   se libera, y llama al servidor (`revertir_orden`).
7. *Varias pendientes.* Se muestra la más reciente; un enlace "y 1 más" abre una lista corta (máx. 3)
   con la misma anatomía. Sin dinero retenido, la de menor antigüedad cede el lugar al llegar la 4.ª.
8. *Otros dispositivos (fase 2, decisión del dueño).* Enlace "retomar" en el correo o WhatsApp de
   checkout abandonado (ya existe para la vendedora) y, tras la primera autorización de un paquete de
   dos empresas, un correo "Tu reserva sigue abierta: falta el pago 2". El `checkout_id` funciona como
   llave de acceso, igual que hoy.

**Backend necesario.** Endpoints de *resumen* sin datos personales: `GET /api/<empresa>/reservas/resumen/
?checkout_id=` y `GET /api/<sede>/ordenes/resumen/?checkout_id=` con `{ estado, producto, paso,
pagos:[{empresa, monto, estado}], vence_en }`; el estado de una orden (`GetOrdenView`) debe traer lo
necesario para reponer el formulario; `POST /api/<sede>/ordenes/<id>/cancelar/` (prueba de posesión
del `checkout_id`, llama a `revertir_orden`); estado `expirada` para lo que el servidor ya cerró.

**Frontend necesario.** `lib/pendientes.ts` (lectura/escritura del puntero, versionado, tope 3,
vigencia); los tres checkouts (`CheckoutView`, `TrasladoView`, `PedidoPaquete`) escriben y borran el
puntero y adoptan el `checkoutId` sembrado; `ContinuarReservacion` (banda y chip, es/en) montado en el
header y en la portada.

**Decidido (dueño, 2026-09-21).** §10 y §10.1 aprobadas tal cual, incluida la fase 2. Quién confirma una
devolución marcada `requiere_atencion`: una vendedora o un admin (ver rol Vendedora/Jefe en
`backend/CLAUDE.md`, sección "Roles"), desde el admin — no un flujo nuevo de personas, se apoya en los
roles existentes. El montaje en la portada se hace ya, en paralelo a la revisión visual del hub
(cambios sin commitear del worktree): el componente `ContinuarReservacion` es autocontenido y no
depende de cómo quede el hero.

**Pendiente técnico (no de negocio):** texto exacto de cada aviso en inglés; diseño de la pantalla de
"requiere atención" en el admin.

### 10.1 Matriz de estados de "Continuar reservación" (R4 y R5; APROBADA)

**Regla de oro (R4).** El texto que ve el cliente sale de un enum `situacion` que calcula el
**servidor**; el navegador nunca infiere. Cada situación tiene una sola frase y cada frase afirma solo
lo que esa situación garantiza. **Prohibido** decir "no se te cobró" o dar plazos bancarios ("en 5 días").
**Vocabulario único** (banda, checkout, confirmación, correo): *retenido* (autorización sin cobrar),
*cobrado*, *liberado*, *devolución*. Esto **reemplaza** el "autorizado" de la §3 en todo lo que ve el cliente (decidido, 2026-09-21):
clave `pedido.authorized` → "retenido en tu tarjeta"; en la matriz de la §3 ("✓ Sal y Sol $6,400 —
autorizado") el texto pasa a "retenido". "Autorizado"/"autorización" quedan como término interno
(código, admin, docs), nunca de cara al cliente.

Contrato del resumen: `{ situacion, producto, sede, montos:[{empresa, monto, estado}], vence_en?,
folio, actualizado_en }` (sin datos personales). `folio` = número de orden o de reserva.

| `situacion` | Texto (línea 1 · línea 2) | Principal | Secundaria | Al hacer clic |
|---|---|---|---|---|
| `sin_pago` | {Producto} · Tus datos están guardados · Aún no has pagado | Continuar reservación | Descartar (solo borra el puntero; "Deshacer" 8 s) | Producto en el paso donde quedó, con lo llenado repuesto |
| `retenido_parcial` (pago 1 de 2) | {Producto} · Pago 1 de 2 retenido: $6,400 en Sal y Sol · Falta $1,650 a Transportes La Paz. Se cancela si no terminas antes de las 3:40 p. m. | Pagar $1,650 (pago 2 de 2) | Cancelar y liberar lo retenido | Pantalla del pago 2, con "✓ Sal y Sol $6,400 retenido" |
| `retenido_total` / `confirmando_cobro` | {Producto} · Tus dos pagos están retenidos ($6,400 + $1,650). Estamos confirmando el cobro. | Ver estado | — | Pantalla de progreso (consulta hasta que el servidor confirme) |
| `pago_en_proceso` (una empresa) | {Producto} · Tu banco está procesando tu pago de $X. | Ver estado | — | Pantalla de progreso |
| `confirmada` (una sola vez) | {Producto} · Tu reservación está confirmada. Se cobró $6,400 a Sal y Sol y $1,650 a Transportes La Paz. (con anticipo: "Se cobró el anticipo de $X.") | Ver mi reservación | Cerrar (borra el puntero) | Pantalla de confirmación |
| `cancelada_liberada` | {Producto} · Se canceló porque no se pudo completar un pago. Se liberó lo retenido en tu tarjeta. | Reservar de nuevo | Entendido | Producto desde cero (con lo llenado, si el servidor lo conserva) |
| `cancelada_devolucion_solicitada` | {Producto} · Se canceló. Ya solicitamos la devolución de $6,400. Tu banco puede tardar en mostrarla. | Ver detalle | Entendido | Pantalla de detalle con folio |
| `cancelada_devolucion_por_confirmar` | {Producto} · Se canceló. Estamos confirmando la devolución de $6,400 y te escribiremos en cuanto la tengamos. Folio #{folio}. | Escribir por WhatsApp (mensaje con folio) | Entendido | WhatsApp prellenado; el servidor marca `requiere_atencion` para el equipo |
| `expirada` (con retención vencida) | {Producto} · Pasó el tiempo para terminar el pago y se liberó lo retenido en tu tarjeta. | Reservar de nuevo | Entendido | Producto desde cero |
| `expirada` (sin dinero) | {Producto} · Esta reservación ya no está activa. | Empezar de nuevo | Entendido | Producto desde cero |
| `no_existe` (404) | No encontramos tu reservación de {producto}. Si ya habías pagado, revisa tu correo de confirmación o escríbenos con tu folio. | Empezar de nuevo | Escribirnos por WhatsApp | Producto desde cero / WhatsApp |
| sin conexión | {Producto} · Sin conexión. Revisaremos tu reservación cuando vuelva la señal. (Sin ninguna afirmación de estado ni de dinero.) | Reintentar | — | Reintenta el resumen; al recuperar señal se re-evalúa solo |
| error del servidor / tiempo agotado | {Producto} · No pudimos revisarla ahora. Intenta de nuevo en un momento. | Reintentar | Ir a mi reservación (el checkout valida por su cuenta) | Reintenta / abre el checkout |

**Tres registros visuales (R2), por peso y no por alarma:** *en curso* (`sin_pago`, `pago_en_proceso`,
`confirmando_cobro`): banda neutra; *con dinero en juego* (`retenido_parcial`, `*_por_confirmar`):
banda de mayor peso, con la hora real de vencimiento cuando aplica; *informativo/cerrado*
(`confirmada`, `cancelada_*`, `expirada`, `no_existe`): banda calmada, una sola vez, con descarte. Sin
rojo de alarma en estados que no son un daño; el color nunca es la única señal.

**Descartar con dinero retenido.** No hay "X". La secundaria abre una hoja de confirmación: título "¿Cancelar
tu reservación?"; cuerpo "Se liberará el pago de $6,400 retenido en tu tarjeta. No se cobrará nada más. Puedes
reservar de nuevo cuando quieras."; botones "Volver" (el predeterminado) y "Sí, cancelar y liberar". La
interfaz muestra el resultado que **devuelve el servidor** (`cancelada_liberada` o
`cancelada_devolucion_por_confirmar`), nunca uno optimista.

**Sin culpar.** Las fallas se describen como "no se pudo completar un pago", sin atribuirlas a la tarjeta
salvo que el servidor lo confirme.

**Backend adicional.** Campo `situacion` (enum arriba) calculado desde Orden/Reserva/PaymentIntents/reembolsos;
`folio`; `vence_en` (creación de la autorización + `ORDEN_TIMEOUT_AUTORIZACION`; la liberación real la hace
`conciliar_pagos` cada hora, por eso el texto dice "se cancela si no terminas **antes de**"); `requiere_atencion`
en la orden/reserva cuando quede una devolución por confirmar (visible en el admin); registrar el resultado de
cada `payment_intents.cancel` y `refunds.create` en `revertir_orden` (hoy solo se registra un error en el log y se
cancela igual). Pendiente operativo del dueño: quién confirma las devoluciones marcadas `requiere_atencion`.
