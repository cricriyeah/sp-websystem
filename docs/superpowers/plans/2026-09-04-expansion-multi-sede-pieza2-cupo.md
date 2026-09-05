# Expansión multi-sede — Pieza 2: Abstracción de Estrategias de Cupo (`EstrategiaCupo`, `PorRecursoDia`) Implementation Plan

> **For agentic workers:** Implement this plan task-by-task. Each task must produce a single atomic commit with an explanatory commit message in Spanish and the required co-author line. All tests must be 100% green before and after each task.

**Goal:** Extraer y abstraer el motor de cupo actual de La Paz hacia la arquitectura tipada de estrategias definida en ADR-003, encapsulando la lógica pura en `EstrategiaCupo` y `PorRecursoDia`, soportando el eje `modo_ocupacion` (exclusivo vs compartido), re-llaveando el advisory lock de Postgres para multi-servicio/recurso, y conectando los consumidores existentes sin alterar en absoluto el comportamiento ni la correctitud del negocio de pesca.

**Architecture:**
1. **Núcleo puro (`apps/bookings/cupo/nucleo.py`):**
   - Funciones matemáticas/algorítmicas sin dependencia de base de datos (`caben`, `caben_compartido`, `motivo_sin_lugar`, `ocupacion_por_rango`).
   - Modo exclusivo: emparejamiento por tamaño de grupo contra capacidad individual de cada recurso (pesca, charters privados).
   - Modo compartido: suma acumulada de personas contra capacidad total del recurso (tours a playas/islas, transporte colectivo).
2. **Estrategias tipadas (`apps/bookings/cupo/estrategias.py`):**
   - Clase base abstracta / protocolo `EstrategiaCupo` con los métodos estándar: `evaluar()`, `validar()`.
   - Implementación de referencia `PorRecursoDia`: calcula disponibilidad y valida cupo en ventanas de 1 día completo, resolviendo por modo exclusivo o compartido.
3. **Advisory Lock de Postgres (`apps/bookings/cupo/candado.py`):**
   - `bloquear_cupo`: candado transaccional `pg_advisory_xact_lock(key1, key2)` derivado de `(empresa_id, hash(ambito, fecha))`, evitando contención entre servicios o empresas distintas en la misma fecha.
4. **Adaptador de datos (`apps/bookings/cupo/adaptador.py`):**
   - Adaptador delgado que extrae reservas, capacidades y topes de `CupoDiario` para alimentar a `PorRecursoDia` mediante consultas optimizadas por lotes.
5. **Registro y Retrocompatibilidad (`apps/bookings/cupo/registro.py` y `apps/bookings/models.py`):**
   - Registro de estrategias por tipo de servicio.
   - `apps/bookings/models.py` reexporta `caben`, `motivo_sin_lugar`, `evaluar_cupo`, `validar_cupo_diario`, etc., delegando limpiamente al nuevo módulo de cupo para cero breaking changes en vistas, serializers o comandos.

**Tech Stack:** Django 6, Postgres (Supabase) / SQLite en local, Python 3.14.

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `backend/apps/bookings/cupo/__init__.py` | Crear | Marcador de paquete y exportación de símbolos públicos. |
| `backend/apps/bookings/cupo/nucleo.py` | Crear | Núcleo de funciones puras: `caben`, `caben_compartido`, `motivo_sin_lugar`, `ocupacion_por_rango`, constantes de motivos. |
| `backend/apps/bookings/cupo/estrategias.py` | Crear | Protocolo `EstrategiaCupo`, enum `ModoOcupacion`, implementación `PorRecursoDia`, DTOs `DemandaCupo`, `ResultadoDisponibilidad`. |
| `backend/apps/bookings/cupo/candado.py` | Crear | `bloquear_cupo` con derivación segura de hash de clave de advisory lock por empresa y fecha/recurso. |
| `backend/apps/bookings/cupo/adaptador.py` | Crear | Adaptador de base de datos que resuelve la flota, reservas y topes de La Paz y los pasa a la estrategia. |
| `backend/apps/bookings/cupo/registro.py` | Crear | Registro centralizado `tipo_servicio -> EstrategiaCupo`. |
| `backend/apps/bookings/models.py` | Modificar | Reemplazar lógica inline de cupo por delegación a `apps.bookings.cupo`, manteniendo firmas idénticas. |
| `backend/apps/bookings/views.py` | Modificar | Asegurar que `CupoDisponibleView` use la interfaz de cupo escopeada. |
| `backend/apps/bookings/tests_cupo_nucleo.py` | Crear | Pruebas de funciones puras del algoritmo de cupo exclusivo y compartido. |
| `backend/apps/bookings/tests_cupo_estrategias.py` | Crear | Pruebas de las clases de estrategia y registro. |
| `backend/apps/bookings/tests_cupo_candado.py` | Crear | Pruebas del candado advisory lock. |
| `backend/apps/bookings/tests_cupo_adaptador.py` | Crear | Pruebas del adaptador con base de datos. |

