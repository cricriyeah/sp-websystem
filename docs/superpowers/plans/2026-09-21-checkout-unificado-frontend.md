# Checkout unificado — Plan de implementación (frontend)

> **Para agentes:** SUB-SKILL REQUERIDO: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para ejecutar este plan tarea por tarea. Los pasos usan casillas `- [ ]`. Modo del proyecto: **un commit por tarea**, **STOP DURO al cerrar cada sección**, sin push ni merge. **Regla dura de diseño:** toda la construcción visual (Sección 3) se hace con la skill `design-taste-frontend` bajo las pantallas ya aprobadas por el dueño (spec §3); este plan fija comportamiento, props, claves de texto y criterios de aceptación. Los bloques JSX son el esqueleto estructural; las clases de Tailwind son indicativas y reusan los tokens del proyecto (`bg-surface`, `border-border`, `text-muted`, `bg-action`).

**Meta:** una sola pantalla de checkout para paquetes de una o de dos empresas, en `/[lang]/reservar?paquete=…`, con extras agrupados por servicio, noches/fecha/personas definidos por el paquete, USD, N pagos secuenciales que no confunden, y (Sección 5) un aviso "Continuar reservación" que recupera cualquier checkout a medias desde la portada.

**Arquitectura:** lógica pura en `src/lib` (calendario, tarifas, reparto, payloads) con pruebas en el runner que ya existe (`frontend/tests/run-hub-tests.cjs`); hooks de estado y de pago en `src/components/pedido/`; un shell `PedidoPaquete` que compone datos → grupos por servicio → confirmar → pagos, con el mismo layout para N=1 y N=2 (se omiten piezas, no se cambia estructura). Se reutilizan `CheckoutSectionCard`, `CheckoutStepper`, `PeopleStepper`, `DateField`, `TimeField`, `StripePanel`.

**Stack:** Next.js 16.3 (Turbopack), React 19.2, Tailwind 4, `@stripe/react-stripe-js`. Sin dependencias nuevas: la lógica pura se prueba con el runner que el repo ya tiene (`frontend/tests/run-hub-tests.cjs` + `*.test.cjs`).

**Spec:** `docs/superpowers/specs/2026-09-21-checkout-unificado-design.md` (pantallas §3, calendario §5, contrato de API §6, vector de prueba §7).

**Plan hermano:** `2026-09-21-checkout-unificado-backend.md`. **Este plan necesita la Sección 2 del backend cerrada, incluidas las Tareas 2.6 y 2.7 (y, para la Sección 5, la Sección 6 — endpoints de resumen y cancelar)** (catálogo con estancia/personas/anticipo y con los componentes de todas las empresas bajo RLS: sin ellas, en PostgreSQL el catálogo de un paquete de dos empresas omite el traslado y el checkout elegiría el motor equivocado), y la Sección 4 para probar órdenes de punta a punta.

## Restricciones globales

- Next.js 16: lee la guía relevante de `node_modules/next/dist/docs/` antes de tocar rutas/páginas (ver `frontend/AGENTS.md`). `params` y `searchParams` son `Promise`. `middleware.ts` es `proxy.ts`.
- Todo texto visible sale de `dictionaries/{es,en}.json` (ambos). **Turbopack cachea los diccionarios: reinicia `npm run dev` después de editarlos** (falso error `Cannot read properties of undefined`).
- Ninguna cifra hardcodeada: precios, topes, noches y porcentajes salen del catálogo. Los del vector de prueba viven solo en tests.
- No usar `<input type="date">` ni `<select>` nativos: usa `DateField` y `TimeField`.
- Fechas ISO: parsear siempre con `new Date(\`${iso}T00:00:00\`)` (`fromLocalISODate`), formatear con `toLocalISODate`.
- El servidor decide el dinero: la UI muestra totales calculados en el cliente solo como vista previa; el monto real lo devuelve `crear-pago`/`crear-pago` de la orden.
- Verificación sin navegador (regla del proyecto): `npx tsc --noEmit`, `npm run lint`, `npm run build`, `npm test` y un smoke con `curl`. El dueño revisa lo visual; no abrir Chrome.
- Los commits terminan con `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Gate por sección: `npx tsc --noEmit && npm run lint && npm test` en verde; `npm run build` al cerrar Secciones 2, 3 y 4.

## Mapa de archivos

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `frontend/package.json` + `frontend/tests/run-hub-tests.cjs` | modificar | script `test` y registro de las suites nuevas |
| `frontend/src/lib/api.ts` | modificar | tipos del catálogo y de los payloads (anticipo, estancia, personas por componente) |
| `frontend/src/lib/calendario-paquete.ts` (+ `frontend/tests/calendario-paquete.test.cjs`) | crear | espejo TS del calendario del paquete (spec §5) |
| `frontend/src/lib/tarifa-transporte.ts` (+ `frontend/tests/tarifa-transporte.test.cjs`) | crear | espejo TS de la resolución de tarifa de traslado |
| `frontend/src/lib/pedido-paquete.ts` (+ `frontend/tests/pedido-paquete.test.cjs`) | crear | reparto por empresa, extras por servicio, total, anticipo (spec §7) |
| `frontend/src/lib/pedido-payload.ts` (+ `frontend/tests/pedido-payload.test.cjs`) | crear | armado de los payloads de reserva y de orden; zona efectiva del traslado |
| `frontend/src/lib/booking-href.ts` (+ `frontend/tests/booking-href.test.cjs`, ya existente) | modificar | una sola URL de reserva de paquete |
| `frontend/src/lib/pedido-estado.ts` (+ `frontend/tests/pedido-estado.test.cjs`) | crear | reducer puro del estado del pedido |
| `frontend/src/components/pedido/use-pedido-estado.ts` | crear | hook delgado sobre el reducer |
| `frontend/src/components/pedido/use-pago-pedido.ts` | crear | envío, pagos secuenciales, reanudación y captura |
| `frontend/src/components/pedido/grupo-servicio.tsx` | crear | detalles + personas + extras de UN servicio |
| `frontend/src/components/pedido/encabezado-pago.tsx` | crear | progreso, pagos hechos ✓ y sujeto del pago actual (R2, R4, R5) |
| `frontend/src/components/pedido/aviso-cargos.tsx` | crear | aviso de N cargos que suman el total (R4) |
| `frontend/src/components/pedido/pedido-paquete.tsx` | crear | shell: compone todo, mismo layout para N=1 y N=2 |
| `frontend/src/components/stripe-panel.tsx` | modificar | ranuras opcionales (aviso, encabezado de pago, etiqueta del botón) y switches de forma de pago/código |
| `frontend/src/app/[lang]/reservar/page.tsx` | modificar | con `?paquete=` monta `PedidoPaquete` (Tarea 3.5); sin él, `CheckoutView` como hoy |
| `frontend/src/app/[lang]/reservar-paquete/` | borrar | ruta y componente `paquete-checkout.tsx` obsoletos |
| `frontend/src/components/checkout-view.tsx` | modificar | quita la rama de paquete; respeta `permite_anticipo` en servicios sueltos |
| `frontend/src/app/[lang]/dictionaries/{es,en}.json` | modificar | claves `pedido.*`; quitar `meta.reservarPaquete` |
| `frontend/src/lib/pendientes.ts` (+ tests) | crear | puntero de checkouts pendientes en localStorage (Sección 5) |
| `frontend/src/lib/pendientes-texto.ts` (+ tests) | crear | matriz de textos de "Continuar reservación" (spec §10.1) |
| `frontend/src/components/continuar-reservacion.tsx` | crear | banda/chip "Continuar reservación" |
| `frontend/CLAUDE.md` | modificar | documentar el checkout unificado |

<!-- arch-critic: APPROVED (revisión adversarial hecha inline por política del proyecto, sin subagente; hallazgos abajo) -->

**Revisión de arquitectura (adversarial, inline).**
1. *Dos motores, una UI:* paquete de una empresa usa `guardarReserva`+`crearPago` (conserva anticipo, código promocional y captcha); paquete de dos empresas usa `crearOrden`+`crearPagoOrden` (captura manual). La diferencia vive **solo** en `use-pago-pedido.ts`; el shell y los componentes no ramifican por motor, ramifican por `pagos.length`.
2. *Divergencia cliente/servidor:* la aritmética de fechas y el reparto se replican en TS; el riesgo se cubre con el **vector de prueba compartido** (spec §7) en los tests de ambos lados y porque el servidor recalcula todo.
3. *`StripePanel` como cuello de botella:* se extiende con props opcionales de default idéntico al comportamiento actual, para que `CheckoutView` y `TrasladoView` no cambien.
4. *Estado de recuperación:* `sessionStorage` guarda `checkoutId`/`ordenId`/`reservaId`; una recarga a mitad de la secuencia reconstruye el paso correcto desde el servidor (`getOrden`/`getEstadoReserva`), nunca desde el navegador.
5. *Riesgo de ramas muertas:* al eliminar `/reservar-paquete` y la rama de paquete de `CheckoutView` se borra también código huérfano (Tarea 4.2); se verifica con `tsc` y `lint`.
6. *Pruebas:* el repo ya tiene un runner (`frontend/tests/run-hub-tests.cjs`, compila con `typescript` y corre `node --test`); las pruebas nuevas se registran ahí y solo cubren lógica pura en `src/lib` con imports relativos (el JS emitido no resuelve `@/`). No se añade ninguna dependencia.

**Revisión externa (2026-09-21, otro agente) — correcciones ya aplicadas a este plan:** (1) el repo ya tenía runner de pruebas: se quita `tsx` y se usa el existente (1.1-1.4, 3.1); (2) `hrefPaquete` ya no depende de `rutaConQuery`, que solo existe en cambios sin commitear del hub, y se actualiza la suite vieja `frontend/tests/booking-href.test.cjs` que exigía `/reservar-paquete` (2.1, 4.1); (3) el hook de pago reanuda y confirma también el motor de una empresa (solo `pagada` es éxito) y no escribe refs en el render (3.2); (4) zona efectiva del traslado en cálculo y payload (1.3, 1.4, 3.4); (5) extras sin precio en la moneda elegida se deshabilitan (3.4); (6) los textos de garantía monetaria ya no prometen "no se te cobra" en absoluto (3.4); (7) dependencia explícita de las Tareas 2.6 y 2.7 del backend.

---

## Sección 0 — Preparación

### Tarea 0.1: Entorno y línea base

**Files:** ninguno.

- [ ] **Paso 1:** trabaja en el worktree `checkout-unificado` creado en la Tarea 0.1 del plan de backend. Si aún no existe, créalo como allí se indica.
- [ ] **Paso 2: dependencias.**

```bash
cd .claude/worktrees/checkout-unificado/frontend
npm ci
```
- [ ] **Paso 3: línea base.**

```bash
npx tsc --noEmit && npm run lint && npm run build
```
Esperado: los tres terminan sin errores. Anota advertencias existentes para no confundirlas con las tuyas. Si algo falla, detente y repórtalo.
- [ ] **Paso 4: leer la guía de Next** relevante a rutas y `searchParams` en `node_modules/next/dist/docs/` (una vez, antes de la Sección 2).

---

## Sección 1 — Contrato y lógica pura

### Tarea 1.1: Runner de pruebas y tipos del contrato

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/lib/api.ts` (tipos `ServicioCatalogo` ≈ L305, `PaqueteServicioCatalogo`, `PaqueteCatalogo`, `ReservaInput` ≈ L55-L85, `ComponenteOrdenInput` ≈ L385-L400)

**Interfaces:**
- Produces (tipos): ver Paso 3. Todas las tareas siguientes los consumen.

- [ ] **Paso 1: usar el runner que ya existe (sin dependencias nuevas).** El repo ya tiene pruebas de lógica pura: `frontend/tests/*.test.cjs` y `frontend/tests/run-hub-tests.cjs`, que compila con `typescript` las entradas de su tabla `suites` y corre `node --test` sobre el JS emitido. Cada prueba nueva se escribe como `.test.cjs`, carga el módulo compilado desde una variable de entorno y se **registra** en la tabla `suites` de `run-hub-tests.cjs` (cada tarea registra la suya cuando nace su módulo; el runner falla si una entrada apunta a un archivo que no existe). Forma de una entrada nueva (ejemplo de la Tarea 1.2):

```js
  'calendario-paquete': ['src/lib/calendario-paquete.ts', 'CALENDARIO_TEST_OUT'],
```
y de una prueba:

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const c = require(path.join(process.env.CALENDARIO_TEST_OUT, 'lib/calendario-paquete.js'));
```
Reglas para que compile y corra: los módulos probados viven en `src/lib/`, **importan solo con rutas relativas** (el JS emitido no resuelve el alias `@/`) y los tipos con `import type`. Añade a `package.json` el script `"test": "node tests/run-hub-tests.cjs"` (corre **todas** las suites, incluidas las existentes; para una sola: `node tests/run-hub-tests.cjs calendario-paquete`).

- [ ] **Paso 2: verificar el runner en la base.**

```bash
npm test
```
Esperado: las suites existentes pasan. Si alguna ya falla en la base (por ejemplo por depender de cambios del hub que esta rama no tiene), anótalo y no la mezcles con tu trabajo; en ese caso ejecuta solo las tuyas por nombre.

- [ ] **Paso 3: tipos.** En `src/lib/api.ts`:

En `ServicioCatalogo` añade:
```ts
  permite_anticipo: boolean;
  porcentaje_anticipo: number;
```
En `PaqueteServicioCatalogo` añade:
```ts
  dia_estancia: number;
  noches: number | null;
  personas_incluidas: number;
```
En `PaqueteCatalogo` añade:
```ts
  permite_anticipo: boolean;   // efectivo: false si el paquete es de dos empresas
  porcentaje_anticipo: number;
  es_cruza_empresa: boolean;
  noches: number | null;
```
En `ReservaInput` añade (y **quita** el uso de `fecha_salida` para paquetes: sigue existiendo para hospedaje suelto):
```ts
  // Paquete de una sola empresa: cuántas personas van a cada servicio, por id de
  // servicio. `numero_personas` es el del componente operativo principal.
  personas_por_servicio?: Record<string, number>;
```
y en `Reserva` (la respuesta) añade `fecha_inicio_paquete?: string;`.
Reemplaza `ComponenteOrdenInput` por:
```ts
export type ComponenteOrdenInput = {
  servicio: string | number;
  hora?: string;
  numero_personas?: number;
  tipo_traslado?: TipoTraslado;
  punto_encuentro?: number | null;
  direccion_personalizada?: string;
  zona?: Zona | '';
  // Solo si el paquete no incluye hospedaje; con hospedaje la define el paquete.
  fecha_regreso?: string | null;
  personalizaciones?: { id: number; cantidad?: number; respuesta?: string }[];
};
```
En `CrearOrdenInput` deja `fecha` (inicio del paquete) y elimina `numero_personas`, `tipo_traslado`, `punto_encuentro`, `direccion_personalizada`, `zona` y `fecha_regreso` de primer nivel (ahora viajan por componente).

- [ ] **Paso 4: verificar.** `npx tsc --noEmit` va a marcar los usos viejos en `paquete-checkout.tsx` y `checkout-view.tsx`; ese código se reemplaza/limpia en las Secciones 3 y 4. **Para no dejar el árbol en rojo entre commits**, en este paso deja a `paquete-checkout.tsx` compilando con un cast temporal `as unknown as CrearOrdenInput` en su `payload` y elimina el cast en la Tarea 4.1 cuando se borre el archivo.

```bash
npx tsc --noEmit && npm run lint && npm test
```

- [ ] **Paso 5: Commit**

```bash
git add frontend/package.json frontend/tests/run-hub-tests.cjs frontend/src/lib/api.ts frontend/src/components/paquete-checkout.tsx
git commit -m "feat(frontend): script de pruebas y tipos del contrato de paquetes"
```

### Tarea 1.2: Calendario del paquete (espejo TS)

**Files:**
- Create: `frontend/src/lib/calendario-paquete.ts`
- Modify: `frontend/tests/run-hub-tests.cjs` (registra `'calendario-paquete'`)
- Test: `frontend/tests/calendario-paquete.test.cjs`

**Interfaces:**
- Produces: `fechaDeComponente(inicio: string, diaEstancia: number): string`, `nochesDelPaquete(componentes): number | null`, `fechaSalida(inicio: string, componentes): string | null`, `sumarDias(iso: string, dias: number): string`, tipo `ComponenteCalendario`.

- [ ] **Paso 1: prueba que falla.** Registra la suite en `frontend/tests/run-hub-tests.cjs` (`'calendario-paquete': ['src/lib/calendario-paquete.ts', 'CALENDARIO_TEST_OUT'],`) y crea `frontend/tests/calendario-paquete.test.cjs` (mismo vector que el backend, spec §5):

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const c = require(path.join(process.env.CALENDARIO_TEST_OUT, 'lib/calendario-paquete.js'));

const PESCA_DIA_2 = { dia_estancia: 2, estrategia_cupo: 'por_recurso_dia', noches: null };
const HOTEL_3 = { dia_estancia: 1, estrategia_cupo: 'por_noche', noches: 3 };
const INICIO = '2026-10-10';

test('suma días cruzando de mes', () => {
  assert.equal(c.sumarDias('2026-10-30', 3), '2026-11-02');
});

test('noches del paquete salen del hospedaje', () => {
  assert.equal(c.nochesDelPaquete([PESCA_DIA_2, HOTEL_3]), 3);
  assert.equal(c.nochesDelPaquete([PESCA_DIA_2]), null);
});

test('la fecha de cada componente cuenta desde el día 1', () => {
  assert.equal(c.fechaDeComponente(INICIO, 1), '2026-10-10');
  assert.equal(c.fechaDeComponente(INICIO, 2), '2026-10-11');
});

test('la salida es inicio + noches; sin hospedaje no hay salida', () => {
  assert.equal(c.fechaSalida(INICIO, [PESCA_DIA_2, HOTEL_3]), '2026-10-13');
  assert.equal(c.fechaSalida(INICIO, [PESCA_DIA_2]), null);
});
```

