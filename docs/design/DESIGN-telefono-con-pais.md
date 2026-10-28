---
surface: web
feature: telefono-con-pais (selector de país y código en el campo teléfono de los tres checkouts)
target: frontend/src/components/checkout/telefono-campo.tsx (nuevo) y checkout/campos-contacto.tsx
status: draft
author: design-advisor v2.0
date: 2026-10-27
---

# DESIGN: teléfono con país

> Lector: el dueño (decide lo visual) y senior-dev. Es una PROPUESTA; Claude se la explica antes de construir. Fuente técnica: `docs/architecture/ARCH-telefono-con-pais.md` (aprobada, no se re-deriva). Archivos leídos: `campos-contacto.tsx`, `field-popover.tsx` (está en `src/components/`, no en `ui/`), `select-personalizado.tsx`, `ui/sheet.tsx`, `ui/input.tsx`, `ui/caja-campo.ts`, `ui/error-de-campo.tsx`, `ui/variantes.ts`, `reserva/use-movil.ts`, `globals.css`.

## 1. Design system pick

Se reutiliza el sistema del checkout, sin tokens ni dependencias nuevas de UI (la regla `styles.csv`/`ux-guidelines` aplicada: *consistency*, *system-controls*, *touch-friendly-input*, *input-labels*, *error-placement*). Esquinas: `rounded-campo` vale 0 (rectángulo), la bandera es un rectángulo 3:2 sin radio, el círculo solo existe en la X de la hoja. Alturas: `min-h-12 sm:min-h-11` de `caja-campo.ts`, iguales a Nombre y Correo.

**Decisión de forma (la 1 que confirma el dueño): DOS cajas hermanas, no una caja partida.** Selector de país a la izquierda y número a la derecha, 8 px entre ellas, cada una con su borde, anillo de foco y alto. Por qué: cada mitad lleva su propio foco visible sin ambigüedad (en una caja única con `focus-within` el anillo no dice si el foco está en el país o en el número), y se usan `CAJA_CONTENEDOR` e `Input` tal cual, sin `aspecto="heredado"` (que el repo quiere borrar). Alternativa descartada: caja unida con divisor; se ve más "pro" pero obliga a un foco doble y a una variante nueva.

**Cambio de icono:** el campo teléfono pierde el icono `Phone` de la izquierda (la bandera ocupa ese lugar); Nombre y Correo conservan el suyo. El `Input` del número va sin `pl-11` (relleno de 16 px).

**Cambio aditivo en `FieldPopover`** (único toque a un componente existente): una prop opcional `etiquetaDisparador?: string` que se pasa como `aria-label` del botón. Hoy el botón se nombra por su texto ("+52") y falta el país. Sin otro cambio de comportamiento; `SelectPersonalizado` y la hora no se afectan.

## 2. Inventario de componentes

| Componente | Estado | Papel y estados |
|---|---|---|
| `TelefonoCampo` (`checkout/telefono-campo.tsx`) | nuevo | Fila: disparador + `Input`. Decide popover o `Sheet` con `useMovil()`. Estados: reposo, foco (en cualquiera de las dos cajas), error (ambas cajas), deshabilitado, abierto. |
| `SelectorPais` (`checkout/selector-pais.tsx`) | nuevo | Dentro del panel/hoja: buscador + lista + sin resultados. Se monta igual en `FieldPopover` y en `Sheet`. |
| `Bandera` (`ui/bandera.tsx`) | nuevo | 24x16 (tamaño `m`) o 20x14 (`s`, resumen), `alt=""`, `next/image` sin optimizar, caja reservada, borde `border-borde` de 1 px (la bandera blanca de Japón o Finlandia no se pierde en un campo blanco; es decorativo, 1,27:1 basta). Sin archivo: icono `Globe` del mismo tamaño. |
| `FieldPopover` | existe | + prop `etiquetaDisparador`. Cierra con Esc, clic fuera y devuelve el foco al botón. |
| `Sheet`, `Input`, `Button`, `ErrorDeCampo`, `Despliegue` | existen | Sin cambios. |
| `CamposContacto` | existe | La rama `phone` usa `TelefonoCampo` dentro de `div role="group"` con `label htmlFor` al input (ver ARCH §4). |
| Resumen del pedido (`resumen-paquete`, renglón "Tus datos") | existe | Muestra `Bandera s` + número formateado (sección 3, "Resumen"). |

