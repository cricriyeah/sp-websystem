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

test('fotosDeGrupo: todas o ninguna', () => {
  assert.equal(m.fotosDeGrupo(['servicio:sal-y-sol/pesca-deportiva']), true);
  assert.equal(m.fotosDeGrupo(['servicio:sal-y-sol/pesca-deportiva', 'paquete:sin-foto']), false);
  assert.equal(m.fotosDeGrupo([]), false);
});