---

## Tareas Bite-Sized

### Bloque 1: Núcleo Puro de Cupo (Sin Base de Datos)

- [x] **Task C1: Crear `apps/bookings/cupo/nucleo.py` y tests unitarios de funciones puras**
  - **Archivos:**
    - Crear `backend/apps/bookings/cupo/__init__.py`
    - Crear `backend/apps/bookings/cupo/nucleo.py`
    - Crear `backend/apps/bookings/tests_cupo_nucleo.py`
  - **Descripción:**
    - Mover/definir constantes `MOTIVO_LLENO = 'lleno'`, `MOTIVO_SIN_PANGA = 'sin_panga'`, `MOTIVO_SIN_LUGAR = 'sin_lugar'`.
    - Implementar `caben(grupos, capacidades)` (algoritmo exacto de pesca actual, emparejamiento de mayor a menor).
    - Implementar `caben_compartido(grupos, capacidad_maxima)` (suma de personas <= capacidad).
    - Implementar `motivo_sin_lugar(personas, grupos, capacidades, tope, modo='exclusivo')`: si `len(grupos) + 1 > tope` (o suma > tope en compartido), devuelve `MOTIVO_LLENO`; si no cabe, devuelve `MOTIVO_SIN_PANGA` o `MOTIVO_SIN_LUGAR`.
    - Implementar `ocupacion_por_rango(recursos, fechas, grupos_existentes_por_fecha, nueva_demanda, modo='exclusivo')`.
  - **Test:** `python manage.py test apps.bookings.tests_cupo_nucleo` (100% verde).
  - **Commit:** `feat(cupo): nucleo puro de cupo con soporte de modo exclusivo y compartido`

### Bloque 2: Abstracción de Estrategias y `PorRecursoDia`

- [x] **Task C2: Crear `apps/bookings/cupo/estrategias.py` con `EstrategiaCupo` y `PorRecursoDia`**
  - **Archivos:**
    - Crear `backend/apps/bookings/cupo/estrategias.py`
    - Modificar `backend/apps/bookings/cupo/__init__.py`
    - Crear `backend/apps/bookings/tests_cupo_estrategias.py`
  - **Descripción:**
    - Definir `ModoOcupacion(StrEnum)`: `EXCLUSIVO = 'exclusivo'`, `COMPARTIDO = 'compartido'`.
    - Definir dataclasses `DemandaCupo(fecha, personas, modo=ModoOcupacion.EXCLUSIVO)` y `ResultadoDisponibilidad(disponible, motivo=None)`.
    - Definir clase base abstracta `EstrategiaCupo(ABC)` con métodos:
      - `evaluar(demanda, recursos, ocupacion_actual, tope) -> ResultadoDisponibilidad`
      - `validar(demanda, recursos, ocupacion_actual, tope) -> raise ValidationError si no hay cupo`
    - Implementar `PorRecursoDia(EstrategiaCupo)`:
      - Implementa la evaluación de 1 día delegando en `motivo_sin_lugar` y `ocupacion_por_rango`.
  - **Test:** `python manage.py test apps.bookings.tests_cupo_estrategias` (100% verde).
  - **Commit:** `feat(cupo): abstraccion EstrategiaCupo e implementacion PorRecursoDia`

### Bloque 3: Advisory Lock Re-llaveado por Ámbito

