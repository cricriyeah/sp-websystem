// Módulo puro, SIN imports: el runner de pruebas compila solo src/ y Node no resuelve
// paquetes ahí. Las primitivas (button.tsx) combinan estas clases con `cn`, que fusiona
// los conflictos en orden de cadena (los TAMANOS van después de las VARIANTES a propósito).

// Contrato visual de `Button` (design.md, "Roles de botón", y design-components.md): 48 px de alto
// en móvil y 44 en escritorio, radio de control (12 px), etiqueta `texto-etiqueta` y foco con el
// anillo `ring` de 2 px y 2 px de desfase (el desfase se pinta con la superficie que lo contiene).
// Un botón NUNCA se deshabilita con `opacity`: el deshabilitado y `aria-disabled` cambian de color
// (`cafe-bruma` con texto `apagado`). Las etiquetas largas pasan a dos renglones (`py-3`,
// `text-balance`) y nunca se truncan: el monto del botón de pago tiene que verse.
const BASE =
  'inline-flex items-center justify-center gap-2 rounded-control px-6 py-3 text-center text-balance texto-etiqueta ' +
  'min-h-12 sm:min-h-11 transition-[background-color,transform] duration-150 ease-[var(--curva-estandar)] ' +
  'active:scale-[0.98] motion-reduce:active:scale-100 ' +
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ' +
  'disabled:cursor-not-allowed aria-disabled:cursor-not-allowed';

// Deshabilitado y `aria-disabled` (acción en curso). `aria-disabled:hover:` gana al `hover:` de la
// variante: un botón en curso no cambia de color al pasar el puntero.
const APAGADO = 'disabled:bg-cafe-bruma disabled:text-apagado aria-disabled:bg-cafe-bruma aria-disabled:text-apagado';

const BASE_CAMPANA = BASE.replace('rounded-control', 'rounded-full'); // píldora: el sitio público (F10) no usa el radio de control

const VARIANTES = {
  principal:
    `bg-cafe text-white hover:bg-cafe-hondo active:bg-cafe-profundo ${APAGADO} ` +
    'aria-disabled:hover:bg-cafe-bruma aria-disabled:active:bg-cafe-bruma',
  secundario:
    'border border-borde-control bg-superficie text-tinta hover:bg-cafe-bruma active:bg-borde ' +
    `${APAGADO} disabled:border-transparent aria-disabled:border-transparent ` +
    'aria-disabled:hover:bg-cafe-bruma aria-disabled:active:bg-cafe-bruma',
  // Acción de texto («Modificar», «Volver», revelar más). `self-start` evita que se estire a lo
  // ancho dentro de una columna. Las acciones meta («Volver») le ponen `text-tinta-suave`.
  texto:
    'self-start min-h-11 bg-transparent px-3 text-cafe hover:bg-cafe-bruma disabled:bg-transparent aria-disabled:bg-transparent ' +
    'disabled:text-apagado aria-disabled:text-apagado disabled:hover:bg-transparent aria-disabled:hover:bg-transparent',
  peligro:
    'bg-error text-white hover:bg-[color-mix(in_srgb,var(--color-error)_92%,var(--color-tinta))] ' +
    `${APAGADO} aria-disabled:hover:bg-cafe-bruma`,
  // Campaña (F10): píldora negra, o blanca sobre foto. Llevan su propia base porque `botonClases` no fusiona
  // clases (un `rounded-control` y un `rounded-full` juntos dependerían del orden de la hoja). El color de
  // marca va solo en el hover; el checkout sigue con `principal` y `secundario`.
  campana:
    `bg-tinta text-white hover:bg-cafe active:bg-cafe-hondo ${APAGADO} ` +
    'aria-disabled:hover:bg-cafe-bruma aria-disabled:active:bg-cafe-bruma',
  'campana-claro':
    `bg-white text-tinta hover:bg-cafe-bruma active:bg-borde ${APAGADO} ` +
    'aria-disabled:hover:bg-cafe-bruma aria-disabled:active:bg-cafe-bruma',
  // Flechas de las filas que se arrastran: círculo gris sobre fondo blanco.
  'campana-gris':
    `bg-cafe-bruma text-tinta hover:bg-borde active:bg-borde-control ${APAGADO} ` +
    'aria-disabled:hover:bg-cafe-bruma aria-disabled:active:bg-cafe-bruma',
  // Variantes de migración (F4): llevan las clases del botón crudo que sustituyen y NO
  // reciben BASE (inline-flex, items-center y la etiqueta cambiarían su aspecto).
  // `fila`: disparador de acordeón de ancho completo (faq-section).
  fila: 'flex w-full cursor-pointer items-center justify-between gap-6 py-5 text-left text-lg text-foreground',
  // `chip`: píldora de filtro (hub-mapa-sedes); el color del estado marcado va por className.
  // Los chips van en píldora (design.md: radio-full).
  chip: 'rounded-full border px-4 py-2 text-sm transition-colors',
  // `libre`: sin estilo; todo llega por className (botón único con aspecto propio).
  libre: '',
} as const;

