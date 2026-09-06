# Expansión multi-sede — Pieza 6: Frontend Multi-Tenant con Selector de Sede, Paquetes Dominantes y Servicios Sueltos en Camino Secundario

> **For agentic workers:** Implement this plan task-by-task. Each task must produce a single atomic commit with an explanatory commit message in Spanish and the required co-author line:
> `Co-Authored-By: Antigravity (Google DeepMind) <antigravity@google.com>`
> All tests, lints, and typechecks must be 100% green before and after each task.

**Goal:** Implementar la experiencia frontend multi-tenant orientada a marketplace según la especificación de diseño (`docs/superpowers/specs/2026-08-31-expansion-multi-sede-design.md`, línea 896):
1. **Selector de Sede (localidad)**: permite al usuario explorar los destinos disponibles (ej. La Paz, Los Cabos) tanto desde la navegación como en el catálogo.
2. **Catálogo con Paquetes Dominantes (*Perception-First Design*)**: tarjetas destacadas como unidad de compra experiencial dominante (ej. "Día completo en La Paz"), con precio ancla claro y edición in-place (el usuario puede desmarcar servicios removibles, descontando su ajuste en vivo sin romper la identidad del paquete).
3. **Servicios Sueltos en Camino Secundario**: sección visualmente secundaria para clientes que buscan una sola prestación (ej. solo transporte o solo pesca), con cross-sell sugerido.
4. **Integración con Checkout**: el paquete elegido (y sus componentes activos) viaja al checkout para ser guardado con `paquete_id` en la reserva de backend.

---

## Arquitectura y Principios de Diseño

1. **Perception-First Design (Decisión 4 aprobada)**:
   - El cliente no ensambla un rompecabezas de partes sueltas: entra a una experiencia empaquetada clara y dominante.
   - El precio ancla no es una simple suma de partes; arranca en el valor del paquete y se reduce según los ajustes configurados si se retiran servicios removibles.
2. **Sede como Agrupador Geográfico**:
   - La Sede agrupa empresas y paquetes sin romper el aislamiento multi-tenant.
   - El frontend consume `/api/sedes/` para el selector y `/api/sedes/<sede_slug>/paquetes/` y `/api/sedes/<sede_slug>/servicios/` para el catálogo.
3. **Consistencia y Retrocompatibilidad**:
   - Mantiene 100% operativo el flujo actual de pesca directa de La Paz (`/reservar`).
   - Los textos y traducciones residen en `src/app/[lang]/dictionaries/{es,en}.json`.
   - Sin cifras hardcodeadas: todos los precios provienen de los endpoints del backend.

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `backend/apps/tenancy/serializers.py` | Crear | Serializador público `SedeSerializer` (`id`, `nombre`, `slug`, `zona_horaria`). |
| `backend/apps/fleet/views.py` | Modificar | Agregar `SedesListView` (`/api/sedes/`) y `ServiciosPorSedeListView` (`/api/sedes/<slug>/servicios/`). |
| `backend/apps/fleet/urls.py` | Modificar | Registrar rutas `/api/sedes/` y `/api/sedes/<slug>/servicios/`. |
| `backend/apps/fleet/tests_paquetes_api.py` | Modificar | Pruebas de integración para los nuevos endpoints de sedes y servicios por sede. |
| `frontend/src/lib/api.ts` | Modificar | Tipos `Sede`, `Paquete`, `PaqueteServicio`, `ServicioCatalogo`, llamadas `getSedes()`, `getPaquetesSede()`, `getServiciosSede()` y campo `paquete` en `ReservaInput`. |
| `frontend/src/lib/pricing-paquete.ts` | Crear | Función pura para calcular precio reactivo del paquete con servicios removidos en cliente. |
| `frontend/src/components/sede-selector.tsx` | Crear | Componente accesible de selección de sede/localidad con persistencia o navegación. |
| `frontend/src/components/paquete-card.tsx` | Crear | Tarjeta dominante de paquete con soporte de edición in-place (remoción de servicios y actualización reactiva de precio ancla). |
| `frontend/src/components/servicios-sueltos-section.tsx` | Crear | Camino secundario para servicios individuales con menor peso visual. |
| `frontend/src/app/[lang]/catalogo/page.tsx` | Crear | Página de catálogo multi-sede con server-side data fetching por sede. |
| `frontend/src/app/[lang]/catalogo/loading.tsx` | Crear | Skeleton loader para la vista de catálogo. |
| `frontend/src/components/site-header.tsx` | Modificar | Incorporar enlace al catálogo y selector de sede en barra de navegación. |
| `frontend/src/components/checkout-view.tsx` | Modificar | Resumen y parametrización de reserva amparada por un paquete. |
| `frontend/src/app/[lang]/dictionaries/es.json` | Modificar | Textos en español para catálogo, selector de sede, paquetes y edición in-place. |
| `frontend/src/app/[lang]/dictionaries/en.json` | Modificar | Textos en inglés para catálogo, selector de sede, paquetes y edición in-place. |

