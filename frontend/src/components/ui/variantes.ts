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
} as const;

const TAMANOS = { md: '', sm: 'px-4 py-1.5 text-xs', icono: 'size-10 p-0' } as const;

export type VarianteBoton = keyof typeof VARIANTES;
export type TamanoBoton = keyof typeof TAMANOS;

export function botonClases({
  variante = 'principal',
  tamano = 'md',
}: { variante?: VarianteBoton; tamano?: TamanoBoton } = {}): string {
  return [BASE, VARIANTES[variante], TAMANOS[tamano]].filter(Boolean).join(' ');
}
