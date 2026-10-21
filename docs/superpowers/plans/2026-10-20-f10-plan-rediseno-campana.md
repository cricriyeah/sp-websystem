# Plan F10: pasar el prototipo «Sun Baja Campaña» al sitio real

**Estado: APROBADO por el dueño el 2026-10-20 («todo lo demás está bien, dale»), con un cambio: el mapa del hub NO se borra, se adapta al estilo nuevo.**

Contexto, tokens y reglas: `docs/superpowers/plans/2026-10-20-f10-brief-rediseno-campana.md` (léelo primero). Prototipo de referencia: artifact `WAMaERBhCmjET1f3khPhCW` (versión 10) o `.taste-skill/prototipos/3-campana/index.html`.

Rama `feat/marca-sun-baja`, worktree `.claude/worktrees/qa`. Sin push. Un commit por tarea, con la línea `Co-Authored-By` que indique el entorno.

## 0. Requisitos (ya fijados, no se vuelven a derivar)

Salen de las tres derivaciones PFD de 2026-10-20 y de las decisiones del dueño:

- **R1 carga:** un significado por color; como máximo 2 acentos por pantalla; el movimiento solo responde a algo (entrar, tocar, abrir).
- **R2 primera impresión:** base negro/blanco/gris en al menos el 85 % de la superficie; el color entra en campos grandes (bloques de palabra, tablero de empresas, paquetes), nunca como puntos.
- **R3 fluidez:** solo los tokens de §3 del brief; una sola curva y juego de duraciones; formas rectángulo o círculo.
- **R4 sesgo:** azul = mar, coral = traslados, verde = estancia, café = marca y acción; ninguna foto contradice su servicio; las convenciones móviles se respetan.
- **R5 decisión:** botón «Reservar →» propio en cada tarjeta; un solo botón principal por pantalla; ninguna animación retrasa un toque.

## 1. Restricciones del código real (descubiertas al revisar `frontend/`)

El plan se escribe para que `npm run verificar` pase en cada commit.

1. **`scripts/guardia-estilos.cjs` tiene un umbral duro (0 infracciones)** en estas reglas. Todo código nuevo las cumple:
   - `<button>` crudo: solo dentro de `ui/` (usar `Button` de `ui/button.tsx`).
   - `<img>` crudo: usar `next/image`.
   - `color-literal`: nada de hex ni `rgb()` en `.tsx`; los colores van como tokens (`bg-azul`, `text-tinta`…). El prototipo usa hex en su CSS; no se copia tal cual.
   - `radio-crudo`: prohibidos `rounded-md|lg|xl|2xl|3xl`. Se permiten `rounded-none`, `rounded-full` y los tokens (`rounded-control`, `rounded-card`). Las formas nuevas (rectángulo o círculo) cumplen sin romper la regla.
   - `mayusculas-crudas`: nada de `uppercase`. Las mayúsculas de Consola Mono van con la clase existente `texto-mono-mayus`.
   - `titular-sin-escala`: todo `<h1>` y `<h2>` lleva una clase `texto-*` de `globals.css`.
   - `letra-fuera-de-escala`: no hay `text-[Npx]` fuera de la lista (12, 14, 16, 20, 22, 24, 28, 36, 40, 56, 64). Los tamaños gigantes del prototipo (hasta 220 px) viven como **clases nuevas en `globals.css`**, no como `text-[..]`.
   - `sombra-cruda`, `paleta-cruda`, `guion-largo` (nada de raya larga «—» en textos ni diccionarios), `objetivo-chico` (botones y enlaces de 44 px o más).
