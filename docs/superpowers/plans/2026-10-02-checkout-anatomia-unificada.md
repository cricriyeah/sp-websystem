# Checkout: anatomía unificada de página y cards — Plan de implementación

> **Para quien ejecute:** SUB-SKILL OBLIGATORIO: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans. Los pasos usan casillas `- [ ]`. Todo lo visual se construye con `design-taste-frontend` y se decide con `perception-first-design` (regla dura del proyecto, ver memoria `feedback-proceso-diseno-frontend`).

**Meta:** que servicio suelto, paquete de una empresa y paquete cruza-empresa compartan el mismo esqueleto de página, el mismo orden de pasos y la misma anatomía de card, y que un cliente que se equivoca varias veces (o choca con el tope de personas) vea un botón flotante de WhatsApp que no mueve el contenido.

**Arquitectura:** se extraen componentes de presentación compartidos (`PaginaCheckout`, `EncabezadoCompra`, `ContenidoViaje`, `CamposContacto`, `BotonPaso`, `BloqueDePaso`, `AyudaFlotante`) y dos módulos puros testeables (`pasos-checkout`, `ayuda-contextual`). `CheckoutView` y `PedidoPaquete` conservan su lógica de datos y de pago; solo cambian su JSX, el orden de pasos del paquete y de dónde sale cada texto. `StripePanel` se parte en dos zonas ("qué compras" / "cómo pagas").

**Tecnología:** Next.js 16.3 (Turbopack), React, Tailwind, `motion/react`, `@phosphor-icons/react`, runner de pruebas propio `tests/run-hub-tests.cjs` (solo módulos puros de `src/lib`).

**Spec:** no hay documento de spec aparte. El diseño sale de la derivación Perception-First (R1–R5, abajo) y de las decisiones del dueño del 2026-10-02, que van en la sección siguiente. Relacionados: `docs/superpowers/specs/2026-09-21-checkout-unificado-design.md`, `frontend/CLAUDE.md` (sección "Checkout unificado de paquetes").

## Diseño aprobado

**Decisiones del dueño (2026-10-02):**
1. Contacto va **después del viaje** también en el paquete: viaje → contacto → detalles → pago.
2. Moneda MXN/USD va en la zona **"Cómo pagas"** del panel derecho (plegada como corrección); se quita el toggle de arriba del paquete.
3. El resumen "Tu pedido" es **vivo desde el paso 1**; en móvil queda visible bajo los pasos y la zona de pago aparece al llegar al paso 4. Total compacto en el stepper en los tres tipos.
4. Alcance: **componentes compartidos**, cada tipo conserva su lógica de datos y de pago.
5. La pregunta junto al botón ("¿Todo bien?") se **quita** (default propuesto; repite el título).
6. **Ayuda flotante:** si el cliente tropieza varias veces (errores de validación al confirmar pasos, deslinde sin marcar, o intentos de pasar el tope de personas) aparece un botón de WhatsApp en posición `fixed`, sin empujar ni mover nada. Se puede cerrar y no vuelve a salir en esa visita.

**Requisitos derivados:**
- **R1** ≤4 bloques por card, una pregunta por bloque; una sola card activa en foco; el panel derecho en dos zonas.
- **R2** Mismo esqueleto de página y misma anatomía de card en los tres tipos (encabezado, cuerpo, pie con un CTA).
- **R3** Orden fijo viaje → contacto → detalles → pago; dentro de la card, obligatorio antes que opcional (cuándo → cuántos → dónde → extras).
- **R4** Un CTA primario por card, solo en la activa; lo del hero llega prellenado; controles secundarios plegados.
- **R5** Bloque "qué compras" fijo arriba, resumen vivo con lo elegido, empresa como etiqueta única y solo si hay más de una.

## Restricciones globales

- Todo texto nuevo va en `es.json` **y** `en.json` (`src/app/[lang]/dictionaries/`). Tras editar diccionarios hay que reiniciar `npm run dev` (Turbopack los cachea).
- No añadir selectores nativos de fecha; para fechas ISO usar `fromLocalISODate`/`toLocalISODate` de `src/lib/dates.ts`.
- Solo clases de Tailwind que ya existen en el proyecto (`bg-action`, `text-action-foreground`, `bg-surface`, `bg-background`, `border-border`, `text-muted`, `text-foreground`, `text-accent`, `bg-exito-fondo`, `text-exito`). No inventar tokens.
- El proyecto no está lanzado: no se conserva compatibilidad con la estructura vieja; se borra lo que deja de usarse.
- La verificación es sin navegador: `npx.cmd tsc --noEmit`, `npx.cmd eslint src tests`, `npm.cmd test`, `npm.cmd run build` (desde `frontend/`). El dueño revisa el sitio.
- Comentarios en español, densidad similar al código vecino (explican el porqué).
- Las pruebas de `npm.cmd test` solo cubren módulos puros de `src/lib`; los componentes se verifican con tsc/eslint/build.
- `traslado-view.tsx` (ruta `/traslados`) queda **fuera de alcance**.
- Mensajes de commit en español, tipo convencional, terminando con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Precondición: trabajo en curso sin commit

El worktree trae cambios de una sesión anterior (calendario por semana de paquetes): `frontend/src/components/pedido/fecha-paquete.tsx` (nuevo), `frontend/src/lib/calendario-semana.ts` y `frontend/tests/calendario-semana.test.cjs` (nuevos), y modificados `date-field.tsx`, `grupo-servicio.tsx`, `run-hub-tests.cjs`, `es.json`, `en.json`. Este plan edita `grupo-servicio.tsx`, `run-hub-tests.cjs` y los diccionarios, así que esa base debe quedar commiteada antes (Tarea 0). `frontend/next-env.d.ts` y `.great_cto/*` son ruido del entorno: no se commitean.

## Mapa de archivos

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `frontend/src/lib/pasos-checkout.ts` | crear | Secuencia fija de pasos y estado de cada tarjeta (puro). |
| `frontend/tests/pasos-checkout.test.cjs` | crear | Pruebas de lo anterior. |
| `frontend/src/lib/ayuda-contextual.ts` | crear | Cuándo ofrecer WhatsApp tras tropiezos repetidos (puro). |
| `frontend/tests/ayuda-contextual.test.cjs` | crear | Pruebas de lo anterior. |
| `frontend/src/lib/personalizaciones.ts` | modificar | `separarPersonalizaciones` (obligatorias antes de opcionales). |
| `frontend/tests/personalizaciones.test.cjs` | modificar | Prueba del separador. |
| `frontend/tests/run-hub-tests.cjs` | modificar | Registrar las dos suites nuevas. |
| `frontend/src/app/[lang]/dictionaries/{es,en}.json` | modificar | Textos nuevos (`checkout.*`, `feedback.floatingHelp`). |
| `frontend/src/components/checkout-section-card.tsx` | modificar | Anatomía de card: `etiqueta`, `pie`, cuerpo en bloques; exporta `BloqueDePaso`. |
| `frontend/src/components/checkout/boton-paso.tsx` | crear | Único CTA primario de card. |
| `frontend/src/components/checkout/campos-contacto.tsx` | crear | Teléfono, nombre y correo (hoy copiados en dos archivos). |
| `frontend/src/components/checkout/contenido-viaje.tsx` | crear | Orden fijo del paso "viaje": fecha → hora/personas → salida → nota. |
| `frontend/src/components/checkout/encabezado-compra.tsx` | crear | Bloque fijo "qué compras" bajo el enlace de volver. |
| `frontend/src/components/checkout/pagina-checkout.tsx` | crear | Esqueleto de página compartido (header, volver, encabezado, stepper, 2 columnas, footer). |
| `frontend/src/components/checkout/ayuda-flotante.tsx` | crear | Botón fijo de WhatsApp, descartable. |
| `frontend/src/components/checkout/use-ayuda-contextual.ts` | crear | Hook que une el módulo puro con el estado de React. |
| `frontend/src/components/stripe-panel.tsx` | modificar | Zona "qué compras" (líneas del viaje + total) y zona "cómo pagas"; moneda movida; visibilidad móvil. |
| `frontend/src/components/pedido/grupo-servicio.tsx` | modificar | Card de grupo con la anatomía nueva; sin fecha de inicio; traslado antes de extras. |
| `frontend/src/components/pedido/pedido-paquete.tsx` | modificar | Pasos viaje → contacto → detalles → pago sobre `PaginaCheckout`. |
| `frontend/src/components/checkout-view.tsx` | modificar | Mismos componentes compartidos para servicio suelto. |
| `frontend/src/components/checkout-loading-shell.tsx`, `frontend/src/app/[lang]/reservar/loading.tsx` | modificar | Skeleton alineado con el nuevo esqueleto. |
| `frontend/CLAUDE.md` | modificar | Documentar la anatomía unificada. |

Revisión de arquitectura (hecha a mano, sin subagente): `pasos-checkout` y `ayuda-contextual` no importan React ni componentes (hoja del grafo). Los componentes de `checkout/` solo importan de `lib/` y de componentes ya existentes; ninguno importa `checkout-view` ni `pedido-paquete`, así que no hay ciclos. `CheckoutSectionCard` sigue siendo la única card; `StripePanel` sigue siendo el único dueño de Stripe/Turnstile y se monta una sola vez. Si prefieres que un subagente haga la crítica adversarial del mapa antes de empezar, pídelo.

---

### Tarea 0: Línea base

**Archivos:** ninguno nuevo.

- [ ] **Paso 1:** Confirmar con el dueño que el trabajo en curso de calendario por semana se commitea tal cual (es suyo, de la sesión anterior).
- [ ] **Paso 2:** Desde `frontend/`, correr el gate para saber que la base está sana:

```bash
npx.cmd tsc --noEmit
npx.cmd eslint src tests
npm.cmd test
```
Esperado: los tres terminan sin errores. Si algo falla, parar y avisar: no es parte de este plan.

- [ ] **Paso 3:** Commit de la base (solo esos archivos, nunca `git add -A`):

