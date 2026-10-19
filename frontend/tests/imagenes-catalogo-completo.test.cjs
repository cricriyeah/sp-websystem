/* eslint-disable @typescript-eslint/no-require-imports */
// Completitud de las fotos del catálogo (Task 9.0, paso 1f). Script aparte con `fs`:
// `npm run test:fotos`. NO entra al runner ni a `verificar` hasta la Task 9.7, porque las
// fotos de La Ventana, Puerto Chale y DLS son una dependencia del dueño.
//
// Las claves son las de `backend/apps/*/management/commands/seed_catalogo_real.py` (servicios
// y paquetes) más la pesca de Sal y Sol. Al sumar un servicio al catálogo, se suma aquí.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const raiz = path.resolve(__dirname, '..');
const fuente = fs.readFileSync(path.join(raiz, 'src/content/imagenes-catalogo.ts'), 'utf8');

const ESPERADAS = [
  'servicio:sal-y-sol/pesca-deportiva',
  'servicio:la-ventana-travel/pesca-con-mosca',
  'servicio:la-ventana-travel/avistamiento-ballenas-orcas',
  'servicio:la-ventana-travel/hospedaje-la-ventana',
  'servicio:la-ventana-travel/traslado-aeropuerto-la-ventana',
  'servicio:piratas-adventures/safari-marino',
  'servicio:piratas-adventures/avistamiento-ballenas',
  'servicio:piratas-adventures/pesca-deportiva',
  'paquete:paquete-5-noches',
  'paquete:paquete-7-noches',
];

// Cada entrada del mapa: 'clave': { src: '...', alt: { es: '...', en: '...' } }
const entradas = [...fuente.matchAll(/'((?:servicio|paquete):[^']+)':\s*\{\s*src:\s*'([^']+)',\s*alt:\s*\{\s*es:\s*'([^']*)',\s*en:\s*'([^']*)'/g)]
  .map(([, clave, src, es, en]) => ({ clave, src, es, en }));

test('todo servicio y paquete del catálogo tiene foto', () => {
  const claves = new Set(entradas.map((e) => e.clave));
  const faltan = ESPERADAS.filter((clave) => !claves.has(clave));
  assert.deepEqual(faltan, [], `Faltan fotos: ${faltan.join(', ')}`);
});

test('ninguna foto es de relleno', () => {
  const relleno = [...fuente.matchAll(/'((?:servicio|paquete):[^']+)':\s*\{([\s\S]*?)\n  \},/g)]
    .filter(([, , cuerpo]) => cuerpo.includes('relleno: true'))
    .map(([, clave]) => clave);
  assert.deepEqual(relleno, [], `Fotos de relleno: ${relleno.join(', ')}`);
});

test('cada foto existe en public/, pesa ≤ 200 KB y tiene alt en es y en', () => {
  for (const { clave, src, es, en } of entradas) {
    const archivo = path.join(raiz, 'public', src);
    assert.ok(fs.existsSync(archivo), `${clave}: no existe ${src}`);
    assert.ok(fs.statSync(archivo).size <= 200 * 1024, `${clave}: ${src} pesa más de 200 KB`);
    assert.ok(es.trim() && en.trim(), `${clave}: falta el alt en es o en`);
  }
});
