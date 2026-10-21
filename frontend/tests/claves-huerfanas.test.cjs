/* eslint-disable @typescript-eslint/no-require-imports */
// Ninguna clave del diccionario queda sin leer (F10): cada nombre de clave tiene que aparecer en el código
// de `src/` (como propiedad, como texto o como nombre de un tipo). Es una guardia por nombre, no por ruta: no
// atrapa una clave que comparte nombre con otra que sí se lee, pero sí la que ya nadie nombra. Las claves que
// se arman con una cadena calculada (nunca nombradas en el código) van en `DINAMICAS`, cada una con su motivo.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const raiz = path.join(__dirname, '..', 'src');

/** Claves que el código no nombra porque las elige por cálculo. Motivo en cada una. */
const DINAMICAS = new Set([
  // `dict.nav[claveNav]`: la clave es el id de una sección de la sede (ver `enlacesDeSede`).
  'galeria', 'temporadas', 'opiniones', 'preguntas',
]);

function archivos(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const ruta = path.join(dir, e.name);
    if (e.isDirectory()) return archivos(ruta);
    return /\.(ts|tsx)$/.test(e.name) ? [ruta] : [];
  });
}

function nombres(valor, acumulado = new Set()) {
  if (Array.isArray(valor)) valor.forEach((v) => nombres(v, acumulado));
  else if (valor && typeof valor === 'object') {
    for (const [k, v] of Object.entries(valor)) {
      acumulado.add(k);
      nombres(v, acumulado);
    }
  }
  return acumulado;
}

test('toda clave del diccionario se nombra en el código', () => {
  const codigo = archivos(raiz).map((a) => fs.readFileSync(a, 'utf8')).join('\n');
  const es = JSON.parse(fs.readFileSync(path.join(raiz, 'app/[lang]/dictionaries/es.json'), 'utf8'));
  const huerfanas = [...nombres(es)].filter((k) => !DINAMICAS.has(k) && !new RegExp(`\\b${k}\\b`).test(codigo));
  assert.deepEqual(huerfanas, [], `Claves sin leer: ${huerfanas.join(', ')}`);
});
