/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { botonClases } = require(path.join(process.env.VARIANTES_TEST_OUT, 'components/ui/variantes.js'));

const clase = (variante, nombre, opciones = {}) =>
  botonClases({ variante, ...opciones }).split(' ').includes(nombre);

const ROLES = ['principal', 'secundario', 'texto', 'peligro'];

test('R5: solo la variante principal usa el color de acción (fondo cafe)', () => {
  assert.ok(clase('principal', 'bg-cafe'));
  assert.ok(clase('principal', 'text-white'));
  for (const v of ['secundario', 'texto', 'peligro']) {
    assert.ok(!clase(v, 'bg-cafe'), v);
  }
  // Los textos de las demás variantes pueden ser cafe, pero su fondo no.
  assert.ok(clase('secundario', 'text-cafe'));
  assert.ok(clase('texto', 'text-cafe'));
});

test('los roles de design.md: secundario con borde de control, peligro con error, texto transparente', () => {
  assert.ok(clase('secundario', 'border-borde-control'));
  assert.ok(clase('secundario', 'bg-superficie'));
  assert.ok(clase('peligro', 'bg-error'));
  assert.ok(clase('peligro', 'text-white'));
  assert.ok(clase('texto', 'bg-transparent'));
  assert.ok(clase('principal', 'hover:bg-cafe-hondo'));
  assert.ok(clase('principal', 'active:bg-cafe-profundo'));
});

test('la variante acento ya no existe (se migró a texto)', () => {
  assert.doesNotMatch(botonClases({ variante: 'acento' }), /text-accent/);
  assert.equal(botonClases({ variante: 'acento' }).includes('undefined'), false);
});

test('objetivo táctil: 48 px en móvil y 44 en escritorio; las acciones de texto, 44', () => {
  for (const v of ['principal', 'secundario', 'peligro']) {
    assert.ok(clase(v, 'min-h-12'), v);
    assert.ok(clase(v, 'sm:min-h-11'), v);
  }
  assert.ok(clase('texto', 'min-h-11'));
});

test('el deshabilitado y aria-disabled cambian de color, nunca de opacidad', () => {
  for (const v of ROLES) {
    const clases = botonClases({ variante: v });
    assert.doesNotMatch(clases, /opacity/, v);
    assert.ok(clases.includes('disabled:text-apagado'), v);
    assert.ok(clases.includes('aria-disabled:text-apagado'), v);
  }
  for (const v of ['principal', 'secundario', 'peligro']) {
    assert.ok(clase(v, 'disabled:bg-cafe-bruma'), v);
    assert.ok(clase(v, 'aria-disabled:bg-cafe-bruma'), v);
  }
  assert.ok(clase('secundario', 'disabled:border-transparent'));
});

test('la base lleva el foco de 2 px con desfase de 2 px, la escala 0,98 y el ancho de etiqueta largo en dos renglones', () => {
  const base = botonClases({ variante: 'principal' }).split(' ');
  for (const c of [
    'inline-flex',
    'items-center',
    'justify-center',
    'gap-2',
    'rounded-control',
    'px-6',
    'texto-etiqueta',
    'focus-visible:outline-2',
    'focus-visible:outline-offset-2',
    'focus-visible:outline-ring',
    'active:scale-[0.98]',
    'motion-reduce:active:scale-100',
    'duration-150',
    'text-balance',
    'py-3',
  ]) {
    assert.ok(base.includes(c), c);
  }
  assert.ok(base.includes('ease-[var(--curva-estandar)]'));
});

test('tamaños: md es la base, sm ya no existe, icono es un círculo de 48 × 48 y bloque agrega ancho completo', () => {
  assert.equal(botonClases({ tamano: 'sm' }).includes('undefined'), false);
  assert.ok(!clase('principal', 'px-4', { tamano: 'sm' }));
  assert.ok(clase('principal', 'size-12', { tamano: 'icono' }));
  assert.ok(clase('principal', 'rounded-full', { tamano: 'icono' }));
  assert.ok(clase('principal', 'p-0', { tamano: 'icono' }));
  assert.ok(!clase('principal', 'w-full'));
  assert.ok(clase('principal', 'w-full', { bloque: true }));
});

test('la forma sale de tokens, no de utilidades crudas', () => {
  assert.match(botonClases({ variante: 'principal' }), /rounded-control/);
  assert.doesNotMatch(botonClases({ variante: 'principal' }), /rounded-full/);
});

