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
- Puerta de cada tarea: `npx.cmd tsc --noEmit`, `npx.cmd eslint src tests`, `npm.cmd test`, `npm.cmd run build`, `npm.cmd run guardia`. Un commit por tarea.
- **No ejecutar `shadcn init`**: reescribe `globals.css` y el skill documenta que rompe las fuentes en Tailwind 4. Se copia el patrón (`cn` + mapas de variantes puros, sin `cva`), no el CLI.
- **Nombres de token en los textos visuales:** las tareas de F7, F8 y las primitivas nuevas (`Sheet`, `AlertDialog`) describen colores con los nombres de `design.md` (`cafe`, `tinta`, `superficie`, `borde-control`, `apagado`…). Hasta F7 esos nombres no existen: F7.2 Paso 1b los declara y deja los actuales (`accent`, `action`, `foreground`, `muted`, `border-strong`) como alias. Antes de F7, un componente nuevo usa el alias equivalente de esa tabla; el aspecto de F3 a F6 no cambia.
- **Medición de peso (Next 16):** `next build` **ya no imprime «First Load JS»** (`upgrading/version-16.md`). Todo «comparar con la línea base» se mide con `scripts/medir-peso.cjs` (Task 0.2: suma bytes crudos y gzip de los chunks de cada ruta desde `page_client-reference-manifest.js` y `.next/static/chunks`); `next experimental-analyze` es solo diagnóstico (por defecto levanta un servidor en :4000 para verlo en navegador). Para el chunk de Stripe hay prueba binaria sin navegador: tras `next start`, `curl` de `/es/reservar` y comprobar que ni el HTML ni los chunks iniciales de la ruta contienen `js.stripe.com` (el literal `@stripe` no sobrevive a la minificación, no prueba nada).
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
| C1 · «First Load JS» ya no existe en Next 16 | Restricciones globales (medición), Tasks 0.2, 1.1, 1.2, 5.5, F6 |
| S1, S2 · `error.tsx`: sin diccionario cliente; firma `{ error, retry }` | Task 1.3 |
| S3 · `?paso=` con `history.pushState`, no `router.push` | Task 8.0 Paso 2 |
| S4 · precargar el formulario de Stripe y esqueleto hasta `onReady` | Task 1.2 Pasos 4–5 |
| S5, S6, S7 · héroe: isla de video, dos `<img>`, `preload` en vez de `priority` | Tasks 1.5 y 5.4 |
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
| M10 · `<ol>` con `aria-current`, objetivo táctil de 44 px | Tasks 8.4 y 7.3 |
| M11 · `media-src` y video fuera de `next/image` | V9 |

**Ronda de taste (skill `design-taste-frontend` con los 3 documentos de `docs/design/`, 2026-10-16):** 3 críticos, 15 significativos y 6 menores sobre la especificación visual; cada uno quedó dentro de su tarea: contrato de `Button`, campo y `Field` en 7.2 Paso 5; tokens y movimiento en 7.2; titulares, sombras, toast, esqueleto, radios y secciones en 7.3; `Sheet`, `AlertDialog` y la Task 3.6 en F3; cabecera en 8.2; tarjeta de paso y título en 8.3; aviso en 8.3b; barra y layout en 8.4; calendario en 8.5. **Los valores de marca entran en F7; F3 a F6 conservan el aspecto actual.**

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
| V1 | 40 archivos importan `@phosphor-icons/react` por el barril y `next.config.ts` no tiene `optimizePackageImports` | `bundle-barrel-imports` (CRÍTICA) | Mejora arranque en dev, build y cold start; en el bundle de producción puede quedar en ≈0 (el tree-shaking ya recorta), y eso no es un fallo |
| V2 | `stripe-panel.tsx` (611 líneas: Stripe + Elements + resumen + portal) se importa estático en las 3 vistas de compra | `bundle-dynamic-imports` (CRÍTICA) | Hay que **partir el módulo primero** (Task 1.2); después Stripe sale del chunk inicial y solo se baja al llegar a pagar. Los calendarios no se difieren (son del primer paso visible) |
| V3 | Se pasa el diccionario completo (`dict`, 55,8 KB en es) a 5 componentes cliente; solo usan `checkout` (18 KB), `pedido`, `traslados`, `feedback`, `continuar` | `server-serialization` (ALTA) | Ahorro modesto (~20 KB por idioma): Task 5.5, después de partir las vistas |
| V4 | 0 `<Suspense>`, solo 2 `loading.tsx` (reservar, traslados) y **ningún** `error.tsx`/`global-error.tsx` | `async-suspense-boundaries` (ALTA) + guía de errores de `nextjs` | Un fallo de la API tumba la página sin diseño |
| V5 | Video de 83,5 MB servido desde `public/` (`videohero.webm`), también referenciado por 2 sedes | `rendering-*` + `next/image` | Mayor riesgo de lanzamiento |
| V6 | 2 `<img>` crudas: `sede-hero.tsx:67` y `hub-hero.tsx:15` (LCP de la portada) | guía `nextjs/image` | LCP y tamaños |
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
| Compuerta estricta vs trabajo en curso | Compuerta con **trinquete**: el recuento de infracciones puede bajar, nunca subir; llega a 0 al cierre de F4 |

### Lo que cada fuente dejaba sin resolver y el plan cubre
- Faltan los **tokens de la marca nueva**: F2/F3 se construyen con los valores actuales y F7 los cambia. Se necesita el brief de marca antes de F7, no antes de F1.
- Las 22 suites cubren `lib/`, no componentes: la red de seguridad de F4/F5 es la compuerta + `tsc` + `build` + revisión del dueño. Se añade una prueba pura de variantes (F3) y se anota como limitación.

---

## 2. Mapa de archivos

| Archivo | Responsabilidad | Fase |
|---|---|---|
| `scripts/guardia-estilos.cjs` | Cuenta infracciones (colores literales, paleta cruda, `<button>`/`<input>` fuera de `ui/`, `<img>`, imports de `ui/` hacia fuera) ignorando comentarios, con lista de exentos con motivo; falla si suben | F0 |
| `scripts/guardia-estilos.baseline.json` | Recuento inicial por regla y archivo | F0 |
| `tests/guardia-estilos.test.cjs` | Prueba la detección con cadenas de ejemplo; se corre con `node --test` (`npm run test:guardia`), fuera del runner de `lib/` | F0 |
| `docs/superpowers/plans/2026-10-15-frontend-base-linea-base.md` | Tamaños por ruta antes/después | F0 |
| `next.config.ts` | `optimizePackageImports`, `images`, CSP si hace falta | F1 |
| `src/app/[lang]/error.tsx`, `src/app/global-error.tsx` | Errores con diseño | F1 |
| `src/app/[lang]/{sede/[slug],servicio/[empresa]/[servicio],catalogo}/loading.tsx` | Esqueletos de carga | F1 |
| `src/components/ui/cn.ts` | `clsx` + `tailwind-merge` | F3 |
| `src/components/ui/{caja-campo.ts,despliegue.tsx,error-de-campo.tsx}` | Movidos desde `checkout/` y `field-error` para que `ui/` no dependa de nada fuera de sí; los archivos viejos los reexportan | F3 |
| `src/components/checkout/pago/{resumen-pedido,tarjeta-como-pagas,nota-seguridad,tipos,formulario-pago,pago-diferido}.tsx` | `stripe-panel.tsx` partido: resumen y tarjeta «Cómo pagas» sin Stripe; solo `formulario-pago` importa Stripe | F1 |
| `src/lib/tokens-pago.ts` | Una sola fuente de los valores que Stripe Elements necesita en concreto (hex, radio), con prueba que la compara con `globals.css` | F2 |
| `src/components/ui/variantes.ts` | Mapas de variantes **puros, sin ningún import** (el runner los compila y los prueba sin DOM ni paquetes) | F3 |
| `src/components/ui/{button,input,field,card,badge}.tsx` | Primitivas (`button`/`card`/`badge` servibles desde servidor; `field` isla cliente) | F3 |
| `src/components/ui/{sheet,alert-dialog}.tsx` | Hoja y confirmación destructiva accesibles | F3 |
| `src/components/ui/video-diferido.tsx` | Isla cliente que monta el `<video>` tras `load`/idle | F1 |
| `src/components/ui/hero-media.tsx`, `section-shell.tsx` | Héroe y sección únicos | F5 |
| `src/components/ui/motion-provider.tsx` | `LazyMotion` con `domAnimation` y `strict` | F1 |
| `src/components/checkout/pago/esqueleto-pago.tsx` | Esqueleto del formulario de tarjeta, sin Stripe; lo usan `formulario-pago` y el `loading` del `dynamic` | F1 |
| `src/lib/errores-textos.ts` | Textos es/en de las páginas de error (sin `server-only`) | F1 |
| `scripts/medir-peso.cjs` | Métrica oficial de peso por ruta (crudo y gzip) | F0 |
| `src/lib/{borrador-reserva,origen}.ts` + sus pruebas | Borrador en la pestaña y origen de la flecha | F8 (8.0) |
| `src/lib/{problema-reserva,errores,etiqueta-boton,control-fecha}.ts` + sus pruebas, `src/components/ui/aviso-accion.tsx` | Avisos con acción, errores por campo, etiqueta del botón, control de fecha por servicio | F8 (8.1, 8.3b, 8.4, 8.5) |
| `src/content/empresas.ts` | Datos por empresa: descripción es/en, enlace oficial, redes, contacto **confirmado**, reseñas con su fuente y estado de confirmación, fotos propias | F9 |
| `src/lib/secciones-sede.ts` + `tests/secciones-sede.test.cjs` | Función pura: qué secciones de la sede se pintan y en qué orden según el contenido real | F9 |
| `src/components/{garantias-reserva,hub-como-funciona,opiniones-empresas}.tsx` | «Reserva con tranquilidad», «Cómo funciona» y reseñas atribuidas | F9 |
| `src/components/checkout/bloques/{bloque-viaje,bloque-extras,bloque-contacto,bloque-recogida,bloque-pago}.tsx` | Un archivo por **bloque** de contenido, extraídos de las vistas gigantes (F8 solo los reagrupa en 3 pasos) | F5 |
| `tests/variantes.test.cjs` | Prueba de las variantes | F3 |
| `src/app/fonts/ConsolaMono-{Book,Bold}.woff2` + `OFL.txt` + `FONTLOG.txt` | Fuente de titulares recortada a latín; la licencia viaja con ella | F7 |
| `src/components/reserva/{cabecera-minima,linea-progreso,barra-inferior,asa-resumen}.tsx` | Piezas del asistente móvil y de la cabecera sin navbar | F8 |
| `src/components/ui/calendario/{calendario,leyenda,atajos}.tsx` | Calendario completo, leyenda hecha con los mismos componentes que las celdas, y atajos | F8 |
| `src/lib/rango-paquete.ts` + `tests/rango-paquete.test.cjs` | Función pura que calcula el rango de un paquete de varias noches y dónde se corta por falta de cupo | F8 |

---

## F0 — Red de seguridad y línea base

### Task 0.1: Compuerta de estilos con trinquete

**Files:** Create `scripts/guardia-estilos.cjs`, `tests/guardia-estilos.test.cjs`; Modify `package.json`. (No se toca `tests/run-hub-tests.cjs`: ese runner compila con `rootDir: src` y un archivo de `scripts/` rompería **todas** las suites con TS6059.)

**Interfaces — Produces:** `npm run guardia` (sale con código 1 si alguna regla sube respecto a `guardia-estilos.baseline.json`) y la función exportada `contar(texto, regla)`.

- [ ] **Paso 1: prueba que falla** — `tests/guardia-estilos.test.cjs`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { contar, sinComentarios, relativosFuera } = require('../scripts/guardia-estilos.cjs');

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
  assert.equal(contar('className="uppercase tracking-wider"', 'mayusculas-crudas'), 1);
  assert.equal(contar('className="rounded-xl"', 'radio-crudo'), 1);
  assert.equal(contar('className="rounded-card"', 'radio-crudo'), 0);
  assert.equal(contar('className="shadow-lg"', 'sombra-cruda'), 1);
  assert.equal(contar('className="shadow-n2"', 'sombra-cruda'), 0);
  assert.equal(contar('className="bg-surface-deep"', 'surface-deep'), 1);
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
  'texto-chico-en-campo': /<(?:input|select|textarea)\b[^>]*\btext-(?:xs|sm)\b/g,
  'mayusculas-crudas': /\b(?:uppercase|tracking-wider|tracking-widest)\b/g,
  'radio-crudo': /\brounded-(?:md|lg|xl|2xl|3xl)\b/g,
  'sombra-cruda': /\bshadow-(?:\[|sm\b|md\b|lg\b|xl\b|2xl\b)/g,
  'surface-deep': /\bbg-surface-deep\b/g,
};

// Exentos con motivo: valores que una API externa pide en concreto, no como var().
const EXENTOS = {
  'src/app/globals.css': 'aquí viven los tokens',
  'src/app/[lang]/opengraph-image.tsx': 'ImageResponse no lee CSS',
  'src/components/lang-switch.tsx': 'SVG de banderas con colores propios',
  'src/lib/tokens-pago.ts': 'única fuente de los valores que Stripe Elements pide en concreto',
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
    if (Object.hasOwn(EXENTOS, rel)) continue;
    const enUi = rel.startsWith('src/components/ui/');
    const texto = sinComentarios(fs.readFileSync(abs, 'utf8'));
    for (const regla of Object.keys(REGLAS)) {
      if (SOLO_FUERA_DE_UI.includes(regla) && enUi) continue;
      if (regla === 'capas-ui' && !enUi) continue;
      const n = contar(texto, regla) + (regla === 'capas-ui' ? relativosFuera(texto, rel) : 0);
      if (n > 0) (resultado[regla] ??= {})[rel] = n;
    }
  }
  return resultado;
}

module.exports = { contar, sinComentarios, medir, relativosFuera, EXENTOS };

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
  let sube = false;
  for (const [regla, porArchivo] of Object.entries(actual)) {
    for (const [archivo, n] of Object.entries(porArchivo)) {
      const antes = base[regla]?.[archivo] ?? 0;
      if (n > antes) {
        console.error(`SUBE ${regla} en ${archivo}: ${antes} -> ${n}`);
        sube = true;
      }
    }
  }
  const total = (o) => Object.values(o).reduce((a, p) => a + Object.values(p).reduce((x, y) => x + y, 0), 0);
  console.log(`Infracciones: ${total(actual)} (línea base ${total(base)})`);
  process.exit(sube ? 1 : 0);
}
```

Las regex de `color-literal` y `capas-ui` son delicadas: **la prueba del Paso 1 es la especificación**; si una regex no la pasa, se ajusta la regex, no la prueba.

- [ ] **Paso 4:** en `package.json` añadir `"guardia": "node scripts/guardia-estilos.cjs"` y `"test:guardia": "node --test tests/guardia-estilos.test.cjs"`; correr `npm.cmd run test:guardia` → pasa. (`npm test` y su runner no se tocan; `verificar` en F6 corre ambos.)
- [ ] **Paso 5:** generar la línea base con `node scripts/guardia-estilos.cjs --escribir`; correr `npm.cmd run guardia` → «Infracciones: N (línea base N)», código 0.
- [ ] **Paso 6: commit** `chore(frontend): compuerta de estilos con trinquete y línea base`.

### Task 0.2: Línea base de carga

**Files:** Create `docs/superpowers/plans/2026-10-15-frontend-base-linea-base.md`, `scripts/medir-peso.cjs`.

- [ ] **Paso 1:** `npm.cmd run build`; crear `scripts/medir-peso.cjs` (**métrica oficial de antes/después**; Next 16 ya no imprime «First Load JS»): por ruta, suma bytes crudos y gzip de los chunks que lista su `page_client-reference-manifest.js` más los de `.next/static/chunks` que carga el HTML. Copiar a ese archivo el tamaño de JS por ruta de `/es`, `/es/sede/[slug]`, `/es/servicio/…`, `/es/reservar` y `/es/traslados`. `next experimental-analyze` queda solo para diagnóstico: sin navegador se usa `npx.cmd next experimental-analyze --output` y se comparan las carpetas de `.next/diagnostics/analyze`.
- [ ] **Paso 2:** añadir `du -sh public/videos public/photos` y el tamaño de `en.json`/`es.json`.
- [ ] **Paso 3: commit** `docs(frontend): línea base de carga antes de la optimización`.

---

## F1 — Carga y resiliencia (independiente del rediseño; se puede hacer ya)

> Es lo que más ayuda al lanzamiento y no depende de la marca. PUNTO DEL DUEÑO al cerrar la fase: mirar el primer paso de `/reservar` y la portada.

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

### Task 1.2: Partir `stripe-panel.tsx` para poder diferir solo el formulario de tarjeta (V2)

> Corrección del crítico: `stripe-panel.tsx` es **un módulo de 611 líneas** que importa `@stripe/stripe-js` y `@stripe/react-stripe-js` arriba y exporta `NotaSeguridadStripe`, `FormularioPago` y `StripePanel`. `StripePanel` pinta el resumen vivo del pedido desde el paso 1 **y**, por portal (`createPortal` hacia `destinoTarjeta`), la tarjeta «Cómo pagas» (promo, deslinde, Turnstile). Si el resumen sigue importando del módulo entero, Stripe viaja en el chunk inicial y el `dynamic` es decorativo; si se difiere el panel completo, el resumen y el portal desaparecen en SSR y se rompen el `ref` y el `scrollIntoView` de `checkout-view.tsx:827`. Por eso esta tarea es un **refactor estructural del checkout** y lleva revisión del dueño del flujo completo.

**Files:** Create `src/components/checkout/pago/resumen-pedido.tsx`, `tarjeta-como-pagas.tsx`, `nota-seguridad.tsx`, `tipos.ts`, `formulario-pago.tsx`, `pago-diferido.tsx`; Modify `src/components/stripe-panel.tsx` (queda como fachada que reexporta), `checkout-view.tsx:23`, `pedido/pedido-paquete.tsx:22`, `traslado-view.tsx:11`.

**Interfaces — Produces:** `StripePanel` (sin Stripe: resumen + portal de la tarjeta «Cómo pagas»), `NotaSeguridadStripe` (en `pago/nota-seguridad.tsx`, sin Stripe: la pintan tanto `FormularioPago` como las vistas), `FormularioPago` (único módulo que importa `loadStripe`, `Elements`, `PaymentElement`) y `FormularioPagoDiferido`; los tipos compartidos `StripePanelProps`, `OrderLine` y `Phase` viven en `pago/tipos.ts` (evita un ciclo de tipos entre el resumen, la tarjeta y la fachada). Las props públicas no cambian.

- [ ] **Paso 1:** leer `stripe-panel.tsx` completo y escribir en el mensaje del commit qué función va a qué archivo y qué estado compartían (`puente`, `pago`, `captchaKey`).
- [ ] **Paso 2:** mover `PaymentForm`, `STRIPE_APARIENCIA`, `STRIPE_FUENTES`, `loadStripe`/`Elements` y `FormularioPago` a `formulario-pago.tsx`. Mover el resumen y `TarjetaComoPagas` a archivos sin imports de Stripe. `stripe-panel.tsx` queda como fachada que reexporta **solo** `StripePanel` y `NotaSeguridadStripe`. **No reexporta `FormularioPago` ni importa `formulario-pago.tsx`**: `@stripe/stripe-js` tiene efectos al importarse y un import estático, aunque sea indirecto, dejaría Stripe en el chunk inicial y anularía el `dynamic`. Las tres vistas dejan de importar `{ FormularioPago, StripePanel }` de `stripe-panel` (`checkout-view.tsx:23`, `pedido-paquete.tsx:22`, `traslado-view.tsx:11`) y toman `FormularioPagoDiferido` de `pago-diferido.tsx`.
- [ ] **Paso 3:** `tsc`, `eslint`, `npm test`, `build`. Comprobar con `grep -rn "@stripe" src` que **solo** `formulario-pago.tsx` importa Stripe, y con `grep -rn "formulario-pago" src` que **solo** `pago-diferido.tsx` lo importa (y de forma dinámica).
- [ ] **Paso 4:** crear `pago-diferido.tsx`:

```tsx
'use client';