- [ ] **Paso 2: verla fallar** — `npm test` → error `Cannot find module './calendario-paquete'`.

- [ ] **Paso 3: implementar** — `frontend/src/lib/calendario-paquete.ts`:

```ts
import { fromLocalISODate, toLocalISODate } from './dates';

/**
 * Espejo de backend/apps/fleet/calendario_paquete.py. Es solo vista previa: el
 * servidor recalcula todas las fechas y rechaza las que mande el cliente. El
 * vector de prueba compartido está en el spec §5/§7.
 */
export type ComponenteCalendario = {
  dia_estancia: number;
  estrategia_cupo: string;
  noches: number | null;
};

export function sumarDias(iso: string, dias: number): string {
  const fecha = fromLocalISODate(iso);
  fecha.setDate(fecha.getDate() + dias);
  return toLocalISODate(fecha);
}

export function nochesDelPaquete(componentes: ComponenteCalendario[]): number | null {
  return componentes.find((c) => c.estrategia_cupo === 'por_noche')?.noches ?? null;
}

export function fechaDeComponente(inicio: string, diaEstancia: number): string {
  return sumarDias(inicio, diaEstancia - 1);
}

export function fechaSalida(inicio: string, componentes: ComponenteCalendario[]): string | null {
  const noches = nochesDelPaquete(componentes);
  return noches ? sumarDias(inicio, noches) : null;
}
```

- [ ] **Paso 4: verla pasar y commit**

```bash
node tests/run-hub-tests.cjs calendario-paquete && npx tsc --noEmit
git add frontend/src/lib/calendario-paquete.ts frontend/tests/calendario-paquete.test.cjs frontend/tests/run-hub-tests.cjs
git commit -m "feat(frontend): calendario del paquete (espejo del backend)"
```

### Tarea 1.3: Tarifa de traslado y reparto del pedido

**Files:**
- Create: `frontend/src/lib/tarifa-transporte.ts`, `frontend/src/lib/pedido-paquete.ts`
- Modify: `frontend/tests/run-hub-tests.cjs` (registra `'tarifa-transporte'` y `'pedido-paquete'`)
- Test: `frontend/tests/tarifa-transporte.test.cjs`, `frontend/tests/pedido-paquete.test.cjs`

**Interfaces:**
- Produces:
  - `type Tarifa = TrasladosCatalogo['tarifas'][number]`; `resolverTarifa(tarifas: Tarifa[], tipo: TipoTraslado, zona: Zona | '', personas: number): Tarifa | null`; `precioTarifa(t: Tarifa, moneda: Moneda): number | null`.
  - `type SeleccionComponente = { personas: number; extras: SeleccionPersonalizacion[]; traslado?: { tipo: TipoTraslado; zona: Zona | '' } }`.
  - `type CargoEmpresa = { empresaSlug: string; monto: number; extras: number }`; `type ResultadoPedido = { cargos: CargoEmpresa[]; total: number }`.
  - `calcularPedido(paquete: PaqueteCatalogo, selecciones: Record<string, SeleccionComponente>, moneda: Moneda, tarifasPorEmpresa: Record<string, Tarifa[]>): ResultadoPedido | null` (`selecciones` indexado por **slug de servicio**; `null` si falta un precio, la tarifa o la selección de un componente; la `zona` de `traslado` que recibe es la **efectiva** — ver `zonaEfectivaDeTraslado` en 1.4 —, no la cruda).
  - `usdDisponible(paquete: PaqueteCatalogo, tarifasPorEmpresa: Record<string, Tarifa[]>): boolean`.
  - `montoInicial(total: number, formaPago: 'completo' | 'anticipo', porcentaje: number): number`.

- [ ] **Paso 1: pruebas que fallan.** Registra dos suites en `frontend/tests/run-hub-tests.cjs`:

```js
  'tarifa-transporte': ['src/lib/tarifa-transporte.ts', 'TARIFA_TEST_OUT'],
  'pedido-paquete': ['src/lib/pedido-paquete.ts', 'PEDIDO_PAQUETE_TEST_OUT'],
```
`frontend/tests/tarifa-transporte.test.cjs`:

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const t = require(path.join(process.env.TARIFA_TEST_OUT, 'lib/tarifa-transporte.js'));

const T = (over) => ({
  tipo_traslado: 'redondo_aeropuerto', zona: '', personas_min: 1, personas_max: null,
  precio: '4500.00', precio_usd: '250.00', ...over,
});

test('elige por tipo, zona y rango de personas', () => {
  const tarifas = [
    T({ personas_max: 4, precio: '4500.00' }),
    T({ personas_min: 5, precio: '6000.00' }),
    T({ tipo_traslado: 'redondo_actividad', zona: 'centro', precio: '1500.00' }),
  ];
  assert.equal(t.resolverTarifa(tarifas, 'redondo_aeropuerto', '', 4).precio, '4500.00');
  assert.equal(t.resolverTarifa(tarifas, 'redondo_aeropuerto', '', 5).precio, '6000.00');
  assert.equal(t.resolverTarifa(tarifas, 'redondo_actividad', 'centro', 2).precio, '1500.00');
  assert.equal(t.resolverTarifa(tarifas, 'redondo_actividad', 'periferia', 2), null);
});

test('precio por moneda; sin precio USD devuelve null', () => {
  assert.equal(t.precioTarifa(T({}), 'MXN'), 4500);
  assert.equal(t.precioTarifa(T({}), 'USD'), 250);
  assert.equal(t.precioTarifa(T({ precio_usd: null }), 'USD'), null);
});
```
`frontend/tests/pedido-paquete.test.cjs` (vector del spec §7):

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PEDIDO_PAQUETE_TEST_OUT, 'lib/pedido-paquete.js'));

const check = (id, precio, precioUsd) => ({
  id, personalizacion_id: id, nombre: `extra-${id}`, tipo: 'amenidad', tipo_interaccion: 'check',
  opciones_seleccion: [], aviso_reforzado: false, cobrar_por_persona: false, cantidad_editable: false,
  precio, precio_usd: precioUsd, obligatorio: false, preseleccionado: false,
});

const servicio = (slug, empresa, tipo, extras) => ({
  id: 1, servicio_id: 1, orden: 1, dia_estancia: 1, noches: null, personas_incluidas: 3,
  servicio: { slug, empresa_slug: empresa, tipo_servicio: tipo, personalizaciones: extras },
});

const PAQUETE = {
  empresa_lider_slug: 'sal-y-sol', precio_ancla: '7500.00', precio_ancla_usd: '450.00',
  servicios_asociados: [
    servicio('pesca', 'sal-y-sol', 'pesca', [check(10, '400.00', '23.00')]),
    servicio('traslado', 'transportes-la-paz', 'transporte', [check(20, '150.00', '9.00')]),
  ],
};

const TARIFAS = {
  'transportes-la-paz': [
    { tipo_traslado: 'redondo_actividad', zona: 'centro', personas_min: 1, personas_max: null, precio: '1500.00', precio_usd: '90.00' },
  ],
};

const SELECCIONES = {
  pesca: { personas: 2, extras: [{ id: 10 }] },
  traslado: { personas: 2, extras: [{ id: 20 }], traslado: { tipo: 'redondo_actividad', zona: 'centro' } },
};

test('vector del spec en MXN: 6,400 + 1,650 = 8,050', () => {
  const r = p.calcularPedido(PAQUETE, SELECCIONES, 'MXN', TARIFAS);
  assert.deepEqual(r.cargos.map((c) => [c.empresaSlug, c.monto]), [
    ['sal-y-sol', 6400],
    ['transportes-la-paz', 1650],
  ]);
  assert.equal(r.total, 8050);
});

test('vector en USD: 383 + 99 = 482', () => {
  const r = p.calcularPedido(PAQUETE, SELECCIONES, 'USD', TARIFAS);
  assert.deepEqual(r.cargos.map((c) => c.monto), [383, 99]);
  assert.equal(r.total, 482);
});

test('sin extras la líder absorbe solo el residuo', () => {
  const sel = { pesca: { personas: 2, extras: [] }, traslado: { ...SELECCIONES.traslado, extras: [] } };
  const r = p.calcularPedido(PAQUETE, sel, 'MXN', TARIFAS);
  assert.deepEqual(r.cargos.map((c) => c.monto), [6000, 1500]);
});

test('devuelve null si falta una tarifa, un precio en la moneda o la zona correcta', () => {
  assert.equal(p.calcularPedido(PAQUETE, SELECCIONES, 'MXN', {}), null);
  const sinUsd = { 'transportes-la-paz': [{ ...TARIFAS['transportes-la-paz'][0], precio_usd: null }] };
  assert.equal(p.calcularPedido(PAQUETE, SELECCIONES, 'USD', sinUsd), null);
  // La zona que llega aquí es la EFECTIVA (la del hotel para redondo_actividad); '' no encuentra tarifa de zona.
  const sinZona = { ...SELECCIONES, traslado: { ...SELECCIONES.traslado, traslado: { tipo: 'redondo_actividad', zona: '' } } };
  assert.equal(p.calcularPedido(PAQUETE, sinZona, 'MXN', TARIFAS), null);
});

test('un extra sin precio en USD hace que el pedido en USD no se pueda calcular', () => {
  const paquete = {
    ...PAQUETE,
    servicios_asociados: [servicio('pesca', 'sal-y-sol', 'pesca', [check(10, '400.00', null)])],
  };
  assert.equal(p.calcularPedido(paquete, { pesca: { personas: 2, extras: [{ id: 10 }] } }, 'USD', {}), null);
  assert.equal(p.calcularPedido(paquete, { pesca: { personas: 2, extras: [] } }, 'USD', {}).total, 450);
});

test('paquete de una sola empresa: un solo cargo = ancla + extras', () => {
  const mono = {
    empresa_lider_slug: 'sal-y-sol', precio_ancla: '9500.00', precio_ancla_usd: null,
    servicios_asociados: [servicio('pesca', 'sal-y-sol', 'pesca', [check(10, '400.00', '23.00')])],
  };
  const r = p.calcularPedido(mono, { pesca: { personas: 2, extras: [{ id: 10 }] } }, 'MXN', {});
  assert.deepEqual(r.cargos.map((c) => [c.empresaSlug, c.monto]), [['sal-y-sol', 9900]]);
  assert.equal(p.calcularPedido(mono, { pesca: { personas: 2, extras: [] } }, 'USD', {}), null);
});

test('USD solo se ofrece si TODOS los precios existen', () => {
  assert.equal(p.usdDisponible(PAQUETE, TARIFAS), true);
  assert.equal(p.usdDisponible({ ...PAQUETE, precio_ancla_usd: null }, TARIFAS), false);
});

test('anticipo: porcentaje del total; completo es el total', () => {
  assert.equal(p.montoInicial(9500, 'anticipo', 50), 4750);
  assert.equal(p.montoInicial(9500, 'completo', 50), 9500);
  assert.equal(p.montoInicial(1000, 'anticipo', 33), 330);
});
```

- [ ] **Paso 2: verlas fallar** — `npm test` → errores de módulo inexistente.

- [ ] **Paso 3: implementar `tarifa-transporte.ts`:**

```ts
import type { Moneda, TipoTraslado, TrasladosCatalogo, Zona } from './api';

export type Tarifa = TrasladosCatalogo['tarifas'][number];

/** Espejo de backend/apps/fleet/tarifa_transporte.py::resolver_tarifa_transporte. */
export function resolverTarifa(
  tarifas: Tarifa[],
  tipo: TipoTraslado,
  zona: Zona | '',
  personas: number,
): Tarifa | null {
  return (
    tarifas.find(
      (t) =>
        t.tipo_traslado === tipo &&
        t.zona === (zona || '') &&
        personas >= t.personas_min &&
        (t.personas_max === null || personas <= t.personas_max),
    ) ?? null
  );
}

export function precioTarifa(tarifa: Tarifa, moneda: Moneda): number | null {
  const crudo = moneda === 'USD' ? tarifa.precio_usd : tarifa.precio;
  if (crudo === null || crudo === undefined || !Number.isFinite(Number(crudo))) return null;
  return Number(crudo);
}
```
**`pedido-paquete.ts`:**

```ts
import type { Moneda, PaqueteCatalogo, TipoTraslado, Zona } from './api';
import { totalPersonalizaciones, type SeleccionPersonalizacion } from './personalizaciones';
import { precioTarifa, resolverTarifa, type Tarifa } from './tarifa-transporte';

/**
 * Vista previa del reparto por empresa (el servidor lo recalcula: ver
 * backend/apps/payments/pricing.py::monto_por_empresa y CrearPagoOrdenView).
 * Regla: el traslado de otra empresa va a su tarifa; la líder absorbe el residuo
 * del precio del paquete; a cada empresa se le suman los extras de SUS servicios.
 */
export type SeleccionComponente = {
  personas: number;
  extras: SeleccionPersonalizacion[];
  traslado?: { tipo: TipoTraslado; zona: Zona | '' };
};

export type CargoEmpresa = { empresaSlug: string; monto: number; extras: number };
export type ResultadoPedido = { cargos: CargoEmpresa[]; total: number };

const centavos = (n: number) => Math.round(n * 100);

function precioAncla(paquete: PaqueteCatalogo, moneda: Moneda): number | null {
  const crudo = moneda === 'USD' ? paquete.precio_ancla_usd : paquete.precio_ancla;
  if (crudo === null || crudo === undefined || crudo === '' || !Number.isFinite(Number(crudo))) return null;
  return Number(crudo);
}

export function calcularPedido(
  paquete: PaqueteCatalogo,
  selecciones: Record<string, SeleccionComponente>,
  moneda: Moneda,
  tarifasPorEmpresa: Record<string, Tarifa[]>,
): ResultadoPedido | null {
  const ancla = precioAncla(paquete, moneda);
  if (ancla === null) return null;

  const lider = paquete.empresa_lider_slug;
  const extrasPorEmpresa = new Map<string, number>();
  const fijosPorEmpresa = new Map<string, number>();
  const orden: string[] = [];

  for (const componente of paquete.servicios_asociados) {
    const servicio = componente.servicio;
    const seleccion = selecciones[servicio.slug];
    if (!seleccion) return null;

    const totalExtras = totalPersonalizaciones(
      servicio.personalizaciones, seleccion.extras, seleccion.personas, moneda,
    );
    if (totalExtras === null) return null;

    const empresa = servicio.empresa_slug;
    if (!orden.includes(empresa)) orden.push(empresa);
    extrasPorEmpresa.set(empresa, (extrasPorEmpresa.get(empresa) ?? 0) + centavos(totalExtras));

    if (empresa !== lider) {
      // v1: lo único que puede ser de otra empresa es el traslado, y su parte es su tarifa.
      if (servicio.tipo_servicio !== 'transporte' || !seleccion.traslado) return null;
      const tarifa = resolverTarifa(
        tarifasPorEmpresa[empresa] ?? [], seleccion.traslado.tipo, seleccion.traslado.zona, seleccion.personas,
      );
      const precio = tarifa ? precioTarifa(tarifa, moneda) : null;
      if (precio === null) return null;
      fijosPorEmpresa.set(empresa, (fijosPorEmpresa.get(empresa) ?? 0) + centavos(precio));
    }
  }

  const fijos = [...fijosPorEmpresa.values()].reduce((suma, c) => suma + c, 0);
  const residuo = centavos(ancla) - fijos;
  if (residuo < 0) return null;

  const cargos: CargoEmpresa[] = orden
    .sort((a, b) => Number(b === lider) - Number(a === lider))
    .map((empresa) => {
      const base = empresa === lider ? residuo : (fijosPorEmpresa.get(empresa) ?? 0);
      const extras = extrasPorEmpresa.get(empresa) ?? 0;
      return { empresaSlug: empresa, monto: (base + extras) / 100, extras: extras / 100 };
    });

  return { cargos, total: cargos.reduce((suma, c) => suma + centavos(c.monto), 0) / 100 };
}

/** USD solo se ofrece si el paquete y cada traslado incluido tienen precio en USD. */
export function usdDisponible(paquete: PaqueteCatalogo, tarifasPorEmpresa: Record<string, Tarifa[]>): boolean {
  if (precioAncla(paquete, 'USD') === null) return false;
  return paquete.servicios_asociados.every((componente) => {
    if (componente.servicio.tipo_servicio !== 'transporte') return true;
    const tarifas = tarifasPorEmpresa[componente.servicio.empresa_slug] ?? [];
    return tarifas.length > 0 && tarifas.every((t) => precioTarifa(t, 'USD') !== null);
  });
}

export function montoInicial(total: number, formaPago: 'completo' | 'anticipo', porcentaje: number): number {
  if (formaPago === 'completo') return total;
  return Math.round(centavos(total) * (porcentaje / 100)) / 100;
}
```

- [ ] **Paso 4: verlas pasar y commit**

```bash
node tests/run-hub-tests.cjs tarifa-transporte pedido-paquete && npx tsc --noEmit && npm run lint
git add frontend/src/lib frontend/tests
git commit -m "feat(frontend): reparto por empresa, tarifas de traslado y anticipo (vector del spec)"
```

### Tarea 1.4: Payloads de reserva y de orden

**Files:**
- Create: `frontend/src/lib/pedido-payload.ts`
- Modify: `frontend/tests/run-hub-tests.cjs` (registra `'pedido-payload'`)
- Test: `frontend/tests/pedido-payload.test.cjs`

