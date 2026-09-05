# Expansión multi-sede — Pieza 3: Catálogo por capas y estrategias de precio (`Servicio`, `Recurso`, `Personalizacion`, `EstrategiaPrecio`) Implementation Plan

> **For agentic workers:** Implement this plan task-by-task. Each task must produce a single atomic commit with an explanatory commit message in Spanish and the required co-author line. All tests must be 100% green before and after each task.

**Goal:** Introducir el catálogo por capas (`Servicio`, `Recurso`, `Personalizacion`, `ServicioPersonalizacion`) en `apps.fleet`, desacoplando el precio del tour del singleton `Tarifa(pk=1)` mediante estrategias de precio tipadas en `apps/payments/pricing.py` (`PorPersona`, `PorGrupo`, `PorNoche`, `TarifaFija`), protegiendo las tablas nuevas con RLS en Postgres y asegurando retrocompatibilidad total con el checkout y reservas de Sal y Sol (La Paz).

**Architecture:**
1. **Estrategias de precio puras (`apps/payments/pricing.py` y `apps/payments/estrategias_precio.py`):**
   - Interfaz tipada `EstrategiaPrecio`: `precio_base(servicio, demanda, moneda) -> Decimal`.
   - Implementaciones:
     - `PorGrupo`: Precio plano por viaje/embarcación más recargo por personas extra arriba de `personas_incluidas` (fórmula actual de pesca deportiva).
     - `PorPersona`: Precio unitario multiplicado por cantidad de personas.
     - `TarifaFija`: Monto fijo plano independiente del tamaño del grupo.
     - `PorNoche`: Precio por noche multiplicado por número de noches (base para hospedaje).
   - Mantiene la garantía inquebrantable de `CLAUDE.md`: todo el dinero se calcula en un solo lugar con funciones puras que reciben primitivos y se congela al confirmar el pago en `CrearPagoView`.
2. **Modelos de catálogo por capas (`apps/fleet/models.py`):**
   - `Servicio`: Cuelga de `Empresa`, define la experiencia vendible (`tipo_servicio`, `estrategia_cupo`, `estrategia_precio`, `modo_ocupacion`, `precio_base`, `precio_base_usd`, etc.).
   - `Recurso`: Cuelga de `Empresa`, representa el activo físico reservable (`nombre`, `capacidad_maxima`, `activo`).
   - `Personalizacion`: Catálogo de extras/complementos reutilizables sin precio fijo a nivel global.
   - `ServicioPersonalizacion`: Asociación M2M entre `Servicio` y `Personalizacion` que define el precio en MXN y USD, obligatoriedad y preselección.
3. **Row Level Security (RLS) en Postgres:**
   - Políticas `FOR ALL` en `fleet_servicio`, `fleet_recurso` y `fleet_personalizacion` usando `empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int OR current_setting('app.operador_plataforma', true) = 'on'`.
   - Política referenciada vía `EXISTS` en `fleet_serviciopersonalizacion` vinculada al `servicio.empresa_id`.
4. **Migración de datos y compatibilidad de La Paz:**
   - Sembrado automático del servicio inicial "Pesca Deportiva" para Sal y Sol a partir de su `Tarifa` actual.
   - Puente transparente para que `Tarifa.de(empresa)` y `/api/<empresa_slug>/tarifa/` sigan funcionando consultando el servicio principal.
   - Nueva ruta `/api/<empresa_slug>/servicios/` para consulta pública de experiencias.

**Tech Stack:** Django 6, Django REST Framework, Postgres RLS (Supabase) / SQLite local, Stripe SDK 15.4.

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `backend/apps/payments/estrategias_precio.py` | Crear | Clases `EstrategiaPrecio`, `PorGrupo`, `PorPersona`, `TarifaFija`, `PorNoche`, y DTOs de cálculo. |
| `backend/apps/payments/pricing.py` | Modificar | Integrar resolución de estrategias de precio manteniendo funciones puras existentes. |
| `backend/apps/payments/tests_pricing_estrategias.py` | Crear | Pruebas unitarias de las estrategias de precio. |
| `backend/apps/fleet/models.py` | Modificar | Modelos `Servicio`, `Recurso`, `Personalizacion`, `ServicioPersonalizacion`. |
| `backend/apps/fleet/admin.py` | Modificar | Registrar los nuevos modelos en el admin con `EmpresaScopedAdminMixin`. |
| `backend/apps/fleet/serializers.py` | Modificar | Serializers para `Servicio` y `ServicioPersonalizacion`. |
| `backend/apps/fleet/views.py` | Modificar | Endpoint público `ServiciosListView` y `ServicioDetailView`. |
| `backend/apps/fleet/urls.py` | Modificar | Montar rutas de servicios bajo el prefijo `<slug:empresa_slug>/`. |
| `backend/apps/fleet/migrations/0016_catalogo_capas.py` | Crear | Migración de esquema para los 4 modelos de catálogo. |
| `backend/apps/fleet/migrations/0017_rls_catalogo.py` | Crear | Políticas RLS de Postgres para las 4 tablas de catálogo. |
| `backend/apps/fleet/migrations/0018_crear_servicio_la_paz.py` | Crear | Migración de datos que siembra el servicio "Pesca Deportiva" en Sal y Sol. |
| `backend/apps/fleet/tests_catalogo.py` | Crear | Pruebas de integración del catálogo, admin y RLS. |
| `backend/apps/bookings/models.py` | Modificar | Agregar FK `servicio` opcional en `Reserva`. |
| `backend/apps/bookings/migrations/0025_reserva_servicio.py` | Crear | Migración de esquema para `Reserva.servicio`. |