## 3. Wireframes y comportamiento

### Campo en reposo, escritorio (columna `sm:col-span-1`, ancho ~300 a 340 px)
```
Número telefónico                      <- text-muted, igual que Correo
+------------+  +------------------------------+
| [MX] +52 v |  | Ej. 612 123 4567             |   alto 44 px (48 en móvil)
+------------+  +------------------------------+
 7,5rem fijos     flex-1, px-4, sin icono
```
- Disparador de ancho FIJO 7,5 rem (120 px): bandera 24 + 8 + "+998" tabular + 8 + `CaretDown` 16 con `px-3`. Fijo para que cambiar de país no mueva el número. Texto `text-base sm:text-sm`, color `text-tinta`; caret `text-muted`.
- Número: `type=tel`, ancho restante (~170 a 210 px, cabe "212 555 123456789"). Placeholder: México `Ej. 612 123 4567` (clave existente); otro país, neutro `phonePlaceholderOther` (ARCH decía vacío; una caja vacía junto a "+47" se lee como rota. Si el dueño prefiere vacío, es quitar la clave).
- Móvil (<640): mismo diseño, a todo el ancho (disparador 120 px, número el resto, ~215 px en 375), alto 48 px, texto 16 px.
- Alineación: etiqueta, cajas y error comparten borde izquierdo con Nombre y Correo; las dos filas de la rejilla quedan a la misma altura porque cajas y `ErrorDeCampo` ocupan lo mismo que el `Input` de Correo.

### Lista abierta, escritorio (panel de `FieldPopover`, `sm:w-80` = 320 px, ancla al disparador)
```
+--------------------------------------+
| [lupa] Buscar país o código          |   Input 44 px, sticky arriba
|--------------------------------------|
| Frecuentes                           |   cabecera, text-sm text-muted
| [MX] México                  +52   v |   v = Check de la seleccionada
| [US] Estados Unidos           +1     |
| [CA] Canadá                   +1     |
| Otros países                         |
| [DE] Alemania                +49     |
| [AR] Argentina               +54     |
|  ...  (alto fijo de la lista)        |
+--------------------------------------+
```
- Lista de alto FIJO, no máximo: `h-[min(22rem,calc(100dvh-14rem))]` (8 filas). Fijo para que, al filtrar, el buscador no se mueva (el panel abre hacia arriba si no hay sitio y un panel que encoge movería el buscador mientras se teclea). Un solo desplazamiento: el del panel no se activa porque la lista cabe en el espacio medido por `FieldPopover`.
- Orden: Frecuentes = México, Estados Unidos, Canadá (siempre ese orden). "Otros países" = resto alfabético con `Intl.Collator(lang)` (es: Ñ y acentos bien colocados), **sin repetir** los tres de arriba (ids y `aria-selected` únicos). Cambio de texto: `phoneCountryAll` pasa a "Otros países" / "Other countries".
- Fila: `min-h-11` (44) en popover y `min-h-12` (48) en hoja, `px-3`, bandera `m`, nombre localizado (puede ocupar 2 líneas; se prefiere ajuste a truncado), código a la derecha en `text-muted` tabular, y una columna de 20 px SIEMPRE reservada para el `Check` (no hay salto entre filas). El +1 muestra sus 25 países con el mismo "+1"; los distingue el nombre. +7 y +44 igual.
- Fila activa (teclado o cursor encima): fondo `cafe-bruma`; con teclado además anillo interior de 2 px `tinta` (16:1). Fila seleccionada: `Check` + `font-medium`, **sin relleno `bg-accent`** (el patrón de `SelectPersonalizado` no sirve aquí: el anillo azul de foco sobre café mide 1,22:1).
- Al abrir: la fila seleccionada queda visible y activa (scroll instantáneo, `block: nearest`). Con texto en el buscador, la primera coincidencia queda activa.
- Buscador: sin acentos ni mayúsculas; entiende nombre ("alem", "germany"), código con o sin `+` ("34", "+34") y sigla de 2 letras ("ES"). Con texto desaparecen las cabeceras y los resultados van planos, ordenados: coincidencia exacta de sigla o código, nombre que empieza con, nombre que contiene. Se reinicia al abrir.
- Sin resultados (sin cabeceras, en el área fija de la lista, centrado): `Sin resultados` en `text-foreground` y debajo `Prueba con el nombre, el código (+34) o la sigla (ES)` en `text-muted`. No hay botón de acción: limpiar es borrar el texto.
- Lista nunca vacía en origen (siempre hay 245). Estado "falló la carga" no existe: la lista es local. Si `Intl.DisplayNames` falta, el nombre cae al ISO y la lista sigue operable.

