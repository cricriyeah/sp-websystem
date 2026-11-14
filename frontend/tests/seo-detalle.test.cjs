/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const m = require(path.join(process.env.SEO_DETALLE_TEST_OUT, 'content/seo-detalle.js'));

test('un producto sin entrada no tiene titulo propio', () => {
  assert.equal(m.seoDeServicio('nadie', 'nada'), undefined);
  assert.equal(m.seoDePaquete('la-ventana', 'nada'), undefined);
  assert.equal(m.seoDeServicio('__proto__', 'x'), undefined);
});

test('la pesca de La Paz apunta a quien compara precios, no al termino de su sede', () => {
  const seo = m.seoDeServicio('sal-y-sol', 'pesca-deportiva');
  assert.match(seo.titulo.es, /^Precio/);
  assert.match(seo.titulo.en, /Prices/);
});

test('los paquetes de La Ventana dicen lo que se busca: orcas', () => {
  for (const paquete of ['paquete-5-noches', 'paquete-7-noches']) {
    const seo = m.seoDePaquete('la-ventana', paquete);
    assert.match(seo.titulo.es, /orcas/);
    assert.match(seo.titulo.en, /Orcas/);
    assert.match(seo.encabezado.es, /orcas/);
  }
});

test('ningun titulo pasa del largo que Google muestra, ni se repite', () => {
  for (const idioma of ['es', 'en']) {
    const titulos = m.TODOS_LOS_SEO_DE_DETALLE.map((seo) => seo.titulo[idioma]);
    for (const titulo of titulos) assert.ok(titulo.length <= m.LARGO_TITULO, `${titulo.length}: ${titulo}`);
    assert.equal(new Set(titulos).size, titulos.length, 'titulos repetidos');
  }
});

test('todo producto tiene titulo y renglon en los dos idiomas', () => {
  for (const seo of m.TODOS_LOS_SEO_DE_DETALLE) {
    for (const idioma of ['es', 'en']) {
      assert.ok(seo.titulo[idioma].trim(), 'titulo');
      assert.ok(seo.encabezado[idioma].trim(), 'encabezado');
    }
  }
});