**Interfaces:**
- Consumes: tipos de `api.ts` (1.1) y `SeleccionPersonalizacion` de `personalizaciones.ts`.
- Produces:
  - `type DatosContacto = { fullName: string; phone: string; email: string }`.
  - `type DetalleTraslado = { tipo: TipoTraslado; modo: 'catalogo' | 'personalizada'; puntoEncuentroId: number | null; direccion: string; zonaLibre: Zona | ''; fechaRegreso: string | null }`.
  - `type ComponentePedido = { personas: number; extras: SeleccionPersonalizacion[]; traslado?: DetalleTraslado }`.
  - `zonaEfectivaDeTraslado(t: DetalleTraslado, zonaDePunto: (id: number | null) => Zona | ''): Zona | ''` — misma regla que `DetalleTransporte.zona_efectiva()` del backend: `''` salvo `redondo_actividad`; en ese tipo, la zona del hotel del catálogo o, si es dirección libre, la elegida.
  - `personasPrincipales(paquete, componentes): number`.
  - `armarPayloadOrden(args): CrearOrdenInput`, `armarPayloadReserva(args): ReservaInput`.

- [ ] **Paso 1: pruebas que fallan.** Registra la suite: `'pedido-payload': ['src/lib/pedido-payload.ts', 'PEDIDO_PAYLOAD_TEST_OUT'],`. `frontend/tests/pedido-payload.test.cjs`:

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PEDIDO_PAYLOAD_TEST_OUT, 'lib/pedido-payload.js'));

const svc = (id, slug, empresa, tipo, estrategia, extra = {}) => ({
  id, servicio_id: id, orden: id, dia_estancia: 1, noches: null, personas_incluidas: 3,
  servicio: { id, slug, empresa_slug: empresa, tipo_servicio: tipo, estrategia_cupo: estrategia, personalizaciones: [] },
  ...extra,
});

const CRUZA = {
  slug: 'pesca-traslado', empresa_lider_slug: 'sal-y-sol', noches: null,
  servicios_asociados: [
    svc(1, 'pesca', 'sal-y-sol', 'pesca', 'por_recurso_dia'),
    svc(2, 'traslado', 'transportes-la-paz', 'transporte', 'bajo_demanda'),
  ],
};

const traslado = (over = {}) => ({
  tipo: 'redondo_actividad', modo: 'catalogo', puntoEncuentroId: 7, direccion: '', zonaLibre: '', fechaRegreso: null, ...over,
});

const COMPONENTES = {
  pesca: { personas: 2, extras: [{ id: 10 }] },
  traslado: { personas: 3, extras: [{ id: 20 }], traslado: traslado() },
};

const BASE = {
  checkoutId: 'chk-1', inicio: '2026-10-15', hora: '07:00', moneda: 'MXN',
  contacto: { fullName: ' Ana Ruiz ', phone: ' 6121234567 ', email: 'ana@example.com' },
  ref: 'amigo', zonaDePunto: () => 'centro',
};

test('zona efectiva: solo cuenta en redondo_actividad', () => {
  const zona = () => 'periferia';
  assert.equal(p.zonaEfectivaDeTraslado(traslado(), zona), 'periferia');
  assert.equal(p.zonaEfectivaDeTraslado(traslado({ modo: 'personalizada', zonaLibre: 'centro' }), zona), 'centro');
  assert.equal(p.zonaEfectivaDeTraslado(traslado({ tipo: 'redondo_aeropuerto' }), zona), '');
  assert.equal(p.zonaEfectivaDeTraslado(traslado({ tipo: 'recepcion_aeropuerto' }), zona), '');
});

test('la orden manda un inicio, personas y extras por componente, sin fechas por servicio', () => {
  const r = p.armarPayloadOrden({ ...BASE, paquete: CRUZA, componentes: COMPONENTES });
  assert.equal(r.fecha, '2026-10-15');
  assert.equal(r.deslinde_nombre, 'Ana Ruiz');
  assert.deepEqual(r.componentes.map((c) => [c.servicio, c.numero_personas]), [['pesca', 2], ['traslado', 3]]);
  assert.deepEqual(r.componentes[0].personalizaciones, [{ id: 10 }]);
  const t = r.componentes[1];
  assert.equal(t.tipo_traslado, 'redondo_actividad');
  assert.equal(t.punto_encuentro, 7);
  assert.equal(t.zona, 'centro');
  assert.equal('fecha' in t, false);
});

test('aeropuerto con hotel del catálogo no manda la zona del hotel (sus tarifas no llevan zona)', () => {
  const comp = { ...COMPONENTES, traslado: { ...COMPONENTES.traslado, traslado: traslado({ tipo: 'redondo_aeropuerto' }) } };
  const r = p.armarPayloadOrden({ ...BASE, paquete: CRUZA, componentes: comp });
  assert.equal(r.componentes[1].zona, '');
  assert.equal(r.componentes[1].punto_encuentro, 7);
});

test('dirección libre manda dirección y zona elegida solo en redondo_actividad', () => {
  const comp = { ...COMPONENTES, traslado: { ...COMPONENTES.traslado, traslado: traslado({ modo: 'personalizada', direccion: ' Calle 1 ', zonaLibre: 'periferia', puntoEncuentroId: null }) } };
  const t = p.armarPayloadOrden({ ...BASE, paquete: CRUZA, componentes: comp }).componentes[1];
  assert.equal(t.direccion_personalizada, 'Calle 1');
  assert.equal(t.zona, 'periferia');
  assert.equal('punto_encuentro' in t, false);
});

test('fecha_regreso del aeropuerto solo viaja si el paquete no tiene hospedaje', () => {
  const comp = { ...COMPONENTES, traslado: { ...COMPONENTES.traslado, traslado: traslado({ tipo: 'redondo_aeropuerto', fechaRegreso: '2026-10-18' }) } };
  const sin = p.armarPayloadOrden({ ...BASE, paquete: CRUZA, componentes: comp });
  assert.equal(sin.componentes[1].fecha_regreso, '2026-10-18');
  const con = p.armarPayloadOrden({ ...BASE, paquete: { ...CRUZA, noches: 3 }, componentes: comp });
  assert.equal(con.componentes[1].fecha_regreso, undefined);
});

const MONO = {
  slug: 'finde', empresa_lider_slug: 'sal-y-sol', noches: 3,
  servicios_asociados: [
    svc(5, 'hotel', 'sal-y-sol', 'hospedaje', 'por_noche', { noches: 3 }),
    svc(6, 'pesca', 'sal-y-sol', 'pesca', 'por_recurso_dia', { dia_estancia: 2 }),
  ],
};

test('personas principales: las del primer componente por_recurso_dia', () => {
  const comps = { hotel: { personas: 1, extras: [] }, pesca: { personas: 3, extras: [] } };
  assert.equal(p.personasPrincipales(MONO, comps), 3);
});

test('la reserva manda personas por servicio (por id), inicio y todos los extras, sin fecha_salida', () => {
  const comps = { hotel: { personas: 1, extras: [{ id: 1 }] }, pesca: { personas: 3, extras: [{ id: 2 }] } };
  const r = p.armarPayloadReserva({ ...BASE, paquete: MONO, componentes: comps });
  assert.equal(r.fecha, '2026-10-15');
  assert.equal(r.paquete, 'finde');
  assert.equal(r.numero_personas, 3);
  assert.deepEqual(r.personas_por_servicio, { 5: 1, 6: 3 });
  assert.deepEqual(r.personalizaciones.map((x) => x.id), [1, 2]);
  assert.equal(r.fecha_salida, undefined);
});
```

- [ ] **Paso 2: verlas fallar** — `node tests/run-hub-tests.cjs pedido-payload` → error de compilación: módulo `./pedido-payload` inexistente.

- [ ] **Paso 3: implementar** — `frontend/src/lib/pedido-payload.ts`:

```ts
import type {
  ComponenteOrdenInput, CrearOrdenInput, Moneda, PaqueteCatalogo, ReservaInput, TipoTraslado, Zona,
} from './api';
import type { SeleccionPersonalizacion } from './personalizaciones';

export type DatosContacto = { fullName: string; phone: string; email: string };

export type DetalleTraslado = {
  tipo: TipoTraslado;
  modo: 'catalogo' | 'personalizada';
  puntoEncuentroId: number | null;
  direccion: string;
  zonaLibre: Zona | '';
  fechaRegreso: string | null;
};

export type ComponentePedido = {
  personas: number;
  extras: SeleccionPersonalizacion[];
  traslado?: DetalleTraslado;
};

type ZonaDePunto = (puntoId: number | null) => Zona | '';

/**
 * Misma regla que `DetalleTransporte.zona_efectiva()` del backend: la zona solo importa en
 * `redondo_actividad` (hotel del catálogo, o la zona elegida si es dirección libre); en los
 * tipos de aeropuerto las tarifas no llevan zona, aunque el hotel tenga una.
 */
export function zonaEfectivaDeTraslado(t: DetalleTraslado, zonaDePunto: ZonaDePunto): Zona | '' {
  if (t.tipo !== 'redondo_actividad') return '';
  return t.modo === 'catalogo' ? zonaDePunto(t.puntoEncuentroId) : t.zonaLibre;
}

type ArgsComunes = {
  checkoutId: string;
  paquete: PaqueteCatalogo;
  componentes: Record<string, ComponentePedido>;
  inicio: string;
  hora: string;
  moneda: Moneda;
  contacto: DatosContacto;
  ref?: string;
  /** Zona de un punto de encuentro del catálogo de traslados, o '' si no aplica. */
  zonaDePunto: ZonaDePunto;
};

/** Personas del componente operativo principal: el primer `por_recurso_dia`; si no hay, el primero. */
export function personasPrincipales(paquete: PaqueteCatalogo, componentes: Record<string, ComponentePedido>): number {
  const ordenados = [...paquete.servicios_asociados].sort((a, b) => a.orden - b.orden);
  const principal = ordenados.find((c) => c.servicio.estrategia_cupo === 'por_recurso_dia') ?? ordenados[0];
  return componentes[principal.servicio.slug]?.personas ?? 1;
}

export function armarPayloadOrden(args: ArgsComunes): CrearOrdenInput {
  const { paquete, componentes, contacto } = args;
  const tieneHospedaje = paquete.noches !== null && paquete.noches !== undefined;
  const nombre = contacto.fullName.trim();

  const filas: ComponenteOrdenInput[] = paquete.servicios_asociados.map((c) => {
    const actual = componentes[c.servicio.slug];
    const fila: ComponenteOrdenInput = {
      servicio: c.servicio.slug,
      hora: args.hora,
      numero_personas: actual.personas,
      personalizaciones: actual.extras,
    };
    if (c.servicio.tipo_servicio === 'transporte' && actual.traslado) {
      const t = actual.traslado;
      fila.tipo_traslado = t.tipo;
      fila.zona = zonaEfectivaDeTraslado(t, args.zonaDePunto);
      if (t.modo === 'catalogo') fila.punto_encuentro = t.puntoEncuentroId;
      else fila.direccion_personalizada = t.direccion.trim();
      if (t.tipo === 'redondo_aeropuerto' && !tieneHospedaje) fila.fecha_regreso = t.fechaRegreso;
    }
    return fila;
  });

  return {
    checkout_id: args.checkoutId,
    paquete: paquete.slug,
    deslinde_aceptado: true,
    deslinde_nombre: nombre,
    nombre_cliente: nombre,
    telefono_cliente: contacto.phone.trim(),
    correo_cliente: contacto.email.trim(),
    moneda: args.moneda,
    ref: args.ref,
    fecha: args.inicio,
    hora: args.hora,
    componentes: filas,
  };
}

export function armarPayloadReserva(args: ArgsComunes): ReservaInput {
  const { paquete, componentes, contacto } = args;
  const nombre = contacto.fullName.trim();
  const personasPorServicio: Record<string, number> = {};
  const personalizaciones: ReservaInput['personalizaciones'] = [];
  for (const c of paquete.servicios_asociados) {
    const actual = componentes[c.servicio.slug];
    personasPorServicio[String(c.servicio_id)] = actual.personas;
    personalizaciones.push(...actual.extras.map((x) => ({ id: x.id, cantidad: x.cantidad, respuesta: x.respuesta })));
  }
  return {
    checkout_id: args.checkoutId,
    fecha: args.inicio,
    hora: args.hora,
    numero_personas: personasPrincipales(paquete, componentes),
    personas_por_servicio: personasPorServicio,
    nombre_cliente: nombre,
    telefono_cliente: contacto.phone.trim(),
    correo_cliente: contacto.email.trim(),
    moneda: args.moneda,
    deslinde_aceptado: true,
    deslinde_nombre: nombre,
    ref: args.ref,
    paquete: paquete.slug,
    personalizaciones,
  };
}
```
(Si `ReservaInput` exige `captcha_token` u otros campos, `tsc` lo dirá; el captcha se añade en el hook de pago, Tarea 3.2, justo antes de enviar.)

- [ ] **Paso 4: verlas pasar y commit**

```bash
node tests/run-hub-tests.cjs pedido-payload && npx tsc --noEmit && npm run lint
git add frontend/src/lib/pedido-payload.ts frontend/tests/pedido-payload.test.cjs frontend/tests/run-hub-tests.cjs
git commit -m "feat(frontend): payloads de reserva y de orden del checkout unificado"
```

**STOP DURO — Cierre de la Sección 1.** Reportar: contrato tipado y lógica pura con pruebas (vector 6,400/1,650/8,050 y USD 383/99 en verde).

---

## Sección 2 — Una sola URL

### Tarea 2.1: `hrefPaquete` apunta siempre a `/reservar`

**Files:**
- Modify: `frontend/src/lib/booking-href.ts` (`hrefPaquete`)
- Modify: `frontend/tests/booking-href.test.cjs` (los tres tests de `hrefPaquete`)

**Interfaces:**
- Produces: `hrefPaquete(paquete, lang, moneda): string` → `/${lang}/reservar?paquete=<slug>&sede=<slug>&moneda=<m>`; no depende de que el paquete sea de una o de dos empresas.

> **Nota de base:** esta tarea **no** usa helpers que existan solo en los cambios sin commitear del hub (p. ej. `rutaConQuery`): la función queda autocontenida, para que compile sobre la rama de partida.

- [ ] **Paso 1: prueba que falla.** En `frontend/tests/booking-href.test.cjs` sustituye los tres tests cuyo nombre empieza por `paquete ` (mono-empresa, cruza-empresa y sin `sede_slug`) por:

```js
test('un paquete de una empresa y uno de dos van a la misma ruta y sin paquete_empresa', () => {
  const una = h.hrefPaquete(paqueteBase(), 'es', 'MXN');
  const cruza = paqueteBase({
    servicios_asociados: [
      { id: 1, servicio_id: 1, orden: 1, servicio: { ...paqueteBase().servicios_asociados[0].servicio, empresa_slug: 'sal-y-sol' } },
      { id: 2, servicio_id: 2, orden: 2, servicio: { ...paqueteBase().servicios_asociados[0].servicio, id: 2, empresa_slug: 'transporte-la-paz' } },
    ],
  });
  const dos = h.hrefPaquete(cruza, 'es', 'MXN');
  assert.equal(una, '/es/reservar?paquete=brunch-y-pesca&sede=la-paz&moneda=MXN');
  assert.equal(dos, una);
});

