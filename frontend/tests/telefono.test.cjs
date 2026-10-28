/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const libreria = require('libphonenumber-js/min');

const archivo = path.join(process.env.TELEFONO_TEST_OUT, 'lib/telefono.js');
const t = require(archivo);

// Carga una copia nueva del modulo con la biblioteca parchada, para probar la
// degradacion cuando libphonenumber-js lanza. La copia no queda en la cache.
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

test('Mexico es el pais por defecto', () => {
  assert.equal(t.PAIS_POR_DEFECTO, 'MX');
});

test('los codigos de pais no son prefijo unos de otros (resolverCodigo depende de eso)', () => {
  const codigos = new Set(libreria.getCountries().map((c) => libreria.getCountryCallingCode(c)));
  for (const a of codigos) {
    for (const b of codigos) {
      if (a !== b) assert.equal(b.startsWith(a), false, a + ' es prefijo de ' + b);
    }
  }
});

test('evaluar: vacio, solo codigo y signos sueltos no cuentan como valor', () => {
  for (const v of ['', '   ', '+', '+52', ' +52 ', '+ 52', '()', '00']) {
    assert.equal(t.evaluar(v), 'vacio', JSON.stringify(v));
  }
});

test('evaluar: Mexico normal, con formato y sin codigo', () => {
  for (const v of ['+526121234567', '+52 612 123 4567', '612 123 4567', '(612) 123-4567', '612.123.4567']) {
    assert.equal(t.evaluar(v), 'ok', v);
  }
});

test('evaluar: pegar +52 1 (prefijo movil viejo) no bloquea', () => {
  assert.equal(t.evaluar('+52 1 612 123 4567'), 'ok');
  assert.equal(t.evaluar('+5216121234567'), 'ok');
});

test('evaluar: 01, 044 y 045 de Mexico no bloquean', () => {
  assert.equal(t.evaluar('+52 01 612 123 4567'), 'ok');
  assert.equal(t.evaluar('+52 044 612 123 4567'), 'ok');
  assert.equal(t.evaluar('+52 045 612 123 4567'), 'ok');
});

test('evaluar: las reglas de Mexico solo actuan cuando dejan 10 digitos', () => {
  assert.equal(t.evaluar('+52 1 612 123 45'), 'incompleto'); // 9 digitos tras el 1
  assert.equal(t.evaluar('+52 044 612 123 45'), 'incompleto'); // 9 digitos tras el 044
  assert.equal(t.evaluar('+52 044 612 123 45678'), 'incompleto'); // 12 tras el 044
  assert.equal(t.evaluar('+52 61212345678'), 'incompleto'); // 11 digitos sin 1 al frente
});

test('evaluar: 00 equivale a +', () => {
  assert.equal(t.evaluar('0052 612 123 4567'), 'ok');
  assert.equal(t.evaluar('0034 612 34 56 78'), 'ok');
  assert.equal(t.evaluar('00999 123 456'), 'codigo-desconocido');
});

test('evaluar: casi valido es incompleto', () => {
  assert.equal(t.evaluar('+52 612 123 456'), 'incompleto'); // 9 digitos
  assert.equal(t.evaluar('+1 212555'), 'incompleto');
  assert.equal(t.evaluar('+526'), 'incompleto');
});

test('evaluar: basura sin digitos es incompleto, no vacio', () => {
  assert.equal(t.evaluar('asdf'), 'incompleto');
});

test('evaluar: codigo desconocido', () => {
  assert.equal(t.evaluar('+999 123 456'), 'codigo-desconocido');
  assert.equal(t.evaluar('+0 612'), 'codigo-desconocido');
});

test('evaluar: paises con numero corto o de 10 digitos totales', () => {
  assert.equal(t.evaluar('+376 312 345'), 'ok'); // Andorra, 9 digitos
  assert.equal(t.evaluar('+299 321000'), 'ok'); // Groenlandia
  assert.equal(t.evaluar('+500 51234'), 'ok'); // Malvinas
  assert.equal(t.evaluar('+47 41234567'), 'ok'); // Noruega, 10 digitos
  assert.equal(t.evaluar('+45 12 34 56 78'), 'ok'); // Dinamarca
  assert.equal(t.evaluar('+65 8123 4567'), 'ok'); // Singapur
});

