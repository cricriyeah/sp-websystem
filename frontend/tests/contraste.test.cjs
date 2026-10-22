/* eslint-disable @typescript-eslint/no-require-imports */
// Contraste WCAG 2.2 de cada par de docs/design/design.md (y design-guidelines.md), calculado
// sobre los valores REALES de src/app/globals.css: si un token cambia y un par deja de dar,
// la prueba falla. Dos comprobaciones por par:
//   1. razón >= mínimo que el documento declara para ese uso (4,5 texto normal; 3 para
//      indicadores, bordes de control y foco; sin mínimo para lo decorativo);
//   2. razón calculada == razón que el documento publica (±0,02: el documento redondea a 2 decimales).
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { resolverToken, leerGlobalsCss } = require('./ayudas/css-tokens.cjs');

const css = leerGlobalsCss();

function luminancia(hex) {
  const canales = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = canales.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function razon(a, b) {
  const [alta, baja] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (alta + 0.05) / (baja + 0.05);
}

const color = (token) => resolverToken(css, `--color-${token}`);

const TEXTO = 4.5; // texto normal
const NO_TEXTO = 3; // iconos, bordes de campos, casillas y focos
const TEXTO_GRANDE = 3; // 24 px o más (o 19 px en negrita): el coral solo admite esto
const DECORATIVO = 0; // sin mínimo

// [texto o elemento, fondo, razón publicada en el documento, mínimo, nota]
const PARES = [
  // Marca: café
  ['blanco', 'cafe', 8.46, TEXTO, 'botón principal'],
  ['blanco', 'cafe-hondo', 11.5, TEXTO, 'hover del botón principal'],
  ['cafe-profundo', 'cafe-bruma', 14.05, TEXTO, 'pulsado, texto sobre cafe-bruma'],
  ['cafe-profundo', 'cafe-claro', 11.84, TEXTO, 'texto sobre aviso y rango de fechas'],
  ['cafe', 'cafe-bruma', 7.87, TEXTO, 'enlace de acción sobre la superficie variante'],
  ['cafe', 'blanco', 8.46, TEXTO, 'botón secundario y texto'],
  // Neutros
  ['tinta', 'arena', 16.07, TEXTO, 'texto principal sobre la página'],
  ['tinta', 'blanco', 17.27, TEXTO, 'texto principal sobre tarjetas y campos'],
  ['tinta-suave', 'arena', 9.53, TEXTO, 'texto secundario sobre la página'],
  ['tinta-suave', 'cafe-bruma', 9.53, TEXTO, 'chip neutro'],
  ['apagado', 'blanco', 6.37, TEXTO, 'ayudas y etiquetas'],
  ['apagado', 'arena', 5.93, TEXTO, 'ayudas sobre la página'],
  ['apagado', 'cafe-bruma', 5.93, TEXTO, 'texto deshabilitado'],
  ['borde-control', 'blanco', 3.42, NO_TEXTO, 'borde de campo sobre tarjeta'],
  ['borde-control', 'arena', 3.19, NO_TEXTO, 'borde de campo sobre la página'],
  ['borde', 'blanco', 1.27, DECORATIVO, 'solo decorativo: no delimita un control'],
  // Actividades
  ['blanco', 'azul', 6.94, TEXTO, 'texto sobre azul (mar)'],
  ['azul', 'azul-claro', 5.48, TEXTO, 'chip de mar'],
  ['tinta', 'coral', 4.13, TEXTO_GRANDE, 'texto grande sobre coral (24 px o más)'],
  ['blanco', 'coral', 4.18, TEXTO_GRANDE, 'texto grande sobre coral (24 px o más)'],
  ['coral-texto', 'coral-claro', 5.72, TEXTO, 'chip de ciudad'],
  ['coral-texto', 'blanco', 8.66, TEXTO, 'texto de la familia coral sobre blanco'],
  ['blanco', 'verde', 11.3, TEXTO, 'texto sobre verde (outside)'],
  ['verde', 'verde-claro', 10.23, TEXTO, 'chip de outside'],
  ['blanco', 'verde-medio', 6.21, TEXTO, 'verde-medio con texto blanco'],
  // Estados: texto o icono sobre su fondo
  ['exito', 'exito-fondo', 6.84, TEXTO, 'éxito'],
  ['error', 'error-fondo', 5.82, TEXTO, 'error sobre su fondo'],
  ['error', 'blanco', 6.67, TEXTO, 'error sobre blanco'],
  ['blanco', 'error', 6.67, TEXTO, 'botón destructivo'],
  ['aviso', 'aviso-fondo', 7.39, TEXTO, 'aviso (el fondo es cafe-claro)'],
  ['info', 'info-fondo', 9.17, TEXTO, 'información (el fondo es azul-claro)'],
  // Enfoque
  ['ring', 'blanco', 6.94, NO_TEXTO, 'anillo de foco sobre tarjeta'],
  ['ring', 'arena', 6.46, NO_TEXTO, 'anillo de foco sobre la página'],
];

for (const [primero, fondo, declarada, minimo, nota] of PARES) {
  test(`${primero} sobre ${fondo} (${nota})`, () => {
    const medida = razon(color(primero), color(fondo));
    assert.ok(
      Math.abs(medida - declarada) <= 0.02,
      `design.md dice ${declarada}:1 y los tokens dan ${medida.toFixed(2)}:1 (${color(primero)} sobre ${color(fondo)})`,
    );
    assert.ok(
      medida >= minimo,
      `${medida.toFixed(2)}:1 queda por debajo del mínimo de ${minimo}:1 (${color(primero)} sobre ${color(fondo)})`,
    );
  });
}

test('los pares prohibidos siguen siendo prohibidos: blanco sobre coral y coral sobre blanco no llegan a 4,5:1', () => {
  assert.ok(razon(color('blanco'), color('coral')) < TEXTO);
  assert.ok(razon(color('coral'), color('blanco')) < TEXTO);
  assert.ok(razon(color('cafe'), color('coral')) < NO_TEXTO);
});

test('el borde decorativo no delimita un control, y los rellenos suaves no distinguen un estado por sí solos', () => {
  assert.ok(razon(color('borde'), color('blanco')) < NO_TEXTO);
  assert.ok(razon(color('cafe-claro'), color('blanco')) < NO_TEXTO);
  assert.ok(razon(color('cafe-bruma'), color('blanco')) < NO_TEXTO);
});

test('la superficie de lectura es blanca y la página es arena, sin negro puro', () => {
  assert.equal(resolverToken(css, '--superficie'), '#ffffff');
  assert.equal(resolverToken(css, '--background'), '#fcf6ed');
  assert.equal(resolverToken(css, '--foreground'), '#1f1a14');
  assert.notEqual(resolverToken(css, '--foreground'), '#000000');
});

test('los alias antiguos siguen apuntando al nombre de marca de design.md', () => {
  const alias = {
    '--accent': 'cafe',
    '--action': 'cafe',
    '--accent-deep': 'cafe-hondo',
    '--surface': 'cafe-bruma',
    '--muted': 'apagado',
    '--border': 'borde',
    '--border-strong': 'borde-control',
    '--exito': 'exito',
    '--error': 'error',
    '--aviso': 'aviso',
  };
  for (const [viejo, nombre] of Object.entries(alias)) {
    assert.equal(resolverToken(css, viejo), color(nombre), viejo);
  }
  assert.equal(resolverToken(css, '--action-foreground'), color('blanco'));
});
