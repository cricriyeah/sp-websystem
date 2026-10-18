import type { ComponentProps } from 'react';
import { Bed, Buildings, Mountains, Package, Van, Waves } from '@phosphor-icons/react/ssr';
import { cn } from './cn';

/**
 * Qué tipo de experiencia es: mar (azul), ciudad (coral), outside o montaña
 * (verde). Fondo `*-claro` y texto del tono oscuro de su familia. `neutro` es
 * para lo que no tiene familia de actividad (hospedaje, traslados, paquetes).
 *
 * NO comunica estado: éxito, error o aviso son `AvisoEstado`. Los dos no se
 * mezclan porque azul y verde comparten familia con info y éxito, y lo único
 * que los separa es el icono y el texto.
 */
const TONOS = {
  mar: 'bg-azul-claro text-azul',
  // El coral puro no alcanza contraste como texto: se usa coral-texto.
  ciudad: 'bg-coral-claro text-coral-texto',
  outside: 'bg-verde-claro text-verde',
  neutro: 'bg-cafe-bruma text-tinta-suave',
} as const;

const ICONO_NEUTRO = { hospedaje: Bed, traslado: Van, paquete: Package } as const;

export type TipoActividad = keyof typeof TONOS;
export type IconoNeutro = keyof typeof ICONO_NEUTRO;

type ChipActividadProps = ComponentProps<'span'> & {
  tipo: TipoActividad;
  /** Solo con `tipo="neutro"`; sin él, `paquete`. */
  icono?: IconoNeutro;
};

export function ChipActividad({ tipo, icono = 'paquete', className, children, ...props }: ChipActividadProps) {
  // Siempre lleva icono: el color solo no basta para quien no distingue tonos.
  const Icono =
    tipo === 'mar' ? Waves : tipo === 'ciudad' ? Buildings : tipo === 'outside' ? Mountains : ICONO_NEUTRO[icono];

  return (
    <span
      {...props}
      className={cn('inline-flex h-7 items-center gap-1.5 rounded-full px-3 texto-pequeno font-semibold', TONOS[tipo], className)}
    >
      <Icono size={16} weight="bold" aria-hidden="true" className="shrink-0" />
      {children}
    </span>
  );
}
