# Base del frontend antes de la marca nueva — Plan de implementación

> **Para quien ejecute:** usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans`. Los pasos usan casillas `- [ ]`. **Regla del dueño:** nada de este plan que toque UI visible se programa sin su luz verde explícita en cada punto de control marcado «PUNTO DEL DUEÑO».

**Meta:** dejar el frontend con tokens completos, primitivas con variantes, vistas de compra partidas y carga optimizada, de modo que la identidad de marca nueva sea un cambio de valores de token y variantes en un solo lanzamiento, sin regresiones en el checkout.

**Arquitectura:** tres capas. (1) `globals.css` declara *todos* los tokens, incluidos radio, sombra y escala de texto, con los valores actuales; Tailwind 4 hace que `rounded-lg`, `shadow-md`, `text-sm` etc. lean esos tokens, así que la marca los cambia en un solo sitio. (2) `src/components/ui/` contiene las primitivas y es una capa baja: solo importa de `ui/`, `lib/` y paquetes; la lógica de variantes vive en un módulo puro sin imports, probado con el runner existente. (3) Una compuerta automática con «trinquete» (solo baja) impide reintroducir colores, radios o controles crudos.

**Stack:** Next.js 16.3, React 19.2, Tailwind 4.3.3, `motion`, `@phosphor-icons/react`, Stripe. Se añaden `clsx` y `tailwind-merge`. Las variantes son mapas de strings puros (sin `cva`) para que el runner de pruebas, que compila solo `src/` y no resuelve paquetes externos, las pueda probar.

**Fuentes de fundamento:** derivación PFD (R1–R5, abajo) + skills de Vercel `react-best-practices`, `nextjs`, `next-cache-components`, `shadcn`, `vercel-storage`. Mediciones del 2026-10-15 sobre la rama `qa/checkout-unificado`. **Sistema de diseño de la marca nueva (Sun Baja Experience): `docs/design/design.md`, `design-guidelines.md` y `design-components.md`** (tokens, fuentes, página de reserva); este plan lo aplica en F7 y F8.

## Restricciones globales

- **Checkout visible idéntico** (diferencia visual cero) hasta las fases F7 y F8, que salen **juntas en un solo lanzamiento**. Montos, cargos, plazos y textos de cobro no cambian. *(PFD R4)*
- La marca nueva aterriza **en un solo lanzamiento**; nunca una mezcla vieja/nueva en producción. *(PFD R4)* F7 es **valores más una pasada de componentes** (fondos, sombras, titulares, foco), no solo valores.
- Todo valor visual sale de un token; todo control de una primitiva. *(PFD R3)*
- Una sola acción principal por paso; su jerarquía vive en la primitiva. *(PFD R1, R5)*
- Puerta de cada tarea: `npx.cmd tsc --noEmit`, `npx.cmd eslint src tests`, `npm.cmd test`, `npm.cmd run build`, `npm.cmd run guardia`. Un commit por tarea.
- **No ejecutar `shadcn init`**: reescribe `globals.css` y el skill documenta que rompe las fuentes en Tailwind 4. Se copia el patrón (`cn` + `cva`), no el CLI.
- Verificación sin abrir navegador (regla del dueño): el dueño mira el sitio en cada PUNTO DEL DUEÑO.
- Next.js 16 difiere de lo que se sabe de memoria: antes de tocar una API de Next, leer `node_modules/next/dist/docs/` (lo exige `frontend/AGENTS.md`).

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
| V1 | 40 archivos importan `@phosphor-icons/react` por el barril y `next.config.ts` no tiene `optimizePackageImports` | `bundle-barrel-imports` (CRÍTICA) | −200 a −800 ms de arranque por import en frío; menos bundle |
| V2 | `stripe-panel.tsx` (611 líneas: Stripe + Elements + resumen + portal) se importa estático en las 3 vistas de compra | `bundle-dynamic-imports` (CRÍTICA) | Hay que **partir el módulo primero** (Task 1.2); después Stripe sale del chunk inicial y solo se baja al llegar a pagar. Los calendarios no se difieren (son del primer paso visible) |
| V3 | Se pasa el diccionario completo (`dict`, 55,8 KB en es) a 5 componentes cliente; solo usan `checkout` (18 KB), `pedido`, `traslados`, `feedback`, `continuar` | `server-serialization` (ALTA) | Ahorro modesto (~20 KB por idioma): Task 5.5, después de partir las vistas |
| V4 | 0 `<Suspense>`, solo 2 `loading.tsx` (reservar, traslados) y **ningún** `error.tsx`/`global-error.tsx` | `async-suspense-boundaries` (ALTA) + guía de errores de `nextjs` | Un fallo de la API tumba la página sin diseño |
| V5 | Video de 83,5 MB servido desde `public/` (`videohero.webm`), también referenciado por 2 sedes | `rendering-*` + `next/image` | Mayor riesgo de lanzamiento |
| V6 | 1 `<img>` cruda en `sede-hero.tsx:67` | guía `nextjs/image` | LCP y tamaños |
| V7 | `request()` en `lib/api.ts` hace `fetch` sin política de caché | `next-cache-components` (`use cache`, `cacheLife`, `cacheTag`) | Oportunidad solo para el catálogo público; **nunca** cupo ni cotización. Entra como sondeo (spike) con decisión, no como compromiso |
| V8 | Fuente `Bella Fashion` con licencia «personal use only» (aviso en `fonts/LICENCIAS.md`); `Bebas Neue` y `Instrument Sans` | — | Resuelto por el sistema de diseño: titulares en **Consola Mono** (SIL OFL, servida desde el sitio) y cuerpo en la **fuente del sistema** (San Francisco en Apple); salen Bella, Bebas e Instrument (F7). Menos descargas de fuentes |
| V9 | CSP `img-src 'self' data: blob:` | `nextjs` (imágenes remotas) | Si las fotos pasan a R2 hay que añadir el dominio a `img-src`/`media-src` y a `images.remotePatterns` |

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
| `src/components/ui/{button,input,field,card,badge}.tsx` | Primitivas | F3 |
| `src/components/ui/hero-media.tsx`, `section-shell.tsx` | Héroe y sección únicos | F5 |
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
const { contar, sinComentarios } = require('../scripts/guardia-estilos.cjs');

test('cuenta controles y colores crudos', () => {
  assert.equal(contar('<button className="x">', 'boton-crudo'), 1);
  assert.equal(contar('<Button>', 'boton-crudo'), 0);
  assert.equal(contar('className="bg-red-400"', 'paleta-cruda'), 1);
  assert.equal(contar('className="bg-accent"', 'paleta-cruda'), 0);
  assert.equal(contar('style={{ color: "#fff" }}', 'color-literal'), 1);
  assert.equal(contar('<input type="text" />', 'input-crudo'), 1);
  assert.equal(contar('<img src="a" />', 'img-cruda'), 1);
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
  'capas-ui': /from\s+['"]@\/(?!components\/ui\/|lib\/)[^'"]*['"]/g,
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
      const n = contar(texto, regla);
      if (n > 0) (resultado[regla] ??= {})[rel] = n;
    }
  }
  return resultado;
}

module.exports = { contar, sinComentarios, medir, EXENTOS };

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

**Files:** Create `docs/superpowers/plans/2026-10-15-frontend-base-linea-base.md`.

- [ ] **Paso 1:** `npm.cmd run build`; copiar a ese archivo la tabla «Route (app) / Size / First Load JS» tal cual la imprime Next.
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
  optimizePackageImports: ['@phosphor-icons/react', 'motion'],
},
```