test('sin colores crudos ni de la marca vieja', () => {
  for (const v of ROLES) {
    const clases = botonClases({ variante: v });
    assert.doesNotMatch(clases, /-(red|green|blue|amber)-\d/);
    assert.doesNotMatch(clases, /bg-action|text-action|bg-accent|text-accent|border-border-strong/);
  }
});

test('fila, chip y libre no heredan la base (su aspecto es el del botón crudo)', () => {
  for (const v of ['fila', 'chip', 'libre']) {
    const clases = botonClases({ variante: v });
    assert.doesNotMatch(clases, /inline-flex/);
    assert.doesNotMatch(clases, /font-medium/);
    assert.doesNotMatch(clases, /bg-action/);
    assert.doesNotMatch(clases, /-(red|green|blue|amber)-\d/);
  }
  assert.equal(botonClases({ variante: 'libre' }), '');
  assert.match(botonClases({ variante: 'principal' }), /inline-flex/);
});

test('fila es el disparador de acordeón de ancho completo', () => {
  const clases = botonClases({ variante: 'fila' }).split(' ');
  for (const c of ['flex', 'w-full', 'items-center', 'justify-between', 'py-5', 'text-left', 'text-lg']) {
    assert.ok(clases.includes(c), c);
  }
});

test('chip es una píldora (radio-full) y no toma el radio de control', () => {
  const clases = botonClases({ variante: 'chip' });
  assert.match(clases, /(^| )rounded-full( |$)/);
  assert.doesNotMatch(clases, /rounded-control/);
});

const { hojaClases, alertaClases } =require(path.join(process.env.VARIANTES_TEST_OUT, 'components/ui/variantes.js'));

const CRUDOS = [
  /-(red|green|blue|amber|gray|slate|zinc|neutral|stone)-\d/, // paleta cruda
  /\brounded(?:-[trblse]{1,2})?-(?:md|lg|xl|2xl|3xl)\b/, // radio crudo
  /\bshadow-(?:\[|xs\b|sm\b|md\b|lg\b|xl\b|2xl\b)/, // sombra cruda
  /#[0-9a-fA-F]{3,8}\b|\brgba?\(/, // color literal
];

function sinCrudos(clases) {
  for (const regex of CRUDOS) assert.doesNotMatch(clases, regex);
}

test('la hoja usa solo tokens y la geometría del plan', () => {
  const { dialogo, asa, cerrar } = hojaClases();
  sinCrudos(Object.values(hojaClases({ sinBorde: true })).join(' '));
  for (const clase of ['inset-x-0', 'bottom-0', 'max-h-[85dvh]', 'overflow-y-auto', 'overscroll-contain', 'bg-superficie', 'rounded-t-sheet', 'shadow-n2', 'hoja-dialogo']) {
    assert.ok(dialogo.split(' ').includes(clase), clase);
  }
  assert.match(dialogo, /pb-\[max\(16px,env\(safe-area-inset-bottom\)\)\]/);
  assert.match(asa, /\bh-1\b/); // 4 px
  assert.match(asa, /\bw-10\b/); // 40 px
  assert.match(asa, /bg-borde-control/);
  assert.match(cerrar, /\bsize-12\b/); // 48 × 48
});

test('sinBorde solo cambia el contenido de la hoja', () => {
  assert.equal(hojaClases().cuerpo, '');
  assert.match(hojaClases({ sinBorde: true }).cuerpo, /border-0/);
  assert.equal(hojaClases({ sinBorde: true }).dialogo, hojaClases().dialogo);
});

test('el diálogo de alerta es centrado, con tokens y botones apilados en móvil', () => {
  const { dialogo, titulo, cuerpo, acciones, boton } = alertaClases();
  sinCrudos(Object.values(alertaClases()).join(' '));
  assert.match(dialogo, /w-\[min\(92vw,420px\)\]/);
  assert.match(dialogo, /rounded-card/);
  assert.match(dialogo, /bg-superficie/);
  assert.match(dialogo, /\bp-6\b/);
  assert.match(dialogo, /shadow-n2/);
  assert.match(dialogo, /alerta-dialogo/);
  assert.match(titulo, /text-foreground/); // el tamaño (texto-subtitulo) va en el <h2>
  assert.match(cuerpo, /texto-cuerpo/);
  assert.match(acciones, /flex-col/);
  assert.match(acciones, /sm:flex-row/);
  assert.match(boton, /\bw-full\b/);
  assert.match(boton, /sm:w-auto/);
});
