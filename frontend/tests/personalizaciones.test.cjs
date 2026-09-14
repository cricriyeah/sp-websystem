/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const h = require(path.join(process.env.PERSONALIZACIONES_TEST_OUT, 'personalizaciones.js'));
const licencia = {
  id: 7,
  nombre: 'Licencia',
  tipo_interaccion: 'check',
  opciones_seleccion: [],
  aviso_reforzado: true,
  obligatorio: false,
  preseleccionado: true,
  cobrar_por_persona: true,
  cantidad_editable: true,
  precio: '450.00',
  precio_usd: null,
};

test('recomendada removible y cantidad efectiva', () => {
  assert.deepEqual(h.seleccionInicial([licencia]), [{ id: 7, cantidad: 1 }]);
  assert.equal(h.totalPersonalizaciones([licencia], [], 5, 'MXN'), 0);
  assert.equal(h.totalPersonalizaciones([licencia], [{ id: 7, cantidad: 2 }], 5, 'MXN'), 900);
  assert.equal(h.totalPersonalizaciones([licencia], [{ id: 7 }], 5, 'USD'), null);
});

test('input número cero, vacío y no finito', () => {
  const p = { ...licencia, tipo_interaccion: 'input_numero', obligatorio: true };
  assert.deepEqual(h.erroresPersonalizaciones([p], [{ id: 7, respuesta: '0' }]), {});
  assert.deepEqual(h.erroresPersonalizaciones([p], []), { 7: 'required' });
  assert.deepEqual(h.erroresPersonalizaciones([p], [{ id: 7, respuesta: 'Infinity' }]), { 7: 'number' });
});
