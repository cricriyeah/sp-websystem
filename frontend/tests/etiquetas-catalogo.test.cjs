/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const e = require(path.join(process.env.ETIQUETAS_TEST_OUT, 'lib/etiquetas-catalogo.js'));

const servicio = (tipo_servicio, slug = 'x') => ({ slug, tipo_servicio });
const paquete = (...tipos) => ({ servicios_asociados: tipos.map((t, i) => ({ servicio: servicio(t, `s${i}`) })) });

test('actividadDe: pesca y paseo son mar; hospedaje, transporte y bajo demanda no tienen familia', () => {
  assert.equal(e.actividadDe(servicio('pesca')), 'mar');
  assert.equal(e.actividadDe(servicio('paseo')), 'mar');
  assert.equal(e.actividadDe(servicio('hospedaje')), null);
  assert.equal(e.actividadDe(servicio('transporte')), null);
  assert.equal(e.actividadDe(servicio('bajo_demanda')), null);
});

test('actividadDePaquete: la familia común, o null si difieren', () => {
  assert.equal(e.actividadDePaquete(paquete('pesca', 'paseo')), 'mar');
  assert.equal(e.actividadDePaquete(paquete('pesca', 'hospedaje')), null);
  assert.equal(e.actividadDePaquete(paquete()), null);
});

test('baseDeCobro: cada estrategia en es y en; según ruta va sin «desde»', () => {
  const casos = {
    por_persona: ['por persona', 'per person'],
    por_grupo: ['por grupo', 'per group'],
    por_noche: ['por noche', 'per night'],
    tarifa_fija: ['tarifa fija', 'flat rate'],
    por_ruta: ['según ruta', 'by route'],
  };
  for (const [estrategia, [es, en]] of Object.entries(casos)) {
    assert.deepEqual(e.baseDeCobro(estrategia, 'es'), { texto: es, conDesde: estrategia !== 'por_ruta' });
    assert.deepEqual(e.baseDeCobro(estrategia, 'en'), { texto: en, conDesde: estrategia !== 'por_ruta' });
  }
  assert.equal(e.baseDeCobro('desconocida', 'es'), null);
});

test('chipDeServicio: una palabra por tipo y el tono de su familia', () => {
  assert.deepEqual(e.chipDeServicio(servicio('pesca'), 'es'), { tipo: 'mar', texto: 'Pesca' });
  assert.deepEqual(e.chipDeServicio(servicio('paseo'), 'en'), { tipo: 'mar', texto: 'Tours' });
  assert.deepEqual(e.chipDeServicio(servicio('hospedaje'), 'es'), { tipo: 'neutro', icono: 'hospedaje', texto: 'Hospedaje' });
  assert.deepEqual(e.chipDeServicio(servicio('transporte'), 'en'), { tipo: 'neutro', icono: 'traslado', texto: 'Transfers' });
});

test('chipDePaquete: con familia común lleva su tono; sin ella, «Paquetes» neutro', () => {
  assert.deepEqual(e.chipDePaquete(paquete('pesca'), 'es'), { tipo: 'mar', texto: 'Paquetes' });
  assert.deepEqual(e.chipDePaquete(paquete('pesca', 'hospedaje'), 'en'), { tipo: 'neutro', icono: 'paquete', texto: 'Packages' });
});

test('chipsDeSede: hasta 3, en orden fijo Pesca, Paseos, Hospedaje, Traslados, Paquetes', () => {
  const chips = e.chipsDeSede(
    [servicio('transporte'), servicio('paseo'), servicio('hospedaje'), servicio('pesca'), servicio('paseo')],
    [paquete('pesca')],
    'es',
  );
  assert.deepEqual(chips.map((c) => c.texto), ['Pesca', 'Paseos', 'Hospedaje']);
  assert.deepEqual(e.chipsDeSede([], [paquete('pesca')], 'en').map((c) => c.texto), ['Packages']);
});

test('tarjetasConFoto: solo si todas las sedes tienen foto propia', () => {
  const propia = { hero: { imagen: '/photos/la-paz.webp' } };
  const ilustracion = { hero: { imagen: '/ilustraciones/ventana.svg' } };
  const sin = { hero: { imagen: null } };
  assert.equal(e.tarjetasConFoto([propia, propia]), true);
  assert.equal(e.tarjetasConFoto([propia, ilustracion]), false);
  assert.equal(e.tarjetasConFoto([propia, sin]), false);
  assert.equal(e.tarjetasConFoto([]), false);
});

