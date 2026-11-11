/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const m = require(path.join(process.env.MEDICION_TEST_OUT, 'lib/medicion.js'));

test('Meta recibe id, nombre, valor redondeado y moneda', () => {
  assert.deepEqual(m.parametrosMeta({ id: 'pesca-deportiva', nombre: 'Pesca', valor: 13096.4, moneda: 'MXN' }), {
    content_ids: ['pesca-deportiva'], content_type: 'product', content_name: 'Pesca', value: 13096.4, currency: 'MXN',
  });
  assert.deepEqual(m.parametrosMeta({}), {});
  assert.deepEqual(m.parametrosMeta({ valor: NaN }), {});
});

test('Google: la compra lleva transaction_id; los demás eventos no', () => {
  const compra = m.parametrosGoogle('Purchase', { id: 'seafari-5', valor: 100, moneda: 'USD', eventoId: 'reserva-12' });
  assert.equal(compra.transaction_id, 'reserva-12');
  assert.deepEqual(compra.items, [{ item_id: 'seafari-5' }]);
  assert.equal(m.parametrosGoogle('ViewContent', { eventoId: 'x' }).transaction_id, undefined);
});

test('reconoce los enlaces de WhatsApp', () => {
  for (const href of ['https://wa.me/5216121985367?text=hola', 'https://api.whatsapp.com/send?phone=1', 'https://www.whatsapp.com/send?phone=1']) {
    assert.equal(m.esEnlaceWhatsapp(href), true, href);
  }
  for (const href of ['/es/sede/la-paz', 'https://www.instagram.com/sunbajaexperiences', '']) {
    assert.equal(m.esEnlaceWhatsapp(href), false, href);
  }
});
