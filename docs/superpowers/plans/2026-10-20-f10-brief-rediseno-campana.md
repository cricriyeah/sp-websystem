# F10: rediseño del sitio público «Sun Baja Campaña». Brief de traspaso

> El plan ya está escrito (borrador, espera luz verde del dueño): `2026-10-20-f10-plan-rediseno-campana.md`, en esta misma carpeta.

> Para la sesión que escriba el plan F10 y lo implemente. Este documento no es el plan: es lo que se decidió con el dueño y dónde está cada cosa. El plan se escribe después, con luz verde del dueño.

## 1. Qué leer, en este orden

1. La memoria: `plan-rediseno-sitio-campana.md` (historial de versiones y decisiones). También `feedback-proceso-diseno-frontend.md`, `feedback-pfd-vs-taste.md`, `feedback-formas-rectangulo-o-circulo.md`, `feedback-fotos-placeholder.md`, `feedback-catalogo-real-en-local.md`, `feedback-se-ve-mal-no-es-redisenar.md`, `referencia-corpus-pfd-real.md`.
2. **El prototipo, que es la fuente de verdad del diseño** (versión 10):
   - Artifact: https://claude.ai/artifact/WAMaERBhCmjET1f3khPhCW. Se lee con `Artifact action=read url=...` (el contenido llega como HTML). Si la sesión usa otra cuenta de claude.ai y devuelve «not found», usa el archivo local.
   - Archivo local, mismo contenido: `.claude/worktrees/qa/.taste-skill/prototipos/3-campana/index.html` (112 KB, un solo archivo con CSS y JS; sin commit).
   - Sus recursos están junto al archivo: `fotos/`, `video/mar.webm` + `mar-poster.webp`, `fuentes/ConsolaMono-Bold.woff2`, `logos/`.
   - `armar-local.sh` genera `local-<vista>.html` con una vista ya visible, para el inspector y las capturas.
3. Los skills: `design-taste-frontend` (instalado en `<repo>/.agents/skills/design-taste-frontend`; sus scripts se corren con ruta de Windows y `MSYS_NO_PATHCONV=1`) y `perception-first-design:solve` para fijar los requisitos del plan.
4. `docs/design/design.md`, `design-components.md`, `design-guidelines.md` (hay que actualizarlos; ver §5).

## 2. Alcance

Se rediseña todo el sitio público **menos la página de reservas** (checkout F8) y su flujo (`/reservar`, `/traslados`, pantallas de pago y confirmación).

El prototipo cubre 6 vistas, todas en español:
- Hub (inicio).
- La Paz, La Ventana y Puerto Chale.
- Detalle de servicio: pesca deportiva y paquete Pesca + Traslado.
- Menú del móvil, selector de idioma, aviso de cookies y visor de galería.

**Lo que el dueño pidió que NO se lleve:** la barra superior del prototipo (su estructura, su menú negro a pantalla completa y su «ES / EN»). El sitio real conserva su barra (`site-header`). Aun así, la barra real debe adoptar los tokens nuevos (colores, formas, curvas de movimiento) para que no se vea de otra familia; se decide en el plan.

**Componentes que el prototipo no cubre y que deben adoptar el estilo nuevo** (ver §6): legales, 404 y error, catálogo, opiniones, WhatsApp, banda «Continuar reservación», skeletons, avisos, selectores.

## 3. Tokens del prototipo

Colores:

| Token | Valor | Uso |
|---|---|---|
| `--negro` | `#1F1A14` | Tinta y base oscura (= `tinta` del sitio) |
| `--blanco` | `#FFFFFF` | Fondo |
| `--gris` | `#F1F0ED` | Superficies (= `cafe-bruma` del sitio) |
| `--cafe` | `#7C3B02` | Marca y acción: hover de botones, sede activa |
| `--cafe-hondo` | `#5D2C02` | Hover del café |
| `--cafe-claro` | `#FEE0AC` | Números de las cifras y fondo del sello de Sal y Sol |
| `--azul` | `#1B607F` | Actividad: mar (pesca, mosca, ballenas, safari) |
| `--coral` | **`#E04332`** (decidido por el dueño) | Actividad: traslados |
| `--verde` | `#343F04` | Actividad: estancia (hospedaje, paquetes con noches) |

- El coral reemplaza a `#F64A25` en `globals.css`, `design.md` y su escala derivada.
- Contraste del coral: 4,2:1 con blanco y 4,1:1 con tinta. Solo admite texto grande: 24 px o más, o 19 px en negrita. Nunca texto de cuerpo encima.
- Los colores de actividad dicen qué tipo de salida es. Nunca se usan como botón ni como estado.
- Texto: todo en `--negro` (o `#F1F0ED` sobre fondo oscuro). **No hay texto gris tenue**: el dueño dijo que casi nadie lo lee.

