# Tarea 11: aviso de fecha cambiada en el enlace (independiente del apartado)

Lee del spec: §4.6 punto 7 y §1 punto 4.

## Contexto
`frontend/src/app/[lang]/reservar/page.tsx` y `frontend/src/lib/dates.ts` (`parseBookingQuery`): si el parámetro `day` del enlace es una fecha pasada, mal formada o inexistente, el sitio la descarta y usa «mañana» (`getMinBookableDate`) EN SILENCIO.

## Qué hacer
Cuando el enlace trae `day` y `parseBookingQuery` lo descarta, el checkout de servicio suelto muestra UNA vez el aviso «Actualizamos la fecha de tu viaje al {fecha}» (hay una clave `feedback.dateChanged` ya existente en `es.json`/`en.json`: reutilízala). La señal de «se descartó la fecha» debe llegar desde `page.tsx` al componente cliente (`CheckoutView`) como una prop pequeña (p. ej. `fechaDescartada: boolean`); no cambies la firma de las funciones de `dates.ts` de forma incompatible con otros llamadores (busca los usos con grep antes). Un enlace sin `day` NO muestra el aviso. No toques el flujo de paquetes.

## Verificación
`npx tsc --noEmit` sin errores nuevos y `eslint` sobre los archivos tocados sin errores nuevos.