```bash
git add frontend/src/components/pedido/fecha-paquete.tsx frontend/src/lib/calendario-semana.ts frontend/tests/calendario-semana.test.cjs frontend/src/components/date-field.tsx frontend/src/components/pedido/grupo-servicio.tsx frontend/tests/run-hub-tests.cjs "frontend/src/app/[lang]/dictionaries/es.json" "frontend/src/app/[lang]/dictionaries/en.json"
git commit -m "feat(checkout): calendario por semana para elegir inicio del paquete

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 1: Secuencia de pasos y estado de tarjeta (módulo puro)

**Archivos:**
- Crear: `frontend/src/lib/pasos-checkout.ts`
- Crear: `frontend/tests/pasos-checkout.test.cjs`
- Modificar: `frontend/tests/run-hub-tests.cjs` (objeto `suites`)

**Interfaces:**
- Produce: `type PasoId = 'viaje' | 'contacto' | 'detalles' | 'pago'`; `ORDEN_PASOS: readonly PasoId[]`; `type EstadoTarjeta = 'activo' | 'editando' | 'completado'`; `estadoDeTarjeta(id: PasoId, actual: PasoId, editando: PasoId | null): EstadoTarjeta | 'oculto'`; `numeroDePaso(id: PasoId): number` (1-4).

- [ ] **Paso 1: escribir la prueba que falla** — `frontend/tests/pasos-checkout.test.cjs`:

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PASOS_CHECKOUT_TEST_OUT, 'lib/pasos-checkout.js'));

test('el orden de los pasos es viaje, contacto, detalles, pago', () => {
  assert.deepEqual([...p.ORDEN_PASOS], ['viaje', 'contacto', 'detalles', 'pago']);
});

test('numera los pasos de 1 a 4', () => {
  assert.equal(p.numeroDePaso('viaje'), 1);
  assert.equal(p.numeroDePaso('contacto'), 2);
  assert.equal(p.numeroDePaso('detalles'), 3);
  assert.equal(p.numeroDePaso('pago'), 4);
});

test('el paso actual está activo, los anteriores completados y los siguientes ocultos', () => {
  assert.equal(p.estadoDeTarjeta('viaje', 'contacto', null), 'completado');
  assert.equal(p.estadoDeTarjeta('contacto', 'contacto', null), 'activo');
  assert.equal(p.estadoDeTarjeta('detalles', 'contacto', null), 'oculto');
  assert.equal(p.estadoDeTarjeta('pago', 'contacto', null), 'oculto');
});

test('un paso ya confirmado reabierto a mano queda en edición', () => {
  assert.equal(p.estadoDeTarjeta('viaje', 'detalles', 'viaje'), 'editando');
  assert.equal(p.estadoDeTarjeta('contacto', 'detalles', 'viaje'), 'completado');
});

test('editar el paso activo no cambia su estado', () => {
  assert.equal(p.estadoDeTarjeta('contacto', 'contacto', 'contacto'), 'activo');
});

test('en el pago todas las tarjetas de pasos están completadas', () => {
  for (const id of ['viaje', 'contacto', 'detalles']) {
    assert.equal(p.estadoDeTarjeta(id, 'pago', null), 'completado');
  }
});
```

- [ ] **Paso 2: registrar la suite** en `frontend/tests/run-hub-tests.cjs`, dentro de `suites` (después de la línea de `'fallo-pago'`):

```js
  'pasos-checkout': ['src/lib/pasos-checkout.ts', 'PASOS_CHECKOUT_TEST_OUT'],
```

(`ayuda-contextual` se registra en la Tarea 2, junto con su módulo: registrarla antes rompe `npm.cmd test` completo.)

- [ ] **Paso 3: verificar que falla.** Desde `frontend/`:

```bash
npm.cmd test -- pasos-checkout
```
Esperado: FALLA con error de TypeScript por archivo inexistente (`src/lib/pasos-checkout.ts`).

- [ ] **Paso 4: implementar** — `frontend/src/lib/pasos-checkout.ts`:

```ts
// Secuencia fija de pasos del checkout, igual para servicio suelto, paquete de
// una empresa y paquete cruza-empresa. Sin React: solo decide qué tarjeta se
// ve y en qué estado, para que los tres checkouts no lo reinventen cada uno.

export type PasoId = 'viaje' | 'contacto' | 'detalles' | 'pago';

export const ORDEN_PASOS: readonly PasoId[] = ['viaje', 'contacto', 'detalles', 'pago'];

export type EstadoTarjeta = 'activo' | 'editando' | 'completado';

/** 1-4, el número que usa el stepper. */
export function numeroDePaso(id: PasoId): number {
  return ORDEN_PASOS.indexOf(id) + 1;
}

/**
 * Estado de la tarjeta de `id` cuando el cliente va en `actual`.
 *
 * - Los pasos posteriores al actual no existen todavía (`'oculto'`).
 * - El actual es el que se está contestando (`'activo'`).
 * - Los anteriores quedan `'completado'` (colapsados a un renglón), salvo el
 *   que el cliente reabrió con "Cambiar" (`editando`), que se ve abierto.
 */
export function estadoDeTarjeta(
  id: PasoId,
  actual: PasoId,
  editando: PasoId | null,
): EstadoTarjeta | 'oculto' {
  const indice = ORDEN_PASOS.indexOf(id);
  const indiceActual = ORDEN_PASOS.indexOf(actual);
  if (indice > indiceActual) return 'oculto';
  if (indice === indiceActual) return 'activo';
  return editando === id ? 'editando' : 'completado';
}
```

- [ ] **Paso 5: verificar que pasa.**

```bash
npm.cmd test -- pasos-checkout
```
Esperado: 6 pruebas pasan.

- [ ] **Paso 6: commit.**

```bash
git add frontend/src/lib/pasos-checkout.ts frontend/tests/pasos-checkout.test.cjs frontend/tests/run-hub-tests.cjs
git commit -m "feat(checkout): secuencia unica de pasos y estado de tarjeta

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 2: Reglas de ayuda contextual (módulo puro)

**Archivos:**
- Crear: `frontend/src/lib/ayuda-contextual.ts`
- Crear: `frontend/tests/ayuda-contextual.test.cjs`
- Modificar: `frontend/tests/run-hub-tests.cjs` (registrar la suite aquí, no en la Tarea 1)

**Interfaces:**
- Produce: `type TipoTropiezo = 'validacion' | 'tope-personas'`; `type EstadoAyuda = { validacion: number; topePersonas: number; descartada: boolean }`; `ayudaInicial: EstadoAyuda`; `TROPIEZOS_PARA_OFRECER_AYUDA = 3`; `registrarTropiezo(estado, tipo): EstadoAyuda`; `descartarAyuda(estado): EstadoAyuda`; `ofreceAyudaFlotante(estado): boolean`; `motivoDeAyuda(estado): TipoTropiezo`.

- [ ] **Paso 1: escribir la prueba que falla** — `frontend/tests/ayuda-contextual.test.cjs`:

```js
/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const a = require(path.join(process.env.AYUDA_CONTEXTUAL_TEST_OUT, 'lib/ayuda-contextual.js'));

const tropezar = (estado, tipo, veces) => {
  let actual = estado;
  for (let i = 0; i < veces; i += 1) actual = a.registrarTropiezo(actual, tipo);
  return actual;
};

test('al inicio no se ofrece ayuda', () => {
  assert.equal(a.ofreceAyudaFlotante(a.ayudaInicial), false);
});

test('se ofrece desde el tercer tropiezo de validación', () => {
  assert.equal(a.ofreceAyudaFlotante(tropezar(a.ayudaInicial, 'validacion', 2)), false);
  assert.equal(a.ofreceAyudaFlotante(tropezar(a.ayudaInicial, 'validacion', 3)), true);
});

test('se ofrece desde el tercer intento de pasar el tope de personas', () => {
  assert.equal(a.ofreceAyudaFlotante(tropezar(a.ayudaInicial, 'tope-personas', 2)), false);
  assert.equal(a.ofreceAyudaFlotante(tropezar(a.ayudaInicial, 'tope-personas', 3)), true);
});

test('los tropiezos de distinto tipo se suman', () => {
  const mezclado = tropezar(tropezar(a.ayudaInicial, 'validacion', 2), 'tope-personas', 1);
  assert.equal(a.ofreceAyudaFlotante(mezclado), true);
});

test('descartar apaga la ayuda y no vuelve a salir', () => {
  const descartada = a.descartarAyuda(tropezar(a.ayudaInicial, 'validacion', 3));
  assert.equal(a.ofreceAyudaFlotante(descartada), false);
  assert.equal(a.ofreceAyudaFlotante(a.registrarTropiezo(descartada, 'validacion')), false);
});

test('el motivo es el tipo de tropiezo que más veces ocurrió', () => {
  assert.equal(a.motivoDeAyuda(tropezar(a.ayudaInicial, 'tope-personas', 3)), 'tope-personas');
  assert.equal(a.motivoDeAyuda(tropezar(a.ayudaInicial, 'validacion', 3)), 'validacion');
  const mas_tope = tropezar(tropezar(a.ayudaInicial, 'validacion', 1), 'tope-personas', 2);
  assert.equal(a.motivoDeAyuda(mas_tope), 'tope-personas');
});

test('registrar un tropiezo no muta el estado anterior', () => {
  const antes = a.ayudaInicial;
  a.registrarTropiezo(antes, 'validacion');
  assert.equal(antes.validacion, 0);
});
```

- [ ] **Paso 1b: registrar la suite** en `frontend/tests/run-hub-tests.cjs`, dentro de `suites`, justo después de la línea de `'pasos-checkout'`:

```js
  'ayuda-contextual': ['src/lib/ayuda-contextual.ts', 'AYUDA_CONTEXTUAL_TEST_OUT'],
```

- [ ] **Paso 2: verificar que falla.**

```bash
npm.cmd test -- ayuda-contextual
```
Esperado: FALLA (archivo `src/lib/ayuda-contextual.ts` no existe).

- [ ] **Paso 3: implementar** — `frontend/src/lib/ayuda-contextual.ts`:

```ts
// Cuándo ofrecer ayuda humana (WhatsApp) mientras el cliente llena el checkout.
// Sin React ni red. La salida de emergencia de un pago rechazado ya existe
// (`fallo-pago.ts`, `ErrorBlock`); esto cubre el llenado: errores repetidos al
// confirmar un paso y choques con el tope de personas.

export type TipoTropiezo = 'validacion' | 'tope-personas';

