# Tarea 03: catálogos de vehículos, menú y permisos

Lee del spec §6 (Vehículos y Vehículos no disponibles, Menú) y §7 (Permisos). Los modelos ya existen (tarea 01).

## Qué hacer
1. En `backend/apps/fleet/admin.py`, junto a `EmbarcacionAdmin`/`EmbarcacionNoDisponibleAdmin` (imítalos, incluido `EmpresaScopedAdminMixin` y `registrado_por`), registra **`VehiculoAdmin`** (lista: nombre, lugares, activo; `activo` editable en la lista; búsqueda por nombre) y **`VehiculoNoDisponibleAdmin`** (lista: fecha, vehículo, desde, hasta, motivo, registrado por; `autocomplete_fields` para el vehículo si `VehiculoAdmin` define `search_fields`; sella `registrado_por` al crear). Verbose names en español.
2. **Menú lateral** en `UNFOLD['SIDEBAR']` de `backend/config/settings/base.py`, con el patrón EXACTO de los ítems vecinos (`reverse_lazy` y un `permission` lambda): grupo Operación: «Vehículos no disponibles» (junto a «Pangas fuera de servicio»); grupo Catálogo: «Vehículos». (El ítem «Traslados» lo agrega la tarea 04.) Un enlace mal escrito tumba el admin completo: la prueba debe cargar una página del admin con cada rol.
3. **Permisos** en `setup_roles` (`backend/apps/bookings/management/commands/setup_roles.py`): **Vendedora** → `viajetransporte` view/change, `vehiculo` view, `vehiculonodisponible` add/change/delete/view. **Jefe** → además `vehiculo` add/change/delete. Recuerda que `setup_roles` busca los permisos con `get`: los modelos ya existen por la tarea 01. Actualiza las pruebas existentes de `setup_roles`/permisos SOLO si cuentan permisos y su conteo cambia, y dilo en el reporte.

## Pruebas (archivo nuevo `backend/apps/bookings/tests_traslados_catalogos.py`)
Permisos por rol (vendedora ve vehículos pero no los edita; jefe sí; bloqueos los gestionan ambos), el admin de cada modelo carga con cada rol, el menú muestra los ítems según permiso, `registrado_por` se sella, aislamiento entre empresas (una vendedora de otra empresa no ve vehículos ajenos) y que bloquear un vehículo con un viaje asignado ese día lo rechaza el formulario con un mensaje.
