# Base del frontend antes de la marca nueva — Plan de implementación

> **Para quien ejecute:** usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans`. Los pasos usan casillas `- [ ]`. **Regla del dueño:** nada de este plan que toque UI visible se programa sin su luz verde explícita en cada punto de control marcado «PUNTO DEL DUEÑO».

**Meta:** dejar el frontend con tokens completos, primitivas con variantes, vistas de compra partidas y carga optimizada, de modo que la identidad de marca nueva sea un cambio de valores de token y variantes en un solo lanzamiento, sin regresiones en el checkout.

**Arquitectura:** tres capas. (1) `globals.css` declara *todos* los tokens, incluidos radio, sombra y escala de texto, con los valores actuales; Tailwind 4 hace que `rounded-lg`, `shadow-md`, `text-sm` etc. lean esos tokens, así que la marca los cambia en un solo sitio. (2) `src/components/ui/` contiene las primitivas y es una capa baja: solo importa de `ui/`, `lib/` y paquetes; la lógica de variantes vive en un módulo puro sin imports, probado con el runner existente. (3) Una compuerta automática con «trinquete» (solo baja) impide reintroducir colores, radios o controles crudos.

**Stack:** Next.js 16.3, React 19.2, Tailwind 4.3.3, `motion`, `@phosphor-icons/react`, Stripe. Se añaden `clsx` y `tailwind-merge`. Las variantes son mapas de strings puros (sin `cva`) para que el runner de pruebas, que compila solo `src/` y no resuelve paquetes externos, las pueda probar.

**Fuentes de fundamento:** derivación PFD (R1–R5, abajo) + skills de Vercel `react-best-practices`, `nextjs`, `next-cache-components`, `shadcn`, `vercel-storage`. Mediciones del 2026-10-15 sobre la rama `qa/checkout-unificado`. **Sistema de diseño de la marca nueva (Sun Baja Experience): `docs/design/design.md`, `design-guidelines.md` y `design-components.md`** (tokens, fuentes, página de reserva); este plan lo aplica en F7 y F8, y el contenido y la estructura de hub y sede en F9.

## Restricciones globales

- **Checkout visible idéntico** (diferencia visual cero) hasta las fases F7, F8 y F9, que salen **juntas en un solo lanzamiento**. Montos, cargos, plazos y textos de cobro no cambian. *(PFD R4)*
- La marca nueva aterriza **en un solo lanzamiento**; nunca una mezcla vieja/nueva en producción. *(PFD R4)* F7 es **valores más una pasada de componentes** (fondos, sombras, titulares, foco), no solo valores.
- Todo valor visual sale de un token; todo control de una primitiva. *(PFD R3)*
- Una sola acción principal por paso; su jerarquía vive en la primitiva. *(PFD R1, R5)*
- Puerta de cada tarea: `npx.cmd tsc --noEmit`, `npx.cmd eslint src tests`, `npm.cmd test`, `npm.cmd run build`, `npm.cmd run guardia`. Un commit por tarea (las tareas divididas con sufijo, p. ej. 8.4a/8.4b/8.4c, llevan un commit por sufijo).
- Todo `tests/*.test.cjs` nuevo empieza con la línea `/* eslint-disable @typescript-eslint/no-require-imports */` (los 20 existentes la llevan); sin ella `eslint src tests` falla desde el primer commit.
- Todo módulo puro de `src/lib/` que tenga prueba en el runner (`tests/run-hub-tests.cjs`) solo importa valores con ruta relativa (`./dates`, como `calendario-paquete.ts:2`) o `import type` con `@/`: un `import` de valor con `@/` revienta en el runner. Cada módulo nuevo con prueba se registra en `suites` de `run-hub-tests.cjs` (variable `X_TEST_OUT`) en la misma tarea que lo crea; sin registrar, la prueba no corre.
- **No ejecutar `shadcn init`**: reescribe `globals.css` y el skill documenta que rompe las fuentes en Tailwind 4. Se copia el patrón (`cn` + mapas de variantes puros, sin `cva`), no el CLI.
- **Tokens aditivos en F2:** un token o clase que F3–F6 necesita y que **no sustituye a ninguno existente** se declara en F2 (Task 2.1, Paso 3b) con su valor final de `design.md`: Tailwind no avisa cuando una utilidad no tiene token y no pinta nada. F7 solo cambia los valores de lo que ya existía y declara los colores de marca que sustituyen a los actuales.
- **Nombres de token en los textos visuales:** las tareas de F7, F8 y las primitivas nuevas (`Sheet`, `AlertDialog`) describen colores con los nombres de `design.md` (`cafe`, `tinta`, `superficie`, `borde-control`, `apagado`…). Esos nombres se declaran desde F2 (Task 2.1, Paso 3b) **apuntando a los valores actuales** (`--color-cafe: var(--accent)`, `--color-arena: var(--background)`, etc.), así que cualquier componente nuevo de F3 a F6 los usa desde el primer día y pinta; F7.2 Paso 1b invierte la dirección de esos alias (el nombre de marca lleva el valor nuevo y los antiguos lo referencian). El aspecto de F3 a F6 no cambia.
- **Medición de peso (Next 16):** `next build` **ya no imprime «First Load JS»** (`upgrading/version-16.md`). Todo «comparar con la línea base» se mide con `scripts/medir-peso.cjs` (Task 0.2: suma bytes crudos y gzip de los chunks que el HTML de cada ruta pide, con `next start`); `next experimental-analyze` es solo diagnóstico (por defecto levanta un servidor en :4000 para verlo en navegador). Para el chunk de Stripe hay prueba binaria sin navegador: tras `next start`, `curl` de `/es/reservar` y comprobar que ni el HTML ni los chunks iniciales de la ruta contienen `js.stripe.com` (el literal `@stripe` no sobrevive a la minificación, no prueba nada).
- Verificación sin abrir navegador (regla del dueño): el dueño mira el sitio en cada PUNTO DEL DUEÑO.
- **Skills obligatorias al ejecutar este plan (regla del dueño, 2026-10-16):**
  - **Al escribir código** (cualquier tarea que cree o modifique `.ts`/`.tsx`/`.css`/`next.config.ts`): cargar y seguir las skills de Vercel antes de programar — `vercel:react-best-practices` (componentes, hooks, bundle, re-renders), `vercel:nextjs` (App Router, Server/Client Components, errores, imágenes, fuentes), `vercel:next-cache-components` (si la tarea toca caché) y `vercel:shadcn` (primitivas, variantes, tokens). Tras editar varios `.tsx`, pasar la revisión de `vercel:react-best-practices`. Si una skill contradice una restricción de este plan, gana el plan y se anota el motivo en el commit.
  - **Al diseñar componentes** (forma, jerarquía, espaciado, estados, movimiento, copy de un componente nuevo o rediseñado: F3, F5.4, F7.3, F8): cargar la skill `design-taste-frontend` (`frontend/.claude/skills/design-taste-frontend/SKILL.md`) y aplicarla al diseño; la decisión de qué resolver sigue yendo por `perception-first-design`, y nada visible se programa sin la luz verde del dueño en el PUNTO DEL DUEÑO.
  - Las subtareas delegadas a un agente llevan estas dos reglas escritas en su brief.
- Next.js 16 difiere de lo que se sabe de memoria: antes de tocar una API de Next, leer `node_modules/next/dist/docs/` (lo exige `frontend/AGENTS.md`).

---

## 0. Ronda 5 del crítico (skills de Vercel, 2026-10-16): dónde quedó cada hallazgo

> Auditoría contra `react-best-practices`, `nextjs`, `next-cache-components`, `shadcn`, `vercel-storage` y `verification`, verificada con la doc instalada (Next 16.3.6) y el código. Veredicto: REVISION REQUIRED (1 crítico, 13 significativos, 11 menores). **Todos están aplicados dentro de la tarea que corresponde**; esta tabla solo da la trazabilidad.

| Hallazgo | Dónde quedó |
|---|---|
| C1 · «First Load JS» ya no existe en Next 16 | Restricciones globales (medición), Tasks 0.2, 1.1, 1.2b, 5.5, F6 |
| S1, S2 · `error.tsx`: sin diccionario cliente; firma `{ error, retry }` | Task 1.3 |
| S3 · `?paso=` con `history.pushState`, no `router.push` | Task 8.0 Paso 2 |
| S4 · precargar el formulario de Stripe y esqueleto hasta `onReady` | Task 1.2b Pasos 1–4 |
| S5, S6, S7 · héroe: isla de video, `<img>` cruda, `preload` en vez de `priority` (el héroe de la portada resultó huérfano: Task 9.3) | Tasks 1.5 y 5.4 |
| S8 · `optimizePackageImports` con los especificadores reales | Task 1.1 |
| S9 · `LazyMotion` | Task 1.8 (nueva) |
| S10 · caché: primero `next.revalidate`/`tags`, costos de `cacheComponents` | V7 y Task 1.7 |
| S11 · estado de F5 sin re-render global | Task 5.1 Paso 2 |
| S12 · `Sheet` y `AlertDialog` | Task 3.5 (nueva) |
| S13 · foco de `AvisoAccion` | Task 8.3b Paso 3 |
| M1 · `cva` | Restricciones globales |
| M2, M3 · primitivas servidor/cliente, `useId`, `aria-busy` | Task 3.3 |
| M4, M5 · preconnect con CORS, `Content-Type` en GET | Task 1.6 |
| M6 · fuentes (Book, métricas de fallback) | Task 7.2 Paso 3 |
| M7 · `Suspense` y paralelizar `await` | Task 1.4 |
| M8 · verificar errores y recursos con `curl` | Tasks 1.3 y 1.5 |
| M9 · hidratación del borrador | Task 8.0 Paso 1 |
| M10 · `<ol>` con `aria-current`, objetivo táctil de 44 px | Tasks 8.4a y 7.3 |
| M11 · `media-src` y video fuera de `next/image` | V9 |

**Ronda de taste (skill `design-taste-frontend` con los 3 documentos de `docs/design/`, 2026-10-16):** 3 críticos, 15 significativos y 6 menores sobre la especificación visual; cada uno quedó dentro de su tarea: contrato de `Button`, campo y `Field` en 7.2 Paso 5; tokens y movimiento en 7.2 (los radios, en el Paso 2); titulares, sombras, toast, esqueleto, radios heredados y secciones en 7.3; `Sheet`, `AlertDialog` y la Task 3.6 en F3; cabecera en 8.2; tarjeta de paso y título en 8.3; aviso en 8.3b; barra y layout en 8.4a-8.4c; calendario en 8.5a-8.5d. **Los valores de marca entran en F7; F3 a F6 conservan el aspecto actual.**

---

## 1. Comparación: PFD vs skills de Vercel, y el plan unificado

### Dónde coinciden
| Tema | PFD | Vercel | Decisión |
|---|---|---|---|
| Una sola fuente visual | R3 fluidez | shadcn: «tokens, no hex ad-hoc; raw `button`/`input` es antipatrón» | Tokens + primitivas + compuerta |
| Menos peso inicial | R1/R2 carga y 50 ms | `bundle-*` y `rendering-*` (críticas) | Fase F1, antes que nada |
| Estados no felices diseñados | L3 sinceridad/confianza | shadcn: «loading/empty/error con tratamiento» | `error.tsx`, `global-error.tsx`, `loading.tsx` |

### Qué aporta solo Vercel (hallazgos medidos)
| # | Hallazgo medido | Regla | Impacto |
|---|---|---|---|
| V1 | 37 archivos importan `@phosphor-icons/react` por el barril (y 6 más `@phosphor-icons/react/ssr`) y `next.config.ts` no tiene `optimizePackageImports` | `bundle-barrel-imports` (CRÍTICA) | Mejora arranque en dev, build y cold start; en el bundle de producción puede quedar en ≈0 (el tree-shaking ya recorta), y eso no es un fallo |
| V2 | `stripe-panel.tsx` (611 líneas: Stripe + Elements + resumen + portal) se importa estático en las 3 vistas de compra | `bundle-dynamic-imports` (CRÍTICA) | Hay que **partir el módulo primero** (Task 1.2); después Stripe sale del chunk inicial y solo se baja al llegar a pagar. Los calendarios no se difieren (son del primer paso visible) |
| V3 | Se pasa el diccionario completo (`dict`, 55,8 KB en es) a 5 componentes cliente; solo usan `checkout` (18 KB), `pedido`, `traslados`, `feedback`, `continuar` | `server-serialization` (ALTA) | Ahorro modesto (~20 KB por idioma): Task 5.5, después de partir las vistas |
| V4 | 0 `<Suspense>`, solo 2 `loading.tsx` (reservar, traslados) y **ningún** `error.tsx`/`global-error.tsx` | `async-suspense-boundaries` (ALTA) + guía de errores de `nextjs` | Un fallo de la API tumba la página sin diseño |
| V5 | Video de 83,5 MB servido desde `public/` (`videohero.webm`), también referenciado por 2 sedes | `rendering-*` + `next/image` | Mayor riesgo de lanzamiento |
| V6 | 1 `<img>` cruda en `sede-hero.tsx:67` (`hub-hero.tsx` también tiene una, pero **nadie lo monta**: es código huérfano y la Task 5.4 lo borra; el héroe nuevo del hub es la Task 9.3) | guía `nextjs/image` | LCP y tamaños |
| V7 | `request()` en `lib/api.ts` hace `fetch` sin política de caché | `next-cache-components` (`use cache`, `cacheLife`, `cacheTag`) | Oportunidad solo para el catálogo público; **nunca** cupo ni cotización. Entra como sondeo (spike) con decisión, no como compromiso: primero el camino barato `fetch(url, { next: { revalidate, tags } })`; `cacheComponents` solo si compensa sus costos (Task 1.7) |
| V8 | Fuente `Bella Fashion` con licencia «personal use only» (aviso en `fonts/LICENCIAS.md`); `Bebas Neue` y `Instrument Sans` | — | Resuelto por el sistema de diseño: titulares en **Consola Mono** (SIL OFL, servida desde el sitio) y cuerpo en la **fuente del sistema** (San Francisco en Apple); salen Bella, Bebas e Instrument (F7). Menos descargas de fuentes |
| V9 | CSP `img-src 'self' data: blob:` | `nextjs` (imágenes remotas) | Si las fotos pasan a R2 hay que añadir el dominio a `img-src`/`media-src` y a `images.remotePatterns` (el `<video>` no pasa por `next/image`; `default-src 'self'` ya cubre el video local) |

### Qué aporta solo PFD (Vercel no lo cubre)
| # | Aporte | Por qué importa |
|---|---|---|
| P1 | R4: sin mezcla vieja/nueva en producción; checkout idéntico durante la base | Una marca aplicada a medias es una desviación accidental justo donde se paga (Clark 2013) |
| P2 | R5: la jerarquía del botón vive en la primitiva | Una marca nueva no puede dejar la acción principal con el mismo peso que las secundarias (Green & Swets 1966) |
| P3 | R2: un solo héroe, imagen inmediata, video después | La primera impresión se decide en 50 ms (Lindgaard 2006) |
| P4 | Compuerta anti casi-iguales (colores a ±5 % de un token) | Bujack et al. 2022 |

### Conflictos y cómo se resuelven
| Conflicto | Resolución |
|---|---|
| shadcn sugiere modo oscuro por defecto, zinc, Geist | **No aplica**: es un sitio de contenido con marca propia y tema claro bloqueado a propósito (`color-scheme: light`). El propio skill dice que lo content-first va en claro. Se toma el patrón de composición, no la estética |
| `use cache` (Cache Components) vs precios y cupos en vivo | Solo catálogo público (servicios/paquetes/sedes) y detrás de un sondeo. Cupo, cotización y pagos jamás. Invalidación por `cacheTag` + `revalidateTag` desde una ruta que llame el backend, o `cacheLife('minutes')` corto |
| Vercel recomienda dividir y lazy-load; PFD exige checkout idéntico | La carga perezosa de Stripe usa un *fallback* del mismo tamaño que el formulario real (sin salto de layout), así el cliente no ve diferencia |
| Compuerta estricta vs trabajo en curso | Compuerta con **trinquete**: el recuento de infracciones puede bajar, nunca subir; llega a 0 al cierre de F6 |

### Lo que cada fuente dejaba sin resolver y el plan cubre
- Los **tokens de la marca nueva**: la marca ya está entregada en `docs/design/`; F2/F3 se construyen con los valores actuales (y los nombres de la marca apuntando a ellos) y F7 aplica los valores nuevos.
- Las 20 suites cubren `lib/`, no componentes: la red de seguridad de F4/F5 es la compuerta + `tsc` + `build` + revisión del dueño. Se añade una prueba pura de variantes (F3) y se anota como limitación.

---

## 2. Mapa de archivos

| Archivo | Responsabilidad | Fase |
|---|---|---|
| `scripts/guardia-estilos.cjs` | Cuenta infracciones (colores literales, paleta cruda, `<button>`/`<input>` fuera de `ui/`, `<img>`, imports de `ui/` hacia fuera) ignorando comentarios, con exentos por regla y con motivo; falla si el **total de una regla** sube | F0 |
| `scripts/guardia-estilos.baseline.json` | Recuento inicial por regla y archivo (el detalle por archivo es solo informe; la compuerta compara totales por regla) | F0 |
| `tests/guardia-estilos.test.cjs` | Prueba la detección con cadenas de ejemplo; se corre con `node --test` (`npm run test:guardia`), fuera del runner de `lib/` | F0 |
| `docs/superpowers/plans/2026-10-15-frontend-base-linea-base.md` | Tamaños por ruta antes/después | F0 |
| `next.config.ts` | `optimizePackageImports`, `images`, CSP si hace falta | F1 |
| `src/app/[lang]/error.tsx`, `src/app/global-error.tsx` | Errores con diseño | F1 |
| `src/app/[lang]/{sede/[slug],servicio/[empresa]/[servicio]}/loading.tsx` | Esqueletos de carga (`catalogo/page.tsx` solo hace `redirect()` y nunca renderiza datos: no lleva) | F1 |
| `src/components/ui/cn.ts` | `clsx` + `tailwind-merge` | F3 |
| `src/components/ui/{caja-campo.ts,despliegue.tsx,error-de-campo.tsx}` | Movidos desde `checkout/` y `field-error` para que `ui/` no dependa de nada fuera de sí; los archivos viejos los reexportan hasta que F6 los borra | F3 |
| `src/components/checkout/pago/{resumen-pedido,tarjeta-como-pagas,nota-seguridad,formulario-pago,pago-diferido}.tsx` y `pago/tipos.ts` | `stripe-panel.tsx` partido: resumen y tarjeta «Cómo pagas» sin Stripe; solo `formulario-pago` importa Stripe | F1 |
| `src/lib/tokens-pago.ts` + `tests/tokens-pago.test.cjs` | Una sola fuente de los valores que Stripe Elements necesita en concreto (hex, radio), con prueba que la compara con `globals.css` | F2 |
| `src/components/ui/variantes.ts` | Mapas de variantes **puros, sin ningún import** (el runner los compila y los prueba sin DOM ni paquetes) | F3 |
| `src/components/ui/{button,input,field,card,chip-actividad,aviso-estado}.tsx` | Primitivas (`button`, `card` y los chips servibles desde servidor; `field` isla cliente) | F3 |
| `src/components/ui/{sheet,alert-dialog}.tsx` | Hoja y confirmación destructiva accesibles | F3 |
| `src/components/ui/{checkbox,opcion}.tsx` | Casilla y opción de radio (el interruptor no se crea hasta que exista un uso) | F3 |
| `src/components/ui/video-diferido.tsx` | Isla cliente que monta el `<video>` tras `load`/idle | F1 |
| `src/components/ui/hero-media.tsx`, `section-shell.tsx` | Héroe y sección únicos (el héroe del hub, con video y poster, también usa `HeroMedia`: Task 9.3) | F5 |
| `src/components/ui/motion-provider.tsx` | `LazyMotion` con `domAnimation` y `strict` | F1 |
| `src/components/checkout/pago/esqueleto-pago.tsx` | Esqueleto del formulario de tarjeta, sin Stripe; lo usan `formulario-pago` y el `loading` del `dynamic` | F1 |
| `src/lib/errores-textos.ts` | Textos es/en de las páginas de error (sin `server-only`) | F1 |
| `src/components/pedido/{grupo-viaje,grupo-datos}.tsx` | Las dos mitades de `GrupoServicio` (Viaje: personas, extras, tipo de traslado, fecha; Datos: recogida y zona) | F5 (5.3) |
| `scripts/medir-peso.cjs` | Métrica oficial de peso por ruta (crudo y gzip) | F0 |
| `src/lib/{borrador-reserva,origen}.ts` + sus pruebas | Borrador en la pestaña y origen de la flecha | F8 (8.0) |
| `src/lib/{problema-reserva,campo-paso,validar-reserva,etiqueta-boton,control-fecha,texto-localizado}.ts` + sus pruebas, `src/components/ui/aviso-accion.tsx` | Avisos con acción, mapa campo → paso, validación con dueño, etiqueta del botón, control de fecha por servicio y texto es/en con respaldo. (`lib/errores.ts` ya existe y no se toca: importa valores de `@/lib/api` y el runner no lo compila) | F8 (8.1, 8.1b, 8.3b, 8.4a, 8.5a) |
| `backend/apps/fleet/{models,serializers,admin}.py` + migración + `tests_personalizacion_descripcion.py` | `descripcion` es/en en `Personalizacion` (editable al crearla en el admin), expuesta en el serializer y mostrada bajo cada extra | F8 (8.1b) |
| `src/content/empresas.ts` + `tests/empresas.test.cjs` | Datos por empresa: descripción es/en, enlace oficial, redes, contacto **confirmado**, reseñas con su fuente y estado de confirmación, fotos propias | F9 |
| `src/lib/secciones-sede.ts` + `tests/secciones-sede.test.cjs`, `src/lib/etiquetas-catalogo.ts` + `tests/etiquetas-catalogo.test.cjs`, `tests/contenido-paridad.test.cjs` | Función pura: qué secciones de la sede se pintan y en qué orden y con qué estado según el contenido real; etiquetas, chips, «desde» y plantillas del catálogo; paridad de diccionarios es/en | F9 |
| `src/content/imagenes-catalogo.ts` + `tests/imagenes-catalogo.test.cjs`, `public/catalogo/*.webp` | Fotos HARDCODEADAS por ahora: mapa clave de servicio o paquete → `{ src, alt: {es,en} }` (≤ ~200 KB cada WebP); la prueba exige foto para todo el catálogo. Sin campo de imagen en el backend, sin R2, sin migración | F9 (9.0) |
| `src/lib/iniciales.ts` + `tests/iniciales.test.cjs`, `src/components/ui/empresa-sello.tsx` | Sello de empresa: logo o monograma, 24/32/64 (también es la marca provisional «SB» de Sun Baja Experience) | F3 (3.7) |
| `src/components/{que-puedes-reservar,tarjeta-servicio,hub-portada,tarjeta-sede-hub,fila-empresa,banda-colaboracion}.tsx` | Bloque de servicios y paquetes, tarjeta de servicio o paquete (con foto), héroe del hub (con video), tarjeta de sede del hub, directorio de empresas y la frase «Una colaboración entre…» de la sede (la galería y las preguntas frecuentes de la sede reutilizan `gallery-section.tsx` y `faq-section.tsx`, que se modifican) | F9 |
| `backend/apps/fleet/{models,serializers,admin}.py` + migración + `tests_incluye.py`, `backend/apps/tenancy/serializers.py` + prueba | Campo `incluye` en `Servicio` y `Paquete` y `resumen` («desde» y tipos) en `/api/sedes/` | F9 (9.0, 9.3) |
| `src/components/{reserva-tranquila,hub-como-funciona,opiniones-empresas}.tsx` | «Reserva con tranquilidad», «Cómo funciona» y reseñas atribuidas | F9 |
| `src/components/checkout/bloques/{bloque-viaje,bloque-extras,bloque-contacto,bloque-recogida,bloque-pago}.tsx` | Un archivo por **bloque** de contenido, extraídos de las vistas gigantes (F8 solo los reagrupa en 3 pasos) | F5 |
| `tests/variantes.test.cjs` | Prueba de las variantes | F3 |
| `src/app/fonts/ConsolaMono-Bold.woff2` + `OFL.txt` + `FONTLOG.txt` | Fuente de titulares recortada a latín; la licencia viaja con ella (Book no se incorpora: todos los titulares son 700) | F7 |
| `src/components/reserva/{cabecera-minima,linea-progreso,barra-inferior,asa-resumen}.tsx` | Piezas del asistente móvil y de la cabecera sin navbar | F8 (8.2, 8.4a) |
| `src/components/ui/calendario/{calendario,leyenda,atajos}.tsx` | Calendario completo, leyenda hecha con los mismos componentes que las celdas, y atajos | F8 (8.5b) |
| `src/lib/rango-paquete.ts` + `tests/rango-paquete.test.cjs` | Función pura que calcula el rango de un paquete de varias noches y dónde se corta por falta de cupo | F8 (8.5a) |

---

## F0 — Red de seguridad y línea base

### Task 0.1: Compuerta de estilos con trinquete

**Files:** Create `scripts/guardia-estilos.cjs`, `tests/guardia-estilos.test.cjs`; Modify `package.json`. (No se toca `tests/run-hub-tests.cjs`: ese runner compila con `rootDir: src` y un archivo de `scripts/` rompería **todas** las suites con TS6059.)

**Interfaces — Produces:** `npm run guardia` (sale con código 1 si el **total** de alguna regla sube respecto a `guardia-estilos.baseline.json`; mover código de un archivo a otro no sube el total) y las funciones exportadas `contar(texto, regla)` y `suben(base, actual)`.

- [ ] **Paso 1: prueba que falla** — `tests/guardia-estilos.test.cjs`:

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const { contar, sinComentarios, relativosFuera, suben } = require('../scripts/guardia-estilos.cjs');

test('cuenta controles y colores crudos', () => {
  assert.equal(contar('<button className="x">', 'boton-crudo'), 1);
  assert.equal(contar('<Button>', 'boton-crudo'), 0);
  assert.equal(contar('className="bg-red-400"', 'paleta-cruda'), 1);
  assert.equal(contar('className="bg-accent"', 'paleta-cruda'), 0);
  assert.equal(contar('style={{ color: "#fff" }}', 'color-literal'), 1);
  assert.equal(contar('<input type="text" />', 'input-crudo'), 1);
  assert.equal(contar('<img src="a" />', 'img-cruda'), 1);
  assert.equal(contar('<motion.div animate={{}} />', 'motion-completo'), 1);
  assert.equal(contar('<m.div animate={{}} />', 'motion-completo'), 0);
  assert.equal(contar('<input className="text-sm" />', 'texto-chico-en-campo'), 1);
  assert.equal(contar('<input className="text-base" />', 'texto-chico-en-campo'), 0);
  assert.equal(contar('<input onChange={(e) => a(e)} className="text-sm" />', 'texto-chico-en-campo'), 1);
  assert.equal(contar('className="uppercase"', 'mayusculas-crudas'), 1);
  assert.equal(contar('className="uppercase tracking-wider"', 'mayusculas-crudas'), 2); // cada clase cuenta
  assert.equal(contar('className="rounded-xl"', 'radio-crudo'), 1);
  assert.equal(contar('className="rounded-t-xl"', 'radio-crudo'), 1);
  assert.equal(contar('className="rounded-card"', 'radio-crudo'), 0);
  assert.equal(contar('className="shadow-lg"', 'sombra-cruda'), 1);
  assert.equal(contar('className="shadow-n2"', 'sombra-cruda'), 0);
  assert.equal(contar('className="bg-surface-deep"', 'surface-deep'), 1);
  assert.equal(contar('className="bg-surface p-4"', 'bg-surface-uso'), 1);
  assert.equal(contar('className="bg-surface-deep"', 'bg-surface-uso'), 0); // surface-deep tiene su regla
  assert.equal(contar('className="bg-superficie"', 'bg-surface-uso'), 0);
});

test('ignora comentarios y anclas parecidas a un hex', () => {
  assert.equal(contar(sinComentarios('// usa <button> aquí\nconst a = 1;'), 'boton-crudo'), 0);
  assert.equal(contar(sinComentarios('/* <img src="x" /> */ const a = 1;'), 'img-cruda'), 0);
  assert.equal(contar('<a href="#add">', 'color-literal'), 0);
  assert.equal(contar('<a href="#bad">', 'color-literal'), 0);
  assert.equal(contar('url(#grad)', 'color-literal'), 0);
  assert.equal(contar("colorPrimary: '#281ab5'", 'color-literal'), 1);
  assert.equal(contar('fill="#fff"', 'color-literal'), 1);
  assert.equal(contar('bg-[#281ab5]', 'color-literal'), 1);
  assert.equal(contar('rgba(0,0,0,.5)', 'color-literal'), 1);
});

test('capas: ui no importa fuera de ui y lib', () => {
  assert.equal(contar("import { x } from '@/components/checkout/estilos';", 'capas-ui'), 1);
  assert.equal(contar("import { x } from '@/components/ui/cn';", 'capas-ui'), 0);
  assert.equal(contar("import { x } from '@/lib/moneda';", 'capas-ui'), 0);
  assert.equal(contar("import { clsx } from 'clsx';", 'capas-ui'), 0);
  assert.equal(relativosFuera("import x from '../checkout/estilos';", 'src/components/ui/a.tsx'), 1);
  assert.equal(relativosFuera("import x from './cn';", 'src/components/ui/a.tsx'), 0);
  assert.equal(relativosFuera("import x from '../cn';", 'src/components/ui/calendario/a.tsx'), 0);
  assert.equal(relativosFuera("import x from '../../checkout/y';", 'src/components/ui/calendario/a.tsx'), 1);
});

test('trinquete por total de regla: mover código no sube, añadir sí', () => {
  // mover una infracción de a.tsx a b.tsx: el total de la regla no cambia
  assert.deepEqual(suben({ 'boton-crudo': { 'a.tsx': 1 } }, { 'boton-crudo': { 'b.tsx': 1 } }), []);
  // una infracción nueva en b.tsx sin quitar la de a.tsx: el total sube
  assert.equal(suben({ 'boton-crudo': { 'a.tsx': 1 } }, { 'boton-crudo': { 'a.tsx': 1, 'b.tsx': 1 } }).length, 1);
  // una regla que no estaba en la línea base y aparece: sube
  assert.equal(suben({}, { 'img-cruda': { 'a.tsx': 1 } }).length, 1);
});
```

- [ ] **Paso 2:** correr `node --test tests/guardia-estilos.test.cjs` → falla («no existe el módulo»).
- [ ] **Paso 3: implementar** `scripts/guardia-estilos.cjs` (CommonJS para cargarlo sin compilar):

```js
const fs = require('node:fs');
const path = require('node:path');

