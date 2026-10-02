import type { Moneda } from './api';

type DecimalApi = string | number | null | undefined;

function fraccion(valor: DecimalApi): { numerador: bigint; escala: bigint } | null {
  if (valor === null || valor === undefined) return null;
  const texto = String(valor).trim();
  if (!/^\d+(?:\.\d+)?$/.test(texto)) return null;
  const [entero, decimales = ''] = texto.split('.');
  return {
    numerador: BigInt(entero + decimales),
    escala: BigInt(10) ** BigInt(decimales.length),
  };
}

/** Igual que payments.moneda.convertir: cada precio MXN se redondea hacia arriba al dólar. */
export function aMoneda(mxn: DecimalApi, moneda: Moneda, tipoCambio: DecimalApi): number | null {
  const monto = fraccion(mxn);
  if (!monto) return null;
  if (moneda === 'MXN') return Number(monto.numerador) / Number(monto.escala);

  const cambio = fraccion(tipoCambio);
  if (!cambio || cambio.numerador <= BigInt(0)) {
    throw new Error('El tipo de cambio USD debe ser positivo.');
  }
  const numerador = monto.numerador * cambio.escala;
  const divisor = monto.escala * cambio.numerador;
  return Number((numerador + divisor - BigInt(1)) / divisor);
}
