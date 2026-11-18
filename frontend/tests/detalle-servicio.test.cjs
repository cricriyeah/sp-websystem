/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { condicionesDeCompra, enlaceAlMapa, etiquetasDeReglas } = require(path.join(process.env.DETALLE_SERVICIO_TEST_OUT, 'lib/detalle-servicio.js'));

const TEXTOS = { confirmas: 'confirmas', clima: 'clima', fecha48: '48', fecha30: '30', fecha24: '24' };

test('un día de mar: confirmas, mal clima y 48 h', () => {
  assert.deepEqual(condicionesDeCompra('mar', true, TEXTOS), ['confirmas', 'clima', '48']);
});

test('cada compra dice su plazo; el mal clima solo donde se sale al mar', () => {
  assert.deepEqual(condicionesDeCompra('paquete-hotel', true, TEXTOS), ['confirmas', 'clima', '30']);
  assert.deepEqual(condicionesDeCompra('paquete-hotel', false, TEXTOS), ['confirmas', '30']);
  assert.deepEqual(condicionesDeCompra('traslado', false, TEXTOS), ['confirmas', '24']);
  assert.deepEqual(condicionesDeCompra('otro', false, TEXTOS), ['confirmas']);
});

test('el mapa busca el punto con su lugar, sin repetirlo', () => {
  assert.equal(
    enlaceAlMapa('Marina La Costa', 'La Paz'),
    'https://www.google.com/maps/search/?api=1&query=Marina%20La%20Costa%2C%20La%20Paz%2C%20Baja%20California%20Sur',
  );
  assert.equal(enlaceAlMapa('Muelle de La Paz', 'La Paz'), 'https://www.google.com/maps/search/?api=1&query=Muelle%20de%20La%20Paz');
  assert.equal(enlaceAlMapa('   '), null);
});

const REGLAS = { quedasPesca: 'quedas', liberacion: 'libera', limpieza: 'limpia', ninos: 'ninos', recogida: 'recoge', llegas: 'llegas' };

test('solo se dicen las reglas confirmadas', () => {
  assert.deepEqual(etiquetasDeReglas({}, REGLAS), []);
  assert.deepEqual(etiquetasDeReglas({ quedasPesca: true, limpieza: false, ninos: true, recogida: false }, REGLAS), ['quedas', 'ninos', 'llegas']);
  assert.deepEqual(etiquetasDeReglas({ quedasPesca: false, recogida: true }, REGLAS), ['libera', 'recoge']);
});