---

## Tareas Bite-Sized

### Bloque 1: Estrategias de Precio Puras (`apps/payments`)

- [x] **Task P1: Crear `apps/payments/estrategias_precio.py` y tests unitarios**
  - **Archivos:**
    - Crear `backend/apps/payments/estrategias_precio.py`
    - Modificar `backend/apps/payments/pricing.py`
    - Crear `backend/apps/payments/tests_pricing_estrategias.py`
  - **Descripción:**
    - Definir `DemandaPrecio(personas, moneda, noches=1)`
    - Definir clase base `EstrategiaPrecio(ABC)` con método abstracto `calcular_base(servicio_config, demanda) -> Decimal`.
    - Implementar `PorGrupo`: `precio_base + cargo_por_personas(precio_persona_extra, personas, personas_incluidas)`.
    - Implementar `PorPersona`: `precio_base * personas`.
    - Implementar `TarifaFija`: `precio_base`.
    - Implementar `PorNoche`: `precio_base * noches`.
    - Registrar estrategias en `REGISTRO_ESTRATEGIAS_PRECIO`.
    - Pruebas en MXN y USD.
  - **Test:** `python manage.py test apps.payments.tests_pricing_estrategias` (100% verde).
  - **Commit:** `feat(payments): estrategias de precio tipadas (PorGrupo, PorPersona, TarifaFija, PorNoche)`

### Bloque 2: Modelos de Catálogo por Capas (`apps/fleet`)

- [x] **Task P2: Crear modelos `Servicio`, `Recurso`, `Personalizacion`, `ServicioPersonalizacion`**
  - **Archivos:**
    - Modificar `backend/apps/fleet/models.py`
    - Crear `backend/apps/fleet/migrations/0016_catalogo_capas.py`
  - **Descripción:**
    - Agregar `Servicio`: `empresa` FK PROTECT, `nombre`, `slug`, `tipo_servicio`, `estrategia_cupo`, `estrategia_precio`, `modo_ocupacion`, `precio_base`, `precio_base_usd`, `precio_persona_extra`, `precio_persona_extra_usd`, `personas_incluidas`, `activo`.
    - Agregar `Recurso`: `empresa` FK PROTECT, `servicio` FK opcional, `nombre`, `capacidad_maxima`, `activo`.
    - Agregar `Personalizacion`: `empresa` FK PROTECT, `nombre`, `tipo`, `cobrar_por_persona`, `cantidad_editable`, `activo`.
    - Agregar `ServicioPersonalizacion`: `servicio` FK CASCADE, `personalizacion` FK PROTECT, `precio`, `precio_usd`, `obligatorio`, `preseleccionado`, `activo`.
    - Generar y correr migración `0016_catalogo_capas.py`.
  - **Test:** `python manage.py check` (0 issues).
  - **Commit:** `feat(fleet): modelos de catalogo por capas (Servicio, Recurso, Personalizacion)`

### Bloque 3: Row Level Security (RLS) en Postgres para Catálogo