2. **Los radios y las primitivas `ui/*` los comparte el checkout**, que no se rediseña. Además, `tests/tokens-pago.test.cjs` exige que el radio de Stripe (`RADIO_PAGO`) coincida con `--radius-campo`. **Decisión del plan: no se cambia ningún token de radio.** El sitio nuevo usa `rounded-none` y `rounded-full` y agrega variantes nuevas en `ui/variantes.ts` (`campana` y `campana-claro`: píldora negra o blanca). El checkout sigue usando `principal` y `secundario` sin cambios.
3. **`tests/contraste.test.cjs` valida los pares de `design.md` contra los valores reales de `globals.css`.** El coral nuevo (`#E04332`) da 4,18:1 con blanco y 4,13:1 con tinta: ya no cumple el par «tinta sobre coral 4,87». Hay que actualizar la prueba y el documento: el coral solo admite texto grande (3:1), y el par prohibido «blanco sobre coral < 4,5» sigue valiendo. Hay que recalcular la escala derivada (`coral-hondo`, `-profundo`, `-medio`, `-claro`, `-bruma`, `-texto`) y revisar `chip-actividad.tsx` y `empresa-sello.tsx`, que usan coral.
4. **Movimiento:** el sitio usa `framer-motion` con `LazyMotion` estricto (solo `m.*`; la regla `motion-completo` falla con `motion.*`). Las animaciones del prototipo (IntersectionObserver, Web Animations) se reescriben con `m.*` y `useReducedMotion`, o con CSS en `globals.css`. Recorta un hijo y nunca el elemento observado (lección con `clip-path`).
5. **La página de sede es dirigida por datos:** `seccionesDeSede` (`src/lib/secciones-sede.ts`) decide qué secciones van y «una sección sin contenido real no se pinta». Por eso:
   - El prototipo escribe a mano las preguntas de La Ventana y Puerto Chale y la galería; en el sitio real **solo La Paz tiene temporadas, galería y preguntas** (`src/content/sedes-cuerpo.ts`). Para las otras dos sedes la sección no se pinta hasta que haya contenido real.
   - La palabra que rota en el arranque no se escribe a mano: sale de lo que vende la sede (tipos y nombres del catálogo, o un campo de contenido por sede en `sedes-cuerpo.ts`), nunca con slugs del demo en el frontend.
   - «Opiniones» ya solo se pinta con reseñas confirmadas: se restila y se conserva esa condición. No es una decisión del dueño.
6. **Paquetes: no hace falta backend.** Ya existen `getPaquetesSede` y `getPaqueteDetalle` en `src/lib/api.ts` y la ruta `sedes/<sede>/paquetes/<slug>/` en el backend. Solo falta la ruta de frontend.
7. **El hub real tiene un mapa** (`hub-mapa-escritorio`, `hub-mapa-sedes`) que el prototipo no trae. **Decisión del dueño: se conserva y se adapta al estilo nuevo** (formas, colores, tipografía y movimiento), con su lógica intacta. Va en el hub entre las cortinas y la fila de servicios. `hub-grid-sedes` y `tarjeta-sede-hub` sí se reemplazan por las cortinas (tarea F10.5).
8. **Textos:** todo va a `dictionaries/es.json` y `en.json`; los datos de sede y servicios, a `src/content/`. Debe pasar `npm run test:contenido` (paridad es/en).
9. **Fotos:** `imagenes-catalogo.ts` marca el relleno con `relleno: true`; `test:fotos` sigue fuera de `verificar`.

## 2. Decisiones del dueño (todas confirmadas el 2026-10-20)

1. **El mapa del hub se adapta al estilo nuevo; no se borra.** Se reemplazan por las cortinas solo `hub-grid-sedes` y `tarjeta-sede-hub`.
2. La Ventana y Puerto Chale no mostrarán galería, temporadas ni preguntas hasta que haya contenido real; hoy el prototipo las inventa para verse completas.
3. «Tu día de pesca» (5:00 AM / A BORDO / PESCA / REGRESA) no existe en el contenido real; se agrega a `sedes-cuerpo.ts` solo para La Paz, con el texto del prototipo, salvo que el dueño quiera otro.
4. «Puedes agregar: trámite de la licencia (opcional, con costo extra)». Falta el monto y si se reserva como extra o solo se menciona.
5. La barra superior se conserva en estructura, pero adopta formas y colores nuevos.

## 3. Tareas

Cada tarea termina con `npm run verificar` verde (o la parte que le aplique) y un commit. En cada tarea que cambie algo visible: inspector del skill (`inspect.mjs`) y capturas de Chrome a 1440, 768 y 390 px, y se avisa al dueño para su revisión en teléfono.

### Sección A. Base

**F10.0 Recursos y línea base.**
- Copia a `frontend/public/` los logos del checkout principal: `sunbajaexperience/*.svg`, `lapaz/logos/dlstransporte.png`, `ventana/logos/laventanatravel.png`, `puertochale/logos/piratasadventures.png`. Conviértelos a webp de 400 px (PNG) donde convenga y deja los SVG tal cual (no llevan color de relleno).
- Registra los logos en `src/content/empresas-marca.ts` (hoy solo Sal y Sol tiene `logo`).
- Corre `npm run verificar` y guarda el resultado como línea base. Verifica que la base local tenga el catálogo real.
- Commit: `chore(f10): logos de Sun Baja y de las empresas`.