---

## Tareas Bite-Sized

### Bloque 1: Endpoints Backend para Catálogo Multi-Sede

- [ ] **Task P6.1: Endpoints públicos `GET /api/sedes/` y `GET /api/sedes/<sede_slug>/servicios/`**
  - **Archivos:**
    - Crear `backend/apps/tenancy/serializers.py`
    - Modificar `backend/apps/fleet/views.py`
    - Modificar `backend/apps/fleet/urls.py`
    - Modificar `backend/apps/fleet/tests_paquetes_api.py`
  - **Descripción:**
    - Crear `SedeSerializer` con campos `id`, `nombre`, `slug`, `zona_horaria`.
    - Crear `SedesListView`: lista pública de sedes con `activo=True`, ordenada por nombre.
    - Crear `ServiciosPorSedeListView`: lista pública de servicios activos cuyas empresas pertenezcan a `sede` y estén activas.
    - Registrar en `backend/apps/fleet/urls.py`:
      - `path('sedes/', SedesListView.as_view(), name='sedes-list')`
      - `path('sedes/<slug:sede_slug>/servicios/', ServiciosPorSedeListView.as_view(), name='servicios-por-sede')`
    - Agregar tests unitarios y de integración en `tests_paquetes_api.py`.
  - **Test:** `python manage.py test apps.fleet.tests_paquetes_api` (100% verde).
  - **Commit:** `feat(fleet): endpoints publicos de sedes y servicios por sede para catalogo`

### Bloque 2: Tipos y Cliente API en Frontend

- [ ] **Task P6.2: Tipos TypeScript y cliente API para catálogo multi-sede y cálculo reactivo de paquete**
  - **Archivos:**
    - Modificar `frontend/src/lib/api.ts`
    - Crear `frontend/src/lib/pricing-paquete.ts`
  - **Descripción:**
    - En `frontend/src/lib/api.ts`:
      - Definir tipos `Sede`, `ServicioCatalogo`, `PaqueteServicioCatalogo`, `PaqueteCatalogo`.
      - Extender `ReservaInput` con campo opcional `paquete?: number | null`.
      - Exportar funciones:
        - `getSedes(): Promise<Sede[]>`
        - `getPaquetesSede(sedeSlug: string): Promise<PaqueteCatalogo[]>`
        - `getServiciosSede(sedeSlug: string): Promise<ServicioCatalogo[]>`
    - En `frontend/src/lib/pricing-paquete.ts`:
      - Implementar función pura `calcularPrecioPaquete(paquete, serviciosExcluidosIds, moneda)` que descuenta los `ajuste_precio` del `precio_ancla` según la moneda elegida.
  - **Test:** `npx.cmd tsc --noEmit` (100% verde).
  - **Commit:** `feat(frontend): tipos y cliente api para sedes, paquetes y calculo de precio ancla`

### Bloque 3: Selector de Sede y Navegación Multi-Tenant

- [ ] **Task P6.3: Componente `SedeSelector` y actualización de navegación**
  - **Archivos:**
    - Crear `frontend/src/components/sede-selector.tsx`
    - Modificar `frontend/src/components/site-header.tsx`
    - Modificar `frontend/src/app/[lang]/dictionaries/es.json`
    - Modificar `frontend/src/app/[lang]/dictionaries/en.json`
  - **Descripción:**
    - Crear `SedeSelector`: dropdown accesible y estilizado con Tailwind v4 / Phosphor Icons para cambiar de localidad.
    - Al cambiar de sede, redirigir a `/[lang]/catalogo?sede=<slug>` o disparar callback `onSelectSede`.
    - Actualizar `SiteHeader` para incluir enlace al Catálogo/Experiencias y renderizar el selector de sede.
    - Agregar traducciones en `es.json` y `en.json`.
  - **Test:** `npx.cmd tsc --noEmit` y `npm.cmd run lint` (100% verde).
  - **Commit:** `feat(frontend): selector de sede y navegacion de experiencias multi-tenant`

### Bloque 4: Paquetes Dominantes con Perception-First Design

- [ ] **Task P6.4: Componente `PaqueteCard` con desglose interactivo y edición in-place**
  - **Archivos:**
    - Crear `frontend/src/components/paquete-card.tsx`
    - Modificar `frontend/src/app/[lang]/dictionaries/es.json`
    - Modificar `frontend/src/app/[lang]/dictionaries/en.json`
  - **Descripción:**
    - Diseñar `PaqueteCard` como producto dominante:
      - Encabezado con badge destacado ("Experiencia recomendada"), nombre experiencial y descripción.
      - Desglose de servicios incluidos en lista con checkboxes interactivos.
      - Para servicios `removible=true`, permitir al usuario desmarcarlos in-place.
      - Para servicios no removibles (`removible=false`), mostrar badge "Incluido fijo" no desmarcable.
      - Visualización reactiva del precio ancla: muestra precio inicial y el ahorro aplicado por servicios removidos en tiempo real.
      - Botón de acción principal hacia la reserva (`/[lang]/reservar?paquete=<slug>&excluidos=...`).
    - Agregar textos y mensajes en diccionarios.
  - **Test:** `npx.cmd tsc --noEmit` y `npm.cmd run lint` (100% verde).
  - **Commit:** `feat(frontend): tarjeta de paquete dominante con edicion in-place de servicios y precio ancla`

