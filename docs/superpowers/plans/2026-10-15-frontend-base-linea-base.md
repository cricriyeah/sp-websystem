# Línea base de carga — frontend (antes de la optimización)

Medido el 2026-10-17 sobre `qa/checkout-unificado` (HEAD 06d35c3f) con `node scripts/medir-peso.cjs` tras `npm run build`. Suma los chunks JS que el HTML de cada ruta pide (los `dynamic()` no entran). API no disponible: las páginas pintan su estado vacío.

| Ruta | Chunks JS | Crudo (KB) | Gzip (KB) |
|---|---|---|---|
| /es | 10 | 780.9 | 244.6 |
| /es/sede/la-paz | 10 | 807.1 | 251.7 |
| /es/servicio/sal-y-sol/pesca-deportiva | 9 | 770.9 | 241.3 |
| /es/reservar | 13 | 1013.4 | 311.6 |
| /es/traslados | 12 | 947.9 | 292.0 |

## Recursos estáticos

- `public/videos`: 84 MB (`videohero.webm`, 87 608 929 bytes)
- `public/photos`: 2,0 MB
- Diccionarios: `es.json` 64 298 bytes, `en.json` 60 900 bytes

## Registro de cambios

- 1.1 `optimizePackageImports`: bundle de producción sin cambio (idéntico en las 5 rutas), como anticipa el plan; el beneficio es dev, build y cold start.
- 1.2b formulario de tarjeta diferido (`next/dynamic`, `ssr:false`) con esqueleto estático y precarga al llegar a «Cómo pagas». Medido el 2026-10-17 con `medir-peso.cjs` tras `npm run build` (sin commitear):

  | Ruta | Chunks | Crudo (KB) | Gzip (KB) | Antes crudo / gzip |
  |---|---|---|---|---|
  | /es | 10 | 780.7 | 244.7 | 780.9 / 244.6 |
  | /es/sede/la-paz | 10 | 807.0 | 251.8 | 807.1 / 251.7 |
  | /es/servicio/sal-y-sol/pesca-deportiva | 10 | 770.8 | 241.7 | 770.9 / 241.3 |
  | /es/reservar | 15 | 1010.4 | 311.4 | 1013.4 / 311.6 |
  | /es/traslados | 13 | 936.9 | 288.8 | 947.9 / 292.0 |

  Prueba binaria con `next start`: ni el HTML de `/es/reservar` ni el de `/es/traslados` contienen `js.stripe.com`, ni ninguno de los chunks que sus `<script src>` piden (0 coincidencias). El único chunk con `js.stripe.com` (`1rohtp7phv55s.js`, 16 754 bytes) no lo pide ninguna de las dos rutas. La bajada de bytes es pequeña (−3.0 KB crudo en reservar, −11.0 en traslados) y el número de chunks sube (13→15 y 12→13); no se investigó la causa (el peso de Stripe en el chunk inicial anterior no se midió por separado). El resultado que cuenta es que Stripe.js ya no está en lo que piden estas rutas al cargar.

