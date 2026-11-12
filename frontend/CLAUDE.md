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
- `src/proxy.ts` redirige segun `Accept-Language` (`lib/idioma-navegador.ts`): el primero de `es`/`en` en la lista del navegador (respeta `q`); sin cabecera, `es`; si no lee ninguno de los dos, `en` (plan de marketing 2026-11-11).
- `src/proxy.ts` manda a la ruta comodín (404 de verdad) una sede o empresa que no existe (`lib/ruta-inexistente.ts`): con `loading.tsx` la página ya salió como 200 cuando su `notFound()` corre y Google la ve como soft 404. Los enlaces a detalle no llevan `?moneda=MXN` ni `?sede=` de la sede propia de la empresa: una sola URL por página (Search Console, 2026-11-11).
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
  previa y el servidor determina el cobro real. Los precios en USD se
  derivan del tipo de cambio de la sede (`lib/moneda.ts`, `aMoneda`, igual
  que `payments.moneda.convertir`), así que siempre existen: no hay estado
  de «extra sin precio USD». El anticipo de paquete solo se ofrece
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
  datos de contacto. `TimeField` usa `FieldPopover`; no añadir selectores
  nativos de fecha ni de hora. Para fechas ISO, usar `fromLocalISODate`/`toLocalISODate` de
  `src/lib/dates.ts` y evitar parsear fechas ISO como UTC.
