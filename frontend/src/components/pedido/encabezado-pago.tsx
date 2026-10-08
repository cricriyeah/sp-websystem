import { Check } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';
import { PorQueVariosPagos } from './por-que-varios-pagos';

type Paso = {
  etiqueta: string;
  monto: string;
  estado: 'hecho' | 'actual' | 'pendiente';
};

type Props = {
  dict: Dictionary;
  pasos: Paso[];
  indice: number;
  /** Total del pedido completo, ya con moneda. */
  total?: string;
};

/**
 * El plan de pagos de un pedido con varias empresas, a la vista ANTES de pagar el
 * primero: un titular que dice cuántos pagos son y por qué, y una ficha por cobro
 * (empresa y monto) con su estado. Cada cobro es un evento aparte, así que cada
 * uno es su propia pieza y no un tramo de una barra de progreso. Sin esto el
 * segundo formulario de tarjeta se lee como un error ("¿otra vez?").
 */
export function EncabezadoPago({ dict, pasos, indice, total }: Props) {
  if (pasos.length <= 1) return null;
  const textos = dict.pedido;
  const esUltimo = indice === pasos.length - 1;

  return (
    <div className="border-b border-border pb-5">
      <p className="text-base font-medium text-foreground">
        {textos.planTitle.replace('{n}', String(pasos.length))}
      </p>
      {total && (
        <p className="mt-1 text-sm text-muted">
          {textos.stripTotal.replace('{total}', total).replace('{n}', String(pasos.length))}
        </p>
      )}

      {/* Mismo lenguaje que el stepper de arriba (círculos unidos por una línea, sin cajas):
          un progreso que se lee y no se toca. Una caja con borde se leería como una opción para elegir. */}
      <ol className="mt-5 flex items-start">
        {pasos.map((paso, i) => {
          const actual = paso.estado === 'actual';
          const hecho = paso.estado === 'hecho';
          const ultimo = i === pasos.length - 1;
          return (
            <li
              key={`${paso.etiqueta}-${i}`}
              aria-current={actual ? 'step' : undefined}
              className={`flex min-w-0 flex-col gap-2 ${ultimo ? 'flex-none' : 'flex-1'}`}
            >
              <div className="flex items-center">
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
                    hecho
                      ? 'bg-accent text-accent-foreground'
                      : actual
                        ? 'border-2 border-accent text-accent'
                        : 'border border-border-strong text-muted'
                  }`}
                >
                  {hecho ? <Check size={12} weight="bold" aria-hidden /> : i + 1}
                </span>
                {!ultimo && (
                  <span aria-hidden className={`mx-3 h-px flex-1 ${hecho ? 'bg-accent' : 'bg-border'}`} />
                )}
              </div>
              <div className={`flex flex-col gap-0.5 ${ultimo ? '' : 'pr-3'}`}>
                <span className={`text-xs font-medium ${actual ? 'text-accent' : 'text-muted'}`}>
                  {actual ? textos.planNow : hecho ? textos.planDone : textos.planNext}
                </span>
                <span className={`text-sm ${actual ? 'font-medium text-foreground' : 'text-muted'}`}>{paso.etiqueta}</span>
                <span className={`text-sm ${actual ? 'font-semibold text-foreground' : 'text-muted'}`}>{paso.monto}</span>
              </div>
            </li>
          );
        })}
      </ol>

      {esUltimo && <p className="mt-3 text-sm text-muted">{textos.payStepHintLast}</p>}
      <div className="mt-1">
        <PorQueVariosPagos dict={dict} />
      </div>
    </div>
  );
}