### Hoja móvil (<640 px, `Sheet`)
```
+--------------------------------------+
|              ----                    |  asa
| País y código del teléfono        (X)|  título + cierre 48x48
| [lupa] Buscar país o código          |  Input 48 px
|--------------------------------------|
| Frecuentes                           |
| [MX] México                  +52   v |  filas 48 px
|  ...  alto fijo, la hoja no encoge   |
+--------------------------------------+
```
- No se enfoca el buscador al abrir (queda el foco en el título, como ya hace `Sheet`): el teclado no tapa la lista al instante y los tres frecuentes se eligen con un toque. Tocar el buscador abre el teclado.
- Teclado abierto: el buscador está arriba, nunca queda tapado. Mientras la hoja está abierta, un efecto escucha `visualViewport` y escribe `--teclado` (px = `innerHeight - vv.height - vv.offsetTop`, mínimo 0); la hoja se levanta con `bottom: var(--teclado)` y la lista usa alto fijo `calc(85dvh - 8.5rem - var(--teclado))` con mínimo 8 rem. Sin `visualViewport`, `--teclado` vale 0 y la lista simplemente se desplaza. El alto de la lista no cambia al filtrar (el buscador no se mueve).
- Cierre: X, Esc, tocar fuera (todo ya en `Sheet`). Al elegir un país la hoja cierra sola y el foco vuelve al disparador (nativo de `<dialog>`); no se fuerza el teclado.
- Tamaño táctil: filas 48, X 48, buscador 48, disparador 48 de alto por 120 de ancho; separación de 8 px entre disparador e input.

### Estados del campo
| Estado | Disparador | Número | Extra |
|---|---|---|---|
| Reposo | `CAJA_CONTENEDOR`, caret `text-muted` | `Input` normal | - |
| Foco (cualquiera) | borde y anillo interior `ring` (azul, 6,9:1 sobre blanco, 6,5:1 sobre arena) solo en la caja enfocada | igual | El foco de la fila activa de la lista es el anillo `tinta` de arriba |
| Escribiendo | sin cambio | solo dígitos y `+ ( ) - . espacio`; sin formato en vivo ni error; si había error se retira al teclear | - |
| Error | `CAJA_CONTENEDOR_ERROR` (2 px `error`) en AMBAS cajas: el error es del número completo | `CAJA_CAMPO_ERROR` | `ErrorDeCampo` debajo de la fila entera, con icono y texto (no solo color); error 6,2 a 6,7:1 |
| Deshabilitado | `disabled`, `bg-cafe-bruma text-apagado`, no abre | igual | Mismo tratamiento que el resto del paso con pago en curso |
| Abierto | `aria-expanded`, caret gira 180° | - | - |
| País cambiado con número escrito | Bandera y código cambian (fundido 150 ms) | **No se toca**: ni se borra ni se trunca | Anuncio por región viva; sin toast ni borde de aviso. Si el largo ya no cuadra, el error sale al salir del campo o al Continuar, nunca al elegir |
| Pegado con `+` o `00` que cambia el país | Igual que arriba, el selector se mueve solo | El texto queda solo con la parte nacional (el cliente ve desaparecer el `+34` que pegó) | El anuncio dice el país nuevo; es el aviso para quien mira |

