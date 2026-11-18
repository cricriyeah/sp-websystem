/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const m = require(path.join(process.env.CATALOGO_EN_TEXTO_TEST_OUT, 'lib/catalogo-en-texto.js'));

const base = { permite_anticipo: true, porcentaje_anticipo: 30, pide_hora: false, hora_apertura: null, hora_cierre: null };
const ballenas = { ...base, empresa_slug: 'piratas-adventures', slug: 'avistamiento-ballenas', precio_base: '5000.00', precio_persona_extra: '600.00', tipo_cambio_usd: '17.5000', personas_incluidas: 6, capacidad_maxima: 8, duracion: '2 h' };
const pesca = { ...base, empresa_slug: 'sal-y-sol', slug: 'pesca-deportiva', precio_base: '11290.00', precio_persona_extra: '1350.00', tipo_cambio_usd: '17.5000', personas_incluidas: 2, capacidad_maxima: 5, duracion: '6–7 h', punto_salida: 'Marina La Costa', pide_hora: true, hora_apertura: '05:00:00', hora_cierre: '07:00:00' };
const mosca = { ...base, empresa_slug: 'la-ventana-travel', slug: 'pesca-con-mosca', precio_base: '12000.00', precio_persona_extra: '0.00', tipo_cambio_usd: '17.5000', personas_incluidas: 3, capacidad_maxima: 3, duracion: 'Día completo', permite_anticipo: false };
const catalogo = [ballenas, pesca, mosca];

test('la marca se cambia por el precio del catalogo con IVA, como en la tarjeta', () => {
  assert.equal(m.textoConCatalogo('Cuesta {precio:piratas-adventures/avistamiento-ballenas}.', catalogo, 'es'), 'Cuesta $5,800 MXN.');
  assert.equal(m.textoConCatalogo('Cada extra, {extra:piratas-adventures/avistamiento-ballenas}.', catalogo, 'es'), 'Cada extra, $696 MXN.');
});

test('en ingles va en pesos con su aproximado en dolares, el mismo de la tarjeta', () => {
  assert.equal(m.textoConCatalogo('It costs {precio:piratas-adventures/avistamiento-ballenas}.', catalogo, 'en'), 'It costs $5,800 MXN (about $331.76 USD).');
});

test('la duracion de la ficha se dice en una frase, en cada idioma', () => {
  assert.equal(m.textoConCatalogo('Son {duracion:piratas-adventures/avistamiento-ballenas} en la bahía.', catalogo, 'es'), 'Son 2 horas en la bahía.');
  assert.equal(m.textoConCatalogo('El viaje dura {duracion:sal-y-sol/pesca-deportiva}.', catalogo, 'es'), 'El viaje dura 6 a 7 horas.');
  assert.equal(m.textoConCatalogo('The trip lasts {duracion:sal-y-sol/pesca-deportiva}.', catalogo, 'en'), 'The trip lasts 6 to 7 hours.');
  assert.equal(m.textoConCatalogo('Una salida de {duracion:sal-y-sol/pesca-deportiva}', [{ ...pesca, duracion: '1 h' }], 'es'), 'Una salida de 1 hora');
});

test('un texto libre de duracion va con mayuscula solo al empezar la frase', () => {
  assert.equal(m.textoConCatalogo('{duracion:la-ventana-travel/pesca-con-mosca} en el mar.', catalogo, 'es'), 'Día completo en el mar.');
  assert.equal(m.textoConCatalogo('Es un {duracion:la-ventana-travel/pesca-con-mosca} en el mar.', catalogo, 'es'), 'Es un día completo en el mar.');
});

test('personas, maximo, anticipo, salida y horario salen del servicio', () => {
  assert.equal(m.textoConCatalogo('Cubre a {personas:sal-y-sol/pesca-deportiva}, hasta {maximo:sal-y-sol/pesca-deportiva}.', catalogo, 'es'), 'Cubre a 2, hasta 5.');
  assert.equal(m.textoConCatalogo('Aparta con el {anticipo:sal-y-sol/pesca-deportiva}.', catalogo, 'es'), 'Aparta con el 30 %.');
  assert.equal(m.textoConCatalogo('Hold it with {anticipo:sal-y-sol/pesca-deportiva}.', catalogo, 'en'), 'Hold it with 30%.');
  assert.equal(m.textoConCatalogo('Sales de {salida:sal-y-sol/pesca-deportiva}.', catalogo, 'es'), 'Sales de Marina La Costa.');
  assert.equal(m.textoConCatalogo('Sales {horario:sal-y-sol/pesca-deportiva}.', catalogo, 'es'), 'Sales entre las 5:00 y las 7:00 am.');
  assert.equal(m.textoConCatalogo('{hora:sal-y-sol/pesca-deportiva}', catalogo, 'es'), '5:00 am');
  assert.equal(m.textoConCatalogo('You leave {horario:sal-y-sol/pesca-deportiva}.', catalogo, 'en'), 'You leave between 5:00 and 7:00 am.');
});

