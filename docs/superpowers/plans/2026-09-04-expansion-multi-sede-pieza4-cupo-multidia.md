# Expansión multi-sede — Pieza 4: Estrategias de Cupo Multidía y Bajo Demanda (`PorNoche`, `BajoDemanda`, `ReservaOcupacion`) Implementation Plan

> **For agentic workers:** Implement this plan task-by-task. Each task must produce a single atomic commit with an explanatory commit message in Spanish and the required co-author line. All tests must be 100% green before and after each task.

**Goal:** Implementar el motor de cupo multidía para hospedaje (`PorNoche`) con traslapes semi-abiertos `[check-in, check-out)`, soporte de asignación de 1..N recursos a una reserva mediante el modelo `ReservaOcupacion` protegido con RLS en PostgreSQL, la estrategia `BajoDemanda` para servicios sin inventario rígido que se agote (chef, guías), y su integración con el modelo `Reserva` (`fecha_salida`). Todo manteniendo 100% de retrocompatibilidad con las reservas de pesca de 1 día de La Paz.

**Architecture:**
1. **Semántica de Hospedaje y Núcleo Compartido (ADR-003, Correcciones 6 y 7):**
   - El traslape de fechas para hospedaje es medio-abierto `[check-in, check-out)`: un check-out en la mañana y un check-in esa misma tarde no colisionan. Dos rangos traslapan si y solo si: `max(ini1, ini2) < min(fin1, fin2)`.
   - `PorNoche`: evalúa la disponibilidad de recursos (habitaciones/cabañas) para que al menos `cantidad_recursos` estén libres de forma continua durante toda la estadía.
   - `BajoDemanda`: para servicios sin inventario limitante que se agote de forma estricta (ej. chef privado, traslados especiales). Siempre disponible.
2. **Modelo de Ocupación `ReservaOcupacion` (`apps.bookings`):**
   - Modela qué `Recurso` físico ampara una `Reserva` en qué intervalo `[fecha_inicio, fecha_fin)`.
   - En paseos de 1 día: `fecha_inicio = fecha`, `fecha_fin = fecha + 1 día`.
   - En hospedaje: `fecha_inicio = check_in`, `fecha_fin = check_out`. Soporta 1..N asignaciones simultáneas por reserva (múltiples habitaciones en un solo pago).
   - Incluye `empresa` FK directa a `tenancy.Empresa` para aislamiento multi-tenant y RLS directo.
3. **Row Level Security (RLS) en Postgres:**
   - Tabla `bookings_reservaocupacion`: `ENABLE ROW LEVEL SECURITY` y `FORCE ROW LEVEL SECURITY`.
   - Política `FOR ALL` filtrando por `empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int OR current_setting('app.operador_plataforma', true) = 'on'`.
4. **Integración con `Reserva` y Retrocompatibilidad:**
   - Campo `fecha_salida` opcional en `Reserva` (null en paseos de 1 día).
   - `validar_cupo_diario` y las señales de confirmación delegan a la estrategia de cupo configurada en el `Servicio` de la reserva (o a `PorRecursoDia` si no tiene servicio).

**Tech Stack:** Django 6, Django REST Framework, PostgreSQL RLS / SQLite local.

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `backend/apps/bookings/cupo/nucleo.py` | Modificar | Función pura de traslape semi-abierto y cálculo de disponibilidad por rango. |
| `backend/apps/bookings/cupo/estrategias.py` | Modificar | Clases `PorNoche` y `BajoDemanda`, y extensión de `DemandaCupo`. |
| `backend/apps/bookings/cupo/registro.py` | Modificar | Registro de las estrategias `por_noche` y `bajo_demanda`. |
| `backend/apps/bookings/cupo/tests_cupo_multidia.py` | Crear | Pruebas unitarias puras de `PorNoche` y `BajoDemanda`. |
| `backend/apps/bookings/models.py` | Modificar | Campo `Reserva.fecha_salida`, modelo `ReservaOcupacion` y validaciones. |
| `backend/apps/bookings/migrations/0026_reserva_ocupacion.py` | Crear | Migración de esquema para `fecha_salida` y `ReservaOcupacion`. |
| `backend/apps/bookings/migrations/0027_rls_reservaocupacion.py` | Crear | Migración RLS de PostgreSQL para `bookings_reservaocupacion`. |
| `backend/apps/bookings/tests_ocupacion_rls.py` | Crear | Pruebas de aislamiento RLS en PostgreSQL para `ReservaOcupacion`. |
| `backend/apps/bookings/cupo/adaptador.py` | Modificar | Métodos para consultar recursos ocupados y libres por rango. |
| `backend/apps/bookings/admin.py` | Modificar | Registro de `ReservaOcupacionAdmin` e inline en `ReservaAdmin`. |

---

## Tareas Bite-Sized

### Bloque 1: Núcleo Puro de Cupo Multidía y Estrategias (`apps/bookings/cupo`)

