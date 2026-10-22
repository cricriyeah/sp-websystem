// IVA que se suma al final del cobro. Espejo de `con_iva` en `backend/apps/payments/pricing.py`, que es quien lo
// cobra de verdad: aquí solo se estima antes de crear el pago; con el pago creado se muestra lo que dijo el servidor.
// Sin React ni red.

/** Fracción de IVA (0.16); el backend toma la suya de `IVA_TASA` y deben coincidir. */
export const TASA_IVA = Number(process.env.NEXT_PUBLIC_IVA_TASA ?? 0.16);

/** "16" para "IVA (16 %)". */
export const porcentajeIva = (tasa: number = TASA_IVA): string => String(Math.round(tasa * 10000) / 100);

/** IVA de un precio ya con descuento y sin impuesto, redondeado a centavos (mitad hacia arriba, como el servidor). */
export function ivaDe(neto: number, tasa: number = TASA_IVA): number {
  return Math.round(Math.round(neto * 100) * tasa) / 100;
}

/** El IVA y el total que se cobra (el anticipo se calcula sobre este total). */
export function conIva(neto: number, tasa: number = TASA_IVA): { iva: number; total: number } {
  const iva = ivaDe(neto, tasa);
  return { iva, total: Math.round(neto * 100) / 100 + iva };
}
