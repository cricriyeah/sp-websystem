// Stripe Elements pinta en un iframe y su API de apariencia no acepta `var()`:
// pide hex y px concretos. Esta es la única fuente de esos valores; la prueba
// tests/tokens-pago.test.cjs los compara contra los tokens de globals.css, así
// que una marca que cambie un token sin cambiar este archivo falla la prueba.
// Sin imports: el runner de pruebas compila solo `src/` y no resuelve el alias `@/`.

export const TOKENS_PAGO = {
  colorPrimary: '#281ab5', // --accent
  colorText: '#16171c', // --foreground
  colorTextSecondary: '#55565f', // --muted
  colorBackground: '#ffffff', // --superficie (el formulario vive en una tarjeta)
  colorDanger: '#c22118', // --error
} as const;

export const RADIO_PAGO = '8px'; // --radius-campo
