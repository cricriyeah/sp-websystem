# Auditoría del lenguaje visual tras F7 (2026-10-17)

Rama `feat/marca-sun-baja`, HEAD `fd6d41d2`, sin push. Método: skill `design-taste-frontend` (secciones 0 a 14) y `perception-first-design:solve` (Mode 2), con la página real abierta en el navegador (escritorio) y mediciones con JavaScript. Es un diagnóstico: **no se tocó código por esta auditoría**. Todo lo de abajo espera la luz verde del dueño.

## 1. Estado de F7 al cerrar

F7 (Tasks 7.1 a 7.3) está completa y verificada con `npm run verificar` (162 pruebas, 36 de contraste, guardia 5/5, build). Commits `feat(marca):` de la 7.3: sombras, brillo, foco, iconos de aviso, escala de titulares, radios (`1b56b532`), card y chips (`7d794474`), héroe y secciones, skeleton y toast, compuerta (`3494b89d`). Después, por decisión del dueño, `fd6d41d2` (titulares siempre en mayúsculas, vía `text-transform: uppercase` en las clases `texto-display/pagina/seccion/paso`; `design.md` y `design-guidelines.md` actualizados).

F7 fue una pasada de valores (colores, radios, sombras, titulares, fondos). No rediseñó componentes. Por eso el sitio se ve "casi igual" con otro color.

## 2. Qué se midió en el navegador (escritorio)

Sede La Paz (`/es/sede/la-paz`) y checkout de servicio suelto (`/es/reservar?servicio=paseo-islas&empresa=sal-y-sol&sede=la-paz`):

- **Radios:** 5 distintos conviviendo (0 px en 16 elementos, 4, 12, 16 y píldora). Los de 0 px son cabecera, menú, selector de idioma y contenedores. `design.md` fija 12 en controles, 16 en tarjetas y píldora solo en chips.
- **Objetivos táctiles bajo 44 px:** enlaces de cabecera 20 px, "Destino" 33, "ES" 36, flechas de reseñas 36, puntos del carrusel 8x8, más y menos de personas 24x24, botones de icono del checkout 32.
- **Tamaños de letra:** en la sede 63 textos de 12 px y 8 de 13 px; en el checkout 25 de 12 px. El 13 y el 15 no están en `design.md`.
- **Selector de idioma fijo** abajo a la izquierda: 36 px, sin radio, y tapa texto de la sede. El icono "N" es solo del modo desarrollo.
- **Cabecera:** caja blanca recta de 80 px; sobre el video parece un recuadro de oficina; en el checkout es una franja casi vacía.
- **Logo:** sigue el viejo (índigo y amarillo) en todas las cabeceras y como wordmark gigante en el pie, que es lo más fuerte de la página.
- **Hub:** La Ventana y Puerto Chale usan la misma ilustración morada y naranja (placeholder de la marca anterior); abre sin foto de mar.
- **Copy:** la pestaña del checkout del paseo dice "Reserva tu tour de pesca deportiva"; 5 em-dashes en los diccionarios (1 en es, 4 en en); en reseñas se ve una nota interna ("Aquí se sincronizan reseñas de Google, Facebook y WhatsApp").

## 3. Qué componentes expresan la marca y cuáles no

La marca (costera, un poco deportiva, de agencia profesional) hoy vive donde **la foto manda**: héroe con video, galería de fotos grandes y temporadas (barra de meses con fotos, el mejor componente). Se siente genérico donde hay **texto en cajas con borde**:

- **Servicios:** 5 tarjetas iguales en 3 columnas, sin foto, chips grises (no los colores de actividad), y los botones "Reservar este servicio" y "Conocer más" repetidos 5 veces.
- **Paquetes:** tarjeta dentro de tarjeta dentro de tarjeta (recuadro de precio y lista de cajas), sin foto, con la etiqueta "Experiencia completa".
- **Empresas ("Marcas que nos acompañan"):** logo y enlace subrayado; DLS Transporte sin logo.
- **Reseñas:** texto y estrellas en gris tenue, nota interna visible; los nombres de los testimonios no están confirmados.
- **Checkout:** el calendario en tira funciona; el stepper y las tarjetas blancas son neutros.
- **Chips de actividad (azul, coral, verde):** el componente existe pero nadie lo usa; hoy ninguna pantalla pinta esos tres colores (solo el azul aparece en el anillo de foco).

## 4. Taste: reglas que se rompen

Aplicado a la sede (secciones relevantes de `design-taste-frontend`): candado de forma (§4.4), tres tarjetas iguales (§9.C), intención de CTA duplicada (§4.5), eyebrow (§4.7), etiqueta sobre una foto ("Temporada fuerte", §9.F), em-dash (§9.G), etiqueta genérica de paso ("Paso N de 3", §9.F), tarjetas anidadas (§4.4). Límite de la skill: no cubre formularios por pasos (§13), así que en el checkout solo se aplican sus reglas de forma, letra y botones.

## 5. PFD, Mode 2: requisitos derivados

- **R1 (L0, Cowan 2010; Sweller 1988):** una acción por oferta y sin cajas dentro de cajas.
- **R2 (L1, Lindgaard 2006; Kurosu & Kashimura 1995):** cada oferta lleva su foto, y la identidad de mayor peso visual usa la paleta nueva.
- **R3 (L2, Reber & Schwarz 1999; Wertheimer 1923):** una sola tarjeta de oferta para servicio y paquete, con el color de actividad como único código.
- **R4 (L3, Fogg 2003; Kahneman & Tversky 1979):** el operador y las reseñas atribuidas se ven con peso suficiente; no se muestra texto interno ni se inventa urgencia.
- **R5 (L4, Thaler & Sunstein 2008; Pirolli & Card 1999):** una oferta destacada y las demás subordinadas, una acción principal por tarjeta.

## 6. Diseño derivado (propuesta)

- **Tarjeta de oferta única** (servicio y paquete): foto arriba sin etiquetas encima; debajo, chip de actividad, título, una línea de descripción y una fila de datos (precio, duración, capacidad) en Consola Mono sin separadores de punto medio; toda la tarjeta enlaza al detalle y hay un solo botón "Reservar" ("Conocer más" desaparece); sin cajas internas (el contenido del paquete es una lista de una línea con iconos); rejilla asimétrica con una destacada grande.
- **Quién opera:** fila con sello (monograma si no hay logo), nombre y qué hace.
- **Reseñas:** texto en tinta y estrellas en café; sin la nota interna; hasta tener reseñas confirmadas por cada empresa, el dueño decidió dejar los ejemplos actuales sin la nota interna.
- **Pie:** logo en tamaño normal con columnas; el wordmark gigante desaparece.
- **Cabecera:** radio de tarjeta y arena, sin la caja blanca sobre el héroe.
- **Checkout:** el resumen lleva la foto o el sello de lo que se compra y la empresa.
- **Piezas globales a unificar:** selector de idioma (44 px, `rounded-control`, que no tape contenido), objetivos táctiles de 44 px, letra a la escala de `design.md`, efecto de pulsado.
- **Propuestas retiradas:** el "boleto" y la franja de color en la tarjeta (la evidencia indica que el carácter lo da la foto, no el marco). Las bandas de azul oscuro quedan solo como opción para el pie, a decidir.

## 7. Decisiones del dueño (2026-10-17)

1. **Tarjeta de oferta:** una sola, con foto y rejilla asimétrica con una destacada. Aprobada.
2. **Pasos del checkout:** nombres como texto principal ("Viaje", "Tus datos", "Pago") y "Paso N de 3" como apoyo secundario en texto pequeño. Aprobada.
3. **Reseñas:** dejar los ejemplos actuales sin la nota interna. (Pendiente confirmar los nombres con cada empresa.)
4. **Fotos de paseos, hospedaje y traslados:** las pasa el dueño antes de F9. Sin ellas, esas tarjetas no se pueden cerrar.
5. **Selector de idioma / cabecera / piezas globales:** no se ha decidido el alcance de la pasada de unificación; el dueño no dio luz verde todavía.

