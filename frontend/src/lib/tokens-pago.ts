// Stripe Elements pinta en un iframe y su API de apariencia no acepta `var()`:
// pide hex y px concretos. Esta es la única fuente de esos valores; la prueba
// tests/tokens-pago.test.cjs los compara contra los tokens de globals.css, así
// que una marca que cambie un token sin cambiar este archivo falla la prueba.
// Sin imports: el runner de pruebas compila solo `src/` y no resuelve el alias `@/`.

export const TOKENS_PAGO = {
  colorPrimary: '#7c3b02', // --accent (cafe)
  colorText: '#1f1a14', // --foreground (tinta)
  colorTextSecondary: '#6b5d4d', // --muted (apagado)
  colorBackground: '#ffffff', // --superficie (el formulario vive en una tarjeta)
  colorDanger: '#b3261e', // --error
  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif', // --font-sans
} as const;

export const RADIO_PAGO = '0px'; // --radius-campo
