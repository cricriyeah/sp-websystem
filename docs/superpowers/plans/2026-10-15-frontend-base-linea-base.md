# Línea base de carga — frontend (antes de la optimización)

Medido el 2026-10-17 sobre `qa/checkout-unificado` (HEAD 06d35c3f) con `node scripts/medir-peso.cjs` tras `npm run build`. Suma los chunks JS que el HTML de cada ruta pide (los `dynamic()` no entran). API no disponible: las páginas pintan su estado vacío.

| Ruta | Chunks JS | Crudo (KB) | Gzip (KB) |
|---|---|---|---|
| /es | 10 | 780.9 | 244.6 |
| /es/sede/la-paz | 10 | 807.1 | 251.7 |
| /es/servicio/sal-y-sol/pesca-deportiva | 9 | 770.9 | 241.3 |
| /es/reservar | 13 | 1013.4 | 311.6 |
| /es/traslados | 12 | 947.9 | 292.0 |

## Recursos estáticos

- `public/videos`: 84 MB (`videohero.webm`, 87 608 929 bytes)
- `public/photos`: 2,0 MB
- Diccionarios: `es.json` 64 298 bytes, `en.json` 60 900 bytes

## Registro de cambios

(se anota aquí cada medición posterior: 1.1, 1.2b, 1.5, 1.8, 5.5)