const REGLAS = {
  'boton-crudo': /<button\b/g,
  'input-crudo': /<(input|select|textarea)\b/g,
  'img-cruda': /<img\b/g,
  'paleta-cruda':
    /\b(?:bg|text|border|ring|from|to|via|fill|stroke|divide|outline)-(?:red|green|blue|amber|sky|gray|slate|zinc|neutral|stone|yellow|orange|emerald|teal|indigo|violet|purple|pink|rose|lime|cyan|fuchsia)-\d{2,3}\b/g,
  // Un hex real tiene 3, 4, 6 u 8 dígitos. Cuenta los que van entre comillas ("#fff", '#281ab5'),
  // que son casi todos los reales; excluye solo anclas (href="#add"), entidades (&#xA9;) y url(#grad).
  'color-literal': /(?<!\w|[&\/#]|href=["'])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b(?![-\w])|\brgba?\(/g,
  // Dentro de ui/: cualquier import que no sea paquete, relativo, '@/components/ui/' ni '@/lib/'.
  'capas-ui': /from\s+['"]@\/(?!components\/ui\/|lib\/)[^'"]*['"]/g, // los imports relativos que escapan de ui/ los cuenta relativosFuera()
  // Con LazyMotion strict, `motion.*` falla en desarrollo y en producción pierde el ahorro: solo `m.*`.
  'motion-completo': /\bmotion\.(?:div|span|button|a|ul|li|section|p|h[1-6]|svg|path|img|nav|header|footer|article|form|input|label)\b/g,
  // Reglas de la marca nueva (taste): cuentan hoy y llegan a 0 al cierre de F7.
  'texto-chico-en-campo': /<(?:input|select|textarea)\b(?:=>|[^>])*?\btext-(?:xs|sm)\b/g, // límite: no ve tamaños que vienen de un className externo o de una constante
  'mayusculas-crudas': /\b(?:uppercase|tracking-wider|tracking-widest)\b/g,
  'radio-crudo': /\brounded(?:-[trblse]{1,2})?-(?:md|lg|xl|2xl|3xl)\b/g, // incluye rounded-t-xl, rounded-b-lg…
  'sombra-cruda': /\bshadow-(?:\[|xs\b|sm\b|md\b|lg\b|xl\b|2xl\b)/g,
  'surface-deep': /\bbg-surface-deep\b/g,
  // Los 77 usos de bg-surface se clasifican en la Task 2.4; cuenta hoy y baja hasta lo que quede como banda de sección.
  'bg-surface-uso': /\bbg-surface(?![-\w])/g,
};

// Exentos POR REGLA y con motivo: valores que una API externa pide en concreto, no como var().
// Un archivo exento de una regla sigue midiéndose en todas las demás (p. ej. lang-switch.tsx
// sigue contando sus <button> y sus motion.*). `globals.css` no figura: el escáner solo lee .ts/.tsx.
const EXENTOS = {
  'src/app/[lang]/opengraph-image.tsx': { reglas: ['color-literal'], motivo: 'ImageResponse no lee CSS' },
  'src/components/lang-switch.tsx': { reglas: ['color-literal'], motivo: 'SVG de banderas con colores propios' },
  'src/lib/tokens-pago.ts': { reglas: ['color-literal'], motivo: 'única fuente de lo que Stripe Elements pide en concreto' },
};
// Las primitivas son el único lugar donde vive el HTML crudo de estos controles.
const SOLO_FUERA_DE_UI = ['boton-crudo', 'input-crudo'];

function sinComentarios(texto) {
  return texto.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
}

function contar(texto, regla) {
  return (texto.match(REGLAS[regla]) ?? []).length;
}

// Imports relativos dentro de ui/ que resuelven fuera de ui/ y lib/ (el alias @/ ya lo ve la regex).
function relativosFuera(texto, rel) {
  let n = 0;
  for (const m of texto.matchAll(/from\s+['"](\.{1,2}\/[^'"]*)['"]/g)) {
    const destino = path.posix.join(path.posix.dirname(rel), m[1]);
    if (!destino.startsWith('src/components/ui/') && !destino.startsWith('src/lib/')) n++;
  }
  return n;
}

function* archivos(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) yield* archivos(p);
    else if (/\.(tsx|ts)$/.test(e.name)) yield p;
  }
}

function medir(raiz) {
  const resultado = {};
  for (const abs of archivos(path.join(raiz, 'src'))) {
    const rel = path.relative(raiz, abs).split(path.sep).join('/');
    const enUi = rel.startsWith('src/components/ui/');
    const texto = sinComentarios(fs.readFileSync(abs, 'utf8'));
    for (const regla of Object.keys(REGLAS)) {
      if (EXENTOS[rel]?.reglas.includes(regla)) continue; // exento de esta regla, no del archivo entero
      if (SOLO_FUERA_DE_UI.includes(regla) && enUi) continue;
      if (regla === 'capas-ui' && !enUi) continue;
      const n = contar(texto, regla) + (regla === 'capas-ui' ? relativosFuera(texto, rel) : 0);
      if (n > 0) (resultado[regla] ??= {})[rel] = n;
    }
  }
  return resultado;
}

// Trinquete por TOTAL de regla: mover código de un archivo a otro (extracciones de F1, F4 y F5)
// no cambia el total, así que no falla. El detalle por archivo de la línea base es solo informe.
function suben(base, actual) {
  const total = (o, r) => Object.values(o[r] ?? {}).reduce((a, n) => a + n, 0);
  return [...new Set([...Object.keys(base), ...Object.keys(actual)])]
    .map((r) => [r, total(base, r), total(actual, r)])
    .filter(([, antes, ahora]) => ahora > antes);
}

module.exports = { contar, sinComentarios, medir, relativosFuera, suben, EXENTOS };

if (require.main === module) {
  const raiz = path.resolve(__dirname, '..');
  const baselinePath = path.join(__dirname, 'guardia-estilos.baseline.json');
  const actual = medir(raiz);
  if (process.argv.includes('--escribir')) {
    fs.writeFileSync(baselinePath, JSON.stringify(actual, null, 2) + '\n');
    console.log('Línea base escrita.');
    process.exit(0);
  }
  const base = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const subidas = suben(base, actual);
  subidas.forEach(([r, a, n]) => console.error(`SUBE ${r}: ${a} -> ${n}`));
  const total = (o) => Object.values(o).reduce((a, p) => a + Object.values(p).reduce((x, y) => x + y, 0), 0);
  console.log(`Infracciones: ${total(actual)} (línea base ${total(base)})`);
  process.exit(subidas.length > 0 ? 1 : 0);
}
```

Las regex de `color-literal` y `capas-ui` son delicadas: **la prueba del Paso 1 es la especificación**; si una regex no la pasa, se ajusta la regex, no la prueba.

**La línea base por archivo es solo informe; la compuerta compara totales por regla.** `--escribir` solo se corre cuando el `git diff` de la línea base muestra totales que bajan o se mueven (nunca para «hacer pasar» una subida). Una regla nueva que se añada a `REGLAS` (p. ej. `titular-sin-escala` en 7.3) se acompaña de `--escribir` en el mismo commit, y el diff debe mostrar solo la regla nueva.

- [ ] **Paso 4:** en `package.json` añadir `"guardia": "node scripts/guardia-estilos.cjs"` y `"test:guardia": "node --test tests/guardia-estilos.test.cjs"`; correr `npm.cmd run test:guardia` → pasa. (`npm test` y su runner no se tocan; `verificar` en F6 corre ambos.)
- [ ] **Paso 5:** generar la línea base con `node scripts/guardia-estilos.cjs --escribir`; correr `npm.cmd run guardia` → «Infracciones: N (línea base N)», código 0.
- [ ] **Paso 6: commit** `chore(frontend): compuerta de estilos con trinquete y línea base`.

### Task 0.2: Línea base de carga

**Files:** Create `docs/superpowers/plans/2026-10-15-frontend-base-linea-base.md`, `scripts/medir-peso.cjs`.

- [ ] **Paso 1:** `npm.cmd run build`; crear `scripts/medir-peso.cjs` (**métrica oficial de antes/después**; Next 16 ya no imprime «First Load JS»). Algoritmo: (1) `next start` en :3000; (2) por cada ruta, `GET` del HTML; (3) extraer los `src` de los `<script>` y los `href` de los `<link rel="preload" as="script">` que empiecen con `/_next/static/`; (4) para cada archivo en `.next/static/…` sumar `fs.statSync().size` (crudo) y `zlib.gzipSync().length` (gzip); (5) una fila por ruta. Rutas: `/es`, `/es/sede/la-paz`, `/es/servicio/sal-y-sol/pesca-deportiva`, `/es/reservar` y `/es/traslados`. Los chunks de `dynamic()` no entran (es justo lo que prueba el `curl` de Stripe). Copiar la tabla al archivo de línea base. `next experimental-analyze` queda solo para diagnóstico: sin navegador se usa `npx.cmd next experimental-analyze --output` y se comparan las carpetas de `.next/diagnostics/analyze`.
- [ ] **Paso 2:** añadir `du -sh public/videos public/photos` y el tamaño de `en.json`/`es.json`.
- [ ] **Paso 3: commit** `docs(frontend): línea base de carga antes de la optimización`.

---

## F1 — Carga y resiliencia (independiente del rediseño; se puede hacer ya)

> Es lo que más ayuda al lanzamiento y no depende de la marca. PUNTO DEL DUEÑO al cerrar F1: la sede La Paz (video e imagen), el primer paso de `/reservar`, los esqueletos de sede y servicio y `/es/prueba-error` (la portada no se toca en F1: no tiene héroe ni video).

### Task 1.1: `optimizePackageImports` (V1)

**Files:** Modify `next.config.ts`.

- [ ] **Paso 1:** leer `node_modules/next/dist/docs/` sobre `optimizePackageImports` en Next 16 y confirmar el nombre de la opción (puede haber salido de `experimental`).
- [ ] **Paso 2:** añadir al objeto `nextConfig`:

```ts
experimental: {
  optimizePackageImports: ['@phosphor-icons/react', '@phosphor-icons/react/ssr', 'motion/react'],
},
```

(ajustar la ubicación si en 16.3 ya no es experimental).
- [ ] **Paso 3:** `npm.cmd run build`; medir con `scripts/medir-peso.cjs` y anotar el cambio en el archivo de línea base. El beneficio es sobre todo arranque en dev, tiempo de build y cold start; un cambio ≈0 en el bundle de producción no es un fallo. Los especificadores reales del código son `motion/react` (20 archivos) y `@phosphor-icons/react/ssr` (6).
- [ ] **Paso 4: commit** `perf(frontend): importar iconos y motion por módulo`.

### Task 1.2a: Partir `stripe-panel.tsx` en archivos sin Stripe (V2, primera mitad)

> Corrección del crítico: `stripe-panel.tsx` es **un módulo de 611 líneas** que importa `@stripe/stripe-js` y `@stripe/react-stripe-js` arriba y exporta `NotaSeguridadStripe`, `FormularioPago` y `StripePanel`. `StripePanel` pinta el resumen vivo del pedido desde el paso 1 **y**, por portal (`createPortal` hacia `destinoTarjeta`), la tarjeta «Cómo pagas» (promo, deslinde, Turnstile). Si el resumen sigue importando del módulo entero, Stripe viaja en el chunk inicial y el `dynamic` es decorativo; si se difiere el panel completo, el resumen y el portal desaparecen en SSR y se rompen el `ref` y el `scrollIntoView` de `checkout-view.tsx:827`. Por eso la tarea se divide en dos commits: **1.2a** (esta) solo parte el módulo, sin cambiar cuándo carga Stripe; **1.2b** difiere el formulario de tarjeta. Ambas llevan revisión del dueño del flujo de cobro.

**Files:** Create `src/components/checkout/pago/resumen-pedido.tsx`, `tarjeta-como-pagas.tsx`, `nota-seguridad.tsx`, `tipos.ts`, `formulario-pago.tsx`; Modify `src/components/stripe-panel.tsx` (queda como fachada que reexporta), `checkout-view.tsx:23`, `pedido/pedido-paquete.tsx:22`, `traslado-view.tsx:11`.

**Interfaces — Produces:** `StripePanel` (sin Stripe: resumen + portal de la tarjeta «Cómo pagas»), `NotaSeguridadStripe` (en `pago/nota-seguridad.tsx`, sin Stripe: la pintan tanto `FormularioPago` como las vistas) y `FormularioPago` (único módulo que importa `loadStripe`, `Elements`, `PaymentElement`); los tipos compartidos `StripePanelProps`, `OrderLine` y `Phase` viven en `pago/tipos.ts` (evita un ciclo de tipos entre el resumen, la tarjeta y la fachada). Las props públicas no cambian.

- [ ] **Paso 1:** leer `stripe-panel.tsx` completo y escribir en el mensaje del commit qué función va a qué archivo y qué estado compartían (`puente`, `pago`, `captchaKey`).
- [ ] **Paso 2:** mover `PaymentForm`, `STRIPE_APARIENCIA`, `STRIPE_FUENTES`, `loadStripe`/`Elements` y `FormularioPago` a `formulario-pago.tsx`. Mover el resumen y `TarjetaComoPagas` a archivos sin imports de Stripe. `stripe-panel.tsx` queda como fachada que reexporta **solo** `StripePanel` y `NotaSeguridadStripe`; no reexporta `FormularioPago`. Las tres vistas dejan de importar `{ FormularioPago, StripePanel }` de `stripe-panel` (`checkout-view.tsx:23`, `pedido-paquete.tsx:22`, `traslado-view.tsx:11`): toman `StripePanel` de la fachada y `FormularioPago` **estático** de `pago/formulario-pago` (en esta tarea Stripe sigue en el chunk de la vista; el `dynamic` es de 1.2b).
- [ ] **Paso 3:** `tsc`, `eslint`, `npm test`, `build`. Comprobar con `grep -rn "@stripe" src` que **solo** `formulario-pago.tsx` importa Stripe. La compuerta (`guardia`) no sube: los `<button>` y el hex de `STRIPE_APARIENCIA` que se mueven a `pago/*.tsx` cambian de archivo, no de total.
- [ ] **Paso 4: PUNTO DEL DUEÑO** — recorrer con tarjeta de prueba de Stripe los **cuatro** caminos: servicio suelto, paquete de una empresa, paquete cruza-empresa (incluido el rechazo tras retención del primer pago) y traslados; y recargar a media compra. No se avanza sin su luz verde.
- [ ] **Paso 5: commit** `refactor(checkout): stripe-panel partido en archivos sin Stripe`.

### Task 1.2b: El formulario de tarjeta carga Stripe bajo demanda (V2, segunda mitad)

> Requiere 1.2a hecha. Aquí sí cambia cuándo se baja Stripe.

**Files:** Create `src/components/checkout/pago/pago-diferido.tsx`, `pago/esqueleto-pago.tsx`; Modify `checkout/pago/formulario-pago.tsx`, `checkout-view.tsx`, `pedido/pedido-paquete.tsx`, `traslado-view.tsx`, `components/skeleton.tsx` (solo su comentario).

**Interfaces — Produces:** `FormularioPagoDiferido` y `precargarFormularioPago` (en `pago-diferido.tsx`; es el **único** módulo que importa `formulario-pago.tsx`, y de forma dinámica) y `EsqueletoPago`.

- [ ] **Paso 1:** crear `pago-diferido.tsx`:

```tsx
'use client';

import dynamic from 'next/dynamic';
import { EsqueletoPago } from '@/components/checkout/pago/esqueleto-pago';

export const FormularioPagoDiferido = dynamic(
  () => import('@/components/checkout/pago/formulario-pago').then((m) => m.FormularioPago),
  { ssr: false, loading: () => <EsqueletoPago /> },
);
```

  El esqueleto dura **hasta `onReady` del `PaymentElement`**, no solo hasta que baja el chunk (si no, hay salto cuando aparece el iframe). El `loading` de `dynamic` solo cubre la descarga del chunk: el esqueleto de la fase `onReady` vive en `pago/esqueleto-pago.tsx` (sin imports de Stripe), se pinta superpuesto con la misma altura dentro de `formulario-pago.tsx` hasta `onReady`, y el `loading` del `dynamic` usa ese mismo componente. **No pulsa** (design-guidelines: no se anima el contenido de pago): es un bloque estático con las filas del formulario dibujadas (número, vencimiento y CVC de 48 px de alto) que se desvanece con opacidad de 150 ms al llegar `onReady`. Ningún elemento con `transform`, `filter` ni `will-change` puede ser ancestro del iframe de Stripe. **Altura (sin navegador no se puede medir):** `EsqueletoPago` usa `min-h-[19rem]` provisional; el dueño la ajusta en el Paso 5 mirando el salto al cargar el iframe.
- [ ] **Paso 2:** actualizar el comentario de `components/skeleton.tsx` (líneas 8-11 dicen que para el iframe de Stripe un esqueleto «es peor que no poner nada»): el esqueleto de pago es estático, de altura fija y sin pulso.
- [ ] **Paso 3:** en las 3 vistas, sustituir el `FormularioPago` estático de 1.2a por `FormularioPagoDiferido`. `StripePanel`, `ref`, portal y `key={captchaKey}` no se tocan. **Precarga (`bundle-preload`):** `pago-diferido.tsx` exporta también `precargarFormularioPago = () => import('@/components/checkout/pago/formulario-pago')`; se llama al montar el paso de datos o «Cómo pagas», o al acercarse al botón de continuar a pago, para que el chunk y `js.stripe.com` ya estén listos al crear la orden. Cargar Stripe.js tarde además reduce sus señales antifraude.
- [ ] **Paso 4:** `build`, `grep -rn "formulario-pago" src` (solo `pago-diferido.tsx` lo importa, de forma dinámica), `next start` y la prueba binaria de Restricciones globales (`curl` de `/es/reservar` y `/es/traslados` sin `js.stripe.com` ni `@stripe` en HTML ni chunks iniciales); además medir con `scripts/medir-peso.cjs` contra la línea base: el chunk inicial de esas rutas debe bajar.
- [ ] **Paso 5: PUNTO DEL DUEÑO** — repetir los **cuatro** caminos con tarjeta de prueba (servicio suelto, paquete de una empresa, cruza-empresa con rechazo tras la retención del primer pago, traslados), recargar a media compra y ajustar la altura provisional del esqueleto mirando el salto cuando carga el iframe. No se avanza sin su luz verde.
- [ ] **Paso 6: commit** `perf(checkout): el formulario de tarjeta carga Stripe bajo demanda`.

> Los calendarios (`DateField`, `CheckoutCalendar`) **no** se difieren en F1: son parte del primer paso visible; diferirlos produciría el salto que R4 prohíbe. Se reevalúa tras F5 con las medidas reales.

### Task 1.3: Páginas de error con diseño (V4)

**Files:** Create `src/app/[lang]/error.tsx`, `src/app/global-error.tsx`.

- [ ] **Paso 1:** leer la guía `nextjs` de manejo de errores y `node_modules/next/dist/docs/` para la firma de `error.tsx` en 16.3.6: **`{ error, retry }`** (`retry()` vuelve a pedir los datos; `reset` solo limpia el estado sin repedir; `unstable_retry` no existe). `[lang]/error.tsx` **no** atrapa fallos de `[lang]/layout.tsx` (p. ej. `getDictionary`): esos caen en `global-error.tsx`.
- [ ] **Paso 2:** `error.tsx` es Client Component y `dictionaries.ts` es `server-only`: **no puede importar el diccionario** (y traerlo al cliente metería ~56 KB por idioma). Toma el idioma con `useParams().lang` y los textos de un módulo pequeño `src/lib/errores-textos.ts` (solo es/en de error). `useParams().lang` es `string | string[] | undefined` y existe `[...resto]`: el módulo normaliza a es/en con fallback a es y no importa `dictionaries.ts`. Botón «Reintentar» que llama `retry()` y enlace a la portada. Registrar el error con su `digest` en consola.
- [ ] **Paso 3:** `global-error.tsx` mínimo (incluye `<html>`/`<body>` y no tiene estilos globales), con texto estático bilingüe de `errores-textos.ts` y `retry()`.
- [ ] **Paso 4:** tipos y `build`. Para ver `error.tsx` sin simular nada en producción: crear la ruta temporal `src/app/[lang]/prueba-error/page.tsx` con `throw new Error('prueba')` (sin guion bajo inicial: Next trata `_carpeta` como privada y no la enruta), `npm run build && npm start`, y el dueño abre `/es/prueba-error` en el PUNTO DEL DUEÑO de F1. Borrar la ruta antes del commit. (Construir con la API en un puerto muerto no sirve: todas las páginas atrapan el fallo con `.catch(() => null)` y renderizan su estado vacío, así que no se vería ningún error con diseño.)
- [ ] **Paso 5: commit** `feat(frontend): páginas de error con diseño propio`.

### Task 1.4: Esqueletos de carga en las rutas con datos (V4)

**Files:** Create `loading.tsx` en `src/app/[lang]/sede/[slug]/` y `servicio/[empresa]/[servicio]/`. (`catalogo/page.tsx` es solo un `redirect()` y nunca renderiza datos: su `loading.tsx` no se vería nunca.)

- [ ] **Paso 1:** para cada ruta, leer su `page.tsx` y copiar la estructura de la página con `Skeleton`, al estilo de `reservar/loading.tsx`. Revisar también la cascada (`async-parallel`): `getDictionary`, `await searchParams` y las llamadas a la API se lanzan en paralelo (`Promise.all`) donde no dependen entre sí, y las secciones que dependen de la API van envueltas en `<Suspense>` (hoy hay 0), de modo que `loading.tsx` no reemplace la página entera, **salvo la sede**, cuyo `loading.tsx` es el límite (Task 9.1b Paso 1: la sede no usa `<Suspense>` porque sus anclas dependen de la lista de secciones).
- [ ] **Paso 2:** `build`. **Paso 3: commit** `feat(frontend): esqueletos de carga en sede y servicio`.

### Task 1.5: Héroe — imagen inmediata y video ligero (V5, V6, PFD R2)

**Files:** Create `src/components/ui/video-diferido.tsx`; Modify `src/components/sede-hero.tsx` (el `<video>` y la `<img>` de la línea ~67); Replace `public/videos/videohero.webm`. (El `Hero` viejo de la portada ya se eliminó. `hub-hero.tsx` está huérfano, nadie lo monta: su destino se decide en la Task 9.3.)

- [ ] **Paso 1: comprimir el video** (hay `ffmpeg` instalado):

```bash
ffmpeg -i public/videos/videohero.webm -vf "scale=-2:720,fps=24" -c:v libvpx-vp9 -crf 38 -b:v 0 -an -row-mt 1 public/videos/videohero.min.webm
ls -la public/videos/
```

Objetivo: ≤ 8 MB. Si se ve mal, subir calidad hasta que el dueño lo apruebe (PUNTO DEL DUEÑO: mirar el video). Añadir también una versión `.mp4` (H.264) como segunda `<source>` solo si hay navegadores objetivo sin VP9.
- [ ] **Paso 2:** reemplazar el archivo en las rutas de `sedes-cuerpo.ts` (2 referencias).
- [ ] **Paso 3:** en `sede-hero.tsx` la imagen del héroe se sirve con `next/image` y **`preload`** (en Next 16 `priority` está deprecado; `image.md`) como capa inferior: es el LCP real. El `<video>` ya no va en el HTML inicial: `ui/video-diferido.tsx` es una isla cliente que lo monta tras `load`/idle **solo si** no hay `prefers-reduced-motion` ni `saveData`, y lo funde sobre la imagen al disparar `canplay`. (`autoPlay` anula `preload="metadata"`, y el CSS no puede detener el autoplay por `reduce`.) Sin video: solo imagen.
- [ ] **Paso 4:** en `sede-hero.tsx:67` reemplazar `<img>` por `<Image fill sizes="100vw" preload alt="" className="object-cover" />`.
- [ ] **Paso 5:** `npm.cmd run guardia -- ` (la regla `img-cruda` baja en 1) y actualizar la línea base con `node scripts/guardia-estilos.cjs --escribir`.
- [ ] **Paso 5b (sin navegador):** `next start` y `curl` de `/es` y de una sede: el `<link rel="preload" as="image">` del héroe está en el HTML y no hay `<video>` en el HTML inicial.
- [ ] **Paso 6: commit** `perf(frontend): video de la sede comprimido, imagen inmediata y next/image en el héroe de la sede`.
- **Después, fuera de este plan:** mover el video a R2 (dominio en `img-src`/`media-src` de la CSP y en `images.remotePatterns`, hallazgo V9).

### Task 1.6: Pre-conexión a la API y CORS (opcional, de bajo riesgo)

- [ ] En los `page.tsx` (Server Components) de `reservar`, `traslados` y `servicio/[empresa]/[servicio]` —esas rutas no tienen `layout.tsx`, y el layout raíz cubriría todo el sitio— añadir `import { preconnect } from 'react-dom'` y llamar `preconnect(process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000', { crossOrigin: 'anonymous' })` (la conexión es de `fetch` CORS; sin `crossOrigin` el navegador abre otra) **solo ahí**, no en la portada ni en el layout raíz (regla `rendering-resource-hints`). Además, `request()` de `lib/api.ts` manda `Content-Type: application/json` incluso en GET, lo que fuerza un preflight en cada `getCupo`/`getCupoRango` cross-origin: enviarlo solo cuando hay body (pesa en el calendario completo de 8.5b; `django-cors-headers` ya envía `Access-Control-Max-Age` de 86400 por defecto, no hay que pedir nada al backend). Commit `perf(frontend): preconexión a la API`.

### Task 1.7: Sondeo de Cache Components (V7) — decisión, no código en producción

- [ ] Leer `node_modules/next/dist/docs/` sobre `cacheComponents` y `use cache` en 16.3. **Primero** evaluar el camino barato sin activar `cacheComponents`: `fetch(url, { next: { revalidate, tags } })` en las GET del catálogo público dentro de `request()`. Solo si no basta, probar `cacheComponents` en una rama aparte con `getServicioDetalle`/`getPaqueteDetalle` y `cacheLife('minutes')`, **listando sus costos**: todo `await params/searchParams` fuera de `<Suspense>` pasa a dinámico y rompe el build en sede, servicio y `/reservar`; activa `<Activity>` en la navegación (las rutas ocultas conservan estado y limpian efectos: Turnstile, `sessionStorage`, `captchaKey`); un `searchParams` solo para `moneda` vuelve dinámica toda la sede. Escribir en el archivo de línea base: qué ruta mejora, cuánto, y cómo se invalida un precio editado en el backoffice. **Sin decisión del dueño no se activa.** Cupo, cotización y pagos quedan fuera siempre.

### Task 1.8: `LazyMotion` en lugar de `motion` completo

**Files:** los ~20 componentes que importan de `motion/react` (incluidos `cookie-notice.tsx` y `lang-switch.tsx`, que están en el layout y viajan en todas las páginas); Create `src/components/ui/motion-provider.tsx`.

- [ ] **Paso 1:** cargar `vercel:react-best-practices` (`bundle-conditional`, `bundle-dynamic-imports`) y `apple-design` (para no cambiar la física de los resortes). `motion-provider.tsx`: `LazyMotion` con `features={domAnimation}` y `strict`, montado en el layout. `domAnimation` se carga **síncrono** (no con `import()` diferido) para evitar «pop-in» en la primera animación: excepción deliberada a `bundle-dynamic-imports`. El provider debe envolver `CookieNotice`, `LangSwitch` y `ProveedorToast`, que viven en `[lang]/layout.tsx`. `strict` solo lanza en desarrollo: en producción un `motion.*` suelto compila y pierde el ahorro; por eso la regla `motion-completo` de la compuerta (Task 0.1) lo cuenta y debe quedar en 0.
- [ ] **Paso 2:** sustituir `motion.*` por `m.*` en cada componente, sin tocar valores de animación. `hub-mapa-sedes.tsx:~49` usa `drag` (solo existe en `domMax`): con `domAnimation` el mapa dejaría de arrastrarse sin error. Ese componente lleva su propio `<LazyMotion features={domMax} strict>` anidado y `m.div`; igual cualquier otro que use `layout`.
- [ ] **Paso 3:** `tsc`, `eslint`, `npm test`, `build`; medir con `scripts/medir-peso.cjs` contra la línea base. El aspecto no cambia. **Paso 4: commit** `perf(frontend): LazyMotion con domAnimation`.

---

## F2 — Tokens completos, sin cambiar un solo valor (PFD R3)

> Idea clave: en Tailwind 4, las utilidades `rounded-lg`, `shadow-md` o `text-sm` ya leen `--radius-lg`, `--shadow-md` y `--text-sm` (Tailwind emite esas variables en `:root` cuando una utilidad las usa). Copiar los valores por defecto a `globals.css` no cambia nada, así que F2 **no** los copia: declara solo los tokens semánticos de forma y los aditivos que F3 a F6 necesitan, y los nombres de color de la marca apuntando a los valores actuales. F7 sobrescribe `--radius-md…2xl` y los valores de marca en un solo sitio. Sin diferencia visual.

### Task 2.1: Declarar forma, sombra, nombres de color y tokens aditivos

**Files:** Modify `src/app/globals.css`.

> Corrección del crítico: el bloque actual es `@theme inline` y contiene los colores como `--color-x: var(--y)`. **No se toca ni se le quita `inline`** (afectaría `bg-card` con opacidad). Se añade un **segundo bloque `@theme { … }`** aparte para las formas y los tokens aditivos; los alias de color con `var()` van dentro del bloque `@theme inline` existente. El CSS generado solo gana reglas nuevas.

- [ ] **Paso 1:** añadir tokens **semánticos de forma**, para que la marca cambie la forma de los controles sin tocar componentes (corrige el supuesto falso de que `--radius-lg` mueve `rounded-full`):

```css
@theme {
  /* Forma de los controles: hoy botones en píldora y campos con radio medio. */
  --radius-control: 9999px;         /* botones: hoy rounded-full */
  --radius-campo: var(--radius-lg); /* campos y cajas: hoy rounded-lg */
}
```

  Las variantes (F3) y `CAJA_CAMPO` usarán `rounded-control` y `rounded-campo`. Añadir también `--color-ring` (foco) y mapear `border-red-400` de `CAJA_CAMPO_ERROR` a `border-error`. Declarar también `--shadow-n0` (none), `--shadow-n1` y `--shadow-n2` con los valores de las sombras actuales (n1 = barra inferior, n2 = popover, toast y hoja), para que `Sheet` (Task 3.5) los use desde F3 y F7.3 solo cambie sus valores.
- [ ] **Paso 1b (aditivo, sin consumidores, sin cambio visual):** declarar en `@theme` lo que no sustituye a nada existente y que F3 y F5 necesitan: `--duracion-corta|media|larga`, `--curva-estandar`, `--curva-salida`; `--radius-casilla` (6 px); `--color-azul|coral|verde` con `-hondo|-profundo|-medio|-claro|-bruma`, `--color-coral-texto`, `--color-info`, `--color-info-fondo`; `--scrim-hoja` (tinta al 40 %) y `--scrim-hero` (con los degradados actuales de `sede-hero`); la escala `--z-cabecera: 40; --z-barra: 50; --z-hoja: 60; --z-toast: 70` (la única declaración: la Task 8.2 la usa, no la repite); y las clases semánticas `texto-display|pagina|seccion|paso|subtitulo|cuerpo|pequeno|etiqueta|pie` en `@layer components` con **los tamaños actuales** que hoy cubren (p. ej. `texto-subtitulo` = `text-xl font-semibold`). **No se declaran aquí `--radius-xs|sm|full`:** F7.2 Paso 2 los fija (hoy `rounded-xs` y `rounded-sm` tienen 0 usos).
- [ ] **Paso 1c (nombres de color de la marca, apuntando a los valores actuales):** dentro del bloque `@theme inline` existente, para que F3 a F6 usen los nombres de `design.md` desde el primer día y F7.2 Paso 1b solo invierta la dirección de los alias y ponga los valores nuevos:

```css
--color-cafe: var(--accent);  --color-cafe-hondo: var(--accent-deep);  --color-cafe-profundo: var(--accent-deep);
--color-tinta: var(--foreground);  --color-tinta-suave: var(--muted);  --color-apagado: var(--muted);
--color-borde: var(--border);  --color-borde-control: var(--border-strong);
--color-arena: var(--background);  --color-blanco: #ffffff;
--color-cafe-bruma: var(--surface);  --color-cafe-claro: var(--surface-deep);
```

  (`--color-blanco` es un hex en `@theme`, no un literal en un componente; `globals.css` no lo cuenta la compuerta.)
- [ ] **Paso 2:** `build` antes y después; `diff` de `.next/static/chunks/*.css` normalizado (sin hashes ni espacios): solo pueden aparecer reglas **nuevas** (`rounded-control`, `rounded-campo`, `rounded-card`, `shadow-n*`, variables `--color-*`); ninguna regla existente cambia de valor. Sin navegador no se compara «estilo calculado»: el `diff` del CSS es la verificación. Cualquier regla existente que cambie se revierte.
- [ ] **Paso 3: commit** `refactor(frontend): forma de controles, nombres de color y tokens aditivos, sin cambio visual`.

### Task 2.2: Retirar los literales de color restantes

**Files:** los archivos con `color-literal` y `paleta-cruda` según `scripts/guardia-estilos.baseline.json` (las cifras exactas salen del baseline; no se citan aquí porque cambian).

- [ ] **Paso 1:** por archivo, reemplazar cada color por su token semántico (`bg-red-400`→`bg-error`, etc.). Los rgba de degradados sobre foto (`sede-hero.tsx`) se convierten en tokens `--scrim-*` en `globals.css`.
- [ ] **Paso 2:** si un literal no tiene equivalente exacto, **no redondear**: crear el token con el valor exacto (Bujack 2022: la desviación casi igual cuesta más que la clara). **Excepción: los grises de estado de Tailwind** (`red-50/200/600/900` y `emerald-*` de `error-block.tsx`, `field-error.tsx` y `toast.tsx`) se mapean a los 6 tokens de estado actuales (`error`, `error-fondo`, `exito`, `exito-fondo`, `aviso`, `aviso-fondo`) aceptando el cambio de matiz, que se documenta en el mensaje del commit (F7 los reemplaza por 2 parejas por estado de `design.md`; crear ~8 tokens exactos que F7 borraría es trabajo perdido). `#25D366` de WhatsApp (`ayuda-flotante.tsx`) no tiene token: se añade a `EXENTOS` de `guardia-estilos.cjs` como `'src/components/ayuda-flotante.tsx': { reglas: ['color-literal'], motivo: 'color de marca de WhatsApp' }`.
- [ ] **Paso 3:** `guardia` (baja), actualizar línea base. **Paso 4: commit** `refactor(frontend): colores literales pasan a tokens`.

### Task 2.3: Una sola fuente para lo que Stripe Elements pide en concreto

> Corrección del crítico: `STRIPE_APARIENCIA` (`stripe-panel.tsx:78-89`) usa `colorPrimary: '#281ab5'`, `borderRadius: '8px'` y otros hex porque la API de Elements no acepta `var()`. Sin esto, la marca nueva dejaría el formulario de tarjeta con la identidad vieja, justo donde se cobra.

**Files:** Create `src/lib/tokens-pago.ts`, `tests/tokens-pago.test.cjs`; Modify `checkout/pago/formulario-pago.tsx`; Modify `tests/run-hub-tests.cjs` (registrar la suite; el módulo es puro y está dentro de `src`).

- [ ] **Paso 1: prueba** (empieza con `/* eslint-disable @typescript-eslint/no-require-imports */`): `tokens-pago.test.cjs` lee `src/app/globals.css`, extrae `--accent`, `--foreground`, `--muted`, `--background` y `--error` y comprueba que `TOKENS_PAGO.colorPrimary`, `colorText`, `colorTextSecondary`, `colorBackground` y `colorDanger` valen lo mismo. **Resolución de variables:** hoy `--accent: var(--indigo)` y `--indigo: #281ab5` (`globals.css:21,41`), y en F7 los valores pasan a `@theme`; la prueba resuelve cadenas `var(--x)` de forma recursiva buscando `--x:` en el bloque `:root {…}` y en `@theme {…}` de `globals.css`, convierte `rem` a px (×16) y falla si una cadena no termina en un hex o en px. Así una marca que cambie un token sin cambiar el otro **falla la prueba**. `RADIO_PAGO` se compara con `--radius-campo` resuelto.
- [ ] **Paso 2:** crear `tokens-pago.ts` exportando `TOKENS_PAGO` con los valores actuales y `RADIO_PAGO = '8px'` (el valor de `--radius-campo` hoy; F7.2 Paso 4 lo sube a `12px`); `formulario-pago.tsx` arma `STRIPE_APARIENCIA` desde ahí.
- [ ] **Paso 3:** `opengraph-image.tsx` queda como excepción documentada en `EXENTOS` (`ImageResponse` no lee CSS); se actualiza a mano en F7.
- [ ] **Paso 4: commit** `refactor(pago): los valores concretos de Stripe Elements salen de una fuente probada contra los tokens`.

