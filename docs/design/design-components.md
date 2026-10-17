# Sun Baja Experience — Componentes

> Especificaciones de los componentes y de la página de reserva. Valores de tokens en [design.md](design.md); reglas de accesibilidad y qué hacer / qué no en [design-guidelines.md](design-guidelines.md).

Agrupados por flujo de trabajo. Las medidas están en px. «(inferido)» marca valores deducidos del lenguaje de diseño que el dueño no dio explícitamente.

---

## Acciones

### Botón

**Variantes:** Principal (relleno `cafe`) > Secundario (blanco con borde `borde-control`, texto `cafe`) > Texto (sin relleno, texto `cafe`) > Destructivo (relleno `error`).
Alto 48 (móvil) / 44 (escritorio). Radio `radio-control` 12. Etiqueta 16/600, caja de oración. Padding horizontal 24. Con icono: 8 de espacio.

| Propiedad | Valor |
|---|---|
| Contraste | Principal 8,46:1; destructivo 6,54:1 |
| Estados | Reposo, hover (+8 % tinta), pulsado (+12 %, escala 0,98), enfoque (anillo `azul`), deshabilitado (`cafe-bruma` + `apagado`) |
| Objetivo táctil | 48 × 48 mínimo |
| Un solo principal por paso | Sí |

**Haz:** etiqueta que diga destino o resultado («Continuar a tus datos»); mostrar el motivo cuando está deshabilitado.
**No hagas:** «Siguiente» ni «Enviar» solos; dos botones principales en la misma vista; botones principales en azul, coral o verde.

---

### Botón de icono (flecha de volver)

Área 48 × 48, icono 24 (flecha izquierda, peso bold), radio completo, fondo transparente con hover `cafe-bruma`. Etiqueta accesible «Volver al paso anterior». Arriba a la izquierda en móvil; en el primer paso vuelve a la página anterior (la ficha del tour).

| Propiedad | Valor |
|---|---|
| Contraste | icono `tinta` 17,27:1 sobre blanco |
| Foco | anillo `azul` |

---

### Enlace

Texto `cafe`, subrayado solo al enfocar o pasar el cursor. Dentro de una oración (deslinde, términos) va subrayado siempre.

---

## Entrada

### Campo de texto

Alto 48, radio 12, fondo blanco, borde 1 px `borde-control`, texto 16 `tinta`, etiqueta arriba (14/600), ayuda abajo (14 `apagado`). Placeholder `apagado` (nunca sustituye a la etiqueta).

| Propiedad | Valor |
|---|---|
| Contraste | Borde 4,15:1; texto 17,27:1 |
| Estados | Reposo, enfoque (borde `azul` 2 px), error (borde y texto `error` + icono + mensaje), deshabilitado |
| Error | Mensaje bajo el campo, siempre montado (reserva espacio), `role="alert"`; el foco va al primer campo con error |

**Haz:** `autocomplete` correcto (nombre, correo, teléfono), teclado adecuado (`tel`, `email`).
**No hagas:** pedir el dato dos veces ni más de ~7 campos por paso.

---

### Selector (lista corta)

Mismo cuerpo que el campo; despliega una lista con opciones de 48 de alto. Para listas largas, buscador interno. No se usa el `<select>` nativo.

---

### Casilla / opción / interruptor

Casilla 24 × 24 con área de 48; radio 6; marcada = relleno `cafe` con palomita blanca. Opción de radio: círculo de 24. Interruptor 52 × 32. Etiqueta siempre a la derecha, clicable.

---

### Contador de personas

Dos botones secundarios circulares de 48 con valor central en 20/600. Respeta el máximo del servicio y, al tocar el tope, explica «Máximo N personas» en lugar de ignorar el toque.

---

### Código promocional

Botón de texto «¿Tienes un código?» que despliega el campo con la misma animación de las tarjetas. El mensaje de éxito o error aparece dentro del bloque, sin saltos.

---

## Navegación

### Cabecera mínima (página de reserva)

Sustituye al navbar completo: **flecha de volver** a la izquierda, **logo redondo** de 32 al centro, **selector de idioma ES/EN** a la derecha. Alto 56, fondo `arena`, sin sombra, línea inferior `borde`. En móvil queda fija (contiene «volver»); en escritorio no se fija. Define `--nav-alto`: 56 px en móvil y 0 en escritorio.

---

### Línea de progreso (móvil)

