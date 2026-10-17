// Módulo puro, SIN imports: el runner de pruebas compila solo src/ y Node no resuelve
// paquetes ahí. Las primitivas (button.tsx) combinan estas clases con `cn`, que fusiona
// los conflictos en orden de cadena (los TAMANOS van después de las VARIANTES a propósito).

const BASE = 'inline-flex items-center font-medium';

// Copiado de BotonPaso (checkout/boton-paso.tsx): transition-transform, active:scale-[0.98]
// y disabled:opacity-60. Único cambio: rounded-full pasa a rounded-control (mismo 9999px).
const PULSABLE = 'justify-center gap-2 rounded-control px-6 py-2.5 text-sm transition-transform active:scale-[0.98] disabled:opacity-60';

// Copiado de AccionTexto (checkout/accion-terciaria.tsx): min-h-10, gap-1.5, self-start,
// text-xs, transition-colors, hover y subrayado solo al enfocar con teclado.
const TEXTO =
  'min-h-10 gap-1.5 self-start text-xs transition-colors hover:text-foreground focus-visible:underline focus-visible:underline-offset-4 disabled:opacity-60';

const VARIANTES = {
  principal: `${PULSABLE} bg-action text-action-foreground`,
  secundario: `${PULSABLE} border border-border-strong bg-background text-foreground hover:bg-cafe-bruma`,
  texto: `${TEXTO} text-muted`,
  acento: `${TEXTO} text-accent`,
  peligro: `${PULSABLE} border border-error bg-error-fondo text-error`,
  // Variantes de migración (F4): llevan las clases del botón crudo que sustituyen y NO
  // reciben BASE (inline-flex, items-center y font-medium cambiarían su aspecto).
  // `fila`: disparador de acordeón de ancho completo (faq-section).
  fila: 'flex w-full cursor-pointer items-center justify-between gap-6 py-5 text-left text-lg text-foreground',
  // `chip`: píldora de filtro (hub-mapa-sedes); el color del estado marcado va por className.
  // rounded-full pasa a rounded-control (mismo 9999px).
  chip: 'rounded-control border px-4 py-2 text-sm transition-colors',
  // `libre`: sin estilo; todo llega por className (botón único con aspecto propio).
  libre: '',
} as const;

// Las variantes de migración no heredan BASE: su aspecto es el del botón crudo original.
const SIN_BASE: readonly string[] = ['fila', 'chip', 'libre'];

const TAMANOS = { md: '', sm: 'px-4 py-1.5 text-xs', icono: 'size-10 p-0' } as const;

export type VarianteBoton = keyof typeof VARIANTES;
export type TamanoBoton = keyof typeof TAMANOS;

export function botonClases({
  variante = 'principal',
  tamano = 'md',
}: { variante?: VarianteBoton; tamano?: TamanoBoton } = {}): string {
  return [SIN_BASE.includes(variante) ? '' : BASE, VARIANTES[variante], TAMANOS[tamano]].filter(Boolean).join(' ');
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
    // El h2 trae la fuente y el espaciado de titular de la base: aquí es un rótulo.
    titulo: 'texto-subtitulo font-sans tracking-normal text-foreground',
    // 48 × 48; -mr-2 alinea el icono de 24 con el margen de 16 de la hoja.
    cerrar:
      '-mr-2 inline-flex size-12 shrink-0 items-center justify-center rounded-control text-foreground transition-colors ' +
      'hover:bg-cafe-bruma focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
    cuerpo: sinBorde ? HOJA_SIN_BORDE : '',
  };
}

export function alertaClases() {
  return {
    dialogo: 'alerta-dialogo m-auto w-[min(92vw,420px)] rounded-card bg-superficie p-6 text-foreground shadow-n2',
    titulo: 'texto-subtitulo font-sans tracking-normal text-foreground',
    cuerpo: 'texto-cuerpo mt-2 text-tinta-suave',
    // Apilados a ancho completo bajo 640 px; en fila a la derecha desde ahí.
    acciones: 'mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end',
    boton: 'w-full sm:w-auto',
  };
}
