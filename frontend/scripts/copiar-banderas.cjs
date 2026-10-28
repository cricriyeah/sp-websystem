/* eslint-disable @typescript-eslint/no-require-imports */
// Copia a public/flags/<ISO>.svg las banderas 3x2 de country-flag-icons de los países que lista
// el selector del teléfono (los de libphonenumber-js, los mismos de src/lib/paises-telefono.ts).
// Los SVG se commitean: el paquete queda como devDependency solo para este script.
//
//   npm run banderas
//
// Es idempotente: no reescribe lo que ya es idéntico. Imprime los países sin bandera en el
// paquete (el componente Bandera muestra un icono Globe para esos).
const fs = require('node:fs');
const path = require('node:path');
const { getCountries } = require('libphonenumber-js/min');

const raiz = path.resolve(__dirname, '..');
// require.resolve (y no armar la ruta a mano) para que el paquete cuente como usado en knip.
const origen = path.join(path.dirname(require.resolve('country-flag-icons/package.json')), '3x2');
const destino = path.join(raiz, 'public', 'flags');

if (!fs.existsSync(origen)) {
  console.error('Falta ' + origen + '. El paquete country-flag-icons no trae 3x2.');
  process.exit(1);
}
fs.mkdirSync(destino, { recursive: true });

let copiadas = 0;
let iguales = 0;
const faltan = [];
for (const iso of getCountries()) {
  const archivo = path.join(origen, iso + '.svg');
  if (!fs.existsSync(archivo)) {
    faltan.push(iso);
    continue;
  }
  const contenido = fs.readFileSync(archivo);
  const salida = path.join(destino, iso + '.svg');
  if (fs.existsSync(salida) && fs.readFileSync(salida).equals(contenido)) {
    iguales += 1;
    continue;
  }
  fs.writeFileSync(salida, contenido);
  copiadas += 1;
}

console.log('Banderas: ' + copiadas + ' copiadas, ' + iguales + ' ya estaban, ' + faltan.length + ' sin bandera.');
if (faltan.length) console.log('Sin bandera en el paquete (el selector usa un icono): ' + faltan.join(', '));
