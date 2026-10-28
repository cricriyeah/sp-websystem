/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');

const archivo = path.join(process.env.PAISES_TELEFONO_TEST_OUT, 'lib/paises-telefono.js');
const p = require(archivo);

// Copia nueva del modulo con la biblioteca parchada (no queda en la cache).
function cargarConBiblioteca(parche) {
  const original = Module._load;
  Module._load = function (peticion, ...resto) {
    const real = original.call(this, peticion, ...resto);
    return peticion === 'libphonenumber-js/min' ? { ...real, ...parche } : real;
  };
  delete require.cache[archivo];
  try {
    return require(archivo);
  } finally {
    Module._load = original;
    delete require.cache[archivo];
  }
}
const lanza = () => {
  throw new Error('la biblioteca fallo');
};

const isos = (lista) => lista.map((x) => x.iso);

test('hay 245 paises con codigo, ISO unico y nombre, en es y en', () => {
  for (const lang of ['es', 'en']) {
    const lista = p.listarPaises(lang);
    assert.equal(lista.length, 245, lang);
    assert.equal(new Set(isos(lista)).size, 245, 'ISO repetido en ' + lang);
    for (const pais of lista) {
      assert.match(pais.iso, /^[A-Z]{2}$/);
      assert.match(pais.codigo, /^\d{1,3}$/);
      assert.ok(pais.nombre.length > 0, pais.iso);
    }
  }
});

test('Mexico, Estados Unidos y Canada van fijos arriba, en ese orden', () => {
  for (const lang of ['es', 'en']) {
    assert.deepEqual(isos(p.listarPaises(lang)).slice(0, 3), ['MX', 'US', 'CA']);
  }
  assert.deepEqual(p.PAISES_FRECUENTES, ['MX', 'US', 'CA']);
});

test('el resto va alfabetico segun el idioma', () => {
  for (const lang of ['es', 'en']) {
    const resto = p.listarPaises(lang).slice(3);
    const colador = new Intl.Collator(lang);
    for (let i = 1; i < resto.length; i += 1) {
      assert.ok(colador.compare(resto[i - 1].nombre, resto[i].nombre) <= 0, lang + ': ' + resto[i - 1].nombre + ' > ' + resto[i].nombre);
    }
  }
});

test('nombres y codigos por idioma', () => {
  const es = Object.fromEntries(p.listarPaises('es').map((x) => [x.iso, x]));
  const en = Object.fromEntries(p.listarPaises('en').map((x) => [x.iso, x]));
  assert.equal(es.MX.nombre, 'México');
  assert.equal(en.MX.nombre, 'Mexico');
  assert.equal(es.DE.nombre, 'Alemania');
  assert.equal(en.DE.nombre, 'Germany');
  assert.equal(es.MX.codigo, '52');
  assert.equal(es.US.codigo, '1');
  assert.equal(es.ES.codigo, '34');
  assert.equal(es.AD.codigo, '376');
});

test('buscar vacio devuelve la lista completa; solo + o espacios tambien', () => {
  const lista = p.listarPaises('es');
  for (const q of ['', '   ', '+', ' + ']) {
    assert.equal(p.buscarPaises(lista, q).length, 245, JSON.stringify(q));
  }
});

test('buscar por nombre, sin acentos ni mayusculas', () => {
  const lista = p.listarPaises('es');
  assert.deepEqual(isos(p.buscarPaises(lista, 'mex')), ['MX']);
  assert.deepEqual(isos(p.buscarPaises(lista, 'MÉX')), ['MX']);
  assert.ok(isos(p.buscarPaises(lista, 'peru')).includes('PE'));
  assert.ok(isos(p.buscarPaises(lista, 'Perú')).includes('PE'));
  assert.equal(p.buscarPaises(lista, 'alemania')[0].iso, 'DE');
  assert.equal(p.buscarPaises(p.listarPaises('en'), 'germany')[0].iso, 'DE');
  assert.equal(p.buscarPaises(p.listarPaises('en'), 'curacao')[0].iso, 'CW');
});

test('buscar por sigla ISO pone el pais exacto primero', () => {
  const lista = p.listarPaises('es');
  assert.equal(p.buscarPaises(lista, 'de')[0].iso, 'DE');
  assert.equal(p.buscarPaises(lista, 'MX')[0].iso, 'MX');
});

