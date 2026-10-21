import { CheckCircle, Clock, Lock } from '@phosphor-icons/react';
import { cn } from '@/components/ui/cn';
import { EmpresaSello } from '@/components/ui/empresa-sello';

export type EstadoCargo = 'pendiente' | 'retenido' | 'cobrado';

/** Un cobro de un pedido con varias empresas, tal como lo ve el cliente. */
export type CargoVisible = {
  empresa: string;
  logo?: string;
  /** Lo que esa empresa opera del paquete (una línea). */
  servicio: string;
  /** Ya con su moneda. */
  monto: string;
  estado: EstadoCargo;
  /** «Pendiente», «Retenido», «Cobrado», ya traducido. */
  etiquetaEstado: string;
  /** El cobro que se está pidiendo ahora. */
  actual?: boolean;
};

// Colores de estado, nunca de actividad ni uno por empresa: el estado es lo que se lee.
const ESTADO = {
  pendiente: { Icono: Clock, color: 'text-foreground' },
  retenido: { Icono: Lock, color: 'text-info' },
  cobrado: { Icono: CheckCircle, color: 'text-exito' },
} as const;

/**
 * Un cargo de cruza-empresa: logo y nombre de quien cobra, lo que opera, el monto y su estado
 * con ícono y texto. El cargo en curso va en un bloque con el borde de control de 2 px; los demás, en gris. Lo usan el encabezado de
 * cada pago y el resumen (panel y hoja «Ver resumen»), así no pueden decir cosas distintas.
 */
export function RenglonCargo({ cargo }: { cargo: CargoVisible }) {
  const { Icono, color } = ESTADO[cargo.estado];
  return (
    <li
      aria-current={cargo.actual ? 'step' : undefined}
      className={cn(
        'flex items-center gap-3 p-4',
        cargo.actual ? 'border-2 border-tinta bg-blanco' : 'bg-cafe-bruma',
      )}
    >
      <EmpresaSello nombre={cargo.empresa} logo={cargo.logo} tamano={32} />
      <div className="min-w-0 flex-1">
        <p className="truncate texto-cuerpo font-semibold text-foreground">{cargo.empresa}</p>
        <p className="truncate texto-cuerpo">{cargo.servicio}</p>
      </div>
      <div className="flex shrink-0 flex-col items-end gap-0.5">
        <span className="texto-cuerpo font-semibold tabular-nums text-foreground">{cargo.monto}</span>
        <span className={cn('flex items-center gap-1 texto-cuerpo', color)}>
          <Icono size={16} weight="bold" aria-hidden />
          {cargo.etiquetaEstado}
        </span>
      </div>
    </li>
  );
}

export function ListaCargos({ cargos }: { cargos: CargoVisible[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {cargos.map((cargo, i) => <RenglonCargo key={`${cargo.empresa}-${i}`} cargo={cargo} />)}
    </ul>
  );
}
