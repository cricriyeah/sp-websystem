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

test('chip toma la forma de un token, no rounded-full', () => {
  const clases = botonClases({ variante: 'chip' });
  assert.match(clases, /rounded-control/);
  assert.doesNotMatch(clases, /rounded-full/);
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
  assert.match(titulo, /texto-subtitulo/);
  assert.match(cuerpo, /texto-cuerpo/);
  assert.match(acciones, /flex-col/);
  assert.match(acciones, /sm:flex-row/);
  assert.match(boton, /\bw-full\b/);
  assert.match(boton, /sm:w-auto/);
});