(ajustar la ubicación si en 16.3 ya no es experimental).
- [ ] **Paso 3:** `npm.cmd run build`; comparar First Load JS con la línea base; anotar el cambio en el archivo de línea base.
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

Medir la altura real del formulario con su `PaymentElement` y poner esa altura en el *fallback* (sin salto de layout: R4).
- [ ] **Paso 5:** en las 3 vistas, usar `FormularioPagoDiferido` en lugar de `FormularioPago`. `StripePanel`, `ref`, portal y `key={captchaKey}` no se tocan.
- [ ] **Paso 6:** `build`; comparar First Load JS de `/reservar` y `/traslados` con la línea base: debe bajar el chunk inicial (el de Stripe sale).
- [ ] **Paso 7: PUNTO DEL DUEÑO** — recorrer con tarjeta de prueba de Stripe los **cuatro** caminos: servicio suelto, paquete de una empresa, paquete cruza-empresa (incluido el rechazo tras retención del primer pago) y traslados; y recargar a media compra. No se avanza sin su luz verde.
- [ ] **Paso 8: commit** `refactor(checkout): stripe-panel partido; solo el formulario de tarjeta carga Stripe, y bajo demanda`.

> Los calendarios (`DateField`, `CheckoutCalendar`) **no** se difieren en F1: son parte del primer paso visible; diferirlos produciría el salto que R4 prohíbe. Se reevalúa tras F5 con las medidas reales.

### Task 1.3: Páginas de error con diseño (V4)

**Files:** Create `src/app/[lang]/error.tsx`, `src/app/global-error.tsx`.

- [ ] **Paso 1:** leer la guía `nextjs` de manejo de errores y `node_modules/next/dist/docs/` para la firma de `error.tsx` en 16.3 (`error`, `unstable_retry` o `reset`).
- [ ] **Paso 2:** `error.tsx` cliente con el mensaje del diccionario `dict.errores` (añadir las claves a `es.json` y `en.json`; reiniciar `npm run dev` porque Turbopack cachea los diccionarios), botón «Reintentar» y enlace a la portada. Registrar el error con su `digest` en consola.
- [ ] **Paso 3:** `global-error.tsx` mínimo (incluye `<html>`/`<body>`), con texto estático bilingüe.
- [ ] **Paso 4:** verificar por tipos y `build`. No se simula un fallo en producción.
- [ ] **Paso 5: commit** `feat(frontend): páginas de error con diseño propio`.

### Task 1.4: Esqueletos de carga en las rutas con datos (V4)

**Files:** Create `loading.tsx` en `src/app/[lang]/sede/[slug]/`, `servicio/[empresa]/[servicio]/` y `catalogo/`.

- [ ] **Paso 1:** para cada ruta, leer su `page.tsx` y copiar la estructura de la página con `Skeleton`, al estilo de `reservar/loading.tsx`.
- [ ] **Paso 2:** `build`. **Paso 3: commit** `feat(frontend): esqueletos de carga en sede, servicio y catálogo`.

### Task 1.5: Héroe — imagen inmediata y video ligero (V5, V6, PFD R2)

**Files:** Modify `src/components/hero.tsx:75-90`, `src/components/sede-hero.tsx:67`; Replace `public/videos/videohero.webm`.

- [ ] **Paso 1: comprimir el video** (hay `ffmpeg` instalado):

