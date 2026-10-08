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
 * El resumen del anticipo para quien paga en móvil: lo que se paga ahora y lo que
 * queda. Va ANTES del formulario de tarjeta, porque se verifica antes de dar datos
 * de pago. Solo un cobro con saldo: cuando son varios cobros (cruza-empresa) el plan
 * completo lo pinta `EncabezadoPago`, dentro del pago y en todos los tamaños. En
 * escritorio el resumen vive en la columna derecha.
 */
export function FranjaResumen({ dict, total, pagos, saldo = null }: Props) {
  const textos = dict.pedido;
  if (pagos.length > 1 || !saldo) return null;

  const actual = pagos.find((p) => p.estado === 'actual');

  return (
    <section className="border border-border bg-background p-5 sm:p-6 lg:hidden">
      <h2 className="font-sans text-sm font-medium tracking-tight text-foreground">
        {dict.checkout.orderSummaryHeadline}
      </h2>
      <p className="mt-3 text-sm text-muted">{`${dict.checkout.total} ${total}`}</p>
      <ol className="mt-3 flex flex-col gap-2 border-t border-border pt-3 text-sm">
        <li className="flex items-baseline justify-between gap-3 font-medium text-foreground">
          <span>{textos.stripDeposit}</span><span>{actual?.monto}</span>
        </li>
        <li className="flex items-baseline justify-between gap-3 text-muted">
          <span>{textos.stripBalance}</span><span>{saldo}</span>
        </li>
      </ol>
    </section>
  );
}