### Carga de banderas
- Cada bandera ocupa su caja 24x16 desde el primer pintado (`width`/`height` fijos en `Bandera`), con fondo `cafe-bruma` hasta que llega (no salta nada, sin esqueleto animado). Las 267 no se piden juntas: la bandera del disparador carga con la página; al abrir la lista solo se piden las de las filas visibles más un colchón (carga diferida nativa de `next/image`, ~10 a 14 SVG de 0,6 a 3,4 KB). No hay lista de carga ni spinner.
- Sin archivo (`XK`, `AC`, `TA`): `Globe` de 20 px centrado en la misma caja, `text-muted`.

### Resumen del pedido
- Panel de resumen y pantalla de resumen móvil: `[Bandera s] +52 612 123 4567` y, en `text-muted` tras un punto medio, el nombre del país (`· México`); se permite pasar a segunda línea. El país visible es la defensa principal contra el riesgo R1 del ARCH (turista que ignora el selector).
- Renglón de una línea de "Tus datos" ya completado: `[Bandera s] +52 612 123 4567`; el nombre del país va en texto solo para lector de pantalla (`sr-only`), por falta de ancho. Senior-dev: si el renglón real admite el nombre sin desbordar a 375 px, mostrarlo.
- Teléfono no parseable (viejo): se muestra tal cual, sin bandera.

## 4. Contrato de accesibilidad

Meta: WCAG 2.2 AA. Contrastes calculados con los tokens de `globals.css`: foco azul 6,94 (blanco) y 6,46 (arena); `tinta` sobre `cafe-bruma` 16,07; `apagado` 6,37 y 5,93; `error` 6,67 y 6,21; `borde-control` 3,42 y 3,19 (delimita el control, cumple 3:1).
- **Grupo:** `div role="group"` con `aria-labelledby` = etiqueta; `label htmlFor` solo apunta al input. El disparador NO va dentro de un `<label>`.
- **Disparador:** `button`, `aria-haspopup="dialog"` (ya en `FieldPopover`), `aria-expanded`, nombre `"País y código del teléfono: México +52"` (se compone con `phoneCountry` + país + código). Bandera `alt=""`.
- **Panel/hoja:** diálogo (`FieldPopover` ya es `role=dialog` con `aria-label`; `Sheet` usa `<dialog>` modal con título). Dentro: buscador `role="combobox"`, `aria-expanded="true"`, `aria-controls` = id de la lista, `aria-autocomplete="list"`, `aria-activedescendant` = id de la fila activa, `aria-label` = `phoneCountrySearch`. Lista `role="listbox"` con `aria-label` = `phoneCountry`; cabeceras como `role="group"` con `aria-labelledby`; filas `role="option"` con `aria-selected`; nombre = texto de la fila ("México, +52"). Hay que dar ids estables a las filas.
- **Teclado:** Tab llega al disparador y luego al número. Con el disparador: Enter o Espacio abren. Con el panel abierto el foco se queda en el buscador (en escritorio se enfoca al abrir): escribir filtra; Flecha abajo/arriba mueven la fila activa (circular no; se detiene en los extremos); Inicio/Fin en la lista; Re Pág/Av Pág saltan 8; Enter elige; Esc cierra y devuelve el foco al disparador; Tab dentro del panel cierra sin elegir (no hay otra cosa que tabular). Los controles dependientes de la hover no existen.
- **Foco al elegir:** escritorio: el foco pasa al número (siguiente acción natural; `FieldPopover.cerrar` no mueve el foco, `TelefonoCampo` lo hace). Móvil: vuelve al disparador (lo hace `<dialog>`), sin teclado por sorpresa.
- **Anuncios:** región `aria-live="polite"` única, visualmente oculta, dentro del grupo: al cambiar el país (por lista o por pegado con `+`) dice `phoneCountryChanged`; con el buscador abierto, el conteo de resultados (con 300 ms de retraso) `phoneCountryCount`. El error usa `role="alert"` ya existente en `FieldError` y `aria-describedby` en el input (`propsDeError`); el foco y scroll al error ya los hace `ErrorDeCampo`.
- `autocomplete="tel"`, `inputMode="tel"`, `enterKeyHint="next"`, `dir="ltr"` (también en árabe/hebreo el número va de izquierda a derecha).
- `prefers-reduced-motion`: ver sección 6. Zoom de texto al 200 %: el disparador es de ancho fijo en rem (crece con el texto) y el número cede ancho; a 375 px con 200 % el número aún cabe en una línea gracias a `min-w-0`.

