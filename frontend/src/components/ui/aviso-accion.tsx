import { Warning, WarningCircle } from '@phosphor-icons/react/ssr';
import type { AccionProblema, ClaveAccion, Problema } from '@/lib/problema-reserva';
import { Button } from './button';
import { cn } from './cn';

const TONOS = {
  aviso: { clases: 'bg-aviso-fondo text-aviso', Icono: Warning },
  error: { clases: 'bg-error-fondo text-error', Icono: WarningCircle },
} as const;

type AvisoAccionProps = {
  problema: Problema;
  /** Qué hacer con cada acción: lo decide la vista (el aviso no sabe de pasos ni de pagos). */
  alAccionar: (clave: ClaveAccion) => void;
  className?: string;
};

/**
 * El aviso con acción de `design-components.md`: qué ocurrió, qué pasó con el dinero y una
 * sola acción principal. `role="alert"` lo anuncia sin mover el foco. Si el problema
 * bloquea, la acción es `principal` (es el botón de la pantalla); si no, `secundario`.
 */
export function AvisoAccion({ problema, alAccionar, className }: AvisoAccionProps) {
  const { clases, Icono } = TONOS[problema.tono];
  const boton = (accion: AccionProblema, variante: 'principal' | 'secundario' | 'texto') => (
    <Button key={accion.clave} type="button" variante={variante} onClick={() => alAccionar(accion.clave)}
      className={variante === 'texto' ? undefined : 'w-full sm:w-auto'}>
      {accion.etiqueta}
    </Button>
  );

  return (
    <div role="alert" className={cn('flex flex-col gap-4 rounded-control p-4', clases, className)}>
      <div className="flex items-start gap-3">
        <Icono size={20} weight="fill" aria-hidden="true" className="mt-px shrink-0" />
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
    </div>
  );
}
