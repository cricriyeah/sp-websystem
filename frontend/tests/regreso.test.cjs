/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const m = require(path.join(process.env.REGRESO_TEST_OUT, 'lib/regreso.js'));

const textos = {
  aria: 'Volver a {destino}',
  destinos: { corto: 'Destinos', aria: 'Volver a todos los destinos' },
  guias: { corto: 'Guías', aria: 'Volver a las guías' },
  anterior: { corto: 'Volver', aria: 'Volver a la página anterior' },
};
const laPaz = { slug: 'la-paz', nombre: 'La Paz' };
const r = (ruta, extra = {}) => m.regresoDe({ lang: 'es', ruta, textos, ...extra });
const DESTINOS = { href: '/es#sedes', etiqueta: 'Destinos', aria: 'Volver a todos los destinos', soloHub: true };
const A_LA_PAZ = { href: '/es/sede/la-paz#reservar', etiqueta: 'La Paz', aria: 'Volver a La Paz' };

test('en el inicio no hay regreso', () => {
  assert.equal(r('/es'), null);
  assert.equal(r('/es/'), null);
});

test('la sede vuelve a todos los destinos con la etiqueta corta, y en modo solo sede la marca soloHub', () => {
  assert.deepEqual(r('/es/sede/la-paz', { sede: laPaz }), DESTINOS);
});

test('un servicio o un paquete vuelve a «Qué reservar» de su sede, con su nombre', () => {
  assert.deepEqual(r('/es/servicio/sal-y-sol/pesca-deportiva', { sede: laPaz }), A_LA_PAZ);
  assert.deepEqual(r('/es/sede/la-paz/paquete/pesca-traslado?moneda=USD', { sede: laPaz }), A_LA_PAZ);
});

test('sin sede conocida, el detalle vuelve a todos los destinos', () => {
  assert.deepEqual(r('/es/servicio/x/y'), DESTINOS);
});

test('una guía vuelve a «Antes de venir» de su sede; sin sede, al índice de guías', () => {
  assert.deepEqual(r('/es/guias/nado-con-orcas-la-ventana', { sede: { slug: 'la-ventana', nombre: 'La Ventana' } }), { href: '/es/sede/la-ventana#guias', etiqueta: 'La Ventana', aria: 'Volver a La Ventana' });
  assert.deepEqual(r('/es/guias/calendario'), { href: '/es/guias', etiqueta: 'Guías', aria: 'Volver a las guías', soloHub: true });
});

test('una legal vuelve a la página del sitio de la que se vino, nunca a otra legal ni fuera del sitio', () => {
  assert.deepEqual(r('/es/privacidad', { anterior: '/es/servicio/sal-y-sol/pesca-deportiva' }), { href: '/es/servicio/sal-y-sol/pesca-deportiva', etiqueta: 'Volver', aria: 'Volver a la página anterior' });
  assert.deepEqual(r('/es/deslinde', { anterior: '/es/privacidad', sede: laPaz }), { href: '/es/sede/la-paz', etiqueta: 'La Paz', aria: 'Volver a La Paz' });
  assert.equal(r('/es/cancelaciones').etiqueta, 'Destinos');
});

test('el índice de guías y nosotros vuelven a la sede si hay, si no a todos los destinos', () => {
  assert.equal(r('/es/guias', { sede: laPaz }).etiqueta, 'La Paz');
  assert.equal(r('/es/nosotros').etiqueta, 'Destinos');
});

test('las etiquetas cortas caben en la esquina de la barra a 390 px', () => {
  const dicts = ['es', 'en'].map((l) => require(path.join(__dirname, '..', 'src', 'app', '[lang]', 'dictionaries', `${l}.json`)).nav.regreso);
  for (const d of dicts) {
    for (const clave of ['destinos', 'guias', 'anterior', 'pasoAnterior', 'servicio', 'paquete']) {
      assert.ok(d[clave].corto.length <= 13, `${clave}: «${d[clave].corto}» es muy largo para la barra`);
      assert.ok(d[clave].aria.length > d[clave].corto.length, `${clave}: el aria dice a dónde vuelve`);
    }
    assert.ok(d.aria.includes('{destino}'));
  }
});

test('el logo de la empresa solo va en la barra cuando la esquina es nuestro logo', () => {
  assert.equal(m.empresaEnBarra(null), 'siempre');
  assert.equal(m.empresaEnBarra(r('/es/sede/la-paz', { sede: laPaz })), 'solo-sede');
  assert.equal(m.empresaEnBarra(r('/es/servicio/sal-y-sol/pesca-deportiva', { sede: laPaz })), 'nunca');
  assert.equal(m.empresaEnBarra({ etiqueta: 'Paso anterior' }), 'nunca');
});

test('el nombre de la esquina siempre cabe en una línea: el tamaño más grande que entra', () => {
  for (const e of ['LA PAZ', 'DESTINOS', 'LA VENTANA', 'GUÍAS', 'VOLVER', 'DETALLES', 'PAQUETE']) assert.equal(m.tamanoDeEtiqueta(e), 20, e);
  for (const e of ['PUERTO CHALE', 'DESTINATIONS']) assert.equal(m.tamanoDeEtiqueta(e), 16, e);
  for (const e of ['PASO ANTERIOR', 'PREVIOUS STEP']) assert.equal(m.tamanoDeEtiqueta(e), 14, e);
});

test('esLegal reconoce las tres legales', () => {
  assert.equal(m.esLegal('/en/privacidad'), true);
  assert.equal(m.esLegal('/es/sede/la-paz'), false);
});

test('el checkout nombra el destino de su «salir» con etiquetas cortas', () => {
  const sedes = { 'la-paz': { nombre: 'La Paz' } };
  const t = {
    aria: 'Volver a {destino}',
    destinos: textos.destinos,
    servicio: { corto: 'Detalles', aria: 'Volver a los detalles' },
    paquete: { corto: 'Paquete', aria: 'Volver al paquete' },
  };
  assert.deepEqual(m.etiquetaDeHref('/es/sede/la-paz#reservar', sedes, t), { etiqueta: 'La Paz', aria: 'Volver a La Paz' });
  assert.deepEqual(m.etiquetaDeHref('/es/sede/la-ventana/paquete/paquete-5-noches', sedes, t), { etiqueta: 'Paquete', aria: 'Volver al paquete' });
  assert.deepEqual(m.etiquetaDeHref('/es/servicio/sal-y-sol/pesca-deportiva', sedes, t), { etiqueta: 'Detalles', aria: 'Volver a los detalles' });
  assert.deepEqual(m.etiquetaDeHref('/es', sedes, t), { etiqueta: 'Destinos', aria: 'Volver a todos los destinos', soloHub: true });
  assert.equal(m.etiquetaDeHref('/es/sede/otra', sedes, t), null);
});
