/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const { contar, sinComentarios, relativosFuera, suben, pasanUmbral } = require('../scripts/guardia-estilos.cjs');

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
  assert.equal(contar('<h1 className="texto-display">', 'titular-sin-escala'), 0);
  assert.equal(contar('<h1 className="texto-gigante">', 'titular-sin-escala'), 0);
  assert.equal(contar('<h2 className="texto-grande">', 'titular-sin-escala'), 0);
  assert.equal(contar('<h2 id="x" className="mt-2 texto-seccion text-foreground">', 'titular-sin-escala'), 0);
  assert.equal(contar('<h2 className="font-sans texto-pequeno">', 'titular-sin-escala'), 0);
  assert.equal(contar('<h1 className="text-5xl">', 'titular-sin-escala'), 1);
  assert.equal(contar('<h2>', 'titular-sin-escala'), 1);
  assert.equal(contar('<h1\n  className="text-3xl"\n>', 'titular-sin-escala'), 1); // etiqueta en varios renglones
  assert.equal(contar('<h1\n  className="texto-pagina"\n>', 'titular-sin-escala'), 0);
  assert.equal(contar('<h3 className="text-xl">', 'titular-sin-escala'), 0); // solo h1 y h2
  assert.equal(contar('<header className="x">', 'titular-sin-escala'), 0);
  assert.equal(contar('className="bg-surface p-4"', 'bg-surface-uso'), 1);
  assert.equal(contar('className="bg-surface-deep"', 'bg-surface-uso'), 0); // surface-deep tiene su regla
  assert.equal(contar('className="bg-superficie"', 'bg-surface-uso'), 0);
});

test('F7b: letra fuera de escala, 12 px, raya larga y objetivo chico', () => {
  assert.equal(contar('className="text-[13px]"', 'letra-fuera-de-escala'), 1);
  assert.equal(contar('className="text-[15px] text-[12.8px]"', 'letra-fuera-de-escala'), 2);
  assert.equal(contar('className="text-[14px] text-[16px] text-[12px]"', 'letra-fuera-de-escala'), 0);
  assert.equal(contar('className="texto-pequeno"', 'letra-fuera-de-escala'), 0);
  assert.equal(contar('className="text-xs text-[12px]"', 'letra-12'), 2);
  assert.equal(contar('className="text-sm"', 'letra-12'), 0);
  assert.equal(contar('const a = "uno — dos";', 'guion-largo'), 1);
  assert.equal(contar('const a = "uno, dos";', 'guion-largo'), 0);
  assert.equal(contar('<Button className="h-8 px-3">', 'objetivo-chico'), 1);
  assert.equal(contar('<Link href="/x" className="size-6">', 'objetivo-chico'), 1);
  assert.equal(contar('<Button className="h-11">', 'objetivo-chico'), 0);
  assert.equal(contar('<div className="h-8">', 'objetivo-chico'), 0);
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

test('umbral duro: cualquier infracción de las reglas de la base falla; las de marca nueva no', () => {
  assert.deepEqual(pasanUmbral({ 'boton-crudo': { 'a.tsx': 2 } }), [['boton-crudo', 2]]);
  assert.deepEqual(pasanUmbral({ 'radio-crudo': { 'a.tsx': 9 }, 'bg-surface-uso': { 'a.tsx': 9 } }), [['radio-crudo', 9]]); // la compuerta de marca (7.3) exige 0; bg-surface-uso puede quedar en bandas
  assert.deepEqual(pasanUmbral({}), []);
});