test('evaluar: codigos compartidos +1, +7 y +44', () => {
  assert.equal(t.evaluar('+1 212 555 1234'), 'ok');
  assert.equal(t.evaluar('+1 876 555 1234'), 'ok'); // Jamaica
  assert.equal(t.evaluar('+7 912 345 67 89'), 'ok');
  assert.equal(t.evaluar('+44 7911 123456'), 'ok');
});

test('evaluar: cero nacional inicial (Reino Unido) se acepta', () => {
  assert.equal(t.evaluar('+44 07911 123456'), 'ok');
});

test('evaluar: tope de 15 digitos entre codigo y numero', () => {
  assert.equal(t.evaluar('+49 1234567890123'), 'ok'); // 15 en total
  assert.equal(t.evaluar('+49 12345678901234'), 'incompleto'); // 16 en total
  assert.equal(t.evaluar('+52 612 123 4567 890 123'), 'incompleto');
});

test('evaluar: la extension se descarta', () => {
  assert.equal(t.evaluar('+52 612 123 4567 ext. 12'), 'ok');
  assert.equal(t.evaluar('612 123 4567 x12'), 'ok');
});

test('evaluar: digitos no ASCII', () => {
  assert.equal(t.evaluar('+٥٢ ٦١٢ ١٢٣ ٤٥٦٧'), 'ok');
});

test('resolverCodigo separa el codigo en cuanto esta completo', () => {
  assert.deepEqual(t.resolverCodigo('+52 612 123 4567'), { codigo: '52', resto: '6121234567' });
  assert.deepEqual(t.resolverCodigo('+526'), { codigo: '52', resto: '6' });
  assert.deepEqual(t.resolverCodigo('+52'), { codigo: '52', resto: '' });
  assert.deepEqual(t.resolverCodigo('0034 612 34 56 78'), { codigo: '34', resto: '612345678' });
  assert.deepEqual(t.resolverCodigo('+1 212 555 1234'), { codigo: '1', resto: '2125551234' });
  assert.deepEqual(t.resolverCodigo('+376 312 345'), { codigo: '376', resto: '312345' });
});

test('resolverCodigo devuelve null sin + ni 00, o con codigo inexistente', () => {
  assert.equal(t.resolverCodigo('612 123 4567'), null);
  assert.equal(t.resolverCodigo(''), null);
  assert.equal(t.resolverCodigo('+'), null);
  assert.equal(t.resolverCodigo('+999 123'), null);
  assert.equal(t.resolverCodigo('+0 123'), null);
});

test('compactar: vacio mientras no haya digitos, el pais solo no cuenta', () => {
  assert.equal(t.compactar('52', ''), '');
  assert.equal(t.compactar('52', '   '), '');
  assert.equal(t.compactar('52', '()-'), '');
});

test('compactar: arma +codigo+digitos y conserva el cero inicial', () => {
  assert.equal(t.compactar('52', '612 123 4567'), '+526121234567');
  assert.equal(t.compactar('52', '(612) 123-4567'), '+526121234567');
  assert.equal(t.compactar('44', '07911 123456'), '+4407911123456');
});

test('compactar: letras se descartan, extension se corta, digitos no ASCII pasan a ASCII', () => {
  assert.equal(t.compactar('52', '612abc123'), '+52612123');
  assert.equal(t.compactar('52', '612 123 4567 ext. 12'), '+526121234567');
  assert.equal(t.compactar('52', '612 123 4567 x12'), '+526121234567');
  assert.equal(t.compactar('52', '٦١٢١٢٣٤٥٦٧'), '+526121234567');
});

