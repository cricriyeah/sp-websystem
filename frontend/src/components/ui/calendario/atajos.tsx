import { X } from '@phosphor-icons/react';
import { atajos as atajosDe } from '@/lib/calendario-mes';
import { Button } from '../button';
import type { TextosCalendario } from './textos';

type Props = {
  hoy: string;
  minDate: string;
  haySeleccion: boolean;
  onBorrar: () => void;
  onElegir: (iso: string) => void;
  textos: TextosCalendario;
};

// `px-2.5` y 6 px entre ellos: los tres caben en una fila en un iPhone 11 aun con «Borrar fecha» (con `px-3`
// y 8 px bajaba a otro renglón). Si de verdad no caben (320 px), se parten en renglones, nunca se cortan.
const CLASE = 'min-h-11 whitespace-nowrap rounded-full border border-borde-control bg-blanco px-2.5 texto-pequeno font-medium text-foreground transition-[background-color,transform] hover:bg-cafe-bruma active:scale-[0.98] motion-reduce:active:scale-100 disabled:opacity-60';

/**
 * «Borrar fecha», «Mañana» y «En 2 días»: valores editables relativos a hoy, en una fila que se
 * parte en renglones (sin scroll horizontal, que chocaría con el deslizamiento de mes). Antes del
 * mínimo de anticipación un atajo se deshabilita y dice por qué.
 */
export function Atajos({ hoy, minDate, haySeleccion, onBorrar, onElegir, textos }: Props) {
  const lista = atajosDe(hoy, minDate);
  const bloqueado = lista.some((a) => a.antesDelMinimo);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1.5">
        {haySeleccion && (
          <Button variante="libre" type="button" onClick={onBorrar} className={`${CLASE} flex items-center gap-1`}>
            {textos.borrar}
            <X size={14} weight="bold" aria-hidden />
          </Button>
        )}
        {lista.map((atajo) => (
          <Button
            key={atajo.clave}
            variante="libre"
            type="button"
            disabled={atajo.antesDelMinimo}
            onClick={() => onElegir(atajo.fecha)}
            className={CLASE}
          >
            {atajo.clave === 'manana' ? textos.manana : textos.en2}
          </Button>
        ))}
      </div>
      {bloqueado && <p className="texto-pequeno text-apagado">{textos.antesDelMinimo}</p>}
    </div>
  );
}
