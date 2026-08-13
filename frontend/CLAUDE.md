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

- **Ninguna cifra hardcodeada.** Precio del tour y precios de amenidades salen los dos
  de `GET /api/tarifa/`. Si esa llamada falla, `tarifa` llega `null` y la vista arranca
  en fase `unavailable` — antes habia un `FALLBACK_TOUR_PRICE` que mostraba un precio
  inventado cuando el backend estaba caido.
- **Moneda**: pesos o dolares (paso 6, dentro del resumen). El selector solo aparece si
  el backend mando `precio_usd`. La moneda elegida viaja en la `Reserva` y es la que usa
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
