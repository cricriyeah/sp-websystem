# Baja California map

The SVG uses the actual boundaries of Baja California and Baja California Sur,
including their islands, from Natural Earth 1:10m Admin 1.

- Source: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_1_states_provinces.geojson
- License: public domain, https://www.naturalearthdata.com/about/terms-of-use/
- Projection: equirectangular, longitude corrected at 28° north.
- Regenerate: `node scripts/generate-baja-map.cjs path/to/ne_10m_admin_1_states_provinces.geojson`

Destination markers represent towns, not meeting or departure points.
Puerto Chale location reference: https://mapcarta.com/20328502 (OpenStreetMap / GeoNames).
The map is local and requires neither an API key nor third-party map tiles.