test('compactar: nunca pasa de 15 digitos ni de 16 caracteres', () => {
  const largo = t.compactar('52', '1234567890123456789012345');
  assert.equal(largo, '+521234567890123');
  assert.ok(largo.length <= 16);
  assert.equal(t.compactar('1', '2'.repeat(40)).length, 16);
  assert.equal(t.compactar('376', '3'.repeat(40)).length, 16);
});

test('aE164 canoniza lo que la biblioteca reconoce', () => {
  assert.equal(t.aE164('+526121234567'), '+526121234567');
  assert.equal(t.aE164('+52 1 612 123 4567'), '+526121234567');
  assert.equal(t.aE164('(612) 123-4567'), '+526121234567');
  assert.equal(t.aE164('+52 044 612 123 4567'), '+526121234567');
  assert.equal(t.aE164('+4407911123456'), '+447911123456');
  assert.equal(t.aE164('+52 612 123 4567 ext. 12'), '+526121234567');
  assert.equal(t.aE164('0034 612 34 56 78'), '+34612345678');
  assert.equal(t.aE164('+376 312 345'), '+376312345');
});

test('aE164 devuelve null cuando no hay un numero posible', () => {
  for (const v of ['', '+52', '+52 612', '+999 123 456', 'asdf', '+52 612 123 4567 890 123']) {
    assert.equal(t.aE164(v), null, JSON.stringify(v));
  }
});

test('telefonoParaEnviar: E.164 si parsea', () => {
  assert.equal(t.telefonoParaEnviar('+52 1 612 123 4567'), '+526121234567');
  assert.equal(t.telefonoParaEnviar('612 123 4567'), '+526121234567');
});

test('telefonoParaEnviar: si no parsea, el texto recortado tal cual (nunca vacia ni inventa)', () => {
  assert.equal(t.telefonoParaEnviar('  +52 612  '), '+52 612');
  assert.equal(t.telefonoParaEnviar(' asdf '), 'asdf');
  assert.equal(t.telefonoParaEnviar(''), '');
  assert.equal(t.telefonoParaEnviar('+999 123 456'), '+999 123 456');
});

test('restaurarTelefono: formatos viejos pasan al compacto', () => {
  assert.equal(t.restaurarTelefono('612 123 4567'), '+526121234567');
  assert.equal(t.restaurarTelefono('+52 1 612 123 4567'), '+526121234567');
  assert.equal(t.restaurarTelefono('(612) 123-4567'), '+526121234567');
  assert.equal(t.restaurarTelefono('+526121234567'), '+526121234567');
  assert.equal(t.restaurarTelefono('0052 612 123 4567'), '+526121234567');
  assert.equal(t.restaurarTelefono('+44 07911 123456'), '+447911123456');
});

test('restaurarTelefono: jamas borra lo que habia', () => {
  assert.equal(t.restaurarTelefono('asdf'), 'asdf');
  assert.equal(t.restaurarTelefono('  asdf  '), 'asdf');
  assert.equal(t.restaurarTelefono('+999 123 456'), '+999 123 456');
  assert.equal(t.restaurarTelefono('+52 612 123 4567 890 123'), '+52 612 123 4567 890 123');
  // incompleto: queda visible con Mexico para que el error de siempre lo explique
  assert.equal(t.restaurarTelefono('12345'), '+5212345');
});

test('restaurarTelefono: vacio sigue vacio', () => {
  assert.equal(t.restaurarTelefono(''), '');
  assert.equal(t.restaurarTelefono('   '), '');
  assert.equal(t.restaurarTelefono('+'), '');
});

test('restaurarTelefono: nunca pasa de 16 caracteres cuando devuelve compacto', () => {
  for (const v of ['612 123 4567', '+52 1 612 123 4567', '12345', '+49 1234567890123']) {
    const r = t.restaurarTelefono(v);
    assert.ok(r.length <= 16, v + ' -> ' + r);
  }
});