test('paquete sin sede_slug omite el parametro sede', () => {
  const href = h.hrefPaquete(paqueteBase({ sede_slug: '' }), 'en', 'USD');
  assert.equal(href, '/en/reservar?paquete=brunch-y-pesca&moneda=USD');
});
```
Los demás tests del archivo (servicios, detalle de servicio) no se tocan.

- [ ] **Paso 2: verla fallar**

```bash
node tests/run-hub-tests.cjs booking-href
```
Esperado: FAIL (el cruza-empresa devuelve `/es/reservar-paquete?...` y el mono-empresa lleva `paquete_empresa`).

- [ ] **Paso 3: implementar.** Reemplaza `hrefPaquete` (y elimina el import `esPaqueteCruzaEmpresa` de `booking-href.ts` si queda sin uso):

```ts
export function hrefPaquete(paquete: PaqueteCatalogo, lang: Locale, moneda: Moneda): string {
  const query = new URLSearchParams({ paquete: paquete.slug });
  if (paquete.sede_slug) query.set('sede', paquete.sede_slug);
  query.set('moneda', moneda);
  return `/${lang}/reservar?${query.toString()}`;
}
```
(`paquete_empresa` deja de viajar: la empresa la deduce el servidor del paquete.)

- [ ] **Paso 4: verla pasar y commit**

```bash
node tests/run-hub-tests.cjs booking-href && npx tsc --noEmit && npm run lint
git add frontend/src/lib/booking-href.ts frontend/tests/booking-href.test.cjs
git commit -m "feat(frontend): una sola URL de reserva para paquetes"
```

**STOP DURO — Cierre de la Sección 2.** Reportar: una sola URL de reserva de paquete (`hrefPaquete` verificado por prueba). La página `/reservar` se conecta al componente nuevo en la Tarea 3.5.

---

## Sección 3 — Componente unificado

> **Regla de diseño:** cada tarea de esta sección que produce UI se construye con la skill `design-taste-frontend` contra las pantallas del spec §3 (ya aprobadas por el dueño) y se detiene para revisión visual del dueño al cerrar la sección. **No** cambies estructura, orden de pasos ni textos aprobados sin volver a consultarlo.

### Tarea 3.1: Estado del pedido (reducer puro y hook)

**Files:**
- Create: `frontend/src/lib/pedido-estado.ts` (reducer puro, probado)
- Create: `frontend/src/components/pedido/use-pedido-estado.ts` (hook delgado)
- Modify: `frontend/tests/run-hub-tests.cjs` (registra `'pedido-estado'`)
- Test: `frontend/tests/pedido-estado.test.cjs`

**Interfaces:**
- Consumes: `ComponentePedido`, `DatosContacto`, `DetalleTraslado` (1.4), `seleccionInicial` de `personalizaciones.ts`.
- Produces:
  - `type EstadoPedido = { contacto: DatosContacto; inicio: string | null; hora: string; moneda: Moneda; formaPago: 'completo' | 'anticipo'; componentes: Record<string, ComponentePedido> }`.
  - `type AccionPedido = { tipo: 'contacto'; cambios: Partial<DatosContacto> } | { tipo: 'inicio'; valor: string } | { tipo: 'hora'; valor: string } | { tipo: 'moneda'; valor: Moneda } | { tipo: 'formaPago'; valor: 'completo' | 'anticipo' } | { tipo: 'personas'; slug: string; valor: number } | { tipo: 'extras'; slug: string; valor: SeleccionPersonalizacion[] } | { tipo: 'traslado'; slug: string; cambios: Partial<DetalleTraslado> }`.
  - `type OpcionesEstadoInicial = { moneda: Moneda; puntoInicial: (empresaSlug: string) => number | null }`.
  - `estadoInicial(paquete, opciones): EstadoPedido`, `reducirPedido(estado, accion): EstadoPedido`.
  - `usePedidoEstado(paquete, opciones): [EstadoPedido, Dispatch<AccionPedido>]`.

- [ ] **Paso 1: prueba que falla.** Registra `'pedido-estado': ['src/lib/pedido-estado.ts', 'PEDIDO_ESTADO_TEST_OUT'],` y crea `frontend/tests/pedido-estado.test.cjs`:

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const e = require(path.join(process.env.PEDIDO_ESTADO_TEST_OUT, 'lib/pedido-estado.js'));

const PAQUETE = {
  servicios_asociados: [
    { servicio_id: 1, personas_incluidas: 3, servicio: { slug: 'pesca', empresa_slug: 'sal-y-sol', tipo_servicio: 'pesca', personalizaciones: [{ id: 10, tipo_interaccion: 'check', preseleccionado: true }] } },
    { servicio_id: 2, personas_incluidas: 2, servicio: { slug: 'traslado', empresa_slug: 'transp', tipo_servicio: 'transporte', personalizaciones: [] } },
  ],
};

const inicial = () => e.estadoInicial(PAQUETE, { moneda: 'MXN', puntoInicial: () => 7 });

test('arranca con las personas incluidas, los extras preseleccionados y sin fecha', () => {
  const s = inicial();
  assert.equal(s.inicio, null);
  assert.equal(s.componentes.pesca.personas, 3);
  assert.deepEqual(s.componentes.pesca.extras, [{ id: 10, cantidad: 1 }]);
  assert.equal(s.componentes.traslado.traslado.puntoEncuentroId, 7);
  assert.equal(s.componentes.pesca.traslado, undefined);
});

test('cambiar personas de un componente no toca a los demás', () => {
  const s = e.reducirPedido(inicial(), { tipo: 'personas', slug: 'pesca', valor: 1 });
  assert.equal(s.componentes.pesca.personas, 1);
  assert.equal(s.componentes.traslado.personas, 2);
});

test('cambios parciales del traslado se mezclan', () => {
  const s = e.reducirPedido(inicial(), { tipo: 'traslado', slug: 'traslado', cambios: { tipo: 'redondo_aeropuerto', fechaRegreso: '2026-10-18' } });
  assert.equal(s.componentes.traslado.traslado.tipo, 'redondo_aeropuerto');
  assert.equal(s.componentes.traslado.traslado.puntoEncuentroId, 7);
});

test('contacto, inicio, moneda y forma de pago', () => {
  let s = e.reducirPedido(inicial(), { tipo: 'contacto', cambios: { fullName: 'Ana' } });
  s = e.reducirPedido(s, { tipo: 'inicio', valor: '2026-10-15' });
  s = e.reducirPedido(s, { tipo: 'moneda', valor: 'USD' });
  s = e.reducirPedido(s, { tipo: 'formaPago', valor: 'anticipo' });
  assert.deepEqual([s.contacto.fullName, s.contacto.phone, s.inicio, s.moneda, s.formaPago], ['Ana', '', '2026-10-15', 'USD', 'anticipo']);
});
```

- [ ] **Paso 2: verla fallar** — `node tests/run-hub-tests.cjs pedido-estado` → error de compilación (módulo inexistente).

- [ ] **Paso 3: implementar** — `frontend/src/lib/pedido-estado.ts` (puro, imports relativos):

```ts
import type { Moneda, PaqueteCatalogo } from './api';
import type { ComponentePedido, DatosContacto, DetalleTraslado } from './pedido-payload';
import { seleccionInicial, type SeleccionPersonalizacion } from './personalizaciones';

export type EstadoPedido = {
  contacto: DatosContacto;
  inicio: string | null;
  hora: string;
  moneda: Moneda;
  formaPago: 'completo' | 'anticipo';
  componentes: Record<string, ComponentePedido>;
};

export type AccionPedido =
  | { tipo: 'contacto'; cambios: Partial<DatosContacto> }
  | { tipo: 'inicio'; valor: string }
  | { tipo: 'hora'; valor: string }
  | { tipo: 'moneda'; valor: Moneda }
  | { tipo: 'formaPago'; valor: 'completo' | 'anticipo' }
  | { tipo: 'personas'; slug: string; valor: number }
  | { tipo: 'extras'; slug: string; valor: SeleccionPersonalizacion[] }
  | { tipo: 'traslado'; slug: string; cambios: Partial<DetalleTraslado> };

export type OpcionesEstadoInicial = {
  moneda: Moneda;
  puntoInicial: (empresaSlug: string) => number | null;
};

export function estadoInicial(paquete: PaqueteCatalogo, opciones: OpcionesEstadoInicial): EstadoPedido {
  const componentes: Record<string, ComponentePedido> = {};
  for (const c of paquete.servicios_asociados) {
    componentes[c.servicio.slug] = {
      personas: c.personas_incluidas,
      extras: seleccionInicial(c.servicio.personalizaciones),
      ...(c.servicio.tipo_servicio === 'transporte'
        ? {
            traslado: {
              tipo: 'redondo_actividad' as const,
              modo: 'catalogo' as const,
              puntoEncuentroId: opciones.puntoInicial(c.servicio.empresa_slug),
              direccion: '',
              zonaLibre: '' as const,
              fechaRegreso: null,
            },
          }
        : {}),
    };
  }
  return {
    contacto: { fullName: '', phone: '', email: '' },
    inicio: null,
    hora: '07:00',
    moneda: opciones.moneda,
    formaPago: 'completo',
    componentes,
  };
}

function conComponente(
  estado: EstadoPedido,
  slug: string,
  cambiar: (c: ComponentePedido) => ComponentePedido,
): EstadoPedido {
  return { ...estado, componentes: { ...estado.componentes, [slug]: cambiar(estado.componentes[slug]) } };
}

export function reducirPedido(estado: EstadoPedido, accion: AccionPedido): EstadoPedido {
  switch (accion.tipo) {
    case 'contacto':
      return { ...estado, contacto: { ...estado.contacto, ...accion.cambios } };
    case 'inicio':
      return { ...estado, inicio: accion.valor };
    case 'hora':
      return { ...estado, hora: accion.valor };
    case 'moneda':
      return { ...estado, moneda: accion.valor };
    case 'formaPago':
      return { ...estado, formaPago: accion.valor };
    case 'personas':
      return conComponente(estado, accion.slug, (c) => ({ ...c, personas: accion.valor }));
    case 'extras':
      return conComponente(estado, accion.slug, (c) => ({ ...c, extras: accion.valor }));
    case 'traslado':
      return conComponente(estado, accion.slug, (c) =>
        c.traslado ? { ...c, traslado: { ...c.traslado, ...accion.cambios } } : c,
      );
  }
}
```
y el hook, `frontend/src/components/pedido/use-pedido-estado.ts`:

```ts
import { useReducer, type Dispatch } from 'react';
import type { PaqueteCatalogo } from '@/lib/api';
import {
  estadoInicial, reducirPedido, type AccionPedido, type EstadoPedido, type OpcionesEstadoInicial,
} from '@/lib/pedido-estado';

export function usePedidoEstado(
  paquete: PaqueteCatalogo,
  opciones: OpcionesEstadoInicial,
): [EstadoPedido, Dispatch<AccionPedido>] {
  return useReducer(reducirPedido, undefined, () => estadoInicial(paquete, opciones));
}
```

- [ ] **Paso 4: verificar y commit**

```bash
node tests/run-hub-tests.cjs pedido-estado && npx tsc --noEmit && npm run lint
git add frontend/src/lib/pedido-estado.ts frontend/src/components/pedido frontend/tests
git commit -m "feat(frontend): estado del pedido (reducer puro) del checkout unificado"
```

### Tarea 3.2: Hook de pago (dos motores, una interfaz)

**Files:**
- Create: `frontend/src/components/pedido/use-pago-pedido.ts`

**Interfaces:**
- Consumes: `crearOrden`, `crearPagoOrden`, `getOrden`, `confirmarCapturaOrden`, `guardarReserva`, `crearPago`, `getEstadoReserva`, `ApiError` de `@/lib/api`; `PagoOrdenItem`, `Pago`.
- Produces:
  - `type PasoPago = { empresaSlug: string; monto: string; clientSecret: string; publishableKey: string }`.
  - `type FasePedido = 'resumiendo' | 'formulario' | 'enviando' | 'pagando' | 'capturando' | 'confirmando' | 'exito' | 'fallo'`.
  - `usePagoPedido(config): { fase; pagos: PasoPago[]; indice: number; error: string; motivoFallo: string; ordenId: number | null; enviar(): Promise<void>; onPagoConfirmado(): void; onPagoRechazado(mensaje: string): void; reiniciar(): void; checkoutId: string }`, con `config = { motor: 'reserva' | 'orden'; sedeSlug: string; empresaSlug: string; paqueteSlug: string; armarPayload: (checkoutId: string) => CrearOrdenInput | ReservaInput; formaPago: 'completo' | 'anticipo'; codigoPromocional?: string; captchaToken: () => string; mensajeDeError: (err: unknown) => string }`.

Es la unión, en un solo hook, de la orquestación que hoy vive en dos sitios: `paquete-checkout.tsx` (L98-L400: `checkoutId` en `sessionStorage`, reanudación con `getOrden`, captura con reintento cada 5 s) y `checkout-view.tsx` (`enviar`: `guardarReserva` + `crearPago`). **Conserva sus reglas**: una recarga a mitad de la secuencia reanuda desde el servidor y no repite pagos ya autorizados; un error de red al consultar la captura no marca fracaso; solo `capturada` es éxito y solo `cancelada` es fallo.

- [ ] **Paso 1: implementar** — `use-pago-pedido.ts`. Reglas que el hook **debe** cumplir (dos motores, una interfaz):
  1. **`orden` (dos empresas):** una recarga a mitad de la secuencia reanuda desde el servidor (`getOrden`) y no repite pagos ya autorizados; solo `capturada` es éxito y solo `cancelada` es fallo; un error de red al consultar no marca fracaso.
  2. **`reserva` (una empresa):** una recarga consulta `getEstadoReserva`; tras el último pago **no** se declara éxito de inmediato: se pasa a `confirmando` y se consulta el estado cada 5 s hasta `pagada` (éxito) o `cancelada` (fallo). El webhook puede cancelar y reembolsar por cupo después de que Stripe acepte la tarjeta, así que solo `pagada` es éxito.
  3. **Lint (React 19):** no se escribe en un ref durante el render; `cfg.current = config` va dentro de un efecto (mismo patrón que `frontend/src/components/turnstile.tsx`).

```ts
'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  confirmarCapturaOrden, crearOrden, crearPago, crearPagoOrden, getEstadoReserva, getOrden,
  guardarReserva, type CrearOrdenInput, type OrdenDetalle, type ReservaInput,
} from '@/lib/api';

export type PasoPago = { empresaSlug: string; monto: string; clientSecret: string; publishableKey: string };
export type FasePedido =
  | 'resumiendo' | 'formulario' | 'enviando' | 'pagando' | 'capturando' | 'confirmando' | 'exito' | 'fallo';

type Config = {
  motor: 'reserva' | 'orden';
  sedeSlug: string;
  empresaSlug: string;
  paqueteSlug: string;
  armarPayload: (checkoutId: string) => CrearOrdenInput | ReservaInput;
  formaPago: 'completo' | 'anticipo';
  codigoPromocional?: string;
  captchaToken: () => string;
  mensajeDeError: (err: unknown) => string;
};

type Guardado = { checkoutId?: string; ordenId?: number };
const REINTENTO_MS = 5000;

export function usePagoPedido(config: Config) {
  const clave = `salysol:pedido:${config.paqueteSlug}`;
  const [checkoutId, setCheckoutId] = useState('');
  const [ordenId, setOrdenId] = useState<number | null>(null);
  const [fase, setFase] = useState<FasePedido>('resumiendo');
  const [pagos, setPagos] = useState<PasoPago[]>([]);
  const [indice, setIndice] = useState(0);
  const [error, setError] = useState('');
  const [motivoFallo, setMotivoFallo] = useState('');

  const cfg = useRef(config);
  useEffect(() => {
    cfg.current = config;
  });

  const guardar = useCallback(
    (datos: Guardado) => {
      try {
        window.sessionStorage.setItem(clave, JSON.stringify(datos));
      } catch {
        // sin almacenamiento: si recarga, empieza de cero
      }
    },
    [clave],
  );

  /* eslint-disable react-hooks/set-state-in-effect -- lectura única de sessionStorage en cliente */
  useLayoutEffect(() => {
    let guardado: Guardado | null = null;
    try {
      const crudo = window.sessionStorage.getItem(clave);
      guardado = crudo ? (JSON.parse(crudo) as Guardado) : null;
    } catch {
      guardado = null;
    }
    if (guardado?.checkoutId) {
      setCheckoutId(guardado.checkoutId);
      if (config.motor === 'orden' && guardado.ordenId) {
        setOrdenId(guardado.ordenId); // el efecto de reanudación de la orden decide la fase
        return;
      }
      if (config.motor === 'reserva') return; // sigue 'resumiendo': el efecto de abajo consulta la reserva
    } else {
      const nuevo = crypto.randomUUID();
      guardar({ checkoutId: nuevo });
      setCheckoutId(nuevo);
    }
    setFase('formulario');
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo al montar
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Motor 'reserva': recuperar el estado de la reserva de este checkout.
  useEffect(() => {
    if (config.motor !== 'reserva' || fase !== 'resumiendo' || !checkoutId) return;
    let cancelado = false;
    getEstadoReserva(checkoutId, config.empresaSlug)
      .then((estado) => {
        if (cancelado) return;
        // 'pendiente_pago' o 'cancelada': se sigue con el formulario; reenviar el mismo
        // checkout_id actualiza la misma reserva (el servidor hace upsert).
        setFase(estado.estado === 'pagada' ? 'exito' : 'formulario');
      })
      .catch(() => {
        if (!cancelado) setFase('formulario'); // 404 o sin red: nunca debe trabar el checkout
      });
    return () => {
      cancelado = true;
    };
  }, [config.motor, config.empresaSlug, fase, checkoutId]);

  // Motor 'orden': reanudación. El estado real lo dice el servidor.
  useEffect(() => {
    if (ordenId === null) return;
    let cancelado = false;
    getOrden(config.sedeSlug, ordenId)
      .then((detalle: OrdenDetalle) => {
        if (cancelado) return;
        if (detalle.estado === 'capturada') return setFase('exito');
        if (detalle.estado === 'cancelada') return setFase('fallo');
        if (detalle.estado === 'autorizando' || detalle.estado === 'autorizada') {
          setPagos(
            detalle.reservas.map((r) => ({
              empresaSlug: r.empresa_slug,
              monto: r.pago.monto ?? '0',
              clientSecret: r.pago.client_secret ?? '',
              publishableKey: r.pago.publishable_key,
            })),
          );
          const pendiente = detalle.reservas.findIndex(
            (r) => !['requires_capture', 'succeeded'].includes(r.pago.estado_pi ?? ''),
          );
          if (pendiente === -1) return setFase('capturando');
          setIndice(pendiente);
          return setFase('pagando');
        }
        setFase('formulario'); // 'armando': se creó pero nunca se llegó a crear-pago
      })
      .catch(() => {
        if (cancelado) return;
        try {
          window.sessionStorage.removeItem(clave);
        } catch {
          // nada que limpiar
        }
        setOrdenId(null);
        setFase('formulario');
      });
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo cuando cambia ordenId
  }, [ordenId]);

  // Motor 'orden': captura final, con consulta periódica si la respuesta se pierde.
  useEffect(() => {
    if (fase !== 'capturando' || ordenId === null) return;
    let cancelado = false;
    let timer: ReturnType<typeof setTimeout>;
    const aplicar = (r: { estado: string; motivo?: string }) => {
      if (cancelado) return true;
      if (r.estado === 'capturada') return setFase('exito'), true;
      if (r.estado === 'cancelada') return setMotivoFallo(r.motivo ?? ''), setFase('fallo'), true;
      return false;
    };
    const consultar = async () => {
      try {
        if (aplicar(await getOrden(config.sedeSlug, ordenId))) return;
      } catch {
        // una respuesta perdida no prueba que el cobro falló: conservar la orden y seguir consultando
      }
      if (!cancelado) timer = setTimeout(consultar, REINTENTO_MS);
    };
    confirmarCapturaOrden(config.sedeSlug, ordenId)
      .then((r) => {
        if (!aplicar(r)) timer = setTimeout(consultar, REINTENTO_MS);
      })
      .catch(() => {
        if (!cancelado) timer = setTimeout(consultar, REINTENTO_MS);
      });
    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
  }, [fase, ordenId, config.sedeSlug]);

  // Motor 'reserva': esperar al webhook. Solo `pagada` es éxito; `cancelada` (cupo lleno, reembolso) es fallo.
  useEffect(() => {
    if (fase !== 'confirmando') return;
    let cancelado = false;
    let timer: ReturnType<typeof setTimeout>;
    const consultar = async () => {
      try {
        const estado = await getEstadoReserva(checkoutId, config.empresaSlug);
        if (cancelado) return;
        if (estado.estado === 'pagada') return setFase('exito');
        if (estado.estado === 'cancelada') return setMotivoFallo(''), setFase('fallo');
      } catch {
        // sin red: seguir consultando
      }
      if (!cancelado) timer = setTimeout(consultar, REINTENTO_MS);
    };
    consultar();
    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
  }, [fase, checkoutId, config.empresaSlug]);

  const enviar = useCallback(async () => {
    if (fase === 'enviando' || fase === 'pagando' || fase === 'capturando' || fase === 'confirmando') return;
    setFase('enviando');
    setError('');
    const c = cfg.current;
    try {
      const payload = c.armarPayload(checkoutId);
      if (c.motor === 'orden') {
        const creada = await crearOrden(c.sedeSlug, payload as CrearOrdenInput);
        setOrdenId(creada.orden_id);
        guardar({ checkoutId, ordenId: creada.orden_id });
        const respuesta = await crearPagoOrden(c.sedeSlug, creada.orden_id);
        setPagos(respuesta.map((p) => ({
          empresaSlug: p.empresa_slug, monto: p.monto, clientSecret: p.client_secret, publishableKey: p.publishable_key,
        })));
      } else {
        const reserva = await guardarReserva(
          { ...(payload as ReservaInput), captcha_token: c.captchaToken() }, c.empresaSlug,
        );
        const pago = await crearPago(
          reserva.id,
          { checkout_id: checkoutId, forma_pago: c.formaPago, codigo_promocional: c.codigoPromocional || undefined },
          c.empresaSlug,
        );
        setPagos([{
          empresaSlug: c.empresaSlug, monto: pago.monto_a_cobrar,
          clientSecret: pago.client_secret, publishableKey: pago.publishable_key,
        }]);
      }
      setIndice(0);
      setFase('pagando');
    } catch (err) {
      // Un 503 ("Stripe no configurado") lo traduce `mensajeDeError` a `checkout.paymentUnavailable`.
      setError(c.mensajeDeError(err));
      setFase('formulario');
    }
  }, [fase, checkoutId, guardar]);

  const onPagoConfirmado = useCallback(
    () => {
      if (indice >= pagos.length - 1) {
        // 'orden': hay que capturar todos los pagos autorizados. 'reserva': esperar al webhook.
        setFase(cfg.current.motor === 'orden' ? 'capturando' : 'confirmando');
        return;
      }
      setIndice(indice + 1);
    },
    [indice, pagos.length],
  );

  const onPagoRechazado = useCallback((mensaje: string) => {
    setMotivoFallo(mensaje);
    if (cfg.current.motor === 'orden') {
      // pedir confirmar-captura revierte la orden incompleta (void del primer pago)
      setFase('capturando');
    } else {
      setError(mensaje);
      setFase('formulario');
    }
  }, []);

  const reiniciar = useCallback(() => {
    try {
      window.sessionStorage.removeItem(clave);
    } catch {
      // nada que limpiar
    }
    window.location.reload();
  }, [clave]);

  return {
    fase, pagos, indice, error, motivoFallo, ordenId, checkoutId,
    enviar, onPagoConfirmado, onPagoRechazado, reiniciar,
  };
}
```
Ajustes al pegar (los valida `tsc`/`eslint`): (1) los nombres de campos de `Pago`/`PagoOrdenItem`/`OrdenDetalle` son los de `frontend/src/lib/api.ts`; (2) `StripePanel` llama `onPagoConfirmado(procesando)`; aquí se ignora el argumento porque en ambos motores la confirmación real llega después (captura de la orden o webhook); (3) en el motor `reserva` un fallo de tarjeta devuelve al formulario con el mensaje y **no** reinicia la reserva (es la misma que se reintenta).

