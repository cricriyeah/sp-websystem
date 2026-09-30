# Hub de agencia y páginas de sede — Plan de implementación

**VERSIÓN REVISADA: 12 tareas — 2026-09-16.** Ejecutar de la Tarea 1 a la Tarea 12.

> **Para el agente ejecutor:** plan independiente del proveedor/modelo. Si tienes Superpowers disponible, puedes usar `executing-plans` o `subagent-driven-development` según las instrucciones de tu entorno. Su ausencia no bloquea este documento. Lee el spec y las instrucciones locales; ejecuta las tareas en el **orden de dependencias** indicado abajo y registra evidencia antes de marcar cada casilla. Este documento describe trabajo pendiente, no una implementación ya verificada.

**Goal:** Convertir `/[lang]` en un hub de agencia (Sal y Sol Baja Experiences) que enlaza a páginas de sede completas (`/[lang]/sede/[slug]`), migrando el contenido y el catálogo que hoy viven en la portada mono-empresa y en `/catalogo`, sin tocar backend/API/pagos.

**Architecture:** El contenido nuevo (empresa fundadora, colaboración, destacadas, otras empresas, hero por-sede) vive hardcodeado en **tres** módulos TS separados por audiencia, no uno: `src/content/sedes-tipos.ts` (solo tipos, sin runtime — importable desde cualquier lado sin costo), `src/content/sedes-indice.ts` (client-safe de verdad: `slug`/`nombre`/`empresaFundadoraNombre`/`logo` — lo mínimo que `SiteHeader`, Client Component montado en cada página, necesita para resolver marca/logo cuando no hay slug en la URL) y `src/content/sedes-cuerpo.ts` (`import 'server-only'` — colaboración, otras empresas, hero completo, negocio; nunca se importa desde un Client Component, y si alguien lo hace por error el build falla en vez de mandar párrafos al bundle de cliente sin necesidad). `getSedeContenido()` en `sedes-cuerpo.ts` combina índice + cuerpo para quien necesita la forma completa (siempre desde Server Components). El contenido que hoy ya es correcto para La Paz y solo necesita "ser null en otras sedes" (temporada, incluye, licencia, galería, reseñas, FAQ) **tampoco se duplica**: la página de sede lo lee directo de `getDictionary(lang)` cuando `slug === 'la-paz'` y usa `null` para cualquier otra sede. `sedesActivas()` (`lib/reconciliar-sedes.ts`) opera únicamente sobre el índice (`Record<string, SedeIndiceEntry>`) — pura, sin fetch propio, recibe `sedesApi: {slug}[] | null` ya resuelto por el caller — y es la misma función que usan hub, sitemap y `SiteHeader`; `SedeSelector` recibe el resultado del header; nadie reimplementa la regla de reconciliación por su cuenta. `getSedes()` (`lib/api.ts`) lleva un `AbortSignal.timeout` explícito antes de entrar al critical path del hub/sitemap, para que un backend colgado caiga en el mismo fallo-abierto que ya cubre un rechazo de red. Dos helpers puros nuevos (`booking-href.ts`, extracción; `selector-experiencia.ts`, resolución + regla mecánica de inline) se testean con `node --test` al estilo que ya usa este repo para `pricing-paquete.ts`/`personalizaciones.ts` (ver `frontend/tests/personalizaciones.test.cjs`). El booking bar heredado de pesca (`BookingBar`/`ProveedorReserva`/`getCupoRango`/`TimeField`) no se toca ni se generaliza — se sigue montando tal cual, solo en la página de sede de `la-paz`.

**Tech Stack:** Next.js 16.3 (Turbopack, App Router, Server Components por defecto), TypeScript estricto, Tailwind (clases utilitarias, sin CSS Modules), `motion/react` para transiciones, `@phosphor-icons/react`, `node --test` + `tsc` ad-hoc para unit tests de lógica pura (no hay Jest/Vitest en este proyecto).

**Spec:** `docs/superpowers/specs/2026-09-15-hub-multisede-design.md` — este plan asume que ya lo leíste; aquí no se repite el porqué de las decisiones (§1 "Correcciones tras dos rondas de revisión adversarial"), solo el cómo.

## Global Constraints

- Cero cambios de backend, modelos o contrato de API — todo el contenido nuevo es hardcodeado en frontend (spec §2).
- `BookingBar`/`ProveedorReserva`/`getCupoRango`/`TimeField` no se generalizan ni se modifican — se montan tal cual, solo en la página de sede de `la-paz` (spec §1.2, §7, §8).
- `PaqueteCard`/`ServiciosSueltosSection` no cambian su JSX, su UI ni a dónde navega su botón de reserva propio — solo se extrae la lógica de armado de `href` a un helper, sin cambiar el resultado (spec §2, §8).
- El índice de contenido (`src/content/sedes-indice.ts`, `SLUGS_CON_CONTENIDO`/`SEDES_INDICE`) es la única fuente de verdad de qué páginas de sede existen; `getSedes()` solo filtra por "sigue activa". Fallo de `getSedes()` → fallo abierto, se muestran todas las sedes del índice (spec §4).
- `sedesActivas(indice, sedesApi)` (`lib/reconciliar-sedes.ts`) es pura: recibe el índice y el resultado ya resuelto de `getSedes()` como parámetros, nunca hace fetch por su cuenta. La usan por igual `SiteHeader`, el hub y el sitemap; `SedeSelector` consume la lista resultante — ninguno reimplementa la intersección.
- `/[lang]/sede/[slug]` llama `notFound()` si el slug no está en `src/content/sedes-indice.ts`, sin consultar la API para decidir existencia (spec §2, §4).
- `src/content/sedes-cuerpo.ts` es `server-only`: ningún Client Component lo importa. Lo único que un Client Component (`SiteHeader`, `SedeSelector`) puede leer de contenido hardcodeado es `src/content/sedes-indice.ts` (slug/nombre/empresa fundadora/logo) — nunca hero completo, colaboración, ni otras empresas.
- `getSedes()` (`lib/api.ts`) usa `AbortSignal.timeout` — un backend colgado (no solo caído) cae en el mismo fallo-abierto que un rechazo de red, en cualquier caller que ya haga `.catch(() => null)`.
- Sin verificación de UI en navegador por el agente — política del proyecto (`verificacion-sin-navegador`). Cada tarea termina con tipos y lint de sus archivos, más las pruebas pertinentes; el build completo se ejecuta al cierre (Tarea 12); el smoke visual (checklist del spec §11) lo hace el dueño manualmente en `localhost`, no es un paso ejecutable de este plan.
- Fuentes nuevas en `frontend/src/...`, pruebas/runner en `frontend/tests/...` y assets en `frontend/public/...`; el plan no toca `backend/`.
- Assets nuevos del spec §10 se preparan en Tarea 6 con las herramientas disponibles. Conservar el formato real de cada archivo y sincronizar sus referencias; cualquier asset interino se identifica para revisión manual y no se presenta como definitivo. No dejar rutas de imagen inexistentes.

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `frontend/tests/run-hub-tests.cjs` | Crear | Runner común de las seis suites del plan; compila a un temporal y configura todas las variables de salida. |
| `frontend/tests/{content-sedes-indice,content-sedes-cuerpo,reconciliar-sedes,booking-href,selector-experiencia}.test.cjs` | Crear | Aserciones de contenido y lógica; `personalizaciones.test.cjs` existente se conserva. |
| `frontend/src/components/site-footer.tsx` | Modificar | `negocio` obligatorio y `sedeSlug` opcional; actualizar los cinco callers actuales en Tarea 8 y agregar el de sede en Tarea 10. Anchors por sede o grid del hub. |
| `frontend/src/content/sedes-tipos.ts` | Crear | Solo tipos (`SedeIndiceEntry`, `SedeHeroContenido`, `SedeNegocio`, `SedeColaboracion`, `SedeDestacada`, `SedeOtraEmpresa`, `SedeServicioTransporte`, `SedeCuerpoContenido`, `SedeContenido`). Sin runtime — `import type` se borra en compilación, cero costo de bundle sin importar quién lo importe. |
| `frontend/src/content/sedes-indice.ts` | Crear | Client-safe de verdad: `SEDES_INDICE: Record<string, SedeIndiceEntry>` (`slug`/`nombre`/`empresaFundadoraNombre`/`logo`), `SLUGS_CON_CONTENIDO`, `getSedeIndice(slug)`. Lo único que `SiteHeader`/`SedeSelector` (Client Components) pueden importar como VALOR de contenido hardcodeado. |
| `frontend/src/content/sedes-cuerpo.ts` | Crear | `import 'server-only'`. Contenido largo por sede: hero completo, negocio, colaboración, otras empresas, servicio de transporte, meta. `SEDES_CUERPO: Record<string, Record<Locale, SedeCuerpoContenido>>`, `getSedeCuerpo(slug, lang)`, y `getSedeContenido(slug, lang)` (combina índice + cuerpo, la forma completa que usan las páginas). Si un Client Component lo importa por error, el build falla — no manda párrafos al bundle sin que nadie los lea ahí. |
| `frontend/src/lib/reconciliar-sedes.ts` | Crear | `sedesActivas(indice: Record<string, SedeIndiceEntry>, sedesApi: {slug: string}[] \| null): SedeIndiceEntry[]` — pura, sin fetch propio, opera solo sobre el índice client-safe. La usan hub, sitemap, `site.ts` (rutas) y `SiteHeader`; `SedeSelector` recibe su resultado. |
| `frontend/src/lib/api.ts` | Modificar | `getSedes()` pasa `AbortSignal.timeout(8000)` a `request()` — sin esto "fallo abierto" solo atrapaba rechazos, nunca un hang, y este plan pone `getSedes()` en el critical path del hub y del build del sitemap. |
| `frontend/src/lib/booking-href.ts` | Crear | `hrefPaquete()`/`hrefServicio()` — extracción exacta de la lógica de armado de URL hoy inline en `PaqueteCard`/`ServiciosSueltosSection`. |
| `frontend/src/components/paquete-card.tsx` | Modificar | Usa `hrefPaquete()` en vez de calcularlo inline. Sin cambio de UI/comportamiento. |
| `frontend/src/components/servicios-sueltos-section.tsx` | Modificar | Usa `hrefServicio()` en vez de calcularlo inline. Sin cambio de UI/comportamiento. |
| `frontend/src/lib/selector-experiencia.ts` | Crear | `resolverChips()` (cruza `destacadas` del contenido con el catálogo real) + `esInlineable()` (regla mecánica de inline, spec §7). Lógica pura, sin JSX. |
| `frontend/src/components/selector-experiencia.tsx` | Crear | Paso 0 visual: chips + "Ver todo", usa `selector-experiencia.ts` y `booking-href.ts`, monta `BookingBar` cuando `esInlineable()` da `true`. |
| `frontend/src/components/about-section.tsx` | Modificar | Nueva prop opcional `imagenSrc`/`imagenAlt` (default = la imagen fija de hoy) para poder reusarlo con la foto de otra sede. |
| `frontend/src/components/sede-hero.tsx` | Crear | Hero de la página de sede: video o imagen según el contenido recibido por props (ya resuelto server-side desde `content/sedes-cuerpo.ts`), monta `BookingBar` solo si `mostrarBookingBar`, siempre monta `SelectorExperiencia`. No modifica `Hero.tsx` (que deja de tener caller tras la Tarea 9, y no se borra: cero riesgo dejarlo, fuera de alcance borrarlo). |
| `frontend/src/components/hub-mapa-sedes.tsx` | Crear | Mapa ilustrado (SVG) + pines + popover. `'use client'`, pero solo importa `type SedeContenido` (se borra en compilación) — recibe `SedeContenido[]` ya resueltos como props desde `page.tsx` (Tarea 9, Server Component), nunca importa `sedes-cuerpo.ts` ni hace fetch. |
| `frontend/src/components/hub-hero.tsx` | Crear | Hero de agencia, CTA que hace scroll a la sección del mapa. |
| `frontend/src/components/hub-grid-sedes.tsx` | Crear | Grid de tarjetas de sede (respaldo accesible/SEO del mapa). |
| `frontend/src/components/hub-por-que.tsx` | Crear | 3 pilares de la agencia. |
| `frontend/src/app/[lang]/page.tsx` | Modificar (reescribe el body) | Deja de ser la portada de Sal y Sol; ensambla `HubHero` + `HubMapaSedes` + `HubGridSedes` + `HubPorQue`. Dejar de importar `Hero`/`AboutSection`/`SeasonSection`/`IncludedSection`/`LicenseSection`/`GallerySection`/`ReviewsSection`/`FaqSection`/`StructuredData`/`StickyBookingBar`/`ProveedorReserva`. |
| `frontend/src/components/structured-data.tsx` | Modificar | Cambia de `{ lang, dict }` a `{ lang, slug, negocio, faqItems, description }`. Sin callers después de la Tarea 9 y hasta integrar la página en la Tarea 10 (el único caller de hoy, `page.tsx`, se le quita en la Tarea 9). |
| `frontend/src/app/[lang]/sede/[slug]/page.tsx` | Crear | Página completa de sede: hero, Paso 0, paquetes, servicios, colaboración, temporada/incluye/licencia (si no null), otras empresas, galería/reseñas/FAQ (si no null), `StructuredData`, footer. `notFound()` si el slug no está en `content/sedes-indice.ts`. |
| `frontend/src/components/site-header.tsx` | Modificar | Nuevas props `variante: 'hub' \| 'sede'` (default `'sede'`) y `sedeSlugActual?: string`. Resuelve la lista una vez en cliente incluso en el hub; sin `sedeSlugActual`, resuelve la selección con `leerSedePreferidaCliente()` + `getSedes()` + `sedesActivas(SEDES_INDICE, ...)` (solo índice — nunca `sedes-cuerpo.ts`) y pasa el resultado (`sedes` + `sedeSeleccionadaSlug`) hacia abajo a `SedeSelector`, que ya no vuelve a pedir `getSedes()` por su cuenta. Logo/marca condicional desde `SedeIndiceEntry.logo`/`empresaFundadoraNombre`, links `#ancla` apuntando a `/${lang}/sede/${slug}#ancla`. |
| `frontend/src/components/sede-selector.tsx` | Modificar | Prop `sedes` cambia de `Sede[]` (API cruda) a `{slug, nombre}[]` (índice reconciliado, provisto por `SiteHeader`). Se borra su `useEffect` con `getSedes()` propio y su fallback hardcodeado a `'la-paz'`: el fallback offline ahora es `Object.values(SEDES_INDICE)` (client-safe, fallo abierto). `handleSelect()` navega a `/${lang}/sede/${slug}` en vez de `/${lang}/catalogo?sede=${slug}`. |
| `frontend/src/app/[lang]/deslinde/page.tsx`, `privacidad/page.tsx`, `not-found.tsx` | Modificar | Pasan `variante="sede"` sin `sedeSlugActual` explícito (fallback cliente). Cambio de una línea cada uno. |
| `frontend/src/app/[lang]/traslados/page.tsx` | Modificar | Resuelve `sedeSlugActual` SERVER-SIDE (buscando en `content/sedes-cuerpo.ts` cuál sede trae `servicioTransporte.empresaSlug === empresaSlug`) y lo pasa como prop a `TrasladoView` y al `SiteHeader` de la rama "no disponible"; cambia el link "volver" de `/${lang}/catalogo` a `/${lang}/sede/${slug}`. |
| `frontend/src/components/traslado-view.tsx` | Modificar | Nueva prop `sedeSlugActual: string \| undefined` (ya resuelta por `traslados/page.tsx` — este componente es `'use client'` y NO debe importar `content/sedes-cuerpo.ts`). La usa para `SiteHeader` y el link "volver" (línea ~500). |
| `frontend/src/components/paquete-checkout.tsx` | Modificar | `sedeSlugActual={sedeSlug}` en los 6 mounts de `SiteHeader` (ya tiene `sedeSlug` en scope, viene de datos de la orden/API, no de `content/`); link "volver" (línea ~557) de `/${lang}/catalogo` a `/${lang}/sede/${sedeSlug}`. |
| `frontend/src/components/checkout-view.tsx`, `booking-confirmation.tsx` | Modificar | Pasan `variante="sede"` sin `sedeSlugActual` explícito (fallback cliente; ninguno de los dos tiene sede resuelta server-side hoy). |
| `frontend/src/app/[lang]/catalogo/page.tsx` | Modificar (reemplaza el contenido) | Deja de tener contenido propio: solo `redirect()` a `/${lang}/sede/${slug}` si `?sede=` es un slug válido en `content/sedes-indice.ts`, si no a `/${lang}`. |
| `frontend/src/app/[lang]/catalogo/loading.tsx` | Borrar | Ya no hace falta: el stub no suspende en nada. |
| `frontend/src/lib/site.ts` | Modificar | `RUTAS` (estáticas) se separa de una nueva `rutasSedes()` async que usa `sedesActivas()`. |
| `frontend/src/app/sitemap.ts` | Modificar | `sitemap()` se vuelve `async`, agrega las rutas de sede de `rutasSedes()`. |

## Estado de revisión y orden de ejecución

Corrección documental del 2026-09-16 (reagrupada de 21 a 12 tareas): sincroniza arquitectura, pasos y código tras la revisión interrumpida. Se corrigieron el contrato de `SedeSelector`, la resolución server-side de traslados, la firma del sitemap, el orden de dependencias y los comandos de pruebas. También se contrastaron los callers de `SiteFooter` con el worktree real. El reporte completo de la última ronda de critic no está adjunto: esta corrección no afirma haber recuperado ni cerrado hallazgos que no figuran en este documento.

**Plan simplificado a 12 tareas funcionales. Ejecutarlas en orden numérico, del 1 al 12.** Los cambios de un helper y sus consumidores se completan en la misma tarea; las comprobaciones de tipos/lint se consolidan al cierre de cada grupo. Se conservan las pruebas de comportamiento y los pasos de implementación concretos.

| Tarea | Resultado |
|---|---|
| 1 | Contenido de sedes y preparación de pruebas |
| 2 | Sedes activas y timeout de consulta |
| 3 | URLs de reserva compartidas y adopción en tarjetas |
| 4 | Selector de experiencias: lógica y componente |
| 5 | Componentes reutilizables de la página de sede |
| 6 | Secciones, recursos gráficos y textos del hub |
| 7 | Navegación por sede: selector y encabezado |
| 8 | Footer por sede y actualización de sus consumidores |
| 9 | Activar la portada como hub de agencia |
| 10 | Página completa de sede y datos estructurados |
| 11 | Migración de enlaces, redirecciones y sitemap |
| 12 | Verificación integral y entrega |

