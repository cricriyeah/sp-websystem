/* eslint-disable @typescript-eslint/no-require-imports */
/* Generate a local SVG from Natural Earth's public-domain 1:10m state boundaries.
 * Usage: node scripts/generate-baja-map.cjs path/to/ne_10m_admin_1_states_provinces.geojson
 * Source: https://github.com/nvkelso/natural-earth-vector
 */
const fs = require('node:fs');
const path = require('node:path');
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const states = data.features.filter(({ properties: p }) => p.adm0_a3 === 'MEX' && ['Baja California', 'Baja California Sur'].includes(p.name));
if (states.length !== 2) throw new Error('Both Baja California states are required');
// Equirectangular projection with longitude corrected at latitude 28 degrees.
// Used by the map markers too; north stays up, no stretching of the peninsula.
const project = ([lon, lat]) => [330 + (lon + 117.5) * 48 * Math.cos(28 * Math.PI / 180), 28 + (33 - lat) * 48];
const paths = states.map(({ geometry }) => {
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  return polygons.map(polygon => '<path d="' + polygon.map(ring => ring.map((point, i) => (i ? 'L' : 'M') + project(point).map(n => n.toFixed(2)).join(' ')).join('') + 'Z').join('') + '"/>').join('');
}).join('\n');
fs.writeFileSync(path.join(__dirname, '../public/ilustraciones/mapa-baja.svg'), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 560"><title>Península de Baja California</title><desc>Natural Earth, public domain. Geographic projection, north up.</desc><g fill="#fff" stroke="#a0a8c7" stroke-width="1.15" stroke-linejoin="round">${paths}</g></svg>\n`);
console.log('Generated Baja California SVG from two geographic boundaries.');
