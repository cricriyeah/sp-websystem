@AGENTS.md

# CLAUDE.md — frontend/

Notas especificas de este modulo. Contexto de negocio completo: ../docs/contexto-negocio.md.

## Next.js 16 — cuidado con supuestos de entrenamiento

Este proyecto usa Next.js 16.3.0 (Turbopack). Antes de asumir una API de versiones anteriores,
revisa `node_modules/next/dist/docs/` (AGENTS.md de este repo ya lo indica). Cambio clave ya
aplicado aqui: `middleware.ts` fue renombrado a `proxy.ts` (exporta `proxy`, no `middleware`).

## Turbopack cachea los diccionarios

Al editar `dictionaries/{es,en}.json` (o renombrar props entre archivos), **reinicia
`npm run dev`**. Turbopack no invalida esos modulos y sigue sirviendo la version vieja:
aparece un `Cannot read properties of undefined` sobre una clave que si existe en el
JSON. La señal para distinguirlo de un bug real es que `npx tsc --noEmit` y
`npm run build` pasan limpios, y que la linea del stack trace no corresponde con el
archivo actual. Los `.tsx` sueltos si los recoge el HMR.

## Enrutamiento es/en

- Todo vive bajo `src/app/[lang]/` (layout, page, dictionaries). No hay `layout.tsx`/`page.tsx`
  sueltos en `src/app/` — el root layout es el de `[lang]`.
- `src/proxy.ts` redirige segun `Accept-Language`; locale por defecto `es`.
- Diccionarios: `src/app/[lang]/dictionaries.ts` + `dictionaries/{es,en}.json`. Patron:
  agregar clave nueva a ambos JSON, usar `getDictionary(lang)` en Server Components.
- `params` es async (`Promise`) en pages/layouts — usar `await params`, tipos `PageProps<'/[lang]'>`
  / `LayoutProps<'/[lang]'>`.

## Checkout unificado de paquetes

La ruta única para paquetes es `/[lang]/reservar?paquete=<slug>&sede=<slug>`.
`src/app/[lang]/reservar/page.tsx` consulta el paquete y monta
`src/components/pedido/pedido-paquete.tsx` (`PedidoPaquete`); si falta
`sede` o no existe el paquete, responde con `notFound()`. Los servicios
sueltos y la pesca legacy siguen en `CheckoutView` dentro de esa misma
ruta. Los traslados tienen su checkout en `/[lang]/traslados` y
`traslado-view.tsx`.

- `PedidoPaquete` elige `motor = 'reserva'` para un paquete de una empresa y
  `motor = 'orden'` para varias (`paquete.es_cruza_empresa`). Los dos pasan
  por `src/components/pedido/use-pago-pedido.ts`: `reserva` crea una reserva
  y un pago, y espera el estado `pagada` del webhook; `orden` crea una
  orden y N pagos secuenciales con captura manual, llama a
  `confirmar-captura` y solo muestra éxito al ver `capturada`. Un error de
  red durante la captura conserva la orden y reintenta la consulta.
  Si Stripe no está configurado, el error 503 se traduce a
  `checkout.paymentUnavailable` sin romper el checkout.
  `src/components/pedido/use-pedido-estado.ts` envuelve el reducer puro de
  `src/lib/pedido-estado.ts`, que guarda contacto, inicio, moneda, forma de
  pago y selecciones por servicio.
- Según R1-R5 del [spec](../docs/superpowers/specs/2026-09-21-checkout-unificado-design.md)
  y la Sección 3 del [plan](../docs/superpowers/plans/2026-09-21-checkout-unificado-frontend.md),
  cada dato se pide una vez; los grupos de servicio terminados se colapsan
  con opción de cambiar. Antes del primer pago, `AvisoCargos` enumera
  empresa y monto de cada cargo, su suma y la regla de retención/captura
  (solo cuando hay varios cargos). En cada pago, `EncabezadoPago` marca
  los anteriores como hechos/retenidos, destaca el actual y deja los demás
  pendientes; el botón indica empresa, monto y posición. Con un solo pago
  se conserva la misma anatomía sin encabezado de secuencia. Hay un solo
  `StripePanel`/`Elements` a la vez, remontado por empresa mediante
  `key={pasoPago.empresaSlug}`; cada cuenta recibe su propia publishable
  key y client secret del backend.
- `src/lib/calendario-paquete.ts` deriva los días por componente y la salida
  desde `dia_estancia` y las noches del hospedaje (espejo de la regla
  del backend); la fecha inicial se
  elige una vez. `personas_incluidas` fija las personas iniciales por
  servicio y cada grupo puede ajustarlas. Los precios, topes y porcentajes
  vienen del catálogo; `src/lib/pedido-paquete.ts` calcula solo la vista
  previa y el servidor determina el cobro real. USD se ofrece para el
  pedido completo solo con precio ancla y tarifas de traslado en USD;
  si falta el precio USD de un extra elegido, no se calcula el pedido.
  No hay conversión de moneda. El anticipo de paquete solo se ofrece
  para una empresa si `paquete.permite_anticipo`, con
  `paquete.porcentaje_anticipo`. `CheckoutView` y `traslado-view.tsx`
  también respetan `servicio.permite_anticipo` y su porcentaje; en caso
  contrario fuerzan pago completo.
