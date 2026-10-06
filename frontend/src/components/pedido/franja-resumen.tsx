'use client';

import { useState } from 'react';
import { CaretLeft } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { Despliegue } from '@/components/checkout/despliegue';

type Linea = { etiqueta: string; valor: string };

type Props = {
  dict: Dictionary;
  /** Total del pedido completo. */
  total: string;
  /** Lo que se cobra en este pago (el que dice el botón). */
  hoy: string;
  /** Lo que queda por cobrar después de este pago; null si no hay más. */
  despues: string | null;
  /** Fecha, personas, etc. */
  lineasViaje: Linea[];
  /** Un renglón por empresa/cobro. */
  cargos: Linea[];
};

/**
 * El resumen del pedido para quien paga en móvil: va ANTES del formulario de
 * tarjeta, porque se verifica antes de dar datos de pago, no después. Fija el
 * punto de referencia (total, lo de hoy, lo de después) en una línea y deja el
 * detalle a un toque. En escritorio el resumen vive en la columna derecha y
 * esta franja no se pinta.
 */
export function FranjaResumen({ dict, total, hoy, despues, lineasViaje, cargos }: Props) {
  const [abierto, setAbierto] = useState(false);
  const textos = dict.pedido;

  return (
    <section className="border border-border bg-background px-5 py-3 sm:px-6 lg:hidden">
      <dl className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm">
        <div className="flex items-baseline gap-2">
          <dt className="text-muted">{dict.checkout.total}</dt>
          <dd className="font-medium text-foreground">{total}</dd>
        </div>
        <div className="flex items-baseline gap-2">
          <dt className="text-muted">{textos.stripToday}</dt>
          <dd className="text-base font-semibold text-foreground">{hoy}</dd>
        </div>
        {despues && (
          <div className="flex items-baseline gap-2">
            <dt className="text-muted">{textos.stripLater}</dt>
            <dd className="text-foreground">{despues}</dd>
          </div>
        )}
      </dl>

      <button
        type="button"
        onClick={() => setAbierto((a) => !a)}
        aria-expanded={abierto}
        className="mt-2 inline-flex min-h-8 items-center gap-1.5 text-xs font-medium text-muted transition-colors hover:text-foreground focus-visible:underline focus-visible:underline-offset-4"
      >
        {abierto ? textos.stripHide : textos.stripShow}
        <CaretLeft size={12} weight="bold" className={`transition-transform duration-300 ${abierto ? '-rotate-90' : ''}`} />
      </button>

      <Despliegue abierto={abierto}>
        <div className="flex flex-col gap-3 pt-3 text-sm">
          {lineasViaje.length > 0 && (
            <dl className="flex flex-col gap-2 border-b border-border pb-3">
              {lineasViaje.map((linea) => (
                <div key={linea.etiqueta} className="flex items-baseline justify-between gap-4">
                  <dt className="text-muted">{linea.etiqueta}</dt>
                  <dd className="text-right text-foreground first-letter:uppercase">{linea.valor}</dd>
                </div>
              ))}
            </dl>
          )}
          <dl className="flex flex-col gap-2">
            {cargos.map((cargo) => (
              <div key={cargo.etiqueta} className="flex items-baseline justify-between gap-4">
                <dt className="text-muted">{cargo.etiqueta}</dt>
                <dd className="text-foreground">{cargo.valor}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Despliegue>
    </section>
  );
}
