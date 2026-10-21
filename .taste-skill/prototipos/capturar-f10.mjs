// Capturas de página completa con Chrome sin interfaz vía DevTools Protocol.
// Uso: node capturar.mjs <salida-dir> <ancho> <alto> <movil 0|1> <ruta>...
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';

const [, , salida, ancho, alto, movil, ...rutas] = process.argv;
mkdirSync(salida, { recursive: true });
const PUERTO = 9333 + Math.floor(Math.random() * 500);
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', `--remote-debugging-port=${PUERTO}`, '--no-first-run', '--hide-scrollbars',
  `--user-data-dir=${salida}/perfil-${PUERTO}`, 'about:blank',
], { stdio: 'ignore' });

const espera = (ms) => new Promise((r) => setTimeout(r, ms));
let ws;
for (let i = 0; i < 40; i++) {
  try {
    const lista = await (await fetch(`http://127.0.0.1:${PUERTO}/json`)).json();
    const pagina = lista.find((t) => t.type === 'page');
    if (pagina) { ws = new WebSocket(pagina.webSocketDebuggerUrl); break; }
  } catch {}
  await espera(250);
}
if (ws.readyState !== 1) await new Promise((r) => ws.addEventListener('open', r));
let id = 0;
const pendientes = new Map();
ws.addEventListener('message', (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pendientes.has(m.id)) { pendientes.get(m.id)(m); pendientes.delete(m.id); }
});
const cdp = (method, params = {}) => new Promise((r) => { const n = ++id; pendientes.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });

await cdp('Page.enable');
await cdp('Runtime.enable');
await cdp('Emulation.setDeviceMetricsOverride', { width: +ancho, height: +alto, deviceScaleFactor: 1, mobile: movil === '1' });
if (movil === '1') await cdp('Emulation.setUserAgentOverride', { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
await cdp('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });

for (const ruta of rutas) {
  await cdp('Page.navigate', { url: 'http://localhost:3000' + ruta });
  await espera(4000);
  await cdp('Runtime.evaluate', { expression: "document.head.append(Object.assign(document.createElement('style'),{textContent:'.rev,.rev-foto,.rev-visor{animation:none!important}'}))" });
  // Recorre la página para que carguen las imágenes diferidas y entren las animaciones.
  const { result } = await cdp('Runtime.evaluate', { expression: 'document.documentElement.scrollHeight', returnByValue: true });
  const total = result.result.value;
  for (let y = 0; y < total; y += +alto / 2) {
    await cdp('Runtime.evaluate', { expression: `window.scrollTo(0, ${y})` });
    await espera(250);
  }
  await cdp('Runtime.evaluate', { expression: 'window.scrollTo(0, 0)' });
  await espera(1200);
  const nombre = ruta.replace(/[/?=&]+/g, "_").replace(/^_/, "") || "raiz";
  const tramo = Math.max(+alto * 1.6, 1300);
  for (let y = 0, n = 0; y < total; y += tramo, n++) {
    const h = Math.min(tramo, total - y);
    const r = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y, width: +ancho, height: h, scale: 1 } });
    writeFileSync(`${salida}/${nombre}-${ancho}-${String(n).padStart(2, "0")}.png`, Buffer.from(r.result.data, "base64"));
  }
  console.log("ok", nombre, ancho, "alto", total);
}
ws.close();
chrome.kill();
process.exit(0);
