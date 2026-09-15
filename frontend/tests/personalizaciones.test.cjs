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
  precio_usd: null,
};

test('recomendada removible y cantidad efectiva', () => {
  assert.deepEqual(h.seleccionInicial([licencia]), [{ id: 7, cantidad: 1 }]);
  assert.equal(h.totalPersonalizaciones([licencia], [], 5, 'MXN'), 0);
  assert.equal(h.totalPersonalizaciones([licencia], [{ id: 7, cantidad: 2 }], 5, 'MXN'), 900);
  assert.equal(h.totalPersonalizaciones([licencia], [{ id: 7 }], 5, 'USD'), null);
});

test('input número cero, vacío y no finito', () => {
  const p = { ...licencia, tipo_interaccion: 'input_numero', obligatorio: true };
  assert.deepEqual(h.erroresPersonalizaciones([p], [{ id: 7, respuesta: '0' }]), {});
  assert.deepEqual(h.erroresPersonalizaciones([p], []), { 7: 'required' });
  assert.deepEqual(h.erroresPersonalizaciones([p], [{ id: 7, respuesta: 'Infinity' }]), { 7: 'number' });
});

test('input gratis aunque payload traiga cantidad y precio USD ausente', () => {
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
    precio_usd: null,
  };
  assert.equal(
    h.totalPersonalizaciones([inputTexto], [{ id: 10, cantidad: 5, respuesta: 'Sin gluten' }], 5, 'USD'),
    0,
  );
  assert.equal(
    h.totalPersonalizaciones([inputTexto], [{ id: 10, cantidad: 5, respuesta: 'Sin gluten' }], 5, 'MXN'),
    0,
  );
});

test('calcularPrecioPaquete: ancla sin seleccion vs ancla + seleccion explicita', () => {
  const paqueteDummy = {
    id: 1,
    slug: 'paquete-pesca-playa',
    nombre: 'Paquete Pesca y Playa',
    precio_ancla: '6000.00',
    precio_ancla_usd: '300.00',
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

  // Moneda USD sin precio en personalización seleccionada: precioFinal y totalPersonalizaciones son null
  const resUsdSinPrecio = pp.calcularPrecioPaquete(paqueteDummy, [{ id: 7, cantidad: 2 }], 5, 'USD');
  assert.equal(resUsdSinPrecio.precioAncla, 300);
  assert.equal(resUsdSinPrecio.totalPersonalizaciones, null);
  assert.equal(resUsdSinPrecio.precioFinal, null);

  // Moneda USD sin precio_ancla_usd: precioFinal y precioAncla son null
  const paqueteSinUsd = { ...paqueteDummy, precio_ancla_usd: null };
  const resSinUsd = pp.calcularPrecioPaquete(paqueteSinUsd, [], 5, 'USD');
  assert.equal(resSinUsd.precioAncla, null);
  assert.equal(resSinUsd.precioFinal, null);
});
