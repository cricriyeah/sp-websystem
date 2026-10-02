# Normalizar el cobro de servicio y paquete — plan (v2, con critic)

Rama `feat/checkout-unificado`. **Requisito previo:** `2026-10-02-tipo-de-cambio-por-sede.md` cerrado. Con él, todo precio es un solo monto en MXN y el USD se deriva; este plan no crea ningún campo `*_usd`.

Meta del dueño: un solo modelo de cobro que cubra todos los casos actuales sin campos especiales por servicio.

## Modelo

`total = base + max(0, personas − personas_base) × extra`, interpretado por una estrategia:

- `por_grupo`: `base` cubre `personas_base`; cada persona de más suma `extra`. Sin extra equivale a precio fijo.
- `por_persona`: `base` es el precio de UNA persona; `total = base × personas`. `clean()` fuerza `personas_precio_base=1` y `extra=0` para no dejar datos inertes.

Paquete restringe `choices` de `estrategia_precio` a `por_grupo` y `por_persona` (el enum del Servicio tiene 5; el admin no debe ofrecer `por_ruta` en un paquete).

**Fuera de alcance:** hospedaje por noche, transporte por ruta, reparto entre empresas (`monto_por_empresa`), extras/personalizaciones. `PaqueteServicio.personas_incluidas` sigue siendo el tope por componente; `personas_precio_base` es otra cosa (hasta cuántas personas cubre el precio).

## Decisiones de diseño

- **Cálculo único** `calcular_base(*, estrategia, base, personas, personas_base, extra)` (solo argumentos por nombre) en `payments/estrategias_precio.py`; `PorGrupo`/`PorPersona` del servicio y `Paquete.precio_total_en` lo llaman. Opera sobre MXN ya convertido por `convertir` cuando la moneda es USD (se convierte `base` y `extra` por separado, cada uno hacia arriba al dólar).
- **Personas cobradas, una sola definición.** Hoy hay dos: `Reserva.personas_del_pedido` (`bookings/models.py:634`, usado en `payments/views.py:74`) y `max(numero_personas)` de la orden (`views.py:~789-821`). Se crea `personas_cobradas(paquete, personas_por_servicio)` (mayor número entre sus servicios) y ambas vías la usan. Test: el mismo pedido por reserva suelta y por orden da el mismo total con `por_grupo` + extra y n > `personas_precio_base`.
- **Campos nuevos de `Paquete`:** `estrategia_precio` (default `por_grupo`), `personas_precio_base` (≥ 1), `precio_persona_extra` (≥ 0, MXN). Sale `precio_por_persona`. `precio_ancla` pasa a llamarse conceptualmente "precio base"; el nombre del campo se conserva para no mover más de lo necesario.
- **Regla "actividad con todas las personas":** hoy depende de `precio_por_persona`. Pasa a `Paquete.precio_depende_de_personas` = estrategia `por_persona` o `precio_persona_extra > 0`.
- **Sin precio configurado:** `calcular_base` del paquete devuelve `None` solo si falta el precio base (se mantiene el contrato de `precio_total_en` y los 503/400 de las vistas). Con tipo de cambio por sede ya no existe el caso "falta el extra en USD".

## Migración de datos (sin cambiar ningún precio)

- `precio_por_persona=True` -> `por_persona`, base 1, extra 0.
- `precio_por_persona=False` -> `por_grupo`, `personas_precio_base = max(personas_incluidas de sus componentes, default 1)`, extra 0. El precio no cambia con cualquier base ≥ 1 mientras el extra sea 0; la base solo importa cuando se active un extra.
- **RLS (bloqueante del critic):** `fleet_paquete` tiene `FORCE ROW LEVEL SECURITY` (`0020_rls_paquetes.py`). El `RunPython` usa `alcance_operador_migracion` como la 0043; sin él, Postgres ve 0 filas y los paquetes quedan con defaults sin error. Test de migración sobre Postgres con un paquete por persona y otro fijo creados antes de migrar.
- **Reversa:** solo exacta con `extra = 0`. Si encuentra un paquete con `extra > 0` lanza error explícito, no convierte mal.
- Orden de operaciones: AddField nuevos -> RunPython -> (al final del plan) RemoveField de `precio_por_persona`.

## Paquete de La Paz (`pesca-traslado`)

