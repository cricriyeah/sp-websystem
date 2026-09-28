import { Check } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type Paso = {
  etiqueta: string;
  monto: string;
  estado: 'hecho' | 'actual' | 'pendiente';
};

type Props = {
  dict: Dictionary;
  pasos: Paso[];
  indice: number;
};

export function EncabezadoPago({ dict, pasos, indice }: Props) {
  if (pasos.length <= 1) return null;

  const actual = pasos.find((paso) => paso.estado === 'actual') ?? pasos[indice];
  const plantilla = indice === pasos.length - 1 ? dict.pedido.payStepLast : dict.pedido.payStep;

  return (
    <div className="border-b border-border pb-5">
      <ol className="flex flex-col gap-2">
        {pasos.filter((paso) => paso.estado === 'hecho').map((paso) => (
          <li key={paso.etiqueta} className="flex items-center gap-2 text-xs text-muted">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-exito-fondo text-exito">
              <Check size={12} weight="bold" />
            </span>
            <span>{paso.etiqueta} · {paso.monto} — {dict.pedido.authorized}</span>
          </li>
        ))}
        <li className="text-sm font-medium text-foreground">
          {plantilla.replace('{n}', String(indice + 1)).replace('{total}', String(pasos.length))}
          {actual && <span className="ml-2 text-muted">{actual.etiqueta} · {actual.monto}</span>}
        </li>
      </ol>
      <div className="mt-3 h-1 overflow-hidden rounded-full bg-border" role="progressbar"
        aria-valuemin={0} aria-valuemax={pasos.length} aria-valuenow={indice + 1}>
        <div className="h-full rounded-full bg-accent transition-[width]"
          style={{ width: `${((indice + 1) / pasos.length) * 100}%` }} />
      </div>
    </div>
  );
}
