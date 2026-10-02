# Paso E — correcciones de la revisión D

Fecha: 2026-10-01. Worktree: `.claude/worktrees/checkout-unificado`, rama `feat/checkout-unificado`.

## Punto de reanudación

Las Tasks 1–8 del cambio de salidas multidía ya estaban implementadas sin commit. E1 tenía la clave compartida por empresa y fecha, pero una prueba concurrente apuntaba a una referencia incorrecta; E2–E5 seguían pendientes. Conservé los cambios previos del árbol. No hice commits ni cambios en frontend.

## Correcciones realizadas

| Punto | Cambio |
|---|---|
| E1 | El candado de cupo serializa todos los servicios de mar de una empresa en la misma fecha y mantiene `servicio_id` en la firma. Reparé la prueba concurrente entre servicios y un import faltante en la prueba multidía del paso C. |
| E2 | `salidas_deseadas` calcula el calendario desde la reserva en memoria; `sincronizar_salidas` crea, mueve y borra filas idempotentemente. `Reserva.save()` lo aplica a reservas ocupantes de paquetes monoempresa multidía cuando no hay `update_fields`; la confirmación de pago reutiliza la misma función. Las canceladas conservan filas históricas y dejan de contar cupo. |
| E3 | Todos los paquetes toman primero los locks de mar en orden de fecha y después los de habitaciones. `aplicar_pago_exitoso` reintenta una vez la transacción completa si `OperationalError` proviene de SQLSTATE `40P01`. |
| E4 | Se rechaza una actividad multidía acompañada por otra actividad de mar en el mismo paquete. |
| E5 | `backend/CLAUDE.md` documenta las dos limitaciones de asignación de panga/capitán pedidas en el plan. |
| Revisión final | Se corrigieron dos riesgos adicionales de E2: al reprogramar, la validación de panga/capitán usa las fechas nuevas; al crear o reprogramar una reserva pagada, se bloquean todos los días de mar, se revalida el cupo y se guarda/sincroniza dentro de una transacción. |

## Archivos

Creado: `backend/apps/bookings/cupo/salidas.py`.

Modificados al continuar E: `backend/CLAUDE.md`, `backend/apps/bookings/cupo/confirmacion.py`, `backend/apps/bookings/models.py`, `backend/apps/bookings/tests_concurrencia.py`, `backend/apps/bookings/tests_paquete_estancia.py`, `backend/apps/bookings/tests_salidas.py`, `backend/apps/fleet/paquete_reglas.py`, `backend/apps/fleet/tests_paquete_reglas.py`, `backend/apps/payments/services.py` y `backend/apps/payments/tests.py`.

E1 ya había modificado `backend/apps/bookings/cupo/candado.py` y `backend/apps/bookings/tests_cupo_candado.py` antes de reanudar; verifiqué ambas. El resto de los cambios backend y frontend que muestra `git status` precedía esta continuación.

## Pruebas y adaptaciones

Las salidas literales de las suites, incluidas las dos corridas de Postgres y los ajustes intermedios, están en [2026-10-01-paso-e-pruebas.log](2026-10-01-paso-e-pruebas.log). La salida cruda de la última corrida Postgres también quedó en [2026-10-01-paso-e-postgres-final.raw.log](2026-10-01-paso-e-postgres-final.raw.log).

| Verificación final | Salida literal de cierre |
|---|---|
| SQLite: `manage.py test apps.bookings apps.payments apps.fleet --noinput` | `Ran 964 tests in 179.442s` / `OK (skipped=24)` |
| Postgres: dos pruebas de paquetes multidía y dos servicios distintos | `Ran 4 tests in 3.591s` / `OK` |
| Postgres: `manage.py test apps config --noinput` | `Ran 1115 tests in 548.272s` / `FAILED (failures=1)` |
| `git diff --check` | exit `0` |

Antes de las pruebas Postgres, la consulta del rol devolvió literalmente `ci_rls  | f` para `rolbypassrls`. El único fallo de la suite completa fue `apps.finance.tests.PanelPorPeriodoTests.test_una_etiqueta_y_un_dato_por_cada_dia_del_periodo`: `AssertionError: 1000.0 != 0`. Es el fallo conocido del día 1 de cada mes admitido en el preámbulo del plan. Ninguna prueba nueva ni el guardarraíl RLS falló. La suite completa no se declara verde.

Ciclos TDD observados, con líneas literales de cierre:

- E2 original: `Ran 4 tests in 0.166s` / `FAILED (failures=4)`; tras el arreglo, `Ran 19 tests in 0.697s` / `OK`.
- E3: `Ran 2 tests in 0.094s` / `FAILED (failures=1, errors=1)`; tras el arreglo, `Ran 2 tests in 0.119s` / `OK`.
- E4: `Ran 1 test in 0.002s` / `FAILED (failures=1)`; tras el arreglo, `Ran 15 tests in 0.001s` / `OK`.
- Revisión, fechas de panga: `Ran 1 test in 0.144s` / `FAILED (failures=1)`; tras el arreglo, `Ran 14 tests in 0.584s` / `OK`.
- Revisión, dos altas pagadas: `Ran 1 test in 0.394s` / `FAILED (failures=1)`; tras el arreglo, `Ran 1 test in 0.560s` / `OK` en Postgres.

Adaptaciones de pruebas existentes:

- `SalidasBase.reserva_con_salidas` dejó de insertar a mano filas para reservas pagadas porque `save()` ya las sincroniza. Mantiene la creación manual para la cancelada histórica y agrega una panga al fixture cuando falta, pues ahora el guardado pagado revalida cupo real. No se quitó ninguna aserción.
- La carrera multidía del paso C ahora sincroniza los hilos antes de la revalidación de `save()`, que es donde se toma el primer lock, en vez de esperar al lock posterior de confirmación. La primera adaptación causó `BrokenBarrierError`; el registro literal aparece en el log y la prueba final pasa.
- La prueba E1 intercepta `confirmacion.evaluar_cupo`; el nombre anterior no existía en ese método. También se añadió el import faltante de `confirmacion` en la prueba del paso C.

## Límites

No probé manualmente el formulario del admin ni hice despliegue. El flujo de `full_clean()`/`save()` que usa el admin se verificó por ORM y con una carrera real en Postgres. La asignación simultánea de panga/capitán sigue sin lock, tal como documenta E5.
