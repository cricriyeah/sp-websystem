# Sun Baja Experience — Sistema de diseño: referencia de tokens

> Léelo primero. Para las especificaciones de componentes y de la página de reserva ve [design-components.md](design-components.md). Para accesibilidad y qué hacer / qué no ve [design-guidelines.md](design-guidelines.md).

Lenguaje: **costero, deportivo y moderno**, con una marca cálida (café) y tres colores que cuentan qué tipo de actividad es (mar, ciudad, outside/montaña). Titulares en la monoespaciada de consola (Consolas), cuerpo en San Francisco (la fuente del sistema de Apple), esquinas redondeadas que hacen eco del logo redondo, superficies planas sin sombras grandes. Unidad base de espaciado: 4 px. Plataformas: web responsive (móvil primero), es/en.

> Decisiones del dueño (2026-10-15): botón principal en café con texto blanco; titulares en Consolas (monoespaciada de consola); cuerpo en San Francisco; radio 12 px en controles y 16 px en tarjetas; neutros cálidos (arena y blanco), sin negro puro. Todos los contrastes de este documento se calcularon con la fórmula de WCAG 2.2 (luminancia relativa) sobre los hex indicados.

---

## Colores

### Marca — café (color principal)

| Token | Hex | Uso | Contraste |
|---|---|---|---|
| `cafe` | `#7C3B02` | Botón principal, enlaces de acción, marca | 8,46:1 con blanco |
| `cafe-hondo` | `#5D2C02` | Hover del botón principal | 11,50:1 con blanco |
| `cafe-profundo` | `#3E1E01` | Pulsado, texto sobre `cafe-claro` | 12,80:1 sobre `cafe-bruma` |
| `cafe-medio` | `#B08967` | Ilustración, líneas decorativas | solo decorativo |
| `cafe-claro` | `#FEE0AC` | Fondos de aviso, rango de fechas confirmado | 11,84:1 con `cafe-profundo` |
| `cafe-bruma` | `#F2EBE6` | Superficie variante, vista previa de rango | 7,17:1 con `cafe` |

### Actividades — qué tipo de experiencia es

Estos tres colores **solo** identifican el tipo de actividad (etiquetas, insignias, ilustración). **Nunca** se usan como color de estado (éxito, error, aviso) ni como color de botón.

| Token | Hex | Significa | Texto sobre el color | Texto sobre su claro |
|---|---|---|---|---|
| `azul` | `#1B607F` | Mar (pesca, paseos en lancha) | blanco, 6,94:1 | `azul` sobre `#DDE6EB`, 5,48:1 |
| `coral` | `#F64A25` | Ciudad (recorridos urbanos, ciudad, vida nocturna) | **tinta** `#1F1A14`, 4,87:1 (con blanco solo 3,54:1: no usar) | `coral-texto` `#8F2409` sobre `#FBC2B5`, 5,56:1 |
| `verde` | `#343F04` | Outside / montaña / naturaleza | blanco, 11,30:1 | `verde` sobre `#DFFFA8`, 10,23:1 |

Escalas derivadas (sacadas de cada primario mezclándolo con blanco o negro):

| Familia | `hondo` (−25 % luz) | `profundo` (−50 %) | `medio` (+40 % blanco) | `claro` (dado) | `bruma` (+90 % blanco) |
|---|---|---|---|---|---|
| azul | `#14485F` | `#0E3040` | `#76A0B2` | `#DDE6EB` | `#E8EFF2` |
| coral | `#B9381C` | `#7B2513` | `#FA927C` | `#FBC2B5` | `#FEEDE9` |
| verde | `#272F03` | `#1A2002` | `#5D6536` (6,21:1 con blanco) | `#DFFFA8` | `#EBECE6` |

`coral-texto` = `#8F2409`: el coral nunca se usa como texto sobre blanco (3,54:1 no alcanza 4,5:1); cuando haga falta texto en esa familia se usa este tono (8,66:1 sobre blanco).

> **Categorías confirmadas por el dueño:** azul = mar, coral = ciudad, verde = outside o montaña (una sola familia). Cada actividad pertenece a una.

### Superficies y neutros (cálidos, sin negro puro)

| Token | Hex | Uso | Contraste |
|---|---|---|---|
| `arena` | `#FBF7F0` | Fondo de página | tinta sobre arena 16,17:1 |
| `blanco` | `#FFFFFF` | Tarjetas, calendario, campos | tinta sobre blanco 17,27:1 |
| `tinta` | `#1F1A14` | Texto principal y titulares | ver arriba |
| `tinta-suave` | `#4A3F33` | Texto secundario | 9,59:1 sobre arena |
| `apagado` | `#6B5D4D` | Ayudas, etiquetas, texto terciario | 6,37:1 blanco / 5,96:1 arena / 5,40:1 sobre `cafe-bruma` |
| `borde` | `#D9C9B4` | Divisores y bordes **decorativos** | 1,62:1 (no sirve para delimitar un control) |
| `borde-control` | `#8A7A66` | Borde de campos, casillas y botones secundarios | 4,15:1 blanco / 3,89:1 arena (cumple 3:1) |