Hoy aparece "por persona" porque la casilla está encendida en la base local (ningún código ni seed la enciende). Queda `por_grupo`, `personas_precio_base=3`, extra 500 MXN (demo, igual que la pesca de Sal y Sol), tope 5 (pesca 5, traslado 2). Se carga con un comando idempotente de seed, no a mano en la base.

## Tareas (TDD; cada commit deja la suite verde)

1. **Cálculo único.** Tests de `calcular_base` (por_grupo con/sin extra, por_persona, personas ≤ base, 1 persona, precio base `None`). `PorGrupo`/`PorPersona` del servicio delegan sin cambiar resultados (los tests existentes del servicio son la red).
2. **Campos nuevos + migración de datos** (sin quitar `precio_por_persona`). Tests de migración en ambos sentidos y RLS en Postgres; `clean()`: base ≥ 1, extra ≥ 0, `por_persona` fuerza 1/0, solo las dos estrategias.
3. **`Paquete.precio_total_en`** usa el cálculo único; `precio_depende_de_personas`; `personas_cobradas` única. Actualizar `tests_pricing_paquete.py`.
4. **Validación contra tarifa de transporte** (reemplaza `_errores_por_persona`, `fleet/models.py:~540-583`): para cada traslado y para m de 1 a `personas_incluidas` del traslado, `paquete.total(m) ≥ peor_tarifa(m)` (el traslado va con m ≤ n personas). Test explícito de `por_grupo` + extra con `base < tarifa(2)`. `monto_por_empresa` sigue lanzando `ValueError` con residuo negativo; el admin debe atraparlo antes.
5. **Reglas de pedido:** `bookings/serializers.py:~323` y `payments/views.py` (~74, ~726, ~821) pasan a `precio_depende_de_personas` y `personas_cobradas`. Tests: anticipo (30 %) sobre `base + extra`; reserva ya pagada + cambio de `extra` no la recalcula; una reserva pendiente sí se recalcula al cobrar (riesgo ya existente con el ancla, no se promete "monto congelado" salvo el tipo de cambio).
6. **API y admin:** `fleet/serializers.py:~88` y `admin.py:~166` exponen `estrategia_precio`, `personas_precio_base`, `precio_persona_extra`, `precio_depende_de_personas`; sale `precio_por_persona`. Admin con ayuda en español.
7. **Seeds y fixtures de test:** `seed_catalogo_real.py` (La Ventana a `por_persona`), `seed_local_demo.py`, `apps/testing.py:~197`, La Paz con el comando idempotente; buscar `precio_por_persona` en ~40 archivos de test y actualizarlos.
8. **Migración final:** RemoveField de `precio_por_persona`. Test de migración.
9. **Gate backend:** SQLite completa y Postgres completa (`config.settings.ci`, `DB_PORT=5433`, `DB_USER=ci_rls`, `DB_PASSWORD=ci_rls_password_local`, contenedor `psd-pg`).
10. **Frontend (regla dura: explicar y esperar luz verde antes de tocar UI).** No es un renombre: `calcularPedido` hoy multiplica ancla × personas y no conoce base ni extra. Archivos: `pedido-estado.ts:35`, `pedido-paquete.ts:56-63`, `pedido-paquete.tsx` (90, 91, 114, 222, 358, 424, 526, 538), `grupo-servicio.tsx` (21, 62, 66, 116), `api.ts:352`, y `lib/pricing-paquete.ts` (`calcularPrecioPaquete` no multiplica por personas y hoy ya no coincide con el backend: se alinea o se elimina si es código muerto; revisar `checkout-view.tsx` y `servicio/.../page.tsx`). El selector único de personas se activa con `precio_depende_de_personas`, y el total usa la fórmula nueva. Paridad con el backend por un fixture JSON compartido `(estrategia, base, personas_base, extra, n, esperado)` leído por pytest y vitest (incluye centavos, tipo de cambio y extra 0). Verificación con tsc/eslint/build/tests; sin abrir Chrome.

## Riesgos

- Backend y frontend deben dar el mismo total: lo cubre el fixture compartido.
- Editar `base` o `extra` cambia el monto de las reservas pendientes de pago (ya ocurre hoy con el ancla); no hay "monto congelado" salvo el tipo de cambio.
- Sin lanzar: no hay datos reales que preservar más allá de la base local.