Cada tarea agrupada contiene bloques de trabajo en el orden en que se necesitan. Esos bloques no requieren commits separados: hacer un único commit al terminar la tarea y pasar sus verificaciones. La tarea final solo genera commit si hace falta corregir algo.
Cada tarea termina sin errores nuevos de tipos/lint. No aceptar errores de compilación como deuda para una tarea futura. Estos commits son hitos de implementación: no desplegar estados intermedios que todavía no tengan creadas las rutas enlazadas. Los pasos de prueba en rojo se ejecutan antes de implementar; las comprobaciones de cierre deben quedar verdes.

**Entorno de comandos:** trabajar en este worktree y ejecutar validaciones desde `frontend/`. Los comandos de staging/commit se ejecutan desde la raíz del worktree. En Windows PowerShell 5.1, ejecutar por separado comandos escritos con `&&`, comprobar `$LASTEXITCODE` y detenerse al primer fallo; no pegar escapes Bash como `\[lang\]`: usar rutas entre comillas con `[lang]` literal. No incluir cambios ajenos en los commits.

### Preparación de pruebas (incluida en la Tarea 1)

Crear `frontend/tests/run-hub-tests.cjs` con el siguiente contenido. Usa el TypeScript instalado y la configuración del proyecto (incluidos aliases y JSON), compila solo las raíces de las suites elegidas y sus dependencias, y configura todas las variables en cada ejecución. Los imports **runtime** entre helpers nuevos deben ser relativos: `tsc` resuelve aliases para comprobar tipos, pero no los reescribe para Node. El stub de `server-only` queda limitado al temporal creado por la prueba de contenido; `npm run build` sigue verificando la frontera real cliente/servidor.

```js
// frontend/tests/run-hub-tests.cjs
/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const ts = require('typescript');

const root = path.resolve(__dirname, '..');
const suites = {
  'content-sedes-indice': ['src/content/sedes-indice.ts', 'CONTENT_SEDES_INDICE_TEST_OUT'],
  'content-sedes-cuerpo': ['src/content/sedes-cuerpo.ts', 'CONTENT_SEDES_CUERPO_TEST_OUT'],
  'reconciliar-sedes': ['src/lib/reconciliar-sedes.ts', 'RECONCILIAR_TEST_OUT'],
  'booking-href': ['src/lib/booking-href.ts', 'BOOKING_HREF_TEST_OUT'],
  'selector-experiencia': ['src/lib/selector-experiencia.ts', 'SELECTOR_TEST_OUT'],
  personalizaciones: ['src/lib/pricing-paquete.ts', 'PERSONALIZACIONES_TEST_OUT'],
};
const chosen = process.argv.length > 2 ? process.argv.slice(2) : Object.keys(suites);
for (const name of chosen) {
  if (!Object.hasOwn(suites, name)) throw new Error('Suite desconocida: ' + name);
}
const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hub-multisede-tests-'));
const loaded = ts.readConfigFile(path.join(root, 'tsconfig.json'), ts.sys.readFile);
const formatHost = {
  getCanonicalFileName: (file) => file,
  getCurrentDirectory: () => root,
  getNewLine: () => '\n',
};
if (loaded.error) throw new Error(ts.formatDiagnostics([loaded.error], formatHost));
const config = ts.parseJsonConfigFileContent({
  ...loaded.config,
  files: chosen.map((name) => suites[name][0]),
  include: [],
  exclude: [],
}, ts.sys, root);
const options = {
  ...config.options,
  rootDir: path.join(root, 'src'), outDir,
  noEmit: false, noEmitOnError: true, incremental: false,
  tsBuildInfoFile: undefined,
  module: ts.ModuleKind.CommonJS,
  moduleResolution: ts.ModuleResolutionKind.Node10,
};
const program = ts.createProgram(config.fileNames, options);
const diagnostics = [...config.errors, ...ts.getPreEmitDiagnostics(program)];
if (diagnostics.length) {
  process.stderr.write(ts.formatDiagnostics(diagnostics, formatHost));
  process.exit(1);
}
const result = program.emit();
if (result.emitSkipped) {
  process.stderr.write(ts.formatDiagnostics(result.diagnostics, formatHost));
  process.exit(1);
}
const env = { ...process.env };
for (const name of chosen) {
  env[suites[name][1]] = name === 'personalizaciones' ? path.join(outDir, 'lib') : outDir;
}
const tests = chosen.map((name) => path.join(root, 'tests', name + '.test.cjs'));
const run = spawnSync(process.execPath, ['--test', ...tests], { cwd: root, env, stdio: 'inherit' });
if (run.error) throw run.error;
process.exitCode = run.status ?? 1;
```

Cada ejecución usa un temporal nuevo, sin depender de variables de una sesión previa. El runner no modifica fuentes ni crea stubs en `frontend/node_modules`. Se conservan temporales para diagnóstico. En las pruebas nuevas `.cjs`, usar el mismo encabezado ESLint de `personalizaciones.test.cjs`.

---
## Tareas

### Tarea 1: Contenido de sedes y preparación de pruebas

**Files:**
- Create: `frontend/tests/run-hub-tests.cjs` (preparación anterior)
- Create: `frontend/src/content/sedes-tipos.ts`
- Create: `frontend/src/content/sedes-indice.ts`
- Create: `frontend/src/content/sedes-cuerpo.ts`
- Test: `frontend/tests/content-sedes-indice.test.cjs`
- Test: `frontend/tests/content-sedes-cuerpo.test.cjs`

**Interfaces:**
- Produce (`sedes-tipos.ts`): `type SedeIndiceEntry`, `type SedeHeroContenido`, `type SedeNegocio`, `type SedeColaboracion`, `type SedeDestacada`, `type SedeOtraEmpresa`, `type SedeServicioTransporte`, `type SedeCuerpoContenido`, `type SedeContenido` (= `SedeIndiceEntry & SedeCuerpoContenido`, la forma combinada que usan las páginas).
- Produce (`sedes-indice.ts`, client-safe): `const SEDES_INDICE: Record<string, SedeIndiceEntry>`, `const SLUGS_CON_CONTENIDO: string[]`, `function getSedeIndice(slug: string): SedeIndiceEntry | undefined`.
- Produce (`sedes-cuerpo.ts`, `import 'server-only'`): `const SEDES_CUERPO: Record<string, Record<Locale, SedeCuerpoContenido>>`, `function getSedeCuerpo(slug: string, lang: Locale): SedeCuerpoContenido | undefined`, `function getSedeContenido(slug: string, lang: Locale): SedeContenido | undefined` (combina índice + cuerpo — la que usan las páginas de servidor).
- Consume: `sedes-indice.ts` y `sedes-cuerpo.ts` importan `type` de `sedes-tipos.ts`; `sedes-cuerpo.ts` además importa `type { Locale } from '@/app/[lang]/dictionaries'` (type-only) y ejecuta `import 'server-only'` (runtime, a propósito).

**Por qué el split:** un solo módulo (client-safe o no) mezclando `slug`/`nombre` con `colaboracion.texto1`/`texto2`/`otrasEmpresas[].descripcion` (prosa) e importado por `SiteHeader` (Client Component, 15 puntos de montaje) manda todo eso al bundle de cada página — los bundlers no tree-shakean propiedades de un objeto. `sedes-indice.ts` es deliberadamente diminuto (solo lo que `SiteHeader`/`SedeSelector` necesitan en cliente); `sedes-cuerpo.ts` lleva `import 'server-only'` para que un import accidental desde un Client Component rompa el build en vez de inflar el bundle en silencio.

- [x] **Step 1: Crear el runner y escribir los tests que fallan**

```js
// frontend/tests/content-sedes-indice.test.cjs
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const i = require(path.join(process.env.CONTENT_SEDES_INDICE_TEST_OUT, 'content/sedes-indice.js'));

test('la-paz y los-cabos existen en el indice con nombre y empresa fundadora', () => {
  const laPaz = i.getSedeIndice('la-paz');
  const losCabos = i.getSedeIndice('los-cabos');
  assert.ok(laPaz);
  assert.ok(losCabos);
  assert.equal(laPaz.nombre, 'La Paz');
  assert.equal(laPaz.empresaFundadoraNombre, 'Sal y Sol Sportfishing');
  assert.equal(losCabos.empresaFundadoraNombre, 'Tours Cabo');
});

test('slug inexistente devuelve undefined', () => {
  assert.equal(i.getSedeIndice('cancun'), undefined);
  assert.equal(i.getSedeIndice('__proto__'), undefined);
  assert.equal(i.getSedeIndice('constructor'), undefined);
});

test('SLUGS_CON_CONTENIDO trae exactamente la-paz y los-cabos', () => {
  assert.deepEqual([...i.SLUGS_CON_CONTENIDO].sort(), ['la-paz', 'los-cabos']);
});

test('el logo de la-paz apunta al logo real; los-cabos usa null (wordmark generico)', () => {
  assert.equal(i.getSedeIndice('la-paz').logo, '/logos/logo2salysol.webp');
  assert.equal(i.getSedeIndice('los-cabos').logo, null);
});
```

```js
// frontend/tests/content-sedes-cuerpo.test.cjs
/* eslint-disable @typescript-eslint/no-require-imports */
//
// `sedes-cuerpo.ts` hace `import 'server-only'` a proposito (ver Step 1 de
// mas abajo): ese paquete no existe fuera del bundler de Next (no esta en
// package.json — Next lo resuelve con un alias interno), asi que un
// `require` directo del compilado revienta con "Cannot find module
// 'server-only'" en un `node --test` normal. Se stubea localmente, solo
// para este proceso de test: node busca `node_modules/server-only` subiendo
// directorios desde el archivo que hace el require, asi que un stub en la
// raiz del outDir compilado (un nivel arriba de `content/`) resuelve antes
// de tocar el paquete real.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

const outDir = process.env.CONTENT_SEDES_CUERPO_TEST_OUT;
const stubDir = path.join(outDir, 'node_modules', 'server-only');
fs.mkdirSync(stubDir, { recursive: true });
fs.writeFileSync(path.join(stubDir, 'package.json'), JSON.stringify({ name: 'server-only', main: 'index.js' }));
fs.writeFileSync(path.join(stubDir, 'index.js'), 'module.exports = {};');

const c = require(path.join(outDir, 'content/sedes-cuerpo.js'));

test('la-paz existe en los dos idiomas con hero y negocio no nulos', () => {
  const es = c.getSedeContenido('la-paz', 'es');
  const en = c.getSedeContenido('la-paz', 'en');
  assert.ok(es);
  assert.ok(en);
  assert.equal(es.slug, 'la-paz');
  assert.equal(es.nombre, 'La Paz');
  assert.equal(es.negocio.ciudad, 'La Paz');
  assert.equal(es.hero.video, '/videos/videohero.webm');
  assert.notEqual(es.hero.titulo.start, en.hero.titulo.start);
});

test('los-cabos existe con negocio null (temporada/incluye no viven aqui, viven en el dict global)', () => {
  const es = c.getSedeContenido('los-cabos', 'es');
  assert.ok(es);
  assert.equal(es.negocio, null);
  assert.equal(es.hero.video, null);
  assert.ok(es.hero.imagen);
  assert.deepEqual(es.hero.facts, []);
});

test('slug inexistente devuelve undefined', () => {
  assert.equal(c.getSedeContenido('cancun', 'es'), undefined);
  assert.equal(c.getSedeContenido('__proto__', 'es'), undefined);
});

test('cada destacada inlineable de la-paz apunta al flujo de pesca legacy', () => {
  const es = c.getSedeContenido('la-paz', 'es');
  const inlineables = es.destacadas.filter((d) => d.inlineable);
  assert.equal(inlineables.length, 1);
  assert.equal(inlineables[0].tipo, 'servicio');
  assert.equal(inlineables[0].slug, 'pesca-deportiva');
});

test('getSedeCuerpo no trae slug/nombre/logo del indice (solo el cuerpo crudo)', () => {
  const cuerpo = c.getSedeCuerpo('la-paz', 'es');
  assert.ok(cuerpo);
  assert.equal(cuerpo.nombre, undefined);
  assert.equal(cuerpo.logo, undefined);
  assert.equal(cuerpo.empresaFundadoraSlug, 'sal-y-sol');
});
```

- [x] **Step 2: Correr los tests y comprobar que fallan**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs content-sedes-indice content-sedes-cuerpo
```
Expected: FAIL — `Cannot find module '.../content/sedes-indice.js'` y `'.../content/sedes-cuerpo.js'` (los archivos fuente todavía no existen).

- [x] **Step 3: Escribir `content/sedes-tipos.ts`**

```ts
// frontend/src/content/sedes-tipos.ts
//
// Solo tipos: sin runtime, sin valores exportados. Un `import type` de este
// archivo se borra por completo en compilacion, asi que es seguro importarlo
// desde cualquier lado (Client o Server Component) sin costo de bundle.
import type { Locale } from '@/app/[lang]/dictionaries';

export type { Locale };

/** Lo minimo que un Client Component necesita para resolver marca/logo por sede. */
export type SedeIndiceEntry = {
  slug: string;
  nombre: string;
  empresaFundadoraNombre: string;
  /** Ruta del logo de la empresa fundadora, o `null` para el wordmark generico de agencia. */
  logo: string | null;
};

export type SedeHeroContenido = {
  video: string | null;
  imagen: string | null;
  titulo: { start: string; emphasis: string; end: string };
  subtitulo: string;
  facts: { value: string; label: string }[];
};

export type SedeNegocio = {
  nombre: string;
  calle: string;
  ciudad: string;
  estado: string;
  pais: string;
  horarioApertura: string;
  horarioCierre: string;
} | null;

export type SedeColaboracion = {
  titulo: string;
  texto1: string;
  texto2: string;
  imagenSrc: string;
  imagenAlt: string;
};

export type SedeDestacada = {
  tipo: 'servicio' | 'paquete';
  slug: string;
  empresaSlug?: string;
  inlineable: boolean;
};

export type SedeOtraEmpresa = {
  slug: string;
  nombre: string;
  descripcion: string;
  enlaceExterno: string;
};

export type SedeServicioTransporte = {
  empresaSlug: string;
  hrefTraslados: string;
} | null;

/** Contenido largo/pesado por sede — vive en `sedes-cuerpo.ts` (server-only). */
export type SedeCuerpoContenido = {
  slug: string;
  empresaFundadoraSlug: string;
  negocio: SedeNegocio;
  metaTitle: string;
  metaDescription: string;
  hero: SedeHeroContenido;
  colaboracion: SedeColaboracion;
  destacadas: SedeDestacada[];
  otrasEmpresas: SedeOtraEmpresa[];
  servicioTransporte: SedeServicioTransporte;
};

/**
 * Forma combinada (indice + cuerpo) que usan las paginas de servidor. Solo
 * existe como tipo — el valor lo arma `getSedeContenido()` en
 * `sedes-cuerpo.ts` (server-only), nunca se construye desde un Client
 * Component.
 */
export type SedeContenido = SedeIndiceEntry & SedeCuerpoContenido;
```

- [x] **Step 4: Escribir `content/sedes-indice.ts` (client-safe)**

```ts
// frontend/src/content/sedes-indice.ts
//
// Client-safe de verdad: SiteHeader (Client Component, montado en cada
// pagina) importa esto para resolver marca/logo cuando no hay slug de sede
// en la URL. El contenido largo (hero completo, colaboracion, otras
// empresas, negocio) vive en `sedes-cuerpo.ts` (server-only) para que nunca
// termine en el bundle de cliente.
import type { SedeIndiceEntry } from './sedes-tipos';

export const SEDES_INDICE: Record<string, SedeIndiceEntry> = {
  'la-paz': {
    slug: 'la-paz',
    nombre: 'La Paz',
    empresaFundadoraNombre: 'Sal y Sol Sportfishing',
    logo: '/logos/logo2salysol.webp',
  },
  'los-cabos': {
    slug: 'los-cabos',
    nombre: 'Los Cabos',
    empresaFundadoraNombre: 'Tours Cabo',
    logo: null,
  },
};

export const SLUGS_CON_CONTENIDO: string[] = Object.keys(SEDES_INDICE);

export function getSedeIndice(slug: string): SedeIndiceEntry | undefined {
  return Object.hasOwn(SEDES_INDICE, slug) ? SEDES_INDICE[slug] : undefined;
}
```

- [x] **Step 5: Escribir `content/sedes-cuerpo.ts` (server-only)**

```ts
// frontend/src/content/sedes-cuerpo.ts
import 'server-only';
import type { Locale } from '@/app/[lang]/dictionaries';
import { SEDES_INDICE } from './sedes-indice';
import type { SedeCuerpoContenido, SedeContenido } from './sedes-tipos';

/**
 * Contenido largo por sede, bilingue. `server-only`: si algun componente
 * cliente lo importa por error, el build falla en vez de mandar estos
 * parrafos al bundle de cliente sin que nadie los necesite ahi.
 */
