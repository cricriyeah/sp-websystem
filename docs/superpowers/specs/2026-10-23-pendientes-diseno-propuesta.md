# Propuesta de diseño: seis pendientes de las pruebas de Stripe (2026-10-23)

Estado: propuesta, sin código. Cada pieza espera luz verde del dueño antes de implementarse.
Todo usa el lenguaje que ya tiene el sitio: esquinas rectas o círculo, campo de color por actividad
(mar = azul, traslado = coral hondo, estancia = verde), tinta y arena, `texto-grande` / `texto-paso` /
`texto-cuerpo`. Nada de gradientes, brillos ni tarjetas con sombra.

## 1. Turnstile: el error se dice en la línea, no en una tarjeta roja

**Qué pasa hoy.** Si el cliente pulsa «Pagar» sin haber marcado la verificación, el servidor contesta
`captcha` y el checkout lo pinta como cualquier fallo de red: tarjeta roja, texto genérico y botón de
WhatsApp. El cliente no sabe qué hacer; tiene que adivinar que falta la casilla.

**Propuesta.**
- La verificación se trata como un campo más de «Cómo pagas»: va debajo del deslinde, con su pregunta
  arriba («Verificación») y su mensaje de error en la línea (`ErrorDeCampo`, el mismo que usan el
  correo y el deslinde).
- Dos mensajes, según lo que ocurra:
  - Todavía no hay token y el widget está visible: «Marca la casilla para confirmar que eres una persona.»
  - Todavía no hay token y el widget no se ha mostrado (Cloudflare lo resuelve solo): «Estamos
    verificando, un momento…» y el botón queda en espera, sin error.
- Si el cliente pulsa «Pagar» sin token no se llama al servidor: se muestra el mensaje, se lleva el
  scroll y el foco a la verificación.
- Si el servidor aun así responde `captcha`, se muestra el mismo mensaje en la línea y se remonta el
  widget. Nunca la tarjeta roja ni WhatsApp.
- WhatsApp aparece solo por la regla que ya existe (`AyudaFlotante`, tras dos tropiezos).

## 2. «Tu reserva está protegida» pasa a «Si algo cambia»

**Qué pasa hoy.** Un título que afirma algo («protegida») sobre dos cuadros grises de texto. El título
es una promesa sin prueba y los cuadros pesan igual que cualquier dato de la página, así que el cliente
no se detiene ni encuentra el número que le importa.

**Propuesta.**
- El título deja de prometer y dice qué cubre: **«Si algo cambia»**.
- Dos renglones, cada uno con la cifra que ya existe en el diccionario como protagonista:
  - **100 %** · «Si el mal clima impide salir, te devolvemos todo.»
  - **48 h** · «Para cambiar la fecha sin costo.»
  La cifra va en `texto-paso` (tabular), a la izquierda, en una columna fija; el texto, a la derecha.
  Renglones separados por espacio de 8 px, sin cuadro de fondo (el fondo arena ya es el de la página).
- Debajo, una sola línea de salida: «¿Algo no cuadra? Escríbenos con tu folio» como enlace de texto a
  WhatsApp con el folio escrito. Ya existe el botón de WhatsApp grande: se queda el botón y el enlace se
  omite si ambos quedan juntos en pantalla.
- Va justo después de «Qué sigue», antes de las acciones.

## 3. Confirmación: una animación que dice «quedó», una sola vez

**Qué pasa hoy.** La confirmación aparece de golpe: un campo de color con «Reserva confirmada». Nada
marca el momento en que el pago pasó de dudoso a hecho.

**Propuesta.** Una secuencia corta (900 ms en total), una sola vez al montar, solo cuando el pago ya
está aplicado (no en «Pago en proceso»):
1. Un círculo de 56 px (64 px en escritorio) aparece a la izquierda del título con una palomita que se
   dibuja (trazo, 450 ms). El círculo es del color de la actividad en claro; la palomita, en tinta.