## 8. Lo que NO se cubrió

Móvil (el navegador bloqueó la ventana emergente y el marco de 390 px; hay que revisarlo a mano con F12), pantallas de confirmación, error, traslados, la banda "Continuar reservación", los pasos de pago del checkout y la segunda mitad del hub. Los números de objetivos táctiles son de escritorio. Las partes de la skill de taste que cubren apéndices no se usaron.

## 9. Hueco contra el plan actual

- F8 rediseña el checkout (3 pasos, barra, calendario, aviso); no pide foto ni sello en el resumen.
- F9 (Task 9.1b "Qué puedes reservar", con foto) ya apunta a una tarjeta con foto, pero hay que fijar que sea una sola para servicio y paquete y asimétrica.
- Ninguna fase cubre la cabecera general, el selector de idioma fuera del checkout, el pie, los objetivos táctiles del resto del sitio ni la nota interna de las reseñas.

## 10. Siguientes pasos

1. Que el dueño revise F7 y confirme el alcance de la pasada de unificación (punto 5).
2. Escribir las especificaciones de estos componentes en `design-components.md` antes de implementar, con la luz verde del dueño.
3. Implementar la pasada de unificación (piezas globales) y luego F8 y F9, que salen juntas con F7 en un solo merge; no se despliega F7 sola; orden de despliegue en la Task 8.6 (backend primero).
4. Pendientes que solo puede resolver el dueño: fotos de paseos, hospedaje y traslados; logo definitivo; revisión visual de F7 (titulares en mayúsculas a 360 px, etiqueta larga del botón de pago, anillo de foco, contraste de `--hero-ink` con la foto real); 9 recorridos manuales de F5 y F4 grupo 4; investigar por qué `/es` pesa unos 40 KB más que antes.

## 11. Decisiones posteriores y dónde quedó cada cosa (2026-10-17)

Tras leer F8 y F9 completas, esta auditoría se integró al plan (`docs/superpowers/plans/2026-10-15-frontend-base-rediseno.md`), que es la única fuente para ejecutar. Este documento queda como respaldo de las razones.

- **Alcance de la pasada global:** completa, aprobada por el dueño. Quedó como fase nueva **F7b** (Tasks 7b.0 a 7b.6), antes de F8.
- **Puerta de taste:** cuatro controles escritos en las restricciones globales del plan (taste y PFD antes del brief, el brief copia las reglas, revisión del orquestador en el navegador, guardia mecánica). La guardia nueva es la Task 7b.0.
- **Tarjeta de oferta única, rejilla con destacada, chips de actividad:** ya estaban en la Task 9.1b (decisión del dueño del 2026-10-16); se añadió la fila de datos en Consola Mono sin separadores.
- **Pasos del checkout con nombre:** ya estaban en 8.0a y 8.3; se añadió el nombre visible en la línea de progreso móvil.
- **Resumen del checkout con foto o sello:** añadido a la Task 8.3, pendiente de luz verde en su PUNTO DEL DUEÑO.
- **Quién opera:** se retira la sección de empresas **de las sedes** (commit `0223aec0`). El hub la conserva y la Task 9.4 la reemplaza por `FilaEmpresa`. Las empresas siguen mencionadas en todo lo demás.
- **Reseñas:** manda la Task 9.5: solo reseñas confirmadas por cada empresa; sin ellas no hay sección. Esto **revierte** la decisión 3 del §7 (dejar los ejemplos sin la nota interna).
- **Titulares en mayúsculas:** el texto de la Task 7.3 que prohibía `uppercase` se corrigió con la excepción del dueño (`fd6d41d2`).