import dynamic from 'next/dynamic';
import { Skeleton } from '@/components/skeleton';

export const FormularioPagoDiferido = dynamic(
  () => import('@/components/checkout/pago/formulario-pago').then((m) => m.FormularioPago),
  { ssr: false, loading: () => <Skeleton className="h-64 w-full" /> },
);
```

Medir la altura real del formulario con su `PaymentElement` y poner esa altura en el *fallback* (sin salto de layout: R4). El esqueleto dura **hasta `onReady` del `PaymentElement`**, no solo hasta que baja el chunk (si no, hay salto cuando aparece el iframe). El `loading` de `dynamic` solo cubre la descarga del chunk: el esqueleto de la fase `onReady` vive en `pago/esqueleto-pago.tsx` (sin imports de Stripe), se pinta superpuesto con la misma altura dentro de `formulario-pago.tsx` hasta `onReady`, y el `loading` del `dynamic` usa ese mismo componente. **No pulsa** (design-guidelines: no se anima el contenido de pago): es un bloque estático con las filas del formulario dibujadas (número, vencimiento y CVC de 48 px de alto) que se desvanece con opacidad de 150 ms al llegar `onReady`. Ningún elemento con `transform`, `filter` ni `will-change` puede ser ancestro del iframe de Stripe.
- [ ] **Paso 5:** en las 3 vistas, usar `FormularioPagoDiferido` en lugar de `FormularioPago`. `StripePanel`, `ref`, portal y `key={captchaKey}` no se tocan. **Precarga (`bundle-preload`):** `pago-diferido.tsx` exporta también `precargarFormularioPago = () => import('@/components/checkout/pago/formulario-pago')`; se llama al montar el paso de datos o «Cómo pagas», o al acercarse al botón de continuar a pago, para que el chunk y `js.stripe.com` ya estén listos al crear la orden. Cargar Stripe.js tarde además reduce sus señales antifraude.
- [ ] **Paso 6:** `build`, `next start` y la prueba binaria de Restricciones globales (`curl` de `/es/reservar` y `/es/traslados` sin `js.stripe.com` ni `@stripe` en HTML ni chunks iniciales); además medir con `scripts/medir-peso.cjs` contra la línea base: el chunk inicial de esas rutas debe bajar.
- [ ] **Paso 7: PUNTO DEL DUEÑO** — recorrer con tarjeta de prueba de Stripe los **cuatro** caminos: servicio suelto, paquete de una empresa, paquete cruza-empresa (incluido el rechazo tras retención del primer pago) y traslados; y recargar a media compra. No se avanza sin su luz verde.
- [ ] **Paso 8: commit** `refactor(checkout): stripe-panel partido; solo el formulario de tarjeta carga Stripe, y bajo demanda`.

> Los calendarios (`DateField`, `CheckoutCalendar`) **no** se difieren en F1: son parte del primer paso visible; diferirlos produciría el salto que R4 prohíbe. Se reevalúa tras F5 con las medidas reales.

### Task 1.3: Páginas de error con diseño (V4)

**Files:** Create `src/app/[lang]/error.tsx`, `src/app/global-error.tsx`.

- [ ] **Paso 1:** leer la guía `nextjs` de manejo de errores y `node_modules/next/dist/docs/` para la firma de `error.tsx` en 16.3.6: **`{ error, retry }`** (`retry()` vuelve a pedir los datos; `reset` solo limpia el estado sin repedir; `unstable_retry` no existe). `[lang]/error.tsx` **no** atrapa fallos de `[lang]/layout.tsx` (p. ej. `getDictionary`): esos caen en `global-error.tsx`.
- [ ] **Paso 2:** `error.tsx` es Client Component y `dictionaries.ts` es `server-only`: **no puede importar el diccionario** (y traerlo al cliente metería ~56 KB por idioma). Toma el idioma con `useParams().lang` y los textos de un módulo pequeño `src/lib/errores-textos.ts` (solo es/en de error). `useParams().lang` es `string | string[] | undefined` y existe `[...resto]`: el módulo normaliza a es/en con fallback a es y no importa `dictionaries.ts`. Botón «Reintentar» que llama `retry()` y enlace a la portada. Registrar el error con su `digest` en consola.
- [ ] **Paso 3:** `global-error.tsx` mínimo (incluye `<html>`/`<body>` y no tiene estilos globales), con texto estático bilingüe de `errores-textos.ts` y `retry()`.
- [ ] **Paso 4:** verificar por tipos y `build`; luego **sin navegador**: construir con el puerto muerto (`NEXT_PUBLIC_API_URL=http://localhost:1 npm run build && npm start`; Next inlinea esa variable en el build, así que cambiarla solo en `next start` no prueba nada; si el build falla porque alguna página pide datos al compilar, usar `next dev` con la variable puesta al arrancar) y `curl` al HTML de `/es/reservar` para ver el error con diseño. No se simula un fallo en producción.
- [ ] **Paso 5: commit** `feat(frontend): páginas de error con diseño propio`.

### Task 1.4: Esqueletos de carga en las rutas con datos (V4)

**Files:** Create `loading.tsx` en `src/app/[lang]/sede/[slug]/`, `servicio/[empresa]/[servicio]/` y `catalogo/`.

- [ ] **Paso 1:** para cada ruta, leer su `page.tsx` y copiar la estructura de la página con `Skeleton`, al estilo de `reservar/loading.tsx`. Revisar también la cascada (`async-parallel`): `getDictionary`, `await searchParams` y las llamadas a la API se lanzan en paralelo (`Promise.all`) donde no dependen entre sí, y las secciones que dependen de la API van envueltas en `<Suspense>` (hoy hay 0), de modo que `loading.tsx` no reemplace la página entera.
- [ ] **Paso 2:** `build`. **Paso 3: commit** `feat(frontend): esqueletos de carga en sede, servicio y catálogo`.

### Task 1.5: Héroe — imagen inmediata y video ligero (V5, V6, PFD R2)

**Files:** Create `src/components/ui/video-diferido.tsx`; Modify `src/components/sede-hero.tsx` (el `<video>` y la `<img>` de la línea ~67) y `src/components/hub-hero.tsx` (la `<img>` de la línea ~15); Replace `public/videos/videohero.webm`. (El `Hero` viejo de la portada ya se eliminó. `hub-hero.tsx` no usa video.)

- [ ] **Paso 1: comprimir el video** (hay `ffmpeg` instalado):

```bash
ffmpeg -i public/videos/videohero.webm -vf "scale=-2:720,fps=24" -c:v libvpx-vp9 -crf 38 -b:v 0 -an -row-mt 1 public/videos/videohero.min.webm
ls -la public/videos/
```

Objetivo: ≤ 8 MB. Si se ve mal, subir calidad hasta que el dueño lo apruebe (PUNTO DEL DUEÑO: mirar el video). Añadir también una versión `.mp4` (H.264) como segunda `<source>` solo si hay navegadores objetivo sin VP9.
- [ ] **Paso 2:** reemplazar el archivo en las rutas de `sedes-cuerpo.ts` (2 referencias).
- [ ] **Paso 3:** en `sede-hero.tsx` la imagen del héroe se sirve con `next/image` y **`preload`** (en Next 16 `priority` está deprecado; `image.md`) como capa inferior: es el LCP real. El `<video>` ya no va en el HTML inicial: `ui/video-diferido.tsx` es una isla cliente que lo monta tras `load`/idle **solo si** no hay `prefers-reduced-motion` ni `saveData`, y lo funde sobre la imagen al disparar `canplay`. (`autoPlay` anula `preload="metadata"`, y el CSS no puede detener el autoplay por `reduce`.) Sin video: solo imagen.
- [ ] **Paso 4:** en `sede-hero.tsx:67` reemplazar `<img>` por `<Image fill sizes="100vw" preload alt="" className="object-cover" />`. Lo mismo en `hub-hero.tsx:~15` (`yellowtail-pelicanos-bahia.webp`, LCP de la portada). `hub-hero.tsx` es `'use client'` solo por un `onClick` que hace `scrollIntoView`: pasarlo a Server Component con `<a href="#mapa">` con las clases literales actuales del botón de `hub-hero` (`botonClases` aún no existe en F1, y F1 puede salir sola a producción; pasa a usarlo en F4 grupo 1, donde `hub-hero` ya está listado). El scroll suave del `<a>` funciona: `globals.css` ya pone `scroll-behavior: smooth` bajo `no-preference` y `<html>` tiene `data-scroll-behavior="smooth"`.
- [ ] **Paso 5:** `npm.cmd run guardia -- ` (la regla `img-cruda` baja en 2) y actualizar la línea base con `node scripts/guardia-estilos.cjs --escribir`.
- [ ] **Paso 5b (sin navegador):** `next start` y `curl` de `/es` y de una sede: el `<link rel="preload" as="image">` del héroe está en el HTML y no hay `<video>` en el HTML inicial.
- [ ] **Paso 6: commit** `perf(frontend): video de portada comprimido, imagen inmediata y next/image en la portada y la sede`.
- **Después, fuera de este plan:** mover el video a R2 (dominio en `img-src`/`media-src` de la CSP y en `images.remotePatterns`, hallazgo V9).

### Task 1.6: Pre-conexión a la API y CORS (opcional, de bajo riesgo)

- [ ] En los `page.tsx` (Server Components) de `reservar`, `traslados` y `servicio/[empresa]/[servicio]` —esas rutas no tienen `layout.tsx`, y el layout raíz cubriría todo el sitio— añadir `import { preconnect } from 'react-dom'` y llamar `preconnect(process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000', { crossOrigin: 'anonymous' })` (la conexión es de `fetch` CORS; sin `crossOrigin` el navegador abre otra) **solo ahí**, no en la portada ni en el layout raíz (regla `rendering-resource-hints`). Además, `request()` de `lib/api.ts` manda `Content-Type: application/json` incluso en GET, lo que fuerza un preflight en cada `getCupo`/`getCupoRango` cross-origin: enviarlo solo cuando hay body y pedir `Access-Control-Max-Age` al backend (pesa en el calendario completo de 8.5). Commit `perf(frontend): preconexión a la API`.

### Task 1.7: Sondeo de Cache Components (V7) — decisión, no código en producción

- [ ] Leer `node_modules/next/dist/docs/` sobre `cacheComponents` y `use cache` en 16.3. **Primero** evaluar el camino barato sin activar `cacheComponents`: `fetch(url, { next: { revalidate, tags } })` en las GET del catálogo público dentro de `request()`. Solo si no basta, probar `cacheComponents` en una rama aparte con `getServicioDetalle`/`getPaqueteDetalle` y `cacheLife('minutes')`, **listando sus costos**: todo `await params/searchParams` fuera de `<Suspense>` pasa a dinámico y rompe el build en sede, servicio y `/reservar`; activa `<Activity>` en la navegación (las rutas ocultas conservan estado y limpian efectos: Turnstile, `sessionStorage`, `captchaKey`); un `searchParams` solo para `moneda` vuelve dinámica toda la sede. Escribir en el archivo de línea base: qué ruta mejora, cuánto, y cómo se invalida un precio editado en el backoffice. **Sin decisión del dueño no se activa.** Cupo, cotización y pagos quedan fuera siempre.

### Task 1.8: `LazyMotion` en lugar de `motion` completo

**Files:** los ~20 componentes que importan de `motion/react` (incluidos `cookie-notice.tsx` y `lang-switch.tsx`, que están en el layout y viajan en todas las páginas); Create `src/components/ui/motion-provider.tsx`.

- [ ] **Paso 1:** cargar `vercel:react-best-practices` (`bundle-conditional`, `bundle-dynamic-imports`) y `apple-design` (para no cambiar la física de los resortes). `motion-provider.tsx`: `LazyMotion` con `features={domAnimation}` y `strict`, montado en el layout. `domAnimation` se carga **síncrono** (no con `import()` diferido) para evitar «pop-in» en la primera animación: excepción deliberada a `bundle-dynamic-imports`. El provider debe envolver `CookieNotice`, `LangSwitch` y `ProveedorToast`, que viven en `[lang]/layout.tsx`. `strict` solo lanza en desarrollo: en producción un `motion.*` suelto compila y pierde el ahorro; por eso la regla `motion-completo` de la compuerta (Task 0.1) lo cuenta y debe quedar en 0.
- [ ] **Paso 2:** sustituir `motion.*` por `m.*` en cada componente, sin tocar valores de animación. `hub-mapa-sedes.tsx:~49` usa `drag` (solo existe en `domMax`): con `domAnimation` el mapa dejaría de arrastrarse sin error. Ese componente lleva su propio `<LazyMotion features={domMax} strict>` anidado y `m.div`; igual cualquier otro que use `layout`.
- [ ] **Paso 3:** `tsc`, `eslint`, `npm test`, `build`; medir con `scripts/medir-peso.cjs` contra la línea base. El aspecto no cambia. **Paso 4: commit** `perf(frontend): LazyMotion con domAnimation`.

---

## F2 — Tokens completos, sin cambiar un solo valor (PFD R3)

> Idea clave: en Tailwind 4, declarar `--radius-*`, `--shadow-*` y `--text-*` dentro de `@theme` con los **mismos** valores por defecto hace que todas las utilidades existentes los lean desde `globals.css`. Después la marca los cambia en un solo sitio, y no hay que tocar componentes. Sin diferencia visual.

### Task 2.1: Declarar radio, sombra y escala de texto

**Files:** Modify `src/app/globals.css`.

> Corrección del crítico: el bloque actual es `@theme inline` y contiene los colores como `--color-x: var(--y)`. **No se toca ni se le quita `inline`** (afectaría `bg-card` con opacidad). Se añade un **segundo bloque `@theme { … }`** aparte. El CSS generado cambia (las utilidades pasan a leer `var(--radius-lg)` y se emite `:root{--radius-lg:…}`), así que el criterio no es «byte a byte» sino «mismo estilo calculado».

- [ ] **Paso 1:** abrir `node_modules/tailwindcss/theme.css` y copiar **literalmente** los valores de `--radius-xs…4xl`, `--shadow-xs…2xl` y solo las `--text-*` (con su `--line-height`) que el código usa (medido: xs, sm, base, lg, xl, 2xl, 3xl, 4xl, 5xl, 6xl). No escribirlos de memoria.
- [ ] **Paso 2:** pegarlos en un `@theme { … }` nuevo.
- [ ] **Paso 3:** añadir tokens **semánticos de forma**, para que la marca cambie la forma de los controles sin tocar componentes (corrige el supuesto falso de que `--radius-lg` mueve `rounded-full`):