**¿Blanco y negro?** Sí el blanco, no el negro puro. El blanco funciona como superficie de lectura (tarjetas, calendario, campos) y da el aire limpio y deportivo; el negro puro (`#000`) choca con el café y endurece la marca costera. Se usa `tinta` `#1F1A14` en su lugar.

### Estados del sistema

Los estados tienen su propio color, distinto de las tres actividades, y siempre llevan icono y texto (nunca solo color).

| Estado | Texto / icono | Fondo | Contraste | Notas |
|---|---|---|---|---|
| Éxito | `#2F5D0A` | `#E7F5D3` | 6,84:1 | Icono de palomita. Familia verde, pero distinto del `verde` de actividad |
| Error | `#B3261E` | `#FDE7E4` | 5,52:1 (6,54:1 sobre blanco) | Icono de alerta. Es un rojo más profundo que el coral para que no se lea como «ciudad» |
| Aviso | `#6B3A00` | `#FEE0AC` (`cafe-claro`) | 7,39:1 | Icono de triángulo |
| Información | `#0F3D52` | `#DDE6EB` (`azul-claro`) | 9,17:1 | Icono de «i». Familia azul, pero distinta del `azul` de actividad |
| Enfoque | `#1B607F` (`azul`) | — | 6,94:1 blanco / 6,50:1 arena | Anillo de 2 px con desfase de 2 px |

**Riesgo conocido:** éxito (verde) e información (azul) comparten familia con dos actividades. La separación depende del icono y del texto, no del color; no uses un chip de actividad para comunicar un estado.

### Roles de botón

| Rol | Fondo | Texto | Contraste |
|---|---|---|---|
| Principal | `cafe` | blanco | 8,46:1 |
| Secundario | blanco, borde `borde-control` | `cafe` | `cafe` sobre blanco 8,46:1 |
| Terciario / texto | transparente | `cafe` | 8,46:1 sobre blanco |
| Destructivo | `error` `#B3261E` | blanco | 6,54:1 |
| Deshabilitado | `cafe-bruma` | `apagado` | 5,40:1 |

---

## Tipografía

| Rol | Familia | Fallback |
|---|---|---|
| Titulares | **Consolas** (la monoespaciada de consola de Windows y Office) | `Consolas, "SF Mono", SFMono-Regular, Menlo, "Roboto Mono", ui-monospace, monospace` |
| Cuerpo y formularios | **San Francisco** (la fuente del sistema de Apple: `-apple-system` / `system-ui`) | `-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` |
| Cifras de dinero | misma fuente del cuerpo con `font-variant-numeric: tabular-nums` | — |

Ninguna de las dos se descarga: son fuentes que ya traen los dispositivos, así que no cuestan carga y no hay licencia que gestionar. **Cada dispositivo muestra la suya:** San Francisco solo existe en dispositivos de Apple (en Windows cae a Segoe UI y en Android a Roboto) y Consolas solo en Windows y Office (en Apple cae a SF Mono o Menlo, en Android a Roboto Mono). El aspecto exacto de los titulares cambia de un dispositivo a otro; la licencia de Apple no permite servir San Francisco desde el sitio. Sustituye a *Instrument Sans*. *Bebas Neue* y *Bella Fashion* (esta con licencia «solo uso personal») salen del proyecto.

| Estilo | Móvil | Escritorio | Peso | Interlineado | Tracking |
|---|---|---|---|---|---|
| Display (portada) | 40 px | 64 px | 800 | 1,05 | −0,02 em |
| **Título de página (reserva)** | **36 px** | **56 px** | 800 | 1,1 | −0,02 em |
| Título de sección | 28 px | 36 px | 700 | 1,15 | −0,01 em |
| **Título de paso (tarjeta)** | **24 px** | **28 px** | 700 | 1,2 | −0,01 em |
| Subtítulo | 20 px | 22 px | 600 | 1,3 | 0 |
| Cuerpo | 16 px | 16 px | 400 | 1,5 | 0 |
| Cuerpo pequeño | 14 px | 14 px | 400 | 1,45 | 0 |
| Etiqueta / botón | 16 px | 16 px | 600 | 1,2 | 0,01 em |
| Pie / aclaración | 12 px | 12 px | 400 | 1,4 | 0,01 em |

- Mínimo 16 px en campos de formulario (evita el zoom automático de iOS).
- La monoespaciada es ancha: los titulares largos van en caja de oración (no todo mayúsculas) y con `text-wrap: balance`.
- Los títulos de paso pasan de ~18 px a 24/28 px (petición del dueño: «más grandes»).

---

## Forma (radio)

El logo es redondo. El radio ideal es el que se nota sin volver pastilla todo el sitio: aproximadamente un cuarto de la altura de un control de 48 px.

