import type { Dictionary } from '@/app/[lang]/dictionaries';

type Props = {
  dict: Dictionary;
  cargos: { etiqueta: string; monto: string }[];
  total: string;
};

export function AvisoCargos({ dict, cargos, total }: Props) {
  if (cargos.length <= 1) return null;

  return (
    <div className="text-xs leading-relaxed text-muted">
      <p className="font-medium text-foreground">
        {dict.pedido.chargesNotice.replace('{n}', String(cargos.length))}
      </p>
      <ul className="mt-2 flex flex-col gap-1">
        {cargos.map((cargo) => (
          <li key={cargo.etiqueta} className="flex justify-between gap-4">
            <span>{cargo.etiqueta}</span>
            <span className="shrink-0 text-foreground">{cargo.monto}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2">{dict.pedido.chargesSum.replace('{total}', total)}</p>
    </div>
  );
}