Tipografía:
- `--display`: Consola Mono Bold, siempre en mayúsculas con `letter-spacing` de -0.02 a -0.05em (ya cargada en `src/app/fonts/ConsolaMono-Bold.woff2` desde `src/app/[lang]/layout.tsx`).
- `--cuerpo`: San Francisco del sistema.

Escala de tamaños:

| Token | Valor |
|---|---|
| `--t-gigante` | `clamp(72px, 13vw, 220px)` |
| `--t-grande` | `clamp(40px, 5.4vw, 84px)` |
| `--t-titulo` | `clamp(28px, 2.6vw, 40px)` |
| `--t-lead` | `20px` |
| `--t-cuerpo` | `18px` (17 px en móvil) |
| `--t-chico` | `15px` |

Otros tokens:
- `--m: clamp(16px, 2.6vw, 40px)` (margen lateral), `--barra: 60px`.
- Curva única: `--ease: cubic-bezier(0.2, 0, 0, 1)`.
- Duraciones: 150 ms al tocar; de 220 a 300 ms al abrir o cerrar; de 600 a 900 ms al entrar en pantalla.

## 4. Reglas de diseño decididas

1. **Formas: solo rectángulo de esquina recta o círculo / píldora completa.** Nada de radio 12 o 16 px. Aplica a fotos, bloques, tarjetas, campos y botones de las páginas rediseñadas.
2. **Base neutra de al menos el 85 %.** Los colores de actividad entran en campos grandes y puntuales (bloques de palabra, tablero de empresas, paquetes), nunca como puntos ni indicadores. El dueño rechazó los puntitos.
3. **Un significado por color**, y como máximo 2 acentos por pantalla.
4. **Botones**: píldora negra, o blanca sobre foto. El color no va en el botón. Cada tarjeta de servicio lleva su botón «Reservar →» explícito, con 44 px o más de alto.
5. **Fotos solo de pesca en servicios de pesca.** Ballenas, safari, hospedaje y traslados van como bloque de palabra en el color de su tipo. Las 9 fotos y el video de la panga son de relleno hasta que el dueño dé las reales.
6. **Sin «¿Cuántos van?»** en La Paz ni en el detalle: esa función no existe fuera del checkout.
7. **Nada en gris tenue y sin filas grises de relleno.** Las preguntas, las notas y el paquete de La Paz siguen en gris (`#F1F0ED`); el dueño aún no pidió quitarlas.
8. **Movimiento sobrio** con transform y opacity, y versión sin desplazamiento con `prefers-reduced-motion`. Ver la lista en §6.
9. **Cabecera de sede sin foto honesta:** video del mar con una palabra gigante que rota (MOSCA, BALLENAS, ORCAS, 5 NOCHES / SAFARI, BALLENAS, PESCA / PESCA, MARLIN, DORADO, TRASLADOS) y abajo el h1 con el nombre.

## 5. Conflicto técnico que el plan debe resolver

Los radios (`--radius-control` 12, `--radius-card` 16, `--radius-sheet` 24…) y los componentes `ui/button`, `ui/card`, `ui/field`, `ui/opcion` y similares **los comparte el checkout**, que no se rediseña. Hay una prueba de tokens de pago (`tests/tokens-pago.test.cjs`) que exige que el radio de Stripe Elements (`RADIO_PAGO`, en `src/lib/tokens-pago.ts`) coincida con `--radius-campo`. Cambiar los tokens globales cambiaría el checkout.

Opciones para el plan (decídelo con PFD solve y con el dueño):
- Radios y variantes nuevas **solo para el sitio público**: variantes en `ui/variantes.ts` o un ámbito (`data-sitio="campana"`) que redefina los tokens bajo el layout público y no bajo el checkout.
- Duplicar solo las primitivas que difieren.

No resuelvas esto cambiando `globals.css` a ciegas. Antes de tocar nada, corre `npm run verificar`: si cambias la forma del checkout, las pruebas lo cantan.

## 6. Qué reemplaza a qué

Los componentes reales están en `frontend/src/components/`. Regla general: **se reemplaza la presentación; los datos, las rutas, los textos es/en, el SEO y la lógica quedan.**

