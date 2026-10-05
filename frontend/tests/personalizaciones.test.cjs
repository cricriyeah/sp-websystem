/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const h = require(path.join(process.env.PERSONALIZACIONES_TEST_OUT, 'personalizaciones.js'));
const pp = require(path.join(process.env.PERSONALIZACIONES_TEST_OUT, 'pricing-paquete.js'));

const licencia = {
  id: 7,
  nombre: 'Licencia',
  tipo_interaccion: 'check',
  opciones_seleccion: [],
  aviso_reforzado: true,
  obligatorio: false,
  preseleccionado: true,
  cobrar_por_persona: true,
  cantidad_editable: true,
  precio: '450.00',
};

test('recomendada removible y cantidad efectiva', () => {
  assert.deepEqual(h.seleccionInicial([licencia]), [{ id: 7, cantidad: 1 }]);
  assert.equal(h.totalPersonalizaciones([licencia], [], 5, 'MXN', '18.0000'), 0);
  assert.equal(h.totalPersonalizaciones([licencia], [{ id: 7, cantidad: 2 }], 5, 'MXN', '18.0000'), 900);
  assert.equal(h.totalPersonalizaciones([licencia], [{ id: 7 }], 5, 'USD', '18.0000'), 25);
});

test('input número cero, vacío y no finito', () => {
  const p = { ...licencia, tipo_interaccion: 'input_numero', obligatorio: true };
  assert.deepEqual(h.erroresPersonalizaciones([p], [{ id: 7, respuesta: '0' }]), {});
  assert.deepEqual(h.erroresPersonalizaciones([p], []), { 7: 'required' });
  assert.deepEqual(h.erroresPersonalizaciones([p], [{ id: 7, respuesta: 'Infinity' }]), { 7: 'number' });
});

test('input gratis aunque payload traiga cantidad', () => {
  const inputTexto = {
    id: 10,
    nombre: 'Alergias o comentarios',
    tipo_interaccion: 'input_texto',
    opciones_seleccion: [],
    aviso_reforzado: false,
    obligatorio: false,
    preseleccionado: false,
    cobrar_por_persona: false,
    cantidad_editable: false,
    precio: '0.00',
  };
  assert.equal(
    h.totalPersonalizaciones([inputTexto], [{ id: 10, cantidad: 5, respuesta: 'Sin gluten' }], 5, 'USD', '18.0000'),
    0,
  );
  assert.equal(
    h.totalPersonalizaciones([inputTexto], [{ id: 10, cantidad: 5, respuesta: 'Sin gluten' }], 5, 'MXN', '18.0000'),
    0,
  );
});

test('calcularPrecioPaquete: ancla sin seleccion vs ancla + seleccion explicita', () => {
  const paqueteDummy = {
    id: 1,
    slug: 'paquete-pesca-playa',
    nombre: 'Paquete Pesca y Playa',
    precio_ancla: '6000.00',
    tipo_cambio_usd: '18.0000', estrategia_precio: 'por_grupo',
    personas_precio_base: 2, precio_persona_extra: '0.00',
    servicios_asociados: [
      {
        servicio: {
          id: 1,
          nombre: 'Embarcacion',
          activo: true,
          personalizaciones: [licencia],
        },
      },
    ],
  };

  // Sin selección: solo ancla
  const resSinSeleccion = pp.calcularPrecioPaquete(paqueteDummy, [], 5, 'MXN');
  assert.equal(resSinSeleccion.precioAncla, 6000);
  assert.equal(resSinSeleccion.totalPersonalizaciones, 0);
  assert.equal(resSinSeleccion.precioFinal, 6000);

  // Con selección explícita: ancla + cargo
  const resConSeleccion = pp.calcularPrecioPaquete(paqueteDummy, [{ id: 7, cantidad: 2 }], 5, 'MXN');
  assert.equal(resConSeleccion.precioAncla, 6000);
  assert.equal(resConSeleccion.totalPersonalizaciones, 900);
  assert.equal(resConSeleccion.precioFinal, 6900);

  // Base 6000/18 -> 334 USD, licencia 450/18 -> 25 USD cada una.
  const resUsd = pp.calcularPrecioPaquete(paqueteDummy, [{ id: 7, cantidad: 2 }], 5, 'USD');
  assert.equal(resUsd.precioAncla, 334);
  assert.equal(resUsd.totalPersonalizaciones, 50);
  assert.equal(resUsd.precioFinal, 384);

  const sinBase = { ...paqueteDummy, precio_ancla: null };
  assert.equal(pp.calcularPrecioPaquete(sinBase, [], 5, 'USD').precioFinal, null);
});

test('separa obligatorias de opcionales conservando el orden', () => {
  const a = { id: 1, obligatorio: false };
  const b = { id: 2, obligatorio: true };
  const c = { id: 3, obligatorio: false };
  const d = { id: 4, obligatorio: true };
  const { obligatorias, opcionales } = h.separarPersonalizaciones([a, b, c, d]);
  assert.deepEqual(obligatorias.map((x) => x.id), [2, 4]);
  assert.deepEqual(opcionales.map((x) => x.id), [1, 3]);
});

test('sin personalizaciones devuelve dos listas vacías', () => {
  assert.deepEqual(h.separarPersonalizaciones([]), { obligatorias: [], opcionales: [] });
});
