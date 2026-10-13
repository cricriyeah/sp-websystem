# Tarea 04: la pantalla de Traslados

Lee del spec §6 (pantalla Traslados) y §3 (decisiones). Es el paralelo de la Agenda de pangas: estudia `AgendaAdmin`, `AgendaForm`, `_ofrecer_solo_lo_que_sirve`, `_aligerar_selectores`, el filtro `CuandoFilter` y la plantilla `agenda_changelist.html` en `backend/apps/bookings/admin.py` y `backend/apps/bookings/templates/bookings/`. Reutiliza sus ayudantes cuando sirvan; no los reescribas.

## Qué hacer
1. `ViajeTransporteAdmin` (con `EmpresaScopedAdminMixin`, verbose «Traslados») en `backend/apps/bookings/admin.py`:
   - Columnas: Cuándo (fecha y hora), Cliente, Personas, Tramo (Ida / Regreso / Único), Recogida (punto de encuentro, dirección o zona del `detalle_transporte`; usa `select_related` para no hacer una consulta por fila), Vehículo (editable), Aviso.
   - `list_editable = ['vehiculo']`. El selector de cada fila ofrece los vehículos activos que **caben** y no están bloqueados ese día/hora, y siempre incluye el actual (mismo patrón que la Agenda). El formulario de la lista **no revalida filas sin cambios** (`has_changed()`) ni da un 500 cuando `clean()` falla sobre un campo ausente (como `AgendaForm._post_clean` / `_update_errors`). Quita los botones añadir/cambiar/borrar del selector.
   - Filtro «Cuándo»: Hoy, Mañana, Próximos 7 días (por defecto), Todos. No muestra viajes cancelados. Orden: sin vehículo primero, luego fecha y hora (sin hora al final del día).
   - Una línea de resumen arriba: «N sin vehículo» o «Todo asignado» (contexto en `changelist_view` y una plantilla que extienda el listado, como la Agenda).
   - Columna Aviso (spec §6): empalme informativo (mismo vehículo, misma fecha y hora, excluyendo cancelados), regreso sin hora, asignación que quedó inválida (ya no cabe o está bloqueado).
   - Sin alta ni borrado manual: `has_add_permission` y `has_delete_permission` devuelven False.
2. Agrega el ítem «Traslados» al menú (`UNFOLD['SIDEBAR']`, grupo Operación, junto a «Agenda»), con `reverse_lazy` y permiso `bookings.view_viajetransporte`.
3. Un regreso sin hora se edita desde la lista: agrega `hora` a `list_editable` SOLO si es práctico y seguro; si no, déjalo como limitación y dilo en el reporte (el spec §3 supone que la vendedora captura esa hora aquí).

## Pruebas (archivo nuevo `backend/apps/bookings/tests_traslados_admin.py`)
Asignar un vehículo desde la lista guarda; el selector solo ofrece los que caben y no están bloqueados; asignar uno que no cabe da el mensaje del motivo; filtro y orden; resumen («N sin vehículo» y «Todo asignado»); avisos (empalme, regreso sin hora, asignación inválida); una fila sin cambios con un vehículo ahora inválido no impide guardar el resto; permisos por rol; no hay alta ni borrado; aislamiento entre empresas; el admin carga sin errores con vendedora y jefe. Cuenta consultas: la lista no debe crecer por fila.