```bash
ffmpeg -i public/videos/videohero.webm -vf "scale=-2:720,fps=24" -c:v libvpx-vp9 -crf 38 -b:v 0 -an -row-mt 1 public/videos/videohero.min.webm
ls -la public/videos/
```

Objetivo: ≤ 8 MB. Si se ve mal, subir calidad hasta que el dueño lo apruebe (PUNTO DEL DUEÑO: mirar el video). Añadir también una versión `.mp4` (H.264) como segunda `<source>` solo si hay navegadores objetivo sin VP9.
- [ ] **Paso 2:** reemplazar el archivo en las rutas de `sedes-cuerpo.ts` (2 referencias) y `hero.tsx`.
- [ ] **Paso 3:** en `hero.tsx` añadir `preload="metadata"` al `<video>`; el `poster` ya existe. Asegurar que la imagen del `poster` se sirva con `next/image` `priority` como capa inferior, de modo que sea el LCP real; el video se funde encima al disparar `canplay`. Mantener `prefers-reduced-motion`: sin video, solo imagen.
- [ ] **Paso 4:** en `sede-hero.tsx:67` reemplazar `<img>` por `<Image fill sizes="100vw" priority alt="" className="object-cover" />`.
- [ ] **Paso 5:** `npm.cmd run guardia -- ` (la regla `img-cruda` baja en 1) y actualizar la línea base con `node scripts/guardia-estilos.cjs --escribir`.
- [ ] **Paso 6: commit** `perf(frontend): video de portada comprimido, imagen inmediata y next/image en la sede`.
- **Después, fuera de este plan:** mover el video a R2 (dominio en `img-src`/`media-src` de la CSP y en `images.remotePatterns`, hallazgo V9).

### Task 1.6: Pre-conexión a la API (opcional, de bajo riesgo)

- [ ] En `src/app/[lang]/layout.tsx` añadir `import { preconnect } from 'react-dom'` y llamar `preconnect(process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000')` al inicio de `RootLayout` (regla `rendering-resource-hints`). Commit `perf(frontend): preconexión a la API`.

### Task 1.7: Sondeo de Cache Components (V7) — decisión, no código en producción

- [ ] Leer `node_modules/next/dist/docs/` sobre `cacheComponents` y `use cache` en 16.3. Probar en una rama aparte con `getServicioDetalle`/`getPaqueteDetalle` y `cacheLife('minutes')`. Escribir en el archivo de línea base: qué ruta mejora, cuánto, y cómo se invalida un precio editado en el backoffice. **Sin decisión del dueño no se activa.** Cupo, cotización y pagos quedan fuera siempre.

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

  Las variantes (F3) y `CAJA_CAMPO` usarán `rounded-control` y `rounded-campo`. Añadir también `--color-ring` (foco) y mapear `border-red-400` de `CAJA_CAMPO_ERROR` a `border-error`.
- [ ] **Paso 4:** `build` y comparar **el cálculo de estilos** de las pantallas de la línea base (mismas clases, mismos valores resueltos). Cualquier diferencia visual se revierte.
- [ ] **Paso 5: commit** `refactor(frontend): radio, sombra, texto y forma de controles como tokens, sin cambio visual`.

### Task 2.2: Retirar los literales de color restantes

**Files:** los archivos con `color-literal` y `paleta-cruda` según `scripts/guardia-estilos.baseline.json` (66 literales + 13 de paleta + 3 arbitrarios en la medición).

- [ ] **Paso 1:** por archivo, reemplazar cada color por su token semántico (`bg-red-400`→`bg-error`, etc.). Los rgba de degradados sobre foto (`hero.tsx`) se convierten en tokens `--scrim-*` en `globals.css`.
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
- `Button(props: ButtonHTMLAttributes & BotonVariantes & { conFlecha?: boolean; cargando?: boolean })`, siempre `type="button"` salvo que se indique `type="submit"`.
- `Input(props: InputHTMLAttributes & { invalido?: boolean })`, con `aria-invalid`.
- `Field({ etiqueta, error, ayuda, id, children })`: etiqueta, control y `ErrorDeCampo` (reutiliza el existente con `Despliegue`).
- `Card`/`Badge`: contenedores con variantes (`plana | elevada`, `exito | aviso | error | neutro`).

- [ ] Por componente: escribir, usar `cn` y las variantes; `Input` usa `CAJA_CAMPO`/`CAJA_CAMPO_ERROR` de `ui/caja-campo` (movidos en Task 3.0; **nunca** de `checkout/estilos.ts`, que violaría la capa `ui`). `Card` usa `bg-superficie` y `rounded-card`; `Badge` tiene las variantes de actividad `mar`, `ciudad` y `outside` (fondo `*-claro`, texto del tono oscuro, siempre con icono) y las de estado `exito`, `error`, `aviso` e `info`.
- [ ] `Button` tiene **`type="button"` por defecto**. Antes de migrar un `<button>` hay que mirar si está dentro de un `<form>` sin `type`: ese hoy **envía** el formulario (p. ej. Enter en `campos-contacto`). Ese caso se migra con `type="submit"` explícito. Listar con `grep -rn "<button" src --include=*.tsx` y revisar los que estén dentro de `<form`.
- Probar en **una sola pantalla**: sustituir los botones de `faq-section.tsx` (superficie pública de bajo riesgo) por `Button`. Verificar con `tsc`, `eslint`, `build`, `guardia` (baja).
- [ ] PUNTO DEL DUEÑO: mirar la sección de preguntas frecuentes (debe verse igual).
- [ ] Commit por componente.