export const SEDES_CUERPO: Record<string, Record<Locale, SedeCuerpoContenido>> = {
  'la-paz': {
    es: {
      slug: 'la-paz',
      empresaFundadoraSlug: 'sal-y-sol',
      negocio: {
        nombre: 'Sal y Sol Sportfishing',
        calle: 'Marina La Costa, Rangel y Navarro',
        ciudad: 'La Paz',
        estado: 'Baja California Sur',
        pais: 'MX',
        horarioApertura: '05:00',
        horarioCierre: '07:00',
      },
      metaTitle: 'Tours de pesca deportiva en La Paz, BCS | Sal y Sol Sportfishing',
      metaDescription:
        'Vive la mejor experiencia de pesca deportiva en La Paz, BCS con capitanes locales. Salidas privadas desde Marina La Costa. Reserva en línea o escríbenos por WhatsApp.',
      hero: {
        video: '/videos/videohero.webm',
        imagen: '/photos/cola-amarilla-acantilado.webp',
        titulo: { start: 'Ven a pescar', emphasis: 'con nosotros', end: 'a la Bahía de La Paz' },
        subtitulo:
          'Somos una agencia local de La Paz con capitanes que conocen estas aguas como nadie. Salimos todos los días de Marina La Costa para darte la mejor experiencia de pesca en BCS.',
        facts: [
          { value: '6 a 8 horas', label: 'Duración de la aventura' },
          { value: '5:00 a 7:00 am', label: 'Horario flexible a tu gusto' },
          { value: 'Hasta 5 personas', label: 'Ambiente privado y familiar' },
          { value: '365 días al año', label: 'Salidas disponibles todo el año' },
        ],
      },
      colaboracion: {
        titulo: 'Tu agencia local de confianza: apasionados por el mar y por tu experiencia',
        texto1:
          'Somos una agencia de pesca deportiva conformada por gente local que conoce, respeta y ama profundamente las aguas de La Paz. Nos preocupamos por cada detalle de tu viaje para que tú y tu grupo disfruten de una jornada extraordinaria, sintiéndose en confianza y con la calidez que nos distingue.',
        texto2:
          'Cada tour es 100% privado y pensado a la medida de tu grupo. Si es tu primera vez en la pesca deportiva, nuestros capitanes te enseñarán con paciencia y gusto las mejores técnicas, y si ya eres un pescador experimentado, te llevaremos a los mejores puntos de la bahía para maximizar tus capturas.',
        imagenSrc: '/photos/capitan-cabrilla-bahia.webp',
        imagenAlt: 'Capitán local sonriendo con una cabrilla recién pescada, con La Paz al fondo',
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: [],
      servicioTransporte: {
        empresaSlug: 'transporte-la-paz',
        hrefTraslados: '/traslados?empresa=transporte-la-paz',
      },
    },
    en: {
      slug: 'la-paz',
      empresaFundadoraSlug: 'sal-y-sol',
      negocio: {
        nombre: 'Sal y Sol Sportfishing',
        calle: 'Marina La Costa, Rangel y Navarro',
        ciudad: 'La Paz',
        estado: 'Baja California Sur',
        pais: 'MX',
        horarioApertura: '05:00',
        horarioCierre: '07:00',
      },
      metaTitle: 'Sportfishing Charters in La Paz, BCS | Sal y Sol Sportfishing',
      metaDescription:
        'Experience the best sportfishing in La Paz, BCS with passionate local captains. Private charters from Marina La Costa. Book online or message us on WhatsApp.',
      hero: {
        video: '/videos/videohero.webm',
        imagen: '/photos/cola-amarilla-acantilado.webp',
        titulo: { start: 'Come fishing', emphasis: 'with us', end: 'in the Bay of La Paz' },
        subtitulo:
          'We are a local La Paz agency with captains who know these waters like no one else. We sail every day from Marina La Costa to bring you the best fishing experience in BCS.',
        facts: [
          { value: '6 to 8 hours', label: 'Adventure duration' },
          { value: '5:00 to 7:00 am', label: 'Flexible departure of your choice' },
          { value: 'Up to 5 guests', label: 'Private & family-friendly' },
          { value: '365 days a year', label: 'Departures available all year' },
        ],
      },
      colaboracion: {
        titulo: 'Your trusted local agency: passionate about the sea and your experience',
        texto1:
          'We are a local sportfishing agency based in La Paz, run by local experts who deeply know, respect, and love these waters. We take care of every detail of your charter so that you and your party feel welcomed, supported, and free to enjoy an extraordinary day out on the sea.',
        texto2:
          'Every trip is 100% private and tailored to your group. Whether you are holding a fishing rod for the very first time or are a seasoned angler, our friendly captains will guide you with patience, warmth, and skill, taking you to the most productive spots in the bay for an unforgettable adventure.',
        imagenSrc: '/photos/capitan-cabrilla-bahia.webp',
        imagenAlt: 'Smiling local captain holding a fresh catch, with La Paz in the background',
      },
      destacadas: [
        { tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true },
      ],
      otrasEmpresas: [],
      servicioTransporte: {
        empresaSlug: 'transporte-la-paz',
        hrefTraslados: '/traslados?empresa=transporte-la-paz',
      },
    },
  },
  'los-cabos': {
    es: {
      slug: 'los-cabos',
      empresaFundadoraSlug: 'tours-cabo',
      negocio: null,
      metaTitle: 'Experiencias en Los Cabos, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Descubre las experiencias de Tours Cabo en Los Cabos, aliado de Sal y Sol Baja Experiences.',
      hero: {
        video: null,
        imagen: '/ilustraciones/los-cabos-placeholder.webp',
        titulo: { start: 'Descubre', emphasis: 'Los Cabos', end: 'con Tours Cabo' },
        subtitulo:
          'Tours Cabo es nuestro aliado local en Los Cabos. Estamos completando el contenido de esta sede — mientras tanto, escríbenos y te ayudamos igual.',
        facts: [],
      },
      colaboracion: {
        titulo: 'Una alianza en construcción',
        texto1:
          'Estamos formalizando el contenido de esta colaboración con Tours Cabo, nuestro aliado en Los Cabos.',
        texto2:
          'Pronto podrás conocer aquí la historia completa de esta alianza, sus experiencias y su equipo.',
        imagenSrc: '/ilustraciones/los-cabos-placeholder.webp',
        imagenAlt: 'Ilustración genérica de costa; imagen provisional de Los Cabos',
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
    en: {
      slug: 'los-cabos',
      empresaFundadoraSlug: 'tours-cabo',
      negocio: null,
      metaTitle: 'Experiences in Los Cabos, BCS | Sal y Sol Baja Experiences',
      metaDescription:
        'Discover Tours Cabo experiences in Los Cabos, a Sal y Sol Baja Experiences partner.',
      hero: {
        video: null,
        imagen: '/ilustraciones/los-cabos-placeholder.webp',
        titulo: { start: 'Discover', emphasis: 'Los Cabos', end: 'with Tours Cabo' },
        subtitulo:
          "Tours Cabo is our local partner in Los Cabos. We're still completing this destination's content — message us in the meantime and we'll help all the same.",
        facts: [],
      },
      colaboracion: {
        titulo: 'A partnership in progress',
        texto1: "We're finalizing the content for this collaboration with Tours Cabo, our partner in Los Cabos.",
        texto2: "Soon you'll be able to read the full story of this partnership, its experiences, and its team here.",
        imagenSrc: '/ilustraciones/los-cabos-placeholder.webp',
        imagenAlt: 'Generic coastal illustration; provisional Los Cabos image',
      },
      destacadas: [],
      otrasEmpresas: [],
      servicioTransporte: null,
    },
  },
};

export function getSedeCuerpo(slug: string, lang: Locale): SedeCuerpoContenido | undefined {
  return SEDES_CUERPO[slug]?.[lang];
}

/** Combina indice + cuerpo. La forma completa que consumen las paginas de servidor. */
export function getSedeContenido(slug: string, lang: Locale): SedeContenido | undefined {
  const indice = Object.hasOwn(SEDES_INDICE, slug) ? SEDES_INDICE[slug] : undefined;
  const cuerpo = SEDES_CUERPO[slug]?.[lang];
  if (!indice || !cuerpo) return undefined;
  return { ...indice, ...cuerpo };
}
```

- [x] **Step 6: Compilar el índice y correr su test**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs content-sedes-indice
```
Expected: PASS (4 tests).

- [x] **Step 7: Compilar el cuerpo y correr su test (con el stub de `server-only`)**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs content-sedes-cuerpo
```
Expected: PASS (5 tests). El stub de `server-only` lo crea el propio test (Step 1) antes del `require`.

- [x] **Step 8: Verificación de tipos del proyecto**

Run: `cd frontend && npx tsc --noEmit`
Expected: sin errores (archivos nuevos, sin callers todavía).

- [x] **Step 9: Commit**

```bash
git add frontend/tests/run-hub-tests.cjs frontend/src/content/sedes-tipos.ts frontend/src/content/sedes-indice.ts frontend/src/content/sedes-cuerpo.ts frontend/tests/content-sedes-indice.test.cjs frontend/tests/content-sedes-cuerpo.test.cjs
git commit -m "feat(frontend): contenido por-sede partido en tipos/indice client-safe/cuerpo server-only"
```

---

### Tarea 2: Sedes activas y timeout de consulta

**Files:**
- Create: `frontend/src/lib/reconciliar-sedes.ts`
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/tests/reconciliar-sedes.test.cjs`

**Interfaces:**
- Consume: `type SedeIndiceEntry` de `@/content/sedes-tipos` (Tarea 1, type-only).
- Produce: `function sedesActivas(indice: Record<string, SedeIndiceEntry>, sedesApi: {slug: string}[] | null): SedeIndiceEntry[]` — pura, sin fetch propio, sin `lang` (el índice no varía por idioma).

- [x] **Step 1: Escribir el test que falla**

```js
// frontend/tests/reconciliar-sedes.test.cjs
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const r = require(path.join(process.env.RECONCILIAR_TEST_OUT, 'lib/reconciliar-sedes.js'));

const indice = {
  'la-paz': { slug: 'la-paz', nombre: 'La Paz', empresaFundadoraNombre: 'Sal y Sol Sportfishing', logo: '/logos/logo2salysol.webp' },
  'los-cabos': { slug: 'los-cabos', nombre: 'Los Cabos', empresaFundadoraNombre: 'Tours Cabo', logo: null },
};

test('interseccion normal: solo los slugs que la API confirma activos', () => {
  const resultado = r.sedesActivas(indice, [{ slug: 'la-paz' }]);
  assert.deepEqual(resultado.map((s) => s.slug), ['la-paz']);
});

test('la API no trae una sede del indice: esa sede desaparece', () => {
  const resultado = r.sedesActivas(indice, [{ slug: 'la-paz' }, { slug: 'cancun' }]);
  assert.deepEqual(resultado.map((s) => s.slug), ['la-paz']);
});

test('fallo abierto: sedesApi null muestra TODO el indice sin filtrar', () => {
  const resultado = r.sedesActivas(indice, null);
  assert.deepEqual(resultado.map((s) => s.slug).sort(), ['la-paz', 'los-cabos']);
});

test('array vacio de la API (sin fallo, pero sin sedes activas): no muestra ninguna', () => {
  const resultado = r.sedesActivas(indice, []);
  assert.deepEqual(resultado, []);
});

test('devuelve entradas del indice, no las reconstruye', () => {
  const resultado = r.sedesActivas(indice, [{ slug: 'la-paz' }]);
  assert.equal(resultado[0].empresaFundadoraNombre, 'Sal y Sol Sportfishing');
  assert.equal(resultado[0].logo, '/logos/logo2salysol.webp');
});
```

- [x] **Step 2: Correr el test y comprobar que falla**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs reconciliar-sedes
```
Expected: FAIL — módulo no existe.

- [x] **Step 3: Implementar `reconciliar-sedes.ts`**

```ts
// frontend/src/lib/reconciliar-sedes.ts
import type { SedeIndiceEntry } from '@/content/sedes-tipos';

/**
 * Intersección índice × API (spec §4, "regla de reconciliación"). Pura: no
 * hace fetch, recibe `sedesApi` ya resuelto por el caller (`getSedes()`
 * consumido afuera). `sedesApi === null` significa que `getSedes()` falló
 * (rechazo de red O timeout — ver Step 4 más abajo): se falla abierto y se
 * devuelven todas las sedes del índice sin filtrar, nunca una lista vacía
 * por un error de red. Opera solo sobre `SedeIndiceEntry` (client-safe) — el
 * contenido largo por sede vive en `content/sedes-cuerpo.ts` (server-only) y
 * nunca pasa por esta función.
 */
export function sedesActivas(
  indice: Record<string, SedeIndiceEntry>,
  sedesApi: { slug: string }[] | null,
): SedeIndiceEntry[] {
  const slugs = Object.keys(indice);
  const slugsAMostrar =
    sedesApi === null ? slugs : slugs.filter((slug) => sedesApi.some((s) => s.slug === slug));

  return slugsAMostrar.map((slug) => indice[slug]);
}
```

- [x] **Step 4: `api.ts` — timeout únicamente en `getSedes()`**

El descubrimiento de sedes requiere un límite de espera, pero cambiar `request()` globalmente alteraría también reservas/pagos. Mantener `request()` intacto y reemplazar solo `getSedes()`:

```ts
export const getSedes = () =>
  request<Sede[]>('/api/sedes/', { signal: AbortSignal.timeout(8000) });
```

El rechazo por timeout sigue el `catch` existente de `request()` y los callers lo convierten a `null`. Una respuesta válida `[]` permanece vacía: no es un error de red. Comprobar en el diff que ningún otro endpoint gana este timeout. El `AbortSignal.timeout` aborta con razón `TimeoutError`; no depender del nombre `AbortError` para activar el fallback.

- [x] **Step 5: Compilar y correr el test**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs reconciliar-sedes
```
Expected: PASS (5 tests).

- [x] **Step 6: `npx tsc --noEmit` desde `frontend/`**

Expected: sin errores.

- [x] **Step 7: Commit**

```bash
git add frontend/src/lib/reconciliar-sedes.ts frontend/src/lib/api.ts frontend/tests/reconciliar-sedes.test.cjs
git commit -m "feat(frontend): reconciliar sedes sobre el indice (puro) + timeout en getSedes()"
```

---

### Tarea 3: URLs de reserva compartidas y adopción en tarjetas

#### A. Helper `booking-href.ts`

**Files:**
- Create: `frontend/src/lib/booking-href.ts`
- Test: `frontend/tests/booking-href.test.cjs`

**Interfaces:**
- Consume: `esPaqueteCruzaEmpresa` de `@/lib/pricing-paquete` (ya existe); `type Moneda, PaqueteCatalogo, ServicioCatalogo` de `@/lib/api`; `type Locale` de `dictionaries`.
- Produce: `function hrefPaquete(paquete: PaqueteCatalogo, lang: Locale, moneda: Moneda): string`, `function hrefServicio(servicio: ServicioCatalogo, lang: Locale, moneda: Moneda): string`.

- [x] **Step 1: Escribir el test que falla**

```js
// frontend/tests/booking-href.test.cjs
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const h = require(path.join(process.env.BOOKING_HREF_TEST_OUT, 'lib/booking-href.js'));

function paqueteBase(overrides = {}) {
  return {
    id: 1, sede: 'La Paz', sede_slug: 'la-paz',
    empresa_lider: 'Sal y Sol', empresa_lider_slug: 'sal-y-sol',
    nombre: 'Brunch y pesca', slug: 'brunch-y-pesca', descripcion: '',
    precio_ancla: '3000', precio_ancla_usd: null, regla_precio: 'fijo', activo: true,
    servicios_asociados: [
      { id: 1, servicio_id: 1, orden: 1, servicio: { id: 1, empresa_slug: 'sal-y-sol', nombre: 'Pesca', slug: 'pesca-deportiva', tipo_servicio: 'pesca', estrategia_cupo: 'x', estrategia_precio: 'x', modo_ocupacion: 'x', precio_base: '0', precio_base_usd: null, precio_persona_extra: '0', precio_persona_extra_usd: null, personas_incluidas: 1, descripcion: '', activo: true, personalizaciones: [] } },
    ],
    ...overrides,
  };
}

test('paquete mono-empresa va a /reservar con paquete_empresa', () => {
  const href = h.hrefPaquete(paqueteBase(), 'es', 'MXN');
  assert.equal(href, '/es/reservar?paquete=brunch-y-pesca&sede=la-paz&paquete_empresa=sal-y-sol&moneda=MXN');
});

test('paquete cruza-empresa va a /reservar-paquete sin paquete_empresa', () => {
  const cruza = paqueteBase({
    servicios_asociados: [
      { id: 1, servicio_id: 1, orden: 1, servicio: { ...paqueteBase().servicios_asociados[0].servicio, empresa_slug: 'sal-y-sol' } },
      { id: 2, servicio_id: 2, orden: 2, servicio: { ...paqueteBase().servicios_asociados[0].servicio, id: 2, empresa_slug: 'transporte-la-paz' } },
    ],
  });
  const href = h.hrefPaquete(cruza, 'es', 'MXN');
  assert.equal(href, '/es/reservar-paquete?paquete=brunch-y-pesca&sede=la-paz&moneda=MXN');
});

test('paquete sin sede_slug omite el parametro sede', () => {
  const href = h.hrefPaquete(paqueteBase({ sede_slug: '' }), 'en', 'USD');
  assert.equal(href, '/en/reservar?paquete=brunch-y-pesca&paquete_empresa=sal-y-sol&moneda=USD');
});

test('hrefServicio arma la URL de reserva de servicio suelto', () => {
  const servicio = {
    id: 5, empresa_slug: 'sal-y-sol', nombre: 'Pesca', slug: 'pesca-deportiva',
    tipo_servicio: 'pesca', estrategia_cupo: 'x', estrategia_precio: 'x', modo_ocupacion: 'x',
    precio_base: '0', precio_base_usd: null, precio_persona_extra: '0', precio_persona_extra_usd: null,
    personas_incluidas: 1, descripcion: '', activo: true, personalizaciones: [],
  };
  const href = h.hrefServicio(servicio, 'es', 'MXN');
  assert.equal(href, '/es/reservar?servicio=pesca-deportiva&empresa=sal-y-sol&moneda=MXN');
});
```

- [x] **Step 2: Correr el test y comprobar que falla**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs booking-href
```
Expected: FAIL — módulo no existe.

- [x] **Step 3: Implementar (idéntico cálculo a `paquete-card.tsx`/`servicios-sueltos-section.tsx` de hoy)**

```ts
// frontend/src/lib/booking-href.ts
import type { Locale } from '@/app/[lang]/dictionaries';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { esPaqueteCruzaEmpresa } from './pricing-paquete';

export function hrefPaquete(paquete: PaqueteCatalogo, lang: Locale, moneda: Moneda): string {
  const sedeParam = paquete.sede_slug ? `&sede=${paquete.sede_slug}` : '';
  const empresaParam = paquete.empresa_lider_slug
    ? `&paquete_empresa=${paquete.empresa_lider_slug}`
    : '';
  const cruzaEmpresa = esPaqueteCruzaEmpresa(paquete);
  return cruzaEmpresa
    ? `/${lang}/reservar-paquete?paquete=${paquete.slug}${sedeParam}&moneda=${moneda}`
    : `/${lang}/reservar?paquete=${paquete.slug}${sedeParam}${empresaParam}&moneda=${moneda}`;
}

export function hrefServicio(servicio: ServicioCatalogo, lang: Locale, moneda: Moneda): string {
  return `/${lang}/reservar?servicio=${servicio.slug}&empresa=${servicio.empresa_slug}&moneda=${moneda}`;
}
```

- [x] **Step 4: Compilar y correr el test**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs booking-href
```
Expected: PASS (4 tests).

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores (archivo nuevo, sin callers todavía).

#### B. Adoptar `booking-href.ts` en `PaqueteCard`/`ServiciosSueltosSection`

**Files:**
- Modify: `frontend/src/components/paquete-card.tsx`
- Modify: `frontend/src/components/servicios-sueltos-section.tsx`

**Interfaces:**
- Consume: `hrefPaquete`, `hrefServicio` de `@/lib/booking-href` (Tarea 3).

- [x] **Step 5: `paquete-card.tsx` — reemplazar el cálculo inline**

Reemplazar (líneas 37-46 de hoy):
```ts
  // URL para continuar hacia el checkout con este paquete. Los paquetes
  // cruza-empresa (componentes de mas de una Empresa, ej. pesca + traslado)
  // van al checkout de orden: el de reserva sencilla solo cobra a una
  // Empresa a la vez.
  const sedeParam = paquete.sede_slug ? `&sede=${paquete.sede_slug}` : '';
  const empresaParam = paquete.empresa_lider_slug ? `&paquete_empresa=${paquete.empresa_lider_slug}` : '';
  const cruzaEmpresa = esPaqueteCruzaEmpresa(paquete);
  const bookingHref = cruzaEmpresa
    ? `/${lang}/reservar-paquete?paquete=${paquete.slug}${sedeParam}&moneda=${moneda}`
    : `/${lang}/reservar?paquete=${paquete.slug}${sedeParam}${empresaParam}&moneda=${moneda}`;
```
por:
```ts
  const bookingHref = hrefPaquete(paquete, lang, moneda);
```
y el import:
```ts
import { calcularPrecioPaquete, formatearPrecio } from '@/lib/pricing-paquete';
import { hrefPaquete } from '@/lib/booking-href';
```
(`esPaqueteCruzaEmpresa` deja de importarse en este archivo — ya no se usa aquí directamente, vive dentro de `hrefPaquete`).

- [x] **Step 6: `servicios-sueltos-section.tsx` — reemplazar el `href` inline**

Reemplazar:
```tsx
                <Link
                  href={`/${lang}/reservar?servicio=${servicio.slug}&empresa=${servicio.empresa_slug}&moneda=${moneda}`}
```
por:
```tsx
                <Link
                  href={hrefServicio(servicio, lang, moneda)}
```
y agregar el import:
```ts
import { hrefServicio } from '@/lib/booking-href';
```

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores. Los dos componentes producen exactamente las mismas URLs que antes (mismo cálculo, ahora centralizado) — lo cubren los tests de la Tarea 3.

#### Cierre de la tarea

- [x] **Step 7: Verificación conjunta de la tarea**

Con todos los bloques anteriores integrados, ejecutar desde `frontend/` `npx tsc --noEmit` y ESLint sobre los archivos modificados de esta tarea. Aplicar los criterios descritos en cada bloque; no repetir tipos/lint tras cada cambio mecánico. Conservar las ejecuciones de pruebas en rojo/verde indicadas para la lógica pura. No avanzar si hay errores nuevos.

- [x] **Step 8: Commit de la tarea completa**

```bash
git add frontend/src/lib/booking-href.ts frontend/tests/booking-href.test.cjs frontend/src/components/paquete-card.tsx frontend/src/components/servicios-sueltos-section.tsx
git commit -m "refactor(frontend): centralizar URLs de reserva"
```

---

### Tarea 4: Selector de experiencias: lógica y componente

#### A. Lógica del selector de experiencia (`selector-experiencia.ts`)

**Files:**
- Create: `frontend/src/lib/selector-experiencia.ts`
- Test: `frontend/tests/selector-experiencia.test.cjs`

**Interfaces:**
- Consume: `type SedeDestacada` de `@/content/sedes-tipos` (Tarea 1, type-only); `type PaqueteCatalogo, ServicioCatalogo` de `@/lib/api`.
- Produce: `type ChipExperiencia = { tipo: 'servicio' | 'paquete'; slug: string; nombre: string; empresaSlug: string | null }`, `function resolverChips(destacadas: SedeDestacada[], paquetes: PaqueteCatalogo[], servicios: ServicioCatalogo[]): ChipExperiencia[]`, `function esInlineable(chip: ChipExperiencia, sedeSlug: string, empresaSlugPescaLegacy: string): boolean`.

- [x] **Step 1: Escribir el test que falla**

```js
// frontend/tests/selector-experiencia.test.cjs
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const s = require(path.join(process.env.SELECTOR_TEST_OUT, 'lib/selector-experiencia.js'));

const servicioPesca = { id: 1, empresa_slug: 'sal-y-sol', nombre: 'Pesca deportiva', slug: 'pesca-deportiva', tipo_servicio: 'pesca', estrategia_cupo: 'x', estrategia_precio: 'x', modo_ocupacion: 'x', precio_base: '0', precio_base_usd: null, precio_persona_extra: '0', precio_persona_extra_usd: null, personas_incluidas: 1, descripcion: '', activo: true, personalizaciones: [] };
const paqueteBrunch = { id: 2, sede: 'La Paz', sede_slug: 'la-paz', empresa_lider: 'Sal y Sol', empresa_lider_slug: 'sal-y-sol', nombre: 'Brunch y pesca', slug: 'brunch-y-pesca', descripcion: '', precio_ancla: '1', precio_ancla_usd: null, regla_precio: 'fijo', activo: true, servicios_asociados: [] };

test('resuelve el nombre desde el catalogo real, no desde el diccionario', () => {
  const destacadas = [{ tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true }];
  const chips = s.resolverChips(destacadas, [], [servicioPesca]);
  assert.equal(chips.length, 1);
  assert.equal(chips[0].nombre, 'Pesca deportiva');
});

test('entrada de destacadas sin contraparte en el catalogo se omite en silencio', () => {
  const destacadas = [{ tipo: 'servicio', slug: 'buceo', inlineable: false }];
  const chips = s.resolverChips(destacadas, [], [servicioPesca]);
  assert.deepEqual(chips, []);
});

test('servicio destacado respeta empresaSlug cuando dos empresas comparten slug', () => {
  const otraEmpresa = { ...servicioPesca, id: 8, empresa_slug: 'otro-operador', nombre: 'Pesca de otro operador' };
  const destacadas = [{ tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true }];
  const chips = s.resolverChips(destacadas, [], [otraEmpresa, servicioPesca]);
  assert.equal(chips.length, 1);
  assert.equal(chips[0].empresaSlug, 'sal-y-sol');
  assert.equal(chips[0].nombre, servicioPesca.nombre);
  assert.deepEqual(s.resolverChips(destacadas, [], [otraEmpresa]), []);
});

test('paquete destacado no lleva empresaSlug (no aplica la regla mecanica)', () => {
  const destacadas = [{ tipo: 'paquete', slug: 'brunch-y-pesca', inlineable: false }];
  const chips = s.resolverChips(destacadas, [paqueteBrunch], []);
  assert.equal(chips[0].empresaSlug, null);
});

test('regla mecanica: inline solo si sede=la-paz + servicio pesca-deportiva + empresa del .env', () => {
  const chip = { tipo: 'servicio', slug: 'pesca-deportiva', nombre: 'Pesca', empresaSlug: 'sal-y-sol' };
  assert.equal(s.esInlineable(chip, 'la-paz', 'sal-y-sol'), true);
  assert.equal(s.esInlineable(chip, 'los-cabos', 'sal-y-sol'), false, 'otra sede');
  assert.equal(s.esInlineable({ ...chip, slug: 'buceo' }, 'la-paz', 'sal-y-sol'), false, 'otro servicio');
  assert.equal(s.esInlineable({ ...chip, tipo: 'paquete' }, 'la-paz', 'sal-y-sol'), false, 'es paquete, no servicio');
  assert.equal(s.esInlineable({ ...chip, empresaSlug: 'otra-empresa' }, 'la-paz', 'sal-y-sol'), false, 'otra empresa');
});

test('inlineable: true del diccionario no basta si la condicion mecanica no se cumple', () => {
  // Simula el caso que el spec §7 quiere evitar: alguien marca inlineable:true
  // en el diccionario para un chip que no es el flujo heredado de pesca.
  const chipMalMarcado = { tipo: 'servicio', slug: 'buceo', nombre: 'Buceo', empresaSlug: 'sal-y-sol' };
  assert.equal(s.esInlineable(chipMalMarcado, 'la-paz', 'sal-y-sol'), false);
});
```

- [x] **Step 2: Correr el test y comprobar que falla**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs selector-experiencia
```
Expected: FAIL — módulo no existe.

- [x] **Step 3: Implementar**

```ts
// frontend/src/lib/selector-experiencia.ts
import type { SedeDestacada } from '@/content/sedes-tipos';
import type { PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';

export type ChipExperiencia = {
  tipo: 'servicio' | 'paquete';
  slug: string;
  nombre: string;
  empresaSlug: string | null;
};

/**
 * Cruza `destacadas` (editorial, spec §4) contra el catálogo real de la sede.
 * El nombre del chip sale del catálogo, no del diccionario (que no lo
 * tiene). Una entrada sin contraparte en el catálogo (producto renombrado o
 * desactivado) se omite en silencio: menos chips, no una página rota.
 */
export function resolverChips(
  destacadas: SedeDestacada[],
  paquetes: PaqueteCatalogo[],
  servicios: ServicioCatalogo[],
): ChipExperiencia[] {
  const chips: ChipExperiencia[] = [];
  for (const d of destacadas) {
    if (d.tipo === 'servicio') {
      const match = servicios.find((s) =>
        s.slug === d.slug && (d.empresaSlug === undefined || s.empresa_slug === d.empresaSlug),
      );
      if (match) chips.push({ tipo: 'servicio', slug: match.slug, nombre: match.nombre, empresaSlug: match.empresa_slug });
    } else {
      const match = paquetes.find((p) => p.slug === d.slug);
      // Los paquetes destacados no llevan empresaSlug (spec §4, nota
      // "destacadas"): cual ruta de checkout usar depende de los
      // componentes del paquete, no de un lider unico.
      if (match) chips.push({ tipo: 'paquete', slug: match.slug, nombre: match.nombre, empresaSlug: null });
    }
  }
  return chips;
}

/**
 * Regla mecanica (spec §7): un chip abre inline el BookingBar heredado de
 * pesca SOLO si las tres condiciones se cumplen a la vez, sin importar lo
 * que diga `inlineable` en el diccionario de contenido.
 */
export function esInlineable(
  chip: ChipExperiencia,
  sedeSlug: string,
  empresaSlugPescaLegacy: string,
): boolean {
  return (
    sedeSlug === 'la-paz' &&
    chip.tipo === 'servicio' &&
    chip.slug === 'pesca-deportiva' &&
    chip.empresaSlug === empresaSlugPescaLegacy
  );
}
```

- [x] **Step 4: Compilar y correr el test**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs selector-experiencia
```
Expected: PASS (6 tests).

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores.

#### B. Componente visual `SelectorExperiencia`

**Files:**
- Create: `frontend/src/components/selector-experiencia.tsx`

**Interfaces:**
- Consume: `resolverChips`, `esInlineable`, `type ChipExperiencia` de `@/lib/selector-experiencia` (Tarea 4); `hrefPaquete`, `hrefServicio` de `@/lib/booking-href` (Tarea 3); `type SedeDestacada` de `@/content/sedes-tipos` (type-only); `BookingBar` de `@/components/booking-bar`; `type Dictionary, Locale` de `dictionaries`.
- Produce: componente `SelectorExperiencia({ lang, sedeSlug, destacadas, paquetes, servicios, moneda, booking, minDate, verTodoLabel, hrefVerTodo }: SelectorExperienciaProps)`. Usado por `SedeHero` (Tarea 5).

- [x] **Step 5: Implementar el componente**

No hay unit test de JSX en este proyecto (no hay Testing Library instalado — ver Tech Stack); la lógica que sí se testea ya está cubierta en la Tarea 4. Este paso escribe el componente y se verifica con `tsc`/`eslint`/`next build` (Tarea 12), como el resto de componentes visuales del repo.

```tsx
// frontend/src/components/selector-experiencia.tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeDestacada } from '@/content/sedes-tipos';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { hrefPaquete, hrefServicio } from '@/lib/booking-href';
import { resolverChips, esInlineable } from '@/lib/selector-experiencia';
import { BookingBar } from '@/components/booking-bar';

type SelectorExperienciaProps = {
  lang: Locale;
  sedeSlug: string;
  destacadas: SedeDestacada[];
  paquetes: PaqueteCatalogo[];
  servicios: ServicioCatalogo[];
  moneda: Moneda;
  booking: Dictionary['booking'];
  minDate: string;
  verTodoLabel: string;
  hrefVerTodo: string;
};

const EMPRESA_PESCA_LEGACY = process.env.NEXT_PUBLIC_EMPRESA_SLUG ?? 'sal-y-sol';

export function SelectorExperiencia({
  lang,
  sedeSlug,
  destacadas,
  paquetes,
  servicios,
  moneda,
  booking,
  minDate,
  verTodoLabel,
  hrefVerTodo,
}: SelectorExperienciaProps) {
  const [inlineAbierto, setInlineAbierto] = useState(false);
  const chips = resolverChips(destacadas, paquetes, servicios);

  return (
    <div className="relative z-10 mt-6 flex flex-wrap items-center gap-3">
      {chips.map((chip) => {
        const inline = esInlineable(chip, sedeSlug, EMPRESA_PESCA_LEGACY);
        const href =
          chip.tipo === 'paquete'
            ? hrefPaquete(paquetes.find((p) => p.slug === chip.slug)!, lang, moneda)
            : hrefServicio(servicios.find((s) => s.slug === chip.slug && s.empresa_slug === chip.empresaSlug)!, lang, moneda);

        if (inline) {
          return (
            <button
              key={`${chip.tipo}-${chip.slug}`}
              type="button"
              onClick={() => setInlineAbierto(true)}
              className="rounded-full border border-accent bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20"
            >
              {chip.nombre}
            </button>
          );
        }

        return (
          <Link
            key={`${chip.tipo}-${chip.slug}`}
            href={href}
            className="rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-accent hover:text-accent"
          >
            {chip.nombre}
          </Link>
        );
      })}

      <Link
        href={hrefVerTodo}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-muted transition-colors hover:text-foreground"
      >
        {verTodoLabel}
        <ArrowRight size={14} />
      </Link>

      {inlineAbierto && (
        <div className="mt-4 w-full">
          <BookingBar lang={lang} booking={booking} minDate={minDate} />
        </div>
      )}
    </div>
  );
}
```

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores (componente nuevo, sin caller todavía).

#### Cierre de la tarea

- [x] **Step 6: Verificación conjunta de la tarea**

Con todos los bloques anteriores integrados, ejecutar desde `frontend/` `npx tsc --noEmit` y ESLint sobre los archivos modificados de esta tarea. Aplicar los criterios descritos en cada bloque; no repetir tipos/lint tras cada cambio mecánico. Conservar las ejecuciones de pruebas en rojo/verde indicadas para la lógica pura. No avanzar si hay errores nuevos.

- [x] **Step 7: Commit de la tarea completa**

```bash
git add frontend/src/lib/selector-experiencia.ts frontend/tests/selector-experiencia.test.cjs frontend/src/components/selector-experiencia.tsx
git commit -m "feat(frontend): selector de experiencias"
```

---

### Tarea 5: Componentes reutilizables de la página de sede

#### A. `AboutSection` — imagen configurable

**Files:**
- Modify: `frontend/src/components/about-section.tsx`

**Interfaces:**
- Produce: `AboutSectionProps` gana `imagenSrc?: string` (default `/photos/capitan-cabrilla-bahia.webp`, el de hoy) e `imagenAlt?: string` (default `about.photoHint`, el de hoy).

- [x] **Step 1: Modificar el componente (retrocompatible)**

```tsx
// frontend/src/components/about-section.tsx
import Image from 'next/image';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type AboutSectionProps = {
  about: Pick<Dictionary['about'], 'headline' | 'body1' | 'body2' | 'photoHint'>;
  imagenSrc?: string;
  imagenAlt?: string;
};

export function AboutSection({
  about,
  imagenSrc = '/photos/capitan-cabrilla-bahia.webp',
  imagenAlt,
}: AboutSectionProps) {
  return (
    <section id="nosotros" className="scroll-mt-24 grid bg-surface lg:grid-cols-2">
      <div className="relative min-h-[320px] lg:min-h-[620px]">
        <Image
          src={imagenSrc}
          alt={imagenAlt ?? about.photoHint}
          fill
          sizes="(min-width: 1024px) 50vw, 100vw"
          className="object-cover"
        />
      </div>

      <div className="flex flex-col justify-center gap-6 px-6 py-16 sm:px-8 lg:px-20 lg:py-24">
        <span aria-hidden className="rev-regla block h-[3px] w-12 bg-action" />
        <h2 className="max-w-[16ch] text-3xl leading-[1.05] text-foreground sm:text-4xl lg:text-[50px]">
          {about.headline}
        </h2>
        <p className="max-w-[52ch] text-lg leading-relaxed text-foreground">{about.body1}</p>
        <p className="max-w-[52ch] text-lg leading-relaxed text-muted">{about.body2}</p>
      </div>
    </section>
  );
}
```

Nota: el tipo de `about` pasa de `Dictionary['about']` completo a un `Pick` de solo los 4 campos que el componente usa — así puede recibir `{ headline: colaboracion.titulo, body1: colaboracion.texto1, body2: colaboracion.texto2, photoHint: colaboracion.imagenAlt }` desde la página de sede (Tarea 10) sin depender del `Dictionary` global. `page.tsx` (que hoy pasa `dict.about` completo) sigue compilando: `Dictionary['about']` ya tiene esos 4 campos, un `Pick` más chico sigue siendo compatible como argumento — pero `page.tsx` deja de llamar a `AboutSection` en la Tarea 9 de todas formas.

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores (el único caller de hoy, `page.tsx`, sigue pasando `about={dict.about}`, compatible con el `Pick` más chico).

#### B. `SedeHero` (hero de la página de sede)

**Files:**
- Create: `frontend/src/components/sede-hero.tsx`

**Interfaces:**
- Consume: `type SedeHeroContenido, SedeDestacada` de `@/content/sedes-tipos` (type-only); `SelectorExperiencia` (Tarea 4); `BookingBar` de `@/components/booking-bar`; `ID_BARRA_PORTADA` de `@/components/sticky-booking-bar`; `type Dictionary, Locale` de `dictionaries`; `type Moneda, PaqueteCatalogo, ServicioCatalogo` de `@/lib/api`.
- Produce: componente `SedeHero(props)`. Usado por `sede/[slug]/page.tsx` (Tarea 10).

- [x] **Step 2: Implementar**

```tsx
// frontend/src/components/sede-hero.tsx
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeDestacada, SedeHeroContenido } from '@/content/sedes-tipos';
import type { Moneda, PaqueteCatalogo, ServicioCatalogo } from '@/lib/api';
import { SelectorExperiencia } from '@/components/selector-experiencia';
import { BookingBar } from '@/components/booking-bar';
import { ID_BARRA_PORTADA } from '@/components/sticky-booking-bar';

type SedeHeroProps = {
  lang: Locale;
  sedeSlug: string;
  contenido: SedeHeroContenido;
  mostrarBookingBar: boolean;
  destacadas: SedeDestacada[];
  paquetes: PaqueteCatalogo[];
  servicios: ServicioCatalogo[];
  moneda: Moneda;
  booking: Dictionary['booking'];
  minDate: string;
  verTodoLabel: string;
  hrefVerTodo: string;
};

/**
 * Hero de la pagina de sede. A diferencia de `Hero.tsx` (que sigue siendo el
 * de la portada de hoy, sin caller tras la Tarea 9), este:
 * - Acepta imagen fija ademas de video (Los Cabos no tiene video).
 * - `facts` puede venir vacio (Los Cabos) — no renderiza la fila si esta vacia.
 * - Solo monta `BookingBar` (con `ID_BARRA_PORTADA`) cuando `mostrarBookingBar`
 *   es true — hoy, unicamente para `sedeSlug === 'la-paz'` (spec §6.1, §7).
 * - Siempre monta `SelectorExperiencia` (Paso 0), en todas las sedes.
 */
export function SedeHero({
  lang,
  sedeSlug,
  contenido,
  mostrarBookingBar,
  destacadas,
  paquetes,
  servicios,
  moneda,
  booking,
  minDate,
  verTodoLabel,
  hrefVerTodo,
}: SedeHeroProps) {
  return (
    <section className="relative z-10 bg-background">
      <div className="relative w-full overflow-hidden">
        {contenido.video ? (
          <video
            autoPlay
            muted
            loop
            playsInline
            poster={contenido.imagen ?? undefined}
            className="absolute inset-0 h-full w-full object-cover"
          >
            <source src={contenido.video} type="video/webm" />
          </video>
        ) : contenido.imagen ? (
          // eslint-disable-next-line @next/next/no-img-element -- fondo a sangre, mismo tratamiento que el poster del video de la-paz
          <img src={contenido.imagen} alt="" className="absolute inset-0 h-full w-full object-cover" />
        ) : null}
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to top, rgba(10,11,14,0.88) 0%, rgba(10,11,14,0.42) 44%, rgba(10,11,14,0.10) 100%)',
          }}
        />

        <div className="relative flex min-h-[calc(52svh_+_var(--nav-alto))] flex-col justify-end lg:min-h-[calc(min(56svh,520px)_+_var(--nav-alto))]">
          <div className="mx-auto w-full max-w-6xl px-6 pt-[calc(5rem_+_var(--nav-alto))] pb-10 sm:px-8 lg:px-12 lg:pt-[calc(7rem_+_var(--nav-alto))] lg:pb-16">
            <h1 className="titulo-entra max-w-[19ch] text-[38px] leading-[1.02] text-hero-ink sm:text-6xl lg:text-[76px] lg:leading-[0.98]">
              {contenido.titulo.start} <span className="acento">{contenido.titulo.emphasis}</span>{' '}
              {contenido.titulo.end}
            </h1>
            <p className="titulo-entra titulo-entra-tarde mt-5 max-w-[52ch] text-base leading-relaxed text-hero-ink-soft lg:mt-6 lg:text-lg">
              {contenido.subtitulo}
            </p>

            <SelectorExperiencia
              lang={lang}
              sedeSlug={sedeSlug}
              destacadas={destacadas}
              paquetes={paquetes}
              servicios={servicios}
              moneda={moneda}
              booking={booking}
              minDate={minDate}
              verTodoLabel={verTodoLabel}
              hrefVerTodo={hrefVerTodo}
            />
          </div>
        </div>
      </div>

      {mostrarBookingBar && (
        <div
          id={ID_BARRA_PORTADA}
          className="relative mx-auto -mt-8 max-w-6xl px-6 sm:px-8 lg:-mt-12 lg:max-w-4xl lg:px-12"
        >
          <BookingBar lang={lang} booking={booking} minDate={minDate} />
        </div>
      )}

      {contenido.facts.length > 0 && (
        <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-x-6 gap-y-8 px-6 pt-12 pb-16 sm:px-8 lg:grid-cols-4 lg:gap-x-0 lg:px-12 lg:pt-14 lg:pb-20">
          {contenido.facts.map(({ value, label }, i) => (
            <div
              key={label}
              className={`flex flex-col gap-1 lg:px-8 ${
                i === 0 ? 'lg:pl-0' : 'lg:border-l lg:border-border'
              } ${i === contenido.facts.length - 1 ? 'lg:pr-0' : ''}`}
            >
              <dt className="text-xl font-bold tracking-[-0.02em] text-accent lg:text-[23px]">{value}</dt>
              <dd className="text-sm text-muted">{label}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
```

- [x] **Step 3: Comprobar integración con el selector**

El único `id={ID_BARRA_PORTADA}` de esta página pertenece a `SedeHero`. La Tarea 4 ya omite ese id en su barra inline, por lo que no hay parche posterior que aplicar. Revisar que `StickyBookingBar` conserva su objetivo y que la regla de inline exige La Paz/servicio/empresa legacy. No modificar componentes de reserva heredados.

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores.

#### Cierre de la tarea

- [x] **Step 4: Verificación conjunta de la tarea**

Con todos los bloques anteriores integrados, ejecutar desde `frontend/` `npx tsc --noEmit` y ESLint sobre los archivos modificados de esta tarea. Aplicar los criterios descritos en cada bloque; no repetir tipos/lint tras cada cambio mecánico. Conservar las ejecuciones de pruebas en rojo/verde indicadas para la lógica pura. No avanzar si hay errores nuevos.

- [x] **Step 5: Commit de la tarea completa**

```bash
git add frontend/src/components/about-section.tsx frontend/src/components/sede-hero.tsx frontend/src/components/selector-experiencia.tsx
git commit -m "feat(frontend): hero de sede e imagen configurable"
```

---

### Tarea 6: Secciones, recursos gráficos y textos del hub

#### A. Mapa ilustrado del hub (`HubMapaSedes`)

**Files:**
- Create: `frontend/src/components/hub-mapa-sedes.tsx`
- Create asset: `frontend/public/ilustraciones/mapa-baja.svg`
- Create asset: `frontend/public/ilustraciones/los-cabos-placeholder.webp` (referenciado por contenido)

**Interfaces:**
- Consume: `type SedeContenido` de `@/content/sedes-tipos` (type-only); `type Locale` de `dictionaries`.
- Produce: componente `HubMapaSedes({ lang, sedes, verDestinoLabel }: HubMapaSedesProps)`. Cada `SedeContenido` necesita coordenadas de pin dentro del SVG — se agregan como un mapa `POSICION_PIN: Record<string, { top: string; left: string }>` local al componente (posiciones ilustradas, no geográficas reales — spec §2 "no incluye... mapa geográfico real").

- [x] **Step 1: Generar el asset ilustrado**

Usar un skill de generación/diseño de imagen disponible en el entorno (`design` u otro cargado en este proyecto) para producir una ilustración SVG a la medida de la costa de Baja California Sur, estilo simple/vectorial acorde a la paleta del sitio (`--indigo`, `--accent`, tonos turquesa vistos en `globals.css`). Guardar en `frontend/public/ilustraciones/mapa-baja.svg` si el resultado es vectorial. Si la herramienta produce raster, usar su extensión real y actualizar las referencias, sin renombrarlo a SVG. Si el skill de imagen no está disponible en el momento de ejecutar esta tarea, usar como interino un SVG geométrico simple (silueta de la península con dos-tres formas, sin detalle fotográfico) para no bloquear el resto del plan, y dejar una nota en el PR pidiendo el asset final de diseño antes de mergear a producción.

Generar además la ilustración genérica de costa para `los-cabos-placeholder.webp`, claramente provisional: no representar un equipo/tour real ni reutilizar fotos de pesca de La Paz como si fueran de Tours Cabo. Si el formato final cambia, actualizar ambas entradas de idioma de `sedes-cuerpo.ts`. Registrar cualquier asset interino pendiente de revisión visual.

- [x] **Step 2: Implementar el componente**

```tsx
// frontend/src/components/hub-mapa-sedes.tsx
'use client';

import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { MapPin, X } from '@phosphor-icons/react';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { SedeContenido } from '@/content/sedes-tipos';

type HubMapaSedesProps = {
  lang: Locale;
  sedes: SedeContenido[];
  verDestinoLabel: string;
  conLabel: string;
};

/**
 * Posiciones ilustradas del pin dentro del SVG (porcentaje del contenedor),
 * no coordenadas geograficas reales (spec §2, §5.2). Agregar una sede nueva
 * = agregar su entrada aqui + en `content/sedes-indice.ts`, sin tocar el layout.
 */
const POSICION_PIN: Record<string, { top: string; left: string }> = {
  'la-paz': { top: '38%', left: '52%' },
  'los-cabos': { top: '82%', left: '58%' },
};

export function HubMapaSedes({ lang, sedes, verDestinoLabel, conLabel }: HubMapaSedesProps) {
  const [abiertoSlug, setAbiertoSlug] = useState<string | null>(null);
  const sedeAbierta = sedes.find((s) => s.slug === abiertoSlug) ?? null;

  return (
    <div className="relative mx-auto max-w-3xl">
      <div className="relative aspect-[3/4] w-full overflow-hidden rounded-3xl border border-border bg-surface">
        <Image
          src="/ilustraciones/mapa-baja.svg"
          alt="Ilustración de la península de Baja California Sur"
          fill
          className="object-contain p-6"
        />

        {sedes.map((sede) => {
          const pos = POSICION_PIN[sede.slug];
          if (!pos) return null;
          return (
            <button
              key={sede.slug}
              type="button"
              onClick={() => setAbiertoSlug(sede.slug === abiertoSlug ? null : sede.slug)}
              aria-label={sede.negocio?.nombre ?? sede.empresaFundadoraNombre}
              className="absolute flex h-9 w-9 -translate-x-1/2 -translate-y-full items-center justify-center rounded-full bg-accent text-white shadow-lg transition-transform hover:scale-110"
              style={{ top: pos.top, left: pos.left }}
            >
              <MapPin size={20} weight="fill" />
            </button>
          );
        })}
      </div>

      {sedeAbierta && (
        <div className="absolute inset-x-6 bottom-6 z-10 flex items-center gap-4 rounded-2xl border border-border bg-background p-4 shadow-[0_18px_45px_rgba(11,36,32,0.16)]">
          <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-surface">
            {sedeAbierta.hero.imagen && (
              <Image src={sedeAbierta.hero.imagen} alt="" fill className="object-cover" />
            )}
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-foreground">
              {sedeAbierta.negocio?.nombre ?? sedeAbierta.empresaFundadoraNombre}
            </p>
            <p className="text-xs text-muted">
              {conLabel} {sedeAbierta.empresaFundadoraNombre}
            </p>
          </div>
          <Link
            href={`/${lang}/sede/${sedeAbierta.slug}`}
            className="shrink-0 rounded-full bg-accent px-4 py-2 text-xs font-semibold text-white"
          >
            {verDestinoLabel}
          </Link>
          <button
            type="button"
            onClick={() => setAbiertoSlug(null)}
            aria-label="Cerrar"
            className="shrink-0 text-muted hover:text-foreground"
          >
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
```

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores (componente nuevo, sin caller todavía).

#### B. Resto de secciones del hub (`HubHero`, `HubGridSedes`, `HubPorQue`)

**Files:**
- Create: `frontend/src/components/hub-hero.tsx`
- Create: `frontend/src/components/hub-grid-sedes.tsx`
- Create: `frontend/src/components/hub-por-que.tsx`
- Create asset: `frontend/public/logos/wordmark-agencia.svg`

**Interfaces:**
- Consume: `type SedeContenido` de `@/content/sedes-tipos` (type-only); `type Locale` de `dictionaries`.
- Produce: `HubHero({ nombreAgencia, mision, ctaLabel, mapaAnchorId })`, `HubGridSedes({ lang, sedes, verDestinoLabel, conLabel })`, `HubPorQue({ pilares }: { pilares: { titulo: string; texto: string }[] })`.

- [x] **Step 3: Generar el wordmark de agencia**

Usar el skill de diseño de imagen disponible para producir un wordmark/logo genérico de "Sal y Sol Baja Experiences" (SVG, mismo tratamiento tipográfico que `svglogosalysol2.svg`). Guardar en `frontend/public/logos/wordmark-agencia.svg`. Si la herramienta produce una imagen raster, conservar su extensión real y actualizar las referencias del header/footer; no renombrar PNG a SVG. Como contingencia, un SVG tipográfico válido con el nombre de agencia puede ocupar esa misma ruta. Debe existir el archivo referenciado antes de cerrar la tarea; un `<span>` aislado no sustituye un asset que otros componentes cargan con `<Image>`.

- [x] **Step 4: `HubHero`**

```tsx
// frontend/src/components/hub-hero.tsx
'use client';

type HubHeroProps = {
  nombreAgencia: string;
  mision: string;
  ctaLabel: string;
  mapaAnchorId: string;
};

export function HubHero({ nombreAgencia, mision, ctaLabel, mapaAnchorId }: HubHeroProps) {
  return (
    <section className="relative overflow-hidden bg-background">
      <div className="relative min-h-[70svh]">
        {/* eslint-disable-next-line @next/next/no-img-element -- fondo decorativo a sangre */}
        <img
          src="/photos/yellowtail-pelicanos-bahia.webp"
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to top, rgba(10,11,14,0.88) 0%, rgba(10,11,14,0.42) 44%, rgba(10,11,14,0.10) 100%)',
          }}
        />
        <div className="relative mx-auto flex min-h-[70svh] max-w-6xl flex-col justify-end px-6 pb-16 pt-[calc(6rem_+_var(--nav-alto))] sm:px-8 lg:px-12">
          <h1 className="max-w-[20ch] text-[38px] leading-[1.02] text-hero-ink sm:text-6xl lg:text-[72px] lg:leading-[0.98]">
            {nombreAgencia}
          </h1>
          <p className="mt-5 max-w-[52ch] text-base leading-relaxed text-hero-ink-soft lg:text-lg">
            {mision}
          </p>
          <button
            type="button"
            onClick={() => document.getElementById(mapaAnchorId)?.scrollIntoView({ behavior: 'smooth' })}
            className="mt-8 inline-flex w-fit items-center justify-center rounded-full bg-accent px-6 py-3 text-sm font-semibold text-white shadow-md transition-transform hover:brightness-105 active:scale-[0.98]"
          >
            {ctaLabel}
          </button>
        </div>
      </div>
    </section>
  );
}
```

- [x] **Step 5: `HubGridSedes`**

```tsx
// frontend/src/components/hub-grid-sedes.tsx
import Image from 'next/image';
import Link from 'next/link';
import type { Locale } from '@/app/[lang]/dictionaries';
import type { SedeContenido } from '@/content/sedes-tipos';

type HubGridSedesProps = {
  lang: Locale;
  sedes: SedeContenido[];
  verDestinoLabel: string;
  conLabel: string;
};

/**
 * Respaldo accesible/SEO del mapa (spec §5.3): las mismas sedes en tarjetas
 * normales, sin depender de JS ni de interaccion con el SVG.
 */
export function HubGridSedes({ lang, sedes, verDestinoLabel, conLabel }: HubGridSedesProps) {
  return (
    <div id="sedes" className="scroll-mt-24 grid gap-6 sm:grid-cols-2">
      {sedes.map((sede) => (
        <article
          key={sede.slug}
          className="flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
        >
          <div className="relative h-48 w-full">
            {sede.hero.imagen && (
              <Image src={sede.hero.imagen} alt="" fill className="object-cover" />
            )}
          </div>
          <div className="flex flex-1 flex-col gap-2 p-6">
            <h3 className="text-xl font-bold text-foreground">
              {sede.negocio?.nombre ?? sede.empresaFundadoraNombre}
            </h3>
            <p className="text-sm text-muted">
              {conLabel} {sede.empresaFundadoraNombre}
            </p>
            <Link
              href={`/${lang}/sede/${sede.slug}`}
              className="mt-4 inline-flex w-fit items-center justify-center rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-transform hover:brightness-105 active:scale-[0.98]"
            >
              {verDestinoLabel}
            </Link>
          </div>
        </article>
      ))}
    </div>
  );
}
```

- [x] **Step 6: `HubPorQue`**

```tsx
// frontend/src/components/hub-por-que.tsx
type Pilar = { titulo: string; texto: string };

type HubPorQueProps = {
  headline: string;
  pilares: Pilar[];
};

export function HubPorQue({ headline, pilares }: HubPorQueProps) {
  return (
    <section className="mx-auto max-w-6xl px-6 py-16 sm:px-8 lg:px-12">
      <h2 className="max-w-[20ch] text-3xl leading-[1.05] text-foreground sm:text-4xl">{headline}</h2>
      <div className="mt-10 grid gap-8 sm:grid-cols-3">
        {pilares.map((pilar) => (
          <div key={pilar.titulo} className="flex flex-col gap-2">
            <h3 className="text-lg font-semibold text-foreground">{pilar.titulo}</h3>
            <p className="text-sm leading-relaxed text-muted">{pilar.texto}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
```

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores.

#### C. Diccionario — claves nuevas de copy del hub

**Files:**
- Modify: `frontend/src/app/[lang]/dictionaries/es.json`
- Modify: `frontend/src/app/[lang]/dictionaries/en.json`

**Interfaces:**
- Produce: nueva clave de nivel superior `hub` en ambos JSON, consumida por `page.tsx` (Tarea 9).

- [x] **Step 7: Agregar la clave `hub` a `es.json`** (junto a las demás claves de nivel superior, ej. después de `catalog`)

```json
  "hub": {
    "nombreAgencia": "Sal y Sol Baja Experiences",
    "mision": "Una alianza de agencias locales para vivir Baja California Sur como se merece: con quienes la conocen de verdad.",
    "ctaElegirDestino": "Elige tu destino",
    "verDestino": "Ver destino",
    "conLabel": "Con",
    "verTodoDestinos": "Ver todos los destinos",
    "porQueHeadline": "Por qué Sal y Sol Baja Experiences",
    "pilares": [
      { "titulo": "Alianzas locales de confianza", "texto": "Cada sede la opera gente de ahí: capitanes, guías y operadores que conocen su tramo de costa mejor que nadie." },
      { "titulo": "Un solo lugar para reservar en toda Baja", "texto": "Explora y reserva experiencias en distintos destinos de Baja California Sur sin cambiar de sitio ni de proceso." },
      { "titulo": "Atención personalizada", "texto": "El mismo trato cercano de siempre, ahora disponible en cada destino de la alianza." }
    ],
    "meta": {
      "title": "Sal y Sol Baja Experiences — Experiencias en Baja California Sur",
      "description": "Descubre experiencias de pesca deportiva y turismo en los destinos de Baja California Sur operados por la alianza Sal y Sol Baja Experiences."
    }
  },
```

- [x] **Step 8: Agregar la clave equivalente a `en.json`**

```json
  "hub": {
    "nombreAgencia": "Sal y Sol Baja Experiences",
    "mision": "A partnership of local agencies for experiencing Baja California Sur the way it deserves: with the people who truly know it.",
    "ctaElegirDestino": "Choose your destination",
    "verDestino": "View destination",
    "conLabel": "With",
    "verTodoDestinos": "See all destinations",
    "porQueHeadline": "Why Sal y Sol Baja Experiences",
    "pilares": [
      { "titulo": "Trusted local partnerships", "texto": "Each destination is run by local people — captains, guides, and operators who know their stretch of coast better than anyone." },
      { "titulo": "One place to book across Baja", "texto": "Explore and book experiences across different Baja California Sur destinations without switching sites or processes." },
      { "titulo": "Personalized attention", "texto": "The same close, personal care as always, now available at every destination in the partnership." }
    ],
    "meta": {
      "title": "Sal y Sol Baja Experiences — Experiences in Baja California Sur",
      "description": "Discover sportfishing and tourism experiences across the Baja California Sur destinations run by the Sal y Sol Baja Experiences partnership."
    }
  },
```

- [x] **Step 9: Reiniciar `npm run dev` si estaba corriendo (nota de `CLAUDE.md`: Turbopack cachea diccionarios)**

No es un paso de verificación automática — es un recordatorio operativo para quien ejecute esta tarea en local.

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores (agregar una clave nueva a ambos JSON no rompe el tipo `Dictionary`, que se infiere de `es.json`; falta que `en.json` tenga exactamente las mismas claves, ya cumplido en el Step 8).

#### Cierre de la tarea

- [x] **Step 10: Verificación conjunta de la tarea**

Con todos los bloques anteriores integrados, ejecutar desde `frontend/` `npx tsc --noEmit` y ESLint sobre los archivos modificados de esta tarea. Aplicar los criterios descritos en cada bloque; no repetir tipos/lint tras cada cambio mecánico. Conservar las ejecuciones de pruebas en rojo/verde indicadas para la lógica pura. No avanzar si hay errores nuevos.

- [x] **Step 11: Commit de la tarea completa**

```bash
git add frontend/src/components/hub-mapa-sedes.tsx frontend/public/ilustraciones/mapa-baja.svg frontend/public/ilustraciones/los-cabos-placeholder.webp frontend/src/components/hub-hero.tsx frontend/src/components/hub-grid-sedes.tsx frontend/src/components/hub-por-que.tsx frontend/public/logos/wordmark-agencia.svg "frontend/src/app/[lang]/dictionaries/es.json" "frontend/src/app/[lang]/dictionaries/en.json"
git commit -m "feat(frontend): componentes assets y textos del hub"
```

---

### Tarea 7: Navegación por sede: selector y encabezado

#### A. Contrato completo de `SedeSelector` y navegación a sede

**Completar este bloque antes del encabezado, dentro de esta misma tarea.**

**Files:**
- Modify: `frontend/src/components/sede-selector.tsx`

**Interfaces:** `SedeOpcion = Pick<SedeIndiceEntry, "slug" | "nombre">`; `sedes?: SedeOpcion[]`; `sedeSeleccionadaSlug?: string`; `onSelectSede?: (sede: SedeOpcion) => void`. Los callers actuales que pasan `Sede[]` siguen siendo compatibles estructuralmente; el encabezado podrá pasar entradas del índice sin `id`/`zona_horaria`.

- [x] **Step 1: Cambiar tipos y eliminar la carga duplicada**

Importar `type SedeIndiceEntry` desde `@/content/sedes-tipos` y `SEDES_INDICE`/`getSedeIndice` desde `@/content/sedes-indice`. Quitar `getSedes`/`Sede`, `sedesFetched`, su setter y el efecto de carga de API. Cambiar también el parámetro de `handleSelect` y el callback a `SedeOpcion`. Mantener los efectos de cierre por Escape/click externo.

Usar `const sedes = sedesProp ?? Object.values(SEDES_INDICE)`: un `[]` explícito significa que no hay sedes activas y nunca dispara fallback. El fallback al índice es solo compatibilidad para callers que todavía omiten la prop; después de la Tarea 7 el encabezado siempre entrega la lista reconciliada.

- [x] **Step 2: Hacer que la selección explícita y el vacío sean correctos**

El slug de ruta recibido por prop manda inmediatamente, también tras navegación SPA. El estado local puede conservar la selección optimista y la preferencia de callers anteriores, pero no debe prevalecer sobre esa prop:

```tsx
const slugActivo = sedeSeleccionadaSlug ?? sedeSlugActiva;
const sedeActiva =
  sedes.find((sede) => sede.slug === slugActivo) ??
  (sedeSeleccionadaSlug ? getSedeIndice(sedeSeleccionadaSlug) : undefined) ??
  sedes[0];
```

Quitar los objetos fallback hardcodeados de La Paz. Si no hay `sedeActiva`, mostrar `label`; con `sedes.length === 0`, deshabilitar la apertura y no renderizar opciones. Usar `sedeActiva?.slug` en la comparación de selección. Una sede explícita que ya no aparezca en la lista activa puede seguir dando nombre al botón: el acceso directo a su página depende del índice, no de la API.

- [x] **Step 3: Navegar y persistir la preferencia**

Mantener `guardarSedePreferida(sede.slug)` y el callback si existe. En la rama sin callback navegar a `/${lang}/sede/${sede.slug}` mediante `router.push`. Conservar el JSX y los estilos salvo los ajustes de vacío y selección anteriores.

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: cero errores nuevos, incluidos los callers actuales de header/catálogo. Inspeccionar que no quede ningún `getSedes`, `sedesFetched` ni objeto fallback a La Paz en este componente.

Casos para el smoke manual de la Tarea 12: `[]` no repuebla destinos; ruta Los Cabos gana a preferencia La Paz; un cambio SPA actualiza el nombre; elegir una sede guarda preferencia y navega a su ruta.

#### B. `SiteHeader` — variante y sede activa

**Files:**
- Modify: `frontend/src/components/site-header.tsx`

**Interfaces:**
- Produce: `SiteHeaderProps` gana `variante?: 'hub' | 'sede'` (default `'sede'`) y `sedeSlugActual?: string`.
- Consume: `SEDES_INDICE`, `type SedeIndiceEntry` de `@/content/sedes-indice` (client-safe — **nunca** `@/content/sedes-cuerpo`, que es `server-only`); `sedesActivas` de `@/lib/reconciliar-sedes`; `getSedes` de `@/lib/api`; `leerSedePreferidaCliente` de `@/lib/sede` (ya existe).

Nota (arch-critic ronda 2, hallazgo 1 y 5): la versión anterior de este componente importaba `getSedeContenido`/`SedeContenido` (el contenido completo, pesado) y hacía su propio `getSedes()` mientras `SedeSelector` (su hijo) hacía el suyo por separado, sin reconciliar. Esta versión: (a) solo toca `SEDES_INDICE` (chico, client-safe), (b) resuelve la lista de sedes UNA vez y se la pasa a `SedeSelector` por prop.

- [x] **Step 4: Preparar resolución de sede y lista única**

Implementar tipos, imports y resolución del ejemplo siguiente. La prop explícita manda sobre estado anterior; cuando no hay prop, resolver query válida → preferencia válida → primera sede activa. Ejecutar el efecto también en el hub para reconciliar su selector. El bloque A de esta tarea ya eliminó la carga de API del hijo.

- [x] **Step 5: Integrar marca, enlaces y menús con esa resolución**

Usar el siguiente componente como referencia final. Conservar tanto desktop como móvil y las props existentes. Los anchors que solo existen en La Paz deben ocultarse en otras sedes; sin sede resuelta, enlazar al grid del hub en vez de construir `/sede/` vacío.

```tsx
// frontend/src/components/site-header.tsx
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import Image from 'next/image';
import { List, X } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { SEDES_INDICE } from '@/content/sedes-indice';
import type { SedeIndiceEntry } from '@/content/sedes-tipos';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { getSedes } from '@/lib/api';
import { leerSedePreferidaCliente } from '@/lib/sede';
import { WhatsappContact } from '@/components/whatsapp-contact';
import { LangSwitch } from '@/components/lang-switch';
import { SedeSelector } from '@/components/sede-selector';

type SiteHeaderProps = {
  lang: Locale;
  nav: Dictionary['nav'];
  /** 'hub' solo en `/[lang]`. Cualquier otra pagina (con o sin sede propia) usa 'sede'. */
  variante?: 'hub' | 'sede';
  /** Si no llega, se resuelve en cliente (query, localStorage/cookie, o primera sede activa). */
  sedeSlugActual?: string;
  /** Clases extra del `<header>`. Existe para el `print:hidden` del recibo. */
  className?: string;
};

export function SiteHeader({
  lang,
  nav,
  variante = 'sede',
  sedeSlugActual,
  className = '',
}: SiteHeaderProps) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const sinMovimiento = useReducedMotion();
  const [slugResuelto, setSlugResuelto] = useState<string | undefined>(sedeSlugActual);
  // Fallo abierto desde el primer render (sin esperar la red): todas las
  // sedes del indice. `sedesActivas` reduce esta lista cuando `getSedes()`
  // resuelve. `SedeSelector` recibe esta misma lista por prop — nunca vuelve
  // a pedir `getSedes()` por su cuenta (arch-critic ronda 2, hallazgo 5).
  const [sedesDisponibles, setSedesDisponibles] = useState<SedeIndiceEntry[]>(
    Object.values(SEDES_INDICE),
  );

  /* eslint-disable react-hooks/set-state-in-effect -- mismo criterio que
     sede-selector.tsx: sin slug explicito, la sede activa se resuelve en
     cliente (localStorage/cookie) post-hidratacion. Un crawler ve el
     fallback (primera sede activa), nunca un valor en blanco. */
  useEffect(() => {
    let montado = true;
    getSedes()
      .then((data) => data, () => null)
      .then((sedesApi) => {
        if (!montado) return;
        const activas = sedesActivas(SEDES_INDICE, sedesApi);
        setSedesDisponibles(activas);
        if (sedeSlugActual) return;
        const enUrl = new URLSearchParams(window.location.search).get('sede');
        const preferida = leerSedePreferidaCliente();
        setSlugResuelto(
          [enUrl, preferida].find((slug) => slug && activas.some((s) => s.slug === slug))
            ?? activas[0]?.slug,
        );
      });
    return () => {
      montado = false;
    };
  }, [pathname, sedeSlugActual]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const slugActual = sedeSlugActual ?? slugResuelto ?? sedesDisponibles[0]?.slug;
  const sedeIndiceActiva: SedeIndiceEntry | undefined =
    variante === 'sede' && slugActual ? SEDES_INDICE[slugActual] : undefined;

  const brandMain = variante === 'hub' ? nav.brandMain : (sedeIndiceActiva?.empresaFundadoraNombre ?? nav.brandMain);
  const brandAccent = variante === 'hub' ? nav.brandAccent : '';
  const logoSrc =
    variante === 'hub' ? '/logos/wordmark-agencia.svg' : (sedeIndiceActiva?.logo ?? '/logos/wordmark-agencia.svg');

  const anclaBase = variante === 'sede' && slugActual ? `/${lang}/sede/${slugActual}` : null;

  const links = anclaBase
    ? [
        { href: `${anclaBase}#experiencias`, label: nav.catalogo },
        { href: `${anclaBase}#nosotros`, label: nav.nosotros },
        ...(slugActual === 'la-paz' ? [
          { href: `${anclaBase}#temporadas`, label: nav.temporadas },
          { href: `${anclaBase}#galeria`, label: nav.galeria },
          { href: `${anclaBase}#preguntas`, label: nav.preguntas },
        ] : []),
      ]
    : [{ href: `/${lang}#sedes`, label: nav.catalogo }];

  return (
    <div className={`fixed inset-x-0 top-0 z-40 lg:top-4 lg:px-8 ${className}`}>
      <header className="relative mx-auto flex h-20 w-full items-center justify-between gap-6 border-b border-border bg-background px-6 sm:px-8 lg:h-[88px] lg:max-w-6xl lg:border lg:border-border lg:px-12 lg:shadow-[0_18px_45px_rgba(11,36,32,0.16)]">
        <Link
          href={`/${lang}`}
          className="flex shrink-0 items-center text-foreground"
          onClick={() => setOpen(false)}
        >
          <Image
            src={logoSrc}
            alt={`${brandMain} ${brandAccent}`.trim()}
            width={1026}
            height={331}
            priority
            className="h-11 w-auto lg:h-14"
          />
        </Link>

        <nav className="hidden items-center gap-7 lg:flex">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-[15px] text-foreground transition-colors hover:text-accent"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          <SedeSelector
            lang={lang}
            sedes={sedesDisponibles}
            sedeSeleccionadaSlug={slugActual}
            label={nav.sedeLabel}
            variant="header"
            className="hidden sm:inline-block"
          />
          <WhatsappContact nav={nav} tone="plain" />

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? nav.closeMenu : nav.openMenu}
            aria-expanded={open}
            className="flex h-11 w-11 items-center justify-center border border-border text-foreground lg:hidden"
          >
            {open ? <X size={18} /> : <List size={18} />}
          </button>
        </div>

        <AnimatePresence>
          {open && (
            <motion.div
              key="menu-movil"
              initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="absolute inset-x-0 top-full flex flex-col border-b border-border bg-surface px-6 py-2 shadow-[0_16px_40px_rgba(11,36,32,0.18)] sm:px-8 lg:hidden"
            >
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="border-b border-border-strong py-3.5 text-[15px] text-foreground last:border-b-0"
                >
                  {link.label}
                </Link>
              ))}
              <div className="flex items-center justify-between border-b border-border-strong py-3.5">
                <span className="text-[15px] text-muted">{nav.sedeLabel}</span>
                <SedeSelector
                  lang={lang}
                  sedes={sedesDisponibles}
                  sedeSeleccionadaSlug={slugActual}
                  label={nav.sedeLabel}
                  variant="header"
                />
              </div>
              <div className="flex items-center justify-between border-b border-border-strong py-3.5">
                <span className="text-[15px] text-muted">{nav.switchLang}</span>
                <LangSwitch lang={lang} label={nav.switchLang} placement="bottom" align="right" />
              </div>
              <div className="py-3">
                <WhatsappContact nav={nav} variant="menu" />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>
    </div>
  );
}
```

Nota: el `esLaPaz`/doble `<Image>` de la versión anterior desaparece — el `logo` de cada sede ya viene resuelto desde `SEDES_INDICE` (Tarea 1), así que agregar una tercera sede no requiere tocar `SiteHeader` (spec §10, forma de escalabilidad).

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores nuevos; el contrato del selector ya se actualizó en el bloque A. Revisar que solo el padre consulta sedes, que el efecto también corre en el hub y que un cambio de `sedeSlugActual` se refleja sin esperar la API.

#### Cierre de la tarea

- [x] **Step 6: Verificación conjunta de la tarea**

Con todos los bloques anteriores integrados, ejecutar desde `frontend/` `npx tsc --noEmit` y ESLint sobre los archivos modificados de esta tarea. Aplicar los criterios descritos en cada bloque; no repetir tipos/lint tras cada cambio mecánico. Conservar las ejecuciones de pruebas en rojo/verde indicadas para la lógica pura. No avanzar si hay errores nuevos.

- [x] **Step 7: Commit de la tarea completa**

```bash
git add frontend/src/components/sede-selector.tsx frontend/src/components/site-header.tsx
git commit -m "feat(frontend): navegacion y encabezado por sede"
```

---

### Tarea 8: Footer por sede y actualización de sus consumidores

**Files:**
- Modify: `frontend/src/components/site-footer.tsx`
- Modify: `frontend/src/app/[lang]/deslinde/page.tsx`
- Modify: `frontend/src/app/[lang]/privacidad/page.tsx`
- Modify: `frontend/src/app/[lang]/not-found.tsx`
- Modify: `frontend/src/components/checkout-view.tsx`
- Modify: `frontend/src/components/booking-confirmation.tsx`
- Modify: `frontend/src/app/[lang]/page.tsx` (caller anterior a la activación del hub)
- Modify: `frontend/src/app/[lang]/catalogo/page.tsx` (caller hasta su retiro en Tarea 11)
- Modify: `frontend/src/app/[lang]/traslados/page.tsx` (footer del estado no disponible)

**Interfaces:**
- Consume: `type SedeNegocio` de `@/content/sedes-tipos` (Tarea 1, type-only — `SiteFooter` es Server Component, recibe `negocio` ya resuelto por props desde `page.tsx`/`sede/[slug]/page.tsx`).

- [x] **Step 1: `SiteFooter` — nueva prop `negocio`**

```tsx
// frontend/src/components/site-footer.tsx
import Link from 'next/link';
import Image from 'next/image';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { SedeNegocio } from '@/content/sedes-tipos';

