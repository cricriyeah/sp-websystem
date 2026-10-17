/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require('node:fs');
const path = require('node:path');

const REGLAS = {
  'boton-crudo': /<button\b/g,
  'input-crudo': /<(input|select|textarea)\b/g,
  'img-cruda': /<img\b/g,
  'paleta-cruda':
    /\b(?:bg|text|border|ring|from|to|via|fill|stroke|divide|outline)-(?:red|green|blue|amber|sky|gray|slate|zinc|neutral|stone|yellow|orange|emerald|teal|indigo|violet|purple|pink|rose|lime|cyan|fuchsia)-\d{2,3}\b/g,
  // Un hex real tiene 3, 4, 6 u 8 dígitos. Cuenta los que van entre comillas ("#fff", '#281ab5'),
  // que son casi todos los reales; excluye solo anclas (href="#add"), entidades (&#xA9;) y url(#grad).
  'color-literal': /(?<!\w|[&\/#]|href=["'])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b(?![-\w])|\brgba?\(/g,
  // Dentro de ui/: cualquier import que no sea paquete, relativo, '@/components/ui/' ni '@/lib/'.
  'capas-ui': /from\s+['"]@\/(?!components\/ui\/|lib\/)[^'"]*['"]/g, // los imports relativos que escapan de ui/ los cuenta relativosFuera()
  // Con LazyMotion strict, `motion.*` falla en desarrollo y en producción pierde el ahorro: solo `m.*`.
  'motion-completo': /\bmotion\.(?:div|span|button|a|ul|li|section|p|h[1-6]|svg|path|img|nav|header|footer|article|form|input|label)\b/g,
  // Reglas de la marca nueva (taste): cuentan hoy y llegan a 0 al cierre de F7.
  'texto-chico-en-campo': /<(?:input|select|textarea)\b(?:=>|[^>])*?\btext-(?:xs|sm)\b/g, // límite: no ve tamaños que vienen de un className externo o de una constante
  'mayusculas-crudas': /\b(?:uppercase|tracking-wider|tracking-widest)\b/g,
  'radio-crudo': /\brounded(?:-[trblse]{1,2})?-(?:md|lg|xl|2xl|3xl)\b/g, // incluye rounded-t-xl, rounded-b-lg…
  'sombra-cruda': /\bshadow-(?:\[|xs\b|sm\b|md\b|lg\b|xl\b|2xl\b)/g,
  'surface-deep': /\bbg-surface-deep\b/g,
  // Los 77 usos de bg-surface se clasifican en la Task 2.4; cuenta hoy y baja hasta lo que quede como banda de sección.
  'bg-surface-uso': /\bbg-surface(?![-\w])/g,
};

// Exentos POR REGLA y con motivo: valores que una API externa pide en concreto, no como var().
// Un archivo exento de una regla sigue midiéndose en todas las demás (p. ej. lang-switch.tsx
// sigue contando sus <button> y sus motion.*). `globals.css` no figura: el escáner solo lee .ts/.tsx.
const EXENTOS = {
  'src/app/[lang]/opengraph-image.tsx': { reglas: ['color-literal'], motivo: 'ImageResponse no lee CSS' },
  'src/components/lang-switch.tsx': { reglas: ['color-literal'], motivo: 'SVG de banderas con colores propios' },
  'src/app/[lang]/error.tsx': { reglas: ['boton-crudo'], motivo: 'sin Button hasta la Task 3.3; la migracion de F4 lo quita' },
  'src/app/global-error.tsx': { reglas: ['boton-crudo'], motivo: 'sin Button hasta la Task 3.3; la migracion de F4 lo quita' },
  'src/components/checkout/ayuda-flotante.tsx': { reglas: ['color-literal'], motivo: 'color de marca de WhatsApp' },
  'src/components/error-block.tsx': { reglas: ['color-literal'], motivo: 'color de marca de WhatsApp en el boton de ayuda' },
  'src/components/pedido/reserva-plegable.tsx': { reglas: ['color-literal'], motivo: 'color de marca de WhatsApp' },
  'src/lib/tokens-pago.ts': { reglas: ['color-literal'], motivo: 'única fuente de lo que Stripe Elements pide en concreto' },
};
// Las primitivas son el único lugar donde vive el HTML crudo de estos controles.
const SOLO_FUERA_DE_UI = ['boton-crudo', 'input-crudo'];

function sinComentarios(texto) {
  return texto.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
}

function contar(texto, regla) {
  return (texto.match(REGLAS[regla]) ?? []).length;
}

// Imports relativos dentro de ui/ que resuelven fuera de ui/ y lib/ (el alias @/ ya lo ve la regex).
function relativosFuera(texto, rel) {
  let n = 0;
  for (const m of texto.matchAll(/from\s+['"](\.{1,2}\/[^'"]*)['"]/g)) {
    const destino = path.posix.join(path.posix.dirname(rel), m[1]);
    if (!destino.startsWith('src/components/ui/') && !destino.startsWith('src/lib/')) n++;
  }
  return n;
}

function* archivos(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) yield* archivos(p);
    else if (/\.(tsx|ts)$/.test(e.name)) yield p;
  }
}

function medir(raiz) {
  const resultado = {};
  for (const abs of archivos(path.join(raiz, 'src'))) {
    const rel = path.relative(raiz, abs).split(path.sep).join('/');
    const enUi = rel.startsWith('src/components/ui/');
    const texto = sinComentarios(fs.readFileSync(abs, 'utf8'));
    for (const regla of Object.keys(REGLAS)) {
      if (EXENTOS[rel]?.reglas.includes(regla)) continue; // exento de esta regla, no del archivo entero
      if (SOLO_FUERA_DE_UI.includes(regla) && enUi) continue;
      if (regla === 'capas-ui' && !enUi) continue;
      const n = contar(texto, regla) + (regla === 'capas-ui' ? relativosFuera(texto, rel) : 0);
      if (n > 0) (resultado[regla] ??= {})[rel] = n;
    }
  }
  return resultado;
}

// Trinquete por TOTAL de regla: mover código de un archivo a otro (extracciones de F1, F4 y F5)
// no cambia el total, así que no falla. El detalle por archivo de la línea base es solo informe.
function suben(base, actual) {
  const total = (o, r) => Object.values(o[r] ?? {}).reduce((a, n) => a + n, 0);
  return [...new Set([...Object.keys(base), ...Object.keys(actual)])]
    .map((r) => [r, total(base, r), total(actual, r)])
    .filter(([, antes, ahora]) => ahora > antes);
}

module.exports = { contar, sinComentarios, medir, relativosFuera, suben, EXENTOS };

if (require.main === module) {
  const raiz = path.resolve(__dirname, '..');
  const baselinePath = path.join(__dirname, 'guardia-estilos.baseline.json');
  const actual = medir(raiz);
  if (process.argv.includes('--escribir')) {
    fs.writeFileSync(baselinePath, JSON.stringify(actual, null, 2) + '\n');
    console.log('Línea base escrita.');
    process.exit(0);
  }
  const base = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const subidas = suben(base, actual);
  subidas.forEach(([r, a, n]) => console.error(`SUBE ${r}: ${a} -> ${n}`));
  const total = (o) => Object.values(o).reduce((a, p) => a + Object.values(p).reduce((x, y) => x + y, 0), 0);
  console.log(`Infracciones: ${total(actual)} (línea base ${total(base)})`);
  process.exit(subidas.length > 0 ? 1 : 0);
}