## 5. Contrato responsive

| Ancho | Qué cambia |
|---|---|
| < 640 | Dos cajas a todo el ancho, 48 px, 16 px de texto. Lista en `Sheet` (≤85dvh, `safe-area` ya incluido en `Sheet`). Dentro del asistente (`AsistenteMovil`) el campo vive en la pantalla "Tus datos" como los demás; la hoja es un `<dialog>` modal, no cambia la pantalla ni el historial. |
| 640 a 1023 (tablet) | Rejilla de 2 columnas, teléfono en `col-span-1`; lista en `FieldPopover` de 320 px con filas de 44 px (táctil). Si el panel se saldría por la derecha de la ventana, se recoloca con `right-0` (prueba en 640 y 768). |
| ≥ 1024 | Igual que tablet, 44 px de alto, texto 14 px. |
| Horizontal en teléfono (≥640 de ancho, poco alto) | Popover con `calc(100dvh-14rem)` en la lista: nunca doble desplazamiento. |
Cruce 640: si el panel está abierto al girar o redimensionar, se cierra (el contenedor cambia de tipo) y se conserva el país elegido.

## 6. Contrato de movimiento

| Qué | Cómo | Reducir movimiento |
|---|---|---|
| Panel del popover | el existente de `FieldPopover` (resorte, opacidad+escala 0,97) | solo opacidad |
| Hoja | animación `.hoja-dialogo` existente | la que ya tiene `Sheet` |
| Caret | gira 180° en `--duracion-corta` (150 ms) con `--curva-estandar` | sin giro, cambia de golpe |
| Bandera/código al cambiar de país | fundido cruzado 150 ms (opacidad) | cambio instantáneo |
| Error | `ErrorDeCampo` (`Despliegue`) | el de `Despliegue` |
| Scroll a la fila activa | instantáneo siempre (no hay cola de animación mientras se teclea) | igual |
Sin hover animado en filas más allá del color de fondo (`transition-colors`, 150 ms).

## 6.5 Integración de plataforma

n/a (web). Solo el `visualViewport` de la hoja móvil (sección 3) y los atributos de autocompletado de la sección 4. Banderas bajo `public/flags/` (`'self'`, sin cambio de CSP).

## 7. Tokens y textos

**Tokens: ninguno nuevo.** Se usan: `--radius-campo` (0), `--color-borde-control`, `--color-ring` (azul, foco), `--color-error`, `--color-tinta` (anillo de fila activa, igual que el cierre de `Sheet`), `--color-apagado`/`text-muted`, `--color-cafe-bruma` (hover, carga de bandera), `--superficie`, `--shadow-n2`, `--duracion-corta`, `--curva-estandar`. Variable local nueva solo dentro del componente: `--teclado` (px, la escribe un efecto).

| Clave (`checkout.`) | es | en |
|---|---|---|
| `phone` | Número telefónico (existe) | Phone number (existe) |
| `phoneCountry` | País y código del teléfono | Country and phone code |
| `phoneCountrySearch` | Buscar país o código | Search country or code |
| `phoneCountryNone` | Sin resultados | No results |
| `phoneCountryNoneHint` | Prueba con el nombre, el código (+34) o la sigla (ES) | Try the name, the code (+34) or the abbreviation (ES) |
| `phoneCountryFrequent` | Frecuentes | Frequent |
| `phoneCountryAll` | Otros países | Other countries |
| `phoneCountryCount` / `phoneCountryCountOne` | {n} resultados / 1 resultado | {n} results / 1 result |
| `phoneCountryChanged` | País cambiado a {pais}, código {codigo} | Country changed to {pais}, code {codigo} |
| `phonePlaceholderOther` | Número sin el código | Number without the code |
| `phoneRequired` (si no existe ya una clave de obligatorio reutilizable) | Escribe tu número de teléfono. | Enter your phone number. |
| `invalidPhone` (reescrita) | El número parece incompleto para {pais} ({codigo}). Revisa los dígitos o cambia el país. | The number looks incomplete for {pais} ({codigo}). Check the digits or change the country. |
| `phoneUnknownCode` | No reconocemos ese código de país. Elígelo de la lista. | We do not recognize that country code. Pick it from the list. |