export type EstadoAyuda = {
  validacion: number;
  topePersonas: number;
  descartada: boolean;
};

export const TROPIEZOS_PARA_OFRECER_AYUDA = 3;

export const ayudaInicial: EstadoAyuda = { validacion: 0, topePersonas: 0, descartada: false };

export function registrarTropiezo(estado: EstadoAyuda, tipo: TipoTropiezo): EstadoAyuda {
  return tipo === 'validacion'
    ? { ...estado, validacion: estado.validacion + 1 }
    : { ...estado, topePersonas: estado.topePersonas + 1 };
}

/** El cliente cerró el aviso: no se le vuelve a ofrecer en esta visita. */
export function descartarAyuda(estado: EstadoAyuda): EstadoAyuda {
  return { ...estado, descartada: true };
}

export function ofreceAyudaFlotante(estado: EstadoAyuda): boolean {
  return !estado.descartada
    && estado.validacion + estado.topePersonas >= TROPIEZOS_PARA_OFRECER_AYUDA;
}

/** Qué mensaje prellenar: el del tipo de tropiezo más frecuente (empate → validación). */
export function motivoDeAyuda(estado: EstadoAyuda): TipoTropiezo {
  return estado.topePersonas > estado.validacion ? 'tope-personas' : 'validacion';
}
```

- [ ] **Paso 4: verificar que pasa.**

```bash
npm.cmd test -- ayuda-contextual
```
Esperado: 7 pruebas pasan.

- [ ] **Paso 5: commit.**

```bash
git add frontend/src/lib/ayuda-contextual.ts frontend/tests/ayuda-contextual.test.cjs frontend/tests/run-hub-tests.cjs
git commit -m "feat(checkout): reglas puras de ayuda contextual por tropiezos repetidos

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 3: Separar personalizaciones obligatorias de opcionales

**Archivos:**
- Modificar: `frontend/src/lib/personalizaciones.ts`
- Modificar: `frontend/tests/personalizaciones.test.cjs`

**Interfaces:**
- Produce: `separarPersonalizaciones<T extends { obligatorio: boolean }>(items: T[]): { obligatorias: T[]; opcionales: T[] }` (conserva el orden relativo de cada grupo).

- [ ] **Paso 1: prueba que falla** — añadir al final de `frontend/tests/personalizaciones.test.cjs`:

```js
test('separa obligatorias de opcionales conservando el orden', () => {
  const a = { id: 1, obligatorio: false };
  const b = { id: 2, obligatorio: true };
  const c = { id: 3, obligatorio: false };
  const d = { id: 4, obligatorio: true };
  const { obligatorias, opcionales } = h.separarPersonalizaciones([a, b, c, d]);
  assert.deepEqual(obligatorias.map((x) => x.id), [2, 4]);
  assert.deepEqual(opcionales.map((x) => x.id), [1, 3]);
});

test('sin personalizaciones devuelve dos listas vacías', () => {
  assert.deepEqual(h.separarPersonalizaciones([]), { obligatorias: [], opcionales: [] });
});
```

- [ ] **Paso 2: verificar que falla.**

```bash
npm.cmd test -- personalizaciones
```
Esperado: FALLA (`h.separarPersonalizaciones is not a function`).

- [ ] **Paso 3: implementar** — en `frontend/src/lib/personalizaciones.ts`, después de `seleccionInicial`:

```ts
/**
 * Lo que el cliente debe contestar (obligatorio) va antes que lo que puede
 * saltarse. Mismo criterio de orden en el checkout de servicio y en cada grupo
 * de un paquete: primero lo que bloquea avanzar, luego los extras.
 */
export function separarPersonalizaciones<T extends { obligatorio: boolean }>(items: T[]) {
  return {
    obligatorias: items.filter((item) => item.obligatorio),
    opcionales: items.filter((item) => !item.obligatorio),
  };
}
```

- [ ] **Paso 4: verificar que pasa.**

```bash
npm.cmd test -- personalizaciones
```
Esperado: todas pasan.

- [ ] **Paso 5: commit.**

```bash
git add frontend/src/lib/personalizaciones.ts frontend/tests/personalizaciones.test.cjs
git commit -m "feat(checkout): separa personalizaciones obligatorias de opcionales

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 4: Textos nuevos (es/en)

**Archivos:**
- Modificar: `frontend/src/app/[lang]/dictionaries/es.json`
- Modificar: `frontend/src/app/[lang]/dictionaries/en.json`

**Interfaces:**
- Produce (se usan en tareas posteriores): `checkout.purchaseKicker`, `checkout.purchaseNights`, `checkout.howYouPay`, `checkout.optionalTag`, `checkout.summary.{date,time,people,checkOut}`, `feedback.floatingHelp.{label,dismiss,messageValidation,messageMaxPeople}`.

- [ ] **Paso 1:** en el objeto `checkout` de `es.json`, añadir (junto a `orderSummaryHeadline`):

```json
    "purchaseKicker": "Tu compra",
    "purchaseNights": "{n} noches",
    "howYouPay": "Cómo pagas",
    "optionalTag": "Opcional",
    "summary": {
      "date": "Fecha",
      "time": "Hora",
      "people": "Personas",
      "checkOut": "Salida"
    },
```

- [ ] **Paso 2:** en el objeto `feedback` de `es.json`, añadir:

```json
    "floatingHelp": {
      "label": "¿Necesitas ayuda?",
      "dismiss": "Cerrar",
      "messageValidation": "Hola, estoy intentando reservar en la página para el {date} para {people} personas y no logro completar los datos. ¿Me pueden ayudar?",
      "messageMaxPeople": "Hola, quiero reservar {name} para más de {max} personas. ¿Me pueden ayudar?"
    },
```

- [ ] **Paso 3:** los mismos bloques en `en.json`:

```json
    "purchaseKicker": "Your booking",
    "purchaseNights": "{n} nights",
    "howYouPay": "How you pay",
    "optionalTag": "Optional",
    "summary": {
      "date": "Date",
      "time": "Time",
      "people": "Guests",
      "checkOut": "Check-out"
    },
```

```json
    "floatingHelp": {
      "label": "Need help?",
      "dismiss": "Close",
      "messageValidation": "Hi, I'm trying to book on the website for {date} for {people} people and I can't complete my details. Can you help me?",
      "messageMaxPeople": "Hi, I'd like to book {name} for more than {max} people. Can you help me?"
    },
```

- [ ] **Paso 4: verificar tipos** (el tipo `Dictionary` sale de los JSON; las dos lenguas deben coincidir en forma):

```bash
npx.cmd tsc --noEmit
```
Esperado: sin errores.

- [ ] **Paso 5: commit.**

```bash
git add "frontend/src/app/[lang]/dictionaries/es.json" "frontend/src/app/[lang]/dictionaries/en.json"
git commit -m "feat(checkout): textos para encabezado de compra, resumen vivo y ayuda flotante

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 5: Anatomía de card (`CheckoutSectionCard`, `BloqueDePaso`, `BotonPaso`)

**Archivos:**
- Modificar: `frontend/src/components/checkout-section-card.tsx`
- Crear: `frontend/src/components/checkout/boton-paso.tsx`

**Interfaces:**
- Produce: `CheckoutSectionCard` acepta además `etiqueta?: string` (chip junto al título) y `pie?: ReactNode` (fila final con el único CTA). Exporta `BloqueDePaso({ titulo?, opcional?, children })`. `BotonPaso({ children, onClick, conFlecha?, disabled? })`.
- Reglas de anatomía: cuerpo `flat` = columna con `gap-5` (cada hijo es un bloque; sin `border-t` ni `mt-*` propios); cuerpo `elevated` queda como estaba (lo usa `StripePanel`); el `pie` solo se pasa cuando la tarjeta está `activo`.

- [ ] **Paso 1:** en `checkout-section-card.tsx`, ampliar las props (después de `onAction`):

```tsx
  /** Empresa del grupo (solo cuando el pedido tiene más de una): una sola vez, junto al título. */
  etiqueta?: string;
  /** Fila final de la tarjeta abierta con el único CTA primario. Solo en `activo`. */
  pie?: ReactNode;
```

Desestructurarlas en la firma (`etiqueta`, `pie`).

- [ ] **Paso 2:** en el encabezado, justo después del `<span ...>{title}</span>`, añadir el chip:

```tsx
          <span className="flex min-w-0 flex-wrap items-center gap-x-2">
            <span className="font-sans text-sm font-medium tracking-tight text-foreground">
              {title}
            </span>
            {etiqueta && (
              <span className="rounded-full bg-surface px-2 py-0.5 text-[11px] font-medium text-muted">
                {etiqueta}
              </span>
            )}
          </span>
```
(reemplaza el `<span ... >{title}</span>` actual; el resumen colapsado queda debajo como hoy).

- [ ] **Paso 3:** reemplazar el cuerpo animado (`<div className="mt-5">{children}</div>`) por:

```tsx
            <div className={`mt-5 ${variant === 'flat' ? 'flex flex-col gap-5' : ''}`}>{children}</div>
            {pie && (
              <div className="mt-6 flex justify-end border-t border-border pt-5">{pie}</div>
            )}
```

- [ ] **Paso 4:** exportar `BloqueDePaso` al final del mismo archivo:

```tsx
/**
 * Un bloque de la tarjeta: una pregunta, con su título corto opcional. El
 * espacio entre bloques lo pone el cuerpo de la tarjeta (`gap-5`), no rayas.
 * `opcional` es el texto de la etiqueta ("Opcional") — se pasa traducido.
 */
export function BloqueDePaso({
  titulo,
  opcional,
  children,
}: {
  titulo?: string;
  opcional?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      {titulo && (
        <p className="text-sm font-medium text-foreground">
          {titulo}
          {opcional && <span className="ml-2 text-xs font-normal text-muted">{opcional}</span>}
        </p>
      )}
      {children}
    </div>
  );
}
```

- [ ] **Paso 5:** crear `frontend/src/components/checkout/boton-paso.tsx`:

```tsx
import type { ReactNode } from 'react';
import { ArrowRight } from '@phosphor-icons/react';

/**
 * El único CTA primario de una tarjeta de paso. Antes había tres formas
 * distintas (redondo con pregunta, redondo suelto, cuadrado con flecha): la
 * misma función se veía diferente en cada paso.
 */
export function BotonPaso({
  children,
  onClick,
  conFlecha = false,
  disabled = false,
}: {
  children: ReactNode;
  onClick: () => void;
  conFlecha?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center gap-2 rounded-full bg-action px-6 py-2.5 text-sm font-medium text-action-foreground transition-transform active:scale-[0.98] disabled:opacity-60"
    >
      {children}
      {conFlecha && <ArrowRight size={16} weight="bold" />}
    </button>
  );
}
```

- [ ] **Paso 6: verificar.**

```bash
npx.cmd tsc --noEmit
npx.cmd eslint src/components/checkout-section-card.tsx src/components/checkout/boton-paso.tsx
```
Esperado: sin errores (los usos existentes de `CheckoutSectionCard` no pasan las props nuevas, que son opcionales).

- [ ] **Paso 7: commit.**

```bash
git add frontend/src/components/checkout-section-card.tsx frontend/src/components/checkout/boton-paso.tsx
git commit -m "feat(checkout): anatomia de card con etiqueta, pie y bloques

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 6: `CamposContacto` y `ContenidoViaje`

**Archivos:**
- Crear: `frontend/src/components/checkout/campos-contacto.tsx`
- Crear: `frontend/src/components/checkout/contenido-viaje.tsx`

**Interfaces:**
- Produce: `CampoContacto = 'fullName' | 'phone' | 'email'`; `CamposContacto({ valores, errores, etiquetas, onCambio, refs?, disabled?, idPrefijo })`; `ContenidoViaje({ fecha, hora?, personas?, salida?, nota? })`.

- [ ] **Paso 1:** crear `campos-contacto.tsx`. Es el JSX de `checkout-view.tsx` (líneas ~1240-1337) parametrizado; orden visual teléfono → nombre → correo (mismo que `ORDEN_CAMPOS`):

```tsx
'use client';

import type { Ref } from 'react';
import { EnvelopeSimple, Phone, User } from '@phosphor-icons/react';
import { CLASES_CAMPO_CON_ERROR, FieldError, propsDeError } from '@/components/field-error';

export type CampoContacto = 'fullName' | 'phone' | 'email';

type Props = {
  valores: Record<CampoContacto, string>;
  errores: Partial<Record<CampoContacto, string>>;
  etiquetas: Record<CampoContacto, string>;
  onCambio: (campo: CampoContacto, valor: string) => void;
  refs?: Partial<Record<CampoContacto, Ref<HTMLInputElement>>>;
  disabled?: boolean;
  /** Prefijo de los ids de error (`aria-describedby`), único por pantalla. */
  idPrefijo: string;
};

const CAMPOS: { campo: CampoContacto; tipo: string; icono: typeof Phone; ancho: string }[] = [
  { campo: 'phone', tipo: 'tel', icono: Phone, ancho: 'sm:col-span-1' },
  { campo: 'fullName', tipo: 'text', icono: User, ancho: 'sm:col-span-1' },
  { campo: 'email', tipo: 'email', icono: EnvelopeSimple, ancho: 'sm:col-span-2' },
];

/** Los tres datos de contacto, iguales en servicio suelto y en paquete. */
export function CamposContacto({ valores, errores, etiquetas, onCambio, refs, disabled, idPrefijo }: Props) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {CAMPOS.map(({ campo, tipo, icono: Icono, ancho }) => {
        const idError = `${idPrefijo}-error-${campo}`;
        const error = errores[campo];
        return (
          <label key={campo} className={`flex flex-col gap-1.5 text-sm ${ancho}`}>
            <span className="text-muted">{etiquetas[campo]}</span>
            <span className="relative">
              <Icono
                size={18}
                className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-muted"
              />
              <input
                ref={refs?.[campo]}
                type={tipo}
                required
                disabled={disabled}
                value={valores[campo]}
                onChange={(e) => onCambio(campo, e.target.value)}
                {...propsDeError(idError, Boolean(error))}
                className={`w-full border bg-surface py-3 pr-4 pl-11 text-foreground outline-none disabled:opacity-60 ${
                  error ? CLASES_CAMPO_CON_ERROR : 'border-border focus:border-accent'
                }`}
              />
            </span>
            {error && <FieldError id={idError} mensaje={error} />}
          </label>
        );
      })}
    </div>
  );
}
```

- [ ] **Paso 2:** crear `contenido-viaje.tsx` (orden fijo del paso "viaje"; `hora` y `personas` van en cajas con borde porque `TimeField`/`PeopleStepper` traen su propio `px-6 py-3.5` y sin caja flotan desalineados):

```tsx
import type { ReactNode } from 'react';

type Props = {
  /** Calendario o selector de fecha de inicio. */
  fecha: ReactNode;
  /** Selector de hora (solo si el servicio o paquete pide hora). */
  hora?: ReactNode;
  /** Selector de personas del viaje (en paquetes sin precio por persona viven en cada grupo). */
  personas?: ReactNode;
  /** Fecha de salida (hospedaje). */
  salida?: ReactNode;
  /** Notas de apoyo en texto pequeño: precio por persona, noches, personas extra. */
  nota?: ReactNode;
};

const CAJA = 'border border-border bg-surface';

/**
 * Orden fijo del paso "viaje" para todos los checkouts: cuándo (fecha) →
 * a qué hora y cuántos → hasta cuándo → aclaraciones. Cada hijo es un bloque
 * del cuerpo de la tarjeta; el espacio lo pone la tarjeta.
 */
export function ContenidoViaje({ fecha, hora, personas, salida, nota }: Props) {
  const campos = [hora, personas].filter(Boolean).length;
  return (
    <>
      <div>{fecha}</div>
      {campos > 0 && (
        <div className={`grid gap-3 ${campos === 2 ? 'sm:grid-cols-2' : ''}`}>
          {hora && <div className={CAJA}>{hora}</div>}
          {personas && <div className={CAJA}>{personas}</div>}
        </div>
      )}
      {salida && <div>{salida}</div>}
      {nota && <div className="flex flex-col gap-1 text-xs text-muted">{nota}</div>}
    </>
  );
}
```

- [ ] **Paso 3: verificar.**

```bash
npx.cmd tsc --noEmit
npx.cmd eslint src/components/checkout
```
Esperado: sin errores.

- [ ] **Paso 4: commit.**

```bash
git add frontend/src/components/checkout/campos-contacto.tsx frontend/src/components/checkout/contenido-viaje.tsx
git commit -m "feat(checkout): componentes compartidos de contacto y contenido del viaje

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 7: `EncabezadoCompra` y `PaginaCheckout`

**Archivos:**
- Crear: `frontend/src/components/checkout/encabezado-compra.tsx`
- Crear: `frontend/src/components/checkout/pagina-checkout.tsx`

**Interfaces:**
- Produce: `EncabezadoCompra({ kicker, nombre, detalle? })`; `PaginaCheckout({ lang, dict, sedeSlug?, volverHref, volverLabel, encabezado, aviso?, stepper: { actual, steps?, totalMovil? }, pasos, pedido })`.
- Consume: `SiteHeader({ lang, nav, variante: 'sede', sedeSlugActual? })`, `CheckoutFooter({ lang, footer, nav })`, `CheckoutStepper({ stepper, actual, steps?, totalMovil? })` (todos ya existen).

- [ ] **Paso 1:** `encabezado-compra.tsx`:

```tsx
/**
 * "Qué compras", siempre arriba y siempre igual: contesta la primera pregunta
 * del cliente antes de pedirle nada. Antes el servicio lo mostraba como un
 * banner dentro de la columna de pasos y el paquete como un `h1` suelto.
 */
export function EncabezadoCompra({
  kicker,
  nombre,
  detalle,
}: {
  kicker: string;
  nombre: string;
  /** Sede · empresa(s) · noches, solo lo que se sepa. */
  detalle?: string;
}) {
  return (
    <header className="mt-6">
      <p className="text-xs font-semibold tracking-wider text-accent uppercase">{kicker}</p>
      <h1 className="mt-1 text-2xl font-bold text-foreground sm:text-3xl">{nombre}</h1>
      {detalle && <p className="mt-1 text-sm text-muted">{detalle}</p>}
    </header>
  );
}
```

- [ ] **Paso 2:** `pagina-checkout.tsx` (el esqueleto que hoy repiten `CheckoutView` y `PedidoPaquete`; el contenedor interno y el `<main>` conservan las clases actuales):

```tsx
import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft } from '@phosphor-icons/react';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { CheckoutFooter } from '@/components/checkout-footer';
import { CheckoutStepper } from '@/components/checkout-stepper';
import { SiteHeader } from '@/components/site-header';

type Props = {
  lang: Locale;
  dict: Dictionary;
  sedeSlug?: string;
  volverHref: string;
  volverLabel: string;
  /** `EncabezadoCompra`. */
  encabezado: ReactNode;
  /** Aviso a todo el ancho entre el encabezado y el stepper (p. ej. día sin lugar). */
  aviso?: ReactNode;
  stepper: { actual: number; steps?: string[]; totalMovil?: string };
  /** Columna izquierda: las tarjetas de paso. */
  pasos: ReactNode;
  /** Columna derecha: `StripePanel`. */
  pedido: ReactNode;
};

/**
 * Esqueleto único del checkout: volver → qué compras → stepper → [pasos |
 * pedido] → footer. Sin `sticky` en la columna del pedido (decisión previa:
 * no persigue el scroll).
 */
export function PaginaCheckout({
  lang, dict, sedeSlug, volverHref, volverLabel, encabezado, aviso, stepper, pasos, pedido,
}: Props) {
  return (
    <div className="min-h-dvh bg-surface">
      <SiteHeader lang={lang} nav={dict.nav} variante="sede" sedeSlugActual={sedeSlug} />

      {/* SiteHeader es `fixed` y no reserva espacio: `--nav-alto` (globals.css)
          lo compensa. El 1.5rem es la separación de siempre. */}
      <div className="mx-auto max-w-6xl px-6 pt-[calc(1.5rem_+_var(--nav-alto))] sm:px-8 lg:px-12">
        <Link
          href={volverHref}
          className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-foreground"
        >
          <ArrowLeft size={16} />
          {volverLabel}
        </Link>
        {encabezado}
      </div>

      {aviso}

      <CheckoutStepper
        stepper={dict.checkout.stepper}
        actual={stepper.actual}
        steps={stepper.steps}
        totalMovil={stepper.totalMovil}
      />

      {/* 3fr/2fr: los pasos necesitan el ancho, el pedido es una columna de cifras. */}
      <main className="mx-auto grid min-w-0 max-w-6xl gap-10 px-6 pt-6 pb-24 sm:px-8 lg:grid-cols-[3fr_2fr] lg:items-start lg:gap-12 lg:px-12">
        <div className="flex min-w-0 flex-col gap-6">{pasos}</div>
        <div className="min-w-0">{pedido}</div>
      </main>

      <CheckoutFooter lang={lang} footer={dict.footer} nav={dict.nav} />
    </div>
  );
}
```

