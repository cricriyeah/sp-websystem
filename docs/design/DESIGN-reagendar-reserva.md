# DESIGN: Vista «Reagendar» del backoffice

Derivada con perception-first-design (Modo 2, 2026-10-28) sobre `docs/architecture/ARCH-reagendar-reserva.md`. Es el contrato visual y de texto para quien arma `templates/bookings/reagendar.html` y `static/bookings/reagendar.css`. Sin taste: se hereda el lenguaje del admin (Unfold) y la regla de formas del dueño (esquinas rectas o círculo, sin sombras ni degradados, sin líneas finas decorativas).

## Requisitos derivados (no negociables)

- **R1 (L0, carga):** una decisión por pantalla y no más de 4 bloques a la vez. Paso 1 = elegir fecha (y hora). Paso 2 = Antes → Ahora, consecuencias, una casilla, un botón. Los campos condicionales (fecha de regreso, motivo de excepción) solo existen cuando aplican.
- **R2 (L1, primera impresión):** en un vistazo se sabe qué reserva es, qué se está haciendo («Reagendar») y, en el paso 2, qué cambia. El «Antes → Ahora» es el elemento de mayor peso.
- **R3 (L2, fluidez):** un solo formato de fecha en toda la vista y en el correo; Antes y Ahora con la misma forma, alineados, y se resalta solo el valor que cambió.
- **R4 (L3, sesgo):** el punto de referencia es la fecha actual. Se dice qué se libera y qué se conserva. Cero urgencia falsa. Los controles donde se esperan.
- **R5 (L4, decisión):** el valor por defecto sirve a la meta de la persona (que el cliente se entere). La etiqueta del botón predice el resultado. Un solo primario; lo demás pesa menos.

## Composición

Una columna, ancho de lectura (máx. ~44 rem), dentro de la página normal del admin de Unfold (título + migas). Tres zonas apiladas:

1. **Encabezado fijo de la reserva** (ambos pasos): `Reagendar reserva #123` y debajo, en una línea, `Ana Ruiz · Pesca deportiva · Sal y Sol Sportfishing · 3 personas`.
2. **Zona de trabajo** (cambia por paso).
3. **Barra de acción** al final de la zona de trabajo, botón primario a la derecha y enlace secundario a la izquierda.

### Paso 1 · Elegir

- Título de zona: `¿Para cuándo?`
- Bloque «Ahora»: una línea de solo lectura, `Ahora: martes 8 de diciembre de 2026 · 6:00 a. m.` (misma forma que en el paso 2).
- Campo `Nueva fecha` (entrada de fecha nativa del admin, ancho completo en móvil, ~16 rem en laptop) y, si la reserva tiene hora o el servicio tiene ventana, `Nueva hora` al lado.
- Solo en traslado redondo de aeropuerto: `Nueva fecha de regreso`, justo debajo.
- Solo en servicios de mar: `Próximas fechas con lugar` con **hasta 5** opciones tipo chip circular/píldora (`mié 9 dic`, `jue 10 dic`…). Tocar una llena el campo `Nueva fecha`. Si no hay lugar en los próximos días: `No hay lugar en los próximos 60 días.`
- Ayuda bajo la fecha, gris: `Se revisa el lugar y la panga antes de confirmar.`
- Botón primario: `Revisar cambio`. Enlace secundario: `Volver a la reserva`.

### Paso 2 · Revisar y confirmar

- Título de zona: `Revisa antes de confirmar`
- **Héroe Antes → Ahora** (dos filas con la misma forma, alineadas en columna):
  - `Antes` · `martes 8 de diciembre de 2026 · 6:00 a. m.` (peso normal, color de texto secundario)
  - `Ahora` · `miércoles 9 de diciembre de 2026 · 6:00 a. m.` (peso grande/negrita; **solo la parte que cambió** va resaltada: la fecha, la hora, o ambas)
  - Paquete: filas extra `Llegada` y `Salida`. Traslado redondo: fila `Regreso`.
- **Consecuencias** (frases cortas, máximo 4, ordenadas por importancia, sin viñetas decorativas):
  1. `El cliente recibirá un correo con la nueva fecha.` (o, con la casilla desmarcada: `No se avisará al cliente. Avísale tú.`; o, sin correo: `El cliente no tiene correo. Avísale por WhatsApp.`)
  2. Mar con panga/capitán: `Se conservan la panga {nombre} y el capitán {nombre}.` / `Se quita la panga {nombre}: hay que asignar otra en «Asignar pangas».` / `Avísale al capitán {nombre} del nuevo día.`
  3. Traslado con vehículo: `Se quita el vehículo {nombre}: asígnalo de nuevo en «Asignar vehículos».`
  4. `El pago no cambia. El lugar del {fecha antes} queda libre.`
