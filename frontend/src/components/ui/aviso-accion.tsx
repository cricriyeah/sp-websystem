import type { ReactNode } from 'react';
import { Warning } from '@phosphor-icons/react/ssr';
import type { AccionProblema, ClaveAccion, Problema } from '@/lib/problema-reserva';
import { Button } from './button';
import { cn } from './cn';

type AvisoAccionProps = {
  problema: Problema;
  /** Qué hacer con cada acción: lo decide la vista (el aviso no sabe de pasos ni de pagos). */
  alAccionar: (clave: ClaveAccion) => void;
  /** Rótulo del bloque donde se dice qué pasó con el dinero (solo un error con cuerpo, p. ej. «Tu dinero»). */
  etiquetaDinero?: string;
  /** Lo que va al final dentro del aviso (la ayuda por WhatsApp), ya con el estilo del fondo. */
  pie?: ReactNode;
  className?: string;
};

/**
 * El aviso con acción de `design-components.md`: qué ocurrió, qué pasó con el dinero y una
 * sola acción principal. `role="alert"` lo anuncia sin mover el foco. Si el problema
 * bloquea, la acción es `principal` (es el botón de la pantalla); si no, `secundario`.
 *
 * Un error (tarjeta rechazada, sin conexión) se pinta como el campo de color de la página de
 * confirmación: bloque de coral pleno, titular en la letra de titulares y lo que se conserva en
 * un bloque tinta, como «Pagaste hoy». Un aviso (sin cupo, dato por corregir) es la caja suave.
 */
export function AvisoAccion({ problema, alAccionar, etiquetaDinero, pie, className }: AvisoAccionProps) {
  if (problema.tono === 'error') {
    const conserva = [problema.queSeConserva, ...problema.lineasDinero].filter(Boolean);
    return (
      <div role="alert" className={cn('flex flex-col gap-5 bg-coral-hondo p-5 text-hero-ink sm:p-6', className)}>
        <p className="texto-paso">{problema.queOcurrio}</p>
        {conserva.length > 0 && (
          <div className="bg-tinta px-4 py-3.5">
            {etiquetaDinero && <p className="texto-pequeno font-semibold text-hero-ink-soft">{etiquetaDinero}</p>}
            {conserva.map((linea) => (
              <p key={linea} className={cn('texto-mono-mayus text-xl font-bold leading-tight', etiquetaDinero && 'mt-1')}>{linea}</p>
            ))}
          </div>
        )}
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-5">
          <Button type="button" variante="campana-claro" onClick={() => alAccionar(problema.accionPrincipal.clave)}
            className="w-full sm:w-auto">
            {problema.accionPrincipal.etiqueta}
          </Button>
          {problema.accionSecundaria && (
            <Button type="button" variante="libre" onClick={() => alAccionar(problema.accionSecundaria!.clave)}
              className="min-h-11 px-0 texto-pequeno font-semibold underline underline-offset-4">
              {problema.accionSecundaria.etiqueta}
            </Button>
          )}
        </div>
        {pie}
      </div>
    );
  }

  const boton = (accion: AccionProblema, variante: 'principal' | 'secundario' | 'texto') => (
    <Button key={accion.clave} type="button" variante={variante} onClick={() => alAccionar(accion.clave)}
      className={variante === 'texto' ? undefined : 'w-full sm:w-auto'}>
      {accion.etiqueta}
    </Button>
  );

  return (
    <div role="alert" className={cn('flex flex-col gap-4 rounded-control bg-aviso-fondo p-4 text-aviso', className)}>
      <div className="flex items-start gap-3">
        <Warning size={20} weight="fill" aria-hidden="true" className="mt-px shrink-0" />
        <div className="min-w-0">
          <p className="texto-pequeno font-semibold">{problema.queOcurrio}</p>
          {problema.queSeConserva && <p className="mt-1 texto-pequeno font-normal text-tinta">{problema.queSeConserva}</p>}
          {problema.lineasDinero.map((linea) => (
            <p key={linea} className="mt-1 texto-pequeno font-normal text-tinta">{linea}</p>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {boton(problema.accionPrincipal, problema.bloquea ? 'principal' : 'secundario')}
        {problema.accionSecundaria && boton(problema.accionSecundaria, 'texto')}
      </div>
      {pie}
    </div>
  );
}