type SiteFooterProps = {
  lang: Locale;
  footer: Dictionary['footer'];
  nav: Dictionary['nav'];
  bookLabel: string;
  /** `null` en el hub y en cualquier sede sin `negocio` (hoy, Los Cabos): el bloque de dirección/horario se omite en vez de mostrar el de otra sede. */
  negocio: SedeNegocio;
  sedeSlug?: string;
};

export function SiteFooter({ lang, footer, nav, bookLabel, negocio, sedeSlug }: SiteFooterProps) {
  const baseSede = sedeSlug ? `/${lang}/sede/${sedeSlug}` : null;
  const secciones = baseSede
    ? [
        { href: `${baseSede}#experiencias`, label: nav.catalogo },
        { href: `${baseSede}#nosotros`, label: nav.nosotros },
        ...(sedeSlug === 'la-paz' ? [
          { href: `${baseSede}#temporadas`, label: nav.temporadas },
          { href: `${baseSede}#incluye`, label: nav.contacto },
          { href: `${baseSede}#preguntas`, label: nav.preguntas },
        ] : []),
      ]
    : [{ href: `/${lang}#sedes`, label: nav.catalogo }];

  const legales = [
    { href: `/${lang}/deslinde`, label: footer.waiver },
    { href: `/${lang}/privacidad`, label: footer.privacy },
  ];

  return (
    <footer
      id="contacto"
      className="relative scroll-mt-24 overflow-hidden border-t border-border bg-background"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: 'radial-gradient(50% 60% at 88% 0%, rgba(49,28,153,0.10), transparent 70%)',
        }}
      />
      <div className="relative mx-auto max-w-6xl px-6 pt-20 sm:px-8 lg:px-12 lg:pt-24">
        <div className="grid gap-10 pb-16 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr] lg:gap-12">
          <div className="flex flex-col items-start gap-5">
            <h2 className="max-w-[13ch] text-3xl leading-[1.05] text-foreground lg:text-[38px]">
              {footer.headline}
            </h2>
            <Link
              href={sedeSlug === 'la-paz' ? `/${lang}/reservar` : baseSede ? `${baseSede}#experiencias` : `/${lang}#sedes`}
              className="inline-flex items-center rounded-full bg-foreground px-6 py-3 text-sm font-semibold text-background transition-transform active:scale-[0.98]"
            >
              {bookLabel}
            </Link>
          </div>

          {negocio && (
            <div className="flex flex-col gap-3">
              <span className="text-xs font-semibold text-muted">{footer.addressLabel}</span>
              <span className="text-base text-foreground">{negocio.calle}</span>
              <span className="text-base text-muted">
                {negocio.ciudad}, {negocio.estado}
              </span>
              <span className="mt-3 text-xs font-semibold text-muted">{footer.hoursLabel}</span>
              <span className="text-base text-foreground">{footer.hours}</span>
              <span className="mt-3 text-xs font-semibold text-muted">{footer.officeLabel}</span>
              <span className="text-base text-foreground">{footer.office}</span>
            </div>
          )}

          <nav aria-label={footer.exploreLabel} className="flex flex-col gap-3">
            <span className="text-xs font-semibold text-muted">{footer.exploreLabel}</span>
            {secciones.map((link) => (
              <Link key={link.href} href={link.href} className="text-base text-foreground">
                {link.label}
              </Link>
            ))}
          </nav>

          <nav aria-label={footer.legalLabel} className="flex flex-col gap-3">
            <span className="text-xs font-semibold text-muted">{footer.legalLabel}</span>
            {legales.map((link) => (
              <Link key={link.href} href={link.href} className="text-base text-foreground">
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>

      <div className="relative mx-auto max-w-6xl overflow-hidden px-6 pb-10 sm:px-8 lg:px-12">
        <Image
          src={sedeSlug === 'la-paz' ? '/logos/svglogosalysol2.svg' : '/logos/wordmark-agencia.svg'}
          alt=""
          width={261}
          height={123}
          sizes="100vw"
          className="mx-auto h-auto w-full max-w-[922px]"
        />
        <div className="mt-8 flex flex-col gap-2 border-t border-border-strong pt-8 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-sm text-muted">
            Sal y Sol Baja Experiences. {footer.rights}
          </span>
          {negocio && <span className="text-sm text-muted">{negocio.ciudad}, {negocio.estado}</span>}
        </div>
      </div>
    </footer>
  );
}
```

Nota: conservar los textos de contacto globales `footer.hours`/`footer.office` solo dentro del bloque condicionado a `negocio`. Los links del footer también deben apuntar a anchors existentes después de migrar la portada: no dejar enlaces al antiguo `/${lang}#nosotros`. El footer genérico no muestra dirección ni ubicación de La Paz.

- [x] **Step 2: Actualizar TODOS los callers de `SiteFooter` en el mismo cambio**

El worktree actual tiene cinco callers, no dos. Confirmarlos con `rg -n "<SiteFooter" src` desde `frontend/` y actualizar:

| Caller | Props en esta tarea |
|---|---|
| `app/[lang]/page.tsx` (todavía portada anterior) | Importar `getSedeContenido` server-side y pasar `negocio={getSedeContenido("la-paz", lang)?.negocio ?? null}` y `sedeSlug="la-paz"`. La Tarea 9 lo sustituye por `negocio={null}` sin `sedeSlug`. |
| `app/[lang]/catalogo/page.tsx` | Importar `getSedeContenido` server-side; pasar negocio de `sedeActual.slug` o `null`, y `sedeSlug={sedeActual.slug}`. Se elimina el caller en Tarea 11. |
| `app/[lang]/deslinde/page.tsx` | `negocio={null}`; footer de agencia sin sede atribuida. |
| `app/[lang]/privacidad/page.tsx` | `negocio={null}`; footer de agencia sin sede atribuida. |
| `app/[lang]/traslados/page.tsx` | `negocio={null}` provisionalmente; Tarea 11 aporta la sede resuelta en servidor y el negocio si hay coincidencia. |

La página nueva de sede (Tarea 10) pasará `negocio={contenido.negocio}` y `sedeSlug={slug}`. No convertir `negocio` en opcional para ocultar callers olvidados.

- [x] **Step 3: `SiteHeader` en `deslinde/page.tsx`, `privacidad/page.tsx`, `not-found.tsx` — pasar `variante="sede"` explícito**

En los tres archivos, cambiar:
```tsx
<SiteHeader lang={lang} nav={dict.nav} />
```
por:
```tsx
<SiteHeader lang={lang} nav={dict.nav} variante="sede" />
```
(en `not-found.tsx`, `lang="es"` en vez de `lang={lang}`, sin cambios ahí). Sin `sedeSlugActual`: los tres son páginas sin sede resuelta server-side, `SiteHeader` cae al fallback de cliente (Tarea 7).

- [x] **Step 4: `SiteHeader` en `checkout-view.tsx` y `booking-confirmation.tsx` — mismo cambio**

```tsx
<SiteHeader lang={lang} nav={nav} variante="sede" />
```
(en `booking-confirmation.tsx`, dentro del `<div className="print:hidden">` que ya existe, sin tocar esa envoltura).

- [x] **Step 5: `npx tsc --noEmit` desde `frontend/`**

Expected: sin errores nuevos. Ejecutar también ESLint sobre los archivos modificados. El contrato obligatorio del footer y los cinco callers se migran juntos, sin errores pendientes para tareas posteriores.

- [x] **Step 6: Commit**

```bash
git add "frontend/src/app/[lang]/page.tsx" "frontend/src/app/[lang]/catalogo/page.tsx" "frontend/src/app/[lang]/traslados/page.tsx" frontend/src/components/site-footer.tsx "frontend/src/app/[lang]/deslinde/page.tsx" "frontend/src/app/[lang]/privacidad/page.tsx" "frontend/src/app/[lang]/not-found.tsx" frontend/src/components/checkout-view.tsx frontend/src/components/booking-confirmation.tsx
git commit -m "feat(frontend): SiteFooter con direccion por sede; variante explicita en paginas sin sede propia"
```

---

### Tarea 9: Activar la portada como hub de agencia

**Files:**
- Modify: `frontend/src/app/[lang]/page.tsx`

**Interfaces:**
- Consume: `HubHero` (Tarea 6), `HubMapaSedes` (Tarea 6), `HubGridSedes` (Tarea 6), `HubPorQue` (Tarea 6), `sedesActivas` (Tarea 2), `SEDES_INDICE` de `@/content/sedes-indice`, `getSedeContenido` de `@/content/sedes-cuerpo` (server-only — `page.tsx` es Server Component, así que es seguro), `getSedes` de `@/lib/api`, `dict.hub` (Tarea 6).

- [x] **Step 1: Reescribir el archivo completo**

```tsx
// frontend/src/app/[lang]/page.tsx
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from './dictionaries';
import { alternativasDe } from '@/lib/site';
import { getSedes } from '@/lib/api';
import { sedesActivas } from '@/lib/reconciliar-sedes';
import { SEDES_INDICE } from '@/content/sedes-indice';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import type { SedeContenido } from '@/content/sedes-tipos';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { HubHero } from '@/components/hub-hero';
import { HubMapaSedes } from '@/components/hub-mapa-sedes';
import { HubGridSedes } from '@/components/hub-grid-sedes';
import { HubPorQue } from '@/components/hub-por-que';

const MAPA_ANCHOR_ID = 'hub-mapa-destinos';

export async function generateMetadata({ params }: PageProps<'/[lang]'>): Promise<Metadata> {
  const { lang } = await params;
  if (!hasLocale(lang)) return {};

  const dict = await getDictionary(lang);
  return {
    title: { absolute: dict.hub.meta.title },
    description: dict.hub.meta.description,
    alternates: alternativasDe(lang),
  };
}

export default async function Home({ params }: PageProps<'/[lang]'>) {
  const { lang } = await params;

  if (!hasLocale(lang)) notFound();

  const dict = await getDictionary(lang);
  const sedesApi = await getSedes().then((s) => s, () => null);
  // `sedesActivas` opera solo sobre el indice (client-safe, chico) — para
  // pintar el mapa/grid con foto (`hero.imagen`) hace falta el cuerpo
  // (server-only) de cada sede activa, combinado aqui, server-side.
  const activas = sedesActivas(SEDES_INDICE, sedesApi);
  const sedes = activas
    .map((entrada) => getSedeContenido(entrada.slug, lang))
    .filter((s): s is SedeContenido => s !== undefined);

  return (
    <>
      <SiteHeader lang={lang} nav={dict.nav} variante="hub" />
      <main>
        <HubHero
          nombreAgencia={dict.hub.nombreAgencia}
          mision={dict.hub.mision}
          ctaLabel={dict.hub.ctaElegirDestino}
          mapaAnchorId={MAPA_ANCHOR_ID}
        />

        <section id={MAPA_ANCHOR_ID} className="scroll-mt-24 mx-auto max-w-6xl px-6 py-16 sm:px-8 lg:px-12">
          <HubMapaSedes
            lang={lang}
            sedes={sedes}
            verDestinoLabel={dict.hub.verDestino}
            conLabel={dict.hub.conLabel}
          />
          <div className="mt-12">
            <HubGridSedes
              lang={lang}
              sedes={sedes}
              verDestinoLabel={dict.hub.verDestino}
              conLabel={dict.hub.conLabel}
            />
          </div>
        </section>

        <HubPorQue headline={dict.hub.porQueHeadline} pilares={dict.hub.pilares} />
      </main>
      <SiteFooter
        lang={lang}
        footer={dict.footer}
        nav={dict.nav}
        bookLabel={dict.booking.submit}
        negocio={null}
      />
    </>
  );
}
```

- [x] **Step 2: Verificar integración del hub**

Las Tareas 7 y 8 ya deben estar completadas. Run desde `frontend/`: `npx tsc --noEmit` y `npx eslint "src/app/[lang]/page.tsx"`. Expected: cero errores nuevos, sin excepciones temporales de props. Comprobar que el hub no monta datos estructurados de negocio ni barras/contexto de reserva.

- [x] **Step 3: Commit**

```bash
git add "frontend/src/app/[lang]/page.tsx"
git commit -m "feat(frontend): portada pasa a ser el hub de agencia"
```

---

### Tarea 10: Página completa de sede y datos estructurados

#### A. `StructuredData` — nuevo contrato de props

**Files:**
- Modify: `frontend/src/components/structured-data.tsx`

**Interfaces:**
- Produce: `StructuredDataProps` cambia de `{ lang, dict }` a `{ lang: Locale; slug: string; negocio: SedeNegocio; description: string; faqItems: { q: string; a: string }[] | null }`.

- [ ] **Step 1: Reescribir el componente**

Nota (arch-critic ronda 2, hallazgo 4): la primera versión de este componente armaba `url: absolutaEn(lang)`, sin slug — montado en `/sede/[slug]` eso declara la URL del **hub** como la de la ficha de esa sede. Con `slug` como prop nueva, `url` apunta a la página real de la sede.

```tsx
// frontend/src/components/structured-data.tsx
import type { Locale } from '@/app/[lang]/dictionaries';
import type { SedeNegocio } from '@/content/sedes-tipos';
import { whatsappNumero, tieneWhatsapp } from '@/lib/contacto';
import { absolutaEn } from '@/lib/site';

type StructuredDataProps = {
  lang: Locale;
  /** Slug de la sede que describe este JSON-LD — nunca el hub. */
  slug: string;
  negocio: SedeNegocio;
  description: string;
  faqItems: { q: string; a: string }[] | null;
};

/**
 * JSON-LD para Google: ficha del negocio de la sede y sus preguntas
 * frecuentes. `negocio`/`faqItems` en `null` (spec §9: hoy solo pasa para
 * Los Cabos) hace que el bloque correspondiente no se renderice — sin datos
 * inventados.
 */
export function StructuredData({ lang, slug, negocio, description, faqItems }: StructuredDataProps) {
  const negocioJsonLd = negocio && {
    '@context': 'https://schema.org',
    '@type': 'TouristAttraction',
    name: negocio.nombre,
    description,
    url: absolutaEn(lang, `/sede/${slug}`),
    address: {
      '@type': 'PostalAddress',
      streetAddress: negocio.calle,
      addressLocality: negocio.ciudad,
      addressRegion: negocio.estado,
      addressCountry: negocio.pais,
    },
    ...(tieneWhatsapp ? { telephone: `+${whatsappNumero}` } : {}),
    openingHoursSpecification: {
      '@type': 'OpeningHoursSpecification',
      dayOfWeek: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
      opens: negocio.horarioApertura,
      closes: negocio.horarioCierre,
    },
    availableLanguage: ['es', 'en'],
  };

  const preguntasJsonLd = faqItems && {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqItems.map((item) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: item.a },
    })),
  };

  return (
    <>
      {negocioJsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(negocioJsonLd) }}
        />
      )}
      {preguntasJsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(preguntasJsonLd) }}
        />
      )}
    </>
  );
}
```

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores — tras la Tarea 9, `page.tsx` ya no importa `StructuredData`, así que este archivo queda sin callers hasta integrar la página en el bloque B de esta tarea.

#### B. Página de sede (`/[lang]/sede/[slug]`)

**Files:**
- Create: `frontend/src/app/[lang]/sede/[slug]/page.tsx`

**Interfaces:**
- Consume: casi todo lo anterior — `getSedeContenido` de `@/content/sedes-cuerpo` (Tarea 1, server-only — esta página es Server Component), `SedeHero` (Tarea 5), `AboutSection` (Tarea 5), `SeasonSection`/`IncludedSection`/`LicenseSection`/`GallerySection`/`ReviewsSection`/`FaqSection` (sin cambios), `StructuredData` (Tarea 10, con la prop `slug` nueva), `SiteHeader`/`SiteFooter` (Tareas 7 y 8), `PaqueteCard`/`ServiciosSueltosSection` (Tarea 3), `StickyBookingBar`/`ProveedorReserva` (sin cambios), `getPaquetesSede`/`getServiciosSede` de `@/lib/api`, `getMinBookableDate` de `@/lib/dates`.

- [ ] **Step 2: Resolver ruta, contenido y datos**

Implementar validación de idioma/slug y carga de diccionario/catálogo del ejemplo. Slug inexistente produce `notFound()` sin consultar sedes activas. Preparar `generateMetadata` con canonical por sede.

- [ ] **Step 3: Integrar hero, catálogo y reservas**

Montar `SedeHero`, paquetes, servicios y enlace de traslados. El proveedor y las barras heredadas solo se montan en La Paz. El enlace de traslados conserva el idioma explícitamente.

- [ ] **Step 4: Integrar contenido condicional, SEO y footer**

Montar las secciones de La Paz desde el diccionario; en otras sedes omitirlas. Pasar `slug` a `StructuredData` y `sedeSlug` al footer. El siguiente bloque reúne el resultado de estos tres pasos:

```tsx
// frontend/src/app/[lang]/sede/[slug]/page.tsx
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ArrowRight, Car } from '@phosphor-icons/react/ssr';
import Link from 'next/link';
import { getDictionary, hasLocale } from '../../dictionaries';
import { alternativasDe } from '@/lib/site';
import { getSedeContenido } from '@/content/sedes-cuerpo';
import { getPaquetesSede, getServiciosSede, type Moneda } from '@/lib/api';
import { getMinBookableDate } from '@/lib/dates';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { SedeHero } from '@/components/sede-hero';
import { PaqueteCard } from '@/components/paquete-card';
import { ServiciosSueltosSection } from '@/components/servicios-sueltos-section';
import { AboutSection } from '@/components/about-section';
import { SeasonSection } from '@/components/season-section';
import { IncludedSection } from '@/components/included-section';
import { LicenseSection } from '@/components/license-section';
import { GallerySection } from '@/components/gallery-section';
import { ReviewsSection } from '@/components/reviews-section';
import { FaqSection } from '@/components/faq-section';
import { StructuredData } from '@/components/structured-data';
import { StickyBookingBar } from '@/components/sticky-booking-bar';
import { ProveedorReserva } from '@/components/booking-state';

type PageProps = {
  params: Promise<{ lang: string; slug: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) return {};
  const contenido = getSedeContenido(slug, lang);
  if (!contenido) return {};
  return {
    title: { absolute: contenido.metaTitle },
    description: contenido.metaDescription,
    alternates: alternativasDe(lang, `/sede/${slug}`),
  };
}

export default async function SedePage({ params, searchParams }: PageProps) {
  const { lang, slug } = await params;
  if (!hasLocale(lang)) notFound();

  const contenido = getSedeContenido(slug, lang);
  if (!contenido) notFound();

  const dict = await getDictionary(lang);
  const query = await searchParams;
  const moneda: Moneda =
    typeof query.moneda === 'string' && query.moneda.toUpperCase() === 'USD' ? 'USD' : 'MXN';
  const minDate = getMinBookableDate();

  const [paquetes, servicios] = await Promise.all([
    getPaquetesSede(slug).catch(() => []),
    getServiciosSede(slug).catch(() => []),
  ]);

  // El contenido largo (temporada/incluye/licencia/galeria/resenas/faq) sigue
  // viviendo en el diccionario global — hoy es identico a lo que ya es
  // correcto para la-paz; cualquier otra sede lo recibe en null (spec §4,
  // §6.6-6.8) hasta que tenga su propio contenido real.
  const contenidoLargo =
    slug === 'la-paz'
      ? {
          temporada: dict.season,
          incluye: dict.included,
          licencia: dict.license,
          galeria: dict.gallery,
          resenas: dict.reviews,
          faq: dict.faq,
        }
      : { temporada: null, incluye: null, licencia: null, galeria: null, resenas: null, faq: null };

  const pagina = (
    <>
      <StructuredData
        lang={lang}
        slug={slug}
        negocio={contenido.negocio}
        description={contenido.metaDescription}
        faqItems={contenidoLargo.faq?.items ?? null}
      />
      <SiteHeader lang={lang} nav={dict.nav} variante="sede" sedeSlugActual={slug} />

        <main>
          <SedeHero
            lang={lang}
            sedeSlug={slug}
            contenido={contenido.hero}
            mostrarBookingBar={slug === 'la-paz'}
            destacadas={contenido.destacadas}
            paquetes={paquetes}
            servicios={servicios}
            moneda={moneda}
            booking={dict.booking}
            minDate={minDate}
            verTodoLabel={dict.catalog.selectDestination}
            hrefVerTodo={`/${lang}/sede/${slug}#experiencias`}
          />

          <section id="experiencias" className="scroll-mt-24 mx-auto max-w-6xl px-6 pt-12 sm:px-8 lg:px-12">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-lg font-bold tracking-tight text-foreground sm:text-xl">
                {dict.catalog.title}
              </h2>
              <span className="text-xs text-muted">
                {paquetes.length} {paquetes.length === 1 ? 'paquete' : 'paquetes'}
              </span>
            </div>

            {paquetes.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border bg-card/60 p-12 text-center">
                <p className="text-muted">{dict.catalog.emptyPackages}</p>
              </div>
            ) : (
              <div className="grid gap-8 md:grid-cols-2 items-start">
                {paquetes.map((paquete) => (
                  <PaqueteCard key={paquete.id} paquete={paquete} lang={lang} dict={dict.catalog} moneda={moneda} />
                ))}
              </div>
            )}

            <ServiciosSueltosSection servicios={servicios} lang={lang} dict={dict.catalog} moneda={moneda} />

            {contenido.servicioTransporte && (
              <section className="mt-12 rounded-2xl border border-border bg-card/60 p-6 sm:p-8">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent">
                      <Car size={24} weight="duotone" />
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-foreground sm:text-lg">{dict.traslados.title}</h3>
                      <p className="mt-1 text-xs text-muted leading-relaxed sm:text-sm">{dict.traslados.subtitle}</p>
                    </div>
                  </div>
                  <Link
                    href={`/${lang}${contenido.servicioTransporte.hrefTraslados}`}
                    className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-border bg-surface px-5 py-2.5 text-xs font-semibold text-foreground transition-colors hover:border-accent hover:text-accent sm:self-auto"
                  >
                    <span>{dict.traslados.cta}</span>
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </section>
            )}
          </section>

          <AboutSection
            about={{
              headline: contenido.colaboracion.titulo,
              body1: contenido.colaboracion.texto1,
              body2: contenido.colaboracion.texto2,
              photoHint: contenido.colaboracion.imagenAlt,
            }}
            imagenSrc={contenido.colaboracion.imagenSrc}
            imagenAlt={contenido.colaboracion.imagenAlt}
          />

          {contenidoLargo.temporada && <SeasonSection season={contenidoLargo.temporada} />}
          {contenidoLargo.incluye && <IncludedSection included={contenidoLargo.incluye} />}
          {contenidoLargo.licencia && <LicenseSection nav={dict.nav} license={contenidoLargo.licencia} />}

          {contenido.otrasEmpresas.length > 0 && (
            <section className="mx-auto max-w-6xl px-6 py-16 sm:px-8 lg:px-12">
              <h2 className="text-xl font-bold text-foreground">{dict.hub.conLabel} más en {contenido.negocio?.ciudad ?? contenido.empresaFundadoraNombre}</h2>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                {contenido.otrasEmpresas.map((empresa) => (
                  <a
                    key={empresa.slug}
                    href={empresa.enlaceExterno}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex flex-col gap-1 rounded-xl border border-border bg-card p-4 transition-colors hover:border-accent"
                  >
                    <span className="text-sm font-semibold text-foreground">{empresa.nombre}</span>
                    <span className="text-xs text-muted">{empresa.descripcion}</span>
                  </a>
                ))}
              </div>
            </section>
          )}

          {contenidoLargo.galeria && <GallerySection gallery={contenidoLargo.galeria} />}
          {contenidoLargo.resenas && <ReviewsSection nav={dict.nav} reviews={contenidoLargo.resenas} />}
          {contenidoLargo.faq && <FaqSection faq={contenidoLargo.faq} />}
        </main>

        <SiteFooter
          lang={lang}
          footer={dict.footer}
          nav={dict.nav}
          bookLabel={dict.booking.submit}
          negocio={contenido.negocio}
          sedeSlug={slug}
        />

        {slug === 'la-paz' && <StickyBookingBar lang={lang} booking={dict.booking} minDate={minDate} />}
    </>
  );
  return slug === 'la-paz' ? <ProveedorReserva>{pagina}</ProveedorReserva> : pagina;
}
```

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores nuevos. Revisar que Los Cabos no recibe proveedor/barras ni contenido largo de La Paz, y que `hrefTraslados` genera `/es/traslados?...` o `/en/traslados?...`.

#### Cierre de la tarea

- [ ] **Step 5: Verificación conjunta de la tarea**

Con todos los bloques anteriores integrados, ejecutar desde `frontend/` `npx tsc --noEmit` y ESLint sobre los archivos modificados de esta tarea. Aplicar los criterios descritos en cada bloque; no repetir tipos/lint tras cada cambio mecánico. Conservar las ejecuciones de pruebas en rojo/verde indicadas para la lógica pura. No avanzar si hay errores nuevos.

- [ ] **Step 6: Commit de la tarea completa**

```bash
git add frontend/src/components/structured-data.tsx "frontend/src/app/[lang]/sede/"
git commit -m "feat(frontend): pagina de sede y datos estructurados"
```

---

### Tarea 11: Migración de enlaces, redirecciones y sitemap

#### A. `/catalogo` como stub de redirect

**Files:**
- Modify: `frontend/src/app/[lang]/catalogo/page.tsx` (reemplaza el contenido completo)
- Delete: `frontend/src/app/[lang]/catalogo/loading.tsx`

**Interfaces:**
- Consume: `getSedeIndice` de `@/content/sedes-indice` (solo existencia — no hace falta el cuerpo para decidir a dónde redirigir).

- [x] **Step 1: Reemplazar el archivo completo**

```tsx
// frontend/src/app/[lang]/catalogo/page.tsx
import { redirect } from 'next/navigation';
import { notFound } from 'next/navigation';
import { hasLocale } from '../dictionaries';
import { getSedeIndice } from '@/content/sedes-indice';