**F10.1 Tokens y documentos.**
- `globals.css`: coral `#E04332` y su escala derivada; clases nuevas `texto-gigante` (`clamp(72px, 13vw, 220px)`), `texto-grande` (`clamp(40px, 5.4vw, 84px)`) y `texto-titulo-campana` si hace falta; curva y duraciones de movimiento; ninguna variable de radio nueva ni cambiada.
- `tests/contraste.test.cjs`: coral solo para texto grande (3:1); recalcula los pares de la escala.
- `docs/design/design.md`, `design-components.md`, `design-guidelines.md`: coral nuevo, formas rectángulo o círculo en el sitio público, regla «sin texto gris tenue», regla de color por actividad y las tablas de movimiento.
- `ui/variantes.ts`: variantes `campana` y `campana-claro` (píldora negra o blanca, 44 px de alto, hover café). Prueba en `tests/` (misma forma que las de `botonClases`).
- Commit: `feat(f10): tokens de la marca campaña y coral nuevo`.

**F10.2 Piezas compartidas.** Una por commit, con su prueba si tienen lógica pura:
1. `FilaArrastrable` (carril con `scroll-snap`, flechas, barra de avance, `flex-grow` para llenar filas cortas). Extrae la lógica de avance a un módulo puro con prueba.
2. `TarjetaProducto` (foto o bloque de palabra en el color de su tipo, nombre, información, precio, botón «Reservar →»). Reemplaza `tarjeta-servicio`. Mapa de color por tipo en un módulo puro (`mar`, `traslado`, `estancia`) en `src/lib/`, con prueba.
3. `BloquePalabra`, `Entrada` (aparición con `m.*`, versión sin desplazamiento con movimiento reducido) y `TituloSeccion` (sube al entrar).
4. `VisorGaleria` con `<dialog>` nativo, flechas y teclado (modelo: `ui/sheet.tsx` y `alert-dialog.tsx`, que ya usan `<dialog>`).
5. `Cifras` (cuenta desde cero una vez; versión estática con movimiento reducido).
- Commits: `feat(f10): fila arrastrable`, `feat(f10): tarjeta de producto`, y así.

### Sección B. Hub

**F10.3 Arranque del hub.** Reemplaza `hub-portada`: video del mar de relleno, h1 gigante «Sal al mar en Baja Sur» (texto sale de `hubContenido`), una frase y un botón. Conserva el `h1` y el poster.

**F10.4 Cortinas de sedes.** Nuevo `CortinasSedes` con `position: sticky`, nombre gigante y botón a media altura; cada cortina se queda 35svh antes de que suba la siguiente; la anterior se hunde y su texto se aparta (CSS con scroll o `m.*`). Usa `vistaDeSede` de `page.tsx` (datos reales: chips, empresas, «desde»). Precio «desde» en MXN en `es`, USD primero en `en`.

**F10.5 Resto del hub.** `que-puedes-reservar` pasa a fila arrastrable (conserva el estado `catalogo_caido` y `vacio`); «Cómo funciona» pasa a bento; el tablero de empresas (cuatro bloques 3:2 con campo de color por empresa, ver brief §7) reemplaza `colaboradores-section` y `fila-empresa`; se borran `hub-grid-sedes` y `tarjeta-sede-hub` con sus claves del diccionario. **El mapa (`hub-mapa-escritorio`, `hub-mapa-sedes`) se conserva y se restila**: tierra en gris claro, sedes como círculos del color de su tipo de actividad, controles de zoom como círculos negros, etiquetas en `texto-mono-mayus`, cursor y arrastre iguales; la lógica y los textos no cambian. Se revisa en escritorio y en el selector móvil.

**F10.6 Pie.** `site-footer`: pie negro con el logo grande SVG en blanco y las cuatro columnas. Conserva `negocio`, `sedeSlug` y `anclas`.

### Sección C. Sedes

**F10.7 Arranque de sede.** `sede-hero`: video con palabra que rota (palabras derivadas del catálogo de la sede) y h1 abajo. Las 3 sedes comparten el componente.