- [x] **Task M1: Implementar traslape semi-abierto y estrategias `PorNoche` y `BajoDemanda`**
  - **Archivos:**
    - Modificar `backend/apps/bookings/cupo/nucleo.py`
    - Modificar `backend/apps/bookings/cupo/estrategias.py`
    - Modificar `backend/apps/bookings/cupo/registro.py`
    - Crear `backend/apps/bookings/cupo/tests_cupo_multidia.py`
  - **Descripción:**
    - Agregar `rango_traslapa(ini1, fin1, ini2, fin2) -> bool` con semántica semi-abierta `[ini, fin)`.
    - Extender `DemandaCupo` con `fecha_fin: date | None = None` y `cantidad_recursos: int = 1`.
    - Implementar `PorNoche(EstrategiaCupo)`: evalúa disponibilidad de habitaciones durante todo el rango.
    - Implementar `BajoDemanda(EstrategiaCupo)`: disponibilidad inmediata sin bloqueo de inventario rígido.
    - Registrar `por_noche` y `bajo_demanda` en `REGISTRO_ESTRATEGIAS`.
    - Pruebas unitarias puras exhaustivas.
  - **Test:** `python manage.py test apps.bookings.cupo.tests_cupo_multidia` (100% verde).
  - **Commit:** `feat(cupo): estrategias PorNoche y BajoDemanda con traslape semi-abierto`

### Bloque 2: Modelo `ReservaOcupacion` y extensión de `Reserva` (`apps/bookings`)

- [x] **Task M2: Crear modelo `ReservaOcupacion` y campo `fecha_salida` en `Reserva`**
  - **Archivos:**
    - Modificar `backend/apps/bookings/models.py`
    - Crear `backend/apps/bookings/migrations/0026_reserva_ocupacion.py`
  - **Descripción:**
    - En `Reserva`: agregar `fecha_salida = models.DateField(null=True, blank=True)`.
    - Crear `ReservaOcupacion`: `empresa` FK PROTECT, `reserva` FK CASCADE, `recurso` FK PROTECT, `fecha_inicio` DateField, `fecha_fin` DateField.
    - `clean()` valida consistencia de empresa, `fecha_inicio < fecha_fin`, y detecta traslapes de fechas con otras ocupaciones activas del mismo recurso.
    - Generar y correr migración `0026_reserva_ocupacion.py`.
  - **Test:** `python manage.py check` (0 issues).
  - **Commit:** `feat(bookings): modelo ReservaOcupacion y soporte de fecha_salida en Reserva`

### Bloque 3: Row Level Security (RLS) en Postgres para `ReservaOcupacion`

- [x] **Task M3: Migración RLS de Postgres para `bookings_reservaocupacion`**
  - **Archivos:**
    - Crear `backend/apps/bookings/migrations/0027_rls_reservaocupacion.py`
    - Crear `backend/apps/bookings/tests_ocupacion_rls.py`
  - **Descripción:**
    - En `0027_rls_reservaocupacion.py`:
      - `ALTER TABLE bookings_reservaocupacion ENABLE ROW LEVEL SECURITY;`
      - `ALTER TABLE bookings_reservaocupacion FORCE ROW LEVEL SECURITY;`
      - Crear política `tenancy_alcance` filtrando por `empresa_id`.
    - Pruebas de aislamiento en `tests_ocupacion_rls.py` (saltadas con `skipUnless` en SQLite).
  - **Test:** `python manage.py test apps.bookings.tests_ocupacion_rls` (100% verde).
  - **Commit:** `feat(bookings): politicas RLS de Postgres para ReservaOcupacion`

### Bloque 4: Adaptador y Gestión en Django Admin

- [x] **Task M4: Adaptador de base de datos para `PorNoche` y Django Admin**
  - **Archivos:**
    - Modificar `backend/apps/bookings/cupo/adaptador.py`
    - Modificar `backend/apps/bookings/admin.py`
  - **Descripción:**
    - En `adaptador.py`: implementar consulta eficiente de recursos ocupados en un rango de fechas `[check_in, check_out)`.
    - En `apps/bookings/admin.py`: registrar `ReservaOcupacionAdmin` e inline `ReservaOcupacionInline` en `ReservaAdmin` con `EmpresaScopedAdminMixin`.
  - **Test:** `python manage.py test apps.bookings` (100% verde).
  - **Commit:** `feat(bookings): adaptador de cupo multidia y administracion de ocupaciones`

### Bloque 5: Verificación Integral de No-Regresión

- [ ] **Task M5: Suite completa de pruebas de backend (verificación integral)**
  - **Archivos:**
    - Ninguno (solo verificación).
  - **Descripción:**
    - Ejecutar `python manage.py check` (0 issues).
    - Ejecutar `python manage.py test config apps` (todas las pruebas 100% verdes).
  - **Test:** `python manage.py test config apps` (100% verde, 0 errores, 0 fallos).
  - **Commit:** `test(cupo): suite integral de pruebas para pieza 4`