- Transiciones y piezas compartidas del checkout: todo lo que aparece, se
  pliega o cambia de sitio (código promocional y sus mensajes, mes del
  calendario, bloques del traslado, avisos de un extra) pasa por
  `components/checkout/despliegue.tsx` (`Despliegue`: altura + opacidad con
  la misma curva de `CheckoutSectionCard`, solo opacidad con "reducir
  movimiento"). No renderices condicionalmente con `&&` algo que el cliente
  ve aparecer: el contenido de abajo brinca. El tipo de traslado se pinta con
  `components/checkout/tipo-traslado-cards.tsx` en `/traslados` y en el paquete
  (en el paquete sin "Desde $": el traslado va incluido).
- **Calendario de reserva.** Las cuatro rutas (servicio suelto, paquete de una empresa,
  cruza-empresa y `/traslados`, también en el asistente móvil) montan `ui/calendario`
  a través de `components/checkout/calendario-reserva.tsx` (`CalendarioReserva`), que
  consulta el cupo del mes visible y el siguiente con `useDisponibilidad(desde, hasta,
  personas, activo, empresaSlug)` (`{ dias, cargando, error, reintentar }`). El control
  sale de `lib/control-fecha.ts`: fecha única, llegada y salida del hospedaje
  `por_noche` (un solo calendario), rango fijo del paquete con noches, e ida y regreso
  del traslado con aeropuerto. Solo la pesca suelta (`por_recurso_dia`) consulta cupo:
  `/cupo/rango/` contesta por las pangas, así que hospedaje, bajo demanda («Reserva
  confirmada al pagar»), paquetes y traslados lo validan al pagar. «Borrar fecha» deja
  la fecha vacía en todas las rutas y Continuar la pide (`checkout.calendario.faltaFecha`).
  La fecha de regreso del traslado dentro de un paquete (`FechaRegresoCompacta`) es
  obligatoria: se ve con el calendario abierto hasta que hay fecha, y entonces se pliega a
  una fila con "Modificar" (nunca un botón "Elegir", que la haría parecer opcional).
  `PeopleStepper` (con la forma de los demás campos; no círculos grandes) recibe el tope del
  servicio (`capacidad_maxima`, o 5 sin ella; en paquete, `topeDeComponente`) y al tocar
  + en el tope dice «Máximo N personas» en línea. El hospedaje `por_noche` suelto
  muestra precio × noches (estrategia `PorNoche` del servidor) con «Estimado» junto al
  total hasta crear el pago.
- Las listas cortas usan `SelectPersonalizado` (sobre `FieldPopover`),
  no `<select>` nativo. Los errores que bloquean se quedan en la tarjeta,
  pegados a su campo (los toasts se auto-descartan: son para avisos): usa
  `<ErrorDeCampo id mensaje={error} />` siempre montado, que entra/sale con
  `Despliegue` y, si queda fuera de pantalla, hace scroll y lleva el foco al
  campo con `aria-describedby` igual al id.
- Anatomía de la tarjeta de traslado (y de cualquier tarjeta con controles):
  una pregunta por bloque; los controles que se contestan dentro de una caja
  (hotel, personas, aeropuerto, listas) usan `CAJA_CAMPO` de
  `components/ui/caja-campo.ts` con `compacto` en `FieldPopover` /
  `PeopleStepper` (relleno de 16 px, borde izquierdo alineado con las filas de
  tipo); los grupos de opciones y la fecha llevan su pregunta como título
  arriba. Orden por causalidad: tipo → regreso (solo aeropuerto) → dónde →
  personas (prellenado, al final y callado) → extras. Las preguntas que
  aparecen y desaparecen llevan su separación (`pt-5`) dentro del bloque y no
  en el `gap` del cuerpo, para que al desplegarse no brinque el hueco. Las
  acciones secundarias NO van subrayadas en reposo (`checkout/accion-terciaria`):
  "Modificar" de un renglón es `EtiquetaModificar` (flecha a la izquierda que gira hacia abajo al abrir, el renglón entero es
  el botón); "revelar más" (ver mes, código promocional) es `AccionTexto` con
  caret que gira; la otra dirección del hotel es la última opción de la lista y
  en modo manual `AccionTexto` vuelve a la lista. El subrayado queda para
  enlaces dentro de una oración (deslinde, términos). El tipo de traslado va en
  lista (descripción completa), no en columnas.
- Respuestas ya dadas y foco: una tarjeta `completado` es un renglón de una
  línea ("título · resumen" + "Modificar" como enlace discreto) y varias
  seguidas son tarjetas delgadas con 8 px entre sí (`ItemPaso` + `unidaConAnterior`, por posición: las
  tarjetas siguen montadas y su colapso sigue animándose). Un solo foco abierto:
  mientras el cliente reabre una respuesta, la tarjeta activa pasa a
  `suspendido` (solo título; sus respuestas viven en el estado del pedido) con
  `estadoVisible`. `useScrollAlFoco` lleva al cliente a la tarjeta con
  `data-tarjeta-foco` solo si no se ve, tras su acción y con `reducir
  movimiento` instantáneo. En escritorio el stepper es `sticky` y el pie con el
  CTA de la tarjeta activa (`PieDeTarjeta`) tiene dos estados en un solo
  elemento: natural, o pegado al borde inferior solo si su sitio natural queda
  bajo la pantalla, y entonces se ve como capa (translúcido, desenfoque,
  sombra hacia arriba, título de la tarjeta a la izquierda). Lo usa `PedidoPaquete` (mismo para paquete de una
  empresa y cruza-empresa) y por `CheckoutView` (servicio suelto).
- Anatomía común de la ruta `/reservar` (servicio suelto, paquete de una
  empresa y paquete cruza-empresa): `PaginaCheckout`
  (`src/components/checkout/pagina-checkout.tsx`) pone volver → `EncabezadoCompra`
  → stepper → [pasos | pedido]. Los pasos son siempre viaje → datos → pago
  (`src/lib/pasos-checkout.ts`; los extras van en Viaje, contacto y recogida en
  Tus datos). El paso vive en `?paso=` (`lib/paso-url.ts` + `use-paso-url.ts`: cada
  paso es una entrada de historial por `pushState`, Atrás reabre el anterior) y el
  borrador de la pestaña en `sessionStorage` (`lib/borrador-reserva.ts` +
  `use-borrador.ts`, solo se repone con `?paso=` en la URL); la flecha es «paso
  anterior» salvo en Viaje o con un pago en curso, donde sale al origen
  (`lib/origen.ts`, `?origen=`). La cabecera de estas rutas es `CabeceraMinima`
  (`components/reserva/`): flecha, marca Sun Baja Experience (+ sello de la empresa si es
  de una sola) e idioma ES | EN; sin navegación ni WhatsApp, 64 px como `SiteHeader`. Cada tarjeta es un
  `CheckoutSectionCard` con un solo CTA en el `pie` (`BotonPaso`) y bloques
  separados por espacio, no por rayas. El panel derecho (`StripePanel`) es SOLO
  el resumen del pedido (líneas vivas del viaje, cargos, total y "pagarás
  ahora" si difiere). El cuarto paso vive en la columna de pasos: "Cómo
  pagas" (moneda, modalidad, promo, deslinde, Turnstile y el botón que crea
  el pago) es una tarjeta que el panel pinta ahí mediante un portal
  (`destinoTarjeta`: el llamador pone `<div ref={setDestino}>` en `pasos` al
  llegar al paso 4 y pasa ese nodo al panel, que conserva todo el estado y las
  props); al crearse el pago esa tarjeta se pliega a un renglón y debajo
  aparece el formulario de tarjeta (`FormularioPago`, con `NotaSeguridadStripe`).
  Sirve igual para servicio, paquete (una empresa y cruza-empresa) y
  `/traslados`. Los `Elements` de Stripe solo envuelven `FormularioPago` (en
  cruza-empresa se remonta por empresa con `key`). Los pagos de una reserva se
  crean con `payment_method_types=['card']` (sin "Link"), igual que las órdenes. Dentro de cada
  tarjeta: lo obligatorio antes que lo opcional (`separarPersonalizaciones`).
  `AyudaFlotante` ofrece WhatsApp, sin mover la página, tras dos tropiezos
  (`src/lib/ayuda-contextual.ts`): errores de validación al confirmar pasos o
  intentos de pasar el tope de personas. En `CheckoutView` los datos de
  contacto usan `CamposContacto` con `idPrefijo="checkout"` (ids de error
  `checkout-error-<campo>`).
- **Asistente móvil (< 640 px).** En `/reservar` y `/traslados` las tarjetas son solo de escritorio y
  tablet; en móvil cada ruta pinta una pantalla por vez con `AsistenteMovil`
  (`components/reserva/`). La lista de pantallas sale de `lib/pantallas-checkout.ts`, y
  `use-pantalla-movil` lleva la pantalla en `?pantalla=` (cada una es una entrada de historial),
  la más avanzada junto al borrador, un `tope` (sin pago no hay tarjeta) y una `minima` (con pago
  en curso no se vuelve). En móvil `usePasoUrl` va apagado. Las rutas arman sus bloques una vez
  (`bloqueViaje`, `bloqueContacto`…) y los usan en las dos formas. Dentro de `AsistenteMovil`,
  `CheckoutSectionCard` pinta solo su contenido: sin marco, título ni pie. El botón grande es de
  la `BarraInferior`, con dos sitios: el de la pantalla («Continuar») y el del contenido, que
  manda. «Cómo pagas» y `PaymentForm` publican el suyo con `usePublicarAccion`; el de Stripe, desde
  dentro de `<Elements>`. «Corregir» en móvil va a la pantalla del campo (`useCorregir` con
  `irAPantalla`). Diseño y orden: `docs/superpowers/plans/2026-10-18-f8-asistente-movil.md`.
- Pruebas desde `frontend/`: `npm.cmd test` ejecuta
  `tests/run-hub-tests.cjs` (una suite por módulo puro). Para una sola,
  `npm.cmd test -- calendario-paquete`; al añadir un módulo, registrar
  su nombre y archivo en `suites` de ese runner. Gate de la sección:
  `npx.cmd tsc --noEmit`, `npx.cmd eslint src tests`, `npm.cmd test` y
  `npm.cmd run build`.

## Base de UI: tokens, primitivas y `guardia`

- **Tokens:** viven en `src/app/globals.css` (colores, radios, sombras, z, `--nav-alto`). Stripe Elements
  no lee CSS: sus valores concretos están en `src/lib/tokens-pago.ts` y una prueba los compara con
  `globals.css`.
- **Primitivas:** `src/components/ui/` (`Button`, `Input`, `Checkbox`, `Opcion`, `Field`, `Card`,
  `Sheet`, `AlertDialog`, `Despliegue`, `ErrorDeCampo`, `HeroMedia`, `SectionShell`, `EmpresaSello`…).
  `ui/` solo importa de `ui/` y `lib/`.
- **Regla «nada crudo»:** fuera de `ui/` no se escribe `<button>`, `<input|select|textarea>`, `<img>`,
  paleta de Tailwind (`bg-red-500`…), colores literales ni `motion.*` (con `LazyMotion` strict solo `m.*`).
  Si falta una variante de `Button`/`Input`, se añade en `ui/variantes.ts` con su prueba
  (`tests/`), no se deja el elemento crudo. `variante="libre"` y `aspecto="heredado"` no añaden clases:
  son el puente para migrar sin cambiar el aspecto.
- **`npm run guardia`** (`scripts/guardia-estilos.cjs`) cuenta las infracciones. Trinquete por total
  de regla contra `scripts/guardia-estilos.baseline.json` (solo puede bajar; tras bajarlo,
  `node scripts/guardia-estilos.cjs --escribir`) y umbral duro en 0 para `boton-crudo`, `input-crudo`,
  `img-cruda`, `paleta-cruda`, `color-literal`, `capas-ui` y `motion-completo`, salvo lo listado con motivo
  en `EXENTOS`. Un exento nuevo exige motivo escrito.
- **`npm run verificar`** corre toda la puerta: `tsc`, `eslint`, `npm test`, `test:guardia`, `guardia`
  y `next build`. Córrelo antes de cerrar cualquier tarea de frontend.

## La Paz: «Nuestras pangas», «Conócenos» y el logo (pedido del dueño, 2026-10-28)

Acomodo derivado con perception-first-design; construido con taste. El héroe es la foto de la panga rumbo a la pesca (2026-11-05; el video volvió al hub).

- **«Nuestras pangas»** (`pangas-sede.tsx`, id `pangas`): justo bajo el héroe y antes de «Reservar ahora»
  (`seccionesDeSede` la pone ahí si `contenido.pangas` tiene fotos; fuera del menú). Cabe en una pantalla y no lleva botón
  para no alejar la compra. Rehecha el 2026-10-30 (PFD + Apple): bajo el título, la foto de la flota COMPLETA, en su
  proporción y sin nada encima (el dueño rechazó los nombres sobre la foto); pegado a ella, una frase grande y el párrafo
  que nombra las siete pangas en el orden de la foto (`pangas.nombres`, `{nombres}` en `texto`); al lado, las dos fotos
  navegando, que en el teléfono son una tira que se desliza de lado. En el teléfono la flota va de orilla a orilla.
- **«Conócenos»** (`conocenos-sede.tsx`): un solo relato a dos columnas en un solo fondo (2026-10-30; reemplazó la banda
  tinta con el collage del staff y el cartel gigante «Sal con el sol»). En escritorio, las fotos del gremio bajan a la
  izquierda (la del relato, la primera de `tripulacion.fotos` y las otras dos lado a lado), sin alinearse con ningún nombre;
  a la derecha, título, apertura, párrafos 1-2, los nombres de los capitanes como frase del relato (`.texto-tripulacion`),
  párrafo 3, la prensa (único bloque tinta) y el cierre: el logo largo a color de la empresa (`MarcaEmpresa.logoLargo`) y
  debajo el único botón (2026-10-30, el dueño quitó «Sal con el sol», el isotipo chico y la frase). En el
  teléfono todo va intercalado con `order` (las columnas son `contents`). Sin cifras sueltas, sin estrellas ni íconos.
  Dinamismo: la foto del relato sangra hasta el borde de la pantalla (en el teléfono, las dos grandes de borde a borde), la escena se encima más angosta con un marco del
  color del fondo y la pareja va escalonada; al hacer scroll las fotos derivan dentro de su marco (`.foto-deriva`), los
  nombres se entintan palabra por palabra (`.tinta-al-leer`). Todo
  con `animation-timeline: view()` y quieto con «reducir movimiento».
- **El logo** solo donde significa algo. En «Las pangas», «Reserva con tranquilidad» y Temporadas va arriba a la
  derecha, en la esquina, alineado al borde de arriba del título, de tamaño medio y fijo (64/80/96/112 px;
  `ui/sello-titulo.tsx`, vía `SectionShell sello`). En «Las pangas», si la empresa tiene `logoLargo` (Sal y Sol), va el logo largo a color en lugar del
  isotipo, del tamaño del sello (48/80/96/112 px), y el título baja a la base del logo para quedar pegado a la foto.
  Lo mismo en «Qué se pesca» (`SectionShell sello.largo`). En la barra de arriba (`LogoEmpresaAlLado`) y en el héroe
  (`SedeHero`, sin el «Con …») también va el logo largo cuando la empresa lo tiene. En «Gente de mar» el dorado
  (`conocenos.ilustracion`, /ilustraciones/dorado.svg) va de fondo, tenue, como el logo de «Reserva con tranquilidad». Sin círculo en fondo claro (isotipo transparente
  `simboloBarra`), dentro de un círculo blanco en la banda tinta, y con su propio círculo si la empresa no tiene isotipo
  transparente. En «Te lleva», sin círculo.
  En «Reserva con tranquilidad» de La Paz no hay sello: el logo de Sal y Sol dibujado en blanco
  (`/logos/logosbgsalysol.svg`, `MarcaEmpresa.ilustracionFondo`) va de fondo detrás de las cifras al 7 % de opacidad,
  cortado por la derecha (`SectionShell ilustracion`). Las empresas sin ilustración conservan el sello.
- Los nombres de la tripulación vienen de una nota de voz: van `pendiente: true` y NO se publican
  (`lib/capitanes-visibles.ts`; se ven en desarrollo o con `NEXT_PUBLIC_VER_PENDIENTES=1`). Al confirmarlos, quitar
  `pendiente` y ajustar la prueba `content-sedes-cuerpo`. Las fotos de pangas y de Conócenos ya son las reales del dueño.

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

## Pixel de Meta

`components/pixel-meta.tsx` (montado en `[lang]/layout.tsx`) mete el código base de Meta en `<head>`
solo si el cliente aceptó las cookies (`lib/cookies.ts`; el aviso ya dice «medir nuestros anuncios»;
`guardarConsentimiento` dispara `EVENTO_CONSENTIMIENTO` para que cargue al momento). Manda el primer
`PageView` y las páginas siguientes las cuenta el propio pixel al cambiar la URL (`pushState`); un
`fbq('track', 'PageView')` a mano después del primero no sirve, fbevents.js acepta uno por carga.
Los pasos del checkout (`?paso=`) también cuentan. `autoConfig` va apagado: sin eventos automáticos
ni lectura de formularios. El CSP de `next.config.ts` permite `connect.facebook.net` y
`www.facebook.com`.

**Eventos de venta y origen de la visita** (plan de marketing, 2026-11-11). `lib/medicion.ts` (`medir`) es el único
punto que avisa al pixel y a Google Analytics; sin cookies aceptadas no hay `fbq`/`gtag` y no hace nada. `ViewContent`
en el detalle de servicio y paquete (`MedirEvento`, hoja cliente en la página de servidor), `InitiateCheckout` justo
antes de `crearPago` en los tres checkouts, `Purchase` desde `ConfirmacionReserva` (`datos.compra`, una vez por folio
con `sessionStorage`; `eventID` = `reserva-<folio>`/`orden-<folio>`, el mismo que usará la API de Conversiones) y
`Contact` en cualquier toque a un enlace de WhatsApp (`MedirWhatsapp`, un oyente en el layout). `lib/atribucion.ts`
guarda 30 días el último enlace con `utm_*`/`fbclid`/`gclid` (o el sitio de origen si no hay nada guardado) desde
`RefCapture`, y los tres checkouts lo mandan como `atribucion` con la reserva u orden (más `_fbp`/`_fbc` si el pixel
cargó); el backend lo limpia (`apps/bookings/atribucion.py`) y lo enseña en la reserva («Llegó por»).
El servidor manda la misma compra a la API de Conversiones (`backend/apps/payments/meta_capi.py`, al confirmar el
cobro; `META_PIXEL_ID` + `META_CAPI_TOKEN` en Render): solo si la reserva trae `_fbp` (cookies aceptadas), salvo
`META_CAPI_SIN_CONSENTIMIENTO=1`.

**Precio público con IVA** (plan de marketing, punto 1). El catálogo va sin IVA; tarjetas, detalle, extras, la nota de
persona extra, el «desde» del hub y la oferta del JSON-LD lo suman con `precioPublico` (`lib/iva.ts`) y lo dicen
(«· IVA incluido» en `baseDeCobro`; un precio por grupo dice «para N personas»). El checkout sigue desglosando el IVA.

## Links cortos por sede (modo «solo sede»)

Cada empresa comparte el link corto de su sede (`/lapaz`, `/laventana`, `/puertochale`; también
`/en/lapaz`) y el cliente no ve el hub. Toda la lógica de rutas está en `src/lib/solo-sede.ts`
(`decidirSoloSede`, pura, probada en `tests/solo-sede.test.cjs`); `proxy.ts` solo la aplica.

- El link corto redirige (307) a `/[lang]/sede/<slug>` conservando la query (`?ref=` sigue
  funcionando) y guarda la cookie `sbe_solo_sede` 30 días.
- Con la cookie, `/`, `/es`, `/en` y `/nosotros` (con o sin idioma) redirigen a la sede: cualquier
  enlace que quede apuntando al hub (checkout, 404, «Ver qué reservar» de privacidad) cae en la sede.
- `/hub` borra la cookie y lleva a la portada (para el dueño y las vendedoras).
- Si el cliente abre otra sede (o un servicio, paquete o checkout de otra), la cookie pasa a esa
  sede: nunca la página de una sede con el logo de otra. Lo hacen dos piezas: el proxy al cargar la
  página (cubre el checkout, que no lleva `SiteHeader`; manda `?sede=` y si no, la sede de
  `?empresa=`/`?paquete_empresa=` o de la empresa del servicio, de `MARCAS.sede`), y `SiteHeader` en
  la navegación sin recarga, que Next puede servir de su caché sin pasar por el proxy. El proxy solo
  cambia el modo en una carga de página entera (`Sec-Fetch-Dest: document`), para que el prefetch de
  un enlace visible no lo cambie; la cabecera `next-router-prefetch` no sirve: Next la quita antes
  de llamar al proxy.
- La sede de cada empresa vive en `content/empresas-marca.ts` (`MARCAS`), no en `empresas.ts`: este es
  `server-only` y el proxy no puede leerlo.
- Lo visible: un script en línea al inicio de `<body>` (layout) pone `data-solo-sede` antes de pintar
  y `globals.css` esconde `.sale-al-hub` (selector de destino de la barra y del menú, «Sobre
  nosotros» y, fuera de una sede, el grupo entero de enlaces del pie). El logo de `SiteHeader` lleva
  a la sede, y «Ver qué reservar» del pie fuera de una sede (`BotonReservarPie`) a su sección de
  reservar. Los dos leen la cookie al hidratar: las páginas siguen estáticas, nada lee cookies en el
  servidor.
- Una sede nueva se agrega en `ENLACES_CORTOS`.
- El matcher de `proxy.ts` escribe `\\.` dentro del string, no `\.`: en JS `'\.'` vale `.`
  (cualquier carácter) y el proxy solo corría en `/` (bug viejo, corregido junto con esto).

## Ruta /traslados (checkout de transporte)

`[lang]/traslados/page.tsx` es el punto de entrada server-side para cotizar y reservar traslados terrestres privados:

- **Server Component + SSR**: obtiene el diccionario con `getDictionary(lang)` y el catálogo con `getTraslados(empresaSlug)` (vía `GET /api/<empresa>/traslados/`). El slug se toma de `searchParams.empresa` o `NEXT_PUBLIC_TRANSPORTE_EMPRESA_SLUG` (por defecto `'transporte-la-paz'`).
- **Resiliencia**: si la API de traslados devuelve 404 o 503 (ej. Stripe no configurado en esa empresa), la página muestra un estado accesible de servicio no disponible sin reventar. Cuenta con `loading.tsx` con esqueletos visuales durante la carga.
- **Componente `traslado-view.tsx`**: usa la misma anatomía que el resto de los
  checkouts (`PaginaCheckout`, `EncabezadoCompra`, renglones unidos, un foco,
  `AyudaFlotante`). Secuencia fija de 3 pasos con stepper `Viaje · Tus datos ·
  Pago` (contacto y recogida comparten Tus datos; abajo, el desglose anterior de
  4 pasos, que ahora son bloques):
  1. **Viaje** (`checkout.tripHeadline`), 4 bloques en este orden: tipo de traslado
     (`TipoTrasladoCards`, lo que define el producto va primero) → fecha
     (`CalendarioReserva`, sin cupo; con `redondo_aeropuerto` un solo calendario de
     ida y regreso, con el regreso obligatorio y vacío al empezar) → hora y pasajeros (`ContenidoViaje`, tope =
     `servicio.capacidad_maxima`).
  2. **Datos** (`CamposContacto`, `idPrefijo="traslado"`).
  3. **Recogida** (`traslados.step2Title`): hotel/punto de encuentro, con "Escribir
     otra dirección…" como última opción de la lista y la zona solo para
     `redondo_actividad`.
  4. **Pago**: la tarjeta "Cómo pagas" (portal del `StripePanel`) y debajo el
     formulario de tarjeta. El panel derecho es el resumen vivo (tipo, fechas,
     hora, pasajeros y, ya elegida, la recogida) y el total va en el stepper móvil.
  `iniciarPago` revalida viaje, datos y recogida (cambiar el tipo después de elegir
  la recogida puede dejarla incompleta) y reabre la tarjeta que falle.
- **Catálogo general**: `[lang]/catalogo/page.tsx` expone un banner secundario Perception-First para traslados cuando la sede seleccionada es La Paz.
