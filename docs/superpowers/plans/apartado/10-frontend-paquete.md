# Tarea 10: frontend de paquetes de una empresa y verificación del traslado

Lee del spec: §4.6 (la fila «Paquete de una empresa» y la de «Traslado» de la tabla, y los puntos 2 a 5). La tarea 09 ya cambió `errores.ts`, `api.ts` y el flujo de servicio suelto; reutiliza lo que dejó.

## Qué hacer
1. `frontend/src/components/pedido/use-pago-pedido.ts` y `pedido-paquete.tsx`: el hook es dueño de `crearPago`, `forma_pago` y el código promocional. Añade: rama `sin_cupo` en `ejecutarEnvio` (hoy cualquier error va por `mensajeDeError` a `setFase('formulario')`): vuelve a `formulario` con el aviso «El cupo de tu itinerario se agotó; elige otra fecha de inicio» (sin `proxima_disponible`, que es `null` para paquetes) y los datos del pedido en memoria; la línea fija del apartado y la renovación en cada clic de «Pagar» (`antesDePagar` implementado en el hook y pasado a `StripePanel`, que `pedido-paquete.tsx` renderiza en dos sitios), reenviando idénticos `forma_pago` y código promocional y pidiendo confirmación si el monto cambia; reutiliza la fase `confirmando` (hoy consulta cada 5 s: ajústala a 2 s), el estado `cancelada`, y `reiniciar`/`soltarIntentoAnterior` (genera `checkout_id` nuevo) con el reinicio del widget de Turnstile; los mismos textos de la tarea 09 (claves ya existentes en los diccionarios) más las que falten, en es y en.
2. `frontend/src/components/traslado-view.tsx`: el traslado es `bajo_demanda` y no aparta; solo verifica que el nuevo mapeo por `codigo` de `errores.ts` no cambie su comportamiento. No añadas funcionalidad; si necesita un ajuste mínimo, hazlo y dilo.

## Verificación
`npx tsc --noEmit` sin errores nuevos y `eslint` sobre los archivos tocados sin errores nuevos.