- Un rechazo de tarjeta en una orden no borra el formulario. El hook
  solicita `confirmar-captura` para que el backend revierta la orden
  incompleta y, si ocurrió en esta sesión,
  `reintentar()` crea otra orden con un `checkout_id` nuevo; `reiniciar()`
  vuelve al formulario sin recargar. `aviso-fallo.tsx` muestra la empresa
  que rechazó y el motivo del banco traducido por `src/lib/fallo-pago.ts`.
  Si el segundo pago falla con el primero retenido, avisa de esa retención;
  `src/lib/fallo-pago.ts` habilita ayuda desde el tercer fallo y
  `src/lib/contacto.ts` arma el enlace de WhatsApp. Tras una
  recarga con la orden cancelada, el motivo bancario no se reconstruye:
  el frontend conocía el índice del pago en vivo y el backend no devuelve
  ese detalle.
- La reanudación de paquete usa `sessionStorage` bajo
  `salysol:pedido:<slug>` y guarda `checkoutId`/`ordenId`; consulta el
  servidor y omite pagos ya `requires_capture` o `succeeded`.
  `CheckoutView` usa `salysol:checkout-id` y traslados usa
  `salysol:traslados:checkout_id`: cada flujo tiene su propio
  `checkout_id`. Es reanudación de la pestaña, no el aviso global de
  "Continuar reservación" de la Sección 5.
- Los servicios sueltos usan `servicio.precio_base` y, para hospedaje
  `por_noche`, envían `fecha_salida`; las personalizaciones elegidas
  viajan sin precio para que el servidor las valore. `empresaSlug`
  selecciona la cuenta de cobro desde `&empresa=` para servicios sueltos,
  o desde `NEXT_PUBLIC_EMPRESA_SLUG` para pesca legacy. El deslinde se
  acepta una vez, enlaza a `/[lang]/deslinde` y su nombre sale de los
  datos de contacto. `DateField`
  y `TimeField` usan `FieldPopover`; no añadir selectores nativos de
  fecha. Para fechas ISO, usar `fromLocalISODate`/`toLocalISODate` de
  `src/lib/dates.ts` y evitar parsear fechas ISO como UTC.