```css
@theme {
  /* Forma de los controles: hoy botones en píldora y campos con radio medio. */
  --radius-control: 9999px;         /* botones: hoy rounded-full */
  --radius-campo: var(--radius-lg); /* campos y cajas: hoy rounded-lg */
}
```

  Las variantes (F3) y `CAJA_CAMPO` usarán `rounded-control` y `rounded-campo`. Añadir también `--color-ring` (foco) y mapear `border-red-400` de `CAJA_CAMPO_ERROR` a `border-error`. Declarar también `--shadow-n0` (none), `--shadow-n1` y `--shadow-n2` con los valores de las sombras actuales (n1 = barra inferior, n2 = popover, toast y hoja), para que `Sheet` (Task 3.5) los use desde F3 y F7.3 solo cambie sus valores.
- [ ] **Paso 4:** `build` y comparar **el cálculo de estilos** de las pantallas de la línea base (mismas clases, mismos valores resueltos). Cualquier diferencia visual se revierte.
- [ ] **Paso 5: commit** `refactor(frontend): radio, sombra, texto y forma de controles como tokens, sin cambio visual`.

### Task 2.2: Retirar los literales de color restantes

**Files:** los archivos con `color-literal` y `paleta-cruda` según `scripts/guardia-estilos.baseline.json` (66 literales + 13 de paleta + 3 arbitrarios en la medición).

- [ ] **Paso 1:** por archivo, reemplazar cada color por su token semántico (`bg-red-400`→`bg-error`, etc.). Los rgba de degradados sobre foto (`sede-hero.tsx`, `hub-hero.tsx`) se convierten en tokens `--scrim-*` en `globals.css`.
- [ ] **Paso 2:** si un literal no tiene equivalente exacto, **no redondear**: crear el token con el valor exacto (Bujack 2022: la desviación casi igual cuesta más que la clara).
- [ ] **Paso 3:** `guardia` (baja), actualizar línea base. **Paso 4: commit** `refactor(frontend): colores literales pasan a tokens`.

### Task 2.3: Una sola fuente para lo que Stripe Elements pide en concreto

> Corrección del crítico: `STRIPE_APARIENCIA` (`stripe-panel.tsx:78-89`) usa `colorPrimary: '#281ab5'`, `borderRadius: '8px'` y otros hex porque la API de Elements no acepta `var()`. Sin esto, la marca nueva dejaría el formulario de tarjeta con la identidad vieja, justo donde se cobra.

**Files:** Create `src/lib/tokens-pago.ts`, `tests/tokens-pago.test.cjs`; Modify `checkout/pago/formulario-pago.tsx`; Modify `tests/run-hub-tests.cjs` (registrar la suite; el módulo es puro y está dentro de `src`).

- [ ] **Paso 1: prueba:** `tokens-pago.test.cjs` lee `src/app/globals.css`, extrae `--accent`, `--foreground`, `--muted`, `--background` y `--error` y comprueba que `TOKENS_PAGO.colorPrimary`, `colorText`, `colorTextSecondary`, `colorBackground` y `colorDanger` valen lo mismo. Así una marca que cambie un token sin cambiar el otro **falla la prueba**.
- [ ] **Paso 2:** crear `tokens-pago.ts` exportando `TOKENS_PAGO` con los valores actuales y `RADIO_PAGO = '8px'`; `formulario-pago.tsx` arma `STRIPE_APARIENCIA` desde ahí.
- [ ] **Paso 3:** `opengraph-image.tsx` queda como excepción documentada en `EXENTOS` (`ImageResponse` no lee CSS); se actualiza a mano en F7.
- [ ] **Paso 4: commit** `refactor(pago): los valores concretos de Stripe Elements salen de una fuente probada contra los tokens`.

### Task 2.4: Token de superficie y tokens de tarjeta, sin cambio visual

> Hallazgo del crítico (ronda 3): hoy `--background` es blanco y `--color-card` apunta a él; 57 usos de `bg-background` mezclan fondos de página con fondos de tarjetas, campos y popovers. El diseño pone la página en **arena** y las superficies en **blanco**. Separarlos hoy, con el mismo color, deja a F7 en «solo valores».

**Files:** Modify `src/app/globals.css` y los componentes que usan `bg-background` (57 sitios).

- [ ] **Paso 1:** en `globals.css` añadir `--superficie: #ffffff` y `--color-superficie: var(--superficie)` (mismo valor que hoy), `--color-card: var(--superficie)`, y los tokens de forma de contenedor con **el valor actual** (las tarjetas hoy no tienen radio): `--radius-card: 0px; --radius-sheet: 0px`.
- [ ] **Paso 2:** recorrer los 57 usos de `bg-background` (`grep -rn "bg-background" src`) y repuntar a `bg-superficie` los que son **contenedores**: tarjetas, campos, popovers, hojas, calendario, resumen, barra inferior. Los de fondo de página o de sección siguen en `bg-background`. Se hace por superficie, en el mismo commit que su migración de F4 si ya la tocó.
- [ ] **Paso 3:** la prueba `tokens-pago` compara `colorBackground` de Stripe con `--superficie` (el formulario vive en una tarjeta), no con `--background`.
- [ ] **Paso 4:** `build` + `guardia`; sin diferencia visual (ambos tokens valen blanco). **Paso 5: commit** `refactor(frontend): token de superficie separado del fondo de página, sin cambio visual`.

---

## F3 — Primitivas con variantes (PFD R1, R5)

### Task 3.0: Subir a `ui/` lo que las primitivas necesitan (evita el ciclo `ui → checkout → ui`)

> Corrección del crítico: `Input` iba a importar `CAJA_CAMPO` de `components/checkout/estilos`, `Field` reutilizaba `ErrorDeCampo` (que usa `Despliegue` de `components/checkout/`) y `BotonPaso` (en `checkout/`) iba a envolver `Button` (en `ui/`): eso es `ui → checkout → ui`. Regla de capas: **`ui/` no importa nada fuera de `ui/`, `lib/` y paquetes** (la compuerta la hace cumplir con la regla `capas-ui`).

- [ ] Mover `CAJA_CAMPO` y `CAJA_CAMPO_ERROR` a `src/components/ui/caja-campo.ts`, `Despliegue` a `ui/despliegue.tsx` y `ErrorDeCampo`/`FieldError`/`propsDeError` a `ui/error-de-campo.tsx`. Los archivos viejos (`checkout/estilos.ts`, `checkout/despliegue.tsx`, `field-error.tsx`) pasan a **reexportar** desde `ui/` para no tocar los llamadores. Reescribir `CAJA_CAMPO` con `rounded-campo` (Task 2.1).
- [ ] `tsc`, `eslint`, `npm test`, `build`, `guardia`. Commit `refactor(ui): capa base de ui sin dependencias hacia checkout`.

### Task 3.1: Dependencias y `cn`

**Files:** Modify `package.json`; Create `src/components/ui/cn.ts`.

- [ ] `npm install clsx tailwind-merge`.
- [ ] `src/components/ui/cn.ts`:

```ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...entradas: ClassValue[]) {
  return twMerge(clsx(entradas));
}
```

- [ ] Commit `chore(frontend): clsx y tailwind-merge para las primitivas`.

### Task 3.2: Variantes puras y probadas

> Corrección del crítico: el runner (`tests/run-hub-tests.cjs`) compila con `rootDir: src` y emite el JS a un directorio temporal donde Node **no resuelve paquetes** (no hay `NODE_PATH`). Por eso `variantes.ts` no importa nada: son mapas de strings y una función. Las primitivas (`button.tsx`) las combinan con `cn`, que no se prueba aquí.

**Files:** Create `src/components/ui/variantes.ts`, `tests/variantes.test.cjs`; Modify `tests/run-hub-tests.cjs` (añadir la entrada de la suite).

**Interfaces — Produces:** `botonClases({ variante, tamano }): string`; variantes `principal | secundario | texto | acento | peligro`; tamaños `md | sm | icono`.

- [ ] **Paso 1: registrar la suite** en `suites` de `run-hub-tests.cjs`: `variantes: ['src/components/ui/variantes.ts', 'VARIANTES_TEST_OUT']`.
- [ ] **Paso 2: prueba** `tests/variantes.test.cjs` (carga el JS compilado como las demás suites):

