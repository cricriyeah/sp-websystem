# Expansión multi-sede — Pieza 5: Paquetes como Producto de Primera Clase (`Paquete`, `PaqueteServicio`, Perception-First Design) Implementation Plan

> **For agentic workers:** Implement this plan task-by-task. Each task must produce a single atomic commit with an explanatory commit message in Spanish and the required co-author line. All tests must be 100% green before and after each task.

**Goal:** Implementar el modelo de `Paquete` como producto de primera clase vendible y editable in-place (Perception-First Design), su relación con múltiples `Servicios` (de la misma empresa o de distintas empresas de la misma `Sede`), la definición de la `empresa_lider` que procesa el cobro en su Stripe estándar, la regla de precio ancla con ajustes por servicios removidos en `apps/payments/pricing.py`, políticas RLS en PostgreSQL, endpoints de catálogo de paquetes por sede y empresa, y administración completa en Django Admin. Todo garantizando 100% de retrocompatibilidad con las reservas de pesca de La Paz.

**Architecture:**
1. **Modelos de Catálogo de Paquetes (`apps.fleet`):**
   - `Paquete`: entidad de primera clase radicada en una `Sede` geográfica, con una `empresa_lider` responsable del cobro en Stripe y de la emisión de la reserva principal. Atributos: `nombre`, `slug`, `descripcion`, `precio_ancla`, `precio_ancla_usd`, `regla_precio` ('precio_ancla'), `activo`.
   - `PaqueteServicio`: tabla de asociación entre `Paquete` y `Servicio`. Atributos: `orden`, `removible` (default True), `ajuste_precio` (descuento del ancla en MXN si se retira), `ajuste_precio_usd`.
   - Regla de integridad geográfica: todos los servicios asociados a un paquete deben pertenecer a empresas de la misma `Sede` que el paquete (`servicio.empresa.sede_id == paquete.sede_id`).
2. **Asociación en `Reserva` (`apps.bookings`):**
   - Campo opcional `paquete = ForeignKey('fleet.Paquete', null=True, blank=True, on_delete=SET_NULL, related_name='reservas')`.
   - Validación: si la reserva tiene un paquete asignado, la empresa de la reserva debe coincidir con la `empresa_lider` del paquete.
3. **Cálculo Puro de Precios de Paquete (`apps.payments.pricing`):**
   - Función pura `precio_paquete(precio_ancla, ajustes_removidos) -> Decimal`: arranca en el ancla y descuenta los ajustes de los servicios removidos por el usuario, evitando caer en una simple "suma de partes con descuento". Soporte para MXN y USD.
4. **Row Level Security (RLS) en Postgres:**
   - Tabla `fleet_paquete`: RLS con política `tenancy_alcance` filtrando por `empresa_lider_id`.
   - Tabla `fleet_paqueteservicio`: RLS con política `tenancy_alcance` vía subconsulta sobre `paquete.empresa_lider_id`.
5. **Endpoints Públicos y Django Admin:**
   - Endpoint `/api/sedes/<sede_slug>/paquetes/`: catálogo público de experiencias empaquetadas por localidad.
   - Endpoint `/api/<empresa_slug>/paquetes/`: paquetes liderados por una empresa en particular.
   - `PaqueteAdmin` con `PaqueteServicioInline` en `apps/fleet/admin.py`, protegido con `EmpresaScopedAdminMixin`.

**Tech Stack:** Django 6, Django REST Framework, PostgreSQL RLS / SQLite local.

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `backend/apps/fleet/models.py` | Modificar | Modelos `Paquete` y `PaqueteServicio`, validaciones de integridad geográfica y constraints. |
| `backend/apps/fleet/migrations/0019_paquetes.py` | Crear | Migración de esquema para `Paquete` y `PaqueteServicio`. |
| `backend/apps/fleet/tests_paquetes.py` | Crear | Pruebas unitarias de modelos `Paquete` y `PaqueteServicio`. |
| `backend/apps/bookings/models.py` | Modificar | Campo `Reserva.paquete` y validación de coincidencia con `empresa_lider`. |
| `backend/apps/bookings/migrations/0028_reserva_paquete.py` | Crear | Migración de esquema agregando `paquete` a `Reserva`. |
| `backend/apps/bookings/tests_reserva_paquete.py` | Crear | Pruebas de integración de `Reserva` vinculada a `Paquete`. |
| `backend/apps/payments/pricing.py` | Modificar | Funciones puras `precio_paquete` y cálculo de precio ajustado. |
| `backend/apps/payments/tests_pricing_paquete.py` | Crear | Pruebas unitarias puras del cálculo de precio de paquetes (ancla - ajustes). |
| `backend/apps/fleet/migrations/0020_rls_paquetes.py` | Crear | Migración RLS de PostgreSQL para `fleet_paquete` y `fleet_paqueteservicio`. |
| `backend/apps/fleet/tests_paquetes_rls.py` | Crear | Pruebas de aislamiento RLS en PostgreSQL para paquetes. |
| `backend/apps/fleet/serializers.py` | Modificar | Serializadores de `Paquete` y `PaqueteServicio`. |
| `backend/apps/fleet/views.py` | Modificar | Vistas API para listar paquetes por sede y por empresa. |
| `backend/apps/fleet/urls.py` | Modificar | Rutas de catálogo de paquetes. |
| `backend/apps/fleet/tests_paquetes_api.py` | Crear | Pruebas de integración para endpoints de paquetes. |
| `backend/apps/fleet/admin.py` | Modificar | Registro de `PaqueteAdmin` y `PaqueteServicioInline`. |