Cierre de la hoja: reusar la clave de «Cerrar» que ya pasan las otras hojas. Interpolación: el mismo estilo de `{n}` de las claves ya existentes (si no hay uno, `.replace`). Sin raya larga (guardia `guion-largo`). `invalidPhone` incluye país y cómo arreglarlo (regla *error-clarity*) y es la segunda defensa de R1.

## 8. Fuera de alcance

Detección de país por IP o idioma; formato en vivo mientras se teclea; selector de país con teclado de tipeo sobre el disparador cerrado (escribir para buscar ocurre dentro del panel abierto); virtualización (245 filas planas bastan); favoritos o recientes; extensión de PBX; modo oscuro (el sitio no lo tiene); correos y plantilla de WhatsApp; validación de que el prefijo exista.

## 9. Decisiones visuales que el dueño debe confirmar

1. **Dos cajas hermanas** (país | número) en vez de una caja unida, y el icono de teléfono sustituido por la bandera.
2. **Resumen con el nombre del país visible** (`+52 612 123 4567 · México`) en el panel de resumen, y solo en texto de lector en el renglón de una línea.
3. **Móvil sin teclado al abrir la hoja**: se abre con los tres frecuentes a un toque y el buscador espera a que lo toquen.

## 10. Preguntas abiertas (con default)

1. Placeholder neutro "Número sin el código" con otro país: default sí (quitar la clave si no).
2. "Otros países" sin repetir México/EE.UU./Canadá: default sí (evita ids duplicados; quien busque "México" en la M lo ve arriba).
3. `invalidPhone` con el país nombrado (cambia el texto aprobado del ARCH §7): default sí; si no, el texto del ARCH.
4. Escribir en el disparador cerrado para abrir con esa letra: default no (v1).
5. Altura de la hoja con teclado abierto en iOS Safari y Chrome Android: no se puede verificar sin teléfono; default el cálculo con `visualViewport`; revisión manual del dueño (suma a la lista §9 del ARCH).
6. Nombre del país en el renglón de una línea: default `sr-only`; subir a visible si cabe.

## 11. Hand-off para senior-dev (T1 a T8 del ARCH §10)

| Tarea | Aporte de diseño |
|---|---|
| T1, T2 | Ninguno visual. T2 devuelve por país: `iso`, `nombre`, `codigo`, `frecuente`; `buscar(texto)` con el orden de la sección 3. |
| T3 | `ui/bandera.tsx` con props `iso`, `tam: 'm' \| 's'`; borde `border-borde`, fondo `cafe-bruma`, caja fija; `Globe` de respaldo. Probar con `JP`, `FI`, `XK`. |
| T4 | `checkout/selector-pais.tsx` (buscador, grupos, filas, sin resultados, ids, teclado) y `checkout/telefono-campo.tsx` (fila, popover o `Sheet`, `--teclado`, región viva, foco al elegir); `campos-contacto.tsx` (rama `phone`); `components/field-popover.tsx` (+ `etiquetaDisparador`). Estados de la sección 3. |
| T5 | Los resúmenes usan `Bandera s` + `formatearTelefono` (sección 3, "Resumen"); verificar el renglón de "Tus datos" a 375 px. |
| T6 | Tabla de claves de la sección 7 en `es.json` y `en.json`; reiniciar `next dev`. |
| T8 | `npm run verificar`; revisar `guardia` (cero `<img>`, `<button>`, `<input>` crudos, colores literales, radios 12/16); revisión manual del dueño: teléfono real con teclado abierto, lector de pantalla, tablet a 640 y 768. |
Orden: T4 no empieza antes de que el dueño confirme la sección 9. No se toca el backend ni `lib/` desde este diseño.

DESIGN-ADVISOR: READY (para confirmar con el dueño: 1. dos cajas hermanas con bandera en lugar del icono de teléfono; 2. nombre del país visible en el resumen; 3. hoja móvil que se abre sin teclado)
