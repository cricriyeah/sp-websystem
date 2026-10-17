/* eslint-disable @typescript-eslint/no-require-imports */
// Resuelve un token de src/app/globals.css a un valor concreto (hex o px).
// Lee los bloques de nivel superior `:root { … }` y `@theme … { … }`; no mira los
// `:root` anidados en @media. No es un *.test.cjs: ningún runner lo ejecuta como prueba.
const fs = require('node:fs');
const path = require('node:path');

function leerGlobalsCss() {
  return fs.readFileSync(path.join(__dirname, '../../src/app/globals.css'), 'utf8');
}

function sinComentarios(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

// Declaraciones `--x: valor;` de los bloques de nivel superior que interesan. La primera gana.
function declaraciones(css) {
  const texto = sinComentarios(css);
  const mapa = new Map();
  let profundidad = 0;
  let inicioEncabezado = 0;
  let inicioCuerpo = -1;
  let encabezado = '';
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (c === '{') {
      if (profundidad === 0) {
        encabezado = texto.slice(inicioEncabezado, i).trim();
        inicioCuerpo = i + 1;
      }
      profundidad++;
    } else if (c === '}') {
      profundidad--;
      if (profundidad === 0) {
        if (encabezado === ':root' || /^@theme\b/.test(encabezado)) {
          const cuerpo = texto.slice(inicioCuerpo, i);
          for (const m of cuerpo.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
            if (!mapa.has(m[1])) mapa.set(m[1], m[2].trim());
          }
        }
        inicioEncabezado = i + 1;
      }
    } else if (c === ';' && profundidad === 0) {
      inicioEncabezado = i + 1; // @import … ;
    }
  }
  return mapa;
}

function numero(n) {
  return String(Math.round(n * 1000) / 1000);
}

function resolverToken(css, nombre) {
  const mapa = declaraciones(css);
  const visitados = [];
  let actual = nombre;
  for (;;) {
    if (visitados.includes(actual)) throw new Error(`Ciclo de var() en ${nombre}: ${[...visitados, actual].join(' -> ')}`);
    visitados.push(actual);
    if (!mapa.has(actual)) throw new Error(`Token ${actual} no declarado (resolviendo ${nombre})`);
    const valor = mapa.get(actual);
    const ref = /^var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)$/.exec(valor);
    if (ref) {
      actual = ref[1];
      continue;
    }
    const rem = /^(-?\d*\.?\d+)rem$/.exec(valor);
    if (rem) return `${numero(Number(rem[1]) * 16)}px`;
    const px = /^(-?\d*\.?\d+)px$/.exec(valor);
    if (px) return `${numero(Number(px[1]))}px`;
    if (/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(valor)) return valor.toLowerCase();
    throw new Error(`${nombre} no termina en hex ni px: "${valor}" (en ${actual})`);
  }
}

module.exports = { resolverToken, declaraciones, leerGlobalsCss };
