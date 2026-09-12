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

## Estado

`[lang]/reservar/page.tsx` es el checkout real, conectado al backend Django via
`src/lib/api.ts` (`NEXT_PUBLIC_API_URL`, default `http://localhost:8000` en
`.env.local`). Trae la tarifa server-side (`getTarifa`), crea la `Reserva`
(`pendiente_pago`) y el `PaymentIntent` al enviar el formulario, y monta
`@stripe/react-stripe-js` (`PaymentElement`) cuando el backend responde con
`client_secret`. Si Stripe no esta configurado en el backend (sin llaves en local),
el checkout muestra `checkout.paymentUnavailable` en vez de romperse — ver
`backend/CLAUDE.md` seccion "API publica (frontend)". `[lang]/page.tsx` (home) sigue
siendo un placeholder.

Reglas del checkout que conviene no romper:

- **Ninguna cifra hardcodeada.** Precio del tour y precios de amenidades salen de
  `GET /api/tarifa/` en pesca legacy, o bien de `precio_ancla`/`pricing-paquete.ts` cuando hay
  paquete, o `servicio.precio_base` para servicios sueltos. Si no hay paquete ni servicio y la tarifa falla,
  la vista arranca en fase `unavailable`. Las empresas nuevas sin Tarifa legacy funcionan correctamente
  con paquetes y servicios.
- **Multi-empresa y resolución dinámica (`empresaSlug`)**:
  El checkout resuelve la empresa responsable del cobro según el producto seleccionado:
  1. Paquete: `paquete.empresa_lider_slug`.
  2. Servicio suelto: `servicio.empresa_slug` (parámetro `&empresa=` en URL).
  3. Pesca legacy: `process.env.NEXT_PUBLIC_EMPRESA_SLUG` (por defecto `sal-y-sol`).
  `api.ts` acepta `empresaSlug?: string` opcional en `request()` y en las funciones de API (`guardarReserva`, `crearPago`, `getCupo`, etc.).
  Stripe se inicializa dinámicamente con `pago.publishable_key` retornado por `crear-pago` para la empresa correspondiente.
- **Campos del checkout para paquetes y hospedaje**:
  - `paquete` / `servicio`: slug del paquete o servicio a reservar.
  - `fecha_salida`: fecha de check-out para reservas multi-día (`por_noche`).
  - `servicios_removidos`: IDs de componentes del paquete excluidos por el usuario.
  - `personalizaciones`: IDs de personalizaciones opcionales añadidas al paquete.
  - `motivo_no_disponible`: maneja `'lleno'`, `'sin_panga'` y `'sin_lugar'` para feedback específico al usuario.
- **Moneda**: pesos o dolares (paso 6, dentro del resumen). El selector solo aparece si
  el backend mando `precio_usd` o el paquete/servicio cuenta con precio en USD. La moneda elegida viaja en la `Reserva` y es la que usa
  el servidor para cobrar.
- **Deslinde**: una casilla discreta arriba del boton de pagar, con enlace a
  `/[lang]/deslinde` (texto completo, abre en otra pestaña para no tirar lo que el
  cliente ya lleno). El `deslinde_nombre` que se manda al backend es el nombre que ya
  escribio en sus datos — no se pide dos veces. El backend lo exige para toda reserva
  web, asi que quitar la casilla de la UI solo produce un 400.
- **Selectores del booking bar**: `DateField` y `TimeField` sobre `FieldPopover`, hechos
  a mano y sin dependencias. No usar `<input type="date">` ni `<select>`: sus
  desplegables los pinta el sistema operativo y no se pueden llevar al diseño. Los
  nombres de meses y dias salen de `Intl`, no de los diccionarios.
- **Fechas ISO**: parsear siempre con `new Date(\`${iso}T00:00:00\`)`. Sin el sufijo, JS
  lo lee como UTC y en `America/Mazatlan` (UTC-7) cae en el dia anterior. Para ir de
  `Date` a ISO esta `toLocalISODate` en `src/lib/dates.ts`.

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


## Checkout de paquete cruza-empresa

`/[lang]/reservar-paquete?paquete=<slug>&sede=<slug>` usa `paquete-checkout.tsx`.
El catálogo dirige aquí los paquetes con componentes de empresas distintas;
los paquetes mono-empresa siguen en `/reservar`.

- Un formulario de contacto, datos por componente y un solo deslinde. Crea una
  `Orden` y sus reservas con `forma_pago=completo`. Esta UI ofrece MXN; la API y el
  catálogo conservan precios independientes MXN/USD.
- Un `StripePanel`/`Elements` a la vez, desmontado por empresa, con la publishable
  key y el client secret devueltos para esa cuenta. Solo tarjeta y captura manual.
- `sessionStorage` conserva el ID de orden/checkout para reanudar. No repite pasos
  `requires_capture` ni `succeeded`.
- Tras autorizar todos solicita `confirmar-captura`. `autorizada` es intermedio:
  consulta el estado cada 5 segundos y solo muestra éxito con `capturada` y fracaso
  con `cancelada`. Un error de red conserva la orden y continúa consultando.
- Un `card_error` en el checkout de paquete solicita confirmar el conjunto incompleto;
  el servidor detecta la autorización fallida y ejecuta `revertir_orden` (void del
  primer pago). El callback opcional no cambia el checkout mono-empresa.
- La confirmación efectiva viene del webhook o de `conciliar_pagos`, nunca de una
  inferencia del navegador. El texto final del deslinde requiere aprobación del dueño.