| Prototipo | Hoy en el sitio | Qué hacer |
|---|---|---|
| Arranque con video y palabra gigante (hub) | `hub-portada` | Reemplazar. Se conservan video/poster de relleno y el `h1`. |
| Cortinas de sedes | `hub-grid-sedes`, `tarjeta-sede-hub`, `hub-mapa-*` | Reemplazar. Cortinas `position: sticky`; el botón va a media altura y cada cortina se queda 35svh más antes de que suba la siguiente. |
| Fila arrastrable «Lo que puedes reservar» | `que-puedes-reservar`, `tarjeta-servicio` | Reemplazar. Se conserva la lógica de catálogo caído (null) o vacío. Tarjetas con `flex: 1 0`, barra de avance y botón «Reservar →». |
| «Cómo funciona» en bento | `hub-como-funciona` | Reemplazar. Bento de 3 fotos que crecen de tamaño. |
| «Empresas locales que nos acompañan» (tablero) | `colaboradores-section`, `fila-empresa`, `empresa-sello` | Reemplazar. Cuatro bloques 3:2 de color plano. La asignación está en §7. |
| Cifras 30 % / 48 h / 100 % | `reserva-tranquila` | Reemplazar. Números que cuentan desde cero. |
| Temporadas con 4 botones | `season-section` | Reemplazar. Marco con foto que cambia por temporada. |
| Galería mosaico + visor | `gallery-section` | Reemplazar. Visor con `<dialog>`, flechas y teclado. |
| Preguntas con animación | `faq-section` | Mismo contenido y datos estructurados. Se despliega con altura en 300 ms. |
| Arranque de sede (palabra que rota) | `sede-hero` | Reemplazar. |
| Paquete de La Paz con foto | (no existe) | Componente nuevo y ruta nueva. |
| Detalle de servicio | `app/[lang]/servicio/[empresa]/[servicio]/page.tsx`, `included-section` | Rediseñar. Se agregan «Quién opera» y «Puedes agregar». |
| Pie con logo grande | `site-footer` | Reemplazar. |
| Aviso de cookies (tira gris, Aceptar y Rechazar del mismo peso) | `cookie-notice` | Restilar. **La lógica se queda**: no aparece en `/reservar` ni `/traslados`, se lee con `useSyncExternalStore`. En el detalle móvil la barra fija de compra sube por encima del aviso. |

Detalles de movimiento del prototipo: títulos de sección que suben al entrar, fotos de tarjeta que se descubren, cortinas que se hunden cuando sube la siguiente, preguntas que se despliegan, cifras que cuentan, barra de avance de la fila, palabra rotatoria, y hover en tarjetas, empresas y bento. Recorta un hijo y nunca el elemento que observa el `IntersectionObserver`: `clip-path` en el observado impide que entre.

**No cubiertos por el prototipo; adaptar a los tokens:**
- Legales (`privacidad`, `deslinde`, `texto-legal`, `legal-back-link`), 404 (`not-found`), `error` y `global-error`, `loading` y `skeleton`.
- `/catalogo`, `selector-experiencia`, `sede-selector`, `selector-idioma`, `site-header`.
- `whatsapp-contact`, `whatsapp-inline`, `continuar-reservacion`, `toast`, `wait-notice`, `banda-colaboracion`, `structured-data`.
- `opiniones-empresas`: el prototipo no la tiene, pero el sitio real solo la pinta con reseñas confirmadas (`seccionesDeSede`). Se restila y se conserva esa condición; no hace falta decidir nada.
- `people-stepper`, `field-popover` y `time-field` son del checkout: no se tocan.

## 7. Datos de contenido que usa el prototipo

**Precios del seed** (`seed_catalogo_real`). Los de La Ventana y Puerto Chale son provisionales:
- Pesca deportiva La Paz: $4,500 MXN por grupo (incluye 3 personas, +$500 por persona extra, hasta 5).
- Pesca + Traslado: $7,500 por grupo.
- Pesca con mosca: $6,000 por grupo (incluye 2, hasta 3).
- Avistamiento de ballenas y orcas (La Ventana): $1,200 por persona (lancha de 12).
- Hospedaje en La Ventana: $2,500 por noche.
- Paquete 5 noches: $45,000 por persona. Paquete 7 noches: $52,500.
- Puerto Chale: safari marino $900 por persona, avistamiento de ballenas $1,100, pesca deportiva $5,000 por grupo (incluye 2, hasta 4).

**Tableros de color de empresas**, elegidos con una hoja de contraste de cada logo contra cada campo:
- Sal y Sol: `--cafe-claro`.
- DLS Transporte: `--coral`.
- La Ventana Travel: `--verde`.
- Piratas Adventures: `--azul`.

**Licencia de pesca:** el trámite se incluye como opcional y con costo extra. Copy del prototipo: «Trámite de la licencia de pesca: opcional, con costo extra. CONAPESCA pide una por pescador». Falta que el dueño confirme el monto o si va como extra reservable.

**El prototipo está solo en español.** F10 debe llevar todo al diccionario es/en y pasar `test:contenido`.

## 8. Recursos

