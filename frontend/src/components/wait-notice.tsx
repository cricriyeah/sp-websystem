'use client';

import { useEffect, useState } from 'react';
import { CircleNotch } from '@phosphor-icons/react';

/**
 * Aviso de que el sistema esta trabajando, con palabras.
 *
 * Un spinner en un boton es correcto para 300ms y **falla** para los quince
 * segundos que puede tardar la confirmacion de un cargo. Pasados unos cuatro
 * segundos sin explicacion, el cliente supone que se rompio: le da otra vez, o
 * recarga, o cierra. Los tres desenlaces son peores que esperar.
 *
 * Por eso el mensaje escala. Primero dice que esta pasando; si se alarga, dice
 * ademas que sigue vivo y que no cierre. La segunda parte no es cortesia: es lo
 * que evita el recargue a medio cobro.
 */
export function WaitNotice({
  mensaje,
  mensajeLento,
  /** A partir de cuando se considera que esto ya tardo. */
  umbralLentoMs = 4000,
}: {
  mensaje: string;
  mensajeLento?: string;
  umbralLentoMs?: number;
}) {
  const [lento, setLento] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setLento(true), umbralLentoMs);
    return () => window.clearTimeout(id);
  }, [umbralLentoMs]);

  return (
    // aria-live para que un lector de pantalla anuncie el cambio de mensaje: sin
    // esto, quien no ve el spinner no tiene forma de saber que sigue en curso.
    <div
      aria-live="polite"
      className="mt-4 flex items-start gap-3 rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground"
    >
      {/* motion-safe: quien pidio menos movimiento ve el icono quieto, y el
          mensaje sigue haciendo todo el trabajo. */}
      <CircleNotch size={18} className="mt-0.5 shrink-0 text-accent motion-safe:animate-spin" />
      <p className="leading-snug">{lento && mensajeLento ? mensajeLento : mensaje}</p>
    </div>
  );
}