- [ ] **Paso 2: verificar** `npx tsc --noEmit && npm run lint`. (Sin prueba unitaria: depende de red y de `sessionStorage`; se cubre en el smoke de la Tarea 3.6.)

- [ ] **Paso 3: Commit**

```bash
git add frontend/src/components/pedido/use-pago-pedido.ts
git commit -m "feat(frontend): hook de pago del pedido con dos motores y reanudacion"
```

### Tarea 3.3: `StripePanel` con ranuras opcionales

**Files:**
- Modify: `frontend/src/components/stripe-panel.tsx` (props ≈ L27-L57, `PaymentForm` ≈ L60-L130, cuerpo ≈ L170-L330)

**Interfaces:**
- Produces (props nuevas, **todas opcionales y con el default que replica el comportamiento actual**):
  - `formaPagoDisponible?: boolean` (default `true`): oculta el fieldset de "completo/anticipo" y el "monto a pagar ahora" cuando es `false`.
  - `codigoPromocionalDisponible?: boolean` (default `true`): oculta el bloque del código.
  - `avisoCargos?: ReactNode`: se pinta en fase `form`, justo arriba de la casilla del deslinde (R4).
  - `encabezadoPago?: ReactNode`: se pinta en fase `payment`, dentro de la tarjeta y arriba de Stripe (R2, R5).
  - `etiquetaBotonPago?: string`: texto del botón de `PaymentForm` (R5); default `checkout.confirmPay`.
  - `etiquetaBotonEnvio?: string`: texto del botón de la fase `form`; default el actual.

- [ ] **Paso 1: implementar.** Añade las props al tipo y a la desestructuración; pasa `etiquetaBotonPago` a `PaymentForm` (nueva prop) y úsalo donde hoy dice `{submitting ? checkout.submitting : checkout.confirmPay}`; envuelve el fieldset de forma de pago con `formaPagoDisponible !== false &&` y el bloque del código con `codigoPromocionalDisponible !== false &&`; inserta `{avisoCargos}` antes de la `<label>` del deslinde (fase `form`) y `{encabezadoPago}` como primer hijo de la fase `payment` antes de `<Elements>`. Cambia el texto del botón de la fase `form` con `etiquetaBotonEnvio ?? <el actual>`.

- [ ] **Paso 2: verificar que nada cambió para los demás usuarios.**

```bash
npx tsc --noEmit && npm run lint
grep -rn "<StripePanel" src
```
Esperado: los usos existentes (`checkout-view.tsx`, `traslado-view.tsx`, `paquete-checkout.tsx`) siguen compilando sin tocar sus props.

- [ ] **Paso 3: Commit**

```bash
git add frontend/src/components/stripe-panel.tsx
git commit -m "feat(frontend): StripePanel con ranuras opcionales para aviso, encabezado y etiqueta del boton"
```

### Tarea 3.4: Componentes de UI y shell `PedidoPaquete`

**Files:**
- Create: `frontend/src/components/pedido/grupo-servicio.tsx`, `aviso-cargos.tsx`, `encabezado-pago.tsx`, `pedido-paquete.tsx`
- Modify: `frontend/src/app/[lang]/dictionaries/es.json`, `en.json` (claves `pedido.*`)

**Interfaces:**
- Produces:
  - `GrupoServicio(props: { lang; dict; componente: PaqueteServicioCatalogo; estado: ComponentePedido; conEncabezadoEmpresa: boolean; moneda: Moneda; inicio: string | null; noches: number | null; salida: string | null; minDate: string; puntos: PuntoEncuentro[]; onPersonas(n); onExtras(sel); onTraslado(cambios) })`.
  - `AvisoCargos(props: { dict; cargos: { etiqueta: string; monto: string }[]; total: string })` — solo se monta si `cargos.length > 1`.
  - `EncabezadoPago(props: { dict; pasos: { etiqueta: string; monto: string; estado: 'hecho' | 'actual' | 'pendiente' }[]; indice: number })`.
  - `PedidoPaquete(props: { lang; dict; paquete: PaqueteCatalogo; sedeSlug: string; tarifasPorEmpresa; puntosPorEmpresa; minDate })`.
- Consumes: todo lo anterior (1.2-1.4, 3.1-3.3).

**Comportamiento fijado (criterios de aceptación).** Cada punto se verifica leyendo el resultado renderizado en el smoke (Tarea 3.6) y en la revisión visual del dueño:

1. **Mismo layout para N=1 y N=2** (D2). El shell decide qué pintar por `cargos.length` (resultado de `calcularPedido`) y por `paquete.permite_anticipo`, nunca por "mono/cruza".
2. **Pasos y colapso:** `CheckoutStepper` con `steps` = [datos, detalles, confirmar, pago]; cada paso completado se colapsa con `CheckoutSectionCard estado="completado"` y "Cambiar". Sin URL por paso.
3. **Grupos por servicio (R1, R3):** un `CheckoutSectionCard` por servicio con título = nombre del servicio y, si `conEncabezadoEmpresa`, subtítulo secundario "de {empresa}" (`pedido.groupOf`). El encabezado de empresa aparece cuando el paquete tiene más de una empresa; con una sola no se muestra.
4. **Fecha de inicio única:** un `DateField` de "Inicio del paquete" (una sola vez, en el primer grupo o en el paso de datos según el diseño aprobado). **Nunca** un campo de fecha de salida: si hay hospedaje se muestra texto `pedido.nightsNote` ("{n} noches · sales el {fecha}") calculado con `fechaSalida`.
5. **Personas por servicio:** `PeopleStepper` con `maxPeople = componente.personas_incluidas` y `minPeople = 1`; nota `pedido.includedNote` ("El paquete incluye {n} lugares"); el precio no cambia al bajar.
6. **Extras del servicio:** solo los `servicio.personalizaciones` de ese servicio, con la misma UI de extras de `CheckoutView` (checks con `+$`, inputs, selección) y el precio por persona usando `estado.personas` **de ese servicio**. Un extra sin precio en la moneda elegida se muestra deshabilitado con `checkout.extrasUnavailableInCurrency` (si aun así llegara al servidor, este responde 503 "No hay precio de … configurado en USD").
7. **Traslado:** tipo, punto de encuentro o dirección libre, zona cuando es `redondo_actividad`, y fecha de regreso **solo** si es `redondo_aeropuerto` y el paquete no incluye hospedaje (misma lógica que `paquete-checkout.tsx` L296-L316, mover aquí).
8. **Moneda:** el selector MXN/USD aparece **una vez**, arriba, solo si `usdDisponible(...)` (D5). Cambiarla recalcula todos los cargos.
9. **Confirmar pedido:** `StripePanel` en fase `form` con `lines` = un renglón por cargo (`etiqueta` = nombre de la empresa, `amount` = monto), `total` = suma, `avisoCargos={<AvisoCargos …/>}` solo si `cargos.length > 1` (R4), `formaPagoDisponible={paquete.permite_anticipo}`, `codigoPromocionalDisponible={motor === 'reserva'}`, `etiquetaBotonEnvio` = `pedido.continueToPayment` con `{n}=1` y `{total}=cargos.length` (o el texto actual si N=1). El texto del aviso **incluye siempre**: cuántos cargos, empresa y monto de cada uno, que suman el total, y lo que ocurre con la captura. **Redacción revisada:** la garantía "no se te cobra" no es absoluta (si una empresa alcanzó a capturar y el reembolso tarda o falla, el cargo existe hasta que se devuelva; ver `revertir_orden`). Usa el texto de `pedido.chargesSum` de este plan/spec §3 —"…Primero se retiene cada pago y solo entonces se cobra. Si algo falla, se libera o se te reembolsa lo retenido." ("retenido", no "autorizado": spec §10.1)— y no lo cambies sin verificarlo con tarjeta de prueba y sin el visto bueno del dueño (spec §9).**
10. **Pagos (R2, R3, R5):** por cada `PasoPago`, `StripePanel` en fase `payment` con `key={paso.empresaSlug}` (se desmonta y remonta entre pagos), `encabezadoPago={<EncabezadoPago …/>}` y `etiquetaBotonPago` = `pedido.payButton` (`"Pagar {amount} a {empresa} · {n} de {total}"`) o `pedido.payButtonSingle` (`"Pagar {amount}"`) si N=1. `EncabezadoPago` muestra, **con peso visual real**, los pagos hechos como línea `✓ {empresa} {monto} — {pedido.authorized}` ("retenido", decisión del dueño en spec §10.1: "autorizado" es término interno, nunca de cara al cliente) y el actual como "Pago {n} de {total}" (+ "el último" en el último), con la barra de progreso; no se muestra nada de esto con N=1.
11. **Éxito/fallo:** pantallas equivalentes a las de `paquete-checkout.tsx` (L403-L461): título, lista de componentes con su fecha y personas, y en fallo el texto de `pedido.fail.body` (lo retenido se libera o se reembolsa; sin prometer "no se cobró nada") + botón que llama `reiniciar()`. Conservar `pc.success`/`pc.fail` renombrando sus claves a `pedido.success`/`pedido.fail`.
12. **Reanudar:** al recargar en mitad de la secuencia se muestra el paso de pago correcto con los ✓ previos (lo resuelve `usePagoPedido`).
13. **Motor:** `motor = paquete.es_cruza_empresa ? 'orden' : 'reserva'`; `empresaSlug` = `paquete.empresa_lider_slug`.

- [ ] **Paso 1: diccionarios** (`es.json`; el `en.json` con la traducción equivalente). Añade el bloque, junto a `paqueteCheckout`:

```json
  "pedido": {
    "title": "Reserva tu paquete",
    "groupOf": "de {empresa}",
    "startLabel": "Inicio del paquete",
    "nightsNote": "{n} noches · sales el {fecha}",
    "peopleIncluded": "El paquete incluye {n} lugares",
    "extrasTitle": "Personaliza tu paquete",
    "chargesNotice": "Pagarás en {n} cargos, uno por cada empresa:",
    "chargesSum": "Suman {total}. Primero se retiene cada pago y solo entonces se cobra. Si algo falla, se libera o se te reembolsa lo retenido.",
    "continueToPayment": "Continuar al pago 1 de {total}",
    "payStep": "Pago {n} de {total}",
    "payStepLast": "Pago {n} de {total} · el último",
    "authorized": "retenido",
    "payButton": "Pagar {amount} a {empresa} · {n} de {total}",
    "payButtonSingle": "Pagar {amount}",
    "resuming": "Ya tienes una reserva en proceso. Retomando donde te quedaste…",
    "errorGeneric": "Ocurrió un detalle temporal al guardar tu reserva. Por favor intenta de nuevo.",
    "success": {
      "title": "¡Tu paquete está confirmado!",
      "body": "Ya procesamos el pago de tu paquete. Un asesor de nuestro equipo te contactará en las próximas 24 horas con todos los detalles de tu viaje.",
      "componentsHeadline": "Resumen de tu paquete"
    },
    "fail": {
      "title": "No se pudo completar el pago",
      "body": "No se pudo completar el pago de tu paquete. Lo que se haya retenido se libera o se te reembolsa; puedes intentar de nuevo.",
      "motivoPrefix": "Detalle: ",
      "retry": "Intentar de nuevo"
    }
  }
```
(Reutiliza las claves existentes de `checkout.*` y `traslados.*` para campos, errores y textos del traslado; no dupliques.) **Reinicia `npm run dev` tras editar.**

- [ ] **Paso 2: construir los componentes** con `design-taste-frontend`, en este orden: `grupo-servicio.tsx` → `aviso-cargos.tsx` → `encabezado-pago.tsx` → `pedido-paquete.tsx`. Esqueleto estructural del shell (la parte que decide N=1 vs N=2 y conecta hooks):

```tsx
'use client';

import { useMemo, useRef } from 'react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import type { PaqueteCatalogo, PuntoEncuentro, TrasladosCatalogo } from '@/lib/api';
import { fechaSalida } from '@/lib/calendario-paquete';
import { calcularPedido, montoInicial, usdDisponible } from '@/lib/pedido-paquete';
import { armarPayloadOrden, armarPayloadReserva, zonaEfectivaDeTraslado } from '@/lib/pedido-payload';
import { leerRef } from '@/lib/ref';
import { formatearPrecio } from '@/lib/pricing-paquete';
import { usePagoPedido } from './use-pago-pedido';
import { usePedidoEstado } from './use-pedido-estado';

type Props = {
  lang: Locale;
  dict: Dictionary;
  paquete: PaqueteCatalogo;
  sedeSlug: string;
  tarifasPorEmpresa: Record<string, TrasladosCatalogo['tarifas']>;
  puntosPorEmpresa: Record<string, PuntoEncuentro[]>;
  minDate: string;
};

export function PedidoPaquete({ lang, dict, paquete, sedeSlug, tarifasPorEmpresa, puntosPorEmpresa, minDate }: Props) {
  const motor = paquete.es_cruza_empresa ? 'orden' : 'reserva';
  const [estado, despachar] = usePedidoEstado(paquete, {
    moneda: 'MXN',
    puntoInicial: (empresa) => puntosPorEmpresa[empresa]?.[0]?.id ?? null,
  });
  const captcha = useRef('');

  const componentes = useMemo(
    () => paquete.servicios_asociados.map((c) => ({ dia_estancia: c.dia_estancia, estrategia_cupo: c.servicio.estrategia_cupo, noches: c.noches })),
    [paquete],
  );
  const salida = estado.inicio ? fechaSalida(estado.inicio, componentes) : null;

  // Misma regla que el backend (DetalleTransporte.zona_efectiva): solo redondo_actividad usa zona.
  const zonaDePunto = (id: number | null) => Object.values(puntosPorEmpresa).flat().find((p) => p.id === id)?.zona ?? '';
  const selecciones = useMemo(
    () => Object.fromEntries(Object.entries(estado.componentes).map(([slug, c]) => [slug, {
      personas: c.personas, extras: c.extras,
      traslado: c.traslado ? { tipo: c.traslado.tipo, zona: zonaEfectivaDeTraslado(c.traslado, zonaDePunto) } : undefined,
    }])),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- zonaDePunto solo depende de puntosPorEmpresa
    [estado.componentes, puntosPorEmpresa],
  );
  const pedido = calcularPedido(paquete, selecciones, estado.moneda, tarifasPorEmpresa);
  const conUsd = usdDisponible(paquete, tarifasPorEmpresa);

  const pago = usePagoPedido({
    motor,
    sedeSlug,
    empresaSlug: paquete.empresa_lider_slug,
    paqueteSlug: paquete.slug,
    formaPago: estado.formaPago,
    captchaToken: () => captcha.current,
    mensajeDeError: (err) => /* mensajeDeError existente de checkout-view, extraído a lib/errores.ts */ String(err),
    armarPayload: (checkoutId) => {
      const args = {
        checkoutId, paquete, componentes: estado.componentes, inicio: estado.inicio ?? minDate,
        hora: estado.hora, moneda: estado.moneda, contacto: estado.contacto, ref: leerRef(),
        zonaDePunto,
      };
      return motor === 'orden' ? armarPayloadOrden(args) : armarPayloadReserva(args);
    },
  });

  // ... render: <CheckoutStepper/>, pasos colapsables (datos, un GrupoServicio por servicio,
  // confirmar con <StripePanel/> en fase 'form', pagos con <StripePanel key=… /> en fase 'payment'),
  // pantallas de éxito/fallo/reanudando. Decide con `pedido.cargos.length` (N) y `paquete.permite_anticipo`.
  return null;
}
```
Notas al implementar: (a) la línea de `mensajeDeError` **no** se deja como `String(err)`: extrae `mensajeDeError` de `checkout-view.tsx` a `src/lib/errores.ts` (ya existe `mensajeDeFallo` allí; reutilízalo y añade el manejo de 503 → `checkout.paymentUnavailable`); (b) el `return null` del esqueleto se reemplaza por el render descrito en los criterios 1-13; (c) `montoInicial` alimenta `amountDueNow` cuando `paquete.permite_anticipo` y el cliente elige anticipo.