### Task 3.4: Absorber lo ya existente

- [ ] `BotonPaso` pasa a ser un envoltorio de `Button variante="principal"`; `AccionTexto` y `EtiquetaModificar` usan `botonClases({ variante: 'texto' | 'acento' })`. Los nombres se conservan para no tocar los llamadores. Commit `refactor(checkout): BotonPaso y AccionTexto sobre la primitiva Button`.

---

## F4 — Migrar los 84 controles (uno por superficie, aspecto idéntico)

Recuento medido (`<button`): continuar-reservacion 7, reviews-carousel 5, grupo-servicio 4, fecha-paquete 4, hub-mapa-sedes 4, stripe-panel 3, date-field 3, checkout-view 3, checkout-calendar 3, y 23 archivos con 1 o 2. Controles de formulario (`<input|select|textarea>`): stripe-panel 4, grupo-servicio 4, traslado-view 2, checkout-view 2, field-popover 1, select-personalizado 1, campos-contacto 1.

**Regla de migración (aplica a todas las tareas):** una superficie por commit; el JSX resultante genera las mismas clases (comparar el HTML renderizado en el `build` no basta: se compara el diff de clases a mano); si una variante no existe, **se añade la variante** a `variantes.ts` con su prueba, no se deja un `<button>` crudo.

Orden por riesgo creciente (PUNTO DEL DUEÑO al cerrar cada grupo):
1. **Públicas sin dinero:** `faq-section`, `cookie-notice`, `lang-switch`, `site-header`, `sede-selector`, `reviews-carousel`, `hub-mapa-sedes`, `hub-hero`, `paquete-card`, `selector-experiencia`, `continuar-reservacion`.
2. **Campos y selectores compartidos:** `field-popover`, `date-field` (solo su modo popover, que usa el hero), `time-field`, `people-stepper`, `select-personalizado`, `toast`. **No se migran** `checkout-calendar` ni `sticky-booking-bar`: F8 reemplaza el primero y borra el segundo (ya no se renderiza en ningún sitio).
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
- [ ] **Paso 2:** el estado compartido sube a un *reducer* (el patrón ya existe en `lib/pedido-estado.ts` + `use-pedido-estado.ts` para paquetes); el estado local de un paso baja a su componente. Regla `rerender-no-inline-components`: ningún componente se define dentro de otro.
- [ ] **Paso 3:** extraer un **bloque** por commit en este orden: pago, extras (hoy «detalles»), contacto, recogida (solo traslados), viaje; los 4 pasos actuales quedan como composición fina de bloques. Así F8 solo reagrupa los bloques en tres pasos, sin volver a partir las vistas. Tras cada extracción: `tsc`, `eslint`, `npm test`, `build`, `guardia`.
- [ ] **Paso 4:** PUNTO DEL DUEÑO tras cada paso extraído (recorrer el servicio suelto completo hasta el pago de prueba).

### Task 5.2: Partir `traslado-view.tsx` (1 006 líneas, 32 `useState`)

- [ ] Mismo procedimiento. Reutiliza `PaginaCheckout`, `ContenidoViaje` y los pasos ya compartidos; el objetivo es que los bloques de traslados (viaje, contacto, recogida, pago) sean componentes de `checkout/bloques/`.

### Task 5.3: Revisar `pedido-paquete.tsx` (894 líneas)

- [ ] Ya usa hooks y reducer; solo extraer los bloques de JSX grandes en componentes (`grupo-servicio.tsx` ya existe). No es prioridad.

### Task 5.4: Un solo héroe y una sola sección

**Files:** Create `src/components/ui/hero-media.tsx`, `section-shell.tsx`; Modify `hero.tsx`, `hub-hero.tsx`, `sede-hero.tsx` y las secciones about/season/included/license/colaboradores/gallery.

- [ ] `HeroMedia({ imagen, video, alt, prioridad })` encapsula imagen inmediata + video diferido + degradado (el patrón de la Task 1.5). Los tres héroes lo usan.
- [ ] `SectionShell({ fondo: 'papel' | 'bruma' | 'bruma-profunda', titulo, regla })` encapsula el ritmo de secciones (la «paleta v3» solo admite esos tres fondos).
- [ ] Un héroe por commit; PUNTO DEL DUEÑO al terminar (portada, sede, servicio).

### Task 5.5: Diccionario por sección en los clientes (V3, ahorro modesto)

> Movida desde F1 por el crítico: con la vista aún entera, `dict` se pasa a sub-componentes (`checkout-view.tsx:1188` y `:1398`; `AvisoCargos`, `EncabezadoPago`, `PorQueVariosPagos` en `pedido-paquete.tsx`), y recortar el tipo se vuelve una cascada de ~10 archivos para ~20 KB. Después de F5, cada paso recibe props mínimas y el recorte es natural.

- [ ] Para cada paso extraído, tipar `dict` con `Pick<Dictionary, 'checkout' | …>` según lo que use; que `tsc` dé la lista. Medir con `build`; si el ahorro es < 10 KB, descartar la tarea y anotarlo. Commit `perf(checkout): cada paso recibe solo las secciones del diccionario que usa`.

---

## F6 — Cerrar la base

