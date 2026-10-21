// Prueba de interacción de F10.8 con Chrome sin interfaz: visor de la galería, preguntas y flechas de la fila.
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';

const [, , salida] = process.argv;
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
const ev = async (expression) => (await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result.result.value;
const tecla = async (key, code) => {
  await cdp('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: key === 'ArrowRight' ? 39 : 37 });
  await cdp('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: key === 'ArrowRight' ? 39 : 37 });
};

await cdp('Page.enable');
await cdp('Runtime.enable');
await cdp('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await cdp('Page.navigate', { url: 'http://localhost:3000/es/sede/la-paz' });
await espera(5000);
const resultados = {};

// Fila: las flechas aparecen solo si desborda; el carril avanza al pulsar «Siguiente».
resultados.flechas = await ev(`(async () => {
  const sig = document.querySelector('[aria-label="Siguiente"]');
  const carril = document.querySelector('[role="region"][tabindex="0"]');
  return { hayFlecha: !!sig, desborda: carril ? carril.scrollWidth - carril.clientWidth : null };
})()`);

// Preguntas: abrir una y comprobar aria-expanded y el panel.
resultados.preguntas = await ev(`(async () => {
  const boton = document.querySelector('#preguntas button[aria-expanded]');
  boton.scrollIntoView({ block: 'center' });
  boton.click();
  await new Promise((r) => setTimeout(r, 500));
  const panel = document.getElementById(boton.getAttribute('aria-controls'));
  return { expandido: boton.getAttribute('aria-expanded'), alto: panel ? panel.getBoundingClientRect().height : 0 };
})()`);

// Visor: abrir la primera foto, avanzar con el teclado, cerrar con Esc.
resultados.visorAbre = await ev(`(async () => {
  const foto = document.querySelector('#galeria button[aria-haspopup="dialog"]');
  foto.scrollIntoView({ block: 'center' });
  foto.click();
  await new Promise((r) => setTimeout(r, 600));
  const d = document.querySelector('dialog[open]');
  return d ? d.querySelector('p').textContent : null;
})()`);
await tecla('ArrowRight', 'ArrowRight');
await espera(500);
resultados.visorSiguiente = await ev(`document.querySelector('dialog[open] p')?.textContent ?? null`);
const captura = await cdp('Page.captureScreenshot', { format: 'png' });
writeFileSync(`${salida}/visor.png`, Buffer.from(captura.result.data, 'base64'));
await tecla('Escape', 'Escape');
await espera(400);
resultados.visorCerrado = await ev(`document.querySelector('dialog[open]') === null`);

console.log(JSON.stringify(resultados, null, 1));
ws.close();
chrome.kill();