| Token | Radio | Componentes |
|---|---|---|
| `radio-xs` | 4 px | Texto resaltado, insignias pequeñas |
| `radio-sm` | 8 px | Etiquetas, tooltips, imágenes pequeñas |
| `radio-control` | **12 px** | Botones, campos, selectores, casillas de opción |
| `radio-card` | **16 px** | Tarjetas, resumen, paneles, popover del calendario |
| `radio-sheet` | 24 px (solo esquinas superiores) | Hojas inferiores y barra fija de móvil |
| `radio-full` | 9999 px | Chips de actividad, atajos de fecha, línea de progreso, **día del calendario (círculo)** |

El círculo del día del calendario repite la forma del logo.

---

## Elevación

Superficies planas: la jerarquía la hacen el color y el borde, no la sombra. La sombra grande del resumen se elimina.

| Nivel | Sombra | Uso |
|---|---|---|
| 0 | ninguna, borde `borde` 1 px | Tarjetas, resumen de la reserva, calendario |
| 1 | `0 -1px 0 #D9C9B4, 0 -6px 16px rgb(31 26 20 / .08)` | Barra inferior fija de móvil (sombra hacia arriba) |
| 2 | `0 8px 24px rgb(31 26 20 / .14)` | Popover, menú desplegable, hoja modal |

Nada usa sombras mayores que el nivel 2.

---

## Estados de interacción

| Estado | Capa sobre el color base | Notas |
|---|---|---|
| Reposo | 0 % | — |
| Hover | 8 % de `tinta` | Solo con puntero |
| Enfoque (teclado) | anillo 2 px `azul` + desfase 2 px | Siempre visible, nunca se elimina |
| Pulsado | 12 % de `tinta` | Escala 0,98 en botones |
| Seleccionado | relleno `cafe` | En el calendario y en opciones de tarjetas |
| Deshabilitado | fondo `cafe-bruma`, texto `apagado` | Siempre acompañado de la razón en texto (ver guías) |

---

## Espaciado y layout

Escala (4 px): `4, 8, 12, 16, 24, 32, 48, 64`.

| Clase | Ancho | Columnas | Reserva |
|---|---|---|---|
| Compacta | < 640 px | 1 | Asistente de un paso por pantalla, barra inferior fija |
| Media | 640–1023 px | 1 | Tarjetas de pasos en una columna, resumen debajo |
| Expandida | ≥ 1024 px | 2 (pasos 640 px + resumen 360 px) | Tarjetas plegables, resumen fijo a la derecha |

Margen lateral: 16 px en móvil, 24 px en tablet, 32 px en escritorio. Ancho máximo del contenido: 1120 px.

---

## Movimiento

| Token | Valor | Uso |
|---|---|---|
| `duracion-corta` | 150 ms | Hover, enfoque, pulsado |
| `duracion-media` | 250 ms | Plegar y desplegar tarjetas, cambio de paso |
| `duracion-larga` | 400 ms | Cambio de mes del calendario, entradas de hoja |
| `curva-estandar` | `cubic-bezier(0.2, 0, 0, 1)` | Entradas y cambios de estado |
| `curva-salida` | `cubic-bezier(0.4, 0, 1, 1)` | Salidas |

Con `prefers-reduced-motion: reduce` solo se anima la opacidad. El cambio de paso en móvil desliza en la dirección de avance o retroceso.

---

## Iconos

Librería actual (Phosphor), peso `bold` para acciones y `regular` para decoración. Tamaños: 16 (en texto), 20 (botones), 24 (navegación). Un estado nunca se comunica solo con un icono de color: va con texto.

---

## Nombres de tokens (convención)

`--color-<rol>`, `--radio-<tamaño>`, `--sombra-<nivel>`, `--texto-<estilo>`, `--duracion-<tamaño>`. En Tailwind 4 los nombres de forma se declaran como `--radius-control`, `--radius-campo`, etc. dentro de `@theme` (ver el plan de la base del frontend).

### Mapeo desde los tokens actuales (`globals.css`)

| Actual | Nuevo | Nota |
|---|---|---|
| `--accent` (`#281ab5` índigo) | `cafe` | El índigo sale |
| `--action` (`#ffde00` amarillo) | `cafe` (botón principal) | El amarillo sale |
| `--foreground` (`#16171c`) | `tinta` `#1F1A14` | |
| `--background` (`#ffffff`) | `arena` (página) / `blanco` (superficies) | |
| `--surface`, `--surface-deep` | `cafe-bruma`, `cafe-claro` | |
| `--border`, `--border-strong` | `borde`, `borde-control` | |
| `--exito`/`--error`/`--aviso` (+ `-fondo`) | valores de la tabla de estados | |
| `--font-titulo` (Bebas), `--font-acento` (Bella), `--font-cuerpo` (Instrument) | Consolas / San Francisco | Bella y Bebas se retiran |