### Task 2.4: Token de superficie y tokens de tarjeta, sin cambio visual

> Hallazgo del crítico (ronda 3): hoy `--background` es blanco y `--color-card` apunta a él; 57 usos de `bg-background` mezclan fondos de página con fondos de tarjetas, campos y popovers. El diseño pone la página en **arena** y las superficies en **blanco**. Separarlos hoy, con el mismo color, deja a F7 en «solo valores».

**Files:** Modify `src/app/globals.css` y los componentes que usan `bg-background` (57 sitios).

- [ ] **Paso 1:** en `globals.css` añadir `--superficie: #ffffff` y `--color-superficie: var(--superficie)` (mismo valor que hoy), `--color-card: var(--superficie)`, y los tokens de forma de contenedor con **el valor actual** (las tarjetas hoy no tienen radio): `--radius-card: 0px; --radius-sheet: 0px`.
- [ ] **Paso 2:** recorrer los 57 usos de `bg-background` (`grep -rn "bg-background" src`) y repuntar a `bg-superficie` los que son **contenedores**: tarjetas, campos, popovers, hojas, calendario, resumen, barra inferior. Los de fondo de página o de sección siguen en `bg-background`. Se hace por superficie, en el mismo commit que su migración de F4 si ya la tocó. **Los 77 usos de `bg-surface` se clasifican igual** (la compuerta los cuenta con la regla `bg-surface-uso`, que el trinquete baja): el fondo de página de checkout (la raíz de `PaginaCheckout` usa `bg-surface`) → `bg-background`; banda de sección → se queda en `bg-surface` (será `cafe-bruma` en F7); tarjeta, campo o popover → `bg-superficie`.
- [ ] **Paso 3:** la prueba `tokens-pago` compara `colorBackground` de Stripe con `--superficie` (el formulario vive en una tarjeta), no con `--background`.
- [ ] **Paso 4:** `build` + `guardia`; sin diferencia visual (ambos tokens valen blanco). **Paso 5: commit** `refactor(frontend): token de superficie separado del fondo de página, sin cambio visual`.

---

## F3 — Primitivas con variantes (PFD R1, R5)

### Task 3.0: Subir a `ui/` lo que las primitivas necesitan (evita el ciclo `ui → checkout → ui`)

> Corrección del crítico: `Input` iba a importar `CAJA_CAMPO` de `components/checkout/estilos`, `Field` reutilizaba `ErrorDeCampo` (que usa `Despliegue` de `components/checkout/`) y `BotonPaso` (en `checkout/`) iba a envolver `Button` (en `ui/`): eso es `ui → checkout → ui`. Regla de capas: **`ui/` no importa nada fuera de `ui/`, `lib/` y paquetes** (la compuerta la hace cumplir con la regla `capas-ui`).

- [ ] Mover `CAJA_CAMPO` y `CAJA_CAMPO_ERROR` a `src/components/ui/caja-campo.ts`, `Despliegue` a `ui/despliegue.tsx` y `ErrorDeCampo`/`FieldError`/`propsDeError` a `ui/error-de-campo.tsx`. Los archivos viejos (`checkout/estilos.ts`, `checkout/despliegue.tsx`, `field-error.tsx`) pasan a **reexportar** desde `ui/` para no tocar los llamadores (los reexports son provisionales: F6 los borra y repunta sus importadores a `@/components/ui/…`). Reescribir `CAJA_CAMPO` con `rounded-campo` (Task 2.1).
- [ ] `tsc`, `eslint`, `npm test`, `build`, `guardia`. Commit `refactor(ui): capa base de ui sin dependencias hacia checkout`.

### Task 3.1: Dependencias y `cn`

**Files:** Modify `package.json`; Create `src/components/ui/cn.ts`.

- [ ] `npm install clsx tailwind-merge`.
- [ ] `src/components/ui/cn.ts`:

```ts
import { clsx, type ClassValue } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

// Los tokens propios no son tallas de Tailwind: sin esto twMerge los trata como
// clases sin conflicto y un `className` externo no puede sustituirlos.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      rounded: [{ rounded: ['control', 'campo', 'card', 'sheet', 'casilla'] }],
      'rounded-t': [{ 'rounded-t': ['sheet'] }],
      shadow: [{ shadow: ['n0', 'n1', 'n2'] }],
    },
  },
});

export function cn(...entradas: ClassValue[]) {
  return twMerge(clsx(entradas));
}
```

- [ ] Verificación: `node -e "const {extendTailwindMerge:e}=require('tailwind-merge');const m=e({extend:{classGroups:{rounded:[{rounded:['control','card']}]}}});console.log(m('rounded-control rounded-card'))"` debe imprimir `rounded-card` (sin la extensión, `twMerge` dejaría las dos clases y ganaría la última de la hoja de estilos: un fallo silencioso).
- [ ] Commit `chore(frontend): clsx y tailwind-merge para las primitivas`.

### Task 3.2: Variantes puras y probadas

> Corrección del crítico: el runner (`tests/run-hub-tests.cjs`) compila con `rootDir: src` y emite el JS a un directorio temporal donde Node **no resuelve paquetes** (no hay `NODE_PATH`). Por eso `variantes.ts` no importa nada: son mapas de strings y una función. Las primitivas (`button.tsx`) las combinan con `cn`, que no se prueba aquí.

**Files:** Create `src/components/ui/variantes.ts`, `tests/variantes.test.cjs`; Modify `tests/run-hub-tests.cjs` (añadir la entrada de la suite).

**Interfaces — Produces:** `botonClases({ variante, tamano }): string`; variantes `principal | secundario | texto | acento | peligro`; tamaños `md | sm | icono`.

- [ ] **Paso 1: registrar la suite** en `suites` de `run-hub-tests.cjs`: `variantes: ['src/components/ui/variantes.ts', 'VARIANTES_TEST_OUT']`.
- [ ] **Paso 2: prueba** `tests/variantes.test.cjs` (carga el JS compilado como las demás suites):

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { botonClases } = require(path.join(process.env.VARIANTES_TEST_OUT, 'components/ui/variantes.js'));

test('R5: solo la variante principal usa el color de acción', () => {
  assert.match(botonClases({ variante: 'principal' }), /bg-action/);
  for (const v of ['secundario', 'texto', 'acento', 'peligro']) {
    assert.doesNotMatch(botonClases({ variante: v }), /bg-action/);
  }
});

test('área táctil mínima de 40 px en las acciones de texto', () => {
  assert.match(botonClases({ variante: 'texto' }), /min-h-10/);
});

test('la forma sale de tokens, no de utilidades crudas', () => {
  assert.match(botonClases({ variante: 'principal' }), /rounded-control/);
  assert.doesNotMatch(botonClases({ variante: 'principal' }), /rounded-full/);
});

test('sin colores crudos', () => {
  for (const v of ['principal', 'secundario', 'texto', 'acento', 'peligro']) {
    assert.doesNotMatch(botonClases({ variante: v }), /-(red|green|blue|amber)-\d/);
  }
});
```

- [ ] **Paso 3:** `npm.cmd test -- variantes` → falla. **Paso 4: implementar** `variantes.ts` (sin imports). Copiar **las clases exactas** de `BotonPaso` para `principal` y de `AccionTexto` para `texto`/`acento` (leer los dos archivos), cambiando únicamente `rounded-full` por `rounded-control`:

```ts
// Copiado de BotonPaso (boton-paso.tsx:25): transition-transform, active:scale y disabled:opacity-60.
const BASE =
  'inline-flex items-center justify-center font-medium transition-transform active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60';

const VARIANTES = {
  principal: 'gap-2 rounded-control bg-action px-6 py-2.5 text-sm text-action-foreground', // + resto copiado de BotonPaso
  secundario: 'gap-2 rounded-control border border-border-strong bg-background px-6 py-2.5 text-sm text-foreground hover:bg-surface',
  texto: 'min-h-10 gap-1.5 text-xs text-muted hover:text-foreground', // + resto copiado de AccionTexto
  acento: 'min-h-10 gap-1.5 text-xs text-accent hover:text-foreground',
  peligro: 'gap-2 rounded-control border border-error bg-error-fondo px-6 py-2.5 text-sm text-error',
} as const;

const TAMANOS = { md: '', sm: 'px-4 py-1.5 text-xs', icono: 'size-10 p-0' } as const;

export type VarianteBoton = keyof typeof VARIANTES;
export type TamanoBoton = keyof typeof TAMANOS;

