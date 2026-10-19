import type { CSSProperties } from 'react';
import type { EstadoCelda } from '@/lib/calendario-mes';
import { cn } from '../cn';

/** Rayado del día sin cupo: con el color del borde de control, sin hex en el código. */
const RAYADO: CSSProperties = {
  backgroundImage: 'repeating-linear-gradient(135deg, transparent 0 4px, var(--color-borde-control) 4px 5px)',
};

type Props = {
  numero: number | string;
  estado: EstadoCelda;
  /** 44 en el calendario (el círculo es el área táctil); 24 en la leyenda. */
  tamano?: 44 | 24;
  /** Leyenda: un anillo de borde para que el círculo «disponible» se vea (color y forma). */
  contorno?: boolean;
  className?: string;
};

/**
 * Un día dibujado: la banda del rango o de la vista previa detrás, y el círculo con el número.
 * La banda se pinta continua de celda a celda (no círculo por círculo) y nace o muere en el
 * centro de sus extremos. La usan el calendario y la leyenda, así no pueden verse distinto.
 */
export function CeldaDia({ numero, estado, tamano = 44, contorno = false, className }: Props) {
  const { base, marca, hoy, inicioBanda, finBanda } = estado;
  const lleno = marca === 'seleccion' || marca === 'extremo';
  const previa = marca === 'vista_previa';
  // Un rango de un solo día es solo su círculo: sin banda.
  const conBanda = (marca === 'rango' || marca === 'extremo' || previa) && !(inicioBanda && finBanda);

  return (
    <span className={cn('relative flex items-center justify-center', tamano === 44 ? 'h-11 w-full' : 'size-6', className)}>
      {conBanda && (
        <span
          aria-hidden
          className={cn(
            'absolute inset-y-0.5',
            previa ? 'border-y border-dashed border-cafe bg-cafe-bruma' : 'bg-cafe-claro',
            inicioBanda ? 'left-1/2' : 'left-0',
            finBanda ? 'right-1/2' : 'right-0',
          )}
        />
      )}
      <span
        aria-hidden
        style={base === 'sin_cupo' && !lleno ? RAYADO : undefined}
        className={cn(
          'relative flex shrink-0 items-center justify-center rounded-full tabular-nums',
          tamano === 44 ? 'size-11 texto-cuerpo font-medium' : 'size-6 texto-pie',
          lleno && 'bg-cafe text-blanco',
          !lleno && marca === 'rango' && 'text-cafe-profundo',
          !lleno && marca !== 'rango' && (base === 'disponible' ? 'text-foreground' : 'text-apagado'),
          base === 'sin_cupo' && !lleno && 'line-through',
          // Vista previa de un solo día: no hay banda, el círculo lleva su borde discontinuo.
          previa && inicioBanda && finBanda && 'border border-dashed border-cafe bg-cafe-bruma',
          hoy && !lleno && 'ring-2 ring-inset ring-azul',
          contorno && !hoy && 'ring-1 ring-inset ring-borde',
          // En el calendario la celda es el botón (`group`): el círculo se tiñe al pasar encima.
          tamano === 44 && base === 'disponible' && marca === 'ninguna' && 'group-hover:bg-cafe-bruma',
        )}
      >
        {numero}
      </span>
    </span>
  );
}