```js
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
const BASE =
  'inline-flex items-center justify-center font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50';

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

### Task 3.3: `Button`, `Input`, `Field`, `Card`, `Badge`

**Files:** Create `src/components/ui/{button,input,field,card,badge}.tsx`.

**Interfaces — Produces:**
- `Button(props: ButtonHTMLAttributes & BotonVariantes & { conFlecha?: boolean; cargando?: boolean })`, siempre `type="button"` salvo que se indique `type="submit"`. `cargando` usa `aria-busy` y `aria-disabled` (no `disabled`, para no perder el foco). Sin `'use client'` ni `motion`: servible desde servidor. En React 19 `ref` es una prop normal (sin `forwardRef`). Con `conFlecha` el icono viene de `@phosphor-icons/react/ssr` (el barril normal usa contexto de cliente); mientras `cargando`, `onClick` se ignora (no hay `disabled`).
- `Input(props: InputHTMLAttributes & { invalido?: boolean })`, con `aria-invalid`.
- `Field({ etiqueta, error, ayuda, children })`: genera el `id` con `useId()` y enlaza error y ayuda con `aria-describedby`; etiqueta, control y `ErrorDeCampo` (reutiliza el existente con `Despliegue`). Es isla cliente. `Card` y `Badge` también servibles desde servidor.
- `Card({ padding })`: una sola variante base, plana, con borde y sin sombra; `padding` `24` (y `32` desde 1024 px). `ChipActividad({ tipo: 'mar' | 'ciudad' | 'outside' })` y `AvisoEstado({ tono: 'exito' | 'error' | 'aviso' | 'info' })` son dos componentes distintos que no se mezclan (un chip de actividad nunca comunica estado). Valores visuales finales en la sección «Card y chips» de 7.3.

- [ ] Por componente: escribir, usar `cn` y las variantes; `Input` usa `CAJA_CAMPO`/`CAJA_CAMPO_ERROR` de `ui/caja-campo` (movidos en Task 3.0; **nunca** de `checkout/estilos.ts`, que violaría la capa `ui`). `Card` usa `bg-superficie` y `rounded-card`; `ChipActividad` lleva fondo `*-claro`, texto del tono oscuro y siempre icono (`Waves`, `Buildings`, `Mountains`); `AvisoEstado` lleva icono `CheckCircle`, `WarningCircle`, `Warning` o `Info`. Una `Card` no contiene otra `Card`: los subgrupos se separan con espacio, no con otro borde.
- [ ] `Button` tiene **`type="button"` por defecto**. Antes de migrar un `<button>` hay que mirar si está dentro de un `<form>` sin `type`: ese hoy **envía** el formulario (p. ej. Enter en `campos-contacto`). Ese caso se migra con `type="submit"` explícito. Listar con `grep -rn "<button" src --include=*.tsx` y revisar los que estén dentro de `<form`.
- Probar en **una sola pantalla**: sustituir los botones de `faq-section.tsx` (superficie pública de bajo riesgo) por `Button`. Verificar con `tsc`, `eslint`, `build`, `guardia` (baja).
- [ ] PUNTO DEL DUEÑO: mirar la sección de preguntas frecuentes (debe verse igual).
- [ ] Commit por componente.

### Task 3.4: Absorber lo ya existente

- [ ] `BotonPaso` pasa a ser un envoltorio de `Button variante="principal"`; `AccionTexto` y `EtiquetaModificar` usan `botonClases({ variante: 'texto' | 'acento' })`. Los nombres se conservan para no tocar los llamadores. Commit `refactor(checkout): BotonPaso y AccionTexto sobre la primitiva Button`.

### Task 3.5: `Sheet` y `AlertDialog` accesibles

> Las Tasks 8.3b, 8.4 y 8.5 usan una hoja («Ver resumen»), una confirmación destructiva («Cancelar y liberar mi lugar») y el calendario en móvil. La skill `shadcn` pide `AlertDialog` (no `Dialog`) para confirmación destructiva y prohíbe el `div` crudo donde existe primitiva. Se construyen una vez, aquí, no tres veces sueltas.

**Files:** Create `src/components/ui/{sheet,alert-dialog}.tsx`.

- [ ] Sobre `<dialog>` nativo con `showModal()` (o Radix/Vaul si se justifica con el analizador): trampa de foco, `aria-modal`, Esc, bloqueo de scroll, fondo inerte, foco que regresa al disparador. Estilos con tokens (`--radius-sheet`, `--shadow-n2` desde F7). Cargar `design-taste-frontend` antes de diseñar su forma. Variantes puras en `variantes.ts` con su prueba.
- [ ] **`Sheet` (< 640 px):** `fixed inset-x-0 bottom-0 max-h-[85dvh] overflow-y-auto overscroll-contain bg-superficie rounded-t-sheet shadow-n2 px-4 pt-3 pb-[max(16px,env(safe-area-inset-bottom))]`. Asa visual de 4 × 40 (`bg-borde-control`, centrada, `mb-3`; no es el área de arrastre). Cabecera con título `texto-subtitulo` y botón «Cerrar» de 48 × 48 a la derecha. Fondo atenuado con el token `--scrim-hoja` (tinta al 40 %). Entra con `translateY(100%) → 0` en 400 ms con `curva-estandar`; sale con `curva-salida` en 250 ms; con reducir movimiento solo opacidad, 150 ms. Para animar `<dialog>` usar `@starting-style` y `transition-behavior: allow-discrete`. El `ResumenPedido` dentro de la hoja usa una variante `sinBorde` (no hay tarjeta dentro de la hoja). Se cierra con Esc, tocando fuera o con «Cerrar». `--radius-sheet` vale 0 hasta F7 (que lo pone en 24 px).
- [ ] **`AlertDialog`:** centrado, `w-[min(92vw,420px)] rounded-card bg-superficie p-6 shadow-n2`, título `texto-subtitulo`, cuerpo `texto-cuerpo`. Botones apilados a ancho completo por debajo de 640 px y en fila a la derecha desde ahí. La acción segura va primero en el DOM («Seguir con mi reserva», `secundario`) y recibe el foco inicial; la destructiva usa `peligro` con la etiqueta del resultado («Cancelar y liberar mi lugar»). Nunca hay dos botones `principal`.
- [ ] Probar en una sola pantalla de bajo riesgo antes de usarlas en F8. PUNTO DEL DUEÑO. Commit `feat(ui): Sheet y AlertDialog accesibles`.

### Task 3.6: `Checkbox`, opción de radio e interruptor

> `design-components.md` los define y el checkout hoy los arma a mano.

**Files:** Create `src/components/ui/{checkbox,opcion,interruptor}.tsx`.

- [ ] Casilla de 24 con área táctil de 48 y radio `rounded-casilla` (6 px); opción de radio de 24; interruptor de 52 × 32; etiqueta clicable a la derecha en los tres; foco con el anillo de `ring`. Islas cliente con `useId()`. Sustituir las casillas y selectores hechos a mano en F4 grupo 3. Commit `feat(ui): casilla, opción e interruptor`.

---

## F4 — Migrar los 84 controles (uno por superficie, aspecto idéntico)

Recuento medido (`<button`): continuar-reservacion 7, reviews-carousel 5, grupo-servicio 4, fecha-paquete 4, hub-mapa-sedes 4, stripe-panel 3, date-field 3, checkout-view 3, checkout-calendar 3, y 23 archivos con 1 o 2. Controles de formulario (`<input|select|textarea>`): stripe-panel 4, grupo-servicio 4, traslado-view 2, checkout-view 2, field-popover 1, select-personalizado 1, campos-contacto 1.

**Regla de migración (aplica a todas las tareas):** una superficie por commit; el JSX resultante genera las mismas clases (comparar el HTML renderizado en el `build` no basta: se compara el diff de clases a mano); si una variante no existe, **se añade la variante** a `variantes.ts` con su prueba, no se deja un `<button>` crudo.

Orden por riesgo creciente (PUNTO DEL DUEÑO al cerrar cada grupo):
1. **Públicas sin dinero:** `faq-section`, `cookie-notice`, `lang-switch`, `site-header`, `sede-selector`, `reviews-carousel`, `hub-mapa-sedes`, `hub-hero`, `paquete-card`, `selector-experiencia`, `continuar-reservacion`.
2. **Campos y selectores compartidos:** `field-popover`, `date-field`, `time-field`, `people-stepper`, `select-personalizado`, `toast`. **No se migra** `checkout-calendar` (ni la tira semanal que usa): F8 los reemplaza por el calendario completo. `BookingBar`, `StickyBookingBar` y el `Hero` viejo ya se eliminaron.
3. **Checkout, tarjetas auxiliares:** `checkout-section-card`, `campos-contacto`, `tipo-traslado-cards`, `ayuda-flotante`, `reserva-plegable`, `aviso-fallo`.
4. **Checkout, núcleo:** `grupo-servicio`, `fecha-paquete`, `checkout-view`, `traslado-view`, `stripe-panel`, `booking-confirmation`. **Se hace DESPUÉS de F5**, ya dentro de `checkout/pasos/*` (corrección del crítico: migrar y luego partir las mismas ~1 700 líneas es trabajo doble con revisión del dueño en cada pasada). Con revisión del dueño del flujo completo.

Cada tarea: sustituir, correr la puerta de siempre, `guardia` debe **bajar**, actualizar la línea base, commit `refactor(<superficie>): controles sobre las primitivas`. Al terminar el grupo 4 (después de F5), `boton-crudo` e `input-crudo` quedan en 0 y el script las hace fallar con cualquier valor > 0.

---

## F5 — Partir las vistas y unificar héroes (PFD R1, R4)

> Es refactor puro: ningún texto, flujo ni estilo cambia. Cada extracción es un commit.

### Recorridos manuales obligatorios (en cada commit de F5 y en el grupo 4 de F4)

> Corrección del crítico: `tsc`, `eslint`, `build`, `guardia` y las suites de `lib/` no ejercitan componentes. Estos casos pueden romperse sin que nada los detecte, así que **cada commit de F5 y del grupo 4 de F4 pasa por esta lista**, y el dueño confirma:
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
- [ ] **Paso 2:** el estado compartido sube a un *reducer* (el patrón ya existe en `lib/pedido-estado.ts` + `use-pedido-estado.ts` para paquetes); el estado local de un paso baja a su componente. **Reparto del estado (evita re-renderizar todo en cada tecla):** el texto de los campos es **local al bloque** y se confirma al reducer en `blur` o al avanzar; el contexto de *state* y el de *dispatch* van separados (o selectores con `useSyncExternalStore`); los bloques van con `memo`; antes de partir, evaluar `reactCompiler: true` (`reactCompiler.md` en 16.3; hoy hay 19 `useMemo/useCallback` y 33 `useEffect`). Reglas `rerender-defer-reads`, `rerender-memo`, `rerender-derived-state-no-effect` y `rerender-no-inline-components`. Esto es un cambio de arquitectura del estado de cobro, no un «refactor puro»: pasa por la lista de recorridos manuales en cada commit.
- [ ] **Paso 3:** extraer un **bloque** por commit en este orden: pago, extras (hoy «detalles»), contacto, recogida (solo traslados), viaje; los 4 pasos actuales quedan como composición fina de bloques. Así F8 solo reagrupa los bloques en tres pasos, sin volver a partir las vistas. Tras cada extracción: `tsc`, `eslint`, `npm test`, `build`, `guardia`.
- [ ] **Paso 4:** PUNTO DEL DUEÑO tras cada paso extraído (recorrer el servicio suelto completo hasta el pago de prueba).

### Task 5.2: Partir `traslado-view.tsx` (1 006 líneas, 32 `useState`)

- [ ] Mismo procedimiento. Reutiliza `PaginaCheckout`, `ContenidoViaje` y los pasos ya compartidos; el objetivo es que los bloques de traslados (viaje, contacto, recogida, pago) sean componentes de `checkout/bloques/`.

### Task 5.3: Revisar `pedido-paquete.tsx` (894 líneas)

- [ ] Ya usa hooks y reducer; solo extraer los bloques de JSX grandes en componentes (`grupo-servicio.tsx` ya existe). No es prioridad.

### Task 5.4: Un solo héroe y una sola sección

**Files:** Create `src/components/ui/hero-media.tsx`, `section-shell.tsx`; Modify `hub-hero.tsx`, `sede-hero.tsx` y las secciones about/season/included/license/colaboradores/gallery.

- [ ] `HeroMedia({ imagen, video, alt, preload })` es un **Server Component**: `<Image preload>` + degradado, más la isla cliente `ui/video-diferido.tsx` de la Task 1.5 (el patrón completo vive allí). Los dos héroes (`hub-hero`, `sede-hero`) lo usan. **Contrato visual** (F5 conserva el aspecto actual; los valores de marca entran en F7.3): contenedor `relative min-h-[100dvh]` en la portada y `min-h-[70dvh] lg:min-h-[80dvh]` en la sede (nunca `h-screen`); imagen `fill object-cover` con `objectPosition` configurable por sede; scrim como token `--scrim-hero`; texto alineado abajo a la izquierda en ≥ 1024 px; pila máxima de 4 elementos (titular `texto-display` en ≤ 2 líneas, subtexto ≤ 20 palabras, un CTA principal y uno secundario); el video entra con fundido de opacidad de 400 ms usando la misma imagen como `poster`; con reducir movimiento solo imagen.
- [ ] `SectionShell({ fondo: 'papel' | 'bruma' | 'bruma-profunda', titulo, regla })` encapsula el ritmo de secciones (la «paleta v3» solo admite esos tres fondos hasta F7, que los renombra a `arena | blanco | cafe-bruma`; ver 7.3). Padding vertical `py-12 sm:py-16 lg:py-24`, ancho máximo 1120 con márgenes de 16, 24 y 32.
- [ ] Un héroe por commit; PUNTO DEL DUEÑO al terminar (portada, sede, servicio). F5.4 solo unifica los contenedores: **qué secciones lleva cada página, en qué orden y con qué texto se decide en F9.**

### Task 5.5: Diccionario por sección en los clientes (V3, ahorro modesto)

> Movida desde F1 por el crítico: con la vista aún entera, `dict` se pasa a sub-componentes (`checkout-view.tsx:1188` y `:1398`; `AvisoCargos`, `EncabezadoPago`, `PorQueVariosPagos` en `pedido-paquete.tsx`), y recortar el tipo se vuelve una cascada de ~10 archivos para ~20 KB. Después de F5, cada paso recibe props mínimas y el recorte es natural.

- [ ] Para cada paso extraído, tipar `dict` con `Pick<Dictionary, 'checkout' | …>` según lo que use; que `tsc` dé la lista. Medir con `scripts/medir-peso.cjs`; si el ahorro es < 10 KB, descartar la tarea y anotarlo. Commit `perf(checkout): cada paso recibe solo las secciones del diccionario que usa`.

---

## F6 — Cerrar la base

- [ ] `guardia`: `boton-crudo`, `input-crudo`, `img-cruda`, `paleta-cruda`, `capas-ui` y `motion-completo` en **0 salvo los exentos listados con motivo** en `EXENTOS` (`globals.css`, `opengraph-image.tsx`, `lang-switch.tsx`, `tokens-pago.ts`); umbral duro. Cualquier exento nuevo exige un motivo escrito en el código.
- [ ] Script `"verificar": "tsc --noEmit && eslint src tests && npm test && npm run test:guardia && npm run guardia && next build"` en `package.json`.
- [ ] Actualizar `frontend/CLAUDE.md`: dónde viven los tokens y las primitivas, la regla «nada crudo», cómo añadir una variante y cómo correr `verificar`.
- [ ] Línea base final de carga en el archivo de F0 (medida con `scripts/medir-peso.cjs`, igual que la inicial). Commit `docs(frontend): base cerrada`.

---

## F7 — Marca nueva: valores y una pasada de componentes (PFD R4)

**Entradas ya entregadas:** `docs/design/design.md` y las decisiones del dueño del 2026-10-15: botón principal café con texto blanco; titulares en Consola Mono (solo 400 y 700); cuerpo en la pila del sistema (San Francisco en Apple); radio 12 px en controles y 16 px en tarjetas; página **arena** `#FBF7F0` con tarjetas, campos y calendario **blancos**; sin negro puro; categorías azul = mar, coral = ciudad, verde = outside o montaña; **sin la palabra caligráfica** de los titulares. **Falta del dueño:** logo y fotos definitivos.

### Task 7.1: Preparar la fuente Consola Mono

**Files:** Create `src/app/fonts/ConsolaMono-Book.woff2`, `ConsolaMono-Bold.woff2`, `OFL.txt`, `FONTLOG.txt`; Modify `src/app/fonts/LICENCIAS.md`.

- [ ] **Paso 1:** descargar el zip de `https://www.dafont.com/es/consola-mono.font` (autor Wojciech Kalinowski, SIL Open Font License 1.1, sin nombre reservado declarado) en una carpeta **nueva y vacía**; los archivos descargados se tratan como no confiables: no se ejecuta nada de ellos.
- [ ] **Paso 2:** recortar a latín con acentos, puntuación, moneda y símbolos de la interfaz y convertir a WOFF2 (requiere `fonttools` y `brotli`):

```bash
pyftsubset ConsolaMono-Bold.ttf --unicodes="U+0020-007E,U+00A0-00FF,U+0100-017F,U+2010-2027,U+20AC,U+2190-2193,U+00D7" --flavor=woff2 --layout-features='*' --output-file=ConsolaMono-Bold.woff2
pyftsubset ConsolaMono-Book.ttf --unicodes="U+0020-007E,U+00A0-00FF,U+0100-017F,U+2010-2027,U+20AC,U+2190-2193,U+00D7" --flavor=woff2 --layout-features='*' --output-file=ConsolaMono-Book.woff2
```

  Objetivo: ≤ 40 KB por archivo. Comprobar á é í ó ú ñ ü ¿ ¡ y `$4,100`.
- [ ] **Paso 3:** copiar `SIL - Open Font License.txt` como `OFL.txt` y `FONTLOG.txt` junto a los `.woff2` (la OFL exige que la licencia acompañe a la fuente) y anotar fuente, autor y licencia en `LICENCIAS.md`.
- [ ] **Paso 4: commit** `chore(fonts): Consola Mono recortada y con su licencia`.

### Task 7.2: Valores de la marca (tokens, fuentes, variantes)

**Files:** Modify `src/app/globals.css`, `src/app/[lang]/layout.tsx`, `src/lib/tokens-pago.ts`, `src/components/ui/variantes.ts`, `src/app/[lang]/opengraph-image.tsx`, `src/components/stripe-panel.tsx` (o `checkout/pago/formulario-pago.tsx` tras F1.2), `src/app/[lang]/not-found.tsx`, `src/components/license-section.tsx`, `src/components/sede-hero.tsx`.

- [ ] **Paso 1: colores** (valores de `design.md`): `--accent`/`--action` → café `#7C3B02` (texto sobre acción `#FFFFFF`, 8,46:1); `--foreground` → `#1F1A14`; **`--background` → arena `#FBF7F0`** (las superficies ya son blancas por F2.4); bordes `#D9C9B4` (decorativo) y `#8A7A66` (controles, 4,15:1); estados con sus parejas; familias `azul`, `coral`, `verde` con `hondo`, `profundo`, `medio`, `claro` y `bruma`; **`--ring` → `azul` `#1B607F`** (foco). Comprobar el contraste de cada par antes del commit. `--amber`, `--indigo` y `--yellow` salen; `--hero-ink` se queda.
- [ ] **Paso 1b: nombres de token** — declarar en `@theme` la lista cerrada de `design.md`: `cafe`, `cafe-hondo`, `cafe-profundo`, `cafe-medio`, `cafe-claro`, `cafe-bruma`; `azul|coral|verde` con `-hondo`, `-profundo`, `-medio`, `-claro`, `-bruma`; `coral-texto` (#8F2409); `arena`, `blanco`, `tinta`, `tinta-suave`, `apagado`, `borde`, `borde-control`; estados `exito`, `exito-fondo`, `error`, `error-fondo`, `aviso`, `aviso-fondo` (= `cafe-claro`), `info` (#0F3D52), `info-fondo` (= `azul-claro`); `ring` (= `azul`). Los nombres actuales son alias temporales: `--accent` y `--action` → `cafe`; `--foreground` → `tinta`; `--muted` → `apagado`; `--surface` → `superficie` (blanco); `--border` → `borde`; `--border-strong` → `borde-control`. **Antes de repuntar `--surface` y `--surface-deep`**, listar sus ~77 y ~7 usos y migrar cada uno a un token con nombre explícito: `surface-deep` **nunca** apunta a `cafe-claro` (#FEE0AC, amarillo saturado); sus usos pasan a `cafe-bruma`, salvo el rango de fechas confirmado y los avisos, que usan `cafe-claro`. La regla `surface-deep` de la compuerta debe quedar en 0.
- [ ] **Paso 2: forma** — `--radius-control: 12px`, `--radius-campo: 12px`, `--radius-card: 16px`, `--radius-sheet: 24px` (las tarjetas ya usan `rounded-card` desde F3/F4); chips y días del calendario en `9999px`. Además declarar `--radius-xs: 4px; --radius-sm: 8px; --radius-casilla: 6px; --radius-full: 9999px` y **sobrescribir** `--radius-md: 8px; --radius-lg: 12px; --radius-xl: 16px; --radius-2xl: 16px` para que cualquier `rounded-*` heredado caiga en la escala de `design.md` (22 `rounded-lg`, 20 `rounded-xl`, 10 `rounded-2xl`, 2 `rounded-md` hoy). En contenedores anidados el radio interior es el exterior menos su padding. La regla `radio-crudo` de la compuerta solo admite `rounded-control|campo|card|sheet|full|xs|sm|casilla` y debe quedar en 0.
- [ ] **Paso 2b: movimiento** — declarar `--duracion-corta: 150ms; --duracion-media: 250ms; --duracion-larga: 400ms; --curva-estandar: cubic-bezier(0.2,0,0,1); --curva-salida: cubic-bezier(0.4,0,1,1)`, y las capas `--capa-hover: color-mix(in srgb, var(--color-tinta) 8%, transparent)` y `--capa-pulsado: … 12% …` (hover solo con puntero: Tailwind 4 ya lo condiciona a `@media (hover:hover)`). Migrar `Despliegue`, `Skeleton`, las hojas, el cambio de paso y el calendario a esos tokens. `.rev`, `.rev-foto`, `.rev-regla` y `.titulo-entra` quedan **solo** en portada, hub y sede, nunca en `/reservar` ni `/traslados`. Reemplazar el bloque global de `prefers-reduced-motion` (hoy pone `0.01ms` y mata también los fundidos) por: sin `transform`, `clip-path` ni cambio de altura, solo opacidad con `animation-duration: 150ms`. Con `m.*`, `transition={{ duration: 0.25, ease: [0.2, 0, 0, 1] }}` y ramificar con `useReducedMotion()`. **Lo que no se anima:** el formulario de tarjeta de Stripe y su esqueleto, los montos y totales (cambian con fundido de 150 ms, sin conteo ascendente: retirar el conteo de `CifraAnimada` en los checkouts), el calendario durante el scroll vertical y el contenido de las pantallas de pago.
- [ ] **Paso 3: fuentes — lista cerrada de lo que se toca** (hallazgo del crítico):
  - `layout.tsx`: quitar `Instrument_Sans`, Bebas Neue y Bella Fashion; añadir `localFont` con los dos `.woff2` de Consola Mono (`display: 'swap'`, `variable: '--font-titulo'`, pesos 400 y 700, `fallback` = la pila monoespaciada de `design.md`). Si los titulares son siempre 700, Book va en su propia llamada a `localFont` con `preload: false` (el `preload` es por fuente, no por peso) o se deja fuera si no se usa. Un fallback monoespaciado de sistema no iguala las métricas de Consola Mono: revisar `adjustFontFallback` y medir el CLS.
  - `globals.css` `@theme inline` (líneas ~110-112): borrar `--font-sans: var(--font-cuerpo)` y `--font-script: var(--font-acento)`; declarar `--font-sans` con **la pila literal** (`-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`) y `--font-display: var(--font-titulo)`.
  - `globals.css` `body` (línea ~300): `font-family: var(--font-sans)` (ya no `--font-cuerpo`).
  - `globals.css` regla `h1, h2` (líneas ~318-324): peso 700, tracking de `design.md` (`--tracking-titulo: -0.02em`), sin el fallback Oswald/Arial Narrow; se conserva `font-synthesis: none` porque Book y Bold son reales.
  - `globals.css` `.acento` (líneas ~265-280): **se elimina**, y en `sede-hero.tsx` (líneas ~79-80) el titular se pinta como texto plano (`start + emphasis + end`, sin estilo especial; el contrato de `sedes-tipos.ts` no cambia).
  - `not-found.tsx` (líneas ~25-37) y `license-section.tsx` (línea ~39): quitar `font-normal` y migrar al nuevo `--tracking-titulo`.
  - `stripe-panel.tsx` (líneas ~76, ~86) carga Instrument Sans por Google Fonts para Stripe Elements: quitar `STRIPE_FUENTES` y poner `fontFamily` de la pila del sistema en `TOKENS_PAGO` (la prueba de `tokens-pago` lo compara con `--font-sans`).
- [ ] **Paso 4: Stripe y OG** — `TOKENS_PAGO` con los hex nuevos (comparados con `globals.css` por su prueba) y `opengraph-image.tsx` a mano (no carga fuentes; solo cambian colores).
- [ ] **Paso 5: variantes** — `variantes.ts`: `principal` café con texto blanco; `secundario` con borde `borde-control` y texto café; `peligro` con `error`. **Contrato visual de `Button`** (este es el paso donde la geometría de F3 cambia a propósito; la prueba de `variantes` se actualiza línea por línea y conserva R5: solo `principal` usa el color de acción). Base común: `inline-flex items-center justify-center gap-2 rounded-control px-6 text-base font-semibold leading-tight tracking-[0.01em] min-h-12 sm:min-h-11 transition-[background-color,transform] duration-150 ease-[var(--curva-estandar)] active:scale-[0.98] motion-reduce:active:scale-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed aria-disabled:cursor-not-allowed`; **no se usa `opacity` para deshabilitar**. `principal`: `bg-cafe text-white hover:bg-cafe-hondo active:bg-cafe-profundo`; deshabilitado y `aria-disabled`: `bg-cafe-bruma text-apagado`. `secundario`: `bg-superficie text-cafe border border-borde-control hover:bg-cafe-bruma active:bg-cafe-claro`; deshabilitado `bg-cafe-bruma text-apagado border-transparent`. `texto`: `bg-transparent text-cafe min-h-11 px-3 hover:bg-cafe-bruma` (se elimina `acento`, queda idéntico; las acciones meta como «Volver» usan `tono="neutro"` con `text-tinta-suave` e icono de 16). `peligro`: `bg-error text-white hover:bg-[color-mix(in_srgb,var(--color-error)_92%,var(--color-tinta))]`. Tamaños: `md` es el de la base; se elimina `sm`; `icono` es `size-12 rounded-full p-0` con icono de 24 (48 × 48 también en escritorio); prop `bloque` agrega `w-full` (barra inferior móvil). **Etiquetas largas:** hasta 2 renglones por debajo de 640 px (`h-auto py-3 text-balance`), nunca se truncan (el monto debe verse); verificar con «Pagar $12,450.00 MXN a Yellowtail Sportfishing» en 360 px, en es y en en. **`cargando`:** `CircleNotch` de 20 con `animate-spin` y «Procesando…», conserva su ancho, sigue en `aria-disabled` con la razón visible abajo; con reducir movimiento el icono pulsa en opacidad (1,2 s) en lugar de girar. El foco es el anillo de 2 px `ring` con 2 px de desfase en todas las variantes, desfase pintado con el color de la superficie que lo contiene.
- [ ] **Paso 5b: campos** — `CAJA_CAMPO = 'min-h-12 sm:min-h-11 rounded-campo border border-borde-control bg-superficie px-4 text-base text-tinta placeholder:text-apagado focus-within:border-2 focus-within:border-ring disabled:bg-cafe-bruma disabled:text-apagado'`; `CAJA_CAMPO_ERROR` pone `border-error` también de 2 px y no cambia el relleno. El borde decorativo `borde` (1,62:1) no delimita un control. Todo `input`, `select` y `textarea` usa `text-base` como mínimo (16 px, evita el zoom de iOS); la regla `texto-chico-en-campo` de la compuerta debe quedar en 0. Para que el borde de 2 px no mueva el contenido, el campo compensa con `box-shadow: inset 0 0 0 1px` en foco o con padding.
- [ ] **Paso 5c: `Field`** — compone en vertical: etiqueta (14/600 `tinta`, `gap-2` sobre el control), control, ayuda (14/400 `apagado`) y error. El error ocupa un renglón `min-h-5` **siempre montado** (aunque esté vacío), con `WarningCircle` de 16 `weight="fill"` y texto de 14 `text-error`, **sin animar la altura**, solo fundido de opacidad de 150 ms; si hay error y ayuda, el error reemplaza a la ayuda en el mismo renglón; con dos renglones de error la altura se mide una vez y se reserva (máximo 2 líneas en 360 px, o se acorta el copy). `Despliegue` queda para tarjetas y el código promocional, no para errores de campo. (En F3 `Field` conserva el comportamiento actual de `ErrorDeCampo`; este cambio es deliberado y de F7.)
- [ ] **Paso 6: commit** `feat(marca): valores de Sun Baja Experience` (todavía sin desplegar).

### Task 7.3: Pasada de componentes (cambios visuales deliberados)

> «Solo valores» era falso para estos puntos (medidos el 2026-10-15): 16 `shadow-[...]` arbitrarias y 18 `shadow-*` sueltas, dos brillos amarillos con `rgba(255,222,0,…)`, 5 `ring-accent`, 2 `text-action` y h1/h2 con clases de tamaño sueltas.

- [ ] **Sombras:** convertir las 16 arbitrarias (p. ej. `checkout-section-card.tsx:54`, `booking-confirmation.tsx:167`, `checkout-loading-shell.tsx:58`, `cookie-notice`, `field-popover`) y las 18 `shadow-*` a tres tokens `--shadow-n0` (ninguna), `--shadow-n1` (barra inferior móvil) y `--shadow-n2` (popover, toast, hoja) con los valores de `design.md`: `--shadow-n1` = `0 -1px 0 #D9C9B4, 0 -6px 16px rgb(31 26 20 / .08)` (solo barra inferior móvil) y `--shadow-n2` = `0 8px 24px rgb(31 26 20 / .14)` (popover, toast, hoja y diálogo). El resumen, las tarjetas, el calendario y las tarjetas de servicio quedan en `n0` con borde `borde`. La regla `sombra-cruda` de la compuerta debe quedar en 0.
- [ ] **Brillo amarillo:** el panel de pago (`rgba(255,222,0,…)`, líneas ~399-404 de `stripe-panel.tsx` antes del split) **se elimina** (no se crea `--brillo-accion`: `design.md` prohíbe el brillo decorativo).
- [ ] **Foco:** los 5 `ring-accent` pasan a `focus-visible:ring-ring`.
- [ ] **`text-action` (2 usos):** el icono `Warning` sobre `bg-action/10` (`checkout-view.tsx:~1313`, `grupo-servicio.tsx:~114`) pasa a `text-aviso` sobre `bg-aviso-fondo`.
- [ ] **Titulares:** definir clases semánticas `texto-display`, `texto-pagina`, `texto-seccion` y `texto-paso` con la escala de `design.md` (40/64, 36/56, 28/36, 24/28) y aplicarlas a los h1/h2 de `sede-hero.tsx` (~38/60/76 px), `hub-hero.tsx` (~38/60/72), el h1 de `servicio/[empresa]/[servicio]/page.tsx` (`text-5xl/6xl`) y `encabezado-compra.tsx` (`text-2xl/3xl`). La monoespaciada es más ancha: los `max-w-[19ch]` calibrados para Bebas condensada (comentario en `globals.css`) se revisan por desbordamiento en móvil de 360 px, en es y en. **Escala completa**, como clases semánticas en `@layer components`, cada una con tamaño, peso, interlineado, tracking y `text-wrap: balance` juntos; corte en `sm` (640 px): `texto-display` 40 → 64, 1,05, −0,02 em, 700 mono; `texto-pagina` 36 → 56, 1,1, −0,02 em, 700 mono; `texto-seccion` 28 → 36, 1,15, −0,01 em, 700 mono; `texto-paso` 24 → 28, 1,2, −0,01 em, 700 mono; `texto-subtitulo` 20 → 22, 1,3, 600 cuerpo; `texto-cuerpo` 16, 1,5; `texto-pequeno` 14, 1,45; `texto-etiqueta` 16, 1,2, 0,01 em, 600; `texto-pie` 12, 1,4, 0,01 em. Las clases mono llevan `overflow-wrap: anywhere` y `hyphens: manual`. Se elimina `--tracking-titulo` único y la regla global `h1, h2` (los h2 que son rótulos pequeños llevan `texto-subtitulo` o `texto-pequeno`). Ningún texto baja de 12 px: las ~22 ocurrencias de `text-[10px]` y `text-[11px]` pasan a `texto-pie`. Se prohíben `uppercase` y `tracking-wider` (caja de oración; incluye el `kicker` de `encabezado-compra.tsx`, que se elimina); la regla `mayusculas-crudas` debe quedar en 0. Probar «Reserva tu paseo en lancha» y su par en inglés a 360 px: no más de 3 renglones en `texto-pagina`.
- [ ] **Objetivo táctil:** el contrato de `Button` de 7.2 Paso 5 (48 px en móvil, 44 px en escritorio) reemplaza los 40 px de F3 a F6; se actualiza la prueba de `variantes`.
- [ ] **Card y chips:** se elimina `Card elevada` y `variant="elevated"` de `CheckoutSectionCard` (hoy `shadow-[0_18px_45px…]`). `ChipActividad`: `h-7 rounded-full px-3 text-[14px] font-semibold gap-1.5` con icono de 16 (`Waves`, `Buildings`, `Mountains`, `weight="bold"`); mar `bg-azul-claro text-azul`, ciudad `bg-coral-claro text-coral-texto`, outside `bg-verde-claro text-verde`; nunca flota en pill sobre una foto (va en el cuerpo de la tarjeta o con fondo opaco). `AvisoEstado`: colores `exito/exito-fondo`, `error/error-fondo`, `aviso/aviso-fondo`, `info/info-fondo`. Iconos: 16 en texto, 20 en botones, 24 en navegación; `bold` para acciones y `regular` para decoración.
- [ ] **Héroe y secciones:** `SectionShell` pasa a `fondo: 'arena' | 'blanco' | 'cafe-bruma'` (se eliminan `papel`, `bruma` y `bruma-profunda`; `cafe-claro` nunca es fondo de sección) alternando bandas en ese orden; la «regla» que abre la sección usa `bg-cafe-medio` (decorativa) de 48 × 2 px, nunca `cafe`. El scrim del héroe es un degradado en `tinta`, no negro: `--scrim-hero: linear-gradient(to top, rgb(31 26 20 / .72) 0%, rgb(31 26 20 / .35) 45%, rgb(31 26 20 / 0) 75%)`; el texto sobre foto (`--hero-ink`) debe dar ≥ 4,5:1 contra la zona más clara bajo el titular, medido con la foto real.
- [ ] **`Skeleton` y toast:** `Skeleton` pasa a `bg-cafe-bruma` con `@keyframes pulso-esqueleto { 50% { opacity: .55 } }` de 1,2 s solo bajo `motion-safe`, y hereda el radio del elemento que reemplaza (el esqueleto del formulario de tarjeta no pulsa: Task 1.2). `Toast`: `rounded-control shadow-n2`, 5 s y descartable, anclado a `bottom: calc(var(--barra-alto) + 8px)` en móvil, región `aria-live="polite"`; no se usa para errores que bloquean (esos usan el aviso de 8.3b).
- [ ] **Compuerta de marca:** `texto-chico-en-campo`, `mayusculas-crudas`, `radio-crudo`, `sombra-cruda` y `surface-deep` en **0** (más `motion-completo`, `boton-crudo`, `input-crudo`, `img-cruda`, `paleta-cruda` y `capas-ui` ya en 0 desde F6) antes de pedir la revisión del dueño.
- [ ] **Verificación:** `verificar` completo, `guardia` en 0 salvo exentos, build; revisión del dueño de portada, hub, sede, servicio, los tres checkouts, traslados, confirmación y páginas de error, en es y en. PUNTO DEL DUEÑO.
- [ ] **Commit** `feat(marca): sombras, foco, titulares y brillos con la identidad nueva`.
- [ ] F7 **no se despliega sola**: sale junto con F8.

---

## F8 — Página de reserva nueva (sale con F7)

> Especificación: `docs/design/design-components.md` (secciones «Página de reserva», «Selección de fecha» y «Tarjeta de paso»). Decisiones del dueño: se quita **solo el stepper numerado**; **tres pasos en todas las rutas** — **Viaje** (fecha, personas, **extras**) · **Tus datos** (contacto + recogida u hotel + notas) · **Pago**; con dos empresas, «Pago 1 de 2» y «Pago 2 de 2» son sub-pasos dentro de Pago; los traslados también quedan en 3 (contacto + recogida en «Tus datos»); paquetes de varias noches con **duración fija**; cabecera mínima con flecha, logo e idioma; calendario con alcance recortado (sin «pocos lugares» ni corte por cupo de hospedaje). **Ronda 4 del crítico (recorridos de todos los servicios) + derivación PFD (R1–R5)** añadieron: un solo botón por pantalla en Pago con la barra **dentro de Stripe**, un patrón único de aviso con acción, historial por paso y borrador en la pestaña, una sola flecha, regreso de traslados **vacío y obligatorio**, bajo demanda como «reserva confirmada al pagar», y controles de fecha y personas según el tipo de servicio (pesca, paseo, hospedaje por noche, bajo demanda, transporte). **Los precios en USD ya se derivan del tipo de cambio de la sede: siempre existen**, así que no hay estado «sin precio USD» que proteger.

### Task 8.0: Historial por paso, borrador en la pestaña y una sola flecha (PFD R4)

**Files:** Create `src/lib/borrador-reserva.ts`, `tests/borrador-reserva.test.cjs`, `src/lib/origen.ts`, `tests/origen.test.cjs`; Modify `checkout-view.tsx`, `pedido/pedido-paquete.tsx`, `traslado-view.tsx`, `lang-switch.tsx`, `continuar-reservacion.tsx`, `lib/pendientes.ts`, `lib/booking-href.ts`.

> Hallazgos (verificados): los pasos son estado de React, no historial, así que el Atrás del navegador sale de la compra (en Android, el gesto de atrás); todo lo previo a crear la reserva vive en memoria y en `sessionStorage` solo queda `checkoutId`; `lang-switch.tsx:121` hace `router.push(pathname + window.location.search)`, lo que remonta el árbol y vuelve a Viaje con la moneda recalculada por idioma; `Pendiente.ruta` guarda el idioma con que se creó; `volverHref` (`checkout-view.tsx:~1402`) manda `/${lang}?day=&time=&people=` a una portada que ya no los lee; hay dos flechas con funciones distintas en el plan.

- [ ] **Paso 1: borrador (módulo puro con prueba primero).** `lib/borrador-reserva.ts` exporta `guardar(clave, estado)`, `leer(clave)` y `borrar(clave)` sobre `sessionStorage` (con `try/catch`: puede lanzar en modo privado), con `version` en el JSON y una vigencia de 4 horas; descarta lo ilegible o de otra versión. Guarda fecha(s), personas, extras, moneda, contacto, recogida, deslinde **no** (el deslinde se acepta de nuevo siempre) y el paso actual. Clave por ruta y producto (`salysol:borrador:<ruta>:<slug>`). **Autorizado por el dueño: solo en la pestaña, se borra al confirmar el pago.** Pruebas: ida y vuelta, versión distinta, vigencia vencida, JSON roto, almacenamiento no disponible. El borrador se restaura con `useSyncExternalStore` o con el patrón `useLayoutEffect` que ya usa `checkout-view.tsx:~104–139`, para evitar un mismatch de hidratación.
- [ ] **Paso 2: historial por paso.** Cada paso es una entrada de historial con `?paso=viaje|datos|pago` con `window.history.pushState` al avanzar y `window.history.replaceState` dentro del mismo paso (se integra con el router y `useSearchParams` sin recargar: `single-page-applications.md`). **No** `router.push/replace`: `reservar/page.tsx` es dinámica y cada navegación del router repediría el RSC y repetiría `getServicioDetalle`/`getPaqueteDetalle`/`getTraslados` contra el backend en cada paso; `router.push` queda solo para cambios de ruta o de idioma. El Atrás del navegador vuelve al paso anterior; el paso se deriva de `useSearchParams()` (una sola fuente de verdad; no hay listener de `popstate` aparte). Un paso al que no se ha llegado se redirige al último válido.
- [ ] **Paso 3: idioma.** Cambiar de idioma conserva `?paso=` y restaura el borrador; la moneda por idioma pasa a ser solo el **valor inicial** (el borrador manda después). `ContinuarReservacion` abre la ruta en el idioma **actual**, no en el guardado.
- [ ] **Paso 4: una sola flecha.** La flecha de arriba a la izquierda es siempre «paso anterior»; en Viaje es «salir» al origen. `lib/origen.ts` (con prueba) resuelve el origen: parámetro `origen` explícito (sede, servicio o portada) y, si falta, la página de la sede; se eliminan `day/time/people` de `volverHref`. `?moneda=` (que llevan todos los enlaces de `booking-href.ts`) se lee en Viaje.
- [ ] **Paso 5:** `tsc`, `eslint`, `npm test`, `build`. Recorridos: recargar en cada paso, Atrás y Adelante, cambio de idioma a media compra, entrada con query, entrada desde «Continuar reservación». **Paso 6: commit** `feat(reserva): historial por paso, borrador en la pestaña y flecha única`.

### Task 8.1: Tres pasos en las cuatro rutas

**Files:** Modify `src/lib/pasos-checkout.ts`, `tests/pasos-checkout.test.cjs`, `checkout-view.tsx`, `pedido/pedido-paquete.tsx`, `traslado-view.tsx`, `checkout-stepper.tsx` (se elimina el numerado), `src/app/[lang]/dictionaries/{es,en}.json` (`checkout.stepper`).

> Hallazgos del crítico verificados: `ORDEN_PASOS` es una constante global de 4 pasos (`pasos-checkout.ts:7-9`); el literal `4` aparece en `checkout-view.tsx:~1249`, `traslado-view.tsx:~595` y `pedido-paquete.tsx:~408-414, ~457, ~531-532` (`actual: 4 + indicePago`); las claves `checkout.stepper` son `trip/contact/extras/payment` y `pedido-paquete.tsx:~404-415` arma `steps`/`etiquetasCortas`; en servicio suelto «detalles» son los extras (`checkout-view.tsx:~1590-1620`) y en paquete una tarjeta por servicio (`pedido-paquete.tsx:~648-654`).

- [ ] **Paso 1: prueba primero** en `tests/pasos-checkout.test.cjs`: `ORDEN_PASOS` es `['viaje','datos','pago']`, `numeroDePaso('pago') === 3`, y `estadoDeTarjeta` mantiene las reglas actuales (oculto / activo / completado / editando). Verla fallar.
- [ ] **Paso 2:** cambiar `PasoId` y `ORDEN_PASOS` a `viaje | datos | pago` (una sola constante vale porque las cuatro rutas quedan iguales). Los sub-pasos de pago por empresa son estado propio del paso Pago (`indicePago`, `totalPagos`), no pasos nuevos: se elimina `actual: 4 + indicePago` y todo `4` literal.
- [ ] **Paso 3:** mover los **extras** al bloque de Viaje (servicio suelto: `bloque-extras` desde «detalles»; paquete: la tarjeta por servicio) y unir `bloque-contacto` + `bloque-recogida` en «Tus datos» (los bloques existen desde F5). Se parte `GrupoServicio`: **Viaje** = personas, extras, tipo de traslado y fecha(s); **Tus datos** = punto de recogida y zona (el tipo de traslado decide si hay regreso y zona). **Validación con dueño (PFD R5):** una función `validarTodo()` devuelve `{ paso, campo, mensaje }` del primer problema; `iniciarPago` y el `enviar` de cada ruta la usan en lugar de `document.getElementById(...).focus()` (que no hace nada si el campo no está montado) y de `setEditando(...)`. Un 400 del servidor con errores por campo se enruta con un mapa `campo → paso` (`lib/errores.ts`, con prueba). El problema se muestra con el patrón de aviso de la Task 8.3b, cuya acción principal es «Corregir [dato] en [paso]»: navega a ese paso (entrada de historial) y **enfoca el campo después de montar el paso**. Casos que hoy solo se detectan en Pago y deben enrutarse igual: cambiar la fecha de inicio tras fijar la de regreso (`pedido-paquete.tsx:~294`) y cambiar el tipo de traslado tras elegir la recogida (`traslado-view.tsx:~373`).
- [ ] **Paso 4:** diccionarios: sustituir `checkout.stepper` (`trip/contact/extras/payment`) por `viaje/datos/pago` en es y en, con «Viaje», «Tus datos», «Pago» y «Paso N de 3»; reiniciar `npm run dev` (Turbopack cachea los JSON).
- [ ] **Paso 5: límite de campos** — contar los controles de «Viaje» por ruta (fecha, personas, extras obligatorios y opcionales). Si en alguna ruta pasan de ~7, **parar y avisar al dueño** antes de seguir (PFD R1): los opcionales se pliegan bajo «Más opciones» en vez de crear un cuarto paso.
- [ ] **Paso 6:** recorridos manuales de F5 en las cuatro rutas, incluido el rechazo en «Pago 2 de 2». **Paso 7: commit** `feat(checkout): tres pasos en todas las rutas; extras en Viaje`.

### Task 8.2: Cabecera mínima sin navbar y `--nav-alto`

**Files:** Create `src/components/reserva/cabecera-minima.tsx`; Modify el layout de `/reservar` y `/traslados`, `src/app/globals.css`.

- [ ] Flecha de volver (48 × 48; su significado y destino se definen en la Task 8.0: **una sola flecha**), logo redondo de 32 y selector ES/EN; sin navbar completo en `/reservar` y `/traslados`; el cambio de idioma conserva `?paso=` y restaura el borrador (Task 8.0). `ContinuarReservacion` sigue fuera del checkout.
- [ ] **Composición de la cabecera:** alto 56, fondo `arena`, `border-b border-borde`, sin sombra ni blur; z-index en una escala declarada en `globals.css`: `--z-cabecera: 40; --z-barra: 50; --z-hoja: 60; --z-toast: 70`. Cuadrícula `grid-cols-[48px_1fr_auto]`: flecha a la izquierda, logo de 32 centrado, selector a la derecha. El selector es una variante compacta de `LangSwitch`: dos segmentos «ES | EN» en `texto-pequeno`, 44 × 44 cada uno, el activo con `bg-cafe-bruma text-cafe font-semibold`, sin banderas ni mayúsculas decorativas. El logo es una imagen sin enlace mientras haya una orden con dinero retenido; en cualquier otro caso enlaza a la portada. Si el logo definitivo no ha llegado, se usa el actual redondo sin recortarlo. Verificar que no desborda en 360 px, en es y en.
- [ ] **`--nav-alto` por ruta:** `globals.css:~60-69` ya avisa que este token se desincronizó una vez. Añadir una clase `reserva-minima` en el layout de esas rutas con `--nav-alto: 56px` por debajo de 1024 px y `0px` desde 1024 px (la cabecera es `sticky top-0` por debajo de 1024 px y estática desde ahí) y `--banda-alto: 0px`. Re-verificar sus consumidores: `pagina-checkout.tsx:~40`, `checkout-loading-shell.tsx:~26,37`, `checkout-section-card.tsx:~189` (scroll-mt), `toast.tsx:~98`, `traslados/page.tsx:~62`, `pedido-paquete.tsx:~365,456,478`, `booking-confirmation.tsx:~132` (`checkout-stepper.tsx` desaparece en 8.3). La confirmación y las pantallas de fallo de la misma ruta usan la misma cabecera.
- [ ] Commit `feat(reserva): cabecera mínima y --nav-alto por ruta`.

### Task 8.3: Título grande, resumen plano y pasos con nombre

- [ ] Título de página 36 px móvil / 56 px escritorio (`texto-pagina`); resumen en elevación 0 (ya en `n0` por F7.3); se elimina `checkout-stepper.tsx`. Las tarjetas de paso muestran «Paso N de 3» y su título en `texto-paso` (24 px móvil / 28 px escritorio, Consola Mono 700). El nombre del paso en el asistente móvil usa la misma clase (24 px). **Regla del título en móvil:** en Viaje se ve `texto-pagina` (36) y debajo «Paso 1 de 3» en `texto-pequeno apagado` más el nombre del paso en `texto-paso`; en «Tus datos» y «Pago» el título de página no se repite: queda solo el nombre del paso en `texto-paso` y debajo una línea de contexto `texto-pequeno apagado` («Reserva tu pesca · sáb 7 nov»), para no apilar dos titulares mono. **`CheckoutSectionCard`:** estados `abierto`, `completado` y `pendiente` (`editando` y `suspendido` se retiran y mapean a `abierto` y `pendiente`). Cabecera: «Paso N de 3» en `texto-pequeno font-semibold text-apagado` y el título en `texto-paso`; `pendiente` pinta el título en `text-apagado` y no abre; `completado` muestra en una línea título + resumen («Sábado 7 de nov · 2 personas») + la acción «Modificar» (variante `texto`, 44 de alto; reemplaza «Cambiar» y «Listo» en es y en). Padding 24, 32 desde `lg`. La altura anima con `Despliegue` en 250 ms (solo opacidad con reducir movimiento).
- [ ] Commit `feat(reserva): título grande, resumen plano y pasos con nombre`.

### Task 8.3b: Un solo patrón de aviso con acción (PFD R3)

**Files:** Create `src/components/ui/aviso-accion.tsx`, `src/lib/problema-reserva.ts`, `tests/problema-reserva.test.cjs`; Modify `checkout-view.tsx` (`volverPorSinCupo`), `pedido/use-pago-pedido.ts`, `pedido/aviso-fallo.tsx`, `traslado-view.tsx`, `pagina-checkout.tsx` (el slot `aviso`).

> Hallazgos: hoy sin cupo, rechazo de tarjeta y apartado vencido se resuelven distinto por ruta (servicio suelto manda a Viaje con un aviso y fecha alternativa; paquete de una empresa se queda en Pago con un bloque de error; cruza-empresa tiene pantalla de fallo completa; traslados recarga). El apartado no tiene cuenta regresiva.

- [ ] **Paso 1: tipos y textos (módulo puro con prueba primero).** `lib/problema-reserva.ts` define `Problema = { tipo, queOcurrio, queSeConserva, accionPrincipal, accionSecundaria? }` con `tipo` en `sin_cupo | tarjeta_rechazada | apartado_vencido | red | catalogo_caido | dato_previo`, y una función `problemaDe(error, contexto)` que lo construye. Pruebas: cada tipo produce una acción principal, nunca más de una; `dato_previo` incluye `{ paso, campo }`.
- [ ] **Paso 2: acciones.** `sin_cupo` → «Elegir otra fecha» (a Viaje, con la fecha alternativa si el servidor la propone); `tarjeta_rechazada` → «Probar otra tarjeta» (conserva la retención del primer pago); `apartado_vencido` → «Volver a apartar mi lugar»; `red` → «Reintentar» (conserva lo capturado); `catalogo_caido` → «Escribirnos por WhatsApp» y volver al origen; `dato_previo` → «Corregir [dato] en [paso]» (Task 8.1).
- [ ] **Paso 3: componente.** `AvisoAccion` (aviso de `design-components.md`) se monta **siempre en el mismo sitio**, encima de la barra inferior en móvil y encima del botón de la tarjeta en escritorio; `role="alert"`. **Foco:** no se envía a la acción principal (el lector anunciaría dos veces y se saltaría el mensaje); o el foco se queda donde está y manda `role="alert"`, o se enfoca el **contenedor** del aviso (`tabIndex={-1}`), nunca la acción. **Estructura y tono:** `rounded-control p-4`, icono de 20 a la izquierda y cuerpo de 14 con título (`queOcurrio`, 14/600), texto (`queSeConserva`, 14/400) y debajo la acción; `sin_cupo`, `apartado_vencido` y `dato_previo` usan el tono `aviso`; `tarjeta_rechazada`, `red` y `catalogo_caido` usan `error`; nunca colores de actividad. **Botón único por pantalla:** mientras haya un problema bloqueante (`sin_cupo`, `tarjeta_rechazada`, `apartado_vencido`, `catalogo_caido`) la barra oculta su botón `principal` y la acción del aviso pasa a ser el botón de la pantalla (variante `principal`); en problemas no bloqueantes (`red`, `dato_previo`) la barra conserva su botón y la acción del aviso es `secundario`. En móvil el aviso se fija encima de la ranura de estado de la barra; en escritorio va dentro de la tarjeta, justo encima del botón del paso. Entra con fundido de 150 ms y, si empuja contenido, con `Despliegue` en 250 ms; en la barra fija no empuja nada. Reemplaza los tratamientos distintos de las cuatro rutas.
- [ ] **Paso 4: cuenta regresiva real.** Solo si el servidor devuelve el vencimiento del apartado (`vence_en`, que ya expone al crear y reanudar una orden): «Tu lugar está apartado, quedan 14:32» (icono de reloj). Antes de existir el apartado no se muestra nada. Al llegar a 0 pasa a `apartado_vencido`.
- [ ] **Paso 5:** recorridos: sin cupo al pagar en cada ruta, rechazo de tarjeta en el primer y en el segundo pago, apartado vencido, red caída, servicio nulo. **Paso 6: commit** `feat(reserva): un solo aviso con acción para todos los problemas`.

### Task 8.4: Asistente de un paso en móvil y un solo botón por pantalla (PFD R1, R2, R5)

**Files:** Create `src/components/reserva/{linea-progreso,barra-inferior,asa-resumen}.tsx`, `src/lib/etiqueta-boton.ts`, `tests/etiqueta-boton.test.cjs`; Modify `checkout/pago/formulario-pago.tsx`, `checkout/pago/tarjeta-como-pagas.tsx`, `pedido/use-pago-pedido.ts`.

> Hallazgos (verificados): el paso Pago tiene **dos acciones distintas**: la primera crea la reserva u orden y retiene (botón de `TarjetaComoPagas`, `stripe-panel.tsx:~389-420`, o `continueToPayment` en `pedido-paquete.tsx:~871`); la segunda confirma el cobro con `stripe.confirmPayment` dentro de `PaymentForm` (`stripe-panel.tsx:~134`), que solo funciona dentro de `<Elements>`. En cruza-empresa son tres pantallas (Cómo pagas, Pago 1, Pago 2).

- [ ] **Pantallas de Pago (decisión del dueño: la barra va dentro de Stripe).** Pago se parte en sub-pantallas con **una acción cada una**: **(a) Cómo pagas** (moneda junto al total, forma de pago, promo, deslinde, verificación antibots) → botón «Continuar a la tarjeta», que crea la reserva u orden y retiene; **(b) Tarjeta de cada empresa** → «Pagar $X a [empresa]». La barra inferior de la pantalla (b) se renderiza **dentro de `<Elements>`** (mismo mecanismo de portal que ya usa `TarjetaComoPagas`) para poder llamar a `elements.submit()` y `confirmPayment`; el botón «Pagar» interno de `PaymentForm` se quita.
- [ ] **Regla de la etiqueta (módulo puro con prueba primero).** `lib/etiqueta-boton.ts`: `etiquetaDeBoton({ paso, subpaso, montoConfirmado, empresa, cargos })`. Un **monto solo aparece cuando el servidor lo confirmó** (o la vista previa está probada como exacta): antes dice «Continuar a pago»; hospedaje por noche y todo servicio con precio por estrategia dice «Estimado» en el resumen hasta que el servidor responde. Pruebas: sin monto confirmado nunca hay cifra; con monto, el texto incluye empresa y cifra; «Pago 1 de 2» y «Pago 2 de 2».
- [ ] **Tres segmentos y sub-pasos.** La línea de progreso mantiene tres segmentos sin números (una lista `<ol>` con `aria-current="step"` en el segmento activo y el texto «Paso 3 de 3: Pago»; no `role="progressbar"`); «Pago 1 de 2 · [empresa] · $X» va en la **primera línea de la pantalla** (PFD R2) y no añade segmentos. En la pantalla (b) de cruza-empresa, la hoja «Ver resumen» muestra cada cargo con su estado (pendiente, retenido, cobrado) y el aviso de doble retención.
- [ ] **«Atrás» tras retener dinero.** Creada la orden, la flecha de arriba pasa a «Cancelar y liberar mi lugar» con confirmación que explica la consecuencia (se libera el cupo y se revierte la retención); nunca aparece como un «atrás» silencioso.
- [ ] **Teclado, Stripe y antibots.** Mientras un campo tiene el foco (`visualViewport`), la barra fija pasa a estática al final del contenido; los campos de texto usan `enterkeyhint="next"`. El iframe de Stripe y 3DS quedan por encima de la barra (`z-index`). El estado de la verificación antibots forma parte de la razón del botón deshabilitado («Verificando que eres una persona…»). `padding-bottom: env(safe-area-inset-bottom)`.
- [ ] **Resto del asistente.** En < 640 px: un paso por pantalla, sin tarjetas plegables; flecha única arriba a la izquierda (Task 8.0); el asa «Ver resumen · $X» abre la hoja; el botón deshabilitado dice qué falta. El estado vive en el reducer existente y en el borrador; el cambio de paso lleva el foco al título y se anuncia con `aria-live`. Pantallas de reanudación (`retomar` o recarga) muestran **solo Pago**, con el resumen construido desde el pedido del servidor, **no** con tarjetas de Viaje y Datos rellenadas con valores inventados (`pedido-paquete.tsx:~557-574` pinta hoy `estado.inicio ?? minDate` y contacto vacío).
- [ ] **Presupuesto de la barra (< 640 px):** asa 48 (área táctil de 48, píldora visual de 40) + 8 + línea de progreso 4 + 12 + botón 48 + 8 + ranura de razón 20 + 12 + `env(safe-area-inset-bottom)`, unos 160 px más la safe-area. Se mide con `ResizeObserver` y se publica como `--barra-alto`. El contenedor de página usa `padding-bottom: calc(var(--barra-alto) + 16px)` y `scroll-padding-bottom` igual (ningún foco queda tapado por la barra); el toast se ancla a `calc(var(--barra-alto) + 8px)`.
- [ ] **Un solo sitio por tipo de mensaje:** la razón del botón deshabilitado va **debajo** del botón (ranura de 20 px reservada solo en los pasos con botón); la cuenta regresiva del apartado va **encima** del botón en su propia píldora (`bg-cafe-claro text-cafe-profundo`, 32 de alto, `Clock` de 16). Si coinciden, la cuenta regresiva queda arriba y la razón abajo. Ambas alturas se reservan siempre para que nada brinque. (Esto resuelve la contradicción entre `design-guidelines.md` y `design-components.md`.)
- [ ] **Estructura sin `transform` en ancestros:** la barra, la cabecera y el aviso son **hermanos**, no hijos, del contenedor que desliza entre pasos (un ancestro con `transform` rompe `position: fixed`). El deslizamiento (`translateX(24px) → 0`, 250 ms, `curva-estandar`) solo se aplica al contenido del paso. **Las pantallas de Pago no deslizan**: solo fundido de 150 ms. El contenedor de Stripe nunca lleva `transform`, `filter` ni `will-change`.
- [ ] **Asa y progreso:** el asa es una fila de 48 con `texto-etiqueta`, «Ver resumen · $4,100 MXN» (`tabular-nums`; sin monto confirmado lleva el rótulo «Estimado» al lado, igual en asa, resumen y barra), `CaretUp` de 16 a la derecha, borde superior `borde` y fondo `blanco`; el cambio de monto hace fundido de 150 ms. La línea de progreso son 3 `<li>` de 4 px de alto, `rounded-full`, `gap-2`, ancho completo; completados y actual en `bg-cafe`, pendientes en `bg-cafe-claro`; el relleno anima con `transform: scaleX` desde la izquierda en 250 ms (no `width`); «Paso 2 de 3: Tus datos» va `sr-only`. Estados de cargo en la hoja de resumen: `Clock` (pendiente), `Lock` (retenido) y `CheckCircle` (cobrado), con texto en el mismo renglón y colores de estado, nunca de actividad.
- [ ] **Layout en escritorio (≥ 1024 px):** `grid grid-cols-[minmax(0,640px)_minmax(300px,360px)] gap-8 justify-center max-w-[1120px] mx-auto px-8` (640 + 360 + 32 no cabe en 960 px: las columnas se comprimen sin desbordar y la de pasos nunca baja de 560). La columna del resumen es `sticky top-6` con `max-h-[calc(100dvh-48px)] overflow-y-auto` para que dos empresas con extras no queden cortadas. Entre 640 y 1023 px es una sola columna con el resumen **debajo** del último paso y sin barra inferior (el asistente de una pantalla es solo < 640 px).
- [ ] **Copy de la barra:** «Estimado», «Cancelar y liberar mi lugar» y «Seguir con mi reserva» van en el diccionario es/en; ninguna etiqueta de botón lleva guion largo; las razones («Elige una fecha para continuar», «Verificando que eres una persona…») caben en un renglón en 360 px, también en inglés.
- [ ] **Casos de servicio nulo y catálogo caído:** pantalla propia con el patrón de la Task 8.3b (`catalogo_caido`).
- [ ] Recorrido manual en móvil real y en escritorio de las cuatro rutas, incluida la de cruza-empresa con rechazo en «Pago 2 de 2». PUNTO DEL DUEÑO.
- [ ] Commit `feat(reserva): asistente móvil con un botón por pantalla y la barra dentro de Stripe`.

### Task 8.5: Calendario completo según el tipo de servicio (alcance recortado)

**Files:** Create `src/components/ui/calendario/{calendario,leyenda,atajos}.tsx`, `src/lib/rango-paquete.ts`, `src/lib/control-fecha.ts`, `tests/rango-paquete.test.cjs`, `tests/control-fecha.test.cjs`; Modify `checkout-view.tsx`, `pedido/fecha-paquete.tsx`, `pedido/grupo-servicio.tsx`, `traslado-view.tsx`, `date-field.tsx`; Delete `checkout-calendar.tsx`, `lib/calendario-semana.ts` y `tests/calendario-semana.test.cjs` (cuando ya no tengan usos).

> **BookingBar eliminada (2026-10-15, commit `5408d06c`).** Lo que F8 reemplaza es la **tira semanal** de **todas** las páginas de reservar (servicio suelto → `CheckoutCalendar`; paquete de una empresa → `FechaPaquete`; cruza-empresa con traslado → `FechaRegresoCompacta`; traslados → `FechaPaquete` y `FechaRegresoCompacta`): en la reserva, siempre el calendario completo.
> Hallazgos que siguen vigentes: `lib/calendario-paquete.ts` solo calcula fechas; la única fuente de cupo por día es `getCupoRango` (`lib/api.ts:~173-188`, `DisponibilidadRango`: `lleno | sin_panga | sin_lugar | null`), de pangas por empresa y personas, y `useDisponibilidad` la llama **sin `empresaSlug`**. `PeopleStepper` en `checkout-view.tsx:~1500` no recibe `maxPeople` (tope fijo de 5) mientras `traslado-view` usa `capacidad_maxima`; `getCupo` ignora `fecha_salida` en hospedaje; `salidas` (días seguidos de la actividad) no existe en el frontend.

- [ ] **Qué control de fecha usa cada servicio (módulo puro con prueba primero).** `lib/control-fecha.ts`: `controlDeFecha(servicio | paquete | tipoTraslado)` devuelve `fecha_unica`, `rango_llegada_salida` (hospedaje `por_noche` suelto), `rango_fijo_paquete` (paquete con noches fijas) o `ida_y_regreso` (`redondo_aeropuerto`), y si pide hora. Pruebas por tipo de servicio: pesca, paseo/tour, hospedaje, bajo demanda, transporte (`recepcion_aeropuerto`, `redondo_actividad`, `redondo_aeropuerto`), paquete de una empresa y cruza-empresa.
- [ ] **En las cuatro rutas** el paso Viaje monta el calendario completo `ui/calendario` (fondo blanco, borde `borde`, radio 16, sin sombra; días en círculo de 44 px) y desaparece la tira semanal con su enlace «desplegar el calendario completo». `checkout-calendar.tsx` y `lib/calendario-semana.ts` se borran.
- [ ] **Rango de paquete con noches fijas (función pura con prueba primero):** `rangoDelPaquete(inicio, noches)` sobre `sumarDias` y `nochesDelPaquete`, y `diasSinCupoEnRango(rango, disponibilidad)` que marca solo los días que `getCupoRango` ya declara llenos. Pruebas: N noches, 0 noches, un solo día, un día `lleno` y todos `null`. **No** hay «pocos lugares» ni corte por cupo de hospedaje: el cupo definitivo se valida al pagar (patrón de la Task 8.3b).
- [ ] **Hospedaje suelto `por_noche`:** calendario de rango llegada → salida, con la misma vista previa; la salida manual no se descarta en silencio al cambiar la llegada (hoy `checkout-view.tsx:~229-235`); el cupo se consulta por el rango (verificar antes con el backend si `cupo/rango` responde para hospedaje; si no, el cupo se valida al pagar).
- [ ] **Traslado `redondo_aeropuerto`:** **un solo calendario de rango** ida y regreso. La fecha de regreso es **obligatoria y vacía** (decisión del dueño): se elimina el prellenado `diaSiguiente(minDate)` de `traslado-view.tsx:~152`; el `CLAUDE.md` del frontend ya decía «no se prellena».
- [ ] **Personas:** `PeopleStepper` recibe `maxPeople` desde `capacidad_maxima` del servicio (de cada servicio en paquete) en las cuatro rutas. Visual: dos botones circulares `secundario` de 48 con el valor en 20/600 entre ellos; al tocar el tope se explica en línea «Máximo N personas» en lugar de ignorar el toque.
- [ ] **Salidas en varios días del paquete:** se muestran como renglón informativo en el resumen («Actividad: días 2 a 5»); su cupo se valida al pagar con el patrón de aviso.
- [ ] **Bajo demanda:** sin leyenda de «sin cupo» y sin control de hora si no la pide; el texto es **«Reserva confirmada al pagar»** (decisión del dueño). Verificar con el negocio que siempre se puede cumplir.
- [ ] **Geometría del calendario:** `grid grid-cols-7` con columnas `minmax(0,1fr)` y padding interior de 8 px con borde de 1 px (328 − 2 − 16 = 310 ≥ 308 de 7 círculos de 44; mínimo 40 en 320 px). La celda es el área táctil y los días se exceptúan expresamente de la regla de 8 px entre objetivos. Se renderizan siempre **6 renglones** (los sobrantes vacíos) para que no cambie de altura al cambiar de mes. `touch-action: pan-y`; el deslizamiento horizontal cambia de mes en 400 ms (solo opacidad con reducir movimiento). Dentro de la tarjeta de paso de ≥ 1024 px no repite borde ni radio; en móvil, sin tarjeta, conserva borde `borde` y `rounded-card`.
- [ ] **Estados de la celda** (`CeldaDia` con prop `estado`, exportada y usada por la leyenda): `disponible` número 16/500 `tinta`, hover `bg-cafe-bruma`; `pasado`/`no_reservable` número `apagado` sin tachado, `aria-disabled` y el motivo en el `aria-label`; `sin_cupo` rayado `repeating-linear-gradient(135deg, transparent 0 4px, var(--color-borde-control) 4px 5px)` con número `apagado` tachado, `aria-disabled` pero **enfocable**, y al tocarlo muestra en línea «Ese día ya no tiene lugar. Elige otro.»; `hoy` anillo `azul` de 2 px hacia adentro (`inset`) y el foco usa `outline` de 2 px con desfase (si coinciden se lee como doble anillo); `seleccion` `bg-cafe text-white`; `vista_previa` `bg-cafe-bruma` con borde discontinuo `cafe` pintado como **banda** del rango (no en cada círculo); `rango` banda `bg-cafe-claro`, número `cafe-profundo`, extremos `bg-cafe text-white`.
- [ ] **Carga y error del cupo:** mientras `getCupoRango` carga, los días se ven `disponible` con la línea «Consultando disponibilidad…» (`texto-pequeno apagado`) y nada se marca lleno; si falla, aviso `info` en línea («No pudimos consultar el cupo. Puedes elegir tu fecha y lo confirmamos al pagar») con «Reintentar» (patrón `red` de 8.3b); se precarga el mes siguiente.
- [ ] **Doble toque y anuncio:** el primer toque = vista previa y el segundo confirma **solo** en `rango_fijo_paquete`, `rango_llegada_salida` e `ida_y_regreso`; en `fecha_unica` un toque elige. Hover no anuncia nada a lectores; foco y selección sí, con una región `aria-live="polite"` («Del 7 al 10 de nov · 3 noches»).
- [ ] **Atajos** «Borrar fecha», «Mañana», «En 2 días»: son relativos a hoy y son valores editables; en el rango de ida y regreso, «Borrar fecha» limpia ambos extremos. Van en `flex flex-wrap gap-2`, 44 de alto, sin scroll horizontal (choca con el deslizamiento de mes); «Borrar fecha ×» solo aparece si hay selección; «Mañana» y «En 2 días» se deshabilitan, con la razón visible, cuando el servicio exige más anticipación.
- [ ] **Interacción de vista previa:** hover, foco o primer toque en móvil = vista previa (`cafe-bruma` + borde discontinuo `cafe`); elegir = rango firme (`cafe-claro`, extremos `cafe`); en móvil el segundo toque en el mismo día confirma.
- [ ] **Leyenda** con los mismos componentes que las celdas: solo los estados que pueden aparecer en ese control (fecha única: Disponible, Sin cupo si se conoce, Tu selección; paquete suma Vista previa y Rango; Hoy solo si el control lo marca), cada uno dibujado con `CeldaDia` a 24 px y `disponible` con anillo `borde` para que el círculo se vea — color **y** forma. En < 640 px la leyenda va en 2 columnas, desde 640 px en una fila, en `texto-pequeno apagado`. Teclado completo (flechas, Re Pág, Av Pág, Inicio, Fin, Esc).
- [ ] **Precio de hospedaje por noche:** el resumen antes de crear el pago usa la estrategia del servidor (noches × precio) y se rotula «Estimado»; la etiqueta de la barra sigue la regla de la Task 8.4.
- [ ] **Limpieza por USD derivado:** los precios en USD se derivan del tipo de cambio de la sede (siempre existen). Verificar en el backend que ninguna respuesta lleva USD vacío y **borrar** del frontend el estado «extra sin precio USD» (`pedido === null` en `pedido-paquete.tsx:~876`, que hoy oculta todo el panel) y su texto en `frontend/CLAUDE.md`.
- [ ] Commit por pieza: `feat(reserva): calendario completo con leyenda y atajos`, `feat(reserva): control de fecha por tipo de servicio`, `fix(reserva): regreso vacío, tope de personas del servicio y rango de hospedaje`.

### Task 8.6: Cierre de F8 y lanzamiento conjunto

- [ ] `verificar` completo y los **recorridos manuales de F5 más los de F8**, en escritorio **y** móvil real, es y en, con tarjeta de prueba de Stripe: servicio suelto de **pesca**, **paseo**, **hospedaje por noche**, **bajo demanda**; paquete de una empresa (con noches y con salidas en varios días); paquete cruza-empresa con rechazo en «Pago 2 de 2»; los tres tipos de traslado (el de ida y regreso con fecha de regreso vacía); y los casos: Atrás y Adelante del navegador, recargar en cada paso, cambio de idioma a media compra, entrada con query y desde «Continuar reservación», apartado vencido, sin cupo al pagar, red caída, servicio nulo, teclado abierto con barra fija. PUNTO DEL DUEÑO.
- [ ] Un solo merge y un solo deploy de F7 + F8 (F9 se cierra en su propia Task 9.7 y sale en el mismo lanzamiento); si falla algo, se revierte el merge completo.

---

## F9 — Contenido y estructura de hub y sede (sale con F7 y F8)

> **Fuente:** `docs/marketing/diagnostico-y-plan-contenido.md` (diagnóstico de `marketing-skills:cro` y `site-architecture`), `docs/marketing/analisis-competidores.md`, `docs/marketing/contenido-empresas.md` y `.agents/product-marketing.md`. **Decisiones del dueño (2026-10-16):** el hub explica la dinámica real (una empresa que reúne servicios de distintas empresas en un solo lugar; cada una opera y cobra directo) y lista **todas** las empresas con enlace a su página oficial y redes; el catálogo de La Ventana Travel cargado es lo que el cliente quiere mostrar; Sal y Sol ya tiene información e imágenes correctas; las reseñas de las empresas pueden usarse **atribuidas y confirmadas por cada empresa**.
>
> **Reglas de la fase (de `cro`):** (1) un propósito por página: hub = elegir sede, sede = reservar; (2) **ninguna sección dice «pronto»**: si no hay contenido real, no se pinta; (3) nada falso: sin reseñas de ejemplo, sin escasez inventada, sin contacto de relleno; (4) el pago, la cancelación y el clima van junto al producto; (5) **lo que incluye un servicio es de ese servicio**, nunca una promesa general; (6) es y en con el mismo orden y peso.
>
> **Skills al ejecutar:** `perception-first-design` para decidir jerarquía y orden; `marketing-skills:copywriting` para los textos; `design-taste-frontend` para diseñar cada componente nuevo (con los 3 documentos de `docs/design/`); las skills de Vercel al escribir código. Nada visible se programa sin la luz verde del dueño (PUNTO DEL DUEÑO).

### Task 9.0: Datos de las empresas y secciones condicionales (módulo puro, prueba primero)

**Files:** Create `src/content/empresas.ts`, `src/lib/secciones-sede.ts`, `tests/secciones-sede.test.cjs`; Modify `tests/run-hub-tests.cjs` (registrar la suite), `src/content/sedes-cuerpo.ts` (`descripcion` de cada empresa, hoy `''`).

- [ ] **Paso 1:** `empresas.ts` exporta, por empresa (`sal-y-sol`, `transporte-la-paz`, `la-ventana-travel`, `piratas-adventures`): nombre, sede, `descripcion` es/en, `web`, `redes[]`, `contacto?` (**solo teléfono o WhatsApp confirmados**), `resenas[]` (`autor`, `texto`, `fuente` con URL, `fecha`, `confirmada: boolean` que arranca en `false`) y `fotos[]` (`src`, `alt`, `propia: boolean`). Se llena con `docs/marketing/contenido-empresas.md`; Sal y Sol, con su información ya correcta. **Quedan fuera hasta que la empresa los confirme:** el WhatsApp +52 612 123 4567 de Piratas, los enlaces de privacidad y términos que van a `#`, las reseñas de plantilla (la de La Ventana de 2018, las 5 de DLS) y las fotos de Pexels o Unsplash. Textos de descripción con `marketing-skills:copywriting`, tono tomado de Piratas.
- [ ] **Paso 2: prueba primero.** `secciones-sede.ts` exporta `seccionesDeSede({ servicios, paquetes, empresas, resenas, fotos, faq, temporadas })` → lista ordenada de ids que se pintan. Pruebas: sin servicios ni paquetes no hay «reservar»; sin reseñas confirmadas aparece `recien-abrimos` y nunca `opiniones`; una sección sin contenido no aparece (nunca un id de «pendiente»); el orden es el de la sede propuesta (hero, reservar, tranquilidad, empresas, galería, temporadas, cómo llegar, opiniones, preguntas, cierre); la misma función sirve a es y en.
- [ ] **Paso 3:** `tsc`, `eslint`, `npm test`. Commit `feat(contenido): datos de empresas y secciones de sede condicionales`.

### Task 9.1: Sede — producto primero, un solo bloque, sin placeholders

**Files:** Modify `app/[lang]/sede/[slug]/page.tsx`, `servicios-sueltos-section.tsx`, `paquete-card.tsx`, `site-header.tsx`, `site-footer.tsx`; Delete `sede-pending-section.tsx` (y su texto `destination.pendingBody`).

- [ ] **Paso 1:** la página pinta solo lo que devuelve `seccionesDeSede`. Orden: héroe → **«Qué puedes reservar»** → «Reserva con tranquilidad» (9.2) → empresas → galería → temporadas → cómo llegar → opiniones (9.5) → preguntas → cierre. «Acerca de» deja de ser una sección independiente: su texto pasa a la tarjeta de cada empresa.
- [ ] **Paso 2: «Qué puedes reservar».** Servicios y paquetes **en un solo bloque**, agrupados por actividad con los colores de actividad del sistema de diseño (`ChipActividad`, Task 3.3). Cada tarjeta muestra: empresa que lo opera, base de cobro («por persona», «por grupo», «por barco») con «desde», y **su propia lista de qué incluye** (si el servicio no la tiene cargada, no se inventa: se muestra «Pregunta qué incluye» con el enlace de contacto). Un bloque vacío (p. ej. «sin paquetes») no se pinta.
- [ ] **Paso 3: anclas.** `site-header.tsx` y `site-footer.tsx` enlazan hoy `#nosotros`, `#experiencias`, `#servicios` y `#temporadas`. Migrarlos al nuevo conjunto de ids en el mismo commit y añadir una prueba que, dado el resultado de `seccionesDeSede`, verifique que **cada ancla enlazada existe** cuando su sección se pinta y que el enlace se omite cuando no.
- [ ] **Paso 4:** `tsc`, `eslint`, `npm test`, `build`, `guardia`. **PUNTO DEL DUEÑO:** mirar La Paz (completa) y La Ventana y Puerto Chale (sin «pronto»), en es y en, en 360 px y en escritorio. Commit `feat(sede): producto primero y solo secciones con contenido real`.

### Task 9.2: «Reserva con tranquilidad» (`GarantiasReserva`)

**Files:** Create `src/components/garantias-reserva.tsx`; Modify dictionaries es/en; si hace falta, `backend` (serializador de servicios).

- [ ] **Paso 1: dato real del modo de pago.** El modo está en el **servicio** (`permite_anticipo`, `porcentaje_anticipo` en `fleet/models.py`), no en la empresa. Los serializadores ya los exponen (`apps/fleet/serializers.py`); confirmar que el tipo `Servicio` del frontend (`lib/api.ts`) los trae en el listado de la sede y en el paquete, y si falta alguno, añadirlo con su prueba **antes** de mostrar nada.
- [ ] **Paso 2: contenido.** (a) Cómo se paga: el modo que aplica a los servicios de la sede, con un ejemplo calculado con el precio real del servicio destacado («30 % ahora, $X MXN / $Y USD, y el resto en efectivo el día del viaje»; sin ejemplo si no hay precio); (b) cancelación y clima: reembolso completo solo por mal clima; (c) cambio de fecha con 48 h; (d) la nota «lo que incluye varía por servicio». Ningún texto promete equipo ni amenidades en general. Si la política difiere por empresa, se muestra por empresa.
- [ ] **Paso 3: diseño.** `Card` plana con `AvisoEstado` de tono `info`/`exito` según el punto; sin tarjetas anidadas; cargar `design-taste-frontend`. **PUNTO DEL DUEÑO** (textos es/en incluidos). Commit `feat(sede): reserva con tranquilidad junto al producto`.

### Task 9.3: Hub — titular, tarjetas de sede útiles y mapa secundario

**Files:** Modify `app/[lang]/page.tsx`, `hub-grid-sedes.tsx`, `hub-mapa-sedes.tsx`, `dict.hub` es/en.

- [ ] **Paso 1: héroe.** Titular que diga qué se hace en Baja y a quién se compra (marca Sun Baja Experience, no «Sal y Sol Baja Experiences»), una línea de confianza y un CTA «Elige tu sede». Texto con `marketing-skills:copywriting`; el titular de la marca nueva se confirma con el dueño.
- [ ] **Paso 2: tarjetas de sede.** Cada tarjeta muestra foto, **qué se puede hacer** (chips de actividad), **las empresas que operan** y **precio «desde»** (de la API; sin precio no se pinta la línea). El mapa interactivo queda como ayuda secundaria en escritorio y no es el único camino; en móvil las tarjetas son el selector.
- [ ] **Paso 3:** `tsc`, `eslint`, `npm test`, `build`, `guardia`. PUNTO DEL DUEÑO. Commit `feat(hub): titular claro y tarjetas de sede con actividades, empresas y precio`.

### Task 9.4: Hub — «Cómo funciona» y «Empresas con las que colaboramos»

**Files:** Create `src/components/hub-como-funciona.tsx`; Modify `colaboradores-section.tsx`, `hub-por-que.tsx` (se elimina), `dict.hub` es/en.

- [ ] **Paso 1: «Cómo funciona» (reemplaza a los pilares genéricos).** Explica la dinámica real: somos una empresa que **reúne los servicios de distintas empresas locales en un solo lugar**; cada empresa opera su servicio y **cobra directo**; reservas y pagas en un solo flujo aunque combines dos empresas. Incluye las garantías reales (pago directo a la empresa, modo 100 % o anticipo según servicio, reembolso por mal clima, cambio con 48 h). Tres pasos cortos, sin tarjetas anidadas.
- [ ] **Paso 2: empresas.** `ColaboradoresSection` lista **todas** las empresas con su descripción real, su sede y enlaces a su **página oficial y redes**; teléfono o WhatsApp solo si está confirmado en `empresas.ts`. Nada de enlaces `#` ni correos inventados.
- [ ] **Paso 3:** PUNTO DEL DUEÑO (textos es/en). Commit `feat(hub): como funciona el sitio y empresas colaboradoras con sus enlaces`.

### Task 9.5: Opiniones atribuidas y fila «Recién abrimos»

**Files:** Create `src/components/opiniones-empresas.tsx`; Modify `reviews-section.tsx`, `reviews-carousel.tsx`, `dict.reviews` es/en.

- [ ] **Paso 1:** se retiran las reseñas de ejemplo del diccionario. `opiniones-empresas.tsx` pinta solo reseñas con `confirmada: true`, cada una con «Opinión publicada por [empresa]» y enlace a su fuente; **nunca** presentadas como verificadas por Sun Baja Experience ni mezcladas sin decir de qué empresa son.
- [ ] **Paso 2: compuerta de confirmación.** Antes de poner `confirmada: true`, el dueño obtiene de la empresa su confirmación de que la reseña es real; sin ella no se publica. Se hace empresa por empresa y se anota la fecha en `empresas.ts`.
- [ ] **Paso 3:** si ninguna reseña de la sede está confirmada, `secciones-sede` devuelve `recien-abrimos`: fila honesta («Acabamos de abrir. Mira las fotos reales de nuestros viajes») con las fotos propias y una invitación a compartir las suyas; sin estrellas ni cifras.
- [ ] **Paso 4:** PUNTO DEL DUEÑO. Commit `feat(sede): opiniones atribuidas y confirmadas, o recien abrimos`.

### Task 9.6: Preguntas frecuentes y datos estructurados por sede

**Files:** Modify `faq-section.tsx`, `structured-data.tsx`, `dict.faq`, `app/[lang]/sede/[slug]/page.tsx`.

- [ ] La FAQ y el JSON-LD de La Paz hablan de una sola empresa. Pasar a FAQ **por sede** (pago, cancelación y clima, qué llevar, punto de encuentro, idioma, niños) con las respuestas reales de cada empresa; el JSON-LD usa solo las preguntas que se pintan. Una sede sin FAQ cargada no pinta la sección (nunca «pronto»). Las preguntas reales de WhatsApp de las primeras semanas alimentan esta sección después del lanzamiento. Commit `feat(sede): preguntas frecuentes y datos estructurados por sede`.

### Task 9.7: Cierre de F9

- [ ] `verificar` completo y los recorridos de F8, ahora con las páginas nuevas: hub y las tres sedes en es y en, en 360 px, 768 px y 1280 px; que ninguna sección diga «pronto»; que no aparezca ningún dato de relleno ni reseña no confirmada; que los enlaces de cabecera, pie y anclas funcionen. PUNTO DEL DUEÑO.
- [ ] **Dependencias de contenido del dueño (bloquean el cierre, no el inicio):** confirmación de reseñas por empresa, contacto confirmado de Piratas y DLS, fotos propias de La Ventana, Puerto Chale y DLS, plazo de la garantía y descripciones finales de cada empresa.
- [ ] Un solo merge y un solo deploy de F7 + F8 + F9.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un refactor del checkout rompe el cobro | Fases F4/F5 por pasos, sin cambio de lógica; `lib/` ya tiene 22 suites; prueba de pago real con tarjeta de prueba de Stripe en el entorno QA tras cada paso; el dueño recorre el flujo |
| Diferir Stripe produce un salto de layout | *Fallback* del mismo tamaño; el resumen no se difiere (Task 1.2) |
| Las 22 suites no cubren componentes | Se declara; la red es compuerta + `tsc` + `build` + revisión del dueño; se evalúa añadir pruebas de componente en un plan aparte |
| La compuerta bloquea trabajo urgente | El trinquete permite bajar, no exige 0 hasta el cierre de F4 |
| El tipo de `dict` recortado rompe llamadores | Lo detecta `tsc`; ahorro modesto, la tarea es la 5.5 (F5) |
| Logo o fotos definitivos sin entregar | F7 se hace con tokens y fuentes; logo y fotos se sustituyen al llegar (no bloquean el resto) |
| Una marca que cambie la **forma** (no solo valores) rompe «F7 es solo tokens» | Forma por tokens semánticos (`--radius-control`, `--radius-campo`) y variantes; si la marca exige un layout distinto, se declara como alcance extra de F7, no como «cambio de valores» |
| Formulario de tarjeta y OG con la identidad vieja | `tokens-pago.ts` probado contra `globals.css`; OG como exento explícito en la lista de F7 |
| Un `<button>` dentro de un `<form>` sin `type` cambia de comportamiento al migrar | Revisión previa en Task 3.3 y migración con `type` explícito |
| Estado de cobro perdido al partir los 36 `useState` | Reducer compartido + recorridos manuales (rechazo, recarga, Turnstile, Enter) en cada commit de F5 |
| Contacto + detalles pasan de ~7 campos en alguna ruta | Task 8.1 cuenta los campos antes de unir; esa ruta se queda en 4 pasos y se avisa al dueño |
| Vista previa del rango se confunde con una selección confirmada | Estilo distinto (borde discontinuo + relleno suave) y señal por forma, no solo por color; segundo toque para confirmar en móvil |
| Perder el estado al cambiar de paso en el asistente móvil | El estado vive en el reducer existente, no en cada pantalla; recorridos manuales de F5 |
| Fuente: Consola Mono solo tiene Book y Bold | Titulares siempre 700; subtítulos y etiquetas en la fuente del cuerpo |
| El fondo arena exige tocar 57 usos de `bg-background` | Task 2.4 separa `--superficie` de `--background` antes de F7, sin cambio visual |
| Viaje se sobrecarga al recibir los extras | Task 8.1 cuenta los controles por ruta; los opcionales se pliegan, no se crea un cuarto paso |
| Quitar la tira semanal deja sin control a las cuatro rutas de compra y a la fecha de regreso de traslados | El calendario completo las cubre (la de regreso, obligatoria y sin prellenar); recorrido manual de las cuatro rutas |
| El botón de la barra no puede cobrar fuera de Stripe | La barra de la pantalla de tarjeta vive dentro de `<Elements>` (Task 8.4); el botón interno de `PaymentForm` se quita |
| Un error de otro paso no tiene adónde llevar al usuario | `validarTodo()` devuelve `{paso, campo}` y el aviso ofrece «Corregir…» (8.1, 8.3b); el foco se aplica tras montar el paso |
| Perder lo escrito (Atrás, recarga, idioma) | Historial por paso + borrador en la pestaña (Task 8.0); se borra al confirmar |
| Datos personales en `sessionStorage` | Solo en la pestaña, con vigencia de 4 horas y borrado al confirmar (autorizado por el dueño); `try/catch` por si el almacenamiento falla |
| Un monto en el botón que no coincide con el cobro | Regla de la etiqueta: monto solo cuando el servidor lo confirmó; «Estimado» antes (Task 8.4) |
| Controles de pesca aplicados a hospedaje, bajo demanda o traslados | `controlDeFecha` por tipo de servicio, con prueba por cada tipo (Task 8.5) |
| Falsos positivos de la compuerta (comentarios, anclas `#add`) | Se ignoran comentarios, la regex de hex exige 3/4/6/8 dígitos y la prueba es la especificación |
| Reseñas de plantilla publicadas como reales | Cada reseña lleva autor, fuente y `confirmada`; solo se pintan las confirmadas por la empresa, siempre atribuidas a ella (Task 9.5); si ninguna, fila «Recién abrimos» |
| Datos de relleno publicados (WhatsApp de Piratas, enlaces `#`, botón de DLS) | Solo contacto marcado como confirmado se renderiza; el resto queda fuera de `empresas.ts` hasta que la empresa lo confirme (Task 9.0) |
| Reordenar secciones rompe los anclas de la cabecera y el pie (`#nosotros`, `#experiencias`, `#servicios`, `#temporadas`) | Task 9.1 migra `site-header.tsx` y `site-footer.tsx` en el mismo commit y una prueba revisa que cada ancla enlazada exista cuando la sección se pinta |
| El modo de pago está en el servicio, no en la empresa (`permite_anticipo`, `porcentaje_anticipo` en `fleet/models.py`) | Task 9.2 lee el modo real de cada servicio desde la API (ya expuesto en `fleet/serializers.py`); se confirma que el frontend lo recibe antes de mostrar nada |

## Orden y dependencias

`F0` → `F1` (en paralelo con `F2`) → `F3` → `F4` grupos 1-3 → `F5` → `F4` grupo 4 (ya dentro de `pasos/*`) → `F6` → `F7` + `F8` + `F9` (salen juntas). F9 (contenido y estructura de hub y sede) solo depende de F5.4 (contenedores) y de F3 (primitivas); su parte de datos y textos puede empezar antes. F1 puede salir a producción sola (mejora el lanzamiento sin tocar el aspecto). F2 no cambia nada visible. F4 y F5 son los que más piden la revisión del dueño.

## Autorrevisión

- **Cobertura:** R1 (F3/F4/F5, 8.1, 8.4), R2 (1.5, 5.4, 8.2, 8.3), R3 (F2, guardia, 8.1), R4 (restricciones, F4, F5, F7, 8.5), R5 (3.2, F7, 8.4); los 13 puntos de la petición de reserva y los 12 hallazgos de recorridos aplicables están en F8 (1→8.2, 2→8.3, 3→8.3, 4→8.3, 5→8.5, 6→8.5, 7→8.3, 8→8.1, 9–12→8.4, 13→8.5); hallazgos V1–V9 asignados a tareas o a F7/futuro (V7 como sondeo, V8 a F7, V9 anotado).
- **Sin marcadores:** las tareas de F4/F5 son procedimentales porque cada una depende de leer el archivo real; llevan regla, orden, puerta y criterio de cierre. Las de F0–F3 llevan código.
- **Consistencia de nombres:** `botonClases`, `FormularioPagoDiferido`, `guardia-estilos.cjs`, `TOKENS_PAGO`, `--radius-control`/`--radius-campo`.
- **Limitación honesta:** los valores de Tailwind (Task 2.1) se copian de `node_modules`, no se citan de memoria; las alturas de los *fallbacks* (1.2) se miden al ejecutar.
- **Crítico de arquitectura:** ejecutado el 2026-10-15 (resultado: REVISION REQUIRED, 3 críticos y 4 significativos). Aplicadas: runner de pruebas (`guardia` fuera del runner, `variantes.ts` sin imports), partir `stripe-panel.tsx` antes de diferir, exentos y regex de la compuerta, F4-núcleo después de F5, capas `ui`, tokens de forma y de pago, `@theme` aparte sin byte-a-byte, recorte del diccionario movido de F1 a la Task 5.5, recorridos manuales. Ronda 3 (F7/F8): REVISION REQUIRED; aplicadas con las decisiones del dueño (3 pasos con extras en Viaje y «Pago 1 de 2» como sub-paso, calendario recortado, sin palabra caligráfica, página arena con tarjetas blancas), más `--nav-alto`, `BookingBar` intacto, lista de consumidores de fuentes, pasada de sombras/foco/titulares y bloques en F5. Ronda 4 (recorridos de todos los servicios): REVISION REQUIRED con 13 hallazgos (el 6, «extra sin precio USD», no aplica: el USD se deriva del tipo de cambio); soluciones derivadas con PFD y aplicadas (Tasks 8.0, 8.3b, 8.4 y 8.5 reescritas; decisiones del dueño: barra dentro de Stripe, regreso vacío y obligatorio, borrador en la pestaña, bajo demanda = reserva confirmada al pagar). Ronda 5 (skills de Vercel, 2026-10-16): REVISION REQUIRED con 1 crítico, 13 significativos y 11 menores; todos recogidos en la sección 0 «Enmiendas». Ronda 6 (verificación de la ronda 5): REVISION REQUIRED sin críticos, 5 significativos y 8 menores, todos aplicados dentro de su tarea (script de medición propio, `botonClases` aún inexistente en F1, `drag` y `strict` de LazyMotion con regla `motion-completo`, puerto muerto fijado en el build, `preconnect` en los `page.tsx`, y los menores). Ronda de taste (skill `design-taste-frontend` + `docs/design/`, 2026-10-16): REVISION REQUIRED con 3 críticos, 15 significativos y 6 menores sobre la especificación visual, todos aplicados dentro de su tarea (los valores de marca en F7, el aspecto de F3 a F6 intacto). Pendiente: ronda 7 técnica y de taste hasta `APPROVED`.