- [ ] **Paso 3: verificar.**

```bash
npx tsc --noEmit && npm run lint && npm test && npm run build
```
(`npm test` corre todas las suites del runner: las existentes y las nuevas.)
- [ ] **Paso 4: Commit (uno por componente ya terminado; al cerrar el shell):**

```bash
git add frontend/src/components/pedido frontend/src/app/[lang]/dictionaries
git commit -m "feat(frontend): checkout unificado de paquetes (PedidoPaquete y componentes)"
```

### Tarea 3.5: `/reservar` monta el checkout de paquete

**Files:**
- Modify: `frontend/src/app/[lang]/reservar/page.tsx`

**Interfaces:**
- Consumes: `PedidoPaquete` con props `{ lang, dict, paquete, sedeSlug, tarifasPorEmpresa, puntosPorEmpresa, minDate }` (3.4) y `getTraslados(empresaSlug)`.

- [ ] **Paso 1: implementar la rama de paquete.** Añade a los imports de la página `import { PedidoPaquete } from '@/components/pedido/pedido-paquete';` y `getTraslados, type TrasladosCatalogo` desde `@/lib/api`. En `reservar/page.tsx`, tras resolver `paquete` (el bloque existente que llama `getPaqueteDetalle`), y **antes** de armar `CheckoutView`:

```tsx
  if (paqueteSlug) {
    // Paquete no encontrado: 404, no caer a la pesca por defecto.
    if (!paquete) notFound();
    const empresasDeTraslado = [
      ...new Set(
        paquete.servicios_asociados
          .filter((c) => c.servicio.tipo_servicio === 'transporte')
          .map((c) => c.servicio.empresa_slug),
      ),
    ];
    const catalogos = await Promise.all(
      empresasDeTraslado.map((empresa) => getTraslados(empresa).catch(() => null)),
    );
    const tarifasPorEmpresa: Record<string, TrasladosCatalogo['tarifas']> = {};
    const puntosPorEmpresa: Record<string, TrasladosCatalogo['puntos_encuentro']> = {};
    empresasDeTraslado.forEach((empresa, i) => {
      tarifasPorEmpresa[empresa] = catalogos[i]?.tarifas ?? [];
      puntosPorEmpresa[empresa] = catalogos[i]?.puntos_encuentro ?? [];
    });
    return (
      <PedidoPaquete
        lang={lang}
        dict={dict}
        paquete={paquete}
        sedeSlug={paquete.sede_slug}
        tarifasPorEmpresa={tarifasPorEmpresa}
        puntosPorEmpresa={puntosPorEmpresa}
        minDate={minDate}
      />
    );
  }
```
Elimina de la página el recorrido de `getSedes()` por todas las sedes cuando no hay `sede` (el enlace nuevo siempre trae `sede`); si falta, responde `notFound()`.

- [ ] **Paso 2: verificar** `npx tsc --noEmit && npm run lint && npm run build`.
- [ ] **Paso 3: Commit**

```bash
git add frontend/src/app
git commit -m "feat(frontend): /reservar monta el checkout unificado cuando hay paquete"
```

### Tarea 3.6: Smoke sin navegador

**Files:** ninguno.

- [ ] **Paso 1: levantar** backend (`cd backend && $PY manage.py runserver 8000`, con `seed_local_demo` ya corrido, ver backend 5.1) y frontend (`npm run dev`).
- [ ] **Paso 2: comprobar con `curl`** que ambos casos renderizan el mismo layout:

```bash
for slug in fin-de-semana-la-paz pesca-traslado; do
  curl -s -o /tmp/$slug.html -w "$slug %{http_code}\n" \
    "http://localhost:3000/es/reservar?paquete=$slug&sede=la-paz&moneda=MXN"
done
```
Esperado: `200` los dos. Comprueba en cada HTML: aparece el título `pedido.title`, un grupo por servicio, **y no** aparece ningún `input type="date"` ni un campo de fecha de salida. Solo en `pesca-traslado` aparece `pedido.chargesNotice`.
- [ ] **Paso 3: comprobar que `/reservar-paquete` ya no se usa:** `grep -rn "reservar-paquete" src` solo debe dar el resultado de la Tarea 4.1 pendiente.
- [ ] **Paso 4: reportar** al dueño lo verificado y **pedir su revisión visual** de las cuatro pantallas (datos/grupos, confirmar con aviso, pago 1, pago 2) en móvil y escritorio; con tarjetas de prueba `4242…` (éxito) y `4000000000009995` (rechazo) para recorrer el pago de dos empresas. Nada de esto se da por bueno sin su visto bueno.

**STOP DURO — Cierre de la Sección 3.** Reportar y esperar la revisión visual del dueño antes de la Sección 4.

---

## Sección 4 — Limpieza y cierre

### Tarea 4.1: Eliminar la ruta y el componente antiguos

**Files:**
- Delete: `frontend/src/app/[lang]/reservar-paquete/` (página y `loading.tsx` si existe), `frontend/src/components/paquete-checkout.tsx`
- Modify: `frontend/src/app/[lang]/dictionaries/{es,en}.json` (quitar `meta.reservarPaquete` y `paqueteCheckout`, tras pasar sus claves útiles a `pedido.*`)
- Modify: `frontend/src/lib/pricing-paquete.ts` (`esPaqueteCruzaEmpresa` solo si ya no lo usa nadie)

- [ ] **Paso 1: borrar y buscar huérfanos.**

```bash
git rm -r "src/app/[lang]/reservar-paquete" src/components/paquete-checkout.tsx
grep -rn "reservar-paquete\|paquete-checkout\|PaqueteCheckout\|paqueteCheckout\|esPaqueteCruzaEmpresa\|reservarPaquete" src tests
```
Esperado: sin resultados (también en `frontend/tests/`, donde vivía la suite vieja de `booking-href`, ya actualizada en la Tarea 2.1); si `esPaqueteCruzaEmpresa` solo lo usaba `booking-href.ts` (ya no), elimínala junto con su test si existiera. Elimina el cast temporal de la Tarea 1.1 (el archivo ya no existe).
- [ ] **Paso 2: verificar** `npx tsc --noEmit && npm run lint && npm test && npm run build`.
- [ ] **Paso 3: Commit**

```bash
git add -A frontend
git commit -m "refactor(frontend): eliminar /reservar-paquete y paquete-checkout"
```

### Tarea 4.2: `CheckoutView` sin rama de paquete y con anticipo explícito

**Files:**
- Modify: `frontend/src/components/checkout-view.tsx`
- Modify: `frontend/src/app/[lang]/reservar/page.tsx` (deja de pasar `paquete` a `CheckoutView`)

**Interfaces:**
- Consumes: `servicio.permite_anticipo`, `servicio.porcentaje_anticipo` (1.1).

- [ ] **Paso 1: quitar la rama de paquete** (ya vive en `PedidoPaquete`): props `paqueteId`, `paqueteNombre`, `paquete`, `initialFechaSalida`; el `catalogoUnificado` de paquete (queda `servicio?.personalizaciones ?? []`), `tieneHospedaje`, `fechaSalida*`, el bloque JSX del "Check-out" con `<input type="date">`, `calcularPrecioPaquete` y el uso de `porcentaje_anticipo` del paquete (L721). Búscalos con:

```bash
grep -n "paquete\|tieneHospedaje\|fechaSalida\|fecha_salida" src/components/checkout-view.tsx
```
Un servicio suelto de hospedaje (`por_noche`) **sí** conserva elegir noches: no borres esa lógica, solo la que dependa de `paquete`; para ese caso reemplaza el `<input type="date">` por `DateField` (regla de frontend).
- [ ] **Paso 2: anticipo explícito para el servicio suelto.** Pasa `permiteAnticipo={servicio?.permite_anticipo ?? true}` a `StripePanel` como `formaPagoDisponible`, usa `servicio.porcentaje_anticipo` para el `amountDueNow`, y si no lo permite fuerza `formaPago = 'completo'`. Aplica lo mismo en `traslado-view.tsx` con `catalogo.servicio.permite_anticipo` (añadir a `TrasladosCatalogo['servicio']` en `api.ts`).
- [ ] **Paso 3: verificar y commit.**

```bash
npx tsc --noEmit && npm run lint && npm test && npm run build
git add frontend/src
git commit -m "refactor(frontend): CheckoutView solo para servicios sueltos; anticipo explicito"
```

### Tarea 4.3: Documentación y cierre

**Files:**
- Modify: `frontend/CLAUDE.md`

- [ ] **Paso 1:** reemplaza las secciones "Estado", "Checkout de paquete cruza-empresa" y las menciones a `/reservar-paquete` por una sección "Checkout unificado de paquetes": ruta única, dos motores tras un hook (`use-pago-pedido.ts`), reglas R1-R5 (qué se muestra cuándo), calendario/personas definidos por el paquete, USD, anticipo (solo N=1 y si `permite_anticipo`), y cómo correr `npm test`. Elimina lo que ya no es cierto ("un `StripePanel`/`Elements` a la vez, desmontado por empresa" sigue siendo cierto; "el catálogo dirige aquí los paquetes con componentes de empresas distintas" no).
- [ ] **Paso 2: gate final.**

```bash
npx tsc --noEmit && npm run lint && npm test && npm run build
```
- [ ] **Paso 3: repaso de diffs** (checklist): (a) ninguna cifra de dinero, noches o personas hardcodeada; (b) ningún `<input type="date">` ni `<select>` nuevo; (c) los dos diccionarios tienen las mismas claves `pedido.*`; (d) `grep -rn "reservar-paquete" src` vacío; (e) sin `console.log`; (f) `git diff feat/transporte-multi-empresa --stat` solo toca los archivos del mapa.
- [ ] **Paso 4: Commit**

```bash
git add frontend/CLAUDE.md
git commit -m "docs(frontend): documentar el checkout unificado de paquetes"
```
- [ ] **Paso 5: anotar** en este plan el HEAD final y resultados. Reportar al dueño, junto con las pendientes de la §9 del spec (verificación del texto del banco, texto legal de lugares no usados, precios USD). **Sin push ni merge sin su luz verde.**

**STOP DURO — Cierre del frontend.**

---

## Sección 5 — Continuar reservación

Implementa spec §10/§10.1 (APROBADA). Depende de la Sección 6 del plan de backend (endpoints de
resumen/cancelar). "Autorizado" pasa a "retenido" en **todo** lo visible al cliente, incluida la
matriz de pagos de la Sección 3 (§10.1, decisión del dueño): en `EncabezadoPago`/`pedido.authorized`
usa "retenido" en vez de "autorizado".

### Tarea 5.1: Puntero de pendientes (`lib/pendientes.ts`)

**Files:**
- Create: `frontend/src/lib/pendientes.ts`
- Modify: `frontend/tests/run-hub-tests.cjs` (registra `'pendientes'`)
- Test: `frontend/tests/pendientes.test.cjs`