### Bloque 5: Camino Secundario para Servicios Sueltos

- [ ] **Task P6.5: Componente `ServiciosSueltosSection` con menor peso visual y cross-sell**
  - **Archivos:**
    - Crear `frontend/src/components/servicios-sueltos-section.tsx`
    - Modificar `frontend/src/app/[lang]/dictionaries/es.json`
    - Modificar `frontend/src/app/[lang]/dictionaries/en.json`
  - **Descripción:**
    - Implementar sección visualmente secundaria ("¿Buscas solo un servicio específico?").
    - Grilla de tarjetas compactas de servicios sueltos (pesca, transporte, etc.) con su precio base.
    - Botón de acción directa para reservar el servicio individual.
    - Sugerencias sutiles de cross-sell ("Combínalo con un paquete para mayor ahorro").
    - Agregar textos correspondientes en diccionarios.
  - **Test:** `npx.cmd tsc --noEmit` y `npm.cmd run lint` (100% verde).
  - **Commit:** `feat(frontend): seccion de camino secundario para servicios sueltos`

### Bloque 6: Página de Catálogo Multi-Sede

- [ ] **Task P6.6: Página de catálogo de experiencias (`/[lang]/catalogo`)**
  - **Archivos:**
    - Crear `frontend/src/app/[lang]/catalogo/page.tsx`
    - Crear `frontend/src/app/[lang]/catalogo/loading.tsx`
    - Modificar `frontend/src/app/[lang]/dictionaries/es.json`
    - Modificar `frontend/src/app/[lang]/dictionaries/en.json`
  - **Descripción:**
    - Página Server Component que recibe `params` (`lang`) y `searchParams` (`sede`).
    - Carga en paralelo: lista de sedes, paquetes de la sede seleccionada (default: primera sede o `la-paz`), y servicios sueltos.
    - Renderiza:
      - Selector de sede destacado para alternar de ciudad.
      - Sección dominante de Paquetes (`PaqueteCard` en grid).
      - Sección secundaria de Servicios sueltos (`ServiciosSueltosSection`).
    - Skeleton loader en `loading.tsx`.
    - Metadatos SEO configurados.
  - **Test:** `npx.cmd tsc --noEmit` y `npm.cmd run lint` (100% verde).
  - **Commit:** `feat(frontend): pagina de catalogo multi-sede con paquetes dominantes y servicios secundarios`

### Bloque 7: Integración de Paquete en el Checkout

- [ ] **Task P6.7: Soporte de reserva con paquete en `CheckoutView`**
  - **Archivos:**
    - Modificar `frontend/src/components/checkout-view.tsx`
    - Modificar `frontend/src/app/[lang]/reservar/page.tsx`
    - Modificar `frontend/src/app/[lang]/dictionaries/es.json`
    - Modificar `frontend/src/app/[lang]/dictionaries/en.json`
  - **Descripción:**
    - Leer `paquete` (slug o id) desde `searchParams` en `ReservarPage`.
    - En `CheckoutView`:
      - Si hay un paquete asignado, mostrar banner con el nombre de la experiencia amparada.
      - Al armar el payload `ReservaInput` en `guardarReserva`, incluir `paquete: paqueteId`.
      - Mantener 100% de retrocompatibilidad si no se envía paquete (reserva tradicional directa de pesca).
  - **Test:** `npx.cmd tsc --noEmit` y `npm.cmd run lint` (100% verde).
  - **Commit:** `feat(frontend): integracion de reserva de paquete en checkout view`

### Bloque 8: Verificación Integral End-to-End

- [ ] **Task P6.8: Suite integral de verificación para la Pieza 6**
  - **Archivos:**
    - Todos los involucrados en Pieza 6.
  - **Descripción:**
    - Ejecutar suite completa de tests de Django backend (`manage.py test`).
    - Ejecutar `manage.py check` con 0 issues.
    - Ejecutar `npm.cmd run lint` en frontend (0 errores/warnings).
    - Ejecutar `npx.cmd tsc --noEmit` en frontend (0 errores de tipado).
    - Ejecutar `npm.cmd run build` para validar que el bundle de Next.js compila limpiamente.
  - **Test:** Backend y Frontend 100% verdes.
  - **Commit:** `test(frontend): verificacion integral de catalogo multi-tenant y paquetes`
