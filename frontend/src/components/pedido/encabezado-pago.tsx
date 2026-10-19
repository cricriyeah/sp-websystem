import type { Dictionary } from '@/app/[lang]/dictionaries';
import { ListaCargos, type CargoVisible } from '@/components/checkout/pago/renglon-cargo';
import { PorQueVariosPagos } from './por-que-varios-pagos';

type Props = {
  dict: Dictionary;
  cargos: CargoVisible[];
  indice: number;
  /** Total del pedido completo, ya con moneda. */
  total?: string;
};

/**
 * El plan de pagos de un pedido con varias empresas, a la vista ANTES de pagar cada uno: a quién
 * va este cobro, por qué cada empresa cobra aparte, y un renglón por cobro con su estado. Sin
 * esto el segundo formulario de tarjeta se lee como un error ("¿otra vez?"). En móvil la primera
 * línea de la pantalla ya dice «Pago 1 de 2 · empresa · $X»: el titular se omite ahí.
 */
export function EncabezadoPago({ dict, cargos, indice, total }: Props) {
  if (cargos.length <= 1) return null;
  const textos = dict.pedido;
  const empresa = cargos[indice]?.empresa ?? '';
  const esUltimo = indice === cargos.length - 1;

  return (
    <div className="flex flex-col gap-3 border-b border-border pb-5">
      <div className="flex flex-col gap-1">
        <p className="texto-etiqueta text-foreground max-sm:hidden">
          {textos.pagoA.replace('{n}', String(indice + 1)).replace('{total}', String(cargos.length)).replace('{empresa}', empresa)}
        </p>
        <p className="texto-pequeno text-apagado">{textos.pagoAAyuda.replace('{empresa}', empresa)}</p>
      </div>
      <ListaCargos cargos={cargos} />
      {total && (
        <p className="texto-pequeno text-apagado tabular-nums">
          {textos.stripTotal.replace('{total}', total).replace('{n}', String(cargos.length))}
        </p>
      )}
      {esUltimo && <p className="texto-pequeno text-apagado">{textos.payStepHintLast}</p>}
      <PorQueVariosPagos dict={dict} />
    </div>
  );
}