- [ ] `guardia`: `boton-crudo`, `input-crudo`, `img-cruda`, `paleta-cruda` y `capas-ui` en **0 salvo los exentos listados con motivo** en `EXENTOS` (`globals.css`, `opengraph-image.tsx`, `lang-switch.tsx`, `tokens-pago.ts`); umbral duro. Cualquier exento nuevo exige un motivo escrito en el código.
- [ ] Script `"verificar": "tsc --noEmit && eslint src tests && npm test && npm run test:guardia && npm run guardia && next build"` en `package.json`.
- [ ] Actualizar `frontend/CLAUDE.md`: dónde viven los tokens y las primitivas, la regla «nada crudo», cómo añadir una variante y cómo correr `verificar`.
- [ ] Línea base final de carga en el archivo de F0. Commit `docs(frontend): base cerrada`.

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

**Files:** Modify `src/app/globals.css`, `src/app/[lang]/layout.tsx`, `src/lib/tokens-pago.ts`, `src/components/ui/variantes.ts`, `src/app/[lang]/opengraph-image.tsx`, `src/components/stripe-panel.tsx` (o `checkout/pago/formulario-pago.tsx` tras F1.2), `src/app/[lang]/not-found.tsx`, `src/components/license-section.tsx`, `src/components/hero.tsx`, `src/components/sede-hero.tsx`.

- [ ] **Paso 1: colores** (valores de `design.md`): `--accent`/`--action` → café `#7C3B02` (texto sobre acción `#FFFFFF`, 8,46:1); `--foreground` → `#1F1A14`; **`--background` → arena `#FBF7F0`** (las superficies ya son blancas por F2.4); bordes `#D9C9B4` (decorativo) y `#8A7A66` (controles, 4,15:1); estados con sus parejas; familias `azul`, `coral`, `verde` con `hondo`, `profundo`, `medio`, `claro` y `bruma`; **`--ring` → `azul` `#1B607F`** (foco). Comprobar el contraste de cada par antes del commit. `--amber`, `--indigo` y `--yellow` salen; `--hero-ink` se queda.
- [ ] **Paso 2: forma** — `--radius-control: 12px`, `--radius-campo: 12px`, `--radius-card: 16px`, `--radius-sheet: 24px` (las tarjetas ya usan `rounded-card` desde F3/F4); chips y días del calendario en `9999px`.
- [ ] **Paso 3: fuentes — lista cerrada de lo que se toca** (hallazgo del crítico):
  - `layout.tsx`: quitar `Instrument_Sans`, Bebas Neue y Bella Fashion; añadir `localFont` con los dos `.woff2` de Consola Mono (`display: 'swap'`, `variable: '--font-titulo'`, pesos 400 y 700, `fallback` = la pila monoespaciada de `design.md`).
  - `globals.css` `@theme inline` (líneas ~110-112): borrar `--font-sans: var(--font-cuerpo)` y `--font-script: var(--font-acento)`; declarar `--font-sans` con **la pila literal** (`-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`) y `--font-display: var(--font-titulo)`.
  - `globals.css` `body` (línea ~300): `font-family: var(--font-sans)` (ya no `--font-cuerpo`).
  - `globals.css` regla `h1, h2` (líneas ~318-324): peso 700, tracking de `design.md` (`--tracking-titulo: -0.02em`), sin el fallback Oswald/Arial Narrow; se conserva `font-synthesis: none` porque Book y Bold son reales.
  - `globals.css` `.acento` (líneas ~265-280): **se elimina**, y en `hero.tsx` (líneas ~99-100) y `sede-hero.tsx` (líneas ~79-80) el titular se pinta como texto plano (`start + emphasis + end`, sin estilo especial; el contrato de `sedes-tipos.ts` no cambia).
  - `not-found.tsx` (líneas ~25-37) y `license-section.tsx` (línea ~39): quitar `font-normal` y migrar al nuevo `--tracking-titulo`.
  - `stripe-panel.tsx` (líneas ~76, ~86) carga Instrument Sans por Google Fonts para Stripe Elements: quitar `STRIPE_FUENTES` y poner `fontFamily` de la pila del sistema en `TOKENS_PAGO` (la prueba de `tokens-pago` lo compara con `--font-sans`).
- [ ] **Paso 4: Stripe y OG** — `TOKENS_PAGO` con los hex nuevos (comparados con `globals.css` por su prueba) y `opengraph-image.tsx` a mano (no carga fuentes; solo cambian colores).
- [ ] **Paso 5: variantes** — `variantes.ts`: `principal` café con texto blanco; `secundario` con borde `borde-control` y texto café; `peligro` con `error`. Las pruebas de F3 siguen pasando.
- [ ] **Paso 6: commit** `feat(marca): valores de Sun Baja Experience` (todavía sin desplegar).

### Task 7.3: Pasada de componentes (cambios visuales deliberados)

> «Solo valores» era falso para estos puntos (medidos el 2026-10-15): 16 `shadow-[...]` arbitrarias y 18 `shadow-*` sueltas, dos brillos amarillos con `rgba(255,222,0,…)`, 5 `ring-accent`, 2 `text-action` y h1/h2 con clases de tamaño sueltas.