Tres segmentos de 4 px de alto y radio completo, 8 de espacio entre ellos, ancho total del contenido. Completado = `cafe`, actual = `cafe` con el segmento siguiente en `cafe-claro`, pendiente = `cafe-claro`. **Sin números.** Va **encima** del botón de avanzar. Para lectores de pantalla: una `<ol>` con `aria-current="step"` y el texto «Paso 2 de 3: Tus datos»; no `role="progressbar"`.

---

### Pestañas / asa «Ver resumen» (móvil)

Una fila de 48 de alto (área táctil; la píldora visual es de 40) sobre la barra inferior que dice «Ver resumen · $4,100 MXN» y abre una hoja modal con el resumen completo. Es la única manera de ver los cargos de dos empresas en móvil sin ocupar pantalla.

---

## Contención

### Tarjeta de paso (escritorio ≥ 1024 px)

**Plegable y expandible, una sola abierta a la vez.** Fondo blanco, borde 1 px `borde`, radio 16, **sin sombra**.

| Parte | Especificación |
|---|---|
| Cabecera | Siempre visible. Etiqueta del paso en 14/600 `apagado` («Paso 1 de 3») y **título del paso en 28/700 mono** («Viaje», «Tus datos», «Pago») |
| Estado cerrado completado | Una línea: título + resumen de la respuesta («Sábado 7 de nov · 2 personas») + «Modificar» en texto `cafe` |
| Estado abierto | Contenido del paso + un solo botón principal al pie |
| Estado pendiente (aún no alcanzado) | Solo cabecera, título en `apagado`, no abre |
| Animación | Altura y opacidad 250 ms con `curva-estandar` |

Padding 24 (32 en pantallas grandes). El foco pasa al título de la tarjeta que se abre. Las tarjetas completadas siguen montadas.

**Haz:** que el título diga el nombre del paso exacto; reservar el espacio de lo que aparece.
**No hagas:** abrir dos tarjetas a la vez; poner números grandes como adorno.

---

### Asistente de un paso (móvil < 640 px)

Sin tarjetas plegables: se ve **un solo paso a la vez**.

```
┌──────────────────────────────┐
│ ←        (logo)         ES/EN│  cabecera mínima (56)
├──────────────────────────────┤
│ Reserva tu pesca  (36 mono)  │  título de la página
│ Paso 2 · Tus datos           │  nombre del paso (24 mono 700)
│ …campos del paso…            │
│                              │
├──────────────────────────────┤  nivel 1 de sombra (hacia arriba)
│ Ver resumen · $4,100 MXN   ▲ │  asa
│ ▬▬▬▬ ▬▬▬▬ ▭▭▭▭               │  línea de progreso
│ [ Continuar a pago        ]  │  botón principal 48 de alto
└──────────────────────────────┘  pegado al borde (con safe-area)
```

- La barra inferior es fija, con `padding-bottom: env(safe-area-inset-bottom)`, fondo blanco y nivel 1 de sombra.
- El botón ocupa todo el ancho útil (menos 16 de margen) y su etiqueta nombra el destino: «Continuar a tus datos», «Continuar a pago», «Pagar $4,100 MXN a Sal y Sol».
- Cada paso nuevo desliza desde la derecha; al volver, desde la izquierda. Con movimiento reducido, solo opacidad.
- El foco va al nombre del paso.

---

### Tarjeta de resumen («Resumen de tu reserva»)

Escritorio: columna derecha de 360, `position: sticky`. Fondo blanco, borde 1 px `borde`, radio 16, **sin sombra (elevación 0)**. Contenido: nombre del servicio o paquete, fecha, personas, líneas de extras, cargos por empresa, total en 20/700 con `tabular-nums` y, si difiere, «Pagarás ahora». Móvil: se abre en una hoja desde el asa «Ver resumen».

| Propiedad | Valor |
|---|---|
| Total | Siempre igual al cobro real |
| Dos empresas | Un renglón por cargo con empresa, monto y, si aplica, «se retiene hasta confirmar el otro pago» |

---

### Hoja modal (móvil)

Sube desde abajo, esquinas superiores `radio-sheet` 24, asa de 4 × 40, fondo blanco, nivel 2 de sombra, fondo atenuado. Se cierra con `Esc`, tocando fuera o con el botón «Cerrar».

---

### Divisor

1 px `borde`. En tarjetas se prefiere separar con espacio (24) antes que con líneas.

---

## Página de reserva — resumen de cambios aplicados

Cada punto de la petición del dueño y dónde queda especificado:

| # | Petición | Especificación |
|---|---|---|
| 1 | Quitar el navbar | Cabecera mínima (arriba) |
| 2 | Quitar los pasos | Se quita **solo el stepper numerado**; los pasos siguen con nombre |
| 3 | Título más grande | Título de página 36 px móvil / 56 px escritorio (design.md) |
| 4 | Quitar la sombra grande del resumen | Tarjeta de resumen: elevación 0 |
| 5 | Sin booking bar | Siempre el calendario completo (abajo) |
| 6 | Calendario blanco con leyenda y atajos | Calendario (abajo) |
| 7 | Tarjetas con el paso en el título y más grandes | Tarjeta de paso: título 28 px con «Paso N de 3» |
| 8 | Pedir datos personales con el pago | **No**: contacto + detalles en «Tus datos»; el pago queda solo (3 pasos) |
| 9–12 | Móvil: un paso, Siguiente abajo, progreso sin números, flecha atrás | Asistente de un paso |
| 13 | Previsualizar noches y pintar al final | Calendario, rango (abajo) |

Pasos: **1 Viaje** (fecha, personas, extras del viaje) · **2 Tus datos** (contacto, hotel o punto de recogida, notas) · **3 Pago** (resumen de cargos, cómo pagas, tarjeta). El orden de las preguntas dentro de cada paso lo define el flujo actual; el recuento de campos de «Tus datos» debe verificarse (≤ ~7).

---

## Selección de fecha

### Calendario completo

Siempre visible en el paso «Viaje» (no hay barra de reserva). **Fondo blanco**, borde 1 px `borde`, radio 16, sin sombra, dentro de la tarjeta del paso.

| Parte | Especificación |
|---|---|
| Encabezado de mes | Mes y año en 20/600; flechas ‹ › de 48 × 48 a los lados; deslizar horizontal en móvil |
| Día | Círculo de 44 × 44, número 16/500. Eco del logo |
| Semana | Empieza en lunes (inferido); letras de día en 12 `apagado` |
| Atajos | Tres chips en una fila encima del mes: **Borrar fecha** (con ×), **Mañana**, **En 2 días**. 44 de alto, radio completo, borde `borde-control`; son valores por defecto editables |

El calendario nunca captura el scroll vertical.

### Leyenda de colores (guía)

Una fila bajo el calendario, hecha con **los mismos componentes que las celdas**, para que cuadre con lo que se ve. Cada estado tiene color **y** forma:

| Estado | Apariencia | Significado |
|---|---|---|
| Disponible | Círculo blanco, número `tinta` | Hay lugar ese día |
| Sin cupo | Rayado diagonal, número `apagado` tachado | No se puede elegir (solo donde el sistema ya lo sabe: cupo de pangas por día; el cupo definitivo se valida al pagar) |
| Hoy | Anillo `azul` de 2 px | Fecha actual |
| Tu selección | Relleno `cafe`, número blanco | Día elegido |
| Vista previa | Relleno `cafe-bruma`, borde discontinuo `cafe` | Días que se tomarían (provisional) |
| Rango confirmado | Relleno `cafe-claro`, número `cafe-profundo`, extremos en `cafe` | Todos los días del paquete elegido |

Contrastes: número blanco sobre `cafe` 8,46:1; `cafe-profundo` sobre `cafe-claro` 11,84:1; `apagado` sobre blanco 6,37:1.

**Ojo (medido):** los rellenos suaves (`cafe-claro` 1,27:1 y `cafe-bruma` 1,18:1 contra blanco) no bastan por sí solos para distinguir un estado (WCAG pide 3:1 en indicadores). Por eso el rango confirmado lleva extremos en `cafe` (8,46:1) y la vista previa lleva borde discontinuo `cafe`: la señal es el borde y los extremos, el relleno solo acompaña.

### Paquetes de varias noches (duración fija)

1. Al pasar el cursor o enfocar un día, se pinta la **vista previa** (provisional): desde ese día hasta el último día del paquete, con borde discontinuo. Si el rango incluye un día que el sistema ya sabe lleno (cupo de pangas), ese día se marca con el rayado de «Sin cupo» y una línea dice cuál es. No hay estado «pocos lugares» ni corte por cupo de hospedaje: el cupo definitivo se valida al pagar.
2. Al elegir el día de inicio (clic, toque o `Enter`), **todos los días del rango se pintan firmes** (`cafe-claro`, extremos `cafe`) y el resumen muestra «Del 7 al 10 de nov · 3 noches».
3. Para cambiar, se toca otro día de inicio o «Borrar fecha». En móvil, sin cursor, el primer toque muestra la vista previa y el segundo toque sobre el mismo día confirma; un toque en otro día mueve la vista previa.

