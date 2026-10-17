/**
 * Cajas de campo de la marca (design.md, "Campo de texto"): 48 px de alto en móvil y 44 en
 * escritorio, radio de campo (12 px), relleno blanco, borde `borde-control` (3:1 para delimitar el
 * control; el `borde` decorativo no sirve), 16 px como mínimo en el texto (evita el zoom de iOS)
 * y, en foco, borde `ring` de 2 px.
 *
 * El borde de 2 px se pinta como 1 px de borde + 1 px de anillo interior (`ring-inset`): sumar un
 * `border-2` movería el contenido un píxel por lado y `shadow-[inset…]` no pasa la regla
 * `sombra-cruda` de la guardia. El error lleva `border-error` también de 2 px, en reposo y en
 * foco, y no cambia el relleno.
 *
 * - `CAJA_CAMPO` / `CAJA_CAMPO_ERROR`: la caja de un control que se escribe directamente (`Input`).
 * - `CAJA_CONTENEDOR` / `CAJA_CONTENEDOR_ERROR`: la misma caja para algo que ya trae su propio
 *   relleno y texto adentro (`FieldPopover compacto`, un selector): sin `px` ni tamaño de texto.
 */
const FORMA = 'min-h-12 sm:min-h-11 rounded-campo bg-superficie';

export const CAJA_CONTENEDOR = `${FORMA} border border-borde-control focus-within:border-ring focus-within:ring-1 focus-within:ring-inset focus-within:ring-ring`;

export const CAJA_CONTENEDOR_ERROR = `${FORMA} border border-error ring-1 ring-inset ring-error`;

export const CAJA_CAMPO = `${CAJA_CONTENEDOR} px-4 text-base text-tinta placeholder:text-apagado disabled:bg-cafe-bruma disabled:text-apagado`;

export const CAJA_CAMPO_ERROR = `${CAJA_CONTENEDOR_ERROR} px-4 text-base text-tinta placeholder:text-apagado`;
