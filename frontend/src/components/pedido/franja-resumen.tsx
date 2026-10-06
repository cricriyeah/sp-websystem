import { Check } from '@phosphor-icons/react';
import type { Dictionary } from '@/app/[lang]/dictionaries';

type Pago = {
  etiqueta: string;
  monto: string;
  estado: 'hecho' | 'actual' | 'pendiente';
};

type Props = {
  dict: Dictionary;
  /** Total del pedido completo. */
  total: string;
  /** Los cobros en el orden en que se hacen. */
  pagos: Pago[];
  /** Con un solo cobro y anticipo: lo que queda por pagar después. */
  saldo?: string | null;
};

/**
 * El resumen de la reserva para quien paga en móvil (el mismo que la columna
 * derecha de escritorio, que aquí no se repite), reducido al plan de pagos: va ANTES del formulario de
 * tarjeta, porque se verifica antes de dar datos de pago, no después. Una línea
 * por cobro, en el orden real: los cobros de un pedido cruza-empresa se hacen
 * uno tras otro en la misma sesión, así que el siguiente es "enseguida", no
 * "después". Fecha, personas y demás ya están en los renglones de arriba: aquí
 * no se repiten. En escritorio el resumen vive en la columna derecha.
 */
export function FranjaResumen({ dict, total, pagos, saldo = null }: Props) {
  const textos = dict.pedido;
  const varios = pagos.length > 1;
  // Un solo cobro sin saldo: el total ya está en el stepper y en el botón.
  if (!varios && !saldo) return null;

  const actual = pagos.find((p) => p.estado === 'actual');

  return (
    <section className="border border-border bg-background p-5 sm:p-6 lg:hidden">
      <h2 className="font-sans text-sm font-medium tracking-tight text-foreground">
        {dict.checkout.orderSummaryHeadline}
      </h2>
      <p className="mt-3 text-sm text-muted">
        {varios
          ? textos.stripTotal.replace('{total}', total).replace('{n}', String(pagos.length))
          : `${dict.checkout.total} ${total}`}
      </p>
      <ol className="mt-3 flex flex-col gap-2 border-t border-border pt-3 text-sm">
        {varios ? pagos.map((pago, i) => (
          <li
            key={`${pago.etiqueta}-${i}`}
            className={`flex items-baseline justify-between gap-3 ${
              pago.estado === 'actual' ? 'font-medium text-foreground' : 'text-muted'
            }`}
          >
            <span className="flex min-w-0 items-baseline gap-2">
              {pago.estado === 'hecho'
                ? <Check size={12} weight="bold" className="shrink-0 self-center text-exito" />
                : <span className="shrink-0">{i + 1}</span>}
              <span className="truncate">{pago.etiqueta}</span>
              {pago.estado === 'actual' && <span className="shrink-0 text-xs font-normal text-accent">{textos.stripNow}</span>}
              {pago.estado === 'pendiente' && <span className="shrink-0 text-xs">{textos.stripNext}</span>}
              {pago.estado === 'hecho' && <span className="shrink-0 text-xs">{textos.authorized}</span>}
            </span>
            <span className="shrink-0">{pago.monto}</span>
          </li>
        )) : (
          <>
            <li className="flex items-baseline justify-between gap-3 font-medium text-foreground">
              <span>{textos.stripDeposit}</span><span>{actual?.monto}</span>
            </li>
            <li className="flex items-baseline justify-between gap-3 text-muted">
              <span>{textos.stripBalance}</span><span>{saldo}</span>
            </li>
          </>
        )}
      </ol>
    </section>
  );
}