---

## Tareas Bite-Sized

### Bloque 1: Modelos de Datos `Paquete` y `PaqueteServicio` (`apps/fleet`)

- [ ] **Task P1: Crear modelos `Paquete` y `PaqueteServicio` con validación geográfica**
  - **Archivos:**
    - Modificar `backend/apps/fleet/models.py`
    - Crear `backend/apps/fleet/migrations/0019_paquetes.py`
    - Crear `backend/apps/fleet/tests_paquetes.py`
  - **Descripción:**
    - Crear modelo `Paquete`:
      - `sede` FK a `tenancy.Sede` (PROTECT, `related_name='paquetes'`).
      - `empresa_lider` FK a `tenancy.Empresa` (PROTECT, `related_name='paquetes_liderados'`).
      - `nombre` CharField(150), `slug` SlugField(150), `descripcion` TextField(blank=True).
      - `precio_ancla` DecimalField(10, 2), `precio_ancla_usd` DecimalField(10, 2, null=True, blank=True).
      - `regla_precio` CharField(50, default='precio_ancla'), `activo` BooleanField(default=True).
      - `UniqueConstraint(fields=['sede', 'slug'], name='paquete_unico_por_sede_slug')`.
      - `clean()` valida: `empresa_lider.sede_id == sede_id`.
    - Crear modelo `PaqueteServicio`:
      - `paquete` FK a `Paquete` (CASCADE, `related_name='servicios_asociados'`).
      - `servicio` FK a `Servicio` (PROTECT, `related_name='paquetes_incluidos'`).
      - `orden` PositiveSmallIntegerField(default=1), `removible` BooleanField(default=True).
      - `ajuste_precio` DecimalField(10, 2, default=0.00), `ajuste_precio_usd` DecimalField(10, 2, null=True, blank=True).
      - `UniqueConstraint(fields=['paquete', 'servicio'], name='paqueteservicio_unico')`.
      - `clean()` valida: `servicio.empresa.sede_id == paquete.sede_id`.
    - Generar y correr migración `0019_paquetes.py`.
    - Pruebas unitarias de creación, validación geográfica y constraints.
  - **Test:** `python manage.py test apps.fleet.tests_paquetes` (100% verde).
  - **Commit:** `feat(fleet): modelos Paquete y PaqueteServicio con validacion geografica`

### Bloque 2: Vinculación de `Paquete` en `Reserva` (`apps/bookings`)

- [ ] **Task P2: Extender `Reserva` con campo opcional `paquete`**
  - **Archivos:**
    - Modificar `backend/apps/bookings/models.py`
    - Crear `backend/apps/bookings/migrations/0028_reserva_paquete.py`
    - Crear `backend/apps/bookings/tests_reserva_paquete.py`
  - **Descripción:**
    - En `Reserva`: agregar campo `paquete = models.ForeignKey('fleet.Paquete', on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas', help_text='Paquete que ampara esta reserva.')`.
    - En `Reserva.clean()`: validar que si `paquete_id` existe, `self.empresa_id == self.paquete.empresa_lider_id`.
    - Generar y aplicar migración `0028_reserva_paquete.py`.
    - Pruebas unitarias de integridad y consistencia con `empresa_lider`.
  - **Test:** `python manage.py test apps.bookings.tests_reserva_paquete` (100% verde).
  - **Commit:** `feat(bookings): vinculacion de paquete en reserva con validacion de empresa lider`

### Bloque 3: Lógica Pura de Precio de Paquete (`apps/payments/pricing.py`)

- [ ] **Task P3: Implementar cálculo de precio ancla con servicios removidos**
  - **Archivos:**
    - Modificar `backend/apps/payments/pricing.py`
    - Crear `backend/apps/payments/tests_pricing_paquete.py`
  - **Descripción:**
    - En `pricing.py`: implementar función pura `precio_paquete(precio_ancla: Decimal, ajustes_removidos: list[Decimal]) -> Decimal`.
      - Descuenta la suma de ajustes del precio ancla, garantizando un piso de `Decimal('0.00')`.
    - Implementar `calcular_precio_paquete(paquete, servicios_removidos_pks=None, moneda='MXN') -> Decimal`.
      - Soporta precios independientes en MXN y USD.
    - Pruebas unitarias completas: paquete sin cambios, paquete con 1 servicio removido, paquete con múltiples servicios removidos, manejo de moneda USD y piso en cero.
  - **Test:** `python manage.py test apps.payments.tests_pricing_paquete` (100% verde).
  - **Commit:** `feat(payments): calculo puro de precio ancla de paquetes con ajuste in-place`

