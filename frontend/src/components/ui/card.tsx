import type { ComponentProps } from 'react';
import { cn } from './cn';

const PADDING = {
  24: 'p-6',
  // 24 en móvil y tablet, 32 desde 1024 px (design-components.md, tarjeta de paso).
  32: 'p-6 lg:p-8',
} as const;

type CardProps = ComponentProps<'div'> & {
  padding?: keyof typeof PADDING;
};

/**
 * Contenedor plano: borde `borde`, fondo `superficie`, sin sombra. Una sola
 * variante base. Una `Card` no contiene otra `Card`: los subgrupos se separan
 * con espacio, no con un segundo borde. Servible desde servidor.
 */
export function Card({ padding = 24, className, ...props }: CardProps) {
  return <div {...props} className={cn('rounded-card border border-borde bg-superficie', PADDING[padding], className)} />;
}