- [ ] **Paso 3: verificar.**

```bash
npx.cmd tsc --noEmit
npx.cmd eslint src/components/checkout
```
Esperado: sin errores. Si `SiteHeader` exige `sedeSlugActual` obligatorio o `CheckoutFooter` firma distinta, ajustar a la firma real (revisar `site-header.tsx`/`checkout-footer.tsx`; `CheckoutView` hoy llama `<SiteHeader lang nav variante="sede" />` sin `sedeSlugActual`).

- [ ] **Paso 4: commit.**

```bash
git add frontend/src/components/checkout/encabezado-compra.tsx frontend/src/components/checkout/pagina-checkout.tsx
git commit -m "feat(checkout): esqueleto de pagina y encabezado de compra compartidos

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 8: `StripePanel` en dos zonas

**Archivos:**
- Modificar: `frontend/src/components/stripe-panel.tsx`

**Interfaces:**
- Consume: `checkout.howYouPay`, `checkout.summary.*` (Tarea 4).
- Produce: `StripePanel` acepta además `lineasViaje?: { etiqueta: string; valor: string }[]` (zona "qué compras", antes de las líneas de cobro) y `pagoVisibleMovil?: boolean` (default `true`). La zona "cómo pagas" va envuelta en un `div` con `hidden lg:block` cuando `pagoVisibleMovil` es `false`: el panel y Stripe/Turnstile siguen montados, solo se ocultan por CSS en móvil.

- [ ] **Paso 1:** en `StripePanelProps` añadir:

```ts
  /** Lo elegido en el viaje (fecha, hora, personas…), vivo desde el paso 1. */
  lineasViaje?: { etiqueta: string; valor: string }[];
  /** En móvil la zona de pago solo se ve al llegar al último paso; en escritorio siempre. */
  pagoVisibleMovil?: boolean;
```
y en la firma de `StripePanel` desestructurar `lineasViaje = []` y `pagoVisibleMovil = true`.

- [ ] **Paso 2:** al inicio del `CheckoutSectionCard` (antes del `<dl>` de `lines`), insertar:

```tsx
      {lineasViaje.length > 0 && (
        <dl className="mb-4 flex flex-col gap-2 border-b border-border pb-4">
          {lineasViaje.map((linea) => (
            <div key={linea.etiqueta} className="flex items-baseline justify-between gap-4 text-sm">
              <dt className="text-muted">{linea.etiqueta}</dt>
              <dd className="text-right text-foreground first-letter:uppercase">{linea.valor}</dd>
            </div>
          ))}
        </dl>
      )}
```

- [ ] **Paso 3:** después del bloque del total (`<p ...>{total}</p></div>`), abrir el contenedor de la zona de pago y el encabezado, y cerrarlo justo antes de `</CheckoutSectionCard>`:

```tsx
      <div className={pagoVisibleMovil ? undefined : 'hidden lg:block'}>
        <p className="mt-6 text-xs font-semibold tracking-wider text-muted uppercase">
          {checkout.howYouPay}
        </p>
        {/* …aquí queda, sin cambios de lógica, todo lo que ya existía después del total:
            selector de moneda, forma de pago, código promocional, estados
            `unavailable`/`payment`, avisoCargos, deslinde, Turnstile, errores y botón… */}
      </div>
```
Mover dentro de ese `div` los bloques existentes (moneda `fieldset`, forma de pago, promo, `unavailable`, `payment`, y el fragmento final con deslinde/Turnstile/botón) **sin editar su contenido**, salvo el punto siguiente.

- [ ] **Paso 4:** el `fieldset` de moneda pasa de `justify-end` a `justify-between` y sube su margen a `mt-3` (queda como fila "Moneda  [MXN | USD]" dentro de "Cómo pagas"):

```tsx
        <fieldset
          className="mt-3 flex items-center justify-between gap-2"
          disabled={phase === 'submitting'}
        >
```

- [ ] **Paso 5: verificar.**

```bash
npx.cmd tsc --noEmit
npx.cmd eslint src/components/stripe-panel.tsx
```
Esperado: sin errores (las dos props nuevas son opcionales; hasta la Tarea 10 y 11 nadie las pasa).

- [ ] **Paso 6: commit.**

```bash
git add frontend/src/components/stripe-panel.tsx
git commit -m "feat(checkout): panel de pedido en dos zonas (que compras / como pagas)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 9: Ayuda flotante (hook + componente)

**Archivos:**
- Crear: `frontend/src/components/checkout/use-ayuda-contextual.ts`
- Crear: `frontend/src/components/checkout/ayuda-flotante.tsx`

**Interfaces:**
- Consume: `ayudaInicial`, `registrarTropiezo`, `descartarAyuda`, `ofreceAyudaFlotante`, `motivoDeAyuda`, `TipoTropiezo` (Tarea 2); `tieneWhatsapp`, `whatsappHref` (`@/lib/contacto`).
- Produce: `useAyudaContextual(): { visible: boolean; motivo: TipoTropiezo; tropezar: (tipo: TipoTropiezo) => void; descartar: () => void }`; `AyudaFlotante({ visible, etiqueta, cerrarLabel, mensaje, onDescartar })`.

- [ ] **Paso 1:** `use-ayuda-contextual.ts`:

```ts
'use client';

import { useCallback, useState } from 'react';
import {
  ayudaInicial, descartarAyuda, motivoDeAyuda, ofreceAyudaFlotante, registrarTropiezo,
  type TipoTropiezo,
} from '@/lib/ayuda-contextual';

/** Estado de React sobre las reglas puras de `lib/ayuda-contextual.ts`. */
export function useAyudaContextual() {
  const [estado, setEstado] = useState(ayudaInicial);
  const tropezar = useCallback(
    (tipo: TipoTropiezo) => setEstado((actual) => registrarTropiezo(actual, tipo)),
    [],
  );
  const descartar = useCallback(() => setEstado((actual) => descartarAyuda(actual)), []);
  return {
    visible: ofreceAyudaFlotante(estado),
    motivo: motivoDeAyuda(estado),
    tropezar,
    descartar,
  };
}
```

- [ ] **Paso 2:** `ayuda-flotante.tsx`. Es `position: fixed`: nunca empuja ni reacomoda el contenido. `z-30` queda debajo del aviso de cookies (`z-40`) y del header; el toast va arriba (no choca):

```tsx
'use client';

import { WhatsappLogo, X } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';

/**
 * Salida de emergencia durante el llenado: aparece solo tras varios tropiezos
 * (ver `lib/ayuda-contextual.ts`), flotando en la esquina, sin mover nada de la
 * página. Se puede cerrar y no vuelve en esa visita. Sin número de WhatsApp
 * configurado no pinta nada (mismo criterio que `ErrorBlock`).
 */
export function AyudaFlotante({
  visible,
  etiqueta,
  cerrarLabel,
  mensaje,
  onDescartar,
}: {
  visible: boolean;
  etiqueta: string;
  cerrarLabel: string;
  /** Mensaje ya redactado para la vendedora. */
  mensaje: string;
  onDescartar: () => void;
}) {
  const sinMovimiento = useReducedMotion();
  if (!tieneWhatsapp) return null;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="ayuda-flotante"
          role="complementary"
          aria-label={etiqueta}
          initial={sinMovimiento ? { opacity: 0 } : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="fixed right-4 bottom-4 z-30 flex items-center rounded-full bg-[#25D366] pl-4 text-sm font-medium text-white shadow-lg"
        >
          <a
            href={whatsappHref(mensaje)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 py-2.5"
          >
            <WhatsappLogo size={18} weight="fill" />
            {etiqueta}
          </a>
          <button
            type="button"
            onClick={onDescartar}
            aria-label={cerrarLabel}
            className="ml-1 flex h-9 w-9 items-center justify-center rounded-full transition-colors hover:bg-black/10"
          >
            <X size={14} weight="bold" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Paso 3: verificar.**

```bash
npx.cmd tsc --noEmit
npx.cmd eslint src/components/checkout
```

- [ ] **Paso 4: commit.**

```bash
git add frontend/src/components/checkout/use-ayuda-contextual.ts frontend/src/components/checkout/ayuda-flotante.tsx
git commit -m "feat(checkout): boton flotante de WhatsApp tras tropiezos repetidos

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 10: Migrar el paquete (`GrupoServicio` + `PedidoPaquete`)

**Archivos:**
- Modificar: `frontend/src/components/pedido/grupo-servicio.tsx`
- Modificar: `frontend/src/components/pedido/pedido-paquete.tsx`

**Interfaces:**
- Consume: todo lo de las Tareas 1-9.
- Cambia `GrupoServicio` Props: **quita** `mostrarInicio`, `onInicio`; **añade** `onTope?: () => void` (se pasa a `PeopleStepper.onMaxAttempt`); `conEncabezadoEmpresa`/`nombreEmpresa` pasan a alimentar `etiqueta` de la card.

#### 10A — `GrupoServicio`

- [ ] **Paso 1:** props: eliminar `mostrarInicio` y `onInicio` (tipo y firma); añadir `onTope?: () => void`. Eliminar el import de `FechaPaquete` **solo si** sigue sin usarse (el selector de fecha de regreso del traslado lo sigue usando: se queda). Importar `BotonPaso` (`@/components/checkout/boton-paso`), `BloqueDePaso` (`@/components/checkout-section-card`) y `separarPersonalizaciones` (`@/lib/personalizaciones`).

- [ ] **Paso 2:** el resumen colapsado deja de repetir la empresa y la fecha (ahora viven en la etiqueta y en la card de viaje):