**Interfaces:**
- Produces:
  - `type Pendiente = { tipo: 'reserva' | 'orden'; checkoutId: string; ordenId?: number; sedeSlug?: string; empresaSlug: string; productoSlug: string; productoNombre: string; ruta: string; actualizadoEn: string; tieneDineroRetenido?: boolean }`.
    `tieneDineroRetenido` extiende el esquema del puntero descrito en spec §10, solución 1 (que solo
    lista `{tipo, checkoutId, ordenId?, sedeSlug, empresaSlug, productoSlug, productoNombre, ruta,
    actualizadoEn}`). No es un dato personal (booleano, no un monto). **Aprobado por el dueño
    (2026-09-23)**: se agrega el campo y se implementa la política de expulsión consciente de dinero
    retenido (hallazgo #10 del review); sin él, la promesa de spec §10 punto 7 ("Sin dinero retenido,
    la de menor antigüedad cede el lugar") es imposible de cumplir, porque el puntero no sabría si
    tiene dinero encima.
  - `guardarPendiente(p: Pendiente): void` — upsert por `checkoutId`; mantiene como máximo 3,
    descartando primero, entre los candidatos a salir, cualquiera con `tieneDineroRetenido !== true`
    (el más viejo de esos); si los tres tienen dinero retenido, no se descarta ninguno y el cuarto
    entra igual (mejor una lista de 4 corta que perder silenciosamente un pendiente con dinero — ver
    nota de arriba si el campo no se aprueba); vigencia 7 días (se filtran al leer, no hace falta un
    timer); se actualiza (`actualizadoEn` y `tieneDineroRetenido`) cada vez que el checkout que lo
    escribió confirma un avance real en el servidor, no en cada render.
  - `listarPendientes(): Pendiente[]` — ordenados por `actualizadoEn` desc, ya filtrados por vigencia
    y por forma válida (ver Paso 3: una entrada con campos faltantes o de tipo incorrecto se descarta
    en silencio, nunca lanza ni rompe el resto de la lista — hallazgo #12).
  - `borrarPendiente(checkoutId: string): void`.
  - Todas las funciones envuelven `localStorage` en `try/catch` (modo privado, cuota llena) y no
    lanzan nunca, **incluido contenido JSON válido pero con forma inválida** (ej. `[null]`, objetos sin
    los campos requeridos) — hallazgo #12: antes solo el `JSON.parse` estaba protegido, no el acceso a
    los campos de cada entrada.

- [ ] **Paso 1: prueba que falla.** Registra `'pendientes': ['src/lib/pendientes.ts', 'PENDIENTES_TEST_OUT'],`
  en `run-hub-tests.cjs`. `frontend/tests/pendientes.test.cjs` (usa un `localStorage` de Node —
  ninguna suite existente lo necesitaba; ver Paso 3 del código para el shim mínimo):

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

globalThis.localStorage = (() => {
  let store = {};
  return {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
    clear: () => { store = {}; },
  };
})();

const p = require(path.join(process.env.PENDIENTES_TEST_OUT, 'lib/pendientes.js'));

beforeEach(() => localStorage.clear());

const pendiente = (over = {}) => ({
  tipo: 'reserva', checkoutId: 'chk-1', empresaSlug: 'sal-y-sol', productoSlug: 'pesca-deportiva',
  productoNombre: 'Pesca deportiva', ruta: '/es/reservar?servicio=pesca-deportiva',
  actualizadoEn: new Date().toISOString(), ...over,
});

test('guarda y lista', () => {
  p.guardarPendiente(pendiente());
  assert.equal(p.listarPendientes().length, 1);
});

test('upsert por checkoutId no duplica', () => {
  p.guardarPendiente(pendiente());
  p.guardarPendiente(pendiente({ productoNombre: 'Pesca (actualizada)' }));
  const lista = p.listarPendientes();
  assert.equal(lista.length, 1);
  assert.equal(lista[0].productoNombre, 'Pesca (actualizada)');
});

test('mas reciente primero', () => {
  // Fechas relativas a Date.now(), no absolutas: hallazgo #11 del review — fechas
  // fijas de 2026 dejan de ser "vigentes" (ventana de 7 dias) en cuanto el test
  // corre despues de esa fecha, y este mismo repo ya esta en 2026.
  const ahora = Date.now();
  p.guardarPendiente(pendiente({ checkoutId: 'a', actualizadoEn: new Date(ahora - 60_000).toISOString() }));
  p.guardarPendiente(pendiente({ checkoutId: 'b', actualizadoEn: new Date(ahora).toISOString() }));
  assert.deepEqual(p.listarPendientes().map((x) => x.checkoutId), ['b', 'a']);
});

test('tope de 3, descarta el mas viejo sin dinero retenido', () => {
  const ahora = Date.now();
  ['a', 'b', 'c', 'd'].forEach((id, i) => {
    p.guardarPendiente(pendiente({
      checkoutId: id, actualizadoEn: new Date(ahora - (4 - i) * 60_000).toISOString(),
    }));
  });
  const lista = p.listarPendientes();
  assert.equal(lista.length, 3);
  assert.ok(!lista.some((x) => x.checkoutId === 'a'));
});

test('tope de 3 no descarta uno con dinero retenido; el 4to entra igual', () => {
  const ahora = Date.now();
  p.guardarPendiente(pendiente({ checkoutId: 'a', actualizadoEn: new Date(ahora - 4 * 60_000).toISOString(), tieneDineroRetenido: true }));
  p.guardarPendiente(pendiente({ checkoutId: 'b', actualizadoEn: new Date(ahora - 3 * 60_000).toISOString(), tieneDineroRetenido: true }));
  p.guardarPendiente(pendiente({ checkoutId: 'c', actualizadoEn: new Date(ahora - 2 * 60_000).toISOString(), tieneDineroRetenido: true }));
  p.guardarPendiente(pendiente({ checkoutId: 'd', actualizadoEn: new Date(ahora - 1 * 60_000).toISOString() }));
  const lista = p.listarPendientes();
  assert.equal(lista.length, 4);
  assert.ok(lista.some((x) => x.checkoutId === 'a'));
});

test('vencido a los 7 dias no aparece', () => {
  const viejo = new Date(Date.now() - 8 * 24 * 60 * 60 * 1000).toISOString();
  p.guardarPendiente(pendiente({ actualizadoEn: viejo }));
  assert.equal(p.listarPendientes().length, 0);
});

test('borrar quita solo ese', () => {
  p.guardarPendiente(pendiente({ checkoutId: 'a' }));
  p.guardarPendiente(pendiente({ checkoutId: 'b' }));
  p.borrarPendiente('a');
  assert.deepEqual(p.listarPendientes().map((x) => x.checkoutId), ['b']);
});

test('localStorage roto no lanza', () => {
  const real = globalThis.localStorage;
  globalThis.localStorage = { getItem() { throw new Error('no'); }, setItem() { throw new Error('no'); } };
  assert.doesNotThrow(() => p.guardarPendiente(pendiente()));
  assert.deepEqual(p.listarPendientes(), []);
  globalThis.localStorage = real;
});

test('JSON valido pero con forma invalida no lanza y se descarta', () => {
  // Hallazgo #12: '[null]' es JSON valido (JSON.parse no lanza) pero cada
  // funcion que accedia a los campos de la entrada si lanzaba TypeError.
  localStorage.setItem('salysol:pendientes:v1', '[null]');
  assert.doesNotThrow(() => p.listarPendientes());
  assert.deepEqual(p.listarPendientes(), []);
  assert.doesNotThrow(() => p.guardarPendiente(pendiente()));
  assert.equal(p.listarPendientes().length, 1);
});

test('entrada sin checkoutId se descarta sin tumbar el resto', () => {
  localStorage.setItem('salysol:pendientes:v1', JSON.stringify([
    pendiente({ checkoutId: 'valida' }),
    { tipo: 'reserva', actualizadoEn: new Date().toISOString() }, // sin checkoutId
  ]));
  assert.deepEqual(p.listarPendientes().map((x) => x.checkoutId), ['valida']);
});
```

- [ ] **Paso 2: verla fallar** — `node tests/run-hub-tests.cjs pendientes` → error de compilación
  (módulo inexistente).

- [ ] **Paso 3: implementar** — `frontend/src/lib/pendientes.ts`:

```ts
const CLAVE = 'salysol:pendientes:v1';
const VIGENCIA_MS = 7 * 24 * 60 * 60 * 1000;
const TOPE = 3;

export type Pendiente = {
  tipo: 'reserva' | 'orden';
  checkoutId: string;
  ordenId?: number;
  sedeSlug?: string;
  empresaSlug: string;
  productoSlug: string;
  productoNombre: string;
  ruta: string;
  actualizadoEn: string;
  tieneDineroRetenido?: boolean;
};

// Hallazgo #12: JSON.parse no lanza con '[null]' — cada entrada del array se valida
// por separado antes de confiar en su forma. Campos opcionales no se exigen.
function esPendienteValido(x: unknown): x is Pendiente {
  if (typeof x !== 'object' || x === null) return false;
  const p = x as Record<string, unknown>;
  return (
    (p.tipo === 'reserva' || p.tipo === 'orden')
    && typeof p.checkoutId === 'string' && p.checkoutId.length > 0
    && typeof p.empresaSlug === 'string'
    && typeof p.productoSlug === 'string'
    && typeof p.productoNombre === 'string'
    && typeof p.ruta === 'string'
    && typeof p.actualizadoEn === 'string'
  );
}

function leerCrudo(): Pendiente[] {
  try {
    const crudo = localStorage.getItem(CLAVE);
    if (!crudo) return [];
    const datos = JSON.parse(crudo);
    return Array.isArray(datos) ? datos.filter(esPendienteValido) : [];
  } catch {
    return [];
  }
}

function escribir(lista: Pendiente[]): void {
  try {
    localStorage.setItem(CLAVE, JSON.stringify(lista));
  } catch {
    // modo privado o cuota llena: el aviso simplemente no persiste
  }
}

function vigente(p: Pendiente): boolean {
  const t = new Date(p.actualizadoEn).getTime();
  return Number.isFinite(t) && Date.now() - t < VIGENCIA_MS;
}

export function listarPendientes(): Pendiente[] {
  return leerCrudo()
    .filter(vigente)
    .sort((a, b) => new Date(b.actualizadoEn).getTime() - new Date(a.actualizadoEn).getTime());
}

export function guardarPendiente(p: Pendiente): void {
  const resto = leerCrudo().filter((x) => x.checkoutId !== p.checkoutId && vigente(x));
  const ordenados = [p, ...resto]
    .sort((a, b) => new Date(b.actualizadoEn).getTime() - new Date(a.actualizadoEn).getTime());
  if (ordenados.length <= TOPE) {
    escribir(ordenados);
    return;
  }
  // Hallazgo #10: expulsar primero, entre los que sobran, al mas viejo SIN dinero
  // retenido. Si todos los candidatos a salir tienen dinero, no se descarta ninguno
  // (la lista puede crecer a 4 en ese caso raro; mejor eso que perder un pendiente
  // con dinero sin que el cliente lo vea).
  const sobran = ordenados.slice(TOPE);
  const descartable = [...sobran].reverse().find((x) => !x.tieneDineroRetenido);
  if (!descartable) {
    escribir(ordenados);
    return;
  }
  escribir(ordenados.filter((x) => x.checkoutId !== descartable.checkoutId));
}

export function borrarPendiente(checkoutId: string): void {
  escribir(leerCrudo().filter((x) => x.checkoutId !== checkoutId));
}
```

**Sobre `tieneDineroRetenido`:** ver la nota de Interfaces arriba — este campo extiende el esquema
del puntero aprobado en spec §10. Si el dueño no lo aprueba antes de implementar esta tarea, quita el
campo del tipo `Pendiente`, la rama de expulsión de arriba se simplifica a un `slice(0, TOPE)` llano
(como estaba antes de esta revisión) y hay que ajustar spec §10 punto 7 para que ya no prometa
proteger al que tiene dinero retenido.

- [ ] **Paso 4: verlas pasar y commit**

```bash
node tests/run-hub-tests.cjs pendientes && npx tsc --noEmit && npm run lint
git add frontend/src/lib/pendientes.ts frontend/tests/pendientes.test.cjs frontend/tests/run-hub-tests.cjs
git commit -m "feat(frontend): puntero de checkouts pendientes en localStorage"
```

### Tarea 5.2: Contrato de resumen y de cancelar en `api.ts`

**Files:**
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces:
  - `type Situacion = 'sin_pago' | 'pago_en_proceso' | 'retenido_parcial' | 'retenido_total' | 'confirmando_cobro' | 'confirmada' | 'cancelada_liberada' | 'cancelada_devolucion_solicitada' | 'cancelada_devolucion_por_confirmar' | 'expirada' | 'no_existe'`.
  - `type ResumenReserva = { situacion: Situacion; producto: string; monto: string | null; moneda: string; forma_pago: string; folio: number; vence_en: null }`.
  - `type ResumenOrden = { situacion: Situacion; producto: string; moneda: string; forma_pago: string; montos: { empresa: string; monto: string | null; monto_reembolsado: string | null; estado: string | null }[]; folio: number; vence_en: string | null; actualizado_en: string }`
    (contrato ampliado tras el hallazgo #3 del review: la versión original solo traía
    `{empresa, monto}` y no alcanzaba para que `pendientes-texto.ts` (5.3) distinguiera un pago
    retenido de uno pendiente, ni mostrara moneda/reembolso — coincide con el backend corregido en el
    plan de backend, Tarea 6.2).
  - `getResumenReserva(checkoutId: string, empresaSlug: string): Promise<ResumenReserva>` (404 se
    propaga como `ApiError`, quien llama lo captura).
  - `getResumenOrden(checkoutId: string, sedeSlug: string): Promise<ResumenOrden>`.
  - `cancelarOrdenPublica(sedeSlug: string, ordenId: number, checkoutId: string): Promise<ResumenOrden>`
    — devuelve el **mismo tipo** que `getResumenOrden` (no `{situacion}`: el backend corregido
    (Tarea 6.2) ahora responde el contrato completo para que `textoDeSituacion` (5.3) pueda formatear
    el resultado de cancelar sin una llamada extra — hallazgo #6). Puede resolver con un `ApiError` de
    status 409 (la orden ya se había capturado): quien llama trata ese caso igual que una respuesta
    200 con `situacion: 'confirmada'`, leyendo `err.detail` como el mismo `ResumenOrden` (ver
    `ApiError.detail` en este archivo).

- [ ] **Paso 1: implementar** (sin prueba: son llamadas de red delgadas, cubiertas por `tsc` y por el
  smoke de la Tarea 5.5). Añade al final de `api.ts`:

```ts
export type Situacion =
  | 'sin_pago' | 'pago_en_proceso' | 'retenido_parcial' | 'retenido_total' | 'confirmando_cobro'
  | 'confirmada' | 'cancelada_liberada' | 'cancelada_devolucion_solicitada'
  | 'cancelada_devolucion_por_confirmar' | 'expirada' | 'no_existe';

export type ResumenReserva = {
  situacion: Situacion; producto: string; monto: string | null; moneda: string; forma_pago: string;
  folio: number; vence_en: null;
};
export type ResumenOrden = {
  situacion: Situacion; producto: string; moneda: string; forma_pago: string;
  montos: { empresa: string; monto: string | null; monto_reembolsado: string | null; estado: string | null }[];
  folio: number; vence_en: string | null; actualizado_en: string;
};

export const getResumenReserva = (checkoutId: string, empresaSlug: string) =>
  request<ResumenReserva>(`/api/reservas/resumen/?checkout_id=${checkoutId}`, undefined, empresaSlug);

export const getResumenOrden = (checkoutId: string, sedeSlug: string) =>
  request<ResumenOrden>(`/api/ordenes/resumen/?checkout_id=${checkoutId}`, undefined, sedeSlug);

export const cancelarOrdenPublica = (sedeSlug: string, ordenId: number, checkoutId: string) =>
  request<ResumenOrden>(`/api/ordenes/${ordenId}/cancelar/`, {
    method: 'POST', body: JSON.stringify({ checkout_id: checkoutId }),
  }, sedeSlug);
```
**Hallazgo #1 del review, ya corregido arriba:** la versión original pasaba la sede/empresa
concatenada dentro del `path` (`/api/sedes/${sedeSlug}/...`, `/api/${sedeSlug}/...`) en vez de como
tercer argumento de `request()`; como `request()` **también** antepone el slug automáticamente
(`views.ts:118-128`), el resultado real era una URL con la sede duplicada
(`/api/sal-y-sol/la-paz/ordenes/7/cancelar/`), que no coincide con ninguna ruta real. El patrón
correcto —usado arriba y ya establecido por `crearOrden`/`getOrden` en este mismo archivo— es pasar
el path **sin** el slug y dejar que `request()` lo anteponga vía su tercer parámetro. No repetir el
error original: probar la URL final armada (mock de `fetch`), no solo que `tsc` compile.

- [ ] **Paso 2: verificar y commit**

```bash
npx tsc --noEmit && npm run lint
git add frontend/src/lib/api.ts
git commit -m "feat(frontend): tipos y llamadas de resumen/cancelar para Continuar reservacion"
```

### Tarea 5.3: Textos y matriz de estados (`lib/pendientes-texto.ts`)

**Files:**
- Create: `frontend/src/lib/pendientes-texto.ts`
- Modify: `frontend/tests/run-hub-tests.cjs` (registra `'pendientes-texto'`)
- Test: `frontend/tests/pendientes-texto.test.cjs`
- Modify: `frontend/src/app/[lang]/dictionaries/{es,en}.json` (claves `continuar.*`)

**Interfaces:**
- Consumes: `Situacion`, `ResumenReserva`, `ResumenOrden` (5.2).
- Produces:
  - `type RegistroVisual = 'en_curso' | 'con_dinero' | 'informativo'`.
  - `type TextoSituacion = { registro: RegistroVisual; linea1: string; linea2: string; principal: string; secundaria: string | null; requiereConfirmacion: boolean }`.
  - `textoDeSituacion(dict: Dictionary['continuar'], resumen: ResumenReserva | ResumenOrden): TextoSituacion`
    — implementa **literalmente** la tabla de la spec §10.1; no reinterpreta, solo formatea montos y
    fechas (`vence_en`) y singular/plural de `montos`.

- [ ] **Paso 1: prueba que falla** — registra la suite y crea `frontend/tests/pendientes-texto.test.cjs`
  con al menos un caso por fila de la tabla del spec (13 casos: las 11 de la tabla + `retenido_total`
  y sin conexión/error, estos dos últimos se cubren en el componente, Tarea 5.4, no aquí). Ejemplo de
  dos casos representativos (replica el patrón para los 11 restantes contra la tabla exacta):

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const t = require(path.join(process.env.PENDIENTES_TEXTO_TEST_OUT, 'lib/pendientes-texto.js'));

const DICT = {
  sinPago: '{producto} · Tus datos están guardados · Aún no has pagado',
  retenidoParcial: '{producto} · Pago 1 de 2 retenido: {montoHecho} en {empresaHecha} · Falta {montoFalta} a {empresaFalta}. Se cancela si no terminas antes de las {vence}.',
  // ... resto de claves 1:1 con la tabla del spec §10.1
  botonContinuar: 'Continuar reservación',
  botonPagarPendiente: 'Pagar {monto} (pago {n} de {total})',
  botonCancelarRetenido: 'Cancelar y liberar lo retenido',
  botonDescartar: 'Descartar',
};

test('sin_pago: registro en_curso, botón continuar', () => {
  const r = t.textoDeSituacion(DICT, {
    situacion: 'sin_pago', producto: 'Pesca deportiva', monto: null,
    moneda: 'MXN', forma_pago: 'completo', folio: 1, vence_en: null,
  });
  assert.equal(r.registro, 'en_curso');
  assert.equal(r.linea1, 'Pesca deportiva · Tus datos están guardados · Aún no has pagado');
  assert.equal(r.principal, 'Continuar reservación');
  assert.equal(r.secundaria, 'Descartar');
  assert.equal(r.requiereConfirmacion, false);
});

test('retenido_parcial de orden: registro con_dinero, muestra falta y vence', () => {
  // Forma del contrato ampliado tras el hallazgo #3 del review de backend: cada
  // entrada de `montos` trae tambien `monto_reembolsado` y `estado` (estado_pi).
  const resumen = {
    situacion: 'retenido_parcial', producto: 'Pesca + Traslado', moneda: 'MXN', forma_pago: 'completo', folio: 7,
    montos: [
      { empresa: 'Sal y Sol', monto: '6400.00', monto_reembolsado: null, estado: 'requires_capture' },
      { empresa: 'Transportes La Paz', monto: null, monto_reembolsado: null, estado: null },
    ],
    vence_en: '2026-10-15T15:40:00-07:00', actualizado_en: '2026-10-14T15:40:00-07:00',
  };
  const r = t.textoDeSituacion(DICT, resumen);
  assert.equal(r.registro, 'con_dinero');
  assert.match(r.linea1, /Sal y Sol/);
  assert.match(r.linea1, /Transportes La Paz/);
  assert.equal(r.requiereConfirmacion, true); // "Cancelar" pasa por confirmación
});
```

- [ ] **Paso 2: verla fallar** — módulo inexistente.

- [ ] **Paso 3: diccionarios.** Añade a `es.json`/`en.json`, junto a `pedido`, un bloque `continuar`
  con **una clave por fila de la tabla del spec §10.1** (11 filas + textos de botones + hoja de
  confirmación de cancelar + "y N más" + fallback sin conexión/error). Usa exactamente el texto de la
  tabla del spec; no lo redactes de nuevo. **Reinicia `npm run dev` tras editar.**

- [ ] **Paso 4: implementar** — `frontend/src/lib/pendientes-texto.ts`. Función de formateo puro que
  aplica la tabla de la spec (una rama por `situacion`, sin lógica de negocio: la decide el backend).
  El cuerpo exacto depende del diccionario final del Paso 3; usa `dict['continuar'][...]` con las
  claves ahí definidas y sustituye `{producto}`, `{monto}`, `{empresa}`, `{vence}` con
  `String.prototype.replace` (mismo patrón que `checkout.stepOf` en `checkout-view.tsx`). Cada rama
  fija `registro` según la tabla (en_curso / con_dinero / informativo) y `requiereConfirmacion = true`
  únicamente para las situaciones con botón "Cancelar y liberar lo retenido".

- [ ] **Paso 5: verlas pasar y commit**

```bash
node tests/run-hub-tests.cjs pendientes-texto && npx tsc --noEmit && npm run lint
git add frontend/src/lib/pendientes-texto.ts frontend/tests frontend/src/app/[lang]/dictionaries
git commit -m "feat(frontend): textos de la matriz de situaciones (spec 10.1)"
```

### Tarea 5.4: Componente `ContinuarReservacion` (banda y chip)

**Files:**
- Create: `frontend/src/components/continuar-reservacion.tsx`
- Modify: `frontend/src/components/site-header.tsx` (monta el chip)
- Modify: `frontend/src/app/[lang]/page.tsx` (monta la banda en la portada, encima del hero)

**Interfaces:**
- Produces: `ContinuarReservacion({ lang, dict, variante: 'banda' | 'chip' })`. Comportamiento
  (criterios de aceptación, construidos con `design-taste-frontend`):
  1. Al montar, lee `listarPendientes()`. Si está vacío, **no renderiza nada** (R2: cero píxeles).
  2. Para el más reciente, consulta `getResumenReserva`/`getResumenOrden` según `tipo`. Mientras
     responde, no se muestra nada (nunca un esqueleto que ocupe espacio y desaparezca: violaría R2).
  3. Si la respuesta es `no_existe` (404): **no** se borra el puntero ni se oculta en silencio — S:361
     exige mostrar la fila `no_existe` de la matriz ("No encontramos tu reservación de {producto}...")
     con sus dos acciones ("Empezar de nuevo" / "Escribirnos por WhatsApp"). Recién al hacer clic en
     cualquiera de las dos se llama `borrarPendiente`. (Hallazgo #6 del review: la versión anterior de
     este punto contradecía S:361 al ocultar sin mostrar nada.) Si en cambio la situación real es
     `expirada`, sigue el mismo tratamiento que su fila de la matriz (dos variantes, con/sin dinero).
  4. Si hay respuesta válida, `textoDeSituacion` decide el texto y el registro visual (5.3). La banda
     ocupa una franja bajo el header; el chip es compacto en el header, mismo texto abreviado a
     `linea1` sin `linea2`.
  5. Si `listarPendientes().length > 1`, un enlace "y N más" abre una hoja con el resto (máx. 3),
     misma anatomía por fila, sin resumen adicional (evita N llamadas de red innecesarias: solo trae
     resumen del primero al cargar; los demás se resuelven al expandir).
  6. Clic en el principal **se ramifica por `situacion`**, según la columna "Al hacer clic" de la
     tabla §10.1 (hallazgo #6: la versión anterior de este punto sembraba la sesión y navegaba al
     producto para **todas** las situaciones por igual, incluidas las que la tabla pide tratar
     distinto):
     - `sin_pago` / `retenido_parcial` / `retenido_total` / `confirmando_cobro` / `pago_en_proceso`:
       sembrar `sessionStorage` con la llave que cada checkout ya usa (`salysol:orden:<paqueteSlug>`
       para `PedidoPaquete`/reservas de paquete, la de `CheckoutView`/`TrasladoView` para servicios
       sueltos — usa **la misma clave y forma** que cada uno lee al montar, ver Tarea 5.5) con
       `{ checkoutId, ordenId? }`, y `router.push(pendiente.ruta)`.
     - `confirmada`: **no** hay página de "mi reservación" hoy en el sitio. Hasta que el dueño decida
       construir una (fuera de alcance de este plan), el clic abre la misma hoja de detalle inline que
       usa `no_existe`/`cancelada_devolucion_solicitada` (ver abajo) con los datos ya traídos del
       resumen — sin navegar a ningún lado. **Marca esto explícitamente al dueño como una reducción de
       alcance**, no como la experiencia "Ver mi reservación" que describe S:355.
     - `cancelada_liberada` / `expirada`: "Reservar de nuevo" navega al producto **con identidad
       nueva**: **no** siembra el `checkoutId` viejo (a diferencia de la rama de arriba) — el checkout
       arranca de cero, como cualquier visita nueva a ese producto. Sembrar el `checkoutId` cancelado
       reabriría un checkout que el servidor ya cerró.
     - `cancelada_devolucion_solicitada`: como no existe una página de "detalle de orden/reserva" hoy,
       "Ver detalle" expande la misma hoja inline con folio, montos y estado que ya trajo el resumen,
       sin navegar. Mismo señalamiento de alcance que en `confirmada`.
     - `cancelada_devolucion_por_confirmar`: "Escribir por WhatsApp" abre `wa.me` con el folio
       prellenado (mismo patrón que `CheckoutAbandonadoAdmin.contacto`, pero del lado del cliente:
       enlace directo, sin pasar por el admin).
     - `no_existe`: ver punto 3.
  7. "Cancelar y liberar lo retenido": abre la hoja de confirmación del spec §10.1 (texto exacto ahí);
     al confirmar llama `cancelarOrdenPublica`, muestra el resultado real (`textoDeSituacion` sobre la
     respuesta). **Solo** si el resultado es `cancelada_liberada` se hace `borrarPendiente` + ocultar
     tras 3s; si el resultado es `cancelada_devolucion_por_confirmar`, el aviso (folio + "Escribir por
     WhatsApp") se queda visible hasta que el cliente toque "Entendido" — hallazgo #6: S:358 exige
     conservar folio y contacto hasta cierre explícito, y ocultar a los 3s independientemente del
     resultado se lo salta.
  8. "Descartar" (sin dinero): `borrarPendiente` inmediato, con "Deshacer" 8s (guarda temporalmente el
     pendiente borrado en memoria del componente, no en `localStorage`, para el deshacer).
  9. Estado sin conexión (`navigator.onLine === false` o el fetch falla por red): texto fijo del
     diccionario ("Sin conexión..."), botón "Reintentar" que repite la consulta; nunca inventa una
     `situacion`.

- [ ] **Paso 1: construir el componente** con `design-taste-frontend`, siguiendo los 9 puntos de
  arriba y el diseño de banda/chip de la spec §3/§10. Reutiliza `CheckoutSectionCard`/patrones de
  `site-header.tsx` para que visualmente encaje. **Antes de construir el punto 6**, confirma con el
  dueño la reducción de alcance marcada ahí (hoja inline en vez de páginas "mi reservación"/"detalle"
  que no existen todavía) — es una decisión de producto, no una que este plan deba tomar sola.
- [ ] **Paso 2: montar.** En `site-header.tsx`, el chip junto al selector de idioma (o donde el diseño
  aprobado indique). En `[lang]/page.tsx` (portada), la banda entre el header y el hero — **sin**
  tocar el hero mismo (coordina con la revisión visual del hub en curso: el componente es
  autocontenido y no depende de cómo quede el hero).
- [ ] **Paso 3: verificar** `npx tsc --noEmit && npm run lint && npm run build`.
- [ ] **Paso 4: Commit**

```bash
git add frontend/src/components/continuar-reservacion.tsx frontend/src/components/site-header.tsx "frontend/src/app/[lang]/page.tsx"
git commit -m "feat(frontend): componente Continuar reservacion (banda y chip)"
```

### Tarea 5.5: Los tres checkouts escriben y borran el puntero

**Files:**
- Modify: `frontend/src/components/checkout-view.tsx`
- Modify: `frontend/src/components/traslado-view.tsx`
- Modify: `frontend/src/components/pedido/use-pago-pedido.ts` (de la Sección 3 del propio plan)
- Modify: `backend/apps/payments/views.py` (`EstadoReservaView`, rama `pendiente_pago` — añade detalle
  de traslado)

**Interfaces:**
- Consumes: `guardarPendiente`, `borrarPendiente` (5.1).
- Produces: cada checkout llama `guardarPendiente(...)` justo después de que el servidor confirma la
  reserva/orden por primera vez (mismo punto donde hoy escriben `sessionStorage`), y `borrarPendiente`
  al llegar a éxito, a fallo definitivo, o al descartar explícitamente.
- `EstadoReservaView` (backend, rama `pendiente_pago`, `views.py:438`) gana un campo
  `detalle_transporte: { tipo_traslado, punto_encuentro_id, direccion_personalizada, zona,
  fecha_regreso, numero_personas, precio_calculado } | null` — `None` si la reserva no tiene
  `DetalleTransporte` asociado. Sin este campo, `TrasladoView` no puede reponer el formulario al
  retomar (hallazgo #13 del review): hoy esa vista solo lee el UUID de la reserva y arranca
  modalidad/punto/zona con sus valores por defecto, como si fuera un checkout nuevo — viola R3
  ("nunca parece un checkout nuevo y vacío") para el único de los tres checkouts que tiene un paso
  adicional de tipo de traslado antes del formulario general.

- [ ] **Paso 1: `checkout-view.tsx` y `traslado-view.tsx`.** En el `then` de `guardarReserva`/
  `crearReservaTraslado` (donde ya se guarda `reservaId`), añade `guardarPendiente({ tipo: 'reserva',
  checkoutId, empresaSlug, productoSlug: servicio?.slug ?? paquete?.slug ?? '', productoNombre:
  servicio?.nombre ?? paquete?.nombre ?? '', ruta: window.location.pathname + window.location.search,
  actualizadoEn: new Date().toISOString() })`. Al llegar a `phase === 'confirmed'`/`'success'` o al
  cancelar explícitamente, llama `borrarPendiente(checkoutId)`.
- [ ] **Paso 2: `use-pago-pedido.ts` (Sección 3).** En `enviar()`, tras `setOrdenId`/tras crear la
  reserva, llama `guardarPendiente` con `tipo: 'orden'` u `'reserva'` según `config.motor`. En las
  fases `exito` y `fallo` (cuando el fallo es definitivo, no un reintento) llama `borrarPendiente`.
  Esto conecta con el hook ya escrito en la Sección 3: añádelo ahí como una edición más de esa tarea
  si aún no se ha commiteado, o como un commit adicional sobre ese archivo si ya se cerró la Sección 3.
- [ ] **Paso 3: backend — `detalle_transporte` en `EstadoReservaView`.** En la rama `pendiente_pago`
  (`views.py:438`), antes del `return Response(...)`, agrega:

  ```python
  detalle_transporte = None
  if hasattr(reserva, 'detalle_transporte'):
      dt = reserva.detalle_transporte
      detalle_transporte = {
          'tipo_traslado': dt.tipo_traslado,
          'punto_encuentro_id': dt.punto_encuentro_id,
          'direccion_personalizada': dt.direccion_personalizada,
          'zona': dt.zona,
          'fecha_regreso': dt.fecha_regreso,
          'numero_personas': dt.numero_personas,
          'precio_calculado': str(dt.precio_calculado) if dt.precio_calculado is not None else None,
      }
  ```
  y añade `'detalle_transporte': detalle_transporte` al diccionario de la `Response`. Reutiliza el
  mismo `related_name` que ya usa `DetalleTransporteInline` en `ReservaAdmin` — verifícalo antes de
  escribir `reserva.detalle_transporte` literal (puede llamarse distinto).
- [ ] **Paso 4: `traslado-view.tsx` — reponer el formulario.** Al montar con un `checkoutId`/UUID
  existente (mismo punto donde hoy solo se lee el UUID, `traslado-view.tsx:116`), llama
  `getEstadoReserva` (ya existe en `api.ts`, usado por `checkout-view.tsx`) y, si
  `estado === 'pendiente_pago'` y trae `detalle_transporte`, inicializa modalidad, punto de
  encuentro/dirección, zona, fecha de regreso, número de personas y moneda desde esos datos en vez de
  los valores por defecto (`traslado-view.tsx:130,155,157`). Prueba manual: crear una reserva de
  traslado, cerrar la pestaña antes de pagar, volver a la misma URL y verificar que el formulario
  aparece lleno, no en el paso 1 vacío.
- [ ] **Paso 5: verificar y commit**

```bash
$PY manage.py test apps.payments
npx tsc --noEmit && npm run lint && npm test && npm run build
git add frontend/src/components backend/apps/payments/views.py
git commit -m "feat(frontend): los checkouts alimentan el puntero de Continuar reservacion y traslado recupera su formulario"
```

### Tarea 5.6: Fase 2 — retomar desde otro dispositivo

**Files:**
- Modify: `backend/apps/notifications/services.py` (nuevo `enviar_correo_retomar_orden`)
- Modify: `backend/apps/payments/ordenes.py` o `views.py` (dispara el correo tras la primera
  autorización de una orden de dos empresas)
- Modify: `backend/apps/bookings/admin.py` (`OrdenAdmin`: columna de contacto tipo
  `CheckoutAbandonadoAdmin.contacto`, con enlace `wa.me` prellenado)
- Test: `backend/apps/notifications/tests.py` (o archivo de tests existente de notificaciones)

**Decisión de alcance (por qué no un WhatsApp automático):** el WhatsApp saliente automatizado fuera
de la ventana de 24h exige una plantilla aprobada por Meta (`WHATSAPP_TEMPLATE`); crear una plantilla
nueva es un paso de producción fuera de este repo (como los ya listados en
`pendientes-manuales-produccion.md`). Además el proyecto ya decidió no automatizar avisos de
WhatsApp — la vendedora los manda a mano (ver memoria "Recordatorios manuales"). Por eso la fase 2
es: (a) **correo automático** con el enlace de retomar (no depende de una plantilla), y (b) un
**enlace de WhatsApp para que el staff lo mande a mano** desde el admin, igual que ya existe para
checkouts abandonados.

**Interfaces:**
- Produces: `enviar_correo_retomar_orden(orden)` — se llama una sola vez (guarda en
  `orden.notificada_en` o un campo equivalente ya existente; revisa `Orden.notificada_en`, que hoy es
  para la notificación de pago: si se reutiliza, verifica que no choquen los dos usos; si chocan,
  añade un `retomar_notificado_en` por columna nueva) cuando `orden.estado == 'autorizando'` y **algún**
  pago quedó en `requires_capture` mientras otro no. El correo incluye
  `{FRONTEND_URL}/{lang}/reservar?paquete={slug}&sede={orden.sede.slug}&retomar={checkout_id}` —
  **incluye `sede`** (hallazgo #5 del review: sin ella, `/[lang]/reservar/page.tsx` resuelve el
  paquete probando todas las sedes — fallback que la Tarea 3.5 de este mismo plan elimina
  explícitamente al mover el checkout unificado a una sola ruta; sin `sede` el enlace cae en un 404
  que el propio plan de frontend ya no admite). Nuevo parámetro `retomar` que la Tarea 3.5 (frontend,
  checkout unificado) debe leer al montar `PedidoPaquete` para sembrar la sesión igual que hace el
  botón de la banda. **Antes de commitear:** confirma contra el estado final de la Tarea 3.5 que la
  ruta sigue esperando `sede` como query param y no como segmento de ruta — probar el enlace generado
  contra el destino real, no solo que el correo se dispare (el review reprodujo el 404 armando la URL
  y ejecutándola contra el código real de la página).

- [ ] **Paso 1: prueba que falla.** Verifica el disparo del correo con un mock de
  `apps.notifications.services.requests.post` (mismo patrón que las pruebas de webhook existentes en
  `apps/payments/tests.py`), comprobando que se dispara una sola vez aunque el webhook se reciba dos
  veces para el mismo pago.
- [ ] **Paso 2: implementar** el envío (reusa `_html`, el patrón de `enviar_correo_confirmacion`) y el
  parámetro `retomar` en el frontend (Tarea 3.5 del plan de frontend, Sección 3): si `searchParams.retomar`
  existe, `PedidoPaquete` siembra `sessionStorage` con ese `checkoutId` antes de montar `usePagoPedido`.
- [ ] **Paso 3: admin.** Columna `contacto` en `OrdenAdmin` para órdenes en `retenido_parcial`, con el
  mismo patrón de `telefono_marcable`/enlace `wa.me` que `CheckoutAbandonadoAdmin.contacto` (backend
  `apps/bookings/admin.py`), mensaje prellenado con el enlace de retomar.
- [ ] **Paso 4: verificar y commit**

```bash
$PY manage.py test apps.notifications apps.payments apps.bookings
git add backend/apps/notifications backend/apps/payments backend/apps/bookings
git commit -m "feat(notifications): correo y enlace de WhatsApp para retomar una orden a medias"
```

**STOP DURO — Cierre de la Sección 5.** Reportar al dueño y **pedir revisión visual** de la banda y
el chip (móvil y escritorio), y de la hoja de confirmación de cancelar. Coordinar el montaje de la
banda con la revisión visual del hub en curso.

---

## Autorrevisión del plan

1. **Cobertura del spec:** D2 (una URL, mismo layout) → 2.1, 3.5, 3.4 (criterio 1), 4.1; D3 extras por servicio → 3.4 (criterios 3, 6); D4 anticipo → 1.3 (`montoInicial`), 3.3, 3.4 (criterio 9), 4.2; D5 USD → 1.3 (`usdDisponible`), 3.4 (criterio 8); D6 noches → 1.2, 3.4 (criterio 4); D7 día → backend (el cliente solo elige inicio); D8 personas → 1.4, 3.1, 3.4 (criterio 5); R1-R5 → 3.3, 3.4 (criterios 9-12); vector de prueba §7 → 1.3; reanudar → 3.2.
2. **Marcadores pendientes:** el shell de 3.4 es un esqueleto declarado y acotado por 13 criterios de aceptación (la construcción visual la hace `design-taste-frontend`, regla dura del dueño); 3.2 lista tres ajustes puntuales que `tsc` valida. No quedan "TBD" en lógica.
3. **Consistencia de tipos:** `SeleccionComponente` (1.3) es un subconjunto de `ComponentePedido` (1.4); `ComponentePedido` alimenta `EstadoPedido` (3.1); `PasoPago` (3.2) alimenta `EncabezadoPago`/`StripePanel` (3.3-3.4). `calcularPedido` indexa por slug de servicio y `armarPayload*` también.
3b. **Continuar reservación (Sección 5, spec §10/§10.1):** puntero → 5.1; contrato de resumen → 5.2; textos → 5.3; componente → 5.4; los checkouts lo alimentan → 5.5; fase 2 → 5.6. "Autorizado"→"retenido" de cara al cliente (decisión del dueño) se aplica también en `EncabezadoPago`/`pedido.authorized` de la Sección 3. **Correcciones del review adversarial de 2026-09-23** (ver `docs/superpowers/plans/REVIEW-continuar-reservacion.md`) integradas en 5.1 (`tieneDineroRetenido` — pendiente de aprobación del dueño, ver nota ahí —, fechas de test relativas, validación de forma contra localStorage corrupto), 5.2 (URLs sin duplicar sede/empresa, contrato de resumen y de cancelar ampliado y unificado), 5.3 (ejemplos ajustados al contrato ampliado), 5.4 (`no_existe` se muestra en vez de ocultarse, acción del clic ramificada por `situacion` con una reducción de alcance marcada para el dueño, el aviso de devolución por confirmar ya no se autooculta a los 3s), 5.5 (traslado recupera su formulario vía `detalle_transporte`, nuevo en `EstadoReservaView`) y 5.6 (el enlace de retomar incluye `sede`).
4. **Riesgos conocidos:** (a) el vector USD de los tests supone los precios del spec; (b) `StripePanel` es compartido: cualquier cambio de default rompe `CheckoutView`/`TrasladoView` (por eso todo va opcional); (c) la frase del aviso depende de la verificación con tarjeta de prueba.