- Transiciones y piezas compartidas del checkout: todo lo que aparece, se
  pliega o cambia de sitio (código promocional y sus mensajes, mes del
  calendario, bloques del traslado, avisos de un extra) pasa por
  `components/checkout/despliegue.tsx` (`Despliegue`: altura + opacidad con
  la misma curva de `CheckoutSectionCard`, solo opacidad con "reducir
  movimiento"). No renderices condicionalmente con `&&` algo que el cliente
  ve aparecer: el contenido de abajo brinca. El tipo de traslado se pinta con
  `components/checkout/tipo-traslado-cards.tsx` en `/traslados` y en el paquete
  (en el paquete sin "Desde $": el traslado va incluido). `PanelCalendario`
  tiene ancho fijo en un popover y `anchoCompleto` cuando va en línea. La fecha
  de regreso del traslado (`FechaRegresoCompacta`) es obligatoria: se ve con
  la tira semanal abierta hasta que hay fecha, y entonces se pliega a una fila
  con "Modificar" (nunca un botón "Elegir", que la haría parecer opcional);
  no se prellena. La tira cambia de semana deslizando en la dirección del
  click. Las listas cortas usan `SelectPersonalizado` (sobre `FieldPopover`),
  no `<select>` nativo. Los errores que bloquean se quedan en la tarjeta,
  pegados a su campo (los toasts se auto-descartan: son para avisos): usa
  `<ErrorDeCampo id mensaje={error} />` siempre montado, que entra/sale con
  `Despliegue` y, si queda fuera de pantalla, hace scroll y lleva el foco al
  campo con `aria-describedby` igual al id.
- Anatomía de la tarjeta de traslado (y de cualquier tarjeta con controles):
  una pregunta por bloque; los controles que se contestan dentro de una caja
  (hotel, personas, aeropuerto, listas) usan `CAJA_CAMPO` de
  `components/checkout/estilos.ts` con `compacto` en `FieldPopover` /
  `PeopleStepper` (relleno de 16 px, borde izquierdo alineado con las filas de
  tipo); los grupos de opciones y la fecha llevan su pregunta como título
  arriba. Orden por causalidad: tipo → regreso (solo aeropuerto) → dónde →
  personas (prellenado, al final y callado) → extras. Las preguntas que
  aparecen y desaparecen llevan su separación (`pt-5`) dentro del bloque y no
  en el `gap` del cuerpo, para que al desplegarse no brinque el hueco. Los
  enlaces secundarios usan `ENLACE_SECUNDARIO`. El tipo de traslado va en
  lista (descripción completa), no en columnas. La tira semanal arranca en
  el primer día reservable y avanza de 7 en 7 (`lib/calendario-semana.ts`):
  sin celdas pasadas que no se pueden tocar.
- Pruebas desde `frontend/`: `npm.cmd test` ejecuta
  `tests/run-hub-tests.cjs` (una suite por módulo puro). Para una sola,
  `npm.cmd test -- calendario-paquete`; al añadir un módulo, registrar
  su nombre y archivo en `suites` de ese runner. Gate de la sección:
  `npx.cmd tsc --noEmit`, `npx.cmd eslint src tests`, `npm.cmd test` y
  `npm.cmd run build`.

## Continuar reservación (banda global)

`ContinuarReservacion` (`src/components/continuar-reservacion.tsx`) es una
banda bajo el header que aparece en **todo el sitio** (hub, sedes, servicio,
privacidad, deslinde…) salvo dentro del checkout (`/reservar`, `/traslados`),
donde el propio checkout ya retoma la reserva. No existe versión "chip".

- Lo monta `SiteHeader` (recibe `continuar={dict.continuar}`; una página que
  no lo pase no muestra banda). Como el header es `fixed` y las páginas se
  apartan con `--nav-alto`, el header mide la banda con `ResizeObserver` y
  escribe `--banda-alto` en `<html>`; `--nav-alto` (globals.css) ya lo suma,
  así el contenido baja solo. Sin banda vale `0px` y nada cambia. No pongas
  alturas de header a mano en una página nueva: usa `var(--nav-alto)`.
- Lee el puntero de `src/lib/pendientes.ts` (`localStorage`, máx. 3, 7 días;
  sin cuentas esa llave es lo único que hay, así que solo sirve en el mismo
  navegador) y consulta el resumen al servidor; el texto sale de la
  `situacion` que calcula el backend (`src/lib/pendientes-texto.ts`), nunca se
  infiere en el navegador. Sin pendientes, o mientras carga, no pinta nada.
- Los tres checkouts escriben el puntero al crear la orden/reserva y
  `use-pago-pedido.ts` lo reasegura al reanudar una orden abierta.
- `confirmada` solo ofrece "Cerrar"; `cancelada_devolucion_solicitada` lleva
  el folio y un WhatsApp prellenado. No hay página de "Mi reservación".

## Atribucion de ventas (?ref=)

La vendedora le pasa a sus clientes un link con su codigo (`?ref=maria`) y la venta
queda a su nombre en el backoffice (ver `backend/CLAUDE.md`, "Registro de ventas").

- `RefCapture` va montado en `[lang]/layout.tsx` y guarda el codigo en cualquier pagina
  del sitio, no solo en el checkout: el link puede caer en la portada y el cliente
  llegar a `/reservar` tres clics despues, cuando el parametro ya se perdio.
- Lee `window.location.search` y **no** `useSearchParams()`: ese hook saca de la
  pre-renderizacion estatica a toda pagina que lo use, y aqui no hay nada que
  renderizar — solo se escribe en localStorage.
- El codigo vive 30 dias en localStorage (`src/lib/ref.ts`) y viaja como `ref` en
  `guardarReserva`. El backend ignora en silencio el que no resuelva.

## Ruta /traslados (checkout de transporte)

`[lang]/traslados/page.tsx` es el punto de entrada server-side para cotizar y reservar traslados terrestres privados:

- **Server Component + SSR**: obtiene el diccionario con `getDictionary(lang)` y el catálogo con `getTraslados(empresaSlug)` (vía `GET /api/<empresa>/traslados/`). El slug se toma de `searchParams.empresa` o `NEXT_PUBLIC_TRANSPORTE_EMPRESA_SLUG` (por defecto `'transporte-la-paz'`).
- **Resiliencia**: si la API de traslados devuelve 404 o 503 (ej. Stripe no configurado en esa empresa), la página muestra un estado accesible de servicio no disponible sin reventar. Cuenta con `loading.tsx` con esqueletos visuales durante la carga.
- **Componente `traslado-view.tsx`**:
  1. Paso 1 — Tipo de traslado: 3 modalidades (`redondo_aeropuerto`, `redondo_actividad`, `recepcion_aeropuerto`) con precios base calculados desde las tarifas del catálogo.
  2. Paso 2 — Hospedaje: selector `<FieldPopover>` con `puntos_encuentro` predefinidos u opción de ingresar dirección libre (con selector de zona solo si el tipo de traslado es `redondo_actividad`).
  3. Paso 3 — Fechas y horario: `DateField` para fecha de inicio y fecha de regreso (solo si aplica), y `TimeField` sin ventanas fijas restrictivas (el transporte opera en cualquier horario).
  4. Paso 4 — Personas: selector numérico con tope dado por `servicio.capacidad_maxima`.
  5. Paso 5 — Checkout: datos del cliente, captura de `?ref=`, checkbox de deslinde obligatorio y panel de pago seguro vía Stripe Elements (`PaymentElement`).
- **Catálogo general**: `[lang]/catalogo/page.tsx` expone un banner secundario Perception-First para traslados cuando la sede seleccionada es La Paz.
