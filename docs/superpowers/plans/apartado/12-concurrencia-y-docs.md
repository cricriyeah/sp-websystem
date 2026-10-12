# Tarea 12: pruebas de concurrencia (Postgres) y documentación

Lee del spec: §5 (la parte «Postgres»: pruebas a-i) y §6 (Despliegue: actualizar `backend/CLAUDE.md`).

## Qué hacer
1. **Pruebas** en el archivo nuevo `backend/apps/bookings/tests_apartado_concurrencia.py`, en el estilo de `backend/apps/bookings/tests_concurrencia.py` (`TransactionTestCase`, `threading.Barrier`, `@SOLO_POSTGRES`; léelo entero antes). Casos: (a) dos `crear-pago` simultáneos por el último lugar de pesca: exactamente uno responde 200 y el otro 409 `sin_cupo`; (b) dos por la última habitación; (c) un paquete con mar y hospedaje donde un solo lugar basta para fallar: no queda ningún apartado a medias; (d) el candado se libera ANTES de la llamada a Stripe (la llamada a Stripe simulada se bloquea y una segunda petición toma el candado sin esperar); (e) un `crear-pago` repetido mientras el PaymentIntent está `processing`/`succeeded` no toca el apartado; (f) una renovación concurrente con el webhook de la misma reserva no produce deadlock; (g) una liberación tras un fallo de Stripe no borra el apartado renovado por otra llamada concurrente; (h) un candado no obtenido a tiempo responde `503 reintentar`; (i) si el intent pasa a `processing`/`succeeded` entre el Bloque A y el C, la respuesta es `pago_en_curso` y el apartado no se libera. Mockea Stripe como las pruebas de `apps/payments`. En SQLite todas se saltan.
2. **Documentación**: actualiza `backend/CLAUDE.md`: en «Cupo diario» y «Cupo multidimensional» la regla del apartado (campos, retrato, vigencia pasiva, `APARTADO_MINUTOS`, no toca `ESTADOS_QUE_OCUPAN_CUPO`), y en «Garantias del cobro» el orden de bloques de `crear-pago`, el contrato de errores con `codigo`, la liberación condicional y los avisos por causa (con `alerta_reembolso_fallido_en`). Texto conciso, en el mismo estilo.

## Verificación
`py_compile` del archivo de pruebas (las pruebas reales solo corren en Postgres; el runner las ejecuta si Docker está disponible).