- [ ] **Sombras:** convertir las 16 arbitrarias (p. ej. `checkout-section-card.tsx:54`, `booking-confirmation.tsx:167`, `checkout-loading-shell.tsx:58`, `cookie-notice`, `field-popover`) y las 18 `shadow-*` a tres tokens `--shadow-n0` (ninguna), `--shadow-n1` (barra inferior móvil) y `--shadow-n2` (popover, toast, hoja) con los valores de `design.md`. El resumen y las tarjetas quedan en `n0`.
- [ ] **Brillos amarillos:** `booking-bar.tsx` (líneas ~131-136) y el panel de pago (`rgba(255,222,0,…)`, líneas ~399-404 de `stripe-panel.tsx` antes del split) pasan a un token `--brillo-accion` (café, baja opacidad) o se eliminan.
- [ ] **Foco:** los 5 `ring-accent` pasan a `focus-visible:ring-ring`.
- [ ] **`text-action` (2 usos):** el icono `Warning` sobre `bg-action/10` (`checkout-view.tsx:~1313`, `grupo-servicio.tsx:~114`) pasa a `text-aviso` sobre `bg-aviso-fondo`.
- [ ] **Titulares:** definir clases semánticas `texto-display`, `texto-pagina`, `texto-seccion` y `texto-paso` con la escala de `design.md` (40/64, 36/56, 28/36, 24/28) y aplicarlas a los h1/h2 de `hero.tsx` (~38/60/76 px), `hub-hero.tsx` (~38/60/72), el h1 de `servicio/[empresa]/[servicio]/page.tsx` (`text-5xl/6xl`) y `encabezado-compra.tsx` (`text-2xl/3xl`). La monoespaciada es más ancha: los `max-w-[19ch]` calibrados para Bebas condensada (comentario en `globals.css`) se revisan por desbordamiento en móvil de 360 px, en es y en.
- [ ] **Verificación:** `verificar` completo, `guardia` en 0 salvo exentos, build; revisión del dueño de portada, hub, sede, servicio, los tres checkouts, traslados, confirmación y páginas de error, en es y en. PUNTO DEL DUEÑO.
- [ ] **Commit** `feat(marca): sombras, foco, titulares y brillos con la identidad nueva`.
- [ ] F7 **no se despliega sola**: sale junto con F8.

---

## F8 — Página de reserva nueva (sale con F7)

> Especificación: `docs/design/design-components.md` (secciones «Página de reserva», «Selección de fecha» y «Tarjeta de paso»). Decisiones del dueño: se quita **solo el stepper numerado**; **tres pasos en todas las rutas** — **Viaje** (fecha, personas, **extras**) · **Tus datos** (contacto + recogida u hotel + notas) · **Pago**; con dos empresas, «Pago 1 de 2» y «Pago 2 de 2» son sub-pasos dentro de Pago; los traslados también quedan en 3 (contacto + recogida en «Tus datos»); paquetes de varias noches con **duración fija**; cabecera mínima con flecha, logo e idioma; calendario con alcance recortado (sin «pocos lugares» ni corte por cupo de hospedaje).

### Task 8.1: Tres pasos en las cuatro rutas

**Files:** Modify `src/lib/pasos-checkout.ts`, `tests/pasos-checkout.test.cjs`, `checkout-view.tsx`, `pedido/pedido-paquete.tsx`, `traslado-view.tsx`, `checkout-stepper.tsx` (se elimina el numerado), `src/app/[lang]/dictionaries/{es,en}.json` (`checkout.stepper`).

> Hallazgos del crítico verificados: `ORDEN_PASOS` es una constante global de 4 pasos (`pasos-checkout.ts:7-9`); el literal `4` aparece en `checkout-view.tsx:~1249`, `traslado-view.tsx:~595` y `pedido-paquete.tsx:~408-414, ~457, ~531-532` (`actual: 4 + indicePago`); las claves `checkout.stepper` son `trip/contact/extras/payment` y `pedido-paquete.tsx:~404-415` arma `steps`/`etiquetasCortas`; en servicio suelto «detalles» son los extras (`checkout-view.tsx:~1590-1620`) y en paquete una tarjeta por servicio (`pedido-paquete.tsx:~648-654`).

- [ ] **Paso 1: prueba primero** en `tests/pasos-checkout.test.cjs`: `ORDEN_PASOS` es `['viaje','datos','pago']`, `numeroDePaso('pago') === 3`, y `estadoDeTarjeta` mantiene las reglas actuales (oculto / activo / completado / editando). Verla fallar.
- [ ] **Paso 2:** cambiar `PasoId` y `ORDEN_PASOS` a `viaje | datos | pago` (una sola constante vale porque las cuatro rutas quedan iguales). Los sub-pasos de pago por empresa son estado propio del paso Pago (`indicePago`, `totalPagos`), no pasos nuevos: se elimina `actual: 4 + indicePago` y todo `4` literal.
- [ ] **Paso 3:** mover los **extras** al bloque de Viaje (servicio suelto: `bloque-extras` desde «detalles»; paquete: la tarjeta por servicio) y unir `bloque-contacto` + `bloque-recogida` en «Tus datos» (los bloques existen desde F5). La validación viaja con cada bloque; `iniciarPago` revalida viaje y datos (contacto + recogida) y reabre la tarjeta que falle.
- [ ] **Paso 4:** diccionarios: sustituir `checkout.stepper` (`trip/contact/extras/payment`) por `viaje/datos/pago` en es y en, con «Viaje», «Tus datos», «Pago» y «Paso N de 3»; reiniciar `npm run dev` (Turbopack cachea los JSON).
- [ ] **Paso 5: límite de campos** — contar los controles de «Viaje» por ruta (fecha, personas, extras obligatorios y opcionales). Si en alguna ruta pasan de ~7, **parar y avisar al dueño** antes de seguir (PFD R1): los opcionales se pliegan bajo «Más opciones» en vez de crear un cuarto paso.
- [ ] **Paso 6:** recorridos manuales de F5 en las cuatro rutas, incluido el rechazo en «Pago 2 de 2». **Paso 7: commit** `feat(checkout): tres pasos en todas las rutas; extras en Viaje`.