test('fotos: lado largo ≥ 800 para entrar, ≥ 1200 para el slot grande, ancho ≥ 1600 para héroe, galería con 3', () => {
  const f = (ancho, alto) => ({ ancho, alto });
  assert.deepEqual(e.fotosAptas([f(799, 600), f(600, 800), f(1086, 1448)]), [f(600, 800), f(1086, 1448)]);
  assert.equal(e.aptaParaSlotGrande(f(1448, 1086)), true);
  assert.equal(e.aptaParaSlotGrande(f(1199, 900)), false);
  assert.equal(e.aptaParaHeroe(f(1600, 900)), true);
  assert.equal(e.aptaParaHeroe(f(1448, 1086)), false);
  assert.equal(e.hayGaleria([f(800, 600), f(900, 600)]), false);
  assert.equal(e.hayGaleria([f(800, 600), f(900, 600), f(1000, 800), f(100, 100)]), true);
});

test('plantillaDeGrupo: sin celdas vacías para cada cantidad', () => {
  assert.deepEqual(e.plantillaDeGrupo(1), { columnas: 1, destacada: 'horizontal' });
  assert.deepEqual(e.plantillaDeGrupo(2), { columnas: 2, destacada: 'ninguna' });
  assert.deepEqual(e.plantillaDeGrupo(3), { columnas: 3, destacada: 'cuadrada' });
  assert.deepEqual(e.plantillaDeGrupo(4), { columnas: 2, destacada: 'ninguna' });
  assert.deepEqual(e.plantillaDeGrupo(5), { columnas: 3, destacada: 'ancha' });
  assert.deepEqual(e.plantillaDeGrupo(6), { columnas: 3, destacada: 'ninguna' });
  assert.deepEqual(e.plantillaDeGrupo(9), { columnas: 3, destacada: 'ninguna' });
});

test('grupoDeServicio: pesca, paseos (también bajo demanda) y estancia y traslados', () => {
  assert.equal(e.grupoDeServicio(servicio('pesca')), 'pesca');
  assert.equal(e.grupoDeServicio(servicio('paseo')), 'paseos');
  assert.equal(e.grupoDeServicio(servicio('bajo_demanda')), 'paseos');
  assert.equal(e.grupoDeServicio(servicio('hospedaje')), 'estancia');
  assert.equal(e.grupoDeServicio(servicio('transporte')), 'estancia');
});

test('grupoDePaquete: con un solo tipo de mar va con ese grupo; mezclado o con estancia, a paquetes', () => {
  assert.equal(e.grupoDePaquete(paquete('pesca', 'pesca')), 'pesca');
  assert.equal(e.grupoDePaquete(paquete('paseo')), 'paseos');
  assert.equal(e.grupoDePaquete(paquete('pesca', 'paseo')), 'paquetes');
  assert.equal(e.grupoDePaquete(paquete('pesca', 'hospedaje')), 'paquetes');
});

test('ORDEN_GRUPOS: paquetes primero', () => {
  assert.deepEqual(e.ORDEN_GRUPOS, ['paquetes', 'pesca', 'paseos', 'estancia']);
});

test('palabrasDeSede: tipos del catálogo en orden fijo, noches por duración y paquetes sin estancia', () => {
  const ventana = e.palabrasDeSede(
    [servicio('hospedaje'), servicio('pesca'), servicio('paseo'), servicio('bajo_demanda')],
    [{ ...paquete('pesca', 'hospedaje'), noches: 7 }, { ...paquete('pesca', 'hospedaje'), noches: 5 }, { ...paquete('pesca'), noches: 5 }],
    'es',
  );
  assert.deepEqual(ventana, ['Pesca', 'Paseos', 'Hospedaje', '5 noches', '7 noches']);
  const laPaz = e.palabrasDeSede([servicio('transporte'), servicio('pesca')], [{ ...paquete('pesca', 'transporte'), noches: null }], 'en');
  assert.deepEqual(laPaz, ['Fishing', 'Transfers', 'Packages']);
});

test('palabrasDeSede: sin catálogo no hay palabras', () => {
  assert.deepEqual(e.palabrasDeSede(null, null, 'es'), []);
  assert.deepEqual(e.palabrasDeSede([], [], 'es'), []);
});