test('formatearTelefono: numero internacional con pais', () => {
  assert.deepEqual(t.formatearTelefono('+526121234567'), { texto: '+52 612 123 4567', codigo: '52', iso: 'MX' });
  assert.deepEqual(t.formatearTelefono('612 123 4567'), { texto: '+52 612 123 4567', codigo: '52', iso: 'MX' });
  assert.deepEqual(t.formatearTelefono('+52 1 612 123 4567'), { texto: '+52 612 123 4567', codigo: '52', iso: 'MX' });
  assert.deepEqual(t.formatearTelefono('+34612345678'), { texto: '+34 612 34 56 78', codigo: '34', iso: 'ES' });
  assert.deepEqual(t.formatearTelefono('+376312345'), { texto: '+376 312 345', codigo: '376', iso: 'AD' });
});

test('formatearTelefono: respeta el pais pedido si comparte codigo', () => {
  assert.equal(t.formatearTelefono('+447911123456', 'GB').iso, 'GB');
  assert.equal(t.formatearTelefono('+447911123456').iso, 'GG');
  // un pais con otro codigo se ignora
  assert.equal(t.formatearTelefono('+526121234567', 'US').iso, 'MX');
});

test('formatearTelefono: null si no hay numero posible (se muestra tal cual)', () => {
  for (const v of ['', 'asdf', '+52 612', '+999 123 456', '+52 612 123 4567 890 123']) {
    assert.equal(t.formatearTelefono(v), null, JSON.stringify(v));
  }
});

test('formatearTelefono: sin extension', () => {
  assert.equal(t.formatearTelefono('+52 612 123 4567 ext. 12').texto, '+52 612 123 4567');
});

test('si parsePhoneNumberFromString lanza, nunca bloquea una venta', () => {
  const rota = cargarConBiblioteca({ parsePhoneNumberFromString: lanza });
  assert.equal(rota.evaluar('+526121234'), 'ok'); // 9 digitos: pasa por el respaldo de 7 a 15
  assert.equal(rota.evaluar('612 123 4567'), 'ok');
  assert.equal(rota.evaluar('+52 123'), 'incompleto'); // 5 digitos
  assert.equal(rota.evaluar('+52 61212345678901'), 'incompleto'); // 16 digitos
  assert.equal(rota.evaluar(''), 'vacio');
  assert.equal(rota.aE164('+526121234567'), null);
  assert.equal(rota.telefonoParaEnviar('  +526121234567 '), '+526121234567');
  assert.equal(rota.formatearTelefono('+526121234567'), null);
  assert.equal(rota.restaurarTelefono('(612) 123-4567'), '+526121234567');
  assert.equal(rota.restaurarTelefono('asdf'), 'asdf');
});

test('si getCountries lanza, el codigo no se puede verificar pero tampoco bloquea', () => {
  const rota = cargarConBiblioteca({ getCountries: lanza });
  assert.equal(rota.evaluar('+999 123 456'), 'ok'); // sin tabla de codigos solo se cuenta el largo
  assert.equal(rota.evaluar('+52 123'), 'incompleto');
  assert.equal(rota.resolverCodigo('+52 612 123 4567'), null);
  assert.equal(rota.telefonoParaEnviar('+999 123 456'), '+999 123 456');
});

test('si getCountryCallingCode lanza, tampoco bloquea', () => {
  const rota = cargarConBiblioteca({ getCountryCallingCode: lanza });
  assert.equal(rota.evaluar('+526121234567'), 'ok');
});

test('cualquier entrada hostil produce un resultado sin lanzar', () => {
  const hostiles = ['\u0000', '+'.repeat(500), '9'.repeat(5000), '+52' + ' '.repeat(2000) + '1', '‮+52', '<script>', '０１２'];
  for (const v of hostiles) {
    assert.ok(['vacio', 'ok', 'incompleto', 'codigo-desconocido'].includes(t.evaluar(v)), JSON.stringify(v).slice(0, 20));
    assert.equal(typeof t.telefonoParaEnviar(v), 'string');
    assert.equal(typeof t.restaurarTelefono(v), 'string');
    t.formatearTelefono(v);
    t.aE164(v);
  }
});