El tope de noches lo da el paquete (nunca se escribe en el cliente).

### Hoja del calendario en móvil

El calendario ocupa el ancho completo del paso; no se abre en un popover.

---

## Datos y presentación

### Insignia de actividad (chip)

Radio completo, alto 28, 14/600. Mar: fondo `azul-claro`, texto `azul`, icono de ola. Ciudad: fondo `coral-claro`, texto `coral-texto`, icono de edificios. Outside / montaña: fondo `verde-claro`, texto `verde`, icono de hoja o montaña. Siempre con icono y texto.

### Tarjeta de servicio / paquete

Blanco, borde `borde`, radio 16, foto arriba cuando exista (relación 4:3, esquinas superiores 16), chips de actividad en el cuerpo de la tarjeta (nunca flotando sobre la foto), título 24/700 mono, precio en 20/700 con `tabular-nums`, botón secundario «Ver y reservar».

### Lista de cargos por empresa

Un renglón por empresa: nombre, monto, estado (pendiente, retenido, cobrado) con icono y texto. Los estados usan los colores de estado, no los de actividad.

### Esqueleto (carga)

Bloques `cafe-bruma` con pulso de 1,2 s, del mismo tamaño que lo que reemplazan (sin saltos). Respeta movimiento reducido.

---

## Retroalimentación

### Aviso en línea (alerta)

Radio 12, padding 16, icono 20 + texto 14. Éxito (`#2F5D0A` sobre `#E7F5D3`), Error (`#B3261E` sobre `#FDE7E4`), Aviso (`#6B3A00` sobre `cafe-claro`), Información (`#0F3D52` sobre `azul-claro`). Siempre con icono. El de error siempre ofrece una acción («Reintentar», «Escribirnos por WhatsApp»).

### Aviso emergente (toast)

Esquina inferior (encima de la barra fija en móvil), radio 12, nivel 2 de sombra, 5 s, descartable. Para avisos, no para errores que bloquean (esos se quedan en la tarjeta junto al campo).

### Cuenta regresiva del apartado de cupo

Cuando existe un apartado temporal, una línea sobre el botón de pagar: «Tu lugar está apartado 14:32 min» (icono de reloj, `cafe-profundo` sobre `cafe-claro`). Solo se muestra si el apartado existe en el servidor; nunca decorativa.

### Estado de red (wifi del hotel)

Si falla la conexión: aviso de error en línea con «Reintentar» que conserva lo capturado; la reserva a medias se retoma con «Continuar reservación». No se pierde el progreso por recargar.

### Progreso y espera

Botón con indicador de carga circular de 20 y la etiqueta «Procesando…»; el botón queda deshabilitado pero con su razón visible. Pagos de dos empresas: encabezado con los cargos anteriores marcados como hechos y el actual destacado.

---

## Pago

### Cómo pagas

El paso 3 se parte en dos sub-pantallas, cada una con **un solo botón**. (a) «Cómo pagas»: moneda, modalidad (completo o anticipo, si aplica), código promocional, deslinde y verificación antibots; su botón es «Continuar a la tarjeta», que crea la reserva u orden y retiene. (b) Tarjeta de cada empresa: formulario de Stripe con la nota de seguridad; su botón es «Pagar $X a [empresa]», y la barra inferior de (b) vive dentro de `<Elements>` (el botón interno de Stripe se quita). La apariencia de Stripe usa los hex de `tokens-pago` (café, tinta, blanco, error) y radio 12.

| Propiedad | Valor |
|---|---|
| Botón | Principal, una acción por sub-pantalla: (a) «Continuar a la tarjeta»; (b) «Pagar $X a [empresa]» (monto solo si el servidor lo confirmó) |
| Seguridad | Candado + «Pago seguro con Stripe» visible sin scroll |
| Dos cobros | Cada formulario de tarjeta se muestra uno a la vez, en secuencia |

---

## Pendientes de decisión (afectan a estos componentes)

| # | Pendiente | Efecto |
|---|---|---|
| 2 | Contar los campos reales de «Tus datos» | Si pasa de ~7, se vuelve a 4 pasos |
| 3 | Idioma del selector en la cabecera mínima | Aplicado: ES/EN a la derecha |
| 4 | Foto y logo definitivos | Cabecera, tarjetas de servicio y héroe |
