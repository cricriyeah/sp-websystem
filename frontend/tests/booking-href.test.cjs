/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const h = require(path.join(process.env.BOOKING_HREF_TEST_OUT, 'lib/booking-href.js'));

function paqueteBase(overrides = {}) {
  return {
    id: 1, sede: 'La Paz', sede_slug: 'la-paz',
    empresa_lider: 'Sal y Sol', empresa_lider_slug: 'sal-y-sol',
    nombre: 'Brunch y pesca', slug: 'brunch-y-pesca', descripcion: '',
    precio_ancla: '3000', precio_ancla_usd: null, regla_precio: 'fijo', activo: true,
    servicios_asociados: [
      { id: 1, servicio_id: 1, orden: 1, servicio: { id: 1, empresa_slug: 'sal-y-sol', nombre: 'Pesca', slug: 'pesca-deportiva', tipo_servicio: 'pesca', estrategia_cupo: 'x', estrategia_precio: 'x', modo_ocupacion: 'x', precio_base: '0', precio_base_usd: null, precio_persona_extra: '0', precio_persona_extra_usd: null, personas_incluidas: 1, descripcion: '', activo: true, personalizaciones: [] } },
    ],
    ...overrides,
  };
}

test('un paquete de una empresa y uno de dos van a la misma ruta y sin paquete_empresa', () => {
  const una = h.hrefPaquete(paqueteBase(), 'es', 'MXN');
  const cruza = paqueteBase({
    servicios_asociados: [
      { id: 1, servicio_id: 1, orden: 1, servicio: { ...paqueteBase().servicios_asociados[0].servicio, empresa_slug: 'sal-y-sol' } },
      { id: 2, servicio_id: 2, orden: 2, servicio: { ...paqueteBase().servicios_asociados[0].servicio, id: 2, empresa_slug: 'transporte-la-paz' } },
    ],
  });
  const dos = h.hrefPaquete(cruza, 'es', 'MXN');
  assert.equal(una, '/es/reservar?paquete=brunch-y-pesca&sede=la-paz&moneda=MXN');
  assert.equal(dos, una);
});

test('paquete sin sede_slug omite el parametro sede', () => {
  const href = h.hrefPaquete(paqueteBase({ sede_slug: '' }), 'en', 'USD');
  assert.equal(href, '/en/reservar?paquete=brunch-y-pesca&moneda=USD');
});

test('hrefServicio arma la URL de reserva de servicio suelto', () => {
  const servicio = {
    id: 5, empresa_slug: 'sal-y-sol', nombre: 'Pesca', slug: 'pesca-deportiva',
    tipo_servicio: 'pesca', estrategia_cupo: 'x', estrategia_precio: 'x', modo_ocupacion: 'x',
    precio_base: '0', precio_base_usd: null, precio_persona_extra: '0', precio_persona_extra_usd: null,
    personas_incluidas: 1, descripcion: '', activo: true, personalizaciones: [],
  };
  const href = h.hrefServicio(servicio, 'es', 'MXN');
  assert.equal(href, '/es/reservar?servicio=pesca-deportiva&empresa=sal-y-sol&moneda=MXN');
});
