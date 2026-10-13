# Traslados con vehículos asignables (DLS Transporte)

**Estado:** borrador para revisión · **Fecha:** 2026-10-13 · **Paso 6 del rediseño del backoffice** ("Traslados y empresas sin pangas")

## 1. Problema

DLS Transporte vende traslados (`Servicio.tipo_servicio = 'transporte'`, `estrategia_cupo = 'bajo_demanda'`). Se venden y se cobran, pero **nunca se asignan a nadie**: la Agenda los excluye, no existe un modelo de vehículo ni de viaje, y la vendedora de DLS no tiene pantalla de trabajo (hallazgo #3 del mapa del backoffice). El dueño quiere crear vehículos con N lugares y repartirlos entre las reservas de traslado, como las pangas.

Las otras tres empresas ya reparten embarcación y capitán; este trabajo es solo para el transporte.

## 2. Alcance

**Dentro:**
- Catálogo de vehículos y sus bloqueos (día completo o rango de horas).
- Un viaje por tramo de cada traslado pagado, que la vendedora asigna a un vehículo.
- Pantalla "Traslados" (lista del día con selector de vehículo por fila).
- Permisos, RLS y pruebas.

**Fuera (no se hace aquí):** conductores, equipaje, rutas o mapas, aviso al cliente al asignar, cuadrícula de vehículos × días, cambiar la venta (sigue `bajo_demanda`: vender un traslado **no** se rechaza por falta de vehículo), unificar con la Agenda de pangas.

## 3. Decisiones

| Decisión | Por qué |
|---|---|
| Un vehículo hace varios viajes al día, uno por reserva (traslado privado, sin compartir asientos) | Es el negocio de DLS |
| Sin duración automática ni rechazo por empalme de horas; solo se valida que el grupo **quepa** y que el vehículo **no esté bloqueado** | Un traslado dura lo que dure; modelar duraciones sería inventar datos que nadie captura |
| Cada tramo se asigna por separado | El regreso se decide otro día |
| `recepcion_aeropuerto` = 1 viaje; `redondo_actividad` = 2 (ida y regreso); `redondo_aeropuerto` = 2 (ida con la fecha de la reserva, regreso en `fecha_regreso`) | Respuesta del dueño: ida y regreso se asignan por separado |
| La hora del regreso la captura la vendedora en la pantalla de Traslados | El checkout no la pide |
| Aviso de empalme **informativo** (misma hora, mismo vehículo), nunca bloquea | Coherente con "sin duración automática" |
| Sin panorama de cuadrícula | DLS tiene pocos vehículos; la lista basta |

## 4. Datos

**`fleet.Vehiculo`** (tabla con `empresa_id` y RLS): `nombre`, `lugares` (entero ≥ 1), `activo`. Único por (`nombre`, `empresa`). Se da de baja con `activo=False`, nunca se borra (PROTECT desde los viajes), igual que `Embarcacion.activa`.

**`fleet.VehiculoNoDisponible`** (RLS): `empresa` (FK PROTECT, como `EmbarcacionNoDisponible`: sin ella el admin no aísla y el guardarraíl de RLS falla), `vehiculo` (PROTECT), `fecha`, `hora_desde` y `hora_hasta` opcionales, `motivo`, `registrado_por`, `creado_en`. Sin horas = todo el día. Si hay una hora debe haber las dos y `hora_desde < hora_hasta`. **Validación inversa:** `clean()` rechaza el bloqueo si ese vehículo ya tiene viajes **no cancelados** que lo toquen (todo el día; o un rango que contenga la hora del viaje; o un viaje sin hora cuando el bloqueo es de rango no cuenta como choque), igual que la Agenda impide sacar una panga que ya tiene viaje ese día. Así no se puede dejar una asignación inválida.

**`bookings.ViajeTransporte`** (RLS): `empresa`, `reserva` (CASCADE, `related_name='viajes_transporte'`), `sentido` (`unico`/`ida`/`regreso`), `fecha`, `hora` (opcional), `vehiculo` (PROTECT, nulo = sin asignar), `cancelado` (bool). Único por (`reserva`, `sentido`).

**Validación de `ViajeTransporte.clean()`** (la corre el listado editable al guardar, igual que la Agenda):
- el vehículo es de la misma empresa y está activo;
- `reserva.numero_personas <= vehiculo.lugares`;
- no hay un `VehiculoNoDisponible` de ese vehículo ese día que lo cubra: sin hora en el viaje solo chocan los bloqueos de día completo; con hora, chocan también los rangos que la contengan;
- un viaje `cancelado` no se puede asignar (y al cancelarse se le quita el vehículo, ver §5).

## 5. Crear y mantener los viajes

`bookings/traslados.py::sincronizar_viajes(reserva)`, **idempotente**:
- Aplica solo si `reserva.servicio.tipo_servicio == 'transporte'` y existe `reserva.detalle_transporte`.
- Viajes deseados según `tipo_traslado`: `recepcion_aeropuerto` → [`unico`: `reserva.fecha`, `reserva.hora`]; `redondo_actividad` → [`ida`: `reserva.fecha`, `reserva.hora`; `regreso`: `reserva.fecha`, sin hora]; `redondo_aeropuerto` → [`ida`: `reserva.fecha`, `reserva.hora`; `regreso`: `detalle.fecha_regreso`, sin hora].
- Si la reserva ocupa cupo (`ESTADOS_QUE_OCUPAN_CUPO`): crea los que faltan, actualiza `fecha`/`hora` de los existentes, **quita el vehículo** de un viaje cuya fecha cambió (la asignación deja de ser válida), borra los que ya no se desean, y pone `cancelado=False`.
- Si no ocupa cupo (cancelada o pendiente): marca `cancelado=True` en los existentes, **les quita el vehículo** (como una panga que suelta una cancelada) y no crea nuevos. Los cancelados no cuentan en el aviso de empalme.
- Nunca toca la hora de un `regreso` ya capturada.
- Usa `update_or_create` por (`reserva`, `sentido`): una carrera con el admin no produce `IntegrityError` por la unicidad.
- Recibe el detalle como argumento opcional: `sincronizar_viajes(reserva, detalle=None)`. Sin argumento lo lee con `try/except RelatedObjectDoesNotExist` (una reserva de transporte sin detalle no genera viajes) y se protege si `reserva.servicio_id` es nulo (reservas de paquete).

**Cuándo se llama** (dos puntos, porque el detalle se guarda después de la reserva en el alta manual y en el checkout):
1. `Reserva._guardar_reserva`, tras `super().save()` cuando `update_fields is None` (mismo lugar que `sincronizar_salidas`).
2. `DetalleTransporte.save()` (pasando `detalle=self`, porque el serializador y el admin guardan la reserva antes que el detalle y el caché inverso puede traer uno viejo) y `post_delete` del detalle (borrar el detalle borra sus viajes).

**El gancho nunca puede tumbar el pago.** El webhook llama `reserva.save()` dentro de un `transaction.atomic()` que solo atrapa `ValidationError` y `SinCupoError`: cualquier otra excepción deshace el cobro. Por eso ambos ganchos llaman a una envoltura `sincronizar_viajes_seguro` que abre su propio savepoint (`transaction.atomic()`), atrapa `Exception` (excepción deliberada: es un efecto secundario que no debe cancelar un cobro ya hecho), la registra con `logger.exception` y sigue. Sin savepoint propio, Postgres deja la transacción abortada.

**Reparación:** un fallo deja los viajes sin crear. `manage.py sincronizar_viajes_transporte [--dry-run]` recorre las reservas de transporte que ocupan cupo y ejecuta `sincronizar_viajes` en cada una, y es lo que también usa la migración de datos como referencia de la lógica.

**Migración de datos** (en `bookings`, después de las migraciones de `fleet` y de las tablas de viajes y de sus políticas RLS): genera los viajes de las reservas de transporte ya existentes que ocupan cupo. Envuelve **lectura y escritura** en `with alcance_operador_migracion(schema_editor.connection):` (sin eso, bajo el rol de la app `NOBYPASSRLS` el `SELECT` devuelve cero filas y la migración "termina bien" sin crear nada), usa los modelos históricos y copia la lógica en vez de importar el módulo de la app.

## 6. Pantallas (admin)

**Traslados** (`ViajeTransporteAdmin`, EmpresaScopedAdminMixin): una fila por viaje.
- Columnas: Cuándo (fecha y hora), Cliente, Personas, Tramo (Ida / Regreso / Único), Recogida (punto de encuentro, dirección o zona del `detalle_transporte`), **Vehículo** (editable en la lista), Aviso.
- `list_editable = ['vehiculo']`. El selector de cada fila ofrece los vehículos activos que **caben** y no están bloqueados ese día, y siempre incluye el actual. Si aun así se elige uno inválido, `clean()` explica el motivo.
- **El formulario no revalida filas sin cambios** (`has_changed()`), igual que `AgendaForm._post_clean`, y evita el 500 cuando `clean()` falla sobre un campo ausente del formulario (`_update_errors`). Sin esto, un viaje ya asignado cuyo vehículo luego se dio de baja, se bloqueó o quedó chico por un cambio de personas impediría guardar la lista completa. Se reutilizan los ayudantes de la Agenda (`_ofrecer_solo_lo_que_sirve`, `_aligerar_selectores` para quitar los botones añadir/cambiar/borrar del selector).
- Filtro "Cuándo": Hoy, Mañana, Próximos 7 días (por defecto), Todos. No muestra viajes cancelados.
- Orden: sin vehículo primero, luego fecha y hora (los sin hora al final del día).
- Línea de resumen arriba: "N sin vehículo" o "Todo asignado".
- Columna Aviso: "Mismo vehículo a la misma hora que #X" cuando hay empalme; "Falta la hora" en un regreso sin hora; "El vehículo ya no cabe o está bloqueado" cuando una asignación quedó inválida por un cambio posterior (más personas, otra hora dentro de un bloqueo).
- Sin alta ni borrado manual: los viajes los crea el sistema.

**Vehículos** y **Vehículos no disponibles**: catálogos simples, como Embarcaciones y Pangas fuera de servicio (el segundo con hora desde/hasta).

**Menú:** se arma a mano en `UNFOLD['SIDEBAR']` (`config/settings/base.py`), con `reverse_lazy` y un `permission` por lambda; un enlace mal escrito tumba el admin completo, así que se prueba que el admin cargue. Grupo Operación: "Traslados", "Vehículos no disponibles"; grupo Catálogo: "Vehículos". Cada uno con su permiso `view_*`.

## 7. Permisos y RLS

- Las tres tablas llevan política RLS `tenancy_alcance` por `empresa_id` (migración propia, patrón de `0050_rls_reservasalida`) . Las políticas de `Vehiculo` y `VehiculoNoDisponible` van en una migración de **`fleet`** y la de `ViajeTransporte` en una de `bookings`. Las tres tablas tienen `empresa_id`, así que la prueba guardarraíl de `tenancy/tests_rls.py` las detecta sola (no hay que tocar su lista blanca) y **falla si falta la política**.
- `setup_roles`: **Vendedora** → `viajetransporte` view/change, `vehiculo` view, `vehiculonodisponible` add/change/delete/view. **Jefe** → además `vehiculo` add/change/delete (ya tiene delete de bloqueos).
- `setup_roles` busca tipos de contenido y permisos con `get`: se ejecuta **después** de `migrate`, también en las pruebas que lo llaman.
- `ViajeTransporte` se crea siempre con `empresa=reserva.empresa`.
- `ViajeTransporte` no se puede crear ni borrar a mano (`has_add_permission`/`has_delete_permission` en `False`).

## 8. Pruebas

- **Modelo:** capacidad, bloqueo de día completo y de rango, viaje sin hora, vehículo de otra empresa, viaje cancelado.
- **Sincronización:** los tres tipos, idempotencia, cambio de fecha quita el vehículo, cambio de tipo, cancelar (quita el vehículo) y reactivar, no pisa la hora del regreso, el alta posterior del detalle, borrar el detalle, reserva de paquete o sin detalle, **un fallo en el gancho no impide guardar la reserva ni el pago** (se simula la excepción), el comando de reparación, la migración de datos con RLS (Postgres).
- **Bloqueos:** no se puede bloquear un vehículo con viajes asignados ese día/hora.
- **Admin:** asignar desde la lista, el selector solo ofrece los que caben, filtro, resumen, aviso de empalme, permisos por rol, aislamiento entre empresas.
- **Postgres (RLS):** aislamiento de las tres tablas.

## 9. Plan de ejecución (delegado a agy; revisión, pruebas y commits por Claude)

1. Modelos (`Vehiculo`, `VehiculoNoDisponible`, `ViajeTransporte`), migraciones con sus políticas RLS y la validación.
2. `sincronizar_viajes` y su envoltura segura, los ganchos, el comando de reparación y la migración de datos.
3. Admin de Vehículos y Vehículos no disponibles, menú y `setup_roles`.
4. Admin de Traslados.
5. Documentación en `backend/CLAUDE.md`.

## 10. Riesgos

- `Reserva.save()` ya es delicado: el gancho va **después** de guardar y dentro de su propio savepoint (ver §5).
- Una reserva de transporte sin `detalle_transporte` no genera viajes; se anota, no se inventan.
- Quitar el vehículo al cambiar la fecha es una decisión conservadora: obliga a reasignar, pero nunca deja una asignación inválida.