// Las variantes de migración no heredan BASE: su aspecto es el del botón crudo original.
const SIN_BASE: readonly string[] = ['fila', 'chip', 'libre'];
const CAMPANA: readonly string[] = ['campana', 'campana-claro', 'campana-gris'];

// `md` es el de la base. `icono` es un círculo de 48 × 48 también en escritorio (icono de 24).
const TAMANOS = { md: '', icono: 'size-12 rounded-full p-0' } as const;

export type VarianteBoton = keyof typeof VARIANTES;
export type TamanoBoton = keyof typeof TAMANOS;

export function botonClases({
  variante = 'principal',
  tamano = 'md',
  bloque = false,
}: { variante?: VarianteBoton; tamano?: TamanoBoton; bloque?: boolean } = {}): string {
  // `bloque`: ancho completo (barra inferior móvil).
  const base = CAMPANA.includes(variante) ? BASE_CAMPANA : SIN_BASE.includes(variante) ? '' : BASE;
  return [base, VARIANTES[variante], TAMANOS[tamano], bloque ? 'w-full' : '']
    .filter(Boolean)
    .join(' ');
}

// --- Sheet y AlertDialog (Task 3.5) ---------------------------------------------
// Ambos son un <dialog> nativo abierto con showModal(). Su movimiento (entrada,
// salida, fondo atenuado, reducir movimiento) vive en globals.css bajo las clases
// `hoja-dialogo` y `alerta-dialogo`, porque ::backdrop y @starting-style no se
// pueden escribir como utilidades. Aquí va todo lo demás.
//
// Tailwind (preflight) pone `margin: 0` a todo, lo que anula el `margin: auto` con el
// que el navegador centra un <dialog> modal: por eso la hoja lleva `m-0` explícito y
// el diálogo de alerta `m-auto`.

const HOJA_DIALOGO =
  'hoja-dialogo fixed inset-x-0 top-auto bottom-0 m-0 max-h-[85dvh] w-full max-w-none overflow-y-auto overscroll-contain ' +
  'rounded-t-sheet bg-superficie px-4 pt-3 pb-[max(16px,env(safe-area-inset-bottom))] text-foreground shadow-n2';

// Dentro de la hoja no hay tarjeta dentro de la hoja: quita borde, radio y sombra al
// contenido directo (p. ej. ResumenPedido, que fuera de la hoja sí es una tarjeta).
const HOJA_SIN_BORDE = '[&>*]:rounded-none [&>*]:border-0 [&>*]:shadow-none';

export function hojaClases({ sinBorde = false }: { sinBorde?: boolean } = {}) {
  return {
    dialogo: HOJA_DIALOGO,
    // Asa visual de 4 × 40; no es el área de arrastre.
    asa: 'mx-auto mb-3 h-1 w-10 rounded-full bg-borde-control',
    cabecera: 'mb-2 flex items-center justify-between gap-4',
    // `texto-subtitulo` va en el <h2> de sheet.tsx (la guardia `titular-sin-escala` lo busca en la etiqueta).
    titulo: 'text-foreground',
    // 48 × 48; -mr-2 alinea el icono de 24 con el margen de 16 de la hoja.
    cerrar:
      '-mr-2 inline-flex size-12 shrink-0 items-center justify-center rounded-full text-foreground transition-colors ' +
      'hover:bg-cafe-bruma focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
    cuerpo: sinBorde ? HOJA_SIN_BORDE : '',
  };
}

export function alertaClases() {
  return {
    dialogo: 'alerta-dialogo m-auto w-[min(92vw,420px)] rounded-card bg-superficie p-6 text-foreground shadow-n2',
    // `texto-subtitulo` va en el <h2> de alert-dialog.tsx (la guardia `titular-sin-escala` lo busca en la etiqueta).
    titulo: 'text-foreground',
    cuerpo: 'texto-cuerpo mt-2 text-tinta-suave',
    // Apilados a ancho completo bajo 640 px; en fila a la derecha desde ahí.
    acciones: 'mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end',
    boton: 'w-full sm:w-auto',
  };
}