- **Casilla** (marcada por defecto): `Avisar al cliente por correo`. Con correo del cliente, ayuda en gris: `Ana Ruiz · a***@correo.com`. Sin correo: deshabilitada y desmarcada, ayuda `Esta reserva no tiene correo.`
- **Aviso de 48 horas** (solo si aplica; va en línea, entre el héroe y las consecuencias, en el color de aviso del admin):
  - Jefe/operador: `Faltan menos de 48 horas para la salida original. Como jefe puedes autorizar el cambio.` + campo obligatorio `Motivo de la excepción` (10 a 200 caracteres), ayuda `Queda registrado en el historial y avisa a toda la empresa.`
  - Vendedora (bloqueo, sin botón de confirmar): `Faltan menos de 48 horas para la salida original, así que no se puede reagendar desde aquí. Pídele a un jefe que lo autorice.` + solo enlace `Volver a la reserva`.
- **Barra de acción:** primario `Reagendar y avisar al cliente` (casilla marcada) / `Reagendar` (desmarcada). Secundario a la izquierda: `Cambiar la fecha` (vuelve al paso 1 con lo tecleado).

## Estados

| Estado | Qué se ve |
|---|---|
| Cargando (enviar) | Botón primario deshabilitado con texto `Reagendando…`; el resto de la vista no se mueve. Evita el doble clic (el token optimista del ARCH es la segunda defensa). |
| Error de campo (paso 1) | El mensaje del servicio bajo el campo afectado, en rojo del admin, con la acción: ej. `Elige una fecha distinta de la actual.` / `Ese día ya no hay lugar. La próxima fecha con lugar es el jueves 10 de diciembre.` Los datos tecleados se conservan. |
| Error general (paso 2) | Banda de error arriba de la zona de trabajo con el mensaje en español y lo que hacer (`Esta reserva cambió mientras la revisabas. Revisa y vuelve a elegir.`). Botón `Cambiar la fecha`. |
| Bloqueo (no reagendable) | No se muestra formulario. Una banda de aviso con el motivo del servicio (`Esta reserva está cancelada: solo se reagendan reservas pagadas o asignadas.`) y el enlace `Volver a la reserva`. |
| Bloqueo 48 h vendedora | Ver arriba: sin botón de confirmar. |
| Éxito | Se redirige a `volver` (lista, calendario o ficha). Aviso verde del admin y notificación: `Reagendaste a Ana Ruiz al miércoles 9 de diciembre. El correo sale en unos segundos; si no sale, te avisa Notificaciones.` Si hubo excepción o no se avisó, el aviso es ámbar y lo dice (`Reagendada sin avisar al cliente. Avísale tú.`). |

## Formato único de fecha y hora (R3)

`martes 8 de diciembre de 2026 · 6:00 a. m.` en la vista, el aviso y el correo. Sin hora: `martes 8 de diciembre de 2026`. Las notificaciones usan la forma corta `8/12/2026` ya establecida en el feed y no se mezclan con la vista.

## Botones «Reagendar» fuera de la vista (misma palabra exacta)

- Lista de reservas: acción de fila `Reagendar`.
- Calendario (popover de Semana y Día): botón `Reagendar` junto a `Abrir reserva`.
- Ficha de la reserva: botón `Reagendar` junto a los demás del resumen.

## Qué NO poner

- Ningún campo de la reserva más allá de fecha, hora, regreso, casilla y motivo (no es el formulario de edición).
- No mostrar precio, IVA ni saldo: el pago no cambia y mostrarlo invita a dudar.
- No usar modal para el aviso de 48 horas ni para confirmar: va en línea.
- No usar cuenta regresiva, rojo de alarma ni mayúsculas para la urgencia: la regla de 48 horas se explica con una frase.
- No un calendario de mes completo: la entrada de fecha nativa más 5 fechas con lugar bastan.
- No sombras, degradados, líneas finas decorativas ni esquinas con radio intermedio (rectas o círculo).
- No clases de Tailwind nuevas: todo el CSS va en `static/bookings/reagendar.css` con variables propias y modo oscuro.
- No emoji ni íconos decorativos; el aviso usa solo el color del admin.
- No segunda confirmación «¿estás seguro?»: el paso 2 ya es la confirmación.
- No un botón «Reenviar correo» ni «Enviar de nuevo» (fuera de alcance).

## Historial

- 2026-10-28 v1: derivación PFD Modo 2; ajusta el ARCH con tres adiciones: «el lugar del {fecha} queda libre» (punto de referencia), estado de carga del botón, y tope de 5 fechas con lugar.
