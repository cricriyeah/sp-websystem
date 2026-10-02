# Tipo de cambio por sede — un solo precio en MXN, USD calculado

Rama `feat/checkout-unificado`. Va ANTES de `2026-10-02-normalizar-precios-servicio-paquete.md`: así el paquete nace sin campos USD.

## Decisiones (confirmadas por el dueño, 2026-10-02)

1. El tipo de cambio vive en la **Sede** (`Sede.tipo_cambio_usd`: pesos por 1 USD), editable en el admin. Cada empresa cobra directo, así que no hay un valor global en código.
2. Se **congela** en la reserva/orden al crearla. Si el dueño cambia el tipo de cambio a mitad de un pago, el monto de Stripe no se mueve.
3. **Redondeo:** cada precio individual (base, extra, tarifa, personalización, mínimo de promoción) se convierte a USD **hacia arriba al dólar entero**. Todo lo que se suma después (totales, reparto entre empresas) ya está en dólares enteros, así que las líneas siempre cuadran con el total. El anticipo (30 %) puede dar centavos, como hoy.
4. **Sin precio USD manual** en ningún modelo. Desaparecen todas las columnas `*_usd`.

**Reversión de una decisión previa:** `docs/contexto-negocio.md` (líneas ~168-169) dice que pesos y dólares son dos precios fijados a mano y que el sistema no aplica tipo de cambio; el comentario de `fleet/models.py:112-114` también. Se reescriben en la tarea 7.

## Modelo

- `Sede.tipo_cambio_usd`: `DecimalField(max_digits=8, decimal_places=4)`, obligatorio, > 0. Valor inicial de migración: `18.0000` (demo; el dueño pone el real).
- `Reserva.tipo_cambio` y `Orden.tipo_cambio` (nulo si la moneda es MXN): el valor de la sede al crearse.
- Función única `apps/payments/moneda.py::convertir(monto_mxn, moneda, tipo_cambio)`: MXN devuelve el monto sin cambios; USD devuelve `ceil(monto_mxn / tipo_cambio)` como `Decimal` entero con 2 decimales. `None` solo si el monto es `None`.
- Todos los `precio_en(moneda)`, `persona_extra_en`, `monto_minimo_en`, `precio_total_en`, tarifa de transporte, etc. pasan a recibir el tipo de cambio y llamar a `convertir`. Se acabó el "no hay precio en USD" (503/400 de `payments/views.py:76,784`).

## Inventario a migrar (grep de la tarea 1, fuera de migraciones y tests)

Referencias a `*_usd` en el backend: `fleet/models.py` (21), `seed_local_demo.py` (13), `seed_catalogo_real.py` (7), `fleet/admin.py` (7), `apps/testing.py` (4), `fleet/serializers.py` (4), `payments/estrategias_precio.py` (2), y una cada una en `fleet/views.py`, `fleet/tarifa_transporte.py` y `seed_extras.py`. 13 archivos de test las usan.

Los puntos de entrada reales son los métodos `*_en(moneda)`: `fleet/models.py` líneas 60 (personalización), 152 (`monto_minimo_en`, promoción), 345 y 349 (Servicio), 514 (tarifa), 703 y 707 (Paquete) y `estrategias_precio.py:198`. Sus llamadores: `payments/pricing.py` (5), `payments/views.py` (4), `bookings/models.py` (1, promoción), `payments/extras.py` (1), `estrategias_precio.py` (1). Convertir esos métodos cubre casi todo; `payments/views.py` y `bookings/models.py` no mencionan `*_usd` directamente.

Frontend (13 archivos): `api.ts`, `pedido-paquete.ts`, `personalizaciones.ts`, `pricing-paquete.ts`, `tarifa-transporte.ts`, `checkout-view.tsx`, `grupo-servicio.tsx`, `pedido-paquete.tsx`, `selector-experiencia.tsx`, `servicios-sueltos-section.tsx`, `traslado-view.tsx`, `servicio/[empresa]/[servicio]/page.tsx`.

## Tareas (TDD; cada commit deja la suite verde)

1. **HECHA — `convertir` + `Sede.tipo_cambio_usd`.** Tests: MXN sin cambio, USD hacia arriba (`29.41 -> 30`, exacto no sube, `None`), tipo de cambio inválido (0, negativo). Migración con RLS correcto (`Sede` y las tablas tocadas; usar `alcance_operador_migracion` si la migración lee o escribe datos). Grep completo del inventario.
2. **Congelar.** `Reserva.tipo_cambio` y `Orden.tipo_cambio`: se llenan al crear si `moneda='USD'`; cobros posteriores (`views.py:74`, `~821`) usan el valor guardado, nunca el actual de la sede. Tests: cambiar el tipo de cambio de la sede después de crear no cambia el monto; reserva MXN lo deja nulo.
3. **Consumidores del backend** (en este orden, un commit por grupo, las columnas viejas siguen en la BD pero se ignoran): Servicio/estrategias de precio, Paquete (`precio_total_en`) y validación contra tarifa de transporte, personalizaciones, tarifas de transporte, promoción (`monto_minimo` convertido con la misma función). Cada test que fijaba un precio USD a mano pasa a fijar el tipo de cambio y esperar el valor convertido.
4. **API y admin.** Los serializadores dejan de exponer `*_usd` y exponen `tipo_cambio_usd` de la sede; admin sin campos USD, con ayuda en `Sede`.
5. **Seeds** sin `*_usd`.
6. **Migración final** que elimina todas las columnas `*_usd`. Los precios USD de la base local se pierden (son demo; sin lanzar). Test de migración en Postgres.
7. **Documentación:** reescribir `docs/contexto-negocio.md` (pesos y dólares: un solo precio en MXN, USD derivado por tipo de cambio de la sede, redondeo hacia arriba al dólar, congelado en la reserva) y el comentario de `fleet/models.py`.
8. **Gate backend:** SQLite completa y Postgres completa (`config.settings.ci`, `DB_PORT=5433`, `DB_USER=ci_rls`, `DB_PASSWORD=ci_rls_password_local`, contenedor `psd-pg`).
9. **Frontend (regla dura: explicar y esperar luz verde antes de tocar UI).** `lib/moneda.ts::aMoneda(mxn, moneda, tipoCambio)` espejo exacto de `convertir`; los 13 archivos dejan de leer `*_usd`. Paridad con el backend por un fixture JSON compartido (`monto, tipo_cambio, esperado`) leído por pytest y vitest. Verificación con tsc/eslint/build/tests; sin abrir Chrome.

## Riesgos

- **Precio mostrado vs. cobrado:** el frontend convierte con el tipo de cambio de la sede al cargar la página; el backend congela al crear la reserva. Si el dueño lo cambia entre ambos momentos, el total puede diferir. El checkout muestra el total que devuelve el backend al crear la reserva/orden antes de pedir tarjeta.
- Redondear cada precio hacia arriba hace el USD ligeramente más caro que la conversión exacta (hasta 1 USD por línea). Es la política elegida; se documenta en `contexto-negocio.md`.
- Pérdida de precios USD manuales en la base local: aceptable, sin lanzar.
