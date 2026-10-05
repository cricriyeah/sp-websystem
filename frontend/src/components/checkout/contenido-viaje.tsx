import type { ReactNode } from 'react';

type Props = {
  /** Calendario o selector de fecha de inicio. */
  fecha: ReactNode;
  /** Selector de hora (solo si el servicio o paquete pide hora). */
  hora?: ReactNode;
  /** Selector de personas del viaje (en paquetes sin precio por persona viven en cada grupo). */
  personas?: ReactNode;
  /** Fecha de salida (hospedaje). */
  salida?: ReactNode;
  /** Notas de apoyo en texto pequeño: precio por persona, noches, personas extra. */
  nota?: ReactNode;
};

const CAJA = 'border border-border bg-surface';

/**
 * Orden fijo del paso "viaje" para todos los checkouts: cuándo (fecha) →
 * a qué hora y cuántos → hasta cuándo → aclaraciones. Cada hijo es un bloque
 * del cuerpo de la tarjeta; el espacio lo pone la tarjeta.
 */
export function ContenidoViaje({ fecha, hora, personas, salida, nota }: Props) {
  const campos = [hora, personas].filter(Boolean).length;
  return (
    <>
      <div>{fecha}</div>
      {campos > 0 && (
        <div className={`grid gap-3 ${campos === 2 ? 'sm:grid-cols-2' : ''}`}>
          {hora && <div className={CAJA}>{hora}</div>}
          {personas && <div className={CAJA}>{personas}</div>}
        </div>
      )}
      {salida && <div>{salida}</div>}
      {nota && <div className="flex flex-col gap-1 text-xs text-muted">{nota}</div>}
    </>
  );
}