test('sin el dato en el backoffice la marca no se resuelve: no se inventa', () => {
  assert.equal(m.textoConCatalogo('Aparta con {anticipo:la-ventana-travel/pesca-con-mosca}.', catalogo, 'es'), null);
  assert.equal(m.textoConCatalogo('Sales {horario:piratas-adventures/avistamiento-ballenas}.', catalogo, 'es'), null);
  assert.equal(m.textoConCatalogo('Extra {extra:la-ventana-travel/pesca-con-mosca}.', catalogo, 'es'), null);
  assert.equal(m.textoConCatalogo('Hasta {maximo:sal-y-sol/pesca-deportiva}.', [{ ...pesca, capacidad_maxima: null }], 'es'), null);
  assert.equal(m.textoConCatalogo('Cuesta {precio:sal-y-sol/pesca-deportiva}.', null, 'es'), null);
});

test('un texto sin marcas sale igual, aunque el catalogo no responda', () => {
  assert.equal(m.textoConCatalogo('Sin datos.', null, 'es'), 'Sin datos.');
  const contenido = { titulo: 'Hola', lista: ['a', 'b'], n: 3 };
  assert.deepEqual(m.conCatalogo(contenido, null, 'es'), contenido);
});

test('en una lista se quita el elemento sin su dato; en un texto suelto, solo la frase', () => {
  const contenido = {
    subtitulo: 'Un pueblo de pescadores. Son {duracion:piratas-adventures/safari-marino} en el mar. Ven pronto.',
    faq: [
      { q: '¿Cuánto cuesta?', a: 'Desde {precio:sal-y-sol/pesca-deportiva}. Con capitán.' },
      { q: '¿Qué incluye?', a: 'La panga.' },
    ],
    parrafos: ['Sales {horario:sal-y-sol/pesca-deportiva}.', 'Llevas gorra.'],
    datos: [{ etiqueta: 'Duración', valor: '{duracion:sal-y-sol/pesca-deportiva}' }, { etiqueta: 'Temporada', valor: 'Todo el año' }],
  };
  const sinCatalogo = m.conCatalogo(contenido, null, 'es');
  assert.equal(sinCatalogo.subtitulo, 'Un pueblo de pescadores. Ven pronto.');
  assert.deepEqual(sinCatalogo.faq, [{ q: '¿Qué incluye?', a: 'La panga.' }]);
  assert.deepEqual(sinCatalogo.parrafos, ['Llevas gorra.']);
  assert.deepEqual(sinCatalogo.datos, [{ etiqueta: 'Temporada', valor: 'Todo el año' }]);

  const conCatalogo = m.conCatalogo(contenido, catalogo, 'es');
  assert.equal(conCatalogo.faq.length, 2);
  assert.equal(conCatalogo.parrafos[0], 'Sales entre las 5:00 y las 7:00 am.');
  assert.equal(conCatalogo.datos[0].valor, '6 a 7 horas');
  assert.doesNotMatch(JSON.stringify(conCatalogo), /\{(precio|duracion|horario):/);
});

test('clavesDeMarcas junta las claves de todo un contenido, sin repetir', () => {
  assert.deepEqual(
    m.clavesDeMarcas({ a: '{precio:sal-y-sol/pesca-deportiva} y {duracion:sal-y-sol/pesca-deportiva}', b: ['{maximo:piratas-adventures/pesca-deportiva}'] }).sort(),
    ['piratas-adventures/pesca-deportiva', 'sal-y-sol/pesca-deportiva'],
  );
});

// Guardia: cada marca escrita en el contenido nombra un campo que existe y un servicio real del catálogo. Una marca con
// errata no se resolvería nunca y su frase desaparecería en silencio.
test('las marcas del contenido apuntan a campos y servicios que existen', () => {
  const SERVICIOS = new Set([
    'sal-y-sol/pesca-deportiva', 'la-ventana-travel/pesca-con-mosca', 'la-ventana-travel/avistamiento-ballenas-orcas',
    'la-ventana-travel/hospedaje-la-ventana', 'piratas-adventures/avistamiento-ballenas', 'piratas-adventures/safari-marino',
    'piratas-adventures/pesca-deportiva',
  ]);
  const CAMPOS = new Set(['precio', 'extra', 'duracion', 'personas', 'maximo', 'anticipo', 'salida', 'hora', 'horario']);
  const contenido = path.join(__dirname, '..', 'src', 'content');
  const diccionarios = path.join(__dirname, '..', 'src', 'app', '[lang]', 'dictionaries');
  const archivos = [
    ...fs.readdirSync(contenido).filter((f) => f.endsWith('.ts')).map((f) => path.join(contenido, f)),
    ...['es.json', 'en.json'].map((f) => path.join(diccionarios, f)),
  ];
  const malas = [];
  for (const ruta of archivos) {
    const archivo = path.basename(ruta);
    const texto = fs.readFileSync(ruta, 'utf8');
    for (const [marca, campo, clave] of texto.matchAll(/\{([a-z]+):([a-z0-9-]+\/[a-z0-9-]+)\}/g)) {
      if (!CAMPOS.has(campo) || !SERVICIOS.has(clave)) malas.push(`${archivo}: ${marca}`);
    }
  }
  assert.deepEqual(malas, []);
});
