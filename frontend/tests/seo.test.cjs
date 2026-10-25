/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const s = require(path.join(process.env.SEO_TEST_OUT, 'lib/seo.js'));

test('una descripcion corta se queda como esta', () => {
  assert.equal(s.recortarDescripcion('  Pesca   deportiva en La Paz.  '), 'Pesca deportiva en La Paz.');
});

test('vacia o solo espacios no es descripcion', () => {
  assert.equal(s.recortarDescripcion(''), undefined);
  assert.equal(s.recortarDescripcion('   '), undefined);
  assert.equal(s.recortarDescripcion(null), undefined);
});

test('una descripcion larga se corta en la ultima oracion que cabe', () => {
  const texto = 'Cinco noches en La Ventana con todo resuelto: te recogen en el aeropuerto y duermes en el hotel. '
    + 'Del dia 2 al 5 sales cada dia al mar a buscar ballenas y orcas, con comida ligera y equipo de snorkel a bordo. '
    + 'Al final te llevan de vuelta al aeropuerto.';
  const corta = s.recortarDescripcion(texto);
  assert.ok(corta.length <= s.LARGO_DESCRIPCION, `${corta.length}`);
  assert.ok(corta.endsWith('.'));
  assert.ok(texto.startsWith(corta));
});

test('sin oracion donde cortar, corta en una palabra y pone puntos suspensivos', () => {
  const texto = 'palabra '.repeat(40).trim();
  const corta = s.recortarDescripcion(texto);
  assert.ok(corta.length <= s.LARGO_DESCRIPCION);
  assert.ok(corta.endsWith('…'));
  assert.ok(!/palabr…$/.test(corta), 'no parte una palabra');
});

test('las etiquetas para compartir llevan la URL y el titulo de la pagina, no los de la portada', () => {
  const e = s.etiquetasSociales({
    url: 'https://x.test/es/sede/la-paz', titulo: 'La Paz | Marca', descripcion: 'Desc', locale: 'es_MX',
    nombreDelSitio: 'Marca', imagen: 'https://x.test/es/opengraph-image',
  });
  assert.equal(e.openGraph.url, 'https://x.test/es/sede/la-paz');
  assert.equal(e.openGraph.title, 'La Paz | Marca');
  assert.equal(e.openGraph.images[0].url, 'https://x.test/es/opengraph-image');
  assert.equal(e.twitter.card, 'summary_large_image');
  assert.deepEqual(e.twitter.images, ['https://x.test/es/opengraph-image']);
});

test('las migas van numeradas desde 1', () => {
  const m = s.jsonLdMigas([{ nombre: 'Inicio', url: 'https://x.test/es' }, { nombre: 'La Paz', url: 'https://x.test/es/sede/la-paz' }]);
  assert.equal(m['@type'], 'BreadcrumbList');
  assert.deepEqual(m.itemListElement.map((i) => i.position), [1, 2]);
  assert.equal(m.itemListElement[1].item, 'https://x.test/es/sede/la-paz');
});

test('la marca son dos bloques: organizacion y sitio, sin datos inventados', () => {
  const [org, sitio] = s.jsonLdMarca({ nombre: 'Marca', url: 'https://x.test/es', descripcion: 'D', idioma: 'es-MX' });
  assert.equal(org['@type'], 'Organization');
  assert.equal(sitio['@type'], 'WebSite');
  assert.equal(sitio.inLanguage, 'es-MX');
  for (const clave of ['sameAs', 'logo', 'telephone']) assert.equal(org[clave], undefined, clave);
});

test('un viaje con precio lleva su oferta, dicha sin IVA', () => {
  const v = s.jsonLdViaje({
    nombre: 'Pesca con mosca', descripcion: 'D', url: 'https://x.test/es/servicio/a/b', proveedor: { nombre: 'Empresa' },
    precio: '2500.00', lugar: 'La Ventana',
  });
  assert.equal(v['@type'], 'TouristTrip');
  assert.equal(v.provider.name, 'Empresa');
  assert.equal(v.offers.price, '2500.00');
  assert.equal(v.offers.priceCurrency, 'MXN');
  assert.equal(v.offers.priceSpecification.valueAddedTaxIncluded, false);
  assert.equal(v.itinerary.name, 'La Ventana');
});

test('un viaje sin precio valido no lleva oferta', () => {
  for (const precio of [null, undefined, '', '0', '0.00', 'abc']) {
    const v = s.jsonLdViaje({ nombre: 'X', url: 'https://x.test', proveedor: { nombre: 'E' }, precio });
    assert.equal(v.offers, undefined, String(precio));
  }
});

test('las preguntas frecuentes van al JSON-LD tal como se pintan', () => {
  const f = s.jsonLdPreguntas([{ q: '¿Uno?', a: 'Sí.' }, { q: '¿Dos?', a: 'No.' }]);
  assert.equal(f['@type'], 'FAQPage');
  assert.deepEqual(f.mainEntity.map((p) => p.name), ['¿Uno?', '¿Dos?']);
  assert.equal(f.mainEntity[1].acceptedAnswer.text, 'No.');
});
