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


test('imagenesDeCatalogo: los paquetes de La Ventana traen cuatro fotos, empezando por la principal', () => {
  for (const slug of ['paquete-5-noches', 'paquete-7-noches']) {
    const clave = m.claveDePaquete(slug);
    const fotos = m.imagenesDeCatalogo(clave, 'es');
    assert.equal(fotos.length, 4);
    assert.equal(fotos[0].src, m.imagenDeCatalogo(clave, 'es').src);
    assert.equal(new Set(fotos.map((f) => f.src)).size, 4);
    assert.ok(fotos.every((f) => f.alt));
  }
  assert.deepEqual(m.imagenesDeCatalogo('servicio:nadie/nada', 'es'), []);
});

test('galeriaDeCatalogo: los dos paquetes con hospedaje comparten las mismas seis fotos, con medidas y sin repetirse', () => {
  const g5 = m.galeriaDeCatalogo(m.claveDePaquete('paquete-5-noches'), 'es');
  const g7 = m.galeriaDeCatalogo(m.claveDePaquete('paquete-7-noches'), 'en');
  assert.equal(g5.length, 6);
  assert.deepEqual(g5.map((f) => f.src), g7.map((f) => f.src));
  assert.equal(new Set(g5.map((f) => f.src)).size, 6);
  assert.ok(g5.every((f) => f.alt && f.ancho > 0 && f.alto > 0));
  assert.notEqual(g5[0].alt, g7[0].alt);
});

test('galeriaDeCatalogo: un producto sin galería la devuelve vacía', () => {
  assert.deepEqual(m.galeriaDeCatalogo('servicio:sal-y-sol/pesca-deportiva', 'es'), []);
  assert.deepEqual(m.galeriaDeCatalogo('servicio:nadie/nada', 'es'), []);
});
