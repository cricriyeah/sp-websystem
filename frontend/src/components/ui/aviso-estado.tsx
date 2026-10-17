import type { ComponentProps } from 'react';
import { CheckCircle, Info, Warning, WarningCircle } from '@phosphor-icons/react/ssr';
import { cn } from './cn';

/**
 * Un estado del sistema (éxito, error, aviso, información): siempre icono y
 * texto, nunca solo color. No es un chip de actividad (`ChipActividad`).
 */
const TONOS = {
  exito: { clases: 'bg-exito-fondo text-exito', Icono: CheckCircle },
  error: { clases: 'bg-error-fondo text-error', Icono: WarningCircle },
  aviso: { clases: 'bg-aviso-fondo text-aviso', Icono: Warning },
  info: { clases: 'bg-info-fondo text-info', Icono: Info },
} as const;

export type TonoAviso = keyof typeof TONOS;

type AvisoEstadoProps = ComponentProps<'div'> & {
  tono: TonoAviso;
};

export function AvisoEstado({ tono, className, children, ...props }: AvisoEstadoProps) {
  const { clases, Icono } = TONOS[tono];

  return (
    <div
      // El error interrumpe (alert); el resto se anuncia sin cortar lo que se esté leyendo (status).
      role={tono === 'error' ? 'alert' : 'status'}
      {...props}
      className={cn('flex items-start gap-2 rounded-campo px-4 py-3 texto-pequeno', clases, className)}
    >
      <Icono size={20} weight="fill" aria-hidden="true" className="mt-px shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
