/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const p = require(path.join(process.env.PROBLEMA_TEST_OUT, 'lib/problema-reserva.js'));

const textos = {
  sin_cupo: { titulo: 'Ya no hay lugar', cuerpo: 'Se conserva lo capturado.', accion: 'Elegir otra fecha' },
  tarjeta_rechazada: { titulo: 'Tarjeta rechazada', cuerpo: 'Sin cobro.', accion: 'Probar otra tarjeta' },
  apartado_vencido: { titulo: 'Venció', cuerpo: 'Sin cobro.', accion: 'Volver a apartar mi lugar' },
  red: { titulo: 'Sin conexión', cuerpo: 'Se conserva.', accion: 'Reintentar' },
  catalogo_caido: { titulo: 'No disponible', cuerpo: 'Intenta luego.', accion: 'Reintentar', whatsapp: 'Escribirnos por WhatsApp', volver: 'Volver' },
  dato_previo: { titulo: 'Falta un dato', cuerpo: 'Revisa {dato} en {paso}.', accion: 'Corregir {dato}' },
};
const TIPOS = ['sin_cupo', 'tarjeta_rechazada', 'apartado_vencido', 'red', 'catalogo_caido', 'dato_previo'];

test('cada clase de fallo cae en un tipo de problema', () => {
  assert.equal(p.tipoDeFallo('sin_cupo'), 'sin_cupo');
  assert.equal(p.tipoDeFallo('conexion'), 'red');
  assert.equal(p.tipoDeFallo('demasiados_intentos'), 'red');
  assert.equal(p.tipoDeFallo('no_disponible'), 'catalogo_caido');
  assert.equal(p.tipoDeFallo('desconocido'), 'red');
});

test('cada tipo trae una sola acción principal con etiqueta', () => {
  for (const tipo of TIPOS) {
    const pr = p.problemaDe(tipo, { dato: 'el correo', paso: 'Tus datos', tieneWhatsapp: true }, textos);
    assert.equal(pr.tipo, tipo);
    assert.ok(pr.queOcurrio.length > 0, tipo);
    assert.ok(pr.accionPrincipal.etiqueta.length > 0, tipo);
    assert.ok(pr.accionPrincipal.clave, tipo);
  }
});

test('sin cupo, tarjeta rechazada, apartado vencido y catálogo caído bloquean; red y dato previo no', () => {
  const bloquea = (t) => p.problemaDe(t, { tieneWhatsapp: false }, textos).bloquea;
  for (const t of ['sin_cupo', 'tarjeta_rechazada', 'apartado_vencido', 'catalogo_caido']) assert.equal(bloquea(t), true, t);
  for (const t of ['red', 'dato_previo']) assert.equal(bloquea(t), false, t);
});

test('el tono es aviso para cupo, apartado y dato, y error para tarjeta, red y catálogo', () => {
  const tono = (t) => p.problemaDe(t, { tieneWhatsapp: false }, textos).tono;
  for (const t of ['sin_cupo', 'apartado_vencido', 'dato_previo']) assert.equal(tono(t), 'aviso', t);
  for (const t of ['tarjeta_rechazada', 'red', 'catalogo_caido']) assert.equal(tono(t), 'error', t);
});

test('dato previo nombra el dato y el paso', () => {
  const pr = p.problemaDe('dato_previo', { dato: 'el correo', paso: 'Tus datos', tieneWhatsapp: false }, textos);
  assert.equal(pr.queSeConserva, 'Revisa el correo en Tus datos.');
  assert.equal(pr.accionPrincipal.etiqueta, 'Corregir el correo');
});

test('las líneas de dinero que manda quien llama van tal cual, antes que la acción', () => {
  const lineas = ['No se hizo ningún cobro.', 'Se libera la retención de Sal y Sol.'];
  const pr = p.problemaDe('tarjeta_rechazada', { lineasDinero: lineas, tieneWhatsapp: false }, textos);
  assert.deepEqual(pr.lineasDinero, lineas);
});

test('catálogo caído ofrece WhatsApp solo si hay número, y siempre volver', () => {
  const con = p.problemaDe('catalogo_caido', { tieneWhatsapp: true }, textos);
  assert.equal(con.accionPrincipal.clave, 'whatsapp');
  assert.equal(con.accionSecundaria.clave, 'volver');
  const sin = p.problemaDe('catalogo_caido', { tieneWhatsapp: false }, textos);
  assert.equal(sin.accionPrincipal.clave, 'reintentar');
  assert.equal(sin.accionSecundaria.clave, 'volver');
});

test('las acciones de cada tipo', () => {
  const clave = (t) => p.problemaDe(t, { tieneWhatsapp: false }, textos).accionPrincipal.clave;
  assert.equal(clave('sin_cupo'), 'elegir_fecha');
  assert.equal(clave('tarjeta_rechazada'), 'otra_tarjeta');
  assert.equal(clave('apartado_vencido'), 'reapartar');
  assert.equal(clave('red'), 'reintentar');
  assert.equal(clave('dato_previo'), 'corregir');
});
