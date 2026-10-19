/* eslint-disable @typescript-eslint/no-require-imports */
// `empresas.ts` hace `import 'server-only'`: se stubea igual que en content-sedes-cuerpo.test.cjs.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');

const outDir = process.env.EMPRESAS_TEST_OUT;
const stubDir = path.join(outDir, 'node_modules', 'server-only');
fs.mkdirSync(stubDir, { recursive: true });
fs.writeFileSync(path.join(stubDir, 'package.json'), JSON.stringify({ name: 'server-only', main: 'index.js' }));
fs.writeFileSync(path.join(stubDir, 'index.js'), 'module.exports = {};');

const { EMPRESAS, getEmpresa } = require(path.join(outDir, 'content/empresas.js'));

test('las cuatro empresas, cada una con su sede', () => {
  assert.deepEqual(
    EMPRESAS.map((e) => [e.slug, e.sede]),
    [['sal-y-sol', 'la-paz'], ['transporte-la-paz', 'la-paz'], ['la-ventana-travel', 'la-ventana'], ['piratas-adventures', 'puerto-chale']],
  );
});

test('descripción en es y en para cada empresa', () => {
  for (const e of EMPRESAS) {
    assert.ok(e.descripcion.es.trim(), `${e.slug}: falta es`);
    assert.ok(e.descripcion.en.trim(), `${e.slug}: falta en`);
  }
});

test('las reseñas arrancan sin confirmar', () => {
  for (const e of EMPRESAS) for (const r of e.resenas) assert.equal(r.confirmada, false, e.slug);
});

test('Sal y Sol no lleva sitio externo; las otras tres sí, confirmado', () => {
  assert.equal(getEmpresa('sal-y-sol').web, undefined);
  assert.equal(getEmpresa('sal-y-sol').webConfirmada, false);
  for (const slug of ['transporte-la-paz', 'la-ventana-travel', 'piratas-adventures']) {
    assert.ok(getEmpresa(slug).web);
    assert.equal(getEmpresa(slug).webConfirmada, true);
  }
});

test('el WhatsApp de relleno de Piratas no entra', () => {
  assert.equal(getEmpresa('piratas-adventures').contacto, undefined);
});