- [ ] **Task P3: Migración RLS de Postgres para las tablas de catálogo**
  - **Archivos:**
    - Crear `backend/apps/fleet/migrations/0017_rls_catalogo.py`
    - Crear `backend/apps/fleet/tests_catalogo_rls.py`
  - **Descripción:**
    - En `0017_rls_catalogo.py`:
      - `ALTER TABLE fleet_servicio ENABLE ROW LEVEL SECURITY; ALTER TABLE fleet_servicio FORCE ROW LEVEL SECURITY;`
      - `ALTER TABLE fleet_recurso ENABLE ROW LEVEL SECURITY; ALTER TABLE fleet_recurso FORCE ROW LEVEL SECURITY;`
      - `ALTER TABLE fleet_personalizacion ENABLE ROW LEVEL SECURITY; ALTER TABLE fleet_personalizacion FORCE ROW LEVEL SECURITY;`
      - `ALTER TABLE fleet_serviciopersonalizacion ENABLE ROW LEVEL SECURITY; ALTER TABLE fleet_serviciopersonalizacion FORCE ROW LEVEL SECURITY;`
      - Crear políticas `FOR ALL` con verificación de `empresa_id` y `app.operador_plataforma`.
    - Tests de aislamiento en `tests_catalogo_rls.py`.
  - **Test:** `python manage.py test apps.fleet.tests_catalogo_rls` (100% verde).
  - **Commit:** `feat(fleet): politicas RLS de Postgres para modelos de catalogo`

### Bloque 4: Migración de Datos La Paz y Admin

- [ ] **Task P4: Siembra de Servicio La Paz y configuración del Admin**
  - **Archivos:**
    - Crear `backend/apps/fleet/migrations/0018_crear_servicio_la_paz.py`
    - Modificar `backend/apps/fleet/admin.py`
  - **Descripción:**
    - En `0018_crear_servicio_la_paz.py`:
      - Migración de datos (`RunPython`): busca la Empresa "Sal y Sol" y su `Tarifa`. Crea el `Servicio` "Pesca Deportiva en La Paz" (`slug='pesca-deportiva'`) con los precios y configuración de pesca.
      - Asocia los `Recurso`s correspondientes a partir de las `Embarcacion`es existentes.
    - En `apps/fleet/admin.py`:
      - Registrar `ServicioAdmin`, `RecursoAdmin`, `PersonalizacionAdmin`, `ServicioPersonalizacionInline` usando `EmpresaScopedAdminMixin`.
  - **Test:** `python manage.py test apps.fleet` (100% verde).
  - **Commit:** `feat(fleet): siembra de servicio de pesca de La Paz y administracion escopeada`

### Bloque 5: Vistas de Catálogo y Serializers

- [ ] **Task P5: Endpoints públicos de servicios y serializers**
  - **Archivos:**
    - Modificar `backend/apps/fleet/serializers.py`
    - Modificar `backend/apps/fleet/views.py`
    - Modificar `backend/apps/fleet/urls.py`
    - Crear `backend/apps/fleet/tests_servicios_api.py`
  - **Descripción:**
    - `ServicioSerializer`: serializa información del servicio, precios, estrategia y personalizaciones activas asociadas.
    - `ServiciosListView` (`GET /api/<empresa_slug>/servicios/`): lista servicios activos de la empresa.
    - `ServicioDetailView` (`GET /api/<empresa_slug>/servicios/<slug>/`): detalle del servicio.
    - Pruebas en `tests_servicios_api.py`.
  - **Test:** `python manage.py test apps.fleet.tests_servicios_api` (100% verde).
  - **Commit:** `feat(fleet): vistas y serializers publicos para catalogo de servicios`

### Bloque 6: Integración con Reservas y Pagos (`Reserva.servicio`)

- [ ] **Task P6: Asociación de `Reserva.servicio` y congelado de precio**
  - **Archivos:**
    - Modificar `backend/apps/bookings/models.py`
    - Crear `backend/apps/bookings/migrations/0025_reserva_servicio.py`
    - Modificar `backend/apps/payments/views.py`
  - **Descripción:**
    - En `apps/bookings/models.py`:
      - Agregar `servicio = models.ForeignKey('fleet.Servicio', null=True, blank=True, on_delete=models.PROTECT, related_name='reservas')`.
    - Generar y correr migración `0025_reserva_servicio.py`.
    - En `apps/payments/views.py` (`CrearPagoView`):
      - Si la reserva tiene `servicio`, calcula el precio base usando la estrategia del servicio; si no, fallback a `Tarifa.de(empresa)` para retrocompatibilidad total.
  - **Test:** `python manage.py test apps.payments apps.bookings` (100% verde).
  - **Commit:** `feat(bookings): asocia Reserva con Servicio y congela precio por estrategia`

### Bloque 7: Verificación Integral de No-Regresión

- [ ] **Task P7: Suite completa de pruebas de backend (verificación integral)**
  - **Archivos:**
    - Ninguno (solo verificación).
  - **Descripción:**
    - Ejecutar `python manage.py check` (0 issues).
    - Ejecutar `python manage.py test config apps` (todos los tests previos + nuevos al 100% en verde).
  - **Test:** `python manage.py test config apps` (100% verde, 0 errores, 0 fallos).
  - **Commit:** `test(catalogo): suite integral de pruebas para pieza 3`
