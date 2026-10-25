/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const m = require(path.join(process.env.MARCA_CONFIRMACION_TEST_OUT, 'lib/marca-confirmacion.js'));

test('sin la marca no se pide la confirmación', () => {
  assert.equal(m.tieneMarcaDeConfirmacion(''), false);
  assert.equal(m.tieneMarcaDeConfirmacion('?servicio=pesca&sede=la-paz'), false);
});

test('solo confirmacion=1 la pide', () => {
  assert.equal(m.tieneMarcaDeConfirmacion('?confirmacion=1'), true);
  assert.equal(m.tieneMarcaDeConfirmacion('servicio=pesca&confirmacion=1'), true);
  assert.equal(m.tieneMarcaDeConfirmacion('?confirmacion=0'), false);
  assert.equal(m.tieneMarcaDeConfirmacion('?confirmacion='), false);
});

test('la marca se suma a la ruta sin perder lo que ya traía', () => {
  assert.equal(m.conMarcaDeConfirmacion('/es/reservar'), '/es/reservar?confirmacion=1');
  assert.equal(
    m.conMarcaDeConfirmacion('/es/reservar?paquete=ballenas&sede=la-ventana'),
    '/es/reservar?paquete=ballenas&sede=la-ventana&confirmacion=1',
  );
});

test('poner la marca dos veces no la repite', () => {
  assert.equal(m.conMarcaDeConfirmacion('/es/traslados?confirmacion=1'), '/es/traslados?confirmacion=1');
});

test('conserva el ancla', () => {
  assert.equal(m.conMarcaDeConfirmacion('/es/reservar?paso=pago#resumen'), '/es/reservar?paso=pago&confirmacion=1#resumen');
});
