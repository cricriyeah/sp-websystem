# Paquetes: precio por persona y actividades en varios días — diseño

Fecha: 2026-10-01. Estado: **borrador para aprobación del dueño, sin código**.

## Por qué

La Ventana Travel vende dos paquetes de una sola empresa, escritos por el cliente:

| Paquete | Mar | Hospedaje | Traslado | Precio |
|---|---|---|---|---|
| A | 4 días saliendo al mar | 5 noches | aeropuerto redondo | $45,000 MXN **por persona** |
| B | 6 días saliendo al mar | 7 noches | aeropuerto-hotel-aeropuerto | $52,500 MXN **por persona** |

El sistema de hoy no puede venderlos por dos razones.

## Cambio 1 — Precio por persona del paquete

**Hoy.** `Paquete.precio_ancla` es un total fijo (`pricing.precio_paquete_total`,
`pricing.py:144`): no se multiplica por personas. Solo las personalizaciones cobran por persona.
`PaqueteServicio.personas_incluidas` limita lugares, no precio.

**Propuesta.** Un campo nuevo en `Paquete`, `precio_por_persona` (booleano, default `False`
para no tocar los paquetes existentes).

- Con `False`: igual que hoy.
- Con `True`: `precio_ancla` (y `precio_ancla_usd`) es el precio de **una** persona y el total
  es `ancla × personas` (más extras, que ya van por su cuenta).
- El número de personas es **uno por pedido**, no uno por servicio. En un paquete por persona
  no tiene sentido que dos servicios lleven grupos distintos; `personas_por_servicio` se
  ignora y el servidor usa `numero_personas`.

**Puntos que cambian:**
1. `pricing.precio_paquete_total` y `calcular_precio_paquete`: multiplicar.
2. `Paquete.validar_configuracion()` compara el ancla contra la peor tarifa de transporte. Con
   precio por persona, la comparación es contra `ancla × personas` para la peor tarifa que
   aplica a ese número de personas, no contra una persona.
3. Reparto cruza-empresa (`monto_por_empresa`): el residuo de la líder pasa a ser
   `ancla × personas − tarifa de transporte`. La regla de reparto no cambia.
4. Anticipo: el porcentaje se aplica sobre el total ya multiplicado.
5. Frontend: el selector de personas del paquete y el desglose de cargos muestran el precio
   por persona y el total. Requiere pasar por tu revisión visual antes de construir.
6. Admin: el campo nuevo, con texto de ayuda claro.

**Riesgo.** Bajo. Es aditivo y el default conserva el comportamiento.

## Cambio 2 — Una actividad que se repite en varios días

**Hoy.** Tres reglas lo impiden:
- `PaqueteServicio` es único por `(paquete, servicio)`: un servicio aparece una vez.
- `paquete_reglas`: *"Las actividades del paquete deben ocurrir el mismo día de la estancia"*.
- **Lo importante:** el cupo de pesca y paseos se cuenta por `Reserva.fecha` (un solo día por
  reserva). `evaluar_cupo` agrupa las reservas por esa fecha. Si una reserva tuviera cuatro
  días de mar, solo ocuparía cupo uno de ellos y **los otros tres se podrían sobrevender**. La
  agenda (`Reserva.embarcacion` y `Reserva.capitan`, uno por reserva) y la regla de "una
  panga, una salida por día" tienen el mismo problema.

**Diseño propuesto: tabla de salidas.** Nuevo modelo `ReservaSalida`
(`reserva`, `servicio`, `fecha`, `embarcacion`, `capitan`, `ocupa_cupo`). Es el mismo patrón
que `ReservaOcupacion` ya usa para las noches de hospedaje.

- `PaqueteServicio` gana `dias_estancia` (lista de días, p. ej. `[2, 3, 4, 5]`) además de
  `dia_estancia`, o cambia a una cantidad `salidas`. La regla "mismo día" se relaja:
  se permiten varias salidas del mismo servicio, no actividades distintas el mismo día solapadas.
- Al confirmar el pago, `reservar_cupo_al_confirmar` crea una `ReservaSalida` por cada día y
  valida cupo en cada fecha; si falta cupo en cualquiera, sigue el rollback y reembolso 100 %
  que ya existe.
- `obtener_contexto_cupo` suma las `ReservaSalida` de esa fecha al conteo de grupos, junto con
  las reservas de un solo día. Así una salida de paquete y una reserva suelta compiten por la
  misma panga.
- La agenda lista salidas, no reservas, para el reparto de panga y capitán por día.
- Cancelar la reserva libera todas sus salidas (como hoy con componentes y ocupaciones).

**Alternativa descartada: una reserva por día.** Dejaría el motor de cupo y la agenda
intactos, pero cada reserva lleva su propio `PaymentIntent`, y un pedido tendría que cobrarse
una sola vez. Habría que reescribir pagos y la lógica de órdenes: más riesgo que la tabla de
salidas.

**Riesgo.** Alto. Toca cupo, agenda, confirmación de pago, cancelación, conciliación y el
calendario del paquete en backend y frontend. Necesita su propio plan con pruebas en SQLite y
en Postgres (los constraints y locks solo se prueban de verdad en Postgres).

## Orden de ejecución

1. Cambio 1 (bajo riesgo) con su plan y pruebas.
2. Cambio 2 con plan propio.
3. Catálogo de La Ventana Travel: servicio de hospedaje con habitaciones, servicio de traslado
   de aeropuerto y los dos paquetes.
4. Actualizar `frontend/src/content/sedes-cuerpo.ts` (hoy lista a Hotel Malecón y habla de
   La Ventana y Puerto Chale como "próximamente").

## Decisiones abiertas

1. **¿Cuántos días de mar en cada paquete, y cuáles?** El texto del cliente dice "4 días
   saliendo al mar, 5 noches". No dice si el mar cae los días 1 a 4, 2 a 5, o con descansos.
2. **¿La Ventana Travel es dueña del hospedaje, o lo contrata fuera?** Los paquetes son de una
   sola empresa, así que el sistema necesita un servicio de hospedaje con habitaciones suyo.
   ¿Cuántas habitaciones y de qué capacidad?
3. **¿Qué precio en USD tienen los paquetes?** Hoy el cliente dio solo MXN.
4. **¿El traslado de aeropuerto es de La Ventana Travel?** Si lo da DLS Transporte (La Paz),
   el paquete sería cruza-empresa y cruza sedes, y el sistema lo prohíbe: el servicio tiene que
   estar en la misma sede del paquete.
