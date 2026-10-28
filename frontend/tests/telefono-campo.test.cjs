/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const c = require(path.join(process.env.TELEFONO_CAMPO_TEST_OUT, 'lib/telefono-campo.js'));

const estado = (iso, texto, valor) => ({ iso, texto, valor });

test('estadoInicial: vacio es Mexico sin texto', () => {
  assert.deepEqual(c.estadoInicial(''), estado('MX', '', ''));
  assert.deepEqual(c.estadoInicial('   '), estado('MX', '', ''));
});

test('estadoInicial: formatos viejos se separan sin perder digitos', () => {
  assert.deepEqual(c.estadoInicial('612 123 4567'), estado('MX', '6121234567', '+526121234567'));
  assert.deepEqual(c.estadoInicial('+52 1 612 123 4567'), estado('MX', '6121234567', '+526121234567'));
  assert.deepEqual(c.estadoInicial('(612) 123-4567'), estado('MX', '6121234567', '+526121234567'));
});

test('estadoInicial: el compacto elige el pais principal del codigo', () => {
  assert.deepEqual(c.estadoInicial('+34612345678'), estado('ES', '612345678', '+34612345678'));
  assert.equal(c.estadoInicial('+12125551234').iso, 'US');
  assert.equal(c.estadoInicial('+79123456789').iso, 'RU');
  assert.equal(c.estadoInicial('+447911123456').iso, 'GB');
  assert.equal(c.estadoInicial('+376312345').iso, 'AD');
});

test('estadoInicial: lo que no se entiende queda visible con Mexico, nunca se vacia', () => {
  assert.deepEqual(c.estadoInicial('asdf'), estado('MX', 'asdf', 'asdf'));
  assert.deepEqual(c.estadoInicial('+999 123 456'), estado('MX', '+999 123 456', '+999 123 456'));
  assert.deepEqual(c.estadoInicial('12345'), estado('MX', '12345', '+5212345'));
});

test('alEscribir: teclear no formatea ni mueve nada', () => {
  assert.deepEqual(c.alEscribir('MX', '612 123 4567'), estado('MX', '612 123 4567', '+526121234567'));
  assert.deepEqual(c.alEscribir('MX', '(612) 123-4567'), estado('MX', '(612) 123-4567', '+526121234567'));
  assert.deepEqual(c.alEscribir('MX', '6'), estado('MX', '6', '+526'));
});

test('alEscribir: sin digitos el valor es vacio, el pais solo no cuenta', () => {
  assert.deepEqual(c.alEscribir('MX', ''), estado('MX', '', ''));
  assert.deepEqual(c.alEscribir('MX', '( )'), estado('MX', '( )', ''));
});

test('alEscribir: las letras se descartan del texto mostrado', () => {
  assert.deepEqual(c.alEscribir('MX', '612abc123'), estado('MX', '612123', '+52612123'));
});

test('alEscribir: la extension se corta del valor y del texto', () => {
  assert.deepEqual(c.alEscribir('MX', '612 123 4567 ext. 12'), estado('MX', '6121234567', '+526121234567'));
  assert.deepEqual(c.alEscribir('MX', '612 123 4567 x12'), estado('MX', '6121234567', '+526121234567'));
});

test('alEscribir: topa en 15 digitos entre codigo y numero y el texto lo refleja', () => {
  const r = c.alEscribir('MX', '1'.repeat(30));
  assert.equal(r.valor, '+52' + '1'.repeat(13));
  assert.equal(r.texto, '1'.repeat(13));
  assert.ok(r.valor.length <= 16);
  const us = c.alEscribir('US', '2'.repeat(30));
  assert.equal(us.valor.length, 16);
});

test('alEscribir: el cero inicial se conserva', () => {
  assert.deepEqual(c.alEscribir('GB', '07911 123456'), estado('GB', '07911 123456', '+4407911123456'));
});

test('alEscribir: digitos no ASCII pasan a ASCII en el valor', () => {
  const r = c.alEscribir('MX', '٦١٢ ١٢٣ ٤٥٦٧');
  assert.equal(r.valor, '+526121234567');
  assert.equal(r.iso, 'MX');
});

test('alEscribir: pegar con + mueve el selector y deja solo la parte nacional', () => {
  assert.deepEqual(c.alEscribir('MX', '+34 612 34 56 78'), estado('ES', '612345678', '+34612345678'));
  assert.deepEqual(c.alEscribir('MX', '0034 612 34 56 78'), estado('ES', '612345678', '+34612345678'));
  assert.deepEqual(c.alEscribir('ES', '+52 1 612 123 4567'), estado('MX', '16121234567', '+5216121234567'));
});