```tsx
  const resumen = precioDependeDePersonas
    ? personasTexto
    : `${estado.personas} ${estado.personas === 1 ? checkout.peopleUnit.one : checkout.peopleUnit.other}`;
```

- [ ] **Paso 3:** reescribir el `return` con la anatomía nueva. Orden de bloques: **personas → traslado → extras obligatorios → extras opcionales**; la empresa solo como `etiqueta`; el botón en `pie` solo si `estadoTarjeta === 'activo'`:

```tsx
  const { obligatorias, opcionales } = separarPersonalizaciones(servicio.personalizaciones);
  const renderExtra = (extra: (typeof servicio.personalizaciones)[number]) => {
    /* mover aquí, SIN cambios, el cuerpo de la función del
       `servicio.personalizaciones.map((extra) => { … })` actual
       (const seleccion … hasta el return del <label>) */
  };

  return (
    <CheckoutSectionCard
      title={servicio.nombre}
      etiqueta={conEncabezadoEmpresa ? nombreEmpresa : undefined}
      estado={estadoTarjeta}
      resumen={resumen}
      actionLabel={estadoTarjeta === 'completado' ? checkout.changeStep : estadoTarjeta === 'editando' ? checkout.doneEditing : undefined}
      onAction={estadoTarjeta === 'activo' ? undefined : onAccion}
      pie={estadoTarjeta === 'activo' ? (
        <BotonPaso onClick={onCompletar}>{checkout.confirmStep}</BotonPaso>
      ) : undefined}
    >
      {esLogistica ? (
        <PeopleStepper /* …props actuales… */ onMaxAttempt={onTope} />
      ) : precioDependeDePersonas ? (
        <p className="text-sm text-muted">{personasTexto}</p>
      ) : (
        <div>
          <div className="border border-border bg-surface">
            <PeopleStepper /* …props actuales… */ onMaxAttempt={onTope} />
          </div>
          <p className="mt-2 text-xs text-muted">
            {pedido.peopleIncluded.replace('{n}', String(componente.personas_incluidas))}
          </p>
        </div>
      )}

      {/* bloques de traslado: los dos `{traslado && …}` actuales, sin `mt-5`
          ni `border-t pt-5` (el espacio lo pone la card), cada uno como
          <BloqueDePaso> */}

      {obligatorias.length > 0 && (
        <BloqueDePaso titulo={checkout.extrasRequiredLabel}>
          {obligatorias.map(renderExtra)}
        </BloqueDePaso>
      )}
      {opcionales.length > 0 && (
        <BloqueDePaso titulo={pedido.extrasTitle} opcional={checkout.optionalTag}>
          {opcionales.map(renderExtra)}
        </BloqueDePaso>
      )}
    </CheckoutSectionCard>
  );
```
El `PeopleStepper` de `esLogistica` queda envuelto en `<div className="border border-border bg-surface">` igual que el otro (misma caja que en el paso de viaje). Quitar el bloque `{conEncabezadoEmpresa && <p …>}` y el bloque `{mostrarInicio && …}` del cuerpo, y el `{estadoTarjeta === 'activo' && …}` del final (ya está en `pie`).

- [ ] **Paso 4: verificar.**

```bash
npx.cmd tsc --noEmit
```
Esperado: errores solo en `pedido-paquete.tsx` por las props `mostrarInicio`/`onInicio` (se resuelven en 10B).

#### 10B — `PedidoPaquete`

- [ ] **Paso 5: estado de pasos.** Reemplazar `const [paso, setPaso] = useState(1)` y `datosEditando` por la secuencia compartida; importar `estadoDeTarjeta`, `numeroDePaso`, `type PasoId` de `@/lib/pasos-checkout`, `useAyudaContextual`, `AyudaFlotante`, `PaginaCheckout`, `EncabezadoCompra`, `ContenidoViaje`, `CamposContacto`, `BotonPaso`:

```tsx
  const [actual, setActual] = useState<PasoId>('viaje');
  const [editando, setEditando] = useState<PasoId | null>(null);
  const tarjeta = (id: PasoId) => estadoDeTarjeta(id, actual, editando);
  const ayuda = useAyudaContextual();
```
Eliminar `topeIntentado`/`setTopeIntentado`.

Mapeo de usos viejos → nuevos:

| Antes | Después |
|---|---|
| `paso === 1`, `paso > 1`, `datosEditando` | `tarjeta('contacto')` (`'activo'` / `'editando'` / `'completado'`) |
| `setDatosEditando((a) => !a)` | `setEditando((e) => (e === 'contacto' ? null : 'contacto'))` |
| `paso >= 2` (mostrar grupos) | `tarjeta('detalles') !== 'oculto'` |
| `paso < 3` (`submitDisabled`, `enviar`, panel móvil) | `actual !== 'pago'` |
| `setPaso(3)` en `confirmarGrupo` | `setActual('pago')` |
| `actual={paso}` del stepper | `actual={numeroDePaso(actual)}` y quitar `steps={pasos}` |

Eliminar la constante `pasos` (usaba etiquetas distintas a servicio); el stepper usa las cuatro por defecto (`viaje`, `datos`, `personalizar`, `pago`). Quitar también `steps={pasos}` de las dos llamadas a `CheckoutStepper` de las pantallas de fallo y de pago (ahí `actual={4}` queda igual).

- [ ] **Paso 6: confirmar viaje y contacto.**

```tsx
  const confirmarViaje = () => {
    if (!estado.inicio) {
      setErrorViaje(traslados.errors.seleccionaFecha);
      ayuda.tropezar('validacion');
      return;
    }
    setErrorViaje('');
    setEditando(null);
    setActual((a) => (a === 'viaje' ? 'contacto' : a));
  };

  const confirmarDatos = () => {
    if (!validarDatos()) {
      ayuda.tropezar('validacion');
      return;
    }
    setEditando(null);
    setActual((a) => (a === 'contacto' ? 'detalles' : a));
  };
```
con `const [errorViaje, setErrorViaje] = useState('')`. En `confirmarGrupo`: si hay `error`, además de `setErrorDetalles(error)` llamar `ayuda.tropezar('validacion')`. En `enviar`: `if (!waiverAccepted) { ayuda.tropezar('validacion'); return setErrorWaiver(true); }` y en el ramal `!validarDatos()` también `ayuda.tropezar('validacion')`. En `enviar`, el chequeo `paso < 3` pasa a `actual !== 'pago'`.

- [ ] **Paso 7: pantalla principal.** Reemplazar el `return` del formulario (hoy ~L418-L629) por `PaginaCheckout`. Estructura (los textos salen de diccionarios existentes salvo los de la Tarea 4):

```tsx
  const empresas = [...new Set(paquete.servicios_asociados.map((c) => nombreEmpresa(c.servicio.empresa_slug)))];
  const detalleCompra = [
    paquete.sede,
    empresas.join(' + '),
    noches !== null ? checkout.purchaseNights.replace('{n}', String(noches)) : null,
  ].filter(Boolean).join(' · ');
  const resumenViaje = [
    estado.inicio ? formatearFecha(estado.inicio) : null,
    paquete.pide_hora && estado.hora ? formatHour(estado.hora) : null,
    paquete.precio_depende_de_personas
      ? `${personasPaquete} ${personasPaquete === 1 ? checkout.peopleUnit.one : checkout.peopleUnit.other}`
      : null,
  ].filter(Boolean).join(' · ');
  const lineasViaje = [
    estado.inicio ? { etiqueta: checkout.summary.date, valor: formatearFecha(estado.inicio) } : null,
    salida && noches !== null ? { etiqueta: checkout.summary.checkOut, valor: formatearFecha(salida) } : null,
    paquete.pide_hora && estado.hora ? { etiqueta: checkout.summary.time, valor: formatHour(estado.hora) } : null,
    paquete.precio_depende_de_personas
      ? { etiqueta: checkout.summary.people, valor: String(personasPaquete) }
      : null,
  ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null);
```
(`formatHour` viene de `@/lib/dates`.) Y el JSX:

```tsx
  return (
    <>
      <PaginaCheckout
        lang={lang} dict={dict} sedeSlug={sedeSlug}
        volverHref={`/${lang}/sede/${sedeSlug}`} volverLabel={textos.back}
        encabezado={<EncabezadoCompra kicker={checkout.purchaseKicker} nombre={paquete.nombre} detalle={detalleCompra} />}
        stepper={{ actual: numeroDePaso(actual), totalMovil }}
        pasos={<>
          {/* 1 · Viaje */}
          <CheckoutSectionCard
            title={checkout.tripHeadline}
            estado={tarjeta('viaje') as 'activo' | 'editando' | 'completado'}
            resumen={resumenViaje}
            actionLabel={tarjeta('viaje') === 'completado' ? checkout.changeStep : tarjeta('viaje') === 'editando' ? checkout.doneEditing : undefined}
            onAction={tarjeta('viaje') === 'activo' ? undefined : () => setEditando((e) => (e === 'viaje' ? null : 'viaje'))}
            pie={tarjeta('viaje') === 'activo' ? <BotonPaso onClick={confirmarViaje}>{checkout.confirmStep}</BotonPaso> : undefined}
          >
            <ContenidoViaje
              fecha={<FechaPaquete /* props que hoy usa GrupoServicio para `mostrarInicio`: label={textos.startLabel}, value={estado.inicio}, onChange={(valor) => despachar({ tipo: 'inicio', valor })}, minDate, chooseLabel, viewMonthLabel, hideMonthLabel, previousWeekLabel, nextWeekLabel, previousMonthLabel={booking.prevMonth}, nextMonthLabel={booking.nextMonth}, personas={personasPaquete}, fullLabel={checkout.dayFull} */ />}
              hora={paquete.pide_hora ? (
                <TimeField label={checkout.hourLabel} help={booking.timeHelp} value={estado.hora}
                  availableHours={horasDePaquete(paquete)}
                  onChange={(valor) => despachar({ tipo: 'hora', valor })} />
              ) : undefined}
              personas={paquete.precio_depende_de_personas && maxPersonas !== null ? (
                <PeopleStepper label={textos.peopleQuestion}
                  maxNotice={(tieneWhatsapp ? textos.morePeople : textos.morePeopleOffline).replace('{max}', String(maxPersonas))}
                  value={personasPaquete} maxPeople={maxPersonas} minPeople={1}
                  onChange={(valor) => { if (slugPrincipal) despachar({ tipo: 'personasPaquete', slugPrincipal, valor }); }}
                  onMaxAttempt={() => ayuda.tropezar('tope-personas')} />
              ) : undefined}
              nota={<>
                {noches !== null && salida && (
                  <p>{textos.nightsNote.replace('{n}', String(noches)).replace('{fecha}', formatearFecha(salida))}</p>
                )}
                {paquete.precio_depende_de_personas && (
                  <>
                    <p className="font-medium text-foreground">
                      {anclaMostrada} {estado.moneda}{' '}
                      {paquete.estrategia_precio === 'por_persona'
                        ? textos.perPerson
                        : textos.perGroup.replace('{n}', String(paquete.personas_precio_base))}
                    </p>
                    {paquete.estrategia_precio === 'por_grupo' && extra !== null && (
                      <p>{textos.extraPerson.replace('{precio}', formatearPrecio(extra, estado.moneda))}</p>
                    )}
                    <p>{precioPersonas}</p>
                  </>
                )}
              </>}
            />
            {errorViaje && <FieldError id="pedido-viaje-error" mensaje={errorViaje} />}
          </CheckoutSectionCard>

          {/* 2 · Datos */}
          {tarjeta('contacto') !== 'oculto' && (
            <CheckoutSectionCard
              title={checkout.contactHeadline}
              estado={tarjeta('contacto') as 'activo' | 'editando' | 'completado'}
              resumen={`${estado.contacto.fullName} · ${estado.contacto.email}`}
              actionLabel={tarjeta('contacto') === 'completado' ? checkout.changeStep : tarjeta('contacto') === 'editando' ? checkout.doneEditing : undefined}
              onAction={tarjeta('contacto') === 'activo' ? undefined : () => setEditando((e) => (e === 'contacto' ? null : 'contacto'))}
              pie={tarjeta('contacto') === 'activo' ? <BotonPaso onClick={confirmarDatos}>{checkout.confirmStep}</BotonPaso> : undefined}
            >
              <CamposContacto
                idPrefijo="pedido"
                valores={estado.contacto}
                errores={erroresContacto}
                etiquetas={{ phone: checkout.phone, fullName: checkout.fullName, email: checkout.email }}
                onCambio={(campo, valor) => despachar({ tipo: 'contacto', cambios: { [campo]: valor } })}
              />
            </CheckoutSectionCard>
          )}

          {/* 3 · Detalles: un grupo por servicio (código existente del `.map`),
              mostrado cuando tarjeta('detalles') !== 'oculto'; ya no pasa
              `mostrarInicio`/`onInicio`; añade
              `onTope={() => ayuda.tropezar('tope-personas')}`. */}
        </>}
        pedido={pedido ? (
          <StripePanel /* props actuales */
            lineasViaje={lineasViaje}
            pagoVisibleMovil={actual === 'pago'}
            usdDisponible={conUsd}
            submitDisabled={actual !== 'pago'}
          />
        ) : (<ErrorBlock /* igual que hoy */ />)}
      />
      <AyudaFlotante
        visible={ayuda.visible}
        etiqueta={feedback.floatingHelp.label}
        cerrarLabel={feedback.floatingHelp.dismiss}
        mensaje={ayuda.motivo === 'tope-personas' && maxPersonas !== null
          ? feedback.floatingHelp.messageMaxPeople.replace('{name}', paquete.nombre).replace('{max}', String(maxPersonas))
          : feedback.floatingHelp.messageValidation
              .replace('{date}', formatearFecha(estado.inicio ?? minDate))
              .replace('{people}', String(personasPaquete))}
        onDescartar={ayuda.descartar}
      />
    </>
  );
```
Detalles que quedan fuera del JSX de arriba y se hacen tal cual el código actual: el `{errorDetalles && <FieldError …/>}` y el `paquete.servicios_asociados.map(...)` de `GrupoServicio` (quitar `mostrarInicio` y `onInicio`; el cálculo `tarjeta` por grupo usa `gruposCompletados`/`grupoEditando` como hoy). El `Pedido.title` y la sección suelta de precio/personas (`<section … aria-label={textos.peopleQuestion}>`), el toggle de moneda superior (`conUsd && <fieldset …>`), el `topeIntentado` y su enlace/`<p>` quedan **eliminados**. El `useEffect` y `pago.*` no cambian.

- [ ] **Paso 8:** la pantalla de `pago.fase === 'pagando'` usa también `PaginaCheckout` con tarjetas `completado` de viaje, contacto y cada grupo (hoy ya hay contacto y grupos; añadir una de viaje con el mismo `resumenViaje`) y `StripePanel` con `pagoVisibleMovil` (siempre `true` aquí) y `lineasViaje={lineasViaje}`.

- [ ] **Paso 9: verificar.**

```bash
npx.cmd tsc --noEmit
npx.cmd eslint src tests
npm.cmd test
```
Esperado: sin errores ni pruebas fallidas. Revisar a mano que no queden referencias a `topeIntentado`, `paso`, `datosEditando`, `mostrarInicio`, `onInicio`, `pasos`.

- [ ] **Paso 10: commit.**

```bash
git add frontend/src/components/pedido/grupo-servicio.tsx frontend/src/components/pedido/pedido-paquete.tsx
git commit -m "feat(checkout): paquete con pasos viaje-contacto-detalles-pago y anatomia unificada

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 11: Migrar el servicio suelto (`CheckoutView`)

**Archivos:**
- Modificar: `frontend/src/components/checkout-view.tsx`

**Interfaces:**
- Consume: Tareas 1-9. Conserva toda la lógica de recuperación, cupo, promo, guardado y pago.

- [ ] **Paso 1: estado de pasos.** Importar `estadoDeTarjeta`, `numeroDePaso`, `type PasoId`, `PaginaCheckout`, `EncabezadoCompra`, `ContenidoViaje`, `CamposContacto`, `BotonPaso`, `BloqueDePaso`, `separarPersonalizaciones`, `useAyudaContextual`, `AyudaFlotante`. Reemplazar `pasosVisibles`, `extrasConfirmado` y `pasoEditando` por:

```tsx
  const [actual, setActual] = useState<PasoId>('viaje');
  const [editando, setEditando] = useState<PasoId | null>(null);
  const ayuda = useAyudaContextual();
```
Mapeo:

| Antes | Después |
|---|---|
| `setPasosVisibles(2)` (confirmar viaje) | `setActual((a) => (a === 'viaje' ? 'contacto' : a))` |
| `setPasosVisibles(3)` en `confirmarContacto`, y `if (pasoEditando === 2) setPasoEditando(null)` | `setActual((a) => (a === 'contacto' ? 'detalles' : a)); setEditando(null)` |
| recuperación `pendiente_pago`: `setPasosVisibles(3); setExtrasConfirmado(true)` | `setActual('pago')` |
| confirmar extras: `setExtrasConfirmado(true); if (pasoEditando === 3) …` | `setActual('pago'); setEditando(null)` |
| `colapsado1/2/3` | `estadoDeTarjeta('viaje'|'contacto'|'detalles', actual, editando)`; `locked` fuerza `detalles` a `completado` sin permitir reabrir (`onAction` queda `undefined` si `locked`) |
| `pasoActualStepper` | `phase === 'submitting' \|\| phase === 'payment' ? 4 : numeroDePaso(actual)` |
| `!extrasConfirmado ? 'hidden lg:block' : …` | `pagoVisibleMovil={actual === 'pago'}` |

- [ ] **Paso 2: tropiezos.** En `confirmarContacto` y en `iniciarPago`: cada `return` por errores de contacto, por `!waiverAccepted` o por `erroresDePersonalizacion` llama antes `ayuda.tropezar('validacion')`. El tope de personas del `PeopleStepper` del viaje recibe `onMaxAttempt={() => ayuda.tropezar('tope-personas')}`.

- [ ] **Paso 3: resumen vivo.** Construir y pasar al panel:

```tsx
  const lineasViaje = [
    { etiqueta: checkout.summary.date, valor: formatDay(dayDate, lang) },
    tieneHospedaje ? { etiqueta: checkout.summary.checkOut, valor: formatDay(fromLocalISODate(fechaSalida), lang) } : null,
    horaTexto ? { etiqueta: checkout.summary.time, valor: horaTexto } : null,
    { etiqueta: checkout.summary.people, valor: String(people) },
  ].filter((linea): linea is { etiqueta: string; valor: string } => linea !== null);
```
`<StripePanel … lineasViaje={lineasViaje} pagoVisibleMovil={actual === 'pago'} />` y, para el stepper móvil, `totalMovil = total !== null ? `${currency.format(total)} ${moneda}` : undefined`. Quitar el wrapper `className={`scroll-mt-28 ${!extrasConfirmado ? 'hidden lg:block' : undefined}`}` pero conservar `ref={refStripePanel}` y `scroll-mt-28` (el scroll al confirmar extras sigue apuntando ahí).

- [ ] **Paso 4: esqueleto.** Sustituir el JSX desde `<div className="min-h-dvh bg-surface">` (L1060) hasta el cierre del footer por `PaginaCheckout`: `volverHref` y `volverLabel` los mismos que el enlace actual; `encabezado={<EncabezadoCompra kicker={checkout.purchaseKicker} nombre={servicioNombre || servicio?.nombre || ''} />}`; el bloque `sinLugar` (L1079-L1113) como `aviso`; las tres tarjetas dentro de `pasos`; `StripePanel` (con el `ErrorBlock`/resto que ya rodea) en `pedido`. Eliminar el banner "Servicio seleccionado" (L1121-L1128). Importes y `AmenitiesReminder` (modal) se quedan fuera del esqueleto, como hoy.

- [ ] **Paso 5: tarjeta de viaje.** Contenido con `ContenidoViaje`; pie con `BotonPaso` solo si `estado === 'activo'`:

```tsx
            <ContenidoViaje
              fecha={<>
                <CheckoutCalendar /* props actuales */ />
                <p className="mt-5 text-sm text-foreground">{formatDay(dayDate, lang)}</p>
              </>}
              hora={pideHora ? (locked
                ? <p className="px-6 py-4 text-sm text-muted">{checkout.hourLabel}: <span className="text-foreground">{horaTexto}</span></p>
                : <TimeField /* props actuales */ />) : undefined}
              personas={<PeopleStepper /* props actuales */ onMaxAttempt={() => ayuda.tropezar('tope-personas')} />}
              salida={tieneHospedaje ? (locked
                ? <p className="text-sm text-foreground">{checkout.checkoutDateLabel}: {formatDay(fromLocalISODate(fechaSalida), lang)}</p>
                : <DateField /* props actuales */ />) : undefined}
              nota={precioPersonaExtra > 0 ? (
                <p>{checkout.extraPeopleHint.replace('{included}', String(personasIncluidas)).replace('{price}', currency.format(precioPersonaExtra))}</p>
              ) : undefined}
            />
