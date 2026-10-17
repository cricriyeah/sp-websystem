# Sun Baja Experience — Guías: accesibilidad y qué hacer / qué no

> Los valores de los tokens están en [design.md](design.md). Las especificaciones de componentes y de la página de reserva están en [design-components.md](design-components.md).

Objetivo: que un turista reserve y pague desde el móvil, con el wifi de un hotel, en español o en inglés, sin dudar de que el sitio es serio ni de que el cobro es el correcto. Nivel de accesibilidad: **WCAG 2.2 AA**.

---

## Accesibilidad

### Contraste

| Requisito | Razón |
|---|---|
| Texto normal (< 24 px, o < 19 px en negrita) | 4,5:1 |
| Texto grande (≥ 24 px, o ≥ 19 px en negrita) | 3:1 |
| Iconos que comunican algo, bordes de campos, casillas y focos | 3:1 contra el fondo |
| Texto deshabilitado | Sin mínimo, pero se mantiene ≥ 4,5:1 por usabilidad (`apagado` sobre `cafe-bruma`: 5,40:1) |

Pares aprobados (calculados):

| Combinación | Contraste |
|---|---|
| `tinta` sobre `arena` / blanco | 16,17:1 / 17,27:1 |
| blanco sobre `cafe` (botón principal) | 8,46:1 |
| `apagado` sobre blanco / arena | 6,37:1 / 5,96:1 |
| blanco sobre `azul` | 6,94:1 |
| blanco sobre `verde` | 11,30:1 |
| `tinta` sobre `coral` | 4,87:1 |
| `coral-texto` sobre `coral-claro` | 5,56:1 |
| `borde-control` sobre blanco / arena | 4,15:1 / 3,89:1 |

Pares **prohibidos**:

| Combinación | Contraste | Por qué |
|---|---|---|
| blanco sobre `coral` | 3,54:1 | No alcanza 4,5:1 para texto normal |
| `coral` como texto sobre blanco | 3,54:1 | Ídem |
| `borde` (`#D9C9B4`) como contorno de un campo | 1,62:1 | No delimita el control |
| `cafe` sobre `coral` | 2,39:1 | Ilegible |
| Cualquier color de actividad usado como estado | — | Se confunde con la categoría |

### Objetivos táctiles

| Elemento | Mínimo |
|---|---|
| Botón, campo, opción | 48 × 48 px (móvil), 44 × 44 px (escritorio) |
| Día del calendario | 44 × 44 px |
| Atajos de fecha (chips) | 44 px de alto, 8 px entre ellos |
| Flecha de volver | 48 × 48 px de área, aunque el icono mida 24 px |
| Espacio entre objetivos adyacentes | 8 px |

### Teclado

| Tecla | Acción |
|---|---|
| `Tab` / `Shift+Tab` | Mueve el foco entre controles, en orden visual |
| `Enter` / `Space` | Activa botón, abre tarjeta, elige día |
| Flechas | Mueven el foco por los días del calendario (← → ↑ ↓) |
| `Re Pág` / `Av Pág` | Mes anterior / siguiente en el calendario |
| `Inicio` / `Fin` | Primer / último día de la semana |
| `Esc` | Cierra un popover o una hoja y devuelve el foco a quien la abrió |
| `Enter` en un formulario | Envía solo si el botón es de envío; nunca avanza sin validar |

El anillo de foco es siempre visible (2 px `azul` + 2 px de desfase). Al cambiar de paso, el foco va al título del paso nuevo.

### Tecnologías de asistencia

- El título del paso se anuncia al entrar (`aria-live="polite"`).
- La línea de progreso del móvil es una `<ol>` con `aria-current="step"` en el segmento activo y el texto «Paso 2 de 3: Tus datos» (los números existen para lectores de pantalla aunque no se vean); no usa `role="progressbar"`.
- Las tarjetas plegables usan `aria-expanded` y `aria-controls`.
- El calendario es una cuadrícula (`role="grid"`) con cada día etiquetado completo («viernes, 7 de noviembre, disponible»); la **leyenda** es texto real, no una imagen.
- Los errores se enlazan al campo con `aria-describedby` y se anuncian con `role="alert"`.
- Un botón deshabilitado expone la razón con `aria-describedby` apuntando al texto de ayuda.
- El estado no depende solo del color: cada estado del calendario tiene además forma (punto, rayado, anillo, borde discontinuo).

### Movimiento reducido

Con `prefers-reduced-motion: reduce`: sin deslizamientos ni animaciones de plegado; solo cambios de opacidad de 150 ms.

---

## Gestos

| Gesto | Uso |
|---|---|
| Toque | Elegir día, abrir tarjeta, avanzar |
| Doble toque | Sin uso |
| Pulsación larga | Sin uso |
| Desplazar | Moverse por la página; el calendario no captura el scroll vertical |
| Deslizar horizontal | Cambiar de mes en el calendario (con botones equivalentes visibles) |
| Deslizar desde el borde izquierdo | Lo reserva el navegador para «atrás»: no se usa |
| Pellizcar | Sin uso |

