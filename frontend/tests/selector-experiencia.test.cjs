/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const s = require(path.join(process.env.SELECTOR_TEST_OUT, 'lib/selector-experiencia.js'));

const servicioPesca = { id: 1, empresa_slug: 'sal-y-sol', nombre: 'Pesca deportiva', slug: 'pesca-deportiva', tipo_servicio: 'pesca', estrategia_cupo: 'x', estrategia_precio: 'x', modo_ocupacion: 'x', precio_base: '0', precio_base_usd: null, precio_persona_extra: '0', precio_persona_extra_usd: null, personas_incluidas: 1, descripcion: '', activo: true, personalizaciones: [] };
const paqueteBrunch = { id: 2, sede: 'La Paz', sede_slug: 'la-paz', empresa_lider: 'Sal y Sol', empresa_lider_slug: 'sal-y-sol', nombre: 'Brunch y pesca', slug: 'brunch-y-pesca', descripcion: '', precio_ancla: '1', precio_ancla_usd: null, regla_precio: 'fijo', activo: true, servicios_asociados: [] };

test('resuelve el nombre desde el catalogo real, no desde el diccionario', () => {
  const destacadas = [{ tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true }];
  const chips = s.resolverChips(destacadas, [], [servicioPesca]);
  assert.equal(chips.length, 1);
  assert.equal(chips[0].nombre, 'Pesca deportiva');
});

test('entrada de destacadas sin contraparte en el catalogo se omite en silencio', () => {
  const destacadas = [{ tipo: 'servicio', slug: 'buceo', inlineable: false }];
  const chips = s.resolverChips(destacadas, [], [servicioPesca]);
  assert.deepEqual(chips, []);
});

test('servicio destacado respeta empresaSlug cuando dos empresas comparten slug', () => {
  const otraEmpresa = { ...servicioPesca, id: 8, empresa_slug: 'otro-operador', nombre: 'Pesca de otro operador' };
  const destacadas = [{ tipo: 'servicio', slug: 'pesca-deportiva', empresaSlug: 'sal-y-sol', inlineable: true }];
  const chips = s.resolverChips(destacadas, [], [otraEmpresa, servicioPesca]);
  assert.equal(chips.length, 1);
  assert.equal(chips[0].empresaSlug, 'sal-y-sol');
  assert.equal(chips[0].nombre, servicioPesca.nombre);
  assert.deepEqual(s.resolverChips(destacadas, [], [otraEmpresa]), []);
});

test('paquete destacado no lleva empresaSlug (no aplica la regla mecanica)', () => {
  const destacadas = [{ tipo: 'paquete', slug: 'brunch-y-pesca', inlineable: false }];
  const chips = s.resolverChips(destacadas, [paqueteBrunch], []);
  assert.equal(chips[0].empresaSlug, null);
});

test('regla mecanica: inline solo si sede=la-paz + servicio pesca-deportiva + empresa del .env', () => {
  const chip = { tipo: 'servicio', slug: 'pesca-deportiva', nombre: 'Pesca', empresaSlug: 'sal-y-sol' };
  assert.equal(s.esInlineable(chip, 'la-paz', 'sal-y-sol'), true);
  assert.equal(s.esInlineable(chip, 'los-cabos', 'sal-y-sol'), false, 'otra sede');
  assert.equal(s.esInlineable({ ...chip, slug: 'buceo' }, 'la-paz', 'sal-y-sol'), false, 'otro servicio');
  assert.equal(s.esInlineable({ ...chip, tipo: 'paquete' }, 'la-paz', 'sal-y-sol'), false, 'es paquete, no servicio');
  assert.equal(s.esInlineable({ ...chip, empresaSlug: 'otra-empresa' }, 'la-paz', 'sal-y-sol'), false, 'otra empresa');
});

test('inlineable: true del diccionario no basta si la condicion mecanica no se cumple', () => {
  // Simula el caso que el spec §7 quiere evitar: alguien marca inlineable:true
  // en el diccionario para un chip que no es el flujo heredado de pesca.
  const chipMalMarcado = { tipo: 'servicio', slug: 'buceo', nombre: 'Buceo', empresaSlug: 'sal-y-sol' };
  assert.equal(s.esInlineable(chipMalMarcado, 'la-paz', 'sal-y-sol'), false);
});