```
Quitar la fila "¿Confirmas el día y la hora…?" + botón (L1208-L1222) y el `<p className="mt-2 px-6 …">` suelto de `extraPeopleHint`.

- [ ] **Paso 6: tarjeta de datos.** Reemplazar los tres `<label>` por `CamposContacto`:

```tsx
              <CamposContacto
                idPrefijo="checkout"
                valores={contact}
                errores={erroresCampo}
                etiquetas={{ phone: checkout.phone, fullName: checkout.fullName, email: checkout.email }}
                refs={{ phone: refPhone, fullName: refFullName, email: refEmail }}
                disabled={locked}
                onCambio={(campo, valor) => {
                  setContact((prev) => ({ ...prev, [campo]: valor }));
                  // El error se limpia al escribir: dejarlo puesto mientras el
                  // cliente corrige lo convierte en un regaño que no se calla.
                  if (erroresCampo[campo]) setErroresCampo((prev) => ({ ...prev, [campo]: undefined }));
                }}
              />
```
Pie con `BotonPaso onClick={confirmarContacto}` solo si `activo`. Eliminar la fila de pregunta + botón (L1339-L1350).

- [ ] **Paso 7: tarjeta de extras (detalles).** Extraer el cuerpo del `catalogoUnificado.map((sp) => { … })` a `const renderPersonalizacion = (sp: (typeof catalogoUnificado)[number]) => { … }` sin cambiar su contenido, y renderizar:

```tsx
                {(() => {
                  const { obligatorias, opcionales } = separarPersonalizaciones(catalogoUnificado);
                  return (
                    <>
                      {obligatorias.length > 0 && (
                        <BloqueDePaso titulo={checkout.extrasRequiredLabel}>
                          {obligatorias.map(renderPersonalizacion)}
                        </BloqueDePaso>
                      )}
                      {opcionales.length > 0 && (
                        <BloqueDePaso titulo={checkout.extrasOptionalLabel} opcional={checkout.optionalTag}>
                          {opcionales.map(renderPersonalizacion)}
                        </BloqueDePaso>
                      )}
                    </>
                  );
                })()}
```
Pie: `<BotonPaso conFlecha onClick={…lo que hace hoy el onClick del botón de extras: setActual('pago'), setEditando(null), scrollIntoView…}>{checkout.continueToPayment || checkout.confirmStep}</BotonPaso>` solo si `activo`. Eliminar la fila con `extrasConfirmQuestion` y el botón cuadrado.

- [ ] **Paso 8: ayuda flotante.** Al final del `return` (hermano de `PaginaCheckout`, como en la Tarea 10):

```tsx
      <AyudaFlotante
        visible={ayuda.visible}
        etiqueta={dict.feedback.floatingHelp.label}
        cerrarLabel={dict.feedback.floatingHelp.dismiss}
        mensaje={ayuda.motivo === 'tope-personas'
          ? dict.feedback.floatingHelp.messageMaxPeople
              .replace('{name}', servicio?.nombre ?? servicioNombre ?? '')
              .replace('{max}', String(servicio?.personas_incluidas ?? people))
          : dict.feedback.floatingHelp.messageValidation
              .replace('{date}', formatDay(dayDate, lang))
              .replace('{people}', String(people))}
        onDescartar={ayuda.descartar}
      />
```
(El tope de personas del servicio en `PeopleStepper` sale de `maxPeople`; si el viaje no lo pasa, usa `MAX_PEOPLE` de `@/lib/dates`: usar ese mismo valor en el mensaje.)

- [ ] **Paso 9: verificar.**

```bash
npx.cmd tsc --noEmit
npx.cmd eslint src tests
npm.cmd test
```
Esperado: sin errores. Revisar a mano que no queden `pasosVisibles`, `extrasConfirmado`, `pasoEditando`, `colapsado1/2/3`, `tripConfirmQuestion`, `contactConfirmQuestion`, `extrasConfirmQuestion` en uso.

- [ ] **Paso 10: commit.**

```bash
git add frontend/src/components/checkout-view.tsx
git commit -m "feat(checkout): servicio suelto sobre el esqueleto y las cards compartidas

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Tarea 12: Skeletons, documentación y gate final

**Archivos:**
- Modificar: `frontend/src/app/[lang]/reservar/loading.tsx`
- Modificar: `frontend/CLAUDE.md`

- [ ] **Paso 1:** `reservar/loading.tsx` pasa a reflejar el encabezado y el pedido visible en móvil:

```tsx
    <CheckoutLoadingShell withTitle showSummaryMobile>
```
(`traslados/loading.tsx` no se toca: queda con los valores por omisión.)

- [ ] **Paso 2:** en `frontend/CLAUDE.md`, sección "Checkout unificado de paquetes", añadir (prosa normal, no caveman):

```markdown
- Anatomía común de la ruta `/reservar` (servicio suelto, paquete de una
  empresa y paquete cruza-empresa): `PaginaCheckout`
  (`src/components/checkout/pagina-checkout.tsx`) pone volver → `EncabezadoCompra`
  → stepper → [pasos | pedido]. Los pasos son siempre viaje → contacto →
  detalles → pago (`src/lib/pasos-checkout.ts`); cada tarjeta es un
  `CheckoutSectionCard` con un solo CTA en el `pie` (`BotonPaso`) y bloques
  separados por espacio, no por rayas. El panel derecho (`StripePanel`) tiene
  dos zonas: "qué compras" (líneas vivas del viaje, cargos y total) y "cómo
  pagas" (moneda, forma de pago, promo, deslinde, botón). Dentro de cada
  tarjeta: lo obligatorio antes que lo opcional
  (`separarPersonalizaciones`). `AyudaFlotante` ofrece WhatsApp, sin mover la
  página, tras tres tropiezos (`src/lib/ayuda-contextual.ts`): errores de
  validación al confirmar pasos o intentos de pasar el tope de personas.
```

- [ ] **Paso 3: gate completo.** Desde `frontend/`:

```bash
npx.cmd tsc --noEmit
npx.cmd eslint src tests
npm.cmd test
npm.cmd run build
```
Esperado: los cuatro terminan sin errores.

- [ ] **Paso 4: commit.**

```bash
git add "frontend/src/app/[lang]/reservar/loading.tsx" frontend/CLAUDE.md
git commit -m "docs(checkout): documenta la anatomia unificada y alinea el skeleton

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

- [ ] **Paso 5:** avisar al dueño que reinicie `npm run dev` (se editaron diccionarios) y revise el sitio: servicio suelto, paquete de una empresa, paquete cruza-empresa, móvil y escritorio, y provocar la ayuda flotante (3 clics en "Confirmar" con campos vacíos, o 3 intentos de pasar el tope de personas).

---

## Autorrevisión

**Cobertura de la spec:**
- R1 (≤4 bloques, una card activa, panel en dos zonas): cuerpo en bloques (T5), `pasos-checkout` (T1), `StripePanel` en zonas (T8), grupos reordenados (T10).
- R2 (mismo esqueleto/anatomía): `PaginaCheckout` (T7), `CheckoutSectionCard` + `BotonPaso` (T5), migración de los dos checkouts (T10, T11).
- R3 (orden fijo, obligatorio antes que opcional): `pasos-checkout` (T1), `separarPersonalizaciones` (T3), `ContenidoViaje` (T6), traslado antes de extras (T10), extras separados (T10, T11).
- R4 (un CTA, prellenado, secundarios plegados): `pie` solo en `activo` (T5), moneda dentro de "cómo pagas" y promo plegada ya existente (T8).
- R5 (qué compras fijo, resumen vivo, empresa única): `EncabezadoCompra` (T7), `lineasViaje` (T8, T10, T11), `etiqueta` de empresa (T5, T10).
- Decisiones 1-6: contacto tras viaje (T10), moneda (T8, T10), resumen vivo y móvil (T8, T10, T11), componentes compartidos (T5-T9), pregunta junto al botón eliminada (T10, T11), ayuda flotante (T2, T9, T10, T11).
- Ayuda por tope de personas: `onMaxAttempt` en `PeopleStepper` (ya existía) cableado en T10/T11; el enlace en línea que empujaba contenido (`topeIntentado`) se elimina (T10).

**Escaneo de marcadores:** las tareas 10 y 11 mueven bloques existentes "sin cambios" (señalados por su ubicación en el archivo) en lugar de pegar cientos de líneas ya presentes; todo código nuevo o modificado está escrito. No quedan "TBD".

**Consistencia de tipos:** `PasoId`/`estadoDeTarjeta`/`numeroDePaso` (T1) se usan igual en T10 y T11. `TipoTropiezo`, `registrarTropiezo`, `descartarAyuda`, `ofreceAyudaFlotante`, `motivoDeAyuda` (T2) son los que consume `useAyudaContextual` (T9). `lineasViaje: { etiqueta; valor }[]` y `pagoVisibleMovil` (T8) son los que pasan T10 y T11. `GrupoServicio` pierde `mostrarInicio`/`onInicio` (T10A) y `PedidoPaquete` deja de pasarlos (T10B). `CamposContacto.onCambio(campo, valor)` coincide con el despacho `{ tipo: 'contacto', cambios: { [campo]: valor } }` del reducer existente.

**Fuera de alcance / riesgos conocidos:**
- `traslado-view.tsx` conserva su anatomía propia.
- `CheckoutLoadingShell` y los skeletons de otras rutas no cambian salvo `reservar/loading.tsx`.
- El cobro por empresa, la reanudación (`sessionStorage`) y la lógica de pago no se tocan.