test('buscar por codigo con o sin +', () => {
  const lista = p.listarPaises('es');
  for (const q of ['+34', '34', ' +34 ', '+ 34']) {
    const encontrados = p.buscarPaises(lista, q);
    assert.deepEqual(isos(encontrados), ['ES'], JSON.stringify(q));
  }
  const uno = p.buscarPaises(lista, '+1');
  assert.equal(uno.length, 25);
  assert.ok(uno.every((x) => x.codigo === '1'));
  assert.ok(isos(uno).includes('JM'));
});

test('buscar un codigo parcial devuelve los que empiezan igual', () => {
  const lista = p.listarPaises('es');
  const t3 = p.buscarPaises(lista, '+3');
  assert.ok(t3.length > 5);
  assert.ok(t3.every((x) => x.codigo.startsWith('3')));
  assert.ok(isos(t3).includes('ES'));
});

test('buscar algo que no existe devuelve lista vacia', () => {
  const lista = p.listarPaises('es');
  assert.deepEqual(p.buscarPaises(lista, 'zzzzzz'), []);
  assert.deepEqual(p.buscarPaises(lista, '+999'), []);
});

test('la busqueda conserva el orden de la lista (fijos primero) entre iguales', () => {
  const lista = p.listarPaises('es');
  const uno = p.buscarPaises(lista, '+1');
  assert.deepEqual(isos(uno).slice(0, 2), ['US', 'CA']);
});

test('paisPrincipal da el pais que se elige al restaurar un codigo', () => {
  assert.equal(p.paisPrincipal('1'), 'US');
  assert.equal(p.paisPrincipal('7'), 'RU');
  assert.equal(p.paisPrincipal('44'), 'GB');
  assert.equal(p.paisPrincipal('52'), 'MX');
  assert.equal(p.paisPrincipal('376'), 'AD');
  assert.equal(p.paisPrincipal('34'), 'ES');
  assert.equal(p.paisPrincipal('999'), null);
  assert.equal(p.paisPrincipal(''), null);
});

test('todo codigo de la lista tiene un pais principal que lo usa', () => {
  const lista = p.listarPaises('en');
  for (const pais of lista) {
    const principal = p.paisPrincipal(pais.codigo);
    assert.ok(principal, pais.codigo);
    assert.equal(lista.find((x) => x.iso === principal).codigo, pais.codigo);
  }
});

test('sin Intl.DisplayNames se muestra la sigla ISO y la lista sigue operable', () => {
  const original = Intl.DisplayNames;
  Intl.DisplayNames = undefined;
  try {
    const lista = p.listarPaises('es');
    assert.equal(lista.length, 245);
    assert.deepEqual(isos(lista).slice(0, 3), ['MX', 'US', 'CA']);
    assert.ok(lista.every((x) => x.nombre === x.iso));
    assert.equal(p.buscarPaises(lista, 'de')[0].iso, 'DE');
    assert.deepEqual(isos(p.buscarPaises(lista, '+34')), ['ES']);
  } finally {
    Intl.DisplayNames = original;
  }
});

test('si Intl.DisplayNames lanza (idioma raro), cae a la sigla ISO', () => {
  const original = Intl.DisplayNames;
  Intl.DisplayNames = function () {
    throw new RangeError('idioma invalido');
  };
  try {
    assert.ok(p.listarPaises('es').every((x) => x.nombre === x.iso));
  } finally {
    Intl.DisplayNames = original;
  }
});

test('si la biblioteca lanza, quedan al menos los tres frecuentes', () => {
  const rota = cargarConBiblioteca({ getCountries: lanza });
  const lista = rota.listarPaises('es');
  assert.deepEqual(lista.map((x) => [x.iso, x.codigo]), [['MX', '52'], ['US', '1'], ['CA', '1']]);
  assert.equal(rota.paisPrincipal('1'), 'US');
  assert.equal(rota.paisPrincipal('52'), 'MX');
  assert.equal(rota.paisPrincipal('376'), null);
});

test('codigoDePais da el codigo de marcacion de una sigla', () => {
  assert.equal(p.codigoDePais('MX'), '52');
  assert.equal(p.codigoDePais('US'), '1');
  assert.equal(p.codigoDePais('GB'), '44');
  assert.equal(p.codigoDePais('AD'), '376');
  assert.equal(p.codigoDePais('XX'), null);
  assert.equal(p.codigoDePais('mx'), null);
  assert.equal(p.codigoDePais(''), null);
});

test('codigoDePais con la biblioteca rota solo conoce los tres frecuentes', () => {
  const rota = cargarConBiblioteca({ getCountries: lanza });
  assert.equal(rota.codigoDePais('MX'), '52');
  assert.equal(rota.codigoDePais('CA'), '1');
  assert.equal(rota.codigoDePais('DE'), null);
});