- 1.8 `LazyMotion` (`domAnimation` síncrono + `strict`) con `m.*` en 18 componentes; el mapa del hub lleva `LazyMotion` anidado con `domMax` por su `drag`. Medido el 2026-10-17 con `medir-peso.cjs` tras `npm run build` (sin commitear). «Antes» = HEAD cfb717d9 recompilado en esta sesión (no la tabla de 1.2b, que quedó desfasada por 1.3-1.7):

  | Ruta | Antes crudo / gzip (HEAD) | `m` desde `motion/react` | `m` desde `framer-motion` (lo que queda) |
  |---|---|---|---|
  | /es | 784.3 / 246.7 | 793.7 / 249.1 | 790.3 / 249.8 |
  | /es/sede/la-paz | 811.0 / 254.1 | 820.3 / 256.4 | 770.4 / 243.2 |
  | /es/servicio/sal-y-sol/pesca-deportiva | 774.8 / 244.0 | 784.1 / 246.3 | 734.2 / 233.1 |
  | /es/reservar | 1014.0 / 313.4 | 1023.2 / 315.7 | 973.3 / 302.5 |
  | /es/traslados | 940.5 / 290.8 | 949.7 / 293.1 | 899.8 / 279.9 |

  Hallazgo: seguir el plan al pie de la letra (`import { m } from 'motion/react'`) **sube** ~9 KB en todas las rutas. `node_modules/motion/dist/es/react.mjs` hace `import * as fm from 'framer-motion'; const motion = fm.motion;` a nivel de módulo y Turbopack no lo descarta: cualquier import de `motion/react` arrastra el `motion` completo (con `DragGesture` y `MeasureLayout`, comprobado en el chunk) aunque nadie lo use. Importando de `framer-motion` (misma versión 12.43.0 que ya trae `motion`; declarado en `package.json`/lock) el chunk completo desaparece de las rutas sin mapa: −40.6 KB crudo / −10.9 KB gzip en sede, servicio, reservar y traslados. El hub (`/es`) queda +6.0 KB crudo porque el mapa carga `domMax` (drag) de forma síncrona; se recuperaría cargando `HubMapaSedes` con `next/dynamic` (no hecho, fuera de la tarea).

(se anota aquí cada medición posterior: 1.5, 5.5)

## Task 1.7 — Sondeo de caché del catálogo (decisión pendiente del dueño)

Estado: **no se activó nada.** Sin API disponible en esta sesión no se pudo medir el beneficio real, así que esto es el análisis y la recomendación.

- **Camino barato (recomendado si se quiere cachear):** en `request()` de `lib/api.ts`, solo para las GET del catálogo público (`getSedes`, `getPaquetesSede`, `getServiciosSede`, `getServicioDetalle`, `getPaqueteDetalle`), pasar `next: { revalidate: 60, tags: ['catalogo'] }` al `fetch`. No requiere `cacheComponents`. Cupo, cotización, pagos y cualquier POST quedan fuera siempre (sin `next` y sin caché).
- **Invalidación de un precio editado en el backoffice:** con `revalidate: 60` el cambio se ve en ≤ 60 s sin hacer nada; para verlo al instante hay que añadir una ruta (`/api/revalidar`) que llame `revalidateTag('catalogo')` y que el backend invoque al guardar un Servicio/Paquete. Esa pieza no existe hoy.
- **`cacheComponents` (no recomendado ahora):** exige envolver en `<Suspense>` todo `await params/searchParams` en sede, servicio y `/reservar` (si no, el build falla), activa `<Activity>` en la navegación (las rutas ocultas conservan estado y limpian efectos: Turnstile, `sessionStorage`, `captchaKey`) y un `searchParams` solo para `moneda` vuelve dinámica toda la sede. El costo supera el beneficio mientras no haya clientes.
- **Riesgo del camino barato:** un precio o cupo viejo hasta 60 s en la sede y el detalle de servicio. El checkout vuelve a pedir el catálogo al montar y el servidor recalcula el cobro, así que el monto cobrado nunca depende de la caché.
- **Decisión que necesito:** ¿activar el camino barato (60 s, sin ruta de invalidación) o dejarlo para después del lanzamiento?

## Task 1.5 — Video de la sede

- `public/videos/videohero.webm`: 87 608 929 bytes (2560×1440) → 5 519 643 bytes (720p, 24 fps, VP9 crf 38, sin audio). Objetivo ≤ 8 MB cumplido; la calidad la aprueba el dueño.
- El HTML de `/es/sede/la-paz` trae `<link rel="preload" as="image">` de la foto del héroe y 0 `<video>`; el video lo monta `ui/video-diferido.tsx` tras `load`/idle (no con `prefers-reduced-motion` ni `saveData`).
