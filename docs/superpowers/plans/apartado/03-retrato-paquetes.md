# Tarea 03: retrato del apartado para paquetes de UNA empresa (actividades de mar)

Lee del spec: §4.1 (forma y reglas del retrato: «refleja la lista de validación»), §4.2.

## Qué hacer
En `backend/apps/bookings/cupo/apartado.py` agrega `construir_retrato_paquete(reserva)`: devuelve el retrato `{"v": 1, "salidas": [...], "habitaciones": []}` con UNA entrada de `salidas` por cada fecha de mar que `reservar_cupo_al_confirmar` (`backend/apps/bookings/cupo/confirmacion.py`) validaría para esa reserva, con las personas que esa función usaría (`personas_de(servicio_id)`; mira cómo calcula las fechas: `fechas_de_componente` y los componentes de una sola salida, que usan `Reserva.fecha`). Reutiliza las MISMAS funciones, no copies la lógica. Un paquete sin componentes de mar devuelve `salidas: []` (no cuenta). El hospedaje queda para la tarea 04: aquí `habitaciones` va vacío.

Verifica que el conteo del motor de la tarea 01 (`obtener_contexto_cupo`, `obtener_contexto_rango`) ya cuente esas entradas por fecha y que una reserva con apartado NO se cuente dos veces (su retrato es la única fuente mientras está `pendiente_pago`; no tiene `ReservaSalida`). Si el motor necesita un ajuste para sumar entradas de varias fechas de un mismo retrato, hazlo en `cupo/adaptador.py` sin tocar `ESTADOS_QUE_OCUPAN_CUPO`.

## Pruebas (archivo nuevo `backend/apps/bookings/tests_apartado_paquetes.py`)
Un paquete con salidas multidía: el retrato trae una entrada por fecha y cuenta en cada una; un paquete que mezcla componentes de una sola salida y de varias salidas (sin hospedaje): la lista de fechas del retrato coincide con la de `reservar_cupo_al_confirmar` para la misma reserva; un paquete sin mar no cuenta; con `APARTADO_MINUTOS=0` no cuenta; el sobre-apartado de un día de más (si existe) está fijado por una prueba que dice cuál lista manda. Mira `tests_paquete_estancia.py` y `tests_salidas.py` para crear paquetes con componentes.
