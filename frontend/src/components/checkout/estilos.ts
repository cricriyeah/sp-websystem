/**
 * Contenedor de un control dentro de una tarjeta del checkout (campo con
 * etiqueta interna, contador, selector). Un solo contenedor para todos: cuatro
 * cajas distintas en la misma tarjeta se leen como cuatro tareas distintas.
 */
export const CAJA_CAMPO = 'rounded-lg border border-border bg-background';

/** El mismo contenedor cuando el campo trae un error. */
export const CAJA_CAMPO_ERROR = 'rounded-lg border border-red-400 bg-background';

/** Enlace secundario bajo un control ("Ver mes completo", "O escribe una dirección…"). */
export const ENLACE_SECUNDARIO =
  'self-start text-xs font-medium text-accent underline underline-offset-4 transition-colors hover:text-foreground';