2. Una onda sale del círculo una sola pasada (ya existe `confirmacion-onda`; se baja a una pasada).
3. El título y el folio entran con el `revelar` que ya usa el sitio, 120 ms después.
- Sin confeti, sin sonido, sin rebote exagerado. Es una confirmación, no una celebración.
- «Reducir movimiento»: el círculo y la palomita aparecen ya dibujados, sin onda ni entrada.
- Pago en proceso: sin palomita; un punto quieto del mismo tamaño y el campo en tinta, como hoy.
- Se anuncia a lectores de pantalla con `role="status"`: «Reserva confirmada, folio N».
- En impresión no aparece el círculo.
- Acomodo: círculo + título en una fila a la izquierda; folio a la derecha como hoy. En móvil el
  círculo va arriba del título y el folio debajo.

## 4. Avisos de tarjeta rechazada: cerca de la tarjeta, con el motivo y sin ruido

**Qué pasa hoy.** El aviso sale al final del formulario, lejos de los campos de tarjeta, en
`texto-pequeno`, con el mismo texto sea cual sea el motivo («Tu tarjeta fue rechazada»), y con un botón
de WhatsApp en el primer fallo.

**Propuesta.**
- Sube y se pone **justo arriba del formulario de tarjeta**, en el flujo, y lleva el scroll y el foco
  al abrirse (`role="alert"` se queda).
- Primera línea, en `texto-cuerpo` (no pequeño) y negrita: el motivo concreto que ya traduce
  `fallo-pago.ts` («No hay fondos suficientes», «La tarjeta venció», «El código de seguridad no
  coincide», «Tu banco pidió verificar y no se completó»…). Si no hay motivo conocido, el genérico.
- Segunda línea con el dinero, con palomita: «No se hizo ningún cobro.» (o la retención de la otra
  empresa en un paquete de dos, como ya hace).
- **Una** acción principal: «Probar otra tarjeta», que limpia el campo de tarjeta y lo enfoca. Sin
  WhatsApp hasta el tercer fallo (regla que ya existe).
- Lo que escribió el cliente (nombre, correo, fecha) no se toca.
- Mismo fondo `error-fondo`, esquinas rectas, sin barra lateral ni ícono extra.

## 5. Correos con membrete

**Qué pasa hoy.** Los correos son HTML sin estilo: una lista con negritas, sin marca, sin folio
destacado, sin separar lo pagado de lo que se paga en efectivo, y con acentos faltantes («dia»,
«capitan»).

**Propuesta.** Una sola envoltura compartida (`envolver_correo`) para todos los correos al cliente:
confirmación (servicio, traslado, paquete y orden de dos empresas) y asignación de panga.
- Ancho 600 px, tablas con estilos en línea (los clientes de correo no entienden nada más), fuente del
  sistema, fondo arena `#fcf6ed` explícito para que el modo oscuro no lo invierta.
- **Banda superior** del color de la actividad (azul, coral hondo o verde) con el nombre de la empresa
  que opera el servicio, y «Sun Baja Experience» como marca. Sin imagen obligatoria: el nombre en texto
  siempre se ve; el logo se añade como imagen con texto alternativo cuando haya URL pública estable.
- **Folio grande** debajo de la banda: «Reserva confirmada · Folio #123».
- **Lo que reservaste**: filas etiqueta a la izquierda y valor a la derecha, igual que la página de
  confirmación.
- **El dinero**: dos bloques como en la página: «Pagaste hoy» en tinta y «Resto en efectivo el día del
  viaje» en arena clara, solo si hay saldo.
- **Qué sigue** en un párrafo y un botón de WhatsApp (botón de tabla, que sí se ve en Outlook) con el
  folio escrito.
- **Pie** con el nombre legal de la empresa, el punto de encuentro (el de cada empresa, no el fijo de
  hoy) y un aviso corto de que pueden responder al correo.
