/* eslint-disable @typescript-eslint/no-require-imports */
// Métrica oficial de peso por ruta (Next 16 ya no imprime «First Load JS»).
// Uso: npm run build && node scripts/medir-peso.cjs  (levanta `next start` en :3000 si no hay uno)
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const { spawn } = require('node:child_process');

const RUTAS = ['/es', '/es/sede/la-paz', '/es/servicio/sal-y-sol/pesca-deportiva', '/es/reservar', '/es/traslados'];
const BASE = process.env.MEDIR_BASE ?? 'http://localhost:3000';
const raiz = path.resolve(__dirname, '..');

async function responde() {
  try { await fetch(BASE + '/es'); return true; } catch { return false; }
}

async function esperar() {
  for (let i = 0; i < 60; i++) {
    if (await responde()) return;
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error('next start no respondió en 60 s');
}

function chunksDe(html) {
  const out = new Set();
  for (const m of html.matchAll(/<script[^>]*\ssrc="(\/_next\/static\/[^"]+)"/g)) out.add(m[1]);
  for (const m of html.matchAll(/<link[^>]*rel="preload"[^>]*as="script"[^>]*href="(\/_next\/static\/[^"]+)"/g)) out.add(m[1]);
  for (const m of html.matchAll(/<link[^>]*href="(\/_next\/static\/[^"]+)"[^>]*as="script"/g)) out.add(m[1]);
  return [...out].map((u) => decodeURIComponent(u.split('?')[0]));
}

function pesar(url) {
  const archivo = path.join(raiz, '.next', url.replace(/^\/_next\//, ''));
  if (!fs.existsSync(archivo)) return { crudo: 0, gzip: 0, falta: true };
  const buf = fs.readFileSync(archivo);
  return { crudo: buf.length, gzip: zlib.gzipSync(buf).length };
}

(async () => {
  let servidor = null;
  if (!(await responde())) {
    servidor = spawn(process.execPath, [path.join(raiz, 'node_modules', 'next', 'dist', 'bin', 'next'), 'start', '-p', '3000'], { cwd: raiz, stdio: 'ignore' });
    await esperar();
  }
  const kb = (n) => (n / 1024).toFixed(1);
  console.log('| Ruta | Chunks JS | Crudo (KB) | Gzip (KB) |\n|---|---|---|---|');
  for (const ruta of RUTAS) {
    const res = await fetch(BASE + ruta);
    const html = await res.text();
    const chunks = chunksDe(html);
    const t = chunks.map(pesar).reduce((a, p) => ({ crudo: a.crudo + p.crudo, gzip: a.gzip + p.gzip }), { crudo: 0, gzip: 0 });
    console.log(`| ${ruta} (HTTP ${res.status}) | ${chunks.length} | ${kb(t.crudo)} | ${kb(t.gzip)} |`);
  }
  if (servidor) servidor.kill();
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