### Bloque 4: Row Level Security (RLS) en Postgres para Paquetes (`apps/fleet`)

- [ ] **Task P4: Migración RLS de Postgres para `fleet_paquete` y `fleet_paqueteservicio`**
  - **Archivos:**
    - Crear `backend/apps/fleet/migrations/0020_rls_paquetes.py`
    - Crear `backend/apps/fleet/tests_paquetes_rls.py`
  - **Descripción:**
    - En `0020_rls_paquetes.py`:
      - `ALTER TABLE fleet_paquete ENABLE ROW LEVEL SECURITY;`
      - `ALTER TABLE fleet_paquete FORCE ROW LEVEL SECURITY;`
      - Política en `fleet_paquete` por `empresa_lider_id`.
      - `ALTER TABLE fleet_paqueteservicio ENABLE ROW LEVEL SECURITY;`
      - `ALTER TABLE fleet_paqueteservicio FORCE ROW LEVEL SECURITY;`
      - Política en `fleet_paqueteservicio` vía subconsulta sobre `fleet_paquete.empresa_lider_id`.
    - Pruebas de aislamiento RLS en `tests_paquetes_rls.py` (saltadas con `skipUnless` en SQLite).
  - **Test:** `python manage.py test apps.fleet.tests_paquetes_rls` (100% verde).
  - **Commit:** `feat(fleet): politicas RLS de Postgres para Paquete y PaqueteServicio`

### Bloque 5: Serializers y Endpoints API de Paquetes (`apps/fleet`)

- [ ] **Task P5: Endpoints de catálogo de paquetes por sede y por empresa**
  - **Archivos:**
    - Modificar `backend/apps/fleet/serializers.py`
    - Modificar `backend/apps/fleet/views.py`
    - Modificar `backend/apps/fleet/urls.py`
    - Crear `backend/apps/fleet/tests_paquetes_api.py`
  - **Descripción:**
    - En `serializers.py`:
      - `PaqueteServicioSerializer`: expone detalle del servicio, orden, removible y ajustes de precio.
      - `PaqueteSerializer`: expone sede, empresa_lider, nombre, slug, descripción, precio ancla (MXN/USD) y lista anidada de servicios asociados.
    - En `views.py`:
      - `PaquetesPorSedeListView`: `/api/sedes/<sede_slug>/paquetes/` (catálogo experiencial de paquetes de la localidad).
      - `PaquetesPorEmpresaListView`: `/api/<empresa_slug>/paquetes/` (paquetes liderados por una empresa específica).
    - En `urls.py`: registrar rutas.
    - Pruebas de integración API validando respuestas HTTP 200, filtrado por sede/empresa y exclusión de paquetes inactivos.
  - **Test:** `python manage.py test apps.fleet.tests_paquetes_api` (100% verde).
  - **Commit:** `feat(fleet): endpoints API de catalogo de paquetes por sede y empresa`

### Bloque 6: Django Admin para Paquetes (`apps/fleet/admin.py`)

- [ ] **Task P6: Registro de `PaqueteAdmin` con `PaqueteServicioInline`**
  - **Archivos:**
    - Modificar `backend/apps/fleet/admin.py`
    - Modificar `backend/apps/bookings/admin.py`
  - **Descripción:**
    - En `fleet/admin.py`:
      - Crear `PaqueteServicioInline(admin.TabularInline)`.
      - Registrar `PaqueteAdmin(EmpresaScopedAdminMixin, ModelAdmin)` con `empresa_campo='empresa_lider'`.
      - Búsqueda por nombre y filtros por sede y activo.
    - En `bookings/admin.py`:
      - Agregar `paquete` a `autocomplete_fields` o `readonly_fields` en `ReservaAdmin`.
  - **Test:** `python manage.py check` y `python manage.py test apps.fleet apps.bookings` (100% verde).
  - **Commit:** `feat(fleet): administracion de paquetes y servicios asociados en Django Admin`

### Bloque 7: Verificación Integral de No-Regresión

- [ ] **Task P7: Suite completa de pruebas de backend (verificación integral)**
  - **Archivos:**
    - Ninguno (solo verificación).
  - **Descripción:**
    - Ejecutar `python manage.py check` (0 issues).
    - Ejecutar `python manage.py test config apps` (todas las pruebas 100% verdes).
  - **Test:** `python manage.py test config apps` (100% verde, 0 errores, 0 fallos).
  - **Commit:** `test(fleet): suite integral de pruebas para pieza 5`
