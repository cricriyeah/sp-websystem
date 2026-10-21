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
  colorDanger: '#a83226', // --error
  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif', // --font-sans
} as const;

export const RADIO_PAGO = '0px'; // --radius-campo

// Mismas medidas táctiles que los campos del sitio (48 px de alto, 16 px de texto): sin esto el iframe se ve de escritorio.
const BORDE_CONTROL = '#8b8b86'; // --color-borde-control
const FOCO = '#1b607f'; // --color-ring (azul)

export const REGLAS_PAGO = {
  '.Input': { padding: '14px 16px', fontSize: '16px', lineHeight: '20px', border: `1px solid ${BORDE_CONTROL}`, boxShadow: 'none' },
  '.Input:focus': { border: `1px solid ${FOCO}`, boxShadow: `0 0 0 1px ${FOCO}` },
  '.Input--invalid': { border: `1px solid ${TOKENS_PAGO.colorDanger}`, boxShadow: `0 0 0 1px ${TOKENS_PAGO.colorDanger}`, color: TOKENS_PAGO.colorText },
  '.Label': { fontSize: '15px', fontWeight: '600', marginBottom: '8px' },
  '.Error': { fontSize: '14px', color: TOKENS_PAGO.colorDanger },
  '.Tab': { padding: '14px 16px', minHeight: '48px' },
  '.TermsText': { fontSize: '13px' },
} as const;