Ningún gesto es el único camino: todo tiene botón.

---

## Contenido y redacción

| Regla | Detalle |
|---|---|
| Tono | Cercano y claro, de «tú». Sin jerga ni promesas exageradas |
| Mayúsculas | Caja de oración en botones, etiquetas y titulares. Nada todo en mayúsculas |
| Botones | Dicen **adónde llevan o qué hacen**: «Continuar a tus datos», «Pagar $4,100 MXN a Sal y Sol». Nunca «Siguiente», «Enviar» ni «Aceptar» solos |
| Botón deshabilitado | Siempre una línea debajo que dice qué falta: «Elige una fecha para continuar» |
| Errores | Qué pasó y cómo arreglarlo, sin culpar: «El número de tarjeta está incompleto. Revisa los 16 dígitos» |
| Dinero | Moneda siempre visible (`$4,100 MXN`), cifras con `tabular-nums`; nunca un total que difiera del cobro |
| Longitud de línea | 45–75 caracteres en párrafos |
| Idiomas | Todo texto sale del diccionario es/en; los botones largos deben caber en inglés y en español |
| Pasos | Mismo nombre en todas partes: **Viaje · Tus datos · Pago** |

---

## Qué hacer y qué no, por categoría

### Color

- **Haz** usar `cafe` para la acción principal de cada pantalla y para nada más.
- **Haz** usar azul, coral y verde solo para decir el tipo de actividad (mar, ciudad, outside o montaña).
- **Haz** poner texto oscuro (`tinta`) sobre rellenos de `coral`.
- **No hagas** botones principales en azul, coral o verde.
- **No uses** el color como única señal: suma icono, forma o texto.
- **No uses** blanco o negro puros en texto: el texto es `tinta` y los fondos son `arena` o blanco.
- **No uses** valores casi iguales a un token (un café «parecido»): usa el token.

### Forma

- **Haz** 12 px en controles y 16 px en tarjetas; círculo en los días del calendario.
- **No mezcles** radios en la misma tarjeta; el radio de un control no cambia por pantalla.
- **No pongas** esquinas más cerradas en el móvil que en el escritorio.

### Elevación

- **Haz** separar con borde y color; la sombra de nivel 1 es solo para la barra inferior fija.
- **No pongas** sombras grandes (la del resumen se elimina); ninguna sombra pasa del nivel 2.

### Interacción

- **Haz** que haya un solo botón principal por paso.
- **Haz** que los atajos de fecha («Borrar fecha», «Mañana», «En 2 días») sean valores por defecto que se pueden cambiar.
- **No ocultes** acciones esenciales detrás de gestos.
- **No avances** sin validar; al fallar, el foco va al primer campo con error.

### Layout

- **Haz** un paso por pantalla en móvil, sin tarjetas plegables.
- **Haz** que el botón de avanzar esté pegado al borde inferior en móvil y que la flecha de volver esté arriba a la izquierda.
- **No pongas** navbar en la página de reserva: la cabecera mínima (flecha, logo, idioma) lo sustituye.
- **No dejes** más de ~7 campos por paso.

### Tipografía

- **Haz** titulares en Consola Mono (solo Book y Bold), caja de oración, con `text-wrap: balance`.
- **Haz** cuerpo en San Francisco (fuente del sistema), mínimo 16 px en campos.
- **No uses** la mono para párrafos largos ni para cifras de dinero en tablas (ahí van `tabular-nums` de la fuente del cuerpo).
- **No uses** más de tres tamaños de texto en una tarjeta.

### Movimiento

- **Haz** animar solo lo que aparece, se pliega o cambia de sitio, con la curva estándar.
- **No animes** el contenido de pago ni el formulario de tarjeta.
- **No hagas** que un elemento brinque el contenido de abajo al aparecer: reserva su espacio.

### Componentes

- **Haz** que cada paso tenga el mismo título en la tarjeta, la cabecera móvil y la línea de progreso.
- **Haz** mostrar un estado de carga, de error con «Reintentar» y de vacío en cada pieza que dependa de la red (el cliente reserva desde wifi de hotel).
- **No muestres** una cuenta regresiva del apartado de cupo que no sea real.
- **No cobres** distinto de lo que dice el botón.

---

## Decisiones y supuestos pendientes de confirmar

| # | Tema | Supuesto actual |
|---|---|---|
| 1 | Fuentes | Titulares: Consola Mono servida desde el sitio (igual en todos los dispositivos). Cuerpo: San Francisco del sistema (cambia a Segoe UI o Roboto fuera de Apple). Consola Mono solo tiene dos pesos, por eso los titulares son siempre 700 |
| 2 | Pasos | 3 pasos: Viaje · Tus datos (contacto + detalles) · Pago. Verificar que contacto + detalles no pasen de ~7 campos |
| 3 | Paquetes de varias noches | Duración fija: el cliente elige el día de inicio y el rango sale del paquete |
| 4 | Contraste de `borde-control` sobre arena | 3,89:1 (cumple 3:1); si se usa sobre `cafe-bruma` hay que re-medir |
