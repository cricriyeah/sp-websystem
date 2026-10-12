# Tarea 04: apartado de hospedaje

Lee del spec: §4.1 (retrato: `habitaciones`), §4.2 (hospedaje), §7.

## Qué hacer (en este orden)
1. **PRIMERO extrae** de `_asignar_cupo_hospedaje` (`backend/apps/bookings/cupo/confirmacion.py`) una función PURA `elegir_habitaciones(...)` (devuelve las habitaciones elegidas para el grupo y el rango, sin tomar candados ni crear `ReservaOcupacion`). Hoy la selección está mezclada con la toma de candados y la creación de filas. `_asignar_cupo_hospedaje` pasa a llamarla (mismo comportamiento: las pruebas existentes de ocupación deben seguir pasando). Haz determinista el orden de iteración de `servicio.recursos` (por `pk`; hoy no está ordenado).
2. `construir_retrato_hospedaje(reserva)` en `cupo/apartado.py`: usa `elegir_habitaciones` para elegir las habitaciones y devuelve las entradas `habitaciones` `{"recurso_id", "inicio", "fin", "servicio_id"}` del retrato (rango `[inicio, fin)`); integra con `construir_retrato_paquete` para paquetes con mar y hospedaje (un solo retrato con `salidas` y `habitaciones`). Si no hay habitaciones libres para el grupo, la función lo señala (excepción o valor que la tarea 05 convertirá en `sin_cupo`; elige y documenta).
3. **Motor**: `obtener_recursos_con_ocupaciones` (`cupo/adaptador.py`) suma a cada habitación los intervalos `[inicio, fin)` de las entradas `habitaciones` de los retratos vigentes del MISMO servicio, excluyendo la reserva evaluada, para que `recursos_disponibles_en_rango` y `PorNoche.evaluar_ocupacion` funcionen sin cambiar su lógica. NO se crean filas físicas.

## Pruebas (archivo nuevo `backend/apps/bookings/tests_apartado_hospedaje.py`)
Apartar y confirmar eligen LAS MISMAS habitaciones para el mismo grupo y rango; una habitación apartada aparece ocupada en su rango y solo para su servicio; la propia reserva se excluye a sí misma; un apartado vencido o con `APARTADO_MINUTOS=0` no cuenta; la restricción `EXCLUDE` de `ReservaOcupacion` nunca se entera (no se crean filas); un paquete con mar Y hospedaje arma un solo retrato correcto. Las pruebas existentes de ocupación/hospedaje (`tests_ocupacion.py`) deben seguir pasando sin cambios.