**Logos nuevos que el dueño puso en el checkout PRINCIPAL** (`C:\Users\kkjf\desarrollo\sistema-pescadeportiva\frontend\public\…`, sin commit y fuera de este worktree). Hay que copiarlos a `feat/marca-sun-baja`:
- `sunbajaexperience/logolg.svg`, `logomed.svg`, `logosm.svg`, `logotall.svg`. Son SVG sin color de relleno: el sol de pétalos y «SUN BAJA EXPERIENCE» o «SBE». Se pintan con `fill: currentColor`.
- `lapaz/logos/dlstransporte.png`, `ventana/logos/laventanatravel.png` (es **blanco**) y `puertochale/logos/piratasadventures.png`. Los tres son PNG con fondo transparente.
- Sal y Sol ya está en `frontend/public/logos/logo2salysol.webp` (también transparente).
- En el prototipo van como webp de 400 px en `logos/`. En el sitio real usa `next/image`.
- **Lección técnica:** `mask-image` con archivos locales falla en `file://`. El prototipo incrusta los SVG como `<symbol>`.

**Fotos y video.** Son las 9 de `frontend/public/photos/` y `frontend/public/videos/videohero.webm`. `imagenes-catalogo.ts` ya marca el relleno con `relleno: true`. `test:fotos` falla mientras haya relleno y está fuera de `verificar`.

## 9. Proceso (reglas duras del dueño)

1. **PFD solve para fijar los requisitos del plan, taste para construir.** Si el dueño ya dio un cambio concreto de composición o movimiento, va directo a taste. Para decisiones abiertas, PFD.
2. **Explica y espera luz verde antes de tocar código del sitio.** Una pregunta reflexiva no es luz verde. «Dale» o «hazlo» sí.
3. **Plan F10** en `docs/superpowers/plans/`, con tareas pequeñas y un commit por tarea, sin push. Termina cada commit con `Co-Authored-By: Claude <modelo> <noreply@anthropic.com>`, usando la línea de atribución que indique el entorno.
4. **Orden sugerido:**
   1. Tokens y `design.md`, resolviendo el conflicto de §5.
   2. Piezas compartidas: pie, filas arrastrables, tarjetas, visor, aviso de cookies.
   3. Hub.
   4. Las tres sedes.
   5. Detalle de servicio y paquete.
   6. Legales, 404 y catálogo.
   7. Barrido de código muerto.
5. **Que no quede código muerto:**
   - Cada tarea reemplaza el componente y **borra el viejo en el mismo commit**. No conviven dos versiones ni hay interruptores de diseño viejo y nuevo.
   - Antes de borrar, busca quién lo importa.
   - Agrega `knip` (archivos, exports y dependencias sin uso) dentro de `npm run verificar`.
   - Prueba de claves huérfanas del diccionario, como la limpieza de F9.
   - Barrido final de fotos y tokens sin uso, más `verificar` completo y build.
6. **Verificación:** `npm run verificar` en `frontend/`. Para este rediseño el dueño pidió explícitamente revisar con el inspector del skill y con capturas de Chrome a 1440, 768 y 390 px. Él revisa en su teléfono. Hay una captura lista en `.taste-skill/prototipos/capturar.mjs`.
7. **Catálogo real en la base local:** antes de levantar servidores, verifica con `/api/sedes/<slug>/servicios/` y corre `seed_catalogo_real --limpiar-demo` si aparece el demo.
8. **Postgres de pruebas:** contenedor `psd-pg`, `127.0.0.1:5434` (no 5433), rol `ci_rls`. Venv en `C:/Users/kkjf/desarrollo/sistema-pescadeportiva/backend/venv/Scripts/python.exe`.
9. En Git Bash, los scripts de Python con acentos se escriben a un archivo y se corren con `python -X utf8 archivo.py`.
10. Responde en español.

## 10. Pendientes del dueño antes o durante F10

- Confirmar las 5 decisiones de §2 del plan F10 (`2026-10-20-f10-plan-rediseno-campana.md`), entre ellas borrar el mapa del hub.
- Confirmar el monto o la forma del trámite de licencia.
- Fotos reales para sustituir el relleno, y el video de La Paz (hoy es el mismo de la panga).
- Una versión en negro del logo de La Ventana Travel si quiere mostrarlo sobre fondo claro; hoy va sobre su campo verde.
- Si quiere quitar también el gris de las preguntas, las notas y el paquete.
- La ruta nueva del detalle de paquete: confirmar si el backend ya entrega esos datos o hay que agregarlos.
- Los 20 comentarios del artifact siguen abiertos porque no se mandaron a Claude; la mayoría ya está aplicada. Los cierra el dueño.
- Merge único F7+F8+F9 y F10: sigue en pausa; el dueño dará la luz verde.
