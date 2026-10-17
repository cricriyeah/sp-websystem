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