export function botonClases({ variante = 'principal', tamano = 'md' }: { variante?: VarianteBoton; tamano?: TamanoBoton } = {}): string {
  return [BASE, VARIANTES[variante], TAMANOS[tamano]].filter(Boolean).join(' ');
}
```

  Sustituir los comentarios «copiado de» por las clases reales al leer los archivos.
- [ ] **Paso 5:** `npm.cmd test -- variantes` → pasa; `npm.cmd test` completo → pasa. **Paso 6: commit** `feat(ui): variantes de botón puras y probadas`.

### Task 3.3: `Button`, `Input`, `Field`, `Card`, `ChipActividad`, `AvisoEstado`

**Files:** Create `src/components/ui/{button,input,field,card,chip-actividad,aviso-estado}.tsx`.

**Interfaces — Produces:**
- `Button(props: ButtonHTMLAttributes & BotonVariantes & { conFlecha?: boolean; cargando?: boolean })`, siempre `type="button"` salvo que se indique `type="submit"`. `cargando` usa `aria-busy` y `aria-disabled` (no `disabled`, para no perder el foco). Sin `'use client'` ni `motion`: servible desde servidor. En React 19 `ref` es una prop normal (sin `forwardRef`). Con `conFlecha` el icono viene de `@phosphor-icons/react/ssr` (el barril normal usa contexto de cliente); mientras `cargando`, `onClick` se ignora (no hay `disabled`).
- `Input(props: InputHTMLAttributes & { invalido?: boolean })`, con `aria-invalid`.
- `Field({ etiqueta, error, ayuda, children })`: genera el `id` con `useId()` y enlaza error y ayuda con `aria-describedby`; etiqueta, control y `ErrorDeCampo` (reutiliza el existente con `Despliegue`). Es isla cliente. `Card`, `ChipActividad` y `AvisoEstado` también servibles desde servidor.
- `Card({ padding })`: una sola variante base, plana, con borde y sin sombra; `padding` `24` (y `32` desde 1024 px). `ChipActividad({ tipo: 'mar' | 'ciudad' | 'outside' | 'neutro' })` (`neutro` = fondo `cafe-bruma`, texto `tinta-suave`, íconos `Bed`, `Van` o `Package`, para hospedaje, traslados y paquetes sin familia: Task 9.0 Paso 1d) y `AvisoEstado({ tono: 'exito' | 'error' | 'aviso' | 'info' })` son dos componentes distintos que no se mezclan (un chip de actividad nunca comunica estado). Valores visuales finales en la sección «Card y chips» de 7.3.

- [ ] Por componente: escribir, usar `cn` y las variantes; `Input` usa `CAJA_CAMPO`/`CAJA_CAMPO_ERROR` de `ui/caja-campo` (movidos en Task 3.0; **nunca** de `checkout/estilos.ts`, que violaría la capa `ui`). `Card` usa `bg-superficie` y `rounded-card`; `ChipActividad` lleva fondo `*-claro`, texto del tono oscuro y siempre icono (`Waves`, `Buildings`, `Mountains`); `AvisoEstado` lleva icono `CheckCircle`, `WarningCircle`, `Warning` o `Info`. Una `Card` no contiene otra `Card`: los subgrupos se separan con espacio, no con otro borde.
- [ ] `Button` tiene **`type="button"` por defecto**. Antes de migrar un `<button>` hay que mirar si está dentro de un `<form>` sin `type`: ese hoy **envía** el formulario (p. ej. Enter en `campos-contacto`). Ese caso se migra con `type="submit"` explícito. Listar con `grep -rn "<button" src --include=*.tsx` y revisar los que estén dentro de `<form`.
- Probar en **una sola pantalla**: sustituir los botones de `cookie-notice.tsx` (aceptar → `principal`, rechazar → `secundario`; superficie pública sin dinero) por `Button`. Los disparadores de acordeón de ancho completo de `faq-section.tsx` (`faq-section.tsx:54-65`) no encajan en ninguna de las 5 variantes: se migran en F4 con una variante `fila`. Verificar con `tsc`, `eslint`, `build`, `guardia` (baja).
- [ ] PUNTO DEL DUEÑO: mirar el aviso de cookies (debe verse igual).
- [ ] Commit por componente.

### Task 3.4: Absorber lo ya existente

- [ ] `BotonPaso` pasa a ser un envoltorio de `Button variante="principal"`; `AccionTexto` y `EtiquetaModificar` usan `botonClases({ variante: 'texto' | 'acento' })`. Los nombres se conservan para no tocar los llamadores. Commit `refactor(checkout): BotonPaso y AccionTexto sobre la primitiva Button`.

### Task 3.5: `Sheet` y `AlertDialog` accesibles

> La hoja («Ver resumen») la usa la Task 8.4a; la confirmación destructiva («Cancelar y liberar mi lugar») la usan las Tasks 8.0 (Atrás con orden creada) y 8.4c y el diálogo de cancelar de `continuar-reservacion`. La skill `shadcn` pide `AlertDialog` (no `Dialog`) para confirmación destructiva y prohíbe el `div` crudo donde existe primitiva. Se construyen una vez, aquí, no tres veces sueltas.

**Files:** Create `src/components/ui/{sheet,alert-dialog}.tsx`.

- [ ] Sobre `<dialog>` nativo con `showModal()` (o Radix/Vaul si se justifica con el analizador): trampa de foco, `aria-modal`, Esc, bloqueo de scroll, fondo inerte, foco que regresa al disparador. Estilos con tokens (`--radius-sheet`, `--shadow-n2` desde F7). Cargar `design-taste-frontend` antes de diseñar su forma. Variantes puras en `variantes.ts` con su prueba.
- [ ] **`Sheet` (< 640 px):** `fixed inset-x-0 bottom-0 max-h-[85dvh] overflow-y-auto overscroll-contain bg-superficie rounded-t-sheet shadow-n2 px-4 pt-3 pb-[max(16px,env(safe-area-inset-bottom))]`. Asa visual de 4 × 40 (`bg-borde-control`, centrada, `mb-3`; no es el área de arrastre). Cabecera con título `texto-subtitulo` y botón «Cerrar» de 48 × 48 a la derecha. Fondo atenuado con el token `--scrim-hoja` (tinta al 40 %). Entra con `translateY(100%) → 0` en 400 ms con `curva-estandar`; sale con `curva-salida` en 250 ms; con reducir movimiento solo opacidad, 150 ms. Para animar `<dialog>` usar `@starting-style` y `transition-behavior: allow-discrete`. El `ResumenPedido` dentro de la hoja usa una variante `sinBorde` (no hay tarjeta dentro de la hoja). Se cierra con Esc, tocando fuera o con «Cerrar». `--radius-sheet` vale 0 hasta F7 (que lo pone en 24 px).
- [ ] **`AlertDialog`:** centrado, `w-[min(92vw,420px)] rounded-card bg-superficie p-6 shadow-n2`, título `texto-subtitulo`, cuerpo `texto-cuerpo`. Botones apilados a ancho completo por debajo de 640 px y en fila a la derecha desde ahí. La acción segura va primero en el DOM («Seguir con mi reserva», `secundario`) y recibe el foco inicial; la destructiva usa `peligro` con la etiqueta del resultado («Cancelar y liberar mi lugar»). Nunca hay dos botones `principal`.
- [ ] `Sheet` y `AlertDialog` no tienen consumidor antes de 8.4 ni 8.0 (excepto el diálogo de `continuar-reservacion`, F4 grupo 1): la verificación es la ruta temporal `src/app/[lang]/prueba-ui/page.tsx` (no se commitea) y el PUNTO DEL DUEÑO de 8.4a. Commit `feat(ui): Sheet y AlertDialog accesibles`.

### Task 3.6: `Checkbox` y opción de radio

> `design-components.md` los define y el checkout hoy los arma a mano. El interruptor (52 × 32) también está definido, pero no tiene consumidor (no hay `role="switch"` en el repo): **no se crea `interruptor.tsx` hasta que exista un uso.**

**Files:** Create `src/components/ui/{checkbox,opcion}.tsx`.

- [ ] Casilla de 24 con área táctil de 48 y radio `rounded-casilla` (6 px); opción de radio de 24; etiqueta clicable a la derecha en ambas; foco con el anillo de `ring`. Islas cliente con `useId()`. Sustituir las casillas y radios hechos a mano en F4 grupo 4 (`checkout-view.tsx:1290`, `grupo-servicio.tsx:95,294`, `stripe-panel.tsx:454,477,561` —ya en `checkout/pago/*` tras 1.2a— y `traslado-view.tsx:901`). Commit `feat(ui): casilla y opción de radio`.

### Task 3.7: `EmpresaSello` — quién es quién (una sola pieza)

> `colaboradores-section.tsx` ya ramifica `marca.logo ? <Image h-20 w-52> : <h3 text-2xl>`: una fila con logo y otra con texto. En `public/logos` solo hay logos de Sal y Sol, y `design-components.md` pide «un renglón por empresa» en el checkout sin definir cómo se ve la empresa. Sin una pieza común, cada sitio improvisa la suya. Vive en F3 (no en F9) porque el checkout de F8 (renglón de cargo, tarjeta de personalizaciones de cada empresa, cabecera mínima) y la marca provisional de la cabecera ya la usan.

**Files:** Create `src/components/ui/empresa-sello.tsx` (Server Component, sin `'use client'`), `src/lib/iniciales.ts`, `tests/iniciales.test.cjs` (registrar la suite `iniciales` en `run-hub-tests.cjs`).

- [ ] **Paso 1: prueba primero** `tests/iniciales.test.cjs`: `iniciales(nombre)` («Sal y Sol Sportfishing»→«SS», «DLS Transporte»→«DT», «La Ventana Travel»→«LV», «Piratas Adventures»→«PA», «Sun Baja Experience»→«SB»; una sola palabra→una inicial; vacío→«»). Módulo puro sin imports.
- [ ] **Paso 2:** props `{ nombre: string; logo?: string | null; tamano: 24 | 32 | 64; mostrarNombre?: boolean }`. Círculo (`rounded-full`, eco del logo redondo). **Con logo:** fondo `blanco`, borde 1 px `borde`, imagen `object-contain` con padding de 12 %, `alt=""` si `mostrarNombre` (el nombre ya está en texto) o `alt={nombre}` si no. **Sin logo:** monograma de 1 a 2 iniciales en fondo `cafe-bruma`, texto `cafe-profundo` (12,80:1), fuente de titulares en 700 (`font-display`; F7 la lleva a Consola Mono), letra al 40 % del círculo en 32 y 64 px; **a 24 px solo la inicial, en `texto-pie` (12 px)**, porque el 40 % del círculo (9,6 px) queda bajo el mínimo de 12 px; sin ilustración ni SVG dibujado a mano. El sello es decorativo: la identidad es el nombre en texto, siempre visible (14/600 con el sello de 24; 24/700 mono con el de 64). **Prohibido asignar un color por empresa:** azul, coral y verde son de actividad.
- [ ] **Marca provisional de Sun Baja Experience (decisión del dueño, 2026-10-16):** mientras no llegue el logo definitivo, la marca del sitio es `<EmpresaSello nombre="Sun Baja Experience" tamano={32} />`, es decir el monograma «SB» en círculo de 32 px (fondo `cafe-bruma`, texto `cafe-profundo`, Consola Mono 700), igual en la cabecera y el pie. No hay wordmark de texto. Cuando llegue el logo (SVG) se pasa como `logo` y el resto no cambia.
- [ ] **Paso 3:** se reutiliza en: tarjeta de servicio (24), fila de empresa (64), pie de galería y de opinión (24), renglón de cargo del checkout (32), tarjeta de personalizaciones de cada empresa en cruza-empresa (24) y las marcas de cabecera y pie. El logo llega por prop desde la página (servidor) leyendo `empresas.ts` a partir de F9; antes de F9 solo Sal y Sol tiene logo (`public/logos`) y las demás muestran monograma. `tsc`, `eslint`, `npm test`, `build`, `guardia`. Commit `feat(ui): sello de empresa con logo o monograma`.

---

## F4 — Migrar los 81 controles (uno por superficie, aspecto idéntico)

Recuento medido (66 `<button` + 15 `<input|select|textarea>` = 81; los que viven en archivos que F9 borra o que F8 reemplaza, como `reviews-carousel`, `paquete-card` y `checkout-calendar`, no se migran): continuar-reservacion 7, grupo-servicio 4, fecha-paquete 4, hub-mapa-sedes 4, stripe-panel 3, date-field 3, checkout-view 3, y 21 archivos con 1 o 2. Controles de formulario (`<input|select|textarea>`): stripe-panel 4, grupo-servicio 4, traslado-view 2, checkout-view 2, field-popover 1, select-personalizado 1, campos-contacto 1.

**Regla de migración (aplica a todas las tareas):** una superficie por commit; el JSX resultante genera las mismas clases (comparar el HTML renderizado en el `build` no basta: se compara el diff de clases a mano); si una variante no existe, **se añade la variante** a `variantes.ts` con su prueba, no se deja un `<button>` crudo.

Orden por riesgo creciente (PUNTO DEL DUEÑO al cerrar cada grupo):
1. **Públicas sin dinero:** `faq-section` (sus disparadores de acordeón usan una variante nueva `fila`, con su prueba), `cookie-notice` (ya migrada como piloto de la Task 3.3), `lang-switch`, `site-header`, `sede-selector`, `hub-mapa-sedes`, `selector-experiencia`, `continuar-reservacion` (su diálogo de cancelar, hecho a mano con `fixed inset-0 z-[70]` y `role="dialog"`, pasa a `AlertDialog` de la Task 3.5: duplica la primitiva y choca con `--z-toast: 70`). No se migran `reviews-carousel` ni `paquete-card`: F9 los borra (Tasks 9.5 y 9.1b).
2. **Campos y selectores compartidos:** `field-popover`, `date-field`, `time-field`, `people-stepper`, `select-personalizado`, `toast`. **No se migra** `checkout-calendar` (ni la tira semanal que usa): F8 los reemplaza por el calendario completo. `BookingBar`, `StickyBookingBar` y el `Hero` viejo ya se eliminaron.
3. **Checkout, tarjetas auxiliares:** `checkout-section-card`, `campos-contacto`, `tipo-traslado-cards`, `ayuda-flotante`, `reserva-plegable`, `aviso-fallo`.
4. **Checkout, núcleo:** `grupo-servicio`, `fecha-paquete`, `checkout-view`, `traslado-view`, los archivos de `checkout/pago/` (antes `stripe-panel`), `booking-confirmation`. **Se hace DESPUÉS de F5**, ya dentro de `checkout/bloques/*` (corrección del crítico: migrar y luego partir las mismas ~1 700 líneas es trabajo doble con revisión del dueño en cada pasada). Con revisión del dueño del flujo completo.

Cada tarea: sustituir, correr la puerta de siempre, `guardia` debe **bajar**, actualizar la línea base, commit `refactor(<superficie>): controles sobre las primitivas`. Al terminar el grupo 4 (después de F5), `boton-crudo` e `input-crudo` quedan en 0 y el script las hace fallar con cualquier valor > 0.

---

## F5 — Partir las vistas y unificar héroes (PFD R1, R4)

> Es refactor puro: ningún texto, flujo ni estilo cambia. Cada extracción es un commit; entre extracciones corre la lista automática (`tsc`, `eslint`, `npm test`, `build`, `guardia`) y el dueño confirma **al cerrar cada Task** (5.1, 5.2, 5.3), no en cada extracción.

### Recorridos manuales obligatorios (al cerrar cada Task de F5 y el grupo 4 de F4)

> Corrección del crítico: `tsc`, `eslint`, `build`, `guardia` y las suites de `lib/` no ejercitan componentes. Estos casos pueden romperse sin que nada los detecte, así que **cada Task de F5 (5.1, 5.2, 5.3) y el grupo 4 de F4 pasan por esta lista al cerrarse**, y el dueño confirma:
>
> 1. Servicio suelto: elegir, datos, pagar con tarjeta de prueba.
> 2. Paquete de una empresa: igual.
> 3. Paquete cruza-empresa: pago 1 retenido y **rechazo en el pago 2** (aviso de retención), luego reintento.
> 4. Traslados: todos los pasos (4 antes de F8, 3 después), incluida la fecha de regreso.
> 5. **Recargar a media compra** (reanudación por `sessionStorage`: `checkoutId`/`ordenId`) y cambiar de idioma.
> 6. **Enter** dentro de un formulario (no debe enviar ni dejar de enviar donde antes lo hacía).
> 7. El token de Turnstile sobrevive al plegar y reabrir la tarjeta, y se renueva tras un rechazo (`captchaKey`).
> 8. Plegar una tarjeta no desmonta estado que el pago necesita (un paso extraído **no** puede perder el estado al desmontarse).
> 9. Teclado: orden de foco, `aria-*` y `disabled` iguales que antes.

### Task 5.1: Partir `checkout-view.tsx` (1 703 líneas, 36 `useState`)

**Files:** Create `src/components/checkout/bloques/{bloque-viaje,bloque-extras,bloque-contacto,bloque-recogida,bloque-pago}.tsx`; Modify `checkout-view.tsx`.

- [ ] **Paso 1:** leer el archivo completo y listar por paso el estado que posee y el que comparte. Dibujar el mapa de estado en el commit.
- [ ] **Paso 2:** el estado compartido sube a un *reducer* (el patrón ya existe en `lib/pedido-estado.ts` + `use-pedido-estado.ts` para paquetes); el estado local de un paso baja a su componente. **Reparto del estado (evita re-renderizar todo en cada tecla):** el texto de los campos es **local al bloque** y se confirma al reducer en `blur` o al avanzar; el contexto de *state* y el de *dispatch* van separados (o selectores con `useSyncExternalStore`); los bloques van con `memo`; antes de partir, evaluar `reactCompiler: true` (`reactCompiler.md` en 16.3; hoy hay 19 `useMemo/useCallback` y 15 `useEffect` en los tres archivos). Reglas `rerender-defer-reads`, `rerender-memo`, `rerender-derived-state-no-effect` y `rerender-no-inline-components`. Esto es un cambio de arquitectura del estado de cobro, no un «refactor puro»: pasa por la lista de recorridos manuales en cada commit.
- [ ] **Paso 3:** extraer un **bloque** por commit en este orden: pago, extras (hoy «detalles»), contacto, recogida (solo traslados), viaje; los 4 pasos actuales quedan como composición fina de bloques. Así F8 solo reagrupa los bloques en tres pasos, sin volver a partir las vistas. Tras cada extracción: `tsc`, `eslint`, `npm test`, `build`, `guardia`.
- [ ] **Paso 4:** PUNTO DEL DUEÑO al cerrar la Task, con la lista de recorridos manuales (servicio suelto completo hasta el pago de prueba, rechazo, recarga a media compra); no tras cada extracción.

### Task 5.2: Partir `traslado-view.tsx` (1 006 líneas, 32 `useState`)

- [ ] Mismo procedimiento. Reutiliza `PaginaCheckout`, `ContenidoViaje` y los pasos ya compartidos; el objetivo es que los bloques de traslados (viaje, contacto, recogida, pago) sean componentes de `checkout/bloques/`.

### Task 5.3: Partir `pedido-paquete.tsx` (894 líneas) y `GrupoServicio`

> La ruta de paquete no puede quedarse sin el trabajo previo que sí tienen servicio suelto y traslados: F8 (Task 8.1) solo reagrupa bloques, no parte componentes.

- [ ] Ya usa hooks y reducer; extraer los bloques de JSX grandes en componentes. Del `grupo-servicio.tsx` existente, extraer dos mitades: `pedido/grupo-viaje.tsx` (personas, extras, tipo de traslado, fecha) y `pedido/grupo-datos.tsx` (recogida, zona). Cada extracción es un commit con los recorridos de F5. **Criterio de cierre:** `pedido-paquete.tsx` ≤ 600 líneas.

### Task 5.4: Un solo héroe y una sola sección

**Files:** Create `src/components/ui/hero-media.tsx`, `section-shell.tsx`; Modify `sede-hero.tsx` y las secciones season/included/gallery (`about-section.tsx` y `hub-por-que.tsx` no se migran: se borran en F9; `reviews-section.tsx`, `reviews-carousel.tsx` y `colaboradores-section.tsx` tampoco: F9 los reemplaza o reescribe); Delete `src/components/hub-hero.tsx` y `src/components/license-section.tsx` (sin importadores: `grep -rn "hub-hero\|license-section" src` = 0).

- [ ] `HeroMedia({ imagen, video, alt, preload })` es un **Server Component**: `<Image preload>` + degradado, más la isla cliente `ui/video-diferido.tsx` de la Task 1.5 (el patrón completo vive allí). El héroe de la sede lo usa; el del hub lo usa en la Task 9.3 (video con poster inmediato). **F5 no cambia valores:** `HeroMedia` y `SectionShell` se escriben con las clases actuales (`sede-hero.tsx:73-74`: `min-h-[calc(52svh+nav)]` y `lg:min-h-[calc(min(56svh,520px)+nav)]`; secciones `py-24 lg:py-32` y `max-w-6xl px-6 sm:px-8 lg:px-12`). Imagen `fill object-cover` con `objectPosition` configurable por sede; scrim como token `--scrim-hero` (con los degradados actuales); el video entra con la misma imagen como `poster`; con reducir movimiento solo imagen. Los valores nuevos (alto `70dvh`/`80dvh`, pila de 4 elementos, fundido de 400 ms, `py-12 sm:py-16 lg:py-24`, ancho 1120) entran en 7.3, punto «Héroe y secciones».
- [ ] `SectionShell({ fondo: 'papel' | 'bruma' | 'bruma-profunda', titulo, regla })` encapsula el ritmo de secciones (la «paleta v3» solo admite esos tres fondos hasta F7, que los renombra a `arena | blanco | cafe-bruma`; ver 7.3). Lleva `scroll-mt-[calc(var(--nav-alto)+16px)]` y `aria-labelledby` apuntando a su `<h2>` (sin eso las anclas no anuncian nada).
- [ ] Un héroe por commit; PUNTO DEL DUEÑO al terminar (sede, servicio; el héroe del hub se revisa en 9.3). F5.4 solo unifica los contenedores: **qué secciones lleva cada página, en qué orden y con qué texto se decide en F9.**

### Task 5.5: Diccionario por sección en los clientes (V3, ahorro modesto)

> Movida desde F1 por el crítico: con la vista aún entera, `dict` se pasa a sub-componentes (`checkout-view.tsx:1188` y `:1398`; `AvisoCargos`, `EncabezadoPago`, `PorQueVariosPagos` en `pedido-paquete.tsx`), y recortar el tipo se vuelve una cascada de ~10 archivos para ~20 KB. Después de F5, cada paso recibe props mínimas y el recorte es natural.

- [ ] Para cada paso extraído, tipar `dict` con `Pick<Dictionary, 'checkout' | …>` según lo que use; que `tsc` dé la lista. Medir con `scripts/medir-peso.cjs`; si el ahorro es < 10 KB, descartar la tarea y anotarlo. Commit `perf(checkout): cada paso recibe solo las secciones del diccionario que usa`.

---

## F6 — Cerrar la base

- [ ] `guardia`: `boton-crudo`, `input-crudo`, `img-cruda`, `paleta-cruda`, `capas-ui` y `motion-completo` en **0 salvo los exentos por regla listados con motivo** en `EXENTOS` (`opengraph-image.tsx`, `lang-switch.tsx` y `tokens-pago.ts`, los tres solo de `color-literal`; más `ayuda-flotante.tsx` si la Task 2.2 lo añadió, también solo de `color-literal`); umbral duro. Cualquier exento nuevo exige un motivo escrito en el código. `checkout-calendar.tsx` no es exento: lo borra la Task 8.5c, después de F6, y hasta entonces su `boton-crudo` y su `radio-crudo` siguen vivos; por eso el umbral de F6 para `boton-crudo` y `radio-crudo` es «0 salvo `checkout-calendar.tsx`» (la entrada se pone en `EXENTOS` solo de esas dos reglas con el motivo «se borra en Task 8.5c», y 8.5c la quita al borrar el archivo).
- [ ] Borrar los reexports provisionales de `checkout/estilos.ts`, `checkout/despliegue.tsx` y `field-error.tsx` (Task 3.0) y repuntar sus importadores a `@/components/ui/…`.
- [ ] Script `"verificar": "tsc --noEmit && eslint src tests && npm test && npm run test:guardia && npm run guardia && next build"` en `package.json` (la Task 9.0 le añade `test:contenido` cuando existe la prueba de paridad de diccionarios).
- [ ] Actualizar `frontend/CLAUDE.md`: dónde viven los tokens y las primitivas, la regla «nada crudo», cómo añadir una variante y cómo correr `verificar`.
- [ ] Línea base final de carga en el archivo de F0 (medida con `scripts/medir-peso.cjs`, igual que la inicial). Commit `docs(frontend): base cerrada`.

---

## F7 — Marca nueva: valores y una pasada de componentes (PFD R4)

**Entradas ya entregadas:** `docs/design/design.md` y las decisiones del dueño del 2026-10-15: botón principal café con texto blanco; titulares en Consola Mono (solo 700; Book no se incorpora); cuerpo en la pila del sistema (San Francisco en Apple); radio 12 px en controles y 16 px en tarjetas; página **arena** `#FBF7F0` con tarjetas, campos y calendario **blancos**; sin negro puro; categorías azul = mar, coral = ciudad, verde = outside o montaña; **sin la palabra caligráfica** de los titulares. **Falta del dueño:** logo y fotos definitivos.

### Task 7.1: Preparar la fuente Consola Mono

**Files:** Create `src/app/fonts/ConsolaMono-Bold.woff2`, `OFL.txt`, `FONTLOG.txt`; Modify `src/app/fonts/LICENCIAS.md`. **Book no se incorpora:** todos los titulares son 700 (`design.md:98-101`).

- [ ] **Paso 1:** descargar el zip de `https://www.dafont.com/es/consola-mono.font` (autor Wojciech Kalinowski, SIL Open Font License 1.1, sin nombre reservado declarado) en una carpeta **nueva y vacía**; los archivos descargados se tratan como no confiables: no se ejecuta nada de ellos.
- [ ] **Paso 2:** recortar a latín con acentos, puntuación, moneda y símbolos de la interfaz y convertir a WOFF2 (requiere `fonttools` y `brotli`, ya instalados; `pyftsubset` no está en el PATH de esta máquina, pero `python -m fontTools.subset` sí funciona):

```bash
python -m fontTools.subset ConsolaMono-Bold.ttf --unicodes="U+0020-007E,U+00A0-00FF,U+0100-017F,U+2010-2027,U+20AC,U+2190-2193,U+00D7" --flavor=woff2 --layout-features='*' --output-file=ConsolaMono-Bold.woff2
```

  Objetivo: ≤ 40 KB. Comprobar á é í ó ú ñ ü ¿ ¡ y `$4,100`.
- [ ] **Paso 3:** copiar `SIL - Open Font License.txt` como `OFL.txt` y `FONTLOG.txt` junto a los `.woff2` (la OFL exige que la licencia acompañe a la fuente) y anotar fuente, autor y licencia en `LICENCIAS.md`.
- [ ] **Paso 4: commit** `chore(fonts): Consola Mono recortada y con su licencia`.

### Task 7.2: Valores de la marca (tokens, fuentes, variantes)

**Files:** Modify `src/app/globals.css`, `src/app/[lang]/layout.tsx`, `src/lib/tokens-pago.ts`, `src/components/ui/variantes.ts`, `src/app/[lang]/opengraph-image.tsx`, `src/components/checkout/pago/formulario-pago.tsx` y `pago/tarjeta-como-pagas.tsx` (tras 1.2a), `src/app/[lang]/not-found.tsx`, `src/components/sede-hero.tsx`.

- [ ] **Paso 1: colores** (valores de `design.md`): `--accent`/`--action` → café `#7C3B02` (texto sobre acción `#FFFFFF`, 8,46:1); `--foreground` → `#1F1A14`; **`--background` → arena `#FBF7F0`** (las superficies ya son blancas por F2.4); bordes `#D9C9B4` (decorativo) y `#8A7A66` (controles, 4,15:1); estados con sus parejas; familias `azul`, `coral`, `verde` con `hondo`, `profundo`, `medio`, `claro` y `bruma`; **`--ring` → `azul` `#1B607F`** (foco). Comprobar el contraste de cada par antes del commit. `--amber`, `--indigo` y `--yellow` salen; `--hero-ink` se queda.
- [ ] **Paso 1b: nombres de token** — los nombres `cafe`, `cafe-hondo`, `cafe-profundo`, `cafe-claro`, `cafe-bruma`, `tinta`, `tinta-suave`, `apagado`, `borde`, `borde-control`, `arena` y `blanco` ya existen desde F2 (Task 2.1, Paso 1c) apuntando a los valores actuales, y las familias `azul|coral|verde`, `coral-texto`, `info` e `info-fondo` también (Paso 1b de F2). Aquí se **invierte la dirección de los alias** para no crear ciclos (en F2 era `--color-cafe: var(--accent)`; ahora el nombre de marca lleva el valor hex de `design.md` y el nombre antiguo lo referencia: `--accent: var(--color-cafe)`) y se declaran los que faltan de la lista cerrada de `design.md`: `cafe-medio`; estados `exito`, `exito-fondo`, `error`, `error-fondo`, `aviso`, `aviso-fondo` (= `cafe-claro`), `info` (#0F3D52), `info-fondo` (= `azul-claro`); `coral-texto` (#8F2409); `ring` (= `azul`). Los nombres antiguos pasan a ser alias de los de marca: `--accent` y `--action` → `cafe`; `--foreground` → `tinta`; `--muted` → `apagado`; `--border` → `borde`; `--border-strong` → `borde-control`; **`--surface` → `cafe-bruma`** (`design.md:207`: `--surface`, `--surface-deep` → `cafe-bruma`, `cafe-claro`; `superficie` es el blanco de tarjetas y campos y ya se separó en la Task 2.4). **Antes de repuntar `--surface` y `--surface-deep`**, listar sus usos (cifras según el baseline: los 77 usos de `bg-surface` ya están clasificados por la Task 2.4 y la regla `bg-surface-uso`) y migrar cada uno a un token con nombre explícito: `surface-deep` **nunca** apunta a `cafe-claro` (#FEE0AC, amarillo saturado); sus usos pasan a `cafe-bruma`, salvo el rango de fechas confirmado y los avisos, que usan `cafe-claro`. La regla `surface-deep` de la compuerta debe quedar en 0, y `bg-surface-uso` solo cuenta bandas de sección.
- [ ] **Paso 2: forma** — `--radius-control: 12px`, `--radius-campo: 12px`, `--radius-card: 16px`, `--radius-sheet: 24px` (las tarjetas ya usan `rounded-card` desde F3/F4); chips y días del calendario en `9999px`. Además declarar `--radius-xs: 4px; --radius-sm: 8px; --radius-full: 9999px` (`--radius-casilla: 6px` ya existe desde F2) y **sobrescribir** `--radius-md: 8px; --radius-lg: 12px; --radius-xl: 16px; --radius-2xl: 16px` para que cualquier `rounded-*` heredado caiga en la escala de `design.md` (22 `rounded-lg`, 20 `rounded-xl`, 10 `rounded-2xl`, 2 `rounded-md` hoy). En contenedores anidados el radio interior es el exterior menos su padding. La regla `radio-crudo` de la compuerta (`/\brounded(?:-[trblse]{1,2})?-(?:md|lg|xl|2xl|3xl)\b/g`, que ya ve `rounded-t-xl`) solo admite `rounded-control|campo|card|sheet|full|xs|sm|casilla` y debe quedar en 0 al cerrar 7.3, donde se reemplazan los 56 usos. Esta sobrescritura de `--radius-md…2xl` es solo red de seguridad.
- [ ] **Paso 2b: movimiento** — (los tokens aditivos ya se declararon en F2, Paso 3b; aquí se confirman sus valores y se migra todo a ellos) `--duracion-corta: 150ms; --duracion-media: 250ms; --duracion-larga: 400ms; --curva-estandar: cubic-bezier(0.2,0,0,1); --curva-salida: cubic-bezier(0.4,0,1,1)`, y las capas `--capa-hover: color-mix(in srgb, var(--color-tinta) 8%, transparent)` y `--capa-pulsado: … 12% …` (hover solo con puntero: Tailwind 4 ya lo condiciona a `@media (hover:hover)`). Migrar `Despliegue`, `Skeleton`, las hojas, el cambio de paso y el calendario a esos tokens. `.rev`, `.rev-foto`, `.rev-regla` y `.titulo-entra` quedan **solo** en el título del héroe de la sede (regla 7 de F9), nunca en `/reservar`, `/traslados`, precios ni políticas. Reemplazar el bloque global de `prefers-reduced-motion` (hoy pone `0.01ms` y mata también los fundidos) por: sin `transform`, `clip-path` ni cambio de altura, solo opacidad con `animation-duration: 150ms`. Con `m.*`, `transition={{ duration: 0.25, ease: [0.2, 0, 0, 1] }}` y ramificar con `useReducedMotion()`. **Lo que no se anima:** el formulario de tarjeta de Stripe y su esqueleto, los montos y totales (cambian con fundido de 150 ms, sin conteo ascendente; `CifraAnimada` solo la usa `checkout-stepper.tsx`, que la Task 8.3 borra, así que no queda conteo que retirar), el calendario durante el scroll vertical y el contenido de las pantallas de pago.
- [ ] **Paso 3: fuentes — lista cerrada de lo que se toca** (hallazgo del crítico):
  - `layout.tsx`: quitar `Instrument_Sans`, Bebas Neue y Bella Fashion; añadir `localFont` con el `.woff2` Bold de Consola Mono (`display: 'swap'`, `variable: '--font-titulo'`, peso 700, `fallback` = la pila monoespaciada de `design.md`). Solo el archivo Bold (peso 700): Book no se incorpora. Un fallback monoespaciado de sistema no iguala las métricas de Consola Mono: revisar `adjustFontFallback` y medir el CLS.
  - `globals.css` `@theme inline` (líneas ~110-112): borrar `--font-sans: var(--font-cuerpo)` y `--font-script: var(--font-acento)`; declarar `--font-sans` con **la pila literal** (`-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`) y `--font-display: var(--font-titulo)`.
  - `globals.css` `body` (línea ~300): `font-family: var(--font-sans)` (ya no `--font-cuerpo`).
  - `globals.css` regla `h1, h2` (líneas ~318-324): peso 700, tracking de `design.md` (`--tracking-titulo: -0.02em`), sin el fallback Oswald/Arial Narrow; se conserva `font-synthesis: none` porque Bold es real. **Provisional: la regla global y `--tracking-titulo` se mantienen hasta la Task 7.3, que los borra solo después de asignar clase a cada `<h1>`/`<h2>` (regla `titular-sin-escala`).**
  - `globals.css` `.acento` (líneas ~265-280): **se elimina**, y en `sede-hero.tsx` (líneas ~79-80) el titular se pinta como texto plano (`start + emphasis + end`, sin estilo especial; el contrato de `sedes-tipos.ts` no cambia).
  - `not-found.tsx` (líneas ~25-37): quitar `font-normal`; su titular usa `texto-pagina` (Task 7.3). Además, migrar los 4 `var(--…)` crudos (`var(--indigo)`, `var(--ink)`, `var(--action)` y `var(--border-strong)`, líneas ~29, 50 y 58) a clases (`text-accent`, `bg-action`…), porque este paso borra `--indigo`, `--yellow` y `--amber` y la compuerta no detecta variables colgantes. Criterio de cierre de 7.2: `grep -rnE "var\(--(indigo|yellow|amber|ink|paper|mist|line)" src` = 0.
  - `checkout/pago/formulario-pago.tsx` (donde viven ahora `STRIPE_APARIENCIA` y `STRIPE_FUENTES`, tras 1.2a) carga Instrument Sans por Google Fonts para Stripe Elements: quitar `STRIPE_FUENTES` y poner `fontFamily` = la pila de `--font-sans` en `TOKENS_PAGO` (`lib/tokens-pago.ts`; la prueba de `tokens-pago` lo compara con `--font-sans`). `checkout/pago/tarjeta-como-pagas.tsx` no carga fuentes.
- [ ] **Paso 4: Stripe y OG** — `TOKENS_PAGO` con los hex nuevos (comparados con `globals.css` por su prueba), `RADIO_PAGO = '12px'` junto con `--radius-campo: 12px`, y `fontFamily` = la pila de `--font-sans`. `opengraph-image.tsx` a mano: **rediseñar el contenido del OG con la marca nueva, sin emoji** (hoy lleva el emoji 🐟 y un degradado verde azulado; no es solo cambiar colores).
- [ ] **Paso 5: variantes** — `variantes.ts`: `principal` café con texto blanco; `secundario` con borde `borde-control` y texto café; `peligro` con `error`. **Contrato visual de `Button`** (este es el paso donde la geometría de F3 cambia a propósito; al final del paso: `grep -rn "variante: 'acento'\|variante=\"acento\"\|tamano.*sm" src`, migrar `acento`→`texto` y `sm`→`md` y quitar `acento` de las listas de `tests/variantes.test.cjs`; la variante `acento` no es la clase `.acento` de `globals.css`; la prueba de `variantes` se actualiza línea por línea y conserva R5: solo `principal` usa el color de acción). Base común: `inline-flex items-center justify-center gap-2 rounded-control px-6 texto-etiqueta min-h-12 sm:min-h-11 transition-[background-color,transform] duration-150 ease-[var(--curva-estandar)] active:scale-[0.98] motion-reduce:active:scale-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed aria-disabled:cursor-not-allowed`; **no se usa `opacity` para deshabilitar**. `principal`: `bg-cafe text-white hover:bg-cafe-hondo active:bg-cafe-profundo`; deshabilitado y `aria-disabled`: `bg-cafe-bruma text-apagado`. `secundario`: `bg-superficie text-cafe border border-borde-control hover:bg-cafe-bruma active:bg-cafe-claro`; deshabilitado `bg-cafe-bruma text-apagado border-transparent`. `texto`: `bg-transparent text-cafe min-h-11 px-3 hover:bg-cafe-bruma` (se elimina `acento`, queda idéntico; las acciones meta como «Volver» usan `tono="neutro"` con `text-tinta-suave` e icono de 16). `peligro`: `bg-error text-white hover:bg-[color-mix(in_srgb,var(--color-error)_92%,var(--color-tinta))]`. Tamaños: `md` es el de la base; se elimina `sm`; `icono` es `size-12 rounded-full p-0` con icono de 24 (48 × 48 también en escritorio); prop `bloque` agrega `w-full` (barra inferior móvil). **Etiquetas largas:** hasta 2 renglones por debajo de 640 px (`h-auto py-3 text-balance`), nunca se truncan (el monto debe verse); verificar con «Pagar $12,450.00 MXN a Yellowtail Sportfishing» en 360 px, en es y en en. **`cargando`:** `CircleNotch` de 20 con `animate-spin` y «Procesando…», conserva su ancho, sigue en `aria-disabled` con la razón visible abajo; con reducir movimiento el icono pulsa en opacidad (1,2 s) en lugar de girar. El foco es el anillo de 2 px `ring` con 2 px de desfase en todas las variantes, desfase pintado con el color de la superficie que lo contiene.
- [ ] **Paso 5b: campos** — `CAJA_CAMPO = 'min-h-12 sm:min-h-11 rounded-campo border border-borde-control bg-superficie px-4 text-base text-tinta placeholder:text-apagado focus-within:border-2 focus-within:border-ring disabled:bg-cafe-bruma disabled:text-apagado'`; `CAJA_CAMPO_ERROR` pone `border-error` también de 2 px y no cambia el relleno. El borde decorativo `borde` (1,62:1) no delimita un control. Todo `input`, `select` y `textarea` usa `text-base` como mínimo (16 px, evita el zoom de iOS); la regla `texto-chico-en-campo` de la compuerta debe quedar en 0. Para que el borde de 2 px no mueva el contenido, el campo compensa con `box-shadow: inset 0 0 0 1px` en foco o con padding.
- [ ] **Paso 5c: `Field`** — compone en vertical: etiqueta (14/600 `tinta`, `gap-2` sobre el control), control, ayuda (14/400 `apagado`) y error. El error ocupa un renglón `min-h-5` **siempre montado** (aunque esté vacío), con `WarningCircle` de 16 `weight="fill"` y texto de 14 `text-error`, **sin animar la altura**, solo fundido de opacidad de 150 ms; si hay error y ayuda, el error reemplaza a la ayuda en el mismo renglón; con dos renglones de error la altura se mide una vez y se reserva (máximo 2 líneas en 360 px, o se acorta el copy). `Despliegue` queda para tarjetas y el código promocional, no para errores de campo. (En F3 `Field` conserva el comportamiento actual de `ErrorDeCampo`; este cambio es deliberado y de F7.)
- [ ] **Paso 6: commit** `feat(marca): valores de Sun Baja Experience` (todavía sin desplegar).

### Task 7.3: Pasada de componentes (cambios visuales deliberados)

> «Solo valores» era falso para estos puntos (medidos el 2026-10-15): 16 `shadow-[...]` arbitrarias y 18 `shadow-*` sueltas, dos brillos amarillos con `rgba(255,222,0,…)`, 5 `ring-accent`, 2 `text-action` y h1/h2 con clases de tamaño sueltas.

- [ ] **Sombras:** convertir las 16 arbitrarias (p. ej. `checkout-section-card.tsx:54`, `booking-confirmation.tsx:167`, `checkout-loading-shell.tsx:58`, `cookie-notice`, `field-popover`) y las 18 `shadow-*` a tres tokens `--shadow-n0` (ninguna), `--shadow-n1` (barra inferior móvil) y `--shadow-n2` (popover, toast, hoja) con los valores de `design.md`: `--shadow-n1` = `0 -1px 0 #D9C9B4, 0 -6px 16px rgb(31 26 20 / .08)` (solo barra inferior móvil) y `--shadow-n2` = `0 8px 24px rgb(31 26 20 / .14)` (popover, toast, hoja y diálogo). El resumen, las tarjetas, el calendario y las tarjetas de servicio quedan en `n0` con borde `borde`. La regla `sombra-cruda` de la compuerta debe quedar en 0.
- [ ] **Brillo amarillo:** el panel de pago (`rgba(255,222,0,…)`, líneas ~399-404 de `stripe-panel.tsx` antes del split) **se elimina** (no se crea `--brillo-accion`: `design.md` prohíbe el brillo decorativo).
- [ ] **Foco:** los 5 `ring-accent` pasan a `focus-visible:ring-ring`.
- [ ] **`text-action` (2 usos):** el icono `Warning` sobre `bg-action/10` (`checkout-view.tsx:~1313`, `grupo-servicio.tsx:~114`) pasa a `text-aviso` sobre `bg-aviso-fondo`.
- [ ] **Titulares:** definir clases semánticas `texto-display`, `texto-pagina`, `texto-seccion` y `texto-paso` con la escala de `design.md` (40/64, 36/56, 28/36, 24/28) y aplicarlas a los h1/h2 de `sede-hero.tsx` (~38/60/76 px), el h1 de la portada (`app/[lang]/page.tsx`, ~48/60 px; el héroe nuevo del hub se construye en la Task 9.3 y `hub-hero.tsx`, huérfano, ya se borró en 5.4), el h1 de `servicio/[empresa]/[servicio]/page.tsx` (`text-5xl/6xl`) y `encabezado-compra.tsx` (`text-2xl/3xl`). La monoespaciada es más ancha: los `max-w-[19ch]` calibrados para Bebas condensada (comentario en `globals.css`) se revisan por desbordamiento en móvil de 360 px, en es y en. **Escala completa**, como clases semánticas en `@layer components` (ya declaradas en F2, Paso 3b, con los tamaños actuales; aquí reciben los valores de la marca), cada una con tamaño, peso, interlineado, tracking y `text-wrap: balance` juntos; corte en `sm` (640 px): `texto-display` 40 → 64, 1,05, −0,02 em, 700 mono; `texto-pagina` 36 → 56, 1,1, −0,02 em, 700 mono; `texto-seccion` 28 → 36, 1,15, −0,01 em, 700 mono; `texto-paso` 24 → 28, 1,2, −0,01 em, 700 mono; `texto-subtitulo` 20 → 22, 1,3, 600 cuerpo; `texto-cuerpo` 16, 1,5; `texto-pequeno` 14, 1,45; `texto-etiqueta` 16, 1,2, 0,01 em, 600; `texto-pie` 12, 1,4, 0,01 em. Las clases mono llevan `overflow-wrap: break-word` (no `anywhere`: reduce el tamaño mínimo de contenido a un carácter y un título junto a un ícono en flex o grid puede encogerse a una columna de una letra), `hyphens: manual` y `min-width: 0` en los hijos flex y grid. Consola Mono mide ~0,55 a 0,6 em por carácter (unos 13 a 14 caracteres por renglón a 40 px en 328 px de ancho): medirla con la fuente real antes de fijar titulares, sin navegador: `python -c "from fontTools.ttLib import TTFont; f=TTFont('ConsolaMono-Bold.ttf'); print(f['hmtx']['a'][0]/f['head'].unitsPerEm)"` da el ancho por carácter en em, y con él se calculan los renglones por titular. Verificar en 360 px, es y en: «Qué puedes reservar», «Reserva con tranquilidad», «Quién opera cada servicio», «Avistamiento de ballenas y orcas» (título de tarjeta a 24 px, hasta 3 renglones, sin clamp), «Puerto Chale» y «Sportfishing». **Antes de borrar la regla global `h1, h2` y `--tracking-titulo`** (7.2 Paso 3 las dejó provisionalmente): añadir la regla de compuerta `titular-sin-escala` = `/<h[12]\b(?![^>]*\btexto-(?:display|pagina|seccion|paso|subtitulo|cuerpo|pequeno|etiqueta|pie)\b)/g` (hoy 38 `<h1>`/`<h2>`, 10 con `font-sans` explícito; se añade a `REGLAS` y a la prueba de `guardia-estilos`, con `--escribir` en el mismo commit) y bajarla a 0 asignando clase a **cada** `<h1>`/`<h2>`, no solo a los cuatro sitios nombrados arriba: también `booking-confirmation.tsx:152`, `pedido-paquete.tsx:366`, `traslados/page.tsx:77`, `checkout-view.tsx:1177`, `aviso-fallo.tsx:17`, `site-footer.tsx:54`, `continuar-reservacion.tsx:330`, `deslinde` y `privacidad`; `not-found.tsx` usa `texto-pagina`; los h2 que son rótulos pequeños llevan `texto-subtitulo` o `texto-pequeno`. Solo entonces se borran la regla global y `--tracking-titulo`. Ningún texto baja de 12 px: las ~22 ocurrencias de `text-[10px]` y `text-[11px]` pasan a `texto-pie`. Se prohíben `uppercase` y `tracking-wider` (caja de oración; incluye el `kicker` de `encabezado-compra.tsx`, que se elimina); la regla `mayusculas-crudas` debe quedar en 0. Probar el título fijo más largo de la página de compra («Reserva tu estancia» y su par en inglés, «Book your fishing trip») a 360 px: no más de 2 renglones en `texto-pagina` (los títulos fijos por tipo de la Task 8.3 reemplazan al nombre del producto, que podía ocupar 3 a 5 renglones).
- [ ] **Objetivo táctil:** el contrato de `Button` de 7.2 Paso 5 (48 px en móvil, 44 px en escritorio) reemplaza los 40 px de F3 a F6; se actualiza la prueba de `variantes`.
- [ ] **Radios:** reemplazar los 56 `rounded-{md,lg,xl,2xl,3xl}` (y sus variantes de lado, p. ej. `rounded-t-xl`) por token: tarjetas y contenedores `rounded-card`, campos y cajas `rounded-campo`, botones `rounded-control`, hojas `rounded-t-sheet`, chips y días `rounded-full`. La regex de `radio-crudo` ya es la ampliada de la Task 0.1. La sobrescritura de `--radius-md…2xl` de 7.2 Paso 2 queda solo como red de seguridad.
- [ ] **Card y chips:** se elimina `Card elevada` y `variant="elevated"` de `CheckoutSectionCard` (hoy `shadow-[0_18px_45px…]`). `ChipActividad`: `h-7 rounded-full px-3 text-[14px] font-semibold gap-1.5` con icono de 16 (`Waves`, `Buildings`, `Mountains`, `weight="bold"`); mar `bg-azul-claro text-azul`, ciudad `bg-coral-claro text-coral-texto`, outside `bg-verde-claro text-verde`, **neutro `bg-cafe-bruma text-tinta-suave`** con `Bed`, `Van` o `Package` (para los tipos sin familia de actividad: Task 9.0 Paso 1d); nunca flota en pill sobre una foto (va en el cuerpo de la tarjeta o con fondo opaco). `design-components.md` ya dice «nunca flotando sobre la foto» (corregido el 2026-10-16). `AvisoEstado`: colores `exito/exito-fondo`, `error/error-fondo`, `aviso/aviso-fondo`, `info/info-fondo`. Iconos: 16 en texto, 20 en botones, 24 en navegación; `bold` para acciones y `regular` para decoración.
- [ ] **Héroe y secciones:** (valores nuevos que F5.4 no aplicó) `HeroMedia` de la sede pasa a `relative min-h-[70dvh] lg:min-h-[80dvh]` (nunca `h-screen`), pila máxima de 4 elementos (titular `texto-display` en ≤ 2 líneas, subtexto ≤ 20 palabras, un CTA principal y uno secundario), texto alineado abajo a la izquierda en ≥ 1024 px y fundido de opacidad de 400 ms del video sobre su `poster`; `SectionShell` pasa a `py-12 sm:py-16 lg:py-24` con ancho máximo 1120 y márgenes de 16, 24 y 32. Además `SectionShell` pasa a `fondo: 'arena' | 'blanco' | 'cafe-bruma'` (se eliminan `papel`, `bruma` y `bruma-profunda`; `cafe-claro` nunca es fondo de sección) alternando bandas en ese orden; `regla` es opcional y arranca en `false` (máximo 2 reglas por página: `reservar` en la sede y `sedes` en el hub; cuando se pinta es `bg-cafe-medio` de 48 × 2 px, nunca `cafe`); se borra `rev-regla` del resto de secciones, y no hay eyebrows sobre los títulos de F9 (`paquete-card.tsx`, con su eyebrow «Experiencia completa», se borra en 9.1b). El scrim del héroe es un degradado en `tinta`, no negro: `--scrim-hero: linear-gradient(to top, rgb(31 26 20 / .72) 0%, rgb(31 26 20 / .35) 45%, rgb(31 26 20 / 0) 75%)`; el texto sobre foto (`--hero-ink`) debe dar ≥ 4,5:1 contra la zona más clara bajo el titular, medido con la foto real.
- [ ] **`Skeleton` y toast:** `Skeleton` pasa a `bg-cafe-bruma` con `@keyframes pulso-esqueleto { 50% { opacity: .55 } }` de 1,2 s solo bajo `motion-safe`, y hereda el radio del elemento que reemplaza (el esqueleto del formulario de tarjeta no pulsa: Task 1.2). `Toast`: `rounded-control shadow-n2`, 5 s y descartable, `toast.tsx:98` conserva `top:` en ≥ 640 px y en móvil pasa a `bottom: calc(var(--barra-alto) + 8px)`, región `aria-live="polite"`; no se usa para errores que bloquean (esos usan el aviso de 8.3b).
- [ ] **Compuerta de marca:** `texto-chico-en-campo`, `mayusculas-crudas`, `radio-crudo`, `sombra-cruda`, `surface-deep` y `titular-sin-escala` en **0**, y `bg-surface-uso` solo con bandas de sección (más `motion-completo`, `boton-crudo`, `input-crudo`, `img-cruda`, `paleta-cruda` y `capas-ui` ya en 0 desde F6) antes de pedir la revisión del dueño.
- [ ] **Verificación:** `verificar` completo, `guardia` en 0 salvo exentos, build; revisión del dueño de portada, hub, sede, servicio, los tres checkouts, traslados, confirmación y páginas de error, en es y en. PUNTO DEL DUEÑO, que incluye el contraste de `--hero-ink` contra la zona más clara bajo el titular **con la foto real** (no se puede medir sin navegador ni sin la foto definitiva).
- [ ] **Commit** `feat(marca): sombras, foco, titulares y brillos con la identidad nueva`.
- [ ] F7 **no se despliega sola**: sale junto con F8.

---

## F8 — Página de reserva nueva (sale con F7)

> Especificación: `docs/design/design-components.md` (secciones «Página de reserva», «Selección de fecha» y «Tarjeta de paso»). Decisiones del dueño: se quita **solo el stepper numerado**; **tres pasos en todas las rutas** — **Viaje** (fecha, personas, **extras**) · **Tus datos** (contacto + recogida u hotel + notas) · **Pago**; con dos empresas, «Pago 1 de 2» y «Pago 2 de 2» son sub-pasos dentro de Pago; los traslados también quedan en 3 (contacto + recogida en «Tus datos»); paquetes de varias noches con **duración fija**; cabecera mínima con flecha, logo e idioma; calendario con alcance recortado (sin «pocos lugares» ni corte por cupo de hospedaje). **Ronda 4 del crítico (recorridos de todos los servicios) + derivación PFD (R1–R5)** añadieron: un solo botón por pantalla en Pago con la barra **dentro de Stripe**, un patrón único de aviso con acción, historial por paso y borrador en la pestaña, una sola flecha, regreso de traslados **vacío y obligatorio**, bajo demanda como «reserva confirmada al pagar», y controles de fecha y personas según el tipo de servicio (pesca, paseo, hospedaje por noche, bajo demanda, transporte). **Los precios en USD ya se derivan del tipo de cambio de la sede: siempre existen**, así que no hay estado «sin precio USD» que proteger.

### Task 8.0: Historial por paso, borrador en la pestaña y una sola flecha (PFD R4)

**Files:** Create `src/lib/borrador-reserva.ts`, `tests/borrador-reserva.test.cjs`, `src/lib/origen.ts`, `tests/origen.test.cjs`; Modify `checkout-view.tsx`, `pedido/pedido-paquete.tsx`, `traslado-view.tsx`, `lang-switch.tsx`, `continuar-reservacion.tsx`, `lib/pendientes.ts`, `lib/booking-href.ts`, `tests/booking-href.test.cjs`, `tests/pendientes.test.cjs`, `tests/run-hub-tests.cjs` (registrar `'borrador-reserva': ['src/lib/borrador-reserva.ts', 'BORRADOR_TEST_OUT']` y `origen: ['src/lib/origen.ts', 'ORIGEN_TEST_OUT']`; sin registrar, la prueba no corre).

> Hallazgos (verificados): los pasos son estado de React, no historial, así que el Atrás del navegador sale de la compra (en Android, el gesto de atrás); todo lo previo a crear la reserva vive en memoria y en `sessionStorage` solo queda `checkoutId`; `lang-switch.tsx:121` hace `router.push(pathname + window.location.search)`, lo que remonta el árbol y vuelve a Viaje con la moneda recalculada por idioma; `Pendiente.ruta` guarda el idioma con que se creó; `volverHref` (`checkout-view.tsx:~1402`) manda `/${lang}?day=&time=&people=` a una portada que ya no los lee; hay dos flechas con funciones distintas en el plan.

- [ ] **Paso 1: borrador (módulo puro con prueba primero).** `lib/borrador-reserva.ts` exporta `guardar(clave, estado)`, `leer(clave)` y `borrar(clave)` sobre `sessionStorage` (con `try/catch`: puede lanzar en modo privado), con `version` en el JSON y una vigencia de 4 horas; descarta lo ilegible o de otra versión. Guarda fecha(s), personas, extras, moneda, contacto, recogida, deslinde **no** (el deslinde se acepta de nuevo siempre) y el paso actual. Clave por ruta y producto (`salysol:borrador:<ruta>:<slug>`). **Autorizado por el dueño: solo en la pestaña, se borra al confirmar el pago.** Pruebas: ida y vuelta, versión distinta, vigencia vencida, JSON roto, almacenamiento no disponible. El borrador se restaura con `useSyncExternalStore` o con el patrón `useLayoutEffect` que ya usa `checkout-view.tsx:~104–139`, para evitar un mismatch de hidratación.
- [ ] **Paso 2: historial por paso.** Cada paso es una entrada de historial con `?paso=viaje|datos|pago` con `window.history.pushState` al avanzar y `window.history.replaceState` dentro del mismo paso (se integra con el router y `useSearchParams` sin recargar: `single-page-applications.md`). **No** `router.push/replace`: `reservar/page.tsx` es dinámica y cada navegación del router repediría el RSC y repetiría `getServicioDetalle`/`getPaqueteDetalle`/`getTraslados` contra el backend en cada paso; `router.push` queda solo para cambios de ruta o de idioma. El Atrás del navegador vuelve al paso anterior; el paso se deriva de `useSearchParams()` (una sola fuente de verdad; no hay listener de `popstate` aparte). Un paso al que no se ha llegado se redirige al último válido. **Con orden o reserva creada** (`checkoutId`/`ordenId` en `sessionStorage`), un `?paso=viaje|datos` (el Atrás del navegador tras retener dinero) se redirige con `replaceState` a `?paso=pago` y se abre el `AlertDialog` de «Cancelar y liberar mi lugar» (Task 8.4c); sin orden, Atrás funciona normal.
- [ ] **Paso 3: idioma.** Cambiar de idioma conserva `?paso=` y restaura el borrador; la moneda por idioma pasa a ser solo el **valor inicial** (el borrador manda después). `ContinuarReservacion` abre la ruta en el idioma **actual**, no en el guardado.
- [ ] **Paso 4: una sola flecha.** La flecha de arriba a la izquierda es siempre «paso anterior»; en Viaje es «salir» al origen. `lib/origen.ts` (con prueba) resuelve el origen: parámetro `origen` explícito (sede, servicio o portada) y, si falta, la página de la sede; se eliminan `day/time/people` de `volverHref`. `?moneda=` (que llevan todos los enlaces de `booking-href.ts`) se lee en Viaje. Se actualizan `tests/booking-href.test.cjs` (nuevo parámetro `origen`) y `tests/pendientes.test.cjs` (la ruta se abre con el idioma actual).
- [ ] **Paso 5:** `tsc`, `eslint`, `npm test`, `build`. Recorridos: recargar en cada paso, Atrás y Adelante, cambio de idioma a media compra, entrada con query, entrada desde «Continuar reservación». **Paso 6: commit** `feat(reserva): historial por paso, borrador en la pestaña y flecha única`.

### Task 8.1: Tres pasos en las cuatro rutas

**Files:** Create `src/lib/campo-paso.ts`, `tests/campo-paso.test.cjs`, `src/lib/validar-reserva.ts`, `tests/validar-reserva.test.cjs`; Modify `src/lib/pasos-checkout.ts`, `tests/pasos-checkout.test.cjs`, `checkout-view.tsx`, `pedido/pedido-paquete.tsx`, `traslado-view.tsx`, `checkout-stepper.tsx` (se elimina el numerado), `src/app/[lang]/dictionaries/{es,en}.json` (`checkout.stepper`), `tests/run-hub-tests.cjs` (registrar `'campo-paso': ['src/lib/campo-paso.ts', 'CAMPO_PASO_TEST_OUT']` y `'validar-reserva': ['src/lib/validar-reserva.ts', 'VALIDAR_RESERVA_TEST_OUT']`).

> Hallazgos del crítico verificados: `ORDEN_PASOS` es una constante global de 4 pasos (`pasos-checkout.ts:7-9`); el literal `4` aparece en `checkout-view.tsx:~1249`, `traslado-view.tsx:~595` y `pedido-paquete.tsx:~408-414, ~457, ~531-532` (`actual: 4 + indicePago`); las claves `checkout.stepper` son `trip/contact/extras/payment` y `pedido-paquete.tsx:~404-415` arma `steps`/`etiquetasCortas`; en servicio suelto «detalles» son los extras (`checkout-view.tsx:~1590-1620`) y en paquete una tarjeta por servicio (`pedido-paquete.tsx:~648-654`).

- [ ] **Paso 1: prueba primero** en `tests/pasos-checkout.test.cjs`: `ORDEN_PASOS` es `['viaje','datos','pago']`, `numeroDePaso('pago') === 3`, y `estadoDeTarjeta` mantiene las reglas actuales (oculto / activo / completado / editando). Verla fallar.
- [ ] **Paso 2:** cambiar `PasoId` y `ORDEN_PASOS` a `viaje | datos | pago` (una sola constante vale porque las cuatro rutas quedan iguales). Los sub-pasos de pago por empresa son estado propio del paso Pago (`indicePago`, `totalPagos`), no pasos nuevos: se elimina `actual: 4 + indicePago` y todo `4` literal.
- [ ] **Paso 3:** mover los **extras** al bloque de Viaje (servicio suelto: `bloque-extras` desde «detalles»; paquete: la tarjeta por servicio) y unir `bloque-contacto` + `bloque-recogida` en «Tus datos» (los bloques existen desde F5). `GrupoServicio` ya está partido por la Task 5.3 (`grupo-viaje.tsx` = personas, extras, tipo de traslado y fecha(s); `grupo-datos.tsx` = punto de recogida y zona): aquí solo se reagrupan en los tres pasos (el tipo de traslado decide si hay regreso y zona). **Validación con dueño (PFD R5):** `lib/validar-reserva.ts` (puro, con `tests/validar-reserva.test.cjs`): `validarTodo(estado, ruta): { paso, campo, mensaje } | null` devuelve el primer problema; `iniciarPago` y el `enviar` de cada ruta la usan en lugar de `document.getElementById(...).focus()` (que no hace nada si el campo no está montado) y de `setEditando(...)`. Un 400 del servidor con errores por campo se enruta con `lib/campo-paso.ts` (función pura `pasoDeCampo(campo: string): 'viaje' | 'datos' | 'pago'`, con `tests/campo-paso.test.cjs`; `lib/errores.ts` no se toca: importa valores de `@/lib/api`). El problema se muestra con el patrón de aviso de la Task 8.3b, cuya acción principal es «Corregir [dato] en [paso]»: navega a ese paso (entrada de historial) y **enfoca el campo después de montar el paso**. Casos que hoy solo se detectan en Pago y deben enrutarse igual: cambiar la fecha de inicio tras fijar la de regreso (`pedido-paquete.tsx:~294`) y cambiar el tipo de traslado tras elegir la recogida (`traslado-view.tsx:~373`).
- [ ] **Paso 4:** diccionarios: sustituir `checkout.stepper` (`trip/contact/extras/payment`) por `viaje/datos/pago` en es y en, con «Viaje», «Tus datos», «Pago» y «Paso N de 3»; reiniciar `npm run dev` (Turbopack cachea los JSON).
- [ ] **Paso 5: límite de campos** — contar los controles de «Viaje» por ruta (fecha, personas, extras obligatorios y opcionales). Si en alguna ruta pasan de ~7, **parar y avisar al dueño** antes de seguir (PFD R1): los opcionales se pliegan bajo «Más opciones» en vez de crear un cuarto paso.
- [ ] **Paso 6:** recorridos manuales de F5 en las cuatro rutas, incluido el rechazo en «Pago 2 de 2». **Paso 7: commit** `feat(checkout): tres pasos en todas las rutas; extras en Viaje`.

### Task 8.1b: Descripción de las personalizaciones (backend + frontend)

> Decisión del dueño (2026-10-16): las personalizaciones llevan **descripción** es/en, que el checkout muestra bajo cada extra. Hoy `Personalizacion` (`backend/apps/fleet/models.py`) solo tiene `nombre` (sin traducción), `tipo`, `tipo_interaccion`, `opciones_seleccion`, `aviso_reforzado`, `cobrar_por_persona` y `cantidad_editable`. Va en F8 porque el bloque de extras vive en el paso Viaje desde 8.1; el backend debe estar desplegado antes que el frontend que lo lee.

**Files:** Modify `backend/apps/fleet/models.py` (`Personalizacion`), `backend/apps/fleet/serializers.py` (`ServicioPersonalizacionSerializer` y todo serializer que exponga la personalización: `grep -rn "opciones_seleccion" backend/apps`), `backend/apps/fleet/admin.py` (`PersonalizacionAdmin`); Create la migración siguiente de `fleet` y `backend/apps/fleet/tests_personalizacion_descripcion.py`; Create `src/lib/texto-localizado.ts` y `tests/texto-localizado.test.cjs`; Modify `tests/run-hub-tests.cjs` (registrar `'texto-localizado': ['src/lib/texto-localizado.ts', 'TEXTO_LOCALIZADO_TEST_OUT']`), `src/lib/api.ts` (tipo de personalización), `checkout/bloques/bloque-extras.tsx`, `pedido/grupo-viaje.tsx` y la tarjeta de personalizaciones de `pedido/pedido-paquete.tsx`.

- [ ] **Paso 1: backend, prueba primero** (`tests_personalizacion_descripcion.py`): `descripcion` vale `{}` por defecto; `clean()` rechaza lo que no sea un objeto, claves distintas de `es` y `en`, valores que no sean texto o pasen de 160 caracteres (se recortan los espacios); el serializer la expone tal cual; una personalización sin descripción sigue siendo válida.
- [ ] **Paso 2: modelo y admin.** `descripcion = models.JSONField(default=dict, blank=True)` con forma `{"es": "…", "en": "…"}`, validada en `clean()`. En `PersonalizacionAdmin` el formulario muestra dos campos de texto, `descripcion_es` y `descripcion_en`, que se guardan en ese JSON (nadie edita JSON a mano), editables **al crear** la personalización. `ServicioPersonalizacionSerializer` añade `descripcion = JSONField(source='personalizacion.descripcion', read_only=True)`. Migración sin datos (el campo nace vacío). Tras migrar, correr las suites de `apps.fleet` en SQLite y en Postgres.
- [ ] **Paso 3: frontend, prueba primero.** `lib/texto-localizado.ts` (puro, sin imports): `textoLocalizado(valor: { es?: string; en?: string } | null | undefined, lang: 'es' | 'en'): string` devuelve el idioma pedido, si falta el otro y si no hay nada `''`; la usan también `incluye` (F9) y las demás descripciones por idioma. `lib/api.ts`: `descripcion?: { es?: string; en?: string }` en el tipo de personalización del catálogo.
- [ ] **Paso 4: dónde se ve.** `bloque-extras` pinta la descripción bajo el nombre de cada extra, en `texto-pequeno apagado`, enlazada con `aria-describedby` al control; **sin descripción no se pinta nada, ni hueco**. En la tarjeta de personalizaciones de **cada empresa** del checkout cruza-empresa, la cabecera de la tarjeta lleva el `EmpresaSello` de 24 (logo, o monograma si la empresa no tiene) y el nombre de la empresa (Task 3.7); en servicio suelto y paquete de una empresa no hace falta, porque la empresa ya está en la línea `detalle` del título.
- [ ] **Paso 5:** `tsc`, `eslint`, `npm test`, `build`, `guardia`. PUNTO DEL DUEÑO: crear una personalización con descripción en el admin y verla en el paso Viaje de servicio suelto y de cruza-empresa. Commits `feat(fleet): descripcion es/en en Personalizacion` y `feat(reserva): descripcion de cada extra en el paso Viaje`.

### Task 8.2: Cabecera mínima sin navbar y `--nav-alto`

**Files:** Create `src/components/reserva/cabecera-minima.tsx` (cliente). Modify `checkout/pagina-checkout.tsx:36`, `pedido/pedido-paquete.tsx:364,455,477`, `booking-confirmation.tsx:125`, `app/[lang]/traslados/page.tsx:61` (estado «no disponible») y `checkout-loading-shell.tsx:19`: cada `<SiteHeader … minimo />` pasa a `<CabeceraMinima …/>`. Retirar la prop `minimo` de `site-header.tsx` y su rama `links = minimo ? [] : …`. Modify `src/app/globals.css` y `src/app/[lang]/layout.tsx:99` (clase `lang-switch-fijo`). (`/reservar` y `/traslados` no tienen `layout.tsx`: la cabecera se monta dentro de esos componentes.)

- [ ] **Qué lleva (decisión del dueño, 2026-10-16: logo provisional y sin WhatsApp).** Flecha de volver (48 × 48; su significado y destino se definen en la Task 8.0: **una sola flecha**), la marca de Sun Baja Experience y el selector ES/EN; sin navbar completo en `/reservar` y `/traslados`; el cambio de idioma conserva `?paso=` y restaura el borrador (Task 8.0). **Marca:** mientras no llegue el logo definitivo es el monograma «SB» en círculo de 32 px (`EmpresaSello nombre="Sun Baja Experience" tamano={32}`, Task 3.7); no hay wordmark de texto (desborda a 360 px: la cabecera deja ~192 px útiles). **Una o dos marcas:** el checkout de **dos empresas** (cruza-empresa) lleva solo la nuestra, para no privilegiar a una; el de **una empresa** (servicio suelto, paquete de una empresa y traslados) añade, a la derecha de la nuestra y separada por una línea vertical de 1 px `borde`, el `EmpresaSello` de 32 de la empresa que presta el servicio (prop opcional `empresa` de `CabeceraMinima`). *Supuesto a confirmar por el dueño: que el checkout de una sola empresa lleve las dos marcas; si prefiere solo la nuestra, se quita la prop.* **El WhatsApp sale de la cabecera** (el `SiteHeader minimo` actual lo incluía); la ayuda queda en `AyudaFlotante`, sobre la barra inferior (Task 8.4c). `ContinuarReservacion` sigue fuera del checkout.
- [ ] **Composición de la cabecera:** alto 56, fondo `arena`, `border-b border-borde`, sin sombra ni blur; z-index en la escala `--z-cabecera: 40; --z-barra: 50; --z-hoja: 60; --z-toast: 70` ya declarada en `globals.css` (F2 Task 2.1 Paso 1b; aquí solo se usa). Cuadrícula `grid-cols-[48px_1fr_auto]`: flecha a la izquierda, marca(s) centradas, selector a la derecha. El selector es una variante compacta de `LangSwitch`: dos segmentos «ES | EN» en `texto-pequeno`, 44 × 44 cada uno, el activo con `bg-cafe-bruma text-cafe font-semibold`, sin banderas ni mayúsculas decorativas. La marca es una imagen sin enlace mientras haya una orden con dinero retenido; en cualquier otro caso enlaza a la portada. Verificar que no desborda en 360 px, en es y en, con una y con dos marcas.
- [ ] **`--nav-alto` por ruta y selector fijo:** `globals.css:~60-69` ya avisa que este token se desincronizó una vez. `ProveedorToast` y el `LangSwitch` fijo (`layout.tsx:97-101`) son hermanos de las páginas, así que una clase en un hijo no les llega: la raíz de `PaginaCheckout`, de `CheckoutLoadingShell` y de las pantallas de confirmación y de fallo lleva la clase `reserva-minima`, y el CSS la lee desde `html`:

```css
html:has(.reserva-minima) { --nav-alto: 56px; --banda-alto: 0px; }
@media (min-width: 64rem) { html:has(.reserva-minima) { --nav-alto: 0px; } }
html:has(.reserva-minima) .lang-switch-fijo { display: none; }
```

  La cabecera es `sticky top-0` por debajo de 1024 px y estática desde ahí; en esas rutas el `LangSwitch` fijo se oculta siempre para no duplicar el selector (por eso no se usa `hidden lg:block`, que lo mostraría justo en escritorio). Re-verificar los consumidores de `--nav-alto`: `pagina-checkout.tsx:~40`, `checkout-loading-shell.tsx:~26,37`, `checkout-section-card.tsx:~189` (scroll-mt), `toast.tsx:~98`, `traslados/page.tsx:~62`, `pedido-paquete.tsx:~365,456,478`, `booking-confirmation.tsx:~132` (`checkout-stepper.tsx` desaparece en 8.3). La confirmación y las pantallas de fallo de la misma ruta usan la misma cabecera.
- [ ] **PUNTO DEL DUEÑO:** cubierto por el recorrido de la Task 8.4c.
- [ ] Commit `feat(reserva): cabecera mínima y --nav-alto por ruta`.

### Task 8.3: Título grande, resumen plano y pasos con nombre

- [ ] **Título fijo por tipo (decisión del dueño, 2026-10-16).** `EncabezadoCompra` (`encabezado-compra.tsx`, hoy `kicker` «Tu compra» + nombre del producto) pasa a un `h1` fijo por tipo desde `dict.checkout.tituloPagina`: pesca «Reserva tu pesca»/«Book your fishing trip»; paseo «Reserva tu paseo»/«Book your tour»; hospedaje «Reserva tu estancia»/«Book your stay»; transporte «Reserva tu traslado»/«Book your transfer»; paquete «Reserva tu paquete»/«Book your package». Va en `texto-pagina`. El nombre del producto, la sede y las empresas pasan a la línea `detalle` (`texto-pequeno apagado`); el `kicker` se elimina. Motivo: un nombre como «Avistamiento de ballenas y orcas» (32 caracteres) a 36 px ocupa 3 o más renglones y un paquete largo, 5 o más. Prueba de longitud en 7.3: «Reserva tu estancia» y «Book your fishing trip» a 360 px, máximo 2 renglones.
- [ ] Título de página 36 px móvil / 56 px escritorio (`texto-pagina`); resumen en elevación 0 (ya en `n0` por F7.3); se elimina `checkout-stepper.tsx`. Las tarjetas de paso muestran «Paso N de 3» y su título en `texto-paso` (24 px móvil / 28 px escritorio, Consola Mono 700). El nombre del paso en el asistente móvil usa la misma clase (24 px). **Regla del título en móvil:** en Viaje se ve `texto-pagina` (36) y debajo «Paso 1 de 3» en `texto-pequeno apagado` más el nombre del paso en `texto-paso`; en «Tus datos» y «Pago» el título de página no se repite: queda solo el nombre del paso en `texto-paso` y debajo una línea de contexto `texto-pequeno apagado` («Reserva tu pesca · sáb 7 nov»), para no apilar dos titulares mono. **`CheckoutSectionCard`:** estados `abierto`, `completado` y `pendiente` (`editando` y `suspendido` se retiran y mapean a `abierto` y `pendiente`). Cabecera: «Paso N de 3» en `texto-pequeno font-semibold text-apagado` y el título en `texto-paso`; `pendiente` pinta el título en `text-apagado` y no abre; `completado` muestra en una línea título + resumen («Sábado 7 de nov · 2 personas») + la acción «Modificar» (variante `texto`, 44 de alto; reemplaza «Cambiar» y «Listo» en es y en). Padding 24, 32 desde `lg`. La altura anima con `Despliegue` en 250 ms (solo opacidad con reducir movimiento).
- [ ] **PUNTO DEL DUEÑO:** cubierto por el recorrido de la Task 8.4c.
- [ ] Commit `feat(reserva): título grande, resumen plano y pasos con nombre`.

### Task 8.3b: Un solo patrón de aviso con acción (PFD R3)

**Files:** Create `src/components/ui/aviso-accion.tsx`, `src/lib/problema-reserva.ts`, `tests/problema-reserva.test.cjs`; Modify `checkout-view.tsx` (`volverPorSinCupo`), `pedido/use-pago-pedido.ts`, `pedido/aviso-fallo.tsx`, `traslado-view.tsx`, `pagina-checkout.tsx` (el slot `aviso`), `tests/run-hub-tests.cjs` (registrar `'problema-reserva': ['src/lib/problema-reserva.ts', 'PROBLEMA_TEST_OUT']`).

> Hallazgos: hoy sin cupo, rechazo de tarjeta y apartado vencido se resuelven distinto por ruta (servicio suelto manda a Viaje con un aviso y fecha alternativa; paquete de una empresa se queda en Pago con un bloque de error; cruza-empresa tiene pantalla de fallo completa; traslados recarga). El apartado no tiene cuenta regresiva.

- [ ] **Paso 1: tipos y textos (módulo puro con prueba primero).** `lib/problema-reserva.ts` define `Problema = { tipo, queOcurrio, queSeConserva, lineasDinero: string[], accionPrincipal, accionSecundaria? }` con `tipo` en `sin_cupo | tarjeta_rechazada | apartado_vencido | red | catalogo_caido | dato_previo`, y una función `problemaDe(clase: ClaseDeFallo, contexto: { motor: 'reserva' | 'orden'; indicePago?: number; empresa?: string })` que lo construye. `ClaseDeFallo` entra con `import type { ClaseDeFallo } from './errores'` (se borra al compilar); quien llama hace `problemaDe(clasificar(error), contexto)`. `problema-reserva.ts` no importa valores con `@/`. `lineasDinero` viene de `fallo-pago.ts` y conserva lo que hoy dice `AvisoFallo` (`aviso-fallo.tsx:11`: «Qué pasó con el dinero. Va antes que cualquier otra cosa»): se pinta antes de la acción. Pruebas: cada tipo produce una acción principal, nunca más de una; `dato_previo` incluye `{ paso, campo }`; el motivo `tarjeta_rechazada` en cruza-empresa trae `lineasDinero`.
- [ ] **Paso 2: acciones.** `sin_cupo` → «Elegir otra fecha» (a Viaje, con la fecha alternativa si el servidor la propone); `tarjeta_rechazada` → «Probar otra tarjeta»: empieza un intento **nuevo** (tras un rechazo el backend revierte la orden incompleta y `reintentar()` crea otra con `checkout_id` nuevo; la retención se libera: `es.json:870-872`). En cruza-empresa, `queSeConserva` usa `pedido.fallo.liberaRetencion` y `dobleRetencion`; en servicio suelto y paquete de una empresa no hubo retención previa: «No se hizo ningún cobro.»; `apartado_vencido` → «Volver a apartar mi lugar»; `red` → «Reintentar» (conserva lo capturado); `catalogo_caido` → «Escribirnos por WhatsApp» solo si `tieneWhatsapp` (número único del sitio, `lib/contacto.ts`; decisión del dueño, 2026-10-16) y siempre «Volver» al origen: si no hay número, el botón de WhatsApp no se pinta y la acción principal es «Reintentar»; `dato_previo` → «Corregir [dato] en [paso]» (Task 8.1).
- [ ] **Paso 3: componente.** `AvisoAccion` (aviso de `design-components.md`) se monta **siempre en el mismo sitio**, encima de la barra inferior en móvil y encima del botón de la tarjeta en escritorio; `role="alert"`. **Foco:** no se envía a la acción principal (el lector anunciaría dos veces y se saltaría el mensaje); o el foco se queda donde está y manda `role="alert"`, o se enfoca el **contenedor** del aviso (`tabIndex={-1}`), nunca la acción. **Estructura y tono:** `rounded-control p-4`, icono de 20 a la izquierda y cuerpo de 14 con título (`queOcurrio`, 14/600), texto (`queSeConserva`, 14/400) y debajo la acción; `sin_cupo`, `apartado_vencido` y `dato_previo` usan el tono `aviso`; `tarjeta_rechazada`, `red` y `catalogo_caido` usan `error`; nunca colores de actividad. **Botón único por pantalla:** mientras haya un problema bloqueante (`sin_cupo`, `tarjeta_rechazada`, `apartado_vencido`, `catalogo_caido`) la barra oculta su botón `principal` y la acción del aviso pasa a ser el botón de la pantalla (variante `principal`); en problemas no bloqueantes (`red`, `dato_previo`) la barra conserva su botón y la acción del aviso es `secundario`. En móvil el aviso se fija encima de la ranura de estado de la barra; en escritorio va dentro de la tarjeta, justo encima del botón del paso. Entra con fundido de 150 ms y, si empuja contenido, con `Despliegue` en 250 ms; en la barra fija no empuja nada. Reemplaza los tratamientos distintos de las cuatro rutas.
- [ ] **Paso 4: cuenta regresiva real.** Solo si el servidor devuelve el vencimiento del apartado de cupo: `apartado_hasta` (`Pago.apartado_hasta`, `lib/api.ts:117`), guardado como `apartadoHasta` en `checkout-view.tsx` y `use-pago-pedido.ts`. (No es el campo de la hora en que se libera una orden de varias empresas.) «Tu lugar está apartado, quedan 14:32» (icono de reloj). Se elimina la línea fija `checkout.apartadoLinea` de `FormularioPago` (`stripe-panel.tsx:270-276` antes del split), que duplicaría la píldora; sin apartado (`APARTADO_MINUTOS=0`) no se pinta nada. La renovación silenciosa `antesDePagar` sigue: al llegar a 0 la acción «Volver a apartar mi lugar» invoca esa misma renovación y el estado pasa a `apartado_vencido`. Depende de que `APARTADO_MINUTOS=15` esté encendido en producción (hoy apagado).
- [ ] **Paso 5:** recorridos: sin cupo al pagar en cada ruta, rechazo de tarjeta en el primer y en el segundo pago, apartado vencido, red caída, servicio nulo. **Paso 6: PUNTO DEL DUEÑO:** cubierto por el recorrido de la Task 8.4c. **Paso 7: commit** `feat(reserva): un solo aviso con acción para todos los problemas`.

### Task 8.4a: Barra inferior, línea de progreso y hoja de resumen (PFD R1, R2, R5)

**Files:** Create `src/components/reserva/{linea-progreso,barra-inferior,asa-resumen}.tsx`, `src/lib/etiqueta-boton.ts`, `tests/etiqueta-boton.test.cjs`; Modify `checkout/pago/tarjeta-como-pagas.tsx`, `pedido/use-pago-pedido.ts`, `checkout/pagina-checkout.tsx`, `tests/run-hub-tests.cjs` (registrar `'etiqueta-boton': ['src/lib/etiqueta-boton.ts', 'ETIQUETA_BOTON_TEST_OUT']`); Delete `franja-resumen.tsx` y la prop `resumenSoloEscritorio` (duplican el asa y la hoja nuevas).

> Hallazgos (verificados): el paso Pago tiene **dos acciones distintas**: la primera crea la reserva u orden y retiene (botón de `TarjetaComoPagas`, `stripe-panel.tsx:~389-420`, o `continueToPayment` en `pedido-paquete.tsx:~871`); la segunda confirma el cobro con `stripe.confirmPayment` dentro de `PaymentForm` (`stripe-panel.tsx:~134`), que solo funciona dentro de `<Elements>`. En cruza-empresa son tres pantallas (Cómo pagas, Pago 1, Pago 2).

- [ ] **Regla de la etiqueta (módulo puro con prueba primero).** `lib/etiqueta-boton.ts`: `etiquetaDeBoton({ paso, subpaso, montoConfirmado, empresa, cargos })`. Un **monto solo aparece cuando el servidor lo confirmó** (o la vista previa está probada como exacta): antes dice «Continuar a pago»; hospedaje por noche y todo servicio con precio por estrategia dice «Estimado» en el resumen hasta que el servidor responde. Pruebas: sin monto confirmado nunca hay cifra; con monto, el texto incluye empresa y cifra; «Pago 1 de 2» y «Pago 2 de 2».
- [ ] **Tres segmentos y sub-pasos.** La línea de progreso mantiene tres segmentos sin números (una lista `<ol>` con `aria-current="step"` en el segmento activo y el texto «Paso 3 de 3: Pago»; no `role="progressbar"`); «Pago 1 de 2 · [empresa] · $X» va en la **primera línea de la pantalla** (PFD R2) y no añade segmentos. En la pantalla (b) de cruza-empresa, la hoja «Ver resumen» muestra cada cargo con su estado (pendiente, retenido, cobrado) y el aviso de doble retención.
- [ ] **Resto del asistente.** En < 640 px: un paso por pantalla, sin tarjetas plegables; flecha única arriba a la izquierda (Task 8.0); el asa «Ver resumen · $X» abre la hoja; el botón deshabilitado dice qué falta. El estado vive en el reducer existente y en el borrador; el cambio de paso lleva el foco al título y se anuncia con `aria-live`. Pantallas de reanudación (`retomar` o recarga) muestran **solo Pago**, con el resumen construido desde el pedido del servidor, **no** con tarjetas de Viaje y Datos rellenadas con valores inventados (`pedido-paquete.tsx:~557-574` pinta hoy `estado.inicio ?? minDate` y contacto vacío).
- [ ] **Presupuesto de la barra (< 640 px):** asa 48 (área táctil de 48, píldora visual de 40) + 8 + línea de progreso 4 + 12 + botón 48 + 8 + ranura de razón 20 + 12 + `env(safe-area-inset-bottom)`, unos 160 px más la safe-area. Se mide con `ResizeObserver` y se publica como `--barra-alto`. El contenedor de página usa `padding-bottom: calc(var(--barra-alto) + 16px)` y `scroll-padding-bottom` igual (ningún foco queda tapado por la barra); el toast se ancla a `calc(var(--barra-alto) + 8px)`.
- [ ] **Un solo sitio por tipo de mensaje:** la razón del botón deshabilitado va **debajo** del botón (ranura de 20 px reservada solo en los pasos con botón); la cuenta regresiva del apartado va **encima** del botón en su propia píldora (`bg-cafe-claro text-cafe-profundo`, 32 de alto, `Clock` de 16). Si coinciden, la cuenta regresiva queda arriba y la razón abajo. Ambas alturas se reservan siempre para que nada brinque. (Esto resuelve la contradicción entre `design-guidelines.md` y `design-components.md`.)
- [ ] **Estructura sin `transform` en ancestros:** la barra, la cabecera y el aviso son **hermanos**, no hijos, del contenedor que desliza entre pasos (un ancestro con `transform` rompe `position: fixed`). El deslizamiento (`translateX(24px) → 0`, 250 ms, `curva-estandar`) solo se aplica al contenido del paso. **Las pantallas de Pago no deslizan**: solo fundido de 150 ms. El contenedor de Stripe nunca lleva `transform`, `filter` ni `will-change`.
- [ ] **Asa y progreso:** el asa es una fila de 48 con `texto-etiqueta`, «Ver resumen · $4,100 MXN» (`tabular-nums`; sin monto confirmado lleva el rótulo «Estimado» al lado, igual en asa, resumen y barra), `CaretUp` de 16 a la derecha, borde superior `borde` y fondo `blanco`; el cambio de monto hace fundido de 150 ms. La línea de progreso son 3 `<li>` de 4 px de alto, `rounded-full`, `gap-2`, ancho completo; completados y actual en `bg-cafe`, pendientes en `bg-cafe-claro`; el relleno anima con `transform: scaleX` desde la izquierda en 250 ms (no `width`); «Paso 2 de 3: Tus datos» va `sr-only`. Estados de cargo en la hoja de resumen: `Clock` (pendiente), `Lock` (retenido) y `CheckCircle` (cobrado), con texto en el mismo renglón y colores de estado, nunca de actividad.
- [ ] **Layout en escritorio (≥ 1024 px):** `grid grid-cols-[minmax(0,640px)_minmax(300px,360px)] gap-8 justify-center max-w-[1120px] mx-auto px-8` (640 + 360 + 32 no cabe en 960 px: las columnas se comprimen sin desbordar y la de pasos nunca baja de 560). La columna del resumen es `sticky top-6` con `max-h-[calc(100dvh-48px)] overflow-y-auto` para que dos empresas con extras no queden cortadas. Entre 640 y 1023 px es una sola columna con el resumen **debajo** del último paso y sin barra inferior (el asistente de una pantalla es solo < 640 px).
- [ ] **Copy de la barra:** «Estimado», «Cancelar y liberar mi lugar» y «Seguir con mi reserva» van en el diccionario es/en; ninguna etiqueta de botón lleva guion largo; las razones («Elige una fecha para continuar», «Verificando que eres una persona…») caben en un renglón en 360 px, también en inglés.
- [ ] **`PieDeTarjeta` plano.** En escritorio `PieDeTarjeta` es hoy una capa translúcida con desenfoque y sombra de 30 px (`pie-tarjeta.tsx:60`) que choca con «superficies planas»: pasa a plano, sin `backdrop-blur` ni sombra mayor que `n1`.
- [ ] **PUNTO DEL DUEÑO:** barra, asa, línea de progreso y hoja «Ver resumen» (aquí se verifica también el `Sheet` de la Task 3.5), en móvil real y en escritorio.
- [ ] Commit `feat(reserva): barra inferior, linea de progreso y hoja de resumen`.

### Task 8.4b: La barra dentro de Stripe y las sub-pantallas de Pago

> Requiere 1.2b (formulario de tarjeta diferido) y 8.4a.

**Files:** Modify `checkout/pago/formulario-pago.tsx`, `checkout/pago/tarjeta-como-pagas.tsx`, `pedido/use-pago-pedido.ts`, `checkout/pago/resumen-pedido.tsx`.

- [ ] **Pantallas de Pago (decisión del dueño: la barra va dentro de Stripe).** Pago se parte en sub-pantallas con **una acción cada una**: **(a) Cómo pagas** (moneda junto al total, forma de pago, promo, deslinde, verificación antibots) → botón «Continuar a la tarjeta», que crea la reserva u orden y retiene; **(b) Tarjeta de cada empresa** → «Pagar $X a [empresa]». La barra inferior de la pantalla (b) se renderiza **dentro de `<Elements>`** (mismo mecanismo de portal que ya usa `TarjetaComoPagas`) para poder llamar a `elements.submit()` y `confirmPayment`; el botón «Pagar» interno de `PaymentForm` se quita. **La barra se monta siempre en el chunk principal** con un botón `principal` deshabilitado y la razón «Cargando el formulario de pago…»; el chunk diferido de Stripe (Task 1.2b) solo aporta el `onClick` por portal, así la barra no brinca mientras baja el formulario.
- [ ] **Presencia de la empresa en el checkout cruza-empresa.** Cada cargo es un renglón: `EmpresaSello` de 32 + nombre de la empresa en 16/600 + línea de servicio en 14 `apagado` + monto en 16/600 `tabular-nums` + estado con ícono y texto (Pendiente `Clock`, Retenido `Lock`, Cobrado `CheckCircle`; colores de estado, nunca de actividad ni un color por empresa); el cargo en curso lleva `borde-control` de 2 px. Encabezado de cada pago: «Pago 1 de 2: a {empresa}»/«Payment 1 of 2: to {company}», y una línea de apoyo «Cada empresa cobra por separado. Este cobro va a la cuenta de {empresa}.»/«Each company charges separately. This payment goes to {company}.» El descriptor que verá el cliente en su estado de cuenta **no se promete** hasta confirmarlo con el dueño.
- [ ] **Casos de servicio nulo y catálogo caído:** pantalla propia con el patrón de la Task 8.3b (`catalogo_caido`).
- [ ] Recorrido con tarjeta de prueba de las cuatro rutas, incluida la de cruza-empresa con rechazo en «Pago 2 de 2». PUNTO DEL DUEÑO.
- [ ] Commit `feat(reserva): la barra de pago vive dentro de Stripe y Pago se parte en dos pantallas`.

### Task 8.4c: Teclado, avisos fijos, cancelar y ayuda flotante

**Files:** Modify `cookie-notice.tsx`, `ayuda-flotante.tsx`, `toast.tsx`, `checkout/pagina-checkout.tsx`, `src/app/globals.css`; usa el `AlertDialog` de la Task 3.5.

- [ ] **«Atrás» tras retener dinero.** Creada la orden, la flecha de arriba pasa a «Cancelar y liberar mi lugar» con un `AlertDialog` (Task 3.5) que explica la consecuencia según el motor: `orden` (cruza-empresa) → «Se libera tu lugar y se revierte lo retenido»; `reserva` (las demás rutas) → «Se libera tu lugar. No se ha cobrado nada.» (la retención previa solo existe en cruza-empresa). La acción segura («Seguir con mi reserva») va primero y recibe el foco; nunca aparece como un «atrás» silencioso. El Atrás del navegador con una orden creada abre este mismo diálogo (Task 8.0 Paso 2).
- [ ] **Teclado, Stripe y antibots.** Mientras un campo tiene el foco (`visualViewport`), la barra fija pasa a estática al final del contenido; los campos de texto usan `enterkeyhint="next"`. El iframe de Stripe y 3DS quedan por encima de la barra (`z-index`). El estado de la verificación antibots forma parte de la razón del botón deshabilitado («Verificando que eres una persona…»). `padding-bottom: env(safe-area-inset-bottom)`.
- [ ] **Aviso de cookies (decisión del dueño, 2026-10-16).** `CookieNotice` es `fixed inset-x-0 bottom-0 z-40` (`cookie-notice.tsx:71`) y la barra (`--z-barra: 50`, ~160 px) lo taparía sin que se pudiera contestar. Por eso **no se muestra en las rutas `reserva-minima`** (`/reservar` y `/traslados`: se reconocen por la misma clase de la Task 8.2); en el resto del sitio se muestra si no se ha contestado. Salvaguarda legal: hoy no hay analítica ni pixel; si se agrega alguno, no se activa hasta el consentimiento (`lib/cookies.ts`), y se revisa que en las rutas de reserva no cargue nada no esencial.
- [ ] **Ayuda flotante y toast.** `AyudaFlotante` (`fixed right-4 bottom-4 z-30`, `ayuda-flotante.tsx:41`) pasa a `bottom: calc(var(--barra-alto) + 16px)` en móvil. Su botón de WhatsApp usa el número único del sitio (`lib/contacto.ts`, `NEXT_PUBLIC_WHATSAPP_NUMBER`) y no se pinta si `tieneWhatsapp` es false. El toast se ancla a `calc(var(--barra-alto) + 8px)` en móvil y conserva `top:` en ≥ 640 px (Task 7.3).
- [ ] Recorrido manual en móvil real (teclado abierto, 3DS, antibots, Atrás del navegador con orden creada) y en escritorio de las cuatro rutas. PUNTO DEL DUEÑO.
- [ ] Commit `feat(reserva): teclado, cookies fuera de la reserva, ayuda flotante y cancelar con confirmacion`.

### Task 8.5a: Módulos puros del calendario: control de fecha y rango de paquete

**Files:** Create `src/lib/rango-paquete.ts`, `src/lib/control-fecha.ts`, `tests/rango-paquete.test.cjs`, `tests/control-fecha.test.cjs`; Modify `tests/run-hub-tests.cjs` (registrar `'control-fecha': ['src/lib/control-fecha.ts', 'CONTROL_FECHA_TEST_OUT']` y `'rango-paquete': ['src/lib/rango-paquete.ts', 'RANGO_PAQUETE_TEST_OUT']`; importan valores solo con ruta relativa, como `calendario-paquete.ts:2`).

> **BookingBar eliminada (2026-10-15, commit `5408d06c`).** Lo que F8 reemplaza es la **tira semanal** de **todas** las páginas de reservar (servicio suelto → `CheckoutCalendar`; paquete de una empresa → `FechaPaquete`; cruza-empresa con traslado → `FechaRegresoCompacta`; traslados → `FechaPaquete` y `FechaRegresoCompacta`): en la reserva, siempre el calendario completo.
> Hallazgos que siguen vigentes: `lib/calendario-paquete.ts` solo calcula fechas; la única fuente de cupo por día es `getCupoRango` (`lib/api.ts:~173-188`, `DisponibilidadRango`: `lleno | sin_panga | sin_lugar | null`), de pangas por empresa y personas, y `useDisponibilidad` la llama **sin `empresaSlug`**. `PeopleStepper` en `checkout-view.tsx:~1500` no recibe `maxPeople` (tope fijo de 5) mientras `traslado-view` usa `capacidad_maxima`; `getCupo` ignora `fecha_salida` en hospedaje; `salidas` (días seguidos de la actividad) no existe en el frontend.

- [ ] **Qué control de fecha usa cada servicio (módulo puro con prueba primero).** `lib/control-fecha.ts`: `controlDeFecha(servicio | paquete | tipoTraslado)` devuelve `fecha_unica`, `rango_llegada_salida` (hospedaje `por_noche` suelto), `rango_fijo_paquete` (paquete con noches fijas) o `ida_y_regreso` (`redondo_aeropuerto`), y si pide hora. Pruebas por tipo de servicio: pesca, paseo/tour, hospedaje, bajo demanda, transporte (`recepcion_aeropuerto`, `redondo_actividad`, `redondo_aeropuerto`), paquete de una empresa y cruza-empresa.
- [ ] **Rango de paquete con noches fijas (función pura con prueba primero):** `rangoDelPaquete(inicio, noches)` sobre `sumarDias` y `nochesDelPaquete`, y `diasSinCupoEnRango(rango, disponibilidad)` que marca solo los días que `getCupoRango` ya declara llenos. Pruebas: N noches, 0 noches, un solo día, un día `lleno` y todos `null`. **No** hay «pocos lugares» ni corte por cupo de hospedaje: el cupo definitivo se valida al pagar (patrón de la Task 8.3b).
- [ ] `tsc`, `eslint`, `npm test`. Commit `feat(reserva): control de fecha por tipo de servicio y rango de paquete, con pruebas`.

### Task 8.5b: `ui/calendario` con estados, leyenda y atajos

**Files:** Create `src/components/ui/calendario/{calendario,leyenda,atajos}.tsx` (`CeldaDia` exportada y usada por la leyenda).

- [ ] **Geometría del calendario:** `grid grid-cols-7` con columnas `minmax(0,1fr)` y padding interior de 8 px con borde de 1 px (328 − 2 − 16 = 310 ≥ 308 de 7 círculos de 44; mínimo 40 en 320 px). La celda es el área táctil y los días se exceptúan expresamente de la regla de 8 px entre objetivos. Se renderizan siempre **6 renglones** (los sobrantes vacíos) para que no cambie de altura al cambiar de mes. `touch-action: pan-y`; el deslizamiento horizontal cambia de mes en 400 ms (solo opacidad con reducir movimiento). Dentro de la tarjeta de paso de ≥ 1024 px no repite borde ni radio; en móvil, sin tarjeta, conserva borde `borde` y `rounded-card`.
- [ ] **Estados de la celda** (`CeldaDia` con prop `estado`, exportada y usada por la leyenda): `disponible` número 16/500 `tinta`, hover `bg-cafe-bruma`; `pasado`/`no_reservable` número `apagado` sin tachado, `aria-disabled` y el motivo en el `aria-label`; `sin_cupo` rayado `repeating-linear-gradient(135deg, transparent 0 4px, var(--color-borde-control) 4px 5px)` con número `apagado` tachado, `aria-disabled` pero **enfocable**, y al tocarlo muestra en línea «Ese día ya no tiene lugar. Elige otro.»; `hoy` anillo `azul` de 2 px hacia adentro (`inset`) y el foco usa `outline` de 2 px con desfase (si coinciden se lee como doble anillo); `seleccion` `bg-cafe text-white`; `vista_previa` `bg-cafe-bruma` con borde discontinuo `cafe` pintado como **banda** del rango (no en cada círculo); `rango` banda `bg-cafe-claro`, número `cafe-profundo`, extremos `bg-cafe text-white`.
- [ ] **Doble toque y anuncio:** el primer toque = vista previa y el segundo confirma **solo** en `rango_fijo_paquete`, `rango_llegada_salida` e `ida_y_regreso`; en `fecha_unica` un toque elige. Hover no anuncia nada a lectores; foco y selección sí, con una región `aria-live="polite"` («Del 7 al 10 de nov · 3 noches»).
- [ ] **Atajos** «Borrar fecha», «Mañana», «En 2 días»: son relativos a hoy y son valores editables; en el rango de ida y regreso, «Borrar fecha» limpia ambos extremos. Van en `flex flex-wrap gap-2`, 44 de alto, sin scroll horizontal (choca con el deslizamiento de mes); «Borrar fecha ×» solo aparece si hay selección; el mínimo de anticipación sale de `getMinBookableDate()` (`lib/dates.ts`); no existe un mínimo por servicio, así que «Mañana» y «En 2 días» solo se deshabilitan, con la razón visible, si la fecha es anterior a ese mínimo.
- [ ] **Interacción de vista previa:** hover, foco o primer toque en móvil = vista previa (`cafe-bruma` + borde discontinuo `cafe`); elegir = rango firme (`cafe-claro`, extremos `cafe`); en móvil el segundo toque en el mismo día confirma.
- [ ] **Leyenda** con los mismos componentes que las celdas: solo los estados que pueden aparecer en ese control (fecha única: Disponible, Sin cupo si se conoce, Tu selección; paquete suma Vista previa y Rango; Hoy solo si el control lo marca), cada uno dibujado con `CeldaDia` a 24 px y `disponible` con anillo `borde` para que el círculo se vea — color **y** forma. En < 640 px la leyenda va en 2 columnas, desde 640 px en una fila, en `texto-pequeno apagado`. Teclado completo (flechas, Re Pág, Av Pág, Inicio, Fin, Esc).
- [ ] Verificación en una ruta temporal `prueba-ui` (no se commitea) y PUNTO DEL DUEÑO en 8.5c. Commit `feat(reserva): calendario completo con leyenda y atajos`.

### Task 8.5c: El calendario en las cuatro rutas

**Files:** Modify `checkout-view.tsx`, `pedido/fecha-paquete.tsx`, `pedido/grupo-viaje.tsx`, `traslado-view.tsx`, `date-field.tsx`, `lib/disponibilidad.ts`, `lib/api.ts`, `tests/run-hub-tests.cjs` (borrar la entrada `'calendario-semana'` de `suites`, línea 15), `frontend/CLAUDE.md` (borrar la mención de la tira semanal y de la suite), `scripts/guardia-estilos.cjs` (quitar la entrada de `checkout-calendar.tsx` de `EXENTOS` al borrarlo); Delete `checkout-calendar.tsx`, `lib/calendario-semana.ts` y `tests/calendario-semana.test.cjs` (cuando ya no tengan usos).

- [ ] **En las cuatro rutas** el paso Viaje monta el calendario completo `ui/calendario` (fondo blanco, borde `borde`, radio 16, sin sombra; días en círculo de 44 px) y desaparece la tira semanal con su enlace «desplegar el calendario completo». `checkout-calendar.tsx` y `lib/calendario-semana.ts` se borran.
- [ ] **Hospedaje suelto `por_noche`:** calendario de rango llegada → salida, con la misma vista previa; la salida manual no se descarta en silencio al cambiar la llegada (hoy `checkout-view.tsx:~229-235`); el cupo se consulta por el rango (verificar antes con el backend si `cupo/rango` responde para hospedaje; si no, el cupo se valida al pagar).
- [ ] **Salidas en varios días del paquete:** se muestran como renglón informativo en el resumen («Actividad: días 2 a 5»); su cupo se valida al pagar con el patrón de aviso. Para eso `PaqueteServicioCatalogo` (`lib/api.ts`) añade el campo `salidas` (el backend ya lo serializa: `fleet/serializers.py:72`).
- [ ] **Bajo demanda:** sin leyenda de «sin cupo» y sin control de hora si no la pide; el texto es **«Reserva confirmada al pagar»** (decisión del dueño). Verificar con el negocio que siempre se puede cumplir.
- [ ] **Carga y error del cupo:** mientras `getCupoRango` carga, los días se ven `disponible` con la línea «Consultando disponibilidad…» (`texto-pequeno apagado`) y nada se marca lleno; si falla, aviso `info` en línea («No pudimos consultar el cupo. Puedes elegir tu fecha y lo confirmamos al pagar») con «Reintentar» (patrón `red` de 8.3b); se precarga el mes siguiente. **Empresa y error en el hook (`lib/disponibilidad.ts`):** `useDisponibilidad(desde, hasta, personas, activo, empresaSlug)` pasa `empresaSlug` a `getCupoRango` (hoy lo llama sin él y consulta siempre `sal-y-sol`) y devuelve `{ dias, cargando, error, reintentar }` (hoy el `catch` traga el error y devuelve `{}`); cada ruta lo llama con el `empresaSlug` del servicio (paquete: `empresa_lider_slug`).
- [ ] `npm.cmd test` pasa sin la suite `calendario-semana`; `guardia` baja (`checkout-calendar.tsx` sale de `boton-crudo` y `radio-crudo`). PUNTO DEL DUEÑO: las cuatro rutas con el calendario nuevo, en móvil real y en escritorio.
- [ ] Commit `feat(reserva): control de fecha por tipo de servicio en las cuatro rutas`.

### Task 8.5d: Personas, regreso vacío, estimado de hospedaje y limpieza de USD

**Files:** Modify `people-stepper.tsx`, `checkout-view.tsx`, `traslado-view.tsx`, `pedido/pedido-paquete.tsx`, `frontend/CLAUDE.md`.

- [ ] **Traslado `redondo_aeropuerto`:** **un solo calendario de rango** ida y regreso. La fecha de regreso es **obligatoria y vacía** (decisión del dueño): se elimina el prellenado `diaSiguiente(minDate)` de `traslado-view.tsx:~152`; el `CLAUDE.md` del frontend ya decía «no se prellena».
- [ ] **Personas:** `PeopleStepper` recibe `maxPeople` desde `capacidad_maxima` del servicio (de cada servicio en paquete) en las cuatro rutas. Visual: dos botones circulares `secundario` de 48 con el valor en 20/600 entre ellos; al tocar el tope se explica en línea «Máximo N personas» en lugar de ignorar el toque.
- [ ] **Precio de hospedaje por noche:** el resumen antes de crear el pago usa la estrategia del servidor (noches × precio) y se rotula «Estimado»; la etiqueta de la barra sigue la regla de la Task 8.4a.
- [ ] **Limpieza por USD derivado:** los precios en USD se derivan del tipo de cambio de la sede (siempre existen). Verificar en el backend que ninguna respuesta lleva USD vacío y **borrar** del frontend el estado «extra sin precio USD» (`pedido === null` en `pedido-paquete.tsx:~876`, que hoy oculta todo el panel) y su texto en `frontend/CLAUDE.md`.
- [ ] Commit `fix(reserva): regreso vacío, tope de personas del servicio y rango de hospedaje`.

### Task 8.7: Verificar que los documentos de diseño coinciden con lo construido (se corre antes de 8.6)

> Los documentos ya se sincronizaron con este plan el 2026-10-16 (decisión del dueño): `design-guidelines.md:70` y `design-components.md:96` describen la línea de progreso como `<ol>` con `aria-current="step"` y el texto «Paso 2 de 3: Tus datos», no `role="progressbar"`; `design-components.md:102` pide la fila del asa de 48 con píldora visual de 40; la sección «Pago» describe las sub-pantallas (a) «Continuar a la tarjeta» y (b) «Pagar $X a [empresa]», con la barra de (b) dentro de `<Elements>`. Esta tarea solo comprueba que lo construido sigue coincidiendo.

- [ ] `grep -rn "progressbar" docs/design src` no devuelve nada que describa la línea de progreso; el asa mide 48 de alto; Pago tiene dos sub-pantallas con un botón cada una. Si el código se separó de los documentos, se corrige el documento o el código y se anota el motivo en el commit. Commit solo si hubo cambios: `docs(design): documentos alineados con la pagina de reserva`.

### Task 8.6: Cierre de F8 y lanzamiento conjunto

- [ ] `verificar` completo y los **recorridos manuales de F5 más los de F8**, en escritorio **y** móvil real, es y en, con tarjeta de prueba de Stripe: servicio suelto de **pesca**, **paseo**, **hospedaje por noche**, **bajo demanda**; paquete de una empresa (con noches y con salidas en varios días); paquete cruza-empresa con rechazo en «Pago 2 de 2»; los tres tipos de traslado (el de ida y regreso con fecha de regreso vacía); y los casos: Atrás y Adelante del navegador, recargar en cada paso, cambio de idioma a media compra, entrada con query y desde «Continuar reservación», apartado vencido, sin cupo al pagar, red caída, servicio nulo, teclado abierto con barra fija. PUNTO DEL DUEÑO.
- [ ] Ramas: `feat/frontend-base` lleva F0-F6 (no cambia el aspecto) y se fusiona a `main` al cerrar F6; `feat/marca-sun-baja` nace de esa rama, lleva F7-F9 y se fusiona y despliega de una sola vez (un solo merge y un solo deploy de F7 + F8 + F9; F9 se cierra en su propia Task 9.7 y sale en el mismo lanzamiento). Si falla algo, se revierte el merge completo.

---

## F9 — Contenido y estructura de hub y sede (sale con F7 y F8)

> **Fuente:** `docs/marketing/diagnostico-y-plan-contenido.md` (diagnóstico de `marketing-skills:cro` y `site-architecture`), `docs/marketing/analisis-competidores.md`, `docs/marketing/contenido-empresas.md` y `.agents/product-marketing.md`. **Decisiones del dueño (2026-10-16):** el hub explica la dinámica real (una empresa que reúne servicios de distintas empresas en un solo lugar; cada una opera y cobra directo) y lista **todas** las empresas con enlace a su página oficial y redes; el catálogo de La Ventana Travel cargado es lo que el cliente quiere mostrar; Sal y Sol ya tiene información e imágenes correctas; las reseñas de las empresas pueden usarse **atribuidas y confirmadas por cada empresa**.
>
> **Reglas de la fase (de `cro`):** (1) un propósito por página: hub = elegir sede, sede = reservar; (2) **ninguna sección dice «pronto»**: si no hay contenido real, no se pinta; (3) nada falso: sin reseñas de ejemplo, sin escasez inventada, sin contacto de relleno; (4) el pago, la cancelación y el clima van junto al producto; (5) **lo que incluye un servicio es de ese servicio**, nunca una promesa general; (6) es y en con el mismo orden y peso; (7) **movimiento bajo**: sin revelado al hacer scroll en precios ni políticas (`.rev` solo en el título del héroe de la sede), solo hover, foco y presionado de 150 ms, acordeón de 250 ms y fundido de imágenes; con reducir movimiento, solo opacidad. **Decisiones del dueño ya tomadas (2026-10-16), que el implementador no reabre:** titular del hub «Reserva en Baja California Sur con las empresas locales»; nombre del sitio «Sun Baja Experience» (la confirmación final solo queda pendiente en el rebrand de cadenas, Task 9.3 Paso 4); bloque de pago «Reserva con tranquilidad»; héroe del hub con video del dueño; `webConfirmada` verdadero para DLS Transporte, La Ventana Travel y Piratas Adventures (Sal y Sol sin enlace externo: su sitio es este); reembolso por mal clima y cambio de fecha con 48 h iguales en las 4 empresas, y **no hay otra protección aparte de esas dos**; los servicios y paquetes llevan foto (hardcodeada por ahora); cada sede es una colaboración entre Sun Baja Experience y la empresa local protagonista; el descriptor del estado de cuenta no se promete hasta que el dueño lo copie del dashboard de Stripe de cada empresa.
>
> **Skills al ejecutar:** `perception-first-design` para decidir jerarquía y orden; `marketing-skills:copywriting` para los textos; `design-taste-frontend` para diseñar cada componente nuevo (con los 3 documentos de `docs/design/`); las skills de Vercel al escribir código. Nada visible se programa sin la luz verde del dueño (PUNTO DEL DUEÑO).

### Task 9.0: Datos de las empresas y secciones condicionales (módulo puro, prueba primero)

**Files:** Create `src/content/empresas.ts`, `tests/empresas.test.cjs`, `src/content/imagenes-catalogo.ts`, `tests/imagenes-catalogo.test.cjs`, `public/catalogo/*.webp`, `src/lib/secciones-sede.ts`, `src/lib/etiquetas-catalogo.ts`, `tests/secciones-sede.test.cjs`, `tests/etiquetas-catalogo.test.cjs`, `tests/contenido-paridad.test.cjs`; Modify `tests/run-hub-tests.cjs` (registrar las suites: `'secciones-sede'`, `'etiquetas-catalogo'`, `'imagenes-catalogo'` y `empresas: ['src/content/empresas.ts', 'EMPRESAS_TEST_OUT']`), `package.json` (`test:contenido`), `src/content/sedes-tipos.ts`, `src/content/sedes-cuerpo.ts`, `lib/api.ts` (tipo `incluye`); backend: `fleet/models.py`, `serializers.py`, `admin.py`, migración y `tests_incluye.py`.

- [ ] **Paso 1:** `empresas.ts` (`import 'server-only'`) exporta, por empresa (`sal-y-sol`, `transporte-la-paz`, `la-ventana-travel`, `piratas-adventures`): nombre, sede, `descripcion` es/en, `web?`, `redes[]`, `contacto?` (**solo teléfono o WhatsApp confirmados**; sirve únicamente para mostrar el teléfono de esa empresa en su fila cuando esté confirmado; el botón «Escribirnos por WhatsApp» del sitio usa el número único de `lib/contacto.ts`, no este), `tambienConocidaComo?` (el nombre comercial de su sitio cuando difiere del catálogo: «DLS Tours y Transporte Turístico» frente a «DLS Transporte»; «La Ventana Adventures» frente a «La Ventana Travel»), `webConfirmada`, `logo?`, `resenas[]` (`autor`, `texto`, `fuente` con URL, `fecha`, `idioma` ('es' | 'en'), `confirmada: boolean` que arranca en `false`) y `fotos[]` (`src`, `alt`, `propia: boolean`). **`webConfirmada` (decisión del dueño, 2026-10-16):** `true` para DLS Transporte, La Ventana Travel y Piratas Adventures; Sal y Sol **sin** enlace externo (su sitio es este: no lleva `web`). El dueño decide así sabiendo que el sitio de La Ventana lista otras actividades (buceo, kayak, paddle board…) y que el de Piratas es un borrador en `vercel.app`, y se compromete a tenerlos al día antes de lanzar (dependencia en 9.7). Se llena con `docs/marketing/contenido-empresas.md`; Sal y Sol, con su información ya correcta. **Quedan fuera hasta que la empresa los confirme:** el WhatsApp +52 612 123 4567 de Piratas, los enlaces de privacidad y términos que van a `#`, las reseñas de plantilla (la de La Ventana de 2018, las 5 de DLS) y las fotos de Pexels o Unsplash. Textos de descripción con `marketing-skills:copywriting`, tono tomado de Piratas.
- [ ] **Paso 1b: «qué incluye» es un campo `incluye` (decisión del dueño, 2026-10-16; sin alternativa).** Hoy `incluye` no existe ni en el backend (`Servicio` no tiene el campo; `ServicioSerializer` no lo expone) ni en `ServicioCatalogo` (`lib/api.ts`, que solo trae `descripcion`, texto libre). Backend, con `tests_incluye.py` primero: `incluye = models.JSONField(default=dict, blank=True)` en `Servicio` y `Paquete` con forma `{"es": [..], "en": [..]}` (máx. 8 renglones de ≤ 80 caracteres cada uno, validado en `clean()`: objeto con solo las claves `es` y `en`, listas de textos no vacíos); `ServicioSerializer` y `PaqueteSerializer` lo exponen; en el admin, el formulario muestra dos cuadros de texto, `incluye_es` e `incluye_en` (un renglón por línea), que se guardan en el JSON; migración sin datos. Frontend: tipo `incluye?: { es: string[]; en: string[] }` en `lib/api.ts`. **Paquetes:** si un paquete tiene `incluye` vacío, la tarjeta muestra la unión ordenada de los `incluye` de sus `servicios_asociados`, cada renglón prefijado con el nombre del servicio. **La página de detalle** (`servicio/[empresa]/[servicio]/page.tsx`) pinta la misma lista (hoy solo pinta `IncludedSection` para pesca de Sal y Sol: `{pesca && …}`; los demás servicios llegaban a una página sin «Incluye», contra la regla 5). Mientras la lista esté vacía, la tarjeta muestra «Pregunta qué incluye» con el enlace de contacto. **Nunca se deriva de `descripcion`.** Dependencia del dueño: escribir las listas es/en de cada servicio (9.7).
- [ ] **Paso 1c (esquema, antes de escribir datos): una sola fuente de empresa.** `SedeOtraEmpresa` (`sedes-tipos.ts`) ya tiene `descripcion`, `enlaceExterno`, `logo` y `redes`, y `SedeIndiceEntry` tiene `web` y `redes`: no se duplican. `empresas.ts` es la ÚNICA fuente (nombre, `descripcion` {es,en}, `web`, `redes`, `contacto?`, `logo`, `resenas`, `fotos`); en `sedes-cuerpo.ts`, `otrasEmpresas` pasa a `string[]` de slugs y se eliminan `descripcion`, `enlaceExterno`, `logo` y `redes` de `SedeOtraEmpresa`; `ColaboradoresSection` lee de `empresas.ts`. `SedeIndiceEntry` sustituye `empresaFundadoraNombre` y `logo` por `empresaProtagonistaSlug` (la empresa fundadora de la sede, que da nombre y logo a la segunda marca de la cabecera: Task 9.1a); el nombre y el logo se leen de `empresas.ts`. **Supuesto a confirmar por el dueño:** en La Paz la protagonista es Sal y Sol y DLS aparece como empresa de la sede (en «Quién opera cada servicio»), no en la cabecera. Se añaden a `SedeCuerpoContenido` (por idioma, como el resto del cuerpo) `galeria?: {src, alt, ancho, alto, empresaSlug}[]`, `temporadas?` y `faq?: {q, a}[]`; `dict.season`, `dict.gallery` y `dict.faq.items` salen del diccionario global y La Paz los recibe de su cuerpo.
- [ ] **Paso 1d: etiquetas del catálogo (módulo puro con prueba primero).** `src/lib/etiquetas-catalogo.ts`: `actividadDe(servicio): 'mar' | 'ciudad' | 'outside' | null` — `pesca`→`mar`; `paseo`→ por mapa explícito `ACTIVIDAD_POR_SERVICIO[slug]` (por defecto `mar`); `hospedaje`, `transporte` y `bajo_demanda`→`null` (grupo «Estancia y traslados»). `actividadDePaquete(paquete)` → la actividad común de todos sus `servicios_asociados`, o `null` si difieren; los paquetes con `null` van en el grupo «Paquetes»/«Packages» (encabezado con `Package` de 20, primero en el bloque, chip `neutro`). `baseDeCobro(estrategia_precio, lang)`: `por_persona`→«por persona», `por_grupo`→«por grupo», `por_noche`→«por noche», `tarifa_fija`→«tarifa fija», `por_ruta`→«según ruta» (esta última sin «desde»). **No existe «por barco» en el backend.** Pruebas por cada valor y en es/en. **Chips:** `ChipActividad` acepta `tipo: 'mar' | 'ciudad' | 'outside' | 'neutro'` (Tasks 3.3 y 7.3). `etiquetaActividad(servicio, lang)` devuelve una sola palabra por tipo (pesca = «Pesca»/«Fishing», paseo = «Paseos»/«Tours», hospedaje = «Hospedaje»/«Lodging», transporte = «Traslados»/«Transfers», paquete sin familia = «Paquetes»/«Packages»); el color sale de `actividadDe` (`azul-claro`/`azul`, `coral-claro`/`coral-texto`, `verde-claro`/`verde`) y los tipos sin familia usan el chip `neutro` (fondo `cafe-bruma`, texto `tinta-suave`, 8,68:1, íconos `Bed`, `Van` o `Package`). **Tarjeta de sede del hub:** hasta 3 chips en orden fijo Pesca, Paseos, Hospedaje, Traslados, Paquetes; el resto se omite; fila `flex-wrap gap-2`, sin truncar. **`TarjetaServicio` de la sede:** el chip de actividad solo si `actividadDe` ≠ null; el grupo «Estancia y traslados» lleva el encabezado y no chip.
- [ ] **Paso 1e: funciones puras de presentación (con prueba primero), en `etiquetas-catalogo.ts`.** `tarjetasConFoto(sedes): boolean` (verdadero solo si **todas** las sedes activas tienen foto propia, es decir, `hero.imagen` que no esté en `/ilustraciones/`: si una no la tiene, ninguna tarjeta de sede del hub muestra foto); `fotosAptas(fotos)` (omite toda foto con lado largo menor de 800 px; el slot grande exige 1200 px o más; **imagen de héroe: ancho ≥ 1600 px, si no se usa con `object-position` y el dueño lo aprueba en el PUNTO** —las 9 fotos de La Paz miden 1086×1448 o 1448×1086 y se ampliarían ~1,33× a 1440 px—; con menos de 3 aptas no hay galería); `plantillaDeGrupo(n)` (n=1 una tarjeta ancha horizontal de máx. 720; n=2 dos columnas; n=3 una destacada a 2 columnas + una normal sin celdas vacías; n=4 2×2; n=5 destacada + 1, luego 1+1+1; n≥6 tres columnas). `iniciales(nombre)` vive en `lib/iniciales.ts` (Task 3.7). Pruebas por cada caso.
- [ ] **Paso 1f: fotos del catálogo, hardcodeadas por ahora (decisión del dueño, 2026-10-16: prioridad lanzar).** Los servicios y los paquetes **llevan foto**. `src/content/imagenes-catalogo.ts` exporta un mapa `clave → { src, alt: { es, en } }` con la clave del view-model de la tarjeta (`servicio:<empresa>/<slug>`, `paquete:<slug>`) y la función `imagenDeCatalogo(clave, lang)` que devuelve `{ src, alt }` o `null`. Las fotos son WebP en `public/catalogo/`, de ≤ ~200 KB cada una, y se pintan con `next/image`. **Sin campo de imagen en el backend, sin R2 y sin migración:** más adelante se migra a la foto del admin cambiando solo esta función; la tarjeta no se toca. Cambiar una foto exige un deploy (costo aceptado). Pruebas (`tests/imagenes-catalogo.test.cjs`, con `fs`, sin runner): todo servicio y paquete del catálogo (las claves de `seed_catalogo_real.py` más las de Sal y Sol) tiene foto en el mapa; cada `src` existe en `public/` y pesa ≤ 200 KB; cada `alt` tiene es y en. En desarrollo, `imagenDeCatalogo` avisa por consola si se le pide una clave sin foto. **Regla «todas o ninguna» por grupo:** si a algún elemento de un grupo le falta la foto, ningún elemento de ese grupo se pinta con foto (la fila no queda dispareja); `fotosDeGrupo(elementos): boolean` es función pura con su prueba. No se usa la foto de una empresa como sustituto (mostraría una panga en una tarjeta de hospedaje). Dependencia del dueño (9.7): fotos de La Ventana, Puerto Chale y DLS (hoy solo hay de Sal y Sol, en `public/photos`).
- [ ] **Paso 2: prueba primero.** `secciones-sede.ts` exporta `seccionesDeSede({ servicios, paquetes, empresas, resenas, fotos, faq, temporadas })` → `{ id: SeccionId; estado?: 'normal' | 'vacio' | 'catalogo_caido' }[]`, ordenada. Pruebas: ambas listas `null` → `reservar` con `catalogo_caido`; ambas `[]` → `reservar` con `vacio`; alguna con elementos → `normal`; sin reseñas confirmadas **no hay** sección de opiniones (ni fila ni sustituto); una sección sin contenido no aparece (nunca un id de «pendiente»); el orden es el de la sede (hero, reservar, tranquilidad, empresas, galería, temporadas, opiniones, preguntas); la misma función sirve a es y en. «Cómo llegar» y el cierre quedan fuera de este plan hasta que existan datos (punto de encuentro por servicio y CTA final); si el dueño los quiere ya, se añade una Task 9.8 con su componente y su dato. **Reglas del módulo:** `secciones-sede.ts` solo importa **tipos** (`import type` de `@/lib/api` y `@/content/*`; un import de valor con `@/` revienta en el runner igual que advierte la Task 3.2) y no importa `empresas.ts` (es `server-only`: la página le pasa los datos). Exporta además `ANCLA_DE: Record<SeccionId, string>` y `enlacesDeSede(ids): { ancla: string; claveNav: string }[]`; las etiquetas salen de `dict.nav` (añadir `reservar`, `empresas`, `galeria`, `temporadas`, `opiniones`, `preguntas` donde falten). Se usan en la Task 9.1a. **Pruebas de contenido:** `tests/contenido-paridad.test.cjs` (solo `fs`, se corre con `node --test`) compara las claves de `es.json` y `en.json`; `tests/empresas.test.cjs` (suite registrada en `run-hub-tests.cjs`) crea el stub de `server-only` igual que `tests/content-sedes-cuerpo.test.cjs:13-17` y comprueba `descripcion.es` y `descripcion.en` por empresa, `confirmada === false` por defecto en las reseñas y que Sal y Sol no tiene `web`. En `package.json`: `"test:contenido": "node --test tests/contenido-paridad.test.cjs"`, y se añade a `verificar` (F6).
- [ ] **Paso 2b: diccionario de la sede.** Crear `dict.sedeContenido` en es y en (`queReservar`, `tranquilidad`, `colaboracion`, `empresas`, `opiniones`, `galeria`, `faq`): hoy solo existe `dict.hubContenido` para el hub y el copy de la sede no tiene espacio de nombres. Las claves huérfanas que `tsc` no ve se borran en la Task 9.7.
- [ ] **Paso 3:** `tsc`, `eslint`, `npm test`. Commit `feat(contenido): datos de empresas y secciones de sede condicionales`.

### Task 9.1a: Sede — orden de la página, dos marcas y anclas

**Files:** Create `src/components/banda-colaboracion.tsx`; Modify `app/[lang]/sede/[slug]/page.tsx`, `app/[lang]/servicio/[empresa]/[servicio]/page.tsx`, `site-header.tsx`, `site-footer.tsx`, `src/content/sedes-tipos.ts`, `dict.nav` y `dict.sedeContenido` es/en.

- [ ] **Paso 1: la página pinta solo lo que devuelve `seccionesDeSede`.** Orden: héroe → **«Qué puedes reservar»** → «Reserva con tranquilidad» (9.2) → empresas → galería → temporadas → opiniones (9.5, solo si hay reseñas confirmadas) → preguntas. «Acerca de» deja de ser una sección independiente: su texto pasa a la tarjeta de cada empresa. **Fondos:** el ritmo **no** se logra con el tono (arena contra blanco es 1,07:1 y contra `cafe-bruma` 1,10:1: las bandas son casi invisibles). Reglas: (a) toda banda salvo la primera lleva `border-t border-borde`; (b) las secciones con tarjetas (`reservar`) van en `arena`; (c) las secciones sin tarjetas (`empresas` como filas, `galeria`, `preguntas`) pueden ir en `blanco`; (d) `tranquilidad` va en `cafe-bruma` con contenido sin tarjetas; (e) si una `Card` cae en banda `blanco`, usa `bg-arena`; (f) nunca dos secciones adyacentes con el mismo fondo, calculado sobre las **secciones pintadas** (la página asigna el fondo por posición, no un valor fijo por sección). El ritmo real lo dan las familias de layout distintas: tarjetas, rejilla de iconos, filas de directorio, mosaico de fotos y acordeón.
- [ ] **Paso 2: dos marcas y la frase de colaboración (decisión del dueño, 2026-10-16).** Cada página de sede deja claro que es una colaboración entre «nosotros» (Sun Baja Experience, agencia de turismo local) y la empresa local protagonista. Esto **reemplaza** la propuesta de que el encabezado llevara siempre solo la marca nuestra. (a) **Cabecera de la sede:** dos marcas, el monograma «SB» (o el logo definitivo) de Sun Baja Experience y, a su lado y separada por una línea vertical de 1 px `borde`, el `EmpresaSello` de 32 de la empresa protagonista (la fundadora: `empresaProtagonistaSlug` de la sede; nombre y logo salen de `empresas.ts` y llegan a `SiteHeader` como prop serializable `marcaSede?: { nombre, logo }`). Hoy `brandMain` usa `empresaFundadoraNombre` y el logo de la empresa; ambos se sustituyen. (b) **Hub y páginas fuera de una sede** (`/`, servicio, traslados, deslinde, privacidad, `not-found`): solo la marca nuestra. El checkout con dos empresas lleva solo la nuestra (Task 8.2). El pie lleva siempre solo la nuestra. (c) **Frase visible** en `banda-colaboracion.tsx` (Server Component): una franja delgada justo debajo del héroe, sin `h2` y sin entrar en `ANCLA_DE`, en `texto-pequeno tinta-suave` sobre `arena`, con el `EmpresaSello` de 24 de la protagonista: «Una colaboración entre Sun Baja Experience, agencia de turismo local, y {empresa}» (en: «A collaboration between Sun Baja Experience, a local travel agency, and {empresa}»). Las demás empresas de la sede (en La Paz, DLS Transporte) no van en la cabecera ni en la frase: aparecen en «Quién opera cada servicio». *Supuesto a confirmar por el dueño: en La Paz la protagonista es Sal y Sol.*
- [ ] **Paso 3: anclas (una sola fuente).** Los enlaces con ancla viven en `site-header.tsx` (líneas ~96-107), `site-footer.tsx` (~20-31 y ~58), `sede/[slug]/page.tsx` (`hrefVerTodo` con `'experiencias'`), `servicio/[empresa]/[servicio]/page.tsx` (`hrefSede(..., 'servicios')`), y los `id` en `hub-por-que.tsx`, `about-section.tsx` y `colaboradores-section.tsx`. `SiteHeader` y `SiteFooter` también salen en `servicio`, `traslados`, `deslinde`, `privacidad` y `not-found`, donde `seccionesDeSede` nunca se calcula. Por eso: `ANCLA_DE` y `enlacesDeSede(ids)` (Task 9.0) son la única fuente; `SiteHeader` y `SiteFooter` reciben una prop serializable opcional `anclas?: { ancla, etiqueta }[]` que arma la página de sede con `enlacesDeSede(seccionesDeSede(...))` y las etiquetas de `dict.nav` (por `claveNav`). **Sin la prop** (servicio, traslados, deslinde, privacidad, not-found) solo muestran el enlace «Reservar» a `hrefSede(lang, slug)` sin ancla. Hub: ids fijos `mapa`, `sedes`, `como-funciona`, `empresas`, migrando header, footer, `page.tsx` y la CTA de 9.3 en el mismo commit. Los enlaces literales a `#galeria` o `#empresas` se construyen con `'#' + ANCLA_DE.galeria` y `'#' + ANCLA_DE.empresas`. Pruebas: `enlacesDeSede` solo devuelve anclas de secciones presentes, y `grep -rnE "#(nosotros|experiencias|servicios|temporadas|galeria|resenas|preguntas|colaboradores|hub-mapa-destinos)" src` queda en 0 salvo `ANCLA_DE`.
- [ ] **Paso 4:** `tsc`, `eslint`, `npm test`, `build`, `guardia`. PUNTO DEL DUEÑO: las dos marcas de la cabecera y la frase en La Paz y en una sede sin DLS, en es y en, en 360 px y en escritorio. Commit `feat(sede): dos marcas, frase de colaboracion y anclas de una sola fuente`.

### Task 9.1b: Sede — «Qué puedes reservar», con foto y catálogo caído

**Files:** Create `src/components/que-puedes-reservar.tsx`, `src/components/tarjeta-servicio.tsx`; Modify `app/[lang]/sede/[slug]/page.tsx`, `src/components/sede-hero.tsx`, `app/[lang]/servicio/[empresa]/[servicio]/page.tsx` (la lista de `incluye`); Delete `sede-pending-section.tsx` (y su texto `destination.pendingBody`), `about-section.tsx`, `paquete-card.tsx` y `servicios-sueltos-section.tsx` (único importador: `sede/[slug]/page.tsx`) y las claves de `dict.catalog` que solo ellos usan (`servicesComingSoon`, `emptyPackages`).

- [ ] **Paso 1: catálogo caído.** `getPaquetesSede` y `getServiciosSede` se devuelven como `null` en caso de error (hoy `.catch(() => [])` mezcla «sin productos» con «catálogo caído»). Si ambos son `null`, `seccionesDeSede` incluye `reservar` con estado `catalogo_caido` y se pinta con `AvisoEstado` tono `error`: título «No pudimos cargar el catálogo» y las acciones «Reintentar» (`<a href>` a la misma URL) y, **solo si `tieneWhatsapp`**, «Escribirnos por WhatsApp» (número único del sitio, `lib/contacto.ts`; sin número el botón no se pinta y queda solo «Reintentar»). Si las listas llegan **vacías** (no caídas), el bloque `reservar` muestra un estado vacío compuesto —ícono `Boat` o `Van` regular de 32 en `apagado`, «Por ahora esta sede no tiene servicios para reservar en línea» y, si `tieneWhatsapp`, un botón secundario «Escribirnos por WhatsApp»—. Ninguno de los dos usa la palabra «pronto». `SedeHero` recibe `paquetes ?? []` y `servicios ?? []` (con `null` revienta). El bloque estático de DLS de `sede/[slug]/page.tsx:57-65` (`servicioTransporte`) se elimina si la API ya devuelve `traslados-la-paz`; si no, `QuePuedesReservar` lo proyecta como un `servicio` más. Esqueleto de la sede: héroe + 3 tarjetas con `min-h-[420px]`. La página espera ese `Promise.all` **antes** de renderizar (no hay `<Suspense>` sobre la lista de secciones, porque las anclas dependen de ella); el `loading.tsx` de la sede (Task 1.4) es un esqueleto genérico de héroe + una tarjeta, no la estructura final.
- [ ] **Paso 2: «Qué puedes reservar».** Servicios y paquetes **en un solo bloque**, agrupados con `actividadDe` y `actividadDePaquete` (Task 9.0, Paso 1d: «Pesca», «Paseos», «Estancia y traslados» y «Paquetes»). Es un **Server Component** nuevo (`que-puedes-reservar.tsx`) que proyecta en servidor cada servicio y paquete a un view-model mínimo `{ clave, nombre, empresa, actividad, foto, base, desdeTexto, incluye[], href, hrefDetalle }` y lo pinta con `<Link>` y `botonClases`: `paquete-card.tsx` y `servicios-sueltos-section.tsx` eran `'use client'` y recibirían objetos completos de la API (`personalizaciones`, `servicios_asociados`) en el payload. `key` única (`servicio:<empresa>/<slug>`, `paquete:<slug>`), nunca el índice. Cada tarjeta muestra: la foto, la empresa que lo opera, `baseDeCobro` con «desde» y la moneda, y **su propia lista de qué incluye** (campo `incluye`, Task 9.0 Paso 1b; si está vacía, «Pregunta qué incluye» con el enlace de contacto; nunca se inventa ni se deriva de `descripcion`). Un bloque vacío (p. ej. «sin paquetes») no se pinta. **Tarjeta (`TarjetaServicio`, Server Component, el mismo para servicio y paquete).** **Con foto** (decisión del dueño, 2026-10-16, que revierte la regla anterior de «tarjeta sin foto»): `imagenDeCatalogo(clave, lang)` (Task 9.0, Paso 1f) con `next/image`, y la regla «todas o ninguna» por grupo (`fotosDeGrupo`) para que la fila no quede dispareja. `Card` plana (`bg-superficie`, borde `borde`, `rounded-card`, sin sombra, padding 24), de arriba abajo: (0) foto a sangre arriba, 16:10, `rounded-t-card`, `alt` descriptivo del mapa, `sizes` correcto, `loading="lazy"` salvo las dos primeras; (1) chips de `etiquetaActividad` en el cuerpo (nunca flotando sobre la foto), (2) título `texto-paso`, (3) renglón de empresa con `EmpresaSello` de 24 y «Opera [empresa]» en 14/600 `tinta-suave`, (4) «Incluye» en 14/600 y hasta 3 renglones de 14/400 con ícono `Check` en `cafe` (no verde: el verde es de éxito y de outside; si hay más, «+N más» como texto), (5) precio con moneda visible: «desde» 14 `apagado`, monto 20/700 `tabular-nums` («$4,100 MXN») y base 14 `apagado`; en `/en`, «$228 USD» primero y «≈ $4,100 MXN» debajo en `texto-pequeno apagado` (los precios nunca van en color de actividad), (6) **un solo** `Link` secundario «Ver y reservar» a `hrefDetalle` (el flujo directo `href` queda en el héroe de la sede). Toda la tarjeta es clicable con enlace estirado (`after:absolute after:inset-0`) y `aria-label="Ver y reservar: {nombre}, {empresa}"`. Foco: `has-[a:focus-visible]:outline-2 outline-ring outline-offset-2`; hover (solo puntero): borde `borde-control` y capa `--capa-hover`; presionado `scale-[0.99]` en 150 ms. `por_ruta`: «Tarifa según ruta» en 16/600 (no con estilo de monto) y el CTA dice «Elegir ruta»/«Choose route». **Composición del bloque:** por cada grupo con contenido, un encabezado `texto-subtitulo` con el ícono de su familia de 20 px (sin chip en «Estancia y traslados»), y la rejilla de `plantillaDeGrupo(n)` (Task 9.0, Paso 1e); la destacada es la primera de `destacadas` y lleva «Incluye» en una columna lateral; en 768 px, dos columnas y la última ocupa 2 si el número es impar; en 360 px, una. **Página de detalle:** la misma lista `incluye` y la misma foto. Copy es/en: «Qué puedes reservar»/«What you can book»; subtexto «Cada servicio muestra qué empresa lo opera, cuánto cuesta y qué incluye.»/«Each service shows which company runs it, what it costs and what it includes.»; «por persona/por grupo/por noche/tarifa fija/según ruta» y «per person/per group/per night/flat rate/depends on route»; «Incluye»/«Includes»; «+2 más»/«+2 more»; «Pregunta qué incluye»/«Ask what is included». Los textos viven en `dict.sedeContenido` (`queReservar`).
- [ ] **Paso 3:** `tsc`, `eslint`, `npm test`, `build`, `guardia`. **PUNTO DEL DUEÑO:** mirar La Paz (completa) y La Ventana y Puerto Chale (sin «pronto»; sin fotos propias de catálogo la regla «todas o ninguna» las deja sin foto), en es y en, en 360 px y en escritorio. Commit `feat(sede): producto primero con foto y solo secciones con contenido real`.

### Task 9.1c: Sede — galería de fotos

**Files:** Modify `gallery-section.tsx`, `season-section.tsx`.

- [ ] **Paso 1: galería de la sede.** `galeria` pasa por `fotosAptas` (Task 9.0, Paso 1e). Layout en contenido (máx. 1120), no a sangre: `columns-2` en móvil y 768 px y `columns-3` desde 1024 px, `gap-3`, `break-inside-avoid`, cada foto en su proporción real con `rounded-card`, sin lightbox (la foto no es enlace). Si hay más de una empresa en la galería, pie de 14 `apagado` con `EmpresaSello` de 24 + nombre **debajo** de la foto, no sobre ella. `loading="lazy"` salvo las dos primeras, `sizes` correcto, `alt` descriptivo y específico («Capitán sostiene un dorado en la bahía de La Paz»), nunca el nombre del archivo; entrada solo con fundido de opacidad de 250 ms al cargar. **Una foto no se repite en la misma página** (héroe, tarjetas de servicio, galería, temporadas, empresas): la galería omite las fotos que ya usan el héroe o las tarjetas, y `season-section` usa las fotos que la galería no use, o no lleva foto. Título «Fotos de los viajes»/«Photos from the trips».
- [ ] **Paso 2:** `tsc`, `eslint`, `npm test`, `build`, `guardia`. PUNTO DEL DUEÑO. Commit `feat(sede): galeria con reglas de calidad`.

### Task 9.2: «Reserva con tranquilidad» (`ReservaTranquila`)

**Files:** Create `src/components/reserva-tranquila.tsx`; Modify dictionaries es/en (`dict.sedeContenido.tranquilidad`).

- [ ] **Paso 1: dato real del modo de pago.** El modo está en el **servicio** (`permite_anticipo`, `porcentaje_anticipo` en `fleet/models.py`), no en la empresa. `ServicioCatalogo` y `PaqueteCatalogo` (`lib/api.ts`) ya traen `permite_anticipo` y `porcentaje_anticipo`, y el serializador (`apps/fleet/serializers.py`) los expone (verificado en la ronda 7): no hay nada que añadir.
- [ ] **Paso 2: contenido.** (a) Cómo se paga: el modo que aplica a los servicios de la sede, con un ejemplo calculado con el precio real del servicio destacado («{porcentaje} % ahora, $X MXN / $Y USD, y el resto en efectivo el día del viaje», donde `{porcentaje}` es el `porcentaje_anticipo` de ese servicio, no un número fijo; sin ejemplo si no hay precio); (b) cancelación y clima: reembolso completo por mal clima; (c) cambio de fecha con 48 h; (d) la nota «lo que incluye varía por servicio». Ningún texto promete equipo ni amenidades en general. **La política es una sola para las 4 empresas** (decisión del dueño, 2026-10-16): un solo texto, sin rama por empresa y sin otra protección aparte; la protección es el reembolso completo por mal clima y el cambio de fecha con 48 h.
- [ ] **Paso 3: diseño.** **Sin `AvisoEstado` ni `Card` anidada** (cuatro cajas de color con íconos de estado leerían como alarma y como letra chica a la vez, y `info` comparte fondo con el chip de mar). Banda de fondo `cafe-bruma` con `border-t border-borde`; dentro, 4 puntos en rejilla de 2 columnas desde 768 px (1 columna por debajo), separados por espacio (gap 32), sin bordes ni cajas. Cada punto: ícono Phosphor `regular` de 24 en `cafe` (no `cafe-medio`: 2,69:1 no alcanza 3:1) **sobre** el título, título 20/600 (`texto-subtitulo`) y texto 16 en `tinta-suave` (`texto-cuerpo`), máximo 60 caracteres por línea. Íconos: `CreditCard` (pago), `CloudRain` (clima), `CalendarCheck` (cambio de fecha), `ListChecks` (qué incluye). Sin colores de estado ni de actividad, triángulos ni signos de exclamación. El punto de pago ocupa las 2 columnas desde 768 px y lleva el ejemplo numérico: «Hoy pagas» en 14 `apagado` + monto en 20/700 `tabular-nums` y «El resto, el día del viaje, en efectivo» + monto en 20/700 (calculado con el servicio destacado; sin precio no hay ejemplo). La sección no tiene botón; cierra con un enlace de texto `cafe` a «Ver qué incluye cada servicio». Cargar `design-taste-frontend`. **PUNTO DEL DUEÑO** (textos es/en incluidos).
- [ ] **Título y copy.** Título visible (decisión del dueño, 2026-10-16): «Reserva con tranquilidad»/«Book with peace of mind». Puntos: «Cómo pagas»/«How you pay» — «Pagas directo a la empresa que opera tu servicio. Según el servicio, pagas el total en línea o el {porcentaje} % ahora y el resto en efectivo el día del viaje.»; «Si hay mal clima»/«If the weather is bad» — «Si el mal clima impide salir, hay reembolso completo.»; «Cambio de fecha»/«Changing your date» — «Puedes cambiar la fecha con al menos 48 horas de anticipación.»; «Qué incluye»/«What is included» — «Cada servicio tiene su propia lista. Revísala antes de reservar.» Commit `feat(sede): reserva con tranquilidad junto al producto`.

### Task 9.3: Hub — titular, héroe con video, tarjetas de sede útiles y mapa secundario

**Files:** Create `src/components/hub-portada.tsx` (héroe del hub), `src/components/tarjeta-sede-hub.tsx`, la clave `dict.hubContenido` (copy nuevo del hub); Modify `app/[lang]/page.tsx`, `hub-grid-sedes.tsx`, `hub-mapa-sedes.tsx`, `site-header.tsx`, `site-footer.tsx`, `app/[lang]/opengraph-image.tsx`, `structured-data.tsx`, `src/lib/site.ts`, `src/content/sedes-cuerpo.ts`, `dict.hub`, `dict.home` y `dict.meta` es/en; backend: `apps/tenancy/serializers.py` (`SedeSerializer`) y su prueba. (`hub-hero.tsx`, huérfano, ya lo borró la Task 5.4.)

- [ ] **Paso 1: héroe del hub con video del dueño (decisión del dueño, 2026-10-16).** Hoy la portada **no tiene héroe**: `page.tsx` abre con una sección `hub-mapa-destinos` con el `<h1>` y el mapa. El héroe nuevo (`hub-portada.tsx`) usa `HeroMedia` (Task 5.4): **video con poster inmediato** a través de `ui/video-diferido.tsx` (Task 1.5): isla cliente que monta el `<video>` tras `load`/idle **solo si** no hay `prefers-reduced-motion` ni `saveData`, y lo funde sobre el poster con un fundido de opacidad de 400 ms. El video es **neutro** (varias sedes o Baja en general, nunca una sola empresa: la foto de pesca de Sal y Sol repetiría el hallazgo H2, «esto es Sal y Sol»), **sin audio** y de **≤ 8 MB** (misma receta de compresión que la Task 1.5). **Sin 100 dvh:** el alto lo da el contenido (padding vertical de 48 a 64) con un tope `max-h-[calc(100svh-var(--nav-alto)-120px)]`, de modo que a 360 × 740 las tarjetas de sede asomen **al menos 120 px** sin scroll. Pila de **3** elementos: titular `texto-display`, subtexto de 20 palabras o menos que ES la línea de confianza (no hay tira aparte) y un CTA principal «Ver las sedes»/«See locations» que lleva a `#sedes`. **Textos:** titular «Reserva en Baja California Sur con las empresas locales» (en: «Book in Baja California Sur with local companies»); subtexto «Pesca, ballenas, hospedaje y traslados en cada sede. Cada empresa opera su servicio y cobra directo.» (en: «Fishing, whales, lodging and transfers at each location. Each company runs its service and charges directly.»); nunca se usan las palabras «vitrina», «marketplace», «agregador» ni «plataforma». Medir con Consola Mono real: máximo 3 renglones a 40 px en 328 px, sin palabra mayor de 13 caracteres. **Mientras no llegue el video:** bloque de texto sobre `arena` con **el mismo layout** (mismo alto, misma pila de 3; texto en `tinta` en vez de `--hero-ink`), y cuando el video y su poster lleguen entran después **sin cambiar el layout**. Dependencia del dueño (9.7): el video del hub (≥ 1280 px de ancho, neutro, sin audio) y su poster. **Mapa (decisión del dueño):** el mapa interactivo actual se conserva **solo desde 1024 px, debajo de las tarjetas** (no en el héroe), cargado con `next/dynamic` y esqueleto de alto fijo; en móvil no se monta y el ancla `mapa` no aparece en el menú.
- [ ] **Paso 2: tarjetas de sede.** Cada tarjeta muestra **qué se puede hacer** (chips de actividad), **las empresas que operan** y **precio «desde»** (de la API; sin precio no se pinta la línea), y foto cuando todas las sedes tienen la propia (Paso 2b). El mapa interactivo queda como ayuda secundaria en escritorio y no es el único camino; en móvil las tarjetas son el selector.
- [ ] **Paso 2b: composición de la tarjeta de sede (`TarjetaSedeHub`).** `Card` plana (blanco, borde `borde`, `rounded-card`, padding 24). Orden: [foto] / título `texto-paso` / chips (máx. 3, de `etiquetaActividad`) / «Con Sal y Sol Sportfishing y DLS Transporte» en 14 `tinta-suave` (una: «Con {a}»; dos: «Con {a} y {b}»; tres o más: «Con {a} y {n} más») / bloque «Desde» / CTA secundario «Ver La Paz»/«See La Paz» de 48 px, ancho completo y `mt-auto`. 360 px: una columna, gap 16. 768 px: dos columnas y, si hay 3 sedes, la tercera ocupa las dos con layout horizontal para no dejar una celda vacía. 1280 px: tres columnas iguales de alturas iguales (`grid-rows-subgrid` o `auto-rows-fr`). **Fila pareja:** con `tarjetasConFoto(sedes)` verdadero la foto de la sede va a sangre arriba (16:9 en móvil, 16:10 desde 768 px); si alguna sede no tiene foto propia, **ninguna** tarjeta de sede muestra foto, el título arranca la tarjeta con un renglón 14/600 `apagado` «Baja California Sur» encima, y nunca se usa `costa-placeholder.webp`. (Esta regla es de las tarjetas de **sede**; los servicios y paquetes sí llevan foto: Task 9.1b.) Toda la tarjeta es clicable con enlace estirado, nombre accesible con la sede («Ver La Paz»), hover solo con puntero (borde `borde-control` y `--capa-hover`), foco `has-[a:focus-visible]` y presionado `scale-[0.99]`. Datos parciales (fallo de la API): sin chips ni «Desde», misma altura y CTA; carga: esqueleto `cafe-bruma` del mismo alto.
- [ ] **Paso 2c: el «desde» lo calcula el backend (decisión del dueño, 2026-10-16).** `getSedes()` devuelve hoy `{ id, nombre, slug, zona_horaria, tipo_cambio_usd }` (`api.ts:307`) y la regla de redondeo (USD hacia arriba al dólar entero, por precio) vive en el backend (`contexto-negocio.md:184`). **Backend:** `SedeSerializer` (`apps/tenancy/serializers.py`) añade `resumen = { desde: { monto_mxn, monto_usd, base, tipo } | null, tipos: [str] }`; el mínimo excluye los servicios `por_ruta`, toma `precio_base` por servicio y `precio_ancla` por paquete, y `monto_usd = ceil(monto_mxn / tipo_cambio_usd)`; `base` es `por_persona|por_grupo|por_noche|tarifa_fija`; prueba en `apps/tenancy` (sin `por_ruta`, USD hacia arriba, empate, sede sin precios → `desde: null`, catálogo inactivo no cuenta), en SQLite y Postgres. **Frontend:** `getSedes()` lo recibe y el hub hace **una sola petición**; la tarjeta muestra «Desde $4,100 MXN por grupo», con USD primero y MXN entre paréntesis en `/en`, y sin precio no hay línea sin cambiar la altura de la tarjeta (CTA con `mt-auto`). Un fallo parcial quita solo la línea «desde» y los chips de esa tarjeta, nunca la tarjeta. **Frontera servidor/cliente:** el copy nuevo va en `dict.hubContenido`, no en `dict.hub`; `HubMapaSedes` (cliente) pasa a recibir `copy: Pick<Dictionary['hub'], …>` y `sedes: { slug, nombre, empresaProtagonistaNombre }[]` (proyección hecha en `page.tsx`), no el diccionario ni las sedes completos.
- [ ] **Paso 3:** `tsc`, `eslint`, `npm test`, `build`, `guardia`. PUNTO DEL DUEÑO (héroe con y sin video, tarjetas, mapa solo en escritorio). Commit `feat(hub): titular claro, heroe con video y tarjetas de sede con actividades, empresas y precio`.
- [ ] **Paso 3b: marca en cabecera y pie (decisión del dueño, 2026-10-16).** Hoy `site-header.tsx` (~L90) y `site-footer.tsx` (~L101) usan `sedeIndiceActiva?.logo ?? wordmark`: dentro de La Paz el sitio se presentaba con el logo de Sal y Sol y DLS pasaba a ser «un invitado». Ahora la marca nuestra es **siempre** el monograma «SB» de Sun Baja Experience (`EmpresaSello`, Task 3.7; sin wordmark de texto) en cabecera y pie de todas las páginas; en el hub y fuera de las sedes es la única; en la sede la cabecera suma la marca de la empresa protagonista (Task 9.1a Paso 2). Se elimina `logo` de `SEDES_INDICE` como fuente del encabezado; el logo de cada empresa vive solo en `empresas.ts` y se muestra con `EmpresaSello`. Criterio: `grep -rn "svglogosalysol" src` queda solo en `empresas.ts`.
- [ ] **Paso 4: rebrand de cadenas.** Aún dicen «Sal y Sol» o «Baja Experiences» como nombre del sitio: `dict.hub.nombreAgencia`, `porQueHeadline`, `hub.meta.title` y `hub.meta.description` (es y en); `home.title` (hoy «Sal y Sol Sportfishing», `es.json:3`), que `layout.tsx:55` pone como sufijo de todos los `<title>`; `meta.home.title` (`es.json:8`), el título por defecto del sitio; `meta.catalogo` y `meta.traslados` (`es.json:28,32`); `nav.brandMain` y `nav.brandAccent` (`es.json:95`, ahora texto accesible de la marca); `lib/site.ts:55` (`NEGOCIO.nombre`, JSON-LD); `site-footer.tsx`; los 4 `metaTitle` de La Ventana y Puerto Chale en `sedes-cuerpo.ts`; el `alt` de `opengraph-image.tsx` (su contenido se rediseña en 7.2 Paso 4); el `siteName` y el JSON-LD. Criterios: `grep -rn "Baja Experiences" src` = 0 y `grep -rn "Sal y Sol" src/app/[lang]/dictionaries src/lib/site.ts "src/app/[lang]/opengraph-image.tsx"` solo devuelve textos que hablan de la empresa Sal y Sol (privacidad, deslinde, `negocio`). El nombre «Sun Baja Experience» está decidido; **su confirmación final queda pendiente solo en este rebrand de cadenas** (PUNTO DEL DUEÑO antes del commit). Commit `feat(marca): nombre del sitio en todas las cadenas`.

### Task 9.4: Hub — «Cómo funciona» y «Empresas con las que colaboramos»

**Files:** Create `src/components/hub-como-funciona.tsx`, `src/components/fila-empresa.tsx`; Modify `colaboradores-section.tsx`, `app/[lang]/page.tsx`, `dict.hubContenido` es/en; Delete `hub-por-que.tsx` (sus `id="nosotros"` y enlaces se migran con los ids fijos del hub de la Task 9.1a Paso 3).

- [ ] **Paso 1: «Cómo funciona» (reemplaza a los pilares genéricos).** Explica la dinámica real: somos una empresa que **reúne los servicios de distintas empresas locales en un solo lugar**; cada empresa opera su servicio y **cobra directo**; reservas y pagas en un solo flujo aunque combines dos empresas. Incluye las condiciones reales (pago directo a la empresa, modo 100 % o anticipo según servicio, reembolso por mal clima, cambio con 48 h; valen igual en las 4 empresas). Tres filas, sin tarjetas anidadas ni numerales visibles ni conectores decorativos (el orden lo da el DOM): banda `cafe-bruma`; desde 1024 px, dos columnas 5/7 (título y dos frases a la izquierda; a la derecha una `ol` vertical de tres filas con ícono en círculo de 48 `blanco` con borde `borde` + título 20/600 + texto 16); en móvil y 768 px, una columna. Los títulos son verbo + objeto, no «Paso N». Íconos `MapPinLine`, `CreditCard`, `UsersThree`. Copy es: título «Un lugar, varias empresas»; «Reunimos en un solo lugar los servicios de las empresas locales de cada sede. Cada empresa opera su servicio y cobra directo.»; filas «Elige tu sede y tu servicio» / «Cada servicio muestra qué empresa lo opera, cuánto cuesta y qué incluye.», «Reserva y paga en un solo trámite» / «Eliges fecha y personas, dejas tus datos y pagas a la empresa. Si combinas servicios de dos empresas, pagas a cada una por separado.», «La empresa te atiende» / «Quien opera tu servicio te recibe el día del viaje. Si el mal clima impide salir, hay reembolso completo.» Copy en: «One place, several local companies»; «We bring together, in one place, the services of each location's local companies. Each company runs its own service and charges you directly.»; «Pick your location and service» / «Each service shows which company runs it, what it costs and what it includes.», «Book and pay in one go» / «Choose a date and group size, add your details and pay the company. If you combine services from two companies, you pay each one separately.», «The company hosts you» / «Whoever runs your service meets you on the day. If bad weather stops the trip, you get a full refund.» Sin enlaces ni animación.
- [ ] **Paso 2: empresas (`FilaEmpresa`, mismo componente en el hub y en la sede).** Directorio de **filas**, no tarjetas (una sede con una sola empresa dejaría una tarjeta huérfana en una rejilla de tres): `ul` con `divide-y divide-borde`, cada fila `py-6`. 360 px: una columna con `EmpresaSello` de 64 + nombre en 24/700 mono (`balance`, `break-word`) / sede y servicios en 14 `apagado` / descripción 16/1,5 (máx. 3 renglones, sin clamp) / enlaces en `flex-wrap gap-x-4`, cada uno de 44 px de alto mínimo. 768 y 1280 px: dos columnas (4/8 en 1280), con foto propia a la derecha a 16:10 desde 1024 px si existe. Título «Quién opera cada servicio»/«Who runs each service» (sin repetir «Empresas») y una frase de apoyo: «Cada empresa es independiente: opera su servicio y cobra directo.»/«Each company is independent: it runs its own service and charges directly.» **Enlaces, en este orden:** (1) interno («Ver servicios en {sede}»/«See services in {location}»), (2) Instagram o Facebook si existen, (3) «Sitio oficial»/«Official site» **solo si `webConfirmada`** (hoy DLS Transporte, La Ventana Travel y Piratas Adventures; Sal y Sol no lleva enlace externo porque su sitio es este, decisión del dueño, 2026-10-16); todo enlace externo lleva `aria-label="{acción}, {empresa}, se abre en una pestaña nueva"` e ícono `ArrowUpRight` de 16. El teléfono de la empresa (`contacto` de `empresas.ts`) solo se muestra en su fila si está confirmado; no se pinta ningún botón de WhatsApp por empresa (el sitio tiene un número único, `lib/contacto.ts`); nada de enlaces `#` ni correos inventados. **Datos faltantes:** sin logo, monograma; sin redes, solo el enlace interno; sin foto, ni foto ni hueco; sin descripción no se pinta la fila. Si el nombre comercial de su sitio difiere del del catálogo, la fila lo dice en 14 `apagado` con `tambienConocidaComo`. Descripciones de partida (sujetas a la confirmación de cada empresa; sin «15+ años» ni «embarcaciones certificadas» hasta tener documentación): Sal y Sol «Pesca deportiva en La Paz con capitanes locales. Salidas privadas desde Marina La Costa.»; DLS Transporte «Transporte turístico y privado en La Paz: traslados a aeropuerto y hospedajes, y transporte para eventos.»; La Ventana Travel «Pesca con mosca, avistamiento de ballenas y orcas, hospedaje, traslado de aeropuerto y paquetes de varios días.»; Piratas Adventures «Familia local de Puerto Chale: safari marino, avistamiento de ballena gris y pesca deportiva.» (con su par en inglés).
- [ ] **Paso 3:** PUNTO DEL DUEÑO (textos es/en y, antes de lanzar, que los sitios enlazados de La Ventana y de Piratas estén al día). Commit `feat(hub): como funciona el sitio y empresas colaboradoras con sus enlaces`.

### Task 9.5: Opiniones atribuidas y confirmadas

**Files:** Create `src/components/opiniones-empresas.tsx`; Delete `reviews-carousel.tsx` y `reviews-section.tsx`; borrar `dict.reviews` es/en.

- [ ] **Paso 1:** se retiran las reseñas de ejemplo del diccionario. `opiniones-empresas.tsx` pinta solo reseñas con `confirmada: true`, cada una con «Opinión publicada por [empresa]» y enlace a su fuente; **nunca** presentadas como verificadas por Sun Baja Experience ni mezcladas sin decir de qué empresa son. El filtro `confirmada === true` se aplica **en el servidor** antes de pasar props: el texto de una reseña no confirmada nunca viaja al navegador. Cada cita lleva `lang` de su idioma original (una reseña en español mostrada en `/en` lleva `lang="es"` y la etiqueta «Original en español»/«Original in English»; sin traducción automática). **Composición:** de 1 a 3 citas, sin carrusel ni estrellas (estrellas sin fuente verificable parecerían una calificación de Sun Baja Experience): cada una es una `figure` con `blockquote` de máximo 3 renglones (se recorta en origen, comillas tipográficas) y `figcaption` con nombre + `EmpresaSello` de 24 + «Opinión publicada por {empresa}» y el enlace «Ver en {fuente}». La primera cita grande (`texto-subtitulo`) y las demás más pequeñas, en 2 columnas desde 768 px; una sola cita es un bloque único. Título «Opiniones de las empresas»/«Reviews from the companies».
- [ ] **Paso 2: compuerta de confirmación.** Antes de poner `confirmada: true`, el dueño obtiene de la empresa su confirmación de que la reseña es real; sin ella no se publica. Se hace empresa por empresa y se anota la fecha en `empresas.ts`.
- [ ] **Paso 3: sin reseñas confirmadas no hay sección.** Si ninguna reseña de la sede está confirmada, `seccionesDeSede` no devuelve `opiniones` y la página no pinta nada en su lugar: ni franja, ni título, ni aviso (decisión del dueño, 2026-10-16: sin franja sustituta). Quien llega a las fotos y a las empresas lo hace por la cabecera y el pie, que ya los enlazan.
- [ ] **Paso 4:** PUNTO DEL DUEÑO. Commit `feat(sede): opiniones atribuidas y confirmadas`.

### Task 9.6: Preguntas frecuentes y datos estructurados por sede

**Files:** Modify `faq-section.tsx`, `structured-data.tsx`, `dict.faq`, `app/[lang]/sede/[slug]/page.tsx`.

- [ ] La FAQ y el JSON-LD de La Paz hablan de una sola empresa. Pasar a FAQ **por sede** (pago, cancelación y clima, qué llevar, punto de encuentro, idioma, niños) con las respuestas reales de cada empresa; el JSON-LD usa solo las preguntas que se pintan. Una sede sin FAQ cargada no pinta la sección (nunca «pronto»). Las preguntas reales de WhatsApp de las primeras semanas alimentan esta sección después del lanzamiento. El JSON-LD se escapa con `.replace(/</g, '\\u003c')` (guía `json-ld.md` de la doc de Next). Auditar `faq.items` de La Paz contra la regla 5: «¿Qué incluye el tour?» promete hielera, carnada y lunch en general, y lo que incluye es de cada servicio. Los resultados enriquecidos de FAQ ya no se dan a sitios comerciales: el JSON-LD de FAQ es inocuo pero no merece esfuerzo extra. **Composición de `FaqSede`:** máximo 8 preguntas, una abierta a la vez, disparador de 48 px con ícono `Plus`/`Minus` de 20 y altura animada en 250 ms solo bajo `motion-safe`; desde 1024 px, título fijo a la izquierda (280 px) y acordeón a la derecha; al final, «Si no encuentras tu duda, escríbenos por WhatsApp»/«If you cannot find your answer, message us on WhatsApp» como enlace de texto al número único del sitio (`lib/contacto.ts`), **solo si `tieneWhatsapp`**; si no, la línea no se pinta. Se quita de La Paz la pregunta «¿Qué incluye el tour?» o pasa a «¿Dónde veo qué incluye cada servicio?». **La sede no lleva CTA final**: el WhatsApp de este bloque hace de cierre (decisión documentada). **Dependencia del dueño:** los textos es/en de cada FAQ por sede (9.7). **PUNTO DEL DUEÑO:** textos es/en de cada FAQ. Commit `feat(sede): preguntas frecuentes y datos estructurados por sede`.

### Task 9.7: Cierre de F9

- [ ] `verificar` completo y los recorridos de F8, ahora con las páginas nuevas: hub y las tres sedes en es y en, en 360 px, 768 px y 1280 px; que ninguna sección diga «pronto» (`grep -rniE "pronto|soon" "src/app/[lang]/dictionaries" | grep -v "as soon as"` = 0; borrar las claves huérfanas que `tsc` no ve: `dict.license`, `dict.about`, `hub.pilares`, `hub.porQueHeadline`, `catalog.servicesComingSoon`, `destination.pendingBody`); que no aparezca ningún dato de relleno ni reseña no confirmada; que los enlaces de cabecera, pie y anclas funcionen; que cada `src` de foto aparezca **a lo más una vez** en el HTML de cada página de sede; que la cabecera de la sede muestre las dos marcas y la frase de colaboración y que el hub y el pie muestren solo la de Sun Baja Experience; que los servicios y paquetes de cada grupo tengan foto o ninguno la tenga; y que las tarjetas de sede del hub tengan la misma altura. PUNTO DEL DUEÑO.
- [ ] **Dependencias de contenido del dueño (bloquean el cierre, no el inicio; pedirlas ya, llegan por partes):**
  - **Precios reales de La Ventana Travel y Piratas Adventures** (B14, decisión del dueño: esperarlos antes de lanzar; hoy el «desde» y las tarjetas mostrarían los de ejemplo de `seed_catalogo_real.py`). Bloquea el cierre de F9.
  - Las listas de «qué incluye» de cada servicio y paquete, en es y en (campo `incluye`).
  - **Fotos del catálogo** (`public/catalogo/*.webp`, ≤ ~200 KB) de La Ventana, Puerto Chale y DLS (hoy solo hay de Sal y Sol), más fotos propias para la galería de cada sede.
  - **Video del hub** (≥ 1280 px de ancho, de contenido neutro —varias sedes o Baja en general—, sin audio, ≤ 8 MB) y su poster.
  - Logo definitivo de Sun Baja Experience (hasta entonces, el monograma «SB»).
  - Las respuestas de FAQ por sede, en es y en.
  - Que los sitios oficiales enlazados estén al día antes de lanzar: el de La Ventana lista otras actividades y el de Piratas es un borrador en `vercel.app` (el dueño decidió enlazarlos, `webConfirmada = true`, sabiéndolo).
  - Confirmación de reseñas por empresa; teléfono confirmado de Piratas y DLS (para su fila); descripciones finales de cada empresa.
  - El descriptor del estado de cuenta de cada empresa (B10): el dueño lo lee en el dashboard de Stripe de cada una y lo pega en el diccionario; hasta entonces no se promete.
  - Confirmación de que en La Paz la protagonista de la cabecera es Sal y Sol y de la cabecera del checkout de una sola empresa (Task 8.2).
  - **Aviso de privacidad y deslinde:** el abogado define el responsable de datos y las partes del deslinde por empresa (hoy `es.json:17,45,49` nombran a Sal y Sol Sportfishing); queda fuera de este plan y no bloquea código.
- [ ] Un solo merge y un solo deploy de F7 + F8 + F9 (rama `feat/marca-sun-baja`, Task 8.6).

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un refactor del checkout rompe el cobro | Fases F4/F5 por pasos, sin cambio de lógica; `lib/` ya tiene 20 suites; prueba de pago real con tarjeta de prueba de Stripe en el entorno QA tras cada paso; el dueño recorre el flujo |
| Diferir Stripe produce un salto de layout | *Fallback* del mismo tamaño; el resumen no se difiere (Task 1.2) |
| Las 20 suites no cubren componentes | Se declara; la red es compuerta + `tsc` + `build` + revisión del dueño; se evalúa añadir pruebas de componente en un plan aparte |
| La compuerta bloquea trabajo urgente | El trinquete permite bajar, no exige 0 hasta el cierre de F6 |
| El tipo de `dict` recortado rompe llamadores | Lo detecta `tsc`; ahorro modesto, la tarea es la 5.5 (F5) |
| Logo o fotos definitivos sin entregar | F7 se hace con tokens y fuentes; logo y fotos se sustituyen al llegar (no bloquean el resto) |
| Una marca que cambie la **forma** (no solo valores) rompe «F7 es solo tokens» | Forma por tokens semánticos (`--radius-control`, `--radius-campo`) y variantes; si la marca exige un layout distinto, se declara como alcance extra de F7, no como «cambio de valores» |
| Formulario de tarjeta y OG con la identidad vieja | `tokens-pago.ts` probado contra `globals.css`; OG como exento explícito en la lista de F7 |
| Un `<button>` dentro de un `<form>` sin `type` cambia de comportamiento al migrar | Revisión previa en Task 3.3 y migración con `type` explícito |
| Estado de cobro perdido al partir los 36 `useState` | Reducer compartido + recorridos manuales (rechazo, recarga, Turnstile, Enter) en cada commit de F5 |
| Contacto + detalles pasan de ~7 campos en alguna ruta | Task 8.1 cuenta los campos antes de unir; los opcionales se pliegan bajo «Más opciones»; no hay cuarto paso, y se avisa al dueño |
| Vista previa del rango se confunde con una selección confirmada | Estilo distinto (borde discontinuo + relleno suave) y señal por forma, no solo por color; segundo toque para confirmar en móvil |
| Perder el estado al cambiar de paso en el asistente móvil | El estado vive en el reducer existente, no en cada pantalla; recorridos manuales de F5 |
| Fuente: Consola Mono solo tiene Book y Bold | Titulares siempre 700; subtítulos y etiquetas en la fuente del cuerpo |
| El fondo arena exige tocar 57 usos de `bg-background` | Task 2.4 separa `--superficie` de `--background` antes de F7, sin cambio visual |
| Viaje se sobrecarga al recibir los extras | Task 8.1 cuenta los controles por ruta; los opcionales se pliegan, no se crea un cuarto paso |
| Quitar la tira semanal deja sin control a las cuatro rutas de compra y a la fecha de regreso de traslados | El calendario completo las cubre (la de regreso, obligatoria y sin prellenar); recorrido manual de las cuatro rutas |
| El botón de la barra no puede cobrar fuera de Stripe | La barra de la pantalla de tarjeta vive dentro de `<Elements>` (Task 8.4b); el botón interno de `PaymentForm` se quita |
| Un error de otro paso no tiene adónde llevar al usuario | `validarTodo()` devuelve `{paso, campo}` y el aviso ofrece «Corregir…» (8.1, 8.3b); el foco se aplica tras montar el paso |
| Perder lo escrito (Atrás, recarga, idioma) | Historial por paso + borrador en la pestaña (Task 8.0); se borra al confirmar |
| Datos personales en `sessionStorage` | Solo en la pestaña, con vigencia de 4 horas y borrado al confirmar (autorizado por el dueño); `try/catch` por si el almacenamiento falla |
| Un monto en el botón que no coincide con el cobro | Regla de la etiqueta: monto solo cuando el servidor lo confirmó; «Estimado» antes (Task 8.4a) |
| Controles de pesca aplicados a hospedaje, bajo demanda o traslados | `controlDeFecha` por tipo de servicio, con prueba por cada tipo (Task 8.5a) |
| Falsos positivos de la compuerta (comentarios, anclas `#add`) | Se ignoran comentarios, la regex de hex exige 3/4/6/8 dígitos y la prueba es la especificación |
| Reseñas de plantilla publicadas como reales | Cada reseña lleva autor, fuente y `confirmada`; solo se pintan las confirmadas por la empresa, siempre atribuidas a ella (Task 9.5); si ninguna, la sección no se pinta |
| Datos de relleno publicados (WhatsApp de Piratas, enlaces `#`, botón de DLS) | Solo contacto marcado como confirmado se renderiza; el resto queda fuera de `empresas.ts` hasta que la empresa lo confirme (Task 9.0) |
| Las fotos del catálogo van en el código (hardcodeadas): una foto nueva exige deploy y puede faltar alguna | Costo aceptado por el dueño (prioridad lanzar); `tests/imagenes-catalogo.test.cjs` exige foto para todo el catálogo, `imagenDeCatalogo` avisa en desarrollo y la regla «todas o ninguna» por grupo evita filas dispares; migrar a la foto del admin cambia solo esa función |
| Se publican precios de ejemplo de La Ventana Travel y Piratas | Decisión del dueño: esperar los reales antes de lanzar (dependencia en 9.7 que bloquea el cierre de F9) |
| Se enlazan sitios oficiales desactualizados (La Ventana lista otras actividades; el de Piratas es un borrador en `vercel.app`) | Decisión del dueño (`webConfirmada = true`) sabiéndolo; se compromete a tenerlos al día antes de lanzar (dependencia en 9.7) |
| El héroe del hub con video retrasa el LCP o empuja las tarjetas fuera del primer pantallazo | Poster inmediato con `next/image`, video diferido y fundido, ≤ 8 MB, sin 100 dvh y con tope de alto para que las tarjetas asomen ≥ 120 px a 360 × 740; sin video, bloque de texto con el mismo layout |
| La cabecera de la sede con dos marcas desborda a 360 px o pone a una empresa por encima de otra | Sellos de 32 con separador; en cruza-empresa y en el hub solo la marca nuestra; en La Paz la protagonista es Sal y Sol (supuesto a confirmar) |
| El backend (`incluye`, `descripcion`, `resumen`) debe estar desplegado antes que el frontend que lo lee | Las migraciones y serializers van en sus propias tareas (8.1b, 9.0, 9.3) y se despliegan primero; los campos nuevos son opcionales en el tipo de `lib/api.ts` |
| Reordenar secciones rompe los anclas (hoy en `site-header.tsx`, `site-footer.tsx` ×2, `sede/[slug]/page.tsx`, `servicio/…/page.tsx` y tres `id` en componentes del hub y la sede) | Task 9.1a Paso 3: `ANCLA_DE` y `enlacesDeSede` como única fuente, prop `anclas` opcional (sin ella, header y pie fuera de la sede solo enlazan «Reservar»), ids fijos en el hub y un `grep` que debe quedar en 0 |
| El modo de pago está en el servicio, no en la empresa (`permite_anticipo`, `porcentaje_anticipo` en `fleet/models.py`) | Task 9.2 lee el modo real de cada servicio desde la API (ya expuesto en `fleet/serializers.py` y recibido por `ServicioCatalogo`) |

## Orden y dependencias

`F0` → `F1` (en paralelo con `F2`, salvo la Task 2.3, que modifica `formulario-pago.tsx` y va después de 1.2a) → `F3` (incluye la Task 3.7, `EmpresaSello`) → `F4` grupos 1-3 → `F5` → `F4` grupo 4 (ya dentro de `bloques/*`) → `F6` → `F7` + `F8` + `F9` (salen juntas). F8 empieza por 8.0 y 8.1; la 8.1b (backend de `descripcion`) puede hacerse antes porque solo añade un campo. F9 (contenido y estructura de hub y sede) depende de F3 (primitivas), F5.4 (contenedores) y F7.2/F7.3 (nombres de token y fondos de sección); solo su parte de datos y textos (Task 9.0 y los textos es/en) puede empezar antes. **Ramas:** `feat/frontend-base` lleva F0-F6 (no cambia el aspecto) y puede fusionarse a `main` al cerrar F6; F1 puede salir antes con `git cherry-pick` del rango F0-F1 (mejora el lanzamiento sin tocar el aspecto). `feat/marca-sun-baja` nace de esa rama, lleva F7-F9 y se fusiona y despliega de una sola vez. F2 no cambia nada visible. F4 y F5 son los que más piden la revisión del dueño.

## Autorrevisión

- **Cobertura:** R1 (F3/F4/F5, 8.1, 8.4a), R2 (1.5, 5.4, 8.2, 8.3), R3 (F2, guardia, 8.1), R4 (restricciones, F4, F5, F7, 8.5), R5 (3.2, F7, 8.4a); los 13 puntos de la petición de reserva y los 12 hallazgos de recorridos aplicables están en F8 (1→8.2, 2→8.3, 3→8.3, 4→8.3, 5→8.5, 6→8.5, 7→8.3, 8→8.1, 9–12→8.4, 13→8.5); hallazgos V1–V9 asignados a tareas o a F7/futuro (V7 como sondeo, V8 a F7, V9 anotado).
- **Sin marcadores:** las tareas de F4/F5 son procedimentales porque cada una depende de leer el archivo real; llevan regla, orden, puerta y criterio de cierre. Las de F0–F3 llevan código.
- **Consistencia de nombres:** `botonClases`, `FormularioPagoDiferido`, `guardia-estilos.cjs`, `TOKENS_PAGO`, `--radius-control`/`--radius-campo`.
- **Limitación honesta:** los valores de Tailwind (Task 2.1) se copian de `node_modules`, no se citan de memoria; las alturas de los *fallbacks* (1.2) se miden al ejecutar.
- **Crítico de arquitectura:** ejecutado el 2026-10-15 (resultado: REVISION REQUIRED, 3 críticos y 4 significativos). Aplicadas: runner de pruebas (`guardia` fuera del runner, `variantes.ts` sin imports), partir `stripe-panel.tsx` antes de diferir, exentos y regex de la compuerta, F4-núcleo después de F5, capas `ui`, tokens de forma y de pago, `@theme` aparte sin byte-a-byte, recorte del diccionario movido de F1 a la Task 5.5, recorridos manuales. Ronda 3 (F7/F8): REVISION REQUIRED; aplicadas con las decisiones del dueño (3 pasos con extras en Viaje y «Pago 1 de 2» como sub-paso, calendario recortado, sin palabra caligráfica, página arena con tarjetas blancas), más `--nav-alto`, `BookingBar` intacto, lista de consumidores de fuentes, pasada de sombras/foco/titulares y bloques en F5. Ronda 4 (recorridos de todos los servicios): REVISION REQUIRED con 13 hallazgos (el 6, «extra sin precio USD», no aplica: el USD se deriva del tipo de cambio); soluciones derivadas con PFD y aplicadas (Tasks 8.0, 8.3b, 8.4 y 8.5 reescritas; decisiones del dueño: barra dentro de Stripe, regreso vacío y obligatorio, borrador en la pestaña, bajo demanda = reserva confirmada al pagar). Ronda 5 (skills de Vercel, 2026-10-16): REVISION REQUIRED con 1 crítico, 13 significativos y 11 menores; todos recogidos dentro de su tarea (la sección 0 da la trazabilidad). Ronda 6 (verificación de la ronda 5): REVISION REQUIRED sin críticos, 5 significativos y 8 menores, todos aplicados dentro de su tarea (script de medición propio, `botonClases` aún inexistente en F1, `drag` y `strict` de LazyMotion con regla `motion-completo`, puerto muerto fijado en el build, `preconnect` en los `page.tsx`, y los menores). Ronda de taste (skill `design-taste-frontend` + `docs/design/`, 2026-10-16): REVISION REQUIRED con 3 críticos, 15 significativos y 6 menores sobre la especificación visual, todos aplicados dentro de su tarea (los valores de marca en F7, el aspecto de F3 a F6 intacto). Ronda 7 técnica (F9 y lo añadido por la ronda de taste): REVISION REQUIRED con 3 críticos, 11 significativos y 8 menores, todos aplicados dentro de su tarea (tokens aditivos en F2, «qué incluye» sin fuente, anclas en 7 sitios, `hub-hero` huérfano, mapeos de actividad y cobro inexistentes, fronteras servidor/cliente, rebrand de cadenas). Cobertura de F9: R1 (9.1a-9.1c, 9.3), R2 (9.3), R3 (9.0, 9.1a Paso 3), R4 (regla «nada de pronto» y sin reseñas no confirmadas), R5 (9.1b Paso 2, 9.2). Ronda 7 de taste (hub y sede con la dinámica de varias empresas y la marca nueva): REVISION REQUIRED con 5 críticos, 14 significativos y 7 menores, todos aplicados dentro de su tarea (sin `AvisoEstado` en el bloque de pago, tarjeta de servicio con un solo CTA, héroe del hub neutro y no de una sola empresa, `EmpresaSello`, ritmo de fondos con bordes, galería con reglas de calidad, reseñas sin carrusel ni estrellas; la marca de cabecera y pie y la foto de las tarjetas se corrigieron después con las decisiones del dueño). **Ronda final meticulosa ejecutada el 2026-10-16:** 3 críticos, 37 significativos y 28 menores (F01-F69) aplicados dentro de su tarea; las decisiones B1-B16 del dueño (logo provisional «SB», héroe del hub con video, sin otra protección aparte del reembolso y el cambio de fecha, titular «Reserva en Baja California Sur con las empresas locales», «Reserva con tranquilidad», `webConfirmada` verdadero en tres empresas, `incluye` en el backend, «desde» del backend, política única de clima, título fijo por tipo, precios reales antes de lanzar, aviso de cookies fuera de las rutas de reserva) y una segunda pasada del dueño (servicios y paquetes con foto hardcodeada, sin sección sustituta cuando no hay reseñas, descripción en las personalizaciones, sede como colaboración entre Sun Baja Experience y la empresa protagonista, sello de empresa en la tarjeta de personalizaciones de cada empresa) también quedaron dentro de su tarea. Tareas divididas con sufijo: 1.2a/1.2b, 8.1b (nueva), 8.4a/8.4b/8.4c, 8.5a-8.5d, 9.1a/9.1b/9.1c; Tasks 3.7 (`EmpresaSello`, que estaba en 9.0b) y 8.7 (verificación de documentos). Supuestos que el dueño aún debe confirmar: protagonista de La Paz (Sal y Sol) y cabecera del checkout de una sola empresa con dos marcas.
