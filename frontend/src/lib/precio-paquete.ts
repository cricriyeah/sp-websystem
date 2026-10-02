import type { Moneda, PaqueteCatalogo } from './api';
import { aMoneda } from './moneda';

/** Espejo de Paquete.precio_total_en: convierte base y extra por separado. */
export function calcularBasePaquete(
  paquete: Pick<PaqueteCatalogo,
    'precio_ancla' | 'tipo_cambio_usd' | 'estrategia_precio' |
    'personas_precio_base' | 'precio_persona_extra'>,
  moneda: Moneda,
  personas: number,
): number | null {
  const base = aMoneda(paquete.precio_ancla, moneda, paquete.tipo_cambio_usd);
  if (base === null) return null;
  const extra = aMoneda(paquete.precio_persona_extra, moneda, paquete.tipo_cambio_usd);
  if (extra === null) return null;
  const n = Math.max(1, Math.trunc(personas));
  const baseCentavos = Math.round(base * 100);
  const extraCentavos = Math.round(extra * 100);
  if (paquete.estrategia_precio === 'por_persona') return baseCentavos * n / 100;
  if (paquete.estrategia_precio === 'por_grupo') {
    return (baseCentavos + Math.max(0, n - paquete.personas_precio_base) * extraCentavos) / 100;
  }
  return null;
}