**F10.8 Reservar, cifras, galería, temporadas, preguntas.**
- `que-puedes-reservar` y `reserva-tranquila` (cifras) reciben el estilo nuevo.
- `gallery-section` pasa a mosaico en escritorio y al ritmo «una foto ancha y dos cuadradas» en móvil, con el visor.
- `season-section` pasa a 4 botones por temporada con marco de foto; los datos siguen saliendo de `sedes-cuerpo`.
- `faq-section` pasa a gris con animación de altura; conserva el cierre de WhatsApp y los datos estructurados (JSON-LD).
- `opiniones-empresas` se restila; sigue pintándose solo con reseñas confirmadas.
- `secciones-sede.ts` y sus pruebas se actualizan si se agrega una sección nueva.

**F10.9 Paquete y «Tu día».**
- Tarjeta del paquete con foto (lee `getPaquetesSede`; el contenido de «En el mar / En tierra» sale de `servicios_asociados` del paquete, no se escribe a mano).
- «Tu día de pesca» como fila arrastrable; contenido nuevo en `sedes-cuerpo.ts` (solo La Paz) con paridad es/en.
- Se agregan ids a `SeccionId` y a `ANCLA_DE`.

### Sección D. Detalle

**F10.10 Detalle de servicio.** Rediseña `app/[lang]/servicio/[empresa]/[servicio]/page.tsx` y `included-section`: arranque con foto o palabra de color, ficha en dos columnas, bloque de compra con precio y botón «Reservar [servicio]» (en móvil, barra fija que sube por encima del aviso de cookies), «Qué incluye», «Puedes agregar», «Quién opera» (con el sello de la empresa), «También en [sede]» solo con servicios de la misma sede. Sin «¿Cuántos van?».

**F10.11 Detalle de paquete.** Ruta nueva `app/[lang]/sede/[slug]/paquete/[paquete]/page.tsx` (o la que el dueño prefiera) que usa `getPaqueteDetalle`; mismo diseño que F10.10, con «Quién opera» para las dos empresas. Metadatos, `alternates` y sitemap.

### Sección E. Piezas no cubiertas por el prototipo

**F10.12 Barra y selectores.** `site-header`, `selector-idioma`, `sede-selector`, `continuar-reservacion`: formas (píldora o círculo), colores y movimiento nuevos; la estructura y el comportamiento se conservan.

**F10.13 Aviso de cookies.** `cookie-notice`: tira nueva, mismos dos botones del mismo peso. La lógica de `useSyncExternalStore` y la exclusión de `/reservar` y `/traslados` no cambian. Prueba existente en verde.

**F10.14 Páginas secundarias.** `privacidad`, `deslinde`, `texto-legal`, `legal-back-link`, `not-found`, `error`, `loading` y `skeleton`, `catalogo`, `whatsapp-contact`, `whatsapp-inline`, `banda-colaboracion`, `toast`, `wait-notice`. Solo estilo; los textos y la lógica no cambian.

### Sección F. Cierre

**F10.15 Barrido de código muerto.**
- Agregar `knip` como dependencia de desarrollo, con su configuración, y `"knip"` dentro de `npm run verificar`.
- Prueba de claves huérfanas de los diccionarios (como la limpieza de F9).
- Fotos y tokens sin uso, clases de `globals.css` sin uso.
- Verifica que no quede una versión vieja de ningún componente reemplazado (cada tarea debió borrarla en su commit).
- `npm run verificar` completo y `next build`.

**F10.16 Cierre.** `test:fotos` sigue fuera de `verificar`. Actualiza la memoria y el índice. El merge único (F7 + F8 + F9 + F10), el push y el backend a Render los decide el dueño tras revisar en su teléfono.

## 4. Fuera de alcance

La página de reservas y su flujo (el dueño la rediseña después, aparte). Sus componentes, `ui/button` (variantes `principal` y `secundario`), `ui/card`, `ui/field`, `ui/opcion` y los radios del sistema no cambian. Cuando el dueño rediseñe el checkout, adoptará las formas nuevas en un plan propio.

## 5. Riesgos

- **Estilos compartidos:** cada tarea corre `npm run verificar`; si algo del checkout cambia de aspecto, `tokens-pago` y la guardia lo notan, y se revierte antes de seguir.
- **Prototipo escrito a mano frente a datos reales:** donde el prototipo inventa contenido (preguntas de La Ventana y Puerto Chale, «Tu día», la palabra que rota) el plan lo sustituye por datos o contenido real, o no lo pinta (regla de F9).
- **Rendimiento:** el video y las fotos en `next/image` con `priority` solo en el arranque; el visor carga la foto grande bajo demanda.
- **Movimiento:** todo animado con `transform` y `opacity`, y con versión sin desplazamiento.