test('alEscribir: el codigo ya coincide, el selector no se recalcula (+1, +7, +44)', () => {
  assert.equal(c.alEscribir('CA', '+1 416 555 1234').iso, 'CA');
  assert.equal(c.alEscribir('JM', '+1 876 555 1234').iso, 'JM');
  assert.equal(c.alEscribir('KZ', '+7 701 234 56 78').iso, 'KZ');
  assert.equal(c.alEscribir('GG', '+44 7911 123456').iso, 'GG');
  assert.equal(c.alEscribir('GB', '+44 7911 123456').iso, 'GB');
});

test('alEscribir: codigo distinto en un grupo compartido toma el principal', () => {
  assert.equal(c.alEscribir('MX', '+1 416 555 1234').iso, 'US');
  assert.equal(c.alEscribir('MX', '+44 7911 123456').iso, 'GB');
});

test('alEscribir: un + sin codigo completo queda a medias, sin inventar un numero mexicano', () => {
  assert.deepEqual(c.alEscribir('MX', '+'), estado('MX', '+', ''));
  assert.deepEqual(c.alEscribir('MX', '+3'), estado('MX', '+3', '+3'));
  assert.deepEqual(c.alEscribir('MX', '00'), estado('MX', '00', ''));
});

test('alEscribir: codigo que no existe conserva el texto y marca el valor con +', () => {
  assert.deepEqual(c.alEscribir('MX', '+999 123 456'), estado('MX', '+999 123 456', '+999123456'));
  assert.deepEqual(c.alEscribir('ES', '00999 123 456'), estado('ES', '00999 123 456', '+999123456'));
});

test('alEscribir: el valor nunca pasa de 16 caracteres', () => {
  for (const crudo of ['9'.repeat(100), '+' + '9'.repeat(100), '+34' + '9'.repeat(100), '+999' + '9'.repeat(100)]) {
    assert.ok(c.alEscribir('MX', crudo).valor.length <= 16, crudo.slice(0, 8));
  }
});

test('alCambiarPais: conserva el texto escrito y cambia el codigo', () => {
  assert.deepEqual(c.alCambiarPais('612 123 4567', 'ES'), estado('ES', '612 123 4567', '+346121234567'));
  assert.deepEqual(c.alCambiarPais('', 'ES'), estado('ES', '', ''));
});

test('alCambiarPais: un texto con + a medias se queda a medias', () => {
  assert.deepEqual(c.alCambiarPais('+999 123', 'ES'), estado('ES', '+999 123', '+999123'));
});

test('alSalir: canoniza y da formato nacional, sin tocar el pais elegido', () => {
  assert.deepEqual(c.alSalir(estado('MX', '(612) 123-4567', '+526121234567')), estado('MX', '612 123 4567', '+526121234567'));
  assert.deepEqual(c.alSalir(estado('GB', '07911 123456', '+4407911123456')), estado('GB', '7911 123456', '+447911123456'));
  assert.deepEqual(c.alSalir(estado('MX', '16121234567', '+5216121234567')), estado('MX', '612 123 4567', '+526121234567'));
});

test('alSalir: lo que no es un numero posible no se toca', () => {
  for (const e of [estado('MX', '612 123', '+52612123'), estado('MX', '', ''), estado('MX', '+999 123', '+999123'), estado('MX', 'asdf', 'asdf')]) {
    assert.deepEqual(c.alSalir(e), e);
  }
});

test('alSalir: el valor guardado sigue siendo compacto', () => {
  const r = c.alSalir(estado('NO', '41 23 45 67', '+4741234567'));
  assert.equal(r.valor, '+4741234567');
  assert.ok(r.valor.length <= 16);
});

test('un valor que sale de alEscribir y vuelve a estadoInicial no cambia', () => {
  for (const crudo of ['612 123 4567', '+34 612 34 56 78', '07911 123456']) {
    const e = c.alEscribir('MX', crudo);
    const otra = c.estadoInicial(e.valor);
    assert.equal(otra.valor, e.valor);
  }
});

test('lineaDeTelefono: número con país, o el valor tal cual si no se puede formatear', () => {
  const nombre = (iso) => ({ MX: 'México', US: 'Estados Unidos' })[iso];
  assert.equal(c.lineaDeTelefono('+526121234567', nombre), '+52 612 123 4567 · México');
  assert.equal(c.lineaDeTelefono('+526121234567', () => undefined), '+52 612 123 4567');
  assert.equal(c.lineaDeTelefono('123', nombre), '123');
  assert.equal(c.lineaDeTelefono('', nombre), '');
});

test('lineaDeTelefono: un móvil británico se muestra como Reino Unido, no como Guernsey', () => {
  const nombre = (iso) => ({ GB: 'Reino Unido', GG: 'Guernesey' })[iso];
  assert.equal(c.lineaDeTelefono('+447911123456', nombre), '+44 7911 123456 · Reino Unido');
});