type PageProps = {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

/**
 * `/catalogo` ya no tiene contenido propio (spec §9): el selector de sede y
 * los grids de paquetes/servicios viven ahora en el hub y en la pagina de
 * sede. Este stub solo redirige a donde corresponda, para no romper links
 * viejos/externos que todavia apunten aqui.
 */
export default async function CatalogoRedirectPage({ params, searchParams }: PageProps) {
  const { lang } = await params;
  if (!hasLocale(lang)) notFound();

  const query = await searchParams;
  const sedeQuery = typeof query.sede === 'string' ? query.sede : undefined;
  const existe = sedeQuery ? getSedeIndice(sedeQuery) : undefined;

  redirect(existe ? `/${lang}/sede/${sedeQuery}` : `/${lang}`);
}
```

- [x] **Step 2: Borrar `loading.tsx`**

```bash
git rm "frontend/src/app/[lang]/catalogo/loading.tsx"
```

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores.

#### B. Traslados y paquete-checkout — regreso a la sede correcta

**Files:**
- Modify: `frontend/src/app/[lang]/traslados/page.tsx`
- Modify: `frontend/src/components/traslado-view.tsx`
- Modify: `frontend/src/components/paquete-checkout.tsx`

**Interfaces:** el servidor usa `SEDES_INDICE`, `getSedeContenido` de `@/content/sedes-cuerpo`, `sedesActivas` y `getSedes`. `TrasladoView` recibe `sedeSlugActual: string | undefined` (prop requerida, admite ausencia si no existe una sede de retorno). Ningún componente cliente importa el cuerpo ni busca empresas dentro de él.

- [x] **Step 3: Resolver la sede solo en `traslados/page.tsx`**

Agregar los imports de contenido/índice/reconciliación y ampliar el import existente de API con `getSedes`. Después de resolver `empresaSlug` y antes de las ramas de render:

```tsx
const sedeDeTransporte = Object.keys(SEDES_INDICE)
  .map((slug) => getSedeContenido(slug, lang))
  .find((contenido) => contenido?.servicioTransporte?.empresaSlug === empresaSlug);
let sedeSlugActual = sedeDeTransporte?.slug;
if (!sedeSlugActual) {
  const sedesApi = await getSedes().catch(() => null);
  sedeSlugActual = sedesActivas(SEDES_INDICE, sedesApi)[0]?.slug;
}
const hrefVolver = sedeSlugActual ? `/${lang}/sede/${sedeSlugActual}` : `/${lang}`;
```

La búsqueda no importa `SEDES_CONTENIDO` ni `@/content/sedes` (no existen). Si no hay coincidencia, respeta la primera sede activa del spec; red caída usa el índice y una respuesta `[]` lleva al hub. No inventar fallback fijo a La Paz.

- [x] **Step 4: Pasar las props y actualizar ambas ramas**

Rama no disponible: `<SiteHeader lang={lang} nav={dict.nav} variante="sede" sedeSlugActual={sedeSlugActual} />`, link con `href={hrefVolver}` y `SiteFooter` con `sedeSlug={sedeSlugActual}` y `negocio={sedeDeTransporte?.negocio ?? null}`. No adjudicar a una empresa desconocida la dirección de la sede usada solo como fallback de navegación.

Rama normal: añadir `sedeSlugActual={sedeSlugActual}` al montaje de `TrasladoView`. En `TrasladoViewProps`, declarar `sedeSlugActual: string | undefined`, recibirla en el destructuring, pasarla al `SiteHeader` y calcular el mismo `hrefVolver` para su enlace. Mantener intacta la lógica de cotización, reserva y pago.

- [x] **Step 5: Actualizar los seis mounts de `paquete-checkout.tsx` y el regreso**

Usar `<SiteHeader lang={lang} nav={nav} variante="sede" sedeSlugActual={sedeSlug} />` en los seis estados existentes. Cambiar el link de regreso a `/${lang}/sede/${sedeSlug}`; este slug ya es prop del checkout. No tocar contratos de queries ni estados de pago.

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores nuevos. Inspeccionar que el cuerpo de contenido se importa únicamente desde la página de servidor y que ambos regresos comparten la sede calculada.

#### C. `RUTAS`/sitemap con rutas de sede (fallo abierto)

**Files:**
- Modify: `frontend/src/lib/site.ts`
- Modify: `frontend/src/app/sitemap.ts`

**Interfaces:**
- Produce (en `site.ts`): `rutasEstaticas` (renombre de la constante `RUTAS` de hoy, mismo valor), `async function rutasSedes(): Promise<string[]>`.
- Consume: `sedesActivas` de `@/lib/reconciliar-sedes`, `getSedes` de `@/lib/api`.

- [x] **Step 6: `site.ts` — separar rutas estáticas de rutas de sede**

Reemplazar:
```ts
/** Rutas publicas del sitio, la fuente del sitemap y de los canonicals. */
export const RUTAS = ['', '/reservar', '/deslinde', '/privacidad'] as const;
```
por:
```ts
/** Rutas publicas estaticas del sitio (no dependen de que sedes esten activas). */
export const rutasEstaticas = ['', '/reservar', '/deslinde', '/privacidad'] as const;

/**
 * Rutas de sede activas para el sitemap (spec §9): mismo criterio de
 * reconciliacion que el hub — si `getSedes()` falla, fallo abierto (todas
 * las sedes del diccionario), nunca un sitemap mas corto por un error de red.
 */
export async function rutasSedes(): Promise<string[]> {
  const sedesApi = await getSedes().then((s) => s, () => null);
  return sedesActivas(SEDES_INDICE, sedesApi).map((sede) => `/sede/${sede.slug}`);
}
```

Y agregar los imports que faltan (`getSedes` de `./api`, `sedesActivas` de `./reconciliar-sedes`) al principio del archivo — cuidado con el ciclo: `site.ts` ya es importado por `structured-data.tsx`/`sede-selector.tsx`/páginas; `reconciliar-sedes.ts` importa solo tipos de `content/sedes-tipos.ts`, no de `site.ts`. Conservar el import existente de `Locale` en `site.ts`: lo usan otros helpers.

```ts
import { SEDES_INDICE } from '@/content/sedes-indice';
import { getSedes } from './api';
import { sedesActivas } from './reconciliar-sedes';
```

- [x] **Step 7: `sitemap.ts` — volverlo `async` e incluir rutas de sede**

```ts
// frontend/src/app/sitemap.ts
import type { MetadataRoute } from 'next';
import { LOCALES, rutasEstaticas, rutasSedes, absolutaEn } from '@/lib/site';

function entradaDe(lang: (typeof LOCALES)[number], ruta: string, ahora: Date) {
  return {
    url: absolutaEn(lang, ruta),
    lastModified: ahora,
    changeFrequency: ruta === '' ? ('weekly' as const) : ('yearly' as const),
    priority: ruta === '' ? 1 : 0.5,
    alternates: {
      languages: {
        'es-MX': absolutaEn('es', ruta),
        'en-US': absolutaEn('en', ruta),
      },
    },
  };
}

/**
 * Una entrada por pagina y por idioma. Las rutas de sede se agregan por
 * idioma a partir de una sola lista reconciliada (el índice no varía por idioma).
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const ahora = new Date();

  const estaticas = LOCALES.flatMap((lang) =>
    rutasEstaticas.filter((ruta) => ruta !== '/reservar').map((ruta) => entradaDe(lang, ruta, ahora)),
  );

  const rutas = await rutasSedes();
  const deSede = LOCALES.flatMap((lang) =>
    rutas.map((ruta) => entradaDe(lang, ruta, ahora)),
  );

  return [...estaticas, ...deSede];
}
```

**Criterios de verificación del bloque (comprobar al cierre):**

Expected: sin errores. (Si algún otro archivo importaba `RUTAS` por su nombre viejo, este paso lo revela — al momento de escribir este plan, `RUTAS` solo lo usa `sitemap.ts`, ya actualizado arriba.)

#### Cierre de la tarea

- [x] **Step 8: Verificación conjunta de la tarea**

Con todos los bloques anteriores integrados, ejecutar desde `frontend/` `npx tsc --noEmit` y ESLint sobre los archivos modificados de esta tarea. Aplicar los criterios descritos en cada bloque; no repetir tipos/lint tras cada cambio mecánico. Conservar las ejecuciones de pruebas en rojo/verde indicadas para la lógica pura. No avanzar si hay errores nuevos.

- [x] **Step 9: Commit de la tarea completa**

```bash
git add "frontend/src/app/[lang]/catalogo/page.tsx" "frontend/src/app/[lang]/traslados/page.tsx" frontend/src/components/traslado-view.tsx frontend/src/components/paquete-checkout.tsx frontend/src/lib/site.ts frontend/src/app/sitemap.ts
git commit -m "fix(frontend): migrar navegacion y sitemap a sedes"
```

---

### Tarea 12: Verificación integral y entrega

**Files:** ninguno nuevo — solo ejecución.

- [x] **Step 1: Verificación de tipos completa**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errores.

- [x] **Step 2: Lint completo**

Run: `cd frontend && npx eslint .`
Expected: 0 errores (warnings existentes previos al plan, si los hay, no se introducen nuevos).

- [x] **Step 3: Build de producción**

Run: `cd frontend && npm run build`
Expected: build exitoso. Confirmar que `/[lang]/sede/[slug]` y `/[lang]/catalogo` están registradas; no exigir el símbolo de prerender estático: la página de sede lee `searchParams` y puede figurar como dinámica (`ƒ`).

- [x] **Step 4: Correr la suite completa de tests puros (`node --test`) una vez más, todos juntos**

Run (PowerShell, desde `frontend/`):
```powershell
node tests/run-hub-tests.cjs
```
Expected: las seis suites registradas en el runner pasan desde una terminal nueva, incluida `personalizaciones.test.cjs`. No depender de variables heredadas de pasos anteriores.

- [ ] **Step 5: Nota de cierre (no ejecutable por el agente)**

Sin verificación de UI en navegador por política del proyecto. El checklist de smoke visual manual del spec (§11) — hub → pin → sede → chip inline en La Paz, Los Cabos sin BookingBar/temporada/licencia/galería/reseñas/FAQ, redirecciones de `/catalogo`, links de "volver" de traslados/paquete-checkout, anchors del nav desde `/reservar`/`/deslinde`/`/privacidad`, header en `/`, `/sede/la-paz` y `/sede/los-cabos`, `sitemap.xml`, comportamiento con backend caído — queda pendiente para que el dueño lo revise en `localhost` antes de mergear.

- [ ] **Step 6: Commit (si el Step 1-4 generó cambios de limpieza, ej. un fix de lint)**

Solo si hubo cambios; si los 4 pasos anteriores ya estaban en verde desde el commit previo, no hay nada que commitear en este paso.

---

## Verificación de esta corrección documental

Se extrajeron a una copia temporal los módulos puros, los cinco archivos de pruebas nuevos y el runner incluidos en este documento; junto con las pruebas existentes de personalizaciones, pasaron 27 pruebas. Esos módulos y pruebas pasaron ESLint; además, se comprobó la sintaxis de los 20 fragmentos completos TypeScript/TSX. Esta comprobación valida esos ejemplos y su compilación aislada, no el build ni la UI de la futura implementación. No se modificó código de la aplicación durante esta revisión.

## Criterios de cierre para el agente ejecutor

- Arquitectura, File Map, contratos y fragmentos usan los mismos módulos (`sedes-tipos`, `sedes-indice`, `sedes-cuerpo`) y la misma firma `sedesActivas(indice, sedesApi)`.
- `SedeSelector` no consulta API; recibe la lista del header y respeta tanto `[]` como el slug explícito. El header reconcilia también en el hub.
- `traslado-view.tsx` recibe la sede como prop y no importa contenido de servidor; ambos enlaces de retorno se construyen desde esa resolución.
- El footer tiene todos sus callers actualizados y sus anchors apuntan a secciones existentes. No se considera aceptable dejar errores de tipos entre tareas.
- El runner usa los nombres nuevos de tests, resuelve aliases/JSON al compilar, usa imports runtime relativos y configura la salida especial `lib/` de las pruebas existentes de personalizaciones.
- `getSedes()` tiene timeout sin cambiar el comportamiento de reserva/pago de otros callers de `request()`.
- Tipos, lint, build y suites ejecutadas quedan registrados con su resultado real. No marcar el smoke visual del dueño como ejecutado por el agente.

Esta lista define aceptación pendiente. No sustituye resultados de ejecución ni una revisión independiente futura.
