/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const m = require(path.join(process.env.IMAGENES_TEST_OUT, 'content/imagenes-catalogo.js'));

test('sin foto para la clave: null', () => {
  assert.equal(m.imagenDeCatalogo('servicio:nadie/nada', 'es'), null);
});

test('con foto: src y alt en el idioma pedido', () => {
  const es = m.imagenDeCatalogo('servicio:sal-y-sol/pesca-deportiva', 'es');
  const en = m.imagenDeCatalogo('servicio:sal-y-sol/pesca-deportiva', 'en');
  assert.match(es.src, /^\/catalogo\/.+\.webp$/);
  assert.equal(es.src, en.src);
  assert.ok(es.alt && en.alt && es.alt !== en.alt);
});

test('claves del view-model de la tarjeta', () => {
  assert.equal(m.claveDeServicio('sal-y-sol', 'pesca-deportiva'), 'servicio:sal-y-sol/pesca-deportiva');
  assert.equal(m.claveDePaquete('ventana-completo'), 'paquete:ventana-completo');
});


test('imagenesDeCatalogo: los paquetes de La Ventana traen tres fotos, empezando por la principal', () => {
  for (const slug of ['paquete-5-noches', 'paquete-7-noches']) {
    const clave = m.claveDePaquete(slug);
    const fotos = m.imagenesDeCatalogo(clave, 'es');
    assert.equal(fotos.length, 3);
    assert.equal(fotos[0].src, m.imagenDeCatalogo(clave, 'es').src);
    assert.equal(new Set(fotos.map((f) => f.src)).size, 3);
    assert.ok(fotos.every((f) => f.alt));
  }
  assert.deepEqual(m.imagenesDeCatalogo('servicio:nadie/nada', 'es'), []);
});