- Versión de texto plano con el mismo contenido en orden.
- Acentos corregidos. El correo interno «aviso a la empresa» se queda simple (es para la vendedora):
  solo gana la banda y el folio.

## 6. Comprobante: que se imprima bien en más de una hoja

**Qué pasa hoy.** «Guardar comprobante» llama a `window.print()` y la página no tiene estilos de
impresión completos: el campo de color y los bloques se cortan a media línea al pasar de hoja.

**Propuesta.** Solo CSS de impresión, la pantalla no cambia.
- Hoja carta/A4 con márgenes de 15 mm; el contenido en una sola columna.
- El campo de color se imprime blanco con texto en tinta y una raya inferior de 2 px del color de la
  actividad (ahorra tinta y no depende de «imprimir fondos»).
- Ningún renglón, tarjeta ni bloque de dinero se parte entre hojas (`break-inside: avoid`); los
  títulos de sección no quedan huérfanos al final de una hoja.
- Se ocultan cabecera, acciones y el círculo animado (ya ocurre con los dos primeros).
- El folio y la fecha de emisión se repiten en el pie de cada hoja.
- El título se reduce de 84 px a un tamaño de impresión (28 pt) para que quepa el folio al lado.

## 7. Cambios de la evaluación PFD (puntaje 71; estos cambios corrigen lo de arriba donde se contradicen)

**1. Turnstile: tres estados, no dos.** Widget visible esperando la casilla: «Marca la casilla…» y no se
llama al servidor. Verificando sin interacción: «Estamos verificando…», botón en espera con el tope de 8 s
que ya existe. Script caído o con error: se deja pasar y el servidor decide (el backend falla abierto a
propósito; un bloqueador de anuncios no debe dejar un checkout muerto). En móvil el mensaje va como
`razon` de la barra inferior, además de la línea.

**2. «Si algo cambia».** Sin «sin costo»: la fuente solo dice «puedes cambiar la fecha con al menos 48 horas
de anticipación»; la promesa de gratis no existe y se agrega solo si el dueño la confirma. «Te devolvemos
todo» pasa a «todo lo que pagaste» (hay anticipos). La cifra 100 % queda en `texto-paso`, sin crecer. Se
quita el enlace extra de WhatsApp (ya existe el botón grande). Revisar el texto en inglés.

**3. Animación.** Solo en la transición real: se marca por folio en `sessionStorage` y no se repite al
reabrir la confirmación desde «Continuar reservación» ni al recargar. El círculo va ARRIBA del título en
todos los anchos, alineado al borde izquierdo del contenido (no a la izquierda del título). Sin
`role="status"`: el `h1` ya lleva el texto.

**4. Aviso de tarjeta.** Sin palomita en «No se hizo ningún cobro» (una palomita sugiere éxito en un error);
solo texto. «Probar otra tarjeta» limpia el campo de tarjeta únicamente ante un rechazo del banco, nunca
ante un fallo de red ni de verificación 3D Secure (se borraría una tarjeta buena). Texto neutral:
«Tu banco rechazó el pago», sin culpar al cliente.

**5. Correos.** Jerarquía según el tipo: la confirmación abre con folio, día y hora; la asignación abre con
capitán, panga, hora y punto de encuentro en grande. Asunto con folio y fecha, texto de vista previa y
versión de texto plano. No prometer «responde a este correo» sin un `Reply-To` verificado. El pie usa el
punto de encuentro por servicio (ya existe en datos). Probar el modo oscuro de Gmail.

**6. Comprobante.** «Guardar comprobante» abre el diálogo de impresión, no descarga un archivo: la
etiqueta pasa a «Imprimir o guardar PDF». El pie con folio en cada hoja usa márgenes de página que solo
soportan los navegadores con Chromium; en los demás no sale (no es garantía). Antes de diseñar, ver una
impresión real para saber por qué se parte (sospecha: `min-h-dvh` más la rejilla de dos columnas).