- [x] **Task C3: Crear `apps/bookings/cupo/candado.py` con locking por ámbito y tests**
  - **Archivos:**
    - Crear `backend/apps/bookings/cupo/candado.py`
    - Crear `backend/apps/bookings/tests_cupo_candado.py`
  - **Descripción:**
    - Implementar `bloquear_cupo(empresa_id, fecha, ambito='pesca')`:
      - Deriva una clave secundaria usando un hash estable de 32 bits para `(ambito, fecha.toordinal())`.
      - En Postgres: `cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [empresa_id, clave_secundaria])`.
      - En SQLite: no-op seguro.
    - Mantener retrocompatibilidad de `bloquear_cupo_del_dia(empresa_id, fecha)` redirigiéndola a `bloquear_cupo(empresa_id, fecha, ambito='default')`.
  - **Test:** `python manage.py test apps.bookings.tests_cupo_candado` (100% verde).
  - **Commit:** `feat(cupo): advisory lock de postgres re-llaveado por empresa y ambito`

### Bloque 4: Adaptador ORM y Registro de Estrategias

- [x] **Task C4: Crear `apps/bookings/cupo/adaptador.py` y `apps/bookings/cupo/registro.py`**
  - **Archivos:**
    - Crear `backend/apps/bookings/cupo/adaptador.py`
    - Crear `backend/apps/bookings/cupo/registro.py`
    - Crear `backend/apps/bookings/tests_cupo_adaptador.py`
  - **Descripción:**
    - En `adaptador.py`:
      - `obtener_contexto_cupo(fecha, empresa)`: consulta reservas activas, capacidades de pangas activas y tope de `CupoDiario` para alimentar a la estrategia.
      - `obtener_contexto_rango(desde, hasta, empresa)`: optimización en 4 consultas para rangos (usada por `disponibilidad_por_fecha`).
    - En `registro.py`:
      - Diccionario / registro `REGISTRO_ESTRATEGIAS`.
      - Función `obtener_estrategia(tipo_servicio='pesca') -> EstrategiaCupo`.
      - Por defecto registra `'pesca' -> PorRecursoDia(modo=ModoOcupacion.EXCLUSIVO)` y `'paseo_compartido' -> PorRecursoDia(modo=ModoOcupacion.COMPARTIDO)`.
  - **Test:** `python manage.py test apps.bookings.tests_cupo_adaptador` (100% verde).
  - **Commit:** `feat(cupo): adaptador de base de datos y registro de estrategias de cupo`

### Bloque 5: Retrofit Transparente de `apps/bookings/models.py` y Consumidores

- [x] **Task C5: Integrar `apps.bookings.cupo` en `models.py`, `views.py` y comandos**
  - **Archivos:**
    - Modificar `backend/apps/bookings/models.py`
    - Modificar `backend/apps/bookings/views.py`
    - Modificar `backend/apps/bookings/management/commands/revisar_cupo.py`
  - **Descripción:**
    - En `apps/bookings/models.py`:
      - Re-exportar `caben`, `motivo_sin_lugar`, `MOTIVO_LLENO`, `MOTIVO_SIN_PANGA` desde `apps.bookings.cupo.nucleo`.
      - `evaluar_cupo` y `validar_cupo_diario` delegan en la estrategia `PorRecursoDia` a través de `adaptador.py`.
      - `disponibilidad_por_fecha` y `proxima_fecha_disponible` utilizan el contexto por rango del adaptador.
      - `bloquear_cupo_del_dia` delega en `candado.bloquear_cupo`.
    - En `views.py`:
      - `CupoDisponibleView` sigue respondiendo con el contrato JSON idéntico `{disponible: bool, motivo: str|None}`.
    - En `revisar_cupo.py`:
      - Mantiene su verificación sin cambio visible pero usando el motor desacoplado.
  - **Test:**
    - `python manage.py test apps.bookings.tests_cupo_rango apps.bookings.tests_concurrencia`
    - `python manage.py check` (0 issues).
  - **Commit:** `refactor(bookings): conecta modelos y vistas de reservas a la arquitectura de estrategias de cupo`

### Bloque 6: Verificación Integral de No-Regresión

- [x] **Task C6: Suite completa de pruebas de backend (verificación integral)**
  - **Archivos:**
    - Ninguno (solo verificación y documentación).
  - **Descripción:**
    - Ejecutar `python manage.py test config apps`.
    - Confirmar que todos los tests previos (567 tests) sigan pasando al 100% en verde sin regresiones, sumados a los nuevos tests de cupo.
  - **Test:** `python manage.py test config apps` (100% verde, 0 errores, 0 fallos).
  - **Commit:** `test(cupo): suite integral de pruebas para pieza 2 (estrategias de cupo)`
