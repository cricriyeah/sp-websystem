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

(se anota aquí cada medición posterior: 1.2b, 1.5, 1.8, 5.5)

## Task 1.7 — Sondeo de caché del catálogo (decisión pendiente del dueño)

Estado: **no se activó nada.** Sin API disponible en esta sesión no se pudo medir el beneficio real, así que esto es el análisis y la recomendación.

- **Camino barato (recomendado si se quiere cachear):** en `request()` de `lib/api.ts`, solo para las GET del catálogo público (`getSedes`, `getPaquetesSede`, `getServiciosSede`, `getServicioDetalle`, `getPaqueteDetalle`), pasar `next: { revalidate: 60, tags: ['catalogo'] }` al `fetch`. No requiere `cacheComponents`. Cupo, cotización, pagos y cualquier POST quedan fuera siempre (sin `next` y sin caché).
- **Invalidación de un precio editado en el backoffice:** con `revalidate: 60` el cambio se ve en ≤ 60 s sin hacer nada; para verlo al instante hay que añadir una ruta (`/api/revalidar`) que llame `revalidateTag('catalogo')` y que el backend invoque al guardar un Servicio/Paquete. Esa pieza no existe hoy.
- **`cacheComponents` (no recomendado ahora):** exige envolver en `<Suspense>` todo `await params/searchParams` en sede, servicio y `/reservar` (si no, el build falla), activa `<Activity>` en la navegación (las rutas ocultas conservan estado y limpian efectos: Turnstile, `sessionStorage`, `captchaKey`) y un `searchParams` solo para `moneda` vuelve dinámica toda la sede. El costo supera el beneficio mientras no haya clientes.
- **Riesgo del camino barato:** un precio o cupo viejo hasta 60 s en la sede y el detalle de servicio. El checkout vuelve a pedir el catálogo al montar y el servidor recalcula el cobro, así que el monto cobrado nunca depende de la caché.
- **Decisión que necesito:** ¿activar el camino barato (60 s, sin ruta de invalidación) o dejarlo para después del lanzamiento?
