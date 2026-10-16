/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const s = require(path.join(process.env.SELECTOR_TEST_OUT, 'lib/selector-experiencia.js'));

const servicioPesca = { id: 1, empresa_slug: 'sal-y-sol', nombre: 'Pesca deportiva', slug: 'pesca-deportiva', tipo_servicio: 'pesca', estrategia_cupo: 'x', estrategia_precio: 'x', modo_ocupacion: 'x', precio_base: '0', tipo_cambio_usd: '18.0000', precio_persona_extra: '0',  personas_incluidas: 1, descripcion: '', activo: true, personalizaciones: [] };
const paqueteBrunch = { id: 2, sede: 'La Paz', sede_slug: 'la-paz', empresa_lider: 'Sal y Sol', empresa_lider_slug: 'sal-y-sol', nombre: 'Brunch y pesca', slug: 'brunch-y-pesca', descripcion: '', precio_ancla: '1', tipo_cambio_usd: '18.0000', estrategia_precio: 'por_grupo', personas_precio_base: 1, precio_persona_extra: '0.00', precio_depende_de_personas: false, regla_precio: 'fijo', activo: true, servicios_asociados: [] };

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
