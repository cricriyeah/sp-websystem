'use client';

import { useState, useSyncExternalStore } from 'react';
import Image from 'next/image';
import type { SedeTemporadas } from '@/content/sedes-tipos';
import { temporadaDeMes } from '@/lib/temporada-actual';
import { Button } from '@/components/ui/button';
import { cn } from '@/components/ui/cn';

const suscribirseAlMes = () => () => {};

type Props = {
  temporadas: SedeTemporadas;
  textos: { ahora: string };
};

/**
 * El calendario de especies (F10), en el orden de la pregunta «¿cuándo vienes?»: arriba, un bloque
 * grande por temporada (el periodo y, si toca, «ahora»); debajo, la foto de la elegida y sus especies en
 * grande. Arranca en la temporada del mes de hoy o, sin ella, en la fuerte.
 *
 * Sin saltos al cambiar: las fotos están todas montadas en el mismo recuadro y solo cambian de
 * opacidad (sin escala), y los textos de todas las temporadas comparten una celda de la cuadrícula, así
 * que el bloque mide siempre lo de la más larga y nada de abajo se mueve. En móvil el texto va antes que la foto: es la respuesta a lo que se acaba de tocar.
 */
export function TemporadasSelector({ temporadas, textos }: Props) {
  const { filas } = temporadas;
  const fuerte = Math.max(0, filas.findIndex((fila) => fila.fuerte));
  // El mes de hoy es del navegador: el servidor no lo sabe (-1) y el cliente lo lee al hidratar.
  const mes = useSyncExternalStore(suscribirseAlMes, () => new Date().getMonth(), () => -1);
  const hoy = temporadaDeMes(filas, mes);
  const [tocada, setTocada] = useState<number | null>(null);
  const elegida = tocada ?? (hoy >= 0 ? hoy : fuerte);

  return (
    <div className="mt-10 flex flex-col gap-10 lg:gap-14">
      <div>
        <p className="texto-etiqueta">{temporadas.etiquetaCalendario}</p>
        <div role="group" aria-label={temporadas.etiquetaCalendario} className="mt-4 grid gap-2 md:grid-cols-3">
          {filas.map((f, i) => (
            <Button
              key={f.periodo}
              variante="libre"
              aria-pressed={i === elegida}
              onClick={() => setTocada(i)}
              className={cn(
                // Móvil: un renglón por temporada (periodo a la izquierda, «ahora» a la derecha). Desde md: bloques.
                'flex min-h-16 items-center justify-between gap-3 p-4 text-left transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring md:min-h-24 md:flex-col md:items-start md:p-5',
                i === elegida ? 'bg-tinta text-white' : 'bg-superficie text-foreground hover:bg-borde',
              )}
            >
              <span className="texto-paso">{f.periodo}</span>
              <span className="texto-etiqueta">
                {i === hoy ? textos.ahora : ''}
                {i === hoy && f.fuerte ? <span className="hidden md:inline">{` · ${temporadas.etiquetaFuerte}`}</span> : null}
                {i !== hoy && f.fuerte ? <span className="hidden md:inline">{temporadas.etiquetaFuerte}</span> : null}
                {i !== hoy && !f.fuerte ? <span className="hidden md:inline">{' '}</span> : null}
              </span>
            </Button>
          ))}
        </div>
      </div>

      <div className="grid items-center gap-8 md:grid-cols-[1.3fr_1fr] lg:gap-16">
        <div className="relative order-2 aspect-[4/3] overflow-hidden bg-superficie md:order-1">
          {filas.map((f, i) => (
            <Image
              key={f.foto}
              src={f.foto}
              alt={i === elegida ? f.estrella : ''}
              fill
              loading="eager"
              sizes="(min-width: 768px) 56vw, 100vw"
              className={cn(
                'object-cover transition-opacity duration-500 ease-out motion-reduce:duration-150',
                i === elegida ? 'opacity-100' : 'opacity-0',
              )}
            />
          ))}
        </div>

        {/* Todos los textos en la misma celda: la altura es la de la temporada más larga. */}
        <div className="order-1 grid md:order-2" aria-live="polite">
          {filas.map((f, i) => (
            <div
              key={f.periodo}
              aria-hidden={i !== elegida}
              className={cn(
                'col-start-1 row-start-1 transition-opacity duration-500 ease-out motion-reduce:duration-150',
                i === elegida ? 'opacity-100' : 'invisible opacity-0',
              )}
            >
              <p className="texto-grande">{f.estrella}</p>
              <p className="mt-4 texto-subtitulo">{f.periodo}</p>
              {f.otras && (
                <p className="mt-6 max-w-[46ch] texto-cuerpo">
                  <span className="font-semibold">{temporadas.etiquetaOtras}:</span> {f.otras}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
