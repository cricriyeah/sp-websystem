// La etiqueta del botón único de cada paso. Regla: un monto solo aparece cuando el
// servidor lo confirmó (o la vista previa está probada como exacta); antes dice
// «Continuar a pago». Sin React ni red.
import type { PasoId } from './pasos-checkout';

export type TextosEtiquetaBoton = {
  /** «Continuar a pago»: la etiqueta sin cifra. */
  continuarAPago: string;
  /** «Pagar {amount}»: un solo cobro. */
  pagarUno: string;
  /** «Pagar {amount} a {empresa}»: un cobro de varios. */
  pagarA: string;
  /** «Pago {n} de {total}». */
  pagoNDeTotal: string;
};

export type EntradaEtiqueta = {
  paso: PasoId;
  /** Lo que el servidor confirmó que se cobra ahora, ya con su moneda; null mientras sea una estimación. */
  montoConfirmado: string | null;
  empresa?: string;
  /** Posición del cobro entre varios; el rótulo «Pago 1 de 2» lo arma `rotuloDePago` y va en la primera línea de la pantalla. */
  cargos?: { n: number; total: number };
  textos: TextosEtiquetaBoton;
};

export function rotuloDePago(n: number, total: number, textos: Pick<TextosEtiquetaBoton, 'pagoNDeTotal'>): string {
  return textos.pagoNDeTotal.replace('{n}', String(n)).replace('{total}', String(total));
}

export function etiquetaDeBoton({ paso, montoConfirmado, empresa, textos }: EntradaEtiqueta): string {
  const monto = montoConfirmado?.trim();
  // Solo el paso de pago cobra: Viaje y Datos nunca llevan cifra en el botón.
  if (paso !== 'pago' || !monto) return textos.continuarAPago;
  if (empresa) return textos.pagarA.replace('{amount}', monto).replace('{empresa}', empresa);
  return textos.pagarUno.replace('{amount}', monto);
}