### Task 8.2: Cabecera mínima sin navbar y `--nav-alto`

**Files:** Create `src/components/reserva/cabecera-minima.tsx`; Modify el layout de `/reservar` y `/traslados`, `src/app/globals.css`.

- [ ] Flecha de volver (48 × 48), logo redondo de 32 y selector ES/EN; sin navbar completo en `/reservar` y `/traslados`; el cambio de idioma conserva la query (como hoy). `ContinuarReservacion` sigue fuera del checkout.
- [ ] **`--nav-alto` por ruta:** `globals.css:~60-69` ya avisa que este token se desincronizó una vez. Añadir una clase `reserva-minima` en el layout de esas rutas con `--nav-alto: 56px` en móvil y `0px` en escritorio (la cabecera es fija en móvil y estática en escritorio) y `--banda-alto: 0px`. Re-verificar sus consumidores: `pagina-checkout.tsx:~40`, `checkout-loading-shell.tsx:~26,37`, `checkout-section-card.tsx:~189` (scroll-mt), `toast.tsx:~98`, `traslados/page.tsx:~62`, `pedido-paquete.tsx:~365,456,478`, `booking-confirmation.tsx:~132` (`checkout-stepper.tsx` desaparece en 8.3). La confirmación y las pantallas de fallo de la misma ruta usan la misma cabecera.
- [ ] Commit `feat(reserva): cabecera mínima y --nav-alto por ruta`.

### Task 8.3: Título grande, resumen plano y pasos con nombre

- [ ] Título de página 36 px móvil / 56 px escritorio (`texto-pagina`); resumen en elevación 0 (ya en `n0` por F7.3); se elimina `checkout-stepper.tsx`. Las tarjetas de paso muestran «Paso N de 3» y su título en `texto-paso` (24 px móvil / 28 px escritorio, Consola Mono 700). El nombre del paso en el asistente móvil usa la misma clase (24 px).
- [ ] Commit `feat(reserva): título grande, resumen plano y pasos con nombre`.

### Task 8.4: Asistente de un paso en móvil

**Files:** Create `src/components/reserva/{linea-progreso,barra-inferior,asa-resumen}.tsx`.

- [ ] En < 640 px: un paso por pantalla, sin tarjetas plegables; barra inferior fija con `padding-bottom: env(safe-area-inset-bottom)`; **línea de progreso de tres segmentos sin números** (`role="progressbar"`, «Paso 2 de 3: Tus datos») encima del botón; botón principal con etiqueta predictiva («Continuar a tus datos», «Continuar a pago», «Pagar $X a [empresa]»). En el paso Pago con dos empresas se muestra «Pago 1 de 2» bajo el título (no añade segmentos). Flecha de volver arriba a la izquierda; el asa «Ver resumen · $X» abre una hoja con los cargos. El botón deshabilitado dice qué falta.
- [ ] El estado de cada paso vive en el reducer existente; el cambio de paso lleva el foco al título. Recorrido manual en móvil real. PUNTO DEL DUEÑO.
- [ ] Commit `feat(reserva): asistente móvil de un paso con barra inferior`.

### Task 8.5: Calendario completo en la reserva (alcance recortado)

**Files:** Create `src/components/ui/calendario/{calendario,leyenda,atajos}.tsx`, `src/lib/rango-paquete.ts`, `src/lib/ids.ts`, `tests/rango-paquete.test.cjs`; Modify `checkout-view.tsx`, `pedido/fecha-paquete.tsx`, `hero.tsx`, `selector-experiencia.tsx`; Delete `checkout-calendar.tsx`, `sticky-booking-bar.tsx`.

> Hallazgos del crítico verificados: `BookingBar` **no** está en `/reservar`: se usa en `hero.tsx:117` y `selector-experiencia.tsx:172` (la entrada de portada y sede que arma la query hacia `/reservar`); `StickyBookingBar` no se renderiza en ningún sitio, pero `hero.tsx:2` y `selector-experiencia.tsx:~16` importan su constante `ID_BARRA_PORTADA`; `lib/calendario-paquete.ts` solo calcula fechas (`sumarDias`, `nochesDelPaquete`, `fechaDeComponente`, `fechaSalida`); la única fuente de cupo por día es `getCupoRango` (`lib/api.ts:~173-188`, `DisponibilidadRango`: `lleno | sin_panga | sin_lugar | null`), de pangas por empresa y personas.

