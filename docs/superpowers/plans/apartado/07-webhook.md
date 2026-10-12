# Tarea 07: webhook y apartado

Lee del spec: §4.4 (incluida la «consecuencia intencional»).

## Qué hacer
1. En el camino de pago exitoso (`apps/payments/services.py`: `aplicar_pago_exitoso` y `_aplicar_pago_exitoso_transaccional`; también lo usa `conciliar_pagos`), al pasar la reserva a `pagada` limpia `apartado_hasta` y `apartado_demanda`; al cancelarla (`_cancelar_sin_cupo`) también. Verifica que `reservar_cupo_al_confirmar` y `Reserva.clean()` NO lean el retrato de la propia reserva y la excluyan al contar (el motor ya acepta `excluir_pk`: confirma que todos los caminos lo pasan, incluido hospedaje).
2. Con `APARTADO_MINUTOS=0` el motor ignora cualquier apartado existente (ya lo hace el helper de la tarea 01): comprueba que el webhook se comporte como antes.
3. NO cambies la lógica de reembolso ni los avisos (tarea 08).

## Pruebas (archivo nuevo `backend/apps/payments/tests_apartado_webhook.py`)
Con apartado vigente la reserva se confirma y se limpian los dos campos; con apartado vencido y el lugar libre se confirma; con apartado vencido y otro cliente con apartado VIGENTE sobre el último lugar ⇒ se reembolsa (consecuencia intencional del spec) y se limpian los campos; un cliente con apartado vigente cuyo lugar tomó otro por vía normal no puede darse (el apartado lo protege): prueba que quien tiene apartado vigente gana frente a un tercero que intenta apartar el mismo lugar. `conciliar_pagos` aplica las mismas reglas (usa el helper de las pruebas existentes de conciliación).
