# Base del frontend antes de la marca nueva — Plan de implementación

> **Para quien ejecute:** usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans`. Los pasos usan casillas `- [ ]`. **Regla del dueño:** nada de este plan que toque UI visible se programa sin su luz verde explícita en cada punto de control marcado «PUNTO DEL DUEÑO».

**Meta:** dejar el frontend con tokens completos, primitivas con variantes, vistas de compra partidas y carga optimizada, de modo que la identidad de marca nueva sea un cambio de valores de token y variantes en un solo lanzamiento, sin regresiones en el checkout.

**Arquitectura:** tres capas. (1) `globals.css` declara *todos* los tokens, incluidos radio, sombra y escala de texto, con los valores actuales; Tailwind 4 hace que `rounded-lg`, `shadow-md`, `text-sm` etc. lean esos tokens, así que la marca los cambia en un solo sitio. (2) `src/components/ui/` contiene las primitivas; la lógica de variantes vive en un módulo puro probado con el runner existente. (3) Una compuerta automática con «trinquete» (solo baja) impide reintroducir colores, radios o controles crudos.

**Stack:** Next.js 16.3, React 19.2, Tailwind 4.3.3, `motion`, `@phosphor-icons/react`, Stripe. Se añaden `clsx`, `tailwind-merge` y `class-variance-authority`.

**Fuentes de fundamento:** derivación PFD (R1–R5, abajo) + skills de Vercel `react-best-practices`, `nextjs`, `next-cache-components`, `shadcn`, `vercel-storage`. Mediciones del 2026-10-15 sobre la rama `qa/checkout-unificado`.

## Restricciones globales

- **Checkout visible idéntico** (diferencia visual cero) hasta la fase F7. Montos, cargos, plazos y textos de cobro no cambian. *(PFD R4)*
- La marca nueva aterriza **en un solo lanzamiento**; nunca una mezcla vieja/nueva en producción. *(PFD R4)*
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
| V2 | `stripe-panel` (Stripe + Elements) se importa estático en las 3 vistas de compra; los calendarios (`DateField`, `CheckoutCalendar`) también | `bundle-dynamic-imports` (CRÍTICA) | Stripe sale del primer paso, solo se baja al llegar a pagar |
| V3 | Se pasa el diccionario completo (`dict`, 55,8 KB en es) a 5 componentes cliente; solo usan `checkout` (18 KB), `pedido`, `traslados`, `feedback`, `continuar` | `server-serialization` (ALTA) | Ahorro modesto (~20 KB por idioma): es la última de F1 |
| V4 | 0 `<Suspense>`, solo 2 `loading.tsx` (reservar, traslados) y **ningún** `error.tsx`/`global-error.tsx` | `async-suspense-boundaries` (ALTA) + guía de errores de `nextjs` | Un fallo de la API tumba la página sin diseño |
| V5 | Video de 83,5 MB servido desde `public/` (`videohero.webm`), también referenciado por 2 sedes | `rendering-*` + `next/image` | Mayor riesgo de lanzamiento |
| V6 | 1 `<img>` cruda en `sede-hero.tsx:67` | guía `nextjs/image` | LCP y tamaños |
| V7 | `request()` en `lib/api.ts` hace `fetch` sin política de caché | `next-cache-components` (`use cache`, `cacheLife`, `cacheTag`) | Oportunidad solo para el catálogo público; **nunca** cupo ni cotización. Entra como sondeo (spike) con decisión, no como compromiso |
| V8 | Fuente `Bella Fashion` con licencia «personal use only» (aviso en `fonts/LICENCIAS.md`) | — | Se resuelve con la tipografía de la marca nueva (F7) |
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
| `scripts/guardia-estilos.cjs` | Cuenta infracciones (colores literales, paleta cruda, `<button>`/`<input>` fuera de `ui/`, `<img>`) y falla si suben | F0 |
| `scripts/guardia-estilos.baseline.json` | Recuento inicial por regla y archivo | F0 |
| `tests/guardia-estilos.test.cjs` | Prueba la detección con cadenas de ejemplo | F0 |
| `docs/superpowers/plans/2026-10-15-frontend-base-linea-base.md` | Tamaños por ruta antes/después | F0 |
| `next.config.ts` | `optimizePackageImports`, `images`, CSP si hace falta | F1 |
| `src/app/[lang]/error.tsx`, `src/app/global-error.tsx` | Errores con diseño | F1 |
| `src/app/[lang]/{sede/[slug],servicio/[empresa]/[servicio],catalogo}/loading.tsx` | Esqueletos de carga | F1 |
| `src/components/ui/cn.ts` | `clsx` + `tailwind-merge` | F3 |
| `src/components/ui/variantes.ts` | Mapas de variantes **puros** (probables sin DOM) | F3 |
| `src/components/ui/{button,input,field,card,badge}.tsx` | Primitivas | F3 |
| `src/components/ui/hero-media.tsx`, `section-shell.tsx` | Héroe y sección únicos | F5 |
| `src/components/checkout/pasos/*.tsx` | Un archivo por paso, extraídos de las vistas gigantes | F5 |
| `tests/variantes.test.cjs` | Prueba de las variantes | F3 |

---

## F0 — Red de seguridad y línea base

### Task 0.1: Compuerta de estilos con trinquete

**Files:** Create `scripts/guardia-estilos.cjs`, `tests/guardia-estilos.test.cjs`; Modify `package.json`, `tests/run-hub-tests.cjs`.

**Interfaces — Produces:** `npm run guardia` (sale con código 1 si alguna regla sube respecto a `guardia-estilos.baseline.json`) y la función exportada `contar(texto, regla)`.

- [ ] **Paso 1: prueba que falla** — `tests/guardia-estilos.test.cjs`:

```js
const assert = require('node:assert/strict');
const { contar } = require('../scripts/guardia-estilos.cjs');

assert.equal(contar('<button className="x">', 'boton-crudo'), 1);
assert.equal(contar('<Button>', 'boton-crudo'), 0);
assert.equal(contar('className="bg-red-400"', 'paleta-cruda'), 1);
assert.equal(contar('className="bg-accent"', 'paleta-cruda'), 0);
assert.equal(contar('style={{ color: "#fff" }}', 'color-literal'), 1);
assert.equal(contar('<input type="text" />', 'input-crudo'), 1);
assert.equal(contar('<img src="a" />', 'img-cruda'), 1);
console.log('guardia-estilos OK');
```

- [ ] **Paso 2:** correr `node tests/guardia-estilos.test.cjs` → falla («no existe el módulo»).
- [ ] **Paso 3: implementar** `scripts/guardia-estilos.cjs` (CommonJS para que el runner de pruebas y `node` lo carguen sin compilar):

```js
const fs = require('node:fs');
const path = require('node:path');

const REGLAS = {
  'boton-crudo': /<button\b/g,
  'input-crudo': /<(input|select|textarea)\b/g,
  'img-cruda': /<img\b/g,
  'paleta-cruda':
    /\b(?:bg|text|border|ring|from|to|via|fill|stroke|divide|outline)-(?:red|green|blue|amber|sky|gray|slate|zinc|neutral|stone|yellow|orange|emerald|teal|indigo|violet|purple|pink|rose|lime|cyan|fuchsia)-\d{2,3}\b/g,
  'color-literal': /#[0-9a-fA-F]{3,8}\b|rgba?\(/g,
};
// Fuera de la regla: el único sitio donde los valores crudos son legítimos.
const EXENTOS = ['src/app/globals.css'];
// Las primitivas son el único lugar donde vive el HTML crudo de estos controles.
const EXENTOS_POR_REGLA = {
  'boton-crudo': ['src/components/ui/'],
  'input-crudo': ['src/components/ui/'],
};

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
    if (EXENTOS.includes(rel)) continue;
    const texto = fs.readFileSync(abs, 'utf8');
    for (const regla of Object.keys(REGLAS)) {
      if ((EXENTOS_POR_REGLA[regla] ?? []).some((p) => rel.startsWith(p))) continue;
      const n = contar(texto, regla);
      if (n > 0) (resultado[regla] ??= {})[rel] = n;
    }
  }
  return resultado;
}

module.exports = { contar, medir };

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

(El guion se llama `guardia-estilos.cjs`; el mapa de archivos lo lista con esa extensión.)

- [ ] **Paso 4:** registrar la suite en `tests/run-hub-tests.cjs` (`'guardia-estilos': ['scripts/guardia-estilos.cjs', 'GUARDIA_TEST_OUT']`, siguiendo el patrón de las otras); correr `npm.cmd test -- guardia-estilos` → pasa.
- [ ] **Paso 5:** en `package.json` añadir `"guardia": "node scripts/guardia-estilos.cjs"`; generar la línea base con `node scripts/guardia-estilos.cjs --escribir`; correr `npm.cmd run guardia` → «Infracciones: N (línea base N)», código 0.
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

### Task 1.2: Stripe y calendarios bajo demanda (V2)

**Files:** Modify `src/components/checkout-view.tsx:23`, `src/components/pedido/pedido-paquete.tsx:22`, `src/components/traslado-view.tsx:11`; Create `src/components/checkout/pago-diferido.tsx`.

**Interfaces — Produces:** `StripePanelDiferido` y `FormularioPagoDiferido` con las mismas props que `StripePanel` y `FormularioPago` (los tipos se infieren con `ComponentProps<typeof ...>`).

- [ ] **Paso 1:** leer la altura real del formulario de pago y del panel de resumen para que el *fallback* ocupe lo mismo (sin salto de layout, requisito PFD R4). Usar `Skeleton` de `src/components/skeleton.tsx`.
- [ ] **Paso 2:** crear `pago-diferido.tsx`:

```tsx
'use client';

import dynamic from 'next/dynamic';
import { Skeleton } from '@/components/skeleton';

export const StripePanelDiferido = dynamic(
  () => import('@/components/stripe-panel').then((m) => m.StripePanel),
  { ssr: false, loading: () => <Skeleton className="h-80 w-full" /> },
);

export const FormularioPagoDiferido = dynamic(
  () => import('@/components/stripe-panel').then((m) => m.FormularioPago),
  { ssr: false, loading: () => <Skeleton className="h-64 w-full" /> },
);
```

(ajustar las alturas a las medidas del paso 1).
- [ ] **Paso 3:** en las 3 vistas, reemplazar el import estático por estos y usarlos en los mismos sitios. Cuidar que `StripePanel` se renderiza desde el paso 1 como resumen del pedido: si el resumen debe verse de inmediato, **separar el resumen** del formulario de tarjeta en vez de diferir el panel entero; solo el formulario (`FormularioPago` y su `Elements`) se difiere. Anotar la decisión en el commit.
- [ ] **Paso 4:** `tsc`, `eslint`, `npm test`, `build`; comparar First Load JS de `/reservar` y `/traslados` con la línea base.
- [ ] **Paso 5: commit** `perf(checkout): el formulario de tarjeta se carga al llegar a pagar`.

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

### Task 1.7: Diccionario por sección en los clientes (V3, ahorro modesto)

**Files:** Modify los 5 clientes que reciben `dict: Dictionary` y las 3 páginas que pasan `dict={dict}`.

- [ ] **Paso 1:** para cada cliente, ver qué secciones usa (`grep -oE "dict\.[a-zA-Z]+"`).
- [ ] **Paso 2:** cambiar el tipo de la prop a las secciones necesarias, p. ej. `dict: Pick<Dictionary, 'checkout' | 'pedido' | 'feedback' | 'continuar' | 'traslados'>`, y en la página pasar solo ese recorte. Dejar que `tsc` dé la lista de lo que falta.
- [ ] **Paso 3:** medir con `build`; si el ahorro real es < 10 KB, dejarlo así y anotarlo.
- [ ] **Paso 4: commit** `perf(checkout): el cliente recibe solo las secciones del diccionario que usa`.

### Task 1.8: Sondeo de Cache Components (V7) — decisión, no código en producción

- [ ] Leer `node_modules/next/dist/docs/` sobre `cacheComponents` y `use cache` en 16.3. Probar en una rama aparte con `getServicioDetalle`/`getPaqueteDetalle` y `cacheLife('minutes')`. Escribir en el archivo de línea base: qué ruta mejora, cuánto, y cómo se invalida un precio editado en el backoffice. **Sin decisión del dueño no se activa.** Cupo, cotización y pagos quedan fuera siempre.

---

## F2 — Tokens completos, sin cambiar un solo valor (PFD R3)

> Idea clave: en Tailwind 4, declarar `--radius-*`, `--shadow-*` y `--text-*` dentro de `@theme` con los **mismos** valores por defecto hace que todas las utilidades existentes los lean desde `globals.css`. Después la marca los cambia en un solo sitio, y no hay que tocar componentes. Sin diferencia visual.

### Task 2.1: Declarar radio, sombra y escala de texto

**Files:** Modify `src/app/globals.css` (dentro del bloque `@theme inline` existente, junto a `--font-*`).

- [ ] **Paso 1:** abrir `node_modules/tailwindcss/theme.css` y copiar **literalmente** los valores de `--radius-xs…4xl`, `--shadow-xs…2xl`, `--text-xs…6xl` y sus `--text-*--line-height`. No escribirlos de memoria.
- [ ] **Paso 2:** pegarlos en `@theme` (los de radio y sombra tal cual están en el tema, p. ej. `--radius-lg: 0.5rem;`). Quitar `inline` solo si es necesario para que los valores sean variables CSS reales (la regla de Tailwind: `inline` resuelve en tiempo de compilación; los tokens que la marca cambie deben ser variables, por lo que se declaran en un `@theme` sin `inline`).
- [ ] **Paso 3:** añadir los tokens semánticos que faltan y hoy son literales: `--color-ring` (anillo de foco), y mapear `border-red-400` de `CAJA_CAMPO_ERROR` a `--color-error` (ya existe `border-error`).
- [ ] **Paso 4:** `build`; la salida de las rutas debe ser byte a byte equivalente a la línea base (mismo CSS utilitario). Cualquier diferencia visual se revierte.
- [ ] **Paso 5: commit** `refactor(frontend): radio, sombra y escala de texto como tokens, sin cambio visual`.

### Task 2.2: Retirar los literales de color restantes

**Files:** los archivos con `color-literal` y `paleta-cruda` según `scripts/guardia-estilos.baseline.json` (66 literales + 13 de paleta + 3 arbitrarios en la medición).

- [ ] **Paso 1:** por archivo, reemplazar cada color por su token semántico (`bg-red-400`→`bg-error`, etc.). Los rgba de degradados sobre foto (`hero.tsx`) se convierten en tokens `--scrim-*` en `globals.css`.
- [ ] **Paso 2:** si un literal no tiene equivalente exacto, **no redondear**: crear el token con el valor exacto (Bujack 2022: la desviación casi igual cuesta más que la clara).
- [ ] **Paso 3:** `guardia` (baja), actualizar línea base. **Paso 4: commit** `refactor(frontend): colores literales pasan a tokens`.

---

## F3 — Primitivas con variantes (PFD R1, R5)

### Task 3.1: Dependencias y `cn`

**Files:** Modify `package.json`; Create `src/components/ui/cn.ts`.

- [ ] `npm install clsx tailwind-merge class-variance-authority`.
- [ ] `src/components/ui/cn.ts`:

```ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...entradas: ClassValue[]) {
  return twMerge(clsx(entradas));
}
```

- [ ] Commit `chore(frontend): clsx, tailwind-merge y cva para las primitivas`.

### Task 3.2: Variantes puras y probadas

**Files:** Create `src/components/ui/variantes.ts`, `tests/variantes.test.cjs`; Modify `tests/run-hub-tests.cjs`.

**Interfaces — Produces:** `botonClases({ variante, tamano }): string`; variantes `principal | secundario | texto | acento | peligro`; tamaños `md | sm | icono`.

- [ ] **Paso 1: prueba** `tests/variantes.test.cjs`:

```js
const assert = require('node:assert/strict');
const { botonClases } = require('../src/components/ui/variantes');

// R5: solo la variante principal usa el color de acción.
assert.match(botonClases({ variante: 'principal' }), /bg-action/);
for (const v of ['secundario', 'texto', 'acento', 'peligro']) {
  assert.doesNotMatch(botonClases({ variante: v }), /bg-action/);
}
// Área táctil mínima de 40 px en las acciones de texto (regla ya vigente).
assert.match(botonClases({ variante: 'texto' }), /min-h-10/);
// Sin colores crudos: todo por tokens.
for (const v of ['principal', 'secundario', 'texto', 'acento', 'peligro']) {
  assert.doesNotMatch(botonClases({ variante: v }), /-(red|green|blue|amber)-\d/);
}
console.log('variantes OK');
```

- [ ] **Paso 2:** correr → falla. **Paso 3: implementar** `variantes.ts` con `cva` copiando **las clases exactas** de `BotonPaso` (`inline-flex items-center justify-center gap-2 rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground …`) para `principal` y de `AccionTexto` para `texto`/`acento`, de modo que migrar un componente a la primitiva no cambie píxeles:

```ts
import { cva, type VariantProps } from 'class-variance-authority';

export const botonVariantes = cva(
  // clases comunes copiadas de BotonPaso / AccionTexto, ver Paso 3
  'inline-flex items-center justify-center gap-2 font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
  {
    variants: {
      variante: {
        principal: 'rounded-full bg-action px-6 py-2.5 text-sm text-action-foreground', // + resto copiado de BotonPaso
        secundario: 'rounded-full border border-border-strong bg-background px-6 py-2.5 text-sm text-foreground hover:bg-surface',
        texto: 'min-h-10 gap-1.5 text-xs text-muted hover:text-foreground',
        acento: 'min-h-10 gap-1.5 text-xs text-accent hover:text-foreground',
        peligro: 'rounded-full border border-error bg-error-fondo px-6 py-2.5 text-sm text-error',
      },
      tamano: { md: '', sm: 'px-4 py-1.5 text-xs', icono: 'size-10 p-0' },
    },
    defaultVariants: { variante: 'principal', tamano: 'md' },
  },
);

export type BotonVariantes = VariantProps<typeof botonVariantes>;
export const botonClases = (v: BotonVariantes = {}) => botonVariantes(v);
```

(sustituir los comentarios «copiado de» por las clases reales al leer los dos archivos).
- [ ] **Paso 4:** registrar la suite y correrla → pasa (`variantes` necesita compilar `cva`; si el runner no resuelve `class-variance-authority` desde `tests/`, apuntarlo con `NODE_PATH` como hacen las otras suites o probar la función desde el JS compilado). **Paso 5: commit** `feat(ui): variantes de botón puras y probadas`.

### Task 3.3: `Button`, `Input`, `Field`, `Card`, `Badge`

**Files:** Create `src/components/ui/{button,input,field,card,badge}.tsx`.

**Interfaces — Produces:**
- `Button(props: ButtonHTMLAttributes & BotonVariantes & { conFlecha?: boolean; cargando?: boolean })`, siempre `type="button"` salvo que se indique `type="submit"`.
- `Input(props: InputHTMLAttributes & { invalido?: boolean })`, con `aria-invalid`.
- `Field({ etiqueta, error, ayuda, id, children })`: etiqueta, control y `ErrorDeCampo` (reutiliza el existente con `Despliegue`).
- `Card`/`Badge`: contenedores con variantes (`plana | elevada`, `exito | aviso | error | neutro`).

- [ ] Por componente: escribir, usar `cn` y las variantes; `Input` usa `CAJA_CAMPO`/`CAJA_CAMPO_ERROR` de `checkout/estilos.ts` (que a su vez se reescribe sobre tokens).
- [ ] Probar en **una sola pantalla**: sustituir los botones de `faq-section.tsx` (superficie pública de bajo riesgo) por `Button`. Verificar con `tsc`, `eslint`, `build`, `guardia` (baja).
- [ ] PUNTO DEL DUEÑO: mirar la sección de preguntas frecuentes (debe verse igual).
- [ ] Commit por componente.

### Task 3.4: Absorber lo ya existente

- [ ] `BotonPaso` pasa a ser un envoltorio de `Button variante="principal"`; `AccionTexto` y `EtiquetaModificar` usan `botonVariantes({ variante: 'texto' | 'acento' })`. Los nombres se conservan para no tocar los llamadores. Commit `refactor(checkout): BotonPaso y AccionTexto sobre la primitiva Button`.

---

## F4 — Migrar los 84 controles (uno por superficie, aspecto idéntico)

Recuento medido (`<button`): continuar-reservacion 7, reviews-carousel 5, grupo-servicio 4, fecha-paquete 4, hub-mapa-sedes 4, stripe-panel 3, date-field 3, checkout-view 3, checkout-calendar 3, y 23 archivos con 1 o 2. Controles de formulario (`<input|select|textarea>`): stripe-panel 4, grupo-servicio 4, traslado-view 2, checkout-view 2, field-popover 1, select-personalizado 1, campos-contacto 1.

**Regla de migración (aplica a todas las tareas):** una superficie por commit; el JSX resultante genera las mismas clases (comparar el HTML renderizado en el `build` no basta: se compara el diff de clases a mano); si una variante no existe, **se añade la variante** a `variantes.ts` con su prueba, no se deja un `<button>` crudo.

Orden por riesgo creciente (PUNTO DEL DUEÑO al cerrar cada grupo):
1. **Públicas sin dinero:** `faq-section`, `cookie-notice`, `lang-switch`, `site-header`, `sede-selector`, `reviews-carousel`, `hub-mapa-sedes`, `hub-hero`, `paquete-card`, `selector-experiencia`, `sticky-booking-bar`, `continuar-reservacion`.
2. **Campos y selectores compartidos:** `field-popover`, `date-field`, `time-field`, `people-stepper`, `checkout-calendar`, `select-personalizado`, `toast`.
3. **Checkout, tarjetas auxiliares:** `checkout-section-card`, `campos-contacto`, `tipo-traslado-cards`, `ayuda-flotante`, `reserva-plegable`, `aviso-fallo`.
4. **Checkout, núcleo:** `grupo-servicio`, `fecha-paquete`, `checkout-view`, `traslado-view`, `stripe-panel`, `booking-confirmation`. Se hace al final y de una vez, con revisión del dueño del flujo completo (servicio, paquete de una empresa y cruza-empresa, traslados).

Cada tarea: sustituir, correr la puerta de siempre, `guardia` debe **bajar**, actualizar la línea base, commit `refactor(<superficie>): controles sobre las primitivas`. Al terminar el grupo 4, `guardia` marca 0 en `boton-crudo` e `input-crudo`; se cambia el script para que esas dos reglas fallen con cualquier valor > 0.

---

## F5 — Partir las vistas y unificar héroes (PFD R1, R4)

> Es refactor puro: ningún texto, flujo ni estilo cambia. Cada extracción es un commit.

### Task 5.1: Partir `checkout-view.tsx` (1 703 líneas, 36 `useState`)

**Files:** Create `src/components/checkout/pasos/{paso-viaje,paso-contacto,paso-detalles,paso-pago}.tsx`; Modify `checkout-view.tsx`.

- [ ] **Paso 1:** leer el archivo completo y listar por paso el estado que posee y el que comparte. Dibujar el mapa de estado en el commit.
- [ ] **Paso 2:** el estado compartido sube a un *reducer* (el patrón ya existe en `lib/pedido-estado.ts` + `use-pedido-estado.ts` para paquetes); el estado local de un paso baja a su componente. Regla `rerender-no-inline-components`: ningún componente se define dentro de otro.
- [ ] **Paso 3:** extraer un paso por commit en este orden: pago, detalles, contacto, viaje. Tras cada extracción: `tsc`, `eslint`, `npm test`, `build`, `guardia`.
- [ ] **Paso 4:** PUNTO DEL DUEÑO tras cada paso extraído (recorrer el servicio suelto completo hasta el pago de prueba).

### Task 5.2: Partir `traslado-view.tsx` (1 006 líneas, 32 `useState`)

- [ ] Mismo procedimiento. Reutiliza `PaginaCheckout`, `ContenidoViaje` y los pasos ya compartidos; el objetivo es que los cuatro pasos de traslados (Viaje · Datos · Recogida · Pago) sean componentes de `checkout/pasos/`.

### Task 5.3: Revisar `pedido-paquete.tsx` (894 líneas)

- [ ] Ya usa hooks y reducer; solo extraer los bloques de JSX grandes en componentes (`grupo-servicio.tsx` ya existe). No es prioridad.

### Task 5.4: Un solo héroe y una sola sección

**Files:** Create `src/components/ui/hero-media.tsx`, `section-shell.tsx`; Modify `hero.tsx`, `hub-hero.tsx`, `sede-hero.tsx` y las secciones about/season/included/license/colaboradores/gallery.

- [ ] `HeroMedia({ imagen, video, alt, prioridad })` encapsula imagen inmediata + video diferido + degradado (el patrón de la Task 1.5). Los tres héroes lo usan.
- [ ] `SectionShell({ fondo: 'papel' | 'bruma' | 'bruma-profunda', titulo, regla })` encapsula el ritmo de secciones (la «paleta v3» solo admite esos tres fondos).
- [ ] Un héroe por commit; PUNTO DEL DUEÑO al terminar (portada, sede, servicio).

---

## F6 — Cerrar la base

- [ ] `guardia`: `boton-crudo`, `input-crudo`, `img-cruda` y `paleta-cruda` en 0 y con umbral duro; `color-literal` solo permitido en `globals.css`.
- [ ] Script `"verificar": "tsc --noEmit && eslint src tests && npm test && npm run guardia && next build"` en `package.json`.
- [ ] Actualizar `frontend/CLAUDE.md`: dónde viven los tokens y las primitivas, la regla «nada crudo», cómo añadir una variante y cómo correr `verificar`.
- [ ] Línea base final de carga en el archivo de F0. Commit `docs(frontend): base cerrada`.

---

## F7 — Marca nueva, en un solo lanzamiento (PFD R4)

**Entradas que faltan y que debe entregar el dueño:** colores (acento, acción, superficies, estados), tipografías de titular, acento y cuerpo (con licencia que cubra uso comercial: resuelve el aviso de `Bella Fashion`), radio, sombras y foto/video definitivos del héroe.

- [ ] En una rama aparte, cambiar **solo** valores de token en `globals.css`, tipografías en `layout.tsx` y las variantes de `variantes.ts` (peso de la variante principal frente a las demás: R5).
- [ ] Revisar contraste (el amarillo nunca como texto sobre papel; regla vigente) y casi-iguales a tokens (`guardia` lo prohíbe).
- [ ] Verificación completa en es y en: portada, hub, sede, servicio, los tres checkouts, traslados, confirmación y páginas de error. PUNTO DEL DUEÑO.
- [ ] Un solo merge y un solo deploy. Si falla algo, revertir el merge completo.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un refactor del checkout rompe el cobro | Fases F4/F5 por pasos, sin cambio de lógica; `lib/` ya tiene 22 suites; prueba de pago real con tarjeta de prueba de Stripe en el entorno QA tras cada paso; el dueño recorre el flujo |
| Diferir Stripe produce un salto de layout | *Fallback* del mismo tamaño; el resumen no se difiere (Task 1.2) |
| Las 22 suites no cubren componentes | Se declara; la red es compuerta + `tsc` + `build` + revisión del dueño; se evalúa añadir pruebas de componente en un plan aparte |
| La compuerta bloquea trabajo urgente | El trinquete permite bajar, no exige 0 hasta el cierre de F4 |
| El tipo de `dict` recortado rompe llamadores | Lo detecta `tsc`; ahorro modesto, la tarea es la última de F1 |
| Marca sin entregar bloquea F7 | F1–F6 no dependen de ella y mejoran el sitio por sí solas |

## Orden y dependencias

`F0` → `F1` (en paralelo con `F2`) → `F3` → `F4` → `F5` → `F6` → `F7`. F1 puede salir a producción sola (mejora el lanzamiento sin tocar el aspecto). F2 no cambia nada visible. F4 y F5 son los que más piden la revisión del dueño.

## Autorrevisión

- **Cobertura:** R1 (F3/F4/F5), R2 (1.5, 5.4), R3 (F2, guardia), R4 (restricciones, F4, F5, F7), R5 (3.2, F7); hallazgos V1–V9 asignados a tareas o a F7/futuro (V7 como sondeo, V8 a F7, V9 anotado).
- **Sin marcadores:** las tareas de F4/F5 son procedimentales porque cada una depende de leer el archivo real; llevan regla, orden, puerta y criterio de cierre. Las de F0–F3 llevan código.
- **Consistencia de nombres:** `botonClases`/`botonVariantes`, `StripePanelDiferido`/`FormularioPagoDiferido`, `guardia-estilos.cjs`.
- **Limitación honesta:** los valores de Tailwind (Task 2.1) se copian de `node_modules`, no se citan de memoria; las alturas de los *fallbacks* (1.2) se miden al ejecutar.
- **No se despachó el crítico de arquitectura** del skill de planes porque requiere un subagente que el dueño no pidió; se puede correr bajo demanda sobre este archivo.