- [ ] **Entradas del hero y la sede no cambian:** `BookingBar` y el modo popover de `DateField` se quedan (la entrada con fecha y personas hacia `/reservar` sigue igual). Mover `ID_BARRA_PORTADA` a `lib/ids.ts` y actualizar los dos imports; borrar `sticky-booking-bar.tsx` (código muerto).
- [ ] **En `/reservar`**, el paso Viaje monta siempre el calendario completo `ui/calendario` (fondo blanco, borde `borde`, radio 16, sin sombra; días en círculo de 44 px); `checkout-calendar.tsx` se borra y `fecha-paquete.tsx` lo usa.
- [ ] **Rango de paquete (función pura con prueba primero):** `rangoDelPaquete(inicio, noches)` construida **sobre** `sumarDias` y `nochesDelPaquete` de `calendario-paquete.ts` (no los duplica) y `diasSinCupoEnRango(rango, disponibilidad: DisponibilidadRango)` que marca solo los días que `getCupoRango` ya declara llenos. Casos de la prueba: rango de N noches, 0 noches, un solo día, un día `lleno` dentro del rango y `null` en todos. **No hay «pocos lugares» ni corte por cupo de hospedaje o de componentes**; el cupo definitivo se valida al pagar, como hoy.
- [ ] **Interacción:** hover, foco o primer toque en móvil = vista previa (`cafe-bruma` + borde discontinuo `cafe`); elegir = rango firme (`cafe-claro`, extremos `cafe`); en móvil el segundo toque en el mismo día confirma.
- [ ] **Leyenda** hecha con los mismos componentes que las celdas: Disponible, Sin cupo (donde se sabe), Hoy, Tu selección, Vista previa, Rango confirmado — cada uno con color **y** forma. **Atajos:** «Borrar fecha», «Mañana», «En 2 días» (valores editables).
- [ ] Teclado completo (flechas, Re Pág, Av Pág, Inicio, Fin, Esc).
- [ ] Commit `feat(reserva): calendario completo con leyenda, atajos y rango de paquete`.

### Task 8.6: Cierre de F8 y lanzamiento conjunto

- [ ] `verificar` completo; recorridos manuales de F5 en escritorio **y** móvil real, es y en, con tarjeta de prueba de Stripe en los cuatro caminos (servicio, paquete de una empresa, cruza-empresa con rechazo en «Pago 2 de 2», traslados). PUNTO DEL DUEÑO.
- [ ] Un solo merge y un solo deploy de F7 + F8; si falla algo, se revierte el merge completo.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un refactor del checkout rompe el cobro | Fases F4/F5 por pasos, sin cambio de lógica; `lib/` ya tiene 22 suites; prueba de pago real con tarjeta de prueba de Stripe en el entorno QA tras cada paso; el dueño recorre el flujo |
| Diferir Stripe produce un salto de layout | *Fallback* del mismo tamaño; el resumen no se difiere (Task 1.2) |
| Las 22 suites no cubren componentes | Se declara; la red es compuerta + `tsc` + `build` + revisión del dueño; se evalúa añadir pruebas de componente en un plan aparte |
| La compuerta bloquea trabajo urgente | El trinquete permite bajar, no exige 0 hasta el cierre de F4 |
| El tipo de `dict` recortado rompe llamadores | Lo detecta `tsc`; ahorro modesto, la tarea es la última de F1 |
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
| Quitar la barra de reserva rompe la entrada desde portada y sede | `BookingBar` y `DateField` popover se quedan; solo se quita el calendario antiguo de la ruta de reserva |
| Falsos positivos de la compuerta (comentarios, anclas `#add`) | Se ignoran comentarios, la regex de hex exige 3/4/6/8 dígitos y la prueba es la especificación |

## Orden y dependencias

`F0` → `F1` (en paralelo con `F2`) → `F3` → `F4` grupos 1-3 → `F5` → `F4` grupo 4 (ya dentro de `pasos/*`) → `F6` → `F7` + `F8` (salen juntas). F1 puede salir a producción sola (mejora el lanzamiento sin tocar el aspecto). F2 no cambia nada visible. F4 y F5 son los que más piden la revisión del dueño.

## Autorrevisión

- **Cobertura:** R1 (F3/F4/F5, 8.1, 8.4), R2 (1.5, 5.4, 8.2, 8.3), R3 (F2, guardia, 8.1), R4 (restricciones, F4, F5, F7, 8.5), R5 (3.2, F7, 8.4); los 13 puntos de la petición de reserva están en F8 (1→8.2, 2→8.3, 3→8.3, 4→8.3, 5→8.5, 6→8.5, 7→8.3, 8→8.1, 9–12→8.4, 13→8.5); hallazgos V1–V9 asignados a tareas o a F7/futuro (V7 como sondeo, V8 a F7, V9 anotado).
- **Sin marcadores:** las tareas de F4/F5 son procedimentales porque cada una depende de leer el archivo real; llevan regla, orden, puerta y criterio de cierre. Las de F0–F3 llevan código.
- **Consistencia de nombres:** `botonClases`, `FormularioPagoDiferido`, `guardia-estilos.cjs`, `TOKENS_PAGO`, `--radius-control`/`--radius-campo`.
- **Limitación honesta:** los valores de Tailwind (Task 2.1) se copian de `node_modules`, no se citan de memoria; las alturas de los *fallbacks* (1.2) se miden al ejecutar.
- **Crítico de arquitectura:** ejecutado el 2026-10-15 (resultado: REVISION REQUIRED, 3 críticos y 4 significativos). Aplicadas: runner de pruebas (`guardia` fuera del runner, `variantes.ts` sin imports), partir `stripe-panel.tsx` antes de diferir, exentos y regex de la compuerta, F4-núcleo después de F5, capas `ui`, tokens de forma y de pago, `@theme` aparte sin byte-a-byte, Task 1.7 movida a 5.5, recorridos manuales. Ronda 3 (F7/F8): REVISION REQUIRED; aplicadas con las decisiones del dueño (3 pasos con extras en Viaje y «Pago 1 de 2» como sub-paso, calendario recortado, sin palabra caligráfica, página arena con tarjetas blancas), más `--nav-alto`, `BookingBar` intacto, lista de consumidores de fuentes, pasada de sombras/foco/titulares y bloques en F5. Pendiente: ronda 4 hasta `APPROVED`.
